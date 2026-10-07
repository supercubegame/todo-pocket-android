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
import ast
import copy
import inspect
import io
import math
import tempfile
import types
import xml.etree.ElementTree as ET
from unittest.mock import patch
from contextlib import redirect_stdout

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
    from verify_note_management import selftest as note_management_selftest
    controls = {}
    controls["note_management"] = note_management_selftest()
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
    controls["signal_target_identity"] = signal_identity_selftest()
    controls["paged_exports"] = paged_observer_selftest()
    controls["full_native_artifacts"] = evidence_selftest()
    controls["full_native_artifacts"]["compiled_mutants"] = evidence_mutations()
    controls["full_native_report_entry"] = report_entry_selftest()
    controls["full_native_report_entry"]["compiled_mutants"] = report_entry_mutations()
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
    "share background process death is proven while system picker remains",
    "share recreated owner refuses old preview without nonempty publication",
    "share returned activity runs in a different proven process",
    "share process-loss refusal preserves complete database and media",
    "share fresh explicit selection after process loss exports exact reviewed ZIP",
    "share fresh post-loss success preserves complete database and media",
]
SHARE_UI_SCOPE = "NATIVE_SINGLE_NOTE_MARKDOWN_SAF_SYNTHETIC_NOT_PDF_OR_RECEIVER"
SHARE_RECREATION = "PROCESS_DEATH_DURING_SAF_REFUSED_AND_FRESH_EXPORT_PASS"

def share_ui_observe(value, api, source, run):
    if not isinstance(value, dict):
        value = {}
    passed = (value.get("status") == "PASS" and value.get("api") == api and
              value.get("commit") == source and value.get("run_id") == run and
              value.get("scope") == SHARE_UI_SCOPE and value.get("checks") == SHARE_UI_LABELS and
              type(value.get("count")) is int and value.get("count") == len(SHARE_UI_LABELS) and
              value.get("recreation") == SHARE_RECREATION and
              value.get("release_ready") is False)
    return {"status": "PASS" if passed else "NOT_VERIFIED", "evidence": value}

def share_ui_selftest():
    import copy
    good = {"status": "PASS", "api": 26, "commit": "source", "run_id": "run",
            "scope": SHARE_UI_SCOPE, "checks": list(SHARE_UI_LABELS),
            "recreation": SHARE_RECREATION,
            "count": len(SHARE_UI_LABELS), "release_ready": False}
    assert share_ui_observe(good, 26, "source", "run")["status"] == "PASS"
    bad = [None, [], {}, dict(good, api=34), dict(good, commit="old"),
           dict(good, run_id="old"), dict(good, status="FAIL"), dict(good, scope="backend"),
           dict(good, count=True), dict(good, release_ready=True),
           dict(good, recreation="NOT_TESTED"), {k:v for k,v in good.items() if k!="recreation"}]
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

def signal_target_identity(pid, cmdline, uid, process_status, package):
    # Android can rewrite argv[0] in an existing argv buffer, leaving NUL padding.
    # Accept only the exact package plus one or more NULs, NEVER other arguments.
    owners = re.findall(r"^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", process_status, re.M)
    name, separator, padding = cmdline.partition(b"\x00")
    exact_name = name == package.encode("ascii")
    zero_tail = bool(separator) and not padding.strip(b"\x00")
    passed = (re.fullmatch(r"[1-9][0-9]*", pid) is not None and int(pid) > 1 and
              exact_name and zero_tail and re.fullmatch(r"[1-9][0-9]*", uid) is not None and
              owners == [(uid, uid, uid, uid)])
    return {"status": "PASS" if passed else "NOT_VERIFIED", "pid": pid,
            "uid": uid, "uid_fields": owners, "expected_package": package,
            "cmdline_bytes": len(cmdline), "cmdline_sha256": hashlib.sha256(cmdline).hexdigest(),
            "cmdline_hex_head": cmdline[:256].hex(), "cmdline_hex_truncated": len(cmdline) > 256,
            "exact_argv0": exact_name, "nul_only_tail": zero_tail,
            "nul_suffix_bytes": len(padding) + 1 if zero_tail else None}

