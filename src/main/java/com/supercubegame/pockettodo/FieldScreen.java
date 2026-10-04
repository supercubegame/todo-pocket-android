package com.supercubegame.pockettodo;

import android.database.Cursor;
import android.view.View;
import android.widget.*;
import java.util.*;

/** Local field definitions are shared; values belong to one stable activity ID.
 * Native callbacks are page-bound and single-submit. Field-note UI comes later.
 */
final class FieldScreen {
    private final TodayScreen host;
    private final long activity;
    private final Runnable back;
    private Page page;
    private boolean opening;
    private static final String[] LABELS={"短文本","长文本","数字","日期","单选","多选","链接","是 / 否"};
    private static final class Entry {
        final CustomFields.Definition definition;
        final List<String> values;
        Entry(CustomFields.Definition definition,List<String> values){this.definition=definition;this.values=values;}
    }
    private static final class Page {
        final LinearLayout root;
        volatile boolean alive=true;
        boolean submitted;
        AppDatabase.FieldEditPlan plan;
        private AppDatabase.FieldEditPlan pending;
        Page(LinearLayout root){this.root=root;}
        // The host may discard a success callback after shutdown. Register the
        // worker result before returning, so detachment owns it in either order.
        synchronized void prepared(AppDatabase.FieldEditPlan value){
            if(!alive){value.close();return;}
            pending=value;
        }
        synchronized void handoff(AppDatabase.FieldEditPlan value){
            if(pending==value)pending=null;
        }
        synchronized void close(){
            alive=false;
            if(pending!=null){pending.close();pending=null;}
            if(plan!=null){plan.close();plan=null;}
        }
    }
    FieldScreen(TodayScreen host,long activity,Runnable back){
        this.host=host;this.activity=activity;this.back=back;
    }
    private boolean current(Page p){
        return page==p&&p.alive&&p.root.isAttachedToWindow()
            &&!host.activity.isFinishing()&&!host.activity.isDestroyed();
    }
    private boolean canSubmit(Page p,View control){
        return current(p)&&!p.submitted&&control.isAttachedToWindow()&&control.isEnabled();
    }
    private List<Entry> entries(){
        synchronized(host.db){
            android.database.sqlite.SQLiteDatabase sql=host.db.getReadableDatabase();
            sql.beginTransaction();
            try{
                List<Entry> result=new ArrayList<>();
                try(Cursor owner=sql.rawQuery("SELECT title FROM activities WHERE id=?",new String[]{Long.toString(activity)})){
                    if(!owner.moveToFirst())throw new IllegalArgumentException("活动不存在");
                }
                try(Cursor c=sql.rawQuery("SELECT id FROM fields ORDER BY rowid",null)){
                    while(c.moveToNext()){
                        String id=c.getString(0);
                        result.add(new Entry(host.db.fieldDefinition(id),host.db.fieldValue(activity,id)));
                    }
                }
                sql.setTransactionSuccessful();return result;
            }finally{sql.endTransaction();}
        }
    }
    void open(View anchor){
        if(opening||!anchor.isAttachedToWindow()||!anchor.isEnabled()
            ||host.activity.isFinishing()||host.activity.isDestroyed())return;
        opening=true;
        host.work(this::entries,items->{
            opening=false;
            if(anchor.isAttachedToWindow()&&!host.activity.isFinishing()&&!host.activity.isDestroyed())render(items);
        },()->{opening=false;});
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
        p.root.addView(host.text(heading,24,TodayScreen.INK));
        return p;
    }
    private LinearLayout scroll(Page p){
        ScrollView view=new ScrollView(host.activity);view.setFillViewport(true);
        LinearLayout body=host.column();view.addView(body);
        p.root.addView(view,new LinearLayout.LayoutParams(-1,0,1));return body;
    }
    private Button button(LinearLayout body,String label,String key){
        Button b=host.button(label,()->{});b.setContentDescription(key);
        body.addView(b,new LinearLayout.LayoutParams(-1,-2));return b;
    }
    private EditText input(LinearLayout body,String key,String hint,boolean multi,String value){
        EditText field=host.field(key,multi);field.setContentDescription(key);field.setHint(hint);field.setText(value);
        body.addView(field,new LinearLayout.LayoutParams(-1,-2));return field;
    }
    private TextView validation(LinearLayout body){
        TextView text=host.text("",14,TodayScreen.ERROR);text.setContentDescription("field-validation");body.addView(text);return text;
    }
    private void refresh(Page p){
        host.work(this::entries,items->{if(current(p))render(items);},()->{
            if(current(p)){
                p.submitted=false;
                host.message("字段读取失败。已提交的操作不会重做，请返回活动后重新进入。",true);
            }
        });
    }
    private void cancel(Page p,LinearLayout body){
        Button b=button(body,"取消，返回字段","field-cancel");
        b.setOnClickListener(v->{
            if(!canSubmit(p,b))return;
            if(p.plan!=null){p.plan.close();p.plan=null;}
            p.submitted=true;refresh(p);
        });
    }
    private void render(List<Entry> items){
        Page p=begin("自定义字段");
        LinearLayout actions=new LinearLayout(host.activity);p.root.addView(actions);
        Button leave=host.button("返回活动",()->{});leave.setContentDescription("field-back");
        leave.setOnClickListener(v->{if(canSubmit(p,leave)){p.close();back.run();}});
        Button create=host.button("新建字段",()->{});create.setContentDescription("field-new");
        create.setOnClickListener(v->{if(canSubmit(p,create))create();});
        for(Button b:new Button[]{leave,create})actions.addView(b,new LinearLayout.LayoutParams(0,host.dp(48),1));
        LinearLayout body=scroll(p);
        body.addView(host.text("字段名称与类型全局共用；这里填写的值只属于当前活动。归档保留历史值和笔记关联。",15,TodayScreen.MUTED));
        if(items.isEmpty())body.addView(host.text("还没有字段，先建一个。",18,TodayScreen.MUTED));
        for(Entry entry:items){
            CustomFields.Definition f=entry.definition;LinearLayout row=host.column();
            row.setPadding(host.dp(12),host.dp(12),host.dp(12),host.dp(12));row.setBackground(host.shape(TodayScreen.WHITE,14));
            row.addView(host.text(f.name+(f.archived?" · 已归档":""),20,TodayScreen.INK));
            row.addView(host.text(LABELS[f.type.ordinal()]+" · "+f.id,13,TodayScreen.MUTED));
            TextView value=host.text(entry.values.isEmpty()?"尚未填写":String.join("\n",entry.values),17,TodayScreen.INK);
            value.setContentDescription("field-value-"+f.id);value.setMaxLines(5);row.addView(value);
            Button edit=button(row,f.archived?"历史值只读":"填写 / 修改","field-edit-"+f.id);edit.setEnabled(!f.archived);
            edit.setOnClickListener(v->prepare(p,edit,f,0));
            LinearLayout tools=new LinearLayout(host.activity);row.addView(tools);
            Button rename=host.button("改名",()->{});rename.setContentDescription("field-rename-"+f.id);
            rename.setOnClickListener(v->prepare(p,rename,f,1));
            Button archive=host.button(f.archived?"恢复字段":"归档",()->{});archive.setContentDescription("field-archive-"+f.id);
            archive.setOnClickListener(v->prepare(p,archive,f,2));
            for(Button b:new Button[]{rename,archive})tools.addView(b,new LinearLayout.LayoutParams(0,host.dp(48),1));
            host.addRow(body,row);
        }
    }
    private void create(){
        Page p=begin("新建字段");LinearLayout body=scroll(p);cancel(p,body);
        String id="field-"+UUID.randomUUID();
        CustomFields.Type[] selected={CustomFields.Type.TEXT};
        body.addView(host.text("同名字段分开保存。选项一行一个，保存后类型和选项标识不变。",15,TodayScreen.MUTED));
        EditText name=input(body,"field-name","字段名称",false,"");
        List<Button> types=new ArrayList<>();
        for(CustomFields.Type type:CustomFields.Type.values()){
            Button pick=button(body,LABELS[type.ordinal()],"field-type-"+type.name());types.add(pick);
        }
        EditText options=input(body,"field-options","单选 / 多选选项，一行一个",true,"");options.setEnabled(false);
        for(CustomFields.Type type:CustomFields.Type.values()){
            Button pick=types.get(type.ordinal());
            pick.setOnClickListener(v->{
                if(!canSubmit(p,pick))return;
                selected[0]=type;options.setEnabled(type==CustomFields.Type.SELECT||type==CustomFields.Type.MULTI_SELECT);
                for(int i=0;i<types.size();i++)types.get(i).setText((i==type.ordinal()?"✓ ":"")+LABELS[i]);
            });
        }
        types.get(0).setText("✓ "+LABELS[0]);
        TextView error=validation(body);Button save=button(body,"创建字段","field-create");
        save.setOnClickListener(v->{
            if(!canSubmit(p,save))return;
            final CustomFields.Definition definition;
            try{
                List<String> values=new ArrayList<>();
                if(selected[0]==CustomFields.Type.SELECT||selected[0]==CustomFields.Type.MULTI_SELECT)
                    for(String option:options.getText().toString().split("\\r?\\n",-1))values.add(option.trim());
                CustomFields validator=new CustomFields();validator.define(id,name.getText().toString(),selected[0].name(),values);
                definition=validator.definition(id);
            }catch(RuntimeException e){error.setText("名称不能为空；选择类型必须填写不重复的有效选项。");return;}
            p.submitted=true;save.setEnabled(false);
            host.work(()->{
                if(!p.alive)throw new IllegalStateException("页面已关闭");
                host.db.defineField(definition.id,definition.name,definition.type.name(),definition.options);return true;
            },ignored->{if(current(p))refresh(p);},()->{
                if(current(p)){p.submitted=false;error.setText("未能创建，请取消后重新打开。本次提交不会重试。");}
            });
        });
    }
    private void prepare(Page p,View control,CustomFields.Definition shown,int mode){
        if(!canSubmit(p,control))return;
        p.submitted=true;
        host.work(()->{
            AppDatabase.FieldEditPlan result=host.db.prepareFieldEdit(activity,shown.id);
            p.prepared(result);return result;
        },plan->{
            p.handoff(plan);
            if(!current(p)){plan.close();return;}
            CustomFields.Definition f=plan.definition();
            if(!f.name.equals(shown.name)||f.archived!=shown.archived||f.type!=shown.type||!f.options.equals(shown.options)){
                plan.close();p.submitted=false;host.message("字段已变化，请返回活动后重新进入。",true);return;
            }
            editor(plan,mode);
        },()->{if(current(p))p.submitted=false;});
    }
    private static List<String> values(CustomFields.Definition f,String text){
        if(text.isEmpty())return Collections.emptyList();
        return f.type==CustomFields.Type.MULTI_SELECT?Arrays.asList(text.split("\\r?\\n",-1)):Collections.singletonList(text);
    }
    private void editor(AppDatabase.FieldEditPlan plan,int mode){
        CustomFields.Definition f=plan.definition();
        Page p=begin(mode==0?"填写字段":mode==1?"字段改名":f.archived?"恢复字段":"归档字段");p.plan=plan;
        LinearLayout body=scroll(p);cancel(p,body);
        body.addView(host.text(f.name+" · "+LABELS[f.type.ordinal()],20,TodayScreen.INK));
        body.addView(host.text("字段标识："+f.id,13,TodayScreen.MUTED));
        EditText field;
        if(mode==0){
            field=input(body,"field-value-input",hint(f.type),f.type==CustomFields.Type.LONG_TEXT||f.type==CustomFields.Type.MULTI_SELECT,String.join("\n",plan.values()));
            if(f.type==CustomFields.Type.SELECT||f.type==CustomFields.Type.MULTI_SELECT||f.type==CustomFields.Type.BOOLEAN){
                List<String> choices=f.type==CustomFields.Type.BOOLEAN?Arrays.asList("true","false"):f.options;
                for(String option:choices){
                    Button choice=button(body,option,"field-choice-"+option);
                    choice.setOnClickListener(v->{
                        if(!canSubmit(p,choice))return;
                        if(f.type==CustomFields.Type.MULTI_SELECT){
                            LinkedHashSet<String> chosen=new LinkedHashSet<>(values(f,field.getText().toString()));
                            if(!chosen.remove(option))chosen.add(option);field.setText(String.join("\n",chosen));
                        }else field.setText(option);
                    });
                }
            }
            body.addView(host.text("留空可清除此活动的值，不删除字段。",14,TodayScreen.MUTED));
        }else if(mode==1){
            field=input(body,"field-name","字段名称",false,f.name);
            body.addView(host.text("改名会在所有活动中显示；字段标识、历史值和笔记关联保持不变。",15,TodayScreen.MUTED));
        }else{
            field=null;
            body.addView(host.text(f.archived?"恢复后可继续填写。原有值和笔记关联保留。":"此字段将对所有活动只读。保留全部历史值和笔记关联，可从这里恢复。",16,TodayScreen.MUTED));
        }
        TextView error=validation(body);
        String key=mode==0?"field-save":mode==1?"field-rename-save":"field-archive-confirm";
        Button save=button(body,mode==0?"保存值":mode==1?"保存名称":f.archived?"确认恢复":"确认归档",key);
        save.setOnClickListener(v->{
            if(!canSubmit(p,save)||p.plan!=plan)return;
            final List<String> input;final String name;
            try{
                if(mode==0){
                    CustomFields validator=new CustomFields();validator.define(f.id,f.name,f.type.name(),f.options);
                    validator.put(activity,f.id,values(f,field.getText().toString()));input=validator.value(activity,f.id);name=null;
                }else{input=null;name=mode==1?ActivityModel.title(field.getText().toString()):null;}
            }catch(RuntimeException e){error.setText(mode==1?"名称不能为空。":hint(f.type)+"；也可以留空清除。");return;}
            p.submitted=true;save.setEnabled(false);
            if(field!=null)field.setEnabled(false);
            host.work(()->{
                if(!p.alive){plan.close();throw new IllegalStateException("页面已关闭");}
                if(mode==0)host.db.confirmFieldValue(plan,input);
                else if(mode==1)host.db.confirmFieldRename(plan,name);
                else host.db.confirmFieldArchive(plan,!f.archived);
                return true;
            },ignored->{if(current(p)){p.plan=null;refresh(p);}},()->{
                plan.close();
                if(current(p)){p.plan=null;p.submitted=false;error.setText("未能保存，内容可能已变化。请取消后重新打开；旧提交不会重试。");}
            });
        });
    }
    private static String hint(CustomFields.Type type){
        switch(type){
            case NUMBER:return "输入十进制数字，例如 -12.50";
            case DATE:return "输入真实日期，例如 2026-10-05";
            case SELECT:return "选择一个已定义的选项";
            case MULTI_SELECT:return "已定义选项一行一个，或点击选项切换";
            case LINK:return "输入 http 或 https 链接，不含账号密码";
            case BOOLEAN:return "选择 true（是）或 false（否）";
            case LONG_TEXT:return "填写多行文本";
            default:return "填写文本";
        }
    }
}
