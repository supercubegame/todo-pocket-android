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
    note_signing_selftest()
    good = sample()
    def parents(value):
        batch = {"status": "PASS", "note_management": value, "deletion_ui": report_ui_sample(),
                 "order_ui": report_ordering_sample()}
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
    try(Cursor c=db.rawQuery("SELECT rowid AS rowid,* FROM \""+name+"\" ORDER BY rowid",null)){
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
    from verify_paged_exports import paged_signing, paged_signing_dsl, paged_signing_build
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
        signing = paged_signing(cert)
        require_registration(adb, gate, "notes-before", "V12DeviceTest")
        with tempfile.TemporaryDirectory(prefix="notes-runner-", dir=root/"build") as directory:
            folder = Path(directory); src = folder/"src"; src.mkdir()
            (src/"NoteManagementInstrumentation.java").write_text(JAVA, encoding="utf-8")
            init = folder/"runner.gradle"
            init.write_text("gradle.beforeProject { p ->\n p.plugins.withId('com.android.application') {\n"
                " p.androidComponents.finalizeDsl { dsl ->\n"
                " dsl.defaultConfig.testInstrumentationRunner = 'ci.notes.NoteManagementInstrumentation'\n"
                " dsl.sourceSets.getByName('androidTest').java.srcDir "+json.dumps(str(src))+"\n"
                +paged_signing_dsl(signing)+
                " }\n }\n}\n")
            backup = folder/"default-test.apk"; backup.write_bytes(saved)
            try:
                log = paged_signing_build(["gradle", "--no-daemon", "--console=plain", "-I", init, "assembleDebugAndroidTest"], signing, 300)
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


DELETE_LABELS = [
    "delete_null_id", "delete_blank_id", "delete_missing", "delete_wrong_owner",
    "delete_zero_owner", "delete_negative_owner", "delete_preview_readonly",
    "delete_cancel_readonly", "delete_cancel_consumed", "delete_null_plan",
    "delete_foreign_helper", "delete_stale_title", "delete_stale_body",
    "delete_stale_privacy", "delete_stale_unrelated", "delete_stale_consumed",
    "delete_late_rollback", "delete_failure_consumed", "delete_exact_target",
    "delete_success_consumed", "delete_field_link_only", "delete_close_invalid",
    "delete_reopen",
]


def observe_deletion(text):
    text = text.replace("\r\n", "\n")
    labels = re.findall(r"^NOTE_DELETE_PASS ([^\r\n]+)$", text, re.M)
    results = re.findall(r"^NOTE_DELETE_RESULT ([^\r\n]+)$", text, re.M)
    assert labels == DELETE_LABELS
    assert results == [str(len(DELETE_LABELS))+" PASS"]
    assert "NOTE_DELETE_FAILED" not in text
    assert text.index("NOTE_MANAGEMENT_PASS reopen") < text.index("NOTE_DELETE_PASS ")
    assert text.rindex("NOTE_DELETE_PASS ") < text.index("NOTE_DELETE_RESULT ")
    assert text.index("NOTE_DELETE_RESULT ") < text.index("NOTE_MANAGEMENT_RESULT ")
    return labels


def deletion_log_accepted(text):
    try:
        observe_deletion(text)
        return True
    except (AssertionError, ValueError, TypeError, AttributeError):
        return False


DELETE_JAVA = r'''
 private int deleteCount;
 private static Object invoke(Object target,String name,Class<?>[] types,Object... values){
  try{return target.getClass().getMethod(name,types).invoke(target,values);}
  catch(java.lang.reflect.InvocationTargetException e){
   Throwable cause=e.getCause();if(cause instanceof RuntimeException)throw (RuntimeException)cause;
   if(cause instanceof Error)throw (Error)cause;throw new AssertionError("unexpected checked API failure",cause);
  }catch(ReflectiveOperationException e){throw new AssertionError("guarded deletion API missing: "+name,e);}
 }
 private static Object preview(AppDatabase h,String id,long owner){
  return invoke(h,"prepareNoteDeletion",new Class<?>[]{String.class,long.class},id,owner);
 }
 private static void confirm(AppDatabase h,Object plan){
  try{
   Class<?> type=Class.forName("com.supercubegame.pockettodo.AppDatabase$NoteDeletionPlan");
   invoke(h,"confirmNoteDeletion",new Class<?>[]{type},plan);
  }catch(ClassNotFoundException e){throw new AssertionError("guarded deletion plan API missing",e);}
 }
 private static void cancel(Object plan)throws Exception{((AutoCloseable)plan).close();}
 private void deletePass(String label){deleteCount++;System.out.println("NOTE_DELETE_PASS "+label);}
 private void deleteRefused(AppDatabase h,Class<? extends Throwable> type,Action action,String label)throws Exception{
  Map<String,List<List<String>>> before=state(h);Throwable caught=null;
  try{action.run();}catch(Throwable failure){caught=failure;}
  need(caught!=null&&caught.getClass()==type,"wrong deletion refusal "+label+" actual="+caught);
  need(state(h).equals(before),"deletion refusal changed all-table state "+label);media();deletePass(label);
 }
 private static Map<String,List<List<String>>> copyState(Map<String,List<List<String>>> before){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();for(List<String> row:e.getValue())rows.add(new ArrayList<>(row));out.put(e.getKey(),rows);
  }return out;
 }
 private static Map<String,List<List<String>>> cellExpected(Map<String,List<List<String>>> before,String table,String keyColumn,String id,String column,String value){
  Map<String,List<List<String>>> out=copyState(before);List<List<String>> rows=out.get(table);
  int key=rows.get(0).indexOf(keyColumn),at=rows.get(0).indexOf(column),matches=0;
  need(key>=0&&at>=0,"external fixture columns");
  for(int i=1;i<rows.size();i++)if(rows.get(i).get(key).equals("3:"+id)){rows.get(i).set(at,value);matches++;}
  need(matches==1,"external fixture exact row");return out;
 }
 private static Map<String,List<List<String>>> deletionExpected(Map<String,List<List<String>>> before,String id){
  Map<String,List<List<String>>> out=copyState(before);
  for(String table:new String[]{"notes","blocks","field_notes"}){
   List<List<String>> rows=out.get(table);int at=rows.get(0).indexOf(table.equals("notes")?"id":"note_id");
   need(at>0,"deletion expected columns");int removed=0;
   for(int i=rows.size()-1;i>0;i--)if(rows.get(i).get(at).equals("3:"+id)){rows.remove(i);removed++;}
   if(table.equals("notes"))need(removed==1,"deletion expected exact identity");
  }
  List<List<String>> rows=out.get("revision");int at=rows.get(0).indexOf("value");
  need(rows.size()==2&&at>0,"deletion revision layout");
  rows.get(1).set(at,"1:"+Math.incrementExact(Long.parseLong(rows.get(1).get(at).substring(2))));
  return out;
 }
 private void deleteVerify()throws Exception{
  Context context=getTargetContext();String name="ci-note-management-"+args.getString("nonce")+".db";
  Map<String,List<List<String>>> finalState;
  try(AppDatabase h=AppDatabase.openSchema3(context,name)){
   deleteRefused(h,IllegalArgumentException.class,()->preview(h,null,1),"delete_null_id");
   deleteRefused(h,IllegalArgumentException.class,()->preview(h,"",1),"delete_blank_id");
   deleteRefused(h,IllegalArgumentException.class,()->preview(h,"missing",1),"delete_missing");
   deleteRefused(h,IllegalArgumentException.class,()->preview(h,"second",2),"delete_wrong_owner");
   deleteRefused(h,IllegalArgumentException.class,()->preview(h,"second",0),"delete_zero_owner");
   deleteRefused(h,IllegalArgumentException.class,()->preview(h,"second",-1),"delete_negative_owner");
   // Rename suite has already proved identity and field associations. Deliberately
   // make the target and sibling have the same title before deletion acceptance.
   h.renameNote("second",1,"External","Same");
   Map<String,List<List<String>>> before=state(h);Object cancelled=preview(h,"second",1);
   need(invoke(cancelled,"noteId",new Class<?>[]{}).equals("second"),"preview note identity");
   need(invoke(cancelled,"activityId",new Class<?>[]{}).equals(1L),"preview owner identity");
   need(invoke(cancelled,"title",new Class<?>[]{}).equals("Same"),"preview title");
   need(invoke(cancelled,"blockCount",new Class<?>[]{}).equals(2L),"preview affected block count");
   need(invoke(cancelled,"fieldLinkCount",new Class<?>[]{}).equals(0L),"preview affected link count");
   need(state(h).equals(before),"preview wrote data");media();deletePass("delete_preview_readonly");
   cancel(cancelled);cancel(cancelled);need(state(h).equals(before),"cancel wrote data");media();deletePass("delete_cancel_readonly");
   deleteRefused(h,IllegalStateException.class,()->confirm(h,cancelled),"delete_cancel_consumed");
   deleteRefused(h,IllegalArgumentException.class,()->confirm(h,null),"delete_null_plan");
   Object foreign=preview(h,"second",1);
   try(AppDatabase other=AppDatabase.openSchema3(context,name)){
    deleteRefused(other,IllegalArgumentException.class,()->confirm(other,foreign),"delete_foreign_helper");
   }finally{cancel(foreign);}
   String[][] edits={
    {"notes","id","second","title","Same","Changed","3:Changed","delete_stale_title"},
    {"blocks","id","text","text","Private sentinel","Changed body","3:Changed body","delete_stale_body"},
    {"blocks","id","text","private","1","0","1:0","delete_stale_privacy"},
    {"todos","id","todo","title","Unrelated","Changed todo","3:Changed todo","delete_stale_unrelated"}
   };
   Object lastStale=null;
   for(String[] edit:edits){
    before=state(h);Object stale=preview(h,"second",1);
    try(SQLiteDatabase external=SQLiteDatabase.openDatabase(context.getDatabasePath(name).getPath(),null,SQLiteDatabase.OPEN_READWRITE)){
     String sql="UPDATE "+edit[0]+" SET "+edit[3]+"=? WHERE "+edit[1]+"=?";
     external.execSQL(sql,new Object[]{edit[5],edit[2]});
     need(state(h).equals(cellExpected(before,edit[0],edit[1],edit[2],edit[3],edit[6])),"not exact same-revision external fixture");
     deleteRefused(h,IllegalStateException.class,()->confirm(h,stale),edit[7]);
     external.execSQL(sql,new Object[]{edit[4],edit[2]});
    }
    need(state(h).equals(before),"external fixture not exactly restored");media();lastStale=stale;
   }
   final Object usedStale=lastStale;
   deleteRefused(h,IllegalStateException.class,()->confirm(h,usedStale),"delete_stale_consumed");
   SQLiteDatabase db=h.getWritableDatabase();
   db.execSQL("CREATE TRIGGER ci_delete_late BEFORE UPDATE OF value ON revision WHEN NOT EXISTS(SELECT 1 FROM notes WHERE id='second') AND NOT EXISTS(SELECT 1 FROM blocks WHERE note_id='second') BEGIN SELECT RAISE(ABORT,'note_delete_late_fault'); END");
   Object failed=preview(h,"second",1);before=state(h);Throwable caught=null;
   try{confirm(h,failed);}catch(Throwable failure){caught=failure;}
   finally{db.execSQL("DROP TRIGGER ci_delete_late");}
   need(caught instanceof IllegalArgumentException&&caught.getCause() instanceof SQLiteConstraintException&&caught.getCause().getMessage().contains("note_delete_late_fault"),"late delete barrier not reached "+caught);
   need(state(h).equals(before),"late delete rollback incomplete");media();deletePass("delete_late_rollback");
   deleteRefused(h,IllegalStateException.class,()->confirm(h,failed),"delete_failure_consumed");
   before=state(h);Object plan=preview(h,"second",1);confirm(h,plan);
   need(state(h).equals(deletionExpected(before,"second")),"delete touched sibling, media registry, order or wrong revision");media();deletePass("delete_exact_target");
   deleteRefused(h,IllegalStateException.class,()->confirm(h,plan),"delete_success_consumed");
   before=state(h);Object linked=preview(h,"linked",1);
   need(invoke(linked,"fieldLinkCount",new Class<?>[]{}).equals(1L),"linked preview count");
   need(invoke(linked,"blockCount",new Class<?>[]{}).equals(1L),"linked block count");confirm(h,linked);
   need(state(h).equals(deletionExpected(before,"linked"))&&h.fieldNoteIds(1,"field").isEmpty(),"field values/definition or unrelated data removed");media();deletePass("delete_field_link_only");
   Object closed=preview(h,"first",1);before=state(h);h.close();
   deleteRefused(h,IllegalStateException.class,()->confirm(h,closed),"delete_close_invalid");
   need(state(h).equals(before),"close changed deletion state");h.exportState();finalState=state(h);
  }
  try(AppDatabase reopened=AppDatabase.openSchema3(context,name)){
   need(state(reopened).equals(finalState),"deleted notes reappeared on helper reopen");media();deletePass("delete_reopen");
  }
  need(deleteCount==23,"delete contract count");System.out.println("NOTE_DELETE_RESULT "+deleteCount+" PASS");
 }
'''


def deletion_selftest():
    good = sample()
    assert deletion_log_accepted(good["log"])
    assert accepted(good, 26, "source", "run", "a"*64)
    bad = []
    for label in DELETE_LABELS:
        marker = "NOTE_DELETE_PASS "+label+"\n"
        assert good["log"].count(marker) == 1
        bad.extend((good["log"].replace(marker, ""), good["log"].replace(marker, marker+marker)))
    bad.extend((
        good["log"].replace("NOTE_DELETE_RESULT 23 PASS", "NOTE_DELETE_RESULT 22 PASS"),
        good["log"]+"NOTE_DELETE_FAILED\n",
        good["log"].replace("NOTE_DELETE_RESULT 23 PASS\n", ""),
        good["log"].replace("NOTE_DELETE_PASS delete_null_id\n", "")+"NOTE_DELETE_PASS delete_null_id\n",
        good["log"].replace("NOTE_DELETE_PASS delete_null_id\n", "NOTE_DELETE_PASS delete_blank_id\n", 1),
        good["log"].replace("NOTE_DELETE_RESULT 23 PASS\n", "").replace("NOTE_DELETE_PASS delete_null_id\n", "NOTE_DELETE_RESULT 23 PASS\nNOTE_DELETE_PASS delete_null_id\n", 1),
    ))
    for log in bad:
        assert log != good["log"]
        assert not deletion_log_accepted(log)
        value = copy.deepcopy(good);value["log"] = log
        value["log_sha256"] = hashlib.sha256(log.encode()).hexdigest()
        assert not accepted(value, 26, "source", "run", "a"*64)
        batch = {"status":"PASS", "note_management":value, "deletion_ui":report_ui_sample(),
                 "order_ui":report_ordering_sample()}
        codec = {"status":"PASS", "api":26, "commit":"source", "run_id":"run",
                 "release_ready":False, "apk_sha256":"a"*64, "batch_ui":batch}
        assert aggregate(codec, {"status":"PASS","batch_ui":copy.deepcopy(batch)}, 26, "source", "run")["status"] != "PASS"
    # Permanent observer mutants: unchanged valid input first, then the same negative
    # corpus must reject a mutant through the exact checker used above.
    import inspect
    source = inspect.getsource(observe_deletion)
    mutants = [
        ("assert labels == DELETE_LABELS", "assert True"),
        ('assert results == [str(len(DELETE_LABELS))+" PASS"]', "assert True"),
        ('assert "NOTE_DELETE_FAILED" not in text', "assert True"),
        ('assert text.rindex("NOTE_DELETE_PASS ") < text.index("NOTE_DELETE_RESULT ")', "assert True"),
    ]
    killed = 0
    for old, new in mutants:
        assert source.count(old) == 1
        modified = source.replace(old, new, 1);assert modified != source
        namespace = dict(globals());exec(compile(modified, "<delete-observer-mutant>", "exec"), namespace)
        checker = namespace["observe_deletion"]
        checker(good["log"])
        escaped = 0
        for log in bad:
            try:checker(log)
            except (AssertionError, ValueError):continue
            escaped += 1
        assert escaped > 0, "mutation did not weaken a exercised obligation"
        killed += 1
    result = {"positive":1,"negative":len(bad),"permanent_observer_mutants":killed,
              "scope":"HOST_RECEIPT_OBSERVERS_NOT_ANDROID_EXECUTION"}
    print("NOTE_DELETE_HOST "+json.dumps(result), flush=True)
    return result


# Retain every existing rename check and use the existing mandatory report path.
SCOPE = "APK_NOTE_RENAME_AND_GUARDED_DELETE_BACKEND_SYNTHETIC_NOT_UI_OR_LMK"
_rename_accepted = accepted
_rename_sample = sample
_rename_selftest = selftest
_rename_aggregate = aggregate


def accepted(value, api, source, run, apk):
    return _rename_accepted(value, api, source, run, apk) and deletion_log_accepted(value["log"])


def sample(api=26, source="source", run="run", apk="a"*64):
    value = _rename_sample(api, source, run, apk)
    marker = "NOTE_MANAGEMENT_RESULT "
    assert value["log"].count(marker) == 1
    evidence = "".join("NOTE_DELETE_PASS "+label+"\n" for label in DELETE_LABELS)
    evidence += "NOTE_DELETE_RESULT "+str(len(DELETE_LABELS))+" PASS\n"
    value["log"] = value["log"].replace(marker, evidence+marker, 1)
    value["log_sha256"] = hashlib.sha256(value["log"].encode()).hexdigest()
    return value


def aggregate(codec, native, api, source, run):
    result = _rename_aggregate(codec, native, api, source, run)
    result["deletion_backend"] = {
        "status":result["status"],
        "checks":len(DELETE_LABELS) if result["status"] == "PASS" else 0,
        "labels":DELETE_LABELS[:] if result["status"] == "PASS" else [],
        "scope":"ACTUAL_INSTALLED_APK_ISOLATED_DB_NOT_NATIVE_CONFIRMATION_UI",
    }
    return result


def selftest():
    result = _rename_selftest()
    result["deletion_backend"] = deletion_selftest()
    return result


_entry = '   verify();need(count==18,"contract count");'
_declaration = " @Override public void onCreate(Bundle value)"
assert JAVA.count(_entry) == JAVA.count(_declaration) == 1
JAVA = JAVA.replace(_entry, '   verify();deleteVerify();need(count==18,"contract count");', 1)
JAVA = JAVA.replace(_declaration, DELETE_JAVA+"\n"+_declaration, 1)


# Independently require native deletion evidence in the report, not just in the
# emitter's own receipt. Keep this expectation separate from verify_batch_exports.
REPORT_DELETE_UI_LABELS = [
    "preview_exact_identity_counts", "cancel_readonly", "unchecked_blocked_readonly",
    "process_loss_readonly", "fresh_preview_unchecked", "same_title_target_only",
    "all_media_preserved", "restart_deletion_and_sibling_persisted",
]


def report_deletion_ui(value, api, source, run, apk):
    if not isinstance(value, dict):
        return False
    return (
        value.get("status") == "PASS" and
        value.get("scope") == "NATIVE_NOTE_DELETE_EXACT_ID_CONSENT_FORCE_STOP_RESTART_NOT_LMK" and
        type(value.get("api")) is int and value["api"] == api and
        value.get("commit") == source and value.get("run_id") == run and
        isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) is not None and
        value.get("apk_sha256") == apk and value.get("release_ready") is False and
        value.get("labels") == REPORT_DELETE_UI_LABELS and
        type(value.get("checks")) is int and value["checks"] == 8 and
        isinstance(value.get("note_id"), str) and bool(value["note_id"].strip()) and
        isinstance(value.get("sibling_id"), str) and bool(value["sibling_id"].strip()) and
        value["note_id"] != value["sibling_id"] and
        type(value.get("owner")) is int and value["owner"] > 0 and
        type(value.get("deleted_blocks")) is int and value["deleted_blocks"] > 0 and
        type(value.get("deleted_field_links")) is int and value["deleted_field_links"] >= 0 and
        type(value.get("preserved_media_files")) is int and value["preserved_media_files"] > 0 and
        value.get("state") == "EXACT_TARGET_ROWS_ONE_REVISION_ALL_MEDIA_PRESERVED"
    )


