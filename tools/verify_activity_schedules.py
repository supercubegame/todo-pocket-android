"""Pure schedule rules, wire and strict device receipts. Does not launch an emulator."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
LABELS=('old_nonempty_v4_copy_no_invented_schedule_or_writes','cancel_stale_one_shot_noop_distinct_same_names','daily_custom_workweek_timezone_leap_and_clear','no_automatic_checkins_ledger_or_private_media_changes','reopen_full_backup_media_and_bad_owner_fail_closed','original_database_archive_and_media_unchanged')

def parse(out,api):
    lines=[x.removeprefix('INSTRUMENTATION_RESULT: stream=') for x in out.splitlines()]
    observed=[s for s in lines if s.startswith(('SCHEDULE_', 'DEVICE_DATABASE_RESULT', 'INSTRUMENTATION_CODE:'))]
    required=[f'SCHEDULE_SCOPE api={api} package=com.supercubegame.pockettodo.v12.preview hardware=ranchu isolated=true',*['SCHEDULE_NATIVE '+n+' PASS' for n in LABELS],'DEVICE_DATABASE_RESULT activity_schedule 2/2 PASS','INSTRUMENTATION_CODE: -1']
    if api not in (26,34) or observed!=required or re.search(r'DEVICE_DATABASE_FAILED|INSTRUMENTATION_FAILED|INSTRUMENTATION_ABORTED|AssertionError|Process crashed|Exception:',out):raise AssertionError('Schedule not accepted; see device-activity-schedule.txt')
    return LABELS

HOST='''package com.supercubegame.pockettodo;
import java.time.*;import java.util.*;import java.nio.*;import java.io.*;
class ScheduleFast {
 static int n; static void yes(boolean v,String m){if(!v)throw new AssertionError(m);n++;}
 static void no(Runnable f,String m){try{f.run();}catch(IllegalArgumentException e){n++;return;}throw new AssertionError(m);}
 static byte[] base(){ByteBuffer q=ByteBuffer.allocate(32);q.putInt(0x50544442).putInt(3).putInt(4);return q.array();} // deliberately not a semantic database
 public static void main(String[] a)throws Exception{LocalDate start=LocalDate.of(2024,2,25);int[] bits={64,1,2,4,8,16,32};for(int mask=1;mask<=127;mask++){
  ActivitySchedule v=new ActivitySchedule(mask,"2024-02-25","2024-03-04","UTC");for(int j=0;j<12;j++){LocalDate d=start.plusDays(j);boolean want=j<=8&&(mask&bits[j%7])!=0;yes(v.due(d)==want,"date and mask "+mask+":"+j);LocalDate found=null;for(int k=j;k<=8;k++){if((mask&bits[k%7])!=0){found=start.plusDays(k);break;}}yes(Objects.equals(v.nextOnOrAfter(d),found),"next day");}yes(!v.due(start.minusDays(1)),"before start");}
  ActivitySchedule v=new ActivitySchedule(31,"2024-02-29",null,"America/Los_Angeles"),w=new ActivitySchedule(65,"2024-02-25","2024-03-04","Asia/Shanghai");Instant t=Instant.parse("2024-03-03T16:30:00Z");yes(!v.dueAt(t)&&w.dueAt(t)&&v.localDay(t).toString().equals("2024-03-03")&&w.localDay(t).toString().equals("2024-03-04"),"explicit timezone");yes(v.localDay(Instant.parse("2024-11-03T08:30:00Z")).equals(v.localDay(Instant.parse("2024-11-03T09:30:00Z"))),"DST fold no duplicate day");yes(new ActivitySchedule(1,"9999-12-31",null,"UTC").nextOnOrAfter(LocalDate.parse("9999-12-31"))==null,"maximum date");
  for(int mask:new int[]{0,128,-1})no(()->new ActivitySchedule(mask,"2024-02-29",null,"UTC"),"mask");for(String d:new String[]{"2024-02-30","0000-01-01","2024-2-29"})no(()->new ActivitySchedule(1,d,null,"UTC"),"bad date");no(()->new ActivitySchedule(1,"2024-02-29","2024-01-01","UTC"),"reverse");no(()->new ActivitySchedule(1,"2024-02-29",null,"Mars/Base"),"zone");
  TreeMap<Long,ActivitySchedule> rs=new TreeMap<>();rs.put(3L,v);rs.put(17L,w);byte[] b=base(),wire=ActivitySchedule.Wire.write(b,rs);ActivitySchedule.Wire p=ActivitySchedule.Wire.read(wire);yes(Arrays.equals(b,p.base)&&p.rules.equals(rs),"round trip");for(int i=0;i<wire.length;i++){final int k=i;no(()->ActivitySchedule.Wire.read(Arrays.copyOf(wire,k)),"truncated");}no(()->ActivitySchedule.Wire.read(Arrays.copyOf(wire,wire.length+1)),"trailing");
  int off=20+b.length;for(int index:new int[]{0,4,8,12,16,16+b.length}){byte[] e=wire.clone();ByteBuffer.wrap(e).putInt(index,-1);no(()->ActivitySchedule.Wire.read(e),"wrong header or count");}byte[] e=wire.clone();ByteBuffer.wrap(e).putLong(off,0);no(()->ActivitySchedule.Wire.read(e),"owner zero");byte[] d=wire.clone();d[off+8]=0;no(()->ActivitySchedule.Wire.read(d),"no weekdays");byte[] du=wire.clone();ByteBuffer.wrap(du).putLong(off+12+10+"America/Los_Angeles".length(),3);no(()->ActivitySchedule.Wire.read(du),"duplicate owner");
  System.out.println("SCHEDULE_FAST "+n+" PASS JDK_RULES_WIRE_NOT_ANDROID_NOT_FULL_BACKUP");}}
'''

def host_selftest():
    with tempfile.TemporaryDirectory() as directory:
        p=Path(directory);f=p/'ScheduleFast.java';f.write_text(HOST);javac=['javac'] if shutil.which('javac') else ['java','-m','jdk.compiler/com.sun.tools.javac.Main'];subprocess.run([*javac,'-encoding','UTF-8','-d',directory,str(ROOT/'src/main/java/com/supercubegame/pockettodo/ActivitySchedule.java'),str(f)],check=True,timeout=40);out=subprocess.check_output(['java','-cp',directory,'com.supercubegame.pockettodo.ScheduleFast'],text=True,timeout=25);assert re.fullmatch(r'SCHEDULE_FAST [1-9][0-9]* PASS JDK_RULES_WIRE_NOT_ANDROID_NOT_FULL_BACKUP\s*',out);print(out.strip(),flush=True)
    for api in (26,34):
        a=[f'SCHEDULE_SCOPE api={api} package=com.supercubegame.pockettodo.v12.preview hardware=ranchu isolated=true',*['SCHEDULE_NATIVE '+s+' PASS' for s in LABELS],'DEVICE_DATABASE_RESULT activity_schedule 2/2 PASS','INSTRUMENTATION_CODE: -1'];v='\n'.join(a);assert parse(v,api)==LABELS;bad=['\n'.join(a[:i]+a[i+1:]) for i in range(len(a))]+[v+'\n'+a[-1],v+'\nAssertionError: stale',v.replace('2/2','1/1'),v.replace('ranchu','phone'),v.replace(a[1]+'\n'+a[2],a[2]+'\n'+a[1]),v.replace(f'api={api}','api=99')];
        for x in bad:
            try:parse(x,api)
            except AssertionError:continue
            raise AssertionError('invalid schedule receipt passed')
        print('SCHEDULE_RECEIPT api=%d %d rejected HOST_ONLY'%(api,len(bad)),flush=True)

if __name__=='__main__':host_selftest()
