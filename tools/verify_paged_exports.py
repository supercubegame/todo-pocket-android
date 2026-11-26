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
import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;
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
 static void awaitPreviewScreen(android.app.Instrumentation inst,android.app.Activity activity)throws Exception{
  long started=android.os.SystemClock.uptimeMillis(),deadline=started+10000;
  int observations=0;
  while(android.os.SystemClock.uptimeMillis()<deadline){
   boolean[] ready={false};
   onUi(inst,()->{
    if(activity.isDestroyed()||activity.isFinishing())throw new IllegalStateException("paged startup owner retired");
    Object screen=field(activity,"screen");
    ready[0]=screen!=null&&!((Boolean)field(screen,"busy"));
   });
   observations++;
   long observed=android.os.SystemClock.uptimeMillis();
   if(observed>=deadline)throw new AssertionError("paged startup observation exceeded bound");
   if(ready[0]){
    System.out.println("PAGED_STARTUP_READY observations="+observations+" elapsed_ms="+(observed-started));
    return;
   }
   android.os.SystemClock.sleep(Math.min(50,deadline-observed));
  }
  throw new AssertionError("paged startup not ready within observation bound; observations="+observations);
 }
 static byte[] state(android.app.Instrumentation inst,android.app.Activity activity)throws Exception{
  Object[] database={null};
  onUi(inst,()->{
   if(activity.isDestroyed()||activity.isFinishing())throw new IllegalStateException("paged snapshot owner retired");
   Object screen=field(activity,"screen");
   if(screen==null||((Boolean)field(screen,"busy")))throw new IllegalStateException("paged snapshot screen not ready");
   database[0]=field(screen,"db");
  });
  Object db=database[0];
  return(byte[])privateMethod(db.getClass(),"exportState").invoke(db);
 }
 @SuppressWarnings("unchecked")
 static void previewUi(android.app.Instrumentation inst,File root)throws Exception{
  Class<?> activityClass=Class.forName("com.supercubegame.pockettodo.MainActivity");
  Method decoder=privateMethod(activityClass,"decodePagedPreview",android.content.Context.class,byte[].class,int.class);
  Method preview=privateMethod(activityClass,"previewShare",byte[][].class,int.class);
  android.content.Intent start=new android.content.Intent().setClassName(inst.getTargetContext(),
    activityClass.getName()).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK);
  android.app.Activity activity=inst.startActivitySync(start);
  try{
   inst.waitForIdleSync();
   awaitPreviewScreen(inst,activity);
   byte[] before=state(inst,activity);
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
     previewOk(boxes.size()==1&&!boxes.get(0).isChecked()&&"我已核对预览，接下来由我选择保存或发送".contentEquals(boxes.get(0).getText()),"unchecked_consent_"+suffix);
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
     previewOk(Arrays.equals(before,state(inst,activity)),"preview_preserves_database_"+suffix);
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
 static android.widget.Button findSend(android.view.View v,String text){
  if(v instanceof android.widget.Button && text.contentEquals(((android.widget.Button)v).getText()))return (android.widget.Button)v;
  if(v instanceof android.view.ViewGroup){android.view.ViewGroup g=(android.view.ViewGroup)v;for(int i=0;i<g.getChildCount();i++){android.widget.Button b=findSend(g.getChildAt(i),text);if(b!=null)return b;}}return null;
 }
 static final class ChooserChoice {
  static final String LABEL="PocketTodo CI Receiver";
  final AccessibilityNodeInfo row,label; final String key,reason;
  ChooserChoice(AccessibilityNodeInfo r,AccessibilityNodeInfo l,String k,String why){row=r;label=l;key=k;reason=why;}
  static ChooserChoice no(String why){return new ChooserChoice(null,null,"",why);}
  static String s(CharSequence t){return t==null?"":t.toString();}
  static boolean system(String p){return Arrays.asList("android","com.android.intentresolver","com.google.android.intentresolver").contains(p);}
  static Rect box(AccessibilityNodeInfo n){Rect r=new Rect();n.getBoundsInScreen(r);return r;}
  static boolean collection(AccessibilityNodeInfo n){String c=s(n.getClassName());return n.isScrollable()||n.getCollectionInfo()!=null||c.endsWith("ListView")||c.endsWith("GridView")||c.endsWith("RecyclerView");}
  static boolean sameWindow(AccessibilityNodeInfo n,String owner,int win){return n!=null&&n.getWindowId()==win&&owner.equals(s(n.getPackageName()));}
  static ChooserChoice sample(AccessibilityNodeInfo top){
   if(top==null)return no("no_window");String owner=s(top.getPackageName());int win=top.getWindowId();
   // Never search the view hierarchy of a non-chooser or click its content.
   if(!system(owner))return no("not_system_chooser");
   AccessibilityNodeInfo label=null;for(AccessibilityNodeInfo n:top.findAccessibilityNodeInfosByText(LABEL)){
    if(n==null||!LABEL.equals(s(n.getText()))||!n.isVisibleToUser())continue;
    if(!sameWindow(n,owner,win))return no("mixed_window");if(label!=null)return no("duplicate_label");label=n;
   }
   if(label==null)return no("no_exact_visible_label");AccessibilityNodeInfo row=label;
   for(int i=0;;i++){
    if(i>=9||!sameWindow(row,owner,win)||top.equals(row)||collection(row)||!row.isEnabled()||!row.isVisibleToUser())return no("not_a_tile");
    if(row.isClickable())break;row=row.getParent();
   }
   AccessibilityNodeInfo a=row;int hops=0;while(!top.equals(a)){
    if(hops++>=32||!sameWindow(a,owner,win))return no("detached_tile");a=a.getParent();
   }
   Rect frame=box(top),item=box(row),text=box(label);if(text.isEmpty()||item.isEmpty()||!frame.contains(item)||!item.contains(text))return no("invalid_bounds");
   ArrayDeque<AccessibilityNodeInfo> todo=new ArrayDeque<>();todo.add(row);int nodes=0,labels=0;
   while(!todo.isEmpty()){
    AccessibilityNodeInfo n=todo.remove();if(++nodes>64||!sameWindow(n,owner,win)||collection(n)||(!n.equals(row)&&n.isClickable()))return no("shared_action");
    String t=s(n.getText()),alt=s(n.getContentDescription());
    if((!t.isEmpty()&&!LABEL.equals(t))||(!alt.isEmpty()&&!LABEL.equals(alt)))return no("other_label_in_tile");
    if(LABEL.equals(t)){if(!n.equals(label))return no("second_label");labels++;}
    int count=n.getChildCount();if(count>64-nodes-todo.size())return no("large_subtree");
    for(int i=0;i<count;i++){AccessibilityNodeInfo child=n.getChild(i);if(child==null)return no("stale_child");todo.add(child);}
   }
   if(labels!=1)return no("label_not_in_tile");String key=owner+":"+win+":"+s(row.getClassName())+":"+s(row.getViewIdResourceName())+":"+item.flattenToString()+":"+text.flattenToString();
   return new ChooserChoice(row,label,key,"eligible");
  }
  // Diagnostics use only structure of the synthetic label's system-owned ancestors, never other labels or file contents.
  static String shape(AccessibilityNodeInfo top){
   if(top==null||!system(s(top.getPackageName())))return "no_system_tree";String owner=s(top.getPackageName());StringBuilder out=new StringBuilder(owner);int win=top.getWindowId(),exact=0;
   for(AccessibilityNodeInfo n:top.findAccessibilityNodeInfosByText(LABEL)){
    if(n==null||!sameWindow(n,owner,win)||!LABEL.equals(s(n.getText()))||!n.isVisibleToUser())continue;if(++exact>1)continue;
    for(int i=0;i<6&&sameWindow(n,owner,win);i++,n=n.getParent()){
     out.append('|').append(s(n.getClassName())).append(':').append(s(n.getViewIdResourceName())).append(':').append(n.isClickable()).append(':').append(n.getChildCount()).append(':').append(box(n).flattenToString());
    }
   }return out.append(" exact=").append(exact).toString();
  }
  static final class Gate {
   ChooserChoice previous;long first;boolean attempted;int samples;
   boolean act(ChooserChoice c,long now,long end){
    samples++;if(attempted||now>=end)return false;if(c.row==null){previous=null;return false;}
    if(previous==null||!c.row.equals(previous.row)||!c.label.equals(previous.label)||!c.key.equals(previous.key)){previous=c;first=now;return false;}
    if(now-first<150)return false;attempted=true;
    if(!c.row.performAction(AccessibilityNodeInfo.ACTION_CLICK))throw new AssertionError("CI receiver tile refused a single semantic click");return true;
   }
  }
 }
 // Post-failure only: a bounded census of system-owned nodes, never a recipient picker.
 static String receiverSurface(AccessibilityNodeInfo top,long endNanos){
  if(top==null||!ChooserChoice.system(ChooserChoice.s(top.getPackageName())))return "surface=unavailable";
  String owner=ChooserChoice.s(top.getPackageName());int win=top.getWindowId(),visited=0,text=0,desc=0,hidden=0,scrollable=0,expand=0;
  boolean complete=true;ArrayDeque<AccessibilityNodeInfo> q=new ArrayDeque<>();q.add(top);
  try{while(!q.isEmpty()){
   if(System.nanoTime()>=endNanos){complete=false;break;}
   AccessibilityNodeInfo n=q.remove();try{
    if(!ChooserChoice.sameWindow(n,owner,win)){complete=false;continue;}visited++;
    boolean t=ChooserChoice.LABEL.contentEquals(ChooserChoice.s(n.getText())),d=ChooserChoice.LABEL.contentEquals(ChooserChoice.s(n.getContentDescription()));
    if(n.isVisibleToUser()){if(t)text++;if(d)desc++;if(n.isScrollable())scrollable++;if((n.getActions()&AccessibilityNodeInfo.ACTION_EXPAND)!=0)expand++;}
    else if(t||d)hidden++;
    int count=n.getChildCount(),room=128-visited-q.size();if(count>room)complete=false;
    for(int i=0;i<Math.min(count,room);i++){if(System.nanoTime()>=endNanos){complete=false;break;}AccessibilityNodeInfo c=n.getChild(i);if(c==null)complete=false;else q.add(c);}
   }finally{if(n!=top)n.recycle();}
  }}catch(RuntimeException e){return "surface=unavailable";}finally{while(!q.isEmpty()){AccessibilityNodeInfo n=q.remove();if(n!=top)n.recycle();}}
  return "surface=observed complete="+complete+" nodes="+visited+" visible_exact_text="+text+" visible_exact_description="+desc+" hidden_exact="+hidden+" visible_scrollable="+scrollable+" visible_expand_action="+expand;
 }
 // Fixture navigation only. An EXPAND is never a recipient choice, byte receipt or acknowledgement.
 static final class DrawerReveal {
  static final String OWNER="com.android.intentresolver", PANEL="android:id/contentPanel", TYPE="android.widget.ScrollView";
  static boolean fixtureScope(int api,String product,String hardware,String file){return api==34&&"com.supercubegame.pockettodo.v12.preview".equals(product)&&"ranchu".equals(hardware)&&"paged.pdf".equals(file);}
  static final class NodeAt {
   final AccessibilityNodeInfo n;final String path;NodeAt(AccessibilityNodeInfo node,String p){n=node;path=p;}
  }
  AccessibilityNodeInfo previousDrawer,previousLabel;String previousKey="",status="not_observed";long since;boolean used;
  void clear(){if(previousDrawer!=null)previousDrawer.recycle();if(previousLabel!=null)previousLabel.recycle();previousDrawer=previousLabel=null;previousKey="";}
  void reject(String why){clear();status=why;}
  boolean eligible(int api,String file,String miss){return !used && api==34 && "paged.pdf".equals(file) && "no_exact_visible_label".equals(miss);}
  void consider(int api,String file,String miss,AccessibilityNodeInfo top,java.util.function.LongSupplier clock,long end){
   if(!eligible(api,file,miss)){clear();return;}
   long start=clock.getAsLong(),scanEnd=Math.min(end,start+120);
   if(start>=end||top==null||!OWNER.contentEquals(ChooserChoice.s(top.getPackageName()))||top.getWindowId()<0){reject("wrong_window_or_deadline");return;}
   int win=top.getWindowId(),expandCount=0,hiddenCount=0;NodeAt drawer=null,hidden=null;
   ArrayList<NodeAt> nodes=new ArrayList<>();nodes.add(new NodeAt(top,"r"));
   try{
    for(int i=0;i<nodes.size();i++){
     NodeAt v=nodes.get(i);AccessibilityNodeInfo n=v.n;
     if(clock.getAsLong()>=scanEnd||!ChooserChoice.sameWindow(n,OWNER,win)){reject("incomplete_window");return;}
     boolean visible=n.isVisibleToUser(),exact=ChooserChoice.LABEL.equals(ChooserChoice.s(n.getText()))||ChooserChoice.LABEL.equals(ChooserChoice.s(n.getContentDescription()));
     if(exact){if(visible){reject("already_visible");return;}hiddenCount++;hidden=v;}
     if(visible&&(n.getActions()&AccessibilityNodeInfo.ACTION_EXPAND)!=0){
      expandCount++;
      if(n.isEnabled()&&n.isScrollable()&&TYPE.equals(ChooserChoice.s(n.getClassName()))&&PANEL.equals(n.getViewIdResourceName()))drawer=v;
     }
     int count=n.getChildCount();if(count>128-nodes.size()){reject("incomplete_window");return;}
     for(int k=0;k<count;k++){
      if(clock.getAsLong()>=scanEnd){reject("incomplete_window");return;}
      AccessibilityNodeInfo child=n.getChild(k);if(child==null){reject("incomplete_window");return;}nodes.add(new NodeAt(child,v.path+"/"+k));
     }
    }
    if(expandCount!=1||drawer==null||hiddenCount!=1||!hidden.path.startsWith(drawer.path+"/")){reject("not_unique_drawer_and_hidden_descendant");return;}
    Rect bounds=ChooserChoice.box(drawer.n);if(bounds.isEmpty()||!ChooserChoice.box(top).contains(bounds)){reject("invalid_drawer_bounds");return;}
    long at=clock.getAsLong();if(at>=scanEnd){reject("scan_deadline");return;}
    String key=win+":"+drawer.path+":"+hidden.path+":"+bounds.flattenToString();
    if(!key.equals(previousKey)||!drawer.n.equals(previousDrawer)||!hidden.n.equals(previousLabel)){
     clear();previousKey=key;previousDrawer=AccessibilityNodeInfo.obtain(drawer.n);previousLabel=AccessibilityNodeInfo.obtain(hidden.n);since=at;status="one_sample";return;
    }
    if(at-since<150){status="awaiting_stability";return;}
    if(clock.getAsLong()>=end){reject("action_deadline");return;}
    used=true;status=drawer.n.performAction(AccessibilityNodeInfo.ACTION_EXPAND)?"accepted":"refused";
    System.out.println("CHOOSER_DRAWER_EXPAND case=paged.pdf one_shot=true result="+status);
   }catch(RuntimeException e){reject(used?"action_error":"unavailable");}
   finally{for(int i=1;i<nodes.size();i++)nodes.get(i).n.recycle();if(used)clear();}
  }
 }
 static void receiverUi(android.app.Instrumentation inst,File root,String filename,String nonce)throws Exception{
  if(!nonce.matches("[0-9a-f]{32}")||!Arrays.asList("paged.pdf","picture.zip","paged.zip","share.zip").contains(filename))throw new AssertionError("fixture identity");
  boolean pdf=filename.endsWith(".pdf"),md=filename.equals("share.zip");final int requested=md?0:pdf?1:2;Class<?> cl=Class.forName("com.supercubegame.pockettodo.MainActivity");
  android.app.Activity a=inst.startActivitySync(new android.content.Intent().setClassName(inst.getTargetContext(),cl.getName()).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
  try{awaitPreviewScreen(inst,a);byte[] current=state(inst,a),bytes=read(new File(root,filename));
   java.lang.reflect.Method preview=privateMethod(cl,"previewShare",byte[][].class,int.class);
   final String label=md?"发送 Markdown 图片包":pdf?"发送 PDF":"按页发送图片";
   final java.util.concurrent.atomic.AtomicInteger forbidden=new java.util.concurrent.atomic.AtomicInteger();
   android.app.Instrumentation.ActivityMonitor guard=new android.app.Instrumentation.ActivityMonitor(){
    @Override public android.app.Instrumentation.ActivityResult onStartActivity(android.content.Intent i){if(android.content.Intent.ACTION_CHOOSER.equals(i.getAction())){forbidden.incrementAndGet();return new android.app.Instrumentation.ActivityResult(android.app.Activity.RESULT_CANCELED,null);}return null;}};
   inst.addMonitor(guard);
   try{
    final byte[] stale=current.clone();stale[0]^=1;
    for(boolean expired:new boolean[]{false,true}){
     onUi(inst,()->{preview.invoke(a,new byte[][]{expired?stale:current,bytes},requested);android.app.AlertDialog d=(android.app.AlertDialog)((List<?>)field(a,"shareDialogs")).get(0);
      android.view.View decor=d.getWindow().getDecorView();List<android.widget.CheckBox> cb=new ArrayList<>();collect(decor,new ArrayList<>(),cb);android.widget.Button send=findSend(decor,label);
      if(send==null||cb.size()!=1||cb.get(0).isChecked())throw new AssertionError("fresh consent");
      if(expired){cb.get(0).setChecked(true);send.performClick();}else{send.performClick();if(!d.isShowing())throw new AssertionError("unchecked send dismissed preview");d.cancel();}});
     awaitPreviewScreen(inst,a);if(expired)onUi(inst,()->{android.widget.TextView status=(android.widget.TextView)field(field(a,"screen"),"status");if(!status.getText().toString().contains("未能完成分享"))throw new AssertionError("stale ticket refusal missing");});if(forbidden.get()!=0)throw new AssertionError("cancelled or stale share launched chooser");
    }
    if(md){onUi(inst,()->{preview.invoke(a,new byte[][]{current,bytes},0);android.app.AlertDialog d=(android.app.AlertDialog)((List<?>)field(a,"shareDialogs")).get(0);List<android.widget.CheckBox> cb=new ArrayList<>();collect(d.getWindow().getDecorView(),new ArrayList<>(),cb);if(cb.size()!=1||cb.get(0).isChecked())throw new AssertionError("fresh Markdown consent");cb.get(0).setChecked(true);d.cancel();});awaitPreviewScreen(inst,a);
     if(forbidden.get()!=0||!Arrays.equals(current,state(inst,a)))throw new AssertionError("cancelled Markdown wrote or launched chooser");System.out.println("MARKDOWN_GUARDS "+nonce+" unchecked_cancel_stale_no_chooser");}
   }finally{inst.removeMonitor(guard);}
   onUi(inst,()->{preview.invoke(a,new byte[][]{current,bytes},requested);List<?> ds=(List<?>)field(a,"shareDialogs");if(ds.size()!=1)throw new AssertionError("one preview");android.app.AlertDialog d=(android.app.AlertDialog)ds.get(0);android.view.View decor=d.getWindow().getDecorView();List<android.widget.CheckBox> boxes=new ArrayList<>();collect(decor,new ArrayList<>(),boxes);android.widget.Button send=findSend(decor,label);if(boxes.size()!=1||boxes.get(0).isChecked()||send==null)throw new AssertionError("initial send controls");send.performClick();if(!d.isShowing())throw new AssertionError("unchecked send");boxes.get(0).setChecked(true);send.performClick();});
   final boolean canReveal=DrawerReveal.fixtureScope(android.os.Build.VERSION.SDK_INT,inst.getTargetContext().getPackageName(),android.os.Build.HARDWARE,filename);
   long end=android.os.SystemClock.elapsedRealtime()+20000;boolean picked=false;ChooserChoice.Gate choice=new ChooserChoice.Gate();String last="not_observed";DrawerReveal reveal=new DrawerReveal();
   try{while(android.os.SystemClock.elapsedRealtime()<end&&!picked){
    ChooserChoice c=ChooserChoice.sample(inst.getUiAutomation().getRootInActiveWindow());last=c.reason;
    picked=choice.act(c,android.os.SystemClock.elapsedRealtime(),end);
    if(picked)System.out.println("CHOOSER_TILE_CLICK "+nonce+" "+c.key+" samples="+choice.samples);
    else{
     if(canReveal&&reveal.eligible(android.os.Build.VERSION.SDK_INT,filename,last)){
      AccessibilityNodeInfo top=inst.getUiAutomation().getRootInActiveWindow();
      try{reveal.consider(android.os.Build.VERSION.SDK_INT,filename,last,top,android.os.SystemClock::elapsedRealtime,end);}finally{if(top!=null)top.recycle();}
     }else reveal.clear();
     android.os.SystemClock.sleep(200);
    }
   }}finally{reveal.clear();}
   if(android.os.Build.VERSION.SDK_INT==34&&"paged.pdf".equals(filename))System.out.println("CHOOSER_DRAWER_STATUS used="+reveal.used+" state="+reveal.status);
   if(!picked){AccessibilityNodeInfo top=inst.getUiAutomation().getRootInActiveWindow();String original=ChooserChoice.shape(top);String evidence="";
    try{if(android.os.Build.VERSION.SDK_INT==34&&"paged.pdf".equals(filename)&&"no_exact_visible_label".equals(last))evidence=" "+receiverSurface(top,System.nanoTime()+250000000L);}catch(RuntimeException ignored){}finally{if(top!=null)top.recycle();}
    throw new AssertionError("no stable isolated CI receiver tile; case="+filename+" reason="+last+" observations="+choice.samples+" final_tree="+original+evidence);
   }File ack=new File(root,"ack-"+nonce);long endAck=android.os.SystemClock.elapsedRealtime()+35000;while(!ack.exists()&&android.os.SystemClock.elapsedRealtime()<endAck)android.os.SystemClock.sleep(150);
   if(!ack.exists()){
    android.view.accessibility.AccessibilityNodeInfo top=inst.getUiAutomation().getRootInActiveWindow();String owner=top==null?"none":String.valueOf(top.getPackageName());
    throw new AssertionError("ack absent after receiver choice: "+filename+" owner="+owner);
   }
   byte[] confirmation=read(ack);if(!Arrays.equals("checked".getBytes(java.nio.charset.StandardCharsets.US_ASCII),confirmation))throw new AssertionError("incorrect ack bytes: "+filename+" length="+confirmation.length);
   if(!Arrays.equals(current,state(inst,a)))throw new AssertionError("sender database differs after share: "+filename);
   System.out.println("SEND_PROBE "+nonce);
  }finally{onUi(inst,a::finish);}
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
   if("send".equals(args.getString("mode")))PagedContractTest.receiverUi(this,root,args.getString("payload"),args.getString("nonce"));
   else PagedContractTest.verify(new String[]{root.getAbsolutePath(),args.getString("expectedApi")},this);
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

RECEIVER_JAVA = 'package com.supercubegame.pockettodo.exportprobe;\n\nimport android.app.Activity;\nimport android.content.ClipData;\nimport android.content.Intent;\nimport android.content.pm.PackageManager;\nimport android.database.Cursor;\nimport android.net.Uri;\nimport android.os.Bundle;\nimport android.os.Process;\nimport android.provider.OpenableColumns;\nimport org.json.JSONArray;\nimport org.json.JSONObject;\nimport java.io.*;\nimport java.nio.charset.StandardCharsets;\nimport java.nio.file.*;\nimport java.security.MessageDigest;\nimport java.util.*;\n\n/** Synthetic CI receiver only; never part of the production APK. Expected outputs are\n * seeded separately into this receiver\'s private directory by the fixture runner, not\n * provided in extras by the sender. Receipt contains metadata, not file contents. */\npublic final class ReceiverActivity extends Activity {\n    private static void need(boolean ok,String msg)throws IOException { if(!ok)throw new IOException(msg); }\n    private static String hex(byte[] data){StringBuilder s=new StringBuilder();for(byte b:data)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}\n    private static String sum(byte[] b)throws Exception{return hex(MessageDigest.getInstance("SHA-256").digest(b));}\n    /** This oracle is for the small public CI selection only. It is not present in the product APK. */\n    static JSONObject inspectMarkdown(byte[] body,JSONObject want)throws Exception{\n        need(body.length>0&&body.length<=65536,"unexpected CI ZIP budget");byte[][] values=new byte[2][];String[] names={"notes.md","assets/image-1.png"};\n        try(java.util.zip.ZipInputStream in=new java.util.zip.ZipInputStream(new ByteArrayInputStream(body))){\n            for(int i=0;i<names.length;i++){\n                java.util.zip.ZipEntry e=in.getNextEntry();need(e!=null&&!e.isDirectory()&&names[i].equals(e.getName()),"selected member order");\n                ByteArrayOutputStream w=new ByteArrayOutputStream();byte[] buf=new byte[2048];int n;while((n=in.read(buf))!=-1){need(n>0&&n<=65536-w.size(),"CI member exceeded budget");w.write(buf,0,n);}in.closeEntry();values[i]=w.toByteArray();\n            }need(in.getNextEntry()==null,"extra CI member");\n        }\n        String md=StandardCharsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(values[0])).toString();String ref="![Image](assets/image-1.png)";\n        int refs=md.split(java.util.regex.Pattern.quote(ref),-1).length-1;need(refs==2&&!md.contains("PRIVATE_NOTE_SECRET")&&!md.contains("UNSELECTED_ORIGINAL_SECRET"),"wrong referenced selection");\n        android.graphics.Bitmap pic=android.graphics.BitmapFactory.decodeByteArray(values[1],0,values[1].length);\n        need(pic!=null,"invalid received PNG");int w,h;byte[] rgba=new byte[48];try{\n            w=pic.getWidth();h=pic.getHeight();need(w==4&&h==3,"wrong derivative geometry");int[] pixels=new int[12];pic.getPixels(pixels,0,4,0,0,4,3);\n            for(int i=0;i<pixels.length;i++){int c=pixels[i];rgba[4*i]=(byte)(c>>>16);rgba[4*i+1]=(byte)(c>>>8);rgba[4*i+2]=(byte)c;rgba[4*i+3]=(byte)(c>>>24);}\n        }finally{pic.recycle();}\n        JSONObject seen=new JSONObject().put("members",new JSONArray().put(names[0]).put(names[1])).put("markdown_bytes",values[0].length).put("markdown_sha256",sum(values[0])).put("asset_sha256",sum(values[1])).put("pixel_sha256",sum(rgba)).put("width",w).put("height",h).put("references",refs);\n        for(String k:new String[]{"markdown_sha256","asset_sha256","pixel_sha256"})need(seen.getString(k).equals(want.getString(k)),"independent "+k);\n        for(String k:new String[]{"markdown_bytes","width","height","references"})need(seen.getInt(k)==want.getInt(k),"independent "+k);\n        need(seen.getJSONArray("members").toString().equals(want.getJSONArray("members").toString()),"independent members");return seen;\n    }\n    @Override public void onCreate(Bundle saved){super.onCreate(saved);\n        final Intent received=getIntent();final Path root=getFilesDir().toPath(), result=root.resolve("receipt.json");\n        new Thread(()->{JSONObject out=new JSONObject();boolean ok=false;\n            try {\n                need(!Files.exists(result),"old receipt");Path ready=root.resolve("expected.json");\n                need(Files.isRegularFile(ready) && Files.size(ready)>0 && Files.size(ready)<65536,"missing bounded receiver-side expectation");\n                JSONObject e=new JSONObject(new String(Files.readAllBytes(ready),StandardCharsets.UTF_8));\n                String pkg=e.getString("sender"), mime=e.getString("mime"),nonce=e.getString("nonce");\n                need(e.getInt("api")==android.os.Build.VERSION.SDK_INT && nonce.matches("[0-9a-f]{32}") && e.getString("source").matches("[0-9a-f]{40}") && e.getString("run").matches("[0-9]+"),"wrong acceptance identity");\n                out.put("source",e.getString("source"));out.put("run",e.getString("run"));out.put("nonce",nonce);out.put("api",android.os.Build.VERSION.SDK_INT);\n                // The fixture runner records the sender UID independently when seeding expected.json.\n                need(Process.myUid()!=e.getInt("sender_uid"),"receiver must have a different UID");\n                boolean md="application/zip".equals(mime);need((md||"application/pdf".equals(mime)||"image/png".equals(mime)) && mime.equals(received.getType()),"wrong MIME");\n                JSONArray items=e.getJSONArray("files");int count=items.length();need(count>=1&&count<=64&&((!md&&!"application/pdf".equals(mime))||count==1),"invalid count");\n                boolean single=count==1;need((single?Intent.ACTION_SEND:Intent.ACTION_SEND_MULTIPLE).equals(received.getAction()),"wrong action");\n                int flags=received.getFlags();need((flags&Intent.FLAG_GRANT_READ_URI_PERMISSION)!=0 && (flags&(Intent.FLAG_GRANT_WRITE_URI_PERMISSION|Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION|Intent.FLAG_GRANT_PREFIX_URI_PERMISSION))==0,"not a temporary exact read grant");\n                List<Uri> uris=single?Collections.singletonList((Uri)received.getParcelableExtra(Intent.EXTRA_STREAM)):received.getParcelableArrayListExtra(Intent.EXTRA_STREAM);\n                ClipData clip=received.getClipData();need(uris!=null && uris.size()==count && clip!=null && clip.getItemCount()==count,"stream/clip count");\n                JSONArray observed=new JSONArray();long total=0;\n                for(int i=0;i<count;i++){\n                    JSONObject w=items.getJSONObject(i);Uri uri=uris.get(i);\n                    need(uri!=null && uri.equals(clip.getItemAt(i).getUri()) && "content".equals(uri.getScheme()) && (pkg+".exports").equals(uri.getAuthority()),"unexpected stream or clip");\n                    need(checkUriPermission(uri,Process.myPid(),Process.myUid(),Intent.FLAG_GRANT_READ_URI_PERMISSION)==PackageManager.PERMISSION_GRANTED && checkUriPermission(uri,Process.myPid(),Process.myUid(),Intent.FLAG_GRANT_WRITE_URI_PERMISSION)!=PackageManager.PERMISSION_GRANTED,"wrong actual grant");\n                    Uri sibling=uri.buildUpon().appendPath("unlisted-synthetic").build();\n                    need(checkUriPermission(sibling,Process.myPid(),Process.myUid(),Intent.FLAG_GRANT_READ_URI_PERMISSION)!=PackageManager.PERMISSION_GRANTED,"unexpected sibling grant");\n                    need(mime.equals(getContentResolver().getType(uri)),"provider MIME mismatch");String canonical=md?"PocketTodo-notes.zip":"application/pdf".equals(mime)?"PocketTodo-notes.pdf":String.format(Locale.ROOT,"page-%03d.png",i+1);\n                    need(canonical.equals(w.getString("name")),"bad independent name");long bytes=w.getLong("bytes");need(bytes>0&&bytes<=16777216-total,"invalid expected size");\n                    try(Cursor c=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE},null,null,null)){\n                        need(c!=null&&c.moveToFirst()&&canonical.equals(c.getString(0))&&c.getLong(1)==bytes&&!c.moveToNext(),"provider name or size mismatch");}\n                    if(md){need(bytes<=65536&&uri.getEncodedPath().matches("/exports/export-[0-9A-Za-z_-]{1,80}/PocketTodo-notes\\\\.zip")&&uri.getEncodedFragment()==null&&uri.getEncodedQuery()==null,"exact Markdown stream");}\n                    ByteArrayOutputStream captured=md?new ByteArrayOutputStream():null;MessageDigest hash=MessageDigest.getInstance("SHA-256");long read=0;\n                    try(InputStream in=getContentResolver().openInputStream(uri)){need(in!=null,"receiver could not open stream");byte[] buf=new byte[16384];int n;while((n=in.read(buf))!=-1){need(n>0&&n<=bytes-read,"receiver length mismatch");hash.update(buf,0,n);if(captured!=null)captured.write(buf,0,n);read+=n;}}\n                    String sha=hex(hash.digest());need(read==bytes && sha.equals(w.getString("sha256")),"receiver byte identity mismatch");total+=read;\n                    if(md){out.put("markdown_archive",inspectMarkdown(captured.toByteArray(),e.getJSONObject("markdown_archive")));out.put("run_attempt",e.getString("run_attempt"));out.put("receiver_uid",Process.myUid());out.put("action",received.getAction());out.put("mime",received.getType());out.put("readonly_exact",true);}\n                    observed.put(new JSONObject().put("name",canonical).put("bytes",read).put("sha256",sha));\n                }\n                out.put("observed",observed);out.put("scope","SYNTHETIC_DISTINCT_UID_RECEIVER_NOT_REAL_APP_UX");out.put("status","PASS");ok=true;\n            } catch(Exception failure){try{out.put("status","FAIL");out.put("error",failure.getClass().getSimpleName()+": "+failure.getMessage());}catch(Exception ignored){}}\n            // Exclusive create; even on duplicate invocation the original first receipt survives.\n            // The host reads only after the independent checksum completion marker exists.\n            try {byte[] body=out.toString().getBytes(StandardCharsets.UTF_8);\n                Files.write(result,body,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);\n                String checksum=hex(MessageDigest.getInstance("SHA-256").digest(body));\n                Files.write(root.resolve("receipt.complete"),checksum.getBytes(StandardCharsets.US_ASCII),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);\n            }catch(Exception publication){ok=false;}\n            final boolean success=ok;runOnUiThread(()->{setResult(success?RESULT_OK:RESULT_CANCELED);finish();});\n        },"read-export-probe").start();\n    }\n}\n'
RECEIVER_MANIFEST = '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.supercubegame.pockettodo.exportprobe">\n  <uses-sdk android:minSdkVersion="26" android:targetSdkVersion="34" />\n  <application android:label="PocketTodo CI Receiver" android:allowBackup="false" android:debuggable="true">\n    <activity android:name=".ReceiverActivity" android:exported="true">\n      <intent-filter><action android:name="android.intent.action.SEND"/><category android:name="android.intent.category.DEFAULT"/><data android:mimeType="application/pdf"/><data android:mimeType="application/zip"/><data android:mimeType="image/png"/></intent-filter>\n      <intent-filter><action android:name="android.intent.action.SEND_MULTIPLE"/><category android:name="android.intent.category.DEFAULT"/><data android:mimeType="image/png"/></intent-filter>\n    </activity>\n  </application>\n</manifest>\n'

def publish_receiver_ack(marker,write_verified,rename):
    assert re.fullmatch(r'cache/paged-contract-[0-9]+/ack-[a-f0-9]{32}',marker), 'unknown sender ack path'
    temp=marker+'.part';write_verified(temp);rename(temp,marker)

CHOOSER_FIXTURES={
'android/graphics/Rect.java':r'''
package android.graphics;
public class Rect {public int left,top,right,bottom;public Rect(){} public Rect(int l,int t,int r,int b){set(l,t,r,b);}public void set(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;}public boolean isEmpty(){return right<=left||bottom<=top;}public boolean contains(Rect r){return !isEmpty()&&!r.isEmpty()&&r.left>=left&&r.top>=top&&r.right<=right&&r.bottom<=bottom;}public String flattenToString(){return left+" "+top+" "+right+" "+bottom;}}
''',
'android/view/accessibility/AccessibilityNodeInfo.java':r'''
package android.view.accessibility;
import android.graphics.Rect;
import java.util.*;
public class AccessibilityNodeInfo {
 public static final int ACTION_CLICK=16,ACTION_EXPAND=262144; public int actions,expands; public static AccessibilityNodeInfo obtain(AccessibilityNodeInfo n){return n;} public int getActions(){return actions;} public void recycle(){} public static final String SYSTEM="com.google.android.intentresolver";
 public String name="", alt="", pkg=SYSTEM, cls="android.view.View", id="", result=""; public int window=7,calls; public boolean clickable,visible=true,enabled=true,scroll,collection,accept=true; public Rect b=new Rect(10,10,60,60);
 public AccessibilityNodeInfo parent; public final List<AccessibilityNodeInfo> children=new ArrayList<>();
 public AccessibilityNodeInfo(String t,boolean click){name=t;clickable=click;}
 public void add(AccessibilityNodeInfo n){children.add(n);n.parent=this;}
 public CharSequence getText(){return name;} public CharSequence getContentDescription(){return alt;} public CharSequence getPackageName(){return pkg;} public CharSequence getClassName(){return cls;} public String getViewIdResourceName(){return id;} public int getWindowId(){return window;}
 public boolean isClickable(){return clickable;} public boolean isEnabled(){return enabled;} public boolean isVisibleToUser(){return visible;} public boolean isScrollable(){return scroll;} public Object getCollectionInfo(){return collection?this:null;} public AccessibilityNodeInfo getParent(){return parent;} public int getChildCount(){return children.size();} public AccessibilityNodeInfo getChild(int i){return children.get(i);}
 public void getBoundsInScreen(Rect v){v.set(b.left,b.top,b.right,b.bottom);} public boolean performAction(int a){if(a==ACTION_EXPAND){expands++;return accept;}if(a!=ACTION_CLICK)throw new AssertionError();calls++;return accept;}
 public List<AccessibilityNodeInfo> findAccessibilityNodeInfosByText(String s){List<AccessibilityNodeInfo> r=new ArrayList<>();if(name.contains(s)||alt.contains(s))r.add(this);for(AccessibilityNodeInfo n:children)if(n!=null)r.addAll(n.findAccessibilityNodeInfosByText(s));return r;}
}
''',
'Harness.template':r'''
import android.view.accessibility.AccessibilityNodeInfo;import android.graphics.Rect;import java.util.*;
public class ChoiceHarness {
@@HELPER@@
 static AccessibilityNodeInfo n(String t,boolean click){return new AccessibilityNodeInfo(t,click);} static void ok(boolean b){if(!b)throw new AssertionError("CHOOSER_CONTRACT");}
 static class Tree {AccessibilityNodeInfo root=n("",false),row=n("",true),label=n(ChooserChoice.LABEL,false);Tree(){root.b=new Rect(0,0,400,800);row.b=new Rect(4,5,90,90);root.add(row);row.add(label);} }
 static void scenario(String kind){Tree t=new Tree();ChooserChoice.Gate g=new ChooserChoice.Gate();boolean healthy=kind.equals("ok")||kind.equals("platform26")||kind.equals("aosp34")||kind.equals("direct")||kind.equals("icon")||kind.equals("tree_recovered")||kind.equals("same_named_hidden_elsewhere");
  if(kind.equals("platform26")||kind.equals("aosp34"))t.root.pkg=t.row.pkg=t.label.pkg=kind.equals("platform26")?"android":"com.android.intentresolver";
  if(kind.equals("direct")){t.row.clickable=false;t.label.clickable=true;}
  if(kind.equals("icon")){AccessibilityNodeInfo img=n("",false);img.alt=ChooserChoice.LABEL;t.row.add(img);}
  if(kind.equals("shared"))t.row.add(n("Other fixture",false));
  if(kind.equals("other_description"))t.row.alt="Other fixture";
  if(kind.equals("extra_click"))t.row.add(n("",true));
  if(kind.equals("grid"))t.row.collection=true;
  if(kind.equals("nonclick"))t.row.clickable=false;
  if(kind.equals("hidden"))t.label.visible=false;
  if(kind.equals("disabled"))t.row.enabled=false;
  if(kind.equals("substring"))t.label.name+=" 2";
  if(kind.equals("duplicate"))t.root.add(n(ChooserChoice.LABEL,true));
  if(kind.equals("same_named_hidden_elsewhere")){AccessibilityNodeInfo extra=n(ChooserChoice.LABEL,true);extra.visible=false;t.root.add(extra);}
  if(kind.equals("different_owner"))t.root.pkg=t.row.pkg=t.label.pkg="com.example.notchooser";
  if(kind.equals("mixed_window"))t.label.window++;
  if(kind.equals("wrong_owner_child"))t.label.pkg="com.example.other";
  if(kind.equals("detached"))t.row.parent=null;
  if(kind.equals("outside"))t.label.b=new Rect(10,10,100,100);
  if(kind.equals("empty"))t.label.b=new Rect(0,0,0,0);
  if(kind.equals("refused"))t.row.accept=false;
  if(kind.equals("tree_recovered")){t.label.visible=false;ok(!g.act(ChooserChoice.sample(t.root),0,20000));t.label.visible=true;}
  ChooserChoice c=ChooserChoice.sample(t.root);boolean first=g.act(c,100,20000);
  if(kind.equals("shifted"))t.row.b=new Rect(3,5,90,90);
  if(kind.equals("rebound")){AccessibilityNodeInfo b=n(ChooserChoice.LABEL,false);t.row.children.clear();t.row.add(b);t.label=b;}
  if(kind.equals("intervening"))g.act(ChooserChoice.sample(null),200,20000);
  long at=kind.equals("late")?20000:kind.equals("too_soon")?200:350;
  boolean second=false;try{second=g.act(ChooserChoice.sample(t.root),at,20000);ok(!kind.equals("refused"));}catch(AssertionError e){if(!kind.equals("refused")||!e.getMessage().contains("refused a single"))throw e;}
  if(healthy){ok(first||second);ok(!g.act(ChooserChoice.sample(t.root),450,20000));ok(t.row.calls+t.label.calls==1);}else if(kind.equals("refused")){ok(!g.act(ChooserChoice.sample(t.root),450,20000));ok(t.row.calls==1);}else {ok(!first&&!second&&t.row.calls+t.label.calls==0);}
  System.out.println("CHOICE_CASE "+kind+" PASS");
 }
 public static void main(String[] args){for(String a:args)scenario(a);}
}
''',
}

def chooser_tile_selftest():
    segment=JAVA[JAVA.index(' static final class ChooserChoice {'):JAVA.index(' static void receiverUi(')]
    cases='ok platform26 aosp34 direct icon tree_recovered same_named_hidden_elsewhere shared other_description extra_click grid nonclick hidden disabled substring duplicate different_owner mixed_window wrong_owner_child detached outside empty refused shifted rebound intervening late too_soon'.split()
    assert len(set(cases))==len(cases)==28
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder); stub=[]
        for n,t in CHOOSER_FIXTURES.items():
            if n.endswith('.java'):
                f=root/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(t);stub.append(str(f))
        def compiled(s):
            f=root/'ChoiceHarness.java';f.write_text(CHOOSER_FIXTURES['Harness.template'].replace('@@HELPER@@',s));cmd=['javac'] if shutil.which('javac') else ['java','-m','jdk.compiler/com.sun.tools.javac.Main'];subprocess.run([*cmd,'-d',folder,*stub,str(f)],check=True,timeout=30)
        def trial(names):return subprocess.run(['java','-cp',folder,'ChoiceHarness',*names],text=True,capture_output=True,timeout=20)
        compiled(segment);p=trial(cases);assert p.returncode==0 and p.stdout.splitlines()==['CHOICE_CASE '+n+' PASS' for n in cases],(p.stdout,p.stderr)
        mutants=[('if((!t.isEmpty()&&!LABEL.equals(t))||(!alt.isEmpty()&&!LABEL.equals(alt)))','if(false)','shared'),('||!c.key.equals(previous.key)','', 'shifted'),('attempted||now>=end','attempted','late'),('if(!system(owner))','if(false)','different_owner')]
        for a,b,case in mutants:
            assert segment.count(a)==1,a;compiled(segment.replace(a,b,1));good=trial(['ok']);bad=trial([case]);assert good.returncode==0 and bad.returncode!=0 and 'CHOOSER_CONTRACT' in bad.stderr,(case,good.stderr,bad.stderr)
        # The exercised class must actually guard the chooser; no alternate click or coordinate fallback.
        dispatch=JAVA.split(' static void receiverUi(',1)[1].split(' public static void verify(',1)[0];loop=dispatch.split('long end=android.os.SystemClock.elapsedRealtime()+20000;',1)[1].split('File ack=',1)[0]
        assert loop.count('ChooserChoice.sample(inst.getUiAutomation().getRootInActiveWindow())')==1 and loop.count('choice.act(c,android.os.SystemClock.elapsedRealtime(),end)')==1 and 'performAction(' not in dispatch and 'injectInputEvent' not in dispatch
        assert segment.count('performAction(AccessibilityNodeInfo.ACTION_CLICK)')==1
    print('CHOOSER_TILE_HOST 28 actual selector scenarios, 4 witnessed mutants; synthetic accessibility nodes, NOT_DEVICE_ACCEPTANCE',flush=True)

def bounded_drawer_selftest():
    """Real helper/selector running on a synthetic Android-14 tree. No device acceptance here."""
    import inspect
    j=JAVA[JAVA.index(' static final class ChooserChoice {'):JAVA.index(' static void receiverUi(')]
    cases=('visible_first reveal_then_visible still_hidden reveal_refused description_only too_soon at_deadline cost_deadline '
           'other_owner mixed_child other_window unstable_window rebound_drawer rebound_label bounds_change interrupted different_reason '
           'wrong_id wrong_class disabled not_scrollable outside_box empty_box no_action hidden_drawer unrelated_drawer prefix_sibling '
           'two_hidden two_expand visible_description no_label partial capped foreign_root no_root api26 png other_case').split()
    assert len(set(cases))==len(cases)
    host=r''' static final class Sheet {
      AccessibilityNodeInfo root=item("",false), drawer=item("",false), row=item("",true), label=item(ChooserChoice.LABEL,false);
      DrawerReveal reveal=new DrawerReveal();ChooserChoice.Gate selector=new ChooserChoice.Gate();int api=34;String file="paged.pdf";
      static AccessibilityNodeInfo item(String s,boolean click){AccessibilityNodeInfo n=new AccessibilityNodeInfo(s,click);n.pkg="com.android.intentresolver";return n;}
      Sheet(){root.b=new Rect(0,0,400,800);drawer.b=new Rect(0,0,400,790);row.b=new Rect(4,5,95,95);drawer.id="android:id/contentPanel";drawer.cls="android.widget.ScrollView";drawer.scroll=true;drawer.actions=AccessibilityNodeInfo.ACTION_EXPAND;
       root.add(drawer);drawer.add(row);row.add(label);label.visible=false;for(int i=0;i<61;i++){AccessibilityNodeInfo n=item("",false);if(i==0)n.scroll=true;drawer.add(n);} }
      boolean pulse(long t){ChooserChoice c=ChooserChoice.sample(root);boolean result=selector.act(c,t,20000);if(!result)reveal.consider(api,file,c.reason,root,()->t,20000);return result;}
      void exact(int ex,int click){ok(drawer.expands==ex&&row.calls==click);ArrayDeque<AccessibilityNodeInfo> q=new ArrayDeque<>();q.add(root);while(!q.isEmpty()){AccessibilityNodeInfo n=q.remove();if(n!=row)ok(n.calls==0);if(n!=drawer)ok(n.expands==0);for(AccessibilityNodeInfo c:n.children)if(c!=null)q.add(c);}}
    }
    static void drawerCase(String name){Sheet h=new Sheet();AccessibilityNodeInfo d=h.drawer,l=h.label,root=h.root;long first=100,last=350;
      if(name.equals("visible_first")){l.visible=true;ok(!h.pulse(first));ok(h.pulse(last));h.exact(0,1);}
      else if(name.equals("reveal_then_visible")){ok(!h.pulse(first));h.exact(0,0);ok(!h.pulse(180));h.exact(0,0);ok(!h.pulse(last));h.exact(1,0);l.visible=true;d.actions=0;ok(!h.pulse(600));h.exact(1,0);ok(h.pulse(850));ok(!h.pulse(1100));h.exact(1,1);}
      else if(name.equals("still_hidden")||name.equals("reveal_refused")||name.equals("description_only")){if(name.equals("reveal_refused"))d.accept=false;if(name.equals("description_only")){l.name="";l.alt=ChooserChoice.LABEL;}
       ok(!h.pulse(first)&&!h.pulse(last));h.exact(1,0);ok(h.reveal.status.equals(d.accept?"accepted":"refused"));if(name.equals("description_only"))l.visible=true;
       for(long t=550;t<=20000;t+=200)ok(!h.pulse(t));h.exact(1,0);ok(h.reveal.used);}
      else if(name.equals("cost_deadline")){long[] now={first};boolean[] crossing={false};AccessibilityNodeInfo late=new AccessibilityNodeInfo("",false){@Override public boolean equals(Object other){if(crossing[0])now[0]=20000;return super.equals(other);}@Override public int hashCode(){return super.hashCode();}};
       late.pkg=d.pkg;late.b=d.b;late.id=d.id;late.cls=d.cls;late.scroll=d.scroll;late.actions=d.actions;root.children.clear();root.add(late);for(AccessibilityNodeInfo x:d.children)late.add(x);h.drawer=late;
       h.reveal.consider(34,h.file,"no_exact_visible_label",root,()->now[0],20000);now[0]=last;crossing[0]=true;h.reveal.consider(34,h.file,"no_exact_visible_label",root,()->now[0],20000);h.exact(0,0);ok(now[0]==20000&&!h.reveal.used);}
      else if(name.equals("different_reason")||name.equals("no_root")){for(long t:new long[]{first,last})h.reveal.consider(34,h.file,name.equals("different_reason")?"shared_action":"no_exact_visible_label",name.equals("no_root")?null:root,()->t,20000);h.exact(0,0);}
      else if(Arrays.asList("unstable_window","rebound_drawer","rebound_label","bounds_change","interrupted").contains(name)){
       h.pulse(first);if(name.equals("unstable_window")){d.window++;h.pulse(250);d.window--;}
       if(name.equals("interrupted"))h.reveal.consider(34,h.file,"duplicate_label",root,()->230,20000);
       if(name.equals("bounds_change"))d.b=new Rect(0,0,400,780);
       if(name.equals("rebound_drawer")){AccessibilityNodeInfo nd=Sheet.item("",false);nd.b=d.b;nd.id=d.id;nd.cls=d.cls;nd.scroll=d.scroll;nd.actions=d.actions;root.children.clear();root.add(nd);for(AccessibilityNodeInfo x:d.children)nd.add(x);h.drawer=nd;}
       if(name.equals("rebound_label")){AccessibilityNodeInfo nl=Sheet.item(ChooserChoice.LABEL,false);nl.visible=false;h.row.children.clear();h.row.add(nl);h.label=nl;}
       h.pulse(last);h.exact(0,0);h.pulse(650);h.exact(1,0);}
      else{
       if(name.equals("too_soon"))last=first+149;if(name.equals("at_deadline"))last=20000;
       if(name.equals("other_owner"))d.pkg="com.other";if(name.equals("foreign_root"))root.pkg="android";
       if(name.equals("mixed_child"))d.children.get(2).pkg="com.other";if(name.equals("other_window"))l.window++;
       if(name.equals("wrong_id"))d.id="com.android.intentresolver:id/contentPanel";if(name.equals("wrong_class"))d.cls="android.widget.Button";
       if(name.equals("disabled"))d.enabled=false;if(name.equals("not_scrollable"))d.scroll=false;if(name.equals("no_action"))d.actions=AccessibilityNodeInfo.ACTION_CLICK;
       if(name.equals("hidden_drawer"))d.visible=false;if(name.equals("outside_box"))d.b=new Rect(-1,3,300,300);if(name.equals("empty_box"))d.b=new Rect();
       if(name.equals("unrelated_drawer")){d.children.remove(h.row);root.add(h.row);}
       if(name.equals("prefix_sibling")){d.children.remove(h.row);root.children.clear();root.add(Sheet.item("",false));root.add(d);for(int i=0;i<8;i++)root.add(Sheet.item("",false));root.add(h.row);}
       if(name.equals("two_hidden")){AccessibilityNodeInfo copy=Sheet.item(ChooserChoice.LABEL,false);copy.visible=false;d.add(copy);}
       if(name.equals("two_expand")){AccessibilityNodeInfo extra=Sheet.item("",false);extra.actions=AccessibilityNodeInfo.ACTION_EXPAND;root.add(extra);}
       if(name.equals("visible_description")){AccessibilityNodeInfo other=Sheet.item("",false);other.alt=ChooserChoice.LABEL;root.add(other);}
       if(name.equals("no_label"))l.name="Other fixture";if(name.equals("partial"))d.children.add(null);
       if(name.equals("capped"))for(int i=0;i<64;i++)root.add(Sheet.item("",false));if(name.equals("api26"))h.api=26;
       if(name.equals("png"))h.file="picture.zip";if(name.equals("other_case"))h.file="other.pdf";
       ok(!h.pulse(first)&&!h.pulse(last));h.exact(0,0);
      }h.reveal.clear();System.out.println("REVEAL_CASE "+name+" PASS");}
     public static void main(String[] args){String pkg="com.supercubegame.pockettodo.v12.preview";ok(DrawerReveal.fixtureScope(34,pkg,"ranchu","paged.pdf"));ok(!DrawerReveal.fixtureScope(26,pkg,"ranchu","paged.pdf")&&!DrawerReveal.fixtureScope(34,"com.other","ranchu","paged.pdf")&&!DrawerReveal.fixtureScope(34,pkg,"physical","paged.pdf")&&!DrawerReveal.fixtureScope(34,pkg,"ranchu","paged.zip"));for(String c:args)drawerCase(c);}}'''
    with tempfile.TemporaryDirectory() as td:
        r=Path(td);fs=[]
        for n,s in CHOOSER_FIXTURES.items():
            if n.endswith('.java'):
                f=r/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s);fs.append(str(f))
        def trial(seg,modes):
            f=r/'ChoiceHarness.java';f.write_text(CHOOSER_FIXTURES['Harness.template'].split(' public static void main(String[] args)',1)[0].replace('@@HELPER@@',seg)+host)
            cmd=['javac'] if shutil.which('javac') else ['java','-m','jdk.compiler/com.sun.tools.javac.Main'];subprocess.run([*cmd,'-d',td,*fs,str(f)],check=True,timeout=30)
            return subprocess.run(['java','-cp',td,'ChoiceHarness',*modes],capture_output=True,text=True,timeout=20)
        checked=lambda p:[s for s in p.stdout.splitlines() if s.startswith('REVEAL_CASE ')]
        p=trial(j,cases);assert p.returncode==0 and checked(p)==['REVEAL_CASE '+s+' PASS' for s in cases],(p.stdout,p.stderr)
        wrong=[('used=true;status=drawer.n.performAction','used=false;status=drawer.n.performAction','still_hidden'),('expandCount!=1||drawer==null','drawer==null','two_expand'),('||!hidden.path.startsWith(drawer.path+"/")','', 'unrelated_drawer'),('||!drawer.n.equals(previousDrawer)','', 'rebound_drawer'),('if(clock.getAsLong()>=end){reject("action_deadline")','if(false){reject("action_deadline")','cost_deadline'),('drawer.n.performAction(AccessibilityNodeInfo.ACTION_EXPAND)','drawer.n.performAction(AccessibilityNodeInfo.ACTION_CLICK)','reveal_then_visible')]
        for a,b,case in wrong:
            assert j.count(a)==1;bad=trial(j.replace(a,b,1),['visible_first',case]);assert bad.returncode!=0 and checked(bad)==['REVEAL_CASE visible_first PASS'] and 'CHOOSER_CONTRACT' in bad.stderr,(case,bad.stdout,bad.stderr)
    # Every insertion in receiverUi is in the non-pick path; keep the click predicate and byte/ack flow intact.
    loop=JAVA.split(' static void receiverUi(',1)[1].split('File ack=',1)[0].split('long end=android.os.SystemClock.elapsedRealtime()+20000;',1)[1]
    assert loop.count('reveal.consider(')==1 and loop.count('reveal.eligible(android.os.Build.VERSION.SDK_INT,filename,last)')==1
    assert loop.index('picked=choice.act(')<loop.index('else{')<loop.index('reveal.eligible(')<loop.index('reveal.consider(')<loop.index('if(!picked)')
    assert 'reveal.consider(android.os.Build.VERSION.SDK_INT,filename,last,top,android.os.SystemClock::elapsedRealtime,end)' in loop and 'if(top!=null)top.recycle()' in loop
    assert loop.count('if(canReveal&&reveal.eligible(')==1 and JAVA.count('canReveal=DrawerReveal.fixtureScope(android.os.Build.VERSION.SDK_INT,inst.getTargetContext().getPackageName(),android.os.Build.HARDWARE,filename)')==1
    assert len(re.findall(r'\.performAction\(',j))==2 and j.count('performAction(AccessibilityNodeInfo.ACTION_EXPAND)')==1 and j.count('performAction(AccessibilityNodeInfo.ACTION_CLICK)')==1
    assert 'emulator-5554' in inspect.getsource(test_receiver_cases) and "get('GITHUB_ACTIONS')=='true'" in inspect.getsource(test_receiver_cases)
    print(f'DRAWER_HOST {len(cases)} scenarios, {len(wrong)} witnessed mutants; 5 execution-scope controls: expansion != selection != receiver receipt; SYNTHETIC_NOT_ANDROID',flush=True)

def failure_evidence_selftest():
    # The very same selector still refuses a missing/description-only/unrevealed label.
    import contextlib,io
    from unittest.mock import patch
    j=JAVA[JAVA.index(' static final class ChooserChoice {'):JAVA.index(' static void receiverUi(')]
    app='com.supercubegame.pockettodo.v12.preview';recv='com.supercubegame.pockettodo.exportprobe';pre=['adb','-s','emulator-5554'];launch=app+'/com.supercubegame.pockettodo.MainActivity';tile=recv+'/.ReceiverActivity';none='No activities found'
    modes='none desc text both hidden scroll expand private partial oldwin cap deadline foreign null'.split()
    main=r''' public static void main(String[] args){for(String m:args){Tree t=new Tree();t.root.pkg=t.row.pkg=t.label.pkg="com.android.intentresolver";t.label.name="";
      if(m.equals("desc")||m.equals("both"))t.row.alt=ChooserChoice.LABEL;if(m.equals("text")||m.equals("both"))t.label.name=ChooserChoice.LABEL;
      if(m.equals("hidden")){t.label.visible=false;t.label.alt=ChooserChoice.LABEL;}if(m.equals("scroll"))t.root.scroll=true;if(m.equals("expand"))t.root.actions=AccessibilityNodeInfo.ACTION_EXPAND;
      if(m.equals("private"))t.row.alt="PRIVATE_FIXTURE";if(m.equals("partial"))t.row.children.add(null);if(m.equals("oldwin")){t.label.window++;t.label.alt=ChooserChoice.LABEL;}
      if(m.equals("foreign"))t.root.pkg="OTHER_FIXTURE";if(m.equals("cap"))for(int i=0;i<133;i++){AccessibilityNodeInfo n=n(i==132?ChooserChoice.LABEL:"",false);n.pkg=t.root.pkg;t.root.add(n);}
      String x=receiverSurface(m.equals("null")?null:t.root,System.nanoTime()+(m.equals("deadline")?-1:1000000000L));
      ok(t.row.calls+t.label.calls+t.root.calls==0&&!x.contains("PRIVATE_FIXTURE")&&!x.contains("OTHER_FIXTURE")&&!x.contains(ChooserChoice.LABEL));
      if(m.equals("foreign")||m.equals("null"))ok(x.equals("surface=unavailable"));else{
       boolean incomplete=Arrays.asList("partial","oldwin","cap","deadline").contains(m);ok(x.contains("complete="+(!incomplete)+" "));
       ok(x.contains(" visible_exact_text="+((m.equals("text")||m.equals("both"))?1:0)+" "));ok(x.contains(" visible_exact_description="+((m.equals("desc")||m.equals("both"))?1:0)+" "));
       ok(x.contains(" hidden_exact="+(m.equals("hidden")?1:0)+" "));ok(x.contains(" visible_scrollable="+(m.equals("scroll")?1:0)+" "));ok(x.endsWith(" visible_expand_action="+(m.equals("expand")?1:0)));
       if(m.equals("cap"))ok(x.contains(" nodes=128 "));if(m.equals("deadline"))ok(x.contains(" nodes=0 "));
       if(m.equals("desc")||m.equals("none")||m.equals("scroll")){ChooserChoice c=ChooserChoice.sample(t.root);ok(c.row==null&&c.reason.equals("no_exact_visible_label"));}}
      System.out.println("SURFACE "+m+" PASS");}}}'''
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);files=[]
        for name,t in CHOOSER_FIXTURES.items():
            if name.endswith('.java'):
                f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(t);files.append(str(f))
        def trial(segment,ms):
            t=CHOOSER_FIXTURES['Harness.template'].split(' public static void main(String[] args)',1)[0].replace('@@HELPER@@',segment)+main
            f=root/'ChoiceHarness.java';f.write_text(t);cmd=['javac'] if shutil.which('javac') else ['java','-m','jdk.compiler/com.sun.tools.javac.Main'];subprocess.run([*cmd,'-d',folder,*files,str(f)],check=True,timeout=30)
            return subprocess.run(['java','-cp',folder,'ChoiceHarness',*ms],capture_output=True,text=True,timeout=15)
        run=trial(j,modes);assert run.returncode==0 and run.stdout.splitlines()==['SURFACE '+k+' PASS' for k in modes],(run.stdout,run.stderr)
        for a,b,k in [('if(d)desc++;','if(false)desc++;','desc'),('if(!ChooserChoice.sameWindow(n,owner,win)){complete=false;continue;}','if(false){complete=false;continue;}','oldwin'),('if(count>room)complete=false;','if(false)complete=false;','cap')]:
            assert j.count(a)==1;bad=trial(j.replace(a,b,1),['none',k]);assert bad.returncode!=0 and bad.stdout.splitlines()==['SURFACE none PASS'] and 'CHOOSER_CONTRACT' in bad.stderr
    tables=[(launch,none,tile,'matched'),(launch,none,recv+'/'+recv+'.ReceiverActivity','matched'),(launch,none,none,'not_listed'),(none,none,none,'unknown'),(launch,tile,tile,'unknown'),(launch,none,'','unknown'),(launch,none,tile+'\n'+tile,'unknown'),(launch,none,'FOREIGN_FIXTURE/private','unknown'),(launch,none,'NONZERO','unknown'),(launch,none,'STDERR','unknown'),(launch,none,'TIMEOUT','unknown'),(launch,none,'TOO_LONG','unknown')]
    with patch.dict(os.environ,{'GITHUB_ACTIONS':'true'}):
        for pos,neg,target,expect in tables:
            answers=iter([pos,neg,target]);calls=[]
            def execute(cmd,**kw):
                calls.append(cmd);assert cmd[:10]==pre+['shell','cmd','package','query-activities','--components','--user','current'] and kw=={'capture_output':True,'timeout':2,'check':False}
                assert cmd[cmd.index('-p')+1] in (app,recv) and cmd.count('-p')==1;v=next(answers)
                if v=='TIMEOUT':raise subprocess.TimeoutExpired(cmd,2)
                return subprocess.CompletedProcess(cmd,int(v=='NONZERO'),(v if v!='TOO_LONG' else 'x'*513).encode(),b'unrelated' if v=='STDERR' else b'')
            evidence=pdf_route_after_miss(pre,34,app,recv,execute);assert len(calls)==3 and evidence['pdf_match']==expect and 'FOREIGN_FIXTURE' not in str(evidence)
            assert calls[0][10:]==['-a','android.intent.action.MAIN','-c','android.intent.category.LAUNCHER','-p',app] and calls[1][10:]==['-a','android.intent.action.SEND','-c','android.intent.category.DEFAULT','-p',recv,'-t','application/x-pocket-ci-no-receiver'] and calls[2]==calls[1][:-1]+['application/pdf']
        def never(*a,**kw):raise AssertionError('off-scope diagnostic')
        for args in [(pre,26,app,recv),(pre[:-1]+['physical-device'],34,app,recv),(pre,34,'other',recv),(pre,34,app,'other')]:assert pdf_route_after_miss(*args,never)=={'scope':'not_applicable'}
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'false'}):assert pdf_route_after_miss(pre,34,app,recv,never)=={'scope':'not_applicable'}
    failure='java.lang.AssertionError: no stable isolated CI receiver tile; case=paged.pdf reason=no_exact_visible_label observations=97';markers=[]
    def record(*a):markers.append(a);return {'scope':'synthetic_control'}
    def unavailable(*a):raise OSError('PRIVATE_FIXTURE')
    with contextlib.redirect_stdout(io.StringIO()) as buffer:
        for s,k,a in [('SEND_PROBE', 'paged.pdf',34),(failure,'paged.zip',34),(failure,'paged.pdf',26),(failure.replace('no_exact_visible_label','shared_action'),'paged.pdf',34),(failure,'paged.pdf',34)]:note_pdf_miss(s,k,pre,a,app,recv,record)
        note_pdf_miss(failure,'paged.pdf',pre,34,app,recv,unavailable)
    assert len(markers)==1 and len(buffer.getvalue().splitlines())==2 and '"unavailable"' in buffer.getvalue() and 'PRIVATE_FIXTURE' not in buffer.getvalue()
    from inspect import getsource
    body=getsource(test_receiver_cases);tail=body.split('finally:',1)[1];assert tail.count('note_pdf_miss(output,filename,prefix,gate.API,gate.PKG,pkg)')==1 and body.count('note_pdf_miss(')==1 and tail.index("print('RECEIVER_INSTRUMENTATION'")<tail.index('note_pdf_miss(')
    use=JAVA.split(' static void receiverUi(',1)[1].split(' public static void verify(',1)[0];assert use.count('receiverSurface(')==1 and 'if(!picked)' in use and use.index('if(!picked)')<use.index('receiverSurface(')<use.index('File ack=') and '"no_exact_visible_label".equals(last)' in use
    print('AFTER_MISS_HOST %d surface cases / 3 mutants; %d route cases / 5 scope exclusions; success bypass and diagnostic-failure controls; NO_DEVICE_NO_CLICK'%(len(modes),len(tables)),flush=True)

