package com.supercubegame.pockettodo;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Opt-in migration and registered-reference storage. NOT the default UI database.
 * Supports new databases, schema1/2 migration and strict state wire candidates.
 * ZIP export and validated archive candidates, but no guarded live restore/UI activation.
 * Keep AppDatabase's old format frozen until compatible backup adapters are ready.
 */
public final class Schema3Store extends SQLiteOpenHelper {
    private static final int COMPARISON_LIMIT=8*1024*1024;
    /** Bounds encoded output growth, not CursorWindow, cell copies or total heap. */
    static final class ComparisonBuffer extends ByteArrayOutputStream {
        private final int limit;
        ComparisonBuffer(int limit){
            super(Math.min(1024,checkedLimit(limit)));this.limit=limit;
        }
        private static int checkedLimit(int limit){
            require(limit>0&&limit<=COMPARISON_LIMIT,"Invalid comparison buffer limit");return limit;
        }
        private void reserve(int length){
            require(length>=0&&length<=limit-count,"Comparison snapshot exceeds budget");
            int required=count+length;
            if(required>buf.length)buf=Arrays.copyOf(buf,Math.min(limit,Math.max(required,buf.length*2)));
        }
        @Override public synchronized void write(int value){reserve(1);buf[count++]=(byte)value;}
        @Override public synchronized void write(byte[] bytes,int offset,int length){
            Objects.requireNonNull(bytes);
            if(offset<0||length<0||offset>bytes.length-length)throw new IndexOutOfBoundsException();
            reserve(length);System.arraycopy(bytes,offset,buf,count,length);count+=length;
        }
        synchronized int capacity(){return buf.length;}
    }
    private static final String[] TABLES={"revision","categories","applications","activities","paths","tags","batches","ledger","checkins","media","notes","blocks","fields","field_options","field_values","field_notes","todos","legacy_imports"};
    private static final String[] OLD_BLOCKS={"note_id","id","position","kind","text","asset_id","caption","private"};
    public Schema3Store(Context context,String name){
        super(context.getApplicationContext(),name(name),null,3);setWriteAheadLoggingEnabled(true);
    }
    private static String name(String value){
        if(value==null||!value.matches("[A-Za-z0-9_-]+\\.db"))throw new IllegalArgumentException("Invalid database name");
        return value;
    }
    private static void require(boolean value,String message){if(!value)throw new IllegalArgumentException(message);}
    @Override public void onConfigure(SQLiteDatabase db){db.setForeignKeyConstraintsEnabled(true);}
    @Override public void onCreate(SQLiteDatabase db){
        // Explicit frozen factory, never a live helper callback. The outer helper
        // owns the same connection and the complete DDL/version transaction.
        AppDatabase.createSchema2(db);
        addOrigin(db);
    }
    @Override public void onUpgrade(SQLiteDatabase db,int from,int to){
        if((from!=1&&from!=2)||to!=3)throw new IllegalStateException("Unsupported migration; preserve database");
        if(from==1)AppDatabase.migrateSchema1To2(db);
        addOrigin(db);
    }
    private static void addOrigin(SQLiteDatabase db){
        try(Cursor c=db.rawQuery("SELECT * FROM blocks LIMIT 0",null)){
            require(Arrays.equals(c.getColumnNames(),OLD_BLOCKS),"Historical block layout mismatch");
        }
        tableSet(db);
        // SQLiteOpenHelper owns the DDL/version transaction. Conflicts must fail.
        db.execSQL("ALTER TABLE blocks ADD COLUMN original_asset_id TEXT REFERENCES media(id) CHECK(kind='IMAGE' OR original_asset_id IS NULL)");
        validate(db);
    }
    @Override public void onDowngrade(SQLiteDatabase db,int from,int to){throw new IllegalStateException("Newer database; preserve data");}
    /** Strict old-state normalization only, NOT a ZIP restore or new wire codec.
     * Frozen decoding, full historical semantics and old canonical byte equality
     * must all succeed BEFORE migration. The returned in-memory DB is owned by
     * the caller and must be closed; no live database/media is opened or replaced.
     * Input must not be concurrently mutated while its defensive copy is made.
     */
    static SQLiteDatabase normalizeLegacyState(byte[] bytes){
        require(bytes!=null&&bytes.length>0&&bytes.length<=COMPARISON_LIMIT,"Missing or oversized legacy state");
        SQLiteDatabase stage=AppDatabase.strictSchema2Candidate(bytes.clone());
        boolean success=false;
        try{
            stage.beginTransaction();
            try{
                addOrigin(stage);
                stage.setVersion(3);
                snapshot(stage); // New column metadata must also fit the comparison budget.
                stage.setTransactionSuccessful();
            }finally{stage.endTransaction();}
            success=true;return stage;
        }finally{if(!success)stage.close();}
    }
    private static void tableSet(SQLiteDatabase db){
        Set<String> actual=new HashSet<>();
        try(Cursor c=db.rawQuery("SELECT name FROM sqlite_master WHERE type='table'",null)){
            while(c.moveToNext()){String n=c.getString(0);if(!n.equals("android_metadata")&&!n.startsWith("sqlite_"))actual.add(n);}
        }
        require(actual.equals(new HashSet<>(Arrays.asList(TABLES))),"Unknown or missing table");
    }
    /** Formal state wire: PTDB, wire2, schema3, all 18 tables and nine block cells.
     * Not the internal comparison format. A legacy projection is used ONLY for
     * frozen full-domain validation, never returned or substituted for new data.
     * Encoding uses explicit declared names to avoid stale SELECT-star metadata.
     */
    private static byte[] wireState(SQLiteDatabase db,boolean legacy)throws IOException{
        tableSet(db);
        ComparisonBuffer buffer=new ComparisonBuffer(COMPARISON_LIMIT);
        DataOutputStream out=new DataOutputStream(buffer);
        out.writeInt(0x50544442);out.writeInt(legacy?1:2);out.writeInt(legacy?2:3);out.writeInt(TABLES.length);
        for(String table:TABLES){
            List<String> names=new ArrayList<>();
            try(Cursor info=db.rawQuery("PRAGMA table_info("+table+")",null)){while(info.moveToNext())names.add(info.getString(1));}
            if(table.equals("blocks")){
                List<String> expected=new ArrayList<>(Arrays.asList(OLD_BLOCKS));expected.add("original_asset_id");
                require(names.equals(expected),"Schema3 block layout differs");
                if(legacy)names=new ArrayList<>(Arrays.asList(OLD_BLOCKS));
            }
            // Table/column identifiers originate from our own schema, not wire SQL.
            for(String name:names)require(name.matches("[a-z_]+"),"Unexpected schema identifier");
            try(Cursor c=db.rawQuery("SELECT "+String.join(",",names)+" FROM "+table+" ORDER BY rowid",null)){
                text(out,table);out.writeInt(names.size());for(String name:names)text(out,name);out.writeInt(c.getCount());
                while(c.moveToNext())for(int i=0;i<names.size();i++){
                    int type=c.getType(i);out.writeByte(type);
                    if(type==Cursor.FIELD_TYPE_INTEGER)out.writeLong(c.getLong(i));
                    else if(type==Cursor.FIELD_TYPE_STRING)text(out,c.getString(i));
                    else if(type==Cursor.FIELD_TYPE_BLOB)bytes(out,c.getBlob(i));
                    else require(type==Cursor.FIELD_TYPE_NULL,"Unsupported wire SQL type");
                }
            }
        }out.flush();return buffer.toByteArray();
    }
    private static byte[] readWireBlob(DataInputStream in)throws IOException{
        int size=in.readInt();
        require(size>=0&&size<=COMPARISON_LIMIT&&size<=in.available(),"Invalid wire value length");
        byte[] value=new byte[size];in.readFully(value);return value;
    }
    private static String readWireText(DataInputStream in)throws IOException{
        return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(readWireBlob(in))).toString();
    }
    private static void decodeWireRows(SQLiteDatabase db,DataInputStream in)throws IOException{
        require(in.readInt()==TABLES.length,"Incomplete schema3 table count");
        for(String table:TABLES){
            require(readWireText(in).equals(table),"Missing or reordered schema3 table");
            List<String> names=new ArrayList<>(),types=new ArrayList<>();
            try(Cursor info=db.rawQuery("PRAGMA table_info("+table+")",null)){
                while(info.moveToNext()){names.add(info.getString(1));types.add(info.getString(2));}
            }
            require(in.readInt()==names.size(),"Schema3 column count differs");
            for(String name:names)require(readWireText(in).equals(name),"Schema3 column name differs");
            int rows=in.readInt();require(rows>=0&&rows<=in.available()/Math.max(1,names.size()),"Invalid schema3 row count");
            String[] marks=new String[names.size()];Arrays.fill(marks,"?");
            String sql="INSERT INTO "+table+"("+String.join(",",names)+") VALUES("+String.join(",",marks)+")";
            for(int row=0;row<rows;row++){
                Object[] values=new Object[names.size()];
                for(int col=0;col<values.length;col++){
                    int tag=in.readUnsignedByte();String name=names.get(col),type=types.get(col);
                    if(tag==0){
                        require((table.equals("activities")&&name.equals("application_id"))||
                            (table.equals("blocks")&&(name.equals("asset_id")||name.equals("original_asset_id"))),"Forbidden wire NULL");
                    }else if(tag==1){require(type.equals("INTEGER"),"Wire integer type differs");values[col]=in.readLong();}
                    else if(tag==3){require(type.equals("TEXT"),"Wire text type differs");values[col]=readWireText(in);}
                    else if(tag==4){require(type.equals("BLOB"),"Wire blob type differs");values[col]=readWireBlob(in);}
                    else throw new IllegalArgumentException("Unknown wire cell type");
                }
                db.execSQL(sql,values);
            }
        }
        require(in.available()==0,"Trailing schema3 state bytes");
    }
    /** Caller owns/closes the independent candidate. Legacy bytes must pass their
     * exact old-format validator BEFORE migration. New bytes retain every origin,
     * pass frozen full-domain semantics plus new constraints, and round-trip exactly.
     * No live database/media/file access; this is not a guarded restore operation.
     */
    static SQLiteDatabase stateCandidate(byte[] input){
        require(input!=null&&input.length>=12&&input.length<=COMPARISON_LIMIT,"Missing or oversized wire state");
        byte[] owned=input.clone(); // No concurrent caller mutation during this copy.
        try{
            DataInputStream in=new DataInputStream(new ByteArrayInputStream(owned));
            require(in.readInt()==0x50544442,"Unknown state magic");
            int wire=in.readInt(),schema=in.readInt();
            if(wire==1&&schema==2)return normalizeLegacyState(owned);
            require(wire==2&&schema==3,"Unknown wire/schema version");
            SQLiteDatabase stage=SQLiteDatabase.create(null);boolean success=false;
            try{
                stage.setForeignKeyConstraintsEnabled(true);AppDatabase.createSchema2(stage);addOrigin(stage);
                stage.beginTransaction();
                try{
                    for(int i=TABLES.length-1;i>=0;i--)stage.delete(TABLES[i],null,null);
                    decodeWireRows(stage,in);validate(stage);
                    // Reuse ALL frozen semantics, including archived field values and
                    // batch payload correspondence. Discard only the validation copy.
                    try(SQLiteDatabase historical=AppDatabase.strictSchema2Candidate(wireState(stage,true))){}
                    require(Arrays.equals(owned,wireState(stage,false)),"Schema3 canonical readback differs");
                    stage.setVersion(3);stage.setTransactionSuccessful();
                }finally{stage.endTransaction();}
                success=true;return stage;
            }finally{if(!success)stage.close();}
        }catch(IOException|RuntimeException failure){throw new IllegalArgumentException("Schema3 state validation failed",failure);}
    }
    /** One consistent full-state export, fully checked before returning owned bytes.
     * Registered media rows are included, but this method does not verify file bytes.
     */
    public synchronized byte[] exportState(){
        SQLiteDatabase db=getWritableDatabase();db.beginTransaction();
        try{
            require(db.getVersion()==3,"Export requires schema3");
            byte[] encoded=wireState(db,false);
            try(SQLiteDatabase checked=stateCandidate(encoded)){}
            db.setTransactionSuccessful();return encoded;
        }catch(IOException failure){throw new IllegalStateException("Cannot encode schema3 state",failure);}
        finally{db.endTransaction();}
    }
    /** Every registered asset is part of a full backup, even when unreferenced.
     * The registry is read from the captured state candidate, not a later live read.
     */
    private static Map<String,Long> registeredMedia(SQLiteDatabase candidate){
        Map<String,Long> result=new LinkedHashMap<>();
        try(Cursor rows=candidate.rawQuery("SELECT id,bytes FROM media ORDER BY id",null)){
            while(rows.moveToNext()){
                String id=rows.getString(0);long size=rows.getLong(1);MediaRepository.validId(id);
                require(size>0&&result.put(id,size)==null,"Invalid registered media");
            }
        }return result;
    }
    private static void verifyRegisteredFile(String id,long expected,Path path)throws IOException{
        if(path==null||!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)||Files.isSymbolicLink(path))
            throw new IOException("Registered media missing or not regular");
        if(Files.size(path)!=expected)throw new IOException("Registered media size differs");
        java.security.MessageDigest hash=MediaRepository.sha();long actual=0;
        try(InputStream in=Files.newInputStream(path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
            byte[] buffer=new byte[16384];int n;
            while((n=in.read(buffer))!=-1){
                if(n==0)throw new IOException("Registered media read made no progress");
                if(n>expected-actual)throw new IOException("Registered media size differs");
                actual+=n;hash.update(buffer,0,n);
            }
        }
        if(actual!=expected)throw new IOException("Registered media size differs");
        if(!id.equals(MediaRepository.hex(hash.digest())))throw new IOException("Registered media digest differs");
    }
    /** Validates an already staged ZIP without writing any live DB or media.
     * Caller separately owns/closes BOTH the Snapshot and returned candidate.
     * Re-checks staged bytes, not just the transport manifest, because a caller may
     * have held/modified staging after read(). NOT an owner/session/consent token;
     * a future guarded restore must revalidate again at confirmation.
     */
    static SQLiteDatabase archiveCandidate(BackupArchive.Snapshot snapshot)throws IOException{
        require(snapshot!=null,"Missing archive snapshot");
        SQLiteDatabase candidate=stateCandidate(snapshot.state());boolean success=false;
        try{
            Map<String,Long> expected=registeredMedia(candidate);Map<String,Path> actual=snapshot.assets();
            require(expected.keySet().equals(actual.keySet()),"Archive registered asset set differs");
            for(Map.Entry<String,Long> asset:expected.entrySet())verifyRegisteredFile(asset.getKey(),asset.getValue(),actual.get(asset.getKey()));
            success=true;return candidate;
        }finally{if(!success)candidate.close();}
    }
    /** Full unencrypted backup including private text and all registered images.
     * Captures one checked state, then uses ONLY that candidate's registry. Does
     * not hold the live SQL transaction while hashing/copying files. Requires
     * immutable cooperating app-private media writers, as MediaRepository does.
     * BackupArchive refuses overwrite and verifies its temporary ZIP before publish.
     * No default UI entry or power-loss/authenticity guarantee is implied.
     */
    public synchronized void exportBackup(Path destination,MediaRepository media)throws IOException{
        require(destination!=null&&media!=null,"Missing backup destination or media");
        byte[] state=exportState();
        try(SQLiteDatabase candidate=stateCandidate(state)){
            Map<String,Long> expected=registeredMedia(candidate);
            for(Map.Entry<String,Long> asset:expected.entrySet()){
                media.verify(asset.getKey()); // Respect this repository's caller-supplied budget.
                verifyRegisteredFile(asset.getKey(),asset.getValue(),media.path(asset.getKey()));
            }
            BackupArchive.write(destination,state,expected.keySet(),media);
        }
    }
    private static long revision(SQLiteDatabase db){
        try(Cursor c=db.rawQuery("SELECT id,value FROM revision",null)){
            require(c.moveToFirst()&&c.getLong(0)==1&&c.getLong(1)>=0,"Invalid revision");
            long value=c.getLong(1);require(!c.moveToNext(),"Multiple revisions");return value;
        }
    }
    private static void validate(SQLiteDatabase db){
        tableSet(db);revision(db);
        try(Cursor c=db.rawQuery("PRAGMA foreign_key_check",null)){require(!c.moveToFirst(),"Invalid foreign key");}
        try(Cursor c=db.rawQuery("SELECT kind,asset_id,original_asset_id FROM blocks",null)){
            while(c.moveToNext()){
                if("IMAGE".equals(c.getString(0)))new NoteDocument.ImageRevision(c.getString(1),c.isNull(2)?null:c.getString(2));
                else require("TEXT".equals(c.getString(0))&&c.isNull(1)&&c.isNull(2),"Invalid text origin");
            }
        }
    }
    /** Internal comparison bytes, NOT a BackupArchive state or an import format. */
    public synchronized byte[] snapshot(){
        SQLiteDatabase db=getWritableDatabase();db.beginTransaction();
        try{byte[] bytes=snapshot(db);db.setTransactionSuccessful();return bytes;}finally{db.endTransaction();}
    }
    private static void bytes(DataOutputStream out,byte[] b)throws IOException{out.writeInt(b.length);out.write(b);}
    private static void text(DataOutputStream out,String s)throws IOException{bytes(out,s.getBytes(StandardCharsets.UTF_8));}
    private static byte[] snapshot(SQLiteDatabase db){
        validate(db);
        try{
            ComparisonBuffer buffer=new ComparisonBuffer(COMPARISON_LIMIT);DataOutputStream out=new DataOutputStream(buffer);
            out.writeInt(0x53334350);out.writeInt(3);
            for(String table:TABLES)try(Cursor c=db.rawQuery("SELECT * FROM "+table+" ORDER BY rowid",null)){
                text(out,table);out.writeInt(c.getColumnCount());for(String n:c.getColumnNames())text(out,n);out.writeInt(c.getCount());
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){
                    int type=c.getType(i);out.writeByte(type);
                    if(type==Cursor.FIELD_TYPE_INTEGER)out.writeLong(c.getLong(i));
                    else if(type==Cursor.FIELD_TYPE_STRING)text(out,c.getString(i));
                    else if(type==Cursor.FIELD_TYPE_BLOB)bytes(out,c.getBlob(i));
                    else require(type==Cursor.FIELD_TYPE_NULL,"Unsupported SQL type");
                }
            }
            out.flush();return buffer.toByteArray();
        }catch(IOException e){throw new IllegalStateException("Cannot encode comparison state",e);}
    }
    private static NoteDocument.ImageEdit imageEdit(SQLiteDatabase db,String note,String block){
        Ledger.identifier(note);Ledger.identifier(block);
        try(Cursor c=db.rawQuery("SELECT kind,asset_id,caption,private,original_asset_id FROM blocks WHERE note_id=? AND id=?",new String[]{note,block})){
            require(c.moveToFirst()&&"IMAGE".equals(c.getString(0)),"Image target not found");
            return new NoteDocument.ImageEdit(note,NoteDocument.Block.image(block,c.getString(1),c.getString(2),c.getInt(3)!=0),c.isNull(4)?null:c.getString(4));
        }
    }
    public synchronized NoteDocument.ImageEdit imageEdit(String note,String block){return imageEdit(getReadableDatabase(),note,block);}
    private static void requireNote(SQLiteDatabase db,String note){
        try(Cursor c=db.rawQuery("SELECT 1 FROM notes WHERE id=?",new String[]{note})){require(c.moveToFirst(),"Note not found");}
    }
    private static List<NoteDocument.Block> noteBlocks(SQLiteDatabase db,String note){
        requireNote(db,note);List<NoteDocument.Block> blocks=new ArrayList<>();
        try(Cursor c=db.rawQuery("SELECT id,kind,text,asset_id,caption,private FROM blocks WHERE note_id=? ORDER BY position",new String[]{note})){
            while(c.moveToNext())blocks.add("IMAGE".equals(c.getString(1))
                ?NoteDocument.Block.image(c.getString(0),c.getString(3),c.getString(4),c.getInt(5)!=0)
                :NoteDocument.Block.text(c.getString(0),c.getString(2),c.getInt(5)!=0));
        }return Collections.unmodifiableList(blocks);
    }
    /** Legacy-shaped UI projection; saveNote preserves origins from the database. */
    public synchronized List<NoteDocument.Block> noteBlocks(String note){
        Ledger.identifier(note);return noteBlocks(getReadableDatabase(),note);
    }
    /** Full-state guarded ordinary edit, not a session/single-use UI token.
     * Existing stable IDs cannot change kind or image asset through this path.
     * Preserve stored origin including NULL; new registered images start at NULL.
     * Removed blocks release references only, never delete shared media.
     */
    public synchronized void saveNote(String note,List<NoteDocument.Block> blocks,byte[] before){
        Ledger.identifier(note);
        require(blocks!=null&&!Ledger.hasNull(blocks),"Missing note blocks");
        require(before!=null&&before.length>0&&before.length<=COMPARISON_LIMIT,"Missing reviewed state");
        List<NoteDocument.Block> owned=new ArrayList<>(blocks);NoteDocument validator=new NoteDocument();
        for(NoteDocument.Block block:owned)validator.add(block);
        byte[] expected=before.clone();SQLiteDatabase db=getWritableDatabase();db.beginTransaction();
        try{
            require(Arrays.equals(expected,snapshot(db)),"Database changed; review again");requireNote(db,note);
            Map<String,String> kinds=new HashMap<>(),assets=new HashMap<>(),origins=new HashMap<>();
            try(Cursor c=db.rawQuery("SELECT id,kind,asset_id,original_asset_id FROM blocks WHERE note_id=?",new String[]{note})){
                while(c.moveToNext()){String id=c.getString(0);kinds.put(id,c.getString(1));assets.put(id,c.isNull(2)?null:c.getString(2));origins.put(id,c.isNull(3)?null:c.getString(3));}
            }
            db.delete("blocks","note_id=?",new String[]{note});
            for(int i=0;i<owned.size();i++){
                NoteDocument.Block block=owned.get(i);String origin=null;
                if(kinds.containsKey(block.id)){
                    require(kinds.get(block.id).equals(block.kind.name()),"Existing block kind cannot change");
                    if(block.kind==NoteDocument.Kind.IMAGE){
                        require(block.assetId.equals(assets.get(block.id)),"Use derivative writer to change existing image");
                        origin=origins.get(block.id);
                    }
                }
                if(block.kind==NoteDocument.Kind.IMAGE){
                    new NoteDocument.ImageRevision(block.assetId,origin);
                    try(Cursor c=db.rawQuery("SELECT bytes FROM media WHERE id=?",new String[]{block.assetId})){
                        require(c.moveToFirst()&&c.getLong(0)>0,"Unregistered image");
                    }
                }
                db.execSQL("INSERT INTO blocks(note_id,id,position,kind,text,asset_id,caption,private,original_asset_id) VALUES(?,?,?,?,?,?,?,?,?)",
                    new Object[]{note,block.id,i,block.kind.name(),block.text,block.kind==NoteDocument.Kind.IMAGE?block.assetId:null,block.caption,block.privateContent?1:0,origin});
            }
            long next=Math.incrementExact(revision(db));db.execSQL("UPDATE revision SET value=? WHERE id=1",new Object[]{next});validate(db);
            try(Cursor c=db.rawQuery("SELECT id,kind,text,asset_id,caption,private,original_asset_id,position FROM blocks WHERE note_id=? ORDER BY position",new String[]{note})){
                int position=0;
                for(NoteDocument.Block block:owned){
                    String asset=block.kind==NoteDocument.Kind.IMAGE?block.assetId:null;
                    String origin=block.kind==NoteDocument.Kind.IMAGE?origins.get(block.id):null;
                    require(c.moveToNext()&&block.id.equals(c.getString(0))&&block.kind.name().equals(c.getString(1))&&block.text.equals(c.getString(2))&&Objects.equals(asset,c.isNull(3)?null:c.getString(3))&&block.caption.equals(c.getString(4))&&(block.privateContent?1:0)==c.getInt(5)&&Objects.equals(origin,c.isNull(6)?null:c.getString(6))&&c.getInt(7)==position++,"Note write readback differs");
                }require(!c.moveToNext(),"Unexpected note rows");
            }
            // Reject an otherwise valid edit that would make future comparisons
            // impossible. Must run AFTER writes but BEFORE transaction success.
            snapshot(db);
            db.setTransactionSuccessful();
        }finally{db.endTransaction();}
    }
    /** Reference-only atomic update. Caller must verify actual immutable bytes and
     * explicit UI consent; this is not a single-use/session preview token.
     * Full-state equality catches external writes even without revision increments.
     */
    public synchronized void saveImageEdit(NoteDocument.ImageEdit edit,byte[] before){
        require(edit!=null&&before!=null&&before.length>0&&before.length<=COMPARISON_LIMIT,"Missing reviewed state");
        byte[] expected=before.clone();SQLiteDatabase db=getWritableDatabase();db.beginTransaction();
        try{
            require(Arrays.equals(expected,snapshot(db)),"Database changed; review again");
            NoteDocument.ImageEdit current=imageEdit(db,edit.noteId,edit.blockId);
            require(current.revision().originalAssetId.equals(edit.revision().originalAssetId),"Original image cannot be replaced");
            for(String id:edit.revision().backupAssets())try(Cursor c=db.rawQuery("SELECT bytes FROM media WHERE id=?",new String[]{id})){
                require(c.moveToFirst()&&c.getLong(0)>0,"Unregistered image");
            }
            db.execSQL("UPDATE blocks SET asset_id=?,original_asset_id=?,caption=?,private=? WHERE note_id=? AND id=?",
                new Object[]{edit.revision().assetId,edit.revision().originalAssetId,edit.caption,edit.privateContent?1:0,edit.noteId,edit.blockId});
            long next=Math.incrementExact(revision(db));db.execSQL("UPDATE revision SET value=? WHERE id=1",new Object[]{next});
            validate(db);
            NoteDocument.ImageEdit actual=imageEdit(db,edit.noteId,edit.blockId);
            require(actual.revision().assetId.equals(edit.revision().assetId)&&actual.revision().originalAssetId.equals(edit.revision().originalAssetId)&&actual.caption.equals(edit.caption)&&actual.privateContent==edit.privateContent,"Image write readback differs");
            snapshot(db); // Include the new caption/origin bytes in the commit budget.
            db.setTransactionSuccessful();
        }finally{db.endTransaction();}
    }
}
