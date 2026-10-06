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


def run_adb_traced(args, *, receipt, binary=False, runner=subprocess.run, environment=None):
    """One original invocation, bounded receipt; stderr intentionally contains mixed trace.

    PIPE capture is unchanged and is not a hard process-memory/output quota. Only the
    retained receipt is bounded. No filtering can safely separate remote stderr from
    client trace, and this collector does not infer whether an exit packet was received.
    """
    import base64
    import os
    env = dict(os.environ if environment is None else environment)
    if env.get("GITHUB_ACTIONS") != "true" or list(args)[1:3] != ["-s", "emulator-5554"]:
        raise ValueError("isolated CI emulator required")
    env["ADB_TRACE"] = "rwx,shell"
    def record(status, stderr, returncode=None):
        try:
            raw = stderr if isinstance(stderr, bytes) else (stderr or "").encode("utf-8")
            receipt.update(status=status, attempts=1, timeout_seconds=40,
                           trace_categories="rwx,shell",
                           stderr_kind="UNFILTERED_MIXED_ADB_TRACE_AND_COMMAND_STDERR",
                           stderr_encoding="RAW_BYTES" if isinstance(stderr, bytes) else "UTF8_REENCODED_TEXT",
                           stderr_bytes=len(raw), stderr_truncated=len(raw) > 4096,
                           stderr_tail_base64=base64.b64encode(raw[-4096:]).decode("ascii"),
                           returncode=returncode)
        except Exception:
            # A diagnostic allocation/serialization failure cannot replace the command.
            pass
    try:
        completed = runner(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=not binary, timeout=40, env=env)
    except subprocess.TimeoutExpired as exc:
        record("TIMEOUT", exc.stderr)
        raise
    except OSError:
        record("SPAWN_ERROR", None)
        raise
    record("COMPLETED", completed.stderr, completed.returncode)
    return completed


def adb_trace_selftest():
    """Host contracts, not evidence that a device emitted an exit packet."""
    import base64
    import inspect
    import os
    import tempfile
    def contract(invoke):
        count = 0
        for binary in (False, True):
            for mode in ("ok", "nonzero", "timeout", "spawn"):
                calls = []; receipt = {}
                env = {"GITHUB_ACTIONS": "true", "ADB_TRACE": "all", "PRIVATE_SENTINEL": "not-a-log"}
                original_env = env.copy()
                args = ["adb", "-s", "emulator-5554", "shell", "-n", "-T", "ls", "files/media"]
                raw = b"remote-error\n" + bytes(range(256)) * 40
                stderr = raw if binary else raw.decode("latin1")
                stdout = b"\x00\xff exact \n" if binary else "  exact \n"
                error = (subprocess.TimeoutExpired(args, 40, stdout, stderr)
                         if mode == "timeout" else OSError("spawn failure"))
                completed = subprocess.CompletedProcess(args, 255 if mode == "nonzero" else 0, stdout, stderr)
                def runner(actual, **kw):
                    calls.append(actual)
                    assert actual == args
                    assert kw == dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=not binary, timeout=40,
                                      env=dict(original_env, ADB_TRACE="rwx,shell"))
                    if mode in ("timeout", "spawn"): raise error
                    return completed
                try: actual = invoke(args, binary=binary, receipt=receipt, runner=runner, environment=env)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    assert mode in ("timeout", "spawn") and exc is error
                else:
                    assert mode in ("ok", "nonzero") and actual is completed
                    assert actual.stdout == stdout and actual.stderr == stderr
                assert len(calls) == 1 and env == original_env
                assert receipt["attempts"] == 1 and receipt["timeout_seconds"] == 40
                assert receipt["stderr_kind"] == "UNFILTERED_MIXED_ADB_TRACE_AND_COMMAND_STDERR"
                assert receipt["trace_categories"] == "rwx,shell"
                assert "PRIVATE_SENTINEL" not in json.dumps(receipt) and "not-a-log" not in json.dumps(receipt)
                assert receipt["status"] == ("TIMEOUT" if mode == "timeout" else "SPAWN_ERROR" if mode == "spawn" else "COMPLETED")
                if mode != "spawn":
                    expected = stderr if isinstance(stderr, bytes) else stderr.encode("utf-8")
                    assert base64.b64decode(receipt["stderr_tail_base64"]) == expected[-4096:]
                    assert receipt["stderr_bytes"] == len(expected) and receipt["stderr_truncated"] is True
                    assert receipt["stderr_encoding"] == ("RAW_BYTES" if binary else "UTF8_REENCODED_TEXT")
                if mode in ("ok", "nonzero"): assert receipt["returncode"] == completed.returncode
                count += 1
        for env, args in (({}, ["adb", "-s", "emulator-5554"]),
                          ({"GITHUB_ACTIONS": "true"}, ["adb", "-s", "phone"])):
            def forbidden(*args, **kw): raise AssertionError("out of scope invocation")
            try: invoke(args, receipt={}, runner=forbidden, environment=env)
            except ValueError: pass
            else: raise AssertionError("scope guard missing")
            count += 1
        class Broken(dict):
            def update(self, *args, **kw): raise OSError("receipt unavailable")
        for failure in (False, True):
            original = subprocess.TimeoutExpired(["adb"], 40, b"partial", b"mixed")
            p = subprocess.CompletedProcess(["adb"], 0, "exact", "mixed")
            calls = []
            def run(*args, **kw):
                calls.append(args)
                if failure: raise original
                return p
            try: value = invoke(["adb", "-s", "emulator-5554"], receipt=Broken(), runner=run,
                                environment={"GITHUB_ACTIONS": "true"})
            except subprocess.TimeoutExpired as exc: assert failure and exc is original
            else: assert not failure and value is p
            assert len(calls) == 1
            count += 1
        return count
    count = contract(run_adb_traced)
    source = inspect.getsource(run_adb_traced)
    mutations = (('env["ADB_TRACE"] = "rwx,shell"', 'env["ADB_TRACE"] = "all"'),
                 ("timeout=40,", "timeout=41,"),
                 ("stdin=subprocess.DEVNULL", "stdin=None"),
                 ("raw[-4096:]", "raw"),
                 ("return completed", "return subprocess.CompletedProcess(args, 0, completed.stdout, completed.stderr)"))
    for old, new in mutations:
        assert source.count(old) == 1, old
        scope = dict(globals()); exec(compile(source.replace(old, new), "<trace-mutant>", "exec"), scope)
        try: contract(scope["run_adb_traced"])
        except AssertionError: pass
        else: raise AssertionError("trace mutant survived: " + old)
    with tempfile.TemporaryDirectory(prefix="pocket-trace-host-") as tmp:
        tool = Path(tmp) / "adb"; marker = Path(tmp) / "count"
        tool.write_text("#!/usr/bin/env python3\nimport os,sys\n"
                        "with open(os.environ['TRACE_COUNT'],'ab') as f:f.write(b'1')\n"
                        "assert os.environ['ADB_TRACE']=='rwx,shell'\n"
                        "sys.stdout.buffer.write(b'\\x00\\xff exact \\n')\n"
                        "sys.stderr.buffer.write(b'original remote error\\n'+b'T'*20000)\n"
                        "sys.exit(255)\n")
        tool.chmod(0o700)
        receipt = {}; env = dict(os.environ, GITHUB_ACTIONS="true", TRACE_COUNT=str(marker))
        p = run_adb_traced([str(tool), "-s", "emulator-5554", "shell", "-n", "-T", "ls"],
                           binary=True, receipt=receipt, environment=env)
        assert marker.read_bytes() == b"1" and p.returncode == 255
        assert p.stdout == b"\x00\xff exact \n" and len(p.stderr) == 20022
        assert base64.b64decode(receipt["stderr_tail_base64"]) == b"T"*4096
        assert receipt["stderr_bytes"] == 20022 and receipt["stderr_truncated"] is True
    print(f"ADB_FIRST_INVOCATION_TRACE host={count} mutants=5 real_subprocess=1 PASS; MIXED_STDERR_NOT_DEVICE_PROTOCOL_PROOF", flush=True)