def consent_checkbox(nodes,kind,package):
    if kind not in ("MARKDOWN","PDF","PNG_ZIP"):raise ValueError("unknown preview format")
    expected="我已核对内容与图片，接下来由我选择保存或发送" if kind=="MARKDOWN" else "我已核对预览，接下来由我选择保存或发送"
    matches=[n for n in nodes if n.get("package")==package and n.get("class")=="android.widget.CheckBox"]
    if not matches:return None
    assert len(matches)==1,"ambiguous preview checkbox"
    n=matches[0];assert n.get("text")==expected,"consent wording does not match available actions"
    assert n.get("checkable")=="true" and n.get("checked")=="false" and n.get("enabled")=="true","consent is not fresh and enabled"
    return n

def consent_copy_selftest():
    kind=("MARKDOWN","PDF","PNG_ZIP");copy=["我已核对内容与图片，接下来由我选择保存或发送","我已核对预览，接下来由我选择保存或发送","我已核对预览，接下来由我选择保存或发送"]
    path=Path(__file__).resolve().parents[1]/"src/main/java/com/supercubegame/pockettodo/MainActivity.java"
    method=path.read_text().split("private void previewShare(byte[][] prepared,int format){",1)[1].split("private void finishShare(",1)[0]
    expression=re.findall(r'consent\.setText\(([^;]+)\);body\.addView\(consent\);',method);assert len(expression)==1
    with tempfile.TemporaryDirectory() as tmp:
        def run_compiler(expr):
            file=Path(tmp)/"Text.java";file.write_text('class Text {static String actual(int format){return '+expr+';}public static void main(String[] a){for(int i=0;i<3;i++)System.out.println(actual(i));}}')
            javac=['javac'] if shutil.which('javac') else ['java','-m','jdk.compiler/com.sun.tools.javac.Main'];subprocess.run([*javac,'-d',tmp,str(file)],check=True,timeout=30)
            return subprocess.check_output(['java','-cp',tmp,'Text'],text=True,timeout=15).splitlines()
        actual=run_compiler(expression[0]);assert actual==copy,actual
        for before,after,match in [('format==0','true',[True,False,False]),('format==0','false',[False,True,True])]:
            assert expression[0].count(before)==1;wrong=run_compiler(expression[0].replace(before,after));assert [a==b for a,b in zip(wrong,copy)]==match
    pkg='com.example.fixture';base={'class':'android.widget.CheckBox','package':pkg,'checkable':'true','checked':'false','enabled':'true'}
    for i,k in enumerate(kind):
        n=dict(base,text=copy[i]);assert consent_checkbox([n],k,pkg) is n
        assert consent_checkbox([dict(n,package='other')],k,pkg) is None and consent_checkbox([dict(n,**{'class':'android.widget.TextView'})],k,pkg) is None
        for bad in ([n,n],[dict(n,text=copy[1-i] if i<2 else copy[0])],[dict(n,checked='true')],[dict(n,checkable='false')],[dict(n,enabled='false')]):
            try:consent_checkbox(bad,k,pkg)
            except AssertionError:pass
            else:raise AssertionError('ambiguous, misleading or stale consent accepted')
    print('PREVIEW_CONSENT_COPY 3 actual Java labels, 2 wrong implementations, format-specific node controls; NOT_DEVICE',flush=True)

