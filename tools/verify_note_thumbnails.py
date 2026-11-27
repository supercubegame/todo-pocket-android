"""Ordinary note rendering: one scoped phase per existing disposable AVD. Raster allocations are not the process heap."""
from pathlib import Path
import hashlib,json,os,re,subprocess,tempfile
PKG='com.supercubegame.pockettodo.v12.preview'
EVENTS=('immutable_display_buffer_and_owned_temporary','BYTES','real_note_24_rows_three_bitmap_allocations','missing_invalid_render_as_markers_no_source_write','PAGES','nine_distinct_forward_back_no_drop_or_stale_page','middle_page_confirm_cancel_and_offpage_rows_preserved','fresh_load_recovers_missing_no_global_cache_state_exact')

def parse(text,api,nonce):
    assert type(api) is int and api in (26,34) and re.fullmatch('[0-9]+-[1-9][0-9]*-'+str(api),nonce),'bad provenance'
    lines=[l.removeprefix('INSTRUMENTATION_RESULT: stream=') for l in text.splitlines()];rows=[l for l in lines if l.startswith(('THUMB_','DEVICE_DATABASE_','INSTRUMENTATION_CODE:'))];assert not re.search('DEVICE_DATABASE_FAILED|INSTRUMENTATION_(FAILED|ABORTED)|AssertionError|Exception:|Process crashed',text),'failed or incomplete device run';assert len(rows)==11 and rows[0]==f'THUMB_SCOPE api={api} nonce={nonce} package={PKG} hardware=ranchu synthetic=true' and rows[-2:]==['DEVICE_DATABASE_RESULT note_thumbnails 2/2 PASS','INSTRUMENTATION_CODE: -1'],'wrong scope, count or terminal';out={}
    for item,line in zip(EVENTS,rows[1:-2],strict=True):
        if item=='BYTES':
            h=re.fullmatch(r'THUMB_BYTES rows=24 unique=3 rowBytes=([0-9]+) uniqueBytes=([0-9]+)',line);assert h;total,unique=map(int,h.groups());assert total==8*unique and 3*512*384*4<=unique<=3*4194304;out.update(references=24,distinct=3,referenced_bytes=total,unique_bytes=unique)
        elif item=='PAGES':
            h=re.fullmatch(r'THUMB_PAGES unique=4,4,1 retained=([0-9]+),([0-9]+),([0-9]+)',line);assert h;pages=list(map(int,h.groups()));assert all(n*512*384*4<=b<=n*4194304 for b,n in zip(pages,(4,4,1),strict=True));out['page_unique_bytes']=pages
        else:assert line=='THUMB_NATIVE '+item+' PASS','missing/wrong native result'
    return out

def host():
    cases=0
    for a in (26,34):
        n=f'99-1-{a}';rows=[f'THUMB_SCOPE api={a} nonce={n} package={PKG} hardware=ranchu synthetic=true']+[('THUMB_BYTES rows=24 unique=3 rowBytes=18874368 uniqueBytes=2359296' if x=='BYTES' else 'THUMB_PAGES unique=4,4,1 retained=3145728,3145728,786432' if x=='PAGES' else 'THUMB_NATIVE '+x+' PASS') for x in EVENTS]+['DEVICE_DATABASE_RESULT note_thumbnails 2/2 PASS','INSTRUMENTATION_CODE: -1'];t='\n'.join(rows);assert parse(t,a,n)['unique_bytes']==2359296
        bad=[t.replace(n,'88-1-'+str(a)),t.replace('ranchu','other'),t.replace('rows=24','rows=23'),t.replace('unique=3','unique=24'),t.replace('18874368','2359296'),t.replace('2359296','1'),t.replace('3145728,3145728','3145728,30000000'),t.replace('4,4,1','4,3,2'),t.replace('CODE: -1','CODE: 0'),t+'\nDEVICE_DATABASE_FAILED',t.replace('2/2 PASS','1/2 PASS'),t+'\n'+rows[2],t.replace(rows[2]+'\n'+rows[3],rows[3]+'\n'+rows[2])]+['\n'.join(rows[:i]+rows[i+1:]) for i in range(1,9)];
        for b in bad:
            assert b!=t
            try:parse(b,a,n)
            except AssertionError:cases+=1
            else:raise AssertionError('bad thumbnail receipt accepted')
    assert cases==42;print('NOTE_THUMB_HOST 2 scope positives / 42 corrupted receipts refused, NOT Android',flush=True)

def device(gate,adb,root):
    env=os.environ;src=env['GITHUB_SHA'];run=env['GITHUB_RUN_ID'];att=env['GITHUB_RUN_ATTEMPT'];api=gate.API;assert env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')=='supercubegame/todo-pocket-android' and env.get('GITHUB_JOB')=='database' and re.fullmatch('[0-9a-f]{40}',src) and run.isdigit() and re.fullmatch('[1-9][0-9]*',att) and api in (26,34) and gate.PKG==PKG and gate.SERIAL=='emulator-5554';nonce=f'{run}-{att}-{api}';raw=Path(root)/'device-note-thumbnails.txt';summary=Path(root)/'device-note-thumbnails-meta.txt';assert not raw.exists() and not summary.exists(),'stale thumbnail result';meta=dict(source=src,run_id=run,run_attempt=att,api=api,nonce=nonce,status='NOT_ACCEPTED',scope='SYNTHETIC_NOTE_BITMAP_ALLOCATIONS_NOT_TOTAL_HEAP_OR_OEM',release_ready=False);cmd=[str(adb),'-s',gate.SERIAL,'shell','-n','-T','am','instrument','-w','-r','-e','expectedApi',str(api),'-e','phase','note_thumbnails','-e','thumbNonce',nonce,PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'];code=None
    try:
        try:
            p=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120);code=p.returncode;data=p.stdout+b'\n'+p.stderr
        except subprocess.TimeoutExpired as exc:data=(exc.stdout or b'')+b'\n'+(exc.stderr or b'')+b'\nTHUMB_TIMEOUT 120s\n'
        with raw.open('xb') as f:f.write(data)
        meta.update(returncode=code,raw_sha256=hashlib.sha256(data).hexdigest());assert code==0,'thumbnail instrumentation did not exit cleanly';meta.update(parse(data.decode(),api,nonce));meta['status']='PASS';return meta
    finally:
        with summary.open('x') as f:json.dump(meta,f,indent=2)
        print('NOTE_THUMB_END',meta['status'],api,flush=True)
