#!/usr/bin/env python3
"""Field stage-one gate: real device SQLite/callbacks, never full release acceptance."""
import ast, copy, hashlib, inspect, json, linecache, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import verify_todo_management as runner
import verify_category_drag as shared
PACKAGE=runner.PACKAGE
SCOPE="FIELD_STAGE2_GUARDED_NOTE_LINKS_AND_UI_NOT_FULL_RELEASE"
assert hashlib.sha256(Path(shared.__file__).read_bytes()).hexdigest()=="9b1b435b21b630e1230f1e112a794962825665982ceabdbb41cc68583ce3d70d","review changed shared adapter"
TYPES=("TEXT","LONG_TEXT","NUMBER","DATE","SELECT","MULTI_SELECT","LINK","BOOLEAN")
EXPECTED={
 "seed":[action+"_"+kind for kind in TYPES for action in ("create","create_duplicate")]+["create_late_rollback","backend_fixture"]+[action+"_"+kind for kind in TYPES for action in ("prepare","value","replay","invalid","consumed")]+
 ["cancel_readonly","same_revision_stale_readonly","rename_stable_id","archive_preserves_history","archived_value_readonly",
  "unarchive_preserves_history","late_rollback","failed_plan_consumed","outer_transaction_readonly","missing_activity_readonly","missing_field_readonly"]+
 ["session_"+op+"_"+action for op in ("value","rename","archive") for action in ("foreign","owner","reopen","old","consumed","fresh")]+
 ["notes_"+x for x in ("fixture","prepare","create","create_replay","link","link_replay","cross_owner","already_linked","unlink","unlink_replay","wrong_field","cancel","stale","stale_consumed","rollback","failure_consumed","archived","missing","foreign","owner")]+["backend_checkpoint"],
 "deleted":["backend_restart","backend_backup","ui_open_readonly"]+sum(
  [["ui_blank_"+kind]+(["ui_duplicate_options_"+kind] if "SELECT" in kind else [])+
   [action+"_"+kind for action in ("ui_create","ui_create_replay","ui_value","ui_replay","ui_clear")] for kind in TYPES],[])+
 ["ui_cancel_readonly","ui_rename_stable_id","ui_archive_history","ui_restore_history"]+
 ["notes_restart","notes_backup"]+["ui_notes_"+x for x in ("archive_readonly","list_scope","blank","create","create_replay","link","link_replay","unlink_cancel","unlink","unlink_replay","open_identity","body_cancel","body_save","body_reopen","body_restore","checkpoint")]+["ui_checkpoint"],
 "undone":["ui_restart","ui_backup"],
}
REQUIRED=copy.deepcopy(EXPECTED)

