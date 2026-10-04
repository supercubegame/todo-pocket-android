#!/usr/bin/env python3
"""Independent manual app catalog gate. No external app launch or full-release claim."""
import ast, copy, hashlib, inspect, json, linecache, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import verify_todo_management as runner
import verify_category_drag as shared
PACKAGE = runner.PACKAGE
SCOPE = "MANUAL_APPLICATION_CATALOG_AND_LINKED_ACTIVITY_NOT_EXTERNAL_LAUNCH_OR_FULL_PRODUCT"
REQUIRED = {'seed': ['backend_fixture', 'application_insert', 'duplicate_package_readonly', 'invalid_package_readonly', 'prepare_readonly', 'create_linked_once', 'duplicate_plan_readonly', 'canceled_plan_readonly', 'second_category_reuse', 'unassigned_activity', 'stale_app_readonly', 'stale_category_readonly', 'late_rollback', 'consumed_failure_readonly', 'outer_transaction_readonly', 'backend_checkpoint'], 'deleted': ['backend_restart', 'backend_backup', 'ui_fixture', 'catalog_open_readonly', 'invalid_name_readonly', 'invalid_package_ui_readonly', 'create_application_ui', 'duplicate_package_ui_readonly', 'same_title_distinct_ids', 'cancel_picker_readonly', 'first_category_link', 'duplicate_click_readonly', 'second_category_link', 'old_picker_readonly', 'unassigned_retained', 'ui_checkpoint'], 'undone': ['ui_restart', 'ui_backup']}
EXPECTED = {'seed': ['backend_fixture', 'application_insert', 'duplicate_package_readonly', 'invalid_package_readonly', 'prepare_readonly', 'create_linked_once', 'duplicate_plan_readonly', 'canceled_plan_readonly', 'second_category_reuse', 'unassigned_activity', 'stale_app_readonly', 'stale_category_readonly', 'late_rollback', 'consumed_failure_readonly', 'outer_transaction_readonly', 'backend_checkpoint'], 'deleted': ['backend_restart', 'backend_backup', 'ui_fixture', 'catalog_open_readonly', 'invalid_name_readonly', 'invalid_package_ui_readonly', 'create_application_ui', 'duplicate_package_ui_readonly', 'same_title_distinct_ids', 'cancel_picker_readonly', 'first_category_link', 'duplicate_click_readonly', 'second_category_link', 'old_picker_readonly', 'unassigned_retained', 'ui_checkpoint'], 'undone': ['ui_restart', 'ui_backup']}
SHARED_SHA256 = "9b1b435b21b630e1230f1e112a794962825665982ceabdbb41cc68583ce3d70d"
# Reuse unchanged transport/receipt infrastructure, never the category cases.
# Pin the whole dependency: a future edit must explicitly review this adapter.
assert hashlib.sha256(Path(shared.__file__).read_bytes()).hexdigest() == SHARED_SHA256, "catalog shared gate changed"
for marker in (" static Map<String,List<List<String>>> expected(", " void save(", " void seed(", " @Override public void onCreate"):
    assert shared.JAVA.count(marker) == 1, "ambiguous Java scaffold boundary"
