package com.supercubegame.pockettodo;

import android.database.Cursor;
import android.view.View;
import android.widget.*;
import java.util.*;

/** Local field definitions are shared; values belong to one stable activity ID.
 * Native callbacks are page-bound and single-submit.
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
            Button notes=button(row,"字段笔记","field-notes-"+f.id);
            notes.setOnClickListener(v->{if(canSubmit(p,notes))loadNotes(p,f.id);});
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
    private static final class NoteRow {
        final String id,title;
        NoteRow(String id,String title){this.id=id;this.title=title;}
    }
    private static final class Notes {
        final CustomFields.Definition field;
        final List<NoteRow> linked=new ArrayList<>(),available=new ArrayList<>();
        Notes(CustomFields.Definition field){this.field=field;}
    }
    private Notes readNotes(String field){
        synchronized(host.db){
            android.database.sqlite.SQLiteDatabase sql=host.db.getReadableDatabase();
            sql.beginTransaction();
            try{
                Notes result=new Notes(host.db.fieldDefinition(field));
                try(Cursor owner=sql.rawQuery("SELECT title FROM activities WHERE id=?",new String[]{Long.toString(activity)})){
                    if(!owner.moveToFirst())throw new IllegalArgumentException("活动不存在");
                }
                try(Cursor c=sql.rawQuery("SELECT n.id,n.title,f.field_id FROM notes n LEFT JOIN field_notes f ON f.note_id=n.id WHERE n.activity_id=? ORDER BY n.rowid",new String[]{Long.toString(activity)})){
                    while(c.moveToNext()){
                        NoteRow note=new NoteRow(c.getString(0),c.getString(1));
                        if(c.isNull(2))result.available.add(note);
                        else if(field.equals(c.getString(2)))result.linked.add(note);
                    }
                }
                sql.setTransactionSuccessful();return result;
            }finally{sql.endTransaction();}
        }
    }
    private void loadNotes(Page p,String field){
        p.submitted=true;
        host.work(()->readNotes(field),notes->{if(current(p))renderNotes(notes);},()->{
            if(current(p)){p.submitted=false;host.message("笔记列表读取失败，请返回后重新打开；已提交操作不会重做。",true);}
        });
    }
    private void renderNotes(Notes notes){
        Page p=begin("字段笔记");p.root.setContentDescription("field-notes-page");
        LinearLayout body=scroll(p);CustomFields.Definition f=notes.field;
        body.addView(host.text(f.name+(f.archived?" · 历史只读":""),20,TodayScreen.INK));
        Button leave=button(body,"返回字段","field-notes-back");
        leave.setOnClickListener(v->{if(canSubmit(p,leave)){p.submitted=true;refresh(p);}});
        Button create=button(body,"新建字段笔记","field-note-new");
        Button link=button(body,"关联已有笔记","field-note-link");
        create.setEnabled(!f.archived);link.setEnabled(!f.archived);
        create.setOnClickListener(v->prepareNote(p,create,f,null,0));
        link.setOnClickListener(v->prepareNote(p,link,f,null,1));
        body.addView(host.text("仅显示当前活动的关联。解除关联不会删除笔记、正文或图片。",14,TodayScreen.MUTED));
        if(notes.linked.isEmpty())body.addView(host.text("还没有关联笔记。",17,TodayScreen.MUTED));
        for(NoteRow note:notes.linked){
            Button title=button(body,note.title+" · "+note.id,"field-note-"+note.id);
            title.setOnClickListener(v->{
                if(!canSubmit(p,title))return;
                p.submitted=true;
                Page loading=begin("打开笔记");
                Runnable returnToNotes=()->{
                    Page next=begin("字段笔记");loadNotes(next,f.id);
                };
                Button leaveNote=button(loading.root,"返回字段笔记","field-note-open-back");
                leaveNote.setOnClickListener(unused->{if(canSubmit(loading,leaveNote))returnToNotes.run();});
                new NoteEditorScreen(host,activity,note.title,returnToNotes).load(note.id);
            });
            Button unlink=button(body,"解除关联","field-note-unlink-"+note.id);unlink.setEnabled(!f.archived);
            unlink.setOnClickListener(v->prepareNote(p,unlink,f,note,2));
        }
    }
    private void prepareNote(Page p,View control,CustomFields.Definition shown,NoteRow note,int mode){
        if(!canSubmit(p,control)||shown.archived)return;
        p.submitted=true;
        host.work(()->{
            AppDatabase.FieldEditPlan plan=host.db.prepareFieldEdit(activity,shown.id);
            p.prepared(plan);return plan;
        },plan->{
            p.handoff(plan);
            if(!current(p)){plan.close(); return;}
            CustomFields.Definition actual=plan.definition();
            if(actual.archived||!actual.name.equals(shown.name)||actual.type!=shown.type||!actual.options.equals(shown.options)){
                plan.close();p.submitted=false;host.message("字段已变化，请重新打开笔记列表。",true);return;
            }
            editNote(plan,note,mode);
        },()->{if(current(p))p.submitted=false;});
    }
    private void editNote(AppDatabase.FieldEditPlan plan,NoteRow note,int mode){
        Page p=begin(mode==0?"新建字段笔记":mode==1?"关联已有笔记":"解除笔记关联");p.plan=plan;
        p.root.setContentDescription("field-notes-page");
        LinearLayout body=scroll(p);String field=plan.definition().id;
        Button cancel=button(body,"取消，返回笔记列表","field-note-cancel");
        cancel.setOnClickListener(v->{
            if(!canSubmit(p,cancel))return;
            plan.close();p.plan=null;loadNotes(p,field);
        });
        TextView error=validation(body);
        if(mode==0){
            String id=UUID.randomUUID().toString();
            EditText title=input(body,"field-note-title","笔记标题",false,"");
            Button create=button(body,"创建并关联","field-note-create");
            create.setOnClickListener(v->{
                if(!canSubmit(p,create)||p.plan!=plan)return;
                final String name;
                try{name=ActivityModel.title(title.getText().toString());}
                catch(RuntimeException e){error.setText("笔记标题不能为空。");return;}
                writeNote(p,create,plan,id,name,0,error);
            });
        }else if(mode==1){
            host.work(()->readNotes(field),notes->{
                if(!current(p))return;
                if(notes.available.isEmpty())body.addView(host.text("当前活动没有未关联的笔记。",16,TodayScreen.MUTED));
                for(NoteRow candidate:notes.available){
                    Button pick=button(body,candidate.title+" · "+candidate.id,"field-note-candidate-"+candidate.id);
                    pick.setOnClickListener(v->writeNote(p,pick,plan,candidate.id,null,1,error));
                }
            },()->{
                plan.close();
                if(current(p)){p.plan=null;error.setText("候选笔记读取失败，请取消后重新打开。");}
            });
        }else{
            body.addView(host.text("解除「"+note.title+"」与当前字段的关联？笔记正文和图片将保留。",17,TodayScreen.INK));
            Button confirm=button(body,"确认解除关联，不删除笔记","field-note-unlink-confirm");
            confirm.setOnClickListener(v->writeNote(p,confirm,plan,note.id,null,2,error));
        }
    }
    private void writeNote(Page p,View control,AppDatabase.FieldEditPlan plan,String note,String title,int mode,TextView error){
        if(!canSubmit(p,control)||p.plan!=plan)return;
        p.submitted=true;control.setEnabled(false);
        host.work(()->{
            if(!p.alive){plan.close();throw new IllegalStateException("笔记页面已关闭");}
            if(mode==0)host.db.confirmFieldNoteCreate(plan,note,title);
            else if(mode==1)host.db.confirmFieldNoteLink(plan,note);
            else host.db.confirmFieldNoteUnlink(plan,note);
            return true;
        },ignored->{
            if(current(p)){p.plan=null;loadNotes(p,plan.definition().id);}
        },()->{
            plan.close();
            if(current(p)){p.plan=null;p.submitted=false;error.setText("未能保存，内容可能已变化。请取消后重新打开；本次提交不会重试。");}
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
