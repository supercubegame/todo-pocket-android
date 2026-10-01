#!/usr/bin/env python3
"""Single primary installed-APK pull. Host contracts are NOT Android acceptance."""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time


def pull_exact(adb, serial, remote, expected, record, *, invoke=None, clock=None):
    """No retry/fallback. Only the initial export-preflight installed APK is in scope."""
    if serial != "emulator-5554" or not isinstance(remote, str) or not (
            remote.startswith("/data/app/") and remote.endswith("/base.apk")
            and not any(c in remote for c in "\x00\r\n") and ".." not in remote.split("/")):
        raise ValueError("installed emulator APK path required")
    if type(expected) is not bytes or not expected:
        raise ValueError("nonempty frozen built APK bytes required")
    if not isinstance(record, dict) or record:
        raise ValueError("fresh transfer receipt required")
    invoke = subprocess.run if invoke is None else invoke
    clock = time.monotonic if clock is None else clock
    started = clock(); deadline = started + 30
    record.update(status="FAIL", method="ADB_PULL_SINGLE_PRIMARY_EXACT_BYTES",
                  attempts=0, budget_seconds=30, expected_bytes=len(expected),
                  expected_sha256=hashlib.sha256(expected).hexdigest())
    def tail(value):
        if value is None: return None
        return value[-4096:].decode("utf-8", errors="replace") if isinstance(value, bytes) else value[-4096:]
    try:
        with tempfile.TemporaryDirectory(prefix="installed-apk-pull-") as folder:
            destination = Path(folder) / "base.apk"
            if destination.exists() or destination.is_symlink():
                raise AssertionError("transfer destination must be fresh")
            command = [str(adb), "-s", serial, "pull", "-Z", remote, str(destination)]
            remaining = deadline - clock()
            if remaining <= 0:
                raise TimeoutError("installed APK transfer budget exhausted before pull")
            record.update(command=command, stdin="DEVNULL", timeout_seconds=remaining, attempts=1)
            result = invoke(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=remaining)
            record.update(returncode=result.returncode, stdout_tail=tail(result.stdout), stderr_tail=tail(result.stderr))
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
            if clock() >= deadline:
                raise TimeoutError("installed APK pull completed outside original 30 second budget")
            info = destination.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise AssertionError("pulled APK must be a regular file, not a link or directory")
            with os.fdopen(os.open(destination, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise AssertionError("pulled file identity changed")
                actual = stream.read(len(expected) + 1)
            record.update(actual_bytes=len(actual), file_bytes=opened.st_size,
                          actual_sha256=hashlib.sha256(actual).hexdigest(),
                          read_limited=opened.st_size > len(expected) + 1)
            assert actual == expected and opened.st_size == len(expected), "installed product bytes differ from built APK"
            elapsed = clock() - started
            if elapsed >= 30:
                raise TimeoutError("installed APK verification exceeded original 30 second budget")
            record.update(status="PASS", elapsed_seconds=elapsed)
            return actual
    except Exception as exc:
        record.update(status="FAIL", error=repr(exc))
        if isinstance(exc, subprocess.TimeoutExpired):
            record.update(stdout_tail=tail(exc.stdout), stderr_tail=tail(exc.stderr))
        raise


def contracts(transfer):
    payload = b"PK\x03\x04\x00\xff\r\n" + bytes(range(256)) * 3
    remote = "/data/app/fixture with space/base.apk"
    cases = ("exact", "short", "wrong", "extra", "missing", "directory",
             "symlink", "exit255", "timeout", "oserror", "late", "lateverify", "preexpired")
    for mode in cases:
        calls = []; destinations = []; record = {}
        timeout = subprocess.TimeoutExpired(["fixture"], 30, output=b"partial", stderr=b"timed out")
        unavailable = OSError("fixture unavailable")
        ticks = iter([0, 31] if mode == "preexpired" else
                     [0, 0, 31] if mode == "late" else [0, 0, 1, 31] if mode == "lateverify" else [0, 0, 1, 2])
        def invoke(command, **kwargs):
            assert not calls, "transfer retried"
            calls.append(command)
            assert command[:6] == ["fixture-adb", "-s", "emulator-5554", "pull", "-Z", remote]
            assert len(command) == 7
            assert kwargs == dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=30)
            target = Path(command[-1]); destinations.append(target)
            assert target.parent.is_dir() and not target.exists() and not target.is_symlink()
            assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
            if mode == "timeout":
                target.write_bytes(payload[:7]); raise timeout
            if mode == "oserror":
                raise unavailable
            if mode == "directory": target.mkdir()
            elif mode == "symlink":
                sibling = target.parent / "other"; sibling.write_bytes(payload); target.symlink_to(sibling)
            elif mode != "missing":
                value = payload[:-1] if mode == "short" else b"X" + payload[1:] if mode == "wrong" else payload + b"x" if mode == "extra" else payload
                target.write_bytes(value)
            return subprocess.CompletedProcess(command, 255 if mode == "exit255" else 0,
                                               b"pull progress", b"adb progress")
        caught = None
        try:
            actual = transfer("fixture-adb", "emulator-5554", remote, payload, record,
                              invoke=invoke, clock=lambda: next(ticks))
        except (AssertionError, OSError, subprocess.SubprocessError, TimeoutError) as exc:
            caught = exc
        assert len(calls) == (0 if mode == "preexpired" else 1), mode
        assert all(not p.parent.exists() for p in destinations), "temporary destination leaked"
        assert record["attempts"] == len(calls) and record["budget_seconds"] == 30
        assert record["method"] == "ADB_PULL_SINGLE_PRIMARY_EXACT_BYTES"
        if mode == "exact":
            assert caught is None and actual == payload and record["status"] == "PASS", repr(caught)
            assert record["actual_bytes"] == record["expected_bytes"] == len(payload)
            assert record["actual_sha256"] == record["expected_sha256"] == hashlib.sha256(payload).hexdigest()
            assert record["returncode"] == 0 and record["elapsed_seconds"] == 2
            assert record["stdout_tail"] == "pull progress" and record["stderr_tail"] == "adb progress"
        else:
            assert caught is not None and record["status"] == "FAIL", mode
            assert record["error"] == repr(caught), (mode, record)
            if mode == "timeout":
                assert caught is timeout and record["stdout_tail"] == "partial" and record["stderr_tail"] == "timed out"
            if mode == "oserror": assert caught is unavailable
            if mode == "exit255":
                assert type(caught) is subprocess.CalledProcessError
                assert (caught.returncode, caught.stdout, caught.stderr) == (255, b"pull progress", b"adb progress")
            if mode in ("short", "wrong", "extra"):
                assert type(caught) is AssertionError and str(caught) == "installed product bytes differ from built APK"
                assert record["actual_bytes"] == (len(payload)-1 if mode=="short" else len(payload)+1 if mode=="extra" else len(payload))
                assert record["actual_sha256"] != record["expected_sha256"]
            if mode in ("late", "lateverify", "preexpired"): assert type(caught) is TimeoutError
            if mode in ("directory", "symlink"): assert type(caught) is AssertionError and "regular file" in str(caught)
            if mode == "missing": assert type(caught) is FileNotFoundError
    # Invalid scope/input is refused before even invoking the transport.
    for serial, path, data in (("other", remote, payload), ("emulator-5554", "/sdcard/base.apk", payload),
                              ("emulator-5554", remote+"\n", payload), ("emulator-5554", remote, b""),
                              ("emulator-5554", "/data/app/../base.apk", payload)):
        calls = []; record = {}
        try: transfer("fixture-adb", serial, path, data, record, invoke=lambda *a, **k: calls.append(a))
        except (AssertionError, ValueError): pass
        else: raise AssertionError("invalid transfer scope accepted")
        assert not calls
    return 1, 17


def subprocess_contracts():
    """Real host subprocess/file boundary; this is still not an ADB or device test."""
    import sys
    with tempfile.TemporaryDirectory(prefix="adb-host-contract-") as folder:
        script = Path(folder) / "fake adb.py"
        script.write_text("import pathlib,sys\npathlib.Path(sys.argv[-1]).write_bytes(bytes(range(256)))\nprint('fixture transfer')\n")
        calls = []
        def invoke(command, **kwargs):
            calls.append(command)
            return subprocess.run([sys.executable, str(script), *command[1:]], **kwargs)
        for expected in (bytes(range(256)), b"x" * 256):
            record = {}; before = len(calls)
            try: actual = pull_exact(script, "emulator-5554", "/data/app/fixture/base.apk", expected, record, invoke=invoke)
            except AssertionError as exc:
                assert expected == b"x" * 256 and str(exc) == "installed product bytes differ from built APK"
                assert record["status"] == "FAIL"
            else:
                assert actual == expected == bytes(range(256)) and record["status"] == "PASS"
            assert len(calls) == before + 1 and not Path(calls[-1][-1]).parent.exists()
    return 2


def assert_workflow_wiring(text):
    """Fail-closed guard for this canonical YAML layout, not a general YAML parser."""
    import ast
    import textwrap
    def unique_part(value, start, end):
        assert value.count(start) == 1 and value.count(end) == 1, "ambiguous workflow boundary"
        return value.split(start, 1)[1].split(end, 1)[0]
    core = unique_part(text, "\n  core:\n", "\n  export_probe:\n")
    lines = core.splitlines()
    expected_command = "          python3 tools/verify_adb_transfer.py 2>&1 | tee -a core.log"
    assert lines.count(expected_command) == 1, "mandatory transfer selftest missing or weakened"
    index = lines.index(expected_command)
    assert lines[index-1].strip() == "python3 tools/verify_ui_observer.py selftest 2>&1 | tee -a core.log"
    assert lines[index-3].strip() == "set -euo pipefail"
    probe = unique_part(text, "\n  export_probe:\n", "\n  export_feedback:\n")
    step = unique_part(probe, "      - name: Independent backend preview and synthetic image multipage native saves\n",
                       "      - uses: actions/upload-artifact@")
    assert step.startswith("        run: |\n          set -euo pipefail\n"), "device step may be skipped"
    python = unique_part(step, "          python3 - <<'PY' 2>&1 | tee export-probe.log\n", "\n          PY\n")
    tree = ast.parse(textwrap.dedent(python))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "install_and_probe"]
    assert len(functions) == 1
    body = functions[0].body
    def same(a, b): return ast.dump(a) == ast.dump(b)
    start = ast.parse("from verify_adb_transfer import pull_exact").body[0]
    indices = [i for i, n in enumerate(body) if same(n, start)]
    assert len(indices) == 1, "actual callback must import the transfer helper"
    i = indices[0]
    # An independently written expected sequence, not derived from observed statements.
    expected = ast.parse("""
from verify_adb_transfer import pull_exact
preflight['phase'] = 'INSTALLED_BYTES'
expected = apps[0].read_bytes()
preflight['installed_transfer'] = {}
actual = pull_exact(adb, gate.SERIAL, installed[8:], expected, preflight['installed_transfer'])
preflight.update(actual_bytes=len(actual), expected_bytes=len(expected),
    actual_sha256=hashlib.sha256(actual).hexdigest(), expected_sha256=hashlib.sha256(expected).hexdigest())
assert actual == expected, 'installed product bytes differ from built APK'
calls.append('installed_exact_product')
preflight['phase'] = 'CODEC_AND_PREVIEW'
verify_exports.android_codec(adb, gate)
""").body
    assert len(body[i:i+len(expected)]) == len(expected)
    assert all(same(a, b) for a, b in zip(body[i:i+len(expected)], expected)), "transfer sequence changed"
    assert not any(isinstance(n, (ast.Return, ast.Try, ast.If, ast.While)) for n in body[:i]), "preflight can bypass transfer"
    binding = ast.parse("gate.verify_database = install_and_probe").body[0]
    assert sum(same(n, binding) for n in tree.body) == 1, "callback disconnected"
    assert sum(isinstance(n, ast.Call) and ast.unparse(n.func) == "pull_exact"
               for n in ast.walk(functions[0])) == 1, "multiple pull calls"
    return ast.Module(body=body[i:i+8], type_ignores=[])