def signal_identity_selftest():
    package = "test.package"
    status = "Name:\ttest\nUid:\t10192\t10192\t10192\t10192\nGid:\t10192\n"
    good = ("123", package.encode() + b"\x00", "10192", status, package)
    positives = [good, (good[0], good[1] + b"\x00" * 127, *good[2:]),
                 (good[0], good[1] + b"\x00" * 511, *good[2:])]
    for values in positives:
        observed = signal_target_identity(*values)
        assert observed["status"] == "PASS", "valid NUL-padded argv0 refused"
        assert observed["cmdline_bytes"] == len(values[1])
        assert observed["nul_suffix_bytes"] == len(values[1]) - len(package)
        assert observed["cmdline_hex_truncated"] == (len(values[1]) > 256)
    bad = []
    for pid in ("", "0", "1", "-1", "123 456", "123\n", "１２３"):
        bad.append((pid, *good[1:]))
    for raw in (b"", package.encode(), b"other\x00", package.encode()+b":worker\x00",
                good[1]+b"argument\x00", good[1]+b"\x00argument\x00",
                good[1]+b"\n", b"\x00"+good[1], good[1]+b"\xff"):
        bad.append((good[0], raw, *good[2:]))
    for uid in ("", "0", "-1", "10192\n", "10192 10193"):
        bad.append((*good[:2], uid, *good[3:]))
    for index in range(4):
        fields = ["10192"] * 4
        fields[index] = "10193"
        bad.append((*good[:3], "Uid:\t" + "\t".join(fields) + "\n", package))
    for invalid in ("", status + "Uid:\t10192\t10192\t10192\t10192\n",
                    "Uid:\t10192\t10192\t10192\n"):
        bad.append((*good[:3], invalid, package))
    for values in bad:
        assert signal_target_identity(*values)["status"] == "NOT_VERIFIED", "unsafe signal target accepted"
    return {"positive": len(positives), "negative": len(bad),
            "scope": "HOST_PROC_IDENTITY_CONTROLS_NOT_ANDROID_PROCESS_DEATH"}

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
    from verify_process_control import wait_old_absent, isolated_stop_runner
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
    result["process_query_traces"] = []
    loss_runner=isolated_stop_runner(adb,gate.SERIAL,gate.PKG,result["process_query_traces"])
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
        # The prior refusal may leave a zero-byte SAF document. Preserve it under
        # another fixture name, so it cannot mask publication in the next case.
        if file_paths():
            shell("mv","/sdcard/Download/PocketTodo-notes.zip","/sdcard/Download/share-stale-empty.zip")
        assert not file_paths()
        start();choose_blocks(True);open_save()
        old_pid = shell("pidof",gate.PKG).strip()
        probes = []
        result["process_loss"] = {"old_pid":old_pid,"absence_probes":probes,
                                  "injection":"CI_APP_UID_SIGKILL_NOT_LMK","stage":"IDENTITY_READ"}
        assert re.fullmatch(r"[1-9][0-9]*",old_pid), "one live product process required: "+repr(old_pid)
        # Deterministic CI fault injection, not a low-memory-killer simulation.
        # am kill left API26 alive; do not force-stop and destroy the result route.
        # Signal only the exact disposable app PID after checking name and UID.
        identity = command("exec-out","run-as",gate.PKG,"cat","/proc/"+old_pid+"/cmdline",binary=True)
        uid = shell("run-as",gate.PKG,"id","-u").strip()
        process_status = shell("run-as",gate.PKG,"cat","/proc/"+old_pid+"/status")
        target = signal_target_identity(old_pid,identity,uid,process_status,gate.PKG)
        result["process_loss"].update(identity=target,uid=uid,uid_fields=target["uid_fields"])
        print("CI_SIGNAL_TARGET "+json.dumps(target),flush=True)
        assert target["status"]=="PASS", "refuse unverified process signal target: "+json.dumps(target)
        shell("run-as",gate.PKG,"kill","-9",old_pid)
        result["process_loss"]["stage"] = "SIGNAL_SENT"
        # Approved CI invocation change: explicit noninteractive shell and DEVNULL.
        # Preserve the original failure; never retry, reconnect, or accept exit255.
        wait_old_absent(prefix,gate.PKG,old_pid,result["process_loss"],invoke=loss_runner)
        picker = find(text="SAVE")
        result["process_loss"]["picker_package"] = picker.get("package")
        ok(picker.get("package") in ("com.android.documentsui","com.google.android.documentsui") and
           not file_paths(), "share background process death is proven while system picker remains")
        tap("SAVE")
        find(**{"content-desc":"v12-status","text":"页面已重建，请重新选择导出内容"})
        paths=file_paths()
        ok(not paths or (len(paths)==1 and command("exec-out","cat",paths[0],binary=True)==b""),
           "share recreated owner refuses old preview without nonempty publication")
        new_pid = shell("pidof",gate.PKG).strip()
        result["process_loss"]["new_pid"] = new_pid
        ok(re.fullmatch(r"[1-9][0-9]*",new_pid) is not None and new_pid!=old_pid,
           "share returned activity runs in a different proven process")
        shot("22-share-process-loss-refused.png");stop()
        ok(snapshot()==(baseline,media),"share process-loss refusal preserves complete database and media")
        if file_paths():
            shell("mv","/sdcard/Download/PocketTodo-notes.zip","/sdcard/Download/share-process-loss-empty.zip")
        assert not file_paths()
        start();choose_blocks(True);open_save();tap("SAVE");saved_message()
        ok(export_bytes()==image_zip,"share fresh explicit selection after process loss exports exact reviewed ZIP")
        shot("23-share-fresh-after-loss.png");stop()
        ok(snapshot()==(baseline,media),"share fresh post-loss success preserves complete database and media")
        result["recreation"]=SHARE_RECREATION
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

# Independent of the device emitter: deleting its labels cannot shrink this
# required contract. These receipts cover synthetic exports, not full delivery.
PAGED_BACKEND_LABELS = ["actual_api"] + [
    name+"_"+kind for kind in ("PDF","PNG_ZIP") for name in (
        "multiple_pages","result_ownership","excluded_blocks_do_not_add_pages","single_page",
        "empty_selection","unknown_selection","private_only","duplicate_identity",
        "selected_bad_image","unselected_bad_image_ignored","source_pixel_budget",
        "invalid_text","page_limit_refuses_not_truncates")
] + ["source_file_unchanged","blank_document_rejected"]
PAGED_PREVIEW_LABELS = [name+"_"+kind for kind in ("PDF","PNG_ZIP") for name in (
    "decoded_actual_pages","decoded_page_bounds_and_ink","corrupt_payload_rejected","wrong_format_rejected",
    "actual_dialog_pages","unchecked_consent","unchecked_save_blocked","saf_format_after_consent",
    "cancel_clears_ticket","preview_preserves_database","dialog_bitmaps_recycled")]
PAGED_NATIVE_LABELS = [name+"_"+kind for kind in ("PDF","PNG_ZIP") for name in (
    "private_excluded_and_empty_selection","format_picker_selected","actual_page_preview",
    "unchecked_save_refused","picker_cancel_preserves_state","real_saf_output",
    "independent_text_page","save_preserves_state","same_revision_privacy_change",
    "stale_publication_refused","stale_refusal_preserves_state","fixture_restored")]
PAGED_NATIVE_SCOPE = "NATIVE_SINGLE_NOTE_TEXT_PDF_PNG_SAF_CANCEL_STALE_NOT_PROCESS_DEATH_OR_RECEIVER"

