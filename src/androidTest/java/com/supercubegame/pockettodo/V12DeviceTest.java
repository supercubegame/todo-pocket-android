package com.supercubegame.pockettodo;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;
import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import java.lang.reflect.*;
import java.time.*;
import java.util.*;
import java.io.*;
import java.nio.file.*;

/** Real-device database/API contracts, NOT product UI acceptance. */
public final class V12DeviceTest extends Instrumentation {
    private Bundle args; private int checks; private final StringBuilder log=new StringBuilder();
    interface Action {void run() throws Exception;}
    @Override public void onCreate(Bundle args){super.onCreate(args);this.args=args;start();}
    private void ok(boolean value,String label){if(!value)throw new AssertionError(label);checks++;log.append("PASS ").append(label).append('\n');}
    private void reject(Action action,String label)throws Exception{boolean bad=false;try{action.run();}catch(IllegalArgumentException|IllegalStateException e){bad=true;}ok(bad,label);}
    private Object call(Object obj,String method,Class<?>[] types,Object...values)throws Exception{
        try{return obj.getClass().getMethod(method,types).invoke(obj,values);}catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
    }
    private Object db(String name)throws Exception{return Class.forName("com.supercubegame.pockettodo.AppDatabase").getConstructor(Context.class,String.class).newInstance(getTargetContext(),name);}
    private void close(Object db)throws Exception{call(db,"close",new Class[]{});}
    private long count(Object db,String table)throws Exception{return((Number)call(db,"count",new Class[]{String.class},table)).longValue();}
    private long total(Object db,long activity,Set<LocalDate> dates,String metric)throws Exception{return((Number)call(db,"total",new Class[]{long.class,Set.class,String.class},activity,dates,metric)).longValue();}
    private void category(Object db,long id,String name)throws Exception{call(db,"addCategory",new Class[]{long.class,String.class},id,name);}
    private void activity(Object db,long id,long cat,long app,String name)throws Exception{call(db,"addActivity",new Class[]{long.class,long.class,long.class,String.class},id,cat,app,name);}
    private boolean batch(Object db,String key,List<Ledger.Entry> entries)throws Exception{return(Boolean)call(db,"recordBatch",new Class[]{String.class,List.class},key,entries);}
    private Ledger.Entry row(String id,long activity,String day,long cents){return new Ledger.Entry(id,activity,LocalDate.parse(day),Ledger.Kind.EXPENSE,cents,"合成备注");}
    private void seed()throws Exception{
        Context context=getTargetContext();context.deleteDatabase("v12-contract.db");Object d=db("v12-contract.db");
        ok(count(d,"categories")==0,"new database empty, no demo user data");
        category(d,1,"每日打卡");category(d,2,"芭芭农场");
        call(d,"addApplication",new Class[]{long.class,String.class,String.class},10L,"淘宝","");activity(d,100,1,10,"90天打卡");activity(d,200,2,10,"农场");
        call(d,"renameCategory",new Class[]{long.class,String.class},1L,"日常活动");
        ok(call(d,"categoryName",new Class[]{long.class},1L).equals("日常活动"),"category rename committed");
        call(d,"moveCategory",new Class[]{long.class,int.class},2L,0);ok(call(d,"categoryIds",new Class[]{}).equals(List.of(2L,1L)),"category order persisted by stable IDs");
        reject(()->call(d,"moveCategory",new Class[]{long.class,int.class},1L,99),"bad reorder rejected");
        ok(call(d,"categoryIds",new Class[]{}).equals(List.of(2L,1L)),"bad reorder retains exact order");
        reject(()->activity(d,300,999,10,"bad"),"unknown category rejected by DB adapter");ok(count(d,"activities")==2,"invalid activity has no partial row");
        call(d,"savePath",new Class[]{long.class,List.class},100L,List.of("我的","福利中心","90天打卡"));
        ok(call(d,"path",new Class[]{long.class},100L).equals(List.of("我的","福利中心","90天打卡")),"ordered in-app path persisted");
        reject(()->call(d,"savePath",new Class[]{long.class,List.class},100L,List.of("替换"," ")),"invalid later path step rejected");
        ok(call(d,"path",new Class[]{long.class},100L).equals(List.of("我的","福利中心","90天打卡")),"failed path replacement leaves all old steps");
        call(d,"saveTags",new Class[]{long.class,List.class},100L,List.of("邀请","购物","邀请"));ok(call(d,"tags",new Class[]{long.class},100L).equals(List.of("邀请","购物")),"tags deduplicate without losing order");
        List<Ledger.Entry> entries=List.of(row("e1",100,"2026-09-01",1500),row("e2",100,"2026-09-03",2000),row("e3",100,"2026-09-08",4500));
        ok(batch(d,"money-1",entries),"multi-date money batch inserted");
        Set<LocalDate> dates=Set.of(LocalDate.of(2026,9,1),LocalDate.of(2026,9,3),LocalDate.of(2026,9,8));
        ok(total(d,100,dates,"EXPENSE")==8000,"persistent selected-date total is 80 yuan");
        ok(!batch(d,"money-1",entries)&&count(d,"ledger")==3,"identical retry no duplicate money");
        reject(()->batch(d,"money-1",List.of(row("e1",100,"2026-09-01",999))),"conflicting batch key rejected");
        reject(()->batch(d,"bad-fk",List.of(row("new",100,"2026-09-01",1),row("foreign",999,"2026-09-01",1))),"late unknown activity rolls back whole money batch");
        ok(count(d,"ledger")==3&&count(d,"batches")==1,"failed batch leaves no rows or idempotency key");
        reject(()->batch(d,"bad-id",List.of(row("new",100,"2026-09-01",1),entries.get(0))),"late duplicate entry rolls back whole transaction");
        ok(count(d,"ledger")==3&&count(d,"batches")==1,"duplicate entry leaves ledger and journal unchanged");
        Ledger.Entry plan=new Ledger.Entry("plan",100,LocalDate.of(2026,9,8),Ledger.Kind.PLANNED,9900,"");batch(d,"planned",List.of(plan));
        ok(total(d,100,dates,"EXPENSE")==8000&&total(d,100,dates,"PLANNED")==9900,"planned isolated from actual after SQL persistence");
        call(d,"undoBatch",new Class[]{String.class},"planned");ok(count(d,"ledger")==3,"latest batch undo removes own rows");
        reject(()->batch(d,"planned",List.of(plan)),"undo tombstone prevents old retry resurrection");
        call(d,"putMark",new Class[]{CalendarRules.Mark.class},new CalendarRules.Mark(100,LocalDate.of(2026,9,1),CalendarRules.Status.DONE,"补记",Instant.parse("2026-09-21T12:00:00Z")));
        call(d,"putMark",new Class[]{CalendarRules.Mark.class},new CalendarRules.Mark(100,LocalDate.of(2026,9,1),CalendarRules.Status.DONE,"补记",Instant.parse("2026-09-21T12:00:00Z")));
        ok(count(d,"checkins")==1,"duplicate check-in single persistent day");
        reject(()->call(d,"putMark",new Class[]{CalendarRules.Mark.class},new CalendarRules.Mark(100,LocalDate.of(2026,9,2),CalendarRules.Status.DONE,"",null)),"persistent mark requires actual entry timestamp");
        call(d,"createNote",new Class[]{String.class,long.class,String.class},"guide",100L,"攻略");
        NoteDocument note=new NoteDocument();note.addText("one","先打开应用");note.add(NoteDocument.Block.text("private","私有备注",true));
        call(d,"saveNote",new Class[]{String.class,List.class},"guide",note.snapshot());
        ok(((List<?>)call(d,"noteBlocks",new Class[]{String.class},"guide")).size()==2,"ordered private/public text blocks committed");
        NoteDocument missingImage=new NoteDocument();missingImage.addText("replace","替换");missingImage.addImage("photo","missing","截图");
        reject(()->call(d,"saveNote",new Class[]{String.class,List.class},"guide",missingImage.snapshot()),"note cannot reference missing stored media");
        ok(((List<?>)call(d,"noteBlocks",new Class[]{String.class},"guide")).size()==2,"failed note replace retains all prior blocks");
        Path mediaRoot=context.getFilesDir().toPath().resolve("contract-media");MediaRepository media=new MediaRepository(mediaRoot,4096);String id=media.copy(new ByteArrayInputStream(new byte[]{97,98,99}));
        ok(id.equals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),"Android locked atomic publication and digest verified");
        ok(media.copy(new ByteArrayInputStream(new byte[]{97,98,99})).equals(id),"Android duplicate media does not replace existing file");
        // Concurrent repository instances must cooperate on one private destination.
        java.util.concurrent.CountDownLatch start=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.atomic.AtomicReference<Throwable> failure=new java.util.concurrent.atomic.AtomicReference<>();
        List<Thread> writers=new ArrayList<>();for(int i=0;i<4;i++){Thread t=new Thread(()->{try{start.await();String actual=new MediaRepository(mediaRoot,4096).copy(new ByteArrayInputStream(new byte[]{97,98,99}));if(!actual.equals(id))throw new AssertionError("digest mismatch");}catch(Throwable e){failure.compareAndSet(null,e);}});writers.add(t);t.start();}
        start.countDown();for(Thread t:writers){t.join(10000);if(t.isAlive())throw new AssertionError("parallel writer stalled");}
        if(failure.get()!=null)throw new AssertionError("parallel writer failed",failure.get());media.verify(id);
        ok(Arrays.equals(Files.readAllBytes(media.path(id)),new byte[]{97,98,99}),"parallel media imports retain exact bytes without overlapping JVM locks");
        call(d,"registerMedia",new Class[]{String.class,String.class,long.class},id,"application/octet-stream",3L);
        note.addImage("image",id,"合成文件，不是图片解码测试");call(d,"saveNote",new Class[]{String.class,List.class},"guide",note.snapshot());
        ok(((List<?>)call(d,"noteBlocks",new Class[]{String.class},"guide")).size()==3,"note image reference requires registered media");
        Path archive=context.getFilesDir().toPath().resolve("contract.ptodo12");Files.deleteIfExists(archive);BackupArchive.write(archive,new byte[]{1,2,3},Set.of(id),media);
        try(BackupArchive.Snapshot snapshot=BackupArchive.read(archive,context.getCacheDir().toPath(),4096)){ok(Arrays.equals(snapshot.state(),new byte[]{1,2,3})&&snapshot.assets().containsKey(id),"Android archive byte transport round-trips");}
        boolean refused=false;byte[] archiveBefore=Files.readAllBytes(archive);try{BackupArchive.write(archive,new byte[]{9},Set.of(id),media);}catch(IOException e){refused=true;}
        ok(refused&&Arrays.equals(archiveBefore,Files.readAllBytes(archive)),"Android export refuses overwrite and preserves exact existing ZIP");
        batch(d,"restart-undo",List.of(row("later",200,"2026-09-08",500)));
        close(d);Object again=db("v12-contract.db");ok(count(again,"ledger")==4,"database helper reopen retains money");close(again);
        context.deleteDatabase("future.db");SQLiteDatabase future=context.openOrCreateDatabase("future.db",0,null);future.execSQL("CREATE TABLE sentinel(value TEXT)");future.execSQL("INSERT INTO sentinel VALUES ('keep')");future.setVersion(99);future.close();
        reject(()->{Object newer=db("future.db");try{count(newer,"categories");}finally{close(newer);}},"future schema refused without destructive downgrade");
        SQLiteDatabase retained=context.openOrCreateDatabase("future.db",0,null);try(android.database.Cursor c=retained.rawQuery("SELECT value FROM sentinel",null)){ok(c.moveToFirst()&&c.getString(0).equals("keep")&&retained.getVersion()==99,"future database remains byte-semantically intact");}finally{retained.close();}
    }
    private void reopen()throws Exception{
        Object d=db("v12-contract.db");
        ok(call(d,"categoryName",new Class[]{long.class},1L).equals("日常活动")&&call(d,"categoryIds",new Class[]{}).equals(List.of(2L,1L)),"separate instrumented process retains names and ordering");
        ok(call(d,"path",new Class[]{long.class},100L).equals(List.of("我的","福利中心","90天打卡")),"process restart retains ordered navigation path");
        ok(call(d,"tags",new Class[]{long.class},100L).equals(List.of("邀请","购物")),"process restart retains tags");
        ok(count(d,"ledger")==4&&count(d,"checkins")==1,"process restart retains money and check-ins");
        @SuppressWarnings("unchecked") List<CalendarRules.Mark> marks=(List<CalendarRules.Mark>)call(d,"marks",new Class[]{long.class},100L);
        ok(marks.size()==1&&marks.get(0).date.equals(LocalDate.of(2026,9,1))&&marks.get(0).recordedAt.equals(Instant.parse("2026-09-21T12:00:00Z")),"process restart keeps backdate separate from timestamp");
        @SuppressWarnings("unchecked") List<NoteDocument.Block> blocks=(List<NoteDocument.Block>)call(d,"noteBlocks",new Class[]{String.class},"guide");
        ok(blocks.size()==3&&blocks.get(0).text.equals("先打开应用")&&blocks.get(1).privateContent&&blocks.get(2).kind==NoteDocument.Kind.IMAGE,"process restart keeps block order text privacy and image reference");
        List<Ledger.Entry> entries=List.of(row("e1",100,"2026-09-01",1500),row("e2",100,"2026-09-03",2000),row("e3",100,"2026-09-08",4500));
        ok(!batch(d,"money-1",entries)&&count(d,"ledger")==4,"idempotency journal survives process restart");
        call(d,"undoBatch",new Class[]{String.class},"restart-undo");ok(count(d,"ledger")==3,"latest batch undo survives process restart");
        reject(()->call(d,"undoBatch",new Class[]{String.class},"money-1"),"old batch undo still invalid after later writes and restart");
        reject(()->batch(d,"restart-undo",List.of(row("later",200,"2026-09-08",500))),"undone batch tombstone survives restart");
        close(d);
    }
    @Override public void onStart(){
        Bundle result=new Bundle();try{
            ok(getTargetContext().getPackageName().equals("com.supercubegame.pockettodo.v12.preview"),"tests target isolated v1.2 package");
            ok(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"actual emulator API equals requested test matrix");
            String phase=args.getString("phase");if("seed".equals(phase))seed();else if("reopen".equals(phase))reopen();else throw new IllegalArgumentException("unknown test phase");
            log.append("DEVICE_DATABASE_RESULT ").append(phase).append(' ').append(checks).append('/').append(checks).append(" PASS\n");result.putString("stream",log.toString());finish(Activity.RESULT_OK,result);
        }catch(Throwable error){StringWriter text=new StringWriter();error.printStackTrace(new PrintWriter(text));result.putString("stream",log+"DEVICE_DATABASE_FAILED\n"+text);finish(Activity.RESULT_CANCELED,result);}
    }
}
