#!/usr/bin/env python3
"""Test-first category ordering and native touch gate. No feature-completion claim."""
import ast
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import verify_todo_management as runner

PACKAGE = runner.PACKAGE
SCOPE = "CATEGORY_GUARDED_ORDER_AND_INJECTED_TOUCH_NOT_PHYSICAL_PHONE_OR_ALL_LIFECYCLES"
REQUIRED = {
    "seed": "backend_fixture move_forward move_backward no_op_readonly stale_refused stale_readonly duplicate_refused duplicate_readonly null_refused null_readonly missing_refused missing_readonly bounds_refused bounds_readonly outer_refused outer_readonly late_fault late_rollback backend_checkpoint".split(),
    "deleted": "backend_restart backend_backup ui_same_title_categories touch_forward touch_duplicate_up_readonly touch_backward touch_same_readonly touch_cancel_readonly touch_outside_readonly touch_short_readonly touch_early_move_readonly touch_navigation_readonly buttons_retained touch_multitouch_pending_readonly touch_multitouch_active_readonly touch_stale_order_refused touch_stale_session_terminal touch_fresh_after_stale ui_checkpoint".split(),
    "undone": "ui_restart ui_backup".split(),
}
EXPECTED = {
    "seed": ["backend_fixture", "move_forward", "move_backward", "no_op_readonly", "stale_refused", "stale_readonly", "duplicate_refused", "duplicate_readonly", "null_refused", "null_readonly", "missing_refused", "missing_readonly", "bounds_refused", "bounds_readonly", "outer_refused", "outer_readonly", "late_fault", "late_rollback", "backend_checkpoint"],
    "deleted": ["backend_restart", "backend_backup", "ui_same_title_categories", "touch_forward", "touch_duplicate_up_readonly", "touch_backward", "touch_same_readonly", "touch_cancel_readonly", "touch_outside_readonly", "touch_short_readonly", "touch_early_move_readonly", "touch_navigation_readonly", "buttons_retained", "touch_multitouch_pending_readonly", "touch_multitouch_active_readonly", "touch_stale_order_refused", "touch_stale_session_terminal", "touch_fresh_after_stale", "ui_checkpoint"],
    "undone": ["ui_restart", "ui_backup"],
}
JAVA = r'''
package ci.todos;
import android.app.*;
import android.os.*;
import android.content.*;
import android.database.*;
import android.database.sqlite.*;
import android.graphics.Rect;
import android.view.*;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.*;
import com.supercubegame.pockettodo.AppDatabase;
import com.supercubegame.pockettodo.MediaRepository;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

public final class TodoInstrumentation extends Instrumentation {
 Bundle args;Path folder;String nonce;int count;Activity activity;Object screen;
 interface Action{void run()throws Exception;}
 static void need(boolean value,String label){if(!value)throw new AssertionError(label);}
 void pass(boolean value,String label){need(value,label);count++;System.out.println("TODO_PASS "+label);}
 static Object field(Object o,String name)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
 void ui(Action action)throws Exception{
  Throwable[] failure={null};runOnMainSync(()->{try{action.run();}catch(Throwable e){failure[0]=e;}});
  if(failure[0]!=null)throw new AssertionError("UI action",failure[0]);
 }
 void ready()throws Exception{
  long end=SystemClock.elapsedRealtime()+10000;
  while(true){boolean[] busy={true};ui(()->busy[0]=(Boolean)field(screen,"busy"));
   if(!busy[0]){waitForIdleSync();return;}
   need(SystemClock.elapsedRealtime()<end,"UI idle deadline");SystemClock.sleep(20);
  }
 }
 void launch()throws Exception{
  activity=startActivitySync(new Intent().setClassName(getTargetContext(),"com.supercubegame.pockettodo.MainActivity").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
  screen=field(activity,"screen");ready();
 }
 View root(){return activity.getWindow().getDecorView();}
 void find(View v,String key,boolean desc,List<View> out){
  CharSequence value=desc?v.getContentDescription():v instanceof TextView?((TextView)v).getText():null;
  if(value!=null&&key.contentEquals(value))out.add(v);
  if(v instanceof ViewGroup)for(int i=0;i<((ViewGroup)v).getChildCount();i++)find(((ViewGroup)v).getChildAt(i),key,desc,out);
 }
 View one(String key,boolean desc){List<View> out=new ArrayList<>();find(root(),key,desc,out);need(out.size()==1,"one view "+key);return out.get(0);}
 void click(String key,boolean desc)throws Exception{ui(()->{View v=one(key,desc);need(v.isShown()&&v.isEnabled()&&v.performClick(),"click "+key);});ready();}
 void nodes(AccessibilityNodeInfo n,String key,boolean desc,List<AccessibilityNodeInfo> out){
  CharSequence s=desc?n.getContentDescription():n.getText();if(s!=null&&key.contentEquals(s))out.add(n);
  for(int i=0;i<n.getChildCount();i++){AccessibilityNodeInfo c=n.getChild(i);if(c!=null)nodes(c,key,desc,out);}
 }
 AccessibilityNodeInfo node(String key,boolean desc)throws Exception{
  long end=SystemClock.elapsedRealtime()+10000;
  while(true){AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();
   if(root!=null&&PACKAGE.contentEquals(root.getPackageName()==null?"":root.getPackageName())){
    List<AccessibilityNodeInfo> out=new ArrayList<>();nodes(root,key,desc,out);if(out.size()==1)return out.get(0);
   }
   need(SystemClock.elapsedRealtime()<end,"node deadline "+key);SystemClock.sleep(50);
  }
 }
 static final String PACKAGE="com.supercubegame.pockettodo.v12.preview";
 void addCategory(String name)throws Exception{
  click("新建分类",false);AccessibilityNodeInfo input=node("分类名称",true);
  Bundle text=new Bundle();text.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,name);
  need(input.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,text),"category text action");
  need(input.refresh()&&name.contentEquals(input.getText()),"category exact text");
  need(node("保存",false).performAction(AccessibilityNodeInfo.ACTION_CLICK),"category save action");
  long end=SystemClock.elapsedRealtime()+10000;
  while(true){
   AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();List<AccessibilityNodeInfo> found=new ArrayList<>();
   if(root!=null){nodes(root,"分类名称",true,found);if(found.isEmpty()&&PACKAGE.contentEquals(root.getPackageName()==null?"":root.getPackageName()))break;}
   need(SystemClock.elapsedRealtime()<end,"category dialog close");SystemClock.sleep(50);
  }ready();
 }
 AppDatabase db()throws Exception{return (AppDatabase)field(screen,"db");}
 static Map<String,List<List<String>>> state(AppDatabase h){
  synchronized(h){SQLiteDatabase db=h.getReadableDatabase();boolean own=!db.inTransaction();if(own)db.beginTransaction();
   try{Map<String,List<List<String>>> out=new TreeMap<>();
    try(Cursor tables=db.rawQuery("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",null)){
     while(tables.moveToNext()){String name=tables.getString(0);need(name.matches("[A-Za-z0-9_]+"),"table name");List<List<String>> rows=new ArrayList<>();
      try(Cursor c=db.rawQuery("SELECT rowid AS rowid,* FROM \""+name+"\" ORDER BY rowid",null)){
       rows.add(Arrays.asList(c.getColumnNames()));
       while(c.moveToNext()){List<String> row=new ArrayList<>();for(int i=0;i<c.getColumnCount();i++){
        int t=c.getType(i);row.add(t+":"+(t==0?"":t==4?android.util.Base64.encodeToString(c.getBlob(i),2):c.getString(i)));
       }rows.add(row);}
      }out.put(name,rows);
     }
    }if(own)db.setTransactionSuccessful();return out;
   }finally{if(own)db.endTransaction();}
  }
 }
 static Map<String,List<List<String>>> expected(Map<String,List<List<String>>> before,List<Long> order,int delta){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){List<List<String>> rows=new ArrayList<>();for(List<String> row:e.getValue())rows.add(new ArrayList<>(row));out.put(e.getKey(),rows);}
  List<List<String>> cats=out.get("categories");int id=cats.get(0).indexOf("id"),pos=cats.get(0).indexOf("position");
  need(cats.size()==order.size()+1,"oracle membership");Set<Long> seen=new HashSet<>();
  for(int i=1;i<cats.size();i++){List<String> row=cats.get(i);long key=Long.parseLong(row.get(id).substring(2));int target=order.indexOf(key);
   need(target>=0&&seen.add(key),"oracle exact identity");row.set(pos,"1:"+target);}
  List<List<String>> revision=out.get("revision");need(revision.size()==2,"one revision");int col=revision.get(0).indexOf("value");
  revision.get(1).set(col,"1:"+Math.addExact(Long.parseLong(revision.get(1).get(col).substring(2)),delta));return out;
 }
 static boolean move(AppDatabase h,long id,List<Long> order,int to)throws Exception{
  try{return (Boolean)h.getClass().getMethod("moveCategory",long.class,List.class,int.class).invoke(h,id,order,to);}
  catch(InvocationTargetException e){Throwable t=e.getCause();if(t instanceof Exception)throw (Exception)t;if(t instanceof Error)throw (Error)t;throw new AssertionError(t);}
 }
 void reject(Class<? extends Throwable> type,Action action,String label)throws Exception{
  Throwable caught=null;try{action.run();}catch(Throwable t){caught=t;}pass(caught!=null&&type.isInstance(caught),label);
 }
 void save(String key,String value)throws Exception{Files.write(folder.resolve(key),value.getBytes("UTF-8"),StandardOpenOption.CREATE_NEW);}
 String read(String key)throws Exception{return new String(Files.readAllBytes(folder.resolve(key)),"UTF-8");}
 String name(){return "category-"+nonce+".db";}
 void backup(AppDatabase source,String suffix)throws Exception{
  Path media=folder.resolve("media-"+suffix);MediaRepository repo=new MediaRepository(media,64L*1024*1024);
  Path zip=folder.resolve(suffix+".zip");source.exportBackup(zip,repo);
  try(AppDatabase target=AppDatabase.openSchema3(getTargetContext(),"restore-category-"+nonce+"-"+suffix+".db")){
   target.restoreBackup(zip,folder.resolve("stage-"+suffix),64L*1024*1024,repo);
   pass(state(target).equals(state(source))&&target.categoryIds().equals(source.categoryIds()),suffix.equals("backend")?"backend_backup":"ui_backup");
  }
 }
 Map<String,String> media()throws Exception{
  Map<String,String> out=new TreeMap<>();Path base=getTargetContext().getFilesDir().toPath().resolve("media");
  if(Files.exists(base))try(java.util.stream.Stream<Path> paths=Files.walk(base)){
   for(Path p:(Iterable<Path>)paths::iterator){if(Files.isDirectory(p))continue;need(Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS),"media regular");out.put(base.relativize(p).toString(),android.util.Base64.encodeToString(Files.readAllBytes(p),2));}
  }return out;
 }
 void seed()throws Exception{
  need(!Files.exists(folder)&&!getTargetContext().getDatabasePath(name()).exists(),"fresh backend");Files.createDirectory(folder);
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name())){
   h.addCategory(7,"Same");h.addCategory(3,"Same");h.addCategory(91,"Last");h.addActivity(4,3,0,"Unrelated activity");h.addTodo("keep","Unrelated todo");
   h.createNote("note",4,"Unrelated note");
   List<Long> a=Arrays.asList(7L,3L,91L),b=Arrays.asList(3L,91L,7L);Map<String,List<List<String>>> before=state(h);
   pass(h.categoryIds().equals(a),"backend_fixture");
   pass(move(h,7,a,2)&&h.categoryIds().equals(b)&&state(h).equals(expected(before,b,1)),"move_forward");
   before=state(h);pass(move(h,7,b,0)&&state(h).equals(expected(before,a,1)),"move_backward");
   before=state(h);pass(!move(h,3,a,1)&&state(h).equals(before),"no_op_readonly");
   reject(IllegalStateException.class,()->move(h,7,b,1),"stale_refused");pass(state(h).equals(before),"stale_readonly");
   reject(IllegalArgumentException.class,()->move(h,7,Arrays.asList(7L,7L,91L),1),"duplicate_refused");pass(state(h).equals(before),"duplicate_readonly");
   reject(IllegalArgumentException.class,()->move(h,7,null,1),"null_refused");pass(state(h).equals(before),"null_readonly");
   reject(IllegalArgumentException.class,()->move(h,99,a,1),"missing_refused");pass(state(h).equals(before),"missing_readonly");
   reject(IllegalArgumentException.class,()->move(h,7,a,3),"bounds_refused");pass(state(h).equals(before),"bounds_readonly");
   SQLiteDatabase sql=h.getWritableDatabase();sql.beginTransaction();
   try{reject(IllegalStateException.class,()->move(h,7,a,1),"outer_refused");}finally{sql.endTransaction();}
   pass(state(h).equals(before),"outer_readonly");
   sql.execSQL("CREATE TRIGGER category_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'category_late_fault'); END");
   Throwable fault=null;try{move(h,7,a,2);}catch(Throwable t){fault=t;}
   boolean found=false;for(Throwable t=fault;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("category_late_fault"))found=true;
   pass(found,"late_fault");pass(state(h).equals(before),"late_rollback");sql.execSQL("DROP TRIGGER category_fault");
   need(move(h,7,a,2),"checkpoint move");save("backend-state",state(h).toString());pass(h.categoryIds().equals(b),"backend_checkpoint");
  }
 }
 Rect handle(long id)throws Exception{
  Rect r=new Rect();ui(()->{View v=one("category-drag-"+id,true);need(v.isShown()&&v.isEnabled()&&v.getGlobalVisibleRect(r)&&r.width()>0&&r.height()>0,"visible handle");});return r;
 }
 static void requireInjection(boolean accepted,boolean orphan){
  need(orphan?!accepted:accepted,orphan?"orphan UP must be rejected by Android":"valid touch injection");
 }
 void inject(long down,int action,float x,float y,boolean orphan){
  MotionEvent e=MotionEvent.obtain(down,SystemClock.uptimeMillis(),action,x,y,0);e.setSource(InputDevice.SOURCE_TOUCHSCREEN);
  try{requireInjection(getUiAutomation().injectInputEvent(e,true),orphan);}finally{e.recycle();}
 }
 void event(long down,int action,float x,float y){inject(down,action,x,y,false);}
 void replayDetachedUp(View old,long down,float x,float y)throws Exception{
  ui(()->{
   need(!old.isAttachedToWindow()&&old.getAlpha()==1f&&!old.isPressed(),"detached clean replay target");
   MotionEvent e=MotionEvent.obtain(down,SystemClock.uptimeMillis(),MotionEvent.ACTION_UP,x,y,0);e.setSource(InputDevice.SOURCE_TOUCHSCREEN);
   try{old.dispatchTouchEvent(e);}finally{e.recycle();}
  });waitForIdleSync();ready();
 }
 long drag(long source,long target,int terminal,boolean outside)throws Exception{
  Rect from=handle(source),to=handle(target);float x=from.exactCenterX(),y=from.exactCenterY();
  float endX=outside?1:to.exactCenterX(),endY=outside?1:to.exactCenterY();long down=SystemClock.uptimeMillis();
  event(down,MotionEvent.ACTION_DOWN,x,y);SystemClock.sleep(ViewConfiguration.getLongPressTimeout()+100);
  for(int i=1;i<=20;i++){event(down,MotionEvent.ACTION_MOVE,x+(endX-x)*i/20,y+(endY-y)*i/20);SystemClock.sleep(16);}
  event(down,terminal,endX,endY);waitForIdleSync();ready();return down;
 }
 void incomplete(long source,long target,boolean earlyMove)throws Exception{
  Rect from=handle(source),to=handle(target);long down=SystemClock.uptimeMillis();
  event(down,MotionEvent.ACTION_DOWN,from.exactCenterX(),from.exactCenterY());
  if(earlyMove){
   int slop=ViewConfiguration.get(activity).getScaledTouchSlop();
   need(Math.abs(to.exactCenterY()-from.exactCenterY())>slop,"early move crosses touch slop");
   event(down,MotionEvent.ACTION_MOVE,to.exactCenterX(),to.exactCenterY());
   need(SystemClock.uptimeMillis()-down<ViewConfiguration.getLongPressTimeout(),"early move fixture before long press");
   SystemClock.sleep(ViewConfiguration.getLongPressTimeout()+100);
  }
  event(down,MotionEvent.ACTION_UP,to.exactCenterX(),to.exactCenterY());
  if(!earlyMove)need(SystemClock.uptimeMillis()-down<ViewConfiguration.getLongPressTimeout(),"short press fixture before long press");
  waitForIdleSync();ready();
 }
 void navigateDuringDrag(long source,long target)throws Exception{
  Rect from=handle(source),to=handle(target);View[] old={null};
  ui(()->old[0]=one("category-drag-"+source,true));long down=SystemClock.uptimeMillis();
  event(down,MotionEvent.ACTION_DOWN,from.exactCenterX(),from.exactCenterY());
  SystemClock.sleep(ViewConfiguration.getLongPressTimeout()+100);
  ui(()->need(old[0].getAlpha()==0.6f,"navigation fixture has active drag"));
  click("今天",false);
  ui(()->need(!old[0].isAttachedToWindow()&&old[0].getAlpha()==1f&&!old[0].isPressed(),"navigation detached and cleared old handle"));
  event(down,MotionEvent.ACTION_UP,to.exactCenterX(),to.exactCenterY());
  waitForIdleSync();ready();click("活动",false);
  ui(()->need(one("category-drag-"+source,true)!=old[0],"navigation rebuilt handle"));
 }
 void twoPointers(long down,int action,float x,float y){
  MotionEvent.PointerProperties[] props=new MotionEvent.PointerProperties[2];
  MotionEvent.PointerCoords[] coords=new MotionEvent.PointerCoords[2];
  for(int i=0;i<2;i++){
   props[i]=new MotionEvent.PointerProperties();props[i].id=i;props[i].toolType=MotionEvent.TOOL_TYPE_FINGER;
   coords[i]=new MotionEvent.PointerCoords();coords[i].x=x+i*4;coords[i].y=y;coords[i].pressure=1;coords[i].size=1;
  }
  MotionEvent e=MotionEvent.obtain(down,SystemClock.uptimeMillis(),action,2,props,coords,0,0,1f,1f,0,0,InputDevice.SOURCE_TOUCHSCREEN,0);
  try{need(getUiAutomation().injectInputEvent(e,true),"valid two pointer injection");}finally{e.recycle();}
 }
 void multitouch(long source,long target,boolean active)throws Exception{
  Rect from=handle(source),to=handle(target);View[] old={null};ui(()->old[0]=one("category-drag-"+source,true));
  long down=SystemClock.uptimeMillis();event(down,MotionEvent.ACTION_DOWN,from.exactCenterX(),from.exactCenterY());
  if(active){SystemClock.sleep(ViewConfiguration.getLongPressTimeout()+100);ui(()->need(old[0].getAlpha()==0.6f,"multitouch active fixture"));}
  twoPointers(down,MotionEvent.ACTION_POINTER_DOWN|(1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),from.exactCenterX(),from.exactCenterY());
  if(!active)need(SystemClock.uptimeMillis()-down<ViewConfiguration.getLongPressTimeout(),"multitouch pending fixture before long press");
  waitForIdleSync();ui(()->need(old[0].getAlpha()==1f&&!old[0].isPressed(),"multitouch clears original handle"));
  twoPointers(down,MotionEvent.ACTION_POINTER_UP|(1<<MotionEvent.ACTION_POINTER_INDEX_SHIFT),from.exactCenterX(),from.exactCenterY());
  // Give a forgotten long-press callback time to fire before the final valid UP.
  SystemClock.sleep(ViewConfiguration.getLongPressTimeout()+100);
  event(down,MotionEvent.ACTION_MOVE,to.exactCenterX(),to.exactCenterY());
  event(down,MotionEvent.ACTION_UP,to.exactCenterX(),to.exactCenterY());waitForIdleSync();ready();
  ui(()->need(old[0].isAttachedToWindow()&&old[0].getAlpha()==1f&&!old[0].isPressed(),"multitouch remains clean"));
 }
 void staleOrder(AppDatabase h,List<Long> rendered,Map<String,String> images)throws Exception{
  Object page=field(screen,"activities"),session=field(page,"categorySession");View[] old={null};
  ui(()->old[0]=one("category-drag-"+rendered.get(0),true));
  Map<String,List<List<String>>> before=state(h);
  List<Long> changed=Arrays.asList(rendered.get(1),rendered.get(2),rendered.get(0));
  // Real second helper/connection: the view and captured order are deliberately not refreshed.
  try(AppDatabase other=AppDatabase.openSchema3(getTargetContext(),"pocket-v12.db")){
   need(other!=h&&move(other,rendered.get(0),rendered,2),"external order fixture write");
  }
  Map<String,List<List<String>>> external=state(h);
  need(h.categoryIds().equals(changed)&&external.equals(expected(before,changed,1))&&media().equals(images),"external order fixture exact");
  ui(()->need(field(page,"categorySession")==session&&one("category-drag-"+rendered.get(0),true)==old[0]
      &&field(session,"order").equals(rendered)&&!(Boolean)field(session,"submitted"),"rendered session genuinely stale"));
  Rect from=handle(rendered.get(0)),to=handle(rendered.get(1));long down=SystemClock.uptimeMillis();
  event(down,MotionEvent.ACTION_DOWN,from.exactCenterX(),from.exactCenterY());
  SystemClock.sleep(ViewConfiguration.getLongPressTimeout()+100);
  ui(()->need(old[0].getAlpha()==0.6f,"stale fixture reaches active drag"));
  event(down,MotionEvent.ACTION_MOVE,to.exactCenterX(),to.exactCenterY());
  event(down,MotionEvent.ACTION_UP,to.exactCenterX(),to.exactCenterY());waitForIdleSync();ready();
  ui(()->need((Boolean)field(session,"submitted")&&field(page,"categorySession")==session
      &&one("未能调整分类顺序；列表可能已变化，请重新进入活动页。",false).isShown(),"stale refusal surfaced after submission"));
  pass(state(h).equals(external)&&media().equals(images),"touch_stale_order_refused");
  drag(rendered.get(0),rendered.get(1),MotionEvent.ACTION_UP,false);
  ui(()->need(field(page,"categorySession")==session&&(Boolean)field(session,"submitted")
      &&old[0].isAttachedToWindow()&&old[0].getAlpha()==1f&&!old[0].isPressed(),"failed session stays terminal"));
  pass(state(h).equals(external)&&media().equals(images),"touch_stale_session_terminal");
  click("今天",false);click("活动",false);
  ui(()->need(field(page,"categorySession")!=session&&field(field(page,"categorySession"),"order").equals(changed),"fresh rendered order"));
  drag(changed.get(2),changed.get(0),MotionEvent.ACTION_UP,false);
  pass(h.categoryIds().equals(rendered)&&state(h).equals(expected(external,rendered,1))&&media().equals(images),"touch_fresh_after_stale");
 }
 void deleted()throws Exception{
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name())){pass(state(h).toString().equals(read("backend-state")),"backend_restart");backup(h,"backend");}
  need(!getTargetContext().getDatabasePath("pocket-v12.db").exists(),"UI fixtures must not be SQL seeded");
  launch();click("活动",false);addCategory("Same");addCategory("Same");addCategory("Last");
  AppDatabase h=db();List<Long> a=h.categoryIds();need(a.size()==3,"three categories");save("ui-order",a.toString());
  pass(h.categoryName(a.get(0)).equals("Same")&&h.categoryName(a.get(1)).equals("Same")&&!a.get(0).equals(a.get(1)),"ui_same_title_categories");
  Map<String,String> images=media();Map<String,List<List<String>>> before=state(h);List<Long> b=Arrays.asList(a.get(1),a.get(2),a.get(0));
  Rect duplicateTarget=handle(a.get(2));View[] previousHandle={null};ui(()->previousHandle[0]=one("category-drag-"+a.get(0),true));
  long previousDown=drag(a.get(0),a.get(2),MotionEvent.ACTION_UP,false);
  pass(h.categoryIds().equals(b)&&state(h).equals(expected(before,b,1))&&media().equals(images),"touch_forward");
  Map<String,List<List<String>>> afterForward=state(h);
  // Android rejects orphan UP before application dispatch. Test that separately,
  // then deliver to the retained real View explicitly; this is not injected input.
  inject(previousDown,MotionEvent.ACTION_UP,duplicateTarget.exactCenterX(),duplicateTarget.exactCenterY(),true);
  need(state(h).equals(afterForward)&&media().equals(images),"orphan rejection readonly");
  replayDetachedUp(previousHandle[0],previousDown,duplicateTarget.exactCenterX(),duplicateTarget.exactCenterY());
  pass(state(h).equals(afterForward)&&media().equals(images),"touch_duplicate_up_readonly");
  before=state(h);drag(a.get(0),a.get(1),MotionEvent.ACTION_UP,false);
  pass(h.categoryIds().equals(a)&&state(h).equals(expected(before,a,1))&&media().equals(images),"touch_backward");
  before=state(h);drag(a.get(1),a.get(1),MotionEvent.ACTION_UP,false);pass(state(h).equals(before)&&media().equals(images),"touch_same_readonly");
  drag(a.get(0),a.get(2),MotionEvent.ACTION_CANCEL,false);pass(state(h).equals(before)&&media().equals(images),"touch_cancel_readonly");
  drag(a.get(0),a.get(2),MotionEvent.ACTION_UP,true);pass(state(h).equals(before)&&media().equals(images),"touch_outside_readonly");
  incomplete(a.get(0),a.get(2),false);pass(state(h).equals(before)&&media().equals(images),"touch_short_readonly");
  incomplete(a.get(0),a.get(2),true);pass(state(h).equals(before)&&media().equals(images),"touch_early_move_readonly");
  navigateDuringDrag(a.get(0),a.get(2));pass(state(h).equals(before)&&media().equals(images),"touch_navigation_readonly");
  click("category-down-"+a.get(0),true);List<Long> c=Arrays.asList(a.get(1),a.get(0),a.get(2));
  pass(h.categoryIds().equals(c)&&state(h).equals(expected(before,c,1))&&media().equals(images),"buttons_retained");
  before=state(h);multitouch(c.get(0),c.get(2),false);
  pass(state(h).equals(before)&&media().equals(images),"touch_multitouch_pending_readonly");
  multitouch(c.get(0),c.get(2),true);
  pass(state(h).equals(before)&&media().equals(images),"touch_multitouch_active_readonly");
  staleOrder(h,c,images);
  save("ui-state",state(h).toString());save("ui-media",media().toString());pass(true,"ui_checkpoint");
 }
 void undone()throws Exception{
  launch();click("活动",false);pass(state(db()).toString().equals(read("ui-state"))&&media().toString().equals(read("ui-media")),"ui_restart");backup(db(),"ui");
 }
 @Override public void onCreate(Bundle b){super.onCreate(b);args=b;start();}
 @Override public void onStart(){
  ByteArrayOutputStream bytes=new ByteArrayOutputStream();PrintStream old=System.out;Bundle result=new Bundle();
  try(PrintStream log=new PrintStream(bytes,true,"UTF-8")){
   System.setOut(log);nonce=args.getString("nonce");int api=Build.VERSION.SDK_INT;String phase=args.getString("phase");
   need(PACKAGE.equals(getTargetContext().getPackageName())&&PACKAGE.equals(args.getString("expectedPackage")),"package");
   need(android.os.Process.myUid()==getTargetContext().getApplicationInfo().uid&&android.os.Process.myUid()>=10000,"uid");
   need((api==26||api==34)&&api==Integer.parseInt(args.getString("expectedApi")),"api");
   need(nonce!=null&&nonce.matches("[0-9]+-[0-9]+-(26|34)"),"nonce");
   need(Build.HARDWARE.contains("ranchu")||Build.HARDWARE.contains("goldfish"),"emulator");
   folder=getTargetContext().getCacheDir().toPath().resolve("category-"+nonce);
   System.out.println("TODO_TARGET "+PACKAGE+" "+android.os.Process.myUid()+" "+api+" "+nonce+" "+phase);
   if("diagnostic".equals(phase))throw new AssertionError("todo_diagnostic_sentinel");
   if("seed".equals(phase))seed();else if("deleted".equals(phase))deleted();else if("undone".equals(phase))undone();else throw new AssertionError("phase");
   System.out.println("TODO_RESULT "+phase+" "+count+" PASS");result.putString("stream",bytes.toString("UTF-8"));finish(Activity.RESULT_OK,result);
  }catch(Throwable t){t.printStackTrace(new PrintStream(bytes));result.putString("stream",bytes.toString()+"\nTODO_FAILED\n");finish(Activity.RESULT_CANCELED,result);}
  finally{System.setOut(old);}
 }
}
'''


