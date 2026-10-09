#!/usr/bin/env python3
"""APK pagination, preview and bounded native SAF text-export verification."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import shlex
import tempfile
import tarfile
import zipfile

JAVA = r'''
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
public final class PagedContractTest {
 static int checks;
 static Class<?> renderer,block,format;
 static void ok(boolean value,String label){if(!value)throw new AssertionError(label);checks++;System.out.println("PAGED_PASS "+label);}
 interface Action{void run()throws Exception;}
 static void reject(Action action,String label)throws Exception{
  boolean failed=false;try{action.run();}catch(IOException|IllegalArgumentException e){failed=true;}ok(failed,label);
 }
 static Set<String> keys(String... s){return new LinkedHashSet<>(Arrays.asList(s));}
 static Object block(String note,String id,String text,byte[] image,String caption,boolean secret)throws Exception{
  return block.getConstructor(String.class,String.class,String.class,byte[].class,String.class,boolean.class)
   .newInstance(note,id,text,image,caption,secret);
 }
 @SuppressWarnings({"rawtypes","unchecked"})
 static Object render(List<Object> blocks,Set<String> selected,String kind)throws Exception{
  try{return renderer.getMethod("render",List.class,Set.class,format).invoke(null,blocks,selected,Enum.valueOf((Class)format,kind));}
  catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
 }
 static byte[] bytes(Object result)throws Exception{return(byte[])result.getClass().getMethod("bytes").invoke(result);}
 static int pages(Object result)throws Exception{return result.getClass().getField("pages").getInt(result);}
 static void write(File root,String name,Object result)throws Exception{
  AndroidCodecTest.save(new File(root,name),bytes(result));
 }
 static byte[] read(File file)throws IOException{
  try(InputStream in=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()){
   byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);return out.toByteArray();
  }
 }
 static void save(File file,byte[] bytes)throws IOException{
  try(OutputStream out=new FileOutputStream(file)){out.write(bytes);}
 }
 static byte[] withoutActualText(byte[] data)throws IOException{
  try(com.tom_roush.pdfbox.pdmodel.PDDocument doc=com.tom_roush.pdfbox.pdmodel.PDDocument.load(data)){
   int removed=0;
   for(com.tom_roush.pdfbox.pdmodel.PDPage page:doc.getPages()){
    com.tom_roush.pdfbox.pdfparser.PDFStreamParser parser=new com.tom_roush.pdfbox.pdfparser.PDFStreamParser(page);
    parser.parse();List<Object> tokens=parser.getTokens();
    for(Object token:tokens){
     if(token instanceof com.tom_roush.pdfbox.cos.COSDictionary){
      com.tom_roush.pdfbox.cos.COSDictionary props=(com.tom_roush.pdfbox.cos.COSDictionary)token;
      com.tom_roush.pdfbox.cos.COSName actual=com.tom_roush.pdfbox.cos.COSName.getPDFName("ActualText");
      if(props.containsKey(actual)){props.removeItem(actual);removed++;}
     }
    }
    com.tom_roush.pdfbox.pdmodel.common.PDStream replacement=new com.tom_roush.pdfbox.pdmodel.common.PDStream(doc);
    try(OutputStream output=replacement.createOutputStream()){
     new com.tom_roush.pdfbox.pdfwriter.ContentStreamWriter(output).writeTokens(tokens);
    }
    page.setContents(replacement);
   }
   if(removed==0)throw new AssertionError("ActualText removal control did not modify PDF");
   ByteArrayOutputStream out=new ByteArrayOutputStream();doc.save(out);return out.toByteArray();
  }
 }
 static void previewOk(boolean value,String label){if(!value)throw new AssertionError(label);System.out.println("PAGED_PREVIEW_PASS "+label);}
 static java.lang.reflect.Method privateMethod(Class<?> type,String name,Class<?>... args)throws Exception{
  for(Class<?> at=type;at!=null;at=at.getSuperclass()){
   try{java.lang.reflect.Method method=at.getDeclaredMethod(name,args);method.setAccessible(true);return method;}
   catch(NoSuchMethodException absent){}
  }
  throw new NoSuchMethodException(name);
 }
 static Object field(Object target,String name)throws Exception{
  for(Class<?> at=target.getClass();at!=null;at=at.getSuperclass()){
   try{java.lang.reflect.Field f=at.getDeclaredField(name);f.setAccessible(true);return f.get(target);}
   catch(NoSuchFieldException absent){}
  }
  throw new NoSuchFieldException(name);
 }
 static void collect(android.view.View view,List<android.widget.ImageView> images,List<android.widget.CheckBox> boxes){
  if(view instanceof android.widget.ImageView&&
     ((android.widget.ImageView)view).getDrawable() instanceof android.graphics.drawable.BitmapDrawable)
   images.add((android.widget.ImageView)view);
  if(view instanceof android.widget.CheckBox)boxes.add((android.widget.CheckBox)view);
  if(view instanceof android.view.ViewGroup){
   android.view.ViewGroup group=(android.view.ViewGroup)view;
   for(int i=0;i<group.getChildCount();i++)collect(group.getChildAt(i),images,boxes);
  }
 }
 static void onUi(android.app.Instrumentation inst,Action action)throws Exception{
  Throwable[] failure={null};
  inst.runOnMainSync(()->{try{action.run();}catch(Throwable e){failure[0]=e;}});
  if(failure[0]!=null)throw new AssertionError("preview UI failure",failure[0]);
 }
 static byte[] state(android.app.Activity activity)throws Exception{
  Object db=field(field(activity,"screen"),"db");
  return(byte[])privateMethod(db.getClass(),"exportState").invoke(db);
 }
 @SuppressWarnings("unchecked")
 static void previewUi(android.app.Instrumentation inst,File root)throws Exception{
  Class<?> activityClass=Class.forName("com.supercubegame.pockettodo.MainActivity");
  Method decoder=privateMethod(activityClass,"decodePagedPreview",android.content.Context.class,byte[].class,int.class);
  Method preview=privateMethod(activityClass,"previewShare",byte[][].class,int.class);
  android.content.Intent start=new android.content.Intent().setClassName(inst.getTargetContext(),
    activityClass.getName()).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK);
  android.app.Activity activity=inst.startActivitySync(start);inst.waitForIdleSync();
  byte[] before=state(activity);
  try{
   for(int format=1;format<=2;format++){
    final int selectedFormat=format;String suffix=format==1?"PDF":"PNG_ZIP";
    byte[] payload=read(new File(root,format==1?"paged.pdf":"paged.zip"));
    List<android.graphics.Bitmap> decoded=(List<android.graphics.Bitmap>)decoder.invoke(null,activity,payload,format);
    previewOk(decoded.size()==3,"decoded_actual_pages_"+suffix);
    boolean bounds=true,ink=true;
    for(android.graphics.Bitmap bitmap:decoded){
     bounds&=bitmap.getWidth()>0&&bitmap.getWidth()<=256&&bitmap.getHeight()>0&&bitmap.getHeight()<=256;
     boolean nonwhite=false;
     for(int y=0;y<bitmap.getHeight();y++)for(int x=0;x<bitmap.getWidth();x++)nonwhite|=bitmap.getPixel(x,y)!=0xffffffff;
     ink&=nonwhite;bitmap.recycle();
    }
    previewOk(bounds&&ink,"decoded_page_bounds_and_ink_"+suffix);
    boolean refused=false;
    try{decoder.invoke(null,activity,new byte[]{1,2,3,4},format);}
    catch(InvocationTargetException e){refused=e.getCause() instanceof IOException||e.getCause() instanceof IllegalArgumentException;}
    previewOk(refused,"corrupt_payload_rejected_"+suffix);
    refused=false;
    try{decoder.invoke(null,activity,read(new File(root,format==1?"paged.zip":"paged.pdf")),format);}
    catch(InvocationTargetException e){refused=e.getCause() instanceof IOException||e.getCause() instanceof IllegalArgumentException;}
    previewOk(refused,"wrong_format_rejected_"+suffix);
    final List<android.widget.ImageView> views=new ArrayList<>();
    final List<android.widget.CheckBox> boxes=new ArrayList<>();
    final android.app.AlertDialog[] dialog={null};
    android.content.Intent[] captured={null};int[] launches={0};
    android.app.Instrumentation.ActivityMonitor monitor=new android.app.Instrumentation.ActivityMonitor(){
     @Override public android.app.Instrumentation.ActivityResult onStartActivity(android.content.Intent intent){
      if(android.content.Intent.ACTION_CREATE_DOCUMENT.equals(intent.getAction())){
       captured[0]=new android.content.Intent(intent);launches[0]++;
       return new android.app.Instrumentation.ActivityResult(android.app.Activity.RESULT_CANCELED,null);
      }
      return null;
     }
    };
    inst.addMonitor(monitor);
    List<android.graphics.Bitmap> shown=new ArrayList<>();
    try{
     onUi(inst,()->{
      preview.invoke(activity,new byte[][]{before,payload},selectedFormat);
      List<android.app.AlertDialog> dialogs=(List<android.app.AlertDialog>)field(activity,"shareDialogs");
      if(dialogs.size()!=1){
       // Diagnostics only, never a retry: retain the original failed UI assertion.
       // previewShare intentionally catches decode/view exceptions for the user.
       // Re-run its decoder on the SAME main thread to expose a platform exception.
       Object screen=field(activity,"screen");
       System.out.println("PAGED_PREVIEW_DIAGNOSTIC format="+selectedFormat+
         " dialogs="+dialogs.size()+" destroyed="+activity.isDestroyed()+
         " finishing="+activity.isFinishing()+" busy="+field(screen,"busy")+
         " status="+((android.widget.TextView)field(screen,"status")).getText());
       List<android.graphics.Bitmap> probe=null;
       try{
        probe=(List<android.graphics.Bitmap>)decoder.invoke(null,activity,payload,selectedFormat);
        android.widget.LinearLayout body=new android.widget.LinearLayout(activity);
        for(android.graphics.Bitmap bitmap:probe){
         android.widget.ImageView image=new android.widget.ImageView(activity);
         image.setImageBitmap(bitmap);image.setAdjustViewBounds(true);body.addView(image);
        }
        System.out.println("PAGED_PREVIEW_DIAGNOSTIC same_thread_decode_and_views=PASS pages="+probe.size());
       }catch(Throwable failure){
        System.out.println("PAGED_PREVIEW_DIAGNOSTIC same_thread_decode_and_views=FAILED");
        failure.printStackTrace(System.out);
       }finally{if(probe!=null)for(android.graphics.Bitmap bitmap:probe)bitmap.recycle();}
       throw new AssertionError("one actual preview dialog; observed="+dialogs.size());
      }
      dialog[0]=dialogs.get(0);collect(dialog[0].getWindow().getDecorView(),views,boxes);
     });
     previewOk(views.size()==3,"actual_dialog_pages_"+suffix);
     for(android.widget.ImageView view:views)shown.add(((android.graphics.drawable.BitmapDrawable)view.getDrawable()).getBitmap());
     previewOk(boxes.size()==1&&!boxes.get(0).isChecked(),"unchecked_consent_"+suffix);
     onUi(inst,()->dialog[0].getButton(android.app.AlertDialog.BUTTON_POSITIVE).performClick());
     inst.waitForIdleSync();
     previewOk(launches[0]==0&&field(activity,"pendingShare")==null&&dialog[0].isShowing(),"unchecked_save_blocked_"+suffix);
     onUi(inst,()->{boxes.get(0).setChecked(true);dialog[0].getButton(android.app.AlertDialog.BUTTON_POSITIVE).performClick();});
     inst.waitForIdleSync();
     String mime=format==1?"application/pdf":"application/zip";
     String filename=format==1?"PocketTodo-notes.pdf":"PocketTodo-pages.zip";
     previewOk(launches[0]==1&&captured[0]!=null&&mime.equals(captured[0].getType())&&
       filename.equals(captured[0].getStringExtra(android.content.Intent.EXTRA_TITLE))&&
       captured[0].hasCategory(android.content.Intent.CATEGORY_OPENABLE),"saf_format_after_consent_"+suffix);
     previewOk(field(activity,"pendingShare")==null,"cancel_clears_ticket_"+suffix);
     previewOk(Arrays.equals(before,state(activity)),"preview_preserves_database_"+suffix);
     boolean recycled=true;for(android.graphics.Bitmap bitmap:shown)recycled&=bitmap.isRecycled();
     previewOk(recycled,"dialog_bitmaps_recycled_"+suffix);
    }finally{
     inst.removeMonitor(monitor);
     onUi(inst,()->{if(dialog[0]!=null)dialog[0].dismiss();});
    }
   }
   System.out.println("PAGED_PREVIEW_RESULT 22/22 PASS ACTUAL_DIALOG_AND_INTERCEPTED_SAF_NOT_PROVIDER_E2E");
  }finally{onUi(inst,activity::finish);inst.waitForIdleSync();}
 }
 public static void verify(String[] args,android.app.Instrumentation inst)throws Exception{
   File root=new File(args[0]);
   renderer=Class.forName("com.supercubegame.pockettodo.PagedNoteRenderer");
   block=Class.forName("com.supercubegame.pockettodo.PagedNoteRenderer$Block");
   format=Class.forName("com.supercubegame.pockettodo.PagedNoteRenderer$Format");
   ok(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args[1]),"actual_api");
   byte[] image=AndroidCodecTest.read(new File(root,"derived.png")),original=image.clone();
   Object picture=block("n","i",null,image,"CAPTION_END",false);
   Arrays.fill(image,(byte)0);
   StringBuilder text=new StringBuilder("BEGIN_SELECTED\n");
   for(int i=0;i<90;i++)text.append(String.format(java.util.Locale.ROOT,"ROW%03d selected text\n",i));
   text.append("END_SELECTED\n中文说明\nUNICODE_PAIR 文|⽂|文|⽂ END_PAIR");
   Object prose=block("n","t",text.toString(),null,"",false);
   Object hidden=block("n","p","PRIVATE_PAGED_SECRET",null,"",true);
   Object badPrivate=block("n","q",null,new byte[]{1,2,3},"PRIVATE_IMAGE_SECRET",true);
   Object unwanted=block("other","t","UNSELECTED_PAGED_SECRET",null,"",false);
   List<Object> input=new ArrayList<>(Arrays.asList(prose,picture,hidden,badPrivate,unwanted));
   for(String kind:new String[]{"PDF","PNG_ZIP"}){
    Object result=render(input,keys("n/i","n/t","n/p","n/q"),kind);
    int pageCount=pages(result);
    ok(pageCount>=3&&pageCount<=5,"multiple_pages_"+kind);
    write(root,kind.equals("PDF")?"paged.pdf":"paged.zip",result);
    if(kind.equals("PDF"))save(new File(root,"unmarked.pdf"),withoutActualText(bytes(result)));
    byte[] first=bytes(result);byte value=first[0];first[0]^=1;
    ok(bytes(result)[0]==value,"result_ownership_"+kind);
    Object filtered=render(Arrays.asList(prose,picture),keys("n/t","n/i"),kind);
    // PDF may contain timestamps; page pixels/text are compared independently below.
    ok(pages(filtered)==pageCount,"excluded_blocks_do_not_add_pages_"+kind);
    write(root,kind.equals("PDF")?"filtered.pdf":"filtered.zip",filtered);
    Object only=render(Arrays.asList(picture),keys("n/i"),kind);
    ok(pages(only)==1,"single_page_"+kind);
    write(root,kind.equals("PDF")?"picture.pdf":"picture.zip",only);
    reject(()->render(input,keys(),kind),"empty_selection_"+kind);
    reject(()->render(input,keys("missing/id"),kind),"unknown_selection_"+kind);
    reject(()->render(input,keys("n/p","n/q"),kind),"private_only_"+kind);
    reject(()->render(Arrays.asList(prose,prose),keys("n/t"),kind),"duplicate_identity_"+kind);
    Object broken=block("n","broken",null,new byte[]{1,2,3},"",false);
    reject(()->render(Arrays.asList(prose,broken),keys("n/t","n/broken"),kind),"selected_bad_image_"+kind);
    ok(pages(render(Arrays.asList(picture,broken),keys("n/i"),kind))==1,"unselected_bad_image_ignored_"+kind);
    Object over=block("n","large",null,AndroidCodecTest.read(new File(root,"over.png")),"",false);
    reject(()->render(Arrays.asList(over),keys("n/large"),kind),"source_pixel_budget_"+kind);
    Object invalid=block("n","invalid","bad\u0001",null,"",false);
    reject(()->render(Arrays.asList(invalid),keys("n/invalid"),kind),"invalid_text_"+kind);
    StringBuilder huge=new StringBuilder();for(int i=0;i<3000;i++)huge.append("line\n");
    Object tooMany=block("n","long",huge.toString(),null,"",false);
    reject(()->render(Arrays.asList(tooMany),keys("n/long"),kind),"page_limit_refuses_not_truncates_"+kind);
   }
   ok(Arrays.equals(original,AndroidCodecTest.read(new File(root,"derived.png"))),"source_file_unchanged");
   Object empty=block("n","empty","",null,"",false);
   reject(()->render(Arrays.asList(empty),keys("n/empty"),"PDF"),"blank_document_rejected");
   if(checks!=29)throw new AssertionError("coverage_count_"+checks);
   previewUi(inst,root);
   System.out.println("PAGED_RESULT 29/29 PASS BACKEND_NOT_NATIVE_UI_SAF_OR_RECEIVER");
 }
}
'''

RUNNER = r'''
package ci.paged;
import android.app.Instrumentation;
import android.os.Bundle;
import java.io.*;
public final class PagedInstrumentation extends Instrumentation {
 private Bundle args;
 @Override public void onCreate(Bundle value){super.onCreate(value);args=value;start();}
 @Override public void onStart(){
  ByteArrayOutputStream bytes=new ByteArrayOutputStream();
  PrintStream oldOut=System.out,oldErr=System.err;
  int code=0;
  try{
   PrintStream log=new PrintStream(bytes,true,"UTF-8");System.setOut(log);System.setErr(log);
   if(!getTargetContext().getPackageName().equals(args.getString("expectedPackage"))||
      android.os.Process.myUid()!=getTargetContext().getApplicationInfo().uid)
    throw new AssertionError("paged_target_identity");
   System.out.println("PAGED_TARGET "+getTargetContext().getPackageName()+" "+android.os.Process.myUid());
   if("diagnostic".equals(args.getString("mode")))throw new AssertionError("paged_diagnostic_sentinel");
   File root=new File(getTargetContext().getCacheDir(),args.getString("folder"));
   PagedContractTest.verify(new String[]{root.getAbsolutePath(),args.getString("expectedApi")},this);
   code=-1;
  }catch(Throwable e){System.err.println("PAGED_FAILED");e.printStackTrace(System.err);}
  finally{
   System.out.flush();System.err.flush();System.setOut(oldOut);System.setErr(oldErr);
   Bundle result=new Bundle();
   try{result.putString("stream",bytes.toString("UTF-8"));}catch(Exception e){throw new RuntimeException(e);}
   finish(code,result);
  }
 }
}
'''

LABELS = ["actual_api"] + [
    name+"_"+kind for kind in ("PDF","PNG_ZIP") for name in (
        "multiple_pages","result_ownership","excluded_blocks_do_not_add_pages","single_page",
        "empty_selection","unknown_selection","private_only","duplicate_identity",
        "selected_bad_image","unselected_bad_image_ignored","source_pixel_budget",
        "invalid_text","page_limit_refuses_not_truncates")
] + ["source_file_unchanged","blank_document_rejected"]

PREVIEW_LABELS=[name+"_"+kind for kind in ("PDF","PNG_ZIP") for name in (
    "decoded_actual_pages","decoded_page_bounds_and_ink","corrupt_payload_rejected","wrong_format_rejected",
    "actual_dialog_pages","unchecked_consent","unchecked_save_blocked","saf_format_after_consent",
    "cancel_clears_ticket","preview_preserves_database","dialog_bitmaps_recycled")]
PREVIEW_RESULT="22/22 PASS ACTUAL_DIALOG_AND_INTERCEPTED_SAF_NOT_PROVIDER_E2E"

def observe(text,package):
    labels=re.findall(r"^PAGED_PASS ([^\r\n]+)",text,re.M)
    targets=re.findall(r"(?:^|stream=)PAGED_TARGET (\S+) (\d+)",text,re.M)
    assert len(targets)==1 and targets[0][0]==package and int(targets[0][1])>=10000
    assert labels==LABELS
    assert re.findall(r"^PAGED_PREVIEW_PASS ([^\r\n]+)",text,re.M)==PREVIEW_LABELS
    assert re.findall(r"^PAGED_PREVIEW_RESULT ([^\r\n]+)",text,re.M)==[PREVIEW_RESULT]
    assert re.findall(r"^PAGED_RESULT ([^\r\n]+)",text,re.M)==[
        "29/29 PASS BACKEND_NOT_NATIVE_UI_SAF_OR_RECEIVER"]
    assert re.findall(r"^INSTRUMENTATION_CODE: (-?\d+)\s*$",text,re.M)==["-1"]
    assert not any(x in text for x in ("PAGED_FAILED","INSTRUMENTATION_FAILED","INSTRUMENTATION_ABORTED"))
    return labels

def matching_key(paths,expected,fingerprint):
    matches=[]
    for path in sorted(set(Path(p).resolve() for p in paths)):
        if path.is_file() and fingerprint(path)==expected:matches.append(path)
    assert len(matches)==1,"expected exactly one existing debug key matching product certificate; matches="+str(len(matches))
    return matches[0]

def debug_key(certificate):
    # CI may relocate Android preferences. Never create a key or trust a filename:
    # the existing certificate must match the actual product APK before any build.
    homes=[Path.home()/".android",Path.home()/".config"/".android"]
    for variable in ("ANDROID_USER_HOME","ANDROID_EMULATOR_HOME"):
        if os.environ.get(variable):homes.append(Path(os.environ[variable]))
    if os.environ.get("ANDROID_SDK_HOME"):homes.append(Path(os.environ["ANDROID_SDK_HOME"])/".android")
    paths=[p/"debug.keystore" for p in homes]
    temporary=Path(os.environ["RUNNER_TEMP"]).resolve()
    visited=0
    for current,dirs,files in os.walk(temporary,followlinks=False):
        visited+=1
        assert visited<=5000,"bounded CI debug key discovery exceeded directory budget"
        depth=len(Path(current).relative_to(temporary).parts)
        dirs[:]=[] if depth>=6 else [d for d in dirs if not (Path(current)/d).is_symlink()]
        if "debug.keystore" in files:paths.append(Path(current)/"debug.keystore")
    def fingerprint(path):
        # Standard disposable Android debug credential only; no release key access.
        p=subprocess.run(["keytool","-exportcert","-keystore",str(path),
                          "-alias","androiddebugkey","-storepass","android"],
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        return hashlib.sha256(p.stdout).hexdigest() if p.returncode==0 else None
    key=matching_key(paths,certificate,fingerprint)
    print("PAGED_DEBUG_KEY existing certificate match verified; no key generated",flush=True)
    return key

def paged_signing(certificate):
    """Select one signing mode. Stable mode never searches for debug credentials."""
    mode = os.environ.get("POCKET_STABLE_SIGNING")
    if mode is None:
        return {"mode": "disposable", "key": str(debug_key(certificate))}
    assert mode == "1", "PAGED_SIGNING_INVALID_MODE"
    import stat
    try:
        root = Path(os.environ["RUNNER_TEMP"]).resolve()
        folder = Path(os.environ["POCKET_SIGNING_DIR"])
        assert (folder.is_absolute() and folder.parent.resolve() == root and
                re.fullmatch(r"pocket-signing-(26|34)", folder.name) and
                not folder.is_symlink() and folder.is_dir())
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700
        key, config = folder / "preview.jks", folder / "credentials.json"
        for path in (key, config):
            assert not path.is_symlink() and path.is_file()
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert 0 < path.stat().st_size <= 1024 * 1024
        def unique(pairs):
            out = {}
            for name, value in pairs:
                assert name not in out
                out[name] = value
            return out
        values = json.loads(config.read_text(), object_pairs_hook=unique)
        assert set(values) == {"alias", "storePassword", "keyPassword", "certificate"}
        assert all(isinstance(v, str) and v and not any(c in v for c in "\r\n\0")
                   for v in values.values())
        assert re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", values["alias"])
        assert re.fullmatch(r"[0-9a-f]{64}", values["certificate"])
        assert values["certificate"] == certificate
        env = dict(os.environ, PAGED_STORE_PASSWORD=values["storePassword"])
        result = subprocess.run(
            ["keytool", "-exportcert", "-keystore", str(key), "-alias", values["alias"],
             "-storepass:env", "PAGED_STORE_PASSWORD"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=20, env=env)
        assert result.returncode == 0 and result.stdout
        assert hashlib.sha256(result.stdout).hexdigest() == certificate
    except Exception:
        # Decoder, filesystem, keytool and timeout details may contain credentials.
        raise AssertionError("PAGED_FIXED_SIGNING_INVALID_OR_MISMATCH; no fallback") from None
    print("PAGED_FIXED_KEY existing certificate match verified; no key generated", flush=True)
    return {"mode": "fixed", "key": str(key), "config": str(config),
            "certificate": certificate}


def paged_signing_dsl(signing):
    """The script contains paths and a public certificate digest, never passwords.
    Configure the *active* debug build type, including historical source which has
    no stablePreview config. No product source or dependency overlay is necessary.
    """
    if signing["mode"] == "disposable":
        return ("   dsl.signingConfigs.getByName('debug').storeFile = new File(" +
                json.dumps(signing["key"]) + ")\n")
    assert signing["mode"] == "fixed", "PAGED_SIGNING_INVALID_DSL_MODE"
    return (
        "   try {\n"
        "    def cfgFile = new File(" + json.dumps(signing["config"]) + ")\n"
        "    def keyFile = new File(" + json.dumps(signing["key"]) + ")\n"
        "    if (!cfgFile.isFile() || !keyFile.isFile()) { throw new IllegalStateException() }\n"
        "    def c = new groovy.json.JsonSlurper().parse(cfgFile)\n"
        "    if (c.keySet() != ['alias','storePassword','keyPassword','certificate'].toSet() ||\n"
        "        c.values().any { !(it instanceof String) || it.isEmpty() } ||\n"
        "        c.certificate != " + json.dumps(signing["certificate"]) + ") {\n"
        "      throw new IllegalStateException()\n"
        "    }\n"
        "    def s = dsl.signingConfigs.getByName('debug')\n"
        "    s.storeFile = keyFile\n"
        "    s.storePassword = c.storePassword\n"
        "    s.keyAlias = c.alias\n"
        "    s.keyPassword = c.keyPassword\n"
        "    dsl.buildTypes.getByName('debug').signingConfig = s\n"
        "   } catch (Exception ignored) {\n"
        "    throw new GradleException('Paged fixed signing unavailable; no fallback')\n"
        "   }\n")


def paged_signing_build(args, signing, timeout):
    """Retain build output, redacting credential values before printing/raising."""
    if signing["mode"] == "disposable":
        return run(args, timeout=timeout)
    assert signing["mode"] == "fixed", "PAGED_SIGNING_INVALID_BUILD_MODE"
    # Revalidate immediately before either build; never expose parser exceptions.
    checked = paged_signing(signing["certificate"])
    assert checked == signing, "PAGED_SIGNING_CHANGED_BEFORE_BUILD"
    try:
        values = json.loads(Path(signing["config"]).read_text())
        secrets = [values["storePassword"], values["keyPassword"]]
    except Exception:
        raise AssertionError("PAGED_SIGNING_CREDENTIAL_READ_FAILED") from None
    def redacted(output):
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output = output or ""
        variants = set()
        for value in secrets:
            variants.update((value, json.dumps(value)[1:-1], repr(value)[1:-1]))
        for value in sorted(variants, key=len, reverse=True):
            output = output.replace(value, "<redacted-signing-credential>")
        return output
    try:
        p = subprocess.run(list(map(str, args)), text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        output = redacted(exc.output)
        print(output, flush=True)
        raise RuntimeError("Paged signing build timed out\n" + output[-6000:]) from None
    except Exception:
        raise RuntimeError("Paged signing build could not start") from None
    output = redacted(p.stdout)
    print(output, flush=True)
    if p.returncode:
        raise RuntimeError("Paged signing build failed; exit=" + str(p.returncode) +
                           "\n" + output[-6000:])
    return output


def paged_signing_contract(select, dsl, build):
    """Host subprocess doubles exercise real Python paths, not Android or Gradle."""
    import contextlib
    import io
    import secrets
    from unittest.mock import patch
    labels = []
    def need(value, label):
        assert value, label
        labels.append(label)
    with tempfile.TemporaryDirectory(prefix="paged-signing-controls-") as temporary:
        root = Path(temporary)
        folder = root / "pocket-signing-26"
        folder.mkdir(mode=0o700)
        key, config = folder / "preview.jks", folder / "credentials.json"
        key.write_bytes(b"host-only-keytool-double")
        key.chmod(0o600)
        cert_bytes = b"host-only-certificate-double"
        cert = hashlib.sha256(cert_bytes).hexdigest()
        password = secrets.token_hex(18) + "'\"\\"
        keypass = secrets.token_hex(18)
        values = dict(alias="non-default-alias", storePassword=password,
                      keyPassword=keypass, certificate=cert)
        def reset():
            config.write_text(json.dumps(values))
            config.chmod(0o600)
        reset()
        env = dict(RUNNER_TEMP=str(root), POCKET_SIGNING_DIR=str(folder),
                   POCKET_STABLE_SIGNING="1")
        calls = []
        def tool(args, **kwargs):
            calls.append((args, kwargs))
            assert args[0] == "keytool"
            assert password not in str(args) and keypass not in str(args)
            assert args[-2:] == ["-storepass:env", "PAGED_STORE_PASSWORD"]
            assert kwargs["env"]["PAGED_STORE_PASSWORD"] == password
            assert kwargs["timeout"] == 20
            return subprocess.CompletedProcess(args, 0, cert_bytes, b"")
        def forbidden(*args, **kwargs):
            raise AssertionError("debug fallback must not execute")
        with patch.dict(os.environ, env, clear=True):
            with patch.dict(select.__globals__, debug_key=forbidden):
                with patch.object(subprocess, "run", tool), contextlib.redirect_stdout(io.StringIO()) as log:
                    signing = select(cert)
                need(signing == dict(mode="fixed", key=str(key), config=str(config),
                                     certificate=cert) and len(calls) == 1, "fixed_exact_key_certificate")
                script = dsl(signing)
                need(password not in script + log.getvalue() and keypass not in script + log.getvalue()
                     and password not in repr(signing), "no_credentials_in_script_or_selection")
                for line in ("s.storeFile = keyFile", "s.storePassword = c.storePassword",
                             "s.keyAlias = c.alias", "s.keyPassword = c.keyPassword",
                             "dsl.buildTypes.getByName('debug').signingConfig = s"):
                    need(line in script, "dsl_" + line.split(" = ")[0])
                need("c.certificate != " + json.dumps(cert) in script and
                     "catch (Exception ignored)" in script, "dsl_certificate_guard_generic_failure")
                def refuse(label, action):
                    caught = None
                    with patch.object(subprocess, "run", tool), contextlib.redirect_stdout(io.StringIO()) as capture:
                        try:
                            action()
                        except Exception as exc:
                            caught = exc
                    need(type(caught) is AssertionError and
                         "PAGED_" in str(caught) and "debug fallback" not in str(caught) and
                         password not in str(caught) + capture.getvalue() and
                         keypass not in str(caught) + capture.getvalue(), label)
                for mode in ("", "0", "true", " 1"):
                    with patch.dict(os.environ, POCKET_STABLE_SIGNING=mode):
                        refuse("invalid_mode_" + repr(mode), lambda: select(cert))
                with patch.dict(os.environ, POCKET_SIGNING_DIR=str(root / "elsewhere")):
                    refuse("invalid_directory", lambda: select(cert))
                folder.chmod(0o755)
                refuse("public_directory", lambda: select(cert))
                folder.chmod(0o700)
                for path in (key, config):
                    path.chmod(0o644)
                    refuse("public_" + path.name, lambda: select(cert))
                    path.chmod(0o600)
                    saved = path.read_bytes()
                    path.unlink()
                    refuse("missing_" + path.name, lambda: select(cert))
                    target = root / ("other-" + path.name)
                    target.write_bytes(saved); target.chmod(0o600)
                    path.symlink_to(target)
                    refuse("symlink_" + path.name, lambda: select(cert))
                    path.unlink(); path.write_bytes(saved); path.chmod(0o600)
                variants = [
                    "{", json.dumps(dict(values, extra="x")),
                    json.dumps(dict(values, storePassword="")),
                    json.dumps(dict(values, keyPassword="bad\nvalue")),
                    json.dumps(dict(values, alias="bad/alias")),
                    json.dumps(dict(values, certificate="b" * 64)),
                    '{"alias":"a","alias":"b"}',
                ]
                for index, text in enumerate(variants):
                    config.write_text(text)
                    refuse("invalid_credentials_" + str(index), lambda: select(cert))
                reset()
                refuse("product_certificate_mismatch", lambda: select("c" * 64))
                for response in (subprocess.CompletedProcess([], 1, password.encode(), keypass.encode()),
                                 subprocess.CompletedProcess([], 0, b"wrong-cert", b"")):
                    def bad_tool(*args, **kwargs):
                        return response
                    with patch.object(subprocess, "run", bad_tool):
                        try:
                            select(cert)
                        except AssertionError as exc:
                            need(str(exc) == "PAGED_FIXED_SIGNING_INVALID_OR_MISMATCH; no fallback",
                                 "keytool_rejected_" + str(response.returncode))
                        else:
                            raise AssertionError("invalid keytool result accepted")
                def leaking_tool(*args, **kwargs):
                    raise subprocess.TimeoutExpired(["keytool"], 20, output=password.encode())
                with patch.object(subprocess, "run", leaking_tool):
                    try:
                        select(cert)
                    except AssertionError as exc:
                        need(password not in str(exc) and exc.__suppress_context__, "keytool_timeout_no_leak")
                    else:
                        raise AssertionError("keytool timeout accepted")
                for outcome in ("success", "failure", "timeout", "startup"):
                    commands = []
                    def compiler(args, **kwargs):
                        if args[0] == "keytool":
                            return tool(args, **kwargs)
                        commands.append((args, kwargs))
                        raw = "OUTPUT_SENTINEL\n" + password + "\n" + keypass + "\n" + json.dumps(password)
                        if outcome == "timeout":
                            raise subprocess.TimeoutExpired(args, kwargs["timeout"], output=raw.encode())
                        if outcome == "startup":
                            raise OSError(raw)
                        return subprocess.CompletedProcess(args, int(outcome == "failure"), raw)
                    caught = None
                    with patch.object(subprocess, "run", compiler), contextlib.redirect_stdout(io.StringIO()) as capture:
                        try:
                            result = build(["gradle", "--no-daemon", "assembleDebug"], signing, 360)
                        except Exception as exc:
                            caught = exc
                    text = capture.getvalue() + (str(caught) if caught else result)
                    need(password not in text and keypass not in text and json.dumps(password)[1:-1] not in text
                         and len(commands) == 1 and commands[0][1]["timeout"] == 360
                         and (caught is None) == (outcome == "success"),
                         "build_" + outcome + "_one_attempt_redacted")
                    if outcome != "startup":
                        need("OUTPUT_SENTINEL" in text, "build_original_output_" + outcome)
            with patch.dict(os.environ, {}, clear=True):
                with patch.dict(select.__globals__, debug_key=lambda certificate: key):
                    selected = select(cert)
                need(selected == dict(mode="disposable", key=str(key)), "disposable_existing_selector")
                need(dsl(selected) == "   dsl.signingConfigs.getByName('debug').storeFile = new File(" +
                     json.dumps(str(key)) + ")\n", "disposable_original_dsl")
                observed = []
                with patch.dict(build.__globals__, run=lambda args, timeout: observed.append((args, timeout)) or "ok"):
                    need(build(["gradle"], selected, 300) == "ok" and observed == [(["gradle"], 300)],
                         "disposable_original_runner_budget")
    return labels


def paged_signing_selftest():
    import ast
    import inspect
    labels = paged_signing_contract(paged_signing, paged_signing_dsl, paged_signing_build)
    assert len(labels) == 41, "paged signing host control population changed"
    mutations = (
        (paged_signing, 'assert mode == "1"', 'assert True'),
        (paged_signing, 'values["certificate"] == certificate', 'True'),
        (paged_signing, 'hashlib.sha256(result.stdout).hexdigest() == certificate', 'True'),
        (paged_signing, 'not path.is_symlink() and path.is_file()', 'path.is_file()'),
        (paged_signing_dsl, "    s.keyPassword = c.keyPassword", "    // key password omitted"),
        (paged_signing_dsl, "    dsl.buildTypes.getByName('debug').signingConfig = s", "    // active signing omitted"),
        (paged_signing_build, 'output.replace(value, "<redacted-signing-credential>")', 'output'),
    )
    killed = 0
    for function, old, new in mutations:
        source = inspect.getsource(function)
        assert source.count(old) == 1, "paged signing mutation anchor drift"
        namespace = dict(globals())
        exec(compile(source.replace(old, new), "<paged-signing-mutant>", "exec"), namespace)
        implementations = [namespace[f.__name__] for f in (paged_signing, paged_signing_dsl, paged_signing_build)]
        try:
            paged_signing_contract(*implementations)
        except AssertionError:
            killed += 1
        else:
            raise AssertionError("paged signing mutant survived: " + function.__name__)
    # Inspect actual callers, not a duplicate list of anticipated invocations.
    assert killed == 7, "paged signing mutation population incomplete"
    for function, task, budget in ((instrumentation, "assembleDebugAndroidTest", 300),
                                   (apk_size_comparison, "assembleDebug", 360)):
        tree = ast.parse(inspect.getsource(function))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        assert sum(n.func.id == "paged_signing" for n in calls) == 1
        assert sum(n.func.id == "paged_signing_dsl" for n in calls) == 1
        assert not any(n.func.id == "debug_key" for n in calls)
        builds = [n for n in calls if n.func.id == "paged_signing_build"]
        assert len(builds) == 1 and len(builds[0].args) == 2
        assert isinstance(builds[0].args[1], ast.Name) and builds[0].args[1].id == "signing"
        assert builds[0].args[0].elts[-1].value == task
        assert [(k.arg, k.value.value) for k in builds[0].keywords] == [("timeout", budget)]
    print("PAGED_SIGNING_HOST " + str(len(labels)) + " controls " + str(killed) +
          " implementation mutants; 2 caller wiring checks PASS NOT_GRADLE_OR_ANDROID", flush=True)

def instrumentation(folder,prefix,gate):
    """Normal target-app startup initializes fonts; never patch hidden framework APIs."""
    from verify_schema3 import certificate, require_registration
    root=Path(__file__).resolve().parents[1]
    apps=list((root/"build/outputs/apk/debug").glob("*.apk"))
    tests=list((root/"build/outputs/apk/androidTest/debug").glob("*.apk"))
    assert len(apps)==len(tests)==1
    app,test=apps[0],tests[0]
    before,saved=app.read_bytes(),test.read_bytes()
    cert=certificate(app,gate)
    assert cert==certificate(test,gate)
    require_registration(prefix[0],gate,"paged-before","V12DeviceTest")
    signing=paged_signing(cert)
    nonce="paged-contract-"+os.environ["GITHUB_RUN_ID"]
    cache="cache/"+nonce
    run([*prefix,"shell","run-as",gate.PKG,"mkdir",cache])
    for name in ("derived.png","over.png"):
        data=(folder/name).read_bytes()
        command="run-as "+shlex.quote(gate.PKG)+" sh -c "+shlex.quote("umask 077; cat > "+cache+"/"+name)
        subprocess.run([*prefix,"shell",command],input=data,check=True,timeout=30)
        assert subprocess.check_output([*prefix,"exec-out","run-as",gate.PKG,"cat",cache+"/"+name],timeout=30)==data
    def installed_app():
        output=run([*prefix,"shell","pm","path",gate.PKG])
        paths=re.findall(r"^package:(\S+)\s*$",output,re.M)
        assert len(paths)==1,"ambiguous installed product APK"
        return subprocess.check_output([*prefix,"exec-out","cat",paths[0]],timeout=30)
    assert installed_app()==before
    with tempfile.TemporaryDirectory(prefix="paged-runner-",dir=root/"build") as temp:
        work=Path(temp);src=work/"src";src.mkdir()
        # Test-only sources; product classes remain solely in the installed APK.
        contract="package ci.paged;\n"+JAVA.replace("AndroidCodecTest.read(","read(").replace("AndroidCodecTest.save(","save(")
        (src/"PagedContractTest.java").write_text(contract,encoding="utf-8")
        (src/"PagedInstrumentation.java").write_text(RUNNER,encoding="utf-8")
        init=work/"runner.gradle"
        init.write_text("gradle.beforeProject { p ->\n"
            " p.plugins.withId('com.android.application') {\n"
            "  p.androidComponents.finalizeDsl { dsl ->\n"
            "   dsl.defaultConfig.testInstrumentationRunner = 'ci.paged.PagedInstrumentation'\n"
            "   dsl.sourceSets.getByName('androidTest').java.srcDir "+json.dumps(str(src))+"\n"
            +paged_signing_dsl(signing)+
            "  }\n }\n}\n")
        backup=work/"default-test.apk";backup.write_bytes(saved)
        try:
            paged_signing_build(["gradle","--no-daemon","--console=plain","-I",init,"assembleDebugAndroidTest"],signing,timeout=300)
            assert app.read_bytes()==before,"test build changed product APK"
            assert certificate(test,gate)==cert,"paged test signing certificate differs"
            run([*prefix,"install","-r","-t",test],timeout=120)
            registration=run([*prefix,"shell","pm","list","instrumentation"])
            rows=re.findall(r"^instrumentation:(\S+) \(target=([^)]+)\)\s*$",registration,re.M)
            assert [r for r in rows if r[0].startswith(gate.PKG+".test/")]==[
                (gate.PKG+".test/ci.paged.PagedInstrumentation",gate.PKG)]
            args=[*prefix,"shell","am","instrument","-w","-r","-e","expectedPackage",gate.PKG,
                  "-e","expectedApi",str(gate.API),"-e","folder",nonce]
            component=gate.PKG+".test/ci.paged.PagedInstrumentation"
            diagnostic=run([*args,"-e","mode","diagnostic",component],timeout=60)
            assert "java.lang.AssertionError: paged_diagnostic_sentinel" in diagnostic
            assert "PAGED_FAILED" in diagnostic and "INSTRUMENTATION_CODE: 0" in diagnostic
            try:observe(diagnostic,gate.PKG)
            except AssertionError:pass
            else:raise AssertionError("failed instrumentation accepted")
            output=run([*args,component],timeout=180)
            labels=observe(output,gate.PKG)
            for stem in ("paged","filtered","picture"):
                for ext in ("pdf","zip"):
                    name=stem+"."+ext
                    data=subprocess.check_output([*prefix,"exec-out","run-as",gate.PKG,"cat",cache+"/"+name],timeout=30)
                    assert 0<len(data)<=16777216
                    (folder/name).write_bytes(data)
            data=subprocess.check_output([*prefix,"exec-out","run-as",gate.PKG,"cat",cache+"/unmarked.pdf"],timeout=30)
            assert 0<len(data)<=16777216
            (folder/"unmarked.pdf").write_bytes(data)
            assert installed_app()==before
        finally:
            assert backup.read_bytes()==saved
            run([*prefix,"install","-r","-t",backup],timeout=120)
            test.write_bytes(saved)
            require_registration(prefix[0],gate,"paged-restored","V12DeviceTest")
            assert app.read_bytes()==before and test.read_bytes()==saved
    return labels,{"runtime":"TARGET_APP_INSTRUMENTATION","diagnostic_failure_rejected":True,
                   "product_apk_sha256":hashlib.sha256(before).hexdigest(),
                   "product_apk_bytes":len(before),
                   "installed_product_readback":"EXACT_BEFORE_AND_AFTER",
                   "default_test_restored":"EXACT_BYTES_AND_REGISTERED_RUNNER","certificate":cert}

HOST = r'''
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import javax.imageio.ImageIO;
public final class PagedHostCheck {
 static void need(boolean v,String s){if(!v)throw new AssertionError(s);}
 public static void main(String[] a)throws Exception{
  BufferedImage image=ImageIO.read(new File(a[0]));
  need(image!=null&&image.getWidth()==595&&image.getHeight()==842,"page_dimensions");
  need(image.getRGB(0,0)==0xffffffff&&image.getRGB(594,841)==0xffffffff,"white_page");
  if(a[1].equals("picture")){
   int[] expected={0xff0a141e,0xff000000,0xff000000,0xff0d1a27,0xff112233,0xff000000,0xff000000,0xff000000,0xff183048,0xff19324b,0xff000000,0xff000000};
   int[] actual=image.getRGB(36,36,4,3,null,0,4);
   System.out.println("PAGED_PIXEL_FILE "+new File(a[0]).getName());
   System.out.println("PAGED_PIXEL_EXPECTED "+Arrays.toString(expected));
   System.out.println("PAGED_PIXEL_ACTUAL "+Arrays.toString(actual));
   for(int y=34;y<42;y++)System.out.println("PAGED_PIXEL_NEIGHBOR "+y+" "+Arrays.toString(image.getRGB(34,y,8,1,null,0,8)));
   need(Arrays.equals(actual,expected),"current_only_exact_crop_mask");
  }else{
   int count=0;for(int y=36;y<806;y++)for(int x=36;x<559;x++)if(image.getRGB(x,y)!=0xffffffff)count++;
   need(count>0,"page_not_empty");
  }
  System.out.println("PAGED_HOST_PASS");
 }
}
'''

def run(args,timeout=90):
    p=subprocess.run(list(map(str,args)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    print(p.stdout,flush=True)
    if p.returncode:raise RuntimeError("Paged command failed: "+str(args)+"\n"+p.stdout[-6000:])
    return p.stdout

def text_check(text):
    assert not any(s in text for s in ("PRIVATE_PAGED_SECRET","PRIVATE_IMAGE_SECRET","UNSELECTED_PAGED_SECRET"))
    assert text.count("BEGIN_SELECTED")==text.count("END_SELECTED")==text.count("CAPTION_END")==1
    rows=re.findall(r"ROW\d{3}",text)
    assert rows==["ROW%03d"%i for i in range(90)],"PDF row loss/duplication/order"
    assert text.index("BEGIN_SELECTED")<text.index("ROW000")<text.index("ROW089")<text.index("END_SELECTED")<text.index("CAPTION_END")
    assert "中文说明" in text.replace(" ","").replace("\n",""),"Chinese PDF text missing"
    assert text.count("UNICODE_PAIR 文|⽂|文|⽂ END_PAIR")==1,"PDF original Unicode pair changed"
    assert re.findall(r"(?m)(?:^|\f)(ROW\d{3})",text)==rows,"PDF hard line boundaries lost"

def pdf_text_diagnostic(text):
    """Only synthetic CI fixture output. Preserve code points, not a guessed cause."""
    tail=text[-800:]
    return {"characters":len(text),"tail":tail,
            "non_ascii":[{"offset":i,"codepoint":"U+%04X"%ord(c)} for i,c in enumerate(text) if ord(c)>127][:80],
            "expected":[ "U+%04X"%ord(c) for c in "中文说明"],
            "form_feeds":text.count("\f")}

def selftest():
    paged_signing_selftest()
    dependency_setup_selftest()
    format_button_selftest()
    native_receipt_selftest()
    derived_receipt_selftest()
    good="BEGIN_SELECTED\n"+"\n".join("ROW%03d"%i for i in range(90))+"\nEND_SELECTED\n中文说明\nUNICODE_PAIR 文|⽂|文|⽂ END_PAIR\nCAPTION_END"
    text_check(good)
    text_check(good.replace("ROW049\nROW050","ROW049\n\n\fROW050"))
    bad=(good.replace("ROW050",""),good.replace("ROW050","ROW049"),good+"PRIVATE_PAGED_SECRET",
         good.replace("中文说明",""),good.replace("ROW000","ROW999"),
         good.replace("文|⽂|文|⽂","⽂|⽂|⽂|⽂"),good.replace("文|⽂|文|⽂","文|文|文|文"),
         good.replace("文|⽂|文|⽂","⽂|文|⽂|文"),good.replace("文|⽂|文|⽂","文|⽂"),
         good.replace("UNICODE_PAIR 文|⽂|文|⽂ END_PAIR",""),
         good.replace("文|⽂|文|⽂","文|�|文|�"),good+"\nUNICODE_PAIR 文|⽂|文|⽂ END_PAIR",
         good.replace("ROW049\nROW050","ROW049ROW050"))
    assert len(bad)==13
    for value in bad:
        assert value!=good,"text mutation did not change fixture"
        try:text_check(value)
        except AssertionError:continue
        raise AssertionError("PDF observer accepted corrupt text")
    print("PAGED_TEXT_OBSERVER 2 positive 13 negatives PASS NOT_PDF_EXECUTION",flush=True)
    for value in ("中文说明","中文说\u660e","\ufffd\ufffd","\u2f42文说明","中文\f说明",""):
        diagnostic=pdf_text_diagnostic(value)
        assert diagnostic["tail"]==value and diagnostic["characters"]==len(value)
        assert diagnostic["non_ascii"]==[{"offset":i,"codepoint":"U+%04X"%ord(c)} for i,c in enumerate(value) if ord(c)>127]
    assert len(pdf_text_diagnostic("中"*1000)["tail"])==800
    assert len(pdf_text_diagnostic("中"*1000)["non_ascii"])==80
    print("PAGED_TEXT_DIAGNOSTIC 8/8 PASS NOT_PDF_EXECUTION",flush=True)
    good="INSTRUMENTATION_RESULT: stream=PAGED_TARGET test.package 10123\n"
    good+="".join("PAGED_PASS "+label+"\n" for label in LABELS)
    good+="".join("PAGED_PREVIEW_PASS "+label+"\n" for label in PREVIEW_LABELS)
    good+="PAGED_PREVIEW_RESULT "+PREVIEW_RESULT+"\n"
    marker="PAGED_RESULT 29/29 PASS BACKEND_NOT_NATIVE_UI_SAF_OR_RECEIVER\n"
    good+=marker+"INSTRUMENTATION_CODE: -1\n"
    assert observe(good,"test.package")==LABELS
    invalid=[good.replace("test.package","other"),good.replace("10123","2000"),
             good.replace(marker,""),good+marker,good.replace("CODE: -1","CODE: 0"),
             good.replace("INSTRUMENTATION_CODE: -1\n",""),good+"PAGED_FAILED\n",
             good+"INSTRUMENTATION_FAILED\n",good.replace("PAGED_PASS actual_api","PAGED_PASS unrelated")]
    invalid += [good.replace("PAGED_PASS "+label+"\n","",1) for label in LABELS]
    invalid += [good.replace("PAGED_PREVIEW_PASS "+label+"\n","",1) for label in PREVIEW_LABELS]
    invalid += [good.replace("PAGED_PREVIEW_RESULT "+PREVIEW_RESULT+"\n","",1),
                good.replace(PREVIEW_RESULT,"21/21 PASS ACTUAL_DIALOG_AND_INTERCEPTED_SAF_NOT_PROVIDER_E2E"),
                good+"PAGED_PREVIEW_PASS "+PREVIEW_LABELS[0]+"\n"]
    for bad in invalid:
        try:observe(bad,"test.package")
        except AssertionError:continue
        raise AssertionError("incomplete paged instrumentation accepted")
    print("PAGED_RUNNER_OBSERVER 1 positive "+str(len(invalid))+" negatives PASS NOT_DEVICE_EXECUTION",flush=True)
    with tempfile.TemporaryDirectory(prefix="paged-key-controls-") as directory:
        a,b=Path(directory)/"a",Path(directory)/"b"
        a.write_bytes(b"test-certificate-a");b.write_bytes(b"test-certificate-b")
        fingerprint=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        expected=fingerprint(b)
        assert matching_key([a,b],expected,fingerprint)==b.resolve()
        assert matching_key([b,b],expected,fingerprint)==b.resolve()
        for paths,cert,reader in (([],expected,fingerprint),([a],expected,fingerprint),
            ([a,b],"wrong",fingerprint),([a,b],expected,lambda p:None),
            ([a,b],expected,lambda p:expected)):
            try:matching_key(paths,cert,reader)
            except AssertionError:continue
            raise AssertionError("unverified or ambiguous debug key accepted")
    print("PAGED_KEY_OBSERVER 2 positive 5 negatives PASS NOT_CI_KEYSTORE_EXECUTION",flush=True)

def rasterizer_controls(folder):
    """Independent raw PDF, not the app renderer. Prove 1:1 sampling before
    using a rasterizer as the exact-pixel oracle. Splash can resample even with
    Interpolate=false; Cairo must pass the same unmodified Java checker.
    """
    colors=[0x0a141e,0,0,0x0d1a27,0x112233,0,0,0,0x183048,0x19324b,0,0]
    def sample(name,pixels,x=36,blank=False):
        image=b"".join(c.to_bytes(3,"big") for c in pixels)
        content=b"" if blank else ("q 4 0 0 3 %d 803 cm /Im1 Do Q\n"%x).encode("ascii")
        def stream(header,data):
            return b"<< "+header+b" /Length "+str(len(data)).encode()+b" >>\nstream\n"+data+b"\nendstream"
        objects=[b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>",
            stream(b"/Type /XObject /Subtype /Image /Width 4 /Height 3 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Interpolate false",image),
            stream(b"",content)]
        data=bytearray(b"%PDF-1.4\n");offsets=[0]
        for i,obj in enumerate(objects,1):
            offsets.append(len(data));data.extend(("%d 0 obj\n"%i).encode()+obj+b"\nendobj\n")
        start=len(data);data.extend(b"xref\n0 6\n0000000000 65535 f \n")
        for offset in offsets[1:]:data.extend(("%010d 00000 n \n"%offset).encode())
        data.extend(("trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"%start).encode())
        path=folder/("oracle-"+name+".pdf");path.write_bytes(data);return path
    good=sample("good",colors)
    changed=colors.copy();changed[1]=0x010101;assert changed!=colors
    samples=[good,sample("changed",changed),sample("shifted",colors,x=37),sample("blank",colors,blank=True)]
    for index,pdf in enumerate(samples):
        prefix=pdf.with_suffix("")
        run(["pdftocairo","-r","72","-png",pdf,prefix])
        p=subprocess.run(["java","-Djava.awt.headless=true","-cp",str(folder),
            "PagedHostCheck",str(prefix)+"-1.png","picture"],capture_output=True,text=True,timeout=30)
        if index==0:
            assert p.returncode==0,p.stdout+p.stderr
        else:
            assert p.returncode!=0 and "java.lang.AssertionError: current_only_exact_crop_mask" in p.stderr,p.stdout+p.stderr
    print("PAGED_RASTER_ORACLE 1 positive 3 negatives PASS INDEPENDENT_PDF_NOT_PRODUCT",flush=True)
    return {"renderer":"pdftocairo","dpi":72,"positive":1,"negative":3,"scope":"INDEPENDENT_RAW_PDF_SAME_EXACT_PIXEL_CHECKER"}

def apk_size_comparison(gate):
    """Build the exact pre-dependency source with the same SDK and existing key.
    This baseline APK is never installed or delivered. No signing key is created.
    """
    from verify_schema3 import certificate
    root=Path(__file__).resolve().parents[1]
    apps=list((root/"build/outputs/apk/debug").glob("*.apk"));assert len(apps)==1
    app=apps[0];current=app.read_bytes();cert=certificate(app,gate);signing=paged_signing(cert)
    baseline="452969cf2f053bb8c527d3fb2dc3bf1fbf4afe21"
    run(["git","-C",root,"fetch","--no-tags","--depth=1","origin",baseline],timeout=120)
    with tempfile.TemporaryDirectory(prefix="paged-size-",dir=root/"build") as temp:
        work=Path(temp);archive=work/"baseline.tar";project=work/"baseline";project.mkdir()
        with archive.open("wb") as out:
            subprocess.run(["git","-C",str(root),"archive",baseline],stdout=out,check=True,timeout=60)
        with tarfile.open(archive) as files:files.extractall(project,filter="data")
        init=work/"signing.gradle"
        init.write_text("gradle.beforeProject { p -> p.plugins.withId('com.android.application') { "
            "p.androidComponents.finalizeDsl { dsl ->\n"
            +paged_signing_dsl(signing)+" } } }\n")
        paged_signing_build(["gradle","--no-daemon","--console=plain","-p",project,"-I",init,"assembleDebug"],signing,timeout=360)
        old=list((project/"build/outputs/apk/debug").glob("*.apk"));assert len(old)==1
        assert certificate(old[0],gate)==cert,"size baseline certificate mismatch"
        previous=old[0].read_bytes()
        assert app.read_bytes()==current,"isolated size build changed product APK"
    result={"baseline_commit":baseline,"baseline_bytes":len(previous),"current_bytes":len(current),
            "delta_bytes":len(current)-len(previous),"baseline_sha256":hashlib.sha256(previous).hexdigest(),
            "current_sha256":hashlib.sha256(current).hexdigest(),"baseline_installed":False}
    print("PAGED_APK_SIZE "+json.dumps(result),flush=True)
    return result

def verify(folder,classes,android,prefix,remote,gate):
    """Called inside the existing codec job; failures propagate to its exit status."""
    selftest()
    # Independent PDF parser/rasterizer. Install only in disposable CI when absent.
    dependencies = ensure_poppler()
    labels,identity=instrumentation(folder,prefix,gate)
    host=folder/"PagedHostCheck.java";host.write_text(HOST,encoding="utf-8")
    run(["javac","-encoding","UTF-8","-d",folder,host])
    oracle=rasterizer_controls(folder)
    def check_image(file,mode):
        return run(["java","-Djava.awt.headless=true","-cp",folder,"PagedHostCheck",file,mode])
    evidence={}
    for stem in ("paged","filtered","picture"):
        info=run(["pdfinfo",folder/(stem+".pdf")])
        match=re.search(r"^Pages:\s+(\d+)",info,re.M);assert match,info
        pages=int(match[1]);assert pages==1 if stem=="picture" else 3<=pages<=5
        run(["pdftotext","-enc","UTF-8",folder/(stem+".pdf"),folder/(stem+".txt")])
        text=(folder/(stem+".txt")).read_text()
        # Emit before assertions, so an independent text failure is diagnosable.
        # Do not normalize compatibility glyphs or remove the Chinese assertion.
        print("PAGED_PDF_TEXT "+json.dumps({"stem":stem,**pdf_text_diagnostic(text)},ensure_ascii=True),flush=True)
        run(["pdffonts",folder/(stem+".pdf")])
        if stem!="picture":text_check(text)
        else:assert text.count("CAPTION_END")==1 and "ROW" not in text
        run(["pdftocairo","-r","72","-png",folder/(stem+".pdf"),folder/(stem+"-pdf")])
        rendered=sorted(folder.glob(stem+"-pdf-*.png"));assert len(rendered)==pages
        if stem=="picture":
            run(["pdfimages","-list",folder/(stem+".pdf")])
            run(["pdftoppm","-r","72","-png",folder/(stem+".pdf"),folder/"picture-splash"])
            # Diagnose both representations before either exact comparison aborts.
            with zipfile.ZipFile(folder/(stem+".zip")) as archive:
                reference=folder/"picture-png-diagnostic.png"
                reference.write_bytes(archive.read("pages/page-001.png"))
            for candidate in (reference,rendered[0],folder/"picture-splash-1.png"):
                p=subprocess.run(["java","-Djava.awt.headless=true","-cp",str(folder),
                    "PagedHostCheck",str(candidate),"picture"],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
                print("PAGED_PIXEL_DIAGNOSTIC exit="+str(p.returncode)+"\n"+p.stdout,flush=True)
            # Retain the original mandatory comparison and failure propagation below.
        for file in rendered:check_image(file,"picture" if stem=="picture" else "text")
        with zipfile.ZipFile(folder/(stem+".zip")) as archive:
            names=archive.namelist()
            assert names==["pages/page-%03d.png"%i for i in range(1,pages+1)],"PNG page set/order"
            assert sum(e.file_size for e in archive.infolist())<=16777216
            for i,name in enumerate(names):
                data=archive.read(name);assert b"PRIVATE_GPS_SECRET" not in data
                file=folder/("%s-png-%03d.png"%(stem,i+1));file.write_bytes(data)
                check_image(file,"picture" if stem=="picture" else "text")
        evidence[stem]={"pages":pages,"pdf_sha256":hashlib.sha256((folder/(stem+".pdf")).read_bytes()).hexdigest(),
                        "zip_sha256":hashlib.sha256((folder/(stem+".zip")).read_bytes()).hexdigest()}
    assert (folder/"paged.txt").read_bytes()==(folder/"filtered.txt").read_bytes(),"excluded content affected PDF text"
    assert (folder/"paged.zip").read_bytes()==(folder/"filtered.zip").read_bytes(),"excluded content affected PNG pages"
    for a,b in zip(sorted(folder.glob("paged-pdf-*.png")),sorted(folder.glob("filtered-pdf-*.png"))):
        assert a.read_bytes()==b.read_bytes(),"excluded content affected PDF pixels"
    # A file-level mutation, not a recompiled product mutant: remove only original
    # text annotations. It must reveal glyph ambiguity without changing any pixel.
    run(["pdftotext","-enc","UTF-8",folder/"unmarked.pdf",folder/"unmarked.txt"])
    try:text_check((folder/"unmarked.txt").read_text())
    except AssertionError as error:
        assert str(error) in ("Chinese PDF text missing","PDF original Unicode pair changed"),"unrelated mutation failure"
    else:raise AssertionError("ActualText removal did not expose exact-Unicode failure")
    run(["pdftocairo","-r","72","-png",folder/"unmarked.pdf",folder/"unmarked-pdf"])
    original=sorted(folder.glob("paged-pdf-*.png"));unmarked=sorted(folder.glob("unmarked-pdf-*.png"))
    assert len(original)==len(unmarked)
    for a,b in zip(original,unmarked):
        assert a.read_bytes()==b.read_bytes(),"ActualText changed visible PDF pixels"
    size=apk_size_comparison(gate)
    report={"commit":os.environ["GITHUB_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],"api":gate.API,
            "status":"PASS","scope":"APK_PAGED_BACKEND_POPPLER_AND_JDK_NOT_UI_SAF_RECEIVER",
            "checks":29,"labels":labels,"independent_outputs":evidence,"text_observer_negative_controls":13,
            "actualtext_removal_control":"REJECTED_WITH_IDENTICAL_PIXELS","apk_size":size,
            "rasterizer_oracle":oracle,"dependency_setup":dependencies,
            "preview_ui":{"checks":len(PREVIEW_LABELS),"labels":PREVIEW_LABELS,
                          "scope":"ACTUAL_DIALOG_AND_INTERCEPTED_SAF_NOT_PROVIDER_E2E"},
            "instrumentation":identity,"release_ready":False}
    target=gate.ROOT/"native-ui" if hasattr(gate,"ROOT") else Path("native-ui")
    target.mkdir(exist_ok=True)
    (target/"paged-result.json").write_text(json.dumps(report,indent=2)+"\n")
    print("PAGED_EXPORT_EVIDENCE "+json.dumps(report),flush=True)
    # Compose after the existing native and Markdown suites, once only. Their
    # failures still abort; the new native result is written into uploaded receipts.
    previous_native=gate.verify_native_ui
    def native_and_paged(adb):
        previous_native(adb)
        native_paged_ui(adb,gate)
    gate.verify_native_ui=native_and_paged
    return report

NATIVE_STEPS=(
    "private_excluded_and_empty_selection","format_picker_selected",
    "actual_page_preview","unchecked_save_refused","picker_cancel_preserves_state",
    "real_saf_output","independent_text_page","save_preserves_state",
    "same_revision_privacy_change","stale_publication_refused",
    "stale_refusal_preserves_state","fixture_restored")
NATIVE_LABELS=[step+"_"+kind for kind in ("PDF","PNG_ZIP") for step in NATIVE_STEPS]
NATIVE_SCOPE="NATIVE_SINGLE_NOTE_TEXT_PDF_PNG_SAF_CANCEL_STALE_NOT_PROCESS_DEATH_OR_RECEIVER"

def format_button(current,title,package):
    # Android's Button all-caps transformation affects accessibility text on
    # both tested APIs. Match the neutral button's identity as well as its
    # whole label; never relax every text selector or accept a substring.
    expected="格式："+title
    matches=[n for n in current if
             n.get("resource-id")=="android:id/button3" and
             n.get("class")=="android.widget.Button" and
             n.get("package")==package and n.get("enabled")=="true" and
             n.get("clickable")=="true" and
             n.get("text") in (expected,expected.upper())]
    assert len(matches)<=1,"ambiguous native format button"
    return matches[0] if matches else None

def format_button_selftest():
    good={"resource-id":"android:id/button3","class":"android.widget.Button",
          "package":"fixture.app","enabled":"true","clickable":"true","text":"格式：Markdown"}
    positives=0
    for title in ("Markdown","PDF","分段PNG图片包"):
        for text in ("格式："+title,("格式："+title).upper()):
            candidate=dict(good,text=text)
            assert format_button([candidate],title,"fixture.app") is candidate
            positives+=1
    invalid=[dict(good,text="格式：PDF"),dict(good,text="格式：Markdown图片包"),
             dict(good,text="旧格式：Markdown"),dict(good,text="格式：MARKDOWN "),
             dict(good,**{"resource-id":"android:id/button1"}),
             dict(good,**{"class":"android.widget.TextView"}),
             dict(good,package="other.app"),dict(good,enabled="false"),
             dict(good,clickable="false"),{}]
    assert format_button([],"Markdown","fixture.app") is None
    for candidate in invalid:
        assert format_button([candidate],"Markdown","fixture.app") is None
    try:format_button([good,dict(good,text="格式：MARKDOWN")],"Markdown","fixture.app")
    except AssertionError:pass
    else:raise AssertionError("duplicate format button accepted")
    print("PAGED_FORMAT_BUTTON_OBSERVER "+str(positives)+" positives 12 negatives PASS NOT_DEVICE_EXECUTION",flush=True)

def native_receipt(value,api,source,run_id):
    return (isinstance(value,dict) and value.get("status")=="PASS" and
            type(value.get("api")) is int and value["api"]==api and
            value.get("commit")==source and value.get("run_id")==run_id and
            value.get("scope")==NATIVE_SCOPE and value.get("labels")==NATIVE_LABELS and
            type(value.get("checks")) is int and value["checks"]==24 and
            value.get("release_ready") is False and
            derived_receipt(value.get("derived"),api,source,run_id))

def native_receipt_selftest():
    import copy
    good={"status":"PASS","api":26,"commit":"source","run_id":"run",
          "scope":NATIVE_SCOPE,"labels":NATIVE_LABELS[:],"checks":24,"release_ready":False,"derived":derived_sample()}
    assert native_receipt(good,26,"source","run")
    invalid=[None,{},dict(good,api=34),dict(good,api=True),dict(good,commit="old"),
             dict(good,run_id="old"),dict(good,status="FAIL"),dict(good,checks=23),
             dict(good,release_ready=True),dict(good,scope="backend"),
             dict(good,labels=list(reversed(NATIVE_LABELS))),dict(good,derived=None)]
    for i in range(24):
        bad=copy.deepcopy(good);del bad["labels"][i];bad["checks"]-=1;invalid.append(bad)
        bad=copy.deepcopy(good);bad["labels"][i]="unrelated";invalid.append(bad)
    for bad in invalid:
        assert not native_receipt(bad,26,"source","run"),"native paged receipt accepted incomplete evidence"
    print("PAGED_NATIVE_OBSERVER 1 positive "+str(len(invalid))+" negatives PASS NOT_DEVICE_EXECUTION",flush=True)

NATIVE_PAGE_CHECK=r'''
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.io.File;
public class NativeTextPage {
 static void check(BufferedImage page){
  if(page==null||page.getWidth()!=595||page.getHeight()!=842)throw new AssertionError("page dimensions");
  int ink=0;
  for(int y=0;y<842;y++)for(int x=0;x<595;x++){
   int pixel=page.getRGB(x,y);
   if(pixel!=0xffffffff){
    // Short single-line fixture only: an accidentally exported image or extra
    // text below this region cannot be hidden behind a nonblank-page assertion.
    if(x<34||x>=200||y<34||y>=65)throw new AssertionError("unselected content on text-only page");
    if((pixel>>>24)!=255)throw new AssertionError("transparent text page");
    ink++;
   }
  }
  if(ink==0)throw new AssertionError("blank text page");
 }
 static BufferedImage fixture(){
  BufferedImage page=new BufferedImage(595,842,BufferedImage.TYPE_INT_ARGB);
  for(int y=0;y<842;y++)for(int x=0;x<595;x++)page.setRGB(x,y,0xffffffff);
  return page;
 }
 public static void main(String[] args)throws Exception{
  if(args[0].equals("--selftest")){
   BufferedImage good=fixture();good.setRGB(36,40,0xff000000);check(good);
   BufferedImage blank=fixture(),extra=fixture(),alpha=fixture();
   extra.setRGB(36,40,0xff000000);extra.setRGB(300,200,0xff000000);
   alpha.setRGB(36,40,0x80000000);
   int failures=0;
   for(BufferedImage bad:new BufferedImage[]{blank,extra,alpha,new BufferedImage(1,1,2)}){
    try{check(bad);}catch(AssertionError expected){failures++;continue;}
    throw new AssertionError("text page negative control accepted");
   }
   if(failures!=4)throw new AssertionError("text page control count");
   System.out.println("NATIVE_TEXT_PAGE_OBSERVER 1 positive 4 negatives PASS NOT_DEVICE_EXECUTION");return;
  }
  check(ImageIO.read(new File(args[0])));
  System.out.println("NATIVE_TEXT_PAGE_PASS");
 }
}
'''

def native_paged_ui(adb,gate):
    """Real touch selection and DocumentsUI save. No reflected product methods.
    Uses the already-accepted synthetic note, media and external-writer fixture.
    PNG checks layout/nonblank only, not OCR; no receiver or process-loss claim.
    """
    import io
    import sqlite3
    import time
    import xml.etree.ElementTree as ET
    from verify_schema3 import share_ui_observe,cancel_share_picker
    out=Path("native-ui");path=out/"native-result.json"
    parent=json.loads(path.read_text())
    source,run_id=os.environ["GITHUB_SHA"],os.environ["GITHUB_RUN_ID"]
    assert share_ui_observe(parent.get("markdown_ui"),gate.API,source,run_id)["status"]=="PASS"
    result={"status":"FAIL","api":gate.API,"commit":source,"run_id":run_id,
            "scope":NATIVE_SCOPE,"labels":[],"checks":0,"release_ready":False,"outputs":{}}
    prefix=[str(adb),"-s",gate.SERIAL];serial=0
    def command(*args,binary=False):
        return subprocess.check_output(prefix+list(args),text=not binary,stderr=subprocess.PIPE,timeout=40)
    def shell(*args):return command("shell",*args)
    def nodes():
        shell("uiautomator","dump","/sdcard/paged-share-window.xml")
        return list(ET.fromstring(shell("cat","/sdcard/paged-share-window.xml")).iter("node"))
    def find(**attrs):
        deadline=time.monotonic()+20;current=[]
        while time.monotonic()<deadline:
            current=nodes()
            for n in current:
                if all(n.get(k)==v for k,v in attrs.items()):return n
            time.sleep(.25)
        raise AssertionError("native paged missing "+repr(attrs)+" actual="+repr([n.attrib for n in current]))
    def click(n):
        assert n.get("enabled")=="true","disabled native paged control"
        x1,y1,x2,y2=map(int,re.findall(r"\d+",n.get("bounds")))
        assert x2>x1 and y2>y1
        shell("input","tap",str((x1+x2)//2),str((y1+y2)//2))
    def tap(text):click(find(text=text))
    def find_format(title):
        deadline=time.monotonic()+20;current=[]
        while time.monotonic()<deadline:
            current=nodes()
            selected=format_button(current,title,gate.PKG)
            if selected is not None:return selected
            time.sleep(.25)
        raise AssertionError("native format button missing "+repr(title)+" actual="+repr([n.attrib for n in current]))
    def stop():
        from verify_process_control import stop_verified
        return stop_verified(adb,gate.SERIAL,gate.PKG)
    def start():
        shell("am","start","-W","-n",gate.PKG+"/com.supercubegame.pockettodo.MainActivity")
        find(**{"content-desc":"v12-status","text":"已保存到本机"})
    def state():
        nonlocal serial
        serial+=1;local=out/("paged-state-"+str(serial)+".db")
        local.write_bytes(command("exec-out","run-as",gate.PKG,"cat","databases/pocket-v12.db",binary=True))
        if "pocket-v12.db-wal" in shell("run-as",gate.PKG,"ls","databases").splitlines():
            Path(str(local)+"-wal").write_bytes(command("exec-out","run-as",gate.PKG,"cat","databases/pocket-v12.db-wal",binary=True))
        with sqlite3.connect(local) as db:
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            data={t:db.execute('SELECT * FROM "'+t+'" ORDER BY rowid').fetchall() for t in tables}
            titles=dict(db.execute("SELECT id,title FROM activities"))
        media={}
        for name in shell("run-as",gate.PKG,"ls","files/media").splitlines():
            assert re.fullmatch(r"[0-9a-f]{64}",name)
            raw=command("exec-out","run-as",gate.PKG,"cat","files/media/"+name,binary=True)
            media[name]=hashlib.sha256(raw).hexdigest();assert media[name]==name
        return data,media,titles
    def ok(condition,step,kind):
        label=step+"_"+kind
        assert condition,label
        assert NATIVE_LABELS[len(result["labels"])]==label,"native paged check order"
        result["labels"].append(label);print("PAGED_NATIVE_PASS "+label,flush=True)
    filename=None
    def paths():return shell("find","/sdcard/Download","-type","f","-name",filename).splitlines()
    def preserve_output(tag):
        found=paths()
        if found:
            assert found==["/sdcard/Download/"+filename]
            destination="/sdcard/Download/paged-"+tag+"-"+filename
            assert not shell("find","/sdcard/Download","-type","f","-name",destination.rsplit("/",1)[1]).splitlines()
            shell("mv",found[0],destination)
    def open_preview(title):
        tap("导出笔记");tap(note_label);find(text="勾选内容（私有项已排除）")
        click(find_format("Markdown"));tap(title);tap("1. 文字：Second edited");tap("生成预览");find(text=title+"预览")
    def save_picker():
        for attempt in range(8):
            found=[n for n in nodes() if n.get("text")=="我已核对内容与图片，可保存此包"]
            if found:
                n=found[0];bounds=list(map(int,re.findall(r"\d+",n.get("bounds"))))
                if bounds[2]>bounds[0] and bounds[3]>bounds[1]:
                    assert n.get("checked")=="false";click(n);break
            shell("input","swipe","160","440","160","190","350")
        else:raise AssertionError("native paged consent unreachable")
        tap("选择保存位置")
        assert find(text=filename).get("package") in ("com.android.documentsui","com.google.android.documentsui")
        assert find(text="SAVE").get("package") in ("com.android.documentsui","com.google.android.documentsui")
    def external(value,previous):
        remote="/data/user/0/"+gate.PKG+"/cache/share-writer.jar"
        raw=command("exec-out","run-as",gate.PKG,"cat",remote,binary=True)
        assert hashlib.sha256(raw).hexdigest()==parent["markdown_ui"]["external_helper"]["sha256"]
        output=shell("run-as",gate.PKG,"env","CLASSPATH="+remote,"app_process","/system/bin",
                     "ShareExternalWriter","/data/user/0/"+gate.PKG+"/databases/pocket-v12.db",
                     note,text_row[1],str(value),str(previous))
        assert output.splitlines()==["EXTERNAL_WRITER_STARTED","EXTERNAL_PRIVACY_WRITE_ONE_ROW"],output
    try:
        assert os.environ.get("GITHUB_ACTIONS")=="true" and shell("getprop","ro.kernel.qemu").strip()=="1"
        stop();baseline=state();data,media,titles=baseline
        derivatives=[r for r in data["blocks"] if r[8] is not None];assert len(derivatives)==1
        note=derivatives[0][0]
        texts=[r for r in data["blocks"] if r[0]==note and r[3]=="TEXT"]
        assert len(texts)==1 and texts[0][4]=="Second edited" and texts[0][7]==0
        text_row=texts[0]
        assert any(r[0]==note and r[7]==1 and r[6]=="PRIVATE_SHARE_SENTINEL" for r in data["blocks"])
        note_label=next(str(i+1)+". "+titles[r[1]]+" / "+r[2] for i,r in enumerate(data["notes"]) if r[0]==note)
        java=out/"NativeTextPage.java";java.write_text(NATIVE_PAGE_CHECK)
        run(["javac","-d",out,java])
        run(["java","-Djava.awt.headless=true","-cp",out,"NativeTextPage","--selftest"])
        for kind,title,filename in (("PDF","PDF","PocketTodo-notes.pdf"),("PNG_ZIP","分段PNG图片包","PocketTodo-pages.zip")):
            assert not paths(),"preexisting paged output"
            start();tap("导出笔记");tap(note_label);find(text="勾选内容（私有项已排除）")
            choices=[n for n in nodes() if n.get("class")=="android.widget.CheckedTextView"]
            ok([n.get("text") for n in choices]==["1. 文字：Second edited","2. 图片："] and
               all(n.get("checked")=="false" for n in choices),"private_excluded_and_empty_selection",kind)
            click(find_format("Markdown"));find(text="选择导出格式");tap(title)
            ok(find_format(title) is not None,"format_picker_selected",kind)
            tap("1. 文字：Second edited");tap("生成预览");find(text=title+"预览")
            ok(find(**{"content-desc":"导出第1页"}) is not None and find(text="第 1 / 1 页") is not None,
               "actual_page_preview",kind)
            tap("选择保存位置")
            ok(find(text=title+"预览") is not None and not any("documentsui" in n.get("package","") for n in nodes()),
               "unchecked_save_refused",kind)
            save_picker();trace=[]
            cancel_share_picker(nodes,lambda:shell("input","keyevent","KEYCODE_BACK"),gate.PKG,trace)
            stop();ok(not paths() and state()==baseline,"picker_cancel_preserves_state",kind)
            start();open_preview(title);save_picker();tap("SAVE")
            find(**{"content-desc":"v12-status","text":title+"已保存，逐字节回读一致"})
            found=paths();assert found==["/sdcard/Download/"+filename],repr(found)
            raw=command("exec-out","cat",found[0],binary=True)
            ok(0<len(raw)<=16777216,"real_saf_output",kind)
            artifact=out/("native-"+filename);artifact.write_bytes(raw)
            if kind=="PDF":
                assert re.findall(r"^Pages:\s+(\d+)",run(["pdfinfo",artifact]),re.M)==["1"]
                extracted=out/"native-paged.txt";run(["pdftotext","-enc","UTF-8",artifact,extracted])
                assert extracted.read_text().strip()=="Second edited","unexpected PDF content"
                image_prefix=out/"native-pdf-text"
                run(["pdftocairo","-r","72","-png","-singlefile",artifact,image_prefix])
                page=Path(str(image_prefix)+".png")
            else:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    assert archive.namelist()==["pages/page-001.png"]
                    assert sum(x.file_size for x in archive.infolist())<=16777216
                    page=out/"native-png-text.png";page.write_bytes(archive.read("pages/page-001.png"))
            verified=run(["java","-Djava.awt.headless=true","-cp",out,"NativeTextPage",page])
            ok(verified.strip()=="NATIVE_TEXT_PAGE_PASS","independent_text_page",kind)
            result["outputs"][kind]={"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
                "pdf_text":"EXACT" if kind=="PDF" else "NOT_OCR_TESTED","page":"SINGLE_NONBLANK_TEXT_REGION_NO_IMAGE"}
            stop();ok(state()==baseline,"save_preserves_state",kind);preserve_output("accepted")
            start();open_preview(title);save_picker();external(1,0)
            changed=state();expected=list(text_row);expected[7]=1
            ok(changed[0]["blocks"]==[tuple(expected) if r==text_row else r for r in data["blocks"]] and
               all(changed[0][t]==data[t] for t in data if t!="blocks") and changed[1:]==baseline[1:],
               "same_revision_privacy_change",kind)
            tap("SAVE")
            find(**{"content-desc":"v12-status","text":"导出未完成：预览过期或保存失败；本机笔记未改。目标可能留有空文件或部分文件，请检查"})
            found=paths()
            ok(not found or (found==["/sdcard/Download/"+filename] and command("exec-out","cat",found[0],binary=True)==b""),
               "stale_publication_refused",kind)
            stop();ok(state()==changed,"stale_refusal_preserves_state",kind)
            external(0,1);ok(state()==baseline,"fixture_restored",kind);preserve_output("stale-empty")
        def set_filename(value):
            nonlocal filename
            filename=value
        result["derived"]=native_derived_exports(adb,gate,parent,baseline,state,stop,start,tap,find,
            nodes,click,find_format,save_picker,command,shell,note_label,derivatives[0],set_filename)
        result["checks"]=len(result["labels"]);result["status"]="PASS"
        assert native_receipt(result,gate.API,source,run_id),"native paged coverage incomplete"
    except Exception as failure:
        result["error"]=repr(failure);parent["status"]="FAIL"
        try:
            screenshot=command("exec-out","screencap","-p",binary=True)
            (out/"paged-native-failure.png").write_bytes(screenshot)
        except Exception as diagnostic:result["screenshot_error"]=repr(diagnostic)
        raise
    finally:
        result["checks"]=len(result["labels"]);parent["paged_ui"]=result
        path.write_text(json.dumps(parent,ensure_ascii=False,indent=2))
        codec_path=out/"codec-result.json"
        codec=json.loads(codec_path.read_text());codec["paged_native_ui"]=result
        codec_path.write_text(json.dumps(codec,ensure_ascii=False,indent=2))
        print("PAGED_NATIVE_RESULT "+json.dumps(result,ensure_ascii=False),flush=True)

DERIVED_PAGE_CHECK=r'''
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
import java.io.File;
public class NativeDerivedPage {
 static final int RED=0xffdc4628,BLUE=0xff235ad2,BLACK=0xff000000,WHITE=0xffffffff;
 static void need(boolean b,String s){if(!b)throw new AssertionError(s);}
 static int expected(int x,int y,int[] c,int[] m){
  int sx=x+c[0],sy=y+c[1];
  return sx>=m[0]&&sx<m[2]&&sy>=m[1]&&sy<m[3]?BLACK:sx<640?RED:BLUE;
 }
 static void check(BufferedImage page,BufferedImage derivative,int[] c,int[] m){
  need(page!=null&&page.getWidth()==595&&page.getHeight()==842,"page dimensions");
  need(derivative!=null&&derivative.getWidth()==c[2]-c[0]&&derivative.getHeight()==c[3]-c[1],"crop dimensions");
  int sw=derivative.getWidth(),sh=derivative.getHeight();
  need(c[0]>=316&&c[0]<=324&&c[1]>=156&&c[1]<=164&&c[2]>=956&&c[2]<=964&&c[3]>=476&&c[3]<=484,"UI crop fixture");
  need(m[0]>=636&&m[0]<=644&&m[1]>=234&&m[1]<=246&&m[2]>=796&&m[2]<=804&&m[3]>=394&&m[3]<=406,"UI mask fixture");
  for(int y=0;y<sh;y++)for(int x=0;x<sw;x++)
   need(derivative.getRGB(x,y)==expected(x,y,c,m),"actual stored derivative pixel");
  int w=523,h=(int)Math.floor(sh*523.0/sw),red=0,blue=0,black=0;
  for(int y=0;y<842;y++)for(int x=0;x<595;x++){
   int actual=page.getRGB(x,y);need((actual>>>24)==255,"export alpha");
   if(x<36||x>=36+w||y<36||y>=36+h){
    need(actual==WHITE,"extra content outside selected image");continue;
   }
   double sx=(x-36+.5)*sw/w+c[0],sy=(y-36+.5)*sh/h+c[1];
   // Independently test solid interiors. A three-source-pixel guard isolates
   // renderer interpolation at the image/color/mask edges, not mask interiors.
   if(sx<c[0]+3||sx>c[2]-3||sy<c[1]+3||sy>c[3]-3||
      Math.abs(sx-640)<3||Math.abs(sx-m[0])<3||Math.abs(sx-m[2])<3||
      Math.abs(sy-m[1])<3||Math.abs(sy-m[3])<3)continue;
   int e=sx>=m[0]&&sx<m[2]&&sy>=m[1]&&sy<m[3]?BLACK:sx<640?RED:BLUE;
   need(actual==e,"export crop or opaque mask differs");
   if(e==RED)red++;else if(e==BLUE)blue++;else black++;
  }
  need(red>10000&&blue>10000&&black>10000,"fixture must exercise both colors and opaque mask");
 }
 static BufferedImage derivative(int[] c,int[] m){
  BufferedImage b=new BufferedImage(c[2]-c[0],c[3]-c[1],2);
  for(int y=0;y<b.getHeight();y++)for(int x=0;x<b.getWidth();x++)b.setRGB(x,y,expected(x,y,c,m));
  return b;
 }
 static BufferedImage page(int[] c,int[] m){
  BufferedImage b=new BufferedImage(595,842,2);
  int sw=c[2]-c[0],sh=c[3]-c[1],h=(int)Math.floor(sh*523.0/sw);
  for(int y=0;y<842;y++)for(int x=0;x<595;x++)
   b.setRGB(x,y,x>=36&&x<559&&y>=36&&y<36+h?
    expected((int)((x-36+.5)*sw/523),(int)((y-36+.5)*sh/h),c,m):WHITE);
  return b;
 }
 public static void main(String[] a)throws Exception{
  if(a[0].equals("--selftest")){
   int[] c={320,160,960,480},m={640,238,800,402};
   check(page(c,m),derivative(c,m),c,m);int refused=0;
   for(int i=0;i<8;i++){
    BufferedImage p=page(c,m),d=derivative(c,m);
    if(i==0)p.setRGB(330,150,BLUE); // removed interior redaction
    if(i==1)p.setRGB(100,80,BLUE); // wrong crop/source, away from interpolation guards
    if(i==2)p.setRGB(500,600,BLACK); // leaked extra text/image
    if(i==3)p.setRGB(330,150,0x80000000);
    if(i==4)d.setRGB(350,100,BLUE);
    if(i==5)p=new BufferedImage(594,842,2);
    if(i==6)d=new BufferedImage(1280,640,2); // origin substituted
    if(i==7)p.setRGB(330,150,0xff010101); // even almost-black is not opaque exact black
    try{check(p,d,c,m);}catch(AssertionError e){refused++;continue;}
    throw new AssertionError("derived observer accepted mutant "+i);
   }
   need(refused==8,"negative controls");
   System.out.println("DERIVED_PAGE_CONTROLS 1 positive 8 negatives");return;
  }
  need(a.length==10,"geometry required");
  int[] c=new int[4],m=new int[4];
  for(int i=0;i<4;i++){c[i]=Integer.parseInt(a[i+2]);m[i]=Integer.parseInt(a[i+6]);}
  check(ImageIO.read(new File(a[0])),ImageIO.read(new File(a[1])),c,m);
  System.out.println("DERIVED_PAGE_PASS EXACT_INTERIORS_AND_STORED_IMAGE");
 }
}
'''


def native_derived_exports(adb,gate,parent,baseline,state,stop,start,tap,find,
                           nodes,click,find_format,save_picker,command,shell,
                           note_label,derivative,set_filename):
    """Actual UI-created crop/mask, exported via DocumentsUI; no DB writes."""
    import io
    record={"status":"FAIL","scope":"NATIVE_DERIVED_IMAGE_SAF_NOT_RECEIVER",
            "commit":os.environ["GITHUB_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],
            "api":gate.API,"outputs":{},"release_ready":False}
    parent["derived_paged_ui"]=record
    out=Path("native-ui")
    geometry=parent["derivative_geometry"]
    crops=[g["observed_crop"] for g in geometry if g.get("source")==[1280,640] and "observed_crop" in g]
    masks=[g["observed_mask"] for g in geometry if g.get("source")==[1280,640] and "observed_mask" in g]
    assert len(crops)==len(masks)==1,"exact prior UI geometry required"
    crop,mask=crops[0],masks[0]
    assert derivative[3]=="IMAGE" and derivative[7]==0 and derivative[5]!=derivative[8]
    def private(asset):
        assert re.fullmatch(r"[0-9a-f]{64}",asset)
        b=command("exec-out","run-as",gate.PKG,"cat","files/media/"+asset,binary=True)
        assert hashlib.sha256(b).hexdigest()==asset
        return b
    current=private(derivative[5]);origin=private(derivative[8])
    assert current!=origin
    source=out/"export-current-derived.png";source.write_bytes(current)
    java=out/"NativeDerivedPage.java";java.write_text(DERIVED_PAGE_CHECK)
    run(["javac","-d",out,java])
    assert run(["java","-Djava.awt.headless=true","-cp",out,"NativeDerivedPage","--selftest"]).strip()=="DERIVED_PAGE_CONTROLS 1 positive 8 negatives"
    try:
        for kind,title,filename in (("PDF","PDF","PocketTodo-notes.pdf"),("PNG_ZIP","分段PNG图片包","PocketTodo-pages.zip")):
            set_filename(filename)
            assert not shell("find","/sdcard/Download","-type","f","-name",filename).splitlines()
            start();tap("导出笔记");tap(note_label);find(text="勾选内容（私有项已排除）")
            choices=[n for n in nodes() if n.get("class")=="android.widget.CheckedTextView"]
            assert [n.get("text") for n in choices]==["1. 文字：Second edited","2. 图片："]
            assert all(n.get("checked")=="false" for n in choices)
            click(find_format("Markdown"));tap(title);tap("2. 图片：");tap("生成预览")
            find(text=title+"预览");find(text="第 1 / 1 页");find(**{"content-desc":"导出第1页"})
            save_picker();tap("SAVE")
            find(**{"content-desc":"v12-status","text":title+"已保存，逐字节回读一致"})
            assert shell("find","/sdcard/Download","-type","f","-name",filename).splitlines()==["/sdcard/Download/"+filename]
            raw=command("exec-out","cat","/sdcard/Download/"+filename,binary=True)
            assert 0<len(raw)<=16777216
            artifact=out/("derived-"+filename);artifact.write_bytes(raw)
            if kind=="PDF":
                assert re.findall(r"^Pages:\s+(\d+)",run(["pdfinfo",artifact]),re.M)==["1"]
                text=out/"derived-export.txt";run(["pdftotext","-enc","UTF-8",artifact,text])
                assert not text.read_text().strip(),"unselected/private text leaked"
                prefix=out/"derived-pdf";run(["pdftocairo","-r","72","-png","-singlefile",artifact,prefix])
                page=Path(str(prefix)+".png")
            else:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    assert z.namelist()==["pages/page-001.png"]
                    assert sum(e.file_size for e in z.infolist())<=16777216
                    page=out/"derived-png.png";page.write_bytes(z.read("pages/page-001.png"))
            proof=run(["java","-Djava.awt.headless=true","-cp",out,"NativeDerivedPage",page,source,*map(str,crop+mask)])
            assert proof.strip()=="DERIVED_PAGE_PASS EXACT_INTERIORS_AND_STORED_IMAGE"
            stop();assert state()==baseline
            assert private(derivative[5])==current and private(derivative[8])==origin
            record["outputs"][kind]={"status":"PASS","pages":1,"bytes":len(raw),
                "sha256":hashlib.sha256(raw).hexdigest(),"current_asset":derivative[5],
                "original_asset":derivative[8],"crop":crop,"mask":mask,
                "pixels":"EXACT_OPAQUE_INTERIORS_EDGE_INTERPOLATION_NOT_ASSERTED",
                "state":"ALL_TABLES_AND_ALL_MEDIA_UNCHANGED"}
        assert set(record["outputs"])=={"PDF","PNG_ZIP"}
        record["status"]="PASS"
        return record
    except Exception as exc:
        record["error"]=repr(exc)
        raise
    finally:
        print("DERIVED_PAGED_RESULT "+json.dumps(record),flush=True)


def derived_receipt(value,api,source,run_id):
    if not isinstance(value,dict):return False
    if not (value.get("status")=="PASS" and value.get("scope")=="NATIVE_DERIVED_IMAGE_SAF_NOT_RECEIVER" and
        type(value.get("api")) is int and value["api"]==api and value.get("commit")==source and
        value.get("run_id")==run_id and value.get("release_ready") is False):return False
    outputs=value.get("outputs")
    if not isinstance(outputs,dict) or set(outputs)!={"PDF","PNG_ZIP"}:return False
    for out in outputs.values():
        if not isinstance(out,dict):return False
        if not (out.get("status")=="PASS" and type(out.get("pages")) is int and out["pages"]==1 and
            type(out.get("bytes")) is int and 0<out["bytes"]<=16777216 and
            out.get("pixels")=="EXACT_OPAQUE_INTERIORS_EDGE_INTERPOLATION_NOT_ASSERTED" and
            out.get("state")=="ALL_TABLES_AND_ALL_MEDIA_UNCHANGED"):return False
        for k in ("sha256","current_asset","original_asset"):
            if not isinstance(out.get(k),str) or not re.fullmatch("[0-9a-f]{64}",out[k]):return False
        if out["current_asset"]==out["original_asset"]:return False
        for k in ("crop","mask"):
            rect=out.get(k)
            if not isinstance(rect,list) or len(rect)!=4 or any(type(n) is not int for n in rect):return False
            if not (0<=rect[0]<rect[2]<=1280 and 0<=rect[1]<rect[3]<=640):return False
    return all(outputs["PDF"][k]==outputs["PNG_ZIP"][k] for k in ("current_asset","original_asset","crop","mask"))


def derived_sample(api=26,source="source",run_id="run"):
    output={"status":"PASS","pages":1,"bytes":100,"sha256":"a"*64,
        "current_asset":"b"*64,"original_asset":"c"*64,"crop":[320,160,960,480],"mask":[640,238,800,402],
        "pixels":"EXACT_OPAQUE_INTERIORS_EDGE_INTERPOLATION_NOT_ASSERTED","state":"ALL_TABLES_AND_ALL_MEDIA_UNCHANGED"}
    return {"status":"PASS","scope":"NATIVE_DERIVED_IMAGE_SAF_NOT_RECEIVER","api":api,"commit":source,
        "run_id":run_id,"release_ready":False,"outputs":{"PDF":dict(output),"PNG_ZIP":dict(output)}}


def derived_receipt_selftest():
    import copy
    good=derived_sample();assert derived_receipt(good,26,"source","run")
    bad=[None,{},dict(good,status="FAIL"),dict(good,api=True),dict(good,commit="old"),
        dict(good,run_id="old"),dict(good,outputs={}),dict(good,release_ready=True)]
    for kind in ("PDF","PNG_ZIP"):
        for field,value in (("pages",True),("pages",2),("bytes",0),("sha256","bad"),
            ("current_asset","c"*64),("pixels","NONBLANK"),("state","NOT_VERIFIED"),
            ("crop",[]),("mask",[0,0,0,0]),("current_asset","d"*64)):
            v=copy.deepcopy(good);v["outputs"][kind][field]=value;bad.append(v)
    for v in bad:assert not derived_receipt(v,26,"source","run"),"missing derived evidence accepted"
    print("DERIVED_RECEIPT_CONTROLS 1 positive "+str(len(bad))+" negatives HOST_ONLY",flush=True)

def temporary_apt_dns(text):
    """Conservative allowlist: only explicit temporary DNS failures, not any timeout."""
    found = False
    pending = False
    summary = ("Some index files failed to download. They have been ignored, or old ones used instead.",
               "Unable to fetch some archives, maybe run apt-get update or try with --fix-missing?")
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        dns = re.fullmatch(r"(?:[EW]: Failed to fetch \S+\s+)?Temporary failure resolving '[^'\r\n]+'", line)
        if dns:
            found = True
            pending = False
            continue
        if pending:
            return False
        if re.match(r"Err:\d+\s", line):
            pending = True
        elif line.startswith(("E:", "W:")):
            if line[2:].strip() not in summary:
                return False
        elif line.startswith(("dpkg:", "sudo:")) or re.search(
                r"(?i)(permission denied|not signed|NO_PUBKEY|hash sum mismatch|"
                r"certificate verification failed|404 Not Found|could not get lock)", line):
            return False
    return found and not pending


def ensure_poppler(*, _which=None, _run=None, _clock=None, _sleep=None):
    """Only dependency setup retries. Each original 240s phase retains its deadline.
    75s/attempt and 5s,10s waits are operational caps, not performance measurements.
    Subprocess termination and Python scheduling can exceed a deadline slightly.
    """
    import time
    which = shutil.which if _which is None else _which
    runner = subprocess.run if _run is None else _run
    clock = time.monotonic if _clock is None else _clock
    sleep = time.sleep if _sleep is None else _sleep
    tools = ("pdftotext", "pdftoppm", "pdftocairo", "pdfimages", "pdfinfo", "pdffonts")
    receipt = {"status": "FAIL", "scope": "HOST_DEPENDENCY_SETUP_NOT_EXPORT_ACCEPTANCE",
               "commit": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID"),
               "phase_budget_seconds": 240, "max_attempts_per_phase": 3, "attempts": []}
    def fail(reason, cause=None):
        receipt["reason"] = reason
        raise RuntimeError("PAGED_DEPENDENCY_RECEIPT " + json.dumps(receipt)) from cause
    try:
        receipt["missing_before"] = [name for name in tools if not which(name)]
        if not receipt["missing_before"]:
            receipt.update(status="READY", mode="ALREADY_PRESENT")
            return receipt
        receipt["mode"] = "INSTALL_MISSING"
        if os.environ.get("GITHUB_ACTIONS") != "true":
            fail("dependency_install_requires_disposable_ci")
        common = ["sudo", "-n", "apt-get", "-o", "Acquire::Retries=0",
                  "-o", "Acquire::http::Timeout=20", "-o", "Acquire::https::Timeout=20"]
        commands = (
            ("update", common + ["-o", "APT::Update::Error-Mode=any", "update"]),
            ("install", common + ["install", "-y", "poppler-utils"]))
        for phase, command in commands:
            deadline = clock() + 240
            for number in range(1, 4):
                remaining = deadline - clock()
                if remaining <= 0:
                    fail("dependency_phase_deadline_exhausted")
                timeout = min(75, remaining)
                started = clock()
                error = None
                try:
                    p = runner(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=timeout,
                               env=dict(os.environ, LC_ALL="C", LANG="C"))
                    code, raw = p.returncode, p.stdout
                except subprocess.TimeoutExpired as exc:
                    error = exc
                    code, raw = None, exc.output
                # Other errors, including product assertions, are never retried.
                if raw is None:
                    raw = b""
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")
                text = raw.decode("utf-8", errors="replace")
                recognized = temporary_apt_dns(text)
                diagnostics = recognized or bool(re.search(r"(?m)^(?:[EW]:|Err:\d+\s)", text))
                record = {"phase": phase, "number": number, "command": command[:],
                          "timeout_seconds": timeout, "returncode": code,
                          "error_type": type(error).__name__ if error else None,
                          "elapsed_seconds": round(clock() - started, 3),
                          "recognized_temporary_dns": recognized, "retry_wait_seconds": 0,
                          "output_bytes": len(raw), "output_tail": raw[-2048:].decode("utf-8", errors="replace"),
                          "output_truncated": len(raw) > 2048}
                receipt["attempts"].append(record)
                if code == 0 and not diagnostics and clock() <= deadline:
                    break
                if not recognized:
                    fail("dependency_failure_not_allowlisted", error)
                if number == 3:
                    fail("dependency_attempts_exhausted", error)
                wait = (5, 10)[number - 1]
                if deadline - clock() <= wait:
                    fail("dependency_phase_deadline_exhausted", error)
                record["retry_wait_seconds"] = wait
                sleep(wait)
        receipt["missing_after"] = [name for name in tools if not which(name)]
        if receipt["missing_after"]:
            fail("dependency_tools_still_missing")
        receipt["status"] = "READY"
        return receipt
    finally:
        # On failure the same complete attempt receipt is in the exception
        # consumed by existing reports; on success verify() nests it in its result.
        print("PAGED_DEPENDENCY_RECEIPT " + json.dumps(receipt), flush=True)


def dependency_setup_contract(ensure):
    """Injected host contracts only: no apt, network or Android execution."""
    import contextlib
    import io
    from unittest.mock import patch
    from subprocess import CompletedProcess, TimeoutExpired
    dns = b"Err:1 https://example.invalid stable InRelease\n  Temporary failure resolving 'example.invalid'\n"
    labels = []

    def scenario(answers=(), installed=False, after=True, ci=True, oversleep=False, missing_after_name=None):
        calls, sleeps = [], []
        now = [100.0]
        ready = [installed]
        def which(name):
            return "/usr/bin/" + name if ready[0] and name != missing_after_name else None
        def clock():
            return now[0]
        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += 300 if oversleep else seconds
        def runner(command, **kwargs):
            index = len(calls)
            assert index < len(answers), "unexpected dependency retry"
            calls.append((list(command), dict(kwargs)))
            code, output, duration = answers[index]
            assert 0 < kwargs["timeout"] <= 75
            assert kwargs["stdin"] == subprocess.DEVNULL
            assert kwargs["stderr"] == subprocess.STDOUT
            assert kwargs["env"]["LC_ALL"] == "C"
            now[0] += min(duration, kwargs["timeout"])
            if code == "timeout":
                raise TimeoutExpired(command, kwargs["timeout"], output=output)
            if code == "assert":
                raise AssertionError("product assertion sentinel")
            if code == 0 and command[-3:] == ["install", "-y", "poppler-utils"] and after:
                ready[0] = True
            return CompletedProcess(command, code, output)
        result, error = None, None
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true" if ci else "false"}):
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                try:
                    result = ensure(_which=which, _run=runner, _clock=clock, _sleep=sleep)
                except Exception as exc:
                    error = exc
        return result, error, calls, sleeps, captured.getvalue()

    def check(value, label):
        assert value, label
        labels.append(label)

    result, error, calls, sleeps, log = scenario(installed=True)
    check(error is None and result["status"] == "READY" and result["attempts"] == [] and
          not calls and not sleeps and result["mode"] == "ALREADY_PRESENT", "present_no_apt")
    ok = (0, b"Reading package lists... Done\n", 1)
    result, error, calls, sleeps, log = scenario([ok, ok])
    check(error is None and result["status"] == "READY" and len(calls) == 2 and
          [a["phase"] for a in result["attempts"]] == ["update", "install"] and
          all(a["number"] == 1 and a["retry_wait_seconds"] == 0 for a in result["attempts"]),
          "install_and_record_first_attempt")
    check(all(c[:3] == ["sudo", "-n", "apt-get"] and "Acquire::Retries=0" in c and
              "Acquire::http::Timeout=20" in c and "Acquire::https::Timeout=20" in c for c, _ in calls)
          and "APT::Update::Error-Mode=any" in calls[0][0] and
          calls[0][0][-1] == "update" and calls[1][0][-3:] == ["install", "-y", "poppler-utils"],
          "strict_fixed_dependency_commands")
    result, error, calls, sleeps, log = scenario([(100, dns, 2), ok, ok])
    check(error is None and len(calls) == 3 and sleeps == [5] and
          result["attempts"][0]["recognized_temporary_dns"] is True and
          result["attempts"][0]["returncode"] == 100 and
          "Temporary failure resolving" in result["attempts"][0]["output_tail"],
          "dns_failure_retry_retains_first_failure")
    result, error, calls, sleeps, log = scenario([("timeout", dns, 75), ok, ok])
    check(error is None and sleeps == [5] and
          result["attempts"][0]["error_type"] == "TimeoutExpired", "dns_timeout_bytes_retry")
    for answer, label in [
        (("timeout", b"", 75), "unknown_timeout_not_retried"),
        ((100, b"E: Unable to locate package poppler-utils\n", 1), "unknown_error_not_retried"),
        ((100, dns + b"E: The repository is not signed.\n", 1), "mixed_signature_failure_not_retried"),
        ((100, dns + b"E: Could not get lock /var/lib/dpkg/lock\n", 1), "mixed_lock_failure_not_retried"),
        ((100, b"E: 404 Not Found\n", 1), "http_404_not_retried"),
        ((0, b"W: Some index files failed to download. They have been ignored, or old ones used instead.\n", 1),
         "partial_update_not_silent_success"),
    ]:
        result, error, calls, sleeps, log = scenario([answer])
        check(result is None and error is not None and len(calls) == 1 and not sleeps and
              "PAGED_DEPENDENCY_RECEIPT" in str(error) and '"status": "FAIL"' in str(error), label)
    result, error, calls, sleeps, log = scenario([(0, dns, 1), ok, ok])
    check(error is None and sleeps == [5] and len(calls) == 3 and
          result["attempts"][0]["returncode"] == 0, "zero_exit_dns_not_accepted")
    result, error, calls, sleeps, log = scenario([(100, dns, 75)] * 3)
    check(result is None and error is not None and len(calls) == 3 and sleeps == [5, 10] and
          sum(k["timeout"] for _, k in calls) + sum(sleeps) <= 240 and
          str(error).count('"phase": "update"') == 3, "three_attempts_with_original_budget")
    result, error, calls, sleeps, log = scenario([ok, (100, dns, 1), ok])
    check(error is None and [c[-1] for c, _ in calls] == ["update", "poppler-utils", "poppler-utils"]
          and [a["number"] for a in result["attempts"]] == [1, 1, 2], "install_retries_only_install")
    result, error, calls, sleeps, log = scenario([ok, ok], after=False)
    check(result is None and error is not None and len(calls) == 2 and
          "missing_after" in str(error), "all_six_tools_required_after_install")
    for tool in ("pdftotext", "pdftoppm", "pdftocairo", "pdfimages", "pdfinfo", "pdffonts"):
        result, error, calls, sleeps, log = scenario([ok, ok], missing_after_name=tool)
        check(result is None and error is not None and len(calls) == 2 and
              '"missing_after": ["' + tool + '"]' in str(error), "missing_tool_" + tool)
    result, error, calls, sleeps, log = scenario([], ci=False)
    check(error is not None and not calls and not sleeps, "no_non_ci_install")
    result, error, calls, sleeps, log = scenario([("assert", b"", 1)])
    check(type(error) is AssertionError and str(error) == "product assertion sentinel" and
          len(calls) == 1 and not sleeps, "assertions_unchanged_no_retry")
    result, error, calls, sleeps, log = scenario([(100, dns, 1)], oversleep=True)
    check(type(error) is RuntimeError and "dependency_phase_deadline_exhausted" in str(error)
          and len(calls) == 1 and sleeps == [5], "deadline_rechecked_after_sleep")
    large = b"x" * 5000 + b"\n" + dns
    result, error, calls, sleeps, log = scenario([(100, large, 1), ok, ok])
    check(error is None and result["attempts"][0]["output_bytes"] == len(large) and
          result["attempts"][0]["output_truncated"] is True and
          len(result["attempts"][0]["output_tail"].encode()) <= 2048, "bounded_attempt_output")
    check("PAGED_DEPENDENCY_RECEIPT" in log and '"attempts":' in log,
          "attempt_receipt_emitted")
    return labels


def dependency_setup_selftest():
    import ast
    import inspect
    labels = dependency_setup_contract(ensure_poppler)
    source = inspect.getsource(ensure_poppler)
    mutations = [
        ("if not recognized:", "if False:"),
        ("code == 0 and not diagnostics", "code == 0"),
        ('receipt["attempts"].append(record)', 'receipt["attempts"] = [record]'),
        ('if receipt["missing_after"]:', "if False:"),
        ("min(75, remaining)", "min(90, remaining)"),
        ("if remaining <= 0:", "if False:"),
    ]
    for old, new in mutations:
        assert source.count(old) == 1, "dependency mutation anchor drift"
        changed = source.replace(old, new)
        namespace = dict(globals())
        exec(compile(changed, "<dependency-mutant>", "exec"), namespace)
        try:
            dependency_setup_contract(namespace["ensure_poppler"])
        except AssertionError:
            continue
        raise AssertionError("dependency mutant survived: " + old)
    # Execute the real verify() prefix, stopping before Android instrumentation.
    # Also inspect the actual report field, not a separately hand-written receipt.
    tree = ast.parse(inspect.getsource(verify))
    function = tree.body[0]
    boundary = next(i for i, statement in enumerate(function.body)
                    if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name) and statement.value.func.id == "instrumentation")
    report = next(statement.value for statement in function.body
                  if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "report" for t in statement.targets))
    fields = {k.value: v for k, v in zip(report.keys, report.values) if isinstance(k, ast.Constant)}
    assert isinstance(fields["dependency_setup"], ast.Name) and fields["dependency_setup"].id == "dependencies"
    function.body = function.body[:boundary] + [ast.Return(value=ast.Name(id="dependencies", ctx=ast.Load()))]
    sentinel = {"dependency": "sentinel"}
    calls = []
    def setup():
        calls.append("setup")
        return sentinel
    namespace = {"selftest": lambda: None, "ensure_poppler": setup}
    exec(compile(ast.fix_missing_locations(tree), "<dependency-wiring>", "exec"), namespace)
    assert namespace["verify"](*([None] * 6)) is sentinel and calls == ["setup"]
    failure = RuntimeError("dependency prefix failure sentinel")
    def broken():
        raise failure
    namespace["ensure_poppler"] = broken
    try:
        namespace["verify"](*([None] * 6))
    except RuntimeError as exc:
        assert exc is failure
    else:
        raise AssertionError("dependency prefix swallowed original failure")
    print("PAGED_DEPENDENCY_CONTROLS " + str(len(labels)) +
          " checks 6 implementation mutants rejected; prefix 2 checks report binding 1 HOST_ONLY", flush=True)


if __name__=="__main__":selftest()
