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
from verify_process_control import stop_verified, isolated_directory_runner, capture_runtime_identity

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

def summary_viewport(frame, package):
    matches = [n for n in frame if n.get('content-desc') == 'activity-details-scroll']
    assert len(matches) == 1, 'missing or duplicate summary viewport'
    node = matches[0]
    assert node.get('package') == package, 'summary viewport belongs to another package'
    assert node.get('class') == 'android.widget.ScrollView' and node.get('enabled') == 'true', 'invalid summary viewport'
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    assert match, 'summary viewport has malformed bounds'
    left, top, right, bottom = map(int, match.groups())
    assert right-left >= 3 and bottom-top >= 3, 'summary viewport too small'
    return left, top, right, bottom

def summary_gesture(bounds):
    left, top, right, bottom = bounds
    x = (left+right)//2
    # Half-viewport travel leaves overlap for short rows; never use screen coordinates.
    start = top + (bottom-top)*3//4
    end = top + (bottom-top)//4
    assert left < x < right and top < end < start < bottom, 'summary gesture leaves viewport'
    return x, start, x, end

def reveal_summary(read_nodes, swipe, package, description, expected, max_swipes=8, records=None):
    """Bounded navigation, not a retry of wrong content; record every observed frame."""
    assert type(max_swipes) is int and 0 <= max_swipes <= 8, 'invalid summary navigation bound'
    records = [] if records is None else records
    previous = None
    for attempt in range(max_swipes + 1):
        frame = list(read_nodes())
        record = dict(attempt=attempt, description=description, status='OBSERVED')
        records.append(record)
        viewport = summary_viewport(frame, package)
        record['viewport'] = list(viewport)
        fields = ('package','content-desc','text','bounds','class')
        signature = hashlib.sha256(json.dumps([[n.get(k,'') for k in fields] for n in frame],
                                              ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        record['frame_sha256'] = signature
        record['changed_from_previous'] = None if previous is None else signature != previous
        previous = signature
        matches = [n for n in frame if n.get('content-desc') == description]
        record['matches'] = len(matches)
        assert len(matches) <= 1, 'duplicate summary identity'
        if matches:
            node = matches[0]
            assert node.get('package') == package, 'summary belongs to another package'
            bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
            assert bounds, 'summary has malformed bounds'
            x1,y1,x2,y2 = map(int,bounds.groups())
            assert x2 > x1 and y2 > y1, 'summary has empty visible bounds'
            left,top,right,bottom = viewport
            assert left <= x1 < x2 <= right and top <= y1 < y2 <= bottom, 'summary outside observed viewport'
            assert node.get('text') == expected, 'summary text differs: '+repr(node.get('text'))
            record['status'] = 'EXACT_SUMMARY_FOUND'
            record['summary_bounds'] = [x1,y1,x2,y2]
            return node
        if attempt < max_swipes:
            coordinates = summary_gesture(viewport)
            record['gesture'] = list(coordinates)
            record['duration_ms'] = 350
            record['status'] = 'SWIPE_REQUESTED'
            swipe(*coordinates)
        else:
            record['status'] = 'ABSENT_AT_BOUND'
    raise AssertionError('summary identity absent after bounded scroll: '+description)

def summary_geometry_selftest():
    """Original API34 geometry replay MODEL, not reconstructed Android touch physics."""
    import ast, copy, inspect
    package='synthetic.app'; description='note-activity-1'; expected='Watered 20 min today'
    viewport={'package':package,'content-desc':'activity-details-scroll','class':'android.widget.ScrollView',
              'enabled':'true','scrollable':'true','bounds':'[18,293][302,578]'}
    node={'package':package,'content-desc':description,'text':expected,'bounds':'[18,400][302,424]'}
    def rejected(fn, needle):
        try: fn()
        except AssertionError as exc:
            assert needle in str(exc), (needle,str(exc))
            return
        raise AssertionError('negative survived: '+needle)
    def overlap_model(reveal, legacy=False):
        # Measured viewport h=285, old requested travel=320. This 24px row lies
        # in the 35px uncovered interval. Actual original intermediate frames
        # were not retained, so this proves the gap mechanism, not its occurrence.
        offset=0; gestures=[]; receipts=[]
        def read():
            top=293+290-offset; bottom=top+24
            result=[dict(viewport)]
            if max(top,293)<min(bottom,578):
                result.append(dict(node,bounds=f'[18,{max(top,293)}][302,{min(bottom,578)}]'))
            return result
        def swipe(*args):
            nonlocal offset
            if legacy:
                assert args == ()
                args=(160,500,160,180)
            gestures.append(args)
            offset += args[1]-args[3]
        if legacy:
            rejected(lambda:reveal(read,swipe,package,description,expected),
                     'summary identity absent after bounded scroll')
            assert len(gestures)==8
        else:
            result=reveal(read,swipe,package,description,expected,records=receipts)
            assert result['text']==expected and len(gestures)==1
            assert gestures == [(160,506,160,364)]
            assert len(receipts)==2 and receipts[-1]['status']=='EXACT_SUMMARY_FOUND'
            assert receipts[-1]['changed_from_previous'] is True
        return receipts
    # A matching immediately-visible positive witness is used for every mutant.
    def visible(reveal):
        result=reveal(lambda:[viewport,node],lambda *a:(_ for _ in ()).throw(AssertionError('unexpected swipe')),
                      package,description,expected)
        assert result==node
    def case(reveal, key):
        if key=='gap': overlap_model(reveal); return
        if key=='text':
            rejected(lambda:reveal(lambda:[viewport,dict(node,text='wrong')],lambda *a:None,package,description,expected),'summary text differs')
        elif key=='identity':
            rejected(lambda:reveal(lambda:[viewport,dict(node,**{'content-desc':'note-activity-2'})],
                                  lambda *a:None,package,description,expected,0),'summary identity absent')
        elif key=='bound':
            calls=[]; receipts=[]
            rejected(lambda:reveal(lambda:[viewport],lambda *a:calls.append(a),package,description,expected,records=receipts),
                     'summary identity absent')
            assert len(calls)==8 and len(receipts)==9,'swipe or observation count differs'
        elif key=='records':
            receipts=overlap_model(reveal)
            assert receipts[0]['gesture']==[160,506,160,364]
    visible(reveal_summary)
    for key in ('gap','text','identity','bound','records'): case(reveal_summary,key)
    negative=0
    for bad, needle in [
        ([], 'missing or duplicate'),([viewport,viewport],'missing or duplicate'),
        ([dict(viewport,package='foreign')],'another package'),
        ([dict(viewport,enabled='false')],'invalid summary viewport'),
        ([dict(viewport,bounds='broken')],'malformed bounds'),
        ([dict(viewport,bounds='[0,0][0,0]')],'too small'),
        ([dict(viewport,**{'class':'android.widget.TextView'})],'invalid summary viewport'),
        ([viewport,dict(node,bounds='[18,20][302,44]')],'outside observed viewport'),
    ]:
        rejected(lambda bad=bad:reveal_summary(lambda:bad,lambda *a:None,package,description,expected),needle)
        negative+=1
    for bound in (-1,9,True,1.5):
        rejected(lambda:reveal_summary(lambda:[viewport],lambda *a:None,package,description,expected,bound),'invalid summary navigation bound')
        negative+=1
    for rect in ((18,281,302,578),(18,293,302,578),(301,700,1001,1200),(10,20,13,24)):
        coords=summary_gesture(rect); left,top,right,bottom=rect
        assert left<coords[0]<right and top<coords[3]<coords[1]<bottom
        assert coords[1]-coords[3] <= (bottom-top+1)//2
    # No progress remains a failure at the ORIGINAL bound, with nine receipts.
    receipts=[];calls=[]
    rejected(lambda:reveal_summary(lambda:[viewport],lambda *a:calls.append(a),package,description,expected,records=receipts),
             'summary identity absent')
    assert len(calls)==8 and len(receipts)==9 and receipts[-1]['status']=='ABSENT_AT_BOUND'
    assert all(r['changed_from_previous'] is False for r in receipts[1:])
    source=inspect.getsource(reveal_summary)
    mutants=[
        ("coordinates = summary_gesture(viewport)","coordinates = (160,500,160,180)",'gap'),
        ("assert node.get('text') == expected","assert True",'text'),
        ("range(max_swipes + 1)","range(max_swipes)",'bound'),
        ("record['gesture'] = list(coordinates)","record['gesture'] = []",'records'),
    ]
    killed=0
    for old,new,key in mutants:
        assert source.count(old)==1
        scope=dict(globals());exec(compile(source.replace(old,new,1),'<navigation-mutant>','exec'),scope)
        mutant=scope['reveal_summary']
        visible(mutant)
        try:case(mutant,key)
        except AssertionError:killed+=1
        else:raise AssertionError('navigation mutant survived '+key)
    assert killed==4
    print('SUMMARY_GEOMETRY_SELFTEST positive_viewports=4 negative_geometry_bounds='+str(negative)+
          ' witnessed_mutants='+str(killed)+' PASS; geometry model, NOT_ANDROID',flush=True)

def summary_wiring_selftest():
    import ast, copy
    tree=ast.parse(Path(__file__).read_text())
    def check(tree):
        native=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_native_ui')
        calls=[n for n in ast.walk(native) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='reveal_summary']
        assert len(calls)==1
        assert ast.unparse(calls[0])=="reveal_summary(nodes, swipe_summary, PKG, 'note-activity-1', 'Watered 20 min today', records=summary_navigation_traces)"
        swipe=next(n for n in native.body if isinstance(n,ast.FunctionDef) and n.name=='swipe_summary')
        assert ast.unparse(swipe)=="def swipe_summary(x1, y1, x2, y2):\n    shell('input', 'swipe', str(x1), str(y1), str(x2), str(y2), '350')\n    time.sleep(0.4)"
        shell=next(n for n in native.body if isinstance(n,ast.FunctionDef) and n.name=='shell')
        assert any(isinstance(n,ast.keyword) and n.arg=='timeout' and ast.literal_eval(n.value)==40 for n in ast.walk(shell))
        writes=[n for n in ast.walk(native) if isinstance(n,ast.Assign) and
                any(ast.unparse(t)=="result['summary_navigation_traces']" for t in n.targets)]
        assert len(writes)==2 and all(ast.unparse(n.value)=='summary_navigation_traces' for n in writes)
        parser=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='parser_selftest')
        names={n.func.id for n in ast.walk(parser) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        assert {'summary_navigation_selftest','summary_geometry_selftest','summary_wiring_selftest'} <= names
    check(tree)
    for omission in ('records','caller','entry'):
        changed=copy.deepcopy(tree)
        if omission=='records':
            native=next(n for n in changed.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_native_ui')
            for n in ast.walk(native):
                if isinstance(n,ast.Assign):
                    for t in n.targets:
                        if ast.unparse(t)=="result['summary_navigation_traces']":t.slice=ast.Constant(value='omitted')
        else:
            for n in ast.walk(changed):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==('reveal_summary' if omission=='caller' else 'summary_geometry_selftest'):
                    n.func.id='omitted'
        try:check(changed)
        except AssertionError:pass
        else:raise AssertionError('summary wiring omission survived '+omission)
    print('SUMMARY_WIRING_SELFTEST positive=1 omissions=3 PASS',flush=True)


def summary_navigation_selftest():
    package = 'synthetic.app'
    description = 'note-activity-1'
    expected = 'Watered 20 min today'
    node = {'package':package,'content-desc':description,'text':expected,'bounds':'[16,120][300,150]'}
    def exercise(frames, passes, swipes, bound=8):
        state = {'frame':0,'reads':0}
        def read():
            state['reads'] += 1
            view={'package':package,'content-desc':'activity-details-scroll','class':'android.widget.ScrollView',
                  'enabled':'true','bounds':'[16,100][300,400]'}
            return [view]+frames[min(state['frame'],len(frames)-1)]
        def swipe(*coordinates):
            state['frame'] += 1
        accepted = False
        try:
            result = reveal_summary(read,swipe,package,description,expected,bound)
            accepted = True
        except AssertionError:
            pass
        assert accepted == passes, 'summary navigation control accepted wrong outcome'
        if accepted: assert result == node, 'summary navigation returned wrong node'
        assert state['frame'] == swipes, 'summary navigation retried content or exceeded scroll bound'
        assert state['reads'] == swipes+1, 'summary navigation observation count differs'
    exercise([[node]],True,0)
    exercise([[],[node]],True,1)
    exercise([[]]*8+[[node]],True,8)
    exercise([[]],False,8)
    exercise([[dict(node,text='wrong')],[node]],False,0)
    exercise([[dict(node,package='foreign.app')],[node]],False,0)
    exercise([[dict(node,bounds='[0,0][0,0]')]],False,0)
    exercise([[dict(node,bounds='broken')]],False,0)
    exercise([[node,node]],False,0)
    exercise([[dict(node,**{'content-desc':'note-activity-2'})]],False,8)
    print('SUMMARY_NAVIGATION_SELFTEST positive=3 negative=7 PASS; host navigation only',flush=True)

def database_directory(adb, serial, package, *, runner=subprocess.run):
    """One isolated text read. Nonzero exits retain both streams and never retry."""
    command = [str(adb), '-s', serial, 'shell', '-n', '-T',
               'run-as', package, 'ls', 'databases']
    result = runner(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, timeout=40, check=False)
    result.check_returncode()
    return result.stdout

def database_directory_selftest():
    command = ['adb', '-s', 'test-serial', 'shell', '-n', '-T',
               'run-as', 'test.package', 'ls', 'databases']
    cases = [(0, 'pocket-v12.db\npocket-v12.db-wal\n', ''),
             (0, '', ''), (1, '', 'permission denied\n'),
             (255, 'pocket-v12.db\n', 'transport sentinel\n'),
             (-9, 'partial', 'signal sentinel')]
    for code, output, error in cases:
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            assert args == command, 'database listing identity or shell isolation differs'
            assert kwargs == dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, timeout=40, check=False), 'database listing streams or budget differ'
            return subprocess.CompletedProcess(args, code, output, error)
        failure = None
        try:
            actual = database_directory('adb', 'test-serial', 'test.package', runner=runner)
        except subprocess.CalledProcessError as exc:
            failure = exc
        assert len(calls) == 1, 'database directory command repeated'
        if code == 0:
            assert failure is None and actual == output, 'directory output was rewritten'
        else:
            assert failure is not None, 'nonzero listing was accepted as complete'
            assert (failure.returncode, failure.cmd, failure.stdout, failure.stderr) == (code, command, output, error), 'original directory failure evidence lost'
    timeout = subprocess.TimeoutExpired(command, 40, output=b'partial', stderr=b'timeout sentinel')
    calls = []
    def timed_out(args, **kwargs):
        calls.append(args)
        raise timeout
    failure = None
    try:
        database_directory('adb', 'test-serial', 'test.package', runner=timed_out)
    except subprocess.TimeoutExpired as exc:
        failure = exc
    assert failure is timeout and len(calls) == 1, 'directory timeout retried or replaced'
    print('DATABASE_DIRECTORY_SELFTEST positive=2 negative=4 PASS; host command contract, not Android root cause', flush=True)

def select_restore_file(read_nodes, tap_node, label, records, clock=None, pause=None):
    """Select once from a verified list view; never replay a failed file tap."""
    clock = time.monotonic if clock is None else clock
    pause = time.sleep if pause is None else pause
    assert isinstance(label, str) and label and "/" not in label
    packages = {"com.android.documentsui", "com.google.android.documentsui"}
    deadline = clock() + 20
    switched = False
    first_layout = None
    stable = 0
    reconfirmed = False
    def valid(n, package=None):
        assert n.get("package") in packages, "foreign picker control"
        if package is not None:
            assert n.get("package") == package, "mixed picker packages"
        assert n.get("enabled") == "true", "disabled picker control"
        match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
        assert match, "invalid picker bounds"
        left, top, right, bottom = map(int, match.groups())
        assert right > left and bottom > top, "empty picker bounds"
    while True:
        if clock() >= deadline:
            raise TimeoutError("restore picker selection exceeded 20 seconds")
        frame = read_nodes()
        if clock() >= deadline:
            raise TimeoutError("restore picker observation completed after deadline")
        controls = [n for n in frame if n.get("content-desc") in ("List view", "Grid view")]
        matches = [n for n in frame if n.get("text") == label]
        # API26 repeats the name in android:id/summary. Keep that evidence,
        # but only the same picker's known summary is not a file title.
        files = [n for n in matches if not (
            n.get("resource-id") == "android:id/summary"
            and len(controls) == 1 and controls[0].get("package") in packages
            and n.get("package") == controls[0].get("package"))]
        records.append({"stage": "OBSERVED",
                        "view_controls": [dict(n.attrib) if hasattr(n, "attrib") else dict(n)
                                          for n in controls],
                        "filename_matches": [dict(n.attrib) if hasattr(n, "attrib") else dict(n)
                                             for n in matches]})
        assert len(controls) <= 1, "ambiguous picker view controls"
        assert len(files) <= 1, "ambiguous restore filename"
        # Only this version's explicit layout button can be requested again.
        key = None
        if len(controls) == len(files) == 1:
            c, f = controls[0], files[0]
            pkg = 'com.google.android.documentsui'
            if (c.get('package') == f.get('package') == pkg and
                    c.get('resource-id') == pkg + ':id/sub_menu_list' and
                    c.get('content-desc') == 'List view' and c.get('class') == 'android.widget.Button' and
                    c.get('clickable') == 'true' and f.get('resource-id') == 'android:id/title'):
                valid(c); valid(f, pkg)
                key = (c.get('bounds'), f.get('bounds'), f.get('text'))
        stable = stable + 1 if key is not None and key == first_layout else 0
        if controls:
            control = controls[0]
            valid(control)
            if control.get("content-desc") == "List view":
                if not switched:
                    switched = True
                    first_layout = key
                    tap_node(control)
                    records.append({"stage": "LIST_VIEW_REQUESTED"})
                elif stable >= 2 and not reconfirmed:
                    assert key is not None and clock() < deadline, 'layout confirmation expired'
                    reconfirmed = True
                    records.append({'stage':'SAME_GRID_RECONFIRMED','bounds':key[:2]})
                    tap_node(control)
                # Never reuse grid coordinates even if the filename was visible.
            elif files:
                file = files[0]
                valid(file, control.get("package"))
                assert file.get("resource-id") == "android:id/title", "unexpected filename resource"
                tap_node(file)
                records.append({"stage": "FILE_TAPPED", "label": label})
                return file
        pause(.25)

def restore_picker_selftest():
    """Host controls; not device acceptance."""
    import copy
    import inspect
    import unittest
    import ast
    import textwrap
    import xml.etree.ElementTree as ET

    PKG = "com.google.android.documentsui"


    def node(desc="", text="", package=PKG, enabled="true", bounds="[20,200][250,250]", rid=""):
        return {"content-desc": desc, "text": text, "package": package,
                "enabled": enabled, "bounds": bounds, "resource-id": rid}


    GRID = node("List view")
    LIST = node("Grid view")
    FILE = node(text="pocket-todo-backup.zip", rid="android:id/title")


    class Model:
        def __init__(self, frames, ticks=None):
            self.frames = copy.deepcopy(frames)
            self.index = 0
            self.now = 0
            self.taps = []
            self.records = []
            self.ticks = iter(ticks) if ticks is not None else None

        def read(self):
            value = self.frames[min(self.index, len(self.frames)-1)]
            self.index += 1
            if isinstance(value, Exception):
                raise value
            return value

        def tap(self, value):
            self.taps.append(value["content-desc"] or value["text"])

        def clock(self):
            return next(self.ticks) if self.ticks is not None else self.now

        def pause(self, seconds):
            assert seconds == .25
            self.now += seconds

        def run(self, function):
            return function(self.read, self.tap, "pocket-todo-backup.zip",
                            self.records, self.clock, self.pause)


    def exercise(function):
        positives = [
            ([[LIST, FILE]], ["pocket-todo-backup.zip"]),
            ([[GRID, FILE], [LIST, FILE]], ["List view", "pocket-todo-backup.zip"]),
            ([[], [GRID, FILE], [GRID, FILE], [LIST], [LIST, FILE]],
             ["List view", "pocket-todo-backup.zip"]),
            ([[LIST], [LIST, FILE]], ["pocket-todo-backup.zip"]),
            ([[LIST, node("Preview the file pocket-todo-backup.zip"), FILE]],
             ["pocket-todo-backup.zip"]),
        ]
        for frames, taps in positives:
            m = Model(frames)
            result = m.run(function)
            assert result == FILE and m.taps == taps, "selection order"
            assert m.records[-1]["stage"] == "FILE_TAPPED", "selection evidence"
        # Both supported DocumentsUI packages must pass using the actual helper.
        m = Model([[dict(LIST, package="com.android.documentsui"),
                    dict(FILE, package="com.android.documentsui")]])
        assert m.run(function)["package"] == "com.android.documentsui"
        assert m.taps == ["pocket-todo-backup.zip"]
        negatives = [
            ([[LIST, FILE, FILE]], AssertionError, [], "duplicate filename"),
            ([[GRID, GRID, FILE]], AssertionError, [], "ambiguous view"),
            ([[GRID, LIST, FILE]], AssertionError, [], "ambiguous view"),
            ([[dict(LIST, package="foreign.app"), FILE]], AssertionError, [], "foreign view"),
            ([[dict(LIST, package="foreign.app"), dict(FILE, package="foreign.app")]],
             AssertionError, [], "coherent foreign picker"),
            ([[LIST, dict(FILE, package="foreign.app")]], AssertionError, [], "foreign file"),
            ([[LIST, dict(FILE, enabled="false")]], AssertionError, [], "disabled file"),
            ([[dict(GRID, enabled="false"), FILE]], AssertionError, [], "disabled view"),
            ([[LIST, dict(FILE, bounds="[0,0][0,0]")]], AssertionError, [], "empty bounds"),
            ([[LIST, dict(FILE, bounds="malformed")]], AssertionError, [], "bad bounds"),
            ([[LIST, dict(FILE, **{"resource-id": "other:id/title"})]], AssertionError, [], "wrong id"),
            ([[GRID, FILE]], TimeoutError, ["List view"], "unchanged grid"),
            ([[LIST]], TimeoutError, [], "missing file"),
            ([[FILE]], TimeoutError, [], "unverified view"),
            ([[]], TimeoutError, [], "missing picker"),
            ([[LIST, dict(FILE, text="pocket-todo-backup (1).zip")]],
             TimeoutError, [], "different file"),
        ]
        for frames, error, taps, name in negatives:
            m = Model(frames)
            try:
                m.run(function)
            except error:
                pass
            else:
                raise AssertionError("negative survived: " + name)
            assert m.taps == taps, "unexpected tap: " + name
            assert len(m.records) <= 82, "unbounded observations"
        for ticks in ([0, 20], [0, 0, 20]):
            m = Model([[LIST, FILE]], ticks)
            try:
                m.run(function)
            except TimeoutError:
                pass
            else:
                raise AssertionError("late observation accepted")
            assert not m.taps, "tap after deadline"
        sentinel = OSError("original read failure")
        m = Model([sentinel])
        # deepcopy on the model replaces exception identity; capture actual fixture.
        sentinel = m.frames[0]
        try:
            m.run(function)
        except OSError as exc:
            assert exc is sentinel, "original read error replaced"
        else:
            raise AssertionError("read error swallowed")
        assert m.index == 1 and not m.taps
        m = Model([[LIST, FILE]])
        sentinel = RuntimeError("original tap failure")
        def broken_tap(value):
            m.taps.append(value["text"])
            raise sentinel
        try:
            function(m.read, broken_tap, "pocket-todo-backup.zip",
                     m.records, m.clock, m.pause)
        except RuntimeError as exc:
            assert exc is sentinel
        else:
            raise AssertionError("tap error swallowed")
        assert m.taps == ["pocket-todo-backup.zip"]
        # Model the API34 trace: a persistent grid is not proof the first tap was lost.
        c=dict(GRID, **{'resource-id':PKG+':id/sub_menu_list','class':'android.widget.Button','clickable':'true','bounds':'[248,174][296,222]'})
        f=dict(FILE,bounds='[74,372][144,391]'); g=[c,f]
        for frames, expected, succeeds in (([g,g,g,[LIST,FILE]], ['List view']*2+[FILE['text']], True),
                ([g,[LIST,FILE]], ['List view', FILE['text']], True),
                ([g], ['List view']*2, False),
                ([g,[dict(c,bounds='[24,17][29,22]'),f]], ['List view'], False),
                ([[dict(c,clickable='false'),f]], ['List view'], False),
                ([g,[c]], ['List view'], False)):
            m=Model(frames)
            try:result=m.run(function)
            except TimeoutError:assert not succeeds
            else:assert succeeds and result==FILE
            assert m.taps==expected
        return 8, 24


    print('RESTORE_PICKER_HOST', exercise(select_restore_file), 'PASS; NOT_ANDROID')
    original = inspect.getsource(select_restore_file)
    mutants = [('if not switched:', 'if True:', 'repeated toggle'), ('assert len(files) <= 1, "ambiguous restore filename"', 'pass', 'duplicate filename'), ('assert n.get("package") in packages, "foreign picker control"', 'pass', 'foreign package'), ('assert n.get("enabled") == "true", "disabled picker control"', 'pass', 'disabled control'), ('assert right > left and bottom > top, "empty picker bounds"', 'pass', 'empty bounds')]
    for old, new, name in mutants:
        assert original.count(old) == 1
        namespace = dict(globals(), select_restore_file=select_restore_file)
        exec(compile(original.replace(old, new, 1), '<picker-mutant>', 'exec'), namespace)
        function = namespace['select_restore_file']
        witness = Model([[LIST, FILE]])
        assert witness.run(function) == FILE
        try:
            exercise(function)
        except AssertionError:
            print('WITNESSED_MUTANT_REJECTED', name)
        else:
            raise AssertionError('mutant survived: ' + name)
    old_caller = "def import_backup(label):\n        tap('活动'); ready()\n        if absent('恢复完整备份'): tap('备份 / 恢复'); ready()\n        tap('恢复完整备份')\n        file=find(text=label); tap_node(file)\n        dialog=desc('restore-consent')\n        assert dialog.get('enabled')=='true' and dialog.get('checked')=='false','consent checkbox starts visible and unchecked'\n        counts=desc('restore-counts').get('text')\n        assert counts is not None and '普通待办：本机 3 → 备份 2' in counts,'restore preview shows exact current and incoming todo counts; actual='+repr(counts)\n        ok(True,'SAF file selection shows visible restore preview and replacement counts')\n        return dialog\n"
    new_caller = old_caller.replace('file=find(text=label); tap_node(file)', 'select_restore_file(nodes,tap_node,label,restore_picker_traces)')
    def caller_exercise(source, starts_grid):
        state = {'grid': starts_grid, 'opened': False}
        events = []

        def nodes():
            return [ET.Element('node', GRID if state['grid'] else LIST), ET.Element('node', FILE)]

        def tap_node(value):
            if value.get('content-desc') == 'List view':
                state['grid'] = False
                events.append('LIST')
            else:
                assert value.get('text') == FILE['text']
                events.append('FILE')
                state['opened'] = not state['grid']

        def desc(value):
            assert state['opened'], 'restore consent missing: still in grid picker'
            events.append(value)
            return {'enabled': 'true', 'checked': 'false'} if value == 'restore-consent' else {'text': '普通待办：本机 3 → 备份 2'}

        def ok(condition, label):
            assert condition
            events.append('EXACT_COUNTS')
        namespace = dict(tap=lambda name: None, ready=lambda: None, absent=lambda name: False, find=lambda **attrs: ET.Element('node', FILE), tap_node=tap_node, desc=desc, ok=ok, nodes=nodes, restore_picker_traces=[], select_restore_file=select_restore_file)
        exec(compile(source, '<actual-import-backup>', 'exec'), namespace)
        namespace['import_backup'](FILE['text'])
        assert events == (['LIST'] if starts_grid else []) + ['FILE', 'restore-consent', 'restore-counts', 'EXACT_COUNTS']
    caller_exercise(old_caller, False)
    try:
        caller_exercise(old_caller, True)
    except AssertionError as exc:
        assert str(exc) == 'restore consent missing: still in grid picker'
        print('ORIGINAL_CALLER_GRID_MODEL_RED: NOT_DEVICE_REPRODUCTION')
    else:
        raise AssertionError('old caller accepted grid fixture')
    caller_exercise(new_caller, False)
    caller_exercise(new_caller, True)
    a, b = (ast.parse(old_caller).body[0], ast.parse(new_caller).body[0])
    assert [ast.dump(n) for n in a.body[6:]] == [ast.dump(n) for n in b.body[5:]]
    print('ACTUAL_CALLER_SLICE list/grid GREEN; original consent/count assertions retained')

def restore_picker_wiring_selftest(source=None):
    """Guard actual call and both receipts; AST proof is not device proof."""
    import ast
    import copy
    source = Path(__file__).read_text() if source is None else source
    tree = ast.parse(source)
    def check(tree):
        native = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == "_verify_native_ui")
        caller = next(n for n in native.body if isinstance(n, ast.FunctionDef)
                      and n.name == "import_backup")
        calls = [n for n in ast.walk(caller) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "select_restore_file"]
        assert len(calls) == 1, "restore picker caller omitted or duplicated"
        assert ast.unparse(calls[0]) == "select_restore_file(nodes, tap_node, label, restore_picker_traces)", "restore picker callback binding differs"
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id in ("find", "tap_node") for n in ast.walk(caller)), "old filename tap remains"
        initialization = [n for n in native.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "restore_picker_traces"
                                  for t in n.targets)]
        assert len(initialization) == 1 and ast.unparse(initialization[0].value) == "[]", "trace lifetime differs"
        trial = next(n for n in native.body if isinstance(n, ast.Try))
        def receipt(body):
            writes = [n for n in body if isinstance(n, ast.Assign)
                      and any(ast.unparse(t) == "result['restore_picker_traces']"
                              for t in n.targets)]
            assert len(writes) == 1 and ast.unparse(writes[0].value) == "restore_picker_traces", "picker receipt missing or rewritten"
        receipt(trial.body)
        assert len(trial.handlers) == 1
        failure = trial.handlers[0].body
        receipt(failure)
        assignment = next(i for i, n in enumerate(failure) if isinstance(n, ast.Assign)
                          and any(ast.unparse(t) == "result['restore_picker_traces']" for t in n.targets))
        write = next(i for i, n in enumerate(failure) if isinstance(n, ast.Expr)
                     and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute)
                     and n.value.func.attr == "write_text")
        assert assignment < write, "failure evidence persisted too late"
        assert isinstance(failure[-1], ast.Raise) and failure[-1].exc is None, "original failure swallowed or replaced"
        parser = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                      and n.name == "parser_selftest")
        for name in ("restore_picker_selftest", "restore_picker_wiring_selftest"):
            assert sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id == name for n in ast.walk(parser)) == 1, "permanent picker test missing"
    check(tree)
    for kind in ("caller", "success", "failure", "binding", "propagation", "entry"):
        mutant = copy.deepcopy(tree)
        native = next(n for n in mutant.body if isinstance(n, ast.FunctionDef)
                      and n.name == "_verify_native_ui")
        trial = next(n for n in native.body if isinstance(n, ast.Try))
        if kind in ("success", "failure"):
            body = trial.body if kind == "success" else trial.handlers[0].body
            body[:] = [n for n in body if not (isinstance(n, ast.Assign) and
                       any(ast.unparse(t) == "result['restore_picker_traces']" for t in n.targets))]
        elif kind == "propagation":
            trial.handlers[0].body[-1] = ast.Pass()
        else:
            for n in ast.walk(mutant):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                    if kind == "caller" and n.func.id == "select_restore_file":
                        n.func.id = "omitted"
                    elif kind == "binding" and n.func.id == "select_restore_file":
                        n.args[-1] = ast.List(elts=[], ctx=ast.Load())
                    elif kind == "entry" and n.func.id == "restore_picker_selftest":
                        n.func.id = "omitted"
        try:
            check(mutant)
        except AssertionError:
            pass
        else:
            raise AssertionError("picker wiring omission survived: " + kind)
    print("RESTORE_PICKER_WIRING positive=1 negative=6 PASS; AST_ONLY", flush=True)


