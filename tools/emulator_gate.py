#!/usr/bin/env python3
"""Create one disposable CI AVD, verify discovery, run real UI checks, terminate it."""
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
SDK = Path(os.environ['ANDROID_HOME'])
BASE = Path(os.environ['RUNNER_TEMP']) / ('pocket-avd-' + os.environ['GITHUB_RUN_ID'])
AVD_HOME = BASE / 'avd'
NAME = 'pocket-ci'
SERIAL = 'emulator-5554'

def run(args, timeout=60, capture=False, **kwargs):
    print('+ ' + ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, timeout=timeout,
                          text=True, stdout=subprocess.PIPE if capture else None, **kwargs)

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
    run([tools / 'sdkmanager', 'emulator', 'system-images;android-30;google_apis;x86_64'], timeout=360)
    avd = AVD_HOME / (NAME + '.avd')
    run([tools / 'avdmanager', 'create', 'avd', '--name', NAME, '--path', avd,
         '--package', 'system-images;android-30;google_apis;x86_64'], input='no\n', timeout=90)
    assert (avd / 'config.ini').is_file(), 'AVD creation did not produce configuration'
    # Tool versions can disagree on the discovery directory. Anchor the locator to
    # the explicitly created AVD, then assert emulator discovery before booting.
    locator = AVD_HOME / (NAME + '.ini')
    locator.write_text('avd.ini.encoding=UTF-8\npath=' + str(avd) + '\ntarget=android-30\n')
    listed = run([emulator, '-list-avds'], capture=True).stdout.splitlines()
    print('AVD_DISCOVERY', listed, flush=True)
    assert NAME in listed, 'emulator cannot discover the newly created AVD'
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
            p = subprocess.run([str(adb), '-s', SERIAL, 'shell', 'getprop', 'sys.boot_completed'],
                               capture_output=True, text=True, timeout=10)
            if p.returncode == 0 and p.stdout.strip() == '1':
                break
            time.sleep(2)
        else:
            raise TimeoutError('emulator boot deadline exceeded; see emulator.log')
        assert run([adb, '-s', SERIAL, 'shell', 'getprop', 'ro.kernel.qemu'], capture=True).stdout.strip() == '1'
        run([adb, '-s', SERIAL, 'shell', 'input', 'keyevent', '82'])
        for key in ['window_animation_scale', 'transition_animation_scale', 'animator_duration_scale']:
            run([adb, '-s', SERIAL, 'shell', 'settings', 'put', 'global', key, '0'])
        run(['python3', 'tools/ui_test.py'], timeout=600)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
        log.close()
        print('EMULATOR_PROCESS_EXITED', proc.returncode, flush=True)

if __name__ == '__main__':
    main()
