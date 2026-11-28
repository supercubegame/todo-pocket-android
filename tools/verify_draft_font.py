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

def _setting_value(key,v):
    # Only two known setting keys. Do not print arbitrary state, errors, commands or device content.
    if v=='null':return v
    if key==KEYS[1] and v in ('0','1'):return v
    if key==KEYS[0] and isinstance(v,str) and re.fullmatch(r'[0-9](?:\.[0-9]{1,8})?',v) and .5<=float(v)<=3:return v
    return 'unexpected'

def _row(cmd,key):
    # The getter alone cannot distinguish an absent row from a literal null. Never retain other settings.
    need(cmd('am','get-current-user').strip()=='0','only the foreground owner of this disposable AVD')
    ns,name=key;v=cmd('settings','--user','0','get',ns,name).strip();entries=[line[len(name)+1:] for line in cmd('settings','--user','0','list',ns).splitlines() if line.startswith(name+'=')]
    return dict(user=0,value=_setting_value(key,v),count=len(entries),listed=_setting_value(key,entries[0]) if len(entries)==1 else None)

def _exact(row,value):
    return isinstance(row,dict) and type(row.get('user')) is int and type(row.get('count')) is int and row=={'user':0,'value':value,'count':int(value!='null'),'listed':None if value=='null' else value} and value!='unexpected'

def _baseline_raw(text,api,nonce,stage):
    need(stage in ('original','neutral') and api in (26,34) and re.fullmatch(r'[0-9]+-[1-9][0-9]*-'+str(api)+'-'+stage,nonce) is not None,'unbound runtime sample')
    lines=[l.removeprefix('INSTRUMENTATION_RESULT: stream=') for l in text.splitlines()];w=[l for l in lines if l.startswith(('FONT_', 'DEVICE_DATABASE_', 'INSTRUMENTATION_CODE:'))]
    marker=f'FONT_BASELINE api={api} user=0 nonce={nonce} stage={stage} package={PKG} hardware=ranchu system=1.0 target=1.0'
    need(w==[marker,'DEVICE_DATABASE_RESULT draft_font_baseline 2/2 PASS','INSTRUMENTATION_CODE: -1'] and not re.search(r'INSTRUMENTATION_(?:ABORTED|FAILED)|Process crashed|Exception:|AssertionError',text),'runtime baseline not witnessed')
    return dict(api=api,user=0,nonce=nonce,stage=stage,system='1.0',target='1.0',raw_sha256=hashlib.sha256(text.encode()).hexdigest())

def _restore_owned(cmd,observe,key,original,owned,normalized):
    r={'original':_setting_value(key,original),'last_owned':_setting_value(key,owned),'seen_before':None,'after':None,'decision':'no_write','write_confirmed':False,'restored':False,'failed_stage':None,'error_class':None,'child_exit':None};stage='read_before'
    try:
        row=observe(key);r['before_row']=row;seen=r['seen_before']=row['value'];need(_exact(row,seen),'inconsistent initial setting row')
        if seen==original:r['decision']='already_original'
        else:
            if seen!=owned:r['decision']='foreign_refused';stage='owner_guard';raise AssertionError('intervening change left untouched')
            absent_font=key==KEYS[0] and original=='null'
            if absent_font:
                # The system can materialize a default if deletion would also change the runtime configuration.
                # Establish the previously observed 1.0 runtime first, then make exactly one guarded delete.
                r['decision']='normalize_delete';stage='normalize';r['normalized_written']=False
                if seen!='1.0':cmd('settings','--user','0','put',*key,'1.0');r['normalized_written']=True
                stage='normalize_read';r['neutral_row']=observe(key);need(_exact(r['neutral_row'],'1.0'),'neutral value not owned')
                stage='runtime';normalized('neutral');stage='delete_guard';r['delete_guard']=observe(key);need(_exact(r['delete_guard'],'1.0'),'concurrent change: no delete')
            else:r['decision']='delete' if original=='null' else 'put'
            stage='write'
            if original=='null':cmd('settings','--user','0','delete',*key)
            else:cmd('settings','--user','0','put',*key,original)
            r['write_confirmed']=True
        stage='read_after';r['after_row']=observe(key);r['after']=r['after_row']['value'];stage='verify';need(_exact(r['after_row'],original),'exact row not restored');r['restored']=True
    except Exception as e:
        r['error_class']=type(e).__name__;r['failed_stage']=stage
        if isinstance(e,subprocess.CalledProcessError):r['child_exit']=e.returncode
    return r