def parser():
    namespace = dict(vars(runner), REQUIRED=EXPECTED)
    exec(compile(inspect.getsource(runner.observe), "<category-parser>", "exec"), namespace)
    return namespace["observe"]


def validate(value, manifest, logs, api, source, run, attempt):
    assert value["status"] == "PASS" and value["scope"] == SCOPE
    for key, want in dict(commit=source, run_id=run, run_attempt=attempt, api=api).items():
        assert type(value[key]) is type(want) and value[key] == want
        assert type(manifest[key]) is type(want) and manifest[key] == want
    for key in ("apk_sha256", "certificate"):
        assert re.fullmatch("[0-9a-f]{64}", value[key]) and value[key] == manifest[key]
    assert type(value["apk_bytes"]) is int and type(manifest["apk_bytes"]) is int and 0 < value["apk_bytes"] == manifest["apk_bytes"]
    assert value["release_ready"] is False
    assert value["default_test_restored"] is True and value["diagnostic_rejected"] is True
    assert value["product_readback"] == "EXACT_BEFORE_AND_AFTER"
    assert value["native_ui"] == "INJECTED_TOUCH_WITH_DETACHED_VIEW_REPLAY"
    assert not any(k in value for k in ("error", "command_failure", "restoration_error"))
    labels = sum(EXPECTED.values(), [])
    assert type(value["checks"]) is int and value["checks"] == len(labels) and value["labels"] == labels
    for phase, wanted in EXPECTED.items():
        assert parser()(logs[phase], PACKAGE, api, run+"-"+attempt+"-"+str(api), phase) == wanted
        assert value[phase]["labels"] == wanted
        assert value[phase]["log_sha256"] == hashlib.sha256(logs[phase].encode()).hexdigest()
    assert "java.lang.AssertionError: todo_diagnostic_sentinel" in logs["diagnostic"]
    assert "TODO_FAILED" in logs["diagnostic"] and "INSTRUMENTATION_CODE: 0" in logs["diagnostic"]
    assert "TODO_RESULT" not in logs["diagnostic"]
    assert len(value["stops"]) == 2
    for stop in value["stops"]:
        assert stop["status"] == "PASS" and stop["package"] == PACKAGE
        assert stop["scope"] == "COMMAND_ACK_AND_OBSERVED_ABSENCE_NOT_LMK"
        assert type(stop["force_stop_attempts"]) is int and stop["force_stop_attempts"] == 1
        command, last = stop["command"], stop["probes"][-1]
        assert type(command["returncode"]) is int and command["returncode"] == 0 and command["stdout"] == command["stderr"] == ""
        assert command["args"][-3:] == ["am", "force-stop", PACKAGE]
        assert type(last["returncode"]) is int and last["returncode"] == 1
        assert last["stdout"].strip() == last["stderr"].strip() == "" and last["args"][-2:] == ["pidof", PACKAGE]