def receiver_ack_selftest():
    marker='cache/paged-contract-42/ack-'+'a'*32
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);(root/marker).parent.mkdir(parents=True)
        def write(p):
            assert p==marker+'.part' and not (root/marker).exists()
            with (root/p).open('xb') as f:
                assert not (root/marker).exists();f.write(b'checked')
            assert (root/p).read_bytes()==b'checked' and not (root/marker).exists()
        publish_receiver_ack(marker,write,lambda p,q:(root/p).rename(root/q))
        assert (root/marker).read_bytes()==b'checked' and not (root/(marker+'.part')).exists()
    moves=[]
    def stop(p):raise IOError('test write failure')
    try:publish_receiver_ack(marker,stop,lambda a,b:moves.append(b))
    except IOError as e:assert str(e)=='test write failure' and not moves
    else:raise AssertionError('failed write handed off')
    for bad in (marker+'.part',marker[:-1],marker.replace('cache/','other/'),marker.replace('/ack-','/../ack-')):
        try:publish_receiver_ack(bad,lambda p:moves.append(p),lambda a,b:moves.append(b))
        except AssertionError as e:assert str(e)=='unknown sender ack path' and not moves
        else:raise AssertionError('bad ack name allowed')
    print('RECEIVER_ACK_HOST atomic publication, first-write failure and 4 path controls; NOT_DEVICE_ACCEPTANCE',flush=True)

