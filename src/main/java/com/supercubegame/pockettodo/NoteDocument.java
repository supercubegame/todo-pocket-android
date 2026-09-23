package com.supercubegame.pockettodo;

import java.util.*;

/** Ordered note structure. Asset IDs are not absolute paths or expiring external URIs. */
public final class NoteDocument {
    public enum Kind { TEXT, IMAGE }
    public static final class Block {
        public final String id;
        public final Kind kind;
        public final String text;
        public final String assetId;
        public final String caption;
        public final boolean privateContent;
        private Block(String id,Kind kind,String text,String assetId,String caption,boolean privateContent) {
            this.id=Ledger.identifier(id); this.kind=kind; this.text=text;
            this.assetId=assetId; this.caption=caption; this.privateContent=privateContent;
        }
        public static Block text(String id,String text,boolean privateContent) {
            if(text==null) throw new IllegalArgumentException("Text cannot be null");
            return new Block(id,Kind.TEXT,text,"","",privateContent);
        }
        public static Block image(String id,String assetId,String caption,boolean privateContent) {
            if(assetId==null || !assetId.matches("[A-Za-z0-9_-]+") || caption==null) throw new IllegalArgumentException("Invalid local asset reference");
            return new Block(id,Kind.IMAGE,"",assetId,caption,privateContent);
        }
    }
    /**
     * Immutable current/original digest pair for the forthcoming schema3 adapter.
     * Reference algebra only: not a decoded-image proof, redaction certificate,
     * sharing permission, persistence API or a replacement for Block.
     * Kept separate until storage/backup can preserve BOTH references atomically.
     */
    public static final class ImageRevision {
        public final String assetId;
        public final String originalAssetId;
        public ImageRevision(String assetId,String originalAssetId) {
            this.assetId=digestId(assetId);
            this.originalAssetId=originalAssetId==null?this.assetId:digestId(originalAssetId);
        }
        private static String digestId(String id) {
            if(id==null||!id.matches("[0-9a-f]{64}"))
                throw new IllegalArgumentException("Invalid immutable media digest");
            return id;
        }
        /** Continue from the displayed revision without forgetting the first original. */
        public ImageRevision withDerivative(String nextAssetId) {
            return new ImageRevision(nextAssetId,originalAssetId);
        }
        /** Full backup obligations. This set must NEVER be reused as share selection. */
        public Set<String> backupAssets() {
            Set<String> ids=new LinkedHashSet<>();
            ids.add(assetId);ids.add(originalAssetId);
            return Collections.unmodifiableSet(ids);
        }
        /** Current-only references, NOT permission to share or evidence of redaction.
         * When IDs are equal, these bytes are also the original; callers still need
         * actual output validation, explicit selection and private-content filtering.
         */
        public Set<String> currentAssets() { return Collections.singleton(assetId); }
    }
    private final List<Block> blocks=new ArrayList<>();
    public NoteDocument() {}
    private int index(String id) {
        Ledger.identifier(id);
        for(int i=0;i<blocks.size();i++) if(blocks.get(i).id.equals(id)) return i;
        throw new IllegalArgumentException("Block not found");
    }
    public synchronized void add(Block block) {
        if(block==null) throw new IllegalArgumentException("Missing block");
        for(Block b:blocks) if(b.id.equals(block.id)) throw new IllegalArgumentException("Duplicate block ID");
        blocks.add(block);
    }
    public synchronized void addText(String id,String text) { add(Block.text(id,text,false)); }
    public synchronized void addImage(String id,String assetId,String caption) { add(Block.image(id,assetId,caption,false)); }
    public synchronized void move(String id,int to) {
        int from=index(id);
        if(to<0||to>=blocks.size()) throw new IllegalArgumentException("Invalid block position");
        Block value=blocks.remove(from); blocks.add(to,value);
    }
    public synchronized void replace(Block replacement) {
        if(replacement==null) throw new IllegalArgumentException("Missing replacement");
        int i=index(replacement.id); blocks.set(i,replacement);
    }
    public synchronized void remove(String id) { blocks.remove(index(id)); }
    public synchronized List<String> blockIds() {
        List<String> ids=new ArrayList<>(); for(Block b:blocks) ids.add(b.id); return List.copyOf(ids);
    }
    public synchronized List<Block> snapshot() { return List.copyOf(blocks); }
    /** Private blocks excluded. Image derivative and redaction checks are still export-layer duties. */
    public synchronized List<Block> shareSelection(Set<String> selectedIds) {
        if(selectedIds==null||Ledger.hasNull(selectedIds)) throw new IllegalArgumentException("Explicit selection required");
        for(String id:selectedIds) index(id);
        List<Block> selected=new ArrayList<>();
        for(Block b:blocks) if(selectedIds.contains(b.id) && !b.privateContent) selected.add(b);
        return List.copyOf(selected);
    }
    public synchronized Set<String> referencedAssets() {
        Set<String> result=new LinkedHashSet<>();
        for(Block b:blocks) if(b.kind==Kind.IMAGE) result.add(b.assetId);
        return Collections.unmodifiableSet(result);
    }
}