def fixture(api):
    manifest = dict(commit="a"*40, run_id="123", run_attempt="1", api=api, apk_sha256="b"*64, certificate="c"*64, apk_bytes=100)
    value = dict(manifest, status="PASS", scope=SCOPE, checks=40, labels=sum(EXPECTED.values(), []),
                 release_ready=False, default_test_restored=True, diagnostic_rejected=True,
                 product_readback="EXACT_BEFORE_AND_AFTER", native_ui="INJECTED_TOUCH_WITH_DETACHED_VIEW_REPLAY")
    stop = dict(status="PASS", package=PACKAGE, scope="COMMAND_ACK_AND_OBSERVED_ABSENCE_NOT_LMK", force_stop_attempts=1,
                command=dict(args=["am", "force-stop", PACKAGE], returncode=0, stdout="", stderr=""),
                probes=[dict(args=["pidof", PACKAGE], returncode=1, stdout="", stderr="")])
    value["stops"] = [copy.deepcopy(stop), copy.deepcopy(stop)]
    logs = {"diagnostic": "java.lang.AssertionError: todo_diagnostic_sentinel\nTODO_FAILED\nINSTRUMENTATION_CODE: 0"}
    for phase, labels in EXPECTED.items():
        text = "INSTRUMENTATION_RESULT: stream=TODO_TARGET "+PACKAGE+" 10123 "+str(api)+" 123-1-"+str(api)+" "+phase+"\n"
        text += "".join("TODO_PASS "+s+"\n" for s in labels)+"TODO_RESULT "+phase+" "+str(len(labels))+" PASS\nINSTRUMENTATION_CODE: -1\n"
        logs[phase] = text
        value[phase] = dict(labels=labels[:], log_sha256=hashlib.sha256(text.encode()).hexdigest())
    return value, manifest, logs