CASES=r'''
 static final String[] TYPES={"TEXT","LONG_TEXT","NUMBER","DATE","SELECT","MULTI_SELECT","LINK","BOOLEAN"};
 static Object invoke(Object target,String method,Class<?>[] types,Object...args)throws Exception{
  try{return target.getClass().getMethod(method,types).invoke(target,args);}
  catch(InvocationTargetException e){Throwable t=e.getCause();if(t instanceof Exception)throw(Exception)t;if(t instanceof Error)throw(Error)t;throw new AssertionError(t);}
 }
 Object prepare(AppDatabase h,long activity,String id)throws Exception{
  return invoke(h,"prepareFieldEdit",new Class<?>[]{long.class,String.class},activity,id);
 }
 void values(AppDatabase h,Object plan,List<String> input)throws Exception{
  invoke(h,"confirmFieldValue",new Class<?>[]{plan.getClass(),List.class},plan,input);
 }
 void rename(AppDatabase h,Object plan,String name)throws Exception{
  invoke(h,"confirmFieldRename",new Class<?>[]{plan.getClass(),String.class},plan,name);
 }
 void archive(AppDatabase h,Object plan,boolean flag)throws Exception{
  invoke(h,"confirmFieldArchive",new Class<?>[]{plan.getClass(),boolean.class},plan,flag);
 }
 void readonly(AppDatabase h,Class<? extends Throwable> type,Action action,String label)throws Exception{
  Map<String,List<List<String>>> before=state(h);Throwable failed=null;
  try{action.run();}catch(Throwable t){failed=t;}
  pass(failed!=null&&type.isInstance(failed)&&state(h).equals(before),label);
 }
 static Map<String,List<List<String>>> copy(Map<String,List<List<String>>> before){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> e:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();for(List<String> row:e.getValue())rows.add(new ArrayList<>(row));out.put(e.getKey(),rows);
  }return out;
 }
 static void revision(Map<String,List<List<String>>> out){
  List<List<String>> rows=out.get("revision");int col=rows.get(0).indexOf("value");
  need(rows.size()==2&&col>=0,"oracle revision shape");
  rows.get(1).set(col,"1:"+Math.incrementExact(Long.parseLong(rows.get(1).get(col).substring(2))));
 }
 static Map<String,List<List<String>>> expectedValue(Map<String,List<List<String>>> before,long activity,String field,List<String> input){
  Map<String,List<List<String>>> out=copy(before);List<List<String>> rows=out.get("field_values");
  need(rows.get(0).equals(Arrays.asList("rowid","activity_id","field_id","position","value")),"oracle value schema");
  rows.removeIf(row->row!=rows.get(0)&&row.get(1).equals("1:"+activity)&&row.get(2).equals("3:"+field));
  long next=0;for(int i=1;i<rows.size();i++)next=Math.max(next,Long.parseLong(rows.get(i).get(0).substring(2)));
  int pos=0;for(String value:input)rows.add(new ArrayList<>(Arrays.asList("1:"+(++next),"1:"+activity,"3:"+field,"1:"+(pos++),"3:"+value)));
  revision(out);return out;
 }
 static Map<String,List<List<String>>> expectedDefinition(Map<String,List<List<String>>> before,String field,String column,String value){
  Map<String,List<List<String>>> out=copy(before);List<List<String>> rows=out.get("fields");
  int id=rows.get(0).indexOf("id"),col=rows.get(0).indexOf(column),changed=0;
  need(id>=0&&col>=0,"oracle definition schema");
  for(int i=1;i<rows.size();i++)if(rows.get(i).get(id).equals("3:"+field)){rows.get(i).set(col,value);changed++;}
  need(changed==1,"oracle field identity");revision(out);return out;
 }
 static long nextRow(List<List<String>> rows){
  long last=0;
  if(rows.size()>1){last=Long.MIN_VALUE;for(int i=1;i<rows.size();i++)last=Math.max(last,Long.parseLong(rows.get(i).get(0).substring(2)));}
  return Math.incrementExact(last);
 }
 static Map<String,List<List<String>>> expectedCreate(Map<String,List<List<String>>> before,String id,String name,String type,List<String> options){
  Map<String,List<List<String>>> out=copy(before);
  List<List<String>> definitions=out.get("fields"),choices=out.get("field_options");
  need(definitions.get(0).equals(Arrays.asList("rowid","id","name","type","archived")),"oracle create schema");
  need(choices.get(0).equals(Arrays.asList("rowid","field_id","id","position")),"oracle options schema");
  for(int i=1;i<definitions.size();i++)need(!definitions.get(i).get(1).equals("3:"+id),"oracle fresh identity");
  definitions.add(new ArrayList<>(Arrays.asList("1:"+nextRow(definitions),"3:"+id,"3:"+name,"3:"+type,"1:0")));
  int position=0;
  for(String option:options)choices.add(new ArrayList<>(Arrays.asList("1:"+nextRow(choices),"3:"+id,"3:"+option,"1:"+(position++))));
  revision(out);return out;
 }
 static List<String> good(String type){
  switch(type){
   case "TEXT":return Arrays.asList("Alpha");
   case "LONG_TEXT":return Arrays.asList("Line one\nLine two");
   case "NUMBER":return Arrays.asList("-12.50");
   case "DATE":return Arrays.asList("2026-10-04");
   case "SELECT":return Arrays.asList("choice-b");
   case "MULTI_SELECT":return Arrays.asList("choice-b","choice-a");
   case "LINK":return Arrays.asList("https://example.com/path?q=1");
   case "BOOLEAN":return Arrays.asList("false");
   default:throw new AssertionError(type);
  }
 }
 static List<String> bad(String type){
  switch(type){
   case "TEXT":case "LONG_TEXT":return Arrays.asList("a","b");
   case "NUMBER":return Arrays.asList("NaN");
   case "DATE":return Arrays.asList("2026-02-30");
   case "SELECT":case "MULTI_SELECT":return Arrays.asList("missing-option");
   case "LINK":return Arrays.asList("javascript:alert(1)");
   case "BOOLEAN":return Arrays.asList("yes");
   default:throw new AssertionError(type);
  }
 }
 void sessionChange(AppDatabase h,Object plan,String op,boolean fresh)throws Exception{
  if(op.equals("value"))values(h,plan,Arrays.asList(fresh?"Fresh":"Owner"));
  else if(op.equals("rename"))rename(h,plan,fresh?"Fresh":"Owner");
  else archive(h,plan,!fresh);
 }
 Map<String,List<List<String>>> sessionExpected(Map<String,List<List<String>>> before,String op,boolean fresh){
  if(op.equals("value"))return expectedValue(before,1,"session-field",Arrays.asList(fresh?"Fresh":"Owner"));
  if(op.equals("rename"))return expectedDefinition(before,"session-field","name","3:"+(fresh?"Fresh":"Owner"));
  return expectedDefinition(before,"session-field","archived",fresh?"1:0":"1:1");
 }
 void sessionCases()throws Exception{
  // Separate real database: keep all original restart/backup fixtures intact.
  String sessionName=name().replace(".db","-sessions.db");
  need(!getTargetContext().getDatabasePath(sessionName).exists(),"fresh session database");
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),sessionName)){
   h.addCategory(1,"Same");h.addActivity(1,1,0,"Same");h.addActivity(2,1,0,"Same");
   h.defineField("session-field","Same","TEXT",Collections.emptyList());
   h.defineField("keep-field","Same","TEXT",Collections.emptyList());
   h.putField(1,"session-field",Arrays.asList("Initial"));h.putField(2,"session-field",Arrays.asList("Other owner"));
   h.putField(1,"keep-field",Arrays.asList("Other field"));h.createFieldNote("session-note",1,"session-field","Keep");
   h.addTodo("session-keep","Keep");
   for(String op:Arrays.asList("value","rename","archive")){
    Object owned=prepare(h,1,"session-field");Map<String,List<List<String>>> before=state(h);
    try(AppDatabase foreign=AppDatabase.openSchema3(getTargetContext(),sessionName)){
     need(foreign!=h&&foreign.getReadableDatabase()!=h.getReadableDatabase()&&state(foreign).equals(before),"independent helper same database");
     readonly(foreign,IllegalArgumentException.class,()->sessionChange(foreign,owned,op,false),"session_"+op+"_foreign");
    }
    // A foreign refusal must not consume the owner's valid plan.
    sessionChange(h,owned,op,false);pass(state(h).equals(sessionExpected(before,op,false)),"session_"+op+"_owner");
    Object old=prepare(h,1,"session-field");before=state(h);
    android.database.sqlite.SQLiteDatabase connection=h.getReadableDatabase();
    h.close();
    need(!connection.isOpen(),"old connection closed");
    pass(h.getReadableDatabase()!=connection&&state(h).equals(before),"session_"+op+"_reopen");
    readonly(h,IllegalStateException.class,()->sessionChange(h,old,op,true),"session_"+op+"_old");
    readonly(h,IllegalStateException.class,()->sessionChange(h,old,op,true),"session_"+op+"_consumed");
    Object fresh=prepare(h,1,"session-field");before=state(h);
    sessionChange(h,fresh,op,true);pass(state(h).equals(sessionExpected(before,op,true)),"session_"+op+"_fresh");
   }
  }
 }
 void seed()throws Exception{
  need(!Files.exists(folder)&&!getTargetContext().getDatabasePath(name()).exists(),"fresh backend");Files.createDirectory(folder);
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name())){
   h.addCategory(1,"Same");h.addActivity(1,1,0,"Same");h.addActivity(2,1,0,"Same");h.addTodo("keep","Keep");
   for(String type:TYPES){
    String id="field-"+type;
    List<String> options=type.contains("SELECT")?Arrays.asList("choice-a","choice-b"):Collections.emptyList();
    Map<String,List<List<String>>> initial=state(h),wanted=expectedCreate(initial,id,"Same",type,options);
    h.defineField(id,"Same",type,type.contains("SELECT")?Arrays.asList("choice-a","choice-b"):Collections.emptyList());
    pass(state(h).equals(wanted),"create_"+type);
    readonly(h,IllegalArgumentException.class,()->h.defineField(id,"Different",type,options),"create_duplicate_"+type);
    h.putField(2,id,good(type));
    if(type.equals("TEXT"))h.createFieldNote("linked-note",1,"field-TEXT","Keep");
   }
   h.getWritableDatabase().execSQL("CREATE TRIGGER create_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'create_late_fault'); END");
   Map<String,List<List<String>>> creationBefore=state(h);Throwable creationFailure=null;
   try{h.defineField("failed-create","Same","SELECT",Arrays.asList("a","b"));}catch(Throwable t){creationFailure=t;}
   boolean createSentinel=false;for(Throwable t=creationFailure;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("create_late_fault"))createSentinel=true;
   pass(createSentinel&&state(h).equals(creationBefore),"create_late_rollback");
   h.getWritableDatabase().execSQL("DROP TRIGGER create_fault");
   pass(h.count("fields")==8&&h.count("field_notes")==1,"backend_fixture");
   for(String type:TYPES){
    String id="field-"+type;Map<String,List<List<String>>> before=state(h);Object p=prepare(h,1,id);
    pass(state(h).equals(before),"prepare_"+type);
    values(h,p,good(type));pass(state(h).equals(expectedValue(before,1,id,good(type))),"value_"+type);
    readonly(h,IllegalStateException.class,()->values(h,p,good(type)),"replay_"+type);
    Object invalid=prepare(h,1,id);
    readonly(h,IllegalArgumentException.class,()->values(h,invalid,bad(type)),"invalid_"+type);
    readonly(h,IllegalStateException.class,()->values(h,invalid,good(type)),"consumed_"+type);
   }
   Object canceled=prepare(h,1,"field-TEXT");((AutoCloseable)canceled).close();
   readonly(h,IllegalStateException.class,()->values(h,canceled,Arrays.asList("changed")),"cancel_readonly");
   Object stale=prepare(h,1,"field-TEXT");
   h.getWritableDatabase().execSQL("UPDATE field_values SET value='newer' WHERE activity_id=1 AND field_id='field-TEXT'");
   readonly(h,IllegalStateException.class,()->values(h,stale,Arrays.asList("overwrite")),"same_revision_stale_readonly");
   Map<String,List<List<String>>> before=state(h);Object title=prepare(h,1,"field-TEXT");rename(h,title,"Renamed");
   pass(state(h).equals(expectedDefinition(before,"field-TEXT","name","3:Renamed")),"rename_stable_id");
   before=state(h);Object archived=prepare(h,1,"field-TEXT");archive(h,archived,true);
   pass(state(h).equals(expectedDefinition(before,"field-TEXT","archived","1:1")),"archive_preserves_history");
   Object archivedValue=prepare(h,1,"field-TEXT");
   readonly(h,IllegalStateException.class,()->values(h,archivedValue,Arrays.asList("overwrite")),"archived_value_readonly");
   before=state(h);Object restored=prepare(h,1,"field-TEXT");archive(h,restored,false);
   pass(state(h).equals(expectedDefinition(before,"field-TEXT","archived","1:0")),"unarchive_preserves_history");
   Object fault=prepare(h,1,"field-NUMBER");
   h.getWritableDatabase().execSQL("CREATE TRIGGER field_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'field_late_fault'); END");
   before=state(h);Throwable failure=null;
   try{values(h,fault,Arrays.asList("99"));}catch(Throwable t){failure=t;}
   boolean sentinel=false;for(Throwable t=failure;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("field_late_fault"))sentinel=true;
   pass(sentinel&&state(h).equals(before),"late_rollback");
   h.getWritableDatabase().execSQL("DROP TRIGGER field_fault");
   readonly(h,IllegalStateException.class,()->values(h,fault,Arrays.asList("99")),"failed_plan_consumed");
   h.getWritableDatabase().beginTransaction();
   try{readonly(h,IllegalStateException.class,()->prepare(h,1,"field-TEXT"),"outer_transaction_readonly");}
   finally{h.getWritableDatabase().endTransaction();}
   readonly(h,IllegalArgumentException.class,()->prepare(h,99,"field-TEXT"),"missing_activity_readonly");
   readonly(h,IllegalArgumentException.class,()->prepare(h,1,"missing"),"missing_field_readonly");
   Map<String,List<List<String>>> originalFixture=state(h);sessionCases();
   need(state(h).equals(originalFixture),"session tests preserve original backend fixture");
   noteCases();need(state(h).equals(originalFixture),"note tests preserve original backend fixture");
   save("backend-state",state(h).toString());pass(h.fieldNoteIds(1,"field-TEXT").equals(Arrays.asList("linked-note")),"backend_checkpoint");
  }
 }
 void text(String key,String value)throws Exception{ui(()->{View v=one(key,true);need(v instanceof EditText,"editable "+key);((EditText)v).setText(value);need(value.contentEquals(((EditText)v).getText()),"exact input");});}
 void openFields()throws Exception{click("活动",false);click("activity-1",true);click("activity-fields-1",true);}
 void deleted()throws Exception{
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name())){
   pass(state(h).toString().equals(read("backend-state")),"backend_restart");backup(h,"backend");
  }
  launch();AppDatabase h=db();need(h.count("categories")==0&&h.count("fields")==0,"fresh UI");
  h.addCategory(1,"Same");h.addActivity(1,1,0,"Same");h.addActivity(2,1,0,"Same");
  Map<String,List<List<String>>> before=state(h);openFields();
  pass(state(h).equals(before),"ui_open_readonly");
  for(String type:TYPES){
   click("field-new",true);before=state(h);click("field-create",true);
   boolean[] blank={false};ui(()->blank[0]=((TextView)one("field-validation",true)).getText().length()>0);
   pass(blank[0]&&state(h).equals(before),"ui_blank_"+type);
   click("field-type-"+type,true);text("field-name","Same");
   if(type.contains("SELECT")){
    text("field-options","choice-a\nchoice-a");before=state(h);click("field-create",true);
    boolean[] visible={false};ui(()->visible[0]=((TextView)one("field-validation",true)).getText().length()>0);
    pass(visible[0]&&state(h).equals(before),"ui_duplicate_options_"+type);
   }
   if(type.contains("SELECT"))text("field-options","choice-a\nchoice-b");
   before=state(h);final View[] createButton={null};
   ui(()->{createButton[0]=one("field-create",true);need(createButton[0].isEnabled()&&createButton[0].performClick(),"create first callback");createButton[0].performClick();});ready();
   String id;try(Cursor c=h.getReadableDatabase().rawQuery("SELECT id FROM fields WHERE type=?",new String[]{type})){
    need(c.moveToFirst(),"created type "+type);id=c.getString(0);need(!c.moveToNext(),"one type "+type);
   }
   need(h.fieldDefinition(id).name.equals("Same")&&!h.fieldDefinition(id).archived,"created exact definition");
   // Only the opaque new UUID is discovered after saving. Name/type/options,
   // rowids/revision and all unrelated cells come from the frozen input state.
   need(id.startsWith("field-")&&UUID.fromString(id.substring(6)).toString().equals(id.substring(6)),"canonical UI field UUID");
   pass(state(h).equals(expectedCreate(before,id,"Same",type,type.contains("SELECT")?Arrays.asList("choice-a","choice-b"):Collections.emptyList())),"ui_create_"+type);
   before=state(h);ui(()->createButton[0].performClick());ready();pass(state(h).equals(before),"ui_create_replay_"+type);
   if(type.equals("TEXT"))h.createFieldNote("create-keep",2,id,"Keep other owner");
   click("field-edit-"+id,true);text("field-value-input",String.join("\n",bad(type)));
   // Text inputs legitimately contain newlines; use a invalid numeric/date/choice/link/boolean case only.
   if(!type.equals("TEXT")&&!type.equals("LONG_TEXT")){
    before=state(h);click("field-save",true);
    boolean[] visible={false};ui(()->{View v=one("field-validation",true);visible[0]=v instanceof TextView&&((TextView)v).getText().length()>0;});
    need(visible[0]&&state(h).equals(before),"invalid UI is visible and readonly "+type);
   }
   text("field-value-input",String.join("\n",good(type)));before=state(h);
   final View[] old={null};ui(()->{old[0]=one("field-save",true);need(old[0].isEnabled()&&old[0].performClick(),"first save");old[0].performClick();});ready();
   pass(state(h).equals(expectedValue(before,1,id,good(type))),"ui_value_"+type);
   before=state(h);ui(()->old[0].performClick());ready();
   pass(state(h).equals(before),"ui_replay_"+type);
   click("field-edit-"+id,true);text("field-value-input","");before=state(h);click("field-save",true);
   pass(state(h).equals(expectedValue(before,1,id,Collections.emptyList())),"ui_clear_"+type);
   // Restore the old nonempty archive/restart fixture; clearing must not weaken it.
   click("field-edit-"+id,true);text("field-value-input",String.join("\n",good(type)));before=state(h);click("field-save",true);
   need(state(h).equals(expectedValue(before,1,id,good(type))),"restore original value after clear");
  }
  String id;try(Cursor c=h.getReadableDatabase().rawQuery("SELECT id FROM fields WHERE type='TEXT'",null)){need(c.moveToFirst(),"text id");id=c.getString(0);}
  h.createFieldNote("ui-linked",1,id,"Keep");click("field-edit-"+id,true);text("field-value-input","Discard");
  before=state(h);click("field-cancel",true);pass(state(h).equals(before),"ui_cancel_readonly");
  click("field-rename-"+id,true);text("field-name","Renamed UI");before=state(h);click("field-rename-save",true);
  pass(state(h).equals(expectedDefinition(before,id,"name","3:Renamed UI")),"ui_rename_stable_id");
  before=state(h);click("field-archive-"+id,true);click("field-archive-confirm",true);
  pass(state(h).equals(expectedDefinition(before,id,"archived","1:1")),"ui_archive_history");
  before=state(h);click("field-archive-"+id,true);click("field-archive-confirm",true);
  pass(state(h).equals(expectedDefinition(before,id,"archived","1:0")),"ui_restore_history");
  before=state(h);click("field-archive-"+id,true);click("field-archive-confirm",true);
  need(state(h).equals(expectedDefinition(before,id,"archived","1:1")),"restore original archived restart fixture");
  try(AppDatabase notes=AppDatabase.openSchema3(getTargetContext(),name().replace(".db","-notes.db"))){
   pass(state(notes).toString().equals(read("notes-state")),"notes_restart");backup(notes,"notes");
  }
  noteUi(h,id);
  save("ui-state",state(h).toString());save("ui-media",media().toString());
  pass(h.fieldNoteIds(1,id).equals(Arrays.asList("ui-linked"))&&h.fieldValue(2,id).isEmpty(),"ui_checkpoint");
 }
 void undone()throws Exception{
  launch();openFields();pass(state(db()).toString().equals(read("ui-state"))&&media().toString().equals(read("ui-media")),"ui_restart");backup(db(),"ui");
 }
 void noteWrite(AppDatabase h,Object plan,String op,String note,String title)throws Exception{
  if(op.equals("create"))invoke(h,"confirmFieldNoteCreate",new Class<?>[]{plan.getClass(),String.class,String.class},plan,note,title);
  else invoke(h,op.equals("link")?"confirmFieldNoteLink":"confirmFieldNoteUnlink",new Class<?>[]{plan.getClass(),String.class},plan,note);
 }
 static Map<String,List<List<String>>> expectedNote(Map<String,List<List<String>>> before,long owner,String field,String note,String title,String op){
  Map<String,List<List<String>>> out=copy(before);
  List<List<String>> notes=out.get("notes"),links=out.get("field_notes");
  need(notes.get(0).equals(Arrays.asList("rowid","id","activity_id","title")),"oracle note schema");
  need(links.get(0).equals(Arrays.asList("rowid","note_id","field_id")),"oracle link schema");
  if(op.equals("create")){
   for(int i=1;i<notes.size();i++)need(!notes.get(i).get(1).equals("3:"+note),"oracle new note");
   notes.add(new ArrayList<>(Arrays.asList("1:"+nextRow(notes),"3:"+note,"1:"+owner,"3:"+title)));
  }else{
   int matches=0;for(int i=1;i<notes.size();i++)if(notes.get(i).get(1).equals("3:"+note)&&notes.get(i).get(2).equals("1:"+owner))matches++;
   need(matches==1,"oracle note owner");
  }
  if(op.equals("unlink")){
   int removed=0;for(int i=links.size()-1;i>0;i--)if(links.get(i).get(1).equals("3:"+note)&&links.get(i).get(2).equals("3:"+field)){links.remove(i);removed++;}
   need(removed==1,"oracle unlink identity");
  }else{
   need(op.equals("create")||op.equals("link"),"oracle note operation");
   for(int i=1;i<links.size();i++)need(!links.get(i).get(1).equals("3:"+note),"oracle unlinked note");
   links.add(new ArrayList<>(Arrays.asList("1:"+nextRow(links),"3:"+note,"3:"+field)));
  }
  revision(out);return out;
 }
 void noteCases()throws Exception{
  String notesName=name().replace(".db","-notes.db");
  need(!getTargetContext().getDatabasePath(notesName).exists(),"fresh notes database");
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),notesName)){
   h.addCategory(1,"Same");h.addActivity(1,1,0,"Same");h.addActivity(2,1,0,"Same");
   h.defineField("notes-field","Same","TEXT",Collections.emptyList());h.defineField("notes-other","Same","TEXT",Collections.emptyList());
   h.createNote("plain",1,"Same");h.createNote("foreign",2,"Same");
   h.createFieldNote("keep-link",1,"notes-other","Same");h.createFieldNote("foreign-link",2,"notes-field","Same");
   h.saveNote("plain",Arrays.asList(com.supercubegame.pockettodo.NoteDocument.Block.text("text","Keep body",true)));
   h.putField(1,"notes-field",Arrays.asList("Keep value"));h.addTodo("notes-keep","Keep");
   pass(h.fieldNoteIds(1,"notes-field").isEmpty()&&h.fieldNoteIds(2,"notes-field").equals(Arrays.asList("foreign-link"))&&h.noteBlocks("plain").size()==1,"notes_fixture");
   Map<String,List<List<String>>> before=state(h);Object create=prepare(h,1,"notes-field");
   pass(state(h).equals(before),"notes_prepare");
   noteWrite(h,create,"create","created","Same");pass(state(h).equals(expectedNote(before,1,"notes-field","created","Same","create")),"notes_create");
   readonly(h,IllegalStateException.class,()->noteWrite(h,create,"create","again","Same"),"notes_create_replay");
   Object link=prepare(h,1,"notes-field");before=state(h);noteWrite(h,link,"link","plain",null);
   pass(state(h).equals(expectedNote(before,1,"notes-field","plain",null,"link")),"notes_link");
   readonly(h,IllegalStateException.class,()->noteWrite(h,link,"link","plain",null),"notes_link_replay");
   Object cross=prepare(h,1,"notes-field");
   readonly(h,IllegalArgumentException.class,()->noteWrite(h,cross,"link","foreign",null),"notes_cross_owner");
   Object occupied=prepare(h,1,"notes-field");
   readonly(h,IllegalStateException.class,()->noteWrite(h,occupied,"link","keep-link",null),"notes_already_linked");
   Object unlink=prepare(h,1,"notes-field");before=state(h);noteWrite(h,unlink,"unlink","plain",null);
   pass(state(h).equals(expectedNote(before,1,"notes-field","plain",null,"unlink")),"notes_unlink");
   readonly(h,IllegalStateException.class,()->noteWrite(h,unlink,"unlink","plain",null),"notes_unlink_replay");
   Object wrong=prepare(h,1,"notes-field");
   readonly(h,IllegalStateException.class,()->noteWrite(h,wrong,"unlink","keep-link",null),"notes_wrong_field");
   Object canceled=prepare(h,1,"notes-field");((AutoCloseable)canceled).close();
   readonly(h,IllegalStateException.class,()->noteWrite(h,canceled,"link","plain",null),"notes_cancel");
   Object stale=prepare(h,1,"notes-field");h.getWritableDatabase().execSQL("UPDATE notes SET title='Changed without revision' WHERE id='plain'");
   readonly(h,IllegalStateException.class,()->noteWrite(h,stale,"link","plain",null),"notes_stale");
   readonly(h,IllegalStateException.class,()->noteWrite(h,stale,"link","plain",null),"notes_stale_consumed");
   Object failed=prepare(h,1,"notes-field");before=state(h);
   h.getWritableDatabase().execSQL("CREATE TRIGGER notes_fault BEFORE UPDATE OF value ON revision BEGIN SELECT RAISE(ABORT,'notes_late_fault'); END");
   Throwable failure=null;try{noteWrite(h,failed,"create","rollback-note","Same");}catch(Throwable t){failure=t;}
   boolean sentinel=false;for(Throwable t=failure;t!=null;t=t.getCause())if(String.valueOf(t.getMessage()).contains("notes_late_fault"))sentinel=true;
   pass(sentinel&&state(h).equals(before),"notes_rollback");h.getWritableDatabase().execSQL("DROP TRIGGER notes_fault");
   readonly(h,IllegalStateException.class,()->noteWrite(h,failed,"create","rollback-note","Same"),"notes_failure_consumed");
   h.archiveField("notes-field",true);Object archived=prepare(h,1,"notes-field");
   readonly(h,IllegalStateException.class,()->noteWrite(h,archived,"link","plain",null),"notes_archived");h.archiveField("notes-field",false);
   Object missing=prepare(h,1,"notes-field");
   readonly(h,IllegalArgumentException.class,()->noteWrite(h,missing,"link","missing-note",null),"notes_missing");
   Object owned=prepare(h,1,"notes-field");before=state(h);
   try(AppDatabase foreign=AppDatabase.openSchema3(getTargetContext(),notesName)){
    need(foreign.getReadableDatabase()!=h.getReadableDatabase()&&state(foreign).equals(before),"notes independent helper witness");
    readonly(foreign,IllegalArgumentException.class,()->noteWrite(foreign,owned,"link","plain",null),"notes_foreign");
   }
   noteWrite(h,owned,"link","plain",null);pass(state(h).equals(expectedNote(before,1,"notes-field","plain",null,"link")),"notes_owner");
   save("notes-state",state(h).toString());
  }
 }
 void noteUi(AppDatabase h,String field)throws Exception{
  Map<String,List<List<String>>> before=state(h);click("field-notes-"+field,true);
  ui(()->{need(one("field-note-ui-linked",true)!=null,"archived history visible");need(!one("field-note-new",true).isEnabled()&&!one("field-note-link",true).isEnabled(),"archived additions disabled");});
  pass(state(h).equals(before),"ui_notes_archive_readonly");click("field-notes-back",true);
  click("field-archive-"+field,true);click("field-archive-confirm",true);
  h.createNote("ui-plain",1,"Same");h.createNote("ui-foreign",2,"Same");
  h.saveNote("ui-plain",Arrays.asList(com.supercubegame.pockettodo.NoteDocument.Block.text("plain-text","Keep linked content",false)));
  before=state(h);click("field-notes-"+field,true);
  ui(()->{View root=one("field-notes-page",true);one("field-note-ui-linked",true);need(noteKeyCount(root,"field-note-create-keep")==0,"other owner hidden");});
  pass(state(h).equals(before)&&h.fieldNoteIds(1,field).equals(Arrays.asList("ui-linked")),"ui_notes_list_scope");
  click("field-note-new",true);before=state(h);click("field-note-create",true);
  boolean[] visible={false};ui(()->visible[0]=((TextView)one("field-validation",true)).getText().length()>0);
  pass(visible[0]&&state(h).equals(before),"ui_notes_blank");text("field-note-title","Same");
  final View[] old={null};before=state(h);
  ui(()->{old[0]=one("field-note-create",true);need(old[0].performClick(),"create linked note witness");old[0].performClick();});ready();
  List<String> ids=h.fieldNoteIds(1,field);need(ids.size()==2&&ids.get(0).equals("ui-linked"),"new linked ID");
  String created=ids.get(1);need(UUID.fromString(created).toString().equals(created),"note canonical UUID");
  pass(state(h).equals(expectedNote(before,1,field,created,"Same","create")),"ui_notes_create");
  before=state(h);ui(()->old[0].performClick());ready();pass(state(h).equals(before),"ui_notes_create_replay");
  click("field-note-link",true);before=state(h);
  ui(()->need(noteKeyCount(one("field-notes-page",true),"field-note-candidate-ui-foreign")==0,"foreign candidate hidden"));
  ui(()->{old[0]=one("field-note-candidate-ui-plain",true);need(old[0].performClick(),"link witness");old[0].performClick();});ready();
  pass(state(h).equals(expectedNote(before,1,field,"ui-plain",null,"link")),"ui_notes_link");
  before=state(h);ui(()->old[0].performClick());ready();pass(state(h).equals(before),"ui_notes_link_replay");
  // The linked same-title note has a real, distinct body. Verify actual rendering,
  // then return through the editor callback rather than assuming the activity list.
  before=state(h);click("field-note-ui-plain",true);
  ui(()->{
   need("ui-plain".contentEquals(((TextView)one("note-selected-id",true)).getText()),"linked editor exact identity");
   need("Keep linked content".contentEquals(((TextView)one("note-text-plain-text",true)).getText()),"linked editor exact body");
  });
  need(state(h).equals(before),"linked editor open readonly");
  click("返回活动",false);
  ui(()->{one("field-notes-page",true);one("field-note-ui-plain",true);one("field-note-"+created,true);});
  need(state(h).equals(before),"editor return list readonly");
  click("field-note-unlink-ui-plain",true);before=state(h);click("field-note-cancel",true);
  pass(state(h).equals(before),"ui_notes_unlink_cancel");
  click("field-note-unlink-ui-plain",true);before=state(h);
  ui(()->{old[0]=one("field-note-unlink-confirm",true);need(old[0].performClick(),"unlink witness");old[0].performClick();});ready();
  pass(state(h).equals(expectedNote(before,1,field,"ui-plain",null,"unlink")),"ui_notes_unlink");
  before=state(h);ui(()->old[0].performClick());ready();pass(state(h).equals(before),"ui_notes_unlink_replay");
  before=state(h);click("field-note-"+created,true);
  ui(()->{
   need(created.contentEquals(((TextView)one("note-selected-id",true)).getText()),"exact selected note ID");
   need(noteKeyCount(root(),"note-text-plain-text")==0,"same-title sibling body not shown");
  });
  pass(state(h).equals(before),"ui_notes_open_identity");
  click("返回活动",false);
  ui(()->{one("field-notes-page",true);one("field-note-"+created,true);});
  need(state(h).equals(before),"created editor return readonly");
  noteBodyUi(h,created);
  click("field-note-unlink-"+created,true);before=state(h);click("field-note-unlink-confirm",true);
  need(state(h).equals(expectedNote(before,1,field,created,null,"unlink")),"restore original link fixture using guarded UI");
  click("field-notes-back",true);click("field-archive-"+field,true);click("field-archive-confirm",true);
  pass(h.fieldNoteIds(1,field).equals(Arrays.asList("ui-linked"))&&h.noteBlocks("ui-plain").size()==1,"ui_notes_checkpoint");
 }
 static int noteKeyCount(View root,String key){
  int n=key.contentEquals(root.getContentDescription()==null?"":root.getContentDescription())?1:0;
  if(root instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)root;for(int i=0;i<group.getChildCount();i++)n+=noteKeyCount(group.getChildAt(i),key);}
  return n;
 }
 // Narrow oracle for this one-TEXT-block fixture. Compute from pre-write rows,
 // including delete/reinsert rowid allocation; never learn expected cells from
 // the saved database. Same block IDs in sibling/foreign notes are intentional.
 static Map<String,List<List<String>>> expectedBody(Map<String,List<List<String>>> before,String note,String block,String text){
  Map<String,List<List<String>>> out=copy(before);List<List<String>> rows=out.get("blocks");
  need(rows.get(0).equals(Arrays.asList("rowid","note_id","id","position","kind","text","asset_id","caption","private","original_asset_id")),"body oracle schema");
  List<String> target=null;int count=0;
  for(int i=rows.size()-1;i>0;i--)if(rows.get(i).get(1).equals("3:"+note)){target=rows.remove(i);count++;}
  need(count==1&&target!=null,"body oracle one target");
  need(target.get(2).equals("3:"+block)&&target.get(3).equals("1:0")&&target.get(4).equals("3:TEXT"),"body oracle exact block");
  target.set(0,"1:"+nextRow(rows));target.set(5,"3:"+text);
  rows.add(target);revision(out);return out;
 }
 void bodyDialog(String input,boolean save)throws Exception{
  AccessibilityNodeInfo field=node("文字内容",true);
  need(field.isEditable(),"body dialog editable witness");
  Bundle value=new Bundle();value.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,input);
  need(field.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,value)&&field.refresh()&&input.contentEquals(field.getText()),"body dialog exact input");
  need(node(save?"保存":"取消",false).performAction(AccessibilityNodeInfo.ACTION_CLICK),"body dialog terminal action");
  long end=SystemClock.elapsedRealtime()+10000;
  while(true){
   AccessibilityNodeInfo active=getUiAutomation().getRootInActiveWindow();List<AccessibilityNodeInfo> inputs=new ArrayList<>();
   if(active!=null&&PACKAGE.contentEquals(active.getPackageName()==null?"":active.getPackageName())){
    nodes(active,"文字内容",true,inputs);if(inputs.isEmpty())break;
   }
   need(SystemClock.elapsedRealtime()<end,"body dialog close deadline");SystemClock.sleep(50);
  }
  ready();
 }
 void noteBodyUi(AppDatabase h,String created)throws Exception{
  // Original empty-note and sibling-body-exclusion assertions already ran.
  h.saveNote(created,Arrays.asList(com.supercubegame.pockettodo.NoteDocument.Block.text("plain-text","New linked body",true)));
  h.saveNote("ui-foreign",Arrays.asList(com.supercubegame.pockettodo.NoteDocument.Block.text("plain-text","Foreign body",false)));
  need(h.noteBlocks(created).size()==1&&h.noteBlocks("ui-plain").size()==1&&h.noteBlocks("ui-foreign").size()==1,"body nonempty identity witnesses");
  Map<String,String> images=media();Map<String,List<List<String>>> before=state(h);
  click("field-note-"+created,true);
  ui(()->{
   need(created.contentEquals(((TextView)one("note-selected-id",true)).getText()),"body selected identity");
   need("New linked body".contentEquals(((TextView)one("note-text-plain-text",true)).getText()),"body initial exact text");
  });
  click("note-edit-plain-text",true);bodyDialog("Canceled body",false);
  pass(state(h).equals(before)&&media().equals(images),"ui_notes_body_cancel");
  Map<String,List<List<String>>> wanted=expectedBody(before,created,"plain-text","Saved linked body");
  click("note-edit-plain-text",true);bodyDialog("Saved linked body",true);
  pass(state(h).equals(wanted)&&media().equals(images),"ui_notes_body_save");
  click("返回活动",false);click("field-note-"+created,true);
  ui(()->{
   need(created.contentEquals(((TextView)one("note-selected-id",true)).getText()),"saved body exact owner");
   need("Saved linked body".contentEquals(((TextView)one("note-text-plain-text",true)).getText()),"saved body exact render");
  });
  pass(state(h).equals(wanted)&&media().equals(images),"ui_notes_body_reopen");
  before=state(h);wanted=expectedBody(before,created,"plain-text","New linked body");
  click("note-edit-plain-text",true);bodyDialog("New linked body",true);
  pass(state(h).equals(wanted)&&media().equals(images),"ui_notes_body_restore");
  click("返回活动",false);
  ui(()->{one("field-notes-page",true);one("field-note-"+created,true);});
  need(state(h).equals(wanted),"body return readonly");
 }
'''
def oracle_selftest():
    extract=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();Set<String>w=new HashSet<>(Arrays.asList("need","copy","revision","expectedValue","expectedDefinition","nextRow","expectedCreate","expectedNote"));StringBuilder out=new StringBuilder();