def workflow_execution(text):
    """Execute the actual guarded workflow slice with real helper and fake transport."""
    import ast
    import sys
    from types import SimpleNamespace
    from unittest.mock import patch
    code = compile(assert_workflow_wiring(text), "<actual-export-workflow-transfer>", "exec")
    payload = bytes(range(256)) * 100
    for mode in ("exact", "short", "wrong", "exit255", "timeout"):
        with tempfile.TemporaryDirectory(prefix="workflow-transfer-") as folder:
            app = Path(folder) / "built.apk"; app.write_bytes(payload)
            calls = []; stages = []; record = {}
            timeout = subprocess.TimeoutExpired(["fixture"], 30, stderr=b"fixture timeout")
            def invoke(command, **kwargs):
                assert not calls, "workflow transfer retried"
                calls.append(command)
                assert command[:6] == ["fixture-adb", "-s", "emulator-5554", "pull", "-Z", "/data/app/fixture/base.apk"]
                assert kwargs["stdin"] == subprocess.DEVNULL and 0 < kwargs["timeout"] <= 30
                path = Path(command[-1]); assert not path.exists()
                path.write_bytes(payload[:-1] if mode == "short" else b"X"+payload[1:] if mode == "wrong" else payload)
                if mode == "timeout": raise timeout
                return subprocess.CompletedProcess(command, 255 if mode == "exit255" else 0, b"out", b"err")
            scope = dict(adb="fixture-adb", gate=SimpleNamespace(SERIAL="emulator-5554"),
                         installed="package:/data/app/fixture/base.apk", apps=[app], calls=stages,
                         preflight=record, hashlib=hashlib)
            caught = None
            # Import in the unmodified workflow resolves to this actual tested module.
            with patch.dict(sys.modules, {"verify_adb_transfer": sys.modules[__name__]}):
                with patch.object(subprocess, "run", invoke):
                    try: exec(code, scope)
                    except (AssertionError, subprocess.SubprocessError) as exc: caught = exc
            assert len(calls) == 1 and not Path(calls[0][-1]).parent.exists()
            receipt = record["installed_transfer"]
            if mode == "exact":
                assert caught is None and stages == ["installed_exact_product"]
                assert receipt["status"] == "PASS" and scope["actual"] == payload
                assert record["actual_bytes"] == record["expected_bytes"] == len(payload)
                assert record["actual_sha256"] == record["expected_sha256"] == hashlib.sha256(payload).hexdigest()
            else:
                assert caught is not None and stages == [] and receipt["status"] == "FAIL"
                assert receipt["error"] == repr(caught)
                if mode in ("short", "wrong"):
                    assert type(caught) is AssertionError and str(caught) == "installed product bytes differ from built APK"
                if mode == "exit255": assert type(caught) is subprocess.CalledProcessError and caught.returncode == 255
                if mode == "timeout": assert caught is timeout
    return 5


