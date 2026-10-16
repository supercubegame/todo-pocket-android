package com.supercubegame.pockettodo;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Opt-in storage only. Not used by AppDatabase, TodayScreen or any live UI.
 * Live migration accepts schema3 only. Historical schema2/schema3 BACKUPS are
 * normalized through the unchanged strict Schema3Store decoder first.
 * v4 transport wraps canonical schema3 bytes and sorted category/application IDs.
 * This is not UI consent, an external launcher, restore undo or power-loss proof.
 */
public final class Schema4Store extends SQLiteOpenHelper {
    private static final String[] OLD=("revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports").split(" ");
    static final String SHORTCUT_DDL="CREATE TABLE category_shortcuts(category_id INTEGER NOT NULL REFERENCES categories(id) CHECK(category_id>0),application_id INTEGER NOT NULL REFERENCES applications(id) CHECK(application_id>0),PRIMARY KEY(category_id,application_id)) WITHOUT ROWID";
    /** Single-process explicit consent, not a persistent ABA or crash journal.
     * Foreign callers cannot consume the owner's attempt. Every owner attempt,
     * including changed-state refusal, is terminal.
     */
    static final class ActivationConsent implements AutoCloseable {
        private final Object owner,session,connection;
        private byte[] cells,archive;
        private boolean terminal;
        ActivationConsent(Object owner,Object session,Object connection,byte[] cells,byte[] archive){
            if(owner==null||session==null||connection==null||cells==null||cells.length==0||
               cells.length>8*1024*1024||archive==null||archive.length!=32)
                throw new IllegalArgumentException("Invalid activation consent");
            this.owner=owner;this.session=session;this.connection=connection;
            this.cells=cells.clone();this.archive=archive.clone();
        }
        synchronized void checkOwner(Object attemptedOwner){
            if(attemptedOwner!=owner)throw new IllegalArgumentException("Foreign activation plan");
        }
        synchronized void checkActive(Object attemptedOwner,Object currentSession){
            checkOwner(attemptedOwner);
            if(terminal)throw new IllegalStateException("Activation plan expired");
            if(currentSession!=session){close();throw new IllegalStateException("Activation review changed");}
        }
        synchronized void consume(Object attemptedOwner,Object currentSession,Object currentConnection,
                                  byte[] currentCells,byte[] currentArchive){
            checkOwner(attemptedOwner);
            if(terminal)throw new IllegalStateException("Activation plan expired");
            try{
                if(currentSession!=session||currentConnection!=connection||
                   !Arrays.equals(cells,currentCells)||!Arrays.equals(archive,currentArchive))
                    throw new IllegalStateException("Activation review changed");
            }finally{close();}
        }
        @Override public synchronized void close(){terminal=true;cells=null;archive=null;}
    }
    static final class ActivationPlan implements AutoCloseable {
        final ActivationConsent consent;
        final Path archive,staging;
        final byte[] wire,cells;
        final SQLiteDatabase connection;
        private ActivationPlan(Object owner,Object session,SQLiteDatabase db,Path archive,Path staging,
                               byte[] wire,byte[] cells,byte[] digest){
            this.archive=archive;this.staging=staging;this.wire=wire.clone();this.cells=cells.clone();
            connection=db;consent=new ActivationConsent(owner,session,db,cells,digest);
        }
        @Override public void close(){consent.close();}
    }
    private static byte[] activationDigest(Path archive)throws IOException{
        if(Files.isSymbolicLink(archive)||!Files.isRegularFile(archive,LinkOption.NOFOLLOW_LINKS))
            throw new IOException("Activation backup missing");
        long size=Files.size(archive);
        if(size<=0||size>64L*1024*1024)throw new IOException("Activation backup budget");
        java.security.MessageDigest digest=MediaRepository.sha();long count=0;
        try(InputStream input=Files.newInputStream(archive,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
            byte[] buffer=new byte[16384];int n;
            while((n=input.read(buffer))!=-1){
                if(n<=0||n>size-count)throw new IOException("Activation backup read changed");
                count+=n;digest.update(buffer,0,n);
            }
        }
        if(count!=size)throw new IOException("Activation backup truncated");
        return digest.digest();
    }
    private static void activationMedia(SQLiteDatabase db,MediaRepository media)throws IOException{
        require(media!=null,"Activation media required");
        for(Map.Entry<String,Long> entry:mediaRegistry(db).entrySet())
            exactFile(entry.getKey(),entry.getValue(),media.path(entry.getKey()));
    }
    private static void activationArchive(Path archive,Path staging,byte[] expected)throws IOException{
        try(BackupArchive.Snapshot snapshot=BackupArchive.read(archive,staging,64L*1024*1024);
            SQLiteDatabase candidate=archiveCandidate(snapshot)){
            require(Arrays.equals(expected,snapshot.state()),"Activation backup state changed");
            require(links(candidate).isEmpty(),"Activation backup unexpectedly contains shortcuts");
        }
    }
    /** Creates a retained private backup, never a data replacement. The UI must
     * explain that uninstall/clear-data removes this LOCAL recovery copy.
     * Partial/failed backups are retained too; none can authorize migration.
     */
    static ActivationPlan prepareActivation(Object owner,Object session,SQLiteDatabase db,
                                            Path directory,MediaRepository media)throws IOException{
        outsideTransaction(db);
        Files.createDirectories(directory);
        require(!Files.isSymbolicLink(directory)&&Files.isDirectory(directory,LinkOption.NOFOLLOW_LINKS),
                "Activation backup directory invalid");
        Path archive=directory.resolve("before-shortcuts-"+UUID.randomUUID()+".zip");
        Path staging=directory.resolve("verify-"+UUID.randomUUID());
        db.beginTransaction();
        try{
            require(db.getVersion()==3,"Activation requires schema3");
            layout(db,false);byte[] before=businessCells(db,true),wire=baseWire(db);
            try(SQLiteDatabase checked=Schema3Store.stateCandidate(wire)){}
            activationMedia(db,media);
            BackupArchive.write(archive,wire,mediaRegistry(db).keySet(),media);
            byte[] digest=activationDigest(archive);
            activationArchive(archive,staging,wire);
            activationMedia(db,media);
            require(Arrays.equals(digest,activationDigest(archive))&&
                    Arrays.equals(before,businessCells(db,true))&&Arrays.equals(wire,baseWire(db)),
                    "Activation preparation changed");
            ActivationPlan plan=new ActivationPlan(owner,session,db,archive,staging,wire,before,digest);
            db.setTransactionSuccessful();return plan;
        }finally{db.endTransaction();}
    }
    /** DDL, version, exact readback and final archive/media checks share the
     * original schema3 write transaction. Never reconstruct or replace old rows.
     * The caller must retire the old facade after success before business writes.
     */
    static void confirmActivation(Object owner,Object session,SQLiteDatabase db,
                                  ActivationPlan plan,MediaRepository media)throws IOException{
        require(plan!=null,"Activation plan required");
        plan.consent.checkActive(owner,session);
        try{
            outsideTransaction(db);db.beginTransaction();
            try{
                require(db.getVersion()==3,"Activation requires schema3");
                layout(db,false);
                byte[] digest=activationDigest(plan.archive);
                plan.consent.consume(owner,session,db,businessCells(db,true),digest);
                require(Arrays.equals(plan.wire,baseWire(db)),"Activation source changed");
                activationArchive(plan.archive,plan.staging,plan.wire);
                activationMedia(db,media);
                db.execSQL(SHORTCUT_DDL);
                db.setVersion(4);
                require(Arrays.equals(plan.cells,businessCells(db,true))&&
                        Arrays.equals(plan.wire,baseWire(db))&&links(db).isEmpty(),
                        "Activation changed historical data");
                encodeState(db);
                activationMedia(db,media);
                require(Arrays.equals(digest,activationDigest(plan.archive)),"Activation backup changed");
                db.setTransactionSuccessful();
            }finally{db.endTransaction();}
        }finally{plan.close();}
    }

    /** Resume only: never SQLiteOpenHelper's create/upgrade path.
     * A custom corruption handler refuses instead of deleting the user's file.
     * This does not claim resistance to malicious same-UID file replacement.
     */
    private final boolean resumeOnly;
    private SQLiteDatabase resumedConnection;
    private boolean resumeClosed;
    private static String resumeName(String name){
        require(name!=null&&name.matches("[A-Za-z0-9_-]+\\.db"),"Invalid resume database name");
        return name;
    }
    static void resumeFile(Path path)throws IOException{
        if(Files.isSymbolicLink(path)||!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)||
           Files.size(path)==0)throw new IOException("Existing nonempty database required");
    }
    private Schema4Store(Context context,String name,boolean resume){
        super(context.getApplicationContext(),resumeName(name),null,4);
        if(!resume)throw new IllegalArgumentException("Resume-only constructor");
        resumeOnly=true;
    }
    static Schema4Store resumeExisting(Context context,String name){
        Schema4Store helper=new Schema4Store(context,name,true);
        try{
            Path path=context.getDatabasePath(resumeName(name)).toPath();
            resumeFile(path);
            helper.resumedConnection=SQLiteDatabase.openDatabase(path.toString(),null,
                SQLiteDatabase.OPEN_READWRITE,broken->{
                    throw new IllegalStateException("Corrupt database; preserve original file");
                });
            SQLiteDatabase db=helper.resumedConnection;
            db.setForeignKeyConstraintsEnabled(true);
            db.beginTransaction();
            try{
                if(db.getVersion()!=4)throw new IllegalStateException("Resume requires already activated schema4");
                validate(db);encodeState(db);
                db.setTransactionSuccessful();
            }finally{db.endTransaction();}
            return helper;
        }catch(IOException e){helper.close();throw new IllegalStateException("Cannot resume; database preserved",e);}
        catch(RuntimeException|Error e){helper.close();throw e;}
    }
    @Override public synchronized SQLiteDatabase getWritableDatabase(){
        if(!resumeOnly)return super.getWritableDatabase();
        if(resumeClosed||resumedConnection==null||!resumedConnection.isOpen())
            throw new IllegalStateException("Resume facade closed");
        if(resumedConnection.getVersion()!=4)
            throw new IllegalStateException("Resumed schema changed; preserve database");
        return resumedConnection;
    }
    @Override public synchronized SQLiteDatabase getReadableDatabase(){
        return resumeOnly?getWritableDatabase():super.getReadableDatabase();
    }

