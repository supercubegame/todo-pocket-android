package com.supercubegame.pockettodo;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputFilter;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.IOException;
import java.util.Arrays;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(245,247,250), INK = Color.rgb(35,37,46);
    private static final int MUTED = Color.rgb(98,106,119), ACCENT = Color.rgb(249,97,73);
    private static final int EXPORT = 41, IMPORT = 42;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private TodoModel model;
    private SharedPreferences prefs;
    private LinearLayout rows;
    private TextView count, status;
    private EditText input;
    private Button addButton, exportButton, importButton, undoButton;
    private int filter = 0;
    private final Button[] filters = new Button[3];
    private boolean storageHealthy = true, busy = false;
    private String undoState;

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
                .setMessage("本地数据无法读取，原始数据已保留。为避免覆盖，本次禁止修改和导入。")
                .setPositiveButton("知道了", null).show();
        }
        undoState = prefs.getString("before_import_v1", null);
        if (saved != null) filter = Math.max(0, Math.min(2, saved.getInt("filter", 0)));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(12), dp(18), dp(10));
        root.setBackgroundColor(BG);
        setContentView(root);
        TextView eyebrow = text("POCKET / TODO · 1.1 PREVIEW", 12, ACCENT);
        eyebrow.setLetterSpacing(0.1f);
        root.addView(eyebrow);
        TextView title = text("口袋待办", 30, INK);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        title.setPadding(0, dp(6), 0, dp(4));
        root.addView(title);
        LinearLayout backupBar = new LinearLayout(this);
        exportButton = button("导出备份"); importButton = button("导入备份"); undoButton = button("撤销导入");
        exportButton.setOnClickListener(v -> exportBackup());
        importButton.setOnClickListener(v -> chooseImport());
        undoButton.setOnClickListener(v -> undoImport());
        for (Button b : new Button[]{exportButton, importButton, undoButton}) backupBar.addView(b, new LinearLayout.LayoutParams(0, dp(48), 1));
        root.addView(backupBar);
        status = text("离线预览版 · 不读取旧版数据", 12, MUTED);
        status.setContentDescription("备份状态");
        root.addView(status);
        count = text("", 17, INK);
        count.setPadding(dp(12), dp(10), dp(12), dp(10));
        count.setBackground(shape(Color.rgb(255,225,218), 14));
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1, -2);
        cp.setMargins(0, dp(10), 0, dp(8));
        root.addView(count, cp);
        LinearLayout tabs = new LinearLayout(this);
        String[] names = {"全部", "待办", "已完成"};
        for (int i = 0; i < 3; i++) {
            final int choice = i;
            filters[i] = button(names[i]);
            filters[i].setOnClickListener(v -> { filter = choice; render(); });
            tabs.addView(filters[i], new LinearLayout.LayoutParams(0, dp(44), 1));
        }
        root.addView(tabs);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        rows = new LinearLayout(this);
        rows.setOrientation(LinearLayout.VERTICAL);
        rows.setPadding(0, dp(8), 0, dp(8));
        scroll.addView(rows);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout composer = new LinearLayout(this);
        composer.setGravity(Gravity.CENTER_VERTICAL);
        input = editText("新待办输入");
        input.setId(View.generateViewId());
        input.setHint("下一件要做的事…");
        if (saved != null) input.setText(saved.getString("draft", ""));
        input.setImeOptions(EditorInfo.IME_ACTION_DONE);
        input.setPadding(dp(12), dp(8), dp(12), dp(8));
        input.setBackground(shape(Color.WHITE, 12));
        composer.addView(input, new LinearLayout.LayoutParams(0, dp(52), 1));
        addButton = button("添加");
        addButton.setTextColor(Color.WHITE);
        addButton.setBackgroundTintList(ColorStateList.valueOf(ACCENT));
        addButton.setOnClickListener(v -> add());
        composer.addView(addButton, new LinearLayout.LayoutParams(dp(68), dp(52)));
        input.setOnEditorActionListener((v, action, event) -> {
            if (action == EditorInfo.IME_ACTION_DONE) { add(); return true; }
            return false;
        });
        root.addView(composer);
        TextView footer = text("备份未加密，请妥善保存", 12, MUTED);
        footer.setGravity(Gravity.CENTER); footer.setPadding(0, dp(6), 0, 0);
        root.addView(footer);
        render();
    }
    private boolean writable() { return storageHealthy && !busy; }
    private TodoModel copy() { return TodoModel.decode(model.encode()); }
    private boolean persist(TodoModel candidate) { return persist(candidate, null); }
    private boolean persist(TodoModel candidate, String prior) {
        if (!writable()) return false;
        SharedPreferences.Editor change = prefs.edit().putString("state_v1", candidate.encode());
        if (prior == null) change.remove("before_import_v1"); else change.putString("before_import_v1", prior);
        if (!change.commit()) {
            status.setText("保存失败，当前列表未更改，请重试");
            return false;
        }
        model = candidate; undoState = prior;
        render();
        return true;
    }
    private void add() {
        if (!writable()) return;
        try {
            TodoModel next = copy(); next.add(input.getText().toString());
            if (persist(next)) {
                input.setText(""); filter = 0; render();
                ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(input.getWindowToken(), 0);
                input.clearFocus();
            }
        } catch (IllegalArgumentException e) { input.setError(e.getMessage()); }
    }
    private void edit(TodoModel.Item item) {
        if (!writable()) return;
        EditText field = editText("编辑待办输入");
        field.setText(item.title); field.setSelectAllOnFocus(true);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("编辑待办").setView(field)
            .setNegativeButton("取消", null).setPositiveButton("保存", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            try {
                TodoModel next = copy(); next.edit(item.id, field.getText().toString());
                if (persist(next)) dialog.dismiss();
            } catch (IllegalArgumentException e) { field.setError(e.getMessage()); }
        }));
        dialog.show();
    }
    private void exportBackup() {
        if (!writable()) return;
        new AlertDialog.Builder(this).setTitle("导出备份")
            .setMessage("将导出全部 " + model.items().size() + " 条待办。文件未加密，选择的文件服务可能会同步它，请选择可信位置。")
            .setNegativeButton("取消", null).setPositiveButton("选择保存位置", (d, w) -> {
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE, "PocketTodo-backup.ptodo");
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                openPicker(intent, EXPORT);
            }).show();
    }
    private void chooseImport() {
        if (!writable()) return;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        openPicker(intent, IMPORT);
    }
    private void openPicker(Intent intent, int request) {
        try { startActivityForResult(intent, request); }
        catch (android.content.ActivityNotFoundException e) { status.setText("找不到系统文件选择器，列表未更改"); }
    }
    private byte[] readBackup(Uri uri) throws IOException {
        try (InputStream in = getContentResolver().openInputStream(uri); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            if (in == null) throw new IOException("No input stream");
            byte[] buffer = new byte[8192]; int n;
            while ((n = in.read(buffer)) != -1) {
                if (out.size() + n > BackupCodec.MAX_BYTES) throw new IOException("Backup too large");
                out.write(buffer, 0, n);
            }
            return out.toByteArray();
        }
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != EXPORT && request != IMPORT) return;
        if (result != RESULT_OK || data == null || data.getData() == null) {
            status.setText("操作已取消，列表未更改"); return;
        }
        if (!writable()) return;
        Uri uri = data.getData();
        byte[] snapshot = request == EXPORT ? BackupCodec.encode(model) : null;
        busy = true; status.setText(request == EXPORT ? "正在写入并校验备份…" : "正在检查备份…"); render();
        io.execute(() -> {
            try {
                if (request == EXPORT) {
                    try (OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
                        if (out == null) throw new IOException("No output stream");
                        out.write(snapshot); out.flush();
                    }
                    byte[] reread = readBackup(uri);
                    if (!Arrays.equals(snapshot, reread)) throw new IOException("Readback mismatch");
                    BackupCodec.decode(reread);
                    runOnUiThread(() -> { if (!isDestroyed()) { busy = false; status.setText("备份已导出并校验"); render(); } });
                } else {
                    TodoModel candidate = BackupCodec.decode(readBackup(uri));
                    runOnUiThread(() -> { if (!isDestroyed()) { busy = false; render(); previewImport(candidate); } });
                }
            } catch (IOException | RuntimeException e) {
                runOnUiThread(() -> { if (!isDestroyed()) {
                    busy = false; render();
                    status.setText(request == EXPORT ? "导出失败，文件可能不完整，请勿使用" : "导入失败：文件无效或无法读取，列表未更改");
                } });
            }
        });
    }
    private void previewImport(TodoModel candidate) {
        int completed = 0;
        for (TodoModel.Item item : candidate.items()) if (item.done) completed++;
        new AlertDialog.Builder(this).setTitle("导入预览")
            .setMessage("备份共 " + candidate.items().size() + " 条，已完成 " + completed + " 条。\n将替换当前 " + model.items().size() + " 条待办。\n导入前列表会保留，可撤销本次导入；后续编辑、新增、删除或勾选会结束撤销机会。再次导入只保留最近一次快照。")
            .setNegativeButton("取消", (d, w) -> status.setText("操作已取消，列表未更改"))
            .setPositiveButton("确认替换", (d, w) -> {
                String prior = model.encode();
                if (persist(candidate, prior)) { filter = 0; render(); status.setText("导入成功，可撤销本次导入"); }
            }).show();
    }
    private void undoImport() {
        if (!writable() || undoState == null) return;
        new AlertDialog.Builder(this).setTitle("撤销本次导入？")
            .setMessage("恢复导入前的列表。当前导入的列表将被替换。")
            .setNegativeButton("取消", null).setPositiveButton("确认撤销", (d, w) -> {
                try { if (persist(TodoModel.decode(undoState))) { filter = 0; render(); status.setText("已恢复导入前列表"); } }
                catch (IllegalArgumentException e) { status.setText("撤销快照无法读取，列表未更改"); }
            }).show();
    }
    private void render() {
        boolean enabled = writable();
        input.setEnabled(enabled); addButton.setEnabled(enabled); exportButton.setEnabled(enabled); importButton.setEnabled(enabled);
        undoButton.setEnabled(enabled && undoState != null);
        int remaining = 0;
        for (TodoModel.Item item : model.items()) if (!item.done) remaining++;
        count.setText("还剩 " + remaining + " 件  /  共 " + model.items().size() + " 件");
        for (int i = 0; i < 3; i++) {
            filters[i].setTextColor(i == filter ? Color.WHITE : MUTED);
            filters[i].setBackgroundTintList(ColorStateList.valueOf(i == filter ? INK : BG));
        }
        rows.removeAllViews(); int visible = 0;
        for (TodoModel.Item item : model.items()) {
            if ((filter == 1 && item.done) || (filter == 2 && !item.done)) continue;
            visible++;
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER_VERTICAL); row.setPadding(dp(6), dp(4), dp(2), dp(4));
            row.setBackground(shape(Color.WHITE, 14));
            CheckBox box = new CheckBox(this);
            box.setText(item.title); box.setTextSize(16); box.setTextColor(item.done ? MUTED : INK);
            box.setButtonTintList(ColorStateList.valueOf(ACCENT)); box.setContentDescription("todo-" + item.id);
            box.setMinHeight(dp(48)); box.setChecked(item.done); box.setEnabled(enabled);
            if (item.done) box.setPaintFlags(box.getPaintFlags() | Paint.STRIKE_THRU_TEXT_FLAG);
            box.setOnCheckedChangeListener((v, checked) -> {
                TodoModel next = copy(); next.toggle(item.id); if (!persist(next)) render();
            });
            row.addView(box, new LinearLayout.LayoutParams(0, -2, 1));
            Button edit = button("改"); edit.setContentDescription("edit-" + item.id); edit.setEnabled(enabled);
            edit.setBackgroundTintList(ColorStateList.valueOf(Color.WHITE)); edit.setOnClickListener(v -> edit(item));
            row.addView(edit, new LinearLayout.LayoutParams(dp(48), dp(48)));
            Button delete = button("×"); delete.setTextSize(24); delete.setContentDescription("delete-" + item.id);
            delete.setTextColor(MUTED); delete.setEnabled(enabled); delete.setBackgroundTintList(ColorStateList.valueOf(Color.WHITE));
            delete.setOnClickListener(v -> new AlertDialog.Builder(this).setTitle("删除这条待办？").setMessage(item.title)
                .setNegativeButton("取消", null).setPositiveButton("删除", (dialog, which) -> {
                    TodoModel next = copy(); next.remove(item.id); persist(next);
                }).show());
            row.addView(delete, new LinearLayout.LayoutParams(dp(48), dp(48)));
            LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(-1, -2); rp.bottomMargin = dp(8); rows.addView(row, rp);
        }
        if (visible == 0) {
            TextView empty = text(filter == 2 ? "还没有已完成的待办" : (filter == 1 ? "待办都完成了 ✓" : "清单空空，心里轻轻。\n从下面添加第一件事。"), 19, MUTED);
            empty.setGravity(Gravity.CENTER); empty.setPadding(dp(8), dp(28), dp(8), dp(18)); rows.addView(empty, new LinearLayout.LayoutParams(-1, -2));
        }
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        state.putInt("filter", filter); state.putString("draft", input.getText().toString()); super.onSaveInstanceState(state);
    }
    @Override protected void onDestroy() { io.shutdownNow(); super.onDestroy(); }
    private EditText editText(String description) {
        EditText v = new EditText(this); v.setContentDescription(description); v.setTextSize(16); v.setTextColor(INK); v.setSingleLine(true);
        v.setFilters(new InputFilter[]{new InputFilter.LengthFilter(TodoModel.MAX_TITLE)}); return v;
    }
    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private TextView text(String value, int size, int color) {
        TextView v = new TextView(this); v.setText(value); v.setTextSize(size); v.setTextColor(color); return v;
    }
    private Button button(String value) {
        Button b = new Button(this); b.setText(value); b.setTextSize(13); b.setAllCaps(false); b.setMinWidth(0); b.setMinimumWidth(0); b.setPadding(dp(4), 0, dp(4), 0); return b;
    }
    private GradientDrawable shape(int color, int radius) {
        GradientDrawable d = new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius)); return d;
    }
}
