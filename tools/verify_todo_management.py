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
    ui_host_observer_selftest()
    ui_product_selftest()
    backend_host_observer_selftest()
    backend_product_selftest()
    backend_report_entry_selftest()
    installed_readback_selftest()


# Embedded into the approved existing gate; no new repository file.
UI_LABELS = """preview_readonly exact_target_details honest_limit cancel_readonly
duplicate_confirm_disabled delete_once_token_retained stable_undo_identity single_use_undo
composer_remembered busy_preview stale_row_rejected late_preview_disposed changed_title_rejected
changed_done_rejected stale_confirm_rejected leave_closes_preview leave_invalidates_undo
closed_completion_disposes_undo destroyed_completion_disposes_preview finishing_preview_blocked
delete_failure_no_undo undo_failure_consumed stale_delete_completion_disposed wrong_page_blocked
invalidation_hides_both_controls invalidated_control_no_write
undo_hides_before_async_without_closing_token hidden_undo_still_executes
rerender_hides_old_controls_keeps_token""".split()
UI_MUTANTS = [
    ("stale_view", "stale_row_rejected", "&&todoView==expected", ""),
    ("changed_title", "changed_title_rejected", "!item.title.equals(plan.title())||item.done!=plan.done()", "false"),
    ("undo_close", "leave_invalidates_undo", "if(token!=null)token.close();", ""),
    ("cancel_close", "cancel_readonly", "if(pendingTodoDeletion==plan){pendingTodoDeletion=null;plan.close();}", "if(pendingTodoDeletion==plan){pendingTodoDeletion=null;}"),
    ("hint_visibility", "invalidation_hides_both_controls", "todoUndoHint.setVisibility(View.GONE);", ""),
    ("button_visibility", "invalidation_hides_both_controls", "todoUndoButton.setVisibility(View.GONE);", ""),
]
UI_SCOPE = "ACTUAL_TODAYSCREEN_MEMBERS_MODELED_WIDGETS_DB_SCHEDULER_NOT_ANDROID"
UI_MARKER = "TODO_UI_MODEL "
UI_SOURCE = "src/main/java/com/supercubegame/pockettodo/TodayScreen.java"


def validate_ui_host(text, source, run, attempt, digest):
    lines = [line[len(UI_MARKER):] for line in text.splitlines() if line.startswith(UI_MARKER)]
    assert len(lines) == 1, "Missing or duplicate actual-product UI host evidence"
    value = json.loads(lines[0])
    for key, expected in dict(status="PASS", scope=UI_SCOPE, commit=source, run_id=run,
                              run_attempt=attempt, source_sha256=digest).items():
        assert type(value[key]) is str and value[key] == expected, "UI host binding "+key
    assert type(value["checks"]) is int and value["checks"] == 29
    assert value["labels"] == UI_LABELS and len(set(value["labels"])) == 29
    assert value["mutants_rejected"] == ["stale_view", "changed_title", "undo_close", "cancel_close", "hint_visibility", "button_visibility"]
    assert value["missing_members_rejected"] is True and value["release_ready"] is False
    assert re.fullmatch("[0-9a-f]{64}", value["source_sha256"])
    return value


def ui_host_observer_selftest():
    good = dict(status="PASS", scope=UI_SCOPE, commit="a"*40, run_id="123", run_attempt="1",
                source_sha256="b"*64, checks=29, labels=UI_LABELS[:],
                mutants_rejected=["stale_view", "changed_title", "undo_close", "cancel_close", "hint_visibility", "button_visibility"],
                missing_members_rejected=True, release_ready=False)
    def log(value):
        return UI_MARKER+json.dumps(value)+"\n"
    args = ("a"*40, "123", "1", "b"*64)
    assert validate_ui_host(log(good), *args) == good
    bad = ["", log(good)+log(good)]
    for key in good:
        value = copy.deepcopy(good);del value[key];bad.append(log(value))
    for key in ("status", "scope", "commit", "run_id", "run_attempt", "source_sha256"):
        value = copy.deepcopy(good);value[key] = "wrong";bad.append(log(value))
    for n in (0, 28, 30, True, 29.0):
        value = copy.deepcopy(good);value["checks"] = n;bad.append(log(value))
    for label in UI_LABELS:
        value = copy.deepcopy(good);value["labels"].remove(label);bad.append(log(value))
    for mutant in good["mutants_rejected"]:
        value = copy.deepcopy(good);value["mutants_rejected"].remove(mutant);bad.append(log(value))
    for key in ("missing_members_rejected", "release_ready"):
        value = copy.deepcopy(good);value[key] = not value[key];bad.append(log(value))
    value = copy.deepcopy(good);value["labels"].reverse();bad.append(log(value))
    for text in bad:
        try:
            validate_ui_host(text, *args)
        except (AssertionError, KeyError, TypeError, ValueError):
            pass
        else:
            raise AssertionError("Incomplete UI host evidence accepted")
    # Deliberately remove each guard, then use the same negative witness.
    validator = inspect.getsource(validate_ui_host)
    witnesses = [
        ('assert len(lines) == 1, "Missing or duplicate actual-product UI host evidence"', 'assert True', log(good)+log(good)),
        ('assert type(value["checks"]) is int and value["checks"] == 29', 'assert True', log(dict(good, checks=True))),
        ('assert value["labels"] == UI_LABELS and len(set(value["labels"])) == 29', 'assert True', log(dict(good, labels=UI_LABELS[:-1]))),
    ]
    for old, new, witness in witnesses:
        assert validator.count(old) == 1
        namespace = dict(globals())
        exec(compile(validator.replace(old, new, 1), "<ui-host-validator-mutant>", "exec"), namespace)
        namespace["validate_ui_host"](witness, *args)
    print("TODO_UI_HOST_OBSERVER "+json.dumps(dict(positive=1, negative=len(bad), validator_mutants=3,
                                                scope="HOST_RECEIPT_CONTROLS_NOT_ANDROID")))


