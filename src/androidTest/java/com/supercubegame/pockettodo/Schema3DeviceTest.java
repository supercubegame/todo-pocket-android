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

/** Runs only after the old mandatory suite, using its frozen historical fixture.
 * Synthetic media bytes test storage, NOT decoding or redaction.
 */
public final class Schema3DeviceTest extends Instrumentation {
    private Bundle args;
    private int checks;
    private final StringBuilder log=new StringBuilder();
    private static final String DB="schema3-contract.db";
    private static final String[] TABLES={"revision","categories","applications","activities","paths","tags","batches","ledger","checkins","media","notes","blocks","fields","field_options","field_values","field_notes","todos","legacy_imports"};
    private interface Action {void run()throws Exception;}
    @Override public void onCreate(Bundle args){super.onCreate(args);this.args=args;start();}
    private void need(boolean ok,String label){if(!ok)throw new AssertionError(label);checks++;log.append("SCHEMA3_PASS ").append(label).append('\n');}
    private void refused(Action action)throws Exception{
        boolean rejected=false;try{action.run();}catch(IllegalArgumentException|IllegalStateException e){rejected=true;}
        if(!rejected)throw new AssertionError("operation unexpectedly accepted");
    }
    private static void text(DataOutputStream out,String value)throws IOException{byte[] b=value.getBytes(java.nio.charset.StandardCharsets.UTF_8);out.writeInt(b.length);out.write(b);}
    /** Independent exact old-cell projection, no production fingerprint method. */
    private byte[] oldCells(SQLiteDatabase db)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        for(String table:TABLES){
            String cols=table.equals("blocks")?"note_id,id,position,kind,text,asset_id,caption,private":"*";
            try(Cursor c=db.rawQuery("SELECT "+cols+" FROM "+table+" ORDER BY rowid",null)){
                text(out,table);out.writeInt(c.getCount());out.writeInt(c.getColumnCount());
                for(String name:c.getColumnNames())text(out,name);
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){
                    int type=c.getType(i);out.writeByte(type);
                    if(type==1)out.writeLong(c.getLong(i));else if(type==3)text(out,c.getString(i));else if(type==4){byte[] b=c.getBlob(i);out.writeInt(b.length);out.write(b);}else if(type!=0)throw new AssertionError("unexpected old type");
                }
            }
        }out.flush();return bytes.toByteArray();
    }
    private long revision(SQLiteDatabase db){try(Cursor c=db.rawQuery("SELECT value FROM revision WHERE id=1",null)){if(!c.moveToFirst())throw new AssertionError("revision missing");return c.getLong(0);}}
    private int columns(SQLiteDatabase db){try(Cursor c=db.rawQuery("SELECT * FROM blocks LIMIT 0",null)){return c.getColumnCount();}}
    private void seed()throws Exception{
        Context c=getTargetContext();Path root=c.getFilesDir().toPath();
        // The old runner created this from frozen V1_DDL+V2_EXTRA_DDL, not live DDL.
        File source=c.getDatabasePath("frozen-v2.db");byte[] before;
        try(SQLiteDatabase old=SQLiteDatabase.openDatabase(source.getPath(),null,SQLiteDatabase.OPEN_READWRITE)){
            need(old.getVersion()==2&&columns(old)==8,"frozen_v2_input");
            before=oldCells(old);
            try(Cursor checkpoint=old.rawQuery("PRAGMA wal_checkpoint(TRUNCATE)",null)){
                if(!checkpoint.moveToFirst()||checkpoint.getInt(0)!=0)throw new AssertionError("fixture checkpoint busy");
            }
        }
        c.deleteDatabase(DB);Files.copy(source.toPath(),c.getDatabasePath(DB).toPath());
        try(Schema3Store store=new Schema3Store(c,DB)){
            SQLiteDatabase db=store.getWritableDatabase();
            need(db.getVersion()==3&&columns(db)==9,"migration_version_and_column");
            need(Arrays.equals(before,oldCells(db))&&revision(db)==42,"migration_preserves_all_old_cells");
            NoteDocument.ImageEdit original=store.imageEdit("second","photo");
            String a=original.revision().assetId;
            need(a.equals(original.revision().originalAssetId)&&original.caption.equals("同图另一篇")&&!original.privateContent,"legacy_origin_fallback");
            MediaRepository media=new MediaRepository(root.resolve("schema3-media"),1000000);
            String originalId=media.copy(new ByteArrayInputStream(new byte[]{97,98,99}));
            String b=media.copy(new ByteArrayInputStream(new byte[]{1,2,3,4}));
            String d=media.copy(new ByteArrayInputStream(new byte[]{5,6,7,8}));
            if(!a.equals(originalId))throw new AssertionError("frozen original differs");
            db.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',4)",new Object[]{b});
            db.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',4)",new Object[]{d});
            byte[] baseline=store.snapshot();long rev=revision(db);
            need(Arrays.equals(store.snapshot(),baseline),"snapshot_is_read_only");
            store.saveImageEdit(original.withDerivative(b).withMetadata("派生说明",true),baseline);
            NoteDocument.ImageEdit first=store.imageEdit("second","photo");
            need(first.revision().assetId.equals(b)&&first.revision().originalAssetId.equals(a)&&first.caption.equals("派生说明")&&first.privateContent&&revision(db)==rev+1,"first_derivative_persisted");
            NoteDocument.ImageEdit sibling=store.imageEdit("first","photo");
            need(sibling.revision().assetId.equals(a)&&sibling.revision().originalAssetId.equals(a)&&sibling.caption.equals("原图说明")&&sibling.privateContent,"sibling_note_isolated");
            refused(()->store.saveImageEdit(first,baseline));
            need(revision(db)==rev+1&&store.imageEdit("second","photo").revision().assetId.equals(b),"stale_full_state_rejected");
            byte[] exact=store.snapshot();
            store.saveImageEdit(first.withDerivative(d),exact);
            NoteDocument.ImageEdit second=store.imageEdit("second","photo");
            need(second.revision().assetId.equals(d)&&second.revision().originalAssetId.equals(a)&&second.privateContent&&second.caption.equals("派生说明"),"second_derivative_keeps_original");
            store.saveImageEdit(second.withMetadata("",false),store.snapshot());
            NoteDocument.ImageEdit metadata=store.imageEdit("second","photo");
            need(metadata.caption.isEmpty()&&!metadata.privateContent&&metadata.revision().assetId.equals(d)&&metadata.revision().originalAssetId.equals(a),"metadata_preserves_pair");
            byte[] unchanged=store.snapshot();
            refused(()->store.saveImageEdit(metadata.withDerivative("f".repeat(64)),unchanged));
            need(Arrays.equals(unchanged,store.snapshot()),"missing_registry_rolls_back");
            NoteDocument.ImageEdit wrong=new NoteDocument.ImageEdit("second",NoteDocument.Block.image("photo",d,"wrong",true),b);
            refused(()->store.saveImageEdit(wrong,unchanged));
            need(Arrays.equals(unchanged,store.snapshot()),"wrong_origin_rolls_back");
            refused(()->store.imageEdit("second","text"));
            need(Arrays.equals(unchanged,store.snapshot()),"text_target_rejected");
            byte[] stale=store.snapshot();db.execSQL("UPDATE todos SET title='外部同修订变更' WHERE id='old-todo'");
            byte[] externallyChanged=store.snapshot();
            refused(()->store.saveImageEdit(metadata.withDerivative(b),stale));
            need(Arrays.equals(externallyChanged,store.snapshot()),"same_revision_external_change_rejected");
            db.execSQL("CREATE TEMP TRIGGER schema3_fault BEFORE UPDATE ON revision BEGIN SELECT RAISE(ABORT,'schema3_late_commit_fault'); END");
            boolean exactFault=false;try{store.saveImageEdit(metadata.withDerivative(b),externallyChanged);}catch(Exception e){for(Throwable x=e;x!=null;x=x.getCause())if(String.valueOf(x.getMessage()).contains("schema3_late_commit_fault"))exactFault=true;}
            need(exactFault&&Arrays.equals(externallyChanged,store.snapshot()),"late_sql_fault_rolls_back_target_and_revision");
            db.execSQL("DROP TRIGGER schema3_fault");
            need(Arrays.equals(Files.readAllBytes(media.path(a)),new byte[]{97,98,99})&&Arrays.equals(Files.readAllBytes(media.path(b)),new byte[]{1,2,3,4})&&Arrays.equals(Files.readAllBytes(media.path(d)),new byte[]{5,6,7,8}),"all_original_and_derived_bytes_unchanged");
            byte[] owned=store.snapshot();owned[0]^=1;
            need(Arrays.equals(externallyChanged,store.snapshot()),"snapshot_caller_mutation_isolated");
            Files.write(root.resolve("schema3-expected.bin"),store.snapshot());
            Files.write(root.resolve("schema3-ids.txt"),String.join("\n",a,b,d).getBytes(java.nio.charset.StandardCharsets.US_ASCII));
        }
        boolean refused=false;try(AppDatabase legacy=new AppDatabase(c,DB)){legacy.getWritableDatabase();}catch(IllegalStateException e){refused=true;}
        try(Schema3Store store=new Schema3Store(c,DB)){need(refused&&Arrays.equals(Files.readAllBytes(root.resolve("schema3-expected.bin")),store.snapshot()),"old_helper_refuses_without_damage");}
        c.deleteDatabase("schema3-conflict.db");
        Files.copy(source.toPath(),c.getDatabasePath("schema3-conflict.db").toPath());
        byte[] conflict;
        try(SQLiteDatabase db=c.openOrCreateDatabase("schema3-conflict.db",0,null)){db.execSQL("ALTER TABLE blocks ADD COLUMN original_asset_id TEXT");conflict=oldCells(db);}
        boolean conflictRefused=false;try(Schema3Store store=new Schema3Store(c,"schema3-conflict.db")){store.getWritableDatabase();}catch(RuntimeException e){conflictRefused=true;}
        try(SQLiteDatabase db=c.openOrCreateDatabase("schema3-conflict.db",0,null)){need(conflictRefused&&db.getVersion()==2&&columns(db)==9&&Arrays.equals(conflict,oldCells(db)),"partial_schema_conflict_not_hidden");}
    }
    private void reopen()throws Exception{
        Context c=getTargetContext();Path root=c.getFilesDir().toPath();
        try(Schema3Store store=new Schema3Store(c,DB)){
            need(Arrays.equals(Files.readAllBytes(root.resolve("schema3-expected.bin")),store.snapshot()),"separate_process_exact_state");
            String[] ids=new String(Files.readAllBytes(root.resolve("schema3-ids.txt")),java.nio.charset.StandardCharsets.US_ASCII).split("\n");
            NoteDocument.ImageEdit edit=store.imageEdit("second","photo");
            need(edit.revision().assetId.equals(ids[2])&&edit.revision().originalAssetId.equals(ids[0])&&edit.caption.isEmpty()&&!edit.privateContent,"separate_process_pair_metadata");
            MediaRepository media=new MediaRepository(root.resolve("schema3-media"),1000000);
            for(String id:ids)media.verify(id);
            need(Arrays.equals(Files.readAllBytes(media.path(ids[0])),new byte[]{97,98,99})&&Arrays.equals(Files.readAllBytes(media.path(ids[2])),new byte[]{5,6,7,8}),"separate_process_media_bytes");
            store.saveImageEdit(edit.withMetadata("重启后编辑",true),store.snapshot());
            need(store.imageEdit("second","photo").caption.equals("重启后编辑")&&store.imageEdit("second","photo").revision().originalAssetId.equals(ids[0]),"separate_process_write_usable");
        }
    }
    @Override public void onStart(){
        Bundle result=new Bundle();try{
            if(!getTargetContext().getPackageName().equals("com.supercubegame.pockettodo.v12.preview"))throw new AssertionError("wrong package");
            int api=Integer.parseInt(args.getString("expectedApi"));
            if(android.os.Build.VERSION.SDK_INT!=api)throw new AssertionError("wrong actual API");
            String phase=args.getString("phase");if("seed".equals(phase))seed();else if("reopen".equals(phase))reopen();else throw new AssertionError("wrong phase");
            log.append("SCHEMA3_RESULT ").append(phase).append(' ').append(api).append(' ').append(checks).append(" PASS\n");
            result.putString("stream",log.toString());finish(Activity.RESULT_OK,result);
        }catch(Throwable error){StringWriter stack=new StringWriter();error.printStackTrace(new PrintWriter(stack));result.putString("stream",log+"SCHEMA3_FAILED\n"+stack);finish(Activity.RESULT_CANCELED,result);}
    }
}
