package com.supercubegame.pockettodo;

import android.app.AlertDialog;
import android.content.res.ColorStateList;
import android.database.Cursor;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.*;

/** Native activity ledger. Date selection is a read filter, never a write batch.
 * Notebook design: six honest totals, calendar in a separate native dialog,
 * actual-vs-planned marks, exact RMB cents throughout. No schema extension.
 * Selected dates are ephemeral UI state; committed entries are persistent.
 */
public final class CalendarScreen {
    private final TodayScreen host;
    private final long activityId;
    private final String title;
    private final Runnable back;
    private final Set<LocalDate> selected=new TreeSet<>();
    private YearMonth month=YearMonth.now(ZoneId.of("Asia/Shanghai"));
    private static final String[] METRICS={"EXPENSE","REFUND","INCOME","PLANNED","NET_EXPENSE","NET_CASH"};
    private static final String[] LABELS={"支出","退款","收入","预计","净支出","净现金"};
    private static final class State {
        final List<Ledger.Entry> entries=new ArrayList<>();
        final Set<LocalDate> actual=new HashSet<>(),planned=new HashSet<>();
        final long[] totals=new long[6];int actualSelected;AppDatabase.MoneyUndoReview latest;
    }
    CalendarScreen(TodayScreen host,long activityId,String title,Runnable back){this.host=host;this.activityId=activityId;this.title=title;this.back=back;}
    static String yuan(long cents){return BigDecimal.valueOf(cents,2).toPlainString();}
    void load(){
        Set<LocalDate> dates=new TreeSet<>(selected);
        host.work(()->{
            State state=new State();Ledger ledger=new Ledger();
            try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT id,day,kind,cents,memo FROM ledger WHERE activity_id=? ORDER BY day DESC,rowid DESC",new String[]{Long.toString(activityId)})){
                while(c.moveToNext()){
                    Ledger.Entry e=new Ledger.Entry(c.getString(0),activityId,LocalDate.parse(c.getString(1)),Ledger.Kind.valueOf(c.getString(2)),c.getLong(3),c.getString(4));state.entries.add(e);
                    if(e.kind==Ledger.Kind.PLANNED)state.planned.add(e.date);else state.actual.add(e.date);
                }
            }
            if(!state.entries.isEmpty())ledger.recordBatch("view",state.entries);
            for(int i=0;i<METRICS.length;i++)state.totals[i]=ledger.total(activityId,dates,METRICS[i]);
            state.actualSelected=ledger.recordedActualDates(activityId,dates).size();state.latest=host.db.latestMoneyUndo(activityId);return state;
        },this::render,null);
    }
    private void render(State state){
        LinearLayout body=host.content();
        LinearLayout header=new LinearLayout(host.activity);
        header.addView(host.button("返回活动",back),new LinearLayout.LayoutParams(0,host.dp(48),1));
        TextView name=host.text("日历账本",22,TodayScreen.INK);name.setGravity(Gravity.CENTER);header.addView(name,new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(header);
        TextView owner=host.text(title,16,TodayScreen.MUTED);owner.setMaxLines(2);body.addView(owner);
        LinearLayout actions=new LinearLayout(host.activity);
        actions.addView(host.button("选择日期",()->chooseDates(state)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        actions.addView(host.button("记一笔",this::entryDialog),new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(actions);
        Button batch=host.button("批量记账",()->{});batch.setOnClickListener(v->openBatch(batch));actions.addView(batch,new LinearLayout.LayoutParams(0,host.dp(48),1));
        if(state.latest!=null){Button undo=host.button("撤销最近批次",()->{});undo.setOnClickListener(v->openUndo(undo,state.latest));header.addView(undo,new LinearLayout.LayoutParams(0,host.dp(48),1));}
        TextView scope=host.text("已选 "+selected.size()+" 天 · 仅汇总，不批量写入",14,TodayScreen.MUTED);scope.setContentDescription("selected-days");body.addView(scope);
        for(int row=0;row<3;row++){
            LinearLayout line=new LinearLayout(host.activity);
            for(int col=0;col<2;col++){
                int index=row*2+col;TextView value=host.text(LABELS[index]+" ¥"+yuan(state.totals[index]),16,index>=4?TodayScreen.ACCENT:TodayScreen.INK);
                value.setContentDescription("metric-"+METRICS[index]);value.setPadding(host.dp(6),host.dp(7),host.dp(4),host.dp(7));value.setBackground(host.shape(TodayScreen.TINT,8));
                line.addView(value,new LinearLayout.LayoutParams(0,-2,1));
            }
            body.addView(line);
        }
        String explanation=selected.isEmpty()?"先选日期查看汇总；空选择不代表全部日期。":state.actualSelected==0?"所选日期没有实际账目，不代表已确认零支出":"实际记录 "+state.actualSelected+" 天；未记录日不算已确认零支出。";
        TextView hint=host.text(explanation,14,TodayScreen.MUTED);hint.setPadding(0,host.dp(6),0,host.dp(6));body.addView(hint);
        ScrollView scroll=new ScrollView(host.activity);LinearLayout rows=host.column();scroll.addView(rows);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        for(Ledger.Entry e:state.entries)if(selected.contains(e.date)){
            LinearLayout row=host.column();row.setPadding(host.dp(10),host.dp(8),host.dp(10),host.dp(8));row.setBackground(host.shape(TodayScreen.WHITE,10));
            row.addView(host.text(e.date+"  "+LABELS[e.kind.ordinal()]+" ¥"+yuan(e.cents),16,TodayScreen.INK));
            if(!e.memo.isEmpty())row.addView(host.text(e.memo,14,TodayScreen.MUTED));host.addRow(rows,row);
        }
        Button corrections=host.button("历史单笔更正：打开独立日程簿",()->{});corrections.setTag("calendar-book-corrections");corrections.setOnClickListener(v->{if(v.isEnabled()&&v.isAttachedToWindow()){android.content.Intent i=new android.content.Intent(host.activity,ScheduleBookActivity.class);host.activity.startActivity(i);}});host.addRow(rows,corrections);
    }
    private void chooseDates(State state){
        Set<LocalDate> draft=new TreeSet<>(selected);
        YearMonth[] shown={month};
        LinearLayout body=host.column();body.setPadding(host.dp(10),0,host.dp(10),0);body.setFocusableInTouchMode(true);
        LinearLayout jump=new LinearLayout(host.activity);
        // Prefilled format is self-explanatory; a hint would become accessibility text
        // when cleared, obscuring the distinction between no input and actual content.
        EditText field=host.field("日历月份",false);field.setText(shown[0].toString());jump.addView(field,new LinearLayout.LayoutParams(0,host.dp(48),1));
        TextView feedback=host.text("多选日期，只改变汇总范围",14,TodayScreen.MUTED);
        LinearLayout days=host.column();ScrollView scroll=new ScrollView(host.activity);scroll.addView(days);
        final Runnable[] draw=new Runnable[1];
        draw[0]=()->{
            days.removeAllViews();field.setText(shown[0].toString());
            LinearLayout week=new LinearLayout(host.activity);for(String day:new String[]{"一","二","三","四","五","六","日"}){TextView v=host.text(day,14,TodayScreen.MUTED);v.setGravity(Gravity.CENTER);week.addView(v,new LinearLayout.LayoutParams(0,host.dp(24),1));}days.addView(week);
            int offset=shown[0].atDay(1).getDayOfWeek().getValue()-1;
            int cells=((offset+shown[0].lengthOfMonth()+6)/7)*7;
            for(int start=0;start<cells;start+=7){LinearLayout row=new LinearLayout(host.activity);
                for(int col=0;col<7;col++){
                    int day=start+col-offset+1;
                    if(day<1||day>shown[0].lengthOfMonth()){row.addView(new View(host.activity),new LinearLayout.LayoutParams(0,host.dp(48),1));continue;}
                    LocalDate date=shown[0].atDay(day);String mark=state.actual.contains(date)?"•":state.planned.contains(date)?"○":"";
                    Button b=host.button(day+(mark.isEmpty()?"":"\n"+mark),()->{});b.setTextSize(14);b.setContentDescription("calendar-day-"+date);
                    Runnable tint=()->{boolean active=draft.contains(date);b.setSelected(active);b.setTextColor(active?TodayScreen.WHITE:TodayScreen.INK);b.setBackgroundTintList(ColorStateList.valueOf(active?TodayScreen.ACCENT:TodayScreen.BG));};
                    b.setOnClickListener(v->{if(!draft.add(date))draft.remove(date);tint.run();feedback.setText("已选 "+draft.size()+" 天；• 实际，○ 仅预计");});tint.run();row.addView(b,new LinearLayout.LayoutParams(0,host.dp(48),1));
                }days.addView(row);
            }
        };
        jump.addView(host.button("转到",()->{
            try{String text=field.getText().toString();if(!text.matches("[0-9]{4}-[0-9]{2}"))throw new IllegalArgumentException();YearMonth candidate=YearMonth.parse(text);Ledger.validDate(candidate.atDay(1));shown[0]=candidate;draw[0].run();hideKeyboard(field);body.requestFocus();feedback.setText("已选 "+draft.size()+" 天；• 实际，○ 仅预计");}
            catch(RuntimeException e){feedback.setText("月份无效，请输入 YYYY-MM");}
        }),new LinearLayout.LayoutParams(host.dp(64),host.dp(48)));body.addView(jump);
        LinearLayout nav=new LinearLayout(host.activity);
        nav.addView(host.button("上月",()->shift(shown,-1,draw[0],feedback)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        nav.addView(host.button("下月",()->shift(shown,1,draw[0],feedback)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        nav.addView(host.button("清空选择",()->{draft.clear();draw[0].run();feedback.setText("已选 0 天");}),new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(nav);body.addView(feedback);
        int height=Math.min(host.dp(300),Math.max(host.dp(144),host.activity.getResources().getDisplayMetrics().heightPixels/2));
        body.addView(scroll,new LinearLayout.LayoutParams(-1,height));draw[0].run();
        AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("选择汇总日期").setView(body).setNegativeButton("取消",null).setPositiveButton("应用选择",(d,w)->{selected.clear();selected.addAll(draft);month=shown[0];load();}).create();
        dialog.show();body.requestFocus();
    }
    private void shift(YearMonth[] shown,int delta,Runnable draw,TextView feedback){
        try{YearMonth next=shown[0].plusMonths(delta);Ledger.validDate(next.atDay(1));shown[0]=next;draw.run();}
        catch(RuntimeException e){feedback.setText("日期范围为 0001-01 至 9999-12");}
    }
    private void hideKeyboard(View view){((InputMethodManager)host.activity.getSystemService(android.app.Activity.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(view.getWindowToken(),0);}
    /** One explicitly opened draft, not a transformation of the date filter. */
    static final class BatchDraft {
        final long activity;final String key=UUID.randomUUID().toString();
        private final ArrayList<Ledger.Entry> rows=new ArrayList<>();
        private List<Ledger.Entry> review;private boolean closed,submitted,inFlight;
        BatchDraft(long activity){this.activity=Ledger.positive(activity);}
        void add(String day,Ledger.Kind kind,String amount,String memo){
            if(closed||review!=null||submitted)throw new IllegalStateException("批次不再可编辑");
            LocalDate date=Ledger.validDate(LocalDate.parse(day));if(!date.toString().equals(day))throw new IllegalArgumentException("日期格式错误");
            rows.add(new Ledger.Entry(UUID.randomUUID().toString(),activity,date,kind,Ledger.parseCents(amount),memo));
        }
        void removeLast(){if(closed||review!=null||submitted||rows.isEmpty())throw new IllegalStateException("没有可移除的草稿行");rows.remove(rows.size()-1);}
        List<Ledger.Entry> rows(){return Collections.unmodifiableList(new ArrayList<>(rows));}
        void freeze(){if(closed||review!=null||rows.isEmpty())throw new IllegalStateException("批次为空或已核对");
            long[] totals=new long[Ledger.Kind.values().length];for(Ledger.Entry e:rows)totals[e.kind.ordinal()]=Math.addExact(totals[e.kind.ordinal()],e.cents);
            Math.subtractExact(Math.addExact(totals[Ledger.Kind.INCOME.ordinal()],totals[Ledger.Kind.REFUND.ordinal()]),totals[Ledger.Kind.EXPENSE.ordinal()]);
            review=rows();
        }
        void editAgain(){if(closed||submitted||review==null)throw new IllegalStateException("请使用同一份核对结果");review=null;}
        List<Ledger.Entry> begin(){if(closed||inFlight||review==null)throw new IllegalStateException("批次未核对或已提交");inFlight=true;submitted=true;return review;}
        void failed(){if(!closed)inFlight=false;}
        void close(){closed=true;rows.clear();review=null;}
    }
    private MoneyWindow activeMoney;
    private final class MoneyWindow implements View.OnAttachStateChangeListener {
        final Button anchor;final BatchDraft draft;AlertDialog box;boolean dead;
        MoneyWindow(Button anchor,BatchDraft draft){this.anchor=anchor;this.draft=draft;activeMoney=this;anchor.addOnAttachStateChangeListener(this);}
        boolean live(){return !dead&&activeMoney==this&&anchor.isAttachedToWindow()&&!host.activity.isFinishing()&&!host.activity.isDestroyed();}
        boolean input(View v){return live()&&anchor.isEnabled()&&box!=null&&box.isShowing()&&v.isAttachedToWindow()&&v.isEnabled();}
        void close(){if(dead)return;dead=true;if(activeMoney==this)activeMoney=null;anchor.removeOnAttachStateChangeListener(this);if(draft!=null)draft.close();
            AlertDialog d=box;box=null;if(d!=null){d.setOnDismissListener(null);if(d.isShowing())d.dismiss();}}
        @Override public void onViewAttachedToWindow(View v){}
        @Override public void onViewDetachedFromWindow(View v){close();}
        void show(AlertDialog d){box=d;d.setOnDismissListener(x->close());try{d.show();}catch(android.view.WindowManager.BadTokenException|IllegalStateException stale){close();}}
    }
    private boolean moneyEntryReady(Button b){return activeMoney==null&&b.isEnabled()&&b.isAttachedToWindow()&&!host.activity.isDestroyed()&&!host.activity.isFinishing();}
    private static String batchLines(List<Ledger.Entry> rows){
        if(rows.isEmpty())return "尚未加入账目。";StringBuilder text=new StringBuilder();int i=0;
        for(Ledger.Entry e:rows){if(i>0)text.append('\n');text.append(++i).append(". ").append(e.date).append("  ").append(LABELS[e.kind.ordinal()]).append(" ¥").append(yuan(e.cents));if(!e.memo.isEmpty())text.append("  ").append(e.memo);}
        return text.toString();
    }
    private void openBatch(Button anchor){
        if(!moneyEntryReady(anchor))return;
        BatchDraft draft=new BatchDraft(activityId);MoneyWindow window=new MoneyWindow(anchor,draft);
        LinearLayout body=host.column();body.setPadding(host.dp(16),host.dp(4),host.dp(16),host.dp(8));body.setFocusableInTouchMode(true);
        TextView intro=host.text("逐行加入日期和金额。这里不会自动套用日历所选日期，也不会打卡。",14,TodayScreen.MUTED);body.addView(intro);
        LinearLayout edit=host.column();body.addView(edit);EditText date=host.field("批次日期",false);date.setHint("YYYY-MM-DD");date.setText(LocalDate.now(ZoneId.of("Asia/Shanghai")).toString());edit.addView(date);
        RadioGroup kinds=new RadioGroup(host.activity);kinds.setOrientation(RadioGroup.HORIZONTAL);
        for(Ledger.Kind kind:Ledger.Kind.values()){RadioButton b=new RadioButton(host.activity);b.setId(View.generateViewId());b.setTag(kind);b.setText(LABELS[kind.ordinal()]);b.setTextSize(14);kinds.addView(b,new RadioGroup.LayoutParams(0,host.dp(48),1));if(kind==Ledger.Kind.EXPENSE)kinds.check(b.getId());}edit.addView(kinds);
        EditText amount=host.field("批次金额（元）",false);amount.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL);amount.setHint("逐笔输入，0 元也需明确填写");edit.addView(amount);
        LinearLayout presets=new LinearLayout(host.activity);for(String yuan:new String[]{"0","5","10","20"}){Button p=host.button(yuan+" 元",()->{});p.setOnClickListener(v->{if(window.input(v)){amount.setText(yuan);amount.setSelection(amount.length());}});presets.addView(p,new LinearLayout.LayoutParams(0,host.dp(48),1));}edit.addView(presets);
        EditText memo=host.field("批次备注",false);memo.setHint("此行备注（可留空）");edit.addView(memo);
        LinearLayout actions=new LinearLayout(host.activity);Button add=host.button("加入本行",()->{}),remove=host.button("移除末行",()->{});actions.addView(add,new LinearLayout.LayoutParams(0,host.dp(48),1));actions.addView(remove,new LinearLayout.LayoutParams(0,host.dp(48),1));edit.addView(actions);
        TextView lines=host.text("尚未加入账目。",15,TodayScreen.INK);body.addView(lines);
        TextView note=host.text("尚未记账。",14,TodayScreen.MUTED);note.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);body.addView(note);
        Button revise=host.button("返回修改草稿",()->{});revise.setVisibility(View.GONE);body.addView(revise);
        Runnable redraw=()->{lines.setText(batchLines(draft.rows()));remove.setEnabled(!draft.rows.isEmpty());};redraw.run();
        add.setOnClickListener(v->{if(!window.input(v))return;try{
            RadioButton choice=kinds.findViewById(kinds.getCheckedRadioButtonId());draft.add(date.getText().toString(),(Ledger.Kind)choice.getTag(),amount.getText().toString(),memo.getText().toString());
            amount.setText("");memo.setText("");redraw.run();note.setText("已加入草稿，还未记账。");
        }catch(java.time.DateTimeException|IllegalArgumentException|ArithmeticException invalid){note.setText("本行未加入：请填真实日期及非负金额，金额最多两位小数。");}});
        remove.setOnClickListener(v->{if(!window.input(v))return;draft.removeLast();redraw.run();note.setText("已移除草稿末行，账本未改变。");});
        ScrollView scroll=new ScrollView(host.activity);scroll.addView(body);
        AlertDialog d=new AlertDialog.Builder(host.activity).setTitle("批量记账").setView(scroll).setNegativeButton("取消",null).setPositiveButton("核对批次",null).create();
        revise.setOnClickListener(v->{if(!window.input(v))return;draft.editAgain();edit.setVisibility(View.VISIBLE);revise.setVisibility(View.GONE);d.setTitle("批量记账");d.getButton(AlertDialog.BUTTON_POSITIVE).setText("核对批次");note.setText("修改后需重新核对。");});
        d.setOnShowListener(x->{Button submit=d.getButton(AlertDialog.BUTTON_POSITIVE);submit.setOnClickListener(v->{if(!window.input(v)||draft.inFlight)return;
            if(draft.review==null){
                if(amount.length()!=0||memo.length()!=0){note.setText("当前行尚未加入。请先点“加入本行”，或清空本行金额和备注。");return;}
                try{draft.freeze();}catch(IllegalStateException|ArithmeticException invalid){note.setText("不能提交：请至少加入一行，并检查合计是否过大。");return;}
                hideKeyboard(amount);edit.setVisibility(View.GONE);revise.setVisibility(View.VISIBLE);d.setTitle("核对批次");note.setText("活动："+title+"。核对以上 "+draft.review.size()+" 行后再记账。预计不算实际收支。");submit.setText("确认记账");scroll.smoothScrollTo(0,0);return;
            }
            final List<Ledger.Entry> frozen=draft.begin();final String key=draft.key;submit.setEnabled(false);revise.setVisibility(View.GONE);d.setCancelable(false);d.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);
            host.work(()->host.db.recordActivityBatch(activityId,key,frozen),inserted->{if(!window.live())return;window.close();host.message(inserted?"已保存整个批次，共 "+frozen.size()+" 笔。":"相同批次已保存，没有重复记账。",false);load();},()->{
                if(!window.live())return;draft.failed();d.setCancelable(true);d.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);submit.setEnabled(true);submit.setText("重试同一批次");note.setText("未能确认保存结果。重试只使用已核对的同一批次，不另记一份。");
            });
        });});window.show(d);body.requestFocus();
    }
    private void openUndo(Button anchor,AppDatabase.MoneyUndoReview plan){
        if(!moneyEntryReady(anchor)||plan==null||plan.activity!=activityId)return;MoneyWindow window=new MoneyWindow(anchor,null);
        AlertDialog d=new AlertDialog.Builder(host.activity).setTitle("撤销最近批次？").setMessage("活动："+title+"。只撤销下面 "+plan.rows.size()+" 笔，其他账目和打卡不变。\n"+batchLines(plan.rows)).setNegativeButton("取消",null).setPositiveButton("确认撤销",null).create();
        d.setOnShowListener(x->d.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{if(!window.input(v))return;v.setEnabled(false);d.setCancelable(false);d.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);
            host.work(()->{host.db.undoActivityBatch(plan);return true;},o->{if(window.live()){window.close();load();}},()->{if(window.live()){window.close();load();host.message("账目可能已变化，未撤销；请重新核对。",true);}});
        }));window.show(d);
    }

    private void entryDialog(){
        LinearLayout body=host.column();body.setPadding(host.dp(16),host.dp(4),host.dp(16),host.dp(4));
        body.addView(host.text("仅新增一笔，不向所选多日批量写入。",14,TodayScreen.MUTED));
        EditText date=host.field("账目日期",false);date.setText((selected.size()==1?selected.iterator().next():LocalDate.now(ZoneId.of("Asia/Shanghai"))).toString());body.addView(date);
        body.addView(host.text("退款填实际到账日；预计金额不算实际收支。",14,TodayScreen.MUTED));
        RadioGroup kinds=new RadioGroup(host.activity);kinds.setOrientation(RadioGroup.HORIZONTAL);
        for(Ledger.Kind kind:Ledger.Kind.values()){RadioButton b=new RadioButton(host.activity);b.setId(View.generateViewId());b.setTag(kind);b.setContentDescription("ledger-kind-"+kind.name());b.setText(LABELS[kind.ordinal()]);b.setTextSize(14);b.setPadding(0,0,0,0);kinds.addView(b,new RadioGroup.LayoutParams(0,host.dp(48),1));if(kind==Ledger.Kind.EXPENSE)kinds.check(b.getId());}body.addView(kinds);
        EditText amount=host.field("金额（元）",false);amount.setHint("金额（元），例如 15.00");amount.setInputType(InputType.TYPE_CLASS_NUMBER|InputType.TYPE_NUMBER_FLAG_DECIMAL);body.addView(amount);
        EditText memo=host.field("账目备注",false);memo.setHint("备注（可留空）");body.addView(memo);
        TextView validation=host.text("金额精确到分，保存后可在所选日期查看。",14,TodayScreen.MUTED);body.addView(validation);
        ScrollView scroll=new ScrollView(host.activity);scroll.addView(body);
        String key=UUID.randomUUID().toString(),id=UUID.randomUUID().toString();
        AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("记一笔").setView(scroll).setNegativeButton("取消",null).setPositiveButton("保存账目",null).create();
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            long cents;LocalDate day;
            try{cents=Ledger.parseCents(amount.getText().toString());}
            catch(RuntimeException e){validation.setText("金额无效：请输入非负金额，最多两位小数");validation.setTextColor(TodayScreen.ERROR);hideKeyboard(amount);return;}
            try{String value=date.getText().toString();day=Ledger.validDate(LocalDate.parse(value));if(!value.equals(day.toString()))throw new IllegalArgumentException();}
            catch(RuntimeException e){validation.setText("日期无效：请填写真实的 YYYY-MM-DD");validation.setTextColor(TodayScreen.ERROR);hideKeyboard(date);return;}
            RadioButton chosen=kinds.findViewById(kinds.getCheckedRadioButtonId());
            Ledger.Entry entry=new Ledger.Entry(id,activityId,day,(Ledger.Kind)chosen.getTag(),cents,memo.getText().toString());
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);
            date.setEnabled(false);amount.setEnabled(false);memo.setEnabled(false);for(int i=0;i<kinds.getChildCount();i++)kinds.getChildAt(i).setEnabled(false);
            host.work(()->host.db.recordBatch(key,Collections.singletonList(entry)),ignored->{hideKeyboard(amount);dialog.dismiss();load();},()->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);
                date.setEnabled(true);amount.setEnabled(true);memo.setEnabled(true);for(int i=0;i<kinds.getChildCount();i++)kinds.getChildAt(i).setEnabled(true);validation.setText("未能保存，请检查后重试；不会重复记同一笔");validation.setTextColor(TodayScreen.ERROR);
            });
        }));
        dialog.show();
    }
}