def ui_product_selftest():
    product = ROOT/UI_SOURCE
    original = product.read_bytes()
    java = shutil.which("java") or "java"
    with tempfile.TemporaryDirectory(prefix="todo-ui-product-") as tmp:
        folder = Path(tmp)
        (folder/"TodayScreen.java").write_bytes(original)
        (folder/"ExtractUi.java").write_text(UI_EXTRACTOR, encoding="utf-8")
        extracted = folder/"members.txt"
        p = subprocess.run([java, str(folder/"ExtractUi.java"), str(folder/"TodayScreen.java"), str(extracted)],
                           capture_output=True, text=True, timeout=30)
        assert p.returncode == 0, "Actual product AST extraction failed\n"+p.stdout+p.stderr
        fragment = extracted.read_text(encoding="utf-8")
        def run_model(code):
            path = folder/"UiModel.java"
            path.write_text(UI_MODEL_PREFIX+code+UI_MODEL_SUFFIX, encoding="utf-8")
            return subprocess.run([java, str(path)], capture_output=True, text=True, timeout=30)
        missing = run_model("")
        assert missing.returncode != 0 and "cannot find symbol" in missing.stderr
        p = run_model(fragment)
        assert p.returncode == 0, p.stdout+p.stderr
        labels = [line.removeprefix("UI_PASS ") for line in p.stdout.splitlines() if line.startswith("UI_PASS ")]
        assert labels == UI_LABELS and p.stdout.splitlines()[-1] == "UI_CHECKS 29 PASS MODEL_NOT_ANDROID"
        print(p.stdout, end="")
        rejected = []
        for name, label, old, new in UI_MUTANTS:
            assert fragment.count(old) == 1, "UI mutant anchor "+name
            p = run_model(fragment.replace(old, new, 1))
            assert p.returncode != 0 and "AssertionError: "+label in p.stderr, (name, p.stdout, p.stderr)
            # Every compiled mutant still passes the initial normal preview witness.
            assert "UI_PASS preview_readonly\n" in p.stdout, "Mutant failed before behavioral witness "+name
            rejected.append(name)
        assert product.read_bytes() == original, "Host model changed product source"
    value = dict(status="PASS", scope=UI_SCOPE, commit=os.environ.get("GITHUB_SHA", "LOCAL"),
                 run_id=os.environ.get("GITHUB_RUN_ID", "LOCAL"), run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", "LOCAL"),
                 source_sha256=hashlib.sha256(original).hexdigest(), checks=len(labels), labels=labels,
                 mutants_rejected=rejected, missing_members_rejected=True, release_ready=False)
    print(UI_MARKER+json.dumps(value, ensure_ascii=False), flush=True)