def pdf_route_after_miss(prefix,api,product,receiver,runner=subprocess.run):
    """System package-matcher observation after a failed synthetic PDF send. Never start an activity."""
    if (api!=34 or product!='com.supercubegame.pockettodo.v12.preview' or receiver!='com.supercubegame.pockettodo.exportprobe' or
        len(prefix)!=3 or list(map(str,prefix[1:]))!=['-s','emulator-5554'] or os.environ.get('GITHUB_ACTIONS')!='true'):
        return {'scope':'not_applicable'}
    def query(package,activity,action,cat,mime):
        args=[*map(str,prefix),'shell','cmd','package','query-activities','--components','--user','current','-a','android.intent.action.'+action,'-c','android.intent.category.'+cat,'-p',package]
        if mime:args+=['-t',mime]
        try:p=runner(args,capture_output=True,timeout=2,check=False)
        except (subprocess.TimeoutExpired,OSError):return 'unknown'
        if p.returncode or p.stderr.strip() or len(p.stdout)>512:return 'unknown'
        lines=p.stdout.strip().splitlines()
        if lines==[b'No activities found']:return 'not_listed'
        full=(package+'/'+activity).encode();short=(package+'/.'+activity[len(package)+1:]).encode() if activity.startswith(package+'.') else full
        return 'matched' if lines in ([short],[full]) else 'unknown'
    activity=receiver+'.ReceiverActivity';pos=query(product,'com.supercubegame.pockettodo.MainActivity','MAIN','LAUNCHER',None)
    neg=query(receiver,activity,'SEND','DEFAULT','application/x-pocket-ci-no-receiver');pdf=query(receiver,activity,'SEND','DEFAULT','application/pdf')
    return {'scope':'emulator_system_query_after_failure_not_actual_chooser','launcher_control':pos,'unsupported_mime_control':neg,
            'pdf_match':pdf if (pos,neg)==('matched','not_listed') else 'unknown'}