def capture_adb_connection(adb, serial, *, runner=subprocess.run, environment=None,
                           connector=None, monotonic=time.monotonic):
    """Host-only observations; never start/reset/reconnect adb or replay a shell command."""
    import os
    import socket
    import tempfile
    environment = os.environ if environment is None else environment
    if environment.get("GITHUB_ACTIONS") != "true" or serial != "emulator-5554":
        raise ValueError("isolated CI emulator required")
    result = {"status": "DIAGNOSTIC_ONLY_NOT_DEVICE_PROOF", "serial": serial,
              "budget_seconds": 6, "reads": [], "release_ready": False}
    # Do not accidentally query a different server or disclose custom endpoint values.
    if any(environment.get(k) for k in
           ("ADB_SERVER_SOCKET", "ANDROID_ADB_SERVER_ADDRESS", "ANDROID_ADB_SERVER_PORT")):
        result["status"] = "CUSTOM_ENDPOINT_NOT_OBSERVED"
        return result
    started = monotonic()
    deadline = started + 6
    connect = socket.create_connection if connector is None else connector
    def remaining():
        value = min(2, deadline - monotonic())
        if value <= 0:
            raise TimeoutError("host diagnostic budget exhausted")
        return value
    def tail(stream):
        stream.flush(); size = stream.seek(0, 2); stream.seek(max(0, size - 8192))
        return {"bytes": size, "truncated": size > 8192,
                "tail": stream.read(8192).decode("utf-8", errors="replace")}
    record = {"kind": "local_client_version", "command": [str(adb), "version"]}
    result["reads"].append(record)
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            timeout = remaining(); record["timeout_seconds"] = timeout
            value = runner(record["command"], stdin=subprocess.DEVNULL,
                           stdout=out, stderr=err, timeout=timeout)
            record.update(returncode=value.returncode, status=(
                "OBSERVED_NOT_ACCEPTANCE" if value.returncode == 0 else "COMMAND_FAILED"))
        except Exception as exc:
            record.update(status="NOT_OBSERVED", error=repr(exc))
        record.update(stdout=tail(out), stderr=tail(err))
    # Direct smart-socket requests do not invoke adb's auto-start/version-mismatch logic.
    # Each service is requested once on its own protocol connection, not a retry.
    for service in (b"host:version", b"host:devices-l"):
        record = {"kind": "existing_server_query", "service": service.decode(),
                  "endpoint": "127.0.0.1:5037", "status": "NOT_OBSERVED"}
        result["reads"].append(record)
        try:
            with connect(("127.0.0.1", 5037), timeout=remaining()) as connection:
                def receive(size):
                    data = b""
                    while len(data) < size:
                        connection.settimeout(remaining())
                        part = connection.recv(size - len(data))
                        if not part:
                            raise EOFError("incomplete smart-socket response")
                        data += part
                    return data
                connection.settimeout(remaining())
                connection.sendall(("%04x" % len(service)).encode() + service)
                status = receive(4); record["protocol_status"] = status.decode("ascii", "replace")
                if status not in (b"OKAY", b"FAIL"):
                    raise ValueError("invalid smart-socket status")
                length = receive(4)
                if not re.fullmatch(b"[0-9a-fA-F]{4}", length):
                    raise ValueError("invalid smart-socket length")
                count = int(length, 16); record["payload_bytes"] = count
                if count > 32768:
                    raise ValueError("host response exceeds diagnostic limit")
                record["payload"] = receive(count).decode("utf-8", "strict")
                remaining()
                record["status"] = "OBSERVED_NOT_ACCEPTANCE" if status == b"OKAY" else "SERVER_REFUSED"
        except Exception as exc:
            record.update(status="NOT_OBSERVED", error=repr(exc))
    result["elapsed_seconds"] = round(monotonic() - started, 6)
    return result


def capture_crash_logs(adb, serial, *, runner=subprocess.run, environment=None, snapshot_reader=None,
                       host_connection_reader=None):
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
        # Only this early-exit path has unused time: 3 + 6 <= original 19 seconds.
        # Normal collection remains 19 + 32 = 51. No extra device query or retry.
        if host_connection_reader is not None:
            try:
                result["host_connection"] = host_connection_reader(
                    adb, serial, runner=runner, environment=environment)
            except Exception as diagnostic:
                result["host_connection_error"] = repr(diagnostic)
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
    # The existing failure handler already persists this whole object. Keep
    # original crash fields/budget intact and name the additional total budget.
    result["combined_collection_budget_seconds"] = 51
    try:
        reader = capture_process_snapshot if snapshot_reader is None else snapshot_reader
        result["process_snapshot"] = reader(adb, serial, runner=runner, environment=environment)
    except Exception as diagnostic:
        result["process_snapshot_error"] = repr(diagnostic)
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
        snapshot_calls = []
        sentinel = {"status": "DIAGNOSTIC_ONLY_NOT_IDENTITY_ACCEPTANCE"}
        def snapshot_reader(adb, serial, **kw):
            assert adb == "adb" and serial == "emulator-5554"
            assert kw == {"runner": runner, "environment": {"GITHUB_ACTIONS": "true"}}
            snapshot_calls.append(True)
            return sentinel
        value = capture("adb", "emulator-5554", runner=runner, environment={"GITHUB_ACTIONS": "true"},
                        snapshot_reader=snapshot_reader)
        assert len(snapshot_calls) == (0 if len(answers) == 1 else 1)
        if len(answers) > 1:
            assert value["process_snapshot"] is sentinel and value["combined_collection_budget_seconds"] == 51
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