def restore_picker_summary_selftest():
    """API26 recorded title/summary shape; host replay, not a device rerun."""
    import inspect
    package = "com.android.documentsui"
    label = "pocket-todo-backup.zip"
    def node(rid, bounds, desc="", text=label):
        return ET.Element("node", {"resource-id": rid, "bounds": bounds,
            "content-desc": desc, "text": text, "package": package, "enabled": "true"})
    grid = node(package+":id/menu_list", "[232,28][280,76]", "List view", "")
    view = node(package+":id/menu_grid", "[232,28][280,76]", "Grid view", "")
    title = node("android:id/title", "[76,156][240,178]")
    summary = node("android:id/summary", "[272,178][304,195]")
    def exercise(function):
        positive = 0
        negative = 0
        for pkg in ("com.android.documentsui", "com.google.android.documentsui"):
            for n in (grid, view, title, summary): n.set("package", pkg)
            for transition in (False, True):
                frames = [[grid, title, summary], [view, summary, title]] if transition else [[view, summary, title]]
                position = [0]; taps = []; records = []
                def read():
                    frame = frames[min(position[0],len(frames)-1)]
                    position[0] += 1
                    return frame
                result = function(read, taps.append, label, records, lambda:0, lambda _:None)
                assert result is title and taps == ([grid,title] if transition else [title])
                assert records[-1]["stage"] == "FILE_TAPPED"
                assert len(records[0]["filename_matches"]) == 2, "summary evidence discarded"
                positive += 1
        for kind in ("two_titles", "summary_only", "foreign_summary", "unknown_resource"):
            other = ET.Element("node", dict(summary.attrib))
            if kind == "foreign_summary": other.set("package", "foreign.app")
            if kind == "unknown_resource": other.set("resource-id", "other:id/title")
            frame = [view,title,title,summary] if kind == "two_titles" else (
                [view,summary] if kind == "summary_only" else [view,title,other])
            taps=[];records=[];now=[0]
            def pause(_): now[0] += .25
            try:
                function(lambda:frame,taps.append,label,records,lambda:now[0],pause)
            except (AssertionError,TimeoutError):
                pass
            else:
                raise AssertionError("summary control accepted "+kind)
            assert not taps, "ambiguous or non-title target tapped"
            negative += 1
        return positive,negative
    assert exercise(select_restore_file) == (4,4)
    source = inspect.getsource(select_restore_file)
    old = 'n.get("resource-id") == "android:id/summary"'
    assert source.count(old) == 1
    namespace = dict(globals())
    exec(compile(source.replace(old,"False",1),"<summary-filter-mutant>","exec"),namespace)
    mutant = namespace["select_restore_file"]
    taps=[]
    assert mutant(lambda:[view,title],taps.append,label,[],lambda:0,lambda _:None) is title
    assert taps == [title]
    try: exercise(mutant)
    except AssertionError: pass
    else: raise AssertionError("summary filter mutant survived")
    print("RESTORE_PICKER_SUMMARY positive=4 negative=4 witnessed_mutant=1 PASS; HOST_REPLAY_NOT_ANDROID",flush=True)



def run_database_phase(args, *, timeout, capture, phase):
    """Keep one original call and exception; persist partial streams without decoding."""
    try:
        return run(args, timeout=timeout, capture=capture)
    except subprocess.TimeoutExpired as failure:
        try:
            streams={}
            for name,value in (("stdout",failure.stdout),("stderr",failure.stderr)):
                raw=value if isinstance(value,bytes) else (value.encode("utf-8") if value is not None else b"")
                filename="device-"+phase+"-timeout-"+name+".txt"
                (ROOT/filename).write_bytes(raw)
                streams[name]={"file":filename,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
                               "captured":value is not None,"original_type":type(value).__name__}
            receipt={"status":"TIMEOUT_NOT_VERIFIED","phase":phase,"command":list(map(str,failure.cmd)),
                     "timeout_seconds":failure.timeout,"attempts":1,"streams":streams}
            (ROOT/("device-"+phase+"-timeout.txt")).write_text(json.dumps(receipt,indent=2)+"\n")
            print("DATABASE_TIMEOUT_EVIDENCE "+json.dumps(receipt),flush=True)
        except Exception as secondary:
            print("DATABASE_TIMEOUT_EVIDENCE_FAILED "+type(secondary).__name__,flush=True)
        raise

def database_timeout_selftest():
    """Actual helper, exception doubles and a real host child timeout, never Android."""
    import ast, inspect, tempfile, sys
    from unittest.mock import patch
    source=inspect.getsource(run_database_phase)
    def exercise(function,mode):
        with tempfile.TemporaryDirectory(prefix="database-timeout-") as directory:
            root=Path(directory);calls=[];command=["adb","-s","fixture","shell","am","instrument"]
            payload={"binary":b"\x00\xffpartial\n","unicode":"中文输出","empty":b"","missing":None}.get(mode,b"sentinel")
            error=subprocess.TimeoutExpired(command,180,output=payload,stderr=b"stderr\x00")
            sentinel=subprocess.CompletedProcess(command,0,"ok")
            if mode=="nonzero":error=subprocess.CalledProcessError(7,command,output=b"failure")
            if mode=="oserror":error=OSError("host sentinel")
            def runner(args,**kw):
                calls.append((args,kw))
                if mode=="success":return sentinel
                raise error
            seen=None;result=None
            with patch.dict(function.__globals__,run=runner,ROOT=root):
                try:result=function(command,timeout=180,capture=True,phase="seed")
                except BaseException as exc:seen=exc
            assert calls==[(command,{"timeout":180,"capture":True})],"command/budget/attempt changed"
            if mode=="success":
                assert result is sentinel and seen is None and not list(root.iterdir())
            elif mode in ("nonzero","oserror"):
                assert seen is error and not list(root.iterdir())
            else:
                assert seen is error,"original exception replaced"
                receipt=json.loads((root/"device-seed-timeout.txt").read_text())
                assert receipt["status"]=="TIMEOUT_NOT_VERIFIED" and receipt["command"]==command
                assert receipt["timeout_seconds"]==180 and receipt["attempts"]==1
                for name,value in (("stdout",payload),("stderr",b"stderr\x00")):
                    expected=value if isinstance(value,bytes) else (value.encode() if value is not None else b"")
                    row=receipt["streams"][name]
                    assert row=={"file":"device-seed-timeout-"+name+".txt","bytes":len(expected),
                                 "sha256":hashlib.sha256(expected).hexdigest(),"captured":value is not None,
                                 "original_type":type(value).__name__}
                    assert (root/row["file"]).read_bytes()==expected,"partial stream changed"
    modes=("success","binary","unicode","empty","missing","nonzero","oserror")
    for mode in modes:exercise(run_database_phase,mode)
    changes=[
        ("write_bytes(raw)","write_bytes(b'')","binary"),
        ('"attempts":1','"attempts":2',"binary"),
        ("        raise\n","        return None\n","binary"),
    ]
    for old,new,bad in changes:
        assert source.count(old)==1
        scope=dict(globals());exec(compile(source.replace(old,new,1),"<timeout-mutant>","exec"),scope)
        function=scope["run_database_phase"];exercise(function,"success")
        try:exercise(function,bad)
        except AssertionError:pass
        else:raise AssertionError("timeout mutant survived "+old)
    # A real Python child flushes then stays alive beyond the HOST-only test cap.
    # This cap is not the unchanged 180-second device command.
    with tempfile.TemporaryDirectory(prefix="timeout-child-") as directory:
        command=[sys.executable,"-c","import os,time;os.write(1,b'HOST_PARTIAL_SENTINEL\\n');time.sleep(60)"]
        seen=None
        with patch.dict(globals(),ROOT=Path(directory)):
            try:run_database_phase(command,timeout=2,capture=True,phase="seed")
            except subprocess.TimeoutExpired as exc:seen=exc
        assert seen is not None and seen.timeout==2 and seen.cmd==command
        assert seen.stdout==b"HOST_PARTIAL_SENTINEL\n","child fixture failed to reach output precondition"
        assert (Path(directory)/"device-seed-timeout-stdout.txt").read_bytes()==seen.stdout
    # Secondary persistence failure never replaces the original timeout.
    sentinel=subprocess.TimeoutExpired(["test"],180,output=b"partial")
    def failed(*a,**kw):raise sentinel
    with tempfile.TemporaryDirectory(prefix="timeout-write-failure-") as directory:
        root=Path(directory)/"file";root.write_bytes(b"x")
        with patch.dict(globals(),ROOT=root,run=failed):
            try:run_database_phase(["test"],timeout=180,capture=True,phase="seed")
            except subprocess.TimeoutExpired as exc:assert exc is sentinel
            else:raise AssertionError("secondary failure swallowed timeout")
    print("DATABASE_TIMEOUT_HOST cases=7 witnessed_mutants=3 real_child_timeout=1 secondary_failure=1 PASS NOT_DEVICE_ROOT_CAUSE",flush=True)

def readiness_timeout_wiring_selftest():
    """Cross-file registration and exact actual caller checks, not string presence."""
    import ast,copy
    emulator=ast.parse(Path(__file__).read_text())
    paged=ast.parse((ROOT/"tools/verify_paged_exports.py").read_text())
    def check(e,p):
        functions={n.name:n for n in e.body if isinstance(n,ast.FunctionDef)}
        phase=functions["verify_database"]
        calls=[n for n in ast.walk(phase) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
               and n.func.id=="run_database_phase"]
        assert len(calls)==1
        call=calls[0]
        assert ast.unparse(call)=="run_database_phase([adb, '-s', SERIAL, 'shell', 'am', 'instrument', '-w', '-r', '-e', 'phase', phase, '-e', 'expectedApi', str(API), PKG + '.test/com.supercubegame.pockettodo.V12DeviceTest'], timeout=180, capture=True, phase=phase)"
        assert sum(isinstance(n,ast.For) and ast.unparse(n.iter)=="('seed', 'reopen')" for n in ast.walk(phase))==1
        for tree,name,required in ((e,"parser_selftest",("database_timeout_selftest","readiness_timeout_wiring_selftest")),
                                   (p,"selftest",("paged_readiness_selftest",))):
            f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            names=[n.value.func.id for n in f.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name)]
            assert all(names.count(x)==1 for x in required),"permanent test call omitted"
    check(emulator,paged)
    for name in ("run_database_phase","database_timeout_selftest","paged_readiness_selftest"):
        e,p=copy.deepcopy(emulator),copy.deepcopy(paged);changed=0
        tree=p if name=="paged_readiness_selftest" else e
        fname="selftest" if tree is p else ("verify_database" if name=="run_database_phase" else "parser_selftest")
        f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==fname)
        for n in ast.walk(f):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name:n.func.id="omitted";changed+=1
        assert changed==1
        try:check(e,p)
        except AssertionError:pass
        else:raise AssertionError("registration omission survived")
    workflow=(ROOT/".github/workflows/android.yml").read_text()
    def collected(text):
        import re
        lines=[];active=False
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):continue
            if re.match(r"^  [A-Za-z_][A-Za-z0-9_]*:",line):active=line=="  database:"
            if active:lines.append(line)
        steps=[];current=[]
        for line in lines:
            if line.startswith("      - "):
                if current:steps.append(current)
                current=[]
            current.append(line)
        if current:steps.append(current)
        selected=[s for s in steps if "          name: database-api-${{ matrix.api }}" in s]
        assert len(selected)==1,"actual database upload absent"
        step=selected[0]
        assert step[0]=="      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
        assert step.count("        if: always()")==1
        assert step.count("          if-no-files-found: error")==1
        assert step.count("          path: |")==1
        paths=[]
        for line in step[step.index("          path: |")+1:]:
            if not line.startswith("            "):break
            paths.append(line.strip())
        assert "device-*.txt" in paths,"partial streams/receipt not collected"
    collected(workflow)
    # Alter only the selected database upload, not matching prose in host scripts.
    mark="          name: database-api-${{ matrix.api }}"
    assert workflow.count("\n"+mark+"\n")==1
    at=workflow.index("\n"+mark+"\n")
    tail=workflow[at:]
    assert "            device-*.txt\n" in tail
    bad=workflow[:at]+tail.replace("            device-*.txt\n","",1)
    try:collected(bad)
    except AssertionError:pass
    else:raise AssertionError("artifact collection omission survived")
    print("READINESS_TIMEOUT_WIRING actual_call=1 registration_omissions=3 upload_omissions=1 PASS AST_AND_COLLECTION_ONLY",flush=True)

def reveal_todo(read_nodes, swipe, package, title, clock=time.monotonic):
    """Navigation within one original20s observation budget, never retry a write."""
    deadline=clock()+20
    history=[]
    for direction in (-1,1):
        previous=None
        for attempt in range(9):
            assert clock()<deadline, 'todo navigation deadline; history='+repr(history)
            frame=list(read_nodes())
            assert clock()<deadline, 'todo observation exceeded deadline'
            view=[n for n in frame if n.get('content-desc')=='todo-list-scroll']
            assert len(view)==1, 'missing/duplicate todo viewport'
            view=view[0]
            assert view.get('package')==package and view.get('class')=='android.widget.ScrollView' and view.get('enabled')=='true', 'invalid todo viewport owner/type'
            def bounds(n):
                m=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.get('bounds',''))
                assert m, 'malformed todo bounds'
                a,b,c,d=map(int,m.groups())
                assert c>a and d>b, 'empty todo bounds'
                return a,b,c,d
            left,top,right,bottom=bounds(view)
            assert right-left>=3 and bottom-top>=3, 'collapsed todo viewport'
            matches=[n for n in frame if n.get('text')==title]
            assert len(matches)<=1, 'ambiguous todo title'
            if matches:
                n=matches[0];a,b,c,d=bounds(n)
                assert n.get('package')==package and n.get('class')=='android.widget.CheckBox' and n.get('enabled')=='true', 'invalid todo checkbox'
                identity=n.get('content-desc','')
                assert identity.startswith('todo-') and len(identity)>5, 'missing todo identity'
                assert left<=a<c<=right and top<=b<d<=bottom, 'todo outside viewport'
                print('TODO_VIEWPORT_FOUND '+json.dumps(dict(title=title,identity=identity,bounds=[a,b,c,d],history=history),ensure_ascii=False),flush=True)
                return n
            signature=tuple(tuple(n.get(k,'') for k in ('package','content-desc','text','bounds','class')) for n in frame)
            if signature==previous:break
            previous=signature
            if attempt<8:
                x,start,_,end=summary_gesture((left,top,right,bottom))
                if direction==-1:start,end=end,start
                history.append(dict(direction=direction,attempt=attempt,viewport=[left,top,right,bottom],gesture=[x,start,x,end]))
                swipe(x,start,x,end)
    raise AssertionError('todo identity absent at navigation bound; history='+repr(history))

def todo_navigation_selftest():
    import ast,inspect,copy
    package='fixture.todo'
    view=dict(package=package,**{'content-desc':'todo-list-scroll','class':'android.widget.ScrollView','enabled':'true','bounds':'[18,288][302,522]'})
    target=dict(package=package,text='After backup',**{'content-desc':'todo-id3','class':'android.widget.CheckBox','enabled':'true','bounds':'[26,400][178,452]'})
    def run(fn,mode):
        offset=0;gestures=[];ticks=0
        def read():
            if mode=='bad-owner':return [dict(view,package='other'),target]
            if mode=='collapsed':return [dict(view,bounds='[18,341][302,343]')]
            if mode=='duplicate-view':return [view,view]
            if mode=='malformed':return [dict(view,bounds='broken')]
            if mode=='empty':return [dict(view,bounds='[18,288][18,522]')]
            visible=mode!='absent' and (mode!='delayed' or offset>0)
            if not visible:return [view]
            n=dict(target)
            if mode=='bad-class':n['class']='android.widget.TextView'
            if mode=='bad-id':n['content-desc']='todo-'
            if mode=='outside':n['bounds']='[26,523][178,575]'
            if mode=='disabled':n['enabled']='false'
            if mode=='foreign-target':n['package']='other'
            return [view,n,n] if mode=='duplicate-target' else [view,n]
        def swipe(x,a,y,b):
            nonlocal offset
            assert 18<x<302 and x==y and 288<a<522 and 288<b<522, 'gesture outside current viewport'
            gestures.append((x,a,y,b));offset=max(0,offset+(1 if a>b else -1))
        def clock():
            nonlocal ticks
            ticks+=1
            return ticks*21 if mode=='deadline' else ticks/1000
        result=fn(read,swipe,package,'After backup',clock)
        if mode in ('ready','delayed'):assert result==target
        if mode=='delayed':assert len(gestures)==2,gestures
        return gestures
    assert run(reveal_todo,'ready')==[]
    run(reveal_todo,'delayed')
    negatives=['bad-owner','collapsed','duplicate-view','malformed','empty','absent','bad-class','bad-id','outside','disabled','foreign-target','duplicate-target','deadline']
    for mode in negatives:
        try:run(reveal_todo,mode)
        except AssertionError:pass
        else:raise AssertionError('todo negative survived '+mode)
    source=inspect.getsource(reveal_todo)
    mutations=[
        ("view.get('package')==package","True",'bad-owner'),
        ("n.get('class')=='android.widget.CheckBox'","True",'bad-class'),
        (" and len(identity)>5","",'bad-id'),
        ("left<=a<c<=right and top<=b<d<=bottom","True",'outside'),
        ("clock()<deadline","True",'deadline'),
    ]
    for old,new,mode in mutations:
        assert old in source
        scope=dict(globals());exec(compile(source.replace(old,new),'<todo-mutant>','exec'),scope)
        fn=scope['reveal_todo'];run(fn,'ready')
        try:run(fn,mode)
        except AssertionError:raise AssertionError('todo mutant was not witnessed '+mode)
    module=ast.parse(Path(__file__).read_text())
    def wiring(tree):
        funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        caller=next(n for n in funcs['_verify_native_ui'].body if isinstance(n,ast.FunctionDef) and n.name=='named_todo')
        assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='reveal_todo' for n in ast.walk(caller)), 'todo caller omitted'
        for name in ('todo_navigation_selftest','result_ui_selftest'):
            assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name for n in ast.walk(funcs['parser_selftest'])), 'selftest omitted'
    wiring(module)
    for name in ('reveal_todo','todo_navigation_selftest','result_ui_selftest'):
        mutant=copy.deepcopy(module)
        class Remove(ast.NodeTransformer):
            def visit_Call(self,n):
                if isinstance(n.func,ast.Name) and n.func.id==name:return ast.Constant(None)
                return self.generic_visit(n)
        mutant=Remove().visit(mutant)
        try:wiring(mutant)
        except AssertionError:pass
        else:raise AssertionError('whole call omission survived '+name)
    print('TODO_NAVIGATION_HOST positive=2 negatives=13 witnessed_mutants=5 caller_omissions=3 PASS SYNTHETIC_GEOMETRY_NOT_ANDROID')

RESULT_UI_EXTRACTOR=r'''
import java.nio.file.*;import java.util.*;import javax.tools.*;
import com.sun.source.tree.*;import com.sun.source.util.*;
public class Extract {
 public static void main(String[] a)throws Exception {
  String s=Files.readString(Path.of(a[0]));JavaCompiler c=ToolProvider.getSystemJavaCompiler();
  DiagnosticCollector<JavaFileObject> d=new DiagnosticCollector<>();
  try(StandardJavaFileManager fm=c.getStandardFileManager(d,null,null)){
   JavacTask t=(JavacTask)c.getTask(null,fm,d,List.of("-proc:none"),null,fm.getJavaFileObjects(a[0]));
   CompilationUnitTree u=t.parse().iterator().next();
   if(d.getDiagnostics().stream().anyMatch(x->x.getKind()==Diagnostic.Kind.ERROR))throw new AssertionError("parse");
   SourcePositions p=Trees.instance(t).getSourcePositions();Set<String> wanted=new HashSet<>(Arrays.asList(a[2].split(","))),found=new HashSet<>();
   StringBuilder out=new StringBuilder();
   for(Tree member:((ClassTree)u.getTypeDecls().get(0)).getMembers()){
    String name=member instanceof MethodTree m?m.getName().toString():member instanceof VariableTree v?v.getName().toString():member instanceof ClassTree k?k.getSimpleName().toString():"";
    if(wanted.contains(name)){
     if(!found.add(name)&&!name.equals("work"))throw new AssertionError("duplicate");
     out.append(s.substring((int)p.getStartPosition(u,member),(int)p.getEndPosition(u,member))).append("\n");
    }
   }
   if(!found.equals(wanted))throw new AssertionError("missing actual member "+found);
   Files.writeString(Path.of(a[1]),out.toString());
  }
 }
}
'''

RESULT_UI_HARNESS=r'''
import java.nio.file.*;import java.io.*;import java.util.concurrent.*;import java.util.function.*;
class Uri {String getScheme(){throw new AssertionError("URI must not be read");}}
class Intent {Uri getData(){throw new AssertionError("result payload must not be read");}}
class Base {static final int RESULT_OK=-1;protected void onActivityResult(int a,int b,Intent c){}}
public class Harness extends Base {
 static int writes,readbacks,opens,closes;static final String MESSAGE="页面已重建，请重新选择导出内容";
 static final int EXPORT_BACKUP=41,IMPORT_BACKUP=42,PICK_NOTE_IMAGE=43,EXPORT_NOTES=44;
 static final String[] SHARE_FORMATS={"Markdown","PDF","PNG"};
 static class android {static class database {static class sqlite {
  static class SQLiteDatabase {void beginTransaction(){}void setTransactionSuccessful(){}void endTransaction(){}}
 }}}
 static class AppDatabase {
  void close(){}byte[] exportState(){throw new AssertionError("DB read not allowed");}
  android.database.sqlite.SQLiteDatabase getWritableDatabase(){throw new AssertionError("DB write not allowed");}
 }
 static class TodayScreen {
  AppDatabase db;String message="";int notices;
  TodayScreen(Harness owner,AppDatabase d){db=d;}
  void show(Object saved){message="已保存到本机";}
  void close(){}void message(String s,boolean error){message=s;notices++;}
  void runBackupExport(Callable<Boolean> save){throw new AssertionError("backup must not replay");}
  void backupCancelled(){throw new AssertionError("backup must not replay");}
  void exportBackup(Path p){throw new AssertionError("backup must not replay");}
  void backupExported(){}void previewRestore(Path p){throw new AssertionError("restore must not replay");}
  void backupFailed(Exception e){throw new AssertionError(e);}
  <T> void work(Callable<T> a,Consumer<T> b,Runnable c){throw new AssertionError("work must not enqueue");}
 }
 static class ShareTicket {void close(){closes++;}byte[] take(byte[] b){throw new AssertionError("consent must not resurrect");}}
 static class VerifiedShareWrite {
  interface O {OutputStream open()throws IOException;}interface I {InputStream open()throws IOException;}
  static void write(byte[] b,O o,I i){writes++;throw new AssertionError("no output");}
 }
 static class Delivery {boolean taken;AppDatabase take(){if(taken)return null;taken=true;opens++;return new AppDatabase();}}
 static class Resolver {InputStream openInputStream(Uri u){readbacks++;throw new AssertionError("no URI read");}}
 TodayScreen screen;Object startupSaved;ShareTicket pendingShare;int pendingShareFormat;
 Consumer<Uri> pendingImage;Delivery startupDelivery=new Delivery();
 Executor startupIo=Runnable::run;boolean destroyed,finishing;
 boolean isDestroyed(){return destroyed;}boolean isFinishing(){return finishing;}
 void releaseStartup(){}void startupMessage(boolean failed){throw new AssertionError("startup failed");}
 java.io.File getCacheDir(){throw new AssertionError("no cache access");}
 Resolver getContentResolver(){return new Resolver();}
 OutputStream openDestination(Uri u){writes++;throw new AssertionError("no output");}
 /*ACTUAL*/
 public static void main(String[] args){
  Harness h=new Harness();String scenario=args[0];int request=EXPORT_NOTES;
  if(scenario.equals("ready"))h.finishDefaultStartup();
  if(scenario.equals("image"))request=PICK_NOTE_IMAGE;
  if(scenario.equals("backup"))request=EXPORT_BACKUP;
  if(scenario.equals("import"))request=IMPORT_BACKUP;
  if(scenario.equals("unknown"))request=987;
  if(scenario.equals("destroyed"))h.destroyed=true;
  if(scenario.equals("finishing"))h.finishing=true;
  if(scenario.equals("ticket")){h.pendingShare=new ShareTicket();h.pendingImage=u->{throw new AssertionError("callback replay");};}
  h.onActivityResult(request,RESULT_OK,new Intent());
  if(h.destroyed||h.finishing){
   if(h.startupRefusal!=0||h.screen!=null||opens!=0)throw new AssertionError("retired notice");
  }else{
   if(!scenario.equals("ready"))h.finishDefaultStartup();
   String expected=request==EXPORT_NOTES?MESSAGE:request==PICK_NOTE_IMAGE?"页面已重建，请重新选择图片；笔记未改变":request==987?"已保存到本机":"页面已重建，请重新选择备份或恢复操作；本机数据未改变";
   if(!expected.equals(h.screen.message))throw new AssertionError("lost_notice: actual="+h.screen.message);
   if(h.startupRefusal!=0)throw new AssertionError("notice not consumed");
   int before=h.screen.notices;h.finishDefaultStartup();
   if(before!=h.screen.notices||opens!=1)throw new AssertionError("notice replay");
   if(scenario.equals("ticket")&&(closes!=1||h.pendingShare!=null||h.pendingImage!=null))throw new AssertionError("consent retained");
  }
  if(writes!=0||readbacks!=0)throw new AssertionError("side effects");
  System.out.println("PASS "+scenario+" no_URI_no_write");
 }
}
'''

BACKUP_SAF_HARNESS=r'''
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.Callable;import java.util.function.Consumer;
class Base {static final int RESULT_OK=-1;protected void onActivityResult(int x,int y,Intent z){}}
class Uri {String getScheme(){return BackupProbe.mode.equals("bad-scheme")?"other":"content";}}
class Intent {final Uri dest=new Uri();Uri getData(){return dest;}}
public class BackupProbe extends Base {
 static final int EXPORT_BACKUP=41,IMPORT_BACKUP=42,PICK_NOTE_IMAGE=43,EXPORT_NOTES=44;
 static final byte[] fixture=new byte[32785];static {for(int i=0;i<fixture.length;i++)fixture[i]=(byte)(11+37*i);}
 static Path scratch;static String mode;static int success,failure,readbacks,output,writeClose,readClose,writes,notices,queued;static boolean worker,ioOnMain;static byte[] persisted;
 static class TodayScreen {boolean busy,closed;/*DISPATCH*/void backupCancelled(){throw new AssertionError("cancel inside positive flow");}void exportBackup(Path p)throws IOException{if(!worker)ioOnMain=true;Files.write(p,fixture,StandardOpenOption.CREATE_NEW);}void previewRestore(Path p){throw new AssertionError();}void backupExported(){success++;}void backupFailed(Exception e){failure++;}void message(String s,boolean err){notices++;if(err){if(!(s.contains("另选位置")||s.contains("页面正忙")))throw new AssertionError("misleading failure: "+s);failure++;}}
  <T>void work(Callable<T> op,Consumer<T> done,Runnable fail){queued++;try{T t;worker=true;try{t=op.call();}finally{worker=false;}done.accept(t);}catch(Exception e){fail.run();}}}
 TodayScreen screen=new TodayScreen();int startupRefusal;Consumer<Uri> pendingImage;static class Ticket{void close(){}}Ticket pendingShare;
 boolean isDestroyed(){return false;}boolean isFinishing(){return false;}void finishShare(int r,Intent i){throw new AssertionError();}File getCacheDir(){return scratch.toFile();}
 OutputStream openDestination(Uri u)throws IOException{if(!worker)ioOnMain=true;output++;if(mode.equals("open-write-fail"))throw new IOException("no destination");return new OutputStream(){ByteArrayOutputStream b=new ByteArrayOutputStream();public void write(int x){b.write(x);}public void write(byte[] a,int off,int n)throws IOException{writes++;if(mode.equals("write-fail"))throw new IOException("test write refused");b.write(a,off,n);}public void close()throws IOException{writeClose++;if(mode.equals("close-write-fail"))throw new IOException("test close refused");persisted=b.toByteArray();if(mode.equals("truncated"))persisted=Arrays.copyOf(persisted,persisted.length-1);if(mode.equals("extended"))persisted=Arrays.copyOf(persisted,persisted.length+1);if(mode.equals("changed"))persisted[16384]^=1;}};}
 static class Resolver {InputStream openInputStream(Uri u)throws IOException{if(!worker)ioOnMain=true;readbacks++;if(writeClose!=1)throw new AssertionError("read before writer closed");if(mode.equals("no-read"))throw new IOException("no readback");if(mode.equals("null-read"))return null;return new InputStream(){int at;public int read(){return at==persisted.length?-1:persisted[at++]&255;}public int read(byte[] a,int off,int n)throws IOException{if(mode.equals("read-fail")&&at>0)throw new IOException("test stale target");if(mode.equals("stalled"))return 0;if(at==persisted.length)return -1;int c=Math.min(Math.min(n,503),persisted.length-at);System.arraycopy(persisted,at,a,off,c);at+=c;return c;}public void close()throws IOException{readClose++;if(mode.equals("close-read-fail"))throw new IOException("test read close");}};}}
 Resolver getContentResolver(){return new Resolver();}
 /*ACTUAL*/
 public static void main(String[] args)throws Exception {mode=args[0];scratch=Files.createTempDirectory("backup-readback-");try{BackupProbe h=new BackupProbe();h.screen.busy=mode.equals("busy");h.onActivityResult(EXPORT_BACKUP,RESULT_OK,new Intent());
 System.out.println(mode+" success="+success+" failure="+failure+" actual="+(persisted==null?-1:persisted.length)+" reads="+readbacks+" expected="+fixture.length+" queued="+queued+" ioOnMain="+ioOnMain);
 boolean good=mode.equals("ok");if(good){if(success!=1||failure!=0||!Arrays.equals(persisted,fixture))throw new AssertionError("valid copy lost");}else if(success!=0||failure!=1)throw new AssertionError("INVALID_COPY_REPORTED_AS_SAVED:"+mode);
 if(mode.equals("busy")||mode.equals("bad-scheme")){if(output!=0||readbacks!=0||queued!=(mode.equals("busy")?0:1))throw new AssertionError("must refuse before IO");}
 else {boolean pre=mode.equals("open-write-fail")||mode.equals("write-fail")||mode.equals("close-write-fail");if(queued!=1||ioOnMain||output!=1||readbacks!=(pre?0:1)||writeClose!=(mode.equals("open-write-fail")?0:1)||readClose!=(pre||mode.equals("no-read")||mode.equals("null-read")?0:1))throw new AssertionError("wrong ownership close order or reads");}
 try(var all=Files.list(scratch)){if(all.findAny().isPresent())throw new AssertionError("private temp leftovers");} }finally{try(var s=Files.walk(scratch)){for(Path p:s.sorted(Comparator.reverseOrder()).toList())Files.delete(p);}} }
}
'''

