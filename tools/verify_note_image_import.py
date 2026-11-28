"""Bounded, installed image-attachment guard. Uses test-only private fixture files; not a real-volume ENOSPC test."""
from pathlib import Path
import hashlib,json,os,re,subprocess
PKG='com.supercubegame.pockettodo.v12.preview'
CASES=('original_bytes_picker_read_format_and_local_staging_failures','v2_stale_owner_first_note_late_rollback_and_reopen','v3_stale_owner_first_note_late_rollback_and_reopen','v4_stale_owner_first_note_late_rollback_and_reopen')

def parse(text,api,nonce):
    assert type(api) is int and api in (26,34) and re.fullmatch(r'[0-9]{1,20}-[1-9][0-9]{0,3}-'+str(api),nonce),'unbound note image fixture'
    lines=[v.removeprefix('INSTRUMENTATION_RESULT: stream=') for v in text.splitlines()];actual=[s for s in lines if s.startswith(('ATTACH_','DEVICE_DATABASE_','INSTRUMENTATION_CODE:'))];expected=[f'ATTACH_SCOPE api={api} nonce={nonce} package={PKG} hardware=ranchu synthetic=true']+['ATTACH_NATIVE '+v+' PASS' for v in CASES]+['DEVICE_DATABASE_RESULT note_image_attach 2/2 PASS','INSTRUMENTATION_CODE: -1']
    assert actual==expected and not re.search(r'DEVICE_DATABASE_FAILED|INSTRUMENTATION_(?:FAILED|ABORTED)|AssertionError|Exception:|Process crashed',text),'absent, failed or wrong image-attachment receipt';return list(CASES)

def device(gate,adb,root):
    env=os.environ;src,rid,attempt=(env[k] for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'));api=gate.API;assert env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')=='supercubegame/todo-pocket-android' and env.get('GITHUB_JOB')=='database' and gate.PKG==PKG and gate.SERIAL=='emulator-5554' and api in (26,34) and re.fullmatch(r'[0-9a-f]{40}',src) and re.fullmatch(r'[0-9]{1,20}',rid) and re.fullmatch(r'[1-9][0-9]{0,3}',attempt),'not the owned Android job';nonce=f'{rid}-{attempt}-{api}';root=Path(root);raw=root/'device-note-image-attach.txt';meta=root/'device-note-image-attach-meta.txt';assert not raw.exists() and not meta.exists(),'old attachment result';r=dict(scope='ACTUAL_DEFAULT_INSTRUMENTATION_SYNTHETIC_PRIVATE_DATA_NOT_ENOSPC_OR_OEM_PICKER',source=src,run_id=rid,attempt=attempt,api=api,nonce=nonce,status='NOT_ACCEPTED',release_ready=False);cmd=[str(adb),'-s',gate.SERIAL,'shell','-n','-T','am','instrument','-w','-r','-e','expectedApi',str(api),'-e','phase','note_image_attach','-e','attachNonce',nonce,PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'];code=None
    try:
        try:p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=100);code=p.returncode;b=p.stdout+b'\n'+p.stderr
        except subprocess.TimeoutExpired as e:b=(e.stdout or b'')+b'\n'+(e.stderr or b'')+b'\nATTACH_TIMEOUT 100s\n'
        with raw.open('xb') as f:f.write(b)
        r.update(returncode=code,raw_sha256=hashlib.sha256(b).hexdigest());assert code==0,'attachment probe did not complete';r['cases']=parse(b.decode(),api,nonce);r['status']='PASS';return r
    finally:
        with meta.open('x') as f:json.dump(r,f,indent=2)
        print('IMAGE_ATTACHMENT_END',r['status'],api,flush=True)

def host():
    nbad=0
    for api in (26,34):
        nonce=f'1234-1-{api}';rows=[f'ATTACH_SCOPE api={api} nonce={nonce} package={PKG} hardware=ranchu synthetic=true']+['ATTACH_NATIVE '+v+' PASS' for v in CASES]+['DEVICE_DATABASE_RESULT note_image_attach 2/2 PASS','INSTRUMENTATION_CODE: -1'];raw='\n'.join(rows);assert parse(raw,api,nonce)==list(CASES)
        bad=[raw.replace(nonce,'9-1-'+str(api)),raw.replace('ranchu','other'),raw.replace('synthetic=true','synthetic=false'),raw.replace(PKG,'other.sample'),raw.replace('CODE: -1','CODE: 0'),raw.replace('2/2 PASS','1/2 PASS'),raw.replace('note_image_attach','note_thumbnails'),raw+'\nDEVICE_DATABASE_FAILED',raw+'\nATTACH_NATIVE unbound PASS',raw.replace(rows[1]+'\n'+rows[2],rows[2]+'\n'+rows[1]),raw.replace(rows[2],rows[3]),raw+'\nProcess crashed']+['\n'.join(rows[:i]+rows[i+1:]) for i in range(len(rows))]
        for other in bad:
            assert other!=raw
            try:parse(other,api,nonce)
            except AssertionError:nbad+=1
            else:raise AssertionError('wrong receipt accepted')
    assert nbad==38;print('IMAGE_ATTACHMENT_HOST 2 scoped positives / 38 rejected malformed outcomes: NOT ANDROID',flush=True)
