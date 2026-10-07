#!/usr/bin/env python3
"""Evidence-only conflict recovery. No device assertion retries."""
import base64
import copy
import contextlib
import hashlib
import json
import math
import os
import re
import signal
import time
import urllib.error
import urllib.request
from urllib.parse import quote


def raw_evidence_read(route, limit):
    """One authenticated raw GET; original 30s socket timeout, no retry.

    Only repository-relative immutable routes built by evidence_bytes enter
    here. Never follow a metadata download_url or send credentials to it.
    The byte bound detects overlong/truncated responses without clipping proof.
    """
    repo = os.environ["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("repository identity required")
    request = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/" + route,
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Accept": "application/vnd.github.raw+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(limit)


def evidence_bytes(value, path, expected, *, commit=None, raw_get=None):
    """Decode inline content or read immutable large-file bytes, fail closed."""
    if (not isinstance(path, str) or not path.startswith(("reports/", "screenshots/"))
            or any(p in ("", ".", "..") for p in path.split("/"))
            or "?" in path or "#" in path):
        raise ValueError("evidence path required")
    if commit is not None and (not isinstance(commit, str)
                              or not re.fullmatch(r"[0-9a-f]{40}", commit)):
        raise ValueError("publication commit identity missing")
    if value.get("encoding") == "base64":
        return base64.b64decode("".join(value["content"].split()), validate=True)
    if value.get("encoding") != "none" or value.get("content") != "":
        raise ValueError("supported evidence encoding required")
    sha, size = value.get("sha"), value.get("size")
    if (value.get("type") != "file" or value.get("path") != path
            or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)
            or type(size) is not int or size != len(expected)):
        raise ValueError("large evidence metadata identity mismatch")
    expected_blob = hashlib.sha1(b"blob " + str(len(expected)).encode() + b"\0" + expected).hexdigest()
    if sha != expected_blob:
        raise AssertionError("large evidence blob differs from expected bytes")
    # Final publication uses its exact commit/path. A conflict refresh has no
    # commit identity, so read its immutable Git blob, never the moving branch.
    route = ("contents/" + quote(path, safe="/") + "?ref=" + commit
             if commit is not None else "git/blobs/" + sha)
    raw = (raw_evidence_read if raw_get is None else raw_get)(route, size + 1)
    if type(raw) is not bytes or len(raw) != size:
        raise AssertionError("large evidence exact length mismatch")
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if blob != sha or raw != expected:
        raise AssertionError("large evidence exact bytes mismatch")
    return raw


def verify_readback(api, path, commit, data, *, raw_get=None):
    """Read the immutable PUT commit, preserving exact-byte acceptance."""
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("publication commit identity missing")
    if (not isinstance(path, str) or not path.startswith(("reports/", "screenshots/"))
            or any(p in ("", ".", "..") for p in path.split("/"))
            or "?" in path or "#" in path):
        raise ValueError("evidence path required")
    actual = api("contents/" + quote(path, safe="/") + "?ref=" + commit)
    if evidence_bytes(actual, path, data, commit=commit, raw_get=raw_get) != data:
        raise AssertionError("evidence exact readback mismatch: " + path)
    return actual


