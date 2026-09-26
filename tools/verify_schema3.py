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
        "restore_late_sql_rollback_keeps_old_state_and_published_blobs", "restore_new_exact_state_origins_and_all_assets",
        "restore_success_duplicate_refused", "restore_old_complete_replacement",
        "restore_full_complete_replacement", "restore_empty_complete_replacement",
    ],
    "restore_reopen": [
        "restore_new_independent_process_exact", "restore_old_independent_process_exact",
        "restore_full_independent_process_exact", "restore_empty_independent_process_exact",
    ],
}

# This is a completion marker emitted AFTER the actual PNG/session assertions.
# It is not a native-UI, late-publication race or distinct reopen certificate.
DERIVATIVE_MARKER = " actual_png preview_cancel_owner_session_stale_tamper_rollback_save_lineage PASS"

RACE_MARKERS = {
    "restore_seed": " positive=PASS after_early_check=PROVEN same_revision_external_write=REFUSED exact_state_and_bytes=PASS",
    "restore_reopen": "_REOPEN exact_state_and_bytes=PASS",
}

def race_fixture(phase):
    return "SCHEMA3_IMAGE_LATE_RACE" + RACE_MARKERS[phase] + "\n" if phase in RACE_MARKERS else ""

def race_markers(text, phase):
    found = list(re.finditer(r"(?:^|stream=)SCHEMA3_IMAGE_LATE_RACE([^\r\n]*)", text, re.M))
    values = [match.group(1) for match in found]
    expected = [RACE_MARKERS[phase]] if phase in RACE_MARKERS else []
    results = list(re.finditer(r"(?:^|stream=)SCHEMA3_RESULT ([^\r\n]+)", text, re.M))
    passed = values == expected and (not found or
             (len(results) == 1 and found[0].start() < results[0].start()))
    return {"status": "PASS" if passed else "NOT_VERIFIED",
            "observed": values, "expected": expected}

def derivative_markers(text, phase):
    found = list(re.finditer(r"(?:^|stream=)SCHEMA3_DERIVATIVE([^\r\n]*)", text, re.M))
    values = [match.group(1) for match in found]
    expected = [DERIVATIVE_MARKER] if phase == "restore_seed" else []
    results = list(re.finditer(r"(?:^|stream=)SCHEMA3_RESULT ([^\r\n]+)", text, re.M))
    passed = values == expected and (not found or
             (len(results) == 1 and found[0].start() < results[0].start()))
    return {"status": "PASS" if passed else "NOT_VERIFIED",
            "observed": values, "expected": expected}

def derivative_summary(devices):
    # Require BOTH expected APIs, the full successful parent phases, and the
    # exact independently extracted marker. Never infer success from job exit alone.
    passed = set(devices) == {"26", "34"}
    race_passed = set(devices) == {"26", "34"}
    for api in ("26", "34"):
        phases = devices.get(api, {})
        seed = phases.get("restore_seed", {})
        marker = seed.get("derivative_markers", {})
        passed = (passed and seed.get("status") == "PASS" and
                  marker.get("status") == "PASS" and
                  marker.get("observed") == [DERIVATIVE_MARKER] and
                  marker.get("expected") == [DERIVATIVE_MARKER] and
                  phases.get("restore_reopen", {}).get("status") == "PASS")
        for phase, expected in RACE_MARKERS.items():
            evidence = phases.get(phase, {})
            race = evidence.get("image_race_markers", {})
            race_passed = (race_passed and evidence.get("status") == "PASS" and
                           race.get("status") == "PASS" and
                           race.get("observed") == [expected] and race.get("expected") == [expected])
    passed = passed and race_passed
    return {"status": "PASS" if passed else "NOT_VERIFIED",
            "scope": "LOCAL_PNG_PREVIEW_AND_GUARDED_SAVE_BACKEND",
            "native_ui": "NOT_IMPLEMENTED",
            "late_publication_race": "PASS" if race_passed else "NOT_VERIFIED",
            "late_race_scope": "REAL_PUBLICATION_BARRIER_CONTROL_AND_SAME_REVISION_EXTERNAL_WRITE",
            "late_race_reopen": "PASS" if race_passed else "NOT_VERIFIED",
            "reopen_evidence": "PARENT_SUITE_PASS_NO_DISTINCT_DERIVATIVE_MARKER",
            "real_photos": "NOT_TESTED"}

def observe(text, phase, api):
    labels = re.findall(r"(?:^|stream=)SCHEMA3_PASS ([^\r\n]+)", text, re.M)
    result = re.findall(r"(?:^|stream=)SCHEMA3_RESULT ([^\r\n]+)", text, re.M)
    finished = re.findall(r"^INSTRUMENTATION_CODE: (-?\d+)\s*$", text, re.M)
    derivative = derivative_markers(text, phase)
    race = race_markers(text, phase)
    passed = (labels == LABELS[phase] and
              result == [f"{phase} {api} {len(LABELS[phase])} PASS"] and
              finished == ["-1"] and "SCHEMA3_FAILED" not in text and
              "INSTRUMENTATION_FAILED" not in text and derivative["status"] == "PASS" and
              race["status"] == "PASS")
    return {"status": "PASS" if passed else "NOT_VERIFIED", "labels": labels,
            "expected_labels": LABELS[phase], "checks": len(labels),
            "log_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "failure_tail": None if passed else text[-9000:],
            "derivative_markers": derivative, "image_race_markers": race}

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
        records += race_fixture(phase)
        if phase == "restore_seed":
            records += "SCHEMA3_DERIVATIVE" + DERIVATIVE_MARKER + "\n"
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
    controls["default_schema3_ui"] = native_schema3_selftest()
    controls["derivative_backend"] = derivative_selftest()
    controls["image_late_race"] = race_selftest()
    controls["markdown_native_ui"] = share_ui_selftest()
    controls["share_picker_navigation"] = share_navigation_selftest()
    return controls

