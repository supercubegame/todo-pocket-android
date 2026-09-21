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
        reject(()->batch(d,"restart-undo",List.of(row("later",200,"2026-09-08",500))),"undone batch tombstone survives restart");close(d);
    }
    private void define(Object d,String id,String name,String type,List<String> options)throws Exception{call(d,"defineField",new Class[]{String.class,String.class,String.class,List.class},id,name,type,options);}
    private void value(Object d,long activity,String id,List<String> values)throws Exception{call(d,"putField",new Class[]{long.class,String.class,List.class},activity,id,values);}
    private Object value(Object d,long activity,String id)throws Exception{return call(d,"fieldValue",new Class[]{long.class,String.class},activity,id);}
    private Object definition(Object d,String id)throws Exception{return call(d,"fieldDefinition",new Class[]{String.class},id);}
    private byte[] legacy(){TodoModel model=new TodoModel();model.add("旧待办甲");model.add("旧待办乙");model.toggle(2);return BackupCodec.encode(model);}
    private long importLegacy(Object d,byte[] bytes)throws Exception{return((Number)call(d,"importLegacy",new Class[]{byte[].class},(Object)bytes)).longValue();}
    private Object todo(Object d,String id)throws Exception{return call(d,"todo",new Class[]{String.class},id);}
    private Object member(Object obj,String name)throws Exception{return obj.getClass().getField(name).get(obj);}
    private void fieldsSeed()throws Exception{
        getTargetContext().deleteDatabase("fields.db");Object d=db("fields.db");category(d,1,"测试");activity(d,1,1,0,"活动一");activity(d,2,1,0,"活动二");
        define(d,"invite","邀请人数","NUMBER",List.of());value(d,1,"invite",List.of("3"));
        call(d,"createFieldNote",new Class[]{String.class,long.class,String.class,String.class},"field-note",1L,"invite","怎么邀请");
        NoteDocument n=new NoteDocument();n.addText("tip","邀请前先确认活动规则");call(d,"saveNote",new Class[]{String.class,List.class},"field-note",n.snapshot());
        call(d,"renameField",new Class[]{String.class,String.class},"invite","需要邀请的人数");
        ok(value(d,1,"invite").equals(List.of("3"))&&((CustomFields.Definition)definition(d,"invite")).name.equals("需要邀请的人数"),"persistent field rename preserves typed value");
        ok(call(d,"fieldNoteIds",new Class[]{long.class,String.class},1L,"invite").equals(List.of("field-note")),"field note stays attached by ID after rename");
        reject(()->value(d,1,"invite",List.of("three")),"persistent numeric field rejects non-number");ok(value(d,1,"invite").equals(List.of("3")),"bad field edit retains exact previous value");
        reject(()->value(d,999,"invite",List.of("4")),"field value cannot refer to unknown activity");
        define(d,"conditions","条件","MULTI_SELECT",List.of("invite","purchase"));value(d,1,"conditions",List.of("purchase","invite","purchase"));
        ok(value(d,1,"conditions").equals(List.of("purchase","invite")),"persistent multi-select deduplicates in order");
        reject(()->value(d,1,"conditions",List.of("invite","unknown")),"late invalid option rejects whole replacement");ok(value(d,1,"conditions").equals(List.of("purchase","invite")),"invalid option leaves all old choices");
        define(d,"date","截止","DATE",List.of());reject(()->value(d,1,"date",List.of("2026-02-29")),"persistent impossible date rejected");
        define(d,"link","规则","LINK",List.of());reject(()->value(d,1,"link",List.of("javascript:alert(1)")),"persistent executable link rejected");value(d,1,"link",List.of("https://example.com/rules"));
        define(d,"flag","已确认","BOOLEAN",List.of());value(d,1,"flag",List.of("false"));ok(value(d,1,"flag").equals(List.of("false")),"false field value differs from unset");
        value(d,1,"flag",List.of());ok(value(d,1,"flag").equals(List.of()),"explicit empty field clears value");
        define(d,"long","攻略补充","LONG_TEXT",List.of());char[] chars=new char[5000];Arrays.fill(chars,'技');String longText=new String(chars);value(d,1,"long",List.of(longText));ok(value(d,1,"long").equals(List.of(longText)),"new long field does not inherit legacy200-char cap");
        call(d,"archiveField",new Class[]{String.class,boolean.class},"invite",true);ok(value(d,1,"invite").equals(List.of("3")),"archiving field retains persistent value");
        reject(()->value(d,1,"invite",List.of("4")),"archived persistent field rejects new value");
        reject(()->call(d,"createFieldNote",new Class[]{String.class,long.class,String.class,String.class},"blocked",1L,"invite","new"),"archived field rejects new attached note");
        ok(call(d,"fieldNoteIds",new Class[]{long.class,String.class},1L,"invite").equals(List.of("field-note"))&&((List<?>)call(d,"noteBlocks",new Class[]{String.class},"field-note")).size()==1,"archive preserves existing field note and text");
        reject(()->call(d,"createFieldNote",new Class[]{String.class,long.class,String.class,String.class},"missing",1L,"missing","bad"),"unknown field note rejected atomically");
        ok(count(d,"notes")==1,"failed field note does not create orphan note");
        call(d,"addTodo",new Class[]{String.class,String.class},"local","本地新待办");call(d,"addTodo",new Class[]{String.class,String.class},"long-todo",longText);
        ok(member(todo(d,"long-todo"),"title").equals(longText),"new ordinary todo does not inherit legacy title cap");
        call(d,"editTodo",new Class[]{String.class,String.class,boolean.class},"local","本地已编辑",true);
        ok(member(todo(d,"local"),"title").equals("本地已编辑")&&(Boolean)member(todo(d,"local"),"done"),"ordinary todo edit and completion persist");
        reject(()->call(d,"editTodo",new Class[]{String.class,String.class,boolean.class},"local"," ",false),"blank ordinary todo edit rejected");
        ok((Boolean)member(todo(d,"local"),"done"),"invalid todo edit does not change completion");
        ok(importLegacy(d,legacy())==2&&count(d,"todos")==4,"legacy import appends ordinary todos without replacing existing");
        ok(importLegacy(d,legacy())==0&&count(d,"todos")==4,"same legacy backup imported twice is persistent no-op");
        String source=LegacyImport.preview(legacy()).sourceId();String first="legacy-"+source+"-1",second="legacy-"+source+"-2";
        ok(member(todo(d,first),"title").equals("旧待办甲")&&!(Boolean)member(todo(d,first),"done")&&(Boolean)member(todo(d,second),"done"),"legacy remapping keeps text and completion");
        ok(call(d,"todoIds",new Class[]{}).equals(List.of("local","long-todo",first,second)),"legacy appends preserve imported and existing order");
        ok(count(d,"activities")==2&&count(d,"ledger")==0&&count(d,"checkins")==0,"legacy import invents no activities money or check-ins");
        byte[] broken=legacy();broken[broken.length-2]^=1;reject(()->importLegacy(d,broken),"corrupt legacy import rejected before transaction");ok(count(d,"todos")==4&&count(d,"legacy_imports")==1,"bad import retains rows and journal exactly");
        // Force an ID conflict on the SECOND imported row. First row and journal must roll back.
        TodoModel other=new TodoModel();other.add("另一备份甲");other.add("另一备份乙");byte[] clash=BackupCodec.encode(other);String clashSource=LegacyImport.preview(clash).sourceId();
        call(d,"addTodo",new Class[]{String.class,String.class},"legacy-"+clashSource+"-2","本地占用标识");
        reject(()->importLegacy(d,clash),"late imported ID collision rolls back complete import");ok(count(d,"todos")==5&&count(d,"legacy_imports")==1,"failed import has neither first row nor journal residue");
        close(d);migration();
    }
    private void fieldsReopen()throws Exception{
        Object d=db("fields.db");ok(value(d,1,"invite").equals(List.of("3"))&&((CustomFields.Definition)definition(d,"invite")).archived,"process restart retains archived definition and numeric value");
        ok(value(d,1,"conditions").equals(List.of("purchase","invite")),"process restart retains multi-select ordering");
        ok(call(d,"fieldNoteIds",new Class[]{long.class,String.class},1L,"invite").equals(List.of("field-note")),"process restart retains field-note relationship");
        ok(member(todo(d,"local"),"title").equals("本地已编辑")&&(Boolean)member(todo(d,"local"),"done"),"process restart retains independent ordinary todo");
        ok(importLegacy(d,legacy())==0&&count(d,"todos")==5&&count(d,"legacy_imports")==1,"process restart retains legacy import idempotency journal");
        close(d);Object migrated=db("migrate-v1.db");ok(call(migrated,"categoryName",new Class[]{long.class},7L).equals("原分类"),"migrated data persists into separate process");close(migrated);
    }
    // Frozen v1 DDL from41165adf, independent from current production onCreate/onUpgrade.
    private static final String[] V1_DDL={
        "CREATE TABLE revision(id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL CHECK(value>=0))",
        "CREATE TABLE categories(id INTEGER PRIMARY KEY CHECK(id>0),name TEXT NOT NULL CHECK(length(trim(name))>0),position INTEGER NOT NULL CHECK(position>=0))",
        "CREATE TABLE applications(id INTEGER PRIMARY KEY CHECK(id>0),name TEXT NOT NULL,package_name TEXT NOT NULL)",
        "CREATE UNIQUE INDEX application_package ON applications(package_name) WHERE package_name<>''",
        "CREATE TABLE activities(id INTEGER PRIMARY KEY CHECK(id>0),category_id INTEGER NOT NULL REFERENCES categories(id),application_id INTEGER REFERENCES applications(id),title TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN(0,1)))",
        "CREATE TABLE paths(activity_id INTEGER NOT NULL REFERENCES activities(id),position INTEGER NOT NULL CHECK(position>=0),text TEXT NOT NULL,PRIMARY KEY(activity_id,position))",
        "CREATE TABLE tags(activity_id INTEGER NOT NULL REFERENCES activities(id),position INTEGER NOT NULL CHECK(position>=0),text TEXT NOT NULL,PRIMARY KEY(activity_id,text),UNIQUE(activity_id,position))",
        "CREATE TABLE batches(id TEXT PRIMARY KEY NOT NULL,payload BLOB NOT NULL,revision INTEGER NOT NULL,undone INTEGER NOT NULL CHECK(undone IN(0,1)))",
        "CREATE TABLE ledger(id TEXT PRIMARY KEY NOT NULL,activity_id INTEGER NOT NULL REFERENCES activities(id),day TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('EXPENSE','REFUND','INCOME','PLANNED')),cents INTEGER NOT NULL CHECK(cents>=0),memo TEXT NOT NULL,batch_id TEXT NOT NULL REFERENCES batches(id),position INTEGER NOT NULL CHECK(position>=0),UNIQUE(batch_id,position))",
        "CREATE INDEX ledger_activity_day ON ledger(activity_id,day)",
        "CREATE TABLE checkins(activity_id INTEGER NOT NULL REFERENCES activities(id),day TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN('DONE','SKIPPED')),memo TEXT NOT NULL,recorded_at TEXT NOT NULL,PRIMARY KEY(activity_id,day))",
        "CREATE TABLE media(id TEXT PRIMARY KEY NOT NULL,mime TEXT NOT NULL,bytes INTEGER NOT NULL CHECK(bytes>0))",
        "CREATE TABLE notes(id TEXT PRIMARY KEY NOT NULL,activity_id INTEGER NOT NULL REFERENCES activities(id),title TEXT NOT NULL)",
        "CREATE TABLE blocks(note_id TEXT NOT NULL REFERENCES notes(id),id TEXT NOT NULL,position INTEGER NOT NULL CHECK(position>=0),kind TEXT NOT NULL CHECK(kind IN('TEXT','IMAGE')),text TEXT NOT NULL,asset_id TEXT REFERENCES media(id),caption TEXT NOT NULL,private INTEGER NOT NULL CHECK(private IN(0,1)),PRIMARY KEY(note_id,id),UNIQUE(note_id,position),CHECK((kind='TEXT' AND asset_id IS NULL) OR (kind='IMAGE' AND asset_id IS NOT NULL)))"
    };
    private void migration()throws Exception{
        Context context=getTargetContext();context.deleteDatabase("migrate-v1.db");SQLiteDatabase old=context.openOrCreateDatabase("migrate-v1.db",0,null);old.setForeignKeyConstraintsEnabled(true);
        for(String sql:V1_DDL)old.execSQL(sql);old.execSQL("INSERT INTO revision VALUES(1,42)");old.execSQL("INSERT INTO categories VALUES(7,'原分类',0)");old.execSQL("INSERT INTO activities VALUES(9,7,NULL,'原活动',0)");old.execSQL("INSERT INTO notes VALUES('old-note',9,'原笔记')");old.execSQL("INSERT INTO blocks VALUES('old-note','old-block',0,'TEXT','不能丢',NULL,'',1)");old.execSQL("INSERT INTO checkins VALUES(9,'2026-09-01','DONE','补记','2026-09-21T12:00:00Z')");old.setVersion(1);
        try(android.database.Cursor c=old.rawQuery("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='fields'",null)){c.moveToFirst();ok(old.getVersion()==1&&c.getLong(0)==0,"migration fixture really is v1 without new field table");}old.close();
        Object newer=db("migrate-v1.db");ok(call(newer,"categoryName",new Class[]{long.class},7L).equals("原分类")&&count(newer,"activities")==1,"v1 to v2 migration retains category and activity");
        @SuppressWarnings("unchecked") List<NoteDocument.Block> blocks=(List<NoteDocument.Block>)call(newer,"noteBlocks",new Class[]{String.class},"old-note");
        ok(blocks.size()==1&&blocks.get(0).text.equals("不能丢")&&blocks.get(0).privateContent&&count(newer,"checkins")==1,"migration preserves old private note and check-in");
        SQLiteDatabase raw=((android.database.sqlite.SQLiteOpenHelper)newer).getReadableDatabase();
        try(android.database.Cursor c=raw.rawQuery("SELECT value FROM revision WHERE id=1",null)){c.moveToFirst();ok(raw.getVersion()==2&&c.getLong(0)==42,"migration advances schema not user revision");}
        define(newer,"new-field","新字段","TEXT",List.of());value(newer,9,"new-field",List.of("迁移后可用"));ok(value(newer,9,"new-field").equals(List.of("迁移后可用")),"new fields usable on migrated database");
        try(android.database.Cursor c=raw.rawQuery("PRAGMA foreign_key_check",null)){ok(!c.moveToFirst(),"migrated database has no foreign key violations");}
        close(newer);
    }
    @Override public void onStart(){
        Bundle result=new Bundle();try{
            ok(getTargetContext().getPackageName().equals("com.supercubegame.pockettodo.v12.preview"),"tests target isolated v1.2 package");
            ok(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"actual emulator API equals requested test matrix");
            String phase=args.getString("phase");if("seed".equals(phase)){seed();fieldsSeed();}else if("reopen".equals(phase)){reopen();fieldsReopen();}else throw new IllegalArgumentException("unknown test phase");
            log.append("DEVICE_DATABASE_RESULT ").append(phase).append(' ').append(checks).append('/').append(checks).append(" PASS\n");result.putString("stream",log.toString());finish(Activity.RESULT_OK,result);
        }catch(Throwable error){StringWriter text=new StringWriter();error.printStackTrace(new PrintWriter(text));result.putString("stream",log+"DEVICE_DATABASE_FAILED\n"+text);finish(Activity.RESULT_CANCELED,result);}
    }
}
