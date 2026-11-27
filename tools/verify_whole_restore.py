"""Exact staged synthetic source + strictly ordered native receipts. Not physical-phone/LMK proof."""
from pathlib import Path
import hashlib,os,re,subprocess,tempfile
from verify_schedule_book import fixture,DIGEST
MOD=('owned_outer_transaction_and_missing_media_refused_v{}','whole_restore_exact_v{}','same_revision_and_external_write_refused_v{}','late_failures_preserve_whole_database_v{}','changed_media_and_reopen_do_not_revive_v{}')
UI=('saf_preview_unchecked_cancel_keeps_original','undo_review_unchecked_cancel_retains_restored_state','confirmed_restore_undo_exact_sql_and_old_media','subsequent_edit_refused_new_row_preserved','source_zip_unchanged_and_each_choice_explicit')
PH={'whole_restore_model':tuple(l.format(v) for v in (2,3,4) for l in MOD),'whole_restore_undo':UI}
def expected(api,phase):return [f'WHOLE_SCOPE api={api} package=com.supercubegame.pockettodo.v12.preview hardware=ranchu isolated=true',*['WHOLE_NATIVE '+v+' PASS' for v in PH[phase]],f'DEVICE_DATABASE_RESULT {phase} 2/2 PASS','INSTRUMENTATION_CODE: -1']
def parse(text,api,phase):
    lines=[s.removeprefix('INSTRUMENTATION_RESULT: stream=') for s in text.splitlines()];seen=[s for s in lines if s.startswith(('WHOLE_','DEVICE_DATABASE_RESULT','INSTRUMENTATION_CODE:'))]
    if api not in (26,34) or seen!=expected(api,phase) or re.search(r'DEVICE_DATABASE_FAILED|INSTRUMENTATION_(?:FAILED|ABORTED)|AssertionError|Exception:|Process crashed',text):raise AssertionError('Whole restore not verified: '+phase)
    return PH[phase]
def stage(adb,serial,api,pkg):
    if os.environ.get('GITHUB_ACTIONS')!='true' or serial!='emulator-5554' or api not in (26,34) or pkg!='com.supercubegame.pockettodo.v12.preview':raise AssertionError('Disposable CI only')
    base=[str(adb),'-s',serial];shell=lambda *a:subprocess.check_output(base+['shell',*a],timeout=15,text=True).strip();assert shell('getprop','ro.kernel.qemu')=='1' and shell('getprop','ro.build.version.sdk')==str(api)
    data=fixture();assert hashlib.sha256(data).hexdigest()==DIGEST;folder=f'/sdcard/Download/pocket-whole-restore-ci-api{api}';subprocess.run(base+['shell','mkdir',folder],timeout=15,check=True);dest=folder+'/restore-source.zip'
    with tempfile.TemporaryDirectory() as t:
        f=Path(t)/'restore-source.zip';f.write_bytes(data);subprocess.run(base+['push',str(f),dest],check=True,timeout=20)
    assert subprocess.check_output(base+['exec-out','cat',dest],timeout=20)==data

def host_selftest():
    assert hashlib.sha256(fixture()).hexdigest()==DIGEST;bad=0
    for api in (26,34):
        for phase in PH:
            original=expected(api,phase);assert parse('\n'.join(original),api,phase)==PH[phase]
            for sample in ([s for j,s in enumerate(original) if j!=i] for i in range(len(original))):
                try:parse('\n'.join(sample),api,phase)
                except AssertionError:bad+=1
                else:raise AssertionError('missing receipt accepted')
            for sample in (original+[original[-1]],original[:1]+list(reversed(original[1:-2]))+original[-2:],original+['Process crashed'],[original[0].replace('isolated=true','isolated=false')]+original[1:],original[:-1]+['INSTRUMENTATION_CODE: 0']):
                try:parse('\n'.join(sample),api,phase)
                except AssertionError:bad+=1
                else:raise AssertionError('wrong control accepted')
    assert bad==72;print('WHOLE_HOST exact source, 4 positive +',bad,'negative receipt cases; no device')