def note_pdf_miss(output,filename,prefix,api,product,receiver,probe=pdf_route_after_miss):
    if (filename!='paged.pdf' or api!=34 or not re.search(r'^java\.lang\.AssertionError: no stable isolated CI receiver tile; case=paged\.pdf reason=no_exact_visible_label ',output,re.M)):
        return
    try:r=probe(prefix,api,product,receiver)
    except Exception:r={'scope':'unavailable'}  # Keep the original exception, never substitute diagnostic success.
    print('RECEIVER_ROUTE_AFTER_MISS '+json.dumps(r,sort_keys=True),flush=True)

MD_PROBE_TEXT=("# Pocket Todo\n\nVisible &#33;&#91;bad&#93;&#40;&#46;&#46;&#47;original&#46;png&#41;\n"
               "&lt;img src&#61;&#34;secret&#34;&gt; &amp; 中文\n\n![Image](assets/image-1.png)\n\nSelected caption\n\n"
               "![Image](assets/image-1.png)\n\nRepeated caption\n\n").encode('utf-8')
MD_PROBE_ARGB=(0xff0a141e,0xff000000,0xff000000,0xff0d1a27,0xff112233,0xff000000,0xff000000,0xff000000,0xff183048,0xff19324b,0xff000000,0xff000000)
def markdown_probe_expected(raw,verified_png):
    """Exact known public selection, not the sender's description of its own outgoing Intent."""
    import io
    assert 0<len(raw)<=65536 and raw[-22:-18]==b'PK\x05\x06' and raw[-2:]==b'\0\0','noncanonical CI archive end'
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist();assert names==['notes.md','assets/image-1.png'] and z.comment==b'','selected Markdown members'
        for e in z.infolist():assert not e.is_dir() and e.comment==b'' and 0<e.file_size<=65536
        doc=z.read(names[0]);png=z.read(names[1]);assert doc==MD_PROBE_TEXT,'exact selected text, literal escaping and ordered duplicate references';assert png==verified_png and png.startswith(b'\x89PNG\r\n\x1a\n'),'independently decoded derivative bytes'
    rgba=bytes(q for c in MD_PROBE_ARGB for q in ((c>>16)&255,(c>>8)&255,c&255,(c>>24)&255));sha=lambda b:hashlib.sha256(b).hexdigest()
    return dict(members=names,markdown_bytes=len(doc),markdown_sha256=sha(doc),asset_sha256=sha(png),pixel_sha256=sha(rgba),width=4,height=3,references=2)