EDITOR_UI_HARNESS=r'''
import java.util.*;import java.util.concurrent.*;import java.util.function.*;
public class EditorHarness {
 static List<String> events=new ArrayList<>();static Button positive,negative;static EditText current;static boolean fail,absentIme;
 static final int MUTED=1,ERROR=2;boolean busy;
 static class Activity {static final String INPUT_METHOD_SERVICE="ime";Object getSystemService(String key){return absentIme?null:new InputMethodManager();}}
 Activity activity=new Activity();
 static class InputMethodManager {void hideSoftInputFromWindow(Object token,int flags){if(!token.equals("attached"))throw new AssertionError("detached token");events.add("hide");}}
 interface Click {void run(Object x);}
 static class Button {Click listener;boolean enabled=true;void setOnClickListener(Click c){listener=c;}void setEnabled(boolean b){enabled=b;}}
 static class LinearLayout {static class LayoutParams {LayoutParams(int a,int b){}}void setPadding(int a,int b,int c,int d){}void addView(Object o){}void addView(Object o,Object p){}}
 static class TextView {void setText(String s){}void setTextColor(int n){}}
 static class EditText {String text;boolean enabled=true;void setText(String s){text=s;}String getText(){return text;}void setEnabled(boolean b){enabled=b;}Object getWindowToken(){return events.contains("dismiss")?"detached":"attached";}void clearFocus(){events.add("clear");}}
 static class AlertDialog {
  static final int BUTTON_POSITIVE=1,BUTTON_NEGATIVE=2;Click show;boolean cancelable=true;
  static class Builder {
   Builder(Activity a){}Builder setTitle(String t){return this;}Builder setView(Object v){return this;}
   Builder setNegativeButton(String t,Object c){return this;}Builder setPositiveButton(String t,Object c){return this;}
   AlertDialog create(){positive=new Button();negative=new Button();return new AlertDialog();}
  }
  void setOnShowListener(Click c){show=c;}Button getButton(int b){return b==1?positive:negative;}
  void show(){show.run(null);}void dismiss(){events.add("dismiss");}void setCancelable(boolean b){cancelable=b;}
 }
 LinearLayout column(){return new LinearLayout();}int dp(int n){return n;}
 EditText field(String d,boolean m){current=new EditText();return current;}
 TextView text(String s,int n,int c){return new TextView();}
 <T>void work(Callable<T> task,Consumer<T> ok,Runnable failed){
  events.add("work");try{if(fail)throw new Exception("injected save failure");T r=task.call();ok.accept(r);}catch(Exception e){failed.run();}
 }
 /*ACTUAL*/
 public static void main(String[] args){
  String mode=args[0];EditorHarness h=new EditorHarness();
  h.busy=mode.equals("busy");fail=mode.equals("failure");absentIme=mode.equals("no-ime");
  h.editor("title","description",mode.equals("empty")?" ":"new text",false,v->{events.add("save");},()->events.add("refresh"));
  if(mode.equals("busy")){if(positive!=null||!events.isEmpty())throw new AssertionError("busy changed");}
  else if(mode.equals("cancel")){if(!events.isEmpty())throw new AssertionError("cancel changed");}
  else{
   positive.listener.run(null);
   List<String> expected=mode.equals("empty")?List.of():fail?List.of("work"):absentIme?List.of("work","save","clear","dismiss","refresh"):List.of("work","save","hide","clear","dismiss","refresh");
   if(!events.equals(expected))throw new AssertionError("IME/order "+events+" expected "+expected);
   if((fail||mode.equals("empty"))&&(!current.enabled||!positive.enabled||!negative.enabled))throw new AssertionError("validation not editable");
  }
  System.out.println("PASS "+mode);
 }
}
'''

NOTICE_UI_HARNESS=r'''
import java.util.*;import java.util.concurrent.*;import java.util.function.*;
public class NoticeHarness {
 static final int ERROR=1,MUTED=2;boolean closed,busy;Object root=new Object();
 static class Status {String value;void setText(String v){value=v;}void setTextColor(int c){}}
 Status status=new Status();
 List<Runnable> jobs=new ArrayList<>(),ui=new ArrayList<>();
 Executor io=jobs::add;
 class Activity {void runOnUiThread(Runnable r){ui.add(r);}boolean isDestroyed(){return false;}}
 Activity activity=new Activity();void pause(Object x){}void resume(){}
 /*ACTUAL*/
 public static void main(String[] a){
  NoticeHarness h=new NoticeHarness();boolean newer=a[0].equals("newer");int[] success={0};
  h.work(()->1,v->success[0]++,null);
  if(newer)h.message("recreated-refusal",true);
  if(h.jobs.size()!=1||!h.ui.isEmpty())throw new AssertionError("fixture scheduling");
  h.jobs.remove(0).run();if(h.ui.size()!=1)throw new AssertionError("fixture completion");
  h.ui.remove(0).run();
  String expected=newer?"recreated-refusal":"已保存到本机";
  if(!expected.equals(h.status.value)||success[0]!=1||h.busy)throw new AssertionError("notice overwritten "+h.status.value);
 }
}
'''

def result_ui_selftest():
    """Current-source Java execution. Android, IME and DB are explicit doubles."""
    import tempfile
    def checked(args):
        p=subprocess.run(args,capture_output=True,text=True,timeout=30)
        assert p.returncode==0,(args,p.stdout,p.stderr)
        return p
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'Extract.java').write_text(RESULT_UI_EXTRACTOR)
        compiler=['java','-m','jdk.compiler/com.sun.tools.javac.Main','-d',tmp]
        checked(compiler+[str(root/'Extract.java')])
        extracted={}
        for filename,names in [('MainActivity.java','startupRefusal,finishDefaultStartup,onActivityResult,finishShare,writeVerifiedBackup'),('TodayScreen.java','editor')]:
            source=ROOT/'src/main/java/com/supercubegame/pockettodo'/filename
            checked(['java','-cp',tmp,'Extract',str(source),str(root/'members.java'),names])
            extracted[filename]=(root/'members.java').read_text()
        def compile_run(members,template,cls,modes):
            file=root/(cls+'.java');file.write_text(template.replace('/*ACTUAL*/',members))
            checked(compiler+[str(file)])
            return {mode:subprocess.run(['java','-cp',tmp,cls,mode],capture_output=True,text=True,timeout=10) for mode in modes}
        main=extracted['MainActivity.java'];editor=extracted['TodayScreen.java']
        source=ROOT/'src/main/java/com/supercubegame/pockettodo'
        checked(['java','-cp',tmp,'Extract',str(source/'MainActivity.java'),str(root/'backup.java'),'onActivityResult,writeVerifiedBackup'])
        checked(['java','-cp',tmp,'Extract',str(source/'TodayScreen.java'),str(root/'backup-ui.java'),'runBackupExport'])
        backup=(root/'backup.java').read_text(); backup_harness=BACKUP_SAF_HARNESS.replace('/*DISPATCH*/',(root/'backup-ui.java').read_text())
        modes=['ok','truncated','changed','extended','no-read','null-read','stalled','read-fail','close-read-fail','open-write-fail','write-fail','close-write-fail','busy','bad-scheme']
        reports=compile_run(backup,backup_harness,'BackupProbe',modes)
        assert all(x.returncode==0 for x in reports.values()),{k:(v.stdout,v.stderr) for k,v in reports.items() if v.returncode}
        mutants=[('if(left[at+i]!=right[i])','if(false)','changed'),('if(got.read()!=-1)','if(false)','extended'),('if(count<=0||count>n-at)','if(count<0)break; if(count==0||count>n-at)','truncated')]
        for old,new,case in mutants:
            assert backup.count(old)==1,old
            result=compile_run(backup.replace(old,new,1),backup_harness,'BackupProbe',['ok',case])
            assert result['ok'].returncode==0 and result[case].returncode!=0 and 'INVALID_COPY_REPORTED_AS_SAVED' in result[case].stderr,(case,result[case].stderr)
        print('BACKUP_SAF_HOST 14 scenarios and 3 witnessed wrong-success mutants: REAL CALLBACK, SYNTHETIC PROVIDER, NOT DEVICE',flush=True)
        scenarios=['ready','delayed','image','backup','import','unknown','destroyed','finishing','ticket']
        results=compile_run(main,RESULT_UI_HARNESS,'Harness',scenarios)
        assert all(p.returncode==0 for p in results.values()),{k:p.stderr for k,p in results.items() if p.returncode}
        # Reintroduce the original whole-guard omission while keeping a ready witness.
        start=main.index('        if(isDestroyed()||isFinishing())return;',main.index('onActivityResult('))
        end=main.index('        if(request==EXPORT_NOTES){finishShare',start)
        original=main[:start]+'        if(screen==null)return;\n'+main[end:]
        old=compile_run(original,RESULT_UI_HARNESS,'Harness',['ready','delayed'])
        assert old['ready'].returncode==0 and old['delayed'].returncode!=0 and 'lost_notice' in old['delayed'].stderr, 'original RED not witnessed'
        mutants=[
            ('startupRefusal=request;','startupRefusal=0;','delayed','lost_notice'),
            ('int refused=startupRefusal;startupRefusal=0;','int refused=startupRefusal;','delayed','notice not consumed'),
            ('if(isDestroyed()||isFinishing())return;','if(false)return;','destroyed','retired notice'),
            ('pendingImage=null;\n            if(pendingShare!=null)','/* omitted */\n            if(pendingShare!=null)','ticket','consent retained'),
        ]
        for old,new,mode,reason in mutants:
            assert main.count(old)==1,old
            run=compile_run(main.replace(old,new,1),RESULT_UI_HARNESS,'Harness',['ready',mode])
            assert run['ready'].returncode==0 and run[mode].returncode!=0 and reason in run[mode].stderr,(mode,run[mode].stderr)
        modes=['success','empty','failure','cancel','busy','no-ime']
        results=compile_run(editor,EDITOR_UI_HARNESS,'EditorHarness',modes)
        assert all(p.returncode==0 for p in results.values()),{k:p.stderr for k,p in results.items() if p.returncode}
        # Original editor success must fail while validation still behaves normally.
        a=editor.index('                InputMethodManager ime=')
        b=editor.index('dialog.dismiss();success.run();',a)
        original=editor[:a]+editor[b:]
        run=compile_run(original,EDITOR_UI_HARNESS,'EditorHarness',['empty','success'])
        assert run['empty'].returncode==0 and run['success'].returncode!=0 and 'IME/order' in run['success'].stderr
        for old,new in [('if(ime!=null)ime.hideSoftInputFromWindow(field.getWindowToken(),0);',''),
                        ('field.clearFocus();',''),
                        ('dialog.dismiss();success.run();','success.run();dialog.dismiss();')]:
            assert editor.count(old)==1
            run=compile_run(editor.replace(old,new,1),EDITOR_UI_HARNESS,'EditorHarness',['empty','success'])
            assert run['empty'].returncode==0 and run['success'].returncode!=0 and 'IME/order' in run['success'].stderr,run['success'].stderr
        checked(['java','-cp',tmp,'Extract',str(ROOT/'src/main/java/com/supercubegame/pockettodo/TodayScreen.java'),str(root/'notice.java'),'work,message,notice'])
        notice=(root/'notice.java').read_text()
        run=compile_run(notice,NOTICE_UI_HARNESS,'NoticeHarness',['normal','newer'])
        assert all(p.returncode==0 for p in run.values()),{k:p.stderr for k,p in run.items()}
        assert notice.count('if(notice==noticeAtStart)')==2
        run=compile_run(notice.replace('if(notice==noticeAtStart)',''),NOTICE_UI_HARNESS,'NoticeHarness',['normal','newer'])
        assert run['normal'].returncode==0 and run['newer'].returncode!=0 and 'notice overwritten' in run['newer'].stderr
        extracted['TodayScreen.notice']=notice
        print('RESULT_EDITOR_HOST cases=17 original_RED=2 witnessed_mutants=8 PASS ACTUAL_SOURCE_ANDROID_DB_IME_DOUBLES_ONLY',
              {k:hashlib.sha256(v.encode()).hexdigest() for k,v in extracted.items()},flush=True)


"""Actual RelationEditor and restore-cancel caller tests, Android/DB doubles only."""
RELATION_EXTRACTOR=r'''
import java.nio.file.*;import java.util.*;import javax.tools.*;
import com.sun.source.tree.*;import com.sun.source.util.*;
public class ExtractRelation {
 public static void main(String[] a)throws Exception {
  String s=Files.readString(Path.of(a[0]));JavaCompiler c=ToolProvider.getSystemJavaCompiler();
  DiagnosticCollector<JavaFileObject> d=new DiagnosticCollector<>();
  try(StandardJavaFileManager fm=c.getStandardFileManager(d,null,null)){
   JavacTask t=(JavacTask)c.getTask(null,fm,d,List.of("-proc:none"),null,fm.getJavaFileObjects(a[0]));
   CompilationUnitTree u=t.parse().iterator().next();
   if(d.getDiagnostics().stream().anyMatch(x->x.getKind()==Diagnostic.Kind.ERROR))throw new AssertionError("parse");
   SourcePositions p=Trees.instance(t).getSourcePositions();Set<String> found=new HashSet<>();
   for(Tree member:((ClassTree)u.getTypeDecls().get(0)).getMembers()){
    String n=member instanceof ClassTree k?k.getSimpleName().toString():member instanceof MethodTree m?m.getName().toString():"";
    if(n.equals("RelationEditor")||n.equals("renderDetail")){
     if(!found.add(n))throw new AssertionError("duplicate");
     Files.writeString(Path.of(a[1],n+".txt"),s.substring((int)p.getStartPosition(u,member),(int)p.getEndPosition(u,member)));
     Files.writeString(Path.of(a[1],n+".ast"),member.toString());
    }
   }
   if(found.size()!=2)throw new AssertionError("actual class/caller missing");
  }
 }
}
'''

RELATION_HARNESS=r'''
import java.util.*;import java.util.concurrent.*;import java.util.function.*;
public class RelationHarness {
 static List<String> events=new ArrayList<>();static Map<String,android.view.View> views=new HashMap<>();
 static boolean noIme;static EditText field;
 static class android {
  static class content {static class Context {static String INPUT_METHOD_SERVICE="ime";}}
  static class view {
   static class View {
    View parent;List<View> children=new ArrayList<>();int height=-2;boolean attached=true,enabled=true;Consumer<View> listener;OnAttachStateChangeListener attach;String description="";
    interface OnAttachStateChangeListener {void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}
    boolean isAttachedToWindow(){return attached;}boolean isEnabled(){return enabled;}
    void setEnabled(boolean b){enabled=b;}void setContentDescription(String s){description=s;views.put(s,this);}
    void setOnClickListener(Consumer<View> l){listener=l;}void click(){if(listener!=null)listener.accept(this);}
    void addOnAttachStateChangeListener(OnAttachStateChangeListener l){attach=l;}
    Object getWindowToken(){if(!attached)throw new AssertionError("detached token");return this;}
    void clearFocus(){events.add("clear");}
    void detach(){attached=false;if(attach!=null)attach.onViewDetachedFromWindow(this);}
   }
   static class inputmethod {static class InputMethodManager {
    boolean hideSoftInputFromWindow(Object token,int flags){
     if(token!=field||!field.attached)throw new AssertionError("wrong/detached input token");
     events.add("hide");return true;
    }
   }}
  }
 }
 static class TextView extends android.view.View {
  String text="";void setText(String s){text=s;}String getText(){return text;}
 }
 static class EditText extends TextView {}
 static class Button extends TextView {}
 static class LinearLayout extends android.view.View {
  static class LayoutParams {int height;LayoutParams(int a,int b){height=b;}LayoutParams(int a,int b,int c){height=b;}}
  void addView(android.view.View v){if(v.parent!=null)throw new AssertionError("duplicate parent");v.parent=this;children.add(v);}
  void addView(android.view.View v,LayoutParams p){v.height=p.height;addView(v);}
 }
 static class ScrollView extends LinearLayout {ScrollView(Activity a){}}
 static class Activity {
  boolean finishing,destroyed;
  boolean isFinishing(){return finishing;}boolean isDestroyed(){return destroyed;}
  Object getSystemService(String s){return noIme?null:new android.view.inputmethod.InputMethodManager();}
 }
 static class AppDatabase {
  int prepares,confirms;boolean fail,stale;List<String> stored=List.of("Old");ActivityStringsPlan last;
  static class ActivityStringsPlan {
   boolean closed;long id=1;String title="Daily";List<String> values=List.of("Old");
   long activityId(){return id;}String title(){return title;}List<String> values(){return values;}
   void close(){closed=true;}
  }
  ActivityStringsPlan prepareActivityStrings(long id,boolean tags){
   prepares++;last=new ActivityStringsPlan();if(stale)last.id=9;return last;
  }
  boolean confirmActivityStrings(ActivityStringsPlan p,List<String> v){
   confirms++;if(fail||p.closed)throw new IllegalStateException("failed");
   stored=new ArrayList<>(v);return true;
  }
 }
 static class TodayScreen {
  static int INK,MUTED,ERROR;Activity activity=new Activity();AppDatabase db=new AppDatabase();
  ArrayDeque<Runnable> jobs=new ArrayDeque<>();String message="";
  <T>void work(Callable<T> c,Consumer<T> ok,Runnable bad){
   jobs.add(()->{T value;try{value=c.call();}catch(Exception e){if(bad!=null)bad.run();return;}ok.accept(value);});
  }
  void flush(){if(jobs.isEmpty())throw new AssertionError("missing actual work");jobs.remove().run();}
  LinearLayout content(){return new LinearLayout();}LinearLayout column(){return new LinearLayout();}
  TextView text(String s,int size,int color){TextView v=new TextView();v.setText(s);return v;}
  EditText field(String s,boolean multi){field=new EditText();field.setContentDescription(s);return field;}
  Button button(String s,Runnable r){Button b=new Button();b.setText(s);b.setOnClickListener(v->r.run());return b;}
  void message(String s,boolean error){message=s;}
 }
 /*ACTUAL*/
 static void check(boolean b,String s){if(!b)throw new AssertionError(s+" events="+events);}
 public static void main(String[] a){
  String mode=a[0];TodayScreen h=new TodayScreen();int[] backs={0};
  Runnable back=()->{events.add("back");backs[0]++;field.attached=false;};
  RelationEditor r=new RelationEditor(h,1,"Daily",(mode.equals("tags")||mode.equals("layout-tags")),List.of("Old"),back);
  android.view.View anchor=new android.view.View();
  if(mode.equals("finishing"))h.activity.finishing=true;
  if(mode.equals("destroyed"))h.activity.destroyed=true;
  if(mode.equals("stale"))h.db.stale=true;
  r.open(anchor);
  if(mode.equals("finishing")||mode.equals("destroyed")){
   check(h.jobs.isEmpty()&&h.db.prepares==0&&events.isEmpty(),"retired open");return;
  }
  h.flush();
  if(mode.equals("stale")){check(field==null&&h.db.last.closed&&events.isEmpty(),"stale open");return;}
  check(field!=null&&r.active(),"actual open/render reached");
  if(mode.equals("layout")||mode.equals("layout-tags")){
   check(r.root.children.size()==1&&r.root.children.get(0) instanceof ScrollView,"one whole editor viewport");
   android.view.View scroll=r.root.children.get(0);
   check(scroll.height==-1&&scroll.description.equals("relation-editor-scroll")&&scroll.children.size()==1,"viewport identity and allocation");
   android.view.View fields=scroll.children.get(0);
   check(fields.children.size()==7&&fields.children.get(0) instanceof TextView,"complete editor content");
   check(field.parent==fields&&views.get("relation-identity").parent==fields&&views.get("relation-validation").parent==fields
     &&views.get("relation-save").parent==fields&&views.get("relation-cancel").parent==fields,"all content scrolls");
   check(h.db.confirms==0&&h.jobs.isEmpty()&&r.active(),"layout readonly ownership");
   System.out.println("LAYOUT_PASS actual rendered hierarchy only, not Android measurement");return;
  }
  if(mode.equals("noime"))noIme=true;
  field.setText(mode.equals("invalid")?"Home\n\nEnd":mode.equals("empty")?"":"Home\nDaily rewards");
  if(mode.equals("cancel")){
   views.get("relation-cancel").click();
   check(h.db.confirms==0&&h.jobs.isEmpty()&&h.db.stored.equals(List.of("Old")),"cancel write");
  }else{
   if(mode.equals("failure")||mode.equals("failure-cancel"))h.db.fail=true;
   views.get("relation-save").click();
   if(mode.equals("invalid")){
    check(h.jobs.isEmpty()&&h.db.confirms==0&&events.isEmpty()&&r.active()
      &&views.get("relation-save").enabled&&((TextView)views.get("relation-validation")).text.length()>0,"invalid kept open");return;
   }
   check(h.jobs.size()==1&&!views.get("relation-save").enabled&&!views.get("relation-cancel").enabled&&events.isEmpty(),"no premature exit");
   views.get("relation-save").click();views.get("relation-cancel").click();
   check(h.jobs.size()==1&&events.isEmpty(),"one attempt");
   if(mode.equals("detach")){r.root.detach();field.attached=false;}
   h.flush();
   if(mode.equals("detach")){
    check(events.isEmpty()&&backs[0]==0&&h.db.last.closed&&h.db.stored.equals(List.of("Old")),"retired callback");return;
   }
   if(mode.equals("failure")||mode.equals("failure-cancel")){
    check(events.isEmpty()&&backs[0]==0&&r.active()&&h.db.stored.equals(List.of("Old"))
      &&views.get("relation-cancel").enabled&&h.db.last.closed,"failure kept visible");
    if(mode.equals("failure"))return;
    views.get("relation-cancel").click();
   }else check(h.db.confirms==1&&h.db.stored.equals(mode.equals("empty")?List.of():List.of("Home","Daily rewards")),"exact ordered values");
  }
  check(events.equals(noIme?List.of("clear","back"):List.of("hide","clear","back")),"IME exit order");
  check(backs[0]==1&&!r.active()&&r.plan==null&&h.db.last.closed,"closed once");
  System.out.println("PASS "+mode+" "+events);
 }
}
'''

def relation_caller_contract(source):
    """Execute the actual restore-cancel assertion and its current lookup caller."""
    import ast,copy
    tree=ast.parse(source)
    native=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_native_ui')
    funcs={n.name:n for n in native.body if isinstance(n,ast.FunctionDef)}
    created={n.args[0].value for n in ast.walk(native) if isinstance(n,ast.Call)
             and isinstance(n.func,ast.Name) and n.func.id=='add_todo' and n.args and isinstance(n.args[0],ast.Constant)}
    assert created=={'Buy milk','Walk outside','After backup'},created
    created.update(n.args[0].value for n in ast.walk(native) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Name) and n.func.id=='named_todo' and n.args and isinstance(n.args[0],ast.Constant))
    blind=[n for n in ast.walk(native) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='find'
           and any(k.arg=='text' and isinstance(k.value,ast.Constant) and k.value.value in created for k in n.keywords)]
    assert not blind,'viewport-blind positive todo lookup'
    label='canceling SAF restore preview makes no database write'
    callers=[n for n in ast.walk(native) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ok'
             and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value==label]
    assert len(callers)==1,'restore-cancel assertion omitted'
    lookup=funcs['named_todo']
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='reveal_todo' for n in ast.walk(lookup)), 'bounded lookup omitted'
    # Both the native callsite and nested named_todo body execute, not a parallel reimplementation.
    import xml.etree.ElementTree as ET
    def run(visible,confirmation=False):
        clock=[0.0];offset=[0];gestures=[]
        def nodes():
            clock[0]+=0.1
            xml='<hierarchy><node class="android.widget.ScrollView" content-desc="todo-list-scroll" package="p" enabled="true" bounds="[18,288][302,522]"/>'
            if visible and offset[0]>0:
                xml+='<node text="After backup" class="android.widget.CheckBox" content-desc="todo-exact" package="p" enabled="true" bounds="[26,293][178,345]"/>'
            return list(ET.fromstring(xml+'</hierarchy>').iter('node'))
        def swipe(x,y,x2,end):
            gestures.append((x,y,x2,end));offset[0]=max(0,offset[0]+(1 if y>end else -1))
        def reveal(*args,**kwargs):
            return reveal_todo(*args,**kwargs,clock=lambda:clock[0])
        def ok(value,message):assert value,message
        env=dict(reveal_todo=reveal,nodes=nodes,swipe_summary=swipe,PKG='p',absent=lambda s:not confirmation,ok=ok)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(lookup)],type_ignores=[])),'actual-named-todo','exec'),env)
        expr=ast.Expression(copy.deepcopy(callers[0]));ast.fix_missing_locations(expr)
        eval(compile(expr,'actual-restore-cancel','eval'),env)
        assert gestures and offset[0]>0,'actual caller did not navigate'
    run(True)
    for visible,confirmation in ((False,False),(True,True)):
        try:run(visible,confirmation)
        except (AssertionError,RuntimeError):pass
        else:raise AssertionError('restore-cancel negative survived')
    assert any(isinstance(n,ast.Constant) and n.value=='cancelled restore leaves exact new todo and old state independent'
               for n in ast.walk(native)),'independent DB assertion omitted'
    return tree

def relation_ui_selftest(original_only=False):
    import ast,copy,hashlib,subprocess,tempfile
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    java=(root/'src/main/java/com/supercubegame/pockettodo/ActivitiesScreen.java')
    source=Path(__file__).read_text()
    def once(s,a,b):
        assert s.count(a)==1,('mutation anchor',a)
        return s.replace(a,b,1)
    with tempfile.TemporaryDirectory(prefix='relation-actual-') as td:
        d=Path(td);(d/'ExtractRelation.java').write_text(RELATION_EXTRACTOR)
        def call(cmd):return subprocess.run(cmd,capture_output=True,text=True,timeout=40)
        def good(p):assert p.returncode==0,(p.stdout,p.stderr)
        good(call(['java','-m','jdk.compiler/com.sun.tools.javac.Main',str(d/'ExtractRelation.java')]))
        good(call(['java','-cp',str(d),'ExtractRelation',str(java),str(d)]))
        actual=(d/'RelationEditor.txt').read_text();caller=(d/'renderDetail.ast').read_text()
        def wiring(c):
            assert 'new RelationEditor(host, id, d.title, false, d.path, this::load)' in c,'path editor identity'
            assert 'new RelationEditor(host, id, d.title, true, d.tags, this::load)' in c,'tag editor identity'
            assert 'pathEditor.open(pathEdit)' in c and 'tagEditor.open(tagEdit)' in c,'actual open wiring'
        wiring(caller)
        def compile_actual(code):
            (d/'RelationHarness.java').write_text(RELATION_HARNESS.replace('/*ACTUAL*/',code))
            good(call(['java','-m','jdk.compiler/com.sun.tools.javac.Main',str(d/'RelationHarness.java')]))
        def scenario(name,passed=True,reason='IME exit order'):
            p=call(['java','-cp',str(d),'RelationHarness',name])
            if passed:good(p)
            else:assert p.returncode!=0 and reason in p.stderr,(name,p.stdout,p.stderr)
        if original_only:
            compile_actual(actual);scenario('invalid');scenario('success',False);scenario('cancel',False)
            try:relation_caller_contract(source)
            except AssertionError as e:assert 'viewport-blind' in str(e)
            else:raise AssertionError('original caller unexpectedly passed')
            print('RELATION_ORIGINAL_RED actual_class_sha256='+hashlib.sha256(actual.encode()).hexdigest()+' success_RED cancel_RED invalid_control_PASS restore_caller_RED ANDROID_DOUBLES_ONLY')
            return
        cases=('success','cancel','invalid','empty','failure','failure-cancel','detach','finishing','destroyed','stale','noime','tags','layout','layout-tags')
        compile_actual(actual)
        for name in cases:scenario(name)
        mutations=[
            ('success-exit', 'if(present){dismissInput(input);back.run();}', 'if(present){back.run();}','success'),
            ('cancel-exit', '{dismissInput(input);close();back.run();}', '{close();back.run();}','cancel'),
            ('hide-call', 'ime.hideSoftInputFromWindow(input.getWindowToken(),0);', '{}','success'),
            ('focus-call', 'input.clearFocus();', '{}','success'),
            ('wrong-order', 'if(present){dismissInput(input);back.run();}', 'if(present){back.run();dismissInput(input);}','success'),
        ]
        for name,a,b,probe in mutations:
            compile_actual(once(actual,a,b));scenario('invalid')
            scenario(probe,False,'detached token' if name=='wrong-order' else 'IME exit order')
        for a,b,reason in [
            ('fields.addView(save,new LinearLayout.LayoutParams(-1,-2))','root.addView(save,new LinearLayout.LayoutParams(-1,-2))','one whole editor viewport'),
            ('fields.addView(identity)','root.addView(identity)','one whole editor viewport'),
            ('scroll.setContentDescription("relation-editor-scroll")','scroll.setContentDescription("wrong-scroll")','viewport identity'),
        ]:
            compile_actual(once(actual,a,b));scenario('layout',False,reason)
        for needle in ('pathEditor.open(pathEdit)','tagEditor.open(tagEdit)'):
            mutant=once(caller,needle,'System.nanoTime()')
            try:wiring(mutant)
            except AssertionError:pass
            else:raise AssertionError('editor caller omission survived')
        relation_caller_contract(source)
        # The previous direct-find bug and deleted whole assertions must both fail the same contract.
        mutant=once(source,"\n        ok(named_todo('After backup') is not None and absent('确认恢复'),","\n        ok(find(text='After backup') is not None and absent('确认恢复'),")
        try:relation_caller_contract(mutant)
        except AssertionError as e:assert 'viewport-blind' in str(e)
        else:raise AssertionError('original direct-find survived')
        parsed=ast.parse(source)
        class Omit(ast.NodeTransformer):
            def visit_Call(self,n):
                if isinstance(n.func,ast.Name) and n.func.id=='ok' and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='canceling SAF restore preview makes no database write':
                    return ast.Constant(None)
                return self.generic_visit(n)
        try:relation_caller_contract(ast.unparse(ast.fix_missing_locations(Omit().visit(parsed))))
        except AssertionError as e:assert 'assertion omitted' in str(e)
        else:raise AssertionError('whole restore assertion omission survived')
        def registered(s):
            p=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='parser_selftest')
            assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='relation_ui_selftest' for n in ast.walk(p)),'registration omitted'
        registered(source)
        try:registered(once(source,'    relation_ui_selftest()\n','    pass\n'))
        except AssertionError:pass
        else:raise AssertionError('selftest omission survived')
        print('RELATION_UI_HOST cases='+str(len(cases))+' witnessed_java_mutants='+str(len(mutations))+' editor_caller_omissions=2 restore_positive=1 restore_negatives=2 original_direct_find_RED=1 whole_assertion_omission=1 registration_omission=1 PASS ACTUAL_SOURCE_ANDROID_DB_IME_DOUBLES_NOT_DEVICE')


