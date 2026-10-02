#!/usr/bin/env python3
"""Independent test-first todo backend gate. No native UI or delivery acceptance."""
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "com.supercubegame.pockettodo.v12.preview"
SCOPE = "ACTUAL_INSTALLED_TODO_SQLITE_RESTART_BACKUP_NOT_NATIVE_UI_OR_CROSS_RESTART_UNDO"
REPORT_REQUIRED = {
    "seed": """fixture_same_title_done_position preview_exact preview_readonly cancel_readonly
cancel_consumed missing_target wrong_helper_preview foreign_attempt_keeps_owner
delete_exact undo_exact undo_consumed delete_consumed same_revision_stale_delete
stale_delete_readonly stale_delete_consumed same_revision_stale_undo stale_undo_readonly
stale_undo_consumed closed_helper_preview closed_helper_undo outer_preview
outer_delete outer_delete_readonly outer_undo outer_undo_readonly
late_delete_error late_delete_rollback late_delete_consumed late_undo_error
late_undo_rollback late_undo_consumed media_unchanged deletion_restart_saved""".split(),
    "deleted": """deleted_restart_exact deleted_restart_media deleted_backup_exact
deleted_backup_order undo_fixture_exact undo_restart_saved""".split(),
    "undone": """undone_restart_exact undone_restart_media undone_backup_exact
undone_backup_order""".split(),
}
REQUIRED = {
    "seed": """fixture_same_title_done_position preview_exact preview_readonly cancel_readonly
cancel_consumed missing_target wrong_helper_preview foreign_attempt_keeps_owner
delete_exact undo_exact undo_consumed delete_consumed same_revision_stale_delete
stale_delete_readonly stale_delete_consumed same_revision_stale_undo stale_undo_readonly
stale_undo_consumed closed_helper_preview closed_helper_undo outer_preview
outer_delete outer_delete_readonly outer_undo outer_undo_readonly
late_delete_error late_delete_rollback late_delete_consumed late_undo_error
late_undo_rollback late_undo_consumed media_unchanged deletion_restart_saved""".split(),
    "deleted": """deleted_restart_exact deleted_restart_media deleted_backup_exact
deleted_backup_order undo_fixture_exact undo_restart_saved""".split(),
    "undone": """undone_restart_exact undone_restart_media undone_backup_exact
undone_backup_order""".split(),
}

