package com.supercubegame.pockettodo;

import android.app.AlertDialog;
import android.content.Intent;
import android.database.Cursor;
import android.widget.*;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

/** Native category/path/check-in workbench with activity-specific calendar ledger.
 * Category touch sorting retains accessible buttons; catalog supports manual reuse.
 * Writes go through validated AppDatabase APIs; UI read queries never mutate raw SQL.
 */
public final class ActivitiesScreen {
    private final TodayScreen host;
    long selected;
    private boolean backupPanel, historyPanel;
    private static final ZoneId CN=ZoneId.of("Asia/Shanghai");
    ActivitiesScreen(TodayScreen host){this.host=host;}
    private static final class Item {
        long id,category;String title;
        Item(Cursor c){id=c.getLong(0);category=c.getLong(1);title=c.getString(2);}
    }
    private static final class Category {
        long id;String name;List<Item> items=new ArrayList<>();
        Category(long id,String name){this.id=id;this.name=name;}
    }
    private static final class NoteSummary {
        final String id,title,text;
        NoteSummary(String id,String title,String text){this.id=id;this.title=title;this.text=text;}
    }
    private static final class Detail {String title,status;List<String> path,tags;LocalDate day;final List<NoteSummary> notes=new ArrayList<>();}
    void load(){if(categorySession!=null)categorySession.alive=false;if(backupPanel)renderBackup();else if(selected==0)loadCategories();else if(historyPanel)loadHistory(selected);else loadDetail(selected);}
    private long nextId(String table){
        // Only fixed internal table names, and one UI writer on the shared executor.
        if(!table.equals("categories")&&!table.equals("activities"))throw new IllegalArgumentException();
        try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT MAX(id) FROM "+table,null)){c.moveToFirst();return c.isNull(0)?1:Math.incrementExact(c.getLong(0));}
    }
    private void loadCategories(){
        host.work(()->{
            List<Category> result=new ArrayList<>();
            for(long id:host.db.categoryIds()){
                Category cat=new Category(id,host.db.categoryName(id));
                try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT id,category_id,title FROM activities WHERE category_id=? AND archived=0 ORDER BY id",new String[]{Long.toString(id)})){while(c.moveToNext())cat.items.add(new Item(c));}
                result.add(cat);
            }
            return result;
        },this::renderCategories,null);
    }
    private void renderCategories(List<Category> categories){
        LinearLayout body=host.content();body.addView(host.text("长期的事，慢慢积累",22,TodayScreen.INK));
        List<Long> shown=new ArrayList<>();for(Category cat:categories)shown.add(cat.id);
        CategorySession session=new CategorySession(shown);categorySession=session;
        List<android.view.View> groups=new ArrayList<>();
        LinearLayout top=new LinearLayout(host.activity);
        top.addView(host.button("新建分类",()->host.editor("新建分类","分类名称","",false,value->host.db.addCategory(nextId("categories"),value),this::load)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        top.addView(host.button("备份 / 恢复",()->{backupPanel=true;load();}),new LinearLayout.LayoutParams(0,host.dp(48),1));
        top.addView(host.button("应用目录",()->{if(categoryCurrent(session,top))new AppCatalog(host,0,this::load).open(top);}),new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(top);
        ScrollView scroll=new ScrollView(host.activity);LinearLayout list=host.column();scroll.addView(list);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        if(categories.isEmpty()){TextView empty=host.text("建一个自己的分类。\n例如：每日打卡、农场、提现。",18,TodayScreen.MUTED);empty.setPadding(0,host.dp(24),0,0);list.addView(empty);}
        for(int index=0;index<categories.size();index++){
            Category cat=categories.get(index);final int position=index;
            LinearLayout group=host.column();group.setPadding(host.dp(12),host.dp(12),host.dp(12),host.dp(12));group.setBackground(host.shape(TodayScreen.WHITE,16));groups.add(group);
            LinearLayout heading=new LinearLayout(host.activity);heading.setGravity(android.view.Gravity.CENTER_VERTICAL);
            TextView name=host.text(cat.name,21,TodayScreen.INK);name.setContentDescription("category-name-"+cat.id);heading.addView(name,new LinearLayout.LayoutParams(0,-2,1));
            Button reuse=host.button("选应用",()->{if(categoryCurrent(session,group))new AppCatalog(host,cat.id,this::load).open(group);});
            reuse.setContentDescription("category-app-add-"+cat.id);heading.addView(reuse,new LinearLayout.LayoutParams(host.dp(64),host.dp(48)));
            heading.addView(categoryHandle(cat.id,session,list,groups),new LinearLayout.LayoutParams(host.dp(96),host.dp(48)));group.addView(heading);
            LinearLayout actions=new LinearLayout(host.activity);
            Button add=host.button("添加活动",()->host.editor("新建活动","活动名称","",false,value->host.db.addActivity(nextId("activities"),cat.id,0,value),this::load));add.setContentDescription("category-add-"+cat.id);
            Button rename=host.button("改名",()->host.editor("分类改名","分类名称",cat.name,false,value->host.db.renameCategory(cat.id,value),this::load));rename.setContentDescription("category-rename-"+cat.id);
            Button up=host.button("上移",()->moveCategory(cat.id,position-1,session,list));up.setContentDescription("category-up-"+cat.id);up.setEnabled(index>0);
            Button down=host.button("下移",()->moveCategory(cat.id,position+1,session,list));down.setContentDescription("category-down-"+cat.id);down.setEnabled(index<categories.size()-1);
            for(Button b:new Button[]{add,rename,up,down})actions.addView(b,new LinearLayout.LayoutParams(0,host.dp(48),1));group.addView(actions);
            if(cat.items.isEmpty())group.addView(host.text("还没有活动",16,TodayScreen.MUTED));
            for(Item item:cat.items){Button open=host.button(item.title,()->{selected=item.id;load();});open.setContentDescription("activity-"+item.id);group.addView(open,new LinearLayout.LayoutParams(-1,-2));}
            host.addRow(list,group);
        }
    }
    /** One rendered order, shared by touch handles and accessible move buttons.
     * A detached/replaced page or one submitted write makes its callbacks terminal.
     */
    private static final class CategorySession {
        final List<Long> order;
        boolean alive=true,submitted;
        CategorySession(List<Long> order){this.order=new ArrayList<>(order);}
    }
    private CategorySession categorySession;
    private boolean categoryCurrent(CategorySession session,android.view.View anchor){
        return categorySession==session&&session.alive&&!session.submitted&&selected==0&&!backupPanel
            &&anchor.isAttachedToWindow()&&anchor.isEnabled()
            &&!host.activity.isFinishing()&&!host.activity.isDestroyed();
    }
    private void moveCategory(long id,int position,CategorySession session,android.view.View anchor){
        if(!categoryCurrent(session,anchor)||position<0||position>=session.order.size()
            ||!session.order.contains(id)||session.order.indexOf(id)==position)return;
        session.submitted=true;
        host.work(()->host.db.moveCategory(id,session.order,position),changed->load(),()->{
            host.message("未能调整分类顺序；列表可能已变化，请重新进入活动页。",true);
        });
    }
    /** Touch state belongs to this handle, not to a name or a mutable row index.
     * No SQL runs until one valid UP; cancellation and out-of-list UP are read-only.
     */
    private Button categoryHandle(long id,CategorySession session,LinearLayout list,List<android.view.View> groups){
        Button handle=host.button("长按拖动",()->host.message("按住这里，再拖到目标分类。也可使用上下移按钮。",false));
        handle.setContentDescription("category-drag-"+id);
        class Touch implements android.view.View.OnTouchListener,Runnable,android.view.View.OnAttachStateChangeListener {
            boolean pending,active;float startX,startY;int pointer;
            void clear(){
                pending=false;active=false;handle.removeCallbacks(this);handle.setPressed(false);handle.setAlpha(1f);
                if(handle.getParent()!=null)handle.getParent().requestDisallowInterceptTouchEvent(false);
            }
            @Override public void run(){
                if(!pending||!categoryCurrent(session,handle)){clear();return;}
                active=true;handle.setAlpha(0.6f);
                handle.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS);
            }
            @Override public boolean onTouch(android.view.View view,android.view.MotionEvent event){
                int action=event.getActionMasked();
                if(action==android.view.MotionEvent.ACTION_DOWN){
                    clear();
                    if(!categoryCurrent(session,handle)||event.getPointerCount()!=1)return false;
                    pending=true;pointer=event.getPointerId(0);startX=event.getRawX();startY=event.getRawY();
                    handle.setPressed(true);
                    if(handle.getParent()!=null)handle.getParent().requestDisallowInterceptTouchEvent(true);
                    if(!handle.postDelayed(this,android.view.ViewConfiguration.getLongPressTimeout()))clear();
                    return true;
                }
                if(!pending)return false;
                if(!categoryCurrent(session,handle)||event.getPointerCount()!=1||event.getPointerId(0)!=pointer
                    ||action==android.view.MotionEvent.ACTION_CANCEL||action==android.view.MotionEvent.ACTION_POINTER_DOWN
                    ||action==android.view.MotionEvent.ACTION_POINTER_UP){clear();return true;}
                if(action==android.view.MotionEvent.ACTION_MOVE){
                    int slop=android.view.ViewConfiguration.get(host.activity).getScaledTouchSlop();
                    if(!active&&(Math.abs(event.getRawX()-startX)>slop||Math.abs(event.getRawY()-startY)>slop))clear();
                    return true;
                }
                if(action==android.view.MotionEvent.ACTION_UP){
                    boolean drop=active;float x=event.getRawX(),y=event.getRawY();clear();
                    if(!drop){handle.performClick();return true;}
                    android.graphics.Rect visible=new android.graphics.Rect();
                    if(!list.getGlobalVisibleRect(visible)||!visible.contains((int)x,(int)y))return true;
                    int destination=-1;
                    for(int i=0;i<groups.size();i++){
                        android.graphics.Rect row=new android.graphics.Rect();
                        if(groups.get(i).getGlobalVisibleRect(row)&&row.contains((int)x,(int)y)){destination=i;break;}
                    }
                    moveCategory(id,destination,session,handle);return true;
                }
                clear();return true;
            }
            @Override public void onViewAttachedToWindow(android.view.View view){}
            @Override public void onViewDetachedFromWindow(android.view.View view){session.alive=false;clear();}
        }
        Touch touch=new Touch();handle.setOnTouchListener(touch);handle.addOnAttachStateChangeListener(touch);
        return handle;
    }
    private void renderBackup(){
        LinearLayout body=host.content();body.addView(host.text("备份与恢复",24,TodayScreen.INK));
        TextView note=host.text("完整备份包含私有内容，且没有加密；只保存到自己信任的位置。恢复会先显示替换数量，勾选明白后才会确认。",15,TodayScreen.MUTED);note.setPadding(0,host.dp(8),0,host.dp(16));body.addView(note);
        body.addView(host.button("导出完整备份",()->{
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("application/zip");intent.putExtra(Intent.EXTRA_TITLE,"pocket-todo-backup.zip");
            host.activity.startActivityForResult(intent,MainActivity.EXPORT_BACKUP);
        }));
        body.addView(host.button("恢复完整备份",()->{
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("application/zip");
            host.activity.startActivityForResult(intent,MainActivity.IMPORT_BACKUP);
        }));
        body.addView(host.button("返回活动",()->{backupPanel=false;load();}));
    }
    private void loadDetail(long id){
        host.work(()->{
            // One consistent read transaction, no revision changes or image decoding.
            synchronized(host.db){
                android.database.sqlite.SQLiteDatabase sql=host.db.getReadableDatabase();
                sql.beginTransaction();
                try{
                    Detail d=new Detail();
                    try(Cursor c=sql.rawQuery("SELECT title FROM activities WHERE id=?",new String[]{Long.toString(id)})){if(!c.moveToFirst())throw new IllegalArgumentException("活动不存在");d.title=c.getString(0);}
                    d.path=host.db.path(id);d.tags=host.db.tags(id);d.day=LocalDate.now(CN);d.status="未记录";
                    for(CalendarRules.Mark mark:host.db.marks(id))if(mark.date.equals(d.day))d.status=mark.status==CalendarRules.Status.DONE?"已完成":"已跳过";
                    try(Cursor c=sql.rawQuery("SELECT id,title FROM notes WHERE activity_id=? ORDER BY rowid",new String[]{Long.toString(id)})){
                        while(c.moveToNext()){
                            String noteId=c.getString(0);
                            d.notes.add(new NoteSummary(noteId,c.getString(1),NoteDocument.summary(host.db.noteBlocks(noteId))));
                        }
                    }
                    sql.setTransactionSuccessful();return d;
                }finally{sql.endTransaction();}
            }
        },d->renderDetail(id,d),null);
    }
    private void renderDetail(long id,Detail d){
        LinearLayout body=host.content();LinearLayout toolbar=new LinearLayout(host.activity);
        toolbar.addView(host.button("返回分类",()->{selected=0;load();}),new LinearLayout.LayoutParams(0,host.dp(48),1));
        toolbar.addView(host.button("日历账本",()->new CalendarScreen(host,id,d.title,this::load).load()),new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(toolbar);
        FieldScreen fields=new FieldScreen(host,id,this::load);
        Button fieldEntry=host.button("字段",()->{});fieldEntry.setContentDescription("activity-fields-"+id);
        fieldEntry.setOnClickListener(v->{if(selected==id&&!backupPanel&&!historyPanel)fields.open(fieldEntry);});
        toolbar.addView(fieldEntry,new LinearLayout.LayoutParams(0,host.dp(48),1));
        ScrollView scroll=new ScrollView(host.activity);LinearLayout details=host.column();scroll.addView(details);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        details.addView(host.text(d.title,26,TodayScreen.INK));
        TextView note=host.text("手动记录，不会替你操作其他应用",14,TodayScreen.MUTED);note.setPadding(0,host.dp(6),0,host.dp(18));details.addView(note);
        details.addView(host.text(d.day+" · 中国时间",16,TodayScreen.MUTED));
        TextView stamp=host.text("今天："+d.status,24,TodayScreen.ACCENT);stamp.setPadding(host.dp(14),host.dp(16),host.dp(14),host.dp(16));stamp.setBackground(host.shape(TodayScreen.TINT,16));details.addView(stamp);
        LinearLayout marks=new LinearLayout(host.activity);
        marks.addView(host.button("标记完成",()->mark(id,LocalDate.now(CN),CalendarRules.Status.DONE)),new LinearLayout.LayoutParams(0,host.dp(52),1));
        marks.addView(host.button("跳过今天",()->mark(id,LocalDate.now(CN),CalendarRules.Status.SKIPPED)),new LinearLayout.LayoutParams(0,host.dp(52),1));details.addView(marks);
        details.addView(host.button("打卡记录",()->{historyPanel=true;load();}));
        details.addView(host.button("笔记",()->new NoteEditorScreen(host,id,d.title,this::load).load()));
        TextView count=host.text("笔记 · "+d.notes.size()+" 篇",16,TodayScreen.INK);count.setContentDescription("note-count-"+id);details.addView(count);
        if(!d.notes.isEmpty())details.addView(host.text("点击笔记标题可改名；同名笔记分开保存。",14,TodayScreen.MUTED));
        List<String> shown=new ArrayList<>();for(NoteSummary item:d.notes)shown.add(item.id);
        for(int i=0;i<d.notes.size();i++){
            NoteSummary summary=d.notes.get(i);
            LinearLayout actions=new LinearLayout(host.activity);
            TextView heading=host.text((i+1)+". "+summary.title,16,TodayScreen.INK);heading.setContentDescription("note-title-"+summary.id);heading.setMaxLines(2);actions.addView(heading,new LinearLayout.LayoutParams(0,-2,1));
            heading.setMinHeight(host.dp(48));heading.setFocusable(true);heading.setOnClickListener(v->renameNote(id,summary));
            Button delete=host.button("删除",()->deleteNote(id,summary,actions));delete.setContentDescription("note-delete-"+summary.id);
            actions.addView(delete,new LinearLayout.LayoutParams(host.dp(64),host.dp(48)));details.addView(actions);
            TextView preview=host.text(summary.text,15,TodayScreen.MUTED);
            // Keep the old first-note accessibility identity for existing regression.
            preview.setContentDescription(i==0?"note-activity-"+id:"note-summary-"+summary.id);
            preview.setMaxLines(2);preview.setPadding(0,0,0,host.dp(8));details.addView(preview);
            details.addView(noteOrderActions(id,shown,summary,i,actions));
        }
        TextView pathTitle=host.text("去哪里操作",20,TodayScreen.INK);pathTitle.setPadding(0,host.dp(18),0,host.dp(8));details.addView(pathTitle);
        if(d.path.isEmpty())details.addView(host.text("把入口一行行记下来，下次不用找。",16,TodayScreen.MUTED));
        for(int i=0;i<d.path.size();i++){TextView step=host.text((i+1)+". "+d.path.get(i),17,TodayScreen.INK);step.setPadding(host.dp(8),host.dp(8),host.dp(8),host.dp(8));details.addView(step);}
        RelationEditor pathEditor=new RelationEditor(host,id,d.title,false,d.path,this::load);
        Button pathEdit=host.button("编辑路径",()->{});pathEdit.setContentDescription("activity-path-edit-"+id);
        pathEdit.setOnClickListener(v->pathEditor.open(pathEdit));details.addView(pathEdit,new LinearLayout.LayoutParams(-1,-2));
        details.addView(host.text("标签",20,TodayScreen.INK));
        TextView tagText=host.text(d.tags.isEmpty()?"还没有标签":String.join(" · ",d.tags),16,TodayScreen.MUTED);
        tagText.setContentDescription("activity-tags-"+id);details.addView(tagText);
        RelationEditor tagEditor=new RelationEditor(host,id,d.title,true,d.tags,this::load);
        Button tagEdit=host.button("编辑标签",()->{});tagEdit.setContentDescription("activity-tags-edit-"+id);
        tagEdit.setOnClickListener(v->tagEditor.open(tagEdit));details.addView(tagEdit,new LinearLayout.LayoutParams(-1,-2));
    }
    /** Buttons retain the displayed stable-ID sequence, never a title lookup.
     * The backend rejects stale membership/order and owns the single transaction.
     */
    private LinearLayout noteOrderActions(long owner,List<String> shown,NoteSummary note,int index,android.view.View anchor){
        final List<String> displayed=new ArrayList<>(shown);
        LinearLayout row=new LinearLayout(host.activity);
        Button up=host.button("上移",()->moveNote(owner,note.id,displayed,index-1,anchor));
        up.setContentDescription("note-up-"+note.id);up.setEnabled(index>0);
        Button down=host.button("下移",()->moveNote(owner,note.id,displayed,index+1,anchor));
        down.setContentDescription("note-down-"+note.id);down.setEnabled(index<displayed.size()-1);
        row.addView(up,new LinearLayout.LayoutParams(0,host.dp(48),1));
        row.addView(down,new LinearLayout.LayoutParams(0,host.dp(48),1));
        return row;
    }
    private void moveNote(long owner,String note,List<String> displayed,int destination,android.view.View anchor){
        if(selected!=owner||!anchor.isAttachedToWindow()||host.activity.isFinishing()||host.activity.isDestroyed())return;
        host.work(()->host.db.moveNote(note,owner,displayed,destination),changed->load(),()->{
            host.message("未能调整顺序；请返回分类后重新进入，避免使用已变化的列表。",true);
        });
    }
    /** A title-only edit. Opening/cancelling never writes; the captured ID and owner
     * remain fixed even when another note has exactly the same displayed title. */
    private void renameNote(long owner,NoteSummary note){
        LinearLayout body=host.column();body.setPadding(host.dp(20),host.dp(4),host.dp(20),host.dp(8));
        EditText field=host.field("笔记标题",false);field.setContentDescription("note-rename-title");field.setText(note.title);body.addView(field,new LinearLayout.LayoutParams(-1,-2));
        TextView validation=host.text("只改这一篇的标题，不改变正文、图片或顺序。",14,TodayScreen.MUTED);body.addView(validation);
        AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("笔记改名").setView(body).setNegativeButton("取消",null).setPositiveButton("保存标题",null).create();
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String value=field.getText().toString().trim();
            if(value.isEmpty()){validation.setText("笔记标题不能为空");validation.setTextColor(TodayScreen.ERROR);return;}
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);field.setEnabled(false);
            host.work(()->host.db.renameNote(note.id,owner,note.title,value),changed->{dialog.dismiss();load();},()->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);field.setEnabled(true);
                validation.setText("未能改名；请取消后重新打开，避免覆盖已变化的标题。");validation.setTextColor(TodayScreen.ERROR);
            });
        }));
        dialog.show();
    }
    /** A detached detail row cannot confirm an old preview. Rotation/process death
     * never persists this plan; helper close is a second backend invalidation guard.
     */
    private void deleteNote(long owner,NoteSummary note,android.view.View anchor){
        host.work(()->host.db.prepareNoteDeletion(note.id,owner),plan->{
            if(!anchor.isAttachedToWindow()||host.activity.isFinishing()||host.activity.isDestroyed()){plan.close();return;}
            LinearLayout body=host.column();body.setPadding(host.dp(20),host.dp(4),host.dp(20),host.dp(8));
            TextView identity=host.text("活动："+plan.activityTitle()+"\n笔记："+plan.title()+"\n笔记标识："+plan.noteId(),15,TodayScreen.INK);
            identity.setContentDescription("note-delete-identity");body.addView(identity);
            TextView counts=host.text("将删除 "+plan.blockCount()+" 个正文块、"+plan.fieldLinkCount()+" 个字段笔记关联。\n字段和值、其他笔记和图片文件均保留。",15,TodayScreen.INK);
            counts.setContentDescription("note-delete-counts");body.addView(counts);
            body.addView(host.text("删除后暂不支持撤销。取消不会修改任何内容。",15,TodayScreen.ERROR));
            CheckBox consent=new CheckBox(host.activity);consent.setText("我明白只删除这一篇，且无法撤销");consent.setTextSize(16);consent.setTextColor(TodayScreen.INK);
            consent.setContentDescription("note-delete-consent");consent.setChecked(false);body.addView(consent);
            TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("note-delete-validation");body.addView(validation);
            ScrollView scroll=new ScrollView(host.activity);scroll.addView(body);
            AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("确认删除笔记？").setView(scroll).setNegativeButton("取消",null).setPositiveButton("确认删除",null).create();
            android.view.View.OnAttachStateChangeListener lifecycle=new android.view.View.OnAttachStateChangeListener(){
                @Override public void onViewAttachedToWindow(android.view.View v){}
                @Override public void onViewDetachedFromWindow(android.view.View v){plan.close();dialog.dismiss();}
            };
            anchor.addOnAttachStateChangeListener(lifecycle);
            dialog.setOnDismissListener(unused->{anchor.removeOnAttachStateChangeListener(lifecycle);plan.close();});
            dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
                if(!consent.isChecked()){validation.setText("请先勾选删除确认");return;}
                if(!anchor.isAttachedToWindow()){plan.close();dialog.dismiss();return;}
                dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);consent.setEnabled(false);
                host.work(()->{host.db.confirmNoteDeletion(plan);return true;},ignored->{dialog.dismiss();load();},()->{
                    plan.close();dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);
                    validation.setText("未能删除；内容可能已变化。请取消后重新预览。");
                });
            }));
            dialog.show();
        },null);
    }
    /** Dedicated editor owns its preview until queued work has completed.
     * Detachment closes it before execution; no old dialog can edit another activity. */
    private static final class RelationEditor {
        private final TodayScreen host;
        private final long id;
        private final String title;
        private final boolean tags;
        private final List<String> shown;
        private final Runnable back;
        private AppDatabase.ActivityStringsPlan plan;
        private LinearLayout root;
        private boolean opening,alive,submitted;
        RelationEditor(TodayScreen host,long id,String title,boolean tags,List<String> shown,Runnable back){
            this.host=host;this.id=id;this.title=title;this.tags=tags;
            this.shown=new ArrayList<>(shown);this.back=back;
        }
        private boolean active(){
            return alive&&root!=null&&root.isAttachedToWindow()&&!host.activity.isFinishing()&&!host.activity.isDestroyed();
        }
        private void close(){alive=false;if(plan!=null){plan.close();plan=null;}}
        void open(android.view.View anchor){
            if(opening||!anchor.isAttachedToWindow()||!anchor.isEnabled()||host.activity.isFinishing()||host.activity.isDestroyed())return;
            opening=true;
            host.work(()->host.db.prepareActivityStrings(id,tags),p->{
                if(!anchor.isAttachedToWindow()||host.activity.isFinishing()||host.activity.isDestroyed()
                    ||p.activityId()!=id||!title.equals(p.title())||!shown.equals(p.values())){
                    p.close();host.message("活动内容已变化，请重新进入后编辑。",true);return;
                }
                plan=p;render();
            },()->host.message("未能读取编辑内容，请重新进入活动。",true));
        }
        private void render(){
            LinearLayout body=host.content();root=host.column();body.addView(root,new LinearLayout.LayoutParams(-1,-1));alive=true;
            root.addOnAttachStateChangeListener(new android.view.View.OnAttachStateChangeListener(){
                @Override public void onViewAttachedToWindow(android.view.View v){}
                @Override public void onViewDetachedFromWindow(android.view.View v){close();}
            });
            root.addView(host.text(tags?"编辑标签":"编辑操作路径",24,TodayScreen.INK));
            TextView identity=host.text(title+" · #"+id,16,TodayScreen.MUTED);identity.setContentDescription("relation-identity");root.addView(identity);
            ScrollView scroll=new ScrollView(host.activity);LinearLayout fields=host.column();scroll.addView(fields);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
            fields.addView(host.text(tags?"每行一个标签，重复标签保留首次出现的位置。清空全部文字可移除标签。":"每行一步，顺序和重复步骤保留。清空全部文字可移除路径。",15,TodayScreen.MUTED));
            EditText input=host.field(tags?"活动标签":"活动路径",true);input.setText(String.join("\n",plan.values()));fields.addView(input,new LinearLayout.LayoutParams(-1,-2));
            TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("relation-validation");fields.addView(validation);
            Button save=host.button("保存",()->{});save.setContentDescription("relation-save");
            Button cancel=host.button("取消",()->{});cancel.setContentDescription("relation-cancel");
            cancel.setOnClickListener(v->{if(active()&&cancel.isEnabled()){close();back.run();}});
            save.setOnClickListener(v->{
                if(!active()||submitted||!save.isEnabled())return;
                String value=input.getText().toString();List<String> values=new ArrayList<>();
                if(!value.isEmpty())for(String part:value.split("\\r?\\n",-1)){
                    String clean=part.trim();if(clean.isEmpty()){validation.setText(tags?"标签不能为空行":"步骤不能为空");return;}values.add(clean);
                }
                submitted=true;save.setEnabled(false);cancel.setEnabled(false);input.setEnabled(false);
                final AppDatabase.ActivityStringsPlan attempt=plan;
                host.work(()->host.db.confirmActivityStrings(attempt,values),changed->{
                    boolean present=active();close();if(present)back.run();
                },()->{
                    attempt.close();
                    if(active()){validation.setText("未能保存；内容可能已变化，请取消后重新打开。");cancel.setEnabled(true);}
                });
            });
            root.addView(save,new LinearLayout.LayoutParams(-1,-2));root.addView(cancel,new LinearLayout.LayoutParams(-1,-2));
        }
    }

    private void loadHistory(long id){host.work(()->host.db.marks(id),marks->renderHistory(id,marks),null);}
    private void renderHistory(long id,List<CalendarRules.Mark> marks){
        LinearLayout body=host.content();body.addView(host.text("打卡记录",24,TodayScreen.INK));
        TextView note=host.text("记录的是哪一天，与哪天写下它分开保存。可以补记过去或改回未记录。",15,TodayScreen.MUTED);note.setPadding(0,host.dp(8),0,host.dp(16));body.addView(note);
        body.addView(host.button("补记 / 修改",()->editMark(id,LocalDate.now(CN).toString(),CalendarRules.Status.DONE)));
        ScrollView scroll=new ScrollView(host.activity);LinearLayout list=host.column();scroll.addView(list);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        if(marks.isEmpty()){TextView empty=host.text("还没有记录。",18,TodayScreen.MUTED);empty.setPadding(0,host.dp(24),0,0);list.addView(empty);}
        for(int i=marks.size()-1;i>=0;i--){
            CalendarRules.Mark mark=marks.get(i);String day=mark.date.toString();
            LinearLayout row=new LinearLayout(host.activity);row.setGravity(android.view.Gravity.CENTER_VERTICAL);row.setPadding(host.dp(8),host.dp(4),host.dp(4),host.dp(4));row.setBackground(host.shape(TodayScreen.WHITE,14));
            TextView text=host.text(day+" · "+(mark.status==CalendarRules.Status.DONE?"已完成":"已跳过"),17,TodayScreen.INK);text.setContentDescription("checkin-"+day);row.addView(text,new LinearLayout.LayoutParams(0,-2,1));
            Button edit=host.button("修改",()->editMark(id,day,mark.status));edit.setContentDescription("edit-checkin-"+day);row.addView(edit,new LinearLayout.LayoutParams(host.dp(64),host.dp(48)));
            host.addRow(list,row);
        }
        body.addView(host.button("返回活动",()->{historyPanel=false;load();}));
    }
    /** Backdate or correct a day. The chosen day is the activity date; the entry
     * timestamp is written by the backend at save time and stays distinct.
     * 未记录 deletes the row rather than storing a third visible state.
     */
    private void editMark(long id,String day,CalendarRules.Status current){
        if(historyPanel==false)return;
        LinearLayout body=host.column();body.setPadding(host.dp(20),host.dp(4),host.dp(20),host.dp(8));
        EditText field=host.field("打卡日期",false);field.setText(day);body.addView(field,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout statuses=new LinearLayout(host.activity);
        Button done=host.button("已完成",()->{});done.setContentDescription("checkin-status-DONE");
        Button skipped=host.button("已跳过",()->{});skipped.setContentDescription("checkin-status-SKIPPED");
        Button unrecorded=host.button("标记未记录",()->{});unrecorded.setContentDescription("checkin-status-UNRECORDED");
        for(Button b:new Button[]{done,skipped,unrecorded})statuses.addView(b,new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(statuses);
        TextView validation=host.text("",14,TodayScreen.ERROR);body.addView(validation);
        final CalendarRules.Status[] picked={current==null?CalendarRules.Status.DONE:current};
        done.setOnClickListener(v->{picked[0]=CalendarRules.Status.DONE;done.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.ACCENT));done.setTextColor(TodayScreen.WHITE);skipped.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.TINT));skipped.setTextColor(TodayScreen.ACCENT);unrecorded.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.TINT));unrecorded.setTextColor(TodayScreen.ACCENT);});
        skipped.setOnClickListener(v->{picked[0]=CalendarRules.Status.SKIPPED;skipped.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.ACCENT));skipped.setTextColor(TodayScreen.WHITE);done.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.TINT));done.setTextColor(TodayScreen.ACCENT);unrecorded.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.TINT));unrecorded.setTextColor(TodayScreen.ACCENT);});
        unrecorded.setOnClickListener(v->{picked[0]=CalendarRules.Status.UNRECORDED;unrecorded.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.ACCENT));unrecorded.setTextColor(TodayScreen.WHITE);done.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.TINT));done.setTextColor(TodayScreen.ACCENT);skipped.setBackgroundTintList(android.content.res.ColorStateList.valueOf(TodayScreen.TINT));skipped.setTextColor(TodayScreen.ACCENT);});
        if(picked[0]==CalendarRules.Status.DONE)done.performClick();else if(picked[0]==CalendarRules.Status.SKIPPED)skipped.performClick();
        AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("补记 / 修改打卡").setView(body).setNegativeButton("取消",null).setPositiveButton("保存记录",null).create();
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String input=field.getText().toString().trim();LocalDate date;
            try{date=LocalDate.parse(input);if(!date.toString().equals(input))throw new IllegalArgumentException();}
            catch(Exception e){validation.setText("日期格式应为 2026-09-21");return;}
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);field.setEnabled(false);
            host.work(()->{host.db.putMark(new CalendarRules.Mark(id,date,picked[0],"",Instant.now()));return true;},ignored->{dialog.dismiss();load();},()->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);field.setEnabled(true);validation.setText("未能保存，请检查内容后重试");
            });
        }));
        dialog.show();
    }
    private void mark(long id,LocalDate day,CalendarRules.Status status){host.work(()->{host.db.putMark(new CalendarRules.Mark(id,day,status,"",Instant.now()));return true;},ignored->load(),null);}
}
