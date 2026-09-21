#!/usr/bin/env python3
"""Exit-code gates. No synthetic substitute for Java, Android, or UI execution."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

def run(args, **kwargs):
    print("+ " + " ".join(map(str, args)), flush=True)
    return subprocess.run(args, check=True, **kwargs)

def core():
    agents = Path("AGENTS.md").read_bytes()
    assert agents == Path("CLAUDE.md").read_bytes(), "agent instructions diverged"
    assert len(agents.splitlines()) <= 200
    manifest = ET.parse("src/main/AndroidManifest.xml").getroot()
    assert not manifest.findall("uses-permission"), "offline app must request no permissions"
    out = Path("build/core")
    out.mkdir(parents=True, exist_ok=True)
    run(["javac", "-encoding", "UTF-8", "-d", str(out),
         "src/main/java/com/supercubegame/pockettodo/TodoModel.java", "tests/CoreTest.java"])
    run(["java", "-cp", str(out), "CoreTest"])

def build():
    run(["gradle", "--no-daemon", "--console=plain", "assembleDebug", "lintDebug"])
    sdk = Path(os.environ["ANDROID_HOME"])
    bt = sdk / "build-tools/35.0.0"
    apk = Path("build/outputs/apk/debug/todo-pocket-android-debug.apk")
    assert apk.exists(), "expected APK output missing"
    Path("delivery").mkdir(exist_ok=True)
    dest = Path("delivery/PocketTodo-1.0-debug.apk")
    dest.write_bytes(apk.read_bytes())
    sig = subprocess.check_output([str(bt / "apksigner"), "verify", "--verbose", "--print-certs", str(dest)], text=True)
    badging = subprocess.check_output([str(bt / "aapt"), "dump", "badging", str(dest)], text=True)
    permissions = subprocess.check_output([str(bt / "aapt"), "dump", "permissions", str(dest)], text=True)
    assert "name='com.supercubegame.pockettodo'" in badging
    assert "sdkVersion:'26'" in badging
    assert "targetSdkVersion:'34'" in badging
    assert "launchable-activity:" in badging
    assert "uses-permission:" not in permissions
    assert "native-code:" not in badging, "APK should not restrict native ABI"
    Path("delivery/signature.txt").write_text(sig)
    Path("delivery/package.txt").write_text(badging + "\n" + permissions)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    Path("delivery/SHA256SUMS.txt").write_text(f"{digest}  {dest.name}\n")
    print(sig)
    print("APK_RESULT " + json.dumps({"sha256": digest, "bytes": dest.stat().st_size, "package": "com.supercubegame.pockettodo", "min_android": "8.0", "signing": "debug"}, ensure_ascii=False))

def report():
    # Only this step receives GH_TOKEN. Never include environment or auth in output.
    out = Path("collected")
    logs = {}
    for name in ("core.log", "setup.log", "build.log", "ui.log", "emulator.log"):
        paths = list(out.rglob(name))
        logs[name] = paths[0].read_text(errors="replace")[-16000:] if paths else "NOT_OBSERVED"
    needs = json.loads(os.environ["NEEDS_JSON"])
    doc = {"commit": os.environ["GITHUB_SHA"], "run_id": os.environ["GITHUB_RUN_ID"],
           "jobs": needs, "logs": logs, "physical_device": "NOT_TESTED"}
    ui_files = list(out.rglob("ui-result.json"))
    doc["ui"] = json.loads(ui_files[0].read_text()) if ui_files else {"status": "NOT_OBSERVED"}
    for name in ("SHA256SUMS.txt", "signature.txt", "package.txt"):
        paths = list(out.rglob(name))
        doc[name] = paths[0].read_text() if paths else "NOT_OBSERVED"
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    def api(path, method="GET", body=None):
        req = urllib.request.Request("https://api.github.com/repos/" + repo + "/" + path,
            data=json.dumps(body).encode() if body is not None else None, method=method,
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    try:
        api("git/ref/heads/evidence")
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
        api("git/refs", "POST", {"ref": "refs/heads/evidence", "sha": os.environ["GITHUB_SHA"]})
    path = "reports/" + os.environ["GITHUB_SHA"] + "-" + os.environ["GITHUB_RUN_ID"] + ".json"
    body = {"message": "Record Android verification evidence", "branch": "evidence", "content": base64.b64encode(data).decode()}
    try:
        prior = api("contents/" + path + "?ref=evidence")
        body["sha"] = prior["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
    written = api("contents/" + path, "PUT", body)
    actual = api("contents/" + path + "?ref=" + written["commit"]["sha"])
    assert base64.b64decode(actual["content"]) == data, "report readback mismatch"
    print("EVIDENCE " + actual["html_url"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", choices=["core", "build", "report"])
    mode = parser.parse_args().gate
    try:
        {"core": core, "build": build, "report": report}[mode]()
    except Exception as exc:
        print(f"GATE_FAILED {mode}: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
