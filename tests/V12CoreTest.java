import java.lang.reflect.*;
import java.time.*;
import java.util.*;
import com.supercubegame.pockettodo.ActivityModel;
import com.supercubegame.pockettodo.Ledger;
import com.supercubegame.pockettodo.CalendarRules;
import com.supercubegame.pockettodo.NoteDocument;

/** New modules use reflection until implemented, so the red gate is a real missing contract. */
public final class V12CoreTest {
    static int checks;
    static Class<?> cls(String n) throws Exception { return Class.forName("com.supercubegame.pockettodo."+n); }
    static Object make(String n) throws Exception { return cls(n).getConstructor().newInstance(); }
    static Object call(Object o,String name,Class<?>[] types,Object... args) throws Exception {
        try { return o.getClass().getMethod(name,types).invoke(o,args); }
        catch(InvocationTargetException e) { if(e.getCause() instanceof Exception) throw (Exception)e.getCause(); throw e; }
    }
    static Object stat(String n,String name,Class<?>[] types,Object... args) throws Exception {
        try { return cls(n).getMethod(name,types).invoke(null,args); }
        catch(InvocationTargetException e) { if(e.getCause() instanceof Exception) throw (Exception)e.getCause(); throw e; }
    }
    static void ok(boolean condition,String name) { if(!condition) throw new AssertionError(name); checks++; System.out.println("PASS "+name); }
    interface Action { void run() throws Exception; }
    static void reject(Action a,String name) throws Exception { boolean failed=false; try{a.run();}catch(IllegalArgumentException|IllegalStateException|ArithmeticException e){failed=true;} ok(failed,name); }
    static long number(Object n) { return ((Number)n).longValue(); }
    static Object add(Object ledger,String id,String batch,long activity,String date,String kind,long cents) throws Exception {
        return call(ledger,"record",new Class<?>[]{String.class,String.class,long.class,LocalDate.class,String.class,long.class},id,batch,activity,LocalDate.parse(date),kind,cents);
    }
    static long sum(Object ledger,long activity,Set<LocalDate> dates,String kind) throws Exception {
        return number(call(ledger,"total",new Class<?>[]{long.class,Set.class,String.class},activity,dates,kind));
    }
    static long money(String text) throws Exception { return number(stat("Ledger","parseCents",new Class<?>[]{String.class},text)); }
    static void ledger() throws Exception {
        Object l=make("Ledger");
        ok(money("15")==1500,"money whole yuan is exact cents");
        ok(money("0.10")==10 && money("20.01")==2001,"money decimal is exact");
        reject(()->money("1.005"),"reject fractional cents");
        reject(()->money("-1"),"reject signed negative amount");
        reject(()->money("NaN"),"reject non-numeric money");
        reject(()->money("1e3"),"reject scientific money notation");
        reject(()->money("92233720368547758.08"),"reject cents overflow");
        add(l,"e1","b1",1,"2026-09-01","EXPENSE",1500); add(l,"e2","b2",1,"2026-09-03","EXPENSE",2000); add(l,"e3","b3",1,"2026-09-08","EXPENSE",4500);
        Set<LocalDate> d=new HashSet<>(Arrays.asList(LocalDate.parse("2026-09-01"),LocalDate.parse("2026-09-03"),LocalDate.parse("2026-09-08"),LocalDate.parse("2026-09-08")));
        ok(sum(l,1,d,"EXPENSE")==8000,"selected nonconsecutive dates total 80 yuan without duplication");
        add(l,"e4","b4",2,"2026-09-01","EXPENSE",200); add(l,"e5","b5",2,"2026-09-03","EXPENSE",500);
        ok(sum(l,0,d,"EXPENSE")==8700,"all activities aggregate 87 yuan");
        ok(sum(l,1,d,"EXPENSE")==8000,"activity filter excludes other activity");
        add(l,"p1","bp",1,"2026-09-08","PLANNED",9900);
        ok(sum(l,1,d,"EXPENSE")==8000 && sum(l,1,d,"PLANNED")==9900,"planned money isolated from actual");
        add(l,"r1","br",1,"2026-09-08","REFUND",500);
        ok(sum(l,0,d,"NET_EXPENSE")==8200,"refund reduces net but not gross expense");
        add(l,"i1","bi",1,"2026-09-08","INCOME",1000);
        ok(sum(l,0,d,"NET_CASH")==-7200,"net cash equals income plus refunds minus expense");
        add(l,"e1","b1",1,"2026-09-01","EXPENSE",1500);
        ok(sum(l,0,d,"EXPENSE")==8700,"same entry replay is idempotent");
        reject(()->add(l,"e1","b1",1,"2026-09-01","EXPENSE",2500),"conflicting replay cannot overwrite existing entry");
        ok(sum(l,0,d,"EXPENSE")==8700,"conflict leaves ledger unchanged");
        add(l,"e6","b6",1,"2026-09-01","EXPENSE",100);
        ok(sum(l,1,Set.of(LocalDate.parse("2026-09-01")),"EXPENSE")==1600,"multiple actual entries same day remain distinct");
        ok(sum(l,0,Collections.emptySet(),"EXPENSE")==0,"empty date selection returns zero not all time");
        reject(()->add(l,"bad","x",1,"2026-09-01","EXPENSE",-1),"reject negative expense row");
        reject(()->add(l,"bad","x",0,"2026-09-01","EXPENSE",1),"reject unassigned activity");
        reject(()->add(l,"bad","x",1,"2026-09-01","OTHER",1),"reject unknown ledger type");
        ok(sum(l,0,d,"EXPENSE")==8800,"invalid records cannot mutate totals");
        Object overflow=make("Ledger"); add(overflow,"max","m",1,"2026-09-01","EXPENSE",Long.MAX_VALUE); add(overflow,"one","n",1,"2026-09-01","EXPENSE",1);
        reject(()->sum(overflow,1,d,"EXPENSE"),"aggregation overflow fails explicitly");
    }
    static void calendar() throws Exception {
        Class<?>[] sig={LocalDate.class,LocalDate.class,Set.class};
        Set<DayOfWeek> weekdays=Set.of(DayOfWeek.MONDAY,DayOfWeek.WEDNESDAY);
        @SuppressWarnings("unchecked") List<LocalDate> dates=(List<LocalDate>)stat("CalendarRules","scheduled",sig,LocalDate.parse("2026-09-01"),LocalDate.parse("2026-09-08"),weekdays);
        ok(dates.equals(List.of(LocalDate.parse("2026-09-02"),LocalDate.parse("2026-09-07"))),"weekday schedule includes correct dates");
        @SuppressWarnings("unchecked") List<LocalDate> leap=(List<LocalDate>)stat("CalendarRules","scheduled",sig,LocalDate.parse("2028-02-28"),LocalDate.parse("2028-03-01"),EnumSet.allOf(DayOfWeek.class));
        ok(leap.size()==3 && leap.get(1).getDayOfMonth()==29,"leap day preserved across months");
        reject(()->stat("CalendarRules","scheduled",sig,LocalDate.parse("2026-09-08"),LocalDate.parse("2026-09-01"),weekdays),"reversed date range rejected");
        Object book=make("CalendarRules"); Class<?>[] mark={long.class,LocalDate.class,String.class}; LocalDate date=LocalDate.parse("2026-09-21");
        call(book,"mark",mark,1L,date,"DONE"); call(book,"mark",mark,1L,date,"DONE");
        ok(number(call(book,"completedCount",new Class<?>[]{long.class},1L))==1,"repeat check-in does not inflate count");
        call(book,"mark",mark,2L,date,"SKIPPED");
        ok(number(call(book,"completedCount",new Class<?>[]{long.class},2L))==0,"skipped is not completed");
        ok(call(book,"status",new Class<?>[]{long.class,LocalDate.class},1L,date.plusDays(1)).equals("UNRECORDED"),"new day unrecorded without destroying history");
        reject(()->call(book,"mark",mark,1L,date,"MAYBE"),"unknown check-in status rejected");
        ok(number(call(book,"completedCount",new Class<?>[]{long.class},1L))==1,"invalid check-in leaves old state");
    }
    static void notes() throws Exception {
        Object note=make("NoteDocument"); Class<?>[] text={String.class,String.class};
        call(note,"addText",text,"a","第一步：打开淘宝\n详细说明");
        call(note,"addImage",new Class<?>[]{String.class,String.class,String.class},"b","asset-001","入口截图");
        call(note,"addText",text,"c","第二步：领取奖励");
        @SuppressWarnings("unchecked") List<String> ids=(List<String>)call(note,"blockIds",new Class<?>[]{});
        ok(ids.equals(List.of("a","b","c")),"interleaved text image text order preserved");
        call(note,"move",new Class<?>[]{String.class,int.class},"b",2);
        ok(call(note,"blockIds",new Class<?>[]{}).equals(List.of("a","c","b")),"moving image retains block identities");
        ok(ids.equals(List.of("a","b","c")),"previous note snapshot independent");
        reject(()->call(note,"addText",text,"a","duplicate"),"duplicate block identity rejected");
        reject(()->call(note,"move",new Class<?>[]{String.class,int.class},"a",99),"invalid move index rejected");
        ok(call(note,"blockIds",new Class<?>[]{}).equals(List.of("a","c","b")),"failed mutations preserve ordered document");
        for(int i=0;i<120;i++) call(note,"addImage",new Class<?>[]{String.class,String.class,String.class},"img"+i,"asset"+i,"");
        ok(((List<?>)call(note,"blockIds",new Class<?>[]{})).size()==123,"note supports more than 100 image references without fixed small quota");
    }
    static Ledger.Entry entry(String id,long cents) { return new Ledger.Entry(id,1,LocalDate.of(2026,9,1),Ledger.Kind.EXPENSE,cents,""); }
    static void safety() throws Exception {
        Ledger l=new Ledger(); Ledger.Entry a=entry("a",1500),b=entry("b",2000),c=entry("c",4500);
        ok(l.recordBatch("batch",List.of(a,b,c)),"batch inserts every row");
        ok(!l.recordBatch("batch",List.of(a,b,c)) && l.snapshot().size()==3,"identical whole batch retry no-op");
        reject(()->l.recordBatch("other",List.of(entry("new",10),a)),"late conflicting row rejects whole batch");
        ok(l.snapshot().size()==3,"conflicting batch leaves no partial first row");
        reject(()->l.recordBatch("null",Arrays.asList(entry("new",10),null)),"null row rejected without immutable-list null trap");
        ok(l.snapshot().size()==3,"null batch leaves no partial data");
        List<Ledger.Entry> snapshot=l.snapshot(); l.undoBatch("batch");
        ok(l.snapshot().isEmpty() && snapshot.size()==3,"undo removes only own batch and snapshot independent");
        reject(()->l.recordBatch("batch",List.of(a,b,c)),"undone batch cannot silently replay");
        l.recordBatch("fresh",List.of(a,b,c)); l.recordBatch("later",List.of(entry("d",1)));
        reject(()->l.undoBatch("fresh"),"undo cannot remove earlier batch after later write");
        Ledger.Entry changed=entry("a",1600); l.correct(a,changed);
        reject(()->l.correct(a,entry("a",9999)),"stale correction cannot overwrite newer entry");
        ok(l.total(1,Set.of(a.date),"EXPENSE")==8101,"explicit correction recomputes summary");
        ok(l.recordedActualDates(1,Set.of(a.date,a.date.plusDays(1))).size()==1,"unrecorded day not invented as zero confirmation");
        Ledger p=new Ledger(); p.record("p","plan",1,a.date,"PLANNED",100);
        ok(p.recordedActualDates(1,Set.of(a.date)).isEmpty(),"planned row does not mark actual day as recorded");
        reject(()->l.total(1,new HashSet<>(Arrays.asList(a.date,null)),"EXPENSE"),"null selected day rejected explicitly");
        CalendarRules cal=new CalendarRules(); Set<DayOfWeek> due=Set.of(DayOfWeek.MONDAY,DayOfWeek.WEDNESDAY);
        cal.mark(1,LocalDate.of(2026,9,21),"DONE"); cal.mark(1,LocalDate.of(2026,9,23),"DONE");
        ok(cal.streak(1,LocalDate.of(2026,9,21),LocalDate.of(2026,9,23),due)==2,"streak follows scheduled days not intervening rest days");
        cal.mark(1,LocalDate.of(2026,9,23),"SKIPPED");
        ok(cal.streak(1,LocalDate.of(2026,9,21),LocalDate.of(2026,9,23),due)==0,"skip breaks scheduled streak");
        Instant entered=Instant.parse("2026-09-25T12:00:00Z"); cal.put(new CalendarRules.Mark(2,a.date,CalendarRules.Status.DONE,"补记",entered));
        ok(cal.snapshot(2).get(0).recordedAt.equals(entered) && cal.snapshot(2).get(0).date.equals(a.date),"backdate distinct from entry timestamp");
        NoteDocument n=new NoteDocument(); n.add(NoteDocument.Block.text("secret","private ledger",true)); n.addText("public","public guide"); n.addImage("im","asset1","caption"); n.addImage("im2","asset1","same photo");
        ok(n.shareSelection(Set.of("secret","public","im")).size()==2,"private blocks excluded from explicit share selection");
        ok(n.shareSelection(Set.of()).isEmpty(),"empty share selection does not export all content");
        reject(()->n.shareSelection(Set.of("missing")),"missing share block rejected rather than ignored");
        reject(()->n.addImage("escape","../private",""),"asset reference rejects directory traversal");
        n.remove("im"); ok(n.referencedAssets().equals(Set.of("asset1")),"removing one image reference preserves other reference");
        List<NoteDocument.Block> old=n.snapshot(); n.replace(NoteDocument.Block.text("public","edited",false));
        ok(old.get(1).text.equals("public guide") && n.snapshot().get(1).text.equals("edited"),"note edit does not mutate export snapshot");
    }
    static void categories() throws Exception {
        Object m=make("ActivityModel"); Class<?>[] named={long.class,String.class};
        call(m,"addCategory",named,1L,"每日打卡"); call(m,"addCategory",named,2L,"芭芭农场");
        call(m,"addApplication",new Class<?>[]{long.class,String.class,String.class},10L,"淘宝","");
        call(m,"setShortcut",new Class<?>[]{long.class,long.class,boolean.class},1L,10L,true); call(m,"setShortcut",new Class<?>[]{long.class,long.class,boolean.class},2L,10L,true);
        ok(((Set<?>)call(m,"shortcuts",new Class<?>[]{long.class},1L)).contains(10L) && ((Set<?>)call(m,"shortcuts",new Class<?>[]{long.class},2L)).contains(10L),"one application reused in multiple categories");
        call(m,"addActivity",new Class<?>[]{long.class,long.class,long.class,String.class},100L,1L,10L,"90天打卡");
        call(m,"renameCategory",named,1L,"日常活动");
        ok(number(call(m,"categoryOf",new Class<?>[]{long.class},100L))==1L,"category rename preserves activity relationship");
        call(m,"moveCategory",new Class<?>[]{long.class,int.class},2L,0);
        ok(call(m,"categoryIds",new Class<?>[]{}).equals(List.of(2L,1L)),"category reorder uses stable identities");
        reject(()->call(m,"moveCategory",new Class<?>[]{long.class,int.class},1L,99),"invalid category reorder rejected");
        ok(call(m,"categoryIds",new Class<?>[]{}).equals(List.of(2L,1L)),"invalid reorder leaves category order unchanged");
        call(m,"setShortcut",new Class<?>[]{long.class,long.class,boolean.class},1L,10L,false);
        ok(number(call(m,"applicationOf",new Class<?>[]{long.class},100L))==10L,"removing app shortcut does not erase activity");
        reject(()->call(m,"addActivity",new Class<?>[]{long.class,long.class,long.class,String.class},101L,999L,10L,"bad"),"unknown category rejected");
        reject(()->call(m,"addCategory",named,1L,"duplicate"),"duplicate category identity rejected");
        reject(()->call(m,"renameCategory",named,1L,"   "),"blank category rename rejected");
        ok(call(m,"categoryName",new Class<?>[]{long.class},1L).equals("日常活动"),"failed rename retains category name");
        call(m,"archiveActivity",new Class<?>[]{long.class,boolean.class},100L,true);
        ok(((List<?>)call(m,"activeIds",new Class<?>[]{})).isEmpty() && number(call(m,"applicationOf",new Class<?>[]{long.class},100L))==10L,"archive hides activity without destroying relationships");
    }
    static final class CategoryRulesProbe {
 static int checks;static void eq(Object actual,Object want,String m){if(!Objects.equals(actual,want))throw new AssertionError(m+": "+actual+" != "+want);checks++;}interface Act{void run();}static void refuse(Act a,String m){try{a.run();}catch(IllegalStateException|IllegalArgumentException e){checks++;return;}throw new AssertionError(m);}
 static ActivityModel data(){ActivityModel m=new ActivityModel();m.addCategory(7,"同名分类");m.addCategory(8,"同名分类");m.addApplication(10,"同名应用","p.fixture.a");m.addApplication(11,"同名应用","");m.addActivity(9,7,10,"同名活动");m.addActivity(20,7,10,"同名活动");m.addActivity(21,8,10,"同名活动");m.addActivity(22,8,11,"同名活动");m.addActivity(23,7,0,"无应用");m.setShortcut(7,10,true);m.setShortcut(8,10,true);m.setShortcut(8,11,true);m.archiveActivity(9,true);return m;}
 static void run(){ActivityModel m=data(),foreign=data();List<ActivityModel.Item> before=m.snapshot();ActivityModel.CategoryReview p=m.reviewCategory(7,true);eq(p.impact.id,7L,"stable category");eq(p.impact.active,2L,"2 active, not three");eq(p.impact.individual,1L,"already archived");eq(p.impact.otherTargets,1L,"same app elsewhere");eq(p.impact.outgoing,1L,"shortcut entries");eq(p.impact.incomingTargets,1L,"other origins affected");eq(m.categoryIds(),Arrays.asList(7L,8L),"preview no write");p.close();refuse(()->m.confirmCategory(p),"cancel reused");ActivityModel.CategoryReview owned=m.reviewCategory(7,true);refuse(()->foreign.confirmCategory(owned),"foreign owner");eq(m.confirmCategory(owned),true,"confirmed");refuse(()->m.confirmCategory(owned),"double-used");eq(m.categoryIds(),Arrays.asList(8L),"only by category id");eq(m.categoryIds(true),Arrays.asList(7L,8L),"historical order");eq(m.activeIds(),Arrays.asList(21L,22L),"effective category filter");eq(m.visibleInSearch(20,false),false,"default search");eq(m.visibleInSearch(9,true),true,"explicit history");eq(m.shortcutTargets(7,10),Collections.emptyList(),"no hidden origin");eq(m.shortcutTargets(8,10),Arrays.asList(21L),"only eligible cross-category targets");eq(m.shortcutTargets(8,11),Arrays.asList(22L),"same-name other app");eq(m.canUseTemplate(20,8),false,"hidden source template");eq(m.canUseTemplate(21,7),false,"hidden template destination");refuse(()->m.addActivity(101,7,10,"不应新增"),"created in hidden category");eq(m.shortcuts(7),Collections.singleton(10L),"underlying links intact");eq(m.applications().size(),2,"no app archived");eq(m.snapshot(),before,"no child replacements");eq(m.confirmCategory(m.reviewCategory(7,true)),false,"idempotent fresh review");ActivityModel.CategoryReview stale=m.reviewCategory(7,false);m.renameActivity(21,"新标题");refuse(()->m.confirmCategory(stale),"stale review");eq(m.confirmCategory(m.reviewCategory(7,false)),true,"restore");eq(m.activeIds(),Arrays.asList(20L,21L,22L,23L),"must not revive child");eq(m.item(9).archived,true,"raw child flag intact");eq(m.shortcutTargets(8,10),Arrays.asList(20L,21L),"global targets return");eq(m.canUseTemplate(21,7),true,"active source and target");System.out.println("CATEGORY_RULES "+checks+" PASS actual Java in memory; no device or persistence");}
}

