#!/usr/bin/env python3
"""Stable preview signing and same-key retained-data overwrite, not phone migration."""
import base64
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

PACKAGE = "com.supercubegame.pockettodo.v12.preview"
OLD_SOURCE = "f42e88e10052a4c71e21b83aa0d4475849b807a0"
TABLES = "revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports".split()
SECRET_NAMES = ("POCKET_PREVIEW_KEYSTORE_B64", "POCKET_PREVIEW_STORE_PASSWORD",
                "POCKET_PREVIEW_KEY_ALIAS", "POCKET_PREVIEW_KEY_PASSWORD",
                "POCKET_PREVIEW_CERT_SHA256")
LABELS = ["old_installed_exact", "ui_nonempty_fixture", "before_independent_snapshot",
          "replace_without_uninstall", "new_installed_exact", "immediate_state_exact",
          "new_ui_opens", "restart_state_exact"]
SCOPE = "REBUILT_OLD_SOURCE_SAME_FIXED_KEY_OVERWRITE_NOT_EXISTING_PHONE_CERTIFICATE"


def need(condition, reason):
    if not condition:
        raise AssertionError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def signing_values(env):
    # Never include a secret value, exception repr, or underlying decoder output.
    need(all(isinstance(env.get(n), str) and env[n] for n in SECRET_NAMES),
         "STABLE_SIGNING_NOT_CONFIGURED: required repository secrets missing; no fallback")
    need(re.fullmatch(r"[0-9a-f]{64}", env[SECRET_NAMES[4]]) is not None,
         "STABLE_SIGNING_INVALID_CERTIFICATE_DIGEST")
    need(re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", env[SECRET_NAMES[2]]) is not None,
         "STABLE_SIGNING_INVALID_ALIAS")
    need(all("\n" not in env[n] and "\r" not in env[n] and "\0" not in env[n]
             for n in SECRET_NAMES[1:4]), "STABLE_SIGNING_INVALID_CREDENTIAL_FORMAT")
    try:
        raw = base64.b64decode(env[SECRET_NAMES[0]], validate=True)
    except (ValueError, TypeError):
        raise AssertionError("STABLE_SIGNING_INVALID_BASE64") from None
    need(0 < len(raw) <= 1024 * 1024, "STABLE_SIGNING_KEYSTORE_SIZE")
    return raw, dict(alias=env[SECRET_NAMES[2]], storePassword=env[SECRET_NAMES[1]],
                     keyPassword=env[SECRET_NAMES[3]], certificate=env[SECRET_NAMES[4]])


def signing_directory():
    root = Path(os.environ["RUNNER_TEMP"]).resolve()
    folder = Path(os.environ["POCKET_SIGNING_DIR"])
    need(folder.is_absolute() and folder.parent.resolve() == root and
         re.fullmatch(r"pocket-signing-(26|34)", folder.name) is not None,
         "SIGNING_DIRECTORY_MUST_BE_RUNNER_TEMP")
    need(not folder.is_symlink(), "SIGNING_DIRECTORY_SYMLINK")
    return folder