def report_ui_sample(api=26, source="source", run="run", apk="a"*64):
    # Host-only report fixture. Device results are never constructed here.
    return {"status": "PASS", "scope": "NATIVE_NOTE_DELETE_EXACT_ID_CONSENT_FORCE_STOP_RESTART_NOT_LMK",
            "api": api, "commit": source, "run_id": run, "apk_sha256": apk,
            "release_ready": False, "labels": REPORT_DELETE_UI_LABELS[:], "checks": 8,
            "note_id": "second", "sibling_id": "third", "owner": 1,
            "deleted_blocks": 3, "deleted_field_links": 0, "preserved_media_files": 6,
            "state": "EXACT_TARGET_ROWS_ONE_REVISION_ALL_MEDIA_PRESERVED"}


_backend_aggregate = aggregate
_backend_selftest = selftest


# Independent expectations: do not import the emitter's labels or validator.
REPORT_EDITOR_UI_LABELS = [
    "up_fresh_default_first", "up_picker_order_cancel_readonly",
    "up_same_title_identity_readonly", "down_fresh_default_first",
    "down_picker_order_cancel_readonly", "down_same_title_identity_readonly",
]


def report_editor_ui(value, api, source, run, apk, owner, note, sibling):
    return isinstance(value, dict) and (
        value.get("status") == "PASS" and
        value.get("scope") == "NATIVE_REORDER_EDITOR_INDEXED_PICKER_DISTINCT_BODY_WITNESS_NOT_LMK" and
        type(value.get("api")) is int and value["api"] == api and
        value.get("commit") == source and value.get("run_id") == run and
        isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) is not None and
        value.get("apk_sha256") == apk and value.get("release_ready") is False and
        value.get("labels") == REPORT_EDITOR_UI_LABELS and
        type(value.get("checks")) is int and value["checks"] == 6 and
        type(owner) is int and owner > 0 and
        type(value.get("owner")) is int and value.get("owner") == owner and
        isinstance(note, str) and bool(note.strip()) and
        isinstance(sibling, str) and bool(sibling.strip()) and note != sibling and
        value.get("note_id") == note and value.get("sibling_id") == sibling and
        value.get("state") == "BROWSING_CANCEL_SELECTION_ALL_TABLES_REVISION_MEDIA_UNCHANGED"
    )