def derivative_selftest():
    import copy
    phase = "restore_seed"
    records = "".join("SCHEMA3_PASS " + x + "\n" for x in LABELS[phase])
    records += race_fixture(phase)
    marker = "SCHEMA3_DERIVATIVE" + DERIVATIVE_MARKER + "\n"
    result = f"SCHEMA3_RESULT {phase} 26 {len(LABELS[phase])} PASS\n"
    finish = "INSTRUMENTATION_CODE: -1\n"
    good = records + marker + result + finish
    for text in (good, good.replace("\n", "\r\n"), "stream=" + good):
        assert observe(text, phase, 26)["status"] == "PASS"
    bad = {
        "missing": good.replace(marker, "", 1),
        "duplicate": good.replace(marker, marker + marker, 1),
        "failure": good.replace(marker, marker.replace(" PASS", " FAIL"), 1),
        "partial": good.replace("rollback_save_lineage", "rollback_save"),
        "prefix_only": good.replace(marker, "SCHEMA3_DERIVATIVE\n", 1),
        "unknown_suffix": good.replace(marker, marker.rstrip("\n") + " extra\n", 1),
        "quoted": good.replace(marker, "quoted: " + marker, 1),
        "after_result": records + result + marker + finish,
        "marker_only": marker + finish,
    }
    for name, text in bad.items():
        assert text != good, "derivative control did not mutate: " + name
        assert observe(text, phase, 26)["status"] != "PASS", "derivative observer missed: " + name
    # A stray success in another phase is not evidence for this phase.
    for other in ("seed", "reopen", "restore_reopen"):
        text = "".join("SCHEMA3_PASS " + x + "\n" for x in LABELS[other])
        text += race_fixture(other)
        text += marker + f"SCHEMA3_RESULT {other} 26 {len(LABELS[other])} PASS\n" + finish
        assert observe(text, other, 26)["status"] != "PASS", "misplaced derivative marker accepted"
    devices = {}
    for api in (26, 34):
        reopened = "".join("SCHEMA3_PASS " + x + "\n" for x in LABELS["restore_reopen"])
        reopened += race_fixture("restore_reopen")
        reopened += f'SCHEMA3_RESULT restore_reopen {api} {len(LABELS["restore_reopen"])} PASS\n' + finish
        devices[str(api)] = {
            "restore_seed": observe(good.replace("restore_seed 26 ", f"restore_seed {api} "), phase, api),
            "restore_reopen": observe(reopened, "restore_reopen", api)}
    summary = derivative_summary(devices)
    assert summary["status"] == "PASS"
    assert summary["native_ui"] == "NOT_IMPLEMENTED" and summary["late_publication_race"] == "PASS"
    assert summary["reopen_evidence"] == "PARENT_SUITE_PASS_NO_DISTINCT_DERIVATIVE_MARKER"
    invalid = [{}, {"26": devices["26"]}, dict(devices, unexpected={})]
    for api in ("26", "34"):
        for key in ("restore_seed", "restore_reopen"):
            mutant = copy.deepcopy(devices);mutant[api][key]["status"] = "NOT_VERIFIED";invalid.append(mutant)
        for key, value in (("status", "NOT_VERIFIED"), ("observed", []), ("expected", [])):
            mutant = copy.deepcopy(devices);mutant[api]["restore_seed"]["derivative_markers"][key] = value;invalid.append(mutant)
    for value in invalid:
        assert derivative_summary(value)["status"] != "PASS", "aggregate derivative observer missed"
    return {"log_positive": 3, "log_negative": len(bad) + 3,
            "aggregate_positive": 1, "aggregate_negative": len(invalid),
            "scope": "PYTHON_LOG_AND_REPORT_CONTROLS_NOT_COMPILED_PRODUCT_MUTANTS"}

