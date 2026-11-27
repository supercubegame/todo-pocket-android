"""Installed draft UI on the existing disposable draft job only; no normal phone, no user data, no release claim."""
from pathlib import Path
import hashlib,json,math,os,re,subprocess
PKG='com.supercubegame.pockettodo.v12.preview'
SCALES=((100,'1.0'),(130,'1.3'),(200,'2.0'))
CASES=('runtime_font_real_ime_and_owned_long_title','save_only_draft_cancel_and_reopen_no_auto_restore','recover_cancel_and_confirm_change_input_only','discard_cancel_then_confirm_only_own_draft','canonical_body_and_tombstone_survive_editor_reopen')
GEOM=('note-draft-save','note-draft-recover','note-draft-recover','note-draft-discard','note-draft-discard')
ORDER=(CASES[0],GEOM[0],CASES[1],GEOM[1],GEOM[2],CASES[2],GEOM[3],GEOM[4],CASES[3],CASES[4])
KEYS=(('system','font_scale'),('secure','show_ime_with_hard_keyboard'))
def need(value,message):
    if not value:raise AssertionError(message)
def parse(text,api,pct,nonce):
    need(type(api)==int and api in (26,34) and type(pct)==int and pct in dict(SCALES) and re.fullmatch(r'[0-9]+-[0-9]+-'+str(api)+'-'+str(pct),nonce),'invalid font scope')
    rows=[x.removeprefix('INSTRUMENTATION_RESULT: stream=') for x in text.splitlines()];rows=[x for x in rows if x.startswith(('FONT_','DEVICE_DATABASE_','INSTRUMENTATION_CODE:'))];need(len(rows)==13 and not re.search(r'DEVICE_DATABASE_FAILED|INSTRUMENTATION_(?:FAILED|ABORTED)|AssertionError|Exception:|Process crashed',text),'missing or failed runtime records')
    scope=re.fullmatch(r'FONT_SCOPE api=([0-9]+) pct=([0-9]+) nonce=([0-9-]+) settings=([0-9.]+) applied=([0-9.]+) package=([^ ]+) hardware=ranchu',rows[0]);need(scope is not None and (int(scope[1]),int(scope[2]),scope[3],scope[6])==(api,pct,nonce,PKG) and all(abs(float(scope[i])*100-pct)<.5 for i in (4,5)),'wrong runtime font or identity')
    need(rows[-2:]==['DEVICE_DATABASE_RESULT draft_font_ui 2/2 PASS','INSTRUMENTATION_CODE: -1'],'missing terminal instrumentation success');coords=r'(-?[0-9]+),(-?[0-9]+),(-?[0-9]+),(-?[0-9]+)';obs=[]
    for r,key in zip(rows[1:-2],ORDER,strict=True):
        if key in CASES:need(r=='FONT_CASE '+key+' PASS','wrong ordered behavior');continue
        hit=re.fullmatch('FONT_GEOMETRY '+key+' enabled=true rect='+coords+' ime='+coords+r' min=([0-9]+) lines=([0-9]+) chars=([0-9]+) scrolls=([0-9]+)',r);need(hit is not None,'missing exact geometry record')
        l,t,x,b,il,it,ix,ib,minimum,lines,chars,scrolls=map(int,hit.groups());need(minimum>0 and x-l>=minimum and b-t>=minimum and l>=0 and t>=0 and ix>il>=0 and ib>it>=0 and (x<=il or ix<=l or b<=it or ib<=t) and lines>0 and chars==(3 if key=='note-draft-save' else 4) and 0<=scrolls<=12,'bad target, IME, text length or scroll measurement');obs.append({'id':key,'button':[l,t,x,b],'ime':[il,it,ix,ib],'minimum_px':minimum,'lines':lines,'utf16':chars,'actual_touch_scrolls':scrolls})
    return {'api':api,'pct':pct,'nonce':nonce,'cases':list(CASES),'geometry':obs,'scope':'NATIVE_LAYOUT_IME_TOUCH_AND_FILE_SQL_NOT_RASTER_OEM'}