def capture_process_snapshot(adb, serial, *, runner=subprocess.run, environment=None):
    """Post-failure observation only. No retry, signal, root or success inference."""
    import os
    import tempfile
    environment = os.environ if environment is None else environment
    if environment.get("GITHUB_ACTIONS") != "true" or not re.fullmatch(r"emulator-[0-9]+", serial):
        raise ValueError("isolated CI emulator required for process diagnostics")
    package = "com.supercubegame.pockettodo.v12.preview"
    prefix = [str(adb), "-s", serial]
    result = {"status": "DIAGNOSTIC_ONLY_NOT_IDENTITY_ACCEPTANCE",
              "scope": "CURRENT_PROCESS_AFTER_FAILURE_NOT_FAILED_PID_OR_RETRY",
              "release_ready": False, "collection_budget_seconds": 32,
              "selected_pid": None, "failed_pid_reconstructed": False, "reads": []}
    def tail(stream, limit):
        stream.flush(); size = stream.seek(0, 2); stream.seek(max(0, size-limit))
        return {"bytes": size, "truncated": size > limit,
                "tail": stream.read(limit).decode("utf-8", errors="replace")}
    def read(args, timeout=3):
        record = {"command": prefix+args, "timeout_seconds": timeout, "returncode": None}
        result["reads"].append(record)
        # Spooling bounds report memory, not temporary-file disk usage.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                p = runner(record["command"], stdin=subprocess.DEVNULL,
                           stdout=out, stderr=err, timeout=timeout)
                record.update(returncode=p.returncode, status=(
                    "OBSERVED_NOT_ACCEPTANCE" if p.returncode == 0 else "COMMAND_FAILED"))
            except subprocess.TimeoutExpired as exc:
                record.update(status="TIMEOUT_PARTIAL", error=repr(exc))
            except OSError as exc:
                record.update(status="NOT_OBSERVED", error=repr(exc))
            record.update(stdout=tail(out, 32768), stderr=tail(err, 8192))
        return record
    shell = ["shell", "-n", "-T"]
    qemu = read(shell+["getprop", "ro.kernel.qemu"])
    if not (qemu["returncode"] == 0 and qemu["stdout"]["tail"].strip() == "1"
            and not qemu["stdout"]["truncated"] and qemu["stderr"]["bytes"] == 0):
        return result
    read(shell+["run-as", package, "id", "-u"])
    current = read(shell+["pidof", package])
    pid = current["stdout"]["tail"].strip()
    if (current["returncode"] == 0 and not current["stdout"]["truncated"]
            and current["stderr"]["bytes"] == 0 and re.fullmatch(r"[1-9][0-9]*", pid)
            and int(pid) > 1):
        result["selected_pid"] = pid
        # These sequential reads are not an atomic identity proof. The final
        # pidof may expose a change but cannot rule out PID reuse or later death.
        read(shell+["cat", "/proc/"+pid+"/status"])
        read(shell+["run-as", package, "cat", "/proc/"+pid+"/status"])
        read(["exec-out", "run-as", package, "cat", "/proc/"+pid+"/cmdline"])
        read(shell+["cat", "/proc/"+pid+"/stat"])
        read(shell+["pidof", package])
    read(["logcat", "-b", "events", "-d", "-t", "80", "-v", "threadtime",
          "am_proc_start:I", "am_proc_died:I", "am_kill:I", "am_crash:I", "*:S"], 8)
    return result


def process_snapshot_contract(capture):
    package = "com.supercubegame.pockettodo.v12.preview"
    prefix = ["adb", "-s", "emulator-5554"]
    base = [
        ["shell", "-n", "-T", "getprop", "ro.kernel.qemu"],
        ["shell", "-n", "-T", "run-as", package, "id", "-u"],
        ["shell", "-n", "-T", "pidof", package],
    ]
    detail = [
        ["shell", "-n", "-T", "cat", "/proc/82/status"],
        ["shell", "-n", "-T", "run-as", package, "cat", "/proc/82/status"],
        ["exec-out", "run-as", package, "cat", "/proc/82/cmdline"],
        ["shell", "-n", "-T", "cat", "/proc/82/stat"],
        ["shell", "-n", "-T", "pidof", package],
    ]
    context = ["logcat", "-b", "events", "-d", "-t", "80", "-v", "threadtime",
               "am_proc_start:I", "am_proc_died:I", "am_kill:I", "am_crash:I", "*:S"]
    normal = [(0, b"1\n", b""), (0, b"10077\n", b""), (0, b"82\n", b""),
              (0, b"Name:\tfixture\nUid:\t10077\t10077\t10077\t10077\n", b""),
              (0, b"Name:\tfixture\nUid:\t10077\t10077\t10077\t10077\n", b""),
              (0, package.encode()+b"\0", b""), (0, b"82 (fixture) S 1 2 3\n", b""),
              (0, b"82\n", b""), (0, b"am_proc_died: synthetic\n", b"")]
    cases = [("readable", normal)]
    for name, index, answer in [
        ("runas_255", 4, (255, b"", b"")),
        ("status_timeout", 4, ("timeout", b"partial", b"timeout")),
        ("missing_adb", 4, ("missing", b"", b"")),
        ("changed_after", 7, (0, b"83\n", b"")),
        ("absent_after", 7, (1, b"", b"")),
        ("large_tail", 3, (0, b"x"*40000+b"END", b"e"*9000)),
        ("invalid_utf8", 3, (0, b"\xff", b"")),
    ]:
        values = list(normal); values[index] = answer; cases.append((name, values))
    for name, answer in [
        ("absent_before", (1, b"", b"")), ("pidof_255", (255, b"", b"")),
        ("failed_nonempty_pid", (255, b"82\n", b"")),
        ("ambiguous_pid", (0, b"82 83\n", b"")), ("pid_one", (0, b"1\n", b"")),
        ("unicode_pid", (0, "٨٢\n".encode(), b"")), ("pid_stderr", (0, b"82\n", b"denied")),
    ]:
        cases.append((name, normal[:2]+[answer, normal[-1]]))
    for name, answer in [
        ("not_emulator", (0, b"0\n", b"")), ("qemu_255", (255, b"1\n", b"")),
        ("qemu_stderr", (0, b"1\n", b"denied")), ("qemu_timeout", ("timeout", b"1\n", b"")),
    ]:
        cases.append((name, [answer]))
    for name, answers in cases:
        expected = base+detail+[context] if len(answers) == 9 else base+[context] if len(answers) == 4 else base[:1]
        calls = []
        def runner(args, **kw):
            i = len(calls)
            assert i < len(expected), "extra/retried diagnostic command"
            assert args == prefix+expected[i], (name, i, args)
            assert set(kw) == {"stdin", "stdout", "stderr", "timeout"}
            assert kw["stdin"] == subprocess.DEVNULL and kw["stdout"] is not kw["stderr"]
            assert kw["timeout"] == (8 if expected[i] == context else 3)
            calls.append(args)
            code, out, err = answers[i]
            kw["stdout"].write(out); kw["stderr"].write(err)
            if code == "timeout": raise subprocess.TimeoutExpired(args, kw["timeout"])
            if code == "missing": raise FileNotFoundError("synthetic missing adb")
            return subprocess.CompletedProcess(args, code)
        value = capture("adb", "emulator-5554", runner=runner, environment={"GITHUB_ACTIONS": "true"})
        assert len(calls) == len(answers), name
        assert value["status"] == "DIAGNOSTIC_ONLY_NOT_IDENTITY_ACCEPTANCE"
        assert value["scope"] == "CURRENT_PROCESS_AFTER_FAILURE_NOT_FAILED_PID_OR_RETRY"
        assert value["release_ready"] is False and value["collection_budget_seconds"] == 32
        assert value["failed_pid_reconstructed"] is False
        assert value["selected_pid"] == ("82" if len(answers) == 9 else None)
        assert len(value["reads"]) == len(answers)
        for record, answer, args in zip(value["reads"], answers, expected):
            code, out, err = answer
            assert record["command"] == prefix+args
            assert record["timeout_seconds"] == (8 if args == context else 3)
            assert record["returncode"] == (code if type(code) is int else None)
            expected_status = ("TIMEOUT_PARTIAL" if code == "timeout" else
                               "NOT_OBSERVED" if code == "missing" else
                               "OBSERVED_NOT_ACCEPTANCE" if code == 0 else "COMMAND_FAILED")
            assert record["status"] == expected_status
            for field, raw, limit in (("stdout", out, 32768), ("stderr", err, 8192)):
                assert record[field] == {"bytes": len(raw), "truncated": len(raw)>limit,
                                        "tail": raw[-limit:].decode("utf-8", errors="replace")}
        if name == "changed_after":
            assert value["reads"][-2]["stdout"]["tail"] == "83\n"
        if name == "runas_255":
            assert value["reads"][4]["returncode"] == 255
        assert len(json.dumps(value)) < 100000
    invalid = [("phone", {"GITHUB_ACTIONS": "true"}), ("emulator-5554", {}),
               ("emulator-5554;bad", {"GITHUB_ACTIONS": "true"})]
    for serial, environment in invalid:
        calls = []
        def forbidden(*args, **kw):
            calls.append(args); raise AssertionError("out-of-scope read")
        try: capture("adb", serial, runner=forbidden, environment=environment)
        except ValueError: pass
        else: raise AssertionError("scope accepted")
        assert not calls
    return len(cases)+len(invalid)