def paged_observe(codec, native, api, source, run):
    def obj(value): return value if isinstance(value,dict) else {}
    def digest(value): return isinstance(value,str) and re.fullmatch(r"[0-9a-f]{64}",value) is not None
    def identity(value):
        return (value.get("status")=="PASS" and type(value.get("api")) is int and
                value.get("api")==api and value.get("commit")==source and
                value.get("run_id")==run and value.get("release_ready") is False)
    def coverage(value, labels):
        return value.get("labels")==labels and type(value.get("checks")) is int and value["checks"]==len(labels)
    codec,native=obj(codec),obj(native)
    backend=obj(codec.get("paged_exports")); preview=obj(backend.get("preview_ui"))
    receipt=obj(codec.get("paged_native_ui")); instrument=obj(backend.get("instrumentation"))
    outputs=obj(receipt.get("outputs")); errors=[]
    if not identity(codec) or not digest(codec.get("apk_sha256")):
        errors.append("current_source_codec_identity")
    if not identity(backend) or not coverage(backend,PAGED_BACKEND_LABELS) or backend.get("scope")!="APK_PAGED_BACKEND_POPPLER_AND_JDK_NOT_UI_SAF_RECEIVER":
        errors.append("required_paged_backend")
    if not coverage(preview,PAGED_PREVIEW_LABELS) or preview.get("scope")!="ACTUAL_DIALOG_AND_INTERCEPTED_SAF_NOT_PROVIDER_E2E":
        errors.append("required_actual_preview")
    if (instrument.get("runtime")!="TARGET_APP_INSTRUMENTATION" or
        instrument.get("diagnostic_failure_rejected") is not True or
        instrument.get("product_apk_sha256")!=codec.get("apk_sha256") or
        instrument.get("installed_product_readback")!="EXACT_BEFORE_AND_AFTER" or
        instrument.get("default_test_restored")!="EXACT_BYTES_AND_REGISTERED_RUNNER"):
        errors.append("preview_product_identity")
    if not identity(receipt) or not coverage(receipt,PAGED_NATIVE_LABELS) or receipt.get("scope")!=PAGED_NATIVE_SCOPE:
        errors.append("required_real_saf")
    if native.get("status")!="PASS" or native.get("paged_ui")!=receipt:
        errors.append("native_codec_receipt_disagreement")
    if set(outputs)!={"PDF","PNG_ZIP"}: errors.append("missing_format_outputs")
    for kind in ("PDF","PNG_ZIP"):
        output=obj(outputs.get(kind))
        if (not digest(output.get("sha256")) or type(output.get("bytes")) is not int or
            not 0<output.get("bytes",0)<=16777216 or
            output.get("pdf_text")!=("EXACT" if kind=="PDF" else "NOT_OCR_TESTED") or
            output.get("page")!="SINGLE_NONBLANK_TEXT_REGION_NO_IMAGE"):
            errors.append("invalid_output_"+kind)
    derived = paged_derived_observe(receipt.get("derived"), api, source, run)
    if derived["status"] != "PASS": errors.append("required_derived_saf")
    return {"status":"PASS" if not errors else "NOT_VERIFIED","errors":errors,
            "scope":"PAGED_BACKEND_PREVIEW_AND_SINGLE_NOTE_TEXT_SAF_NOT_FULL_SHARING",
            "backend_checks":backend.get("checks"),"preview_checks":preview.get("checks"),
            "native_checks":receipt.get("checks"),"outputs":outputs,"derived":derived,"release_ready":False}

def paged_observer_selftest():
    import copy
    common={"status":"PASS","api":26,"commit":"source","run_id":"run","release_ready":False}
    backend=dict(common,checks=29,labels=PAGED_BACKEND_LABELS[:],
        scope="APK_PAGED_BACKEND_POPPLER_AND_JDK_NOT_UI_SAF_RECEIVER",
        preview_ui={"checks":22,"labels":PAGED_PREVIEW_LABELS[:],
                    "scope":"ACTUAL_DIALOG_AND_INTERCEPTED_SAF_NOT_PROVIDER_E2E"},
        instrumentation={"runtime":"TARGET_APP_INSTRUMENTATION","diagnostic_failure_rejected":True,
                         "product_apk_sha256":"a"*64,"installed_product_readback":"EXACT_BEFORE_AND_AFTER",
                         "default_test_restored":"EXACT_BYTES_AND_REGISTERED_RUNNER"})
    receipt=dict(common,checks=24,labels=PAGED_NATIVE_LABELS[:],scope=PAGED_NATIVE_SCOPE,
        outputs={kind:{"sha256":"b"*64,"bytes":100,"pdf_text":"EXACT" if kind=="PDF" else "NOT_OCR_TESTED",
                       "page":"SINGLE_NONBLANK_TEXT_REGION_NO_IMAGE"} for kind in ("PDF","PNG_ZIP")})
    derived_good, derived_bad = paged_derived_cases()
    receipt["derived"] = derived_good
    codec=dict(common,apk_sha256="a"*64,paged_exports=backend,paged_native_ui=receipt)
    native={"status":"PASS","paged_ui":copy.deepcopy(receipt)}
    baseline=copy.deepcopy((codec,native))
    def accepted(c,n): return paged_observe(c,n,26,"source","run")["status"]=="PASS"
    assert accepted(codec,native) and (codec,native)==baseline
    mutants=[]
    for value in derived_bad:
        c=copy.deepcopy(codec);c["paged_native_ui"]["derived"]=copy.deepcopy(value)
        n=copy.deepcopy(native);n["paged_ui"]=copy.deepcopy(c["paged_native_ui"])
        assert c["status"]==n["status"]=="PASS"
        mutants.append((c,n))
    c=copy.deepcopy(codec);del c["paged_native_ui"]["derived"]
    n=copy.deepcopy(native);n["paged_ui"]=copy.deepcopy(c["paged_native_ui"]);mutants.append((c,n))
    for path in ((),("paged_exports",),("paged_exports","preview_ui"),("paged_native_ui",)):
        for key,value in (("checks",0),("labels",[]),("scope","wrong")) if path else (("commit","old"),("run_id","old"),("api",True),("status","FAIL"),("release_ready",True)):
            c=copy.deepcopy(codec);target=c
            for part in path:target=target[part]
            target[key]=value;mutants.append((c,copy.deepcopy(native)))
    for path,labels in ((("paged_exports",),PAGED_BACKEND_LABELS),
                        (("paged_exports","preview_ui"),PAGED_PREVIEW_LABELS),
                        (("paged_native_ui",),PAGED_NATIVE_LABELS)):
        for index in range(len(labels)):
            c=copy.deepcopy(codec);target=c
            for part in path:target=target[part]
            del target["labels"][index];target["checks"]-=1
            n=copy.deepcopy(native)
            # Missing native checks remain self-consistent in BOTH reports.
            # Parent status stays PASS, reproducing the old aggregate blind spot.
            if path==("paged_native_ui",):n["paged_ui"]=copy.deepcopy(target)
            assert c["status"]==n["status"]=="PASS"
            mutants.append((c,n))
        for key,value in (("api",34),("commit","old"),("run_id","old"),("release_ready",True)) if len(path)==1 else (("checks",True),):
            c=copy.deepcopy(codec);target=c
            for part in path:target=target[part]
            target[key]=value;mutants.append((c,copy.deepcopy(native)))
    for key in ("paged_exports","paged_native_ui"):
        for value in (None,[],{}):
            c=copy.deepcopy(codec);c[key]=value;mutants.append((c,copy.deepcopy(native)))
    for kind in ("PDF","PNG_ZIP"):
        for key,value in (("sha256","bad"),("bytes",0),("bytes",True),("bytes",16777217),("pdf_text","wrong"),("page","wrong")):
            c=copy.deepcopy(codec);c["paged_native_ui"]["outputs"][kind][key]=value
            n=copy.deepcopy(native);n["paged_ui"]=copy.deepcopy(c["paged_native_ui"]);mutants.append((c,n))
    for key,value in (("runtime","wrong"),("diagnostic_failure_rejected",False),
                      ("product_apk_sha256","c"*64),("installed_product_readback","wrong"),
                      ("default_test_restored","wrong")):
        c=copy.deepcopy(codec);c["paged_exports"]["instrumentation"][key]=value
        mutants.append((c,copy.deepcopy(native)))
    mutants.extend([(None,native),(codec,None),(codec,{"status":"PASS"}),
                    (codec,dict(native,status="FAIL"))])
    for c,n in mutants:
        assert repr((c,n))!=repr(baseline),"paged mutation did not apply"
        assert not accepted(c,n),"paged aggregate accepted missing/failed evidence"
    return {"positive":1,"negative":len(mutants),"derived_negative":len(derived_bad)+1,"scope":"REPORT_MUTATIONS_NOT_DEVICE_EXECUTION"}

