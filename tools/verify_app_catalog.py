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
REQUIRED = {'seed': ['backend_fixture', 'application_insert', 'duplicate_package_readonly', 'invalid_package_readonly', 'prepare_readonly', 'create_linked_once', 'duplicate_plan_readonly', 'canceled_plan_readonly', 'second_category_reuse', 'unassigned_activity', 'stale_app_readonly', 'stale_category_readonly', 'late_rollback', 'consumed_failure_readonly', 'outer_transaction_readonly', 'backend_checkpoint', 'rename_fixture', 'rename_prepare_readonly', 'rename_exact_state', 'rename_duplicate', 'rename_same_readonly', 'rename_cancel', 'rename_blank', 'rename_blank_consumed', 'rename_stale', 'rename_unrelated_change', 'rename_late_rollback', 'rename_failure_consumed', 'rename_readback_rollback', 'rename_prepare_outer', 'rename_confirm_outer', 'rename_missing', 'rename_foreign', 'rename_owner_retained', 'rename_closed_helper', 'rename_reopened_state', 'relation_prepare', 'relation_path_order', 'relation_duplicate', 'relation_tag_order', 'relation_same', 'relation_clear', 'relation_blank', 'relation_blank_consumed', 'relation_cancel', 'relation_stale', 'relation_late_rollback', 'relation_failure_consumed', 'relation_readback_rollback', 'relation_foreign', 'relation_owner_retained', 'relation_prepare_outer', 'relation_confirm_outer', 'relation_missing', 'relation_closed', 'relation_final', 'archive_prepare', 'archive_exact', 'archive_duplicate', 'archive_same', 'archive_relation_refused', 'archive_restore_exact', 'archive_cancel', 'archive_stale_same', 'archive_late_rollback', 'archive_failure_consumed', 'archive_readback_rollback', 'archive_foreign', 'archive_owner_retained', 'archive_prepare_outer', 'archive_confirm_outer', 'archive_missing', 'archive_closed', 'archive_reopened_restore', 'archive_final', 'archive_schema2_compatible'], 'deleted': ['backend_restart', 'backend_backup', 'ui_fixture', 'catalog_open_readonly', 'invalid_name_readonly', 'invalid_package_ui_readonly', 'create_application_ui', 'duplicate_package_ui_readonly', 'same_title_distinct_ids', 'cancel_picker_readonly', 'first_category_link', 'duplicate_click_readonly', 'second_category_link', 'old_picker_readonly', 'unassigned_retained', 'ui_checkpoint', 'rename_ui_prepare', 'rename_ui_blank', 'rename_ui_exact', 'rename_ui_duplicate', 'rename_ui_cancel', 'rename_ui_same', 'rename_ui_stale', 'rename_ui_detached', 'rename_ui_final', 'relation_ui_prepare', 'relation_ui_blank', 'relation_ui_path', 'relation_ui_duplicate', 'relation_ui_tags', 'relation_ui_same', 'relation_ui_cancel', 'relation_ui_clear', 'relation_ui_other_owner', 'relation_ui_other_tags', 'relation_ui_stale', 'relation_ui_detached', 'relation_ui_final', 'archive_ui_preview', 'archive_ui_cancel', 'archive_ui_exact', 'archive_ui_duplicate', 'archive_ui_readonly_history', 'archive_ui_list', 'archive_ui_active_filter', 'archive_ui_restore_cancel', 'archive_ui_restore', 'archive_ui_stale', 'archive_ui_detached', 'archive_ui_final'], 'undone': ['ui_restart', 'ui_backup', 'archive_ui_restart_history']}
EXPECTED = {'seed': ['backend_fixture', 'application_insert', 'duplicate_package_readonly', 'invalid_package_readonly', 'prepare_readonly', 'create_linked_once', 'duplicate_plan_readonly', 'canceled_plan_readonly', 'second_category_reuse', 'unassigned_activity', 'stale_app_readonly', 'stale_category_readonly', 'late_rollback', 'consumed_failure_readonly', 'outer_transaction_readonly', 'backend_checkpoint', 'rename_fixture', 'rename_prepare_readonly', 'rename_exact_state', 'rename_duplicate', 'rename_same_readonly', 'rename_cancel', 'rename_blank', 'rename_blank_consumed', 'rename_stale', 'rename_unrelated_change', 'rename_late_rollback', 'rename_failure_consumed', 'rename_readback_rollback', 'rename_prepare_outer', 'rename_confirm_outer', 'rename_missing', 'rename_foreign', 'rename_owner_retained', 'rename_closed_helper', 'rename_reopened_state', 'relation_prepare', 'relation_path_order', 'relation_duplicate', 'relation_tag_order', 'relation_same', 'relation_clear', 'relation_blank', 'relation_blank_consumed', 'relation_cancel', 'relation_stale', 'relation_late_rollback', 'relation_failure_consumed', 'relation_readback_rollback', 'relation_foreign', 'relation_owner_retained', 'relation_prepare_outer', 'relation_confirm_outer', 'relation_missing', 'relation_closed', 'relation_final', 'archive_prepare', 'archive_exact', 'archive_duplicate', 'archive_same', 'archive_relation_refused', 'archive_restore_exact', 'archive_cancel', 'archive_stale_same', 'archive_late_rollback', 'archive_failure_consumed', 'archive_readback_rollback', 'archive_foreign', 'archive_owner_retained', 'archive_prepare_outer', 'archive_confirm_outer', 'archive_missing', 'archive_closed', 'archive_reopened_restore', 'archive_final', 'archive_schema2_compatible'], 'deleted': ['backend_restart', 'backend_backup', 'ui_fixture', 'catalog_open_readonly', 'invalid_name_readonly', 'invalid_package_ui_readonly', 'create_application_ui', 'duplicate_package_ui_readonly', 'same_title_distinct_ids', 'cancel_picker_readonly', 'first_category_link', 'duplicate_click_readonly', 'second_category_link', 'old_picker_readonly', 'unassigned_retained', 'ui_checkpoint', 'rename_ui_prepare', 'rename_ui_blank', 'rename_ui_exact', 'rename_ui_duplicate', 'rename_ui_cancel', 'rename_ui_same', 'rename_ui_stale', 'rename_ui_detached', 'rename_ui_final', 'relation_ui_prepare', 'relation_ui_blank', 'relation_ui_path', 'relation_ui_duplicate', 'relation_ui_tags', 'relation_ui_same', 'relation_ui_cancel', 'relation_ui_clear', 'relation_ui_other_owner', 'relation_ui_other_tags', 'relation_ui_stale', 'relation_ui_detached', 'relation_ui_final', 'archive_ui_preview', 'archive_ui_cancel', 'archive_ui_exact', 'archive_ui_duplicate', 'archive_ui_readonly_history', 'archive_ui_list', 'archive_ui_active_filter', 'archive_ui_restore_cancel', 'archive_ui_restore', 'archive_ui_stale', 'archive_ui_detached', 'archive_ui_final'], 'undone': ['ui_restart', 'ui_backup', 'archive_ui_restart_history']}
SHARED_SHA256 = "9b1b435b21b630e1230f1e112a794962825665982ceabdbb41cc68583ce3d70d"
# Reuse unchanged transport/receipt infrastructure, never the category cases.
# Pin the whole dependency: a future edit must explicitly review this adapter.
assert hashlib.sha256(Path(shared.__file__).read_bytes()).hexdigest() == SHARED_SHA256, "catalog shared gate changed"
for marker in (" static Map<String,List<List<String>>> expected(", " void save(", " void seed(", " @Override public void onCreate"):
    assert shared.JAVA.count(marker) == 1, "ambiguous Java scaffold boundary"
