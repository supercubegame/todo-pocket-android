#!/usr/bin/env python3
"""Real APK and system picker gates, disposable CI emulator only."""
import hashlib, json, os, re, subprocess, time, urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
PKG="com.supercubegame.pockettodo.safe.preview"
OLD="com.supercubegame.pockettodo"
ACTIVITY="com.supercubegame.pockettodo.MainActivity"
OUT=Path("delivery")
checks=[]
touch_ready=False

def adb(*args,binary=False): return subprocess.check_output(["adb",*args],timeout=40,text=not binary)
def tree():
    adb("shell","uiautomator","dump","/sdcard/window.xml")
    return ET.fromstring(adb("shell","cat","/sdcard/window.xml"))
def nodes(): return list(tree().iter("node"))
def find(**attrs):
    deadline=time.monotonic()+18; last=[]
    while time.monotonic()<deadline:
        last=nodes()
        for n in last:
            if all(n.get(k)==v for k,v in attrs.items()): return n
        time.sleep(.3)
    print("UI_NODES "+repr([{k:n.get(k) for k in ("text","content-desc","resource-id","bounds","focused","enabled")} for n in last if n.get("text") or n.get("content-desc") or n.get("focused")=="true"]),flush=True)
    raise AssertionError("UI node not found: "+repr(attrs))
