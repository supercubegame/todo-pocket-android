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
        return oldCells(db,TABLES);
    }
    private byte[] oldCells(SQLiteDatabase db,String[] tables)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        for(String table:tables){
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
    private int columns(SQLiteDatabase db){
        List<String> names=new ArrayList<>();
        try(Cursor c=db.rawQuery("PRAGMA table_info(blocks)",null)){while(c.moveToNext())names.add(c.getString(c.getColumnIndexOrThrow("name")));}
        int cached;
        try(Cursor c=db.rawQuery("SELECT * FROM blocks LIMIT 0",null)){cached=c.getColumnCount();}
        // ALTER can leave cached SELECT-star metadata on older Android SQLite.
        // Explicit names independently require every declared column to compile.
        try(Cursor c=db.rawQuery("SELECT "+String.join(",",names)+" FROM blocks LIMIT 0",null)){
            log.append("SCHEMA3_LAYOUT version=").append(db.getVersion()).append(" star=").append(cached).append(" declared=").append(names).append(" explicit=").append(Arrays.toString(c.getColumnNames())).append('\n');
            if(!Arrays.equals(c.getColumnNames(),names.toArray(new String[0])))throw new AssertionError("declared and explicit block layout differ");
        }
        return names.size();
    }
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
            int migratedColumns=columns(db);
            need(db.getVersion()==3&&migratedColumns==9,"migration_version_and_column");
            try(Cursor layout=db.rawQuery("SELECT note_id,id,position,kind,text,asset_id,caption,private,original_asset_id FROM blocks LIMIT 0",null)){
                if(!Arrays.equals(layout.getColumnNames(),new String[]{"note_id","id","position","kind","text","asset_id","caption","private","original_asset_id"}))throw new AssertionError("exact schema3 column names differ");
            }
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
        try(Schema3Store store=new Schema3Store(c,DB)){budgetChecks(store);}
        lifecycleSeed();
        ordinaryNoteSeed();
        postWriteBudgetSeed();
        legacyCandidateSeed();
        wireSeed();
    }
    /** Independent new wire fixture, including explicit ninth block column.
     * Never call the product encoder to manufacture rejection controls.
     */
    private byte[] newWire(SQLiteDatabase db,boolean reverse)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(0x50544442);out.writeInt(2);out.writeInt(3);out.writeInt(TABLES.length);
        for(String table:TABLES){
            String cols=table.equals("blocks")?"note_id,id,position,kind,text,asset_id,caption,private,original_asset_id":"*";
            try(Cursor c=db.rawQuery("SELECT "+cols+" FROM "+table+" ORDER BY rowid"+(reverse&&table.equals("categories")?" DESC":""),null)){
                text(out,table);out.writeInt(c.getColumnCount());for(String name:c.getColumnNames())text(out,name);out.writeInt(c.getCount());
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){
                    int type=c.getType(i);out.writeByte(type);
                    if(type==1)out.writeLong(c.getLong(i));else if(type==3)text(out,c.getString(i));
                    else if(type==4){byte[] value=c.getBlob(i);out.writeInt(value.length);out.write(value);}
                    else if(type!=0)throw new AssertionError("unexpected wire fixture type");
                }
            }
        }out.flush();return bytes.toByteArray();
    }
    private void wireRejected(byte[] input,String cause)throws Exception{
        boolean rejected=false;
        try(SQLiteDatabase ignored=Schema3Store.stateCandidate(input)){}
        catch(IllegalArgumentException failure){
            if(cause==null)rejected=true;
            for(Throwable e=failure;e!=null;e=e.getCause())
                if(cause!=null&&String.valueOf(e.getMessage()).contains(cause))rejected=true;
        }
        if(!rejected)throw new AssertionError("wire rejection missing: "+cause);
    }
    /** Locate mutation offsets by parsing the independent, valid fixture first.
     * No hardcoded byte offsets and no product decoder supplies these positions.
     */
    private Map<String,Integer> wireOffsets(byte[] wire)throws Exception{
        Map<String,Integer> offsets=new LinkedHashMap<>();
        ByteArrayInputStream bytes=new ByteArrayInputStream(wire);DataInputStream in=new DataInputStream(bytes);
        if(in.readInt()!=0x50544442||in.readInt()!=2||in.readInt()!=3||in.readInt()!=TABLES.length)throw new AssertionError("wire offset fixture header");
        for(String table:TABLES){
            offsets.put(table+"/length",wire.length-bytes.available());
            int length=in.readInt();byte[] name=new byte[length];in.readFully(name);
            if(!table.equals(new String(name,java.nio.charset.StandardCharsets.UTF_8)))throw new AssertionError("wire offset fixture table");
            offsets.put(table+"/columns",wire.length-bytes.available());
            int count=in.readInt();List<String> names=new ArrayList<>();
            for(int col=0;col<count;col++){
                int at=wire.length-bytes.available();length=in.readInt();name=new byte[length];in.readFully(name);
                String column=new String(name,java.nio.charset.StandardCharsets.UTF_8);names.add(column);offsets.put(table+"/"+column+"/name",at);
            }
            offsets.put(table+"/rows",wire.length-bytes.available());int rows=in.readInt();
            for(int row=0;row<rows;row++)for(String column:names){
                int at=wire.length-bytes.available(),tag=in.readUnsignedByte();
                if(row==0)offsets.put(table+"/"+column+"/cell",at);
                if(tag==1)in.readLong();
                else if(tag==3||tag==4){length=in.readInt();if(length<0||in.skipBytes(length)!=length)throw new AssertionError("wire offset fixture length");}
                else if(tag!=0)throw new AssertionError("wire offset fixture tag");
            }
        }
        if(bytes.available()!=0)throw new AssertionError("wire offset fixture trailing bytes");
        return offsets;
    }
    private void wireBoundaryChecks(byte[] wire)throws Exception{
        Map<String,Integer> at=wireOffsets(wire);
        try(SQLiteDatabase valid=Schema3Store.stateCandidate(wire)){
            if(!Arrays.equals(wire,newWire(valid,false)))throw new AssertionError("boundary positive control differs");
        }
        int controls=0;
        String[] intKeys={"revision/length","revision/length","revision/length","revision/columns","revision/columns","revision/rows","revision/rows","categories/name/cell","categories/name/cell","categories/name/cell"};
        int[] values={-1,Integer.MAX_VALUE,wire.length+1,0,3,-1,Integer.MAX_VALUE,-1,Integer.MAX_VALUE,wire.length+1};
        for(int i=0;i<intKeys.length;i++){
            byte[] bad=wire.clone();int offset=at.get(intKeys[i])+(intKeys[i].endsWith("/cell")?1:0);
            java.nio.ByteBuffer.wrap(bad).putInt(offset,values[i]);
            if(Arrays.equals(bad,wire))throw new AssertionError("integer boundary mutation unchanged: "+intKeys[i]);
            String cause=i<3||i>=7?"Invalid wire value length":i<5?"Schema3 column count differs":"Invalid schema3 row count";
            wireRejected(bad,cause);controls++;
        }
        String[] cellKeys={"revision/id/cell","revision/id/cell","revision/id/cell","revision/id/cell","revision/id/cell","categories/name/cell","categories/name/cell","batches/payload/cell"};
        int[] tags={0,2,3,4,255,1,4,3};
        String[] causes={"Forbidden wire NULL","Unknown wire cell type","Wire text type differs","Wire blob type differs","Unknown wire cell type","Wire integer type differs","Wire blob type differs","Wire text type differs"};
        for(int i=0;i<cellKeys.length;i++){
            Integer offset=at.get(cellKeys[i]);if(offset==null)throw new AssertionError("missing typed boundary fixture: "+cellKeys[i]);
            byte[] bad=wire.clone();if((bad[offset]&255)==tags[i])throw new AssertionError("tag mutation unchanged");
            bad[offset]=(byte)tags[i];wireRejected(bad,causes[i]);controls++;
        }
        byte[] bad=wire.clone();bad[at.get("revision/length")+4]='x';wireRejected(bad,"Missing or reordered schema3 table");controls++;
        bad=wire.clone();bad[at.get("revision/id/name")+4]='x';wireRejected(bad,"Schema3 column name differs");controls++;
        // Truncate inside each payload family, not merely at the archive tail.
        for(String key:new String[]{"revision/id/cell","categories/name/cell","batches/payload/cell"}){
            int offset=at.get(key);wireRejected(Arrays.copyOf(wire,offset+2),null);controls++;
        }
        // A rejected candidate must not poison the next independent invocation.
        try(SQLiteDatabase valid=Schema3Store.stateCandidate(wire)){
            if(valid.inTransaction()||valid.getVersion()!=3||!Arrays.equals(wire,newWire(valid,false)))throw new AssertionError("boundary rejection contaminated valid candidate");
        }
        if(controls!=23)throw new AssertionError("boundary control count differs: "+controls);
        log.append("SCHEMA3_WIRE_BOUNDARY controls=").append(controls).append(" positive=2\n");
    }
    private void wireSeed()throws Exception{
        Context c=getTargetContext();Path root=c.getFilesDir().toPath();
        byte[] old=Files.readAllBytes(root.resolve("frozen-v2-state.bin")),wire;
        try(SQLiteDatabase candidate=Schema3Store.stateCandidate(old)){
            need(candidate.getVersion()==3&&columns(candidate)==9&&!candidate.inTransaction(),"wire_legacy_dispatch_normalizes");
        }
        try(Schema3Store store=new Schema3Store(c,DB)){
            SQLiteDatabase db=store.getWritableDatabase();byte[] before=store.snapshot();
            wire=store.exportState();
            if(!Arrays.equals(wire,newWire(db,false)))throw new AssertionError("independent schema3 wire differs");
            try(SQLiteDatabase candidate=Schema3Store.stateCandidate(wire)){
                if(candidate.getVersion()!=3||columns(candidate)!=9||candidate.inTransaction()||!Arrays.equals(oldCells(db),oldCells(candidate))||!Arrays.equals(wire,newWire(candidate,false)))throw new AssertionError("wire roundtrip lost cells or ownership");
                try(Cursor rows=candidate.rawQuery("SELECT note_id,id,asset_id,original_asset_id FROM blocks WHERE kind='IMAGE' ORDER BY note_id,id",null);
                    Cursor expected=db.rawQuery("SELECT note_id,id,asset_id,original_asset_id FROM blocks WHERE kind='IMAGE' ORDER BY note_id,id",null)){
                    int count=0;while(expected.moveToNext()){
                        if(!rows.moveToNext())throw new AssertionError("image row missing");
                        for(int i=0;i<4;i++)if(!Objects.equals(expected.isNull(i)?null:expected.getString(i),rows.isNull(i)?null:rows.getString(i)))throw new AssertionError("image origin pair changed");
                        count++;
                    }if(rows.moveToNext()||count<2)throw new AssertionError("pair fixture incomplete");
                }
            }
            need(Arrays.equals(before,store.snapshot()),"wire_schema3_exact_roundtrip_preserves_pairs");
            byte[] owned=wire.clone();
            try(SQLiteDatabase candidate=Schema3Store.stateCandidate(owned)){
                owned[0]^=1;candidate.execSQL("UPDATE todos SET title='独立副本' WHERE id='old-todo'");
            }
            byte[] exported=store.exportState();exported[0]^=1;
            try(SQLiteDatabase candidate=Schema3Store.stateCandidate(wire)){
                need(Arrays.equals(wire,newWire(candidate,false))&&Arrays.equals(wire,store.exportState())&&Arrays.equals(before,store.snapshot()),"wire_input_output_and_candidate_owned");
            }
            // Old software must reject the new version, never silently omit origins.
            boolean rejected=false;try(SQLiteDatabase ignored=AppDatabase.strictSchema2Candidate(wire)){}
            catch(IllegalArgumentException e){rejected=true;}
            need(rejected&&Arrays.equals(before,store.snapshot()),"wire_old_decoder_refuses_new_format");
        }
        wireRejected(null,null);wireRejected(new byte[0],null);wireRejected(new byte[8*1024*1024+1],null);
        wireRejected(Arrays.copyOf(wire,wire.length-1),null);
        wireRejected(Arrays.copyOf(wire,wire.length+1),"Trailing schema3 state bytes");
        for(int offset:new int[]{0,7,11,15,20}){
            byte[] bad=wire.clone();bad[offset]=(byte)0xff;wireRejected(bad,null);
        }
        // Frozen media-only fixture has no batch payload. Use the old suite's
        // independently asserted nonempty-all-table backup for typed BLOB controls.
        try(SQLiteDatabase full=Schema3Store.stateCandidate(Files.readAllBytes(root.resolve("restore-expected.bin")))){
            wireBoundaryChecks(newWire(full,false));
        }
        need(true,"wire_rejects_invalid_header_lengths_utf8_and_trailing");
        try(SQLiteDatabase candidate=Schema3Store.stateCandidate(wire)){
            String[] faults={"UPDATE categories SET name=' 未规范 '",
                "UPDATE blocks SET caption='hidden' WHERE kind='TEXT'",
                "UPDATE blocks SET position=9 WHERE note_id='second' AND id='text'",
                "UPDATE fields SET type='NUMBER' WHERE id='old-field'"};
            for(String sql:faults){
                candidate.beginTransaction();byte[] bad;
                try{candidate.execSQL(sql);bad=newWire(candidate,false);}finally{candidate.endTransaction();}
                if(Arrays.equals(bad,wire))throw new AssertionError("wire poison fixture unchanged");
                wireRejected(bad,"备份状态校验失败");
            }
            candidate.execSQL("INSERT INTO categories VALUES(8,'合法新增分类',1)");
            byte[] canonical=newWire(candidate,false),reversed=newWire(candidate,true);
            if(Arrays.equals(canonical,reversed))throw new AssertionError("noncanonical fixture unchanged");
            try(SQLiteDatabase accepted=Schema3Store.stateCandidate(canonical)){
                if(!Arrays.equals(canonical,newWire(accepted,false)))throw new AssertionError("canonical control changed");
            }
            wireRejected(reversed,"Schema3 canonical readback differs");
        }
        need(true,"wire_rejects_semantic_poison_and_noncanonical_order");
        try(SQLiteDatabase candidate=Schema3Store.stateCandidate(wire)){
            candidate.setForeignKeyConstraintsEnabled(false);
            candidate.execSQL("UPDATE blocks SET original_asset_id=? WHERE note_id='second' AND id='photo'",new Object[]{"f".repeat(64)});
            wireRejected(newWire(candidate,false),null);
        }
        try(SQLiteDatabase candidate=Schema3Store.stateCandidate(wire)){
            candidate.execSQL("PRAGMA ignore_check_constraints=ON");
            String original;
            try(Cursor row=candidate.rawQuery("SELECT id FROM media ORDER BY id LIMIT 1",null)){if(!row.moveToFirst())throw new AssertionError("missing media fixture");original=row.getString(0);}
            candidate.execSQL("UPDATE blocks SET original_asset_id=? WHERE kind='TEXT'",new Object[]{original});
            wireRejected(newWire(candidate,false),null);
        }
        try(SQLiteDatabase candidate=Schema3Store.stateCandidate(wire)){
            // Same current digest may legitimately have different per-block origins.
            candidate.execSQL("UPDATE blocks SET asset_id=(SELECT asset_id FROM blocks WHERE note_id='second' AND id='photo') WHERE note_id='first' AND id='photo'");
            byte[] shared=newWire(candidate,false);
            try(SQLiteDatabase accepted=Schema3Store.stateCandidate(shared)){
                if(!Arrays.equals(shared,newWire(accepted,false)))throw new AssertionError("shared digest origin pairs changed");
            }
        }
        need(true,"wire_origin_constraints_without_global_digest_owner");
        Files.write(root.resolve("schema3-wire.bin"),wire);
    }
    /** Independent historical wire encoder. Reverse INTEGER-PK category rows only
     * for a semantically valid but noncanonical transport negative control.
     */
    private byte[] legacyWire(SQLiteDatabase db,boolean reverseCategories)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(0x50544442);out.writeInt(1);out.writeInt(2);out.writeInt(TABLES.length);
        for(String table:TABLES){
            String order=reverseCategories&&table.equals("categories")?" DESC":"";
            try(Cursor c=db.rawQuery("SELECT * FROM "+table+" ORDER BY rowid"+order,null)){
                text(out,table);out.writeInt(c.getColumnCount());for(String name:c.getColumnNames())text(out,name);out.writeInt(c.getCount());
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){
                    int type=c.getType(i);out.writeByte(type);
                    if(type==1)out.writeLong(c.getLong(i));else if(type==3)text(out,c.getString(i));
                    else if(type==4){byte[] b=c.getBlob(i);out.writeInt(b.length);out.write(b);}
                    else if(type!=0)throw new AssertionError("unexpected legacy wire type");
                }
            }
        }out.flush();return bytes.toByteArray();
    }
    /** Probe the existing private strict decoder without widening the product API.
     * This is a pre-integration gate, NOT a production schema3 restore adapter.
     */
    private SQLiteDatabase legacyCandidate(byte[] bytes)throws Exception{
        java.lang.reflect.Method method=AppDatabase.class.getDeclaredMethod("candidate",byte[].class);method.setAccessible(true);
        try(AppDatabase helper=new AppDatabase(getTargetContext(),"schema3-candidate-probe.db")){
            try{return (SQLiteDatabase)method.invoke(helper,(Object)bytes);}
            catch(java.lang.reflect.InvocationTargetException e){
                Throwable cause=e.getCause();if(cause instanceof Exception)throw (Exception)cause;throw e;
            }
        }
    }
    private void candidateRejected(byte[] bytes,String causeText)throws Exception{
        // Both the frozen decoder and the production normalizer must refuse the
        // same invalid input; migration cannot repair or bypass old validation.
        for(boolean normalize:new boolean[]{false,true}){
        boolean rejected=false;
        try(SQLiteDatabase ignored=normalize?Schema3Store.normalizeLegacyState(bytes):legacyCandidate(bytes)){}
        catch(IllegalArgumentException e){
            if(!"备份状态校验失败".equals(e.getMessage()))throw e;
            for(Throwable cause=e.getCause();cause!=null;cause=cause.getCause())
                if(causeText==null||String.valueOf(cause.getMessage()).contains(causeText))rejected=true;
        }
        if(!rejected)throw new AssertionError("legacy candidate rejection/cause missing: "+causeText);
        }
    }
    private void legacyCandidateSeed()throws Exception{
        Context c=getTargetContext();Path root=c.getFilesDir().toPath();
        byte[] frozen=Files.readAllBytes(root.resolve("frozen-v2-state.bin")),sourceCells;
        Path archive=root.resolve("frozen-v2.zip");byte[] archiveBefore=Files.readAllBytes(archive);
        String id=new String(Files.readAllBytes(root.resolve("frozen-v2-media-id.txt")),java.nio.charset.StandardCharsets.US_ASCII);
        try(SQLiteDatabase source=SQLiteDatabase.openDatabase(c.getDatabasePath("frozen-v2.db").getPath(),null,SQLiteDatabase.OPEN_READONLY)){
            sourceCells=oldCells(source);
            if(!Arrays.equals(frozen,legacyWire(source,false)))throw new AssertionError("frozen transport fixture differs");
        }
        try(BackupArchive.Snapshot zip=BackupArchive.read(archive,c.getCacheDir().toPath(),1000000);
            SQLiteDatabase candidate=legacyCandidate(zip.state())){
            need(Arrays.equals(zip.state(),frozen)&&zip.assets().keySet().equals(Set.of(id))&&Arrays.equals(Files.readAllBytes(zip.assets().get(id)),new byte[]{97,98,99})&&columns(candidate)==8&&revision(candidate)==42&&Arrays.equals(sourceCells,oldCells(candidate))&&Arrays.equals(frozen,legacyWire(candidate,false)),"legacy_candidate_zip_strict_roundtrip");
        }
        byte[] owned=frozen.clone();
        try(SQLiteDatabase candidate=legacyCandidate(owned)){
            owned[0]^=1;
            need(Arrays.equals(frozen,legacyWire(candidate,false))&&!c.getDatabasePath("schema3-candidate-probe.db").exists(),"legacy_candidate_input_owned_and_no_helper_file");
        }
        candidateRejected(Arrays.copyOf(frozen,frozen.length-1),null);
        candidateRejected(Arrays.copyOf(frozen,frozen.length+1),"备份状态存在尾随数据");
        byte[] future=frozen.clone();future[11]=3;candidateRejected(future,"未知备份格式或数据库版本");
        byte[] utf=frozen.clone();utf[20]=(byte)0xff;candidateRejected(utf,null);
        need(Arrays.equals(archiveBefore,Files.readAllBytes(archive)),"legacy_candidate_rejects_invalid_transport");
        try(SQLiteDatabase source=legacyCandidate(frozen)){
            String[] faults={"UPDATE categories SET name=' 未规范名称 '",
                "UPDATE blocks SET caption='隐藏说明' WHERE kind='TEXT'",
                "UPDATE blocks SET position=9 WHERE note_id='second' AND id='text'",
                "UPDATE fields SET type='NUMBER' WHERE id='old-field'"};
            String[] causes={"名称不是有效规范文本","笔记块有非规范隐藏内容","有序数据缺失或重复",""};
            for(int i=0;i<faults.length;i++){
                byte[] bad;source.beginTransaction();
                try{source.execSQL(faults[i]);bad=legacyWire(source,false);}finally{source.endTransaction();}
                if(Arrays.equals(bad,frozen))throw new AssertionError("semantic poison fixture unchanged");
                candidateRejected(bad,causes[i]);
                if(!Arrays.equals(frozen,legacyWire(source,false)))throw new AssertionError("poison fixture rollback incomplete");
            }
        }
        need(true,"legacy_candidate_rejects_semantic_poison");
        try(SQLiteDatabase source=legacyCandidate(frozen)){
            source.execSQL("INSERT INTO categories VALUES(8,'另一个分类',1)");
            byte[] canonical=legacyWire(source,false),noncanonical=legacyWire(source,true);
            if(Arrays.equals(canonical,noncanonical))throw new AssertionError("row order negative control unchanged");
            try(SQLiteDatabase accepted=legacyCandidate(canonical)){
                if(!Arrays.equals(canonical,legacyWire(accepted,false)))throw new AssertionError("canonical control rejected or changed");
            }
            candidateRejected(noncanonical,"备份规范回读不一致");
        }
        need(true,"legacy_candidate_rejects_noncanonical_before_migration");
        // Existing migration is exercised only after the strict decoder returns.
        // No live DB replacement, new archive format or production adapter is claimed.
        try(SQLiteDatabase candidate=legacyCandidate(frozen);
            Schema3Store adapter=new Schema3Store(c,"schema3-candidate-migration-probe.db")){
            candidate.beginTransaction();
            try{
                adapter.onUpgrade(candidate,2,3);
                try(Cursor origin=candidate.rawQuery("SELECT count(*) FROM blocks WHERE original_asset_id IS NOT NULL",null)){
                    need(columns(candidate)==9&&revision(candidate)==42&&origin.moveToFirst()&&origin.getInt(0)==0&&Arrays.equals(sourceCells,oldCells(candidate))&&candidate.inTransaction(),"legacy_candidate_migration_preserves_old_cells");
                }
                // Intentionally no success marker: prove the candidate DDL is in
                // the caller transaction, without altering any on-disk helper DB.
            }finally{candidate.endTransaction();}
            if(columns(candidate)!=8||!Arrays.equals(frozen,legacyWire(candidate,false)))throw new AssertionError("candidate migration rollback failed");
        }
        byte[] input=frozen.clone();
        try(SQLiteDatabase normalized=Schema3Store.normalizeLegacyState(input)){
            input[0]^=1;
            if(normalized.getVersion()!=3||columns(normalized)!=9||normalized.inTransaction()||revision(normalized)!=42||!Arrays.equals(sourceCells,oldCells(normalized)))throw new AssertionError("production normalized candidate changed old state/version/ownership");
            try(Cursor origin=normalized.rawQuery("SELECT count(*) FROM blocks WHERE original_asset_id IS NOT NULL",null)){
                if(!origin.moveToFirst()||origin.getInt(0)!=0)throw new AssertionError("legacy normalization invented origins");
            }
            // Returned in-memory DB is independently owned, usable and closeable.
            // Mutating one candidate must not mutate its source or a later one.
            normalized.execSQL("UPDATE todos SET title='仅候选变更' WHERE id='old-todo'");
            if(Arrays.equals(sourceCells,oldCells(normalized)))throw new AssertionError("candidate mutation control did not change rows");
        }
        try(SQLiteDatabase again=Schema3Store.normalizeLegacyState(frozen)){
            if(again.getVersion()!=3||!Arrays.equals(sourceCells,oldCells(again)))throw new AssertionError("normalization retained prior candidate mutation");
        }
        for(byte[] invalid:new byte[][]{null,new byte[0],new byte[8*1024*1024+1]}){
            boolean rejected=false;try(SQLiteDatabase ignored=Schema3Store.normalizeLegacyState(invalid)){}
            catch(IllegalArgumentException e){rejected="Missing or oversized legacy state".equals(e.getMessage());}
            if(!rejected)throw new AssertionError("normalizer input budget guard missing");
        }
        try(SQLiteDatabase source=SQLiteDatabase.openDatabase(c.getDatabasePath("frozen-v2.db").getPath(),null,SQLiteDatabase.OPEN_READONLY);
            SQLiteDatabase again=legacyCandidate(frozen)){
            need(source.getVersion()==2&&columns(source)==8&&Arrays.equals(sourceCells,oldCells(source))&&Arrays.equals(frozen,legacyWire(again,false))&&Arrays.equals(archiveBefore,Files.readAllBytes(archive))&&!c.getDatabasePath("schema3-candidate-migration-probe.db").exists(),"legacy_candidate_rejections_and_migration_leave_source_unchanged");
        }
    }
    private String schema(SQLiteDatabase db){
        StringBuilder out=new StringBuilder();
        try(Cursor c=db.rawQuery("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name",null)){
            while(c.moveToNext())out.append(c.getString(0)).append('\t').append(c.getString(1)).append('\t').append(c.getString(2)).append('\n');
        }return out.toString();
    }
    private void createFrozenV1(SQLiteDatabase db)throws Exception{
        java.lang.reflect.Field ddl=V12DeviceTest.class.getDeclaredField("V1_DDL");ddl.setAccessible(true);
        for(String sql:((String[])ddl.get(null)).clone())db.execSQL(sql);
        db.execSQL("INSERT INTO revision VALUES(1,42)");
        db.execSQL("INSERT INTO categories VALUES(7,'历史分类',0)");
        db.execSQL("INSERT INTO activities VALUES(9,7,NULL,'历史活动',0)");
        db.execSQL("INSERT INTO paths VALUES(9,0,'首页')");
        db.execSQL("INSERT INTO tags VALUES(9,0,'历史')");
        db.execSQL("INSERT INTO checkins VALUES(9,'2026-09-01','DONE','补记','2026-09-21T12:00:00Z')");
        db.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',3)",new Object[]{"1".repeat(64)});
        db.execSQL("INSERT INTO notes VALUES('old',9,'旧笔记')");
        db.execSQL("INSERT INTO blocks VALUES('old','photo',0,'IMAGE','',?,'历史图片',1)",new Object[]{"1".repeat(64)});
        db.execSQL("INSERT INTO blocks VALUES('old','text',1,'TEXT','旧文字',NULL,'',1)");
        db.setVersion(1);
    }
    private void lifecycleSeed()throws Exception{
        Context c=getTargetContext();Path root=c.getFilesDir().toPath();
        String a="1".repeat(64),b="2".repeat(64);
        c.deleteDatabase("schema3-new.db");
        try(Schema3Store store=new Schema3Store(c,"schema3-new.db")){
            SQLiteDatabase db=store.getWritableDatabase();boolean empty=true;
            for(String table:TABLES)try(Cursor rows=db.rawQuery("SELECT count(*) FROM "+table,null)){
                if(!rows.moveToFirst()||rows.getLong(0)!=(table.equals("revision")?1:0))empty=false;
            }
            need(empty&&db.getVersion()==3&&columns(db)==9&&revision(db)==0&&!c.getDatabasePath("schema3-ddl-adapter.db").exists(),"fresh_schema3_empty_layout");
            db.execSQL("INSERT INTO categories VALUES(7,'新分类',0)");
            db.execSQL("INSERT INTO activities VALUES(9,7,NULL,'新活动',0)");
            db.execSQL("INSERT INTO notes VALUES('fresh',9,'新笔记')");
            db.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',3)",new Object[]{a});
            db.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',4)",new Object[]{b});
            db.execSQL("INSERT INTO blocks VALUES('fresh','photo',0,'IMAGE','',?,'原图',0,NULL)",new Object[]{a});
            store.saveImageEdit(store.imageEdit("fresh","photo").withDerivative(b).withMetadata("新库派生",true),store.snapshot());
            NoteDocument.ImageEdit edit=store.imageEdit("fresh","photo");
            need(edit.revision().assetId.equals(b)&&edit.revision().originalAssetId.equals(a)&&edit.privateContent&&edit.caption.equals("新库派生")&&revision(db)==1,"fresh_schema3_reference_write");
            Files.write(root.resolve("schema3-new-expected.bin"),store.snapshot());
        }
        String[] v1=Arrays.copyOf(TABLES,12);byte[] before;
        c.deleteDatabase("schema3-v1.db");
        try(SQLiteDatabase db=c.openOrCreateDatabase("schema3-v1.db",0,null)){
            db.setForeignKeyConstraintsEnabled(true);createFrozenV1(db);before=oldCells(db,v1);
            try(Cursor count=db.rawQuery("SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('fields','todos','legacy_imports')",null)){
                need(count.moveToFirst()&&count.getInt(0)==0&&db.getVersion()==1&&columns(db)==8&&revision(db)==42,"frozen_v1_input");
            }
        }
        try(Schema3Store store=new Schema3Store(c,"schema3-v1.db")){
            SQLiteDatabase db=store.getWritableDatabase();
            need(db.getVersion()==3&&columns(db)==9&&revision(db)==42&&Arrays.equals(before,oldCells(db,v1)),"v1_to_3_preserves_old_cells");
            db.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',4)",new Object[]{b});
            store.saveImageEdit(store.imageEdit("old","photo").withDerivative(b),store.snapshot());
            NoteDocument.ImageEdit edit=store.imageEdit("old","photo");
            need(edit.revision().assetId.equals(b)&&edit.revision().originalAssetId.equals(a)&&edit.privateContent&&edit.caption.equals("历史图片")&&revision(db)==43,"v1_to_3_reference_write");
            Files.write(root.resolve("schema3-v1-expected.bin"),store.snapshot());
        }
        // Collision is encountered only AFTER the 1->2 callback creates six tables.
        c.deleteDatabase("schema3-v1-conflict.db");String layout;byte[] cells;
        try(SQLiteDatabase db=c.openOrCreateDatabase("schema3-v1-conflict.db",0,null)){
            createFrozenV1(db);db.execSQL("ALTER TABLE blocks ADD COLUMN original_asset_id TEXT");
            layout=schema(db);cells=oldCells(db,v1);
        }
        boolean rejected=false;try(Schema3Store store=new Schema3Store(c,"schema3-v1-conflict.db")){store.getWritableDatabase();}catch(IllegalArgumentException e){rejected="Historical block layout mismatch".equals(e.getMessage());}
        try(SQLiteDatabase db=c.openOrCreateDatabase("schema3-v1-conflict.db",0,null)){
            need(rejected&&db.getVersion()==1&&schema(db).equals(layout)&&Arrays.equals(cells,oldCells(db,v1)),"v1_late_conflict_rolls_back_all_ddl");
        }
        c.deleteDatabase("schema3-future.db");
        try(SQLiteDatabase db=c.openOrCreateDatabase("schema3-future.db",0,null)){
            db.execSQL("CREATE TABLE sentinel(value TEXT)");db.execSQL("INSERT INTO sentinel VALUES('keep')");db.setVersion(99);layout=schema(db);
        }
        rejected=false;try(Schema3Store store=new Schema3Store(c,"schema3-future.db")){store.getWritableDatabase();}catch(IllegalStateException e){rejected="Newer database; preserve data".equals(e.getMessage());}
        try(SQLiteDatabase db=c.openOrCreateDatabase("schema3-future.db",0,null);Cursor value=db.rawQuery("SELECT value FROM sentinel",null)){
            need(rejected&&db.getVersion()==99&&schema(db).equals(layout)&&value.moveToFirst()&&value.getString(0).equals("keep")&&!value.moveToNext(),"future_schema_refused_without_damage");
        }
    }
    private void ordinaryNoteSeed()throws Exception{
        Context c=getTargetContext();Path root=c.getFilesDir().toPath();
        String a="1".repeat(64),b="2".repeat(64);
        try(Schema3Store store=new Schema3Store(c,"schema3-new.db")){
            SQLiteDatabase db=store.getWritableDatabase();
            db.execSQL("INSERT INTO notes VALUES('sibling',9,'新笔记')");
            db.execSQL("INSERT INTO blocks VALUES('sibling','photo',0,'IMAGE','',?,'兄弟说明',0,?)",new Object[]{b,a});
            List<NoteDocument.Block> shown=store.noteBlocks("fresh");
            boolean immutable=false;try{shown.clear();}catch(UnsupportedOperationException e){immutable=true;}
            refused(()->store.noteBlocks("missing"));
            need(immutable&&shown.size()==1&&shown.get(0).id.equals("photo")&&shown.get(0).assetId.equals(b)&&shown.get(0).privateContent,"ordinary_note_read_owned_projection");
            long rev=revision(db);
            List<NoteDocument.Block> edited=List.of(NoteDocument.Block.text("intro","编辑后的文字",true),NoteDocument.Block.image("photo",b,"普通编辑说明",false),NoteDocument.Block.image("added",a,"新增图片",true));
            store.saveNote("fresh",edited,store.snapshot());
            NoteDocument.ImageEdit main=store.imageEdit("fresh","photo"),added=store.imageEdit("fresh","added");
            List<NoteDocument.Block> after=store.noteBlocks("fresh");
            try(Cursor raw=db.rawQuery("SELECT original_asset_id FROM blocks WHERE note_id='fresh' AND id='added'",null)){
                if(!raw.moveToFirst()||!raw.isNull(0))throw new AssertionError("new image must retain raw NULL origin");
            }
            need(main.revision().assetId.equals(b)&&main.revision().originalAssetId.equals(a)&&!main.privateContent&&main.caption.equals("普通编辑说明")&&added.revision().originalAssetId.equals(a)&&after.size()==3&&after.get(0).text.equals("编辑后的文字")&&after.get(0).privateContent&&after.get(1).id.equals("photo")&&revision(db)==rev+1,"ordinary_metadata_order_and_origin_preserved");
            NoteDocument.ImageEdit sibling=store.imageEdit("sibling","photo");
            need(sibling.caption.equals("兄弟说明")&&!sibling.privateContent&&sibling.revision().assetId.equals(b)&&sibling.revision().originalAssetId.equals(a),"ordinary_save_sibling_isolated");
            byte[] exact=store.snapshot();
            refused(()->store.saveNote("fresh",List.of(NoteDocument.Block.image("photo",a,"wrong",false)),exact));
            refused(()->store.saveNote("fresh",List.of(NoteDocument.Block.text("photo","wrong kind",false)),exact));
            refused(()->store.saveNote("fresh",List.of(NoteDocument.Block.image("intro",a,"wrong kind",false)),exact));
            refused(()->store.saveNote("fresh",List.of(edited.get(0),edited.get(0)),exact));
            refused(()->store.saveNote("missing",List.of(),exact));
            need(Arrays.equals(exact,store.snapshot()),"ordinary_replacement_kind_duplicate_and_missing_refused");
            refused(()->store.saveNote("fresh",List.of(NoteDocument.Block.text("one","先写入",false),NoteDocument.Block.image("unregistered","f".repeat(64),"不得保留",false)),exact));
            need(Arrays.equals(exact,store.snapshot()),"ordinary_late_missing_media_rolls_back");
            db.execSQL("INSERT INTO todos VALUES('external','相同修订的外部写入',0,0)");
            byte[] external=store.snapshot();
            refused(()->store.saveNote("fresh",edited,exact));
            need(revision(db)==rev+1&&Arrays.equals(external,store.snapshot()),"ordinary_same_revision_stale_rejected");
            db.execSQL("CREATE TEMP TRIGGER ordinary_fault BEFORE INSERT ON blocks WHEN NEW.note_id='fresh' AND NEW.id='photo' BEGIN SELECT RAISE(ABORT,'ordinary_note_late_fault'); END");
            boolean fault=false;try{store.saveNote("fresh",edited,external);}catch(Exception e){for(Throwable x=e;x!=null;x=x.getCause())if(String.valueOf(x.getMessage()).contains("ordinary_note_late_fault"))fault=true;}
            need(fault&&Arrays.equals(external,store.snapshot()),"ordinary_late_sql_fault_rolls_back");
            db.execSQL("DROP TRIGGER ordinary_fault");
            db.execSQL("INSERT INTO notes VALUES('remove',9,'只移除引用')");
            db.execSQL("INSERT INTO blocks VALUES('remove','photo',0,'IMAGE','',?,'',0,?)",new Object[]{b,a});
            store.saveNote("remove",List.of(),store.snapshot());
            try(Cursor media=db.rawQuery("SELECT count(*) FROM media",null)){
                need(store.noteBlocks("remove").isEmpty()&&media.moveToFirst()&&media.getInt(0)==2&&store.imageEdit("sibling","photo").revision().originalAssetId.equals(a)&&store.imageEdit("fresh","photo").revision().originalAssetId.equals(a),"ordinary_remove_keeps_shared_registry");
            }
            Files.write(root.resolve("schema3-new-expected.bin"),store.snapshot());
        }
    }
    private void postWriteBudgetSeed()throws Exception{
        Context c=getTargetContext();Path root=c.getFilesDir().toPath();
        c.deleteDatabase("schema3-write-budget.db");
        try(Schema3Store store=new Schema3Store(c,"schema3-write-budget.db")){
            SQLiteDatabase db=store.getWritableDatabase();String asset="3".repeat(64),payload="x".repeat(256*1024);
            List<NoteDocument.Block> near=new ArrayList<>(),over=new ArrayList<>();
            for(int i=0;i<33;i++){NoteDocument.Block block=NoteDocument.Block.text("text-"+i,payload,false);over.add(block);if(i<30)near.add(block);}
            db.beginTransaction();
            try{
                db.execSQL("INSERT INTO categories VALUES(1,'预算分类',0)");
                db.execSQL("INSERT INTO activities VALUES(1,1,NULL,'预算活动',0)");
                db.execSQL("INSERT INTO notes VALUES('text',1,'接近预算')");
                db.execSQL("INSERT INTO notes VALUES('image',1,'图片说明')");
                db.execSQL("INSERT INTO media VALUES(?,'application/octet-stream',3)",new Object[]{asset});
                db.execSQL("INSERT INTO blocks VALUES('image','photo',0,'IMAGE','',?,'原说明',1,NULL)",new Object[]{asset});
                for(int i=0;i<30;i++)db.execSQL("INSERT INTO blocks VALUES('text',?,?,'TEXT',?,NULL,'',0,NULL)",new Object[]{"text-"+i,i,payload});
                db.setTransactionSuccessful();
            }finally{db.endTransaction();}
            byte[] before=store.snapshot();long rev=revision(db);
            if(db.inTransaction()||before.length<=7*1024*1024||before.length>=8*1024*1024)throw new AssertionError("committed near-limit fixture invalid");
            boolean rejected=false;
            try{store.saveNote("text",over,before);}catch(IllegalArgumentException e){rejected="Comparison snapshot exceeds budget".equals(e.getMessage());}
            need(rejected&&!db.inTransaction()&&revision(db)==rev&&Arrays.equals(before,store.snapshot()),"ordinary_postwrite_budget_rolls_back");
            NoteDocument.ImageEdit image=store.imageEdit("image","photo");rejected=false;
            try{store.saveImageEdit(image.withMetadata("c".repeat(768*1024),false),before);}catch(IllegalArgumentException e){rejected="Comparison snapshot exceeds budget".equals(e.getMessage());}
            need(rejected&&!db.inTransaction()&&revision(db)==rev&&Arrays.equals(before,store.snapshot()),"image_postwrite_budget_rolls_back");
            near.set(0,NoteDocument.Block.text("text-0","小编辑",true));
            store.saveNote("text",near,before);
            store.saveImageEdit(image.withMetadata("预算内说明",false),store.snapshot());
            NoteDocument.ImageEdit saved=store.imageEdit("image","photo");
            need(revision(db)==rev+2&&store.noteBlocks("text").get(0).text.equals("小编辑")&&store.noteBlocks("text").get(0).privateContent&&saved.caption.equals("预算内说明")&&!saved.privateContent&&saved.revision().originalAssetId.equals(asset)&&store.snapshot().length<8*1024*1024,"postwrite_budget_small_edits_usable");
            Files.write(root.resolve("schema3-write-budget-expected.bin"),store.snapshot());
        }
    }
    private void budgetChecks(Schema3Store store)throws Exception{
        Schema3Store.ComparisonBuffer buffer=new Schema3Store.ComparisonBuffer(5);
        buffer.write(new byte[]{1,2,3},0,3);
        byte[] prefix=buffer.toByteArray();
        refused(()->buffer.write(new byte[]{4,5,6},0,3));
        if(!Arrays.equals(prefix,buffer.toByteArray()))throw new AssertionError("partial rejected write");
        buffer.write(4);buffer.write(5);
        refused(()->buffer.write(6));
        Schema3Store.ComparisonBuffer growth=new Schema3Store.ComparisonBuffer(1500);
        byte[] expected=new byte[1500];for(int i=0;i<expected.length;i++)expected[i]=(byte)i;
        growth.write(expected,0,1023);
        refused(()->growth.write(new byte[478],0,478));
        if(growth.size()!=1023)throw new AssertionError("rejected expansion wrote partial bytes");
        growth.write(expected,1023,477);
        need(Arrays.equals(buffer.toByteArray(),new byte[]{1,2,3,4,5})&&buffer.capacity()==5&&growth.capacity()==1500&&Arrays.equals(expected,growth.toByteArray()),"comparison_buffer_exact_limit_and_atomic_rejection");
        SQLiteDatabase db=store.getWritableDatabase();
        byte[] before=store.snapshot();long rev=revision(db);
        NoteDocument.ImageEdit edit=store.imageEdit("second","photo");
        boolean snapshotRejected=false,saveRejected=false;
        db.beginTransaction();
        try{
            String payload="x".repeat(256*1024);
            for(int i=0;i<40;i++)db.execSQL("INSERT INTO blocks(note_id,id,position,kind,text,asset_id,caption,private,original_asset_id) VALUES('first',?,?,'TEXT',?,NULL,'',0,NULL)",new Object[]{"budget-"+i,1000+i,payload});
            try(Cursor count=db.rawQuery("SELECT count(*),sum(length(text)) FROM blocks WHERE id LIKE 'budget-%'",null)){
                if(!count.moveToFirst()||count.getInt(0)!=40||count.getLong(1)!=10485760L)throw new AssertionError("oversize fixture not established");
            }
            try{store.snapshot();}catch(IllegalArgumentException e){snapshotRejected="Comparison snapshot exceeds budget".equals(e.getMessage());}
            need(snapshotRejected,"oversize_comparison_snapshot_rejected");
            try{store.saveImageEdit(edit.withMetadata("must not persist",true),before);}catch(IllegalArgumentException e){saveRejected="Comparison snapshot exceeds budget".equals(e.getMessage());}
            if(revision(db)!=rev||!store.imageEdit("second","photo").caption.equals(edit.caption))throw new AssertionError("oversize save modified target or revision");
        }finally{db.endTransaction();} // Intentionally roll back only this test fixture.
        need(saveRejected&&Arrays.equals(before,store.snapshot()),"oversize_save_and_fixture_rollback_preserve_state");
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
        try(Schema3Store store=new Schema3Store(c,"schema3-new.db")){
            need(store.getReadableDatabase().getVersion()==3&&Arrays.equals(Files.readAllBytes(root.resolve("schema3-new-expected.bin")),store.snapshot()),"fresh_schema3_separate_process_exact");
            List<NoteDocument.Block> blocks=store.noteBlocks("fresh");NoteDocument.ImageEdit edit=store.imageEdit("fresh","photo");
            need(blocks.size()==3&&blocks.get(0).id.equals("intro")&&blocks.get(0).text.equals("编辑后的文字")&&blocks.get(0).privateContent&&blocks.get(1).id.equals("photo")&&!edit.privateContent&&edit.caption.equals("普通编辑说明")&&edit.revision().assetId.equals("2".repeat(64))&&edit.revision().originalAssetId.equals("1".repeat(64)),"ordinary_note_separate_process_origin_and_order");
        }
        try(Schema3Store store=new Schema3Store(c,"schema3-v1.db")){
            need(store.getReadableDatabase().getVersion()==3&&Arrays.equals(Files.readAllBytes(root.resolve("schema3-v1-expected.bin")),store.snapshot()),"v1_to_3_separate_process_exact");
        }
        try(Schema3Store store=new Schema3Store(c,"schema3-write-budget.db")){
            need(Arrays.equals(Files.readAllBytes(root.resolve("schema3-write-budget-expected.bin")),store.snapshot())&&store.imageEdit("image","photo").caption.equals("预算内说明")&&store.noteBlocks("text").get(0).text.equals("小编辑"),"postwrite_budget_separate_process_exact");
        }
        byte[] wire=Files.readAllBytes(root.resolve("schema3-wire.bin"));
        try(SQLiteDatabase candidate=Schema3Store.stateCandidate(wire)){
            need(candidate.getVersion()==3&&columns(candidate)==9&&Arrays.equals(wire,newWire(candidate,false)),"wire_separate_process_exact_candidate");
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