def publish(api, path, data, pause=time.sleep, emit=lambda row: None, *, raw_get=None):
    """Bounded PUT-409 recovery, pinned exact readback, concurrent-target guard.

    api is the existing authenticated repository-relative JSON transport.
    A rerun may replace the originally observed target. A different writer's
    intervening target bytes must never be silently overwritten.
    """
    if not isinstance(data, bytes) or not data:
        raise ValueError("nonempty evidence bytes required")
    if (not isinstance(path, str) or not path.startswith(("reports/", "screenshots/"))
            or any(p in ("", ".", "..") for p in path.split("/"))):
        raise ValueError("evidence path required")
    endpoint = "contents/" + quote(path, safe="/")

    def current():
        try:
            return api(endpoint + "?ref=evidence")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            return None

    def content(value):
        return evidence_bytes(value, path, data, raw_get=raw_get)

    original = current()
    original_sha = None if original is None else original["sha"]
    observed = original
    for attempt in range(1, 4):
        body = {"message": "Record synthetic verification evidence",
                "branch": "evidence", "content": base64.b64encode(data).decode()}
        if observed is not None:
            body["sha"] = observed["sha"]
        emit({"event": "evidence_put", "path": path, "attempt": attempt})
        try:
            written = api(endpoint, "PUT", body)
        except urllib.error.HTTPError as exc:
            if exc.code != 409 or attempt == 3:
                raise
            emit({"event": "evidence_conflict", "path": path, "attempt": attempt,
                  "status": 409, "wait_seconds": attempt})
            pause(attempt)
            observed = current()
            refreshed_sha = None if observed is None else observed["sha"]
            if refreshed_sha != original_sha:
                if observed is not None and observed.get("encoding") == "none":
                    expected_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                    if observed.get("sha") != expected_blob or observed.get("size") != len(data):
                        raise RuntimeError("concurrent evidence target changed: " + path) from exc
                if observed is None or content(observed) != data:
                    raise RuntimeError("concurrent evidence target changed: " + path) from exc
            continue
        # Do not retry failed verification or GET errors. Inspect this exact commit,
        # never a moving branch, even if another job writes immediately afterward.
        commit = written["commit"]["sha"]
        if (not isinstance(commit, str) or len(commit) != 40
                or any(c not in "0123456789abcdef" for c in commit)):
            raise ValueError("publication commit identity missing")
        actual = verify_readback(api, path, commit, data, raw_get=raw_get)
        return {"url": actual["html_url"], "raw_url": actual["download_url"],
                "sha256": hashlib.sha256(data).hexdigest()}
    raise AssertionError("unreachable evidence publication exit")


