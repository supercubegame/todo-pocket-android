#!/usr/bin/env python3
"""Execute the real draft store on JDK17; not Android UI or power-loss proof."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = "src/main/java/com/supercubegame/pockettodo/NoteDraftStore.java"
LABELS = """initial_absence exact_text read_exact_token helper_reopen same_save_readonly
stale_save stale_clear stale_keeps_bytes matching_base changed_body_refused invalid_current_base
slot_isolation slot_isolation slot_isolation slot_isolation clear_tombstone
absent_token_cannot_replay old_token_cannot_replay cleared_not_recoverable clear_keeps_siblings
repeat_clear_readonly empty_draft_not_deletion whitespace_preserved null_text bad_utf16 bad_base
null_expected over_text_budget invalid_keeps_bytes zero_owner negative_owner blank_note blank_block
bad_identity_utf16 identity_not_path exact_text_budget checksum_rejected corruption_not_overwritten
corruption_preserved truncated_rejected trailing_rejected unknown_version_rejected
symlink_payload_rejected symlink_write_rejected outside_unchanged symlink_root_rejected
symlink_lock_rejected lock_outside_unchanged nonfile_target_rejected nonfile_no_temp_residue
prior_bytes_reopen""".split()
BOOT = r'''
import javax.tools.ToolProvider;
public class CompileDrafts {
 public static void main(String[] args){
  int code=ToolProvider.getSystemJavaCompiler().run(null,System.out,System.err,args);
  if(code!=0)System.exit(code);
 }
}
'''
TEST = r'''
import com.supercubegame.pockettodo.NoteDraftStore;
import com.supercubegame.pockettodo.NoteDraftStore.Slot;
import com.supercubegame.pockettodo.NoteDraftStore.Record;
import java.nio.file.*;
import java.util.*;
import java.io.*;
import java.security.*;
public class DraftContract {
 static int checks;
 static final String BASE="a".repeat(64), CHANGED="b".repeat(64);
 interface Action {void run()throws Exception;}
 static void ok(boolean value,String label){if(!value)throw new AssertionError(label);checks++;System.out.println("DRAFT_PASS "+label);}
 static void reject(Class<? extends Throwable> type,Action action,String label)throws Exception{
  Throwable caught=null;try{action.run();}catch(Throwable e){caught=e;}
  ok(caught!=null&&caught.getClass()==type,label);
 }
 static Map<String,String> files(Path root)throws Exception{
  Map<String,String> out=new TreeMap<>();
  try(var stream=Files.list(root)){
   for(Path p:stream.toArray(Path[]::new))if(Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS))
    out.put(p.getFileName().toString(),Base64.getEncoder().encodeToString(Files.readAllBytes(p)));
  }return out;
 }
 static Path payload(Path root)throws Exception{
  try(var s=Files.list(root)){return s.filter(p->p.toString().endsWith(".draft")).findFirst().orElseThrow();}
 }
 public static void main(String[] args)throws Exception{
  Path root=Path.of(args[1]);
  Slot slot=new Slot(1,"same-title-a","text");
  if(args[0].equals("read")){
   Record r=new NoteDraftStore(root).read(slot);
   if(!r.text.equals("  草稿😀\nline\n")||!r.base.equals(BASE))throw new AssertionError("process_read");
   System.out.println("PROCESS_READ_EXACT");return;
  }
  if(args[0].equals("race")){
   try{new NoteDraftStore(root).save(slot,args[2],BASE,args[3]);System.out.println("CAS_WIN");}
   catch(IllegalStateException e){if(!e.getMessage().equals("Draft changed; reopen"))throw e;System.out.println("CAS_STALE");}
   return;
  }
  NoteDraftStore store=new NoteDraftStore(root);
  Record empty=store.read(slot);
  ok(empty.token.equals("")&&empty.text==null&&empty.base==null,"initial_absence");
  Record first=store.save(slot,empty.token,BASE,"  草稿😀\nline\n");
  ok(first.text.equals("  草稿😀\nline\n")&&first.base.equals(BASE)&&!first.token.isEmpty(),"exact_text");
  ok(store.read(slot).token.equals(first.token),"read_exact_token");
  ok(new NoteDraftStore(root).read(slot).text.equals(first.text),"helper_reopen");
  Map<String,String> frozen=files(root);
  ok(store.save(slot,first.token,BASE,first.text).token.equals(first.token)&&files(root).equals(frozen),"same_save_readonly");
  reject(IllegalStateException.class,()->store.save(slot,"",BASE,"lost"),"stale_save");
  reject(IllegalStateException.class,()->store.clear(slot,""),"stale_clear");
  ok(files(root).equals(frozen),"stale_keeps_bytes");
  ok(first.requireBase(BASE).equals(first.text),"matching_base");
  reject(IllegalStateException.class,()->first.requireBase(CHANGED),"changed_body_refused");
  reject(IllegalArgumentException.class,()->first.requireBase(null),"invalid_current_base");
  Slot sibling=new Slot(1,"same-title-b","text"),foreign=new Slot(2,"same-title-a","text"),other=new Slot(1,"same-title-a","other"),addition=new Slot(1,"same-title-a",null);
  for(Slot key:new Slot[]{sibling,foreign,other,addition})ok(store.read(key).text==null,"slot_isolation");
  Record b=store.save(sibling,"",BASE,"sibling");
  Record added=store.save(addition,"",BASE,"new block");
  Record cleared=store.clear(slot,first.token);
  ok(cleared.text==null&&!cleared.token.equals(first.token)&&!cleared.token.isEmpty(),"clear_tombstone");
  reject(IllegalStateException.class,()->store.save(slot,"",BASE,"ABA"),"absent_token_cannot_replay");
  reject(IllegalStateException.class,()->store.save(slot,first.token,BASE,"ABA"),"old_token_cannot_replay");
  reject(IllegalStateException.class,()->cleared.requireBase(BASE),"cleared_not_recoverable");
  ok(store.read(sibling).token.equals(b.token)&&store.read(addition).token.equals(added.token),"clear_keeps_siblings");
  frozen=files(root);
  ok(store.clear(slot,cleared.token).token.equals(cleared.token)&&files(root).equals(frozen),"repeat_clear_readonly");
  Record blank=store.save(slot,cleared.token,BASE,"");
  ok(blank.text.equals("")&&blank.requireBase(BASE).equals(""),"empty_draft_not_deletion");
  Record spaces=store.save(slot,blank.token,BASE," \n ");
  ok(spaces.text.equals(" \n "),"whitespace_preserved");
  frozen=files(root);
  reject(IllegalArgumentException.class,()->store.save(slot,spaces.token,BASE,null),"null_text");
  reject(IllegalArgumentException.class,()->store.save(slot,spaces.token,BASE,"\ud800"),"bad_utf16");
  reject(IllegalArgumentException.class,()->store.save(slot,spaces.token,"wrong","body"),"bad_base");
  reject(IllegalArgumentException.class,()->store.save(slot,null,BASE,"body"),"null_expected");
  reject(IllegalArgumentException.class,()->store.save(slot,spaces.token,BASE,"x".repeat(8388609)),"over_text_budget");
  ok(files(root).equals(frozen),"invalid_keeps_bytes");
  reject(IllegalArgumentException.class,()->new Slot(0,"note",null),"zero_owner");
  reject(IllegalArgumentException.class,()->new Slot(-1,"note",null),"negative_owner");
  reject(IllegalArgumentException.class,()->new Slot(1," ",null),"blank_note");
  reject(IllegalArgumentException.class,()->new Slot(1,"note",""),"blank_block");
  reject(IllegalArgumentException.class,()->new Slot(1,"\ud800",null),"bad_identity_utf16");
  // Identity is serialized, never interpolated into a path.
  Slot traversal=new Slot(1,"../outside","../../escape");
  Record pathText=store.save(traversal,"",BASE,"safe");
  ok(store.read(traversal).token.equals(pathText.token)&&!Files.exists(root.getParent().resolve("escape")),"identity_not_path");
  Record exact=store.save(slot,spaces.token,BASE,"x".repeat(8388608));
  ok(store.read(slot).text.length()==8388608,"exact_text_budget");
  store.save(slot,exact.token,BASE,"  草稿😀\nline\n");
  Path corruptRoot=Files.createDirectory(root.resolveSibling("corrupt"));
  NoteDraftStore corrupt=new NoteDraftStore(corruptRoot);Record original=corrupt.save(slot,"",BASE,"original");
  Path file=payload(corruptRoot);byte[] bytes=Files.readAllBytes(file);
  byte[] damaged=bytes.clone();damaged[damaged.length-1]^=1;Files.write(file,damaged);
  reject(IOException.class,()->corrupt.read(slot),"checksum_rejected");
  reject(IOException.class,()->corrupt.save(slot,original.token,BASE,"overwrite"),"corruption_not_overwritten");
  ok(Arrays.equals(Files.readAllBytes(file),damaged),"corruption_preserved");
  Files.write(file,Arrays.copyOf(bytes,bytes.length-1));
  reject(IOException.class,()->corrupt.read(slot),"truncated_rejected");
  Files.write(file,Arrays.copyOf(bytes,bytes.length+1));
  reject(IOException.class,()->corrupt.read(slot),"trailing_rejected");
  // Keep checksum valid while making the version invalid.
  byte[] version=bytes.clone();version[7]=99;
  byte[] digest=MessageDigest.getInstance("SHA-256").digest(Arrays.copyOf(version,version.length-32));
  System.arraycopy(digest,0,version,version.length-32,32);Files.write(file,version);
  reject(IOException.class,()->corrupt.read(slot),"unknown_version_rejected");
  Files.write(file,bytes);
  Path outside=Files.write(root.resolveSibling("outside-payload"),bytes);
  Files.delete(file);Files.createSymbolicLink(file,outside);
  reject(IOException.class,()->corrupt.read(slot),"symlink_payload_rejected");
  reject(IOException.class,()->corrupt.save(slot,original.token,BASE,"overwrite"),"symlink_write_rejected");
  ok(Arrays.equals(Files.readAllBytes(outside),bytes),"outside_unchanged");
  Path link=root.resolveSibling("root-link");Files.createSymbolicLink(link,root);
  reject(IOException.class,()->new NoteDraftStore(link),"symlink_root_rejected");
  Path lockRoot=Files.createDirectory(root.resolveSibling("lock-root"));
  Files.createSymbolicLink(lockRoot.resolve(".lock"),outside);
  reject(IOException.class,()->new NoteDraftStore(lockRoot).read(slot),"symlink_lock_rejected");
  ok(Arrays.equals(Files.readAllBytes(outside),bytes),"lock_outside_unchanged");
  Path failRoot=Files.createDirectory(root.resolveSibling("fail-root"));
  NoteDraftStore failing=new NoteDraftStore(failRoot);Record prior=failing.save(slot,"",BASE,"keep");
  Path target=payload(failRoot);byte[] priorBytes=Files.readAllBytes(target);
  Files.delete(target);Files.createDirectory(target);
  reject(IOException.class,()->failing.save(slot,prior.token,BASE,"wrong"),"nonfile_target_rejected");
  ok(Files.isDirectory(target)&&files(failRoot).keySet().equals(Set.of(".lock")),"nonfile_no_temp_residue");
  Files.delete(target);Files.write(target,priorBytes);
  ok(failing.read(slot).text.equals("keep"),"prior_bytes_reopen");
  System.out.println("DRAFT_RESULT "+checks+" PASS");
 }
}
'''


def command(args, **kw):
    result = subprocess.run(list(map(str, args)), text=True, capture_output=True, timeout=60, **kw)
    print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", flush=True)
    if result.returncode:
        raise RuntimeError("Draft command failed with exit "+str(result.returncode))
    return result.stdout


def selftest():
    java = shutil.which("java")
    if not java:
        home = os.environ.get("JAVA_HOME")
        java = str(Path(home)/"bin/java") if home else None
    if not java:
        raise RuntimeError("JDK17 required; no Java tests executed")
    product = ROOT/PRODUCT
    if not product.is_file():
        raise RuntimeError("Draft product source missing; no storage behavior verified")
    with tempfile.TemporaryDirectory(prefix="note-draft-contract-") as tmp:
        folder = Path(tmp)
        boot = folder/"CompileDrafts.java"; boot.write_text(BOOT)
        test = folder/"DraftContract.java"; test.write_text(TEST)
        classes = folder/"classes"; classes.mkdir()
        command([java, boot, "--release", "8", "-encoding", "UTF-8", "-d", classes, product])
        command([java, boot, "-encoding", "UTF-8", "-cp", classes, "-d", classes, test])
        root = folder/"drafts"
        output = command([java, "-cp", classes, "DraftContract", "test", root])
        labels = [line.removeprefix("DRAFT_PASS ") for line in output.splitlines() if line.startswith("DRAFT_PASS ")]
        if labels != LABELS or output.splitlines()[-1] != "DRAFT_RESULT 51 PASS":
            raise AssertionError("Incomplete draft contract output")
        command([java, "-cp", classes, "DraftContract", "read", root])
        # Two separate processes compete with one identical expected token.
        # Read the token with an independent format reader, not product API.
        import struct
        records = []
        for p in root.glob("*.draft"):
            data = p.read_bytes(); at = 16
            def string():
                nonlocal at
                size = struct.unpack_from(">i", data, at)[0]; at += 4
                value = data[at:at+size].decode("utf-8"); at += size
                return value
            note = string(); has_block = data[at]; at += 1
            block = string() if has_block else None
            token = string()
            if note == "same-title-a" and block == "text":
                records.append(token)
        assert len(records) == 1
        args = [java, "-cp", str(classes), "DraftContract", "race", str(root), records[0]]
        workers = [subprocess.Popen(args+[text], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for text in ("writer-one", "writer-two")]
        outputs = []
        try:
            for worker in workers:
                stdout, stderr = worker.communicate(timeout=30)
                assert worker.returncode == 0, stderr
                outputs.append(stdout.strip())
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill(); worker.wait()
        assert sorted(outputs) == ["CAS_STALE", "CAS_WIN"], outputs
        mutations = (
            ('if(!before.token.equals(expectedToken))', 'if(false)', 'stale_save'),
            ('if(text==null||!base.equals(current))', 'if(text==null)', 'changed_body_refused'),
            ('if(!MessageDigest.isEqual(digest(body),Arrays.copyOfRange(raw,raw.length-32,raw.length)))',
             'if(false)', 'checksum_rejected'),
        )
        source = product.read_text()
        for index, (before, after, failure) in enumerate(mutations):
            assert source.count(before) == 1, "Mutation anchor changed"
            mutated = folder/("mutant-"+str(index)); mutated.mkdir()
            candidate = mutated/"NoteDraftStore.java"
            candidate.write_text(source.replace(before, after, 1))
            command([java, boot, "--release", "8", "-encoding", "UTF-8", "-d", mutated, candidate])
            run = subprocess.run([java, "-cp", os.pathsep.join((str(mutated), str(classes))),
                                  "DraftContract", "test", str(mutated/"drafts")],
                                 text=True, capture_output=True, timeout=60)
            assert run.returncode != 0 and "AssertionError: "+failure in run.stderr, (
                "Mutant survived or failed for wrong reason", failure, run.stdout, run.stderr)
            print("DRAFT_MUTANT_REJECTED "+failure, flush=True)
        result = {"status": "PASS", "scope": "REAL_JDK17_DRAFT_FILES_NOT_ANDROID_UI_OR_POWERLOSS",
                  "commit": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID"),
                  "checks": len(labels), "labels": labels, "separate_process_read": True,
                  "two_process_cas": outputs, "compiled_product_mutants": len(mutations),
                  "release_ready": False}
        print("NOTE_DRAFT_HOST "+json.dumps(result), flush=True)
        return result



SESSION_STUBS = r'''
@@ android/database/Cursor.java
package android.database;
public class Cursor implements AutoCloseable {
 private final boolean found; private final long owner;
 public Cursor(boolean f,long o){found=f;owner=o;}
 public boolean moveToFirst(){return found;}
 public long getLong(int i){return owner;}
 public void close(){}
}
@@ android/database/sqlite/SQLiteDatabase.java
package android.database.sqlite;
import android.database.Cursor;
import com.supercubegame.pockettodo.AppDatabase;
public class SQLiteDatabase {
 public final AppDatabase app;public boolean outer,tx,success,open=true;
 public SQLiteDatabase(AppDatabase a){app=a;}
 public boolean inTransaction(){return outer||tx;}
 public boolean isOpen(){return open;}
 public void beginTransaction(){if(inTransaction())throw new IllegalStateException("nested");tx=true;success=false;app.backup();}
 public void setTransactionSuccessful(){success=true;}
 public void endTransaction(){boolean committed=success;tx=false;if(!success)app.rollback();
  if(committed&&app.wrote){app.wrote=false;Runnable r=app.afterCommit;app.afterCommit=null;if(r!=null)r.run();}}
 public Cursor rawQuery(String sql,String[] args){
  if(!sql.equals("SELECT activity_id FROM notes WHERE id=?"))throw new AssertionError("unexpected query "+sql);
  return new Cursor("note".equals(args[0]),1);
 }
}
@@ com/supercubegame/pockettodo/AppDatabase.java
package com.supercubegame.pockettodo;
import java.util.*;
public class AppDatabase {
 public final android.database.sqlite.SQLiteDatabase sql=new android.database.sqlite.SQLiteDatabase(this);
 public List<NoteDocument.Block> blocks=new ArrayList<>(Arrays.asList(NoteDocument.Block.text("block","original",true)));
 public long revision;public int writes;public boolean failSave,wrote,guardInside,saveInside;
 public Runnable afterCommit;private List<NoteDocument.Block> prior;private long oldRevision;private int oldWrites;
 public android.database.sqlite.SQLiteDatabase getWritableDatabase(){return sql;}
 public List<NoteDocument.Block> noteBlocks(String id){return new ArrayList<>(blocks);}
 public byte[] exportState(){guardInside|=sql.tx;String s=revision+"";
  for(NoteDocument.Block b:blocks)s+="|"+b.id+"|"+b.text+"|"+b.privateContent;
  return s.getBytes(java.nio.charset.StandardCharsets.UTF_8);}
 public void saveNote(String id,List<NoteDocument.Block> b){if(!sql.tx)throw new AssertionError("save outside transaction");
  saveInside=true;blocks=new ArrayList<>(b);revision++;writes++;wrote=true;if(failSave)throw new IllegalStateException("injected late write failure");}
 public void external(String text){blocks.set(0,NoteDocument.Block.text("block",text,true));}
 public void backup(){prior=new ArrayList<>(blocks);oldRevision=revision;oldWrites=writes;}
 public void rollback(){blocks=prior;revision=oldRevision;writes=oldWrites;wrote=false;}
}
@@ com/supercubegame/pockettodo/NoteDocument.java
package com.supercubegame.pockettodo;
public class NoteDocument {
 public enum Kind {TEXT,IMAGE}
 public static class Block {
  public String id,text,assetId,caption="";public boolean privateContent;public Kind kind;
  public static Block text(String id,String text,boolean privacy){Block b=new Block();b.id=id;b.text=text;b.kind=Kind.TEXT;b.privateContent=privacy;return b;}
 }
}
@@ com/supercubegame/pockettodo/MediaRepository.java
package com.supercubegame.pockettodo;
public class MediaRepository {
 public static String digest(byte[] b){try{StringBuilder s=new StringBuilder();for(byte v:java.security.MessageDigest.getInstance("SHA-256").digest(b))s.append(String.format("%02x",v));return s.toString();}catch(Exception e){throw new RuntimeException(e);}}
}
'''
SESSION_TEST = r'''
package com.supercubegame.pockettodo;
import java.nio.file.*;
import java.util.*;
public class SessionContract {
 interface Action {void run()throws Exception;}
 static int checks;
 static void ok(boolean b,String name){if(!b)throw new AssertionError(name);checks++;System.out.println("SESSION_PASS "+name);}
 static void reject(Action a,String name)throws Exception{
  boolean failed=false;try{a.run();}catch(IllegalStateException|java.io.IOException e){failed=true;}ok(failed,name);
 }
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]); NoteDraftStore store=new NoteDraftStore(root);
  AppDatabase db=new AppDatabase();
  NoteEditorScreen.TextDraftSession s=new NoteEditorScreen.TextDraftSession(db,store,1,"note","block",db.noteBlocks("note"));
  ok(s.initial.equals("original"),"initial");
  byte[] before=db.exportState();
  s.saveDraft("  草稿😀\nline\n");
  ok(Arrays.equals(before,db.exportState()),"draft_db_readonly");
  ok(s.recover().equals("  草稿😀\nline\n"),"recover_exact");
  ok(Arrays.equals(before,db.exportState()),"recover_db_readonly");
  s.close();
  reject(()->s.saveDraft("closed"),"closed_refused");
  NoteEditorScreen.TextDraftSession reopened=new NoteEditorScreen.TextDraftSession(db,store,1,"note","block",db.noteBlocks("note"));
  ok(reopened.recover().equals("  草稿😀\nline\n"),"new_session_recovery");
  reopened.discard();
  ok(reopened.record.text==null&&Arrays.equals(before,db.exportState()),"discard_db_readonly");
  reopened.saveDraft("");
  ok(reopened.recover().equals(""),"empty_draft");
  reject(()->reopened.commit(" "),"blank_commit");
  reopened.saveDraft("saved");
  ok(reopened.commit("saved"),"commit_cleanup");
  ok(db.blocks.get(0).text.equals("saved")&&db.revision==1&&db.writes==1,"commit_once");
  ok(store.read(new NoteDraftStore.Slot(1,"note","block")).text==null,"committed_draft_cleared");
  reject(()->reopened.commit("twice"),"commit_terminal");
  NoteEditorScreen.TextDraftSession stale=new NoteEditorScreen.TextDraftSession(db,store,1,"note","block",db.noteBlocks("note"));
  stale.saveDraft("keep");
  db.external("newer");
  byte[] changed=db.exportState();
  reject(()->stale.commit("overwrite"),"canonical_stale_commit");
  reject(stale::recover,"canonical_stale_recovery");
  reject(()->stale.saveDraft("overwrite draft"),"canonical_stale_draft");
  ok(Arrays.equals(changed,db.exportState()),"stale_db_preserved");
  NoteEditorScreen.TextDraftSession afterChange=new NoteEditorScreen.TextDraftSession(db,store,1,"note","block",db.noteBlocks("note"));
  reject(afterChange::recover,"stored_base_stale");
  ok(store.read(new NoteDraftStore.Slot(1,"note","block")).text.equals("keep"),"stale_draft_retained");
  afterChange.discard();
  afterChange.saveDraft("before race");
  NoteEditorScreen.TextDraftSession raceA=new NoteEditorScreen.TextDraftSession(db,store,1,"note","block",db.noteBlocks("note"));
  NoteEditorScreen.TextDraftSession raceB=new NoteEditorScreen.TextDraftSession(db,store,1,"note","block",db.noteBlocks("note"));
  raceA.saveDraft("winner");
  reject(()->raceB.saveDraft("loser"),"draft_cas_save");
  reject(raceB::discard,"draft_cas_discard");
  reject(raceB::recover,"draft_cas_recover");
  ok(store.read(new NoteDraftStore.Slot(1,"note","block")).text.equals("winner"),"newer_draft_retained");
  raceA.recover();
  db.failSave=true; byte[] preFailure=db.exportState();
  reject(()->raceA.commit("failure"),"late_failure");
  ok(Arrays.equals(preFailure,db.exportState()),"late_failure_model_rollback");
  ok(store.read(new NoteDraftStore.Slot(1,"note","block")).text.equals("winner"),"late_failure_keeps_draft");
  db.failSave=false;
  // A cooperating writer can publish after the draft read, before DB commit ends.
  db.afterCommit=()->{try{NoteDraftStore.Record r=store.read(new NoteDraftStore.Slot(1,"note","block"));
    store.save(new NoteDraftStore.Slot(1,"note","block"),r.token,r.base,"concurrent");}catch(Exception e){throw new RuntimeException(e);}};
  ok(!raceA.commit("accepted"),"cleanup_conflict_reported");
  ok(db.blocks.get(0).text.equals("accepted"),"cleanup_failure_not_db_failure");
  ok(store.read(new NoteDraftStore.Slot(1,"note","block")).text.equals("concurrent"),"cleanup_keeps_newer_draft");
  List<NoteDocument.Block> shown=db.noteBlocks("note");db.external("moved");
  reject(()->new NoteEditorScreen.TextDraftSession(db,store,1,"note","block",shown),"stale_shown_blocks");
  reject(()->new NoteEditorScreen.TextDraftSession(db,store,2,"note","block",db.noteBlocks("note")),"wrong_owner");
  reject(()->new NoteEditorScreen.TextDraftSession(db,store,1,"missing","block",db.noteBlocks("note")),"missing_note");
  reject(()->new NoteEditorScreen.TextDraftSession(db,store,1,"note","missing",db.noteBlocks("note")),"missing_block");
  db.sql.outer=true;
  reject(()->new NoteEditorScreen.TextDraftSession(db,store,1,"note","block",db.noteBlocks("note")),"outer_transaction");
  db.sql.outer=false;
  NoteEditorScreen.TextDraftSession adding=new NoteEditorScreen.TextDraftSession(db,store,1,"note",null,db.noteBlocks("note"));
  adding.saveDraft("new block");
  ok(adding.commit("new block"),"new_block_commit");
  ok(db.blocks.size()==2&&db.blocks.get(0).text.equals("moved")&&db.blocks.get(1).text.equals("new block"),"append_preserves_existing");
  ok(db.guardInside&&db.saveInside,"comparison_and_save_model_transaction");
  System.out.println("SESSION_RESULT "+checks+" PASS");
 }
}
'''

# This gate compiles the actual nested Java session, but substitutes Android/DB
# collaborators. Its rollback result is a model check, NOT Android SQLite proof.
SESSION_LABELS = """initial draft_db_readonly recover_exact recover_db_readonly
closed_refused new_session_recovery discard_db_readonly empty_draft blank_commit
commit_cleanup commit_once committed_draft_cleared commit_terminal canonical_stale_commit
canonical_stale_recovery canonical_stale_draft stale_db_preserved stored_base_stale
stale_draft_retained draft_cas_save draft_cas_discard draft_cas_recover newer_draft_retained
late_failure late_failure_model_rollback late_failure_keeps_draft cleanup_conflict_reported
cleanup_failure_not_db_failure cleanup_keeps_newer_draft stale_shown_blocks wrong_owner
missing_note missing_block outer_transaction new_block_commit append_preserves_existing
comparison_and_save_model_transaction""".split()

SESSION_EXTRACT = r'''
import java.nio.file.*;
import java.util.*;
import javax.tools.*;
import com.sun.source.tree.*;
import com.sun.source.util.*;
class ExtractSession {
 public static void main(String[] args)throws Exception{
  String source=Files.readString(Path.of(args[0]));
  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();
  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();
  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){
   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,Arrays.asList("-proc:none"),null,
    files.getJavaFileObjects(args[0]));
   List<String> matches=new ArrayList<>();
   for(CompilationUnitTree tree:task.parse()){
    SourcePositions pos=Trees.instance(task).getSourcePositions();
    new TreeScanner<Void,Void>(){
     public Void visitClass(ClassTree node,Void unused){
      if(node.getSimpleName().contentEquals("TextDraftSession")){
       int start=(int)pos.getStartPosition(tree,node),end=(int)pos.getEndPosition(tree,node);
       if(start<0||end<=start)throw new AssertionError("Incomplete session syntax");
       matches.add(source.substring(start,end));
      }return super.visitClass(node,unused);
     }
    }.scan(tree,null);
   }
   for(Diagnostic<?> d:errors.getDiagnostics())if(d.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(d.toString());
   if(matches.size()!=1)throw new AssertionError("Exactly one actual TextDraftSession required; found "+matches.size());
   System.out.print(matches.get(0));
  }
 }
}
'''

def session_selftest():
    java = shutil.which("java") or str(Path(os.environ["JAVA_HOME"])/"bin/java")
    source = ROOT/"src/main/java/com/supercubegame/pockettodo/NoteEditorScreen.java"
    if not source.is_file():
        raise RuntimeError("Editor source missing; no draft session integration verified")
    with tempfile.TemporaryDirectory(prefix="draft-session-contract-") as tmp:
        folder = Path(tmp)
        extractor = folder/"ExtractSession.java"; extractor.write_text(SESSION_EXTRACT)
        parsed = subprocess.run([java, str(extractor), str(source)], text=True,
                                capture_output=True, timeout=30)
        if parsed.returncode:
            raise RuntimeError("Draft session not implemented or invalid:\n"+parsed.stderr[-6000:])
        actual = parsed.stdout
        assert actual.strip() and "TextDraftSession" in actual
        boot = folder/"CompileDrafts.java"; boot.write_text(BOOT)
        for part in SESSION_STUBS.split("@@ ")[1:]:
            name, text = part.split("\n", 1)
            target = folder/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(text)
        package = folder/"com/supercubegame/pockettodo"
        product = package/"NoteEditorScreen.java"
        prefix = "package com.supercubegame.pockettodo;import java.util.*;import java.io.*;import android.database.Cursor;\npublic class NoteEditorScreen {\n"
        product.write_text(prefix+actual+"\n}\n")
        (package/"NoteDraftStore.java").write_bytes((ROOT/PRODUCT).read_bytes())
        (package/"SessionContract.java").write_text(SESSION_TEST)
        classes = folder/"classes"; classes.mkdir()
        sources = [p for p in folder.rglob("*.java") if p not in (boot, extractor)]
        command([java, boot, "--release", "8", "-encoding", "UTF-8", "-d", classes, *sources])
        def execute(cp, data):
            return subprocess.run([java, "-cp", str(cp), "com.supercubegame.pockettodo.SessionContract", str(data)],
                                  text=True, capture_output=True, timeout=60)
        run = execute(classes, folder/"positive")
        labels = [line.removeprefix("SESSION_PASS ") for line in run.stdout.splitlines()
                  if line.startswith("SESSION_PASS ")]
        assert run.returncode == 0 and labels == SESSION_LABELS, (run.stdout, run.stderr)
        assert run.stdout.splitlines()[-1] == "SESSION_RESULT 37 PASS"
        mutations = (
            ("if(!base.equals(MediaRepository.digest(app.exportState())))", "if(false)", "canonical_stale_commit"),
            ("if(!record.token.equals(store.read(slot).token))", "if(false)", "draft_cas_recover"),
            ("if(!sameBlocks(blocks,shown))", "if(false)", "stale_shown_blocks"),
            ("if(!c.moveToFirst()||c.getLong(0)!=owner)", "if(!c.moveToFirst())", "wrong_owner"),
        )
        for index, (before, after, expected) in enumerate(mutations):
            assert actual.count(before) == 1, "Session mutation anchor changed"
            product.write_text(prefix+actual.replace(before, after, 1)+"\n}\n")
            mutant = folder/("mutant-"+str(index)); mutant.mkdir()
            # Require compilation success; syntax errors never count as caught faults.
            command([java, boot, "--release", "8", "-encoding", "UTF-8", "-cp", classes, "-d", mutant, product])
            result = execute(os.pathsep.join((str(mutant), str(classes))), folder/("negative-"+str(index)))
            assert result.returncode != 0 and "AssertionError: "+expected in result.stderr, (
                "Session mutant survived or wrong failure", expected, result.stdout, result.stderr)
        result = {"status": "PASS", "checks": len(labels), "labels": labels,
                  "compiled_session_mutants": len(mutations),
                  "scope": "ACTUAL_JAVA_SESSION_WITH_MODELED_DB_NOT_ANDROID_SQLITE_UI_OR_RESTART",
                  "release_ready": False}
        print("NOTE_DRAFT_SESSION_HOST "+json.dumps(result), flush=True)
        return result

UI_MODEL = r'''
import java.util.*;
import java.util.concurrent.Callable;
import java.util.function.Consumer;
public class DraftUiContract {
 static final class View {
  boolean enabled=true; String desc=""; Consumer<View> click;
  void setContentDescription(String x){desc=x;}
  void setEnabled(boolean x){enabled=x;}
  void setOnClickListener(Consumer<View> x){click=x;}
  void press(){if(enabled&&click!=null)click.accept(this);}
 }
 static class TextView {
  boolean enabled=true; String desc="",text=""; int color;
  void setContentDescription(String x){desc=x;}
  void setEnabled(boolean x){enabled=x;}
  void setText(String x){text=x;}
  String getText(){return text;}
  void setTextColor(int x){color=x;}
 }
 static final class EditText extends TextView {}
 static final class Button extends TextView {
  Consumer<Button> click; void setOnClickListener(Consumer<Button> x){click=x;}
  void press(){if(enabled&&click!=null)click.accept(this);}
 }
 static final class LinearLayout {
  final List<Object> children=new ArrayList<>();
  void setPadding(int a,int b,int c,int d){}
  void addView(Object x){children.add(x);}
  void addView(Object x,int at){children.add(at,x);}
  void addView(Object x,LayoutParams p){children.add(x);}
  static final class LayoutParams{LayoutParams(int w,int h){}}
 }
 static final class ScrollView {
  Object child; ScrollView(Object activity){}
  void addView(Object x){child=x;}
 }
 static final class Window {
  int softInputMode;
  void setSoftInputMode(int x){softInputMode=x;}
 }
 static final class AlertDialog {
  static final int BUTTON_POSITIVE=-1,BUTTON_NEGATIVE=-2;
  static AlertDialog last;
  final Button positive=new Button(),negative=new Button();
  final Window window=new Window();
  Object view; String title,message; boolean showing,cancelable=true;
  Consumer<AlertDialog> shown,dismissed;
  interface Confirm{void accept(AlertDialog d,int which);}
  Button getButton(int which){return which==BUTTON_POSITIVE?positive:negative;}
  Window getWindow(){return window;}
  void setCancelable(boolean x){cancelable=x;}
  boolean isShowing(){return showing;}
  void setOnShowListener(Consumer<AlertDialog> x){shown=x;}
  void setOnDismissListener(Consumer<AlertDialog> x){dismissed=x;}
  void show(){showing=true;last=this;if(shown!=null)shown.accept(this);}
  void dismiss(){if(showing){showing=false;if(dismissed!=null)dismissed.accept(this);}}
  void back(){if(cancelable)dismiss();}
  static final class Builder {
   final AlertDialog d=new AlertDialog(); Builder(Object activity){}
   Builder setTitle(String x){d.title=x;return this;}
   Builder setMessage(String x){d.message=x;return this;}
   Builder setView(Object x){d.view=x;return this;}
   Builder setNegativeButton(String text,Confirm c){
    d.negative.text=text;d.negative.click=v->{if(c!=null)c.accept(d,BUTTON_NEGATIVE);d.dismiss();};return this;
   }
   Builder setPositiveButton(String text,Confirm c){
    d.positive.text=text;d.positive.click=v->{if(c!=null)c.accept(d,BUTTON_POSITIVE);d.dismiss();};return this;
   }
   AlertDialog create(){return d;}
   AlertDialog show(){d.show();return d;}
  }
 }
 static final class TodayScreen {
  static final int MUTED=1,ERROR=2;
  final Object activity=new Object();
  boolean defer,fail; Runnable pending; String notice; int loads;
  LinearLayout column(){return new LinearLayout();}
  int dp(int x){return x;}
  EditText field(String name,boolean multiline){EditText f=new EditText();f.desc=name;return f;}
  TextView text(String text,int size,int color){TextView t=new TextView();t.text=text;t.color=color;return t;}
  Button button(String text,Runnable r){Button b=new Button();b.text=text;b.click=v->r.run();return b;}
  void message(String text,boolean error){notice=text;}
  <T> void work(Callable<T> action,Consumer<T> success,Runnable failure){
   if(pending!=null)throw new AssertionError("overlapping host work");
   pending=()->{T value;try{if(fail)throw new Exception("injected");value=action.call();}
    catch(Exception e){failure.run();return;}success.accept(value);};
   if(!defer)complete();
  }
  void complete(){Runnable r=pending;pending=null;if(r==null)throw new AssertionError("missing work");r.run();}
 }
 static final class TextDraftSession {
  String initial="body",block="block"; final Record record=new Record();
  int saves,recovers,discards,commits,closes; String committed; boolean clean=true;
  static final class Record{String text;}
  void saveDraft(String s){saves++;record.text=s;}
  String recover(){recovers++;return record.text;}
  void discard(){discards++;record.text=null;}
  boolean commit(String s){commits++;committed=s;return clean;}
  void close(){closes++;}
 }
 final TodayScreen host=new TodayScreen();
 void load(){host.loads++;}
 // ACTUAL_METHOD
 static int count;
 static void ok(boolean x,String label){if(!x)throw new AssertionError(label);count++;System.out.println("DRAFT_UI_PASS "+label);}
 static final class Fixture {
  final DraftUiContract app=new DraftUiContract();
  final TextDraftSession s=new TextDraftSession();
  final AlertDialog d; final LinearLayout body; final EditText input;
  final TextView status; final Button save,recover,discard;
  Fixture(String draft){
   s.record.text=draft;app.showTextDraft(s);d=AlertDialog.last;
   body=(LinearLayout)((ScrollView)d.view).child;
   input=(EditText)find("文字内容");status=(TextView)find("note-draft-status");
   save=(Button)find("note-draft-save");recover=(Button)find("note-draft-recover");discard=(Button)find("note-draft-discard");
  }
  Object find(String desc){
   Object found=null;for(Object x:body.children)if(x instanceof TextView&&((TextView)x).desc.equals(desc)){
    if(found!=null)throw new AssertionError("ambiguous control "+desc);found=x;
   }if(found==null)throw new AssertionError("missing control "+desc);return found;
  }
  boolean untouched(){return s.saves==0&&s.recovers==0&&s.discards==0&&s.commits==0;}
 }
 public static void main(String[] args){
  Fixture f=new Fixture(null);
  ok(f.body.children.get(0)==f.status&&f.body.children.get(1)==f.input,"feedback_before_input");
  ok(f.d.window.softInputMode==16,"resize_window");
  ok(f.input.text.equals("body")&&f.untouched(),"canonical_initial_no_autorestore");
  ok(f.save.enabled&&!f.recover.enabled&&!f.discard.enabled,"absent_draft_controls");
  f.input.setText("cancel input");f.d.negative.press();
  ok(!f.d.showing&&f.s.closes==1&&f.untouched(),"cancel_no_draft_mutation");
  f=new Fixture("  草稿\n😀  ");
  ok(f.recover.enabled&&f.discard.enabled&&f.input.text.equals("body")&&f.untouched(),"present_draft_explicit");
  f.input.setText(" \n\t ");f.d.positive.press();
  ok(f.d.showing&&f.status.text.equals("内容不能为空")&&f.status.color==TodayScreen.ERROR&&f.untouched(),"blank_body_stays_open");
  String exact=" \n草稿😀\t ";f.input.setText(exact);f.save.press();
  ok(f.s.saves==1&&exact.equals(f.s.record.text)&&f.s.commits==0,"save_exact_draft");
  ok(f.input.enabled&&f.save.enabled&&f.recover.enabled&&f.discard.enabled&&f.d.cancelable,"save_unlocks");
  f.input.setText("unsaved");f.recover.press();AlertDialog confirm=AlertDialog.last;
  ok(confirm!=f.d&&confirm.showing&&f.s.recovers==0,"recover_requires_confirmation");
  confirm.negative.press();
  ok(f.s.recovers==0&&f.input.text.equals("unsaved")&&f.d.showing,"recover_cancel_keeps_input");
  f.recover.press();AlertDialog.last.positive.press();
  ok(f.s.recovers==1&&f.input.text.equals(exact)&&f.s.commits==0,"recover_exact_no_body_commit");
  f.discard.press();confirm=AlertDialog.last;
  ok(confirm!=f.d&&confirm.showing&&f.s.discards==0,"discard_requires_confirmation");
  confirm.negative.press();
  ok(f.s.discards==0&&f.s.record.text.equals(exact),"discard_cancel_keeps_draft");
  f.discard.press();AlertDialog.last.positive.press();
  ok(f.s.discards==1&&f.s.record.text==null&&f.input.text.equals(exact)&&f.s.commits==0,"discard_keeps_input_body");
  ok(!f.recover.enabled&&!f.discard.enabled&&f.save.enabled,"discard_updates_controls");
  f=new Fixture("");
  ok(f.recover.enabled&&f.discard.enabled,"empty_draft_is_present");
  f.recover.press();AlertDialog.last.positive.press();
  ok(f.input.text.equals("")&&f.s.recovers==1,"empty_draft_recovery");
  f=new Fixture(null);f.app.host.defer=true;f.input.setText(exact);f.save.press();
  ok(!f.save.enabled&&!f.recover.enabled&&!f.discard.enabled&&!f.input.enabled&&!f.d.positive.enabled&&!f.d.negative.enabled&&!f.d.cancelable,"busy_disables_all");
  f.d.back();f.d.negative.press();f.save.press();
  ok(f.d.showing&&f.s.closes==0&&f.s.saves==0,"busy_blocks_cancel_duplicate");
  f.app.host.complete();
  ok(f.s.saves==1&&f.d.negative.enabled&&f.d.positive.enabled&&f.d.cancelable,"deferred_save_completes_once");
  f=new Fixture("old");f.app.host.fail=true;f.input.setText(exact);f.save.press();
  ok(f.input.text.equals(exact)&&f.s.record.text.equals("old")&&f.untouched()&&f.d.showing,"failure_preserves_input_draft");
  ok(f.status.color==TodayScreen.ERROR&&f.save.enabled&&f.input.enabled&&f.d.cancelable,"failure_feedback_unlocks");
  f=new Fixture(null);f.input.setText("body change");f.d.positive.press();
  ok(f.s.commits==1&&f.s.committed.equals("body change")&&!f.d.showing&&f.s.closes==1&&f.app.host.loads==1,"body_commit_closes_reload");
  f=new Fixture("draft");f.s.clean=false;f.input.setText("body change");f.d.positive.press();
  ok(f.s.commits==1&&!f.d.showing&&f.app.host.loads==1&&f.app.host.notice.contains("正文已保存")&&f.app.host.notice.contains("请勿重复保存"),"cleanup_failure_not_body_failure");
  f=new Fixture("keep");f.d.back();
  ok(!f.d.showing&&f.s.closes==1&&f.untouched()&&f.s.record.text.equals("keep"),"back_closes_without_clear");
  System.out.println("DRAFT_UI_RESULT "+count+" PASS");
 }
}
'''

UI_LABELS = """feedback_before_input resize_window canonical_initial_no_autorestore
absent_draft_controls cancel_no_draft_mutation present_draft_explicit blank_body_stays_open
save_exact_draft save_unlocks recover_requires_confirmation recover_cancel_keeps_input
recover_exact_no_body_commit discard_requires_confirmation discard_cancel_keeps_draft
discard_keeps_input_body discard_updates_controls empty_draft_is_present empty_draft_recovery
busy_disables_all busy_blocks_cancel_duplicate deferred_save_completes_once
failure_preserves_input_draft failure_feedback_unlocks body_commit_closes_reload
cleanup_failure_not_body_failure back_closes_without_clear""".split()

def ui_model_selftest():
    """Actual Java UI method, modeled widgets/session. NOT Android geometry or SQLite."""
    java = shutil.which("java") or str(Path(os.environ["JAVA_HOME"])/"bin/java")
    source = ROOT/"src/main/java/com/supercubegame/pockettodo/NoteEditorScreen.java"
    # Reuse the compiler parser, never regex-match method braces or comments.
    extractor_source = SESSION_EXTRACT.replace("ExtractSession", "ExtractDraftUi").replace(
        "visitClass(ClassTree node", "visitMethod(MethodTree node").replace(
        'node.getSimpleName().contentEquals("TextDraftSession")',
        'node.getName().contentEquals("showTextDraft")').replace(
        "super.visitClass(node,unused)", "super.visitMethod(node,unused)")
    with tempfile.TemporaryDirectory(prefix="draft-ui-contract-") as tmp:
        folder = Path(tmp)
        extractor = folder/"ExtractDraftUi.java"; extractor.write_text(extractor_source)
        parsed = subprocess.run([java, str(extractor), str(source)], text=True,
                                capture_output=True, timeout=30)
        if parsed.returncode:
            raise RuntimeError("Draft UI extraction failed:\n"+parsed.stderr[-6000:])
        actual = parsed.stdout
        assert actual.strip().startswith("private void showTextDraft(")
        boot = folder/"CompileDrafts.java"; boot.write_text(BOOT)
        window = folder/"android/view/WindowManager.java"; window.parent.mkdir(parents=True)
        window.write_text("package android.view; public interface WindowManager {"
                          "public static class LayoutParams {public static final int SOFT_INPUT_ADJUST_RESIZE=16;}}")
        product = folder/"DraftUiContract.java"
        def build(method, name):
            product.write_text(UI_MODEL.replace("// ACTUAL_METHOD", method))
            classes = folder/name; classes.mkdir()
            command([java, boot, "--release", "8", "-encoding", "UTF-8", "-d", classes, window, product])
            return subprocess.run([java, "-cp", str(classes), "DraftUiContract"], text=True,
                                  capture_output=True, timeout=30)
        run = build(actual, "positive")
        labels = [line.removeprefix("DRAFT_UI_PASS ") for line in run.stdout.splitlines()
                  if line.startswith("DRAFT_UI_PASS ")]
        assert run.returncode == 0 and labels == UI_LABELS, (run.stdout, run.stderr)
        assert run.stdout.splitlines()[-1] == "DRAFT_UI_RESULT 26 PASS"
        mutations = (
            ("body.addView(validation,0);", "body.addView(validation);", "feedback_before_input"),
            ("android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE", "0", "resize_window"),
            ("if(value.trim().isEmpty())", "if(false)", "blank_body_stays_open"),
            ("String exact=field.getText().toString();", "String exact=field.getText().toString().trim();", "save_exact_draft"),
            ("unused->session.close()", "unused->{}", "cancel_no_draft_mutation"),
        )
        for index, (before, after, expected) in enumerate(mutations):
            assert actual.count(before) == 1, "Draft UI mutation anchor changed"
            result = build(actual.replace(before, after, 1), "negative-"+str(index))
            assert result.returncode != 0 and "AssertionError: "+expected in result.stderr, (
                "UI mutant survived or wrong failure", expected, result.stdout, result.stderr)
        result = {"status": "PASS", "checks": len(labels), "labels": labels,
                  "compiled_ui_mutants": len(mutations),
                  "scope": "ACTUAL_JAVA_UI_METHOD_MODELED_WIDGETS_SESSION_NOT_ANDROID_GEOMETRY_OR_DB",
                  "release_ready": False}
        print("NOTE_DRAFT_UI_MODEL "+json.dumps(result), flush=True)
        return result


DEVICE_SCOPE = "ACTUAL_ANDROID_DRAFT_SESSION_SQLITE_FILES_FORCE_STOP_NOT_NATIVE_BUTTONS_OR_LMK"
DEVICE_LABELS = {
    "seed": """initial_body exact_draft_save draft_all_tables_readonly explicit_recover