for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers())
if(m instanceof MethodTree&&w.remove(((MethodTree)m).getName().toString()))out.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");
if(!w.isEmpty())throw new AssertionError(w);Files.writeString(Path.of(a[1]),out.toString());}}}'''
    harness=r'''import java.util.*;class Oracle{
__METHODS__
static List<String> r(String...s){return new ArrayList<>(Arrays.asList(s));}
public static void main(String[]a){
Map<String,List<List<String>>> b=new TreeMap<>();
b.put("revision",new ArrayList<>(Arrays.asList(r("rowid","id","value"),r("1:1","1:1","1:9"))));
b.put("field_values",new ArrayList<>(Arrays.asList(r("rowid","activity_id","field_id","position","value"),r("1:3","1:1","3:f","1:0","3:old"),r("1:5","1:1","3:g","1:0","3:sibling"),r("1:8","1:2","3:f","1:0","3:other"))));
b.put("fields",new ArrayList<>(Arrays.asList(r("rowid","id","name","type","archived"),r("1:1","3:f","3:Same","3:TEXT","1:0"),r("1:2","3:g","3:Same","3:TEXT","1:0"))));
b.put("notes",new ArrayList<>(Arrays.asList(r("id"),r("3:keep"))));
need(copy(b).equals(b),"valid_copy");System.out.println("FIELD_ORACLE_VALID_WITNESS");
String frozen=b.toString();Map<String,List<List<String>>> out=expectedValue(b,1,"f",Arrays.asList("new","two"));
need(out.get("field_values").equals(Arrays.asList(r("rowid","activity_id","field_id","position","value"),r("1:5","1:1","3:g","1:0","3:sibling"),r("1:8","1:2","3:f","1:0","3:other"),r("1:9","1:1","3:f","1:0","3:new"),r("1:10","1:1","3:f","1:1","3:two"))),"exact_value_owner_order");
need(out.get("revision").get(1).equals(r("1:1","1:1","1:10")),"exact_revision");
need(b.toString().equals(frozen)&&out.get("fields").equals(b.get("fields"))&&out.get("notes").equals(b.get("notes")),"input_unrelated_preserved");
Map<String,List<List<String>>> renamed=expectedDefinition(b,"f","name","3:Renamed");
need(renamed.get("fields").get(1).equals(r("1:1","3:f","3:Renamed","3:TEXT","1:0"))&&renamed.get("fields").get(2).equals(b.get("fields").get(2)),"exact_definition_identity");
need(expectedDefinition(b,"f","archived","1:1").get("field_values").equals(b.get("field_values")),"archive_keeps_values");
need(expectedValue(b,1,"f",Collections.emptyList()).get("field_values").equals(Arrays.asList(b.get("field_values").get(0),b.get("field_values").get(2),b.get("field_values").get(3))),"clear_keeps_other_owner");
boolean no=false;try{expectedDefinition(b,"missing","name","3:x");}catch(AssertionError e){no=true;}need(no,"missing_identity_rejected");
System.out.println("FIELD_ORACLE_PASS");}}'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"Extract.java").write_text(extract);(p/"TodoInstrumentation.java").write_text(JAVA)
        subprocess.run(["java",str(p/"Extract.java"),str(p/"TodoInstrumentation.java"),str(p/"methods")],check=True,timeout=30)
        methods=(p/"methods").read_text()
        def execute(code):
            (p/"Oracle.java").write_text(harness.replace("__METHODS__",code))
            return subprocess.run(["java",str(p/"Oracle.java")],capture_output=True,text=True,timeout=30)
        good=execute(methods);assert good.returncode==0,(good.stdout,good.stderr);print(good.stdout.strip())
        for old,new,label in (
            ('&&row.get(2).equals("3:"+field)','',"exact_value_owner_order"),
            ('Math.incrementExact(Long.parseLong(rows.get(1).get(col).substring(2)))','Long.parseLong(rows.get(1).get(col).substring(2))',"exact_revision"),
            ('rows.add(new ArrayList<>(row))','rows.add(row)',"input_unrelated_preserved"),
            ('rows.get(i).get(id).equals("3:"+field)','true',"oracle field identity"),
        ):
            assert methods.count(old)==1,(old,methods.count(old))
            code=methods.replace(old,new,1);result=execute(code)
            assert result.returncode==1 and "FIELD_ORACLE_VALID_WITNESS" in result.stdout and "AssertionError: "+label in result.stderr,(label,result.stdout,result.stderr)
        print("FIELD_ORACLE compiled_witnessed_mutants=4 PASS; Java oracle, not Android")
        # Keep the old creation mutation's input bounded to its original AST members.
        creation_oracle_selftest(methods[:methods.index("static Map<String,List<List<String>>> expectedNote")])
        note_oracle_selftest(methods)