def selftest(target=publish):
    data = b"synthetic fixture \xe6\x96\x87\n"
    old = b"old fixture\n"
    path = "reports/fixture.json"
    route = "contents/" + path
    commit = "c" * 40

    def error(code):
        return urllib.error.HTTPError("https://example.invalid/evidence", code,
                                      "fixture", {}, None)

    def value(raw, sha):
        return {"encoding": "base64", "content": base64.b64encode(raw).decode(),
                "sha": sha, "html_url": "https://example.invalid/verified",
                "download_url": "https://example.invalid/raw"}

    written = {"commit": {"sha": commit}}
    empty = lambda: error(404)
    good = lambda: value(data, "new")
    cases = [
        ("create", [empty(), written, good()], [None], [], None),
        ("replace_observed", [value(old, "old"), written, good()], ["old"], [], None),
        ("one_conflict", [empty(), error(409), empty(), written, good()],
         [None, None], [1], None),
        ("two_conflicts", [empty(), error(409), empty(), error(409), empty(),
                           written, good()], [None, None, None], [1, 2], None),
        ("branch_moves_target_stable", [value(old, "old"), error(409),
                                        value(old, "old"), written, good()],
         ["old", "old"], [1], None),
        ("same_bytes_appeared", [empty(), error(409), good(), written, good()],
         [None, "new"], [1], None),
        ("conflict_exhausted", [empty(), error(409), empty(), error(409), empty(),
                                error(409)], [None, None, None], [1, 2],
         urllib.error.HTTPError),
        ("different_target_appeared", [empty(), error(409), value(old, "other")],
         [None], [1], RuntimeError),
        ("different_target_replaced", [value(old, "old"), error(409),
                                      value(b"other", "other")],
         ["old"], [1], RuntimeError),
        ("target_disappeared", [value(old, "old"), error(409), empty()],
         ["old"], [1], RuntimeError),
        ("readback_mismatch", [empty(), written, value(old, "bad")],
         [None], [], AssertionError),
        ("readback_http409", [empty(), written, error(409)],
         [None], [], urllib.error.HTTPError),
        ("readback_timeout", [empty(), written, TimeoutError("readback")],
         [None], [], TimeoutError),
        ("initial_get403", [error(403)], [], [], urllib.error.HTTPError),
        ("initial_get409", [error(409)], [], [], urllib.error.HTTPError),
        ("refresh_get403", [empty(), error(409), error(403)],
         [None], [1], urllib.error.HTTPError),
        ("put_timeout", [empty(), TimeoutError("uncertain PUT")],
         [None], [], TimeoutError),
    ]
    for code in (400, 401, 403, 404, 422, 429, 500, 503):
        cases.append(("put_" + str(code), [empty(), error(code)],
                      [None], [], urllib.error.HTTPError))
    for name, answers, shas, waits, failure in cases:
        calls, bodies, sleeps, events = [], [], [], []

        def api(url, method="GET", body=None):
            assert len(calls) < len(answers), name + " unexpected retry"
            if method == "PUT":
                assert url == route and body["branch"] == "evidence"
                assert base64.b64decode(body["content"]) == data
                assert body.get("sha") == shas[len(bodies)]
                bodies.append(copy.deepcopy(body))
            else:
                assert method == "GET" and body is None
                # Only the last successful readback may use the immutable commit.
                expected = route + "?ref=" + (
                    commit if len(calls) and answers[len(calls)-1] == written else "evidence")
                assert url == expected, (name, url, expected)
            answer = answers[len(calls)]
            calls.append((url, method))
            if isinstance(answer, Exception):
                raise answer
            return copy.deepcopy(answer)

        caught = None
        try:
            result = target(api, path, data, sleeps.append, events.append)
        except Exception as exc:
            caught = exc
        if failure is None:
            assert caught is None, (name, repr(caught))
            assert result == {"url": "https://example.invalid/verified",
                              "raw_url": "https://example.invalid/raw",
                              "sha256": hashlib.sha256(data).hexdigest()}
        else:
            assert type(caught) is failure, (name, repr(caught), failure)
        assert len(calls) == len(answers), (name, "unconsumed script")
        assert len(bodies) == len(shas) and sleeps == waits, name
        assert [e["attempt"] for e in events if e["event"] == "evidence_put"] == list(range(1, len(shas)+1))
        assert [e["status"] for e in events if e["event"] == "evidence_conflict"] == [409]*len(waits)
    print(json.dumps({"scope": "HOST_TRANSPORT_CONTROLS_NOT_GITHUB_OR_ANDROID",
                      "cases": len(cases), "status": "PASS"}))


class InitialReadBudgetExceeded(TimeoutError):
    """The initial read's single wall-clock budget expired."""


@contextlib.contextmanager
def initial_read_deadline(seconds):
    """Main-thread POSIX timer also bounds DNS and slow/trickling response reads."""
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("positive finite initial-read deadline required")
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise RuntimeError("initial-read timer already owned")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(signum, frame):
        raise InitialReadBudgetExceeded("initial evidence read wall-clock budget expired")

    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def initial_evidence_read(api, path, *, clock=time.monotonic,
                          guard=initial_read_deadline, emit=lambda row: None):
    """Opt-in initial GET only: three attempts within ONE 30-second deadline.

    Not used by publish(), its conflict-refresh GETs, any PUT, or pinned readback.
    HTTP errors (including 404), wrapped URL errors and malformed JSON propagate.
    The existing caller alone interprets an observed HTTP 404 as absent.
    """
    if (not isinstance(path, str) or not path.startswith("reports/")
            or any(part in ("", ".", "..") for part in path.split("/"))
            or "?" in path or "#" in path):
        raise ValueError("initial evidence report path required")
    endpoint = "contents/" + quote(path, safe="/") + "?ref=evidence"
    deadline = clock() + 30.0
    with guard(30.0):
        for attempt in range(1, 4):
            remaining = deadline - clock()
            if remaining <= 0:
                raise InitialReadBudgetExceeded("initial evidence read budget exhausted")
            timeout = min(10.0, remaining)
            emit({"event": "evidence_initial_get", "attempt": attempt,
                  "timeout_seconds": timeout, "remaining_seconds": remaining})
            try:
                value = api(endpoint, timeout=timeout)
            except InitialReadBudgetExceeded:
                raise
            except TimeoutError:
                emit({"event": "evidence_initial_timeout", "attempt": attempt})
                if attempt == 3 or clock() >= deadline:
                    raise
                continue
            if clock() >= deadline:
                raise InitialReadBudgetExceeded("initial evidence read exceeded 30 seconds")
            return value
    raise AssertionError("unreachable initial evidence read exit")