def report_editor_sample(api=26, source="source", run="run", apk="a"*64):
    # Host fixture only. Never used to manufacture device evidence.
    return {"status": "PASS",
            "scope": "NATIVE_REORDER_EDITOR_INDEXED_PICKER_DISTINCT_BODY_WITNESS_NOT_LMK",
            "api": api, "commit": source, "run_id": run, "apk_sha256": apk,
            "release_ready": False, "labels": REPORT_EDITOR_UI_LABELS[:], "checks": 6,
            "note_id": "third", "sibling_id": "second", "owner": 1,
            "state": "BROWSING_CANCEL_SELECTION_ALL_TABLES_REVISION_MEDIA_UNCHANGED"}


REPORT_ORDER_UI_LABELS = [
    "boundary_controls", "singleton_disabled_readonly", "same_title_up_exact_state",
    "restart_up_summary_order", "same_title_down_exact_state",
    "restart_down_summary_order", "original_order_restored_two_revisions",
    "all_media_preserved",
]


def report_ordering_ui(value, api, source, run, apk):
    if not isinstance(value, dict):
        return False
    return (
        value.get("status") == "PASS" and
        value.get("scope") == "NATIVE_NOTE_ORDER_STABLE_ID_FORCE_STOP_RESTART_NOT_LMK" and
        type(value.get("api")) is int and value["api"] == api and
        value.get("commit") == source and value.get("run_id") == run and
        isinstance(apk, str) and re.fullmatch("[0-9a-f]{64}", apk) is not None and
        value.get("apk_sha256") == apk and value.get("release_ready") is False and
        value.get("labels") == REPORT_ORDER_UI_LABELS and
        type(value.get("checks")) is int and value["checks"] == 8 and
        isinstance(value.get("note_id"), str) and bool(value["note_id"].strip()) and
        isinstance(value.get("sibling_id"), str) and bool(value["sibling_id"].strip()) and
        value["note_id"] != value["sibling_id"] and
        type(value.get("owner")) is int and value["owner"] > 0 and
        value.get("state") == "EXACT_OWNER_SLOT_SWAP_PER_MOVE_TWO_REVISIONS_ALL_OTHER_TABLES_MEDIA_UNCHANGED" and
        report_editor_ui(value.get("editor_ui"), api, source, run, apk,
                         value["owner"], value["note_id"], value["sibling_id"])
    )


def report_ordering_sample(api=26, source="source", run="run", apk="a"*64):
    # Host fixture only, never a device result.
    return {"status": "PASS", "scope": "NATIVE_NOTE_ORDER_STABLE_ID_FORCE_STOP_RESTART_NOT_LMK",
            "api": api, "commit": source, "run_id": run, "apk_sha256": apk,
            "release_ready": False, "labels": REPORT_ORDER_UI_LABELS[:], "checks": 8,
            "note_id": "third", "sibling_id": "second", "owner": 1,
            "editor_ui": report_editor_sample(api, source, run, apk),
            "state": "EXACT_OWNER_SLOT_SWAP_PER_MOVE_TWO_REVISIONS_ALL_OTHER_TABLES_MEDIA_UNCHANGED"}


def aggregate(codec, native, api, source, run):
    result = _backend_aggregate(codec, native, api, source, run)
    c = codec.get("batch_ui") if isinstance(codec, dict) else None
    n = native.get("batch_ui") if isinstance(native, dict) else None
    c = c if isinstance(c, dict) else {}
    n = n if isinstance(n, dict) else {}
    value = c.get("deletion_ui")
    apk = codec.get("apk_sha256") if isinstance(codec, dict) else None
    passed = (
        result["status"] == "PASS" and value == n.get("deletion_ui") and
        report_deletion_ui(value, api, source, run, apk) and
        report_deletion_ui(n.get("deletion_ui"), api, source, run, apk)
    )
    result["deletion_ui"] = {
        "status": "PASS" if passed else "NOT_VERIFIED",
        "evidence": value,
        "checks": 8 if passed else 0,
        "scope": "INDEPENDENT_NATIVE_DELETE_RECEIPT_NOT_NEW_DEVICE_EXECUTION",
        "release_ready": False,
    }
    order_value = c.get("order_ui")
    ordered = (passed and order_value == n.get("order_ui") and
               report_ordering_ui(order_value, api, source, run, apk) and
               report_ordering_ui(n.get("order_ui"), api, source, run, apk))
    result["order_ui"] = {
        "status": "PASS" if ordered else "NOT_VERIFIED",
        "evidence": order_value, "checks": 8 if ordered else 0,
        "scope": "INDEPENDENT_NATIVE_ORDER_RECEIPT_NOT_NEW_DEVICE_EXECUTION",
        "release_ready": False,
    }
    result["status"] = "PASS" if ordered else "NOT_VERIFIED"
    result["editor_ui"] = {
        "status": "PASS" if ordered else "NOT_VERIFIED",
        "evidence": order_value.get("editor_ui") if isinstance(order_value, dict) else None,
        "checks": 6 if ordered else 0,
        "scope": "INDEPENDENT_NATIVE_EDITOR_RECEIPT_NOT_NEW_DEVICE_EXECUTION",
        "release_ready": False,
    }
    return result


def report_deletion_selftest():
    def parents(value, api=26):
        batch = {"status": "PASS", "note_management": sample(api), "deletion_ui": value,
                 "order_ui": report_ordering_sample(api)}
        return ({"status": "PASS", "api": api, "commit": "source", "run_id": "run",
                 "release_ready": False, "apk_sha256": "a"*64, "batch_ui": copy.deepcopy(batch)},
                {"status": "PASS", "batch_ui": copy.deepcopy(batch)})
    def passes(pair, api=26):
        result = aggregate(*pair, api, "source", "run")
        return result["status"] == result["deletion_ui"]["status"] == "PASS"
    for api in (26, 34):
        assert passes(parents(report_ui_sample(api), api), api)
    good = report_ui_sample()
    bad = [None, {}, []]
    for key in good:
        value = copy.deepcopy(good); del value[key]; bad.append(value)
    for key, value in (("status", "FAIL"), ("scope", "BACKEND_ONLY"), ("api", 34), ("api", True),
            ("commit", "old"), ("run_id", "old"), ("apk_sha256", "b"*64),
            ("release_ready", True), ("checks", True), ("checks", 7),
            ("note_id", ""), ("note_id", " "), ("sibling_id", "second"), ("sibling_id", None),
            ("owner", True), ("owner", 0), ("deleted_blocks", True), ("deleted_blocks", 0),
            ("deleted_field_links", True), ("deleted_field_links", -1),
            ("preserved_media_files", True), ("preserved_media_files", 0),
            ("state", "NOT_VERIFIED"), ("labels", REPORT_DELETE_UI_LABELS[::-1])):
        item = copy.deepcopy(good); item[key] = value; bad.append(item)
    for index in range(8):
        for duplicate in (False, True):
            item = copy.deepcopy(good)
            if duplicate: item["labels"].insert(index, item["labels"][index])
            else: item["labels"].pop(index)
            item["checks"] = len(item["labels"]); bad.append(item)
    pairs = []
    for value in bad:
        assert not report_deletion_ui(value, 26, "source", "run", "a"*64)
        # Both parents carry the same malformed value: equality alone cannot pass.
        pairs.append(parents(value))
    for side in (0, 1):
        pair = list(parents(good)); del pair[side]["batch_ui"]["deletion_ui"]; pairs.append(pair)
        for key, value in (("note_id", "different"), ("sibling_id", "different"),
                           ("owner", 2), ("deleted_blocks", 4), ("preserved_media_files", 7)):
            pair = list(parents(good)); pair[side]["batch_ui"]["deletion_ui"][key] = value
            assert report_deletion_ui(pair[side]["batch_ui"]["deletion_ui"], 26, "source", "run", "a"*64)
            pairs.append(pair)
        pair = list(parents(good)); del pair[side]["batch_ui"]["note_management"]; pairs.append(pair)
        pair = list(parents(good)); pair[side]["batch_ui"]["status"] = "FAIL"; pairs.append(pair)
        for key, value in (("owner", True), ("deleted_field_links", False)):
            pair = list(parents(good)); pair[side]["batch_ui"]["deletion_ui"][key] = value
            # Python dict equality treats True==1 and False==0. Validate both sides.
            assert pair[0]["batch_ui"]["deletion_ui"] == pair[1]["batch_ui"]["deletion_ui"]
            pairs.append(pair)
    for pair in pairs:
        assert not passes(pair), "independent deletion report accepted missing, stale or divergent evidence"
    # Execute weakened report implementations against this exact corpus.
    import inspect
    source = inspect.getsource(aggregate)
    killed = 0
    for old, new in (
        ('value == n.get("deletion_ui")', "True"),
        ("report_deletion_ui(value, api, source, run, apk)", "True"),
        ('report_deletion_ui(n.get("deletion_ui"), api, source, run, apk)', "True"),
        ('result["status"] == "PASS"', "True"),
    ):
        assert source.count(old) == 1
        namespace = dict(globals())
        exec(compile(source.replace(old, new, 1), "<delete-report-mutant>", "exec"), namespace)
        checker = namespace["aggregate"]
        assert checker(*parents(good), 26, "source", "run")["status"] == "PASS"
        assert any(checker(*pair, 26, "source", "run")["status"] == "PASS" for pair in pairs)
        killed += 1
    result = {"positive": 2, "receipt_negative": len(bad), "aggregate_negative": len(pairs),
              "permanent_report_mutants": killed, "scope": "HOST_REPORT_OBSERVERS_NOT_ANDROID_EXECUTION"}
    print("NOTE_DELETE_REPORT_HOST "+json.dumps(result), flush=True)
    return result


