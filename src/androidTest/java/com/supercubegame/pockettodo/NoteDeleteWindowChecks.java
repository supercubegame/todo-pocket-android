package com.supercubegame.pockettodo;

import android.app.Instrumentation;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.graphics.Rect;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.TextView;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.Collections;
import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;

/** API-26 supplemental native NoteDeleteSurface check; not external UI acceptance. */
public final class NoteDeleteWindowChecks {
    private static final String DB=MainActivity.NOTE_DELETE_DB, MEDIA=MainActivity.NOTE_DELETE_MEDIA;
    private static final long OWNER=11L;
    private static final String A="note-a", B="note-b", TITLE="同名笔记";
    private static final String ACTIVITY="删除测试活动", CATEGORY="删除测试", FIELD="delete-field";
    private static final String CONSENT="我明白只删除这一篇，且无法撤销", DELETE="确认删除";
    private final Instrumentation ins; private final Bundle args; private final StringBuilder log; private final Context c;
    private final long deadline=SystemClock.uptimeMillis()+75000L;
    private MainActivity activity; private byte[] image; private String imageId; private Snapshot before;
    private NoteDeleteWindowChecks(Instrumentation i,Bundle a,StringBuilder l){ins=i;args=a==null?new Bundle():a;log=l;c=i.getTargetContext();}
    public static void run(Instrumentation i,Bundle a,StringBuilder l)throws Exception{new NoteDeleteWindowChecks(i,a,l).verify();}
    private static void need(boolean ok,String s){if(!ok)throw new AssertionError("note-delete-window: "+s);}
    private void pass(String s){log.append("WINDOW_DELETE_CASE ").append(s).append(" PASS\n");}
    private void verify()throws Exception{
        String nonce=args.getString("nonce","");need(Build.VERSION.SDK_INT==26&&"26".equals(args.getString("expectedApi")),"API 26 only");need(nonce.matches("[0-9]{1,20}-[1-9][0-9]{0,3}-26"),"nonce format");
        need(!MainActivity.isolatedNoteDeleteTest&&!MainActivity.isolatedRestoreUndoTest&&!MainActivity.isolatedScheduleBookTest&&!MainActivity.isolatedShortcutTest&&!MainActivity.isolatedNoteThumbnailTest&&MainActivity.isolatedDraftFontScale==0&&!MainActivity.isolatedCategoryImpactTest&&!MainActivity.isolatedActivitySearchTest&&!MainActivity.isolatedActivityTemplateTest&&!MainActivity.isolatedStartupTest&&!MainActivity.isolatedActivationTest,"overlapping test hook");
        need("com.supercubegame.pockettodo.v12.preview".equals(c.getPackageName()),"preview package");need("ranchu".equals(Build.HARDWARE),"ranchu emulator");
        log.append("NOTE_DELETE_WINDOW_SCOPE api=26 nonce=").append(nonce).append(" package=").append(c.getPackageName()).append(" hardware=").append(Build.HARDWARE).append('\n');
        reserve(); seed(); verifySeed(); negativeChecks(); before=readSnapshot();
        try{
            launchHome(); requireButton(A); openDelete(A); requireIdentity(A); requireConsentUnchecked(); clickText(DELETE); requireText("请先勾选删除确认"); need(before.equals(readSnapshot()),"unchecked changed DB");verifyImage(); pass("unchecked_confirm_readonly");
            checkOnce(); dispatchBack(); waitReviewGoneAndButton(A,false); need(before.equals(readSnapshot()),"Back changed DB");verifyImage(); pass("checked_back_readonly");
            openDelete(A);requireConsentUnchecked();checkOnce();clickText(DELETE);waitReviewGoneAndButton(B,true); verifyExpectedDelete(); pass("exact_identity_single_delete_shared_media");
            reopenAfterClose();waitReviewGoneAndButton(B,true);verifyExpectedDelete(); pass("reopen_readonly_exact_state");
        } finally { try{closeActivityAndWorkers();} finally {MainActivity.isolatedNoteDeleteTest=false;} }
    }
    private void reserve()throws Exception{
        Path p=c.getDatabasePath(DB).toPath();need(!Files.exists(p,LinkOption.NOFOLLOW_LINKS),"existing DB refused");
        for(String x:new String[]{"-wal","-shm","-journal"})need(!Files.exists(c.getDatabasePath(DB+x).toPath(),LinkOption.NOFOLLOW_LINKS),"existing sidecar refused");
        Path parent=p.getParent();need(parent!=null,"database parent");Files.createDirectories(parent);
        try(java.nio.file.DirectoryStream<Path> ds=Files.newDirectoryStream(parent,DB+"-*")){need(!ds.iterator().hasNext(),"same-prefix database artifact refused");}
        Path m=c.getFilesDir().toPath().resolve(MEDIA);need(!Files.exists(m,LinkOption.NOFOLLOW_LINKS),"existing media refused");
        Files.createFile(p);Files.createDirectory(m);
    }
    private void seed()throws Exception{
        Path root=c.getFilesDir().toPath().resolve(MEDIA).resolve("assets");MediaRepository repo=new MediaRepository(root,1048576L);
        image=java.util.Base64.getDecoder().decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aCmsAAAAASUVORK5CYII=");imageId=repo.copy(new ByteArrayInputStream(image));
        try(AppDatabase d=AppDatabase.openSchema3(c,DB)){
            d.addCategory(1,CATEGORY);d.addActivity(OWNER,1,0,ACTIVITY);d.defineField(FIELD,"删除字段","TEXT",java.util.Collections.emptyList());d.putField(OWNER,FIELD,java.util.Collections.singletonList("history"));d.registerMedia(imageId,"image/png",image.length);
            d.createFieldNote(A,OWNER,FIELD,TITLE);d.saveNote(A,java.util.Arrays.asList(NoteDocument.Block.text("a-text","private-a",true),NoteDocument.Block.image("a-image",imageId,"original",false)));
            d.createFieldNote(B,OWNER,FIELD,TITLE);d.saveNote(B,java.util.Arrays.asList(NoteDocument.Block.text("b-text","private-b",true),NoteDocument.Block.image("b-image",imageId,"original",false)));
            d.addTodo("extra-row","额外行");
        }
    }
    private void launchHome()throws Exception{MainActivity.isolatedNoteDeleteTest=true;activity=(MainActivity)ins.startActivitySync(new Intent(c,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));waitKey("v12-home");clickKey("activity-"+OWNER);}
    private void openDelete(String id)throws Exception{clickKey("note-delete-"+id);requireIdentity(id);requireText("确认删除笔记？");requireText("将删除 2 个正文块、1 个字段笔记关联。\n字段和值、其他笔记和图片文件均保留。");}
    private void checkOnce()throws Exception{requireConsentUnchecked();clickText(CONSENT);waitFor("consent set",()->{View v=findText(CONSENT);return v instanceof CheckBox&&((CheckBox)v).isChecked()?Boolean.TRUE:null;});}
    private void requireIdentity(String id)throws Exception{waitFor("identity",()->ui(()->{List<View> a=new ArrayList<>();collectText(activity.getWindow().getDecorView(),"活动："+ACTIVITY+"\n笔记："+TITLE+"\n笔记标识："+id,TextView.class,a);return a.size()==1?Boolean.TRUE:null;}));}
    private void requireConsentUnchecked()throws Exception{waitFor("unchecked consent",()->ui(()->{List<View>a=new ArrayList<>();collectText(activity.getWindow().getDecorView(),CONSENT,CheckBox.class,a);need(a.size()<=1,"ambiguous consent");return a.size()==1&&!((CheckBox)a.get(0)).isChecked()?Boolean.TRUE:null;}));}
    private void clickKey(String key)throws Exception{click("key "+key,()->findKey(key));}
    private void clickText(String text)throws Exception{click("text "+text,()->findText(text));}
    private boolean own(View v){if(activity==null||activity.isFinishing()||activity.isDestroyed()||v==null)return false;View root=activity.getWindow().getDecorView();return root.hasWindowFocus()&&root.isAttachedToWindow()&&root.getWindowToken()!=null&&v.getRootView()==root&&v.getWindowToken()==root.getWindowToken()&&v.isAttachedToWindow()&&v.isShown()&&v.isEnabled();}
    private void click(String label,Callable<View> finder)throws Exception{final View[] bound={null};final boolean[] scrolled={false};waitFor(label,()->{View v=finder.call();if(v==null)return null;if(bound[0]!=null)need(v==bound[0],"control replaced "+label);if(!own(v)||v.getWidth()<=0||v.getHeight()<=0)return null;bound[0]=v;need(v instanceof Button&&v.isClickable(),"not an owned button: "+label);Rect rect=new Rect();if(!v.getLocalVisibleRect(rect)||rect.left!=0||rect.top!=0||rect.right!=v.getWidth()||rect.bottom!=v.getHeight()){if(!scrolled[0]){scrolled[0]=true;v.requestRectangleOnScreen(new Rect(0,0,v.getWidth(),v.getHeight()),true);}return null;}need(finder.call()==v&&own(v)&&v.performClick(),"owned single view callback refused: "+label);return Boolean.TRUE;});ins.waitForIdleSync();}
    private void dispatchBack()throws Exception{runUi(()->{View v=findText(CONSENT);need(v instanceof CheckBox&&((CheckBox)v).isChecked()&&own(v)&&findExactText("确认删除笔记？")!=null,"not checked own review");activity.onBackPressed();return null;});ins.waitForIdleSync();}
    private void waitReviewGoneAndButton(String id,boolean deleted)throws Exception{waitFor("review closed and expected note",()->{if(findExactText("确认删除")!=null||findExactText("确认删除笔记？")!=null||findExactText(CONSENT)!=null)return null;View v=findKey("note-delete-"+id);return own(v)&&(!deleted||findKey("note-delete-"+A)==null)?Boolean.TRUE:null;});}
    private void requireButton(String id)throws Exception{waitKey("note-delete-"+id);}
    private void waitKey(String key)throws Exception{waitFor("key "+key,()->ui(()->findKey(key)!=null?Boolean.TRUE:null));}
    private void waitPresentText(String s)throws Exception{waitFor("text "+s,()->ui(()->findExactText(s)!=null?Boolean.TRUE:null));}
    private void requireText(String s)throws Exception{waitPresentText(s);}
    private void reopenAfterClose()throws Exception{closeActivityAndWorkers();launchHome();requireButton(B);}
    private void closeActivityAndWorkers()throws Exception{if(activity==null)return;TodayScreen screen=runUi(()->activity.shortcutTestScreen());if(!activity.isFinishing()&&!activity.isDestroyed())runUi(()->{activity.finish();return null;});ins.waitForIdleSync();need(screen!=null&&screen.awaitShortcutClose(),"screen worker did not close");activity=null;}
    private void verifyImage()throws Exception{Path dir=c.getFilesDir().toPath().resolve(MEDIA).resolve("assets"),file=dir.resolve(imageId);need(Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS)&&Arrays.equals(image,Files.readAllBytes(file)),"physical PNG changed");try(java.nio.file.DirectoryStream<Path> ds=Files.newDirectoryStream(dir)){int n=0;for(Path x:ds){n++;need(imageId.equals(x.getFileName().toString()),"unexpected media filename");}need(n==1,"shared media file set changed");}}
    private void verifySeed()throws Exception{verifyImage();try(SQLiteDatabase d=SQLiteDatabase.openDatabase(c.getDatabasePath(DB).getPath(),null,SQLiteDatabase.OPEN_READONLY)){need(count(d,"PRAGMA user_version")==3&&count(d,"SELECT count(*) FROM notes")==2&&count(d,"SELECT count(*) FROM todos WHERE id=?","extra-row")==1&&count(d,"SELECT count(*) FROM media WHERE id=? AND bytes=?",imageId,Integer.toString(image.length))==1,"invalid named fixture");for(String id:new String[]{A,B})need(count(d,"SELECT count(*) FROM notes WHERE activity_id=11 AND id=? AND title=?",id,TITLE)==1&&count(d,"SELECT count(*) FROM blocks WHERE note_id=?",id)==2&&count(d,"SELECT count(*) FROM blocks WHERE note_id=? AND asset_id=?",id,imageId)==1&&count(d,"SELECT count(*) FROM field_notes WHERE field_id=? AND note_id=?",FIELD,id)==1,"invalid note identity/association");}}
    private void negativeChecks()throws Exception{
        Snapshot s=readSnapshot(); boolean refused=false;
        try(AppDatabase d=AppDatabase.openSchema3(c,DB)){try{d.prepareNoteDeletion("missing-note",OWNER);}catch(IllegalArgumentException|IllegalStateException e){refused=true;}need(refused,"missing target was not refused");refused=false;try{d.registerMedia("not-a-sha256-id","image/jpeg",1);}catch(IllegalArgumentException|IllegalStateException e){refused=true;}need(refused,"wrong media identity was not refused");}
        need(s.equals(readSnapshot()),"negative target/media changed state");verifyImage();pass("wrong_target_and_media_refused");
    }
    private Snapshot readSnapshot()throws Exception{Snapshot a=readOnce(),b=readOnce();need(a.equals(b),"independent snapshot changed during read");return b;}
    private Snapshot readOnce()throws Exception{
        Snapshot all=new Snapshot();Path p=c.getDatabasePath(DB).toPath();need(Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS),"named database missing");try(SQLiteDatabase d=SQLiteDatabase.openDatabase(p.toString(),null,SQLiteDatabase.OPEN_READONLY);Cursor t=d.rawQuery("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",null)){try(Cursor k=d.rawQuery("PRAGMA quick_check",null);Cursor f=d.rawQuery("PRAGMA foreign_key_check",null)){need(k.moveToFirst()&&"ok".equals(k.getString(0))&&!k.moveToNext()&&!f.moveToFirst(),"isolated SQLite integrity");}while(t.moveToNext()){String n=t.getString(0);Table z=new Table(n,t.getString(1));try(Cursor r=d.rawQuery("SELECT rowid,* FROM \""+n.replace("\"","\"\"")+"\" ORDER BY rowid",null)){for(int i=0;i<r.getColumnCount();i++)z.columns.add(r.getColumnName(i));while(r.moveToNext())z.rows.add(row(r));}all.tables.put(n,z);}}need(all.tables.keySet().containsAll(Arrays.asList("notes","blocks","field_notes","fields","todos","activities","media","revision")),"incomplete schema");return all;}
    private Row row(Cursor r){Row q=new Row();for(int i=0;i<r.getColumnCount();i++){int t=r.getType(i);StringBuilder b=new StringBuilder().append(t).append(':');switch(t){case Cursor.FIELD_TYPE_NULL:break;case Cursor.FIELD_TYPE_INTEGER:b.append(r.getLong(i));break;case Cursor.FIELD_TYPE_FLOAT:b.append(Double.toString(r.getDouble(i)));break;case Cursor.FIELD_TYPE_STRING:b.append(java.util.Base64.getEncoder().encodeToString(r.getString(i).getBytes(StandardCharsets.UTF_8)));break;case Cursor.FIELD_TYPE_BLOB:b.append(java.util.Base64.getEncoder().encodeToString(r.getBlob(i)));break;default:throw new AssertionError("unknown cursor type");}q.values.add(b.toString());}return q;}
    private void verifyExpectedDelete()throws Exception{
        Snapshot after=readSnapshot(); Snapshot expected=before.copy();
        for(String table:new String[]{"notes","blocks","field_notes"}){Table z=expected.tables.get(table);need(z!=null,"required table missing "+table);int col=z.columns.indexOf(table.equals("notes")?"id":"note_id");need(col>=0,"required identity column missing "+table);String needle=typedStringColumn(z,col,A);int initial=z.rows.size();z.rows.removeIf(x->x.values.get(col).equals(needle));need(initial-z.rows.size()==(table.equals("blocks")?2:1),"wrong expected removed rows "+table);}
        Table rev=expected.tables.get("revision");need(rev!=null,"revision table missing");int value=rev.columns.indexOf("value");need(value>=0&&rev.rows.size()==1,"revision value missing");rev.rows.set(0,incrementCell(rev.rows.get(0),value));
        need(expected.equals(after),"post-delete business tables differ beyond target rows/revision");
        verifyImage();
        try(SQLiteDatabase d=SQLiteDatabase.openDatabase(c.getDatabasePath(DB).toString(),null,SQLiteDatabase.OPEN_READONLY)){need(count(d,"SELECT count(*) FROM notes WHERE id=?",A)==0,"target note remains");need(count(d,"SELECT count(*) FROM notes WHERE id=? AND title=?",B,TITLE)==1,"sibling missing");need(count(d,"SELECT count(*) FROM blocks WHERE note_id=?",B)==2,"sibling blocks changed");need(count(d,"SELECT count(*) FROM field_notes WHERE note_id=?",B)==1,"sibling relation changed");need(count(d,"SELECT count(*) FROM media WHERE id=? AND mime='image/png' AND bytes=?",imageId,Integer.toString(image.length))==1,"shared media registry changed");}
    }
    private String typedStringColumn(Table z,int col,String s){return "3:"+java.util.Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8));}
    private Row incrementCell(Row r,int value){Row out=new Row();out.values.addAll(r.values);String x=out.values.get(value);need(x.startsWith("1:"),"revision value is not integer");long v=Long.parseLong(x.substring(2));out.values.set(value,"1:"+Math.incrementExact(v));return out;}
    private static final class Row{final List<String> values=new ArrayList<>();}
    private static final class Table{final String name,sql;final List<String> columns=new ArrayList<>();final List<Row> rows=new ArrayList<>();Table(String n,String s){name=n;sql=s;}}
    private static final class Snapshot{final Map<String,Table> tables=new LinkedHashMap<>();Snapshot copy(){Snapshot n=new Snapshot();for(Map.Entry<String,Table>e:tables.entrySet()){Table q=new Table(e.getValue().name,e.getValue().sql);q.columns.addAll(e.getValue().columns);for(Row r:e.getValue().rows){Row x=new Row();x.values.addAll(r.values);q.rows.add(x);}n.tables.put(e.getKey(),q);}return n;}public boolean equals(Object o){if(!(o instanceof Snapshot))return false;Snapshot n=(Snapshot)o;if(!tables.keySet().equals(n.tables.keySet()))return false;for(String k:tables.keySet()){Table a=tables.get(k),b=n.tables.get(k);if(!a.sql.equals(b.sql)||!a.columns.equals(b.columns)||a.rows.size()!=b.rows.size())return false;for(int i=0;i<a.rows.size();i++)if(!a.rows.get(i).values.equals(b.rows.get(i).values))return false;}return true;}}
    private long count(SQLiteDatabase d,String q,String...a)throws Exception{try(Cursor x=d.rawQuery(q,a)){need(x.moveToFirst(),"scalar missing");return x.getLong(0);}}
    private View findKey(String k){if(activity==null||activity.isDestroyed()||activity.isFinishing())return null;List<View>a=new ArrayList<>();collectKey(activity.getWindow().getDecorView(),k,a);need(a.size()<=1,"ambiguous key "+k);return a.isEmpty()?null:a.get(0);}
    private View findText(String s){List<View>a=new ArrayList<>();collectText(activity.getWindow().getDecorView(),s,TextView.class,a);need(a.size()<=1,"ambiguous text "+s);return a.isEmpty()?null:a.get(0);}
    private View findExactText(String s){return findText(s);}
    private static void collectKey(View v,String k,List<View>o){if(v.isAttachedToWindow()&&v.isShown()&&v.isEnabled()&&(k.equals(v.getTag())||k.equals(String.valueOf(v.getContentDescription()))))o.add(v);if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++)collectKey(g.getChildAt(i),k,o);}}
    private static void collectText(View v,String s,Class<? extends View> type,List<View>o){if(type.isInstance(v)&&v.isAttachedToWindow()&&v.isShown()&&s.contentEquals(String.valueOf(((TextView)v).getText())))o.add(v);if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++)collectText(g.getChildAt(i),s,type,o);}}
    private <T>T runUi(Callable<T> x)throws Exception{FutureTask<T> f=new FutureTask<>(x);ins.runOnMainSync(f);return f.get();}
    private <T>T ui(Callable<T>x)throws Exception{return x.call();}
    private <T>T waitFor(String what,Callable<T>x)throws Exception{long end=Math.min(deadline,SystemClock.uptimeMillis()+12000);while(SystemClock.uptimeMillis()<end){T v=runUi(x);if(v!=null)return v;SystemClock.sleep(25);}throw new AssertionError("note-delete-window: not observed "+what);}
}
