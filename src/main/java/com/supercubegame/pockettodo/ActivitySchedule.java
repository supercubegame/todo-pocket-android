package com.supercubegame.pockettodo;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;

/** A planning rule, not a recorded check-in. No live clock, enumeration of unbounded dates,
 * reminders or accounting. ISO Monday is bit zero. The stored zone survives device changes. */
public final class ActivitySchedule {
    public static final int DAILY=127, WEEKDAYS=31;
    public final int days;
    public final LocalDate first,last; // inclusive; null last means no end
    public final ZoneId zone;
    private static final Set<String> ZONES=Collections.unmodifiableSet(new HashSet<>(ZoneId.getAvailableZoneIds()));
    private static void need(boolean b,String m){if(!b)throw new IllegalArgumentException(m);}
    public ActivitySchedule(int days,String first,String last,String zoneId){
        need(days>=1&&days<=127,"Choose at least one weekday");this.days=days;
        this.first=date(first);this.last=last==null?null:date(last);
        need(this.last==null||!this.last.isBefore(this.first),"End date before start");
        need(zoneId!=null && zoneId.length()<=128 && (zoneId.equals("UTC")||ZONES.contains(zoneId)),"Unknown region time zone");
        zone=ZoneId.of(zoneId);
    }
    static LocalDate date(String s){
        need(s!=null&&s.matches("[0-9]{4}-[0-9]{2}-[0-9]{2}"),"Canonical date required");
        try{LocalDate d=LocalDate.parse(s);need(d.getYear()>0&&d.toString().equals(s),"Canonical date required");return d;}
        catch(DateTimeException e){throw new IllegalArgumentException("Invalid local date",e);}
    }
    public boolean due(LocalDate d){Objects.requireNonNull(d);return !d.isBefore(first)&&(last==null||!d.isAfter(last)) && d.getYear()<=9999 && (days&(1<<(d.getDayOfWeek().getValue()-1)))!=0;}
    public LocalDate localDay(Instant now){return Objects.requireNonNull(now).atZone(zone).toLocalDate();}
    public boolean dueAt(Instant now){return due(localDay(now));}
    public LocalDate nextOnOrAfter(LocalDate day){Objects.requireNonNull(day);LocalDate d=day.isBefore(first)?first:day;
        for(int i=0;i<7;i++){if(d.getYear()>9999||last!=null&&d.isAfter(last))return null;if(due(d))return d;d=d.plusDays(1);}return null;}
    @Override public boolean equals(Object o){if(!(o instanceof ActivitySchedule))return false;ActivitySchedule s=(ActivitySchedule)o;return s.days==days&&s.first.equals(first)&&Objects.equals(last,s.last)&&s.zone.equals(zone);}
    @Override public int hashCode(){return Objects.hash(days,first,last,zone);}

    // PTDB wire4/schema5: immutable canonical schema4 bytes, then rules sorted by positive activity ID.
    // The Android data layer independently validates all nested rows, semantic links and media.
    static final class Wire {
        static final int LIMIT=8*1024*1024, MAGIC=0x50544442;
        final byte[] base;final SortedMap<Long,ActivitySchedule> rules;
        private Wire(byte[] base,SortedMap<Long,ActivitySchedule> rs){this.base=base.clone();this.rules=Collections.unmodifiableSortedMap(new TreeMap<>(rs));}
        private static void v4(byte[] b){need(b!=null&&b.length>=20,"Missing embedded schema4");ByteBuffer x=ByteBuffer.wrap(b);need(x.getInt()==MAGIC&&x.getInt()==3&&x.getInt()==4,"Wrong embedded schema4");}
        private static void text(DataOutputStream o,String s)throws IOException{byte[] b=s.getBytes(StandardCharsets.US_ASCII);need(b.length<=128 && s.equals(new String(b,StandardCharsets.US_ASCII)),"Unsupported schedule encoding");o.writeByte(b.length);o.write(b);}
        private static String text(DataInputStream i)throws IOException{int n=i.readUnsignedByte();need(n<=128&&n<=i.available(),"Schedule string length");byte[] b=new byte[n];i.readFully(b);for(byte c:b)need(c>0,"Schedule string encoding");return new String(b,StandardCharsets.US_ASCII);}
        static byte[] write(byte[] base,SortedMap<Long,ActivitySchedule> rows){v4(base);need(rows!=null,"Missing rules");long len=20L+base.length;long prev=0;
            for(Map.Entry<Long,ActivitySchedule> e:rows.entrySet()){ActivitySchedule v=e.getValue();need(e.getKey()!=null&&e.getKey()>prev&&v!=null,"Schedule order or missing rule");prev=e.getKey();len+=12L+v.first.toString().length()+(v.last==null?0:v.last.toString().length())+v.zone.getId().length();need(len<=LIMIT,"Schedule backup budget");}need(len<=LIMIT,"Schedule backup budget");
            try{ByteArrayOutputStream b=new ByteArrayOutputStream((int)len);DataOutputStream o=new DataOutputStream(b);o.writeInt(MAGIC);o.writeInt(4);o.writeInt(5);o.writeInt(base.length);o.write(base);o.writeInt(rows.size());
                for(Map.Entry<Long,ActivitySchedule> e:rows.entrySet()){ActivitySchedule v=e.getValue();o.writeLong(e.getKey());o.writeByte(v.days);text(o,v.first.toString());text(o,v.last==null?"":v.last.toString());text(o,v.zone.getId());}o.flush();need(b.size()==len,"Schedule length differs");return b.toByteArray();}
            catch(IOException e){throw new IllegalStateException(e);}}
        static Wire read(byte[] raw){need(raw!=null&&raw.length>=40&&raw.length<=LIMIT,"Schedule envelope length");try{DataInputStream i=new DataInputStream(new ByteArrayInputStream(raw));need(i.readInt()==MAGIC&&i.readInt()==4&&i.readInt()==5,"Unknown schedule envelope");int n=i.readInt();need(n>=20&&n<=i.available()-4,"Embedded length");byte[] base=new byte[n];i.readFully(base);v4(base);int count=i.readInt();need(count>=0&&count<=i.available()/23,"Rule count");TreeMap<Long,ActivitySchedule> rows=new TreeMap<>();long prev=0;
                for(int j=0;j<count;j++){long id=i.readLong();need(id>prev,"Duplicate or unordered activity");prev=id;int mask=i.readUnsignedByte();String a=text(i),b=text(i),z=text(i);rows.put(id,new ActivitySchedule(mask,a,b.isEmpty()?null:b,z));}need(i.available()==0,"Trailing schedule bytes");need(Arrays.equals(raw,write(base,rows)),"Noncanonical schedule encoding");return new Wire(base,rows);}
            catch(IOException e){throw new IllegalArgumentException("Truncated schedule",e);}}
    }
}
