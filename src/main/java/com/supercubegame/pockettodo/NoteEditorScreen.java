package com.supercubegame.pockettodo;

import android.app.AlertDialog;
import android.database.Cursor;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.view.MotionEvent;
import android.view.View;
import android.widget.*;
import java.io.IOException;
import java.io.ByteArrayOutputStream;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Native activity note editor: stable note selection and ordered text/image blocks.
 * SAF-selected PNG/JPEG originals are private immutable copies, with bounded previews.
 * Camera and EXIF orientation remain subsequent work; crop and opaque redaction
 * run through the guarded derivative backend behind real touch selection.
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
                Button edit=host.button("说明 / 私有",()->editImage(s,b));edit.setContentDescription("note-image-edit-"+b.id);meta.addView(edit,new LinearLayout.LayoutParams(-2,host.dp(48)));
                Button derive=host.button("裁剪 / 遮挡",()->deriveImage(s,b));derive.setContentDescription("note-image-derive-"+b.id);meta.addView(derive,new LinearLayout.LayoutParams(-2,host.dp(48)));row.addView(meta);
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
    /** One derivative dialog session; dismissal always closes the owned preview. */
    private static final class Session {
        Editor editor;
        Preview preview;
        void close(){
            if(preview!=null){preview.close();preview=null;}
            if(editor!=null){editor.close();editor=null;}
        }
    }
    /** Real touch selection on the actually decoded preview. View coordinates map
     * through fit-center into source pixels; reports expose the exact mapping. */
    static final class SelectionView extends View {
        private final android.graphics.Bitmap preview;
        private final int srcW,srcH;
        private final Paint frame=new Paint(),dim=new Paint(),mark=new Paint();
        private final ArrayList<Rect> masks=new ArrayList<>();
        private Rect crop;
        private float downX,downY,moveX,moveY;
        private boolean dragging,redact,locked;
        private TextView cropReport,maskReport;
        SelectionView(android.content.Context context,android.graphics.Bitmap preview,int srcW,int srcH){
            super(context);
            this.preview=preview;this.srcW=srcW;this.srcH=srcH;
            frame.setStyle(Paint.Style.STROKE);frame.setStrokeWidth(3);frame.setColor(0xffffffff);
            dim.setColor(0x88203d35);
            mark.setColor(0x99a33743);
        }
        void attach(TextView cropReport,TextView maskReport){this.cropReport=cropReport;this.maskReport=maskReport;}
        void setRedact(boolean value){if(redact!=value)cancelDrag();redact=value;}
        void setLocked(boolean value){if(value)cancelDrag();locked=value;}
        void reset(){if(locked)return;cancelDrag();crop=null;masks.clear();report();invalidate();}
        private void parentGesture(boolean owned){
            if(getParent()!=null)getParent().requestDisallowInterceptTouchEvent(owned);
        }
        private void cancelDrag(){dragging=false;parentGesture(false);invalidate();}
        @Override protected void onDetachedFromWindow(){cancelDrag();super.onDetachedFromWindow();}
        @Override protected void onSizeChanged(int w,int h,int oldw,int oldh){
            if(w!=oldw||h!=oldh)cancelDrag();
            super.onSizeChanged(w,h,oldw,oldh);
        }
        Rect crop(){return crop==null?null:new Rect(crop);}
        List<Rect> masks(){List<Rect> copy=new ArrayList<>();for(Rect m:masks)copy.add(new Rect(m));return copy;}
        private float scale(){return Math.min(getWidth()/(float)preview.getWidth(),getHeight()/(float)preview.getHeight());}
        private float offsetX(){return (getWidth()-preview.getWidth()*scale())/2f;}
        private float offsetY(){return (getHeight()-preview.getHeight()*scale())/2f;}
        private float sourceX(float x){float p=Math.max(0,Math.min(preview.getWidth(),(x-offsetX())/scale()));return p*srcW/preview.getWidth();}
        private float sourceY(float y){float p=Math.max(0,Math.min(preview.getHeight(),(y-offsetY())/scale()));return p*srcH/preview.getHeight();}
        private RectF viewRect(Rect area){
            float s=scale();
            return new RectF(offsetX()+area.left*preview.getWidth()/(float)srcW*s,offsetY()+area.top*preview.getHeight()/(float)srcH*s,
                offsetX()+area.right*preview.getWidth()/(float)srcW*s,offsetY()+area.bottom*preview.getHeight()/(float)srcH*s);
        }
        @Override public boolean onTouchEvent(MotionEvent event){
            if(locked){cancelDrag();return true;}
            // A selection is one pointer stream, never a scroll or a pinch.
            // Cancellation keeps the last committed crop/masks, not the draft.
            if(event.getPointerCount()!=1){cancelDrag();return true;}
            switch(event.getActionMasked()){
                case MotionEvent.ACTION_DOWN:
                    if(getWidth()<=0||getHeight()<=0)return false;
                    // Drawing-only: avoid frame-batched/resampled input for pixel
                    // selection. This request ends with the platform touch stream.
                    requestUnbufferedDispatch(event);parentGesture(true);
                    downX=event.getX();downY=event.getY();moveX=downX;moveY=downY;dragging=true;invalidate();return true;
                case MotionEvent.ACTION_CANCEL:
                case MotionEvent.ACTION_POINTER_DOWN:
                case MotionEvent.ACTION_POINTER_UP:
                    cancelDrag();return true;
                case MotionEvent.ACTION_MOVE:
                    if(dragging){moveX=event.getX();moveY=event.getY();invalidate();}
                    return true;
                case MotionEvent.ACTION_UP:
                    if(!dragging)return true;dragging=false;parentGesture(false);
                    int l=Math.round(Math.min(sourceX(downX),sourceX(event.getX())));
                    int t=Math.round(Math.min(sourceY(downY),sourceY(event.getY())));
                    int r=Math.round(Math.max(sourceX(downX),sourceX(event.getX())));
                    int b=Math.round(Math.max(sourceY(downY),sourceY(event.getY())));
                    Rect area=new Rect(l,t,r,b);
                    if(area.width()>=2&&area.height()>=2){
                        if(redact)masks.add(area);else crop=area;
                        report();
                    }
                    invalidate();return true;
            }
            return true;
        }
        private void report(){
            if(cropReport!=null)cropReport.setText(crop==null?"未选择裁剪区域":"裁剪 "+crop.left+","+crop.top+" → "+crop.right+","+crop.bottom);
            if(maskReport!=null){
                StringBuilder text=new StringBuilder("遮挡 ").append(masks.size()).append(" 处");
                for(Rect m:masks)text.append("：").append(m.left).append(",").append(m.top).append(" → ").append(m.right).append(",").append(m.bottom);
                maskReport.setText(text);
            }
        }
        @Override protected void onDraw(Canvas canvas){
            canvas.drawColor(0xff203d35);
            float s=scale(),ox=offsetX(),oy=offsetY(),dw=preview.getWidth()*s,dh=preview.getHeight()*s;
            canvas.drawBitmap(preview,null,new RectF(ox,oy,ox+dw,oy+dh),null);
            if(crop!=null){
                RectF area=viewRect(crop);
                canvas.drawRect(ox,oy,ox+dw,area.top,dim);
                canvas.drawRect(ox,area.bottom,ox+dw,oy+dh,dim);
                canvas.drawRect(ox,area.top,area.left,area.bottom,dim);
                canvas.drawRect(area.right,area.top,ox+dw,area.bottom,dim);
                canvas.drawRect(area,frame);
            }
            for(Rect m:masks){RectF area=viewRect(m);canvas.drawRect(area,mark);canvas.drawRect(area,frame);}
            if(dragging)canvas.drawRect(Math.min(downX,moveX),Math.min(downY,moveY),Math.max(downX,moveX),Math.max(downY,moveY),frame);
        }
    }
    /** Touch selection feeding the accepted guarded backend. Original bytes, caption,
     * privacy and siblings stay untouched; abandoned previews never write. */
    private void deriveImage(State s,NoteDocument.Block block){
        final android.graphics.Bitmap shown=s.previews.get(block.id);
        if(shown==null){host.message("图片副本不可用，无法裁剪",true);return;}
        host.work(()->{
            android.graphics.BitmapFactory.Options size=bounds(s.media.path(block.assetId));
            return new int[]{size.outWidth,size.outHeight};
        },size->showDerive(s,block,shown,size[0],size[1]),null);
    }
    private void showDerive(State s,NoteDocument.Block block,android.graphics.Bitmap shown,int srcW,int srcH){
        LinearLayout body=host.column();body.setPadding(host.dp(12),host.dp(4),host.dp(12),host.dp(4));
        final SelectionView view=new SelectionView(host.activity,shown,srcW,srcH);
        view.setContentDescription("derive-canvas");body.addView(view,new LinearLayout.LayoutParams(-1,host.dp(240)));
        TextView source=host.text("原图 "+srcW+" × "+srcH+" · 预览 "+shown.getWidth()+" × "+shown.getHeight(),14,TodayScreen.MUTED);source.setContentDescription("derive-source");body.addView(source);
        TextView crop=host.text("未选择裁剪区域",14,TodayScreen.INK);crop.setContentDescription("derive-crop");body.addView(crop);
        TextView masks=host.text("遮挡 0 处",14,TodayScreen.MUTED);masks.setContentDescription("derive-masks");body.addView(masks);
        view.attach(crop,masks);
        LinearLayout modes=new LinearLayout(host.activity);
        modes.addView(host.button("裁剪模式",()->view.setRedact(false)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        modes.addView(host.button("遮挡模式",()->view.setRedact(true)),new LinearLayout.LayoutParams(0,host.dp(48),1));
        body.addView(modes);
        body.addView(host.button("重置选区",view::reset),new LinearLayout.LayoutParams(-1,host.dp(48)));
        TextView output=host.text("",14,TodayScreen.INK);output.setContentDescription("derive-output");body.addView(output);
        TextView validation=host.text("拖拽选择裁剪区域；遮挡模式可叠加多处。保存生成新图，原图保留。",14,TodayScreen.MUTED);body.addView(validation);
        ScrollView scroll=new ScrollView(host.activity);scroll.addView(body);
        final AlertDialog dialog=new AlertDialog.Builder(host.activity).setTitle("裁剪 / 遮挡").setView(scroll).setNegativeButton("取消",null).setPositiveButton("预览",null).create();
        final Session session=new Session();
        dialog.setOnDismissListener(unused->session.close());
        dialog.setOnShowListener(unused->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            if(session.preview!=null){
                dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);
                host.work(()->{session.editor.confirm(session.preview);return true;},ignored->{dialog.dismiss();load();},()->dialog.dismiss());
                return;
            }
            Rect area=view.crop();
            List<Rect> drawn=view.masks();
            if(area==null&&drawn.isEmpty()){validation.setText("尚未选择：请拖出裁剪区域，或在遮挡模式涂抹");validation.setTextColor(TodayScreen.ERROR);return;}
            if(area==null)area=new Rect(0,0,srcW,srcH);
            if((long)area.width()*area.height()>1000000L){validation.setText("选区过大：派生图最多 100 万像素");validation.setTextColor(TodayScreen.ERROR);return;}
            if(area.width()<2||area.height()<2){validation.setText("选区过小");validation.setTextColor(TodayScreen.ERROR);return;}
            if(area.equals(new Rect(0,0,srcW,srcH))&&drawn.isEmpty()){validation.setText("未做任何修改");validation.setTextColor(TodayScreen.ERROR);return;}
            ArrayList<int[]> translated=new ArrayList<>();
            for(Rect m:drawn){
                int l=Math.max(m.left,area.left),t=Math.max(m.top,area.top),r=Math.min(m.right,area.right),b=Math.min(m.bottom,area.bottom);
                if(l<r&&t<b)translated.add(new int[]{l-area.left,t-area.top,r-area.left,b-area.top});
            }
            final Rect target=area;
            final int[][] maskArray=translated.toArray(new int[0][]);
            dialog.setCancelable(false);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(false);view.setLocked(true);
            host.work(()->{
                session.editor=new Editor(host.db,s.media);
                session.preview=session.editor.prepare(s.noteId,block.id,target.left,target.top,target.right,target.bottom,maskArray);
                byte[] png=session.preview.png();
                android.graphics.Bitmap decoded=android.graphics.BitmapFactory.decodeByteArray(png,0,png.length);
                if(decoded==null)throw new IOException("派生预览解码失败");
                return decoded;
            },decoded->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);
                output.setText("派生预览 "+decoded.getWidth()+" × "+decoded.getHeight());
                ImageView image=new ImageView(host.activity);
                image.setImageBitmap(decoded);image.setAdjustViewBounds(true);image.setMaxHeight(host.dp(160));image.setContentDescription("derive-result");
                body.addView(image,0,new LinearLayout.LayoutParams(-1,-2));
                Button positive=dialog.getButton(AlertDialog.BUTTON_POSITIVE);positive.setText("保存");positive.setEnabled(true);
            },()->{
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);view.setLocked(false);
                session.close();
                validation.setText("预览失败：原图可能已变化，请重新选择");validation.setTextColor(TodayScreen.ERROR);
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
        AlertDialog pick=new AlertDialog.Builder(host.activity).setTitle("加入图片").setMessage("选择 PNG/JPEG，最大 8 MiB、2000 万像素、单边 16384。保留本机原图副本及元数据，完整备份也会包含；尚不支持相机、旋转校正或分享。")
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
