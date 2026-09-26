#!/usr/bin/env python3
"""Exit-code gates. Real Java execution, explicit staged Android boundaries."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
V12_SOURCES = ("ActivityModel", "Ledger", "CalendarRules", "CustomFields", "NoteDocument", "TodoModel", "BackupCodec", "LegacyImport", "MediaRepository", "BackupArchive")

# Generated test output is not a new hand-authored project file. These execute real
# Java filesystem/ZIP operations, not a Python reimplementation. Fixtures are synthetic.
IO_TEST = r'''
import com.supercubegame.pockettodo.*;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
public final class FileBoundaryTest {
 static int checks;
 interface Action { void run() throws Exception; }
 static void ok(boolean b,String s) {if(!b)throw new AssertionError(s);checks++;System.out.println("PASS "+s);}
 static Object invoke(Object o,String method,Class<?>[] types,Object...args)throws Exception {
  try{return o.getClass().getMethod(method,types).invoke(o,args);}catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
 }
 static void reject(Action a,String s)throws Exception {boolean bad=false;try{a.run();}catch(IllegalArgumentException|IllegalStateException|IOException e){bad=true;}ok(bad,s);}
 static Class<?> type(String n)throws Exception{return Class.forName("com.supercubegame.pockettodo."+n);}
 static Object preview(byte[] b)throws Exception {try{return type("LegacyImport").getMethod("preview",byte[].class).invoke(null,(Object)b);}catch(InvocationTargetException e){throw(Exception)e.getCause();}}
 static Object repo(Path p,long max)throws Exception {return type("MediaRepository").getConstructor(Path.class,long.class).newInstance(p,max);}
 static String copy(Object r,InputStream in)throws Exception{return(String)invoke(r,"copy",new Class[]{InputStream.class},in);}
 static Path media(Object r,String id)throws Exception{return(Path)invoke(r,"path",new Class[]{String.class},id);}
 static void archive(Path p,byte[] state,Set<String> ids,Object r)throws Exception {
  try{type("BackupArchive").getMethod("write",Path.class,byte[].class,Set.class,type("MediaRepository")).invoke(null,p,state,ids,r);}catch(InvocationTargetException e){throw(Exception)e.getCause();}
 }
 static Object open(Path p,Path root,long budget)throws Exception {
  try{return type("BackupArchive").getMethod("read",Path.class,Path.class,long.class).invoke(null,p,root,budget);}catch(InvocationTargetException e){throw(Exception)e.getCause();}
 }
 static long count(Path p)throws IOException{try(java.util.stream.Stream<Path>s=Files.list(p)){return s.count();}}
 static void close(Object o)throws Exception{((AutoCloseable)o).close();}
 static void rewrite(Path source,Path target,String change,boolean remove)throws IOException{
  try(ZipFile z=new ZipFile(source.toFile());ZipOutputStream out=new ZipOutputStream(Files.newOutputStream(target))){
   Enumeration<? extends ZipEntry> es=z.entries();while(es.hasMoreElements()){
    ZipEntry e=es.nextElement();if(remove&&e.getName().equals(change))continue;
    out.putNextEntry(new ZipEntry(e.getName()));try(InputStream in=z.getInputStream(e)){byte[] bytes=in.readAllBytes();if(e.getName().equals(change))bytes[0]^=1;out.write(bytes);}out.closeEntry();
   }
  }
 }
 static void extraEntry(Path source,Path target,String name)throws IOException{
  try(ZipFile z=new ZipFile(source.toFile());ZipOutputStream out=new ZipOutputStream(Files.newOutputStream(target))){
   Enumeration<? extends ZipEntry> es=z.entries();while(es.hasMoreElements()){
    ZipEntry e=es.nextElement();out.putNextEntry(new ZipEntry(e.getName()));try(InputStream in=z.getInputStream(e)){out.write(in.readAllBytes());}out.closeEntry();
   }out.putNextEntry(new ZipEntry(name));out.write(1);out.closeEntry();
  }
 }
 public static void main(String[] args)throws Exception{
  TodoModel old=new TodoModel();long first=old.add("普通待办：买牛奶");old.add("已经完成");old.toggle(2);String before=old.encode();byte[] bytes=BackupCodec.encode(old);
  Object plan=preview(bytes);List<?> items=(List<?>)invoke(plan,"todos",new Class[]{});
  TodoModel.Item a=(TodoModel.Item)items.get(0),b=(TodoModel.Item)items.get(1);
  ok(items.size()==2&&a.id==first&&a.title.equals("普通待办：买牛奶")&&!a.done&&b.done,"legacy preview preserves order identity text and completion");
  ok(old.encode().equals(before),"legacy preview does not mutate source model");
  ok(invoke(plan,"sourceId",new Class[]{}).equals(invoke(preview(bytes),"sourceId",new Class[]{})),"legacy import retry has stable source fingerprint");
  boolean immutable=false;try{items.clear();}catch(UnsupportedOperationException e){immutable=true;}ok(immutable,"legacy preview list immutable");
  ok(((List<?>)invoke(preview(BackupCodec.encode(new TodoModel())),"todos",new Class[]{})).isEmpty(),"empty legacy backup imports no invented rows");
  reject(()->preview(new byte[]{1,2,3}),"foreign legacy bytes rejected");byte[] broken=bytes.clone();broken[broken.length-2]^=1;
  reject(()->preview(broken),"damaged legacy checksum rejected");reject(()->preview(null),"null legacy backup rejected");
  Path root=Files.createTempDirectory("pocket-files-");
  try{
   Path store=Files.createDirectory(root.resolve("private-media"));Object r=repo(store,1024);byte[] photo=new byte[]{(byte)137,80,78,71,13,10,26,10,1,2,3,4};
   Path original=root.resolve("gallery-original");Files.write(original,photo);String id;try(InputStream in=Files.newInputStream(original)){id=copy(r,in);}
   ok(id.matches("[0-9a-f]{64}")&&Arrays.equals(Files.readAllBytes(media(r,id)),photo),"private copy content digest and exact bytes");
   ok(Files.exists(original)&&Arrays.equals(Files.readAllBytes(original),photo),"import never deletes or changes gallery source");
   ok(copy(r,new ByteArrayInputStream(photo)).equals(id)&&count(store)==1,"duplicate media content deduplicated");
   Object reopened=repo(store,1024);ok(Arrays.equals(Files.readAllBytes(media(reopened,id)),photo),"media survives repository reconstruction");
   reject(()->media(r,"../outside"),"media path traversal rejected");
   reject(()->copy(r,new ByteArrayInputStream(new byte[1025])),"over-budget media import explicitly fails");
   ok(count(store)==1,"oversize import leaves no partial asset");
   // Override bulk read explicitly: InputStream's default implementation may swallow
   // a one-shot read() failure after partial progress. Require the exact injected cause.
   IOException injected=new IOException("synthetic read failure after prefix");
   InputStream failing=new InputStream(){boolean prefix;public int read()throws IOException{throw injected;}public int read(byte[] out,int off,int len)throws IOException{if(prefix)throw injected;prefix=true;out[off]=7;return 1;}};
   boolean exact=false;try{copy(r,failing);}catch(IOException e){exact=e==injected;}
   ok(exact,"interrupted source read propagates exact injected failure not budget rejection");ok(count(store)==1,"failed stream leaves no partial asset");
   reject(()->copy(r,new ByteArrayInputStream(new byte[0])),"empty media input rejected");
   Path outside=root.resolve("outside");Files.write(outside,photo);String fake="a".repeat(64);Files.createSymbolicLink(store.resolve(fake),outside);
   reject(()->media(r,fake),"media symlink cannot escape private store");Files.delete(store.resolve(fake));
   Files.write(media(r,id),new byte[]{9});reject(()->invoke(r,"verify",new Class[]{String.class},id),"corrupted stored media rejected by digest");
   reject(()->copy(r,new ByteArrayInputStream(photo)),"dedup does not trust an existing corrupt file");Files.write(store.resolve(id),photo);
   Path staging=Files.createDirectory(root.resolve("staging"));Path zip=root.resolve("full.ptodo12");byte[] state="synthetic-state-v1\n中文".getBytes(java.nio.charset.StandardCharsets.UTF_8);
   archive(zip,state,Set.of(id),r);Object snap=open(zip,staging,4096);byte[] restored=(byte[])invoke(snap,"state",new Class[]{});
   ok(Arrays.equals(state,restored),"archive state round-trips exact bytes");
   @SuppressWarnings("unchecked") Map<String,Path> assets=(Map<String,Path>)invoke(snap,"assets",new Class[]{});
   ok(assets.keySet().equals(Set.of(id))&&Arrays.equals(Files.readAllBytes(assets.get(id)),photo),"archive media set and bytes round-trip exactly");
   restored[0]^=1;ok(Arrays.equals(state,(byte[])invoke(snap,"state",new Class[]{})),"archive state snapshot defensive copy");
   ok(Arrays.equals(Files.readAllBytes(store.resolve(id)),photo),"archive staging never replaces live media");close(snap);ok(count(staging)==0,"closing staged snapshot cleans temporary files");
   reject(()->invoke(snap,"state",new Class[]{}),"closed archive snapshot cannot be reused");
   reject(()->archive(zip,state,Set.of(id),r),"archive export refuses existing destination");
   Path bad=root.resolve("bad.ptodo12");rewrite(zip,bad,"media/"+id,false);reject(()->open(bad,staging,4096),"damaged archive media rejected");ok(count(staging)==0,"bad media archive leaves no staging residue");
   rewrite(zip,bad,"state.bin",false);reject(()->open(bad,staging,4096),"damaged archive state rejected");
   rewrite(zip,bad,"media/"+id,true);reject(()->open(bad,staging,4096),"missing referenced asset rejected");
   rewrite(zip,bad,"manifest.txt",false);reject(()->open(bad,staging,4096),"foreign archive header rejected");
   extraEntry(zip,bad,"unlisted.bin");reject(()->open(bad,staging,4096),"unlisted archive asset cannot slip through");
   // Build a real duplicate-name ZIP by patching equal-length local/central names.
   extraEntry(zip,bad,"spare.bin");byte[] duplicate=Files.readAllBytes(bad),from="spare.bin".getBytes(),to="state.bin".getBytes();int patched=0;
   for(int i=0;i<=duplicate.length-from.length;i++){boolean match=true;for(int j=0;j<from.length;j++)if(duplicate[i+j]!=from[j])match=false;if(match){System.arraycopy(to,0,duplicate,i,to.length);patched++;}}
   ok(patched==2,"duplicate zip fixture changes both local and central names");Files.write(bad,duplicate);
   try(ZipFile valid=new ZipFile(bad.toFile())){int names=0;Enumeration<? extends ZipEntry> en=valid.entries();while(en.hasMoreElements())if(en.nextElement().getName().equals("state.bin"))names++;ok(names==2,"duplicate fixture parses and exposes two state entries");}
   reject(()->open(bad,staging,4096),"duplicate archive names rejected");
   reject(()->open(zip,staging,state.length+photo.length-1),"expanded archive byte budget enforced");ok(count(staging)==0,"all rejected archive reads clean staging");
   try(ZipOutputStream out=new ZipOutputStream(Files.newOutputStream(bad))){out.putNextEntry(new ZipEntry("../escaped"));out.write(photo);out.closeEntry();}
   reject(()->open(bad,staging,4096),"hostile archive paths rejected");ok(!Files.exists(root.resolve("escaped")),"archive never extracts arbitrary entry paths");
   byte[] packed=Files.readAllBytes(zip);Files.write(bad,Arrays.copyOf(packed,packed.length-10));reject(()->open(bad,staging,4096),"truncated zip central directory rejected");
   Path missing=root.resolve("missing.ptodo12");reject(()->archive(missing,state,Set.of(fake),r),"export rejects referenced missing media");ok(!Files.exists(missing),"failed archive export leaves no published destination");
   archive(root.resolve("empty.ptodo12"),new byte[0],Set.of(),r);Object empty=open(root.resolve("empty.ptodo12"),staging,1);ok(((byte[])invoke(empty,"state",new Class[]{})).length==0&&((Map<?,?>)invoke(empty,"assets",new Class[]{})).isEmpty(),"transport can represent an empty payload without inventing data");close(empty);
   String abc=copy(r,new ByteArrayInputStream(new byte[]{97,98,99}));ok(abc.equals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),"media digest matches independent published SHA256 abc vector");
   String boundary=copy(r,new ByteArrayInputStream(new byte[1024]));ok(Files.size(media(r,boundary))==1024,"exact media byte budget accepted");
   InputStream stalled=new InputStream(){public int read(){return 0;}public int read(byte[] x,int off,int len){return 0;}};reject(()->copy(r,stalled),"nonprogressing input fails instead of hanging");
   ok(count(staging)==0&&Arrays.equals(Files.readAllBytes(original),photo),"all boundary tests retain original and clear staging");
  }finally{try(java.util.stream.Stream<Path>s=Files.walk(root)){for(Path p:s.sorted(Comparator.reverseOrder()).toArray(Path[]::new))Files.deleteIfExists(p);}}
  System.out.println("FILE_BOUNDARY_RESULT "+checks+"/"+checks+" PASS; JVM_FILESYSTEM_ONLY; DATABASE_ANDROID_IMAGE_DECODING_FULL_RESTORE_NOT_TESTED");
 }
}
'''

def run(args, **kwargs):
    print("+ " + " ".join(map(str, args)), flush=True)
    return subprocess.run(args, check=True, **kwargs)

def core():
    agents = Path("AGENTS.md").read_bytes()
    assert agents == Path("CLAUDE.md").read_bytes(), "agent instructions diverged"
    assert len(agents.splitlines()) <= 200
    manifest = ET.parse("src/main/AndroidManifest.xml").getroot()
    assert not manifest.findall("uses-permission"), "offline app must request no permissions"
    out = Path("build/core")
    out.mkdir(parents=True, exist_ok=True)
    run(["javac", "-encoding", "UTF-8", "-d", str(out),
         "src/main/java/com/supercubegame/pockettodo/TodoModel.java",
         "src/main/java/com/supercubegame/pockettodo/BackupCodec.java", "tests/CoreTest.java"])
    run(["java", "-cp", str(out), "CoreTest"])

def v12():
    core()
    base = Path("src/main/java/com/supercubegame/pockettodo")
    sources = [base / (name + ".java") for name in V12_SOURCES]
    sources.append(Path("tests/V12CoreTest.java"))
    for path in sources:
        assert path.is_file(), "Required V1.2 contract source missing: " + str(path)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="v12-core-", dir="build") as out:
        test = Path(out) / "FileBoundaryTest.java"
        test.write_text(IO_TEST, encoding="utf-8")
        run(["javac", "-encoding", "UTF-8", "-d", out, *map(str, sources), str(test)])
        run(["java", "-cp", out, "V12CoreTest"])
        run(["java", "-cp", out, "FileBoundaryTest"])
    run([sys.executable, "tools/verify_exports.py"])
    share_ticket()
    share_write()
    print("V12_ACCEPTANCE PARTIAL: JVM domain/file/pixel contracts only; Android codecs/persisted derivatives/UI/share NOT_TESTED by this fast gate")

def share_ticket():
    """Compile the actual pure nested class; no Android/SQLite/SAF is simulated."""
    import tempfile
    source = Path("src/main/java/com/supercubegame/pockettodo/MainActivity.java").read_text()
    start, end = "    static final class ShareTicket", "    // END_SHARE_TICKET"
    assert source.count(start) == source.count(end) == 1, "Missing/ambiguous share ticket"
    body = source[source.index(start):source.index(end)]
    tests = r'''
 static int n;
 interface Action {void run();}
 static void ok(boolean b){if(!b)throw new AssertionError("check "+(n+1));n++;}
 static void reject(Action a){boolean bad=false;try{a.run();}catch(IllegalArgumentException|IllegalStateException e){bad=true;}ok(bad);}
 public static void main(String[] x){
  byte[] state={1,2},zip={3,4};ShareTicket t=new ShareTicket(state,zip);
  state[0]=9;zip[0]=9;ok(java.util.Arrays.equals(t.take(new byte[]{1,2}),new byte[]{3,4}));
  reject(()->t.take(new byte[]{1,2}));
  ShareTicket stale=new ShareTicket(new byte[]{1,2},new byte[]{3});
  reject(()->stale.take(new byte[]{1,9}));reject(()->stale.take(new byte[]{1,2}));
  ShareTicket cancel=new ShareTicket(new byte[]{1},new byte[]{3});cancel.close();cancel.close();reject(()->cancel.take(new byte[]{1}));
  reject(()->new ShareTicket(null,new byte[]{3}));reject(()->new ShareTicket(new byte[]{1},null));
  reject(()->new ShareTicket(new byte[0],new byte[]{3}));reject(()->new ShareTicket(new byte[]{1},new byte[0]));
  reject(()->new ShareTicket(new byte[8388609],new byte[]{3}));
  reject(()->new ShareTicket(new byte[]{1},new byte[16777217]));
  ShareTicket exact=new ShareTicket(new byte[8388608],new byte[16777216]);ok(exact.take(new byte[8388608]).length==16777216);
  ShareTicket noState=new ShareTicket(new byte[]{1},new byte[]{3});reject(()->noState.take(null));reject(()->noState.take(new byte[]{1}));
  if(n!=14)throw new AssertionError("coverage drift");
  System.out.println("SHARE_TICKET_HOST 14/14 PASS NOT_ANDROID_DB_OR_SAF");
 }
'''
    variants = [("real", body, None)]
    for name, before, after, failure in (
        ("zip_alias", "this.zip=zip.clone();", "this.zip=zip;", "AssertionError: check 1"),
        ("stale_bypass", "if(!java.util.Arrays.equals(state,current))", "if(false)", "AssertionError: check 3"),
        ("replay", "}finally{close();}", "}finally{}", "AssertionError: check 2"),
    ):
        assert body.count(before) == 1, "Mutation anchor drift: " + name
        variants.append((name, body.replace(before, after, 1), failure))
    for name, implementation, failure in variants:
        with tempfile.TemporaryDirectory(prefix="share-ticket-", dir="build") as out:
            test = Path(out) / "TicketTest.java"
            test.write_text("public class TicketTest {\n" + implementation + tests + "\n}", encoding="utf-8")
            run(["javac", "--release", "8", "-encoding", "UTF-8", "-d", out, str(test)], timeout=40)
            result = subprocess.run(["java", "-cp", out, "TicketTest"], text=True, capture_output=True, timeout=40)
            print(name, result.returncode, result.stdout, result.stderr, flush=True)
            if failure is None:
                assert result.returncode == 0 and "SHARE_TICKET_HOST 14/14 PASS" in result.stdout, "Share ticket real implementation failed"
            else:
                assert result.returncode != 0 and failure in result.stderr, "Share ticket mutant survived or failed for wrong reason: " + name
    print("SHARE_TICKET_MUTANTS 3/3 REJECTED; HOST_EXTRACTED_JAVA_NOT_ANDROID_UI")

def share_write():
    """Execute the actual stream helper with controlled failures, not Android providers."""
    import tempfile
    source = Path("src/main/java/com/supercubegame/pockettodo/MainActivity.java").read_text()
    start, end = "    static final class VerifiedShareWrite", "    // END_VERIFIED_SHARE_WRITE"
    assert source.count(start) == source.count(end) == 1, "Missing/ambiguous verified share writer"
    body = source[source.index(start):source.index(end)]
    tests = r'''
 static int checks;
 interface Action {void run() throws Exception;}
 static void ok(boolean b,String label){if(!b)throw new AssertionError(label);checks++;System.out.println("PASS "+label);}
 static IOException failure(Action a)throws Exception{try{a.run();}catch(IOException e){return e;}throw new AssertionError("expected_io_failure");}
 static byte[] sample(int size){byte[] b=new byte[size];for(int i=0;i<size;i++)b[i]=(byte)(i*37+11);return b;}
 static final class Sink extends OutputStream {
  final ByteArrayOutputStream data=new ByteArrayOutputStream();int closes,writes,maxWrite;
  IOException writeFailure,closeFailure;
  public void write(int b)throws IOException{write(new byte[]{(byte)b},0,1);}
  public void write(byte[] b,int off,int n)throws IOException{writes++;maxWrite=Math.max(maxWrite,n);if(writeFailure!=null){data.write(b,off,Math.min(7,n));throw writeFailure;}data.write(b,off,n);}
  public void close()throws IOException{closes++;if(closeFailure!=null)throw closeFailure;}
 }
 static final class Source extends InputStream {
  final byte[] data;int at,closes,reads;boolean zeroOnce;int failAfter=-1;
  IOException readFailure,closeFailure;
  Source(byte[] data){this.data=data;}
  public int read()throws IOException{throw new AssertionError("bulk_read_required");}
  public int read(byte[] b,int off,int n)throws IOException{
   reads++;if(zeroOnce){zeroOnce=false;return 0;}
   if(readFailure!=null&&at>=failAfter)throw readFailure;
   if(at==data.length)return -1;
   int count=Math.min(Math.min(n,1031),data.length-at);
   if(failAfter>at)count=Math.min(count,failAfter-at);
   System.arraycopy(data,at,b,off,count);at+=count;return count;
  }
  public void close()throws IOException{closes++;if(closeFailure!=null)throw closeFailure;}
 }
 static final class Fixture {
  Sink sink=new Sink();Source source;int outputs,inputs;boolean nullOutput,nullInput;
  IOException outputFailure,inputFailure;
  Fixture(byte[] b){source=new Source(b.clone());}
  OutputStream output()throws IOException{outputs++;if(outputFailure!=null)throw outputFailure;return nullOutput?null:sink;}
  InputStream input()throws IOException{inputs++;if(sink.closes!=1)throw new AssertionError("read_before_output_close");if(inputFailure!=null)throw inputFailure;return nullInput?null:source;}
  void run(byte[] b)throws Exception{VerifiedShareWrite.write(b,this::output,this::input);}
 }
 public static void main(String[] args)throws Exception{
  for(int size:new int[]{1,16384,16385,32775,16777216}){
   byte[] b=sample(size),before=b.clone();Fixture f=new Fixture(b);f.run(b);
   ok(Arrays.equals(f.sink.data.toByteArray(),before)&&Arrays.equals(b,before)&&f.outputs==1&&f.inputs==1&&f.sink.closes==1&&f.source.closes==1&&f.sink.maxWrite<=16384,"exact_roundtrip_"+size);
  }
  for(byte[] invalid:new byte[][]{null,new byte[0],new byte[16777217]}){
   Fixture f=new Fixture(new byte[]{1});IOException e=failure(()->f.run(invalid));
   ok(e.getMessage().equals("Share output budget")&&f.outputs==0&&f.inputs==0,"invalid_budget_before_open");
  }
  byte[] b=sample(32775);
  Fixture open=new Fixture(b);open.outputFailure=new IOException("open-output");
  ok(failure(()->open.run(b))==open.outputFailure&&open.outputs==1&&open.inputs==0,"output_open_failure");
  Fixture nil=new Fixture(b);nil.nullOutput=true;
  ok(failure(()->nil.run(b)).getMessage().equals("No output stream")&&nil.inputs==0,"null_output");
  Fixture partial=new Fixture(b);partial.sink.writeFailure=new IOException("partial-write");
  ok(failure(()->partial.run(b))==partial.sink.writeFailure&&partial.sink.closes==1&&partial.inputs==0&&partial.sink.data.size()==7&&Arrays.equals(b,sample(32775)),"partial_write_failure_no_readback");
  Fixture close=new Fixture(b);close.sink.closeFailure=new IOException("close-output");
  ok(failure(()->close.run(b))==close.sink.closeFailure&&close.sink.closes==1&&close.inputs==0,"output_close_failure_no_readback");
  Fixture both=new Fixture(b);both.sink.writeFailure=new IOException("write-primary");both.sink.closeFailure=new IOException("close-secondary");
  IOException combined=failure(()->both.run(b));
  ok(combined==both.sink.writeFailure&&combined.getSuppressed().length==1&&combined.getSuppressed()[0]==both.sink.closeFailure&&both.inputs==0,"write_failure_keeps_suppressed_close");
  Fixture readOpen=new Fixture(b);readOpen.inputFailure=new IOException("open-input");
  ok(failure(()->readOpen.run(b))==readOpen.inputFailure&&readOpen.inputs==1&&readOpen.sink.closes==1,"readback_open_failure");
  Fixture readNil=new Fixture(b);readNil.nullInput=true;
  ok(failure(()->readNil.run(b)).getMessage().equals("No output readback")&&readNil.sink.closes==1,"null_readback");
  for(int prefix:new int[]{0,7,16385}){
   Fixture f=new Fixture(b);f.source.failAfter=prefix;f.source.readFailure=new IOException("read-"+prefix);
   ok(failure(()->f.run(b))==f.source.readFailure&&f.source.at==prefix&&f.source.closes==1,"read_failure_"+prefix);
  }
  for(int size:new int[]{0,7,b.length-1}){
   Fixture f=new Fixture(b);f.source=new Source(Arrays.copyOf(b,size));
   ok(failure(()->f.run(b)).getMessage().equals("Output truncated")&&f.source.closes==1,"truncation_"+size);
  }
  Fixture extra=new Fixture(b);extra.source=new Source(Arrays.copyOf(b,b.length+1));
  ok(failure(()->extra.run(b)).getMessage().equals("Output length differs")&&extra.source.closes==1,"extra_byte_rejected");
  for(int at:new int[]{0,16384,b.length-1}){
   Fixture f=new Fixture(b);f.source.data[at]^=1;
   ok(failure(()->f.run(b)).getMessage().equals("Output bytes differ")&&f.source.closes==1,"mismatch_"+at);
  }
  Fixture stalled=new Fixture(b);stalled.source.zeroOnce=true;
  ok(failure(()->stalled.run(b)).getMessage().equals("Output read made no progress")&&stalled.source.reads==1&&stalled.source.closes==1,"zero_progress_rejected");
  Fixture readClose=new Fixture(b);readClose.source.closeFailure=new IOException("close-input");
  ok(failure(()->readClose.run(b))==readClose.source.closeFailure&&readClose.source.closes==1,"readback_close_failure");
  Fixture mismatchClose=new Fixture(b);mismatchClose.source.data[0]^=1;mismatchClose.source.closeFailure=new IOException("close-after-mismatch");
  IOException mismatch=failure(()->mismatchClose.run(b));
  ok(mismatch.getMessage().equals("Output bytes differ")&&mismatch.getSuppressed().length==1&&mismatch.getSuppressed()[0]==mismatchClose.source.closeFailure,"mismatch_keeps_suppressed_close");
  if(checks!=28)throw new AssertionError("coverage_count_"+checks);
  System.out.println("SHARE_WRITE_HOST 28/28 PASS NOT_ANDROID_PROVIDER_OR_DB");
 }
'''
    variants = [("real", body)]
    for name, before, after in (
        ("mismatch", "if(chunk[i]!=bytes[offset+i])", "if(false)"),
        ("truncated", "if(offset!=bytes.length)", "if(false)"),
        ("zero_progress", 'if(n==0)throw new IOException("Output read made no progress");', "if(n==0)continue;"),
    ):
        assert body.count(before) == 1, "Share writer mutation anchor drift: " + name
        variants.append((name, body.replace(before, after, 1)))
    for name, implementation in variants:
        with tempfile.TemporaryDirectory(prefix="share-write-", dir="build") as out:
            test = Path(out) / "WriteTest.java"
            test.write_text("import java.io.*;import java.util.*;public class WriteTest {\n" + implementation + tests + "\n}", encoding="utf-8")
            run(["javac", "--release", "8", "-encoding", "UTF-8", "-d", out, str(test)], timeout=40)
            result = subprocess.run(["java", "-cp", out, "WriteTest"], text=True, capture_output=True, timeout=40)
            print(name, result.returncode, result.stdout, result.stderr, flush=True)
            if name == "real":
                assert result.returncode == 0 and "SHARE_WRITE_HOST 28/28 PASS" in result.stdout, "Real share writer failed"
            else:
                assert result.returncode != 0 and "AssertionError: expected_io_failure" in result.stderr, "Share writer mutant survived or wrong failure: " + name
    print("SHARE_WRITE_MUTANTS 3/3 REJECTED; HOST_EXTRACTED_JAVA_NOT_ANDROID_PROVIDER")

def build():
    # The inherited V1.1 Gradle/UI configuration is not a V1.2 product. No dormant
    # APK publisher remains here. Replace this guard only WITH real Android gates.
    raise RuntimeError("V1.2 Android phase is not wired: refusing to build/publish the inherited V1.1 UI as V1.2")

def report():
    out = Path("collected")
    logs = {}
    for name in ("core.log", "setup.log", "build.log", "ui.log", "emulator.log"):
        paths = list(out.rglob(name))
        if len(paths) > 1: raise RuntimeError("Ambiguous evidence log: " + name)
        logs[name] = paths[0].read_text(errors="replace")[-24000:] if paths else "NOT_OBSERVED"
    needs = json.loads(os.environ["NEEDS_JSON"])
    doc = {"commit": os.environ["GITHUB_SHA"], "run_id": os.environ["GITHUB_RUN_ID"],
           "jobs": needs, "logs": logs, "physical_device": "NOT_TESTED", "durable_upgrade_ready": False,
           "acceptance_scope": "V1.2_JVM_DOMAIN_AND_FILE_BOUNDARIES", "full_v12_acceptance": "NOT_TESTED", "release_ready": False}
    ui_files = list(out.rglob("ui-result.json"))
    if len(ui_files) > 1: raise RuntimeError("Ambiguous UI evidence")
    doc["ui"] = json.loads(ui_files[0].read_text()) if ui_files else {"status": "NOT_OBSERVED"}
    for name in ("SHA256SUMS.txt", "signature.txt", "package.txt"):
        paths = list(out.rglob(name))
        if len(paths) > 1: raise RuntimeError("Ambiguous artifact evidence: " + name)
        doc[name] = paths[0].read_text() if paths else "NOT_OBSERVED"
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]
    def api(path, method="GET", body=None):
        req = urllib.request.Request("https://api.github.com/repos/" + repo + "/" + path,
            data=json.dumps(body).encode() if body is not None else None, method=method,
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    try:
        api("git/ref/heads/evidence")
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
        api("git/refs", "POST", {"ref": "refs/heads/evidence", "sha": os.environ["GITHUB_SHA"]})
    path = "reports/" + os.environ["GITHUB_SHA"] + "-" + os.environ["GITHUB_RUN_ID"] + ".json"
    body = {"message": "Record staged V1.2 verification evidence", "branch": "evidence", "content": base64.b64encode(data).decode()}
    try:
        prior = api("contents/" + path + "?ref=evidence")
        body["sha"] = prior["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404: raise
    written = api("contents/" + path, "PUT", body)
    actual = api("contents/" + path + "?ref=" + written["commit"]["sha"])
    assert base64.b64decode(actual["content"]) == data, "report readback mismatch"
    print("EVIDENCE " + actual["html_url"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", choices=["core", "v12", "build", "report"])
    mode = parser.parse_args().gate
    try:
        {"core": core, "v12": v12, "build": build, "report": report}[mode]()
    except Exception as exc:
        print(f"GATE_FAILED {mode}: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
