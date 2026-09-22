#!/usr/bin/env python3
"""Disposable DB/media and bounded native UI slice; never full product acceptance."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import xml.etree.ElementTree as ET

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
        'scope': 'ANDROID_SCHEMA2_DATABASE_AND_MEDIA_BYTES', 'ui': 'SEE_NATIVE_UI_RESULT', 'image_decoding': 'NOT_TESTED',
        'full_backup_restore': RESTORE_SCOPE, 'saf_restore_ui': 'SEE_NATIVE_UI_RESULT', 'power_loss': 'NOT_TESTED',
        'release_ready': False}, indent=2))

def verify_native_ui(adb):
    """Only real taps/text input; independently read SQLite after force-stop, no seeding UI DB."""
    out = Path('native-ui'); out.mkdir(exist_ok=True)
    checks, shots = [], []
    infra_retries = []
    def shell(*args):
        return subprocess.check_output([str(adb), '-s', SERIAL, 'shell', *args], text=True, timeout=40)
    def nodes():
        last=None
        for attempt in range(4):
            try:
                shell('uiautomator', 'dump', '/sdcard/pocket-window.xml')
                return list(ET.fromstring(shell('cat', '/sdcard/pocket-window.xml')).iter('node'))
            except (subprocess.CalledProcessError, ET.ParseError) as exc:
                last=exc; infra_retries.append('uiautomator-snapshot')
                print('INFRA_RETRY uiautomator snapshot attempt '+str(attempt+1)+' failed: '+repr(exc),flush=True)
                time.sleep(1.5)
        raise AssertionError('uiautomator snapshot failed repeatedly: '+repr(last))
    def tap_node(n):
        assert n.get('enabled')=='true', 'disabled touch target '+repr(n.attrib)
        x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')))
        assert x2>x1 and y2>y1, 'empty touch bounds'
        shell('input','tap',str((x1+x2)//2),str((y1+y2)//2))
    def swipe_up():
        shell('input','swipe','160','500','160','180','350'); time.sleep(.4)
    def find(**attrs):
        deadline=time.monotonic()+20; last=[]
        while time.monotonic()<deadline:
            last=nodes()
            for n in last:
                if all(n.get(k)==v for k,v in attrs.items()): return n
            crash=[n for n in last if n.get('resource-id')=='android:id/aerr_close']
            if crash:
                title=' '.join(x for x in (n.get('text') for n in last if n.get('resource-id')=='android:id/alertTitle') if x)
                assert '口袋待办' not in title and 'Pocket' not in title, 'own app crashed: '+title
                print('DISMISS_FOREIGN_CRASH '+title,flush=True)
                tap_node(crash[0]); time.sleep(.5); continue
            time.sleep(.25)
        raise AssertionError('UI missing '+repr(attrs)+'; actual='+repr([n.attrib for n in last if n.get('text') or n.get('content-desc')]))
    def desc(value): return find(**{'content-desc':value})
    def tap(text): tap_node(find(text=text))
    def touch(value): tap_node(desc(value))
    def type_text(value): shell('input','text',value.replace(' ','%s'))
    def ok(condition,label):
        assert condition,label
        checks.append(label); print('UI_PASS '+label,flush=True)
    def absent(text): return not any(n.get('text')==text for n in nodes())
    def gone(text):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if absent(text): return
            time.sleep(.25)
        raise AssertionError('UI still shows '+repr(text))
    def ready(): find(**{'content-desc':'v12-status','text':'已保存到本机'})
    def start():
        shell('am','start','-W','-n',PKG+'/com.supercubegame.pockettodo.MainActivity'); desc('v12-home'); ready()
    def stop():
        shell('am','force-stop',PKG)
        p=subprocess.run([str(adb),'-s',SERIAL,'shell','pidof',PKG],text=True,capture_output=True,timeout=10)
        assert p.returncode==1 and not p.stdout.strip(),'UI process must actually stop'
    def restart(): stop(); start()
    def clear_field(description):
        n=desc(description); count=len(n.get('text','').encode('utf-16-le'))//2
        tap_node(n); shell('input','keyevent','KEYCODE_MOVE_END')
        shell('input','keyevent',*(['KEYCODE_DEL']*(count+1)))
        assert desc(description).get('text')=='','input fixture not cleared'
    def shot(name):
        data=subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','screencap','-p'],timeout=30)
        assert data[:8]==b'\x89PNG\r\n\x1a\n','real PNG signature required'
        (out/name).write_bytes(data)
        shots.append({'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    def named_todo(title):
        n=find(text=title); assert n.get('class')=='android.widget.CheckBox' and n.get('content-desc','').startswith('todo-'),n.attrib
        return n
    def add_todo(title):
        touch('新待办输入'); type_text(title); tap('添加'); ready(); return named_todo(title)
    def copy_db(name):
        local=out/name
        local.write_bytes(subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','databases/pocket-v12.db'],timeout=30))
        present=shell('run-as',PKG,'ls','databases').splitlines()
        if 'pocket-v12.db-wal' in present:
            Path(str(local)+'-wal').write_bytes(subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','databases/pocket-v12.db-wal'],timeout=30))
        return local
    def select_days(days):
        tap('选择日期'); clear_field('日历月份'); type_text('2026-09'); tap('转到')
        tap('清空选择')
        for day in days: touch('calendar-day-2026-09-'+str(day).zfill(2))
        tap('应用选择'); ready()
    def money(day,kind,amount,save=True):
        tap('记一笔'); clear_field('账目日期'); type_text(day)
        touch('ledger-kind-'+kind); touch('金额（元）'); type_text(amount)
        tap('保存账目' if save else '取消'); ready()
    def metric(name,value):return desc('metric-'+name).get('text')==value
    def export_backup():
        tap('活动'); ready(); tap('备份 / 恢复'); ready()
        tap('导出完整备份')
        save=find(text='SAVE'); tap_node(save)
        find(**{'content-desc':'v12-status','text':'备份已保存到你选的位置'})
        tap('返回活动'); ready()
    def import_backup(label):
        tap('活动'); ready()
        if absent('恢复完整备份'): tap('备份 / 恢复'); ready()
        tap('恢复完整备份')
        file=find(text=label); tap_node(file)
        dialog=desc('restore-consent')
        assert dialog.get('enabled')=='true' and dialog.get('checked')=='false','consent checkbox starts visible and unchecked'
        counts=desc('restore-counts').get('text')
        assert counts is not None and '普通待办：本机 3 → 备份 2' in counts,'restore preview shows exact current and incoming todo counts; actual='+repr(counts)
        ok(True,'SAF file selection shows visible restore preview and replacement counts')
        return dialog
    try:
        start()
        ok(find(text='还剩 0 件 / 共 0 件') is not None,'new UI database starts empty without fabricated activities')
        tap('添加'); ok(find(text='内容不能为空') is not None,'blank todo rejected visibly')
        a=add_todo('Buy milk'); aid=a.get('content-desc')[5:]
        b=add_todo('Walk outside'); bid=b.get('content-desc')[5:]
        ok(aid!=bid,'UI adds distinct stable todo identities')
        touch('todo-'+aid); ready()
        ok(named_todo('Buy milk').get('checked')=='true','real checkbox completes todo')
        tap('待办'); ready(); ok(absent('Buy milk') and named_todo('Walk outside') is not None,'pending filter excludes completed row')
        tap('已完成'); ready(); ok(absent('Walk outside') and named_todo('Buy milk').get('checked')=='true','completed filter excludes pending row')
        tap('全部'); ready(); touch('edit-'+aid); clear_field('编辑待办输入'); tap('保存')
        ok(find(text='内容不能为空') is not None,'invalid edit stays open without losing original')
        tap('取消'); ok(named_todo('Buy milk').get('checked')=='true','cancel invalid edit preserves value and completion')
        touch('edit-'+aid); clear_field('编辑待办输入'); type_text('Fresh milk'); tap('保存'); ready()
        ok(named_todo('Fresh milk').get('content-desc')=='todo-'+aid and named_todo('Fresh milk').get('checked')=='true','title edit preserves stable identity and completion')
        restart(); ok(named_todo('Fresh milk').get('checked')=='true' and named_todo('Walk outside').get('checked')=='false','native todo state survives actual process restart')
        shot('01-todos.png')
        tap('活动'); ready(); tap('新建分类'); touch('分类名称'); type_text('Daily'); tap('保存'); ready()
        ok(find(text='Daily') is not None,'category created through visible native dialog')
        touch('category-rename-1'); clear_field('分类名称'); type_text('Checkins'); tap('保存'); ready()
        ok(find(text='Checkins') is not None and absent('Daily'),'category rename updates visible label')
        touch('category-add-1'); touch('活动名称'); type_text('Daily reward'); tap('保存'); ready()
        ok(desc('activity-1').get('text')=='Daily reward','activity created under selected category')
        touch('activity-1'); ready(); swipe_up(); tap('编辑路径'); touch('活动路径'); type_text('Home'); shell('input','keyevent','KEYCODE_ENTER'); type_text('Daily rewards'); tap('保存'); ready(); swipe_up()
        ok(find(text='1. Home') is not None and find(text='2. Daily rewards') is not None,'ordered multiline manual path displays without collapse')
        tap('标记完成'); ready(); ok(find(text='今天：已完成') is not None,'daily check-in writes visible done state')
        tap('标记完成'); ready(); ok(find(text='今天：已完成') is not None,'repeated daily mark remains one visible day')
        tap('跳过今天'); ready(); ok(find(text='今天：已跳过') is not None,'skipped is distinct from done and unrecorded')
        shot('02-activity.png')
        tap('返回分类'); ready(); tap('新建分类'); touch('分类名称'); type_text('Farm'); tap('保存'); ready()
        touch('category-up-2'); ready()
        cats=[n.get('text') for n in nodes() if n.get('content-desc','').startswith('category-name-')]
        ok(cats==['Farm','Checkins'],'accessible category reorder changes exact visible order')
        shot('03-categories.png')
        restart(); tap('活动'); ready()
        cats=[n.get('text') for n in nodes() if n.get('content-desc','').startswith('category-name-')]
        ok(cats==['Farm','Checkins'],'category order persists after process restart')
        touch('activity-1'); ready()
        ok(find(text='今天：已跳过') is not None,'skipped mark persists after process restart')
        swipe_up(); ok(find(text='2. Daily rewards') is not None,'activity path persists after process restart')
        ok(len({x['sha256'] for x in shots})==len(shots),'actual native screenshots represent distinct states')
        stop()
        with sqlite3.connect(copy_db('pocket-v12.db')) as db:
            ok(db.execute('SELECT id,title,done FROM todos ORDER BY position').fetchall()==[(aid,'Fresh milk',1),(bid,'Walk outside',0)],'independent SQLite read matches exact UI todo identities titles and states')
            ok(db.execute('SELECT id,name FROM categories ORDER BY position').fetchall()==[(2,'Farm'),(1,'Checkins')],'independent SQLite read matches renamed reordered categories')
            ok(db.execute('SELECT category_id,application_id,title FROM activities').fetchall()==[(1,None,'Daily reward')],'activity stays in its category without invented application')
            ok(db.execute('SELECT position,text FROM paths ORDER BY position').fetchall()==[(0,'Home'),(1,'Daily rewards')],'independent SQLite read preserves path order')
            marks=db.execute('SELECT activity_id,day,status,recorded_at FROM checkins').fetchall()
            ok(len(marks)==1 and marks[0][0]==1 and marks[0][2]=='SKIPPED' and bool(marks[0][1]) and bool(marks[0][3]),'repeated native marks persist exactly one day with entry timestamp')
            ok(db.execute('SELECT count(*) FROM ledger').fetchone()[0]==0,'check-in does not invent money entries')
        start(); tap('活动'); ready(); touch('activity-1'); ready(); tap('日历账本'); ready()
        ok(metric('EXPENSE','支出 ¥0.00'),'new native ledger starts with empty selection and zero summary')
        select_days([1,2,3]); ok(desc('selected-days').get('text')=='已选 3 天 · 仅汇总，不批量写入','calendar multi-select is explicit read-only scope')
        money('2026-09-01','EXPENSE','15'); money('2026-09-02','EXPENSE','20'); money('2026-09-03','EXPENSE','45')
        ok(metric('EXPENSE','支出 ¥80.00') and metric('NET_EXPENSE','净支出 ¥80.00'),'three different-day amounts total exactly 80 yuan in native UI')
        money('2026-09-03','EXPENSE','99',False)
        ok(metric('EXPENSE','支出 ¥80.00'),'cancel native entry does not change totals')
        tap('记一笔'); touch('金额（元）'); type_text('1.001'); tap('保存账目')
        ok(find(text='金额无效：请输入非负金额，最多两位小数') is not None,'native ledger rejects fractional cents without closing editor')
        tap('取消'); ready()
        money('2026-09-02','REFUND','5')
        ok(metric('EXPENSE','支出 ¥80.00') and metric('REFUND','退款 ¥5.00') and metric('NET_EXPENSE','净支出 ¥75.00'),'refund reduces net expense without rewriting gross expense')
        money('2026-09-03','PLANNED','100'); money('2026-09-03','INCOME','2.50')
        ok(metric('PLANNED','预计 ¥100.00') and metric('INCOME','收入 ¥2.50') and metric('NET_CASH','净现金 ¥-72.50'),'planned is separate and signed net cash is exact')
        shot('04-ledger.png')
        select_days([1,3]); ok(metric('EXPENSE','支出 ¥60.00') and metric('REFUND','退款 ¥0.00'),'nonconsecutive selected days exclude actual refund date')
        tap('选择日期'); touch('calendar-day-2026-09-02'); tap('取消')
        ok(metric('EXPENSE','支出 ¥60.00'),'cancel date selection keeps previous summary')
        select_days([4]); ok(find(text='所选日期没有实际账目，不代表已确认零支出') is not None,'missing day is not presented as confirmed zero expenditure')
        select_days([]); ok(metric('EXPENSE','支出 ¥0.00') and desc('selected-days').get('text')=='已选 0 天 · 仅汇总，不批量写入','empty date selection is zero not all-time total')
        select_days([1,2,3]); shot('05-selected-dates.png')
        restart(); tap('活动'); ready(); touch('activity-1'); ready(); tap('日历账本'); ready(); select_days([1,2,3])
        ok(metric('EXPENSE','支出 ¥80.00') and metric('NET_EXPENSE','净支出 ¥75.00') and metric('NET_CASH','净现金 ¥-72.50'),'native ledger exact totals survive stopped-process restart')
        stop()
        with sqlite3.connect(copy_db('ledger-after.db')) as db:
            expected=[('2026-09-01','EXPENSE',1500),('2026-09-02','EXPENSE',2000),('2026-09-02','REFUND',500),('2026-09-03','EXPENSE',4500),('2026-09-03','INCOME',250),('2026-09-03','PLANNED',10000)]
            ok(db.execute('SELECT day,kind,cents FROM ledger WHERE activity_id=1 ORDER BY day,kind').fetchall()==expected,'independent Android SQLite read matches all six exact typed dated entries')
            ok(db.execute('SELECT count(*),count(DISTINCT batch_id),count(DISTINCT id) FROM ledger').fetchone()==(6,6,6),'native saves have distinct entry and batch identities without selection-generated writes')
            ok(db.execute('SELECT count(*) FROM batches WHERE undone=0').fetchone()[0]==6,'cancel and invalid amount leave no batch journal residue')
            ok(db.execute('SELECT activity_id,day,status,recorded_at FROM checkins').fetchall()==marks,'money and date filtering never mutate the check-in history')
        start(); tap('活动'); ready(); touch('activity-1'); ready(); tap('打卡记录'); ready()
        tap('补记 / 修改'); clear_field('打卡日期'); type_text('not-a-date'); tap('保存记录')
        ok(find(text='日期格式应为 2026-09-21') is not None and find(text='保存记录') is not None,'native check-in editor rejects malformed date without closing')
        tap('取消'); ready()
        tap('补记 / 修改'); clear_field('打卡日期'); type_text('2026-09-20'); tap('保存记录'); ready()
        ok(desc('checkin-2026-09-20').get('text')=='2026-09-20 · 已完成','backdated done check-in appears with its exact date')
        shot('06-checkin-history.png')
        touch('edit-checkin-2026-09-20'); tap('标记未记录'); tap('保存记录'); ready()
        ok(absent('2026-09-20 · 已完成') and not any(n.get('content-desc')=='checkin-2026-09-20' for n in nodes()),'un-recording removes the visible history row')
        stop()
        with sqlite3.connect(copy_db('checkins-after.db')) as db:
            rows=db.execute('SELECT activity_id,day,status,recorded_at FROM checkins').fetchall()
            ok(rows==marks,'un-recorded backdate leaves the exact prior single mark in independent readback')
            ok(db.execute('SELECT count(*) FROM ledger').fetchone()[0]==6,'check-in editing never mutates the ledger')
        start(); tap('活动'); ready(); touch('activity-1'); ready(); tap('打卡记录'); ready(); tap('补记 / 修改'); clear_field('打卡日期'); type_text('2026-09-20'); tap('保存记录'); ready()
        ok(desc('checkin-2026-09-20').get('text')=='2026-09-20 · 已完成','backdated check-in survives cancel then re-entered identically')
        tap('返回活动'); ready(); tap('返回分类'); ready()
        export_backup(); tap('今天'); ready()
        add_todo('After backup'); shot('07-backup.png')
        import_backup('pocket-todo-backup.zip')
        tap('取消'); ready(); tap('今天'); ready()
        ok(find(text='After backup') is not None and absent('确认恢复'),'canceling SAF restore preview makes no database write')
        stop()
        with sqlite3.connect(copy_db('before-restore.db')) as db:
            rows=db.execute('SELECT title,done FROM todos ORDER BY position').fetchall()
            ok(rows==[('Fresh milk',1),('Walk outside',0),('After backup',0)],'cancelled restore leaves exact new todo and old state independent')
            ok(db.execute('SELECT count(*) FROM ledger').fetchone()[0]==6,'cancelled restore retains exact ledger rows')
        start(); import_backup('pocket-todo-backup.zip'); shot('08-restore-preview.png')
        tap('确认恢复')
        ok(find(text='请先勾选：我明白会替换本机数据') is not None and find(text='确认恢复') is not None,'unchecked consent cannot restore even with visible confirmation control')
        tap('取消'); ready(); import_backup('pocket-todo-backup.zip')
        touch('restore-consent'); tap('确认恢复'); gone('确认恢复'); ready()
        tap('今天'); ready()
        ok(absent('After backup') and named_todo('Fresh milk') is not None,'explicit SAF consent replaces data with previewed backup')
        restart()
        ok(absent('After backup') and named_todo('Walk outside') is not None,'SAF restored data survives a separate stopped-process restart')
        stop()
        with sqlite3.connect(copy_db('after-saf-restore.db')) as db:
            rows=db.execute('SELECT title,done FROM todos ORDER BY position').fetchall()
            ok(rows==[('Fresh milk',1),('Walk outside',0)],'independent SQLite read matches exact SAF restored state')
            ok(db.execute('SELECT count(*) FROM ledger').fetchone()[0]==6,'SAF restore retains exact ledger after independent readback')
            marks2=db.execute('SELECT activity_id,day,status,recorded_at FROM checkins ORDER BY day').fetchall()
            ok(len(marks2)==2 and marks2[0][:3]==(1,'2026-09-20','DONE') and marks2[1]==marks[0] and all(row[3] for row in marks2),'SAF restore retains exact check-in history including the re-entered backdate')
        start(); tap('活动'); ready(); touch('activity-1'); ready(); tap('笔记'); ready()
        ok(find(text='写点什么，或加一张图。') is not None,'empty note starts visibly empty without fabricated content')
        tap('加入文字'); tap('保存'); ok(find(text='内容不能为空') is not None,'blank note save rejected visibly')
        tap('取消'); ready()
        tap('加入文字'); touch('文字内容'); type_text('Watered 20 min today'); tap('保存'); ready()
        ok(find(text='Watered 20 min today') is not None,'saved note text appears on activity')
        shot('09-note.png')
        restart(); tap('活动'); ready(); touch('activity-1'); ready()
        ok(find(text='Watered 20 min today') is not None,'note survives process restart')
        tap('笔记'); ready(); tap('加入图片')
        tap('加入合成图'); ready()
        ok(any(n.get('content-desc','').startswith('note-image-') for n in nodes()),'attached image is registered with note')
        stop()
        with sqlite3.connect(copy_db('note-after.db')) as db:
            notes=db.execute('SELECT id,activity_id,title FROM notes').fetchall()
            ok(notes and notes[0][1]==1 and notes[0][2]=='Daily reward','note inherits its activity title and stays bound to that activity')
            blocks=db.execute('SELECT kind,text,asset_id,private FROM blocks ORDER BY position').fetchall()
            ok(len(blocks)==2 and blocks[0][0]=='TEXT' and blocks[0][1]=='Watered 20 min today' and blocks[1][0]=='IMAGE','note keeps ordered text then image blocks')
            ok(blocks[1][3]==0,'image block is not private by default')
            media=db.execute('SELECT id,mime,bytes FROM media').fetchall()
            ok(len(media)==1 and media[0][1].startswith('image/') and media[0][2]>0,'image bytes registered under immutable content id')
            ok(blocks[1][2]==media[0][0],'image block references exact registered media id')
            ok(db.execute('SELECT count(*) FROM ledger').fetchone()[0]==6,'notes never mutate the ledger')
        result={'status':'PASS','scope':'NATIVE_TODO_CATEGORY_ACTIVITY_PATH_CHECKIN_LEDGER_NOTE_RESTORE_SLICE','ledger_calendar':'NATIVE_MULTI_DATE_LEDGER_PASS','saf_restore':'NATIVE_SAF_RESTORE_PREVIEW_CONFIRM_PASS','checkin_history':'NATIVE_CHECKIN_HISTORY_BACKDATE_PASS','note_editor':'NATIVE_TEXT_IMAGE_NOTE_PASS','api':API,'count':len(checks),'checks':checks,'screenshots':shots,'infra_retries':infra_retries,'restore_undo':'NOT_IMPLEMENTED','restore_preview_lifecycle':'NOT_TESTED','checkin_schedules':'NOT_IMPLEMENTED','real_photo_selection':'NOT_IMPLEMENTED','photos':'NOT_TESTED','sharing':'NOT_TESTED','release_ready':False}
    except Exception as exc:
        result={'status':'FAIL','api':API,'count':len(checks),'checks':checks,'error':repr(exc),'screenshots':shots,'infra_retries':infra_retries,'release_ready':False}
        try: shot('failure.png')
        except Exception: pass
        (out/'native-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print('NATIVE_UI_FAILED '+json.dumps(result,ensure_ascii=False),flush=True)
        raise
    (out/'native-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('NATIVE_UI_RESULT '+json.dumps(result,ensure_ascii=False),flush=True)

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
        verify_native_ui(adb)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=10)
        log.close()
        print('EMULATOR_PROCESS_EXITED', proc.returncode, flush=True)

if __name__ == '__main__': main()