def prepare_signing():
    raw, values = signing_values(os.environ)
    folder = signing_directory()
    folder.mkdir(mode=0o700, exist_ok=False)
    try:
        key = folder / "preview.jks"
        fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        # Password is transported via subprocess environment, never argv/output.
        command = ["keytool", "-exportcert", "-keystore", str(key),
                   "-alias", values["alias"], "-storepass:env", SECRET_NAMES[1]]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=30, check=False)
        need(result.returncode == 0 and result.stdout and
             digest(result.stdout) == values["certificate"],
             "STABLE_SIGNING_KEYSTORE_OR_CERTIFICATE_MISMATCH")
        fd = os.open(folder / "credentials.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(values, stream)
    except BaseException:
        cleanup_signing()
        raise
    print("STABLE_SIGNING_PREPARED certificate=" + values["certificate"], flush=True)


def cleanup_signing():
    folder = signing_directory()
    if not folder.exists():
        return
    need({p.name for p in folder.iterdir()} <= {"preview.jks", "credentials.json"},
         "SIGNING_CLEANUP_UNEXPECTED_FILE")
    for name in ("preview.jks", "credentials.json"):
        (folder / name).unlink(missing_ok=True)
    folder.rmdir()


def typed(value):
    if value is None:
        return ["null", None]
    if type(value) is int:
        return ["integer", str(value)]
    if type(value) is float:
        return ["real", value.hex()]
    if type(value) is str:
        return ["text", value]
    need(type(value) is bytes, "UNSUPPORTED_SQLITE_TYPE")
    return ["blob", base64.b64encode(value).decode()]


def database_snapshot(path):
    # The host reads SQLite independently; product export/restore is not the oracle.
    with sqlite3.connect("file:" + str(path.resolve()) + "?mode=ro", uri=True) as db:
        need(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "SQLITE_INTEGRITY")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        need(version == 3, "UPGRADE_EXPECTS_SCHEMA3")
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        need(names == sorted(TABLES), "EXACT_DATABASE_TABLE_SET")
        schema = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        tables = {}
        for name in names:
            cursor = db.execute('SELECT rowid,* FROM "' + name + '" ORDER BY rowid')
            tables[name] = dict(columns=[c[0] for c in cursor.description],
                                rows=[[typed(v) for v in row] for row in cursor.fetchall()])
        return dict(version=version, schema=schema, tables=tables)


def state_equal(before, after):
    need(before["database"] == after["database"], "DATABASE_TYPED_ROWS_OR_SCHEMA_CHANGED")
    need(before["media"] == after["media"], "MEDIA_BYTES_OR_FILE_SET_CHANGED")
    need(before["uid"] == after["uid"], "PACKAGE_UID_CHANGED")


def check_apk_identity(meta, certificate):
    need(meta["package"] == PACKAGE, "APK_PACKAGE_MISMATCH")
    need(meta["version_code"] == 3 and meta["version_name"] == "1.2",
         "APK_VERSION_MISMATCH")
    need(meta["min_sdk"] == 26, "APK_MIN_SDK_MISMATCH")
    need(meta["certificate"] == certificate, "APK_CERTIFICATE_MISMATCH")
    need(type(meta["bytes"]) is int and meta["bytes"] > 0 and
         re.fullmatch(r"[0-9a-f]{64}", meta["sha256"]) is not None, "APK_BYTES_MISSING")


def check_receipt(value, source, run, attempt, api, candidate):
    need(value["status"] == "PASS" and value["scope"] == SCOPE, "UPGRADE_NOT_ACCEPTED")
    need((value["commit"], value["run_id"], value["run_attempt"], value["api"]) ==
         (source, run, attempt, api) and type(value["api"]) is int, "UPGRADE_BINDING_MISMATCH")
    need(value["old_source"] == OLD_SOURCE, "OLD_SOURCE_MISMATCH")
    need(value["labels"] == LABELS, "UPGRADE_STAGES_MISSING_OR_REORDERED")
    need(value["install_command"] == ["install", "-r", "-t", "candidate.apk"],
         "OVERWRITE_COMMAND_CHANGED")
    installs = [r for r in value["commands"] if r["args"] and r["args"][0] == "install"]
    need(len(installs) == 2 and installs[0]["args"][:2] == ["install", "-t"] and
         installs[1]["args"] == ["install", "-r", "-t", "upgrade-evidence/candidate.apk"] and
         all(r["returncode"] == 0 and r["attempts"] == 1 for r in installs),
         "OBSERVED_INSTALL_COMMANDS_DIFFER")
    need(all(not ({"clear", "uninstall", "-d"} & set(r["args"])) for r in value["commands"]),
         "DESTRUCTIVE_INSTALL_HISTORY")
    need(value["old_apk"]["sha256"] != value["new_apk"]["sha256"], "NOT_A_DISTINCT_UPGRADE")
    need(value["new_apk"]["sha256"] == candidate["sha256"] and
         value["new_apk"]["bytes"] == candidate["bytes"], "DELIVERED_APK_NOT_TESTED")
    for key in ("old_apk", "new_apk"):
        check_apk_identity(value[key], candidate["certificate_sha256"])
        need(value["installed"][key] == value[key]["sha256"], "INSTALLED_APK_NOT_EXACT")
    before = value["snapshots"]["before"]
    need(before["database"]["tables"]["todos"]["rows"] and
         before["database"]["tables"]["blocks"]["rows"] and before["media"],
         "UPGRADE_EMPTY_FIXTURE")
    state_equal(before, value["snapshots"]["immediate"])
    state_equal(before, value["snapshots"]["restart"])
    need(value["release_ready"] is False and value["durable_upgrade_ready"] is False and
         value["current_phone_certificate_compatible"] is False, "UPGRADE_SCOPE_OVERCLAIM")


def apk_identity(path, sdk):
    tools = Path(sdk) / "build-tools/35.0.0"
    def output(*args):
        return subprocess.check_output(list(map(str, args)), text=True,
                                       stderr=subprocess.PIPE, timeout=30)
    badging = output(tools / "aapt", "dump", "badging", path)
    signature = output(tools / "apksigner", "verify", "--verbose", "--print-certs", path)
    package = re.findall(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'",
                         badging, re.M)
    minimum = re.findall(r"^sdkVersion:'(\d+)'$", badging, re.M)
    certs = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})$",
                       signature, re.M)
    need(len(package) == len(minimum) == len(certs) == 1, "APK_IDENTITY_AMBIGUOUS")
    need("uses-permission:" not in output(tools / "aapt", "dump", "permissions", path),
         "APK_UNEXPECTED_PERMISSION")
    raw = path.read_bytes()
    return dict(package=package[0][0], version_code=int(package[0][1]),
                version_name=package[0][2], min_sdk=int(minimum[0]),
                certificate=certs[0], sha256=digest(raw), bytes=len(raw))


def read_candidate(folder, source, run):
    meta = json.loads((folder / "preview.json").read_text())
    need(meta["commit"] == source and meta["run_id"] == run, "CANDIDATE_BINDING")
    need(meta["release_ready"] is False and meta["durable_upgrade_ready"] is False,
         "CANDIDATE_OVERCLAIM")
    name = meta["apk"]
    need(isinstance(name, str) and re.fullmatch(r"PocketTodo-v1\.2-preview-[0-9a-f]{12}\.apk", name),
         "CANDIDATE_UNSAFE_FILENAME")
    path = folder / name
    need(path.is_file() and not path.is_symlink(), "CANDIDATE_NOT_ORDINARY_FILE")
    raw = path.read_bytes()
    need(len(raw) == meta["bytes"] and digest(raw) == meta["sha256"], "CANDIDATE_BYTES")
    return meta, path