CASES = r'''
 static Object invoke(Object target,String method,Class<?>[] types,Object... args)throws Exception{
  try{return target.getClass().getMethod(method,types).invoke(target,args);}
  catch(InvocationTargetException e){Throwable t=e.getCause();if(t instanceof Exception)throw(Exception)t;if(t instanceof Error)throw(Error)t;throw new AssertionError(t);}
 }
 Object prepare(AppDatabase h,long category,long app)throws Exception{
  return invoke(h,"prepareApplicationActivity",new Class<?>[]{long.class,long.class},category,app);
 }
 long confirm(AppDatabase h,Object plan,String title)throws Exception{
  return ((Number)invoke(h,"confirmApplicationActivity",new Class<?>[]{plan.getClass(),String.class},plan,title)).longValue();
 }
 void close(Object plan)throws Exception{((AutoCloseable)plan).close();}
 void readonly(AppDatabase h,Class<? extends Throwable> type,Action action,String label)throws Exception{
  Map<String,List<List<String>>> before=state(h);Throwable failure=null;
  try{action.run();}catch(Throwable t){failure=t;}
  pass(failure!=null&&type.isInstance(failure)&&state(h).equals(before),label);
 }
 static Map<String,List<List<String>>> addition(Map<String,List<List<String>>> before,String table,List<String> row){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();for(List<String> r:e.getValue())rows.add(new ArrayList<>(r));out.put(e.getKey(),rows);
  }
  need(out.containsKey(table)&&row.size()==out.get(table).get(0).size(),"oracle row schema");
  out.get(table).add(new ArrayList<>(row));
  List<List<String>> rev=out.get("revision");int col=rev.get(0).indexOf("value");
  need(col>=0&&rev.size()==2,"oracle revision");
  rev.get(1).set(col,"1:"+Math.incrementExact(Long.parseLong(rev.get(1).get(col).substring(2))));
  return out;
 }
 static List<String> activityRow(long id,long category,long app,String title){
  return Arrays.asList("1:"+id,"1:"+id,"1:"+category,app==0?"0:":"1:"+app,"3:"+title,"1:0");
 }
 void seed()throws Exception{
  need(!Files.exists(folder)&&!getTargetContext().getDatabasePath(name()).exists(),"fresh backend");Files.createDirectory(folder);
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name())){
   h.addCategory(3,"Same");h.addCategory(7,"Same");h.addActivity(4,3,0,"Keep");
   h.addTodo("keep","Keep");h.createNote("note",4,"Keep");
   h.savePath(4,Arrays.asList("Keep path"));h.saveTags(4,Arrays.asList("Keep tag"));
   h.recordBatch("keep",Arrays.asList(new com.supercubegame.pockettodo.Ledger.Entry("keep",4,java.time.LocalDate.of(2026,10,4),com.supercubegame.pockettodo.Ledger.Kind.EXPENSE,123,"Keep")));
   h.putMark(new com.supercubegame.pockettodo.CalendarRules.Mark(4,java.time.LocalDate.of(2026,10,4),com.supercubegame.pockettodo.CalendarRules.Status.DONE,"Keep",java.time.Instant.parse("2026-10-04T00:00:00Z")));
   pass(h.count("applications")==0&&h.count("ledger")==1&&h.count("checkins")==1,"backend_fixture");
   Map<String,List<List<String>>> before=state(h);
   h.addApplication(10,"Same","example.catalog");
   pass(state(h).equals(addition(before,"applications",Arrays.asList("1:10","1:10","3:Same","3:example.catalog"))),"application_insert");
   readonly(h,IllegalArgumentException.class,()->h.addApplication(11,"Same","example.catalog"),"duplicate_package_readonly");
   readonly(h,IllegalArgumentException.class,()->h.addApplication(11,"Same","javascript:bad"),"invalid_package_readonly");
   before=state(h);Object first=prepare(h,3,10);
   pass(state(h).equals(before),"prepare_readonly");
   long id=confirm(h,first,"Linked");
   pass(id==5&&state(h).equals(addition(before,"activities",activityRow(5,3,10,"Linked"))),"create_linked_once");
   readonly(h,IllegalStateException.class,()->confirm(h,first,"Again"),"duplicate_plan_readonly");
   Object canceled=prepare(h,3,10);close(canceled);
   readonly(h,IllegalStateException.class,()->confirm(h,canceled,"Canceled"),"canceled_plan_readonly");
   before=state(h);Object second=prepare(h,7,10);
   pass(confirm(h,second,"Linked")==6&&state(h).equals(addition(before,"activities",activityRow(6,7,10,"Linked"))),"second_category_reuse");
   before=state(h);Object unassigned=prepare(h,7,0);
   pass(confirm(h,unassigned,"Plain")==7&&state(h).equals(addition(before,"activities",activityRow(7,7,0,"Plain"))),"unassigned_activity");
   Object stale=prepare(h,3,10);
   h.getWritableDatabase().execSQL("UPDATE applications SET name='Changed' WHERE id=10");
   readonly(h,IllegalStateException.class,()->confirm(h,stale,"Stale"),"stale_app_readonly");
   Object staleCategory=prepare(h,3,10);h.renameCategory(3,"Changed");
   readonly(h,IllegalStateException.class,()->confirm(h,staleCategory,"Stale"),"stale_category_readonly");
   Object fault=prepare(h,3,10);before=state(h);
   h.getWritableDatabase().execSQL("CREATE TRIGGER catalog_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'catalog_late_fault'); END");
   Throwable failed=null;try{confirm(h,fault,"Rollback");}catch(Throwable t){failed=t;}
   boolean sentinel=false;for(Throwable t=failed;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("catalog_late_fault"))sentinel=true;
   pass(sentinel&&state(h).equals(before),"late_rollback");
   h.getWritableDatabase().execSQL("DROP TRIGGER catalog_fault");
   readonly(h,IllegalStateException.class,()->confirm(h,fault,"Again"),"consumed_failure_readonly");
   h.getWritableDatabase().beginTransaction();
   try{readonly(h,IllegalStateException.class,()->prepare(h,3,10),"outer_transaction_readonly");}
   finally{h.getWritableDatabase().endTransaction();}
   save("backend-state",state(h).toString());pass(h.count("applications")==1&&h.count("activities")==4&&h.count("ledger")==1&&h.count("checkins")==1,"backend_checkpoint");
  }
 }
 void text(String key,String value)throws Exception{ui(()->{View v=one(key,true);need(v instanceof EditText,"editable "+key);((EditText)v).setText(value);need(value.contentEquals(((EditText)v).getText()),"exact input");});}
 void invalidUI(AppDatabase h,String label)throws Exception{
  Map<String,List<List<String>>> before=state(h);click("catalog-create-app",true);
  boolean[] visible={false};ui(()->{View v=one("catalog-validation",true);visible[0]=v instanceof TextView&&((TextView)v).getText().length()>0;});
  pass(visible[0]&&state(h).equals(before),label);
 }
 void deleted()throws Exception{
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name())){
   pass(state(h).toString().equals(read("backend-state")),"backend_restart");backup(h,"backend");
  }
  launch();AppDatabase h=db();need(h.count("categories")==0&&h.count("applications")==0,"fresh UI database");
  h.addCategory(1,"Same");h.addCategory(2,"Same");h.addActivity(1,1,0,"Keep");h.addTodo("keep","Keep");
  h.recordBatch("keep",Arrays.asList(new com.supercubegame.pockettodo.Ledger.Entry("keep",1,java.time.LocalDate.of(2026,10,4),com.supercubegame.pockettodo.Ledger.Kind.EXPENSE,123,"Keep")));
  click("活动",false);pass(h.count("activities")==1&&h.count("applications")==0,"ui_fixture");
  Map<String,List<List<String>>> before=state(h);click("应用目录",false);
  pass(state(h).equals(before),"catalog_open_readonly");
  text("catalog-name","   ");text("catalog-package","example.ui");invalidUI(h,"invalid_name_readonly");
  text("catalog-name","Same");text("catalog-package","bad package");invalidUI(h,"invalid_package_ui_readonly");
  text("catalog-package","example.ui");before=state(h);click("catalog-create-app",true);
  pass(state(h).equals(addition(before,"applications",Arrays.asList("1:1","1:1","3:Same","3:example.ui"))),"create_application_ui");
  text("catalog-name","Duplicate");text("catalog-package","example.ui");invalidUI(h,"duplicate_package_ui_readonly");
  text("catalog-name","Same");text("catalog-package","");before=state(h);click("catalog-create-app",true);
  pass(state(h).equals(addition(before,"applications",Arrays.asList("1:2","1:2","3:Same","3:"))),"same_title_distinct_ids");
  click("catalog-back",true);before=state(h);click("category-app-add-1",true);click("catalog-back",true);
  pass(state(h).equals(before),"cancel_picker_readonly");
  click("category-app-add-1",true);click("catalog-app-1",true);text("catalog-activity-title","Linked");
  final View[] old={null};before=state(h);
  ui(()->{old[0]=one("catalog-create-activity",true);need(old[0].performClick(),"first submit");old[0].performClick();});ready();
  Map<String,List<List<String>>> linked=addition(before,"activities",activityRow(2,1,1,"Linked"));
  pass(state(h).equals(linked),"first_category_link");
  ui(()->old[0].performClick());ready();pass(state(h).equals(linked),"duplicate_click_readonly");
  click("category-app-add-2",true);click("catalog-app-1",true);text("catalog-activity-title","Linked");before=state(h);
  click("catalog-create-activity",true);
  pass(state(h).equals(addition(before,"activities",activityRow(3,2,1,"Linked"))),"second_category_link");
  click("category-app-add-1",true);final View[] detached={null};ui(()->detached[0]=one("catalog-app-2",true));click("catalog-back",true);
  before=state(h);ui(()->detached[0].performClick());ready();
  boolean[] categories={false};ui(()->categories[0]=one("category-app-add-1",true).isAttachedToWindow());
  pass(categories[0]&&state(h).equals(before),"old_picker_readonly");
  ui(()->need(one("category-add-1",true).isEnabled(),"old unassigned entry"));
  pass(h.count("activities")==3&&h.count("applications")==2&&h.count("ledger")==1,"unassigned_retained");
  save("ui-state",state(h).toString());save("ui-media",media().toString());pass(h.count("checkins")==0,"ui_checkpoint");
 }
 void undone()throws Exception{
  launch();click("活动",false);
  pass(state(db()).toString().equals(read("ui-state"))&&media().toString().equals(read("ui-media")),"ui_restart");backup(db(),"ui");
 }
'''
JAVA = (shared.JAVA[:shared.JAVA.index(" static Map<String,List<List<String>>> expected(")] + CASES
    + shared.JAVA[shared.JAVA.index(" void save("):shared.JAVA.index(" void seed(")].replace("category-", "catalog-").replace("&&target.categoryIds().equals(source.categoryIds())", "")
    + shared.JAVA[shared.JAVA.index(" @Override public void onCreate"):].replace('"category-"+nonce', '"catalog-"+nonce'))