def markdown_receiver_selftest():
    # Exercise the real receiver-side expectation reader and report verifier. Android pixel decoding is a separate device obligation.
    import io,copy,base64
    known=base64.b64decode('iVBORw0KGgo=')+b'fixture-already-decoded-by-independent-codec'
    def make(members):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
            for k,v in members:z.writestr(k,v)
        return b.getvalue()
    parts=[('notes.md',MD_PROBE_TEXT),('assets/image-1.png',known)];wire=make(parts);doc=markdown_probe_expected(wire,known)
    e=dict(nonce='1'*32,api=26,source='a'*40,run='123',run_attempt='1',mime='application/zip',sender_uid=10077,markdown_archive=doc,files=[dict(name='PocketTodo-notes.zip',bytes=len(wire),sha256=hashlib.sha256(wire).hexdigest())]);r={k:e[k] for k in ('nonce','api','source','run','run_attempt')};r.update(status='PASS',scope='SYNTHETIC_DISTINCT_UID_RECEIVER_NOT_REAL_APP_UX',observed=copy.deepcopy(e['files']),receiver_uid=10079,mime='application/zip',action='android.intent.action.SEND',readonly_exact=True,markdown_archive=copy.deepcopy(doc))
    assert markdown_receive_check(r,e,10077,10079)['receiver_uid']==10079
    denies=0
    for items in [[(parts[0][0],MD_PROBE_TEXT+b'Unselected'),parts[1]],[(parts[0][0],MD_PROBE_TEXT.replace(b'Repeated caption',b'PRIVATE_NOTE_SECRET')),parts[1]],[parts[1],parts[0]],parts+[('extra',b'public fixture')],[parts[0],(parts[1][0],known+b'changed')],parts[:1]]:
        try:markdown_probe_expected(make(items),known)
        except AssertionError:denies+=1
        else:raise AssertionError('unexpected ZIP content was accepted')
    for k,val in [('nonce','2'*32),('api',34),('source','b'*40),('run','456'),('run_attempt','2'),('status','FAIL'),('scope','HOST'),('receiver_uid',10077),('action','android.intent.action.SEND_MULTIPLE'),('mime','image/png'),('readonly_exact',1),('observed',[]),('observed',r['observed']*2),('observed',[dict(r['observed'][0],sha256='d'*64)]),('markdown_archive',dict(doc,pixel_sha256='e'*64)),('markdown_archive',dict(doc,members=['notes.md'])),('markdown_archive',dict(doc,references=1))]:
        altered=copy.deepcopy(r);altered[k]=val
        try:markdown_receive_check(altered,e,10077,10079)
        except AssertionError:denies+=1
        else:raise AssertionError('accepted an unrelated or incomplete receipt: '+k)
    for sender,receiver in [(10077,10077),(999,10079),(10077,0)]:
        try:markdown_receive_check(r,e,sender,receiver)
        except AssertionError:denies+=1
        else:raise AssertionError('unusable receiver identity')
    assert denies==26;print('MD_RECEIPT_HOST exact document and receipt positives; 26 refused; synthetic bytes not Android image decoding',flush=True)

def markdown_receive_check(r,e,sender_uid,receiver_uid):
    assert type(sender_uid) is int and type(receiver_uid) is int and sender_uid>=10000 and receiver_uid>=10000 and sender_uid!=receiver_uid
    assert r['status']=='PASS' and all(r[k]==e[k] for k in ('nonce','api','source','run','run_attempt'))
    assert r['scope']=='SYNTHETIC_DISTINCT_UID_RECEIVER_NOT_REAL_APP_UX' and r['observed']==e['files'] and len(r['observed'])==1
    assert e['mime']=='application/zip' and r['observed'][0]['name']=='PocketTodo-notes.zip' and e['sender_uid']==sender_uid
    assert r['receiver_uid']==receiver_uid and r['mime']=='application/zip' and r['action']=='android.intent.action.SEND' and r['readonly_exact'] is True
    assert r['markdown_archive']==e['markdown_archive'] and type(r['markdown_archive']['markdown_bytes']) is int
    return dict(r,sender_uid=sender_uid,receiver_uid=receiver_uid)

