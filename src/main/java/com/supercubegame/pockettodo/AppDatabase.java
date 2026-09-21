package com.supercubegame.pockettodo;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteConstraintException;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.util.*;

/** Local SQLite schema2. Every write is transactional, no destructive fallback.
 * Full DB/media backup restore and asynchronous UI integration remain separate work.
 */
public final class AppDatabase extends SQLiteOpenHelper {
    private interface Work<T> { T run(SQLiteDatabase db); }
    public AppDatabase(Context context,String name) {
        super(context.getApplicationContext(),validName(name),null,2);
        setWriteAheadLoggingEnabled(true);
    }
    private static String validName(String name) {
        if(name==null||!name.matches("[A-Za-z0-9_-]+\\.db"))throw new IllegalArgumentException("无效数据库文件名");return name;
    }
    @Override public void onConfigure(SQLiteDatabase db) {db.setForeignKeyConstraintsEnabled(true);}
    @Override public void onCreate(SQLiteDatabase db) {
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
        try{T result=action.run(db);db.setTransactionSuccessful();return result;}
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
    /** Registry only: caller must copy/verify files and validate actual image format. */
    public synchronized void registerMedia(String id,String mime,long bytes){MediaRepository.validId(id);String clean=text(mime);if(bytes<=0)throw new IllegalArgumentException("媒体大小无效");tx(db->{try(Cursor c=db.rawQuery("SELECT mime,bytes FROM media WHERE id=?",new String[]{id})){if(c.moveToFirst()){if(!clean.equals(c.getString(0))||bytes!=c.getLong(1))throw new IllegalStateException("媒体标识对应的元数据冲突");return null;}}db.execSQL("INSERT INTO media VALUES(?,?,?)",new Object[]{id,clean,bytes});bump(db);return null;});}
    public synchronized void saveNote(String id,List<NoteDocument.Block> blocks){Ledger.identifier(id);if(blocks==null||Ledger.hasNull(blocks))throw new IllegalArgumentException("缺少笔记内容");List<NoteDocument.Block> owned=new ArrayList<>(blocks);NoteDocument validator=new NoteDocument();for(NoteDocument.Block b:owned)validator.add(b);tx(db->{exists(db,"notes",id);db.delete("blocks","note_id=?",new String[]{id});for(int i=0;i<owned.size();i++){NoteDocument.Block b=owned.get(i);if(b.kind==NoteDocument.Kind.IMAGE)exists(db,"media",b.assetId);db.execSQL("INSERT INTO blocks VALUES(?,?,?,?,?,?,?,?)",new Object[]{id,b.id,i,b.kind.name(),b.text,b.kind==NoteDocument.Kind.IMAGE?b.assetId:null,b.caption,b.privateContent?1:0});}bump(db);return null;});}
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
}
