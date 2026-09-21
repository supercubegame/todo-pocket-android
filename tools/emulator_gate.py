#!/usr/bin/env python3
"""Disposable Android database/API verification. No product UI or release acceptance."""
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
        assert 'DEVICE_DATABASE_FAILED' not in output and 'INSTRUMENTATION_FAILED' not in output
        found = re.findall(r'DEVICE_DATABASE_RESULT ' + phase + r' (\d+)/(\d+) PASS', output)
        assert len(found) == 1 and found[0][0] == found[0][1] and int(found[0][0]) > 0, 'missing exact device pass result'
        assert 'INSTRUMENTATION_CODE: -1' in output, 'instrumentation did not finish successfully'
        results[phase] = int(found[0][0])
    Path('device-result.json').write_text(json.dumps({'status': 'PASS', 'api': API, 'checks': results,
        'scope': 'ANDROID_DATABASE_AND_BYTE_TRANSPORT_ONLY', 'ui': 'NOT_TESTED', 'image_decoding': 'NOT_TESTED',
        'full_backup_restore': 'NOT_TESTED', 'release_ready': False}, indent=2))

def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'disposable GitHub runner only'
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
    proc = subprocess.Popen([str(emulator), '-avd', NAME, '-port', '5554', '-no-window',
                             '-no-audio', '-no-boot-anim', '-no-snapshot', '-gpu', 'swiftshader_indirect',
                             '-memory', '2048', '-camera-back', 'none', '-camera-front', 'none'],
                            stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                log.flush()
                raise RuntimeError('emulator exited before boot: ' + Path('emulator.log').read_text()[-4000:])
            p = subprocess.run([str(adb), '-s', SERIAL, 'shell', 'getprop', 'sys.boot_completed'], capture_output=True, text=True, timeout=10)
            if p.returncode == 0 and p.stdout.strip() == '1': break
            time.sleep(2)
        else: raise TimeoutError('emulator boot deadline exceeded; see emulator.log')
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
