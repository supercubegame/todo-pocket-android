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
import android.accessibilityservice.AccessibilityServiceInfo;
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
  static String bounds(Rect r) {
    return "["+r.left+","+r.top+"]["+r.right+","+r.bottom+"]";
  }
  static void configureWindowTracking(UiAutomation ui)throws Exception {
    // Register window-change tracking once, before READY and before any UI input.
    // Preserve existing view-ID, event and feedback configuration; no touch exploration.
    AccessibilityServiceInfo info=ui.getServiceInfo();
    if(info==null)throw new IOException("missing observer service info");
    int expected=info.flags|AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS;
    info.flags=expected;
    ui.setServiceInfo(info);
    AccessibilityServiceInfo actual=ui.getServiceInfo();
    if(actual==null||actual.flags!=expected)throw new IOException("window tracking configuration mismatch");
  }
  static void clearObservationCache(UiAutomation ui)throws Exception {
    // Invalidate only this shell observer's accessibility cache before its ONE read.
    // API26 has the process-wide client cache; API34 exposes a connection cache.
    // No reconnect, second tree read, input replay or cached-XML fallback.
    if(Build.VERSION.SDK_INT==26) {
      Class<?> client=Class.forName("android.view.accessibility.AccessibilityInteractionClient");
      Object instance=client.getMethod("getInstance").invoke(null);
      client.getMethod("clearCache").invoke(instance);
    } else if(Build.VERSION.SDK_INT==34) {
      if(!ui.clearCache())throw new IOException("cache clear refused");
    } else throw new IOException("unsupported cache API");
  }
  static void node(StringBuilder b,AccessibilityNodeInfo n,int index,int depth,Rect clip,String path)throws Exception {
    if(depth>96||++nodes>20000)throw new IOException("hierarchy limit");
    if(!n.isVisibleToUser())return;
    Rect r=new Rect();n.getBoundsInScreen(r);
    String rawBounds=bounds(r);
    if(!r.intersect(clip))throw new IOException("visible node outside root/scroll viewport"
        +" path="+path+" window="+n.getWindowId()+" bounds="+rawBounds+" clip="+bounds(clip));
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
      if(child==null)throw new IOException("missing hierarchy child path="+path+"/"+i+" window="+n.getWindowId());
      try { node(b,child,i,depth+1,n.isScrollable()?r:clip,path+"/"+i); }
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
    clearObservationCache(ui);
    AccessibilityNodeInfo root=ui.getRootInActiveWindow();
    if(root==null)throw new IOException("no active root");
    try {
      if(!root.refresh())throw new IOException("stale root refresh");
      if(!root.isVisibleToUser())throw new IOException("invisible active root");
      Rect clip=new Rect();root.getBoundsInScreen(clip);
      if(clip.isEmpty())throw new IOException("empty root bounds");
      nodes=0;StringBuilder b=new StringBuilder("<hierarchy>");
      node(b,root,0,0,clip,"0");b.append("</hierarchy>");return b.toString();
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
      configureWindowTracking(ui);
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


def validate_receipt(receipt, binding, xml, reads):
    """Validate against separately frozen identity and actual last XML, not self-consistency alone."""
    commit,run,attempt,api,nonce,dex=binding
    assert isinstance(commit,str) and re.fullmatch("[0-9a-f]{40}",commit)
    assert all(isinstance(v,str) and re.fullmatch("[1-9][0-9]*",v) for v in (run,attempt))
    assert type(api) is int and api in (26,34)
    assert isinstance(nonce,str) and re.fullmatch("[0-9a-f]{32}",nonce)
    assert isinstance(dex,str) and re.fullmatch("[0-9a-f]{64}",dex)
    assert type(reads) is int and reads>0
    expected=dict(commit=commit,run_id=run,run_attempt=attempt,api=api,nonce=nonce,dex_sha256=dex,
        status="CLOSED",scope="CI_PERSISTENT_READONLY_UI_NOT_PRODUCT_OR_ROOT_CAUSE_PROOF")
    for key,value in expected.items():
        assert type(receipt[key]) is type(value) and receipt[key]==value
    for key,value in dict(starts=1,reconnects=0,reads=reads,last_sequence=reads,exit_code=0).items():
        assert type(receipt[key]) is int and receipt[key]==value
    assert not any(key in receipt for key in ("error","close_error","cleanup_errors"))
    assert isinstance(xml,bytes) and 0<len(xml)<=MAX_XML
    text=xml.decode("utf-8",errors="strict")
    assert "<!" not in text
    root=ET.fromstring(text)
    assert root.tag=="hierarchy" and list(root.iter("node"))
    assert receipt["last_xml_sha256"]==hashlib.sha256(xml).hexdigest()
    return True


class Observer:
    def __init__(self, adb, serial, sdk, folder, receipt):
        self.prefix=[str(adb),"-s",serial]
        self.serial=serial;self.sdk=Path(sdk);self.folder=Path(folder)
        self.receipt=receipt;self.process=None;self.pipe=None;self.log=None
        self.nonce=uuid.uuid4().hex;self.seq=0;self.failed=False;self.closed=False
        self.binding=None
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
            # Immutable expected values come from CI/device/build inputs, never the mutable receipt.
            self.binding=(env["GITHUB_SHA"],env["GITHUB_RUN_ID"],env["GITHUB_RUN_ATTEMPT"],
                          self.api,self.nonce,hashlib.sha256(data).hexdigest())
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
            if error is None and self.receipt["status"]=="CLOSED":
                cleanup(lambda:validate_receipt(self.receipt,self.binding,
                    (self.folder/"observer-last.xml").read_bytes(),self.seq-1))
            def write_receipt():
                self.folder.mkdir(parents=True,exist_ok=True)
                (self.folder/"observer.json").write_text(json.dumps(self.receipt,indent=2)+"\n")
            cleanup(write_receipt)
        if error is not None and not primary_failed:raise error


def run_native_phase(observer, body, phase):
    """One original-native phase; return only after strict observer shutdown.

    body receives a fresh node reader. This is an adapter, not full-gate wiring:
    the caller must invoke it at the original phase boundary, and its independent
    report must require the persisted receipt, binding, DEX and XML artifacts.
    """
    started=time.monotonic();primary=None;binding=None;reads=0;last_xml=b""
    phase.clear()
    phase.update(status="FAIL",release_ready=False,
        scope="ORIGINAL_NATIVE_PHASE_OBSERVER_LIFECYCLE_NOT_PRODUCT_ACCEPTANCE")
    try:
        observer.start()
        binding=tuple(observer.binding)
        phase["binding"]=list(binding)
        def nodes():
            nonlocal reads,last_xml
            text=observer.dump()
            tree=ET.fromstring(text)
            assert tree.tag=="hierarchy" and list(tree.iter("node"))
            last_xml=text.encode("utf-8");reads+=1
            return list(tree.iter("node"))
        value=body(nodes)
    except BaseException as exc:
        primary=exc
        phase["error"]=repr(exc)
        raise
    finally:
        try:
            observer.close(primary_failed=primary is not None)
            if primary is None:
                validate_receipt(observer.receipt,binding,last_xml,reads)
                phase.update(status="PASS",reads=reads,close_before_return=True,
                    last_xml_sha256=hashlib.sha256(last_xml).hexdigest())
        except BaseException as exc:
            phase["status"]="FAIL"
            if primary is None:
                phase["error"]=repr(exc)
                raise
            phase["close_error"]=repr(exc)
        finally:
            phase["elapsed_seconds"]=float(time.monotonic()-started)
    return value


def native_phase_contracts(run):
    """Exercise the exact phase runner with lifecycle doubles, not Android."""
    import copy
    primary=ValueError("original native assertion")
    close_error=RuntimeError("observer close sentinel")
    xml='<hierarchy><node text="fresh"/></hierarchy>'
    counts={"positive":0,"negative":0}
    def case(mode):
        events=[];phase={};receipt={}
        class Model:
            binding=("a"*40,"12","1",26,"b"*32,"c"*64)
            def start(self):
                events.append("start")
                if mode=="start":raise primary
                receipt.update(commit="a"*40,run_id="12",run_attempt="1",api=26,
                    nonce="b"*32,dex_sha256="c"*64,status="ACTIVE",starts=1,
                    reconnects=0,reads=0,last_sequence=0,exit_code=0,
                    scope="CI_PERSISTENT_READONLY_UI_NOT_PRODUCT_OR_ROOT_CAUSE_PROOF")
                return self
            def dump(self):
                events.append("dump")
                if mode=="dump":raise primary
                receipt["reads"]+=1;receipt["last_sequence"]+=1
                receipt["last_xml_sha256"]=hashlib.sha256(xml.encode()).hexdigest()
                return xml
            def close(self,primary_failed=False):
                events.append(("close",primary_failed))
                if mode in ("close","both"):raise close_error
                if mode!="not_closed":receipt["status"]="CLOSED"
        observer=Model();observer.receipt=receipt
        def body(nodes):
            events.append("body")
            if mode=="zero":return 42
            for i in range(2):
                got=nodes();assert len(got)==1 and got[0].get("text")=="fresh"
            if mode in ("body","both"):raise primary
            if mode=="binding":
                observer.binding=("d"*40,)+observer.binding[1:]
                receipt["commit"]="d"*40
            if mode=="count":
                receipt["reads"]=receipt["last_sequence"]=3
            return 42
        try:
            value=run(observer,body,phase)
        except BaseException as exc:
            if mode in ("start","dump","body","both"):
                assert exc is primary,("primary exception replaced",mode,exc)
            elif mode=="close":assert exc is close_error
            else:assert isinstance(exc,(AssertionError,ValueError,KeyError)),(mode,exc)
            assert phase["status"]=="FAIL" and "error" in phase
            assert events.count("start")==1
            assert sum(isinstance(e,tuple) and e[0]=="close" for e in events)==1
            if mode=="both":assert phase["close_error"]==repr(close_error)
            assert "later_instrumentation" not in events
            counts["negative"]+=1
        else:
            assert mode=="ok",("invalid phase accepted",mode)
            assert value==42 and phase["status"]=="PASS"
            assert events==["start","body","dump","dump",("close",False)]
            # A following suite is entered only after the synchronous return.
            events.append("later_instrumentation")
            assert phase["reads"]==2 and phase["binding"]==list(observer.binding)
            assert phase["last_xml_sha256"]==hashlib.sha256(xml.encode()).hexdigest()
            assert phase["close_before_return"] is True
            assert phase["scope"]=="ORIGINAL_NATIVE_PHASE_OBSERVER_LIFECYCLE_NOT_PRODUCT_ACCEPTANCE"
            assert phase["release_ready"] is False
            counts["positive"]+=1
        assert type(phase["elapsed_seconds"]) is float and phase["elapsed_seconds"]>=0
        return copy.deepcopy(phase)
    case("ok")
    for mode in ("start","dump","body","close","both","zero","not_closed","binding","count"):
        case(mode)
    return counts


def native_phase_selftest():
    counts=native_phase_contracts(run_native_phase)
    source=inspect.getsource(run_native_phase)
    mutants=[
        ("primary=exc", "primary=None"),
        ("validate_receipt(observer.receipt,binding,last_xml,reads)",
         "validate_receipt(observer.receipt,observer.binding,last_xml,reads)"),
        ("validate_receipt(observer.receipt,binding,last_xml,reads)",
         'validate_receipt(observer.receipt,binding,last_xml,observer.receipt["reads"])'),
    ]
    for old,new in mutants:
        assert source.count(old)==1
        scope=dict(globals())
        exec(compile(source.replace(old,new,1),"native-phase-mutant","exec"),scope)
        # contracts always execute the valid two-read lifecycle before bad input.
        try:native_phase_contracts(scope["run_native_phase"])
        except AssertionError:pass
        else:raise AssertionError("native phase mutant survived "+old)
    print("UI_OBSERVER_NATIVE_PHASE_HOST "+json.dumps(counts)+
          " 3 compiled mutants rejected; LIFECYCLE_DOUBLES_NOT_FULL_GATE_WIRING",flush=True)


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


def receipt_contracts(validate):
    import copy
    xml=b'<hierarchy><node text="exact"/></hierarchy>'
    binding=("a"*40,"12","1",26,"b"*32,"c"*64)
    good=dict(status="CLOSED",scope="CI_PERSISTENT_READONLY_UI_NOT_PRODUCT_OR_ROOT_CAUSE_PROOF",
        commit=binding[0],run_id="12",run_attempt="1",api=26,nonce=binding[4],
        dex_sha256=binding[5],starts=1,reads=2,reconnects=0,last_sequence=2,exit_code=0,
        last_xml_sha256=hashlib.sha256(xml).hexdigest())
    original=copy.deepcopy(good)
    assert validate(good,binding,xml,2) is True and good==original
    other=dict(good,api=34)
    assert validate(other,binding[:3]+(34,)+binding[4:],xml,2) is True
    bad=[]
    for key in good:
        item=copy.deepcopy(good);del item[key];bad.append((item,binding,xml,2))
    for key,values in {
        "status":["ACTIVE","FAIL"],
        "scope":["PRODUCT_ACCEPTANCE"],
        "commit":["d"*40],"run_id":["13"],"run_attempt":["2"],
        "api":[34,26.0,True],"nonce":["e"*32],"dex_sha256":["f"*64],
        "starts":[0,2,True,1.0],"reads":[0,1,3,True,2.0],
        "reconnects":[1,False,0.0],"last_sequence":[1,3,True,2.0],
        "exit_code":[255,False,0.0],"last_xml_sha256":["f"*64],
        "error":["earlier failure"],"close_error":["shutdown failed"],"cleanup_errors":[[]],
    }.items():
        for value in values:
            item=copy.deepcopy(good);item[key]=value;bad.append((item,binding,xml,2))
    for data in (b"",b"wrong",b"<hierarchy/>",
                 b'<!DOCTYPE hierarchy><hierarchy><node/></hierarchy>',b"\xff"):
        item=dict(good,last_xml_sha256=hashlib.sha256(data).hexdigest())
        bad.append((item,binding,data,2))
    bad.append((good,binding,xml+b" ",2))
    for count in (0,1,3,True,2.0):bad.append((good,binding,xml,count))
    for index,value in enumerate(("", "0", "01", 27, "nonce", "dex")):
        changed=list(binding);changed[index]=value;item=dict(good)
        item[("commit","run_id","run_attempt","api","nonce","dex_sha256")[index]]=value
        bad.append((item,tuple(changed),xml,2))
    for args in bad:
        try:validate(*args)
        except (AssertionError,ValueError,KeyError,TypeError,ET.ParseError,UnicodeError):pass
        else:raise AssertionError("invalid observer receipt accepted "+repr(args[:2]))
    return len(bad)


def receipt_selftest():
    count=receipt_contracts(validate_receipt)
    source=inspect.getsource(validate_receipt)
    for old,new in [
        ('assert type(receipt[key]) is type(value) and receipt[key]==value',
         'assert True'),
        ('assert type(receipt[key]) is int and receipt[key]==value',
         'assert receipt[key]==value'),
        ('assert receipt["last_xml_sha256"]==hashlib.sha256(xml).hexdigest()', 'assert True'),
        ('assert not any(key in receipt for key in ("error","close_error","cleanup_errors"))',
         'assert True'),
        ('assert root.tag=="hierarchy" and list(root.iter("node"))', 'assert True'),
    ]:
        assert source.count(old)==1
        scope=dict(globals())
        exec(compile(source.replace(old,new,1),"receipt-mutant","exec"),scope)
        try:receipt_contracts(scope["validate_receipt"])
        except AssertionError:pass
        else:raise AssertionError("observer receipt mutant survived "+old)
    print("UI_OBSERVER_RECEIPT_HOST 2 positive "+str(count)+
          " negative 5 compiled mutants rejected; NOT_INDEPENDENT_REPORT_ACCEPTANCE",flush=True)


def selftest():
    receipt_selftest()
    native_phase_selftest()
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
            observer.binding=("a"*40,"12","1",26,observer.nonce,"c"*64)
            receipt.update(commit="a"*40,run_id="12",run_attempt="1",api=26,dex_sha256="c"*64)
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
        for field,value in (("commit","d"*40),("reads",True),("last_xml_sha256","f"*64)):
            obs,receipt=attach("tamper-"+field);obs.dump();receipt[field]=value
            try:obs.close()
            except AssertionError:pass
            else:raise AssertionError("close accepted corrupted receipt "+field)
            assert receipt["status"]=="FAIL" and obs.closed and obs.process.poll()==0
            persisted=json.loads((obs.folder/"observer.json").read_text())
            assert persisted["status"]=="FAIL" and persisted["cleanup_errors"]
        obs,receipt=attach("tamper-primary");obs.dump();receipt["commit"]="d"*40
        try:
            try:raise sentinel
            finally:obs.close(primary_failed=True)
        except ValueError as caught:assert caught is sentinel
        assert receipt["status"]=="FAIL"
        for mode in ("phase-ok","phase-dead","phase-both"):
            obs,receipt=attach(mode);phase={}
            # Only setup is substituted. dump/close and the local process pipe
            # are the actual implementation; Android startup is not simulated.
            obs.start=lambda:obs
            def body(nodes):
                for number in (1,2):
                    assert nodes()[0].get("text")==str(number)
                if mode!="phase-ok":
                    obs.process.terminate();obs.process.wait(timeout=3)
                if mode=="phase-both":raise sentinel
                return "completed"
            try:value=run_native_phase(obs,body,phase)
            except BaseException as exc:
                if mode=="phase-both":assert exc is sentinel
                else:assert mode=="phase-dead" and isinstance(exc,RuntimeError)
                assert phase["status"]=="FAIL" and receipt["status"]=="FAIL"
            else:
                assert mode=="phase-ok" and value=="completed"
                assert phase["status"]=="PASS" and phase["reads"]==2
                assert receipt["status"]=="CLOSED" and receipt["exit_code"]==0
            assert obs.closed and obs.process.poll() is not None
            persisted=json.loads((obs.folder/"observer.json").read_text())
            assert persisted==receipt
    print("UI_OBSERVER_NATIVE_PHASE_PIPES 1 positive 2 negative; ACTUAL_HOST_PIPES_NOT_ADB",flush=True)
    print("UI_OBSERVER_SESSION_HOST 2 positive 8 negative; ACTUAL_PIPES_NOT_ADB",flush=True)
    print("UI_OBSERVER_RECEIPT_CLOSE 3 tamper rejections 1 original failure preserved; ACTUAL_HOST_PIPES",flush=True)


def java_contracts():
    # Android signatures and deterministic doubles; executable Java bridge, NOT SDK/device acceptance.
    stubs={
      "android/accessibilityservice/AccessibilityServiceInfo.java":"""package android.accessibilityservice;
        public class AccessibilityServiceInfo {
          public static final int FLAG_RETRIEVE_INTERACTIVE_WINDOWS=64;
          public int flags=18,eventTypes=-1,feedbackType=16;public long notificationTimeout=0;
        }""",
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
      "android/os/Build.java":"package android.os; public class Build {public static class VERSION {public static int SDK_INT=Integer.getInteger(\"api\",26);}}",
      "android/os/Process.java":"package android.os; public class Process {public static int myUid(){return 2000;}}",
      "android/os/SystemProperties.java":'package android.os; public class SystemProperties {public static String get(String k){return "1";}}',
      "android/app/IUiAutomationConnection.java":"package android.app; public interface IUiAutomationConnection {}",
      "android/app/UiAutomationConnection.java":"package android.app; public class UiAutomationConnection implements IUiAutomationConnection {public UiAutomationConnection(){}}",
      "android/graphics/Rect.java":"""package android.graphics; public class Rect {
        public int left=0,top=0,right=100,bottom=100;
        public boolean intersect(Rect r){
          if(left<r.right&&r.left<right&&top<r.bottom&&r.top<bottom){
            left=Math.max(left,r.left);top=Math.max(top,r.top);
            right=Math.min(right,r.right);bottom=Math.min(bottom,r.bottom);return true;
          }return false;
        }
        public boolean isEmpty(){return left>=right||top>=bottom;} }""",
      "android/view/accessibility/AccessibilityInteractionClient.java":"""package android.view.accessibility;
        public class AccessibilityInteractionClient {
          public static AccessibilityInteractionClient getInstance(){return new AccessibilityInteractionClient();}
          public void clearCache(){
            if(android.os.Build.VERSION.SDK_INT!=26)throw new AssertionError("wrong legacy cache path");
            android.app.UiAutomation.clearFixture();
          }
        }""",
      "android/util/Base64.java":"""package android.util; public class Base64 {
        public static final int NO_WRAP=2;public static String encodeToString(byte[] b,int f){
        return java.util.Base64.getEncoder().encodeToString(b);}}""",
      "android/app/UiAutomation.java":"""package android.app;
        import android.os.Looper; import android.view.accessibility.AccessibilityNodeInfo;
        import android.accessibilityservice.AccessibilityServiceInfo;
        public class UiAutomation {
          static boolean connected=false;static int reads,clears,idles;
          static int infoReads,infoWrites;static boolean verifiedInfo;
          static AccessibilityServiceInfo info=new AccessibilityServiceInfo();
          public UiAutomation(Looper l,IUiAutomationConnection c){}
          public void connect(){if(connected)throw new AssertionError("reconnect");connected=true;System.err.println("CONNECT");}
          public void disconnect(){if(!connected)throw new AssertionError("double disconnect");connected=false;System.err.println("DISCONNECT");}
          public AccessibilityServiceInfo getServiceInfo(){
            if(!connected||reads!=0||idles!=0)throw new AssertionError("service info outside startup");
            infoReads++;String f=System.getProperty("fixture","");
            if(f.equals("info-null")&&infoReads==1||f.equals("info-readback-null")&&infoReads==2)return null;
            AccessibilityServiceInfo result=new AccessibilityServiceInfo();
            result.flags=f.equals("info-mismatch")&&infoReads==2?18:info.flags;
            if(infoReads==2)verifiedInfo=true;
            return result;
          }
          public void setServiceInfo(AccessibilityServiceInfo value){
            if(!connected||infoReads!=1||infoWrites++!=0||reads!=0)throw new AssertionError("service setup order");
            if("info-write-failure".equals(System.getProperty("fixture")))throw new IllegalStateException("fixture service failure");
            if(value.flags!=82||value.eventTypes!=-1||value.feedbackType!=16||value.notificationTimeout!=0)
              throw new AssertionError("old service properties lost");
            info=value;
          }
          public void waitForIdle(long idle,long total)throws Exception {
            if(!connected)throw new AssertionError("disconnected");
            if(infoWrites!=1||infoReads!=2||!verifiedInfo||info.flags!=82)throw new AssertionError("window tracking setup missing");
            if(android.os.SystemClock.sleeps!=reads+1)throw new AssertionError("fresh request settle missing");
            if(idle!=1000||total!=9000)throw new AssertionError("shared idle budget");
            if("idle".equals(System.getProperty("fixture")))throw new java.util.concurrent.TimeoutException("idle");
            if("late-idle".equals(System.getProperty("fixture")))android.os.SystemClock.now+=9000;
            idles++;
          }
          public static void clearFixture(){
            if(!connected||idles!=reads+1||clears!=reads)throw new AssertionError("cache clear order/count");
            if("cache-failure".equals(System.getProperty("fixture")))throw new IllegalStateException("fixture cache failure");
            clears++;
          }
          public boolean clearCache(){
            if(android.os.Build.VERSION.SDK_INT!=34)throw new AssertionError("wrong modern cache path");
            if("cache-false".equals(System.getProperty("fixture")))return false;
            clearFixture();return true;
          }
          public AccessibilityNodeInfo getRootInActiveWindow(){
            if(clears!=reads+1)throw new AssertionError("fresh cache invalidation missing");
            if("null".equals(System.getProperty("fixture")))return null;
            return new AccessibilityNodeInfo(++reads);
          }
        }""",
      "android/view/accessibility/AccessibilityNodeInfo.java":"""package android.view.accessibility;
        import android.graphics.Rect;public class AccessibilityNodeInfo {
        int n,level;public AccessibilityNodeInfo(int n){this(n,0);}
        AccessibilityNodeInfo(int n,int level){this.n=n;this.level=level;}
        String fixture(){return System.getProperty("fixture","");}
        boolean tree(){return fixture().equals("nested")||fixture().equals("outside");}
        public boolean refresh(){return !"stale".equals(System.getProperty("fixture"));}
        public boolean isVisibleToUser(){return !"invisible".equals(System.getProperty("fixture"));}
        public void getBoundsInScreen(Rect r){
          if(fixture().equals("empty"))r.right=0;
          if(tree()&&level==1){r.left=10;r.top=10;r.right=90;r.bottom=90;}
          if(tree()&&level==2){r.left=20;r.top=0;r.right=80;r.bottom=100;}
          if(fixture().equals("outside")&&level==2){r.left=110;r.right=120;}
        }
        public int getWindowId(){return 7;}
        public CharSequence getText(){return "  草稿😀\\nline\\t "+n;}
        public String getViewIdResourceName(){return "id";}
        public CharSequence getClassName(){return "EditText";} public CharSequence getPackageName(){return "fixture";}
        public CharSequence getContentDescription(){return "desc";}
        public boolean isEnabled(){return true;} public boolean isClickable(){return false;}
        public boolean isLongClickable(){return false;} public boolean isCheckable(){return false;}
        public boolean isChecked(){return false;} public boolean isFocusable(){return true;}
        public boolean isFocused(){return true;} public boolean isScrollable(){return tree()&&level==1;}
        public boolean isSelected(){return false;} public boolean isPassword(){return false;}
        public int getChildCount(){return fixture().equals("child")||tree()&&level<2?1:0;}
        public AccessibilityNodeInfo getChild(int i){return tree()?new AccessibilityNodeInfo(n,level+1):null;}
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
        def run(requests,fixture=None,api=26):
            cmd=["java","-Dapi="+str(api)]+([] if fixture is None else ["-Dfixture="+fixture])+["-cp",str(folder),"PocketUiObserver",nonce]
            return subprocess.run(cmd,input=requests,capture_output=True,text=True,timeout=8)
        requests=nonce+" 1 DUMP\n"+nonce+" 2 DUMP\n"+nonce+" 3 STOP\n"
        def positive(api=26):
            p=run(requests,api=api);assert p.returncode==0,(p.stdout,p.stderr)
            lines=p.stdout.encode().splitlines(keepends=True);assert len(lines)==4
            assert decode_frame(lines[0],nonce,0,"READY")==str(api)
            for seq in (1,2):
                root=ET.fromstring(decode_frame(lines[seq],nonce,seq,"OK"))
                assert root[0].get("text")=="  草稿😀\nline\t "+str(seq)
                assert root[0].get("content-desc")=="desc" and root[0].get("bounds")=="[0,0][100,100]"
            assert decode_frame(lines[3],nonce,3,"BYE")=="closed"
            assert p.stderr.splitlines()==["CONNECT","DISCONNECT"]
        positive();positive(34)
        def window_config_controls():
            for api in (26,34):
                for fixture,reason in (("info-null","missing observer service info"),
                                       ("info-readback-null","window tracking configuration mismatch"),
                                       ("info-mismatch","window tracking configuration mismatch"),
                                       ("info-write-failure","fixture service failure")):
                    p=run(requests,fixture,api)
                    assert p.returncode!=0 and reason in p.stderr,(fixture,p.stdout,p.stderr)
                    assert " READY " not in p.stdout and " OK " not in p.stdout
                    assert p.stderr.splitlines().count("CONNECT")==p.stderr.splitlines().count("DISCONNECT")==1
        window_config_controls()
        def cache_geometry_controls():
            for api in (26,34):
                p=run(requests,"nested",api)
                assert p.returncode==0,(p.stdout,p.stderr)
                lines=p.stdout.encode().splitlines(keepends=True)
                for seq in (1,2):
                    tree=ET.fromstring(decode_frame(lines[seq],nonce,seq,"OK"))
                    assert [n.get("bounds") for n in tree.iter("node")]==[
                        "[0,0][100,100]","[10,10][90,90]","[20,10][80,90]"]
                for fixture,reason in (("outside","visible node outside root/scroll viewport"),
                                       ("empty","empty root bounds"),("cache-failure","fixture cache failure")):
                    p=run(requests,fixture,api)
                    assert p.returncode!=0 and reason in p.stderr and " OK " not in p.stdout,(fixture,p.stdout,p.stderr)
                    if fixture=="outside":
                        assert all(s in p.stderr for s in (
                            "path=0/0/0","window=7","bounds=[110,0][120,100]","clip=[10,10][90,90]"))
                    assert p.stderr.splitlines().count("CONNECT")==p.stderr.splitlines().count("DISCONNECT")==1
            p=run(requests,"cache-false",34)
            assert p.returncode!=0 and "cache clear refused" in p.stderr and " OK " not in p.stdout
        cache_geometry_controls()
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
        for old,new in [
            ("clearObservationCache(ui);",""),
            ('client.getMethod("clearCache").invoke(instance);',""),
            ('if(!ui.clearCache())throw new IOException("cache clear refused");',"ui.clearCache();"),
            ("n.isScrollable()?r:clip","clip"),
            ("if(!r.intersect(clip))","if(false)"),
            ('+" path="+path+" window="+n.getWindowId()+" bounds="+rawBounds+" clip="+bounds(clip)', '+" details omitted"'),
        ]:
            assert JAVA.count(old)==1
            source.write_text(JAVA.replace(old,new));compile_java(folder,sources)
            try:positive();positive(34);cache_geometry_controls()
            except AssertionError:pass
            else:raise AssertionError("compiled cache/geometry mutant survived "+old)
        for old,new in [
            ("configureWindowTracking(ui);",""),
            ("info.flags|AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS",
             "AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS"),
            ("ui.setServiceInfo(info);",""),
            ('if(actual==null||actual.flags!=expected)throw new IOException("window tracking configuration mismatch");',""),
        ]:
            assert JAVA.count(old)==1
            source.write_text(JAVA.replace(old,new));compile_java(folder,sources)
            try:positive();positive(34);window_config_controls()
            except AssertionError:pass
            else:raise AssertionError("compiled window configuration mutant survived "+old)
    print("UI_OBSERVER_JAVA_HOST 2 API sequence positives 2 nested geometry positives 28 negative 18 compiled mutants rejected; ANDROID_DOUBLES_NOT_DEVICE",flush=True)


if __name__ == "__main__":
    if sys.argv[1:] != ["selftest"]:
        raise SystemExit("usage: verify_ui_observer.py selftest")
    selftest()