def driver():
    source = inspect.getsource(runner.android)
    replacements = {
        'ROOT/"todo-device"': 'ROOT/"category-device"',
        'ROOT/"todo-apk.json"': 'ROOT/"category-apk.json"',
        'native_ui="NOT_IMPLEMENTED"': 'native_ui="INJECTED_TOUCH_WITH_DETACHED_VIEW_REPLAY"',
    }
    for old, new in replacements.items():
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    namespace = dict(vars(runner), ROOT=ROOT, JAVA=JAVA, REQUIRED=REQUIRED, SCOPE=SCOPE, observe=parser())
    exec(compile(source, "<category-existing-android-driver>", "exec"), namespace)
    return namespace["android"]


def oracle_selftest():
    # Extract the actual generated Java oracle, not a Python reimplementation.
    extract = """import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();int count=0;
for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers())
if(m instanceof MethodTree&&((MethodTree)m).getName().contentEquals("expected")){
Files.writeString(Path.of(a[1]),s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m)));count++;}
if(count!=1)throw new AssertionError("one oracle");}}}"""
    harness = """import java.util.*;class Oracle{
static void need(boolean b,String s){if(!b)throw new AssertionError(s);}
__METHOD__
static List<String> row(String...v){return new ArrayList<>(Arrays.asList(v));}
static Map<String,List<List<String>>> fixture(){
Map<String,List<List<String>>> m=new TreeMap<>();
m.put("categories",new ArrayList<>(Arrays.asList(row("rowid","id","name","position"),row("1:3","1:3","3:Same","1:1"),row("1:7","1:7","3:Same","1:0"),row("1:91","1:91","3:Last","1:2"))));
m.put("revision",new ArrayList<>(Arrays.asList(row("rowid","id","value"),row("1:1","1:1","1:10"))));
m.put("todos",new ArrayList<>(Arrays.asList(row("id","title"),row("3:keep","3:unchanged"))));return m;}
public static void main(String[]args){
Map<String,List<List<String>>> before=fixture();String frozen=before.toString();
need(expected(before,Arrays.asList(7L,3L,91L),0).equals(before),"valid_unchanged_witness");
System.out.println("ORACLE_UNCHANGED_WITNESS_PASS");
Map<String,List<List<String>>> moved=expected(before,Arrays.asList(3L,91L,7L),1);
need(moved.get("categories").get(1).equals(row("1:3","1:3","3:Same","1:0"))&&moved.get("categories").get(2).equals(row("1:7","1:7","3:Same","1:2"))&&moved.get("categories").get(3).equals(row("1:91","1:91","3:Last","1:1")),"exact_id_positions");
need(moved.get("revision").get(1).equals(row("1:1","1:1","1:11")),"exact_revision");
need(before.toString().equals(frozen)&&moved.get("todos").equals(before.get("todos")),"input_and_unrelated_preserved");
need(expected(before,Arrays.asList(7L,3L,91L),0).equals(before),"no_op_oracle");
System.out.println("ORACLE_VALID_PASS");
for(List<Long> wrong:Arrays.asList(Arrays.asList(7L,7L,91L),Arrays.asList(7L,3L),Arrays.asList(7L,3L,99L))){
boolean rejected=false;try{expected(before,wrong,1);}catch(AssertionError e){rejected=true;}need(rejected,"reject_invalid_order");}
System.out.println("CATEGORY_ORACLE positive=4 negative=3 PASS; host oracle, not product");}}"""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp);(p/"Extract.java").write_text(extract);(p/"TodoInstrumentation.java").write_text(JAVA)
        subprocess.run(["java", str(p/"Extract.java"), str(p/"TodoInstrumentation.java"), str(p/"method")], check=True, timeout=30)
        method = (p/"method").read_text()
        def execute(code):
            (p/"Oracle.java").write_text(harness.replace("__METHOD__", code))
            return subprocess.run(["java", str(p/"Oracle.java")], capture_output=True, text=True, timeout=30)
        result = execute(method);assert result.returncode == 0, (result.stdout, result.stderr);print(result.stdout.strip())
        for old, new, label in (
            ('row.set(pos,"1:"+target);', ';', "exact_id_positions"),
            ('substring(2)),delta)', 'substring(2)),0)', "exact_revision"),
            ('rows.add(new ArrayList<>(row))', 'rows.add(row)', "input_and_unrelated_preserved"),
        ):
            assert method.count(old) == 1
            result = execute(method.replace(old, new))
            assert result.returncode != 0 and "AssertionError: "+label in result.stderr and "ORACLE_UNCHANGED_WITNESS_PASS" in result.stdout, (label, result.stdout, result.stderr)
        print("CATEGORY_ORACLE compiled_mutants=3 rejected at intended behavioral assertions")


