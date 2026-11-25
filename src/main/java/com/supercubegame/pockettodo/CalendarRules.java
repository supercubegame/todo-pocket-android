package com.supercubegame.pockettodo;

import java.time.*;
import java.util.*;

/** Dates are supplied in activity timezone. No live clock and no midnight reset. */
public final class CalendarRules {
    public enum Status { DONE, SKIPPED, UNRECORDED }
    public static final class Mark {
        public final long activityId;
        public final LocalDate date;
        public final Status status;
        public final String memo;
        public final Instant recordedAt;
        public Mark(long activityId,LocalDate date,Status status,String memo,Instant recordedAt) {
            this.activityId=Ledger.positive(activityId); this.date=Ledger.validDate(date);
            if(status==null || memo==null) throw new IllegalArgumentException("Invalid check-in");
            this.status=status; this.memo=memo; this.recordedAt=recordedAt;
        }
    }
    private final Map<Long,TreeMap<LocalDate,Mark>> marks=new LinkedHashMap<>();
    public CalendarRules() {}
    public static List<LocalDate> scheduled(LocalDate start,LocalDate end,Set<DayOfWeek> weekdays) {
        Ledger.validDate(start); Ledger.validDate(end);
        if(end.isBefore(start)||weekdays==null||Ledger.hasNull(weekdays)) throw new IllegalArgumentException("Invalid schedule");
        List<LocalDate> result=new ArrayList<>();
        for(LocalDate d=start;!d.isAfter(end);d=d.plusDays(1)) if(weekdays.contains(d.getDayOfWeek())) result.add(d);
        return List.copyOf(result);
    }
    public synchronized void mark(long activityId,LocalDate date,String status) {
        if(status==null) throw new IllegalArgumentException("Missing status");
        put(new Mark(activityId,date,Status.valueOf(status),"",null));
    }
    /** Production callers supply recordedAt to distinguish backdated activity from entry time. */
    public synchronized void put(Mark value) {
        if(value==null) throw new IllegalArgumentException("Missing check-in");
        TreeMap<LocalDate,Mark> existing=marks.computeIfAbsent(value.activityId,k->new TreeMap<>());
        if(value.status==Status.UNRECORDED) existing.remove(value.date); else existing.put(value.date,value);
    }
    public synchronized String status(long activityId,LocalDate date) {
        Ledger.positive(activityId); Ledger.validDate(date);
        Map<LocalDate,Mark> history=marks.get(activityId);
        Mark found=history==null?null:history.get(date);
        return found==null?Status.UNRECORDED.name():found.status.name();
    }
    public synchronized long completedCount(long activityId) {
        Ledger.positive(activityId); Map<LocalDate,Mark> history=marks.get(activityId);
        return history==null?0:history.values().stream().filter(m->m.status==Status.DONE).count();
    }
    public synchronized List<Mark> snapshot(long activityId) {
        Ledger.positive(activityId); Map<LocalDate,Mark> history=marks.get(activityId);
        return history==null?List.of():List.copyOf(history.values());
    }
    /** Consecutive scheduled days through the supplied date. Skipped/unrecorded breaks. */
    public synchronized int streak(long activityId,LocalDate start,LocalDate through,Set<DayOfWeek> weekdays) {
        Ledger.positive(activityId);
        List<LocalDate> due=scheduled(start,through,weekdays); int result=0;
        for(int i=due.size()-1;i>=0;i--) {
            if(!status(activityId,due.get(i)).equals(Status.DONE.name())) break;
            result=Math.incrementExact(result);
        }
        return result;
    }
}