UI_EXTRACTOR = r'''
import javax.tools.*;
import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.nio.file.*;
import java.util.*;
public class ExtractUi {
 public static void main(String[] args)throws Exception{
  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();
  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();
  try(StandardJavaFileManager fm=compiler.getStandardFileManager(errors,null,null)){
   String source=Files.readString(Path.of(args[0]));
   JavacTask task=(JavacTask)compiler.getTask(null,fm,errors,List.of("-proc:none"),null,fm.getJavaFileObjects(args[0]));
   CompilationUnitTree unit=task.parse().iterator().next();
   for(Diagnostic<?> d:errors.getDiagnostics())if(d.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(d);
   SourcePositions positions=Trees.instance(task).getSourcePositions();
   Set<String> required=new LinkedHashSet<>(List.of("pendingTodoDeletion","todoUndo","todoUndoHint","todoUndoButton","todoDialog","todoView","todoViewCurrent","clearTodoUndo","clearTodoUndoControls","clearTodoPreview","leaveTodoSession","previewTodoDeletion","showTodoDeletion","renderTodoUndo"));
   Set<String> seen=new HashSet<>();StringBuilder out=new StringBuilder();
   for(Tree type:unit.getTypeDecls())if(type instanceof ClassTree&&((ClassTree)type).getSimpleName().contentEquals("TodayScreen"))
    for(Tree member:((ClassTree)type).getMembers()){
     String name=member instanceof MethodTree?((MethodTree)member).getName().toString():member instanceof VariableTree?((VariableTree)member).getName().toString():"";
     if(required.contains(name)){
      if(!seen.add(name))throw new AssertionError("Duplicate product member "+name);
      out.append(source.substring((int)positions.getStartPosition(unit,member),(int)positions.getEndPosition(unit,member))).append('\n');
     }
    }
   if(!seen.equals(required))throw new AssertionError("Missing product members "+required+" observed "+seen);
   Files.writeString(Path.of(args[1]),out);
  }
 }
}
'''
UI_MODEL_PREFIX = r'''
import java.util.*;
import java.util.concurrent.Callable;
import java.util.function.Consumer;
public class UiModel {
 static class View {static final int GONE=8;Consumer<View> click;String description;boolean enabled=true;int visibility=0;void setVisibility(int v){visibility=v;}void setContentDescription(String s){description=s;}void setMinHeight(int v){}void setEnabled(boolean v){enabled=v;}void setOnClickListener(Consumer<View> c){click=c;}void tap(){if(enabled&&visibility!=GONE&&click!=null)click.accept(this);}}
 static class TextView extends View {String text;TextView(String s){text=s;}}
 static class Button extends TextView {Button(String s){super(s);}}
 static class LinearLayout extends View {List<View> children=new ArrayList<>();void addView(View v){children.add(v);}void addView(View v,LayoutParams p){addView(v);}void setPadding(int a,int b,int c,int d){}static class LayoutParams{LayoutParams(int a,int b){}}}
 static class ScrollView extends LinearLayout {ScrollView(Activity a){}}
 static class Activity {boolean destroyed,finishing;boolean isDestroyed(){return destroyed;}boolean isFinishing(){return finishing;}}
 static class AlertDialog {
  static final int BUTTON_POSITIVE=1,BUTTON_NEGATIVE=-1;static AlertDialog last;
  Button pos=new Button(""),neg=new Button("");View body;Consumer<Object> show,dismiss;boolean showing,cancelable=true;
  AlertDialog(){neg.setOnClickListener(v->dismiss());}
  void setOnDismissListener(Consumer<Object> c){dismiss=c;}void setOnShowListener(Consumer<Object> c){show=c;}void show(){last=this;showing=true;if(show!=null)show.accept(this);}
  void dismiss(){if(!showing)return;showing=false;if(dismiss!=null)dismiss.accept(this);}
  Button getButton(int n){return n==1?pos:neg;}void setCancelable(boolean b){cancelable=b;}
  static class Builder{AlertDialog d=new AlertDialog();Builder(Activity a){}Builder setTitle(String s){return this;}Builder setView(View v){d.body=v;return this;}Builder setNegativeButton(String s,Object v){d.neg.text=s;return this;}Builder setPositiveButton(String s,Object v){d.pos.text=s;return this;}AlertDialog create(){return d;}}
 }
 static class AppDatabase {
  static class TodoDeletionPlan {String id,title;boolean done,closed;TodoDeletionPlan(String i,String t,boolean d){id=i;title=t;done=d;}String todoId(){return id;}String title(){return title;}boolean done(){return done;}void close(){closed=true;}}
  static class TodoDeletionUndo {String id,title;boolean closed;TodoDeletionUndo(TodoDeletionPlan p){id=p.id;title=p.title;}String todoId(){return id;}String title(){return title;}void close(){closed=true;}}
  int prepares,deletes,undos;boolean failDelete,failUndo;String title="same";boolean done=true;TodoDeletionPlan plan;TodoDeletionUndo token;
  TodoDeletionPlan prepareTodoDeletion(String id){prepares++;return plan=new TodoDeletionPlan(id,title,done);}
  TodoDeletionUndo confirmTodoDeletion(TodoDeletionPlan p){if(p.closed)throw new IllegalStateException();p.close();if(failDelete)throw new IllegalStateException();deletes++;return token=new TodoDeletionUndo(p);}
  void undoTodoDeletion(TodoDeletionUndo t){if(t.closed)throw new IllegalStateException();t.close();if(failUndo)throw new IllegalStateException();undos++;}
 }
 static class TodoRow {String id,title;boolean done;TodoRow(String i){id=i;title="same";done=true;}}
 Activity activity=new Activity();AppDatabase db=new AppDatabase();boolean closed,busy;int page,loads,remembered;String notice="";
 static final int INK=1,ERROR=2,MUTED=3;
 LinearLayout column(){return new LinearLayout();}TextView text(String v,int s,int c){return new TextView(v);}int dp(int v){return v;}
 Button button(String v,Runnable action){Button b=new Button(v);b.setOnClickListener(w->{if(!busy)action.run();});return b;}
 void message(String v,boolean b){notice=v;}void rememberDraft(){remembered++;}void loadTodos(){loads++;todoView=new Object();}
 Runnable pending;
 <T> void work(Callable<T> action,Consumer<T> success,Runnable failure){work(action,success,failure,ignored->{});}
 <T> void work(Callable<T> action,Consumer<T> success,Runnable failure,Consumer<T> abandoned){
  if(closed||busy)return;busy=true;
  pending=()->{try{T result=action.call();if(closed||activity.isDestroyed()){abandoned.accept(result);return;}busy=false;success.accept(result);}catch(Exception e){busy=false;if(failure!=null)failure.run();}};
 }
 void finish(){Runnable r=pending;pending=null;if(r==null)throw new AssertionError("missing queued action");r.run();}
 void preview(){previewTodoDeletion(new TodoRow("second-id"),todoView);}
 void open(){preview();finish();}
 void confirm(){AlertDialog.last.pos.tap();}
 Button undoButton(){LinearLayout b=column();renderTodoUndo(b);return (Button)b.children.get(1);}
 static int checks;static void ok(boolean value,String name){if(!value)throw new AssertionError(name);checks++;System.out.println("UI_PASS "+name);}
'''
UI_MODEL_SUFFIX = r'''
 public static void main(String[] args){
  UiModel m=new UiModel();m.open();ok(m.db.deletes==0&&m.pendingTodoDeletion==m.db.plan,"preview_readonly");
  ScrollView scroll=(ScrollView)AlertDialog.last.body;LinearLayout details=(LinearLayout)scroll.children.get(0);
  ok(((TextView)details.children.get(0)).text.equals("same\n状态：已完成\nID：second-id"),"exact_target_details");
  ok(((TextView)details.children.get(1)).text.contains("重启后不可撤销"),"honest_limit");
  AlertDialog.last.neg.tap();ok(m.db.plan.closed&&m.pendingTodoDeletion==null&&m.db.deletes==0,"cancel_readonly");
  m=new UiModel();m.open();AlertDialog d=AlertDialog.last;m.confirm();m.confirm();ok(m.busy&&!d.cancelable&&!d.pos.enabled&&!d.neg.enabled,"duplicate_confirm_disabled");m.finish();
  ok(m.db.deletes==1&&m.todoUndo==m.db.token&&!d.showing,"delete_once_token_retained");
  Button u=m.undoButton();ok(u.description.equals("todo-undo-second-id"),"stable_undo_identity");u.tap();u.tap();m.finish();
  ok(m.db.undos==1&&m.todoUndo==null&&m.db.token.closed,"single_use_undo");
  ok(m.remembered==2,"composer_remembered");
  m=new UiModel();m.busy=true;m.preview();ok(m.pending==null,"busy_preview");
  m=new UiModel();Object old=m.todoView;m.todoView=new Object();m.previewTodoDeletion(new TodoRow("second-id"),old);ok(m.pending==null,"stale_row_rejected");
  m=new UiModel();m.preview();m.todoView=new Object();m.finish();ok(m.db.plan.closed&&m.pendingTodoDeletion==null,"late_preview_disposed");
  m=new UiModel();m.db.title="changed";m.open();ok(m.db.plan.closed&&m.pendingTodoDeletion==null&&m.loads==1,"changed_title_rejected");
  m=new UiModel();m.db.done=false;m.open();ok(m.db.plan.closed&&m.pendingTodoDeletion==null,"changed_done_rejected");
  m=new UiModel();m.open();m.todoView=new Object();m.confirm();ok(m.pending==null&&m.db.deletes==0,"stale_confirm_rejected");
  m=new UiModel();m.open();m.leaveTodoSession();ok(m.db.plan.closed&&m.pendingTodoDeletion==null&&!AlertDialog.last.showing,"leave_closes_preview");
  m=new UiModel();m.open();m.confirm();m.finish();u=m.undoButton();m.leaveTodoSession();u.tap();ok(m.pending==null&&m.todoUndo==null&&m.db.token.closed,"leave_invalidates_undo");
  m=new UiModel();m.open();m.confirm();m.closed=true;m.finish();ok(m.db.token.closed&&m.todoUndo==null,"closed_completion_disposes_undo");
  m=new UiModel();m.preview();m.activity.destroyed=true;m.finish();ok(m.db.plan.closed,"destroyed_completion_disposes_preview");
  m=new UiModel();m.activity.finishing=true;m.preview();ok(m.pending==null,"finishing_preview_blocked");
  m=new UiModel();m.open();m.db.failDelete=true;m.confirm();m.finish();ok(m.todoUndo==null&&m.db.deletes==0&&!AlertDialog.last.showing&&m.notice.contains("删除未完成"),"delete_failure_no_undo");
  m=new UiModel();m.open();m.confirm();m.finish();m.db.failUndo=true;u=m.undoButton();u.tap();m.finish();ok(m.todoUndo==null&&m.db.undos==0&&m.notice.contains("无法撤销"),"undo_failure_consumed");
  m=new UiModel();m.open();m.confirm();m.todoView=new Object();m.finish();ok(m.db.token.closed&&m.todoUndo==null,"stale_delete_completion_disposed");
  m=new UiModel();m.page=1;m.preview();ok(m.pending==null,"wrong_page_blocked");
  m=new UiModel();m.open();m.confirm();m.finish();LinearLayout body=m.column();m.renderTodoUndo(body);
  TextView hint=(TextView)body.children.get(0);u=(Button)body.children.get(1);m.clearTodoUndo();
  ok(hint.visibility==View.GONE&&u.visibility==View.GONE&&m.todoUndo==null&&m.db.token.closed,"invalidation_hides_both_controls");
  m.clearTodoUndo();u.tap();ok(m.pending==null&&m.db.undos==0,"invalidated_control_no_write");
  m=new UiModel();m.open();m.confirm();m.finish();body=m.column();m.renderTodoUndo(body);hint=(TextView)body.children.get(0);u=(Button)body.children.get(1);u.tap();
  ok(hint.visibility==View.GONE&&u.visibility==View.GONE&&m.busy&&!m.db.token.closed,"undo_hides_before_async_without_closing_token");
  m.finish();ok(m.db.undos==1&&m.db.token.closed,"hidden_undo_still_executes");
  m=new UiModel();m.open();m.confirm();m.finish();body=m.column();m.renderTodoUndo(body);hint=(TextView)body.children.get(0);u=(Button)body.children.get(1);m.renderTodoUndo(m.column());
  ok(hint.visibility==View.GONE&&u.visibility==View.GONE&&!m.db.token.closed,"rerender_hides_old_controls_keeps_token");
  System.out.println("UI_CHECKS "+checks+" PASS MODEL_NOT_ANDROID");
 }
}
'''