def note_oracle_selftest(methods):
    harness=r'''import java.util.*;class NotesOracle{
__METHODS__
static List<String> r(String...s){return new ArrayList<>(Arrays.asList(s));}
static void check(boolean b,String s){need(b,s);System.out.println("NOTE_ORACLE_PASS "+s);}
public static void main(String[]args){
Map<String,List<List<String>>> b=new TreeMap<>();
b.put("revision",new ArrayList<>(Arrays.asList(r("rowid","id","value"),r("1:1","1:1","1:9"))));
b.put("notes",new ArrayList<>(Arrays.asList(r("rowid","id","activity_id","title"),r("1:2","3:plain","1:1","3:Same"),r("1:5","3:keep","1:1","3:Same"),r("1:9","3:foreign","1:2","3:Same"))));
b.put("field_notes",new ArrayList<>(Arrays.asList(r("rowid","note_id","field_id"),r("1:5","3:keep","3:other"),r("1:7","3:foreign","3:f"))));
b.put("blocks",new ArrayList<>(Arrays.asList(r("rowid","note_id","text"),r("1:7","3:plain","3:Keep"))));
check(copy(b).equals(b),"valid_copy");String frozen=b.toString();
Map<String,List<List<String>>> linked=expectedNote(b,1,"f","plain",null,"link");
check(linked.get("field_notes").equals(Arrays.asList(b.get("field_notes").get(0),r("1:5","3:keep","3:other"),r("1:7","3:foreign","3:f"),r("1:8","3:plain","3:f"))),"exact_link");
check(linked.get("notes").equals(b.get("notes"))&&linked.get("blocks").equals(b.get("blocks"))&&b.toString().equals(frozen),"link_preserves_body");
check(linked.get("revision").get(1).equals(r("1:1","1:1","1:10")),"revision");
Map<String,List<List<String>>> created=expectedNote(b,1,"f","new","Same","create");
check(created.get("notes").equals(Arrays.asList(b.get("notes").get(0),r("1:2","3:plain","1:1","3:Same"),r("1:5","3:keep","1:1","3:Same"),r("1:9","3:foreign","1:2","3:Same"),r("1:10","3:new","1:1","3:Same"))),"exact_create_owner");
Map<String,List<List<String>>> unlinked=expectedNote(linked,1,"f","plain",null,"unlink");
check(unlinked.get("field_notes").equals(b.get("field_notes"))&&unlinked.get("notes").equals(b.get("notes"))&&unlinked.get("blocks").equals(b.get("blocks")),"exact_unlink");
boolean refused=false;try{expectedNote(b,1,"f","foreign",null,"link");}catch(AssertionError e){refused=e.getMessage().equals("oracle note owner");}
check(refused,"cross_owner_refused");
check(b.toString().equals(frozen),"input_frozen");
}}'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"NotesOracle.java").write_text(harness.replace("__METHODS__",methods))
        def run(code):
            (p/"NotesOracle.java").write_text(harness.replace("__METHODS__",code))
            # Source launcher compiles each real Java mutant; exact runtime witness
            # prefixes below prevent compile failures from counting as rejection.
            return subprocess.run(["java",str(p/"NotesOracle.java")],capture_output=True,text=True,timeout=30)
        good=run(methods);assert good.returncode==0,(good.stdout,good.stderr)
        lines=good.stdout.splitlines();assert len(lines)==8,lines
        mutants=(
            ('"1:"+nextRow(links),"3:"+note,"3:"+field','"1:"+nextRow(links),"3:"+note,"3:other"',"exact_link"),
            ('"1:"+nextRow(notes),"3:"+note,"1:"+owner','"1:"+nextRow(notes),"3:"+note,"1:2"',"exact_create_owner"),
            ('links.get(i).get(1).equals("3:"+note)&&links.get(i).get(2).equals("3:"+field)','links.get(i).get(2).equals("3:"+field)',"oracle unlink identity"),
            ('&&notes.get(i).get(2).equals("1:"+owner)','',"cross_owner_refused"),
        )
        for old,new,label in mutants:
            assert methods.count(old)==1,(old,methods.count(old))
            result=run(methods.replace(old,new,1))
            stop="exact_unlink" if label=="oracle unlink identity" else label
            assert result.returncode==1 and "AssertionError: "+label in result.stderr,(label,result.stdout,result.stderr)
            assert result.stdout.splitlines()==lines[:lines.index("NOTE_ORACLE_PASS "+stop)]
        print("FIELD_NOTES_ORACLE positive_assertions=8 compiled_witnessed_oracle_mutants=4 PASS; not product or Android")

def creation_oracle_selftest(methods):
    harness=r'''import java.util.*;import java.lang.reflect.*;