def android():
    import time
    import xml.etree.ElementTree as ET
    import emulator_gate as gate
    from verify_adb_transfer import pull_exact
    from verify_process_control import stop_verified
    from verify_ui_observer import Observer
    need(os.environ.get("GITHUB_ACTIONS") == "true", "DISPOSABLE_RUNNER_ONLY")
    source, run, attempt = [os.environ[k] for k in
                            ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")]
    out = Path("upgrade-evidence"); out.mkdir(exist_ok=True)
    need(not (out / "result.json").exists(), "OLD_UPGRADE_RESULT_PRESENT")
    result = dict(status="FAIL", scope=SCOPE, commit=source, run_id=run,
                  run_attempt=attempt, api=gate.API, old_source=OLD_SOURCE,
                  labels=[], installed={}, snapshots={}, commands=[], stops=[],
                  release_ready=False, durable_upgrade_ready=False,
                  current_phone_certificate_compatible=False)
    completed = []

    def save():
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")

    def execute(adb):
        cert = json.loads((signing_directory() / "credentials.json").read_text())["certificate"]
        meta, candidate_path = read_candidate(Path("upgrade-candidate"), source, run)
        old_paths = list(Path("upgrade-old/build/outputs/apk/debug").glob("*.apk"))
        need(len(old_paths) == 1, "ONE_OLD_APK_REQUIRED")
        old = old_paths[0]
        # Constant filename makes the asserted overwrite command independent of build naming.
        candidate = out / "candidate.apk"
        candidate.write_bytes(candidate_path.read_bytes())
        result["old_apk"] = apk_identity(old, gate.SDK)
        result["new_apk"] = apk_identity(candidate, gate.SDK)
        for key in ("old_apk", "new_apk"):
            check_apk_identity(result[key], cert)
        need(result["old_apk"]["sha256"] != result["new_apk"]["sha256"],
             "NOT_A_DISTINCT_UPGRADE")
        need(meta["sha256"] == result["new_apk"]["sha256"] and
             meta["certificate_sha256"] == cert, "CANDIDATE_SIGNATURE_OR_BYTES")
        prefix = [str(adb), "-s", gate.SERIAL]
        def command(args, timeout=40, binary=False):
            need("uninstall" not in args and "clear" not in args and "-d" not in args,
                 "DESTRUCTIVE_OR_DOWNGRADE_COMMAND_FORBIDDEN")
            trace = dict(args=list(map(str, args)), timeout=timeout, attempts=1)
            result["commands"].append(trace); save()
            try:
                p = subprocess.run(prefix + list(map(str, args)), capture_output=True,
                                   stdin=subprocess.DEVNULL, timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                trace.update(error="TIMEOUT", stdout_bytes=len(exc.stdout or b""),
                             stderr_bytes=len(exc.stderr or b""))
                save()
                raise
            trace.update(returncode=p.returncode, stdout_bytes=len(p.stdout),
                         stderr_bytes=len(p.stderr), stdout_sha256=digest(p.stdout),
                         stderr_sha256=digest(p.stderr))
            if p.returncode:
                trace.update(stdout_tail=p.stdout[-8000:].decode(errors="replace"),
                             stderr_tail=p.stderr[-8000:].decode(errors="replace"),
                             truncated=len(p.stdout) > 8000 or len(p.stderr) > 8000)
            save()
            p.check_returncode()
            return p.stdout if binary else p.stdout.decode()
        def shell(*args):
            return command(["shell", "-n", "-T", *args])
        def stop():
            stop_verified(adb, gate.SERIAL, PACKAGE, emit=result["stops"].append)
        def installed(key, path):
            lines = shell("pm", "path", PACKAGE).splitlines()
            need(len(lines) == 1 and lines[0].startswith("package:/data/app/"), "ONE_INSTALLED_APK")
            trace = {}
            result.setdefault("transfers", []).append(trace)
            raw = pull_exact(adb, gate.SERIAL, lines[0][8:], path.read_bytes(), trace)
            need(raw == path.read_bytes(), "INSTALLED_BYTES")
            result["installed"][key] = digest(raw)
        def snapshot(phase):
            folder = out / phase; folder.mkdir()
            names = shell("run-as", PACKAGE, "ls", "databases").splitlines()
            need("pocket-v12.db" in names, "MAIN_DATABASE_ABSENT")
            for name in ("pocket-v12.db", "pocket-v12.db-wal"):
                if name in names:
                    raw = command(["exec-out", "run-as", PACKAGE, "cat", "databases/" + name], binary=True)
                    need(0 < len(raw) <= 8 * 1024 * 1024, "DATABASE_READ_BUDGET")
                    (folder / name).write_bytes(raw)
            database = database_snapshot(folder / "pocket-v12.db")
            media = {}
            names = shell("run-as", PACKAGE, "ls", "files/media").splitlines()
            need(names and len(names) == len(set(names)), "MEDIA_EMPTY_OR_DUPLICATE")
            total = 0
            for name in names:
                need(re.fullmatch(r"[0-9a-f]{64}", name), "UNSAFE_MEDIA_NAME")
                raw = command(["exec-out", "run-as", PACKAGE, "cat", "files/media/" + name], binary=True)
                total += len(raw)
                need(0 < len(raw) <= 8 * 1024 * 1024 and total <= 64 * 1024 * 1024,
                     "MEDIA_READ_BUDGET")
                need(digest(raw) == name, "MEDIA_CONTENT_ID_MISMATCH")
                media[name] = dict(bytes=len(raw), base64=base64.b64encode(raw).decode())
            registry = database["tables"]["media"]
            columns = registry["columns"]
            actual = {row[columns.index("id")][1]: int(row[columns.index("bytes")][1])
                      for row in registry["rows"]}
            need(actual == {k: v["bytes"] for k, v in media.items()}, "MEDIA_REGISTRY_MISMATCH")
            uid = shell("run-as", PACKAGE, "id", "-u").strip()
            need(re.fullmatch(r"[1-9][0-9]+", uid), "PACKAGE_UID_INVALID")
            return dict(database=database, media=media, uid=uid)
        def passed(label):
            need(label == LABELS[len(result["labels"])], "UPGRADE_STAGE_ORDER")
            result["labels"].append(label); save()
        need(shell("getprop", "ro.kernel.qemu").strip() == "1", "NOT_EMULATOR")
        # Fresh disposable AVD only. Never remove any existing installation.
        need(shell("pm", "list", "packages", PACKAGE).strip() == "", "PREEXISTING_INSTALL_REFUSED")
        command(["install", "-t", str(old)], timeout=120)
        installed("old_apk", old); passed("old_installed_exact")
        observer = Observer(adb, gate.SERIAL, gate.SDK, out / "observer", result.setdefault("observer", {}))
        def nodes():
            return list(ET.fromstring(observer.dump()).iter("node"))
        def find(**attrs):
            deadline = time.monotonic() + 20
            current = []
            while time.monotonic() < deadline:
                current = nodes()
                found = [n for n in current if all(n.get(k) == v for k, v in attrs.items())]
                need(len(found) <= 1, "AMBIGUOUS_UPGRADE_CONTROL")
                if found:
                    return found[0]
                time.sleep(.25)
            raise AssertionError("UPGRADE_CONTROL_MISSING: " + repr(attrs) +
                                 " actual=" + repr([n.attrib for n in current]))
        def click(node):
            need(node.get("package") == PACKAGE and node.get("enabled") == "true", "UNSAFE_UI_TARGET")
            match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
            need(match is not None, "UI_TARGET_BOUNDS")
            a, b, c, d = map(int, match.groups())
            need(c > a and d > b, "UI_TARGET_EMPTY")
            shell("input", "tap", str((a + c) // 2), str((b + d) // 2))
        def tap(text):
            click(find(text=text))
        def touch(desc):
            click(find(**{"content-desc": desc}))
        def ready():
            find(**{"content-desc": "v12-status", "text": "已保存到本机"})
        def start():
            shell("am", "start", "-W", "-n", PACKAGE + "/com.supercubegame.pockettodo.MainActivity")
            ready()
        try:
            observer.start(); start()
            touch("新待办输入"); shell("input", "text", "Upgrade_keep_todo"); tap("添加"); ready()
            tap("活动"); ready(); tap("新建分类"); touch("分类名称")
            shell("input", "text", "Upgrade_category"); tap("保存"); ready()
            controls = [n for n in nodes() if n.get("content-desc", "").startswith("category-add-")]
            need(len(controls) == 1, "ONE_SYNTHETIC_CATEGORY")
            click(controls[0]); touch("活动名称"); shell("input", "text", "Upgrade_activity")
            tap("保存"); ready(); tap("Upgrade_activity"); ready(); tap("笔记"); ready()
            tap("加入文字"); touch("文字内容"); shell("input", "text", "Upgrade_keep_text")
            tap("保存"); ready(); tap("加入图片"); tap("加入合成图"); ready()
            stop()
            before = snapshot("before")
            tables = before["database"]["tables"]
            need(len(tables["todos"]["rows"]) == 1 and len(tables["notes"]["rows"]) == 1 and
                 len(tables["blocks"]["rows"]) == 2 and len(before["media"]) == 1,
                 "SYNTHETIC_FIXTURE_POPULATION")
            need(any(["text", "Upgrade_keep_text"] in row for row in tables["blocks"]["rows"]) and
                 any(["text", "Upgrade_keep_todo"] in row for row in tables["todos"]["rows"]),
                 "SYNTHETIC_FIXTURE_CONTENT")
            result["snapshots"]["before"] = before
            passed("ui_nonempty_fixture"); passed("before_independent_snapshot")
            # Installed observer is closed before replacement and restarted afterwards.
            observer.close()
            result["install_command"] = ["install", "-r", "-t", "candidate.apk"]
            command(["install", "-r", "-t", str(candidate)], timeout=120)
            passed("replace_without_uninstall")
            installed("new_apk", candidate); passed("new_installed_exact")
            result["snapshots"]["immediate"] = snapshot("immediate")
            state_equal(before, result["snapshots"]["immediate"]); passed("immediate_state_exact")
            observer = Observer(adb, gate.SERIAL, gate.SDK, out / "new-observer",
                                result.setdefault("new_observer", {}))
            observer.start(); start()
            find(text="Upgrade_keep_todo"); passed("new_ui_opens")
            stop(); result["snapshots"]["restart"] = snapshot("restart")
            state_equal(before, result["snapshots"]["restart"]); passed("restart_state_exact")
            observer.close()
            result["status"] = "PASS"
            check_receipt(result, source, run, attempt, gate.API, meta)
            completed.append("verified")
        finally:
            observer.close(primary_failed=result["status"] != "PASS")
            save()

    def finish(adb):
        need(completed == ["verified"], "UPGRADE_CALLBACK_NOT_COMPLETED")
    gate.verify_database = execute
    gate.verify_native_ui = finish
    try:
        gate.main()
        need(completed == ["verified"], "UPGRADE_NOT_EXECUTED")
    except BaseException as exc:
        result.update(status="FAIL", error=repr(exc))
        raise
    finally:
        save()
        # Never include APK, key material, credentials or entire workspace in evidence uploads.
        (out / "candidate.apk").unlink(missing_ok=True)
        print("UPGRADE_RESULT status=" + result["status"] + " stages=" + str(len(result["labels"])))


def report():
    import urllib.request
    from verify_evidence import publish
    source, run, attempt = [os.environ[k] for k in
                            ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")]
    root = Path("collected")
    value = dict(status="FAIL", scope=SCOPE, commit=source, run_id=run, run_attempt=attempt,
                 devices={}, release_ready=False, durable_upgrade_ready=False,
                 current_phone_certificate_compatible=False)
    failure = None
    try:
        meta, _ = read_candidate(root / "internal-preview-candidate", source, run)
        needs = json.loads(os.environ["NEEDS_JSON"])
        need(needs["upgrade"]["result"] == "success", "UPGRADE_MATRIX_JOB_NOT_SUCCESS")
        for api in (26, 34):
            raw = (root / ("upgrade-api-" + str(api)) / "result.json").read_bytes()
            need(len(raw) <= 2 * 1024 * 1024, "UPGRADE_REPORT_BUDGET")
            row = json.loads(raw)
            value["devices"][str(api)] = row
            check_receipt(row, source, run, attempt, api, meta)
        value["status"] = "PASS"
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as exc:
        value["error"] = repr(exc); failure = exc
    def api(path, method="GET", body=None):
        request = urllib.request.Request("https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + "/" + path,
                    method=method, data=None if body is None else json.dumps(body).encode(),
                    headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                             "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    Path("upgrade-report.json").write_bytes(raw)
    asset = publish(api, "reports/upgrade-" + source + "-" + run + "-" + attempt + ".json", raw)
    print("UPGRADE_EVIDENCE " + json.dumps(asset), flush=True)
    need(failure is None and value["status"] == "PASS", "UPGRADE_NOT_ACCEPTED: see published evidence")


SIGNING_PATH_SCRIPT = """set -euo pipefail
case "$TEST_API" in 26|34) ;; *) exit 1 ;; esac
python3 - <<'PY'
import os
from pathlib import Path
root = Path(os.environ["RUNNER_TEMP"])
assert root.is_absolute() and root.is_dir(), "valid runner temp required"
assert not any(c in str(root) for c in ("\\n", "\\r", "\\0")), "unsafe runner temp"
folder = root / ("pocket-signing-" + os.environ["TEST_API"])
with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as stream:
    stream.write("POCKET_SIGNING_DIR=" + str(folder) + "\\n")
PY
"""


def signing_path_wiring(lines, prefix=()):
    """Validate this canonical job's env scope and executable first step."""
    step_start = lines.index("    steps:")
    job_env = lines[:step_start]
    need(not any("runner." in v or "POCKET_SIGNING_DIR:" in v for v in job_env),
         "RUNNER_CONTEXT_FORBIDDEN_IN_JOB_ENV")
    steps = []
    for line in lines[step_start + 1:]:
        if line.startswith("      - "):
            steps.append([])
        need(bool(steps), "UNEXPECTED_STEP_LAYOUT")
        steps[-1].append(line)
    expected = ["      - name: Initialize fixed signing directory",
                "        run: |"] + ["          " + v for v in SIGNING_PATH_SCRIPT.splitlines()]
    need(steps[:len(prefix)] == list(prefix), "SIGNING_PATH_REQUIRED_PREFIX")
    need(steps[len(prefix)] == expected, "SIGNING_PATH_INITIALIZATION_ORDER")
    need(sum("Initialize fixed signing directory" in v for v in lines) == 1,
         "SIGNING_PATH_INITIALIZER_DUPLICATED")
    need(not any(line.startswith("          POCKET_SIGNING_DIR:")
                 for step in steps[len(prefix)+1:] for line in step),
         "SIGNING_PATH_LATER_OVERRIDE")


def signing_path_selftest():
    """Execute the real initialization shell; never import or invoke Android."""
    import tempfile
    lines = ["    env:", "      TEST_API: ${{ matrix.api }}",
             "      POCKET_STABLE_SIGNING: '1'", "    steps:",
             "      - name: Initialize fixed signing directory", "        run: |"]
    lines += ["          " + v for v in SIGNING_PATH_SCRIPT.splitlines()]
    lines += ["      - name: Later step", "        run: echo no-secrets"]
    signing_path_wiring(lines)
    signing_path_wiring(lines + ["      - name: Read configured path", "        run: |",
                                 "          print(os.environ['POCKET_SIGNING_DIR'])"])
    invalid = []
    # Reproduce the actual rejected job-level expression, with a valid initializer witness.
    bad = lines[:]; bad.insert(3, "      POCKET_SIGNING_DIR: ${{ runner.temp }}/pocket-signing-${{ matrix.api }}")
    invalid.append(bad)
    invalid.append([v for v in lines if v != "      - name: Initialize fixed signing directory"])
    invalid.append([v.replace('stream.write(', '#stream.write(') for v in lines])
    invalid.append(lines + ["      - name: Wrong override", "        env:",
                            "          POCKET_SIGNING_DIR: /tmp/wrong", "        run: echo wrong"])
    for bad in invalid:
        try:
            signing_path_wiring(bad)
        except (AssertionError, ValueError):
            pass
        else:
            raise AssertionError("SIGNING_PATH_NEGATIVE_SURVIVED")
    with tempfile.TemporaryDirectory(prefix="signing-path-host-") as tmp:
        root = Path(tmp) / "runner with spaces"; root.mkdir()
        target = Path(tmp) / "github-env"
        def execute(script, api, temp=str(root)):
            target.write_text("EXISTING=retained\n")
            env = dict(os.environ, TEST_API=api, RUNNER_TEMP=temp, GITHUB_ENV=str(target))
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                                    env=env, capture_output=True, timeout=10)
            return result, target.read_text()
        for api in ("26", "34"):
            result, output = execute(SIGNING_PATH_SCRIPT, api)
            need(result.returncode == 0 and output ==
                 "EXISTING=retained\nPOCKET_SIGNING_DIR=" + str(root / ("pocket-signing-" + api)) + "\n",
                 "SIGNING_PATH_RUNTIME_BINDING")
            need(not (root / ("pocket-signing-" + api)).exists(),
                 "INITIALIZER_MUST_NOT_CREATE_SECRET_DIRECTORY")
        for api, temp in (("25", str(root)), ("", str(root)), ("34\nINJECTED=1", str(root)),
                          ("26", "relative"), ("26", str(root / "missing"))):
            result, output = execute(SIGNING_PATH_SCRIPT, api, temp)
            need(result.returncode != 0 and output == "EXISTING=retained\n",
                 "INVALID_PATH_INPUT_NOT_REJECTED")
        # Compiled shell/Python mutation, valid API witness retained; the path observer rejects it.
        old = '("pocket-signing-" + os.environ["TEST_API"])'
        need(SIGNING_PATH_SCRIPT.count(old) == 1, "PATH_MUTATION_ANCHOR")
        changed = SIGNING_PATH_SCRIPT.replace(old, '"pocket-signing-26"')
        result, output = execute(changed, "26")
        need(result.returncode == 0 and output.endswith("/pocket-signing-26\n"), "PATH_MUTANT_WITNESS")
        result, output = execute(changed, "34")
        need(result.returncode == 0 and not output.endswith("/pocket-signing-34\n"),
             "PATH_MUTANT_SURVIVED")
    print("SIGNING_PATH_HOST runtime_positive=2 invalid_inputs=5 wiring_negative=4 witnessed_mutant=1 PASS; NOT_ANDROID")



def workflow_contract(text):
    """Canonical job/step layout only; separate from the stages it guards."""
    jobs = {}
    current = None
    need(text.splitlines().count("jobs:") == 1, "ONE_JOBS_BLOCK_REQUIRED")
    for line in text.split("jobs:\n", 1)[1].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.fullmatch(r"  [a-z_]+:", line):
            current = line.strip()[:-1]
            need(current not in jobs, "DUPLICATE_JOB")
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    need(set(jobs) == {"core", "database", "export_probe", "export_feedback", "upgrade", "report"},
         "UPGRADE_JOB_POPULATION")
    for job, budget in (("core", 5), ("database", 75), ("export_probe", 35),
                        ("export_feedback", 5), ("report", 5), ("upgrade", 35)):
        need([v for v in jobs[job] if v.startswith("    timeout-minutes:")] ==
             ["    timeout-minutes: " + str(budget)], "JOB_BUDGET_CHANGED")
    need("    needs: [core, database]" in jobs["upgrade"] and
         "        api: [26, 34]" in jobs["upgrade"] and
         "    if: github.event_name != 'pull_request'" in jobs["upgrade"],
         "UPGRADE_MATRIX_OR_DEPENDENCY")
    need("    needs: [core, database, export_probe, export_feedback, upgrade]" in jobs["report"],
         "REPORT_DOES_NOT_WAIT_FOR_UPGRADE")
    for job in ("database", "upgrade"):
        lines = jobs[job]
        prefix = (
            ["      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"],
            ["      - name: Require isolated tracing before full regression device work",
             "        run: *isolated_trace_setup"],
        ) if job == "database" else ()
        signing_path_wiring(lines, prefix)
        need("      POCKET_STABLE_SIGNING: '1'" in lines, "STABLE_MODE_NOT_MANDATORY")
        prepare = [i for i, line in enumerate(lines)
                   if line.strip() == "run: python3 tools/verify_upgrade.py prepare-signing"]
        build = [i for i, line in enumerate(lines)
                 if line.strip() == ("run: *verified_build" if job == "database" else
                                     "run: python3 tools/verify_upgrade.py build-old")]
        need(len(prepare) == len(build) == 1 and prepare[0] < build[0], "SIGNING_PREPARE_BEFORE_BUILD")
        for name in SECRET_NAMES:
            need("          " + name + ": ${{ secrets." + name + " }}" in lines, "SIGNING_SECRET_WIRING")
        cleanup = [i for i, line in enumerate(lines)
                   if line.strip() == "run: python3 tools/verify_upgrade.py cleanup-signing"]
        need(len(cleanup) == 1 and lines[cleanup[0] - 1] == "        if: always()",
             "SIGNING_CLEANUP_NOT_ALWAYS")
    need("        run: python3 tools/verify_upgrade.py android" in jobs["upgrade"],
         "ANDROID_UPGRADE_CALLER_MISSING")
    need("        run: python3 tools/verify_upgrade.py report" in jobs["report"],
         "UPGRADE_REPORT_CALLER_MISSING")
    report_lines = jobs["report"]
    gate = report_lines.index("        run: python3 tools/verify_upgrade.py report")
    publish = report_lines.index("        id: preview")
    need(gate < publish and "      - name: Require both current-source devices before preview delivery" in report_lines,
         "UPGRADE_MUST_BLOCK_PREVIEW_DELIVERY")
    need("          name: upgrade-api-${{ matrix.api }}" in jobs["upgrade"] and
         "          path: upgrade-evidence/" in jobs["upgrade"],
         "UPGRADE_ARTIFACT_OMITTED")
    need(not any(line.strip() in ("path: .", "path: ./", "path: ${{ runner.temp }}")
                 for lines in jobs.values() for line in lines), "UNSAFE_ARTIFACT_SCOPE")


def workflow_selftest():
    signing_path_selftest()
    text = Path(".github/workflows/android.yml").read_text()
    workflow_contract(text)
    start = text.index("  database:\n")
    end = text.index("  upgrade:\n", start)
    database = text[start:end]
    initializer = ("      - name: Initialize fixed signing directory\n        run: |\n" +
                   "".join("          " + line + "\n" for line in SIGNING_PATH_SCRIPT.splitlines()))
    trace = ("      - name: Require isolated tracing before full regression device work\n"
             "        run: *isolated_trace_setup\n")
    need(database.count(initializer) == database.count(trace) == 1, "ORDER_TEST_ANCHORS")
    wrong = database.replace(initializer, "").replace("    steps:\n", "    steps:\n" + initializer, 1)
    original_failure = text[:start] + wrong + text[end:]
    for changed in (original_failure, text.replace(trace, "", 1),
                    text.replace(trace, trace.replace("        run:", "        if: false\n        run:"), 1)):
        need(changed != text, "ORDER_MUTATION_NOT_APPLIED")
        try:
            workflow_contract(changed)
        except AssertionError:
            pass
        else:
            raise AssertionError("ORIGINAL_ORDER_OR_TRACE_OMISSION_SURVIVED")
    print("SIGNING_ORDER original_first_step_REJECTED missing_trace_REJECTED conditional_trace_REJECTED")
    variants = [
        ("  upgrade:", "  missing:"),
        ("    needs: [core, database, export_probe, export_feedback, upgrade]",
         "    needs: [core, database, export_probe, export_feedback]"),
        ("        run: python3 tools/verify_upgrade.py android", "        run: echo omitted"),
        ("        run: python3 tools/verify_upgrade.py report", "        run: echo omitted"),
        ("      POCKET_STABLE_SIGNING: '1'", "      POCKET_STABLE_SIGNING: '0'"),
        ("          name: upgrade-api-${{ matrix.api }}", "          name: other-evidence"),
    ]
    for old, new in variants:
        need(old in text, "WORKFLOW_MUTATION_NOT_APPLIED")
        changed = text.replace(old, new, 1)
        try:
            workflow_contract(changed)
        except (AssertionError, ValueError):
            pass
        else:
            raise AssertionError("WORKFLOW_OMISSION_SURVIVED")
    print("UPGRADE_WORKFLOW positive=1 negative=" + str(len(variants)) + " STRUCTURE_ONLY_NOT_DEVICE")


def build_old():
    """Pinned historical app, only signing config overlaid; no rewritten product Java."""
    import ast
    root = Path.cwd()
    old = root / "upgrade-old"
    need(subprocess.check_output(["git", "-C", str(old), "rev-parse", "HEAD"],
                                 text=True, timeout=30).strip() == OLD_SOURCE, "OLD_CHECKOUT_IDENTITY")
    (old / "build.gradle").write_bytes((root / "build.gradle").read_bytes())
    changed = subprocess.check_output(["git", "-C", str(old), "diff", "--name-only"],
                                      text=True, timeout=30).splitlines()
    need(changed == ["build.gradle"], "OLD_SOURCE_DIFF_ESCAPES_SIGNING")
    text = (root / ".github/workflows/android.yml").read_text()
    marker = "        run: &verified_build |\n"
    need(text.count(marker) == 1, "ONE_PRESERVED_BUILD_GUARD")
    lines = []
    for line in text.split(marker, 1)[1].splitlines():
        if line and not line.startswith("          "):
            break
        lines.append(line[10:] if line else "")
    script = "\n".join(lines) + "\n"
    need(script.startswith("set -euo pipefail\npython3 - <<'PY'\n") and script.endswith("PY\n"),
         "BUILD_GUARD_SHAPE")
    ast.parse(script.split("python3 - <<'PY'\n", 1)[1][:-3])
    env = dict(os.environ, BUILD_429_EXECUTE="true", BUILD_LOG=str(root / "upgrade-evidence/old-build.log"))
    subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=old, env=env,
                   check=True, timeout=900)


def selftest():
    import contextlib
    import io
    import secrets
    positives = negatives = mutants = 0

    def rejected(fn, reason):
        nonlocal negatives
        try:
            fn()
        except AssertionError as exc:
            need(str(exc) == reason, "WRONG_NEGATIVE_FAILURE: " + str(exc))
            negatives += 1
            return
        raise AssertionError("NEGATIVE_SURVIVED: " + reason)

    sentinel = secrets.token_hex(24)
    env = dict(zip(SECRET_NAMES, [base64.b64encode(b"fixture-not-a-key").decode(),
                                 sentinel, "fixture", sentinel, "a" * 64]))
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        need(signing_values(env)[0] == b"fixture-not-a-key", "SIGNING_POSITIVE")
        positives += 1
        for name in SECRET_NAMES:
            bad = dict(env); bad[name] = ""
            rejected(lambda bad=bad: signing_values(bad),
                     "STABLE_SIGNING_NOT_CONFIGURED: required repository secrets missing; no fallback")
        for name, value, reason in (
            (SECRET_NAMES[0], sentinel + "!", "STABLE_SIGNING_INVALID_BASE64"),
            (SECRET_NAMES[0], "", "STABLE_SIGNING_NOT_CONFIGURED: required repository secrets missing; no fallback"),
            (SECRET_NAMES[2], "../other", "STABLE_SIGNING_INVALID_ALIAS"),
            (SECRET_NAMES[4], "B" * 64, "STABLE_SIGNING_INVALID_CERTIFICATE_DIGEST"),
            (SECRET_NAMES[1], sentinel + "\n", "STABLE_SIGNING_INVALID_CREDENTIAL_FORMAT")):
            bad = dict(env); bad[name] = value
            rejected(lambda bad=bad: signing_values(bad), reason)
    need(sentinel not in output.getvalue() and sentinel not in Path(__file__).read_text(),
         "SIGNING_SENTINEL_LEAKED")
    # Actual keytool round-trip using a disposable test key, never a delivery key.
    # Nothing from the temporary directory becomes a repository file or artifact.
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        key = root / "fixture.p12"
        test_env = dict(os.environ, TEST_SIGNING_PASSWORD=sentinel)
        generated = subprocess.run(["keytool", "-genkeypair", "-storetype", "PKCS12",
            "-keystore", str(key), "-alias", "fixture", "-storepass:env", "TEST_SIGNING_PASSWORD",
            "-keypass:env", "TEST_SIGNING_PASSWORD", "-keyalg", "RSA", "-keysize", "2048",
            "-dname", "CN=Disposable Host Control", "-validity", "1"],
            env=test_env, capture_output=True, timeout=30)
        need(generated.returncode == 0, "HOST_KEYTOOL_GENERATION_FAILED")
        exported = subprocess.run(["keytool", "-exportcert", "-keystore", str(key),
            "-alias", "fixture", "-storepass:env", "TEST_SIGNING_PASSWORD"],
            env=test_env, capture_output=True, timeout=30)
        need(exported.returncode == 0, "HOST_CERTIFICATE_EXPORT_FAILED")
        real = dict(zip(SECRET_NAMES, [base64.b64encode(key.read_bytes()).decode(),
                    sentinel, "fixture", sentinel, digest(exported.stdout)]))
        real.update(RUNNER_TEMP=str(root), POCKET_SIGNING_DIR=str(root / "pocket-signing-26"))
        capture = io.StringIO()
        with patch.dict(os.environ, real), contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            prepare_signing()
            folder = signing_directory()
            need((folder / "preview.jks").read_bytes() == key.read_bytes(), "SIGNING_EXACT_FILE")
            need((folder / "preview.jks").stat().st_mode & 0o777 == 0o600 and
                 (folder / "credentials.json").stat().st_mode & 0o777 == 0o600, "SECRET_FILE_PERMISSIONS")
            cleanup_signing()
            need(not folder.exists(), "SIGNING_CLEANUP_FAILED")
            positives += 1
            os.environ[SECRET_NAMES[4]] = "0" * 64
            rejected(prepare_signing, "STABLE_SIGNING_KEYSTORE_OR_CERTIFICATE_MISMATCH")
            need(not folder.exists(), "FAILED_SIGNING_LEFT_PRIVATE_FILES")
            os.environ[SECRET_NAMES[4]] = real[SECRET_NAMES[4]]
            os.environ[SECRET_NAMES[1]] = "wrong-" + sentinel
            rejected(prepare_signing, "STABLE_SIGNING_KEYSTORE_OR_CERTIFICATE_MISMATCH")
            need(not folder.exists(), "BAD_PASSWORD_LEFT_PRIVATE_FILES")
        need(sentinel not in capture.getvalue() and real[SECRET_NAMES[0]] not in capture.getvalue(),
             "REAL_SIGNING_CONTROL_LEAKED")
    cert = "a" * 64
    meta = dict(package=PACKAGE, version_code=3, version_name="1.2", min_sdk=26,
                certificate=cert, bytes=13, sha256="b" * 64)
    candidate = dict(sha256="c" * 64, bytes=14, certificate_sha256=cert)
    state = dict(database=dict(tables=dict(todos=dict(rows=[[[1, "todo"]]]),
                                          blocks=dict(rows=[[[1, "image"]]]))),
                 media={"d" * 64: dict(bytes=3, base64="YWJj")}, uid="10077")
    receipt = dict(status="PASS", scope=SCOPE, commit="e" * 40, run_id="12",
                   run_attempt="1", api=26, old_source=OLD_SOURCE, labels=LABELS[:],
                   install_command=["install", "-r", "-t", "candidate.apk"],
                   commands=[dict(args=["install", "-t", "old.apk"], returncode=0, attempts=1),
                             dict(args=["install", "-r", "-t", "upgrade-evidence/candidate.apk"],
                                  returncode=0, attempts=1)],
                   old_apk=meta, new_apk=dict(meta, bytes=14, sha256="c" * 64),
                   installed=dict(old_apk="b" * 64, new_apk="c" * 64),
                   snapshots={p: copy.deepcopy(state) for p in ("before", "immediate", "restart")},
                   release_ready=False, durable_upgrade_ready=False,
                   current_phone_certificate_compatible=False)

    def check(value, checker=check_receipt):
        checker(value, "e" * 40, "12", "1", 26, candidate)

    check(receipt); positives += 1
    cases = []
    for key, value, reason in [
        ("status", "NOT_VERIFIED", "UPGRADE_NOT_ACCEPTED"),
        ("commit", "f" * 40, "UPGRADE_BINDING_MISMATCH"),
        ("api", 34, "UPGRADE_BINDING_MISMATCH"),
        ("labels", LABELS[:-1], "UPGRADE_STAGES_MISSING_OR_REORDERED"),
        ("install_command", ["install", "-t", "candidate.apk"], "OVERWRITE_COMMAND_CHANGED"),
        ("current_phone_certificate_compatible", True, "UPGRADE_SCOPE_OVERCLAIM")]:
        bad = copy.deepcopy(receipt); bad[key] = value; cases.append((bad, reason))
    for key, value, reason in [
        ("package", "foreign.package", "APK_PACKAGE_MISMATCH"),
        ("certificate", "f" * 64, "APK_CERTIFICATE_MISMATCH"),
        ("sha256", "f" * 64, "DELIVERED_APK_NOT_TESTED")]:
        bad = copy.deepcopy(receipt); bad["new_apk"][key] = value; cases.append((bad, reason))
    for phase in ("immediate", "restart"):
        for key, value, reason in [
            ("database", {}, "DATABASE_TYPED_ROWS_OR_SCHEMA_CHANGED"),
            ("media", {}, "MEDIA_BYTES_OR_FILE_SET_CHANGED"),
            ("uid", "10078", "PACKAGE_UID_CHANGED")]:
            bad = copy.deepcopy(receipt); bad["snapshots"][phase][key] = value
            cases.append((bad, reason))
    bad = copy.deepcopy(receipt); bad["installed"]["new_apk"] = "0" * 64
    cases.append((bad, "INSTALLED_APK_NOT_EXACT"))
    for bad, reason in cases:
        rejected(lambda bad=bad: check(bad), reason)
    # Each weakened checker still accepts the valid witness, then must be killed
    # by the SAME behavioral negatives, not by a special mutant-only validator.
    for function, anchor in [
        (state_equal, 'need(before["database"] == after["database"], "DATABASE_TYPED_ROWS_OR_SCHEMA_CHANGED")'),
        (state_equal, 'need(before["media"] == after["media"], "MEDIA_BYTES_OR_FILE_SET_CHANGED")'),
        (state_equal, 'need(before["uid"] == after["uid"], "PACKAGE_UID_CHANGED")'),
        (check_apk_identity, 'need(meta["certificate"] == certificate, "APK_CERTIFICATE_MISMATCH")')]:
        source = inspect.getsource(function)
        need(source.count(anchor) == 1, "MUTATION_ANCHOR_DRIFT")
        namespace = dict(globals())
        exec(compile(source.replace(anchor, "pass", 1), "<upgrade-mutant>", "exec"), namespace)
        # Rebind the actual outer checker to the mutated dependency.
        exec(compile(inspect.getsource(check_receipt), "<receipt-with-mutant>", "exec"), namespace)
        mutant = namespace["check_receipt"]
        check(receipt, mutant)
        caught = False
        for bad, _ in cases:
            try:
                check(bad, mutant)
            except AssertionError:
                continue
            caught = True
        need(caught, "MUTANT_NOT_WITNESSED_BY_NEGATIVE_POPULATION")
        mutants += 1
    # Real SQLite files prove typed values, NULL, BLOB and hidden rowid retention.
    with tempfile.TemporaryDirectory() as tmp:
        dbfile = Path(tmp) / "fixture.db"
        with sqlite3.connect(dbfile) as db:
            db.execute("PRAGMA user_version=3")
            for name in TABLES:
                db.execute('CREATE TABLE "' + name + '" (value)')
            db.executemany("INSERT INTO todos(rowid,value) VALUES(?,?)",
                           [(2, None), (4, b"abc"), (7, 1), (9, "1"), (12, 1.5)])
        original = database_snapshot(dbfile)
        need(original["tables"]["todos"]["rows"][1] == [["integer", "4"], ["blob", "YWJj"]],
             "SQLITE_TYPED_ORACLE")
        positives += 1
        with sqlite3.connect(dbfile) as db:
            db.execute("UPDATE todos SET value='1' WHERE rowid=7")
        need(database_snapshot(dbfile) != original, "SQLITE_TYPE_CHANGE_UNDETECTED")
        negatives += 1
    result = dict(status="PASS", positive=positives, negative=negatives,
                  witnessed_mutants=mutants, scope="HOST_ONLY_NOT_ANDROID_OR_SIGNING_ACCEPTANCE")
    print("UPGRADE_HOST " + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    import sys
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    if command == "selftest":
        selftest()
    elif command == "prepare-signing":
        try:
            prepare_signing()
        except BaseException:
            # Do not expose keytool/decoder arguments or secret-bearing exceptions.
            print("STABLE_SIGNING_NOT_VERIFIED: missing/invalid configuration; no temporary-key fallback")
            raise SystemExit(1) from None
    elif command == "cleanup-signing":
        cleanup_signing()
    elif command == "android":
        android()
    elif command == "report":
        report()
    elif command == "workflow-selftest":
        workflow_selftest()
    elif command == "build-old":
        build_old()
    else:
        raise SystemExit("unknown upgrade command")
