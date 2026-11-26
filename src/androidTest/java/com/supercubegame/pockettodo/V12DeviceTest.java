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
        try(android.database.Cursor c=raw.rawQuery("PRAGMA foreign_key_check",null)){ok(!c.moveToFirst(),"migrated database has no foreign key violations");}close(newer);
    }

    // Independent schema2 wire fixture: no production encoder or semantic validator used.
    private static final String[] TABLES={"revision","categories","applications","activities","paths","tags","batches","ledger","checkins","media","notes","blocks","fields","field_options","field_values","field_notes","todos","legacy_imports"};
    private SQLiteDatabase raw(Object d){return((android.database.sqlite.SQLiteOpenHelper)d).getWritableDatabase();}
    private void bytes(DataOutputStream out,byte[] b)throws IOException{out.writeInt(b.length);out.write(b);}
    private void str(DataOutputStream out,String s)throws IOException{bytes(out,s.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
    private byte[] fixture(Object d)throws Exception{
        ByteArrayOutputStream b=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(b);out.writeInt(0x50544442);out.writeInt(1);out.writeInt(2);out.writeInt(TABLES.length);
        for(String table:TABLES)try(android.database.Cursor c=raw(d).rawQuery("SELECT * FROM "+table+" ORDER BY rowid",null)){
            str(out,table);out.writeInt(c.getColumnCount());for(String name:c.getColumnNames())str(out,name);out.writeInt(c.getCount());
            while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){int type=c.getType(i);out.writeByte(type);switch(type){case 0:break;case 1:out.writeLong(c.getLong(i));break;case 3:str(out,c.getString(i));break;case 4:bytes(out,c.getBlob(i));break;default:throw new AssertionError("unexpected fixture SQL type");}}
        }out.flush();return b.toByteArray();
    }
    private byte[] state(Object d)throws Exception{return(byte[])call(d,"exportState",new Class[]{});}
    private void backup(Object d,Path file,MediaRepository media)throws Exception{call(d,"exportBackup",new Class[]{Path.class,MediaRepository.class},file,media);}
    private void restore(Object d,Path file,MediaRepository media)throws Exception{call(d,"restoreBackup",new Class[]{Path.class,Path.class,long.class,MediaRepository.class},file,getTargetContext().getCacheDir().toPath(),1000000L,media);}
    private void rejectedRestore(Object d,Path file,MediaRepository media,byte[] before,String label)throws Exception{
        boolean refused=false;try{restore(d,file,media);}catch(IOException|IllegalArgumentException|IllegalStateException e){refused=true;}
        ok(refused,label+" rejected");ok(Arrays.equals(state(d),before),label+" keeps complete prior DB state");
    }
    private byte[] poisoned(Object source,String sql)throws Exception{SQLiteDatabase r=raw(source);r.beginTransaction();try{r.execSQL(sql);return fixture(source);}finally{r.endTransaction();}}
    private void backupSeed()throws Exception{
        Context c=getTargetContext();c.deleteDatabase("backup-source.db");c.deleteDatabase("backup-target.db");Object s=db("backup-source.db"),t=db("backup-target.db");
        category(s,1,"完整恢复");call(s,"addApplication",new Class[]{long.class,String.class,String.class},10L,"示例应用","com.example.app");activity(s,100,1,10,"活动内容");
        call(s,"savePath",new Class[]{long.class,List.class},100L,List.of("我的","福利","打卡"));call(s,"saveTags",new Class[]{long.class,List.class},100L,List.of("购物","邀请"));
        define(s,"number","次数","NUMBER",List.of());value(s,100,"number",List.of("12"));define(s,"choice","方式","MULTI_SELECT",List.of("a","b"));value(s,100,"choice",List.of("b","a"));
        call(s,"createFieldNote",new Class[]{String.class,long.class,String.class,String.class},"n",100L,"number","字段攻略");
        MediaRepository sm=new MediaRepository(c.getFilesDir().toPath().resolve("backup-source-media"),1000000),tm=new MediaRepository(c.getFilesDir().toPath().resolve("backup-target-media"),1000000);
        byte[] asset={1,2,3,4,5};String id=sm.copy(new ByteArrayInputStream(asset));call(s,"registerMedia",new Class[]{String.class,String.class,long.class},id,"application/octet-stream",5L);
        NoteDocument n=new NoteDocument();n.add(NoteDocument.Block.text("secret","保留私有内容",true));n.addImage("img",id,"合成媒体原字节");n.addText("end","末尾文字");call(s,"saveNote",new Class[]{String.class,List.class},"n",n.snapshot());call(s,"archiveField",new Class[]{String.class,boolean.class},"number",true);
        call(s,"putMark",new Class[]{CalendarRules.Mark.class},new CalendarRules.Mark(100,LocalDate.of(2026,9,1),CalendarRules.Status.SKIPPED,"跳过",Instant.parse("2026-09-21T12:00:00Z")));
        call(s,"addTodo",new Class[]{String.class,String.class},"own","自己的待办");importLegacy(s,legacy());
        batch(s,"undone",List.of(row("u",100,"2026-09-01",100)));call(s,"undoBatch",new Class[]{String.class},"undone");
        List<Ledger.Entry> money=List.of(row("m1",100,"2026-09-01",1500),new Ledger.Entry("m2",100,LocalDate.of(2026,9,3),Ledger.Kind.REFUND,500,"退款"));batch(s,"latest",money);
        byte[] expected=state(s);ok(Arrays.equals(expected,fixture(s)),"production snapshot equals independently encoded all-table fixture");
        for(String table:TABLES)try(android.database.Cursor rows=raw(s).rawQuery("SELECT count(*) FROM "+table,null)){rows.moveToFirst();ok(rows.getLong(0)>0,"backup fixture covers nonempty "+table);}
        Path good=c.getFilesDir().toPath().resolve("full-good.zip");Files.deleteIfExists(good);backup(s,good,sm);
        try(BackupArchive.Snapshot z=BackupArchive.read(good,c.getCacheDir().toPath(),1000000)){ok(Arrays.equals(z.state(),expected)&&z.assets().keySet().equals(Set.of(id)),"real backup ZIP contains exact semantic state and registered assets");}
        call(t,"addTodo",new Class[]{String.class,String.class},"sentinel","恢复前不要丢");byte[] before=state(t);String oldId=tm.copy(new ByteArrayInputStream(new byte[]{9,8,7}));
        Path bad=c.getFilesDir().toPath().resolve("full-bad.zip");Files.deleteIfExists(bad);BackupArchive.write(bad,expected,Set.of(),sm);rejectedRestore(t,bad,tm,before,"valid ZIP with missing registered media");
        String extra=sm.copy(new ByteArrayInputStream(new byte[]{6,7}));Files.deleteIfExists(bad);BackupArchive.write(bad,expected,Set.of(id,extra),sm);rejectedRestore(t,bad,tm,before,"valid ZIP with unregistered extra media");
        byte[] future=expected.clone();future[11]=99;Files.deleteIfExists(bad);BackupArchive.write(bad,future,Set.of(id),sm);rejectedRestore(t,bad,tm,before,"unknown state schema");
        byte[] tail=Arrays.copyOf(expected,expected.length+1);Files.deleteIfExists(bad);BackupArchive.write(bad,tail,Set.of(id),sm);rejectedRestore(t,bad,tm,before,"trailing semantic state bytes");
        String[] faults={"UPDATE field_values SET value='not-a-number' WHERE field_id='number'","UPDATE checkins SET day='2026-02-29'","UPDATE paths SET position=99 WHERE position=1","UPDATE batches SET payload=X'00000000' WHERE id='latest'","UPDATE media SET bytes=6","UPDATE field_values SET value='unknown' WHERE field_id='choice' AND position=0"};
        String[] labels={"invalid archived numeric field","impossible check-in date","ordered path gap","inconsistent money batch journal","media registry size mismatch","unknown saved choice"};
        for(int i=0;i<faults.length;i++){byte[] invalid=poisoned(s,faults[i]);ok(!Arrays.equals(invalid,expected),"semantic fault fixture differs: "+labels[i]);Files.deleteIfExists(bad);BackupArchive.write(bad,invalid,Set.of(id),sm);rejectedRestore(t,bad,tm,before,labels[i]);}
        // This trigger fails late, after replacement has deleted old rows and inserted parents.
        raw(t).execSQL("CREATE TEMP TRIGGER fail_restore BEFORE INSERT ON todos WHEN NEW.id='own' BEGIN SELECT RAISE(ABORT,'injected_restore_failure'); END");
        boolean injected=false;try{restore(t,good,tm);}catch(Exception e){Throwable x=e;while(x!=null){if(String.valueOf(x.getMessage()).contains("injected_restore_failure"))injected=true;x=x.getCause();}}
        ok(injected,"late restore failure is the exact injected SQLite trigger fault");ok(Arrays.equals(state(t),before),"late commit failure rolls back deleted old data plus all inserted tables");
        ok(Arrays.equals(Files.readAllBytes(tm.path(oldId)),new byte[]{9,8,7}),"failed restore never modifies old media bytes");raw(t).execSQL("DROP TRIGGER fail_restore");
        restore(t,good,tm);ok(Arrays.equals(state(t),expected),"successful replacement round-trips all tables and journals exactly");ok(Arrays.equals(Files.readAllBytes(tm.path(id)),asset),"restored media has exact source bytes");
        ok(count(t,"todos")==3&&call(t,"todoIds",new Class[]{}).equals(call(s,"todoIds",new Class[]{})),"restore replaces sentinel rather than merging and preserves todo order");
        ok(value(t,100,"choice").equals(List.of("b","a"))&&((CustomFields.Definition)definition(t,"number")).archived,"restore retains ordered choices and archived field values");
        ok(call(t,"fieldNoteIds",new Class[]{long.class,String.class},100L,"number").equals(List.of("n")),"restore retains field-note relationship");
        ok(importLegacy(t,legacy())==0,"restored legacy import journal still prevents duplicate import");ok(!batch(t,"latest",money),"restored money journal still prevents duplicate batch");
        reject(()->batch(t,"undone",List.of(row("u",100,"2026-09-01",100))),"restored undo tombstone rejects resurrection");
        restore(t,good,tm);ok(Arrays.equals(state(t),expected),"same complete backup can be restored repeatedly without duplicates");
        Files.write(c.getFilesDir().toPath().resolve("restore-expected.bin"),expected);Files.write(c.getFilesDir().toPath().resolve("restore-media-id.txt"),id.getBytes(java.nio.charset.StandardCharsets.US_ASCII));
        raw(s).execSQL("CREATE TABLE unregistered(value TEXT)");boolean unknown=false;try{state(s);}catch(IllegalArgumentException|IllegalStateException e){unknown=true;}ok(unknown,"new unregistered table cannot silently disappear from backup");raw(s).execSQL("DROP TABLE unregistered");
        close(s);close(t);
    }
    private void backupReopen()throws Exception{
        Context c=getTargetContext();Object t=db("backup-target.db");ok(Arrays.equals(state(t),Files.readAllBytes(c.getFilesDir().toPath().resolve("restore-expected.bin"))),"separate process retains complete restored state");
        String id=new String(Files.readAllBytes(c.getFilesDir().toPath().resolve("restore-media-id.txt")),java.nio.charset.StandardCharsets.US_ASCII);MediaRepository m=new MediaRepository(c.getFilesDir().toPath().resolve("backup-target-media"),1000000);m.verify(id);ok(Arrays.equals(Files.readAllBytes(m.path(id)),new byte[]{1,2,3,4,5}),"separate process retains restored media bytes");
        ok(total(t,100,Set.of(LocalDate.of(2026,9,1),LocalDate.of(2026,9,3)),"NET_EXPENSE")==1000,"restored exact-cent totals remain usable after restart");
        call(t,"undoBatch",new Class[]{String.class},"latest");ok(count(t,"ledger")==0,"restored latest batch undo works after separate-process restart");ok(importLegacy(t,legacy())==0,"restored import journal still works after restart");close(t);
    }

    private Object preview(Object d,Path archive,Path stage)throws Exception{return call(d,"prepareRestore",new Class[]{Path.class,Path.class,long.class},archive,stage,1000000L);}
    private void confirm(Object d,Object plan,MediaRepository media)throws Exception{call(d,"confirmRestore",new Class[]{plan.getClass(),MediaRepository.class},plan,media);}
    private boolean empty(Path dir)throws IOException{try(java.util.stream.Stream<Path> files=Files.list(dir)){return !files.findAny().isPresent();}}
    private void guardedSeed()throws Exception{
        Context c=getTargetContext();c.deleteDatabase("guarded.db");Object t=db("guarded.db"),source=db("backup-source.db");
        call(t,"addTodo",new Class[]{String.class,String.class},"local","保留本地");byte[] before=fixture(t),expected=fixture(source);
        Path good=c.getFilesDir().toPath().resolve("full-good.zip"),stage=c.getCacheDir().toPath().resolve("guarded-stage");Files.createDirectories(stage);
        MediaRepository media=new MediaRepository(c.getFilesDir().toPath().resolve("guarded-media"),1000000);
        String id=new String(Files.readAllBytes(c.getFilesDir().toPath().resolve("restore-media-id.txt")),java.nio.charset.StandardCharsets.US_ASCII);
        Object canceled=preview(t,good,stage);
        // MediaRepository.path requires an existing file; absence must be checked
        // independently against the fixture directory, not through that accessor.
        ok(Arrays.equals(fixture(t),before)&&!Files.exists(c.getFilesDir().toPath().resolve("guarded-media").resolve(id),LinkOption.NOFOLLOW_LINKS),"restore preview does not mutate any live table or publish media");
        @SuppressWarnings("unchecked") Map<String,Long> current=(Map<String,Long>)call(canceled,"currentCounts",new Class[]{});
        @SuppressWarnings("unchecked") Map<String,Long> incoming=(Map<String,Long>)call(canceled,"incomingCounts",new Class[]{});
        Map<String,Long> actualCurrent=new LinkedHashMap<>(),actualIncoming=new LinkedHashMap<>();
        for(String table:TABLES){try(android.database.Cursor a=raw(t).rawQuery("SELECT count(*) FROM "+table,null);android.database.Cursor b=raw(source).rawQuery("SELECT count(*) FROM "+table,null)){a.moveToFirst();b.moveToFirst();actualCurrent.put(table,a.getLong(0));actualIncoming.put(table,b.getLong(0));}}
        ok(current.equals(actualCurrent)&&incoming.equals(actualIncoming),"preview shows independent exact current and incoming counts for every table");
        boolean immutable=false;try{incoming.put("todos",999L);}catch(UnsupportedOperationException e){immutable=true;}ok(immutable,"restore preview summary cannot be modified by caller");
        close(canceled);close(canceled);ok(empty(stage)&&Arrays.equals(fixture(t),before),"cancel twice clears private staging without altering live state");
        reject(()->confirm(t,canceled,media),"canceled restore plan cannot be confirmed");
        boolean invalid=false;try{Object bad=preview(t,c.getFilesDir().toPath().resolve("full-bad.zip"),stage);close(bad);}catch(IOException|IllegalArgumentException|IllegalStateException e){invalid=true;}
        ok(invalid&&empty(stage)&&Arrays.equals(fixture(t),before),"semantic-invalid preview refuses and cleans staging without touching live data");
        Object foreign=preview(t,good,stage),other=db("guarded.db");
        reject(()->confirm(other,foreign,media),"restore preview is bound to its exact database helper owner");close(other);close(foreign);
        Object stale=preview(t,good,stage);call(t,"editTodo",new Class[]{String.class,String.class,boolean.class},"local","预览后的新内容",true);byte[] newer=fixture(t);
        reject(()->confirm(t,stale,media),"ordinary write after preview rejects stale restore");
        ok(Arrays.equals(fixture(t),newer)&&empty(stage),"stale rejection preserves every new row and revision and clears stage");
        reject(()->confirm(t,stale,media),"failed stale plan is single use and requires a new preview");
        Object sameRevision=preview(t,good,stage),writer=db("guarded.db");
        raw(writer).execSQL("UPDATE todos SET title='另一个连接写入' WHERE id='local'");close(writer);byte[] changed=fixture(t);
        reject(()->confirm(t,sameRevision,media),"full snapshot guard rejects another connection write even without revision bump");
        ok(Arrays.equals(fixture(t),changed),"same-revision stale rejection retains exact externally changed state");
        Object damaged=preview(t,good,stage);Path asset;
        try(java.util.stream.Stream<Path> paths=Files.walk(stage)){asset=paths.filter(p->p.getFileName().toString().equals(id)).findFirst().orElseThrow(()->new AssertionError("missing staged asset fixture"));}
        Files.write(asset,new byte[]{5,4,3,2,1});boolean corrupt=false;try{confirm(t,damaged,media);}catch(IOException e){corrupt=true;}
        ok(corrupt&&Arrays.equals(fixture(t),changed)&&empty(stage),"changed staged media is rejected on confirmation with complete old state intact");
        Object late=preview(t,good,stage);raw(t).execSQL("CREATE TEMP TRIGGER guarded_fault BEFORE INSERT ON todos WHEN NEW.id='own' BEGIN SELECT RAISE(ABORT,'guarded_commit_fault'); END");
        boolean injected=false;try{confirm(t,late,media);}catch(Exception e){for(Throwable x=e;x!=null;x=x.getCause())if(String.valueOf(x.getMessage()).contains("guarded_commit_fault"))injected=true;}
        ok(injected&&Arrays.equals(fixture(t),changed),"guarded confirmation late injected failure rolls back every replaced table");
        raw(t).execSQL("DROP TRIGGER guarded_fault");reject(()->confirm(t,late,media),"failed commit plan cannot be reused after removing the fault");
        Object frozen=preview(t,good,stage);byte[] zip=Files.readAllBytes(good);Files.write(good,new byte[]{0,1,2});
        try{confirm(t,frozen,media);}finally{Files.write(good,zip);}
        ok(Arrays.equals(fixture(t),expected),"confirmation uses the exact validated preview not a subsequently replaced source file");
        ok(Arrays.equals(Files.readAllBytes(media.path(id)),new byte[]{1,2,3,4,5})&&empty(stage),"confirmed snapshot publishes exact media and cleans staging before commit");
        reject(()->confirm(t,frozen,media),"successful confirmation cannot be replayed");
        Object noop=preview(t,good,stage);List<Ledger.Entry> money=List.of(row("m1",100,"2026-09-01",1500),new Ledger.Entry("m2",100,LocalDate.of(2026,9,3),Ledger.Kind.REFUND,500,"退款"));
        ok(!batch(t,"latest",money),"exact idempotent retry remains a genuine no-op while preview is open");
        confirm(t,noop,media);ok(Arrays.equals(fixture(t),expected)&&empty(stage),"unchanged state after no-op can still confirm the reviewed snapshot");
        close(source);close(t);
    }
    private void guardedReopen()throws Exception{
        Object t=db("guarded.db");ok(Arrays.equals(fixture(t),Files.readAllBytes(getTargetContext().getFilesDir().toPath().resolve("restore-expected.bin"))),"guarded restore survives a separate Android process with all tables exact");
        ok(importLegacy(t,legacy())==0&&total(t,100,Set.of(LocalDate.of(2026,9,1),LocalDate.of(2026,9,3)),"NET_EXPENSE")==1000,"guarded restore retains usable import journal and exact-cent totals after restart");close(t);
    }
    // Frozen historical schema2, not generated through current AppDatabase DDL/encoder.
    // Keep this old format fixed when schema3 arrives. This suite has its own counter;
    // failures throw through onStart and fail the existing mandatory seed/reopen gate.
    private int legacyChecks;
    private void legacyNeed(boolean value,String label){if(!value)throw new AssertionError(label);legacyChecks++;log.append("LEGACY_SCHEMA2_PASS ").append(label).append('\n');}
    private static final String[] V2_EXTRA_DDL={
        "CREATE TABLE fields(id TEXT PRIMARY KEY NOT NULL,name TEXT NOT NULL,type TEXT NOT NULL CHECK(type IN('TEXT','LONG_TEXT','NUMBER','DATE','SELECT','MULTI_SELECT','LINK','BOOLEAN')),archived INTEGER NOT NULL CHECK(archived IN(0,1)))",
        "CREATE TABLE field_options(field_id TEXT NOT NULL REFERENCES fields(id),id TEXT NOT NULL,position INTEGER NOT NULL CHECK(position>=0),PRIMARY KEY(field_id,id),UNIQUE(field_id,position))",
        "CREATE TABLE field_values(activity_id INTEGER NOT NULL REFERENCES activities(id),field_id TEXT NOT NULL REFERENCES fields(id),position INTEGER NOT NULL CHECK(position>=0),value TEXT NOT NULL,PRIMARY KEY(activity_id,field_id,position))",
        "CREATE TABLE field_notes(note_id TEXT PRIMARY KEY NOT NULL REFERENCES notes(id),field_id TEXT NOT NULL REFERENCES fields(id))",
        "CREATE TABLE todos(id TEXT PRIMARY KEY NOT NULL,title TEXT NOT NULL CHECK(length(trim(title))>0),done INTEGER NOT NULL CHECK(done IN(0,1)),position INTEGER NOT NULL CHECK(position>=0) UNIQUE)",
        "CREATE TABLE legacy_imports(source_id TEXT PRIMARY KEY NOT NULL,item_count INTEGER NOT NULL CHECK(item_count>=0))"
    };
    private byte[] frozenV2(SQLiteDatabase db)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(0x50544442);out.writeInt(1);out.writeInt(2);out.writeInt(TABLES.length);
        for(String table:TABLES){
            String columns=table.equals("blocks")?"note_id,id,position,kind,text,asset_id,caption,private":"*";
            try(android.database.Cursor c=db.rawQuery("SELECT "+columns+" FROM "+table+" ORDER BY rowid",null)){
                str(out,table);out.writeInt(c.getColumnCount());for(String name:c.getColumnNames())str(out,name);out.writeInt(c.getCount());
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){int type=c.getType(i);out.writeByte(type);switch(type){case 0:break;case 1:out.writeLong(c.getLong(i));break;case 3:str(out,c.getString(i));break;case 4:bytes(out,c.getBlob(i));break;default:throw new AssertionError("unexpected frozen SQL type");}}
            }
        }out.flush();return bytes.toByteArray();
    }
    private void frozenSeed()throws Exception{
        Context c=getTargetContext();c.deleteDatabase("frozen-v2.db");c.deleteDatabase("frozen-target.db");
        Path root=c.getFilesDir().toPath();MediaRepository sourceMedia=new MediaRepository(root.resolve("frozen-source-media"),1000000),targetMedia=new MediaRepository(root.resolve("frozen-target-media"),1000000);
        byte[] asset={97,98,99};String id=sourceMedia.copy(new ByteArrayInputStream(asset));byte[] legacy;
        try(SQLiteDatabase old=c.openOrCreateDatabase("frozen-v2.db",0,null)){
            old.setForeignKeyConstraintsEnabled(true);for(String sql:V1_DDL)old.execSQL(sql);for(String sql:V2_EXTRA_DDL)old.execSQL(sql);
            old.execSQL("INSERT INTO revision VALUES(1,42)");old.execSQL("INSERT INTO categories VALUES(7,'旧分类',0)");old.execSQL("INSERT INTO activities VALUES(9,7,NULL,'旧活动',0)");
            old.execSQL("INSERT INTO notes VALUES('first',9,'同名')");old.execSQL("INSERT INTO notes VALUES('second',9,'同名')");old.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',3)",new Object[]{id});
            old.execSQL("INSERT INTO blocks VALUES('first','photo',0,'IMAGE','',?,'原图说明',1)",new Object[]{id});old.execSQL("INSERT INTO blocks VALUES('second','photo',0,'IMAGE','',?,'同图另一篇',0)",new Object[]{id});
            old.execSQL("INSERT INTO blocks VALUES('second','text',1,'TEXT','保留私有文字',NULL,'',1)");old.execSQL("INSERT INTO todos VALUES('old-todo','旧待办',1,0)");
            old.execSQL("INSERT INTO fields VALUES('old-field','旧字段','TEXT',1)");old.execSQL("INSERT INTO field_values VALUES(9,'old-field',0,'归档值')");old.execSQL("INSERT INTO field_notes VALUES('second','old-field')");
            old.setVersion(2);
            try(android.database.Cursor cols=old.rawQuery("SELECT * FROM blocks LIMIT 0",null)){legacyNeed(old.getVersion()==2&&cols.getColumnCount()==8,"frozen fixture really uses schema2 and eight block columns");}
            legacy=frozenV2(old);
            byte[] changed;old.beginTransaction();try{old.execSQL("UPDATE blocks SET caption='corrupt' WHERE note_id='second' AND id='photo'");changed=frozenV2(old);}finally{old.endTransaction();}
            legacyNeed(!Arrays.equals(legacy,changed)&&Arrays.equals(legacy,frozenV2(old)),"frozen serializer detects a real changed row and rollback restores fixture");
        }
        Files.write(root.resolve("frozen-v2-state.bin"),legacy);Files.write(root.resolve("frozen-v2-media-id.txt"),id.getBytes(java.nio.charset.StandardCharsets.US_ASCII));
        Path good=root.resolve("frozen-v2.zip");Files.deleteIfExists(good);BackupArchive.write(good,legacy,Set.of(id),sourceMedia);
        try(BackupArchive.Snapshot snap=BackupArchive.read(good,c.getCacheDir().toPath(),1000000)){legacyNeed(Arrays.equals(snap.state(),legacy)&&snap.assets().keySet().equals(Set.of(id)),"archive wraps frozen old bytes without current database encoder");}
        Object upgraded=db("frozen-v2.db"),target=db("frozen-target.db");
        try{
            legacyNeed(Arrays.equals(frozenV2(raw(upgraded)),legacy),"opening frozen old database preserves all historical cells and ordering");
            call(target,"addTodo",new Class[]{String.class,String.class},"sentinel","恢复前保留");byte[] before=state(target);
            Path stage=c.getCacheDir().toPath().resolve("frozen-stage");Files.createDirectories(stage);
            Object canceled=preview(target,good,stage);close(canceled);
            legacyNeed(Arrays.equals(before,state(target))&&empty(stage)&&!Files.exists(root.resolve("frozen-target-media").resolve(id)),"cancel old-backup preview preserves live state and publishes no media");
            Object accepted=preview(target,good,stage);confirm(target,accepted,targetMedia);
            legacyNeed(Arrays.equals(frozenV2(raw(target)),legacy),"guarded old-backup restore preserves complete old-format projection");
            legacyNeed(Arrays.equals(Files.readAllBytes(targetMedia.path(id)),asset),"guarded old-backup restore publishes exact original bytes");
            legacyNeed(call(target,"fieldNoteIds",new Class[]{long.class,String.class},9L,"old-field").equals(List.of("second"))&&value(target,9,"old-field").equals(List.of("归档值")),"old archived field and note attachment survive restore");
            @SuppressWarnings("unchecked") List<NoteDocument.Block> first=(List<NoteDocument.Block>)call(target,"noteBlocks",new Class[]{String.class},"first");
            @SuppressWarnings("unchecked") List<NoteDocument.Block> second=(List<NoteDocument.Block>)call(target,"noteBlocks",new Class[]{String.class},"second");
            legacyNeed(first.size()==1&&second.size()==2&&first.get(0).privateContent&&!second.get(0).privateContent&&second.get(1).privateContent&&first.get(0).assetId.equals(second.get(0).assetId),"duplicate titles and shared image retain separate block privacy and ownership");
            byte[] stable=state(target);Path bad=root.resolve("frozen-v2-bad.zip");Files.deleteIfExists(bad);
            BackupArchive.write(bad,Arrays.copyOf(legacy,legacy.length-1),Set.of(id),sourceMedia);
            boolean refused=false;try{restore(target,bad,targetMedia);}catch(IOException|IllegalArgumentException|IllegalStateException e){refused=true;}
            legacyNeed(refused&&Arrays.equals(stable,state(target)),"truncated frozen state cannot replace current live data");
            Files.deleteIfExists(bad);BackupArchive.write(bad,legacy,Set.of(),sourceMedia);refused=false;
            try{restore(target,bad,targetMedia);}catch(IOException|IllegalArgumentException|IllegalStateException e){refused=true;}
            legacyNeed(refused&&Arrays.equals(stable,state(target)),"missing frozen original refuses restore without data loss");
            raw(target).execSQL("CREATE TEMP TRIGGER frozen_fault BEFORE INSERT ON todos WHEN NEW.id='old-todo' BEGIN SELECT RAISE(ABORT,'frozen_v2_commit_failure'); END");
            boolean exact=false;try{restore(target,good,targetMedia);}catch(Exception e){for(Throwable x=e;x!=null;x=x.getCause())if(String.valueOf(x.getMessage()).contains("frozen_v2_commit_failure"))exact=true;}
            legacyNeed(exact&&Arrays.equals(stable,state(target)),"late old-backup restore failure rolls back every deleted and inserted table");
            raw(target).execSQL("DROP TRIGGER frozen_fault");restore(target,good,targetMedia);
            legacyNeed(Arrays.equals(stable,state(target))&&Arrays.equals(Files.readAllBytes(targetMedia.path(id)),asset),"lower-level old restore stays deterministic and retains original bytes");
            Path round=root.resolve("frozen-roundtrip.zip");Files.deleteIfExists(round);backup(target,round,targetMedia);restore(upgraded,round,sourceMedia);
            legacyNeed(Arrays.equals(state(upgraded),state(target))&&Arrays.equals(frozenV2(raw(upgraded)),legacy),"current-format export and restore retain historical semantic content");
        }finally{close(upgraded);close(target);}
        if(legacyChecks!=14)throw new AssertionError("frozen seed assertion coverage drift: "+legacyChecks);
        log.append("LEGACY_SCHEMA2_RESULT seed ").append(legacyChecks).append('/').append(legacyChecks).append(" PASS\n");
    }
    private void frozenReopen()throws Exception{
        Context c=getTargetContext();Path root=c.getFilesDir().toPath();Object target=db("frozen-target.db");
        try{
            legacyNeed(Arrays.equals(frozenV2(raw(target)),Files.readAllBytes(root.resolve("frozen-v2-state.bin"))),"separate process retains complete frozen old-backup content");
            String id=new String(Files.readAllBytes(root.resolve("frozen-v2-media-id.txt")),java.nio.charset.StandardCharsets.US_ASCII);
            MediaRepository media=new MediaRepository(root.resolve("frozen-target-media"),1000000);media.verify(id);
            legacyNeed(Arrays.equals(Files.readAllBytes(media.path(id)),new byte[]{97,98,99}),"separate process retains exact shared original");
            legacyNeed((Boolean)member(todo(target,"old-todo"),"done")&&((CustomFields.Definition)definition(target,"old-field")).archived,"restored todo and archived field remain usable after process restart");
        }finally{close(target);}
        if(legacyChecks!=3)throw new AssertionError("frozen reopen assertion coverage drift: "+legacyChecks);
        log.append("LEGACY_SCHEMA2_RESULT reopen ").append(legacyChecks).append('/').append(legacyChecks).append(" PASS\n");
    }
    private void prepareUiBackup()throws Exception{
        // Runs in the isolated test APK process after native checks force-stop the UI.
        // The app holds no storage permission, so the fixture stays in app-private
        // storage; the host gate copies it out with run-as and pushes it to public
        // Download as the shell user. It never creates product data, skips product
        // SAF/UI assertions, or accepts a live process; release acceptance still
        // requires actual picker coverage.
        Context c=getTargetContext();boolean stopped=false;
        for(int i=0;i<50;i++){
            boolean live=false;for(java.io.File p:new java.io.File("/proc").listFiles())if(p.isDirectory())try{String name=new String(Files.readAllBytes(new java.io.File(p,"cmdline").toPath()),java.nio.charset.StandardCharsets.UTF_8);if(name.startsWith(c.getPackageName()+"\0")){live=true;break;}}catch(Exception ignored){}
            if(!live){stopped=true;break;}Thread.sleep(200);
        }
        if(!stopped)throw new IllegalStateException("UI process still running; backup fixture would copy a live database");
        Path data=c.getDataDir().toPath();
        for(String suffix:new String[]{"","-wal","-shm"}){Path source=data.resolve("databases/pocket-v12.db"+suffix);if(Files.exists(source))Files.copy(source,data.resolve("databases/ui-backup-source.db"+suffix),StandardCopyOption.REPLACE_EXISTING);}
        Path mediaTarget=data.resolve("files/ui-backup-media");Files.createDirectories(mediaTarget);
        Path media=data.resolve("files/pocket-v12-media");if(Files.isDirectory(media))try(java.util.stream.Stream<Path> files=Files.list(media)){for(Path p:(Iterable<Path>)files::iterator)Files.copy(p,mediaTarget.resolve(p.getFileName().toString()),StandardCopyOption.REPLACE_EXISTING);}
        Object d=db("ui-backup-source.db");MediaRepository m=new MediaRepository(mediaTarget,1000000);
        Path out=data.resolve("files/ui-export");Files.createDirectories(out);
        backup(d,out.resolve("PocketTodo-v12-backup.zip"),m);close(d);
        ok(Files.size(out.resolve("PocketTodo-v12-backup.zip"))>0,"UI backup fixture exported nonempty");
    }
    private static void restoreOwnerNeed(boolean condition,String label){if(!condition)throw new AssertionError("Restore preview lifecycle: "+label);}
    private static Set<Path> restoreOwnerChildren(Path root)throws IOException{
        try(java.util.stream.Stream<Path> files=Files.list(root)){return files.collect(java.util.stream.Collectors.toSet());}
    }
    private static boolean restoreOwnerInput(android.view.View v){
        if("新待办输入".contentEquals(v.getContentDescription()==null?"":v.getContentDescription()))return v.isEnabled()&&v.isAttachedToWindow();
        if(v instanceof android.view.ViewGroup){android.view.ViewGroup g=(android.view.ViewGroup)v;for(int i=0;i<g.getChildCount();i++)if(restoreOwnerInput(g.getChildAt(i)))return true;}
        return false;
    }
    private boolean restoreOwnerDialog(){
        android.view.accessibility.AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();if(root==null)return false;
        try{for(android.view.accessibility.AccessibilityNodeInfo n:root.findAccessibilityNodeInfosByText("我明白会替换本机数据")){
            try{if(n.isVisibleToUser()&&n.isCheckable()&&!n.isChecked()&&getTargetContext().getPackageName().contentEquals(n.getPackageName())&&"restore-consent".contentEquals(n.getContentDescription()==null?"":n.getContentDescription()))return true;}finally{n.recycle();}
        }return false;}finally{root.recycle();}
    }
    /** Independent from the private pending-plan field: prove the real unchecked
     * dialog was live, then finish its Activity and read the filesystem + SQL. */
    private void restorePreviewOwnerReopen()throws Exception{
        Context c=getTargetContext();String dbName="schema4-startup-ui.db";
        restoreOwnerNeed(!c.getDatabasePath(dbName).exists(),"refuse to replace an existing test database");
        Path cache=c.getCacheDir().toPath(),scope=Files.createTempDirectory(cache,"restore-life-probe-"),stage=Files.createDirectories(cache.resolve("restore-stage"));
        Path archive=scope.resolve("nonempty.zip"),chosen=scope.resolve("chosen.zip");byte[] payload={7,11,21,31,41},before;String mediaId;
        MediaRepository media=new MediaRepository(c.getFilesDir().toPath().resolve("media"),64L*1024*1024);
        try(AppDatabase d=AppDatabase.openForStartup(c,dbName)){
            mediaId=media.copy(new ByteArrayInputStream(payload));d.registerMedia(mediaId,"application/octet-stream",payload.length);
            d.addTodo("owner-before","预览前保留");d.exportBackup(archive,media);d.addTodo("owner-later","未确认不得覆盖");before=d.exportState();
        }
        Files.copy(archive,chosen);Set<Path> prior=restoreOwnerChildren(stage);MainActivity[] activity={null};TodayScreen[] screen={null};
        try(BackupArchive.Snapshot other=BackupArchive.read(archive,stage,64L*1024*1024)){
            Set<Path> keep=restoreOwnerChildren(stage),extra=new HashSet<>(keep);extra.removeAll(prior);restoreOwnerNeed(extra.size()==1,"positive sibling fixture");Path otherDir=extra.iterator().next();byte[] zipState=other.state();
            restoreOwnerNeed(zipState.length>0&&!Arrays.equals(zipState,before)&&Arrays.equals(Files.readAllBytes(other.assets().get(mediaId)),payload),"distinct nonempty incoming and current fixtures");
            MainActivity.isolatedStartupTest=true;
            try{
                activity[0]=(MainActivity)startActivitySync(new android.content.Intent(c,MainActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
                long until=android.os.SystemClock.uptimeMillis()+10000;
                while(screen[0]==null&&android.os.SystemClock.uptimeMillis()<until){runOnMainSync(()->{if(restoreOwnerInput(activity[0].getWindow().getDecorView()))screen[0]=activity[0].shortcutTestScreen();});if(screen[0]==null)android.os.SystemClock.sleep(25);}
                restoreOwnerNeed(screen[0]!=null,"native screen ready");java.util.concurrent.atomic.AtomicReference<Exception> failure=new java.util.concurrent.atomic.AtomicReference<>();
                runOnMainSync(()->{try{screen[0].previewRestore(chosen);}catch(Exception e){failure.set(e);}});if(failure.get()!=null)throw failure.get();
                boolean visible=false;until=android.os.SystemClock.uptimeMillis()+10000;
                while(!visible&&android.os.SystemClock.uptimeMillis()<until){visible=restoreOwnerDialog();if(!visible)android.os.SystemClock.sleep(25);}
                restoreOwnerNeed(visible&&!Files.exists(chosen),"real unchecked dialog and consumed input");
                Set<Path> showing=restoreOwnerChildren(stage),own=new HashSet<>(showing);own.removeAll(keep);
                restoreOwnerNeed(showing.containsAll(keep)&&own.size()==1,"one additional owned staging directory");Path privateDir=own.iterator().next();
                restoreOwnerNeed(Arrays.equals(Files.readAllBytes(privateDir.resolve("state.bin")),zipState)&&Arrays.equals(Files.readAllBytes(privateDir.resolve(mediaId)),payload),"reviewed private bytes before finish");
                runOnMainSync(activity[0]::finish);waitForIdleSync();restoreOwnerNeed(screen[0].awaitShortcutClose(),"existing close executor completed");
                restoreOwnerNeed(activity[0].isDestroyed()&&restoreOwnerChildren(stage).equals(keep)&&Files.notExists(privateDir),"only the abandoned stage vanished");
                restoreOwnerNeed(Arrays.equals(Files.readAllBytes(otherDir.resolve("state.bin")),zipState)&&Arrays.equals(Files.readAllBytes(other.assets().get(mediaId)),payload)&&Arrays.equals(Files.readAllBytes(media.path(mediaId)),payload),"live media and sibling snapshot survived");
                try(AppDatabase d=AppDatabase.openForStartup(c,dbName)){restoreOwnerNeed(Arrays.equals(d.exportState(),before),"complete state after reopen");}
                try(SQLiteDatabase sql=SQLiteDatabase.openDatabase(c.getDatabasePath(dbName).getPath(),null,SQLiteDatabase.OPEN_READONLY);android.database.Cursor rows=sql.rawQuery("SELECT id,title,done FROM todos ORDER BY position",null)){
                    restoreOwnerNeed(rows.moveToFirst()&&rows.getString(0).equals("owner-before")&&rows.getString(1).equals("预览前保留")&&rows.getInt(2)==0&&rows.moveToNext()&&rows.getString(0).equals("owner-later")&&rows.getString(1).equals("未确认不得覆盖")&&rows.getInt(2)==0&&!rows.moveToNext(),"independent SQL retained both exact rows");}
                log.append("RESTORE_OWNER_DEVICE unchecked_finish_owned_stage_gone_sibling_media_sql_unchanged PASS\n");
            }finally{if(activity[0]!=null&&!activity[0].isFinishing()&&!activity[0].isDestroyed())runOnMainSync(activity[0]::finish);MainActivity.isolatedStartupTest=false;}
        }finally{BackupArchive.deleteTree(scope);}
    }
    private void appendNeed(boolean value,String why){if(!value)throw new AssertionError("legacy append: "+why);}
    private byte[] appendShell(String command)throws IOException{
        // Only fixed utilities and our generated synthetic fixture paths on a disposable emulator.
        try(InputStream in=new android.os.ParcelFileDescriptor.AutoCloseInputStream(getUiAutomation().executeShellCommand(command))){
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] block=new byte[1024];int n;
            while((n=in.read(block))!=-1){if(n<=0||out.size()+n>8192)throw new IOException("fixture command size");out.write(block,0,n);}return out.toByteArray();
        }
    }
    private byte[] appendCells(String dbName,boolean all)throws Exception{
        ByteArrayOutputStream buf=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(buf);
        try(SQLiteDatabase sql=SQLiteDatabase.openDatabase(getTargetContext().getDatabasePath(dbName).getPath(),null,SQLiteDatabase.OPEN_READONLY)){
            for(String table:TABLES){if(!all&&(table.equals("revision")||table.equals("todos")||table.equals("legacy_imports")))continue;
                try(android.database.Cursor c=sql.rawQuery("SELECT rowid,* FROM "+table+" ORDER BY rowid",null)){
                    str(out,table);out.writeInt(c.getCount());for(String name:c.getColumnNames())str(out,name);
                    while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){int t=c.getType(i);out.writeByte(t);switch(t){case 0:break;case 1:out.writeLong(c.getLong(i));break;case 3:str(out,c.getString(i));break;case 4:bytes(out,c.getBlob(i));break;default:throw new AssertionError("unexpected SQL type");}}
                }
            }
        }out.flush();return buf.toByteArray();
    }
    private void appendButtons(android.view.View v,String text,List<android.widget.Button> found){
        if(v instanceof android.widget.Button&&text.contentEquals(((android.widget.Button)v).getText())&&v.isAttachedToWindow()&&v.isShown()&&v.isEnabled())found.add((android.widget.Button)v);
        if(v instanceof android.view.ViewGroup){android.view.ViewGroup g=(android.view.ViewGroup)v;for(int i=0;i<g.getChildCount();i++)appendButtons(g.getChildAt(i),text,found);}
    }
    private void appendClick(MainActivity a,String label,long budget)throws Exception{
        long end=Math.min(budget,android.os.SystemClock.uptimeMillis()+10000);boolean[] clicked={false};
        while(!clicked[0]&&android.os.SystemClock.uptimeMillis()<end){runOnMainSync(()->{
            List<android.widget.Button> found=new ArrayList<>();appendButtons(a.getWindow().getDecorView(),label,found);
            appendNeed(found.size()<=1,"ambiguous app action "+label);
            if(found.size()==1){android.widget.Button b=found.get(0);b.requestRectangleOnScreen(new android.graphics.Rect(0,0,b.getWidth(),b.getHeight()),true);
                android.graphics.Rect box=new android.graphics.Rect();if(b.getGlobalVisibleRect(box)&&!box.isEmpty())clicked[0]=b.performClick();}
        });if(!clicked[0])android.os.SystemClock.sleep(25);}
        appendNeed(clicked[0],"app action missing "+label);waitForIdleSync();
    }
    private android.graphics.Rect appendRect(String text,String viewId,boolean system,boolean exact){
        android.view.accessibility.AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();if(root==null)return null;
        try{
            String pkg=String.valueOf(root.getPackageName());if(system?!(pkg.equals("com.android.documentsui")||pkg.equals("com.google.android.documentsui")):!getTargetContext().getPackageName().equals(pkg))return null;
            android.graphics.Rect result=null;
            for(android.view.accessibility.AccessibilityNodeInfo n:root.findAccessibilityNodeInfosByText(text)){
                try{String value=String.valueOf(n.getText());if(!pkg.contentEquals(n.getPackageName())||!viewId.equals(n.getViewIdResourceName())||!n.isVisibleToUser()||!n.isEnabled()||!(exact?value.equals(text):value.contains(text)))continue;
                    android.graphics.Rect box=new android.graphics.Rect();n.getBoundsInScreen(box);if(box.isEmpty())continue;
                    appendNeed(result==null,"ambiguous visible node "+text);result=box;
                }finally{n.recycle();}
            }return result;
        }finally{root.recycle();}
    }
    // Use the visible target's advertised Android accessibility action. A normal
    // instrumentation pointer belongs to this app, not the external system picker.
    // Never click a guessed point, the whole directory, or any other filename.
    private boolean appendFileRow(android.view.accessibility.AccessibilityNodeInfo row,String pkg,String label){
        if(!row.isVisibleToUser()||!row.isEnabled()||!pkg.contentEquals(row.getPackageName()))return false;
        android.view.accessibility.AccessibilityNodeInfo parent=row.getParent();boolean directItem=false;
        try{if(parent!=null&&pkg.contentEquals(parent.getPackageName())){
            String cls=String.valueOf(parent.getClassName()),id=String.valueOf(parent.getViewIdResourceName());
            directItem=cls.endsWith("RecyclerView")||cls.endsWith("GridView")||cls.endsWith("ListView")||id.equals(pkg+":id/dir_list")||id.equals(pkg+":id/directory_list");
        }}finally{if(parent!=null)parent.recycle();}
        if(!directItem&&!(pkg+":id/item_root").equals(row.getViewIdResourceName()))return false;
        int names=0,matched=0;
        for(android.view.accessibility.AccessibilityNodeInfo n:row.findAccessibilityNodeInfosByViewId("android:id/title")){
            try{if(n.isVisibleToUser()){names++;if(label.contentEquals(n.getText()==null?"":n.getText())&&pkg.contentEquals(n.getPackageName()))matched++;}}finally{n.recycle();}
        }
        return names==1&&matched==1;
    }
    private void appendSemanticClick(String text,String id,boolean system,android.graphics.Rect observed,long deadline){
        android.view.accessibility.AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow(),one=null,target=null;
        appendNeed(root!=null,"missing window before click");
        try{
            String pkg=String.valueOf(root.getPackageName());appendNeed(system?(pkg.equals("com.android.documentsui")||pkg.equals("com.google.android.documentsui")):getTargetContext().getPackageName().equals(pkg),"window changed before click");
            for(android.view.accessibility.AccessibilityNodeInfo n:root.findAccessibilityNodeInfosByText(text)){
                try{if(!n.isVisibleToUser()||!n.isEnabled()||!pkg.contentEquals(n.getPackageName())||!id.equals(n.getViewIdResourceName())||!text.contentEquals(n.getText()==null?"":n.getText()))continue;
                    android.graphics.Rect b=new android.graphics.Rect();n.getBoundsInScreen(b);appendNeed(one==null&&observed.equals(b),"ambiguous or moved target before click");one=android.view.accessibility.AccessibilityNodeInfo.obtain(n);
                }finally{n.recycle();}
            }
            appendNeed(one!=null,"target disappeared");target=android.view.accessibility.AccessibilityNodeInfo.obtain(one);
            for(int level=0;target!=null&&level<8;level++){
                boolean owned=level==0||system&&appendFileRow(target,pkg,text);
                if(owned&&target.isVisibleToUser()&&target.isEnabled()&&pkg.contentEquals(target.getPackageName())&&target.getActionList().contains(android.view.accessibility.AccessibilityNodeInfo.AccessibilityAction.ACTION_CLICK)){
                    appendNeed(android.os.SystemClock.uptimeMillis()<deadline,"click deadline");appendNeed(target.performAction(android.view.accessibility.AccessibilityNodeInfo.ACTION_CLICK),"advertised click refused");return;
                }
                if(!system)break;android.view.accessibility.AccessibilityNodeInfo p=target.getParent();target.recycle();target=p;
            }
            throw new AssertionError("legacy append: exact item has no owned accessible click: "+id+" / "+text);
        }finally{if(target!=null)target.recycle();if(one!=null)one.recycle();root.recycle();}
    }
    private void appendObserve(String text,String id,boolean system,boolean click,boolean exact,long budget)throws Exception{
        long until=Math.min(budget,android.os.SystemClock.uptimeMillis()+(system?20000:10000));android.graphics.Rect last=null;
        while(android.os.SystemClock.uptimeMillis()<until){android.graphics.Rect now=appendRect(text,id,system,exact);
            if(now!=null&&now.equals(last)&&android.os.SystemClock.uptimeMillis()<until){
                if(click){appendSemanticClick(text,id,system,now,until);waitForIdleSync();}return;
            }last=now;android.os.SystemClock.sleep(35);
        }throw new AssertionError("legacy append visible node deadline: "+id+" / "+text);
    }
    private void appendRows(String dbName,String source)throws Exception{
        try(SQLiteDatabase sql=SQLiteDatabase.openDatabase(getTargetContext().getDatabasePath(dbName).getPath(),null,SQLiteDatabase.OPEN_READONLY);
            android.database.Cursor c=sql.rawQuery("SELECT id,title,done,position FROM todos ORDER BY position",null);
            android.database.Cursor journal=sql.rawQuery("SELECT source_id,item_count FROM legacy_imports",null)){
            String[] ids={"append-local","legacy-"+source+"-1","legacy-"+source+"-2"};int[] done={0,0,1};
            for(int i=0;i<3;i++)appendNeed(c.moveToNext()&&ids[i].equals(c.getString(0))&&"同名记录".equals(c.getString(1))&&c.getInt(2)==done[i]&&c.getInt(3)==i,"stable appended identity, title, state and order "+i);
            appendNeed(!c.moveToNext()&&journal.moveToFirst()&&source.equals(journal.getString(0))&&journal.getInt(1)==2&&!journal.moveToNext(),"one journal, no extra rows");
        }
    }
    /** The ActivityMonitor only sets the system picker's initial DIRECTORY. It never
     * substitutes a result, supplies a file URI to the app, or grants permissions.
     * Test file creation targets only our unique synthetic directory on the CI AVD. */
    private void legacyAppendNative()throws Exception{
        Context c=getTargetContext();appendNeed("com.supercubegame.pockettodo.v12.preview".equals(c.getPackageName())&&"ranchu".equals(android.os.Build.HARDWARE),"refuse non-CI device or package");
        String name="schema4-activation-ui.db";appendNeed(!c.getDatabasePath(name).exists(),"refuse existing isolated fixture");
        TodoModel old=new TodoModel();old.add("同名记录");long done=old.add("同名记录");old.toggle(done);byte[] wire=BackupCodec.encode(old);
        StringBuilder sha=new StringBuilder();for(byte b:java.security.MessageDigest.getInstance("SHA-256").digest(wire))sha.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
        try(AppDatabase fresh=AppDatabase.openForStartup(c,name)){fresh.addTodo("append-local","同名记录");fresh.addCategory(7,"保留分类");fresh.addActivity(71,7,0,"保留活动");fresh.recordBatch("keep-money",List.of(row("keep-entry",71,"2028-02-29",108)));}
        byte[] initial=appendCells(name,true),side=appendCells(name,false);String folder="pocket-append-ci-api"+android.os.Build.VERSION.SDK_INT,file="old-todos.txt";
        String dest="/sdcard/Download/"+folder+"/"+file;
        byte[] published=appendShell("cat "+dest);appendNeed(Arrays.equals(published,wire),"exact external picker fixture bytes, expected="+wire.length+" actual="+published.length);
        java.util.concurrent.atomic.AtomicInteger opens=new java.util.concurrent.atomic.AtomicInteger();android.app.Instrumentation.ActivityMonitor monitor=new android.app.Instrumentation.ActivityMonitor(){
            @Override public android.app.Instrumentation.ActivityResult onStartActivity(android.content.Intent intent){
                if(android.content.Intent.ACTION_OPEN_DOCUMENT.equals(intent.getAction())){
                    appendNeed(intent.hasCategory(android.content.Intent.CATEGORY_OPENABLE)&&"*/*".equals(intent.getType())&&intent.getComponent()==null&&intent.getData()==null&&(intent.getFlags()&android.content.Intent.FLAG_GRANT_WRITE_URI_PERMISSION)==0,"actual append intent is document selection, not replacement or writing");
                    opens.incrementAndGet();intent.putExtra(android.provider.DocumentsContract.EXTRA_INITIAL_URI,android.provider.DocumentsContract.buildDocumentUri("com.android.externalstorage.documents","primary:Download/"+folder));
                }return null;
            }
        };
        MainActivity ui=null;android.accessibilityservice.AccessibilityServiceInfo info=getUiAutomation().getServiceInfo();int flags=info.flags;info.flags|=android.accessibilityservice.AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;getUiAutomation().setServiceInfo(info);
        addMonitor(monitor);MainActivity.isolatedActivationTest=true;long end=android.os.SystemClock.uptimeMillis()+60000;
        try{
            ui=(MainActivity)startActivitySync(new android.content.Intent(c,MainActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
            appendClick(ui,"活动",end);appendClick(ui,"备份 / 恢复",end);
            for(int pass=0;pass<3;pass++){
                appendClick(ui,"追加旧版待办",end);appendObserve(file,"android:id/title",true,true,true,end);
                appendObserve("文件共 2 条：已完成 1 条，未完成 1 条。","android:id/message",false,false,false,end);
                if(pass==0){appendNeed(Arrays.equals(initial,appendCells(name,true)),"preview does not write");appendObserve("取消","android:id/button2",false,true,true,end);appendNeed(Arrays.equals(initial,appendCells(name,true)),"cancel retains every typed SQL cell");log.append("LEGACY_APPEND_NATIVE exact_picker_preview_and_cancel PASS\n");}
                else if(pass==1){appendObserve("确认追加","android:id/button1",false,true,true,end);
                    long until=Math.min(end,android.os.SystemClock.uptimeMillis()+10000);boolean committed=false;while(!committed&&android.os.SystemClock.uptimeMillis()<until){try(SQLiteDatabase s=SQLiteDatabase.openDatabase(c.getDatabasePath(name).getPath(),null,SQLiteDatabase.OPEN_READONLY);android.database.Cursor row=s.rawQuery("SELECT COUNT(*) FROM legacy_imports",null)){committed=row.moveToFirst()&&row.getLong(0)==1;}if(!committed)android.os.SystemClock.sleep(30);}
                    appendNeed(committed,"positive commit observed");appendRows(name,sha.toString());appendNeed(Arrays.equals(side,appendCells(name,false)),"all non-append business cells unchanged");log.append("LEGACY_APPEND_NATIVE real_confirmation_exact_ids_and_untouched_business PASS\n");}
                else{byte[] stable=appendCells(name,true);appendObserve("这份文件已在本机迁入","android:id/message",false,false,false,end);appendNeed(appendRect("确认追加","android:id/button1",false,true)==null,"duplicate source must not offer a write");appendObserve("关闭","android:id/button2",false,true,true,end);appendNeed(Arrays.equals(stable,appendCells(name,true)),"duplicate review no SQL change");}
            }
            appendNeed(opens.get()==3,"three distinct picker requests");final MainActivity closing=ui;final TodayScreen[] screen={null};runOnMainSync(()->{screen[0]=closing.shortcutTestScreen();closing.finish();});waitForIdleSync();
            appendNeed(screen[0]!=null&&screen[0].awaitShortcutClose(),"native screen closed");appendRows(name,sha.toString());appendNeed(Arrays.equals(side,appendCells(name,false)),"preserved after close and independent reopen");log.append("LEGACY_APPEND_NATIVE duplicate_and_database_reopen PASS\n");
        }finally{if(ui!=null&&!ui.isFinishing()&&!ui.isDestroyed()){final MainActivity a=ui;runOnMainSync(a::finish);}MainActivity.isolatedActivationTest=false;removeMonitor(monitor);info.flags=flags;getUiAutomation().setServiceInfo(info);}
    }
    private static void moneyNeed(boolean pass,String label){if(!pass)throw new AssertionError("calendar batch: "+label);}
    private void moneyPass(String label){log.append("CALENDAR_BATCH_NATIVE ").append(label).append(" PASS\n");}
    private static long scalar(SQLiteDatabase db,String query,String... args){try(android.database.Cursor c=db.rawQuery(query,args)){moneyNeed(c.moveToFirst(),"scalar row");return c.getLong(0);}}
    private long moneyScalar(String database,String query,String... args){try(SQLiteDatabase db=SQLiteDatabase.openDatabase(getTargetContext().getDatabasePath(database).getPath(),null,SQLiteDatabase.OPEN_READONLY)){return scalar(db,query,args);}}
    private void moneyControls()throws Exception{
        Context c=getTargetContext();String n="calendar-contracts-ci.db";moneyNeed(!c.getDatabasePath(n).exists(),"refuse existing schema3 fixture");
        try(AppDatabase s=AppDatabase.openForStartup(c,n)){
            s.addCategory(7,"测试");s.addActivity(71,7,0,"同名");s.addActivity(72,7,0,"同名");s.addTodo("keep","数据保留");
            List<Ledger.Entry> r=List.of(row("b1",71,"2028-02-29",125),row("b2",71,"2028-03-01",0));byte[] before=appendCells(n,true);SQLiteDatabase sql=s.getWritableDatabase();
            sql.execSQL("CREATE TEMP TRIGGER money_changed AFTER INSERT ON ledger WHEN NEW.position=1 BEGIN UPDATE ledger SET cents=cents+3 WHERE id=NEW.id; END");
            boolean exact=false;try{s.recordActivityBatch(71,"cal-1",r);}catch(IllegalStateException expected){exact="批次写后核对失败".equals(expected.getMessage());}finally{sql.execSQL("DROP TRIGGER money_changed");}
            moneyNeed(exact&&Arrays.equals(before,appendCells(n,true)),"silent second-line amount change rolled back including journal and revision");
            sql.execSQL("CREATE TEMP TRIGGER money_late BEFORE INSERT ON ledger WHEN NEW.position=1 BEGIN SELECT RAISE(ABORT,'money_late_fixture'); END");
            boolean late=false;try{s.recordActivityBatch(71,"cal-1",r);}catch(RuntimeException e){for(Throwable x=e;x!=null;x=x.getCause())if(String.valueOf(x.getMessage()).contains("money_late_fixture"))late=true;}finally{sql.execSQL("DROP TRIGGER money_late");}
            moneyNeed(late&&Arrays.equals(before,appendCells(n,true)),"late second-line failure rolled back all cells");
            moneyNeed(s.recordActivityBatch(71,"cal-1",r),"first save");byte[] saved=appendCells(n,true);moneyNeed(!s.recordActivityBatch(71,"cal-1",r)&&Arrays.equals(saved,appendCells(n,true)),"idempotent replay exact");
            boolean clash=false;try{s.recordActivityBatch(71,"cal-1",List.of(row("b1",71,"2028-02-29",126)));}catch(IllegalStateException e){clash=true;}
            boolean sameId=false;try{s.recordActivityBatch(71,"cal-2",List.of(row("new-id",71,"2028-03-02",321),r.get(0)));}catch(IllegalArgumentException e){sameId=true;}
            boolean other=false;try{s.recordActivityBatch(71,"cal-3",List.of(r.get(0),row("foreign",72,"2028-03-02",1)));}catch(IllegalArgumentException e){other=true;}
            moneyNeed(clash&&sameId&&other&&Arrays.equals(saved,appendCells(n,true)),"same key changed, other key duplicated ID, and cross-activity rows refused");
            AppDatabase.MoneyUndoReview stale=s.latestMoneyUndo(71);moneyNeed(stale!=null&&s.latestMoneyUndo(72)==null,"undo restricted to owner");s.addTodo("later","保留后续更改");byte[] newer=appendCells(n,true);boolean refused=false;
            try{s.undoActivityBatch(stale);}catch(IllegalStateException e){refused=true;}moneyNeed(refused&&s.latestMoneyUndo(71)==null&&Arrays.equals(newer,appendCells(n,true)),"stale undo cannot remove later data");
            s.recordActivityBatch(71,"cal-fresh",List.of(row("fresh",71,"2028-03-01",900)));AppDatabase.MoneyUndoReview token=s.latestMoneyUndo(71);s.undoActivityBatch(token);byte[] undone=appendCells(n,true);
            boolean twice=false,resurrect=false;try{s.undoActivityBatch(token);}catch(IllegalStateException e){twice=true;}try{s.recordActivityBatch(71,"cal-fresh",List.of(row("fresh",71,"2028-03-01",900)));}catch(IllegalStateException e){resurrect=true;}
            moneyNeed(twice&&resurrect&&Arrays.equals(undone,appendCells(n,true)),"consumed undo and tombstone cannot replay");
        }moneyPass("schema3_atomic_replay_owner_and_undo_guards");
    }
    private static void moneyViews(android.view.View view,String id,boolean edit,boolean desc,List<android.view.View> found){
        if(view.isAttachedToWindow()&&view.isShown()&&view.isEnabled()){
            boolean type=edit?view instanceof android.widget.EditText:view instanceof android.widget.Button;
            if(type){String label=String.valueOf(desc?view.getContentDescription():((android.widget.TextView)view).getText());if(id.equals(label))found.add(view);}
        }
        if(view instanceof android.view.ViewGroup){android.view.ViewGroup g=(android.view.ViewGroup)view;for(int i=0;i<g.getChildCount();i++)moneyViews(g.getChildAt(i),id,edit,desc,found);}
    }
    private android.app.AlertDialog moneyDialog(CalendarScreen cal)throws Exception{
        java.lang.reflect.Field f=CalendarScreen.class.getDeclaredField("activeMoney");f.setAccessible(true);Object owner=f.get(cal);if(owner==null)return null;
        java.lang.reflect.Field d=owner.getClass().getDeclaredField("box");d.setAccessible(true);return (android.app.AlertDialog)d.get(owner);
    }
    /** Reflection is only used to locate the current Dialog's window; all edits/clicks
     * go through real visible widgets. The oracle opens a separate read-only SQLite handle. */
    private void moneyAct(CalendarScreen cal,String id,String text,long end)throws Exception{
        long until=Math.min(end,android.os.SystemClock.uptimeMillis()+7000);boolean[] done={false};
        while(!done[0]&&android.os.SystemClock.uptimeMillis()<until){runOnMainSync(()->{
            try{android.app.AlertDialog dlg=moneyDialog(cal);if(dlg==null||!dlg.isShowing())return;
                List<android.view.View> found=new ArrayList<>();moneyViews(dlg.getWindow().getDecorView(),id,text!=null,text!=null,found);moneyNeed(found.size()<=1,"duplicate dialog action "+id);
                if(found.size()==1){android.view.View v=found.get(0);v.requestRectangleOnScreen(new android.graphics.Rect(0,0,v.getWidth(),v.getHeight()),true);android.graphics.Rect visible=new android.graphics.Rect();if(!v.getGlobalVisibleRect(visible)||visible.isEmpty())return;
                    if(text==null&&v instanceof android.widget.RadioButton){
                        android.widget.RadioButton radio=(android.widget.RadioButton)v;
                        moneyNeed(radio.getParent() instanceof android.widget.RadioGroup&&radio.getId()>0,"radio is outside its group: "+id);
                        android.widget.RadioGroup group=(android.widget.RadioGroup)radio.getParent();
                        if(!radio.isChecked()||group.getCheckedRadioButtonId()!=radio.getId())radio.performClick();
                        moneyNeed(radio.isChecked()&&group.getCheckedRadioButtonId()==radio.getId(),"radio did not select the requested item: "+id);
                        done[0]=true;
                    }else if(text==null){moneyNeed(v.performClick(),"ordinary button did not handle click: "+id);done[0]=true;}
                    else{((android.widget.EditText)v).setText(text);done[0]=true;}}
            }catch(ReflectiveOperationException e){throw new AssertionError(e);}catch(Exception e){throw new AssertionError(e);}
        });if(!done[0])android.os.SystemClock.sleep(25);}moneyNeed(done[0],"missing visible dialog action "+id);waitForIdleSync();
    }
    private void moneyLine(CalendarScreen cal,String day,String kind,String amount,boolean preset,long end)throws Exception{
        moneyAct(cal,"批次日期",day,end);moneyAct(cal,kind,null,end);if(preset)moneyAct(cal,amount+" 元",null,end);else moneyAct(cal,"批次金额（元）",amount,end);moneyAct(cal,"加入本行",null,end);
    }
    private byte[] moneySide(String n,long activity)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        try(SQLiteDatabase db=SQLiteDatabase.openDatabase(getTargetContext().getDatabasePath(n).getPath(),null,SQLiteDatabase.OPEN_READONLY)){
            List<String> tables=new ArrayList<>(Arrays.asList(TABLES));tables.add("category_shortcuts");
            for(String t:tables){if(t.equals("revision"))continue;
                String where=t.equals("ledger")?" WHERE activity_id<>?":t.equals("batches")?" WHERE id IN (SELECT batch_id FROM ledger WHERE activity_id<>?)":"";
                String query=t.equals("category_shortcuts")?"SELECT * FROM category_shortcuts ORDER BY category_id,application_id":"SELECT rowid,* FROM "+t+where+" ORDER BY rowid";
                try(android.database.Cursor v=db.rawQuery(query,where.isEmpty()?null:new String[]{Long.toString(activity)})){
                    str(out,t);out.writeInt(v.getColumnCount());out.writeInt(v.getCount());while(v.moveToNext())for(int i=0;i<v.getColumnCount();i++){int k=v.getType(i);out.writeByte(k);switch(k){case 0:break;case 1:out.writeLong(v.getLong(i));break;case 3:str(out,v.getString(i));break;case 4:bytes(out,v.getBlob(i));break;default:throw new AssertionError("type");}}
                }
            }
        }out.flush();return bytes.toByteArray();
    }
    private void calendarBatchPhase()throws Exception{
        Context c=getTargetContext();moneyNeed("com.supercubegame.pockettodo.v12.preview".equals(c.getPackageName())&&"ranchu".equals(android.os.Build.HARDWARE)&&android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"CI preview only");
        ciCalendarBoundary("enter_backend_controls");moneyControls();ciCalendarBoundary("prepare_workbench");String n="schema4-ui.db";moneyNeed(!c.getDatabasePath(n).exists(),"isolated native UI database must be new");
        try(AppDatabase s=AppDatabase.openSchema4(c,n)){s.addCategory(7,"分类");s.addApplication(9,"应用","");s.addActivity(71,7,9,"同名账本");s.addActivity(72,7,9,"同名账本");s.setShortcut(7,9,true);s.addTodo("keep-ui","非空本机待办");s.recordBatch("unrelated",List.of(row("other-row",72,"2028-03-01",999)));}
        ciCalendarBoundary("snapshot_nonempty_fixture");byte[] base=appendCells(n,true),other=moneySide(n,71);long rev=moneyScalar(n,"SELECT value FROM revision WHERE id=1");long end=android.os.SystemClock.uptimeMillis()+55000;MainActivity a=null;
        try{
            ciCalendarBoundary("launch_workbench");MainActivity.isolatedShortcutTest=true;a=(MainActivity)startActivitySync(new android.content.Intent(c,MainActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));final MainActivity activity=a;final TodayScreen host=a.shortcutTestScreen();moneyNeed(host!=null,"real schema4 test workbench");
            boolean ready=false;long until=Math.min(end,android.os.SystemClock.uptimeMillis()+7000);while(!ready&&android.os.SystemClock.uptimeMillis()<until){boolean[] seen={false};runOnMainSync(()->{List<android.widget.Button> b=new ArrayList<>();appendButtons(activity.getWindow().getDecorView(),"备份 / 恢复",b);seen[0]=b.size()==1;});ready=seen[0];if(!ready)android.os.SystemClock.sleep(25);}moneyNeed(ready,"workbench ready");
            ciCalendarBoundary("open_calendar");final CalendarScreen cal=new CalendarScreen(host,71,"同名账本",()->{});runOnMainSync(cal::load);appendClick(a,"批量记账",end);
            ciCalendarBoundary("first_preview");moneyLine(cal,"2028-02-29","支出","5",true,end);moneyAct(cal,"核对批次",null,end);moneyNeed(Arrays.equals(base,appendCells(n,true)),"review is read-only");moneyAct(cal,"取消",null,end);moneyNeed(Arrays.equals(base,appendCells(n,true)),"cancel is read-only");moneyPass("preview_and_cancel_preserve_all_business_cells");
            ciCalendarBoundary("six_row_batch");appendClick(a,"批量记账",end);String[] days={"2028-02-28","2028-02-29","2028-03-01","2028-03-01","2028-03-01","2028-03-01"},kinds={"支出","支出","支出","退款","收入","预计"},types={"EXPENSE","EXPENSE","EXPENSE","REFUND","INCOME","PLANNED"},yuan={"0","1.25","13","1","2.50","9"};long[] cents={0,125,1300,100,250,900};
            for(int i=0;i<6;i++)moneyLine(cal,days[i],kinds[i],yuan[i],i==0,end);moneyAct(cal,"核对批次",null,end);moneyNeed(Arrays.equals(base,appendCells(n,true)),"not saved by review");moneyAct(cal,"确认记账",null,end);
            appendClick(a,"撤销最近批次",end);String key;Set<String> ids=new HashSet<>();try(SQLiteDatabase s=SQLiteDatabase.openDatabase(c.getDatabasePath(n).getPath(),null,SQLiteDatabase.OPEN_READONLY);android.database.Cursor rows=s.rawQuery("SELECT id,day,kind,cents,position,batch_id FROM ledger WHERE activity_id=71 ORDER BY position",null)){
                String current=null;for(int i=0;i<6;i++){moneyNeed(rows.moveToNext()&&ids.add(rows.getString(0))&&days[i].equals(rows.getString(1))&&types[i].equals(rows.getString(2))&&cents[i]==rows.getLong(3)&&i==rows.getLong(4),"exact row "+i);if(i==0)current=rows.getString(5);moneyNeed(current!=null&&current.equals(rows.getString(5)),"all rows one batch");}moneyNeed(!rows.moveToNext()&&scalar(s,"SELECT value FROM revision")==rev+1&&scalar(s,"SELECT COUNT(*) FROM ledger WHERE activity_id=71 AND day='2028-03-02'")==0,"one revision and absent day");key=current;
                moneyNeed(scalar(s,"SELECT SUM(cents) FROM ledger WHERE activity_id=71 AND kind='EXPENSE'")==1425&&scalar(s,"SELECT count(DISTINCT day) FROM ledger WHERE activity_id=71 AND kind<>'PLANNED'")==3,"independent expense and actual days");
            }moneyNeed(Arrays.equals(other,moneySide(n,71)),"unrelated business tables unchanged");moneyPass("six_ordered_rows_one_key_zero_missing_leap_four_kinds");
            ciCalendarBoundary("start_undo");byte[] committed=appendCells(n,true);moneyAct(cal,"取消",null,end);moneyNeed(Arrays.equals(committed,appendCells(n,true)),"cancel undo is read-only");appendClick(a,"撤销最近批次",end);moneyAct(cal,"确认撤销",null,end);
            until=Math.min(end,android.os.SystemClock.uptimeMillis()+8000);while(moneyScalar(n,"SELECT value FROM revision")!=rev+2&&android.os.SystemClock.uptimeMillis()<until)android.os.SystemClock.sleep(25);
            moneyNeed(moneyScalar(n,"SELECT value FROM revision")==rev+2&&moneyScalar(n,"SELECT count(*) FROM ledger WHERE activity_id=71")==0&&moneyScalar(n,"SELECT cents FROM ledger WHERE id='other-row' AND activity_id=72")==999&&moneyScalar(n,"SELECT undone FROM batches WHERE id=?",key)==1&&Arrays.equals(other,moneySide(n,71)),"undo only exact batch with tombstone");
            runOnMainSync(activity::finish);waitForIdleSync();moneyNeed(host.awaitShortcutClose()&&moneyScalar(n,"SELECT undone FROM batches WHERE id=?",key)==1&&moneyScalar(n,"SELECT count(*) FROM ledger")==1,"independent database reopen after finish");moneyPass("undo_cancel_then_exact_batch_only_and_reopen");
        }finally{if(a!=null&&!a.isFinishing()&&!a.isDestroyed()){MainActivity closing=a;runOnMainSync(closing::finish);}MainActivity.isolatedShortcutTest=false;}
    }
    private static void searchNeed(boolean pass,String label){if(!pass)throw new AssertionError("activity search: "+label);}
    private void searchPass(String label){log.append("ACTIVITY_SEARCH_NATIVE ").append(label).append(" PASS\n");}
    private static void searchFind(android.view.View v,String key,List<android.view.View> out){
        if((key.equals(v.getTag())||key.contentEquals(String.valueOf(v.getContentDescription())))&&v.isShown()&&v.isAttachedToWindow()&&v.isEnabled())out.add(v);
        if(v instanceof android.view.ViewGroup){android.view.ViewGroup g=(android.view.ViewGroup)v;for(int i=0;i<g.getChildCount();i++)searchFind(g.getChildAt(i),key,out);}
    }
    private void searchWidget(MainActivity a,String key,String value,boolean click,long budget)throws Exception{
        long until=Math.min(budget,android.os.SystemClock.uptimeMillis()+8000);boolean[] done={false};android.view.View[] located={null};boolean[] scrolled={false};
        while(!done[0]&&android.os.SystemClock.uptimeMillis()<until){runOnMainSync(()->{
            ArrayList<android.view.View> found=new ArrayList<>();searchFind(a.getWindow().getDecorView(),key,found);searchNeed(found.size()<=1,"ambiguous control "+key);if(found.isEmpty())return;android.view.View v=found.get(0);
            if(value!=null&&!(v instanceof android.widget.EditText)&&(!(v instanceof android.widget.TextView)||!value.contentEquals(((android.widget.TextView)v).getText())))return;
            if(!click&&!(v instanceof android.widget.EditText&&value!=null)){done[0]=true;return;}
            if(v.getWidth()<=0||v.getHeight()<=0)return;if(located[0]!=null)searchNeed(located[0]==v,"control replaced "+key);located[0]=v;android.graphics.Rect rect=new android.graphics.Rect();
            if(!v.getLocalVisibleRect(rect)||rect.left!=0||rect.top!=0||rect.right!=v.getWidth()||rect.bottom!=v.getHeight()){
                if(!scrolled[0]){scrolled[0]=true;v.requestRectangleOnScreen(new android.graphics.Rect(0,0,v.getWidth(),v.getHeight()),true);}return;
            }
            if(click){searchNeed(v.isClickable(),"not clickable "+key);v.performClick();}else ((android.widget.EditText)v).setText(value);done[0]=true;
        });if(!done[0])android.os.SystemClock.sleep(30);}searchNeed(done[0],"missing requested widget "+key);waitForIdleSync();
    }
    private static void searchIds(android.view.View v,List<Long> ids){String desc=String.valueOf(v.getTag());if(desc.startsWith("activity-search-hit-")&&v.isAttachedToWindow()&&v.isShown())ids.add(Long.parseLong(desc.substring("activity-search-hit-".length())));if(v instanceof android.view.ViewGroup){android.view.ViewGroup g=(android.view.ViewGroup)v;for(int i=0;i<g.getChildCount();i++)searchIds(g.getChildAt(i),ids);}}
    private void searchResults(MainActivity a,int page,List<Long> expected,long end)throws Exception{
        searchWidget(a,"activity-search-status",expected.isEmpty()?"没有匹配的活动。":"第 "+page+" 页 · 本页 "+expected.size()+" 项",false,end);
        runOnMainSync(()->{List<Long> got=new ArrayList<>();searchIds(a.getWindow().getDecorView(),got);searchNeed(got.equals(expected),"ordered IDs expected "+expected+" got "+got);});
    }
    private void searchQuery(MainActivity a,String query,int page,List<Long> ids,long end)throws Exception{searchWidget(a,"activity-search-query",query,false,end);searchWidget(a,"activity-search-submit",null,true,end);searchResults(a,page,ids,end);}
    /** Reserve one disposable, fixed app-private search fixture name. Do not open or remove old files. */
    static void reserveSearchDatabase(Path file,String name)throws java.io.IOException{
        if(!(MainActivity.ACTIVITY_SEARCH_TEST_DB.equals(name)||"search-roundtrip-ci.db".equals(name))||file==null||
                !file.isAbsolute()||!file.equals(file.normalize())||!name.equals(file.getFileName().toString()))throw new java.io.IOException("Unexpected search fixture path");
        Path dir=file.getParent();Files.createDirectories(dir);
        if(!Files.isDirectory(dir,java.nio.file.LinkOption.NOFOLLOW_LINKS))throw new java.io.IOException("Search fixture directory unavailable");
        // A sidecar without its database is not a fresh fixture either. Names only; no unrelated files are opened.
        try(java.nio.file.DirectoryStream<Path> family=Files.newDirectoryStream(dir,name+"-*")){
            if(family.iterator().hasNext())throw new java.io.IOException("Existing sidecar for "+name+"; preserving fixture");
        }
        Files.createFile(file); // Exclusive CREATE_NEW, including broken symlinks. No truncation or retry.
    }
    private static int checkSearchReservation(Path dir)throws Exception{
        String name=MainActivity.ACTIVITY_SEARCH_TEST_DB;int checks=0;Path sample=dir.resolve(name);
        reserveSearchDatabase(sample,name);if(!Files.isRegularFile(sample)||Files.size(sample)!=0)throw new AssertionError("fresh reservation");checks++;
        byte[] marker={4,9,7};Files.write(sample,marker);boolean refused=false;try{reserveSearchDatabase(sample,name);}catch(java.io.IOException ex){refused=true;}
        if(!refused||!Arrays.equals(marker,Files.readAllBytes(sample)))throw new AssertionError("existing source preserved");checks++;
        for(String suffix:new String[]{"-wal","-shm","-journal","-mj-test"}){Path sub=Files.createTempDirectory(dir,"owned-side-");Path f=sub.resolve(name+suffix);Files.write(f,marker);refused=false;
            try{reserveSearchDatabase(sub.resolve(name),name);}catch(java.io.IOException ex){refused=true;}
            if(!refused||Files.exists(sub.resolve(name))||!Arrays.equals(marker,Files.readAllBytes(f)))throw new AssertionError("orphan sidecar preserved "+suffix);checks++;}
        for(String other:new String[]{"pocket-v12.db","schema4-ui.db","other.db"}){Path f=dir.resolve(other);refused=false;try{reserveSearchDatabase(f,other);}catch(java.io.IOException ex){refused=true;}
            if(!refused||Files.exists(f))throw new AssertionError("foreign database untouched");checks++;}
        String dest="search-roundtrip-ci.db";Path otherPath=dir.resolve("unrelated-fresh.db");refused=false;try{reserveSearchDatabase(otherPath,dest);}catch(java.io.IOException ex){refused=true;}
        if(!refused||Files.exists(otherPath)||!Arrays.equals(marker,Files.readAllBytes(sample)))throw new AssertionError("name/path mismatch");checks++;
        reserveSearchDatabase(dir.resolve(dest),dest);if(!Files.exists(dir.resolve(dest))||!Arrays.equals(marker,Files.readAllBytes(sample)))throw new AssertionError("independent destination");return checks+1;
    }
    private void ciCalendarBoundary(String label){Bundle b=new Bundle();b.putString("pocket_calendar_stage",label);sendStatus(1,b);}
    private void activitySearchPhase()throws Exception{
        Context c=getTargetContext();searchNeed("com.supercubegame.pockettodo.v12.preview".equals(c.getPackageName())&&"ranchu".equals(android.os.Build.HARDWARE)&&android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"disposable test environment only");
        // This phase must not borrow a previous phase's initialization; all fixtures are this invocation's own.
        searchNeed(!MainActivity.isolatedShortcutTest&&!MainActivity.isolatedStartupTest&&!MainActivity.isolatedActivationTest&&!MainActivity.isolatedActivitySearchTest,"no overlapping test window");
        searchNeed(checkSearchReservation(Files.createTempDirectory(c.getCacheDir().toPath(),"search-reserve-controls-"))==11,"search reservation controls");
        String n=MainActivity.ACTIVITY_SEARCH_TEST_DB,dest="search-roundtrip-ci.db";
        reserveSearchDatabase(c.getDatabasePath(n).toPath(),n);reserveSearchDatabase(c.getDatabasePath(dest).toPath(),dest);byte[] before,wire;
        try(AppDatabase s=AppDatabase.openSchema4(c,n)){
            searchNeed(scalar(s.getReadableDatabase(),"SELECT count(*) FROM activities")==0&&scalar(s.getReadableDatabase(),"SELECT count(*) FROM todos")==0,"fresh search source not empty");
            s.addCategory(7,"对照分类");s.addApplication(9,"对照应用","");s.addActivity(71,7,9,"无关活动");s.addActivity(72,7,9,"无关活动");s.setShortcut(7,9,true);
            s.addTodo("keep-ui","非空本机待办");s.recordBatch("unrelated",List.of(row("other-row",72,"2028-03-01",999)));
            searchNeed(scalar(s.getReadableDatabase(),"SELECT count(*) FROM todos WHERE id='keep-ui'")==1&&scalar(s.getReadableDatabase(),"SELECT cents FROM ledger WHERE id='other-row' AND activity_id=72")==999&&s.shortcutApplications(7).contains(9L),"owned nonempty unrelated fixture");
            s.addCategory(801,"家庭");s.addCategory(802,"工作");s.addApplication(803,"共享应用","");s.addActivity(8101,801,803,"早读🌱");s.addActivity(8102,802,803,"早读🌱");s.addActivity(8103,802,803,"早读🌱");s.addActivity(8104,802,0,"预算 50%_A\\café");s.savePath(8101,List.of("只在路径里"));s.createNote("search-private-note",8102,"私密笔记标题");NoteDocument body=new NoteDocument();body.add(NoteDocument.Block.text("search-private-block","不搜索这段私密内容",true));s.saveNote("search-private-note",body.snapshot());
            try(AppDatabase.ActivityArchivePlan p=s.prepareActivityArchive(8103,true)){searchNeed(s.confirmActivityArchive(p),"archived fixture");}
            for(int i=0;i<26;i++)s.addActivity(8200+i,801,803,"页例 "+i);before=appendCells(n,true);wire=s.exportState();
        }
        MainActivity a=null;long end=android.os.SystemClock.uptimeMillis()+65000;List<Long> only=Arrays.asList(8101L,8102L),all=Arrays.asList(8101L,8102L,8103L);MainActivity.isolatedActivitySearchTest=true;
        try{
            a=(MainActivity)startActivitySync(new android.content.Intent(c,MainActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));final MainActivity active=a;TodayScreen host=a.shortcutTestScreen();searchNeed(host!=null,"real host");
            searchWidget(a,"activity-search-open",null,true,end);searchWidget(a,"activity-search-submit",null,true,end);searchWidget(a,"activity-search-status","请输入活动标题。",false,end);searchQuery(a,"早读",1,only,end);searchNeed(Arrays.equals(before,appendCells(n,true)),"search preview readonly");searchPass("empty_query_and_two_distinct_active_identities");
            final android.view.View[] old={null};runOnMainSync(()->{List<android.view.View> found=new ArrayList<>();searchFind(active.getWindow().getDecorView(),"activity-search-hit-8101",found);searchNeed(found.size()==1,"first stable result");old[0]=found.get(0);android.view.accessibility.AccessibilityNodeInfo info=old[0].createAccessibilityNodeInfo();try{String spoken=String.valueOf(info.getContentDescription());searchNeed(spoken.contains("家庭")&&spoken.contains("8101")&&spoken.contains("早读"),"spoken identity");}finally{info.recycle();}});searchWidget(a,"activity-search-query","修改关键词",false,end);runOnMainSync(()->{searchNeed(!old[0].isAttachedToWindow(),"old result detached");old[0].performClick();searchNeed(host.activities.selected==0,"stale click did not open detail");});searchNeed(Arrays.equals(before,appendCells(n,true)),"stale click no writes");searchQuery(a,"早读",1,only,end);searchPass("spoken_identity_and_detached_result_cannot_navigate");
            searchWidget(a,"activity-search-hit-8102",null,true,end);searchWidget(a,"activity-fields-8102",null,false,end);searchNeed(host.activities.selected==8102,"second identity not title");runOnMainSync(active::onBackPressed);searchResults(a,1,only,end);searchWidget(a,"activity-search-archives",null,true,end);searchWidget(a,"activity-search-submit",null,true,end);searchResults(a,1,all,end);
            searchWidget(a,"activity-search-hit-8103",null,true,end);searchWidget(a,"archive-history-8103",null,false,end);appendClick(a,"返回搜索",end);searchResults(a,1,all,end);runOnMainSync(()->{List<android.view.View> in=new ArrayList<>(),flags=new ArrayList<>();searchFind(active.getWindow().getDecorView(),"activity-search-query",in);searchFind(active.getWindow().getDecorView(),"activity-search-archives",flags);searchNeed(in.size()==1&&flags.size()==1&&"早读".contentEquals(((android.widget.EditText)in.get(0)).getText())&&((android.widget.CheckBox)flags.get(0)).isChecked(),"back retained query and archive scope");});searchPass("open_second_and_archived_id_back_preserves_scope");
            searchQuery(a,"%_a\\café",1,Arrays.asList(8104L),end);searchQuery(a,"私密内容",1,Collections.emptyList(),end);searchQuery(a,"只在路径里",1,Collections.emptyList(),end);searchQuery(a,"🌱",1,all,end);searchPass("literal_symbols_unicode_and_no_private_body_results");
            List<Long> front=new ArrayList<>();for(int i=0;i<24;i++)front.add(8200L+i);searchQuery(a,"页例",1,front,end);searchWidget(a,"activity-search-next",null,true,end);searchResults(a,2,Arrays.asList(8224L,8225L),end);searchWidget(a,"activity-search-previous",null,true,end);searchResults(a,1,front,end);searchPass("keyset_pages_exact_no_drops_or_duplicates");
            searchWidget(a,"activity-search-back",null,true,end);searchWidget(a,"activity-search-open",null,false,end);searchNeed(Arrays.equals(before,appendCells(n,true)),"all source tables unchanged");runOnMainSync(active::finish);waitForIdleSync();searchNeed(host.awaitShortcutClose(),"closed database worker");
        }finally{if(a!=null&&!a.isFinishing()&&!a.isDestroyed()){final MainActivity live=a;runOnMainSync(live::finish);}MainActivity.isolatedActivitySearchTest=false;}
        Path dir=Files.createTempDirectory(c.getCacheDir().toPath(),"search-ci-");Path zip=dir.resolve("activity-backup.zip");MediaRepository m=new MediaRepository(dir.resolve("media"),1048576);
        try(AppDatabase reopened=AppDatabase.openSchema4(c,n)){searchNeed(Arrays.equals(wire,reopened.exportState())&&Arrays.equals(before,appendCells(n,true)),"reopened raw rows and wire unchanged");reopened.exportBackup(zip,m);}
        try(AppDatabase restored=AppDatabase.openSchema4(c,dest)){restored.restoreBackup(zip,dir,8388608L,m);List<Long> ids=new ArrayList<>();for(ActivitiesScreen.SearchHit h:ActivitiesScreen.searchRead(restored.getReadableDatabase(),"早读",true,0))ids.add(h.id);searchNeed(ids.equals(all)&&Arrays.equals(wire,restored.exportState()),"fresh backup restoration, exact complete wire and search IDs");}
        searchPass("unchanged_all_cells_reopen_and_independent_backup_restore");
    }
    private static void templateNeed(boolean b,String label){if(!b)throw new AssertionError("activity template: "+label);}
    private void templatePass(String label){log.append("ACTIVITY_TEMPLATE_NATIVE ").append(label).append(" PASS\n");}
    private void templateReserve(Context c,String name)throws Exception{
        templateNeed(name.equals(MainActivity.ACTIVITY_TEMPLATE_TEST_DB)||name.equals("template-roundtrip-ci.db"),"CI-only fixture");Path db=c.getDatabasePath(name).toPath(),dir=db.getParent();Files.createDirectories(dir);
        templateNeed(Files.isDirectory(dir,java.nio.file.LinkOption.NOFOLLOW_LINKS),"private fixture directory");try(java.nio.file.DirectoryStream<Path> f=Files.newDirectoryStream(dir,name+"-*")){templateNeed(!f.iterator().hasNext(),"owned fixture sidecar already present, preserved");}Files.createFile(db);
    }
    // Independent encoder: exact unaffected rows/rowids/cell types, including shortcuts. Revision checked independently.
    private byte[] templateUnrelated(String n,long ignore)throws Exception{
        ByteArrayOutputStream b=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(b);List<String> tables=new ArrayList<>(Arrays.asList(TABLES));tables.add("category_shortcuts");
        try(SQLiteDatabase db=SQLiteDatabase.openDatabase(getTargetContext().getDatabasePath(n).getPath(),null,SQLiteDatabase.OPEN_READONLY)){
            for(String t:tables){boolean shortcut=t.equals("category_shortcuts"),rev=t.equals("revision");String col=t.equals("activities")?"id":t.equals("paths")||t.equals("tags")?"activity_id":null;
                String q=shortcut?"SELECT category_id,application_id FROM category_shortcuts ORDER BY category_id,application_id":"SELECT rowid,* FROM "+t+(col==null?"":" WHERE "+col+"<>?")+" ORDER BY rowid";
                try(android.database.Cursor r=db.rawQuery(q,col==null?null:new String[]{Long.toString(ignore)})){str(out,t);out.writeInt(r.getCount());for(String key:r.getColumnNames())str(out,key);while(r.moveToNext())for(int i=0;i<r.getColumnCount();i++){int type=r.getType(i);out.writeByte(type);if(type==1)out.writeLong(rev&&"value".equals(r.getColumnName(i))?0:r.getLong(i));else if(type==3)str(out,r.getString(i));else if(type==4)bytes(out,r.getBlob(i));else templateNeed(type==0,"unexpected SQL type");}}
            }}
        out.flush();return b.toByteArray();
    }
    private void templateText(String text,long deadline)throws Exception{
        long end=Math.min(deadline,android.os.SystemClock.uptimeMillis()+8000);while(android.os.SystemClock.uptimeMillis()<end){android.view.accessibility.AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();int matches=0;if(root!=null)try{
            if(getTargetContext().getPackageName().contentEquals(String.valueOf(root.getPackageName())))for(android.view.accessibility.AccessibilityNodeInfo x:root.findAccessibilityNodeInfosByText(text))try{
                if(x.isVisibleToUser()&&getTargetContext().getPackageName().contentEquals(String.valueOf(x.getPackageName()))&&text.contentEquals(String.valueOf(x.getText())))matches++;
            }finally{x.recycle();}}finally{root.recycle();}templateNeed(matches<=1,"ambiguous preview");if(matches==1)return;android.os.SystemClock.sleep(30);}throw new AssertionError("missing template preview: "+text);
    }
    private void activityTemplatePhase()throws Exception{
        Context c=getTargetContext();templateNeed("com.supercubegame.pockettodo.v12.preview".equals(c.getPackageName())&&"ranchu".equals(android.os.Build.HARDWARE)&&android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"disposable emulator only");
        templateNeed(!MainActivity.isolatedShortcutTest&&!MainActivity.isolatedStartupTest&&!MainActivity.isolatedActivationTest&&!MainActivity.isolatedActivitySearchTest&&!MainActivity.isolatedActivityTemplateTest,"exclusive test session");
        String n=MainActivity.ACTIVITY_TEMPLATE_TEST_DB,dest="template-roundtrip-ci.db";templateReserve(c,n);templateReserve(c,dest);Path dir=Files.createTempDirectory(c.getCacheDir().toPath(),"template-ci-");MediaRepository media=new MediaRepository(dir.resolve("media"),1048576);
        android.graphics.Bitmap bitmap=android.graphics.Bitmap.createBitmap(2,1,android.graphics.Bitmap.Config.ARGB_8888);ByteArrayOutputStream encoded=new ByteArrayOutputStream();bitmap.eraseColor(0xff31875f);templateNeed(bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG,100,encoded),"fixture PNG");bitmap.recycle();byte[] pixels=encoded.toByteArray();String asset=media.copy(new ByteArrayInputStream(pixels));
        List<String> paths=Arrays.asList("我的","福利","我的"),tags=Arrays.asList("阅读","日常");byte[] before,unchanged;long rev;
        try(AppDatabase db=AppDatabase.openSchema4(c,n)){
            db.addCategory(7,"学习");db.addApplication(9,"阅读应用","");db.addActivity(71,7,0,"同名活动");db.addActivity(72,7,9,"同名活动");db.addActivity(90,7,9,"已归档样本");try(AppDatabase.ActivityArchivePlan p=db.prepareActivityArchive(90,true)){db.confirmActivityArchive(p);}db.setShortcut(7,9,true);
            db.savePath(71,List.of("兄弟活动"));db.savePath(72,paths);db.saveTags(72,tags);db.addTodo("template-keep","保留普通待办");db.recordBatch("template-side-batch",List.of(row("template-expense",72,"2028-02-29",125)));
            db.putMark(new CalendarRules.Mark(72,LocalDate.of(2028,2,29),CalendarRules.Status.DONE,"手动记录",Instant.parse("2028-02-29T03:00:00Z")));
            db.defineField("guide","注意事项","TEXT",Collections.emptyList());db.putField(72,"guide",List.of("原字段值"));db.createFieldNote("template-note",72,"guide","源笔记");db.registerMedia(asset,"image/png",pixels.length);NoteDocument note=new NoteDocument();note.add(NoteDocument.Block.text("secret","私密内容",true));note.addImage("img",asset,"来源图片");db.saveNote("template-note",note.snapshot());
            boolean refused=false;try(AppDatabase.ActivityTemplatePlan ignored=db.prepareActivityTemplate(90)){}catch(IllegalStateException expected){refused=true;}templateNeed(refused,"archived source denied");
            try(AppDatabase.ActivityTemplatePlan p=db.prepareActivityTemplate(71)){templateNeed(p.applicationId==0&&p.paths.equals(List.of("兄弟活动"))&&p.tags.isEmpty(),"same title sibling, no application");}
            try(AppDatabase.ActivityTemplatePlan stale=db.prepareActivityTemplate(72)){db.addTodo("template-later","另一次操作");byte[] cur=appendCells(n,true);refused=false;try{db.confirmActivityTemplate(stale,"不得创建");}catch(IllegalStateException expected){refused=true;}templateNeed(refused&&Arrays.equals(cur,appendCells(n,true)),"stale no partial writes");}
            before=appendCells(n,true);unchanged=templateUnrelated(n,0);rev=moneyScalar(n,"SELECT value FROM revision");
        }templatePass("archived_nullable_sibling_and_stale_preview_readonly");
        MainActivity a=null;long end=android.os.SystemClock.uptimeMillis()+65000;android.accessibilityservice.AccessibilityServiceInfo info=getUiAutomation().getServiceInfo();int flags=info.flags;info.flags|=android.accessibilityservice.AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;getUiAutomation().setServiceInfo(info);MainActivity.isolatedActivityTemplateTest=true;
        try{a=(MainActivity)startActivitySync(new android.content.Intent(c,MainActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));final MainActivity live=a;TodayScreen host=a.shortcutTestScreen();templateNeed(host!=null,"real template host");
            searchWidget(a,"activity-72",null,true,end);searchWidget(a,"activity-template-open-72",null,true,end);templateText("来源：同名活动 · #72",end);
            appendObserve("取消","android:id/button2",false,true,true,end);searchWidget(a,"activity-template-open-72",null,false,end);templateNeed(Arrays.equals(before,appendCells(n,true))&&Arrays.equals(unchanged,templateUnrelated(n,0)),"cancel exact raw cells");templatePass("owned_native_preview_cancel_all_cells_unchanged");
            searchWidget(a,"activity-template-open-72",null,true,end);templateText("来源：同名活动 · #72",end);appendObserve("确认新建","android:id/button1",false,true,true,end);searchWidget(a,"activity-fields-91",null,false,end);templateNeed(host.activities.selected==91,"new ID navigated");
            templateNeed(moneyScalar(n,"SELECT count(*) FROM activities WHERE id=91 AND title='同名活动' AND archived=0 AND category_id=7 AND application_id=9")==1&&moneyScalar(n,"SELECT value FROM revision")==rev+1&&Arrays.equals(unchanged,templateUnrelated(n,91)),"only allowed new rows and exactly one revision");
            try(AppDatabase read=AppDatabase.openSchema4(c,n)){templateNeed(read.path(91).equals(paths)&&read.tags(91).equals(tags)&&read.path(72).equals(paths)&&read.path(71).equals(List.of("兄弟活动")),"ordered rows separate");}
            templateNeed(Arrays.equals(pixels,Files.readAllBytes(media.path(asset))),"private media bytes unchanged");templatePass("new_id_only_ordered_structure_no_fields_notes_money_marks_or_media_copy");runOnMainSync(live::finish);waitForIdleSync();templateNeed(host.awaitShortcutClose(),"closed workbench");
        }finally{if(a!=null&&!a.isDestroyed()&&!a.isFinishing()){final MainActivity f=a;runOnMainSync(f::finish);}MainActivity.isolatedActivityTemplateTest=false;info.flags=flags;getUiAutomation().setServiceInfo(info);}
        byte[] wire;Path archive=dir.resolve("template.zip");try(AppDatabase reopened=AppDatabase.openSchema4(c,n)){templateNeed(reopened.path(91).equals(paths)&&Arrays.equals(unchanged,templateUnrelated(n,91)),"fresh helper reopens copy");reopened.savePath(91,List.of("只改副本"));templateNeed(reopened.path(72).equals(paths)&&reopened.path(91).equals(List.of("只改副本"))&&Arrays.equals(unchanged,templateUnrelated(n,91)),"editing copy preserves source");wire=reopened.exportState();reopened.exportBackup(archive,media);}
        MediaRepository other=new MediaRepository(dir.resolve("restored-media"),1048576);try(AppDatabase restored=AppDatabase.openSchema4(c,dest)){restored.restoreBackup(archive,dir,8388608L,other);templateNeed(Arrays.equals(wire,restored.exportState())&&restored.path(91).equals(List.of("只改副本"))&&restored.path(72).equals(paths)&&restored.tags(91).equals(tags)&&Arrays.equals(pixels,Files.readAllBytes(other.path(asset))),"independent backup restore IDs, cells and media bytes");}templatePass("independent_edit_reopen_and_backup_preserve_source_and_copy");
    }
    @Override public void onStart(){
        Bundle result=new Bundle();try{
            ok(getTargetContext().getPackageName().equals("com.supercubegame.pockettodo.v12.preview"),"tests target isolated v1.2 package");
            ok(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args.getString("expectedApi")),"actual emulator API equals requested test matrix");
            String phase=args.getString("phase");if("seed".equals(phase)){seed();fieldsSeed();backupSeed();guardedSeed();frozenSeed();legacyAppendNative();}else if("reopen".equals(phase)){reopen();fieldsReopen();backupReopen();guardedReopen();frozenReopen();restorePreviewOwnerReopen();}else if("calendar_batch".equals(phase))calendarBatchPhase();else if("activity_search".equals(phase))activitySearchPhase();else if("activity_template".equals(phase))activityTemplatePhase();else if("prepare_ui_backup".equals(phase))prepareUiBackup();else throw new IllegalArgumentException("unknown test phase");
            log.append("DEVICE_DATABASE_RESULT ").append(phase).append(' ').append(checks).append('/').append(checks).append(" PASS\n");result.putString("stream",log.toString());finish(Activity.RESULT_OK,result);
        }catch(Throwable error){StringWriter text=new StringWriter();error.printStackTrace(new PrintWriter(text));result.putString("stream",log+"DEVICE_DATABASE_FAILED\n"+text);finish(Activity.RESULT_CANCELED,result);}
    }
}
