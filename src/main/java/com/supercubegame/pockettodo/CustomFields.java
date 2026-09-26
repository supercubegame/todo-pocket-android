package com.supercubegame.pockettodo;

import java.math.BigDecimal;
import java.net.URI;
import java.net.URISyntaxException;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.*;

/** Definitions and values keyed by stable IDs, not labels. No expression or script execution. */
public final class CustomFields {
    public enum Type { TEXT, LONG_TEXT, NUMBER, DATE, SELECT, MULTI_SELECT, LINK, BOOLEAN }
    public static final class Definition {
        public final String id,name;
        public final Type type;
        public final List<String> options;
        public final boolean archived;
        Definition(String id,String name,Type type,List<String> options,boolean archived) {
            this.id=Ledger.identifier(id); this.name=ActivityModel.title(name);
            if(type==null||options==null||Ledger.hasNull(options)) throw new IllegalArgumentException("Invalid field definition");
            LinkedHashSet<String> unique=new LinkedHashSet<>();
            for(String option:options) if(!unique.add(Ledger.identifier(option))) throw new IllegalArgumentException("Duplicate option ID");
            if(type!=Type.SELECT && type!=Type.MULTI_SELECT && !unique.isEmpty()) throw new IllegalArgumentException("Only choice fields have options");
            if((type==Type.SELECT||type==Type.MULTI_SELECT)&&unique.isEmpty()) throw new IllegalArgumentException("Choice options required");
            this.type=type; this.options=List.copyOf(unique); this.archived=archived;
        }
    }
    private final LinkedHashMap<String,Definition> definitions=new LinkedHashMap<>();
    private final Map<Long,Map<String,List<String>>> values=new LinkedHashMap<>();
    public CustomFields() {}
    public synchronized Definition definition(String id) {
        Definition d=definitions.get(id); if(d==null) throw new IllegalArgumentException("Field not found"); return d;
    }
    public synchronized void define(String id,String name,String type,List<String> options) {
        if(type==null) throw new IllegalArgumentException("Type required");
        Definition d=new Definition(id,name,Type.valueOf(type),options,false);
        if(definitions.containsKey(id)) throw new IllegalArgumentException("Field ID already defined");
        definitions.put(id,d);
    }
    public synchronized void rename(String id,String name) {
        Definition old=definition(id); Definition value=new Definition(old.id,name,old.type,old.options,old.archived); definitions.put(id,value);
    }
    public synchronized void archive(String id,boolean archived) {
        Definition old=definition(id); definitions.put(id,new Definition(old.id,old.name,old.type,old.options,archived));
    }
    public synchronized List<Definition> definitions() { return List.copyOf(definitions.values()); }
    public synchronized void put(long activityId,String id,List<String> input) {
        Ledger.positive(activityId); Definition d=definition(id);
        if(d.archived) throw new IllegalStateException("Archived field is read only");
        if(input==null||Ledger.hasNull(input)) throw new IllegalArgumentException("Invalid field values");
        List<String> copy=List.copyOf(input);
        if(d.type!=Type.MULTI_SELECT&&copy.size()>1) throw new IllegalArgumentException("Single value required");
        for(String v:copy) validate(d,v);
        if(d.type==Type.MULTI_SELECT) copy=List.copyOf(new LinkedHashSet<>(copy));
        values.computeIfAbsent(activityId,k->new LinkedHashMap<>()).put(id,copy);
    }
    public synchronized List<String> value(long activityId,String id) {
        Ledger.positive(activityId); definition(id);
        Map<String,List<String>> map=values.get(activityId); return map==null?List.of():map.getOrDefault(id,List.of());
    }
    private static void validate(Definition d,String value) {
        switch(d.type) {
            case NUMBER:
                if(!value.matches("-?[0-9]+(?:\\.[0-9]+)?")) throw new IllegalArgumentException("Decimal number required");
                new BigDecimal(value); break;
            case DATE:
                try { LocalDate date=LocalDate.parse(value); Ledger.validDate(date); if(!date.toString().equals(value)) throw new IllegalArgumentException("Canonical date required"); }
                catch(DateTimeParseException e) { throw new IllegalArgumentException("Invalid calendar date",e); }
                break;
            case SELECT: case MULTI_SELECT:
                if(!d.options.contains(value)) throw new IllegalArgumentException("Unknown option ID"); break;
            case BOOLEAN:
                if(!value.equals("true")&&!value.equals("false")) throw new IllegalArgumentException("Boolean required"); break;
            case LINK:
                try {
                    URI uri=new URI(value);
                    if(!("http".equalsIgnoreCase(uri.getScheme())||"https".equalsIgnoreCase(uri.getScheme()))||uri.getHost()==null||uri.getUserInfo()!=null) throw new IllegalArgumentException("HTTP(S) link without embedded credentials required");
                } catch(URISyntaxException e) { throw new IllegalArgumentException("Invalid link",e); }
                break;
            case TEXT: case LONG_TEXT: break;
        }
    }
}