def race_selftest():
    import copy
    good_logs = {}
    positive = negative = 0
    for phase in RACE_MARKERS:
        records = "".join("SCHEMA3_PASS " + x + "\n" for x in LABELS[phase])
        derivative = "SCHEMA3_DERIVATIVE" + DERIVATIVE_MARKER + "\n" if phase == "restore_seed" else ""
        marker = race_fixture(phase)
        result = f"SCHEMA3_RESULT {phase} 26 {len(LABELS[phase])} PASS\n"
        finish = "INSTRUMENTATION_CODE: -1\n"
        good = records + marker + derivative + result + finish
        good_logs[phase] = good
        for text in (good, good.replace("\n", "\r\n"), good.replace(marker, "stream=" + marker)):
            assert observe(text, phase, 26)["status"] == "PASS"
            positive += 1
        bad = {
            "missing": good.replace(marker, ""),
            "duplicate": good.replace(marker, marker + marker),
            "failure": good.replace(marker, marker.replace("PASS", "FAIL")),
            "truncated": good.replace(marker, "SCHEMA3_IMAGE_LATE_RACE\n"),
            "extra": good.replace(marker, marker.rstrip("\n") + " extra\n"),
            "quoted": good.replace(marker, "quoted: " + marker),
            "wrong_phase": good.replace(marker, race_fixture("restore_reopen" if phase == "restore_seed" else "restore_seed")),
            "after_result": records + derivative + result + marker + finish,
            "marker_only": marker + finish,
            "both_phases": good.replace(marker, race_fixture("restore_seed") + race_fixture("restore_reopen")),
        }
        if phase == "restore_seed":
            for token in ("positive=PASS", "after_early_check=PROVEN", "same_revision_external_write=REFUSED"):
                bad[token] = good.replace(token, token.split("=")[0] + "=UNKNOWN")
        for name, text in bad.items():
            assert text != good, "race control not mutated: " + name
            assert observe(text, phase, 26)["status"] != "PASS", "race observer missed: " + name
            negative += 1
        for other in ("seed", "reopen"):
            text = "".join("SCHEMA3_PASS " + x + "\n" for x in LABELS[other])
            text += marker + f"SCHEMA3_RESULT {other} 26 {len(LABELS[other])} PASS\n" + finish
            assert observe(text, other, 26)["status"] != "PASS"
            negative += 1
    devices = {str(api): {phase: observe(text.replace(f"{phase} 26 ", f"{phase} {api} "), phase, api)
                         for phase, text in good_logs.items()} for api in (26, 34)}
    summary = derivative_summary(devices)
    assert summary["status"] == summary["late_publication_race"] == summary["late_race_reopen"] == "PASS"
    assert summary["native_ui"] == "NOT_IMPLEMENTED" and summary["real_photos"] == "NOT_TESTED"
    invalid = [{}, {"26": devices["26"]}, {"34": devices["34"]}, dict(devices, extra={})]
    for api in ("26", "34"):
        for phase in RACE_MARKERS:
            absent = copy.deepcopy(devices);del absent[api][phase]["image_race_markers"];invalid.append(absent)
            for key, value in (("status", "NOT_VERIFIED"), ("observed", []), ("expected", [])):
                mutant = copy.deepcopy(devices);mutant[api][phase]["image_race_markers"][key] = value;invalid.append(mutant)
    for value in invalid:
        result = derivative_summary(value)
        assert result["status"] == result["late_publication_race"] == result["late_race_reopen"] == "NOT_VERIFIED", "race aggregate missed"
    return {"log_positive": positive, "log_negative": negative,
            "aggregate_positive": 1, "aggregate_negative": len(invalid),
            "scope": "PYTHON_LOG_AND_REPORT_CONTROLS_NOT_COMPILED_PRODUCT_MUTANTS"}

NATIVE_SCHEMA3_LABELS = [
    "default native UI uses schema3 with exact nine-column block layout",
    "native schema3 survives SAF restore and all ordinary edits without invented image origins",
]

# Touch crop/redaction UI over the guarded derivative backend. Deleting any of
# these device checks must turn the whole report NOT_VERIFIED, never silent green.
NATIVE_DERIVATIVE_LABELS = [
    "derivative dialog shows actual decoded source dimensions with empty selection",
    "derivative preview without selection rejected visibly",
    "derivative cancel leaves every table and original bytes unchanged",
    "corner drag maps to full source extent within touch rounding",
    "derivative oversize selection rejected with visible pixel budget",
    "derivative reset clears selection reports",
    "touch crop maps onto intended source rectangle within rounding",
    "redact mode adds exactly one reported mask",
    "touch mask maps onto intended source rectangle within rounding",
    "derivative preview renders exact reported output dimensions",
    "derived block preserves note owner position kind empty caption public flag and records exact original",
    "derived PNG registered with exact mime and byte length",
    "derivative save preserves all unrelated tables",
    "original imported PNG bytes unchanged after derivative save",
    "sibling blocks across notes remain exact after derivative save",
    "independent decoder proves exact cropped pixels and opaque mask for reported rects",
    "derived image renders with working entry after process restart",
    "derivative state and both images survive stopped-process restart exactly",
    "re-derived preview renders for abandonment check",
    "abandoned second preview writes nothing and keeps published derivative",
]

def native_schema3(result, api):
    checks = result.get("checks", [])
    required = NATIVE_SCHEMA3_LABELS + NATIVE_DERIVATIVE_LABELS
    passed = (result.get("status") == "PASS" and result.get("api") == api and
              result.get("default_app_schema") == 3 and
              result.get("default_schema3_ui") == "NATIVE_SCHEMA3_UI_PASS" and
              isinstance(checks, list) and result.get("count") == len(checks) and
              all(checks.count(label) == 1 for label in required) and
              result.get("saf_restore") == "NATIVE_SAF_RESTORE_PREVIEW_CONFIRM_PASS" and
              result.get("image_metadata") == "CAPTION_PRIVATE_CANCEL_EDIT_CLEAR_RESTART_PASS" and
              result.get("derivative_ui") == "NATIVE_CROP_MASK_UI_SAVE_CANCEL_RESTART_PASS")
    return {"status": "PASS" if passed else "NOT_VERIFIED", "evidence": result}

