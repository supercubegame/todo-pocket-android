package com.supercubegame.pockettodo;

import android.content.Context;
import android.graphics.Bitmap;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Build;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/** Isolated app-private fixtures; no external picker, user photo, live DB or low-disk simulation. */
final class NoteImageImportChecks {
    private NoteImageImportChecks(){}
    private static void need(boolean b,String why){if(!b)throw new AssertionError(why);}
    private static byte[] png(int color)throws IOException{Bitmap b=Bitmap.createBitmap(12,8,Bitmap.Config.ARGB_8888);try{b.eraseColor(color);ByteArrayOutputStream o=new ByteArrayOutputStream();if(!b.compress(Bitmap.CompressFormat.PNG,100,o))throw new IOException("fixture");return o.toByteArray();}finally{b.recycle();}}
    interface Operation{void go()throws Exception;}
    private static void refused(NoteImageImport.Reason reason,Operation op)throws Exception{try{op.go();}catch(NoteImageImport.Problem p){need(p.reason==reason,"wrong refusal, not a witness");return;}throw new AssertionError("missing refusal");}
    private static void empty(Path dir)throws IOException{try(DirectoryStream<Path>s=Files.newDirectoryStream(dir)){need(!s.iterator().hasNext(),"staging residue");}}
    private static void fixtureVersion(Context c,int v,String nonce,NoteImageImport.Stored a,NoteImageImport.Stored b)throws Exception{
        String n="ci-attach-"+nonce+"-v"+v+".db";File path=c.getDatabasePath(n);
        need(!path.exists()&&!new File(path+"-wal").exists()&&!new File(path+"-shm").exists()&&!new File(path+"-journal").exists(),"preserve preexisting fixture");
        byte[] finalState;try(AppDatabase db=open(c,v,n)){
            db.addCategory(1,"fixtures");db.addActivity(11,1,0,"first");db.addActivity(12,1,0,"second");db.addActivity(13,1,0,"empty");
            db.createNote("n",11,"same");db.createNote("other",12,"same");db.registerMedia(a.id,a.mime,a.size);
            db.saveNote("n",Collections.singletonList(NoteDocument.Block.text("old","text",false)));db.saveNote("other",Collections.singletonList(NoteDocument.Block.image("shared",a.id,"unchanged",true)));
            byte[] before;List<NoteDocument.Block> old=db.noteBlocks("n");List<NoteDocument.Block> latest=Arrays.asList(NoteDocument.Block.text("old","text",true),NoteDocument.Block.text("new","later",false));db.saveNote("n",latest);before=db.exportState();
            refused(NoteImageImport.Reason.STALE,()->NoteImageImport.append(db,11,"same","n",old,b.id,b.mime,b.size));need(Arrays.equals(before,db.exportState()),"stale contents overwritten");
            refused(NoteImageImport.Reason.STALE,()->NoteImageImport.append(db,11,"same","other",db.noteBlocks("other"),b.id,b.mime,b.size));need(Arrays.equals(before,db.exportState()),"foreign owner changed");
            NoteImageImport.preflight(db,13,null,Collections.emptyList());db.createNote("new-first",13,"same");before=db.exportState();refused(NoteImageImport.Reason.STALE,()->NoteImageImport.append(db,13,"same",null,Collections.emptyList(),b.id,b.mime,b.size));need(Arrays.equals(before,db.exportState()),"duplicate first note");
            db.addActivity(14,1,0,"rollback-first");SQLiteDatabase s=db.getWritableDatabase();s.execSQL("CREATE TEMP TRIGGER attach_fail BEFORE INSERT ON blocks WHEN NEW.kind='IMAGE' AND NEW.note_id<>'other' BEGIN SELECT RAISE(ABORT,'synthetic-attach-late'); END");
            try{for(boolean initiallyEmpty:new boolean[]{false,true}){byte[] pre=db.exportState();boolean rejection=false;try{NoteImageImport.append(db,initiallyEmpty?14:11,"same",initiallyEmpty?null:"n",initiallyEmpty?Collections.emptyList():latest,b.id,b.mime,b.size);}catch(RuntimeException controlled){for(Throwable x=controlled;x!=null;x=x.getCause())if(x.getMessage()!=null&&x.getMessage().contains("synthetic-attach-late"))rejection=true;}
                need(rejection&&Arrays.equals(pre,db.exportState()),"late failure either not reached or changed DB");}}
            finally{s.execSQL("DROP TRIGGER attach_fail");}
            NoteImageImport.append(db,11,"same","n",latest,a.id,a.mime,a.size);List<NoteDocument.Block> now=db.noteBlocks("n");need(now.size()==3&&now.get(0).privateContent&&now.get(1).id.equals("new")&&now.get(2).assetId.equals(a.id)&&db.count("media")==1,"current note/shared asset");
            NoteImageImport.append(db,14,"new",null,Collections.emptyList(),b.id,b.mime,b.size);need(db.count("media")==2&&db.count("notes")==4,"first note or registration missing");finalState=db.exportState();}
        try(AppDatabase reopened=open(c,v,n)){need(Arrays.equals(finalState,reopened.exportState()),"independent reopen");List<NoteDocument.Block> sib=reopened.noteBlocks("other");need(sib.size()==1&&sib.get(0).assetId.equals(a.id)&&sib.get(0).privateContent&&sib.get(0).caption.equals("unchanged"),"sibling changed");}
    }
    private static AppDatabase open(Context c,int v,String n){return v==2?new AppDatabase(c,n):v==3?AppDatabase.openSchema3(c,n):AppDatabase.openSchema4(c,n);}
    static void run(Context c,int api,String nonce,StringBuilder log)throws Exception{
        need((api==26||api==34)&&Build.VERSION.SDK_INT==api&&"ranchu".equals(Build.HARDWARE)&&"com.supercubegame.pockettodo.v12.preview".equals(c.getPackageName())&&nonce!=null&&nonce.matches("[0-9]{1,20}-[1-9][0-9]{0,3}-"+api),"owned disposable emulator only");
        Path root=Files.createDirectory(c.getFilesDir().toPath().resolve("ci-img-attach-"+nonce)),cache=Files.createDirectory(root.resolve("stage"));MediaRepository media=new MediaRepository(root.resolve("media"),1048576);byte[] A=png(0xff057135),B=png(0xffbfc9ee);log.append("ATTACH_SCOPE api=").append(api).append(" nonce=").append(nonce).append(" package=").append(c.getPackageName()).append(" hardware=ranchu synthetic=true\n");
        NoteImageImport.Stored a=NoteImageImport.stage(cache,()->new ByteArrayInputStream(A),NoteEditorScreen::checkedImageMime,media,8388608),b=NoteImageImport.stage(cache,()->new ByteArrayInputStream(B),NoteEditorScreen::checkedImageMime,media,8388608);need(!a.id.equals(b.id)&&a.id.equals(MediaRepository.digest(A))&&b.id.equals(MediaRepository.digest(B)),"distinct source samples");empty(cache);
        refused(NoteImageImport.Reason.READ,()->NoteImageImport.stage(cache,()->new InputStream(){int i;public int read(byte[] dst,int off,int len)throws IOException{if(i++!=0)throw new IOException("controlled source read");dst[off]=1;return 1;}public int read(){throw new AssertionError();}},NoteEditorScreen::checkedImageMime,media,8388608));empty(cache);
        refused(NoteImageImport.Reason.FORMAT,()->NoteImageImport.stage(cache,()->new ByteArrayInputStream(A),NoteEditorScreen::checkedImageMime,media,2));refused(NoteImageImport.Reason.FORMAT,()->NoteImageImport.stage(cache,()->new ByteArrayInputStream(new byte[]{1,2,3}),NoteEditorScreen::checkedImageMime,media,8388608));empty(cache);
        Path blocked=Files.createFile(root.resolve("not-directory"));refused(NoteImageImport.Reason.STORE,()->NoteImageImport.stage(blocked,()->{throw new AssertionError("source after refused staging");},NoteEditorScreen::checkedImageMime,media,8388608));need(Files.size(blocked)==0,"sentinel changed");
        log.append("ATTACH_NATIVE original_bytes_picker_read_format_and_local_staging_failures PASS\n");
        for(int v:new int[]{2,3,4}){fixtureVersion(c,v,nonce,a,b);media.verify(a.id);media.verify(b.id);need(Arrays.equals(A,Files.readAllBytes(media.path(a.id)))&&Arrays.equals(B,Files.readAllBytes(media.path(b.id))),"file altered");log.append("ATTACH_NATIVE v").append(v).append("_stale_owner_first_note_late_rollback_and_reopen PASS\n");}
    }
}