def selftest():
    result = _backend_selftest()
    result["deletion_ui_report"] = report_deletion_selftest()
    return result


# Stable-ID ordering contracts. This is deliberately test-first: the installed
# product must expose moveNote before the device can emit any ordering PASS.
ORDER_LABELS = [
    "order_null_id", "order_blank_id", "order_missing_note", "order_wrong_owner",
    "order_zero_owner", "order_null_list", "order_empty_list",
    "order_duplicate_id", "order_null_member", "order_missing_member",
    "order_foreign_member", "order_negative_position", "order_past_end",
    "order_same_position_readonly", "order_move_up_exact", "order_move_down_exact",
    "order_linked_first_exact", "order_input_list_preserved",
    "order_stale_sequence", "order_external_same_revision",
    "order_new_note_stale", "order_late_rollback",
    "order_helper_reopen", "order_backup_restore",
]


def observe_order(text):
    text = text.replace("\r\n", "\n")
    labels = re.findall(r"^NOTE_ORDER_PASS ([^\r\n]+)$", text, re.M)
    results = re.findall(r"^NOTE_ORDER_RESULT ([^\r\n]+)$", text, re.M)
    assert labels == ORDER_LABELS
    assert results == [str(len(ORDER_LABELS))+" PASS"]
    assert "NOTE_ORDER_FAILED" not in text
    assert text.index("NOTE_DELETE_RESULT ") < text.index("NOTE_ORDER_PASS ")
    assert text.rindex("NOTE_ORDER_PASS ") < text.index("NOTE_ORDER_RESULT ")
    assert text.index("NOTE_ORDER_RESULT ") < text.index("NOTE_MANAGEMENT_RESULT ")
    return labels


def order_log_accepted(text):
    try:
        observe_order(text)
        return True
    except (AssertionError, ValueError, TypeError, AttributeError):
        return False


ORDER_JAVA = r'''
 private int orderCount;
 private void orderPass(String label){orderCount++;System.out.println("NOTE_ORDER_PASS "+label);}
 private static boolean moveNote(AppDatabase h,String id,long owner,List<String> seen,int to){
  Object answer=invoke(h,"moveNote",new Class<?>[]{String.class,long.class,List.class,int.class},id,owner,seen,to);
  need(answer instanceof Boolean,"moveNote must return actual change");return (Boolean)answer;
 }
 private static List<String> noteOrder(AppDatabase h,long owner){
  List<String> ids=new ArrayList<>();
  try(Cursor c=h.getReadableDatabase().rawQuery("SELECT id FROM notes WHERE activity_id=? ORDER BY rowid",new String[]{Long.toString(owner)})){
   while(c.moveToNext())ids.add(c.getString(0));
  }return ids;
 }
 private static Map<String,List<List<String>>> orderExpected(Map<String,List<List<String>>> before,List<String> wanted){
  Map<String,List<List<String>>> out=copyState(before);
  List<List<String>> rows=out.get("notes");
  need(rows.get(0).equals(Arrays.asList("rowid","id","activity_id","title")),"order fixture columns");
  List<Integer> slots=new ArrayList<>();Map<String,List<String>> byId=new HashMap<>();
  for(int i=1;i<rows.size();i++)if(rows.get(i).get(2).equals("1:1")){
   slots.add(i);byId.put(rows.get(i).get(1).substring(2),new ArrayList<>(rows.get(i)));
  }
  need(slots.size()==wanted.size()&&new HashSet<>(wanted).equals(byId.keySet()),"expected exact owner permutation");
  List<String> rowids=new ArrayList<>();for(int slot:slots)rowids.add(rows.get(slot).get(0));
  for(int i=0;i<slots.size();i++){
   List<String> row=new ArrayList<>(byId.get(wanted.get(i)));row.set(0,rowids.get(i));rows.set(slots.get(i),row);
  }
  List<List<String>> revision=out.get("revision");
  need(revision.size()==2&&revision.get(0).equals(Arrays.asList("rowid","id","value")),"order revision fixture actual="+revision);
  revision.get(1).set(2,"1:"+Math.incrementExact(Long.parseLong(revision.get(1).get(2).substring(2))));
  return out;
 }
 private void orderRefused(AppDatabase h,Class<? extends Throwable> type,Action action,String label)throws Exception{
  Map<String,List<List<String>>> before=state(h);Throwable caught=null;
  try{action.run();}catch(Throwable failure){caught=failure;}
  need(caught!=null&&caught.getClass()==type,"wrong order refusal "+label+" actual="+caught);
  need(state(h).equals(before),"order refusal changed full state "+label);media();orderPass(label);
 }
 private void orderVerify()throws Exception{
  Context context=getTargetContext();String nonce=args.getString("nonce");
  String name="ci-note-order-"+nonce+".db",restoredName="ci-note-order-restored-"+nonce+".db";
  need(!context.getDatabasePath(name).exists()&&!context.getDatabasePath(restoredName).exists(),"no order fixture reuse");
  Path folder=new File(context.getCacheDir(),"note-order-"+nonce).toPath();Files.createDirectory(folder);
  com.supercubegame.pockettodo.MediaRepository mediaStore=new com.supercubegame.pockettodo.MediaRepository(folder.resolve("media"),8388608);
  String digest=mediaStore.copy(new ByteArrayInputStream(assetBytes));
  Map<String,List<List<String>>> finalState;byte[] wire;Path archive=folder.resolve("ordered.zip");
  try(AppDatabase h=AppDatabase.openSchema3(context,name)){
   h.addCategory(1,"Order");h.addActivity(1,1,0,"First");h.addActivity(2,1,0,"Other");
   h.createNote("a",1,"Same");h.createNote("foreign",2,"Same");h.createNote("b",1,"Same");
   h.defineField("field","Field","LONG_TEXT",Collections.emptyList());
   h.createFieldNote("linked",1,"field","Same");h.putField(1,"field",Collections.singletonList("Field value"));
   h.addTodo("todo","Keep");h.registerMedia(digest,"image/png",assetBytes.length);
   h.saveNote("a",Arrays.asList(NoteDocument.Block.text("text","Private sentinel",true),NoteDocument.Block.image("image",digest,"caption",false)));
   h.saveNote("b",Collections.singletonList(NoteDocument.Block.image("image",digest,"shared",true)));
   h.saveNote("linked",Collections.singletonList(NoteDocument.Block.text("text","Linked",false)));
   final List<String> original=Arrays.asList("a","b","linked");
   need(noteOrder(h,1).equals(original)&&noteOrder(h,2).equals(Collections.singletonList("foreign")),"explicit interleaved order fixture");
   h.exportState();
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,null,1,original,0),"order_null_id");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"",1,original,0),"order_blank_id");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"missing",1,original,0),"order_missing_note");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"b",2,Collections.singletonList("foreign"),0),"order_wrong_owner");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"b",0,original,0),"order_zero_owner");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"b",1,null,0),"order_null_list");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"b",1,Collections.emptyList(),0),"order_empty_list");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"b",1,Arrays.asList("a","b","b"),0),"order_duplicate_id");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"b",1,Arrays.asList("a","b",null),0),"order_null_member");
   orderRefused(h,IllegalStateException.class,()->moveNote(h,"b",1,Arrays.asList("a","b"),0),"order_missing_member");
   orderRefused(h,IllegalStateException.class,()->moveNote(h,"b",1,Arrays.asList("a","b","foreign"),0),"order_foreign_member");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"b",1,original,-1),"order_negative_position");
   orderRefused(h,IllegalArgumentException.class,()->moveNote(h,"b",1,original,3),"order_past_end");
   Map<String,List<List<String>>> before=state(h);
   need(!moveNote(h,"b",1,original,1)&&state(h).equals(before),"same position changed state");media();orderPass("order_same_position_readonly");
   need(moveNote(h,"b",1,original,0),"move up no change");
   need(noteOrder(h,1).equals(Arrays.asList("b","a","linked"))&&state(h).equals(orderExpected(before,Arrays.asList("b","a","linked"))),"up changed identity, body, foreign row, link or revision");media();orderPass("order_move_up_exact");
   before=state(h);
   need(moveNote(h,"b",1,Arrays.asList("b","a","linked"),2),"move down no change");
   need(noteOrder(h,1).equals(Arrays.asList("a","linked","b"))&&state(h).equals(orderExpected(before,Arrays.asList("a","linked","b"))),"down exact state");media();orderPass("order_move_down_exact");
   before=state(h);List<String> input=new ArrayList<>(Arrays.asList("a","linked","b"));
   need(moveNote(h,"linked",1,input,0),"linked move no change");
   need(noteOrder(h,1).equals(Arrays.asList("linked","a","b"))&&state(h).equals(orderExpected(before,Arrays.asList("linked","a","b"))),"linked move altered other state");media();orderPass("order_linked_first_exact");
   need(input.equals(Arrays.asList("a","linked","b"))&&h.fieldNoteIds(1,"field").equals(Collections.singletonList("linked")),"caller list or field link changed");orderPass("order_input_list_preserved");
   orderRefused(h,IllegalStateException.class,()->moveNote(h,"a",1,original,1),"order_stale_sequence");
   // External writer changes membership without a revision bump. Fully prove
   // that fixture before checking stale refusal; never infer it from API failure.
   before=state(h);
   try(SQLiteDatabase external=SQLiteDatabase.openDatabase(context.getDatabasePath(name).getPath(),null,SQLiteDatabase.OPEN_READWRITE)){
    external.execSQL("INSERT INTO notes(id,activity_id,title) VALUES('external',1,'Same')");
   }
   need(state(h).get("revision").equals(before.get("revision"))&&noteOrder(h,1).equals(Arrays.asList("linked","a","b","external")),"same-revision external fixture");
   orderRefused(h,IllegalStateException.class,()->moveNote(h,"a",1,Arrays.asList("linked","a","b"),0),"order_external_same_revision");
   List<String> seen=noteOrder(h,1);h.createNote("new",1,"Same");
   orderRefused(h,IllegalStateException.class,()->moveNote(h,"a",1,seen,0),"order_new_note_stale");
   SQLiteDatabase db=h.getWritableDatabase();
   db.execSQL("CREATE TRIGGER ci_order_late BEFORE UPDATE OF value ON revision WHEN (SELECT id FROM notes WHERE activity_id=1 ORDER BY rowid LIMIT 1)='a' BEGIN SELECT RAISE(ABORT,'note_order_late_fault'); END");
   before=state(h);Throwable caught=null;
   try{moveNote(h,"a",1,noteOrder(h,1),0);}catch(Throwable failure){caught=failure;}
   finally{db.execSQL("DROP TRIGGER ci_order_late");}
   need(caught instanceof IllegalArgumentException&&caught.getCause() instanceof SQLiteConstraintException&&caught.getCause().getMessage().contains("note_order_late_fault"),"late reorder barrier not reached "+caught);
   need(state(h).equals(before),"partial row moves or revision escaped rollback");media();orderPass("order_late_rollback");
   finalState=state(h);wire=h.exportState();h.exportBackup(archive,mediaStore);
   need(state(h).equals(finalState),"backup changed source");mediaStore.verify(digest);
   need(Arrays.equals(Files.readAllBytes(mediaStore.path(digest)),assetBytes),"registered shared asset changed");
  }
  try(AppDatabase reopened=AppDatabase.openSchema3(context,name)){
   need(state(reopened).equals(finalState)&&Arrays.equals(reopened.exportState(),wire),"helper reopen changed order/state");media();orderPass("order_helper_reopen");
  }
  com.supercubegame.pockettodo.MediaRepository restoredMedia=new com.supercubegame.pockettodo.MediaRepository(folder.resolve("restored-media"),8388608);
  try(AppDatabase restored=AppDatabase.openSchema3(context,restoredName)){
   try(AppDatabase.RestorePlan plan=restored.prepareRestore(archive,folder.resolve("staging"),16777216)){
    restored.confirmRestore(plan,restoredMedia);
   }
   need(Arrays.equals(restored.exportState(),wire),"backup semantic bytes/order differ");
   need(noteOrder(restored,1).equals(Arrays.asList("linked","a","b","external","new"))&&noteOrder(restored,2).equals(Collections.singletonList("foreign")),"backup note ordering differs");
   need(restored.fieldNoteIds(1,"field").equals(Collections.singletonList("linked")),"backup field association differs");
   restoredMedia.verify(digest);need(Arrays.equals(Files.readAllBytes(restoredMedia.path(digest)),assetBytes),"backup shared asset differs");
   media();orderPass("order_backup_restore");
  }
  need(orderCount==24,"order contract count");System.out.println("NOTE_ORDER_RESULT "+orderCount+" PASS");
 }
'''


