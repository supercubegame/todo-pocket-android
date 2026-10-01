#!/usr/bin/env python3
"""CI-only UI observation experiment. Host contracts are not Android acceptance."""
import base64
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

MAX_XML = 4 * 1024 * 1024
MAX_LINE = MAX_XML * 2


def require_ci(env, serial, qemu, api):
    if (env.get("GITHUB_ACTIONS") != "true" or serial != "emulator-5554"
            or qemu != "1" or api not in ("26", "34") or env.get("TEST_API") != api
            or not re.fullmatch("[0-9a-f]{40}", env.get("GITHUB_SHA", ""))
            or not re.fullmatch("[1-9][0-9]*", env.get("GITHUB_RUN_ID", ""))
            or not re.fullmatch("[1-9][0-9]*", env.get("GITHUB_RUN_ATTEMPT", ""))):
        raise ValueError("observer requires identified CI run and disposable API26/34 emulator")
    return int(api)


def decode_frame(line, nonce, seq, expected):
    if not line.endswith(b"\n") or line.count(b"\n") != 1 or len(line) > MAX_LINE:
        raise ValueError("missing, multiple or oversized observer frame")
    parts = line[:-1].decode("ascii").split(" ")
    if len(parts) != 5 or parts[:3] != ["PTO1", nonce, str(seq)]:
        raise ValueError("observer identity/sequence mismatch")
    payload = base64.b64decode(parts[4], validate=True)
    if len(payload) > MAX_XML:
        raise ValueError("observer payload limit")
    text = payload.decode("utf-8", errors="strict")
    if parts[3] != expected:
        raise RuntimeError("observer response "+parts[3]+": "+text[:4000])
    if expected == "OK":
        if "<!" in text:
            raise ValueError("observer DTD/entity/declaration refused")
        root = ET.fromstring(text)
        if root.tag != "hierarchy" or not list(root.iter("node")):
            raise ValueError("observer returned empty/wrong hierarchy")
    return text