def relation_control(nodes,swipe,package,description,*,clock=time.monotonic):
    """One bounded viewport search; no typing, back key or command replay."""
    deadline=clock()+20
    for direction in (1,-1):
        for attempt in range(9):
            if clock()>=deadline:raise AssertionError('relation navigation deadline')
            frame=nodes()
            scrolls=[n for n in frame if n.get('package')==package and
                     n.get('class')=='android.widget.ScrollView' and
                     n.get('content-desc')=='relation-editor-scroll' and n.get('enabled')=='true']
            assert len(scrolls)==1,'relation viewport identity'
            def box(n):
                raw=n.get('bounds','')
                assert re.fullmatch(r'\[-?\d+,-?\d+\]\[-?\d+,-?\d+\]',raw),'relation bounds syntax'
                return tuple(map(int,re.findall(r'-?\d+',raw)))
            x1,y1,x2,y2=box(scrolls[0])
            assert x2-x1>=16 and y2-y1>=16,'relation viewport collapsed'
            targets=[n for n in frame if n.get('package')==package and n.get('content-desc')==description]
            assert len(targets)<=1,'duplicate relation target'
            if targets:
                n=targets[0];a,b,c,d=box(n)
                cls='android.widget.EditText' if description in ('活动路径','活动标签') else 'android.widget.Button'
                minimum=16 if cls.endswith('EditText') else 40
                if n.get('class')==cls and n.get('enabled')=='true' and n.get('clickable')=='true' and x1<=a<c<=x2 and y1<=b<d<=y2 and d-b>=minimum:
                    return n
            if attempt==8:break
            x=(x1+x2)//2;top=y1+max(2,(y2-y1)//5);bottom=y2-max(2,(y2-y1)//5)
            swipe(x,bottom if direction==1 else top,x,top if direction==1 else bottom)
    raise AssertionError('relation target absent or clipped: '+description)

def relation_input(nodes,package,expected,*,clock=time.monotonic,sleep=time.sleep):
    """Observe the exact focused field; fail closed without retrying input."""
    deadline=clock()+20;last=[]
    while clock()<deadline:
        last=nodes()
        fields=[n for n in last if n.get('package')==package and n.get('content-desc')=='活动路径']
        assert len(fields)<=1,'duplicate relation input'
        if fields:
            n=fields[0]
            scrolls=[v for v in last if v.get('package')==package and v.get('class')=='android.widget.ScrollView' and v.get('content-desc')=='relation-editor-scroll']
            if len(scrolls)==1:
                def box(v):return tuple(map(int,re.findall(r'-?\d+',v.get('bounds',''))))
                a=box(n);b=box(scrolls[0])
                if len(a)==len(b)==4 and a[2]>a[0] and a[3]-a[1]>=16 and b[0]<=a[0]<a[2]<=b[2] and b[1]<=a[1]<a[3]<=b[3] and n.get('class')=='android.widget.EditText' and n.get('focused')=='true' and n.get('enabled')=='true' and n.get('text')==expected:
                    print('RELATION_INPUT_OBSERVED '+repr(n.attrib),flush=True)
                    return n
        sleep(.1)
    raise AssertionError('relation focused exact input missing: '+repr(expected)+' actual='+repr([n.attrib for n in last]))

def enter_relation_path(nodes,swipe,package,tap_node,type_text,shell):
    tap_node(relation_control(nodes,swipe,package,'活动路径'))
    relation_input(nodes,package,'')
    type_text('Home');relation_input(nodes,package,'Home')
    shell('input','keyevent','KEYCODE_ENTER');relation_input(nodes,package,'Home\n')
    type_text('Daily rewards');relation_input(nodes,package,'Home\nDaily rewards')
    tap_node(relation_control(nodes,swipe,package,'relation-save'))

def relation_input_selftest():
    """Execute current caller/helpers with synthetic frames; never Android proof."""
    import ast,copy,inspect,xml.etree.ElementTree as ET
    def exercise(mode,caller=enter_relation_path):
        tick=[0.0];state=dict(focused=False,text='',scrolled=False);commands=[];saved=[]
        def clock():tick[0]+=.05;return tick[0]
        def sleep(seconds):tick[0]+=seconds
        def node(**a):return ET.Element('node',dict(package='p',enabled='true',clickable='true',**a))
        def nodes():
            tick[0]+=.1
            if mode=='missing-scroll':return []
            viewport='[18,198][302,343]' if state['focused'] else '[18,198][302,578]'
            rows=[node(**{'class':'android.widget.ScrollView','content-desc':'relation-editor-scroll','bounds':viewport})]
            if mode=='collapsed':rows[0].set('bounds','[18,255][302,255]')
            if mode=='duplicate-scroll':rows.append(copy.deepcopy(rows[0]))
            if state['scrolled']:
                if mode!='missing-save':
                    rows.append(node(**{'class':'android.widget.Button','content-desc':'relation-save','bounds':'[18,240][302,288]'}))
            else:
                rows.append(node(**{'class':'android.widget.EditText','content-desc':'活动路径','text':state['text'],'focused':str(state['focused'] and mode!='focus').lower(),'bounds':'[18,218][302,302]'}))
            return rows
        def tap(n):
            if n.get('content-desc')=='relation-save':
                saved.append(state['text']);return
            state['focused']=True
        def swipe(x,y,x2,y2):
            assert 18<x<302 and x==x2 and 198<y<343 and 198<y2<343,'gesture left viewport'
            state['scrolled']=True
        def type_text(value):
            commands.append(value)
            if mode==('home' if value=='Home' else 'second'):return
            state['text']+=value
        def shell(*args):
            assert args==('input','keyevent','KEYCODE_ENTER')
            commands.append('ENTER')
            if mode!='enter':state['text']+='\n'
        env=dict(caller.__globals__)
        env['relation_control']=lambda *a:relation_control(*a,clock=clock)
        env['relation_input']=lambda *a:relation_input(*a,clock=clock,sleep=sleep)
        import types
        actual=types.FunctionType(caller.__code__,env)
        failure=None
        try:actual(nodes,swipe,'p',tap,type_text,shell)
        except AssertionError as e:failure=e
        if mode=='ok':
            assert failure is None,repr(failure)
            assert commands==['Home','ENTER','Daily rewards'] and saved==['Home\nDaily rewards']
        else:
            assert failure is not None and not saved,('negative escaped',mode,commands,saved)
            expected={'focus':[],'home':['Home'],'enter':['Home','ENTER'],'second':['Home','ENTER','Daily rewards']}
            if mode in expected:assert commands==expected[mode],('late refusal',mode,commands)
        return failure
    for mode in ('ok','focus','home','enter','second','missing-scroll','duplicate-scroll','collapsed','missing-save'):
        exercise(mode)
    original=inspect.getsource(enter_relation_path)
    for value,mode in (("''",'focus'),("'Home'",'home'),("'Home\\n'",'enter'),("'Home\\nDaily rewards'",'second')):
        needle='relation_input(nodes,package,'+value+')'
        assert original.count(needle)==1,needle
        source=original.replace(needle,'None',1);env=dict(globals());exec(source,env)
        exercise('ok',env['enter_relation_path'])
        try:exercise(mode,env['enter_relation_path'])
        except AssertionError:pass
        else:raise AssertionError('input observation mutant survived '+mode)
    source=Path(__file__).read_text();tree=ast.parse(source)
    def wiring(t):
        native=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_native_ui')
        calls=[n for n in ast.walk(native) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='enter_relation_path']
        assert len(calls)==1 and [ast.unparse(a) for a in calls[0].args]==['nodes','swipe_summary','PKG','tap_node','type_text','shell'],'relation actual caller omitted'
        labels={n.value for n in ast.walk(native) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        assert 'ordered multiline manual path displays without collapse' in labels,'visible path assertion omitted'
        assert 'independent SQLite read preserves path order' in labels,'exact DB assertion omitted'
        parser=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='parser_selftest')
        assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='relation_input_selftest' for n in ast.walk(parser)),'relation selftest omitted'
    wiring(tree)
    for name in ('enter_relation_path','relation_input_selftest'):
        t=copy.deepcopy(tree)
        for n in ast.walk(t):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name:n.func.id='omitted'
        try:wiring(t)
        except AssertionError:pass
        else:raise AssertionError('whole caller omission survived '+name)
    for label in ('ordered multiline manual path displays without collapse','independent SQLite read preserves path order'):
        t=copy.deepcopy(tree)
        for n in ast.walk(t):
            if isinstance(n,ast.Constant) and n.value==label:n.value='omitted'
        try:wiring(t)
        except AssertionError:pass
        else:raise AssertionError('assertion omission survived')
    print('RELATION_INPUT_HOST positive=1 negatives=8 witnessed_observation_mutants=4 caller_assertion_omissions=4 PASS SYNTHETIC_FRAMES_NOT_ANDROID')


def reveal_activity(read_nodes, swipe, package, *, title=None, identity=None, clock=time.monotonic):
    """One20s bounded navigation; no writes, Back, typing or input retries."""
    assert (title is None) != (identity is None), 'one activity selector required'
    if identity is not None:
        assert re.fullmatch(r'activity-[1-9]\d*',identity), 'invalid requested activity identity'
    deadline=clock()+20
    history=[]
    def bounds(node):
        match=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',node.get('bounds',''))
        assert match, 'malformed activity bounds'
        a,b,c,d=map(int,match.groups())
        assert c>a and d>b, 'empty activity bounds'
        return a,b,c,d
    for direction in (-1,1):
        previous=None
        for attempt in range(9):
            assert clock()<deadline, 'activity navigation deadline; history='+repr(history)
            frame=list(read_nodes())
            assert clock()<deadline, 'activity observation exceeded deadline'
            views=[n for n in frame if n.get('content-desc')=='activity-list-scroll']
            assert len(views)==1, 'missing/duplicate activity viewport'
            view=views[0]
            assert view.get('package')==package and view.get('class')=='android.widget.ScrollView' and view.get('enabled')=='true', 'invalid activity viewport owner/type'
            left,top,right,bottom=bounds(view)
            assert right-left>=16 and bottom-top>=48, 'collapsed activity viewport'
            matches=[n for n in frame if (n.get('text')==title if title is not None else n.get('content-desc')==identity)]
            assert len(matches)<=1, 'ambiguous activity selector'
            if matches:
                n=matches[0]
                assert n.get('package')==package and n.get('class')=='android.widget.Button' and n.get('enabled')=='true' and n.get('clickable')=='true', 'invalid activity target owner/type/state'
                found=n.get('content-desc','')
                assert re.fullmatch(r'activity-[1-9]\d*',found), 'invalid activity identity'
                a,b,c,d=bounds(n)
                if left<=a<c<=right and top<=b<d<=bottom and d-b>=40:
                    print('ACTIVITY_VIEWPORT_FOUND '+json.dumps(dict(title=n.get('text'),identity=found,bounds=[a,b,c,d],history=history),ensure_ascii=False),flush=True)
                    return n
            signature=tuple(tuple(n.get(k,'') for k in ('package','content-desc','text','bounds','class')) for n in frame)
            if signature==previous:break
            previous=signature
            if attempt<8:
                x,start,_,end=summary_gesture((left,top,right,bottom))
                if direction==-1:start,end=end,start
                history.append(dict(direction=direction,attempt=attempt,viewport=[left,top,right,bottom],gesture=[x,start,x,end]))
                swipe(x,start,x,end)
    raise AssertionError('activity absent or clipped at navigation bound; history='+repr(history))

def verify_first_activity(rows, identity):
    """Independent stopped-process SQLite rows, not success-toast inference."""
    assert type(identity) is int and identity>1, 'new activity identity required'
    matches=[row for row in rows if row[0]==identity]
    assert matches==[(identity,1,None,'Image first',0)], 'saved activity identity/category/title/archive differs'
    assert [row[0] for row in rows if row[3]=='Image first']==[identity], 'new activity title is ambiguous'


def activity_navigation_selftest():
    import ast,copy,inspect,types
    package='fixture.activity'
    view={'package':package,'class':'android.widget.ScrollView','enabled':'true','content-desc':'activity-list-scroll','bounds':'[18,279][302,578]'}
    target={'package':package,'class':'android.widget.Button','enabled':'true','clickable':'true','text':'Image first','content-desc':'activity-2','bounds':'[30,480][290,528]'}
    def exercise(fn,mode,by_id=False):
        offset=0;ticks=0;gestures=[]
        def read():
            v=dict(view);n=dict(target)
            if mode=='missing-view':return []
            if mode=='foreign-view':v['package']='foreign'
            if mode=='wrong-view-class':v['class']='android.widget.LinearLayout'
            if mode=='disabled-view':v['enabled']='false'
            if mode=='bad-bounds':v['bounds']='broken'
            if mode=='collapsed':v['bounds']='[18,341][302,343]'
            if mode=='empty-view':v['bounds']='[18,279][18,578]'
            if mode=='duplicate-view':return [v,v]
            if mode=='absent' or (mode=='below' and offset==0):return [v]
            if mode=='clipped' and offset==0:n['bounds']='[30,570][290,578]'
            if mode=='outside':n['bounds']='[30,600][290,648]'
            if mode=='foreign-target':n['package']='foreign'
            if mode=='wrong-class':n['class']='android.widget.TextView'
            if mode=='disabled':n['enabled']='false'
            if mode=='unclickable':n['clickable']='false'
            if mode=='bad-id':n['content-desc']='activity-0'
            if mode=='wrong-id':n['content-desc']='activity-3'
            if mode=='duplicate-target':return [v,n,n]
            return [v,n]
        def swipe(x,a,y,b):
            nonlocal offset
            assert 18<x<302 and x==y and 279<a<578 and 279<b<578, 'gesture outside activity viewport'
            gestures.append((x,a,y,b));offset=max(0,offset+(1 if a>b else -1))
            assert len(gestures)<=16, 'unbounded activity gestures'
        def clock():
            nonlocal ticks
            ticks+=1
            return ticks*21 if mode=='deadline' else ticks*.001
        args={'identity':'activity-2'} if by_id else {'title':'Image first'}
        result=fn(read,swipe,package,clock=clock,**args)
        if mode in ('ready','below','clipped'):assert result==target
        if mode in ('below','clipped'):assert len(gestures)==2
        return result
    for mode in ('ready','below','clipped'):
        exercise(reveal_activity,mode);exercise(reveal_activity,mode,True)
    negatives=('missing-view','foreign-view','wrong-view-class','disabled-view','bad-bounds','collapsed','empty-view','duplicate-view','absent','outside','foreign-target','wrong-class','disabled','unclickable','bad-id','duplicate-target','deadline')
    for mode in negatives:
        try:exercise(reveal_activity,mode)
        except AssertionError:pass
        else:raise AssertionError('activity negative survived '+mode)
    try:exercise(reveal_activity,'wrong-id',True)
    except AssertionError:pass
    else:raise AssertionError('same title substituted wrong identity')
    source=inspect.getsource(reveal_activity)
    mutations=[
        ("view.get('package')==package","True",'foreign-view'),
        ("n.get('class')=='android.widget.Button'","True",'wrong-class'),
        ("n.get('clickable')=='true'","True",'unclickable'),
        ("re.fullmatch(r'activity-[1-9]\\d*',found)","True",'bad-id'),
        ("left<=a<c<=right and top<=b<d<=bottom and d-b>=40","True",'outside'),
        ("clock()<deadline","True",'deadline'),
    ]
    for old,new,mode in mutations:
        assert old in source
        env=dict(globals());exec(compile(source.replace(old,new),'<activity-mutant>','exec'),env)
        exercise(env['reveal_activity'],'ready')
        exercise(env['reveal_activity'],mode)
    rows=[(1,1,None,'Daily reward',0),(2,1,None,'Image first',0)]
    verify_first_activity(rows,2)
    badrows=[rows[:1],rows+[rows[1]],rows+[(3,1,None,'Image first',0)]]
    for i,value in [(0,3),(1,2),(2,4),(3,'wrong'),(4,1)]:
        row=list(rows[1]);row[i]=value;badrows.append([rows[0],tuple(row)])
    for rows_bad in badrows:
        try:verify_first_activity(rows_bad,2)
        except AssertionError:pass
        else:raise AssertionError('activity saved-row negative survived')
    dbsource=inspect.getsource(verify_first_activity)
    for needle,bad in [
        ("assert matches==[(identity,1,None,'Image first',0)], 'saved activity identity/category/title/archive differs'",badrows[0]),
        ("assert [row[0] for row in rows if row[3]=='Image first']==[identity], 'new activity title is ambiguous'",badrows[2]),
    ]:
        # Each omission must survive good rows and admit its specific bad rows.
        assert needle in dbsource
        env=dict(globals());exec(dbsource.replace(needle,'pass',1),env)
        env['verify_first_activity'](rows,2)
        witness=bad if bad is not badrows[0] else [(1,1,None,'Daily reward',0),(2,2,None,'Image first',0)]
        env['verify_first_activity'](witness,2)
    module=ast.parse(Path(__file__).read_text())
    def wiring(tree):
        funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        native=funcs['_verify_native_ui']
        calls=[ast.unparse(n) for n in ast.walk(native) if isinstance(n,ast.Call)]
        assert "reveal_activity(nodes, swipe_summary, PKG, title='Image first')" in calls, 'activity creation lookup omitted'
        screen=next(n for n in ast.walk(native) if isinstance(n,ast.FunctionDef) and n.name=='first_screen')
        assert "tap_node(reveal_activity(nodes, swipe_summary, PKG, identity=first_desc))" in [ast.unparse(n) for n in ast.walk(screen) if isinstance(n,ast.Call)], 'activity stable navigation omitted'
        assert "verify_first_activity(first_base['activities'], first_activity)" in calls, 'saved activity assertion omitted'
        assert "activity_navigation_selftest()" in [ast.unparse(n) for n in ast.walk(funcs['parser_selftest']) if isinstance(n,ast.Call)], 'activity tests not registered'
        assert "find(text='Image first')" not in calls and "touch(first_desc)" not in calls, 'unbounded first activity lookup remains'
    wiring(module)
    omissions=0
    for call in ("reveal_activity(nodes, swipe_summary, PKG, title='Image first')","tap_node(reveal_activity(nodes, swipe_summary, PKG, identity=first_desc))","verify_first_activity(first_base['activities'], first_activity)","activity_navigation_selftest()"):
        class Remove(ast.NodeTransformer):
            def visit_Call(self,n):
                if ast.unparse(n)==call:return ast.Constant(None)
                return self.generic_visit(n)
        mutant=Remove().visit(copy.deepcopy(module))
        try:wiring(mutant)
        except AssertionError:omissions+=1
        else:raise AssertionError('activity whole call omission survived')
    # Execute actual first_screen, not a parallel handwritten caller.
    native=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_native_ui')
    screen=next(n for n in ast.walk(native) if isinstance(n,ast.FunctionDef) and n.name=='first_screen')
    events=[]
    def reveal(*a,**kw):
        assert kw=={'identity':'activity-2'};events.append('identity');return target
    env=dict(start=lambda:events.append('start'),tap=lambda s:events.append(s),ready=lambda:None,
             tap_node=lambda n:events.append(n['content-desc']),reveal_activity=reveal,nodes=lambda:[],
             swipe_summary=lambda *a:None,PKG=package,first_desc='activity-2')
    exec(compile(ast.Module(body=[screen],type_ignores=[]),'<actual-first-screen>','exec'),env);env['first_screen']()
    assert events==['start','活动','identity','activity-2','笔记']
    print('ACTIVITY_NAVIGATION_HOST positive=6 negative='+str(len(negatives)+1)+' witnessed_navigation_mutants='+str(len(mutations))+' saved_row_negatives='+str(len(badrows))+' saved_row_omissions=2 caller_omissions='+str(omissions)+' PASS SYNTHETIC_GEOMETRY_NOT_ANDROID')


DERIVE_OVERSIZE_MESSAGE='原图过大或格式不支持：裁剪/遮挡仅支持不超过 100 万像素、单边 2048 的 PNG/JPEG；原图未改动'
DERIVE_ROTATED_MESSAGE='原图带旋转或 EXIF 方向信息，需先在相册里转正并另存，暂不支持裁剪或遮挡；原图未改动'
DERIVE_EXIF_UNCONFIRMED_MESSAGE='无法确认原图的 EXIF 方向，暂不支持裁剪或遮挡；原图未改动'
DERIVE_CHANGED_MESSAGE='笔记已在别处变化，请关闭后重新选择；原图未改动'
DERIVE_SAVE_FAILED_MESSAGE='保存未完成：笔记和原图未改动，请重新打开后再试'
DERIVE_PREVIEW_GENERIC_MESSAGE='预览失败：原图可能已变化，请重新选择'
HARDENING_LABELS=[
 'oversize source with a legal selection names the real pixel limit instead of generic preview failure',
 'oversize source refusal and cancel leave every table and every original byte unchanged',
 'late derivative save failure shows the exact visible message',
 'late derivative save failure and cancel leave every table and every original byte unchanged',
 'JPEG source imports into the first note as one exact block with exact private bytes and registry',
 'JPEG derivative dialog shows actual decoded JPEG dimensions with empty selection',
 'JPEG touch crop and opaque mask save one derived PNG recording the exact JPEG original',
 'independent ImageIO decode proves exact cropped pixels and opaque mask for the JPEG source',
 'JPEG original derived PNG and every table survive stopped-process restart exactly',
]
def jpeg_with_orientation(jpeg,orientation):
    """Insert one big-endian EXIF primary-IFD orientation APP1 right after SOI."""
    import struct
    assert jpeg[:2]==b'\xff\xd8' and orientation in range(1,9)
    tiff=b'MM\x00*\x00\x00\x00\x08'+struct.pack('>H',1)+struct.pack('>HHIHH',274,3,1,orientation,0)+b'\x00\x00\x00\x00'
    payload=b'Exif\x00\x00'+tiff
    return jpeg[:2]+b'\xff\xe1'+struct.pack('>H',len(payload)+2)+payload+jpeg[2:]
def jpeg_orientation_model(b):
    """Port of ShareExporter.jpegOrientation; refusal text equals the Java IOException text."""
    def u16(p,little):return (b[p]|(b[p+1]<<8)) if little else ((b[p]<<8)|b[p+1])
    def u32(p,little):return ((u16(p+2,True)<<16)|u16(p,True)) if little else ((u16(p,False)<<16)|u16(p+2,False))
    if len(b)<4 or b[0]!=255 or b[1]!=216:raise IOError('Invalid JPEG')
    p=2;exif=0
    while p<len(b):
        if b[p]!=255:raise IOError('Invalid JPEG marker')
        p+=1
        while p<len(b) and b[p]==255:p+=1
        if p>=len(b):raise IOError('Truncated JPEG marker')
        marker=b[p];p+=1
        if marker in (218,217):return
        if marker==1 or 208<=marker<=215:continue
        if marker==0 or marker==216 or p>len(b)-2:raise IOError('Invalid JPEG segment')
        n=u16(p,False)
        if n<2 or n>len(b)-p:raise IOError('Truncated JPEG segment')
        start=p+2;end=p+n
        if marker==225 and end-start>=6 and b[start:start+6]==b'Exif\x00\x00':
            exif+=1
            if exif!=1:raise IOError('Ambiguous JPEG EXIF')
            t=start+6
            if end-t<8:raise IOError('Truncated TIFF header')
            little=b[t:t+2]==b'II'
            if not little and b[t:t+2]!=b'MM':raise IOError('Invalid TIFF byte order')
            if u16(t+2,little)!=42:raise IOError('Invalid TIFF header')
            offset=u32(t+4,little)
            if offset<8 or offset>end-t-2:raise IOError('Invalid primary IFD')
            ifd=t+offset;count=u16(ifd,little)
            if ifd+2+12*count+4>end:raise IOError('Truncated primary IFD')
            seen=False;q=ifd+2
            for _ in range(count):
                if u16(q,little)==274:
                    if seen or u16(q+2,little)!=3 or u32(q+4,little)!=1:raise IOError('Ambiguous primary orientation')
                    seen=True
                    if u16(q+8,little)!=1:raise IOError('Image orientation must be normalized before editing')
                q+=12
            if not seen:raise IOError('EXIF orientation cannot be confirmed')
        p=end
    raise IOError('Incomplete JPEG header')
def derivative_failure_model(message,saving):
    """Port of NoteEditorScreen.derivativeFailure; unknown failures stay generic."""
    m=message or ''
    if 'Only PNG/JPEG up to 1 million pixels' in m:return DERIVE_OVERSIZE_MESSAGE
    if 'must be normalized' in m:return DERIVE_ROTATED_MESSAGE
    if 'EXIF' in m or 'orientation' in m:return DERIVE_EXIF_UNCONFIRMED_MESSAGE
    if 'Database changed' in m:return DERIVE_CHANGED_MESSAGE
    return DERIVE_SAVE_FAILED_MESSAGE if saving else DERIVE_PREVIEW_GENERIC_MESSAGE
def derivative_java_contract(source):
    """Static contract for the two failure paths in NoteEditorScreen source text."""
    import re
    head='static String derivativeFailure(Throwable failure,boolean saving){'
    assert source.count(head)==1,'single derivativeFailure mapping'
    a=source.index(head);b=source.index('\n    }\n',a)
    literals=re.findall(r'"((?:[^"\\]|\\.)*)"',source[a:b])
    expected=['','Only PNG/JPEG up to 1 million pixels',DERIVE_OVERSIZE_MESSAGE,'must be normalized',DERIVE_ROTATED_MESSAGE,
              'EXIF','orientation',DERIVE_EXIF_UNCONFIRMED_MESSAGE,'Database changed',DERIVE_CHANGED_MESSAGE,
              DERIVE_SAVE_FAILED_MESSAGE,DERIVE_PREVIEW_GENERIC_MESSAGE]
    assert literals==expected,'Java message mapping differs from native expectations: '+repr(literals)
    for needle in ('prepareFailure.set(failure);throw failure;','derivativeFailure(prepareFailure.get(),false)',
                   'saveFailure.set(failure);throw failure;','host.message(derivativeFailure(saveFailure.get(),true),true)'):
        assert source.count(needle)==1,'missing derivative failure wiring: '+needle
    assert source.count(DERIVE_PREVIEW_GENERIC_MESSAGE)==1,'generic preview failure only remains the fallback'
    assert 'ignored->{dialog.dismiss();load();},()->dialog.dismiss());' not in source,'silent save failure path remains'