# Actual members are extracted at runtime; SQLite/helper collaborators below are models.
BACKEND_SOURCE = "src/main/java/com/supercubegame/pockettodo/AppDatabase.java"
BACKEND_SCOPE = "ACTUAL_APPDATABASE_TODO_MEMBERS_MODELED_SQLITE_TX_NOT_ANDROID_OR_MEDIA"
BACKEND_MARKER = "TODO_BACKEND_MODEL "
BACKEND_LABELS = """preview_exact preview_readonly cancel_terminal missing_target foreign_preview
delete_exact delete_terminal foreign_undo undo_exact undo_terminal stale_delete stale_readonly
stale_undo stale_undo_readonly stale_undo_revision closed_preview closed_undo late_delete
late_delete_model_rollback late_delete_terminal late_undo late_undo_model_rollback
delete_side_effect delete_side_effect_rollback undo_side_effect undo_side_effect_rollback
outer_preview outer_delete""".split()
BACKEND_MUTANTS = [
    ("delete_guard", "stale_delete", "if(!Arrays.equals(plan.before,todoDeletionState(db,null,-1)))", "if(false)"),
    ("undo_guard", "stale_undo_revision", "if(!Arrays.equals(token.after,todoDeletionState(db,null,-1)))", "if(false)"),
    ("delete_readback", "delete_side_effect", "if(bump(db)!=next||!Arrays.equals(expected,todoDeletionState(db,null,-1)))", "if(bump(db)!=next)"),
    ("undo_readback", "undo_side_effect", "if(bump(db)!=next||!Arrays.equals(token.restored,todoDeletionState(db,null,0)))", "if(bump(db)!=next)"),
]


def validate_backend_host(text, source, run, attempt, digest):
    lines = [line[len(BACKEND_MARKER):] for line in text.splitlines() if line.startswith(BACKEND_MARKER)]
    assert len(lines) == 1, "Missing or duplicate actual-product backend host evidence"
    value = json.loads(lines[0])
    for key, expected in dict(status="PASS", scope=BACKEND_SCOPE, commit=source, run_id=run,
                              run_attempt=attempt, source_sha256=digest).items():
        assert type(value[key]) is str and value[key] == expected, "Backend host binding "+key
    assert type(value["checks"]) is int and value["checks"] == 28, "Backend host count"
    assert value["labels"] == BACKEND_LABELS, "Backend host labels"
    assert value["mutants_rejected"] == ["delete_guard", "undo_guard", "delete_readback", "undo_readback"]
    assert value["missing_members_rejected"] is True and value["release_ready"] is False
    assert re.fullmatch("[0-9a-f]{64}", value["source_sha256"])
    return value


def backend_host_observer_selftest():
    good = dict(status="PASS", scope=BACKEND_SCOPE, commit="a"*40, run_id="123", run_attempt="1",
                source_sha256="b"*64, checks=28, labels=BACKEND_LABELS[:],
                mutants_rejected=["delete_guard", "undo_guard", "delete_readback", "undo_readback"],
                missing_members_rejected=True, release_ready=False)
    def log(value):
        return BACKEND_MARKER+json.dumps(value)+"\n"
    args = ("a"*40, "123", "1", "b"*64)
    def accepts(checker, text):
        try:
            checker(text, *args)
        except (AssertionError, KeyError, TypeError, ValueError):
            return False
        return True
    assert validate_backend_host(log(good), *args) == good
    bad = ["", log(good)+log(good)]
    for key in good:
        value = copy.deepcopy(good);del value[key];bad.append(log(value))
    for key in ("status", "scope", "commit", "run_id", "run_attempt", "source_sha256"):
        value = copy.deepcopy(good);value[key] = "wrong";bad.append(log(value))
    for count in (0, 27, 29, True, 28.0):
        bad.append(log(dict(good, checks=count)))
    for label in BACKEND_LABELS:
        value = copy.deepcopy(good);value["labels"].remove(label);bad.append(log(value))
    for name in good["mutants_rejected"]:
        value = copy.deepcopy(good);value["mutants_rejected"].remove(name);bad.append(log(value))
    for key in ("missing_members_rejected", "release_ready"):
        for replacement in (not good[key], int(good[key])):
            value = copy.deepcopy(good);value[key] = replacement;bad.append(log(value))
    bad.append(log(dict(good, labels=BACKEND_LABELS[::-1])))
    for text in bad:
        assert not accepts(validate_backend_host, text), "Incomplete backend host evidence accepted"
    validator = inspect.getsource(validate_backend_host)
    witnesses = [
        ('assert len(lines) == 1, "Missing or duplicate actual-product backend host evidence"', 'assert True', log(good)+log(good)),
        ('assert type(value["checks"]) is int and value["checks"] == 28, "Backend host count"', 'assert True', log(dict(good, checks=True))),
        ('assert value["labels"] == BACKEND_LABELS, "Backend host labels"', 'assert True', log(dict(good, labels=BACKEND_LABELS[:-1]))),
    ]
    for old, new, witness in witnesses:
        assert validator.count(old) == 1
        namespace = dict(globals())
        exec(compile(validator.replace(old, new, 1), "<backend-host-mutant>", "exec"), namespace)
        checker = namespace["validate_backend_host"]
        assert checker(log(good), *args) == good, "Mutant failed valid witness"
        assert not accepts(validate_backend_host, witness) and accepts(checker, witness), "Non-discriminating witness"
    print("TODO_BACKEND_HOST_OBSERVER "+json.dumps(dict(positive=1, negative=len(bad),
          validator_mutants=3, scope="HOST_RECEIPT_CONTROLS_NOT_ANDROID")))