class CreateOracle{
__METHODS__
static List<String> r(String...s){return new ArrayList<>(Arrays.asList(s));}
static void check(boolean ok,String label){if(!ok)throw new AssertionError(label);System.out.println("CREATE_CHECK "+label);}
@SuppressWarnings("unchecked")
static Map<String,List<List<String>>> create(Map<String,List<List<String>>> before,String type,List<String> options)throws Exception{
 Method m;
 try{m=CreateOracle.class.getDeclaredMethod("expectedCreate",Map.class,String.class,String.class,String.class,List.class);}
 catch(NoSuchMethodException e){throw new AssertionError("missing_creation_oracle");}
 return (Map<String,List<List<String>>>)m.invoke(null,before,"new-id","Same",type,options);
}
public static void main(String[]args)throws Exception{
 Map<String,List<List<String>>> b=new TreeMap<>();
 b.put("revision",new ArrayList<>(Arrays.asList(r("rowid","id","value"),r("1:1","1:1","1:9"))));
 b.put("fields",new ArrayList<>(Arrays.asList(r("rowid","id","name","type","archived"),r("1:7","3:old","3:Same","3:TEXT","1:0"),r("1:9","3:other","3:Same","3:SELECT","1:0"))));
 b.put("field_options",new ArrayList<>(Arrays.asList(r("rowid","field_id","id","position"),r("1:12","3:other","3:a","1:0"))));
 b.put("field_values",new ArrayList<>(Arrays.asList(r("rowid","activity_id","field_id","position","value"),r("1:2","1:1","3:old","1:0","3:Keep"))));
 b.put("field_notes",new ArrayList<>(Arrays.asList(r("rowid","note_id","field_id"),r("1:4","3:note","3:old"))));
 b.put("notes",new ArrayList<>(Arrays.asList(r("rowid","id","activity_id","title"),r("1:6","3:note","1:1","3:Keep"))));
 check(copy(b).equals(b),"positive_copy");System.out.println("CREATE_ORACLE_WITNESS");
 String frozen=b.toString();
 Map<String,List<List<String>>> got=create(b,"MULTI_SELECT",Arrays.asList("b","a"));
 check(got.get("fields").equals(Arrays.asList(b.get("fields").get(0),b.get("fields").get(1),b.get("fields").get(2),r("1:10","3:new-id","3:Same","3:MULTI_SELECT","1:0"))),"definition_exact");
 check(got.get("field_options").equals(Arrays.asList(b.get("field_options").get(0),b.get("field_options").get(1),r("1:13","3:new-id","3:b","1:0"),r("1:14","3:new-id","3:a","1:1"))),"options_exact");
 check(got.get("revision").get(1).equals(r("1:1","1:1","1:10")),"revision_once");
 check(b.toString().equals(frozen),"input_unchanged");
 for(String table:Arrays.asList("field_values","field_notes","notes"))check(got.get(table).equals(b.get(table)),"preserve_"+table);
 Map<String,List<List<String>>> plain=create(b,"TEXT",Collections.emptyList());
 check(plain.get("field_options").equals(b.get("field_options")),"no_phantom_options");
 Map<String,List<List<String>>> empty=copy(b);empty.get("fields").subList(1,empty.get("fields").size()).clear();empty.get("field_options").subList(1,empty.get("field_options").size()).clear();
 Map<String,List<List<String>>> fresh=create(empty,"SELECT",Arrays.asList("x"));
 check(fresh.get("fields").get(1).get(0).equals("1:1")&&fresh.get("field_options").get(1).equals(r("1:1","3:new-id","3:x","1:0")),"empty_rowids");
 System.out.println("CREATE_ORACLE_PASS");
}}'''
    with tempfile.TemporaryDirectory() as tmp:
        f=Path(tmp)/"CreateOracle.java"
        def execute(code):
            f.write_text(harness.replace("__METHODS__",code))
            return subprocess.run(["java",str(f)],capture_output=True,text=True,timeout=30)
        good=execute(methods);assert good.returncode==0,(good.stdout,good.stderr)
        lines=good.stdout.splitlines();assert lines[-1]=="CREATE_ORACLE_PASS";print(good.stdout,end="")
        for old,new,label in (
            ('"1:"+nextRow(definitions)','"1:1"',"definition_exact"),
            ('"1:"+(position++)','"1:0"',"options_exact"),
            ('"3:"+option','"3:wrong"',"options_exact"),
            ('Math.incrementExact(Long.parseLong(rows.get(1).get(col).substring(2)))','Long.parseLong(rows.get(1).get(col).substring(2))',"revision_once"),
            ('revision(out);return out;\n }\n','out.get("field_notes").clear();revision(out);return out;\n }\n',"preserve_field_notes"),
        ):
            # The final mutant targets only the end of expectedCreate.
            count=methods.count(old)
            if label=="preserve_field_notes":
                assert count>=1;at=methods.index("static Map<String,List<List<String>>> expectedCreate")
                prefix,body=methods[:at],methods[at:];assert body.count(old)==1;candidate=prefix+body.replace(old,new)
            else:
                assert count==1,(old,count);candidate=methods.replace(old,new)
            result=execute(candidate)
            target=lines.index("CREATE_CHECK "+label)
            assert result.returncode==1 and "AssertionError: "+label in result.stderr,(label,result.stdout,result.stderr)
            assert result.stdout.splitlines()==lines[:target] and "CREATE_ORACLE_WITNESS" in result.stdout
            print("CREATE_ORACLE_COMPILED_WITNESSED_MUTANT "+label)
        print("CREATE_ORACLE mutations=5 PASS; fixed expected cells, not Android")


def session_selftest():
    # Parse current product members, not a copied implementation. This model
    # isolates owner/session/connection gates; tx/SQLite are explicit doubles.
    extract=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class ExtractSession{public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();Set<String>w=new HashSet<>(Arrays.asList("FieldEditPlan","fieldEditAttempt","validName"));StringBuilder out=new StringBuilder();
for(Tree type:u.getTypeDecls())if(type instanceof ClassTree&&((ClassTree)type).getSimpleName().contentEquals("AppDatabase"))for(Tree m:((ClassTree)type).getMembers()){
String name=m instanceof MethodTree?((MethodTree)m).getName().toString():m instanceof ClassTree?((ClassTree)m).getSimpleName().toString():"";
if(w.remove(name))out.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");
}
if(!w.isEmpty())throw new AssertionError(w);Files.writeString(Path.of(a[1]),out.toString());}}}'''
    harness=r'''import java.util.*;
class SessionHarness {
 static String fixtureName(String base){return __NAME_EXPRESSION__;}
 static void ok(boolean b,String s){if(!b)throw new AssertionError(s);System.out.println("SESSION_PASS "+s);}
 static void refuses(Class<? extends Throwable> kind,Runnable r,String label){
  Throwable failure=null;try{r.run();}catch(Throwable t){failure=t;}ok(failure!=null&&kind.isInstance(failure),label);
 }
 static AppDatabase.FieldEditPlan plan(AppDatabase h){return new AppDatabase.FieldEditPlan(h,h.connection,1,new CustomFields.Definition(),Arrays.asList("kept"),h.state.clone());}
 static void write(AppDatabase h,AppDatabase.FieldEditPlan p){h.fieldEditAttempt(p,db->{h.writes++;return null;});}
 public static void main(String[] args){
  if(args.length>0){
   String base="fields-37264008018-1-"+args[0]+".db";
   ok(AppDatabase.validName(base).equals(base),"fixture_valid_parent");
   String actual=fixtureName(base);
   ok(actual.equals("fields-37264008018-1-"+args[0]+"-sessions.db"),"fixture_exact_name");
   ok(AppDatabase.validName(actual).equals(actual),"fixture_product_name");
   return;
  }
  AppDatabase h=new AppDatabase();AppDatabase.FieldEditPlan p=plan(h);write(h,p);
  ok(h.writes==1,"valid_owner");ok(p.terminal&&p.before==null,"successful_cleanup");
  AppDatabase foreign=new AppDatabase();foreign.connection=h.connection;
  AppDatabase.FieldEditPlan owned=plan(h);
  refuses(IllegalArgumentException.class,()->write(foreign,owned),"foreign_owner");
  ok(foreign.writes==0&&!owned.terminal&&owned.before!=null,"foreign_preserves_plan");write(h,owned);ok(h.writes==2,"owner_after_foreign");
  refuses(IllegalArgumentException.class,()->write(h,null),"null_plan");
  AppDatabase.FieldEditPlan closed=plan(h);closed.close();
  ok(closed.terminal&&closed.before==null,"cancel_cleanup");
  refuses(IllegalStateException.class,()->write(h,closed),"closed_plan");
  AppDatabase.FieldEditPlan session=plan(h);h.restoreSession=new Object();
  refuses(IllegalStateException.class,()->write(h,session),"old_session");
  ok(session.terminal&&session.before==null,"session_cleanup");
  AppDatabase.FieldEditPlan connection=plan(h);h.connection=new SQLiteDatabase();
  refuses(IllegalStateException.class,()->write(h,connection),"old_connection");
  ok(connection.terminal&&connection.before==null,"connection_cleanup");
  AppDatabase.FieldEditPlan outer=plan(h);h.connection.outer=true;
  refuses(IllegalStateException.class,()->write(h,outer),"outer_transaction");h.connection.outer=false;
  refuses(IllegalStateException.class,()->write(h,outer),"outer_consumed");
  AppDatabase.FieldEditPlan stale=plan(h);h.state=new byte[]{9};
  refuses(IllegalStateException.class,()->write(h,stale),"same_revision_content");
  ok(stale.terminal&&stale.before==null,"stale_cleanup");
  AppDatabase.FieldEditPlan failed=plan(h);
  refuses(UnsupportedOperationException.class,()->h.fieldEditAttempt(failed,db->{throw new UnsupportedOperationException("sentinel");}),"original_failure");
  ok(failed.terminal&&failed.before==null,"failure_cleanup");
  refuses(IllegalStateException.class,()->write(h,failed),"failure_consumed");
  ok(h.writes==2&&foreign.writes==0,"all_rejections_readonly");
  write(h,plan(h));ok(h.writes==3,"fresh_session_connection");
  System.out.println("SESSION_PASS_COMPLETE");
 }
 static class SQLiteDatabase {boolean outer;boolean isOpen(){return true;}}
 static class CustomFields {static class Definition{}}
 static class AppDatabase {
  interface Work<T>{T run(SQLiteDatabase db);}
  Object restoreSession=new Object();SQLiteDatabase connection=new SQLiteDatabase();byte[] state={1};int writes;
  SQLiteDatabase getWritableDatabase(){return connection;}
  void noteDeletionNoOuterTransaction(SQLiteDatabase db){if(db.outer)throw new IllegalStateException();}
  byte[] noteDeletionState(SQLiteDatabase db){return state.clone();}
  <T>T tx(Work<T> work){return work.run(connection);}
__MEMBERS__
 }
}'''
    product=ROOT/"src/main/java/com/supercubegame/pockettodo/AppDatabase.java"
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"ExtractSession.java").write_text(extract)
        subprocess.run(["java",str(p/"ExtractSession.java"),str(product),str(p/"members")],check=True,timeout=30)
        members=(p/"members").read_text()
        expressions=re.findall(r'  String sessionName=(.+);',CASES)
        assert len(expressions)==1,"one actual device fixture name expression"
        expression=expressions[0].replace("name()","base")
        def execute(code,name_expression=expression,args=()):
            f=p/"SessionHarness.java";f.write_text(harness.replace("__MEMBERS__",code).replace("__NAME_EXPRESSION__",name_expression))
            return subprocess.run(["java",str(f),*args],capture_output=True,text=True,timeout=30)
        for api in ("26","34"):
            named=execute(members,args=(api,))
            assert named.returncode==0,(named.stdout,named.stderr)
            assert named.stdout.splitlines()==["SESSION_PASS fixture_valid_parent","SESSION_PASS fixture_exact_name","SESSION_PASS fixture_product_name"]
        for wrong in ('base+"-sessions"','base','"fields-fixed-sessions.db"'):
            rejected=execute(members,name_expression=wrong,args=("26",))
            assert rejected.returncode==1 and "AssertionError: fixture_exact_name" in rejected.stderr
            assert rejected.stdout.splitlines()==["SESSION_PASS fixture_valid_parent"]
        print("FIELDS_FIXTURE_NAME host_positive=2 compiled_fixture_mutants=3 PASS; actual Java expression and product validator, not Android")
        good=execute(members);assert good.returncode==0,(good.stdout,good.stderr)
        lines=good.stdout.splitlines();assert len(lines)==22 and lines[-1]=="SESSION_PASS_COMPLETE";print(good.stdout,end="")
        mutants=(
            ("plan==null||plan.owner!=this","plan==null","foreign_owner"),
            ("plan.terminal||plan.session!=restoreSession","plan.terminal","old_session"),
            ("connection!=plan.connection||!connection.isOpen()","!connection.isOpen()","old_connection"),
            ("noteDeletionNoOuterTransaction(connection);",";","outer_transaction"),
            ("!Arrays.equals(plan.before,noteDeletionState(db))","false","same_revision_content"),
            ("terminal=true;before=null;","terminal=true;","successful_cleanup"),
        )
        for old,new,label in mutants:
            assert members.count(old)==1,(old,members.count(old))
            result=execute(members.replace(old,new,1))
            assert result.returncode==1 and "AssertionError: "+label in result.stderr,(label,result.stdout,result.stderr)
            assert result.stdout.splitlines()==lines[:lines.index("SESSION_PASS "+label)]
            assert "SESSION_PASS valid_owner" in result.stdout
            print("SESSION_COMPILED_WITNESSED_MUTANT "+label)
        print("FIELDS_SESSION_HOST "+json.dumps(dict(status="PASS",checks=21,compiled_product_mutants=len(mutants),
            product_sha256=hashlib.sha256(product.read_bytes()).hexdigest(),members_sha256=hashlib.sha256(members.encode()).hexdigest(),
            scope="CURRENT_JAVA_PLAN_AND_ATTEMPT_WITH_DB_DOUBLES_NOT_SQLITE_ATOMICITY_OR_CONCURRENCY",
            release_ready=False)))


