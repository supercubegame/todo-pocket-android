package com.supercubegame.pockettodo;

import android.app.AlertDialog;
import android.database.Cursor;
import android.graphics.Color;
import android.widget.*;
import java.io.IOException;
import java.io.ByteArrayOutputStream;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Native single-note editor for an activity: ordered text then image blocks.
 * Text and a synthetic registered image only; real gallery/camera selection,
 * decoding, thumbnails, crop and opaque redaction remain subsequent work.
 * Writes go through validated AppDatabase APIs; UI read queries never mutate raw SQL.
 */
public final class NoteEditorScreen {
    private final TodayScreen host;
    private final long activityId;
    private final String title;
    private final Runnable back;
    private static final class State {
        String noteId;
        final List<NoteDocument.Block> blocks=new ArrayList<>();
        MediaRepository media;
    }
    NoteEditorScreen(TodayScreen host,long activityId,String title,Runnable back){this.host=host;this.activityId=activityId;this.title=title;this.back=back;}
    void load(){
        host.work(()->{
            State s=new State();
            s.media=new MediaRepository(host.activity.getFilesDir().toPath().resolve("media"),64L*1024*1024);
            List<String> ids=new ArrayList<>();
            try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT id FROM notes WHERE activity_id=? ORDER BY rowid",new String[]{Long.toString(activityId)})){while(c.moveToNext())ids.add(c.getString(0));}
            if(!ids.isEmpty()){s.noteId=ids.get(0);s.blocks.addAll(host.db.noteBlocks(s.noteId));}
            return s;
        },this::render,null);
    }
    private void render(State s){
        LinearLayout body=host.content();
        LinearLayout header=new LinearLayout(host.activity);
        header.addView(host.button("返回活动",back),new LinearLayout.LayoutParams(0,host.dp(48),1));
        TextView name=host.text("笔记",22,TodayScreen.INK);name.setGravity(android.view.Gravity.CENTER);header.addView(name,new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(header);
        TextView owner=host.text(title+" · 图文并存，图是登记的本地副本",15,TodayScreen.MUTED);owner.setMaxLines(2);owner.setPadding(0,host.dp(4),0,host.dp(10));body.addView(owner);
        LinearLayout actions=new LinearLayout(host.activity);
        actions.addView(host.button("加入文字",()->editText(s,null)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        actions.addView(host.button("加入图片",()->addImage(s)),new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(actions);
        ScrollView scroll=new ScrollView(host.activity);LinearLayout list=host.column();scroll.addView(list);body.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        if(s.blocks.isEmpty()){TextView empty=host.text("写点什么，或加一张图。",18,TodayScreen.MUTED);empty.setPadding(0,host.dp(24),0,0);list.addView(empty);}
        for(int i=0;i<s.blocks.size();i++){
            NoteDocument.Block b=s.blocks.get(i);
            if(b.kind==NoteDocument.Kind.TEXT){
                TextView text=host.text(b.text,17,TodayScreen.INK);text.setContentDescription("note-text-"+b.id);text.setPadding(host.dp(10),host.dp(10),host.dp(10),host.dp(10));text.setBackground(host.shape(TodayScreen.WHITE,10));list.addView(text);
                Button edit=host.button("修改文字",()->editText(s,b.id));edit.setContentDescription("note-edit-"+b.id);
                list.addView(edit,new LinearLayout.LayoutParams(-1,host.dp(48)));
            }else{
                LinearLayout row=host.column();row.setPadding(host.dp(10),host.dp(8),host.dp(10),host.dp(8));row.setBackground(host.shape(TodayScreen.WHITE,10));
                try{
                    Path path=s.media.path(b.assetId);
                    android.graphics.Bitmap image=android.graphics.BitmapFactory.decodeFile(path.toString());
                    ImageView view=new ImageView(host.activity);
                    if(image!=null){view.setImageBitmap(image);view.setAdjustViewBounds(true);view.setMaxHeight(host.dp(220));}
                    else{view.setBackgroundColor(TodayScreen.TINT);view.setMinimumHeight(host.dp(96));}
                    view.setContentDescription("note-image-"+b.id);row.addView(view);
                }catch(IOException e){TextView broken=host.text("图片副本不可用",15,TodayScreen.ERROR);broken.setContentDescription("note-image-"+b.id);row.addView(broken);}
                if(!b.caption.isEmpty())row.addView(host.text(b.caption,14,TodayScreen.MUTED));
                list.addView(row);
            }
        }
    }
    /** Own dialog, not the shared editor helper: that one intentionally accepts blank
     * multiline input for path clearing, while a note text block must never be blank. */
    private void editText(State s,String existingId){
        NoteDocument.Block existing=null;
        if(existingId!=null)for(NoteDocument.Block b:s.blocks)if(b.id.equals(existingId)&&b.kind==NoteDocument.Kind.TEXT)existing=b;
        if(existingId!=null&&existing==null)throw new IllegalArgumentException("文字块不存在");
        String initial=existing==null?"":existing.text;
        final boolean privateContent=existing!=null&&existing.privateContent;
        LinearLayout body=host.column();body.setPadding(host.dp(20),host.dp(4),host.dp(20),host.dp(8));
        EditText field=host.field("文字内容",true);field.setText(initial);body.addView(field,new LinearLayout.LayoutParams(-1,-2));
        TextView validation=host.text("文字不能为空，之后可随时修改。",14,TodayScreen.MUTED);body.addView(validation);
        AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle(existingId==null?"加入文字":"修改文字").setView(body).setNegativeButton("取消",null).setPositiveButton("保存",null).create();
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String value=field.getText().toString().trim();
            if(value.isEmpty()){validation.setText("内容不能为空");validation.setTextColor(TodayScreen.ERROR);return;}
            final String id=existingId==null?UUID.randomUUID().toString():existingId;
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);field.setEnabled(false);
            host.work(()->{persist(s,NoteDocument.Block.text(id,value,privateContent),existingId!=null);return true;},ignored->{dialog.dismiss();load();},()->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);field.setEnabled(true);validation.setText("未能保存，请检查内容后重试");validation.setTextColor(TodayScreen.ERROR);
            });
        }));
        dialog.show();
    }
    /** Synthetic solid square. Real photo selection, decoding and derivative checks are separate. */
    private void addImage(State s){
        AlertDialog pick=new AlertDialog.Builder(host.activity).setTitle("加入图片").setMessage("当前切片使用合成图片验证登记与排序；相册与相机选择还没接。")
            .setNegativeButton("取消",null).setPositiveButton("加入合成图",null).create();
        pick.setOnShowListener(unused->pick.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            pick.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
            host.work(()->{
                android.graphics.Bitmap image=android.graphics.Bitmap.createBitmap(96,96,android.graphics.Bitmap.Config.ARGB_8888);
                image.eraseColor(Color.parseColor("#21785f"));
                ByteArrayOutputStream out=new ByteArrayOutputStream();
                if(!image.compress(android.graphics.Bitmap.CompressFormat.PNG,100,out))throw new IOException("无法生成图片");
                byte[] bytes=out.toByteArray();
                String assetId=s.media.copy(new java.io.ByteArrayInputStream(bytes));
                host.db.registerMedia(assetId,"image/png",bytes.length);
                String blockId=UUID.randomUUID().toString();
                persistBlocks(s,NoteDocument.Block.image(blockId,assetId,"",false),false);
                return true;
            },ignored->{pick.dismiss();load();},()->pick.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true));
        }));
        pick.show();
    }
    private void persist(State s,NoteDocument.Block block,boolean replacing){persistBlocks(s,block,replacing);}
    private void persistBlocks(State s,NoteDocument.Block block,boolean replacing){
        String noteId=s.noteId;
        if(noteId==null){noteId=UUID.randomUUID().toString();host.db.createNote(noteId,activityId,title);s.noteId=noteId;}
        List<NoteDocument.Block> next=new ArrayList<>(s.blocks);
        if(replacing){for(int i=0;i<next.size();i++)if(next.get(i).id.equals(block.id)){next.set(i,block);break;}}
        else next.add(block);
        host.db.saveNote(noteId,next);
    }
}