def wiring_contracts(text):
    assert_workflow_wiring(text)
    replacements = [
        ("python3 tools/verify_adb_transfer.py 2>&1 | tee -a core.log",
         "# python3 tools/verify_adb_transfer.py 2>&1 | tee -a core.log"),
        ("python3 tools/verify_adb_transfer.py 2>&1 | tee -a core.log",
         "python3 tools/verify_adb_transfer.py 2>&1 | tee -a core.log || true"),
        ("from verify_adb_transfer import pull_exact", "from other import pull_exact"),
        ("actual=pull_exact(adb,gate.SERIAL,installed[8:],expected,preflight['installed_transfer'])",
         "actual=expected"),
        ("actual=pull_exact(adb,gate.SERIAL,installed[8:],expected,preflight['installed_transfer'])",
         "actual=pull_exact(adb,gate.SERIAL,installed[8:],b'wrong',preflight['installed_transfer'])"),
        ("actual=pull_exact(adb,gate.SERIAL,installed[8:],expected,preflight['installed_transfer'])",
         "actual=pull_exact(adb,gate.SERIAL,installed[8:],expected,{})"),
        ("preflight['installed_transfer']={}", "preflight['installed_transfer']={'status':'PASS'}"),
        ("assert actual==expected,'installed product bytes differ from built APK'",
         "assert True,'installed product bytes differ from built APK'"),
        ("calls.append('installed_exact_product')", "pass"),
        ("gate.verify_database=install_and_probe", "gate.verify_database=lambda adb: None"),
        ("preflight['phase']='CODEC_AND_PREVIEW'", "return"),
    ]
    for old, new in replacements:
        assert text.count(old) == 1, old
        bad = text.replace(old, new, 1)
        try: assert_workflow_wiring(bad)
        except AssertionError: pass
        else: raise AssertionError("workflow wiring mutant survived: " + old)
    return len(replacements)


