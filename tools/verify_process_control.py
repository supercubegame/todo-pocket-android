#!/usr/bin/env python3
"""One acknowledged stop, then bounded read-only absence checks. Not LMK proof."""
import json
import math
from pathlib import Path
import re
import subprocess
import time


def stop_verified(adb, serial, package, *, runner=subprocess.run,
                  monotonic=time.monotonic, sleep=time.sleep, budget=30, emit=None):
    if not isinstance(package, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
        raise ValueError("exact package required")
    if (not isinstance(serial, str) or not serial or
            type(budget) not in (int, float) or not math.isfinite(budget) or
            not 0 < budget <= 30):
        raise ValueError("serial and bounded wait required")
    record = {"status": "FAIL", "package": package, "force_stop_attempts": 0,
              "probes": [], "scope": "COMMAND_ACK_AND_OBSERVED_ABSENCE_NOT_LMK"}
    prefix = [str(adb), "-s", serial, "shell", "-n", "-T"]
    def invoke(args, timeout, target):
        target.update(args=prefix + args, timeout=timeout)
        p = runner(prefix + args, text=True, capture_output=True,
                   stdin=subprocess.DEVNULL, timeout=timeout)
        target.update(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
        return p
    def pid_result(p):
        if p.returncode not in (0, 1):
            raise subprocess.CalledProcessError(p.returncode, p.args,
                                                output=p.stdout, stderr=p.stderr)
        assert not p.stderr.strip(), "pidof wrote stderr"
        text = p.stdout.strip()
        if p.returncode == 1:
            assert not text, "nonempty absence response"
            return None
        assert re.fullmatch(r"[1-9][0-9]*", text) and int(text) > 1, "one positive app PID required"
        return text
    started = monotonic()
    try:
        record["before"] = {}
        original = pid_result(invoke(["pidof", package], 10, record["before"]))
        record["force_stop_attempts"] = 1
        record["command"] = {}
        p = invoke(["am", "force-stop", package], 40, record["command"])
        if p.returncode:
            raise subprocess.CalledProcessError(p.returncode, p.args,
                                                output=p.stdout, stderr=p.stderr)
        assert not p.stdout.strip() and not p.stderr.strip(), "unexpected force-stop output"
        deadline = monotonic() + budget
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("app still present after bounded wait")
            observation = {}
            record["probes"].append(observation)
            current = pid_result(invoke(["pidof", package], min(10, remaining), observation))
            if current is None:
                record["status"] = "PASS"
                return record
            assert original is not None and current == original, "unexpected process after force-stop"
            sleep(min(.25, max(0, deadline - monotonic())))
    except Exception as exc:
        record["error"] = repr(exc)
        if isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
            def text(value):
                return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
            record["original_failure"] = {
                "type": type(exc).__name__, "command": exc.cmd,
                "stdout": text(exc.stdout), "stderr": text(exc.stderr)}
            if isinstance(exc, subprocess.CalledProcessError):
                record["original_failure"]["returncode"] = exc.returncode
            else:
                record["original_failure"]["timeout"] = exc.timeout
        raise
    finally:
        record["elapsed_seconds"] = round(monotonic() - started, 6)
        # Log even without a callback, including incomplete command/probe records.
        # Diagnostic failures cannot replace the original command failure.
        try:
            print("PROCESS_STOP_RESULT " + json.dumps(record), flush=True)
        except Exception:
            pass
        if emit is not None:
            try:
                emit(record)
            except Exception as exc:
                print("STOP_EVIDENCE_WRITE_FAILED " + repr(exc), flush=True)


def contract(stop):
    cases = [
        ("immediate", [(0, "82\n", ""), (0, "", ""), (1, "", "")], None, 1),
        ("delayed", [(0, "82\n", ""), (0, "", ""), (0, "82\n", ""), (1, "", "")], None, 1),
        ("already_absent", [(1, "", ""), (0, "", ""), (1, "", "")], None, 1),
        ("command_255", [(0, "82\n", ""), (255, "", "")], subprocess.CalledProcessError, 1),
        ("probe_255", [(0, "82\n", ""), (0, "", ""), (255, "", "")], subprocess.CalledProcessError, 1),
        ("new_pid", [(0, "82\n", ""), (0, "", ""), (0, "83\n", "")], AssertionError, 1),
        ("empty_zero", [(0, "82\n", ""), (0, "", ""), (0, "", "")], AssertionError, 1),
        ("nonempty_one", [(0, "82\n", ""), (0, "", ""), (1, "82\n", "")], AssertionError, 1),
        ("stderr", [(0, "82\n", ""), (0, "", ""), (1, "", "denied")], AssertionError, 1),
        ("bad_pid", [(0, "1\n", "")], AssertionError, 0),
        ("multiple", [(0, "82 83\n", "")], AssertionError, 0),
        ("preprobe_255", [(255, "", "")], subprocess.CalledProcessError, 0),
        ("never_stops", [(0, "82\n", ""), (0, "", "")] + [(0, "82\n", "")] * 30, TimeoutError, 1),
        ("command_timeout", [(0, "82\n", ""), subprocess.TimeoutExpired("am", 40, output=b"partial", stderr=b"timeout")], subprocess.TimeoutExpired, 1),
        ("command_output", [(0, "82\n", ""), (0, "unexpected", "")], AssertionError, 1),
        ("command_stderr", [(0, "82\n", ""), (0, "", "denied")], AssertionError, 1),
        ("appeared", [(1, "", ""), (0, "", ""), (0, "83\n", "")], AssertionError, 1),
        ("probe_timeout", [(0, "82\n", ""), (0, "", ""), subprocess.TimeoutExpired("pidof", 2)], subprocess.TimeoutExpired, 1),
        ("unicode_pid", [(0, "٨٢\n", "")], AssertionError, 0),
    ]
    for name, answers, expected, stops in cases:
        queue = list(answers)
        calls, clock, records = [], [0], []
        def runner(args, **kwargs):
            assert args[:6] == ["adb", "-s", "test-serial", "shell", "-n", "-T"]
            assert args[6:] in (["pidof", "com.example.fixture"],
                                ["am", "force-stop", "com.example.fixture"])
            assert kwargs["capture_output"] is True and kwargs["text"] is True
            assert kwargs["stdin"] is subprocess.DEVNULL and 0 < kwargs["timeout"] <= 40
            calls.append(args)
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return subprocess.CompletedProcess(args, *item)
        def sleep(seconds):
            clock[0] += seconds
        caught = None
        try:
            result = stop("adb", "test-serial", "com.example.fixture", runner=runner,
                          monotonic=lambda: clock[0], sleep=sleep, budget=2, emit=records.append)
        except Exception as exc:
            caught = exc
        assert (caught is None) if expected is None else isinstance(caught, expected), (name, repr(caught))
        assert sum("force-stop" in c for c in calls) == stops, (name, calls)
        assert records and records[-1]["status"] == ("PASS" if expected is None else "FAIL"), name
        assert records[-1]["force_stop_attempts"] == stops
        if expected is None:
            assert result["probes"][-1]["returncode"] == 1 and result["probes"][-1]["stdout"] == ""
        if name == "delayed":
            assert len(result["probes"]) == 2
        if name in ("command_255", "probe_255", "preprobe_255"):
            assert caught.returncode == 255 and caught.stdout == "" and caught.stderr == ""
            assert records[-1]["original_failure"]["returncode"] == 255
        if name in ("command_timeout", "probe_timeout"):
            assert caught is answers[-1]
            assert records[-1]["original_failure"]["type"] == "TimeoutExpired"
        if name == "command_timeout":
            assert records[-1]["original_failure"]["stdout"] == "partial"
        if name == "never_stops":
            assert 2 <= clock[0] <= 2.25
    # Invalid configuration must fail before issuing any device command.
    for invalid in (0, -1, 31, True, float("nan"), float("inf"), "30"):
        calls = []
        try:
            stop("adb", "test-serial", "com.example.fixture", budget=invalid,
                 runner=lambda *a, **k: calls.append(a))
        except ValueError:
            pass
        else:
            raise AssertionError("invalid budget accepted")
        assert not calls
    return len(cases) + 7


def selftest():
    import contextlib
    import io
    import inspect
    with contextlib.redirect_stdout(io.StringIO()):
        count = contract(stop_verified)
        source = inspect.getsource(stop_verified)
        mutants = [
            ("if current is None:", "if True:"),
            ('assert original is not None and current == original, "unexpected process after force-stop"', "pass"),
            ("if p.returncode:", "if False:"),
        ]
        for old, new in mutants:
            assert source.count(old) == 1, "mutation must change exactly one site"
            candidate = source.replace(old, new, 1)
            namespace = dict(globals())
            exec(compile(candidate, "<stop-mutant>", "exec"), namespace)
            try:
                contract(namespace["stop_verified"])
            except AssertionError:
                pass
            else:
                raise AssertionError("stop mutant survived: " + old)
    print("PROCESS_STOP_CONTROLS " + str(count) + "/" + str(count) +
          " PASS; mutants=3/3 rejected; HOST_INJECTED_NOT_ANDROID", flush=True)
    return count


def capture_crash_logs(adb, serial, *, runner=subprocess.run, environment=None):
    """Read only disposable CI logs. Empty/missing tails never prove no crash."""
    import os
    import tempfile
    environment = os.environ if environment is None else environment
    if environment.get("GITHUB_ACTIONS") != "true" or not re.fullmatch(r"emulator-[0-9]+", serial):
        raise ValueError("isolated CI emulator required for log capture")
    prefix = [str(adb), "-s", serial]
    result = {"status": "SCOPE_NOT_VERIFIED", "logs": [], "release_ready": False,
              "scope": "CI_SYNTHETIC_LOG_TAILS_NOT_ACCEPTANCE_OR_NO_CRASH_PROOF",
              "collection_budget_seconds": 19}
    def tail(stream, limit):
        stream.flush()
        size = stream.seek(0, 2)
        stream.seek(max(0, size - limit))
        return {"bytes": size, "truncated": size > limit,
                "tail": stream.read(limit).decode("utf-8", errors="replace")}
    def read(args, timeout):
        record = {"command": prefix + args, "timeout_seconds": timeout, "returncode": None}
        # Spool to disposable host files, not unbounded in-memory communicate().
        # The timeout and logcat entry limits bound collection; only byte tails
        # enter reports. Disk usage is not a hard byte quota.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                completed = runner(record["command"], stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=err, timeout=timeout)
                record.update(returncode=completed.returncode, status=(
                    "OBSERVED_NOT_ACCEPTANCE" if completed.returncode == 0 else "COMMAND_FAILED"))
            except subprocess.TimeoutExpired as exc:
                record.update(status="TIMEOUT_PARTIAL", error=repr(exc))
            except OSError as exc:
                record.update(status="NOT_OBSERVED", error=repr(exc))
            record.update(stdout=tail(out, 32768), stderr=tail(err, 8192))
        return record
    identity = read(["shell", "-n", "-T", "getprop", "ro.kernel.qemu"], 3)
    result["identity"] = identity
    if not (identity["returncode"] == 0 and identity["stdout"]["tail"].strip() == "1"
            and not identity["stdout"]["truncated"] and identity["stderr"]["bytes"] == 0):
        return result
    for args in (
        ["logcat", "-b", "crash", "-d", "-t", "160", "-v", "threadtime"],
        ["logcat", "-b", "main", "-b", "system", "-d", "-t", "240", "-v", "threadtime",
         "AndroidRuntime:E", "libc:F", "DEBUG:F", "ActivityManager:E", "*:S"],
    ):
        result["logs"].append(read(args, 8))
    if any(r["status"] != "OBSERVED_NOT_ACCEPTANCE" or r["stderr"]["bytes"] for r in result["logs"]):
        result["status"] = "PARTIAL_NOT_ACCEPTANCE"
    elif not any(r["stdout"]["bytes"] for r in result["logs"]):
        result["status"] = "EMPTY_NOT_PROOF_NO_CRASH"
    else:
        result["status"] = "OBSERVED_NOT_ACCEPTANCE"
    return result


def crash_contract(capture):
    expected = [
        ["adb", "-s", "emulator-5554", "shell", "-n", "-T", "getprop", "ro.kernel.qemu"],
        ["adb", "-s", "emulator-5554", "logcat", "-b", "crash", "-d", "-t", "160", "-v", "threadtime"],
        ["adb", "-s", "emulator-5554", "logcat", "-b", "main", "-b", "system", "-d", "-t", "240",
         "-v", "threadtime", "AndroidRuntime:E", "libc:F", "DEBUG:F", "ActivityManager:E", "*:S"],
    ]
    cases = [
        ("captured", [(0, b"1\n", b""), (0, b"FATAL EXCEPTION: fixture\n", b""), (0, b"runtime", b"")]),
        ("empty", [(0, b"1\n", b""), (0, b"", b""), (0, b"", b"")]),
        ("nonzero", [(0, b"1\n", b""), (255, b"partial", b"denied"), (0, b"runtime", b"")]),
        ("timeout", [(0, b"1\n", b""), ("timeout", b"partial-timeout", b"timeout-stderr"), (0, b"runtime", b"")]),
        ("missing", [(0, b"1\n", b""), ("oserror", b"", b""), ("oserror", b"", b"")]),
        ("large", [(0, b"1\n", b""), (0, b"x" * 40000 + b"END", b"e" * 10000), (0, b"\xff", b"")]),
        ("not_emulator", [(0, b"0\n", b"")]),
        ("identity_error", [(255, b"1\n", b"")]),
        ("identity_stderr", [(0, b"1\n", b"denied")]),
        ("identity_timeout", [("timeout", b"1\n", b"")]),
    ]
    for name, answers in cases:
        calls = []
        def runner(args, **kw):
            index = len(calls)
            assert index < len(answers), "no diagnostic retry"
            assert args == expected[index]
            assert kw["stdin"] == subprocess.DEVNULL and kw["timeout"] == (3 if index == 0 else 8)
            assert set(kw) == {"stdin", "stdout", "stderr", "timeout"}
            assert kw["stdout"] is not kw["stderr"]
            code, out, err = answers[index]
            calls.append(args)
            kw["stdout"].write(out); kw["stderr"].write(err)
            if code == "timeout":
                raise subprocess.TimeoutExpired(args, kw["timeout"])
            if code == "oserror":
                raise FileNotFoundError("synthetic missing adb")
            return subprocess.CompletedProcess(args, code)
        value = capture("adb", "emulator-5554", runner=runner, environment={"GITHUB_ACTIONS": "true"})
        assert len(calls) == len(answers), name
        assert value["scope"] == "CI_SYNTHETIC_LOG_TAILS_NOT_ACCEPTANCE_OR_NO_CRASH_PROOF"
        assert value["release_ready"] is False
        assert value["collection_budget_seconds"] == 19
        records = [value["identity"]] + value["logs"]
        assert len(records) == len(answers)
        for index, (record, (code, out, err)) in enumerate(zip(records, answers)):
            assert record["command"] == expected[index]
            assert record["timeout_seconds"] == (3 if index == 0 else 8)
            assert record["returncode"] == (code if isinstance(code, int) else None)
            for field, raw, limit in (("stdout", out, 32768), ("stderr", err, 8192)):
                stream = record[field]
                assert stream["bytes"] == len(raw)
                assert stream["tail"] == raw[-limit:].decode("utf-8", errors="replace")
                assert stream["truncated"] is (len(raw) > limit)
            if code == "timeout":
                assert record["status"] == "TIMEOUT_PARTIAL" and "TimeoutExpired" in record["error"]
            elif code == "oserror":
                assert record["status"] == "NOT_OBSERVED" and "FileNotFoundError" in record["error"]
            else:
                assert record["status"] == ("OBSERVED_NOT_ACCEPTANCE" if code == 0 else "COMMAND_FAILED")
        if len(answers) == 1:
            assert value["status"] == "SCOPE_NOT_VERIFIED" and not value["logs"]
        elif name == "empty":
            assert value["status"] == "EMPTY_NOT_PROOF_NO_CRASH"
        elif name in ("nonzero", "timeout", "missing", "large"):
            assert value["status"] == "PARTIAL_NOT_ACCEPTANCE"
        else:
            assert value["status"] == "OBSERVED_NOT_ACCEPTANCE"
        assert len(json.dumps(value)) < 160000
    for serial, env in [("phone", {"GITHUB_ACTIONS": "true"}), ("emulator-5554", {}),
                        ("emulator-5554", {"GITHUB_ACTIONS": "false"}), ("emulator-5554;bad", {"GITHUB_ACTIONS": "true"})]:
        calls = []
        def forbidden(*args, **kwargs):
            calls.append(args)
            raise AssertionError("out-of-scope device command")
        try:
            capture("adb", serial, environment=env, runner=forbidden)
        except ValueError:
            pass
        else:
            raise AssertionError("scope must be rejected before adb")
        assert not calls
    return len(cases) + 4


def crash_wiring_contract(workflow):
    """Execute the actual generated driver's exception handler, with host fakes."""
    import ast
    import copy
    import tempfile
    import textwrap
    marker = 'cat > "$RUNNER_TEMP/export_native_probe.py" <<\'PY\'\n'
    assert workflow.count(marker) == 1
    driver = textwrap.dedent(workflow.split(marker, 1)[1].split("\n          PY", 1)[0])
    tree = ast.parse(driver)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "standalone_native")
    guarded = next(n for n in function.body if isinstance(n, ast.Try))
    assert any(isinstance(n, ast.ImportFrom) and n.module == "verify_process_control"
               and any(a.name == "capture_crash_logs" for a in n.names) for n in function.body)
    handlers = copy.deepcopy(guarded.handlers)
    test = ast.Module(body=[ast.Try(body=[ast.Raise(exc=ast.Name(id="original", ctx=ast.Load()))],
                                   handlers=handlers, orelse=[], finalbody=[])], type_ignores=[])
    compiled = compile(ast.fix_missing_locations(test), "<actual-export-failure-handler>", "exec")
    for fail_capture, fail_old in ((False, False), (True, False), (False, True), (True, True)):
        calls = []; original = AssertionError("ORIGINAL_NATIVE_FAILURE")
        sentinel = {"status": "OBSERVED_NOT_ACCEPTANCE", "tail": "FATAL EXCEPTION: synthetic"}
        result = {"status": "FAIL", "labels": ["fresh_ui_database"]}
        def capture(adb, serial):
            assert adb == "adb" and serial == "emulator-5554"
            calls.append("crash")
            if fail_capture:
                raise OSError("crash capture failed")
            return sentinel
        def old(*args):
            calls.append("old")
            if fail_old:
                raise OSError("old probe failed")
            return {"preserved": True}
        def command(*args, **kw):
            calls.append("screenshot")
            raise OSError("screenshot failed")
        with tempfile.TemporaryDirectory() as folder:
            namespace = {"original": original, "result": result, "adb": "adb",
                         "gate": type("Gate", (), {"SERIAL": "emulator-5554"}),
                         "capture_crash_logs": capture, "native_failure_evidence": old,
                         "exception_evidence": lambda exc: {"error": repr(exc)}, "command": command,
                         "out": Path(folder)}
            try:
                exec(compiled, namespace)
            except AssertionError as exc:
                assert exc is original
            else:
                raise AssertionError("original native failure swallowed")
        assert calls == ["crash", "old", "screenshot"]
        assert result["status"] == "FAIL" and result["labels"] == ["fresh_ui_database"]
        assert result["error"] == repr(original) and result["original_failure"] == {"error": repr(original)}
        if fail_capture:
            assert "crash capture failed" in result["crash_diagnostic_error"]["error"]
        else:
            assert result["crash_logs"] is sentinel
        if fail_old:
            assert "old probe failed" in result["diagnostic_error"]["error"]
        else:
            assert result["failure_diagnostics"] == {"preserved": True}
    assert 'Path("export-native.json").write_text(json.dumps(result' in driver
    assert "if Path('export-native.json').exists():result['native_image_pages']=json.loads" in workflow
    return 4


def crash_selftest(workflow):
    import inspect
    count = crash_contract(capture_crash_logs)
    source = inspect.getsource(capture_crash_logs)
    mutants = [
        ("stdin=subprocess.DEVNULL", "stdin=None"),
        ("stdout=tail(out, 32768)", "stdout=tail(out, 40000)"),
        ('if environment.get("GITHUB_ACTIONS") != "true" or not re.fullmatch(r"emulator-[0-9]+", serial):', "if False:"),
        ('if not (identity["returncode"] == 0', 'if not (True'),
    ]
    for old, new in mutants:
        assert source.count(old) == 1
        namespace = dict(globals())
        exec(compile(source.replace(old, new, 1), "<crash-mutant>", "exec"), namespace)
        try:
            crash_contract(namespace["capture_crash_logs"])
        except AssertionError:
            pass
        else:
            raise AssertionError("crash capture mutant survived: " + old)
    wired = crash_wiring_contract(workflow)
    print("CRASH_CAPTURE_CONTROLS " + str(count) + " PASS; mutants=4/4 rejected; wiring=" +
          str(wired) + "/4 original failures retained; HOST_INJECTED_NOT_ANDROID", flush=True)


if __name__ == "__main__":
    import sys
    assert sys.argv[1:] == ["selftest"], "usage: verify_process_control.py selftest"
    selftest()
    crash_selftest(Path(".github/workflows/android.yml").read_text())