CASES = r'''
 Object archivePlan(AppDatabase h,long id,boolean target)throws Exception{
  return invoke(h,"prepareActivityArchive",new Class<?>[]{long.class,boolean.class},id,target);
 }
 boolean archiveConfirm(AppDatabase h,Object p)throws Exception{
  return (Boolean)invoke(h,"confirmActivityArchive",new Class<?>[]{p.getClass()},p);
 }
 static Map<String,List<List<String>>> archiveExpected(Map<String,List<List<String>>> before,long owner,boolean value){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();for(List<String> r:e.getValue())rows.add(new ArrayList<>(r));out.put(e.getKey(),rows);
  }
  List<List<String>> rows=out.get("activities");int col=rows.get(0).indexOf("archived"),matched=0;
  need(col==5,"archive independent oracle columns");
  for(int i=1;i<rows.size();i++)if(rows.get(i).get(1).equals("1:"+owner)){rows.get(i).set(col,value?"1:1":"1:0");matched++;}
  need(matched==1,"archive one stable identity");
  List<List<String>> rev=out.get("revision");int v=rev.get(0).indexOf("value");
  rev.get(1).set(v,"1:"+Math.incrementExact(Long.parseLong(rev.get(1).get(v).substring(2))));return out;
 }
 void archiveBackend(AppDatabase h)throws Exception{
  h.defineField("archive-field","Archive field","TEXT",Collections.emptyList());
  h.putField(5,"archive-field",Arrays.asList("Preserved field"));
  h.createFieldNote("archive-note",5,"archive-field","Preserved linked note");
  h.saveNote("archive-note",Arrays.asList(com.supercubegame.pockettodo.NoteDocument.Block.text("archive-body","Preserved full history",true)));
  h.putMark(new com.supercubegame.pockettodo.CalendarRules.Mark(5,java.time.LocalDate.of(2026,10,8),com.supercubegame.pockettodo.CalendarRules.Status.DONE,"Preserved mark",java.time.Instant.parse("2026-10-08T00:00:00Z")));
  Map<String,List<List<String>>> before=state(h);Object p=archivePlan(h,5,true);
  pass(state(h).equals(before)&&((Number)invoke(p,"activityId",new Class<?>[]{})).longValue()==5
      &&!(Boolean)invoke(p,"wasArchived",new Class<?>[]{})&&(Boolean)invoke(p,"willArchive",new Class<?>[]{}),"archive_prepare");
  pass(archiveConfirm(h,p)&&state(h).equals(archiveExpected(before,5,true)),"archive_exact");
  Object used=p;readonly(h,IllegalStateException.class,()->archiveConfirm(h,used),"archive_duplicate");
  before=state(h);pass(!archiveConfirm(h,archivePlan(h,5,true))&&state(h).equals(before),"archive_same");
  readonly(h,IllegalArgumentException.class,()->relationPlan(h,5,false),"archive_relation_refused");
  before=state(h);pass(archiveConfirm(h,archivePlan(h,5,false))&&state(h).equals(archiveExpected(before,5,false)),"archive_restore_exact");
  Object canceled=archivePlan(h,5,true);close(canceled);readonly(h,IllegalStateException.class,()->archiveConfirm(h,canceled),"archive_cancel");
  Object stale=archivePlan(h,5,false);h.getWritableDatabase().execSQL("UPDATE applications SET name='Archive intervening' WHERE id=11");
  readonly(h,IllegalStateException.class,()->archiveConfirm(h,stale),"archive_stale_same");
  Object late=archivePlan(h,5,true);before=state(h);
  h.getWritableDatabase().execSQL("CREATE TRIGGER archive_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'archive_late_fault'); END");
  Throwable error=null;try{archiveConfirm(h,late);}catch(Throwable t){error=t;}
  boolean found=false;for(Throwable t=error;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("archive_late_fault"))found=true;
  pass(found&&state(h).equals(before),"archive_late_rollback");h.getWritableDatabase().execSQL("DROP TRIGGER archive_fault");
  readonly(h,IllegalStateException.class,()->archiveConfirm(h,late),"archive_failure_consumed");
  Object damage=archivePlan(h,5,true);before=state(h);
  h.getWritableDatabase().execSQL("CREATE TRIGGER archive_damage AFTER UPDATE OF archived ON activities WHEN NEW.id=5 BEGIN UPDATE notes SET title='Damaged' WHERE id='archive-note'; END");
  error=null;try{archiveConfirm(h,damage);}catch(Throwable t){error=t;}
  found=false;for(Throwable t=error;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("活动归档回读不一致"))found=true;
  pass(found&&state(h).equals(before),"archive_readback_rollback");h.getWritableDatabase().execSQL("DROP TRIGGER archive_damage");
  Object foreignPlan=archivePlan(h,5,true);
  try(AppDatabase foreign=AppDatabase.openSchema3(getTargetContext(),name())){
   readonly(h,IllegalArgumentException.class,()->archiveConfirm(foreign,foreignPlan),"archive_foreign");
  }
  before=state(h);pass(archiveConfirm(h,foreignPlan)&&state(h).equals(archiveExpected(before,5,true)),"archive_owner_retained");
  Object outer=archivePlan(h,5,false);h.getWritableDatabase().beginTransaction();
  try{
   readonly(h,IllegalStateException.class,()->archivePlan(h,5,false),"archive_prepare_outer");
   readonly(h,IllegalStateException.class,()->archiveConfirm(h,outer),"archive_confirm_outer");
  }finally{h.getWritableDatabase().endTransaction();}
  readonly(h,IllegalArgumentException.class,()->archivePlan(h,999,true),"archive_missing");
  Object closed=archivePlan(h,5,false);h.close();
  readonly(h,IllegalStateException.class,()->archiveConfirm(h,closed),"archive_closed");
  before=state(h);pass(archiveConfirm(h,archivePlan(h,5,false))&&state(h).equals(archiveExpected(before,5,false)),"archive_reopened_restore");
  before=state(h);pass(archiveConfirm(h,archivePlan(h,5,true))&&state(h).equals(archiveExpected(before,5,true)),"archive_final");
  try(AppDatabase legacy=new AppDatabase(getTargetContext(),"archive-schema2-"+nonce+".db")){
   legacy.addCategory(1,"Legacy");legacy.addActivity(1,1,0,"Legacy");before=state(legacy);
   need(archiveConfirm(legacy,archivePlan(legacy,1,true)),"schema2 archive operation");
   byte[] wire=legacy.exportState();
   pass(state(legacy).equals(archiveExpected(before,1,true))&&wire.length>0&&legacy.getReadableDatabase().getVersion()==2,"archive_schema2_compatible");
  }
 }
 boolean archiveAbsent(String key)throws Exception{
  boolean[] absent={false};ui(()->{List<View> found=new ArrayList<>();find(root(),key,true,found);absent[0]=found.isEmpty();});return absent[0];
 }
 void archiveReadOnlyViews(View view){
  need(!(view instanceof EditText),"archive history has no editor");
  if(view instanceof Button){
   String key=String.valueOf(view.getContentDescription());
   need(key.equals("archive-detail-back")||key.equals("activity-restore-1"),"archive history has no business write button "+key);
  }else if(view instanceof TextView)need(!view.hasOnClickListeners(),"archive history text is read-only");
  if(view instanceof ViewGroup){ViewGroup g=(ViewGroup)view;for(int i=0;i<g.getChildCount();i++)archiveReadOnlyViews(g.getChildAt(i));}
 }
 void archiveHistoryCheck()throws Exception{
  ui(()->{
   View history=one("archive-history-1",true);
   need(history instanceof ViewGroup,"archive historical rows");
   archiveReadOnlyViews((View)history.getParent().getParent());
   for(String expected:Arrays.asList("History full text","History field value","History mark","history-batch","History path")){
    List<View> found=new ArrayList<>();archiveContains(history,expected,found);need(!found.isEmpty(),"archive retained history visible "+expected);
   }
  });
 }
 void archiveContains(View view,String text,List<View> found){
  if(view instanceof TextView&&((TextView)view).getText().toString().contains(text))found.add(view);
  if(view instanceof ViewGroup){ViewGroup g=(ViewGroup)view;for(int i=0;i<g.getChildCount();i++)archiveContains(g.getChildAt(i),text,found);}
 }
 void archiveUI(AppDatabase h)throws Exception{
  h.savePath(1,Arrays.asList("History path"));h.saveTags(1,Arrays.asList("History tag"));
  h.defineField("history-field","History field","TEXT",Collections.emptyList());h.putField(1,"history-field",Arrays.asList("History field value"));
  h.createFieldNote("history-note",1,"history-field","History note");
  h.saveNote("history-note",Arrays.asList(com.supercubegame.pockettodo.NoteDocument.Block.text("history-body","History full text",true)));
  h.putMark(new com.supercubegame.pockettodo.CalendarRules.Mark(1,java.time.LocalDate.of(2026,10,8),com.supercubegame.pockettodo.CalendarRules.Status.DONE,"History mark",java.time.Instant.parse("2026-10-08T00:00:00Z")));
  h.recordBatch("history-batch",Arrays.asList(new com.supercubegame.pockettodo.Ledger.Entry("history-entry",1,java.time.LocalDate.of(2026,10,8),com.supercubegame.pockettodo.Ledger.Kind.EXPENSE,123,"History memo")));
  click("activity-1",true);Map<String,List<List<String>>> before=state(h);
  click("activity-archive-1",true);final View[] old={null};boolean[] okay={false};
  ui(()->{old[0]=one("archive-confirm",true);okay[0]=((TextView)one("archive-identity",true)).getText().toString().contains("#1");});
  pass(okay[0]&&state(h).equals(before),"archive_ui_preview");
  click("archive-cancel",true);ui(()->old[0].performClick());ready();pass(state(h).equals(before),"archive_ui_cancel");
  click("activity-archive-1",true);
  ui(()->{old[0]=one("archive-confirm",true);need(old[0].performClick(),"archive explicit click");old[0].performClick();});ready();
  pass(state(h).equals(archiveExpected(before,1,true)),"archive_ui_exact");
  before=state(h);ui(()->old[0].performClick());ready();pass(state(h).equals(before),"archive_ui_duplicate");
  archiveHistoryCheck();pass(state(h).equals(before),"archive_ui_readonly_history");
  click("archive-detail-back",true);pass(!archiveAbsent("archived-activity-1"),"archive_ui_list");
  click("archive-list-back",true);pass(archiveAbsent("activity-1")&&!archiveAbsent("activity-2")&&!archiveAbsent("activity-3")&&state(h).equals(before),"archive_ui_active_filter");
  click("archived-activities",true);click("archived-activity-1",true);click("activity-restore-1",true);
  click("archive-cancel",true);pass(state(h).equals(before),"archive_ui_restore_cancel");
  click("activity-restore-1",true);click("archive-confirm",true);
  pass(state(h).equals(archiveExpected(before,1,false))&&!archiveAbsent("activity-path-edit-1"),"archive_ui_restore");
  click("activity-archive-1",true);h.getWritableDatabase().execSQL("UPDATE applications SET name='Archive stale UI' WHERE id=2");before=state(h);
  click("archive-confirm",true);
  ui(()->okay[0]=!one("archive-confirm",true).isEnabled()&&((TextView)one("archive-validation",true)).getText().length()>0);
  pass(okay[0]&&state(h).equals(before),"archive_ui_stale");click("archive-cancel",true);
  click("activity-archive-1",true);ui(()->old[0]=one("archive-confirm",true));click("今天",false);
  ui(()->old[0].performClick());ready();pass(state(h).equals(before),"archive_ui_detached");
  click("活动",false);click("activity-archive-1",true);click("archive-confirm",true);
  pass(state(h).equals(archiveExpected(before,1,true)),"archive_ui_final");
  click("archive-detail-back",true);click("archive-list-back",true);
 }
 void archiveRestartUI()throws Exception{
  AppDatabase h=db();Map<String,List<List<String>>> before=state(h);
  need(archiveAbsent("activity-1"),"restart active filter");
  click("archived-activities",true);click("archived-activity-1",true);archiveHistoryCheck();
  pass(state(h).equals(before),"archive_ui_restart_history");
 }
 // Backup wire transports declared columns, not hidden paths/tags rowids.
 // Keep full physical equality everywhere else, including in-place writes/rollback.
 static Map<String,List<List<String>>> backupProjection(Map<String,List<List<String>>> input){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> entry:input.entrySet()){
   String table=entry.getKey();List<List<String>> rows=new ArrayList<>();
   boolean relation=table.equals("paths")||table.equals("tags");
   List<List<String>> original=entry.getValue();
   if(relation)need(!original.isEmpty()&&original.get(0).equals(Arrays.asList("rowid","activity_id","position","text")),"backup relation columns");
   long previous=Long.MIN_VALUE;
   for(int i=0;i<original.size();i++){
    List<String> row=original.get(i);
    if(relation){
     need(row.size()==4,"backup relation width");
     if(i>0){
      need(row.get(0).startsWith("1:"),"backup rowid type");
      long current=Long.parseLong(row.get(0).substring(2));
      need(current>previous,"backup rowid order");previous=current;
     }
     rows.add(new ArrayList<>(row.subList(1,row.size())));
    }else rows.add(new ArrayList<>(row));
   }
   out.put(table,rows);
  }
  return out;
 }
 static boolean backupEqual(Map<String,List<List<String>>> before,Map<String,List<List<String>>> after){
  return backupProjection(before).equals(backupProjection(after));
 }
 void backup(AppDatabase source,String suffix)throws Exception{
  Map<String,List<List<String>>> before=state(source);
  byte[] wire=source.exportState();
  Path media=folder.resolve("media-"+suffix);MediaRepository repo=new MediaRepository(media,64L*1024*1024);
  Path zip=folder.resolve(suffix+".zip");source.exportBackup(zip,repo);
  try(AppDatabase target=AppDatabase.openSchema3(getTargetContext(),"restore-catalog-"+nonce+"-"+suffix+".db")){
   target.restoreBackup(zip,folder.resolve("stage-"+suffix),64L*1024*1024,repo);
   Map<String,List<List<String>>> after=state(target);
   boolean logical=backupEqual(before,after);
   if(logical){
    for(String table:Arrays.asList("paths","tags")){
     List<List<String>> left=before.get(table),right=after.get(table);
     need(left!=null&&right!=null,"backup relation tables");
     for(int i=1;i<left.size();i++)if(!left.get(i).get(0).equals(right.get(i).get(0)))
      System.out.println("BACKUP_ROWID_ONLY "+suffix+" "+table+" row="+i+" "+left.get(i).get(0)+" -> "+right.get(i).get(0));
    }
   }else{
    for(String table:before.keySet())if(!before.get(table).equals(after.get(table)))
     System.out.println("BACKUP_NONMATCHING_TABLE "+suffix+" "+table);
   }
   need(state(source).equals(before),"backup source remains physically unchanged");
   need(Arrays.equals(wire,target.exportState()),"backup exact wire readback");
   pass(logical,suffix.equals("backend")?"backend_backup":"ui_backup");
  }
 }
 void relationGeometry()throws Exception{
  final ScrollView[] scroll={null};
  ui(()->{
   View v=one("activity-details-scroll",true);need(v instanceof ScrollView,"detail scroll identity");
   scroll[0]=(ScrollView)v;scroll[0].fullScroll(View.FOCUS_DOWN);
  });
  waitForIdleSync();
  ui(()->{
   android.graphics.Rect viewport=new android.graphics.Rect();
   need(scroll[0].getGlobalVisibleRect(viewport)&&viewport.height()>0,"detail viewport nonempty");
   for(String label:Arrays.asList("标记完成","跳过今天")){
    View control=one(label,false);android.graphics.Rect rect=new android.graphics.Rect();
    need(control.isShown()&&control.isEnabled()&&control.getGlobalVisibleRect(rect)
      &&rect.height()==control.getHeight()&&rect.width()==control.getWidth()
      &&rect.height()>=Math.round(48*activity.getResources().getDisplayMetrics().density),"checkin fully visible "+label);
    need(!(control.getParent() instanceof ScrollView),"checkin not scroll child");
    need(rect.bottom<=viewport.top,"checkin pinned above scrolling details");
   }
   View stamp=one("activity-today-status",true);android.graphics.Rect rect=new android.graphics.Rect();
   need(stamp.getGlobalVisibleRect(rect)&&rect.height()==stamp.getHeight()&&rect.bottom<=viewport.top,"status fully visible above scroll");
   System.out.println("DETAIL_GEOMETRY viewport="+viewport+" status="+rect+" size="+root().getWidth()+"x"+root().getHeight());
  });
 }
 Object relationPlan(AppDatabase h,long id,boolean tags)throws Exception{
  return invoke(h,"prepareActivityStrings",new Class<?>[]{long.class,boolean.class},id,tags);
 }
 boolean relationConfirm(AppDatabase h,Object p,List<String> input)throws Exception{
  return (Boolean)invoke(h,"confirmActivityStrings",new Class<?>[]{p.getClass(),List.class},p,input);
 }
 static Map<String,List<List<String>>> relationExpected(Map<String,List<List<String>>> before,String table,long owner,List<String> values){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();for(List<String> r:e.getValue())rows.add(new ArrayList<>(r));out.put(e.getKey(),rows);
  }
  List<List<String>> rows=out.get(table);need(rows.get(0).equals(Arrays.asList("rowid","activity_id","position","text")),"relation oracle columns");
  for(int i=rows.size()-1;i>0;i--)if(rows.get(i).get(1).equals("1:"+owner))rows.remove(i);
  long rowid=rows.size()==1?0:Long.parseLong(rows.get(rows.size()-1).get(0).substring(2));
  for(int i=0;i<values.size();i++)rows.add(Arrays.asList("1:"+Math.incrementExact(rowid+i),"1:"+owner,"1:"+i,"3:"+values.get(i)));
  List<List<String>> rev=out.get("revision");int v=rev.get(0).indexOf("value");
  rev.get(1).set(v,"1:"+Math.incrementExact(Long.parseLong(rev.get(1).get(v).substring(2))));return out;
 }
 void relationsBackend(AppDatabase h)throws Exception{
  Map<String,List<List<String>>> before=state(h);Object p=relationPlan(h,5,false);
  pass(state(h).equals(before),"relation_prepare");
  pass(relationConfirm(h,p,Arrays.asList(" A ","B","A"))&&state(h).equals(relationExpected(before,"paths",5,Arrays.asList("A","B","A"))),"relation_path_order");
  Object used=p;readonly(h,IllegalStateException.class,()->relationConfirm(h,used,Arrays.asList("Again")),"relation_duplicate");
  before=state(h);p=relationPlan(h,6,true);
  pass(relationConfirm(h,p,Arrays.asList(" z ","a","z"))&&state(h).equals(relationExpected(before,"tags",6,Arrays.asList("z","a"))),"relation_tag_order");
  before=state(h);p=relationPlan(h,6,true);
  pass(!relationConfirm(h,p,Arrays.asList("z","a","z"))&&state(h).equals(before),"relation_same");
  before=state(h);p=relationPlan(h,5,false);
  pass(relationConfirm(h,p,Collections.emptyList())&&state(h).equals(relationExpected(before,"paths",5,Collections.emptyList())),"relation_clear");
  Object blank=relationPlan(h,5,false);
  readonly(h,IllegalArgumentException.class,()->relationConfirm(h,blank,Arrays.asList("A"," ")),"relation_blank");
  readonly(h,IllegalStateException.class,()->relationConfirm(h,blank,Arrays.asList("A")),"relation_blank_consumed");
  Object canceled=relationPlan(h,5,false);close(canceled);
  readonly(h,IllegalStateException.class,()->relationConfirm(h,canceled,Arrays.asList("A")),"relation_cancel");
  Object stale=relationPlan(h,5,false);h.savePath(6,Arrays.asList("Other activity"));
  readonly(h,IllegalStateException.class,()->relationConfirm(h,stale,Arrays.asList("Overwrite")),"relation_stale");
  Object late=relationPlan(h,5,false);before=state(h);
  h.getWritableDatabase().execSQL("CREATE TRIGGER relation_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'relation_late_fault'); END");
  Throwable error=null;try{relationConfirm(h,late,Arrays.asList("Bad"));}catch(Throwable t){error=t;}
  boolean found=false;for(Throwable t=error;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("relation_late_fault"))found=true;
  pass(found&&state(h).equals(before),"relation_late_rollback");h.getWritableDatabase().execSQL("DROP TRIGGER relation_fault");
  readonly(h,IllegalStateException.class,()->relationConfirm(h,late,Arrays.asList("Bad")),"relation_failure_consumed");
  Object corrupt=relationPlan(h,5,false);before=state(h);
  h.getWritableDatabase().execSQL("CREATE TRIGGER relation_damage AFTER INSERT ON paths WHEN NEW.activity_id=5 BEGIN UPDATE applications SET name='Damaged' WHERE id=10; END");
  error=null;try{relationConfirm(h,corrupt,Arrays.asList("Bad"));}catch(Throwable t){error=t;}
  found=false;for(Throwable t=error;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("路径标签回读不一致"))found=true;
  pass(found&&state(h).equals(before),"relation_readback_rollback");h.getWritableDatabase().execSQL("DROP TRIGGER relation_damage");
  Object foreignPlan=relationPlan(h,5,false);
  try(AppDatabase foreign=AppDatabase.openSchema3(getTargetContext(),name())){
   readonly(h,IllegalArgumentException.class,()->relationConfirm(foreign,foreignPlan,Arrays.asList("Bad")),"relation_foreign");
  }
  before=state(h);pass(relationConfirm(h,foreignPlan,Arrays.asList("Final path"))&&state(h).equals(relationExpected(before,"paths",5,Arrays.asList("Final path"))),"relation_owner_retained");
  Object outer=relationPlan(h,5,true);h.getWritableDatabase().beginTransaction();
  try{
   readonly(h,IllegalStateException.class,()->relationPlan(h,5,false),"relation_prepare_outer");
   readonly(h,IllegalStateException.class,()->relationConfirm(h,outer,Arrays.asList("Bad")),"relation_confirm_outer");
  }finally{h.getWritableDatabase().endTransaction();}
  readonly(h,IllegalArgumentException.class,()->relationPlan(h,999,false),"relation_missing");
  Object closed=relationPlan(h,5,false);h.close();
  readonly(h,IllegalStateException.class,()->relationConfirm(h,closed,Arrays.asList("Bad")),"relation_closed");
  before=state(h);p=relationPlan(h,5,true);
  pass(relationConfirm(h,p,Arrays.asList("Final tag"))&&state(h).equals(relationExpected(before,"tags",5,Arrays.asList("Final tag"))),"relation_final");
 }
 void relationText(String value)throws Exception{
  ui(()->{List<View> out=new ArrayList<>();find(root(),"活动路径",true,out);find(root(),"活动标签",true,out);
   need(out.size()==1&&out.get(0) instanceof EditText,"one relation input");((EditText)out.get(0)).setText(value);
   need(value.contentEquals(((EditText)out.get(0)).getText()),"exact relation input");});
 }
 void relationsUI(AppDatabase h)throws Exception{
  click("activity-2",true);relationGeometry();Map<String,List<List<String>>> before=state(h);
  click("activity-path-edit-2",true);
  boolean[] okay={false};ui(()->okay[0]=((TextView)one("relation-identity",true)).getText().toString().contains("#2"));
  pass(okay[0]&&state(h).equals(before),"relation_ui_prepare");
  relationText("A\n \nB");click("relation-save",true);
  ui(()->okay[0]=((TextView)one("relation-validation",true)).getText().length()>0);
  pass(okay[0]&&state(h).equals(before),"relation_ui_blank");
  relationText(" A\nB\nA");final View[] old={null};
  ui(()->{old[0]=one("relation-save",true);need(old[0].performClick(),"relation first click");old[0].performClick();});ready();
  pass(state(h).equals(relationExpected(before,"paths",2,Arrays.asList("A","B","A"))),"relation_ui_path");
  before=state(h);ui(()->old[0].performClick());ready();pass(state(h).equals(before),"relation_ui_duplicate");
  click("activity-tags-edit-2",true);relationText(" z\na\nz");click("relation-save",true);
  pass(state(h).equals(relationExpected(before,"tags",2,Arrays.asList("z","a"))),"relation_ui_tags");relationGeometry();
  before=state(h);click("activity-tags-edit-2",true);click("relation-save",true);pass(state(h).equals(before),"relation_ui_same");
  click("activity-path-edit-2",true);relationText("Cancel");ui(()->old[0]=one("relation-save",true));click("relation-cancel",true);
  ui(()->old[0].performClick());ready();pass(state(h).equals(before),"relation_ui_cancel");
  click("activity-path-edit-2",true);relationText("");click("relation-save",true);
  pass(state(h).equals(relationExpected(before,"paths",2,Collections.emptyList())),"relation_ui_clear");
  before=state(h);click("返回分类",false);click("activity-3",true);click("activity-path-edit-3",true);relationText("Other\nPath");click("relation-save",true);
  pass(state(h).equals(relationExpected(before,"paths",3,Arrays.asList("Other","Path"))),"relation_ui_other_owner");
  before=state(h);click("activity-tags-edit-3",true);relationText("Independent");click("relation-save",true);
  pass(state(h).equals(relationExpected(before,"tags",3,Arrays.asList("Independent"))),"relation_ui_other_tags");
  click("activity-tags-edit-3",true);h.saveTags(2,Arrays.asList("External"));before=state(h);relationText("Overwrite");click("relation-save",true);
  ui(()->okay[0]=!one("relation-save",true).isEnabled()&&((TextView)one("relation-validation",true)).getText().length()>0);
  pass(okay[0]&&state(h).equals(before),"relation_ui_stale");click("relation-cancel",true);
  click("activity-tags-edit-3",true);ui(()->old[0]=one("relation-save",true));click("今天",false);
  ui(()->old[0].performClick());ready();pass(state(h).equals(before),"relation_ui_detached");
  click("活动",false);click("activity-tags-edit-3",true);relationText("Final");
  click("relation-save",true);pass(state(h).equals(relationExpected(before,"tags",3,Arrays.asList("Final"))),"relation_ui_final");
  click("返回分类",false);
 }
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
  relationsBackend(h);archiveBackend(h);
  save("backend-rename-state",state(h).toString());
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
  click("catalog-back",true);relationsUI(h);archiveUI(h);save("ui-rename-state",state(h).toString());save("ui-rename-media",media().toString());
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
   pass(state(h).toString().equals(read("backend-rename-state")),"backend_restart");backup(h,"backend");
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
  pass(state(db()).toString().equals(read("ui-rename-state"))&&media().toString().equals(read("ui-rename-media")),"ui_restart");backup(db(),"ui");archiveRestartUI();
 }
'''
JAVA = (shared.JAVA[:shared.JAVA.index(" static Map<String,List<List<String>>> expected(")] + CASES
    + shared.JAVA[shared.JAVA.index(" void save("):shared.JAVA.index(" void seed(")].replace("category-", "catalog-").replace("&&target.categoryIds().equals(source.categoryIds())", "").replace(" void backup(", " void historicalBackup(")
    + shared.JAVA[shared.JAVA.index(" @Override public void onCreate"):].replace('"category-"+nonce', '"catalog-"+nonce'))