def native_schema3_selftest():
    required = NATIVE_SCHEMA3_LABELS + NATIVE_DERIVATIVE_LABELS
    good = {"status": "PASS", "api": 26, "default_app_schema": 3,
            "default_schema3_ui": "NATIVE_SCHEMA3_UI_PASS",
            "checks": list(required), "count": len(required),
            "saf_restore": "NATIVE_SAF_RESTORE_PREVIEW_CONFIRM_PASS",
            "image_metadata": "CAPTION_PRIVATE_CANCEL_EDIT_CLEAR_RESTART_PASS",
            "derivative_ui": "NATIVE_CROP_MASK_UI_SAVE_CANCEL_RESTART_PASS"}
    assert native_schema3(good, 26)["status"] == "PASS"
    bad = [{}, dict(good, status="FAIL"), dict(good, api=34),
           dict(good, default_app_schema=2), dict(good, default_schema3_ui=""),
           dict(good, checks=good["checks"][:1], count=1),
           dict(good, checks=good["checks"]+good["checks"], count=2*len(required)),
           dict(good, count=len(required)+1), dict(good, saf_restore="NOT_VERIFIED"),
           dict(good, image_metadata="NOT_VERIFIED"),
           dict(good, checks=[x for x in required if x != NATIVE_DERIVATIVE_LABELS[0]], count=len(required)-1),
           dict(good, derivative_ui="NOT_IMPLEMENTED")]
    for value in bad:
        assert native_schema3(value, 26)["status"] != "PASS", "native schema3 observer missed"
    return {"positive": 1, "negative": len(bad), "scope": "REPORT_CONTROLS_NOT_DEVICE_EXECUTION"}

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

SHARE_UI_LABELS = [
    "share private fixture changes only chosen image metadata",
    "share duplicate-title empty note cannot export namesake content",
    "share picker excludes private image and starts with no selection",
    "share empty selection stays in selection dialog",
    "share actual preview contains selected text and image",
    "share unchecked consent cannot open system save",
    "share preview cancellation preserves complete database and media",
    "share system picker cancellation publishes no file and preserves state",
    "share text-only selection creates exact Markdown without image entries",
    "share text-only success preserves complete database and media",
    "share selected export contains exact Markdown and only one current image",
    "share independent decoder verifies exported crop and opaque mask pixels",
    "share successful image export preserves complete database and media",
    "share external writer changes privacy without revision increment",
    "share stale preview refuses publication through real system picker",
    "share stale refusal causes no extra database or media mutation",
]
SHARE_UI_SCOPE = "NATIVE_SINGLE_NOTE_MARKDOWN_SAF_SYNTHETIC_NOT_PDF_OR_RECEIVER"

def share_ui_observe(value, api, source, run):
    if not isinstance(value, dict):
        value = {}
    passed = (value.get("status") == "PASS" and value.get("api") == api and
              value.get("commit") == source and value.get("run_id") == run and
              value.get("scope") == SHARE_UI_SCOPE and value.get("checks") == SHARE_UI_LABELS and
              type(value.get("count")) is int and value.get("count") == len(SHARE_UI_LABELS) and
              value.get("release_ready") is False)
    return {"status": "PASS" if passed else "NOT_VERIFIED", "evidence": value}

def share_ui_selftest():
    import copy
    good = {"status": "PASS", "api": 26, "commit": "source", "run_id": "run",
            "scope": SHARE_UI_SCOPE, "checks": list(SHARE_UI_LABELS),
            "count": len(SHARE_UI_LABELS), "release_ready": False}
    assert share_ui_observe(good, 26, "source", "run")["status"] == "PASS"
    bad = [None, [], {}, dict(good, api=34), dict(good, commit="old"),
           dict(good, run_id="old"), dict(good, status="FAIL"), dict(good, scope="backend"),
           dict(good, count=True), dict(good, release_ready=True)]
    for i in range(len(SHARE_UI_LABELS)):
        missing = copy.deepcopy(good);del missing["checks"][i];missing["count"] -= 1
        swapped = copy.deepcopy(good);swapped["checks"][i] = "unrelated"
        bad.extend((missing, swapped))
    bad.extend((dict(good, checks=good["checks"] + good["checks"], count=2*len(SHARE_UI_LABELS)),
                dict(good, checks=list(reversed(good["checks"])))))
    for value in bad:
        assert share_ui_observe(value, 26, "source", "run")["status"] != "PASS", "share UI observer missed"
    return {"positive": 1, "negative": len(bad), "scope": "REPORT_CONTROLS_NOT_ANDROID_EXECUTION"}

