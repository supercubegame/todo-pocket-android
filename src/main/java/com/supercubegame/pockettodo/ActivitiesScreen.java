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
    private boolean backupPanel, historyPanel, archivePanel;
    private boolean compactOrder;
    private int compactScrollY;
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
    private static final class Detail {String title,status;boolean archived;List<String> path,tags;LocalDate day;List<String> history=new ArrayList<>();final List<NoteSummary> notes=new ArrayList<>();}
    // Search reads only activity/category metadata, never notes, field values, money or marks.
    private static final String SEARCH_COLS="SELECT a.id,a.category_id,c.name,a.title,a.archived FROM activities a JOIN categories c ON c.id=a.category_id ";
    static final int SEARCH_PAGE=24;
    static final String SEARCH_MATCH=SEARCH_COLS+"WHERE a.id>CAST(? AS INTEGER) AND (a.archived=0 OR ?='1') AND instr(lower(a.title),lower(?))>0 ORDER BY a.id LIMIT 25";
    static final String SEARCH_BY_ID=SEARCH_COLS+"WHERE a.id=CAST(? AS INTEGER)";
    static final class SearchHit {
        final long id,category;final String categoryName,title;final boolean archived;
        SearchHit(Cursor c){id=c.getLong(0);category=c.getLong(1);categoryName=c.getString(2);title=c.getString(3);archived=c.getInt(4)!=0;}
        boolean same(SearchHit h){return h!=null&&id==h.id&&category==h.category&&archived==h.archived&&title.equals(h.title)&&categoryName.equals(h.categoryName);}
        String label(){return title+"\n"+categoryName+" · 活动 #"+id+(archived?" · 已归档":"");}
    }
    static final class SearchFlow {
        String text="";boolean archives,submitted;long epoch,opened;
        final ArrayList<Long> pages=new ArrayList<>();SearchFlow(){pages.add(0L);}
        long after(){return pages.get(pages.size()-1);}
        void change(String query,boolean include){text=query;archives=include;submitted=false;pages.clear();pages.add(0L);epoch++;}
    }
    private SearchFlow searchFlow;
    void leaveSearch(){if(searchFlow!=null){searchFlow.epoch++;searchFlow=null;}}
    private boolean searchDetail(long id){return id>0&&searchFlow!=null&&searchFlow.opened==id&&selected==id;}
    boolean backFromSearch(){
        if(searchFlow==null)return false;
        if(searchDetail(selected)){searchFlow.opened=0;selected=0;historyPanel=false;archivePanel=false;load();return true;}
        if(selected==0){leaveSearch();load();return true;}return false;
    }
    static List<SearchHit> searchRead(android.database.sqlite.SQLiteDatabase db,String raw,boolean archives,long after){
        String term=raw.trim();List<SearchHit> hits=new ArrayList<>();if(term.isEmpty()||after<0)return hits;
        try(Cursor c=db.rawQuery(SEARCH_MATCH,new String[]{Long.toString(after),archives?"1":"0",term})){while(c.moveToNext())hits.add(new SearchHit(c));}return hits;
    }
    static boolean searchStillCurrent(android.database.sqlite.SQLiteDatabase db,SearchHit hit){
        try(Cursor c=db.rawQuery(SEARCH_BY_ID,new String[]{Long.toString(hit.id)})){return c.moveToFirst()&&hit.same(new SearchHit(c))&&!c.moveToNext();}
    }
    private final class SearchPage {
        final SearchFlow s;final ScrollView scroll;final LinearLayout panel,rows;final EditText input;final CheckBox archives;final TextView help;
        SearchPage(SearchFlow state){
            s=state;LinearLayout body=host.content();scroll=new ScrollView(host.activity);scroll.setTag("activity-search-scroll");panel=host.column();panel.setFocusableInTouchMode(true);scroll.addView(panel);body.addView(scroll,new LinearLayout.LayoutParams(-1,-1));
            LinearLayout bar=new LinearLayout(host.activity);bar.addView(host.text("搜索活动",22,TodayScreen.INK),new LinearLayout.LayoutParams(0,-2,1));Button back=host.button("返回分类",()->{if(active())backFromSearch();});back.setTag("activity-search-back");bar.addView(back);panel.addView(bar);
            input=host.field("活动标题关键词",false);input.setTag("activity-search-query");input.setHint("输入活动标题");input.setText(s.text);input.setSelection(input.length());input.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH);panel.addView(input,new LinearLayout.LayoutParams(-1,-2));
            LinearLayout actions=new LinearLayout(host.activity);archives=new CheckBox(host.activity);archives.setText("包含已归档");archives.setMinHeight(host.dp(48));archives.setTag("activity-search-archives");archives.setChecked(s.archives);actions.addView(archives,new LinearLayout.LayoutParams(0,-2,1));Button go=host.button("搜索",()->submit(true));go.setTag("activity-search-submit");actions.addView(go);panel.addView(actions);
            help=host.text("输入标题后搜索，只查活动名称。",15,TodayScreen.MUTED);help.setTag("activity-search-status");help.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);panel.addView(help);rows=host.column();panel.addView(rows);panel.requestFocus();
            input.addTextChangedListener(new android.text.TextWatcher(){public void beforeTextChanged(CharSequence x,int st,int ct,int af){}public void onTextChanged(CharSequence x,int st,int before,int count){changed();}public void afterTextChanged(android.text.Editable e){}});
            archives.setOnCheckedChangeListener((button,on)->changed());input.setOnEditorActionListener((v,action,event)->{if(action!=android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH)return false;submit(true);return true;});
            if(s.submitted)submit(false);
        }
        boolean active(){return searchFlow==s&&s.opened==0&&selected==0&&scroll.isAttachedToWindow()&&!host.activity.isFinishing()&&!host.activity.isDestroyed();}
        void changed(){if(!active())return;s.change(input.getText().toString(),archives.isChecked());rows.removeAllViews();help.setText("输入标题后搜索，只查活动名称。");}
        void submit(boolean fresh){
            if(!active())return;if(fresh)s.change(input.getText().toString(),archives.isChecked());
            final String term=s.text.trim();final long cursor=s.after();final boolean include=s.archives;final long ticket=++s.epoch;
            rows.removeAllViews();if(term.isEmpty()){s.submitted=false;help.setText("请输入活动标题。");return;}
            android.view.inputmethod.InputMethodManager ime=(android.view.inputmethod.InputMethodManager)host.activity.getSystemService(android.content.Context.INPUT_METHOD_SERVICE);if(ime!=null)ime.hideSoftInputFromWindow(input.getWindowToken(),0);panel.requestFocus();
            help.setText("正在搜索…");s.submitted=true;
            host.work(()->searchRead(host.db.getReadableDatabase(),term,include,cursor),hits->{
                if(!active()||ticket!=s.epoch)return;int n=Math.min(SEARCH_PAGE,hits.size());help.setText(n==0?"没有匹配的活动。":"第 "+s.pages.size()+" 页 · 本页 "+n+" 项");
                for(int i=0;i<n;i++){final SearchHit hit=hits.get(i);Button open=host.button(hit.label(),()->{});open.setTag("activity-search-hit-"+hit.id);open.setContentDescription(hit.label().replace('\n','，'));open.setOnClickListener(v->{if(!active()||!open.isEnabled()||!open.isAttachedToWindow()||s.epoch!=ticket)return;
                    host.work(()->searchStillCurrent(host.db.getReadableDatabase(),hit),valid->{if(!active()||s.epoch!=ticket)return;if(!valid){help.setText("活动已变化，请重新搜索。");s.epoch++;rows.removeAllViews();return;}
                        s.epoch++;s.opened=hit.id;selected=hit.id;historyPanel=false;archivePanel=false;load();},()->{if(active())help.setText("无法读取这项活动，请重新搜索。");});});rows.addView(open,new LinearLayout.LayoutParams(-1,-2));}
                if(s.pages.size()>1)addPage("上一页",false,0,ticket);if(hits.size()>SEARCH_PAGE)addPage("下一页",true,hits.get(n-1).id,ticket);
                host.message("本机搜索 · 未修改数据",false);scroll.scrollTo(0,0);
            },()->{if(active()&&s.epoch==ticket){s.submitted=false;help.setText("搜索未完成，请再试一次。");}});
        }
        void addPage(String label,boolean next,long lower,long ticket){Button b=host.button(label,()->{if(!active()||s.epoch!=ticket)return;if(next)s.pages.add(lower);else s.pages.remove(s.pages.size()-1);submit(false);});b.setTag(next?"activity-search-next":"activity-search-previous");rows.addView(b,new LinearLayout.LayoutParams(-1,-2));}
    }

    void load(){if(shortcutOrigin!=null&&selected!=shortcutOrigin.target)shortcutOrigin=null;if(categorySession!=null)categorySession.alive=false;if(backupPanel)renderBackup();else if(selected==0){if(archivePanel)loadArchivedActivities();else if(searchFlow!=null)new SearchPage(searchFlow);else loadCategories();}else if(historyPanel)loadHistory(selected);else loadDetail(selected);}
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
        LinearLayout body=host.content();
        List<Long> shown=new ArrayList<>();for(Category cat:categories)shown.add(cat.id);
        CategorySession session=new CategorySession(shown);categorySession=session;
        final boolean orderOnly=compactOrder;
        LinearLayout title=new LinearLayout(host.activity);title.setGravity(android.view.Gravity.CENTER_VERTICAL);
        title.addView(host.text(orderOnly?"分类排序":"活动",22,TodayScreen.INK),new LinearLayout.LayoutParams(0,-2,1));
        if(!orderOnly){Button search=host.button("搜索",()->{if(!categoryCurrent(session,title))return;searchFlow=new SearchFlow();load();});search.setTag("activity-search-open");search.setContentDescription("按活动标题搜索");title.addView(search,new LinearLayout.LayoutParams(-2,-2));}
        Button mode=host.button(orderOnly?"返回活动":"分类排序",()->setCategoryOrderMode(session,title,!orderOnly));
        mode.setContentDescription(orderOnly?"category-order-leave":"category-order-enter");
        categorySpeech(mode,orderOnly?"返回活动列表":"整理分类顺序");
        title.addView(mode,new LinearLayout.LayoutParams(-2,-2));body.addView(title);
        if(orderOnly){renderCompactOrder(body,categories,session);return;}
        List<android.view.View> groups=new ArrayList<>();
        LinearLayout top=new LinearLayout(host.activity);
        top.addView(host.button("新建分类",()->host.editor("新建分类","分类名称","",false,value->host.db.addCategory(nextId("categories"),value),this::load)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        top.addView(host.button("备份 / 恢复",()->{backupPanel=true;load();}),new LinearLayout.LayoutParams(0,host.dp(48),1));
        top.addView(host.button("应用目录",()->{if(categoryCurrent(session,top))new AppCatalog(host,0,this::load).open(top);}),new LinearLayout.LayoutParams(0,host.dp(48),1));
        Button archived=host.button("已归档",()->{archivePanel=true;historyPanel=false;load();});
        archived.setContentDescription("archived-activities");top.addView(archived,new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(top);
        ScrollView scroll=new ScrollView(host.activity);scroll.setContentDescription("activity-list-scroll");LinearLayout list=host.column();scroll.addView(list);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
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
            if(host.db.shortcutsEnabled()){
                Button shortcuts=host.button("快捷入口",()->openShortcuts(cat.id,session,group));
                shortcuts.setContentDescription("shortcut-manage-"+cat.id);categorySpeech(shortcuts,"管理快捷入口，分类 "+cat.name+"，编号 "+cat.id);
                group.addView(shortcuts,new LinearLayout.LayoutParams(-1,-2));
            }
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
    private boolean categoryHere(CategorySession session,android.view.View anchor){
        return categorySession==session&&session.alive&&selected==0&&!backupPanel
            &&!archivePanel&&searchFlow==null&&anchor.isAttachedToWindow()&&anchor.isEnabled()
            &&!host.activity.isFinishing()&&!host.activity.isDestroyed();
    }
    private boolean categoryCurrent(CategorySession session,android.view.View anchor){
        return !session.submitted&&categoryHere(session,anchor);
    }
    /** Navigation has no write. A failed order can still leave the sorting view. */
    private void setCategoryOrderMode(CategorySession session,android.view.View anchor,boolean next){
        if(!categoryHere(session,anchor)||compactOrder==next)return;
        changeCategoryOrderMode(session,next);
    }
    private void changeCategoryOrderMode(CategorySession session,boolean next){
        session.alive=false;compactOrder=next;compactScrollY=0;load();
    }
    boolean backFromCategoryOrder(){
        CategorySession current=categorySession;
        if(!compactOrder||current==null||!current.alive||selected!=0||backupPanel||archivePanel
                ||host.activity.isFinishing()||host.activity.isDestroyed())return false;
        changeCategoryOrderMode(current,false);return true;
    }
    private static void categorySpeech(android.view.View view,String label){
        view.setAccessibilityDelegate(new android.view.View.AccessibilityDelegate(){
            @Override public void onInitializeAccessibilityNodeInfo(android.view.View source,android.view.accessibility.AccessibilityNodeInfo info){
                super.onInitializeAccessibilityNodeInfo(source,info);info.setContentDescription(label);
            }
        });
    }
    static boolean compactSortStacked(int widthDp,float fontScale){
        return widthDp<300||fontScale>=1.3f;
    }
    private void renderCompactOrder(LinearLayout body,List<Category> categories,CategorySession session){
        body.addView(host.text("长按拖动到目标分类，或用上移、下移。",14,TodayScreen.MUTED));
        ScrollView scroll=new ScrollView(host.activity);scroll.setContentDescription("category-order-scroll");
        LinearLayout list=host.column();scroll.addView(list);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        final int restoreY=compactScrollY;
        scroll.setOnScrollChangeListener((v,x,y,oldX,oldY)->{
            if(compactOrder&&categorySession==session&&session.alive&&scroll.isAttachedToWindow())compactScrollY=y;
        });
        if(restoreY>0)scroll.addOnLayoutChangeListener(new android.view.View.OnLayoutChangeListener(){
            public void onLayoutChange(android.view.View v,int l,int t,int r,int b,int ol,int ot,int orr,int ob){
                if(b<=t)return;scroll.removeOnLayoutChangeListener(this);
                if(compactOrder&&categorySession==session&&session.alive&&scroll.isAttachedToWindow())scroll.scrollTo(0,restoreY);
            }
        });
        if(categories.isEmpty()){list.addView(host.text("还没有分类。返回活动页可新建。",16,TodayScreen.MUTED));return;}
        boolean stacked=compactSortStacked(host.activity.getResources().getConfiguration().screenWidthDp,
                host.activity.getResources().getConfiguration().fontScale);
        List<android.view.View> groups=new ArrayList<>();
        for(int i=0;i<categories.size();i++){
            Category category=categories.get(i);final long id=category.id;final int position=i;
            LinearLayout card=host.column();card.setContentDescription("category-order-row-"+id);
            card.setBackground(host.shape(TodayScreen.WHITE,12));card.setPadding(host.dp(6),host.dp(2),host.dp(6),host.dp(2));
            card.setImportantForAccessibility(android.view.View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            groups.add(card);LinearLayout line=new LinearLayout(host.activity);line.setGravity(android.view.Gravity.CENTER_VERTICAL);
            TextView name=host.text(category.name,17,TodayScreen.INK);name.setContentDescription("category-name-"+id);
            if(stacked)card.addView(name,new LinearLayout.LayoutParams(-1,-2));else line.addView(name,new LinearLayout.LayoutParams(0,-2,1));
            Button drag=categoryHandle(id,session,list,groups);drag.setText("拖动");
            Button up=host.button("上移",()->moveCategory(id,position-1,session,list));up.setContentDescription("category-up-"+id);up.setEnabled(i>0);
            Button down=host.button("下移",()->moveCategory(id,position+1,session,list));down.setContentDescription("category-down-"+id);down.setEnabled(i+1<categories.size());
            String spoken=category.name+"，第"+(i+1)+"项，共"+categories.size()+"项";
            categorySpeech(name,spoken);categorySpeech(drag,"长按拖动："+spoken);categorySpeech(up,"上移："+spoken);categorySpeech(down,"下移："+spoken);
            for(Button control:new Button[]{drag,up,down})line.addView(control,stacked?new LinearLayout.LayoutParams(0,-2,1):new LinearLayout.LayoutParams(host.dp(control==drag?60:48),-2));
            card.addView(line,new LinearLayout.LayoutParams(-1,-2));host.addRow(list,card);
        }
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
    /** This gate is exercised as actual Java by the host controls. */
    static boolean shortcutCanAct(boolean alive,boolean submitted,boolean attached,
                                  boolean enabled,boolean finishing,boolean destroyed){
        return alive&&!submitted&&attached&&enabled&&!finishing&&!destroyed;
    }
    /** Transient origin for a detail opened through a shortcut. No persistence and no reusable DB permission. */
    private static final class ShortcutOrigin {
        final long category,application,target;android.view.View back;
        ShortcutOrigin(long c,long a,long t){category=c;application=a;target=t;}
    }
    private ShortcutOrigin shortcutOrigin;
    private ShortcutPage shortcutShowing;
    private ShortcutOrigin shortcutFor(long id){return id>0&&selected==id&&shortcutOrigin!=null&&shortcutOrigin.target==id?shortcutOrigin:null;}
    void leaveActivityNavigation(){leaveSearch();shortcutOrigin=null;if(shortcutShowing!=null)shortcutShowing.close();}
    private boolean usableShortcut(){return !host.activity.isFinishing()&&!host.activity.isDestroyed();}
    private boolean returnFromShortcut(ShortcutOrigin from,android.view.View back){
        if(from==null||back==null||from!=shortcutFor(selected)||from.back!=back||!back.isAttachedToWindow()||!back.isShown()||!back.isEnabled()||!usableShortcut())return false;
        // Consume the origin before posting work. The old selector and its plan were closed on entry.
        from.back=null;shortcutOrigin=null;selected=0;historyPanel=false;archivePanel=false;
        ShortcutPage pending=shortcutPage("返回快捷目标");
        TextView hint=host.text("正在核对原来的快捷入口…",16,TodayScreen.MUTED);hint.setTag("shortcut-return-status");hint.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);pending.root.addView(hint);
        Runnable unavailable=()->{if(!pending.current(pending.root))return;hint.setText("原快捷入口已移除或不可用，请返回分类。");host.message("未打开其他活动，也未修改数据。",false);};
        host.work(()->host.db.prepareShortcut(from.category,from.application),fresh->{
            if(!pending.current(pending.root)){fresh.close();return;}
            if(!fresh.enabled||fresh.category!=from.category||fresh.application!=from.application){fresh.close();unavailable.run();return;}
            showShortcutTargets(fresh);
        },unavailable,AppDatabase.ShortcutPlan::close);return true;
    }
    boolean backFromShortcut(){
        if(!usableShortcut())return false;
        ShortcutPage p=shortcutShowing;
        if(p!=null&&p.current(p.root)){p.close();shortcutOrigin=null;selected=0;historyPanel=false;archivePanel=false;load();return true;}
        ShortcutOrigin from=shortcutFor(selected);return from!=null&&returnFromShortcut(from,from.back);
    }
    private Button detailBack(long id,boolean archived){
        final ShortcutOrigin from=shortcutFor(id);String label=from!=null?"返回快捷目标":searchDetail(id)?"返回搜索":archived?"返回归档列表":"返回分类";
        Button back=host.button(label,()->{});if(from!=null){from.back=back;back.setTag("shortcut-detail-back");}
        back.setOnClickListener(v->{if(!back.isEnabled()||!back.isAttachedToWindow()||!back.isShown()||!usableShortcut()||selected!=id)return;
            if(from!=null){returnFromShortcut(from,back);return;}if(searchDetail(id)){backFromSearch();return;}
            selected=0;archivePanel=archived;historyPanel=false;load();});return back;
    }
    private static final String SHORTCUT_TARGET_SQL="SELECT a.title,c.name,c.id FROM activities a JOIN categories c ON c.id=a.category_id WHERE a.id=? AND a.application_id=? AND a.archived=0";
    static String shortcutOriginLabel(String category,long cid,String app,long aid){return "入口分类："+category+" · #"+cid+"\n应用："+app+" · #"+aid;}
    static String shortcutTargetLabel(String title,long id,String category,long cid){return title+" · 活动 #"+id+"\n所属分类："+category+" · #"+cid;}
    private final class ShortcutPage {
        final LinearLayout root;
        AppDatabase.ShortcutPlan plan;
        boolean alive=true,submitted;
        ShortcutPage(LinearLayout root){this.root=root;}
        boolean current(android.view.View control){
            return shortcutShowing==this&&shortcutCanAct(alive,submitted,root.isAttachedToWindow(),
                control.isAttachedToWindow()&&control.isEnabled(),host.activity.isFinishing(),host.activity.isDestroyed());
        }
        void close(){alive=false;if(shortcutShowing==this)shortcutShowing=null;if(plan!=null){plan.close();plan=null;}}
    }
    private static final class ShortcutEntry {
        final long id;final String name;final boolean enabled;
        ShortcutEntry(long id,String name,boolean enabled){this.id=id;this.name=name;this.enabled=enabled;}
    }
    private ShortcutPage shortcutPage(String title){
        LinearLayout body=host.content(),root=host.column();body.addView(root,new LinearLayout.LayoutParams(-1,-1));
        ShortcutPage p=new ShortcutPage(root);shortcutShowing=p;
        root.addOnAttachStateChangeListener(new android.view.View.OnAttachStateChangeListener(){
            @Override public void onViewAttachedToWindow(android.view.View v){}
            @Override public void onViewDetachedFromWindow(android.view.View v){p.close();}
        });
        root.addView(host.text(title,24,TodayScreen.INK));
        Button back=host.button("返回分类",()->{if(p.current(root)){p.close();selected=0;load();}});
        back.setContentDescription("shortcut-back");categorySpeech(back,"返回分类");root.addView(back,new LinearLayout.LayoutParams(-1,-2));
        return p;
    }
    private LinearLayout shortcutScroll(ShortcutPage p){
        ScrollView scroll=new ScrollView(host.activity);LinearLayout rows=host.column();scroll.addView(rows);
        p.root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));return rows;
    }
    private void openShortcuts(long category,CategorySession session,android.view.View anchor){
        if(!host.db.shortcutsEnabled()||!categoryCurrent(session,anchor))return;
        host.work(()->{
            List<ShortcutEntry> entries=new ArrayList<>();
            synchronized(host.db){
                android.database.sqlite.SQLiteDatabase db=host.db.getReadableDatabase();db.beginTransaction();
                try{
                    List<Long> enabled=host.db.shortcutApplications(category);
                    try(Cursor c=db.rawQuery("SELECT id,name FROM applications ORDER BY id",null)){
                        while(c.moveToNext())entries.add(new ShortcutEntry(c.getLong(0),c.getString(1),enabled.contains(c.getLong(0))));
                    }
                    db.setTransactionSuccessful();
                }finally{db.endTransaction();}
            }
            return entries;
        },entries->{
            if(!categoryCurrent(session,anchor))return;
            ShortcutPage p=shortcutPage("分类快捷入口 · 分类 #"+category);
            LinearLayout rows=shortcutScroll(p);
            rows.addView(host.text("仅跳转到本应用内已有活动，不启动其他 App，不自动记账或打卡。",16,TodayScreen.MUTED));
            if(entries.isEmpty())rows.addView(host.text("应用目录还是空的，请先返回添加应用。",16,TodayScreen.MUTED));
            for(ShortcutEntry item:entries){
                rows.addView(host.text(item.name+" · #"+item.id,18,TodayScreen.INK));
                Button change=host.button(item.enabled?"移除快捷入口":"添加快捷入口",()->{});
                change.setContentDescription("shortcut-change-"+category+"-"+item.id);categorySpeech(change,(item.enabled?"移除":"添加")+"快捷入口，应用 "+item.name+"，编号 "+item.id);
                change.setOnClickListener(v->prepareShortcutPage(p,change,category,item,false));
                rows.addView(change,new LinearLayout.LayoutParams(-1,-2));
                if(item.enabled){
                    Button open=host.button("打开 "+item.name+" · #"+item.id,()->{});
                    open.setContentDescription("shortcut-open-"+category+"-"+item.id);categorySpeech(open,"打开应用 "+item.name+" 的活动，应用编号 "+item.id);
                    open.setOnClickListener(v->prepareShortcutPage(p,open,category,item,true));
                    rows.addView(open,new LinearLayout.LayoutParams(-1,-2));
                }
            }
        },()->host.message("无法读取快捷入口，请重新进入分类。",true));
    }
    private void prepareShortcutPage(ShortcutPage p,android.view.View control,long category,ShortcutEntry entry,boolean navigation){
        if(!p.current(control))return;
        p.submitted=true;
        host.work(()->host.db.prepareShortcut(category,entry.id),plan->{
            if(!p.alive||!p.root.isAttachedToWindow()){plan.close();return;}
            if(!entry.name.equals(plan.applicationName)||entry.enabled!=plan.enabled){
                plan.close();p.submitted=false;host.message("快捷入口已变化，请返回分类后重新打开。",true);return;
            }
            if(navigation)showShortcutTargets(plan);else showShortcutChange(plan);
        },()->{if(p.alive){p.submitted=false;host.message("目标不存在或内容已变化，请重新选择。",true);}},AppDatabase.ShortcutPlan::close);
    }
    private void showShortcutChange(AppDatabase.ShortcutPlan plan){
        ShortcutPage p=shortcutPage(plan.enabled?"移除快捷入口":"添加快捷入口");p.plan=plan;
        LinearLayout rows=shortcutScroll(p);
        rows.addView(host.text(plan.categoryName+" · #"+plan.category+"\n"+plan.applicationName+" · #"+plan.application,18,TodayScreen.INK));
        rows.addView(host.text("只改变这一条快捷关联，不删除应用、活动、笔记或任何历史记录。",16,TodayScreen.MUTED));
        Button save=host.button("确认"+(plan.enabled?"移除":"添加"),()->{});
        save.setContentDescription("shortcut-confirm");categorySpeech(save,(plan.enabled?"确认移除":"确认添加")+"快捷入口，分类 "+plan.categoryName+"，编号 "+plan.category+"，应用 "+plan.applicationName+"，编号 "+plan.application);
        save.setOnClickListener(v->{
            if(!p.current(save)||p.plan!=plan)return;
            p.submitted=true;
            host.work(()->host.db.confirmShortcut(plan,!plan.enabled),changed->{
                p.plan=null;if(!p.alive||!p.root.isAttachedToWindow())return;
                p.close();selected=0;load();host.message("快捷入口已更新",false);
            },()->{
                plan.close();p.plan=null;
                if(p.alive){p.submitted=false;save.setEnabled(false);host.message("未能修改：内容已变化或保存失败，请返回重新选择。",true);}
            });
        });
        rows.addView(save,new LinearLayout.LayoutParams(-1,-2));
    }
    private void showShortcutTargets(AppDatabase.ShortcutPlan plan){
        ShortcutPage p=shortcutPage("选择要打开的活动");p.plan=plan;
        LinearLayout rows=shortcutScroll(p);
        TextView origin=host.text(shortcutOriginLabel(plan.categoryName,plan.category,plan.applicationName,plan.application),18,TodayScreen.INK);origin.setTag("shortcut-origin");rows.addView(origin);
        host.work(()->{
            List<ShortcutEntry> targets=new ArrayList<>();
            synchronized(host.db){
                for(long id:host.db.activityTargets(plan.category,plan.application)){
                    try(Cursor c=host.db.getReadableDatabase().rawQuery(
                        SHORTCUT_TARGET_SQL,new String[]{Long.toString(id),Long.toString(plan.application)})){
                        if(c.moveToFirst())targets.add(new ShortcutEntry(id,shortcutTargetLabel(c.getString(0),id,c.getString(1),c.getLong(2)),true));
                    }
                }
            }
            return targets;
        },targets->{
            if(!p.alive||!p.root.isAttachedToWindow()){plan.close();return;}
            if(targets.isEmpty())rows.addView(host.text("没有可打开的活动：可能已归档或移除。不会自动新建。",16,TodayScreen.MUTED));
            for(ShortcutEntry target:targets){
                Button open=host.button(target.name,()->{});
                open.setContentDescription("shortcut-target-"+target.id);categorySpeech(open,"打开 "+target.name.replace(" · 活动 #","，活动编号 ").replace("\n所属分类：","，所属分类 ").replace(" · #","，分类编号 "));
                open.setOnClickListener(v->{
                    if(!p.current(open)||p.plan!=plan)return;
                    p.submitted=true;
                    host.work(()->host.db.navigateShortcut(plan,target.id),id->{
                        p.plan=null;if(!p.alive||!p.root.isAttachedToWindow())return;
                        p.close();shortcutOrigin=new ShortcutOrigin(plan.category,plan.application,id);selected=id;historyPanel=false;archivePanel=false;load();
                    },()->{
                        plan.close();p.plan=null;
                        if(p.alive){p.submitted=false;for(int i=0;i<rows.getChildCount();i++)rows.getChildAt(i).setEnabled(false);
                            host.message("目标已变化、归档或入口已移除，请返回分类后重选。",true);}
                    });
                });
                rows.addView(open,new LinearLayout.LayoutParams(-1,-2));
            }
        },()->{plan.close();p.plan=null;host.message("无法读取活动，请返回分类后重选。",true);});
    }

    private void renderBackup(){
        LinearLayout page=host.content(),body=host.column();ScrollView scroll=new ScrollView(host.activity);
        scroll.addView(body);page.addView(scroll,new LinearLayout.LayoutParams(-1,-1));
        body.addView(host.text("备份与恢复",24,TodayScreen.INK));
        TextView note=host.text("完整备份包含私有内容，且没有加密；只保存到自己信任的位置。恢复会先显示替换数量，勾选明白后才会确认。",15,TodayScreen.MUTED);note.setPadding(0,host.dp(8),0,host.dp(16));body.addView(note);
        body.addView(host.button("导出完整备份",()->{
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("application/zip");intent.putExtra(Intent.EXTRA_TITLE,"pocket-todo-backup.zip");
            host.activity.startActivityForResult(intent,MainActivity.EXPORT_BACKUP);
        }));
        body.addView(host.button("恢复完整备份",()->{
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("application/zip");
            host.activity.startActivityForResult(intent,MainActivity.IMPORT_BACKUP);
        }));
        Button append=host.button("追加旧版待办",()->{});
        append.setOnClickListener(v->LegacyPicker.open(this,append));body.addView(append);
        host.addRestoreUndo(body);
        body.addView(host.button("返回活动",()->{host.clearRestoreUndo();backupPanel=false;load();}));
    }
    /** A dedicated platform Fragment owns only the append picker result. It has no
     * entry in the manifest and never receives the full-backup request code. The
     * native Activity uses framework fragments (no new UI library or permissions).
     * A restored fragment has no owner/anchor and cannot resume a former consent. */
    @SuppressWarnings("deprecation")
    public static final class LegacyPicker extends android.app.Fragment implements android.view.View.OnAttachStateChangeListener {
        private static final String TAG="pocket.append.legacy";
        private static final int PICK=1;
        private ActivitiesScreen owner;
        private Button anchor;
        private boolean waiting,retired,removalQueued;
        private Picked pending;
        private AlertDialog dialog;
        public LegacyPicker(){} // Framework recreation deliberately does not restore an owner.
        private static final class Picked implements AutoCloseable {
            final LegacyImport.AppendReview source;final long existing;final boolean already;
            Picked(LegacyImport.AppendReview source,long existing,boolean already){this.source=source;this.existing=existing;this.already=already;}
            @Override public void close(){source.close();}
        }
        static void open(ActivitiesScreen owner,Button anchor){
            android.app.Activity a=owner.host.activity;
            if(!owner.backupPanel||!anchor.isAttachedToWindow()||!anchor.isEnabled()||a.isFinishing()||a.isDestroyed())return;
            android.app.FragmentManager manager=a.getFragmentManager();
            if(manager.isStateSaved()||manager.findFragmentByTag(TAG)!=null)return;
            LegacyPicker picker=new LegacyPicker();picker.owner=owner;picker.anchor=anchor;
            anchor.addOnAttachStateChangeListener(picker);
            try{
                manager.beginTransaction().add(picker,TAG).commitNow();
                picker.waiting=true;
                Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                picker.startActivityForResult(intent,PICK);
            }catch(android.content.ActivityNotFoundException|SecurityException|IllegalStateException failure){
                picker.retire(true);owner.host.message("无法打开旧版待办选择器，未追加任何内容。",true);
            }
        }
        private boolean live(){
            return !retired&&owner!=null&&anchor!=null&&owner.backupPanel&&anchor.isAttachedToWindow()
                &&isAdded()&&getActivity()==owner.host.activity&&!getActivity().isDestroyed()&&!getActivity().isFinishing();
        }
        private void removeWhenPossible(){
            android.app.FragmentManager m=getFragmentManager();
            if(!removalQueued&&isAdded()&&!isRemoving()&&m!=null&&!m.isDestroyed()&&!m.isStateSaved()){
                removalQueued=true;m.beginTransaction().remove(this).commit();
            }
        }
        private void retire(boolean remove){
            retired=true;waiting=false;
            if(anchor!=null)anchor.removeOnAttachStateChangeListener(this);
            anchor=null;owner=null;
            Picked read=pending;pending=null;if(read!=null)read.close();
            AlertDialog open=dialog;dialog=null;
            if(open!=null){open.setOnDismissListener(null);open.dismiss();}
            if(remove)removeWhenPossible();
        }
        @Override public void onViewAttachedToWindow(android.view.View v){}
        @Override public void onViewDetachedFromWindow(android.view.View v){retire(true);}
        @Override public void onResume(){super.onResume();if(owner==null||retired){retire(true);return;}showIfReady();}
        @Override public void onDestroy(){retire(false);super.onDestroy();}
        @Override public void onActivityResult(int code,int result,Intent data){
            super.onActivityResult(code,result,data);
            if(code!=PICK||!waiting)return;
            waiting=false;
            if(!live()){retire(true);return;}
            final TodayScreen host=owner.host;
            if(result!=android.app.Activity.RESULT_OK){retire(true);host.message("已取消旧版待办迁入，未追加。",false);return;}
            android.net.Uri uri=data==null?null:data.getData();
            if(uri==null||!"content".equals(uri.getScheme())||!anchor.isEnabled()){
                retire(true);host.message("请重新选择一份可读取的旧版待办文件，未追加。",true);return;
            }
            final android.content.ContentResolver resolver=host.activity.getApplicationContext().getContentResolver();
            host.work(()->{
                LegacyImport.AppendReview read=LegacyImport.readForAppend(resolver.openInputStream(uri));
                try{
                    final Picked value;
                    try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT (SELECT COUNT(*) FROM todos), EXISTS(SELECT 1 FROM legacy_imports WHERE source_id=?)",new String[]{read.sourceId()})){
                        if(!c.moveToFirst())throw new IllegalStateException("Missing legacy summary");
                        value=new Picked(read,c.getLong(0),c.getInt(1)!=0);
                    }
                    return value;
                }catch(RuntimeException failure){read.close();throw failure;}
            },value->{
                if(!live()){value.close();retire(true);return;}
                pending=value;host.message("旧版待办预览：尚未追加。",false);showIfReady();
            },()->{
                boolean active=live();retire(true);if(active)host.message("未能读取有效的旧版待办，未追加。完整备份 ZIP 请使用单独的恢复入口。",true);
            },Picked::close);
            // A read-only preview must not emit work()'s generic success notice.
            host.message("正在读取旧版待办，仅预览。",false);
        }
        private void showIfReady(){
            final Picked value=pending;
            if(value==null||dialog!=null||!live()||!isResumed()||getFragmentManager().isStateSaved())return;
            final TodayScreen host=owner.host;final Button entry=anchor;
            String summary="本机已有 "+value.existing+" 条普通待办。\n文件共 "+value.source.total()+" 条：已完成 "+value.source.completed()+" 条，未完成 "+(value.source.total()-value.source.completed())+" 条。\n只追加普通待办，不替换已有内容，不生成活动、打卡或账目。";
            boolean canAppend=!value.already&&value.source.total()>0;
            if(value.already)summary+="\n这份文件已在本机迁入，不会重复追加。";
            else if(!canAppend)summary+="\n这份文件没有待办，无需追加。";
            else summary+="\n同一份文件只迁入一次；改过的文件会作为新来源。";
            try{
                AlertDialog.Builder builder=new AlertDialog.Builder(host.activity).setTitle("预览旧版待办").setMessage(summary).setNegativeButton(canAppend?"取消":"关闭",null);
                if(canAppend)builder.setPositiveButton("确认追加",null);
                final AlertDialog shown=builder.create();dialog=shown;
                shown.setOnDismissListener(unused->{if(dialog==shown)retire(true);});
                if(canAppend)shown.setOnShowListener(unused->shown.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
                    if(!live()||!isResumed()||!shown.isShowing()||!v.isAttachedToWindow()||dialog!=shown||pending!=value||!entry.isEnabled())return;
                    // Move the one-shot review to the serial database writer before dismissing.
                    pending=null;retire(true);
                    host.work(()->{try(Picked owned=value){return owned.source.appendOnce(host.db::importLegacy);}},n->{
                        if(entry.isAttachedToWindow()&&!host.activity.isFinishing())host.message(n==0?"这份文件已迁入，没有重复追加。":"已追加 "+n+" 条普通待办。",false);
                    },()->{if(entry.isAttachedToWindow()&&!host.activity.isFinishing())host.message("追加未完成，请重新选择文件核对。",true);});
                }));
                shown.show();
            }catch(android.view.WindowManager.BadTokenException|IllegalStateException failure){retire(true);if(!host.activity.isFinishing()&&!host.activity.isDestroyed())host.message("页面已变化，请重新选择旧版待办文件。",true);}
        }
    }

    private void loadDetail(long id){
        host.work(()->{
            // One consistent read transaction, no revision changes or image decoding.
            synchronized(host.db){
                android.database.sqlite.SQLiteDatabase sql=host.db.getReadableDatabase();
                sql.beginTransaction();
                try{
                    Detail d=new Detail();
                    try(Cursor c=sql.rawQuery("SELECT title,archived FROM activities WHERE id=?",new String[]{Long.toString(id)})){if(!c.moveToFirst())throw new IllegalArgumentException("活动不存在");d.title=c.getString(0);d.archived=c.getLong(1)==1;}
                    d.path=host.db.path(id);d.tags=host.db.tags(id);d.day=LocalDate.now(CN);d.status="未记录";
                    for(CalendarRules.Mark mark:host.db.marks(id))if(mark.date.equals(d.day))d.status=mark.status==CalendarRules.Status.DONE?"已完成":"已跳过";
                    try(Cursor c=sql.rawQuery("SELECT id,title FROM notes WHERE activity_id=? ORDER BY rowid",new String[]{Long.toString(id)})){
                        while(c.moveToNext()){
                            String noteId=c.getString(0);
                            d.notes.add(new NoteSummary(noteId,c.getString(1),NoteDocument.summary(host.db.noteBlocks(noteId))));
                        }
                    }
                    if(d.archived)d.history=archiveHistory(sql,id);
                    sql.setTransactionSuccessful();return d;
                }finally{sql.endTransaction();}
            }
        },d->renderDetail(id,d),null);
    }
    private void renderDetail(long id,Detail d){
        if(d.archived){renderArchived(id,d);return;}
        LinearLayout body=host.content();LinearLayout toolbar=new LinearLayout(host.activity);
        Button back=detailBack(id,false);if(shortcutFor(id)!=null)body.addView(back,new LinearLayout.LayoutParams(-1,-2));else toolbar.addView(back,new LinearLayout.LayoutParams(0,host.dp(48),1));
        toolbar.addView(host.button("日历账本",()->new CalendarScreen(host,id,d.title,this::load).load()),new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(toolbar);
        FieldScreen fields=new FieldScreen(host,id,this::load);
        Button fieldEntry=host.button("字段",()->{});fieldEntry.setContentDescription("activity-fields-"+id);
        fieldEntry.setOnClickListener(v->{if(selected==id&&!backupPanel&&!historyPanel)fields.open(fieldEntry);});
        toolbar.addView(fieldEntry,new LinearLayout.LayoutParams(0,host.dp(48),1));
        // Daily status/actions remain reachable while reading long paths or tags.
        TextView stamp=host.text("今天："+d.status,18,TodayScreen.ACCENT);stamp.setContentDescription("activity-today-status");
        stamp.setPadding(host.dp(8),host.dp(8),host.dp(8),host.dp(8));stamp.setBackground(host.shape(TodayScreen.TINT,16));body.addView(stamp);
        LinearLayout marks=new LinearLayout(host.activity);
        marks.addView(host.button("标记完成",()->mark(id,LocalDate.now(CN),CalendarRules.Status.DONE)),new LinearLayout.LayoutParams(0,host.dp(52),1));
        marks.addView(host.button("跳过今天",()->mark(id,LocalDate.now(CN),CalendarRules.Status.SKIPPED)),new LinearLayout.LayoutParams(0,host.dp(52),1));body.addView(marks);
        ScrollView scroll=new ScrollView(host.activity);scroll.setContentDescription("activity-details-scroll");LinearLayout details=host.column();scroll.addView(details);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        details.addView(host.text(d.title,26,TodayScreen.INK));
        TextView note=host.text("手动记录，不会替你操作其他应用",14,TodayScreen.MUTED);note.setPadding(0,host.dp(6),0,host.dp(18));details.addView(note);
        details.addView(host.text(d.day+" · 中国时间",16,TodayScreen.MUTED));
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
        ArchiveAction archive=new ArchiveAction(host,id,d.title,false,this::load);
        Button archiveEntry=host.button("归档活动",()->{});archiveEntry.setContentDescription("activity-archive-"+id);
        archiveEntry.setOnClickListener(v->archive.open(archiveEntry));details.addView(archiveEntry,new LinearLayout.LayoutParams(-1,-2));
        details.addView(host.text("标签",20,TodayScreen.INK));
        TextView tagText=host.text(d.tags.isEmpty()?"还没有标签":String.join(" · ",d.tags),16,TodayScreen.MUTED);
        tagText.setContentDescription("activity-tags-"+id);details.addView(tagText);
        RelationEditor tagEditor=new RelationEditor(host,id,d.title,true,d.tags,this::load);
        Button tagEdit=host.button("编辑标签",()->{});tagEdit.setContentDescription("activity-tags-edit-"+id);
        tagEdit.setOnClickListener(v->tagEditor.open(tagEdit));details.addView(tagEdit,new LinearLayout.LayoutParams(-1,-2));
        TextView pathTitle=host.text("去哪里操作",20,TodayScreen.INK);pathTitle.setPadding(0,host.dp(18),0,host.dp(8));details.addView(pathTitle);
        if(d.path.isEmpty())details.addView(host.text("把入口一行行记下来，下次不用找。",16,TodayScreen.MUTED));
        for(int i=0;i<d.path.size();i++){TextView step=host.text((i+1)+". "+d.path.get(i),17,TodayScreen.INK);step.setPadding(host.dp(8),host.dp(8),host.dp(8),host.dp(8));details.addView(step);}
        RelationEditor pathEditor=new RelationEditor(host,id,d.title,false,d.path,this::load);
        Button pathEdit=host.button("编辑路径",()->{});pathEdit.setContentDescription("activity-path-edit-"+id);
        pathEdit.setOnClickListener(v->pathEditor.open(pathEdit));details.addView(pathEdit,new LinearLayout.LayoutParams(-1,-2));
        details.addView(new TemplateAction(id,d.title).entry,new LinearLayout.LayoutParams(-1,-2));
    }
    /** Only an attached, active activity detail can own a template preview. The normal close/back path is read-only. */
    private final class TemplateAction {
        final long source;final String shown;final Button entry;boolean opening;
        TemplateAction(long id,String title){source=id;shown=title;entry=host.button("按此结构新建活动",this::open);entry.setTag("activity-template-open-"+id);entry.setContentDescription("以活动编号 "+id+" 的结构新建独立活动");}
        boolean owner(){return selected==source&&!backupPanel&&!historyPanel&&!archivePanel&&entry.isAttachedToWindow()&&entry.isShown()&&!host.activity.isFinishing()&&!host.activity.isDestroyed();}
        void open(){if(opening||!owner()||!entry.isEnabled())return;opening=true;
            host.work(()->host.db.prepareActivityTemplate(source),plan->{
                if(!owner()||plan.sourceId!=source||!shown.equals(plan.title)){opening=false;plan.close();return;}
                try{show(plan);}catch(android.view.WindowManager.BadTokenException|IllegalStateException ex){opening=false;plan.close();if(owner())host.message("页面已变化，请重新打开模板预览。",true);}
            },()->{opening=false;if(owner())host.message("活动状态已变化或读取失败，请重新进入后预览。",true);},AppDatabase.ActivityTemplatePlan::close);
        }
        void show(AppDatabase.ActivityTemplatePlan plan){
            LinearLayout contents=host.column();contents.setPadding(host.dp(18),host.dp(8),host.dp(18),host.dp(8));contents.setFocusableInTouchMode(true);
            TextView identity=host.text("来源："+plan.title+" · #"+source,18,TodayScreen.INK);identity.setTag("template-source");contents.addView(identity);
            TextView scope=host.text("沿用分类："+plan.categoryName+" · #"+plan.categoryId+"\n关联应用："+plan.applicationName+(plan.applicationId==0?"":" · #"+plan.applicationId)+"\n复制操作路径 "+plan.paths.size()+" 步、标签 "+plan.tags.size()+" 个，顺序不变。",16,TodayScreen.INK);scope.setTag("template-scope");contents.addView(scope);
            contents.addView(host.text("不复制字段值、字段笔记、其他笔记、图片、草稿、打卡或账目。副本有自己的编号，不会覆盖源活动。",15,TodayScreen.MUTED));
            EditText name=host.field("新活动名称",false);name.setTag("template-name");name.setText(plan.title);name.setSelection(name.length());contents.addView(name,new LinearLayout.LayoutParams(-1,-2));
            TextView validation=host.text("",14,TodayScreen.ERROR);validation.setTag("template-validation");validation.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);contents.addView(validation);contents.requestFocus();
            ScrollView scroll=new ScrollView(host.activity);scroll.addView(contents);
            AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("按此结构新建活动").setView(scroll).setNegativeButton("取消",null).setPositiveButton("确认新建",null).create();
            final boolean[] handed={false};android.view.View.OnAttachStateChangeListener detach=new android.view.View.OnAttachStateChangeListener(){public void onViewAttachedToWindow(android.view.View v){}public void onViewDetachedFromWindow(android.view.View v){if(dialog.isShowing())dialog.dismiss();}};
            entry.addOnAttachStateChangeListener(detach);dialog.setOnDismissListener(d->{entry.removeOnAttachStateChangeListener(detach);opening=false;if(!handed[0])plan.close();});
            dialog.setOnShowListener(d->{Button yes=dialog.getButton(AlertDialog.BUTTON_POSITIVE),no=dialog.getButton(AlertDialog.BUTTON_NEGATIVE);yes.setTag("template-confirm");no.setTag("template-cancel");yes.setMinHeight(host.dp(48));no.setMinHeight(host.dp(48));
                yes.setOnClickListener(v->{if(handed[0]||!dialog.isShowing()||!owner()||!yes.isEnabled())return;String entered=name.getText().toString();if(entered.trim().isEmpty()){validation.setText("请输入新活动名称。");return;}
                    handed[0]=true;dialog.setCancelable(false);yes.setEnabled(false);no.setEnabled(false);name.setEnabled(false);
                    host.work(()->host.db.confirmActivityTemplate(plan,entered),created->{boolean active=owner()&&dialog.isShowing();dialog.dismiss();if(active){leaveSearch();selected=created;load();}},()->{
                        plan.close();if(owner()&&dialog.isShowing()){dialog.setCancelable(true);no.setEnabled(true);validation.setText("未能确认创建；请关闭后核对活动列表，再重新预览。");}
                    });
                });
            });
            try{dialog.show();}catch(RuntimeException e){entry.removeOnAttachStateChangeListener(detach);plan.close();throw e;}
        }
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
        private void dismissInput(EditText input){
            android.view.inputmethod.InputMethodManager ime=(android.view.inputmethod.InputMethodManager)
                host.activity.getSystemService(android.content.Context.INPUT_METHOD_SERVICE);
            if(ime!=null)ime.hideSoftInputFromWindow(input.getWindowToken(),0);
            input.clearFocus();
        }
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
            ScrollView scroll=new ScrollView(host.activity);scroll.setContentDescription("relation-editor-scroll");
            LinearLayout fields=host.column();scroll.addView(fields);root.addView(scroll,new LinearLayout.LayoutParams(-1,-1));
            fields.addView(host.text(tags?"编辑标签":"编辑操作路径",24,TodayScreen.INK));
            TextView identity=host.text(title+" · #"+id,16,TodayScreen.MUTED);identity.setContentDescription("relation-identity");fields.addView(identity);
            fields.addView(host.text(tags?"每行一个标签，重复标签保留首次出现的位置。清空全部文字可移除标签。":"每行一步，顺序和重复步骤保留。清空全部文字可移除路径。",15,TodayScreen.MUTED));
            EditText input=host.field(tags?"活动标签":"活动路径",true);input.setText(String.join("\n",plan.values()));fields.addView(input,new LinearLayout.LayoutParams(-1,-2));
            TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("relation-validation");fields.addView(validation);
            Button save=host.button("保存",()->{});save.setContentDescription("relation-save");
            Button cancel=host.button("取消",()->{});cancel.setContentDescription("relation-cancel");
            cancel.setOnClickListener(v->{if(active()&&cancel.isEnabled()){dismissInput(input);close();back.run();}});
            save.setOnClickListener(v->{
                if(!active()||submitted||!save.isEnabled())return;
                String value=input.getText().toString();List<String> values=new ArrayList<>();
                if(!value.isEmpty())for(String part:value.split("\\r?\\n",-1)){
                    String clean=part.trim();if(clean.isEmpty()){validation.setText(tags?"标签不能为空行":"步骤不能为空");return;}values.add(clean);
                }
                submitted=true;save.setEnabled(false);cancel.setEnabled(false);input.setEnabled(false);
                final AppDatabase.ActivityStringsPlan attempt=plan;
                host.work(()->host.db.confirmActivityStrings(attempt,values),changed->{
                    boolean present=active();close();if(present){dismissInput(input);back.run();}
                },()->{
                    attempt.close();
                    if(active()){validation.setText("未能保存；内容可能已变化，请取消后重新打开。");cancel.setEnabled(true);}
                });
            });
            fields.addView(save,new LinearLayout.LayoutParams(-1,-2));fields.addView(cancel,new LinearLayout.LayoutParams(-1,-2));
        }
    }

    /** A real, read-only preview on the ordinary workbench. Until a backup-aware durable
     * format is supported here, do not advertise a confirmation that cannot persist. */
    private final class ImpactBrowser implements android.view.View.OnAttachStateChangeListener {
        final android.view.View anchor;final ArrayList<Long> starts=new ArrayList<>();
        android.app.AlertDialog shown;long ticket;boolean retired,loading;
        ImpactBrowser(android.view.View anchor){this.anchor=anchor;starts.add(0L);}
        boolean live(){return !retired&&archivePanel&&selected==0&&anchor.isAttachedToWindow()&&!host.activity.isFinishing()&&!host.activity.isDestroyed();}
        void start(){if(!live())return;anchor.addOnAttachStateChangeListener(this);page();}
        public void onViewAttachedToWindow(android.view.View v){}
        public void onViewDetachedFromWindow(android.view.View v){close();}
        void dismiss(){android.app.AlertDialog old=shown;shown=null;if(old!=null)old.dismiss();}
        void close(){if(retired)return;retired=true;++ticket;anchor.removeOnAttachStateChangeListener(this);dismiss();}
        void show(android.app.AlertDialog d){if(!live()){close();return;}shown=d;d.setOnDismissListener(x->{if(shown==d)close();});d.show();}
        void failure(long t){if(live()&&ticket==t){close();host.message("无法确认这个分类的最新状态，请重新选择。没有改动数据。",true);}}
        void page(){if(!live()||loading)return;dismiss();loading=true;long t=++ticket;long key=starts.get(starts.size()-1);
            host.work(()->host.db.categoryImpactChoices(key),items->{if(!live()||ticket!=t)return;loading=false;LinearLayout box=host.column();box.setPadding(host.dp(16),host.dp(8),host.dp(16),host.dp(8));
                box.addView(host.text("只查看归档会影响哪些入口；本页不会修改分类或活动。",16,TodayScreen.MUTED));if(items.isEmpty())box.addView(host.text("没有可预览的分类。",16,TodayScreen.MUTED));
                int n=Math.min(24,items.size());for(int i=0;i<n;i++){ActivityModel.Category c=items.get(i);Button choose=host.button(c.name+" · #"+c.id,()->{});choose.setContentDescription("预览分类 "+c.name+"，编号 "+c.id);choose.setOnClickListener(v->{if(live()&&ticket==t&&v.isEnabled()&&v.isAttachedToWindow())detail(c);});box.addView(choose,new LinearLayout.LayoutParams(-1,-2));}
                if(starts.size()>1)box.addView(host.button("上一页",()->{if(live()&&ticket==t){starts.remove(starts.size()-1);page();}}));
                if(items.size()>n){long next=items.get(n-1).id;box.addView(host.button("下一页",()->{if(live()&&ticket==t){starts.add(next);page();}}));}
                ScrollView sv=new ScrollView(host.activity);sv.addView(box);show(new android.app.AlertDialog.Builder(host.activity).setTitle("选择要预览的分类").setView(sv).setNegativeButton("取消",null).create());host.message("已读取分类，没有改动数据。",false);
            },()->failure(t));host.message("正在读取分类…",false);}
        void detail(ActivityModel.Category c){if(!live()||loading)return;dismiss();loading=true;long t=++ticket;
            host.work(()->host.db.previewCategoryImpact(c.id,c.name),p->{if(!live()||ticket!=t)return;loading=false;LinearLayout box=host.column();box.setPadding(host.dp(16),host.dp(8),host.dp(16),host.dp(8));
                TextView identity=host.text(p.name+" · 分类 #"+p.id,18,TodayScreen.INK);identity.setContentDescription("所选归档分类");box.addView(identity);
                String counts="将从默认列表和搜索隐藏的活动："+p.active+"\n原本已单独归档的活动："+p.individual+"\n其他分类仍可用的同应用活动："+p.otherTargets+"\n本分类的快捷入口："+p.outgoing+"\n其他分类快捷入口中将隐藏的活动："+p.incomingTargets;
                TextView info=host.text(counts,16,TodayScreen.INK);info.setContentDescription("分类归档影响数量");box.addView(info);
                box.addView(host.text("恢复分类只恢复入口。原已归档的活动不会自动恢复；应用、账目、打卡、笔记、字段、路径、标签和图片都保留。当前仅预览，尚未归档。",15,TodayScreen.MUTED));ScrollView sv=new ScrollView(host.activity);sv.addView(box);
                android.app.AlertDialog dialog=new android.app.AlertDialog.Builder(host.activity).setTitle("分类归档影响").setView(sv).setNeutralButton("返回选择",null).setNegativeButton("关闭预览",null).create();dialog.setOnShowListener(x->dialog.getButton(android.app.AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->{if(live()&&ticket==t)page();}));show(dialog);host.message("分类影响预览，未归档。",false);
            },()->failure(t));host.message("正在读取分类影响…",false);}
    }
    private void loadArchivedActivities(){
        host.work(()->{
            List<Item> items=new ArrayList<>();
            try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT id,category_id,title FROM activities WHERE archived=1 ORDER BY id",null)){
                while(c.moveToNext())items.add(new Item(c));
            }
            return items;
        },items->{
            LinearLayout body=host.content();body.addView(host.text("已归档活动",24,TodayScreen.INK));
            Button back=host.button("返回分类",()->{archivePanel=false;selected=0;historyPanel=false;load();});
            back.setContentDescription("archive-list-back");body.addView(back);
            ScrollView scroll=new ScrollView(host.activity);LinearLayout list=host.column();scroll.addView(list);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
            Button impact=host.button("预览分类归档影响",()->{});impact.setTag("category-impact-open");impact.setContentDescription("查看分类归档的影响，不修改数据");impact.setOnClickListener(v->{if(archivePanel&&selected==0&&v.isEnabled()&&v.isAttachedToWindow())new ImpactBrowser(v).start();});list.addView(impact,new LinearLayout.LayoutParams(-1,-2));
            if(items.isEmpty())list.addView(host.text("没有已归档活动",18,TodayScreen.MUTED));
            for(Item item:items){
                Button open=host.button(item.title+" · #"+item.id,()->{selected=item.id;historyPanel=false;load();});
                open.setContentDescription("archived-activity-"+item.id);list.addView(open,new LinearLayout.LayoutParams(-1,-2));
            }
        },null);
    }
    /** Fixed SELECTs only. No editor, image decoder, draft access or write API.
     * Images are listed by immutable identity/caption, not opened or exported. */
    private List<String> archiveHistory(android.database.sqlite.SQLiteDatabase sql,long id){
        List<String> out=new ArrayList<>();String[] owner={Long.toString(id)};
        try(Cursor c=sql.rawQuery("SELECT c.name,a.application_id FROM activities a JOIN categories c ON c.id=a.category_id WHERE a.id=?",owner)){
            if(!c.moveToFirst())throw new IllegalArgumentException("活动不存在");
            out.add("原分类："+c.getString(0)+"\n应用标识："+(c.isNull(1)?"无":Long.toString(c.getLong(1))));
        }
        for(CalendarRules.Mark mark:host.db.marks(id))
            out.add("打卡："+mark.date+" · "+(mark.status==CalendarRules.Status.DONE?"已完成":"已跳过")+"\n"+mark.memo+"\n录入："+mark.recordedAt);
        try(Cursor c=sql.rawQuery("SELECT day,kind,cents,memo,batch_id FROM ledger WHERE activity_id=? ORDER BY day,rowid",owner)){
            while(c.moveToNext())out.add("账目："+c.getString(0)+" · "+c.getString(1)+" · "+c.getLong(2)+" 分\n"+c.getString(3)+"\n批次："+c.getString(4));
        }
        try(Cursor c=sql.rawQuery("SELECT f.name,f.type,v.value FROM field_values v JOIN fields f ON f.id=v.field_id WHERE v.activity_id=? ORDER BY f.rowid,v.position",owner)){
            while(c.moveToNext())out.add("字段："+c.getString(0)+" · "+c.getString(1)+"\n"+c.getString(2));
        }
        try(Cursor notes=sql.rawQuery("SELECT n.id,n.title,f.name FROM notes n LEFT JOIN field_notes fn ON fn.note_id=n.id LEFT JOIN fields f ON f.id=fn.field_id WHERE n.activity_id=? ORDER BY n.rowid",owner)){
            while(notes.moveToNext()){
                String noteId=notes.getString(0);
                out.add("笔记："+notes.getString(1)+"\n标识："+noteId+(notes.isNull(2)?"":"\n关联字段："+notes.getString(2)));
                try(Cursor c=sql.rawQuery("SELECT kind,text,asset_id,caption,private FROM blocks WHERE note_id=? ORDER BY position",new String[]{noteId})){
                    while(c.moveToNext()){
                        String content=c.getString(0).equals("TEXT")?c.getString(1):"图片："+c.getString(2)+"\n"+c.getString(3);
                        out.add((c.getLong(4)==0?"":"私密内容\n")+content);
                    }
                }
            }
        }
        return out;
    }
    private void renderArchived(long id,Detail d){
        LinearLayout body=host.content();body.addView(host.text("已归档 · 只读历史",24,TodayScreen.INK));
        Button back=detailBack(id,true);
        back.setContentDescription("archive-detail-back");if(shortcutFor(id)!=null)categorySpeech(back,"返回快捷目标");body.addView(back);
        ArchiveAction action=new ArchiveAction(host,id,d.title,true,this::load);
        Button restore=host.button("恢复活动",()->{});restore.setContentDescription("activity-restore-"+id);
        restore.setOnClickListener(v->action.open(restore));body.addView(restore);
        ScrollView scroll=new ScrollView(host.activity);LinearLayout rows=host.column();scroll.addView(rows);
        body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        rows.setContentDescription("archive-history-"+id);
        rows.addView(host.text(d.title+" · #"+id,22,TodayScreen.INK));
        rows.addView(host.text("此页不修改历史。图片只列出标识和说明，恢复活动后可进入原编辑界面查看。",14,TodayScreen.MUTED));
        rows.addView(host.text("路径",20,TodayScreen.INK));
        for(int i=0;i<d.path.size();i++)rows.addView(host.text((i+1)+". "+d.path.get(i),16,TodayScreen.INK));
        rows.addView(host.text("标签："+String.join(" · ",d.tags),16,TodayScreen.INK));
        for(String value:d.history){TextView line=host.text(value,16,TodayScreen.INK);line.setPadding(0,host.dp(8),0,host.dp(8));rows.addView(line);}
    }

    /** Preview is not a write. One explicit attempt, closed on page detachment. */
    private static final class ArchiveAction {
        private final TodayScreen host;
        private final long id;
        private final String title;
        private final boolean archived;
        private final Runnable back;
        private AppDatabase.ActivityArchivePlan plan;
        private LinearLayout root;
        private boolean opening,alive,submitted;
        ArchiveAction(TodayScreen host,long id,String title,boolean archived,Runnable back){
            this.host=host;this.id=id;this.title=title;this.archived=archived;this.back=back;
        }
        private boolean active(){
            return alive&&root!=null&&root.isAttachedToWindow()&&!host.activity.isFinishing()&&!host.activity.isDestroyed();
        }
        private void close(){alive=false;if(plan!=null){plan.close();plan=null;}}
        void open(android.view.View anchor){
            if(opening||!anchor.isAttachedToWindow()||!anchor.isEnabled()||host.activity.isFinishing()||host.activity.isDestroyed())return;
            opening=true;
            host.work(()->host.db.prepareActivityArchive(id,!archived),p->{
                if(!anchor.isAttachedToWindow()||host.activity.isFinishing()||host.activity.isDestroyed()
                    ||p.activityId()!=id||!title.equals(p.title())||p.wasArchived()!=archived||p.willArchive()==archived){
                    p.close();host.message("活动状态已变化，请重新打开后确认。",true);return;
                }
                plan=p;render();
            },()->host.message("未能读取归档预览，请重新进入活动。",true));
        }
        private void render(){
            LinearLayout body=host.content();root=host.column();body.addView(root,new LinearLayout.LayoutParams(-1,-1));alive=true;
            root.addOnAttachStateChangeListener(new android.view.View.OnAttachStateChangeListener(){
                @Override public void onViewAttachedToWindow(android.view.View v){}
                @Override public void onViewDetachedFromWindow(android.view.View v){close();}
            });
            root.addView(host.text(archived?"恢复活动":"归档活动",24,TodayScreen.INK));
            ScrollView scroll=new ScrollView(host.activity);LinearLayout preview=host.column();scroll.addView(preview);
            root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
            TextView identity=host.text(title+" · #"+id,18,TodayScreen.INK);identity.setContentDescription("archive-identity");preview.addView(identity);
            TextView impact=host.text(archived
                ?"恢复后重新出现在原分类，可继续记录。全部历史、路径、标签、字段、笔记、账目和图片保持不变。"
                :"只归档这一项活动，从活动列表隐藏。全部历史、路径、标签、字段、笔记、账目和图片保留；应用目录记录不变。可在「已归档活动」只读查看历史，再明确恢复。",16,TodayScreen.MUTED);
            impact.setContentDescription("archive-impact");preview.addView(impact);
            TextView validation=host.text("",14,TodayScreen.ERROR);validation.setContentDescription("archive-validation");preview.addView(validation);
            Button confirm=host.button(archived?"确认恢复活动":"确认归档活动",()->{});confirm.setContentDescription("archive-confirm");
            Button cancel=host.button("取消",()->{});cancel.setContentDescription("archive-cancel");
            cancel.setOnClickListener(v->{if(active()&&cancel.isEnabled()){close();back.run();}});
            confirm.setOnClickListener(v->{
                if(!active()||submitted||!confirm.isEnabled())return;
                submitted=true;confirm.setEnabled(false);cancel.setEnabled(false);
                final AppDatabase.ActivityArchivePlan attempt=plan;
                host.work(()->host.db.confirmActivityArchive(attempt),changed->{
                    boolean present=active();close();if(present)back.run();
                },()->{
                    attempt.close();
                    if(active()){validation.setText("未能修改；内容可能已变化。请取消后重新预览。");cancel.setEnabled(true);}
                });
            });
            root.addView(confirm,new LinearLayout.LayoutParams(-1,-2));
            root.addView(cancel,new LinearLayout.LayoutParams(-1,-2));
        }
    }

    private void loadHistory(long id){
        host.work(()->{
            try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT archived FROM activities WHERE id=?",new String[]{Long.toString(id)})){
                if(!c.moveToFirst())throw new IllegalArgumentException("活动不存在");
                if(c.getLong(0)==1)return (List<CalendarRules.Mark>)null;
            }
            return host.db.marks(id);
        },marks->{if(marks==null){historyPanel=false;loadDetail(id);}else renderHistory(id,marks);},null);
    }
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
