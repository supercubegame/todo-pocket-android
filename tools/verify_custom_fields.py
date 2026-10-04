#!/usr/bin/env python3
"""Field stage-one gate: real device SQLite/callbacks, never full release acceptance."""
import ast, copy, hashlib, inspect, json, linecache, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import verify_todo_management as runner
import verify_category_drag as shared
PACKAGE=runner.PACKAGE
SCOPE="FIELD_STAGE1_EIGHT_TYPES_GUARDED_EDITS_NOT_FIELD_NOTE_UI_OR_FULL_RELEASE"
assert hashlib.sha256(Path(shared.__file__).read_bytes()).hexdigest()=="9b1b435b21b630e1230f1e112a794962825665982ceabdbb41cc68583ce3d70d","review changed shared adapter"
TYPES=("TEXT","LONG_TEXT","NUMBER","DATE","SELECT","MULTI_SELECT","LINK","BOOLEAN")
EXPECTED={
 "seed":["backend_fixture"]+[action+"_"+kind for kind in TYPES for action in ("prepare","value","replay","invalid","consumed")]+
 ["cancel_readonly","same_revision_stale_readonly","rename_stable_id","archive_preserves_history","archived_value_readonly",
  "unarchive_preserves_history","late_rollback","failed_plan_consumed","outer_transaction_readonly","missing_activity_readonly","missing_field_readonly","backend_checkpoint"],
 "deleted":["backend_restart","backend_backup","ui_open_readonly"]+[action+"_"+kind for kind in TYPES for action in ("ui_value","ui_replay")]+
 ["ui_cancel_readonly","ui_rename_stable_id","ui_archive_history","ui_checkpoint"],
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
 void seed()throws Exception{
  need(!Files.exists(folder)&&!getTargetContext().getDatabasePath(name()).exists(),"fresh backend");Files.createDirectory(folder);
  try(AppDatabase h=AppDatabase.openSchema3(getTargetContext(),name())){
   h.addCategory(1,"Same");h.addActivity(1,1,0,"Same");h.addActivity(2,1,0,"Same");h.addTodo("keep","Keep");
   for(String type:TYPES){
    String id="field-"+type;
    h.defineField(id,"Same",type,type.contains("SELECT")?Arrays.asList("choice-a","choice-b"):Collections.emptyList());
    h.putField(2,id,good(type));
   }
   h.createFieldNote("linked-note",1,"field-TEXT","Keep");
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
   click("field-new",true);click("field-type-"+type,true);text("field-name","Same");
   if(type.contains("SELECT"))text("field-options","choice-a\nchoice-b");
   click("field-create",true);
   String id;try(Cursor c=h.getReadableDatabase().rawQuery("SELECT id FROM fields WHERE type=?",new String[]{type})){
    need(c.moveToFirst(),"created type "+type);id=c.getString(0);need(!c.moveToNext(),"one type "+type);
   }
   need(h.fieldDefinition(id).name.equals("Same")&&!h.fieldDefinition(id).archived,"created exact definition");
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
  }
  String id;try(Cursor c=h.getReadableDatabase().rawQuery("SELECT id FROM fields WHERE type='TEXT'",null)){need(c.moveToFirst(),"text id");id=c.getString(0);}
  h.createFieldNote("ui-linked",1,id,"Keep");click("field-edit-"+id,true);text("field-value-input","Discard");
  before=state(h);click("field-cancel",true);pass(state(h).equals(before),"ui_cancel_readonly");
  click("field-rename-"+id,true);text("field-name","Renamed UI");before=state(h);click("field-rename-save",true);
  pass(state(h).equals(expectedDefinition(before,id,"name","3:Renamed UI")),"ui_rename_stable_id");
  before=state(h);click("field-archive-"+id,true);click("field-archive-confirm",true);
  pass(state(h).equals(expectedDefinition(before,id,"archived","1:1")),"ui_archive_history");
  save("ui-state",state(h).toString());save("ui-media",media().toString());
  pass(h.fieldNoteIds(1,id).equals(Arrays.asList("ui-linked"))&&h.fieldValue(2,id).isEmpty(),"ui_checkpoint");
 }
 void undone()throws Exception{
  launch();openFields();pass(state(db()).toString().equals(read("ui-state"))&&media().toString().equals(read("ui-media")),"ui_restart");backup(db(),"ui");
 }
'''
def oracle_selftest():
    extract=r'''import javax.tools.*;import com.sun.source.util.*;import com.sun.source.tree.*;import java.nio.file.*;import java.util.*;
class Extract{public static void main(String[]a)throws Exception{
JavaCompiler c=ToolProvider.getSystemJavaCompiler();DiagnosticCollector<JavaFileObject>d=new DiagnosticCollector<>();
try(StandardJavaFileManager f=c.getStandardFileManager(d,null,null)){
JavacTask t=(JavacTask)c.getTask(null,f,d,Arrays.asList("-proc:none"),null,f.getJavaFileObjects(a[0]));
CompilationUnitTree u=t.parse().iterator().next();for(Diagnostic<?>e:d.getDiagnostics())if(e.getKind()==Diagnostic.Kind.ERROR)throw new AssertionError(e.toString());
String s=Files.readString(Path.of(a[0]));SourcePositions p=Trees.instance(t).getSourcePositions();Set<String>w=new HashSet<>(Arrays.asList("need","copy","revision","expectedValue","expectedDefinition"));StringBuilder out=new StringBuilder();
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


for marker in (" static Map<String,List<List<String>>> expected(", " void save(", " void seed(", " @Override public void onCreate"):
    assert shared.JAVA.count(marker)==1,marker
JAVA=(shared.JAVA[:shared.JAVA.index(" static Map<String,List<List<String>>> expected(")]+CASES+
      shared.JAVA[shared.JAVA.index(" void save("):shared.JAVA.index(" void seed(")].replace("category-","fields-").replace("&&target.categoryIds().equals(source.categoryIds())","")+
      shared.JAVA[shared.JAVA.index(" @Override public void onCreate"):].replace('"category-"+nonce','"fields-"+nonce'))
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

def selftest():
    assert not sys.flags.optimize
    assert REQUIRED==EXPECTED and [len(EXPECTED[p]) for p in ("seed","deleted","undone")]==[53,23,2]
    assert len(set(sum(EXPECTED.values(),[])))==78
    rejected=0
    for api in (26,34):
        v,m,l=fixture(api);validate(v,m,l,api,"a"*40,"123","1")
        cases=[]
        for key in v:
            bad=copy.deepcopy(v);del bad[key];cases.append((bad,m,l))
        for key in m:
            bad=copy.deepcopy(m);del bad[key];cases.append((v,bad,l))
        for key,wrong in (("checks",78.0),("checks",True),("release_ready",0),("api",float(api)),
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
    assert callable(driver())
    print("FIELDS_HOST "+json.dumps(dict(status="PASS",positive=2,negative=rejected,device_checks=78,
        scope="HOST_REPORT_AND_ORACLE_NOT_ANDROID",release_ready=False)))

if __name__=="__main__":
    assert not sys.flags.optimize
    {"selftest":selftest,"android":driver(),"report":report}[sys.argv[1]]()
