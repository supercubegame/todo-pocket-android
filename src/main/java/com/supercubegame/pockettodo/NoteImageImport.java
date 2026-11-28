package com.supercubegame.pockettodo;

import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Private image input for the ordinary editor. A staged immutable object is not a DB registration.
 * Never unlink a digest on DB failure: it may be shared by another note or an in-flight operation. */
final class NoteImageImport {
    private NoteImageImport(){}
    enum Reason {
        FORMAT("图片未加入：仅支持有效 PNG/JPEG，最大 8 MiB、2000 万像素、单边 16384"),
        READ("图片未加入：无法完整读取所选文件，请重新选择。"),
        STORE("图片未加入：无法完成本机暂存或校验，请检查存储后再试。"),
        TRANSFER("图片未加入：文件读取或暂存没有完成，请重新选择并检查本机存储。"),
        STALE("图片未加入：笔记内容或归属已变化，请重新打开笔记后再选图。"),
        WRITE("图片保存未确认，请重新打开笔记核对后再试。"),
        GENERATED("未能生成示例图片，笔记未修改。");
        final String text;Reason(String text){this.text=text;}
    }
    static final class Problem extends IOException {final Reason reason;Problem(Reason r){super(r.text);reason=r;}Problem(Reason r,Throwable e){super(r.text,e);reason=r;}}
    static String feedback(Throwable e){return (e instanceof Problem?((Problem)e).reason:Reason.WRITE).text;}
    interface Open{InputStream open()throws IOException;}
    interface Inspect{String checkedMime(Path p)throws IOException;}
    static final class Stored {final String id,mime;final long size;Stored(String id,String mime,long size){this.id=id;this.mime=mime;this.size=size;}}
    private static final class Mine implements AutoCloseable{
        final Path path;Mine(Path cache)throws Problem{try{path=Files.createTempFile(cache,"image-",".part");}catch(IOException|SecurityException e){throw new Problem(Reason.STORE,e);}}
        public void close()throws Problem{try{Files.deleteIfExists(path);}catch(IOException|SecurityException e){throw new Problem(Reason.STORE,e);}}
    }
    private static InputStream openSource(Open source)throws Problem{try{InputStream in=source.open();if(in==null)throw new IOException("no input");return in;}catch(IOException|SecurityException e){throw new Problem(Reason.READ,e);}}
    private static OutputStream openTemp(Path target)throws Problem{try{return Files.newOutputStream(target,StandardOpenOption.WRITE,StandardOpenOption.TRUNCATE_EXISTING,LinkOption.NOFOLLOW_LINKS);}catch(IOException|SecurityException e){throw new Problem(Reason.STORE,e);}}
    static Stored stage(Path cache,Open source,Inspect validator,MediaRepository media,long limit)throws Problem{
        // The temporary is closed before the caller may commit anything. A cleanup failure cannot turn a committed note into a retry prompt.
        try(Mine tmp=new Mine(cache)){
            long size=0;
            try(InputStream in=openSource(source);OutputStream out=openTemp(tmp.path)){
                byte[] buf=new byte[16384];for(;;){int n;
                    try{n=in.read(buf);}catch(IOException|SecurityException e){throw new Problem(Reason.READ,e);}
                    if(n==-1)break;if(n<=0||n>buf.length)throw new Problem(Reason.READ);
                    if(n>limit-size)throw new Problem(Reason.FORMAT);
                    try{out.write(buf,0,n);}catch(IOException|SecurityException e){throw new Problem(Reason.STORE,e);}size+=n;
                }
            }catch(Problem e){throw e;}catch(IOException|SecurityException e){throw new Problem(Reason.TRANSFER,e);}
            if(size==0)throw new Problem(Reason.FORMAT);
            try{String mime=validator.checkedMime(tmp.path);
                if(!("image/png".equals(mime)||"image/jpeg".equals(mime)))throw new Problem(Reason.FORMAT);
                try(InputStream in=Files.newInputStream(tmp.path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){return new Stored(media.copy(in),mime,size);}
            }catch(Problem e){throw e;}catch(IOException|SecurityException e){throw new Problem(Reason.STORE,e);}
        }
    }
    private static boolean same(List<NoteDocument.Block> shown,List<NoteDocument.Block> actual){
        if(shown==null||shown.size()!=actual.size())return false;for(int i=0;i<shown.size();i++){
            NoteDocument.Block a=shown.get(i),b=actual.get(i);if(a==null||!a.id.equals(b.id)||a.kind!=b.kind||!Objects.equals(a.text,b.text)||!Objects.equals(a.caption,b.caption)||!Objects.equals(a.assetId,b.assetId)||a.privateContent!=b.privateContent)return false;
        }return true;
    }
    private static void selection(AppDatabase db,SQLiteDatabase sql,long owner,String note,List<NoteDocument.Block> shown)throws Problem{
        if(note==null){try(Cursor c=sql.rawQuery("SELECT 1 FROM activities WHERE id=?",new String[]{Long.toString(owner)})){if(!c.moveToFirst())throw new Problem(Reason.STALE);}
            try(Cursor c=sql.rawQuery("SELECT 1 FROM notes WHERE activity_id=? LIMIT 1",new String[]{Long.toString(owner)})){
                if(shown==null||!shown.isEmpty()||c.moveToFirst())throw new Problem(Reason.STALE);}return;}
        try(Cursor c=sql.rawQuery("SELECT activity_id FROM notes WHERE id=?",new String[]{note})){if(!c.moveToFirst()||c.getLong(0)!=owner)throw new Problem(Reason.STALE);}
        if(!same(shown,db.noteBlocks(note)))throw new Problem(Reason.STALE);
    }
    /** An optimization only. The authoritative check below repeats in the same transaction as the write. */
    static void preflight(AppDatabase db,long owner,String note,List<NoteDocument.Block> shown)throws Problem{
        synchronized(db){selection(db,db.getReadableDatabase(),owner,note,shown);}
    }
    static void append(AppDatabase db,long owner,String title,String note,List<NoteDocument.Block> shown,String assetId,String mime,long size)throws Problem{
        synchronized(db){SQLiteDatabase sql=db.getWritableDatabase();if(sql.inTransaction())throw new Problem(Reason.WRITE);
            sql.beginTransaction();try{
                selection(db,sql,owner,note,shown);
                String target=note;if(target==null){target=UUID.randomUUID().toString();db.createNote(target,owner,title);}
                db.registerMedia(assetId,mime,size);
                List<NoteDocument.Block> next=new ArrayList<>(shown);next.add(NoteDocument.Block.image(UUID.randomUUID().toString(),assetId,"",false));
                db.saveNote(target,next);sql.setTransactionSuccessful();
            }finally{sql.endTransaction();}
        }
    }
}