JAVA = r'''
import android.app.UiAutomation;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.Build;
import android.os.SystemClock;
import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;
import android.util.Base64;
import java.io.*;
import java.nio.charset.StandardCharsets;

public final class PocketUiObserver {
  static final int LIMIT = 4*1024*1024;
  static String nonce;
  static long seq;
  static int nodes;
  static void frame(String state,String text) throws Exception {
    byte[] data=text.getBytes(StandardCharsets.UTF_8);
    if(data.length>LIMIT)throw new IOException("payload limit");
    System.out.println("PTO1 "+nonce+" "+seq+" "+state+" "+Base64.encodeToString(data,Base64.NO_WRAP));
    System.out.flush();
    if(System.out.checkError())throw new IOException("observer output closed");
  }
  static String escape(Object raw) throws Exception {
    String text=raw==null?"":raw.toString();
    if(text.length()>LIMIT)throw new IOException("attribute limit");
    StringBuilder b=new StringBuilder();
    for(int i=0;i<text.length();) {
      int c=text.codePointAt(i);i+=Character.charCount(c);
      if(c==9||c==10||c==13)b.append("&#").append(c).append(';');
      else if(c=='&')b.append("&amp;");
      else if(c=='<')b.append("&lt;");
      else if(c=='>')b.append("&gt;");
      else if(c=='"')b.append("&quot;");
      else if(c<32||(c>=0xd800&&c<=0xdfff)||c==0xfffe||c==0xffff)
        throw new IOException("invalid XML character");
      else b.appendCodePoint(c);
    }
    return b.toString();
  }
  static void attr(StringBuilder b,String k,Object v)throws Exception {
    b.append(' ').append(k).append("=\"").append(escape(v)).append('"');
    if(b.length()>LIMIT)throw new IOException("XML limit");
  }
  static void node(StringBuilder b,AccessibilityNodeInfo n,int index,int depth,Rect clip)throws Exception {
    if(depth>96||++nodes>20000)throw new IOException("hierarchy limit");
    if(!n.isVisibleToUser())return;
    Rect r=new Rect();n.getBoundsInScreen(r);
    if(!r.intersect(clip))throw new IOException("visible node outside root/scroll viewport");
    b.append("<node");
    attr(b,"index",index);attr(b,"text",n.getText());attr(b,"resource-id",n.getViewIdResourceName());
    attr(b,"class",n.getClassName());attr(b,"package",n.getPackageName());attr(b,"content-desc",n.getContentDescription());
    attr(b,"enabled",n.isEnabled());attr(b,"clickable",n.isClickable());
    attr(b,"long-clickable",n.isLongClickable());attr(b,"checkable",n.isCheckable());attr(b,"checked",n.isChecked());
    attr(b,"focusable",n.isFocusable());attr(b,"focused",n.isFocused());attr(b,"scrollable",n.isScrollable());
    attr(b,"selected",n.isSelected());attr(b,"password",n.isPassword());
    attr(b,"bounds","["+r.left+","+r.top+"]["+r.right+","+r.bottom+"]");b.append('>');
    for(int i=0;i<n.getChildCount();i++) {
      AccessibilityNodeInfo child=n.getChild(i);
      if(child==null)throw new IOException("missing hierarchy child");
      try { node(b,child,i,depth+1,n.isScrollable()?r:clip); }
      finally {child.recycle();}
    }
    b.append("</node>");
  }
  static String dump(UiAutomation ui)throws Exception {
    // A persistent connection can already be idle from the PREVIOUS screen.
    // Allow the new input/window transition to dispatch before observing idle.
    // This is one pre-read barrier, not a retry of a failed tree or assertion.
    long deadline=SystemClock.uptimeMillis()+10000;
    SystemClock.sleep(1000);
    long remaining=deadline-SystemClock.uptimeMillis();
    if(remaining<=0)throw new IOException("settle budget exhausted");
    ui.waitForIdle(1000,remaining);
    if(SystemClock.uptimeMillis()>=deadline)throw new IOException("late idle observation");
    AccessibilityNodeInfo root=ui.getRootInActiveWindow();
    if(root==null)throw new IOException("no active root");
    try {
      if(!root.refresh())throw new IOException("stale root refresh");
      if(!root.isVisibleToUser())throw new IOException("invisible active root");
      Rect clip=new Rect();root.getBoundsInScreen(clip);
      if(clip.isEmpty())throw new IOException("empty root bounds");
      nodes=0;StringBuilder b=new StringBuilder("<hierarchy>");
      node(b,root,0,0,clip);b.append("</hierarchy>");return b.toString();
    } finally {root.recycle();}
  }
  static String request(String line,long next)throws Exception {
    if(line==null||line.length()>128)throw new IOException("closed/oversized request");
    String[] p=line.split(" ",-1);
    if(p.length!=3||!p[0].equals(nonce)||!p[1].equals(Long.toString(next))
       ||(!p[2].equals("DUMP")&&!p[2].equals("STOP")))throw new IOException("invalid request identity/sequence/action");
    return p[2];
  }
  public static void main(String[] args) {
    HandlerThread thread=null;UiAutomation ui=null;boolean connected=false;int exit=1;
    try {
      if(args.length!=1||!args[0].matches("[0-9a-f]{32}"))throw new IOException("nonce");
      nonce=args[0];
      Object qemu=Class.forName("android.os.SystemProperties").getMethod("get",String.class).invoke(null,"ro.kernel.qemu");
      if(!"1".equals(qemu)||android.os.Process.myUid()!=2000
          ||(Build.VERSION.SDK_INT!=26&&Build.VERSION.SDK_INT!=34))throw new IOException("shell emulator only");
      thread=new HandlerThread("pocket-ui-observer");thread.start();
      Class<?> connection=Class.forName("android.app.IUiAutomationConnection");
      Object service=Class.forName("android.app.UiAutomationConnection").getConstructor().newInstance();
      ui=(UiAutomation)UiAutomation.class.getConstructor(Looper.class,connection).newInstance(thread.getLooper(),service);
      UiAutomation.class.getMethod("connect").invoke(ui);connected=true;
      frame("READY",Integer.toString(Build.VERSION.SDK_INT));
      BufferedReader in=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));
      for(;;) {
        String op=request(in.readLine(),seq+1);seq++;
        if(op.equals("STOP")) {
          UiAutomation.class.getMethod("disconnect").invoke(ui);connected=false;
          frame("BYE","closed");exit=0;break;
        }
        frame("OK",dump(ui));
      }
    } catch(Throwable error) {
      error.printStackTrace(System.err);
      try { frame("ERROR",error.toString()); } catch(Throwable reporting) {reporting.printStackTrace(System.err);}
    } finally {
      if(connected)try {UiAutomation.class.getMethod("disconnect").invoke(ui);}
        catch(Throwable closing){closing.printStackTrace(System.err);exit=1;}
      if(thread!=null)thread.quitSafely();
    }
    System.exit(exit);
  }
}
'''