def paged_derived_observe(value, api, source, run):
    """Independent report contract, not imported from the device emitter."""
    def obj(v): return v if isinstance(v, dict) else {}
    def digest(v): return isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) is not None
    value = obj(value)
    errors = []
    if not (value.get("status") == "PASS" and type(value.get("api")) is int and
            value.get("api") == api and value.get("commit") == source and
            value.get("run_id") == run and value.get("release_ready") is False and
            value.get("scope") == "NATIVE_DERIVED_IMAGE_SAF_NOT_RECEIVER"):
        errors.append("derived_identity")
    outputs = obj(value.get("outputs"))
    if set(outputs) != {"PDF", "PNG_ZIP"}:
        errors.append("derived_formats")
    for kind in ("PDF", "PNG_ZIP"):
        output = obj(outputs.get(kind))
        if not (output.get("status") == "PASS" and type(output.get("pages")) is int and
                output.get("pages") == 1 and type(output.get("bytes")) is int and
                0 < output.get("bytes", 0) <= 16777216):
            errors.append(kind + "_derived_output")
        if not all(digest(output.get(key)) for key in ("sha256", "current_asset", "original_asset")):
            errors.append(kind + "_derived_digest")
        if output.get("current_asset") == output.get("original_asset"):
            errors.append(kind + "_origin_substitution")
        if (output.get("pixels") != "EXACT_OPAQUE_INTERIORS_EDGE_INTERPOLATION_NOT_ASSERTED" or
                output.get("state") != "ALL_TABLES_AND_ALL_MEDIA_UNCHANGED"):
            errors.append(kind + "_derived_assertions")
        for key in ("crop", "mask"):
            rect = output.get(key)
            if not (isinstance(rect, list) and len(rect) == 4 and
                    all(type(n) is int for n in rect) and
                    0 <= rect[0] < rect[2] <= 1280 and 0 <= rect[1] < rect[3] <= 640):
                errors.append(kind + "_derived_" + key)
    a, b = obj(outputs.get("PDF")), obj(outputs.get("PNG_ZIP"))
    if any(a.get(key) != b.get(key) for key in ("current_asset", "original_asset", "crop", "mask")):
        errors.append("derived_cross_format_identity")
    return {"status": "PASS" if not errors else "NOT_VERIFIED", "errors": errors,
            "scope": "INDEPENDENT_DERIVED_SAF_RECEIPT_NOT_FULL_SHARING",
            "commit": source, "run_id": run, "api": api,
            "outputs": outputs, "release_ready": False}


def paged_derived_cases():
    """Handwritten report fixtures independent of verify_paged_exports.py."""
    import copy
    output = {"status": "PASS", "pages": 1, "bytes": 548, "sha256": "d"*64,
              "current_asset": "e"*64, "original_asset": "f"*64,
              "crop": [320, 160, 960, 480], "mask": [640, 238, 800, 402],
              "pixels": "EXACT_OPAQUE_INTERIORS_EDGE_INTERPOLATION_NOT_ASSERTED",
              "state": "ALL_TABLES_AND_ALL_MEDIA_UNCHANGED"}
    good = {"status": "PASS", "scope": "NATIVE_DERIVED_IMAGE_SAF_NOT_RECEIVER",
            "api": 26, "commit": "source", "run_id": "run", "release_ready": False,
            "outputs": {kind: copy.deepcopy(output) for kind in ("PDF", "PNG_ZIP")}}
    bad = [None, [], {}]
    for key in good:
        v = copy.deepcopy(good); del v[key]; bad.append(v)
    for key, value in (("status", "FAIL"), ("scope", "backend"), ("api", True),
                       ("api", 34), ("commit", "old"), ("run_id", "old"), ("release_ready", True)):
        v = copy.deepcopy(good); v[key] = value; bad.append(v)
    for kind in ("PDF", "PNG_ZIP"):
        v = copy.deepcopy(good); del v["outputs"][kind]; bad.append(v)
        for key in output:
            v = copy.deepcopy(good); del v["outputs"][kind][key]; bad.append(v)
        for key, value in (("status", "FAIL"), ("pages", True), ("pages", 2),
            ("bytes", True), ("bytes", 0), ("bytes", 16777217), ("sha256", "bad"),
            ("current_asset", "f"*64), ("current_asset", "a"*64),
            ("original_asset", "b"*64), ("pixels", "NONBLANK"), ("state", "NOT_TESTED"),
            ("crop", []), ("crop", [True, 160, 960, 480]),
            ("crop", [320, 160, 320, 480]), ("crop", [320, 160, 1281, 480]),
            ("crop", [321, 160, 960, 480]), ("mask", [640, 238, 800, 641]),
            ("mask", [640, 239, 800, 402])):
            v = copy.deepcopy(good); v["outputs"][kind][key] = value; bad.append(v)
    v = copy.deepcopy(good); v["outputs"]["other"] = copy.deepcopy(output); bad.append(v)
    assert all(repr(v) != repr(good) for v in bad), "derived mutation did not apply"
    return good, bad

