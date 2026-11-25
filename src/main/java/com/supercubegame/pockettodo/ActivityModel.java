package com.supercubegame.pockettodo;

import java.util.*;

/** Domain metadata only. Installed-app discovery and durable storage belong to adapters. */
public final class ActivityModel {
    public static final class Category {
        public final long id; public final String name;
        Category(long id,String name) { this.id=Ledger.positive(id); this.name=title(name); }
    }
    public static final class Application {
        public final long id; public final String name,packageName;
        Application(long id,String name,String packageName) {
            this.id=Ledger.positive(id); this.name=title(name);
            if(packageName==null || (!packageName.isEmpty() && !packageName.matches("[A-Za-z][A-Za-z0-9_]*(?:\\.[A-Za-z][A-Za-z0-9_]*)+"))) throw new IllegalArgumentException("Invalid package name");
            this.packageName=packageName;
        }
    }
    public static final class Item {
        public final long id,categoryId,applicationId;
        public final String title;
        public final boolean archived;
        Item(long id,long categoryId,long applicationId,String title,boolean archived) {
            this.id=Ledger.positive(id); this.categoryId=Ledger.positive(categoryId);
            if(applicationId<0) throw new IllegalArgumentException("Invalid application ID");
            this.applicationId=applicationId; this.title=title(title); this.archived=archived;
        }
    }
    private final LinkedHashMap<Long,Category> categories=new LinkedHashMap<>();
    private final List<Long> order=new ArrayList<>();
    private final LinkedHashMap<Long,Application> applications=new LinkedHashMap<>();
    private final LinkedHashMap<Long,Item> activities=new LinkedHashMap<>();
    private final Map<Long,LinkedHashSet<Long>> shortcuts=new HashMap<>();
    public ActivityModel() {}
    static String title(String value) {
        if(value==null||value.trim().isEmpty()) throw new IllegalArgumentException("Name cannot be blank");
        return value.trim();
    }
    private Category category(long id) {
        Category c=categories.get(id); if(c==null) throw new IllegalArgumentException("Category not found"); return c;
    }
    private Application application(long id) {
        Application a=applications.get(id); if(a==null) throw new IllegalArgumentException("Application not found"); return a;
    }
    public synchronized Item item(long id) {
        Item a=activities.get(id); if(a==null) throw new IllegalArgumentException("Activity not found"); return a;
    }
    public synchronized void addCategory(long id,String name) {
        Category c=new Category(id,name);
        if(categories.containsKey(id)) throw new IllegalArgumentException("Duplicate category ID");
        categories.put(id,c); order.add(id); shortcuts.put(id,new LinkedHashSet<>());
    }
    public synchronized void renameCategory(long id,String name) {
        category(id); Category c=new Category(id,name); categories.put(id,c);
    }
    public synchronized void moveCategory(long id,int position) {
        category(id); if(position<0||position>=order.size()) throw new IllegalArgumentException("Invalid category position");
        order.remove(Long.valueOf(id)); order.add(position,id);
    }
    public synchronized List<Long> categoryIds() { return List.copyOf(order); }
    public synchronized String categoryName(long id) { return category(id).name; }
    public synchronized List<Category> categories() {
        List<Category> result=new ArrayList<>(); for(long id:order) result.add(categories.get(id)); return List.copyOf(result);
    }
    public synchronized void addApplication(long id,String name,String packageName) {
        Application a=new Application(id,name,packageName);
        if(applications.containsKey(id)) throw new IllegalArgumentException("Duplicate application ID");
        if(!packageName.isEmpty()) for(Application existing:applications.values()) if(existing.packageName.equals(packageName)) throw new IllegalArgumentException("Package already in catalog");
        applications.put(id,a);
    }
    public synchronized List<Application> applications() { return List.copyOf(applications.values()); }
    public synchronized void setShortcut(long categoryId,long applicationId,boolean enabled) {
        category(categoryId); application(applicationId);
        if(enabled) shortcuts.get(categoryId).add(applicationId); else shortcuts.get(categoryId).remove(applicationId);
    }
    public synchronized Set<Long> shortcuts(long categoryId) {
        category(categoryId); return Collections.unmodifiableSet(new LinkedHashSet<>(shortcuts.get(categoryId)));
    }
    /** applicationId=0 supports ordinary todos/manual unassigned entries. */
    public synchronized void addActivity(long id,long categoryId,long applicationId,String name) {
        category(categoryId); if(applicationId!=0) application(applicationId);
        Item value=new Item(id,categoryId,applicationId,name,false);
        if(activities.containsKey(id)) throw new IllegalArgumentException("Duplicate activity ID");
        activities.put(id,value);
    }
    public synchronized void renameActivity(long id,String name) {
        Item old=item(id); Item value=new Item(old.id,old.categoryId,old.applicationId,name,old.archived); activities.put(id,value);
    }
    public synchronized long categoryOf(long id) { return item(id).categoryId; }
    public synchronized long applicationOf(long id) { return item(id).applicationId; }
    public synchronized void archiveActivity(long id,boolean archived) {
        Item old=item(id); activities.put(id,new Item(old.id,old.categoryId,old.applicationId,old.title,archived));
    }
    public synchronized void moveActivity(long id,long toCategory) {
        Item old=item(id); category(toCategory);
        activities.put(id,new Item(old.id,toCategory,old.applicationId,old.title,old.archived));
    }
    public synchronized List<Long> activeIds() {
        List<Long> result=new ArrayList<>(); for(Item value:activities.values()) if(!value.archived) result.add(value.id); return List.copyOf(result);
    }
    public synchronized List<Item> snapshot() { return List.copyOf(activities.values()); }
}