def injection_selftest():
    """Parse and execute the actual Java injection assertion, not a translation."""
    extract = """import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();int count=0;
for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers())
if(m instanceof MethodTree&&((MethodTree)m).getName().contentEquals("requireInjection")){
Files.writeString(Path.of(a[1]),s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m)));count++;}
if(count!=1)throw new AssertionError("one injection assertion");}}}"""
    harness = """class Injection{
static void need(boolean b,String s){if(!b)throw new AssertionError(s);}
__METHOD__
public static void main(String[]args){
requireInjection(true,false);requireInjection(false,true);System.out.println("INJECTION_VALID_WITNESS_PASS");
for(boolean orphan:new boolean[]{false,true}){
boolean rejected=false;try{requireInjection(orphan,orphan);}catch(AssertionError e){
need(e.getMessage().equals(orphan?"orphan UP must be rejected by Android":"valid touch injection"),"failure_identity");rejected=true;}
need(rejected,orphan?"orphan_acceptance_rejected":"valid_rejection_not_hidden");}
System.out.println("INJECTION_ASSERTION positive=2 negative=2 PASS; assertion behavior, not Android dispatch");}}"""
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"Extract.java").write_text(extract);(p/"TodoInstrumentation.java").write_text(JAVA)
        subprocess.run(["java",str(p/"Extract.java"),str(p/"TodoInstrumentation.java"),str(p/"method")],check=True,timeout=30)
        method=(p/"method").read_text()
        def execute(code):
            (p/"Injection.java").write_text(harness.replace("__METHOD__",code))
            return subprocess.run(["java",str(p/"Injection.java")],capture_output=True,text=True,timeout=30)
        result=execute(method);assert result.returncode==0,(result.stdout,result.stderr);print(result.stdout.strip())
        for replacement,label in (("orphan||accepted","orphan_acceptance_rejected"),("!orphan||!accepted","valid_rejection_not_hidden")):
            assert method.count("orphan?!accepted:accepted")==1
            result=execute(method.replace("orphan?!accepted:accepted",replacement))
            assert result.returncode!=0 and "INJECTION_VALID_WITNESS_PASS" in result.stdout and "AssertionError: "+label in result.stderr,(label,result.stdout,result.stderr)
    print("INJECTION_ASSERTION compiled_mutants=2 rejected after valid witnesses")