def cancel_share_picker(read, back, package, trace):
    # Back may first dismiss the IME or a provider subview, not the Activity.
    # Navigation is bounded and conditional, never a retry of the export test.
    providers = {"com.android.documentsui", "com.google.android.documentsui"}
    for sent in range(4):
        current = read()
        packages = {n.get("package") for n in current if n.get("package")}
        picker = bool(packages & providers)
        cancelled = any(n.get("package") == package and n.get("content-desc") == "v12-status" and
                        n.get("text") == "已取消导出，本机笔记未改变" for n in current)
        trace.append({"backs": sent, "packages": sorted(packages), "cancelled": cancelled})
        if cancelled and not picker:
            assert sent > 0, "picker cancellation was not exercised"
            return sent
        assert picker and package not in packages, "unexpected window during picker cancellation: " + repr(trace)
        assert sent < 3, "picker did not cancel within bounded navigation: " + repr(trace)
        back()
    raise AssertionError("unreachable cancellation")

def share_navigation_selftest():
    package = "test.package"
    picker = [{"package": "com.android.documentsui", "text": "SAVE"}]
    cancelled = [{"package": package, "content-desc": "v12-status",
                  "text": "已取消导出，本机笔记未改变"}]
    unexpected = [{"package": package, "content-desc": "v12-status", "text": "wrong"}]
    cases = [
        ([picker, cancelled], 1),
        ([picker, picker, cancelled], 2),
        ([picker, picker, picker, cancelled], 3),
        ([cancelled], None), ([[]], None),
        ([[{"package": "other.documentsui.fake"}]], None),
        ([picker, unexpected], None), ([picker], None),
    ]
    for frames, expected in cases:
        sent = []
        def read():
            return frames[min(len(sent), len(frames)-1)]
        def back():
            sent.append("BACK")
        trace = []
        try:
            actual = cancel_share_picker(read, back, package, trace)
        except AssertionError:
            assert expected is None, "valid picker navigation rejected"
        else:
            assert expected is not None and actual == expected == len(sent), "false cancellation"
        assert len(sent) <= 3 and len(trace) == len(sent)+1
        if frames == [picker, unexpected]:
            assert len(sent) == 1, "sent Back after returning to product"
    return {"checks": len(cases), "scope": "HOST_NAVIGATION_MODEL_NOT_ANDROID_IME"}

