package com.supercubegame.pockettodo;

import android.net.Uri;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

/** Explicit full-backup replacement UI. Not sharing and not undo.
 * Selection freezes a validated private preview; it never writes live rows.
 * Confirmation must remain attached to this exact preview token.
 */
public final class RestoreScreen {
    private final TodayScreen host;
    private AppDatabase.RestorePlan plan;
    private Runnable invalid;
    private Button confirm;
    RestoreScreen(TodayScreen host){this.host=host;}
    void attach(AppDatabase.RestorePlan value,Runnable stale){cancelSilently();plan=value;invalid=stale;}
    void show(Uri file){
        LinearLayout body=host.content();body.addView(host.text("备份",24,TodayScreen.INK));
        TextView privacy=host.text("完整备份包含私有内容且未加密。恢复会替换本机数据，不会合并；请在系统文件选择器里确认来源。",15,TodayScreen.MUTED);
        privacy.setPadding(host.dp(14),host.dp(12),host.dp(14),host.dp(12));privacy.setBackground(host.shape(TodayScreen.TINT,16));body.addView(privacy);
        body.addView(host.button("全部替换为",()->host.chooseRestore(this::cancelled)));
        if(plan==null){
            TextView empty=host.text(file==null?"还没有选择备份。":"正在检查备份…",17,TodayScreen.MUTED);empty.setPadding(0,host.dp(20),0,0);body.addView(empty);
            if(file!=null)prepare(file);
            return;
        }
        ScrollView scroll=new ScrollView(host.activity);LinearLayout rows=host.column();scroll.addView(rows);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        TextView title=host.text("确认替换影响",20,TodayScreen.INK);title.setPadding(0,host.dp(14),0,host.dp(8));rows.addView(title);
        for(Map.Entry<String,Long> item:plan.currentCounts().entrySet()){
            String table=item.getKey();long incoming=plan.incomingCounts().get(table);
            TextView row=host.text(table+"：当前 "+item.getValue()+" 条 / 恢复后 "+incoming+" 条",15,TodayScreen.INK);
            row.setContentDescription("restore-row-"+table);row.setPadding(host.dp(10),host.dp(8),host.dp(10),host.dp(8));row.setBackground(host.shape(TodayScreen.WHITE,12));host.addRow(rows,row);
        }
        LinearLayout actions=new LinearLayout(host.activity);
        actions.addView(host.button("取消恢复",this::cancelled),new LinearLayout.LayoutParams(0,host.dp(52),1));
        Button again=host.button("重新预览",()->cancelSilently());again.setContentDescription("restore-refresh");actions.addView(again,new LinearLayout.LayoutParams(0,host.dp(52),1));
        confirm=host.button("确认替换",this::confirmNow);confirm.setContentDescription("restore-confirm");actions.addView(confirm,new LinearLayout.LayoutParams(0,host.dp(52),1));body.addView(actions);
    }
    private Path copy(Uri uri)throws IOException{
        Path temp=Files.createTempFile(host.activity.getCacheDir().toPath(),"restore-source-",".zip");
        try(InputStream in=host.activity.getContentResolver().openInputStream(uri)){
            if(in==null)throw new IOException("无法读取所选备份");
            Files.copy(in,temp,java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }catch(IOException|RuntimeException e){Files.deleteIfExists(temp);throw new IOException("无法读取所选备份",e);}
        return temp;
    }
    private void prepare(Uri uri){
        host.work(()->{
            Path temp=copy(uri);
            try{return host.db.prepareRestore(temp,host.activity.getCacheDir().toPath(),1000000);}
            finally{Files.deleteIfExists(temp);}
        },selected->host.beginRestorePlan(selected,()->host.message("预览已过期，请重新选择备份",true)),()->host.message("备份文件无效或已损坏，未更改本机数据",true));
    }
    private void confirmNow(){
        AppDatabase.RestorePlan active=plan;if(active==null)return;
        confirm.setEnabled(false);
        host.work(()->{
            try(java.io.Closeable ignored=active){host.db.confirmRestore(active,new MediaRepository(host.activity.getFilesDir().toPath().resolve("pocket-v12-media"),1000000));}
            return true;
        },ignored->{plan=null;host.refresh();},()->{
            plan=null;
            host.message("数据在预览后已有变化，或备份不完整；未替换本机数据。请重新预览。",true);
            host.refresh();
        });
    }
    void cancelled(){cancelSilently();host.message("已取消恢复，未更改本机数据",false);host.refresh();}
    void cancelSilently(){
        AppDatabase.RestorePlan active=plan;plan=null;
        if(active==null)return;
        try{active.close();}catch(IOException ignored){}
        if(invalid!=null)invalid.run();invalid=null;
    }
}
