#!/usr/bin/env python3
"""Evidence-only conflict recovery. No device assertion retries."""
import base64
import copy
import hashlib
import json
import time
import urllib.error
from urllib.parse import quote


def publish(api, path, data, pause=time.sleep, emit=lambda row: None):
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
        if value.get("encoding") != "base64":
            raise ValueError("base64 evidence readback required")
        return base64.b64decode("".join(value["content"].split()), validate=True)

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
                if observed is None or content(observed) != data:
                    raise RuntimeError("concurrent evidence target changed: " + path) from exc
            continue
        # Do not retry failed verification or GET errors. Inspect this exact commit,
        # never a moving branch, even if another job writes immediately afterward.
        commit = written["commit"]["sha"]
        if (not isinstance(commit, str) or len(commit) != 40
                or any(c not in "0123456789abcdef" for c in commit)):
            raise ValueError("publication commit identity missing")
        actual = api(endpoint + "?ref=" + commit)
        if content(actual) != data:
            raise AssertionError("evidence exact readback mismatch: " + path)
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


if __name__ == "__main__":
    selftest()
