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
        activationSeed();
        startupSeed();
        uiSeed();
        startupUiSeed();
        activationUiSeed();
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
        activationReopen();
        startupReopen();
        uiReopen();
        startupUiReopen();
        activationUiReopen();
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

    private static final String UI_DB="schema4-ui.db";
    private MainActivity uiActivity;
    private android.view.View findUi(android.view.View view,String id){
        if(id.contentEquals(view.getContentDescription()==null?"":view.getContentDescription()))return view;
        if(view instanceof android.view.ViewGroup){
            android.view.ViewGroup group=(android.view.ViewGroup)view;
            for(int i=0;i<group.getChildCount();i++){android.view.View v=findUi(group.getChildAt(i),id);if(v!=null)return v;}
        }
        return null;
    }
    private android.view.View awaitUi(String id)throws Exception{
        long end=android.os.SystemClock.uptimeMillis()+10000;
        while(android.os.SystemClock.uptimeMillis()<end){
            android.view.View[] found={null};
            runOnMainSync(()->{
                android.view.View v=findUi(uiActivity.getWindow().getDecorView(),id);
                if(v!=null&&v.isAttachedToWindow()&&v.isEnabled())found[0]=v;
            });
            if(found[0]!=null)return found[0];
            Thread.sleep(25);
        }
        throw new AssertionError("UI observation deadline: "+id);
    }
    /** One physical DOWN/UP pair, never an action retry or guessed screen coordinate. */
    private android.view.View touchUi(String id)throws Exception{
        android.view.View view=awaitUi(id);
        runOnMainSync(()->view.requestRectangleOnScreen(new android.graphics.Rect(0,0,view.getWidth(),view.getHeight()),true));
        waitForIdleSync();
        android.graphics.Rect rect=new android.graphics.Rect();
        runOnMainSync(()->assertThat(view.isEnabled()&&view.isAttachedToWindow()&&view.getGlobalVisibleRect(rect)
            &&rect.width()>0&&rect.height()>0,"UI visible control: "+id));
        long now=android.os.SystemClock.uptimeMillis();
        android.view.MotionEvent down=android.view.MotionEvent.obtain(now,now,android.view.MotionEvent.ACTION_DOWN,rect.exactCenterX(),rect.exactCenterY(),0);
        android.view.MotionEvent up=android.view.MotionEvent.obtain(now,now+50,android.view.MotionEvent.ACTION_UP,rect.exactCenterX(),rect.exactCenterY(),0);
        try{sendPointerSync(down);sendPointerSync(up);}finally{down.recycle();up.recycle();}
        waitForIdleSync();return view;
    }
    private void launchShortcutUi()throws Exception{
        MainActivity.isolatedShortcutTest=true;
        uiActivity=(MainActivity)startActivitySync(new android.content.Intent(getTargetContext(),MainActivity.class)
            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
        awaitUi("shortcut-manage-7");
    }
    private TodayScreen captureScreenOnMain(MainActivity activity){
        TodayScreen[] captured={null};
        runOnMainSync(()->captured[0]=activity.shortcutTestScreen());
        assertThat(captured[0]!=null,"UI screen capture missing");
        return captured[0];
    }
    private void closeShortcutUi()throws Exception{
        if(uiActivity!=null){
            MainActivity old=uiActivity;TodayScreen screen=captureScreenOnMain(old);
            runOnMainSync(old::finish);waitForIdleSync();
            // Wait for the existing serial executor's close, without reopening it.
            assertThat(screen.awaitShortcutClose(),"UI close executor deadline");
            uiActivity=null;
        }
        MainActivity.isolatedShortcutTest=false;
    }
    private byte[] uiCells()throws Exception{
        try(AppDatabase db=AppDatabase.openSchema4(getTargetContext(),UI_DB)){return bridgeCells(db.getReadableDatabase());}
    }
    private void uiSeed()throws Exception{
        Context context=getTargetContext();context.deleteDatabase(UI_DB);
        try(SQLiteDatabase db=context.openOrCreateDatabase(UI_DB,0,null)){frozen(db);}
        try(Schema3Store old=new Schema3Store(context,UI_DB)){old.getWritableDatabase();}
        byte[] oldCells;
        try(AppDatabase app=AppDatabase.openSchema4(context,UI_DB)){oldCells=cells(app.getReadableDatabase(),false);}
        try{
            launchShortcutUi();
            touchUi("shortcut-manage-7");awaitUi("shortcut-change-7-10");
            byte[] baseline=uiCells();
            touchUi("shortcut-change-7-10");awaitUi("shortcut-confirm");touchUi("shortcut-back");awaitUi("shortcut-manage-7");
            need(Arrays.equals(baseline,uiCells()),"ui_preview_cancel_is_read_only");
            touchUi("shortcut-manage-7");touchUi("shortcut-change-7-10");
            android.view.View abandonedConfirm=awaitUi("shortcut-confirm");
            closeShortcutUi();launchShortcutUi();
            runOnMainSync(()->abandonedConfirm.performClick());waitForIdleSync();
            need(Arrays.equals(baseline,uiCells()),"ui_closed_preview_cannot_write_after_relaunch");
            touchUi("shortcut-manage-7");touchUi("shortcut-change-7-10");touchUi("shortcut-confirm");awaitUi("shortcut-manage-7");
            try(AppDatabase app=AppDatabase.openSchema4(context,UI_DB)){
                need(app.shortcutApplications(7).equals(List.of(10L))&&Arrays.equals(oldCells,cells(app.getReadableDatabase(),false)),
                    "ui_add_exact_relation_no_business_copy");
            }
            touchUi("shortcut-manage-8");touchUi("shortcut-change-8-10");touchUi("shortcut-confirm");awaitUi("shortcut-manage-8");
            baseline=uiCells();
            touchUi("shortcut-manage-7");touchUi("shortcut-open-7-10");awaitUi("shortcut-target-20");
            android.view.View[] absent={null};
            runOnMainSync(()->absent[0]=findUi(uiActivity.getWindow().getDecorView(),"shortcut-target-23"));
            need(absent[0]==null&&awaitUi("shortcut-target-21")!=null&&Arrays.equals(baseline,uiCells()),"ui_targets_exclude_archived_and_do_not_write");
            android.view.View oldTarget=touchUi("shortcut-target-21");awaitUi("activity-fields-21");
            need(Arrays.equals(baseline,uiCells()),"ui_same_name_navigation_exact_and_pure");
            runOnMainSync(()->oldTarget.performClick());waitForIdleSync();
            need(Arrays.equals(baseline,uiCells()),"ui_detached_callback_cannot_replay");
            closeShortcutUi();launchShortcutUi();
            touchUi("shortcut-manage-7");touchUi("shortcut-open-7-10");awaitUi("shortcut-target-20");
            try(AppDatabase app=AppDatabase.openSchema4(context,UI_DB)){app.setShortcut(7,10,false);}
            byte[] removed=uiCells();
            touchUi("shortcut-target-20");awaitUi("shortcut-back");
            // Await the explicit asynchronous rejection, not merely the old back button.
            awaitUiText("v12-status","目标已变化");
            need(Arrays.equals(removed,uiCells()),"ui_removed_link_refuses_stale_navigation");
            touchUi("shortcut-back");touchUi("shortcut-manage-7");touchUi("shortcut-change-7-10");touchUi("shortcut-confirm");awaitUi("shortcut-manage-7");
            touchUi("shortcut-manage-7");touchUi("shortcut-change-7-10");touchUi("shortcut-confirm");awaitUi("shortcut-manage-7");
            try(AppDatabase app=AppDatabase.openSchema4(context,UI_DB)){
                need(app.shortcutApplications(7).isEmpty()&&app.shortcutApplications(8).equals(List.of(10L))&&
                    Arrays.equals(oldCells,cells(app.getReadableDatabase(),false)),"ui_remove_retains_other_category_and_history");
            }
            touchUi("shortcut-manage-7");touchUi("shortcut-change-7-10");touchUi("shortcut-confirm");awaitUi("shortcut-manage-7");
            closeShortcutUi();
            try(AppDatabase app=AppDatabase.openSchema4(context,UI_DB)){
                byte[] before=bridgeCells(app.getReadableDatabase());
                need(!app.confirmShortcut(app.prepareShortcut(7,10),true)&&Arrays.equals(before,bridgeCells(app.getReadableDatabase())),
                    "ui_api_repeat_setting_exact_noop");
                AppDatabase.ShortcutPlan stale=app.prepareShortcut(7,10);
                app.getWritableDatabase().execSQL("UPDATE applications SET name='changed' WHERE id=10");
                byte[] changed=bridgeCells(app.getReadableDatabase());
                refused(()->app.confirmShortcut(stale,false),"Shortcut state changed");
                need(Arrays.equals(changed,bridgeCells(app.getReadableDatabase())),"ui_api_same_revision_edit_refused");
                app.getWritableDatabase().execSQL("UPDATE applications SET name='应用同名' WHERE id=10");
                AppDatabase.ShortcutPlan foreign=app.prepareShortcut(7,10);
                try(AppDatabase other=AppDatabase.openSchema4(context,UI_DB)){
                    refused(()->other.confirmShortcut(foreign,false),"Foreign shortcut plan");
                }
                need(!app.confirmShortcut(foreign,true),"ui_api_foreign_attempt_preserves_owner_plan");
                AppDatabase.ShortcutPlan expired=app.prepareShortcut(7,10);app.close();
                refused(()->app.confirmShortcut(expired,false),"Shortcut plan expired");
                need(app.shortcutApplications(7).equals(List.of(10L)),"ui_api_close_invalidates_plan");
                before=bridgeCells(app.getReadableDatabase());
                AppDatabase.ShortcutPlan fault=app.prepareShortcut(7,10);
                app.getWritableDatabase().execSQL("CREATE TEMP TRIGGER ui_fault BEFORE UPDATE ON revision BEGIN SELECT RAISE(ABORT,'ui_late_fault'); END");
                refused(()->app.confirmShortcut(fault,false),"ui_late_fault");
                app.getWritableDatabase().execSQL("DROP TRIGGER ui_fault");
                need(Arrays.equals(before,bridgeCells(app.getReadableDatabase())),"ui_api_late_failure_rolls_back_all_cells");
                AppDatabase.ShortcutPlan unrelated=app.prepareShortcut(7,10);
                app.getWritableDatabase().execSQL("CREATE TEMP TRIGGER ui_unrelated AFTER DELETE ON category_shortcuts BEGIN UPDATE todos SET title='wrong'; END");
                refused(()->app.confirmShortcut(unrelated,false),"Shortcut unrelated state changed");
                app.getWritableDatabase().execSQL("DROP TRIGGER ui_unrelated");
                need(Arrays.equals(before,bridgeCells(app.getReadableDatabase())),"ui_api_unrelated_write_rolls_back");
                Path backup=root().resolve("schema4-ui-full.zip");app.exportBackup(backup,media());
                app.setShortcut(7,10,false);
                AppDatabase.RestorePlan restore=app.prepareRestore(backup,getTargetContext().getCacheDir().toPath().resolve("schema4-ui-stage"),1000000);
                app.confirmRestore(restore,media());
                need(Arrays.equals(before,bridgeCells(app.getReadableDatabase())),"ui_backup_restore_keeps_relations_and_history");
                Files.write(root().resolve("schema4-ui-expected.bin"),before);
            }
            launchShortcutUi();touchUi("shortcut-manage-7");awaitUi("shortcut-open-7-10");
            android.graphics.Bitmap shot=getUiAutomation().takeScreenshot();
            assertThat(shot!=null,"UI screenshot absent");
            try(OutputStream out=Files.newOutputStream(root().resolve("schema4-ui.png"))){
                assertThat(shot.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out),"UI screenshot encode");
            }finally{shot.recycle();}
            need(Arrays.equals(Files.readAllBytes(root().resolve("schema4-ui-expected.bin")),uiCells()),"ui_activity_relaunch_preserves_exact_state");
        }finally{closeShortcutUi();}
        need(!context.getDatabasePath("pocket-v12.db").exists(),"ui_never_opens_phone_database");
    }
    private void awaitUiText(String id,String prefix)throws Exception{
        long end=android.os.SystemClock.uptimeMillis()+10000;
        while(android.os.SystemClock.uptimeMillis()<end){
            boolean[] ok={false};
            runOnMainSync(()->{
                android.view.View v=findUi(uiActivity.getWindow().getDecorView(),id);
                ok[0]=v instanceof android.widget.TextView&&((android.widget.TextView)v).getText().toString().startsWith(prefix);
            });
            if(ok[0])return;
            Thread.sleep(25);
        }
        throw new AssertionError("UI feedback deadline: "+id+" "+prefix);
    }
    private void uiReopen()throws Exception{
        byte[] expected=Files.readAllBytes(root().resolve("schema4-ui-expected.bin"));
        need(Arrays.equals(expected,uiCells()),"ui_separate_process_exact_state");
        try{
            launchShortcutUi();touchUi("shortcut-manage-8");touchUi("shortcut-open-8-10");touchUi("shortcut-target-20");awaitUi("activity-fields-20");
            need(Arrays.equals(expected,uiCells()),"ui_separate_process_navigation_pure");
        }finally{closeShortcutUi();}
        need(!getTargetContext().getDatabasePath("pocket-v12.db").exists(),"ui_separate_process_live_database_absent");
    }

    private static final String ACTIVATION_DB="schema4-activation.db";
    private Path activationBackups(){return root().resolve("schema4-activation-backups");}
    private boolean activationUnchanged(AppDatabase app,byte[] expected)throws Exception{
        return app.getWritableDatabase().getVersion()==3&&Arrays.equals(expected,cells(app.getWritableDatabase(),true));
    }
    private void activationSeed()throws Exception{
        Context context=getTargetContext();context.deleteDatabase(ACTIVATION_DB);
        try(SQLiteDatabase db=context.openOrCreateDatabase(ACTIVATION_DB,0,null)){frozen(db);}
        MediaRepository media=media();
        AppDatabase app=AppDatabase.openSchema3(context,ACTIVATION_DB);
        try{
            SQLiteDatabase sql=app.getWritableDatabase();byte[] before=cells(sql,true);
            for(String table:OLD)assertThat(number(sql,"SELECT count(*) FROM "+table)>0,"activation fixture empty "+table);
            need(sql.getVersion()==3,"activation_original_schema3_nonempty");
            {
        
        resumeRefused(ACTIVATION_DB);
        need(activationUnchanged(app,before),"activation_resume_schema3_never_migrates");
        String missing="schema4-resume-missing.db";
        assertThat(!context.getDatabasePath(missing).exists(),"resume fixture must start missing");
        resumeRefused(missing);
        need(!context.getDatabasePath(missing).exists(),"activation_resume_missing_never_creates");
        String empty="schema4-resume-empty.db";
        Path emptyPath=context.getDatabasePath(empty).toPath();
        Files.write(emptyPath,new byte[0]);resumeRefused(empty);
        need(Files.exists(emptyPath)&&Files.size(emptyPath)==0,"activation_resume_empty_preserved");
        String corrupt="schema4-resume-corrupt.db";
        Path corruptPath=context.getDatabasePath(corrupt).toPath();
        byte[] invalid=new byte[4096];Arrays.fill(invalid,(byte)0x5a);
        Files.write(corruptPath,invalid);resumeRefused(corrupt);
        need(Arrays.equals(invalid,Files.readAllBytes(corruptPath)),"activation_resume_corrupt_never_deleted");
        String future="schema4-resume-future.db";
        try(SQLiteDatabase futureSql=context.openOrCreateDatabase(future,0,null)){
            futureSql.execSQL("CREATE TABLE sentinel(value TEXT)");futureSql.execSQL("INSERT INTO sentinel VALUES('keep')");
            futureSql.setVersion(99);
        }
        byte[] futureBytes=Files.readAllBytes(context.getDatabasePath(future).toPath());
        resumeRefused(future);
        need(Arrays.equals(futureBytes,Files.readAllBytes(context.getDatabasePath(future).toPath())),
             "activation_resume_future_exact_preservation");
        String linked="schema4-resume-symlink.db";
        Files.createSymbolicLink(context.getDatabasePath(linked).toPath(),context.getDatabasePath(ACTIVATION_DB).toPath());
        resumeRefused(linked);
        need(activationUnchanged(app,before),"activation_resume_symlink_refused");
    
            }
            AppDatabase.ShortcutActivationPlan cancelled=app.prepareShortcutActivation(activationBackups(),media);
            Path cancelledBackup=activationBackups().resolve(cancelled.backupName());
            need(Files.size(cancelledBackup)>0&&sql.getVersion()==3&&Arrays.equals(before,cells(sql,true)),
                 "activation_preview_backup_without_migration");
            cancelled.close();
            refused(()->app.confirmShortcutActivation(cancelled,media),"expired");
            need(activationUnchanged(app,before),"activation_cancel_refuses_replay");
            AppDatabase.ShortcutActivationPlan foreign=app.prepareShortcutActivation(activationBackups(),media);
            try(AppDatabase other=AppDatabase.openSchema3(context,"schema4-activation-foreign.db")){
                refused(()->other.confirmShortcutActivation(foreign,media),"Foreign");
            }
            need(!context.getDatabasePath("schema4-activation-foreign.db").exists(),
                 "activation_foreign_attempt_never_opens_database");
            foreign.close();
            AppDatabase.ShortcutActivationPlan stale=app.prepareShortcutActivation(activationBackups(),media);
            sql.execSQL("UPDATE todos SET title='修改但不增加修订' WHERE id='todo'");
            before=cells(sql,true);
            refused(()->app.confirmShortcutActivation(stale,media),"changed");
            need(activationUnchanged(app,before),"activation_same_revision_change_refused");
            refused(()->app.confirmShortcutActivation(stale,media),"expired");
            need(activationUnchanged(app,before),"activation_failed_attempt_consumed");
            AppDatabase.ShortcutActivationPlan damaged=app.prepareShortcutActivation(activationBackups(),media);
            Files.write(activationBackups().resolve(damaged.backupName()),new byte[]{1,2,3});
            refused(()->app.confirmShortcutActivation(damaged,media),"changed");
            need(activationUnchanged(app,before),"activation_changed_backup_refused");
            AppDatabase.ShortcutActivationPlan missing=app.prepareShortcutActivation(activationBackups(),media);
            Files.delete(activationBackups().resolve(missing.backupName()));
            refused(()->app.confirmShortcutActivation(missing,media),"missing");
            need(activationUnchanged(app,before),"activation_missing_backup_refused");
            AppDatabase.ShortcutActivationPlan badMedia=app.prepareShortcutActivation(activationBackups(),media);
            Files.write(media.path(ASSET),new byte[]{120,121,122});
            try{
                refused(()->app.confirmShortcutActivation(badMedia,media),"digest differs");
                need(activationUnchanged(app,before),"activation_changed_media_refused");
            }finally{Files.write(media.path(ASSET),new byte[]{97,98,99});}
            AppDatabase.ShortcutActivationPlan closed=app.prepareShortcutActivation(activationBackups(),media);
            app.close();
            refused(()->app.confirmShortcutActivation(closed,media),"changed");
            need(activationUnchanged(app,before),"activation_helper_close_expires_consent");
            AppDatabase.ShortcutActivationPlan nested=app.prepareShortcutActivation(activationBackups(),media);
            sql=app.getWritableDatabase();sql.beginTransaction();
            try{refused(()->app.confirmShortcutActivation(nested,media),"outer transaction");}
            finally{sql.endTransaction();}
            need(activationUnchanged(app,before),"activation_outer_transaction_refused");
            AppDatabase.ShortcutActivationPlan success=app.prepareShortcutActivation(activationBackups(),media);
            Path backup=activationBackups().resolve(success.backupName());
            byte[] backupBefore=Files.readAllBytes(backup);String oldSchema=schema(app.getWritableDatabase());
            Files.write(root().resolve("schema4-activation-before.bin"),before);
            app.confirmShortcutActivation(success,media);
            try(AppDatabase activated=AppDatabase.openSchema4(context,ACTIVATION_DB)){
                SQLiteDatabase after=activated.getWritableDatabase();
                need(after.getVersion()==4&&Arrays.equals(before,cells(after,true))&&
                     schema(after,true).equals(oldSchema)&&number(after,"SELECT count(*) FROM category_shortcuts")==0,
                     "activation_atomic_schema4_preserves_all_cells");
                need(Arrays.equals(backupBefore,Files.readAllBytes(backup))&&
                     Arrays.equals(new byte[]{97,98,99},Files.readAllBytes(media.path(ASSET))),
                     "activation_retains_verified_backup_and_media");
                need(activated.setShortcut(7,10,true)&&activated.setShortcut(8,10,true)&&activated.activityTargets(7,10).equals(List.of(20L,21L)),
                     "activation_new_facade_supports_shortcuts");
                Files.write(root().resolve("schema4-activation-final.bin"),cells(after,true));
            }
            {
        AppDatabase resumed=AppDatabase.resumeActivated(getTargetContext(),ACTIVATION_DB);
        try{
            SQLiteDatabase connection=resumed.getWritableDatabase();
            need(connection==resumed.getReadableDatabase()&&connection.getVersion()==4,
                 "activation_resume_one_existing_connection");
            need(Arrays.equals(Files.readAllBytes(root().resolve("schema4-activation-final.bin")),cells(connection,true))&&
                 resumed.shortcutApplications(7).equals(List.of(10L)),
                 "activation_resume_exact_state_and_links");
            resumed.close();
            boolean denied=false;
            try{resumed.getReadableDatabase();}catch(IllegalStateException expectedFailure){denied=true;}
            need(denied&&!connection.isOpen(),"activation_resume_closed_cannot_reopen");
        }finally{resumed.close();}
    
            }
            refused(()->app.confirmShortcutActivation(success,media),"expired");
            need(!context.getDatabasePath("pocket-v12.db").exists(),"activation_never_touches_phone_database");
        }finally{app.close();}
    }
    private void activationReopen()throws Exception{
        try(AppDatabase app=AppDatabase.resumeActivated(getTargetContext(),ACTIVATION_DB)){
            need(Arrays.equals(Files.readAllBytes(root().resolve("schema4-activation-final.bin")),
                              cells(app.getWritableDatabase(),true)),
                 "activation_separate_process_exact_state");
            need(app.shortcutApplications(7).equals(List.of(10L))&&app.activityTargets(7,10).equals(List.of(20L,21L)),
                 "activation_separate_process_relations");
        }
        need(!getTargetContext().getDatabasePath("pocket-v12.db").exists(),
             "activation_separate_process_phone_database_absent");
    }