def full_observer_evidence(native, folder, api, source, run, attempt):
    """Independent artifact reader, never call the runtime receipt validator."""
    result = dict(status="NOT_VERIFIED", api=api, commit=source, run_id=run,
                  run_attempt=attempt, release_ready=False,
                  scope="FULL_NATIVE_OBSERVER_ARTIFACT_BINDING_NOT_RELEASE_OR_RECOMPILED_DEX")
    try:
        def exact(left, right):
            if type(left) is not type(right):
                return False
            if type(left) is dict:
                return left.keys() == right.keys() and all(exact(left[k], right[k]) for k in left)
            if type(left) is list:
                return len(left) == len(right) and all(exact(a, b) for a, b in zip(left, right))
            return left == right
        assert type(api) is int and api in (26, 34), "api context"
        assert re.fullmatch("[0-9a-f]{40}", source), "source context"
        assert all(type(v) is str and re.fullmatch("[1-9][0-9]*", v)
                   for v in (run, attempt)), "run context"
        def read(name, limit, allow_empty=False):
            path = folder / name
            assert not any(p.is_symlink() for p in (path, *path.parents)), "symlink artifact"
            with path.open("rb") as stream:
                raw = stream.read(limit + 1)
            assert len(raw) <= limit and (allow_empty or raw), "artifact byte budget: " + name
            return raw
        def pairs(rows):
            value = {}
            for key, item in rows:
                assert key not in value, "duplicate JSON key"
                value[key] = item
            return value
        def obj(name):
            return json.loads(read(name, 65536).decode("utf-8"), object_pairs_hook=pairs)
        binding, phase, receipt = obj("binding.json"), obj("phase.json"), obj("observer.json")
        assert type(binding) is list and len(binding) == 6, "binding shape"
        assert all(type(v) is type(e) and v == e
                   for v, e in zip(binding[:4], (source, run, attempt, api))), "binding context"
        nonce, dex_hash = binding[4:]
        assert type(nonce) is str and re.fullmatch("[0-9a-f]{32}", nonce), "nonce"
        assert type(dex_hash) is str and re.fullmatch("[0-9a-f]{64}", dex_hash), "dex digest shape"
        builds = sorted(p.name for p in folder.glob("observer-*") if p.is_dir())
        assert builds == ["observer-" + nonce], "one nonce build"
        dex = read("observer-" + nonce + "/dex/classes.dex", 16777216)
        assert dex.startswith(b"dex\n") and dex[4:7].isdigit() and dex[7:8] == b"\0", "DEX header"
        assert hashlib.sha256(dex).hexdigest() == dex_hash, "DEX bytes"
        from verify_ui_observer import JAVA
        java = read("observer-" + nonce + "/PocketUiObserver.java", 1048576)
        assert java == JAVA.encode("utf-8"), "checked-out observer Java"
        xml = read("observer-last.xml", 4194304)
        text = xml.decode("utf-8")
        assert "<!" not in text, "XML declarations"
        root = ET.fromstring(text)
        assert root.tag == "hierarchy" and list(root.iter("node")), "nonempty XML hierarchy"
        xml_hash = hashlib.sha256(xml).hexdigest()
        stderr = read("observer-stderr.log", 16777216, allow_empty=True)
        assert type(native) is dict and native.get("status") == "PASS", "native parent"
        assert type(native.get("api")) is int and native["api"] == api, "native API"
        assert native.get("release_ready") is False and "error" not in native, "native failure"
        assert type(native.get("count")) is int and native["count"] == 186, "native count"
        assert type(native.get("checks")) is list and len(native["checks"]) == 186, "native checks"
        assert all(type(v) is str and v for v in native["checks"]), "native label shape"
        embedded = native.get("full_native_observer")
        assert type(embedded) is dict, "required observer object"
        assert embedded.get("evidence_directory") == "native-ui/full-observer", "evidence directory"
        assert type(receipt) is dict and type(phase) is dict, "receipt objects"
        assert exact(embedded.get("receipt"), receipt) and exact(embedded.get("phase"), phase), "persisted receipt agreement"
        expected = dict(status="CLOSED", scope="CI_PERSISTENT_READONLY_UI_NOT_PRODUCT_OR_ROOT_CAUSE_PROOF",
                        commit=source, run_id=run, run_attempt=attempt, api=api,
                        nonce=nonce, dex_sha256=dex_hash, last_xml_sha256=xml_hash)
        for key, value in expected.items():
            assert type(receipt.get(key)) is type(value) and receipt[key] == value, "receipt identity: " + key
        for key, value in dict(starts=1, reconnects=0, exit_code=0).items():
            assert type(receipt.get(key)) is int and receipt[key] == value, "receipt lifecycle: " + key
        assert phase.get("status") == "PASS" and phase.get("release_ready") is False, "phase status"
        assert phase.get("scope") == "ORIGINAL_NATIVE_PHASE_OBSERVER_LIFECYCLE_NOT_PRODUCT_ACCEPTANCE", "phase scope"
        assert exact(phase.get("binding"), binding), "phase binding"
        assert phase.get("close_before_return") is True, "phase close"
        reads = phase.get("reads")
        assert type(reads) is int and reads > 0, "phase reads"
        for key in ("reads", "last_sequence"):
            assert type(receipt.get(key)) is int and receipt[key] == reads, "independent read count"
        assert phase.get("last_xml_sha256") == xml_hash, "phase XML"
        elapsed = phase.get("elapsed_seconds")
        assert type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 < elapsed < 4500, "phase time"
        assert not any(key in value for value in (phase, receipt)
                       for key in ("error", "close_error", "cleanup_errors")), "observer failure"
        result.update(status="PASS", reads=reads, phase_elapsed_seconds=elapsed,
                      nonce=nonce, dex_sha256=dex_hash, xml_sha256=xml_hash,
                      java_sha256=hashlib.sha256(java).hexdigest(),
                      stderr_bytes=len(stderr), stderr_sha256=hashlib.sha256(stderr).hexdigest(),
                      native_checks=186, close_before_return=True)
    except (AssertionError, OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        result["error"] = repr(exc)
    return result


def evidence_selftest(checker=full_observer_evidence):
    from verify_ui_observer import JAVA
    positive = negative = 0
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        source, run, attempt, api, nonce = "a"*40, "12", "2", 26, "b"*32
        dex = b"dex\n035\0synthetic artifact, NOT compiled Android"
        xml = b'<hierarchy><node text="fixture"/></hierarchy>'
        binding = [source, run, attempt, api, nonce, hashlib.sha256(dex).hexdigest()]
        receipt = dict(status="CLOSED", scope="CI_PERSISTENT_READONLY_UI_NOT_PRODUCT_OR_ROOT_CAUSE_PROOF",
                       commit=source, run_id=run, run_attempt=attempt, api=api, nonce=nonce,
                       dex_sha256=binding[5], starts=1, reconnects=0, exit_code=0, reads=2,
                       last_sequence=2, last_xml_sha256=hashlib.sha256(xml).hexdigest())
        phase = dict(status="PASS", release_ready=False,
                     scope="ORIGINAL_NATIVE_PHASE_OBSERVER_LIFECYCLE_NOT_PRODUCT_ACCEPTANCE",
                     binding=binding, reads=2, close_before_return=True,
                     last_xml_sha256=receipt["last_xml_sha256"], elapsed_seconds=2.5)
        native = dict(status="PASS", api=api, release_ready=False, count=186,
                      checks=["synthetic-" + str(i) for i in range(186)],
                      full_native_observer=dict(receipt=receipt, phase=phase,
                                                evidence_directory="native-ui/full-observer"))
        files = {"binding.json": json.dumps(binding).encode(), "phase.json": json.dumps(phase).encode(),
                 "observer.json": json.dumps(receipt).encode(), "observer-last.xml": xml,
                 "observer-stderr.log": b"", "observer-"+nonce+"/dex/classes.dex": dex,
                 "observer-"+nonce+"/PocketUiObserver.java": JAVA.encode()}
        def reset():
            for name, raw in files.items():
                path = folder/name
                if path.is_symlink(): path.unlink()
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        def evaluate(value, context=None):
            return checker(value, folder, *(context or (api, source, run, attempt)))["status"] == "PASS"
        reset()
        assert evaluate(native), "valid artifact witness"
        positive += 1
        # Equal Python values are not interchangeable JSON evidence types.
        # These must fail even when both stored and embedded copies agree.
        for section, key, value, persist in (
            ("receipt", "starts", 1.0, False),
            ("receipt", "starts", True, False),
            ("phase", "reads", 2.0, False),
            ("phase", "close_before_return", 1, False),
            ("phase", "binding", [source, run, attempt, 26.0, nonce, binding[5]], True),
            ("phase", "binding", [source, run, attempt, 26.0, nonce, binding[5]], False),
        ):
            reset(); bad = copy.deepcopy(native)
            bad["full_native_observer"][section][key] = value
            if persist:
                filename = "observer.json" if section == "receipt" else "phase.json"
                (folder/filename).write_text(json.dumps(bad["full_native_observer"][section]))
            assert not evaluate(bad), "type alias accepted: " + section + "." + key
            negative += 1
        # Every field is removed independently from persisted AND embedded copies.
        for section in ("receipt", "phase"):
            filename = "observer.json" if section == "receipt" else "phase.json"
            for key in native["full_native_observer"][section]:
                reset(); bad = copy.deepcopy(native); del bad["full_native_observer"][section][key]
                (folder/filename).write_text(json.dumps(bad["full_native_observer"][section]))
                assert not evaluate(bad), "missing field: " + section + "." + key
                negative += 1
        for name in files:
            reset(); (folder/name).unlink()
            assert not evaluate(native), "missing artifact: " + name
            negative += 1
        for context in ((34, source, run, attempt), (True, source, run, attempt),
                        (api, "c"*40, run, attempt), (api, source, "13", attempt),
                        (api, source, run, "3")):
            reset(); assert not evaluate(native, context); negative += 1
        for name, value in (
            ("observer-last.xml", xml+b" "), ("observer-last.xml", b"<hierarchy/>"),
            ("observer-last.xml", b"<!DOCTYPE hierarchy><hierarchy><node/></hierarchy>"),
            ("observer-last.xml", b"\xff"), ("observer-last.xml", b"x"*4194305),
            ("binding.json", b"null"), ("phase.json", b'{"status":"FAIL","status":"PASS"}'),
            ("observer.json", b"[]"), ("observer-"+nonce+"/dex/classes.dex", dex+b"x"),
            ("observer-"+nonce+"/PocketUiObserver.java", JAVA.encode()+b" ")):
            reset(); (folder/name).write_bytes(value)
            assert not evaluate(native), "changed artifact: " + name
            negative += 1
        for section, key, value in (
            ("receipt", "starts", True), ("receipt", "starts", 2),
            ("receipt", "reconnects", 1), ("receipt", "exit_code", False),
            ("receipt", "reads", 3), ("receipt", "last_sequence", 3),
            ("receipt", "error", "fixture"), ("receipt", "close_error", "fixture"),
            ("receipt", "cleanup_errors", []), ("receipt", "status", "ACTIVE"),
            ("phase", "reads", True), ("phase", "reads", 0),
            ("phase", "close_before_return", 1), ("phase", "elapsed_seconds", float("nan")),
            ("phase", "elapsed_seconds", float("inf")), ("phase", "elapsed_seconds", 0),
            ("phase", "error", "fixture"), ("phase", "close_error", "fixture"),
            ("phase", "release_ready", True)):
            reset(); bad=copy.deepcopy(native); bad["full_native_observer"][section][key]=value
            filename="observer.json" if section=="receipt" else "phase.json"
            (folder/filename).write_text(json.dumps(bad["full_native_observer"][section]))
            assert not evaluate(bad), "invalid field: " + section + "." + key
            negative += 1
        for key, value in (("full_native_observer", None), ("full_native_observer", {}),
                           ("status", "FAIL"), ("count", 185), ("checks", []),
                           ("release_ready", True), ("api", 34), ("error", "fixture")):
            reset(); bad = copy.deepcopy(native); bad[key] = value
            assert not evaluate(bad), "invalid parent: " + key
            negative += 1
        reset(); raw = (folder/"observer-last.xml").read_bytes()
        outside = folder/"alternate.xml"; outside.write_bytes(raw)
        (folder/"observer-last.xml").unlink(); (folder/"observer-last.xml").symlink_to(outside)
        assert not evaluate(native), "symlink accepted"; negative += 1
    return dict(positive=positive, negative=negative, scope="HOST_ARTIFACT_FIXTURES_NOT_ANDROID")


def evidence_mutations():
    source = inspect.getsource(full_observer_evidence)
    variants = [
        ('assert hashlib.sha256(dex).hexdigest() == dex_hash, "DEX bytes"', 'pass'),
        ('receipt[key] == reads, "independent read count"', 'receipt[key] > 0, "independent read count"'),
        ('phase.get("close_before_return") is True, "phase close"', 'bool(phase.get("close_before_return")), "phase close"'),
        ('exact(embedded.get("receipt"), receipt) and exact(embedded.get("phase"), phase)',
         'embedded.get("receipt") == receipt and embedded.get("phase") == phase'),
        ('exact(phase.get("binding"), binding)', 'phase.get("binding") == binding'),
    ]
    for old, new in variants:
        assert source.count(old) == 1, "mutation anchor"
        changed = source.replace(old, new, 1); assert changed != source
        scope = dict(globals()); exec(compile(changed, "<artifact-mutant>", "exec"), scope)
        try: evidence_selftest(scope["full_observer_evidence"])
        except AssertionError as exc:
            assert str(exc) in (
                "changed artifact: observer-"+"b"*32+"/dex/classes.dex",
                "invalid field: receipt.reads", "invalid field: phase.close_before_return",
                "type alias accepted: receipt.starts", "type alias accepted: phase.binding"), str(exc)
        else: raise AssertionError("artifact validator mutant survived")
    return len(variants)


def report_entry_selftest(report_fn=None):
    """Run the actual report body; unrelated suites and HTTP are host doubles."""
    from verify_ui_observer import JAVA
    if report_fn is None:
        report_fn = report
    source, run, attempt = "a"*40, "12", "2"
    positive = negative = 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        files = {}
        for api in (26, 34):
            prefix = f"collected/database-api-{api}/"
            nonce = ("b" if api == 26 else "c")*32
            dex = b"dex\n035\0HOST FIXTURE NOT ANDROID"
            xml = b'<hierarchy><node text="fixture"/></hierarchy>'
            binding = [source, run, attempt, api, nonce, hashlib.sha256(dex).hexdigest()]
            receipt = dict(status="CLOSED", scope="CI_PERSISTENT_READONLY_UI_NOT_PRODUCT_OR_ROOT_CAUSE_PROOF",
                           commit=source, run_id=run, run_attempt=attempt, api=api, nonce=nonce,
                           dex_sha256=binding[-1], starts=1, reconnects=0, exit_code=0,
                           reads=2, last_sequence=2, last_xml_sha256=hashlib.sha256(xml).hexdigest())
            phase = dict(status="PASS", release_ready=False,
                         scope="ORIGINAL_NATIVE_PHASE_OBSERVER_LIFECYCLE_NOT_PRODUCT_ACCEPTANCE",
                         binding=binding, reads=2, close_before_return=True,
                         last_xml_sha256=receipt["last_xml_sha256"], elapsed_seconds=2.5)
            native = dict(status="PASS", api=api, release_ready=False, count=186,
                          checks=["repeated-valid-label"]*186,
                          full_native_observer=dict(receipt=receipt, phase=phase,
                                                   evidence_directory="native-ui/full-observer"))
            def add(name, value):
                files[prefix+name] = value if type(value) is bytes else json.dumps(value).encode()
            add("native-ui/native-result.json", native)
            add("native-ui/full-observer/binding.json", binding)
            add("native-ui/full-observer/phase.json", phase)
            add("native-ui/full-observer/observer.json", receipt)
            add("native-ui/full-observer/observer-last.xml", xml)
            add("native-ui/full-observer/observer-stderr.log", b"")
            add("native-ui/full-observer/observer-"+nonce+"/dex/classes.dex", dex)
            add("native-ui/full-observer/observer-"+nonce+"/PocketUiObserver.java", JAVA.encode())
            add("device-schema3-apks.txt", dict(status="PASS", product_before="d"*64,
                product_after="d"*64, default_test_before="e"*64, default_test_after="e"*64))
            add("device-schema3-certificates.txt", {k: "f"*64 for k in
                ("app", "default_test", "schema3_test", "restore_test")})
        def reset():
            for name, value in files.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
        def alter_json(name, edit):
            path = root/name
            value = json.loads(path.read_text())
            edit(value)
            path.write_text(json.dumps(value))
        def invoke(large=False, corrupt=False):
            # Execute the report function itself, not a second model of its
            # aggregation. Only unrelated suites and network are host doubles.
            published = []
            reads = []
            raw_reads = []
            def open_request(req, timeout):
                assert timeout == 30 and req.full_url.startswith(
                    "https://api.github.com/repos/fixture/repo/contents/reports/schema3-")
                if req.method == "PUT":
                    body = json.loads(req.data)
                    assert body["branch"] == "evidence"
                    published.append(base64.b64decode(body["content"]))
                    response = {"commit": {"sha": "1"*40}}
                elif published:
                    reads.append(req.full_url)
                    response = {"encoding": "base64", "content": base64.b64encode(published[-1]).decode(),
                                "html_url": "https://example.invalid/fixture-only"}
                    if large:
                        data = published[-1]
                        assert len(data) > 1024*1024, "large report fixture did not reach boundary"
                        response.update(type="file", path="reports/schema3-"+source+"-"+run+".json",
                            size=len(data), encoding="none", content="",
                            sha=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest())
                else:
                    raise urllib.error.HTTPError(req.full_url, 404, "host fixture", {}, None)
                return io.BytesIO(json.dumps(response).encode())
            def raw_read(route, limit):
                raw_reads.append(route)
                assert route == "contents/reports/schema3-"+source+"-"+run+".json?ref="+"1"*40
                assert limit == len(published[-1])+1
                return b"!"+published[-1][1:] if corrupt else published[-1]
            green = lambda *args, **kwargs: {"status": "PASS"}
            scope = dict(report_fn.__globals__)
            scope.update(Path=lambda value: root/value, selftest=lambda: (
                             {"scope": "HOST_STUBS", "large_fixture": "x"*(1024*1024+1)}
                             if large else {"scope": "HOST_STUBS"}),
                         native_schema3=green, share_ui_observe=green, paged_observe=green,
                         registration=green, observe=green, derivative_summary=green,
                         LABELS={"seed": [], "reopen": [], "restore_seed": [], "restore_reopen": []},
                         full_observer_evidence=full_observer_evidence,
                         os=types.SimpleNamespace(environ={"GITHUB_SHA": source, "GITHUB_RUN_ID": run,
                             "GITHUB_RUN_ATTEMPT": attempt, "GITHUB_REPOSITORY": "fixture/repo",
                             "GH_TOKEN": "host-fixture-not-a-secret"}),
                         urllib=types.SimpleNamespace(error=urllib.error, request=types.SimpleNamespace(
                             Request=urllib.request.Request, urlopen=open_request)))
            runner = types.FunctionType(report_fn.__code__, scope)
            module = types.ModuleType("verify_note_management")
            module.aggregate = green
            error = None
            with patch.dict(sys.modules, {"verify_note_management": module}), redirect_stdout(io.StringIO()), \
                    patch("verify_evidence.raw_evidence_read", raw_read):
                try:
                    runner()
                except AssertionError as exc:
                    error = str(exc)
            assert len(published) == len(reads) == 1, "report not published and read back"
            assert len(raw_reads) == int(large), "report raw read count"
            return json.loads(published[0]), error
        reset()
        doc, error = invoke()
        assert error is None and doc["status"] == "PASS" and doc["release_ready"] is False, "valid report witness"
        positive += 1
        def rejected(label):
            nonlocal negative
            doc, error = invoke()
            assert doc["status"] == "NOT_VERIFIED" and error == (
                "schema3 suite absent or failed; read published evidence"), "report accepted: " + label
            negative += 1
        for api in (26, 34):
            prefix = f"collected/database-api-{api}/native-ui/"
            reset()
            alter_json(prefix+"native-result.json", lambda v: v.pop("full_native_observer"))
            rejected("missing observer " + str(api))
            for name in files:
                if name.startswith(prefix+"full-observer/"):
                    reset(); (root/name).unlink()
                    rejected("missing raw " + name)
            reset()
            alter_json(prefix+"full-observer/binding.json", lambda v: v.__setitem__(2, "3"))
            rejected("wrong attempt " + str(api))
            reset()
            alter_json(prefix+"native-result.json", lambda v: v["full_native_observer"]["receipt"].__setitem__("starts", True))
            rejected("embedded type alias " + str(api))
        reset()
        # A failed unrelated suite must not be overridden by observer success.
        alter_json("collected/database-api-26/device-schema3-apks.txt",
                   lambda v: v.__setitem__("status", "FAIL"))
        rejected("unrelated suite failure")
        reset()
        doc, error = invoke()
        assert error is None and doc["status"] == "PASS", "positive after negatives"
        positive += 1
        doc, error = invoke(large=True)
        assert error is None and doc["status"] == "PASS", "large actual report witness"
        positive += 1
        doc, error = invoke(large=True, corrupt=True)
        assert error == "large evidence exact bytes mismatch", "corrupt large report accepted"
        negative += 1
    return {"positive": positive, "negative": negative,
            "scope": "ACTUAL_REPORT_BODY_OTHER_SUITES_AND_HTTP_DOUBLED_NOT_ANDROID"}


def report_entry_mutations():
    original = inspect.getsource(report)
    tree = ast.parse(original)
    function = tree.body[0]
    target = []
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name) and node.value.func.id == "full_observer_evidence":
                target.append(node)
    assert len(target) == 1, "report hook must be one executable assignment"
    variants = []
    for mode in ("remove", "force_pass"):
        changed = copy.deepcopy(tree)
        class Mutate(ast.NodeTransformer):
            def visit_Assign(self, node):
                if node.lineno != target[0].lineno:
                    return node
                if mode == "remove":
                    return ast.copy_location(ast.Pass(), node)
                node.value = ast.parse('{"status": "PASS"}', mode="eval").body
                return node
        changed = Mutate().visit(changed)
        ast.fix_missing_locations(changed)
        assert ast.dump(tree) != ast.dump(changed), "report mutation not applied"
        scope = dict(report.__globals__)
        exec(compile(changed, "<report-hook-mutant>", "exec"), scope)
        try:
            report_entry_selftest(scope["report"])
        except AssertionError as exc:
            # The valid report witness must have passed before this rejection.
            assert str(exc) == "report accepted: missing observer 26", str(exc)
        else:
            raise AssertionError("report hook mutant survived")
        variants.append(mode)
    return variants


