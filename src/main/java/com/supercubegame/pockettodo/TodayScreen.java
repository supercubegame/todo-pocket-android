package com.supercubegame.pockettodo;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.database.Cursor;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

/** Native workbench, not the finished v1.2 product.
 * Pocket notebook logic: a quiet green daily tab, generous readable rows, fixed
 * navigation. No invented demo data, web content, photo or fake restore state.
 * All DB work belongs to the single executor, including close after queued work.
 */
public final class TodayScreen {
    static final int BG=0xfff5f9f7, INK=0xff203d35, MUTED=0xff5b726a;
    static final int ACCENT=0xff21785f, TINT=0xffdceee5, WHITE=0xfffefffe, ERROR=0xffa33743;
    final Activity activity;
    final AppDatabase db;
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private LinearLayout root, content;
    private TextView status;
    private EditText input;
    private int page, filter;
    private String draft="";
    private boolean busy, closed;
    private final Map<View,Boolean> paused=new IdentityHashMap<>();
    final ActivitiesScreen activities;
    private AppDatabase.RestorePlan pendingRestore;

    public TodayScreen(Activity activity) {
        this.activity=activity;
        db=AppDatabase.openSchema3(activity,"pocket-v12.db");
        activities=new ActivitiesScreen(this);
    }
    public void show(Bundle saved) {
        if(saved!=null){page=saved.getInt("page",0);filter=saved.getInt("filter",0);draft=saved.getString("draft","");activities.selected=saved.getLong("activity",0);}
        activity.getWindow().setStatusBarColor(BG);
        activity.getWindow().setNavigationBarColor(BG);
        activity.getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        root=column();root.setPadding(dp(18),dp(12),dp(18),dp(10));root.setBackgroundColor(BG);root.setFocusableInTouchMode(true);
        activity.setContentView(root);root.requestFocus();
        TextView label=text("口袋待办  /  1.2 开发预览",14,ACCENT);label.setContentDescription("v12-home");root.addView(label);
        TextView heading=text("把今天，放进口袋",28,INK);heading.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));heading.setPadding(0,dp(8),0,dp(8));root.addView(heading);
        status=text("正在读取本机数据…",14,MUTED);status.setContentDescription("v12-status");status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);root.addView(status);
        content=column();LinearLayout.LayoutParams cp=new LinearLayout.LayoutParams(-1,0,1);cp.topMargin=dp(12);root.addView(content,cp);
        LinearLayout nav=new LinearLayout(activity);
        nav.addView(button("今天",()->navigate(0)),new LinearLayout.LayoutParams(0,dp(52),1));
        nav.addView(button("活动",()->navigate(1)),new LinearLayout.LayoutParams(0,dp(52),1));
        nav.addView(button("导出笔记",()->((MainActivity)activity).openNoteShare()),new LinearLayout.LayoutParams(0,dp(52),1));root.addView(nav);
        refresh();
    }
    private void navigate(int next){if(busy)return;rememberDraft();page=next;refresh();}
    void refresh(){if(page==1)activities.load();else loadTodos();}
    LinearLayout content(){input=null;content.removeAllViews();return content;}
    private void rememberDraft(){if(input!=null)draft=input.getText().toString();}
    private static final class TodoRow {
        final String id,title;final boolean done;
        TodoRow(Cursor c){id=c.getString(0);title=c.getString(1);done=c.getInt(2)!=0;}
    }
    private void loadTodos() {
        rememberDraft();
        work(()->{
            List<TodoRow> rows=new ArrayList<>();
            try(Cursor c=db.getReadableDatabase().rawQuery("SELECT id,title,done FROM todos ORDER BY position",null)){while(c.moveToNext())rows.add(new TodoRow(c));}
            return rows;
        },this::renderTodos,null);
    }
    private void renderTodos(List<TodoRow> todos) {
        LinearLayout body=content();int remaining=0;for(TodoRow row:todos)if(!row.done)remaining++;
        TextView summary=text("还剩 "+remaining+" 件 / 共 "+todos.size()+" 件",20,INK);summary.setPadding(dp(14),dp(12),dp(14),dp(12));summary.setBackground(shape(TINT,16));body.addView(summary);
        LinearLayout tabs=new LinearLayout(activity);String[] labels={"全部","待办","已完成"};
        for(int i=0;i<labels.length;i++){final int choice=i;Button b=button(labels[i],()->{filter=choice;loadTodos();});if(i==filter){b.setBackgroundTintList(ColorStateList.valueOf(ACCENT));b.setTextColor(WHITE);}tabs.addView(b,new LinearLayout.LayoutParams(0,dp(48),1));}
        body.addView(tabs);
        ScrollView scroll=new ScrollView(activity);scroll.setFillViewport(true);LinearLayout rows=column();scroll.addView(rows);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        int visible=0;
        for(TodoRow item:todos){
            if((filter==1&&item.done)||(filter==2&&!item.done))continue;visible++;
            LinearLayout row=new LinearLayout(activity);row.setGravity(Gravity.CENTER_VERTICAL);row.setPadding(dp(8),dp(5),dp(4),dp(5));row.setBackground(shape(WHITE,14));
            CheckBox box=new CheckBox(activity);box.setText(item.title);box.setTextSize(17);box.setTextColor(item.done?MUTED:INK);box.setMinHeight(dp(52));box.setButtonTintList(ColorStateList.valueOf(ACCENT));box.setContentDescription("todo-"+item.id);box.setChecked(item.done);
            if(item.done)box.setPaintFlags(box.getPaintFlags()|Paint.STRIKE_THRU_TEXT_FLAG);
            box.setOnCheckedChangeListener((b,checked)->work(()->{db.editTodo(item.id,item.title,checked);return true;},ignored->loadTodos(),this::loadTodos));
            row.addView(box,new LinearLayout.LayoutParams(0,-2,1));
            Button edit=button("编辑",()->editor("编辑待办","编辑待办输入",item.title,false,value->db.editTodo(item.id,value,item.done),this::loadTodos));edit.setContentDescription("edit-"+item.id);row.addView(edit,new LinearLayout.LayoutParams(dp(60),dp(52)));
            addRow(rows,row);
        }
        if(visible==0){TextView empty=text(filter==2?"完成的事会留在这里":filter==1?"这一页已经清空，真不错":"先放进一件小事。\n活动和打卡，在「活动」里。",18,MUTED);empty.setPadding(dp(12),dp(28),dp(12),dp(16));rows.addView(empty);}
        LinearLayout composer=new LinearLayout(activity);composer.setGravity(Gravity.CENTER_VERTICAL);
        input=field("新待办输入",false);input.setHint("下一件小事…");input.setText(draft);input.setBackground(shape(WHITE,12));input.setPadding(dp(12),dp(8),dp(12),dp(8));
        composer.addView(input,new LinearLayout.LayoutParams(0,dp(56),1));
        composer.addView(button("添加",this::addTodo),new LinearLayout.LayoutParams(dp(68),dp(56)));body.addView(composer);
    }
    private void addTodo(){
        if(busy)return;String title=input.getText().toString().trim();
        if(title.isEmpty()){message("内容不能为空",true);return;}
        final String id=UUID.randomUUID().toString();
        work(()->{db.addTodo(id,title);return true;},ignored->{
            ((InputMethodManager)activity.getSystemService(Activity.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(input.getWindowToken(),0);
            input.setText("");draft="";filter=0;loadTodos();
        },null);
    }
    /** Dialog validation stays visible; save button cannot enqueue duplicate writes. */
    void editor(String title,String description,String initial,boolean multiline,Consumer<String> save,Runnable success){
        if(busy)return;
        LinearLayout body=column();body.setPadding(dp(20),dp(4),dp(20),dp(8));
        EditText field=field(description,multiline);field.setText(initial);body.addView(field,new LinearLayout.LayoutParams(-1,-2));
        TextView validation=text(multiline?"每行一步，按顺序保存；留空可清空路径。":"名称可随时修改。",14,MUTED);body.addView(validation);
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle(title).setView(body).setNegativeButton("取消",null).setPositiveButton("保存",null).create();
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String value=field.getText().toString().trim();
            if(!multiline&&value.isEmpty()){validation.setText("内容不能为空");validation.setTextColor(ERROR);return;}
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);field.setEnabled(false);
            work(()->{save.accept(value);return true;},ignored->{dialog.dismiss();success.run();},()->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);field.setEnabled(true);validation.setText("未能保存，请检查内容后重试");validation.setTextColor(ERROR);
            });
        }));
        dialog.show();
    }

    void exportBackup(Path temp)throws IOException{db.exportBackup(temp,new MediaRepository(activity.getFilesDir().toPath().resolve("media"),64L*1024*1024));}
    void backupExported(){activity.runOnUiThread(()->{message("备份已保存到你选的位置",false);content();activities.load();});}
    void backupCancelled(){activity.runOnUiThread(()->message("已取消，没有改变本机数据",false));}
    void backupFailed(Exception e){activity.runOnUiThread(()->message("备份或恢复未完成，本机数据保持原样",true));}
    /** The returned plan is shown in one dialog and consumed at most once.
     * Rotation/process death currently discards this in-memory plan; the user must
     * choose the file again. Persistent abandoned-plan cleanup remains pending.
     */
    void previewRestore(Path chosen)throws IOException{
        AppDatabase.RestorePlan plan;
        try{plan=db.prepareRestore(chosen,activity.getCacheDir().toPath().resolve("restore-stage"),64L*1024*1024);}
        finally{Files.deleteIfExists(chosen);}
        activity.runOnUiThread(()->showRestorePlan(plan));
    }
    private void showRestorePlan(AppDatabase.RestorePlan plan){
        pendingRestore=plan;
        LinearLayout body=column();body.setPadding(dp(20),dp(4),dp(20),dp(8));
        TextView warning=text("恢复会替换本机当前所有内容，不是合并。",17,ERROR);body.addView(warning);
        Map<String,Long> current=plan.currentCounts(),incoming=plan.incomingCounts();
        StringBuilder rows=new StringBuilder();
        String[] labels={"activities:活动","todos:普通待办","ledger:账目","checkins:打卡","notes:笔记","media:媒体文件"};
        for(String pair:labels){String[] parts=pair.split(":");rows.append(parts[1]).append("：本机 ").append(current.get(parts[0])).append(" → 备份 ").append(incoming.get(parts[0])).append('\n');}
        rows.append("恢复后暂无撤销按钮；可先返回导出当前备份。");
        TextView counts=text(rows.toString(),15,INK);counts.setContentDescription("restore-counts");body.addView(counts);
        CheckBox consent=new CheckBox(activity);consent.setText("我明白会替换本机数据");consent.setTextSize(16);consent.setTextColor(INK);consent.setContentDescription("restore-consent");body.addView(consent);
        TextView validation=text("",14,ERROR);validation.setContentDescription("restore-validation");body.addView(validation);
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("确认恢复备份？").setView(body).setNegativeButton("取消",null).setPositiveButton("确认恢复",null).create();
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            if(!consent.isChecked()){validation.setText("请先勾选：我明白会替换本机数据");return;}
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);consent.setEnabled(false);
            work(()->{db.confirmRestore(plan,new MediaRepository(activity.getFilesDir().toPath().resolve("media"),64L*1024*1024));return true;},ignored->{pendingRestore=null;dialog.dismiss();activities.selected=0;refresh();},()->dialog.dismiss());
        }));
        dialog.setOnDismissListener(unused->{if(pendingRestore==plan){pendingRestore=null;try{plan.close();}catch(IOException ignored){}}});
        dialog.show();
    }
    <T> void work(Callable<T> action,Consumer<T> success,Runnable failure){
        if(closed||busy)return;
        busy=true;pause(root);message("正在读取或保存…",false);
        io.execute(()->{
            try{T result=action.call();activity.runOnUiThread(()->{
                if(closed||activity.isDestroyed())return;busy=false;resume();message("已保存到本机",false);success.accept(result);
            });}catch(Exception e){activity.runOnUiThread(()->{
                if(closed||activity.isDestroyed())return;busy=false;resume();message("未能保存或读取，原始数据未清空",true);if(failure!=null)failure.run();
            });}
        });
    }
    void message(String value,boolean error){status.setText(value);status.setTextColor(error?ERROR:MUTED);}
    private void pause(View v){paused.put(v,v.isEnabled());v.setEnabled(false);if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++)pause(g.getChildAt(i));}}
    private void resume(){for(Map.Entry<View,Boolean> state:paused.entrySet())state.getKey().setEnabled(state.getValue());paused.clear();}
    void addRow(LinearLayout parent,View view){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(10);parent.addView(view,p);}
    LinearLayout column(){LinearLayout v=new LinearLayout(activity);v.setOrientation(LinearLayout.VERTICAL);return v;}
    TextView text(String value,int size,int color){TextView v=new TextView(activity);v.setText(value);v.setTextSize(size);v.setTextColor(color);return v;}
    EditText field(String description,boolean multiline){EditText v=new EditText(activity);v.setContentDescription(description);v.setTextSize(17);v.setTextColor(INK);v.setSingleLine(!multiline);if(multiline){v.setMinLines(3);v.setMaxLines(6);v.setGravity(Gravity.TOP);v.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE);}return v;}
    Button button(String value,Runnable action){Button b=new Button(activity);b.setText(value);b.setTextSize(14);b.setAllCaps(false);b.setTextColor(ACCENT);b.setMinWidth(0);b.setMinimumWidth(0);b.setMinHeight(dp(48));b.setPadding(dp(5),0,dp(5),0);b.setBackgroundTintList(ColorStateList.valueOf(TINT));b.setOnClickListener(v->{if(!busy)action.run();});return b;}
    GradientDrawable shape(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
    int dp(int value){return Math.round(value*activity.getResources().getDisplayMetrics().density);}
    public void save(Bundle out){rememberDraft();out.putInt("page",page);out.putInt("filter",filter);out.putString("draft",draft);out.putLong("activity",activities.selected);}
    public boolean back(){if(busy)return true;if(page==1&&activities.selected!=0){activities.selected=0;activities.load();return true;}return false;}
    public void close(){if(closed)return;closed=true;io.execute(db::close);io.shutdown();}
}