def bind_infrastructure():
    for name in ("parser", "validate", "fixture", "driver", "report", "report_selftest"):
        s=inspect.getsource(getattr(shared,name))
        s=s.replace("INJECTED_TOUCH_WITH_DETACHED_VIEW_REPLAY","INSTALLED_VIEW_CALLBACKS_NOT_PHYSICAL_TOUCH")
        s=s.replace("category","catalog").replace("Category","Catalog").replace("CATEGORY","CATALOG")
        if name=="fixture":
            assert s.count("checks=40")==1
            s=s.replace("checks=40","checks=34")
        if name=="report":
            old='["physical_phone_gestures", "all_lifecycle_stale_duplicate_UI_cases", "referenced_media_fixture", "ordinary_todo_sorting"]'
            assert s.count(old)==1
            s=s.replace(old,'["physical_phone_gestures", "referenced_media_fixture", "catalog_rename_archive", "category_shortcuts", "external_app_launch", "full_lifecycle", "field_UI"]')
        s=s.replace('"reports/catalog-drag-','"reports/app-catalog-')
        filename="<catalog-bound-"+name+">"
        linecache.cache[filename]=(len(s),None,s.splitlines(True),filename)
        exec(compile(s,filename,"exec"),globals())
bind_infrastructure()

def catalog_ui_selftest():
    """Compile current AppCatalog, never a copied product; UI/DB doubles only."""
    files={
    "android/view/View.java":r'''package android.view;
    import java.util.*;
    public class View {
     public boolean attached,enabled=true;public String description="";
     public List<View> children=new ArrayList<>();
     public interface OnClickListener{void onClick(View v);}
     public interface OnAttachStateChangeListener{void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}
     public OnClickListener click;public List<OnAttachStateChangeListener> listeners=new ArrayList<>();
     public boolean isAttachedToWindow(){return attached;}public boolean isEnabled(){return enabled;}
     public void setEnabled(boolean b){enabled=b;}public void setContentDescription(String s){description=s;}
     public void setOnClickListener(OnClickListener l){click=l;}
     public boolean performClick(){if(click==null)return false;click.onClick(this);return true;}
     public void addOnAttachStateChangeListener(OnAttachStateChangeListener l){listeners.add(l);}
     public void attach(boolean yes){attached=yes;for(View v:new ArrayList<>(children))v.attach(yes);for(OnAttachStateChangeListener l:listeners){if(yes)l.onViewAttachedToWindow(this);else l.onViewDetachedFromWindow(this);}}
     public void setPadding(int a,int b,int c,int d){}public void setBackground(Object o){}
     public View find(String s){if(description.equals(s))return this;for(View v:children){View x=v.find(s);if(x!=null)return x;}return null;}
    }''',
    "android/widget/LinearLayout.java":r'''package android.widget;import android.view.View;
    public class LinearLayout extends View{
     public LinearLayout(Object c){} public static class LayoutParams{public LayoutParams(int a,int b){}public LayoutParams(int a,int b,int c){}}
     public void addView(View v){children.add(v);if(attached)v.attach(true);}
     public void addView(View v,LayoutParams p){addView(v);}
     public void removeAllViews(){for(View v:children)v.attach(false);children.clear();}
    }''',
    "android/widget/TextView.java":r'''package android.widget;import android.view.View;
    public class TextView extends View{public String text="";public TextView(Object c){}public void setText(String s){text=s;}public CharSequence getText(){return text;}}''',
    "android/widget/EditText.java":r'''package android.widget;public class EditText extends TextView{public EditText(Object c){super(c);}public void setHint(String s){}}''',
    "android/widget/Button.java":r'''package android.widget;public class Button extends TextView{public Button(Object c){super(c);}}''',
    "android/widget/ScrollView.java":r'''package android.widget;public class ScrollView extends LinearLayout{public ScrollView(Object c){super(c);}public void setFillViewport(boolean b){}}''',
    "android/database/Cursor.java":r'''package android.database;import java.util.*;
    public class Cursor implements AutoCloseable{
     List<Object[]>rows;int i=-1;public Cursor(List<Object[]>r){rows=r;}
     public boolean moveToNext(){return ++i<rows.size();}public boolean moveToFirst(){i=0;return !rows.isEmpty();}
     public long getLong(int c){return((Number)rows.get(i)[c]).longValue();}public String getString(int c){return(String)rows.get(i)[c];}
     public boolean isNull(int c){return rows.get(i)[c]==null;}public void close(){}
    }''',
    "com/supercubegame/pockettodo/TodayScreen.java":r'''package com.supercubegame.pockettodo;
    import android.view.View;import android.widget.*;import java.util.*;import java.util.concurrent.Callable;import java.util.function.Consumer;
    class TodayScreen{
     static final int INK=1,MUTED=2,ERROR=3,WHITE=4;
     static class Activity{boolean finishing,destroyed;boolean isFinishing(){return finishing;}boolean isDestroyed(){return destroyed;}}
     Activity activity=new Activity();AppDatabase db=new AppDatabase();LinearLayout outer=new LinearLayout(activity);
     ArrayDeque<Runnable> queue=new ArrayDeque<>();boolean busy;String message;
     TodayScreen(){outer.attach(true);}
     <T>void work(Callable<T>a,Consumer<T>s,Runnable f){
      if(busy)throw new AssertionError("unexpected concurrent work");busy=true;
      queue.add(()->{T x;try{x=a.call();}catch(Exception e){busy=false;if(f!=null)f.run();return;}busy=false;s.accept(x);});
     }
     void drain(){int n=0;while(!queue.isEmpty()){if(++n>20)throw new AssertionError("queue cycle");queue.remove().run();}}
     LinearLayout content(){outer.removeAllViews();return outer;}LinearLayout column(){return new LinearLayout(activity);}
     TextView text(String s,int size,int color){TextView v=new TextView(activity);v.setText(s);return v;}
     EditText field(String key,boolean multi){EditText v=new EditText(activity);v.setContentDescription(key);return v;}
     Button button(String s,Runnable r){Button v=new Button(activity);v.setText(s);v.setOnClickListener(w->{if(!busy)r.run();});return v;}
     int dp(int n){return n;}Object shape(int c,int r){return null;}
     void addRow(LinearLayout p,View v){p.addView(v);}void message(String s,boolean e){message=s;}
     View one(String s){View v=outer.find(s);if(v==null)throw new AssertionError("missing "+s);return v;}
     void text(String s,String v){((EditText)one(s)).setText(v);}
    }''',
    "com/supercubegame/pockettodo/AppDatabase.java":r'''package com.supercubegame.pockettodo;
    import android.database.Cursor;import java.util.*;
    class AppDatabase{
     TreeMap<Long,String[]>apps=new TreeMap<>();int writes,links,attempts;boolean fail,failRead;
     class SQL{Cursor rawQuery(String q,String[]args){
      List<Object[]>r=new ArrayList<>();if(q.equals("SELECT MAX(id) FROM applications"))r.add(new Object[]{apps.isEmpty()?null:apps.lastKey()});
      else if(q.equals("SELECT id,name,package_name FROM applications ORDER BY id")){if(failRead)throw new IllegalStateException("read failed");for(Map.Entry<Long,String[]>e:apps.entrySet())r.add(new Object[]{e.getKey(),e.getValue()[0],e.getValue()[1]});}
      else throw new AssertionError(q);return new Cursor(r);
     }}
     SQL getReadableDatabase(){return new SQL();}
     void addApplication(long id,String name,String pkg){for(String[]a:apps.values())if(!pkg.isEmpty()&&a[1].equals(pkg))throw new IllegalArgumentException("duplicate");apps.put(id,new String[]{name,pkg});writes++;}
     static class ApplicationActivityPlan implements AutoCloseable{
      long category,app;String name;boolean terminal;public void close(){terminal=true;}
      long applicationId(){return app;}String categoryName(){return "Category";}String applicationName(){return name;}
     }
     ApplicationActivityPlan last;
     ApplicationActivityPlan prepareApplicationActivity(long c,long a){ApplicationActivityPlan p=new ApplicationActivityPlan();p.category=c;p.app=a;p.name=apps.get(a)[0];last=p;return p;}
     long confirmApplicationActivity(ApplicationActivityPlan p,String title){attempts++;if(p.terminal)throw new IllegalStateException();p.close();if(fail)throw new IllegalStateException("late");links++;writes++;return links;}
    }''',
    "com/supercubegame/pockettodo/Test.java":r'''package com.supercubegame.pockettodo;
    import android.view.View;import android.widget.*;import java.lang.reflect.*;
    public class Test{
     static int checked;static void need(boolean b,String s){if(!b)throw new AssertionError(s);checked++;System.out.println("CATALOG_UI_CHECK "+s);}
     static TodayScreen fresh(long category){
      TodayScreen h=new TodayScreen();if(category!=0)h.db.addApplication(10,"Same","");
      View anchor=new View();h.outer.addView(anchor);
      new AppCatalog(h,category,()->h.content()).open(anchor);h.drain();return h;
     }
     static View submit(TodayScreen h){h.one("catalog-app-10").performClick();h.drain();return h.one("catalog-create-activity");}
     public static void main(String[]args)throws Exception{
      TodayScreen h=fresh(0);
      need(h.db.writes==0&&h.one("catalog-name").isAttachedToWindow(),"open_readonly");
      System.out.println("VALID_CATALOG_RENDER_WITNESS");
      h.text("catalog-name"," ");h.text("catalog-package","example.test");h.one("catalog-create-app").performClick();
      need(h.queue.isEmpty()&&h.db.writes==0&&!((TextView)h.one("catalog-validation")).text.isEmpty(),"invalid_name");
      h.text("catalog-name","Same");h.text("catalog-package","bad package");h.one("catalog-create-app").performClick();need(h.queue.isEmpty(),"invalid_package");
      h.text("catalog-package","example.test");View old=h.one("catalog-create-app");old.performClick();old.performClick();
      need(h.queue.size()==1,"pending_once");h.drain();need(h.db.writes==1&&h.db.apps.get(1L)[0].equals("Same"),"one_app");
      old.performClick();need(h.queue.isEmpty(),"detached_create");
      h.text("catalog-name","Same");h.text("catalog-package","example.test");h.one("catalog-create-app").performClick();h.drain();
      need(h.db.writes==1&&!((TextView)h.one("catalog-validation")).text.isEmpty(),"duplicate_visible");
      h.text("catalog-package","");h.one("catalog-create-app").performClick();h.drain();need(h.db.apps.size()==2&&h.db.writes==2,"same_name_distinct");
      h=fresh(1);View pick=h.one("catalog-app-10");h.one("catalog-back").performClick();pick.performClick();need(h.queue.isEmpty()&&h.db.links==0,"detached_picker");
      h=fresh(1);View create=submit(h);h.text("catalog-activity-title"," ");create.performClick();need(h.queue.isEmpty()&&h.db.links==0,"invalid_activity");
      h.text("catalog-activity-title","Linked");create.performClick();create.performClick();need(h.queue.size()==1,"activity_pending_once");h.drain();
      need(h.db.links==1&&h.db.attempts==1,"one_link");create.performClick();need(h.queue.isEmpty(),"old_confirm");
      h=fresh(1);create=submit(h);h.one("catalog-back").performClick();create.performClick();
      need(h.db.last.terminal&&h.queue.isEmpty()&&h.db.links==0,"cancel_closes_plan");
      h=fresh(1);create=submit(h);h.db.fail=true;create.performClick();h.drain();create.performClick();
      need(h.db.links==0&&h.db.attempts==1&&h.queue.isEmpty()&&!create.isEnabled(),"failure_terminal");
      h=fresh(1);pick=h.one("catalog-app-10");pick.performClick();h.content();h.drain();
      need(h.db.last.terminal&&h.outer.children.isEmpty(),"stale_completion_closes");
      h=fresh(1);create=submit(h);h.activity.finishing=true;create.performClick();need(h.queue.isEmpty(),"finishing_readonly");
      h.activity.finishing=false;h.activity.destroyed=true;create.performClick();need(h.queue.isEmpty(),"destroyed_readonly");
      h=fresh(1);create=submit(h);create.setEnabled(false);create.performClick();need(h.queue.isEmpty(),"disabled_readonly");
      h=fresh(1);create=submit(h);create.attached=false;create.performClick();need(h.queue.isEmpty(),"detached_control");
      h=fresh(0);h.text("catalog-name","Same");h.text("catalog-package","");old=h.one("catalog-create-app");old.performClick();h.db.failRead=true;h.drain();old.performClick();
      need(h.db.writes==1&&h.queue.isEmpty()&&!old.isEnabled(),"refresh_failure_no_duplicate");
      System.out.println("CATALOG_UI_MODEL "+checked+" scenarios PASS HOST_DOUBLES_ONLY");
     }
    }''',
    "Compile.java":r'''import javax.tools.*;import java.nio.file.*;import java.util.*;
    class Compile{public static void main(String[]a)throws Exception{List<String>x=new ArrayList<>(List.of("-d",a[0]));try(var s=Files.walk(Path.of(a[0]))){s.filter(p->p.toString().endsWith(".java")&&!p.getFileName().toString().equals("Compile.java")).forEach(p->x.add(p.toString()));}if(ToolProvider.getSystemJavaCompiler().run(null,null,null,x.toArray(new String[0]))!=0)System.exit(1);}}'''
    }

    expected = (
        "open_readonly", "invalid_name", "invalid_package", "pending_once", "one_app",
        "detached_create", "duplicate_visible", "same_name_distinct", "detached_picker",
        "invalid_activity", "activity_pending_once", "one_link", "old_confirm",
        "cancel_closes_plan", "failure_terminal", "stale_completion_closes",
        "finishing_readonly", "destroyed_readonly", "disabled_readonly",
        "detached_control", "refresh_failure_no_duplicate",
    )
    assert len(expected)==21 and len(set(expected))==len(expected)
    path=ROOT/"src/main/java/com/supercubegame/pockettodo/AppCatalog.java"
    source=path.read_text()
    mutations=(
        ("&&control.isEnabled();","&&true;","disabled_readonly"),
        ("if(!current(p)){plan.close();return;}","if(false){plan.close();return;}","stale_completion_closes"),
        ("if(plan!=null){plan.close();plan=null;}","if(plan!=null){plan=null;}","cancel_closes_plan"),
        ("&&!host.activity.isDestroyed();","&&true;","destroyed_readonly"),
        ("p.submitted=false;create.setEnabled(false);host.message","p.submitted=false;host.message","refresh_failure_no_duplicate"),
    )
    with tempfile.TemporaryDirectory(prefix="catalog-ui-model-") as tmp:
        root=Path(tmp)
        for name,content in files.items():
            target=root/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(content)
        product=root/"com/supercubegame/pockettodo/AppCatalog.java"
        def execute(code):
            product.write_text(code)
            compiled=subprocess.run(["java",str(root/"Compile.java"),tmp],
                capture_output=True,text=True,timeout=30)
            assert compiled.returncode==0,("catalog model compile failed",compiled.stdout,compiled.stderr)
            return subprocess.run(["java","-cp",tmp,"com.supercubegame.pockettodo.Test"],
                capture_output=True,text=True,timeout=30)
        def records(result):
            return tuple(re.findall(r"^CATALOG_UI_CHECK ([a-z_]+)$",result.stdout,re.M))
        good=execute(source)
        assert good.returncode==0 and not good.stderr,(good.stdout,good.stderr)
        assert records(good)==expected,("catalog model omitted/reordered cases",good.stdout)
        assert good.stdout.splitlines().count("VALID_CATALOG_RENDER_WITNESS")==1
        assert good.stdout.splitlines()[-1]=="CATALOG_UI_MODEL "+str(len(expected))+" scenarios PASS HOST_DOUBLES_ONLY"
        print(good.stdout.strip(),flush=True)
        witnessed=[]
        for old,new,label in mutations:
            assert source.count(old)==1,(old,source.count(old))
            changed=source.replace(old,new,1)
            assert changed!=source
            result=execute(changed)
            assert result.returncode==1,("mutant did not fail by Java assertion",label,result.returncode,result.stdout,result.stderr)
            assert result.stdout.splitlines().count("VALID_CATALOG_RENDER_WITNESS")==1
            assert records(result)==expected[:expected.index(label)],("mutant failed before its intended assertion",label,result.stdout,result.stderr)
            assert "AssertionError: "+label+"\n" in result.stderr,(label,result.stdout,result.stderr)
            witnessed.append(label)
            print("WITNESSED_UI_MUTANT_REJECTED "+label,flush=True)
    receipt=dict(status="PASS",checks=len(expected),labels=list(expected),
        compiled_witnessed_mutants=len(witnessed),mutants=witnessed,
        product_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        scope="ACTUAL_APPCATALOG_JAVA_WITH_UI_DB_DOUBLES_NOT_ANDROID_SQLITE_GESTURES_OR_LIFECYCLE",
        release_ready=False)
    print("CATALOG_UI_HOST "+json.dumps(receipt,sort_keys=True),flush=True)
    return receipt