def process_snapshot_wiring(capture):
    """Use the default nested reader, then prove reader failure stays diagnostic."""
    calls = []
    def runner(args, **kw):
        calls.append(args)
        if args[-2:] == ["getprop", "ro.kernel.qemu"]: raw = b"1\n"
        elif args[-2:] == ["id", "-u"]: raw = b"10077\n"
        elif args[-2:] == ["pidof", "com.supercubegame.pockettodo.v12.preview"]: raw = b"82\n"
        else: raw = b"diagnostic-only\n"
        kw["stdout"].write(raw)
        return subprocess.CompletedProcess(args, 0)
    value = capture("adb", "emulator-5554", runner=runner, environment={"GITHUB_ACTIONS": "true"})
    assert len(calls) == 12 and value["combined_collection_budget_seconds"] == 51
    assert len(value["logs"]) == 2
    nested = value["process_snapshot"]
    assert nested["selected_pid"] == "82" and len(nested["reads"]) == 9
    assert nested["status"] == "DIAGNOSTIC_ONLY_NOT_IDENTITY_ACCEPTANCE"
    assert sum(r["timeout_seconds"] for r in nested["reads"]) == 32
    assert sum(r["timeout_seconds"] for r in [value["identity"]]+value["logs"]) == 19
    def broken(*args, **kw): raise OSError("snapshot_write_sentinel")
    value = capture("adb", "emulator-5554", runner=runner, environment={"GITHUB_ACTIONS": "true"},
                    snapshot_reader=broken)
    assert "snapshot_write_sentinel" in value["process_snapshot_error"]
    assert len(value["logs"]) == 2 and "process_snapshot" not in value
    return 2


def process_snapshot_selftest():
    import inspect
    count = process_snapshot_contract(capture_process_snapshot)
    source = inspect.getsource(capture_process_snapshot)
    mutants = [
        ("stdin=subprocess.DEVNULL", "stdin=None"),
        ("stdout=tail(out, 32768)", "stdout=tail(out, 40000)"),
        ('current["returncode"] == 0', "True"),
        ('if environment.get("GITHUB_ACTIONS") != "true" or not re.fullmatch(r"emulator-[0-9]+", serial):', "if False:"),
    ]
    for old, new in mutants:
        assert source.count(old) == 1
        namespace = dict(globals())
        exec(compile(source.replace(old, new, 1), "<process-diagnostic-mutant>", "exec"), namespace)
        try: process_snapshot_contract(namespace["capture_process_snapshot"])
        except AssertionError: pass
        else: raise AssertionError("process diagnostic mutant survived "+old)
    assert process_snapshot_wiring(capture_crash_logs) == 2
    source = inspect.getsource(capture_crash_logs)
    old = 'result["process_snapshot"] = reader(adb, serial, runner=runner, environment=environment)'
    assert source.count(old) == 1
    namespace = dict(globals())
    exec(compile(source.replace(old, "pass", 1), "<process-wiring-mutant>", "exec"), namespace)
    try: process_snapshot_wiring(namespace["capture_crash_logs"])
    except (AssertionError, KeyError): pass
    else: raise AssertionError("missing diagnostic wiring accepted")
    print("PROCESS_SNAPSHOT_CONTROLS "+str(count)+" PASS; mutants=4/4 rejected; wiring=2/2 mutant=1/1; HOST_ONLY", flush=True)


def adb_connection_selftest():
    import inspect
    env = {"GITHUB_ACTIONS": "true"}
    def contract(capture):
        cases = [
            (b"OKAY00040029", b"OKAY0016emulator-5554\tdevice\n\n"),
            (b"FAIL0006denied", b"OKAY0000"),
            (b"", b"NOPE"),
            (b"OKAYzzzz", b"OKAYffff"),
            (b"OKAY0002\xff\xff", b"OKAY0003x"),
            (TimeoutError("socket timeout"), ConnectionRefusedError("not listening")),
        ]
        for index, replies in enumerate(cases):
            calls = []; sockets = []; clock = [0.]
            def runner(args, **kw):
                assert args == ["adb", "version"]
                assert set(kw) == {"stdin", "stdout", "stderr", "timeout"}
                assert kw["stdin"] == subprocess.DEVNULL and 0 < kw["timeout"] <= 2
                calls.append(args)
                kw["stdout"].write(b"x" * 9000); kw["stderr"].write(b"err")
                if index == 2: raise subprocess.TimeoutExpired(args, kw["timeout"])
                if index == 3: raise FileNotFoundError("missing client")
                return subprocess.CompletedProcess(args, 255 if index == 1 else 0)
            class Connection:
                def __init__(self, raw): self.raw = raw; self.sent = []; self.closed = False
                def __enter__(self): return self
                def __exit__(self, *args): self.closed = True
                def settimeout(self, value): assert 0 < value <= 2
                def sendall(self, value): self.sent.append(value)
                def recv(self, size):
                    assert 0 < size <= 32768
                    value = self.raw[:min(size, 2)]; self.raw = self.raw[len(value):]
                    return value
            attempts = []
            def connect(address, timeout):
                assert address == ("127.0.0.1", 5037) and 0 < timeout <= 2
                n = len(attempts); attempts.append(address); reply = replies[n]
                if isinstance(reply, Exception): raise reply
                value = Connection(reply); sockets.append((n, value)); return value
            value = capture("adb", "emulator-5554", runner=runner, environment=env,
                            connector=connect, monotonic=lambda: clock[0])
            assert len(calls) == 1 and len(attempts) == 2 and len(value["reads"]) == 3
            assert value["budget_seconds"] == 6 and value["release_ready"] is False
            assert value["status"] == "DIAGNOSTIC_ONLY_NOT_DEVICE_PROOF"
            for n, connection in sockets:
                assert connection.closed
                assert connection.sent == [[b"000chost:version", b"000ehost:devices-l"][n]]
            client = value["reads"][0]
            assert client["stdout"] == {"bytes": 9000, "truncated": True, "tail": "x" * 8192}
            assert client["stderr"]["tail"] == "err"
            assert client["status"] == ("NOT_OBSERVED" if index in (2, 3) else
                                        "COMMAND_FAILED" if index == 1 else "OBSERVED_NOT_ACCEPTANCE")
            if index == 0:
                assert [r["payload"] for r in value["reads"][1:]] == ["0029", "emulator-5554\tdevice\n\n"]
                assert all(r["status"] == "OBSERVED_NOT_ACCEPTANCE" for r in value["reads"])
            elif index == 1:
                assert value["reads"][1]["status"] == "SERVER_REFUSED"
                assert value["reads"][2]["payload"] == ""
            else:
                assert all(r["status"] == "NOT_OBSERVED" and r["error"] for r in value["reads"][1:])
                if index == 3:
                    assert "exceeds diagnostic limit" in value["reads"][2]["error"]
        def forbidden(*args, **kw): raise AssertionError("unexpected IO")
        for key in ("ADB_SERVER_SOCKET", "ANDROID_ADB_SERVER_ADDRESS", "ANDROID_ADB_SERVER_PORT"):
            value = capture("adb", "emulator-5554", runner=forbidden, connector=forbidden,
                            environment=dict(env, **{key: "secret-sentinel"}))
            assert value["status"] == "CUSTOM_ENDPOINT_NOT_OBSERVED" and not value["reads"]
            assert "secret-sentinel" not in json.dumps(value)
        for environment, serial in (({}, "emulator-5554"), (env, "physical"), (env, "emulator-5556")):
            try: capture("adb", serial, runner=forbidden, connector=forbidden, environment=environment)
            except ValueError: pass
            else: raise AssertionError("scope accepted")
        clock = iter([0, 7, 7, 7, 7])
        value = capture("adb", "emulator-5554", runner=forbidden, connector=forbidden,
                        environment=env, monotonic=lambda: next(clock))
        assert all(r["status"] == "NOT_OBSERVED" for r in value["reads"])
        assert all("budget exhausted" in r["error"] for r in value["reads"])
    contract(capture_adb_connection)
    source = inspect.getsource(capture_adb_connection)
    for old, new in [
        ("stdin=subprocess.DEVNULL", "stdin=None"),
        ("count > 32768", "count > 65535"),
        ("value <= 0", "value < -100"),
        ('status == b"OKAY"', "True"),
        ('environment.get(k)', 'False'),
    ]:
        assert source.count(old) == 1
        namespace = dict(globals())
        exec(compile(source.replace(old, new, 1), "<host-connection-mutant>", "exec"), namespace)
        try: contract(namespace["capture_adb_connection"])
        except AssertionError: pass
        else: raise AssertionError("host connection mutant survived: " + old)
    # Opt-in on failed identity only; untouched normal path and first error retained.
    for broken in (False, True):
        calls = []
        def runner(args, **kw):
            calls.append(args)
            return subprocess.CompletedProcess(args, 255)
        def reader(adb, serial, **kw):
            calls.append("host")
            if broken: raise OSError("host diagnostic sentinel")
            return {"status": "DIAGNOSTIC_ONLY_NOT_DEVICE_PROOF", "budget_seconds": 6}
        value = capture_crash_logs("adb", "emulator-5554", runner=runner, environment=env,
                                   host_connection_reader=reader)
        assert len(calls) == 2 and calls[-1] == "host"
        assert value["identity"]["returncode"] == 255 and value["status"] == "SCOPE_NOT_VERIFIED"
        assert value["collection_budget_seconds"] == 19 and value["logs"] == []
        assert (3 + 6) <= value["collection_budget_seconds"]
        assert ("host_connection_error" in value) is broken
        assert ("host_connection" in value) is not broken
    print("ADB_CONNECTION_HOST cases=13 mutants=5 wiring=2 PASS; NOT_ANDROID_OR_ROOT_CAUSE", flush=True)


