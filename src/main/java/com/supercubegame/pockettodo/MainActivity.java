package com.supercubegame.pockettodo;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

/** Isolated native v1.2 workbench. Does not read or overwrite v1.0/v1.1 storage. */
public final class MainActivity extends Activity {
    static final int EXPORT_BACKUP=41, IMPORT_BACKUP=42, PICK_NOTE_IMAGE=43, EXPORT_NOTES=44;
    private TodayScreen screen;
    private java.util.function.Consumer<Uri> pendingImage;
    private ShareTicket pendingShare;
    private final java.util.List<android.app.AlertDialog> shareDialogs=new java.util.ArrayList<>();
    private boolean sharing;
    @Override public void onCreate(Bundle saved){super.onCreate(saved);screen=new TodayScreen(this);screen.show(saved);}
    @Override protected void onSaveInstanceState(Bundle out){if(screen!=null)screen.save(out);super.onSaveInstanceState(out);}
    @Override public void onBackPressed(){if(screen==null||!screen.back())super.onBackPressed();}
    @Override protected void onDestroy(){
        pendingImage=null;
        if(pendingShare!=null){pendingShare.close();pendingShare=null;}
        for(android.app.AlertDialog d:new java.util.ArrayList<>(shareDialogs))d.dismiss();
        shareDialogs.clear();
        if(screen!=null)screen.close();super.onDestroy();
    }
    /** In-memory, single-use consent boundary. Not restored after recreation.
     * Full-state equality includes privacy and changes without a revision bump. */
    static final class ShareTicket implements AutoCloseable {
        private byte[] state,zip;
        ShareTicket(byte[] state,byte[] zip){
            if(state==null||zip==null||state.length==0||state.length>8388608||zip.length==0||zip.length>16777216)
                throw new IllegalArgumentException("Share ticket budget");
            this.state=state.clone();this.zip=zip.clone();
        }
        synchronized byte[] take(byte[] current){
            if(state==null)throw new IllegalStateException("Share preview expired");
            try{
                if(!java.util.Arrays.equals(state,current))throw new IllegalStateException("Share content changed");
                return zip.clone();
            }finally{close();}
        }
        @Override public synchronized void close(){state=null;zip=null;}
    }
    // END_SHARE_TICKET
    /** Stream completion is not provider atomicity: failures may leave partial files.
     * Factories are opened once, only after the caller has consumed valid consent.
     * Closing output must succeed BEFORE readback; every byte and EOF must match.
     */
    static final class VerifiedShareWrite {
        interface Output { java.io.OutputStream open() throws IOException; }
        interface Input { InputStream open() throws IOException; }
        static void write(byte[] bytes,Output output,Input input)throws IOException{
            if(bytes==null||bytes.length==0||bytes.length>16777216)throw new IOException("Share output budget");
            try(java.io.OutputStream out=output.open()){
                if(out==null)throw new IOException("No output stream");
                for(int offset=0;offset<bytes.length;){
                    int count=Math.min(16384,bytes.length-offset);
                    out.write(bytes,offset,count);offset+=count;
                }
            }
            try(InputStream in=input.open()){
                if(in==null)throw new IOException("No output readback");
                byte[] chunk=new byte[16384];int offset=0,n;
                while((n=in.read(chunk))!=-1){
                    if(n==0)throw new IOException("Output read made no progress");
                    if(n<0||n>chunk.length||n>bytes.length-offset)throw new IOException("Output length differs");
                    for(int i=0;i<n;i++)if(chunk[i]!=bytes[offset+i])throw new IOException("Output bytes differ");
                    offset+=n;
                }
                if(offset!=bytes.length)throw new IOException("Output truncated");
            }
        }
    }
    // END_VERIFIED_SHARE_WRITE
    private static final class ShareChoice {
        byte[] state;String note;
        final java.util.List<NoteDocument.Block> blocks=new java.util.ArrayList<>();
    }
    /** Explicit one-note/block slice; no ledger, backup or origin assets are selected. */
    void openNoteShare(){
        if(sharing||pendingShare!=null)return;
        sharing=true;
        screen.work(()->{
            java.util.List<String[]> notes=new java.util.ArrayList<>();
            try(android.database.Cursor c=screen.db.getReadableDatabase().rawQuery(
                "SELECT n.id,n.title,a.title FROM notes n JOIN activities a ON a.id=n.activity_id ORDER BY n.rowid",null)){
                while(c.moveToNext()){
                    if(notes.size()==1000)throw new IOException("Too many notes");
                    notes.add(new String[]{c.getString(0),c.getString(1),c.getString(2)});
                }
            }
            return notes;
        },notes->{
            sharing=false;
            if(notes.isEmpty()){screen.message("没有可导出的笔记",false);return;}
            String[] labels=new String[notes.size()];
            for(int i=0;i<labels.length;i++)labels[i]=(i+1)+". "+shortLabel(notes.get(i)[2])+" / "+shortLabel(notes.get(i)[1]);
            android.app.AlertDialog d=new android.app.AlertDialog.Builder(this).setTitle("导出哪篇笔记？")
                .setItems(labels,(dialog,which)->loadShareChoice(notes.get(which)[0])).setNegativeButton("取消",null).create();
            showShareDialog(d);
        },()->{sharing=false;screen.message("无法读取笔记列表；超过1000篇时请先缩小数据范围",true);});
    }
    private static String shortLabel(String value){return value.length()>80?value.substring(0,80)+"…":value;}
    private void showShareDialog(android.app.AlertDialog d){
        shareDialogs.add(d);d.setOnDismissListener(unused->shareDialogs.remove(d));d.show();
    }
    private void loadShareChoice(String note){
        screen.work(()->{
            synchronized(screen.db){
                android.database.sqlite.SQLiteDatabase sql=screen.db.getWritableDatabase();
                sql.beginTransaction();
                try{
                    ShareChoice choice=new ShareChoice();choice.note=note;choice.state=screen.db.exportState();
                    try(android.database.Cursor c=sql.rawQuery("SELECT id FROM notes WHERE id=?",new String[]{note})){
                        if(!c.moveToFirst())throw new IOException("Note disappeared");
                    }
                    for(NoteDocument.Block b:screen.db.noteBlocks(note)){
                        if(b.privateContent)continue; // Before touching any image bytes.
                        if(choice.blocks.size()==1000)throw new IOException("Too many blocks");
                        choice.blocks.add(b);
                    }
                    sql.setTransactionSuccessful();return choice;
                }finally{sql.endTransaction();}
            }
        },this::selectShareBlocks,()->screen.message("无法读取这篇笔记，请重新选择",true));
    }
    private void selectShareBlocks(ShareChoice choice){
        if(choice.blocks.isEmpty()){screen.message("这篇笔记没有非私有内容可导出",false);return;}
        String[] labels=new String[choice.blocks.size()];boolean[] checked=new boolean[labels.length];
        for(int i=0;i<labels.length;i++){
            NoteDocument.Block b=choice.blocks.get(i);
            labels[i]=(i+1)+". "+(b.kind==NoteDocument.Kind.TEXT?"文字："+shortLabel(b.text):"图片："+shortLabel(b.caption));
        }
        android.app.AlertDialog d=new android.app.AlertDialog.Builder(this).setTitle("勾选内容（私有项已排除）")
            .setMultiChoiceItems(labels,checked,(dialog,which,value)->checked[which]=value)
            .setNegativeButton("取消",null).setPositiveButton("生成预览",null).create();
        d.setOnShowListener(unused->d.getButton(android.app.AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            java.util.Set<String> selected=new java.util.LinkedHashSet<>();
            for(int i=0;i<checked.length;i++)if(checked[i])selected.add(choice.blocks.get(i).id);
            if(selected.isEmpty()){screen.message("请至少勾选一项；空选不会导出全部内容",true);return;}
            d.dismiss();screen.work(()->prepareShare(choice,selected),this::previewShare,
                ()->screen.message("导出预览失败：内容可能已变化，或图片超出处理限制；请重新选择",true));
        }));
        showShareDialog(d);
    }
    private byte[][] prepareShare(ShareChoice choice,java.util.Set<String> selected)throws IOException{
        synchronized(screen.db){
            android.database.sqlite.SQLiteDatabase sql=screen.db.getWritableDatabase();sql.beginTransaction();
            try{
                if(!java.util.Arrays.equals(choice.state,screen.db.exportState()))throw new IOException("Selection changed");
                MediaRepository media=new MediaRepository(getFilesDir().toPath().resolve("media"),64L*1024*1024);
                java.util.List<ShareExporter.MarkdownItem> items=new java.util.ArrayList<>();
                java.util.Set<String> keys=new java.util.LinkedHashSet<>();long bytes=0;
                for(NoteDocument.Block b:choice.blocks){
                    if(!selected.contains(b.id)||b.privateContent)continue;
                    byte[] image=null;
                    if(b.kind==NoteDocument.Kind.IMAGE){
                        long size;
                        try(android.database.Cursor c=sql.rawQuery("SELECT bytes,mime FROM media WHERE id=?",new String[]{b.assetId})){
                            if(!c.moveToFirst()||!("image/png".equals(c.getString(1))||"image/jpeg".equals(c.getString(1))))throw new IOException("Missing image");
                            size=c.getLong(0);
                        }
                        if(size<=0||size>8388608||size>16777216-bytes)throw new IOException("Selected image byte budget");
                        bytes+=size;media.verify(b.assetId);
                        Path path=media.path(b.assetId);if(Files.size(path)!=size)throw new IOException("Image size changed");
                        image=new byte[(int)size];
                        try(java.io.DataInputStream in=new java.io.DataInputStream(Files.newInputStream(path,java.nio.file.LinkOption.NOFOLLOW_LINKS))){
                            in.readFully(image);if(in.read()!=-1)throw new IOException("Image grew");
                        }
                        if(!b.assetId.equals(MediaRepository.digest(image)))throw new IOException("Image changed");
                    }
                    items.add(new ShareExporter.MarkdownItem(choice.note,b.id,b.kind==NoteDocument.Kind.TEXT?b.text:null,image,b.caption,false));
                    keys.add(choice.note+"/"+b.id);
                }
                if(keys.size()!=selected.size())throw new IOException("Unknown selection");
                byte[] zip=ShareExporter.markdownZip(items,keys);
                sql.setTransactionSuccessful();return new byte[][]{choice.state,zip};
            }finally{sql.endTransaction();}
        }
    }
    /** Preview the actual ZIP text and newly encoded PNGs, never source/origin files. */
    private void previewShare(byte[][] prepared){
        ShareTicket ticket=new ShareTicket(prepared[0],prepared[1]);
        android.widget.LinearLayout body=screen.column();
        final java.util.List<android.graphics.Bitmap> images=new java.util.ArrayList<>();
        try(java.util.zip.ZipInputStream zip=new java.util.zip.ZipInputStream(new java.io.ByteArrayInputStream(prepared[1]))){
            java.util.zip.ZipEntry entry;long expanded=0,pixels=0;
            while((entry=zip.getNextEntry())!=null){
                java.io.ByteArrayOutputStream buffer=new java.io.ByteArrayOutputStream();byte[] chunk=new byte[16384];int n;
                while((n=zip.read(chunk))!=-1){if(n==0||n>16777216-expanded)throw new IOException("Preview budget");expanded+=n;buffer.write(chunk,0,n);}
                byte[] data=buffer.toByteArray();
                if("notes.md".equals(entry.getName()))body.addView(screen.text(new String(data,java.nio.charset.StandardCharsets.UTF_8),16,TodayScreen.INK));
                else{
                    android.graphics.BitmapFactory.Options o=new android.graphics.BitmapFactory.Options();o.inJustDecodeBounds=true;
                    android.graphics.BitmapFactory.decodeByteArray(data,0,data.length,o);o.inJustDecodeBounds=false;o.inSampleSize=1;
                    if(o.outWidth<=0||o.outHeight<=0)throw new IOException("Invalid preview");
                    while(o.outWidth/o.inSampleSize>256||o.outHeight/o.inSampleSize>256)o.inSampleSize*=2;
                    android.graphics.Bitmap image=android.graphics.BitmapFactory.decodeByteArray(data,0,data.length,o);
                    if(image==null)throw new IOException("Invalid PNG preview");
                    images.add(image);pixels+=(long)image.getWidth()*image.getHeight();
                    if(pixels>4194304)throw new IOException("Preview image budget");
                    body.addView(screen.text(entry.getName(),14,TodayScreen.MUTED));
                    android.widget.ImageView view=new android.widget.ImageView(this);view.setImageBitmap(image);view.setAdjustViewBounds(true);body.addView(view);
                }
            }
        }catch(Exception e){ticket.close();for(android.graphics.Bitmap b:images)b.recycle();screen.message("预览无法完整显示，未导出；请减少选项",true);return;}
        body.addView(screen.text("以上是实际包内Markdown源码和图片缩略图。仅导出所选非私有内容；图片重新编码不等于自动脱敏。完整备份、账目和原图文件不在包内。",14,TodayScreen.MUTED));
        android.widget.CheckBox consent=new android.widget.CheckBox(this);consent.setText("我已核对内容与图片，可保存此包");body.addView(consent);
        android.widget.ScrollView scroll=new android.widget.ScrollView(this);scroll.addView(body);
        android.app.AlertDialog d=new android.app.AlertDialog.Builder(this).setTitle("Markdown图片包预览").setView(scroll)
            .setNegativeButton("取消",null).setPositiveButton("选择保存位置",null).create();
        shareDialogs.add(d);
        d.setOnDismissListener(unused->{shareDialogs.remove(d);if(pendingShare!=ticket)ticket.close();for(android.graphics.Bitmap b:images)b.recycle();});
        d.setOnShowListener(unused->d.getButton(android.app.AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            if(!consent.isChecked()){screen.message("请先核对并勾选确认",true);return;}
            if(pendingShare!=null)return;
            pendingShare=ticket;
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE);
            intent.putExtra(Intent.EXTRA_TITLE,"PocketTodo-notes.zip");
            try{startActivityForResult(intent,EXPORT_NOTES);d.dismiss();}
            catch(android.content.ActivityNotFoundException e){pendingShare=null;ticket.close();d.dismiss();screen.message("系统保存入口不可用，未导出",true);}
        }));d.show();
    }
    private void finishShare(int result,Intent data){
        final ShareTicket ticket=pendingShare;pendingShare=null;
        if(ticket==null){screen.message("页面已重建，请重新选择导出内容",true);return;}
        if(result!=RESULT_OK||data==null||data.getData()==null){ticket.close();screen.message("已取消导出，本机笔记未改变",false);return;}
        final Uri uri=data.getData();
        screen.work(()->{
            try{
                synchronized(screen.db){
                    android.database.sqlite.SQLiteDatabase sql=screen.db.getWritableDatabase();sql.beginTransaction();
                    try{
                        byte[] bytes=ticket.take(screen.db.exportState());
                        if(isDestroyed()||!"content".equals(uri.getScheme()))throw new IOException("Export owner/destination invalid");
                        // Hold the read snapshot's write lock through publication: another
                        // connection cannot alter privacy between validation and output.
                        VerifiedShareWrite.write(bytes,()->openDestination(uri),
                            ()->getContentResolver().openInputStream(uri));
                        sql.setTransactionSuccessful();
                    }finally{sql.endTransaction();}
                }
                return true;
            }finally{ticket.close();}
        },ignored->screen.message("Markdown图片包已保存，逐字节回读一致",false),
            ()->screen.message("导出未完成：预览过期或保存失败；本机笔记未改。目标可能留有空文件或部分文件，请检查",true));
    }
    /** Deliberately not restored across Activity recreation: never attach to a new owner.
     * The user selects again after recreation; no persistent URI grant or storage permission.
     */
    void chooseNoteImage(java.util.function.Consumer<Uri> callback){
        if(pendingImage!=null)return;
        pendingImage=callback;
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("image/*").addCategory(Intent.CATEGORY_OPENABLE);
        intent.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"image/png","image/jpeg"});
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try{startActivityForResult(intent,PICK_NOTE_IMAGE);}
        catch(android.content.ActivityNotFoundException e){pendingImage=null;screen.message("系统文件选择器不可用，笔记未改变",true);}
    }
    /** SAF only supplies the URI. Copying to private storage freezes the user's choice;
     * replacing/deleting the original later cannot change the preview being reviewed.
     * This is not crash/lifecycle cleanup for an abandoned preview.
     */
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(screen==null)return;
        if(request==EXPORT_NOTES){finishShare(result,data);return;}
        if(request==PICK_NOTE_IMAGE){
            java.util.function.Consumer<Uri> callback=pendingImage;pendingImage=null;
            if(callback==null){screen.message("页面已重建，请重新选择图片；笔记未改变",true);return;}
            callback.accept(result==RESULT_OK&&data!=null?data.getData():null);return;
        }
        if(request!=EXPORT_BACKUP&&request!=IMPORT_BACKUP)return;
        if(result!=RESULT_OK||data==null||data.getData()==null){screen.backupCancelled();return;}
        Uri uri=data.getData();
        try{
            if(request==EXPORT_BACKUP){
                // The archive writer deliberately refuses an existing destination, so the
                // temporary path must not exist yet. The validated archive is streamed to
                // the SAF destination only after it has been fully written and closed.
                Path dir=Files.createTempDirectory(getCacheDir().toPath(),"export-");
                Path temp=dir.resolve("backup.zip");
                try{
                    screen.exportBackup(temp);
                    try(InputStream in=Files.newInputStream(temp);java.io.OutputStream out=openDestination(uri)){
                        byte[] buffer=new byte[16384];int n;while((n=in.read(buffer))!=-1){if(n==0)throw new IOException("备份读取未取得进展");out.write(buffer,0,n);}
                    }
                    screen.backupExported();
                }finally{Files.deleteIfExists(temp);Files.deleteIfExists(dir);}
            }else if(request==IMPORT_BACKUP){
                Path chosen=Files.createTempFile(getCacheDir().toPath(),"chosen-",".zip");boolean success=false;
                try(InputStream in=getContentResolver().openInputStream(uri)){
                    if(in==null)throw new IOException("无法读取所选备份");
                    Files.copy(in,chosen,StandardCopyOption.REPLACE_EXISTING);screen.previewRestore(chosen);success=true;
                }finally{if(!success)Files.deleteIfExists(chosen);}
            }
        }catch(Exception e){screen.backupFailed(e);}
    }
    private java.io.OutputStream openDestination(Uri uri)throws IOException{
        java.io.OutputStream out=getContentResolver().openOutputStream(uri,"wt");
        if(out==null)throw new IOException("无法写入所选位置");return out;
    }
}
