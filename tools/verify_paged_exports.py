#!/usr/bin/env python3
"""Actual APK pagination API + independent Poppler/PNG checks. NOT app UI or SAF."""
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
    key=debug_key(cert)
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
            "   dsl.signingConfigs.getByName('debug').storeFile = new File("+json.dumps(str(key))+")\n"
            "  }\n }\n}\n")
        backup=work/"default-test.apk";backup.write_bytes(saved)
        try:
            run(["gradle","--no-daemon","--console=plain","-I",init,"assembleDebugAndroidTest"],timeout=300)
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
    app=apps[0];current=app.read_bytes();cert=certificate(app,gate);key=debug_key(cert)
    baseline="452969cf2f053bb8c527d3fb2dc3bf1fbf4afe21"
    run(["git","-C",root,"fetch","--no-tags","--depth=1","origin",baseline],timeout=120)
    with tempfile.TemporaryDirectory(prefix="paged-size-",dir=root/"build") as temp:
        work=Path(temp);archive=work/"baseline.tar";project=work/"baseline";project.mkdir()
        with archive.open("wb") as out:
            subprocess.run(["git","-C",str(root),"archive",baseline],stdout=out,check=True,timeout=60)
        with tarfile.open(archive) as files:files.extractall(project,filter="data")
        init=work/"signing.gradle"
        init.write_text("gradle.beforeProject { p -> p.plugins.withId('com.android.application') { "
            "p.androidComponents.finalizeDsl { dsl -> dsl.signingConfigs.getByName('debug').storeFile = new File("
            +json.dumps(str(key))+") } } }\n")
        run(["gradle","--no-daemon","--console=plain","-p",project,"-I",init,"assembleDebug"],timeout=360)
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
    if not all(shutil.which(x) for x in ("pdftotext","pdftoppm","pdftocairo","pdfimages","pdfinfo","pdffonts")):
        run(["sudo","apt-get","update"],timeout=240)
        run(["sudo","apt-get","install","-y","poppler-utils"],timeout=240)
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
            "rasterizer_oracle":oracle,
            "preview_ui":{"checks":len(PREVIEW_LABELS),"labels":PREVIEW_LABELS,
                          "scope":"ACTUAL_DIALOG_AND_INTERCEPTED_SAF_NOT_PROVIDER_E2E"},
            "instrumentation":identity,"release_ready":False}
    target=gate.ROOT/"native-ui" if hasattr(gate,"ROOT") else Path("native-ui")
    target.mkdir(exist_ok=True)
    (target/"paged-result.json").write_text(json.dumps(report,indent=2)+"\n")
    print("PAGED_EXPORT_EVIDENCE "+json.dumps(report),flush=True)
    return report

if __name__=="__main__":selftest()