def adb_failure_wiring(workflow):
    import ast
    import copy
    import textwrap
    start = "          # DRAFT_NATIVE_BEGIN\n"; end = "          # DRAFT_NATIVE_END\n"
    assert workflow.count(start) == workflow.count(end) == 1
    tree = ast.parse(textwrap.dedent(workflow.split(start)[1].split(end)[0]))
    native = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "native")
    command = next(n for n in native.body if isinstance(n, ast.FunctionDef) and n.name == "command")
    def contract(node):
        for timeout_first, timeout_second in ((False, False), (False, True), (True, False), (True, True)):
            result = {}; calls = []; original = subprocess.TimeoutExpired(["first"], 40, b"first", b"err")
            def run(args, **kw):
                assert kw.pop("env") == {"GITHUB_ACTIONS": "true", "ADB_TRACE": "rwx,shell"}
                assert kw == dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, timeout=40)
                calls.append(args)
                if len(calls) == 1 and timeout_first: raise original
                if len(calls) == 2 and timeout_second: raise subprocess.TimeoutExpired(args, 40, b"later", b"later")
                return subprocess.CompletedProcess(args, 255 if len(calls) == 1 else 17, "first" if len(calls) == 1 else "later", "")
            scope = dict(result=result, prefix=["adb", "-s", "emulator-5554"],
                         run_adb_traced=lambda *a, **kw: run_adb_traced(*a, **kw, environment={"GITHUB_ACTIONS": "true"}),
                         subprocess=type("Fake", (), dict(run=staticmethod(run), TimeoutExpired=subprocess.TimeoutExpired,
                                                         DEVNULL=subprocess.DEVNULL, PIPE=subprocess.PIPE)))
            exec(compile(ast.Module(body=[node], type_ignores=[]), "<actual-draft-command>", "exec"), scope)
            try: scope["command"]("first")
            except subprocess.TimeoutExpired as exc: assert timeout_first and exc is original
            except RuntimeError: assert not timeout_first
            else: raise AssertionError("first failure swallowed")
            first = copy.deepcopy(result["command_failure"])
            assert first["adb_trace"]["attempts"] == 1
            assert first["adb_trace"]["stderr_kind"] == "UNFILTERED_MIXED_ADB_TRACE_AND_COMMAND_STDERR"
            try: scope["command"]("screenshot")
            except (RuntimeError, subprocess.TimeoutExpired): pass
            else: raise AssertionError("later failure swallowed")
            assert result["command_failure"] == first, "original failure overwritten"
            assert calls == [["adb", "-s", "emulator-5554", "first"],
                             ["adb", "-s", "emulator-5554", "screenshot"]]
    contract(command)
    traced_calls = [n for n in ast.walk(command) if isinstance(n, ast.Call) and
                    isinstance(n.func, ast.Name) and n.func.id == "run_adb_traced"]
    assert len(traced_calls) == 1
    assert ast.unparse(traced_calls[0]) == "run_adb_traced(prefix + list(args), binary=binary, receipt=trace, runner=subprocess.run)"
    assert any(isinstance(n, ast.ImportFrom) and n.module == "verify_process_control" and
               any(a.name == "run_adb_traced" for a in n.names) for n in tree.body)
    for first in (True, False):
        mutant = copy.deepcopy(command)
        candidates = [n for n in ast.walk(mutant) if isinstance(n, ast.Expr) and
                      isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) and
                      n.value.func.attr == "setdefault"]
        assert len(candidates) == 2
        call = candidates[0 if first else 1].value
        assignment = ast.Assign(targets=[ast.Subscript(value=ast.Name(id="result", ctx=ast.Load()),
                                slice=ast.Constant("command_failure"), ctx=ast.Store())], value=call.args[1])
        class Replace(ast.NodeTransformer):
            def visit_Expr(self, node):
                return ast.copy_location(assignment, node) if node.value is call else self.generic_visit(node)
        mutant = ast.fix_missing_locations(Replace().visit(mutant))
        try: contract(mutant)
        except AssertionError: pass
        else: raise AssertionError("first failure mutation survived")
    capture = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "capture_draft_failure")
    calls = [n for n in ast.walk(capture) if isinstance(n, ast.Call) and
             isinstance(n.func, ast.Name) and n.func.id == "capture_crash_logs"]
    assert len(calls) == 1 and ast.unparse(calls[0]) == "capture_crash_logs(adb, serial, host_connection_reader=capture_adb_connection)"
    assert any(isinstance(n, ast.ImportFrom) and n.module == "verify_process_control" and
               any(a.name == "capture_adb_connection" for a in n.names) for n in tree.body)
    assert workflow.count("python3 tools/verify_process_control.py connection-selftest 2>&1 | tee -a draft-host.log") == 1
    print("ADB_FAILURE_WIRING first_failure=4 mutants=2 PASS; actual workflow AST", flush=True)