def matrix(cmd,run_one,collect,serial,pkg,api,env):
    need(env.get('GITHUB_ACTIONS')=='true' and serial=='emulator-5554' and pkg==PKG and type(api)==int and api in (26,34),'disposable CI only');rid=env['GITHUB_RUN_ID'];att=env['GITHUB_RUN_ATTEMPT'];src=env['GITHUB_SHA'];need(re.fullmatch(r'[0-9]+',rid) and re.fullmatch(r'[1-9][0-9]*',att) and re.fullmatch(r'[a-f0-9]{40}',src),'unbound run')
    for key,target in [('ro.kernel.qemu','1'),('ro.hardware','ranchu'),('ro.build.version.sdk',str(api))]:need(cmd('getprop',key).strip()==target,'unexpected emulator')
    get=lambda key:cmd('settings','get',*key).strip();before={k:get(k) for k in KEYS};active={};errors=[];rows=[];rest={};
    need(before[KEYS[1]] in ('null','0','1') and (before[KEYS[0]]=='null' or (re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',before[KEYS[0]]) and .5<=float(before[KEYS[0]])<=3)),'unexpected saved settings: no changes')
    def set_own(key,to):
        need(get(key)==active.get(key,before[key]),'concurrent setting change: leave alone');active[key]=to;cmd('settings','put',*key,to);need(get(key)==to,'setting write unconfirmed')
    try:
        set_own(KEYS[1],'1')
        for pct,value in SCALES:
            set_own(KEYS[0],value);nonce=f'{rid}-{att}-{api}-{pct}';rec={'source':src,'run_id':rid,'attempt':att,'api':api,'pct':pct,'nonce':nonce,'status':'NOT_ACCEPTED'}
            try:
                stop,text=run_one(pct,nonce);collect(f'font-{pct}.txt',text);rec['raw_sha256']=hashlib.sha256(text.encode()).hexdigest();need(stop==0,'instrumentation command failed');rec.update(parse(text,api,pct,nonce));rec['status']='PASS'
            except Exception as e:rec['error_class']=type(e).__name__;errors.append(type(e).__name__+' at '+str(pct))
            rows.append(rec)
    finally:
        for key in reversed(KEYS):
            if key not in active:continue
            try:
                current=get(key)
                if current!=before[key]:
                    need(current==active[key],'refuse to overwrite intervening setting');cmd('settings','delete',*key) if before[key]=='null' else cmd('settings','put',*key,before[key]);
                rest[key]=get(key)==before[key];need(rest[key],'setting restoration unconfirmed')
            except Exception as e:rest[key]=False;errors.append(type(e).__name__+' restoring '+key[1])
        status='PASS' if not errors and len(rows)==3 and all(r['status']=='PASS' for r in rows) and all(rest.get(k,False) for k in KEYS) else 'FAIL';result={'source':src,'run_id':rid,'attempt':att,'api':api,'original':{k[1]:v for k,v in before.items()},'restored':{k[1]:v for k,v in rest.items()},'raw_series':rows,'status':status,'physical_device':False,'pixel_measurement':False,'release_ready':False};collect('font-matrix.json',json.dumps(result,indent=2)+'\n')
    need(result['status']=='PASS','draft font series incomplete: '+', '.join(errors));return result

def device(adb,serial,pkg,api,out):
    prefix=[str(adb),'-s',serial,'shell'];out=Path(out)
    def shell(*a):return subprocess.check_output(prefix+list(a),stdin=subprocess.DEVNULL,timeout=12,text=True)
    def invoke(pct,nonce):
        args=prefix+['-n','-T','am','instrument','-w','-r','-e','expectedApi',str(api),'-e','phase','draft_font_ui','-e','fontPct',str(pct),'-e','fontNonce',nonce,pkg+'.test/com.supercubegame.pockettodo.V12DeviceTest'];
        try:p=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=145)
        except subprocess.TimeoutExpired as e:
            decode=lambda x:x.decode('utf-8','replace') if isinstance(x,bytes) else x or '';return None,decode(e.stdout)+'\n'+decode(e.stderr)+'\nFONT_TIMEOUT 145s\n'
        return p.returncode,p.stdout+'\n'+p.stderr
    def save(n,t):
        with (out/n).open('x',encoding='utf-8') as f:f.write(t)
    return matrix(shell,invoke,save,serial,pkg,api,os.environ)

def host():
    import copy
    env={'GITHUB_ACTIONS':'true','GITHUB_RUN_ID':'701','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'0'*40}
    def fixture(a,p,n):
        lines=[f'FONT_SCOPE api={a} pct={p} nonce={n} settings={p/100} applied={p/100} package={PKG} hardware=ranchu'];lines += [('FONT_CASE '+k+' PASS' if k in CASES else 'FONT_GEOMETRY '+k+' enabled=true rect=8,100,310,152 ime=0,350,320,640 min=48 lines=1 chars='+str(3 if k=='note-draft-save' else 4)+' scrolls=2') for k in ORDER];return '\n'.join(lines+['DEVICE_DATABASE_RESULT draft_font_ui 2/2 PASS','INSTRUMENTATION_CODE: -1'])
    rejected=0
    for a in (26,34):
        for p,_ in SCALES:
            n=f'701-1-{a}-{p}';s=fixture(a,p,n);assert parse(s,a,p,n)['pct']==p
            for old,new in [('hardware=ranchu','hardware=other'),(f'nonce={n}',f'nonce={n}0'),('applied='+str(p/100),'applied=0.1'),('note-draft-save','wrong'),('enabled=true','enabled=false'),('ime=0,350','ime=0,114'),('min=48','min=60'),('lines=1','lines=0'),('chars=3','chars=2'),('scrolls=2','scrolls=13'),('2/2 PASS','1/2 PASS'),('CODE: -1','CODE: 0'),('FONT_CASE '+CASES[1],'FONT_CASE '+CASES[0]),('FONT_SCOPE','DEVICE_DATABASE_FAILED\nFONT_SCOPE')]:
                assert old in s
                try:parse(s.replace(old,new,1),a,p,n)
                except AssertionError:rejected+=1
                else:raise AssertionError('accepted bad font receipt')
    loops={}
    for name in ['all','bad_middle','numeric_exit','ime_missing','restore_denied','foreign_after','not_ci','wrong_hardware','unknown_original']:
        state={KEYS[0]:'1.15' if name!='unknown_original' else 'unknown',KEYS[1]:'null'};saved=state.copy();written=[];calls=[];docs={}
        def shell(*args):
            if args[0]=='getprop':return {'ro.kernel.qemu':'0' if name=='wrong_hardware' else '1','ro.hardware':'ranchu','ro.build.version.sdk':'26'}[args[1]]
            _,op,group,k,*v=args;key=(group,k)
            if op=='get':return state[key]
            written.append((key,op,*v))
            if name=='restore_denied' and key==KEYS[1] and op=='delete':raise RuntimeError('simulated setting restore failure')
            state[key]=v[0] if op=='put' else 'null';return ''
        def invoke(p,n):
            calls.append(p);assert state[KEYS[0]]==dict(SCALES)[p];s=fixture(26,p,n)
            if name=='foreign_after' and p==200:state[KEYS[0]]='1.71'
            return (17 if p==130 and name=='numeric_exit' else 0),s.replace('CODE: -1','CODE: 0') if p==130 and name=='bad_middle' else s.replace('ime=0,350,320,640','ime=0,0,0,0') if name=='ime_missing' else s
        try:rr=matrix(shell,invoke,lambda n,v:docs.update({n:v}),'emulator-5554',PKG,26,env|({'GITHUB_ACTIONS':'false'} if name=='not_ci' else {}))
        except AssertionError:assert name!='all'
        else:assert name=='all' and rr['status']=='PASS'
        if name in ('not_ci','wrong_hardware','unknown_original'):assert not calls and not written and state==saved
        else:
            assert calls==[100,130,200] and len(docs)==4;r=json.loads(docs['font-matrix.json']);assert (r['status']=='PASS')==(name=='all')
            if name=='foreign_after':assert state[KEYS[0]]=='1.71' and state[KEYS[1]]=='null'
            elif name=='restore_denied':assert state[KEYS[0]]==saved[KEYS[0]] and not r['restored']['show_ime_with_hard_keyboard']
            else:assert state==saved
        loops[name]=len(calls)
    assert rejected==84 and len(loops)==9;print('DRAFT_FONT_HOST 6 positive / 84 rejected native receipt shapes; 9 setting lifecycle controls. HOST ONLY.')
