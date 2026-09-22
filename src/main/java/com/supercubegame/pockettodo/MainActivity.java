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
    static final int EXPORT_BACKUP=41, IMPORT_BACKUP=42, PICK_NOTE_IMAGE=43;
    private TodayScreen screen;
    private java.util.function.Consumer<Uri> pendingImage;
    @Override public void onCreate(Bundle saved){super.onCreate(saved);screen=new TodayScreen(this);screen.show(saved);}
    @Override protected void onSaveInstanceState(Bundle out){if(screen!=null)screen.save(out);super.onSaveInstanceState(out);}
    @Override public void onBackPressed(){if(screen==null||!screen.back())super.onBackPressed();}
    @Override protected void onDestroy(){pendingImage=null;if(screen!=null)screen.close();super.onDestroy();}
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