def hardening_wiring_check(source):
    """The native stage must register exactly the declared checks outside the fixed ok() contract."""
    import ast
    tree=ast.parse(source)
    fn=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_native_ui']
    assert len(fn)==1,'native function present'
    calls=[n for n in ast.walk(fn[0]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='okh'
           and len(n.args)>1 and isinstance(n.args[1],ast.Constant)]
    seen=[n.args[1].value for n in sorted(calls,key=lambda n:(n.lineno,n.col_offset))]
    assert seen==HARDENING_LABELS,'hardening labels differ: '+repr(seen)
    text=ast.get_source_segment(source,fn[0])
    for needle in ('hard_checks.append(label)','derivative_hardening={','derivative_jpeg_tools()','make_derivative_jpeg(fixture_dir)',"'VerifyDerivative',jsrc"):
        assert text.count(needle)>=1,'missing hardening wiring '+needle

DERIVATIVE_JPEG_JAVA={'MakeDerivativeJpegs.java':'''import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.IIOImage;
import javax.imageio.ImageIO;
import javax.imageio.ImageWriteParam;
import javax.imageio.ImageWriter;
import javax.imageio.stream.ImageOutputStream;
public class MakeDerivativeJpegs {
 public static void main(String[] a) throws Exception {
  int w=640,h=320;
  BufferedImage img=new BufferedImage(w,h,BufferedImage.TYPE_INT_RGB);
  for(int y=0;y<h;y++)for(int x=0;x<w;x++){int v=40+(((x/16)*5+(y/16)*3)%9)*20;img.setRGB(x,y,(v<<16)|(v<<8)|v);}
  ImageWriter writer=ImageIO.getImageWritersByFormatName("jpeg").next();
  ImageWriteParam param=writer.getDefaultWriteParam();
  param.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);param.setCompressionQuality(1.0f);
  File file=new File(new File(a[0]),"pocket-derive-source.jpg");
  try(ImageOutputStream output=ImageIO.createImageOutputStream(file)){writer.setOutput(output);writer.write(null,new IIOImage(img,null,null),param);}
  writer.dispose();
  BufferedImage back=ImageIO.read(file);
  if(back==null||back.getWidth()!=w||back.getHeight()!=h||back.getType()!=BufferedImage.TYPE_3BYTE_BGR) throw new AssertionError("fixture must decode as a 3-channel 640x320 JPEG");
  for(int by=0;by<h/8;by++)for(int bx=0;bx<w/8;bx++){
   int first=back.getRGB(bx*8,by*8);
   if(((first>>16)&255)!=((first>>8)&255)||((first>>8)&255)!=(first&255)) throw new AssertionError("decoded fixture must stay neutral gray");
   for(int y=0;y<8;y++)for(int x=0;x<8;x++) if(back.getRGB(bx*8+x,by*8+y)!=first) throw new AssertionError("each 8x8 block must be flat so every JPEG decoder agrees");
  }
  System.out.println("DERIVATIVE_JPEG_FIXTURE_PASS 640x320 flat-gray-blocks");
 }
}
'''}
def derivative_jpeg_tools():
    """Compile the synthetic JPEG fixture writer and prove its flat-block decode before slow UI work."""
    helper=Path('build/ci-note-image-jpeg');helper.mkdir(parents=True,exist_ok=True)
    for name,text in DERIVATIVE_JPEG_JAVA.items():(helper/name).write_text(text)
    run(['javac','-d',helper]+[helper/name for name in DERIVATIVE_JPEG_JAVA],timeout=60)
    return 'JPEG_FIXTURE_WRITER_COMPILED'
def make_derivative_jpeg(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    helper=Path('build/ci-note-image-jpeg')
    made=run(['java','-Djava.awt.headless=true','-cp',helper,'MakeDerivativeJpegs',directory],timeout=60,capture=True).stdout.strip()
    assert made=='DERIVATIVE_JPEG_FIXTURE_PASS 640x320 flat-gray-blocks',made
    data=(directory/'pocket-derive-source.jpg').read_bytes()
    assert data[:2]==b'\xff\xd8' and len(data)<8*1024*1024 and 640*320<=1000000 and b'Exif\x00\x00' not in data[:64]
    jpeg_orientation_model(data)
    return data

def derivative_hardening_selftest():
    import inspect
    jfif=b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    base=jfif+b'\xff\xda\x00\x02'
    jpeg_orientation_model(base)
    for value in range(1,9):
        candidate=jpeg_with_orientation(base,value)
        assert candidate!=base and candidate[:2]==b'\xff\xd8'
        if value==1:jpeg_orientation_model(candidate)
        else:
            try:jpeg_orientation_model(candidate)
            except IOError as refusal:assert str(refusal)=='Image orientation must be normalized before editing',str(refusal)
            else:raise AssertionError('orientation '+str(value)+' was accepted')
    try:jpeg_orientation_model(jpeg_with_orientation(jpeg_with_orientation(base,1),1))
    except IOError as refusal:assert str(refusal)=='Ambiguous JPEG EXIF'
    else:raise AssertionError('duplicate EXIF accepted')
    source=inspect.getsource(jpeg_orientation_model)
    mutated=source.replace("if u16(q+8,little)!=1:raise IOError('Image orientation must be normalized before editing')","pass",1)
    assert mutated!=source
    scope={};exec(compile(mutated,'orientation-mutant','exec'),scope)
    scope['jpeg_orientation_model'](jpeg_with_orientation(base,6))
    cases=[('Only PNG/JPEG up to 1 million pixels and edge 2048 can be edited',False,DERIVE_OVERSIZE_MESSAGE),
           ('Image orientation must be normalized before editing',False,DERIVE_ROTATED_MESSAGE),
           ('PNG EXIF must be normalized before editing',False,DERIVE_ROTATED_MESSAGE),
           ('EXIF orientation cannot be confirmed',False,DERIVE_EXIF_UNCONFIRMED_MESSAGE),
           ('Ambiguous primary orientation',False,DERIVE_EXIF_UNCONFIRMED_MESSAGE),
           ('Database changed; review image again',False,DERIVE_CHANGED_MESSAGE),
           ('Image digest differs',False,DERIVE_PREVIEW_GENERIC_MESSAGE),
           ('Image digest differs',True,DERIVE_SAVE_FAILED_MESSAGE),
           (None,True,DERIVE_SAVE_FAILED_MESSAGE),(None,False,DERIVE_PREVIEW_GENERIC_MESSAGE)]
    for message,saving,expected in cases:assert derivative_failure_model(message,saving)==expected,(message,saving)
    messages=[DERIVE_OVERSIZE_MESSAGE,DERIVE_ROTATED_MESSAGE,DERIVE_EXIF_UNCONFIRMED_MESSAGE,DERIVE_CHANGED_MESSAGE,DERIVE_SAVE_FAILED_MESSAGE,DERIVE_PREVIEW_GENERIC_MESSAGE]
    assert len(set(messages))==6 and all(m for m in messages)
    java=(ROOT/'src/main/java/com/supercubegame/pockettodo/NoteEditorScreen.java').read_text(encoding='utf-8')
    derivative_java_contract(java)
    mutations=[
        ('prepareFailure.set(failure);throw failure;','throw failure;'),
        ('derivativeFailure(prepareFailure.get(),false)','"预览失败：原图可能已变化，请重新选择"'),
        ('saveFailure.set(failure);throw failure;','throw failure;'),
        ('host.message(derivativeFailure(saveFailure.get(),true),true);','/*silent*/'),
        ('if(m.contains("must be normalized"))return "'+DERIVE_ROTATED_MESSAGE+'";','if(false)return "'+DERIVE_ROTATED_MESSAGE+'";'),
        (DERIVE_OVERSIZE_MESSAGE,DERIVE_OVERSIZE_MESSAGE+'!'),
        ('()->{dialog.dismiss();load();host.message(derivativeFailure(saveFailure.get(),true),true);}','()->dialog.dismiss()'),
    ]
    for old,new in mutations:
        assert java.count(old)>=1,old
        mutant=java.replace(old,new,1)
        try:derivative_java_contract(mutant)
        except AssertionError:pass
        else:raise AssertionError('Java contract survived mutation '+old[:60])
    gate=(ROOT/'tools/emulator_gate.py').read_text(encoding='utf-8')
    hardening_wiring_check(gate)
    first=HARDENING_LABELS[0]
    index=gate.rindex("'"+first+"'")
    broken=gate[:index]+"'"+first+" '"+gate[index+len(first)+2:]
    try:hardening_wiring_check(broken)
    except AssertionError:pass
    else:raise AssertionError('hardening label drift survived')
    index=gate.rindex('hard_checks.append(label)')
    omitted=gate[:index]+'pass'+gate[index+len('hard_checks.append(label)'):]
    try:hardening_wiring_check(omitted)
    except AssertionError:pass
    else:raise AssertionError('hardening recording omission survived')
    print('DERIVATIVE_HARDENING_SELFTEST_PASS orientations=8 messages=6 java_mutants=%d fixed_native_labels_untouched'%len(mutations),flush=True)

CALENDAR_DRAFT_PROBE=r'''
package com.supercubegame.pockettodo;
import java.util.*;import java.time.*;
public class MoneyProbe{
/*SOURCE*/
static int checks;
static void need(boolean b,String label){if(!b)throw new AssertionError(label);checks++;}
static void reject(Runnable r,String why){try{r.run();}catch(IllegalArgumentException|IllegalStateException|ArithmeticException|java.time.DateTimeException|UnsupportedOperationException expected){checks++;return;}throw new AssertionError(why);}
public static void main(String[] a){
  BatchDraft d=new BatchDraft(71);reject(d::begin,"unreviewed write");reject(d::freeze,"empty draft");reject(d::removeLast,"empty remove");
  for(String s:new String[]{"","-1","1.001","1e2","NaN","92233720368547758.08"})reject(()->d.add("2028-02-29",Ledger.Kind.EXPENSE,s,""),"invalid amount accepted: "+s);
  for(String s:new String[]{"2027-02-29","2028-02-30","0000-01-01","2028-2-29"})reject(()->d.add(s,Ledger.Kind.EXPENSE,"1",""),"invalid date accepted: "+s);
  need(d.rows().isEmpty(),"failed rows mutated draft");d.add("2028-02-28",Ledger.Kind.EXPENSE,"0","zero");d.add("2028-02-29",Ledger.Kind.EXPENSE,"1.25","leap");d.add("2028-03-01",Ledger.Kind.EXPENSE,"13","expense");d.add("2028-03-01",Ledger.Kind.REFUND,"1","refund");d.add("2028-03-01",Ledger.Kind.INCOME,"2.50","income");d.add("2028-03-01",Ledger.Kind.PLANNED,"9","planned");
  List<Ledger.Entry> six=d.rows();String key=d.key;d.add("2028-03-02",Ledger.Kind.EXPENSE,"20","remove me");d.removeLast();need(six.equals(d.rows()),"remove last mutated other rows");
  Set<String> ids=new HashSet<>();long[] cents={0,125,1300,100,250,900};String[] dates={"2028-02-28","2028-02-29","2028-03-01","2028-03-01","2028-03-01","2028-03-01"};Ledger.Kind[] kinds={Ledger.Kind.EXPENSE,Ledger.Kind.EXPENSE,Ledger.Kind.EXPENSE,Ledger.Kind.REFUND,Ledger.Kind.INCOME,Ledger.Kind.PLANNED};for(int i=0;i<6;i++){Ledger.Entry row=six.get(i);need(row.activityId==71&&row.cents==cents[i]&&row.kind==kinds[i]&&row.date.toString().equals(dates[i])&&ids.add(row.id),"row identity or values "+i);}
  reject(()->six.clear(),"mutable row exposure");d.freeze();reject(()->d.add("2028-03-02",Ledger.Kind.EXPENSE,"2",""),"frozen edit");d.editAgain();d.freeze();List<Ledger.Entry> reviewed=d.begin();need(reviewed.equals(six)&&!key.isEmpty(),"review changed before confirm");
  reject(d::begin,"duplicate confirmation");reject(d::editAgain,"post-submit edit");reject(()->reviewed.remove(0),"mutable submitted rows");d.failed();need(d.begin()==reviewed&&key.equals(d.key),"retry changed key or payload");d.close();reject(d::begin,"abandoned confirmation");need(reviewed.size()==6,"close revoked handed-off write");
  BatchDraft canceled=new BatchDraft(71);canceled.add("2028-03-02",Ledger.Kind.EXPENSE,"1","");canceled.freeze();canceled.close();reject(canceled::begin,"canceled confirmation");need(!canceled.key.equals(key),"cross-draft key reuse");
  Ledger ledger=new Ledger();ledger.recordBatch(key,reviewed);Set<LocalDate> sel=new TreeSet<>();for(String day:new String[]{"2028-02-28","2028-02-29","2028-03-01","2028-03-02"})sel.add(LocalDate.parse(day));long[] metrics={1425,100,250,900,1325,-1075};String[] names={"EXPENSE","REFUND","INCOME","PLANNED","NET_EXPENSE","NET_CASH"};for(int i=0;i<6;i++)need(ledger.total(71,sel,names[i])==metrics[i],"wrong independent metric "+names[i]);need(ledger.recordedActualDates(71,sel).equals(Set.of(LocalDate.parse("2028-02-28"),LocalDate.parse("2028-02-29"),LocalDate.parse("2028-03-01"))),"missing versus zero");
  BatchDraft big=new BatchDraft(71);big.add("2028-02-28",Ledger.Kind.EXPENSE,"92233720368547758.07","");big.add("2028-02-29",Ledger.Kind.EXPENSE,"0.01","");reject(big::freeze,"category sum overflow ignored");System.out.println("CALENDAR_DRAFT_HOST "+checks+" PASS actual Java draft, not UI/SQL");
}}
'''

def calendar_draft_selftest():
    import tempfile
    base=ROOT/'src/main/java/com/supercubegame/pockettodo'
    with tempfile.TemporaryDirectory(prefix='calendar-batch-') as temp:
        work=Path(temp);jc=['java','-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8','-d',temp]
        extract=work/'Extract.java';extract.write_text(RESULT_UI_EXTRACTOR);subprocess.run(jc+[str(extract)],check=True,timeout=30)
        member=work/'members';subprocess.run(['java','-cp',temp,'Extract',str(base/'CalendarScreen.java'),str(member),'BatchDraft'],check=True,timeout=20)
        probe=work/'MoneyProbe.java';probe.write_text(CALENDAR_DRAFT_PROBE.replace('/*SOURCE*/',member.read_text()))
        subprocess.run(jc+[str(probe),str(base/'Ledger.java')],check=True,timeout=30)
        subprocess.run(['java','-cp',temp,'com.supercubegame.pockettodo.MoneyProbe'],check=True,timeout=15)

# API34 CI only. Scope is normal cancellation of this test's OPEN_DOCUMENT dialog, not arbitrary system navigation.
_IMAGE_CANCEL_ROOT='sdk_gphone64_x86_64'
_IMAGE_CANCEL_FOLDER='pocket-append-ci-api34'
_IMAGE_CANCEL_TEXT='已取消选图，没有改变笔记'

def _ci_image_surface(frame,product):
    system={'com.android.documentsui','com.google.android.documentsui'}
    def live(n):
        m=re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]',n.get('bounds',''))
        return bool(m and int(m[3])>int(m[1]) and int(m[4])>int(m[2]) and n.get('visible-to-user')!='false')
    owners={n.get('package') for n in frame};owner=next(iter(owners)) if len(owners)==1 else None
    if owner==product:
        status=[n for n in frame if n.get('content-desc')=='v12-status'];done=len(status)==1 and status[0].get('class')=='android.widget.TextView' and status[0].get('text')==_IMAGE_CANCEL_TEXT and live(status[0]);return ('returned' if done else 'application',product,())
    if owner not in system or not frame or frame[0].get('package')!=owner:return ('other','',())
    if any(n.get('resource-id') in ('android:id/alertTitle','android:id/aerr_close','android:id/button1') for n in frame):return ('other','',())
    def at(n,key):return n.get('resource-id')==owner+':id/'+key
    bars=[n for n in frame if at(n,'toolbar') and live(n)];headers=[n for n in frame if at(n,'directory_header') and live(n)]
    if len(bars)!=1 or len(headers)!=1:return ('other','',())
    strips=[n for n in headers[0].iter('node') if at(n,'horizontal_breadcrumb') and live(n)]
    if len(strips)!=1:return ('other','',())
    raw=[n.get('text','') for n in strips[0].iter('node') if at(n,'breadcrumb_text') and n.get('class')=='android.widget.TextView']
    # A clipped leading crumb may be present in the accessibility tree; never infer a missing parent.
    chain=(_IMAGE_CANCEL_ROOT,'Download',_IMAGE_CANCEL_FOLDER);known=tuple(raw)
    crumbs=[n for n in strips[0].iter('node') if at(n,'breadcrumb_text')]
    if not raw or len(raw)!=len(crumbs) or not live(crumbs[-1]) or not raw[-1]:return ('other','',())
    if known in (chain[:1],chain[:2],chain):return ('directory',owner,known)
    return ('unbound',owner,())

def cancel_fixture_image_picker(read_nodes,back,records,case,product,api,serial,ci,clock=time.monotonic,pause=time.sleep):
    """One original Back; at most two further navigation actions, each authorized ONLY by a distinct observed parent transition. 20 seconds total."""
    if (product,api,serial,ci)!=('com.supercubegame.pockettodo.v12.preview',34,'emulator-5554',True) or case not in ('existing_note','first_image'):raise ValueError('outside image cancel CI fixture')
    end=clock()+20;row={'case':case,'api':api,'status':'PENDING','samples':0,'transitions':[],'backs':[]};records.append(row)
    key=None;since=0.;previous=None;retired=False;owner=None
    try:
        while clock()<end:
            kind,who,path=_ci_image_surface(read_nodes(),product);at=clock();row['samples']+=1
            if at>=end:break
            current=(kind,who,path)
            if current!=key:
                key=current;since=at
                if len(row['transitions'])<48:row['transitions'].append([kind,list(path)])
            if kind in ('application','returned'):
                if previous is not None:
                    retired=True
                    if kind=='returned':row['status']='APP_CONFIRMED_CANCEL';return True
            elif kind=='other':
                raise AssertionError('outside verified normal image picker/application')
            else:
                if retired:raise AssertionError('picker reappeared after return to application')
                if owner is not None and owner!=who:raise AssertionError('image picker ownership changed')
                if previous is None:reason='INITIAL_CANCEL'
                elif current==previous:reason=None
                elif previous[0]=='directory' and kind=='directory' and len(previous[2])==len(path)+1 and previous[2][:-1]==path:reason='OBSERVED_PARENT'
                else:raise AssertionError('unverified image picker path transition')
                if at-since<.15:reason=None
                if reason:
                    if len(row['backs'])>=3 or path in [tuple(v['path']) for v in row['backs']]:raise AssertionError('duplicate or excessive Back')
                    remain=end-clock()
                    if remain<=0:break
                    row['backs'].append({'reason':reason,'path':list(path)});owner=who;previous=current;back(remain)
            delay=min(.20,max(0,end-clock()))
            if delay:pause(delay)
        raise TimeoutError('image picker did not deliver the application cancellation within 20s; see image_picker_cancels')
    except Exception as e:
        row['status']='FAIL';row['exception']=type(e).__name__;raise

_IMAGE_FIXTURES=frozenset(('pocket-broken.png','pocket-wide.png','pocket-large.png','pocket-selected.png','pocket-first.jpg','pocket-pixel-over.png','pocket-pixel-limit.png','pocket-derive-valid.png','pocket-derive-source.jpg'))

def _fixture_rectangle(n):
    if n is None or n.get('enabled')!='true' or n.get('visible-to-user')=='false':return None
    hit=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.get('bounds',''))
    if not hit:return None
    x,y,r,b=map(int,hit.groups());return (x,y,r,b) if x<r and y<b else None

def _fixture_scroll_box(d,who):
    # Only a single real directory contents widget with multiple owned visible item rows.
    if d.get('resource-id')!=who+':id/dir_list' or d.get('class') not in ('android.widget.GridView','androidx.recyclerview.widget.RecyclerView','android.widget.ListView') or d.get('scrollable')!='true':return None
    area=_fixture_rectangle(d);rows=[]
    if not area:return None
    for n in d.iter('node'):
        if n.get('resource-id')!=who+':id/item_root' or n.get('clickable')!='true':continue
        box=_fixture_rectangle(n);titles=[t for t in n.iter('node') if t.get('package')==who and t.get('resource-id')=='android:id/title' and t.get('class')=='android.widget.TextView' and _fixture_rectangle(t)];
        if box and len(titles)==1 and box[0]>=area[0] and box[2]<=area[2] and box[1]>=area[1] and box[3]<=area[3]:rows.append((titles[0].get('text',''),box))
    if len(rows)<2 or not any(name in _IMAGE_FIXTURES for name,_ in rows):return None
    # Find a common interior column and two observed rows separated vertically.
    rows.sort(key=lambda r:r[1][1]);high=rows[0][1];low=rows[-1][1];left=max(high[0],low[0]);right=min(high[2],low[2]);y1=(low[1]+low[3])//2;y2=(high[1]+high[3])//2
    if right<=left+8 or y1-y2<64:return None
    x=(left+right)//2;return (x,y1,x,y2),(d.get('class'),area),tuple(rows)

def select_ci_image(name,choose,read,act,hash_on_device,expected,records,product,api,serial,ci,clock=time.monotonic,pause=time.sleep):
    """CI-only public synthetic fixture in Download. One confirmed parent navigation at most; never guess a path, file or recipient."""
    if (product,api,serial,ci)!=('com.supercubegame.pockettodo.v12.preview',34,'emulator-5554',True) or name not in _IMAGE_FIXTURES or (not choose and name!='pocket-first.jpg') or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('outside staged image fixture')
    end=clock()+20;parent=(_IMAGE_CANCEL_ROOT,'Download');child=parent+(_IMAGE_CANCEL_FOLDER,);state={'name':name,'choose':choose,'status':'PENDING','actions':[]};records.append(state)
    sent_parent=False;at_parent=False;sent_list=False;seen=False;held=None;since=0.;owner=None;sent_scroll=False;scroll_rows=None;scroll_owner=None
    try:
        # Only a build-produced name in the exact public CI directory can reach this read.
        if hash_on_device('/sdcard/Download/'+name,end-clock())!=expected:raise AssertionError('staged fixture bytes differ')
        state['sha256']=expected
        while clock()<end:
            frame=read();kind,who,path=_ci_image_surface(frame,product);now=clock()
            if now>=end:break
            action=None;target=None;signature=None
            if not seen and kind=='application':pass
            elif kind!='directory' or path not in (child,parent) or (seen and who!=owner):raise AssertionError('unexpected picker, folder or window')
            else:
                seen=True;owner=who
                if path==child:
                    if at_parent:raise AssertionError('folder changed after reaching Download')
                    if not sent_parent:action='PARENT'
                else:
                    at_parent=True
                    dirs=[n for n in frame if n.get('resource-id')==who+':id/dir_list'];rows=[n for n in frame if n.get('text')==name and n.get('resource-id')=='android:id/title'];mode=[n for n in frame if n.get('resource-id')==who+':id/sub_menu_list' and n.get('content-desc')=='List view'];
                    if len(rows)>1 or len(dirs)>1 or len(mode)>1:raise AssertionError('ambiguous picker evidence')
                    if rows:
                        target=rows[0];box=_fixture_rectangle(target);containers=[] if not dirs else [n for n in dirs[0].iter('node') if n.get('resource-id')==who+':id/item_root' and n.get('clickable')=='true' and any(k is target for k in n.iter('node'))];outer=_fixture_rectangle(containers[0]) if len(containers)==1 else None
                        if box and outer and target.get('class')=='android.widget.TextView' and outer[0]<=box[0] and outer[1]<=box[1] and box[2]<=outer[2] and box[3]<=outer[3]:action='CHOOSE' if choose else 'OBSERVE'
                    elif mode and not sent_scroll and not sent_list and _fixture_rectangle(mode[0]) and mode[0].get('clickable')=='true':action='LIST';target=mode[0]
                    elif choose and name=='pocket-pixel-over.png' and not sent_scroll and len(dirs)==1:
                        info=_fixture_scroll_box(dirs[0],who)
                        if info:action='SCROLL';target=info
                    if sent_scroll and action=='CHOOSE':
                        info=_fixture_scroll_box(dirs[0],who) if len(dirs)==1 else None
                        if not info or info[1]!=scroll_owner or info[2]==scroll_rows:action=None;target=None
                signature=(path,action,target if action=='SCROLL' else _fixture_rectangle(target))
            if signature!=held:held=signature;since=now
            elif action and now-since>=.15:
                left=end-clock()
                if left<=0:break
                if action=='OBSERVE':state['status']='VISIBLE_NOT_SELECTED';return True
                state['actions'].append(action)
                if action=='PARENT':sent_parent=True
                if action=='LIST':sent_list=True
                if action=='SCROLL':sent_scroll=True;scroll_owner,scroll_rows=target[1:];target=target[0]
                act(action,target,left)
                if action=='CHOOSE':state['status']='SELECTED_ONCE_NOT_IMPORT_ACCEPTANCE';return True
                held=None
            pause(min(.2,max(0,end-clock())))
        raise TimeoutError('staged file not confirmed in Download within original 20s')
    except Exception as err:
        state['status']='FAIL';state['error']=type(err).__name__;raise

def image_cancel_selftest():
    import copy
    P='com.supercubegame.pockettodo.v12.preview';S='com.google.android.documentsui';R=_IMAGE_CANCEL_ROOT;L=_IMAGE_CANCEL_FOLDER
    def node(parent=None,**attrs):
        g={'package':S,'class':'android.view.View','bounds':'[0,0][320,640]','enabled':'true'};g.update(attrs);return ET.Element('node',g) if parent is None else ET.SubElement(parent,'node',g)
    def dir(*path,owner=S):
        root=node();bar=node(root,**{'resource-id':S+':id/toolbar'});header=node(root,**{'resource-id':S+':id/directory_header'});strip=node(header,**{'resource-id':S+':id/horizontal_breadcrumb'});
        for name in path:node(strip,text=name,**{'resource-id':S+':id/breadcrumb_text','class':'android.widget.TextView'})
        for v in root.iter('node'):
            v.set('package',owner);v.set('resource-id',v.get('resource-id','').replace(S,owner))
        return list(root.iter('node'))
    app=lambda msg:[node(**{'package':P,'class':'android.widget.TextView','content-desc':'v12-status','text':msg})];A=app(_IMAGE_CANCEL_TEXT);child=dir(R,'Download',L);parent=dir(R,'Download');top=dir(R);unknown=dir(R,'unbound fixture');F=[node(**{'package':'other.fixture'})]
    cases=[('direct',[top,A],1,True),('deep',[child,parent,top,A],3,True),('one_parent',[child,parent,A],2,True),('unbound_direct',[unknown,A],1,True),('never_change',[child,child],1,False),('unknown_then_parent',[unknown,parent],1,False),('jump_root',[child,top],1,False),('wrong_parent',[child,unknown],1,False),('wrong_owner',[child,dir(R,'Download',owner='com.android.documentsui')],1,False),('other',[F],0,False),('late_other',[child,F],1,False),('already_done',[A],0,False),('app_without_status',[top,app('未返回')],1,False),('ambiguous_status',[top,A+A],1,False),('zero_bounds',[top,[node(**{'package':P,'class':'android.widget.TextView','content-desc':'v12-status','text':_IMAGE_CANCEL_TEXT,'bounds':'[0,0][0,0]'})]],1,False)]
    def run(frames,expected,suc,twist='',fn=cancel_fixture_image_picker):
        t=[0.];i=[0];calls=[];tr=[];reads=[0]
        def read():
            reads[0]+=1
            if twist=='borrowed_then_known' and i[0]==1:return F if reads[0]<5 else parent
            if twist=='application_then_picker' and i[0]==1:return app('等待') if reads[0]<5 else parent
            if twist=='slow' and reads[0]==2:t[0]=20.
            if twist=='late_result' and i[0]==1:t[0]=20.
            if twist=='lingering' and i[0]==1 and reads[0]<8:return frames[0]
            if twist=='transient_leaf' and reads[0]==1:return child
            return frames[min(i[0],len(frames)-1)]
        def back(left):
            assert 0<left<=20;calls.append(i[0]);i[0]+=1
            if twist=='throw':raise OSError('synthetic key failure')
        try:ok=fn(read,back,tr,'existing_note',P,34,'emulator-5554',True,lambda:t[0],lambda d:t.__setitem__(0,t[0]+d))
        except (TimeoutError,AssertionError,OSError):ok=False
        assert len(calls)==expected and bool(ok)==suc and len(tr)==1 and len(tr[0]['backs'])==expected,(twist,len(calls),expected,ok,tr);assert (tr[0]['status']=='APP_CONFIRMED_CANCEL')==suc
        return calls
    for name,frames,num,suc in cases:run(frames,num,suc)
    for key in ('foreign_then_return','ambiguous_then_return','wrong_owner_then_return','jump_then_return'):
        run([child,{'foreign_then_return':F,'ambiguous_then_return':parent+F,'wrong_owner_then_return':dir(R,'Download',owner='com.android.documentsui'),'jump_then_return':top}[key],A],1,False,key)
    for key,frame in [('missing_header',copy.deepcopy(parent)),('missing_breadcrumb',copy.deepcopy(parent)),('clipped_leaf',copy.deepcopy(parent)),('duplicated_header',copy.deepcopy(parent)),('system_alert',copy.deepcopy(parent))]:
        if key=='missing_header':frame=[v for v in frame if not v.get('resource-id','').endswith('/directory_header')]
        elif key=='missing_breadcrumb':frame=[v for v in frame if not v.get('resource-id','').endswith('/directory_header')]+[node(**{'resource-id':S+':id/directory_header'})]
        elif key=='clipped_leaf':
            header=next(v for v in frame if v.get('resource-id','').endswith('/directory_header'));list(header.iter('node'))[-1].set('bounds','[0,0][0,0]')
        elif key=='duplicated_header':frame.append(node(**{'resource-id':S+':id/directory_header'}))
        else:frame.append(node(**{'resource-id':'android:id/alertTitle'}))
        run([frame,A],0,False,key)
    for name in ('borrowed_then_known','application_then_picker'):run([child,parent,top,A],1,False,name)
    run([top,A],0,False,'slow');run([top,A],1,False,'throw');run([top,A],1,False,'late_result');run([child,parent,A],2,True,'lingering');run([top,A],1,True,'transient_leaf')
    def never(*a):raise AssertionError('foreign fixture interacted')
    for args in [(P,26,'emulator-5554',True),('other',34,'emulator-5554',True),(P,34,'phone',True),(P,34,'emulator-5554',False)]:
        try:cancel_fixture_image_picker(never,never,[],'existing_note',*args)
        except ValueError:pass
        else:raise AssertionError('out-of-scope picker action')
    # Both prior aggregate receipts may still say FAIL: only original exact labels + the subsequent independent SQL/bytes checks define acceptance.
    import ast
    tree=ast.parse(Path(__file__).read_text());native=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='_verify_native_ui');xs=list(ast.walk(native));calls=[x for x in xs if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='cancel_note_picker'];assert [ast.literal_eval(x.args[0]) for x in calls]==['existing_note','first_image'];assert sum(isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='cancel_fixture_image_picker' for x in xs)==1
    print('IMAGE_CANCEL_HOST 31 scenarios, 4 off-scope refusals, both original paths present; 20 s per cancel; modeled normal directory navigation, not Android',flush=True)

def image_fixture_target_selftest():
    from copy import deepcopy
    own='com.supercubegame.pockettodo.v12.preview';system='com.google.android.documentsui';chain=(_IMAGE_CANCEL_ROOT,'Download',_IMAGE_CANCEL_FOLDER);name='pocket-broken.png';digest=hashlib.sha256(b'not a PNG').hexdigest()
    def frame(level=2,mode='ok',item=name):
        def add(p,**changes):
            attrs={'package':system,'bounds':'[0,0][60,30]','enabled':'true','class':'android.widget.TextView'};attrs.update(changes);return ET.SubElement(p,'node',attrs)
        root=ET.Element('hierarchy');v=add(root);add(v,**{'resource-id':system+':id/toolbar'});h=add(v,**{'resource-id':system+':id/directory_header'});b=add(h,**{'resource-id':system+':id/horizontal_breadcrumb'})
        for txt in chain[:level]:add(b,text=txt,**{'resource-id':system+':id/breadcrumb_text'})
        d=add(v,**{'resource-id':system+':id/dir_list'});c=add(d,clickable='true',**{'resource-id':system+':id/item_root'});typ={'resource-id':'android:id/title','text':item}
        if mode in ('ok','disabled','twins','foreign','flat','hidden','clipped'):t=add(v if mode=='flat' else c,**typ)
        if mode=='disabled':t.set('enabled','false')
        if mode=='hidden':t.set('visible-to-user','false')
        if mode=='clipped':t.set('bounds','[0,0][65,31]')
        if mode=='twins':add(c,**typ)
        if mode=='foreign':t.set('package','not.the.picker')
        if mode=='grid':add(v,clickable='true',**{'resource-id':system+':id/sub_menu_list','content-desc':'List view'})
        return list(root.iter('node'))
    P=frame();C=frame(3,'empty');G=frame(2,'grid');cases=[]
    def test(key,seq,want,success,wrong_hash=False,late=False,choose=True):
        t=[0.];events=[];state=[];i=[0];fn=name if choose else 'pocket-first.jpg'
        def read():
            n=i[0];i[0]+=1
            if late and n==1:t[0]+=21
            return seq[min(n,len(seq)-1)]
        def hs(path,left):assert path=='/sdcard/Download/'+fn;return digest if not wrong_hash else '0'*64
        try:ok=select_ci_image(fn,choose,read,lambda k,n,l:events.append(k),hs,digest,state,own,34,'emulator-5554',True,lambda:t[0],lambda x:t.__setitem__(0,t[0]+x))
        except (AssertionError,TimeoutError):ok=False
        assert bool(ok)==success and events==want,(key,state,events);cases.append(key)
    test('already parent',[P],['CHOOSE'],True);test('visible parent after Back',[C,C,C,P,P],['PARENT','CHOOSE'],True);test('grid once',[G,G,G,P,P],['LIST','CHOOSE'],True);test('observed only',[frame(item='pocket-first.jpg')],[],True,choose=False);test('same child forever',[C],['PARENT'],False);test('same grid',[G],['LIST'],False);test('unexpected grandparent',[C,C,frame(1)],['PARENT'],False);test('parent withdrawn',[P,C,C],[],False);test('wrong bytes',[P],[],False,wrong_hash=True);test('late',[P],[],False,late=True);test('wrong filename',[frame(item='some-file.png')],[],False)
    for k in ('disabled','twins','foreign','flat','hidden','clipped'):test(k,[frame(mode=k)],[],False)
    # A missing known file in the positively identified Download listing may be off screen,
    # not necessarily below it. Scrolling alone never satisfies the selection condition.
    def pane(item,flags=()):
        f=frame(2,'empty');d=next(n for n in f if n.get('resource-id')==system+':id/dir_list');d.attrib.update({'class':'android.widget.GridView','scrollable':'false' if 'locked' in flags else 'true','bounds':'[0,24][320,640]'});d.remove(list(d)[0]);names=['pocket-broken.png','pocket-first.jpg','pocket-pixel-limit.png' if item is None else item];
        if 'duplicate' in flags:names.append(names[-1]);
        for i,name2 in enumerate(names):
            box='[0,%d][320,%d]'%(128+100*i,205+100*i);outer=ET.SubElement(d,'node',{'resource-id':system+':id/item_root','package':system,'enabled':'true','class':'android.widget.LinearLayout','clickable':'true','bounds':box});ET.SubElement(outer,'node',{'resource-id':'android:id/title','package':system,'enabled':'true','class':'android.widget.TextView','text':name2,'bounds':box})
        if 'wrongpath' in flags:next(n for n in f if n.get('text')=='Download').set('text','Elsewhere')
        if 'moved' in flags:d.set('bounds','[0,10][320,640]')
        return list(f[0].iter('node'))
    over='pocket-pixel-over.png';bfr=pane(None);aft=pane(over);tname=name;name=over
    test('missing known file then exactly one scroll',[bfr,bfr,bfr,aft,aft,aft],['SCROLL','CHOOSE'],True)
    test('scroll without reveal',[bfr],['SCROLL'],False);test('wrong row after scroll',[bfr,bfr,pane('pocket-other.png')],['SCROLL'],False)
    test('wrong path after scroll',[bfr,bfr,pane(over,('wrongpath',))],['SCROLL'],False);test('ambiguous revealed row',[bfr,bfr,pane(over,('duplicate',))],['SCROLL'],False)
    test('container changed after scroll',[bfr,bfr,pane(over,('moved',))],['SCROLL'],False);test('unscrollable Download',[pane(None,('locked',))],[],False);test('digest gates scroll',[bfr],[],False,wrong_hash=True)
    name=tname
    for n,product,api,serial,ci in [('unknown.png',own,34,'emulator-5554',True),(name,own,26,'emulator-5554',True),(name,'foreign',34,'emulator-5554',True),(name,own,34,'phone',True),(name,own,34,'emulator-5554',False)]:
        try:select_ci_image(n,True,None,None,None,digest,[],product,api,serial,ci)
        except ValueError:continue
        raise AssertionError('off-scope file or environment allowed')
    print('IMAGE_FIXTURE_TARGET_HOST %d selection/observation cases and 5 off-scope refusals; no device'%len(cases),flush=True)