def bind_infrastructure():
    for name in ("parser", "validate", "fixture", "driver", "report", "report_selftest"):
        s=inspect.getsource(getattr(shared,name))
        s=s.replace("INJECTED_TOUCH_WITH_DETACHED_VIEW_REPLAY","INSTALLED_VIEW_CALLBACKS_NOT_PHYSICAL_TOUCH")
        s=s.replace("category","catalog").replace("Category","Catalog").replace("CATEGORY","CATALOG")
        if name=="fixture":
            assert s.count("checks=40")==1
            s=s.replace("checks=40","checks=129")
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

def snapshot_selftest(source=None):
    """Actual generated Java save/read and AST-derived checkpoint calls.
    Host filesystem checks, not Android lifecycle or database acceptance."""
    if source is None:
        source = JAVA
    extract = r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{
 public static void main(String[]a)throws Exception{
  JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
  try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
   JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
   CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
   String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();
   Map<String,MethodTree> methods=new HashMap<>();StringBuilder helpers=new StringBuilder();
   for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers())if(m instanceof MethodTree){
    MethodTree mt=(MethodTree)m;String n=mt.getName().toString();if(methods.put(n,mt)!=null)throw new AssertionError("duplicate method");
    if(n.equals("save")||n.equals("read"))helpers.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");
   }
   if(!methods.keySet().containsAll(Arrays.asList("save","read","seed","renameBackend","deleted","renameUI","undone")))throw new AssertionError("missing checkpoint method");
   Files.writeString(Path.of(a[1]),helpers);
   List<String> events=new ArrayList<>();
   for(String name:Arrays.asList("seed","renameBackend","deleted","renameUI","undone")){
    new TreeScanner<Void,Void>(){
     @Override public Void visitMethodInvocation(MethodInvocationTree call,Void unused){
      String n=call.getMethodSelect().toString();
      if(n.equals("save")||n.equals("read")){
       Tree key=call.getArguments().get(0);if(!(key instanceof LiteralTree)||!(((LiteralTree)key).getValue() instanceof String))throw new AssertionError("literal checkpoint key");
       events.add(name+"\t"+n+"\t"+((LiteralTree)key).getValue());
      }else if(n.equals("renameBackend")||n.equals("renameUI"))events.add(name+"\tcall\t"+n);
      return super.visitMethodInvocation(call,unused);
     }
    }.scan(methods.get(name).getBody(),null);
   }
   Files.write(Path.of(a[2]),events);
  }
 }
}'''
    harness = r'''import java.nio.file.*;import java.util.*;
