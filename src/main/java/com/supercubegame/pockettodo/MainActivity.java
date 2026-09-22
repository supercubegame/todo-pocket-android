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
    static final int EXPORT_BACKUP=41, IMPORT_BACKUP=42;
    private TodayScreen screen;
    @Override public void onCreate(Bundle saved){super.onCreate(saved);screen=new TodayScreen(this);screen.show(saved);}
    @Override protected void onSaveInstanceState(Bundle out){if(screen!=null)screen.save(out);super.onSaveInstanceState(out);}
    @Override public void onBackPressed(){if(screen==null||!screen.back())super.onBackPressed();}
    @Override protected void onDestroy(){if(screen!=null)screen.close();super.onDestroy();}
    /** SAF only supplies the URI. Copying to private storage freezes the user's choice;
     * replacing/deleting the original later cannot change the preview being reviewed.
     * This is not crash/lifecycle cleanup for an abandoned preview.
     */
    @Override protected void onActivityResult(int request,int result,Intent data){
        super.onActivityResult(request,result,data);
        if(screen==null)return;
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