_before_order_accepted = accepted
_before_order_sample = sample
_before_order_selftest = selftest


def accepted(value, api, source, run, apk):
    return _before_order_accepted(value, api, source, run, apk) and order_log_accepted(value["log"])


def sample(api=26, source="source", run="run", apk="a"*64):
    value = _before_order_sample(api, source, run, apk)
    marker = "NOTE_MANAGEMENT_RESULT "
    assert value["log"].count(marker) == 1
    records = "".join("NOTE_ORDER_PASS "+label+"\n" for label in ORDER_LABELS)
    records += "NOTE_ORDER_RESULT "+str(len(ORDER_LABELS))+" PASS\n"
    value["log"] = value["log"].replace(marker, records+marker, 1)
    value["log_sha256"] = hashlib.sha256(value["log"].encode()).hexdigest()
    return value


def order_selftest():
    good = sample()
    assert order_log_accepted(good["log"])
    assert accepted(good, 26, "source", "run", "a"*64)
    bad = []
    for label in ORDER_LABELS:
        marker = "NOTE_ORDER_PASS "+label+"\n"
        assert good["log"].count(marker) == 1
        bad.extend((good["log"].replace(marker, ""), good["log"].replace(marker, marker+marker)))
    bad.extend((
        good["log"].replace("NOTE_ORDER_RESULT 24 PASS", "NOTE_ORDER_RESULT 23 PASS"),
        good["log"]+"NOTE_ORDER_FAILED\n",
        good["log"].replace("NOTE_ORDER_RESULT 24 PASS\n", ""),
        good["log"].replace("NOTE_ORDER_PASS order_null_id\n", "")+"NOTE_ORDER_PASS order_null_id\n",
        good["log"].replace("NOTE_ORDER_PASS order_null_id\n", "NOTE_ORDER_PASS order_blank_id\n", 1),
        good["log"].replace("NOTE_ORDER_RESULT 24 PASS\n", "").replace("NOTE_ORDER_PASS order_null_id\n", "NOTE_ORDER_RESULT 24 PASS\nNOTE_ORDER_PASS order_null_id\n", 1),
    ))
    # Regression receipts have to remain positive before each negative edit.
    def parents(value):
        batch = {"status":"PASS", "note_management":value, "deletion_ui":report_ui_sample(),
                 "order_ui":report_ordering_sample()}
        return ({"status":"PASS", "api":26, "commit":"source", "run_id":"run",
                 "release_ready":False, "apk_sha256":"a"*64, "batch_ui":copy.deepcopy(batch)},
                {"status":"PASS", "batch_ui":copy.deepcopy(batch)})
    assert aggregate(*parents(good), 26, "source", "run")["status"] == "PASS"
    for log in bad:
        assert log != good["log"] and not order_log_accepted(log)
        value = copy.deepcopy(good);value["log"] = log
        value["log_sha256"] = hashlib.sha256(log.encode()).hexdigest()
        assert not accepted(value, 26, "source", "run", "a"*64)
        assert aggregate(*parents(value), 26, "source", "run")["status"] == "NOT_VERIFIED"
    import inspect
    source = inspect.getsource(observe_order)
    for old in (
        "assert labels == ORDER_LABELS",
        'assert results == [str(len(ORDER_LABELS))+" PASS"]',
        'assert "NOTE_ORDER_FAILED" not in text',
        'assert text.rindex("NOTE_ORDER_PASS ") < text.index("NOTE_ORDER_RESULT ")',
    ):
        assert source.count(old) == 1
        namespace = dict(globals())
        exec(compile(source.replace(old, "assert True", 1), "<order-observer-mutant>", "exec"), namespace)
        checker = namespace["observe_order"];checker(good["log"])
        escaped = 0
        for log in bad:
            try:checker(log)
            except (AssertionError, ValueError):continue
            escaped += 1
        assert escaped > 0, "order observer mutant did not weaken an exercised obligation"
    result = {"positive":1, "negative":len(bad), "permanent_observer_mutants":4,
              "scope":"HOST_REPORT_OBSERVERS_NOT_ANDROID_EXECUTION"}
    print("NOTE_ORDER_HOST "+json.dumps(result), flush=True)
    return result


def order_projection_selftest():
    """Real host SQLite metadata from product DDL and instrumentation SQL.
    This checks the fixture's SQL shape, not Android Cursor or moveNote behavior.
    """
    import sqlite3
    root = Path(__file__).resolve().parents[1]
    product = (root/"src/main/java/com/supercubegame/pockettodo/AppDatabase.java").read_text()
    begin = JAVA.index(" static Map<String,List<List<String>>> state(")
    end = JAVA.index(" static Map<String,List<List<String>>> expected(", begin)
    projection = re.findall(r'db.rawQuery\("(SELECT [^"\n]+) FROM \\"', JAVA[begin:end])
    assert len(projection) == 1, "snapshot projection missing or ambiguous"
    expected = {"revision": ["rowid", "id", "value"],
                "notes": ["rowid", "id", "activity_id", "title"]}
    with sqlite3.connect(":memory:") as db:
        for table in expected:
            declarations = re.findall(r'db\.execSQL\("(CREATE TABLE '+table+r'\([^"\n]+)"\);', product)
            assert len(declarations) == 1, "missing actual product DDL "+table
            db.execute(declarations[0])
        db.execute("INSERT INTO revision VALUES(1,7)")
        db.execute("INSERT INTO notes VALUES('same-a',1,'Same')")
        db.execute("INSERT INTO notes VALUES('same-b',1,'Same')")
        def check(query):
            for table, columns in expected.items():
                cursor = db.execute(query+' FROM "'+table+'" ORDER BY rowid')
                actual = [column[0] for column in cursor.description]
                assert actual == columns, (table, actual, columns)
                rows = cursor.fetchall()
                plain = db.execute('SELECT * FROM "'+table+'" ORDER BY rowid').fetchall()
                assert [row[1:] for row in rows] == plain, "projection lost typed cells"
                assert [row[0] for row in rows] == list(range(1, len(rows)+1))
        check(projection[0])
        # The historical unaliased query must fail on the INTEGER PRIMARY KEY
        # table, rather than being declared equivalent by a string-only guard.
        assert projection[0] != "SELECT rowid,*"
        killed = 0
        for query in ("SELECT rowid,*", "SELECT *", "SELECT 0 AS rowid,*"):
            try:
                check(query)
            except AssertionError:
                killed += 1
            else:
                raise AssertionError("projection mutant escaped "+query)
        assert killed == 3
    result = {"tables": 2, "sql_mutants_rejected": killed,
              "scope": "HOST_SQLITE_ACTUAL_DDL_AND_TEST_QUERY_NOT_ANDROID"}
    print("NOTE_ORDER_PROJECTION_HOST "+json.dumps(result), flush=True)
    return result