def compile_java(folder, sources, classpath=None):
    launcher = folder/"CompileObserver.java"
    launcher.write_text('import javax.tools.ToolProvider; public class CompileObserver {'
        'public static void main(String[] a) {var c=ToolProvider.getSystemJavaCompiler();'
        'if(c==null)throw new AssertionError("JDK compiler missing");System.exit(c.run(null,System.out,System.err,a));}}')
    args = ["java", str(launcher), "-source", "8", "-target", "8", "-encoding", "UTF-8", "-d", str(folder)]
    if classpath:
        args += ["-classpath", str(classpath)]
    p = subprocess.run(args+list(map(str,sources)),capture_output=True,text=True,timeout=90)
    if p.returncode:
        raise RuntimeError("observer Java compile failed\n"+p.stdout[-6000:]+p.stderr[-6000:])


class LinePipe:
    """One bounded response, no reconnect, no replay, no fallback to old XML."""
    def __init__(self, process):
        self.process=process
        self.buffer=b""
        self.selector=selectors.DefaultSelector()
        self.selector.register(process.stdout,selectors.EVENT_READ)

    def read(self, timeout):
        deadline=time.monotonic()+timeout
        while b"\n" not in self.buffer:
            remaining=deadline-time.monotonic()
            if remaining<=0 or not self.selector.select(remaining):
                raise TimeoutError("observer response timeout")
            part=os.read(self.process.stdout.fileno(),65536)
            if not part:raise RuntimeError("observer disconnected before complete response")
            self.buffer+=part
            if len(self.buffer)>MAX_LINE:raise ValueError("observer frame limit")
        line,self.buffer=self.buffer.split(b"\n",1)
        if time.monotonic()>deadline:raise TimeoutError("observer late response")
        if self.buffer:raise ValueError("unsolicited observer bytes")
        return line+b"\n"

    def close(self):
        self.selector.close()


