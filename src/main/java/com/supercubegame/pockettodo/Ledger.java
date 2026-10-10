package com.supercubegame.pockettodo;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;

/** Android-free ledger. IDs, dates and batch keys come from the caller, never a clock. */
public final class Ledger {
    public enum Kind { EXPENSE, REFUND, INCOME, PLANNED }
    public static final class Entry {
        public final String id;
        public final long activityId;
        public final LocalDate date;
        public final Kind kind;
        public final long cents;
        public final String memo;
        public Entry(String id,long activityId,LocalDate date,Kind kind,long cents,String memo) {
            this.id=identifier(id); this.activityId=positive(activityId); this.date=validDate(date);
            if(kind==null || cents<0 || memo==null) throw new IllegalArgumentException("Invalid ledger entry");
            this.kind=kind; this.cents=cents; this.memo=memo;
        }
        @Override public boolean equals(Object other) {
            if(!(other instanceof Entry)) return false;
            Entry e=(Entry)other;
            return id.equals(e.id) && activityId==e.activityId && date.equals(e.date) && kind==e.kind && cents==e.cents && memo.equals(e.memo);
        }
        @Override public int hashCode() { return Objects.hash(id,activityId,date,kind,cents,memo); }
    }
    private static final class Batch {
        final List<Entry> entries;
        final long revision;
        boolean undone;
        Batch(List<Entry> entries,long revision) { this.entries=List.copyOf(entries); this.revision=revision; }
    }
    private final LinkedHashMap<String,Entry> entries=new LinkedHashMap<>();
    private final Map<String,Batch> batches=new HashMap<>();
    private long revision;
    public Ledger() {}
    static String identifier(String value) {
        if(value==null || value.trim().isEmpty() || !value.equals(value.trim())) throw new IllegalArgumentException("Stable ID required");
        return value;
    }
    static long positive(long id) { if(id<=0) throw new IllegalArgumentException("Positive activity ID required"); return id; }
    static LocalDate validDate(LocalDate date) {
        if(date==null || date.getYear()<1 || date.getYear()>9999) throw new IllegalArgumentException("Date outside supported calendar");
        return date;
    }
    static boolean hasNull(Collection<?> items) { for(Object item:items) if(item==null) return true; return false; }
    public static long parseCents(String text) {
        if(text==null || !text.matches("[0-9]+(?:\\.[0-9]{1,2})?")) throw new IllegalArgumentException("Use non-negative decimal yuan with at most two decimal places");
        return new BigDecimal(text).movePointRight(2).longValueExact();
    }
    public synchronized boolean record(String id,String batch,long activity,LocalDate date,String kind,long cents) {
        if(kind==null) throw new IllegalArgumentException("Entry kind required");
        return recordBatch(batch,List.of(new Entry(id,activity,date,Kind.valueOf(kind),cents,"")));
    }
    /** Validate the entire batch before mutating. A retry of identical payload is a no-op. */
    public synchronized boolean recordBatch(String key,List<Entry> rows) {
        identifier(key);
        if(rows==null || rows.isEmpty() || hasNull(rows)) throw new IllegalArgumentException("Non-empty batch required");
        List<Entry> copy=List.copyOf(rows);
        Batch prior=batches.get(key);
        if(prior!=null) {
            if(!prior.entries.equals(copy)) throw new IllegalStateException("Batch token already used for another payload");
            if(prior.undone) throw new IllegalStateException("Batch was undone; use a new submission token");
            return false;
        }
        Set<String> ids=new HashSet<>();
        for(Entry row:copy) if(!ids.add(row.id) || entries.containsKey(row.id)) throw new IllegalStateException("Entry ID already exists");
        long next=Math.incrementExact(revision);
        for(Entry row:copy) entries.put(row.id,row);
        batches.put(key,new Batch(copy,next)); revision=next; return true;
    }
    /** Only latest untouched batch can be undone; later edits cannot be silently removed. */
    public synchronized void undoBatch(String key) {
        Batch batch=batches.get(identifier(key));
        if(batch==null || batch.undone || batch.revision!=revision) throw new IllegalStateException("Batch is not the latest untouched operation");
        for(Entry row:batch.entries) if(!row.equals(entries.get(row.id))) throw new IllegalStateException("Batch changed");
        long next=Math.incrementExact(revision);
        for(Entry row:batch.entries) entries.remove(row.id);
        batch.undone=true; revision=next;
    }
    public synchronized void correct(Entry expected,Entry replacement) {
        if(expected==null || replacement==null || !expected.id.equals(replacement.id)) throw new IllegalArgumentException("Correction must preserve identity");
        if(!expected.equals(entries.get(expected.id))) throw new IllegalStateException("Entry changed; review current value first");
        long next=Math.incrementExact(revision); entries.put(replacement.id,replacement); revision=next;
    }
    public synchronized List<Entry> snapshot() { return List.copyOf(entries.values()); }
    /** activity=0 means all activities. Empty selected days always means nothing selected. */
    public synchronized long total(long activity,Set<LocalDate> dates,String metric) {
        if(activity<0 || dates==null || hasNull(dates) || metric==null) throw new IllegalArgumentException("Invalid summary filter");
        Set<LocalDate> selected=new HashSet<>(dates);
        for(LocalDate date:selected) validDate(date);
        if(!Set.of("EXPENSE","REFUND","INCOME","PLANNED","NET_EXPENSE","NET_CASH").contains(metric)) throw new IllegalArgumentException("Unknown metric");
        long expenses=0,refunds=0,income=0,planned=0;
        for(Entry e:entries.values()) {
            if((activity!=0 && e.activityId!=activity) || !selected.contains(e.date)) continue;
            switch(e.kind) {
                case EXPENSE: if(metric.equals("EXPENSE")||metric.equals("NET_EXPENSE")||metric.equals("NET_CASH")) expenses=Math.addExact(expenses,e.cents); break;
                case REFUND: if(metric.equals("REFUND")||metric.equals("NET_EXPENSE")||metric.equals("NET_CASH")) refunds=Math.addExact(refunds,e.cents); break;
                case INCOME: if(metric.equals("INCOME")||metric.equals("NET_CASH")) income=Math.addExact(income,e.cents); break;
                case PLANNED: if(metric.equals("PLANNED")) planned=Math.addExact(planned,e.cents); break;
            }
        }
        switch(metric) {
            case "EXPENSE": return expenses;
            case "REFUND": return refunds;
            case "INCOME": return income;
            case "PLANNED": return planned;
            case "NET_EXPENSE": return Math.subtractExact(expenses,refunds);
            default: return Math.subtractExact(Math.addExact(income,refunds),expenses);
        }
    }
    public synchronized Set<LocalDate> recordedActualDates(long activity,Set<LocalDate> selected) {
        if(activity<0 || selected==null || hasNull(selected)) throw new IllegalArgumentException("Invalid selected dates");
        for(LocalDate date:selected) validDate(date);
        Set<LocalDate> result=new TreeSet<>();
        for(Entry e:entries.values()) if(e.kind!=Kind.PLANNED && (activity==0||activity==e.activityId) && selected.contains(e.date)) result.add(e.date);
        return Collections.unmodifiableSet(result);
    }
}
