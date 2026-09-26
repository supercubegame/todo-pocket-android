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
        final long[] totals=new long[6];int actualSelected;
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
            state.actualSelected=ledger.recordedActualDates(activityId,dates).size();return state;
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