def selftest():
    assert REQUIRED == EXPECTED and [len(EXPECTED[p]) for p in ("seed", "deleted", "undone")] == [19, 19, 2]
    total = 0
    for api in (26, 34):
        value, manifest, logs = fixture(api)
        validate(value, manifest, logs, api, "a"*40, "123", "1")
        cases = []
        for key in value:
            bad = copy.deepcopy(value);del bad[key];cases.append((bad, manifest, logs))
        for key in manifest:
            bad = dict(manifest);del bad[key];cases.append((value, bad, logs))
        for key, wrong in (("checks", 40.0), ("checks", True), ("release_ready", 0), ("api", float(api)), ("default_test_restored", 1),
                           ("commit", "d"*40), ("run_id", "999"), ("run_attempt", "2"), ("apk_sha256", "d"*64),
                           ("native_ui", "WIDGET_CALLBACKS"), ("status", "FAIL"), ("error", "sentinel")):
            bad = copy.deepcopy(value);bad[key] = wrong;cases.append((bad, manifest, logs))
        for phase, labels in EXPECTED.items():
            for label in labels:
                bad = dict(logs);bad[phase] = bad[phase].replace("TODO_PASS "+label+"\n", "");cases.append((value, manifest, bad))
        bad = dict(logs);bad["diagnostic"] = "";cases.append((value, manifest, bad))
        for bad, m, l in cases:
            try:validate(bad, m, l, api, "a"*40, "123", "1")
            except (AssertionError, KeyError, TypeError):total += 1
            else:raise AssertionError("invalid receipt accepted")
    source = inspect.getsource(validate)
    for old, new, key, wrong in (
        ('assert value["native_ui"] == "INJECTED_TOUCH_WITH_DETACHED_VIEW_REPLAY"', "assert True", "native_ui", "WIDGET_CALLBACKS"),
        ('assert value["release_ready"] is False', "assert True", "release_ready", 0),
        ('assert type(value["checks"]) is int and value["checks"] == len(labels) and value["labels"] == labels', "assert True", "checks", 40.0),
    ):
        assert source.count(old) == 1
        namespace = dict(globals());exec(compile(source.replace(old, new), "<category-validator-mutant>", "exec"), namespace)
        v, m, l = fixture(26);namespace["validate"](v, m, l, 26, "a"*40, "123", "1")
        v[key] = wrong
        try:validate(v, m, l, 26, "a"*40, "123", "1")
        except AssertionError:pass
        else:raise AssertionError("negative witness did not reject")
        namespace["validate"](v, m, l, 26, "a"*40, "123", "1")
    # Complete generated Java syntax, not Android compilation or feature proof.
    parse = """import javax.tools.*;import com.sun.source.util.*;import java.util.*;
class Parse{public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
for(Object u:t.parse()){}for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());}}}"""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp);(p/"Parse.java").write_text(parse);(p/"TodoInstrumentation.java").write_text(JAVA)
        subprocess.run(["java", str(p/"Parse.java"), str(p/"TodoInstrumentation.java")], check=True, timeout=30)
    assert callable(driver())
    oracle_selftest()
    injection_selftest()
    report_selftest()
    print("CATEGORY_HOST "+json.dumps(dict(status="PASS", positive=2, negative=total, compiled_validator_mutants=3,
          scope="HOST_RECEIPT_AND_JAVA_SYNTAX_NOT_FEATURE_ACCEPTANCE", release_ready=False)))


