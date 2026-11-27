package com.supercubegame.pockettodo;

import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import java.io.*;
import java.math.BigInteger;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.util.*;

/** Amendments to one imported private book. Original batches and ledger rows stay immutable.
 * PTDB wire 5 / database 6 embeds a complete canonical v5 state followed by ordered events. */
final class LedgerChanges {
    static final int LIMIT=ActivitySchedule.Wire.LIMIT, MAX_EVENTS=8192, MAX_TEXT=32768;
    static final String DDL="CREATE TABLE ledger_changes(seq INTEGER PRIMARY KEY CHECK(seq>0),token TEXT NOT NULL UNIQUE,target TEXT NOT NULL REFERENCES ledger(id),owner INTEGER NOT NULL REFERENCES activities(id),payload BLOB NOT NULL)";
    enum Op { EDIT, VOID, UNDO }
    static void need(boolean b,String m){if(!b)throw new IllegalArgumentException(m);}
    static LocalDate day(String s){LocalDate d=Ledger.validDate(LocalDate.parse(s));need(d.toString().equals(s),"日期无效");return d;}
    static String token(String s){need(s!=null&&UUID.fromString(s).toString().equals(s),"操作编号无效");return s;}
    static void string(DataOutputStream d,String s)throws IOException{byte[] b=s.getBytes(StandardCharsets.UTF_8);need(b.length<=MAX_TEXT&&s.equals(new String(b,StandardCharsets.UTF_8)),"文字超出范围");d.writeInt(b.length);d.write(b);}
    static String string(DataInputStream d)throws IOException{int n=d.readInt();need(n>=0&&n<=MAX_TEXT&&n<=d.available(),"文字长度无效");byte[] b=new byte[n];d.readFully(b);String s=new String(b,StandardCharsets.UTF_8);need(Arrays.equals(b,s.getBytes(StandardCharsets.UTF_8)),"文字编码无效");return s;}
    static void value(DataOutputStream o,Ledger.Entry e)throws IOException{o.writeByte(e==null?0:1);if(e!=null){string(o,e.date.toString());string(o,e.kind.name());o.writeLong(e.cents);string(o,e.memo);}}
    static Ledger.Entry value(DataInputStream i,String target,long owner)throws IOException{int t=i.readUnsignedByte();need(t==0||t==1,"账目存在标记无效");return t==0?null:new Ledger.Entry(target,owner,day(string(i)),Ledger.Kind.valueOf(string(i)),i.readLong(),string(i));}
    static final class Event {
        final String id,target,ref;final long owner;final Op op;final Ledger.Entry before,after;
        Event(String id,String target,long owner,Op op,String ref,Ledger.Entry before,Ledger.Entry after){this.id=token(id);this.target=Ledger.identifier(target);this.owner=Ledger.positive(owner);this.op=Objects.requireNonNull(op);this.ref=op==Op.UNDO?token(ref):ref;need((op==Op.UNDO)==(ref!=null),"操作引用无效");this.before=before;this.after=after;for(Ledger.Entry e:new Ledger.Entry[]{before,after})if(e!=null)need(e.id.equals(target)&&e.activityId==owner,"操作不能改变账目归属");}
        byte[] bytes(){try{ByteArrayOutputStream b=new ByteArrayOutputStream();DataOutputStream o=new DataOutputStream(b);string(o,id);string(o,target);o.writeLong(owner);string(o,op.name());string(o,ref==null?"":ref);value(o,before);value(o,after);o.flush();return b.toByteArray();}catch(IOException e){throw new IllegalStateException(e);}}
        static Event read(byte[] b){need(b!=null&&b.length>0&&b.length<=4*MAX_TEXT+512,"变更记录过大或为空");try{DataInputStream i=new DataInputStream(new ByteArrayInputStream(b));String id=string(i),target=string(i);long owner=i.readLong();Op op=Op.valueOf(string(i));String ref=string(i);Event e=new Event(id,target,owner,op,ref.isEmpty()?null:ref,value(i,target,owner),value(i,target,owner));need(i.available()==0&&Arrays.equals(e.bytes(),b),"变更记录不是标准格式");return e;}catch(IOException e){throw new IllegalArgumentException("变更记录不完整",e);}}
    }
    static final class Row {final Ledger.Entry original,current,display;final Event last;Row(Ledger.Entry o,Ledger.Entry e,Ledger.Entry display,Event last){original=o;current=e;this.display=display;this.last=last;}
        boolean same(Row r){return r!=null&&original.equals(r.original)&&Objects.equals(current,r.current)&&Objects.equals(last==null?null:last.id,r.last==null?null:r.last.id);}
        boolean canUndo(){return last!=null&&last.op!=Op.UNDO;}}
    static final class Trace {
        final LinkedHashMap<String,Row> rows=new LinkedHashMap<>();final ArrayList<Event> events=new ArrayList<>();final HashSet<String> tokens=new HashSet<>();
        Trace(Collection<Ledger.Entry> bases){for(Ledger.Entry e:bases)need(rows.put(e.id,new Row(e,e,e,null))==null,"原始账目编号重复");}
        void apply(Event e){Row r=rows.get(e.target);need(r!=null&&r.original.activityId==e.owner&&Objects.equals(r.current,e.before),"原始账目或前值不匹配");need(events.size()<MAX_EVENTS&&!tokens.contains(e.id),"操作过多或编号重复");
            switch(e.op){case EDIT:need(r.current!=null&&e.after!=null&&!r.current.equals(e.after),"更正没有变化或账目已删除");break;case VOID:need(r.current!=null&&e.after==null,"账目已删除");break;case UNDO:need(r.canUndo()&&r.last.id.equals(e.ref)&&Objects.equals(e.after,r.last.before),"只能撤销本笔最近一次尚未撤销的变更");break;default:throw new AssertionError();}
            tokens.add(e.id);events.add(e);rows.put(e.target,new Row(r.original,e.after,e.after==null?r.display:e.after,e));}
    }
    static Trace load(SQLiteDatabase d){ArrayList<Ledger.Entry> base=new ArrayList<>();try(Cursor c=d.rawQuery("SELECT id,activity_id,day,kind,cents,memo FROM ledger ORDER BY rowid",null)){while(c.moveToNext())base.add(new Ledger.Entry(c.getString(0),c.getLong(1),day(c.getString(2)),Ledger.Kind.valueOf(c.getString(3)),c.getLong(4),c.getString(5)));}Trace t=new Trace(base);
        if(d.getVersion()==6){try(Cursor c=d.rawQuery("SELECT seq,token,target,owner,payload FROM ledger_changes ORDER BY seq",null)){while(c.moveToNext()){need(c.getType(0)==Cursor.FIELD_TYPE_INTEGER&&c.getLong(0)==1L+t.events.size()&&c.getType(1)==Cursor.FIELD_TYPE_STRING&&c.getType(2)==Cursor.FIELD_TYPE_STRING&&c.getType(3)==Cursor.FIELD_TYPE_INTEGER&&c.getType(4)==Cursor.FIELD_TYPE_BLOB,"账目变更索引异常");Event e=Event.read(c.getBlob(4));need(e.id.equals(c.getString(1))&&e.target.equals(c.getString(2))&&e.owner==c.getLong(3),"账目变更关联异常");t.apply(e);}}need(!t.events.isEmpty(),"缺少变更历史");}else need(d.getVersion()==5,"日程簿版本无效");return t;}
    static void insert(SQLiteDatabase d,int seq,Event e){d.execSQL("INSERT INTO ledger_changes(seq,token,target,owner,payload) VALUES(?,?,?,?,?)",new Object[]{seq,e.id,e.target,e.owner,e.bytes()});}
    static final class Envelope {final byte[] base;final List<Event> events;Envelope(byte[] b,List<Event> e){base=b;events=e;}}
    static boolean v6(byte[] b){return b!=null&&b.length>=12&&ByteBuffer.wrap(b).getInt()==ActivitySchedule.Wire.MAGIC&&ByteBuffer.wrap(b).getInt(4)==5&&ByteBuffer.wrap(b).getInt(8)==6;}
    static byte[] pack(byte[] base,List<Event> items){ActivitySchedule.Wire.read(base);need(items!=null&&items.size()<=MAX_EVENTS,"变更条数无效");if(items.isEmpty())return base.clone();try{ByteArrayOutputStream b=new ByteArrayOutputStream();DataOutputStream o=new DataOutputStream(b);need(20L+base.length<=LIMIT,"备份超过上限");o.writeInt(ActivitySchedule.Wire.MAGIC);o.writeInt(5);o.writeInt(6);o.writeInt(base.length);o.write(base);o.writeInt(items.size());for(Event e:items){byte[] v=e.bytes();need(4L+v.length+b.size()<=LIMIT,"备份超过上限");o.writeInt(v.length);o.write(v);}o.flush();return b.toByteArray();}catch(IOException e){throw new IllegalStateException(e);}}
    static Envelope split(byte[] raw){need(raw!=null&&raw.length>=12&&raw.length<=LIMIT,"备份长度无效");if(!v6(raw)){ActivitySchedule.Wire.read(raw);return new Envelope(raw.clone(),Collections.emptyList());}
        try{DataInputStream i=new DataInputStream(new ByteArrayInputStream(raw));i.readInt();i.readInt();i.readInt();int n=i.readInt();need(n>0&&n<=i.available()-4,"内嵌日程簿长度无效");byte[] b=new byte[n];i.readFully(b);ActivitySchedule.Wire.read(b);int count=i.readInt();need(count>0&&count<=MAX_EVENTS&&count<=i.available()/8,"变更条数无效");ArrayList<Event> out=new ArrayList<>();HashSet<String> keys=new HashSet<>();for(int k=0;k<count;k++){int size=i.readInt();need(size>0&&size<=4*MAX_TEXT+512&&size<=i.available(),"变更段长度无效");byte[] v=new byte[size];i.readFully(v);Event e=Event.read(v);need(keys.add(e.id),"重复变更编号");out.add(e);}need(i.available()==0&&Arrays.equals(raw,pack(b,out)),"备份尾部或编码异常");return new Envelope(b,Collections.unmodifiableList(out));}catch(IOException e){throw new IllegalArgumentException("备份截断",e);}}
    static final class Page {
        final List<Row> rows;final BigInteger[] totals;final int records,actual,items,page;final boolean more;
        Page(Trace t,long owner,LocalDate day,int index){Ledger.positive(owner);need(index>=0,"页码无效");ArrayList<Row> all=new ArrayList<>();BigInteger[] sum={BigInteger.ZERO,BigInteger.ZERO,BigInteger.ZERO,BigInteger.ZERO};int rec=0,act=0;
            for(Row r:t.rows.values())if(r.original.activityId==owner&&(day==null||day.equals(r.display.date))){all.add(r);Ledger.Entry e=r.current;if(e!=null){rec++;if(e.kind!=Ledger.Kind.PLANNED)act++;int k=e.kind.ordinal();sum[k]=sum[k].add(BigInteger.valueOf(e.cents));}}all.sort((x,y)->{int v=y.display.date.compareTo(x.display.date);return v!=0?v:x.original.id.compareTo(y.original.id);});items=all.size();page=Math.min(index,Math.max(0,(items-1)/20));int from=page*20,to=Math.min(from+20,items);rows=Collections.unmodifiableList(new ArrayList<>(all.subList(from,to)));more=to<items;records=rec;actual=act;totals=new BigInteger[]{sum[0],sum[1],sum[2],sum[3],sum[0].subtract(sum[1]),sum[2].add(sum[1]).subtract(sum[0])};}
    }
    private LedgerChanges(){}
}