def initial_read_selftest():
    """Actual helper controls with scripted HTTP, not actual GitHub/Android."""
    import inspect
    import textwrap

    def controls(target, witness_only=False):
        good = {"sha": "before-write"}
        cases = [
            ("success", [(0, good)], None, [10.0]),
            ("one_timeout", [(10, TimeoutError("first")), (0, good)], None, [10.0, 10.0]),
            ("two_timeouts", [(10, TimeoutError("first")), (10, TimeoutError("second")), (9, good)],
             None, [10.0, 10.0, 10.0]),
            ("exhausted", [(1, TimeoutError("one")), (1, TimeoutError("two")), (1, TimeoutError("three"))],
             TimeoutError, [10.0, 10.0, 10.0]),
            ("deadline_timeout", [(30, TimeoutError("slow"))], TimeoutError, [10.0]),
            ("late_success", [(30, good)], InitialReadBudgetExceeded, [10.0]),
            ("remaining_budget", [(23, TimeoutError("slow")), (6, good)], None, [10.0, 7.0]),
            ("deadline_interrupt", [(0, InitialReadBudgetExceeded("alarm"))],
             InitialReadBudgetExceeded, [10.0]),
        ]
        for code in (400, 401, 403, 404, 409, 422, 429, 500, 503):
            error = urllib.error.HTTPError("https://example.invalid", code, "fixture", {}, None)
            cases.append(("http_" + str(code), [(0, error)], urllib.error.HTTPError, [10.0]))
        for error in (ValueError("json"), KeyError("sha"), OSError("socket"),
                      ConnectionResetError("reset"), AssertionError("assertion"),
                      urllib.error.URLError(TimeoutError("wrapped-not-approved"))):
            cases.append((type(error).__name__, [(0, error)], type(error), [10.0]))
        error = urllib.error.HTTPError("https://example.invalid", 404, "absent", {}, None)
        cases.append(("timeout_then_absent", [(10, TimeoutError("first")), (0, error)],
                      urllib.error.HTTPError, [10.0, 10.0]))
        for name, answers, failure, expected_timeouts in (cases[:1] if witness_only else cases):
            now, calls, guards, events = [0.0], [], [], []

            @contextlib.contextmanager
            def guard(seconds):
                guards.append(seconds)
                yield

            def api(path, method="GET", body=None, *, timeout):
                assert path == "contents/reports/fixture.json?ref=evidence", name + ": route"
                assert method == "GET" and body is None, name + ": initial GET only"
                assert len(calls) < len(answers), name + ": unexpected retry"
                delay, value = answers[len(calls)]
                calls.append(timeout)
                now[0] += delay
                if isinstance(value, Exception):
                    raise value
                return value

            caught = None
            try:
                result = target(api, "reports/fixture.json", clock=lambda: now[0],
                                guard=guard, emit=events.append)
            except Exception as exc:
                caught = exc
            if failure is None:
                assert caught is None and result is good, name + ": success contract"
            else:
                assert type(caught) is failure, name + ": failure identity"
                if isinstance(answers[-1][1], Exception):
                    assert caught is answers[-1][1], name + ": original exception preserved"
            assert calls == expected_timeouts, name + ": exact attempts/timeouts"
            assert guards == [30.0], name + ": one outer deadline"
            starts = [row for row in events if row["event"] == "evidence_initial_get"]
            assert [row["attempt"] for row in starts] == list(range(1, len(calls) + 1)), name + ": receipt"
            assert [row["timeout_seconds"] for row in starts] == calls, name + ": timeout receipt"
        if witness_only:
            return 1
        invalid = [None, "", "screenshots/a", "../reports/a", "reports/../a", "reports//a",
                   "reports/./a", "reports/a?ref=other", "reports/a#fragment"]
        for path in invalid:
            calls = []
            try:
                target(lambda *a, **k: calls.append(a), path)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid path accepted")
            assert not calls, "invalid path reached transport"
        return len(cases) + len(invalid)

    checks = controls(initial_evidence_read)
    original = textwrap.dedent(inspect.getsource(initial_evidence_read))
    edits = [
        ("no_retry", "range(1, 4)", "range(1, 2)", "one_timeout"),
        ("four_attempts", "attempt == 3", "attempt == 4", "exhausted"),
        ("wide_retry", "except TimeoutError:", "except OSError:", "http_400"),
        ("per_call_30", "min(10.0, remaining)", "min(30.0, remaining)", "success"),
        ("late_pass", 'raise InitialReadBudgetExceeded("initial evidence read exceeded 30 seconds")',
         "return value", "late_success"),
        ("no_guard", "with guard(30.0):", "with contextlib.nullcontext():", "success"),
    ]
    rejected = []
    for name, old, new, expected in edits:
        assert original.count(old) == 1, name + ": mutation must apply exactly once"
        env = dict(globals())
        exec(compile(original.replace(old, new, 1), "<initial-read-mutant-" + name + ">", "exec"), env)
        mutant = env["initial_evidence_read"]
        # All compiled mutants first complete a valid read, before their rejection.
        witness = {"sha": "valid"}
        assert mutant(lambda *a, **k: witness, "reports/fixture.json",
                      clock=lambda: 0.0, guard=lambda seconds: contextlib.nullcontext()) is witness
        try:
            controls(mutant)
        except AssertionError as exc:
            assert expected in str(exc), (name, str(exc))
            rejected.append(name)
        else:
            raise AssertionError(name + ": mutant survived")
    previous = signal.getsignal(signal.SIGALRM)
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    try:
        with initial_read_deadline(0.02):
            time.sleep(0.2)
    except InitialReadBudgetExceeded:
        pass
    else:
        raise AssertionError("real timer failed to interrupt blocked work")
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    with initial_read_deadline(1.0):
        pass
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    for value in (0, -1, float("nan"), float("inf"), True):
        try:
            with initial_read_deadline(value):
                raise AssertionError("invalid timer entered")
        except ValueError:
            pass
    signal.setitimer(signal.ITIMER_REAL, 5)
    try:
        try:
            with initial_read_deadline(1):
                raise AssertionError("existing timer overwritten")
        except RuntimeError:
            pass
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    print("INITIAL_EVIDENCE_READ_CONTROLS " + json.dumps({
        "status": "PASS", "cases": checks, "timer_controls": 8,
        "witnessed_compiled_mutants": rejected,
        "scope": "HOST_SCRIPTED_HTTP_AND_POSIX_TIMER_NOT_GITHUB_OR_ANDROID",
        "release_ready": False}))


