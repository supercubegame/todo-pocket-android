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
 * Category drag, schedules, application catalog and notes remain subsequent work.
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
    private static final class Detail {String title,status;List<String> path;LocalDate day;String noteSummary;boolean hasNote;}
    void load(){if(backupPanel)renderBackup();else if(selected==0)loadCategories();else if(historyPanel)loadHistory(selected);else loadDetail(selected);}
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
        LinearLayout top=new LinearLayout(host.activity);
        top.addView(host.button("新建分类",()->host.editor("新建分类","分类名称","",false,value->host.db.addCategory(nextId("categories"),value),this::load)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        top.addView(host.button("备份 / 恢复",()->{backupPanel=true;load();}),new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(top);
        ScrollView scroll=new ScrollView(host.activity);LinearLayout list=host.column();scroll.addView(list);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        if(categories.isEmpty()){TextView empty=host.text("建一个自己的分类。\n例如：每日打卡、农场、提现。",18,TodayScreen.MUTED);empty.setPadding(0,host.dp(24),0,0);list.addView(empty);}
        for(int index=0;index<categories.size();index++){
            Category cat=categories.get(index);final int position=index;
            LinearLayout group=host.column();group.setPadding(host.dp(12),host.dp(12),host.dp(12),host.dp(12));group.setBackground(host.shape(TodayScreen.WHITE,16));
            TextView name=host.text(cat.name,21,TodayScreen.INK);name.setContentDescription("category-name-"+cat.id);group.addView(name);
            LinearLayout actions=new LinearLayout(host.activity);
            Button add=host.button("添加活动",()->host.editor("新建活动","活动名称","",false,value->host.db.addActivity(nextId("activities"),cat.id,0,value),this::load));add.setContentDescription("category-add-"+cat.id);
            Button rename=host.button("改名",()->host.editor("分类改名","分类名称",cat.name,false,value->host.db.renameCategory(cat.id,value),this::load));rename.setContentDescription("category-rename-"+cat.id);
            Button up=host.button("上移",()->move(cat.id,position-1));up.setContentDescription("category-up-"+cat.id);up.setEnabled(index>0);
            Button down=host.button("下移",()->move(cat.id,position+1));down.setContentDescription("category-down-"+cat.id);down.setEnabled(index<categories.size()-1);
            for(Button b:new Button[]{add,rename,up,down})actions.addView(b,new LinearLayout.LayoutParams(0,host.dp(48),1));group.addView(actions);
            if(cat.items.isEmpty())group.addView(host.text("还没有活动",16,TodayScreen.MUTED));
            for(Item item:cat.items){Button open=host.button(item.title,()->{selected=item.id;load();});open.setContentDescription("activity-"+item.id);group.addView(open,new LinearLayout.LayoutParams(-1,-2));}
            host.addRow(list,group);
        }
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
    private void move(long id,int position){host.work(()->{host.db.moveCategory(id,position);return true;},ignored->load(),null);}
    private void loadDetail(long id){
        host.work(()->{
            Detail d=new Detail();
            try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT title FROM activities WHERE id=?",new String[]{Long.toString(id)})){if(!c.moveToFirst())throw new IllegalArgumentException("活动不存在");d.title=c.getString(0);}
            d.path=host.db.path(id);d.day=LocalDate.now(CN);d.status="未记录";
            for(CalendarRules.Mark mark:host.db.marks(id))if(mark.date.equals(d.day))d.status=mark.status==CalendarRules.Status.DONE?"已完成":"已跳过";
            d.hasNote=false;d.noteSummary="";
            List<String> noteIds=new ArrayList<>();
            try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT id FROM notes WHERE activity_id=? ORDER BY rowid",new String[]{Long.toString(id)})){while(c.moveToNext())noteIds.add(c.getString(0));}
            if(!noteIds.isEmpty()){
                List<NoteDocument.Block> blocks=host.db.noteBlocks(noteIds.get(0));
                for(NoteDocument.Block b:blocks)if(b.kind==NoteDocument.Kind.TEXT){d.noteSummary=b.text;break;}
                d.hasNote=!blocks.isEmpty();
            }
            return d;
        },d->renderDetail(id,d),null);
    }
    private void renderDetail(long id,Detail d){
        LinearLayout body=host.content();LinearLayout toolbar=new LinearLayout(host.activity);
        toolbar.addView(host.button("返回分类",()->{selected=0;load();}),new LinearLayout.LayoutParams(0,host.dp(48),1));
        toolbar.addView(host.button("日历账本",()->new CalendarScreen(host,id,d.title,this::load).load()),new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(toolbar);
        ScrollView scroll=new ScrollView(host.activity);LinearLayout details=host.column();scroll.addView(details);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        details.addView(host.text(d.title,26,TodayScreen.INK));
        TextView note=host.text("手动记录，不会替你操作其他应用",14,TodayScreen.MUTED);note.setPadding(0,host.dp(6),0,host.dp(18));details.addView(note);
        details.addView(host.text(d.day+" · 中国时间",16,TodayScreen.MUTED));
        TextView stamp=host.text("今天："+d.status,24,TodayScreen.ACCENT);stamp.setPadding(host.dp(14),host.dp(16),host.dp(14),host.dp(16));stamp.setBackground(host.shape(TodayScreen.TINT,16));details.addView(stamp);
        LinearLayout marks=new LinearLayout(host.activity);
        marks.addView(host.button("标记完成",()->mark(id,LocalDate.now(CN),CalendarRules.Status.DONE)),new LinearLayout.LayoutParams(0,host.dp(52),1));
        marks.addView(host.button("跳过今天",()->mark(id,LocalDate.now(CN),CalendarRules.Status.SKIPPED)),new LinearLayout.LayoutParams(0,host.dp(52),1));details.addView(marks);
        details.addView(host.button("打卡记录",()->{historyPanel=true;load();}));
        if(d.hasNote){TextView preview=host.text(d.noteSummary,15,TodayScreen.MUTED);preview.setContentDescription("note-activity-"+id);preview.setMaxLines(2);details.addView(preview);}
        details.addView(host.button("笔记",()->new NoteEditorScreen(host,id,d.title,this::load).load()));
        TextView pathTitle=host.text("去哪里操作",20,TodayScreen.INK);pathTitle.setPadding(0,host.dp(18),0,host.dp(8));details.addView(pathTitle);
        if(d.path.isEmpty())details.addView(host.text("把入口一行行记下来，下次不用找。",16,TodayScreen.MUTED));
        for(int i=0;i<d.path.size();i++){TextView step=host.text((i+1)+". "+d.path.get(i),17,TodayScreen.INK);step.setPadding(host.dp(8),host.dp(8),host.dp(8),host.dp(8));details.addView(step);}
        details.addView(host.button("编辑路径",()->host.editor("编辑操作路径","活动路径",String.join("\n",d.path),true,value->{
            List<String> steps=new ArrayList<>();if(!value.isEmpty())for(String step:value.split("\\r?\\n",-1)){if(step.trim().isEmpty())throw new IllegalArgumentException("步骤不能为空");steps.add(step.trim());}
            host.db.savePath(id,steps);
        },this::load)));
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