JAVA = r'''
package ci.todos;
import android.app.Instrumentation;
import android.os.Bundle;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import com.supercubegame.pockettodo.AppDatabase;
import com.supercubegame.pockettodo.MediaRepository;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

public final class TodoInstrumentation extends Instrumentation {
 private Bundle args; private int count; private Path folder; private String name;
 private MediaRepository media; private String mediaId;
 private static final byte[] ASSET={0,7,3,9,1,4,8,2};
 private static final String TITLE="相同待办😀";
 interface Action {void run()throws Exception;}
 static void need(boolean b,String label){if(!b)throw new AssertionError(label);}
 void pass(boolean b,String label){need(b,label);count++;System.out.println("TODO_PASS "+label);}
 static Throwable cause(Throwable t){while(t instanceof InvocationTargetException)t=t.getCause();return t;}
 void reject(Class<? extends Throwable> type,Action action,String label)throws Exception{
  Throwable caught=null;try{action.run();}catch(Throwable t){caught=cause(t);}
  pass(caught!=null&&type.isInstance(caught),label);
 }
 static Object call(Object owner,String method,Class<?>[] types,Object...values)throws Exception{
  try{return owner.getClass().getMethod(method,types).invoke(owner,values);}
  catch(InvocationTargetException e){Throwable t=e.getCause();if(t instanceof Exception)throw (Exception)t;if(t instanceof Error)throw (Error)t;throw new AssertionError(t);}
 }
 static Object plan(AppDatabase h,String id)throws Exception{
  return call(h,"prepareTodoDeletion",new Class<?>[]{String.class},id);
 }
 static Object remove(AppDatabase h,Object p)throws Exception{
  return call(h,"confirmTodoDeletion",new Class<?>[]{p.getClass()},p);
 }
 static void undo(AppDatabase h,Object token)throws Exception{
  call(h,"undoTodoDeletion",new Class<?>[]{token.getClass()},token);
 }
 static void close(Object p)throws Exception{((AutoCloseable)p).close();}
 static Object getter(Object p,String method)throws Exception{return call(p,method,new Class<?>[]{});}
 static Map<String,List<List<String>>> state(AppDatabase h){
  Map<String,List<List<String>>> out=new TreeMap<>();SQLiteDatabase db=h.getReadableDatabase();
  try(Cursor tables=db.rawQuery("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",null)){
   while(tables.moveToNext()){
    String table=tables.getString(0);need(table.matches("[A-Za-z0-9_]+"),"table name");
    List<List<String>> rows=new ArrayList<>();
    try(Cursor c=db.rawQuery("SELECT rowid AS rowid,* FROM \""+table+"\" ORDER BY rowid",null)){
     rows.add(Arrays.asList(c.getColumnNames()));
     while(c.moveToNext()){
      List<String> row=new ArrayList<>();
      for(int i=0;i<c.getColumnCount();i++){
       int type=c.getType(i);String value=type==0?"":type==4?android.util.Base64.encodeToString(c.getBlob(i),2):c.getString(i);
       row.add(type+":"+value);
      }rows.add(row);
     }
    }out.put(table,rows);
   }
  }return out;
 }
 static Map<String,List<List<String>>> expected(Map<String,List<List<String>>> before,boolean deleted,int delta){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();for(List<String> row:e.getValue())rows.add(new ArrayList<>(row));out.put(e.getKey(),rows);
  }
  if(deleted){
   int n=0;Iterator<List<String>> it=out.get("todos").iterator();it.next();
   while(it.hasNext())if(it.next().get(1).equals("3:target")){it.remove();n++;}
   need(n==1,"exact target fixture");
  }
  List<List<String>> revisions=out.get("revision");need(revisions.size()==2,"single revision");
  List<String> row=revisions.get(1);long value=Long.parseLong(row.get(2).substring(2));
  row.set(2,"1:"+Math.addExact(value,delta));return out;
 }
 static List<String> todoRows(AppDatabase h){
  List<String> rows=new ArrayList<>();
  try(Cursor c=h.getReadableDatabase().rawQuery("SELECT id,title,done,position FROM todos ORDER BY position",null)){
   while(c.moveToNext())rows.add(c.getString(0)+"|"+c.getString(1)+"|"+c.getInt(2)+"|"+c.getLong(3));
  }return rows;
 }
 AppDatabase fresh(String suffix)throws Exception{
  String file=name.replace(".db",suffix+".db");
  need(!getTargetContext().getDatabasePath(file).exists(),"fresh fixture "+suffix);
  AppDatabase h=AppDatabase.openSchema3(getTargetContext(),file);
  h.addCategory(1,"Keep category");h.addActivity(1,1,0,"Keep activity");
  h.createNote("keep-note",1,"Keep note");
  h.addTodo("first",TITLE);h.addTodo("target",TITLE);h.addTodo("last","Keep last");
  h.editTodo("target",TITLE,true);
  h.getWritableDatabase().execSQL("UPDATE todos SET position=position+10");
  return h;
 }
 void mediaExact(String label)throws Exception{
  pass(Arrays.equals(ASSET,Files.readAllBytes(media.path(mediaId))),label);
 }
 static void save(Path file,String text)throws Exception{
  Files.write(file,text.getBytes("UTF-8"),StandardOpenOption.CREATE_NEW);
 }
 static String read(Path file)throws Exception{return new String(Files.readAllBytes(file),"UTF-8");}
 void saveRestart(AppDatabase h,String phase)throws Exception{
  save(folder.resolve(phase+".state"),state(h).toString());
  Files.write(folder.resolve(phase+".canonical"),h.exportState(),StandardOpenOption.CREATE_NEW);
  save(folder.resolve(phase+".order"),todoRows(h).toString());
  h.exportBackup(folder.resolve(phase+".zip"),media);
 }
 void backup(AppDatabase original,String phase)throws Exception{
  String restored=name.replace(".db","-restore-"+phase+".db");
  need(!getTargetContext().getDatabasePath(restored).exists(),"fresh restored DB");
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),restored)){
   h.addTodo("replacement","Must disappear");
   try(AppDatabase.RestorePlan p=h.prepareRestore(folder.resolve(phase+".zip"),folder.resolve("stage-"+phase),64L*1024*1024)){
    h.confirmRestore(p,media);
   }
   pass(Arrays.equals(h.exportState(),Files.readAllBytes(folder.resolve(phase+".canonical"))),phase+"_backup_exact");
   pass(todoRows(h).equals(todoRows(original))&&todoRows(h).toString().equals(read(folder.resolve(phase+".order"))),phase+"_backup_order");
  }
 }
 void seed()throws Exception{
  need(!Files.exists(folder),"fresh fixture root");Files.createDirectory(folder);
  media=new MediaRepository(folder.resolve("media"),64L*1024*1024);
  mediaId=media.copy(new ByteArrayInputStream(ASSET));save(folder.resolve("media-id"),mediaId);
  try(AppDatabase h=fresh("")){
   h.registerMedia(mediaId,"application/octet-stream",ASSET.length);
   Map<String,List<List<String>>> before=state(h);
   pass(todoRows(h).equals(Arrays.asList("first|"+TITLE+"|0|10","target|"+TITLE+"|1|11","last|Keep last|0|12")),"fixture_same_title_done_position");
   Object p=plan(h,"target");
   pass(getter(p,"todoId").equals("target")&&getter(p,"title").equals(TITLE)&&getter(p,"done").equals(true)&&getter(p,"position").equals(11L),"preview_exact");
   pass(state(h).equals(before),"preview_readonly");close(p);
   pass(state(h).equals(before),"cancel_readonly");
   reject(IllegalStateException.class,()->remove(h,p),"cancel_consumed");
   reject(IllegalArgumentException.class,()->plan(h,"missing"),"missing_target");
   Object valid=plan(h,"target");
   try(AppDatabase other=AppDatabase.openSchema3(getTargetContext(),name)){
    reject(IllegalArgumentException.class,()->remove(other,valid),"wrong_helper_preview");
   }
   Object token=remove(h,valid);
   pass(token!=null,"foreign_attempt_keeps_owner");
   pass(state(h).equals(expected(before,true,1)),"delete_exact");
   undo(h,token);pass(state(h).equals(expected(before,false,2)),"undo_exact");
   reject(IllegalStateException.class,()->undo(h,token),"undo_consumed");
   reject(IllegalStateException.class,()->remove(h,valid),"delete_consumed");
  }
  try(AppDatabase h=fresh("-stale-delete")){
   Object p=plan(h,"target");h.getWritableDatabase().execSQL("UPDATE categories SET name='External' WHERE id=1");
   Map<String,List<List<String>>> changed=state(h);
   reject(IllegalStateException.class,()->remove(h,p),"same_revision_stale_delete");
   pass(state(h).equals(changed),"stale_delete_readonly");
   reject(IllegalStateException.class,()->remove(h,p),"stale_delete_consumed");
  }
  try(AppDatabase h=fresh("-stale-undo")){
   Object token=remove(h,plan(h,"target"));h.getWritableDatabase().execSQL("UPDATE todos SET title='External' WHERE id='first'");
   Map<String,List<List<String>>> changed=state(h);
   reject(IllegalStateException.class,()->undo(h,token),"same_revision_stale_undo");
   pass(state(h).equals(changed),"stale_undo_readonly");
   reject(IllegalStateException.class,()->undo(h,token),"stale_undo_consumed");
  }
  AppDatabase closed=fresh("-closed-preview");Object old=plan(closed,"target");closed.close();
  try{reject(IllegalStateException.class,()->remove(closed,old),"closed_helper_preview");}finally{closed.close();}
  AppDatabase closedUndo=fresh("-closed-undo");Object oldUndo=remove(closedUndo,plan(closedUndo,"target"));closedUndo.close();
  try{reject(IllegalStateException.class,()->undo(closedUndo,oldUndo),"closed_helper_undo");}finally{closedUndo.close();}
  try(AppDatabase h=fresh("-outer")){
   SQLiteDatabase db=h.getWritableDatabase();Map<String,List<List<String>>> before=state(h);
   db.beginTransaction();
   try{reject(IllegalStateException.class,()->plan(h,"target"),"outer_preview");}finally{db.endTransaction();}
   Object p=plan(h,"target");db.beginTransaction();
   try{reject(IllegalStateException.class,()->remove(h,p),"outer_delete");}finally{db.endTransaction();}
   pass(state(h).equals(before),"outer_delete_readonly");
   Object u=remove(h,plan(h,"target"));Map<String,List<List<String>>> deleted=state(h);db.beginTransaction();
   try{reject(IllegalStateException.class,()->undo(h,u),"outer_undo");}finally{db.endTransaction();}
   pass(state(h).equals(deleted),"outer_undo_readonly");
  }
  try(AppDatabase h=fresh("-late-delete")){
   Object p=plan(h,"target");SQLiteDatabase db=h.getWritableDatabase();Map<String,List<List<String>>> before=state(h);
   db.execSQL("CREATE TRIGGER ci_todo_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'todo_late_fault'); END");
   Throwable failure=null;try{remove(h,p);}catch(Throwable t){failure=t;}
   pass(failure!=null&&failure.toString().contains("todo_late_fault")||failure!=null&&failure.getCause()!=null&&failure.getCause().toString().contains("todo_late_fault"),"late_delete_error");
   pass(state(h).equals(before),"late_delete_rollback");
   db.execSQL("DROP TRIGGER ci_todo_fault");
   reject(IllegalStateException.class,()->remove(h,p),"late_delete_consumed");
  }
  try(AppDatabase h=fresh("-late-undo")){
   Object u=remove(h,plan(h,"target"));SQLiteDatabase db=h.getWritableDatabase();Map<String,List<List<String>>> before=state(h);
   db.execSQL("CREATE TRIGGER ci_todo_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'todo_late_fault'); END");
   Throwable failure=null;try{undo(h,u);}catch(Throwable t){failure=t;}
   pass(failure!=null&&failure.toString().contains("todo_late_fault")||failure!=null&&failure.getCause()!=null&&failure.getCause().toString().contains("todo_late_fault"),"late_undo_error");
   pass(state(h).equals(before),"late_undo_rollback");
   db.execSQL("DROP TRIGGER ci_todo_fault");
   reject(IllegalStateException.class,()->undo(h,u),"late_undo_consumed");
  }
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name)){
   close(remove(h,plan(h,"target")));mediaExact("media_unchanged");saveRestart(h,"deleted");
   pass(!h.todoIds().contains("target"),"deletion_restart_saved");
  }
 }
 void deleted()throws Exception{
  media=new MediaRepository(folder.resolve("media"),64L*1024*1024);mediaId=read(folder.resolve("media-id"));
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name)){
   pass(state(h).toString().equals(read(folder.resolve("deleted.state")))&&!h.todoIds().contains("target"),"deleted_restart_exact");
   mediaExact("deleted_restart_media");backup(h,"deleted");
  }
  try(AppDatabase h=fresh("-undone")){
   h.registerMedia(mediaId,"application/octet-stream",ASSET.length);
   Map<String,List<List<String>>> before=state(h);Object token=remove(h,plan(h,"target"));undo(h,token);
   pass(state(h).equals(expected(before,false,2)),"undo_fixture_exact");saveRestart(h,"undone");
   pass(todoRows(h).contains("target|"+TITLE+"|1|11"),"undo_restart_saved");
  }
 }
 void undone()throws Exception{
  media=new MediaRepository(folder.resolve("media"),64L*1024*1024);mediaId=read(folder.resolve("media-id"));
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name.replace(".db","-undone.db"))){
   pass(state(h).toString().equals(read(folder.resolve("undone.state"))),"undone_restart_exact");
   mediaExact("undone_restart_media");backup(h,"undone");
  }
 }
 @Override public void onCreate(Bundle value){super.onCreate(value);args=value;start();}
 @Override public void onStart(){
  ByteArrayOutputStream bytes=new ByteArrayOutputStream();PrintStream originalOut=System.out,originalErr=System.err;int code=0;
  try{
   PrintStream log=new PrintStream(bytes,true,"UTF-8");System.setOut(log);System.setErr(log);
   Context c=getTargetContext();String phase=args.getString("phase"),nonce=args.getString("nonce");
   need(nonce!=null&&nonce.matches("[0-9]+-[0-9]+-(26|34)"),"nonce");
   need(c.getPackageName().equals(args.getString("expectedPackage"))&&android.os.Process.myUid()==c.getApplicationInfo().uid,"target identity");
   need(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"actual API");
   need(android.os.Build.HARDWARE.equals("ranchu")||android.os.Build.HARDWARE.equals("goldfish"),"emulator only");
   System.out.println("TODO_TARGET "+c.getPackageName()+" "+android.os.Process.myUid()+" "+android.os.Build.VERSION.SDK_INT+" "+nonce+" "+phase);
   if("diagnostic".equals(phase))throw new AssertionError("todo_diagnostic_sentinel");
   folder=new File(c.getCacheDir(),"todo-contract-"+nonce).toPath();name="todo-contract-"+nonce+".db";
   if("seed".equals(phase))seed();else if("deleted".equals(phase))deleted();else if("undone".equals(phase))undone();else throw new AssertionError("phase");
   System.out.println("TODO_RESULT "+phase+" "+count+" PASS");code=-1;
  }catch(Throwable t){System.err.println("TODO_FAILED");t.printStackTrace(System.err);}
  finally{
   System.out.flush();System.err.flush();System.setOut(originalOut);System.setErr(originalErr);
   Bundle result=new Bundle();try{result.putString("stream",bytes.toString("UTF-8"));}catch(Exception e){throw new RuntimeException(e);}finish(code,result);
  }
 }
}
'''


