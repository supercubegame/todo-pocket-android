"""Public synthetic book made from the real v4 exporter; no user data, new permissions or app test URI. Browser/SAF acceptance only comes from the device receipt."""
from pathlib import Path
import base64, hashlib, io, json, os, re, subprocess, tempfile, zipfile, zlib
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
STATE='eNqtVUtv00AQTuI4SZNSBOJvVPgVJ+aAaNWoVAgUqT0gLtFmd50u8UvOJiJHTggJpCJVQgi4cClnbnDg19BW/Rfsw3bsJEi8VnG8O5755pvZ2dn+0d5uqVRS2FMtlRp6X64riewmexoxnpEJCYNEXiGI/asz4E0xm5TLJTmyyXX2NCGgeBTGBE8SKGlWDYDPrRpROCFUgi4QuF7t/OTV+cnrVMbHJogijzBEpr8ebjMCcAxGeJCsM0hFQn47vTz9rCSyJoCUzJh3wU3NwFoJ5/lALLdyXqVEpYR6gj2I4TGZYS5UUlf7K4lQ1sWTTu7/mfrBb6nztxoBepymqZXEmsSUT3uV4meUB7/CSFgql6dfVrmKLz++vhP2YPQ3bvYLbspgNX9CPmR/9SGg8FhsUzXbpnoE5l4I0FJp1qYBCgOc2e9yi7tJTpTQQ6kbXgGGZljbmrFtOByw97jfe3TYS7zvcLCrF2+uPn1MGTXz1VjzMBrhmLtflE4xfgWBOec8JoGoG4gDKoLwsR9yQxHXaq5kehnXLCdKka2So1tO+SoLwjLyPNsGyx9kPNJSX8+0NqGATvMUWzGGYYwwGgCar7q1jA4fHPT7vT3B/uLtGX/fkirmtqYfadod8XvCOfgYEVA8xD4Rh1YdzqnY6wr/dq9joW4HDiHQusDBGtTY0mpbXcexTQd0HAu1kdVlH21gt11bN4aog21NR0zQxtAVRInPusLtpxEepQGoAhyBjoZcYCHHddoAOh32NnTcxbZhmu2uYdqmbrqmaQEXIs2GCLld0LYNHbo20LEIe0OCR0GGzaVqENKlpreU86yNiO2ucv3soIm9vDx7fvHhJZ8NvRCOOdgGTzPXlBCV1WOW1Fp63BpgMsFUatchiBK1ehSTGWtzbHqDdecRCYA3yKkuKIlYRISF86oePNzZ7ynp8r8kUjl//71w+P9573nuXII9VGwd6XVRpfNouY/zcU3YDMIof9M0pPAXeRf3k9QQN2LqcLkj5kDy5tk1ykdLKqUFVCnueR5CFDINUViML6usatIKV5pLeSwTvuaG4WPLwyMAGWc/CmOaktiYhNMYJjSahGJ/AMNpQJcAslPwEygglrg='
DIGEST='23f6a2e6aca0a16aac6489b5174b688b5085dd07099b6ab7d85e65ecc8788bcc'
LABELS=('native_today_entry_no_auto_import','real_saf_cancel_unchecked_confirm_and_publish','stable_duplicate_ids_archived_readonly_private_values_absent','changed_snapshot_refuses_confirmation','confirmed_rule_today_uses_its_zone_no_automatic_marks','one_verified_saf_export_independent_restore','reopen_from_today_preserves_source_book_and_full_media')
sha=lambda b:hashlib.sha256(b).hexdigest()
def fixture():
    # categories 1; duplicate titles IDs 71/72/73; 73 archived; one historical ledger/check-in,
    # one private note with a current and original media ID. Opaque marker bytes, no photo/PII.
    state=zlib.decompress(base64.b64decode(STATE));assert sha(state)=='998228b66669320bbf593ffba0e9a76f18b2ffeb2d4ff50ccd829d92566b9a45' and state[:12]==bytes.fromhex('505444420000000300000004');media={sha(x):x for x in [bytes([11,22,33,44,55]),bytes([51,52,53])]};manifest=('POCKET_TODO_ARCHIVE\n1\n'+sha(state)+' '+str(len(state))+'\n'+''.join(f'{k} {len(media[k])}\n' for k in sorted(media))).encode();dst=io.BytesIO()
    with zipfile.ZipFile(dst,'w') as z:
        for name,data in [('manifest.txt',manifest),('state.bin',state),*[('media/'+k,media[k]) for k in sorted(media)]]:
            info=zipfile.ZipInfo(name,(2024,2,29,0,0,0));info.create_system=3;info.external_attr=0o600<<16;z.writestr(info,data)
    return dst.getvalue()
