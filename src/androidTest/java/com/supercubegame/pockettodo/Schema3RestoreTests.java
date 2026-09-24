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
        try(java.util.stream.Stream<Path> files=Files.list(directory)){return files.findAny().isEmpty();}
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
            need(empty(stage)&&empty(root.resolve("schema3-restore-media"))&&Arrays.equals(changed,store.exportState()),"restore_other_connection_same_revision_stale_refused");

            Schema3Store.RestorePlan damaged=store.prepareRestore(archives.resolve("good.zip"),stage,1000000);
            String id=Files.readString(root.resolve("schema3-ids.txt")).trim().split("\\s+")[0];
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
            String[] ids=Files.readString(root.resolve("schema3-ids.txt")).trim().split("\\s+");
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
        restoreShape("empty",archives.resolve("empty.zip"),Files.readAllBytes(archives.resolve("empty-state.bin")),stage);
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
                    String[] ids=Files.readString(root.resolve("schema3-ids.txt")).trim().split("\\s+");
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
