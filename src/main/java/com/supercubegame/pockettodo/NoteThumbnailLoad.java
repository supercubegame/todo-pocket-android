package com.supercubegame.pockettodo;

import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** One immutable display asset, one decoder call for this one note load. Not an app-global bitmap cache. */
final class NoteThumbnailLoad {
    private NoteThumbnailLoad() { }
    static final int MAX_DISTINCT=4, MAX_BLOCKS=32;
    static final class Page {
        final int index,count,first,end;final List<NoteDocument.Block> blocks;
        Page(List<NoteDocument.Block> source,int i,int n,int a,int b){index=i;count=n;first=a;end=b;blocks=java.util.Collections.unmodifiableList(new java.util.ArrayList<>(source.subList(a,b)));}
    }
    /** Only a rendering projection. Never supply this subset to saveNote(), a backup, or a share selector. Text-only notes retain their original presentation. */
    static Page page(List<NoteDocument.Block> all,int requested){
        if(requested<0)throw new IllegalArgumentException("negative preview page");
        boolean images=false;for(NoteDocument.Block b:all)if(b.kind==NoteDocument.Kind.IMAGE){images=true;break;}
        if(!images)return new Page(all,0,1,0,all.size());
        java.util.ArrayList<Integer> starts=new java.util.ArrayList<>();starts.add(0);java.util.HashSet<String> ids=new java.util.HashSet<>();int start=0;
        for(int i=0;i<all.size();i++){NoteDocument.Block b=all.get(i);boolean image=b.kind==NoteDocument.Kind.IMAGE;
            if(i-start>=MAX_BLOCKS||(image&&!ids.contains(b.assetId)&&ids.size()>=MAX_DISTINCT)){start=i;starts.add(i);ids.clear();}
            if(image)ids.add(b.assetId);
        }
        int n=starts.size(),at=Math.min(requested,n-1);return new Page(all,at,n,starts.get(at),at+1<n?starts.get(at+1):all.size());
    }
    interface Reader<T> { T read(String currentAsset) throws IOException; }
    static <T> Map<String,T> read(List<NoteDocument.Block> blocks, Reader<T> reader) {
        Map<String,T> byAsset=new HashMap<>(), byBlock=new HashMap<>();
        for(NoteDocument.Block block:blocks) {
            if(block.kind!=NoteDocument.Kind.IMAGE)continue;
            // Use the currently displayed immutable ID, not an original link, caption, or visible title.
            if(!byAsset.containsKey(block.assetId)) {
                T value=null;
                try { value=reader.read(block.assetId); }
                catch(IOException unreadable) { /* The existing per-block unavailable indicator remains. */ }
                byAsset.put(block.assetId,value);
            }
            T image=byAsset.get(block.assetId);
            if(image!=null)byBlock.put(block.id,image);
        }
        return byBlock;
    }
}
