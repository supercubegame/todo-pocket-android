#!/usr/bin/env python3
"""Drive the real installed APK via Android UIAutomator hierarchy and adb input."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

PKG = "com.supercubegame.pockettodo"
OUT = Path("delivery")
checks = []

def adb(*args, binary=False):
    return subprocess.check_output(["adb", *args], timeout=40, text=not binary)

def tree():
    adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
    return ET.fromstring(adb("shell", "cat", "/sdcard/window.xml"))

def nodes():
    return list(tree().iter("node"))

def find(**attrs):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        for n in nodes():
            if all(n.get(k) == v for k, v in attrs.items()):
                return n
        time.sleep(0.3)
    raise AssertionError("UI node not found: " + repr(attrs))

def tap(**attrs):
    n = find(**attrs)
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
    adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))
    time.sleep(0.25)

def check(ok, name):
    if not ok: raise AssertionError(name)
    checks.append(name)
    print("PASS " + name, flush=True)

def item(id):
    return find(**{"content-desc": "todo-" + str(id)})

def add(title):
    tap(**{"content-desc": "新待办输入"})
    adb("shell", "input", "text", title.replace(" ", "%s"))
    tap(text="添加")

def screenshot(name):
    # Capture only after hierarchy assertions have confirmed the intended UI state.
    time.sleep(0.5)
    data = adb("exec-out", "screencap", "-p", binary=True)
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "invalid PNG"
    path = OUT / name
    path.write_bytes(data)
    return {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

def main():
    OUT.mkdir(exist_ok=True)
    check(adb("shell", "getprop", "ro.kernel.qemu").strip() == "1", "disposable emulator identity")
    adb("install", "-r", str(OUT / "PocketTodo-1.0-debug.apk"))
    adb("shell", "pm", "clear", PKG)
    adb("shell", "am", "start", "-W", "-n", PKG + "/.MainActivity")
    find(text="口袋待办")
    check(find(text="还剩 0 件  /  共 0 件") is not None, "fresh APK launches empty")
    shots = [screenshot("01-empty.png")]
    tap(text="添加")
    check(not any(n.get("content-desc", "").startswith("todo-") for n in nodes()), "blank input creates no task")
    add("Buy milk")
    check(item(1).get("text") == "Buy milk", "add via visible input")
    add("Walk outside")
    check(item(2).get("text") == "Walk outside", "second task distinct")
    tap(**{"content-desc": "todo-1"})
    check(item(1).get("checked") == "true", "complete via checkbox")
    tap(text="待办")
    check(not any(n.get("content-desc") == "todo-1" for n in nodes()) and item(2) is not None, "pending filter")
    tap(text="已完成")
    check(item(1).get("checked") == "true" and not any(n.get("content-desc") == "todo-2" for n in nodes()), "completed filter")
    tap(text="全部")
    adb("shell", "am", "force-stop", PKG)
    adb("shell", "am", "start", "-W", "-n", PKG + "/.MainActivity")
    check(item(1).get("checked") == "true" and item(2).get("text") == "Walk outside", "force-stop restart preserves titles and completion")
    tap(**{"content-desc": "todo-1"})
    check(item(1).get("checked") == "false", "uncomplete via checkbox")
    tap(**{"content-desc": "delete-2"})
    tap(text="取消")
    check(item(2) is not None, "cancel deletion preserves task")
    tap(**{"content-desc": "delete-2"})
    tap(text="删除")
    check(not any(n.get("content-desc") == "todo-2" for n in nodes()), "confirm deletes exact task")
    adb("shell", "am", "force-stop", PKG)
    adb("shell", "am", "start", "-W", "-n", PKG + "/.MainActivity")
    check(item(1).get("checked") == "false" and not any(n.get("content-desc") == "todo-2" for n in nodes()), "deletion and uncomplete persist across restart")
    add("Finish one small thing")
    add("Try Pocket Todo")
    tap(**{"content-desc": "todo-1"})
    find(text="还剩 2 件  /  共 3 件")
    shots.append(screenshot("02-tasks.png"))
    tap(text="已完成")
    check(item(1).get("checked") == "true", "completed screenshot state")
    shots.append(screenshot("03-completed.png"))
    check(len({x["sha256"] for x in shots}) == len(shots), "screenshots show distinct states")
    return {"status": "PASS", "checks": checks, "count": len(checks), "screenshots": shots,
            "device": adb("shell", "getprop", "ro.product.model").strip(),
            "api": adb("shell", "getprop", "ro.build.version.sdk").strip(), "physical_device": "NOT_TESTED"}

try:
    result = main()
except Exception as exc:
    result = {"status": "FAIL", "checks": checks, "error": repr(exc), "physical_device": "NOT_TESTED"}
    OUT.mkdir(exist_ok=True)
    (OUT / "ui-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    raise
else:
    (OUT / "ui-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print("UI_RESULT " + json.dumps(result, ensure_ascii=False))
