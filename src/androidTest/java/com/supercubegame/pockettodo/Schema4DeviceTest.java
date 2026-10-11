package com.supercubegame.pockettodo;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Bundle;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Isolated, synthetic storage acceptance. Never opens pocket-v12.db or launches UI.
 * The independent oracle retains typed cells, rowids and original media bytes.
 * seed/reopen are separate instrumentation processes, not merely helper reopen.
 */
public final class Schema4DeviceTest extends Instrumentation {
    private static final String DB="schema4-contract.db";
    private static final String[] OLD=("revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports").split(" ");
    private static final String ASSET="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
    private Bundle args;
    private final List<String> checks=new ArrayList<>();
    private final StringBuilder log=new StringBuilder();
    interface Action {void run()throws Exception;}
    @Override public void onCreate(Bundle value){super.onCreate(value);args=value;start();}
    private void need(boolean ok,String label){
        if(!ok)throw new AssertionError(label);
        if(checks.contains(label))throw new AssertionError("duplicate check "+label);
        checks.add(label);log.append("SHORTCUT_PASS ").append(label).append('\n');
    }
    private static void assertThat(boolean ok,String label){if(!ok)throw new AssertionError(label);}
    private static void refused(Action run,String cause)throws Exception{
        try{run.run();}catch(Exception failure){
            for(Throwable e=failure;e!=null;e=e.getCause())
                if(String.valueOf(e.getMessage()).contains(cause))return;
            throw new AssertionError("wrong rejection for "+cause,failure);
        }
        throw new AssertionError("accepted invalid operation: "+cause);
    }
    private static void text(DataOutputStream out,String s)throws IOException{
        byte[] b=s.getBytes(java.nio.charset.StandardCharsets.UTF_8);out.writeInt(b.length);out.write(b);
    }
    /** Full old data readback, independent of every product snapshot/encoder. */
    private static byte[] cells(SQLiteDatabase db,boolean includeRevision)throws IOException{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        for(String table:OLD){
            if(!includeRevision&&table.equals("revision"))continue;
            try(Cursor c=db.rawQuery("SELECT rowid,* FROM "+table+" ORDER BY rowid",null)){
                text(out,table);out.writeInt(c.getCount());out.writeInt(c.getColumnCount());
                for(String column:c.getColumnNames())text(out,column);
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){
                    int type=c.getType(i);out.writeByte(type);
                    if(type==1)out.writeLong(c.getLong(i));
                    else if(type==3)text(out,c.getString(i));
                    else if(type==4){byte[] b=c.getBlob(i);out.writeInt(b.length);out.write(b);}
                    else assertThat(type==0,"unexpected SQL type");
                }
            }
        }out.flush();return bytes.toByteArray();
    }
    private static String schema(SQLiteDatabase db){
        return schema(db,false);
    }
    private static String schema(SQLiteDatabase db,boolean oldOnly){
        StringBuilder value=new StringBuilder();
        try(Cursor c=db.rawQuery("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name<>'android_metadata' ORDER BY type,name",null)){
            while(c.moveToNext()){
                if(oldOnly&&c.getString(1).equals("category_shortcuts"))continue;
                for(int i=0;i<4;i++)value.append(c.getString(i)).append('\n');
            }
        }return value.toString();
    }
    private static long number(SQLiteDatabase db,String sql){
        try(Cursor c=db.rawQuery(sql,null)){assertThat(c.moveToFirst(),"missing scalar");long n=c.getLong(0);assertThat(!c.moveToNext(),"multiple scalars");return n;}
    }
    /** Frozen independent old DDL, not the new Schema4Store factory. */
    private static void frozen(SQLiteDatabase db)throws Exception{
        for(String field:new String[]{"V1_DDL","V2_EXTRA_DDL"}){
            java.lang.reflect.Field f=V12DeviceTest.class.getDeclaredField(field);f.setAccessible(true);
            for(String sql:((String[])f.get(null)).clone())db.execSQL(sql);
        }
        db.execSQL("INSERT INTO revision VALUES(1,42)");
        db.execSQL("INSERT INTO categories VALUES(7,'分类同名',0),(8,'分类同名',1)");
        db.execSQL("INSERT INTO applications VALUES(10,'应用同名',''),(11,'应用同名','')");
        db.execSQL("INSERT INTO activities VALUES(20,7,10,'活动同名',0),(21,8,10,'活动同名',0),(22,7,11,'活动同名',0),(23,7,10,'归档活动',1)");
        db.execSQL("INSERT INTO paths VALUES(20,0,'首页')");
        db.execSQL("INSERT INTO tags VALUES(20,0,'历史')");
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(1);text(out,"entry");out.writeLong(20);text(out,"2026-09-01");text(out,"EXPENSE");out.writeLong(123);text(out,"历史账目");out.flush();
        db.execSQL("INSERT INTO batches VALUES('batch',?,42,0)",new Object[]{bytes.toByteArray()});
        db.execSQL("INSERT INTO ledger VALUES('entry',20,'2026-09-01','EXPENSE',123,'历史账目','batch',0)");
        db.execSQL("INSERT INTO checkins VALUES(20,'2026-09-01','DONE','历史打卡','2026-09-21T12:00:00Z')");
        db.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',3)",new Object[]{ASSET});
        db.execSQL("INSERT INTO notes VALUES('note',20,'历史笔记')");
        db.execSQL("INSERT INTO blocks VALUES('note','image',0,'IMAGE','',?,'私有图片',1),('note','text',1,'TEXT','私有文字',NULL,'',1)",new Object[]{ASSET});
        db.execSQL("INSERT INTO fields VALUES('field','选项','SELECT',0)");
        db.execSQL("INSERT INTO field_options VALUES('field','yes',0)");
        db.execSQL("INSERT INTO field_values VALUES(20,'field',0,'yes')");
        db.execSQL("INSERT INTO field_notes VALUES('note','field')");
        db.execSQL("INSERT INTO todos VALUES('todo','历史待办',0,0)");
        db.execSQL("INSERT INTO legacy_imports VALUES(?,1)",new Object[]{"f".repeat(64)});
        db.setVersion(2);
    }
    private Path root(){return getTargetContext().getFilesDir().toPath();}
    private MediaRepository media()throws IOException{return new MediaRepository(root().resolve("schema4-media"),1000000);}
    private void seed()throws Exception{
        Context context=getTargetContext();
        assertThat(!context.getDatabasePath("pocket-v12.db").exists(),"fixture must never open live database");
        context.deleteDatabase(DB);
        try(SQLiteDatabase db=context.openOrCreateDatabase(DB,0,null)){frozen(db);}
        byte[] v2;
        try(AppDatabase old=new AppDatabase(context,DB)){
            v2=old.exportState();Files.write(root().resolve("schema4-old-v2.bin"),v2);
        }
        byte[] before,wire3;String schema3;
        try(Schema3Store old=new Schema3Store(context,DB)){
            SQLiteDatabase db=old.getWritableDatabase();
            before=cells(db,true);schema3=schema(db);wire3=old.exportState();
            for(String table:OLD)assertThat(number(db,"SELECT count(*) FROM "+table)>0,"all-table fixture empty: "+table);
        }
        need(true,"all_18_tables_nonempty_before_migration");
        MediaRepository media=media();assertThat(ASSET.equals(media.copy(new ByteArrayInputStream(new byte[]{97,98,99}))),"media abc vector");
        Path oldZip=root().resolve("schema4-old.zip");BackupArchive.write(oldZip,wire3,Set.of(ASSET),media);
        try(Schema4Store store=new Schema4Store(context,DB)){
            SQLiteDatabase db=store.getWritableDatabase();
            need(db.getVersion()==4&&Arrays.equals(before,cells(db,true))&&number(db,"SELECT count(*) FROM category_shortcuts")==0,"migration_preserves_all_old_cells");
            need(schema(db,true).equals(schema3),"migration_only_adds_shortcut_table");
            byte[] unrelated=cells(db,false);
            need(store.setShortcut(7,10,true)&&store.setShortcut(8,10,true)&&store.setShortcut(7,11,true)&&number(db,"SELECT value FROM revision")==45,"stable_ids_and_multi_category_links");
            byte[] saved=store.exportState();long revision=number(db,"SELECT value FROM revision");
            need(!store.setShortcut(7,10,true)&&Arrays.equals(saved,store.exportState())&&number(db,"SELECT value FROM revision")==revision,"repeat_setting_is_exact_noop");
            need(store.shortcutApplications(7).equals(List.of(10L,11L))&&store.shortcutApplications(8).equals(List.of(10L)),"same_name_targets_not_confused");
            refused(()->store.setShortcut(999,10,true),"Category missing");
            refused(()->store.setShortcut(7,999,true),"Application missing");
            refused(()->store.setShortcut(-1,10,true),"Invalid identity");
            need(Arrays.equals(saved,store.exportState()),"invalid_targets_leave_exact_state");
            need(store.setShortcut(7,11,false)&&!store.setShortcut(7,11,false)&&store.shortcutApplications(7).equals(List.of(10L))&&number(db,"SELECT value FROM revision")==46,"remove_relation_only_and_repeat_noop");
            byte[] exact=store.exportState();
            need(store.activityTargets(7,10).equals(List.of(20L,21L))&&Arrays.equals(exact,store.exportState()),"navigation_read_is_pure_and_excludes_archived");
            refused(()->store.activityTargets(7,11),"Shortcut missing");
            need(Arrays.equals(exact,store.exportState())&&Arrays.equals(unrelated,cells(db,false)),"missing_navigation_no_business_writes");
            db.execSQL("CREATE TEMP TRIGGER shortcut_fault BEFORE UPDATE ON revision BEGIN SELECT RAISE(ABORT,'shortcut_late_fault'); END");
            refused(()->store.setShortcut(7,11,true),"shortcut_late_fault");
            need(Arrays.equals(exact,store.exportState()),"late_sql_failure_rolls_back_link_and_revision");
            db.execSQL("DROP TRIGGER shortcut_fault");
            db.execSQL("CREATE TABLE unexpected(value TEXT)");
            refused(()->store.exportState(),"Unknown or missing schema");
            db.execSQL("DROP TABLE unexpected");
            need(Arrays.equals(exact,store.exportState()),"unknown_tables_never_silently_omitted");
            Files.write(root().resolve("schema4-expected.bin"),exact);
            Files.write(root().resolve("schema4-old-cells.bin"),cells(db,true));
            Path backup=root().resolve("schema4-full.zip");store.exportBackup(backup,media);
            need(Arrays.equals(exact,store.exportState())&&Arrays.equals(new byte[]{97,98,99},Files.readAllBytes(media.path(ASSET))),"backup_preserves_source_and_original_media");
            restoreChecks(store,backup,oldZip,media);
            need(Arrays.equals(exact,store.exportState())&&Arrays.equals(unrelated,cells(store.getReadableDatabase(),false)),"restore_suite_preserves_all_business_cells");
        }
        for(byte[] legacy:new byte[][]{v2,wire3})try(SQLiteDatabase candidate=Schema4Store.stateCandidate(legacy)){
            need(candidate.getVersion()==4&&number(candidate,"SELECT count(*) FROM category_shortcuts")==0,
                legacy==v2?"v2_backup_normalizes_empty_shortcuts":"v3_backup_normalizes_empty_shortcuts");
        }
        try(Schema4Store store=new Schema4Store(context,DB)){
            byte[] good=store.exportState();
            for(byte[] bad:new byte[][]{Arrays.copyOf(good,good.length-1),Arrays.copyOf(good,good.length+1),new byte[12]})
                refused(()->{try(SQLiteDatabase ignored=Schema4Store.stateCandidate(bad)){};},"Schema4 state validation failed");
            refused(()->{try(SQLiteDatabase ignored=Schema3Store.stateCandidate(good)){};},"Unknown wire/schema version");
            need(Arrays.equals(good,store.exportState()),"malformed_and_new_to_old_backups_refused");
        }
        migrationFailureChecks();
        refused(()->{try(Schema4Store ignored=new Schema4Store(context,"pocket-v12.db")){};},"Live UI database not enabled");
        need(!context.getDatabasePath("pocket-v12.db").exists(),"live_ui_database_never_opened");
        bridgeSeed();
    }
    private void restoreChecks(Schema4Store store,Path backup,Path oldZip,MediaRepository media)throws Exception{
        Path stage=getTargetContext().getCacheDir().toPath().resolve("schema4-stage");
        byte[] baseline=store.exportState();
        Schema4Store.RestorePlan cancel=store.prepareRestore(backup,stage,1000000);
        need(cancel.incomingCounts().size()==19&&cancel.incomingCounts().get("category_shortcuts")==2L&&Arrays.equals(baseline,store.exportState()),"restore_preview_is_read_only_and_counts_complete");
        boolean immutable=false;
        try{cancel.incomingCounts().put("category_shortcuts",999L);}catch(UnsupportedOperationException expected){immutable=true;}
        need(immutable,"restore_counts_immutable");
        cancel.close();refused(()->store.confirmRestore(cancel,media),"Restore plan no longer active");
        need(Arrays.equals(baseline,store.exportState()),"cancel_and_replay_preserve_state");
        Schema4Store.RestorePlan foreign=store.prepareRestore(backup,stage,1000000);
        try(Schema4Store other=new Schema4Store(getTargetContext(),DB)){
            refused(()->other.confirmRestore(foreign,media),"Restore belongs to a different helper");
        }
        store.confirmRestore(foreign,media);
        need(Arrays.equals(baseline,store.exportState()),"foreign_owner_refused_without_consuming_valid_plan");
        Schema4Store.RestorePlan expired=store.prepareRestore(backup,stage,1000000);
        store.close();
        refused(()->store.confirmRestore(expired,media),"Restore plan no longer active");
        need(Arrays.equals(baseline,store.exportState()),"helper_close_invalidates_restore_session");
        Schema4Store.RestorePlan stale=store.prepareRestore(backup,stage,1000000);
        try(Schema4Store writer=new Schema4Store(getTargetContext(),DB)){
            writer.getWritableDatabase().execSQL("UPDATE todos SET title='同修订变化' WHERE id='todo'");
        }
        byte[] changed=store.exportState();
        refused(()->store.confirmRestore(stale,media),"Database changed");
        need(Arrays.equals(changed,store.exportState()),"same_revision_stale_restore_refused");
        Schema4Store.RestorePlan good=store.prepareRestore(backup,stage,1000000);
        store.confirmRestore(good,media);
        refused(()->store.confirmRestore(good,media),"Restore plan no longer active");
        need(Arrays.equals(baseline,store.exportState()),"new_backup_restore_exact_and_single_use");
        Schema4Store.RestorePlan old=store.prepareRestore(oldZip,stage,1000000);
        store.confirmRestore(old,media);
        need(store.shortcutApplications(7).isEmpty(),"old_backup_replacement_clears_new_relationships");
        Schema4Store.RestorePlan restore=store.prepareRestore(backup,stage,1000000);
        SQLiteDatabase db=store.getWritableDatabase();
        db.execSQL("CREATE TEMP TRIGGER restore_fault BEFORE INSERT ON category_shortcuts BEGIN SELECT RAISE(ABORT,'shortcut_restore_fault'); END");
        byte[] prior=store.exportState();
        refused(()->store.confirmRestore(restore,media),"shortcut_restore_fault");
        need(Arrays.equals(prior,store.exportState()),"late_restore_failure_rolls_back_every_table");
        db.execSQL("DROP TRIGGER restore_fault");
        store.confirmRestore(store.prepareRestore(backup,stage,1000000),media);
        Schema4Store.RestorePlan damaged=store.prepareRestore(backup,stage,1000000);
        Path asset;
        try(java.util.stream.Stream<Path> paths=Files.walk(stage)){
            asset=paths.filter(p->p.getFileName().toString().equals(ASSET)).findFirst().orElseThrow(()->new AssertionError("staged media missing"));
        }
        Files.write(asset,new byte[]{97,98,100});
        refused(()->store.confirmRestore(damaged,media),"Registered media digest differs");
        refused(()->store.confirmRestore(damaged,media),"Restore plan no longer active");
        need(Arrays.equals(baseline,store.exportState())&&Arrays.equals(new byte[]{97,98,99},Files.readAllBytes(media.path(ASSET))),"changed_staged_media_refused_without_live_damage");
        Schema4Store.RestorePlan frozen=store.prepareRestore(backup,stage,1000000);
        byte[] originalZip=Files.readAllBytes(backup);
        Files.write(backup,new byte[]{0});
        try{store.confirmRestore(frozen,media);}finally{Files.write(backup,originalZip);}
        need(Arrays.equals(baseline,store.exportState()),"reviewed_source_frozen_against_file_replacement");
        try(java.util.stream.Stream<Path> paths=Files.list(stage)){
            need(!paths.findAny().isPresent()&&Arrays.equals(new byte[]{97,98,99},Files.readAllBytes(media.path(ASSET))),"staging_closed_and_original_media_exact");
        }
    }
    private void migrationFailureChecks()throws Exception{
        Context c=getTargetContext();String name="schema4-conflict.db";c.deleteDatabase(name);
        try(Schema3Store old=new Schema3Store(c,name)){
            old.getWritableDatabase().execSQL("CREATE TABLE category_shortcuts(sentinel TEXT)");
        }
        String before;
        try(SQLiteDatabase db=c.openOrCreateDatabase(name,0,null)){before=schema(db);}
        refused(()->{try(Schema4Store store=new Schema4Store(c,name)){store.getWritableDatabase();}},"Unknown or missing schema");
        try(SQLiteDatabase db=c.openOrCreateDatabase(name,0,null)){
            need(db.getVersion()==3&&before.equals(schema(db)),"migration_conflict_keeps_version_and_schema");
        }
        String future="schema4-future.db";c.deleteDatabase(future);
        try(SQLiteDatabase db=c.openOrCreateDatabase(future,0,null)){db.execSQL("CREATE TABLE sentinel(value TEXT)");db.execSQL("INSERT INTO sentinel VALUES('keep')");db.setVersion(99);}
        refused(()->{try(Schema4Store store=new Schema4Store(c,future)){store.getWritableDatabase();}},"Newer database");
        try(SQLiteDatabase db=c.openOrCreateDatabase(future,0,null);Cursor row=db.rawQuery("SELECT value FROM sentinel",null)){
            need(db.getVersion()==99&&row.moveToFirst()&&row.getString(0).equals("keep"),"future_schema_refused_without_damage");
        }
    }
    private void reopen()throws Exception{
        try(Schema4Store store=new Schema4Store(getTargetContext(),DB)){
            need(Arrays.equals(Files.readAllBytes(root().resolve("schema4-expected.bin")),store.exportState()),"separate_process_exact_state");
            need(Arrays.equals(Files.readAllBytes(root().resolve("schema4-old-cells.bin")),cells(store.getReadableDatabase(),true)),"separate_process_all_business_cells");
            need(store.shortcutApplications(7).equals(List.of(10L))&&store.shortcutApplications(8).equals(List.of(10L))&&store.activityTargets(7,10).equals(List.of(20L,21L)),"separate_process_relationships_and_read_only_targets");
            MediaRepository media=media();
            need(Arrays.equals(new byte[]{97,98,99},Files.readAllBytes(media.path(ASSET))),"separate_process_original_media");
            byte[] exact=store.exportState();
            store.confirmRestore(store.prepareRestore(root().resolve("schema4-full.zip"),getTargetContext().getCacheDir().toPath().resolve("schema4-stage"),1000000),media);
            need(Arrays.equals(exact,store.exportState()),"separate_process_backup_restore_exact");
            need(!getTargetContext().getDatabasePath("pocket-v12.db").exists(),"separate_process_no_live_ui_database");
            bridgeReopen();
        }
    }
    private static final String BUSINESS_DB="schema4-business.db";
    private static byte[] bridgeCells(SQLiteDatabase db)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();bytes.write(cells(db,true));
        DataOutputStream out=new DataOutputStream(bytes);
        try(Cursor c=db.rawQuery("SELECT category_id,application_id FROM category_shortcuts ORDER BY category_id,application_id",null)){
            out.writeInt(c.getCount());
            while(c.moveToNext()){assertThat(c.getType(0)==1&&c.getType(1)==1,"bridge typed keys");out.writeLong(c.getLong(0));out.writeLong(c.getLong(1));}
        }
        out.flush();return bytes.toByteArray();
    }
    private void bridgeSeed()throws Exception{
        Context context=getTargetContext();context.deleteDatabase(BUSINESS_DB);
        MediaRepository media=media();Path stage=context.getCacheDir().toPath().resolve("bridge-stage");
        Path backup=root().resolve("schema4-business.zip");
        try(AppDatabase app=AppDatabase.openSchema4(context,BUSINESS_DB)){
            SQLiteDatabase db=app.getWritableDatabase();
            need(db==app.getReadableDatabase()&&db.getVersion()==4,"bridge_one_connection_and_schema4");
            app.addCategory(7,"一");app.addCategory(8,"二");app.addApplication(10,"应用","");
            app.addActivity(20,7,10,"活动");app.setShortcut(7,10,true);app.setShortcut(8,10,true);
            app.createNote("bn",20,"笔记");app.registerMedia(ASSET,"image/png",3);
            app.saveNote("bn",List.of(NoteDocument.Block.text("text","私密正文",true),NoteDocument.Block.image("image",ASSET,"图片",true)));
            need(app.noteBlocks("bn").size()==2&&number(db,"SELECT count(*) FROM blocks WHERE original_asset_id IS NULL")==2&&app.shortcutApplications(7).equals(List.of(10L)),"bridge_note_write_preserves_links_and_origins");
            app.defineField("bf","字段","TEXT",List.of());
            app.confirmFieldValue(app.prepareFieldEdit(20,"bf"),List.of("值"));
            app.confirmFieldRename(app.prepareFieldEdit(20,"bf"),"字段新名");
            app.confirmFieldNoteCreate(app.prepareFieldEdit(20,"bf"),"bfn","字段笔记");
            app.saveNote("bfn",List.of(NoteDocument.Block.text("body","内容",false)));
            need(app.fieldValue(20,"bf").equals(List.of("值"))&&app.fieldNoteIds(20,"bf").equals(List.of("bfn"))&&number(db,"SELECT count(*) FROM category_shortcuts")==2,"bridge_field_and_field_note_operations");
            app.confirmApplicationRename(app.prepareApplicationRename(10),"新应用");
            app.confirmActivityStrings(app.prepareActivityStrings(20,false),List.of("入口","终点"));
            app.confirmActivityStrings(app.prepareActivityStrings(20,true),List.of("标签"));
            app.confirmActivityArchive(app.prepareActivityArchive(20,true));
            app.confirmActivityArchive(app.prepareActivityArchive(20,false));
            byte[] readOnly=bridgeCells(db);
            need(app.activityTargets(7,10).equals(List.of(20L))&&Arrays.equals(readOnly,bridgeCells(db)),"bridge_catalog_paths_archive_and_pure_navigation");
            app.addTodo("bt","待办");
            AppDatabase.TodoDeletionUndo undo=app.confirmTodoDeletion(app.prepareTodoDeletion("bt"));
            app.undoTodoDeletion(undo);
            need(app.todoIds().equals(List.of("bt"))&&number(db,"SELECT count(*) FROM category_shortcuts")==2,"bridge_todo_delete_undo_preserves_shortcuts");
            AppDatabase.ApplicationRenamePlan stale=app.prepareApplicationRename(10);
            long rev=number(db,"SELECT value FROM revision");
            db.execSQL("DELETE FROM category_shortcuts WHERE category_id=8");
            byte[] external=bridgeCells(db);
            refused(()->app.confirmApplicationRename(stale,"过期"),"本机内容已变化");
            need(Arrays.equals(external,bridgeCells(db))&&number(db,"SELECT value FROM revision")==rev,"bridge_same_revision_relation_change_invalidates_plan");
            app.setShortcut(8,10,true);
            byte[] before=bridgeCells(db);
            db.execSQL("CREATE TEMP TRIGGER bridge_fault BEFORE UPDATE ON revision BEGIN SELECT RAISE(ABORT,'bridge_late_fault'); END");
            refused(()->app.addTodo("late","不得残留"),"bridge_late_fault");
            db.execSQL("DROP TRIGGER bridge_fault");
            need(Arrays.equals(before,bridgeCells(db)),"bridge_late_business_failure_rolls_back_exactly");
            db.execSQL("CREATE TEMP TRIGGER bridge_relation_fault AFTER UPDATE ON applications BEGIN DELETE FROM category_shortcuts WHERE category_id=8; END");
            refused(()->app.confirmApplicationRename(app.prepareApplicationRename(10),"触发器污染"),"回读不一致");
            db.execSQL("DROP TRIGGER bridge_relation_fault");
            need(Arrays.equals(before,bridgeCells(db)),"bridge_unrelated_relation_mutation_rolls_back");
            app.exportBackup(backup,media);byte[] wire=app.exportState();
            AppDatabase.RestorePlan cancel=app.prepareRestore(backup,stage,1000000);
            need(cancel.currentCounts().size()==19&&cancel.incomingCounts().get("category_shortcuts")==2L&&Arrays.equals(before,bridgeCells(db)),"bridge_backup_preview_has_all_tables_and_no_writes");
            cancel.close();refused(()->app.confirmRestore(cancel,media),"恢复预览已取消");
            AppDatabase.RestorePlan foreign=app.prepareRestore(backup,stage,1000000);
            try(AppDatabase other=AppDatabase.openSchema4(context,BUSINESS_DB)){
                refused(()->other.confirmRestore(foreign,media),"恢复预览不属于");
            }
            app.confirmRestore(foreign,media);
            need(Arrays.equals(wire,app.exportState()),"bridge_foreign_restore_does_not_consume_owner_plan");
            AppDatabase.RestorePlan old=app.prepareRestore(backup,stage,1000000);
            db.execSQL("DELETE FROM category_shortcuts WHERE category_id=8");
            byte[] changed=bridgeCells(db);
            refused(()->app.confirmRestore(old,media),"Database changed");
            need(Arrays.equals(changed,bridgeCells(db)),"bridge_restore_detects_same_revision_link_edit");
            app.confirmRestore(app.prepareRestore(backup,stage,1000000),media);
            AppDatabase.RestorePlan late=app.prepareRestore(backup,stage,1000000);
            byte[] exact=bridgeCells(db);
            db.execSQL("CREATE TEMP TRIGGER bridge_restore_fault BEFORE INSERT ON category_shortcuts BEGIN SELECT RAISE(ABORT,'bridge_restore_late'); END");
            refused(()->app.confirmRestore(late,media),"bridge_restore_late");
            db.execSQL("DROP TRIGGER bridge_restore_fault");
            need(Arrays.equals(exact,bridgeCells(db)),"bridge_restore_late_failure_preserves_every_table");
            AppDatabase.FieldEditPlan expired=app.prepareFieldEdit(20,"bf");
            app.close();
            refused(()->app.confirmFieldRename(expired,"失效"),"字段编辑已取消");
            db=app.getWritableDatabase();
            need(Arrays.equals(wire,app.exportState()),"bridge_close_invalidates_business_session");
            db.execSQL("CREATE TABLE bridge_unknown(value TEXT)");
            refused(()->app.addTodo("unknown","不能提交"),"Unknown or missing schema");
            db.execSQL("DROP TABLE bridge_unknown");
            need(Arrays.equals(wire,app.exportState()),"bridge_unknown_table_refused_without_partial_write");
            Files.write(root().resolve("schema4-business-expected.bin"),bridgeCells(db));
            Files.write(root().resolve("schema4-business-wire.bin"),app.exportState());
        }
        refused(()->{try(AppDatabase ignored=AppDatabase.openSchema4(context,"pocket-v12.db")){}},"Live UI database not enabled");
        need(!context.getDatabasePath("pocket-v12.db").exists(),"bridge_live_database_name_refused");
    }
    private void bridgeReopen()throws Exception{
        try(AppDatabase app=AppDatabase.openSchema4(getTargetContext(),BUSINESS_DB)){
            need(Arrays.equals(Files.readAllBytes(root().resolve("schema4-business-expected.bin")),bridgeCells(app.getReadableDatabase()))&&
                 Arrays.equals(Files.readAllBytes(root().resolve("schema4-business-wire.bin")),app.exportState()),"bridge_separate_process_all_cells_and_wire_exact");
            byte[] before=bridgeCells(app.getReadableDatabase());
            need(app.activityTargets(7,10).equals(List.of(20L))&&app.fieldValue(20,"bf").equals(List.of("值"))&&
                 app.todoIds().equals(List.of("bt"))&&app.noteBlocks("bn").size()==2&&Arrays.equals(before,bridgeCells(app.getReadableDatabase())),"bridge_separate_process_business_reads_are_pure");
        }
    }

    @Override public void onStart(){
        Bundle result=new Bundle();
        try{
            assertThat(getTargetContext().getPackageName().equals("com.supercubegame.pockettodo.v12.preview"),"wrong package");
            int api=Integer.parseInt(args.getString("expectedApi"));
            assertThat((api==26||api==34)&&android.os.Build.VERSION.SDK_INT==api,"wrong device API");
            String phase=args.getString("phase");
            if("seed".equals(phase))seed();else if("reopen".equals(phase))reopen();else throw new AssertionError("wrong phase");
            log.append("SHORTCUT_RESULT ").append(phase).append(' ').append(api).append(' ').append(checks.size()).append(" PASS\n");
            result.putString("stream",log.toString());finish(Activity.RESULT_OK,result);
        }catch(Throwable error){
            StringWriter stack=new StringWriter();error.printStackTrace(new PrintWriter(stack));
            result.putString("stream",log+"SHORTCUT_FAILED\n"+stack);finish(Activity.RESULT_CANCELED,result);
        }
    }
}
