#!/usr/bin/env python3
"""Real APK + system document picker checks, only on a disposable CI emulator."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET

PKG = "com.supercubegame.pockettodo.safe.preview"
OLD = "com.supercubegame.pockettodo"
ACTIVITY = "com.supercubegame.pockettodo.MainActivity"
OUT = Path("delivery")
checks = []

def adb(*args, binary=False):
    return subprocess.check_output(["adb", *args], timeout=40, text=not binary)

def tree():
    adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
    return ET.fromstring(adb("shell", "cat", "/sdcard/window.xml"))

def nodes(): return list(tree().iter("node"))

def find(**attrs):
    deadline = time.monotonic() + 18
    last = []
    while time.monotonic() < deadline:
        last = nodes()
        for n in last:
            if all(n.get(k) == v for k, v in attrs.items()): return n
        time.sleep(0.3)
    print("UI_NODES " + repr([n.attrib for n in last]), flush=True)
    raise AssertionError("UI node not found: " + repr(attrs))

def tap_node(n):
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
    adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))
    time.sleep(0.25)

def tap(**attrs): tap_node(find(**attrs))

def check(ok, name):
    if not ok: raise AssertionError(name)
    checks.append(name); print("PASS " + name, flush=True)

def item(id): return find(**{"content-desc": "todo-" + str(id)})
def absent(id): return not any(n.get("content-desc") == "todo-" + str(id) for n in nodes())
def start(pkg=PKG): adb("shell", "am", "start", "-W", "-n", pkg + "/" + ACTIVITY)
def restart():
    adb("shell", "am", "force-stop", PKG); start()

def add(title):
    tap(**{"content-desc": "新待办输入"})
    adb("shell", "input", "text", title.replace(" ", "%s")); tap(text="添加")

def replace_field(description, title):
    field = find(**{"content-desc": description})
    length = len(field.get("text", "").encode("utf-16-le")) // 2
    tap_node(field)
    adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    adb("shell", "input", "keyevent", *(["KEYCODE_DEL"] * (length + 1)))
    check(find(**{"content-desc": description}).get("text") == "", "editor fixture cleared through real input")
    if title: adb("shell", "input", "text", title.replace(" ", "%s"))

def screenshot(name):
    time.sleep(0.5)
    data = adb("exec-out", "screencap", "-p", binary=True)
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "invalid PNG"
    (OUT / name).write_bytes(data)
    return {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

def save_document():
    deadline = time.monotonic() + 18
    last = []
    while time.monotonic() < deadline:
        last = nodes()
        for n in last:
            if n.get("text", "").casefold() in ("save", "保存") and n.get("enabled") == "true" and "documentsui" in n.get("package", ""):
                tap_node(n); return
        time.sleep(0.3)
    print("PICKER_NODES " + repr([n.attrib for n in last]), flush=True)
    raise AssertionError("System document picker save button missing")

def select_backup_file():
    find(text="PocketTodo-backup.ptodo")
    # Grid nameplate labels can select instead of opening. Use the real list row.
    for n in nodes():
        if n.get("content-desc") == "List view":
            tap_node(n); break
    root = tree()
    matches = [n for n in root.iter("node") if n.get("resource-id", "").endswith(":id/item_root")
               and any(c.get("text") == "PocketTodo-backup.ptodo" for c in n.iter("node"))]
    if len(matches) != 1: raise AssertionError("Expected exactly one backup document row")
    print("PICKER_TARGET " + repr(matches[0].attrib), flush=True)
    tap_node(matches[0])
    # Accessibility keyboard activation is a real picker action, not a URI bypass.
    current = nodes()
    if any(n.get("text") == "PocketTodo-backup.ptodo" and "documentsui" in n.get("package", "") for n in current):
        adb("shell", "input", "keyevent", "KEYCODE_ENTER")

def open_backup():
    tap(text="导入备份"); select_backup_file(); find(text="导入预览")

def stored_state():
    return adb("shell", "run-as", PKG, "cat", "shared_prefs/pocket_todo.xml")

def main():
    OUT.mkdir(exist_ok=True)
    check(os.environ.get("GITHUB_ACTIONS") == "true" and adb("shell", "getprop", "ro.kernel.qemu").strip() == "1", "disposable CI emulator identity")
    old_url = "https://github.com/supercubegame/todo-pocket-android/releases/download/test-35518045028-1/PocketTodo-1.0-debug.apk"
    with urllib.request.urlopen(old_url, timeout=40) as response: old_apk = response.read()
    check(hashlib.sha256(old_apk).hexdigest() == "2064ab1a485552830bb666f782c6081f6099179b860b097c7084e5b2c6b8d695", "original phone-accepted APK pinned digest")
    old_path = Path(os.environ["RUNNER_TEMP"]) / "original-todo.apk"; old_path.write_bytes(old_apk)
    adb("install", str(old_path)); start(OLD); add("Keep old data")
    check(item(1).get("text") == "Keep old data", "seed original app on disposable emulator")
    adb("install", "-r", str(OUT / "PocketTodo-1.1-preview.apk"))
    adb("shell", "pm", "clear", PKG); start()
    find(text="口袋待办")
    check(find(text="还剩 0 件  /  共 0 件") is not None, "isolated preview launches empty")
    shots = [screenshot("01-empty.png")]
    tap(text="添加"); check(absent(1), "blank input creates no task")
    add("Buy milk"); check(item(1).get("text") == "Buy milk", "add via visible input")
    add("Walk outside"); check(item(2).get("text") == "Walk outside", "second task distinct")
    tap(**{"content-desc": "todo-1"}); check(item(1).get("checked") == "true", "complete via checkbox")
    tap(text="待办"); check(absent(1) and item(2) is not None, "pending filter")
    tap(text="已完成"); check(item(1).get("checked") == "true" and absent(2), "completed filter")
    tap(text="全部"); restart()
    check(item(1).get("checked") == "true" and item(2).get("text") == "Walk outside", "restart preserves titles and completion")
    tap(**{"content-desc": "edit-1"}); replace_field("编辑待办输入", "Fresh milk"); tap(text="保存")
    check(item(1).get("text") == "Fresh milk" and item(1).get("checked") == "true", "edit keeps completion and id")
    tap(**{"content-desc": "edit-1"}); replace_field("编辑待办输入", ""); tap(text="保存")
    check(find(text="编辑待办") is not None, "blank edit stays open for correction")
    tap(text="取消"); check(item(1).get("text") == "Fresh milk", "cancel invalid edit preserves title")
    tap(**{"content-desc": "edit-1"}); replace_field("编辑待办输入", "Discard edit"); tap(text="取消")
    check(item(1).get("text") == "Fresh milk", "cancel valid edit preserves title")
    restart(); check(item(1).get("text") == "Fresh milk" and item(1).get("checked") == "true", "edit persists across restart")
    tap(text="导出备份"); tap(text="取消"); check(item(1).get("text") == "Fresh milk", "cancel export keeps list")
    tap(text="导出备份"); tap(text="选择保存位置"); save_document()
    check(find(text="备份已导出并校验") is not None, "export through real system picker and exact readback")
    tap(**{"content-desc": "delete-2"}); tap(text="取消"); check(item(2) is not None, "cancel deletion preserves task")
    tap(**{"content-desc": "delete-2"}); tap(text="删除"); check(absent(2), "confirm deletes exact task")
    tap(**{"content-desc": "todo-1"}); check(item(1).get("checked") == "false", "uncomplete via checkbox")
    restart(); check(absent(2) and item(1).get("checked") == "false", "deletion and uncomplete persist")
    tap(text="导入备份"); adb("shell", "input", "keyevent", "KEYCODE_BACK")
    check(item(1).get("checked") == "false" and absent(2), "cancel file picker keeps list")
    open_backup(); shots.append(screenshot("02-import-preview.png")); tap(text="取消")
    check(absent(2) and item(1).get("checked") == "false", "cancel import preview keeps list")
    open_backup(); tap(text="确认替换")
    check(item(1).get("checked") == "true" and item(2).get("text") == "Walk outside", "confirmed import restores exact exported state")
    restart(); check(item(1).get("checked") == "true" and item(2) is not None, "import survives restart")
    tap(text="撤销导入"); tap(text="确认撤销")
    check(absent(2) and item(1).get("checked") == "false", "undo survives restart and restores pre-import list")
    restart(); check(absent(2) and item(1).get("checked") == "false", "undo persists across restart")
    open_backup(); tap(text="确认替换"); tap(**{"content-desc": "todo-1"})
    check(find(text="撤销导入").get("enabled") == "false", "new mutation invalidates old undo snapshot")
    tap(**{"content-desc": "todo-1"}); shots.append(screenshot("03-tasks.png"))
    before = stored_state()
    paths = adb("shell", "find", "/storage/emulated/0", "-name", "PocketTodo-backup.ptodo").strip().splitlines()
    check(len(paths) == 1 and paths[0].startswith("/storage/emulated/0/"), "locate disposable exported backup fixture")
    corrupt = Path(os.environ["RUNNER_TEMP"]) / "corrupt.ptodo"; corrupt.write_bytes(b"broken backup\n")
    adb("push", str(corrupt), paths[0])
    tap(text="导入备份"); select_backup_file()
    find(text="导入失败：文件无效或无法读取，列表未更改")
    check(stored_state() == before and item(1).get("checked") == "true" and item(2).get("text") == "Walk outside", "corrupt file through real picker leaves exact persisted state unchanged")
    restart(); check(stored_state() == before, "rejected import remains unchanged after restart")
    tap(text="已完成"); check(item(1).get("checked") == "true" and absent(2), "completed view after backup roundtrip")
    shots.append(screenshot("04-completed.png"))
    start(OLD); check(item(1).get("text") == "Keep old data" and item(1).get("checked") == "false", "original APK coexists and keeps original data")
    check(len({x["sha256"] for x in shots}) == len(shots), "real screenshots show distinct states")
    return {"status": "PASS", "checks": checks, "count": len(checks), "screenshots": shots,
            "device": adb("shell", "getprop", "ro.product.model").strip(), "api": adb("shell", "getprop", "ro.build.version.sdk").strip(),
            "physical_device": "NOT_TESTED", "release_upgrade": "NOT_TESTED", "provider_failure_injection": "NOT_TESTED"}

try:
    result = main()
except Exception as exc:
    result = {"status": "FAIL", "checks": checks, "error": repr(exc), "physical_device": "NOT_TESTED"}
    OUT.mkdir(exist_ok=True)
    try: screenshot("failure.png")
    except Exception: pass
    (OUT / "ui-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    raise
else:
    (OUT / "ui-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print("UI_RESULT " + json.dumps(result, ensure_ascii=False))