def selftest():
    import inspect
    positive, negative = contracts(pull_exact)
    source = inspect.getsource(pull_exact)
    changes = [
        ("actual == expected and opened.st_size == len(expected)", "True"),
        ("if result.returncode != 0:", "if False:"),
        ("if not stat.S_ISREG(info.st_mode):", "if False:"),
        ("if clock() >= deadline:", "if False:"),
        ("if elapsed >= 30:", "if False:"),
        ("timeout=remaining)", "timeout=remaining + 30)"),
    ]
    for old, new in changes:
        assert source.count(old) == 1 and old != new
        changed = source.replace(old, new, 1)
        namespace = dict(globals())
        exec(compile(changed, "<adb-transfer-mutant>", "exec"), namespace)
        try: contracts(namespace["pull_exact"])
        except AssertionError: pass
        else: raise AssertionError("surviving transfer mutant: " + old)
    boundary = subprocess_contracts()
    print("ADB_TRANSFER_HOST", positive, "positive", negative, "negative",
          len(changes), "compiled mutants", boundary, "real host subprocess cases; NOT_ANDROID_ACCEPTANCE")
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/android.yml"
    text = workflow.read_text()
    print("ADB_TRANSFER_WIRING", wiring_contracts(text), "negative controls",
          workflow_execution(text), "actual workflow slice cases; HOST_ONLY")


if __name__ == "__main__":
    selftest()