recover_all_tables_readonly cancel_keeps_draft empty_draft_exact empty_draft_readonly
discard_tombstone discard_readonly same_title_note_isolation owner_slot_isolation
new_text_slot_isolation media_unchanged restart_fixture_saved""".split(),
    "reopen": """restart_exact_draft restart_full_state restart_media
wrong_owner missing_note missing_block stale_shown_blocks
same_revision_mutation stale_recover stale_commit stale_save stale_refusal_readonly
stale_draft_retained new_session_stale_base cas_save cas_recover cas_discard
cas_newer_draft_retained late_sql_failure late_sql_rollback late_sql_draft_retained
commit_cleanup commit_exact_body commit_one_revision commit_preserves_siblings
commit_terminal new_block_append new_block_preserves_existing final_media""".split(),
}

# Test-only instrumentation. Reflection crosses the instrumentation class loader
# boundary; the session and store come from the installed product, not a clone.
DEVICE_JAVA = r'''
package ci.drafts;
import android.app.Instrumentation;
import android.os.Bundle;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import com.supercubegame.pockettodo.AppDatabase;
import com.supercubegame.pockettodo.NoteDocument;
import com.supercubegame.pockettodo.NoteDraftStore;
import java.io.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;

public final class DraftInstrumentation extends Instrumentation {
 private Bundle args; private int count; private Path folder,asset; private String name;
 private static final String EXACT="  草稿😀\nline\t\n";
 private static final byte[] MEDIA={0,1,2,3,4,5,6,7};
 interface Action {void run()throws Exception;}
 static void need(boolean b,String label){if(!b)throw new AssertionError(label);}
 void pass(boolean b,String label){need(b,label);count++;System.out.println("DRAFT_DEVICE_PASS "+label);}
 void reject(Class<? extends Throwable> type,Action action,String label)throws Exception{
  Throwable caught=null;try{action.run();}catch(Throwable e){caught=e;}
  pass(caught!=null&&type.isInstance(caught),label);
 }
 static Object invoke(Object target,String method,Class<?>[] types,Object...args)throws Exception{
  Method m=target.getClass().getDeclaredMethod(method,types);m.setAccessible(true);
  try{return m.invoke(target,args);}catch(InvocationTargetException e){
   Throwable c=e.getCause();if(c instanceof Exception)throw (Exception)c;
   if(c instanceof Error)throw (Error)c;throw new AssertionError(c);
  }
 }
 Object session(AppDatabase h,NoteDraftStore s,long owner,String note,String block,List<NoteDocument.Block> shown)throws Exception{
  Class<?> c=Class.forName("com.supercubegame.pockettodo.NoteEditorScreen$TextDraftSession",true,getTargetContext().getClassLoader());
  Constructor<?> ctor=c.getDeclaredConstructor(AppDatabase.class,NoteDraftStore.class,long.class,String.class,String.class,List.class);
  ctor.setAccessible(true);
  try{return ctor.newInstance(h,s,owner,note,block,shown);}
  catch(InvocationTargetException e){Throwable t=e.getCause();if(t instanceof Exception)throw (Exception)t;throw new AssertionError(t);}
 }
 Object session(AppDatabase h,NoteDraftStore s)throws Exception{return session(h,s,1,"first","text",h.noteBlocks("first"));}
 void save(Object s,String text)throws Exception{invoke(s,"saveDraft",new Class<?>[]{String.class},text);}
 String recover(Object s)throws Exception{return (String)invoke(s,"recover",new Class<?>[]{});}
 void close(Object s)throws Exception{invoke(s,"close",new Class<?>[]{});}
 void discard(Object s)throws Exception{invoke(s,"discard",new Class<?>[]{});}
 boolean commit(Object s,String text)throws Exception{return (Boolean)invoke(s,"commit",new Class<?>[]{String.class},text);}
 static String state(AppDatabase h){
  SQLiteDatabase db=h.getReadableDatabase();StringBuilder out=new StringBuilder();
  try(Cursor tables=db.rawQuery("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",null)){
   while(tables.moveToNext()){
    String table=tables.getString(0);need(table.matches("[A-Za-z0-9_]+"),"table name");out.append(table).append('\n');
    try(Cursor c=db.rawQuery("SELECT rowid AS rowid,* FROM \""+table+"\" ORDER BY rowid",null)){
     out.append(Arrays.toString(c.getColumnNames())).append('\n');
     while(c.moveToNext()){for(int i=0;i<c.getColumnCount();i++){
      int type=c.getType(i);String v=type==0?"":type==4?android.util.Base64.encodeToString(c.getBlob(i),2):c.getString(i);
      out.append(type).append(':').append(v.length()).append(':').append(v).append(';');
     }out.append('\n');}
    }
   }
  }return out.toString();
 }
 static long revision(AppDatabase h){
  try(Cursor c=h.getReadableDatabase().rawQuery("SELECT value FROM revision",null)){
   need(c.moveToFirst(),"revision exists");long v=c.getLong(0);need(!c.moveToNext(),"single revision");return v;
  }
 }
 void media(String label)throws Exception{pass(Arrays.equals(MEDIA,Files.readAllBytes(asset)),label);}
 NoteDraftStore.Slot slot(){return new NoteDraftStore.Slot(1,"first","text");}
 void seed()throws Exception{
  need(!getTargetContext().getDatabasePath(name).exists()&&!Files.exists(folder),"fresh synthetic fixture required");
  Files.createDirectory(folder);Files.write(asset,MEDIA,StandardOpenOption.CREATE_NEW);
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name)){
   h.addCategory(1,"Draft test");h.addActivity(1,1,0,"First");h.addActivity(2,1,0,"Other");
   h.createNote("first",1,"Same");h.createNote("second",1,"Same");h.createNote("other",2,"Same");
   h.saveNote("first",Arrays.asList(NoteDocument.Block.text("text","Original",true),NoteDocument.Block.text("sibling","Keep",false)));
   h.saveNote("second",Collections.singletonList(NoteDocument.Block.text("text","Second",false)));
   h.saveNote("other",Collections.singletonList(NoteDocument.Block.text("text","Other",false)));
   NoteDraftStore store=new NoteDraftStore(folder.resolve("drafts"));
   Object s=session(h,store);String before=state(h);
   pass(h.noteBlocks("first").get(0).text.equals("Original"),"initial_body");
   save(s,EXACT);pass(store.read(slot()).text.equals(EXACT),"exact_draft_save");
   pass(state(h).equals(before),"draft_all_tables_readonly");
   pass(recover(s).equals(EXACT),"explicit_recover");pass(state(h).equals(before),"recover_all_tables_readonly");
   String token=store.read(slot()).token;close(s);
   pass(store.read(slot()).token.equals(token)&&store.read(slot()).text.equals(EXACT),"cancel_keeps_draft");
   s=session(h,store);save(s,"");pass(recover(s).equals(""),"empty_draft_exact");
   pass(state(h).equals(before),"empty_draft_readonly");discard(s);
   pass(store.read(slot()).text==null&&!store.read(slot()).token.equals(token),"discard_tombstone");
   pass(state(h).equals(before),"discard_readonly");save(s,EXACT);
   String base=store.read(slot()).base;
   NoteDraftStore.Slot same=new NoteDraftStore.Slot(1,"second","text");
   store.save(same,"",base,"second draft");
   pass(store.read(same).text.equals("second draft")&&store.read(slot()).text.equals(EXACT),"same_title_note_isolation");
   NoteDraftStore.Slot other=new NoteDraftStore.Slot(2,"other","text");
   store.save(other,"",base,"other draft");
   pass(store.read(other).text.equals("other draft")&&store.read(slot()).text.equals(EXACT),"owner_slot_isolation");
   Object empty=session(h,store,1,"first",null,h.noteBlocks("first"));save(empty,"new draft");
   pass(store.read(new NoteDraftStore.Slot(1,"first",null)).text.equals("new draft")&&store.read(slot()).text.equals(EXACT),"new_text_slot_isolation");
   close(empty);close(s);media("media_unchanged");
   Files.write(folder.resolve("state.txt"),before.getBytes("UTF-8"),StandardOpenOption.CREATE_NEW);
   Files.write(folder.resolve("draft-token.txt"),store.read(slot()).token.getBytes("UTF-8"),StandardOpenOption.CREATE_NEW);
   pass(state(h).equals(before),"restart_fixture_saved");
  }
 }
 void reopen()throws Exception{
  need(getTargetContext().getDatabasePath(name).isFile()&&Files.isDirectory(folder),"persisted fixture required");
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name)){
   NoteDraftStore store=new NoteDraftStore(folder.resolve("drafts"));Object s=session(h,store);
   pass(recover(s).equals(EXACT)&&store.read(slot()).token.equals(new String(Files.readAllBytes(folder.resolve("draft-token.txt")),"UTF-8")),"restart_exact_draft");
   pass(state(h).equals(new String(Files.readAllBytes(folder.resolve("state.txt")),"UTF-8")),"restart_full_state");
   media("restart_media");
   reject(IllegalStateException.class,()->session(h,store,2,"first","text",h.noteBlocks("first")),"wrong_owner");
   reject(IllegalStateException.class,()->session(h,store,1,"missing","text",h.noteBlocks("first")),"missing_note");
   reject(IllegalStateException.class,()->session(h,store,1,"first","missing",h.noteBlocks("first")),"missing_block");
   reject(IllegalStateException.class,()->session(h,store,1,"first","text",Collections.emptyList()),"stale_shown_blocks");
   SQLiteDatabase db=h.getWritableDatabase();long rev=revision(h);
   db.execSQL("UPDATE notes SET title='External' WHERE id='first'");
   pass(revision(h)==rev&&h.noteBlocks("first").get(0).text.equals("Original"),"same_revision_mutation");
   String changed=state(h);
   reject(IllegalStateException.class,()->recover(s),"stale_recover");
   reject(IllegalStateException.class,()->commit(s,"Overwrite"),"stale_commit");
   reject(IllegalStateException.class,()->save(s,"Overwrite"),"stale_save");
   pass(state(h).equals(changed),"stale_refusal_readonly");
   pass(store.read(slot()).text.equals(EXACT),"stale_draft_retained");
   Object fresh=session(h,store);
   reject(IllegalStateException.class,()->recover(fresh),"new_session_stale_base");
   discard(fresh);save(fresh,"before race");
   Object race=session(h,store);save(fresh,"winner");
   reject(IllegalStateException.class,()->save(race,"loser"),"cas_save");
   reject(IOException.class,()->recover(race),"cas_recover");
   reject(IllegalStateException.class,()->discard(race),"cas_discard");
   pass(store.read(slot()).text.equals("winner")&&state(h).equals(changed),"cas_newer_draft_retained");
   close(race);close(fresh);close(s);
   Object late=session(h,store);save(late,"commit body");
   String before=state(h),token=store.read(slot()).token;
   db.execSQL("CREATE TRIGGER ci_draft_late BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'draft_late_sql_fault'); END");
   Throwable failure=null;try{commit(late,"commit body");}catch(Throwable t){failure=t;}
   pass(failure instanceof android.database.sqlite.SQLiteException&&failure.getMessage().contains("draft_late_sql_fault"),"late_sql_failure");
   pass(state(h).equals(before),"late_sql_rollback");
   pass(store.read(slot()).token.equals(token)&&store.read(slot()).text.equals("commit body"),"late_sql_draft_retained");
   db.execSQL("DROP TRIGGER ci_draft_late");rev=revision(h);
   pass(commit(late,"  commit body  ")&&store.read(slot()).text==null,"commit_cleanup");
   List<NoteDocument.Block> blocks=h.noteBlocks("first");
   pass(blocks.size()==2&&blocks.get(0).id.equals("text")&&blocks.get(0).text.equals("commit body")&&blocks.get(0).privateContent,"commit_exact_body");
   pass(revision(h)==rev+1,"commit_one_revision");
   pass(blocks.get(1).id.equals("sibling")&&blocks.get(1).text.equals("Keep")&&h.noteBlocks("second").get(0).text.equals("Second")&&h.noteBlocks("other").get(0).text.equals("Other"),"commit_preserves_siblings");
   reject(IllegalStateException.class,()->commit(late,"again"),"commit_terminal");
   Object append=session(h,store,1,"first",null,h.noteBlocks("first"));save(append,"appended");
   need(commit(append,"appended"),"append cleanup");
   List<NoteDocument.Block> after=h.noteBlocks("first");
   pass(after.size()==3&&after.get(2).text.equals("appended")&&!after.get(2).id.equals("text")&&!after.get(2).id.equals("sibling"),"new_block_append");
   pass(after.get(0).id.equals("text")&&after.get(0).text.equals("commit body")&&after.get(0).privateContent&&after.get(1).id.equals("sibling")&&after.get(1).text.equals("Keep"),"new_block_preserves_existing");
   media("final_media");
  }
 }
 @Override public void onCreate(Bundle value){super.onCreate(value);args=value;start();}
 @Override public void onStart(){
  ByteArrayOutputStream bytes=new ByteArrayOutputStream();PrintStream oldOut=System.out,oldErr=System.err;int code=0;
  try{
   PrintStream log=new PrintStream(bytes,true,"UTF-8");System.setOut(log);System.setErr(log);
   Context c=getTargetContext();String nonce=args.getString("nonce"),phase=args.getString("phase");
   need(nonce!=null&&nonce.matches("[0-9]+-[0-9]+-(26|34)"),"synthetic nonce");
   need(c.getPackageName().equals(args.getString("expectedPackage"))&&android.os.Process.myUid()==c.getApplicationInfo().uid,"target identity");
   need(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"actual API");
   need(android.os.Build.HARDWARE.equals("ranchu")||android.os.Build.HARDWARE.equals("goldfish"),"CI emulator only");
   System.out.println("DRAFT_DEVICE_TARGET "+c.getPackageName()+" "+android.os.Process.myUid()+" "+android.os.Build.VERSION.SDK_INT+" "+nonce+" "+phase);
   if("diagnostic".equals(phase))throw new AssertionError("draft_device_diagnostic_sentinel");
   folder=new File(c.getCacheDir(),"draft-device-"+nonce).toPath();asset=folder.resolve("synthetic.bin");name="draft-device-"+nonce+".db";
   if("seed".equals(phase)){seed();need(count==15,"seed count");}
   else if("reopen".equals(phase)){reopen();need(count==29,"reopen count");}
   else throw new AssertionError("unknown phase");
   System.out.println("DRAFT_DEVICE_RESULT "+phase+" "+count+" PASS");code=-1;
  }catch(Throwable t){System.err.println("DRAFT_DEVICE_FAILED");t.printStackTrace(System.err);}
  finally{
   System.out.flush();System.err.flush();System.setOut(oldOut);System.setErr(oldErr);Bundle result=new Bundle();
   try{result.putString("stream",bytes.toString("UTF-8"));}catch(Exception t){throw new RuntimeException(t);}
   finish(code,result);
  }
 }
}
'''


def device_observe(text, package, api, nonce, phase):
    """Validate transport finish plus exact ordered coverage, never a substring PASS."""
    import re
    assert type(api) is int and api in (26, 34)
    assert re.fullmatch(r"[0-9]+-[0-9]+-"+str(api), nonce)
    assert phase in DEVICE_LABELS and isinstance(text, str)
    lines = text.replace("\r\n", "\n").splitlines()
    targets = re.findall(r"(?:^|\n)(?:INSTRUMENTATION_RESULT: stream=)?DRAFT_DEVICE_TARGET (\S+) ([0-9]+) ([0-9]+) (\S+) (\S+)(?:\n|$)", text)
    assert len(targets) == 1
    pkg, uid, actual_api, actual_nonce, actual_phase = targets[0]
    assert (pkg, actual_api, actual_nonce, actual_phase) == (package, str(api), nonce, phase)
    assert int(uid) >= 10000
    labels = [line[len("DRAFT_DEVICE_PASS "):] for line in lines if line.startswith("DRAFT_DEVICE_PASS ")]
    assert labels == DEVICE_LABELS[phase]
    results = [line for line in lines if line.startswith("DRAFT_DEVICE_RESULT ")]
    assert results == ["DRAFT_DEVICE_RESULT "+phase+" "+str(len(labels))+" PASS"]
    assert [line for line in lines if line.startswith("INSTRUMENTATION_CODE:")] == ["INSTRUMENTATION_CODE: -1"]
    assert not any(marker in text for marker in ("DRAFT_DEVICE_FAILED", "INSTRUMENTATION_FAILED", "INSTRUMENTATION_ABORTED", "FATAL EXCEPTION", "Process crashed."))
    return labels


def device_observer_selftest():
    import inspect
    total = 0
    for api in (26, 34):
        for phase, labels in DEVICE_LABELS.items():
            nonce = "123-1-"+str(api)
            good = "INSTRUMENTATION_RESULT: stream=DRAFT_DEVICE_TARGET test.package 10123 "+str(api)+" "+nonce+" "+phase+"\n"
            good += "".join("DRAFT_DEVICE_PASS "+label+"\n" for label in labels)
            good += "DRAFT_DEVICE_RESULT "+phase+" "+str(len(labels))+" PASS\nINSTRUMENTATION_CODE: -1\n"
            assert device_observe(good, "test.package", api, nonce, phase) == labels
            bad = [good.replace("DRAFT_DEVICE_PASS "+label+"\n", "", 1) for label in labels]
            bad += [good+"DRAFT_DEVICE_PASS "+labels[0]+"\n",
                    good.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: 0"),
                    good+"\nINSTRUMENTATION_CODE: -1\n",
                    good.replace("test.package", "wrong.package"),
                    good.replace(nonce, "999-1-"+str(api)),
                    good.replace("10123", "999"),
                    good.replace("DRAFT_DEVICE_RESULT "+phase, "DRAFT_DEVICE_RESULT diagnostic"),
                    good.replace("DRAFT_DEVICE_PASS "+labels[0], "DRAFT_DEVICE_PASS unknown"),
                    good+"DRAFT_DEVICE_FAILED\n", good+"INSTRUMENTATION_FAILED\n",
                    good.replace(" "+str(api)+" "+nonce, " "+str(60-api)+" "+nonce),
                    good.replace("DRAFT_DEVICE_RESULT "+phase+" "+str(len(labels)), "DRAFT_DEVICE_RESULT "+phase+" 0")]
            for text in bad:
                assert text != good
                try:
                    device_observe(text, "test.package", api, nonce, phase)
                except AssertionError:
                    total += 1
                else:
                    raise AssertionError("Draft device observer accepted incomplete or mismatched evidence")
    # Prove three independently disabled checks make specific negative fixtures pass.
    source = inspect.getsource(device_observe)
    mutations = [
        ("assert labels == DEVICE_LABELS[phase]", "assert True", "missing"),
        ('assert [line for line in lines if line.startswith("INSTRUMENTATION_CODE:")] == ["INSTRUMENTATION_CODE: -1"]', "assert True", "finish"),
        ('assert (pkg, actual_api, actual_nonce, actual_phase) == (package, str(api), nonce, phase)', "assert True", "identity"),
    ]
    for old, new, kind in mutations:
        assert source.count(old) == 1
        scope = {"DEVICE_LABELS": DEVICE_LABELS};exec(compile(source.replace(old, new, 1), "<draft-observer-mutant>", "exec"), scope)
        bad = good.replace("DRAFT_DEVICE_PASS "+labels[0]+"\n", "", 1) if kind == "missing" else good.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: 0") if kind == "finish" else good.replace("test.package", "wrong.package")
        if kind == "missing":
            # Keep count/result coherent so only exact coverage can reject this mutant.
            bad = bad.replace("DRAFT_DEVICE_RESULT "+phase+" "+str(len(labels)), "DRAFT_DEVICE_RESULT "+phase+" "+str(len(labels)-1))
            try:device_observe(bad, "test.package", api, nonce, phase)
            except AssertionError:pass
            else:raise AssertionError("coverage negative did not fail")
        scope["device_observe"](bad, "test.package", api, nonce, phase)
    print("NOTE_DRAFT_DEVICE_OBSERVER "+json.dumps({"status":"PASS","positive":4,"negative":total,"compiled_parser_mutants":3,"scope":"HOST_RECEIPT_PARSER_NOT_DEVICE_EXECUTION","release_ready":False}), flush=True)


def device_android():
    """Independent command, never attached to the existing full regression.

    Existing emulator startup is reused by substituting callbacks only in this
    process. This backend receipt explicitly does NOT certify native buttons.
    """
    import hashlib
    import re
    import traceback
    assert os.environ.get("GITHUB_ACTIONS") == "true", "Disposable Actions emulator only"
    import emulator_gate as gate
    from verify_schema3 import certificate, require_registration
    from verify_paged_exports import debug_key
    from verify_process_control import stop_verified
    from verify_todo_management import installed_readback
    out = ROOT/"draft-device";out.mkdir(exist_ok=True)
    result = {"status":"FAIL","scope":DEVICE_SCOPE,"api":gate.API,
              "commit":os.environ["GITHUB_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],
              "run_attempt":os.environ.get("GITHUB_RUN_ATTEMPT","1"),
              "labels":[],"checks":0,"release_ready":False,
              "native_buttons":"NOT_TESTED","cleanup_failure_race":"NOT_TESTED",
              "media_scope":"UNREFERENCED_SYNTHETIC_FILE_NOT_IMAGE_NOTE_COVERAGE"}
    def run(args, timeout=60, binary=False):
        args = list(map(str, args))
        try:
            p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=not binary, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            def decoded(value):return value.decode("utf-8","replace") if isinstance(value,bytes) else value or ""
            result["command_failure"] = {"args":args,"timeout":timeout,"stdout_tail":decoded(e.stdout)[-6000:],"stderr_tail":decoded(e.stderr)[-6000:]}
            raise
        if p.returncode:
            result["command_failure"] = {"args":args,"returncode":p.returncode,
                "stdout_tail":str(p.stdout)[-6000:],"stderr_tail":str(p.stderr)[-6000:]}
            raise RuntimeError("Draft device command failed: "+repr(args))
        return p.stdout if binary else p.stdout+"\n"+p.stderr
    def verify(adb):
        prefix=[str(adb),"-s",gate.SERIAL]
        apps=list((ROOT/"build/outputs/apk/debug").glob("*.apk"))
        tests=list((ROOT/"build/outputs/apk/androidTest/debug").glob("*.apk"))
        assert len(apps)==len(tests)==1
        app,test=apps[0],tests[0];product,saved=app.read_bytes(),test.read_bytes()
        cert=certificate(app,gate);assert certificate(test,gate)==cert
        result.update(apk_sha256=hashlib.sha256(product).hexdigest(),apk_bytes=len(product),certificate=cert)
        for path in (app,test):run(prefix+["install","-r","-t",path],120)
        require_registration(adb,gate,"draft-before","V12DeviceTest")
        def installed():
            return installed_readback(run,prefix,gate.PKG,product,result.setdefault("installed_readbacks",[]))
        assert installed()==product
        key=debug_key(cert)
        nonce=result["run_id"]+"-"+result["run_attempt"]+"-"+str(gate.API)
        assert re.fullmatch(r"[0-9]+-[0-9]+-(26|34)",nonce)
        with tempfile.TemporaryDirectory(prefix="draft-runner-",dir=ROOT/"build") as temporary:
            work=Path(temporary);src=work/"src";src.mkdir()
            (src/"DraftInstrumentation.java").write_text(DEVICE_JAVA,encoding="utf-8")
            init=work/"runner.gradle"
            init.write_text("gradle.beforeProject { p ->\n p.plugins.withId('com.android.application') {\n"
                " p.androidComponents.finalizeDsl { dsl ->\n"
                " dsl.defaultConfig.testInstrumentationRunner = 'ci.drafts.DraftInstrumentation'\n"
                " dsl.sourceSets.getByName('androidTest').java.srcDir "+json.dumps(str(src))+"\n"
                " dsl.signingConfigs.getByName('debug').storeFile = new File("+json.dumps(str(key))+")\n"
                " }\n }\n}\n")
            backup=work/"default-test.apk";backup.write_bytes(saved)
            try:
                text=run(["gradle","--no-daemon","--console=plain","-I",init,"assembleDebugAndroidTest"],300)
                (out/"build.log").write_text(text)
                assert app.read_bytes()==product and certificate(test,gate)==cert
                run(prefix+["install","-r","-t",test],120)
                component=gate.PKG+".test/ci.drafts.DraftInstrumentation"
                rows=re.findall(r"^instrumentation:(\S+) \(target=([^)]+)\)\s*$",run(prefix+["shell","pm","list","instrumentation"]),re.M)
                assert [r for r in rows if r[0].startswith(gate.PKG+".test/")]==[(component,gate.PKG)]
                args=prefix+["shell","-n","-T","am","instrument","-w","-r","-e","expectedPackage",gate.PKG,"-e","expectedApi",str(gate.API),"-e","nonce",nonce]
                diagnostic=run(args+["-e","phase","diagnostic",component],60)
                (out/"diagnostic.log").write_text(diagnostic)
                assert "java.lang.AssertionError: draft_device_diagnostic_sentinel" in diagnostic
                assert "DRAFT_DEVICE_FAILED" in diagnostic and "INSTRUMENTATION_CODE: 0" in diagnostic
                try:device_observe(diagnostic,gate.PKG,gate.API,nonce,"seed")
                except AssertionError:pass
                else:raise AssertionError("Diagnostic failure accepted")
                for phase in ("seed","reopen"):
                    if phase=="reopen":
                        result["force_stop"]=stop_verified(adb,gate.SERIAL,gate.PKG)
                    text=run(args+["-e","phase",phase,component],180)
                    (out/(phase+".log")).write_text(text)
                    labels=device_observe(text,gate.PKG,gate.API,nonce,phase)
                    result["labels"].extend(labels)
                    result[phase]={"labels":labels,"log_sha256":hashlib.sha256(text.encode()).hexdigest(),"log":text}
                assert installed()==product
            finally:
                assert backup.read_bytes()==saved
                run(prefix+["install","-r","-t",backup],120);test.write_bytes(saved)
                require_registration(adb,gate,"draft-restored","V12DeviceTest")
                assert app.read_bytes()==product and test.read_bytes()==saved and installed()==product
        result.update(product_readback="EXACT_BEFORE_AND_AFTER",default_test_restored=True,diagnostic_failure_rejected=True)
    old_database,old_native=gate.verify_database,gate.verify_native_ui
    try:
        gate.verify_database=verify
        gate.verify_native_ui=lambda adb:None
        gate.main()
        assert result["labels"]==DEVICE_LABELS["seed"]+DEVICE_LABELS["reopen"]
        result["status"]="PASS"
    except BaseException as e:
        result.update(status="FAIL",error=repr(e),traceback=traceback.format_exc()[-12000:])
        raise
    finally:
        gate.verify_database,gate.verify_native_ui=old_database,old_native
        result["checks"]=len(result["labels"])
        (out/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        print("NOTE_DRAFT_DEVICE "+json.dumps(result,ensure_ascii=False),flush=True)


def installed_pull_selftest():
    """Execute both actual draft callbacks with filesystem/ADB doubles, not Android."""
    import ast
    import inspect
    import textwrap
    from types import SimpleNamespace
    from unittest.mock import patch
    import verify_adb_transfer as transfer
    import verify_todo_management as shared
    source = Path(__file__).read_text()
    workflow = (ROOT/".github/workflows/note-drafts.yml").read_text()
    start, end = "          # DRAFT_NATIVE_BEGIN\n", "          # DRAFT_NATIVE_END\n"
    assert workflow.count(start) == workflow.count(end) == 1
    native = textwrap.dedent(workflow.split(start, 1)[1].split(end, 1)[0])
    trees = [ast.parse(source), ast.parse(native)]
    callbacks = []
    for tree, owner, expected_count in zip(trees, ("device_android", "native"), (3, 6)):
        outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == owner)
        imports = [n for n in ast.walk(outer if owner == "device_android" else tree)
                   if isinstance(n, ast.ImportFrom) and n.module == "verify_todo_management"]
        assert len(imports) == 1
        namespace = {}
        exec(compile(ast.Module(body=imports, type_ignores=[]), "<draft-shared-import>", "exec"), namespace)
        assert namespace.get("installed_readback") is shared.installed_readback
        found = [n for n in ast.walk(outer) if isinstance(n, ast.FunctionDef) and n.name == "installed"]
        assert len(found) == 1
        callback = found[0]
        calls = [n for n in ast.walk(outer) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "installed"]
        assert len(calls) == expected_count, "Every original APK checkpoint must remain"
        # No independent installed APK stream left hidden beside the new callback.
        for node in ast.walk(outer):
            if isinstance(node, ast.Call):
                literals = [x.value for x in ast.walk(node) if isinstance(x, ast.Constant)]
                assert not ("exec-out" in literals and "cat" in literals and "run-as" not in literals)
        if owner == "native":
            command = next(n for n in outer.body if isinstance(n, ast.FunctionDef) and n.name == "command")
            traced = [n for n in ast.walk(command) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Name) and n.func.id == "run_adb_traced"]
            assert len(traced) == 1 and {k.arg for k in traced[0].keywords} == {"binary", "receipt", "runner"}
        def checker(run, prefix, package, expected, records, node=callback, kind=owner):
            # Native command already owns its unchanged 40-second traced-command budget.
            # The shared transfer owns the original 30-second exact-file budget.
            def command(*args, binary=False):
                return run(prefix+list(args), binary=binary)
            scope = dict(namespace, run=run, prefix=prefix, gate=SimpleNamespace(PKG=package),
                         product=expected, result={"installed_readbacks": records}, command=command)
            exec(compile(ast.Module(body=[node], type_ignores=[]), "<actual-draft-installed>", "exec"), scope)
            return scope["installed"]()
        assert shared.shared_pull_contracts(checker) == 16
        callbacks.append(checker)
    # Same actual callbacks/checker for genuine and compiled mutants. Every mutant
    # must first pass the exact positive witness before its negative is exercised.
    original = transfer.pull_exact
    text = inspect.getsource(original)
    changes = [
        ("actual == expected and opened.st_size == len(expected)", "True"),
        ("if result.returncode != 0:", "if False:"),
        ("if clock() >= deadline:", "if False:"),
        ("if elapsed >= 30:", "if False:"),
        ("actual_bytes=len(actual)", "actual_bytes=len(expected)"),
    ]
    caught = 0
    for old, new in changes:
        assert text.count(old) == 1 and old != new
        scope = dict(vars(transfer))
        exec(compile(text.replace(old, new, 1), "<draft-pull-mutant>", "exec"), scope)
        with patch.object(transfer, "pull_exact", scope["pull_exact"]):
            for checker in callbacks:
                assert shared.shared_pull_contracts(checker, ("exact",)) == 1
                try:
                    shared.shared_pull_contracts(checker)
                except AssertionError:
                    caught += 1
                else:
                    raise AssertionError("Draft callback accepted weakened installed transfer")
    assert caught == 10
    print("DRAFT_INSTALLED_PULL "+json.dumps(dict(status="PASS", callbacks=2,
        positive=2, negative=30, compiled_mutants=5, witnessed_rejections=caught,
        scope="ACTUAL_DRAFT_CALLBACKS_HOST_FILES_AND_ADB_DOUBLES_NOT_ANDROID",
        release_ready=False)), flush=True)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["selftest"]:
        selftest()
        session_selftest()
        ui_model_selftest()
        device_observer_selftest()
        installed_pull_selftest()
    elif sys.argv[1:] == ["android"]:
        device_android()
    else:
        raise SystemExit("Usage: verify_note_drafts.py selftest|android")