for marker in (" static Map<String,List<List<String>>> expected(", " void save(", " void seed(", " @Override public void onCreate"):
    assert shared.JAVA.count(marker)==1,marker
JAVA=(shared.JAVA[:shared.JAVA.index(" static Map<String,List<List<String>>> expected(")]+CASES+
      shared.JAVA[shared.JAVA.index(" void save("):shared.JAVA.index(" void seed(")].replace("category-","fields-").replace("&&target.categoryIds().equals(source.categoryIds())","")+
      shared.JAVA[shared.JAVA.index(" @Override public void onCreate"):].replace('"category-"+nonce','"fields-"+nonce'))
_backup_label='suffix.equals("backend")?"backend_backup":"ui_backup"'
assert JAVA.count(_backup_label)==1,"one inherited backup label"
JAVA=JAVA.replace(_backup_label,'suffix+"_backup"')
BACKUP_EXPECTED=r'''
 static Map<String,List<List<String>>> expectedBackup(Map<String,List<List<String>>> before){
  Map<String,List<List<String>>> out=new TreeMap<>();
  for(Map.Entry<String,List<List<String>>> entry:before.entrySet()){
   List<List<String>> rows=new ArrayList<>();
   for(List<String> row:entry.getValue())rows.add(new ArrayList<>(row));
   out.put(entry.getKey(),rows);
  }
  // This fixture writes/deletes blocks. Backup serializes declared columns,
  // preserving row order but not SQLite's undeclared physical rowid gaps.
  // Other tables retain the exact original expectations, including their rowids.
  List<List<String>> rows=out.get("blocks");
  if(rows==null||rows.isEmpty()||!rows.get(0).equals(Arrays.asList(
    "rowid","note_id","id","position","kind","text","asset_id","caption","private","original_asset_id")))
   throw new AssertionError("backup block schema");
  for(int i=1;i<rows.size();i++){
   if(rows.get(i).size()!=10)throw new AssertionError("backup block cells");
   rows.get(i).set(0,"1:"+i);
  }
  return out;
 }
'''
assert JAVA.count("state(target).equals(state(source))")==1
assert JAVA.count('Path zip=folder.resolve(suffix+".zip");source.exportBackup(zip,repo);')==1
JAVA=JAVA.replace("state(target).equals(state(source))","state(target).equals(expectedBackup(before))&&state(source).equals(before)")
JAVA=JAVA.replace('Path zip=folder.resolve(suffix+".zip");source.exportBackup(zip,repo);',
 'Map<String,List<List<String>>> before=state(source);Path zip=folder.resolve(suffix+".zip");source.exportBackup(zip,repo);')