def native_share_ui(adb, gate):
    """Continue the real v1.2 UI fixture, not the historical v1.1 ui_test.py.
    No product test hooks. SQLite/media are independently read on the host.
    One explicit CI-only external SQLite writer tests same-revision privacy staleness.
    """
    import io
    import sqlite3
    import time
    import zipfile
    import xml.etree.ElementTree as ET
    out = Path("native-ui")
    report_path = out / "native-result.json"
    parent = json.loads(report_path.read_text())
    assert native_schema3(parent, gate.API)["status"] == "PASS", "native prerequisites not accepted"
    checks, shots, serial = [], [], 0
    prefix = [str(adb), "-s", gate.SERIAL]
    result = {"status": "FAIL", "api": gate.API, "commit": os.environ["GITHUB_SHA"],
              "run_id": os.environ["GITHUB_RUN_ID"], "scope": SHARE_UI_SCOPE,
              "checks": checks, "release_ready": False,
              "recreation": "NOT_TESTED", "provider_failures": "NOT_TESTED",
              "private_text": "NOT_TESTED", "actual_receiver": "NOT_TESTED"}
    def command(*args, binary=False):
        return subprocess.check_output(prefix + list(args), text=not binary, stderr=subprocess.PIPE, timeout=40)
    def shell(*args): return command("shell", *args)
    def nodes():
        shell("uiautomator", "dump", "/sdcard/share-window.xml")
        return list(ET.fromstring(shell("cat", "/sdcard/share-window.xml")).iter("node"))
    def find(**attrs):
        deadline = time.monotonic() + 20
        current = []
        while time.monotonic() < deadline:
            current = nodes()
            for n in current:
                if all(n.get(k) == v for k, v in attrs.items()): return n
            time.sleep(.25)
        raise AssertionError("share UI missing " + repr(attrs) + "; actual=" +
                             repr([n.attrib for n in current if n.get("text") or n.get("content-desc")]))
    def click(n):
        assert n.get("enabled") == "true", "disabled share target"
        x1,y1,x2,y2 = map(int,re.findall(r"\d+",n.get("bounds")))
        assert x2>x1 and y2>y1, "empty share target bounds"
        shell("input","tap",str((x1+x2)//2),str((y1+y2)//2))
    def tap(text): click(find(text=text))
    def touch(desc): click(find(**{"content-desc":desc}))
    def ready(): find(**{"content-desc":"v12-status","text":"已保存到本机"})
    def stop(): shell("am","force-stop",gate.PKG)
    def start():
        shell("am","start","-W","-n",gate.PKG+"/com.supercubegame.pockettodo.MainActivity")
        ready()
    def snapshot():
        nonlocal serial
        serial += 1
        path = out / ("share-state-" + str(serial) + ".db")
        path.write_bytes(command("exec-out","run-as",gate.PKG,"cat","databases/pocket-v12.db",binary=True))
        if "pocket-v12.db-wal" in shell("run-as",gate.PKG,"ls","databases").splitlines():
            Path(str(path)+"-wal").write_bytes(command("exec-out","run-as",gate.PKG,"cat","databases/pocket-v12.db-wal",binary=True))
        with sqlite3.connect(path) as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            assert "blocks" in tables and "revision" in tables
            state = {t:db.execute('SELECT * FROM "'+t+'" ORDER BY rowid').fetchall() for t in tables}
        media = {}
        for name in shell("run-as",gate.PKG,"ls","files/media").splitlines():
            assert re.fullmatch(r"[0-9a-f]{64}",name), "unexpected media filename"
            data = command("exec-out","run-as",gate.PKG,"cat","files/media/"+name,binary=True)
            media[name] = hashlib.sha256(data).hexdigest()
            assert media[name] == name, "stored media digest mismatch"
        return state, media
    def ok(condition, label):
        assert condition, label
        assert label == SHARE_UI_LABELS[len(checks)], "share check order drift"
        checks.append(label);print("NATIVE_SHARE_PASS "+label,flush=True)
    def shot(name):
        data = command("exec-out","screencap","-p",binary=True)
        assert data.startswith(b"\x89PNG\r\n\x1a\n")
        (out/name).write_bytes(data)
        shots.append({"file":name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    def file_paths():
        return shell("find","/sdcard/Download","-type","f","-name","PocketTodo-notes.zip").splitlines()
    def export_bytes():
        paths = file_paths()
        assert paths == ["/sdcard/Download/PocketTodo-notes.zip"], "missing or ambiguous SAF output: "+repr(paths)
        data = command("exec-out","cat",paths[0],binary=True)
        assert data, "empty SAF output"
        return data
    def choose_note(note_id):
        tap("导出笔记");find(text="导出哪篇笔记？")
        tap(note_labels[note_id])
    def choose_blocks(image):
        choose_note(note)
        find(text="勾选内容（私有项已排除）")
        tap("1. 文字：Second edited")
        if image: tap("2. 图片：")
        tap("生成预览");find(text="Markdown图片包预览")
    def consent():
        for attempt in range(8):
            current = nodes()
            for n in current:
                if n.get("text") == "我已核对内容与图片，可保存此包":
                    bounds=list(map(int,re.findall(r"\d+",n.get("bounds"))))
                    if bounds[2]>bounds[0] and bounds[3]>bounds[1]:
                        assert n.get("checked") == "false", "consent not initially empty"
                        click(n);return
            shell("input","swipe","160","440","160","190","350")
        raise AssertionError("share consent not reachable")
    def open_save():
        consent();tap("选择保存位置")
        assert "documentsui" in find(text="PocketTodo-notes.zip").get("package","")
        assert "documentsui" in find(text="SAVE").get("package","")
    def saved_message():
        find(**{"content-desc":"v12-status","text":"Markdown图片包已保存，逐字节回读一致"})
    try:
        assert os.environ.get("GITHUB_ACTIONS") == "true" and shell("getprop","ro.kernel.qemu").strip() == "1"
        stop();initial, original_media = snapshot()
        derived = [r for r in initial["blocks"] if r[8] is not None]
        assert len(derived) == 1, "expected actual native derivative fixture"
        row = derived[0];note, block = row[0], row[1]
        siblings = [r for r in initial["blocks"] if r[0] == note and r[3] == "IMAGE" and r[1] != block]
        assert len(siblings) == 1 and siblings[0][7] == 0 and row[7] == 0
        private = siblings[0]
        note_row = next(r for r in initial["notes"] if r[0] == note)
        duplicates = [r for r in initial["notes"] if r[2] == note_row[2] and r[0] != note]
        assert len(duplicates) == 1 and not any(r[0] == duplicates[0][0] for r in initial["blocks"])
        # Resolve actual activity title column independently from SQLite schema.
        with sqlite3.connect(out/("share-state-"+str(serial)+".db")) as db:
            titles = dict(db.execute("SELECT id,title FROM activities"))
        note_labels = {r[0]:str(i+1)+". "+titles[r[1]]+" / "+r[2] for i,r in enumerate(initial["notes"])}
        start();tap("活动");ready();touch("activity-"+str(note_row[1]));ready();tap("笔记");ready()
        tap("切换笔记");tap("2. Second note");ready()
        touch("note-image-edit-"+private[1]);touch("image-caption")
        shell("input","text","PRIVATE_SHARE_SENTINEL");touch("image-private");tap("保存");ready();stop()
        baseline, media = snapshot()
        expected = list(private);expected[6]="PRIVATE_SHARE_SENTINEL";expected[7]=1
        ok(baseline["blocks"] == [tuple(expected) if r==private else r for r in initial["blocks"]] and
           all(baseline[t]==initial[t] for t in initial if t not in ("blocks","revision")) and media==original_media,
           "share private fixture changes only chosen image metadata")
        assert not file_paths(), "preexisting share output would mask failed publication"
        start();choose_note(duplicates[0][0])
        find(**{"content-desc":"v12-status","text":"这篇笔记没有非私有内容可导出"})
        ok(not any(n.get("text")=="勾选内容（私有项已排除）" for n in nodes()),
           "share duplicate-title empty note cannot export namesake content")
        choose_note(note);find(text="勾选内容（私有项已排除）")
        choices = [n for n in nodes() if n.get("class")=="android.widget.CheckedTextView"]
        ok([n.get("text") for n in choices]==["1. 文字：Second edited","2. 图片："] and
           all(n.get("checked")=="false" for n in choices),
           "share picker excludes private image and starts with no selection")
        tap("生成预览")
        ok(find(text="勾选内容（私有项已排除）") is not None and not file_paths(),
           "share empty selection stays in selection dialog")
        tap("1. 文字：Second edited");tap("2. 图片：");tap("生成预览");find(text="Markdown图片包预览")
        visible = nodes()
        ok(any("Second edited" in n.get("text","") for n in visible) and
           any(n.get("class")=="android.widget.ImageView" for n in visible),
           "share actual preview contains selected text and image")
        shot("20-share-preview.png");tap("选择保存位置")
        ok(find(text="Markdown图片包预览") is not None and not file_paths() and
           not any("documentsui" in n.get("package","") for n in nodes()),
           "share unchecked consent cannot open system save")
        tap("取消");stop()
        ok(snapshot()==(baseline,media),"share preview cancellation preserves complete database and media")
        start();choose_blocks(True);open_save()
        result["picker_cancel_navigation"] = []
        cancel_share_picker(nodes, lambda: shell("input","keyevent","KEYCODE_BACK"),
                            gate.PKG, result["picker_cancel_navigation"])
        find(**{"content-desc":"v12-status","text":"已取消导出，本机笔记未改变"});stop()
        ok(not file_paths() and snapshot()==(baseline,media),
           "share system picker cancellation publishes no file and preserves state")
        start();choose_blocks(False);open_save();tap("SAVE");saved_message()
        text_zip = export_bytes()
        with zipfile.ZipFile(io.BytesIO(text_zip)) as archive:
            ok(archive.namelist()==["notes.md"] and archive.read("notes.md")==b"# Pocket Todo\n\nSecond edited\n\n",
               "share text-only selection creates exact Markdown without image entries")
        stop();ok(snapshot()==(baseline,media),"share text-only success preserves complete database and media")
        shell("mv","/sdcard/Download/PocketTodo-notes.zip","/sdcard/Download/share-text-verified.zip")
        start();choose_blocks(True);open_save();tap("SAVE");saved_message()
        image_zip = export_bytes()
        with zipfile.ZipFile(io.BytesIO(image_zip)) as archive:
            ok(archive.namelist()==["notes.md","assets/image-1.png"] and
               archive.read("notes.md")==b"# Pocket Todo\n\nSecond edited\n\n![Image](assets/image-1.png)\n\n",
               "share selected export contains exact Markdown and only one current image")
            (out/"share-exported.png").write_bytes(archive.read("assets/image-1.png"))
        geometry = parent["derivative_geometry"]
        crops = [g["observed_crop"] for g in geometry if g.get("source")==[1280,640] and "observed_crop" in g]
        masks = [g["observed_mask"] for g in geometry if g.get("source")==[1280,640] and "observed_mask" in g]
        assert len(crops)==len(masks)==1
        pixels = subprocess.check_output(["java","-Djava.awt.headless=true","-cp","build/ci-note-image","VerifyDerivative",
            str(out/"derivative-source.png"),str(out/"share-exported.png"),*map(str,crops[0]),*map(str,masks[0])],
            text=True,timeout=60).strip()
        ok(pixels=="DERIVATIVE_PIXELS_PASS "+str(crops[0][2]-crops[0][0])+"x"+str(crops[0][3]-crops[0][1]),
           "share independent decoder verifies exported crop and opaque mask pixels")
        shot("21-share-saved.png");stop()
        ok(snapshot()==(baseline,media),"share successful image export preserves complete database and media")
        result["zip_sha256"] = hashlib.sha256(image_zip).hexdigest()
        result["zip_bytes"] = len(image_zip)
        shell("mv","/sdcard/Download/PocketTodo-notes.zip","/sdcard/Download/share-image-verified.zip")
        helper = Path("build/ci-share-writer");helper.mkdir(parents=True,exist_ok=True)
        java = helper/"ShareExternalWriter.java"
        java.write_text('''import android.database.sqlite.SQLiteDatabase;
import android.content.ContentValues;
public class ShareExternalWriter {
 public static void main(String[] a) {
  try {
  System.out.println("EXTERNAL_WRITER_STARTED");
  if(!android.os.Build.HARDWARE.equals("ranchu")&&!android.os.Build.HARDWARE.equals("goldfish"))throw new SecurityException("CI emulator only");
  try(SQLiteDatabase db=SQLiteDatabase.openDatabase(a[0],null,SQLiteDatabase.OPEN_READWRITE)){
   ContentValues v=new ContentValues();v.put("private",Integer.parseInt(a[3]));
   if(db.update("blocks",v,"note_id=? AND id=? AND private=?",new String[]{a[1],a[2],a[4]})!=1)throw new AssertionError("exact external target");
  }
  System.out.println("EXTERNAL_PRIVACY_WRITE_ONE_ROW");
  } catch(Throwable failure) {
   System.err.println("EXTERNAL_WRITER_FATAL "+failure);
   failure.printStackTrace(System.err);System.exit(1);
  }
 }
}''',encoding="utf-8")
        android_jar = gate.SDK/"platforms/android-35/android.jar"
        subprocess.run(["javac","-encoding","UTF-8","-cp",str(android_jar),"-d",str(helper),str(java)],check=True,timeout=40)
        jar = helper/"writer.jar"
        subprocess.run([str(gate.SDK/"build-tools/35.0.0/d8"),"--lib",str(android_jar),"--min-api","26",
                        "--output",str(jar),str(helper/"ShareExternalWriter.class")],check=True,timeout=40)
        # Load the helper from the same app-owned context that executes it.
        # Exact readback precedes execution; do not relax SELinux or use root.
        import shlex
        remote = "/data/user/0/"+gate.PKG+"/cache/share-writer.jar"
        stage = "run-as "+shlex.quote(gate.PKG)+" sh -c "+shlex.quote("umask 077; cat > cache/share-writer.jar")
        subprocess.run(prefix+["shell",stage],input=jar.read_bytes(),capture_output=True,check=True,timeout=40)
        shell("run-as",gate.PKG,"chmod","444",remote)
        assert command("exec-out","run-as",gate.PKG,"cat",remote,binary=True)==jar.read_bytes(), "external helper bytes differ"
        result["external_helper"] = {"sha256":hashlib.sha256(jar.read_bytes()).hexdigest(),
                                     "readback":"EXACT_BYTES","location":"APP_PRIVATE_CACHE"}
        def external(value, previous):
            try:
                output=shell("run-as",gate.PKG,"env","CLASSPATH="+remote,"app_process","/system/bin",
                             "ShareExternalWriter","/data/user/0/"+gate.PKG+"/databases/pocket-v12.db",
                             note,block,str(value),str(previous))
                assert output.splitlines()==["EXTERNAL_WRITER_STARTED","EXTERNAL_PRIVACY_WRITE_ONE_ROW"],output
            except Exception:
                try:
                    crash = shell("logcat","-b","crash","-d","-t","100")
                    result["external_writer_crash_log"] = output_evidence(crash)
                    print("EXTERNAL_WRITER_CRASH_LOG "+json.dumps(result["external_writer_crash_log"]),flush=True)
                except Exception as diagnostic:
                    result["external_writer_crash_log"] = {"error":exception_evidence(diagnostic)}
                raise
        start();choose_blocks(True);open_save()
        external(1,0)
        changed, changed_media = snapshot()
        stale_row = list(row);stale_row[7]=1
        ok(changed["blocks"]==[tuple(stale_row) if r==row else r for r in baseline["blocks"]] and
           all(changed[t]==baseline[t] for t in baseline if t!="blocks") and changed_media==media,
           "share external writer changes privacy without revision increment")
        tap("SAVE")
        find(**{"content-desc":"v12-status","text":"导出未完成：预览过期或保存失败；本机笔记未改。目标可能留有空文件或部分文件，请检查"})
        paths=file_paths()
        ok(not paths or (len(paths)==1 and command("exec-out","cat",paths[0],binary=True)==b""),
           "share stale preview refuses publication through real system picker")
        stop()
        ok(snapshot()==(changed,media),"share stale refusal causes no extra database or media mutation")
        external(0,1)
        assert snapshot()==(baseline,media), "external test cleanup changed other state"
        result["status"]="PASS"
    except Exception as exc:
        result["error"]=exception_evidence(exc)
        parent["status"]="FAIL"
        try: shot("share-failure.png")
        except Exception as capture: result["screenshot_error"]=repr(capture)
        raise
    finally:
        result["count"]=len(checks)
        parent["markdown_ui"]=result
        if result["status"]=="PASS": parent["sharing"]=SHARE_UI_SCOPE
        parent["screenshots"].extend(shots)
        report_path.write_text(json.dumps(parent,ensure_ascii=False,indent=2))
        print("NATIVE_SHARE_RESULT "+json.dumps(result,ensure_ascii=False),flush=True)

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
    def native_and_share(adb):
        native_with_diagnostics(adb, gate, native)
        native_with_diagnostics(adb, gate, lambda device: native_share_ui(device, gate))
    gate.verify_native_ui = native_and_share
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
        path = folder / "native-ui/native-result.json"
        native = json.loads(path.read_text()) if path.exists() else {}
        devices[str(api)]["default_ui"] = native_schema3(native, api)
        devices[str(api)]["markdown_ui"] = share_ui_observe(native.get("markdown_ui"), api, source, run)
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
    derivative = derivative_summary(devices)
    passed = passed and derivative["status"] == "PASS"
    doc = {"commit": source, "run_id": run, "status": "PASS" if passed else "NOT_VERIFIED",
           "scope": "SCHEMA3_STORAGE_ARCHIVE_GUARDED_RESTORE_AND_DEFAULT_NATIVE_UI",
           "devices": devices, "observer_selftests": controls, "release_ready": False,
           "archive_compatibility": {"export_and_candidate": "PASS" if passed else "NOT_VERIFIED",
                                     "guarded_live_restore": "PASS" if passed else "NOT_VERIFIED",
                                     "default_ui_activation": "PASS" if all(d["default_ui"]["status"] == "PASS" for d in devices.values()) else "NOT_VERIFIED"},
           "configured_default_app_schema": 3,
           "guarded_derivative_plan": derivative}
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