def tap_node(n):
    x1,y1,x2,y2=map(int,re.findall(r"\d+",n.get("bounds")))
    adb("shell","input","tap",str((x1+x2)//2),str((y1+y2)//2)); time.sleep(.25)
def tap(**attrs): tap_node(find(**attrs))
def check(ok,name):
    if not ok: raise AssertionError(name)
    checks.append(name); print("PASS "+name,flush=True)
def item(id): return find(**{"content-desc":"todo-"+str(id)})
def absent(id): return not any(n.get("content-desc")=="todo-"+str(id) for n in nodes())
def start(pkg=PKG): adb("shell","am","start","-W","-n",pkg+"/"+ACTIVITY)
def restart():
    adb("shell","am","force-stop",PKG); start()
def add(title):
    tap(**{"content-desc":"新待办输入"}); adb("shell","input","text",title.replace(" ","%s")); tap(text="添加")
def replace_field(description,title):
    field=find(**{"content-desc":description}); length=len(field.get("text","").encode("utf-16-le"))//2
    tap_node(field); adb("shell","input","keyevent","KEYCODE_MOVE_END")
    adb("shell","input","keyevent",*(["KEYCODE_DEL"]*(length+1)))
    check(find(**{"content-desc":description}).get("text")=="","editor fixture cleared through real input")
    if title: adb("shell","input","text",title.replace(" ","%s"))
def screenshot(name):
    time.sleep(.5); data=adb("exec-out","screencap","-p",binary=True)
    assert data[:8]==b"\x89PNG\r\n\x1a\n","invalid PNG"
    (OUT/name).write_bytes(data)
    return {"file":name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}
def save_document():
    deadline=time.monotonic()+18
    while time.monotonic()<deadline:
        for n in nodes():
            if n.get("text","").casefold() in ("save","保存") and n.get("enabled")=="true" and "documentsui" in n.get("package",""):
                tap_node(n); return
        time.sleep(.3)
    raise AssertionError("System document picker save button missing")

def prepare_touch():
    global touch_ready
    if touch_ready: return
    assert os.environ.get("GITHUB_ACTIONS")=="true" and adb("shell","getprop","ro.kernel.qemu").strip()=="1"
    work=Path("build/ci-touch"); work.mkdir(parents=True,exist_ok=True)
    source=r'''import android.os.Build;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.MotionEvent;
public final class PocketTouch {
 public static void main(String[] args) throws Exception {
  if (!Build.HARDWARE.equals("ranchu") && !Build.HARDWARE.equals("goldfish")) throw new SecurityException("Emulator only");
  float x=Float.parseFloat(args[0]), y=Float.parseFloat(args[1]);
  Class<?> cls=Class.forName("android.hardware.input.InputManager");
  Object manager=cls.getMethod("getInstance").invoke(null);
  java.lang.reflect.Method inject=cls.getMethod("injectInputEvent",InputEvent.class,int.class);
  MotionEvent.PointerProperties p=new MotionEvent.PointerProperties(); p.id=0; p.toolType=MotionEvent.TOOL_TYPE_FINGER;
  MotionEvent.PointerCoords c=new MotionEvent.PointerCoords(); c.x=x; c.y=y; c.size=1; c.pressure=1;
  long down=SystemClock.uptimeMillis();
  for (int action : new int[]{MotionEvent.ACTION_DOWN,MotionEvent.ACTION_UP}) {
   if (action==MotionEvent.ACTION_UP) { SystemClock.sleep(80); c.pressure=0; }
   MotionEvent e=MotionEvent.obtain(down,SystemClock.uptimeMillis(),action,1,new MotionEvent.PointerProperties[]{p},new MotionEvent.PointerCoords[]{c},0,0,1,1,0,0,InputDevice.SOURCE_TOUCHSCREEN,0);
   if (e.getToolType(0)!=MotionEvent.TOOL_TYPE_FINGER) throw new AssertionError("Missing finger type");
   if (!Boolean.TRUE.equals(inject.invoke(manager,e,2))) throw new AssertionError("Input injection rejected");
   e.recycle();
  }
  System.out.println("FINGER_TOUCH source=4098 tool=1 accepted");
 }
}
'''
    java=work/"PocketTouch.java"; java.write_text(source)
    sdk=Path(os.environ["ANDROID_HOME"]); android=sdk/"platforms/android-35/android.jar"
    subprocess.run(["javac","-encoding","UTF-8","-cp",str(android),"-d",str(work),str(java)],check=True,timeout=40)
    jar=work/"pocket-touch.jar"
    subprocess.run([str(sdk/"build-tools/35.0.0/d8"),"--lib",str(android),"--min-api","26","--output",str(jar),str(work/"PocketTouch.class")],check=True,timeout=40)
    adb("push",str(jar),"/data/local/tmp/pocket-touch.jar"); touch_ready=True

def select_backup_file():
    find(text="PocketTodo-backup.ptodo")
    for n in nodes():
        if n.get("content-desc")=="List view": tap_node(n); time.sleep(1); break
    matches=[n for n in tree().iter("node") if n.get("resource-id","").endswith(":id/item_root") and any(c.get("text")=="PocketTodo-backup.ptodo" for c in n.iter("node"))]
    if len(matches)!=1: raise AssertionError("Expected exactly one backup document row")
    target=matches[0]; print("PICKER_TARGET "+repr(target.attrib),flush=True)
    x1,y1,x2,y2=map(int,re.findall(r"\d+",target.get("bounds")))
    prepare_touch()
    print(adb("shell","CLASSPATH=/data/local/tmp/pocket-touch.jar","app_process","/system/bin","PocketTouch",str((x1+x2)//2),str((y1+y2)//2)),flush=True)
    time.sleep(1)

def picker_diagnostics():
    result={}
    for name,args in (("activities",("shell","dumpsys","activity","activities")),("platform",("logcat","-d","-v","brief","*:W","PickerActionHandler:V","PickActivity:V","ActivityTaskManager:I","UriGrantsManagerService:V","AccessibilityNodeInfoDumper:S","AndroidRuntime:E"))):
        try:
            text=adb(*args)
            if name=="activities": text="\n".join(line for line in text.splitlines() if any(s in line for s in ("Intent","Hist #","Resumed","launchedFrom","resultTo","resultWho","requestCode")))
            result[name]=text[-18000:]
        except Exception as e: result[name]=repr(e)
    return result

def open_backup():
    tap(text="导入备份"); select_backup_file(); find(text="导入预览")
def stored_state(): return adb("shell","run-as",PKG,"cat","shared_prefs/pocket_todo.xml")

def main():
    OUT.mkdir(exist_ok=True)
    check(os.environ.get("GITHUB_ACTIONS")=="true" and adb("shell","getprop","ro.kernel.qemu").strip()=="1","disposable CI emulator identity")
    url="https://github.com/supercubegame/todo-pocket-android/releases/download/test-35518045028-1/PocketTodo-1.0-debug.apk"
    with urllib.request.urlopen(url,timeout=40) as r: old=r.read()
    check(hashlib.sha256(old).hexdigest()=="2064ab1a485552830bb666f782c6081f6099179b860b097c7084e5b2c6b8d695","original phone-accepted APK pinned digest")
    path=Path(os.environ["RUNNER_TEMP"])/"original-todo.apk"; path.write_bytes(old)
    adb("install",str(path)); start(OLD); add("Keep old data")
    check(item(1).get("text")=="Keep old data","seed original app on disposable emulator")
    adb("install","-r",str(OUT/"PocketTodo-1.1-preview.apk")); adb("shell","pm","clear",PKG); start()
    find(text="口袋待办"); check(find(text="还剩 0 件  /  共 0 件") is not None,"isolated preview launches empty")
    shots=[screenshot("01-empty.png")]
    tap(text="添加"); check(absent(1),"blank input creates no task")
    add("Buy milk"); check(item(1).get("text")=="Buy milk","add via visible input")
    add("Walk outside"); check(item(2).get("text")=="Walk outside","second task distinct")
    tap(**{"content-desc":"todo-1"}); check(item(1).get("checked")=="true","complete via checkbox")
    tap(text="待办"); check(absent(1) and item(2) is not None,"pending filter")
    tap(text="已完成"); check(item(1).get("checked")=="true" and absent(2),"completed filter")
    tap(text="全部"); restart()
    check(item(1).get("checked")=="true" and item(2).get("text")=="Walk outside","restart preserves titles and completion")
    tap(**{"content-desc":"edit-1"}); replace_field("编辑待办输入","Fresh milk"); tap(text="保存")
    check(item(1).get("text")=="Fresh milk" and item(1).get("checked")=="true","edit keeps completion and id")
    tap(**{"content-desc":"edit-1"}); replace_field("编辑待办输入",""); tap(text="保存")
    check(find(text="编辑待办") is not None,"blank edit stays open for correction")
    tap(text="取消"); check(item(1).get("text")=="Fresh milk","cancel invalid edit preserves title")
    tap(**{"content-desc":"edit-1"}); replace_field("编辑待办输入","Discard edit"); tap(text="取消")
    check(item(1).get("text")=="Fresh milk","cancel valid edit preserves title")
    restart(); check(item(1).get("text")=="Fresh milk" and item(1).get("checked")=="true","edit persists across restart")
    tap(text="导出备份"); tap(text="取消"); check(item(1).get("text")=="Fresh milk","cancel export keeps list")
    tap(text="导出备份"); tap(text="选择保存位置"); save_document()
    check(find(text="备份已导出并校验") is not None,"export through real system picker and exact readback")
    tap(**{"content-desc":"delete-2"}); tap(text="取消"); check(item(2) is not None,"cancel deletion preserves task")
    tap(**{"content-desc":"delete-2"}); tap(text="删除"); check(absent(2),"confirm deletes exact task")
    tap(**{"content-desc":"todo-1"}); check(item(1).get("checked")=="false","uncomplete via checkbox")
    restart(); check(absent(2) and item(1).get("checked")=="false","deletion and uncomplete persist")
    tap(text="导入备份"); adb("shell","input","keyevent","KEYCODE_BACK")
    check(item(1).get("checked")=="false" and absent(2),"cancel file picker keeps list")
    open_backup(); shots.append(screenshot("02-import-preview.png")); tap(text="取消")
    check(absent(2) and item(1).get("checked")=="false","cancel import preview keeps list")
    open_backup(); tap(text="确认替换")
    check(item(1).get("checked")=="true" and item(2).get("text")=="Walk outside","confirmed import restores exact exported state")
    restart(); check(item(1).get("checked")=="true" and item(2) is not None,"import survives restart")
    tap(text="撤销导入"); tap(text="确认撤销")
    check(absent(2) and item(1).get("checked")=="false","undo survives restart and restores pre-import list")
    restart(); check(absent(2) and item(1).get("checked")=="false","undo persists across restart")
    open_backup(); tap(text="确认替换"); tap(**{"content-desc":"todo-1"})
    check(find(text="撤销导入").get("enabled")=="false","new mutation invalidates old undo snapshot")
    tap(**{"content-desc":"todo-1"}); shots.append(screenshot("03-tasks.png"))
    before=stored_state(); paths=adb("shell","find","/storage/emulated/0","-name","PocketTodo-backup.ptodo").strip().splitlines()
    check(len(paths)==1 and paths[0].startswith("/storage/emulated/0/"),"locate disposable exported backup fixture")
    corrupt=Path(os.environ["RUNNER_TEMP"])/"corrupt.ptodo"; corrupt.write_bytes(b"broken backup\n"); adb("push",str(corrupt),paths[0])
    tap(text="导入备份"); select_backup_file(); find(text="导入失败：文件无效或无法读取，列表未更改")
    check(stored_state()==before and item(1).get("checked")=="true" and item(2).get("text")=="Walk outside","corrupt file through real picker leaves exact persisted state unchanged")
    restart(); check(stored_state()==before,"rejected import remains unchanged after restart")
    tap(text="已完成"); check(item(1).get("checked")=="true" and absent(2),"completed view after backup roundtrip")
    shots.append(screenshot("04-completed.png"))
    start(OLD); check(item(1).get("text")=="Keep old data" and item(1).get("checked")=="false","original APK coexists and keeps original data")
    check(len({x["sha256"] for x in shots})==len(shots),"real screenshots show distinct states")
    return {"status":"PASS","checks":checks,"count":len(checks),"screenshots":shots,"device":adb("shell","getprop","ro.product.model").strip(),"api":adb("shell","getprop","ro.build.version.sdk").strip(),"physical_device":"NOT_TESTED","release_upgrade":"NOT_TESTED","provider_failure_injection":"NOT_TESTED"}
try:
    result=main()
except Exception as exc:
    result={"status":"FAIL","checks":checks,"error":repr(exc),"physical_device":"NOT_TESTED","diagnostics":picker_diagnostics()}
    print("FAILURE_DIAGNOSTICS "+json.dumps(result["diagnostics"],ensure_ascii=False),flush=True)
    OUT.mkdir(exist_ok=True)
    try: screenshot("failure.png")
    except Exception: pass
    (OUT/"ui-result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)); raise
else:
    (OUT/"ui-result.json").write_text(json.dumps(result,indent=2,ensure_ascii=False))
    print("UI_RESULT "+json.dumps(result,ensure_ascii=False))