JAVA=JAVA.replace(" void backup(",BACKUP_EXPECTED+" void backup(")
def bind():
    for name in ("parser","validate","fixture","driver","report","report_selftest"):
        s=inspect.getsource(getattr(shared,name))
        s=s.replace("INJECTED_TOUCH_WITH_DETACHED_VIEW_REPLAY","INSTALLED_VIEW_CALLBACKS_NOT_PHYSICAL_TOUCH")
        s=s.replace("category","fields").replace("Category","Fields").replace("CATEGORY","FIELDS")
        if name=="fixture":
            assert s.count("checks=40")==1
            s=s.replace("checks=40","checks="+str(sum(map(len,EXPECTED.values()))))
        if name=="report":
            old='["physical_phone_gestures", "all_lifecycle_stale_duplicate_UI_cases", "referenced_media_fixture", "ordinary_todo_sorting"]'
            assert s.count(old)==1
            s=s.replace(old,'["physical_phone_gestures","field_note_UI","referenced_media_fixture","full_lifecycle","stable_upgrade","schema_migration_not_retested_here"]')
        s=s.replace('"reports/fields-drag-','"reports/custom-fields-')
        filename="<fields-bound-"+name+">"
        linecache.cache[filename]=(len(s),None,s.splitlines(True),filename)
        exec(compile(s,filename,"exec"),globals())
bind()

def backup_selftest():
    """Compile the generated helper, with explicit backup/storage doubles."""
    extract=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();StringBuilder out=new StringBuilder();int count=0;
for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers())
if(m instanceof MethodTree&&Arrays.asList("backup","expectedBackup").contains(((MethodTree)m).getName().toString())){
out.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");count++;}
if(count!=2)throw new AssertionError("backup helper and expected state");Files.writeString(Path.of(a[1]),out.toString());}}}'''
    harness=r'''import java.util.*;import java.nio.file.*;
class BackupCheck{
 Path folder=Path.of("fixture");String nonce="1";List<String>labels=new ArrayList<>();Object getTargetContext(){return this;}
 static final class MediaRepository{MediaRepository(Path p,long n){}}
 static final class AppDatabase implements AutoCloseable{
  static List<String>calls=new ArrayList<>();static boolean corrupt,gapped,changeSource;
  boolean restored,exported;
  static AppDatabase openSchema3(Object c,String n){calls.add("open:"+n);return new AppDatabase();}
  void exportBackup(Path p,MediaRepository m){calls.add("export:"+p);exported=true;}
  void restoreBackup(Path z,Path p,long n,MediaRepository m){calls.add("restore:"+z);restored=true;}
  public void close(){}
 }
 static Map<String,List<List<String>>>state(AppDatabase h){
  Map<String,List<List<String>>> out=new TreeMap<>();
  out.put("blocks",new ArrayList<>(Arrays.asList(
   new ArrayList<>(Arrays.asList("rowid","note_id","id","position","kind","text","asset_id","caption","private","original_asset_id")),
   new ArrayList<>(Arrays.asList("1:1","3:sibling","3:plain-text","1:0","3:TEXT","3:Keep linked content","0:","3:","1:0","0:")),
   new ArrayList<>(Arrays.asList(h.restored||!AppDatabase.gapped?"1:2":"1:3","3:foreign","3:plain-text","1:0","3:TEXT","3:Foreign body","0:","3:","1:0","0:")),
   new ArrayList<>(Arrays.asList(h.restored||!AppDatabase.gapped?"1:3":"1:4","3:target","3:plain-text","1:0","3:TEXT",h.restored&&AppDatabase.corrupt?"3:changed":"3:New linked body","0:","3:","1:1","0:")))));
  out.put("revision",new ArrayList<>(Arrays.asList(new ArrayList<>(Arrays.asList("rowid","id","value")),new ArrayList<>(Arrays.asList("1:1","1:1",h.exported&&AppDatabase.changeSource?"1:10":"1:9")))));
  return out;
 }
 void pass(boolean b,String label){if(!b)throw new AssertionError("backup equality");labels.add(label);}
 __BACKUP__
 public static void main(String[]a)throws Exception{
  BackupCheck h=new BackupCheck();
  h.backup(new AppDatabase(),"backend");h.backup(new AppDatabase(),"ui");
  if(!h.labels.equals(Arrays.asList("backend_backup","ui_backup")))throw new AssertionError("original_backup_labels");
  System.out.println("BACKUP_ORIGINAL_WITNESS");
  h.backup(new AppDatabase(),"notes");
  if(!h.labels.equals(Arrays.asList("backend_backup","ui_backup","notes_backup")))throw new AssertionError("notes_backup_label");
  if(AppDatabase.calls.size()!=9)throw new AssertionError("all_backup_calls");
  for(String suffix:Arrays.asList("backend","ui","notes")){
   if(!AppDatabase.calls.contains("export:fixture/"+suffix+".zip")||
      !AppDatabase.calls.contains("open:restore-fields-1-"+suffix+".db")||
      !AppDatabase.calls.contains("restore:fixture/"+suffix+".zip"))throw new AssertionError("backup_paths");
  }
  AppDatabase.corrupt=true;boolean rejected=false;
  try{h.backup(new AppDatabase(),"notes");}catch(AssertionError e){if(!"backup equality".equals(e.getMessage()))throw e;rejected=true;}
  if(!rejected||h.labels.size()!=3)throw new AssertionError("changed_backup_rejected");
  System.out.println("BACKUP_HELPER positive=3 negative=1 PASS; generated helper with storage doubles");
  AppDatabase.corrupt=false;AppDatabase.gapped=true;
  h.backup(new AppDatabase(),"ui");
  if(h.labels.size()!=4)throw new AssertionError("gapped_backup");
  System.out.println("BACKUP_GAPPED_ROWIDS_PASS");
  Map<String,List<List<String>>> frozen=state(new AppDatabase());String original=frozen.toString();
  Map<String,List<List<String>>> normalized=expectedBackup(frozen);
  if(!original.equals(frozen.toString())||!normalized.get("revision").equals(frozen.get("revision")))
   throw new AssertionError("backup_input_and_unrelated_preserved");
  AppDatabase.changeSource=true;rejected=false;
  try{h.backup(new AppDatabase(),"notes");}catch(AssertionError e){if(!"backup equality".equals(e.getMessage()))throw e;rejected=true;}
  if(!rejected||h.labels.size()!=4)throw new AssertionError("changed_source_rejected");
  System.out.println("BACKUP_EXTENDED positive=4 negative=2 PASS; storage doubles, not Android");
 }
}'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"Extract.java").write_text(extract);(p/"Source.java").write_text(JAVA)
        subprocess.run(["java",str(p/"Extract.java"),str(p/"Source.java"),str(p/"members")],check=True,timeout=30)
        helper=(p/"members").read_text()
        def execute(code):
            (p/"BackupCheck.java").write_text(harness.replace("__BACKUP__",code))
            return subprocess.run(["java",str(p/"BackupCheck.java")],capture_output=True,text=True,timeout=30)
        good=execute(helper);assert good.returncode==0,(good.stdout,good.stderr);print(good.stdout.strip())
        for old,new,label in (
            ('suffix+"_backup"','suffix.equals("backend")?"backend_backup":"ui_backup"',"notes_backup_label"),
            ("state(target).equals(expectedBackup(before))","true","changed_backup_rejected"),
            ('rows.get(i).set(0,"1:"+i);',';',"backup equality"),
            ("state(source).equals(before)","true","changed_source_rejected"),
        ):
            assert helper.count(old)==1
            result=execute(helper.replace(old,new))
            assert result.returncode==1 and "BACKUP_ORIGINAL_WITNESS" in result.stdout and "AssertionError: "+label in result.stderr,(result.stdout,result.stderr)
        print("BACKUP_HELPER compiled_witnessed_mutants=4 PASS; not Android backup acceptance")

