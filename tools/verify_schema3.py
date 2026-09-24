#!/usr/bin/env python3
"""Mandatory independent observer for opt-in SQLite3 tests; no release claim."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

LABELS = {
    "seed": [
        "frozen_v2_input", "migration_version_and_column", "migration_preserves_all_old_cells",
        "legacy_origin_fallback", "snapshot_is_read_only", "first_derivative_persisted",
        "sibling_note_isolated", "stale_full_state_rejected", "second_derivative_keeps_original",
        "metadata_preserves_pair", "missing_registry_rolls_back", "wrong_origin_rolls_back",
        "text_target_rejected", "same_revision_external_change_rejected",
        "late_sql_fault_rolls_back_target_and_revision", "all_original_and_derived_bytes_unchanged",
        "snapshot_caller_mutation_isolated", "old_helper_refuses_without_damage",
        "partial_schema_conflict_not_hidden",
        "comparison_buffer_exact_limit_and_atomic_rejection",
        "oversize_comparison_snapshot_rejected",
        "oversize_save_and_fixture_rollback_preserve_state",
        "fresh_schema3_empty_layout", "fresh_schema3_reference_write", "frozen_v1_input",
        "v1_to_3_preserves_old_cells", "v1_to_3_reference_write",
        "v1_late_conflict_rolls_back_all_ddl", "future_schema_refused_without_damage",
        "ordinary_note_read_owned_projection", "ordinary_metadata_order_and_origin_preserved",
        "ordinary_save_sibling_isolated", "ordinary_replacement_kind_duplicate_and_missing_refused",
        "ordinary_late_missing_media_rolls_back", "ordinary_same_revision_stale_rejected",
        "ordinary_late_sql_fault_rolls_back", "ordinary_remove_keeps_shared_registry",
        "ordinary_postwrite_budget_rolls_back", "image_postwrite_budget_rolls_back",
        "postwrite_budget_small_edits_usable",
        "legacy_candidate_zip_strict_roundtrip", "legacy_candidate_input_owned_and_no_helper_file",
        "legacy_candidate_rejects_invalid_transport", "legacy_candidate_rejects_semantic_poison",
        "legacy_candidate_rejects_noncanonical_before_migration",
        "legacy_candidate_migration_preserves_old_cells",
        "legacy_candidate_rejections_and_migration_leave_source_unchanged",
        "wire_legacy_dispatch_normalizes", "wire_schema3_exact_roundtrip_preserves_pairs",
        "wire_input_output_and_candidate_owned", "wire_old_decoder_refuses_new_format",
        "wire_rejects_invalid_header_lengths_utf8_and_trailing",
        "wire_rejects_semantic_poison_and_noncanonical_order",
        "wire_origin_constraints_without_global_digest_owner",
    ],
    "reopen": [
        "separate_process_exact_state", "separate_process_pair_metadata",
        "separate_process_media_bytes", "separate_process_write_usable",
        "fresh_schema3_separate_process_exact", "ordinary_note_separate_process_origin_and_order",
        "v1_to_3_separate_process_exact",
        "postwrite_budget_separate_process_exact",
        "wire_separate_process_exact_candidate",
    ],
    "restore_seed": [
        "restore_preview_owned_read_only_counts", "restore_cancel_idempotent_consumed",
        "restore_foreign_same_file_helper_refused", "restore_helper_close_invalidates_session",
        "restore_other_connection_same_revision_stale_refused",
        "restore_staged_tamper_refused_before_publication",
        "restore_failed_attempt_consumed_and_cleaned", "restore_outer_transaction_refused",
        "restore_late_sql_rollback_keeps_old_state_and_published_blobs",
        "restore_new_exact_state_origins_and_all_assets", "restore_success_duplicate_refused",
        "restore_old_complete_replacement", "restore_full_complete_replacement",
        "restore_empty_complete_replacement",
    ],
    "restore_reopen": [
        "restore_new_independent_process_exact", "restore_old_independent_process_exact",
        "restore_full_independent_process_exact", "restore_empty_independent_process_exact",
    ],
}

def observe(text, phase, api):
    labels = re.findall(r"(?:^|stream=)SCHEMA3_PASS ([^\r\n]+)", text, re.M)
    result = re.findall(r"(?:^|stream=)SCHEMA3_RESULT ([^\r\n]+)", text, re.M)
    finished = re.findall(r"^INSTRUMENTATION_CODE: (-?\d+)\s*$", text, re.M)
    passed = (labels == LABELS[phase] and
              result == [f"{phase} {api} {len(LABELS[phase])} PASS"] and
              finished == ["-1"] and "SCHEMA3_FAILED" not in text and
              "INSTRUMENTATION_FAILED" not in text)
    return {"status": "PASS" if passed else "NOT_VERIFIED", "labels": labels,
            "expected_labels": LABELS[phase], "checks": len(labels),
            "log_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "failure_tail": None if passed else text[-9000:]}

def registration(text, runner):
    package = "com.supercubegame.pockettodo.v12.preview"
    expected = [(package + ".test/com.supercubegame.pockettodo." + runner, package)]
    rows = re.findall(r"^instrumentation:(\S+) \(target=([^)]+)\)\s*$", text, re.M)
    relevant = [row for row in rows if row[0].startswith(package + ".test/")]
    passed = relevant == expected
    return {"status": "PASS" if passed else "NOT_VERIFIED", "registered": relevant,
            "expected_runner": runner, "log": text}

def selftest():
    controls = {}
    for phase, labels in LABELS.items():
        records = "".join("SCHEMA3_PASS " + x + "\n" for x in labels)
        marker = f"SCHEMA3_RESULT {phase} 26 {len(labels)} PASS\n"
        good = records + marker + "INSTRUMENTATION_CODE: -1\n"
        assert observe(good, phase, 26)["status"] == "PASS"
        assert observe(good.replace("\n", "\r\n"), phase, 26)["status"] == "PASS"
        bad = {
            "entire_suite_missing": "INSTRUMENTATION_CODE: -1\n",
            "label_missing": good.replace("SCHEMA3_PASS " + labels[-1] + "\n", "", 1),
            "consistent_missing": good.replace("SCHEMA3_PASS " + labels[-1] + "\n", "", 1).replace(f"26 {len(labels)} PASS", f"26 {len(labels)-1} PASS", 1),
            "label_duplicate": records + "SCHEMA3_PASS " + labels[0] + "\n" + marker + "INSTRUMENTATION_CODE: -1\n",
            "label_substituted": good.replace(labels[-1], "unknown", 1),
            "result_missing": good.replace(marker, "", 1),
            "result_duplicate": good + marker,
            "wrong_api": good.replace("26 "+str(len(labels)), "34 "+str(len(labels)), 1),
            "wrong_phase": good.replace("RESULT "+phase, "RESULT wrong", 1),
            "failure": good + "SCHEMA3_FAILED\n",
            "instrumentation_failure": good + "INSTRUMENTATION_FAILED\n",
            "bad_finish": good.replace("CODE: -1", "CODE: 0"),
            "missing_finish": good.replace("INSTRUMENTATION_CODE: -1\n", ""),
        }
        for name, text in bad.items():
            assert text != good, "mutation not applied: " + name
            assert observe(text, phase, 26)["status"] != "PASS", "missed: " + name
        controls[phase] = {"positive": 2, "negative": len(bad), "mutants": list(bad)}
    package = "com.supercubegame.pockettodo.v12.preview"
    prefix = "instrumentation:" + package + ".test/com.supercubegame.pockettodo."
    old = prefix + "V12DeviceTest (target=" + package + ")\n"
    new = prefix + "Schema3DeviceTest (target=" + package + ")\n"
    assert registration(old, "V12DeviceTest")["status"] == "PASS"
    assert registration(new, "Schema3DeviceTest")["status"] == "PASS"
    assert registration(new + "instrumentation:other/Runner (target=other)\n", "Schema3DeviceTest")["status"] == "PASS"
    bad = ("", old, new + new, old + new,
           new.replace("target=" + package, "target=wrong"),
           new.replace("Schema3DeviceTest", "WrongRunner"))
    for text in bad:
        assert registration(text, "Schema3DeviceTest")["status"] != "PASS", "runner registration guard missed"
    assert registration(new, "V12DeviceTest")["status"] != "PASS"
    controls["registration"] = {"positive": 3, "negative": len(bad) + 1}
    controls["native_failure_diagnostics"] = diagnostics_selftest()
    return controls

def diagnostics_selftest():
    import tempfile
    from types import SimpleNamespace
    gate = SimpleNamespace(SERIAL="test-serial", PKG="test.package")
    original = subprocess.CalledProcessError(255, ["adb", "shell", "run-as"],
                                            output=b"stdout-sentinel\xff", stderr="stderr-sentinel")
    calls = []
    def probe(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=7, stdout="probe-output", stderr="probe-error")
    evidence = native_failure_evidence("adb", gate, original, run=probe)
    assert evidence["original"]["returncode"] == 255
    assert evidence["original"]["stdout"]["tail"] == "stdout-sentinel\ufffd"
    assert evidence["original"]["stderr"]["tail"] == "stderr-sentinel"
    assert evidence["status"] == "DIAGNOSTIC_ONLY_NOT_RETRY_OR_ACCEPTANCE"
    assert len(calls) == 4 and all(c[1]["timeout"] == 10 for c in calls)
    assert all(p["returncode"] == 7 and p["stderr"]["tail"] == "probe-error"
               for p in evidence["probes"])
    assert output_evidence(None) == {"captured": False, "tail": None, "truncated": False}
    assert output_evidence("x" * 9000) == {"captured": True, "tail": "x" * 4096, "truncated": True}
    def broken_probe(*args, **kwargs):
        raise subprocess.TimeoutExpired(["probe"], 10, output=b"partial", stderr=b"timeout-error")
    timed = native_failure_evidence("adb", gate, original, run=broken_probe)
    assert len(timed["probes"]) == 4
    assert all(p["error"]["type"] == "TimeoutExpired" and
               p["error"]["stderr"]["tail"] == "timeout-error" for p in timed["probes"])
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        baseline = {"status": "FAIL", "count": 47, "checks": ["sentinel"],
                    "error": repr(original), "release_ready": False}
        report_path = root / "native-result.json"
        report_path.write_text(json.dumps(baseline))
        invocation = []
        def fail(adb):
            invocation.append(adb)
            raise original
        def collect(*args):
            return evidence
        try:
            native_with_diagnostics("adb", gate, fail, root=root, collect=collect)
            raise AssertionError("native failure swallowed")
        except subprocess.CalledProcessError as caught:
            assert caught is original
        result = json.loads(report_path.read_text())
        assert result.pop("failure_diagnostics") == evidence and result == baseline
        assert invocation == ["adb"], "original native suite retried"
        assert json.loads((root / "native-failure-diagnostics.json").read_text()) == evidence
        def forbidden(*args):
            raise AssertionError("success must not run diagnostics")
        assert native_with_diagnostics("adb", gate, lambda adb: "success",
                                       root=root, collect=forbidden) == "success"
        def failed_collect(*args):
            raise OSError("diagnostic write/probe failure")
        for collector, target in ((failed_collect, root), (collect, root / "missing")):
            try:
                native_with_diagnostics("adb", gate, fail, root=target, collect=collector)
                raise AssertionError("diagnostic failure masked original")
            except subprocess.CalledProcessError as caught:
                assert caught is original
    return {"checks": 8, "scope": "HOST_PYTHON_INJECTED_FAILURES_NOT_DEVICE_ROOT_CAUSE"}

def output_evidence(value):
    if value is None:
        return {"captured": False, "tail": None, "truncated": False}
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    return {"captured": True, "tail": text[-4096:], "truncated": len(text) > 4096}

def exception_evidence(exc):
    return {"type": type(exc).__name__, "message": str(exc),
            "command": getattr(exc, "cmd", None), "returncode": getattr(exc, "returncode", None),
            "stdout": output_evidence(getattr(exc, "stdout", None)),
            "stderr": output_evidence(getattr(exc, "stderr", None))}

def native_failure_evidence(adb, gate, exc, run=None):
    # Read-only probes are NOT retries and can never turn the original failure green.
    # The old shell helper does not capture stderr: report that absence explicitly.
    run = subprocess.run if run is None else run
    prefix = [str(adb), "-s", gate.SERIAL]
    commands = [
        ("transport", ["get-state"]),
        ("shell_identity", ["shell", "id"]),
        ("app_identity", ["shell", "run-as", gate.PKG, "id"]),
        ("database_directory", ["shell", "run-as", gate.PKG, "ls", "databases"]),
    ]
    result = {"status": "DIAGNOSTIC_ONLY_NOT_RETRY_OR_ACCEPTANCE",
              "original": exception_evidence(exc), "probes": []}
    for name, args in commands:
        row = {"name": name, "command": prefix + args}
        try:
            p = run(prefix + args, capture_output=True, text=True, timeout=10)
            row.update(returncode=p.returncode, stdout=output_evidence(p.stdout),
                       stderr=output_evidence(p.stderr))
        except Exception as failure:
            row["error"] = exception_evidence(failure)
        result["probes"].append(row)
    return result

def native_with_diagnostics(adb, gate, original, root=None, collect=None):
    root = Path("native-ui") if root is None else root
    collect = native_failure_evidence if collect is None else collect
    try:
        return original(adb)
    except Exception as exc:
        try:
            evidence = collect(adb, gate, exc)
            print("NATIVE_FAILURE_DIAGNOSTICS " + json.dumps(evidence, ensure_ascii=False), flush=True)
            (root / "native-failure-diagnostics.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2))
            path = root / "native-result.json"
            if path.exists():
                result = json.loads(path.read_text())
                # Preserve status, checks, count and the original error verbatim.
                result["failure_diagnostics"] = evidence
                path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as diagnostic_error:
            print("NATIVE_DIAGNOSTICS_INCOMPLETE " + repr(diagnostic_error), flush=True)
        raise

def require_registration(adb, gate, stage, runner):
    prefix = [str(adb), "-s", gate.SERIAL]
    p = subprocess.run(prefix + ["shell", "pm", "list", "instrumentation"],
                       capture_output=True, text=True, timeout=30)
    text = p.stdout + "\n" + p.stderr
    Path("device-schema3-registration-" + stage + ".txt").write_text(text)
    print(text, flush=True)
    assert p.returncode == 0 and registration(text, runner)["status"] == "PASS", "installed test APK runner/target mismatch: " + stage

def device(adb, gate, runner="Schema3DeviceTest", phases=("seed", "reopen")):
    prefix = [str(adb), "-s", gate.SERIAL]
    for phase in phases:
        if phase.endswith("reopen"):
            subprocess.run(prefix + ["shell", "am", "force-stop", gate.PKG], check=True, timeout=30)
            p = subprocess.run(prefix + ["shell", "pidof", gate.PKG], capture_output=True, text=True, timeout=10)
            assert p.returncode == 1 and not p.stdout.strip(), "prior app process still alive"
        args = prefix + ["shell", "am", "instrument", "-w", "-r", "-e", "phase", phase,
                         "-e", "expectedApi", str(gate.API),
                         gate.PKG + ".test/com.supercubegame.pockettodo." + runner]
        p = subprocess.run(args, capture_output=True, text=True, timeout=180)
        text = p.stdout + "\n" + p.stderr
        Path("device-schema3-" + phase + ".txt").write_text(text)
        print(text, flush=True)
        assert p.returncode == 0 and observe(text, phase, gate.API)["status"] == "PASS", "schema3 " + phase + " failed; inspect device-schema3 log"

def certificate(apk, gate):
    tool = gate.SDK / "build-tools/35.0.0/apksigner"
    p = subprocess.run([str(tool), "verify", "--verbose", "--print-certs", str(apk)],
                       capture_output=True, text=True, timeout=30)
    values = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})$", p.stdout, re.M)
    assert p.returncode == 0 and len(values) == 1, "APK must have one verified signing certificate"
    return values[0]

def isolated_runner(adb, gate, build_env):
    # One runner per test APK, selected through AGP's documented runner setting.
    # Never uninstall or reinstall the product APK, and retain default test bytes.
    import shutil
    prefix = [str(adb), "-s", gate.SERIAL]
    tests = list(Path("build/outputs/apk/androidTest/debug").glob("*.apk"))
    apps = list(Path("build/outputs/apk/debug").glob("*.apk"))
    assert len(tests) == len(apps) == 1, "ambiguous APK outputs"
    test, app = tests[0], apps[0]
    saved = Path("build/schema3-runner/default-test.apk")
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(test, saved)
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    app_before, test_before = digest(app), digest(saved)
    app_certificate, test_certificate = certificate(app, gate), certificate(saved, gate)
    assert app_certificate == test_certificate, "default app/test signing certificates differ"
    require_registration(adb, gate, "default", "V12DeviceTest")
    try:
        args = ["gradle", "--no-daemon", "--console=plain", "-PpocketSchema3Runner=true", "assembleDebugAndroidTest"]
        # Emulator setup changes ANDROID_USER_HOME. Build with the environment
        # captured before that setup so AGP reuses the original debug keystore.
        p = subprocess.run(args, capture_output=True, text=True, timeout=300, env=build_env)
        text = p.stdout + "\n" + p.stderr
        Path("device-schema3-build.txt").write_text(text)
        print(text, flush=True)
        assert p.returncode == 0, "schema3 test APK build failed"
        assert digest(app) == app_before, "product APK changed during test-only build"
        new_certificate = certificate(test, gate)
        Path("device-schema3-certificates.txt").write_text(json.dumps({
            "app": app_certificate, "default_test": test_certificate,
            "schema3_test": new_certificate}))
        assert new_certificate == app_certificate, "schema3 test signing certificate differs; refuse installation"
        subprocess.run(prefix + ["install", "-r", "-t", str(test)], check=True, timeout=120)
        require_registration(adb, gate, "schema3", "Schema3DeviceTest")
        device(adb, gate)
        args = ["gradle", "--no-daemon", "--console=plain", "-PpocketSchema3RestoreRunner=true", "assembleDebugAndroidTest"]
        p = subprocess.run(args, capture_output=True, text=True, timeout=300, env=build_env)
        text = p.stdout + "\n" + p.stderr
        Path("device-schema3-restore-build.txt").write_text(text)
        print(text, flush=True)
        assert p.returncode == 0 and digest(app) == app_before, "restore runner build failed or changed product"
        restore_certificate = certificate(test, gate)
        Path("device-schema3-certificates.txt").write_text(json.dumps({
            "app": app_certificate, "default_test": test_certificate,
            "schema3_test": new_certificate, "restore_test": restore_certificate}))
        assert restore_certificate == app_certificate, "restore test signing certificate differs"
        subprocess.run(prefix + ["install", "-r", "-t", str(test)], check=True, timeout=120)
        require_registration(adb, gate, "restore", "Schema3RestoreTests")
        device(adb, gate, "Schema3RestoreTests", ("restore_seed", "restore_reopen"))
    finally:
        assert digest(saved) == test_before, "saved default test APK changed"
        subprocess.run(prefix + ["install", "-r", "-t", str(saved)], check=True, timeout=120)
        shutil.copyfile(saved, test)
        require_registration(adb, gate, "restored", "V12DeviceTest")
        assert digest(test) == test_before and digest(app) == app_before, "APK restoration changed bytes"
        Path("device-schema3-apks.txt").write_text(json.dumps({
            "status": "PASS", "product_before": app_before, "product_after": digest(app),
            "default_test_before": test_before, "default_test_after": digest(test),
            "app_certificate": app_certificate, "default_test_certificate": test_certificate,
            "scope": "HOST_APK_BYTES_AND_INSTALLED_RUNNER_NOT_DEVICE_APK_PULLBACK"}))

def android():
    build_env = os.environ.copy()
    print("SCHEMA3_OBSERVER_SELFTEST " + json.dumps(selftest()), flush=True)
    import emulator_gate as gate
    import verify_exports
    original = gate.verify_database
    def database_and_schema3(adb):
        original(adb)
        isolated_runner(adb, gate, build_env)
    gate.verify_database = database_and_schema3
    native = gate.verify_native_ui
    gate.verify_native_ui = lambda adb: native_with_diagnostics(adb, gate, native)
    # Existing codec wrapper still invokes our wrapper, then all old native tests.
    try:
        verify_exports.android_main()
    finally:
        gate.verify_native_ui = native
        gate.verify_database = original

def report():
    controls = selftest()
    source, run = os.environ["GITHUB_SHA"], os.environ["GITHUB_RUN_ID"]
    devices = {}
    for api in (26, 34):
        folder = Path("collected") / ("database-api-" + str(api))
        devices[str(api)] = {}
        for stage, runner in (("default", "V12DeviceTest"), ("schema3", "Schema3DeviceTest"), ("restore", "Schema3RestoreTests"), ("restored", "V12DeviceTest")):
            path = folder / ("device-schema3-registration-" + stage + ".txt")
            text = path.read_text(errors="replace") if path.exists() else ""
            devices[str(api)]["registration_" + stage] = registration(text, runner)
        path = folder / "device-schema3-apks.txt"
        identity = json.loads(path.read_text()) if path.exists() else {}
        valid = (identity.get("status") == "PASS" and
                 re.fullmatch(r"[0-9a-f]{64}", identity.get("product_before", "")) and
                 re.fullmatch(r"[0-9a-f]{64}", identity.get("default_test_before", "")) and
                 identity.get("product_before") == identity.get("product_after") and
                 identity.get("default_test_before") == identity.get("default_test_after"))
        devices[str(api)]["apk_preservation"] = {"status": "PASS" if valid else "NOT_VERIFIED", "evidence": identity}
        path = folder / "device-schema3-certificates.txt"
        certs = json.loads(path.read_text()) if path.exists() else {}
        verified = (re.fullmatch(r"[0-9a-f]{64}", certs.get("app", "")) and
                    certs.get("app") == certs.get("default_test") == certs.get("schema3_test") == certs.get("restore_test"))
        devices[str(api)]["certificates"] = {"status": "PASS" if verified else "NOT_VERIFIED", "evidence": certs}
        for phase in LABELS:
            path = folder / ("device-schema3-" + phase + ".txt")
            text = path.read_text(errors="replace") if path.exists() else ""
            devices[str(api)][phase] = observe(text, phase, api)
    passed = all(p["status"] == "PASS" for phases in devices.values() for p in phases.values())
    doc = {"commit": source, "run_id": run, "status": "PASS" if passed else "NOT_VERIFIED",
           "scope": "OPT_IN_SCHEMA3_STORAGE_ARCHIVE_AND_GUARDED_RESTORE_NOT_DEFAULT_UI",
           "devices": devices, "observer_selftests": controls, "release_ready": False,
           "archive_compatibility": {"export_and_candidate": "PASS" if passed else "NOT_VERIFIED",
                                     "guarded_live_restore": "PASS" if passed else "NOT_VERIFIED",
                                     "default_ui_activation": False},
           "default_app_schema": 2,
           "guarded_derivative_plan": "NOT_IMPLEMENTED"}
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    endpoint = "https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + "/"
    def api(path, method="GET", body=None):
        req = urllib.request.Request(endpoint + path, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    path = "reports/schema3-" + source + "-" + run + ".json"
    body = {"message": "Record opt-in schema3 storage evidence", "branch": "evidence",
            "content": base64.b64encode(data).decode()}
    try:
        body["sha"] = api("contents/" + path + "?ref=evidence")["sha"]
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    written = api("contents/" + path, "PUT", body)
    actual = api("contents/" + path + "?ref=" + written["commit"]["sha"])
    assert base64.b64decode(actual["content"]) == data, "schema3 report readback differs"
    print("SCHEMA3_EVIDENCE " + actual["html_url"], flush=True)
    assert passed, "schema3 suite absent or failed; read published evidence"

if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        print(json.dumps(selftest(), indent=2))
    elif sys.argv[1:] == ["android"]:
        android()
    elif sys.argv[1:] == ["report"]:
        report()
    else:
        raise SystemExit("usage: verify_schema3.py selftest|android|report")
