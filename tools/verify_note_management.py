#!/usr/bin/env python3
"""Independent rename contracts against the installed APK, not a Python model."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

SCOPE = "APK_NOTE_RENAME_BACKEND_SYNTHETIC_NOT_UI_OR_LMK"
LABELS = [
    "null_id", "blank_id", "missing_note", "wrong_owner", "zero_owner",
    "negative_owner", "null_expected", "null_title", "blank_title",
    "same_title_noop", "trimmed_noop", "target_only",
    "external_same_revision", "stale_refused", "stale_equal_new_refused",
    "field_link_preserved", "late_rollback", "reopen",
]


def observe(text, api, package):
    text = text.replace("\r\n", "\n")
    labels = re.findall(r"^NOTE_MANAGEMENT_PASS ([^\r\n]+)$", text, re.M)
    targets = re.findall(r"(?:^|stream=)NOTE_MANAGEMENT_TARGET (\S+) ([0-9]+) ([0-9]+)\r?$", text, re.M)
    result = re.findall(r"^NOTE_MANAGEMENT_RESULT ([^\r\n]+)$", text, re.M)
    finish = re.findall(r"^INSTRUMENTATION_CODE: (-?[0-9]+)\s*$", text, re.M)
    assert len(targets) == 1 and targets[0][0] == package
    assert int(targets[0][1]) >= 10000 and targets[0][2] == str(api)
    assert labels == LABELS and result == [str(len(LABELS))+" PASS"]
    assert finish == ["-1"] and "NOTE_MANAGEMENT_FAILED" not in text
    assert "INSTRUMENTATION_FAILED" not in text
    assert text.index("NOTE_MANAGEMENT_TARGET ") < text.index("NOTE_MANAGEMENT_PASS ")
    assert text.rindex("NOTE_MANAGEMENT_PASS ") < text.index("NOTE_MANAGEMENT_RESULT ")
    assert text.index("NOTE_MANAGEMENT_RESULT ") < text.index("INSTRUMENTATION_CODE:")
    return labels


def accepted(value, api, source, run, apk):
    if not isinstance(value, dict):
        return False
    identity = value.get("instrumentation")
    if not isinstance(identity, dict):
        return False
    return (
        value.get("status") == "PASS" and value.get("scope") == SCOPE and
        type(value.get("api")) is int and value["api"] == api and
        value.get("commit") == source and value.get("run_id") == run and
        isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) is not None and
        value.get("apk_sha256") == apk and value.get("labels") == LABELS and
        type(value.get("checks")) is int and value["checks"] == len(LABELS) and
        value.get("release_ready") is False and
        value.get("live_state") == "ALL_TABLES_ALL_MEDIA_UNCHANGED" and
        identity.get("runtime") == "TARGET_APP_INSTRUMENTATION" and
        identity.get("product_apk_sha256") == apk and
        identity.get("installed_product_readback") == "EXACT_BEFORE_AND_AFTER" and
        identity.get("default_test_restored") == "EXACT_BYTES_AND_REGISTERED_RUNNER" and
        identity.get("diagnostic_failure_rejected") is True and
        isinstance(value.get("log"), str) and log_accepted(value["log"], api) and
        value.get("log_sha256") == hashlib.sha256(value["log"].encode()).hexdigest()
    )


def log_accepted(text, api):
    try:
        observe(text, api, "com.supercubegame.pockettodo.v12.preview")
        return True
    except (AssertionError, ValueError):
        return False


def aggregate(codec, native, api, source, run):
    """Called independently by schema3 report, even if the batch emitter disappears."""
    codec = codec if isinstance(codec, dict) else {}
    native = native if isinstance(native, dict) else {}
    c = codec.get("batch_ui"); n = native.get("batch_ui")
    c = c if isinstance(c, dict) else {}
    n = n if isinstance(n, dict) else {}
    value = c.get("note_management")
    passed = (
        codec.get("status") == native.get("status") == c.get("status") == n.get("status") == "PASS" and
        type(codec.get("api")) is int and codec["api"] == api and
        codec.get("commit") == source and codec.get("run_id") == run and
        codec.get("release_ready") is False and
        value == n.get("note_management") and
        accepted(value, api, source, run, codec.get("apk_sha256"))
    )
    return {"status": "PASS" if passed else "NOT_VERIFIED", "evidence": value,
            "scope": SCOPE, "release_ready": False}


def sample(api=26, source="source", run="run", apk="a"*64):
    # Report fixture only. Never used to emit Android acceptance.
    log = "NOTE_MANAGEMENT_TARGET com.supercubegame.pockettodo.v12.preview 10001 "+str(api)+"\n"
    log += "".join("NOTE_MANAGEMENT_PASS "+label+"\n" for label in LABELS)
    log += "NOTE_MANAGEMENT_RESULT "+str(len(LABELS))+" PASS\nINSTRUMENTATION_CODE: -1\n"
    return {"status": "PASS", "scope": SCOPE, "api": api, "commit": source,
            "run_id": run, "apk_sha256": apk, "labels": LABELS[:], "checks": len(LABELS),
            "release_ready": False, "live_state": "ALL_TABLES_ALL_MEDIA_UNCHANGED",
            "log": log, "log_sha256": hashlib.sha256(log.encode()).hexdigest(),
            "instrumentation": {"runtime": "TARGET_APP_INSTRUMENTATION",
                "product_apk_sha256": apk, "installed_product_readback": "EXACT_BEFORE_AND_AFTER",
                "default_test_restored": "EXACT_BYTES_AND_REGISTERED_RUNNER",
                "diagnostic_failure_rejected": True}}


def selftest():
    good = sample()
    def parents(value):
        batch = {"status": "PASS", "note_management": value}
        return ({"status": "PASS", "api": 26, "commit": "source", "run_id": "run",
                 "release_ready": False, "apk_sha256": "a"*64, "batch_ui": copy.deepcopy(batch)},
                {"status": "PASS", "batch_ui": copy.deepcopy(batch)})
    def valid(c, n):
        return aggregate(c, n, 26, "source", "run")["status"] == "PASS"
    assert accepted(good, 26, "source", "run", "a"*64)
    assert valid(*parents(good))
    bad = [None, [], {}]
    for key in good:
        value = copy.deepcopy(good); del value[key]; bad.append(value)
    for key, value in (("status", "FAIL"), ("api", True), ("api", 34),
            ("commit", "old"), ("run_id", "old"), ("apk_sha256", "b"*64),
            ("scope", "HOST_ONLY"), ("checks", True), ("release_ready", True),
            ("live_state", "NOT_VERIFIED"), ("log_sha256", "c"*64)):
        v = copy.deepcopy(good); v[key] = value; bad.append(v)
    for index in range(len(LABELS)):
        v = copy.deepcopy(good); del v["labels"][index]; v["checks"] -= 1
        bad.append(v)
    for key in good["instrumentation"]:
        v = copy.deepcopy(good); del v["instrumentation"][key]; bad.append(v)
    text = good["log"]
    logs = ["", text.replace("CODE: -1", "CODE: 0"),
            text + "NOTE_MANAGEMENT_FAILED\n", text + "INSTRUMENTATION_FAILED\n",
            text.replace("10001 26", "10001 34"), text.replace("10001 26", "9999 26"),
            text.replace(".preview 10001", ".wrong 10001"),
            text.replace("NOTE_MANAGEMENT_RESULT 18 PASS", "NOTE_MANAGEMENT_RESULT 17 PASS"),
            text + "NOTE_MANAGEMENT_RESULT 18 PASS\n",
            text.replace("NOTE_MANAGEMENT_PASS null_id\n", "") + "NOTE_MANAGEMENT_PASS null_id\n"]
    for label in LABELS:
        marker = "NOTE_MANAGEMENT_PASS "+label+"\n"
        logs.extend((text.replace(marker, ""), text.replace(marker, marker+marker)))
    for log in logs:
        v = copy.deepcopy(good); v["log"] = log
        v["log_sha256"] = hashlib.sha256(log.encode()).hexdigest(); bad.append(v)
    for value in bad:
        assert value != good
        assert not accepted(value, 26, "source", "run", "a"*64)
        assert not valid(*parents(value)), "self-consistent missing evidence accepted"
    parent_bad = []
    for side in (0, 1):
        for level in ("parent", "batch", "receipt"):
            pair = list(parents(good))
            if level == "parent": pair[side]["status"] = "FAIL"
            if level == "batch": pair[side]["batch_ui"]["status"] = "FAIL"
            if level == "receipt": del pair[side]["batch_ui"]["note_management"]
            parent_bad.append(pair)
    pair = list(parents(good)); del pair[0]["batch_ui"]; del pair[1]["batch_ui"]
    parent_bad.append(pair)
    for pair in parent_bad:
        assert not valid(*pair), "missing/failed parent accepted"
    result = {"positive": 2, "receipt_negative": len(bad), "parent_negative": len(parent_bad),
              "scope": "HOST_OBSERVERS_NOT_ANDROID_EXECUTION"}
    print("NOTE_MANAGEMENT_HOST "+json.dumps(result), flush=True)
    return result


JAVA = r'''
package ci.notes;
import android.app.Instrumentation;
import android.os.Bundle;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteConstraintException;
import com.supercubegame.pockettodo.AppDatabase;
import com.supercubegame.pockettodo.NoteDocument;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

public final class NoteManagementInstrumentation extends Instrumentation {
 private Bundle args;
 private int count;
 private Path asset;
 private byte[] assetBytes;
 interface Action {void run();}
 static void need(boolean value,String name){if(!value)throw new AssertionError(name);}
 void pass(String name){count++;System.out.println("NOTE_MANAGEMENT_PASS "+name);}
 static String hex(byte[] bytes){StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format(java.util.Locale.ROOT,"%02x",b&255));return out.toString();}
 static Map<String,List<List<String>>> state(AppDatabase helper){
  SQLiteDatabase db=helper.getReadableDatabase();
  Map<String,List<List<String>>> out=new TreeMap<>();
  try(Cursor tables=db.rawQuery("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",null)){
   while(tables.moveToNext()){
    String name=tables.getString(0);need(name.matches("[A-Za-z0-9_]+"),"table identity");
    List<List<String>> rows=new ArrayList<>();
    try(Cursor c=db.rawQuery("SELECT rowid,* FROM \""+name+"\" ORDER BY rowid",null)){
     rows.add(new ArrayList<>(Arrays.asList(c.getColumnNames())));
     while(c.moveToNext()){
      List<String> row=new ArrayList<>();
      for(int i=0;i<c.getColumnCount();i++){
       int type=c.getType(i);
       row.add(type==0?"N":type==4?"B"+hex(c.getBlob(i)):type+":"+c.getString(i));
      }rows.add(row);
     }
    }out.put(name,rows);
   }
  }need(out.containsKey("notes")&&out.containsKey("revision")&&out.containsKey("field_notes"),"fixture tables");
  return out;
 }
 static Map<String,List<List<String>>> expected(Map<String,List<List<String>>> before,String id,String title,boolean bump){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();for(List<String> row:e.getValue())rows.add(new ArrayList<>(row));out.put(e.getKey(),rows);
  }
  List<List<String>> notes=out.get("notes");int matches=0;
  need(notes.get(0).equals(Arrays.asList("rowid","id","activity_id","title")),"note layout");
  for(int i=1;i<notes.size();i++)if(notes.get(i).get(1).equals("3:"+id)){notes.get(i).set(3,"3:"+title);matches++;}
  need(matches==1,"exact expected note");
  List<List<String>> revision=out.get("revision");
  need(revision.size()==2&&revision.get(0).size()==3,"revision layout");
  if(bump){long old=Long.parseLong(revision.get(1).get(2).substring(2));revision.get(1).set(2,"1:"+Math.incrementExact(old));}
  return out;
 }
 void media()throws Exception{need(Arrays.equals(assetBytes,Files.readAllBytes(asset)),"synthetic media bytes changed");}
 void refused(AppDatabase helper,Class<? extends Throwable> type,Action action,String label)throws Exception{
  Map<String,List<List<String>>> before=state(helper);Throwable caught=null;
  try{action.run();}catch(Throwable failure){caught=failure;}
  need(caught!=null&&caught.getClass()==type,"wrong refusal "+label+" actual="+caught);
  need(state(helper).equals(before),"rejection changed full state "+label);media();pass(label);
 }
 void verify()throws Exception{
  Context context=getTargetContext();
  String name="ci-note-management-"+args.getString("nonce")+".db";
  need(!context.getDatabasePath(name).exists(),"refuse reuse of fixture database");
  Path folder=new File(context.getCacheDir(),"note-management-"+args.getString("nonce")).toPath();
  Files.createDirectory(folder);asset=folder.resolve("synthetic.png");
  assetBytes=android.util.Base64.decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",android.util.Base64.DEFAULT);
  Files.write(asset,assetBytes,StandardOpenOption.CREATE_NEW);
  String digest=hex(MessageDigest.getInstance("SHA-256").digest(assetBytes));
  Map<String,List<List<String>>> finalState;
  try(AppDatabase h=AppDatabase.openSchema3(context,name)){
   h.addCategory(1,"Notes");h.addActivity(1,1,0,"First");h.addActivity(2,1,0,"Other");
   h.createNote("first",1,"Same");h.createNote("second",1,"Same");h.createNote("other",2,"Same");
   h.defineField("field","Field","LONG_TEXT",Collections.emptyList());
   h.createFieldNote("linked",1,"field","Same");h.putField(1,"field",Collections.singletonList("Field value"));
   h.addTodo("todo","Unrelated");h.registerMedia(digest,"image/png",assetBytes.length);
   h.saveNote("second",Arrays.asList(NoteDocument.Block.text("text","Private sentinel",true),NoteDocument.Block.image("image",digest,"caption",false)));
   h.saveNote("first",Collections.singletonList(NoteDocument.Block.image("image",digest,"shared",true)));
   h.saveNote("linked",Collections.singletonList(NoteDocument.Block.text("linked-text","Linked value",false)));
   h.exportState();
   refused(h,IllegalArgumentException.class,()->h.renameNote(null,1,"Same","New"),"null_id");
   refused(h,IllegalArgumentException.class,()->h.renameNote("",1,"Same","New"),"blank_id");
   refused(h,IllegalArgumentException.class,()->h.renameNote("missing",1,"Same","New"),"missing_note");
   refused(h,IllegalArgumentException.class,()->h.renameNote("second",2,"Same","New"),"wrong_owner");
   refused(h,IllegalArgumentException.class,()->h.renameNote("second",0,"Same","New"),"zero_owner");
   refused(h,IllegalArgumentException.class,()->h.renameNote("second",-1,"Same","New"),"negative_owner");
   refused(h,IllegalArgumentException.class,()->h.renameNote("second",1,null,"New"),"null_expected");
   refused(h,IllegalArgumentException.class,()->h.renameNote("second",1,"Same",null),"null_title");
   refused(h,IllegalArgumentException.class,()->h.renameNote("second",1,"Same"," \t\n"),"blank_title");
   Map<String,List<List<String>>> before=state(h);
   need(!h.renameNote("second",1,"Same","Same")&&state(h).equals(before),"same title write");media();pass("same_title_noop");
   need(!h.renameNote("second",1,"Same"," \tSame\n")&&state(h).equals(before),"trim no-op write");media();pass("trimmed_noop");
   need(h.renameNote("second",1,"Same"," Renamed "),"rename return");
   need(state(h).equals(expected(before,"second","Renamed",true)),"wrong identity, order, content or revision");media();pass("target_only");
   before=state(h);
   try(SQLiteDatabase external=SQLiteDatabase.openDatabase(context.getDatabasePath(name).getPath(),null,SQLiteDatabase.OPEN_READWRITE)){
    external.execSQL("UPDATE notes SET title='External' WHERE id='second'");
   }
   need(state(h).equals(expected(before,"second","External",false)),"external writer not exact same-revision");media();pass("external_same_revision");
   refused(h,IllegalStateException.class,()->h.renameNote("second",1,"Renamed","Fresh"),"stale_refused");
   refused(h,IllegalStateException.class,()->h.renameNote("second",1,"Renamed","External"),"stale_equal_new_refused");
   before=state(h);need(h.renameNote("linked",1,"Same","Linked renamed"),"linked rename return");
   need(state(h).equals(expected(before,"linked","Linked renamed",true))&&h.fieldNoteIds(1,"field").equals(Collections.singletonList("linked")),"field association changed");media();pass("field_link_preserved");
   SQLiteDatabase db=h.getWritableDatabase();
   db.execSQL("CREATE TRIGGER ci_note_late BEFORE UPDATE OF value ON revision WHEN (SELECT title FROM notes WHERE id='second')='Fault' BEGIN SELECT RAISE(ABORT,'note_rename_late_fault'); END");
   before=state(h);Throwable caught=null;
   try{h.renameNote("second",1,"External","Fault");}catch(Throwable failure){caught=failure;}
   finally{db.execSQL("DROP TRIGGER ci_note_late");}
   need(caught instanceof IllegalArgumentException&&caught.getCause() instanceof SQLiteConstraintException&&caught.getCause().getMessage().contains("note_rename_late_fault"),"late SQL barrier not reached "+caught);
   need(state(h).equals(before),"late title/revision rollback incomplete");media();pass("late_rollback");
   finalState=state(h);h.exportState();
  }
  try(AppDatabase reopened=AppDatabase.openSchema3(context,name)){
   need(state(reopened).equals(finalState),"helper reopen state differs");media();pass("reopen");
  }
 }
 @Override public void onCreate(Bundle value){super.onCreate(value);args=value;start();}
 @Override public void onStart(){
  ByteArrayOutputStream bytes=new ByteArrayOutputStream();PrintStream oldOut=System.out,oldErr=System.err;int code=0;
  try{
   PrintStream log=new PrintStream(bytes,true,"UTF-8");System.setOut(log);System.setErr(log);
   need(getTargetContext().getPackageName().equals(args.getString("expectedPackage"))&&android.os.Process.myUid()==getTargetContext().getApplicationInfo().uid,"target identity");
   need(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"actual API");
   need(android.os.Build.HARDWARE.equals("ranchu")||android.os.Build.HARDWARE.equals("goldfish"),"CI emulator only");
   System.out.println("NOTE_MANAGEMENT_TARGET "+getTargetContext().getPackageName()+" "+android.os.Process.myUid()+" "+android.os.Build.VERSION.SDK_INT);
   if("diagnostic".equals(args.getString("mode")))throw new AssertionError("note_management_diagnostic_sentinel");
   verify();need(count==18,"contract count");System.out.println("NOTE_MANAGEMENT_RESULT "+count+" PASS");code=-1;
  }catch(Throwable failure){System.err.println("NOTE_MANAGEMENT_FAILED");failure.printStackTrace(System.err);}
  finally{
   System.out.flush();System.err.flush();System.setOut(oldOut);System.setErr(oldErr);Bundle result=new Bundle();
   try{result.putString("stream",bytes.toString("UTF-8"));}catch(Exception failure){throw new RuntimeException(failure);}
   finish(code,result);
  }
 }
}
'''


def native(adb, gate, snapshot):
    from verify_paged_exports import debug_key
    from verify_schema3 import certificate, require_registration, exception_evidence
    from verify_process_control import stop_verified
    root = Path(__file__).resolve().parents[1]
    out = Path("native-ui"); out.mkdir(exist_ok=True)
    prefix = [str(adb), "-s", gate.SERIAL]
    result = {"status": "FAIL", "scope": SCOPE, "api": gate.API,
              "commit": os.environ["GITHUB_SHA"], "run_id": os.environ["GITHUB_RUN_ID"],
              "release_ready": False, "labels": [], "checks": 0}
    def command(args, timeout=40, binary=False):
        p = subprocess.run([str(x) for x in args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           stdin=subprocess.DEVNULL, text=not binary, timeout=timeout)
        p.check_returncode()
        return p.stdout if binary else p.stdout+"\n"+p.stderr
    def installed():
        rows = re.findall(r"^package:(\S+)\s*$", command(prefix+["shell", "-n", "-T", "pm", "path", gate.PKG]), re.M)
        assert len(rows) == 1
        return command(prefix+["exec-out", "cat", rows[0]], binary=True)
    try:
        assert os.environ.get("GITHUB_ACTIONS") == "true"
        stop_verified(adb, gate.SERIAL, gate.PKG)
        live_before = snapshot()
        apps = list((root/"build/outputs/apk/debug").glob("*.apk"))
        tests = list((root/"build/outputs/apk/androidTest/debug").glob("*.apk"))
        assert len(apps) == len(tests) == 1
        app, test = apps[0], tests[0]
        product, saved = app.read_bytes(), test.read_bytes()
        assert installed() == product
        digest = hashlib.sha256(product).hexdigest()
        cert = certificate(app, gate); assert certificate(test, gate) == cert
        key = debug_key(cert)
        require_registration(adb, gate, "notes-before", "V12DeviceTest")
        with tempfile.TemporaryDirectory(prefix="notes-runner-", dir=root/"build") as directory:
            folder = Path(directory); src = folder/"src"; src.mkdir()
            (src/"NoteManagementInstrumentation.java").write_text(JAVA, encoding="utf-8")
            init = folder/"runner.gradle"
            init.write_text("gradle.beforeProject { p ->\n p.plugins.withId('com.android.application') {\n"
                " p.androidComponents.finalizeDsl { dsl ->\n"
                " dsl.defaultConfig.testInstrumentationRunner = 'ci.notes.NoteManagementInstrumentation'\n"
                " dsl.sourceSets.getByName('androidTest').java.srcDir "+json.dumps(str(src))+"\n"
                " dsl.signingConfigs.getByName('debug').storeFile = new File("+json.dumps(str(key))+")\n"
                " }\n }\n}\n")
            backup = folder/"default-test.apk"; backup.write_bytes(saved)
            try:
                log = command(["gradle", "--no-daemon", "--console=plain", "-I", init, "assembleDebugAndroidTest"], 300)
                (out/"note-management-build.log").write_text(log)
                assert app.read_bytes() == product and certificate(test, gate) == cert
                command(prefix+["install", "-r", "-t", test], 120)
                registration = command(prefix+["shell", "-n", "-T", "pm", "list", "instrumentation"])
                rows = re.findall(r"^instrumentation:(\S+) \(target=([^)]+)\)\s*$", registration, re.M)
                component = gate.PKG+".test/ci.notes.NoteManagementInstrumentation"
                assert [r for r in rows if r[0].startswith(gate.PKG+".test/")] == [(component, gate.PKG)]
                nonce = result["run_id"]+"-"+os.environ.get("GITHUB_RUN_ATTEMPT", "1")+"-"+str(gate.API)
                assert re.fullmatch("[0-9]+-[0-9]+-(26|34)", nonce)
                args = prefix+["shell", "-n", "-T", "am", "instrument", "-w", "-r",
                               "-e", "expectedPackage", gate.PKG, "-e", "expectedApi", str(gate.API),
                               "-e", "nonce", nonce]
                diagnostic = command(args+["-e", "mode", "diagnostic", component], 60)
                (out/"note-management-diagnostic.log").write_text(diagnostic)
                assert "java.lang.AssertionError: note_management_diagnostic_sentinel" in diagnostic
                assert "NOTE_MANAGEMENT_FAILED" in diagnostic and "INSTRUMENTATION_CODE: 0" in diagnostic
                assert not log_accepted(diagnostic, gate.API)
                text = command(args+[component], 180)
                (out/"note-management-device.log").write_text(text)
                result.update(log=text, log_sha256=hashlib.sha256(text.encode()).hexdigest())
                result["labels"] = observe(text, gate.API, gate.PKG)
                assert installed() == product
            finally:
                assert backup.read_bytes() == saved
                command(prefix+["install", "-r", "-t", backup], 120)
                test.write_bytes(saved)
                require_registration(adb, gate, "notes-restored", "V12DeviceTest")
                assert app.read_bytes() == product and test.read_bytes() == saved and installed() == product
        stop_verified(adb, gate.SERIAL, gate.PKG)
        assert snapshot() == live_before, "note management instrumentation changed live tables/media"
        result.update(status="PASS", checks=len(result["labels"]), apk_sha256=digest,
            live_state="ALL_TABLES_ALL_MEDIA_UNCHANGED", instrumentation={
                "runtime": "TARGET_APP_INSTRUMENTATION", "product_apk_sha256": digest,
                "installed_product_readback": "EXACT_BEFORE_AND_AFTER",
                "default_test_restored": "EXACT_BYTES_AND_REGISTERED_RUNNER",
                "diagnostic_failure_rejected": True})
        assert accepted(result, gate.API, result["commit"], result["run_id"], digest)
        return result
    except Exception as exc:
        result.update(status="FAIL", error=exception_evidence(exc))
        raise
    finally:
        result["checks"] = len(result["labels"])
        (out/"note-management-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
        print("NOTE_MANAGEMENT_NATIVE "+json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    import sys
    assert sys.argv[1:] == ["selftest"]
    selftest()
