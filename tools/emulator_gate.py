#!/usr/bin/env python3
"""Disposable database/media-byte verification. No product UI or photo acceptance."""
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
SDK = Path(os.environ['ANDROID_HOME'])
API = int(os.environ.get('TEST_API', '26'))
assert API in (26, 34), 'only approved minimum/current API matrix'
BASE = Path(os.environ['RUNNER_TEMP']) / ('pocket-avd-' + os.environ['GITHUB_RUN_ID'] + '-' + str(API))
AVD_HOME = BASE / 'avd'
NAME = 'pocket-ci'
SERIAL = 'emulator-5554'
PKG = 'com.supercubegame.pockettodo.v12.preview'
RESTORE_SCOPE = 'SCHEMA2_DB_MEDIA_BYTES_PASS'
TABLES = ('revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports').split()
REQUIRED = {
    'seed': {
        'production snapshot equals independently encoded all-table fixture',
        'real backup ZIP contains exact semantic state and registered assets',
        'late restore failure is the exact injected SQLite trigger fault',
        'late commit failure rolls back deleted old data plus all inserted tables',
        'failed restore never modifies old media bytes',
        'successful replacement round-trips all tables and journals exactly',
        'restored media has exact source bytes',
        'restore replaces sentinel rather than merging and preserves todo order',
        'restore retains ordered choices and archived field values',
        'restore retains field-note relationship',
        'restored legacy import journal still prevents duplicate import',
        'restored money journal still prevents duplicate batch',
        'restored undo tombstone rejects resurrection',
        'same complete backup can be restored repeatedly without duplicates',
        'new unregistered table cannot silently disappear from backup',
    } | {'backup fixture covers nonempty ' + table for table in TABLES},
    'reopen': {
        'separate process retains complete restored state',
        'separate process retains restored media bytes',
        'restored exact-cent totals remain usable after restart',
        'restored latest batch undo works after separate-process restart',
        'restored import journal still works after restart',
    },
}
for label in (
    'valid ZIP with missing registered media', 'valid ZIP with unregistered extra media',
    'unknown state schema', 'trailing semantic state bytes', 'invalid archived numeric field',
    'impossible check-in date', 'ordered path gap', 'inconsistent money batch journal',
    'media registry size mismatch', 'unknown saved choice',
):
    REQUIRED['seed'].update((label + ' rejected', label + ' keeps complete prior DB state'))

def verify_phase(output, phase):
    assert 'DEVICE_DATABASE_FAILED' not in output and 'INSTRUMENTATION_FAILED' not in output
    found = re.findall(r'DEVICE_DATABASE_RESULT ' + phase + r' (\d+)/(\d+) PASS', output)
    assert len(found) == 1 and found[0][0] == found[0][1] and int(found[0][0]) > 0, 'missing exact device pass result'
    assert re.findall(r'^INSTRUMENTATION_CODE: (-?\d+)\s*$', output, re.M) == ['-1'], 'instrumentation did not finish successfully'
    labels = re.findall(r'(?:^|stream=)PASS ([^\r\n]+)', output, re.M)
    assert len(labels) == int(found[0][0]), 'declared check count differs from actual PASS records'
    missing = REQUIRED[phase] - set(labels)
    assert not missing, 'restore coverage missing: ' + repr(sorted(missing))
    return int(found[0][0])

def parser_selftest():
    checks = 0
    def synthetic(labels, phase, code=-1, count=None):
        n = len(labels) if count is None else count
        return '\n'.join('PASS ' + x for x in labels) + '\nDEVICE_DATABASE_RESULT ' + phase + ' ' + str(n) + '/' + str(n) + ' PASS\nINSTRUMENTATION_CODE: ' + str(code) + '\n'
    for phase in ('seed', 'reopen'):
        labels = sorted(REQUIRED[phase])
        assert verify_phase(synthetic(labels, phase), phase) == len(labels)
        checks += 1
        for broken in (synthetic(labels[:-1], phase), synthetic(labels, phase, code=0), synthetic(labels, phase, count=len(labels)+1), synthetic(labels, phase)+'DEVICE_DATABASE_FAILED\n'):
            refused = False
            try: verify_phase(broken, phase)
            except AssertionError: refused = True
            assert refused, 'coverage parser negative fixture unexpectedly accepted'
            checks += 1
    print('RESULT_PARSER_SELFTEST', checks, 'PASS; parser only, not device behavior', flush=True)

def run(args, timeout=60, capture=False, **kwargs):
    print('+ ' + ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, timeout=timeout,
                          text=True, stdout=subprocess.PIPE if capture else None, **kwargs)