def run_pidof_isolated(args, *, capture_output, text, stdin, timeout, receipt,
                       environment=None, tracer="strace"):
    """One CI pidof invocation; separate tracer pipes, bounded diagnostic tails.

    strace changes timing. This is diagnostic instrumentation, not an untraced
    reproduction, device-root-cause proof, or permission to accept exit 255.
    Command streams retain subprocess.run's existing unbounded capture contract.
    Trace retention is bounded in memory and never spooled to disk.
    """
    import base64
    import locale
    import os
    import selectors
    import signal
    import sys
    env = dict(os.environ if environment is None else environment)
    args = list(args)
    if (env.get("GITHUB_ACTIONS") != "true" or len(args) != 8 or
            args[1:7] != ["-s", "emulator-5554", "shell", "-n", "-T", "pidof"] or
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", args[7]) or
            capture_output is not True or text is not True or stdin != subprocess.DEVNULL or
            type(timeout) not in (int, float) or not math.isfinite(timeout) or
            not 0 < timeout <= 10 or not isinstance(receipt, dict)):
        raise ValueError("CI emulator exact pidof and original <=10s capture contract required")
    receipt.update(scope="HOST_SYSCALL_TAIL_NOT_DEVICE_ROOT_CAUSE", attempts=1,
                   command=args, timeout_seconds=timeout, status="NOT_OBSERVED",
                   stderr_kind="COMMAND_STDERR_SEPARATE_FROM_TRACER", timed_out=False,
                   trace_retention_bytes=65536, tracer_stderr_retention_bytes=4096,
                   release_ready=False)
    # The child alone writes this private completion pipe. A tracer returning 1
    # before launch must not masquerade as a legitimate pidof absence response.
    wrapper = (
        "import os,subprocess,sys\n"
        "error,done,trace=map(int,sys.argv[1:4])\n"
        "os.dup2(error,2);os.close(error);os.close(trace)\n"
        "p=subprocess.run(sys.argv[4:],stdin=subprocess.DEVNULL,close_fds=True)\n"
        "os.write(done,(str(p.returncode)+'\\n').encode('ascii'));os.close(done)\n"
        "os._exit(p.returncode if p.returncode>=0 else 128-p.returncode)\n"
    )
    buffers = {key: bytearray() for key in ("stdout", "stderr", "done", "trace", "tracer_stderr")}
    totals = dict.fromkeys(buffers, 0)
    limits = {"trace": 65536, "tracer_stderr": 4096, "done": 64}
    fds = set(); writes = []; process = None
    selector = selectors.DefaultSelector()
    started = time.monotonic(); deadline = started + timeout
    def keep(name, chunk):
        totals[name] += len(chunk)
        buffers[name].extend(chunk)
        if name in limits and len(buffers[name]) > limits[name]:
            del buffers[name][:-limits[name]]
    def register(fd, name):
        os.set_blocking(fd, False)
        selector.register(fd, selectors.EVENT_READ, name)
    def drain(wait):
        for key, _ in selector.select(wait):
            try: chunk = os.read(key.fd, 8192)
            except BlockingIOError: continue
            if chunk:
                keep(key.data, chunk)
            else:
                selector.unregister(key.fd)
    def terminate():
        if process is None: return
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        # Cleanup is not a new command/observation budget or an assertion retry.
        # Do not wait indefinitely for a tracer or its descendants after timeout.
        try:
            process.wait(timeout=1)
            receipt["cleanup"] = "PROCESS_GROUP_KILLED_AND_REAPED"
        except subprocess.TimeoutExpired:
            receipt["cleanup"] = "PROCESS_GROUP_KILLED_REAP_NOT_OBSERVED"
    try:
        channels = {}
        for name in ("stderr", "done", "trace"):
            read_fd, write_fd = os.pipe()
            fds.update((read_fd, write_fd)); writes.append(write_fd)
            channels[name] = write_fd
            register(read_fd, name)
        command = [tracer, "-f", "-qq", "-ttt", "-s", "128", "-xx",
                   "-e", "trace=read,write,readv,writev,recvfrom,recvmsg,sendto,sendmsg,connect,exit_group",
                   "-o", "/proc/self/fd/"+str(channels["trace"]),
                   sys.executable, "-c", wrapper, str(channels["stderr"]),
                   str(channels["done"]), str(channels["trace"]), *args]
        process = subprocess.Popen(command, stdin=stdin, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, pass_fds=tuple(writes),
                                   start_new_session=True, env=env)
        for fd in writes:
            os.close(fd); fds.remove(fd)
        register(process.stdout.fileno(), "stdout")
        register(process.stderr.fileno(), "tracer_stderr")
        while selector.get_map() or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                receipt["timed_out"] = True
                terminate()
                # Bounded nonblocking drain preserves already-buffered command
                # output. No second invocation or post-failure pidof is issued.
                for _ in range(64):
                    if not selector.get_map(): break
                    drain(0)
                raise subprocess.TimeoutExpired(args, timeout,
                    output=bytes(buffers["stdout"]), stderr=bytes(buffers["stderr"]))
            drain(min(.05, remaining))
        receipt["tracer_returncode"] = process.returncode
        completed = bytes(buffers["done"])
        if totals["done"] != len(completed) or not re.fullmatch(rb"-?[0-9]{1,3}\n", completed):
            raise RuntimeError("isolated trace has no exact child exit receipt; not process absence")
        code = int(completed)
        if not -64 <= code <= 255:
            raise RuntimeError("invalid original child exit receipt")
        receipt["command_returncode"] = code
        receipt["tracer_exit_matches"] = process.returncode == (code if code >= 0 else 128-code)
        receipt["status"] = "OBSERVED_NOT_ROOT_CAUSE" if totals["trace"] else "TRACE_NOT_OBSERVED"
        encoding = locale.getencoding()
        def decode(raw):
            return bytes(raw).decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
        return subprocess.CompletedProcess(args, code, decode(buffers["stdout"]), decode(buffers["stderr"]))
    except BaseException as exc:
        receipt["error"] = repr(exc)
        if process is not None and process.poll() is None: terminate()
        raise
    finally:
        for name in ("trace", "tracer_stderr"):
            receipt[name] = {"bytes": totals[name], "truncated": totals[name] > len(buffers[name]),
                             "tail_b64": base64.b64encode(buffers[name]).decode("ascii")}
        receipt["elapsed_seconds"] = round(time.monotonic()-started, 6)
        selector.close()
        for fd in fds:
            try: os.close(fd)
            except OSError: pass
        if process is not None:
            process.stdout.close(); process.stderr.close()


def isolated_stop_runner(adb, serial, package, records, *, environment=None, tracer="strace"):
    """Explicit export-only adapter. Unchanged force-stop is invoked exactly once."""
    import os
    env = dict(os.environ if environment is None else environment)
    if env.get("GITHUB_ACTIONS") != "true" or serial != "emulator-5554":
        raise ValueError("isolated stop tracing is CI emulator-only")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", package):
        raise ValueError("exact package required")
    prefix = [str(adb), "-s", serial, "shell", "-n", "-T"]
    sequence = 0
    def invoke(args, **kwargs):
        nonlocal sequence
        if args == prefix+["pidof", package]:
            # Keep at most eight query traces; the existing stop receipt still
            # records EVERY command. A failing query is last because stop_verified
            # propagates it immediately, so its original trace is not overwritten.
            sequence += 1
            if len(records) >= 8: records.pop(0)
            record = {"observation_number": sequence, "retention": "LATEST_8_QUERY_TRACES"}
            records.append(record)
            return run_pidof_isolated(args, receipt=record, environment=env, tracer=tracer, **kwargs)
        if args != prefix+["am", "force-stop", package]:
            raise ValueError("unexpected stop adapter command")
        return subprocess.run(args, env=env, **kwargs)
    return invoke