    static void fields() throws Exception {
        Object f=make("CustomFields"); Class<?>[] def={String.class,String.class,String.class,List.class}; Class<?>[] put={long.class,String.class,List.class};
        call(f,"define",def,"invite","邀请人数","NUMBER",List.of());
        call(f,"put",put,100L,"invite",List.of("3")); call(f,"rename",new Class<?>[]{String.class,String.class},"invite","需要邀请的人数");
        ok(call(f,"value",new Class<?>[]{long.class,String.class},100L,"invite").equals(List.of("3")),"field rename preserves value and stable note attachment ID");
        reject(()->call(f,"put",put,100L,"invite",List.of("three")),"numeric field rejects non-number");
        ok(call(f,"value",new Class<?>[]{long.class,String.class},100L,"invite").equals(List.of("3")),"invalid field change leaves prior value");
        call(f,"define",def,"tags","条件","MULTI_SELECT",List.of("new-user","purchase"));
        call(f,"put",put,100L,"tags",List.of("new-user","purchase","new-user"));
        ok(((List<?>)call(f,"value",new Class<?>[]{long.class,String.class},100L,"tags")).size()==2,"multi-select deduplicates option identities");
        reject(()->call(f,"put",put,100L,"tags",List.of("unknown")),"unknown option rejected");
        call(f,"define",def,"deadline","截止日期","DATE",List.of());
        reject(()->call(f,"put",put,100L,"deadline",List.of("2026-02-29")),"date field rejects impossible calendar date");
        call(f,"define",def,"url","规则链接","LINK",List.of());
        reject(()->call(f,"put",put,100L,"url",List.of("javascript:alert(1)")),"link field rejects executable URI");
        call(f,"put",put,100L,"url",List.of("https://example.com/rules"));
        ok(((List<?>)call(f,"value",new Class<?>[]{long.class,String.class},100L,"url")).size()==1,"ordinary web link accepted");
        call(f,"archive",new Class<?>[]{String.class,boolean.class},"invite",true);
        ok(call(f,"value",new Class<?>[]{long.class,String.class},100L,"invite").equals(List.of("3")),"field archive retains values for recovery");
        reject(()->call(f,"put",put,100L,"invite",List.of("4")),"archived field prevents silent new writes");
    }
    static Object imageRevision(String current,String original)throws Exception {
        try{return cls("NoteDocument$ImageRevision").getConstructor(String.class,String.class).newInstance(current,original);}
        catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
    }
    static String revisionId(Object value,String field)throws Exception{return(String)value.getClass().getField(field).get(value);}
    static Object derive(Object value,String asset)throws Exception{return call(value,"withDerivative",new Class<?>[]{String.class},asset);}
    static void imageRevisions()throws Exception {
        String a="a".repeat(64),b="b".repeat(64),c="c".repeat(64);
        Object original=imageRevision(a,null);
        ok(revisionId(original,"assetId").equals(a)&&revisionId(original,"originalAssetId").equals(a),"image revision normalizes legacy missing origin to current asset");
        ok(call(original,"backupAssets",new Class<?>[]{}).equals(Set.of(a)),"unmodified image backup references deduplicate");
        Object first=derive(original,b),second=derive(first,c);
        ok(revisionId(first,"assetId").equals(b)&&revisionId(first,"originalAssetId").equals(a),"first derivative retains earliest original");
        ok(revisionId(second,"assetId").equals(c)&&revisionId(second,"originalAssetId").equals(a),"second derivative never promotes prior derivative to original");
        ok(revisionId(original,"assetId").equals(a)&&revisionId(first,"assetId").equals(b),"later image edits leave prior immutable revisions exact");
        ok(call(second,"backupAssets",new Class<?>[]{}).equals(Set.of(a,c)),"backup keeps current and earliest original but not obsolete intermediate");
        ok(call(second,"currentAssets",new Class<?>[]{}).equals(Set.of(c)),"current-only reference projection excludes distinct original");
        Object restored=imageRevision(c,a);
        ok(call(restored,"backupAssets",new Class<?>[]{}).equals(call(second,"backupAssets",new Class<?>[]{})),"explicit restored image pair retains same references");
        ok(revisionId(derive(restored,b),"originalAssetId").equals(a),"editing reconstructed revision keeps original");
        Object other=imageRevision(c,b);
        ok(revisionId(other,"originalAssetId").equals(b)&&revisionId(second,"originalAssetId").equals(a),"identical derived bytes can have different per-block originals");
        Object same=derive(original,a);
        ok(call(same,"backupAssets",new Class<?>[]{}).equals(Set.of(a))&&revisionId(same,"originalAssetId").equals(a),"identical output digest is valid without duplicate asset entries");
        @SuppressWarnings("unchecked") Set<String> backup=(Set<String>)call(second,"backupAssets",new Class<?>[]{});
        boolean frozen=false;try{backup.clear();}catch(UnsupportedOperationException e){frozen=true;}ok(frozen&&backup.equals(Set.of(a,c)),"backup asset set is immutable");
        @SuppressWarnings("unchecked") Set<String> current=(Set<String>)call(second,"currentAssets",new Class<?>[]{});
        frozen=false;try{current.add(a);}catch(UnsupportedOperationException e){frozen=true;}ok(frozen&&current.equals(Set.of(c)),"current asset set cannot acquire original through caller mutation");
        String[] bad={"","../outside","https://example.com/photo","A".repeat(64),"a".repeat(63),"a".repeat(65),"g".repeat(64)};
        for(int i=0;i<bad.length;i++){
            final String id=bad[i];
            reject(()->imageRevision(id,a),"invalid current media digest rejected "+i);
            reject(()->imageRevision(a,id),"invalid original media digest rejected "+i);
            reject(()->derive(second,id),"invalid derivative media digest rejected "+i);
        }
        reject(()->imageRevision(null,a),"null current media digest rejected");
        reject(()->derive(second,null),"null derivative media digest rejected");
        ok(revisionId(second,"assetId").equals(c)&&revisionId(second,"originalAssetId").equals(a),"all invalid revisions leave existing relationship unchanged");
    }
    static Object imageEdit(String note,NoteDocument.Block block,String original)throws Exception {
        try{return cls("NoteDocument$ImageEdit").getConstructor(String.class,NoteDocument.Block.class,String.class).newInstance(note,block,original);}
        catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
    }
    static Object editField(Object edit,String name)throws Exception{return edit.getClass().getField(name).get(edit);}
    static Object editMetadata(Object edit,String caption,boolean privacy)throws Exception{return call(edit,"withMetadata",new Class<?>[]{String.class,boolean.class},caption,privacy);}
    static Object editRevision(Object edit)throws Exception{return call(edit,"revision",new Class<?>[]{});}
    static void imageEdits()throws Exception {
        String a="a".repeat(64),b="b".repeat(64),c="c".repeat(64);
        NoteDocument.Block block=NoteDocument.Block.image("photo",a,"原图说明",true);
        Object draft=imageEdit("second-note",block,null);
        ok(editField(draft,"noteId").equals("second-note")&&editField(draft,"blockId").equals("photo"),"image edit binds stable note and block IDs not titles");
        ok(editField(draft,"caption").equals("原图说明")&&(Boolean)editField(draft,"privateContent"),"image edit captures exact caption and privacy");
        ok(revisionId(editRevision(draft),"assetId").equals(a)&&revisionId(editRevision(draft),"originalAssetId").equals(a),"image edit starts from current asset with legacy origin fallback");
        Object first=derive(draft,b),second=derive(first,c);
        ok(revisionId(editRevision(first),"assetId").equals(b)&&revisionId(editRevision(first),"originalAssetId").equals(a),"image block first edit retains original");
        ok(revisionId(editRevision(second),"assetId").equals(c)&&revisionId(editRevision(second),"originalAssetId").equals(a),"image block second edit retains earliest original");
        ok(editField(second,"noteId").equals("second-note")&&editField(second,"blockId").equals("photo"),"repeated image edits preserve both stable target identities");
        ok(editField(second,"caption").equals("原图说明")&&(Boolean)editField(second,"privateContent"),"derivative replacement retains caption and private flag");
        Object metadata=editMetadata(second,"新说明\n第二行",false);
        ok(editField(metadata,"caption").equals("新说明\n第二行")&&!(Boolean)editField(metadata,"privateContent"),"image metadata edit preserves exact multiline caption and explicit false");
        ok(revisionId(editRevision(metadata),"assetId").equals(c)&&revisionId(editRevision(metadata),"originalAssetId").equals(a),"caption privacy edit never resets current or original image");
        Object privateAgain=editMetadata(metadata,"",true);
        ok(editField(privateAgain,"caption").equals("")&&(Boolean)editField(privateAgain,"privateContent"),"empty caption and explicit private are valid independent values");
        ok(editField(privateAgain,"noteId").equals("second-note")&&editField(privateAgain,"blockId").equals("photo"),"metadata changes cannot retarget another note or block");
        ok(editField(second,"caption").equals("原图说明")&&(Boolean)editField(second,"privateContent"),"metadata edits leave earlier immutable draft unchanged");
        ok(revisionId(editRevision(draft),"assetId").equals(a)&&revisionId(editRevision(first),"assetId").equals(b),"later derivative edits leave earlier immutable drafts unchanged");
        ok(block.assetId.equals(a)&&block.caption.equals("原图说明")&&block.privateContent,"image draft does not modify source block");
        Object restored=imageEdit("second-note",NoteDocument.Block.image("photo",c,"恢复说明",false),a);
        ok(revisionId(editRevision(derive(restored,b)),"originalAssetId").equals(a),"editing restored image block keeps earliest original");
        Object sibling=imageEdit("first-note",NoteDocument.Block.image("photo",c,"另一篇",true),b);
        ok(revisionId(editRevision(sibling),"originalAssetId").equals(b)&&editField(sibling,"noteId").equals("first-note")&&revisionId(editRevision(restored),"originalAssetId").equals(a),"shared current bytes and block ID do not conflate per-note origins");
        Object identical=derive(draft,a);
        ok(call(editRevision(identical),"backupAssets",new Class<?>[]{}).equals(Set.of(a)),"no-op derivative keeps a single original reference");
        ok(call(editRevision(second),"backupAssets",new Class<?>[]{}).equals(Set.of(a,c))&&call(editRevision(second),"currentAssets",new Class<?>[]{}).equals(Set.of(c)),"image draft backup obligation remains separate from current-only projection");
        NoteDocument note=new NoteDocument();note.addText("before","文字");note.add(block);note.addImage("sibling",a,"共享原图");
        List<NoteDocument.Block> snapshot=note.snapshot();derive(draft,b);editMetadata(draft,"未保存",false);
        ok(note.blockIds().equals(List.of("before","photo","sibling"))&&note.snapshot().get(1)==block&&snapshot.get(2)==note.snapshot().get(2),"unsaved edits leave note order target and shared-image sibling untouched");
        ok(!NoteDocument.Block.class.isAssignableFrom(draft.getClass()),"image edit cannot masquerade as a legacy block and silently lose original on save");
        reject(()->imageEdit("n",null,a),"image edit rejects missing source block");
        reject(()->imageEdit("n",NoteDocument.Block.text("text","内容",false),a),"image edit rejects text source");
        reject(()->imageEdit(null,block,a),"image edit rejects missing note identity");
        reject(()->imageEdit("",block,a),"image edit rejects empty note identity");
        reject(()->imageEdit("n",NoteDocument.Block.image("photo","asset-placeholder","",false),null),"image edit rejects non-digest legacy placeholder before persistence");
        reject(()->imageEdit("n",block,"../outside"),"image edit rejects invalid original digest");
        reject(()->editMetadata(second,null,false),"image edit rejects null caption");
        reject(()->derive(second,null),"image edit rejects missing derivative digest");
        reject(()->derive(second,"A".repeat(64)),"image edit rejects noncanonical derivative digest");
        ok(revisionId(editRevision(second),"assetId").equals(c)&&revisionId(editRevision(second),"originalAssetId").equals(a)&&editField(second,"caption").equals("原图说明")&&(Boolean)editField(second,"privateContent"),"all rejected image edits leave relationship and metadata exact");
        ok(Modifier.isFinal(draft.getClass().getModifiers()),"image edit cannot be subclassed into mutable state");
        boolean immutable=true;for(Field f:draft.getClass().getDeclaredFields())if(!Modifier.isStatic(f.getModifiers()))immutable&=Modifier.isFinal(f.getModifiers());
        ok(immutable,"every image edit instance field is final");
    }
    static Object shareBlock(String note,NoteDocument.Block block)throws Exception {
        try{return cls("NoteDocument$ShareBlock").getConstructor(String.class,NoteDocument.Block.class).newInstance(note,block);}
        catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
    }
    @SuppressWarnings("unchecked")
    static List<Object> across(List<Object> blocks,Set<String> selected)throws Exception {
        return (List<Object>)stat("NoteDocument","shareAcrossNotes",new Class<?>[]{List.class,Set.class},blocks,selected);
    }
    static void batchShares()throws Exception {
        NoteDocument.Block first=NoteDocument.Block.text("same","FIRST",false);
        NoteDocument.Block second=NoteDocument.Block.text("same","SECOND",false);
        NoteDocument.Block hidden=NoteDocument.Block.image("secret","unread-private-asset","PRIVATE",true);
        Object a=shareBlock("n1",first),b=shareBlock("n2",second),p=shareBlock("n2",hidden);
        Object image=shareBlock("n2",NoteDocument.Block.image("image","current-asset","CURRENT",false));
        List<Object> input=new ArrayList<>(List.of(a,p,b,image));
        Set<String> selected=new LinkedHashSet<>(List.of("n2/image","n2/same","n1/same","n2/secret"));
        List<Object> result=across(input,selected);
        ok(result.equals(List.of(a,b,image)),"batch share follows source order not checkbox click order");
        ok(result.get(0).getClass().getField("noteId").get(result.get(0)).equals("n1")&&
            result.get(1).getClass().getField("noteId").get(result.get(1)).equals("n2"),
            "batch share same block IDs remain distinct across notes");
        ok(call(a,"key",new Class<?>[]{}).equals("n1/same")&&call(b,"key",new Class<?>[]{}).equals("n2/same"),
            "batch share keys use note and block identities");
        ok(across(input,Set.of("n2/same")).equals(List.of(b)),"batch share unselected note excluded");
        ok(!result.contains(p)&&selected.contains("n2/secret"),"batch share private selected image excluded without mutating selection");
        NoteDocument.Block projected=(NoteDocument.Block)image.getClass().getField("block").get(image);
        ok(projected.assetId.equals("current-asset")&&projected.caption.equals("CURRENT"),
            "batch share retains current image reference and caption only");
        input.clear();selected.clear();
        ok(result.equals(List.of(a,b,image)),"batch share result survives caller collection mutation");
        boolean frozen=false;try{result.clear();}catch(UnsupportedOperationException e){frozen=true;}
        ok(frozen&&result.size()==3,"batch share result cannot be mutated");
        reject(()->across(List.of(a),Set.of()),"batch share empty selection refused not all");
        reject(()->across(List.of(p),Set.of("n2/secret")),"batch share private-only selection refused");
        reject(()->across(List.of(a),Set.of("n1/missing")),"batch share unknown selection refused");
        reject(()->across(List.of(a),Set.of("same")),"batch share bare block identity refused");
        reject(()->across(List.of(a,a),Set.of("n1/same")),"batch share duplicate compound identity refused");
        reject(()->across(List.of(p,p,a),Set.of("n1/same")),"batch share duplicate excluded identity refused");
        reject(()->across(null,Set.of("n1/same")),"batch share null candidates refused");
        reject(()->across(Arrays.asList(a,null),Set.of("n1/same")),"batch share null candidate refused");
        reject(()->across(List.of(a),null),"batch share null selection refused");
        reject(()->across(List.of(a),new HashSet<>(Arrays.asList("n1/same",null))),"batch share null selected key refused");
        reject(()->shareBlock("n",null),"batch share missing block refused");
        reject(()->shareBlock("",first),"batch share empty note ID refused");
        reject(()->shareBlock(null,first),"batch share null note ID refused");
        reject(()->shareBlock("n/1",first),"batch share slash note ID refused to prevent key collision");
        reject(()->shareBlock("n",NoteDocument.Block.text("a/b","x",false)),"batch share slash block ID refused to prevent key collision");
        List<Object> limit=new ArrayList<>();Set<String> keys=new LinkedHashSet<>();
        for(int i=0;i<1000;i++){limit.add(shareBlock("n",NoteDocument.Block.text("b"+i,"x",false)));keys.add("n/b"+i);}
        ok(across(limit,keys).size()==1000,"batch share exact candidate budget accepted without truncation");
        limit.add(shareBlock("n",NoteDocument.Block.text("over","x",false)));
        reject(()->across(limit,keys),"batch share over candidate budget rejects whole request");
        keys.add("n/over");
        reject(()->across(List.of(a),keys),"batch share over selection budget rejects whole request");
        ok(across(List.of(b,a),Set.of("n1/same","n2/same")).equals(List.of(b,a)),
            "batch share retains explicit source note order");
        ok(Modifier.isFinal(a.getClass().getModifiers()),"batch share entry cannot be subclassed");
        boolean immutable=true;for(Field f:a.getClass().getDeclaredFields())if(!Modifier.isStatic(f.getModifiers()))immutable&=Modifier.isFinal(f.getModifiers());
        ok(immutable&&a.getClass().getField("block").get(a)==first,"batch share entry fields and block reference immutable");
    }
    static String summary(List<NoteDocument.Block> blocks)throws Exception {
        return (String)stat("NoteDocument","summary",new Class<?>[]{List.class},blocks);
    }
    static void noteSummaries()throws Exception {
        ok(summary(List.of()).equals("空笔记"),"empty note has explicit summary");
        ok(summary(List.of(NoteDocument.Block.text("a","  原文\n下一行  ",false))).equals("原文\n下一行"),"summary trims edges but preserves original multiline text");
        ok(summary(List.of(NoteDocument.Block.text("a"," \n ",false),NoteDocument.Block.text("b","第二段",false))).equals("第二段"),"summary skips blank text without losing later content");
        ok(summary(List.of(NoteDocument.Block.text("a","PRIVATE",true),NoteDocument.Block.text("b","公开",false))).equals("公开"),"summary omits private text before choosing public text");
        ok(summary(List.of(NoteDocument.Block.text("a","PRIVATE",true))).equals("私有内容（摘要已隐藏）"),"private-only text summary is a placeholder");
        ok(summary(List.of(NoteDocument.Block.image("i","asset","PRIVATE_CAPTION",false))).equals("图片笔记"),"image-only summary never exposes caption or reads media");
        ok(summary(List.of(NoteDocument.Block.image("i","asset","PRIVATE_CAPTION",true))).equals("私有内容（摘要已隐藏）"),"private image summary omits caption");
        ok(summary(List.of(NoteDocument.Block.image("i","asset","caption",false),NoteDocument.Block.text("t","公开文字",false))).equals("公开文字"),"public text summary found after image block");
        ok(summary(List.of(NoteDocument.Block.text("t"," \n ",false))).equals("空笔记"),"blank-only note summary is empty placeholder");
        String face="\ud83d\ude00";
        ok(summary(List.of(NoteDocument.Block.text("t",face.repeat(80),false))).equals(face.repeat(80)),"summary exact eighty code points stays untruncated");
        ok(summary(List.of(NoteDocument.Block.text("t",face.repeat(81),false))).equals(face.repeat(80)+"…"),"summary truncation preserves supplementary Unicode pairs");
        ok(summary(List.of(NoteDocument.Block.text("t","文⽂",false))).equals("文⽂"),"summary does not normalize distinct Unicode characters");
        List<NoteDocument.Block> blocks=new ArrayList<>(List.of(NoteDocument.Block.text("a","one",false),NoteDocument.Block.text("b","two",false)));
        ok(summary(blocks).equals("one"),"summary uses first public text in document order");
        ok(blocks.size()==2&&blocks.get(0).id.equals("a")&&blocks.get(1).text.equals("two"),"summary leaves input order and content unchanged");
        reject(()->summary(null),"summary rejects null blocks");
        reject(()->summary(Arrays.asList((NoteDocument.Block)null)),"summary rejects null block member");
    }
    /** Real legacy wire bytes; the only double is the final append destination.
     * Runs on JVM, not an Android picker, SQLite transaction or device receipt. */
    static void legacyAppendReview() throws Exception {
        com.supercubegame.pockettodo.TodoModel old=new com.supercubegame.pockettodo.TodoModel();
        long first=old.add("同名待办"),second=old.add("同名待办");old.toggle(second);old.add("带有空格的 旧待办");
        byte[] expected=com.supercubegame.pockettodo.BackupCodec.encode(old),input=expected.clone();
        Object previous=stat("LegacyImport","preview",new Class<?>[]{byte[].class},expected);
        String digest=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(expected));
        ok(previous.getClass().getMethod("sourceId").invoke(previous).equals(digest)&&first!=second,"legacy append fixture is a real nonempty canonical backup");
        class ShortRead extends java.io.ByteArrayInputStream {
            int closes,bulk;ShortRead(byte[] b){super(b);}
            @Override public synchronized int read(byte[] b,int o,int n){bulk++;return super.read(b,o,Math.min(7,n));}
            @Override public int available(){return 0;}
            @Override public void close(){closes++;}
        }
        ShortRead in=new ShortRead(input);Object r=stat("LegacyImport","readForAppend",new Class<?>[]{java.io.InputStream.class},in);
        ok(in.closes==1&&in.bulk>1,"legacy review reads short chunks to EOF and closes only its source");
        ok(number(call(r,"total",new Class[]{}))==3&&number(call(r,"completed",new Class[]{}))==1&&call(r,"sourceId",new Class[]{}).equals(digest),"legacy review counts and full-source fingerprint match independent expectations");
        Arrays.fill(input,(byte)0);int[] writes={0};java.util.function.ToLongFunction<byte[]> target=bytes->{
            if(++writes[0]!=1||!Arrays.equals(bytes,expected))throw new AssertionError("appended different bytes or more than once");
            var rows=com.supercubegame.pockettodo.BackupCodec.decode(bytes).items();
            if(rows.size()!=3||rows.get(0).id!=first||rows.get(1).id!=second||!rows.get(0).title.equals(rows.get(1).title)||rows.get(0).done||!rows.get(1).done)throw new AssertionError("wrong legacy row identities");return rows.size();};
        ok(writes[0]==0,"legacy preview performs no append");
        ok(number(call(r,"appendOnce",new Class[]{java.util.function.ToLongFunction.class},target))==3&&writes[0]==1,"explicit legacy append transfers only the exact reviewed bytes");
        reject(()->call(r,"appendOnce",new Class[]{java.util.function.ToLongFunction.class},target),"second confirmation cannot replay the append");
        Object canceled=stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},new ShortRead(expected));((AutoCloseable)canceled).close();((AutoCloseable)canceled).close();
        reject(()->call(canceled,"appendOnce",new Class[]{java.util.function.ToLongFunction.class},target),"cancelled legacy review cannot append");
        Object empty=stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},new ShortRead(com.supercubegame.pockettodo.BackupCodec.encode(new com.supercubegame.pockettodo.TodoModel())));
        ok(number(call(empty,"total",new Class[]{}))==0&&number(call(empty,"completed",new Class[]{}))==0,"empty legacy backup is a read-only zero-row preview");
        reject(()->call(empty,"appendOnce",new Class[]{java.util.function.ToLongFunction.class},target),"empty legacy source never invokes the append destination");
        Object duplicate=stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},new ShortRead(expected));java.util.function.ToLongFunction<byte[]> seen=b->{if(!Arrays.equals(expected,b))throw new AssertionError("duplicate source differs");return 0;};
        ok(number(call(duplicate,"appendOnce",new Class[]{java.util.function.ToLongFunction.class},seen))==0,"already-imported zero result is not presented as new rows");
        Object failure=stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},new ShortRead(expected));RuntimeException sentinel=new IllegalStateException("synthetic append failed");int[] attempts={0};java.util.function.ToLongFunction<byte[]> refused=b->{attempts[0]++;throw sentinel;};boolean exact=false;
        try{call(failure,"appendOnce",new Class[]{java.util.function.ToLongFunction.class},refused);}catch(RuntimeException e){exact=e==sentinel;}
        ok(exact&&attempts[0]==1,"legacy append failure is preserved without replay");reject(()->call(failure,"appendOnce",new Class[]{java.util.function.ToLongFunction.class},target),"failed legacy confirmation requires a new review");
        Object race=stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},new ShortRead(expected));java.util.concurrent.atomic.AtomicInteger entered=new java.util.concurrent.atomic.AtomicInteger(),accepted=new java.util.concurrent.atomic.AtomicInteger(),lost=new java.util.concurrent.atomic.AtomicInteger();
        var start=new java.util.concurrent.CountDownLatch(1);var pool=java.util.concurrent.Executors.newFixedThreadPool(2);
        try{List<java.util.concurrent.Future<?>> futures=new ArrayList<>();for(int i=0;i<2;i++)futures.add(pool.submit(()->{start.await();try{java.util.function.ToLongFunction<byte[]> sink=b->{if(!Arrays.equals(b,expected))throw new AssertionError("wrong concurrent bytes");entered.incrementAndGet();return 3;};call(race,"appendOnce",new Class[]{java.util.function.ToLongFunction.class},sink);accepted.incrementAndGet();}catch(IllegalStateException e){lost.incrementAndGet();}return null;}));start.countDown();for(var f:futures)f.get(5,java.util.concurrent.TimeUnit.SECONDS);}finally{pool.shutdownNow();}
        ok(entered.get()==1&&accepted.get()==1&&lost.get()==1,"two concurrent confirmations deliver exactly once");
        int limit=com.supercubegame.pockettodo.BackupCodec.MAX_BYTES;
        class Sized extends java.io.InputStream {int left,consumed,closedAt,extra;Sized(int n){left=n;}
          public int read(){extra++;if(left==0)return -1;left--;consumed++;return 65;}
          public int read(byte[] b,int off,int len){if(left==0)return -1;int n=Math.min(left,len);Arrays.fill(b,off,off+n,(byte)65);left-=n;consumed+=n;return n;}
          public void close(){closedAt++;}}
        Sized large=new Sized(limit+32);boolean tooLarge=false;try{stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},large);}catch(java.io.IOException e){tooLarge=e.getMessage().contains("大小");}
        ok(tooLarge&&large.consumed==limit+1&&large.closedAt==1,"oversize legacy stream stops at limit plus one without reading the remainder");
        Sized exactLimit=new Sized(limit);boolean format=false;try{stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},exactLimit);}catch(IllegalArgumentException e){format=true;}
        ok(format&&exactLimit.consumed==limit&&exactLimit.closedAt==1,"exact-limit invalid envelope reaches the codec rather than being rejected as oversize");
        java.io.IOException badRead=new java.io.IOException("read failed"),badClose=new java.io.IOException("close failed");int[] closed={0};java.io.InputStream broken=new java.io.InputStream(){public int read()throws java.io.IOException{throw badRead;}public int read(byte[] b,int o,int n)throws java.io.IOException{throw badRead;}public void close()throws java.io.IOException{closed[0]++;throw badClose;}};exact=false;
        try{stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},broken);}catch(java.io.IOException e){exact=e==badRead&&e.getSuppressed().length==1&&e.getSuppressed()[0]==badClose;}
        ok(exact&&closed[0]==1,"source read and close failures retain both causes without producing a review");
        java.io.InputStream closing=new java.io.ByteArrayInputStream(expected){public void close()throws java.io.IOException{throw badClose;}};exact=false;try{stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},closing);}catch(java.io.IOException e){exact=e==badClose;}
        ok(exact,"source close must succeed before a legacy review is returned");
        java.io.InputStream stalled=new java.io.InputStream(){public int read(){throw new AssertionError("no byte fallback");}public int read(byte[] b,int o,int n){return 0;}};boolean noProgress=false;
        try{stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},stalled);}catch(java.io.IOException e){noProgress=e.getMessage().contains("进展");}
        ok(noProgress,"zero-progress legacy provider is not treated as EOF");
        java.io.ByteArrayOutputStream archive=new java.io.ByteArrayOutputStream();try(var zip=new java.util.zip.ZipOutputStream(archive)){zip.putNextEntry(new java.util.zip.ZipEntry("manifest.txt"));zip.write(65);zip.closeEntry();}
        ShortRead wrong=new ShortRead(archive.toByteArray());boolean wrongFormat=false;try{stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},wrong);}catch(IllegalArgumentException e){wrongFormat=e.getMessage().contains("ZIP");}
        ok(wrongFormat&&wrong.closes==1,"full-backup ZIP is rejected by append-only review, never rerouted to replacement");
        byte[] damaged=expected.clone();damaged[damaged.length-3]^=1;ShortRead corrupt=new ShortRead(damaged);reject(()->stat("LegacyImport","readForAppend",new Class[]{java.io.InputStream.class},corrupt),"checksum failure never creates a legacy append review");
        ok(corrupt.closes==1&&writes[0]==1,"refused and cancelled samples never reached the approved destination");
    }
    public static void main(String[] args) throws Exception {
        ledger(); calendar(); notes(); safety(); categories(); CategoryRulesProbe.run(); fields(); imageRevisions(); imageEdits(); batchShares(); noteSummaries(); legacyAppendReview();
        System.out.println("V12_CORE_RESULT "+checks+"/"+checks+" PASS; DOMAIN_ONLY; ANDROID_EXPORT_RESTORE_NOT_TESTED");
    }
}
