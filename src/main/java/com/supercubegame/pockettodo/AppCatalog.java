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
        Button leave=host.button("\u8fd4\u56de\u5206\u7c7b",()->{if(current(p)&&!p.submitted){p.close();back.run();}});
        leave.setContentDescription("catalog-back");p.root.addView(leave,new LinearLayout.LayoutParams(-1,-2));
        return p;
    }
    private LinearLayout scroll(Page p){
        ScrollView scroll=new ScrollView(host.activity);scroll.setFillViewport(true);
        LinearLayout body=host.column();scroll.addView(body);
        p.root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));return body;
    }
    private void render(List<Entry> items){
        Page p=begin(category==0?"\u5e94\u7528\u76ee\u5f55":"\u9009\u62e9\u5e94\u7528");
        LinearLayout body=scroll(p);
        TextView intro=host.text(category==0?"\u624b\u52a8\u6574\u7406\u5e38\u7528\u5e94\u7528\uff0c\u4f9b\u4e0d\u540c\u5206\u7c7b\u590d\u7528\u3002":"\u53ea\u5173\u8054\u5e94\u7528\uff0c\u4e0d\u590d\u5236\u5df2\u6709\u6d3b\u52a8\u3001\u6253\u5361\u6216\u8d26\u76ee\u3002",16,TodayScreen.MUTED);
        intro.setPadding(0,host.dp(8),0,host.dp(16));body.addView(intro);
        if(category==0){
            EditText name=host.field("catalog-name",false);name.setHint("\u5e94\u7528\u540d\u79f0");body.addView(name,new LinearLayout.LayoutParams(-1,-2));
            EditText pkg=host.field("catalog-package",false);pkg.setHint("\u5305\u540d\uff08\u9009\u586b\uff0c\u4f8b\u5982 com.example.app\uff09");body.addView(pkg,new LinearLayout.LayoutParams(-1,-2));
            TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("catalog-validation");
            Button create=host.button("\u6dfb\u52a0\u5230\u76ee\u5f55",()->{});create.setContentDescription("catalog-create-app");
            create.setOnClickListener(v->{
                if(!canSubmit(p,create))return;
                String title=name.getText().toString().trim(),packageName=pkg.getText().toString().trim();
                if(title.isEmpty()){validation.setText("\u5e94\u7528\u540d\u79f0\u4e0d\u80fd\u4e3a\u7a7a");return;}
                if(!packageName.isEmpty()&&!packageName.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+")){
                    validation.setText("\u5305\u540d\u683c\u5f0f\u65e0\u6548\uff1b\u4e0d\u77e5\u9053\u5305\u540d\u53ef\u7559\u7a7a\u3002");return;
                }
                p.submitted=true;
                host.work(()->{
                    synchronized(host.db){
                        long id;
                        try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT MAX(id) FROM applications",null)){
                            if(!c.moveToFirst())throw new IllegalStateException("\u65e0\u6cd5\u5206\u914d\u5e94\u7528\u6807\u8bc6");
                            id=c.isNull(0)?1:Math.incrementExact(c.getLong(0));
                        }
                        host.db.addApplication(id,title,packageName);
                    }
                    return true;
                },ignored->{if(current(p))renderAfterCreate(p,create);},()->{
                    if(current(p)){p.submitted=false;validation.setText("\u672a\u80fd\u6dfb\u52a0\uff1a\u5305\u540d\u53ef\u80fd\u5df2\u5b58\u5728\uff0c\u6216\u5b58\u50a8\u672a\u5b8c\u6210\u3002\u8bf7\u68c0\u67e5\u540e\u91cd\u8bd5\u3002");}
                });
            });
            body.addView(create,new LinearLayout.LayoutParams(-1,-2));body.addView(validation);
        }
        TextView label=host.text("\u5df2\u4fdd\u5b58 \u00b7 "+items.size(),18,TodayScreen.INK);
        label.setPadding(0,host.dp(20),0,host.dp(8));body.addView(label);
        if(items.isEmpty())body.addView(host.text(category==0?"\u76ee\u5f55\u8fd8\u662f\u7a7a\u7684\uff0c\u5148\u6dfb\u52a0\u4e00\u4e2a\u5e94\u7528\u3002":"\u76ee\u5f55\u8fd8\u662f\u7a7a\u7684\uff0c\u8bf7\u8fd4\u56de\u5206\u7c7b\uff0c\u4ece\u300c\u5e94\u7528\u76ee\u5f55\u300d\u6dfb\u52a0\u3002",16,TodayScreen.MUTED));
        for(Entry item:items){
            LinearLayout row=host.column();row.setPadding(host.dp(12),host.dp(8),host.dp(12),host.dp(12));row.setBackground(host.shape(TodayScreen.WHITE,14));
            if(category==0){
                TextView title=host.text(item.name,18,TodayScreen.INK);title.setContentDescription("catalog-app-"+item.id);row.addView(title);
                Button rename=host.button("\u6539\u540d",()->{});rename.setContentDescription("catalog-rename-"+item.id);
                rename.setOnClickListener(v->rename(p,rename,item));row.addView(rename,new LinearLayout.LayoutParams(-1,-2));
            }else{
                Button select=host.button(item.name,()->{});select.setContentDescription("catalog-app-"+item.id);
                select.setOnClickListener(v->choose(p,select,item));row.addView(select,new LinearLayout.LayoutParams(-1,-2));
            }
            row.addView(host.text((item.packageName.isEmpty()?"\u672a\u586b\u5199\u5305\u540d":item.packageName)+" \u00b7 #"+item.id,14,TodayScreen.MUTED));
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
                plan.close();p.submitted=false;host.message("\u5e94\u7528\u5df2\u53d8\u5316\uff0c\u8bf7\u8fd4\u56de\u540e\u91cd\u65b0\u6253\u5f00\u76ee\u5f55\u3002",true);return;
            }
            renderRename(plan);
        },()->{if(current(p)){p.submitted=false;host.message("\u65e0\u6cd5\u8bfb\u53d6\u6539\u540d\u9884\u89c8\uff0c\u8bf7\u91cd\u65b0\u6253\u5f00\u76ee\u5f55\u3002",true);}});
    }
    private void renderRename(AppDatabase.ApplicationRenamePlan plan){
        Page p=begin("\u5e94\u7528\u6539\u540d");p.renamePlan=plan;
        LinearLayout body=scroll(p);
        TextView identity=host.text("\u5e94\u7528\uff1a"+plan.name()+" \u00b7 #"+plan.applicationId()+"\n\u5305\u540d\uff1a"+(plan.packageName().isEmpty()?"\u672a\u586b\u5199":plan.packageName()),16,TodayScreen.INK);
        identity.setContentDescription("catalog-rename-identity");body.addView(identity);
        EditText name=host.field("catalog-rename-name",false);name.setText(plan.name());body.addView(name,new LinearLayout.LayoutParams(-1,-2));
        body.addView(host.text("\u53ea\u4fee\u6539\u76ee\u5f55\u540d\u79f0\u3002\u5173\u8054\u6d3b\u52a8\u7684\u540d\u79f0\u3001\u8def\u5f84\u3001\u6807\u7b7e\u3001\u7b14\u8bb0\u548c\u8d26\u76ee\u4fdd\u6301\u4e0d\u53d8\u3002",16,TodayScreen.MUTED));
        TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("catalog-rename-validation");
        Button save=host.button("\u4fdd\u5b58\u5e94\u7528\u540d\u79f0",()->{});save.setContentDescription("catalog-rename-save");
        Button cancel=host.button("\u53d6\u6d88\u6539\u540d",()->{});cancel.setContentDescription("catalog-rename-cancel");
        cancel.setOnClickListener(v->{
            if(!canSubmit(p,cancel))return;
            plan.close();p.renamePlan=null;p.submitted=true;save.setEnabled(false);
            refreshRename(p,save,"\u5df2\u53d6\u6d88\u6539\u540d\uff0c\u4f46\u76ee\u5f55\u8bfb\u53d6\u5931\u8d25\u3002\u8bf7\u8fd4\u56de\u5206\u7c7b\u540e\u91cd\u65b0\u6253\u5f00\u3002");
        });
        save.setOnClickListener(v->{
            if(!canSubmit(p,save)||p.renamePlan!=plan)return;
            String value=name.getText().toString().trim();
            if(value.isEmpty()){validation.setText("\u5e94\u7528\u540d\u79f0\u4e0d\u80fd\u4e3a\u7a7a");return;}
            p.submitted=true;save.setEnabled(false);name.setEnabled(false);cancel.setEnabled(false);
            host.work(()->host.db.confirmApplicationRename(plan,value),changed->{
                plan.close();p.renamePlan=null;
                if(current(p))refreshRename(p,save,"\u540d\u79f0\u5df2\u4fdd\u5b58\uff0c\u4f46\u76ee\u5f55\u8bfb\u53d6\u5931\u8d25\u3002\u8bf7\u8fd4\u56de\u5206\u7c7b\u540e\u91cd\u65b0\u6253\u5f00\uff0c\u4e0d\u8981\u91cd\u590d\u4fdd\u5b58\u3002");
            },()->{
                plan.close();p.renamePlan=null;
                if(current(p)){
                    p.submitted=false;cancel.setEnabled(true);
                    validation.setText("\u672a\u80fd\u6539\u540d\uff0c\u5185\u5bb9\u53ef\u80fd\u5df2\u53d8\u5316\u3002\u672c\u6b21\u5df2\u7ed3\u675f\uff0c\u8bf7\u53d6\u6d88\u540e\u91cd\u65b0\u6253\u5f00\u3002");
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
            if(current(p)){p.submitted=false;create.setEnabled(false);host.message("\u5e94\u7528\u5df2\u6dfb\u52a0\uff0c\u4f46\u76ee\u5f55\u8bfb\u53d6\u5931\u8d25\u3002\u8bf7\u8fd4\u56de\u540e\u91cd\u65b0\u6253\u5f00\uff0c\u4e0d\u8981\u91cd\u590d\u6dfb\u52a0\u3002",true);}
        });
    }
    private void choose(Page p,View control,Entry item){
        if(!canSubmit(p,control))return;
        p.submitted=true;
        host.work(()->host.db.prepareApplicationActivity(category,item.id),plan->{
            if(!current(p)){plan.close();return;}
            if(!item.name.equals(plan.applicationName())){plan.close();p.submitted=false;host.message("\u5e94\u7528\u5df2\u53d8\u5316\uff0c\u8bf7\u8fd4\u56de\u540e\u91cd\u65b0\u9009\u62e9\u3002",true);return;}
            renderActivity(plan);
        },()->{if(current(p)){p.submitted=false;host.message("\u65e0\u6cd5\u8bfb\u53d6\u5e94\u7528\u6216\u5206\u7c7b\uff0c\u8bf7\u8fd4\u56de\u540e\u91cd\u65b0\u9009\u62e9\u3002",true);}});
    }
    private void renderActivity(AppDatabase.ApplicationActivityPlan plan){
        Page p=begin("\u65b0\u5efa\u5173\u8054\u6d3b\u52a8");p.plan=plan;
        LinearLayout body=scroll(p);
        body.addView(host.text("\u5206\u7c7b\uff1a"+plan.categoryName()+"\n\u5e94\u7528\uff1a"+plan.applicationName()+" \u00b7 #"+plan.applicationId(),18,TodayScreen.INK));
        EditText title=host.field("catalog-activity-title",false);title.setHint("\u6d3b\u52a8\u540d\u79f0");title.setText(plan.applicationName());body.addView(title,new LinearLayout.LayoutParams(-1,-2));
        body.addView(host.text("\u53ea\u65b0\u589e\u8fd9\u4e00\u6761\u6d3b\u52a8\u3002\u539f\u6709\u8def\u5f84\u3001\u7b14\u8bb0\u3001\u6253\u5361\u548c\u8d26\u76ee\u4e0d\u4f1a\u590d\u5236\u3002",16,TodayScreen.MUTED));
        TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("catalog-validation");
        Button create=host.button("\u521b\u5efa\u5173\u8054\u6d3b\u52a8",()->{});create.setContentDescription("catalog-create-activity");
        create.setOnClickListener(v->{
            if(!canSubmit(p,create)||p.plan!=plan)return;
            String value=title.getText().toString().trim();
            if(value.isEmpty()){validation.setText("\u6d3b\u52a8\u540d\u79f0\u4e0d\u80fd\u4e3a\u7a7a");return;}
            p.submitted=true;p.plan=null;
            host.work(()->host.db.confirmApplicationActivity(plan,value),id->{
                if(current(p)){p.close();back.run();}
            },()->{
                plan.close();
                if(current(p)){
                    p.submitted=false;create.setEnabled(false);
                    validation.setText("\u672a\u80fd\u521b\u5efa\uff0c\u5185\u5bb9\u53ef\u80fd\u5df2\u53d8\u5316\u3002\u8bf7\u8fd4\u56de\u5206\u7c7b\u540e\u91cd\u65b0\u9009\u62e9\uff1b\u672c\u6b21\u4e0d\u4f1a\u91cd\u590d\u63d0\u4ea4\u3002");
                }
            });
        });
        body.addView(create,new LinearLayout.LayoutParams(-1,-2));body.addView(validation);
    }
}
