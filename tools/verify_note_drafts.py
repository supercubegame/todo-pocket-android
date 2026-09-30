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


if __name__ == "__main__":
    import sys
    assert sys.argv[1:] == ["selftest"]
    selftest()