def isolated_stop_selftest(module=None, witness_only=False):
    """Real host subprocesses with a fake tracer/ADB, never device evidence."""
    import base64
    import os
    import tempfile
    namespace = globals() if module is None else module
    run = namespace["run_pidof_isolated"]
    make_runner = namespace["isolated_stop_runner"]
    fake_trace = r'''#!/usr/bin/env python3
import os,subprocess,sys
a=sys.argv[1:]; i=a.index("-o"); path=a[i+1]; command=a[i+2:]
mode=os.environ.get("TRACE_FIXTURE","normal")
if mode=="missing_receipt": sys.exit(1)
with open(path,"wb",buffering=0) as f:
    f.write(b"x"*100000+b"TRACE_END")
    if mode=="trace_stderr": os.write(2,b"TRACER_ONLY_SENTINEL")
    p=subprocess.run(command,close_fds=False)
sys.exit(p.returncode)
'''
    fake_adb = r'''#!/usr/bin/env python3
import os,sys,time
from pathlib import Path
p=Path(os.environ["CALL_FILE"])
previous=p.read_text().splitlines() if p.exists() else []
with p.open("a") as f: f.write(" ".join(sys.argv[1:])+"\n")
if os.environ.get("STOP_FIXTURE"):
    if "force-stop" in sys.argv: sys.exit(0)
    if not previous: print("5744"); sys.exit(0)
    sys.exit(int(os.environ["STOP_FIXTURE"]))
os.write(1,bytes.fromhex(os.environ.get("ADB_OUT","")))
os.write(2,bytes.fromhex(os.environ.get("ADB_ERR","")))
if os.environ.get("ADB_SLEEP"): time.sleep(10)
sys.exit(int(os.environ.get("ADB_CODE","0")))
'''
    with tempfile.TemporaryDirectory(prefix="isolated-stop-host-") as directory:
        root = Path(directory)
        trace = root/"fake-strace"; trace.write_text(fake_trace); trace.chmod(0o700)
        adb = root/"adb"; adb.write_text(fake_adb); adb.chmod(0o700)
        calls = root/"calls"
        command = [str(adb), "-s", "emulator-5554", "shell", "-n", "-T",
                   "pidof", "com.supercubegame.pockettodo.v12.preview"]
        base = dict(os.environ, GITHUB_ACTIONS="true", CALL_FILE=str(calls))
        def exercise(code, out, err, mode="normal"):
            calls.unlink(missing_ok=True)
            env = dict(base, ADB_CODE=str(code), ADB_OUT=out.hex(), ADB_ERR=err.hex(),
                       TRACE_FIXTURE=mode)
            record = {}
            value = run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                        timeout=5, receipt=record, environment=env, tracer=str(trace))
            assert value.args == command and value.returncode == code, "original exit or argv lost"
            assert value.stdout == out.decode().replace("\r\n", "\n").replace("\r", "\n"), "stdout changed"
            assert value.stderr == err.decode().replace("\r\n", "\n").replace("\r", "\n"), "stderr changed"
            assert calls.read_text().splitlines() == [" ".join(command[1:])], "command replayed"
            assert record["attempts"] == 1 and record["timeout_seconds"] == 5
            assert record["scope"] == "HOST_SYSCALL_TAIL_NOT_DEVICE_ROOT_CAUSE"
            assert record["command_returncode"] == code
            assert record["trace"]["bytes"] == 100009 and record["trace"]["truncated"] is True
            assert len(base64.b64decode(record["trace"]["tail_b64"])) == 65536
            assert base64.b64decode(record["trace"]["tail_b64"]).endswith(b"TRACE_END")
            expected = b"TRACER_ONLY_SENTINEL" if mode == "trace_stderr" else b""
            assert base64.b64decode(record["tracer_stderr"]["tail_b64"]) == expected
            assert record["stderr_kind"] == "COMMAND_STDERR_SEPARATE_FROM_TRACER"
            return value
        exercise(0, b"5744\n", b"")
        if witness_only:
            print("ISOLATED_POSITIVE_WITNESS PASS", flush=True)
            return
        exercise(1, b"", b"")
        exercise(255, b"original-out\r\n", b"original-error")
        exercise(1, b"", b"adb-warning")
        exercise(0, b"5744\n", b"", "trace_stderr")
        positives = 5
        negatives = 0
        for tracer, mode, failure in (
                (str(root/"missing-strace"), "normal", FileNotFoundError),
                (str(trace), "missing_receipt", RuntimeError)):
            calls.unlink(missing_ok=True); record = {}
            try:
                run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                    timeout=5, receipt=record, environment=dict(base, TRACE_FIXTURE=mode),
                    tracer=tracer)
            except failure: pass
            else: raise AssertionError("tracer setup failure interpreted as command absence")
            assert not calls.exists(), "fallback command launched"
            negatives += 1
        calls.unlink(missing_ok=True); record = {}
        try:
            run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                timeout=.5, receipt=record,
                environment=dict(base, ADB_SLEEP="true", ADB_OUT=b"partial".hex(),
                                 ADB_ERR=b"original-timeout-error".hex()), tracer=str(trace))
        except subprocess.TimeoutExpired as exc:
            assert exc.cmd == command and exc.timeout == .5
            assert exc.stdout == b"partial" and exc.stderr == b"original-timeout-error"
        else: raise AssertionError("timeout was hidden or retried")
        assert len(calls.read_text().splitlines()) == 1
        assert record["timed_out"] is True and record["cleanup"] == "PROCESS_GROUP_KILLED_AND_REAPED"
        negatives += 1
        for changed, env in (
                (command[:2]+["phone"]+command[3:], base),
                (command[:-2]+["am", command[-1]], base),
                (command, dict(base, GITHUB_ACTIONS="false"))):
            calls.unlink(missing_ok=True)
            try:
                run(changed, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                    timeout=5, receipt={}, environment=env, tracer=str(trace))
            except ValueError: pass
            else: raise AssertionError("scope escaped")
            assert not calls.exists()
            negatives += 1
        for final in (1, 255):
            calls.unlink(missing_ok=True); records = []; stops = []
            runner = make_runner(str(adb), "emulator-5554", command[-1], records,
                                 environment=dict(base, STOP_FIXTURE=str(final)), tracer=str(trace))
            try:
                namespace["stop_verified"](str(adb), "emulator-5554", command[-1],
                                            runner=runner, emit=stops.append)
            except subprocess.CalledProcessError as exc:
                assert final == 255 and exc.returncode == 255
                assert exc.stdout == "" and exc.stderr == "" and exc.cmd == command
            else:
                assert final == 1 and stops[-1]["status"] == "PASS"
            assert len(calls.read_text().splitlines()) == 3, "stop or query was replayed"
            assert len(records) == 2 and all(r["timeout_seconds"] <= 10 for r in records)
            assert stops[-1]["force_stop_attempts"] == 1
            if final == 255: assert stops[-1]["original_failure"]["returncode"] == 255
        calls.unlink(missing_ok=True); records = []
        runner = make_runner(str(adb), "emulator-5554", command[-1], records,
                             environment=dict(base, ADB_CODE="1"), tracer=str(trace))
        for number in range(12):
            value = runner(command, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=5)
            assert value.returncode == 1 and value.stdout == value.stderr == ""
        assert len(calls.read_text().splitlines()) == 12
        assert len(records) == 8 and [v["observation_number"] for v in records] == list(range(5,13))
        print("ISOLATED_STOP_HOST_CONTROLS 5 positive 6 negative 2 stop integrations PASS; FAKE_TRACER_NOT_DEVICE", flush=True)
        print("ISOLATED_TRACE_RETENTION 12 invocations latest8 retained PASS", flush=True)
        return positives, negatives