def test_receiver_cases(folder,prefix,gate,work,root,args,component,cache):
    """Only the generated receiver on a disposable emulator. No user media, implicit recipient or phone."""
    import secrets,time,io
    assert os.environ.get('GITHUB_ACTIONS')=='true' and gate.API in (26,34) and 'emulator-5554' in prefix
    pkg='com.supercubegame.pockettodo.exportprobe'; project=work/'receiver-project'; src=project/'src/main'; (src/'java').mkdir(parents=True)
    (project/'settings.gradle').write_bytes((root/'settings.gradle').read_bytes());(project/'build.gradle').write_text("plugins { id 'com.android.application' version '8.7.3' }\nandroid { namespace '"+pkg+"'; compileSdk 35; defaultConfig { applicationId '"+pkg+"'; minSdk 26; targetSdk 34 } }\n")
    (src/'AndroidManifest.xml').write_text(RECEIVER_MANIFEST.replace(' package="'+pkg+'"',''));(src/'java/ReceiverActivity.java').write_text(RECEIVER_JAVA)
    run(['gradle','--no-daemon','--console=plain','-p',project,'assembleDebug'],timeout=300)
    apks=list((project/'build/outputs/apk/debug').glob('*.apk'));assert len(apks)==1
    run([*prefix,'install','-t',apks[0]],timeout=120)
    def shell(*v):return run([*prefix,'shell',*v]).strip()
    def uid(p):return int(shell('run-as',p,'id','-u'))
    sender_uid=uid(gate.PKG);receiver_uid=uid(pkg);assert receiver_uid!=sender_uid
    def seed(p,path,raw):
        cmd='run-as '+shlex.quote(p)+' sh -c '+shlex.quote('umask 077; cat > '+shlex.quote(path));subprocess.run([*prefix,'shell',cmd],input=raw,check=True,timeout=20)
        assert read(p,path)==raw
    def read(p,path):return subprocess.check_output([*prefix,'exec-out','run-as',p,'cat',path],timeout=20)
    receipts=[];markdown=None;shell('run-as',pkg,'mkdir','-p','files')
    for filename in ('paged.pdf','picture.zip','paged.zip','share.zip'):
        raw=(folder/filename).read_bytes(); pdf=filename.endswith('.pdf'); nonce=secrets.token_hex(16)
        md=filename=='share.zip'
        if md:parts=[('PocketTodo-notes.zip',raw)]
        elif pdf:parts=[('PocketTodo-notes.pdf',raw)]
        else:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names=z.namelist();assert names==['pages/page-%03d.png'%i for i in range(1,1+len(names))];parts=[(n.split('/')[1],z.read(n)) for n in names]
        assert len(parts)==(3 if filename=='paged.zip' else 1)
        e={'nonce':nonce,'source':os.environ['GITHUB_SHA'],'run':os.environ['GITHUB_RUN_ID'],'api':gate.API,'sender':gate.PKG,'sender_uid':sender_uid,'mime':'application/zip' if md else 'application/pdf' if pdf else 'image/png','files':[dict(name=n,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in parts]}
        if md:e.update(run_attempt=os.environ['GITHUB_RUN_ATTEMPT'],markdown_archive=markdown_probe_expected(raw,(folder/'share-derived.png').read_bytes()))
        for n in ('receipt.complete','receipt.json'):
            shell('run-as',pkg,'rm','-f','files/'+n)
        seed(pkg,'files/expected.json',json.dumps(e).encode());marker=cache+'/ack-'+nonce
        with tempfile.TemporaryFile() as out:
            proc=subprocess.Popen([*map(str,args),'-e','mode','send','-e','payload',filename,'-e','nonce',nonce,component],stdout=out,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+65
                while True:
                    assert proc.poll() is None,'send instrumentation ended before receiver receipt'
                    listed=shell('run-as',pkg,'ls','files').splitlines()
                    if 'receipt.complete' in listed:break
                    if time.monotonic()>=deadline:raise TimeoutError('receiver first receipt missing: '+filename)
                    time.sleep(.3)
                actual=read(pkg,'files/receipt.json');assert read(pkg,'files/receipt.complete')==hashlib.sha256(actual).hexdigest().encode();r=json.loads(actual)
                assert r.get('status')=='PASS' and all(r[k]==e[k] for k in ('nonce','source','run','api')) and r['observed']==e['files'],r
                if md:markdown=markdown_receive_check(r,e,sender_uid,receiver_uid)
                else:print('RECEIVER_BYTES_VERIFIED '+json.dumps(dict(r,sender_uid=sender_uid,receiver_uid=receiver_uid)),flush=True)
                publish_receiver_ack(marker,lambda temp:seed(gate.PKG,temp,b'checked'),lambda temp,final:shell('run-as',gate.PKG,'mv',temp,final))
                assert read(gate.PKG,marker)==b'checked', 'sender ack post-rename readback'
                assert proc.wait(timeout=20)==0
                out.seek(0);output=out.read().decode(errors='replace');assert output.count('CHOOSER_TILE_CLICK '+nonce+' ')==1 and 'SEND_PROBE '+nonce in output and 'INSTRUMENTATION_CODE: -1' in output and 'PAGED_FAILED' not in output,output
                if md:
                    assert output.count('MARKDOWN_GUARDS '+nonce+' unchecked_cancel_stale_no_chooser')==1
                    markdown.update(preview_guards='UNCHECKED_CANCEL_STALE_NO_CHOOSER',completion='SENDER_ACK_EXACT_AND_TERMINAL_INSTRUMENTATION')
                    Path('markdown-system-send.json').write_text(json.dumps(markdown,indent=2)+'\n');print('MARKDOWN_RECEIVER_BYTES_VERIFIED '+json.dumps(markdown),flush=True)
                else:receipts.append(dict(r,sender_uid=sender_uid,receiver_uid=receiver_uid))
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
                out.seek(0);output=out.read()[-4000:].decode(errors='replace');print('RECEIVER_INSTRUMENTATION',filename,output,flush=True)
                note_pdf_miss(output,filename,prefix,gate.API,gate.PKG,pkg)
    assert len(receipts)==3 and markdown is not None
    return receipts,markdown


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
    for name in ("derived.png","over.png","share.zip"):
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
            receiver_receipts,markdown_receipt=test_receiver_cases(folder,prefix,gate,work,root,args,component,cache)
            assert installed_app()==before
        finally:
            assert backup.read_bytes()==saved
            run([*prefix,"install","-r","-t",backup],timeout=120)
            test.write_bytes(saved)
            require_registration(prefix[0],gate,"paged-restored","V12DeviceTest")
            assert app.read_bytes()==before and test.read_bytes()==saved
    return labels,{"runtime":"TARGET_APP_INSTRUMENTATION","diagnostic_failure_rejected":True,"external_receiver":receiver_receipts,"markdown_system_send":markdown_receipt,
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


PAGED_READY_EXTRACTOR='\nimport java.nio.file.*;\nimport java.util.*;\nimport javax.tools.*;\nimport com.sun.source.tree.*;\nimport com.sun.source.util.*;\npublic class Extract {\n static void need(boolean b,String s){if(!b)throw new AssertionError(s);}\n static String called(MethodInvocationTree n){return n.getMethodSelect().toString();}\n static List<MethodInvocationTree> calls(Tree t){\n  List<MethodInvocationTree> r=new ArrayList<>();\n  new TreeScanner<Void,Void>(){\n   public Void visitMethodInvocation(MethodInvocationTree n,Void v){r.add(n);return super.visitMethodInvocation(n,v);}\n  }.scan(t,null);return r;\n }\n public static void main(String[] a)throws Exception{\n  String source=Files.readString(Path.of(a[0]));\n  JavaCompiler c=ToolProvider.getSystemJavaCompiler();\n  DiagnosticCollector<JavaFileObject> d=new DiagnosticCollector<>();\n  try(StandardJavaFileManager fm=c.getStandardFileManager(d,null,null)){\n   JavacTask task=(JavacTask)c.getTask(null,fm,d,List.of("-proc:none"),null,fm.getJavaFileObjects(a[0]));\n   CompilationUnitTree unit=task.parse().iterator().next();\n   need(d.getDiagnostics().stream().noneMatch(x->x.getKind()==Diagnostic.Kind.ERROR),"parse");\n   Map<String,MethodTree> methods=new HashMap<>();\n   ClassTree cls=(ClassTree)unit.getTypeDecls().get(0);\n   for(Tree t:cls.getMembers())if(t instanceof MethodTree){\n    MethodTree m=(MethodTree)t;need(methods.put(m.getName().toString(),m)==null,"duplicate method");\n   }\n   if(a[2].equals("new")){\n    MethodTree preview=methods.get("previewUi");need(preview!=null,"preview absent");\n    List<? extends StatementTree> statements=preview.getBody().getStatements();\n    List<TryTree> tries=new ArrayList<>();\n    for(StatementTree s:statements)if(s instanceof TryTree)tries.add((TryTree)s);\n    need(tries.size()==1,"one outer cleanup");\n    TryTree tr=tries.get(0);\n    List<? extends StatementTree> body=tr.getBlock().getStatements();\n    need(body.size()>=4,"preview body");\n    need(body.get(0).toString().equals("inst.waitForIdleSync();"),"idle inside cleanup");\n    need(body.get(1).toString().equals("awaitPreviewScreen(inst, activity);"),"readiness caller");\n    need(body.get(2) instanceof VariableTree,"snapshot declaration");\n    VariableTree before=(VariableTree)body.get(2);\n    need(before.getName().contentEquals("before")&&before.getInitializer().toString().equals("state(inst, activity)"),"snapshot binding");\n    need(tr.getFinallyBlock()!=null&&tr.getFinallyBlock().getStatements().size()==2,"cleanup retained");\n    need(tr.getFinallyBlock().getStatements().get(0).toString().equals("onUi(inst, activity::finish);"),"finish cleanup");\n    need(tr.getFinallyBlock().getStatements().get(1).toString().equals("inst.waitForIdleSync();"),"cleanup idle");\n    need(calls(preview).stream().filter(x->called(x).equals("awaitPreviewScreen")).count()==1,"one readiness call");\n    List<MethodInvocationTree> snapshots=new ArrayList<>();\n    for(MethodInvocationTree x:calls(preview))if(called(x).equals("state"))snapshots.add(x);\n    need(snapshots.size()==2&&snapshots.stream().allMatch(x->x.toString().equals("state(inst, activity)")),"both snapshots bound");\n    for(StatementTree s:statements)if(s!=tr){\n     need(calls(s).stream().noneMatch(x->Set.of("state","awaitPreviewScreen","inst.waitForIdleSync").contains(called(x))),"startup read outside cleanup");\n    }\n    need(calls(methods.get("verify")).stream().filter(x->x.toString().equals("previewUi(inst, root)")).count()==1,"actual preview entry");\n   }\n   Trees trees=Trees.instance(task);SourcePositions positions=trees.getSourcePositions();\n   StringBuilder out=new StringBuilder();\n   for(String name:List.of("privateMethod","field","onUi","awaitPreviewScreen","state")){\n    MethodTree m=methods.get(name);\n    if(m==null){need(name.equals("awaitPreviewScreen")&&a[2].equals("old"),"missing method "+name);continue;}\n    out.append(source.substring((int)positions.getStartPosition(unit,m),(int)positions.getEndPosition(unit,m))).append("\\n");\n   }\n   Files.writeString(Path.of(a[1]),out.toString());\n  }\n }\n}\n'
PAGED_READY_HARNESS='\nimport java.util.*;\npublic class ReadyTest {\n interface Action{void run()throws Exception;}\n@@METHODS@@\n public static class Database{\n  int reads;\n  public byte[] exportState(){if(android.app.Instrumentation.main)throw new AssertionError("database on UI");reads++;return new byte[]{4,8,15};}\n }\n public static class Screen{public boolean busy;public Database db=new Database();}\n static void need(boolean b,String s){if(!b)throw new AssertionError(s);}\n public static void main(String[] args)throws Exception{\n  String mode=args[0];boolean old=args[1].equals("old");\n  android.app.Activity a=new android.app.Activity();\n  Screen s=new Screen();\n  android.app.Instrumentation inst=new android.app.Instrumentation();\n  android.app.Instrumentation.before=()->{\n   if(mode.equals("late"))android.os.SystemClock.now=10000;\n   boolean delayed=mode.equals("delayed")||mode.equals("never");\n   a.screen=delayed&&android.os.SystemClock.now< (mode.equals("never")?20000:100)?null:s;\n   s.busy=mode.equals("busy")&&android.os.SystemClock.now<100;\n  };\n  a.destroyed=mode.equals("destroyed");a.finishing=mode.equals("finishing");\n  if(mode.equals("ready"))a.screen=s;\n  Throwable failure=null;byte[] result=null;\n  try{\n   @@INVOKE@@\n  }catch(Throwable t){failure=t;}\n  if(old){\n   if(mode.equals("ready"))need(failure==null&&Arrays.equals(result,new byte[]{4,8,15}),"old ready");\n   else need(failure instanceof NullPointerException,"original null-screen RED "+failure);\n  }else if(Set.of("ready","delayed","busy").contains(mode)){\n   need(failure==null&&Arrays.equals(result,new byte[]{4,8,15})&&s.db.reads==1,"new snapshot "+failure);\n   need(android.app.Instrumentation.calls==(mode.equals("ready")?2:4),"main-thread observation and snapshot");\n   need(android.os.SystemClock.now==(mode.equals("ready")?0:100),"bounded poll semantics");\n  }else{\n   need(failure!=null&&s.db.reads==0,"failed readiness must not export");\n   if(mode.equals("never"))need(android.os.SystemClock.now==10000&&android.app.Instrumentation.calls==200,"exact observation cap");\n   if(Set.of("finishing","destroyed","late").contains(mode))need(android.app.Instrumentation.calls==1,"reject during wait, not a later snapshot");\n  }\n  System.out.println("CASE_PASS "+mode+" "+args[1]);\n }\n}\n'
PAGED_OLD_STATE=' static byte[] state(android.app.Activity activity)throws Exception{\n  Object db=field(field(activity,"screen"),"db");\n  return(byte[])privateMethod(db.getClass(),"exportState").invoke(db);\n }\n'

def paged_readiness_selftest():
    """Compile actual method bytes with explicit Android doubles; not device proof."""
    import ast
    import inspect
    import textwrap
    with tempfile.TemporaryDirectory(prefix="paged-readiness-") as directory:
        root=Path(directory)
        (root/"Extract.java").write_text(PAGED_READY_EXTRACTOR)
        def command(args):
            p=subprocess.run(args,text=True,capture_output=True,timeout=40)
            assert p.returncode==0,p.stdout+p.stderr
            return p.stdout
        command(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",str(root),str(root/"Extract.java")])
        def extract(source,mode="new",accept=True):
            (root/"PagedContractTest.java").write_text(source)
            p=subprocess.run(["java","-cp",str(root),"Extract",str(root/"PagedContractTest.java"),
                str(root/"methods.txt"),mode],text=True,capture_output=True,timeout=40)
            assert (p.returncode==0)==accept,p.stdout+p.stderr
            if accept:return (root/"methods.txt").read_text()
            assert "AssertionError" in p.stderr,p.stderr
        actual=extract(JAVA)
        # Actual helper bodies below are extracted from the currently executing JAVA.
        stubs={
          "android/app/Activity.java": "package android.app; public class Activity{public Object screen;public boolean destroyed,finishing;public boolean isDestroyed(){return destroyed;}public boolean isFinishing(){return finishing;}}",
          "android/app/Instrumentation.java": "package android.app; public class Instrumentation{public static boolean main;public static int calls;public static Runnable before=()->{};public void runOnMainSync(Runnable r){calls++;main=true;try{before.run();r.run();}finally{main=false;}}}",
          "android/os/SystemClock.java": "package android.os; public class SystemClock{public static long now;public static long uptimeMillis(){return now;}public static void sleep(long n){if(android.app.Instrumentation.main)throw new AssertionError(\"sleep on UI\");now+=n;}}",
        }
        for name,body in stubs.items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
        def compile_methods(methods,old=False):
            invoke="result=state(a);" if old else "awaitPreviewScreen(inst,a); result=state(inst,a);"
            code=PAGED_READY_HARNESS.replace("@@METHODS@@",methods).replace("@@INVOKE@@",invoke)
            (root/"ReadyTest.java").write_text(code)
            command(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",str(root),
                     str(root/"ReadyTest.java"),*[str(root/name) for name in stubs]])
        def case(name,old=False,accept=True):
            p=subprocess.run(["java","-cp",str(root),"ReadyTest",name,"old" if old else "new"],
                             text=True,capture_output=True,timeout=10)
            assert (p.returncode==0)==accept,p.stdout+p.stderr
            if not accept:assert "AssertionError" in p.stderr,p.stderr
        compile_methods(actual)
        cases=("ready","delayed","busy","never","finishing","destroyed","late")
        for name in cases:case(name)
        changes=[
          ('screen!=null&&!((Boolean)field(screen,"busy"))','screen!=null',"busy"),
          ('activity.isDestroyed()||activity.isFinishing()','false',"finishing"),
          ('if(observed>=deadline)','if(false)',"late"),
          ('android.os.SystemClock.sleep(Math.min(50,deadline-observed))','android.os.SystemClock.sleep(10000)',"delayed"),
        ]
        for old,new,bad in changes:
            # Lifecycle guard occurs in wait and snapshot; mutate wait only.
            assert old in actual
            mutant=actual.replace(old,new,1);assert mutant!=actual
            compile_methods(mutant);case("ready");case(bad,accept=False)
        # Real original state fragment retained as a regression fixture.
        old_methods=actual[:actual.index("static void awaitPreviewScreen")]+PAGED_OLD_STATE
        compile_methods(old_methods,True);case("ready",True);case("delayed",True)
        # Whole-call omissions use the exact same JDK AST checker.
        omissions=[
          ("awaitPreviewScreen(inst,activity);",""),
          ("previewUi(inst,root);",""),
          ("onUi(inst,activity::finish);",""),
          ("byte[] before=state(inst,activity);","byte[] before=null;"),
        ]
        for old,new in omissions:
            assert JAVA.count(old)==1,old
            extract(JAVA.replace(old,new,1),accept=False)
    print("PAGED_READINESS_HOST cases=7 witnessed_mutants=4 caller_omissions=4 original_null_RED PASS ANDROID_DOUBLES_ONLY",flush=True)

def share_png_fixture(data, hardening):
    """Resolve the old public PNG share target without removing the independently verified JPEG."""
    registry = {r[0]: r for r in data["media"]}
    rows = [r for r in data["blocks"] if r[8] is not None]
    assert len(rows) == 2, "expected both persisted derivative fixtures"
    for row in rows:
        assert row[3] == "IMAGE" and row[7] == 0 and row[5] != row[8], "unexpected derivative privacy, type or identity"
        assert row[8] in registry and row[5] in registry and registry[row[5]][1] == "image/png", "missing source or published PNG"
    png = [r for r in rows if registry[r[8]][1] == "image/png"]
    jpeg = [r for r in rows if registry[r[8]][1] == "image/jpeg"]
    assert len(png) == len(jpeg) == 1, "expected exactly one derivative per source MIME"
    p, j = png[0], jpeg[0]
    assert p[0] != j[0], "JPEG control cannot be in the note selected for PNG export"
    assert hardening.get("status") == "PASS", "missing prior native hardening acceptance"
    proof = hardening["jpeg_source_derivative"]
    assert (j[8], j[5], registry[j[5]][2]) == (proof["source_sha256"], proof["derived_sha256"], proof["derived_bytes"]), "JPEG source or derived identity differs from native evidence"
    siblings = [r for r in data["blocks"] if r[0] == p[0] and r[1] != p[1] and r[3] == "IMAGE" and r[7] == 1 and r[6] == "PRIVATE_SHARE_SENTINEL"]
    assert len(siblings) == 1, "PNG target must belong to the note with the exact private sentinel sibling"
    return p


def share_png_fixture_selftest():
    from copy import deepcopy
    a,b,c,d,e = [hashlib.sha256(v.encode()).hexdigest() for v in ("p-src","p-out","j-src","j-out","private")]
    p=("s","image-p",0,"IMAGE","",b,"",0,a); j=("f","image-j",0,"IMAGE","",d,"",0,c)
    witness=("s","sibling",1,"IMAGE","",e,"PRIVATE_SHARE_SENTINEL",1,None)
    media=[(a,"image/png",200),(b,"image/png",180),(c,"image/jpeg",250),(d,"image/png",170),(e,"image/png",160)]
    h={"status":"PASS","jpeg_source_derivative":{"source_sha256":c,"derived_sha256":d,"derived_bytes":170}}
    build=lambda rs,ms: {"blocks":list(rs),"media":list(ms)}
    for rows in ((p,j,witness),(j,witness,p)):
        assert share_png_fixture(build(rows,media),h) == p
    def edit(row,i,val):
        out=row[:i]+(val,)+row[i+1:]; assert out!=row; return out
    def wrong_proof(key,value):
        broken=deepcopy(h); broken["jpeg_source_derivative"][key]=value; assert broken!=h;return broken
    cases=[((p,witness),media,h),((j,witness),media,h),((p,j,j,witness),media,h),
           ((p,edit(j,0,p[0]),witness),media,h),((edit(p,7,1),j,witness),media,h),
           ((p,edit(j,7,1),witness),media,h),((p,edit(j,5,c),witness),media,h),
           ((p,j,edit(witness,6,"other")),media,h),((p,j,witness),media[1:],h),
           ((p,j,witness),[edit(m,1,"image/png") if m[0]==c else m for m in media],h),
           ((p,j,witness),media,wrong_proof("source_sha256",a)),
           ((p,j,witness),media,wrong_proof("derived_sha256",b)),
           ((p,j,witness),media,wrong_proof("derived_bytes",171)),
           ((p,j,witness),media,dict(h,status="FAIL"))]
    for rows,ms,proof in cases:
        try:share_png_fixture(build(rows,ms),proof)
        except AssertionError:pass
        else:raise AssertionError("invalid derivative fixture was accepted")
    return {"positive":2,"negative":len(cases)}


MD_WIRE_HOST = r'''
package com.supercubegame.pockettodo;
import android.content.*;import android.net.Uri;import java.util.*;import java.util.zip.*;import java.io.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;import java.security.*;import javax.imageio.ImageIO;
public class MarkdownWireHost{
 static final String DOC="PocketTodo-notes.zip",ZIP="application/zip",START="# Pocket Todo\n\n",REF="![Image](assets/image-1.png)\n\n",PKG="com.example.fixture";static int n;static Path root;static Context ctx;
 interface Op{void go()throws Exception;}static void ok(boolean v,String s){if(!v)throw new AssertionError(s);n++;System.out.println("MD_HOST "+s);}
 static void reject(Op o,String stage,String name)throws Exception{try{o.go();}catch(IOException|IllegalArgumentException e){if(!stage.isEmpty()&&!String.valueOf(e.getMessage()).contains(stage))throw new AssertionError("wrong cause "+name,e);ok(true,name);return;}throw new AssertionError("accepted "+name);}
 static byte[] text(String s){return s.getBytes(StandardCharsets.UTF_8);}static byte[] png(int rgb)throws Exception{var b=new java.awt.image.BufferedImage(4,3,java.awt.image.BufferedImage.TYPE_INT_ARGB);for(int y=0;y<3;y++)for(int x=0;x<4;x++)b.setRGB(x,y,0xff000000|(x+y+rgb));var out=new ByteArrayOutputStream();ImageIO.write(b,"png",out);return out.toByteArray();}
 static byte[] zip(String comment,String[] names,byte[]... bodies)throws Exception{var sink=new ByteArrayOutputStream();try(var z=new ZipOutputStream(sink)){if(comment!=null)z.setComment(comment);for(int i=0;i<names.length;i++){var e=new ZipEntry(names[i]);e.setTime(0);z.putNextEntry(e);z.write(bodies[i]);z.closeEntry();}}return sink.toByteArray();}
 static byte[] pack(byte[] doc,byte[]... images)throws Exception{var names=new String[1+images.length];var body=new byte[names.length][];names[0]="notes.md";body[0]=doc;for(int i=0;i<images.length;i++){names[i+1]="assets/image-"+(i+1)+".png";body[i+1]=images[i];}return zip(null,names,body);}
 static FinalShareAttachments.Batch stage(byte[] raw,int count)throws Exception{return FinalShareAttachments.stage(root,0,count,raw,FinalShareAttachments.digest(raw));}
 static int folders()throws Exception{try(var s=Files.list(root)){return (int)s.count();}}
 static void bad(byte[] raw,int count,String cause,String id)throws Exception{int before=folders();reject(()->stage(raw,count),cause,id);ok(before==folders(),id+"_no_partial");}
 static Uri uri(String path){return Uri.parse("content://"+PKG+".exports"+path);}
 public static void main(String[] argv)throws Exception{ctx=new Context(new File(argv[0]),PKG);root=PagedShareProvider.outbox(ctx);byte[] a=png(25),b=png(69),doc=text(START+REF+"Reviewed\n\n"+REF+"Again\n\n"),one=pack(doc,a),two=pack(text(START+REF+REF+"![Image](assets/image-2.png)\n\n"),a,b);int ix=0;
  for(byte[] wire:Arrays.asList(pack(text(START+"Plain\n\n")),one,two)){
    try(var batch=stage(wire,ix)){ok(batch.mime.equals(ZIP)&&batch.files.size()==1&&batch.files.get(0).getFileName().toString().equals(DOC)&&Arrays.equals(wire,Files.readAllBytes(batch.files.get(0))),"exact_bytes_"+ix);
     var uris=PagedShareProvider.makeReady(ctx,batch);ok(uris.size()==1,"one_ready_uri_"+ix);var u=uris.get(0);var f=PagedShareProvider.lookup(root,u.getEncodedPath(),System.currentTimeMillis(),android.os.SystemClock.elapsedRealtime());ok(f.name.equals(DOC)&&f.mime.equals(ZIP)&&f.size==wire.length&&Arrays.equals(wire,Files.readAllBytes(f.path)),"provider_final_only_"+ix);
     var intent=PagedShareIntent.chooser(PKG,ZIP,uris);ok(intent.target.action.equals(Intent.ACTION_SEND)&&ZIP.equals(intent.target.type)&&intent.target.flags==1&&intent.flags==1&&intent.target.extras.size()==1&&intent.target.extras.get(Intent.EXTRA_STREAM)==u&&intent.clip==intent.target.clip&&intent.clip.list.size()==1&&intent.clip.list.get(0).uri==u,"single_readonly_clip_"+ix);
     String path=u.getEncodedPath(),base=path.substring(0,path.lastIndexOf('/')+1);reject(()->PagedShareProvider.lookup(root,base+"page-001.png",System.currentTimeMillis(),android.os.SystemClock.elapsedRealtime()),"","zip_rejects_page_"+ix);reject(()->PagedShareProvider.lookup(root,base+"PocketTodo-notes.pdf",System.currentTimeMillis(),android.os.SystemClock.elapsedRealtime()),"","zip_rejects_pdf_"+ix);
     reject(()->PagedShareProvider.lookup(root,path,System.currentTimeMillis()+PagedShareProvider.WINDOW_MS+1000,android.os.SystemClock.elapsedRealtime()),"","wall_expiry_"+ix);reject(()->PagedShareProvider.lookup(root,path,System.currentTimeMillis(),android.os.SystemClock.elapsedRealtime()+PagedShareProvider.WINDOW_MS+1000),"","mono_expiry_"+ix);
     var dup=Arrays.asList(u,u);reject(()->PagedShareIntent.chooser(PKG,ZIP,dup),"count","zip_not_multiple_"+ix);reject(()->PagedShareIntent.chooser(PKG,"image/png",uris),"wrong export","zip_not_png_"+ix);reject(()->PagedShareIntent.chooser(PKG,ZIP,Collections.singletonList(uri(base+"PocketTodo-notes.pdf"))),"wrong export","zip_not_pdf_name_"+ix);
    }ok(folders()==0,"unlaunched_disposal_"+ix);ix++;
  }
  byte[] p=pack(text(START+"Hello\n\n"));bad(p,1,"reference","wrong_reviewed_asset_count");bad(one,0,"reference","hidden_extra_image");bad(pack(text(START+"Plain\n\n"),a),1,"unreferenced","orphan_image");bad(pack(text(START+"![Image](assets/image-2.png)\n\n"),a,b),2,"reference","reference_gap");bad(zip(null,new String[]{"data.log"},doc),0,"member","not_document");bad(zip(null,new String[]{"notes.md","image.png"},doc,a),1,"member","wrong_asset_name");bad(zip(null,new String[]{"notes.md","extra.txt"},text(START+"Hello"),text("omitted")),0,"extra","extra_member");bad(zip("out-of-document",new String[]{"notes.md"},text(START+"Hello")),0,"outside","archive_metadata");bad(Arrays.copyOf(p,p.length+5),0,"outside","after_end");bad(Arrays.copyOf(p,p.length-3),0,"outside","missing_end");bad(pack(text("Not a rendered document")),0,"unrecognized","wrong_document");bad(pack(new byte[]{(byte)0xc3}),0,"","invalid_utf8");bad(pack(text(START+REF),Arrays.copyOf(a,a.length+7)),1,"end","extra_image_bytes");byte[] wrong=a.clone();wrong[wrong.length-1]^=1;bad(pack(text(START+REF),wrong),1,"integrity","png_crc");bad(pack(new byte[1048577]),0,"budget","oversize_document");reject(()->FinalShareAttachments.stage(root,0,0,p,new byte[32]),"differs","wrong_preview_digest");ok(folders()==0,"negative_cleanup");
  try(var batch=FinalShareAttachments.stage(root,1,1,text("%PDF-1.4\n"),FinalShareAttachments.digest(text("%PDF-1.4\n")))){var list=PagedShareProvider.makeReady(ctx,batch);String raw=list.get(0).getEncodedPath();var fi=PagedShareProvider.lookup(root,raw,System.currentTimeMillis(),android.os.SystemClock.elapsedRealtime());ok(fi.mime.equals("application/pdf"),"v1_pdf_marker_still_readable");reject(()->PagedShareProvider.lookup(root,raw.replace(".pdf",".zip"),System.currentTimeMillis(),android.os.SystemClock.elapsedRealtime()),"","v1_no_zip");}
  var batches=new ArrayList<FinalShareAttachments.Batch>();for(int i=0;i<4;i++){PagedShareProvider.prune(root);var x=stage(p,0);PagedShareProvider.makeReady(ctx,x);batches.add(x);}reject(()->PagedShareProvider.prune(root),"","fifth_not_evicting_live");ok(folders()==4,"four_live_stay");for(var x:batches)x.close();System.out.println("MD_HOST_OK "+n+" SYNTHETIC_FS_AND_ANDROID_DOUBLES_NOT_DEVICE");
 }
}
'''

def markdown_wire_selftest():
    # Compile actual sender classes on native Java with explicit Android API doubles. These cannot establish platform permission or receiver UX.
    src=Path(__file__).resolve().parents[1]/'src/main/java/com/supercubegame/pockettodo';files={
        'android/content/Intent.java': 'package android.content;import android.net.Uri;import java.util.*;\npublic final class Intent {public static final String ACTION_SEND="android.intent.action.SEND",ACTION_SEND_MULTIPLE="android.intent.action.SEND_MULTIPLE",ACTION_CHOOSER="android.intent.action.CHOOSER",EXTRA_STREAM="android.intent.extra.STREAM";public static final int FLAG_GRANT_READ_URI_PERMISSION=1,FLAG_GRANT_WRITE_URI_PERMISSION=2; public final String action;public String type;public int flags;public ClipData clip;public Intent target;public final Map<String,Object> extras=new HashMap<>();public Intent(String a){action=a;}public Intent setType(String t){type=t;return this;}public Intent putExtra(String k,Uri v){extras.put(k,v);return this;}public Intent putParcelableArrayListExtra(String k,ArrayList<Uri> v){extras.put(k,new ArrayList<>(v));return this;}public void setClipData(ClipData c){clip=c;}public Intent addFlags(int f){flags|=f;return this;}public static Intent createChooser(Intent v,CharSequence t){Intent c=new Intent(ACTION_CHOOSER);c.target=v;return c;} }\n',
        'android/content/ClipData.java': 'package android.content;import android.net.Uri;import java.util.*;\npublic final class ClipData {public static final class Item {public final Uri uri;public Item(Uri u){uri=u;}} public final List<Item> list=new ArrayList<>();public final String[] types;public ClipData(CharSequence l,String[] t,Item i){list.add(i);types=t.clone();}public void addItem(Item i){list.add(i);} }\n',
        'android/net/Uri.java': 'package android.net; import java.net.URI;\npublic final class Uri { final URI u; private Uri(String x){u=URI.create(x);} public static Uri parse(String x){return new Uri(x);}public String getScheme(){return u.getScheme();} public String getEncodedAuthority(){return u.getRawAuthority();}public String getEncodedQuery(){return u.getRawQuery();}public String getEncodedFragment(){return u.getRawFragment();}public String getEncodedPath(){return u.getRawPath();} public String toString(){return u.toString();} public static final class Builder {String scheme,authority,paths="";public Builder scheme(String v){scheme=v;return this;}public Builder authority(String v){authority=v;return this;}public Builder appendPath(String v){paths+="/"+v;return this;}public Uri build(){return parse(scheme+"://"+authority+paths);} } }',
        'android/content/Context.java': 'package android.content;import java.io.*;public class Context{final File d;final String p;public Context(File d,String p){this.d=d;this.p=p;}public String getPackageName(){return p;}public File getCacheDir(){return d;}}',
        'android/content/ContentProvider.java': 'package android.content;import android.net.Uri;import android.database.Cursor;import android.os.ParcelFileDescriptor;import android.content.pm.ProviderInfo;public abstract class ContentProvider{Context c;public void attachInfo(Context c,ProviderInfo p){this.c=c;}public Context getContext(){return c;}public abstract boolean onCreate();public abstract String getType(Uri u);public abstract ParcelFileDescriptor openFile(Uri u,String mode)throws java.io.FileNotFoundException;public abstract Cursor query(Uri u,String[]p,String s,String[]a,String o);public abstract Uri insert(Uri u,ContentValues v);public abstract int delete(Uri u,String s,String[]a);public abstract int update(Uri u,ContentValues v,String s,String[]a);}',
        'android/content/pm/ProviderInfo.java': 'package android.content.pm;public class ProviderInfo{public boolean exported,grantUriPermissions;public String authority;}',
        'android/content/ContentValues.java': 'package android.content;public class ContentValues{}',
        'android/database/Cursor.java': 'package android.database;public interface Cursor{}',
        'android/database/MatrixCursor.java': 'package android.database;public class MatrixCursor implements Cursor{public MatrixCursor(String[] k,int n){}public void addRow(Object[] row){}}',
        'android/os/ParcelFileDescriptor.java': 'package android.os;public class ParcelFileDescriptor{public static final int MODE_READ_ONLY=1;public static ParcelFileDescriptor open(java.io.File f,int m)throws java.io.FileNotFoundException{return new ParcelFileDescriptor();}}',
        'android/os/SystemClock.java': 'package android.os;public class SystemClock{public static long elapsedRealtime(){return System.nanoTime()/1000000;}}',
        'android/provider/OpenableColumns.java': 'package android.provider;public class OpenableColumns{public static final String SIZE="_size",DISPLAY_NAME="_display_name";}',
        'com/supercubegame/pockettodo/MarkdownWireHost.java': MD_WIRE_HOST,
    }
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);out=root/'classes';out.mkdir();inputs=[]
        for name,body in files.items():
            f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(body,encoding='utf-8');inputs.append(str(f))
        for n in ('FinalShareAttachments','PagedShareIntent','PagedShareProvider'):inputs.append(str(src/(n+'.java')))
        javac=['javac'] if shutil.which('javac') else ['java','-m','jdk.compiler/com.sun.tools.javac.Main'];subprocess.run([*javac,'-encoding','UTF-8','-d',str(out),*inputs],check=True,timeout=40)
        drive=root/'drive';drive.mkdir();v=subprocess.run(['java','-Djava.awt.headless=true','-cp',str(out),'com.supercubegame.pockettodo.MarkdownWireHost',str(drive)],text=True,capture_output=True,timeout=25)
        labels=re.findall(r'^MD_HOST (.+)$',v.stdout,re.M);assert v.returncode==0 and len(labels)==len(set(labels)) and len(labels)==72 and v.stdout.splitlines()[-1]=='MD_HOST_OK '+str(len(labels))+' SYNTHETIC_FS_AND_ANDROID_DOUBLES_NOT_DEVICE',(v.stdout[-1400:],v.stderr[-1100:]);print(v.stdout.splitlines()[-1],flush=True)

def selftest():
    markdown_receiver_selftest()
    markdown_wire_selftest()
    consent_copy_selftest()
    chooser_tile_selftest()
    failure_evidence_selftest()
    bounded_drawer_selftest()
    receiver_ack_selftest()
    print("PAGED_SHARE_FIXTURE_HOST", share_png_fixture_selftest(), flush=True)
    paged_readiness_selftest()
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
    def save_picker(kind):
        for attempt in range(8):
            n=consent_checkbox(nodes(),kind,gate.PKG)
            if n is not None:
                bounds=list(map(int,re.findall(r"\d+",n.get("bounds"))))
                if bounds[2]>bounds[0] and bounds[3]>bounds[1]:click(n);break
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
        derivative=share_png_fixture(data,parent["derivative_hardening"])
        note=derivative[0]
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
            save_picker(kind);trace=[]
            cancel_share_picker(nodes,lambda:shell("input","keyevent","KEYCODE_BACK"),gate.PKG,trace)
            stop();ok(not paths() and state()==baseline,"picker_cancel_preserves_state",kind)
            start();open_preview(title);save_picker(kind);tap("SAVE")
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
            start();open_preview(title);save_picker(kind);external(1,0)
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
            nodes,click,find_format,save_picker,command,shell,note_label,derivative,set_filename)
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
            save_picker(kind);tap("SAVE")
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