def selftest():
    catalog_ui_selftest()
    assert REQUIRED == EXPECTED
    assert [len(EXPECTED[p]) for p in ("seed", "deleted", "undone")] == [16,16,2]
    rejected = 0
    for api in (26,34):
        value, manifest, logs = fixture(api)
        validate(value,manifest,logs,api,"a"*40,"123","1")
        cases = []
        for key in value:
            bad=copy.deepcopy(value);del bad[key];cases.append((bad,manifest,logs))
        for key in manifest:
            bad=dict(manifest);del bad[key];cases.append((value,bad,logs))
        for key, wrong in (("checks",34.0),("checks",True),("release_ready",0),("api",float(api)),
            ("default_test_restored",1),("commit","d"*40),("run_id","999"),("run_attempt","2"),
            ("apk_sha256","d"*64),("native_ui","WIDGET_CALLBACKS"),("status","FAIL"),("error","sentinel")):
            bad=copy.deepcopy(value);bad[key]=wrong;cases.append((bad,manifest,logs))
        for phase,labels in EXPECTED.items():
            for label in labels:
                bad=dict(logs);bad[phase]=bad[phase].replace("TODO_PASS "+label+"\n","");cases.append((value,manifest,bad))
        for bad,m,l in cases:
            try:validate(bad,m,l,api,"a"*40,"123","1")
            except (AssertionError,KeyError,TypeError):rejected+=1
            else:raise AssertionError("invalid receipt accepted")
    source=inspect.getsource(validate)
    for old,new,key,wrong in (
        ('assert value["native_ui"] == "INSTALLED_VIEW_CALLBACKS_NOT_PHYSICAL_TOUCH"',"assert True","native_ui","WIDGET_CALLBACKS"),
        ('assert value["release_ready"] is False',"assert True","release_ready",0),
        ('assert type(value["checks"]) is int and value["checks"] == len(labels) and value["labels"] == labels',"assert True","checks",34.0)):
        assert source.count(old)==1
        ns=dict(globals());exec(compile(source.replace(old,new),"<catalog-validator-mutant>","exec"),ns)
        v,m,l=fixture(26);ns["validate"](v,m,l,26,"a"*40,"123","1")
        v[key]=wrong
        try:validate(v,m,l,26,"a"*40,"123","1")
        except AssertionError:pass
        else:raise AssertionError("negative witness accepted")
        ns["validate"](v,m,l,26,"a"*40,"123","1")
    parse=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Parse {public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();Set<String>w=new HashSet<>(Arrays.asList("need","addition","activityRow"));StringBuilder out=new StringBuilder();
for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers())
if(m instanceof MethodTree&&w.remove(((MethodTree)m).getName().toString()))out.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");
if(!w.isEmpty())throw new AssertionError(w);Files.writeString(Path.of(a[1]),out.toString());}}}'''
    harness=r'''import java.util.*;class Oracle{
__METHODS__
static List<String> r(String...v){return new ArrayList<>(Arrays.asList(v));}
public static void main(String[]a){
need(activityRow(8,7,0,"Plain").equals(r("1:8","1:8","1:7","0:","3:Plain","1:0")),"null_app");
System.out.println("ORACLE_VALID_WITNESS");
Map<String,List<List<String>>> b=new TreeMap<>();
b.put("revision",new ArrayList<>(Arrays.asList(r("rowid","id","value"),r("1:1","1:1","1:9"))));
b.put("activities",new ArrayList<>(Arrays.asList(r("rowid","id","category_id","application_id","title","archived"))));
b.put("ledger",new ArrayList<>(Arrays.asList(r("id"),r("3:keep"))));
String frozen=b.toString();List<String> row=activityRow(8,7,10,"Same");
Map<String,List<List<String>>> o=addition(b,"activities",row);
need(o.get("activities").size()==2&&o.get("activities").get(1).equals(r("1:8","1:8","1:7","1:10","3:Same","1:0")),"exact_row");
need(o.get("revision").get(1).equals(r("1:1","1:1","1:10")),"one_revision");
need(b.toString().equals(frozen)&&o.get("ledger").equals(b.get("ledger")),"unchanged_others");
row.set(4,"3:Changed");need(o.get("activities").get(1).get(4).equals("3:Same"),"owned_row");
System.out.println("CATALOG_ORACLE_PASS");
}}'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"Parse.java").write_text(parse);(p/"TodoInstrumentation.java").write_text(JAVA)
        subprocess.run(["java",str(p/"Parse.java"),str(p/"TodoInstrumentation.java"),str(p/"members")],check=True,timeout=30)
        members=(p/"members").read_text()
        def execute(code):
            (p/"Oracle.java").write_text(harness.replace("__METHODS__",code))
            return subprocess.run(["java",str(p/"Oracle.java")],capture_output=True,text=True,timeout=30)
        good=execute(members);assert good.returncode==0,(good.stdout,good.stderr);print(good.stdout.strip())
        for old,new,label in (
            ('out.get(table).add(new ArrayList<>(row));',';',"exact_row"),
            ('Math.incrementExact(Long.parseLong(rev.get(1).get(col).substring(2)))','Long.parseLong(rev.get(1).get(col).substring(2))',"one_revision"),
            ('rows.add(new ArrayList<>(r))','rows.add(r)',"unchanged_others")):
            assert members.count(old)==1
            result=execute(members.replace(old,new))
            assert result.returncode!=0 and "ORACLE_VALID_WITNESS" in result.stdout and "AssertionError: "+label in result.stderr,(label,result.stdout,result.stderr)
    assert callable(driver())
    report_selftest()
    print("CATALOG_HOST "+json.dumps(dict(status="PASS",positive=2,negative=rejected,
        witnessed_validator_mutants=3,witnessed_oracle_mutants=3,
        scope="HOST_RECEIPT_ORACLE_JAVA_SYNTAX_NOT_ANDROID",release_ready=False)))

if __name__ == "__main__":
    {"selftest": selftest, "android": driver(), "report": report}[sys.argv[1]]()
