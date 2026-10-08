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
REQUIRED = {'seed': ['backend_fixture', 'application_insert', 'duplicate_package_readonly', 'invalid_package_readonly', 'prepare_readonly', 'create_linked_once', 'duplicate_plan_readonly', 'canceled_plan_readonly', 'second_category_reuse', 'unassigned_activity', 'stale_app_readonly', 'stale_category_readonly', 'late_rollback', 'consumed_failure_readonly', 'outer_transaction_readonly', 'backend_checkpoint', 'rename_fixture', 'rename_prepare_readonly', 'rename_exact_state', 'rename_duplicate', 'rename_same_readonly', 'rename_cancel', 'rename_blank', 'rename_blank_consumed', 'rename_stale', 'rename_unrelated_change', 'rename_late_rollback', 'rename_failure_consumed', 'rename_readback_rollback', 'rename_prepare_outer', 'rename_confirm_outer', 'rename_missing', 'rename_foreign', 'rename_owner_retained', 'rename_closed_helper', 'rename_reopened_state'], 'deleted': ['backend_restart', 'backend_backup', 'ui_fixture', 'catalog_open_readonly', 'invalid_name_readonly', 'invalid_package_ui_readonly', 'create_application_ui', 'duplicate_package_ui_readonly', 'same_title_distinct_ids', 'cancel_picker_readonly', 'first_category_link', 'duplicate_click_readonly', 'second_category_link', 'old_picker_readonly', 'unassigned_retained', 'ui_checkpoint', 'rename_ui_prepare', 'rename_ui_blank', 'rename_ui_exact', 'rename_ui_duplicate', 'rename_ui_cancel', 'rename_ui_same', 'rename_ui_stale', 'rename_ui_detached', 'rename_ui_final'], 'undone': ['ui_restart', 'ui_backup']}
EXPECTED = {'seed': ['backend_fixture', 'application_insert', 'duplicate_package_readonly', 'invalid_package_readonly', 'prepare_readonly', 'create_linked_once', 'duplicate_plan_readonly', 'canceled_plan_readonly', 'second_category_reuse', 'unassigned_activity', 'stale_app_readonly', 'stale_category_readonly', 'late_rollback', 'consumed_failure_readonly', 'outer_transaction_readonly', 'backend_checkpoint', 'rename_fixture', 'rename_prepare_readonly', 'rename_exact_state', 'rename_duplicate', 'rename_same_readonly', 'rename_cancel', 'rename_blank', 'rename_blank_consumed', 'rename_stale', 'rename_unrelated_change', 'rename_late_rollback', 'rename_failure_consumed', 'rename_readback_rollback', 'rename_prepare_outer', 'rename_confirm_outer', 'rename_missing', 'rename_foreign', 'rename_owner_retained', 'rename_closed_helper', 'rename_reopened_state'], 'deleted': ['backend_restart', 'backend_backup', 'ui_fixture', 'catalog_open_readonly', 'invalid_name_readonly', 'invalid_package_ui_readonly', 'create_application_ui', 'duplicate_package_ui_readonly', 'same_title_distinct_ids', 'cancel_picker_readonly', 'first_category_link', 'duplicate_click_readonly', 'second_category_link', 'old_picker_readonly', 'unassigned_retained', 'ui_checkpoint', 'rename_ui_prepare', 'rename_ui_blank', 'rename_ui_exact', 'rename_ui_duplicate', 'rename_ui_cancel', 'rename_ui_same', 'rename_ui_stale', 'rename_ui_detached', 'rename_ui_final'], 'undone': ['ui_restart', 'ui_backup']}
SHARED_SHA256 = "9b1b435b21b630e1230f1e112a794962825665982ceabdbb41cc68583ce3d70d"
# Reuse unchanged transport/receipt infrastructure, never the category cases.
# Pin the whole dependency: a future edit must explicitly review this adapter.
assert hashlib.sha256(Path(shared.__file__).read_bytes()).hexdigest() == SHARED_SHA256, "catalog shared gate changed"
for marker in (" static Map<String,List<List<String>>> expected(", " void save(", " void seed(", " @Override public void onCreate"):
    assert shared.JAVA.count(marker) == 1, "ambiguous Java scaffold boundary"