class Checkpoint{
 Path folder;
 __HELPERS__
 static void need(boolean b,String s){if(!b)throw new AssertionError(s);}
 public static void main(String[]a)throws Exception{
  Checkpoint h=new Checkpoint();h.folder=Files.createTempDirectory("catalog-checkpoint-");
  try{
   h.save("witness","unchanged");need(h.read("witness").equals("unchanged"),"valid_save_read");
   System.out.println("SNAPSHOT_VALID_WITNESS");
   Map<String,String> original=new HashMap<>();int writes=0,reads=0,calls=0;
   for(String event:Files.readAllLines(Path.of(a[0]))){
    String[] v=event.split("\t",-1);String method=v[0],op=v[1],key=v[2];
    if(op.equals("call")){
     need((method.equals("seed")&&key.equals("renameBackend"))||(method.equals("deleted")&&key.equals("renameUI")),"rename_phase_binding");calls++;continue;
    }
    if(op.equals("save")){
     String value=method+":"+key;h.save(key,value);original.put(key,value);writes++;
    }else{
     String wanted=method.equals("deleted")?"renameBackend:backend-rename-state":
         key.endsWith("media")?"renameUI:ui-rename-media":"renameUI:ui-rename-state";
     need(h.read(key).equals(wanted),"restart_reads_renamed_checkpoint");reads++;
    }
   }
   need(writes==6&&reads==3&&calls==2&&original.size()==6,"exact_checkpoint_population");
   for(Map.Entry<String,String> e:original.entrySet())need(h.read(e.getKey()).equals(e.getValue()),"original_snapshots_preserved");
   boolean refused=false;try{h.save("witness","overwrite");}catch(FileAlreadyExistsException e){refused=true;}
   need(refused&&h.read("witness").equals("unchanged"),"duplicate_snapshot_rejected");
   System.out.println("SNAPSHOT_PASS writes=6 reads=3 originals=6 duplicate_rejected=true");
  }finally{
   try(java.util.stream.Stream<Path> ps=Files.walk(h.folder)){for(Path p:(Iterable<Path>)ps.sorted(Comparator.reverseOrder())::iterator)Files.delete(p);}
  }
 }
}'''
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp)
        (p/"Extract.java").write_text(extract)
        def execute(text):
            (p/"TodoInstrumentation.java").write_text(text)
            parsed = subprocess.run(["java", str(p/"Extract.java"), str(p/"TodoInstrumentation.java"),
                str(p/"helpers"), str(p/"events")], capture_output=True, text=True, timeout=30)
            assert parsed.returncode == 0, (parsed.stdout, parsed.stderr)
            (p/"Checkpoint.java").write_text(harness.replace("__HELPERS__", (p/"helpers").read_text()))
            return subprocess.run(["java", str(p/"Checkpoint.java"), str(p/"events")],
                                  capture_output=True, text=True, timeout=30)
        good = execute(source)
        assert good.returncode == 0, (good.stdout, good.stderr)
        print(good.stdout.strip())
        mutations = (
            ('save("backend-rename-state"', 'save("backend-state"', "FileAlreadyExistsException"),
            ('save("ui-rename-state"', 'save("ui-state"', "FileAlreadyExistsException"),
            ('save("ui-rename-media"', 'save("ui-media"', "FileAlreadyExistsException"),
            ('read("backend-rename-state")', 'read("backend-state")', "restart_reads_renamed_checkpoint"),
            ('read("ui-rename-state")', 'read("ui-state")', "restart_reads_renamed_checkpoint"),
            ('read("ui-rename-media")', 'read("ui-media")', "restart_reads_renamed_checkpoint"),
            ("StandardOpenOption.CREATE_NEW", "StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING", "duplicate_snapshot_rejected"),
        )
        for old, new, label in mutations:
            assert source.count(old) == 1, ("checkpoint mutation anchor", old)
            result = execute(source.replace(old, new))
            assert result.returncode != 0 and "SNAPSHOT_VALID_WITNESS" in result.stdout and label in result.stderr, (label,result.stdout,result.stderr)
        print("CATALOG_SNAPSHOT_HOST positive=1 witnessed_mutants=7 PASS; actual save/read and AST-derived calls, not Android")


def selftest():
    archive_host_selftest()
    repair_selftest()
    relation_host_selftest()
    snapshot_selftest()
    rename_host_selftest()
    catalog_ui_selftest()
    assert REQUIRED == EXPECTED
    assert [len(EXPECTED[p]) for p in ("seed", "deleted", "undone")] == [76,50,3]
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


def relation_host_selftest():
    """Extract actual current members; explicit SQL/widget doubles, not device proof."""
    assets={'backend-prelude': 'import java.util.*;import java.io.*;import java.nio.charset.StandardCharsets;\nclass Ledger{static void positive(long id){if(id<=0)throw new IllegalArgumentException();}}\nclass Cursor implements AutoCloseable{\n static final int FIELD_TYPE_NULL=0,FIELD_TYPE_INTEGER=1,FIELD_TYPE_STRING=3,FIELD_TYPE_BLOB=4;\n boolean moveToFirst(){return true;}String getString(int i){return "Same";}public void close(){}\n}\nclass SQLiteDatabase{\n List<String> values=new ArrayList<>(Arrays.asList("Old")),tags=new ArrayList<>(Arrays.asList("Tag")),other=new ArrayList<>(Arrays.asList("Keep"));\n long rev=9,external=0;boolean outer,fault,corrupt;long pathFirst=1,tagFirst=1;\n SQLiteDatabase copy(){SQLiteDatabase d=new SQLiteDatabase();d.values=new ArrayList<>(values);d.tags=new ArrayList<>(tags);d.other=new ArrayList<>(other);d.rev=rev;d.external=external;d.pathFirst=pathFirst;d.tagFirst=tagFirst;return d;}\n boolean inTransaction(){return outer;}void beginTransaction(){}void endTransaction(){}void setTransactionSuccessful(){}boolean isOpen(){return true;}\n Cursor rawQuery(String q,String[]a){if(!q.equals("SELECT title FROM activities WHERE id=? AND archived=0"))throw new AssertionError(q);if(!a[0].equals("10"))throw new IllegalArgumentException();return new Cursor();}\n int delete(String table,String where,String[]a){if(!where.equals("activity_id=?")||!a[0].equals("10"))throw new AssertionError("owner");List<String> v=table.equals("paths")?values:tags;int n=v.size();v.clear();if(table.equals("paths"))pathFirst=6;else tagFirst=6;return n;}\n void execSQL(String q,Object[]a){String table=q.contains("paths")?"paths":"tags";if(!q.equals("INSERT INTO "+table+" VALUES(?,?,?)")||!a[0].equals(10L))throw new AssertionError(q);List<String> v=table.equals("paths")?values:tags;if(!a[1].equals(v.size()))throw new AssertionError("position");v.add((String)a[2]);if(corrupt)external++;}\n}\nclass AppDatabase {\n Object restoreSession=new Object();SQLiteDatabase sql=new SQLiteDatabase();\n interface Work<T>{T run(SQLiteDatabase db);}\n <T>T tx(Work<T>a){SQLiteDatabase b=sql.copy();try{return a.run(sql);}catch(RuntimeException e){sql.values=b.values;sql.tags=b.tags;sql.other=b.other;sql.rev=b.rev;sql.external=b.external;sql.pathFirst=b.pathFirst;sql.tagFirst=b.tagFirst;throw e;}}\n SQLiteDatabase getReadableDatabase(){return sql;}SQLiteDatabase getWritableDatabase(){return sql;}\n static void noteDeletionNoOuterTransaction(SQLiteDatabase d){if(d.outer)throw new IllegalStateException();}\n static String text(String s){if(s==null||s.trim().isEmpty())throw new IllegalArgumentException();return s.trim();}\n List<String> orderedStrings(String t,long id){return new ArrayList<>(t.equals("paths")?sql.values:sql.tags);}\n static long revision(SQLiteDatabase d){return d.rev;}static long bump(SQLiteDatabase d){if(d.fault)throw new IllegalStateException("late");return ++d.rev;}\n static void require(boolean b,String s){if(!b)throw new IllegalArgumentException(s);}\n static final String[] SNAPSHOT_TABLES={"revision","paths","tags","ledger"};\n static class LimitedBytes extends ByteArrayOutputStream{}\n static void blob(DataOutputStream o,byte[]b)throws IOException{o.writeInt(b.length);o.write(b);}\n static void utf8(DataOutputStream o,String s)throws IOException{blob(o,s.getBytes(StandardCharsets.UTF_8));}\n static byte[] readBlob(DataInputStream i)throws IOException{int n=i.readInt();require(n>=0&&n<=i.available(),"length");byte[]b=new byte[n];i.readFully(b);return b;}\n static String readText(DataInputStream i)throws IOException{return new String(readBlob(i),StandardCharsets.UTF_8);}\n static void table(DataOutputStream o,String t,String[] names,List<Object[]> rows)throws IOException{\n  utf8(o,t);o.writeInt(names.length);for(String n:names)utf8(o,n);o.writeInt(rows.size());\n  for(Object[]row:rows)for(Object v:row){if(v instanceof Long){o.writeByte(1);o.writeLong((Long)v);}else if(v instanceof String){o.writeByte(3);utf8(o,(String)v);}else if(v instanceof byte[]){o.writeByte(4);blob(o,(byte[])v);}else o.writeByte(0);}\n }\n static byte[] noteDeletionState(SQLiteDatabase d){\n  try{var b=new ByteArrayOutputStream();var o=new DataOutputStream(b);o.writeInt(0x4e444c31);o.writeInt(3);o.writeInt(4);\n   table(o,"revision",new String[]{"id","id","value"},Collections.singletonList(new Object[]{1L,1L,d.rev}));\n   for(String t:Arrays.asList("paths","tags")){\n    List<Object[]>rows=new ArrayList<>();List<String>v=t.equals("paths")?d.values:d.tags;long first=t.equals("paths")?d.pathFirst:d.tagFirst;\n    for(int j=0;j<v.size();j++)rows.add(new Object[]{first+j,10L,(long)j,v.get(j)});\n    rows.add(new Object[]{5L,20L,0L,"Keep"});rows.sort(Comparator.comparingLong(r->(Long)r[0]));\n    table(o,t,new String[]{"rowid","activity_id","position","text"},rows);\n   }\n   table(o,"ledger",new String[]{"rowid","value","bytes","nullable"},Collections.singletonList(new Object[]{1L,d.external,new byte[]{0,-1,2},null}));return b.toByteArray();\n  }catch(IOException e){throw new RuntimeException(e);}\n }\n', 'backend-test': 'import java.util.*;\nclass Test {\n static int checks;\n static void need(boolean b,String s){if(!b)throw new AssertionError(s);checks++;System.out.println("RELATION_CHECK "+s);}\n interface Action{void run()throws Exception;}\n static void refuse(Class<?> type,Action a,String label)throws Exception{\n  try{a.run();}catch(Exception e){need(type.isInstance(e),label);return;}throw new AssertionError(label);\n }\n public static void main(String[]args)throws Exception{\n  AppDatabase h=new AppDatabase();var p=h.prepareActivityStrings(10,false);\n  need(p.activityId()==10&&p.title().equals("Same")&&p.values().equals(Arrays.asList("Old"))&&h.sql.rev==9,"prepare");\n  System.out.println("RELATION_VALID_WITNESS");\n  need(h.confirmActivityStrings(p,Arrays.asList(" A ","B","A"))&&h.sql.values.equals(Arrays.asList("A","B","A"))&&h.sql.rev==10,"path_order_duplicates");\n  need(h.sql.other.equals(Arrays.asList("Keep"))&&h.sql.tags.equals(Arrays.asList("Tag")),"unrelated");\n  final var used=p;refuse(IllegalStateException.class,()->h.confirmActivityStrings(used,Arrays.asList("Again")),"duplicate");\n  p=h.prepareActivityStrings(10,true);need(h.confirmActivityStrings(p,Arrays.asList(" z ","a","z"))&&h.sql.tags.equals(Arrays.asList("z","a")),"tag_dedup_order");\n  p=h.prepareActivityStrings(10,true);long rev=h.sql.rev;\n  need(!h.confirmActivityStrings(p,Arrays.asList("z","a","z"))&&h.sql.rev==rev,"same_readonly");\n  p=h.prepareActivityStrings(10,false);need(h.confirmActivityStrings(p,Collections.emptyList())&&h.sql.values.isEmpty(),"clear");\n  final var blank=h.prepareActivityStrings(10,false);\n  refuse(IllegalArgumentException.class,()->h.confirmActivityStrings(blank,Arrays.asList("A"," ")),"blank");\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(blank,Arrays.asList("A")),"blank_consumed");\n  final var cancel=h.prepareActivityStrings(10,false);cancel.close();\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(cancel,Arrays.asList("A")),"cancel");\n  final var stale=h.prepareActivityStrings(10,false);h.sql.external++;\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(stale,Collections.emptyList()),"stale");\n  final var session=h.prepareActivityStrings(10,false);h.restoreSession=new Object();\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(session,Arrays.asList("A")),"session");\n  final var connection=h.prepareActivityStrings(10,false);h.sql=h.sql.copy();\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(connection,Arrays.asList("A")),"connection");\n  final var foreign=h.prepareActivityStrings(10,false);\n  refuse(IllegalArgumentException.class,()->new AppDatabase().confirmActivityStrings(foreign,Arrays.asList("A")),"foreign");\n  need(h.confirmActivityStrings(foreign,Arrays.asList("A")),"owner_retained");\n  final var fault=h.prepareActivityStrings(10,false);byte[] before=AppDatabase.noteDeletionState(h.sql);h.sql.fault=true;\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(fault,Arrays.asList("B")),"late_fault");\n  need(Arrays.equals(before,AppDatabase.noteDeletionState(h.sql)),"rollback");h.sql.fault=false;\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(fault,Arrays.asList("B")),"failure_consumed");\n  final var damage=h.prepareActivityStrings(10,false);before=AppDatabase.noteDeletionState(h.sql);h.sql.corrupt=true;\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(damage,Arrays.asList("B")),"readback");\n  need(Arrays.equals(before,AppDatabase.noteDeletionState(h.sql)),"readback_rollback");h.sql.corrupt=false;\n  final var outer=h.prepareActivityStrings(10,false);h.sql.outer=true;\n  refuse(IllegalStateException.class,()->h.confirmActivityStrings(outer,Arrays.asList("B")),"outer");\n  refuse(IllegalStateException.class,()->h.prepareActivityStrings(10,false),"prepare_outer");h.sql.outer=false;\n  refuse(IllegalArgumentException.class,()->h.prepareActivityStrings(11,false),"missing");\n  System.out.println("RELATION_BACKEND_PASS "+checks+" HOST_DOUBLES_NOT_SQLITE");\n }\n}\n', 'ui-db': 'package com.supercubegame.pockettodo;\nimport java.util.*;\nclass AppDatabase{\n List<String> path=new ArrayList<>(Arrays.asList("Old")),tags=new ArrayList<>(Arrays.asList("Tag"));int writes,attempts,external;\n ActivityStringsPlan last;\n static class ActivityStringsPlan implements AutoCloseable{\n  boolean terminal,tags;int external;List<String> values;\n  public void close(){terminal=true;}long activityId(){return 10;}String title(){return "Same";}List<String> values(){return values;}\n }\n ActivityStringsPlan prepareActivityStrings(long id,boolean tags){\n  if(id!=10)throw new AssertionError("wrong owner");last=new ActivityStringsPlan();last.tags=tags;last.external=external;last.values=new ArrayList<>(tags?this.tags:path);return last;\n }\n boolean confirmActivityStrings(ActivityStringsPlan p,List<String> input){\n  attempts++;if(p.terminal||p.external!=external)throw new IllegalStateException();p.close();\n  List<String>v=new ArrayList<>();for(String s:input){s=s.trim();if(s.isEmpty())throw new IllegalArgumentException();if(!p.tags||!v.contains(s))v.add(s);}\n  if(v.equals(p.values))return false;if(p.tags)tags=v;else path=v;writes++;return true;\n }\n}\n', 'ui-test': 'package com.supercubegame.pockettodo;\nimport android.view.View;import android.widget.*;import java.util.*;\nclass Test {\n static int checks;\n static void need(boolean b,String s){if(!b)throw new AssertionError(s);checks++;System.out.println("RELATION_UI_CHECK "+s);}\n static TodayScreen fresh(){return new TodayScreen();}\n static void input(TodayScreen h,String value){((EditText)h.one(h.outer.find("活动路径")==null?"活动标签":"活动路径")).setText(value);}\n static View open(TodayScreen h,boolean tags){\n  View a=new View();h.outer.addView(a);\n  RelationEditor r=new RelationEditor(h,10,"Same",tags,Arrays.asList(tags?"Tag":"Old"),()->h.content());\n  r.open(a);h.drain();return h.one("relation-save");\n }\n public static void main(String[]args){\n  TodayScreen h=fresh();View save=open(h,false);\n  need(((TextView)h.one("relation-identity")).text.contains("#10")&&h.db.writes==0,"prepare");\n  System.out.println("RELATION_UI_VALID_WITNESS");\n  input(h,"A\\n \\nB");save.performClick();\n  need(h.queue.isEmpty()&&h.db.writes==0&&!((TextView)h.one("relation-validation")).text.isEmpty(),"blank_visible");\n  input(h," A\\nB\\nA");save.performClick();save.performClick();\n  need(h.queue.size()==1,"pending_once");h.drain();\n  need(h.db.path.equals(Arrays.asList("A","B","A"))&&h.db.writes==1,"path_order");save.performClick();need(h.queue.isEmpty(),"old_save");\n  h=fresh();save=open(h,true);input(h," z\\na\\nz");save.performClick();h.drain();\n  need(h.db.tags.equals(Arrays.asList("z","a"))&&h.db.path.equals(Arrays.asList("Old")),"tag_order");\n  h=fresh();save=open(h,false);input(h,"");save.performClick();h.drain();need(h.db.path.isEmpty(),"clear");\n  h=fresh();save=open(h,false);save.performClick();h.drain();need(h.db.writes==0,"same");\n  h=fresh();save=open(h,false);h.one("relation-cancel").performClick();save.performClick();h.drain();need(h.db.writes==0&&h.db.last.terminal,"cancel");\n  h=fresh();save=open(h,false);h.content();save.performClick();h.drain();need(h.db.writes==0&&h.db.last.terminal,"detached");\n  h=fresh();save=open(h,false);input(h,"Change");save.performClick();h.content();h.drain();need(h.db.writes==0&&h.db.last.terminal,"queued_detached");\n  h=fresh();save=open(h,false);h.db.external++;input(h,"Change");save.performClick();h.drain();\n  need(h.db.writes==0&&!save.isEnabled()&&!((TextView)h.one("relation-validation")).text.isEmpty(),"stale");\n  save.performClick();h.drain();need(h.db.attempts==1,"failure_terminal");\n  h=fresh();View anchor=new View();h.outer.addView(anchor);\n  new RelationEditor(h,10,"Wrong",false,Arrays.asList("Old"),h::content).open(anchor);h.drain();\n  need(h.db.last.terminal&&h.outer.find("relation-save")==null,"stale_title");\n  h=fresh();anchor=new View();h.outer.addView(anchor);\n  new RelationEditor(h,10,"Same",false,Arrays.asList("Wrong"),h::content).open(anchor);h.drain();\n  need(h.db.last.terminal&&h.outer.find("relation-save")==null,"stale_values");\n  h=fresh();anchor=new View();h.outer.addView(anchor);\n  new RelationEditor(h,10,"Same",false,Arrays.asList("Old"),h::content).open(anchor);h.content();h.drain();\n  need(h.db.last.terminal&&h.outer.find("relation-save")==null,"prepare_detached");\n  h=fresh();save=open(h,false);h.activity.destroyed=true;input(h,"X");save.performClick();h.drain();need(h.db.writes==0,"destroyed");\n  System.out.println("RELATION_UI_PASS "+checks+" HOST_WIDGET_DOUBLES");\n }\n}\n', 'ui-fixtures': {'android/view/View.java': 'package android.view;\nimport java.util.*;\npublic class View {\n public boolean attached,enabled=true;public String description="";\n public List<View> children=new ArrayList<>();\n public interface OnClickListener{void onClick(View v);}\n public interface OnAttachStateChangeListener{void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}\n public OnClickListener click;public List<OnAttachStateChangeListener> listeners=new ArrayList<>();\n public boolean isAttachedToWindow(){return attached;}public boolean isEnabled(){return enabled;}\n public void setEnabled(boolean b){enabled=b;}public void setContentDescription(String s){description=s;}\n public void setOnClickListener(OnClickListener l){click=l;}\n public boolean performClick(){if(click==null)return false;click.onClick(this);return true;}\n public void addOnAttachStateChangeListener(OnAttachStateChangeListener l){listeners.add(l);}\n public void attach(boolean yes){attached=yes;for(View v:new ArrayList<>(children))v.attach(yes);for(OnAttachStateChangeListener l:listeners){if(yes)l.onViewAttachedToWindow(this);else l.onViewDetachedFromWindow(this);}}\n public void setPadding(int a,int b,int c,int d){}public void setBackground(Object o){}\n public View find(String s){if(description.equals(s))return this;for(View v:children){View x=v.find(s);if(x!=null)return x;}return null;}\n}', 'android/widget/LinearLayout.java': 'package android.widget;import android.view.View;\npublic class LinearLayout extends View{\n public LinearLayout(Object c){} public static class LayoutParams{public LayoutParams(int a,int b){}public LayoutParams(int a,int b,int c){}}\n public void addView(View v){children.add(v);if(attached)v.attach(true);}\n public void addView(View v,LayoutParams p){addView(v);}\n public void removeAllViews(){for(View v:children)v.attach(false);children.clear();}\n}', 'android/widget/TextView.java': 'package android.widget;import android.view.View;\npublic class TextView extends View{public String text="";public TextView(Object c){}public void setText(String s){text=s;}public CharSequence getText(){return text;}}', 'android/widget/EditText.java': 'package android.widget;public class EditText extends TextView{public EditText(Object c){super(c);}public void setHint(String s){}}', 'android/widget/Button.java': 'package android.widget;public class Button extends TextView{public Button(Object c){super(c);}}', 'android/widget/ScrollView.java': 'package android.widget;public class ScrollView extends LinearLayout{public ScrollView(Object c){super(c);}public void setFillViewport(boolean b){}}', 'android/database/Cursor.java': 'package android.database;import java.util.*;\npublic class Cursor implements AutoCloseable{\n List<Object[]>rows;int i=-1;public Cursor(List<Object[]>r){rows=r;}\n public boolean moveToNext(){return ++i<rows.size();}public boolean moveToFirst(){i=0;return !rows.isEmpty();}\n public long getLong(int c){return((Number)rows.get(i)[c]).longValue();}public String getString(int c){return(String)rows.get(i)[c];}\n public boolean isNull(int c){return rows.get(i)[c]==null;}public void close(){}\n}', 'com/supercubegame/pockettodo/TodayScreen.java': 'package com.supercubegame.pockettodo;\nimport android.view.View;import android.widget.*;import java.util.*;import java.util.concurrent.Callable;import java.util.function.Consumer;\nclass TodayScreen{\n static final int INK=1,MUTED=2,ERROR=3,WHITE=4;\n static class Activity{boolean finishing,destroyed;boolean isFinishing(){return finishing;}boolean isDestroyed(){return destroyed;}}\n Activity activity=new Activity();AppDatabase db=new AppDatabase();LinearLayout outer=new LinearLayout(activity);\n ArrayDeque<Runnable> queue=new ArrayDeque<>();boolean busy;String message;\n TodayScreen(){outer.attach(true);}\n <T>void work(Callable<T>a,Consumer<T>s,Runnable f){\n  if(busy)throw new AssertionError("unexpected concurrent work");busy=true;\n  queue.add(()->{T x;try{x=a.call();}catch(Exception e){busy=false;if(f!=null)f.run();return;}busy=false;s.accept(x);});\n }\n void drain(){int n=0;while(!queue.isEmpty()){if(++n>20)throw new AssertionError("queue cycle");queue.remove().run();}}\n LinearLayout content(){outer.removeAllViews();return outer;}LinearLayout column(){return new LinearLayout(activity);}\n TextView text(String s,int size,int color){TextView v=new TextView(activity);v.setText(s);return v;}\n EditText field(String key,boolean multi){EditText v=new EditText(activity);v.setContentDescription(key);return v;}\n Button button(String s,Runnable r){Button v=new Button(activity);v.setText(s);v.setOnClickListener(w->{if(!busy)r.run();});return v;}\n int dp(int n){return n;}Object shape(int c,int r){return null;}\n void addRow(LinearLayout p,View v){p.addView(v);}void message(String s,boolean e){message=s;}\n View one(String s){View v=outer.find(s);if(v==null)throw new AssertionError("missing "+s);return v;}\n void text(String s,String v){((EditText)one(s)).setText(v);}\n}', 'com/supercubegame/pockettodo/AppDatabase.java': 'package com.supercubegame.pockettodo;\nimport android.database.Cursor;import java.util.*;\nclass AppDatabase{\n TreeMap<Long,String[]>apps=new TreeMap<>();int writes,links,attempts;boolean fail,failRead;\n class SQL{Cursor rawQuery(String q,String[]args){\n  List<Object[]>r=new ArrayList<>();if(q.equals("SELECT MAX(id) FROM applications"))r.add(new Object[]{apps.isEmpty()?null:apps.lastKey()});\n  else if(q.equals("SELECT id,name,package_name FROM applications ORDER BY id")){if(failRead)throw new IllegalStateException("read failed");for(Map.Entry<Long,String[]>e:apps.entrySet())r.add(new Object[]{e.getKey(),e.getValue()[0],e.getValue()[1]});}\n  else throw new AssertionError(q);return new Cursor(r);\n }}\n SQL getReadableDatabase(){return new SQL();}\n void addApplication(long id,String name,String pkg){for(String[]a:apps.values())if(!pkg.isEmpty()&&a[1].equals(pkg))throw new IllegalArgumentException("duplicate");apps.put(id,new String[]{name,pkg});writes++;}\n static class ApplicationActivityPlan implements AutoCloseable{\n  long category,app;String name;boolean terminal;public void close(){terminal=true;}\n  long applicationId(){return app;}String categoryName(){return "Category";}String applicationName(){return name;}\n }\n ApplicationActivityPlan last;\n ApplicationActivityPlan prepareApplicationActivity(long c,long a){ApplicationActivityPlan p=new ApplicationActivityPlan();p.category=c;p.app=a;p.name=apps.get(a)[0];last=p;return p;}\n long confirmApplicationActivity(ApplicationActivityPlan p,String title){attempts++;if(p.terminal)throw new IllegalStateException();p.close();if(fail)throw new IllegalStateException("late");links++;writes++;return links;}\n}'}}
    extract=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{
 public static void main(String[]a)throws Exception{
  JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
  try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
   JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
   CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
   String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();
   Set<String>w=new HashSet<>(Arrays.asList(a[2].split(",")));StringBuilder out=new StringBuilder();
   for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers()){
    String n=m instanceof ClassTree?((ClassTree)m).getSimpleName().toString():m instanceof MethodTree?((MethodTree)m).getName().toString():"";
    if(w.remove(n))out.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");
   }
   if(!w.isEmpty())throw new AssertionError("missing relation API "+w);Files.writeString(Path.of(a[1]),out.toString());
  }
 }
}'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"Extract.java").write_text(extract)
        (p/"Compile.java").write_text('import javax.tools.*;class Compile{public static void main(String[]a){System.exit(ToolProvider.getSystemJavaCompiler().run(null,null,null,a));}}')
        def members(file,names):
            result=subprocess.run(["java",str(p/"Extract.java"),str(ROOT/"src/main/java/com/supercubegame/pockettodo"/file),str(p/"members"),names],capture_output=True,text=True,timeout=30)
            assert result.returncode==0,(result.stdout,result.stderr)
            return (p/"members").read_text()
        backend=members("AppDatabase.java","ActivityStringsPlan,prepareActivityStrings,confirmActivityStrings,activityStringsExpected")
        ui=members("ActivitiesScreen.java","RelationEditor")
        def execute(code,kind):
            target=p/kind;target.mkdir(exist_ok=True)
            if kind=="BACKEND":
                files={"AppDatabase.java":assets["backend-prelude"]+code+"\n}\n","Test.java":assets["backend-test"]}
                entry="Test"
            else:
                files=dict(assets["ui-fixtures"])
                files["com/supercubegame/pockettodo/AppDatabase.java"]=assets["ui-db"]
                files["com/supercubegame/pockettodo/RelationEditor.java"]="package com.supercubegame.pockettodo;import android.widget.*;import java.util.*;\n"+code.replace("private static final class RelationEditor","final class RelationEditor",1)
                files["com/supercubegame/pockettodo/Test.java"]=assets["ui-test"]
                entry="com.supercubegame.pockettodo.Test"
            for name,text in files.items():
                f=target/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
            compiled=subprocess.run(["java",str(p/"Compile.java"),"-d",str(target)]+[str(target/n) for n in files],capture_output=True,text=True,timeout=30)
            assert compiled.returncode==0,("relation host compile",compiled.stdout,compiled.stderr)
            return subprocess.run(["java","-cp",str(target),entry],capture_output=True,text=True,timeout=30)
        for kind,code,count,mutants in [
            ("BACKEND",backend,23,[
                ('if(!plan.tags||!clean.contains(s))','if(true)',"tag_dedup_order"),
                ('terminal=true;before=null;',';',"cancel"),
                ('if(!Arrays.equals(plan.before,noteDeletionState(db)))','if(false)',"stale"),
                ('plan.session!=restoreSession','false',"session"),
                ('connection!=plan.connection||!connection.isOpen()','!connection.isOpen()',"connection"),
                ('||!Arrays.equals(expected,noteDeletionState(db))','||false',"readback"),
                ('if(clean.equals(plan.values))return false;','if(false)return false;',"same_readonly"),
            ]),
            ("UI",ui,17,[
                ('if(clean.isEmpty())','if(false)',"blank_visible"),
                ('@Override public void onViewDetachedFromWindow(android.view.View v){close();}','@Override public void onViewDetachedFromWindow(android.view.View v){}',"detached"),
                ('||!title.equals(p.title())','',"stale_title"),
                ('||!shown.equals(p.values())','',"stale_values"),
            ])
        ]:
            result=execute(code,kind);assert result.returncode==0,(result.stdout,result.stderr)
            expected_prefix="RELATION_CHECK " if kind=="BACKEND" else "RELATION_UI_CHECK "
            labels=[l[len(expected_prefix):] for l in result.stdout.splitlines() if l.startswith(expected_prefix)]
            assert len(labels)==count and len(set(labels))==count,(kind,labels)
            print(result.stdout.strip(),flush=True)
            witness="RELATION_VALID_WITNESS" if kind=="BACKEND" else "RELATION_UI_VALID_WITNESS"
            for old,new,label in mutants:
                assert code.count(old)==1,(kind,"mutation anchor",old)
                result=execute(code.replace(old,new),kind)
                assert result.returncode!=0 and witness in result.stdout and "AssertionError: "+label in result.stderr,(kind,label,result.stdout,result.stderr)
                print("RELATION_MUTANT_REJECTED "+kind+" "+label,flush=True)
        print("RELATION_HOST backend=23 ui=17 witnessed_mutants=11 PASS; extracted Java, SQL/widget doubles")


def repair_selftest(source=None, ui_source=None, mutants=True):
    """Actual generated comparator and Java AST layout checks, not Android geometry."""
    import tempfile, subprocess
    from pathlib import Path
    if source is None: source=JAVA
    if ui_source is None: ui_source=(ROOT/"src/main/java/com/supercubegame/pockettodo/ActivitiesScreen.java").read_text()
    extract=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{
 public static void main(String[]a)throws Exception{
  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
  try(StandardJavaFileManager f=compiler.getStandardFileManager(d,null,null)){
   JavacTask task=(JavacTask)compiler.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
   CompilationUnitTree unit=task.parse().iterator().next();
   for(Diagnostic<?> e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
   String text=Files.readString(Path.of(a[0]));SourcePositions pos=Trees.instance(task).getSourcePositions();
   Map<String,MethodTree> methods=new HashMap<>();
   for(Tree type:unit.getTypeDecls())if(type instanceof ClassTree)for(Tree member:((ClassTree)type).getMembers())
    if(member instanceof MethodTree)methods.put(((MethodTree)member).getName().toString(),(MethodTree)member);
   if(a[2].equals("backup")){
    StringBuilder out=new StringBuilder();
    for(String name:Arrays.asList("backupProjection","backupEqual")){
     MethodTree m=methods.get(name);if(m==null)throw new AssertionError("missing backup comparator");
     out.append(text.substring((int)pos.getStartPosition(unit,m),(int)pos.getEndPosition(unit,m))).append("\n");
    }Files.writeString(Path.of(a[1]),out);
   }else{
    MethodTree render=methods.get("renderDetail");if(render==null)throw new AssertionError("missing render");
    List<String> calls=new ArrayList<>();
    new TreeScanner<Void,Void>(){
     @Override public Void visitMethodInvocation(MethodInvocationTree m,Void p){
      calls.add(m.getMethodSelect().toString()+"("+m.getArguments().toString()+")");return super.visitMethodInvocation(m,p);
     }
    }.scan(render.getBody(),null);
    if(Collections.frequency(calls,"body.addView(stamp)")!=1||Collections.frequency(calls,"body.addView(marks)")!=1
      ||calls.contains("details.addView(stamp)")||calls.contains("details.addView(marks)"))
      throw new AssertionError("checkin must stay outside scroll");
    int status=calls.indexOf("body.addView(stamp)"),marks=calls.indexOf("body.addView(marks)"),scroll=-1;
    for(int i=0;i<calls.size();i++)if(calls.get(i).startsWith("body.addView(scroll,"))scroll=i;
    if(!(status<marks&&marks<scroll))throw new AssertionError("fixed controls before scroll");
    if(calls.indexOf("details.addView(tagText)")>=calls.indexOf("details.addView(pathTitle)"))
      throw new AssertionError("path remains last scroll section");
    System.out.println("DETAIL_LAYOUT_AST_PASS_NOT_GEOMETRY");
   }
  }
 }
}'''
    harness=r'''import java.util.*;
class Check{
 static void need(boolean b,String s){if(!b)throw new AssertionError(s);}
 __METHODS__
 static List<String> row(String...v){return new ArrayList<>(Arrays.asList(v));}
 static Map<String,List<List<String>>> fixture(boolean restored){
  Map<String,List<List<String>>> m=new TreeMap<>();
  m.put("paths",new ArrayList<>(Arrays.asList(row("rowid","activity_id","position","text"),row("1:1","1:5","1:0","3:A"),row("1:2","1:5","1:1","3:B"),row("1:3","1:5","1:2","3:A"))));
  m.put("tags",new ArrayList<>(Arrays.asList(row("rowid","activity_id","position","text"),row(restored?"1:1":"1:2","1:6","1:0","3:z"),row(restored?"1:2":"1:3","1:6","1:1","3:a"),row(restored?"1:3":"1:4","1:5","1:0","3:Final"))));
  m.put("notes",new ArrayList<>(Arrays.asList(row("rowid","id","title"),row("1:9","3:note","3:Keep"))));
  m.put("revision",new ArrayList<>(Arrays.asList(row("rowid","id","value"),row("1:1","1:1","1:12"))));return m;
 }
 static void bad(Map<String,List<List<String>>> a,Map<String,List<List<String>>> b,String label){
  boolean rejected;try{rejected=!backupEqual(a,b);}catch(AssertionError|IllegalArgumentException e){rejected=true;}need(rejected,label);
 }
 public static void main(String[]args){
  var a=fixture(false);var b=fixture(true);String frozen=a.toString();
  need(backupEqual(a,a),"equal witness");System.out.println("BACKUP_EQUAL_WITNESS");
  need(!a.equals(b)&&backupEqual(a,b),"rowid_only_allowed");System.out.println("BACKUP_NORMALIZATION_WITNESS");
  need(a.toString().equals(frozen),"input_unchanged");
  for(String table:Arrays.asList("paths","tags"))for(int col=1;col<4;col++){
   b=fixture(true);b.get(table).get(1).set(col,"3:corrupt");bad(a,b,"declared_cell");
  }
  b=fixture(true);b.get("tags").get(1).set(1,"3:6");bad(a,b,"type_preserved");
  b=fixture(true);Collections.swap(b.get("paths"),1,2);bad(a,b,"row_order");
  b=fixture(true);b.get("paths").remove(3);bad(a,b,"duplicate_step");
  b=fixture(true);b.remove("paths");bad(a,b,"table_set");
  b=fixture(true);b.get("tags").get(0).set(3,"caption");bad(a,b,"columns");
  b=fixture(true);b.get("notes").get(1).set(0,"1:1");bad(a,b,"other_rowid_exact");
  b=fixture(true);b.get("notes").get(1).set(2,"3:Bad");bad(a,b,"other_content_exact");
  b=fixture(true);b.get("revision").get(1).set(2,"1:13");bad(a,b,"revision_exact");
  b=fixture(true);b.get("paths").add(row("1:4","1:5","1:3","3:Extra"));bad(a,b,"extra_row");
  b=fixture(true);b.get("tags").get(1).set(0,"3:1");bad(a,b,"rowid_type");
  b=fixture(true);b.get("tags").get(2).set(0,"1:1");bad(a,b,"rowid_order");
  System.out.println("BACKUP_COMPARATOR_PASS 3 positive 17 negative");
 }
}'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"Extract.java").write_text(extract)
        (p/"Device.java").write_text(source);(p/"ActivitiesScreen.java").write_text(ui_source)
        def run(args):
            return subprocess.run(["java",*map(str,args)],capture_output=True,text=True,timeout=30)
        r=run([p/"Extract.java",p/"Device.java",p/"methods","backup"])
        assert r.returncode==0,(r.stdout,r.stderr)
        methods=(p/"methods").read_text()
        def check(code):
            (p/"Check.java").write_text(harness.replace("__METHODS__",code))
            return run([p/"Check.java"])
        r=check(methods);assert r.returncode==0,(r.stdout,r.stderr);print(r.stdout.strip())
        r=run([p/"Extract.java",p/"ActivitiesScreen.java",p/"unused","layout"])
        assert r.returncode==0,(r.stdout,r.stderr);print(r.stdout.strip())
        if mutants:
            for old,new,label,witness in (
                ('row.subList(1,row.size())','row','rowid_only_allowed','BACKUP_EQUAL_WITNESS'),
                ('row.subList(1,row.size())','row.subList(2,row.size())','declared_cell','BACKUP_NORMALIZATION_WITNESS'),
                ('}else rows.add(new ArrayList<>(row));','}else rows.add(new ArrayList<>(row.subList(1,row.size())));','other_rowid_exact','BACKUP_NORMALIZATION_WITNESS'),
                ('return backupProjection(before).equals(backupProjection(after));','return true;','declared_cell','BACKUP_NORMALIZATION_WITNESS'),
                ('need(current>previous,"backup rowid order");',';','rowid_order','BACKUP_NORMALIZATION_WITNESS'),
            ):
                assert methods.count(old)==1
                r=check(methods.replace(old,new))
                assert r.returncode!=0 and witness in r.stdout and ("AssertionError: "+label) in r.stderr,(label,r.stdout,r.stderr)
            for old,new in (("body.addView(stamp)","details.addView(stamp)"),("body.addView(marks)","details.addView(marks)")):
                assert ui_source.count(old)==1
                (p/"ActivitiesScreen.java").write_text(ui_source.replace(old,new))
                r=run([p/"Extract.java",p/"ActivitiesScreen.java",p/"unused","layout"])
                assert r.returncode!=0 and "checkin must stay outside scroll" in r.stderr,r.stderr
            print("REPAIR_MUTANTS 5 comparator and 2 layout rejected; host only")


def archive_host_selftest():
    """Actual extracted members; SQL/widget doubles are not Android acceptance."""
    assets={'prelude': 'import java.util.*;import java.io.*;import java.nio.charset.StandardCharsets;\nclass Ledger{static void positive(long id){if(id<=0)throw new IllegalArgumentException("id");}}\nclass Cursor implements AutoCloseable{\n static final int FIELD_TYPE_NULL=0,FIELD_TYPE_INTEGER=1,FIELD_TYPE_STRING=3,FIELD_TYPE_BLOB=4;\n Object[] row;Cursor(Object[]r){row=r;}\n boolean moveToFirst(){return row!=null;}String getString(int i){return (String)row[i];}\n long getLong(int i){return (Long)row[i];}public void close(){}\n}\nclass SQLiteDatabase{\n long rev=9,archived=0,otherArchived=0,external=0;boolean outer,open=true,fault,corrupt,noWrite,wrongOwner;\n SQLiteDatabase copy(){SQLiteDatabase b=new SQLiteDatabase();b.rev=rev;b.archived=archived;b.otherArchived=otherArchived;b.external=external;return b;}\n void restore(SQLiteDatabase b){rev=b.rev;archived=b.archived;otherArchived=b.otherArchived;external=b.external;}\n boolean inTransaction(){return outer;}void beginTransaction(){}void endTransaction(){}void setTransactionSuccessful(){}boolean isOpen(){return open;}\n Cursor rawQuery(String q,String[]a){\n  if(!q.equals("SELECT title,archived FROM activities WHERE id=?"))throw new AssertionError(q);\n  return new Cursor(a[0].equals("10")?new Object[]{"Same",archived}:null);\n }\n void execSQL(String q,Object[]a){\n  if(!q.equals("UPDATE activities SET archived=? WHERE id=? AND archived=?")||!a[1].equals(10L))throw new AssertionError(q);\n  if(noWrite)return;\n  if(archived==((Number)a[2]).longValue()){if(wrongOwner)otherArchived=((Number)a[0]).longValue();else archived=((Number)a[0]).longValue();}\n  if(corrupt)external++;\n }\n}\nclass AppDatabase{\n Object restoreSession=new Object();SQLiteDatabase sql=new SQLiteDatabase();\n interface Work<T>{T run(SQLiteDatabase d);}\n <T>T tx(Work<T>a){SQLiteDatabase b=sql.copy();try{return a.run(sql);}catch(RuntimeException e){sql.restore(b);throw e;}}\n SQLiteDatabase getReadableDatabase(){return sql;}SQLiteDatabase getWritableDatabase(){return sql;}\n static void noteDeletionNoOuterTransaction(SQLiteDatabase d){if(d.outer)throw new IllegalStateException("outer");}\n static long revision(SQLiteDatabase d){return d.rev;}static long bump(SQLiteDatabase d){if(d.fault)throw new IllegalStateException("late");return ++d.rev;}\n static void require(boolean b,String s){if(!b)throw new IllegalArgumentException(s);}\n static final String[] SNAPSHOT_TABLES={"revision","categories","applications","activities","paths","tags","batches","ledger","checkins","media","notes","blocks","fields","field_options","field_values","field_notes","todos","legacy_imports"};\n static class LimitedBytes extends ByteArrayOutputStream{}\n static void blob(DataOutputStream o,byte[]b)throws IOException{o.writeInt(b.length);o.write(b);}\n static void utf8(DataOutputStream o,String s)throws IOException{blob(o,s.getBytes(StandardCharsets.UTF_8));}\n static byte[] readBlob(DataInputStream i)throws IOException{int n=i.readInt();require(n>=0&&n<=i.available(),"length");byte[]b=new byte[n];i.readFully(b);return b;}\n static String readText(DataInputStream i)throws IOException{return new String(readBlob(i),StandardCharsets.UTF_8);}\n static void table(DataOutputStream o,String t,String[]names,List<Object[]>rows)throws IOException{\n  utf8(o,t);o.writeInt(names.length);for(String n:names)utf8(o,n);o.writeInt(rows.size());\n  for(Object[]r:rows)for(Object v:r){if(v instanceof Long){o.writeByte(1);o.writeLong((Long)v);}else if(v instanceof String){o.writeByte(3);utf8(o,(String)v);}else if(v instanceof byte[]){o.writeByte(4);blob(o,(byte[])v);}else o.writeByte(0);}\n }\n static byte[] noteDeletionState(SQLiteDatabase d){\n  try{var b=new ByteArrayOutputStream();var o=new DataOutputStream(b);o.writeInt(0x4e444c31);o.writeInt(3);o.writeInt(SNAPSHOT_TABLES.length);\n   for(String t:SNAPSHOT_TABLES){\n    if(t.equals("revision"))table(o,t,new String[]{"id","id","value"},Collections.singletonList(new Object[]{1L,1L,d.rev}));\n    else if(t.equals("activities"))table(o,t,new String[]{"id","id","category_id","application_id","title","archived"},\n     Arrays.asList(new Object[]{10L,10L,2L,3L,"Same",d.archived},new Object[]{20L,20L,4L,null,"Same",d.otherArchived}));\n    else table(o,t,new String[]{"rowid","counter","text","payload","nullable"},Collections.singletonList(new Object[]{7L,d.external,t+" 中文",new byte[]{0,-1,2},null}));\n   }return b.toByteArray();\n  }catch(IOException e){throw new RuntimeException(e);}\n }\n', 'backend-test': 'import java.util.*;\nclass Test{\n static int checks;\n static void need(boolean b,String s){if(!b)throw new AssertionError(s);checks++;System.out.println("ARCHIVE_CHECK "+s);}\n interface Action{void run()throws Exception;}\n static void refuse(Class<?>type,Action a,String label)throws Exception{\n  try{a.run();}catch(Exception e){need(type.isInstance(e),label);return;}throw new AssertionError(label);\n }\n static void same(AppDatabase h,byte[]before,String label){need(Arrays.equals(before,AppDatabase.noteDeletionState(h.sql)),label);}\n public static void main(String[]args)throws Exception{\n  AppDatabase h=new AppDatabase();byte[]before=AppDatabase.noteDeletionState(h.sql);\n  var p=h.prepareActivityArchive(10,true);\n  need(p.activityId()==10&&p.title().equals("Same")&&!p.wasArchived()&&p.willArchive(),"preview_identity");\n  same(h,before,"prepare_readonly");System.out.println("ARCHIVE_VALID_WITNESS");\n  var expected=h.sql.copy();expected.archived=1;expected.rev++;\n  need(h.confirmActivityArchive(p)&&Arrays.equals(AppDatabase.noteDeletionState(expected),AppDatabase.noteDeletionState(h.sql)),"archive_exact");\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(p),"duplicate");\n  before=AppDatabase.noteDeletionState(h.sql);\n  need(!h.confirmActivityArchive(h.prepareActivityArchive(10,true)),"same_result");same(h,before,"same_readonly");\n  expected=h.sql.copy();expected.archived=0;expected.rev++;\n  need(h.confirmActivityArchive(h.prepareActivityArchive(10,false))&&Arrays.equals(AppDatabase.noteDeletionState(expected),AppDatabase.noteDeletionState(h.sql)),"restore_exact");\n  final var canceled=h.prepareActivityArchive(10,true);canceled.close();before=AppDatabase.noteDeletionState(h.sql);\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(canceled),"cancel");same(h,before,"cancel_readonly");\n  final var stale=h.prepareActivityArchive(10,false);h.sql.external++;\n  before=AppDatabase.noteDeletionState(h.sql);refuse(IllegalStateException.class,()->h.confirmActivityArchive(stale),"stale_same");same(h,before,"stale_readonly");\n  final var session=h.prepareActivityArchive(10,true);h.restoreSession=new Object();\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(session),"session");\n  final var connection=h.prepareActivityArchive(10,true);h.sql=h.sql.copy();\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(connection),"connection");\n  final var closed=h.prepareActivityArchive(10,true);h.sql.open=false;\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(closed),"closed");h.sql.open=true;\n  final var foreign=h.prepareActivityArchive(10,true);\n  refuse(IllegalArgumentException.class,()->new AppDatabase().confirmActivityArchive(foreign),"foreign");\n  need(h.confirmActivityArchive(foreign),"foreign_retains_owner");\n  final var fault=h.prepareActivityArchive(10,false);h.sql.fault=true;before=AppDatabase.noteDeletionState(h.sql);\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(fault),"late_fault");same(h,before,"late_rollback");h.sql.fault=false;\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(fault),"failure_consumed");\n  final var corrupt=h.prepareActivityArchive(10,false);h.sql.corrupt=true;before=AppDatabase.noteDeletionState(h.sql);\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(corrupt),"readback");same(h,before,"readback_rollback");h.sql.corrupt=false;\n  final var missingWrite=h.prepareActivityArchive(10,false);h.sql.noWrite=true;before=AppDatabase.noteDeletionState(h.sql);\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(missingWrite),"missing_write");same(h,before,"missing_write_rollback");h.sql.noWrite=false;\n  final var wrong=h.prepareActivityArchive(10,false);h.sql.wrongOwner=true;before=AppDatabase.noteDeletionState(h.sql);\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(wrong),"wrong_owner");same(h,before,"wrong_owner_rollback");h.sql.wrongOwner=false;\n  final var outer=h.prepareActivityArchive(10,false);h.sql.outer=true;\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(outer),"outer");\n  refuse(IllegalStateException.class,()->h.prepareActivityArchive(10,true),"prepare_outer");h.sql.outer=false;\n  refuse(IllegalStateException.class,()->h.confirmActivityArchive(outer),"outer_consumed");\n  refuse(IllegalArgumentException.class,()->h.prepareActivityArchive(11,true),"missing");\n  refuse(IllegalArgumentException.class,()->h.prepareActivityArchive(0,true),"invalid_id");\n  refuse(IllegalArgumentException.class,()->h.confirmActivityArchive(null),"null_plan");\n  h.sql.rev=Long.MAX_VALUE;final var overflow=h.prepareActivityArchive(10,false);before=AppDatabase.noteDeletionState(h.sql);\n  refuse(ArithmeticException.class,()->h.confirmActivityArchive(overflow),"overflow");same(h,before,"overflow_readonly");\n  System.out.println("ARCHIVE_BACKEND_PASS "+checks+" EXPLICIT_SQL_DOUBLES_NOT_ANDROID");\n }\n}\n', 'ui-db': 'package com.supercubegame.pockettodo;\nclass AppDatabase{\n boolean archived,fail;int writes,attempts,external;ActivityArchivePlan last;\n static class ActivityArchivePlan implements AutoCloseable{\n  boolean terminal,archived,target;int external;\n  public void close(){terminal=true;}long activityId(){return 10;}String title(){return "Same";}\n  boolean wasArchived(){return archived;}boolean willArchive(){return target;}\n }\n ActivityArchivePlan prepareActivityArchive(long id,boolean target){\n  if(id!=10)throw new AssertionError("wrong owner");\n  last=new ActivityArchivePlan();last.archived=archived;last.target=target;last.external=external;return last;\n }\n boolean confirmActivityArchive(ActivityArchivePlan p){\n  attempts++;if(p.terminal)throw new IllegalStateException();p.close();\n  if(fail||p.external!=external)throw new IllegalStateException();\n  if(archived==p.target)return false;archived=p.target;writes++;return true;\n }\n}\n', 'ui-test': 'package com.supercubegame.pockettodo;\nimport android.view.View;import android.widget.*;\nclass Test{\n static int checks;\n static void need(boolean b,String s){if(!b)throw new AssertionError(s);checks++;System.out.println("ARCHIVE_UI_CHECK "+s);}\n static View open(TodayScreen h,boolean archived){\n  h.db.archived=archived;View anchor=new View();h.outer.addView(anchor);\n  new ArchiveAction(h,10,"Same",archived,h::content).open(anchor);h.drain();return h.one("archive-confirm");\n }\n public static void main(String[]args){\n  TodayScreen h=new TodayScreen();View confirm=open(h,false);\n  need(((TextView)h.one("archive-identity")).text.contains("#10")&&((TextView)h.one("archive-impact")).text.contains("保留")&&h.db.writes==0,"preview");\n  System.out.println("ARCHIVE_UI_VALID_WITNESS");\n  confirm.performClick();confirm.performClick();need(h.queue.size()==1,"pending_once");h.drain();\n  need(h.db.archived&&h.db.writes==1,"archive");confirm.performClick();need(h.queue.isEmpty(),"old_callback");\n  h=new TodayScreen();confirm=open(h,true);need(((TextView)confirm).text.equals("确认恢复活动"),"restore_preview");\n  confirm.performClick();h.drain();need(!h.db.archived&&h.db.writes==1,"restore");\n  h=new TodayScreen();confirm=open(h,false);h.one("archive-cancel").performClick();confirm.performClick();h.drain();\n  need(h.db.writes==0&&h.db.last.terminal,"cancel");\n  h=new TodayScreen();confirm=open(h,false);h.content();confirm.performClick();h.drain();\n  need(h.db.writes==0&&h.db.last.terminal,"detached");\n  h=new TodayScreen();confirm=open(h,false);confirm.performClick();h.content();h.drain();\n  need(h.db.writes==0&&h.db.last.terminal,"queued_detached");\n  h=new TodayScreen();confirm=open(h,false);h.db.external++;confirm.performClick();h.drain();\n  need(h.db.writes==0&&!confirm.isEnabled()&&h.one("archive-cancel").isEnabled()&&!((TextView)h.one("archive-validation")).text.isEmpty(),"stale");\n  confirm.performClick();h.drain();need(h.db.attempts==1,"failure_terminal");\n  h=new TodayScreen();confirm=open(h,false);h.db.fail=true;confirm.performClick();h.drain();\n  need(h.db.writes==0&&h.db.last.terminal&&h.one("archive-cancel").isEnabled(),"late_failure");\n  h=new TodayScreen();View a=new View();h.outer.addView(a);\n  new ArchiveAction(h,10,"Wrong",false,h::content).open(a);h.drain();\n  need(h.db.last.terminal&&h.outer.find("archive-confirm")==null,"stale_title");\n  h=new TodayScreen();a=new View();h.outer.addView(a);h.db.archived=true;\n  new ArchiveAction(h,10,"Same",false,h::content).open(a);h.drain();\n  need(h.db.last.terminal&&h.outer.find("archive-confirm")==null,"stale_state");\n  h=new TodayScreen();a=new View();h.outer.addView(a);\n  ArchiveAction action=new ArchiveAction(h,10,"Same",false,h::content);action.open(a);action.open(a);\n  need(h.queue.size()==1,"open_once");h.content();h.drain();\n  need(h.db.last.terminal&&h.outer.find("archive-confirm")==null,"prepare_detached");\n  h=new TodayScreen();confirm=open(h,false);h.activity.destroyed=true;confirm.performClick();h.drain();need(h.db.writes==0,"destroyed");\n  h=new TodayScreen();a=new View();h.outer.addView(a);a.setEnabled(false);\n  new ArchiveAction(h,10,"Same",false,h::content).open(a);need(h.queue.isEmpty(),"disabled_anchor");\n  System.out.println("ARCHIVE_UI_PASS "+checks+" HOST_WIDGET_DOUBLES_NOT_DEVICE");\n }\n}\n', 'ui-fixtures': {'android/view/View.java': 'package android.view;\nimport java.util.*;\npublic class View {\n public boolean attached,enabled=true;public String description="";\n public List<View> children=new ArrayList<>();\n public interface OnClickListener{void onClick(View v);}\n public interface OnAttachStateChangeListener{void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}\n public OnClickListener click;public List<OnAttachStateChangeListener> listeners=new ArrayList<>();\n public boolean isAttachedToWindow(){return attached;}public boolean isEnabled(){return enabled;}\n public void setEnabled(boolean b){enabled=b;}public void setContentDescription(String s){description=s;}\n public void setOnClickListener(OnClickListener l){click=l;}\n public boolean performClick(){if(click==null)return false;click.onClick(this);return true;}\n public void addOnAttachStateChangeListener(OnAttachStateChangeListener l){listeners.add(l);}\n public void attach(boolean yes){attached=yes;for(View v:new ArrayList<>(children))v.attach(yes);for(OnAttachStateChangeListener l:listeners){if(yes)l.onViewAttachedToWindow(this);else l.onViewDetachedFromWindow(this);}}\n public void setPadding(int a,int b,int c,int d){}public void setBackground(Object o){}\n public View find(String s){if(description.equals(s))return this;for(View v:children){View x=v.find(s);if(x!=null)return x;}return null;}\n}', 'android/widget/LinearLayout.java': 'package android.widget;import android.view.View;\npublic class LinearLayout extends View{\n public LinearLayout(Object c){} public static class LayoutParams{public LayoutParams(int a,int b){}public LayoutParams(int a,int b,int c){}}\n public void addView(View v){children.add(v);if(attached)v.attach(true);}\n public void addView(View v,LayoutParams p){addView(v);}\n public void removeAllViews(){for(View v:children)v.attach(false);children.clear();}\n}', 'android/widget/TextView.java': 'package android.widget;import android.view.View;\npublic class TextView extends View{public String text="";public TextView(Object c){}public void setText(String s){text=s;}public CharSequence getText(){return text;}}', 'android/widget/EditText.java': 'package android.widget;public class EditText extends TextView{public EditText(Object c){super(c);}public void setHint(String s){}}', 'android/widget/Button.java': 'package android.widget;public class Button extends TextView{public Button(Object c){super(c);}}', 'android/widget/ScrollView.java': 'package android.widget;public class ScrollView extends LinearLayout{public ScrollView(Object c){super(c);}public void setFillViewport(boolean b){}}', 'android/database/Cursor.java': 'package android.database;import java.util.*;\npublic class Cursor implements AutoCloseable{\n List<Object[]>rows;int i=-1;public Cursor(List<Object[]>r){rows=r;}\n public boolean moveToNext(){return ++i<rows.size();}public boolean moveToFirst(){i=0;return !rows.isEmpty();}\n public long getLong(int c){return((Number)rows.get(i)[c]).longValue();}public String getString(int c){return(String)rows.get(i)[c];}\n public boolean isNull(int c){return rows.get(i)[c]==null;}public void close(){}\n}', 'com/supercubegame/pockettodo/TodayScreen.java': 'package com.supercubegame.pockettodo;\nimport android.view.View;import android.widget.*;import java.util.*;import java.util.concurrent.Callable;import java.util.function.Consumer;\nclass TodayScreen{\n static final int INK=1,MUTED=2,ERROR=3,WHITE=4;\n static class Activity{boolean finishing,destroyed;boolean isFinishing(){return finishing;}boolean isDestroyed(){return destroyed;}}\n Activity activity=new Activity();AppDatabase db=new AppDatabase();LinearLayout outer=new LinearLayout(activity);\n ArrayDeque<Runnable> queue=new ArrayDeque<>();boolean busy;String message;\n TodayScreen(){outer.attach(true);}\n <T>void work(Callable<T>a,Consumer<T>s,Runnable f){\n  if(busy)throw new AssertionError("unexpected concurrent work");busy=true;\n  queue.add(()->{T x;try{x=a.call();}catch(Exception e){busy=false;if(f!=null)f.run();return;}busy=false;s.accept(x);});\n }\n void drain(){int n=0;while(!queue.isEmpty()){if(++n>20)throw new AssertionError("queue cycle");queue.remove().run();}}\n LinearLayout content(){outer.removeAllViews();return outer;}LinearLayout column(){return new LinearLayout(activity);}\n TextView text(String s,int size,int color){TextView v=new TextView(activity);v.setText(s);return v;}\n EditText field(String key,boolean multi){EditText v=new EditText(activity);v.setContentDescription(key);return v;}\n Button button(String s,Runnable r){Button v=new Button(activity);v.setText(s);v.setOnClickListener(w->{if(!busy)r.run();});return v;}\n int dp(int n){return n;}Object shape(int c,int r){return null;}\n void addRow(LinearLayout p,View v){p.addView(v);}void message(String s,boolean e){message=s;}\n View one(String s){View v=outer.find(s);if(v==null)throw new AssertionError("missing "+s);return v;}\n void text(String s,String v){((EditText)one(s)).setText(v);}\n}', 'com/supercubegame/pockettodo/AppDatabase.java': 'package com.supercubegame.pockettodo;\nimport android.database.Cursor;import java.util.*;\nclass AppDatabase{\n TreeMap<Long,String[]>apps=new TreeMap<>();int writes,links,attempts;boolean fail,failRead;\n class SQL{Cursor rawQuery(String q,String[]args){\n  List<Object[]>r=new ArrayList<>();if(q.equals("SELECT MAX(id) FROM applications"))r.add(new Object[]{apps.isEmpty()?null:apps.lastKey()});\n  else if(q.equals("SELECT id,name,package_name FROM applications ORDER BY id")){if(failRead)throw new IllegalStateException("read failed");for(Map.Entry<Long,String[]>e:apps.entrySet())r.add(new Object[]{e.getKey(),e.getValue()[0],e.getValue()[1]});}\n  else throw new AssertionError(q);return new Cursor(r);\n }}\n SQL getReadableDatabase(){return new SQL();}\n void addApplication(long id,String name,String pkg){for(String[]a:apps.values())if(!pkg.isEmpty()&&a[1].equals(pkg))throw new IllegalArgumentException("duplicate");apps.put(id,new String[]{name,pkg});writes++;}\n static class ApplicationActivityPlan implements AutoCloseable{\n  long category,app;String name;boolean terminal;public void close(){terminal=true;}\n  long applicationId(){return app;}String categoryName(){return "Category";}String applicationName(){return name;}\n }\n ApplicationActivityPlan last;\n ApplicationActivityPlan prepareApplicationActivity(long c,long a){ApplicationActivityPlan p=new ApplicationActivityPlan();p.category=c;p.app=a;p.name=apps.get(a)[0];last=p;return p;}\n long confirmApplicationActivity(ApplicationActivityPlan p,String title){attempts++;if(p.terminal)throw new IllegalStateException();p.close();if(fail)throw new IllegalStateException("late");links++;writes++;return links;}\n}'}, 'backend-mutants': [('terminal=true;before=null;', ';', 'cancel'), ('if(!Arrays.equals(plan.before,noteDeletionState(db)))', 'if(false)', 'stale_same'), ('plan.session!=restoreSession', 'false', 'session'), ('connection!=plan.connection||!connection.isOpen()', '!connection.isOpen()', 'connection'), ('connection!=plan.connection||!connection.isOpen()', 'connection!=plan.connection', 'closed'), ('||!Arrays.equals(expected,noteDeletionState(db))', '||false', 'readback'), ('if(plan.archived==plan.target)return false;', 'if(false)return false;', 'same_result')], 'ui-mutants': [('@Override public void onViewDetachedFromWindow(android.view.View v){close();}', '@Override public void onViewDetachedFromWindow(android.view.View v){}', 'detached'), ('||!title.equals(p.title())', '', 'stale_title'), ('||p.wasArchived()!=archived', '', 'stale_state')]}
    extract=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{
 public static void main(String[]a)throws Exception{
  JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
  try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
   JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
   CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
   String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();
   Set<String>w=new HashSet<>(Arrays.asList(a[2].split(",")));StringBuilder out=new StringBuilder();
   for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers()){
    String n=m instanceof ClassTree?((ClassTree)m).getSimpleName().toString():m instanceof MethodTree?((MethodTree)m).getName().toString():"";
    if(w.remove(n))out.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");
   }
   if(!w.isEmpty())throw new AssertionError("missing archive API "+w);Files.writeString(Path.of(a[1]),out.toString());
  }
 }
}'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"Extract.java").write_text(extract)
        (p/"Compile.java").write_text('import javax.tools.*;class Compile{public static void main(String[]a){System.exit(ToolProvider.getSystemJavaCompiler().run(null,null,null,a));}}')
        def members(file,names):
            result=subprocess.run(["java",str(p/"Extract.java"),str(ROOT/"src/main/java/com/supercubegame/pockettodo"/file),str(p/"members"),names],capture_output=True,text=True,timeout=30)
            assert result.returncode==0,(result.stdout,result.stderr)
            return (p/"members").read_text()
        backend=members("AppDatabase.java","ActivityArchivePlan,prepareActivityArchive,confirmActivityArchive,activityArchiveExpected")
        ui=members("ActivitiesScreen.java","ArchiveAction")
        def execute(code,kind):
            target=p/kind;target.mkdir(exist_ok=True)
            if kind=="BACKEND":
                files={"AppDatabase.java":assets["prelude"]+code+"\n}\n","Test.java":assets["backend-test"]}
                entry="Test"
            else:
                files=dict(assets["ui-fixtures"])
                files["com/supercubegame/pockettodo/AppDatabase.java"]=assets["ui-db"]
                files["com/supercubegame/pockettodo/ArchiveAction.java"]="package com.supercubegame.pockettodo;import android.widget.*;\n"+code.replace("private static final class ArchiveAction","final class ArchiveAction",1)
                files["com/supercubegame/pockettodo/Test.java"]=assets["ui-test"]
                entry="com.supercubegame.pockettodo.Test"
            for name,text in files.items():
                f=target/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
            compiled=subprocess.run(["java",str(p/"Compile.java"),"-d",str(target)]+[str(target/n) for n in files],capture_output=True,text=True,timeout=30)
            assert compiled.returncode==0,("archive host compile",compiled.stdout,compiled.stderr)
            return subprocess.run(["java","-cp",str(target),entry],capture_output=True,text=True,timeout=30)
        for kind,code,count,mutants in [
            ("BACKEND",backend,33,assets["backend-mutants"]),
            ("UI",ui,18,assets["ui-mutants"])
        ]:
            result=execute(code,kind);assert result.returncode==0,(result.stdout,result.stderr)
            prefix="ARCHIVE_CHECK " if kind=="BACKEND" else "ARCHIVE_UI_CHECK "
            labels=[l[len(prefix):] for l in result.stdout.splitlines() if l.startswith(prefix)]
            assert len(labels)==count and len(set(labels))==count,(kind,labels)
            print(result.stdout.strip(),flush=True)
            witness="ARCHIVE_VALID_WITNESS" if kind=="BACKEND" else "ARCHIVE_UI_VALID_WITNESS"
            for old,new,label in mutants:
                assert code.count(old)==1,(kind,"mutation anchor",old)
                result=execute(code.replace(old,new),kind)
                assert result.returncode!=0 and witness in result.stdout and "AssertionError: "+label in result.stderr,(kind,label,result.stdout,result.stderr)
                print("ARCHIVE_MUTANT_REJECTED "+kind+" "+label,flush=True)
        print("ARCHIVE_HOST backend=33 ui=18 witnessed_mutants=10 PASS; actual extracted Java, SQL/widget doubles",flush=True)


if __name__ == "__main__":
    {"selftest": selftest, "android": driver(), "report": report}[sys.argv[1]]()