def selftest():
    result = _before_order_selftest()
    result["ordering_backend"] = order_selftest()
    result["ordering_projection"] = order_projection_selftest()
    result["ordering_ui_report"] = report_ordering_selftest()
    result["editor_ui_report"] = report_editor_selftest()
    return result


_order_entry = '   verify();deleteVerify();need(count==18,"contract count");'
assert JAVA.count(_order_entry) == JAVA.count(_declaration) == 1
JAVA = JAVA.replace(_order_entry, '   verify();deleteVerify();orderVerify();need(count==18,"contract count");', 1)
JAVA = JAVA.replace(_declaration, ORDER_JAVA+"\n"+_declaration, 1)


def report_ordering_selftest():
    """Independent report contract; fixtures never claim Android execution."""
    def good(api=26):
        return {"status": "PASS",
                "scope": "NATIVE_NOTE_ORDER_STABLE_ID_FORCE_STOP_RESTART_NOT_LMK",
                "api": api, "commit": "source", "run_id": "run", "apk_sha256": "a"*64,
                "release_ready": False,
                "labels": ["boundary_controls", "singleton_disabled_readonly",
                           "same_title_up_exact_state", "restart_up_summary_order",
                           "same_title_down_exact_state", "restart_down_summary_order",
                           "original_order_restored_two_revisions", "all_media_preserved"],
                "checks": 8, "note_id": "third", "sibling_id": "second", "owner": 1,
                "editor_ui": report_editor_sample(api),
                "state": "EXACT_OWNER_SLOT_SWAP_PER_MOVE_TWO_REVISIONS_ALL_OTHER_TABLES_MEDIA_UNCHANGED"}
    def parents(value, api=26):
        batch = {"status": "PASS", "note_management": sample(api),
                 "deletion_ui": report_ui_sample(api), "order_ui": value}
        return ({"status": "PASS", "api": api, "commit": "source", "run_id": "run",
                 "release_ready": False, "apk_sha256": "a"*64, "batch_ui": copy.deepcopy(batch)},
                {"status": "PASS", "batch_ui": copy.deepcopy(batch)})
    # Regression red: current aggregate accepts both parents with no order UI.
    absent = list(parents(good()))
    for side in absent:
        del side["batch_ui"]["order_ui"]
    assert aggregate(*absent, 26, "source", "run")["status"] == "NOT_VERIFIED", "missing ordering evidence accepted"
    for api in (26, 34):
        pair = parents(good(api), api); frozen = copy.deepcopy(pair)
        result = aggregate(*pair, api, "source", "run")
        assert result["status"] == result["order_ui"]["status"] == "PASS"
        assert result["order_ui"]["checks"] == 8 and pair == frozen
        assert report_ordering_ui(good(api), api, "source", "run", "a"*64)
    value = good()
    bad = [None, {}, []]
    for key in value:
        item = copy.deepcopy(value); del item[key]; bad.append(item)
    for key, replacement in (
        ("status", "FAIL"), ("scope", "BACKEND_ONLY"), ("api", 34), ("api", True),
        ("api", 26.0), ("commit", "old"), ("run_id", "old"), ("apk_sha256", "b"*64),
        ("release_ready", True), ("release_ready", 0), ("checks", True), ("checks", 8.0),
        ("checks", 7), ("note_id", ""), ("note_id", " "), ("note_id", None),
        ("sibling_id", ""), ("sibling_id", " "), ("sibling_id", None),
        ("sibling_id", "third"), ("owner", True), ("owner", 1.0), ("owner", 0),
        ("owner", -1), ("state", "NOT_VERIFIED"), ("labels", value["labels"][::-1]),
    ):
        item = copy.deepcopy(value); item[key] = replacement; bad.append(item)
    for index in range(8):
        for mode in ("missing", "duplicate", "substituted"):
            item = copy.deepcopy(value)
            if mode == "missing": item["labels"].pop(index)
            elif mode == "duplicate": item["labels"].insert(index, item["labels"][index])
            else: item["labels"][index] = "unrelated"
            item["checks"] = len(item["labels"]); bad.append(item)
    pairs = [absent]
    for item in bad:
        assert not report_ordering_ui(item, 26, "source", "run", "a"*64)
        pairs.append(parents(item))
    for side in (0, 1):
        pair = list(parents(value)); del pair[side]["batch_ui"]["order_ui"]; pairs.append(pair)
        for key, replacement in (("note_id", "different"), ("sibling_id", "different"), ("owner", 2)):
            pair = list(parents(value)); pair[side]["batch_ui"]["order_ui"][key] = replacement
            pair[side]["batch_ui"]["order_ui"]["editor_ui"][key] = replacement
            assert report_ordering_ui(pair[side]["batch_ui"]["order_ui"], 26, "source", "run", "a"*64)
            pairs.append(pair)
        for key, replacement in (("owner", True), ("owner", 1.0), ("checks", 8.0), ("release_ready", 0)):
            pair = list(parents(value)); pair[side]["batch_ui"]["order_ui"][key] = replacement
            assert pair[0]["batch_ui"]["order_ui"] == pair[1]["batch_ui"]["order_ui"]
            pairs.append(pair)
        for level in ("parent", "batch", "backend", "deletion"):
            pair = list(parents(value))
            if level == "parent": pair[side]["status"] = "FAIL"
            elif level == "batch": pair[side]["batch_ui"]["status"] = "FAIL"
            elif level == "backend": del pair[side]["batch_ui"]["note_management"]
            else: del pair[side]["batch_ui"]["deletion_ui"]
            pairs.append(pair)
    for key, replacement in (("api", True), ("api", 34), ("commit", "old"),
                             ("run_id", "old"), ("apk_sha256", "b"*64), ("release_ready", True)):
        pair = list(parents(value)); pair[0][key] = replacement; pairs.append(pair)
    # Two parents cannot manufacture acceptance with an invalid but matching digest.
    for apk in (None, "", "a"*63, "A"*64, "g"*64):
        assert not report_ordering_ui(dict(value, apk_sha256=apk), 26, "source", "run", apk)
    for pair in pairs:
        result = aggregate(*pair, 26, "source", "run")
        assert result["status"] == result["order_ui"]["status"] == "NOT_VERIFIED"
        assert result["order_ui"]["checks"] == 0, "failed ordering report retained success count"
    import inspect
    source = inspect.getsource(aggregate)
    killed = 0
    for old in (
        'order_value == n.get("order_ui")',
        "report_ordering_ui(order_value, api, source, run, apk)",
        'report_ordering_ui(n.get("order_ui"), api, source, run, apk)',
        "ordered = (passed and",
    ):
        assert source.count(old) == 1
        replacement = "ordered = (True and" if old.startswith("ordered =") else "True"
        namespace = dict(globals())
        exec(compile(source.replace(old, replacement, 1), "<order-report-mutant>", "exec"), namespace)
        checker = namespace["aggregate"]
        assert checker(*parents(value), 26, "source", "run")["status"] == "PASS"
        assert any(checker(*pair, 26, "source", "run")["status"] == "PASS" for pair in pairs), old
        killed += 1
    result = {"positive": 2, "receipt_negative": len(bad)+5,
              "aggregate_negative": len(pairs), "permanent_report_mutants": killed,
              "scope": "HOST_INDEPENDENT_REPORT_NOT_ANDROID_EXECUTION"}
    print("NOTE_ORDER_UI_REPORT_HOST "+json.dumps(result), flush=True)
    return result


def report_editor_selftest():
    def parents(editor, api=26):
        order = report_ordering_sample(api)
        order["editor_ui"] = copy.deepcopy(editor)
        batch = {"status": "PASS", "note_management": sample(api),
                 "deletion_ui": report_ui_sample(api), "order_ui": order}
        return ({"status": "PASS", "api": api, "commit": "source", "run_id": "run",
                 "release_ready": False, "apk_sha256": "a"*64, "batch_ui": copy.deepcopy(batch)},
                {"status": "PASS", "batch_ui": copy.deepcopy(batch)})
    absent = parents(None)
    for parent in absent:
        del parent["batch_ui"]["order_ui"]["editor_ui"]
    assert aggregate(*absent, 26, "source", "run")["status"] == "NOT_VERIFIED", "missing editor evidence accepted"
    for api in (26, 34):
        good = report_editor_sample(api)
        pair = parents(good, api); frozen = copy.deepcopy(pair)
        result = aggregate(*pair, api, "source", "run")
        assert result["status"] == result["editor_ui"]["status"] == "PASS"
        assert result["editor_ui"]["checks"] == 6 and pair == frozen
    good = report_editor_sample()
    invalid = [None, {}, [], True]
    for key in good:
        bad = copy.deepcopy(good); del bad[key]; invalid.append(bad)
    for key, value in (
        ("status", "FAIL"), ("scope", "HOST_ONLY"), ("api", 34), ("api", True), ("api", 26.0),
        ("commit", "old"), ("run_id", "old"), ("apk_sha256", "b"*64),
        ("release_ready", True), ("release_ready", 0), ("checks", True), ("checks", 6.0),
        ("checks", 5), ("owner", True), ("owner", 1.0), ("owner", 0), ("owner", 2),
        ("note_id", ""), ("note_id", "second"), ("note_id", "different"),
        ("sibling_id", "third"), ("sibling_id", "different"), ("sibling_id", None),
        ("state", "NOT_VERIFIED"), ("labels", good["labels"][::-1]),
    ):
        bad = copy.deepcopy(good); bad[key] = value; invalid.append(bad)
    for i in range(6):
        for mode in ("missing", "duplicate", "substituted"):
            bad = copy.deepcopy(good)
            if mode == "missing": bad["labels"].pop(i)
            elif mode == "duplicate": bad["labels"].insert(i, bad["labels"][i])
            else: bad["labels"][i] = "unrelated"
            bad["checks"] = len(bad["labels"]); invalid.append(bad)
    pairs = [absent]
    for value in invalid:
        assert not report_editor_ui(value, 26, "source", "run", "a"*64, 1, "third", "second")
        pairs.append(parents(value))
        for side in (0, 1):
            pair = parents(good); pair[side]["batch_ui"]["order_ui"]["editor_ui"] = value
            pairs.append(pair)
    for side in (0, 1):
        pair = parents(good); del pair[side]["batch_ui"]["order_ui"]["editor_ui"]; pairs.append(pair)
        for level in ("parent", "batch", "order", "backend", "deletion"):
            pair = parents(good)
            target = pair[side] if level == "parent" else pair[side]["batch_ui"]
            if level == "order": target = target["order_ui"]
            if level == "backend": target = target["note_management"]
            if level == "deletion": target = target["deletion_ui"]
            target["status"] = "FAIL"; pairs.append(pair)
    for pair in pairs:
        result = aggregate(*pair, 26, "source", "run")
        assert result["status"] == result["editor_ui"]["status"] == "NOT_VERIFIED"
        assert result["editor_ui"]["checks"] == 0
    import inspect
    original = inspect.getsource(report_editor_ui)
    for old in (
        'value.get("labels") == REPORT_EDITOR_UI_LABELS',
        'value.get("apk_sha256") == apk',
        'value.get("note_id") == note',
        'type(value.get("owner")) is int',
    ):
        assert original.count(old) == 1
        namespace = dict(globals())
        exec(original.replace(old, "True"), namespace)
        assert namespace["report_editor_ui"](good, 26, "source", "run", "a"*64, 1, "third", "second")
        assert any(namespace["report_editor_ui"](bad, 26, "source", "run", "a"*64, 1, "third", "second") for bad in invalid)
    result = {"positive": 2, "receipt_negative": len(invalid), "aggregate_negative": len(pairs),
              "permanent_report_mutants": 4, "scope": "HOST_INDEPENDENT_EDITOR_REPORT_NOT_ANDROID_EXECUTION"}
    print("NOTE_EDITOR_REPORT_HOST "+json.dumps(result), flush=True)
    return result