CASES = r'''
 Object renamePlan(AppDatabase h,long id)throws Exception{
  return invoke(h,"prepareApplicationRename",new Class<?>[]{long.class},id);
 }
 boolean renameConfirm(AppDatabase h,Object plan,String name)throws Exception{
  return (Boolean)invoke(h,"confirmApplicationRename",new Class<?>[]{plan.getClass(),String.class},plan,name);
 }
 static Map<String,List<List<String>>> renamed(Map<String,List<List<String>>> before,long id,String name){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();for(List<String> row:e.getValue())rows.add(new ArrayList<>(row));out.put(e.getKey(),rows);
  }
  List<List<String>> apps=out.get("applications");int key=apps.get(0).lastIndexOf("id"),title=apps.get(0).indexOf("name"),found=0;
  need(key>=0&&title>=0,"rename oracle columns");
  for(int i=1;i<apps.size();i++)if(apps.get(i).get(key).equals("1:"+id)){apps.get(i).set(title,"3:"+name);found++;}
  need(found==1,"rename oracle identity");
  List<List<String>> rev=out.get("revision");int value=rev.get(0).indexOf("value");
  need(value>=0&&rev.size()==2,"rename oracle revision");
  rev.get(1).set(value,"1:"+Math.incrementExact(Long.parseLong(rev.get(1).get(value).substring(2))));
  return out;
 }
 void renameBackend(AppDatabase h)throws Exception{
  h.addApplication(11,"Changed","example.other");
  h.savePath(5,Arrays.asList("Linked path"));h.saveTags(5,Arrays.asList("Linked tag"));
  h.createNote("rename-note",5,"Linked note");h.saveNote("rename-note",Arrays.asList(com.supercubegame.pockettodo.NoteDocument.Block.text("body","Preserved",false)));
  h.recordBatch("rename-batch",Arrays.asList(new com.supercubegame.pockettodo.Ledger.Entry("rename-entry",5,java.time.LocalDate.of(2026,10,8),com.supercubegame.pockettodo.Ledger.Kind.EXPENSE,25,"Preserved")));
  pass(h.count("applications")==2&&h.count("notes")==2&&h.path(5).equals(Arrays.asList("Linked path")),"rename_fixture");
  Map<String,List<List<String>>> before=state(h);Object p=renamePlan(h,10);
  pass(state(h).equals(before)&&((Number)invoke(p,"applicationId",new Class<?>[]{})).longValue()==10,"rename_prepare_readonly");
  pass(renameConfirm(h,p," Renamed ")&&state(h).equals(renamed(before,10,"Renamed")),"rename_exact_state");
  readonly(h,IllegalStateException.class,()->renameConfirm(h,p,"Again"),"rename_duplicate");
  Object same=renamePlan(h,10);before=state(h);
  pass(!renameConfirm(h,same,"Renamed")&&state(h).equals(before),"rename_same_readonly");
  Object canceled=renamePlan(h,10);close(canceled);
  readonly(h,IllegalStateException.class,()->renameConfirm(h,canceled,"Bad"),"rename_cancel");
  Object blank=renamePlan(h,10);
  readonly(h,IllegalArgumentException.class,()->renameConfirm(h,blank," "),"rename_blank");
  readonly(h,IllegalStateException.class,()->renameConfirm(h,blank,"Bad"),"rename_blank_consumed");
  Object stale=renamePlan(h,10);h.getWritableDatabase().execSQL("UPDATE applications SET name='External' WHERE id=10");
  readonly(h,IllegalStateException.class,()->renameConfirm(h,stale,"Bad"),"rename_stale");
  Object unrelated=renamePlan(h,10);h.addTodo("rename-intervening","Changed");
  readonly(h,IllegalStateException.class,()->renameConfirm(h,unrelated,"Bad"),"rename_unrelated_change");
  Object late=renamePlan(h,10);before=state(h);
  h.getWritableDatabase().execSQL("CREATE TRIGGER rename_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'rename_late_fault'); END");
  Throwable failure=null;try{renameConfirm(h,late,"Bad");}catch(Throwable t){failure=t;}
  boolean sentinel=false;for(Throwable t=failure;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("rename_late_fault"))sentinel=true;
  pass(sentinel&&state(h).equals(before),"rename_late_rollback");
  h.getWritableDatabase().execSQL("DROP TRIGGER rename_fault");
  readonly(h,IllegalStateException.class,()->renameConfirm(h,late,"Bad"),"rename_failure_consumed");
  Object damage=renamePlan(h,10);before=state(h);
  h.getWritableDatabase().execSQL("CREATE TRIGGER rename_damage AFTER UPDATE OF name ON applications WHEN NEW.id=10 BEGIN UPDATE applications SET package_name='example.damaged' WHERE id=11; END");
  failure=null;try{renameConfirm(h,damage,"Bad");}catch(Throwable t){failure=t;}
  sentinel=false;for(Throwable t=failure;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("应用改名回读不一致"))sentinel=true;
  pass(sentinel&&state(h).equals(before),"rename_readback_rollback");
  h.getWritableDatabase().execSQL("DROP TRIGGER rename_damage");
  Object outer=renamePlan(h,10);h.getWritableDatabase().beginTransaction();
  try{
   readonly(h,IllegalStateException.class,()->renamePlan(h,10),"rename_prepare_outer");
   readonly(h,IllegalStateException.class,()->renameConfirm(h,outer,"Bad"),"rename_confirm_outer");
  }finally{h.getWritableDatabase().endTransaction();}
  readonly(h,IllegalArgumentException.class,()->renamePlan(h,999),"rename_missing");
  Object foreignPlan=renamePlan(h,10);
  try(AppDatabase foreign=AppDatabase.openSchema3(getTargetContext(),name())){
   readonly(h,IllegalArgumentException.class,()->renameConfirm(foreign,foreignPlan,"Bad"),"rename_foreign");
  }
  before=state(h);pass(renameConfirm(h,foreignPlan,"Final")&&state(h).equals(renamed(before,10,"Final")),"rename_owner_retained");
  Object closed=renamePlan(h,10);before=state(h);h.close();
  readonly(h,IllegalStateException.class,()->renameConfirm(h,closed,"Bad"),"rename_closed_helper");
  pass(state(h).equals(before),"rename_reopened_state");
  save("backend-state",state(h).toString());
 }
 void renameUI(AppDatabase h)throws Exception{
  click("应用目录",false);Map<String,List<List<String>>> before=state(h);
  click("catalog-rename-1",true);
  boolean[] identity={false};ui(()->identity[0]=((TextView)one("catalog-rename-identity",true)).getText().toString().contains("#1"));
  pass(identity[0]&&state(h).equals(before),"rename_ui_prepare");
  text("catalog-rename-name"," ");click("catalog-rename-save",true);
  boolean[] visible={false};ui(()->visible[0]=((TextView)one("catalog-rename-validation",true)).getText().length()>0);
  pass(visible[0]&&state(h).equals(before),"rename_ui_blank");
  text("catalog-rename-name","UI renamed");final View[] old={null};
  ui(()->{old[0]=one("catalog-rename-save",true);need(old[0].performClick(),"rename submit");old[0].performClick();});ready();
  Map<String,List<List<String>>> expected=renamed(before,1,"UI renamed");
  pass(state(h).equals(expected),"rename_ui_exact");
  ui(()->old[0].performClick());ready();pass(state(h).equals(expected),"rename_ui_duplicate");
  click("catalog-rename-2",true);before=state(h);click("catalog-rename-cancel",true);
  pass(state(h).equals(before),"rename_ui_cancel");
  click("catalog-rename-1",true);click("catalog-rename-save",true);
  pass(state(h).equals(before),"rename_ui_same");
  click("catalog-rename-1",true);h.getWritableDatabase().execSQL("UPDATE applications SET name='External UI' WHERE id=1");
  before=state(h);text("catalog-rename-name","Overwrite");click("catalog-rename-save",true);
  ui(()->visible[0]=((TextView)one("catalog-rename-validation",true)).getText().length()>0&&!one("catalog-rename-save",true).isEnabled());
  pass(visible[0]&&state(h).equals(before),"rename_ui_stale");
  click("catalog-rename-cancel",true);click("catalog-rename-1",true);ui(()->old[0]=one("catalog-rename-save",true));click("catalog-back",true);
  before=state(h);ui(()->old[0].performClick());ready();pass(state(h).equals(before),"rename_ui_detached");
  click("应用目录",false);click("catalog-rename-1",true);text("catalog-rename-name","Final UI");before=state(h);click("catalog-rename-save",true);
  pass(state(h).equals(renamed(before,1,"Final UI")),"rename_ui_final");
  click("catalog-back",true);save("ui-state",state(h).toString());save("ui-media",media().toString());
 }
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
   renameBackend(h);
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
  renameUI(h);
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
            s=s.replace("checks=40","checks=63")
        if name=="report":
            old='["physical_phone_gestures", "all_lifecycle_stale_duplicate_UI_cases", "referenced_media_fixture", "ordinary_todo_sorting"]'
            assert s.count(old)==1
            s=s.replace(old,'["physical_phone_gestures", "referenced_media_fixture", "catalog_archive", "category_shortcuts", "external_app_launch", "full_lifecycle", "field_UI"]')
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

    key="com/supercubegame/pockettodo/AppDatabase.java"
    files[key]=files[key].rstrip()[:-1]+RENAME_UI_DB_DOUBLE+"\n}"

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
    rename_host_selftest()
    catalog_ui_selftest()
    assert REQUIRED == EXPECTED
    assert [len(EXPECTED[p]) for p in ("seed", "deleted", "undone")] == [36,25,2]
    rejected = 0
    for api in (26,34):
        value, manifest, logs = fixture(api)
        validate(value,manifest,logs,api,"a"*40,"123","1")
        cases = []
        for key in value:
            bad=copy.deepcopy(value);del bad[key];cases.append((bad,manifest,logs))
        for key in manifest:
            bad=dict(manifest);del bad[key];cases.append((value,bad,logs))
        for key, wrong in (("checks",63.0),("checks",True),("release_ready",0),("api",float(api)),
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
        ('assert type(value["checks"]) is int and value["checks"] == len(labels) and value["labels"] == labels',"assert True","checks",63.0)):
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

RENAME_UI_DB_DOUBLE = '     int renames;\n     ApplicationRenamePlan lastRename;\n     String renameState(){StringBuilder s=new StringBuilder();for(Map.Entry<Long,String[]> e:apps.entrySet())s.append(e.getKey()).append(Arrays.toString(e.getValue()));return s.toString()+writes;}\n     static class ApplicationRenamePlan implements AutoCloseable{\n      long id;String name,pkg,before;boolean terminal;public void close(){terminal=true;}\n      long applicationId(){return id;}String name(){return name;}String packageName(){return pkg;}\n     }\n     ApplicationRenamePlan prepareApplicationRename(long id){\n      ApplicationRenamePlan p=new ApplicationRenamePlan();p.id=id;p.name=apps.get(id)[0];p.pkg=apps.get(id)[1];p.before=renameState();lastRename=p;return p;\n     }\n     boolean confirmApplicationRename(ApplicationRenamePlan p,String name){\n      renames++;if(p.terminal)throw new IllegalStateException("closed");p.close();\n      if(fail||!p.before.equals(renameState()))throw new IllegalStateException("changed");\n      if(p.name.equals(name))return false;apps.get(p.id)[0]=name;writes++;return true;\n     }\n'

def rename_host_selftest():
    """Compile extracted current Java methods and the actual current UI.
    Doubles are scoped host tests, never SQLite/device/backup acceptance."""
    backend_test='import java.util.*;\nclass Test {\n static int checks;\n static void need(boolean b,String label){if(!b)throw new AssertionError(label);checks++;System.out.println("RENAME_BACKEND_CHECK "+label);}\n interface Action{void run()throws Exception;}\n static void refuses(Class<?> type,Action action,String label)throws Exception{\n  try{action.run();}catch(Exception e){need(type.isInstance(e),label);return;}\n  throw new AssertionError(label);\n }\n public static void main(String[] args)throws Exception{\n  AppDatabase h=new AppDatabase();\n  var p=h.prepareApplicationRename(10);\n  need(p.applicationId()==10&&p.name().equals("Same")&&p.packageName().equals("example.one")&&h.sql.writes==0,"prepare_readonly");\n  System.out.println("RENAME_BACKEND_VALID_WITNESS");\n  need(h.confirmApplicationRename(p," Renamed ")&&h.sql.name.equals("Renamed")&&h.sql.other.equals("Same")&&h.sql.rev==10,"exact_target");\n  final var used=p;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(used,"Again"),"single_attempt");\n  p=h.prepareApplicationRename(10);p.close();final var canceled=p;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(canceled,"Again"),"cancel");\n  p=h.prepareApplicationRename(10);h.sql.name="Intervening";final var stale=p;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(stale,"Again"),"stale");\n  need(h.sql.name.equals("Intervening")&&h.sql.rev==10,"stale_readonly");\n  p=h.prepareApplicationRename(10);final var blank=p;\n  refuses(IllegalArgumentException.class,()->h.confirmApplicationRename(blank," "), "blank");\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(blank,"Again"),"blank_consumed");\n  p=h.prepareApplicationRename(10);need(!h.confirmApplicationRename(p,"Intervening")&&h.sql.rev==10,"same_readonly");\n  p=h.prepareApplicationRename(10);final var foreign=p;\n  refuses(IllegalArgumentException.class,()->new AppDatabase().confirmApplicationRename(foreign,"Bad"),"foreign");\n  need(h.confirmApplicationRename(p,"Owner"),"foreign_does_not_consume");\n  p=h.prepareApplicationRename(10);h.restoreSession=new Object();final var session=p;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(session,"Bad"),"session");\n  p=h.prepareApplicationRename(10);SQLiteDatabase previous=h.sql;h.sql=new SQLiteDatabase();h.sql.name=previous.name;h.sql.rev=previous.rev;final var connection=p;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(connection,"Bad"),"connection");\n  p=h.prepareApplicationRename(10);h.sql.outer=true;final var outer=p;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(outer,"Bad"),"outer");\n  h.sql=new SQLiteDatabase();p=h.prepareApplicationRename(10);h.sql.fault=true;final var fault=p;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(fault,"Bad"),"rollback");\n  need(h.sql.name.equals("Same")&&h.sql.rev==9,"rollback_state");\n  h.sql.fault=false;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(fault,"Bad"),"failure_consumed");\n  p=h.prepareApplicationRename(10);h.sql.corrupt=true;final var corrupt=p;\n  refuses(IllegalStateException.class,()->h.confirmApplicationRename(corrupt,"Bad"),"readback");\n  need(h.sql.name.equals("Same")&&h.sql.other.equals("Same")&&h.sql.rev==9,"readback_rollback");\n  h.sql.corrupt=false;\n  refuses(IllegalArgumentException.class,()->h.prepareApplicationRename(0),"invalid_id");\n  refuses(IllegalArgumentException.class,()->h.prepareApplicationRename(11),"missing_id");\n  h.sql.outer=true;\n  refuses(IllegalStateException.class,()->h.prepareApplicationRename(10),"prepare_outer");\n  System.out.println("RENAME_BACKEND_PASS "+checks+" HOST_SQL_DOUBLES_NOT_ANDROID");\n }\n}\n'
    prelude='\nimport java.util.*;import java.io.*;import java.nio.charset.StandardCharsets;\nclass Ledger{static void positive(long id){if(id<=0)throw new IllegalArgumentException();}}\nclass Cursor implements AutoCloseable{\n static final int FIELD_TYPE_NULL=0,FIELD_TYPE_INTEGER=1,FIELD_TYPE_STRING=3,FIELD_TYPE_BLOB=4;\n String[] row;boolean seen;Cursor(String...v){row=v;}\n boolean moveToFirst(){return row.length>0;}String getString(int i){return row[i];}\n public void close(){}\n}\nclass SQLiteDatabase{\n String name="Same",pkg="example.one",other="Same";long rev=9;int writes;boolean outer,fault,corrupt;\n boolean inTransaction(){return outer;}void beginTransaction(){}void setTransactionSuccessful(){}void endTransaction(){}\n boolean isOpen(){return true;}\n Cursor rawQuery(String q,String[] args){\n  if(!q.equals("SELECT name,package_name FROM applications WHERE id=?"))throw new AssertionError(q);\n  return args[0].equals("10")?new Cursor(name,pkg):new Cursor();\n }\n void execSQL(String q,Object[] args){\n  if(!q.equals("UPDATE applications SET name=? WHERE id=?")||!args[1].equals(10L))throw new AssertionError(q);\n  name=(String)args[0];writes++;if(corrupt)other="CORRUPT";\n }\n}\nclass AppDatabase{\n SQLiteDatabase sql=new SQLiteDatabase();Object restoreSession=new Object();\n SQLiteDatabase getReadableDatabase(){return sql;}SQLiteDatabase getWritableDatabase(){return sql;}\n interface Work<T>{T run(SQLiteDatabase db);}\n <T>T tx(Work<T> a){\n  String name=sql.name,other=sql.other;long rev=sql.rev;int writes=sql.writes;\n  try{return a.run(sql);}catch(RuntimeException e){sql.name=name;sql.other=other;sql.rev=rev;sql.writes=writes;throw e;}\n }\n static void noteDeletionNoOuterTransaction(SQLiteDatabase db){if(db.outer)throw new IllegalStateException();}\n static String text(String s){if(s==null||s.trim().isEmpty())throw new IllegalArgumentException();return s.trim();}\n static long revision(SQLiteDatabase db){return db.rev;}\n static long bump(SQLiteDatabase db){if(db.fault)throw new IllegalStateException("late fault");return ++db.rev;}\n static final String[] SNAPSHOT_TABLES={"revision","applications","ledger"};\n static class LimitedBytes extends ByteArrayOutputStream{}\n static void require(boolean b,String message){if(!b)throw new IllegalArgumentException(message);}\n static void utf8(DataOutputStream out,String s)throws IOException{blob(out,s.getBytes(StandardCharsets.UTF_8));}\n static void blob(DataOutputStream out,byte[] b)throws IOException{out.writeInt(b.length);out.write(b);}\n static byte[] readBlob(DataInputStream in)throws IOException{int n=in.readInt();if(n<0||n>in.available())throw new IllegalArgumentException();byte[] b=new byte[n];in.readFully(b);return b;}\n static String readText(DataInputStream in)throws IOException{return new String(readBlob(in),StandardCharsets.UTF_8);}\n static byte[] noteDeletionState(SQLiteDatabase db){\n  try{\n   var bytes=new ByteArrayOutputStream();var out=new DataOutputStream(bytes);\n   out.writeInt(0x4e444c31);out.writeInt(3);out.writeInt(3);\n   table(out,"revision",new String[]{"id","id","value"},new Object[][]{{1L,1L,db.rev}});\n   table(out,"applications",new String[]{"id","id","name","package_name"},new Object[][]{{10L,10L,db.name,db.pkg},{20L,20L,db.other,"example.two"}});\n   table(out,"ledger",new String[]{"rowid","id","payload","nullable"},new Object[][]{{1L,"keep",new byte[]{0,1,-1},null}});\n   return bytes.toByteArray();\n  }catch(IOException e){throw new RuntimeException(e);}\n }\n static void table(DataOutputStream out,String table,String[] names,Object[][] rows)throws IOException{\n  utf8(out,table);out.writeInt(names.length);for(String n:names)utf8(out,n);out.writeInt(rows.length);\n  for(Object[] row:rows)for(Object value:row){\n   if(value instanceof Long){out.writeByte(1);out.writeLong((Long)value);}\n   else if(value instanceof String){out.writeByte(3);utf8(out,(String)value);}\n   else if(value instanceof byte[]){out.writeByte(4);blob(out,(byte[])value);}\n   else out.writeByte(0);\n  }\n }\n'
    ui_test='package com.supercubegame.pockettodo;\nimport android.view.View;import android.widget.*;\npublic class Test{\n static int checked;\n static void need(boolean b,String label){if(!b)throw new AssertionError(label);checked++;System.out.println("RENAME_UI_CHECK "+label);}\n static TodayScreen fresh(){\n  TodayScreen h=new TodayScreen();h.db.addApplication(10,"Same","example.one");h.db.addApplication(20,"Same","example.two");\n  View anchor=new View();h.outer.addView(anchor);new AppCatalog(h,0,()->h.content()).open(anchor);h.drain();return h;\n }\n static View edit(TodayScreen h){h.one("catalog-rename-10").performClick();h.drain();return h.one("catalog-rename-save");}\n public static void main(String[]args){\n  TodayScreen h=fresh();need(h.one("catalog-app-10").isAttachedToWindow()&&h.one("catalog-app-20").isAttachedToWindow(),"render_existing");\n  System.out.println("RENAME_UI_VALID_WITNESS");\n  View save=edit(h);need(h.db.writes==2&&((TextView)h.one("catalog-rename-identity")).text.contains("#10"),"prepare_readonly");\n  h.text("catalog-rename-name"," ");save.performClick();need(h.queue.isEmpty()&&h.db.writes==2&&!((TextView)h.one("catalog-rename-validation")).text.isEmpty(),"blank_visible");\n  h.text("catalog-rename-name","Renamed");save.performClick();save.performClick();need(h.queue.size()==1,"pending_once");h.drain();\n  need(h.db.writes==3&&h.db.renames==1&&h.db.apps.get(10L)[0].equals("Renamed")&&h.db.apps.get(20L)[0].equals("Same")&&h.db.apps.get(10L)[1].equals("example.one"),"exact_identity");\n  save.performClick();need(h.queue.isEmpty()&&h.db.renames==1,"old_save");\n  h=fresh();save=edit(h);save.performClick();h.drain();need(h.db.writes==2&&h.db.renames==1,"same_readonly");\n  h=fresh();save=edit(h);h.one("catalog-rename-cancel").performClick();h.drain();save.performClick();need(h.db.lastRename.terminal&&h.db.writes==2&&h.queue.isEmpty(),"cancel_readonly");\n  h=fresh();save=edit(h);h.db.apps.get(10L)[0]="Changed";h.text("catalog-rename-name","Overwrite");save.performClick();h.drain();\n  need(h.db.apps.get(10L)[0].equals("Changed")&&h.db.writes==2&&!((TextView)h.one("catalog-rename-validation")).text.isEmpty(),"stale_visible");\n  save.performClick();need(h.db.renames==1&&h.queue.isEmpty()&&!save.isEnabled(),"failure_terminal");\n  h=fresh();save=edit(h);h.content();save.performClick();need(h.db.lastRename.terminal&&h.queue.isEmpty()&&h.db.writes==2,"detached_readonly");\n  h=fresh();save=edit(h);h.text("catalog-rename-name","Queued");save.performClick();h.content();h.drain();\n  need(h.db.lastRename.terminal&&h.db.writes==2&&h.outer.children.isEmpty(),"queued_detach_readonly");\n  h=fresh();h.one("catalog-rename-10").performClick();h.content();h.drain();need(h.db.lastRename.terminal&&h.outer.children.isEmpty(),"stale_prepare_closes");\n  h=fresh();h.db.apps.get(10L)[0]="Changed";h.one("catalog-rename-10").performClick();h.drain();\n  need(h.db.lastRename.terminal&&h.outer.find("catalog-rename-save")==null&&h.message!=null,"changed_name_preview");\n  h=fresh();h.db.apps.get(10L)[1]="example.changed";h.one("catalog-rename-10").performClick();h.drain();\n  need(h.db.lastRename.terminal&&h.outer.find("catalog-rename-save")==null&&h.message!=null,"changed_package_preview");\n  h=fresh();save=edit(h);h.text("catalog-rename-name","New");h.activity.finishing=true;save.performClick();need(h.queue.isEmpty(),"finishing");\n  h.activity.finishing=false;h.activity.destroyed=true;save.performClick();need(h.queue.isEmpty(),"destroyed");\n  h=fresh();save=edit(h);h.text("catalog-rename-name","New");save.setEnabled(false);save.performClick();need(h.queue.isEmpty(),"disabled");\n  h=fresh();save=edit(h);h.text("catalog-rename-name","New");save.attached=false;save.performClick();need(h.queue.isEmpty(),"detached_control");\n  h=fresh();save=edit(h);h.text("catalog-rename-name","New");h.db.fail=true;save.performClick();h.drain();save.performClick();\n  need(h.db.writes==2&&h.db.renames==1&&h.db.lastRename.terminal&&h.queue.isEmpty()&&!save.isEnabled(),"storage_failure");\n  h=fresh();save=edit(h);h.text("catalog-rename-name","New");h.db.failRead=true;save.performClick();h.drain();save.performClick();\n  need(h.db.writes==3&&h.db.renames==1&&h.queue.isEmpty()&&!save.isEnabled()&&h.message!=null,"refresh_failure");\n  h=fresh();save=edit(h);h.one("catalog-back").performClick();save.performClick();need(h.db.lastRename.terminal&&h.db.writes==2&&h.queue.isEmpty(),"back_closes");\n  System.out.println("RENAME_UI_PASS "+checked+" HOST_DOUBLES_NOT_ANDROID");\n }\n}\n'
    backend_labels=['prepare_readonly', 'exact_target', 'single_attempt', 'cancel', 'stale', 'stale_readonly', 'blank', 'blank_consumed', 'same_readonly', 'foreign', 'foreign_does_not_consume', 'session', 'connection', 'outer', 'rollback', 'rollback_state', 'failure_consumed', 'readback', 'readback_rollback', 'invalid_id', 'missing_id', 'prepare_outer']
    ui_labels=['render_existing', 'prepare_readonly', 'blank_visible', 'pending_once', 'exact_identity', 'old_save', 'same_readonly', 'cancel_readonly', 'stale_visible', 'failure_terminal', 'detached_readonly', 'queued_detach_readonly', 'stale_prepare_closes', 'changed_name_preview', 'changed_package_preview', 'finishing', 'destroyed', 'disabled', 'detached_control', 'storage_failure', 'refresh_failure', 'back_closes']
    backend_mutations=[('terminal=true;before=null;', ';', 'cancel'), ('if(!Arrays.equals(plan.before,noteDeletionState(db)))', 'if(false)', 'stale'), ('plan.session!=restoreSession', 'false', 'session'), ('connection!=plan.connection||!connection.isOpen()', '!connection.isOpen()', 'connection'), ('bump(db)!=next||!Arrays.equals(expected,noteDeletionState(db))', 'bump(db)!=next', 'readback'), ('if(clean.equals(plan.name))return false;', 'if(false)return false;', 'same_readonly')]
    ui_mutations=[('if(renamePlan!=null){renamePlan.close();renamePlan=null;}', 'if(renamePlan!=null){renamePlan=null;}', 'detached_readonly'), ('if(!current(p)){\n                plan.close();return;\n            }', 'if(false){\n                plan.close();return;\n            }', 'stale_prepare_closes'), ('||!item.packageName.equals(plan.packageName())', '||false', 'changed_package_preview'), ('&&control.isEnabled();', '&&true;', 'disabled')]
    parse=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{
public static void main(String[]a)throws Exception{
 JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
 try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
  JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
  CompilationUnitTree u=t.parse().iterator().next();
  for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
  SourcePositions p=Trees.instance(t).getSourcePositions();String s=Files.readString(Path.of(a[0]));
  Set<String>w=new HashSet<>(Arrays.asList("ApplicationRenamePlan","prepareApplicationRename","confirmApplicationRename","applicationRenameExpected"));
  StringBuilder out=new StringBuilder();
  for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers()){
   String n=m instanceof MethodTree?((MethodTree)m).getName().toString():m instanceof ClassTree?((ClassTree)m).getSimpleName().toString():"";
   if(w.remove(n))out.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");
  }
  if(!w.isEmpty())throw new AssertionError("missing rename members "+w);
  Files.writeString(Path.of(a[1]),out.toString());
 }
}}'''
    tree=ast.parse(inspect.getsource(catalog_ui_selftest))
    assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="files" for t in n.targets)]
    assert len(assignments)==1
    files=ast.literal_eval(assignments[0].value)
    dbkey="com/supercubegame/pockettodo/AppDatabase.java"
    files[dbkey]=files[dbkey].rstrip()[:-1]+RENAME_UI_DB_DOUBLE+"\n}"
    files["com/supercubegame/pockettodo/Test.java"]=ui_test
    files.pop("Compile.java",None)
    source=ROOT/"src/main/java/com/supercubegame/pockettodo"
    compiler='import javax.tools.*;class Compile{public static void main(String[]a){System.exit(ToolProvider.getSystemJavaCompiler().run(null,null,null,a));}}'
    receipts={}
    with tempfile.TemporaryDirectory(prefix="catalog-rename-") as tmp:
        root=Path(tmp);(root/"Extract.java").write_text(parse)
        result=subprocess.run(["java",str(root/"Extract.java"),str(source/"AppDatabase.java"),str(root/"members")],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,(result.stdout,result.stderr)
        members=(root/"members").read_text()
        def execute(code,ui):
            area=root/("ui" if ui else "backend");area.mkdir(exist_ok=True)
            units=dict(files) if ui else {"AppDatabase.java":prelude+code+"\n}\n","Test.java":backend_test}
            if ui:units["com/supercubegame/pockettodo/AppCatalog.java"]=code
            for name,value in units.items():
                path=area/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
            (area/"Compile.java").write_text(compiler)
            result=subprocess.run(["java",str(area/"Compile.java"),"-d",str(area)]+[str(area/n) for n in units],capture_output=True,text=True,timeout=30)
            assert result.returncode==0,("rename compilation",result.stdout,result.stderr)
            return subprocess.run(["java","-cp",str(area),"com.supercubegame.pockettodo.Test" if ui else "Test"],capture_output=True,text=True,timeout=30)
        for ui,code,labels,mutations in ((False,members,backend_labels,backend_mutations),(True,(source/"AppCatalog.java").read_text(),ui_labels,ui_mutations)):
            kind="UI" if ui else "BACKEND";prefix="RENAME_"+kind+"_CHECK "
            witness="RENAME_"+kind+"_VALID_WITNESS"
            assert len(labels)==22 and len(set(labels))==22
            good=execute(code,ui)
            assert good.returncode==0 and not good.stderr,(good.stdout,good.stderr)
            assert re.findall("^"+prefix+"([a-z_]+)$",good.stdout,re.M)==labels,good.stdout
            assert good.stdout.splitlines().count(witness)==1
            assert good.stdout.splitlines()[-1]=="RENAME_"+kind+"_PASS 22 "+("HOST_DOUBLES_NOT_ANDROID" if ui else "HOST_SQL_DOUBLES_NOT_ANDROID")
            print(good.stdout,flush=True)
            caught=[]
            for old,new,label in mutations:
                assert code.count(old)==1,(old,code.count(old))
                mutant=code.replace(old,new,1);assert mutant!=code
                result=execute(mutant,ui)
                assert result.returncode==1 and "AssertionError: "+label+"\n" in result.stderr,(label,result.stdout,result.stderr)
                assert result.stdout.splitlines().count(witness)==1
                assert re.findall("^"+prefix+"([a-z_]+)$",result.stdout,re.M)==labels[:labels.index(label)]
                caught.append(label);print("RENAME_MUTANT_REJECTED "+kind+" "+label,flush=True)
            receipts[kind]=dict(checks=len(labels),mutants=caught)
    assert len(receipts["BACKEND"]["mutants"])==6 and len(receipts["UI"]["mutants"])==4
    print("RENAME_HOST "+json.dumps(dict(status="PASS",receipts=receipts,
        scope="EXTRACTED_CURRENT_JAVA_AND_CURRENT_UI_WITH_HOST_DOUBLES_NOT_ANDROID_SQLITE_OR_BACKUP",
        release_ready=False),sort_keys=True),flush=True)


if __name__ == "__main__":
    {"selftest": selftest, "android": driver(), "report": report}[sys.argv[1]]()
