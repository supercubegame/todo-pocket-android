#!/usr/bin/env python3
"""Synthetic native multi-note export. No receiver, OCR, real photos or LMK claim."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile

SCOPE = "NATIVE_TWO_NOTE_TEXT_SAF_NOT_OCR_RECEIVER_OR_PROCESS_LOSS"
FORMATS = (("MARKDOWN", "Markdown图片包", "PocketTodo-notes.zip"),
           ("PDF", "PDF", "PocketTodo-notes.pdf"),
           ("PNG_ZIP", "分段PNG图片包", "PocketTodo-pages.zip"))
STEPS = ["ui_created_second_note", "empty_note_selection_blocked",
         "note_cancel_preserves_state", "content_cancel_preserves_state"]
PER_FORMAT = ["explicit_reverse_clicks_private_excluded", "empty_content_blocked",
              "unchecked_save_blocked", "picker_cancel_preserves_state", "saved_and_independently_read",
              "all_tables_media_unchanged"]
LABELS = STEPS + [step + "_" + kind for kind, _, _ in FORMATS for step in PER_FORMAT]
EXPECTED = "# Pocket Todo\n\nSecond edited\n\nBatchsecond\n\n"


def markdown_check(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.namelist() == ["notes.md"], "batch ZIP membership"
        assert z.getinfo("notes.md").file_size == len(EXPECTED.encode())
        assert z.read("notes.md").decode("utf-8") == EXPECTED, "batch text/order/privacy"


def pdf_text_check(text):
    assert "".join(text.split()) == "SecondeditedBatchsecond", "batch PDF text/order/privacy"


def cancel_readback_check(before_paths, after_paths, filename, baseline, actual):
    # Download directory membership, not arbitrary-provider atomicity or file-content proof.
    assert "/sdcard/Download/"+filename not in before_paths, "cancel target already exists"
    assert after_paths == before_paths, "cancel changed Download file membership"
    assert actual == baseline, "cancel changed database or private media"


def receipt(value, api, source, run, apk):
    if not isinstance(value, dict):
        return False
    if not (value.get("status") == "PASS" and value.get("scope") == SCOPE and
            type(value.get("api")) is int and value["api"] == api and
            value.get("commit") == source and value.get("run_id") == run and
            isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) and
            value.get("apk_sha256") == apk and value.get("labels") == LABELS and
            type(value.get("checks")) is int and value["checks"] == len(LABELS) and
            value.get("release_ready") is False):
        return False
    outputs = value.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != {x[0] for x in FORMATS}:
        return False
    for kind, _, _ in FORMATS:
        o = outputs[kind]
        if not isinstance(o, dict):
            return False
        if not (type(o.get("bytes")) is int and 0 < o["bytes"] <= 16777216 and
                isinstance(o.get("sha256"), str) and re.fullmatch("[0-9a-f]{64}", o["sha256"]) and
                o.get("state") == "ALL_TABLES_AND_ALL_MEDIA_UNCHANGED" and
                o.get("observer") == ("EXACT_MEMBERS_UTF8" if kind == "MARKDOWN" else
                                     "EXACT_PDF_TEXT" if kind == "PDF" else "TWO_TEXT_BANDS_NOT_OCR")):
            return False
    return True


PAGE_CHECK = r'''
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.io.File;
public class BatchPageCheck {
 static void check(BufferedImage p) {
  if(p==null||p.getWidth()!=595||p.getHeight()!=842)throw new AssertionError("dimensions");
  boolean[] rows=new boolean[842];
  for(int y=0;y<842;y++)for(int x=0;x<595;x++){
   int v=p.getRGB(x,y);
   if(v!=0xffffffff){
    if((v>>>24)!=255||x<36||x>=260||y<36||y>=130)throw new AssertionError("outside text region");
    rows[y]=true;
   }
  }
  int bands=0;boolean before=false;
  for(boolean row:rows){if(row&&!before)bands++;before=row;}
  if(bands!=2)throw new AssertionError("exactly two text bands");
 }
 static BufferedImage blank(){
  BufferedImage p=new BufferedImage(595,842,2);
  for(int y=0;y<842;y++)for(int x=0;x<595;x++)p.setRGB(x,y,0xffffffff);
  return p;
 }
 public static void main(String[] args)throws Exception{
  if(args[0].equals("--selftest")){
   BufferedImage good=blank();good.setRGB(40,42,0xff000000);good.setRGB(40,82,0xff000000);check(good);
   for(int mode=0;mode<5;mode++){
    BufferedImage bad=blank();
    if(mode>0)bad.setRGB(40,42,0xff000000);
    if(mode>1)bad.setRGB(40,82,0xff000000);
    if(mode==2)bad.setRGB(40,102,0xff000000);
    if(mode==3)bad.setRGB(300,200,0xff000000);
    if(mode==4)bad.setRGB(40,42,0x80000000);
    try{check(bad);}catch(AssertionError expected){continue;}
    throw new AssertionError("negative pixel control survived "+mode);
   }
   System.out.println("BATCH_PAGE_CONTROLS 1 positive 5 negatives");return;
  }
  check(ImageIO.read(new File(args[0])));System.out.println("BATCH_PAGE_PASS");
 }
}
'''


def selftest():
    assert len(LABELS) == 22 and all("picker_cancel_preserves_state_"+kind in LABELS
                                   for kind in ("MARKDOWN", "PDF", "PNG_ZIP"))
    paths = ["/sdcard/Download/existing.zip"]
    baseline = ({"notes": [(1, "public")], "meta": [(9,)]}, {"asset": "digest"}, {1: "title"})
    cancel_readback_check(paths, paths[:], "new.zip", baseline, copy.deepcopy(baseline))
    changed_db = copy.deepcopy(baseline); changed_db[0]["notes"] = [(1, "private")]
    changed_revision = copy.deepcopy(baseline); changed_revision[0]["meta"] = [(10,)]
    changed_media = copy.deepcopy(baseline); changed_media[1]["asset"] = "different"
    cancel_bad = [
        (paths, paths, "existing.zip", baseline),
        (paths, paths+["/sdcard/Download/new.zip"], "new.zip", baseline),
        (paths, [], "new.zip", baseline),
        (paths, paths+["/sdcard/Download/unexpected.zip"], "new.zip", baseline),
        (paths, paths, "new.zip", changed_db),
        (paths, paths, "new.zip", changed_revision),
        (paths, paths, "new.zip", changed_media),
    ]
    for before, after, filename, actual in cancel_bad:
        try:
            cancel_readback_check(before, after, filename, baseline, actual)
        except AssertionError:
            continue
        raise AssertionError("batch cancellation negative survived")
    # The format button starts abbreviated, but preview/status use full titles.
    # These explicit expectations are independent of the product constant.
    assert FORMATS == (("MARKDOWN", "Markdown图片包", "PocketTodo-notes.zip"),
                       ("PDF", "PDF", "PocketTodo-notes.pdf"),
                       ("PNG_ZIP", "分段PNG图片包", "PocketTodo-pages.zip"))
    assert [title+"预览" for _, title, _ in FORMATS] == [
        "Markdown图片包预览", "PDF预览", "分段PNG图片包预览"]
    assert [title+"已保存，逐字节回读一致" for _, title, _ in FORMATS] == [
        "Markdown图片包已保存，逐字节回读一致", "PDF已保存，逐字节回读一致",
        "分段PNG图片包已保存，逐字节回读一致"]
    def archive(text, extra=False):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("notes.md", text)
            if extra:
                z.writestr("assets/original.png", b"forbidden")
        return out.getvalue()
    markdown_check(archive(EXPECTED))
    pdf_text_check("Second edited\n\nBatchsecond\n\f")
    negatives = [
        lambda: markdown_check(archive(EXPECTED, True)),
        lambda: markdown_check(archive(EXPECTED.replace("Second edited\n\nBatchsecond", "Batchsecond\n\nSecond edited"))),
        lambda: markdown_check(archive(EXPECTED + "PRIVATE_SHARE_SENTINEL")),
        lambda: markdown_check(archive(EXPECTED.replace("Batchsecond\n\n", ""))),
        lambda: pdf_text_check("Batchsecond Second edited"),
        lambda: pdf_text_check("Second edited"),
        lambda: pdf_text_check("Second edited Batchsecond Batchunselected"),
    ]
    for action in negatives:
        try:
            action()
        except AssertionError:
            continue
        raise AssertionError("batch output negative survived")
    good = {"status": "PASS", "scope": SCOPE, "api": 26, "commit": "source", "run_id": "run",
            "apk_sha256": "a"*64, "labels": LABELS[:], "checks": len(LABELS),
            "release_ready": False, "outputs": {}}
    for kind, _, _ in FORMATS:
        good["outputs"][kind] = {"bytes": 100, "sha256": "b"*64,
            "state": "ALL_TABLES_AND_ALL_MEDIA_UNCHANGED",
            "observer": "EXACT_MEMBERS_UTF8" if kind == "MARKDOWN" else
                        "EXACT_PDF_TEXT" if kind == "PDF" else "TWO_TEXT_BANDS_NOT_OCR"}
    assert receipt(good, 26, "source", "run", "a"*64)
    bads = [None, {}, dict(good, status="FAIL"), dict(good, api=True), dict(good, api=34),
            dict(good, commit="old"), dict(good, run_id="old"), dict(good, apk_sha256="c"*64),
            dict(good, checks=True), dict(good, release_ready=True), dict(good, scope="backend")]
    for i in range(len(LABELS)):
        b = copy.deepcopy(good); b["labels"].pop(i); b["checks"] -= 1; bads.append(b)
    for kind, _, _ in FORMATS:
        b = copy.deepcopy(good); del b["outputs"][kind]; bads.append(b)
        for key, value in (("bytes", True), ("bytes", 0), ("sha256", "bad"),
                           ("state", "NOT_VERIFIED"), ("observer", "NONBLANK")):
            b = copy.deepcopy(good); b["outputs"][kind][key] = value; bads.append(b)
    for b in bads:
        assert not receipt(b, 26, "source", "run", "a"*64), "batch incomplete receipt accepted"
    # Execute the real composition, not a source substring check.
    from types import SimpleNamespace
    global native
    actual_native = native
    events = []
    try:
        native = lambda adb, gate: events.append(("batch", adb))
        gate = SimpleNamespace(verify_native_ui=lambda adb: events.append(("old", adb)))
        install(gate); gate.verify_native_ui("device")
        assert events == [("old", "device"), ("batch", "device")]
        sentinel = RuntimeError("old suite failed")
        def failed(adb): raise sentinel
        gate = SimpleNamespace(verify_native_ui=failed); install(gate)
        try: gate.verify_native_ui("device")
        except RuntimeError as exc: assert exc is sentinel
        else: raise AssertionError("old suite failure swallowed")
        assert events == [("old", "device"), ("batch", "device")]
    finally:
        native = actual_native
    print("BATCH_HOST_CONTROLS outputs=2_positive_7_negative receipts=1_positive_" +
          str(len(bads)) + "_negative composition=2 format_contracts=3 cancel=1_positive_7_negative HOST_ONLY", flush=True)


def native(adb, gate):
    """All fixture writes use visible app UI. State snapshots are read-only."""
    from verify_paged_exports import format_button
    from verify_process_control import stop_verified
    from verify_schema3 import cancel_share_picker
    source, run_id = os.environ["GITHUB_SHA"], os.environ["GITHUB_RUN_ID"]
    out = Path("native-ui"); prefix = [str(adb), "-s", gate.SERIAL]; serial = 0
    result = {"status": "FAIL", "scope": SCOPE, "commit": source, "run_id": run_id,
              "api": gate.API, "labels": [], "checks": 0, "outputs": {}, "release_ready": False}
    def command(*args, binary=False):
        return subprocess.check_output(prefix + list(args), text=not binary, stderr=subprocess.PIPE,
                                       stdin=subprocess.DEVNULL, timeout=40)
    def shell(*args): return command("shell", "-n", "-T", *args)
    def nodes():
        shell("uiautomator", "dump", "/sdcard/batch-window.xml")
        return list(ET.fromstring(shell("cat", "/sdcard/batch-window.xml")).iter("node"))
    def find(**attrs):
        deadline = time.monotonic() + 20; current = []
        while time.monotonic() < deadline:
            current = nodes()
            found = [n for n in current if all(n.get(k) == v for k, v in attrs.items())]
            assert len(found) <= 1, "ambiguous batch control " + repr(attrs)
            if found: return found[0]
            time.sleep(.25)
        raise AssertionError("batch control missing " + repr(attrs) + " actual=" + repr([n.attrib for n in current]))
    def click(n):
        assert n.get("enabled") == "true"
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
        assert x2 > x1 and y2 > y1
        shell("input", "tap", str((x1+x2)//2), str((y1+y2)//2))
    def tap(text): click(find(text=text))
    def touch(desc): click(find(**{"content-desc": desc}))
    def ready(): find(**{"content-desc": "v12-status", "text": "已保存到本机"})
    def stop(): stop_verified(adb, gate.SERIAL, gate.PKG)
    def start():
        shell("am", "start", "-W", "-n", gate.PKG + "/com.supercubegame.pockettodo.MainActivity"); ready()
    def state():
        nonlocal serial
        serial += 1; local = out / ("batch-state-" + str(serial) + ".db")
        local.write_bytes(command("exec-out", "run-as", gate.PKG, "cat", "databases/pocket-v12.db", binary=True))
        if "pocket-v12.db-wal" in shell("run-as", gate.PKG, "ls", "databases").splitlines():
            Path(str(local)+"-wal").write_bytes(command("exec-out", "run-as", gate.PKG, "cat", "databases/pocket-v12.db-wal", binary=True))
        with sqlite3.connect(local) as db:
            tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            data = {t: db.execute('SELECT * FROM "'+t+'" ORDER BY rowid').fetchall() for t in tables}
            titles = dict(db.execute("SELECT id,title FROM activities"))
        media = {}
        for name in shell("run-as", gate.PKG, "ls", "files/media").splitlines():
            assert re.fullmatch("[0-9a-f]{64}", name)
            raw = command("exec-out", "run-as", gate.PKG, "cat", "files/media/"+name, binary=True)
            media[name] = hashlib.sha256(raw).hexdigest(); assert media[name] == name
        return data, media, titles
    def ok(label):
        assert LABELS[len(result["labels"])] == label, "batch obligation order"
        result["labels"].append(label)
    def checked():
        return [n for n in nodes() if n.get("class") == "android.widget.CheckedTextView"]
    def open_notes():
        tap("导出笔记"); tap("批量选择"); find(text="勾选笔记（下一步逐项选择内容）")
        assert checked() and all(n.get("checked") == "false" for n in checked())
    def select_notes():
        # Deliberately reverse click order. The output must retain document order.
        tap(note_labels[1]); tap(note_labels[0]); tap("选择内容")
        find(text="勾选内容（私有项已排除）")
        c = checked()
        assert [n.get("text") for n in c] == block_labels
        assert all(n.get("checked") == "false" for n in c)
    def consent():
        for _ in range(8):
            c = [n for n in nodes() if n.get("text") == "我已核对内容与图片，可保存此包"]
            if c:
                assert len(c) == 1 and c[0].get("checked") == "false"
                click(c[0]); return
            shell("input", "swipe", "160", "440", "160", "190", "350")
        raise AssertionError("batch consent unreachable")
    def downloads():
        return sorted(shell("find", "/sdcard/Download", "-type", "f").splitlines())
    try:
        assert os.environ.get("GITHUB_ACTIONS") == "true" and shell("getprop", "ro.kernel.qemu").strip() == "1"
        prior = json.loads((out/"native-result.json").read_text())
        assert prior["status"] == "PASS" and prior["paged_ui"]["status"] == "PASS"
        apks = list(Path("build/outputs/apk/debug").glob("*.apk")); assert len(apks) == 1
        product = apks[0].read_bytes(); result["apk_sha256"] = hashlib.sha256(product).hexdigest()
        installed = shell("pm", "path", gate.PKG).strip()
        assert installed.startswith("package:") and "\n" not in installed
        assert command("exec-out", "cat", installed[8:], binary=True) == product
        stop(); before = state()
        derivatives = [r for r in before[0]["blocks"] if r[8] is not None]; assert len(derivatives) == 1
        first = derivatives[0][0]
        assert any(r[0] == first and r[7] == 1 and r[6] == "PRIVATE_SHARE_SENTINEL" for r in before[0]["blocks"])
        assert not any(r[2] == "Batchnote" for r in before[0]["notes"])
        start(); tap("活动"); ready()
        adds = [n for n in nodes() if n.get("content-desc", "").startswith("category-add-")]
        assert adds; click(adds[0]); touch("活动名称"); shell("input", "text", "Batchnote"); tap("保存"); ready()
        activity = find(text="Batchnote").get("content-desc"); assert re.fullmatch(r"activity-\d+", activity)
        touch(activity); ready(); tap("笔记"); ready()
        for text in ("Batchsecond", "Batchunselected"):
            tap("加入文字"); touch("文字内容"); shell("input", "text", text); tap("保存"); ready()
        stop(); baseline = state(); data, media, titles = baseline
        second_rows = [r for r in data["notes"] if r[2] == "Batchnote"]; assert len(second_rows) == 1
        second = second_rows[0][0]
        assert [r[4] for r in data["blocks"] if r[0] == second] == ["Batchsecond", "Batchunselected"]
        assert media == before[1] and len(data["notes"]) == len(before[0]["notes"]) + 1
        note_labels = [next(str(i+1)+". "+titles[r[1]]+" / "+r[2] for i, r in enumerate(data["notes"]) if r[0] == n)
                       for n in (first, second)]
        selected = [r for n in (first, second) for r in sorted(data["blocks"], key=lambda r: r[2]) if r[0] == n and r[7] == 0]
        assert len(selected) == 4 and [r[4] for r in selected if r[3] == "TEXT"] == ["Second edited", "Batchsecond", "Batchunselected"]
        owners = {r[0]: titles[r[1]]+" / "+r[2] for r in data["notes"]}
        block_labels = [str(i+1)+". ["+owners[r[0]]+"] "+("文字："+r[4] if r[3] == "TEXT" else "图片："+r[6])
                        for i, r in enumerate(selected)]
        chosen = [block_labels[i] for i, r in enumerate(selected) if r[3] == "TEXT" and r[4] in ("Second edited", "Batchsecond")]
        assert len(chosen) == 2
        ok("ui_created_second_note")
        start(); open_notes(); tap("选择内容"); find(text="勾选笔记（下一步逐项选择内容）")
        assert all(n.get("checked") == "false" for n in checked()); ok("empty_note_selection_blocked")
        tap("取消"); stop(); assert state() == baseline; ok("note_cancel_preserves_state")
        start(); open_notes(); select_notes(); tap("取消"); stop()
        assert state() == baseline; ok("content_cancel_preserves_state")
        java = out/"BatchPageCheck.java"; java.write_text(PAGE_CHECK)
        subprocess.run(["javac", "-d", str(out), str(java)], check=True, timeout=40)
        subprocess.run(["java", "-Djava.awt.headless=true", "-cp", str(out), "BatchPageCheck", "--selftest"], check=True, timeout=40)
        for kind, title, filename in FORMATS:
            old = shell("find", "/sdcard/Download", "-type", "f", "-name", filename).splitlines()
            if old:
                assert old == ["/sdcard/Download/"+filename]
                destination = "/sdcard/Download/pre-batch-"+filename
                assert not shell("find", "/sdcard/Download", "-type", "f", "-name", "pre-batch-"+filename).splitlines()
                shell("mv", old[0], destination)
            before_downloads = downloads()
            start(); open_notes(); select_notes(); ok("explicit_reverse_clicks_private_excluded_"+kind)
            tap("生成预览"); find(text="勾选内容（私有项已排除）")
            assert all(n.get("checked") == "false" for n in checked()); ok("empty_content_blocked_"+kind)
            if kind != "MARKDOWN":
                button = format_button(nodes(), "Markdown", gate.PKG); assert button is not None
                click(button); tap(title)
            tap(chosen[1]); tap(chosen[0]); tap("生成预览"); find(text=title+"预览")
            tap("选择保存位置"); find(text=title+"预览")
            assert not any("documentsui" in n.get("package", "") for n in nodes())
            ok("unchecked_save_blocked_"+kind); consent(); tap("选择保存位置")
            assert find(text=filename).get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            assert find(text="SAVE").get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            trace = []
            result.setdefault("cancel_traces", {})[kind] = trace
            cancel_share_picker(nodes, lambda: shell("input", "keyevent", "KEYCODE_BACK"), gate.PKG, trace)
            stop()
            cancel_readback_check(before_downloads, downloads(), filename, baseline, state())
            ok("picker_cancel_preserves_state_"+kind)
            # Cancellation consumes the old preview. Generate and consent afresh.
            start(); open_notes(); select_notes()
            if kind != "MARKDOWN":
                button = format_button(nodes(), "Markdown", gate.PKG); assert button is not None
                click(button); tap(title)
            tap(chosen[1]); tap(chosen[0]); tap("生成预览"); find(text=title+"预览")
            consent(); tap("选择保存位置")
            assert find(text=filename).get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            assert find(text="SAVE").get("package") in ("com.android.documentsui", "com.google.android.documentsui")
            tap("SAVE"); find(**{"content-desc": "v12-status", "text": title+"已保存，逐字节回读一致"})
            assert shell("find", "/sdcard/Download", "-type", "f", "-name", filename).splitlines() == ["/sdcard/Download/"+filename]
            raw = command("exec-out", "cat", "/sdcard/Download/"+filename, binary=True)
            assert 0 < len(raw) <= 16777216
            artifact = out/("batch-"+filename); artifact.write_bytes(raw)
            if kind == "MARKDOWN":
                markdown_check(raw)
            elif kind == "PDF":
                info = subprocess.check_output(["pdfinfo", str(artifact)], text=True, timeout=30)
                assert re.findall(r"^Pages:\s+(\d+)", info, re.M) == ["1"]
                textfile = out/"batch-pdf.txt"
                subprocess.run(["pdftotext", "-enc", "UTF-8", str(artifact), str(textfile)], check=True, timeout=30)
                pdf_text_check(textfile.read_text())
            else:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    assert z.namelist() == ["pages/page-001.png"]
                    assert z.getinfo("pages/page-001.png").file_size <= 16777216
                    page = out/"batch-page.png"; page.write_bytes(z.read("pages/page-001.png"))
                subprocess.run(["java", "-Djava.awt.headless=true", "-cp", str(out), "BatchPageCheck", str(page)], check=True, timeout=40)
            ok("saved_and_independently_read_"+kind)
            stop(); assert state() == baseline; ok("all_tables_media_unchanged_"+kind)
            result["outputs"][kind] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "state": "ALL_TABLES_AND_ALL_MEDIA_UNCHANGED",
                "observer": "EXACT_MEMBERS_UTF8" if kind == "MARKDOWN" else
                            "EXACT_PDF_TEXT" if kind == "PDF" else "TWO_TEXT_BANDS_NOT_OCR"}
        assert command("exec-out", "cat", installed[8:], binary=True) == product
        result.update(status="PASS", checks=len(result["labels"]))
        assert receipt(result, gate.API, source, run_id, result["apk_sha256"])
        return result
    except Exception as exc:
        from verify_schema3 import exception_evidence
        result.update(status="FAIL", error=repr(exc), original_failure=exception_evidence(exc))
        try:
            (out/"batch-failure.png").write_bytes(command("exec-out", "screencap", "-p", binary=True))
        except Exception as diagnostic:
            result["screenshot_error"] = repr(diagnostic)
        raise
    finally:
        result["checks"] = len(result["labels"])
        (out/"batch-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
        for filename in ("native-result.json", "codec-result.json"):
            path = out/filename
            parent = json.loads(path.read_text()); parent["batch_ui"] = result
            if result["status"] != "PASS": parent["status"] = "FAIL"
            path.write_text(json.dumps(parent, ensure_ascii=False, indent=2)+"\n")
        print("BATCH_NATIVE_RESULT "+json.dumps(result, ensure_ascii=False), flush=True)


def install(gate):
    previous = gate.verify_native_ui
    def previous_then_batch(adb):
        previous(adb)
        native(adb, gate)
    gate.verify_native_ui = previous_then_batch


if __name__ == "__main__":
    import sys
    assert sys.argv[1:] == ["selftest"], "usage: verify_batch_exports.py selftest"
    selftest()
