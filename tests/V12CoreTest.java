import java.lang.reflect.*;
import java.time.*;
import java.util.*;
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
    public static void main(String[] args) throws Exception {
        ledger(); calendar(); notes(); safety(); categories(); fields();
        System.out.println("V12_CORE_RESULT "+checks+"/"+checks+" PASS; DOMAIN_ONLY; ANDROID_EXPORT_RESTORE_NOT_TESTED");
    }
}