class Observer:
    def __init__(self, adb, serial, sdk, folder, receipt):
        self.prefix=[str(adb),"-s",serial]
        self.serial=serial;self.sdk=Path(sdk);self.folder=Path(folder)
        self.receipt=receipt;self.process=None;self.pipe=None;self.log=None
        self.nonce=uuid.uuid4().hex;self.seq=0;self.failed=False;self.closed=False
        receipt.update(status="NOT_STARTED",scope="CI_PERSISTENT_READONLY_UI_NOT_PRODUCT_OR_ROOT_CAUSE_PROOF",
                       nonce=self.nonce,starts=0,reads=0,reconnects=0)

    def command(self,*args,timeout=40):
        p=subprocess.run(self.prefix+list(args),stdin=subprocess.DEVNULL,capture_output=True,timeout=timeout)
        if p.returncode:
            raise RuntimeError("observer setup command failed "+repr(args)+" "+repr(p.returncode)+
                               "\n"+p.stdout[-3000:].decode(errors="replace")+p.stderr[-3000:].decode(errors="replace"))
        return p.stdout

    def start(self):
        if self.receipt["starts"] or self.closed:raise RuntimeError("observer cannot restart")
        self.receipt["starts"]=1;self.receipt["status"]="STARTING"
        try:
            # Refuse non-CI before even contacting adb.
            env=os.environ
            require_ci(env,self.serial,"1",env.get("TEST_API",""))
            qemu=self.command("shell","-n","-T","getprop","ro.kernel.qemu").decode().strip()
            api=self.command("shell","-n","-T","getprop","ro.build.version.sdk").decode().strip()
            self.api=require_ci(env,self.serial,qemu,api)
            self.receipt.update(commit=env["GITHUB_SHA"],run_id=env["GITHUB_RUN_ID"],
                                run_attempt=env["GITHUB_RUN_ATTEMPT"],api=self.api)
            self.folder.mkdir(parents=True,exist_ok=True)
            build=self.folder/("observer-"+self.nonce);build.mkdir()
            source=build/"PocketUiObserver.java";source.write_text(JAVA)
            android=self.sdk/"platforms/android-35/android.jar"
            compile_java(build,[source],android)
            dex=build/"dex";dex.mkdir()
            args=[str(self.sdk/"build-tools/35.0.0/d8"),"--min-api","26","--lib",str(android),
                  "--output",str(dex)]+list(map(str,sorted(build.glob("PocketUiObserver*.class"))))
            p=subprocess.run(args,capture_output=True,text=True,timeout=90)
            if p.returncode:raise RuntimeError("observer dex failed\n"+p.stdout[-4000:]+p.stderr[-4000:])
            data=(dex/"classes.dex").read_bytes()
            self.receipt["dex_sha256"]=hashlib.sha256(data).hexdigest()
            remote="/data/local/tmp/pocket-ui-"+self.nonce+".dex"
            self.command("push",str(dex/"classes.dex"),remote)
            if self.command("exec-out","cat",remote)!=data:raise RuntimeError("observer dex readback mismatch")
            self.log=(self.folder/"observer-stderr.log").open("wb")
            # No -n here: stdin carries the request protocol. No PTY, shell root, product code or database access.
            self.process=subprocess.Popen(self.prefix+["shell","-T","CLASSPATH="+remote,"app_process",
                "/system/bin","PocketUiObserver",self.nonce],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=self.log,bufsize=0)
            self.pipe=LinePipe(self.process)
            ready=decode_frame(self.pipe.read(40),self.nonce,0,"READY")
            if ready!=str(self.api):raise RuntimeError("observer API handshake mismatch")
            self.receipt["status"]="ACTIVE"
            return self
        except BaseException as exc:
            self.failed=True;self.receipt.update(status="FAIL",error=repr(exc))
            self.close(primary_failed=True)
            raise

    def _request(self, op, state):
        if self.failed or self.closed or self.process is None or self.process.poll() is not None:
            raise RuntimeError("observer is not live")
        self.seq+=1
        self.process.stdin.write((self.nonce+" "+str(self.seq)+" "+op+"\n").encode())
        self.process.stdin.flush()
        return decode_frame(self.pipe.read(40),self.nonce,self.seq,state)

    def dump(self):
        try:
            text=self._request("DUMP","OK")
            self.receipt["reads"]+=1
            self.receipt["last_sequence"]=self.seq
            self.receipt["last_xml_sha256"]=hashlib.sha256(text.encode()).hexdigest()
            (self.folder/"observer-last.xml").write_text(text)
            return text
        except BaseException as exc:
            self.failed=True;self.receipt.update(status="FAIL",error=repr(exc))
            raise

    def close(self, primary_failed=False):
        if self.closed:return
        error=None
        try:
            if self.process is not None:
                if self.failed:
                    raise RuntimeError("observer failed before shutdown")
                if self._request("STOP","BYE")!="closed":
                    raise RuntimeError("observer shutdown acknowledgment mismatch")
                self.process.stdin.close()
                code=self.process.wait(timeout=5)
                self.receipt["exit_code"]=code
                if code!=0:raise RuntimeError("observer nonzero shutdown")
                self.receipt["status"]="CLOSED"
        except BaseException as exc:
            error=exc;self.failed=True
            self.receipt.update(status="FAIL",close_error=repr(exc))
        finally:
            self.closed=True
            def cleanup(action):
                nonlocal error
                try:action()
                except BaseException as exc:
                    if error is None:error=exc
                    self.receipt.setdefault("cleanup_errors",[]).append(repr(exc))
                    self.receipt["status"]="FAIL"
            def terminate():
                if self.process.poll() is None:
                    self.process.terminate()
                    try:self.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=3)
            if self.process is not None:
                cleanup(terminate)
                for stream in (self.process.stdin,self.process.stdout):
                    if stream and not stream.closed:cleanup(stream.close)
            if self.pipe:cleanup(self.pipe.close)
            if self.log:cleanup(self.log.close)
            def write_receipt():
                self.folder.mkdir(parents=True,exist_ok=True)
                (self.folder/"observer.json").write_text(json.dumps(self.receipt,indent=2)+"\n")
            cleanup(write_receipt)
        if error is not None and not primary_failed:raise error


