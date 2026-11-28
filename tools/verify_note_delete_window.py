"""API 26 only: on-app native control callbacks in a fixed fresh fixture. Never substitutes for the external UI or a real touchscreen."""
from pathlib import Path
import hashlib,json,os,re,subprocess
PKG='com.supercubegame.pockettodo.v12.preview'
CASES=('wrong_target_and_media_refused','unchecked_confirm_readonly','checked_back_readonly','exact_identity_single_delete_shared_media','reopen_readonly_exact_state')
SCOPE='API26_OWN_ACTIVITY_CONTROLS_NAMED_SCHEMA3_AND_MEDIA_NOT_EXTERNAL_TOUCH_OR_PROCESS_LOSS'
_TOGGLE='WINDOW_DELETE_TOGGLE handled=false same=true checked=true'

def labels(nonce):
    out=[f'NOTE_DELETE_WINDOW_SCOPE api=26 nonce={nonce} package={PKG} hardware=ranchu']
    for case in CASES:
        if case in ('checked_back_readonly','exact_identity_single_delete_shared_media'):out.append(_TOGGLE)
        out.append('WINDOW_DELETE_CASE '+case+' PASS')
    return out+['DEVICE_DATABASE_RESULT note_delete_window 2/2 PASS','INSTRUMENTATION_CODE: -1']
def parse(raw,nonce):
    assert re.fullmatch('[0-9]{1,20}-[1-9][0-9]{0,3}-26',nonce);text=raw.decode('utf-8','strict');lines=[l.removeprefix('INSTRUMENTATION_RESULT: stream=') for l in text.splitlines()];observed=[l for l in lines if l.startswith(('NOTE_DELETE_WINDOW_','WINDOW_DELETE_','DEVICE_DATABASE_','INSTRUMENTATION_CODE:'))];observed=[_TOGGLE if l=='WINDOW_DELETE_TOGGLE handled=true same=true checked=true' else l for l in observed];assert observed==labels(nonce) and not re.search(r'DEVICE_DATABASE_FAILED|INSTRUMENTATION_(?:FAILED|ABORTED)|AssertionError|Exception:|Process crashed',text),'incomplete on-app deletion evidence';return list(CASES)
def device(gate,adb,root,binding):
    e=os.environ;owner='supercubegame/todo-pocket-android';s,r,a=e['GITHUB_SHA'],e['GITHUB_RUN_ID'],e['GITHUB_RUN_ATTEMPT'];assert e.get('GITHUB_ACTIONS')=='true' and e.get('GITHUB_REPOSITORY')==owner and e.get('GITHUB_JOB')=='database' and e.get('GITHUB_WORKFLOW_REF','').startswith(owner+'/.github/workflows/android.yml@refs/heads/') and re.fullmatch('[0-9a-f]{40}',s) and re.fullmatch('[0-9]{1,20}',r) and re.fullmatch('[1-9][0-9]{0,3}',a) and type(gate.API) is int and gate.API==26 and gate.PKG==PKG and gate.SERIAL=='emulator-5554';assert (binding['source'],binding['run_id'],binding['attempt'],binding['api'])==(s,r,a,26) and set(binding['expected_sha256'])==set(binding['apk_readbacks'])=={PKG,PKG+'.test'}
    hashes={}
    for p,held in binding['apk_readbacks'].items():
        rec,=held;h=rec['actual_sha256'];assert rec['status']=='PASS' and rec['exact'] is True and re.fullmatch('[a-f0-9]{64}',h) and h==rec['expected_sha256']==binding['expected_sha256'][p] and type(rec['actual_bytes']) is int and rec['actual_bytes']==rec['expected_bytes']>0;hashes[p]=h
    nonce=f'{r}-{a}-26';root=Path(root);raw=root/'device-note-delete-window.txt';meta=root/'device-note-delete-window-meta.txt';assert not raw.exists() and not meta.exists(),'refusing old supplement evidence';result={'scope':SCOPE,'source':s,'run_id':r,'attempt':a,'api':26,'nonce':nonce,'installed_sha256':hashes,'status':'NOT_ACCEPTED','release_ready':False};code=None
    cmd=[str(adb),'-s',gate.SERIAL,'shell','-n','-T','am','instrument','-w','-r','-e','expectedApi','26','-e','phase','note_delete_window','-e','nonce',nonce,PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest']
    try:
        try:v=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL,timeout=92);code=v.returncode;b=v.stdout+b'\n'+v.stderr
        except subprocess.TimeoutExpired as t:b=(t.stdout or b'')+b'\n'+(t.stderr or b'')+b'\nWINDOW_DELETE_TIMEOUT 92\n'
        with raw.open('xb') as f:f.write(b)
        result.update(returncode=code,raw_sha256=hashlib.sha256(b).hexdigest());assert code==0,'delete supplement transport did not complete';result['cases']=parse(b,nonce);result['status']='PASS';return result
    finally:
        with meta.open('x') as f:json.dump(result,f,indent=2)
        print('OWNED_DELETE_WINDOW_END',result['status'],26,flush=True)
def host():
    n='314-1-26';a=labels(n);raw='\n'.join(a);assert parse(raw.encode(),n)==list(CASES);bad=['\n'.join(a[:i]+a[i+1:]) for i in range(len(a))]+[raw.replace(n,'123-1-26'),raw.replace('ranchu','phone'),raw.replace('api=26','api=34'),raw.replace(PKG,'other.app'),raw.replace('CODE: -1','CODE: 0'),raw.replace('2/2 PASS','1/1 PASS'),raw+'\n'+a[2],raw+'\nDEVICE_DATABASE_FAILED',raw+'\nProcess crashed',raw.replace(a[2]+'\n'+a[3],a[3]+'\n'+a[2])];
    pos=[i for i,l in enumerate(a) if l==_TOGGLE];assert len(pos)==2
    for first,second in (('true','true'),('false','true'),('true','false')):
        k=a.copy();k[pos[0]]=k[pos[0]].replace('handled=false','handled='+first);k[pos[1]]=k[pos[1]].replace('handled=false','handled='+second);assert parse(('\n'.join(k)).encode(),n)==list(CASES)
    for phrase in ('handled=unknown same=true checked=true','handled=false same=true checked=false','handled=true same=true checked=false','handled=false same=false checked=true'):
        bad.append(raw.replace(_TOGGLE,'WINDOW_DELETE_TOGGLE '+phrase,1))
    bad.append(raw.replace(_TOGGLE,_TOGGLE+'\n'+_TOGGLE,1))
    for t in bad:
        try:parse(t.encode(),n)
        except AssertionError:continue
        raise AssertionError('invalid deletion supplement accepted')
    print('OWNED_DELETE_WINDOW_HOST four checked/listener combinations;',len(bad),'malformed receipts rejected; not device evidence')