def large_readback_selftest():
    """Real helper/publisher with scripted HTTP, not live GitHub acceptance."""
    import inspect
    import io
    from unittest.mock import patch

    path, commit = "reports/large.json", "c"*40
    data = (b'{"trace":"' + b"x"*1473569 + b'"}\n')
    assert len(data) > 1024*1024
    sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    metadata = dict(type="file", path=path, size=len(data), sha=sha, encoding="none",
                    content="", html_url="https://example.invalid/verified",
                    download_url="https://untrusted.invalid/do-not-follow")
    route = "contents/" + path + "?ref=" + commit
    checks = 0

    def controls(target):
        nonlocal checks
        calls = []

        def api(url):
            assert url == route, "immutable JSON route"
            calls.append(("json", url))
            return dict(metadata)

        def raw(url, limit):
            assert url == route and limit == len(data)+1, "immutable raw route/bound"
            calls.append(("raw", url))
            return data

        assert target(api, path, commit, data, raw_get=raw) == metadata
        assert calls == [("json", route), ("raw", route)]
        checks += 1
        # Text is never reserialized: unicode, whitespace and arbitrary bytes
        # follow the same exact identity contract as JSON reports.
        for payload in (b"small \xff\0\n", "\u6587\n".encode()):
            inline = dict(encoding="base64", content=base64.b64encode(payload).decode())
            assert target(lambda url: inline, path, commit, payload,
                          raw_get=lambda *a: (_ for _ in ()).throw(AssertionError("raw on inline"))) == inline
            checks += 1

        negatives = [
            ("wrong_size", dict(metadata, size=len(data)-1), data, ValueError, 0),
            ("bool_size", dict(metadata, size=True), data, ValueError, 0),
            ("wrong_path", dict(metadata, path="reports/other.json"), data, ValueError, 0),
            ("wrong_type", dict(metadata, type="dir"), data, ValueError, 0),
            ("wrong_blob", dict(metadata, sha="a"*40), data, AssertionError, 0),
            ("missing_blob", dict(metadata, sha=None), data, ValueError, 0),
            ("unexpected_inline", dict(metadata, content="not empty"), data, ValueError, 0),
            ("encoding", dict(metadata, encoding="gzip"), data, ValueError, 0),
            ("truncated", metadata, data[:-1], AssertionError, 1),
            ("overlong", metadata, data+b"x", AssertionError, 1),
            ("corrupt", metadata, b"!"+data[1:], AssertionError, 1),
            ("not_bytes", metadata, data.decode(), AssertionError, 1),
            ("inline_mismatch", dict(encoding="base64", content="eA=="), data, AssertionError, 0),
        ]
        for name, meta, payload, error, expected_raw in negatives:
            seen = []
            def get_raw(url, limit):
                seen.append((url, limit))
                return payload
            try:
                target(lambda url: dict(meta), path, commit, data, raw_get=get_raw)
            except error:
                pass
            else:
                raise AssertionError(name + ": invalid proof accepted")
            assert len(seen) == expected_raw, name + ": unexpected read"
            checks += 1
        for invalid in ("evidence", "c"*39, "C"*40, None, 123):
            seen = []
            try:
                target(lambda *a: seen.append(a), path, invalid, data, raw_get=raw)
            except ValueError:
                pass
            else:
                raise AssertionError("mutable/invalid commit accepted")
            assert seen == [], "bad commit reached transport"
            checks += 1
        for invalid in ("reports/../x", "reports//x", "reports/a?ref=evidence", "reports/a#x"):
            seen = []
            try:
                target(lambda *a: seen.append(a), invalid, commit, data, raw_get=raw)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid path accepted")
            assert seen == []
            checks += 1
        for stage in ("json", "raw"):
            for failure in (TimeoutError("original"), urllib.error.HTTPError(
                    "https://example.invalid", 503, "original", {}, None), ValueError("malformed")):
                seen = []
                def get_json(url):
                    seen.append("json")
                    if stage == "json":
                        raise failure
                    return dict(metadata)
                def get_raw(url, limit):
                    seen.append("raw")
                    raise failure
                try:
                    target(get_json, path, commit, data, raw_get=get_raw)
                except Exception as exc:
                    assert exc is failure, "original exception replaced"
                else:
                    raise AssertionError("read failure accepted")
                assert seen == (["json"] if stage == "json" else ["json", "raw"]), "read retried"
                checks += 1

    controls(verify_readback)
    primary_checks = checks
    # Run the actual shared publisher through large create + conflict routes.
    for mode in ("create", "same", "different", "raw_error"):
        calls, waits, raw_calls = [], [], []
        answers = [urllib.error.HTTPError("https://example.invalid", 404, "absent", {}, None)]
        written = {"commit": {"sha": commit}}
        if mode != "create":
            answers += [urllib.error.HTTPError("https://example.invalid", 409, "conflict", {}, None),
                        dict(metadata, sha="a"*40) if mode == "different" else metadata]
        if mode in ("create", "same"):
            answers += [written, metadata]
        failure = TimeoutError("conflict raw")
        def api(url, method="GET", body=None):
            assert len(calls) < len(answers), "publisher retry count"
            if method == "PUT":
                assert url == "contents/"+path and body["branch"] == "evidence"
                assert base64.b64decode(body["content"]) == data
            else:
                assert url == "contents/"+path+"?ref="+(
                    commit if calls and answers[len(calls)-1] == written else "evidence")
            result = answers[len(calls)]
            calls.append((url, method))
            if isinstance(result, Exception):
                raise result
            return dict(result)
        def raw(url, limit):
            raw_calls.append(url)
            assert limit == len(data)+1
            assert url in (route, "git/blobs/"+sha)
            if mode == "raw_error":
                raise failure
            return data
        try:
            result = publish(api, path, data, waits.append, raw_get=raw)
        except Exception as exc:
            assert (mode == "different" and type(exc) is RuntimeError) or (
                mode == "raw_error" and exc is failure), (mode, repr(exc))
        else:
            assert mode in ("create", "same")
            assert result["sha256"] == hashlib.sha256(data).hexdigest()
        assert len(calls) == len(answers)
        assert waits == ([] if mode == "create" else [1])
        assert raw_calls == {"create": [route], "same": ["git/blobs/"+sha, route],
                             "different": [], "raw_error": ["git/blobs/"+sha]}[mode]
    # Exercise the real raw transport with a response double. No network or
    # credentials leave this process; assert timeout/media/byte-limit exactly.
    transport_calls = []
    sentinel = "host-" + "sentinel"
    class Response(io.BytesIO):
        def read(self, limit=-1):
            assert limit == len(data)+1, "raw byte bound changed"
            return super().read(limit)
    def open_request(request, timeout):
        transport_calls.append(request.full_url)
        assert timeout == 30
        assert request.get_header("Accept") == "application/vnd.github.raw+json"
        assert request.get_header("Authorization") == "Bearer "+sentinel
        assert request.full_url == "https://api.github.com/repos/fixture/repo/"+route
        return Response(data)
    with patch.dict(os.environ, {"GITHUB_REPOSITORY": "fixture/repo", "GH_TOKEN": sentinel}):
        with patch.object(urllib.request, "urlopen", open_request):
            assert verify_readback(lambda url: metadata, path, commit, data) == metadata
    assert len(transport_calls) == 1
    # Witness each compiled mutation on valid data before testing rejection.
    rejected = []
    for name, function, before, after, expected_failure in (
        ("skip_inline_identity", verify_readback,
         'if evidence_bytes(actual, path, data, commit=commit, raw_get=raw_get) != data:',
         'if evidence_bytes(actual, path, data, commit=commit, raw_get=raw_get) is None:',
         "inline_mismatch"),
        ("moving_raw_ref", evidence_bytes, '"?ref=" + commit', '"?ref=evidence"',
         "immutable raw route"),
    ):
        source = inspect.getsource(function)
        assert source.count(before) == 1
        env = dict(globals())
        exec(compile(source.replace(before, after, 1), "<large-readback-mutant>", "exec"), env)
        # A valid inline observation is an independent positive witness.
        assert env["evidence_bytes"]({"encoding":"base64","content":"eA=="}, path, b"x") == b"x"
        if function is evidence_bytes:
            exec(compile(inspect.getsource(verify_readback), "<readback-caller>", "exec"), env)
        assert env["verify_readback"](lambda url: {"encoding":"base64","content":"eA=="},
                                      path, commit, b"x")["content"] == "eA=="
        try:
            controls(env["verify_readback"])
        except AssertionError as exc:
            assert expected_failure in str(exc)
            rejected.append(name)
        else:
            raise AssertionError("large readback mutant survived: "+name)
    print("LARGE_EVIDENCE_READBACK " + json.dumps(dict(
        status="PASS", readback_cases=primary_checks, publisher_cases=4,
        transport_cases=1, witnessed_mutants=rejected,
        scope="HOST_SCRIPTED_HTTP_NOT_LIVE_GITHUB_OR_ANDROID", release_ready=False)))


if __name__ == "__main__":
    selftest()
    initial_read_selftest()
    large_readback_selftest()