def body_oracle_selftest():
    """Actual Java expected-state helper; no Android or product-save claim."""
    extract=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class ExtractBody{public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();Set<String>w=new HashSet<>(Arrays.asList("need","copy","revision","nextRow","expectedBody"));StringBuilder out=new StringBuilder();
for(Tree type:u.getTypeDecls())if(type instanceof ClassTree)for(Tree m:((ClassTree)type).getMembers())
if(m instanceof MethodTree&&w.remove(((MethodTree)m).getName().toString()))out.append(s.substring((int)p.getStartPosition(u,m),(int)p.getEndPosition(u,m))).append("\n");
w.remove("expectedBody");if(!w.isEmpty())throw new AssertionError(w);Files.writeString(Path.of(a[1]),out.toString());}}}'''
    harness=r'''import java.util.*;import java.lang.reflect.*;
class BodyOracle{
__METHODS__
static List<String> r(String...s){return new ArrayList<>(Arrays.asList(s));}
static void check(boolean b,String label){need(b,label);System.out.println("BODY_CHECK "+label);}
@SuppressWarnings("unchecked")
static Map<String,List<List<String>>> call(Map<String,List<List<String>>> b,String note)throws Exception{
 Method m;try{m=BodyOracle.class.getDeclaredMethod("expectedBody",Map.class,String.class,String.class,String.class);}
 catch(NoSuchMethodException e){throw new AssertionError("missing_body_oracle");}
 try{return (Map<String,List<List<String>>>)m.invoke(null,b,note,"shared","Saved text");}
 catch(InvocationTargetException e){if(e.getCause() instanceof Error)throw(Error)e.getCause();throw e;}
}
public static void main(String[]a)throws Exception{
 Map<String,List<List<String>>> b=new TreeMap<>();
 b.put("revision",new ArrayList<>(Arrays.asList(r("rowid","id","value"),r("1:1","1:1","1:9"))));
 b.put("blocks",new ArrayList<>(Arrays.asList(
  r("rowid","note_id","id","position","kind","text","asset_id","caption","private","original_asset_id"),
  r("1:3","3:target","3:shared","1:0","3:TEXT","3:Before","0:","3:","1:1","0:"),
  r("1:7","3:sibling","3:shared","1:0","3:TEXT","3:Sibling","0:","3:","1:0","0:"),
  r("1:11","3:foreign","3:shared","1:0","3:TEXT","3:Foreign","0:","3:","1:0","0:"))));
 b.put("notes",new ArrayList<>(Arrays.asList(r("id","activity_id","title"),r("3:target","1:1","3:Same"),r("3:sibling","1:1","3:Same"),r("3:foreign","1:2","3:Same"))));
 b.put("field_notes",new ArrayList<>(Arrays.asList(r("note_id","field_id"),r("3:target","3:f"))));
 check(copy(b).equals(b),"copy_witness");String frozen=b.toString();
 Map<String,List<List<String>>> out=call(b,"target");
 check(out.get("blocks").equals(Arrays.asList(b.get("blocks").get(0),b.get("blocks").get(2),b.get("blocks").get(3),
  r("1:12","3:target","3:shared","1:0","3:TEXT","3:Saved text","0:","3:","1:1","0:"))),"exact_target_rows");
 check(out.get("notes").equals(b.get("notes"))&&out.get("field_notes").equals(b.get("field_notes")),"unrelated_tables");
 check(out.get("revision").get(1).equals(r("1:1","1:1","1:10")),"one_revision");
 check(b.toString().equals(frozen),"frozen_input");
 boolean missing=false;try{call(b,"absent");}catch(AssertionError e){missing="body oracle one target".equals(e.getMessage());}
 check(missing,"missing_refused");
 Map<String,List<List<String>>> multiple=copy(b);multiple.get("blocks").add(r("1:20","3:target","3:second","1:1","3:TEXT","3:Other","0:","3:","1:0","0:"));
 boolean refused=false;try{call(multiple,"target");}catch(AssertionError e){refused="body oracle one target".equals(e.getMessage());}
 check(refused,"multi_block_fixture_refused");
}}'''
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/"ExtractBody.java").write_text(extract);(p/"Source.java").write_text(JAVA)
        subprocess.run(["java",str(p/"ExtractBody.java"),str(p/"Source.java"),str(p/"methods")],check=True,timeout=30)
        methods=(p/"methods").read_text()
        def execute(code):
            (p/"BodyOracle.java").write_text(harness.replace("__METHODS__",code))
            return subprocess.run(["java",str(p/"BodyOracle.java")],capture_output=True,text=True,timeout=30)
        good=execute(methods);assert good.returncode==0,(good.stdout,good.stderr)
        lines=good.stdout.splitlines();assert len(lines)==7;print(good.stdout,end="")
        for old,new,label in (
            ('target.set(0,"1:"+nextRow(rows));','target.set(0,"1:1");',"exact_target_rows"),
            ('target.set(5,"3:"+text);','target.set(5,"3:wrong");',"exact_target_rows"),
            ('rows.add(target);revision(out);','target.set(8,"1:0");rows.add(target);revision(out);',"exact_target_rows"),
            ('Math.incrementExact(Long.parseLong(rows.get(1).get(col).substring(2)))','Long.parseLong(rows.get(1).get(col).substring(2))',"one_revision"),
        ):
            assert methods.count(old)==1,(old,methods.count(old))
            result=execute(methods.replace(old,new,1))
            assert result.returncode==1 and "AssertionError: "+label in result.stderr,(result.stdout,result.stderr)
            assert result.stdout.splitlines()==lines[:lines.index("BODY_CHECK "+label)]
        print("FIELD_BODY_ORACLE checks=7 compiled_witnessed_mutants=4 PASS; independent expected rows, not Android")

def selftest():
    assert not sys.flags.optimize
    assert REQUIRED==EXPECTED and [len(EXPECTED[p]) for p in ("seed","deleted","undone")]==[108,76,2]
    assert len(set(sum(EXPECTED.values(),[])))==186
    rejected=0
    for api in (26,34):
        v,m,l=fixture(api);validate(v,m,l,api,"a"*40,"123","1")
        cases=[]
        for key in v:
            bad=copy.deepcopy(v);del bad[key];cases.append((bad,m,l))
        for key in m:
            bad=copy.deepcopy(m);del bad[key];cases.append((v,bad,l))
        for key,wrong in (("checks",186.0),("checks",True),("checks",78),("checks",130),("checks",148),("checks",182),("release_ready",0),("api",float(api)),
                          ("commit","d"*40),("run_id","999"),("run_attempt","2"),("apk_sha256","d"*64),
                          ("native_ui","WIDGET_CALLBACKS"),("status","FAIL"),("error","sentinel")):
            bad=copy.deepcopy(v);bad[key]=wrong;cases.append((bad,m,l))
        for phase,labels in EXPECTED.items():
            for label in labels:
                bad=dict(l);bad[phase]=bad[phase].replace("TODO_PASS "+label+"\n","");cases.append((v,m,bad))
        for value,manifest,logs in cases:
            try:validate(value,manifest,logs,api,"a"*40,"123","1")
            except (AssertionError,KeyError,TypeError):rejected+=1
            else:raise AssertionError("invalid field receipt accepted")
    report_selftest()
    oracle_selftest()
    session_selftest()
    backup_selftest()
    body_oracle_selftest()
    assert callable(driver())
    print("FIELDS_HOST "+json.dumps(dict(status="PASS",positive=2,negative=rejected,device_checks=186,
        scope="HOST_REPORT_AND_ORACLE_NOT_ANDROID",release_ready=False)))

if __name__=="__main__":
    assert not sys.flags.optimize
    {"selftest":selftest,"android":driver(),"report":report}[sys.argv[1]]()