    private Object session=new Object();
    public Schema4Store(Context context,String name){
        super(context.getApplicationContext(),validName(name),null,4);
        resumeOnly=false;
        setWriteAheadLoggingEnabled(true);
    }
    private static String validName(String name){
        require(name!=null&&name.matches("[A-Za-z0-9_-]+\\.db"),"Invalid database name");
        // This opt-in stage must never migrate the actual application's database.
        require(!name.equals("pocket-v12.db"),"Live UI database not enabled");
        return name;
    }
    private static void require(boolean ok,String reason){if(!ok)throw new IllegalArgumentException(reason);}
    @Override public void onConfigure(SQLiteDatabase db){db.setForeignKeyConstraintsEnabled(true);}
    @Override public void onCreate(SQLiteDatabase db){
        if(resumeOnly)throw new IllegalStateException("Resume must never create");
        Schema3Store.createSchema3(db);db.execSQL(SHORTCUT_DDL);validate(db);
    }
    @Override public void onUpgrade(SQLiteDatabase db,int from,int to){
        if(resumeOnly)throw new IllegalStateException("Resume must never upgrade");
        if(from!=3||to!=4)throw new IllegalStateException("Unsupported migration; preserve database");
        layout(db,false);
        byte[] before=businessCells(db,true);
        try(SQLiteDatabase checked=Schema3Store.stateCandidate(baseWire(db))){}
        db.execSQL(SHORTCUT_DDL);
        validate(db);
        require(Arrays.equals(before,businessCells(db,true)),"Migration changed historical cells");
        encodeState(db); // Fail before helper transaction commits if wire exceeds budget.
    }
    @Override public void onDowngrade(SQLiteDatabase db,int from,int to){throw new IllegalStateException("Newer database; preserve data");}
    @Override public synchronized void close(){session=new Object();resumeClosed=true;if(resumedConnection!=null){resumedConnection.close();resumedConnection=null;}super.close();}