def report():
    controls = selftest()
    source, run = os.environ["GITHUB_SHA"], os.environ["GITHUB_RUN_ID"]
    devices = {}
    for api in (26, 34):
        folder = Path("collected") / ("database-api-" + str(api))
        devices[str(api)] = {}
        path = folder / "native-ui/native-result.json"
        native = json.loads(path.read_text()) if path.exists() else {}
        devices[str(api)]["full_native_observer"] = full_observer_evidence(
            native, folder / "native-ui/full-observer", api, source, run,
            os.environ["GITHUB_RUN_ATTEMPT"])
        devices[str(api)]["default_ui"] = native_schema3(native, api)
        devices[str(api)]["markdown_ui"] = share_ui_observe(native.get("markdown_ui"), api, source, run)
        path = folder / "native-ui/codec-result.json"
        codec = json.loads(path.read_text()) if path.exists() else {}
        devices[str(api)]["paged_exports"] = paged_observe(codec, native, api, source, run)
        from verify_note_management import aggregate as note_management_aggregate
        devices[str(api)]["note_management"] = note_management_aggregate(codec, native, api, source, run)
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
           "paged_exports_summary": {api: phases["paged_exports"] for api, phases in devices.items()},
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
    from verify_evidence import verify_readback
    actual = verify_readback(api, path, written["commit"]["sha"], data)
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
