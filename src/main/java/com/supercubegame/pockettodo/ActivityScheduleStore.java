package com.supercubegame.pockettodo;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;

/** Opt-in isolated v5 workspaces only. No live name, implicit migration, sidecar rule or
 * replacement of an existing store. Every imported workspace owns its database and media.
 * Public UI activation, automatic cleanup after abrupt process loss and release are not part of this layer. */
public final class ActivityScheduleStore implements AutoCloseable {
    static final String DDL="CREATE TABLE activity_schedules(activity_id INTEGER PRIMARY KEY REFERENCES activities(id) CHECK(activity_id>0),days INTEGER NOT NULL CHECK(days BETWEEN 1 AND 127),first_day TEXT NOT NULL,last_day TEXT,zone_id TEXT NOT NULL)";
    private final Path dir;private final SQLiteDatabase db;private final MediaRepository media;private boolean closed;
    private ActivityScheduleStore(Path dir,SQLiteDatabase db,MediaRepository media){this.dir=dir;this.db=db;this.media=media;}
    boolean ownsDirectory(Path expected){return dir.equals(expected);}
    public String key(){return dir.getFileName().toString();}
    private static void need(boolean b,String m){if(!b)throw new IllegalStateException(m);}
    private static Path parent(Context c)throws IOException{
        Path p=c.getApplicationContext().getDir("activity-schedule-preview",Context.MODE_PRIVATE).toPath();
        if(!Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS))throw new IOException("Invalid private schedule directory");return p.toRealPath();}
    private static void schema(SQLiteDatabase d){Schema3Store.createSchema3(d);d.execSQL(Schema4Store.SHORTCUT_DDL);d.execSQL(DDL);d.setVersion(5);}
    private static List<String> signature(SQLiteDatabase d){List<String> out=new ArrayList<>();try(Cursor c=d.rawQuery("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name",null)){
        while(c.moveToNext()){String n=c.getString(1);if(n.equals("android_metadata")||n.startsWith("sqlite_"))continue;for(int i=0;i<4;i++)out.add(c.getString(i));}}return out;}
    private static void layout(SQLiteDatabase d){need(d.getVersion()==5,"Not a schedule workspace");try(SQLiteDatabase sample=SQLiteDatabase.create(null)){sample.setForeignKeyConstraintsEnabled(true);schema(sample);need(signature(sample).equals(signature(d)),"Unexpected schedule table layout");}
        try(Cursor c=d.rawQuery("PRAGMA foreign_key_check",null)){need(!c.moveToFirst(),"Foreign schedule or historical owner");}}
    private static void outside(SQLiteDatabase d){need(d.isOpen()&&!d.inTransaction(),"Independent schedule transaction required");}
    private void live(){need(!closed&&db.isOpen(),"Schedule workspace closed");}
    private static long revision(SQLiteDatabase d){try(Cursor c=d.rawQuery("SELECT value FROM revision WHERE id=1",null)){need(c.moveToFirst(),"Missing revision");return c.getLong(0);}}
    private static ActivitySchedule row(Cursor c,int i){need(c.getType(i)==Cursor.FIELD_TYPE_INTEGER&&c.getLong(i)>=1&&c.getLong(i)<=127&&c.getType(i+1)==Cursor.FIELD_TYPE_STRING&&(c.isNull(i+2)||c.getType(i+2)==Cursor.FIELD_TYPE_STRING)&&c.getType(i+3)==Cursor.FIELD_TYPE_STRING,"Invalid stored schedule types");return new ActivitySchedule(c.getInt(i),c.getString(i+1),c.isNull(i+2)?null:c.getString(i+2),c.getString(i+3));}
    private static SortedMap<Long,ActivitySchedule> rows(SQLiteDatabase d){TreeMap<Long,ActivitySchedule> m=new TreeMap<>();try(Cursor c=d.rawQuery("SELECT activity_id,days,first_day,last_day,zone_id FROM activity_schedules ORDER BY activity_id",null)){
        while(c.moveToNext()){long id=c.getLong(0);need(c.getType(0)==Cursor.FIELD_TYPE_INTEGER&&id>0&&m.put(id,row(c,1))==null,"Invalid schedule identity");}}return m;}
    private static void put(SQLiteDatabase d,long id,ActivitySchedule v){d.execSQL("INSERT INTO activity_schedules(activity_id,days,first_day,last_day,zone_id) VALUES(?,?,?,?,?)",new Object[]{id,v.days,v.first.toString(),v.last==null?null:v.last.toString(),v.zone.getId()});}
    private static boolean archived(SQLiteDatabase d,long id){need(id>0,"Invalid activity ID");try(Cursor c=d.rawQuery("SELECT archived FROM activities WHERE id=?",new String[]{Long.toString(id)})){need(c.moveToFirst(),"Missing schedule activity");return c.getInt(0)!=0;}}
    private static byte[] snapshot(SQLiteDatabase d){layout(d);return ActivitySchedule.Wire.write(Schema4Store.scheduleProjection(d),rows(d));}
    public synchronized ActivitySchedule rule(long id){live();archived(db,id);try(Cursor c=db.rawQuery("SELECT days,first_day,last_day,zone_id FROM activity_schedules WHERE activity_id=?",new String[]{Long.toString(id)})){return c.moveToFirst()?row(c,0):null;}}
    public synchronized boolean dueAt(long id,Instant moment){live();Objects.requireNonNull(moment);try(Cursor c=db.rawQuery("SELECT a.archived,s.days,s.first_day,s.last_day,s.zone_id FROM activities a LEFT JOIN activity_schedules s ON s.activity_id=a.id WHERE a.id=?",new String[]{Long.toString(id)})){need(id>0&&c.moveToFirst(),"Missing schedule activity");return c.getInt(0)==0&&!c.isNull(1)&&row(c,1).dueAt(moment);}}
    /** This list belongs only to this private copy. No note, field, mark or ledger content is queried. */
    static final class BookRow {
        final ActivityScheduleStore owner; final long id,category; final String title,categoryName; final boolean archived; final ActivitySchedule rule;
        BookRow(ActivityScheduleStore s,Cursor c){owner=s;id=c.getLong(0);title=c.getString(1);category=c.getLong(2);categoryName=c.getString(3);archived=c.getInt(4)!=0;rule=c.isNull(5)?null:row(c,5);}
        String identity(){return title+" · #"+id+"\n"+categoryName+" · 分类 #"+category;}
        boolean same(BookRow r){return r!=null&&owner==r.owner&&id==r.id&&category==r.category&&title.equals(r.title)&&categoryName.equals(r.categoryName)&&archived==r.archived&&Objects.equals(rule,r.rule);}
    }
    static final class BookPage {final List<BookRow> items;final boolean more;BookPage(List<BookRow> r,boolean b){items=Collections.unmodifiableList(r);more=b;}}
    private static final String BOOK_SELECT="SELECT a.id,a.title,c.id,c.name,a.archived,s.days,s.first_day,s.last_day,s.zone_id FROM activities a JOIN categories c ON c.id=a.category_id LEFT JOIN activity_schedules s ON s.activity_id=a.id ";
    synchronized BookPage page(long after,boolean today,Instant at){live();need(after>=0&&at!=null,"Invalid book page");List<BookRow> rows=new ArrayList<>();
        try(Cursor c=db.rawQuery(BOOK_SELECT+"WHERE a.id>? "+(today?"AND a.archived=0 AND s.activity_id IS NOT NULL ":"")+"ORDER BY a.id"+(today?"":" LIMIT 25"),new String[]{Long.toString(after)})){
            while(c.moveToNext()){BookRow r=new BookRow(this,c);if(today&&(r.rule==null||!r.rule.dueAt(at)))continue;if(rows.size()==24)return new BookPage(rows,true);rows.add(r);}return new BookPage(rows,false);}}
    synchronized Review reviewShown(BookRow shown,ActivitySchedule proposed){need(shown!=null&&shown.owner==this,"Foreign displayed row");return reviewChecked(shown.id,shown,proposed);}
    synchronized int[] bookCounts(){live();int[] out=new int[3];try(Cursor c=db.rawQuery("SELECT (SELECT count(*) FROM activities),(SELECT count(*) FROM activity_schedules),(SELECT count(*) FROM media)",null)){need(c.moveToFirst(),"Missing counts");for(int i=0;i<3;i++)out[i]=c.getInt(i);}return out;}
    synchronized byte[] verifiedBookState()throws IOException{byte[] b=state();SortedMap<String,Long> assets=mediaRows(db);for(Map.Entry<String,Long> e:assets.entrySet()){media.verify(e.getKey());need(Files.size(media.path(e.getKey()))==e.getValue(),"Media length changed");}return b;}
    public static final class Review implements AutoCloseable{
        private final ActivityScheduleStore owner;public final long activity;public final ActivitySchedule previous,proposed;private byte[] before;
        private Review(ActivityScheduleStore o,long id,ActivitySchedule old,ActivitySchedule next,byte[] state){owner=o;activity=id;previous=old;proposed=next;before=state;}
        @Override public void close(){synchronized(owner){before=null;}}
    }
    /** null means explicitly review clearing the rule. It does not remove check-ins or ledger. */
    public synchronized Review review(long id,ActivitySchedule proposed){return reviewChecked(id,null,proposed);}
    private Review reviewChecked(long id,BookRow shown,ActivitySchedule proposed){live();outside(db);db.beginTransaction();try{
        if(shown!=null){try(Cursor c=db.rawQuery(BOOK_SELECT+"WHERE a.id=?",new String[]{Long.toString(id)})){need(c.moveToFirst()&&shown.same(new BookRow(this,c)),"Displayed activity or schedule changed");}}
        need(!archived(db,id),"Archived activity is read only");Review p=new Review(this,id,rule(id),proposed,snapshot(db));db.setTransactionSuccessful();return p;
    }finally{db.endTransaction();}}
    public synchronized boolean confirm(Review p){need(p!=null&&p.owner==this,"Foreign schedule review");byte[] expected=p.before;need(expected!=null,"Schedule review expired");p.before=null;live();outside(db);db.beginTransaction();try{
        byte[] actual=snapshot(db);need(Arrays.equals(expected,actual)&&!archived(db,p.activity),"Schedule state changed; review again");
        if(Objects.equals(p.previous,p.proposed)){db.setTransactionSuccessful();return false;}
        ActivitySchedule.Wire prior=ActivitySchedule.Wire.read(actual);TreeMap<Long,ActivitySchedule> after=new TreeMap<>(prior.rules);long rev=revision(db),next=Math.incrementExact(rev);byte[] expectedBase;
        // Independent strict historical candidate: only its single revision cell may change.
        try(SQLiteDatabase copy=Schema4Store.stateCandidate(prior.base)){copy.execSQL("UPDATE revision SET value=? WHERE id=1",new Object[]{next});expectedBase=Schema4Store.scheduleProjection(copy);}
        int n=db.delete("activity_schedules","activity_id=?",new String[]{Long.toString(p.activity)});need(n==(p.previous==null?0:1),"Schedule write count differs");
        if(p.proposed!=null){put(db,p.activity,p.proposed);after.put(p.activity,p.proposed);}else after.remove(p.activity);
        db.execSQL("UPDATE revision SET value=? WHERE id=1 AND value=?",new Object[]{next,rev});
        need(Arrays.equals(ActivitySchedule.Wire.write(expectedBase,after),snapshot(db)),"Schedule transaction changed other data");db.setTransactionSuccessful();return true;
    }finally{db.endTransaction();}}
    public synchronized byte[] state(){live();outside(db);db.beginTransaction();try{byte[] x=snapshot(db);db.setTransactionSuccessful();return x;}finally{db.endTransaction();}}
    private static SortedMap<String,Long> mediaRows(SQLiteDatabase base){TreeMap<String,Long> m=new TreeMap<>();try(Cursor c=base.rawQuery("SELECT id,bytes FROM media ORDER BY id",null)){while(c.moveToNext()){String id=c.getString(0);long n=c.getLong(1);MediaRepository.validId(id);need(n>0&&m.put(id,n)==null,"Invalid media registry");}}return m;}
    public synchronized void exportBackup(Path destination)throws IOException{byte[] s=state();ActivitySchedule.Wire w=ActivitySchedule.Wire.read(s);try(SQLiteDatabase base=Schema4Store.stateCandidate(w.base)){
        SortedMap<String,Long> assets=mediaRows(base);for(Map.Entry<String,Long> e:assets.entrySet()){String id=e.getKey();media.verify(id);need(Files.size(media.path(id))==e.getValue(),"Registered media length differs");}
        BackupArchive.write(destination,s,assets.keySet(),media);
    }}
    /** The caller must explicitly choose a full archive. Always materializes a fresh, private workspace;
     * neither a filename from the ZIP nor a live application database can be chosen as destination. */
    public static ActivityScheduleStore importCopy(Context ctx,Path archive,long budget)throws IOException{
        return importFresh(parent(ctx).resolve("sched-"+UUID.randomUUID()),archive,budget);}
    static ActivityScheduleStore importFresh(Path vacant,Path archive,long budget)throws IOException{
        Path dir=Files.createDirectory(vacant);SQLiteDatabase dest=null;boolean success=false;
        try{Path stages=Files.createDirectory(dir.resolve("staging"));MediaRepository media=new MediaRepository(dir.resolve("media"),budget);
            try(BackupArchive.Snapshot archiveCopy=BackupArchive.read(archive,stages,budget)){
                byte[] input=archiveCopy.state();need(input.length>=12&&ByteBuffer.wrap(input).getInt()==ActivitySchedule.Wire.MAGIC,"Invalid archive state");
                int wire=ByteBuffer.wrap(input).getInt(4);ActivitySchedule.Wire w=wire==4?ActivitySchedule.Wire.read(input):null;
                try(SQLiteDatabase base=Schema4Store.stateCandidate(w==null?input:w.base)){
                    SortedMap<String,Long> assets=mediaRows(base);need(assets.keySet().equals(archiveCopy.assets().keySet()),"Unexpected or missing media");
                    for(Map.Entry<String,Long> e:assets.entrySet()){String id=e.getKey();Path file=archiveCopy.assets().get(id);need(Files.size(file)==e.getValue(),"Archive media length differs");try(InputStream in=Files.newInputStream(file,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){need(id.equals(media.copy(in)),"Archive media differs");}media.verify(id);}
                    SortedMap<Long,ActivitySchedule> rules=w==null?new TreeMap<>():w.rules;byte[] expected=ActivitySchedule.Wire.write(Schema4Store.scheduleProjection(base),rules);
                    if(w!=null)need(Arrays.equals(expected,input),"Historical schedule archive differs");
                    dest=SQLiteDatabase.openOrCreateDatabase(dir.resolve("data.db").toFile(),null);dest.setForeignKeyConstraintsEnabled(true);dest.beginTransaction();try{
                        schema(dest);Schema4Store.seedFreshScheduleCopy(dest,base);for(Map.Entry<Long,ActivitySchedule> e:rules.entrySet())put(dest,e.getKey(),e.getValue());
                        need(Arrays.equals(expected,snapshot(dest)),"Imported schedules differ");dest.setTransactionSuccessful();
                    }finally{dest.endTransaction();}
                }
            }
            ActivityScheduleStore result=new ActivityScheduleStore(dir,dest,media);success=true;return result;
        }finally{if(!success){try{if(dest!=null)dest.close();}finally{BackupArchive.deleteTree(dir);}}}
    }
    public static ActivityScheduleStore reopen(Context ctx,String key,long budget)throws IOException{
        need(key!=null&&key.matches("sched-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),"Unknown schedule workspace key");return openOwned(parent(ctx).resolve(key),budget);}
    static ActivityScheduleStore openOwned(Path dir,long budget)throws IOException{Path f=dir.resolve("data.db"),m=dir.resolve("media");
        need(Files.isDirectory(dir,LinkOption.NOFOLLOW_LINKS)&&Files.isRegularFile(f,LinkOption.NOFOLLOW_LINKS)&&Files.size(f)>0&&Files.isDirectory(m,LinkOption.NOFOLLOW_LINKS),"Existing schedule workspace required");
        SQLiteDatabase d=SQLiteDatabase.openDatabase(f.toString(),null,SQLiteDatabase.OPEN_READWRITE);boolean ok=false;try{d.setForeignKeyConstraintsEnabled(true);ActivityScheduleStore store=new ActivityScheduleStore(dir,d,new MediaRepository(m,budget));store.state();ok=true;return store;}finally{if(!ok)d.close();}}
    @Override public synchronized void close(){if(!closed){closed=true;db.close();}}
}