    /** Exact layout validator for internal business comparisons, not old decoders. */
    static void checkBusinessLayout(SQLiteDatabase db){require(db.getVersion()==4,"Business bridge requires schema4");validate(db);}
    private static byte[] bridgeSnapshot(SQLiteDatabase db){
        encodeState(db);
        try{
            Schema3Store.ComparisonBuffer bytes=new Schema3Store.ComparisonBuffer(Wire.LIMIT);
            DataOutputStream out=new DataOutputStream(bytes);out.writeInt(0x53344350);
            byte[] old=businessCells(db,true);out.writeInt(old.length);out.write(old);
            for(Link link:links(db)){out.writeLong(link.category);out.writeLong(link.application);}
            out.flush();return bytes.toByteArray();
        }catch(IOException e){throw new IllegalStateException("Cannot compare schema4 business state",e);}
    }
    synchronized byte[] relationshipState(){
        SQLiteDatabase db=getWritableDatabase();validate(db);
        try{
            Schema3Store.ComparisonBuffer bytes=new Schema3Store.ComparisonBuffer(Wire.LIMIT);
            DataOutputStream out=new DataOutputStream(bytes);
            for(Link link:links(db)){out.writeLong(link.category);out.writeLong(link.application);}
            out.flush();return bytes.toByteArray();
        }catch(IOException e){throw new IllegalStateException("Cannot compare shortcut state",e);}
    }
    Schema3Store businessAdapter(Context context,String name){
        return new Schema3Store(context,name,new Schema3Store.BusinessConnection(){
            public SQLiteDatabase database(){return Schema4Store.this.getWritableDatabase();}
            public byte[] snapshot(SQLiteDatabase db){require(db==database(),"Foreign business connection");return bridgeSnapshot(db);}
            public void validate(SQLiteDatabase db){require(db==database(),"Foreign business connection");encodeState(db);}
        });
    }