def activity_search_host_selftest():
    # Execute actual SQL constants against SQLite. A separate device phase exercises UI callbacks and restoration.
    src=(ROOT/'src/main/java/com/supercubegame/pockettodo/ActivitiesScreen.java').read_text();android=(ROOT/'src/main/java/com/supercubegame/pockettodo/AppDatabase.java').read_text()
    def literal(key):
        match=re.findall(r'\b'+key+r'=(?:SEARCH_COLS\+)?("[^"\n]*");',src);assert len(match)==1,key;return json.loads(match[0])
    query=literal('SEARCH_COLS')+literal('SEARCH_MATCH');one=literal('SEARCH_COLS')+literal('SEARCH_BY_ID');tests=[]
    with sqlite3.connect(':memory:') as db:
        for table in ('categories','applications','activities'):
            ddl=re.findall(r'db\.execSQL\(("CREATE TABLE '+table+r'\([^"\n]+")\);',android);assert len(ddl)==1,table;db.execute(json.loads(ddl[0]))
        db.executemany('INSERT INTO categories VALUES (?,?,?)',[(2,'家庭',0),(5,'工作',1)]);db.execute("INSERT INTO applications VALUES (6,'读书','')");base=[(72,2,6,'晨读🌱',0),(74,5,6,'晨读🌱',0),(75,5,6,'晨读🌱',1),(79,2,None,"O'Brien 50%_café",0)]+[(200+i,2,6,'连续编号',0) for i in range(31)];db.executemany('INSERT INTO activities VALUES (?,?,?,?,?)',base);db.commit();db.execute('PRAGMA query_only=ON');before=list(db.iterdump())
        def ids(term,arch,cursor=0):return [x[0] for x in db.execute(query,(str(cursor),'1' if arch else '0',term))]
        for term,arch,want in [('晨',False,[72,74]),('晨',True,[72,74,75]),('🌱',False,[72,74]),('%_',True,[79]),("O'B",False,[79]),('café',False,[79]),('不在标题',True,[]),('家庭',True,[]),('读书',True,[])]:assert ids(term,arch)==want,(term,arch);tests.append(term)
        assert ids('连续',False)==list(range(200,225)) and ids('连续',False,223)==list(range(224,231));assert db.execute(one,('74',)).fetchall()==[(74,5,'工作','晨读🌱',0)] and not db.execute(one,('2',)).fetchall() and list(db.iterdump())==before
    sample=''.join('ACTIVITY_SEARCH_NATIVE '+label+' PASS\n' for label in SEARCH_LABELS)+'DEVICE_DATABASE_RESULT activity_search 2/2 PASS\nINSTRUMENTATION_CODE: -1\n';search_native_receipt(sample);bad=[sample.replace(label,'absent',1) for label in SEARCH_LABELS]+[sample.replace('-1','0'),sample.replace('2/2','1/2'),sample.replace('DEVICE_DATABASE_RESULT','DEVICE_DATABASE_FAILED\nDEVICE_DATABASE_RESULT'),sample.replace(SEARCH_LABELS[1],SEARCH_LABELS[0])]
    for v in bad:
        try:search_native_receipt(v)
        except AssertionError:continue
        raise AssertionError('false search acceptance')
    print('ACTIVITY_SEARCH_HOST 9 literal result sets, 2 pages, stable-ID relookup and readonly cells, %d receipt negatives; not Android'%len(bad),flush=True)

TEMPLATE_LABELS=('archived_nullable_sibling_and_stale_preview_readonly','owned_native_preview_cancel_all_cells_unchanged','new_id_only_ordered_structure_no_fields_notes_money_marks_or_media_copy','independent_edit_reopen_and_backup_preserve_source_and_copy')

def template_native_receipt(out):
    labels=tuple(re.findall(r'(?m)^(?:INSTRUMENTATION_RESULT: stream=)?ACTIVITY_TEMPLATE_NATIVE ([a-z0-9_]+) PASS\s*$',out))
    codes=re.findall(r'(?m)^INSTRUMENTATION_CODE: (-?\d+)\s*$',out);ends=re.findall(r'(?m)^DEVICE_DATABASE_RESULT activity_template ([^\r\n]+)$',out)
    if labels!=TEMPLATE_LABELS or codes!=['-1'] or ends!=['2/2 PASS'] or 'DEVICE_DATABASE_FAILED' in out:raise AssertionError('template device contract incomplete; see device-activity-template.txt')