def observe(text, package, api, nonce, phase):
    assert type(api) is int and api in (26, 34)
    assert phase in REQUIRED and re.fullmatch(r"[0-9]+-[0-9]+-"+str(api), nonce)
    lines = text.replace("\r\n", "\n").splitlines()
    targets = re.findall(r"(?:^|\n)(?:INSTRUMENTATION_RESULT: stream=)?TODO_TARGET (\S+) ([0-9]+) ([0-9]+) (\S+) (\S+)(?=\n|$)", text)
    assert len(targets) == 1
    pkg, uid, device, actual_nonce, actual_phase = targets[0]
    assert (pkg, device, actual_nonce, actual_phase) == (package, str(api), nonce, phase)
    assert int(uid) >= 10000
    labels = [s.removeprefix("TODO_PASS ") for s in lines if s.startswith("TODO_PASS ")]
    assert labels == REQUIRED[phase]
    assert [s for s in lines if s.startswith("TODO_RESULT ")] == ["TODO_RESULT "+phase+" "+str(len(labels))+" PASS"]
    assert [s for s in lines if s.startswith("INSTRUMENTATION_CODE:")] == ["INSTRUMENTATION_CODE: -1"]
    assert not any(s in text for s in ("TODO_FAILED", "INSTRUMENTATION_FAILED", "INSTRUMENTATION_ABORTED", "FATAL EXCEPTION", "Process crashed."))
    return labels