def stage(adb,serial,api,pkg):
    assert os.environ.get('GITHUB_ACTIONS')=='true' and serial=='emulator-5554' and api in (26,34) and pkg=='com.supercubegame.pockettodo.v12.preview';prefix=[str(adb),'-s',serial];shell=lambda *v:subprocess.check_output(prefix+['shell',*v],timeout=15,text=True).strip();assert shell('getprop','ro.kernel.qemu')=='1' and shell('getprop','ro.build.version.sdk')==str(api);data=fixture();assert sha(data)==DIGEST
    path='/sdcard/Download/pocket-book-ci-api'+str(api);subprocess.run(prefix+['shell','mkdir',path],check=True,timeout=15);file=path+'/schedule-input.zip'
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'schedule-input.zip';p.write_bytes(data);subprocess.run(prefix+['push',str(p),file],check=True,timeout=20)
    actual=subprocess.check_output(prefix+['exec-out','cat',file],timeout=20);assert actual==data;Path('device-book-public-fixture.txt').write_text(json.dumps({'source':os.environ.get('GITHUB_SHA'),'run':os.environ.get('GITHUB_RUN_ID'),'attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'api':api,'size':len(actual),'sha256':sha(actual),'scope':'SYNTHETIC_PUBLIC_EMULATOR_DOWNLOAD_ONLY'})+'\n')
def required(api):return [f'BOOK_SCOPE api={api} package=com.supercubegame.pockettodo.v12.preview hardware=ranchu physical=false',*['BOOK_NATIVE '+l+' PASS' for l in LABELS],'DEVICE_DATABASE_RESULT schedule_book_ui 2/2 PASS','INSTRUMENTATION_CODE: -1']
def parse(text,api):
    lines=[s.removeprefix('INSTRUMENTATION_RESULT: stream=') for s in text.splitlines()];scope=[s for s in lines if s.startswith(('BOOK_','DEVICE_DATABASE_RESULT','INSTRUMENTATION_CODE:'))];
    if api not in (26,34) or scope!=required(api) or re.search(r'DEVICE_DATABASE_FAILED|INSTRUMENTATION_(?:FAILED|ABORTED)|AssertionError|Exception:|Process crashed',text):raise AssertionError('Schedule book UI not verified; see device-schedule-book.txt')
    return LABELS

def stop_contract():
    # Execute the exact fixed shell script using benign local process doubles; no ADB/device.
    import contextlib,sys
    from verify_process_control import snapshot_stop26
    tag='1'*32;cases=['pass','waiting','pre255','pre_multi','stop255','stop_noise','post255','new_pid','post_empty_zero','post_one_with_pid','post_stderr','never_gone','lost_outer','missing_end','foreign_nonce','duplicate_ack'];rows={}
    for kind in cases:
      with tempfile.TemporaryDirectory() as td:
        d=Path(td);files={'sleep':'exit 0', 'am':'''echo "$*" >>"$TMPD/stops"; [ "$K" = stop255 ] && exit 255; [ "$K" = stop_noise ] && echo unexpected; exit 0''', 'pidof':'''n=0; [ ! -f "$TMPD/n" ] || n=$(cat "$TMPD/n"); echo $((n+1)) >"$TMPD/n"
if [ "$n" = 0 ]; then [ "$K" != pre255 ] || exit 255; [ "$K" != pre_multi ] || { echo '7383 89';exit 0; }; echo 7383;exit 0; fi
case "$K" in post255)exit 255;; new_pid)echo 8111;exit 0;; post_empty_zero)exit 0;;post_one_with_pid)echo 7383;exit 1;;post_stderr)echo problem >&2;exit 1;; never_gone)echo 7383; exit 0;;waiting)if [ "$n" = 1 ];then echo 7383;exit 0;fi;;esac;exit 1'''}
        for f,s in files.items():p=d/f;p.write_text('#!/bin/sh\n'+s+'\n');p.chmod(0o700)
        calls=[];records=[]
        def run(cmd,**kw):
            assert cmd[:-1]==['fixture-adb','-s','emulator-5554','shell','-n','-T'] and kw['timeout']==30;calls.append(cmd);p=subprocess.run(['/bin/sh','-c',cmd[-1]],cwd=d,env=dict(os.environ,PATH=str(d)+':'+os.environ['PATH'],K=kind,TMPD=str(d)),**kw)
            if kind=='lost_outer':p.returncode=255
            elif kind=='missing_end':p.stdout=p.stdout.replace(tag+' END\n','')
            elif kind=='foreign_nonce':p.stdout=p.stdout.replace(tag,'2'*32,1)
            elif kind=='duplicate_ack':p.stdout=p.stdout.replace(tag+' STOP 0\n',(tag+' STOP 0\n')*2)
            return p
        ok=True
        with contextlib.redirect_stdout(io.StringIO()):
            try:snapshot_stop26('fixture-adb','emulator-5554','com.supercubegame.pockettodo.v12.preview',runner=run,emit=records.append,nonce=tag)
            except (ValueError,subprocess.SubprocessError):ok=False
        expected=kind in ('pass','waiting');assert ok==expected and len(calls)==1 and len(records)==1 and (records[0]['status']=='PASS')==expected,kind;stops=(d/'stops').read_text().splitlines() if (d/'stops').exists() else [];assert stops==([] if kind in ('pre255','pre_multi') else ['force-stop com.supercubegame.pockettodo.v12.preview']),kind;rows[kind]={'passed':ok,'stops':len(stops)}
    return rows

def host_selftest():
    data=fixture();assert sha(data)==DIGEST;z=zipfile.ZipFile(io.BytesIO(data));assert len(z.namelist())==4 and not z.testzip();manifest=ET.parse(ROOT/'src/main/AndroidManifest.xml');a='{http://schemas.android.com/apk/res/android}';m=[x for x in manifest.findall('.//activity') if x.get(a+'name','').endswith('.ScheduleBookActivity')];assert len(m)==1 and m[0].get(a+'exported')=='false' and not m[0].findall('intent-filter') and not manifest.findall('uses-permission');controls=0
    for api in (26,34):
        v=required(api);s='\n'.join(v);assert parse(s,api)==LABELS
        for bad in ['\n'.join(v[:i]+v[i+1:]) for i in range(len(v))]+[s+'\n'+v[-1],s+'\nDEVICE_DATABASE_FAILED',s.replace(v[2],v[1]),s.replace('2/2','1/1'),s.replace('ranchu','phone'),s.replace('api='+str(api),'api=0')]:
            try:parse(bad,api)
            except AssertionError:controls+=1;continue
            raise AssertionError('invalid book receipt accepted')
    rows=stop_contract();print('BOOK_HOST fixed_synthetic_zip='+sha(data)+' receipt_rejections='+str(controls)+' checkpoint_shell_cases='+str(len(rows))+' NO_ANDROID',flush=True)
if __name__=='__main__':host_selftest()