def verify_template_device(adb):
    out=run_database_phase([adb,'-s',SERIAL,'shell','am','instrument','-w','-r','-e','phase','activity_template','-e','expectedApi',str(API),PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'],timeout=120,capture=True,phase='activity-template').stdout
    Path('device-activity-template.txt').write_text(out);print(out,flush=True);template_native_receipt(out)

def activity_template_host_selftest():
    src=(ROOT/'src/main/java/com/supercubegame/pockettodo/AppDatabase.java').read_text();cut=src[src.index('public static final class ActivityTemplatePlan'):src.index('/** Single-attempt selection. Catalog reuse')]
    def string(pattern):
        v=re.findall(pattern,cut);assert len(v)==1,pattern;return json.loads(v[0])
    source=string(r'rawQuery\(("SELECT a.category_id[^"\n]+"),');q=[string(r'execSQL\(("INSERT INTO '+table+r'\([^"\n]+"),') for table in ('activities','paths','tags')]
    with sqlite3.connect(':memory:') as db:
        db.execute('PRAGMA foreign_keys=ON')
        for table in ('categories','applications','activities','paths','tags'):
            ddl=re.findall(r'db\.execSQL\(("CREATE TABLE '+table+r'\([^"\n]+")\);',src);assert len(ddl)==1;db.execute(json.loads(ddl[0]))
        db.executescript("INSERT INTO categories VALUES(3,'原分类',0); INSERT INTO applications VALUES(4,'应用',''); INSERT INTO activities VALUES(9,3,NULL,'同名',0),(10,3,4,'同名',0),(11,3,4,'同名',1);INSERT INTO paths VALUES(10,0,'去'),(10,1,'回'),(10,2,'去'); INSERT INTO tags VALUES(10,0,'甲'),(10,1,'乙');")
        assert db.execute(source,(9,)).fetchall()==[(3,None,'同名','原分类',None)] and db.execute(source,(10,)).fetchall()==[(3,4,'同名','原分类','应用')] and not db.execute(source,(11,)).fetchall();before=list(db.iterdump());db.execute('BEGIN');db.execute(q[0],(12,3,4,'同名'))
        for i,t in enumerate(['去','回','去']):db.execute(q[1],(12,i,t))
        for i,t in enumerate(['甲','乙']):db.execute(q[2],(12,i,t))
        assert db.execute('SELECT category_id,application_id,title,archived FROM activities WHERE id=12').fetchall()==[(3,4,'同名',0)] and db.execute('SELECT position,text FROM paths WHERE activity_id=12 ORDER BY position').fetchall()==[(0,'去'),(1,'回'),(2,'去')] and db.execute('SELECT position,text FROM tags WHERE activity_id=12 ORDER BY position').fetchall()==[(0,'甲'),(1,'乙')];db.rollback();assert list(db.iterdump())==before
    sample=''.join('ACTIVITY_TEMPLATE_NATIVE '+s+' PASS\n' for s in TEMPLATE_LABELS)+'DEVICE_DATABASE_RESULT activity_template 2/2 PASS\nINSTRUMENTATION_CODE: -1\n';template_native_receipt(sample)
    invalid=[sample.replace(s,'missing',1) for s in TEMPLATE_LABELS]+[sample.replace('-1','0'),sample.replace('2/2','1/2'),sample.replace(TEMPLATE_LABELS[1],TEMPLATE_LABELS[0]),'DEVICE_DATABASE_FAILED\n'+sample,sample.replace('ACTIVITY_TEMPLATE_NATIVE','X',1),sample+'INSTRUMENTATION_CODE: -1\n',sample+'DEVICE_DATABASE_RESULT activity_template 2/2 PASS\n']
    for bad in invalid:
        try:template_native_receipt(bad)
        except AssertionError:continue
        raise AssertionError('false template acceptance')
    print('ACTIVITY_TEMPLATE_HOST source/inserts/ordered children and rollback, %d invalid receipts rejected; not a device'%len(invalid),flush=True)

def verify_activity_schedule_device(adb):
    from verify_activity_schedules import parse
    output=run_database_phase([adb,'-s',SERIAL,'shell','am','instrument','-w','-r','-e','phase','activity_schedule','-e','expectedApi',str(API),PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'],timeout=120,capture=True,phase='activity-schedule').stdout
    print(output,flush=True);Path('device-activity-schedule.txt').write_text(output);parse(output,API)

def verify_oriented_photo_device(adb):
    from verify_oriented_photos import parse_receipt
    out=run_database_phase([adb,'-s',SERIAL,'shell','am','instrument','-w','-r','-e','phase','oriented_photo','-e','expectedApi',str(API),PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'],timeout=120,capture=True,phase='oriented-photo').stdout
    Path('device-oriented-photo.txt').write_text(out);print(out,flush=True);parse_receipt(out,API)

def verify_ledger_changes_device(adb):
    from verify_ledger_changes import parse
    out=run_database_phase([adb,'-s',SERIAL,'shell','am','instrument','-w','-r','-e','phase','ledger_changes','-e','expectedApi',str(API),PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'],timeout=120,capture=True,phase='ledger-changes').stdout
    Path('device-ledger-changes.txt').write_text(out);print(out,flush=True);parse(out,API)

def verify_schedule_book_device(adb):
    from verify_schedule_book import stage,parse
    stage(adb,SERIAL,API,PKG)
    out=run_database_phase([adb,'-s',SERIAL,'shell','am','instrument','-w','-r','-e','phase','schedule_book_ui','-e','expectedApi',str(API),PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'],timeout=120,capture=True,phase='schedule-book').stdout
    Path('device-schedule-book.txt').write_text(out);print(out,flush=True);parse(out,API)

def parser_selftest():
    from verify_schedule_book import host_selftest as book_host_selftest
    book_host_selftest()
    from verify_activity_schedules import host_selftest as activity_schedule_host_selftest
    activity_schedule_host_selftest()
    from verify_ledger_changes import host_selftest as ledger_changes_host_selftest
    ledger_changes_host_selftest()
    from verify_oriented_photos import host_selftest as oriented_photo_host_selftest
    oriented_photo_host_selftest()
    activity_template_host_selftest()
    activity_search_host_selftest()
    image_fixture_target_selftest()
    image_cancel_selftest()
    calendar_draft_selftest()
    activity_navigation_selftest()
    derivative_hardening_selftest()
    relation_input_selftest()
    relation_ui_selftest()
    result_ui_selftest()
    todo_navigation_selftest()
    database_timeout_selftest()
    readiness_timeout_wiring_selftest()
    restore_picker_summary_selftest()
    restore_picker_selftest()
    restore_picker_wiring_selftest()
    full_native_observer_selftest()
    summary_navigation_selftest()
    summary_geometry_selftest()
    summary_wiring_selftest()
    database_directory_selftest()
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

def legacy_public_fixture(adb):
    """Publish only known synthetic legacy bytes in a NEW directory on our disposable emulator.
    The app still receives a real user-selected content URI. No app/URI permissions are changed.
    The device independently builds the expected file with the original Java codec.
    """
    import base64, struct, tempfile
    assert os.environ.get('GITHUB_ACTIONS')=='true' and SERIAL=='emulator-5554' and API in (26,34) and PKG=='com.supercubegame.pockettodo.v12.preview'
    def shellprop(key):return subprocess.check_output([str(adb),'-s',SERIAL,'shell','getprop',key],text=True,timeout=15).strip()
    assert shellprop('ro.kernel.qemu')=='1' and shellprop('ro.build.version.sdk')==str(API), 'not isolated matrix emulator'
    title='同名记录'.encode('utf-8') # chosen BMP characters have identical UTF-8 and Java writeUTF bodies
    plain=struct.pack('>IqI',0x544f4431,3,2)+b''.join(struct.pack('>qH',i,len(title))+title+bytes((done,)) for i,done in ((1,0),(2,1)))
    payload=base64.b64encode(plain);wire=b'POCKET_TODO_BACKUP\n1\n'+hashlib.sha256(payload).hexdigest().encode('ascii')+b'\n'+payload+b'\n'
    directory='/sdcard/Download/pocket-append-ci-api'+str(API);dest=directory+'/old-todos.txt'
    with tempfile.TemporaryDirectory(prefix='pocket-append-fixture-') as td:
        local=Path(td)/'old-todos.txt';local.write_bytes(wire)
        run([adb,'-s',SERIAL,'shell','mkdir',directory],timeout=20) # fail if it existed; no replacement or deletion
        run([adb,'-s',SERIAL,'push',local,dest],timeout=20)
    actual=subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','cat',dest],timeout=20)
    proof={'commit':os.environ.get('GITHUB_SHA'),'run_id':os.environ['GITHUB_RUN_ID'],'api':API,'expected':hashlib.sha256(wire).hexdigest(),'observed':hashlib.sha256(actual).hexdigest(),'bytes':len(actual),'source':'CI_SYNTHETIC_PUBLIC_DOWNLOAD_ONLY'}
    Path('device-legacy-fixture.txt').write_text(json.dumps(proof,sort_keys=True)+'\n')
    assert actual==wire,'public legacy fixture bytes differ; see device-legacy-fixture.txt'


def verify_calendar_batch_device(adb):
    """Separate phase before the original seed/reopen. Keep its raw receipt even if another phase fails."""
    expected=['schema3_atomic_replay_owner_and_undo_guards','preview_and_cancel_preserve_all_business_cells','six_ordered_rows_one_key_zero_missing_leap_four_kinds','undo_cancel_then_exact_batch_only_and_reopen']
    out=run_database_phase([adb,'-s',SERIAL,'shell','am','instrument','-w','-r','-e','phase','calendar_batch','-e','expectedApi',str(API),PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'],timeout=125,capture=True,phase='calendar-batch').stdout
    Path('device-calendar-batch.txt').write_text(out);print(out,flush=True)
    labels=re.findall(r'(?m)^(?:INSTRUMENTATION_RESULT: stream=)?CALENDAR_BATCH_NATIVE ([a-z0-9_]+) PASS\s*$',out)
    assert re.findall(r'(?m)^INSTRUMENTATION_CODE: (-?\d+)\s*$',out)==['-1'] and 'DEVICE_DATABASE_FAILED' not in out and labels==expected and 'DEVICE_DATABASE_RESULT calendar_batch 2/2 PASS' in out,'calendar native phase not accepted; see device-calendar-batch.txt'


SEARCH_LABELS=('empty_query_and_two_distinct_active_identities','spoken_identity_and_detached_result_cannot_navigate','open_second_and_archived_id_back_preserves_scope','literal_symbols_unicode_and_no_private_body_results','keyset_pages_exact_no_drops_or_duplicates','unchanged_all_cells_reopen_and_independent_backup_restore')

def search_native_receipt(out):
    labels=tuple(re.findall(r'(?m)^(?:INSTRUMENTATION_RESULT: stream=)?ACTIVITY_SEARCH_NATIVE ([a-z0-9_]+) PASS\s*$',out));codes=re.findall(r'(?m)^INSTRUMENTATION_CODE: (-?\d+)\s*$',out)
    if labels!=SEARCH_LABELS or codes!=['-1'] or 'DEVICE_DATABASE_FAILED' in out or not re.search(r'(?m)^DEVICE_DATABASE_RESULT activity_search 2/2 PASS\s*$',out):raise AssertionError('activity search device contract not verified')

def verify_search_device(adb):
    out=run_database_phase([adb,'-s',SERIAL,'shell','am','instrument','-w','-r','-e','phase','activity_search','-e','expectedApi',str(API),PKG+'.test/com.supercubegame.pockettodo.V12DeviceTest'],timeout=120,capture=True,phase='activity-search').stdout
    Path('device-activity-search.txt').write_text(out);print(out,flush=True);search_native_receipt(out)

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
    calendar_error=None
    try:verify_calendar_batch_device(adb)
    except Exception as exc:
        calendar_error=exc;print('CALENDAR_PHASE_NOT_ACCEPTED '+repr(exc),flush=True)
    search_error=None
    try:verify_search_device(adb)
    except Exception as exc:
        search_error=exc;print('ACTIVITY_SEARCH_PHASE_NOT_ACCEPTED '+repr(exc),flush=True)
    template_error=None
    try:verify_template_device(adb)
    except Exception as exc:
        template_error=exc;print('ACTIVITY_TEMPLATE_PHASE_NOT_ACCEPTED '+repr(exc),flush=True)
    photo_error=None
    try:verify_oriented_photo_device(adb)
    except Exception as exc:
        photo_error=exc;print('ORIENTED_PHOTO_PHASE_NOT_ACCEPTED '+repr(exc),flush=True)
    schedule_error=None
    try:verify_activity_schedule_device(adb)
    except Exception as exc:
        schedule_error=exc;print('ACTIVITY_SCHEDULE_PHASE_NOT_ACCEPTED '+repr(exc),flush=True)
    book_error=None
    try:verify_schedule_book_device(adb)
    except Exception as exc:
        book_error=exc;print('SCHEDULE_BOOK_PHASE_NOT_ACCEPTED '+repr(exc),flush=True)
    amend_error=None
    try:verify_ledger_changes_device(adb)
    except Exception as exc:
        amend_error=exc;print('LEDGER_CHANGES_PHASE_NOT_ACCEPTED '+repr(exc),flush=True)
    legacy_public_fixture(adb)
    results = {}
    for phase in ('seed', 'reopen'):
        if phase == 'reopen':
            stop_verified(adb, SERIAL, PKG)
        output = run_database_phase([adb, '-s', SERIAL, 'shell', 'am', 'instrument', '-w', '-r', '-e', 'phase', phase,
                      '-e', 'expectedApi', str(API), PKG + '.test/com.supercubegame.pockettodo.V12DeviceTest'], timeout=180, capture=True, phase=phase).stdout
        print(output, flush=True)
        Path('device-' + phase + '.txt').write_text(output)
        results[phase] = verify_phase(output, phase)
    Path('device-result.json').write_text(json.dumps({'status': 'PASS', 'api': API, 'checks': results,
        'scope': 'ANDROID_SCHEMA2_DATABASE_AND_MEDIA_BYTES', 'ui': 'SEE_NATIVE_UI_RESULT', 'image_decoding': 'NOT_TESTED',
        'full_backup_restore': RESTORE_SCOPE, 'saf_restore_ui': 'SEE_NATIVE_UI_RESULT', 'power_loss': 'NOT_TESTED',
        'release_ready': False}, indent=2))
    if calendar_error is not None:raise calendar_error
    if search_error is not None:raise search_error
    if template_error is not None:raise template_error
    if photo_error is not None:raise photo_error
    if schedule_error is not None:raise schedule_error
    if book_error is not None:raise book_error
    if amend_error is not None:raise amend_error

def derivative_checker():
    """Compile and prove the actual pixel oracle before slow native UI work."""
    helper=Path('build/ci-note-image');helper.mkdir(parents=True,exist_ok=True)
    source=helper/'VerifyDerivative.java'
    source.write_text('''import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
public class VerifyDerivative {
 public static void main(String[] a) throws Exception {
  if(a.length==0){selftest();System.out.println("DERIVATIVE_ORACLE_PASS positive=1 negative=2");return;}
  BufferedImage src=ImageIO.read(new File(a[0])), out=ImageIO.read(new File(a[1]));
  if(src==null||out==null) throw new AssertionError("decode failed");
  int l=Integer.parseInt(a[2]),t=Integer.parseInt(a[3]),r=Integer.parseInt(a[4]),b=Integer.parseInt(a[5]);
  if(out.getWidth()!=r-l||out.getHeight()!=b-t) throw new AssertionError("output dimensions differ from reported crop");
  java.util.List<int[]> masks=new java.util.ArrayList<>();
  for(int i=6;i+3<a.length;i+=4) masks.add(new int[]{Integer.parseInt(a[i])-l,Integer.parseInt(a[i+1])-t,Integer.parseInt(a[i+2])-l,Integer.parseInt(a[i+3])-t});
  verify(src,out,l,t,masks);
  selftest();
  System.out.println("DERIVATIVE_PIXELS_PASS "+out.getWidth()+"x"+out.getHeight());
 }
 static void verify(BufferedImage src,BufferedImage out,int l,int t,java.util.List<int[]> masks){
  for(int y=0;y<out.getHeight();y++) for(int x=0;x<out.getWidth();x++){
   boolean masked=false;
   for(int[] m:masks) if(x>=m[0]&&x<m[2]&&y>=m[1]&&y<m[3]){masked=true;break;}
   int expected=masked?0xff000000:src.getRGB(l+x,t+y);
   if(out.getRGB(x,y)!=expected) throw new AssertionError("pixel differs at "+x+","+y);
  }
 }
 static void selftest(){
  BufferedImage src=new BufferedImage(4,1,BufferedImage.TYPE_INT_ARGB);
  BufferedImage out=new BufferedImage(4,1,BufferedImage.TYPE_INT_ARGB);
  for(int x=0;x<4;x++){src.setRGB(x,0,0xff21785f);out.setRGB(x,0,x==1||x==2?0xff000000:0xff21785f);}
  java.util.List<int[]> masks=java.util.Collections.singletonList(new int[]{1,0,3,1});
  verify(src,out,0,0,masks);
  for(int x:new int[]{2,3}){
   int old=out.getRGB(x,0);out.setRGB(x,0,0xffffffff);
   boolean rejected=false;
   try{verify(src,out,0,0,masks);}catch(AssertionError expected){rejected=true;}
   out.setRGB(x,0,old);
   if(!rejected)throw new AssertionError("pixel checker skipped corruption after first mask at "+x);
  }
 }
}
''')
    run(['javac','-d',helper,source],timeout=40)
    proof=run(['java','-Djava.awt.headless=true','-cp',helper,'VerifyDerivative'],timeout=40,capture=True).stdout.strip()
    assert proof=='DERIVATIVE_ORACLE_PASS positive=1 negative=2',proof
    return proof

def verify_native_ui(adb):
    """Close the one readonly observer before any later instrumentation callback."""
    from verify_ui_observer import Observer, run_native_phase
    out=Path('native-ui');out.mkdir(exist_ok=True)
    folder=out/'full-observer'
    receipt={};phase={};primary=None
    observer=Observer(adb,SERIAL,SDK,folder,receipt)
    def body(nodes):
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'binding.json').write_text(json.dumps(list(observer.binding))+'\n')
        return _verify_native_ui(adb,nodes)
    try:
        run_native_phase(observer,body,phase)
    except BaseException as exc:
        primary=exc
        raise
    finally:
        try:
            folder.mkdir(parents=True,exist_ok=True)
            (folder/'phase.json').write_text(json.dumps(phase,indent=2)+'\n')
            target=out/'native-result.json'
            result=json.loads(target.read_text()) if target.is_file() else {
                'status':'FAIL','api':API,'count':0,'checks':[],'release_ready':False}
            result['full_native_observer']=dict(receipt=receipt,phase=phase,
                evidence_directory='native-ui/full-observer')
            if primary is not None:
                result['status']='FAIL';result.setdefault('error',repr(primary))
            else:
                assert result['status']=='PASS' and phase['status']=='PASS'
                assert phase['close_before_return'] is True
            target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            print('FULL_NATIVE_OBSERVER_RESULT '+json.dumps(
                result['full_native_observer'],ensure_ascii=False),flush=True)
        except BaseException as reporting:
            if primary is None:raise
            print('FULL_NATIVE_OBSERVER_REPORT_FAILED '+repr(reporting),flush=True)


def full_native_observer_selftest(native=verify_native_ui):
    """Actual phase/wrapper with observation doubles; not Android acceptance."""
    import ast
    import copy
    import inspect
    import tempfile
    import verify_ui_observer as bridge
    from unittest.mock import patch
    primary=ValueError('native business sentinel')
    close_error=RuntimeError('native close sentinel')
    original=inspect.getsource(native)
    def exercise(source,mode):
        events=[];receipts=[]
        class Fake:
            def __init__(self,adb,serial,sdk,folder,receipt):
                assert (adb,serial,sdk)==('test-adb',SERIAL,SDK)
                self.receipt=receipt;self.binding=('a'*40,'12','1',26,'b'*32,'c'*64)
                self.folder=folder;receipts.append(receipt)
            def start(self):
                events.append('start')
                if mode=='start':raise primary
                self.receipt.update(status='ACTIVE',scope='CI_PERSISTENT_READONLY_UI_NOT_PRODUCT_OR_ROOT_CAUSE_PROOF',
                    commit='a'*40,run_id='12',run_attempt='1',api=26,nonce='b'*32,
                    dex_sha256='c'*64,starts=1,reconnects=0,reads=0,last_sequence=0,exit_code=0)
                return self
            def dump(self):
                events.append('dump')
                if mode=='dump':raise primary
                raw='<hierarchy><node text="fresh"/></hierarchy>'
                self.receipt['reads']+=1;self.receipt['last_sequence']+=1
                self.receipt['last_xml_sha256']=hashlib.sha256(raw.encode()).hexdigest()
                return raw
            def close(self,primary_failed=False):
                events.append(('close',primary_failed))
                if mode in ('close','both'):raise close_error
                self.receipt['status']='CLOSED'
        with tempfile.TemporaryDirectory(prefix='full-native-wiring-') as tmp:
            root=Path(tmp)
            def body(adb,nodes):
                assert adb=='test-adb';events.append('body')
                if mode in ('body','both'):raise primary
                assert nodes()[0].get('text')=='fresh'
                assert nodes()[0].get('text')=='fresh'
                value=dict(status='PASS',api=26,count=186,checks=['fixture'],release_ready=False)
                (root/'native-ui/native-result.json').write_text(json.dumps(value))
            scope=dict(globals(),Path=lambda path:root/path,_verify_native_ui=body)
            exec(compile(source,'actual-native-wrapper','exec'),scope)
            failure=None
            with patch.object(bridge,'Observer',Fake):
                try:scope['verify_native_ui']('test-adb')
                except BaseException as exc:failure=exc
            if mode=='ok':
                assert failure is None,repr(failure)
                assert events==['start','body','dump','dump',('close',False)],events
            else:
                assert failure is (close_error if mode=='close' else primary),('original failure lost',mode,repr(failure))
                assert events[-1]==('close',True if mode in ('start','body','both','dump') else False)
            result=json.loads((root/'native-ui/native-result.json').read_text())
            phase=json.loads((root/'native-ui/full-observer/phase.json').read_text())
            assert result['status']==('PASS' if mode=='ok' else 'FAIL')
            assert result['full_native_observer']['phase']==phase
            assert result['full_native_observer']['receipt']==receipts[0]
            assert result['release_ready'] is False
            if mode=='ok':assert phase['reads']==2 and phase['close_before_return'] is True
            else:assert phase['status']=='FAIL' and result['error']==repr(failure)
    for mode in ('ok','start','dump','body','close','both'):exercise(original,mode)
    mutants=[
        ("result['status']='FAIL';result.setdefault('error',repr(primary))",
         "result.setdefault('error',repr(primary))",'close'),
        ("primary=exc", "primary=None",'both'),
    ]
    for old,new,mode in mutants:
        assert original.count(old)==1
        mutant=original.replace(old,new,1)
        exercise(mutant,'ok')
        try:exercise(mutant,mode)
        except AssertionError:pass
        else:raise AssertionError('native wrapper mutant survived '+old)
    # Inspect executable AST, not comments or a keyword elsewhere in the file.
    tree=ast.parse(Path(__file__).read_text())
    def wiring(tree):
        native=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_native_ui']
        assert len(native)==1
        assert [a.arg for a in native[0].args.args]==['adb','nodes']
        assert not any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='nodes'
                       for n in ast.walk(native[0]))
        assert not any(isinstance(n,ast.Constant) and n.value=='uiautomator' for n in ast.walk(native[0]))
        wrapper=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_native_ui']
        assert len(wrapper)==1
        body=[n for n in ast.walk(wrapper[0]) if isinstance(n,ast.FunctionDef) and n.name=='body']
        assert len(body)==1 and ast.unparse(body[0].body[-1])=='return _verify_native_ui(adb, nodes)'
        calls=[n for n in ast.walk(wrapper[0]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='run_native_phase']
        assert len(calls)==1 and ast.unparse(calls[0])=='run_native_phase(observer, body, phase)'
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='verify_native_ui'
                   and ast.unparse(n)=='verify_native_ui(adb)' for n in ast.walk(main))
    wiring(tree)
    for kind in ('reader','phase','main'):
        changed=copy.deepcopy(tree)
        if kind=='reader':
            f=next(n for n in changed.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_native_ui')
            f.body.insert(0,ast.parse('def nodes(): return []').body[0])
        else:
            fname='verify_native_ui' if kind=='phase' else 'main'
            callname='run_native_phase' if kind=='phase' else 'verify_native_ui'
            f=next(n for n in changed.body if isinstance(n,ast.FunctionDef) and n.name==fname)
            for n in ast.walk(f):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==callname:n.func.id='omitted'
        try:wiring(changed)
        except AssertionError:pass
        else:raise AssertionError('full native wiring omission accepted '+kind)
    print('FULL_NATIVE_OBSERVER_HOST 1 positive 5 negative 2 compiled behavioral mutants 3 AST wiring omissions PASS; NOT_ANDROID',flush=True)


def _verify_native_ui(adb,nodes):
    """Only real taps/text input; independently read SQLite after force-stop, no seeding UI DB."""
    out = Path('native-ui'); out.mkdir(exist_ok=True)
    checks, shots = [], []
    infra_retries = []
    process_stops = []
    restore_picker_traces = []
    summary_navigation_traces = []
    image_fixture_navigation=[]
    image_picker_cancels=[]
    directory_traces = []
    hard_checks = []
    directory_runner = isolated_directory_runner(adb, SERIAL, PKG, directory_traces)
    def shell(*args):
        return subprocess.check_output([str(adb), '-s', SERIAL, 'shell', *args], text=True, timeout=40)
    def tap_node(n):
        assert n.get('enabled')=='true', 'disabled touch target '+repr(n.attrib)
        x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')))
        assert x2>x1 and y2>y1, 'empty touch bounds'
        shell('input','tap',str((x1+x2)//2),str((y1+y2)//2))
    def swipe_summary(x1,y1,x2,y2):
        shell('input','swipe',str(x1),str(y1),str(x2),str(y2),'350'); time.sleep(.4)
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
        return stop_verified(adb, SERIAL, PKG, emit=process_stops.append)
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
        n=reveal_todo(nodes,swipe_summary,PKG,title)
        return n
    def add_todo(title):
        touch('新待办输入'); type_text(title); tap('添加'); ready(); return named_todo(title)
    def copy_db(name):
        local=out/name
        local.write_bytes(subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','databases/pocket-v12.db'],timeout=30))
        present=database_directory(adb,SERIAL,PKG,runner=directory_runner).splitlines()
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
        select_restore_file(nodes,tap_node,label,restore_picker_traces)
        dialog=desc('restore-consent')
        assert dialog.get('enabled')=='true' and dialog.get('checked')=='false','consent checkbox starts visible and unchecked'
        counts=desc('restore-counts').get('text')
        assert counts is not None and '普通待办：本机 3 → 备份 2' in counts,'restore preview shows exact current and incoming todo counts; actual='+repr(counts)
        ok(True,'SAF file selection shows visible restore preview and replacement counts')
        return dialog
    try:
        pixel_oracle=derivative_checker()
        (out/'derivative-oracle.json').write_text(json.dumps({'status':'PASS','evidence':pixel_oracle}))
        jpeg_oracle=derivative_jpeg_tools()
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
        touch('activity-1'); ready(); swipe_up(); tap('编辑路径'); enter_relation_path(nodes,swipe_summary,PKG,tap_node,type_text,shell); ready(); swipe_up()
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
        if API==26:
            from verify_process_control import snapshot_stop26
            snapshot_stop26(adb,SERIAL,PKG,emit=process_stops.append)
        else:stop()
        with sqlite3.connect(copy_db('pocket-v12.db')) as db:
            ok(db.execute('PRAGMA user_version').fetchone()==(3,) and [r[1] for r in db.execute('PRAGMA table_info(blocks)')]==['note_id','id','position','kind','text','asset_id','caption','private','original_asset_id'],'default native UI uses schema3 with exact nine-column block layout')
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
        ok(named_todo('After backup') is not None and absent('确认恢复'),'canceling SAF restore preview makes no database write')
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
        # The activity summary can be below the viewport after accessible title controls grow.
        # Navigate by stable identity, then assert exact content once; never retry wrong text.
        ok(reveal_summary(nodes,swipe_summary,PKG,'note-activity-1','Watered 20 min today',records=summary_navigation_traces) is not None,'note survives process restart')
        # The bottom tab reloads the selected detail; it does not clear selected activity.
        # Verify that detail before entering notes, rather than seeking a category-list row.
        tap('活动'); ready()
        assert desc('note-count-1').get('text')=='笔记 · 1 篇','activity tab must retain the selected detail before opening notes'
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
            before_notes=db.execute('SELECT * FROM notes ORDER BY id').fetchall()
            before_blocks=db.execute('SELECT * FROM blocks ORDER BY note_id,position').fetchall()
            before_media=db.execute('SELECT * FROM media ORDER BY id').fetchall()
            before_ledger=db.execute('SELECT * FROM ledger ORDER BY id').fetchall()
        # Independent read of the actual private file, not just its registration.
        asset,mime,registered_size=media[0]
        assert re.fullmatch(r'[0-9a-f]{64}',asset), 'invalid media ID cannot enter adb path'
        image_bytes=subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','files/media/'+asset],timeout=30)
        ok(len(image_bytes)==registered_size and hashlib.sha256(image_bytes).hexdigest()==asset,'actual private PNG bytes match registry size and content ID')
        image_file=(out/'note-media.png').resolve(); image_file.write_bytes(image_bytes)
        # Generated verification helper uses host JDK ImageIO, independent of Android Bitmap.
        helper=Path('build/ci-note-image'); helper.mkdir(parents=True,exist_ok=True)
        source=helper/'VerifyNotePng.java'
        source.write_text('''import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
public class VerifyNotePng {
 public static void main(String[] args) throws Exception {
  BufferedImage image=ImageIO.read(new File(args[0]));
  if(image==null || image.getWidth()!=96 || image.getHeight()!=96) throw new AssertionError("Expected decoded 96x96 PNG");
  for(int y=0;y<96;y++) for(int x=0;x<96;x++)
   if(image.getRGB(x,y)!=0xff21785f) throw new AssertionError("Wrong or transparent pixel at "+x+","+y);
  System.out.println("NOTE_PNG_PIXELS_PASS 9216");
 }
}
''')
        run(['javac','-d',helper,source],timeout=40)
        decoded=run(['java','-Djava.awt.headless=true','-cp',helper,'VerifyNotePng',image_file],timeout=40,capture=True).stdout
        ok(image_bytes[:8]==b'\x89PNG\r\n\x1a\n' and decoded.strip()=='NOTE_PNG_PIXELS_PASS 9216','independent PNG decoder verifies all 9216 opaque expected pixels')
        text_id=before_blocks[0][1]
        start(); tap('活动'); ready(); touch('activity-1'); ready(); tap('笔记'); ready()
        touch('note-edit-'+text_id)
        ok(desc('文字内容').get('text')=='Watered 20 min today','edit existing note opens with the exact stored text')
        clear_field('文字内容'); type_text('Discard note edit'); tap('取消'); ready()
        ok(desc('note-text-'+text_id).get('text')=='Watered 20 min today' and absent('Discard note edit'),'cancel note edit preserves original text and identity')
        touch('note-edit-'+text_id); clear_field('文字内容'); tap('保存')
        ok(find(text='内容不能为空') is not None and find(text='修改文字') is not None,'blank existing note edit stays open with visible validation')
        tap('取消'); ready(); stop()
        with sqlite3.connect(copy_db('note-cancel.db')) as db:
            ok(db.execute('SELECT * FROM notes ORDER BY id').fetchall()==before_notes and db.execute('SELECT * FROM blocks ORDER BY note_id,position').fetchall()==before_blocks,'cancelled valid and blank note edits leave exact persisted note rows unchanged')
        start(); tap('活动'); ready(); touch('activity-1'); ready(); tap('笔记'); ready()
        touch('note-edit-'+text_id); clear_field('文字内容'); type_text('Watered 35 min today'); tap('保存'); ready()
        ok(desc('note-text-'+text_id).get('text')=='Watered 35 min today' and absent('Watered 20 min today'),'note edit replaces text in place without leaving an old duplicate')
        restart(); tap('活动'); ready(); touch('activity-1'); ready(); tap('笔记'); ready()
        ok(desc('note-text-'+text_id).get('text')=='Watered 35 min today','edited note text and stable block identity survive stopped-process restart')
        ok(desc('note-image-'+before_blocks[1][1]).get('class')=='android.widget.ImageView','image remains an image view after editing text and restarting')
        shot('10-note-edited.png'); stop()
        with sqlite3.connect(copy_db('note-edited.db')) as db:
            expected_blocks=[list(row) for row in before_blocks]; expected_blocks[0][4]='Watered 35 min today'
            ok(db.execute('SELECT * FROM notes ORDER BY id').fetchall()==before_notes and db.execute('SELECT * FROM blocks ORDER BY note_id,position').fetchall()==[tuple(row) for row in expected_blocks],'independent readback proves only text changed with note IDs block IDs order and privacy retained')
            ok(db.execute('SELECT * FROM media ORDER BY id').fetchall()==before_media and db.execute('SELECT * FROM ledger ORDER BY id').fetchall()==before_ledger,'editing note leaves exact media registry and complete ledger unchanged')
        after_image=subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','files/media/'+asset],timeout=30)
        ok(after_image==image_bytes,'text editing and restart preserve exact private image bytes')
        # Public fixtures are generated locally; never upload real user photos.
        import struct, zlib
        def png(w,h):
            def chunk(kind,data):
                return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
            pixels=b''.join(b'\0'+bytes((220,70,40,255))*(w//2)+bytes((35,90,210,255))*(w-w//2) for _ in range(h))
            return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')
        chosen=png(1536,768)
        fixtures={'pocket-selected.png':chosen,'pocket-broken.png':b'not a PNG',
                  'pocket-wide.png':png(20000,1),'pocket-large.png':chosen+b'\0'*(8*1024*1024+1-len(chosen))}
        fixture_dir=Path('build/ci-picked-images'); fixture_dir.mkdir(parents=True,exist_ok=True)
        for name,data in fixtures.items():
            path=fixture_dir/name;path.write_bytes(data)
            run([adb,'-s',SERIAL,'push',path,'/sdcard/Download/'+name])
        def note_screen():
            start(); tap('活动'); ready(); touch('activity-1'); ready(); tap('笔记'); ready()
        # API34 image grids expose a description, not a text node; select in list view.
        # Use the same shell tap as the verified SAF backup flow. The legacy finger
        # helper remains untouched in ui_test.py; its API34 exit 137 is not diagnosed.
        def checked_fixture(name,choose):
            def stage_sha(path,left):
                return subprocess.check_output([str(adb),'-s',SERIAL,'shell','sha256sum',path],text=True,timeout=left).split()[0]
            def act(action,target,left):
                if action=='PARENT':args=['input','keyevent','KEYCODE_BACK']
                elif action=='SCROLL':args=['input','swipe',*[str(x) for x in target],'300']
                else:
                    l,t,r,b=_fixture_rectangle(target);args=['input','tap',str((l+r)//2),str((t+b)//2)]
                subprocess.run([str(adb),'-s',SERIAL,'shell',*args],timeout=left,check=True)
            assert name in _IMAGE_FIXTURES
            digest=hashlib.sha256((fixture_dir/name).read_bytes()).hexdigest()
            return select_ci_image(name,choose,nodes,act,stage_sha,digest,image_fixture_navigation,PKG,API,SERIAL,os.environ.get('GITHUB_ACTIONS')=='true')
        def pick_image(name=None):
            tap('加入图片'); tap('从文件选择')
            if name is not None:
                if API==34:return checked_fixture(name,True)
                for n in nodes():
                    if n.get('content-desc')=='List view':
                        tap_node(n);break
                target=find(text=name)
                assert target.get('package','').endswith('documentsui'),'image fixture selection must stay in system picker'
                x1,y1,x2,y2=map(int,re.findall(r'\d+',target.get('bounds')))
                assert x2>x1 and y2>y1,'document filename must have actual touch bounds'
                print('IMAGE_PICKER_TARGET '+repr(target.attrib),flush=True)
                tap_node(target)
        def cancel_note_picker(case):
            if API!=34:
                shell('input','keyevent','KEYCODE_BACK')
                return find(**{'content-desc':'v12-status','text':'已取消选图，没有改变笔记'}) is not None
            def key_back(left):
                return subprocess.check_output([str(adb),'-s',SERIAL,'shell','input','keyevent','KEYCODE_BACK'],text=True,timeout=min(40,left))
            return cancel_fixture_image_picker(nodes,key_back,image_picker_cancels,case,PKG,API,SERIAL,os.environ.get('GITHUB_ACTIONS')=='true')
        note_screen(); pick_image()
        ok(any(n.get('package','').endswith('documentsui') for n in nodes()),'image import opens the actual system document picker')
        ok(cancel_note_picker('existing_note'),'cancel system image picker reports no note change')
        stop()
        with sqlite3.connect(copy_db('pick-cancel.db')) as db:
            baseline={t:db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall() for t in TABLES}
            ok(db.execute('SELECT * FROM blocks ORDER BY note_id,position').fetchall()==[tuple(row) for row in expected_blocks] and db.execute('SELECT * FROM media ORDER BY id').fetchall()==before_media,'cancel picker leaves exact blocks and media registrations unchanged')
        for filename,label in [('pocket-broken.png','malformed'),('pocket-wide.png','oversized dimensions'),('pocket-large.png','excess byte budget')]:
            note_screen(); pick_image(filename)
            ok(find(**{'content-desc':'v12-status','text':'图片未加入：仅支持有效 PNG/JPEG，最大 8 MiB、2000 万像素、单边 16384'}) is not None,label+' selected image rejected visibly')
            stop()
            with sqlite3.connect(copy_db('reject-'+filename+'.db')) as db:
                ok({t:db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall() for t in TABLES}==baseline,label+' rejection preserves every database table including revision')
        note_screen(); pick_image('pocket-selected.png'); ready(); stop()
        chosen_id=hashlib.sha256(chosen).hexdigest()
        with sqlite3.connect(copy_db('pick-success.db')) as db:
            selected_blocks=db.execute('SELECT * FROM blocks ORDER BY note_id,position').fetchall()
            ok(len(selected_blocks)==3 and selected_blocks[:2]==[tuple(row) for row in expected_blocks] and selected_blocks[2][2:]==(2,'IMAGE','',chosen_id,'',0,None),'SAF image appends one exact ordered block without replacing text or prior image')
            ok(db.execute('SELECT id,mime,bytes FROM media WHERE id=?',(chosen_id,)).fetchall()==[(chosen_id,'image/png',len(chosen))],'SAF original bytes registered by exact hash MIME and length')
            ok(all(db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall()==baseline[t] for t in TABLES if t not in ('revision','blocks','media')),'image import preserves notes identity and all unrelated tables')
        copied=subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','files/media/'+chosen_id],timeout=30)
        ok(copied==chosen,'SAF private copy equals independently generated two-color PNG byte for byte')
        shell('rm','/sdcard/Download/pocket-selected.png')
        note_screen(); swipe_up()
        ok(desc('note-image-'+selected_blocks[2][1]).get('class')=='android.widget.ImageView','selected image still renders after source deletion and stopped-process restart')
        shot('11-selected-image.png'); stop()
        with sqlite3.connect(copy_db('pick-restart.db')) as db:
            ok(db.execute('SELECT * FROM blocks ORDER BY note_id,position').fetchall()==selected_blocks,'selected image block identity order and reference survive restart')
        ok(subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','files/media/'+chosen_id],timeout=30)==chosen,'source deletion never removes or changes the private selected image')
        # Stage14: prove actual JPEG selection, inclusive pixel budget and image-first note.
        # Fixtures stay synthetic. Host ImageIO is independent of Android BitmapFactory.
        edge_ok=png(5000,4000); edge_bad=png(5000,4001)
        assert 5000*4000==20000000 and 5000*4001>20000000 and max(5000,4001)<16384
        assert max(len(edge_ok),len(edge_bad))<8*1024*1024,'pixel fixtures must not hit byte or edge rejection first'
        (fixture_dir/'pocket-pixel-limit.png').write_bytes(edge_ok)
        (fixture_dir/'pocket-pixel-over.png').write_bytes(edge_bad)
        source=helper/'ImageImportFixture.java'
        source.write_text('''import java.awt.image.BufferedImage;
import java.io.File;
import javax.imageio.ImageIO;
import javax.imageio.ImageReader;
import javax.imageio.stream.ImageInputStream;
public class ImageImportFixture {
 static void verify(File file,String format,int width,int height) throws Exception {
  try(ImageInputStream in=ImageIO.createImageInputStream(file)){
   ImageReader reader=ImageIO.getImageReaders(in).next(); reader.setInput(in);
   if(!reader.getFormatName().equalsIgnoreCase(format))throw new AssertionError("format");
   BufferedImage image=reader.read(0);
   if(image.getWidth()!=width||image.getHeight()!=height)throw new AssertionError("dimensions");
   int[] expected={0xffdc4628,0xff235ad2};
   for(int half=0;half<2;half++){
    int pixel=image.getRGB(half==0?10:width-11,height/2);
    for(int shift:new int[]{0,8,16})if(Math.abs(((pixel>>shift)&255)-((expected[half]>>shift)&255))>3)
     throw new AssertionError("fixture decoded color");
   }
   image.flush();reader.dispose();
  }
 }
 public static void main(String[] args)throws Exception{
  File dir=new File(args[0]); BufferedImage image=new BufferedImage(1600,900,BufferedImage.TYPE_INT_RGB);
  for(int y=0;y<900;y++)for(int x=0;x<1600;x++)image.setRGB(x,y,x<800?0xffdc4628:0xff235ad2);
  File jpeg=new File(dir,"pocket-first.jpg");
  if(!ImageIO.write(image,"jpeg",jpeg))throw new AssertionError("JPEG encoder missing");
  image.flush();verify(jpeg,"JPEG",1600,900);
  verify(new File(dir,"pocket-pixel-limit.png"),"PNG",5000,4000);
  verify(new File(dir,"pocket-pixel-over.png"),"PNG",5000,4001);
  System.out.println("IMAGE_IMPORT_FIXTURES_PASS JPEG=1600x900 PNG=20000000/20005000");
 }
}
''')
        run(['javac','-d',helper,source],timeout=40)
        fixture_result=run(['java','-Djava.awt.headless=true','-cp',helper,'ImageImportFixture',fixture_dir],timeout=60,capture=True).stdout
        ok(fixture_result.strip()=='IMAGE_IMPORT_FIXTURES_PASS JPEG=1600x900 PNG=20000000/20005000','independent host decoder proves JPEG and both pixel boundary fixtures really decode with intended dimensions and colors')
        jpeg=(fixture_dir/'pocket-first.jpg').read_bytes(); jpeg_id=hashlib.sha256(jpeg).hexdigest()
        assert jpeg[:2]==b'\xff\xd8' and len(jpeg)<8*1024*1024,'JPEG fixture must satisfy its independent byte precondition'
        for name in ('pocket-first.jpg','pocket-pixel-limit.png','pocket-pixel-over.png'):
            run([adb,'-s',SERIAL,'push',fixture_dir/name,'/sdcard/Download/'+name])
        start();tap('活动');ready();touch('category-add-1');touch('活动名称');type_text('Image first');tap('保存');ready()
        first_desc=reveal_activity(nodes,swipe_summary,PKG,title='Image first').get('content-desc','')
        assert re.fullmatch(r'activity-\d+',first_desc) and first_desc!='activity-1','new visible activity must have an independent identity'
        first_activity=int(first_desc.split('-')[1]);stop()
        def state_read(name):
            with sqlite3.connect(copy_db(name)) as db:
                return {t:db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall() for t in TABLES}
        first_base=state_read('first-image-base.db')
        verify_first_activity(first_base['activities'],first_activity)
        ok(not any(row[1]==first_activity for row in first_base['notes']),'new image-first activity has no existing note in independent SQLite read')
        def first_screen():
            start();tap('活动');ready();tap_node(reveal_activity(nodes,swipe_summary,PKG,identity=first_desc));ready();tap('笔记');ready()
        first_screen();ok(find(text='写点什么，或加一张图。') is not None,'image-first activity shows genuine empty note before any import')
        pick_image()
        ok((checked_fixture('pocket-first.jpg',False) if API==34 else find(text='pocket-first.jpg').get('package','').endswith('documentsui')),'first-image cancellation waits for a visible system picker before pressing Back')
        ok(cancel_note_picker('first_image'),'canceling first image reports no note change')
        stop();ok(state_read('first-image-cancel.db')==first_base,'first-image cancel creates no orphan note media block or revision')
        for filename,label in [('pocket-broken.png','malformed first image'),('pocket-pixel-over.png','20005000-pixel first image')]:
            first_screen();pick_image(filename)
            ok(find(**{'content-desc':'v12-status','text':'图片未加入：仅支持有效 PNG/JPEG，最大 8 MiB、2000 万像素、单边 16384'}) is not None,label+' rejected visibly before note creation')
            stop();ok(state_read('first-reject-'+filename+'.db')==first_base,label+' leaves every table unchanged with no orphan note or media registration')
        first_screen();pick_image('pocket-first.jpg');ready();stop()
        first_saved=state_read('first-image-saved.db')
        new_notes=[row for row in first_saved['notes'] if row not in first_base['notes']]
        ok(len(new_notes)==1 and new_notes[0][1:]==(first_activity,'Image first') and all(row in first_saved['notes'] for row in first_base['notes']),'JPEG-first import creates exactly one note with correct activity binding title and preserved prior notes')
        first_note=new_notes[0][0]
        new_blocks=[row for row in first_saved['blocks'] if row not in first_base['blocks']]
        ok(len(new_blocks)==1 and new_blocks[0][0]==first_note and new_blocks[0][2:]==(0,'IMAGE','',jpeg_id,'',0,None) and all(row in first_saved['blocks'] for row in first_base['blocks']),'JPEG-first import creates exactly one position-zero public image block without touching previous blocks')
        ok([row for row in first_saved['media'] if row not in first_base['media']]==[(jpeg_id,'image/jpeg',len(jpeg))] and all(row in first_saved['media'] for row in first_base['media']),'JPEG-first media registry has exact actual MIME digest and original byte length')
        ok(all(first_saved[t]==first_base[t] for t in TABLES if t not in ('revision','notes','blocks','media')),'JPEG-first note creation preserves activities todos checkins ledger and all unrelated tables')
        def private_bytes(asset_id):
            assert re.fullmatch(r'[0-9a-f]{64}',asset_id),'only safe digest IDs enter private file paths'
            return subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','files/media/'+asset_id],timeout=30)
        ok(private_bytes(jpeg_id)==jpeg,'selected JPEG private original is byte-exact rather than a recompressed preview')
        shell('rm','/sdcard/Download/pocket-first.jpg');first_screen()
        ok(desc('note-image-'+new_blocks[0][1]).get('class')=='android.widget.ImageView','JPEG-first note displays a real ImageView after external source deletion and process restart')
        shot('12-jpeg-first-note.png');stop()
        ok(state_read('first-image-restart.db')==first_saved and private_bytes(jpeg_id)==jpeg,'JPEG-first restart preserves every database table and exact private JPEG bytes')
        first_screen();pick_image('pocket-pixel-limit.png');ready();stop()
        limit_saved=state_read('pixel-limit-saved.db');limit_id=hashlib.sha256(edge_ok).hexdigest()
        limit_blocks=[row for row in limit_saved['blocks'] if row not in first_saved['blocks']]
        ok(len(limit_blocks)==1 and limit_blocks[0][0]==first_note and limit_blocks[0][2:]==(1,'IMAGE','',limit_id,'',0,None) and all(row in limit_saved['blocks'] for row in first_saved['blocks']),'exactly 20000000 pixels is accepted inclusively as one appended ordered image block')
        ok([row for row in limit_saved['media'] if row not in first_saved['media']]==[(limit_id,'image/png',len(edge_ok))] and all(row in limit_saved['media'] for row in first_saved['media']) and private_bytes(limit_id)==edge_ok,'pixel-limit image keeps exact private original and matching media registry')
        ok(all(limit_saved[t]==first_saved[t] for t in TABLES if t not in ('revision','blocks','media')),'pixel-limit import preserves note identity and unrelated complete tables')
        shell('rm','/sdcard/Download/pocket-pixel-limit.png');first_screen();swipe_up()
        ok(desc('note-image-'+limit_blocks[0][1]).get('class')=='android.widget.ImageView','20000000-pixel image remains an ImageView after source deletion and restart')
        shot('13-pixel-limit-image.png');stop()
        ok(state_read('pixel-limit-restart.db')==limit_saved and private_bytes(limit_id)==edge_ok,'pixel-limit restart preserves exact complete database and original image bytes')
        # Multiple notes use only visible UI; independent full-table reads guard isolation.
        note_screen()
        ok(desc('note-current').get('text')=='Daily reward · 1 / 1','existing single note remains the initial selected note')
        tap('新建笔记');tap('创建')
        ok(find(text='笔记标题不能为空') is not None,'blank new note title stays in dialog without creating a note')
        touch('笔记标题');type_text('Discard new note');tap('取消');stop()
        ok(state_read('multi-cancel.db')==limit_saved,'canceling a populated new-note dialog preserves every table and revision')
        note_screen();tap('新建笔记');touch('笔记标题');type_text('Second note');tap('创建');ready()
        ok(desc('note-current').get('text')=='Second note · 2 / 2' and find(text='写点什么，或加一张图。') is not None and absent('Watered 35 min today'),'new note selects its own empty content instead of copying the first note')
        tap('加入文字');touch('文字内容');type_text('Second content');tap('保存');ready();stop()
        multi_saved=state_read('multi-created.db')
        added_notes=[row for row in multi_saved['notes'] if row not in limit_saved['notes']]
        ok(len(added_notes)==1 and added_notes[0][1:]==(1,'Second note') and all(row in multi_saved['notes'] for row in limit_saved['notes']),'second note has one fresh identity correct owner title and unchanged old notes')
        second_id=added_notes[0][0]
        added_blocks=[row for row in multi_saved['blocks'] if row not in limit_saved['blocks']]
        ok(len(added_blocks)==1 and added_blocks[0][0]==second_id and added_blocks[0][2:]==(0,'TEXT','Second content',None,'',0,None) and all(row in multi_saved['blocks'] for row in limit_saved['blocks']),'second note owns exactly its text block while all first-note and other-activity blocks remain exact')
        ok(all(multi_saved[t]==limit_saved[t] for t in TABLES if t not in ('revision','notes','blocks')),'creating and editing second note preserves media ledger checkins and all unrelated tables')
        note_screen()
        ok(desc('note-current').get('text')=='Daily reward · 1 / 2' and find(text='Watered 35 min today') is not None,'restart opens original first note without replacing its content')
        tap('切换笔记')
        ok([n.get('text') for n in nodes() if n.get('text') in ('1. Daily reward','2. Second note')]==['1. Daily reward','2. Second note'],'note picker exposes both titles in stable creation order')
        tap('取消');ready()
        ok(desc('note-current').get('text')=='Daily reward · 1 / 2','canceling note switch keeps selected note')
        tap('切换笔记');tap('2. Second note');ready()
        ok(desc('note-current').get('text')=='Second note · 2 / 2' and find(text='Second content') is not None and absent('Watered 35 min today'),'explicit selection restores second note alone after process restart')
        touch('note-edit-'+added_blocks[0][1]);clear_field('文字内容');type_text('Second edited');tap('保存');ready()
        ok(desc('note-current').get('text')=='Second note · 2 / 2' and find(text='Second edited') is not None,'editing second note stays on selected stable note instead of jumping to first')
        tap('切换笔记');tap('1. Daily reward');ready()
        ok(find(text='Watered 35 min today') is not None and absent('Second edited'),'switching back preserves original first-note text')
        swipe_up()
        ok(desc('note-image-'+selected_blocks[2][1]).get('class')=='android.widget.ImageView','first note retains its imported image after multi-note editing')
        shot('14-multiple-notes.png');stop()
        multi_edited=state_read('multi-edited.db')
        updated=list(added_blocks[0]);updated[4]='Second edited'
        ok(multi_edited['notes']==multi_saved['notes'] and sorted(multi_edited['blocks'])==sorted(limit_saved['blocks']+[tuple(updated)]),'independent readback proves only second text changed with all note and block identities intact')
        ok(all(multi_edited[t]==multi_saved[t] for t in TABLES if t not in ('revision','blocks')) and private_bytes(chosen_id)==chosen and private_bytes(jpeg_id)==jpeg and private_bytes(limit_id)==edge_ok,'multi-note edits preserve unrelated tables and all selected private originals byte for byte')
        note_screen();tap('新建笔记');touch('笔记标题');type_text('Second note');tap('创建');ready()
        ok(desc('note-current').get('text')=='Second note · 3 / 3' and find(text='写点什么，或加一张图。') is not None,'duplicate note title creates a separate empty note rather than overwriting its namesake')
        stop();multi_duplicate=state_read('multi-duplicate.db')
        duplicate_rows=[row for row in multi_duplicate['notes'] if row not in multi_edited['notes']]
        ok(len(duplicate_rows)==1 and duplicate_rows[0][1:]==(1,'Second note') and duplicate_rows[0][0]!=second_id and all(row in multi_duplicate['notes'] for row in multi_edited['notes']) and all(multi_duplicate[t]==multi_edited[t] for t in TABLES if t not in ('revision','notes')),'same-title creation adds only one distinct note and never touches existing blocks or unrelated tables')
        note_screen();tap('切换笔记')
        ok([n.get('text') for n in nodes() if n.get('text') in ('1. Daily reward','2. Second note','3. Second note')]==['1. Daily reward','2. Second note','3. Second note'],'restart preserves creation order and separate indexed entries for duplicate titles')
        tap('2. Second note');ready()
        ok(find(text='Second edited') is not None,'same-title note selection resolves exact second identity not latest matching title')
        shot('15-second-note.png');stop()
        ok(state_read('multi-final.db')==multi_duplicate,'switching and restarting notes are read-only across the complete database')
        # Stage16: a reused original creates a fresh block on the selected non-first
        # note. Metadata edits must never rewrite media or sibling notes.
        run([adb,'-s',SERIAL,'push',fixture_dir/'pocket-first.jpg','/sdcard/Download/pocket-first.jpg'])
        def second_screen():
            note_screen();tap('切换笔记');tap('2. Second note');ready()
        second_screen();pick_image('pocket-first.jpg');ready()
        ok(desc('note-current').get('text')=='Second note · 2 / 3' and find(text='Second edited') is not None,'image append retains the non-first selected note and its existing text')
        stop();second_image=state_read('second-image.db')
        image_rows=[row for row in second_image['blocks'] if row not in multi_duplicate['blocks']]
        ok(len(image_rows)==1 and image_rows[0][0]==second_id and image_rows[0][2:]==(1,'IMAGE','',jpeg_id,'',0,None) and all(row in second_image['blocks'] for row in multi_duplicate['blocks']),'non-first image import appends exactly one correctly owned ordered block without modifying any old block')
        second_image_row=image_rows[0];second_image_id=second_image_row[1]
        ok(all(second_image[t]==multi_duplicate[t] for t in TABLES if t not in ('revision','blocks')) and private_bytes(jpeg_id)==jpeg,'reused JPEG import preserves notes complete media registry unrelated tables and exact original')
        shell('rm','/sdcard/Download/pocket-first.jpg');second_screen()
        ok(desc('note-image-'+second_image_id).get('class')=='android.widget.ImageView','non-first note image survives source deletion and explicit reselect after restart')
        touch('note-image-edit-'+second_image_id)
        ok(desc('image-caption').get('text','')=='' and desc('image-private').get('checked')=='false','new image metadata editor starts with empty caption and public flag')
        touch('image-caption');type_text('Discard caption');touch('image-private');tap('取消');stop()
        ok(state_read('image-metadata-cancel.db')==second_image and private_bytes(jpeg_id)==jpeg,'canceling edited caption and privacy preserves every table revision and original bytes')
        second_screen();touch('note-image-edit-'+second_image_id);touch('image-caption');type_text('Private caption');touch('image-private');tap('保存');ready()
        ok(desc('note-current').get('text')=='Second note · 2 / 3' and find(text='Private caption') is not None and desc('note-image-privacy-'+second_image_id).get('text')=='私有图片','caption and private badge render on the selected second note after saving')
        stop();private_saved=state_read('image-private-saved.db')
        private_row=list(second_image_row);private_row[6]='Private caption';private_row[7]=1;private_row=tuple(private_row)
        expected=[private_row if row==second_image_row else row for row in second_image['blocks']]
        ok(sorted(private_saved['blocks'])==sorted(expected),'private caption save changes only caption and privacy while retaining every block identity owner order and asset reference')
        ok(all(private_saved[t]==second_image[t] for t in TABLES if t not in ('revision','blocks')) and private_bytes(jpeg_id)==jpeg and private_bytes(chosen_id)==chosen and private_bytes(limit_id)==edge_ok,'metadata edit preserves complete unrelated tables media registrations and all imported originals')
        second_screen();touch('note-image-edit-'+second_image_id)
        ok(desc('image-caption').get('text')=='Private caption' and desc('image-private').get('checked')=='true','restart and reselect prefill the persisted caption and true private flag')
        tap('取消');tap('切换笔记');tap('1. Daily reward');ready()
        ok(find(text='Watered 35 min today') is not None and absent('Private caption'),'editing second image metadata does not leak its caption into first note')
        tap('切换笔记');tap('3. Second note');ready()
        ok(find(text='写点什么，或加一张图。') is not None and absent('Private caption'),'same-title third note stays empty after second note image edits')
        stop();ok(state_read('image-private-switch.db')==private_saved,'restart and switching across private-image notes are read-only for every table')
        second_screen();touch('note-image-edit-'+second_image_id);clear_field('image-caption');type_text('Updated private');tap('保存');ready();stop()
        private_updated=state_read('image-private-updated.db')
        updated_private=list(private_row);updated_private[6]='Updated private';updated_private=tuple(updated_private)
        ok(sorted(private_updated['blocks'])==sorted([updated_private if row==private_row else row for row in private_saved['blocks']]),'caption-only edit preserves existing true private flag and all other block fields')
        ok(all(private_updated[t]==private_saved[t] for t in TABLES if t not in ('revision','blocks')) and private_bytes(jpeg_id)==jpeg,'caption-only private edit leaves all unrelated tables and immutable original unchanged')
        second_screen();shot('16-private-image-caption.png');touch('note-image-edit-'+second_image_id)
        ok(desc('image-caption').get('text')=='Updated private' and desc('image-private').get('checked')=='true','updated private caption survives another force-stop and explicit note selection')
        clear_field('image-caption');touch('image-private');tap('保存');ready()
        ok(desc('note-image-privacy-'+second_image_id).get('text')=='非私有图片' and absent('Updated private'),'empty caption is allowed and private flag can be explicitly unset')
        stop();public_saved=state_read('image-public-empty.db')
        ok(sorted(public_saved['blocks'])==sorted(second_image['blocks']) and all(public_saved[t]==second_image[t] for t in TABLES if t not in ('revision','blocks')),'clearing caption and unsetting private restores exact original block fields without touching siblings or other tables')
        second_screen();touch('note-image-edit-'+second_image_id)
        ok(desc('image-caption').get('text','')=='' and desc('image-private').get('checked')=='false','empty caption and false private flag persist after restart')
        tap('取消');ready();shot('17-second-image-public.png');stop()
        ok(state_read('image-final-restart.db')==public_saved and private_bytes(jpeg_id)==jpeg,'final metadata cancel and restart preserve every table and exact JPEG original')
        # Stage19: real touch crop/redaction UI over the accepted derivative backend.
        # Selection rects come from the dialog's own source-pixel reports; host pixel
        # proof uses those reported values, never fixture-hardcoded geometry.
        derive_base=state_read('derive-base.db')
        derive_block=selected_blocks[2][1]
        derive_geometry=[]
        derive_note='1. Daily reward'
        def daily_note():
            note_screen();tap('切换笔记');tap(derive_note);ready()
        def reveal(description):
            for attempt in range(8):
                current=nodes()
                for n in current:
                    if n.get('content-desc')==description:
                        bounds=list(map(int,re.findall(r'\d+',n.get('bounds'))))
                        if bounds[2]>bounds[0] and bounds[3]>bounds[1]:return n
                swipe_up()
            raise AssertionError('derivative control not visible after bounded scroll: '+description)
        def open_derive():
            tap_node(reveal('note-image-derive-'+derive_block))
            canvas=re.findall(r'\d+',desc('derive-canvas').get('bounds'))
            cx1,cy1,cx2,cy2=map(int,canvas)
            assert cx2>cx1 and cy2>cy1,'selection canvas must have real bounds'
            dims=re.fullmatch(r'原图 (\d+) × (\d+) · 预览 (\d+) × (\d+)',desc('derive-source').get('text'))
            assert dims,'source and preview dimensions report missing'
            sw,sh,pw,ph=map(int,dims.groups())
            def screen(sx,sy):
                live=list(map(int,re.findall(r'\d+',desc('derive-canvas').get('bounds'))))
                bx1,by1,bx2,by2=live
                bw,bh=bx2-bx1,by2-by1
                sc=min(bw/pw,bh/ph);ox=(bw-pw*sc)/2;oy=(bh-ph*sc)/2
                return (round(bx1+ox+sx*pw/sw*sc),round(by1+oy+sy*ph/sh*sc))
            def drag(a,b,c,d):
                x1,y1=screen(a,b);x2,y2=screen(c,d)
                derive_geometry.append({'source':[sw,sh],'preview':[pw,ph],
                    'requested':[a,b,c,d],'screen':[x1,y1,x2,y2],
                    'canvas':desc('derive-canvas').get('bounds')})
                shell('input','swipe',str(x1),str(y1),str(x2),str(y2),'400');time.sleep(.3)
            return (sw,sh),drag
        def wait_crop():
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                found=re.fullmatch(r'裁剪 (\d+),(\d+) → (\d+),(\d+)',desc('derive-crop').get('text') or '')
                if found:
                    observed=tuple(map(int,found.groups()))
                    derive_geometry[-1]['observed_crop']=observed
                    print('DERIVATIVE_GEOMETRY '+json.dumps(derive_geometry[-1]),flush=True)
                    return observed
                time.sleep(.25)
            raise AssertionError('crop report never appeared')
        def wait_report(desc_id,value):
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                if desc(desc_id).get('text')==value:return
                time.sleep(.25)
            raise AssertionError(desc_id+' never became '+value)
        daily_note();(sw,sh),drag=open_derive()
        ok((sw,sh)==(1536,768) and desc('derive-crop').get('text')=='未选择裁剪区域' and desc('derive-masks').get('text')=='遮挡 0 处','derivative dialog shows actual decoded source dimensions with empty selection')
        tap('预览')
        ok(find(text='尚未选择：请拖出裁剪区域，或在遮挡模式涂抹') is not None,'derivative preview without selection rejected visibly')
        tap('取消');stop()
        ok(state_read('derive-cancel-empty.db')==derive_base and private_bytes(chosen_id)==chosen,'derivative cancel leaves every table and original bytes unchanged')
        daily_note();(sw,sh),drag=open_derive()
        drag(0,0,sw,sh)
        fl,ft,fr,fb=wait_crop()
        ok(abs(fl)<=4 and abs(ft)<=4 and abs(fr-sw)<=4 and abs(fb-sh)<=4,'corner drag maps to full source extent within touch rounding')
        tap('预览')
        ok(find(text='选区过大：派生图最多 100 万像素') is not None,'derivative oversize selection rejected with visible pixel budget')
        tap('重置选区');wait_report('derive-crop','未选择裁剪区域');wait_report('derive-masks','遮挡 0 处')
        ok(True,'derivative reset clears selection reports')
        tap('取消');stop()
        assert state_read('derive-reject-reset.db')==derive_base and private_bytes(chosen_id)==chosen,'oversize rejection/reset must preserve complete state and original'
        # Keep the 1536x768 oversize negative above. A success source must itself
        # satisfy the codec limit, not merely have a crop below one million pixels.
        derive_input=png(1280,640);derive_source_id=hashlib.sha256(derive_input).hexdigest()
        assert 1280*640<=1000000 and 1280<=2048 and len(derive_input)<8*1024*1024
        path=fixture_dir/'pocket-derive-valid.png';path.write_bytes(derive_input)
        run([adb,'-s',SERIAL,'push',path,'/sdcard/Download/pocket-derive-valid.png'])
        second_screen();pick_image('pocket-derive-valid.png');ready();stop()
        derive_new=state_read('derive-valid-import.db')
        derive_rows=[row for row in derive_new['blocks'] if row not in derive_base['blocks']]
        assert len(derive_rows)==1 and derive_rows[0][0]==second_id and derive_rows[0][2:]==(2,'IMAGE','',derive_source_id,'',0,None),'legal source must target exact non-first note'
        assert all(row in derive_new['blocks'] for row in derive_base['blocks']),'legal fixture import altered sibling'
        assert all(derive_new[t]==derive_base[t] for t in TABLES if t not in ('revision','blocks','media')),'legal fixture import altered unrelated tables'
        assert [row for row in derive_new['media'] if row not in derive_base['media']]==[(derive_source_id,'image/png',len(derive_input))] and private_bytes(derive_source_id)==derive_input,'legal fixture registry or private copy differs'
        derive_base=derive_new;derive_block=derive_rows[0][1];derive_note='2. Second note'
        shell('rm','/sdcard/Download/pocket-derive-valid.png')
        daily_note();(sw,sh),drag=open_derive()
        assert (sw,sh)==(1280,640),'legal source dimensions must be decoded, not guessed'
        drag(320,160,960,480)
        cl,ct,cr,cb=wait_crop()
        ok(abs(cl-320)<=4 and abs(ct-160)<=4 and abs(cr-960)<=4 and abs(cb-480)<=4,'touch crop maps onto intended source rectangle within rounding')
        tap('遮挡模式');drag(640,240,800,400)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            mask_text=desc('derive-masks').get('text') or ''
            if mask_text.startswith('遮挡 1 处'):break
            time.sleep(.25)
        masks_found=re.findall(r'(\d+),(\d+) → (\d+),(\d+)',mask_text)
        ok(mask_text.startswith('遮挡 1 处') and len(masks_found)==1,'redact mode adds exactly one reported mask')
        ml,mt,mr,mb=map(int,masks_found[0])
        derive_geometry[-1]['observed_mask']=[ml,mt,mr,mb]
        ok(abs(ml-640)<=4 and abs(mt-240)<=4 and abs(mr-800)<=4 and abs(mb-400)<=4,'touch mask maps onto intended source rectangle within rounding')
        tap('预览');find(text='保存')
        preview_class=reveal('derive-result').get('class')
        output=re.fullmatch(r'派生预览 (\d+) × (\d+)',reveal('derive-output').get('text') or '')
        assert output,'derivative output dimensions missing'
        ow,oh=map(int,output.groups())
        ok((ow,oh)==(cr-cl,cb-ct) and preview_class=='android.widget.ImageView','derivative preview renders exact reported output dimensions')
        shot('18-derivative-preview.png')
        tap('保存');gone('保存');ready();stop()
        saved=state_read('derive-saved.db')
        target=[row for row in saved['blocks'] if row[1]==derive_block]
        assert len(target)==1,'derived block identity lost'
        derived_row=target[0];derived_id=derived_row[5]
        assert re.fullmatch(r'[0-9a-f]{64}',derived_id) and derived_id!=derive_source_id,'derived asset must be a new content id'
        ok(derived_row[0]==second_id and derived_row[2:5]==(2,'IMAGE','') and derived_row[6:]==('',0,derive_source_id),'derived block preserves note owner position kind empty caption public flag and records exact original')
        derivative_bytes=private_bytes(derived_id)
        added_media=[row for row in saved['media'] if row not in derive_base['media']]
        ok(added_media==[(derived_id,'image/png',len(derivative_bytes))],'derived PNG registered with exact mime and byte length')
        ok(all(saved[t]==derive_base[t] for t in TABLES if t not in ('revision','blocks','media')),'derivative save preserves all unrelated tables')
        ok(private_bytes(derive_source_id)==derive_input and private_bytes(chosen_id)==chosen,'original imported PNG bytes unchanged after derivative save')
        siblings=[row for row in derive_base['blocks'] if row[1]!=derive_block]
        ok(all(row in saved['blocks'] for row in siblings) and len(saved['blocks'])==len(derive_base['blocks']),'sibling blocks across notes remain exact after derivative save')
        source_png=(out/'derivative-source.png').resolve();source_png.write_bytes(derive_input)
        derived_png=(out/'derivative-output.png').resolve();derived_png.write_bytes(derivative_bytes)
        pixels=run(['java','-Djava.awt.headless=true','-cp',helper,'VerifyDerivative',source_png,derived_png,str(cl),str(ct),str(cr),str(cb),str(ml),str(mt),str(mr),str(mb)],timeout=60,capture=True).stdout
        ok(pixels.strip()=='DERIVATIVE_PIXELS_PASS '+str(cr-cl)+'x'+str(cb-ct),'independent decoder proves exact cropped pixels and opaque mask for reported rects')
        daily_note()
        ok(reveal('note-image-'+derive_block).get('class')=='android.widget.ImageView' and reveal('note-image-derive-'+derive_block).get('enabled')=='true','derived image renders with working entry after process restart')
        shot('19-derivative-saved.png');stop()
        ok(state_read('derive-restart.db')==saved and private_bytes(derived_id)==derivative_bytes and private_bytes(derive_source_id)==derive_input and private_bytes(chosen_id)==chosen,'derivative state and both images survive stopped-process restart exactly')
        daily_note();(dw,dh),drag=open_derive()
        drag(0,0,dw//2,dh//2)
        tap('预览');find(text='保存')
        ok(reveal('derive-result').get('class')=='android.widget.ImageView','re-derived preview renders for abandonment check')
        tap('取消');stop()
        ok(state_read('derive-abandon.db')==saved and private_bytes(derived_id)==derivative_bytes,'abandoned second preview writes nothing and keeps published derivative')
        with sqlite3.connect(copy_db('schema3-final.db')) as db:
            origins=db.execute('SELECT id,original_asset_id FROM blocks WHERE original_asset_id IS NOT NULL').fetchall()
            ok(db.execute('PRAGMA user_version').fetchone()==(3,) and db.execute('SELECT count(*) FROM blocks').fetchone()[0]>0 and origins==[(derive_block,derive_source_id)],'native schema3 survives SAF restore and all ordinary edits without invented image origins')
        # Stage20: accurate derivative refusals, a visible late save failure, then one persistent
        # JPEG-source derivative with an independent decode oracle. The refusal parts persist nothing;
        # the JPEG part adds exactly one imported JPEG block in the first note and its derived PNG, which
        # the share phase now expects (PNG and JPEG derivative fixtures). Recorded beside, never inside,
        # the fixed 186-label native contract; own stop and directory-trace lists keep every older
        # evidence list untouched.
        hard_stops=[];hard_traces=[]
        hard_runner=isolated_directory_runner(adb,SERIAL,PKG,hard_traces)
        geometry_start=len(derive_geometry)
        def okh(condition,label):
            assert condition,label
            hard_checks.append(label);print('UI_PASS_HARDENING '+label,flush=True)
        def hard_stop():
            return stop_verified(adb,SERIAL,PKG,emit=hard_stops.append)
        def hard_state(name):
            local=out/name
            local.write_bytes(subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','databases/pocket-v12.db'],timeout=30))
            if 'pocket-v12.db-wal' in database_directory(adb,SERIAL,PKG,runner=hard_runner).splitlines():
                Path(str(local)+'-wal').write_bytes(subprocess.check_output([str(adb),'-s',SERIAL,'exec-out','run-as',PKG,'cat','databases/pocket-v12.db-wal'],timeout=30))
            with sqlite3.connect(local) as db:
                return {t:db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall() for t in TABLES}
        def hard_media():
            names=subprocess.check_output([str(adb),'-s',SERIAL,'shell','run-as',PKG,'ls','files/media'],timeout=30).decode().split()
            return sorted(names)
        media_before=hard_media()
        # A 1536x768 source exceeds the codec pixel limit even when the selection is small.
        derive_note='1. Daily reward';derive_block=selected_blocks[2][1]
        daily_note();(sw,sh),drag=open_derive()
        assert (sw,sh)==(1536,768),'oversize-source fixture dimensions must be decoded, not guessed'
        drag(0,0,sw//2,sh//2);ol,ot,orr,ob=wait_crop()
        assert 0<(orr-ol)*(ob-ot)<=1000000,'oversize-source selection itself must stay within the output budget'
        tap('预览')
        okh(find(text=DERIVE_OVERSIZE_MESSAGE) is not None and find(text='预览') is not None,'oversize source with a legal selection names the real pixel limit instead of generic preview failure')
        tap('取消');hard_stop()
        okh(hard_state('hardening-oversize.db')==saved and private_bytes(chosen_id)==chosen and private_bytes(derived_id)==derivative_bytes,'oversize source refusal and cancel leave every table and every original byte unchanged')
        # Hold the current image file after a valid preview, so the final save fails before any commit.
        derive_note='2. Second note';derive_block=derived_row[1]
        daily_note();(dw,dh),drag=open_derive()
        drag(0,0,dw//2,dh//2);wait_crop();tap('预览');find(text='保存')
        held='files/media/'+derived_id
        subprocess.check_output([str(adb),'-s',SERIAL,'shell','run-as',PKG,'mv',held,held+'.held'],timeout=30)
        try:
            tap('保存')
            okh(find(**{'content-desc':'v12-status','text':DERIVE_SAVE_FAILED_MESSAGE}) is not None,'late derivative save failure shows the exact visible message')
        finally:
            subprocess.check_output([str(adb),'-s',SERIAL,'shell','run-as',PKG,'mv',held+'.held',held],timeout=30)
        hard_stop()
        okh(hard_state('hardening-save-failed.db')==saved and hard_media()==media_before and private_bytes(derived_id)==derivative_bytes and private_bytes(derive_source_id)==derive_input and private_bytes(chosen_id)==chosen,'late derivative save failure and cancel leave every table and every original byte unchanged')
        # Persistent JPEG-source derivative. A flat 8x8-block gray JPEG decodes identically in every
        # baseline decoder, so the host ImageIO oracle can demand exact pixels from the Android output.
        jpeg_input=make_derivative_jpeg(fixture_dir);jpeg_id=hashlib.sha256(jpeg_input).hexdigest()
        assert jpeg_id not in (chosen_id,derive_source_id,derived_id)
        jpeg_path=fixture_dir/'pocket-derive-source.jpg';jpeg_path.write_bytes(jpeg_input)
        run([adb,'-s',SERIAL,'push',jpeg_path,'/sdcard/Download/pocket-derive-source.jpg'])
        jpeg_base=hard_state('hardening-jpeg-base.db')
        assert jpeg_base==saved,'JPEG stage must start from the exact accepted native state'
        note_screen();pick_image('pocket-derive-source.jpg');ready();hard_stop()
        jpeg_new=hard_state('hardening-jpeg-import.db')
        jpeg_rows=[row for row in jpeg_new['blocks'] if row not in jpeg_base['blocks']]
        shell('rm','/sdcard/Download/pocket-derive-source.jpg')
        okh(len(jpeg_rows)==1 and jpeg_rows[0][0]==selected_blocks[2][0] and jpeg_rows[0][3]=='IMAGE' and jpeg_rows[0][4:]==('',jpeg_id,'',0,None) and
            all(row in jpeg_new['blocks'] for row in jpeg_base['blocks']) and
            [row for row in jpeg_new['media'] if row not in jpeg_base['media']]==[(jpeg_id,'image/jpeg',len(jpeg_input))] and
            private_bytes(jpeg_id)==jpeg_input and
            all(jpeg_new[t]==jpeg_base[t] for t in TABLES if t not in ('revision','blocks','media')),
            'JPEG source imports into the first note as one exact block with exact private bytes and registry')
        derive_note='1. Daily reward';derive_block=jpeg_rows[0][1]
        daily_note();(jw,jh),drag=open_derive()
        okh((jw,jh)==(640,320) and desc('derive-crop').get('text')=='未选择裁剪区域' and desc('derive-masks').get('text')=='遮挡 0 处',
            'JPEG derivative dialog shows actual decoded JPEG dimensions with empty selection')
        drag(96,64,544,256);jl,jt,jr,jb=wait_crop()
        assert abs(jl-96)<=4 and abs(jt-64)<=4 and abs(jr-544)<=4 and abs(jb-256)<=4,'JPEG touch crop must map onto the intended source rectangle'
        tap('遮挡模式');drag(240,112,400,208)
        deadline=time.monotonic()+20;jpeg_mask_text=''
        while time.monotonic()<deadline:
            jpeg_mask_text=desc('derive-masks').get('text') or ''
            if jpeg_mask_text.startswith('遮挡 1 处'):break
            time.sleep(.25)
        jpeg_masks=re.findall(r'(\d+),(\d+) → (\d+),(\d+)',jpeg_mask_text)
        assert jpeg_mask_text.startswith('遮挡 1 处') and len(jpeg_masks)==1,'JPEG redact mode must report exactly one mask'
        jml,jmt,jmr,jmb=map(int,jpeg_masks[0])
        derive_geometry[-1]['observed_mask']=[jml,jmt,jmr,jmb]
        assert abs(jml-240)<=4 and abs(jmt-112)<=4 and abs(jmr-400)<=4 and abs(jmb-208)<=4,'JPEG touch mask must map onto the intended source rectangle'
        tap('预览');find(text='保存')
        jpeg_output=re.fullmatch(r'派生预览 (\d+) × (\d+)',reveal('derive-output').get('text') or '')
        assert jpeg_output and tuple(map(int,jpeg_output.groups()))==(jr-jl,jb-jt) and reveal('derive-result').get('class')=='android.widget.ImageView','JPEG preview must render the exact reported output size'
        tap('保存');gone('保存');ready();hard_stop()
        jpeg_saved=hard_state('hardening-jpeg-saved.db')
        jpeg_target=[row for row in jpeg_saved['blocks'] if row[1]==derive_block]
        assert len(jpeg_target)==1,'JPEG derived block identity lost'
        jpeg_derived_row=jpeg_target[0];jpeg_derived_id=jpeg_derived_row[5]
        jpeg_derived_bytes=private_bytes(jpeg_derived_id)
        okh(re.fullmatch(r'[0-9a-f]{64}',jpeg_derived_id) is not None and jpeg_derived_id not in (jpeg_id,derive_source_id,derived_id) and
            jpeg_derived_row[0]==jpeg_rows[0][0] and jpeg_derived_row[2:5]==jpeg_rows[0][2:5] and jpeg_derived_row[6:]==('',0,jpeg_id) and
            [row for row in jpeg_saved['media'] if row not in jpeg_new['media']]==[(jpeg_derived_id,'image/png',len(jpeg_derived_bytes))] and
            all(row in jpeg_saved['blocks'] for row in jpeg_new['blocks'] if row[1]!=derive_block) and len(jpeg_saved['blocks'])==len(jpeg_new['blocks']) and
            all(jpeg_saved[t]==jpeg_new[t] for t in TABLES if t not in ('revision','blocks','media')) and
            private_bytes(jpeg_id)==jpeg_input and private_bytes(derive_source_id)==derive_input and private_bytes(chosen_id)==chosen and private_bytes(derived_id)==derivative_bytes,
            'JPEG touch crop and opaque mask save one derived PNG recording the exact JPEG original')
        jsrc=(out/'hardening-jpeg-source.jpg').resolve();jsrc.write_bytes(jpeg_input)
        jout=(out/'hardening-jpeg-derived.png').resolve();jout.write_bytes(jpeg_derived_bytes)
        jpeg_pixels=run(['java','-Djava.awt.headless=true','-cp',helper,'VerifyDerivative',jsrc,jout,str(jl),str(jt),str(jr),str(jb),str(jml),str(jmt),str(jmr),str(jmb)],timeout=60,capture=True).stdout.strip()
        okh(jpeg_pixels=='DERIVATIVE_PIXELS_PASS '+str(jr-jl)+'x'+str(jb-jt),'independent ImageIO decode proves exact cropped pixels and opaque mask for the JPEG source')
        daily_note()
        assert reveal('note-image-'+derive_block).get('class')=='android.widget.ImageView' and reveal('note-image-derive-'+derive_block).get('enabled')=='true','JPEG derived image must render with a working entry after restart'
        hard_stop()
        okh(hard_state('hardening-jpeg-restart.db')==jpeg_saved and private_bytes(jpeg_derived_id)==jpeg_derived_bytes and private_bytes(jpeg_id)==jpeg_input and
            private_bytes(derive_source_id)==derive_input and private_bytes(derived_id)==derivative_bytes and private_bytes(chosen_id)==chosen,
            'JPEG original derived PNG and every table survive stopped-process restart exactly')
        assert hard_checks==HARDENING_LABELS,'hardening stage must record exactly its declared checks'
        hardening_geometry=[dict(entry) for entry in derive_geometry[geometry_start:]]
        del derive_geometry[geometry_start:]
        assert [e.get('source') for e in hardening_geometry]==[[1536,768],[640,320],[640,320],[640,320]],'hardening geometry must stay separate from the one native 1280x640 fixture'
        assert hardening_geometry[2].get('observed_crop')==(jl,jt,jr,jb) and hardening_geometry[3].get('observed_mask')==[jml,jmt,jmr,jmb],'JPEG geometry entries must carry the observed rectangles'
        jpeg_summary={'source':[jw,jh],'crop':[jl,jt,jr,jb],'mask':[jml,jmt,jmr,jmb],'pixels':jpeg_pixels,'source_sha256':jpeg_id,'derived_sha256':jpeg_derived_id,'derived_bytes':len(jpeg_derived_bytes)}
        result={'status':'PASS','scope':'NATIVE_TODO_CATEGORY_ACTIVITY_PATH_CHECKIN_LEDGER_NOTE_RESTORE_SLICE','ledger_calendar':'NATIVE_MULTI_DATE_LEDGER_PASS','saf_restore':'NATIVE_SAF_RESTORE_PREVIEW_CONFIRM_PASS','checkin_history':'NATIVE_CHECKIN_HISTORY_BACKDATE_PASS','note_editor':'NATIVE_TEXT_IMAGE_NOTE_PASS','api':API,'count':len(checks),'checks':checks,'screenshots':shots,'infra_retries':infra_retries,'restore_undo':'NOT_IMPLEMENTED','restore_preview_lifecycle':'NOT_TESTED','checkin_schedules':'NOT_IMPLEMENTED','real_photo_selection':'NOT_IMPLEMENTED','photos':'NOT_TESTED','sharing':'NOT_TESTED','release_ready':False}
        result.update(real_photo_selection='NATIVE_SAF_PNG_PASS',photos='SYNTHETIC_PNG_ONLY',image_picker_lifecycle='CANCEL_AND_RESTART_ONLY',jpeg='NOT_TESTED',camera='NOT_IMPLEMENTED')
        result.update(real_photo_selection='NATIVE_SAF_PNG_JPEG_PASS',photos='SYNTHETIC_PNG_JPEG_ONLY',jpeg='NATIVE_SAF_EXACT_PRIVATE_COPY_PASS',image_first_note='CANCEL_REJECT_CREATE_RESTART_PASS',image_pixel_budget='20000000_ACCEPTED_20005000_REJECTED',exif_orientation='NOT_TESTED',whole_note_memory='NOT_TESTED')
        result.update(multiple_notes='CREATE_SWITCH_EDIT_DUPLICATE_TITLE_RESTART_PASS',note_selection_persistence='RESTART_DEFAULTS_FIRST_EXPLICIT_RESELECT',note_rename_delete_reorder='NOT_IMPLEMENTED')
        result.update(nonfirst_image='APPEND_ISOLATION_RESTART_PASS',image_metadata='CAPTION_PRIVATE_CANCEL_EDIT_CLEAR_RESTART_PASS',private_sharing='NOT_TESTED')
        result.update(default_app_schema=3,default_schema3_ui='NATIVE_SCHEMA3_UI_PASS')
        result.update(derivative_ui='NATIVE_CROP_MASK_UI_SAVE_CANCEL_RESTART_PASS')
        result.update(derivative_hardening={'status':'PASS','scope':'NATIVE_REFUSALS_LATE_SAVE_FAILURE_AND_PERSISTED_JPEG_SOURCE_DERIVATIVE','count':len(hard_checks),'checks':list(hard_checks),'geometry':hardening_geometry,'jpeg_source_derivative':jpeg_summary,'fixture_writer':jpeg_oracle,'process_stops':hard_stops,'directory_traces':hard_traces,'not_tested':['native_rotated_jpeg_import','rotation_during_edit','large_font_scale','low_storage_publication','camera','real_photos','multi_touch_device_cancel']})
        result.update(derivative_geometry=derive_geometry,pixel_oracle=pixel_oracle,process_stops=process_stops)
        result['restore_picker_traces']=restore_picker_traces
        result['summary_navigation_traces']=summary_navigation_traces
        result['image_picker_cancels']=image_picker_cancels
        result['image_fixture_navigation']=image_fixture_navigation
        result['database_directory_traces']=directory_traces
    except Exception as exc:
        result={'status':'FAIL','api':API,'count':len(checks),'checks':checks,'error':repr(exc),'screenshots':shots,'infra_retries':infra_retries,'release_ready':False,'process_stops':process_stops}
        result['restore_picker_traces']=restore_picker_traces
        result['summary_navigation_traces']=summary_navigation_traces
        result['image_picker_cancels']=image_picker_cancels
        result['image_fixture_navigation']=image_fixture_navigation
        result['database_directory_traces']=directory_traces
        if 'derive_geometry' in locals():result['derivative_geometry']=derive_geometry
        result['derivative_hardening_partial']=list(hard_checks)
        if 'pixel_oracle' in locals():result['pixel_oracle']=pixel_oracle
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
    try:
        identity = capture_runtime_identity(adb, emulator,
            SDK / 'system-images' / ('android-' + str(API)) / 'google_apis/x86_64/source.properties',
            avd / 'config.ini')
        Path('ci-runtime-identity.json').write_text(json.dumps(identity, indent=2) + '\n')
        print('CI_RUNTIME_IDENTITY ' + json.dumps(identity), flush=True)
    except Exception as diagnostic:
        print('CI_RUNTIME_IDENTITY_NOT_OBSERVED ' + repr(diagnostic), flush=True)
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