def backend_product_selftest():
    product = ROOT/BACKEND_SOURCE
    original = product.read_bytes()
    # Reuse the existing JDK AST parser, adding nested-class selection explicitly.
    start = UI_EXTRACTOR.index('   Set<String> required=')
    end = UI_EXTRACTOR.index('\n', start)
    extractor = UI_EXTRACTOR[:start]+'''   Set<String> required=new LinkedHashSet<>(List.of("TodoDeletionPlan","TodoDeletionUndo","todoDeletionState","prepareTodoDeletion","confirmTodoDeletion","undoTodoDeletion"));'''+UI_EXTRACTOR[end:]
    extractor = extractor.replace('contentEquals("TodayScreen")', 'contentEquals("AppDatabase")')
    old = 'String name=member instanceof MethodTree?'
    assert extractor.count(old) == 1
    extractor = extractor.replace(old, 'String name=member instanceof ClassTree?((ClassTree)member).getSimpleName().toString():member instanceof MethodTree?', 1)
    java = shutil.which("java") or "java"
    with tempfile.TemporaryDirectory(prefix="todo-backend-product-") as tmp:
        folder = Path(tmp);source = folder/"AppDatabase.java";source.write_bytes(original)
        (folder/"ExtractUi.java").write_text(extractor, encoding="utf-8")
        extracted = folder/"members.txt"
        def extract():
            return subprocess.run([java, str(folder/"ExtractUi.java"), str(source), str(extracted)],
                                  capture_output=True, text=True, timeout=30)
        p = extract()
        assert p.returncode == 0, "Actual backend AST extraction failed\n"+p.stdout+p.stderr
        fragment = extracted.read_text(encoding="utf-8")
        # The same parser must refuse missing members instead of testing stale fragments.
        source.write_text("class AppDatabase {}", encoding="utf-8")
        p = extract()
        assert p.returncode != 0 and "Missing product members" in p.stderr
        def run_model(code):
            source.write_text(BACKEND_MODEL_PREFIX+code+BACKEND_MODEL_SUFFIX, encoding="utf-8")
            return subprocess.run([java, str(source)], capture_output=True, text=True, timeout=30)
        p = run_model(fragment)
        assert p.returncode == 0, p.stdout+p.stderr
        labels = [line.removeprefix("BACKEND_PASS ") for line in p.stdout.splitlines() if line.startswith("BACKEND_PASS ")]
        assert labels == BACKEND_LABELS and p.stdout.splitlines()[-1] == "BACKEND_CHECKS 28 PASS MODEL_NOT_ANDROID"
        print(p.stdout, end="")
        rejected = []
        for name, label, old, new in BACKEND_MUTANTS:
            assert fragment.count(old) == 1, "Backend mutant anchor "+name
            p = run_model(fragment.replace(old, new, 1))
            assert p.returncode != 0 and "AssertionError: "+label+"\n" in p.stderr, (name, p.stdout, p.stderr)
            # All four must compile and pass the complete ordinary preview/delete/undo witness.
            observed = [line.removeprefix("BACKEND_PASS ") for line in p.stdout.splitlines() if line.startswith("BACKEND_PASS ")]
            assert observed[:10] == BACKEND_LABELS[:10], "Mutant failed before valid behavioral witness "+name
            rejected.append(name)
        assert product.read_bytes() == original, "Host model changed product source"
    value = dict(status="PASS", scope=BACKEND_SCOPE, commit=os.environ.get("GITHUB_SHA", "LOCAL"),
                 run_id=os.environ.get("GITHUB_RUN_ID", "LOCAL"), run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", "LOCAL"),
                 source_sha256=hashlib.sha256(original).hexdigest(), checks=len(labels), labels=labels,
                 mutants_rejected=rejected, missing_members_rejected=True, release_ready=False)
    print(BACKEND_MARKER+json.dumps(value), flush=True)


def backend_report_entry_selftest(report_fn=None):
    """Run the actual report body; network/publisher are explicit doubles, devices use existing valid fixtures."""
    import contextlib
    import io
    import types
    from unittest.mock import patch
    report_fn = report if report_fn is None else report_fn
    fixtures = {}
    real_validate = validate
    def capture(value, manifest, logs, api, *args):
        real_validate(value, manifest, logs, api, *args)
        fixtures.setdefault(api, copy.deepcopy((value, manifest, logs)))
    with patch.dict(globals(), validate=capture), contextlib.redirect_stdout(io.StringIO()):
        report_selftest()
    assert set(fixtures) == {26, 34}
    fake = types.ModuleType("verify_evidence");published = []
    def publish(api, path, data):
        published.append((path, json.loads(data)))
        return {"scope": "HOST_PUBLISHER_DOUBLE_NOT_REMOTE_READBACK"}
    fake.publish = publish
    with tempfile.TemporaryDirectory(prefix="todo-backend-report-") as tmp:
        root = Path(tmp)
        for path in (UI_SOURCE, BACKEND_SOURCE):
            product = root/path;product.parent.mkdir(parents=True, exist_ok=True);product.write_bytes(b"explicit host source binding fixture")
        digest = hashlib.sha256(b"explicit host source binding fixture").hexdigest()
        ui = dict(status="PASS", scope=UI_SCOPE, commit="a"*40, run_id="123", run_attempt="1",
                  source_sha256=digest, checks=29, labels=UI_LABELS[:],
                  mutants_rejected=[m[0] for m in UI_MUTANTS], missing_members_rejected=True, release_ready=False)
        backend = dict(status="PASS", scope=BACKEND_SCOPE, commit="a"*40, run_id="123", run_attempt="1",
                       source_sha256=digest, checks=28, labels=BACKEND_LABELS[:],
                       mutants_rejected=[m[0] for m in BACKEND_MUTANTS], missing_members_rejected=True, release_ready=False)
        for api, (value, manifest, logs) in fixtures.items():
            base = root/"collected-todos"/("todo-device-api-"+str(api));device = base/"todo-device";device.mkdir(parents=True)
            (base/"todo-apk.json").write_text(json.dumps(manifest))
            (device/"result.json").write_text(json.dumps(value))
            for phase, text in logs.items():(device/(phase+".log")).write_text(text)
        log = root/"collected-todos/todo-host/todo-host.log";log.parent.mkdir(parents=True)
        good = BACKEND_MARKER+json.dumps(backend)+"\n"
        cases = [(good, True), ("", False), (good+good, False)]
        for key, replacement in (("source_sha256", "b"*64), ("commit", "c"*40), ("run_id", "122"),
                                 ("run_attempt", "2"), ("checks", 28.0), ("labels", BACKEND_LABELS[:-1]),
                                 ("mutants_rejected", [m[0] for m in BACKEND_MUTANTS][:-1])):
            cases.append((BACKEND_MARKER+json.dumps(dict(backend, **{key: replacement}))+"\n", False))
        env = dict(GITHUB_SHA="a"*40, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1",
                   GITHUB_REPOSITORY="fixture/repo", NEEDS_JSON=json.dumps({"todo_host":{"result":"success"},"todo_device":{"result":"success"}}))
        with patch.dict(globals(), ROOT=root), patch.dict(sys.modules, verify_evidence=fake), patch.dict(os.environ, env):
            for text, accepted in cases:
                log.write_text(UI_MARKER+json.dumps(ui)+"\n"+text)
                published.clear()
                with contextlib.redirect_stdout(io.StringIO()):
                    try:
                        report_fn();passed = True
                    except AssertionError as exc:
                        assert str(exc) == "Todo backend evidence missing, mismatched or failed; native UI not accepted"
                        passed = False
                output = json.loads((root/"todo-report.json").read_text())
                assert passed == accepted and output["status"] == ("PASS" if accepted else "FAIL"), "Backend report accepted missing or wrong evidence"
                assert all(row["status"] == "PASS" for row in output["devices"].values())
                assert output["ui_host_model"]["status"] == "PASS"
                assert output["backend_host_model"]["status"] == ("PASS" if accepted else "FAIL")
                assert len(published) == 1 and published[0][1] == output, "Failure lost its report"
    print("TODO_BACKEND_REPORT_ENTRY "+json.dumps(dict(positive=1, negative=len(cases)-1,
          scope="ACTUAL_REPORT_BODY_HOST_FIXTURES_PUBLISHER_DOUBLE_NOT_ANDROID")))