    // BEGIN_PURE_WIRE
    static final class Link {
        final long category,application;
        private static void require(boolean ok,String reason){if(!ok)throw new IllegalArgumentException(reason);}
        Link(long category,long application){
            require(category>0&&application>0,"Invalid identity");
            this.category=category;this.application=application;
        }
        @Override public boolean equals(Object other){
            return other instanceof Link&&((Link)other).category==category&&((Link)other).application==application;
        }
        @Override public int hashCode(){return Objects.hash(category,application);}
    }
    static final class Wire {
        static final int LIMIT=8*1024*1024;
        private final byte[] original;
        final List<Link> links;
        private Wire(byte[] original,List<Link> links){
            this.original=original.clone();this.links=Collections.unmodifiableList(new ArrayList<>(links));
        }
        byte[] base(){return original.clone();}
        private static void require(boolean ok,String reason){if(!ok)throw new IllegalArgumentException(reason);}
        static void baseHeader(byte[] base){
            require(base!=null&&base.length>=16,"Embedded state length");
            java.nio.ByteBuffer header=java.nio.ByteBuffer.wrap(base);
            require(header.getInt()==0x50544442&&header.getInt()==2&&header.getInt()==3&&header.getInt()==18,"Embedded schema3 header");
        }
        static Wire read(byte[] input){
            require(input!=null&&input.length>=20&&input.length<=LIMIT,"Envelope budget");
            byte[] owned=input.clone();
            try{
                DataInputStream in=new DataInputStream(new ByteArrayInputStream(owned));
                require(in.readInt()==0x50544442&&in.readInt()==3&&in.readInt()==4,"Envelope version");
                int size=in.readInt();
                require(size>=16&&size<=in.available()-4,"Embedded state length");
                byte[] base=new byte[size];in.readFully(base);baseHeader(base);
                int count=in.readInt();require(count>=0&&count<=in.available()/16,"Shortcut count");
                List<Link> links=new ArrayList<>();Link prior=null;
                for(int i=0;i<count;i++){
                    Link link=new Link(in.readLong(),in.readLong());
                    require(prior==null||prior.category<link.category||(prior.category==link.category&&prior.application<link.application),"Shortcut order");
                    links.add(link);prior=link;
                }
                require(in.available()==0,"Trailing envelope bytes");
                return new Wire(base,links);
            }catch(IOException e){throw new IllegalArgumentException("Truncated envelope",e);}
        }
        static byte[] encode(byte[] base,List<Link> links){
            baseHeader(base);require(links!=null,"Missing links");
            long size=20L+base.length+16L*links.size();require(size<=LIMIT,"Envelope budget");
            try{
                ByteArrayOutputStream b=new ByteArrayOutputStream((int)size);DataOutputStream out=new DataOutputStream(b);
                out.writeInt(0x50544442);out.writeInt(3);out.writeInt(4);out.writeInt(base.length);out.write(base);
                out.writeInt(links.size());
                for(Link link:links){require(link!=null,"Missing link");out.writeLong(link.category);out.writeLong(link.application);}
                out.flush();byte[] result=b.toByteArray();read(result);return result;
            }catch(IOException e){throw new IllegalStateException("Cannot encode envelope",e);}
        }
    }
    // END_PURE_WIRE