def report():
    import urllib.request
    from verify_evidence import publish
    source, run, attempt = (os.environ[k] for k in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"))
    needs = json.loads(os.environ["NEEDS_JSON"])
    passed = all(needs.get(k, {}).get("result") == "success" for k in ("category_host", "category_device"))
    devices = {}
    for api in (26, 34):
        folder = ROOT/"collected-category"/("category-device-api-"+str(api))
        row = dict(status="NOT_VERIFIED");devices[str(api)] = row
        try:
            value = json.loads((folder/"category-device/result.json").read_text())
            manifest = json.loads((folder/"category-apk.json").read_text())
            logs = {p: (folder/"category-device"/(p+".log")).read_text() for p in (*EXPECTED, "diagnostic")}
            validate(value, manifest, logs, api, source, run, attempt)
            row.update(status="PASS", evidence=value, manifest=manifest)
        except (OSError, ValueError, AssertionError, KeyError, TypeError, IndexError) as e:
            passed = False;row["error"] = repr(e)
        row["diagnostics"] = {}
        for name in ("result.json", "build.log", "seed.log", "deleted.log", "undone.log"):
            try:
                data = (folder/"category-device"/name).read_bytes()
                row["diagnostics"][name] = dict(bytes=len(data), truncated=len(data)>12000, tail=data[-12000:].decode("utf-8", "replace"))
            except OSError as e:row["diagnostics"][name] = dict(error=repr(e))
    value = dict(status="PASS" if passed else "NOT_VERIFIED", scope=SCOPE, commit=source, run_id=run, run_attempt=attempt,
                 devices=devices, parents=needs, release_ready=False, durable_upgrade_ready=False,
                 not_covered=["physical_phone_gestures", "all_lifecycle_stale_duplicate_UI_cases", "referenced_media_fixture", "ordinary_todo_sorting"])
    data = (json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode()
    (ROOT/"category-report.json").write_bytes(data)
    endpoint = "https://api.github.com/repos/"+os.environ["GITHUB_REPOSITORY"]+"/"
    def api_call(path, method="GET", body=None):
        request = urllib.request.Request(endpoint+path, method=method, data=None if body is None else json.dumps(body).encode(),
                  headers={"Authorization": "Bearer "+os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=30) as response:return json.load(response)
    print("CATEGORY_REPORT", publish(api_call, "reports/category-drag-"+source+"-"+run+"-"+attempt+".json", data))
    assert passed, "Category feature missing, failed or evidence incomplete"


def report_selftest():
    """Exercise the real report entry; only network publication is doubled."""
    import contextlib
    import io
    import types
    import urllib.request
    from unittest.mock import patch

    cases = ("good", "missing_device", "missing_log", "wrong_commit", "wrong_attempt",
             "wrong_apk", "float_count", "no_native", "failed_parent", "missing_diagnostic")
    def exercise(invoke, case):
        namespace = invoke.__globals__;oldroot = namespace["ROOT"]
        published = []
        fake = types.ModuleType("verify_evidence")
        def publish(api, path, data):
            published.append((path, data))
            return "EXPLICIT_LOCAL_PUBLISHER_DOUBLE"
        fake.publish = publish
        parents = {"category_host": {"result": "success"}, "category_device": {"result": "success"}}
        if case == "failed_parent":parents["category_device"]["result"] = "failure"
        env = dict(GITHUB_SHA="a"*40, GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1",
                   GITHUB_REPOSITORY="explicit/test", GH_TOKEN="local-publisher-double", NEEDS_JSON=json.dumps(parents))
        try:
            with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env), patch.dict(sys.modules, {"verify_evidence": fake}), \
                 patch.object(urllib.request, "urlopen", side_effect=AssertionError("selftest network forbidden")):
                namespace["ROOT"] = Path(tmp)
                for api in (26, 34):
                    value, manifest, logs = fixture(api)
                    folder = Path(tmp)/"collected-category"/("category-device-api-"+str(api))
                    (folder/"category-device").mkdir(parents=True)
                    if api == 34:
                        if case == "missing_device":continue
                        if case == "missing_log":del logs["deleted"]
                        if case == "wrong_commit":manifest["commit"] = "d"*40
                        if case == "wrong_attempt":manifest["run_attempt"] = "2"
                        if case == "wrong_apk":manifest["apk_sha256"] = "d"*64
                        if case == "float_count":value["checks"] = float(value["checks"])
                        if case == "no_native":value["native_ui"] = "WIDGET_CALLBACKS"
                        if case == "missing_diagnostic":logs["diagnostic"] = ""
                    (folder/"category-apk.json").write_text(json.dumps(manifest))
                    (folder/"category-device/result.json").write_text(json.dumps(value))
                    for name, text in logs.items():(folder/"category-device"/(name+".log")).write_text(text)
                error = None
                try:
                    with contextlib.redirect_stdout(io.StringIO()):invoke()
                except AssertionError as e:error = e
                saved = json.loads((Path(tmp)/"category-report.json").read_text())
                assert saved["status"] == ("PASS" if case == "good" else "NOT_VERIFIED"), "report_overall"
                assert (error is None) == (case == "good"), "report_failure_exit"
                if error is not None:assert str(error) == "Category feature missing, failed or evidence incomplete", "report_primary_error"
                assert saved["commit"] == "a"*40 and saved["run_id"] == "123" and saved["run_attempt"] == "1", "report_identity"
                assert saved["release_ready"] is False and saved["durable_upgrade_ready"] is False, "report_not_release"
                assert len(published) == 1 and json.loads(published[0][1]) == saved, "report_published_exactly_once"
                assert published[0][0] == "reports/category-drag-"+"a"*40+"-123-1.json", "report_publication_identity"
                assert saved["devices"]["26"]["status"] == "PASS", "report_preserves_valid_device"
                assert saved["devices"]["34"]["status"] == ("PASS" if case in ("good", "failed_parent") else "NOT_VERIFIED"), "report_device_status"
        finally:
            namespace["ROOT"] = oldroot
    for case in cases:exercise(report, case)
    source = inspect.getsource(report);rejected = []
    for old, new, case, label in (
        ('passed = all(needs.get(k, {}).get("result") == "success" for k in ("category_host", "category_device"))',
         "passed = True", "failed_parent", "report_overall"),
        ('validate(value, manifest, logs, api, source, run, attempt)', "pass", "wrong_apk", "report_overall"),
        ('assert passed, "Category feature missing, failed or evidence incomplete"', "pass", "failed_parent", "report_failure_exit"),
    ):
        assert source.count(old) == 1, "report mutation anchor"
        namespace = dict(globals());exec(compile(source.replace(old, new), "<category-report-mutant>", "exec"), namespace)
        invoke = namespace["report"];exercise(invoke, "good")
        try:exercise(invoke, case)
        except AssertionError as e:assert str(e) == label, (label, repr(e));rejected.append((case, label))
        else:raise AssertionError("report mutant survived")
    assert len(cases) == 10 and len(rejected) == 3
    print("CATEGORY_REPORT_ENTRY positive=1 negative=9 compiled_mutants=3 PASS; actual entry with explicit artifacts and network doubles")


if __name__ == "__main__":
    assert not sys.flags.optimize
    {"selftest": selftest, "android": lambda: driver()(), "report": report}[sys.argv[1]]()