BACKEND_MODEL_PREFIX = r'''
import java.io.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
public class AppDatabase {
 Object restoreSession=new Object();
 SQLiteDatabase sql=new SQLiteDatabase();
 static final String[] SNAPSHOT_TABLES={"revision","categories","applications","activities","paths","tags","batches","ledger","checkins","media","notes","blocks","fields","field_options","field_values","field_notes","todos","legacy_imports"};
 interface Work<T>{T run(SQLiteDatabase d);}
 SQLiteDatabase getReadableDatabase(){return sql;}
 SQLiteDatabase getWritableDatabase(){return sql;}
 void close(){restoreSession=new Object();sql.open=false;}
 <T>T tx(Work<T> w){sql.beginTransaction();try{T v=w.run(sql);sql.setTransactionSuccessful();return v;}finally{sql.endTransaction();}}
 static long revision(SQLiteDatabase d){return (Long)d.tables.get("revision").get(0)[2];}
 static long bump(SQLiteDatabase d){
  if(d.late)throw new IllegalStateException("late sentinel");
  long n=Math.incrementExact(revision(d));d.tables.get("revision").get(0)[2]=n;
  if(d.sideEffect)d.tables.get("categories").get(0)[2]="unexpected";
  return n;
 }
 static void noteDeletionNoOuterTransaction(SQLiteDatabase d){if(d.inTransaction())throw new IllegalStateException("outer");}
 static void tableSet(SQLiteDatabase d){if(!d.tables.keySet().equals(new HashSet<>(Arrays.asList(SNAPSHOT_TABLES))))throw new IllegalArgumentException("tables");}
 static class Ledger {static void identifier(String s){if(s==null||s.trim().isEmpty())throw new IllegalArgumentException("id");}}
 static class LimitedBytes extends ByteArrayOutputStream{
  public synchronized void write(int b){if(count>=8388608)throw new IllegalArgumentException("limit");super.write(b);}
  public synchronized void write(byte[] b,int o,int l){if(l>8388608-count)throw new IllegalArgumentException("limit");super.write(b,o,l);}
 }
 static void utf8(DataOutputStream o,String s)throws IOException{byte[] b=s.getBytes(StandardCharsets.UTF_8);o.writeInt(b.length);o.write(b);}
 static void blob(DataOutputStream o,byte[] b)throws IOException{o.writeInt(b.length);o.write(b);}
 static Object cell(Cursor c,int i){return c.rows.get(c.at)[i];}
 static final class Cursor implements AutoCloseable{
  final String[] names;final List<Object[]> rows;int at=-1;
  Cursor(String[] n,List<Object[]> r){names=n;rows=r;}
  boolean moveToFirst(){at=0;return at<rows.size();}
  boolean moveToNext(){return ++at<rows.size();}
  String getString(int i){return (String)rows.get(at)[i];}
  int getInt(int i){return ((Number)rows.get(at)[i]).intValue();}
  long getLong(int i){return ((Number)rows.get(at)[i]).longValue();}
  int getColumnCount(){return names.length;}
  String[] getColumnNames(){return names;}
  int getCount(){return rows.size();}
  int getColumnIndexOrThrow(String n){for(int i=0;i<names.length;i++)if(names[i].equals(n))return i;throw new IllegalArgumentException(n);}
  int getType(int i){Object v=rows.get(at)[i];return v==null?0:v instanceof Long?1:v instanceof String?3:4;}
  public void close(){}
 }
 static final class SQLiteDatabase{
  Map<String,List<Object[]>> tables=new LinkedHashMap<>(),saved;
  boolean transaction,success,open=true,late,sideEffect;
  SQLiteDatabase(){
   for(String t:SNAPSHOT_TABLES)tables.put(t,new ArrayList<>());
   tables.get("revision").add(new Object[]{1L,1L,7L});
   tables.get("categories").add(new Object[]{1L,1L,"category",0L});
   tables.get("todos").add(new Object[]{3L,"first","Same",0L,10L});
   tables.get("todos").add(new Object[]{8L,"target","Same",1L,11L});
   tables.get("todos").add(new Object[]{9L,"last","Last",0L,12L});
  }
  boolean inTransaction(){return transaction;}
  boolean isOpen(){return open;}
  int getVersion(){return 3;}
  void beginTransaction(){if(transaction||!open)throw new IllegalStateException("connection");transaction=true;success=false;saved=new LinkedHashMap<>();for(String t:tables.keySet()){List<Object[]> r=new ArrayList<>();for(Object[] row:tables.get(t))r.add(row.clone());saved.put(t,r);}}
  void setTransactionSuccessful(){success=true;}
  void endTransaction(){if(!success)tables=saved;transaction=false;}
  Cursor rawQuery(String q,String[] args){
   if(q.equals("SELECT title,done,position,rowid FROM todos WHERE id=?")){
    List<Object[]> out=new ArrayList<>();for(Object[] r:tables.get("todos"))if(r[1].equals(args[0]))out.add(new Object[]{r[2],r[3],r[4],r[0]});
    return new Cursor(new String[]{"title","done","position","rowid"},out);
   }
   if(q.startsWith("SELECT rowid,* FROM ")&&q.endsWith(" ORDER BY rowid")){
    String t=q.substring(20,q.length()-15);
    String[] names=t.equals("todos")?new String[]{"rowid","id","title","done","position"}:
      t.equals("revision")?new String[]{"id","id","value"}:
      t.equals("categories")?new String[]{"id","id","name","position"}:new String[]{"rowid","id"};
    if(!tables.containsKey(t))throw new AssertionError("query table "+t);
    return new Cursor(names,tables.get(t));
   }throw new AssertionError("query "+q);
  }
  int delete(String table,String where,String[] args){
   if(!transaction)throw new AssertionError("delete outside tx");
   if(!table.equals("todos")||!where.equals("id=?"))throw new AssertionError("delete query");
   int old=tables.get(table).size();tables.get(table).removeIf(r->r[1].equals(args[0]));return old-tables.get(table).size();
  }
  void execSQL(String q,Object[] values){
   if(!transaction||!q.equals("INSERT INTO todos(rowid,id,title,done,position) VALUES(?,?,?,?,?)"))throw new AssertionError("insert query");
   for(Object[] r:tables.get("todos"))if(r[0].equals(values[0])||r[1].equals(values[1])||r[4].equals(values[4]))throw new IllegalArgumentException("collision");
   Object[] row=values.clone();row[3]=((Number)row[3]).longValue();tables.get("todos").add(row);
   tables.get("todos").sort(Comparator.comparingLong(r->(Long)r[0]));
  }
 }
'''