private void resumeRefused(String name)throws Exception{
        try(AppDatabase ignored=AppDatabase.resumeActivated(getTargetContext(),name)){
            throw new AssertionError("resume unexpectedly accepted "+name);
        }catch(IllegalArgumentException|IllegalStateException|android.database.sqlite.SQLiteException expected){}
    }
    private static final String STARTUP_DB="schema4-startup.db";
    private void startupSeed()throws Exception{
        Context context=getTargetContext();
        String fresh="schema4-startup-new.db";
        assertThat(!context.getDatabasePath(fresh).exists(),"fresh fixture absent");
        try(AppDatabase app=AppDatabase.openForStartup(context,fresh)){
            need(app.getWritableDatabase().getVersion()==3&&!app.shortcutsEnabled(),
                 "startup_fresh_stays_schema3");
            app.addTodo("new","保留新待办");
        }
        try(AppDatabase app=AppDatabase.openForStartup(context,fresh)){
            need(app.todoIds().equals(List.of("new"))&&!app.shortcutsEnabled(),
                 "startup_existing_schema3_keeps_data");
        }
        String[] invalid={"schema4-resume-empty.db","schema4-resume-corrupt.db","schema4-resume-future.db"};
        for(String name:invalid){
            Path file=context.getDatabasePath(name).toPath();byte[] prior=Files.readAllBytes(file);
            boolean denied=false;
            try(AppDatabase app=AppDatabase.openForStartup(context,name)){}
            catch(IllegalArgumentException|IllegalStateException|android.database.sqlite.SQLiteException expected){denied=true;}
            assertThat(denied&&Arrays.equals(prior,Files.readAllBytes(file)),"startup bad file altered "+name);
        }
        need(true,"startup_invalid_files_exact_preservation");
        String link="schema4-resume-symlink.db";
        boolean denied=false;
        try(AppDatabase app=AppDatabase.openForStartup(context,link)){}
        catch(IllegalArgumentException|IllegalStateException expected){denied=true;}
        need(denied&&Files.isSymbolicLink(context.getDatabasePath(link).toPath()),
             "startup_symlink_refused_without_reset");
        try(SQLiteDatabase original=context.openOrCreateDatabase(STARTUP_DB,0,null)){frozen(original);}
        byte[] wire2;
        try(AppDatabase old=new AppDatabase(context,STARTUP_DB)){wire2=old.exportState();}
        byte[] normalized;
        try(SQLiteDatabase expected=Schema3Store.normalizeLegacyState(wire2)){normalized=cells(expected,true);}
        try(AppDatabase app=AppDatabase.openForStartup(context,STARTUP_DB)){
            SQLiteDatabase connection=app.getWritableDatabase();
            need(connection.getVersion()==3&&!app.shortcutsEnabled()&&Arrays.equals(normalized,cells(connection,true)),
                 "startup_schema2_uses_frozen_migration");
            byte[] before=cells(connection,true);
            AppDatabase.ShortcutActivationPlan plan=app.prepareShortcutActivation(activationBackups(),media());
            plan.close();
            need(Arrays.equals(before,cells(connection,true))&&connection.getVersion()==3,
                 "startup_cancelled_activation_stays_schema3");
            AppDatabase.ShortcutActivationPlan accepted=app.prepareShortcutActivation(activationBackups(),media());
            app.confirmShortcutActivation(accepted,media());
        }
        try(AppDatabase app=AppDatabase.openForStartup(context,STARTUP_DB)){
            need(app.shortcutsEnabled()&&app.getWritableDatabase().getVersion()==4&&
                 Arrays.equals(normalized,cells(app.getWritableDatabase(),true)),
                 "startup_activated_schema4_resumes_exactly");
            app.setShortcut(7,10,true);app.setShortcut(8,10,true);
            Files.write(root().resolve("schema4-startup-final.bin"),cells(app.getWritableDatabase(),true));
        }
        AppDatabase closed=AppDatabase.openForStartup(context,fresh);
        SQLiteDatabase connection=closed.getWritableDatabase();closed.close();
        denied=false;
        try{closed.getReadableDatabase();}catch(IllegalStateException expected){denied=true;}
        need(denied&&!connection.isOpen(),"startup_closed_facade_cannot_reopen");
        need(!context.getDatabasePath("pocket-v12.db").exists(),"startup_never_touches_phone_database");
    }
    private void startupReopen()throws Exception{
        try(AppDatabase app=AppDatabase.openForStartup(getTargetContext(),STARTUP_DB)){
            need(Arrays.equals(Files.readAllBytes(root().resolve("schema4-startup-final.bin")),
                              cells(app.getWritableDatabase(),true))&&app.shortcutsEnabled(),
                 "startup_separate_process_exact_state");
            need(app.shortcutApplications(7).equals(List.of(10L))&&
                 app.activityTargets(7,10).equals(List.of(20L,21L)),
                 "startup_separate_process_relations");
        }
    }

    // Fixed in-process test routing; uses the actual default background startup.
    private static final String STARTUP_UI_DB="schema4-startup-ui.db";
    private void nativeStartupNeed(boolean value,String label){
        assertThat(value,label);
        log.append("STARTUP_NATIVE_PASS ").append(label).append('\n');
    }
    private void launchStartupUi(boolean error)throws Exception{
        MainActivity.isolatedShortcutTest=false;
        MainActivity.isolatedStartupTest=true;
        uiActivity=(MainActivity)startActivitySync(new android.content.Intent(getTargetContext(),MainActivity.class)
            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
        awaitUi(error?"startup-error":"新待办输入");
        final boolean[] attached={false};
        runOnMainSync(()->attached[0]=uiActivity.shortcutTestScreen()!=null);
        assertThat(attached[0]!=error,"startup screen/error ownership");
    }
    private void closeStartupUi()throws Exception{
        try{
            if(uiActivity!=null){
                MainActivity old=uiActivity;
                TodayScreen[] screen={null};
                runOnMainSync(()->{screen[0]=old.shortcutTestScreen();old.finish();});
                waitForIdleSync();
                java.lang.reflect.Field field=MainActivity.class.getDeclaredField("startupIo");
                field.setAccessible(true);
                java.util.concurrent.ExecutorService executor=(java.util.concurrent.ExecutorService)field.get(old);
                assertThat(executor.awaitTermination(10,java.util.concurrent.TimeUnit.SECONDS),"startup executor close deadline");
                if(screen[0]!=null)assertThat(screen[0].awaitShortcutClose(),"startup screen close deadline");
                uiActivity=null;
            }
        }finally{MainActivity.isolatedStartupTest=false;}
    }
    private byte[] startupUiCells(boolean links)throws Exception{
        // File must already exist. Independent read never creates or upgrades.
        try(SQLiteDatabase db=SQLiteDatabase.openDatabase(
                getTargetContext().getDatabasePath(STARTUP_UI_DB).getPath(),null,
                SQLiteDatabase.OPEN_READWRITE,(bad)->{throw new IllegalStateException("native snapshot corruption");})){
            assertThat(db.getVersion()==(links?4:3),"native startup schema");
            return links?bridgeCells(db):cells(db,true);
        }
    }
    private void startupUiSeed()throws Exception{
        Context context=getTargetContext();
        assertThat(!context.getDatabasePath("pocket-v12.db").exists(),"native live fixture precondition");
        context.deleteDatabase(STARTUP_UI_DB);
        try{
            launchStartupUi(false);closeStartupUi();
            byte[] fresh=startupUiCells(false);
            nativeStartupNeed(fresh.length>0,"native_startup_fresh_schema3");
            context.deleteDatabase(STARTUP_UI_DB);
            try(SQLiteDatabase db=context.openOrCreateDatabase(STARTUP_UI_DB,0,null)){frozen(db);}
            try(Schema3Store old=new Schema3Store(context,STARTUP_UI_DB)){old.getWritableDatabase();}
            byte[] prior=startupUiCells(false);
            launchStartupUi(false);
            awaitUi("todo-todo");
            closeStartupUi();
            nativeStartupNeed(Arrays.equals(prior,startupUiCells(false)),"native_startup_existing_schema3_exact");
            context.deleteDatabase(STARTUP_UI_DB);
            byte[] corrupt=new byte[256];Arrays.fill(corrupt,(byte)71);
            Path path=context.getDatabasePath(STARTUP_UI_DB).toPath();Files.write(path,corrupt);
            launchStartupUi(true);closeStartupUi();
            nativeStartupNeed(Arrays.equals(corrupt,Files.readAllBytes(path)),"native_startup_corrupt_file_retained");
            // Discard only this synthetic corrupt fixture, never a live database.
            context.deleteDatabase(STARTUP_UI_DB);
            try(SQLiteDatabase db=context.openOrCreateDatabase(STARTUP_UI_DB,0,null)){frozen(db);}
            try(Schema3Store old=new Schema3Store(context,STARTUP_UI_DB)){old.getWritableDatabase();}
            try(AppDatabase app=AppDatabase.openSchema4(context,STARTUP_UI_DB)){
                app.setShortcut(7,10,true);app.setShortcut(8,10,true);
            }
            byte[] expected=startupUiCells(true);
            launchStartupUi(false);awaitUi("todo-todo");closeStartupUi();
            nativeStartupNeed(Arrays.equals(expected,startupUiCells(true)),"native_startup_schema4_exact");
            launchStartupUi(false);awaitUi("todo-todo");closeStartupUi();
            nativeStartupNeed(Arrays.equals(expected,startupUiCells(true)),"native_startup_relaunch_exact");
            Files.write(root().resolve("startup-ui-expected.bin"),expected);
            nativeStartupNeed(!context.getDatabasePath("pocket-v12.db").exists(),"native_startup_phone_database_absent");
        }finally{closeStartupUi();}
    }
    private void startupUiReopen()throws Exception{
        byte[] expected=Files.readAllBytes(root().resolve("startup-ui-expected.bin"));
        assertThat(Arrays.equals(expected,startupUiCells(true)),"native prelaunch separate process cells");
        try{launchStartupUi(false);awaitUi("todo-todo");}finally{closeStartupUi();}
        nativeStartupNeed(Arrays.equals(expected,startupUiCells(true)),"native_startup_separate_process_exact");
        nativeStartupNeed(!getTargetContext().getDatabasePath("pocket-v12.db").exists(),"native_startup_separate_process_phone_absent");
    }


    private void activationPostDdlScenario(byte[] before,boolean rollback)throws Exception{
        // Existing isolated fixture only. Observe final archive digest after DDL,
        // before setTransactionSuccessful/endTransaction, not process death.
        launchActivationUi();
        touchUi("activation-entry");awaitActivation("activation-confirm");
        Path backup=activationUiBackup();byte[] archived=Files.readAllBytes(backup);
        touchActivation("activation-consent");
        MainActivity old=uiActivity;TodayScreen screen=captureScreenOnMain(old);
        AppDatabase database=(AppDatabase)activationQueueField(screen,"db");
        java.util.concurrent.ExecutorService executor=(java.util.concurrent.ExecutorService)activationQueueField(screen,"io");
        // Capture this facade's existing connection on its owner before migration.
        // Reopening through the schema3 facade after DDL correctly fails closed.
        SQLiteDatabase observed=executor.submit(()->database.getReadableDatabase()).get(2,java.util.concurrent.TimeUnit.SECONDS);
        Thread worker=executor.submit(()->Thread.currentThread()).get(2,java.util.concurrent.TimeUnit.SECONDS);
        java.security.Provider original=java.security.MessageDigest.getInstance("SHA-256").getProvider();
        java.util.concurrent.CountDownLatch entered=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.CountDownLatch release=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.atomic.AtomicInteger hits=new java.util.concurrent.atomic.AtomicInteger();
        java.util.concurrent.atomic.AtomicReference<Throwable> failure=new java.util.concurrent.atomic.AtomicReference<>();
        java.util.concurrent.atomic.AtomicBoolean injected=new java.util.concurrent.atomic.AtomicBoolean();
        String providerName="PocketPostDdlObservation";
        assertThat(java.security.Security.getProvider(providerName)==null,"postddl provider initially absent");
        java.security.Provider provider=new java.security.Provider(providerName,1.0,"Test-only delegated digest observation"){
            {
                putService(new java.security.Provider.Service(this,"MessageDigest","SHA-256","delegated",null,null){
                    @Override public Object newInstance(Object ignored)throws java.security.NoSuchAlgorithmException{
                        java.security.MessageDigest delegate=java.security.MessageDigest.getInstance("SHA-256",original);
                        return new java.security.MessageDigestSpi(){
                            @Override protected void engineUpdate(byte value){delegate.update(value);}
                            @Override protected void engineUpdate(byte[] value,int offset,int length){delegate.update(value,offset,length);}
                            @Override protected void engineReset(){delegate.reset();}
                            @Override protected int engineGetDigestLength(){return delegate.getDigestLength();}
                            @Override protected byte[] engineDigest(){
                                boolean confirm=false,digest=false;
                                if(Thread.currentThread()==worker)for(StackTraceElement frame:worker.getStackTrace()){
                                    confirm|=frame.getClassName().equals(Schema4Store.class.getName())&&frame.getMethodName().equals("confirmActivation");
                                    digest|=frame.getClassName().equals(Schema4Store.class.getName())&&frame.getMethodName().equals("activationDigest");
                                }
                                if(confirm&&digest&&hits.incrementAndGet()==2){
                                    try{
                                        assertThat(observed.inTransaction()&&
                                            observed.getVersion()==4,"postddl actual schema4 transaction");
                                        entered.countDown();
                                        assertThat(release.await(10,java.util.concurrent.TimeUnit.SECONDS),"postddl release deadline");
                                    }catch(Throwable error){failure.set(error);entered.countDown();throw new AssertionError(error);}
                                    if(rollback){
                                        injected.set(true);
                                        throw new IllegalStateException("intentional post-DDL digest failure");
                                    }
                                }
                                return delegate.digest();
                            }
                        };
                    }
                });
            }
        };
        java.util.concurrent.Future<?> tail=null;
        try{
            assertThat(java.security.Security.insertProviderAt(provider,1)==1&&
                java.security.Security.getProvider(providerName)==provider,"postddl provider installed");
            assertThat(java.security.MessageDigest.getInstance("SHA-256").getProvider()==provider,
                "postddl provider selected");
            assertThat(Arrays.equals(java.security.MessageDigest.getInstance("SHA-256").digest(new byte[]{97,98,99}),
                java.security.MessageDigest.getInstance("SHA-256",original).digest(new byte[]{97,98,99})),
                "postddl digest delegates exact bytes");
            touchActivation("activation-confirm");tail=executor.submit(()->null);
            assertThat(entered.await(5,java.util.concurrent.TimeUnit.SECONDS)&&failure.get()==null,
                "postddl transaction entered: "+failure.get());
            assertThat(hits.get()==2&&!tail.isDone(),"postddl worker remains paused");
            boolean[] owned={false};runOnMainSync(()->{
                try{owned[0]=(Boolean)activationQueueField(screen,"busy")&&
                    activationQueueField(screen,"activationAttempt")!=null;}
                catch(Exception error){throw new AssertionError(error);}
            });
            assertThat(owned[0],"postddl owns active attempt");
            runOnMainSync(old::finish);
            boolean[] destroyed={false};long end=android.os.SystemClock.uptimeMillis()+5000;
            while(!destroyed[0]&&android.os.SystemClock.uptimeMillis()<end){
                runOnMainSync(()->{
                    try{destroyed[0]=old.isDestroyed()&&(Boolean)activationQueueField(screen,"closed");}
                    catch(Exception error){throw new AssertionError(error);}
                });
                if(!destroyed[0])Thread.sleep(10);
            }
            assertThat(destroyed[0]&&executor.isShutdown()&&!tail.isDone(),
                "postddl destruction precedes digest release");
        }finally{
            release.countDown();
            try{
                if(tail!=null)tail.get(10,java.util.concurrent.TimeUnit.SECONDS);
            }finally{
                if(java.security.Security.getProvider(providerName)==provider)java.security.Security.removeProvider(providerName);
            }
        }
        assertThat(failure.get()==null&&hits.get()==2,"postddl observation completed once");
        assertThat(java.security.Security.getProvider(providerName)==null&&
            java.security.MessageDigest.getInstance("SHA-256").getProvider()==original,"postddl provider restored");
        awaitActivationRetired(old,screen);waitForIdleSync();
        boolean[] clean={false};runOnMainSync(()->{
            try{clean[0]=activationQueueField(screen,"activationDialog")==null&&
                activationQueueField(screen,"activationPlan")==null&&activationQueueField(screen,"activationAttempt")==null;}
            catch(Exception error){throw new AssertionError(error);}
        });
        assertThat(clean[0],"postddl no late owned UI");
        assertThat(Arrays.equals(before,activationUiCells(rollback?3:4))&&Arrays.equals(archived,Files.readAllBytes(backup)),
            "postddl exact outcome preserves history and backup");
        uiActivity=null;closeActivationUi();launchActivationUi();
        assertThat(Arrays.equals(before,activationUiCells(rollback?3:4))&&Arrays.equals(archived,Files.readAllBytes(backup)),
            "postddl relaunch preserves history and backup");
        assertThat(injected.get()==rollback,"postddl injected outcome witnessed");
        closeActivationUi();uiActivity=null;
        log.append("ACTIVATION_POSTDDL_PASS ").append(rollback?"postddl_failure_finish_rolls_back_exact":"postddl_success_finish_commits_exact").append('\n');
    }

    private void activationPostDdlLifecycle(byte[] before)throws Exception{
        activationPostDdlScenario(before,false);
        resetPostDdlFixture(before);
        activationPostDdlScenario(before,true);
        resetPostDdlFixture(before);
    }
    private void resetPostDdlFixture(byte[] before)throws Exception{
        // Recreate ONLY the disposable fixture, after its old facade is closed.
        Context context=getTargetContext();
        assertThat(uiActivity==null&&ACTIVATION_UI_DB.equals("schema4-activation-ui.db")&&
            !context.getDatabasePath("pocket-v12.db").exists(),"postddl fixture-only reset guard");
        context.deleteDatabase(ACTIVATION_UI_DB);
        try(SQLiteDatabase db=context.openOrCreateDatabase(ACTIVATION_UI_DB,0,null)){frozen(db);}
        try(Schema3Store old=new Schema3Store(context,ACTIVATION_UI_DB)){old.getWritableDatabase();}
        assertThat(Arrays.equals(before,activationUiCells(3)),"postddl recreated original fixture exact");
    }

    private void activationConfirmRunningLifecycle(byte[] before)throws Exception{
        // Test-only digest provider delegates every byte to the original provider.
        // Pause only this worker in the real transaction's pre-consent archive digest.
        // This is NOT a claim about interruption after DDL or process death.
        touchUi("activation-entry");awaitActivation("activation-confirm");
        Path backup=activationUiBackup();byte[] archived=Files.readAllBytes(backup);
        touchActivation("activation-consent");
        MainActivity old=uiActivity;TodayScreen screen=captureScreenOnMain(old);
        AppDatabase database=(AppDatabase)activationQueueField(screen,"db");
        java.util.concurrent.ExecutorService executor=(java.util.concurrent.ExecutorService)activationQueueField(screen,"io");
        Thread worker=executor.submit(()->Thread.currentThread()).get(2,java.util.concurrent.TimeUnit.SECONDS);
        java.security.Provider original=java.security.MessageDigest.getInstance("SHA-256").getProvider();
        java.util.concurrent.CountDownLatch entered=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.CountDownLatch release=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.atomic.AtomicInteger hits=new java.util.concurrent.atomic.AtomicInteger();
        java.util.concurrent.atomic.AtomicReference<Throwable> failure=new java.util.concurrent.atomic.AtomicReference<>();
        String providerName="PocketConfirmObservation";
        assertThat(java.security.Security.getProvider(providerName)==null,"confirm running provider initially absent");
        java.security.Provider provider=new java.security.Provider(providerName,1.0,"Test-only delegated digest observation"){
            {
                putService(new java.security.Provider.Service(this,"MessageDigest","SHA-256","delegated",null,null){
                    @Override public Object newInstance(Object ignored)throws java.security.NoSuchAlgorithmException{
                        java.security.MessageDigest delegate=java.security.MessageDigest.getInstance("SHA-256",original);
                        return new java.security.MessageDigestSpi(){
                            @Override protected void engineUpdate(byte value){delegate.update(value);}
                            @Override protected void engineUpdate(byte[] value,int offset,int length){delegate.update(value,offset,length);}
                            @Override protected void engineReset(){delegate.reset();}
                            @Override protected int engineGetDigestLength(){return delegate.getDigestLength();}
                            @Override protected byte[] engineDigest(){
                                boolean confirm=false,digest=false;
                                if(Thread.currentThread()==worker)for(StackTraceElement frame:worker.getStackTrace()){
                                    confirm|=frame.getClassName().equals(Schema4Store.class.getName())&&frame.getMethodName().equals("confirmActivation");
                                    digest|=frame.getClassName().equals(Schema4Store.class.getName())&&frame.getMethodName().equals("activationDigest");
                                }
                                if(confirm&&digest&&hits.incrementAndGet()==1){
                                    try{
                                        assertThat(database.getReadableDatabase().inTransaction()&&
                                            database.getReadableDatabase().getVersion()==3,"confirm running actual schema3 transaction");
                                        entered.countDown();
                                        assertThat(release.await(10,java.util.concurrent.TimeUnit.SECONDS),"confirm running release deadline");
                                    }catch(Throwable error){failure.set(error);entered.countDown();throw new AssertionError(error);}
                                }
                                return delegate.digest();
                            }
                        };
                    }
                });
            }
        };
        java.util.concurrent.Future<?> tail=null;
        try{
            assertThat(java.security.Security.insertProviderAt(provider,1)==1&&
                java.security.Security.getProvider(providerName)==provider,"confirm running provider installed");
            assertThat(java.security.MessageDigest.getInstance("SHA-256").getProvider()==provider,
                "confirm running provider selected");
            assertThat(Arrays.equals(java.security.MessageDigest.getInstance("SHA-256").digest(new byte[]{97,98,99}),
                java.security.MessageDigest.getInstance("SHA-256",original).digest(new byte[]{97,98,99})),
                "confirm running digest delegates exact bytes");
            touchActivation("activation-confirm");tail=executor.submit(()->null);
            assertThat(entered.await(5,java.util.concurrent.TimeUnit.SECONDS)&&failure.get()==null,
                "confirm running transaction entered: "+failure.get());
            assertThat(hits.get()==1&&!tail.isDone(),"confirm running worker remains paused");
            boolean[] owned={false};runOnMainSync(()->{
                try{owned[0]=(Boolean)activationQueueField(screen,"busy")&&
                    activationQueueField(screen,"activationAttempt")!=null;}
                catch(Exception error){throw new AssertionError(error);}
            });
            assertThat(owned[0],"confirm running owns active attempt");
            runOnMainSync(old::finish);
            boolean[] destroyed={false};long end=android.os.SystemClock.uptimeMillis()+5000;
            while(!destroyed[0]&&android.os.SystemClock.uptimeMillis()<end){
                runOnMainSync(()->{
                    try{destroyed[0]=old.isDestroyed()&&(Boolean)activationQueueField(screen,"closed");}
                    catch(Exception error){throw new AssertionError(error);}
                });
                if(!destroyed[0])Thread.sleep(10);
            }
            assertThat(destroyed[0]&&executor.isShutdown()&&!tail.isDone(),
                "confirm running destruction precedes digest release");
        }finally{
            release.countDown();
            try{
                if(tail!=null)tail.get(10,java.util.concurrent.TimeUnit.SECONDS);
            }finally{
                if(java.security.Security.getProvider(providerName)==provider)java.security.Security.removeProvider(providerName);
            }
        }
        assertThat(failure.get()==null&&hits.get()==1,"confirm running observation completed once");
        assertThat(java.security.Security.getProvider(providerName)==null&&
            java.security.MessageDigest.getInstance("SHA-256").getProvider()==original,"confirm running provider restored");
        awaitActivationRetired(old,screen);waitForIdleSync();
        boolean[] clean={false};runOnMainSync(()->{
            try{clean[0]=activationQueueField(screen,"activationDialog")==null&&
                activationQueueField(screen,"activationPlan")==null&&activationQueueField(screen,"activationAttempt")==null;}
            catch(Exception error){throw new AssertionError(error);}
        });
        assertThat(clean[0],"confirm running no late owned UI");
        assertThat(Arrays.equals(before,activationUiCells(3))&&Arrays.equals(archived,Files.readAllBytes(backup)),
            "confirm running rollback preserves history and backup");
        uiActivity=null;closeActivationUi();launchActivationUi();
        assertThat(Arrays.equals(before,activationUiCells(3))&&Arrays.equals(archived,Files.readAllBytes(backup)),
            "confirm running relaunch preserves history and backup");
        log.append("ACTIVATION_CONFIRM_RUNNING_PASS confirm_transaction_before_consent_finish_preserves_exact\n");
    }

    private void activationInflightLifecycle(byte[] before)throws Exception{
        // Hold the existing static publication monitor, not the executor queue.
        // The captured worker must be inside actual prepare/ZIP publication.
        MainActivity old=uiActivity;TodayScreen screen=captureScreenOnMain(old);
        java.util.concurrent.ExecutorService executor=(java.util.concurrent.ExecutorService)activationQueueField(screen,"io");
        Thread worker=executor.submit(()->Thread.currentThread()).get(2,java.util.concurrent.TimeUnit.SECONDS);
        Path directory=root().resolve("activation-backups");
        java.util.Set<Path> prior=new java.util.HashSet<>();
        if(Files.exists(directory))try(java.util.stream.Stream<Path> files=Files.list(directory)){files.forEach(prior::add);}
        java.util.concurrent.Future<?> tail;
        synchronized(MediaRepository.class){
            runOnMainSync(()->{
                try{
                    java.lang.reflect.Method request=TodayScreen.class.getDeclaredMethod("requestShortcutActivation");
                    request.setAccessible(true);request.invoke(screen);
                }catch(Exception error){throw new AssertionError("inflight request",error);}
            });
            tail=executor.submit(()->null);
            boolean entered=false;long end=android.os.SystemClock.uptimeMillis()+5000;
            while(!entered&&android.os.SystemClock.uptimeMillis()<end){
                boolean prepare=false,archive=false,publish=false;
                for(StackTraceElement frame:worker.getStackTrace()){
                    prepare|=frame.getClassName().equals(Schema4Store.class.getName())&&frame.getMethodName().equals("prepareActivation");
                    archive|=frame.getClassName().equals(BackupArchive.class.getName())&&frame.getMethodName().equals("write");
                    publish|=frame.getClassName().equals(MediaRepository.class.getName())&&frame.getMethodName().equals("publishNewFile");
                }
                entered=worker.getState()==Thread.State.BLOCKED&&prepare&&archive&&publish&&!tail.isDone();
                if(!entered)Thread.sleep(10);
            }
            assertThat(entered,"inflight real prepare publication stack: "+worker.getState()+" "+Arrays.toString(worker.getStackTrace()));
            boolean[] pending={false};
            runOnMainSync(()->{
                try{pending[0]=(Boolean)activationQueueField(screen,"busy")&&
                    activationQueueField(screen,"activationPlan")==null&&activationQueueField(screen,"activationDialog")==null;}
                catch(Exception error){throw new AssertionError(error);}
            });
            assertThat(pending[0],"inflight prepare has no completed plan");
            runOnMainSync(old::finish);
            boolean[] destroyed={false};end=android.os.SystemClock.uptimeMillis()+5000;
            while(!destroyed[0]&&android.os.SystemClock.uptimeMillis()<end){
                runOnMainSync(()->{
                    try{destroyed[0]=old.isDestroyed()&&(Boolean)activationQueueField(screen,"closed");}
                    catch(Exception error){throw new AssertionError(error);}
                });
                if(!destroyed[0])Thread.sleep(10);
            }
            assertThat(destroyed[0]&&executor.isShutdown()&&!tail.isDone(),
                "inflight destruction precedes prepare release");
        }
        tail.get(10,java.util.concurrent.TimeUnit.SECONDS);
        awaitActivationRetired(old,screen);waitForIdleSync();
        boolean[] clean={false};runOnMainSync(()->{
            try{clean[0]=activationQueueField(screen,"activationDialog")==null&&
                activationQueueField(screen,"activationPlan")==null&&activationQueueField(screen,"activationAttempt")==null;}
            catch(Exception error){throw new AssertionError(error);}
        });
        assertThat(clean[0],"inflight no late owned UI");
        java.util.List<Path> added=new java.util.ArrayList<>();
        try(java.util.stream.Stream<Path> files=Files.list(directory)){files.filter(path->!prior.contains(path)).forEach(added::add);}
        Path retained=null,verification=null;
        for(Path path:added){
            String name=path.getFileName().toString();
            assertThat(!Files.isSymbolicLink(path),"inflight no backup symlinks");
            if(name.startsWith("before-shortcuts-")&&name.endsWith(".zip")&&Files.isRegularFile(path))retained=path;
            else if(name.startsWith("verify-")&&Files.isDirectory(path))verification=path;
        }
        assertThat(added.size()==2&&retained!=null&&verification!=null,"inflight completed backup layout");
        try(java.util.stream.Stream<Path> files=Files.list(verification)){
            assertThat(!files.findAny().isPresent(),"inflight verification root empty");
        }
        byte[] archived=Files.readAllBytes(retained);
        try(java.util.zip.ZipFile zip=new java.util.zip.ZipFile(retained.toFile())){
            assertThat(archived.length>0&&zip.size()>0,"inflight complete retained ZIP");
        }
        assertThat(Arrays.equals(before,activationUiCells(3)),"inflight exact schema3 history");
        uiActivity=null;closeActivationUi();launchActivationUi();
        assertThat(Arrays.equals(before,activationUiCells(3))&&Arrays.equals(archived,Files.readAllBytes(retained)),
            "inflight relaunch preserves history and backup");
        log.append("ACTIVATION_INFLIGHT_PASS prepare_running_finish_preserves_exact\n");
    }

    private void activationCallbackLifecycle(byte[] before)throws Exception{
        // Hold one main-thread turn until the real prepare worker has posted
        // its callback. finish() then precedes callback dispatch, NOT onDestroy.
        MainActivity old=uiActivity;TodayScreen screen=captureScreenOnMain(old);
        java.util.concurrent.ExecutorService executor=(java.util.concurrent.ExecutorService)activationQueueField(screen,"io");
        Path directory=root().resolve("activation-backups");
        java.util.Set<Path> prior=new java.util.HashSet<>();
        if(Files.exists(directory))try(java.util.stream.Stream<Path> files=Files.list(directory)){
            files.forEach(prior::add);
        }
        Path[] retained={null};byte[][] archived={null};Throwable[] failure={null};
        runOnMainSync(()->{
            try{
                java.lang.reflect.Method request=TodayScreen.class.getDeclaredMethod("requestShortcutActivation");
                request.setAccessible(true);request.invoke(screen);
                executor.submit(()->null).get(2,java.util.concurrent.TimeUnit.SECONDS);
                assertThat((Boolean)activationQueueField(screen,"busy")&&
                    activationQueueField(screen,"activationPlan")==null&&
                    activationQueueField(screen,"activationDialog")==null,
                    "activation callback worker done before UI dispatch");
                java.util.List<Path> added=new java.util.ArrayList<>();
                try(java.util.stream.Stream<Path> files=Files.list(directory)){
                    files.filter(path->!prior.contains(path)).forEach(added::add);
                }
                java.util.List<Path> archives=new java.util.ArrayList<>();
                java.util.List<Path> verification=new java.util.ArrayList<>();
                for(Path path:added){
                    assertThat(!Files.isSymbolicLink(path),"activation callback no backup symlinks");
                    if(Files.isRegularFile(path,java.nio.file.LinkOption.NOFOLLOW_LINKS))archives.add(path);
                    else if(Files.isDirectory(path,java.nio.file.LinkOption.NOFOLLOW_LINKS))verification.add(path);
                }
                assertThat(added.size()==2&&archives.size()==1&&verification.size()==1&&
                    archives.get(0).getFileName().toString().startsWith("before-shortcuts-")&&
                    archives.get(0).getFileName().toString().endsWith(".zip")&&
                    verification.get(0).getFileName().toString().startsWith("verify-"),
                    "activation callback exact archive and verification root: "+added);
                try(java.util.stream.Stream<Path> files=Files.list(verification.get(0))){
                    assertThat(!files.findAny().isPresent(),"activation callback verification root empty");
                }
                retained[0]=archives.get(0);archived[0]=Files.readAllBytes(retained[0]);
                try(java.util.zip.ZipFile zip=new java.util.zip.ZipFile(retained[0].toFile())){
                    assertThat(zip.size()>0,"activation callback backup is complete ZIP");
                }
                old.finish();
                assertThat(old.isFinishing()&&activationQueueField(screen,"activationPlan")==null,
                    "activation callback finish precedes delivery");
            }catch(Throwable error){failure[0]=error;old.finish();}
        });
        if(failure[0]!=null)throw new AssertionError("activation callback setup",failure[0]);
        // Idleness is not lifecycle completion. Observe on the main thread;
        // finish() was requested exactly once above, never retried here.
        boolean[] destroyed={false};
        long destroyEnd=android.os.SystemClock.uptimeMillis()+5000;
        while(!destroyed[0]&&android.os.SystemClock.uptimeMillis()<destroyEnd){
            runOnMainSync(()->destroyed[0]=old.isDestroyed());
            if(!destroyed[0])Thread.sleep(10);
        }
        assertThat(destroyed[0],"activation callback destroy observation deadline");
        awaitActivationRetired(old,screen);waitForIdleSync();
        boolean[] clean={false};runOnMainSync(()->{
            try{clean[0]=activationQueueField(screen,"activationDialog")==null&&
                activationQueueField(screen,"activationPlan")==null&&
                activationQueueField(screen,"activationAttempt")==null;}
            catch(Exception e){throw new AssertionError(e);}
        });
        assertThat(clean[0],"activation callback no late owned UI");
        assertThat(Arrays.equals(before,activationUiCells(3))&&
            Arrays.equals(archived[0],Files.readAllBytes(retained[0])),
            "activation callback exact cells and retained backup");
        uiActivity=null;closeActivationUi();launchActivationUi();
        assertThat(Arrays.equals(before,activationUiCells(3)),
            "activation callback relaunch exact history");
        log.append("ACTIVATION_CALLBACK_PASS prepare_complete_finish_before_delivery_exact\n");
    }

    private void activationQueueNeed(boolean ok,String label){
        assertThat(ok,label);log.append("ACTIVATION_QUEUE_PASS ").append(label).append('\n');
    }
    private Object activationQueueField(TodayScreen screen,String name)throws Exception{
        java.lang.reflect.Field field=TodayScreen.class.getDeclaredField(name);
        field.setAccessible(true);return field.get(screen);
    }
    private boolean finishQueuedActivation(boolean confirm,byte[] before)throws Exception{
        // The real screen executor is held BEFORE the requested operation.
        // This is queued work, not an in-progress SQLite transaction.
        Path backup=null;byte[] backupBytes=null;
        if(confirm){
            touchUi("activation-entry");awaitActivation("activation-confirm");
            backup=activationUiBackup();backupBytes=Files.readAllBytes(backup);
            touchActivation("activation-consent");
        }
        MainActivity old=uiActivity;TodayScreen screen=captureScreenOnMain(old);
        java.util.concurrent.ExecutorService executor=(java.util.concurrent.ExecutorService)activationQueueField(screen,"io");
        java.util.concurrent.CountDownLatch entered=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.CountDownLatch release=new java.util.concurrent.CountDownLatch(1);
        java.util.concurrent.Future<?> held=executor.submit(()->{
            entered.countDown();
            if(!release.await(10,java.util.concurrent.TimeUnit.SECONDS))
                throw new AssertionError("activation queue release deadline");
            return null;
        });
        try{
            assertThat(entered.await(10,java.util.concurrent.TimeUnit.SECONDS),"activation queue worker held");
            if(confirm)touchActivation("activation-confirm");else touchUi("activation-entry");
            boolean[] busy={false};runOnMainSync(()->{
                try{busy[0]=(Boolean)activationQueueField(screen,"busy");}
                catch(Exception e){throw new AssertionError(e);}
            });
            assertThat(busy[0]&&!held.isDone(),"activation queue request actually pending");
            runOnMainSync(old::finish);
            boolean[] retired={false};
            long end=android.os.SystemClock.uptimeMillis()+5000;
            while(!retired[0]&&android.os.SystemClock.uptimeMillis()<end){
                runOnMainSync(()->{
                    try{retired[0]=old.isDestroyed()&&(Boolean)activationQueueField(screen,"closed");}
                    catch(Exception e){throw new AssertionError(e);}
                });
                if(!retired[0])Thread.sleep(10);
            }
            assertThat(retired[0]&&executor.isShutdown()&&!held.isDone(),
                "activation queue destruction precedes worker release");
        }finally{release.countDown();}
        held.get(10,java.util.concurrent.TimeUnit.SECONDS);
        awaitActivationRetired(old,screen);
        waitForIdleSync();
        boolean[] clean={false};runOnMainSync(()->{
            try{clean[0]=activationQueueField(screen,"activationDialog")==null&&
                activationQueueField(screen,"activationPlan")==null&&
                activationQueueField(screen,"activationAttempt")==null;}
            catch(Exception e){throw new AssertionError(e);}
        });
        assertThat(clean[0],"activation queue no late dialog or owned plan");
        boolean exact=Arrays.equals(before,activationUiCells(3))&&
            (backup==null||Arrays.equals(backupBytes,Files.readAllBytes(backup)));
        uiActivity=null;closeActivationUi();launchActivationUi();
        return exact&&Arrays.equals(before,activationUiCells(3));
    }
    private void activationQueuedLifecycle(byte[] before)throws Exception{
        activationQueueNeed(finishQueuedActivation(false,before),
            "activation_queue_prepare_finish_preserves_exact");
        activationQueueNeed(finishQueuedActivation(true,before),
            "activation_queue_confirm_finish_preserves_exact");
    }

    private void activationLifeNeed(boolean ok,String label){
        assertThat(ok,label);log.append("ACTIVATION_LIFE_PASS ").append(label).append('\n');
    }
    private void awaitActivationRetired(MainActivity old,TodayScreen screen)throws Exception{
        waitForIdleSync();
        boolean[] destroyed={false};runOnMainSync(()->destroyed[0]=old.isDestroyed());
        assertThat(destroyed[0],"activation lifecycle old Activity destroyed");
        java.lang.reflect.Field f=MainActivity.class.getDeclaredField("startupIo");f.setAccessible(true);
        java.util.concurrent.ExecutorService executor=(java.util.concurrent.ExecutorService)f.get(old);
        assertThat(executor.awaitTermination(10,java.util.concurrent.TimeUnit.SECONDS),"activation lifecycle startup executor retired");
        assertThat(screen.awaitShortcutClose(),"activation lifecycle screen executor retired");
    }
    private void activationLifecycle(byte[] before)throws Exception{
        // These are real Android configuration/recreation/finish events, not
        // simulated callbacks. Preparation-in-flight and commit-in-flight are
        // deliberately not claimed by this completed-preview suite.
        touchUi("activation-entry");awaitActivation("activation-confirm");
        Path rotatedBackup=activationUiBackup();byte[] rotatedBytes=Files.readAllBytes(rotatedBackup);
        touchActivation("activation-consent");
        android.view.View rotatedConfirm=awaitActivation("activation-confirm");
        MainActivity rotated=uiActivity;TodayScreen rotatedScreen=captureScreenOnMain(rotated);
        int[] orientation={0};
        runOnMainSync(()->orientation[0]=rotated.getResources().getConfiguration().orientation);
        assertThat(orientation[0]==1||orientation[0]==2,"activation lifecycle known orientation");
        int target=orientation[0]==1?2:1;
        ActivityMonitor rotationMonitor=addMonitor(MainActivity.class.getName(),null,false);
        try{
            runOnMainSync(()->rotated.setRequestedOrientation(target==2?
                android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE:
                android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT));
            Activity replacement=waitForMonitorWithTimeout(rotationMonitor,10000);
            assertThat(replacement instanceof MainActivity&&replacement!=rotated,"activation lifecycle rotation replacement");
            uiActivity=(MainActivity)replacement;awaitUi("todo-todo");
            runOnMainSync(()->orientation[0]=uiActivity.getResources().getConfiguration().orientation);
            assertThat(orientation[0]==target,"activation lifecycle actual orientation changed");
            awaitActivationRetired(rotated,rotatedScreen);
        }finally{removeMonitor(rotationMonitor);}
        runOnMainSync(()->rotatedConfirm.performClick());waitForIdleSync();
        activationLifeNeed(Arrays.equals(before,activationUiCells(3))&&
            Arrays.equals(rotatedBytes,Files.readAllBytes(rotatedBackup)),
            "activation_life_rotation_stale_consent_preserves_exact");

        touchUi("activation-entry");awaitActivation("activation-confirm");
        Path recreatedBackup=activationUiBackup();byte[] recreatedBytes=Files.readAllBytes(recreatedBackup);
        touchActivation("activation-consent");
        android.view.View recreatedConfirm=awaitActivation("activation-confirm");
        MainActivity recreated=uiActivity;TodayScreen recreatedScreen=captureScreenOnMain(recreated);
        ActivityMonitor recreateMonitor=addMonitor(MainActivity.class.getName(),null,false);
        try{
            runOnMainSync(recreated::recreate);
            Activity replacement=waitForMonitorWithTimeout(recreateMonitor,10000);
            assertThat(replacement instanceof MainActivity&&replacement!=recreated,"activation lifecycle explicit replacement");
            uiActivity=(MainActivity)replacement;awaitUi("todo-todo");
            awaitActivationRetired(recreated,recreatedScreen);
        }finally{removeMonitor(recreateMonitor);}
        runOnMainSync(()->recreatedConfirm.performClick());waitForIdleSync();
        activationLifeNeed(Arrays.equals(before,activationUiCells(3))&&
            Arrays.equals(recreatedBytes,Files.readAllBytes(recreatedBackup)),
            "activation_life_recreate_stale_consent_preserves_exact");

        touchUi("activation-entry");awaitActivation("activation-confirm");
        Path finishedBackup=activationUiBackup();byte[] finishedBytes=Files.readAllBytes(finishedBackup);
        touchActivation("activation-consent");
        android.view.View finishedConfirm=awaitActivation("activation-confirm");
        MainActivity finished=uiActivity;TodayScreen finishedScreen=captureScreenOnMain(finished);
        closeActivationUi();awaitActivationRetired(finished,finishedScreen);
        runOnMainSync(()->finishedConfirm.performClick());waitForIdleSync();
        activationLifeNeed(Arrays.equals(before,activationUiCells(3))&&
            Arrays.equals(finishedBytes,Files.readAllBytes(finishedBackup)),
            "activation_life_finish_stale_consent_preserves_exact");
        launchActivationUi();
    }

    private static final String ACTIVATION_UI_DB="schema4-activation-ui.db";
    private void activationUiNeed(boolean ok,String label){
        assertThat(ok,label);log.append("ACTIVATION_UI_PASS ").append(label).append('\n');
    }
    private void launchActivationUi()throws Exception{
        MainActivity.isolatedShortcutTest=false;MainActivity.isolatedStartupTest=false;
        MainActivity.isolatedActivationTest=true;
        uiActivity=(MainActivity)startActivitySync(new android.content.Intent(getTargetContext(),MainActivity.class)
            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
        awaitUi("todo-todo");
    }
    private void closeActivationUi()throws Exception{
        try{closeStartupUi();}finally{MainActivity.isolatedActivationTest=false;}
    }
    private byte[] activationUiCells(int version)throws Exception{
        try(SQLiteDatabase db=SQLiteDatabase.openDatabase(getTargetContext().getDatabasePath(ACTIVATION_UI_DB).getPath(),null,
                SQLiteDatabase.OPEN_READWRITE,(bad)->{throw new IllegalStateException("activation fixture corruption");})){
            assertThat(db.getVersion()==version,"activation UI expected schema");
            return cells(db,true);
        }
    }
    private android.view.View awaitActivation(String id)throws Exception{
        long end=android.os.SystemClock.uptimeMillis()+10000;
        while(android.os.SystemClock.uptimeMillis()<end){
            android.view.View[] found={null};
            runOnMainSync(()->{
                TodayScreen screen=uiActivity.shortcutTestScreen();
                if(screen==null)return;
                try{
                    java.lang.reflect.Field f=TodayScreen.class.getDeclaredField("activationDialog");f.setAccessible(true);
                    android.app.AlertDialog d=(android.app.AlertDialog)f.get(screen);
                    if(d==null||d.getWindow()==null)return;
                    android.view.View v=findUi(d.getWindow().getDecorView(),id);
                    if(v!=null&&v.isAttachedToWindow()&&v.isEnabled())found[0]=v;
                }catch(ReflectiveOperationException e){throw new AssertionError(e);}
            });
            if(found[0]!=null)return found[0];
            Thread.sleep(25);
        }
        throw new AssertionError("activation dialog observation deadline "+id);
    }
    private static android.graphics.Rect activationTouchRect(android.view.View view){
        android.graphics.Rect rect=new android.graphics.Rect();
        assertThat(view.isEnabled()&&view.isAttachedToWindow()&&view.getLocalVisibleRect(rect)
            &&rect.width()>0&&rect.height()>0,"activation visible screen bounds");
        int[] screen=new int[2];view.getLocationOnScreen(screen);
        rect.offset(screen[0],screen[1]);
        return rect;
    }

    private android.view.View touchActivation(String id)throws Exception{
        android.view.View v=awaitActivation(id);
        runOnMainSync(()->v.requestRectangleOnScreen(new android.graphics.Rect(0,0,v.getWidth(),v.getHeight()),true));
        waitForIdleSync();android.graphics.Rect r=new android.graphics.Rect();
        runOnMainSync(()->r.set(activationTouchRect(v)));
        long now=android.os.SystemClock.uptimeMillis();
        android.view.MotionEvent down=android.view.MotionEvent.obtain(now,now,0,r.exactCenterX(),r.exactCenterY(),0);
        android.view.MotionEvent up=android.view.MotionEvent.obtain(now,now+50,1,r.exactCenterX(),r.exactCenterY(),0);
        try{sendPointerSync(down);sendPointerSync(up);}finally{down.recycle();up.recycle();}
        waitForIdleSync();return v;
    }
    private Path activationUiBackup()throws Exception{
        AppDatabase.ShortcutActivationPlan[] plan={null};
        runOnMainSync(()->{
            try{
                java.lang.reflect.Field f=TodayScreen.class.getDeclaredField("activationPlan");f.setAccessible(true);
                plan[0]=(AppDatabase.ShortcutActivationPlan)f.get(uiActivity.shortcutTestScreen());
            }catch(ReflectiveOperationException e){throw new AssertionError(e);}
        });
        assertThat(plan[0]!=null,"actual activation plan");
        return root().resolve("activation-backups").resolve(plan[0].backupName());
    }
    private void activationUiSeed()throws Exception{
        Context context=getTargetContext();
        assertThat(!context.getDatabasePath("pocket-v12.db").exists(),"activation UI phone absent before");
        context.deleteDatabase(ACTIVATION_UI_DB);
        try(SQLiteDatabase db=context.openOrCreateDatabase(ACTIVATION_UI_DB,0,null)){frozen(db);}
        try(Schema3Store old=new Schema3Store(context,ACTIVATION_UI_DB)){old.getWritableDatabase();}
        MediaRepository m=new MediaRepository(root().resolve("media"),64L*1024*1024);
        assertThat(ASSET.equals(m.copy(new ByteArrayInputStream(new byte[]{97,98,99}))),"activation real media abc vector");
        byte[] before=activationUiCells(3);
        activationPostDdlLifecycle(before);
        try{
            launchActivationUi();touchUi("activation-entry");
            android.view.View stale=awaitActivation("activation-confirm");
            Path retained=activationUiBackup();
            activationUiNeed(Files.size(retained)>0&&Arrays.equals(before,activationUiCells(3)),"activation_ui_preview_keeps_schema3");
            touchActivation("activation-confirm");
            android.widget.TextView validation=(android.widget.TextView)awaitActivation("activation-validation");
            String[] warning={""};runOnMainSync(()->warning[0]=validation.getText().toString());
            assertThat(warning[0].startsWith("请先勾选"),"unchecked validation feedback: "+warning[0]);
            byte[] unchecked=activationUiCells(3);
            assertThat(Arrays.equals(before,unchecked),"unchecked exact old cells changed");
            activationUiNeed(warning[0].startsWith("请先勾选")&&Arrays.equals(before,unchecked),"activation_ui_unchecked_cannot_commit");
            touchActivation("activation-cancel");awaitUiText("v12-status","已取消启用");
            activationUiNeed(Files.isRegularFile(retained)&&Arrays.equals(before,activationUiCells(3)),"activation_ui_cancel_keeps_backup_and_cells");
            runOnMainSync(()->stale.performClick());waitForIdleSync();
            activationUiNeed(Arrays.equals(before,activationUiCells(3)),"activation_ui_stale_confirm_refused");
            activationLifecycle(before);
            activationQueuedLifecycle(before);
            activationCallbackLifecycle(before);
            activationInflightLifecycle(before);
            activationConfirmRunningLifecycle(before);
            touchUi("activation-entry");awaitActivation("activation-confirm");
            Path changed=activationUiBackup();Files.write(changed,new byte[]{0});
            TodayScreen old=captureScreenOnMain(uiActivity);
            touchActivation("activation-consent");touchActivation("activation-confirm");
            awaitUi("activation-restart-required");
            assertThat(old.awaitShortcutClose(),"failed activation facade retired");
            activationUiNeed(Arrays.equals(before,activationUiCells(3)),"activation_ui_changed_backup_refused");
            closeActivationUi();launchActivationUi();touchUi("activation-entry");awaitActivation("activation-confirm");
            Path good=activationUiBackup();
            ActivityMonitor monitor=addMonitor(MainActivity.class.getName(),null,false);
            TodayScreen retired=captureScreenOnMain(uiActivity);
            try{
                touchActivation("activation-consent");touchActivation("activation-confirm");
                Activity replacement=waitForMonitorWithTimeout(monitor,10000);
                assertThat(replacement instanceof MainActivity&&replacement!=uiActivity,"activation actual recreation");
                uiActivity=(MainActivity)replacement;awaitUi("todo-todo");
                assertThat(retired.awaitShortcutClose(),"successful activation old facade retired");
            }finally{removeMonitor(monitor);}
            activationUiNeed(Files.isRegularFile(good)&&Arrays.equals(before,activationUiCells(4)),"activation_ui_confirm_recreates_with_exact_history");
            touchUi("activation-entry");awaitUiText("v12-status","分类快捷入口已启用");
            activationUiNeed(Arrays.equals(before,activationUiCells(4)),"activation_ui_repeat_entry_is_noop");
            closeActivationUi();
            Files.write(root().resolve("activation-ui-expected.bin"),before);
            activationUiNeed(!context.getDatabasePath("pocket-v12.db").exists(),"activation_ui_phone_database_absent");
        }finally{closeActivationUi();}
    }
    private void activationUiReopen()throws Exception{
        byte[] expected=Files.readAllBytes(root().resolve("activation-ui-expected.bin"));
        try{launchActivationUi();awaitUi("todo-todo");}finally{closeActivationUi();}
        activationUiNeed(Arrays.equals(expected,activationUiCells(4)),"activation_ui_separate_process_exact");
        activationUiNeed(!getTargetContext().getDatabasePath("pocket-v12.db").exists(),"activation_ui_separate_process_phone_absent");
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
