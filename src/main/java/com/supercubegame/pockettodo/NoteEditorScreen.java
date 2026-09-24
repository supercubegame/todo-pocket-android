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

/** Native activity note editor: stable note selection and ordered text/image blocks.
 * SAF-selected PNG/JPEG originals are private immutable copies, with bounded previews.
 * Camera, EXIF orientation, crop and opaque redaction remain subsequent work.
 * Writes go through validated AppDatabase APIs; UI read queries never mutate raw SQL.
 */
public final class NoteEditorScreen {
    /** Local derivative session. Caller runs prepare/confirm off the UI thread and
     * closes on abandonment. Lock order: Editor then AppDatabase, never reversed.
     * Separate from the pure codec so its compiled mutation controls stay isolated.
     */
    public static final class Editor implements AutoCloseable {
        private static final int MAX_BYTES=8*1024*1024;
        private final AppDatabase app;
        private final MediaRepository media;
        private final android.database.sqlite.SQLiteDatabase connection;
        private final java.util.Set<Preview> previews=new java.util.HashSet<>();
        private boolean closed;
        public Editor(AppDatabase app,MediaRepository media){
            if(app==null||media==null)throw new IllegalArgumentException("Missing editor storage");
            this.app=app;this.media=media;
            synchronized(app){
                connection=app.getWritableDatabase();
                if(connection.getVersion()!=3)throw new IllegalArgumentException("Editor requires schema3");
            }
        }
        private void active(){
            if(closed||!connection.isOpen()||app.getWritableDatabase()!=connection)
                throw new IllegalStateException("Editor no longer active");
        }
        private void noOuter(){
            if(connection.inTransaction())throw new IllegalStateException("Editor refuses outer transaction");
        }
        private NoteDocument.ImageEdit target(String note,String block){
            Ledger.identifier(note);Ledger.identifier(block);
            try(Cursor c=connection.rawQuery("SELECT kind,asset_id,caption,private,original_asset_id FROM blocks WHERE note_id=? AND id=?",new String[]{note,block})){
                if(!c.moveToFirst()||!"IMAGE".equals(c.getString(0)))throw new IllegalArgumentException("Image target not found");
                return new NoteDocument.ImageEdit(note,NoteDocument.Block.image(block,c.getString(1),c.getString(2),c.getInt(3)!=0),c.isNull(4)?null:c.getString(4));
            }
        }
        private long registeredSize(String id){
            try(Cursor c=connection.rawQuery("SELECT bytes FROM media WHERE id=?",new String[]{id})){
                if(!c.moveToFirst()||c.getLong(0)<=0||c.getLong(0)>MAX_BYTES)throw new IllegalArgumentException("Image registry size invalid");
                return c.getLong(0);
            }
        }
        private byte[] actual(String id,long expected)throws IOException{
            media.verify(id);Path path=media.path(id);
            if(java.nio.file.Files.size(path)!=expected)throw new IOException("Image registered size differs");
            byte[] bytes=new byte[(int)expected];
            try(java.io.DataInputStream in=new java.io.DataInputStream(java.nio.file.Files.newInputStream(path,java.nio.file.StandardOpenOption.READ,java.nio.file.LinkOption.NOFOLLOW_LINKS))){
                in.readFully(bytes);
                if(in.read()!=-1)throw new IOException("Image grew while reading");
            }
            if(!id.equals(MediaRepository.digest(bytes)))throw new IOException("Image digest differs");
            return bytes;
        }
        private void unchanged(Preview plan){
            active();
            if(!java.util.Arrays.equals(plan.before,app.exportState()))throw new IllegalStateException("Database changed; review image again");
        }
        public synchronized Preview prepare(String note,String block,int left,int top,int right,int bottom,int[][] masks)throws IOException{
            synchronized(app){
                active();noOuter();
                byte[] before;NoteDocument.ImageEdit edit;long currentSize,originalSize;
                connection.beginTransaction();
                try{
                    before=app.exportState();edit=target(note,block);
                    currentSize=registeredSize(edit.revision().assetId);originalSize=registeredSize(edit.revision().originalAssetId);
                    connection.setTransactionSuccessful();
                }finally{connection.endTransaction();}
                byte[] source=actual(edit.revision().assetId,currentSize);
                if(!edit.revision().assetId.equals(edit.revision().originalAssetId))actual(edit.revision().originalAssetId,originalSize);
                byte[] output=ShareExporter.png(source,left,top,right,bottom,masks,1000000L);
                Preview plan=new Preview(this,before,edit,output,currentSize,originalSize);
                try{
                    connection.beginTransaction();
                    try{unchanged(plan);connection.setTransactionSuccessful();}finally{connection.endTransaction();}
                    previews.add(plan);return plan;
                }catch(RuntimeException failure){plan.clear();throw failure;}
            }
        }
        /** UI consent remains the caller's responsibility. Owner attempts consume
         * the token. Late rollback may leave an immutable orphan: never delete it,
         * because a concurrent writer might already reference the published bytes.
         */
        public synchronized void confirm(Preview plan)throws IOException{
            if(plan==null||plan.owner!=this)throw new IllegalArgumentException("Preview belongs to a different editor");
            synchronized(app){
                if(plan.terminal)throw new IllegalStateException("Preview no longer active");
                plan.terminal=true;
                try{
                    active();noOuter();
                    connection.beginTransaction();
                    try{unchanged(plan);connection.setTransactionSuccessful();}finally{connection.endTransaction();}
                    actual(plan.edit.revision().assetId,plan.currentSize);
                    if(!plan.edit.revision().assetId.equals(plan.edit.revision().originalAssetId))actual(plan.edit.revision().originalAssetId,plan.originalSize);
                    String id=MediaRepository.digest(plan.output);
                    if(!id.equals(media.copy(new java.io.ByteArrayInputStream(plan.output))))throw new IOException("Derivative publication differs");
                    actual(id,plan.output.length);
                    connection.beginTransaction();
                    try{
                        unchanged(plan);
                        try(Cursor c=connection.rawQuery("SELECT mime,bytes FROM media WHERE id=?",new String[]{id})){
                            if(c.moveToFirst()){
                                if(!"image/png".equals(c.getString(0))||c.getLong(1)!=plan.output.length)throw new IllegalStateException("Derivative registry conflict");
                            }else connection.execSQL("INSERT INTO media VALUES(?,?,?)",new Object[]{id,"image/png",plan.output.length});
                        }
                        connection.execSQL("UPDATE blocks SET asset_id=?,original_asset_id=? WHERE note_id=? AND id=?",
                            new Object[]{id,plan.edit.revision().originalAssetId,plan.edit.noteId,plan.edit.blockId});
                        long next;
                        try(Cursor c=connection.rawQuery("SELECT value FROM revision WHERE id=1",null)){
                            if(!c.moveToFirst())throw new IllegalStateException("Missing revision");
                            next=Math.incrementExact(c.getLong(0));
                        }
                        connection.execSQL("UPDATE revision SET value=? WHERE id=1",new Object[]{next});
                        NoteDocument.ImageEdit saved=target(plan.edit.noteId,plan.edit.blockId);
                        if(!saved.revision().assetId.equals(id)||!saved.revision().originalAssetId.equals(plan.edit.revision().originalAssetId)||
                            !saved.caption.equals(plan.edit.caption)||saved.privateContent!=plan.edit.privateContent)
                            throw new IllegalStateException("Derivative readback differs");
                        app.exportState(); // Full semantics and encoded-state budget before commit.
                        connection.setTransactionSuccessful();
                    }finally{connection.endTransaction();}
                }finally{plan.clear();previews.remove(plan);}
            }
        }
        @Override public synchronized void close(){
            closed=true;for(Preview plan:previews)plan.clear();previews.clear();
        }
    }
    /** Owned output only; closing drops the in-memory output and comparison bytes. */
    public static final class Preview implements AutoCloseable {
        private final Editor owner;
        private final NoteDocument.ImageEdit edit;
        private final long currentSize,originalSize;
        private byte[] before,output;
        private boolean terminal;
        private Preview(Editor owner,byte[] before,NoteDocument.ImageEdit edit,byte[] output,long currentSize,long originalSize){
            this.owner=owner;this.before=before;this.edit=edit;this.output=output;this.currentSize=currentSize;this.originalSize=originalSize;
        }
        public byte[] png(){
            synchronized(owner){synchronized(owner.app){
                if(terminal)throw new IllegalStateException("Preview no longer active");
                owner.active();return output.clone();
            }}
        }
        private void clear(){terminal=true;before=null;output=null;}
        @Override public void close(){synchronized(owner){clear();owner.previews.remove(this);}}
    }
    private final TodayScreen host;
    private final long activityId;
    private final String title;
    private final Runnable back;
    // Selection belongs to this screen instance; a fresh screen defaults to the first note.
    private String selectedNote;
    private static final class State {
        String noteId;
        final List<String> ids=new ArrayList<>(),titles=new ArrayList<>();
        final List<NoteDocument.Block> blocks=new ArrayList<>();
        MediaRepository media;
        final java.util.Map<String,android.graphics.Bitmap> previews=new java.util.HashMap<>();
    }
    NoteEditorScreen(TodayScreen host,long activityId,String title,Runnable back){this.host=host;this.activityId=activityId;this.title=title;this.back=back;}
    void load(){
        final String requested=selectedNote;
        host.work(()->{
            State s=new State();
            s.media=new MediaRepository(host.activity.getFilesDir().toPath().resolve("media"),64L*1024*1024);
            try(Cursor c=host.db.getReadableDatabase().rawQuery("SELECT id,title FROM notes WHERE activity_id=? ORDER BY rowid",new String[]{Long.toString(activityId)})){while(c.moveToNext()){s.ids.add(c.getString(0));s.titles.add(c.getString(1));}}
            if(requested!=null&&!s.ids.contains(requested))throw new IllegalStateException("所选笔记已不存在，请返回活动重新打开");
            if(!s.ids.isEmpty()){s.noteId=requested==null?s.ids.get(0):requested;s.blocks.addAll(host.db.noteBlocks(s.noteId));}
            for(NoteDocument.Block b:s.blocks)if(b.kind==NoteDocument.Kind.IMAGE){
                try{s.previews.put(b.id,decodePreview(s.media.path(b.assetId)));}
                catch(IOException ignored){/* Render an explicit unavailable marker, never a fake image. */}
            }
            return s;
        },this::render,null);
    }
    private void render(State s){
        selectedNote=s.noteId;
        LinearLayout body=host.content();
        LinearLayout header=new LinearLayout(host.activity);
        header.addView(host.button("返回活动",back),new LinearLayout.LayoutParams(0,host.dp(48),1));
        header.addView(host.button("新建笔记",this::createNote),new LinearLayout.LayoutParams(0,host.dp(48),1));
        Button choose=host.button("切换笔记",()->chooseNote(s));choose.setEnabled(!s.ids.isEmpty());header.addView(choose,new LinearLayout.LayoutParams(0,host.dp(48),1));body.addView(header);
        int index=s.ids.indexOf(s.noteId);
        TextView owner=host.text(index<0?title+" · 尚无笔记":s.titles.get(index)+" · "+(index+1)+" / "+s.ids.size(),15,TodayScreen.MUTED);owner.setContentDescription("note-current");owner.setMaxLines(2);owner.setPadding(0,host.dp(4),0,host.dp(10));body.addView(owner);
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
                LinearLayout meta=new LinearLayout(host.activity);
                TextView privacy=host.text(b.privateContent?"私有图片":"非私有图片",14,TodayScreen.MUTED);privacy.setContentDescription("note-image-privacy-"+b.id);
                meta.addView(privacy,new LinearLayout.LayoutParams(0,-2,1));
                Button edit=host.button("说明 / 私有",()->editImage(s,b));edit.setContentDescription("note-image-edit-"+b.id);meta.addView(edit,new LinearLayout.LayoutParams(-2,host.dp(48)));row.addView(meta);
                if(!b.caption.isEmpty())row.addView(host.text(b.caption,14,TodayScreen.MUTED));
                android.graphics.Bitmap image=s.previews.get(b.id);
                if(image!=null){
                    ImageView view=new ImageView(host.activity);
                    view.setImageBitmap(image);view.setAdjustViewBounds(true);view.setMaxHeight(host.dp(220));
                    view.setContentDescription("note-image-"+b.id);row.addView(view);
                }else{TextView broken=host.text("图片副本不可用",15,TodayScreen.ERROR);broken.setContentDescription("note-image-"+b.id);row.addView(broken);}
                list.addView(row);
            }
        }
    }
    private void chooseNote(State s){
        String[] labels=new String[s.ids.size()];
        for(int i=0;i<labels.length;i++)labels[i]=(i+1)+". "+s.titles.get(i);
        new AlertDialog.Builder(host.activity).setTitle("选择笔记").setItems(labels,(dialog,which)->{
            selectedNote=s.ids.get(which);load();
        }).setNegativeButton("取消",null).show();
    }
    /** Creating an explicitly named empty note is intentional; cancel and blank never write.
     * IDs, not titles, drive selection, so duplicate titles never replace an existing note. */
    private void createNote(){
        LinearLayout body=host.column();body.setPadding(host.dp(20),host.dp(4),host.dp(20),host.dp(8));
        EditText field=host.field("笔记标题",false);body.addView(field,new LinearLayout.LayoutParams(-1,-2));
        TextView validation=host.text("创建后可加入文字和图片；同名笔记会分开保存。",14,TodayScreen.MUTED);body.addView(validation);
        AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("新建笔记").setView(body).setNegativeButton("取消",null).setPositiveButton("创建",null).create();
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String value=field.getText().toString().trim();
            if(value.isEmpty()){validation.setText("笔记标题不能为空");validation.setTextColor(TodayScreen.ERROR);return;}
            String id=UUID.randomUUID().toString();
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);field.setEnabled(false);
            host.work(()->{host.db.createNote(id,activityId,value);return id;},created->{selectedNote=created;dialog.dismiss();load();},()->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);field.setEnabled(true);validation.setText("未能创建，请重试");validation.setTextColor(TodayScreen.ERROR);
            });
        }));
        dialog.show();
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
    /** Metadata only: stable block/asset identity and original bytes remain untouched.
     * Private is a future sharing filter, not encryption or omission from full backups. */
    private void editImage(State s,NoteDocument.Block existing){
        LinearLayout body=host.column();body.setPadding(host.dp(20),host.dp(4),host.dp(20),host.dp(8));
        body.addView(host.text("图片说明（可留空）",14,TodayScreen.MUTED));
        EditText field=host.field("图片说明",true);field.setContentDescription("image-caption");field.setHint("");field.setText(existing.caption);body.addView(field,new LinearLayout.LayoutParams(-1,-2));
        CheckBox privacy=new CheckBox(host.activity);privacy.setText("标记为私有图片");privacy.setContentDescription("image-private");privacy.setChecked(existing.privateContent);body.addView(privacy);
        TextView validation=host.text("仅修改说明和标记，不改原图。私有不是加密，完整备份仍包含；分享排除尚未实现。",14,TodayScreen.MUTED);body.addView(validation);
        AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("图片说明与私有标记").setView(body).setNegativeButton("取消",null).setPositiveButton("保存",null).create();
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String caption=field.getText().toString().trim();boolean privateContent=privacy.isChecked();
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);field.setEnabled(false);privacy.setEnabled(false);
            host.work(()->{persist(s,NoteDocument.Block.image(existing.id,existing.assetId,caption,privateContent),true);return true;},ignored->{dialog.dismiss();load();},()->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);field.setEnabled(true);privacy.setEnabled(true);validation.setText("未能保存，请重试；原图不变");validation.setTextColor(TodayScreen.ERROR);
            });
        }));
        dialog.show();
    }
    /** Resource policy, not a measured capacity promise. Per-image limits do not bound a whole note. */
    private static final long IMAGE_BYTES=8L*1024*1024, IMAGE_PIXELS=20000000;
    private static final int IMAGE_EDGE=16384, PREVIEW_EDGE=1024;
    private static android.graphics.BitmapFactory.Options bounds(Path path)throws IOException{
        if(java.nio.file.Files.size(path)<=0||java.nio.file.Files.size(path)>IMAGE_BYTES)throw new IOException("图片字节超限");
        android.graphics.BitmapFactory.Options o=new android.graphics.BitmapFactory.Options();o.inJustDecodeBounds=true;
        android.graphics.BitmapFactory.decodeFile(path.toString(),o);
        if(o.outWidth<=0||o.outHeight<=0||o.outWidth>IMAGE_EDGE||o.outHeight>IMAGE_EDGE||
            (long)o.outWidth*o.outHeight>IMAGE_PIXELS||!("image/png".equals(o.outMimeType)||"image/jpeg".equals(o.outMimeType)))throw new IOException("图片格式或尺寸无效");
        return o;
    }
    private static android.graphics.Bitmap decodePreview(Path path)throws IOException{
        android.graphics.BitmapFactory.Options header=bounds(path),o=new android.graphics.BitmapFactory.Options();
        o.inSampleSize=1;o.inPreferredConfig=android.graphics.Bitmap.Config.ARGB_8888;
        while((header.outWidth+o.inSampleSize-1)/o.inSampleSize>PREVIEW_EDGE||(header.outHeight+o.inSampleSize-1)/o.inSampleSize>PREVIEW_EDGE)o.inSampleSize*=2;
        android.graphics.Bitmap image=android.graphics.BitmapFactory.decodeFile(path.toString(),o);
        if(image==null)throw new IOException("图片解码失败");
        if(image.getWidth()>PREVIEW_EDGE||image.getHeight()>PREVIEW_EDGE||image.getAllocationByteCount()>4*PREVIEW_EDGE*PREVIEW_EDGE){image.recycle();throw new IOException("图片解码预算超限");}
        return image;
    }
    private void importImage(State s,android.net.Uri uri){
        if(uri==null){host.message("已取消选图，没有改变笔记",false);return;}
        host.work(()->{
            Path temp=java.nio.file.Files.createTempFile(host.activity.getCacheDir().toPath(),"image-",".part");
            try{
                try(java.io.InputStream in=host.activity.getContentResolver().openInputStream(uri);
                    java.io.OutputStream out=java.nio.file.Files.newOutputStream(temp)){
                    if(in==null)throw new IOException("无法读取图片");
                    byte[] buffer=new byte[16384];long size=0;int n;
                    while((n=in.read(buffer))!=-1){if(n==0||n>IMAGE_BYTES-size)throw new IOException("图片读取超限");out.write(buffer,0,n);size+=n;}
                }
                String mime=bounds(temp).outMimeType;
                android.graphics.Bitmap probe=decodePreview(temp);probe.recycle();
                String assetId;
                try(java.io.InputStream in=java.nio.file.Files.newInputStream(temp)){assetId=s.media.copy(in);}
                android.database.sqlite.SQLiteDatabase sql=host.db.getWritableDatabase();
                sql.beginTransaction();
                try{
                    host.db.registerMedia(assetId,mime,java.nio.file.Files.size(temp));
                    persistBlocks(s,NoteDocument.Block.image(UUID.randomUUID().toString(),assetId,"",false),false);
                    sql.setTransactionSuccessful();
                }finally{sql.endTransaction();}
                return true;
            }finally{java.nio.file.Files.deleteIfExists(temp);}
        },ignored->load(),()->host.message("图片未加入：仅支持有效 PNG/JPEG，最大 8 MiB、2000 万像素、单边 16384",true));
    }
    /** Original retained privately; backups include it and any metadata. No share path yet. */
    private void addImage(State s){
        AlertDialog pick=new AlertDialog.Builder(host.activity).setTitle("加入图片").setMessage("选择 PNG/JPEG，最大 8 MiB、2000 万像素、单边 16384。保留本机原图副本及元数据，完整备份也会包含；尚不支持相机、旋转校正、裁剪遮挡或分享。")
            .setNegativeButton("取消",null).setNeutralButton("从文件选择",(dialog,which)->((MainActivity)host.activity).chooseNoteImage(uri->importImage(s,uri)))
            .setPositiveButton("加入合成图",null).create();
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
        if(noteId==null){noteId=UUID.randomUUID().toString();host.db.createNote(noteId,activityId,title);}
        List<NoteDocument.Block> next=new ArrayList<>(s.blocks);
        if(replacing){for(int i=0;i<next.size();i++)if(next.get(i).id.equals(block.id)){next.set(i,block);break;}}
        else next.add(block);
        host.db.saveNote(noteId,next);
    }
}
