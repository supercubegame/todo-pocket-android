package com.supercubegame.pockettodo;

import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;

/** API 26: review inside the existing Activity window. No extra dialog window,
 * accessibility service changes, saved consent or alternate database write path. */
final class NoteDeleteSurface implements View.OnAttachStateChangeListener {
    private final TodayScreen host;
    private final LinearLayout container, panel;
    private final View anchor;
    private final AppDatabase.NoteDeletionPlan plan;
    private final BooleanSupplier current;
    private final Consumer<NoteDeleteSurface> retired;
    private final Runnable reload;
    private final Map<View,Integer> previous=new IdentityHashMap<>();
    private CheckBox consent;
    private TextView validation;
    private Button yes,no;
    private boolean closed, submitted, writing;

    NoteDeleteSurface(TodayScreen host, LinearLayout container, View anchor,
        AppDatabase.NoteDeletionPlan plan, BooleanSupplier current,
        Consumer<NoteDeleteSurface> retired, Runnable reload) {
        this.host=host;this.container=container;this.anchor=anchor;this.plan=plan;
        this.current=current;this.retired=retired;this.reload=reload;panel=host.column();
    }
    private boolean owned(){return !closed&&current.getAsBoolean()&&anchor.isAttachedToWindow()
        &&panel.getParent()==container&&panel.isAttachedToWindow()&&panel.isShown()
        &&!host.activity.isFinishing()&&!host.activity.isDestroyed();}
    void show(){
        if(closed||!current.getAsBoolean()||!anchor.isAttachedToWindow()||!anchor.isShown()
            ||!container.isAttachedToWindow()||host.activity.isFinishing()||host.activity.isDestroyed()){close();return;}
        try{
            panel.setFocusableInTouchMode(true);
            LinearLayout details=host.column();ScrollView sc=new ScrollView(host.activity);sc.addView(details);
            panel.addView(sc,new LinearLayout.LayoutParams(-1,0,1));
            TextView title=host.text("确认删除笔记？",22,TodayScreen.INK);details.addView(title);
            details.addView(host.text("活动："+plan.activityTitle()+"\n笔记："+plan.title()+"\n笔记标识："+plan.noteId(),15,TodayScreen.INK));
            details.addView(host.text("将删除 "+plan.blockCount()+" 个正文块、"+plan.fieldLinkCount()+" 个字段笔记关联。\n字段和值、其他笔记和图片文件均保留。",15,TodayScreen.INK));
            details.addView(host.text("删除后暂不支持撤销。取消不会修改任何内容。",15,TodayScreen.ERROR));
            consent=new CheckBox(host.activity);consent.setText("我明白只删除这一篇，且无法撤销");
            consent.setMinHeight(host.dp(48));consent.setTextSize(16);consent.setTextColor(TodayScreen.INK);
            consent.setSaveEnabled(false);consent.setChecked(false);details.addView(consent,new LinearLayout.LayoutParams(-1,-2));
            validation=host.text("",14,TodayScreen.ERROR);validation.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);details.addView(validation);
            LinearLayout bar=new LinearLayout(host.activity);no=host.button("取消",this::cancel);yes=host.button("确认删除",this::confirm);
            yes.setTextColor(TodayScreen.ERROR);bar.addView(no,new LinearLayout.LayoutParams(0,-2,1));bar.addView(yes,new LinearLayout.LayoutParams(0,-2,1));panel.addView(bar,new LinearLayout.LayoutParams(-1,-2));
            for(int i=0;i<container.getChildCount();i++){View v=container.getChildAt(i);previous.put(v,v.getVisibility());v.setVisibility(View.GONE);}
            anchor.addOnAttachStateChangeListener(this);panel.addOnAttachStateChangeListener(this);
            container.addView(panel,new LinearLayout.LayoutParams(-1,-1));panel.requestFocus();
        }catch(RuntimeException e){close();throw e;}
    }
    boolean back(){if(closed)return false;if(!writing)cancel();return true;}
    private void cancel(){
        if(!owned()||writing)return;
        boolean reread=submitted;close();
        if(reread)reload.run();else{if(anchor.isAttachedToWindow()&&anchor.isShown())anchor.requestFocus();host.message("已取消，笔记未修改。",false);}
    }
    private void confirm(){
        if(!owned()||!panel.hasWindowFocus()||submitted||!yes.isEnabled())return;
        if(!consent.isChecked()){validation.setText("请先勾选删除确认");return;}
        submitted=true;writing=true;yes.setEnabled(false);no.setEnabled(false);consent.setEnabled(false);
        host.work(()->{host.db.confirmNoteDeletion(plan);return true;},ignored->{
            writing=false;if(!owned()){close();return;}close();reload.run();
        },()->{
            writing=false;plan.close();if(!owned()){close();return;}
            no.setText("返回核对");no.setEnabled(true);validation.setText("未能确认删除结果，请返回核对笔记后再操作。");
        });
    }
    void close(){finish(true);}
    private void finish(boolean removeNow){
        if(closed)return;closed=true;anchor.removeOnAttachStateChangeListener(this);panel.removeOnAttachStateChangeListener(this);
        plan.close();if(panel.getParent()==container){panel.setVisibility(View.GONE);
            if(removeNow)container.removeView(panel);else container.post(()->{if(panel.getParent()==container)container.removeView(panel);});}
        for(Map.Entry<View,Integer> e:previous.entrySet())if(e.getKey().getParent()==container)e.getKey().setVisibility(e.getValue());
        previous.clear();retired.accept(this);
    }
    @Override public void onViewAttachedToWindow(View v){}
    @Override public void onViewDetachedFromWindow(View v){finish(false);}
}
