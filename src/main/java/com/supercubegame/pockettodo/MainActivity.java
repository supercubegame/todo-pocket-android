package com.supercubegame.pockettodo;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputFilter;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;

public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(245,247,250);
    private static final int INK = Color.rgb(35,37,46);
    private static final int MUTED = Color.rgb(98,106,119);
    private static final int ACCENT = Color.rgb(249,97,73);
    private TodoModel model;
    private SharedPreferences prefs;
    private LinearLayout rows;
    private TextView count;
    private EditText input;
    private int filter = 0;
    private final Button[] filters = new Button[3];
    private boolean storageHealthy = true;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        prefs = getSharedPreferences("pocket_todo", MODE_PRIVATE);
        try { model = TodoModel.decode(prefs.getString("state_v1", "")); }
        catch (IllegalArgumentException e) {
            storageHealthy = false;
            model = new TodoModel();
            new AlertDialog.Builder(this).setTitle("数据需要检查")
                .setMessage("本地数据无法读取，原始数据已保留。为避免覆盖，本次禁止修改。")
                .setPositiveButton("知道了", null).show();
        }
        if (saved != null) filter = saved.getInt("filter", 0);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(22), dp(20), dp(22), dp(14));
        root.setBackgroundColor(BG);
        setContentView(root);
        TextView eyebrow = text("POCKET / TODO", 14, ACCENT);
        eyebrow.setLetterSpacing(0.14f);
        root.addView(eyebrow);
        TextView title = text("口袋待办", 34, INK);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        title.setPadding(0, dp(8), 0, dp(6));
        root.addView(title);
        root.addView(text("把事情记下来，一件件完成。", 16, MUTED));
        count = text("", 18, INK);
        count.setPadding(dp(16), dp(14), dp(16), dp(14));
        count.setBackground(shape(Color.rgb(255,225,218), 16));
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1, -2);
        cp.setMargins(0, dp(22), 0, dp(14));
        root.addView(count, cp);
        LinearLayout tabs = new LinearLayout(this);
        String[] names = {"全部", "待办", "已完成"};
        for (int i = 0; i < 3; i++) {
            final int choice = i;
            filters[i] = button(names[i]);
            filters[i].setOnClickListener(v -> { filter = choice; render(); });
            tabs.addView(filters[i], new LinearLayout.LayoutParams(0, dp(48), 1));
        }
        root.addView(tabs);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        rows = new LinearLayout(this);
        rows.setOrientation(LinearLayout.VERTICAL);
        rows.setPadding(0, dp(10), 0, dp(12));
        scroll.addView(rows);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout composer = new LinearLayout(this);
        composer.setGravity(Gravity.CENTER_VERTICAL);
        input = new EditText(this);
        input.setId(1001);
        input.setContentDescription("新待办输入");
        input.setHint("下一件要做的事…");
        input.setTextSize(16);
        input.setTextColor(INK);
        input.setSingleLine(true);
        input.setFilters(new InputFilter[]{new InputFilter.LengthFilter(TodoModel.MAX_TITLE)});
        input.setImeOptions(EditorInfo.IME_ACTION_DONE);
        input.setPadding(dp(12), dp(8), dp(12), dp(8));
        input.setBackground(shape(Color.WHITE, 12));
        composer.addView(input, new LinearLayout.LayoutParams(0, dp(56), 1));
        Button add = button("添加");
        add.setTextColor(Color.WHITE);
        add.setBackgroundTintList(ColorStateList.valueOf(ACCENT));
        add.setEnabled(storageHealthy);
        add.setOnClickListener(v -> add());
        composer.addView(add, new LinearLayout.LayoutParams(dp(76), dp(56)));
        input.setOnEditorActionListener((v, action, event) -> {
            if (action == EditorInfo.IME_ACTION_DONE) { add(); return true; }
            return false;
        });
        input.setEnabled(storageHealthy);
        root.addView(composer);
        TextView footer = text("仅保存在本机 · 无需登录", 14, MUTED);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(0, dp(12), 0, 0);
        root.addView(footer);
        render();
    }
    private boolean persist(TodoModel candidate) {
        if (!storageHealthy) return false;
        if (!prefs.edit().putString("state_v1", candidate.encode()).commit()) {
            Toast.makeText(this, "保存失败，请重试。当前列表未更改。", Toast.LENGTH_LONG).show();
            return false;
        }
        model = candidate;
        render();
        return true;
    }
    private void add() {
        if (!storageHealthy) return;
        try {
            TodoModel next = TodoModel.decode(model.encode());
            next.add(input.getText().toString());
            if (persist(next)) {
                input.setText("");
                filter = 0;
                render();
                ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(input.getWindowToken(), 0);
                input.clearFocus();
            }
        } catch (IllegalArgumentException e) { input.setError(e.getMessage()); }
    }
    private void render() {
        int remaining = 0;
        for (TodoModel.Item item : model.items()) if (!item.done) remaining++;
        count.setText("还剩 " + remaining + " 件  /  共 " + model.items().size() + " 件");
        for (int i = 0; i < 3; i++) {
            filters[i].setTextColor(i == filter ? Color.WHITE : MUTED);
            filters[i].setBackgroundTintList(ColorStateList.valueOf(i == filter ? INK : BG));
        }
        rows.removeAllViews();
        int visible = 0;
        for (TodoModel.Item item : model.items()) {
            if ((filter == 1 && item.done) || (filter == 2 && !item.done)) continue;
            visible++;
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(10), dp(8), dp(4), dp(8));
            row.setBackground(shape(Color.WHITE, 14));
            CheckBox box = new CheckBox(this);
            box.setText(item.title);
            box.setTextSize(17);
            box.setTextColor(item.done ? MUTED : INK);
            box.setButtonTintList(ColorStateList.valueOf(ACCENT));
            box.setContentDescription("todo-" + item.id);
            box.setMinHeight(dp(48));
            box.setChecked(item.done);
            if (item.done) box.setPaintFlags(box.getPaintFlags() | Paint.STRIKE_THRU_TEXT_FLAG);
            box.setOnCheckedChangeListener((v, checked) -> {
                TodoModel next = TodoModel.decode(model.encode());
                next.toggle(item.id);
                if (!persist(next)) render();
            });
            row.addView(box, new LinearLayout.LayoutParams(0, -2, 1));
            Button delete = button("×");
            delete.setTextSize(24);
            delete.setContentDescription("delete-" + item.id);
            delete.setTextColor(MUTED);
            delete.setBackgroundTintList(ColorStateList.valueOf(Color.WHITE));
            delete.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("删除这条待办？").setMessage(item.title)
                .setNegativeButton("取消", null)
                .setPositiveButton("删除", (dialog, which) -> {
                    TodoModel next = TodoModel.decode(model.encode());
                    next.remove(item.id);
                    persist(next);
                }).show());
            row.addView(delete, new LinearLayout.LayoutParams(dp(52), dp(52)));
            LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, -2);
            rp.bottomMargin = dp(10);
            rows.addView(row, rp);
        }
        if (visible == 0) {
            TextView empty = text(filter == 2 ? "还没有已完成的待办" :
                (filter == 1 ? "待办都完成了 ✓" : "清单空空，心里轻轻。\n从下面添加第一件事。"), 20, MUTED);
            empty.setGravity(Gravity.CENTER);
            empty.setPadding(dp(8), dp(52), dp(8), dp(24));
            rows.addView(empty, new LinearLayout.LayoutParams(-1, -2));
        }
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        state.putInt("filter", filter);
        super.onSaveInstanceState(state);
    }
    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private TextView text(String value, int size, int color) {
        TextView v = new TextView(this);
        v.setText(value); v.setTextSize(size); v.setTextColor(color);
        return v;
    }
    private Button button(String value) {
        Button b = new Button(this);
        b.setText(value); b.setTextSize(14); b.setAllCaps(false);
        b.setMinWidth(0); b.setMinimumWidth(0);
        b.setPadding(dp(6), 0, dp(6), 0);
        return b;
    }
    private GradientDrawable shape(int color, int radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color); d.setCornerRadius(dp(radius)); return d;
    }
}