BACKEND_MODEL_SUFFIX = r'''
 static java.util.Map<String,String> rows(AppDatabase h,String omit,long rev){
  java.util.Map<String,String> result=new java.util.TreeMap<>();
  for(String table:h.sql.tables.keySet()){
   java.util.List<String> values=new java.util.ArrayList<>();
   for(Object[] original:h.sql.tables.get(table)){
    if(table.equals("todos")&&java.util.Objects.equals(original[1],omit))continue;
    Object[] row=original.clone();if(table.equals("revision")&&rev>=0)row[2]=rev;
    values.add(java.util.Arrays.deepToString(row));
   }
   result.put(table,values.toString());
  }
  return result;
 }
 static int checks;
 interface Attempt{void run();}
 static void ok(boolean v,String name){if(!v)throw new AssertionError(name);checks++;System.out.println("BACKEND_PASS "+name);}
 static void reject(Attempt a,String name){boolean bad=false;try{a.run();}catch(IllegalStateException|IllegalArgumentException e){bad=true;}ok(bad,name);}
 static byte[] state(AppDatabase h){return todoDeletionState(h.sql,null,-1);}
 public static void main(String[] args){
  AppDatabase h=new AppDatabase();byte[] before=state(h);
  TodoDeletionPlan p=h.prepareTodoDeletion("target");
  ok(p.todoId().equals("target")&&p.title().equals("Same")&&p.done()&&p.position()==11,"preview_exact");
  ok(Arrays.equals(before,state(h)),"preview_readonly");
  p.close();reject(()->h.confirmTodoDeletion(p),"cancel_terminal");
  reject(()->h.prepareTodoDeletion("missing"),"missing_target");
  TodoDeletionPlan fresh=h.prepareTodoDeletion("target");AppDatabase other=new AppDatabase();
  reject(()->other.confirmTodoDeletion(fresh),"foreign_preview");
  byte[] expected=todoDeletionState(h.sql,"target",8),shape=todoDeletionState(h.sql,null,0);
  java.util.Map<String,String> directDeleted=rows(h,"target",8),directRestored=rows(h,null,9);
  TodoDeletionUndo u=h.confirmTodoDeletion(fresh);
  ok(Arrays.equals(expected,state(h))&&revision(h.sql)==8&&rows(h,null,-1).equals(directDeleted),"delete_exact");
  reject(()->h.confirmTodoDeletion(fresh),"delete_terminal");
  reject(()->other.undoTodoDeletion(u),"foreign_undo");
  h.undoTodoDeletion(u);
  ok(Arrays.equals(shape,todoDeletionState(h.sql,null,0))&&revision(h.sql)==9&&rows(h,null,-1).equals(directRestored),"undo_exact");
  reject(()->h.undoTodoDeletion(u),"undo_terminal");
  AppDatabase stale=new AppDatabase();TodoDeletionPlan sp=stale.prepareTodoDeletion("target");
  stale.sql.tables.get("categories").get(0)[2]="external";byte[] changed=state(stale);
  reject(()->stale.confirmTodoDeletion(sp),"stale_delete");ok(Arrays.equals(changed,state(stale)),"stale_readonly");
  AppDatabase su=new AppDatabase();TodoDeletionUndo ut=su.confirmTodoDeletion(su.prepareTodoDeletion("target"));
  su.sql.tables.get("categories").get(0)[2]="external";byte[] changedUndo=state(su);
  reject(()->su.undoTodoDeletion(ut),"stale_undo");ok(Arrays.equals(changedUndo,state(su)),"stale_undo_readonly");
  AppDatabase revisionOnly=new AppDatabase();TodoDeletionUndo revToken=revisionOnly.confirmTodoDeletion(revisionOnly.prepareTodoDeletion("target"));
  revisionOnly.sql.tables.get("revision").get(0)[2]=9L;
  reject(()->revisionOnly.undoTodoDeletion(revToken),"stale_undo_revision");
  AppDatabase closing=new AppDatabase();TodoDeletionPlan cp=closing.prepareTodoDeletion("target");closing.close();
  reject(()->closing.confirmTodoDeletion(cp),"closed_preview");
  AppDatabase cu=new AppDatabase();TodoDeletionUndo cut=cu.confirmTodoDeletion(cu.prepareTodoDeletion("target"));cu.close();
  reject(()->cu.undoTodoDeletion(cut),"closed_undo");
  AppDatabase late=new AppDatabase();TodoDeletionPlan lp=late.prepareTodoDeletion("target");byte[] lb=state(late);late.sql.late=true;
  reject(()->late.confirmTodoDeletion(lp),"late_delete");
  ok(Arrays.equals(lb,state(late)),"late_delete_model_rollback");late.sql.late=false;
  reject(()->late.confirmTodoDeletion(lp),"late_delete_terminal");
  AppDatabase lu=new AppDatabase();TodoDeletionUndo lut=lu.confirmTodoDeletion(lu.prepareTodoDeletion("target"));byte[] lub=state(lu);lu.sql.late=true;
  reject(()->lu.undoTodoDeletion(lut),"late_undo");ok(Arrays.equals(lub,state(lu)),"late_undo_model_rollback");
  AppDatabase side=new AppDatabase();TodoDeletionPlan sidep=side.prepareTodoDeletion("target");byte[] sideb=state(side);side.sql.sideEffect=true;
  reject(()->side.confirmTodoDeletion(sidep),"delete_side_effect");ok(Arrays.equals(sideb,state(side)),"delete_side_effect_rollback");
  AppDatabase sidu=new AppDatabase();TodoDeletionUndo sidut=sidu.confirmTodoDeletion(sidu.prepareTodoDeletion("target"));byte[] sidub=state(sidu);sidu.sql.sideEffect=true;
  reject(()->sidu.undoTodoDeletion(sidut),"undo_side_effect");ok(Arrays.equals(sidub,state(sidu)),"undo_side_effect_rollback");
  AppDatabase nested=new AppDatabase();TodoDeletionPlan np=nested.prepareTodoDeletion("target");nested.sql.beginTransaction();
  reject(()->nested.prepareTodoDeletion("target"),"outer_preview");reject(()->nested.confirmTodoDeletion(np),"outer_delete");nested.sql.endTransaction();
  System.out.println("BACKEND_CHECKS "+checks+" PASS MODEL_NOT_ANDROID");
 }
}
'''


def installed_readback(run, prefix, package, expected, records):
    """One installed-path query and one primary exact-byte pull; no retry/fallback."""
    from verify_adb_transfer import pull_exact
    record = dict(status="FAIL", expected_bytes=len(expected),
                  expected_sha256=hashlib.sha256(expected).hexdigest(),
                  method="ADB_PULL_SINGLE_PRIMARY_EXACT_BYTES", budget_seconds=30)
    records.append(record)
    try:
        assert len(prefix) == 3 and prefix[1:] == ["-s", "emulator-5554"], "Explicit emulator prefix required"
        paths = re.findall(r"^package:(\S+)\s*$", run(prefix+["shell", "pm", "path", package]), re.M)
        record["paths"] = paths
        assert len(paths) == 1, "One installed product APK path required"
        transfer = {};record["transfer"] = transfer
        try:
            actual = pull_exact(prefix[0], prefix[2], paths[0], expected, transfer)
        finally:
            for key in ("actual_bytes", "actual_sha256"):
                if key in transfer: record[key] = transfer[key]
            record["exact"] = transfer.get("status") == "PASS"
        record.update(actual_bytes=len(actual), actual_sha256=hashlib.sha256(actual).hexdigest(),
                      exact=actual == expected)
        assert actual == expected, "Installed product readback differs: "+json.dumps(record, sort_keys=True)
        record["status"] = "PASS"
        return actual
    except BaseException as exc:
        record["error"] = repr(exc)
        raise