def contracts(decode, guard):
    nonce = "a" * 32
    xml = '<hierarchy><node text="  草稿😀&#10;line&#9; " bounds="[0,0][80,40]" enabled="true"/></hierarchy>'
    def frame(n=nonce, seq="1", status="OK", payload=xml):
        return ("PTO1 %s %s %s %s\n" % (n, seq, status, base64.b64encode(payload.encode()).decode())).encode()
    assert decode(frame(), nonce, 1, "OK") == xml
    assert ET.fromstring(decode(frame(), nonce, 1, "OK"))[0].get("text") == "  草稿😀\nline\t "
    assert decode(frame(seq="0", status="READY", payload="26"), nonce, 0, "READY") == "26"
    assert decode(frame(seq="2", status="BYE", payload="closed"), nonce, 2, "BYE") == "closed"
    bad = [frame(n="b"*32), frame(seq="0"), frame(seq="2"), frame(seq="01"),
           frame(status="ERROR", payload="root missing"), frame(status="READY"),
           b"", b"garbage\n", frame()[:-1], frame()+frame(), frame().replace(b"PTO1", b"PTO2"),
           frame().replace(b"OK ", b"OK ***"), frame(payload="<hierarchy/>"),
           frame(payload="<node/>"), frame(payload="<hierarchy><node></hierarchy>"),
           frame(payload='<!DOCTYPE hierarchy [<!ENTITY x "hi">]><hierarchy><node text="&x;"/></hierarchy>'),
           frame(payload="x"*(MAX_XML+1))]
    for line in bad:
        try:
            decode(line, nonce, 1, "OK")
        except (ValueError, RuntimeError, ET.ParseError, UnicodeError):
            pass
        else:
            raise AssertionError("invalid/stale response accepted")
    env = dict(GITHUB_ACTIONS="true", GITHUB_SHA="a"*40, GITHUB_RUN_ID="12",
               GITHUB_RUN_ATTEMPT="1", TEST_API="26")
    assert guard(env, "emulator-5554", "1", "26") == 26
    for key in env:
        changed = dict(env); changed[key] = ""
        try: guard(changed, "emulator-5554", "1", "26")
        except ValueError: pass
        else: raise AssertionError("missing CI identity accepted: "+key)
    for serial, qemu, api in [("phone","1","26"),("emulator-5554","0","26"),
                              ("emulator-5554","1","34"),("emulator-5554","1","27")]:
        try: guard(env, serial, qemu, api)
        except ValueError: pass
        else: raise AssertionError("unsafe observer environment accepted")
    return {"positive": 5, "negative": len(bad)+len(env)+4}


def selftest():
    counts = contracts(decode_frame, require_ci)
    mutations = [
        ("parts[:3] != [\"PTO1\", nonce, str(seq)]", "parts[:1] != [\"PTO1\"]"),
        ('if parts[3] != expected:', 'if False:'),
        ('or not list(root.iter("node"))', ''),
        ('env.get("GITHUB_ACTIONS") != "true"', 'False'),
        ('or qemu != "1"', ''),
    ]
    for old,new in mutations:
        target=decode_frame if old in inspect.getsource(decode_frame) else require_ci
        source=inspect.getsource(target)
        assert source.count(old)==1
        scope=dict(globals());exec(compile(source.replace(old,new),"observer-mutant","exec"),scope)
        try:contracts(scope["decode_frame"],scope["require_ci"])
        except AssertionError:pass
        else:raise AssertionError("observer guard mutant survived "+old)
    # Real local subprocess pipes exercise split frames, EOF and timeout. Not Android.
    script="import os,time;os.write(1,b'first');time.sleep(.03);os.write(1,b' line\\n');time.sleep(.1)"
    p=subprocess.Popen([sys.executable,"-c",script],stdout=subprocess.PIPE)
    pipe=LinePipe(p)
    try:
        assert pipe.read(2)==b"first line\n"
        try:pipe.read(2)
        except RuntimeError:pass
        else:raise AssertionError("EOF accepted")
    finally:pipe.close();p.wait(timeout=3);p.stdout.close()
    p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(5)"],stdout=subprocess.PIPE)
    pipe=LinePipe(p)
    try:
        before=time.monotonic()
        try:pipe.read(.05)
        except TimeoutError:pass
        else:raise AssertionError("silent observer accepted")
        assert time.monotonic()-before<2
    finally:p.terminate();p.wait(timeout=3);pipe.close();p.stdout.close()
    java_contracts()
    session_contracts()
    print("UI_OBSERVER_HOST_PROTOCOL "+json.dumps(counts)+" HOST_ONLY", flush=True)
    print("UI_OBSERVER_HOST_MUTANTS 5 rejected; PIPE 1 positive 2 negative; HOST_ONLY",flush=True)


