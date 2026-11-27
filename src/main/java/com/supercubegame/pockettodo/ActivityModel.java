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
    /** Category archive is a visibility layer. Never copy or rewrite child items, apps or links. */
    private final Set<Long> hiddenCategories=new HashSet<>();
    private Object viewVersion=new Object();
    private void changed(){viewVersion=new Object();}
    private void requireActiveCategory(long id){category(id);if(hiddenCategories.contains(id))throw new IllegalStateException("分类已归档");}
    public synchronized boolean categoryArchived(long id){category(id);return hiddenCategories.contains(id);}
    public synchronized List<Long> categoryIds(boolean history){List<Long> ids=new ArrayList<>();for(long id:order)if(history||!hiddenCategories.contains(id))ids.add(id);return List.copyOf(ids);}
    public synchronized boolean visibleInSearch(long id,boolean history){Item a=item(id);return history||(!a.archived&&!hiddenCategories.contains(a.categoryId));}
    public synchronized boolean canUseTemplate(long source,long dest){category(dest);return !hiddenCategories.contains(dest)&&visibleInSearch(source,false);}
    public synchronized List<Long> shortcutTargets(long category,long app){category(category);application(app);if(hiddenCategories.contains(category)||!shortcuts.get(category).contains(app))return Collections.emptyList();List<Long> ids=new ArrayList<>();for(Item a:activities.values())if(a.applicationId==app&&visibleInSearch(a.id,false))ids.add(a.id);Collections.sort(ids);return List.copyOf(ids);}
    public static final class CategoryImpact {
        public final long id,active,individual,otherTargets,outgoing,incomingTargets;public final String name;
        CategoryImpact(long id,String name,long active,long individual,long otherTargets,long outgoing,long incomingTargets){this.id=Ledger.positive(id);this.name=title(name);if(active<0||individual<0||otherTargets<0||outgoing<0||incomingTargets<0||incomingTargets>active)throw new IllegalArgumentException("无效的分类影响统计");this.active=active;this.individual=individual;this.otherTargets=otherTargets;this.outgoing=outgoing;this.incomingTargets=incomingTargets;}
    }
    public static final class CategoryReview implements AutoCloseable {
        private final ActivityModel owner;private final Object version;private final boolean hidden;private boolean retired;
        public final CategoryImpact impact;
        private CategoryReview(ActivityModel owner,boolean hidden,CategoryImpact impact){this.owner=owner;this.version=owner.viewVersion;this.hidden=hidden;this.impact=impact;}
        @Override public void close(){synchronized(owner){retired=true;}}
    }
    public synchronized CategoryReview reviewCategory(long id,boolean hide){Category selected=category(id);Set<Long> apps=new HashSet<>(),otherLinks=new HashSet<>();long active=0,individual=0,other=0,tracked=0;
        for(Map.Entry<Long,LinkedHashSet<Long>> s:shortcuts.entrySet())if(s.getKey()!=id&&!hiddenCategories.contains(s.getKey()))otherLinks.addAll(s.getValue());
        for(Item a:activities.values())if(a.categoryId==id){if(a.archived){individual++;continue;}active++;if(a.applicationId!=0){apps.add(a.applicationId);if(otherLinks.contains(a.applicationId))tracked++;}}
        for(Item a:activities.values())if(a.categoryId!=id&&!a.archived&&!hiddenCategories.contains(a.categoryId)&&apps.contains(a.applicationId))other++;
        return new CategoryReview(this,hide,new CategoryImpact(id,selected.name,active,individual,other,shortcuts.get(id).size(),tracked));}
    public synchronized boolean confirmCategory(CategoryReview p){if(p==null||p.owner!=this)throw new IllegalArgumentException("分类预览不属于此会话");if(p.retired)throw new IllegalStateException("分类预览已使用或已取消");p.retired=true;if(p.version!=viewVersion)throw new IllegalStateException("分类或活动已变化，请重新预览");long id=p.impact.id;boolean updated=p.hidden?hiddenCategories.add(id):hiddenCategories.remove(id);if(updated)changed();return updated;}
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
        categories.put(id,c); order.add(id); shortcuts.put(id,new LinkedHashSet<>());changed();
    }
    public synchronized void renameCategory(long id,String name) {
        requireActiveCategory(id); Category c=new Category(id,name);if(category(id).name.equals(c.name))return;categories.put(id,c);changed();
    }
    public synchronized void moveCategory(long id,int position) {
        requireActiveCategory(id);List<Long> visible=new ArrayList<>(categoryIds());if(position<0||position>=visible.size())throw new IllegalArgumentException("Invalid category position");if(visible.indexOf(id)==position)return;visible.remove(Long.valueOf(id));visible.add(position,id);int j=0;for(int i=0;i<order.size();i++)if(!hiddenCategories.contains(order.get(i)))order.set(i,visible.get(j++));changed();
    }
    public synchronized List<Long> categoryIds() { return categoryIds(false); }
    public synchronized String categoryName(long id) { return category(id).name; }
    public synchronized List<Category> categories() {
        List<Category> result=new ArrayList<>(); for(long id:categoryIds()) result.add(categories.get(id)); return List.copyOf(result);
    }
    public synchronized void addApplication(long id,String name,String packageName) {
        Application a=new Application(id,name,packageName);
        if(applications.containsKey(id)) throw new IllegalArgumentException("Duplicate application ID");
        if(!packageName.isEmpty()) for(Application existing:applications.values()) if(existing.packageName.equals(packageName)) throw new IllegalArgumentException("Package already in catalog");
        applications.put(id,a);changed();
    }
    public synchronized List<Application> applications() { return List.copyOf(applications.values()); }
    public synchronized void setShortcut(long categoryId,long applicationId,boolean enabled) {
        requireActiveCategory(categoryId); application(applicationId);
        boolean updated=enabled?shortcuts.get(categoryId).add(applicationId):shortcuts.get(categoryId).remove(applicationId);if(updated)changed();
    }
    public synchronized Set<Long> shortcuts(long categoryId) {
        category(categoryId); return Collections.unmodifiableSet(new LinkedHashSet<>(shortcuts.get(categoryId)));
    }
    /** applicationId=0 supports ordinary todos/manual unassigned entries. */
    public synchronized void addActivity(long id,long categoryId,long applicationId,String name) {
        requireActiveCategory(categoryId); if(applicationId!=0) application(applicationId);
        Item value=new Item(id,categoryId,applicationId,name,false);
        if(activities.containsKey(id)) throw new IllegalArgumentException("Duplicate activity ID");
        activities.put(id,value);changed();
    }
    public synchronized void renameActivity(long id,String name) {
        Item old=item(id);requireActiveCategory(old.categoryId);Item value=new Item(old.id,old.categoryId,old.applicationId,name,old.archived);if(old.title.equals(value.title))return;activities.put(id,value);changed();
    }
    public synchronized long categoryOf(long id) { return item(id).categoryId; }
    public synchronized long applicationOf(long id) { return item(id).applicationId; }
    public synchronized void archiveActivity(long id,boolean archived) {
        Item old=item(id);requireActiveCategory(old.categoryId);if(old.archived==archived)return;activities.put(id,new Item(old.id,old.categoryId,old.applicationId,old.title,archived));changed();
    }
    public synchronized void moveActivity(long id,long toCategory) {
        Item old=item(id);requireActiveCategory(old.categoryId);requireActiveCategory(toCategory);if(old.categoryId==toCategory)return;
        activities.put(id,new Item(old.id,toCategory,old.applicationId,old.title,old.archived));changed();
    }
    public synchronized List<Long> activeIds() {
        List<Long> result=new ArrayList<>(); for(Item value:activities.values()) if(visibleInSearch(value.id,false)) result.add(value.id); return List.copyOf(result);
    }
    public synchronized List<Item> snapshot() { return List.copyOf(activities.values()); }
}