    /** Exact schema identity, not a permissive table whitelist. sqlite_ internal
     * tables and Android locale metadata are not business schema. Temp triggers
     * remain usable for failure injection and do not enter exported state.
     */
    private static Map<String,List<String>> schema(SQLiteDatabase db){
        Map<String,List<String>> result=new TreeMap<>();
        try(Cursor c=db.rawQuery("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name",null)){
            while(c.moveToNext()){
                String name=c.getString(1);
                if(name.equals("android_metadata")||name.startsWith("sqlite_"))continue;
                require(result.put(c.getString(0)+"/"+name,Arrays.asList(c.getString(2),c.getString(3)))==null,"Duplicate schema object");
            }
        }return result;
    }
    private static void layout(SQLiteDatabase db,boolean shortcuts){
        try(SQLiteDatabase expected=SQLiteDatabase.create(null)){
            expected.setForeignKeyConstraintsEnabled(true);Schema3Store.createSchema3(expected);
            if(shortcuts)expected.execSQL(SHORTCUT_DDL);
            require(schema(db).equals(schema(expected)),"Unknown or missing schema");
        }
    }
    private static long revision(SQLiteDatabase db){
        try(Cursor c=db.rawQuery("SELECT id,value FROM revision",null)){
            require(c.moveToFirst()&&c.getLong(0)==1&&c.getLong(1)>=0,"Invalid revision");
            long value=c.getLong(1);require(!c.moveToNext(),"Multiple revisions");return value;
        }
    }
    private static List<Link> links(SQLiteDatabase db){
        List<Link> result=new ArrayList<>();
        try(Cursor c=db.rawQuery("SELECT category_id,application_id FROM category_shortcuts ORDER BY category_id,application_id",null)){
            while(c.moveToNext()){
                require(c.getType(0)==Cursor.FIELD_TYPE_INTEGER&&c.getType(1)==Cursor.FIELD_TYPE_INTEGER,"Shortcut SQL type");
                result.add(new Link(c.getLong(0),c.getLong(1)));
            }
        }return result;
    }
    private static void validate(SQLiteDatabase db){
        layout(db,true);revision(db);links(db);
        try(Cursor c=db.rawQuery("PRAGMA foreign_key_check",null)){require(!c.moveToFirst(),"Invalid foreign key");}
    }
    private static void text(DataOutputStream out,String value)throws IOException{
        byte[] b=value.getBytes(java.nio.charset.StandardCharsets.UTF_8);out.writeInt(b.length);out.write(b);
    }
    private static void cell(DataOutputStream out,Cursor c,int i)throws IOException{
        int type=c.getType(i);out.writeByte(type);
        if(type==Cursor.FIELD_TYPE_INTEGER)out.writeLong(c.getLong(i));
        else if(type==Cursor.FIELD_TYPE_STRING)text(out,c.getString(i));
        else if(type==Cursor.FIELD_TYPE_BLOB){byte[] b=c.getBlob(i);out.writeInt(b.length);out.write(b);}
        else require(type==Cursor.FIELD_TYPE_NULL,"Unsupported SQL type");
    }
    /** Explicit declared columns defeat stale SELECT-star metadata after ALTER.
     * The unchanged v3 decoder checks names/types/domain/canonical ordering.
     */
    private static byte[] baseWire(SQLiteDatabase db){
        try{
            Schema3Store.ComparisonBuffer b=new Schema3Store.ComparisonBuffer(Wire.LIMIT);
            DataOutputStream out=new DataOutputStream(b);
            out.writeInt(0x50544442);out.writeInt(2);out.writeInt(3);out.writeInt(OLD.length);
            for(String table:OLD){
                List<String> names=new ArrayList<>();
                try(Cursor info=db.rawQuery("PRAGMA table_info("+table+")",null)){
                    while(info.moveToNext()){String name=info.getString(1);require(name.matches("[a-z_]+"),"Invalid column");names.add(name);}
                }
                require(!names.isEmpty(),"Missing historical table");
                try(Cursor c=db.rawQuery("SELECT "+String.join(",",names)+" FROM "+table+" ORDER BY rowid",null)){
                    text(out,table);out.writeInt(names.size());for(String name:names)text(out,name);out.writeInt(c.getCount());
                    while(c.moveToNext())for(int i=0;i<names.size();i++)cell(out,c,i);
                }
            }out.flush();return b.toByteArray();
        }catch(IOException e){throw new IllegalStateException("Cannot encode historical state",e);}
    }
    private static byte[] businessCells(SQLiteDatabase db,boolean includeRevision){
        try{
            Schema3Store.ComparisonBuffer b=new Schema3Store.ComparisonBuffer(Wire.LIMIT);DataOutputStream out=new DataOutputStream(b);
            for(String table:OLD){
                if(!includeRevision&&table.equals("revision"))continue;
                // No DDL is performed between these internal snapshots.
                try(Cursor c=db.rawQuery("SELECT rowid,* FROM "+table+" ORDER BY rowid",null)){
                    text(out,table);out.writeInt(c.getCount());out.writeInt(c.getColumnCount());
                    for(String name:c.getColumnNames())text(out,name);
                    while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++)cell(out,c,i);
                }
            }out.flush();return b.toByteArray();
        }catch(IOException e){throw new IllegalStateException("Cannot compare historical cells",e);}
    }
    private static byte[] encodeState(SQLiteDatabase db){
        validate(db);byte[] base=baseWire(db);
        try(SQLiteDatabase checked=Schema3Store.stateCandidate(base)){}
        return Wire.encode(base,links(db));
    }
    static SQLiteDatabase stateCandidate(byte[] input){
        require(input!=null&&input.length>=12&&input.length<=Wire.LIMIT,"Schema4 state validation failed: input budget");
        byte[] owned=input.clone();SQLiteDatabase stage=null;boolean success=false;
        try{
            java.nio.ByteBuffer header=java.nio.ByteBuffer.wrap(owned);
            require(header.getInt()==0x50544442,"Invalid state magic");
            int wire=header.getInt(),version=header.getInt();List<Link> incoming=Collections.emptyList();
            boolean modern=wire==3&&version==4;
            if(modern){
                Wire parsed=Wire.read(owned);stage=Schema3Store.stateCandidate(parsed.base());incoming=parsed.links;
            }else{
                require((wire==1&&version==2)||(wire==2&&version==3),"Unsupported state version");
                stage=Schema3Store.stateCandidate(owned);
            }
            stage.beginTransaction();
            try{
                stage.execSQL(SHORTCUT_DDL);
                for(Link link:incoming)stage.execSQL("INSERT INTO category_shortcuts VALUES(?,?)",new Object[]{link.category,link.application});
                stage.setVersion(4);
                byte[] actual=encodeState(stage);
                if(modern)require(Arrays.equals(owned,actual),"Noncanonical schema4 state");
                stage.setTransactionSuccessful();
            }finally{stage.endTransaction();}
            success=true;return stage;
        }catch(RuntimeException e){throw new IllegalArgumentException("Schema4 state validation failed",e);}
        finally{if(!success&&stage!=null)stage.close();}
    }
    public synchronized byte[] exportState(){
        SQLiteDatabase db=getWritableDatabase();db.beginTransaction();
        try{
            require(db.getVersion()==4,"Export requires schema4");byte[] bytes=encodeState(db);
            db.setTransactionSuccessful();return bytes;
        }finally{db.endTransaction();}
    }
    private static void outsideTransaction(SQLiteDatabase db){
        if(db.inTransaction())throw new IllegalStateException("Operation refuses outer transaction");
    }
    private static void exists(SQLiteDatabase db,String table,long id,String reason){
        try(Cursor c=db.rawQuery("SELECT id FROM "+table+" WHERE id=?",new String[]{Long.toString(id)})){require(c.moveToFirst(),reason);}
    }
    /** Explicit setting, not a toggle. Idempotent calls never bump revision.
     * Only the selected relation and one revision may change, checked in the same
     * transaction against all historical typed cells, rowids and other links.
     */
    public synchronized boolean setShortcut(long category,long application,boolean enabled){
        Link wanted=new Link(category,application);SQLiteDatabase db=getWritableDatabase();outsideTransaction(db);
        db.beginTransaction();
        try{
            encodeState(db);
            exists(db,"categories",category,"Category missing");exists(db,"applications",application,"Application missing");
            List<Link> expected=new ArrayList<>(links(db));boolean present=expected.contains(wanted);
            if(present==enabled){db.setTransactionSuccessful();return false;}
            byte[] old=businessCells(db,false);long next=Math.incrementExact(revision(db));
            if(enabled){
                expected.add(wanted);expected.sort((a,b)->{int c=Long.compare(a.category,b.category);return c!=0?c:Long.compare(a.application,b.application);});
                db.execSQL("INSERT INTO category_shortcuts(category_id,application_id) VALUES(?,?)",new Object[]{category,application});
            }else{
                expected.remove(wanted);
                require(db.delete("category_shortcuts","category_id=? AND application_id=?",new String[]{Long.toString(category),Long.toString(application)})==1,"Shortcut deletion count");
            }
            db.execSQL("UPDATE revision SET value=? WHERE id=1",new Object[]{next});
            require(revision(db)==next&&expected.equals(links(db))&&Arrays.equals(old,businessCells(db,false)),"Shortcut write readback differs");
            encodeState(db);db.setTransactionSuccessful();return true;
        }finally{db.endTransaction();}
    }
    public synchronized List<Long> shortcutApplications(long category){
        require(category>0,"Invalid identity");SQLiteDatabase db=getReadableDatabase();db.beginTransaction();
        try{
            exists(db,"categories",category,"Category missing");List<Long> result=new ArrayList<>();
            for(Link link:links(db))if(link.category==category)result.add(link.application);
            db.setTransactionSuccessful();return Collections.unmodifiableList(result);
        }finally{db.endTransaction();}
    }
    /** Pure navigation candidates by stable application ID, across categories.
     * The caller still has to select/revalidate an activity at click time. This
     * list is NOT a durable consent/session token and causes no business writes.
     */
    public synchronized List<Long> activityTargets(long category,long application){
        Link wanted=new Link(category,application);SQLiteDatabase db=getReadableDatabase();db.beginTransaction();
        try{
            exists(db,"categories",category,"Category missing");exists(db,"applications",application,"Application missing");
            require(links(db).contains(wanted),"Shortcut missing");List<Long> result=new ArrayList<>();
            try(Cursor c=db.rawQuery("SELECT id FROM activities WHERE application_id=? AND archived=0 ORDER BY id",new String[]{Long.toString(application)})){
                while(c.moveToNext())result.add(c.getLong(0));
            }
            db.setTransactionSuccessful();return Collections.unmodifiableList(result);
        }finally{db.endTransaction();}
    }
    private static Map<String,Long> mediaRegistry(SQLiteDatabase db){
        Map<String,Long> result=new LinkedHashMap<>();
        try(Cursor c=db.rawQuery("SELECT id,bytes FROM media ORDER BY id",null)){
            while(c.moveToNext()){
                String id=c.getString(0);long count=c.getLong(1);MediaRepository.validId(id);
                require(count>0&&result.put(id,count)==null,"Invalid media registry");
            }
        }return result;
    }
    private static void exactFile(String id,long size,Path file)throws IOException{
        if(file==null||Files.isSymbolicLink(file)||!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)||Files.size(file)!=size)
            throw new IOException("Registered media size or file differs");
        java.security.MessageDigest hash=MediaRepository.sha();long read=0;
        try(InputStream in=Files.newInputStream(file,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
            byte[] buffer=new byte[16384];int n;
            while((n=in.read(buffer))!=-1){
                if(n<=0||n>size-read)throw new IOException("Registered media read differs");
                read+=n;hash.update(buffer,0,n);
            }
        }
        if(read!=size||!id.equals(MediaRepository.hex(hash.digest())))throw new IOException("Registered media digest differs");
    }
    static SQLiteDatabase archiveCandidate(BackupArchive.Snapshot snapshot)throws IOException{
        require(snapshot!=null,"Missing archive snapshot");SQLiteDatabase db=stateCandidate(snapshot.state());boolean success=false;
        try{
            Map<String,Long> expected=mediaRegistry(db);
            require(snapshot.assets().keySet().equals(expected.keySet()),"Archive registered asset set differs");
            for(Map.Entry<String,Long> asset:expected.entrySet())exactFile(asset.getKey(),asset.getValue(),snapshot.assets().get(asset.getKey()));
            success=true;return db;
        }finally{if(!success)db.close();}
    }
    public synchronized void exportBackup(Path destination,MediaRepository media)throws IOException{
        require(destination!=null&&media!=null,"Missing backup destination or media");
        byte[] state=exportState();
        try(SQLiteDatabase candidate=stateCandidate(state)){
            Map<String,Long> registry=mediaRegistry(candidate);
            for(Map.Entry<String,Long> asset:registry.entrySet()){
                media.verify(asset.getKey());exactFile(asset.getKey(),asset.getValue(),media.path(asset.getKey()));
            }
            BackupArchive.write(destination,state,registry.keySet(),media);
        }
    }
    public static final class RestorePlan implements AutoCloseable {
        private final Schema4Store owner;
        private final Object session;
        private final SQLiteDatabase connection;
        private final BackupArchive.Snapshot staged;
        private final byte[] before,beforeCells,expected;
        private final Map<String,Long> current,incoming;
        private boolean terminal;
        private RestorePlan(Schema4Store owner,SQLiteDatabase connection,BackupArchive.Snapshot staged,
                            byte[] before,byte[] beforeCells,byte[] expected,Map<String,Long> current,Map<String,Long> incoming){
            this.owner=owner;this.session=owner.session;this.connection=connection;this.staged=staged;
            this.before=before.clone();this.beforeCells=beforeCells.clone();this.expected=expected.clone();
            this.current=Collections.unmodifiableMap(new LinkedHashMap<>(current));
            this.incoming=Collections.unmodifiableMap(new LinkedHashMap<>(incoming));
        }
        public Map<String,Long> currentCounts(){return current;}
        public Map<String,Long> incomingCounts(){return incoming;}
        @Override public void close()throws IOException{synchronized(owner){terminal=true;staged.close();}}
    }
    private static List<String> tables(){
        List<String> names=new ArrayList<>(Arrays.asList(OLD));names.add("category_shortcuts");return names;
    }
    private static Map<String,Long> counts(SQLiteDatabase db){
        Map<String,Long> result=new LinkedHashMap<>();
        for(String table:tables())try(Cursor c=db.rawQuery("SELECT count(*) FROM "+table,null)){
            require(c.moveToFirst(),"Missing count");result.put(table,c.getLong(0));
        }return result;
    }
    public synchronized RestorePlan prepareRestore(Path archive,Path staging,long budget)throws IOException{
        SQLiteDatabase live=getWritableDatabase();outsideTransaction(live);
        BackupArchive.Snapshot snapshot=BackupArchive.read(archive,staging,budget);boolean success=false;
        try(SQLiteDatabase candidate=archiveCandidate(snapshot)){
            live.beginTransaction();
            try{
                RestorePlan plan=new RestorePlan(this,live,snapshot,encodeState(live),businessCells(live,true),
                    encodeState(candidate),counts(live),counts(candidate));
                live.setTransactionSuccessful();success=true;return plan;
            }finally{live.endTransaction();}
        }finally{if(!success)snapshot.close();}
    }
    private static void unchanged(SQLiteDatabase db,RestorePlan plan){
        if(db!=plan.connection||!db.isOpen()||db.getVersion()!=4||
           !Arrays.equals(plan.before,encodeState(db))||!Arrays.equals(plan.beforeCells,businessCells(db,true)))
            throw new IllegalStateException("Database changed; review restore again");
    }
    private static void replaceRows(SQLiteDatabase live,SQLiteDatabase source){
        List<String> tables=tables();
        for(int i=tables.size()-1;i>=0;i--)live.delete(tables.get(i),null,null);
        for(String table:tables){
            String order=table.equals("category_shortcuts")?"category_id,application_id":"rowid";
            try(Cursor c=source.rawQuery("SELECT * FROM "+table+" ORDER BY "+order,null)){
                List<String> names=Arrays.asList(c.getColumnNames());String[] marks=new String[names.size()];Arrays.fill(marks,"?");
                String sql="INSERT INTO "+table+"("+String.join(",",names)+") VALUES("+String.join(",",marks)+")";
                while(c.moveToNext()){
                    Object[] values=new Object[names.size()];
                    for(int i=0;i<values.length;i++){
                        int type=c.getType(i);
                        if(type==1)values[i]=c.getLong(i);else if(type==3)values[i]=c.getString(i);
                        else if(type==4)values[i]=c.getBlob(i);else require(type==0,"Unsupported restore type");
                    }live.execSQL(sql,values);
                }
            }
        }
    }
    /** Single-use owner/session/connection-bound logical replacement.
     * Revalidate staged bytes, close staging before commit, retain old media on
     * every failure. New unreachable blobs may remain; never blindly delete them.
     */
    public synchronized void confirmRestore(RestorePlan plan,MediaRepository media)throws IOException{
        if(plan==null||plan.owner!=this)throw new IllegalArgumentException("Restore belongs to a different helper");
        if(plan.terminal||plan.session!=session){plan.close();throw new IllegalStateException("Restore plan no longer active");}
        plan.terminal=true;
        try(BackupArchive.Snapshot snapshot=plan.staged){
            require(media!=null,"Missing restore media");SQLiteDatabase live=getWritableDatabase();outsideTransaction(live);
            live.beginTransaction();
            try{unchanged(live,plan);live.setTransactionSuccessful();}finally{live.endTransaction();}
            try(SQLiteDatabase candidate=archiveCandidate(snapshot)){
                require(Arrays.equals(plan.expected,encodeState(candidate)),"Reviewed restore candidate changed");
                Map<String,Long> registry=mediaRegistry(candidate);
                for(Map.Entry<String,Long> asset:registry.entrySet()){
                    try(InputStream in=Files.newInputStream(snapshot.assets().get(asset.getKey()),StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
                        require(asset.getKey().equals(media.copy(in)),"Restore asset digest changed");
                    }
                    media.verify(asset.getKey());exactFile(asset.getKey(),asset.getValue(),media.path(asset.getKey()));
                }
                snapshot.close();
                live.beginTransaction();
                try{
                    unchanged(live,plan);replaceRows(live,candidate);
                    require(Arrays.equals(plan.expected,encodeState(live)),"Restore transaction readback differs");
                    businessCells(live,true);live.setTransactionSuccessful();
                }finally{live.endTransaction();}
            }
        }
    }
}
