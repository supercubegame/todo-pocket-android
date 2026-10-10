package com.supercubegame.pockettodo;

import android.database.Cursor;
import android.view.View;
import android.widget.*;
import java.util.ArrayList;
import java.util.List;

/** Manual, local catalog. Reuse an application identity, never its business records.
 * Notebook styling follows TodayScreen; names lead, package/identity disambiguate.
 * No package scanning, permission request, external launch or automatic recording.
 */
final class AppCatalog {
    private final TodayScreen host;
    private final long category;
    private final Runnable back;
    private Page page;
    private static final class Entry {
        final long id;final String name,packageName;
        Entry(Cursor c){id=c.getLong(0);name=c.getString(1);packageName=c.getString(2);}
    }
    private static final class Page {
        final LinearLayout root;
        boolean alive=true,submitted;
        AppDatabase.ApplicationActivityPlan plan;
        AppDatabase.ApplicationRenamePlan renamePlan;
        Page(LinearLayout root){this.root=root;}
        void close(){alive=false;if(plan!=null){plan.close();plan=null;}if(renamePlan!=null){renamePlan.close();renamePlan=null;}}
    }
    AppCatalog(TodayScreen host,long category,Runnable back){
        this.host=host;this.category=category;this.back=back;
    }
    private boolean current(Page p){
        return page==p&&p.alive&&p.root.isAttachedToWindow()
            &&!host.activity.isFinishing()&&!host.activity.isDestroyed();
    }
    private boolean canSubmit(Page p,View control){
        return current(p)&&!p.submitted&&control.isAttachedToWindow()&&control.isEnabled();
    }
    private List<Entry> entries(){
        List<Entry> out=new ArrayList<>();
        try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT id,name,package_name FROM applications ORDER BY id",null)){
            while(c.moveToNext())out.add(new Entry(c));
        }
        return out;
    }
    void open(View anchor){
        if(!anchor.isAttachedToWindow()||host.activity.isFinishing()||host.activity.isDestroyed())return;
        host.work(this::entries,items->{
            if(anchor.isAttachedToWindow()&&!host.activity.isFinishing()&&!host.activity.isDestroyed())render(items);
        },null);
    }
    private Page begin(String heading){
        if(page!=null)page.close();
        LinearLayout outer=host.content();
        Page p=new Page(host.column());page=p;
        outer.addView(p.root,new LinearLayout.LayoutParams(-1,-1));
        p.root.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener(){
            @Override public void onViewAttachedToWindow(View v){}
            @Override public void onViewDetachedFromWindow(View v){p.close();}
        });
        TextView title=host.text(heading,24,TodayScreen.INK);p.root.addView(title);
        Button leave=host.button("返回分类",()->{if(current(p)&&!p.submitted){p.close();back.run();}});
        leave.setContentDescription("catalog-back");p.root.addView(leave,new LinearLayout.LayoutParams(-1,-2));
        return p;
    }
    private LinearLayout scroll(Page p){
        ScrollView scroll=new ScrollView(host.activity);scroll.setFillViewport(true);
        LinearLayout body=host.column();scroll.addView(body);
        p.root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));return body;
    }
    private void render(List<Entry> items){
        Page p=begin(category==0?"应用目录":"选择应用");
        LinearLayout body=scroll(p);
        TextView intro=host.text(category==0?"手动整理常用应用，供不同分类复用。":"只关联应用，不复制已有活动、打卡或账目。",16,TodayScreen.MUTED);
        intro.setPadding(0,host.dp(8),0,host.dp(16));body.addView(intro);
        if(category==0){
            EditText name=host.field("catalog-name",false);name.setHint("应用名称");body.addView(name,new LinearLayout.LayoutParams(-1,-2));
            EditText pkg=host.field("catalog-package",false);pkg.setHint("包名（选填，例如 com.example.app）");body.addView(pkg,new LinearLayout.LayoutParams(-1,-2));
            TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("catalog-validation");
            Button create=host.button("添加到目录",()->{});create.setContentDescription("catalog-create-app");
            create.setOnClickListener(v->{
                if(!canSubmit(p,create))return;
                String title=name.getText().toString().trim(),packageName=pkg.getText().toString().trim();
                if(title.isEmpty()){validation.setText("应用名称不能为空");return;}
                if(!packageName.isEmpty()&&!packageName.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+")){
                    validation.setText("包名格式无效；不知道包名可留空。");return;
                }
                p.submitted=true;
                host.work(()->{
                    synchronized(host.db){
                        long id;
                        try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT MAX(id) FROM applications",null)){
                            if(!c.moveToFirst())throw new IllegalStateException("无法分配应用标识");
                            id=c.isNull(0)?1:Math.incrementExact(c.getLong(0));
                        }
                        host.db.addApplication(id,title,packageName);
                    }
                    return true;
                },ignored->{if(current(p))renderAfterCreate(p,create);},()->{
                    if(current(p)){p.submitted=false;validation.setText("未能添加：包名可能已存在，或存储未完成。请检查后重试。");}
                });
            });
            body.addView(create,new LinearLayout.LayoutParams(-1,-2));body.addView(validation);
        }
        TextView label=host.text("已保存 · "+items.size(),18,TodayScreen.INK);
        label.setPadding(0,host.dp(20),0,host.dp(8));body.addView(label);
        if(items.isEmpty())body.addView(host.text(category==0?"目录还是空的，先添加一个应用。":"目录还是空的，请返回分类，从「应用目录」添加。",16,TodayScreen.MUTED));
        for(Entry item:items){
            LinearLayout row=host.column();row.setPadding(host.dp(12),host.dp(8),host.dp(12),host.dp(12));row.setBackground(host.shape(TodayScreen.WHITE,14));
            if(category==0){
                TextView title=host.text(item.name,18,TodayScreen.INK);title.setContentDescription("catalog-app-"+item.id);row.addView(title);
                Button rename=host.button("改名",()->{});rename.setContentDescription("catalog-rename-"+item.id);
                rename.setOnClickListener(v->rename(p,rename,item));row.addView(rename,new LinearLayout.LayoutParams(-1,-2));
            }else{
                Button select=host.button(item.name,()->{});select.setContentDescription("catalog-app-"+item.id);
                select.setOnClickListener(v->choose(p,select,item));row.addView(select,new LinearLayout.LayoutParams(-1,-2));
            }
            row.addView(host.text((item.packageName.isEmpty()?"未填写包名":item.packageName)+" · #"+item.id,14,TodayScreen.MUTED));
            host.addRow(body,row);
        }
    }
    private void rename(Page p,View control,Entry item){
        if(!canSubmit(p,control))return;
        p.submitted=true;
        host.work(()->host.db.prepareApplicationRename(item.id),plan->{
            if(!current(p)){
                plan.close();return;
            }
            if(!item.name.equals(plan.name())||!item.packageName.equals(plan.packageName())){
                plan.close();p.submitted=false;host.message("应用已变化，请返回后重新打开目录。",true);return;
            }
            renderRename(plan);
        },()->{if(current(p)){p.submitted=false;host.message("无法读取改名预览，请重新打开目录。",true);}});
    }
    private void renderRename(AppDatabase.ApplicationRenamePlan plan){
        Page p=begin("应用改名");p.renamePlan=plan;
        LinearLayout body=scroll(p);
        TextView identity=host.text("应用："+plan.name()+" · #"+plan.applicationId()+"\n包名："+(plan.packageName().isEmpty()?"未填写":plan.packageName()),16,TodayScreen.INK);
        identity.setContentDescription("catalog-rename-identity");body.addView(identity);
        EditText name=host.field("catalog-rename-name",false);name.setText(plan.name());body.addView(name,new LinearLayout.LayoutParams(-1,-2));
        body.addView(host.text("只修改目录名称。关联活动的名称、路径、标签、笔记和账目保持不变。",16,TodayScreen.MUTED));
        TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("catalog-rename-validation");
        Button save=host.button("保存应用名称",()->{});save.setContentDescription("catalog-rename-save");
        Button cancel=host.button("取消改名",()->{});cancel.setContentDescription("catalog-rename-cancel");
        cancel.setOnClickListener(v->{
            if(!canSubmit(p,cancel))return;
            plan.close();p.renamePlan=null;p.submitted=true;save.setEnabled(false);
            refreshRename(p,save,"已取消改名，但目录读取失败。请返回分类后重新打开。");
        });
        save.setOnClickListener(v->{
            if(!canSubmit(p,save)||p.renamePlan!=plan)return;
            String value=name.getText().toString().trim();
            if(value.isEmpty()){validation.setText("应用名称不能为空");return;}
            p.submitted=true;save.setEnabled(false);name.setEnabled(false);cancel.setEnabled(false);
            // Keep the plan owned by the page until the queued write finishes.
            // Detaching before execution closes it instead of reviving a stale write.
            host.work(()->host.db.confirmApplicationRename(plan,value),changed->{
                plan.close();p.renamePlan=null;
                if(current(p))refreshRename(p,save,"名称已保存，但目录读取失败。请返回分类后重新打开，不要重复保存。");
            },()->{
                plan.close();p.renamePlan=null;
                if(current(p)){
                    p.submitted=false;cancel.setEnabled(true);
                    validation.setText("未能改名，内容可能已变化。本次已结束，请取消后重新打开。");
                }
            });
        });
        body.addView(save,new LinearLayout.LayoutParams(-1,-2));body.addView(cancel,new LinearLayout.LayoutParams(-1,-2));body.addView(validation);
    }
    private void refreshRename(Page p,Button save,String failure){
        host.work(this::entries,items->{if(current(p))render(items);},()->{
            if(current(p)){p.submitted=false;save.setEnabled(false);host.message(failure,true);}
        });
    }
    private void renderAfterCreate(Page p,Button create){
        host.work(this::entries,items->{if(current(p))render(items);},()->{
            if(current(p)){p.submitted=false;create.setEnabled(false);host.message("应用已添加，但目录读取失败。请返回后重新打开，不要重复添加。",true);}
        });
    }
    private void choose(Page p,View control,Entry item){
        if(!canSubmit(p,control))return;
        p.submitted=true;
        host.work(()->host.db.prepareApplicationActivity(category,item.id),plan->{
            if(!current(p)){plan.close();return;}
            if(!item.name.equals(plan.applicationName())){plan.close();p.submitted=false;host.message("应用已变化，请返回后重新选择。",true);return;}
            renderActivity(plan);
        },()->{if(current(p)){p.submitted=false;host.message("无法读取应用或分类，请返回后重新选择。",true);}});
    }
    private void renderActivity(AppDatabase.ApplicationActivityPlan plan){
        Page p=begin("新建关联活动");p.plan=plan;
        LinearLayout body=scroll(p);
        body.addView(host.text("分类："+plan.categoryName()+"\n应用："+plan.applicationName()+" · #"+plan.applicationId(),18,TodayScreen.INK));
        EditText title=host.field("catalog-activity-title",false);title.setHint("活动名称");title.setText(plan.applicationName());body.addView(title,new LinearLayout.LayoutParams(-1,-2));
        body.addView(host.text("只新增这一条活动。原有路径、笔记、打卡和账目不会复制。",16,TodayScreen.MUTED));
        TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("catalog-validation");
        Button create=host.button("创建关联活动",()->{});create.setContentDescription("catalog-create-activity");
        create.setOnClickListener(v->{
            if(!canSubmit(p,create)||p.plan!=plan)return;
            String value=title.getText().toString().trim();
            if(value.isEmpty()){validation.setText("活动名称不能为空");return;}
            p.submitted=true;p.plan=null;
            host.work(()->host.db.confirmApplicationActivity(plan,value),id->{
                if(current(p)){p.close();back.run();}
            },()->{
                plan.close();
                if(current(p)){
                    p.submitted=false;create.setEnabled(false);
                    validation.setText("未能创建，内容可能已变化。请返回分类后重新选择；本次不会重复提交。");
                }
            });
        });
        body.addView(create,new LinearLayout.LayoutParams(-1,-2));body.addView(validation);
    }
}