def matrix(cmd,run_one,collect,serial,pkg,api,env):
    need(env.get('GITHUB_ACTIONS')=='true' and serial=='emulator-5554' and pkg==PKG and type(api)==int and api in (26,34),'disposable CI only');rid=env['GITHUB_RUN_ID'];att=env['GITHUB_RUN_ATTEMPT'];src=env['GITHUB_SHA'];need(re.fullmatch(r'[0-9]+',rid) and re.fullmatch(r'[1-9][0-9]*',att) and re.fullmatch(r'[a-f0-9]{40}',src),'unbound run')
    for key,target in [('ro.kernel.qemu','1'),('ro.hardware','ranchu'),('ro.build.version.sdk',str(api))]:need(cmd('getprop',key).strip()==target,'unexpected emulator')
    def observe(k):return _row(cmd,k)
    def get(k):
        r=observe(k);need(_exact(r,r['value']),'owned setting row and getter disagree');return r['value']
    initial={k:observe(k) for k in KEYS};need(all(_exact(r,r['value']) for r in initial.values()),'conflicting original rows: no change');before={k:r['value'] for k,r in initial.items()};active={};errors=[];rows=[];rest={};runtime={}
    def baseline(stage):
        nonce=f'{rid}-{att}-{api}-{stage}';raw=cmd('am','instrument','--user','0','-w','-r','-e','expectedApi',str(api),'-e','phase','draft_font_baseline','-e','fontNonce',nonce,'-e','fontStage',stage,PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest');collect('font-config-'+stage+'.txt',raw);runtime[stage]=_baseline_raw(raw,api,nonce,stage)
    if before[KEYS[0]]=='null':baseline('original')
    need(before[KEYS[1]] in ('null','0','1') and (before[KEYS[0]]=='null' or (re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',before[KEYS[0]]) and .5<=float(before[KEYS[0]])<=3)),'unexpected saved settings: no changes')
    def set_own(key,to):
        need(get(key)==active.get(key,before[key]),'concurrent setting change: leave alone');active[key]=to;cmd('settings','--user','0','put',*key,to);need(get(key)==to,'setting write unconfirmed')
    try:
        set_own(KEYS[1],'1')
        for pct,value in SCALES:
            set_own(KEYS[0],value);nonce=f'{rid}-{att}-{api}-{pct}';rec={'source':src,'run_id':rid,'attempt':att,'api':api,'pct':pct,'nonce':nonce,'status':'NOT_ACCEPTED'}
            try:
                stop,text=run_one(pct,nonce);collect(f'font-{pct}.txt',text);rec['raw_sha256']=hashlib.sha256(text.encode()).hexdigest();need(stop==0,'instrumentation command failed');rec.update(parse(text,api,pct,nonce));rec['status']='PASS'
            except Exception as e:rec['error_class']=type(e).__name__;errors.append(type(e).__name__+' at '+str(pct))
            rows.append(rec)
    finally:
        evidence={}
        for key in reversed(KEYS):
            if key not in active:continue
            trace=_restore_owned(cmd,observe,key,before[key],active[key],baseline);evidence[key[1]]=trace;rest[key]=trace['restored']
            if not rest[key]:errors.append(str(trace['error_class'])+' restoring '+key[1]+' at '+str(trace['failed_stage']))
        status='PASS' if not errors and len(rows)==3 and all(r['status']=='PASS' for r in rows) and all(rest.get(k,False) for k in KEYS) else 'FAIL';result={'source':src,'run_id':rid,'attempt':att,'api':api,'original':{k[1]:v for k,v in before.items()},'restored':{k[1]:v for k,v in rest.items()},'restoration':evidence,'original_rows':{k[1]:v for k,v in initial.items()},'runtime_baseline':runtime,'raw_series':rows,'status':status,'physical_device':False,'pixel_measurement':False,'release_ready':False};collect('font-matrix.json',json.dumps(result,indent=2)+'\n')
    need(result['status']=='PASS','draft font series incomplete: '+', '.join(errors));return result

# Fixed, read-only API26 owner sample. Use one noninteractive shell for these three reads;
# never put externally supplied text into this command, and never run settings through it.
_OWNER26_SAMPLE = r'''printf '%s\n' PT26_BEGIN_V1
u=$(id -u) || { r=$?; printf '%s\n' PT26_ERROR_UID; exit "$r"; }
printf '%s\n' PT26_UID_DONE
f=$(am get-current-user) || { r=$?; printf '%s\n' PT26_ERROR_FOREGROUND; exit "$r"; }
printf '%s\n' PT26_FOREGROUND_DONE
p=$(pm list users) || { r=$?; printf '%s\n' PT26_ERROR_USERS; exit "$r"; }
printf 'PT26_VALUES\n%s\n%s\n%s\nPT26_END_V1\n' "$u" "$f" "$p"'''
_OWNER26_PREFIX=('PT26_BEGIN_V1','PT26_UID_DONE','PT26_FOREGROUND_DONE')

def _owner26(raw,at,trace):
    step='api26-owner-'+at;trace['step']=step;trace['owner_requests']=trace.get('owner_requests',0)+1
    try:text=raw('-n','-T',_OWNER26_SAMPLE)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
        # Report the failing child if it gave an unambiguous marker; never store identifiers,
        # full output, raw user lists, or assume that a transport 255 came from a remote read.
        b=e.output or '';b=b.decode('ascii','replace') if isinstance(b,bytes) else b;lines=tuple(b.splitlines()) if len(b)<=512 else ();kind='unattributed'
        for n,stage in enumerate(('uid','foreground','users'),1):
            if lines==_OWNER26_PREFIX[:n]+('PT26_ERROR_'+stage.upper(),):kind=stage
        trace['step']=step+'-'+kind;raise
    trace['step']=step+'-frame';need(type(text) is str and len(text)<=4096,'bounded legacy owner sample required');ls=text.splitlines()
    need(len(ls)>=9 and tuple(ls[:4])==_OWNER26_PREFIX+('PT26_VALUES',) and ls[-1]=='PT26_END_V1','incomplete owner frame')
    uid,fg=ls[4:6];users=[l.strip() for l in ls[6:-1] if l.strip()];trace['step']=step+'-membership'
    need(uid=='2000' and fg=='0' and len(users)==2 and users[0]=='Users:' and re.fullmatch(r'UserInfo\{0:[^:\r\n{}]{1,80}:[0-9a-fA-F]+\} running',users[1]) is not None,'legacy command refused without unique foreground owner and user-0 shell');trace['owner_checks']+=1

def _legacy26_settings(raw,argv,trace):
    # Android 8 SettingsService rejects --user for LIST/DELETE. These two call SettingsProvider as the caller,
    # unlike explicit GET/PUT. Never issue their implicit spelling on other users, namespaces or a real phone.
    verb,namespace=argv[3:5];tail=argv[5:];need(tuple(argv[:3])==('settings','--user','0') and ((verb=='list' and not tail and namespace in ('system','secure')) or (verb=='delete' and len(tail)==1 and (namespace,tail[0]) in KEYS)),'unowned legacy setting command')
    _owner26(raw,'before',trace);trace['step']='api26-'+verb+'-'+namespace;trace['legacy_'+verb]+=1;value=raw('settings',verb,namespace,*tail)
    _owner26(raw,'after',trace);trace['step']='api26-result-'+verb+'-'+namespace
    if verb=='list':
        entries=[s for s in value.splitlines() if s.strip()];need(bool(entries) and all(re.match(r'^[^=\s]+=',x) for x in entries),'malformed or empty provider listing; never proof of an absent key')
    else:need(value.strip()=='Deleted 1 rows','selected owned row was not deleted exactly once')
    return value

def legacy26_settings_controls():
    for case in ('ok','profile','uid','foreground','switch','badcount','badlist','scope'):
        calls=[];trace={'owner_checks':0,'legacy_list':0,'legacy_delete':0,'step':'init'}
        def run(*a):
            calls.append(a)
            if a==('-n','-T',_OWNER26_SAMPLE):
                uid='0' if case=='uid' else '2000';fg='11' if case=='foreground' or (case=='switch' and ('settings','list','system') in calls) else '0';users='Users:\n UserInfo{0:Owner:13} running'+('\n UserInfo{10:Other:30}\n' if case=='profile' else '')
                return '\n'.join(_OWNER26_PREFIX+('PT26_VALUES',uid,fg,users,'PT26_END_V1',''))
            if a==('settings','list','system'):return 'Bad arguments' if case=='badlist' else 'fixture=1'
            if a==('settings','delete','system','font_scale'):return 'Deleted 0 rows' if case=='badcount' else 'Deleted 1 rows'
            raise AssertionError('unexpected argv')
        try:
            _legacy26_settings(run,('settings','--user','0','list','system'),trace)
            _legacy26_settings(run,('settings','--user','0','delete','system','other' if case=='scope' else 'font_scale'),trace)
        except AssertionError:assert case!='ok'
        else:assert case=='ok' and trace['owner_checks']==4
        assert sum(a[:2]==('settings','delete') for a in calls)==int(case in ('ok','badcount'))
    print('LEGACY26_SETTINGS 8 scoped shapes incl wrong caller, scope, membership, removal and changed foreground; no Android',flush=True)

def device(adb,serial,pkg,api,out):
    prefix=[str(adb),'-s',serial,'shell'];out=Path(out)
    trace={'scope':'DISPOSABLE_SETTINGS_COMMAND_FAMILY_NO_USER_NAMES_OR_VALUES','source':os.environ.get('GITHUB_SHA'),'run':os.environ.get('GITHUB_RUN_ID'),'attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'api':api,'legacy_list':0,'legacy_delete':0,'owner_checks':0,'owner_requests':0,'step':'initial','first_failure':None}
    def raw(*a):return subprocess.check_output(prefix+list(a),stdin=subprocess.DEVNULL,timeout=12,text=True)
    def failed(e):
        if trace['first_failure'] is None:trace['first_failure']={'step':trace['step'],'kind':type(e).__name__,'child_exit':e.returncode if isinstance(e,subprocess.CalledProcessError) else None}
    def shell(*a):
        trace['step']=('explicit-'+a[3]+'-'+a[4]) if a[:3]==('settings','--user','0') else 'foreground' if a[:2]==('am','get-current-user') else 'runtime' if a[:2]==('am','instrument') else 'emulator-check'
        try:
            if api==26 and a[:3]==('settings','--user','0') and a[3] in ('list','delete'):
                need(serial=='emulator-5554' and pkg==PKG and os.environ.get('GITHUB_ACTIONS')=='true','disposable AVD only');return _legacy26_settings(raw,a,trace)
            return raw(*a)
        except Exception as e:failed(e);raise
    def invoke(pct,nonce):
        args=prefix+['-n','-T','am','instrument','-w','-r','-e','expectedApi',str(api),'-e','phase','draft_font_ui','-e','fontPct',str(pct),'-e','fontNonce',nonce,pkg+'.test/com.supercubegame.pockettodo.V12DeviceTest'];
        try:p=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=145)
        except subprocess.TimeoutExpired as e:
            decode=lambda x:x.decode('utf-8','replace') if isinstance(x,bytes) else x or '';return None,decode(e.stdout)+'\n'+decode(e.stderr)+'\nFONT_TIMEOUT 145s\n'
        return p.returncode,p.stdout+'\n'+p.stderr
    def save(n,t):
        with (out/n).open('x',encoding='utf-8') as f:f.write(t)
    try:return matrix(shell,invoke,save,serial,pkg,api,os.environ)
    except Exception as e:failed(e);raise
    finally:save('font-cli.json',json.dumps(trace,indent=2)+'\n')

def _confirmed_restores(j):
    originals=j.get('original',{});r=j.get('restoration',{});need(set(originals)==set(r)=={k[1] for k in KEYS},'incomplete original or restore receipts')
    for k,active in zip(KEYS,('2.0','1'),strict=True):
        name=k[1];orig=originals[name];ev=r[name];need(isinstance(orig,str) and _setting_value(k,orig)==orig and orig!='unexpected' and ev['restored'] is True and j['restored'][name] is True and ev['original']==ev['after']==orig and ev['last_owned']==active and ev['failed_stage'] is None and ev['error_class'] is None and ev['child_exit'] is None,'exact restore evidence missing')
        need(_exact(j['original_rows'][name],orig) and _exact(ev['before_row'],ev['seen_before']) and _exact(ev['after_row'],orig),'get and row membership not independently recorded')
        noop=ev['seen_before']==orig;norm=k==KEYS[0] and orig=='null' and not noop
        need((noop or ev['seen_before']==active) and ev['decision']==('already_original' if noop else 'normalize_delete' if norm else 'delete' if orig=='null' else 'put') and ev['write_confirmed'] is (not noop),'wrong owner or operation in restore receipt')
        if norm:need(ev['normalized_written'] is True and _exact(ev['neutral_row'],'1.0') and _exact(ev['delete_guard'],'1.0'),'neutralization not witnessed')

def _checked_owner_receipt(j,cli,src,rid,att):
    # Each successful matrix has 2 original observations, 2 for each of four setting writes,
    # and the pre/post row of both restores. Neutralization contributes its two additional rows.
    # Never infer a successful deletion from a CLI exit or a default runtime font value.
    traces=j['restoration'];normalize=traces['font_scale']['decision']=='normalize_delete'
    want_lists=2+2*(1+len(SCALES))+2*len(KEYS)+2*int(normalize)
    want_deletes=sum(v['decision'] in ('delete','normalize_delete') for v in traces.values())
    need(cli.get('scope')=='DISPOSABLE_SETTINGS_COMMAND_FAMILY_NO_USER_NAMES_OR_VALUES' and cli.get('api')==26 and (cli.get('source'),cli.get('run'),cli.get('attempt'))==(src,rid,att) and 'first_failure' in cli and cli['first_failure'] is None,'API26 owner evidence missing or failed')
    ns=('legacy_list','legacy_delete','owner_checks','owner_requests');counts=[cli.get(k) for k in ns]
    need(all(type(x) is int for x in counts) and counts==[want_lists,want_deletes,2*(want_lists+want_deletes),2*(want_lists+want_deletes)],'API26 pre/post samples or exact setting operations missing')

def check_font_files(folder,expected,api,src,rid,att):
    """Read only these four synthetic source-bound files; never trust the matrix's PASS alone."""
    raw=folder/'font-matrix.json';j=json.loads(raw.read_bytes());need(j.get('api')==api and j.get('source')==src and j.get('run_id')==rid and j.get('attempt')==att and j.get('status')=='PASS' and j.get('restored')=={'font_scale':True,'show_ime_with_hard_keyboard':True} and all(v is True for v in j['restored'].values()),'missing source-bound completed matrix and restored settings');_confirmed_restores(j); rows=j['raw_series'];need(len(rows)==3,'incomplete font series');labels=[]
    if api==26:_checked_owner_receipt(j,json.loads((folder/'font-cli.json').read_bytes()),src,rid,att)
    stages=[] if j['original']['font_scale']!='null' else ['original']+(['neutral'] if j['restoration']['font_scale']['decision']=='normalize_delete' else [])
    need(set(j['runtime_baseline'])==set(stages),'missing or unexpected baseline sample')
    for stage in stages:
        raw=(folder/('font-config-'+stage+'.txt')).read_bytes();n=f'{rid}-{att}-{api}-{stage}';need(_baseline_raw(raw.decode(),api,n,stage)==j['runtime_baseline'][stage],'unbound runtime raw')
    for row,(pct,_) in zip(rows,SCALES,strict=True):
        nonce=rid+'-'+att+'-'+str(api)+'-'+str(pct);data=(folder/f'font-{pct}.txt').read_bytes();need((row['source'],row['run_id'],row['attempt'],row['api'],row['pct'],row['nonce'],row['status'])==(src,rid,att,api,pct,nonce,'PASS') and row['raw_sha256']==hashlib.sha256(data).hexdigest(),'wrong individual run or output');parsed=parse(data.decode(),api,pct,nonce);need(parsed['cases']==row['cases'] and parsed['geometry']==row['geometry'],'raw and summarized geometry disagree');labels.append(pct)
    need(labels==[100,130,200] and set(expected)=={PKG,PKG+'.test'},'wrong package/scale set');return labels

def bind_full_endcheck(gate,root):
    """Capture both built APKs before alternate runners can replace either. Only the full Android database job calls this."""
    from verify_schema3 import registration
    from verify_todo_management import installed_readback
    env=os.environ;src,rid,att=env['GITHUB_SHA'],env['GITHUB_RUN_ID'],env['GITHUB_RUN_ATTEMPT'];owner='supercubegame/todo-pocket-android';wf=env.get('GITHUB_WORKFLOW_REF','')
    need(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==owner and env.get('GITHUB_JOB')=='database' and wf.startswith(owner+'/.github/workflows/android.yml@refs/heads/') and re.fullmatch('[0-9a-f]{40}',src) and rid.isdigit() and att.isdigit() and gate.API in (26,34) and gate.SERIAL=='emulator-5554' and gate.PKG==PKG,'not the full owned Android verification job')
    root=Path(root);expected={}
    for name,sub in [(PKG,'debug'),(PKG+'.test','androidTest/debug')]:
        files=list((root/'build/outputs/apk'/sub).glob('*.apk'));need(len(files)==1,'missing unique built APK');expected[name]=files[0].read_bytes();need(bool(expected[name]),'empty built APK')
    once=[]
    def finish(adb):
        need(not once,'duplicate endcheck');once.append(True);folder=root/'build/ci-end-draft-font';folder.mkdir(parents=True,exist_ok=False);prefix=[str(adb),'-s',gate.SERIAL];record={'scope':'DISPOSABLE_FULL_JOB_FONT_ENDCHECK','source':src,'run_id':rid,'attempt':att,'api':gate.API,'expected_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in expected.items()},'apk_readbacks':{},'status':'NOT_ACCEPTED','release_ready':False,'test_started':False}
        def command(argv,timeout=30):return subprocess.check_output(argv,timeout=timeout,stdin=subprocess.DEVNULL,text=True)
        thumbnail_error=None;image_attach_error=None;delete_window_error=None
        try:
            regs=command(prefix+['shell','pm','list','instrumentation']);need(registration(regs,'V12DeviceTest')['status']=='PASS','final runner not restored: no font setting changed')
            for name,original in expected.items():
                rec=[];record['apk_readbacks'][name]=rec;need(installed_readback(command,prefix,name,original,rec)==original,'installed APK identity mismatch: no settings changed')
            # Both independent installed probes use the exact just-read product/test bytes and the registered default runner.
            # Thumbnail-first requires no settings changes; preserve its original file even if the subsequent font probe also fails.
            from verify_note_thumbnails import device as verify_note_page
            try:verify_note_page(gate,adb,root)
            except Exception as error:
                thumbnail_error=error;print('INDEPENDENT_NOTE_THUMB_FAILURE '+type(error).__name__,flush=True)
            from verify_note_image_import import device as verify_image_attach
            try:verify_image_attach(gate,adb,root)
            except Exception as error:
                image_attach_error=error;print('INDEPENDENT_IMAGE_ATTACH_FAILURE '+type(error).__name__,flush=True)
            # The API26 in-window check owns a different synthetic DB. Run once even if ordinary UI wasn't reached.
            # Its receipt is not an external-tap result. Registration and both installed bytes must have matched first.
            if gate.API==26:
                from verify_note_delete_window import device as verify_owned_delete
                try:verify_owned_delete(gate,adb,root,record)
                except Exception as error:
                    delete_window_error=error;print('INDEPENDENT_OWNED_DELETE_FAILURE '+type(error).__name__,flush=True)
            record['test_started']=True;device(adb,gate.SERIAL,PKG,gate.API,folder);record['accepted_scales']=check_font_files(folder,expected,gate.API,src,rid,att);record['status']='PASS'
        except Exception as exc:
            record['error_class']=type(exc).__name__;raise
        finally:
            # Existing always-upload glob device-*.txt picks up even a partial failed matrix. No settings, permission, signer or workflow changes outside the disposable AVD.
            for leaf in ('font-100.txt','font-130.txt','font-200.txt','font-matrix.json','font-config-original.txt','font-config-neutral.txt','font-cli.json'):
                p=folder/leaf
                if p.is_file():
                    with (root/('device-draft-'+p.stem+'.txt')).open('xb') as out:out.write(p.read_bytes())
            with (root/'device-draft-font-binding.txt').open('x') as w:w.write(json.dumps(record,indent=2)+'\n')
            print('DRAFT_FONT_ENDCHECK '+str(record['status'])+' api='+str(gate.API),flush=True)
        if thumbnail_error is not None:raise thumbnail_error # A font pass cannot hide a thumbnail failure.
        if image_attach_error is not None:raise image_attach_error
        if delete_window_error is not None:raise delete_window_error
    return finish

def absent_restore_controls():
    # Two independent provider observations. A command completing is never treated as a successful removal.
    font=KEYS[0];api=34;count=0
    for mode in ('ok','foreign','intervened','config_miss','reinserted','getter_only','already','two_rows'):
        store={'value':'1.71' if mode=='foreign' else 'null' if mode=='already' else '2.0'};actions=[];runtime=[]
        def row(key):
            v=store['value'];listed='1.0' if actions and actions[-1]=='delete' and mode=='getter_only' else v
            return dict(user=0,value=v,count=2 if mode=='two_rows' else int(listed!='null'),listed=None if listed=='null' else listed)
        def send(*args):
            assert args[:3]==('settings','--user','0');op,ns,k,*rest=args[3:];assert (ns,k)==font;actions.append(op)
            store['value']=rest[0] if op=='put' else '1.0' if mode=='reinserted' else 'null'
        def sample(stage):
            runtime.append(stage);n='123-1-34-'+stage;t=f'FONT_BASELINE api=34 user=0 nonce={n} stage={stage} package={PKG} hardware=ranchu system=1.0 target=1.0\nDEVICE_DATABASE_RESULT draft_font_baseline 2/2 PASS\nINSTRUMENTATION_CODE: -1'
            _baseline_raw(t.replace('target=1.0','target=2.0') if mode=='config_miss' else t,api,n,stage)
            if mode=='intervened':store['value']='1.75'
        r=_restore_owned(send,row,font,'null','2.0',sample);assert r['restored'] is (mode in ('ok','already'))
        want=[] if mode in ('foreign','already','two_rows') else ['put'] if mode in ('intervened','config_miss') else ['put','delete']
        assert actions==want and runtime==(['neutral'] if actions else []) and (mode!='intervened' or store['value']=='1.75');count+=1
    assert all(not _exact(x,'null') for x in ({'user':False,'count':0,'value':'null','listed':None},{'user':0,'count':False,'value':'null','listed':None},{'user':0,'count':1,'value':'null','listed':'null'}));print('ABSENT_FONT_RESTORE',count,'owned/foreign/runtime/row paths, 3 false receipt shapes rejected; NOT Android',flush=True)

def full_evidence_controls():
    legacy26_settings_controls()
    from verify_note_image_import import host as image_attach_host
    image_attach_host()
    from verify_note_delete_window import host as owned_delete_host
    owned_delete_host()
    absent_restore_controls()
    import tempfile,copy,ast
    import emulator_gate as gates
    old=AssertionError('primary');secondary=ValueError('secondary');matrix={}
    for original in (True,False):
        for final in (True,False):
            actions=[]
            def done(adb):
                actions.append(adb)
                if not final:raise secondary
            error=None
            try:
                with gates.run_endcheck('sample',done):
                    actions.append('body')
                    if not original:raise old
            except Exception as exc:error=exc
            assert actions==['body','sample'] and error is (old if not original else None if final else secondary);matrix[original,final]=True
    # Shared Android source, not a second build. Nothing in a specialized workflow registers this hook.
    root=Path(__file__).resolve().parents[1]; tree=ast.parse((root/'tools/verify_schema3.py').read_text());runner=next(n for n in tree.body if getattr(n,'name','')=='android');st=ast.unparse(runner);assert st.count('gate.end_device_check = bind_full_endcheck(gate, gate.ROOT)')==1 and st.count('gate.end_device_check = None')==1 and st.index('bind_full_endcheck(gate, gate.ROOT)')<st.index('verify_exports.android_main()') and 'finally:' in st
    y=(root/'.github/workflows/android.yml').read_text();beg=y.index('\n  database:\n');end=y.index('\n  upgrade_baseline:\n',beg);block=y[beg:end];assert block.count('python3 tools/verify_schema3.py android')==1 and '            device-*.txt\n' in block
    for p in ('verify_note_drafts.py','verify_paged_exports.py'):
        assert 'gate.end_device_check = bind_full_endcheck' not in (root/'tools'/p).read_text()
    # Independent shape, not accepting self-reported matrix status if bytes or scope differ.
    env=dict(src='f'*40,rid='567',att='1');apks={PKG:b'app',PKG+'.test':b'test'};count=0
    with tempfile.TemporaryDirectory() as td:
        folder=Path(td)
        for api in (26,34):
            rawfiles={};rows=[]
            for p,_ in SCALES:
                n=f'567-1-{api}-{p}';lines=[f'FONT_SCOPE api={api} pct={p} nonce={n} settings={p/100} applied={p/100} package={PKG} hardware=ranchu'];lines+=['FONT_CASE '+v+' PASS' if v in CASES else 'FONT_GEOMETRY '+v+' enabled=true rect=8,100,300,160 ime=0,331,320,640 min=48 lines=1 chars='+str(3 if v.endswith('save') else 4)+' scrolls=1' for v in ORDER];t='\n'.join(lines+['DEVICE_DATABASE_RESULT draft_font_ui 2/2 PASS','INSTRUMENTATION_CODE: -1']);rawfiles[p]=t.encode();s=parse(t,api,p,n);rows.append(dict(source=env['src'],run_id='567',attempt='1',status='PASS',raw_sha256=hashlib.sha256(t.encode()).hexdigest(),**s))
            base=dict(api=api,source=env['src'],run_id='567',attempt='1',status='PASS',restored={'font_scale':True,'show_ime_with_hard_keyboard':True},raw_series=rows)
            base['original']={'font_scale':'1.25','show_ime_with_hard_keyboard':'1'};base['restoration']={};base['original_rows']={};base['runtime_baseline']={}
            def proven(x):return {'user':0,'value':x,'count':int(x!='null'),'listed':None if x=='null' else x}
            for k,last in zip(KEYS,('2.0','1')):
                orig=base['original'][k[1]];base['restoration'][k[1]]=dict(original=orig,last_owned=last,seen_before=last,after=orig,decision='already_original' if last==orig else 'put',write_confirmed=(last!=orig),restored=True,failed_stage=None,error_class=None,child_exit=None,before_row=proven(last),after_row=proven(orig));base['original_rows'][k[1]]=proven(orig)
            if api==26:(folder/'font-cli.json').write_text(json.dumps({'scope':'DISPOSABLE_SETTINGS_COMMAND_FAMILY_NO_USER_NAMES_OR_VALUES','api':26,'source':env['src'],'run':'567','attempt':'1','first_failure':None,'legacy_list':14,'legacy_delete':0,'owner_requests':28,'owner_checks':28}))
            for fault in ('wrong_after','forged_write','claimed_foreign','absent_restore','none','missing_raw','wrong_hash','wrong_source','wrong_order','partial','fake_pos','foreign_attempt','not_restored','fake_bool','omitted_case','missing_terminal','wrong_apks'):
                j=copy.deepcopy(base);b=dict(rawfiles);e=apks
                if fault=='wrong_after':j['restoration']['font_scale']['after']='1.0'
                if fault=='forged_write':j['restoration']['show_ime_with_hard_keyboard']['write_confirmed']=True
                if fault=='claimed_foreign':j['restoration']['font_scale']['seen_before']='1.75'
                if fault=='absent_restore':j['restoration'].pop('font_scale')
                if fault=='missing_raw':del b[130]
                if fault=='wrong_hash':j['raw_series'][2]['raw_sha256']='a'*64
                if fault=='wrong_source':j['source']='c'*40
                if fault=='wrong_order':j['raw_series'].reverse()
                if fault=='partial':j['raw_series'].pop()
                if fault=='fake_pos':j['raw_series'][1]['geometry'][0]['button'][0]+=1
                if fault=='foreign_attempt':j['raw_series'][1]['attempt']='2'
                if fault=='not_restored':j['restored']['font_scale']=False
                if fault=='fake_bool':j['restored']['font_scale']=1
                if fault=='omitted_case':j['raw_series'][1]['cases'].pop()
                if fault=='missing_terminal':b[130]=b[130].replace(b'CODE: -1',b'CODE: 0');j['raw_series'][1]['raw_sha256']=hashlib.sha256(b[130]).hexdigest()
                if fault=='wrong_apks':e={PKG:b'app'}
                for p in rawfiles:
                    f=folder/f'font-{p}.txt'
                    if p in b:f.write_bytes(b[p])
                    elif f.exists():f.unlink()
                (folder/'font-matrix.json').write_text(json.dumps(j))
                try:got=check_font_files(folder,e,api,**env)
                except (AssertionError,FileNotFoundError):assert fault!='none';count+=1
                else:assert fault=='none' and got==[100,130,200]
    assert count==32 and len(matrix)==4;print('FULL_FONT_HOST 2 bound matrices + 32 refusals; 4 independent result combinations; no second build or font dispatch, NOT Android')

def host():
    full_evidence_controls()
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
            if args[:2]==('am','get-current-user'):return '0'
            assert args[:3]==('settings','--user','0');op,group,*tail=args[3:]
            if op=='list':return '\n'.join(k+'='+v for (ns,k),v in state.items() if ns==group and v!='null')
            k,*v=tail;key=(group,k)
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
        if name=='foreign_after':
            ev=r['restoration']['font_scale'];assert ev['seen_before']=='1.71' and ev['decision']=='foreign_refused' and ev['failed_stage']=='owner_guard' and ev['after'] is None and not ev['write_confirmed']
        if name=='restore_denied':
            ev=r['restoration']['show_ime_with_hard_keyboard'];assert ev['decision']=='delete' and ev['failed_stage']=='write' and ev['error_class']=='RuntimeError' and not ev['write_confirmed']
    assert rejected==84 and len(loops)==9;print('DRAFT_FONT_HOST 6 positive / 84 rejected native receipt shapes; 9 setting lifecycle controls. HOST ONLY.')