def shared_pull_contracts(checker, modes=None):
    import verify_adb_transfer as transfer
    from unittest.mock import patch
    payload = bytes(range(256))*3+b"\x00\r\n\xff"
    prefix = ["fixture-adb", "-s", "emulator-5554"]
    remote = "/data/app/fixture/base.apk"
    modes = modes or ("exact", "short", "wrong", "extra", "empty", "timeout",
                      "exit255", "missing", "multiple", "path_error", "invalid_path",
                      "directory", "symlink", "missing_file", "late", "lateverify")
    for mode in modes:
        queries = []; pulls = []; records = []
        sentinel = (subprocess.TimeoutExpired(["fixture"], 30, output=b"partial", stderr=b"timeout")
                    if mode == "timeout" else RuntimeError("path query sentinel"))
        def run(args, timeout=60, binary=False):
            queries.append((args, timeout, binary))
            assert len(queries) == 1, "path query retried or exec-out used"
            assert args == prefix+["shell", "pm", "path", PACKAGE] and timeout == 60 and not binary
            if mode == "path_error": raise sentinel
            path = "/sdcard/base.apk" if mode == "invalid_path" else remote
            return "" if mode == "missing" else "package:"+path+"\n"+("package:/data/app/other/base.apk\n" if mode == "multiple" else "")
        def invoke(command, **kwargs):
            pulls.append(command)
            assert len(pulls) == 1, "installed transfer retried"
            assert command[:6] == prefix+["pull", "-Z", remote] and len(command) == 7
            assert kwargs == dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=30)
            target = Path(command[-1])
            assert target.parent.is_dir() and not target.exists() and not target.is_symlink()
            if mode == "timeout":
                target.write_bytes(payload[:7]); raise sentinel
            if mode == "directory": target.mkdir()
            elif mode == "symlink":
                sibling = target.parent/"other"; sibling.write_bytes(payload); target.symlink_to(sibling)
            elif mode != "missing_file":
                value = payload[:-1] if mode == "short" else b"X"+payload[1:] if mode == "wrong" else payload+b"x" if mode == "extra" else b"" if mode == "empty" else payload
                target.write_bytes(value)
            return subprocess.CompletedProcess(command, 255 if mode == "exit255" else 0, b"out", b"err")
        ticks = iter([0, 0, 31] if mode == "late" else [0, 0, 1, 31] if mode == "lateverify" else [0, 0, 1, 2])
        caught = None
        with patch.object(transfer.subprocess, "run", invoke), patch.object(transfer.time, "monotonic", lambda: next(ticks)):
            try: actual = checker(run, prefix, PACKAGE, payload, records)
            except BaseException as exc: caught = exc
        assert len(records) == len(queries) == 1, "single path query and retained receipt"
        assert len(pulls) == (0 if mode in ("missing", "multiple", "path_error", "invalid_path") else 1), "single primary pull"
        assert all(not Path(command[-1]).parent.exists() for command in pulls), "temporary file leaked"
        record = records[0]
        assert record["method"] == "ADB_PULL_SINGLE_PRIMARY_EXACT_BYTES" and record["budget_seconds"] == 30
        assert record["expected_bytes"] == len(payload) and record["expected_sha256"] == hashlib.sha256(payload).hexdigest()
        if mode == "exact":
            assert caught is None and actual == payload and record["status"] == "PASS" and record["exact"] is True, repr(caught)
            assert record["actual_bytes"] == len(payload) and record["actual_sha256"] == record["expected_sha256"]
            assert record["transfer"]["status"] == "PASS" and record["transfer"]["attempts"] == 1
        else:
            assert caught is not None and record["status"] == "FAIL" and record["error"] == repr(caught), "failure preserved"
            if mode in ("timeout", "path_error"): assert caught is sentinel, "original exception identity"
            if mode in ("short", "wrong", "extra", "empty"):
                size = {"short":len(payload)-1, "wrong":len(payload), "extra":len(payload)+1, "empty":0}[mode]
                assert type(caught) is AssertionError and str(caught) == "installed product bytes differ from built APK"
                assert record["actual_bytes"] == size and record["exact"] is False, "actual mismatch diagnostics"
                assert record["actual_sha256"] != record["expected_sha256"]
            if mode == "exit255":
                assert type(caught) is subprocess.CalledProcessError and (caught.returncode, caught.stdout, caught.stderr) == (255, b"out", b"err")
            if mode == "timeout":
                assert record["transfer"]["stdout_tail"] == "partial" and record["transfer"]["stderr_tail"] == "timeout"
            if mode in ("late", "lateverify"): assert type(caught) is TimeoutError
            if mode in ("directory", "symlink"): assert type(caught) is AssertionError and "regular file" in str(caught)
            if mode == "missing_file": assert type(caught) is FileNotFoundError
            if pulls:
                assert record["transfer"]["status"] == "FAIL" and record["transfer"]["error"] == repr(caught)
    return len(modes)


def installed_readback_selftest():
    import verify_adb_transfer as transfer
    from unittest.mock import patch
    checker = installed_readback
    count = shared_pull_contracts(checker)
    original = transfer.pull_exact
    source = inspect.getsource(original)
    changes = [
        ("actual == expected and opened.st_size == len(expected)", "True"),
        ("if result.returncode != 0:", "if False:"),
        ("if clock() >= deadline:", "if False:"),
        ("if elapsed >= 30:", "if False:"),
        ("actual_bytes=len(actual)", "actual_bytes=len(expected)"),
    ]
    for old, new in changes:
        assert source.count(old) == 1 and old != new
        namespace = dict(vars(transfer))
        exec(compile(source.replace(old, new, 1), "<shared-pull-helper-mutant>", "exec"), namespace)
        with patch.object(transfer, "pull_exact", namespace["pull_exact"]):
            shared_pull_contracts(checker, ("exact",))
            try: shared_pull_contracts(checker)
            except AssertionError: pass
            else: raise AssertionError("Shared pull mutant survived: "+old)
    print("SHARED_INSTALLED_PULL host_positive=1 negative="+str(count-1)+" compiled_mutants="+str(len(changes))+" valid_witnesses="+str(len(changes))+" PASS; HOST_ONLY_NOT_ANDROID")



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
            return installed_readback(run, prefix, gate.PKG, product, result.setdefault("installed_readbacks", []))
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
    host = {"status": "FAIL"}
    try:
        log = (ROOT/"collected-todos/todo-host/todo-host.log").read_text(encoding="utf-8")
        host = validate_ui_host(log, source, run, attempt, hashlib.sha256((ROOT/UI_SOURCE).read_bytes()).hexdigest())
    except (OSError, ValueError, AssertionError, KeyError, TypeError) as e:
        passed = False;host["error"] = repr(e)
    backend_host = {"status": "FAIL"}
    try:
        log = (ROOT/"collected-todos/todo-host/todo-host.log").read_text(encoding="utf-8")
        backend_host = validate_backend_host(log, source, run, attempt, hashlib.sha256((ROOT/BACKEND_SOURCE).read_bytes()).hexdigest())
    except (OSError, ValueError, AssertionError, KeyError, TypeError) as e:
        passed = False;backend_host["error"] = repr(e)
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
                 native_ui="NOT_IMPLEMENTED", ui_host_model=host, backend_host_model=backend_host, release_ready=False, durable_upgrade_ready=False)
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