def isolated_stop_mutation_selftest():
    """Compile and run changed implementations, each with a passing live witness."""
    import inspect
    import textwrap
    source = textwrap.dedent(inspect.getsource(run_pidof_isolated))
    variants = [
        ("code = int(completed)", "code = 1 if int(completed) == 255 else int(completed)",
         "original exit or argv lost"),
        ('decode(buffers["stderr"]))', '"" )', "stderr changed"),
        ('decode(buffers["stderr"]))', 'decode(buffers["stderr"]+buffers["tracer_stderr"]))',
         "stderr changed"),
        ('completed = bytes(buffers["done"])',
         'completed = bytes(buffers["done"]) or (str(process.returncode)+"\\n").encode(); totals["done"] = len(completed)',
         "tracer setup failure interpreted as command absence"),
    ]
    for old, new, expected in variants:
        assert source.count(old) == 1, "ambiguous mutation anchor"
        changed = source.replace(old, new, 1)
        assert changed != source
        namespace = dict(globals())
        exec(compile(changed, "<compiled-isolated-stop-mutant>", "exec"), namespace)
        isolated_stop_selftest(namespace, witness_only=True)
        try: isolated_stop_selftest(namespace)
        except AssertionError as exc:
            assert expected in str(exc), (expected, str(exc))
        else: raise AssertionError("compiled trace mutant survived")
    print("ISOLATED_STOP_MUTANTS 4 compiled 4 witnessed 4 rejected HOST_ONLY", flush=True)


def isolated_stop_real_tracer_selftest():
    """CI real strace + synthetic executable, NOT ADB/device acceptance."""
    import base64
    import os
    import shutil
    import tempfile
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("real tracer gate is CI-only")
    tracer = shutil.which("strace")
    if not tracer: raise FileNotFoundError("required CI strace dependency missing; no fallback")
    with tempfile.TemporaryDirectory(prefix="isolated-real-tracer-") as directory:
        path = Path(directory)/"fixture-adb"
        path.write_text("#!/usr/bin/env python3\nimport os,sys,time\n"
                        "os.write(1,bytes.fromhex(os.environ['ISOLATED_OUT']))\n"
                        "os.write(2,bytes.fromhex(os.environ['ISOLATED_ERR']))\n"
                        "if os.environ.get('ISOLATED_SLEEP'):time.sleep(10)\n"
                        "sys.exit(int(os.environ['ISOLATED_FIXTURE_CODE']))\n")
        path.chmod(0o700)
        for code, out, err in ((0, b"5744\n", b""), (1, b"", b""),
                               (255, b"original-out\n", b"original-error\n"),
                               (1, b"", b"command-warning\n")):
            record = {}
            command = [str(path), "-s", "emulator-5554", "shell", "-n", "-T",
                       "pidof", "com.example.fixture"]
            value = run_pidof_isolated(command, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=10, receipt=record, tracer=tracer,
                environment=dict(os.environ, ISOLATED_FIXTURE_CODE=str(code),
                                 ISOLATED_OUT=out.hex(), ISOLATED_ERR=err.hex()))
            assert (value.returncode, value.stdout, value.stderr) == (
                code, out.decode(), err.decode())
            assert record["tracer_exit_matches"] and record["trace"]["bytes"] > 0
            assert record["tracer_stderr"]["bytes"] == 0
            assert base64.b64decode(record["trace"]["tail_b64"])
        record = {}
        try:
            run_pidof_isolated(command, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=1, receipt=record, tracer=tracer,
                environment=dict(os.environ, ISOLATED_FIXTURE_CODE="0", ISOLATED_SLEEP="true",
                                 ISOLATED_OUT=b"partial".hex(), ISOLATED_ERR=b"partial-error".hex()))
        except subprocess.TimeoutExpired as exc:
            assert exc.cmd == command and exc.timeout == 1
            assert exc.stdout == b"partial" and exc.stderr == b"partial-error"
            assert record["cleanup"] == "PROCESS_GROUP_KILLED_AND_REAPED"
        else: raise AssertionError("real tracer timeout did not stop the original invocation")
    print("ISOLATED_REAL_STRACE_CONTROLS 4 exit cases 1 timeout PASS; SYNTHETIC_HOST_EXECUTABLE_NOT_DEVICE", flush=True)


def isolated_stop_wiring(workflow):
    """Inspect the real export caller, not a detached copy of its command."""
    import ast
    marker = '          cat > "$RUNNER_TEMP/export_native_probe.py" <<'+"'PY'"+'\n'
    assert workflow.count(marker) == 1
    body = workflow.split(marker, 1)[1].split('          PY\n', 1)[0]
    source = "\n".join(line[10:] if line else "" for line in body.splitlines())+"\n"
    def check(source):
        tree = ast.parse(source)
        native = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "standalone_native")
        stop = next(n for n in native.body if isinstance(n, ast.FunctionDef) and n.name == "stop")
        expected = ast.parse('def stop():\n    return stop_verified(adb,gate.SERIAL,gate.PKG,runner=stop_runner,emit=result["process_stops"].append)\n').body[0]
        assert ast.dump(stop) == ast.dump(expected), "export stop bypasses isolated runner"
        bindings = [n for n in native.body if isinstance(n, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == "stop_runner" for t in n.targets)]
        expected = ast.parse('stop_runner=isolated_stop_runner(adb,gate.SERIAL,gate.PKG,result["process_query_traces"])').body[0]
        assert len(bindings) == 1 and ast.dump(bindings[0]) == ast.dump(expected), "wrong runner binding"
        imports = [a.name for n in native.body if isinstance(n, ast.ImportFrom) and
                   n.module == "verify_process_control" for a in n.names]
        assert imports.count("isolated_stop_runner") == 1, "missing actual adapter import"
    check(source)
    for old, new, expected_error in (
            ('runner=stop_runner,', '', "export stop bypasses"),
            ('result["process_query_traces"]', 'result["other"]', "wrong runner binding"),
            ('stop_verified,capture_crash_logs,isolated_stop_runner',
             'stop_verified,capture_crash_logs', "missing actual adapter import")):
        assert source.count(old) == 1
        changed = source.replace(old, new, 1); compile(changed, "<caller-mutant>", "exec")
        try: check(changed)
        except AssertionError as exc: assert expected_error in str(exc)
        else: raise AssertionError("caller mutation survived")
    assert workflow.count("        run: &isolated_trace_setup |") == 1
    assert workflow.count("        run: *isolated_trace_setup") == 1
    assert workflow.count("python3 tools/verify_process_control.py isolated-selftest") == 1
    assert workflow.count("python3 tools/verify_process_control.py isolated-real-selftest") == 1
    assert workflow.count("strace --version") == 1
    print("ISOLATED_STOP_WIRING 1 actual positive 3 compiled negative controls PASS; NOT_DEVICE", flush=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["isolated-selftest"]:
        isolated_stop_selftest()
        isolated_stop_mutation_selftest()
        isolated_stop_wiring(Path(".github/workflows/android.yml").read_text())
        sys.exit(0)
    if sys.argv[1:] == ["isolated-real-selftest"]:
        isolated_stop_real_tracer_selftest()
        sys.exit(0)

if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["connection-selftest"]:
        adb_trace_selftest()
        adb_connection_selftest()
        adb_failure_wiring(Path(".github/workflows/note-drafts.yml").read_text())
        sys.exit(0)
    assert sys.argv[1:] == ["selftest"], "usage: verify_process_control.py selftest"
    selftest()
    crash_selftest(Path(".github/workflows/android.yml").read_text())
    process_snapshot_selftest()
    adb_trace_selftest()
    adb_connection_selftest()
    adb_failure_wiring(Path(".github/workflows/note-drafts.yml").read_text())