def note_signing_case(checker, mode="fixed", api=26, fault=None, keytool=None):
    """Host-only: execute the actual Python native caller with controlled APK/adb
    doubles. Gradle and Android are NOT executed. Existing receipt/Java tests run
    separately, unchanged. Optional keytool callback permits a real ephemeral key.
    """
    import contextlib
    import io
    import secrets
    import sys
    import types
    from unittest.mock import patch
    import verify_paged_exports as paged
    calls, registrations, stops = [], [], []
    caught = None
    with tempfile.TemporaryDirectory(prefix="note-signing-host-") as temporary:
        root = Path(temporary)
        tools = root/"tools"; tools.mkdir()
        product_path = root/"build/outputs/apk/debug/app.apk"
        test_path = root/"build/outputs/apk/androidTest/debug/test.apk"
        for path in (product_path, test_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        product, saved, rebuilt = b"HOST_PRODUCT", b"HOST_DEFAULT_TEST", b"HOST_NOTE_TEST"
        product_path.write_bytes(product); test_path.write_bytes(saved)
        folder = root/"pocket-signing-26"; folder.mkdir(mode=0o700)
        key, config = folder/"preview.jks", folder/"credentials.json"
        key.write_bytes(b"HOST_KEYTOOL_DOUBLE"); key.chmod(0o600)
        der = b"HOST_CERTIFICATE_DOUBLE"
        cert = hashlib.sha256(der).hexdigest()
        password = secrets.token_hex(18) + "'\"\\"
        values = dict(alias="non-default-alias", storePassword=password,
                      keyPassword=password, certificate=cert)
        if keytool is not None:
            der, values = keytool("prepare", key, values)
            cert = hashlib.sha256(der).hexdigest()
            assert values["certificate"] == cert
            password = values["storePassword"]
        if fault == "wrong_certificate":
            values["certificate"] = "0"*64
        config.write_text(json.dumps(values)); config.chmod(0o600)
        if fault == "permissions":
            config.chmod(0o644)
        home = root/"home"; home.mkdir()
        debug = home/".android/debug.keystore"
        if mode == "disposable":
            debug.parent.mkdir(); debug.write_bytes(b"HOST_DEBUG_KEY")
        env = dict(HOME=str(home), RUNNER_TEMP=str(root), POCKET_SIGNING_DIR=str(folder),
                   GITHUB_ACTIONS="true", GITHUB_SHA="host-source", GITHUB_RUN_ID="123",
                   GITHUB_RUN_ATTEMPT="1")
        for name in ("PATH", "JAVA_HOME"):
            if name in os.environ:
                env[name] = os.environ[name]
        if mode == "fixed":
            env["POCKET_STABLE_SIGNING"] = "1"
        if fault == "invalid_mode":
            env["POCKET_STABLE_SIGNING"] = "0"
        gate = types.SimpleNamespace(SERIAL="host-serial", API=api, PKG="host.package")
        installed_calls = 0
        snapshot_calls = 0
        built = False
        diagnostic = ("java.lang.AssertionError: note_management_diagnostic_sentinel\n"
                      "NOTE_MANAGEMENT_FAILED\nINSTRUMENTATION_CODE: 0")
        def certificate(path, gate):
            if fault == "test_certificate" and built and Path(path) == test_path:
                return "f"*64
            return cert
        def registration(adb, gate, stage, runner):
            assert runner == "V12DeviceTest"
            registrations.append(stage)
        def snapshot():
            nonlocal snapshot_calls
            snapshot_calls += 1
            return {"table": [snapshot_calls if fault == "state" else 1], "media": b"same"}
        def dispatch(args, **kwargs):
            nonlocal installed_calls, built
            args = list(map(str, args)); calls.append((args, kwargs.get("timeout")))
            if args[0] == "keytool":
                if keytool is not None:
                    return keytool("export", args, kwargs)
                assert kwargs["timeout"] == 20
                if mode == "fixed":
                    assert args[-2:] == ["-storepass:env", "PAGED_STORE_PASSWORD"]
                    assert kwargs["env"]["PAGED_STORE_PASSWORD"] == password
                else:
                    assert args[-4:] == ["-alias", "androiddebugkey", "-storepass", "android"]
                return subprocess.CompletedProcess(args, 0, der, b"")
            if args[0] == "gradle":
                assert args[:4] == ["gradle", "--no-daemon", "--console=plain", "-I"]
                assert args[5:] == ["assembleDebugAndroidTest"] and kwargs["timeout"] == 300
                script = Path(args[4]).read_text()
                assert "ci.notes.NoteManagementInstrumentation" in script
                assert password not in script
                if mode == "fixed":
                    for line in ("s.storePassword = c.storePassword", "s.keyAlias = c.alias",
                                 "s.keyPassword = c.keyPassword",
                                 "dsl.buildTypes.getByName('debug').signingConfig = s"):
                        assert line in script, "NOTE_HOST_DSL_MISSING "+line
                else:
                    assert str(debug) in script and "storePassword" not in script
                built = True; test_path.write_bytes(rebuilt)
                if fault == "product":
                    product_path.write_bytes(b"CHANGED")
                output = ("host-build " + password + " " + json.dumps(password)[1:-1] +
                          " " + repr(password)[1:-1]) if mode == "fixed" else "host-build"
                if fault == "timeout":
                    raise subprocess.TimeoutExpired(args, 300, output=output)
                return subprocess.CompletedProcess(args, 7 if fault == "build" else 0, output, "")
            assert args[:3] == ["host-adb", "-s", gate.SERIAL], args
            tail = args[3:]; timeout = kwargs["timeout"]
            out = ""
            if tail == ["shell", "-n", "-T", "pm", "path", gate.PKG]:
                assert timeout == 40; out = "package:/host/app.apk\n"
            elif tail == ["exec-out", "cat", "/host/app.apk"]:
                assert timeout == 40 and kwargs["text"] is False
                installed_calls += 1
                out = b"BAD_INSTALLED" if fault == "installed" and installed_calls == 2 else product
                return subprocess.CompletedProcess(args, 0, out, b"")
            elif tail[:3] == ["install", "-r", "-t"]:
                assert timeout == 120
                payload = Path(tail[3]).read_bytes()
                assert payload == (saved if Path(tail[3]).name == "default-test.apk" else rebuilt)
                if fault == "restore" and payload == saved:
                    return subprocess.CompletedProcess(args, 9, "", "HOST_RESTORE_FAILURE")
            elif tail == ["shell", "-n", "-T", "pm", "list", "instrumentation"]:
                out = "instrumentation:host.package.test/ci.notes.NoteManagementInstrumentation (target=host.package)"
            elif tail[:6] == ["shell", "-n", "-T", "am", "instrument", "-w"]:
                if "diagnostic" in tail:
                    assert timeout == 60
                    out = "BAD_DIAGNOSTIC" if fault == "diagnostic" else diagnostic
                else:
                    assert timeout == 180
                    if fault == "device":
                        raise RuntimeError("HOST_DEVICE_FAILURE")
                    out = "HOST_DEVICE_SUCCESS"
            else:
                raise AssertionError("unexpected host command "+repr(args))
            return subprocess.CompletedProcess(args, 0, out, "")
        schema = types.ModuleType("verify_schema3")
        schema.certificate = certificate
        schema.require_registration = registration
        schema.exception_evidence = lambda exc: {"type": type(exc).__name__, "message": str(exc)}
        control = types.ModuleType("verify_process_control")
        control.stop_verified = lambda *args: stops.append(args)
        observed = []
        def observe(text, api, package):
            assert text.strip() == "HOST_DEVICE_SUCCESS"
            observed.append((api, package))
            return ["HOST_CALLER_WITNESS"]
        namespace = dict(checker.__globals__, __file__=str(tools/"verify_note_management.py"),
                         JAVA="// HOST_ONLY_NOT_COMPILED", SCOPE="HOST_ONLY",
                         observe=observe, log_accepted=lambda text, api: False,
                         accepted=lambda *args: True)
        actual = types.FunctionType(checker.__code__, namespace, checker.__name__,
                                    checker.__defaults__, checker.__closure__)
        cwd = Path.cwd()
        capture = io.StringIO()
        try:
            os.chdir(root)
            with patch.dict(os.environ, env, clear=True), patch.dict(sys.modules,
                    verify_schema3=schema, verify_process_control=control), \
                    patch.object(Path, "home", return_value=home), \
                    patch.object(subprocess, "run", dispatch), \
                    contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                try:
                    actual("host-adb", gate, snapshot)
                except Exception as exc:
                    caught = exc
        finally:
            os.chdir(cwd)
        receipt = json.loads((root/"native-ui/note-management-result.json").read_text())
        visible = capture.getvalue()+str(caught)+json.dumps(receipt)
        for path in (root/"native-ui").iterdir():
            if path.is_file():
                visible += path.read_text()
        for secret in (password, values["keyPassword"]):
            assert secret not in visible and json.dumps(secret)[1:-1] not in visible
            assert repr(secret)[1:-1] not in visible
        if fault in ("invalid_mode", "wrong_certificate", "permissions"):
            assert type(caught) is AssertionError and "PAGED_" in str(caught), repr(caught)
            assert not built and not any("install" in a for a, _ in calls)
        elif fault:
            assert caught is not None and built, "negative did not reach build: "+repr(caught)
            if fault == "build":
                assert type(caught) is RuntimeError and "exit=7" in str(caught)
            if fault == "timeout":
                assert type(caught) is RuntimeError and "timed out" in str(caught)
            if fault == "device":
                assert str(caught) == "HOST_DEVICE_FAILURE"
            if fault == "restore":
                assert isinstance(caught, subprocess.CalledProcessError) and caught.returncode == 9
            if fault == "state":
                assert str(caught) == "note management instrumentation changed live tables/media"
            assert any("default-test.apk" in " ".join(a) for a, _ in calls)
            if fault not in ("restore", "product"):
                assert test_path.read_bytes() == saved and registrations[-1] == "notes-restored"
        else:
            if caught is not None:
                raise caught
            assert receipt["status"] == "PASS" and observed == [(api, gate.PKG)]
            assert product_path.read_bytes() == product and test_path.read_bytes() == saved
            assert registrations == ["notes-before", "notes-restored"]
            assert installed_calls == 3 and snapshot_calls == 2 and len(stops) == 2
            installs = [a[3:] for a, _ in calls if a[:3] == ["host-adb", "-s", gate.SERIAL]
                        and len(a) > 3 and a[3] == "install"]
            assert len(installs) == 2 and installs[0] == ["install", "-r", "-t", str(test_path)]
            assert installs[1][:3] == ["install", "-r", "-t"]
            assert Path(installs[1][3]).name == "default-test.apk", "original test install omitted"
            assert sum(a[0] == "gradle" for a, _ in calls) == 1
            assert sum(a[0] == "keytool" for a, _ in calls) == (2 if mode == "fixed" else 1)
        if caught is not None:
            assert receipt["status"] == "FAIL" and receipt["error"]["type"] == type(caught).__name__
        return {"mode": mode, "api": api, "fault": fault, "built": built,
                "scope": "HOST_CALLER_WITH_BUILD_AND_ADB_DOUBLES_NOT_ANDROID"}


def note_signing_wiring(sources):
    """Guard the three known fixed-signing build consumers, not every separate
    disposable workflow. Inspect executable AST, never comments or Java strings.
    """
    import ast
    contracts = {"native": (300, "assembleDebugAndroidTest"),
                 "instrumentation": (300, "assembleDebugAndroidTest"),
                 "apk_size_comparison": (360, "assembleDebug")}
    assert set(sources) == set(contracts)
    for name, (budget, task) in contracts.items():
        module = ast.parse(sources[name])
        functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name]
        assert len(functions) == 1, "missing fixed signing consumer "+name
        node = functions[0]
        calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
        def named(target):
            return [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == target]
        assert not named("debug_key"), "old debug lookup in "+name
        for target in ("paged_signing", "paged_signing_dsl", "paged_signing_build"):
            assert len(named(target)) == 1, (name, target, "missing or repeated")
        build = named("paged_signing_build")[0]
        assert ast.literal_eval(build.keywords[0].value) == budget if build.keywords else (
            len(build.args) == 3 and ast.literal_eval(build.args[2]) == budget)
        command = build.args[0]
        assert isinstance(command, ast.List)
        assert ast.literal_eval(command.elts[0]) == "gradle"
        assert ast.literal_eval(command.elts[-1]) == task
        for call in calls:
            if call is build or not call.args or not isinstance(call.args[0], ast.List):
                continue
            elements = call.args[0].elts
            assert not (elements and isinstance(elements[0], ast.Constant) and
                        elements[0].value == "gradle"), "unwrapped Gradle in "+name
    return len(contracts)


