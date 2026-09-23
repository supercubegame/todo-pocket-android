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
    ],
    "reopen": [
        "separate_process_exact_state", "separate_process_pair_metadata",
        "separate_process_media_bytes", "separate_process_write_usable",
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

def registration(text):
    package = "com.supercubegame.pockettodo.v12.preview"
    expected = {
        (package + ".test/com.supercubegame.pockettodo." + name, package)
        for name in ("V12DeviceTest", "Schema3DeviceTest")
    }
    rows = re.findall(r"^instrumentation:(\S+) \(target=([^)]+)\)\s*$", text, re.M)
    relevant = [row for row in rows if row[0].startswith(package + ".test/")]
    passed = len(relevant) == 2 and set(relevant) == expected
    return {"status": "PASS" if passed else "NOT_VERIFIED", "registered": relevant,
            "log": text}

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
    assert registration(old + new)["status"] == "PASS"
    assert registration(new + old)["status"] == "PASS"
    bad = ("", old, new, old + new + new,
           (old + new).replace("target=" + package, "target=wrong"),
           old + new.replace("Schema3DeviceTest", "WrongRunner"))
    for text in bad:
        assert registration(text)["status"] != "PASS", "runner registration guard missed"
    controls["registration"] = {"positive": 2, "negative": len(bad)}
    return controls

def device(adb, gate):
    prefix = [str(adb), "-s", gate.SERIAL]
    p = subprocess.run(prefix + ["shell", "pm", "list", "instrumentation"],
                       capture_output=True, text=True, timeout=30)
    text = p.stdout + "\n" + p.stderr
    Path("device-schema3-registration.txt").write_text(text)
    print(text, flush=True)
    assert p.returncode == 0 and registration(text)["status"] == "PASS", "installed test APK must register both exact runners and targets"
    for phase in LABELS:
        if phase == "reopen":
            subprocess.run(prefix + ["shell", "am", "force-stop", gate.PKG], check=True, timeout=30)
            p = subprocess.run(prefix + ["shell", "pidof", gate.PKG], capture_output=True, text=True, timeout=10)
            assert p.returncode == 1 and not p.stdout.strip(), "prior app process still alive"
        args = prefix + ["shell", "am", "instrument", "-w", "-r", "-e", "phase", phase,
                         "-e", "expectedApi", str(gate.API),
                         gate.PKG + ".test/com.supercubegame.pockettodo.Schema3DeviceTest"]
        p = subprocess.run(args, capture_output=True, text=True, timeout=180)
        text = p.stdout + "\n" + p.stderr
        Path("device-schema3-" + phase + ".txt").write_text(text)
        print(text, flush=True)
        assert p.returncode == 0 and observe(text, phase, gate.API)["status"] == "PASS", "schema3 " + phase + " failed; inspect device-schema3 log"

def android():
    print("SCHEMA3_OBSERVER_SELFTEST " + json.dumps(selftest()), flush=True)
    import emulator_gate as gate
    import verify_exports
    original = gate.verify_database
    def database_and_schema3(adb):
        original(adb)
        device(adb, gate)
    gate.verify_database = database_and_schema3
    # Existing codec wrapper still invokes our wrapper, then all old native tests.
    verify_exports.android_main()

def report():
    controls = selftest()
    source, run = os.environ["GITHUB_SHA"], os.environ["GITHUB_RUN_ID"]
    devices = {}
    for api in (26, 34):
        folder = Path("collected") / ("database-api-" + str(api))
        devices[str(api)] = {}
        path = folder / "device-schema3-registration.txt"
        text = path.read_text(errors="replace") if path.exists() else ""
        devices[str(api)]["registration"] = registration(text)
        for phase in LABELS:
            path = folder / ("device-schema3-" + phase + ".txt")
            text = path.read_text(errors="replace") if path.exists() else ""
            devices[str(api)][phase] = observe(text, phase, api)
    passed = all(p["status"] == "PASS" for phases in devices.values() for p in phases.values())
    doc = {"commit": source, "run_id": run, "status": "PASS" if passed else "NOT_VERIFIED",
           "scope": "OPT_IN_SCHEMA2_TO_3_REGISTERED_REFERENCE_STORAGE_NOT_BACKUP_OR_UI",
           "devices": devices, "observer_selftests": controls, "release_ready": False,
           "archive_compatibility": "NOT_IMPLEMENTED", "default_app_schema": 2,
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