def verify_database(adb):
    apks = list(Path('build/outputs/apk/debug').glob('*.apk'))
    tests = list(Path('build/outputs/apk/androidTest/debug').glob('*.apk'))
    assert len(apks) == len(tests) == 1, 'exactly one app and instrumentation APK required'
    aapt = SDK / 'build-tools/35.0.0/aapt'
    badging = run([aapt, 'dump', 'badging', apks[0]], capture=True).stdout
    permissions = run([aapt, 'dump', 'permissions', apks[0]], capture=True).stdout
    assert "name='" + PKG + "'" in badging
    assert "versionCode='3'" in badging and "versionName='1.2'" in badging
    assert "sdkVersion:'26'" in badging and "targetSdkVersion:'34'" in badging
    assert 'uses-permission:' not in permissions
    signature = run([SDK / 'build-tools/35.0.0/apksigner', 'verify', '--verbose', '--print-certs', apks[0]], capture=True).stdout
    Path('device-package.txt').write_text(badging + '\n' + permissions + '\n' + signature)
    for apk in [apks[0], tests[0]]:
        run([adb, '-s', SERIAL, 'install', '-t', str(apk)], timeout=120)
    results = {}
    for phase in ('seed', 'reopen'):
        if phase == 'reopen':
            run([adb, '-s', SERIAL, 'shell', 'am', 'force-stop', PKG])
            proc = subprocess.run([str(adb), '-s', SERIAL, 'shell', 'pidof', PKG], text=True, capture_output=True, timeout=10)
            assert proc.returncode == 1 and not proc.stdout.strip(), 'prior app process must be absent before reopen'
        output = run([adb, '-s', SERIAL, 'shell', 'am', 'instrument', '-w', '-r', '-e', 'phase', phase,
                      '-e', 'expectedApi', str(API), PKG + '.test/com.supercubegame.pockettodo.V12DeviceTest'], timeout=180, capture=True).stdout
        print(output, flush=True)
        Path('device-' + phase + '.txt').write_text(output)
        results[phase] = verify_phase(output, phase)
    Path('device-result.json').write_text(json.dumps({'status': 'PASS', 'api': API, 'checks': results,
        'scope': 'ANDROID_SCHEMA2_DATABASE_AND_MEDIA_BYTES', 'ui': 'NOT_TESTED', 'image_decoding': 'NOT_TESTED',
        'full_backup_restore': RESTORE_SCOPE, 'saf_restore_ui': 'NOT_TESTED', 'power_loss': 'NOT_TESTED',
        'release_ready': False}, indent=2))

def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'disposable GitHub runner only'
    parser_selftest()
    BASE.mkdir(parents=True, exist_ok=False)
    AVD_HOME.mkdir()
    os.environ['ANDROID_USER_HOME'] = str(BASE)
    os.environ['ANDROID_EMULATOR_HOME'] = str(BASE)
    os.environ['ANDROID_AVD_HOME'] = str(AVD_HOME)
    os.environ['ANDROID_SERIAL'] = SERIAL
    tools = SDK / 'cmdline-tools/latest/bin'
    emulator = SDK / 'emulator/emulator'
    adb = SDK / 'platform-tools/adb'
    os.environ['PATH'] = str(adb.parent) + os.pathsep + os.environ['PATH']
    run(['sudo', 'chmod', '666', '/dev/kvm'])
    image = 'system-images;android-' + str(API) + ';google_apis;x86_64'
    run([tools / 'sdkmanager', 'emulator', image], timeout=360)
    avd = AVD_HOME / (NAME + '.avd')
    run([tools / 'avdmanager', 'create', 'avd', '--name', NAME, '--path', avd,
         '--package', image], input='no\n', timeout=90)
    assert (avd / 'config.ini').is_file(), 'AVD creation did not produce configuration'
    locator = AVD_HOME / (NAME + '.ini')
    locator.write_text('avd.ini.encoding=UTF-8\npath=' + str(avd) + '\ntarget=android-' + str(API) + '\n')
    listed = run([emulator, '-list-avds'], capture=True).stdout.splitlines()
    print('AVD_DISCOVERY', listed, flush=True)
    assert NAME in listed, 'emulator cannot discover newly created AVD'
    log = open('emulator.log', 'w')
    proc = subprocess.Popen([str(emulator), '-avd', NAME, '-port', '5554', '-no-window', '-no-metrics',
                             '-no-audio', '-no-boot-anim', '-no-snapshot', '-gpu', 'swiftshader_indirect',
                             '-memory', '2048', '-camera-back', 'none', '-camera-front', 'none'],
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 240
        last = 'no probe yet'
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                log.flush()
                raise RuntimeError('emulator exited before boot: ' + Path('emulator.log').read_text()[-4000:])
            try:
                p = subprocess.run([str(adb), '-s', SERIAL, 'shell', 'getprop', 'sys.boot_completed'], capture_output=True, text=True,
                                   timeout=min(10, max(0.1, deadline-time.monotonic())))
                last = 'rc=' + str(p.returncode) + ' stdout=' + p.stdout.strip() + ' stderr=' + p.stderr[-300:]
                if p.returncode == 0 and p.stdout.strip() == '1': break
            except subprocess.TimeoutExpired:
                last = 'boot probe timed out; emulator still alive=' + str(proc.poll() is None)
                print('BOOT_RETRY', last, flush=True)
            time.sleep(min(2, max(0, deadline-time.monotonic())))
        else:
            raise TimeoutError('emulator boot deadline exceeded: ' + last + '; see emulator.log')
        assert run([adb, '-s', SERIAL, 'shell', 'getprop', 'ro.kernel.qemu'], capture=True).stdout.strip() == '1'
        verify_database(adb)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=10)
        log.close()
        print('EMULATOR_PROCESS_EXITED', proc.returncode, flush=True)

if __name__ == '__main__': main()