def note_main_chain_wiring(source):
    """Validate the batch entry edges in real Python AST, not Java/text matches."""
    import ast
    tree = ast.parse(source)
    def edge(parent, wanted):
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == parent]
        assert functions, "missing main-chain function "+parent
        expected = ast.dump(ast.parse(wanted, mode="eval").body, include_attributes=False)
        found = [node for fn in functions for node in ast.walk(fn)
                 if isinstance(node, ast.Call) and ast.dump(node, include_attributes=False) == expected]
        assert len(found) == 1, "missing or repeated main-chain edge "+wanted
    edge("native", "note_management.native(adb, gate, state)")
    edge("selftest", "note_management.selftest()")
    installs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "install"]
    assert len(installs) == 1
    expected = ast.parse(
        "def install(gate):\n"
        "    previous = gate.verify_native_ui\n"
        "    def previous_then_batch(adb):\n"
        "        previous(adb)\n"
        "        native(adb, gate)\n"
        "    gate.verify_native_ui = previous_then_batch\n").body[0]
    assert ast.dump(installs[0], include_attributes=False) == ast.dump(expected, include_attributes=False)
    return 3


def note_signing_selftest():
    import ast
    import inspect
    import verify_paged_exports as paged
    source = inspect.getsource(native)
    cases = [("fixed", 26, None), ("fixed", 34, None), ("disposable", 26, None)]
    cases += [("fixed", 26, fault) for fault in (
        "invalid_mode", "wrong_certificate", "permissions", "build", "timeout",
        "product", "test_certificate", "installed", "diagnostic", "device", "restore", "state")]
    for mode, api, fault in cases:
        note_signing_case(native, mode, api, fault)
    def changed(old, new):
        assert source.count(old) == 1, old
        modified = source.replace(old, new, 1)
        assert modified != source
        namespace = dict(globals())
        exec(compile(modified, "<note-signing-mutant>", "exec"), namespace)
        return namespace["native"]
    mutants = [
        ("signing = paged_signing(cert)",
         "signing = dict(mode='disposable', key=str(__import__('verify_paged_exports').debug_key(cert)))",
         ("disposable", 26, None)),
        ("+paged_signing_dsl(signing)+",
         '''+(" dsl.signingConfigs.getByName('debug').storeFile = new File("+json.dumps(signing["key"])+")\\n")+''',
         ("disposable", 26, None)),
        ('log = paged_signing_build(["gradle", "--no-daemon", "--console=plain", "-I", init, "assembleDebugAndroidTest"], signing, 300)',
         'log = command(["gradle", "--no-daemon", "--console=plain", "-I", init, "assembleDebugAndroidTest"], 300)',
         ("disposable", 26, None)),
        ('command(prefix+["install", "-r", "-t", backup], 120)',
         'pass # deliberately omit restore install',
         ("fixed", 26, "invalid_mode")),
    ]
    killed = []
    for old, new, witness in mutants:
        checker = changed(old, new)
        # Plausible mutant must first pass a case in which its defect is dormant.
        note_signing_case(checker, *witness)
        try:
            note_signing_case(checker)
        except (AssertionError, RuntimeError):
            killed.append(old)
        else:
            raise AssertionError("note signing mutant escaped "+old)
    sources = dict(native=source, instrumentation=inspect.getsource(paged.instrumentation),
                   apk_size_comparison=inspect.getsource(paged.apk_size_comparison))
    assert note_signing_wiring(sources) == 3
    wiring_killed = []
    for name in sources:
        for target in ("paged_signing", "paged_signing_dsl", "paged_signing_build"):
            tree = ast.parse(sources[name])
            nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
                     isinstance(n.func, ast.Name) and n.func.id == target]
            assert len(nodes) == 1
            nodes[0].func.id = "omitted_"+target
            modified = dict(sources, **{name: ast.unparse(tree)})
            # Unchanged parsing/shape still succeeds; the shared checker must reject.
            assert len([n for n in ast.parse(modified[name]).body if isinstance(n, ast.FunctionDef)]) == 1
            try:
                note_signing_wiring(modified)
            except AssertionError:
                wiring_killed.append(name+"."+target)
            else:
                raise AssertionError("caller omission escaped")
    root = Path(__file__).resolve().parents[1]
    batch = (root/"tools/verify_batch_exports.py").read_text()
    assert note_main_chain_wiring(batch) == 3
    chain_killed = []
    for parent, method in (("native", "native"), ("selftest", "selftest"), ("install", "native")):
        tree = ast.parse(batch)
        matched = []
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef) or fn.name != parent:
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                target = node.func
                if parent != "install" and isinstance(target, ast.Attribute) and (
                        isinstance(target.value, ast.Name) and target.value.id == "note_management" and
                        target.attr == method):
                    target.attr = "omitted_"+method; matched.append(node)
                elif parent == "install" and isinstance(target, ast.Name) and target.id == method:
                    target.id = "omitted_"+method; matched.append(node)
        assert len(matched) == 1
        mutant = ast.unparse(tree)
        assert len(ast.parse(mutant).body) == len(ast.parse(batch).body)
        try:
            note_main_chain_wiring(mutant)
        except AssertionError:
            chain_killed.append(parent)
        else:
            raise AssertionError("main-chain omission escaped "+parent)
    result = dict(cases=len(cases), caller_mutants=len(killed), known_consumers=len(sources),
                  wiring_mutants=len(wiring_killed),
                  main_chain_edges=3, main_chain_mutants=len(chain_killed),
                  scope="HOST_PYTHON_CALLER_NOT_FULL_PROJECT_GRADLE_OR_ANDROID")
    assert (result["cases"], result["caller_mutants"], result["known_consumers"],
            result["wiring_mutants"], result["main_chain_mutants"]) == (15, 4, 3, 9, 3)
    print("NOTE_SIGNING_HOST "+json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    import sys
    assert sys.argv[1:] == ["selftest"]
    selftest()
