package com.supercubegame.pockettodo;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteException;
import android.os.Bundle;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Independent opt-in restore contract. Synthetic bytes are NOT image/UI acceptance. */
public final class Schema3RestoreTests extends Instrumentation {
    private Bundle args;
    private int checks;
    private final StringBuilder log=new StringBuilder();
    private interface Action {void run()throws Exception;}
    @Override public void onCreate(Bundle value){super.onCreate(value);args=value;start();}
    private void need(boolean value,String label){
        if(!value)throw new AssertionError(label);
        checks++;log.append("SCHEMA3_PASS ").append(label).append('\n');
    }
    private static void check(boolean value,String message){if(!value)throw new AssertionError(message);}
    private static void rejected(Action action,String message)throws Exception{
        try{action.run();}catch(IllegalArgumentException|IllegalStateException|IOException expected){
            check(expected.getMessage()!=null&&expected.getMessage().contains(message),"wrong rejection: "+expected);
            return;
        }throw new AssertionError("accepted instead of "+message);
    }
    private static boolean empty(Path directory)throws IOException{
        try(java.util.stream.Stream<Path> files=Files.list(directory)){return !files.findAny().isPresent();}
    }
    private static Map<String,Long> counts(SQLiteDatabase db){
        Map<String,Long> result=new LinkedHashMap<>();
        String[] tables={"revision","categories","applications","activities","paths","tags","batches","ledger","checkins","media","notes","blocks","fields","field_options","field_values","field_notes","todos","legacy_imports"};
        for(String table:tables)try(Cursor c=db.rawQuery("SELECT count(*) FROM "+table,null)){
            check(c.moveToFirst(),"count missing");result.put(table,c.getLong(0));
        }return result;
    }
    private static long revision(SQLiteDatabase db){
        try(Cursor c=db.rawQuery("SELECT value FROM revision WHERE id=1",null)){
            check(c.moveToFirst(),"revision missing");return c.getLong(0);
        }
    }
    private static Path stagedAsset(Path stage,String id)throws IOException{
        try(java.util.stream.Stream<Path> files=Files.walk(stage)){
            return files.filter(p->p.getFileName().toString().equals(id)).findFirst().orElseThrow(()->new IOException("missing staged fixture"));
        }
    }
    private void seed()throws Exception{
        Context context=getTargetContext();Path root=context.getFilesDir().toPath();
        Path archives=root.resolve("schema3-archives"),stage=context.getCacheDir().toPath().resolve("schema3-restore-stage");
        Files.createDirectories(stage);
        MediaRepository media=new MediaRepository(root.resolve("schema3-restore-media"),1000000);
        context.deleteDatabase("schema3-restore.db");
        try(Schema3Store store=new Schema3Store(context,"schema3-restore.db")){
            SQLiteDatabase db=store.getWritableDatabase();
            db.execSQL("INSERT INTO todos VALUES('keep','恢复前待办',0,0)");
            db.execSQL("UPDATE revision SET value=7 WHERE id=1");
            byte[] before=store.exportState();
            Schema3Store.RestorePlan cancel=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            Map<String,Long> current=counts(db);
            try(BackupArchive.Snapshot input=BackupArchive.read(archives.resolve("good.zip"),context.getCacheDir().toPath().resolve("restore-reference"),1000000);
                SQLiteDatabase candidate=Schema3Store.archiveCandidate(input)){
                check(cancel.currentCounts().equals(current)&&cancel.incomingCounts().equals(counts(candidate)),"preview counts differ");
            }
            boolean immutable=false;try{cancel.incomingCounts().put("todos",99L);}catch(UnsupportedOperationException expected){immutable=true;}
            need(immutable&&Arrays.equals(before,store.exportState())&&empty(root.resolve("schema3-restore-media")),"restore_preview_owned_read_only_counts");
            cancel.close();cancel.close();
            rejected(()->store.confirmRestore(cancel,media),"no longer active");
            need(empty(stage)&&Arrays.equals(before,store.exportState()),"restore_cancel_idempotent_consumed");

            Schema3Store.RestorePlan foreign=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            try(Schema3Store other=new Schema3Store(context,"schema3-restore.db")){
                rejected(()->other.confirmRestore(foreign,media),"different helper");
            }
            foreign.close();
            need(empty(stage)&&Arrays.equals(before,store.exportState()),"restore_foreign_same_file_helper_refused");

            Schema3Store.RestorePlan expired=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            store.close();
            rejected(()->store.confirmRestore(expired,media),"no longer active");
            expired.close();db=store.getWritableDatabase();
            need(empty(stage)&&Arrays.equals(before,store.exportState()),"restore_helper_close_invalidates_session");

            Schema3Store.RestorePlan stale=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            long rev=revision(db);
            try(Schema3Store external=new Schema3Store(context,"schema3-restore.db")){
                external.getWritableDatabase().execSQL("UPDATE todos SET title='另一连接写入' WHERE id='keep'");
            }
            byte[] changed=store.exportState();
            check(!Arrays.equals(before,changed)&&revision(db)==rev,"same revision fixture not established");
            rejected(()->store.confirmRestore(stale,media),"Database changed");
            rejected(()->store.confirmRestore(stale,media),"no longer active");
            lateRaceChecks();
            need(empty(stage)&&empty(root.resolve("schema3-restore-media"))&&Arrays.equals(changed,store.exportState()),"restore_other_connection_same_revision_stale_refused");

            Schema3Store.RestorePlan damaged=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            String id=new String(Files.readAllBytes(root.resolve("schema3-ids.txt")),java.nio.charset.StandardCharsets.US_ASCII).trim().split("\\s+")[0];
            Path file=stagedAsset(stage,id);byte[] content=Files.readAllBytes(file);content[0]^=1;Files.write(file,content);
            rejected(()->store.confirmRestore(damaged,media),"digest differs");
            rejected(()->store.confirmRestore(damaged,media),"no longer active");
            need(empty(stage)&&empty(root.resolve("schema3-restore-media"))&&Arrays.equals(changed,store.exportState()),"restore_staged_tamper_refused_before_publication");

            Schema3Store.RestorePlan invalidMedia=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            rejected(()->store.confirmRestore(invalidMedia,null),"Missing restore media");
            rejected(()->store.confirmRestore(invalidMedia,media),"no longer active");
            need(empty(stage)&&Arrays.equals(changed,store.exportState()),"restore_failed_attempt_consumed_and_cleaned");

            Schema3Store.RestorePlan nested=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            db.beginTransaction();
            try{
                rejected(()->store.confirmRestore(nested,media),"outer transaction");
                rejected(()->store.prepareRestore(archives.resolve("good.zip"),stage,1000000),"outer transaction");
            }finally{db.endTransaction();}
            need(empty(stage)&&Arrays.equals(changed,store.exportState()),"restore_outer_transaction_refused");

            Schema3Store.RestorePlan fault=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            db.execSQL("CREATE TRIGGER restore_late_fault BEFORE INSERT ON blocks BEGIN SELECT RAISE(ABORT,'restore late fault'); END");
            boolean failed=false;
            try{store.confirmRestore(fault,media);}catch(SQLiteException expected){failed=expected.getMessage().contains("restore late fault");}
            finally{db.execSQL("DROP TRIGGER restore_late_fault");}
            rejected(()->store.confirmRestore(fault,media),"no longer active");
            check(failed&&Arrays.equals(changed,store.exportState())&&empty(stage),"late fault did not roll back");
            String[] ids=new String(Files.readAllBytes(root.resolve("schema3-ids.txt")),java.nio.charset.StandardCharsets.US_ASCII).trim().split("\\s+");
            for(String asset:ids)media.verify(asset);
            need(ids.length==3&&revision(db)==rev,"restore_late_sql_rollback_keeps_old_state_and_published_blobs");

            Schema3Store.RestorePlan exact=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            store.confirmRestore(exact,media);
            byte[] expected=Files.readAllBytes(root.resolve("schema3-wire.bin"));
            check(Arrays.equals(expected,store.exportState()),"restored canonical state differs");
            NoteDocument.ImageEdit edit=store.imageEdit("second","photo");
            check(edit.revision().originalAssetId.equals(ids[0])&&edit.revision().assetId.equals(ids[2]),"origin pair lost");
            check(Arrays.equals(Files.readAllBytes(media.path(ids[0])),new byte[]{97,98,99})&&
                Arrays.equals(Files.readAllBytes(media.path(ids[1])),new byte[]{1,2,3,4})&&
                Arrays.equals(Files.readAllBytes(media.path(ids[2])),new byte[]{5,6,7,8}),"restored media bytes differ");
            Files.write(root.resolve("schema3-restore-expected.bin"),expected);
            need(empty(stage)&&!db.inTransaction(),"restore_new_exact_state_origins_and_all_assets");
            rejected(()->store.confirmRestore(exact,media),"no longer active");
            need(Arrays.equals(expected,store.exportState()),"restore_success_duplicate_refused");
        }
        restoreShape("old",root.resolve("frozen-v2.zip"),null,stage);
        restoreShape("full",archives.resolve("full.zip"),Files.readAllBytes(archives.resolve("full-state.bin")),stage);
        facadeChecks();
        domainFacadeChecks();
        restoreShape("empty",archives.resolve("empty.zip"),Files.readAllBytes(archives.resolve("empty-state.bin")),stage);
    }
    /** Real business writers, not raw-SQL population: every historical domain and
     * all 18 tables must survive the same facade's export/restore/reopen path.
     */
    private static byte[] domainLegacy(){
        TodoModel model=new TodoModel();long id=model.add("旧版已完成");model.toggle(id);model.add("旧版待办");
        return BackupCodec.encode(model);
    }
    private void domainFacadeChecks()throws Exception{
        Context context=getTargetContext();Path root=context.getFilesDir().toPath();
        String name="schema3-domain.db";context.deleteDatabase(name);
        MediaRepository media=new MediaRepository(root.resolve("schema3-domain-media"),1000000);
        java.time.LocalDate day=java.time.LocalDate.of(2026,9,24),other=day.minusDays(1);
        java.time.Instant at=java.time.Instant.parse("2026-09-24T12:00:00Z");
        byte[] expected;
        try(AppDatabase app=AppDatabase.openSchema3(context,name)){
            app.addCategory(81,"分类甲");app.addCategory(82,"分类乙");app.moveCategory(82,0);
            check(app.categoryIds().equals(Arrays.asList(82L,81L)),"domain category ordering differs");
            app.addApplication(83,"目录应用","com.example.app");app.addActivity(84,81,83,"活动甲");app.addActivity(85,82,83,"活动乙");
            app.savePath(84,Arrays.asList("打开","进入页面"));app.saveTags(84,Arrays.asList("甲","乙","甲"));
            check(app.path(84).equals(Arrays.asList("打开","进入页面"))&&app.tags(84).equals(Arrays.asList("甲","乙")),"domain ordered strings differ");
            app.putMark(new CalendarRules.Mark(84,day,CalendarRules.Status.DONE,"今日完成",at));
            app.putMark(new CalendarRules.Mark(84,other,CalendarRules.Status.SKIPPED,"跳过",at));
            app.putMark(new CalendarRules.Mark(84,other,CalendarRules.Status.UNRECORDED,"",at));
            check(app.marks(84).size()==1&&app.marks(84).get(0).status==CalendarRules.Status.DONE,"domain marks not isolated");
            app.createNote("domain-note",84,"活动笔记");
            byte[] raw={11,22,33,44};String asset=media.copy(new ByteArrayInputStream(raw));
            app.registerMedia(asset,"image/png",raw.length);
            app.saveNote("domain-note",Arrays.asList(NoteDocument.Block.text("text","正文",false),NoteDocument.Block.image("photo",asset,"原始登记",true)));
            byte[] registered=app.exportState();app.registerMedia(asset,"image/png",raw.length);
            check(Arrays.equals(registered,app.exportState()),"domain duplicate registry wrote state");
            rejected(()->app.registerMedia(asset,"image/jpeg",raw.length),"冲突");
            check(Arrays.equals(registered,app.exportState()),"domain registry conflict changed state");
            String[] types={"TEXT","LONG_TEXT","NUMBER","DATE","SELECT","MULTI_SELECT","LINK","BOOLEAN"};
            String[] values={"短文","长文\n第二行","-12.50","2026-09-24","b","b","https://example.com/path","true"};
            for(int i=0;i<types.length;i++){
                String id="field-"+i;boolean choice=i==4||i==5;
                app.defineField(id,"字段"+i,types[i],choice?Arrays.asList("a","b"):Collections.emptyList());
                List<String> input=i==5?Arrays.asList("b","a","b"):Arrays.asList(values[i]);
                app.putField(84,id,input);
                check(app.fieldValue(84,id).equals(i==5?Arrays.asList("b","a"):Arrays.asList(values[i])),"domain field value "+types[i]);
            }
            app.renameField("field-2","历史金额");app.createFieldNote("domain-field-note",84,"field-2","字段笔记");
            app.saveNote("domain-field-note",Arrays.asList(NoteDocument.Block.text("text","字段说明",true)));
            app.archiveField("field-2",true);
            check(app.fieldDefinition("field-2").archived&&app.fieldDefinition("field-2").name.equals("历史金额")&&
                app.fieldNoteIds(84,"field-2").equals(Arrays.asList("domain-field-note")),"domain archived definition or note differs");
            byte[] archived=app.exportState();
            rejected(()->app.putField(84,"field-2",Arrays.asList("99")),"只读");
            rejected(()->app.createFieldNote("forbidden",84,"field-2","禁止"),"归档");
            check(Arrays.equals(archived,app.exportState()),"domain archived write changed state");
            SQLiteDatabase sql=app.getWritableDatabase();
            sql.execSQL("CREATE TRIGGER domain_field_fault BEFORE INSERT ON field_values BEGIN SELECT RAISE(ABORT,'domain field fault'); END");
            boolean failed=false;
            try{app.putField(84,"field-0",Arrays.asList("不能保存"));}
            catch(IllegalArgumentException error){failed=error.getCause()!=null&&error.getCause().getMessage().contains("domain field fault");}
            finally{sql.execSQL("DROP TRIGGER domain_field_fault");}
            check(failed&&Arrays.equals(archived,app.exportState()),"domain field delete/insert fault did not fully roll back");
            app.addTodo("domain-todo","本期待办");app.editTodo("domain-todo","编辑后",true);
            check(app.importLegacy(domainLegacy())==2,"domain legacy import count");
            byte[] imported=app.exportState();check(app.importLegacy(domainLegacy())==0&&Arrays.equals(imported,app.exportState()),"domain legacy duplicate wrote state");
            List<Ledger.Entry> removed=Arrays.asList(new Ledger.Entry("removed-entry",84,day,Ledger.Kind.EXPENSE,999,"撤销"));
            check(app.recordBatch("removed-batch",removed),"domain first batch not recorded");app.undoBatch("removed-batch");
            byte[] undone=app.exportState();rejected(()->app.recordBatch("removed-batch",removed),"撤销");
            check(Arrays.equals(undone,app.exportState()),"domain undo tombstone changed state");
            rejected(()->app.recordBatch("bad-batch",Arrays.asList(new Ledger.Entry("bad",999,day,Ledger.Kind.EXPENSE,1,""))),"关联对象不存在");
            check(Arrays.equals(undone,app.exportState()),"domain failed batch leaked revision or journal");
            List<Ledger.Entry> rows=Arrays.asList(
                new Ledger.Entry("expense",84,day,Ledger.Kind.EXPENSE,1234,"支出"),
                new Ledger.Entry("refund",84,day,Ledger.Kind.REFUND,234,"退款"),
                new Ledger.Entry("income",84,day,Ledger.Kind.INCOME,500,"收入"),
                new Ledger.Entry("planned",84,day,Ledger.Kind.PLANNED,9000,"计划"),
                new Ledger.Entry("other-day",84,other,Ledger.Kind.EXPENSE,111,"昨天"),
                new Ledger.Entry("other-activity",85,day,Ledger.Kind.EXPENSE,222,"另一活动"));
            check(app.recordBatch("live-batch",rows),"domain live batch not recorded");expected=app.exportState();
            check(!app.recordBatch("live-batch",rows)&&Arrays.equals(expected,app.exportState()),"domain batch retry wrote state");
            check(app.total(84,Collections.singleton(day),"NET_EXPENSE")==1000&&app.total(84,Collections.singleton(day),"NET_CASH")==-500&&
                app.total(84,Collections.singleton(day),"PLANNED")==9000&&app.total(84,Collections.emptySet(),"EXPENSE")==0,"domain selected-date metrics differ");
            check(Arrays.equals(expected,app.exportState()),"domain selected-date read wrote state");
            for(long count:counts(sql).values())check(count>0,"domain fixture did not populate every table");
            Path zip=root.resolve("schema3-domain.zip");app.exportBackup(zip,media);
            Path stage=context.getCacheDir().toPath().resolve("schema3-domain-stage");Files.createDirectories(stage);
            context.deleteDatabase("schema3-domain-restored.db");
            try(AppDatabase target=AppDatabase.openSchema3(context,"schema3-domain-restored.db");
                AppDatabase.RestorePlan plan=target.prepareRestore(zip,stage,1000000)){
                target.confirmRestore(plan,new MediaRepository(root.resolve("schema3-domain-restored-media"),1000000));
                check(Arrays.equals(expected,target.exportState()),"domain full-table facade restore differs");
            }
            check(empty(stage),"domain restore staging not cleaned");
            Files.write(root.resolve("schema3-domain-expected.bin"),expected);
        }
        log.append("SCHEMA3_DOMAIN_FACADE all18=PASS writers=PASS rollback=PASS archive_roundtrip=PASS\n");
    }
    /** The real UI-facing API, on isolated files. Default constructor stays v2. */
    private void facadeChecks()throws Exception{
        Context context=getTargetContext();Path root=context.getFilesDir().toPath();
        String name="schema3-facade.db";context.deleteDatabase(name);
        byte[] old;
        try(AppDatabase legacy=new AppDatabase(context,name)){
            legacy.addCategory(71,"兼容分类");legacy.addActivity(72,71,0,"兼容活动");
            legacy.addTodo("facade-todo","迁移前");legacy.createNote("facade-note",72,"兼容笔记");
            legacy.saveNote("facade-note",Arrays.asList(NoteDocument.Block.text("text","迁移前正文",false)));
            old=legacy.exportState();check(legacy.getReadableDatabase().getVersion()==2,"default constructor changed");
        }
        Path stage=context.getCacheDir().toPath().resolve("schema3-facade-stage");Files.createDirectories(stage);
        MediaRepository media=new MediaRepository(root.resolve("schema3-facade-media"),1000000);
        try(AppDatabase app=AppDatabase.openSchema3(context,name)){
            SQLiteDatabase sql=app.getWritableDatabase();
            check(sql==app.getReadableDatabase()&&sql.getVersion()==3,"facade connection not shared");
            check(Arrays.equals(old,legacyWire(sql)),"facade migration changed old cells");
            app.editTodo("facade-todo","迁移后",true);app.renameCategory(71,"新分类");
            app.savePath(72,Arrays.asList("打开","进入"));app.saveTags(72,Arrays.asList("标签"));
            app.saveNote("facade-note",Arrays.asList(NoteDocument.Block.text("text","迁移后正文",true)));
            check(app.todo("facade-todo").done&&app.categoryName(71).equals("新分类")&&
                app.path(72).equals(Arrays.asList("打开","进入"))&&app.tags(72).equals(Arrays.asList("标签"))&&
                app.noteBlocks("facade-note").get(0).privateContent,"facade ordinary APIs not persisted");
            byte[] before=app.exportState();
            AppDatabase.RestorePlan cancel=app.prepareRestore(root.resolve("schema3-archives/good.zip"),stage,1000000);
            check(cancel.currentCounts().equals(counts(sql)),"facade current preview counts differ");
            cancel.close();rejected(()->app.confirmRestore(cancel,media),"恢复预览");
            check(empty(stage)&&Arrays.equals(before,app.exportState()),"facade cancellation wrote data");
            AppDatabase.RestorePlan plan=app.prepareRestore(root.resolve("schema3-archives/good.zip"),stage,1000000);
            try(AppDatabase foreign=AppDatabase.openSchema3(context,name)){
                rejected(()->foreign.confirmRestore(plan,media),"不属于");
            }
            app.confirmRestore(plan,media);
            check(Arrays.equals(Files.readAllBytes(root.resolve("schema3-wire.bin")),app.exportState()),"facade new restore differs");
            rejected(()->app.confirmRestore(plan,media),"恢复预览");plan.close();
            String[] ids=new String(Files.readAllBytes(root.resolve("schema3-ids.txt")),java.nio.charset.StandardCharsets.US_ASCII).trim().split("\\s+");
            List<NoteDocument.Block> next=new ArrayList<>(app.noteBlocks("second"));boolean found=false;
            for(int i=0;i<next.size();i++)if(next.get(i).id.equals("photo")){
                next.set(i,NoteDocument.Block.image("photo",ids[2],"接入层说明",true));found=true;
            }
            check(found,"facade photo fixture missing");app.saveNote("second",next);
            try(Cursor c=sql.rawQuery("SELECT asset_id,original_asset_id,caption,private FROM blocks WHERE note_id='second' AND id='photo'",null)){
                check(c.moveToFirst()&&ids[2].equals(c.getString(0))&&ids[0].equals(c.getString(1))&&
                    "接入层说明".equals(c.getString(2))&&c.getInt(3)==1,"facade ordinary save lost image provenance");
            }
            byte[] preserved=app.exportState();
            List<NoteDocument.Block> bad=new ArrayList<>(next);
            for(int i=0;i<bad.size();i++)if(bad.get(i).id.equals("photo"))bad.set(i,NoteDocument.Block.image("photo",ids[0],"错误替换",false));
            rejected(()->app.saveNote("second",bad),"derivative writer");
            check(Arrays.equals(preserved,app.exportState()),"facade failed edit changed state");
            sql.beginTransaction();
            try{app.addTodo("rolled-back","外层回滚");}finally{sql.endTransaction();}
            check(Arrays.equals(preserved,app.exportState()),"facade writer escaped outer transaction");
            Path zip=root.resolve("schema3-facade.zip");app.exportBackup(zip,media);
            try(BackupArchive.Snapshot snapshot=BackupArchive.read(zip,stage,1000000);
                SQLiteDatabase candidate=Schema3Store.archiveCandidate(snapshot)){
                check(Arrays.equals(preserved,snapshot.state())&&counts(candidate).equals(counts(sql)),"facade backup differs");
            }
            AppDatabase.RestorePlan expired=app.prepareRestore(zip,stage,1000000);
            app.close();rejected(()->app.confirmRestore(expired,media),"恢复预览");expired.close();
            check(empty(stage)&&Arrays.equals(preserved,app.exportState()),"facade close/reopen changed state");
            Files.write(root.resolve("schema3-facade-expected.bin"),preserved);
            try(AppDatabase target=AppDatabase.openSchema3(context,"schema3-facade-old.db")){
                target.addTodo("remove","应被替换");
                try(AppDatabase.RestorePlan legacy=target.prepareRestore(root.resolve("frozen-v2.zip"),stage,1000000)){
                    target.confirmRestore(legacy,media);
                }
                check(Arrays.equals(Files.readAllBytes(root.resolve("frozen-v2-state.bin")),legacyWire(target.getReadableDatabase())),"facade old restore differs");
            }
        }
        log.append("SCHEMA3_FACADE migration=PASS ordinary_apis=PASS origin_preserved=PASS old_new_restore=PASS default_schema=2\n");
    }
    /** Hold the real publication monitor, not a product test hook. The worker can
     * reach publishNewFile ONLY after early state/asset checks have completed.
     * A separate helper writes while publication is parked; no sleeps choose a race.
     * Run a no-write positive control through exactly the same barrier first.
     */
    private void lateRaceChecks()throws Exception{
        Context context=getTargetContext();Path root=context.getFilesDir().toPath();
        Path archive=root.resolve("schema3-archives/good.zip");
        String[] ids=new String(Files.readAllBytes(root.resolve("schema3-ids.txt")),java.nio.charset.StandardCharsets.US_ASCII).trim().split("\\s+");
        for(boolean mutate:new boolean[]{false,true}){
            String stem=mutate?"schema3-race-stale":"schema3-race-control";
            context.deleteDatabase(stem+".db");
            Path stage=context.getCacheDir().toPath().resolve(stem+"-stage");
            Files.createDirectories(stage);
            MediaRepository media=new MediaRepository(root.resolve(stem+"-media"),1000000);
            try(Schema3Store store=new Schema3Store(context,stem+".db")){
                SQLiteDatabase db=store.getWritableDatabase();
                db.execSQL("INSERT INTO todos VALUES('race','并发前',0,0)");
                db.execSQL("UPDATE revision SET value=11 WHERE id=1");
                byte[] before=store.exportState();
                Schema3Store.RestorePlan plan=store.prepareRestore(archive,stage,1000000);
                java.util.concurrent.atomic.AtomicReference<Throwable> failure=new java.util.concurrent.atomic.AtomicReference<>();
                Thread worker=new Thread(()->{
                    try{store.confirmRestore(plan,media);}catch(Throwable error){failure.set(error);}
                },"restore-publication-race");
                worker.setDaemon(true);
                byte[] externalState=null;
                try{
                    synchronized(MediaRepository.class){
                        worker.start();
                        long deadline=android.os.SystemClock.elapsedRealtime()+15000;
                        boolean parked=false;
                        while(android.os.SystemClock.elapsedRealtime()<deadline&&worker.isAlive()){
                            if(worker.getState()==Thread.State.BLOCKED){
                                for(StackTraceElement frame:worker.getStackTrace()){
                                    if(frame.getClassName().equals(MediaRepository.class.getName())&&frame.getMethodName().equals("publishNewFile"))parked=true;
                                }
                            }
                            if(parked)break;
                            Thread.sleep(5); // Poll a proven state, never assume a timing window.
                        }
                        check(parked,"restore did not reach publication barrier: "+failure.get());
                        // Publication has not occurred, yet early validation is behind us.
                        for(String id:ids)check(!Files.exists(root.resolve(stem+"-media").resolve(id)),"asset published before barrier");
                        try(Schema3Store external=new Schema3Store(context,stem+".db")){
                            check(Arrays.equals(before,external.exportState())&&revision(external.getReadableDatabase())==11,"barrier current state differs");
                            if(mutate)external.getWritableDatabase().execSQL("UPDATE todos SET title='早检查之后的写入' WHERE id='race'");
                            externalState=external.exportState();
                            check(revision(external.getReadableDatabase())==11,"external write changed revision");
                            check(mutate?!Arrays.equals(before,externalState):Arrays.equals(before,externalState),"external mutation control differs");
                        }
                    }
                }finally{
                    // Never join while holding the publication monitor.
                    worker.join(15000);
                    check(!worker.isAlive(),"restore worker did not finish after barrier release");
                }
                Throwable actual=failure.get();
                if(mutate){
                    check(actual instanceof IllegalStateException&&actual.getMessage().contains("Database changed"),"late stale guard not observed: "+actual);
                    check(Arrays.equals(externalState,store.exportState())&&revision(db)==11,"restore overwrote external writer");
                }else{
                    check(actual==null,"positive barrier control failed: "+actual);
                    check(Arrays.equals(Files.readAllBytes(root.resolve("schema3-wire.bin")),store.exportState()),"positive barrier restore differs");
                }
                for(String id:ids)media.verify(id); // All publications preceded final rejection.
                check(ids.length==3&&empty(stage)&&!db.inTransaction(),"late race cleanup or publication incomplete");
                rejected(()->store.confirmRestore(plan,media),"no longer active");
                plan.close();
            }
        }
        log.append("SCHEMA3_RESTORE_LATE_RACE positive=PASS after_early_check=PROVEN same_revision_external_write=REFUSED full_state_preserved=PASS\n");
    }
    private void restoreShape(String name,Path archive,byte[] expected,Path stage)throws Exception{
        Context context=getTargetContext();Path root=context.getFilesDir().toPath();
        String database="schema3-restore-"+name+".db";context.deleteDatabase(database);
        MediaRepository media=new MediaRepository(root.resolve("schema3-restore-"+name+"-media"),1000000);
        try(Schema3Store store=new Schema3Store(context,database)){
            SQLiteDatabase db=store.getWritableDatabase();
            db.execSQL("INSERT INTO todos VALUES('removed','应被完整替换',0,0)");
            try(Schema3Store.RestorePlan plan=store.prepareRestore(archive,stage,1000000)){
                store.confirmRestore(plan,media);
            }
            byte[] actual=store.exportState();
            if(name.equals("old")){
                // Compare every historical cell through the independent old format encoder.
                byte[] old=Files.readAllBytes(root.resolve("frozen-v2-state.bin"));
                check(Arrays.equals(old,legacyWire(db)),"old restored cells differ");
                try(Cursor c=db.rawQuery("SELECT original_asset_id FROM blocks",null)){
                    while(c.moveToNext())check(c.isNull(0),"old import invented provenance");
                }
            }else check(Arrays.equals(expected,actual),"shape canonical state differs");
            Map<String,Long> rows=counts(db);
            if(name.equals("full"))for(long value:rows.values())check(value>0,"full shape lost a table");
            if(name.equals("empty"))for(Map.Entry<String,Long> row:rows.entrySet())check(row.getValue()==(row.getKey().equals("revision")?1L:0L),"empty shape retained rows");
            try(BackupArchive.Snapshot input=BackupArchive.read(archive,context.getCacheDir().toPath().resolve("restore-reference"),1000000)){
                for(Map.Entry<String,Path> asset:input.assets().entrySet()){
                    media.verify(asset.getKey());check(Arrays.equals(Files.readAllBytes(asset.getValue()),Files.readAllBytes(media.path(asset.getKey()))),"shape asset differs");
                }
            }
            Files.write(root.resolve("schema3-restore-"+name+"-expected.bin"),actual);
            need(empty(stage)&&!db.inTransaction(),"restore_"+name+"_complete_replacement");
        }
    }
    private static void text(DataOutputStream out,String s)throws IOException{byte[] b=s.getBytes(java.nio.charset.StandardCharsets.UTF_8);out.writeInt(b.length);out.write(b);}
    private static byte[] legacyWire(SQLiteDatabase db)throws IOException{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(0x50544442);out.writeInt(1);out.writeInt(2);Map<String,Long> tables=counts(db);out.writeInt(tables.size());
        for(String table:tables.keySet()){
            String cols=table.equals("blocks")?"note_id,id,position,kind,text,asset_id,caption,private":"*";
            try(Cursor c=db.rawQuery("SELECT "+cols+" FROM "+table+" ORDER BY rowid",null)){
                text(out,table);out.writeInt(c.getColumnCount());for(String col:c.getColumnNames())text(out,col);out.writeInt(c.getCount());
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){
                    int type=c.getType(i);out.writeByte(type);
                    if(type==1)out.writeLong(c.getLong(i));else if(type==3)text(out,c.getString(i));
                    else if(type==4){byte[] b=c.getBlob(i);out.writeInt(b.length);out.write(b);}
                    else check(type==0,"unexpected type");
                }
            }
        }out.flush();return bytes.toByteArray();
    }
    private void reopen()throws Exception{
        Context context=getTargetContext();Path root=context.getFilesDir().toPath();
        for(String name:new String[]{"schema3-domain","schema3-domain-restored"}){
            try(AppDatabase app=AppDatabase.openSchema3(context,name+".db")){
                check(Arrays.equals(Files.readAllBytes(root.resolve("schema3-domain-expected.bin")),app.exportState()),"domain independent-process exact state differs");
                check(app.importLegacy(domainLegacy())==0&&app.count("todos")==3&&app.todo("domain-todo").done,"domain reopened legacy journal or todo differs");
                check(app.fieldValue(84,"field-2").equals(Arrays.asList("-12.50"))&&app.fieldDefinition("field-2").archived&&
                    app.fieldNoteIds(84,"field-2").equals(Arrays.asList("domain-field-note"))&&app.marks(84).size()==1,"domain reopened fields or marks differ");
                MediaRepository media=new MediaRepository(root.resolve(name+"-media"),1000000);
                try(Cursor c=app.getReadableDatabase().rawQuery("SELECT id FROM media",null)){
                    check(c.moveToFirst(),"domain reopened media missing");media.verify(c.getString(0));
                    check(Arrays.equals(Files.readAllBytes(media.path(c.getString(0))),new byte[]{11,22,33,44})&&!c.moveToNext(),"domain reopened media bytes differ");
                }
                app.undoBatch("live-batch");
                check(app.count("ledger")==0&&app.count("batches")==2,"domain reopened latest batch undo differs");
                byte[] after=app.exportState();rejected(()->app.undoBatch("live-batch"),"只能撤销");
                check(Arrays.equals(after,app.exportState()),"domain repeated undo changed state");
            }
        }
        try(AppDatabase app=AppDatabase.openSchema3(context,"schema3-facade.db")){
            check(app.getReadableDatabase().getVersion()==3&&Arrays.equals(
                Files.readAllBytes(root.resolve("schema3-facade-expected.bin")),app.exportState()),"facade independent reopen differs");
            check(app.noteBlocks("second").stream().anyMatch(b->b.id.equals("photo")&&b.caption.equals("接入层说明")&&b.privateContent),"facade reopened UI projection differs");
        }
        for(String name:new String[]{"new","old","full","empty"}){
            String stem=name.equals("new")?"schema3-restore":"schema3-restore-"+name;
            try(Schema3Store store=new Schema3Store(context,stem+".db")){
                byte[] expected=Files.readAllBytes(root.resolve(stem+"-expected.bin"));
                check(store.getReadableDatabase().getVersion()==3&&Arrays.equals(expected,store.exportState()),"reopened restored state differs");
                MediaRepository media=new MediaRepository(root.resolve(stem+"-media"),1000000);
                try(Cursor c=store.getReadableDatabase().rawQuery("SELECT id,bytes FROM media",null)){
                    while(c.moveToNext()){media.verify(c.getString(0));check(Files.size(media.path(c.getString(0)))==c.getLong(1),"reopen size differs");}
                }
                if(name.equals("new")){
                    String[] ids=new String(Files.readAllBytes(root.resolve("schema3-ids.txt")),java.nio.charset.StandardCharsets.US_ASCII).trim().split("\\s+");
                    check(store.imageEdit("second","photo").revision().originalAssetId.equals(ids[0]),"reopen origin lost");
                }
                need(!store.getReadableDatabase().inTransaction(),"restore_"+name+"_independent_process_exact");
            }
        }
    }
    @Override public void onStart(){
        Bundle result=new Bundle();
        try{
            check(getTargetContext().getPackageName().equals("com.supercubegame.pockettodo.v12.preview"),"wrong package");
            int api=Integer.parseInt(args.getString("expectedApi"));check(api==android.os.Build.VERSION.SDK_INT,"wrong API");
            String phase=args.getString("phase");
            if("restore_seed".equals(phase))seed();else if("restore_reopen".equals(phase))reopen();else throw new AssertionError("wrong phase");
            log.append("SCHEMA3_RESULT ").append(phase).append(' ').append(api).append(' ').append(checks).append(" PASS\n");
            result.putString("stream",log.toString());finish(Activity.RESULT_OK,result);
        }catch(Throwable error){
            StringWriter stack=new StringWriter();error.printStackTrace(new PrintWriter(stack));
            result.putString("stream",log+"SCHEMA3_FAILED\n"+stack);finish(Activity.RESULT_CANCELED,result);
        }
    }
}