def selftest():
    assert REQUIRED == REPORT_REQUIRED and sum(map(len, REPORT_REQUIRED.values())) == 43
    negatives = 0
    for api in (26, 34):
        for phase, labels in REQUIRED.items():
            nonce = "123-1-"+str(api)
            good = "INSTRUMENTATION_RESULT: stream=TODO_TARGET "+PACKAGE+" 10123 "+str(api)+" "+nonce+" "+phase+"\n"
            good += "".join("TODO_PASS "+s+"\n" for s in labels)
            good += "TODO_RESULT "+phase+" "+str(len(labels))+" PASS\nINSTRUMENTATION_CODE: -1\n"
            assert observe(good, PACKAGE, api, nonce, phase) == labels
            bad = [good.replace("TODO_PASS "+s+"\n", "", 1) for s in labels]
            bad += [good.replace(PACKAGE, "wrong.package"), good.replace(nonce, "999-1-"+str(api)),
                    good.replace("10123", "999"), good.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: 0"),
                    good+good, good+"TODO_FAILED\n", good+"TODO_PASS unknown\n",
                    good.replace("TODO_RESULT "+phase, "TODO_RESULT wrong")]
            for text in bad:
                try:
                    observe(text, PACKAGE, api, nonce, phase)
                except AssertionError:
                    negatives += 1
                else:
                    raise AssertionError("Incomplete or mismatched evidence accepted")
    source = inspect.getsource(observe)
    mutations = [
        ("assert labels == REQUIRED[phase]", "assert True", good.replace("TODO_PASS "+labels[0]+"\n", "").replace("TODO_RESULT "+phase+" "+str(len(labels)), "TODO_RESULT "+phase+" "+str(len(labels)-1))),
        ('assert [s for s in lines if s.startswith("INSTRUMENTATION_CODE:")] == ["INSTRUMENTATION_CODE: -1"]', "assert True", good.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: 0")),
        ("assert (pkg, device, actual_nonce, actual_phase) == (package, str(api), nonce, phase)", "assert True", good.replace(PACKAGE, "wrong.package")),
    ]
    for old, new, bad in mutations:
        assert source.count(old) == 1
        try:
            observe(bad, PACKAGE, api, nonce, phase)
        except AssertionError:
            pass
        else:
            raise AssertionError("Negative fixture did not fail")
        namespace = {"re": re, "REQUIRED": REQUIRED}
        exec(compile(source.replace(old, new, 1), "<todo-parser-mutant>", "exec"), namespace)
        namespace["observe"](bad, PACKAGE, api, nonce, phase)
    # JDK parser checks Java syntax only. Android compilation and behavior remain device work.
    parser = '''import javax.tools.*;import com.sun.source.util.*;import java.util.*;
class ParseTodo{public static void main(String[] args)throws Exception{
 JavaCompiler c=ToolProvider.getSystemJavaCompiler();if(c==null)throw new AssertionError("JDK required");
 DiagnosticCollector<JavaFileObject> d=new DiagnosticCollector<>();
 try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
  JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(args[0]));
  for(Object tree:t.parse()){}for(Diagnostic<?> x:d.getDiagnostics())if(x.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(x.toString());
 }
}}'''
    with tempfile.TemporaryDirectory(prefix="todo-parser-") as tmp:
        folder = Path(tmp);(folder/"ParseTodo.java").write_text(parser);(folder/"TodoInstrumentation.java").write_text(JAVA)
        p = subprocess.run([shutil.which("java") or "java", str(folder/"ParseTodo.java"), str(folder/"TodoInstrumentation.java")], capture_output=True, text=True, timeout=30)
        assert p.returncode == 0, (p.stdout, p.stderr)
    print(json.dumps(dict(status="PASS", positive=6, negative=negatives, parser_mutants=3,
                         scope="HOST_RECEIPT_PARSER_AND_JAVA_SYNTAX_ONLY_NOT_PRODUCT_BEHAVIOR", release_ready=False)))
    report_selftest()


def android():
    assert os.environ.get("GITHUB_ACTIONS") == "true"
    import emulator_gate as gate
    from verify_schema3 import certificate, require_registration
    from verify_paged_exports import debug_key
    from verify_process_control import stop_verified
    out = ROOT/"todo-device";out.mkdir(exist_ok=True)
    result = dict(status="FAIL", scope=SCOPE, commit=os.environ["GITHUB_SHA"],
                  run_id=os.environ["GITHUB_RUN_ID"], run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
                  api=gate.API, labels=[], release_ready=False, native_ui="NOT_IMPLEMENTED",
                  cross_restart_undo="NOT_SUPPORTED", stops=[])
    def run(args, timeout=60, binary=False):
        args = list(map(str, args))
        try:
            p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=not binary, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            result.setdefault("command_failure", dict(args=args, timeout=timeout, stdout=repr(e.stdout)[-6000:], stderr=repr(e.stderr)[-6000:]))
            raise
        if p.returncode:
            result.setdefault("command_failure", dict(args=args, returncode=p.returncode, stdout=repr(p.stdout)[-6000:], stderr=repr(p.stderr)[-6000:]))
            raise RuntimeError("Todo device command failed: "+repr(args))
        return p.stdout if binary else p.stdout+"\n"+p.stderr
    def verify(adb):
        prefix = [str(adb), "-s", gate.SERIAL]
        apps = list((ROOT/"build/outputs/apk/debug").glob("*.apk"))
        tests = list((ROOT/"build/outputs/apk/androidTest/debug").glob("*.apk"))
        assert len(apps) == len(tests) == 1
        app, test = apps[0], tests[0];product, saved = app.read_bytes(), test.read_bytes()
        cert = certificate(app, gate);assert certificate(test, gate) == cert
        result.update(apk_sha256=hashlib.sha256(product).hexdigest(), apk_bytes=len(product), certificate=cert)
        manifest = json.loads((ROOT/"todo-apk.json").read_text())
        for key, value in manifest.items():
            assert type(result[key]) is type(value) and result[key] == value
        for path in (app, test):
            run(prefix+["install", "-r", "-t", path], 120)
        require_registration(adb, gate, "todo-before", "V12DeviceTest")
        def installed():
            paths = re.findall(r"^package:(\S+)\s*$", run(prefix+["shell", "pm", "path", gate.PKG]), re.M)
            assert len(paths) == 1
            return run(prefix+["exec-out", "cat", paths[0]], 30, True)
        assert installed() == product
        key = debug_key(cert);nonce = result["run_id"]+"-"+result["run_attempt"]+"-"+str(gate.API)
        with tempfile.TemporaryDirectory(prefix="todo-runner-", dir=ROOT/"build") as tmp:
            work = Path(tmp);src = work/"src";src.mkdir();(src/"TodoInstrumentation.java").write_text(JAVA)
            init = work/"runner.gradle"
            init.write_text("gradle.beforeProject { p ->\n p.plugins.withId('com.android.application') {\n"
                            " p.androidComponents.finalizeDsl { dsl ->\n"
                            " dsl.defaultConfig.testInstrumentationRunner = 'ci.todos.TodoInstrumentation'\n"
                            " dsl.sourceSets.getByName('androidTest').java.srcDir "+json.dumps(str(src))+"\n"
                            " dsl.signingConfigs.getByName('debug').storeFile = new File("+json.dumps(str(key))+")\n }\n }\n}\n")
            backup = work/"default-test.apk";backup.write_bytes(saved);primary = None
            try:
                (out/"build.log").write_text(run(["gradle", "--no-daemon", "--console=plain", "-I", init, "assembleDebugAndroidTest"], 300))
                assert app.read_bytes() == product and certificate(test, gate) == cert
                run(prefix+["install", "-r", "-t", test], 120)
                component = PACKAGE+".test/ci.todos.TodoInstrumentation"
                registrations = re.findall(r"^instrumentation:(\S+) \(target=([^)]+)\)\s*$", run(prefix+["shell", "pm", "list", "instrumentation"]), re.M)
                assert [r for r in registrations if r[0].startswith(PACKAGE+".test/")] == [(component, PACKAGE)]
                args = prefix+["shell", "-n", "-T", "am", "instrument", "-w", "-r", "-e", "expectedPackage", PACKAGE, "-e", "expectedApi", str(gate.API), "-e", "nonce", nonce]
                diagnostic = run(args+["-e", "phase", "diagnostic", component])
                (out/"diagnostic.log").write_text(diagnostic)
                assert "java.lang.AssertionError: todo_diagnostic_sentinel" in diagnostic and "TODO_FAILED" in diagnostic and "INSTRUMENTATION_CODE: 0" in diagnostic
                try:
                    observe(diagnostic, PACKAGE, gate.API, nonce, "seed")
                except AssertionError:
                    result["diagnostic_rejected"] = True
                else:
                    raise AssertionError("Injected failure accepted")
                for phase in REQUIRED:
                    if phase != "seed":
                        result["stops"].append(stop_verified(adb, gate.SERIAL, PACKAGE))
                    text = run(args+["-e", "phase", phase, component], 180)
                    (out/(phase+".log")).write_text(text)
                    labels = observe(text, PACKAGE, gate.API, nonce, phase)
                    result[phase] = dict(labels=labels, log_sha256=hashlib.sha256(text.encode()).hexdigest())
                    result["labels"].extend(labels)
                assert installed() == product
            except BaseException as e:
                primary = e
                raise
            finally:
                try:
                    assert backup.read_bytes() == saved
                    run(prefix+["install", "-r", "-t", backup], 120);test.write_bytes(saved)
                    require_registration(adb, gate, "todo-restored", "V12DeviceTest")
                    assert app.read_bytes() == product and test.read_bytes() == saved and installed() == product
                    result["default_test_restored"] = True
                except BaseException as e:
                    result["restoration_error"] = repr(e)
                    if primary is None:
                        raise
        result["product_readback"] = "EXACT_BEFORE_AND_AFTER"
    old_db, old_native = gate.verify_database, gate.verify_native_ui
    try:
        gate.verify_database = verify;gate.verify_native_ui = lambda adb: None
        gate.main()
        assert result["labels"] == sum(REQUIRED.values(), [])
        result["status"] = "PASS"
    except BaseException as e:
        result.update(status="FAIL", error=repr(e), traceback=traceback.format_exc()[-12000:])
        raise
    finally:
        gate.verify_database, gate.verify_native_ui = old_db, old_native
        result["checks"] = len(result["labels"])
        (out/"result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
        print("TODO_DEVICE "+json.dumps(result, ensure_ascii=False), flush=True)


def validate(value, manifest, logs, api, source, run, attempt):
    assert value["status"] == "PASS" and value["scope"] == SCOPE
    for key, expected in dict(api=api, commit=source, run_id=run, run_attempt=attempt).items():
        assert type(value[key]) is type(expected) and value[key] == expected
        assert type(manifest[key]) is type(expected) and manifest[key] == expected
    for key in ("apk_sha256", "certificate"):
        assert re.fullmatch("[0-9a-f]{64}", value[key]) and value[key] == manifest[key]
    assert type(value["apk_bytes"]) is int and type(manifest["apk_bytes"]) is int
    assert 0 < value["apk_bytes"] == manifest["apk_bytes"]
    assert value["labels"] == sum(REPORT_REQUIRED.values(), [])
    assert type(value["checks"]) is int and value["checks"] == 43
    assert value["release_ready"] is False and value["native_ui"] == "NOT_IMPLEMENTED"
    assert value["cross_restart_undo"] == "NOT_SUPPORTED"
    assert value["default_test_restored"] is True and value["diagnostic_rejected"] is True
    assert value["product_readback"] == "EXACT_BEFORE_AND_AFTER" and "restoration_error" not in value
    nonce = run+"-"+attempt+"-"+str(api)
    for phase in REPORT_REQUIRED:
        assert observe(logs[phase], PACKAGE, api, nonce, phase) == value[phase]["labels"]
        assert value[phase]["labels"] == REPORT_REQUIRED[phase]
        assert hashlib.sha256(logs[phase].encode()).hexdigest() == value[phase]["log_sha256"]
    assert len(value["stops"]) == 2
    for stop in value["stops"]:
        assert stop["status"] == "PASS" and stop["package"] == PACKAGE
        assert stop["scope"] == "COMMAND_ACK_AND_OBSERVED_ABSENCE_NOT_LMK"
        assert type(stop["force_stop_attempts"]) is int and stop["force_stop_attempts"] == 1
        cmd, last = stop["command"], stop["probes"][-1]
        assert type(cmd["returncode"]) is int and cmd["returncode"] == 0 and cmd["stdout"] == cmd["stderr"] == ""
        assert cmd["args"][-3:] == ["am", "force-stop", PACKAGE]
        assert type(last["returncode"]) is int and last["returncode"] == 1
        assert last["stdout"].strip() == last["stderr"].strip() == "" and last["args"][-2:] == ["pidof", PACKAGE]


def report_selftest():
    total = 0
    for api in (26, 34):
        source, run, attempt = "a"*40, "123", "1"
        manifest = dict(api=api, commit=source, run_id=run, run_attempt=attempt, apk_sha256="b"*64, apk_bytes=100, certificate="c"*64)
        stop = dict(status="PASS", package=PACKAGE, scope="COMMAND_ACK_AND_OBSERVED_ABSENCE_NOT_LMK", force_stop_attempts=1,
                    command=dict(returncode=0, stdout="", stderr="", args=["am", "force-stop", PACKAGE]),
                    probes=[dict(returncode=1, stdout="", stderr="", args=["pidof", PACKAGE])])
        value = dict(manifest, status="PASS", scope=SCOPE, labels=sum(REPORT_REQUIRED.values(), []), checks=43,
                     release_ready=False, native_ui="NOT_IMPLEMENTED", cross_restart_undo="NOT_SUPPORTED",
                     default_test_restored=True, diagnostic_rejected=True,
                     product_readback="EXACT_BEFORE_AND_AFTER", stops=[copy.deepcopy(stop), copy.deepcopy(stop)])
        logs = {}
        for phase, labels in REPORT_REQUIRED.items():
            text = "INSTRUMENTATION_RESULT: stream=TODO_TARGET "+PACKAGE+" 10123 "+str(api)+" "+run+"-"+attempt+"-"+str(api)+" "+phase+"\n"
            text += "".join("TODO_PASS "+s+"\n" for s in labels)
            text += "TODO_RESULT "+phase+" "+str(len(labels))+" PASS\nINSTRUMENTATION_CODE: -1\n"
            logs[phase] = text;value[phase] = dict(labels=labels[:], log_sha256=hashlib.sha256(text.encode()).hexdigest())
        validate(value, manifest, logs, api, source, run, attempt)
        bad = []
        for key in value:
            v = copy.deepcopy(value);del v[key];bad.append((v, manifest, logs))
        for key in manifest:
            m = copy.deepcopy(manifest);del m[key];bad.append((value, m, logs))
        for key, changed in (("checks", 43.0), ("checks", True), ("api", float(api)), ("status", "FAIL"),
                             ("commit", "d"*40), ("run_id", "124"), ("run_attempt", "2"),
                             ("apk_bytes", True), ("certificate", "d"*64), ("apk_sha256", "d"*64),
                             ("release_ready", 0), ("native_ui", "PASS"), ("default_test_restored", 1),
                             ("diagnostic_rejected", 1), ("restoration_error", "sentinel")):
            v = copy.deepcopy(value);v[key] = changed;bad.append((v, manifest, logs))
        for phase, labels in REPORT_REQUIRED.items():
            for label in labels:
                v = copy.deepcopy(value);l = dict(logs)
                v["labels"].remove(label);v["checks"] -= 1;v[phase]["labels"].remove(label)
                l[phase] = l[phase].replace("TODO_PASS "+label+"\n", "")
                v[phase]["log_sha256"] = hashlib.sha256(l[phase].encode()).hexdigest()
                bad.append((v, manifest, l))
        for index in range(2):
            for code in (0, 255, True):
                v = copy.deepcopy(value);v["stops"][index]["probes"][-1]["returncode"] = code;bad.append((v, manifest, logs))
        v = copy.deepcopy(value);v["stops"].pop();bad.append((v, manifest, logs))
        for v, m, l in bad:
            try:
                validate(v, m, l, api, source, run, attempt)
            except (AssertionError, KeyError, TypeError, IndexError):
                total += 1
            else:
                raise AssertionError("Bad aggregate evidence accepted")
    print(json.dumps(dict(status="PASS", report_positive=2, report_negative=total,
                         scope="HOST_AGGREGATE_CONTROLS_NOT_ANDROID", release_ready=False)))


def report():
    import urllib.request
    from verify_evidence import publish
    source, run, attempt = (os.environ[k] for k in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"))
    needs = json.loads(os.environ["NEEDS_JSON"])
    passed = all(needs.get(k, {}).get("result") == "success" for k in ("todo_host", "todo_device"))
    devices = {}
    for api in (26, 34):
        folder = ROOT/"collected-todos"/("todo-device-api-"+str(api))
        row = {"status": "FAIL"};devices[str(api)] = row
        try:
            value = json.loads((folder/"todo-device/result.json").read_text())
            manifest = json.loads((folder/"todo-apk.json").read_text())
            logs = {p: (folder/"todo-device"/(p+".log")).read_text() for p in REQUIRED}
            validate(value, manifest, logs, api, source, run, attempt)
            row.update(status="PASS", evidence=value, manifest=manifest)
        except (OSError, ValueError, AssertionError, KeyError, TypeError, IndexError) as e:
            passed = False;row["error"] = repr(e)
        row["diagnostics"] = {}
        for name in ("todo-setup.log", "todo-build.log", "todo-android.log", "emulator.log", "todo-device/build.log", "todo-device/seed.log", "todo-device/result.json"):
            try:
                with (folder/name).open("rb") as f:
                    f.seek(0, 2);size = f.tell();f.seek(max(0, size-12000));tail = f.read(12000)
                row["diagnostics"][name] = dict(bytes=size, truncated=size>12000, tail=tail.decode("utf-8", "replace"))
            except OSError as e:
                row["diagnostics"][name] = dict(error=repr(e))
    value = dict(status="PASS" if passed else "FAIL", scope="TODO_BACKEND_GATE_ONLY_NOT_FEATURE_ACCEPTANCE",
                 commit=source, run_id=run, run_attempt=attempt, devices=devices, parents=needs,
                 native_ui="NOT_IMPLEMENTED", release_ready=False, durable_upgrade_ready=False)
    data = (json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode()
    (ROOT/"todo-report.json").write_bytes(data)
    endpoint = "https://api.github.com/repos/"+os.environ["GITHUB_REPOSITORY"]+"/"
    def api_call(path, method="GET", body=None):
        request = urllib.request.Request(endpoint+path, method=method, data=None if body is None else json.dumps(body).encode(),
                                         headers={"Authorization": "Bearer "+os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    print("TODO_REPORT_PUBLISHED "+str(publish(api_call, "reports/todo-management-"+source+"-"+run+"-"+attempt+".json", data)), flush=True)
    assert passed, "Todo backend evidence missing, mismatched or failed; native UI not accepted"


if __name__ == "__main__":
    assert not sys.flags.optimize, "Assertions must remain enabled"
    modes = {"selftest": selftest, "android": android, "report": report}
    if len(sys.argv) != 2 or sys.argv[1] not in modes:
        raise SystemExit("Usage: verify_todo_management.py selftest|android|report")
    modes[sys.argv[1]]()
