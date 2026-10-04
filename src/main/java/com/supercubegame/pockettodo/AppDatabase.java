package com.supercubegame.pockettodo;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteConstraintException;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CodingErrorAction;
import java.nio.file.*;
import java.time.Instant;
import java.time.LocalDate;
import java.util.*;

/** Default SQLite schema2, with an explicit opt-in schema3 business-API facade.
 * Backup APIs are private-storage adapters, not SAF/UI acceptance or photo decoding.
 */
public final class AppDatabase extends SQLiteOpenHelper {
    private interface Work<T> { T run(SQLiteDatabase db); }
    private Object restoreSession=new Object();
    private final Schema3Store schema3;
    public AppDatabase(Context context,String name) {this(context,name,false);}
    private AppDatabase(Context context,String name,boolean upgraded) {
        super(context.getApplicationContext(),validName(name),null,2);
        schema3=upgraded?new Schema3Store(context,name):null;
        setWriteAheadLoggingEnabled(true);
    }
    /** Explicit compatibility bridge. The default constructor remains frozen at v2.
     * Every business read/write uses ONE delegate connection; the v2 superclass never
     * opens this file. Backup/restore and note origins use the verified v3 adapters.
     */
    public static AppDatabase openSchema3(Context context,String name){return new AppDatabase(context,name,true);}
    @Override public synchronized SQLiteDatabase getWritableDatabase(){return schema3==null?super.getWritableDatabase():schema3.getWritableDatabase();}
    @Override public synchronized SQLiteDatabase getReadableDatabase(){return schema3==null?super.getReadableDatabase():schema3.getReadableDatabase();}
    @Override public synchronized void close(){restoreSession=new Object();if(schema3!=null)schema3.close();super.close();}
    private static String validName(String name) {
        if(name==null||!name.matches("[A-Za-z0-9_-]+\\.db"))throw new IllegalArgumentException("无效数据库文件名");return name;
    }
    @Override public void onConfigure(SQLiteDatabase db) {db.setForeignKeyConstraintsEnabled(true);}
    @Override public void onCreate(SQLiteDatabase db) {createSchema2(db);}
    /** Frozen schema2 DDL for historical backup validation. Future live-schema
     * additions belong after this call in onCreate, NOT inside this old factory.
     * Keep addV2 frozen too; candidate must never infer old columns from live DDL.
     * Package entry for historical adapters; never call a live helper callback.
     * Caller owns connection, foreign keys and any DDL/version transaction.
     */
    static void createSchema2(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE revision(id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL CHECK(value>=0))");
        db.execSQL("INSERT INTO revision VALUES(1,0)");
        db.execSQL("CREATE TABLE categories(id INTEGER PRIMARY KEY CHECK(id>0),name TEXT NOT NULL CHECK(length(trim(name))>0),position INTEGER NOT NULL CHECK(position>=0))");
        db.execSQL("CREATE TABLE applications(id INTEGER PRIMARY KEY CHECK(id>0),name TEXT NOT NULL,package_name TEXT NOT NULL)");
        db.execSQL("CREATE UNIQUE INDEX application_package ON applications(package_name) WHERE package_name<>''");
        db.execSQL("CREATE TABLE activities(id INTEGER PRIMARY KEY CHECK(id>0),category_id INTEGER NOT NULL REFERENCES categories(id),application_id INTEGER REFERENCES applications(id),title TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN(0,1)))");
        db.execSQL("CREATE TABLE paths(activity_id INTEGER NOT NULL REFERENCES activities(id),position INTEGER NOT NULL CHECK(position>=0),text TEXT NOT NULL,PRIMARY KEY(activity_id,position))");
        db.execSQL("CREATE TABLE tags(activity_id INTEGER NOT NULL REFERENCES activities(id),position INTEGER NOT NULL CHECK(position>=0),text TEXT NOT NULL,PRIMARY KEY(activity_id,text),UNIQUE(activity_id,position))");
        db.execSQL("CREATE TABLE batches(id TEXT PRIMARY KEY NOT NULL,payload BLOB NOT NULL,revision INTEGER NOT NULL,undone INTEGER NOT NULL CHECK(undone IN(0,1)))");
        db.execSQL("CREATE TABLE ledger(id TEXT PRIMARY KEY NOT NULL,activity_id INTEGER NOT NULL REFERENCES activities(id),day TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('EXPENSE','REFUND','INCOME','PLANNED')),cents INTEGER NOT NULL CHECK(cents>=0),memo TEXT NOT NULL,batch_id TEXT NOT NULL REFERENCES batches(id),position INTEGER NOT NULL CHECK(position>=0),UNIQUE(batch_id,position))");
        db.execSQL("CREATE INDEX ledger_activity_day ON ledger(activity_id,day)");
        db.execSQL("CREATE TABLE checkins(activity_id INTEGER NOT NULL REFERENCES activities(id),day TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN('DONE','SKIPPED')),memo TEXT NOT NULL,recorded_at TEXT NOT NULL,PRIMARY KEY(activity_id,day))");
        db.execSQL("CREATE TABLE media(id TEXT PRIMARY KEY NOT NULL,mime TEXT NOT NULL,bytes INTEGER NOT NULL CHECK(bytes>0))");
        db.execSQL("CREATE TABLE notes(id TEXT PRIMARY KEY NOT NULL,activity_id INTEGER NOT NULL REFERENCES activities(id),title TEXT NOT NULL)");
        db.execSQL("CREATE TABLE blocks(note_id TEXT NOT NULL REFERENCES notes(id),id TEXT NOT NULL,position INTEGER NOT NULL CHECK(position>=0),kind TEXT NOT NULL CHECK(kind IN('TEXT','IMAGE')),text TEXT NOT NULL,asset_id TEXT REFERENCES media(id),caption TEXT NOT NULL,private INTEGER NOT NULL CHECK(private IN(0,1)),PRIMARY KEY(note_id,id),UNIQUE(note_id,position),CHECK((kind='TEXT' AND asset_id IS NULL) OR (kind='IMAGE' AND asset_id IS NOT NULL)))");
        addV2(db);
    }
    private static void addV2(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE fields(id TEXT PRIMARY KEY NOT NULL,name TEXT NOT NULL,type TEXT NOT NULL CHECK(type IN('TEXT','LONG_TEXT','NUMBER','DATE','SELECT','MULTI_SELECT','LINK','BOOLEAN')),archived INTEGER NOT NULL CHECK(archived IN(0,1)))");
        db.execSQL("CREATE TABLE field_options(field_id TEXT NOT NULL REFERENCES fields(id),id TEXT NOT NULL,position INTEGER NOT NULL CHECK(position>=0),PRIMARY KEY(field_id,id),UNIQUE(field_id,position))");
        db.execSQL("CREATE TABLE field_values(activity_id INTEGER NOT NULL REFERENCES activities(id),field_id TEXT NOT NULL REFERENCES fields(id),position INTEGER NOT NULL CHECK(position>=0),value TEXT NOT NULL,PRIMARY KEY(activity_id,field_id,position))");
        db.execSQL("CREATE TABLE field_notes(note_id TEXT PRIMARY KEY NOT NULL REFERENCES notes(id),field_id TEXT NOT NULL REFERENCES fields(id))");
        db.execSQL("CREATE TABLE todos(id TEXT PRIMARY KEY NOT NULL,title TEXT NOT NULL CHECK(length(trim(title))>0),done INTEGER NOT NULL CHECK(done IN(0,1)),position INTEGER NOT NULL CHECK(position>=0) UNIQUE)");
        db.execSQL("CREATE TABLE legacy_imports(source_id TEXT PRIMARY KEY NOT NULL,item_count INTEGER NOT NULL CHECK(item_count>=0))");
    }
    @Override public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion) {
        if(oldVersion!=1||newVersion!=2)throw new IllegalStateException("尚无已验证的迁移，保留原数据库");
        migrateSchema1To2(db);
    }
    /** Frozen additive step, without helper construction or version/commit changes.
     * Both helpers invoke it inside their own complete upgrade transaction.
     */
    static void migrateSchema1To2(SQLiteDatabase db) {
        // SQLiteOpenHelper wraps DDL and version change in one transaction.
        // No IF NOT EXISTS: a conflicting partial schema must fail, not be hidden.
        for(String table:Arrays.asList("revision","categories","applications","activities","paths","tags","batches","ledger","checkins","media","notes","blocks")) {
            try(Cursor c=db.rawQuery("SELECT * FROM "+table+" LIMIT 0",null)){c.getColumnCount();}
        }
        addV2(db);
        try(Cursor c=db.rawQuery("PRAGMA foreign_key_check",null)){
            if(c.moveToFirst())throw new IllegalStateException("迁移后关联校验失败，保留原数据库");
        }
    }
    @Override public void onDowngrade(SQLiteDatabase db,int oldVersion,int newVersion){throw new IllegalStateException("数据库来自更新版本，保留原数据");}
    private <T> T tx(Work<T> action) {
        SQLiteDatabase db=getWritableDatabase();db.beginTransaction();
        try{T result=action.run(db);if(schema3!=null)schema3.snapshot();db.setTransactionSuccessful();return result;}
        catch(SQLiteConstraintException e){throw new IllegalArgumentException("数据重复或关联不存在，本次修改已回滚",e);}
        finally{db.endTransaction();}
    }
    private static String text(String value){if(value==null||value.trim().isEmpty())throw new IllegalArgumentException("名称不能为空");return value.trim();}
    private static void exists(SQLiteDatabase db,String table,Object id) {
        // table names only from internal literals, never caller input.
        try(Cursor c=db.rawQuery("SELECT 1 FROM "+table+" WHERE id=?",new String[]{String.valueOf(id)})){
            if(!c.moveToFirst())throw new IllegalArgumentException("关联对象不存在："+table);
        }
    }
    private static long revision(SQLiteDatabase db){try(Cursor c=db.rawQuery("SELECT value FROM revision WHERE id=1",null)){if(!c.moveToFirst())throw new IllegalStateException("数据库缺少修订信息");return c.getLong(0);}}
    private static long bump(SQLiteDatabase db){long next=Math.incrementExact(revision(db));db.execSQL("UPDATE revision SET value=? WHERE id=1",new Object[]{next});return next;}
    public synchronized long count(String table) {
        if(!Arrays.asList("categories","applications","activities","paths","tags","ledger","batches","checkins","notes","blocks","media","fields","field_options","field_values","field_notes","todos","legacy_imports").contains(table))throw new IllegalArgumentException("不允许的表");
        try(Cursor c=getReadableDatabase().rawQuery("SELECT count(*) FROM "+table,null)){c.moveToFirst();return c.getLong(0);}
    }
    public synchronized void addCategory(long id,String name){Ledger.positive(id);String clean=text(name);tx(db->{db.execSQL("INSERT INTO categories(id,name,position) VALUES(?,?,(SELECT count(*) FROM categories))",new Object[]{id,clean});bump(db);return null;});}
    public synchronized void renameCategory(long id,String name){String clean=text(name);tx(db->{exists(db,"categories",id);db.execSQL("UPDATE categories SET name=? WHERE id=?",new Object[]{clean,id});bump(db);return null;});}
    public synchronized String categoryName(long id){try(Cursor c=getReadableDatabase().rawQuery("SELECT name FROM categories WHERE id=?",new String[]{Long.toString(id)})){if(!c.moveToFirst())throw new IllegalArgumentException("分类不存在");return c.getString(0);}}
    private static List<Long> categoryIds(SQLiteDatabase db){List<Long> out=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT id FROM categories ORDER BY position,id",null)){while(c.moveToNext())out.add(c.getLong(0));}return out;}
    public synchronized List<Long> categoryIds(){return Collections.unmodifiableList(categoryIds(getReadableDatabase()));}
    public synchronized void moveCategory(long id,int to){tx(db->{List<Long> ids=categoryIds(db);int from=ids.indexOf(id);if(from<0||to<0||to>=ids.size())throw new IllegalArgumentException("分类位置无效");ids.add(to,ids.remove(from));for(int i=0;i<ids.size();i++)db.execSQL("UPDATE categories SET position=? WHERE id=?",new Object[]{i,ids.get(i)});bump(db);return null;});}
    /** Reorder the exact category identities shown to the caller. The legacy
     * button API remains available; UI callers should pass their displayed order.
     * Membership/order guard, write, readback and revision share one transaction.
     * This is not a full-content/ABA token or a schema change.
     */
    public synchronized boolean moveCategory(long id,List<Long> expectedOrder,int to){
        Ledger.positive(id);
        if(expectedOrder==null||expectedOrder.isEmpty())throw new IllegalArgumentException("缺少分类顺序");
        List<Long> seen=new ArrayList<>(expectedOrder);Set<Long> unique=new HashSet<>();
        for(Long key:seen)if(key==null||key<=0||!unique.add(key))throw new IllegalArgumentException("分类标识无效或重复");
        if(!seen.contains(id)||to<0||to>=seen.size())throw new IllegalArgumentException("分类位置无效");
        SQLiteDatabase connection=getWritableDatabase();
        if(connection.inTransaction())throw new IllegalStateException("请在当前操作结束后调整分类顺序");
        return tx(db->{
            List<Long> ids=categoryIds(db);
            if(!ids.equals(seen))throw new IllegalStateException("分类列表已变化，请刷新后重新排序");
            int from=ids.indexOf(id);
            if(from==to)return false;
            ids.add(to,ids.remove(from));
            for(int i=0;i<ids.size();i++){
                db.execSQL("UPDATE categories SET position=? WHERE id=?",new Object[]{i,ids.get(i)});
                try(Cursor changed=db.rawQuery("SELECT changes()",null)){
                    if(!changed.moveToFirst()||changed.getLong(0)!=1)throw new IllegalStateException("分类排序目标已变化");
                }
            }
            int index=0;
            try(Cursor c=db.rawQuery("SELECT id,position FROM categories ORDER BY position,id",null)){
                while(c.moveToNext()){
                    if(index>=ids.size()||c.getLong(0)!=ids.get(index)||c.getLong(1)!=index)
                        throw new IllegalStateException("分类排序回读不一致，本次修改已回滚");
                    index++;
                }
            }
            if(index!=ids.size())throw new IllegalStateException("分类数量已变化，本次修改已回滚");
            bump(db);return true;
        });
    }
    public synchronized void addApplication(long id,String name,String packageName){Ledger.positive(id);String clean=text(name);if(packageName==null||(!packageName.isEmpty()&&!packageName.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+")))throw new IllegalArgumentException("应用包名无效");tx(db->{db.execSQL("INSERT INTO applications VALUES(?,?,?)",new Object[]{id,clean,packageName});bump(db);return null;});}
    public synchronized void addActivity(long id,long category,long application,String title){Ledger.positive(id);Ledger.positive(category);if(application<0)throw new IllegalArgumentException("应用标识无效");String clean=text(title);tx(db->{exists(db,"categories",category);if(application!=0)exists(db,"applications",application);db.execSQL("INSERT INTO activities(id,category_id,application_id,title) VALUES(?,?,?,?)",new Object[]{id,category,application==0?null:application,clean});bump(db);return null;});}
    private void orderedStrings(String table,long activity,List<String> values,boolean deduplicate){if(values==null)throw new IllegalArgumentException("缺少有序内容");List<String> clean=new ArrayList<>();for(String value:values){String s=text(value);if(!deduplicate||!clean.contains(s))clean.add(s);}tx(db->{exists(db,"activities",activity);db.delete(table,"activity_id=?",new String[]{Long.toString(activity)});for(int i=0;i<clean.size();i++)db.execSQL("INSERT INTO "+table+" VALUES(?,?,?)",new Object[]{activity,i,clean.get(i)});bump(db);return null;});}
    private List<String> orderedStrings(String table,long activity){SQLiteDatabase db=getReadableDatabase();exists(db,"activities",activity);List<String> out=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT text FROM "+table+" WHERE activity_id=? ORDER BY position",new String[]{Long.toString(activity)})){while(c.moveToNext())out.add(c.getString(0));}return Collections.unmodifiableList(out);}
    public synchronized void savePath(long activity,List<String> steps){orderedStrings("paths",activity,steps,false);}
    public synchronized List<String> path(long activity){return orderedStrings("paths",activity);}
    public synchronized void saveTags(long activity,List<String> tags){orderedStrings("tags",activity,tags,true);}
    public synchronized List<String> tags(long activity){return orderedStrings("tags",activity);}
    private static void utf8(DataOutputStream out,String value)throws IOException{byte[] bytes=value.getBytes(StandardCharsets.UTF_8);out.writeInt(bytes.length);out.write(bytes);}
    private static byte[] payload(List<Ledger.Entry> rows){try{ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);out.writeInt(rows.size());for(Ledger.Entry row:rows){utf8(out,row.id);out.writeLong(row.activityId);utf8(out,row.date.toString());utf8(out,row.kind.name());out.writeLong(row.cents);utf8(out,row.memo);}out.flush();return bytes.toByteArray();}catch(IOException e){throw new IllegalStateException(e);}}
    public synchronized boolean recordBatch(String key,List<Ledger.Entry> rows){Ledger.identifier(key);if(rows==null||rows.isEmpty()||Ledger.hasNull(rows))throw new IllegalArgumentException("记账批次不能为空");List<Ledger.Entry> owned=new ArrayList<>(rows);byte[] encoded=payload(owned);return tx(db->{try(Cursor c=db.rawQuery("SELECT payload,undone FROM batches WHERE id=?",new String[]{key})){if(c.moveToFirst()){if(!Arrays.equals(c.getBlob(0),encoded)||c.getInt(1)!=0)throw new IllegalStateException("批次已用于其他内容或已撤销");return false;}}long next=bump(db);db.execSQL("INSERT INTO batches VALUES(?,?,?,0)",new Object[]{key,encoded,next});for(int i=0;i<owned.size();i++){Ledger.Entry r=owned.get(i);exists(db,"activities",r.activityId);db.execSQL("INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?)",new Object[]{r.id,r.activityId,r.date.toString(),r.kind.name(),r.cents,r.memo,key,i});}return true;});}
    private static Ledger.Entry entry(Cursor c){return new Ledger.Entry(c.getString(0),c.getLong(1),LocalDate.parse(c.getString(2)),Ledger.Kind.valueOf(c.getString(3)),c.getLong(4),c.getString(5));}
    public synchronized void undoBatch(String key){Ledger.identifier(key);tx(db->{byte[] expected;try(Cursor c=db.rawQuery("SELECT payload,revision,undone FROM batches WHERE id=?",new String[]{key})){if(!c.moveToFirst()||c.getInt(2)!=0||c.getLong(1)!=revision(db))throw new IllegalStateException("只能撤销最新且未修改的批次");expected=c.getBlob(0);}List<Ledger.Entry> current=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT id,activity_id,day,kind,cents,memo FROM ledger WHERE batch_id=? ORDER BY position",new String[]{key})){while(c.moveToNext())current.add(entry(c));}if(!Arrays.equals(expected,payload(current)))throw new IllegalStateException("批次内容已变化");db.delete("ledger","batch_id=?",new String[]{key});db.execSQL("UPDATE batches SET undone=1 WHERE id=?",new Object[]{key});bump(db);return null;});}
    public synchronized long total(long activity,Set<LocalDate> dates,String metric){Ledger ledger=new Ledger();List<Ledger.Entry> rows=new ArrayList<>();try(Cursor c=getReadableDatabase().rawQuery("SELECT id,activity_id,day,kind,cents,memo FROM ledger",null)){while(c.moveToNext())rows.add(entry(c));}if(!rows.isEmpty())ledger.recordBatch("snapshot",rows);return ledger.total(activity,dates,metric);}
    public synchronized void putMark(CalendarRules.Mark mark){if(mark==null||mark.recordedAt==null)throw new IllegalArgumentException("需要真实录入时间");tx(db->{exists(db,"activities",mark.activityId);db.delete("checkins","activity_id=? AND day=?",new String[]{Long.toString(mark.activityId),mark.date.toString()});if(mark.status!=CalendarRules.Status.UNRECORDED)db.execSQL("INSERT INTO checkins VALUES(?,?,?,?,?)",new Object[]{mark.activityId,mark.date.toString(),mark.status.name(),mark.memo,mark.recordedAt.toString()});bump(db);return null;});}
    public synchronized List<CalendarRules.Mark> marks(long activity){SQLiteDatabase db=getReadableDatabase();exists(db,"activities",activity);List<CalendarRules.Mark> out=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT day,status,memo,recorded_at FROM checkins WHERE activity_id=? ORDER BY day",new String[]{Long.toString(activity)})){while(c.moveToNext())out.add(new CalendarRules.Mark(activity,LocalDate.parse(c.getString(0)),CalendarRules.Status.valueOf(c.getString(1)),c.getString(2),Instant.parse(c.getString(3))));}return Collections.unmodifiableList(out);}
    public synchronized void createNote(String id,long activity,String title){Ledger.identifier(id);String clean=text(title);tx(db->{exists(db,"activities",activity);db.execSQL("INSERT INTO notes VALUES(?,?,?)",new Object[]{id,activity,clean});bump(db);return null;});}
    /** Rename one stable note identity. Compare the displayed title inside the write
     * transaction, so a stale dialog cannot overwrite a newer title. Same-title saves
     * are read-only; block order, ownership, field links and immutable media stay intact.
     */
    public synchronized boolean renameNote(String id,long activity,String expectedTitle,String title){
        Ledger.identifier(id);Ledger.positive(activity);String clean=text(title);
        if(expectedTitle==null)throw new IllegalArgumentException("缺少原笔记标题");
        return tx(db->{
            String current;
            try(Cursor c=db.rawQuery("SELECT activity_id,title FROM notes WHERE id=?",new String[]{id})){
                if(!c.moveToFirst()||c.getLong(0)!=activity)throw new IllegalArgumentException("所选笔记不存在或不属于当前活动");
                current=c.getString(1);
            }
            if(!current.equals(expectedTitle))throw new IllegalStateException("笔记标题已变化，请重新打开改名");
            if(current.equals(clean))return false;
            db.execSQL("UPDATE notes SET title=? WHERE id=? AND activity_id=?",new Object[]{clean,id,activity});
            bump(db);return true;
        });
    }
    /** Move one stable note ID within the exact activity order the user saw.
     * Ordering uses the existing rowid slots, not a new schema or delete/reinsert.
     * IDs, ownership, title, block order, field links and media are untouched.
     * This compares membership/order, not full content or an ABA/session token.
     */
    public synchronized boolean moveNote(String id,long activity,List<String> expectedOrder,int to){
        Ledger.identifier(id);Ledger.positive(activity);
        if(expectedOrder==null||expectedOrder.isEmpty())throw new IllegalArgumentException("缺少当前笔记顺序");
        List<String> seen=new ArrayList<>(expectedOrder);Set<String> unique=new HashSet<>();
        for(String note:seen)if(!unique.add(Ledger.identifier(note)))throw new IllegalArgumentException("笔记顺序含重复标识");
        if(to<0||to>=seen.size())throw new IllegalArgumentException("笔记位置无效");
        SQLiteDatabase connection=getWritableDatabase();
        if(connection.inTransaction())throw new IllegalStateException("请在当前操作完成后重新排序");
        return tx(db->{
            List<String> ids=new ArrayList<>();List<Long> slots=new ArrayList<>();
            try(Cursor c=db.rawQuery("SELECT id,rowid FROM notes WHERE activity_id=? ORDER BY rowid",new String[]{Long.toString(activity)})){
                while(c.moveToNext()){ids.add(c.getString(0));slots.add(c.getLong(1));}
            }
            int from=ids.indexOf(id);
            if(from<0)throw new IllegalArgumentException("所选笔记不存在或不属于当前活动");
            if(!ids.equals(seen))throw new IllegalStateException("笔记顺序已变化，请刷新后重新排序");
            if(from==to)return false;
            // Find a free slot across ALL owners. No MAX+1 overflow and no
            // assumptions about old backups having positive or contiguous rowids.
            long spare=0;
            try(Cursor c=db.rawQuery("SELECT rowid FROM notes WHERE rowid>=0 ORDER BY rowid",null)){
                while(c.moveToNext()){
                    long occupied=c.getLong(0);
                    if(occupied>spare)break;
                    if(occupied==spare)spare=Math.incrementExact(spare);
                }
            }
            moveNoteSlot(db,id,activity,spare);
            if(from<to){
                for(int i=from+1;i<=to;i++)moveNoteSlot(db,ids.get(i),activity,slots.get(i-1));
            }else{
                for(int i=from-1;i>=to;i--)moveNoteSlot(db,ids.get(i),activity,slots.get(i+1));
            }
            moveNoteSlot(db,id,activity,slots.get(to));
            List<String> wanted=new ArrayList<>(ids);wanted.add(to,wanted.remove(from));
            int index=0;
            try(Cursor c=db.rawQuery("SELECT id,rowid FROM notes WHERE activity_id=? ORDER BY rowid",new String[]{Long.toString(activity)})){
                while(c.moveToNext()){
                    if(index>=wanted.size()||!wanted.get(index).equals(c.getString(0))||slots.get(index)!=c.getLong(1))
                        throw new IllegalStateException("笔记排序回读不一致，本次修改已回滚");
                    index++;
                }
            }
            if(index!=wanted.size())throw new IllegalStateException("笔记数量已变化，本次修改已回滚");
            bump(db);return true;
        });
    }
    private static void moveNoteSlot(SQLiteDatabase db,String id,long activity,long slot){
        android.content.ContentValues values=new android.content.ContentValues();values.put("rowid",slot);
        if(db.update("notes",values,"id=? AND activity_id=?",new String[]{id,Long.toString(activity)})!=1)
            throw new IllegalStateException("笔记排序目标已变化，本次修改已回滚");
    }
    /** Read-only, exact-helper/session/connection-bound deletion preview.
     * No body text, image paths or mutable snapshot bytes are exposed.
     * Caller must close on cancellation and obtain explicit UI consent.
     */
    public static final class NoteDeletionPlan implements AutoCloseable {
        private final AppDatabase owner;
        private final Object session;
        private final SQLiteDatabase connection;
        private final String id,title,activityTitle;
        private final long activity,blocks,links;
        private byte[] before;
        private boolean terminal;
        private NoteDeletionPlan(AppDatabase owner,SQLiteDatabase connection,String id,long activity,
                                 String title,String activityTitle,long blocks,long links,byte[] before){
            this.owner=owner;this.session=owner.restoreSession;this.connection=connection;
            this.id=id;this.activity=activity;this.title=title;this.activityTitle=activityTitle;
            this.blocks=blocks;this.links=links;this.before=before;
        }
        public String noteId(){return id;}
        public long activityId(){return activity;}
        public String title(){return title;}
        public String activityTitle(){return activityTitle;}
        public long blockCount(){return blocks;}
        public long fieldLinkCount(){return links;}
        @Override public void close(){synchronized(owner){terminal=true;before=null;}}
    }
    private static long noteRows(SQLiteDatabase db,String table,String id){
        // Fixed internal table names only.
        try(Cursor c=db.rawQuery("SELECT count(*) FROM "+table+" WHERE note_id=?",new String[]{id})){
            if(!c.moveToFirst())throw new IllegalStateException("无法读取笔记数量");return c.getLong(0);
        }
    }
    /** Internal comparison only, never a backup wire format. Include schema version,
     * all business tables, row identities/order, typed cells and schema3 image origins.
     * Registry rows are compared; immutable files are never opened or removed here.
     */
    private static byte[] noteDeletionState(SQLiteDatabase db){
        tableSet(db);
        try{
            LimitedBytes bytes=new LimitedBytes();DataOutputStream out=new DataOutputStream(bytes);
            out.writeInt(0x4e444c31);out.writeInt(db.getVersion());out.writeInt(SNAPSHOT_TABLES.length);
            for(String table:SNAPSHOT_TABLES)try(Cursor c=db.rawQuery("SELECT rowid,* FROM "+table+" ORDER BY rowid",null)){
                utf8(out,table);out.writeInt(c.getColumnCount());for(String name:c.getColumnNames())utf8(out,name);out.writeInt(c.getCount());
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){
                    Object value=cell(c,i);out.writeByte(c.getType(i));
                    if(value instanceof Long)out.writeLong((Long)value);
                    else if(value instanceof String)utf8(out,(String)value);
                    else if(value instanceof byte[])blob(out,(byte[])value);
                }
            }
            out.flush();return bytes.toByteArray();
        }catch(IOException e){throw new IllegalStateException("无法读取删除预览状态",e);}
    }
    private static void noteDeletionNoOuterTransaction(SQLiteDatabase db){
        if(db.inTransaction())throw new IllegalStateException("请在当前操作完成后重新预览删除");
    }
    public synchronized NoteDeletionPlan prepareNoteDeletion(String id,long activity){
        Ledger.identifier(id);Ledger.positive(activity);
        SQLiteDatabase db=getReadableDatabase();noteDeletionNoOuterTransaction(db);db.beginTransaction();
        try{
            String title,activityTitle;
            try(Cursor c=db.rawQuery("SELECT n.title,a.title FROM notes n JOIN activities a ON a.id=n.activity_id WHERE n.id=? AND n.activity_id=?",new String[]{id,Long.toString(activity)})){
                if(!c.moveToFirst())throw new IllegalArgumentException("所选笔记不存在或不属于当前活动");
                title=c.getString(0);activityTitle=c.getString(1);
            }
            NoteDeletionPlan plan=new NoteDeletionPlan(this,db,id,activity,title,activityTitle,
                noteRows(db,"blocks",id),noteRows(db,"field_notes",id),noteDeletionState(db));
            db.setTransactionSuccessful();return plan;
        }finally{db.endTransaction();}
    }
    /** Single owner attempt, including failure, consumes the preview. Foreign helpers
     * cannot use it. Complete-state comparison and deletion share ONE transaction.
     * Remove references only: field definitions/values and all media remain intact.
     * No undo or garbage collection, and no claim of power-loss durability.
     */
    public synchronized void confirmNoteDeletion(NoteDeletionPlan plan){
        if(plan==null||plan.owner!=this)throw new IllegalArgumentException("删除预览不属于当前数据库");
        if(plan.terminal||plan.session!=restoreSession){plan.close();throw new IllegalStateException("删除预览已取消、使用或失效，请重新预览");}
        plan.terminal=true;
        try{
            SQLiteDatabase connection=getWritableDatabase();noteDeletionNoOuterTransaction(connection);
            if(connection!=plan.connection||!connection.isOpen())throw new IllegalStateException("数据库连接已变化，请重新预览删除");
            tx(db->{
                if(!Arrays.equals(plan.before,noteDeletionState(db)))throw new IllegalStateException("本机内容已变化，请重新预览删除");
                if(db.delete("field_notes","note_id=?",new String[]{plan.id})!=plan.links||
                   db.delete("blocks","note_id=?",new String[]{plan.id})!=plan.blocks||
                   db.delete("notes","id=? AND activity_id=?",new String[]{plan.id,Long.toString(plan.activity)})!=1)
                    throw new IllegalStateException("笔记删除数量不一致，本次修改已回滚");
                bump(db);return null;
            });
        }finally{plan.close();}
    }
    /** Registry only: caller must copy/verify files and validate actual image format. */
    public synchronized void registerMedia(String id,String mime,long bytes){MediaRepository.validId(id);String clean=text(mime);if(bytes<=0)throw new IllegalArgumentException("媒体大小无效");tx(db->{try(Cursor c=db.rawQuery("SELECT mime,bytes FROM media WHERE id=?",new String[]{id})){if(c.moveToFirst()){if(!clean.equals(c.getString(0))||bytes!=c.getLong(1))throw new IllegalStateException("媒体标识对应的元数据冲突");return null;}}db.execSQL("INSERT INTO media VALUES(?,?,?)",new Object[]{id,clean,bytes});bump(db);return null;});}
    public synchronized void saveNote(String id,List<NoteDocument.Block> blocks){if(schema3!=null){schema3.saveNote(id,blocks,schema3.snapshot());return;}Ledger.identifier(id);if(blocks==null||Ledger.hasNull(blocks))throw new IllegalArgumentException("缺少笔记内容");List<NoteDocument.Block> owned=new ArrayList<>(blocks);NoteDocument validator=new NoteDocument();for(NoteDocument.Block b:owned)validator.add(b);tx(db->{exists(db,"notes",id);db.delete("blocks","note_id=?",new String[]{id});for(int i=0;i<owned.size();i++){NoteDocument.Block b=owned.get(i);if(b.kind==NoteDocument.Kind.IMAGE)exists(db,"media",b.assetId);db.execSQL("INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?)",new Object[]{id,b.id,i,b.kind.name(),b.text,b.kind==NoteDocument.Kind.IMAGE?b.assetId:null,b.caption,b.privateContent?1:0});}bump(db);return null;});}
    public synchronized List<NoteDocument.Block> noteBlocks(String id){SQLiteDatabase db=getReadableDatabase();exists(db,"notes",id);List<NoteDocument.Block> out=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT id,kind,text,asset_id,caption,private FROM blocks WHERE note_id=? ORDER BY position",new String[]{id})){while(c.moveToNext())out.add(c.getString(1).equals("TEXT")?NoteDocument.Block.text(c.getString(0),c.getString(2),c.getInt(5)!=0):NoteDocument.Block.image(c.getString(0),c.getString(3),c.getString(4),c.getInt(5)!=0));}return Collections.unmodifiableList(out);}

    private static CustomFields.Definition fieldDefinition(SQLiteDatabase db,String id) {
        Ledger.identifier(id);String name,type;boolean archived;
        try(Cursor c=db.rawQuery("SELECT name,type,archived FROM fields WHERE id=?",new String[]{id})){
            if(!c.moveToFirst())throw new IllegalArgumentException("字段不存在");name=c.getString(0);type=c.getString(1);archived=c.getInt(2)!=0;
        }
        List<String> options=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT id FROM field_options WHERE field_id=? ORDER BY position",new String[]{id})){while(c.moveToNext())options.add(c.getString(0));}
        return new CustomFields.Definition(id,name,CustomFields.Type.valueOf(type),options,archived);
    }
    public synchronized CustomFields.Definition fieldDefinition(String id){return fieldDefinition(getReadableDatabase(),id);}
    public synchronized void defineField(String id,String name,String type,List<String> options){
        CustomFields validator=new CustomFields();validator.define(id,name,type,options);CustomFields.Definition f=validator.definition(id);
        tx(db->{db.execSQL("INSERT INTO fields VALUES(?,?,?,0)",new Object[]{f.id,f.name,f.type.name()});for(int i=0;i<f.options.size();i++)db.execSQL("INSERT INTO field_options VALUES(?,?,?)",new Object[]{f.id,f.options.get(i),i});bump(db);return null;});
    }
    public synchronized void renameField(String id,String name){String clean=text(name);tx(db->{exists(db,"fields",id);db.execSQL("UPDATE fields SET name=? WHERE id=?",new Object[]{clean,id});bump(db);return null;});}
    public synchronized void archiveField(String id,boolean archived){tx(db->{exists(db,"fields",id);db.execSQL("UPDATE fields SET archived=? WHERE id=?",new Object[]{archived?1:0,id});bump(db);return null;});}
    public synchronized void putField(long activity,String id,List<String> input){
        if(input==null||Ledger.hasNull(input))throw new IllegalArgumentException("无效字段值");List<String> owned=new ArrayList<>(input);
        tx(db->{exists(db,"activities",activity);CustomFields.Definition f=fieldDefinition(db,id);if(f.archived)throw new IllegalStateException("已归档字段只读");
            CustomFields validator=new CustomFields();validator.define(f.id,f.name,f.type.name(),f.options);validator.put(activity,id,owned);List<String> values=validator.value(activity,id);
            db.delete("field_values","activity_id=? AND field_id=?",new String[]{Long.toString(activity),id});for(int i=0;i<values.size();i++)db.execSQL("INSERT INTO field_values VALUES(?,?,?,?)",new Object[]{activity,id,i,values.get(i)});bump(db);return null;});
    }
    public synchronized List<String> fieldValue(long activity,String id){SQLiteDatabase db=getReadableDatabase();exists(db,"activities",activity);exists(db,"fields",id);List<String> values=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT value FROM field_values WHERE activity_id=? AND field_id=? ORDER BY position",new String[]{Long.toString(activity),id})){while(c.moveToNext())values.add(c.getString(0));}return Collections.unmodifiableList(values);}
    public synchronized void createFieldNote(String noteId,long activity,String fieldId,String title){Ledger.identifier(noteId);String clean=text(title);tx(db->{exists(db,"activities",activity);if(fieldDefinition(db,fieldId).archived)throw new IllegalStateException("不能向归档字段添加笔记");db.execSQL("INSERT INTO notes VALUES(?,?,?)",new Object[]{noteId,activity,clean});db.execSQL("INSERT INTO field_notes VALUES(?,?)",new Object[]{noteId,fieldId});bump(db);return null;});}
    public synchronized List<String> fieldNoteIds(long activity,String fieldId){SQLiteDatabase db=getReadableDatabase();exists(db,"activities",activity);exists(db,"fields",fieldId);List<String> ids=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT n.id FROM notes n JOIN field_notes f ON f.note_id=n.id WHERE n.activity_id=? AND f.field_id=? ORDER BY n.rowid",new String[]{Long.toString(activity),fieldId})){while(c.moveToNext())ids.add(c.getString(0));}return Collections.unmodifiableList(ids);}
    public static final class Todo {
        public final String id,title;public final boolean done;
        private Todo(String id,String title,boolean done){this.id=id;this.title=title;this.done=done;}
    }
    private static long nextTodoPosition(SQLiteDatabase db){try(Cursor c=db.rawQuery("SELECT MAX(position) FROM todos",null)){c.moveToFirst();return c.isNull(0)?0:Math.incrementExact(c.getLong(0));}}
    public synchronized void addTodo(String id,String title){Ledger.identifier(id);String clean=text(title);tx(db->{db.execSQL("INSERT INTO todos VALUES(?,?,0,?)",new Object[]{id,clean,nextTodoPosition(db)});bump(db);return null;});}
    public synchronized void editTodo(String id,String title,boolean done){Ledger.identifier(id);String clean=text(title);tx(db->{exists(db,"todos",id);db.execSQL("UPDATE todos SET title=?,done=? WHERE id=?",new Object[]{clean,done?1:0,id});bump(db);return null;});}
    public synchronized Todo todo(String id){Ledger.identifier(id);try(Cursor c=getReadableDatabase().rawQuery("SELECT title,done FROM todos WHERE id=?",new String[]{id})){if(!c.moveToFirst())throw new IllegalArgumentException("待办不存在");return new Todo(id,c.getString(0),c.getInt(1)!=0);}}
    public synchronized List<String> todoIds(){List<String> ids=new ArrayList<>();try(Cursor c=getReadableDatabase().rawQuery("SELECT id FROM todos ORDER BY position",null)){while(c.moveToNext())ids.add(c.getString(0));}return Collections.unmodifiableList(ids);}
    /** Reorder the exact complete todo identity list shown on the All tab.
     * Reuse existing nonnegative UNIQUE position slots, including gaps and MAX_VALUE.
     * No delete/reinsert, schema change, renumbering, or title/completion writes.
     * Membership/order guard, write, exact readback and revision share one transaction.
     * This is not a full-content/ABA token. UI owns filter and rendered-session guards.
     */
    public synchronized boolean moveTodo(String id,List<String> expectedOrder,int to){
        Ledger.identifier(id);
        if(expectedOrder==null||expectedOrder.isEmpty())throw new IllegalArgumentException("缺少当前待办顺序");
        List<String> seen=new ArrayList<>(expectedOrder);Set<String> unique=new HashSet<>();
        for(String key:seen)if(!unique.add(Ledger.identifier(key)))throw new IllegalArgumentException("待办顺序含重复标识");
        if(!seen.contains(id)||to<0||to>=seen.size())throw new IllegalArgumentException("待办位置无效");
        SQLiteDatabase connection=getWritableDatabase();
        if(connection.inTransaction())throw new IllegalStateException("请在当前操作完成后调整待办顺序");
        return tx(db->{
            List<String> ids=new ArrayList<>();List<Long> slots=new ArrayList<>();
            try(Cursor c=db.rawQuery("SELECT id,position FROM todos ORDER BY position",null)){
                while(c.moveToNext()){ids.add(c.getString(0));slots.add(c.getLong(1));}
            }
            if(!ids.equals(seen))throw new IllegalStateException("待办列表已变化，请刷新后重新排序");
            int from=ids.indexOf(id);
            if(from==to)return false;
            long spare=0;
            for(long occupied:slots){
                if(occupied>spare)break;
                if(occupied==spare)spare=Math.incrementExact(spare);
            }
            moveTodoSlot(db,id,spare);
            if(from<to){
                for(int i=from+1;i<=to;i++)moveTodoSlot(db,ids.get(i),slots.get(i-1));
            }else{
                for(int i=from-1;i>=to;i--)moveTodoSlot(db,ids.get(i),slots.get(i+1));
            }
            moveTodoSlot(db,id,slots.get(to));
            ids.add(to,ids.remove(from));int index=0;
            try(Cursor c=db.rawQuery("SELECT id,position FROM todos ORDER BY position",null)){
                while(c.moveToNext()){
                    if(index>=ids.size()||!ids.get(index).equals(c.getString(0))||slots.get(index)!=c.getLong(1))
                        throw new IllegalStateException("待办排序回读不一致，本次修改已回滚");
                    index++;
                }
            }
            if(index!=ids.size())throw new IllegalStateException("待办数量已变化，本次修改已回滚");
            bump(db);return true;
        });
    }
    private static void moveTodoSlot(SQLiteDatabase db,String id,long position){
        db.execSQL("UPDATE todos SET position=? WHERE id=?",new Object[]{position,id});
        try(Cursor c=db.rawQuery("SELECT changes()",null)){
            if(!c.moveToFirst()||c.getLong(0)!=1)throw new IllegalStateException("待办排序目标已变化，本次修改已回滚");
        }
    }
    /** In-memory, single-attempt ordinary-todo preview. No schema or media changes.
     * All token state is guarded by the owning helper monitor. Closing a helper
     * changes restoreSession, so reopening that same helper cannot revive a token.
     */
    public static final class TodoDeletionPlan implements AutoCloseable {
        private final AppDatabase owner;
        private final Object session;
        private final SQLiteDatabase connection;
        private final String id,title;
        private final boolean done;
        private final long position,rowid;
        private byte[] before;
        private boolean terminal;
        private TodoDeletionPlan(AppDatabase owner,SQLiteDatabase connection,String id,String title,
                                 boolean done,long position,long rowid,byte[] before){
            this.owner=owner;this.session=owner.restoreSession;this.connection=connection;
            this.id=id;this.title=title;this.done=done;this.position=position;this.rowid=rowid;this.before=before;
        }
        public String todoId(){return id;}
        public String title(){return title;}
        public boolean done(){return done;}
        public long position(){return position;}
        @Override public void close(){synchronized(owner){terminal=true;before=null;}}
    }
    public static final class TodoDeletionUndo implements AutoCloseable {
        private final AppDatabase owner;
        private final Object session;
        private final SQLiteDatabase connection;
        private final String id,title;
        private final boolean done;
        private final long position,rowid;
        private byte[] after,restored;
        private boolean terminal;
        private TodoDeletionUndo(TodoDeletionPlan plan,byte[] after,byte[] restored){
            owner=plan.owner;session=plan.session;connection=plan.connection;
            id=plan.id;title=plan.title;done=plan.done;position=plan.position;rowid=plan.rowid;
            this.after=after;this.restored=restored;
        }
        public String todoId(){return id;}
        public String title(){return title;}
        @Override public void close(){synchronized(owner){terminal=true;after=null;restored=null;}}
    }
    /** Canonical full-state oracle with an optional logical deletion and revision
     * replacement. These transformations calculate the expected result BEFORE SQL.
     * Include every table, column, storage type and rowid; keep the existing 8MiB
     * snapshot budget. Registry only: immutable media files are never touched.
     */
    private static byte[] todoDeletionState(SQLiteDatabase db,String omit,long revisionValue){
        tableSet(db);
        try{
            LimitedBytes bytes=new LimitedBytes();DataOutputStream out=new DataOutputStream(bytes);
            out.writeInt(0x54444c31);out.writeInt(db.getVersion());out.writeInt(SNAPSHOT_TABLES.length);
            for(String table:SNAPSHOT_TABLES)try(Cursor c=db.rawQuery("SELECT rowid,* FROM "+table+" ORDER BY rowid",null)){
                boolean deleting=omit!=null&&table.equals("todos");
                int idColumn=deleting?c.getColumnIndexOrThrow("id"):-1;
                int revisionColumn=table.equals("revision")?c.getColumnIndexOrThrow("value"):-1;
                utf8(out,table);out.writeInt(c.getColumnCount());for(String name:c.getColumnNames())utf8(out,name);
                out.writeInt(c.getCount()-(deleting?1:0));int omitted=0;
                while(c.moveToNext()){
                    if(deleting&&omit.equals(c.getString(idColumn))){omitted++;continue;}
                    for(int i=0;i<c.getColumnCount();i++){
                        Object value=cell(c,i);out.writeByte(c.getType(i));
                        if(i==revisionColumn&&revisionValue>=0)value=revisionValue;
                        if(value instanceof Long)out.writeLong((Long)value);
                        else if(value instanceof String)utf8(out,(String)value);
                        else if(value instanceof byte[])blob(out,(byte[])value);
                    }
                }
                if(deleting&&omitted!=1)throw new IllegalStateException("待办目标已变化，请重新预览");
            }
            out.flush();return bytes.toByteArray();
        }catch(IOException e){throw new IllegalStateException("无法读取待办删除状态",e);}
    }
    public synchronized TodoDeletionPlan prepareTodoDeletion(String id){
        Ledger.identifier(id);SQLiteDatabase db=getReadableDatabase();noteDeletionNoOuterTransaction(db);
        db.beginTransaction();
        try{
            String title;boolean done;long position,rowid;
            try(Cursor c=db.rawQuery("SELECT title,done,position,rowid FROM todos WHERE id=?",new String[]{id})){
                if(!c.moveToFirst())throw new IllegalArgumentException("待办不存在");
                title=c.getString(0);done=c.getInt(1)!=0;position=c.getLong(2);rowid=c.getLong(3);
            }
            TodoDeletionPlan plan=new TodoDeletionPlan(this,db,id,title,done,position,rowid,todoDeletionState(db,null,-1));
            db.setTransactionSuccessful();return plan;
        }finally{db.endTransaction();}
    }
    /** Caller obtains explicit consent. Owner attempts consume even on failure.
     * Final full-state comparison, exact deletion, revision and readback share one
     * transaction. The undo token is returned only after tx has successfully ended.
     */
    public synchronized TodoDeletionUndo confirmTodoDeletion(TodoDeletionPlan plan){
        if(plan==null||plan.owner!=this)throw new IllegalArgumentException("删除预览不属于当前数据库");
        if(plan.terminal||plan.session!=restoreSession){plan.close();throw new IllegalStateException("删除预览已取消、使用或失效");}
        plan.terminal=true;
        try{
            SQLiteDatabase connection=getWritableDatabase();noteDeletionNoOuterTransaction(connection);
            if(connection!=plan.connection||!connection.isOpen())throw new IllegalStateException("数据库连接已变化");
            return tx(db->{
                if(!Arrays.equals(plan.before,todoDeletionState(db,null,-1)))throw new IllegalStateException("本机内容已变化，请重新预览删除");
                long next=Math.incrementExact(revision(db));
                byte[] expected=todoDeletionState(db,plan.id,next);
                byte[] restored=todoDeletionState(db,null,0);
                if(db.delete("todos","id=?",new String[]{plan.id})!=1)throw new IllegalStateException("待办删除数量不一致");
                if(bump(db)!=next||!Arrays.equals(expected,todoDeletionState(db,null,-1)))
                    throw new IllegalStateException("待办删除回读不一致，本次修改已回滚");
                return new TodoDeletionUndo(plan,expected,restored);
            });
        }finally{plan.close();}
    }
    /** Same session only, no persistent undo log. Any intervening full-state change
     * refuses restoration. Reinstate the original rowid as well as ID/title/done/
     * position; other rows are never shifted, deleted or overwritten.
     */
    public synchronized void undoTodoDeletion(TodoDeletionUndo token){
        if(token==null||token.owner!=this)throw new IllegalArgumentException("撤销记录不属于当前数据库");
        if(token.terminal||token.session!=restoreSession){token.close();throw new IllegalStateException("撤销记录已使用或失效");}
        token.terminal=true;
        try{
            SQLiteDatabase connection=getWritableDatabase();noteDeletionNoOuterTransaction(connection);
            if(connection!=token.connection||!connection.isOpen())throw new IllegalStateException("数据库连接已变化");
            tx(db->{
                if(!Arrays.equals(token.after,todoDeletionState(db,null,-1)))throw new IllegalStateException("本机内容已变化，不能撤销这次删除");
                long next=Math.incrementExact(revision(db));
                db.execSQL("INSERT INTO todos(rowid,id,title,done,position) VALUES(?,?,?,?,?)",
                    new Object[]{token.rowid,token.id,token.title,token.done?1:0,token.position});
                if(bump(db)!=next||!Arrays.equals(token.restored,todoDeletionState(db,null,0)))
                    throw new IllegalStateException("待办撤销回读不一致，本次修改已回滚");
                return null;
            });
        }finally{token.close();}
    }
    /** Append only, never overwrite. Caller must show preview/consent before invoking.
     * Exact same backup bytes imported at most once. Modified backup is a distinct source.
     * IDs are namespaced by backup hash; a conflicting local ID aborts the entire import.
     */
    public synchronized long importLegacy(byte[] bytes){
        LegacyImport.Plan plan=LegacyImport.preview(bytes);
        return tx(db->{try(Cursor c=db.rawQuery("SELECT item_count FROM legacy_imports WHERE source_id=?",new String[]{plan.sourceId()})){if(c.moveToFirst())return 0L;}
            db.execSQL("INSERT INTO legacy_imports VALUES(?,?)",new Object[]{plan.sourceId(),plan.todos().size()});long position=nextTodoPosition(db);
            for(TodoModel.Item item:plan.todos()){String id="legacy-"+plan.sourceId()+"-"+item.id;db.execSQL("INSERT INTO todos VALUES(?,?,?,?)",new Object[]{id,item.title,item.done?1:0,position});position=Math.incrementExact(position);}
            bump(db);return (long)plan.todos().size();});
    }

    // Fixed schema2 transport. No backup-provided SQL, identifiers or DDL are executed.
    // This order is topological for FKs; reverse order is used for transactional deletion.
    private static final String[] SNAPSHOT_TABLES={"revision","categories","applications","activities","paths","tags","batches","ledger","checkins","media","notes","blocks","fields","field_options","field_values","field_notes","todos","legacy_imports"};
    private static final int STATE_LIMIT=8*1024*1024; // Coupled to BackupArchive metadata budget.
    private static void require(boolean condition,String message){if(!condition)throw new IllegalArgumentException(message);}
    private static void tableSet(SQLiteDatabase db){
        Set<String> actual=new HashSet<>();try(Cursor c=db.rawQuery("SELECT name FROM sqlite_master WHERE type='table'",null)){
            while(c.moveToNext()){String name=c.getString(0);if(!name.equals("android_metadata")&&!name.startsWith("sqlite_"))actual.add(name);}
        }
        require(actual.equals(new HashSet<>(Arrays.asList(SNAPSHOT_TABLES))),"备份表集合与当前实现不一致，拒绝遗漏数据");
    }
    private static final class LimitedBytes extends ByteArrayOutputStream {
        @Override public synchronized void write(int value){require(count<STATE_LIMIT,"备份状态超过内存预算");super.write(value);}
        @Override public synchronized void write(byte[] b,int off,int len){require(len<=STATE_LIMIT-count,"备份状态超过内存预算");super.write(b,off,len);}
    }
    private static void blob(DataOutputStream out,byte[] value)throws IOException{out.writeInt(value.length);out.write(value);}
    private static byte[] readBlob(DataInputStream in)throws IOException{
        int n=in.readInt();require(n>=0&&n<=STATE_LIMIT&&n<=in.available(),"备份长度无效或截断");byte[] out=new byte[n];in.readFully(out);return out;
    }
    private static String readText(DataInputStream in)throws IOException{
        return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(readBlob(in))).toString();
    }
    private static Object cell(Cursor c,int i){switch(c.getType(i)){case Cursor.FIELD_TYPE_NULL:return null;case Cursor.FIELD_TYPE_INTEGER:return c.getLong(i);case Cursor.FIELD_TYPE_STRING:return c.getString(i);case Cursor.FIELD_TYPE_BLOB:return c.getBlob(i);default:throw new IllegalArgumentException("备份不接受浮点或未知 SQL 类型");}}
    private static String insertSql(String table,int columns){String[] marks=new String[columns];Arrays.fill(marks,"?");return "INSERT INTO "+table+" VALUES("+String.join(",",marks)+")";}
    private static byte[] encodeState(SQLiteDatabase db){
        tableSet(db);
        try{LimitedBytes bytes=new LimitedBytes();DataOutputStream out=new DataOutputStream(bytes);out.writeInt(0x50544442);out.writeInt(1);out.writeInt(2);out.writeInt(SNAPSHOT_TABLES.length);
            for(String table:SNAPSHOT_TABLES)try(Cursor c=db.rawQuery("SELECT * FROM "+table+" ORDER BY rowid",null)){
                utf8(out,table);out.writeInt(c.getColumnCount());for(String name:c.getColumnNames())utf8(out,name);out.writeInt(c.getCount());
                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){
                    Object value=cell(c,i);out.writeByte(c.getType(i));if(value instanceof Long)out.writeLong((Long)value);else if(value instanceof String)utf8(out,(String)value);else if(value instanceof byte[])blob(out,(byte[])value);
                }
            }out.flush();return bytes.toByteArray();
        }catch(IOException e){throw new IllegalStateException("无法编码备份状态",e);}
    }
    private static void deleteRows(SQLiteDatabase db){for(int i=SNAPSHOT_TABLES.length-1;i>=0;i--)db.delete(SNAPSHOT_TABLES[i],null,null);}
    private static void decodeRows(SQLiteDatabase db,byte[] bytes)throws IOException{
        DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes));
        require(in.readInt()==0x50544442&&in.readInt()==1&&in.readInt()==2,"未知备份格式或数据库版本");
        require(in.readInt()==SNAPSHOT_TABLES.length,"备份表数量不完整");
        for(String table:SNAPSHOT_TABLES){
            require(readText(in).equals(table),"备份表缺失、重复或顺序错误");List<String> names=new ArrayList<>(),types=new ArrayList<>();
            try(Cursor c=db.rawQuery("PRAGMA table_info("+table+")",null)){while(c.moveToNext()){names.add(c.getString(1));types.add(c.getString(2));}}
            require(in.readInt()==names.size(),"备份列数量不匹配");for(String name:names)require(readText(in).equals(name),"备份列不匹配");
            int rows=in.readInt();require(rows>=0&&rows<=in.available()/Math.max(1,names.size()),"备份行数量无效");String sql=insertSql(table,names.size());
            for(int row=0;row<rows;row++){Object[] values=new Object[names.size()];for(int col=0;col<values.length;col++){
                int tag=in.readUnsignedByte();String type=types.get(col);
                if(tag==0){require((table.equals("activities")&&names.get(col).equals("application_id"))||(table.equals("blocks")&&names.get(col).equals("asset_id")),"备份包含不允许的空值");values[col]=null;}
                else if(tag==1){require(type.equals("INTEGER"),"整数列类型不匹配");values[col]=in.readLong();}
                else if(tag==3){require(type.equals("TEXT"),"文本列类型不匹配");values[col]=readText(in);}
                else if(tag==4){require(type.equals("BLOB"),"二进制列类型不匹配");values[col]=readBlob(in);}
                else throw new IllegalArgumentException("未知备份值类型");
            }db.execSQL(sql,values);}
        }
        require(in.available()==0,"备份状态存在尾随数据");
    }
    private static void ordered(SQLiteDatabase db,String table,String group){
        String grouping=group.isEmpty()?"":" GROUP BY "+group;
        try(Cursor c=db.rawQuery("SELECT count(*),count(DISTINCT position),min(position),max(position) FROM "+table+grouping,null)){
            while(c.moveToNext()){long n=c.getLong(0);if(n>0)require(c.getLong(1)==n&&c.getLong(2)==0&&c.getLong(3)==n-1,"有序数据缺失或重复："+table);}
        }
    }
    private static LocalDate day(String input){LocalDate date=Ledger.validDate(LocalDate.parse(input));require(date.toString().equals(input),"非标准日期");return date;}
    private static List<Ledger.Entry> decodeBatch(byte[] bytes)throws IOException{
        DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes));int n=in.readInt();require(n>0&&n<=in.available(),"记账批次载荷无效");List<Ledger.Entry> rows=new ArrayList<>();Set<String> ids=new HashSet<>();
        for(int i=0;i<n;i++){Ledger.Entry e=new Ledger.Entry(readText(in),in.readLong(),day(readText(in)),Ledger.Kind.valueOf(readText(in)),in.readLong(),readText(in));require(ids.add(e.id),"批次内条目标识重复");rows.add(e);}
        require(in.available()==0&&Arrays.equals(payload(rows),bytes),"记账批次编码不完整");return rows;
    }
    private static void validateSemantics(SQLiteDatabase db)throws IOException{
        try(Cursor c=db.rawQuery("PRAGMA foreign_key_check",null)){require(!c.moveToFirst(),"备份存在无效关联");}
        revision(db);
        try(Cursor c=db.rawQuery("SELECT count(*) FROM revision",null)){c.moveToFirst();require(c.getLong(0)==1,"备份修订记录不完整");}
        for(String table:new String[]{"categories","applications","activities","notes","todos"}){
            String column=table.equals("categories")||table.equals("applications")?"name":"title";
            try(Cursor c=db.rawQuery("SELECT id,"+column+" FROM "+table,null)){while(c.moveToNext()){if(table.equals("notes")||table.equals("todos"))Ledger.identifier(c.getString(0));else Ledger.positive(c.getLong(0));require(text(c.getString(1)).equals(c.getString(1)),"名称不是有效规范文本");}}
        }
        try(Cursor c=db.rawQuery("SELECT package_name FROM applications",null)){while(c.moveToNext()){String p=c.getString(0);require(p.isEmpty()||p.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+"),"备份应用包名无效");}}
        for(String table:new String[]{"paths","tags"})try(Cursor c=db.rawQuery("SELECT text FROM "+table,null)){while(c.moveToNext())require(text(c.getString(0)).equals(c.getString(0)),"路径或标签文本无效");}
        ordered(db,"categories","");ordered(db,"paths","activity_id");ordered(db,"tags","activity_id");ordered(db,"ledger","batch_id");ordered(db,"blocks","note_id");ordered(db,"field_options","field_id");ordered(db,"field_values","activity_id,field_id");
        try(Cursor c=db.rawQuery("SELECT activity_id,day,status,memo,recorded_at FROM checkins",null)){while(c.moveToNext()){
            Instant at=Instant.parse(c.getString(4));require(at.toString().equals(c.getString(4)),"非标准录入时间");new CalendarRules.Mark(c.getLong(0),day(c.getString(1)),CalendarRules.Status.valueOf(c.getString(2)),c.getString(3),at);
        }}
        try(Cursor c=db.rawQuery("SELECT id,mime FROM media",null)){while(c.moveToNext()){MediaRepository.validId(c.getString(0));require(text(c.getString(1)).equals(c.getString(1)),"媒体类型无效");}}
        try(Cursor notes=db.rawQuery("SELECT id FROM notes",null)){while(notes.moveToNext()){
            NoteDocument validator=new NoteDocument();try(Cursor c=db.rawQuery("SELECT id,kind,text,asset_id,caption,private FROM blocks WHERE note_id=? ORDER BY position",new String[]{notes.getString(0)})){
                while(c.moveToNext()){boolean image=c.getString(1).equals("IMAGE");NoteDocument.Block b=image?NoteDocument.Block.image(c.getString(0),c.getString(3),c.getString(4),c.getInt(5)!=0):NoteDocument.Block.text(c.getString(0),c.getString(2),c.getInt(5)!=0);validator.add(b);require(b.text.equals(c.getString(2))&&b.caption.equals(c.getString(4)),"笔记块有非规范隐藏内容");}
            }
        }}
        try(Cursor fields=db.rawQuery("SELECT id FROM fields",null)){while(fields.moveToNext()){
            CustomFields.Definition f=fieldDefinition(db,fields.getString(0));CustomFields validator=new CustomFields();validator.define(f.id,f.name,f.type.name(),f.options);
            // Validate historical values even for archived definitions; do not reopen archive.
            try(Cursor owners=db.rawQuery("SELECT DISTINCT activity_id FROM field_values WHERE field_id=?",new String[]{f.id})){while(owners.moveToNext()){
                long activity=owners.getLong(0);List<String> values=new ArrayList<>();try(Cursor c=db.rawQuery("SELECT value FROM field_values WHERE activity_id=? AND field_id=? ORDER BY position",new String[]{Long.toString(activity),f.id})){while(c.moveToNext())values.add(c.getString(0));}
                validator.put(activity,f.id,values);require(validator.value(activity,f.id).equals(values),"字段值重复或非规范");
            }}
        }}
        Set<Long> batchRevisions=new HashSet<>();try(Cursor c=db.rawQuery("SELECT id,payload,revision,undone FROM batches",null)){while(c.moveToNext()){
            String id=Ledger.identifier(c.getString(0));long rev=c.getLong(2);boolean undone=c.getInt(3)!=0;require(rev>0&&rev<=revision(db)&&batchRevisions.add(rev)&&(!undone||rev<revision(db)),"批次修订号无效");
            List<Ledger.Entry> saved=decodeBatch(c.getBlob(1));for(Ledger.Entry row:saved)exists(db,"activities",row.activityId);
            List<Ledger.Entry> live=new ArrayList<>();try(Cursor rows=db.rawQuery("SELECT id,activity_id,day,kind,cents,memo FROM ledger WHERE batch_id=? ORDER BY position",new String[]{id})){while(rows.moveToNext()){day(rows.getString(2));live.add(entry(rows));}}
            require(undone?live.isEmpty():saved.equals(live),"账本与批次日志不一致");
        }}
        try(Cursor c=db.rawQuery("SELECT source_id FROM legacy_imports",null)){while(c.moveToNext())MediaRepository.validId(c.getString(0));}
    }
    /** Frozen-format candidate. The old canonical equality check is mandatory BEFORE
     * any future migration to a newer candidate; never decode old bytes into live DDL.
     * Currently only schema2 is supported, and no migration/normalization is performed.
     */
    private SQLiteDatabase candidate(byte[] bytes){return strictSchema2Candidate(bytes);}
    /** Package-level frozen decoder for newer adapters. Caller closes the returned
     * independent in-memory database. This method never migrates or opens live data.
     */
    static SQLiteDatabase strictSchema2Candidate(byte[] bytes){
        require(bytes!=null&&bytes.length>0&&bytes.length<=STATE_LIMIT,"备份状态为空或超过预算");SQLiteDatabase stage=SQLiteDatabase.create(null);boolean success=false;
        try{stage.setForeignKeyConstraintsEnabled(true);createSchema2(stage);stage.beginTransaction();try{
            deleteRows(stage);decodeRows(stage,bytes);validateSemantics(stage);require(Arrays.equals(encodeState(stage),bytes),"备份规范回读不一致");stage.setTransactionSuccessful();
        }finally{stage.endTransaction();}success=true;return stage;
        }catch(IOException|RuntimeException e){throw new IllegalArgumentException("备份状态校验失败",e);}finally{if(!success)stage.close();}
    }
    /** One consistent transaction, including revision/journals and insertion-based note order. */
    public synchronized byte[] exportState(){if(schema3!=null)return schema3.exportState();return tx(db->{byte[] state=encodeState(db);try(SQLiteDatabase ignored=candidate(state)){return state;}});}
    private static Map<String,Long> registeredMedia(SQLiteDatabase db){Map<String,Long> out=new LinkedHashMap<>();try(Cursor c=db.rawQuery("SELECT id,bytes FROM media ORDER BY id",null)){while(c.moveToNext())out.put(c.getString(0),c.getLong(1));}return out;}
    public synchronized void exportBackup(Path destination,MediaRepository media)throws IOException{
        if(schema3!=null){schema3.exportBackup(destination,media);return;}
        if(media==null)throw new IllegalArgumentException("媒体仓库不能为空");byte[] state=exportState();
        try(SQLiteDatabase staged=candidate(state)){
            Map<String,Long> files=registeredMedia(staged);for(Map.Entry<String,Long> item:files.entrySet()){media.verify(item.getKey());if(Files.size(media.path(item.getKey()))!=item.getValue())throw new IOException("媒体登记大小不一致");}
            BackupArchive.write(destination,state,files.keySet(),media);
        }
    }
    private static void copyRows(SQLiteDatabase source,SQLiteDatabase target){
        for(String table:SNAPSHOT_TABLES)try(Cursor c=source.rawQuery("SELECT * FROM "+table+" ORDER BY rowid",null)){
            String sql=insertSql(table,c.getColumnCount());while(c.moveToNext()){Object[] values=new Object[c.getColumnCount()];for(int i=0;i<values.length;i++)values[i]=cell(c,i);target.execSQL(sql,values);}
        }
    }
    /** Destructive REPLACE adapter: future UI MUST preview and get consent first.
     * No archive SQL executed. Validate entire state/assets before touching live rows.
     * Publish immutable blobs first, then replace rows in ONE SQLite transaction.
     * Failure never removes old media. New unreachable blobs may remain for future GC;
     * do NOT delete them here because another writer may already reference them.
     * This is logical atomicity, not power-loss durability or an undo-restore feature.
     */
    public synchronized void restoreBackup(Path archive,Path stagingRoot,long byteBudget,MediaRepository media)throws IOException{
        if(schema3!=null){try(RestorePlan plan=prepareRestore(archive,stagingRoot,byteBudget)){confirmRestore(plan,media);}return;}
        if(media==null)throw new IllegalArgumentException("媒体仓库不能为空");
        try(BackupArchive.Snapshot snapshot=BackupArchive.read(archive,stagingRoot,byteBudget);SQLiteDatabase staged=candidate(snapshot.state())){
            // Bind commit equality to the validated candidate, not the transport bytes.
            // These are still identical in schema2; future version conversion belongs
            // inside candidate AFTER historical-format canonical validation succeeds.
            byte[] expected=encodeState(staged);Map<String,Long> registry=registeredMedia(staged);Map<String,Path> files=snapshot.assets();
            if(!registry.keySet().equals(files.keySet()))throw new IOException("媒体集合与数据库引用不一致");
            for(Map.Entry<String,Long> item:registry.entrySet())if(Files.size(files.get(item.getKey()))!=item.getValue())throw new IOException("媒体登记大小不一致");
            for(String id:registry.keySet())try(InputStream in=Files.newInputStream(files.get(id),StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
                if(!media.copy(in).equals(id))throw new IOException("恢复媒体摘要不一致");
            }
            // Staging cleanup occurs BEFORE live commit; cleanup failure cannot report
            // a failed restore after the replacement has already committed.
            snapshot.close();
            for(Map.Entry<String,Long> item:registry.entrySet()){media.verify(item.getKey());if(Files.size(media.path(item.getKey()))!=item.getValue())throw new IOException("恢复媒体回读大小不一致");}
            tx(db->{tableSet(db);deleteRows(db);copyRows(staged,db);require(Arrays.equals(encodeState(db),expected),"恢复事务回读不一致");return null;});
        }
    }

    /** A private, validated, single-attempt preview. Caller MUST close on cancellation
     * or lifecycle abandonment, and obtain explicit user consent before confirmRestore.
     * Counts describe replacement, not merge. No paths or mutable state are exposed.
     * This token is in-memory only, not restorable after process death/helper close.
     */
    public static final class RestorePlan implements AutoCloseable {
        private final AppDatabase owner;
        private final Object session;
        private final BackupArchive.Snapshot snapshot;
        private final Schema3Store.RestorePlan upgraded;
        private final byte[] before,expected;
        private final Map<String,Long> current,incoming;
        private boolean terminal;
        private RestorePlan(AppDatabase owner,BackupArchive.Snapshot snapshot,byte[] before,byte[] expected,Map<String,Long> current,Map<String,Long> incoming){
            this.owner=owner;this.session=owner.restoreSession;this.snapshot=snapshot;this.upgraded=null;
            this.before=before.clone();this.expected=expected.clone();this.current=current;this.incoming=incoming;
        }
        private RestorePlan(AppDatabase owner,Schema3Store.RestorePlan upgraded){
            this.owner=owner;this.session=owner.restoreSession;this.upgraded=upgraded;this.snapshot=null;
            this.before=null;this.expected=null;this.current=upgraded.currentCounts();this.incoming=upgraded.incomingCounts();
        }
        public Map<String,Long> currentCounts(){return current;}
        public Map<String,Long> incomingCounts(){return incoming;}
        @Override public void close()throws IOException{synchronized(owner){terminal=true;if(upgraded!=null)upgraded.close();else snapshot.close();}}
    }
    private static Map<String,Long> summary(SQLiteDatabase db){
        Map<String,Long> counts=new LinkedHashMap<>();for(String table:SNAPSHOT_TABLES)try(Cursor c=db.rawQuery("SELECT count(*) FROM "+table,null)){c.moveToFirst();counts.put(table,c.getLong(0));}
        return Collections.unmodifiableMap(counts);
    }
    private static Map<String,Long> validateFiles(SQLiteDatabase staged,BackupArchive.Snapshot snapshot)throws IOException{
        Map<String,Long> registry=registeredMedia(staged);Map<String,Path> files=snapshot.assets();
        if(!registry.keySet().equals(files.keySet()))throw new IOException("媒体集合与数据库引用不一致");
        for(Map.Entry<String,Long> item:registry.entrySet())if(!Files.isRegularFile(files.get(item.getKey()),LinkOption.NOFOLLOW_LINKS)||Files.size(files.get(item.getKey()))!=item.getValue())throw new IOException("媒体登记大小或文件类型不一致");
        return registry;
    }
    /** Performs full archive/domain validation, freezes the reviewed source in private
     * staging and captures a consistent current state. No live media is published.
     * Later source-file changes cannot substitute a different backup after consent.
     */
    public synchronized RestorePlan prepareRestore(Path archive,Path stagingRoot,long byteBudget)throws IOException{
        if(schema3!=null)return new RestorePlan(this,schema3.prepareRestore(archive,stagingRoot,byteBudget));
        BackupArchive.Snapshot snapshot=BackupArchive.read(archive,stagingRoot,byteBudget);boolean success=false;
        try{
            byte[] source=snapshot.state(),before=exportState();
            try(SQLiteDatabase incoming=candidate(source);SQLiteDatabase current=candidate(before)){
                validateFiles(incoming,snapshot);
                // Freeze exactly the validated candidate shown in the preview. Do not
                // remove candidate's old-format equality check to make conversion pass.
                byte[] expected=encodeState(incoming);
                RestorePlan plan=new RestorePlan(this,snapshot,before,expected,summary(current),summary(incoming));success=true;return plan;
            }
        }finally{if(!success)snapshot.close();}
    }
    private static void unchanged(SQLiteDatabase db,RestorePlan plan){
        // Revision alone is insufficient: restores can rewind it and another connection
        // could change content without bumping it. Compare the complete canonical state.
        if(!Arrays.equals(encodeState(db),plan.before))throw new IllegalStateException("本机数据已变化，请重新预览后确认恢复");
    }
    /** Caller consent is a UI obligation, not something this backend can prove.
     * Owner/session identity and single-attempt consumption prevent stale token reuse.
     * Final comparison and replacement share ONE write transaction, not a TOCTOU check.
     * Legacy restoreBackup remains a lower-level adapter and bypasses this preview API;
     * future user-facing restoration MUST use this guarded path instead.
     */
    public synchronized void confirmRestore(RestorePlan plan,MediaRepository media)throws IOException{
        if(plan==null||plan.owner!=this)throw new IllegalArgumentException("恢复预览不属于当前数据库");
        if(plan.terminal||plan.session!=restoreSession)throw new IllegalStateException("恢复预览已取消、使用或失效，请重新预览");
        plan.terminal=true;
        if(plan.upgraded!=null){try{schema3.confirmRestore(plan.upgraded,media);}finally{plan.upgraded.close();}return;}
        try(BackupArchive.Snapshot snapshot=plan.snapshot;SQLiteDatabase staged=candidate(plan.expected)){
            if(media==null)throw new IllegalArgumentException("媒体仓库不能为空");
            // Early read avoids unnecessary publication for already stale plans. It is
            // NOT the safety boundary: repeat inside the actual replacement transaction.
            tx(db->{unchanged(db,plan);return null;});
            Map<String,Long> registry=validateFiles(staged,snapshot);Map<String,Path> files=snapshot.assets();
            for(String id:registry.keySet())try(InputStream in=Files.newInputStream(files.get(id),StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){
                if(!media.copy(in).equals(id))throw new IOException("预览媒体已变化，拒绝恢复");
            }
            snapshot.close();
            for(Map.Entry<String,Long> item:registry.entrySet()){media.verify(item.getKey());if(Files.size(media.path(item.getKey()))!=item.getValue())throw new IOException("恢复媒体回读大小不一致");}
            tx(db->{unchanged(db,plan);deleteRows(db);copyRows(staged,db);require(Arrays.equals(encodeState(db),plan.expected),"恢复事务回读不一致");return null;});
        }
    }
}
