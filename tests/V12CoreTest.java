import java.lang.reflect.*;
import java.time.*;
import java.util.*;

/** Reflection lets the unimplemented baseline compile and fail on a missing real contract. */
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
        add(l,"e1","b1",1,"2026-09-01","EXPENSE",1500);
        add(l,"e2","b2",1,"2026-09-03","EXPENSE",2000);
        add(l,"e3","b3",1,"2026-09-08","EXPENSE",4500);
        Set<LocalDate> d=new HashSet<>(Arrays.asList(LocalDate.parse("2026-09-01"),LocalDate.parse("2026-09-03"),LocalDate.parse("2026-09-08"),LocalDate.parse("2026-09-08")));
        ok(sum(l,1,d,"EXPENSE")==8000,"selected nonconsecutive dates total 80 yuan without duplication");
        add(l,"e4","b4",2,"2026-09-01","EXPENSE",200);
        add(l,"e5","b5",2,"2026-09-03","EXPENSE",500);
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
        Object overflow=make("Ledger");
        add(overflow,"max","m",1,"2026-09-01","EXPENSE",Long.MAX_VALUE);
        add(overflow,"one","n",1,"2026-09-01","EXPENSE",1);
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
        Object book=make("CalendarRules");
        Class<?>[] mark={long.class,LocalDate.class,String.class};
        LocalDate date=LocalDate.parse("2026-09-21");
        call(book,"mark",mark,1L,date,"DONE"); call(book,"mark",mark,1L,date,"DONE");
        ok(number(call(book,"completedCount",new Class<?>[]{long.class},1L))==1,"repeat check-in does not inflate count");
        call(book,"mark",mark,2L,date,"SKIPPED");
        ok(number(call(book,"completedCount",new Class<?>[]{long.class},2L))==0,"skipped is not completed");
        ok(call(book,"status",new Class<?>[]{long.class,LocalDate.class},1L,date.plusDays(1)).equals("UNRECORDED"),"new day unrecorded without destroying history");
        reject(()->call(book,"mark",mark,1L,date,"MAYBE"),"unknown check-in status rejected");
        ok(number(call(book,"completedCount",new Class<?>[]{long.class},1L))==1,"invalid check-in leaves old state");
    }
    static void notes() throws Exception {
        Object note=make("NoteDocument");
        Class<?>[] text={String.class,String.class};
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
        // This is metadata capacity, not proof that 120 full-resolution images render on a phone.
    }
    public static void main(String[] args) throws Exception {
        ledger(); calendar(); notes();
        System.out.println("V12_CORE_RESULT "+checks+"/"+checks+" PASS; DOMAIN_ONLY; ANDROID_EXPORT_RESTORE_NOT_TESTED");
    }
}