def session_contracts():
    server=r'''import sys,base64
nonce,mode=sys.argv[1:]
for line in sys.stdin:
    n,s,op=line.strip().split(" ")
    if mode=="disconnect":sys.exit(7)
    state="BYE" if op=="STOP" else "OK"
    body="closed" if op=="STOP" else '<hierarchy><node text="'+s+'"/></hierarchy>'
    if mode=="error":state="ERROR";body="fixture error"
    if mode=="stale":s="0"
    if mode=="close-error" and op=="STOP":sys.exit(8)
    print("PTO1 "+n+" "+s+" "+state+" "+base64.b64encode(body.encode()).decode(),flush=True)
    if op=="STOP":sys.exit(0)
'''
    with tempfile.TemporaryDirectory(prefix="observer-pipes-") as tmp:
        def attach(mode):
            receipt={}
            observer=Observer("unused","emulator-5554","unused",Path(tmp)/mode,receipt)
            observer.folder.mkdir()
            observer.process=subprocess.Popen([sys.executable,"-c",server,observer.nonce,mode],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
            observer.pipe=LinePipe(observer.process)
            receipt.update(starts=1,status="ACTIVE")
            return observer,receipt
        obs,receipt=attach("ok")
        for i in (1,2):
            assert ET.fromstring(obs.dump())[0].get("text")==str(i)
        obs.close();assert receipt["status"]=="CLOSED" and receipt["reads"]==2 and receipt["exit_code"]==0
        assert receipt["reconnects"]==0 and obs.seq==3
        try:obs.dump()
        except RuntimeError:pass
        else:raise AssertionError("closed observer reused")
        for mode in ("disconnect","error","stale"):
            obs,receipt=attach(mode)
            try:obs.dump()
            except RuntimeError:pass
            except ValueError:pass
            else:raise AssertionError("bad observer accepted "+mode)
            sequence=obs.seq
            try:obs.dump()
            except RuntimeError:pass
            else:raise AssertionError("failed observer reused")
            assert obs.seq==sequence and receipt["reads"]==0
            obs.close(primary_failed=True);assert receipt["status"]=="FAIL"
        obs,receipt=attach("close-error")
        obs.dump()
        try:obs.close()
        except RuntimeError:pass
        else:raise AssertionError("failed shutdown accepted")
        assert receipt["status"]=="FAIL"
        obs,receipt=attach("primary")
        obs.failed=True
        sentinel=ValueError("original product assertion")
        try:
            try:raise sentinel
            finally:obs.close(primary_failed=True)
        except ValueError as caught:assert caught is sentinel
    print("UI_OBSERVER_SESSION_HOST 2 positive 8 negative; ACTUAL_PIPES_NOT_ADB",flush=True)


def java_contracts():
    # Android signatures and deterministic doubles; executable Java bridge, NOT SDK/device acceptance.
    stubs={
      "android/os/Looper.java":"package android.os; public class Looper {}",
      "android/os/SystemClock.java":"""package android.os; public class SystemClock {
        public static long now=20000;public static int sleeps;
        public static long uptimeMillis(){return now;}
        public static void sleep(long duration){
          if(duration!=1000)throw new AssertionError("settle duration");
          sleeps++;now+="settle-overrun".equals(System.getProperty("fixture"))?10000:duration;
        }}""",
      "android/os/HandlerThread.java":"""package android.os; public class HandlerThread {
        public HandlerThread(String n){} public void start(){} public Looper getLooper(){return new Looper();}
        public boolean quitSafely(){return true;} }""",
      "android/os/Build.java":"package android.os; public class Build {public static class VERSION {public static int SDK_INT=26;}}",
      "android/os/Process.java":"package android.os; public class Process {public static int myUid(){return 2000;}}",
      "android/os/SystemProperties.java":'package android.os; public class SystemProperties {public static String get(String k){return "1";}}',
      "android/app/IUiAutomationConnection.java":"package android.app; public interface IUiAutomationConnection {}",
      "android/app/UiAutomationConnection.java":"package android.app; public class UiAutomationConnection implements IUiAutomationConnection {public UiAutomationConnection(){}}",
      "android/graphics/Rect.java":"""package android.graphics; public class Rect {
        public int left=0,top=0,right=100,bottom=100;
        public boolean intersect(Rect r){return true;} public boolean isEmpty(){return false;} }""",
      "android/util/Base64.java":"""package android.util; public class Base64 {
        public static final int NO_WRAP=2;public static String encodeToString(byte[] b,int f){
        return java.util.Base64.getEncoder().encodeToString(b);}}""",
      "android/app/UiAutomation.java":"""package android.app;
        import android.os.Looper; import android.view.accessibility.AccessibilityNodeInfo;
        public class UiAutomation {
          static boolean connected=false;static int reads;
          public UiAutomation(Looper l,IUiAutomationConnection c){}
          public void connect(){if(connected)throw new AssertionError("reconnect");connected=true;System.err.println("CONNECT");}
          public void disconnect(){if(!connected)throw new AssertionError("double disconnect");connected=false;System.err.println("DISCONNECT");}
          public void waitForIdle(long idle,long total)throws Exception {
            if(!connected)throw new AssertionError("disconnected");
            if(android.os.SystemClock.sleeps!=reads+1)throw new AssertionError("fresh request settle missing");
            if(idle!=1000||total!=9000)throw new AssertionError("shared idle budget");
            if("idle".equals(System.getProperty("fixture")))throw new java.util.concurrent.TimeoutException("idle");
            if("late-idle".equals(System.getProperty("fixture")))android.os.SystemClock.now+=9000;
          }
          public AccessibilityNodeInfo getRootInActiveWindow(){
            if("null".equals(System.getProperty("fixture")))return null;
            return new AccessibilityNodeInfo(++reads);
          }
        }""",
      "android/view/accessibility/AccessibilityNodeInfo.java":"""package android.view.accessibility;
        import android.graphics.Rect;public class AccessibilityNodeInfo {
        int n;public AccessibilityNodeInfo(int n){this.n=n;}
        public boolean refresh(){return !"stale".equals(System.getProperty("fixture"));}
        public boolean isVisibleToUser(){return !"invisible".equals(System.getProperty("fixture"));} public void getBoundsInScreen(Rect r){}
        public CharSequence getText(){return "  草稿😀\\nline\\t "+n;}
        public String getViewIdResourceName(){return "id";}
        public CharSequence getClassName(){return "EditText";} public CharSequence getPackageName(){return "fixture";}
        public CharSequence getContentDescription(){return "desc";}
        public boolean isEnabled(){return true;} public boolean isClickable(){return false;}
        public boolean isLongClickable(){return false;} public boolean isCheckable(){return false;}
        public boolean isChecked(){return false;} public boolean isFocusable(){return true;}
        public boolean isFocused(){return true;} public boolean isScrollable(){return false;}
        public boolean isSelected(){return false;} public boolean isPassword(){return false;}
        public int getChildCount(){return "child".equals(System.getProperty("fixture"))?1:0;} public AccessibilityNodeInfo getChild(int n){return null;}
        public void recycle(){}
        }"""
    }
    nonce="a"*32
    with tempfile.TemporaryDirectory(prefix="observer-contract-") as tmp:
        folder=Path(tmp);sources=[]
        for name,body in stubs.items():
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body);sources.append(path)
        source=folder/"PocketUiObserver.java";source.write_text(JAVA);sources.append(source)
        compile_java(folder,sources)
        def run(requests,fixture=None):
            cmd=["java"]+([] if fixture is None else ["-Dfixture="+fixture])+["-cp",str(folder),"PocketUiObserver",nonce]
            return subprocess.run(cmd,input=requests,capture_output=True,text=True,timeout=8)
        requests=nonce+" 1 DUMP\n"+nonce+" 2 DUMP\n"+nonce+" 3 STOP\n"
        def positive():
            p=run(requests);assert p.returncode==0,(p.stdout,p.stderr)
            lines=p.stdout.encode().splitlines(keepends=True);assert len(lines)==4
            assert decode_frame(lines[0],nonce,0,"READY")=="26"
            for seq in (1,2):
                root=ET.fromstring(decode_frame(lines[seq],nonce,seq,"OK"))
                assert root[0].get("text")=="  草稿😀\nline\t "+str(seq)
                assert root[0].get("content-desc")=="desc" and root[0].get("bounds")=="[0,0][100,100]"
            assert decode_frame(lines[3],nonce,3,"BYE")=="closed"
            assert p.stderr.splitlines()==["CONNECT","DISCONNECT"]
        positive()
        def budget_controls():
            for fixture,reason in (("settle-overrun","settle budget exhausted"),("late-idle","late idle observation")):
                p=run(requests,fixture)
                assert p.returncode!=0 and reason in p.stderr and " OK " not in p.stdout,(fixture,p.stdout,p.stderr)
                assert p.stderr.splitlines().count("CONNECT")==p.stderr.splitlines().count("DISCONNECT")==1
        budget_controls()
        for fixture in ("null","stale","idle","settle-overrun","late-idle","invisible","child"):
            p=run(requests,fixture)
            assert p.returncode!=0 and " ERROR " in p.stdout and " OK " not in p.stdout,(fixture,p.stdout,p.stderr)
            assert p.stderr.splitlines().count("CONNECT")==p.stderr.splitlines().count("DISCONNECT")==1
        for request in (nonce+" 0 DUMP\n",nonce+" 2 DUMP\n","b"*32+" 1 DUMP\n",
                        nonce+" 1 TAP\n",nonce+" 01 DUMP\n",""):
            p=run(request)
            assert p.returncode!=0 and " ERROR " in p.stdout and " OK " not in p.stdout
        mutants=[
            ('!p[1].equals(Long.toString(next))','false'),
            ('!p[0].equals(nonce)','false'),
            ('frame("OK",dump(ui));','frame("OK","<hierarchy><node text=\\"cached\\"/></hierarchy>");'),
            ('frame("BYE","closed");','frame("BYE","not-closed");'),
        ]
        for old,new in mutants:
            assert JAVA.count(old)==1
            source.write_text(JAVA.replace(old,new));compile_java(folder,sources)
            try:
                positive()
                for request in (nonce+" 0 STOP\n","b"*32+" 1 STOP\n"):
                    p=run(request);assert p.returncode!=0 and " BYE " not in p.stdout
            except AssertionError:pass
            else:raise AssertionError("compiled Java mutant survived "+old)
        for old,new in [
            ("SystemClock.sleep(1000);",""),
            ("ui.waitForIdle(1000,remaining);","ui.waitForIdle(1000,10000);"),
            ('if(remaining<=0)throw new IOException("settle budget exhausted");',""),
            ('if(SystemClock.uptimeMillis()>=deadline)throw new IOException("late idle observation");',""),
        ]:
            assert JAVA.count(old)==1
            source.write_text(JAVA.replace(old,new));compile_java(folder,sources)
            try:positive();budget_controls()
            except AssertionError:pass
            else:raise AssertionError("compiled settle mutant survived "+old)
    print("UI_OBSERVER_JAVA_HOST 1 sequence positive 13 negative 8 compiled mutants rejected; ANDROID_DOUBLES_NOT_DEVICE",flush=True)


if __name__ == "__main__":
    if sys.argv[1:] != ["selftest"]:
        raise SystemExit("usage: verify_ui_observer.py selftest")
    selftest()
