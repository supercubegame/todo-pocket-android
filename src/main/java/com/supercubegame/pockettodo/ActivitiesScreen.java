package com.supercubegame.pockettodo;

import android.database.Cursor;
import android.widget.*;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

/** A bounded native slice: category buttons, manual paths, today's explicit marks.
 * Category drag, schedules, application catalog, money and notes UI are subsequent work.
 * Writes go through validated AppDatabase APIs; UI read queries never mutate raw SQL.
 */
public final class ActivitiesScreen {
    private final TodayScreen host;
    long selected;
    ActivitiesScreen(TodayScreen host){this.host=host;}
    private static final class Item {
        long id,category;String title;
        Item(Cursor c){id=c.getLong(0);category=c.getLong(1);title=c.getString(2);}
    }
    private static final class Category {
        long id;String name;List<Item> items=new ArrayList<>();
        Category(long id,String name){this.id=id;this.name=name;}
    }
    private static final class Detail {String title,status;List<String> path;LocalDate day;}
    void load(){if(selected==0)loadCategories();else loadDetail(selected);}
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
        body.addView(host.button("新建分类",()->host.editor("新建分类","分类名称","",false,value->host.db.addCategory(nextId("categories"),value),this::load)));
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
    private void move(long id,int position){host.work(()->{host.db.moveCategory(id,position);return true;},ignored->load(),null);}
    private void loadDetail(long id){
        host.work(()->{
            Detail d=new Detail();
            try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT title FROM activities WHERE id=?",new String[]{Long.toString(id)})){if(!c.moveToFirst())throw new IllegalArgumentException("活动不存在");d.title=c.getString(0);}
            d.path=host.db.path(id);d.day=LocalDate.now(ZoneId.of("Asia/Shanghai"));d.status="未记录";
            for(CalendarRules.Mark mark:host.db.marks(id))if(mark.date.equals(d.day))d.status=mark.status==CalendarRules.Status.DONE?"已完成":"已跳过";
            return d;
        },d->renderDetail(id,d),null);
    }
    private void renderDetail(long id,Detail d){
        LinearLayout body=host.content();body.addView(host.button("返回分类",()->{selected=0;load();}));
        ScrollView scroll=new ScrollView(host.activity);LinearLayout details=host.column();scroll.addView(details);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        details.addView(host.text(d.title,26,TodayScreen.INK));
        TextView note=host.text("手动记录，不会替你操作其他应用",14,TodayScreen.MUTED);note.setPadding(0,host.dp(6),0,host.dp(18));details.addView(note);
        details.addView(host.text(d.day+" · 中国时间",16,TodayScreen.MUTED));
        TextView stamp=host.text("今天："+d.status,24,TodayScreen.ACCENT);stamp.setPadding(host.dp(14),host.dp(16),host.dp(14),host.dp(16));stamp.setBackground(host.shape(TodayScreen.TINT,16));details.addView(stamp);
        LinearLayout marks=new LinearLayout(host.activity);
        marks.addView(host.button("标记完成",()->mark(id,CalendarRules.Status.DONE)),new LinearLayout.LayoutParams(0,host.dp(52),1));
        marks.addView(host.button("跳过今天",()->mark(id,CalendarRules.Status.SKIPPED)),new LinearLayout.LayoutParams(0,host.dp(52),1));details.addView(marks);
        TextView pathTitle=host.text("去哪里操作",20,TodayScreen.INK);pathTitle.setPadding(0,host.dp(18),0,host.dp(8));details.addView(pathTitle);
        if(d.path.isEmpty())details.addView(host.text("把入口一行行记下来，下次不用找。",16,TodayScreen.MUTED));
        for(int i=0;i<d.path.size();i++){TextView step=host.text((i+1)+". "+d.path.get(i),17,TodayScreen.INK);step.setPadding(host.dp(8),host.dp(8),host.dp(8),host.dp(8));details.addView(step);}
        details.addView(host.button("编辑路径",()->host.editor("编辑操作路径","活动路径",String.join("\n",d.path),true,value->{
            List<String> steps=new ArrayList<>();if(!value.isEmpty())for(String step:value.split("\\r?\\n",-1)){if(step.trim().isEmpty())throw new IllegalArgumentException("步骤不能为空");steps.add(step.trim());}
            host.db.savePath(id,steps);
        },this::load)));
    }
    private void mark(long id,CalendarRules.Status status){host.work(()->{host.db.putMark(new CalendarRules.Mark(id,LocalDate.now(ZoneId.of("Asia/Shanghai")),status,"",Instant.now()));return true;},ignored->load(),null);}
}
