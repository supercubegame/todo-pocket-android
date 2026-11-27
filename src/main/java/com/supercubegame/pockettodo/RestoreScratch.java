package com.supercubegame.pockettodo;

import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;

/** Private, process-locked staging for the native full-restore picker. No DB or media GC.
 * Historical unowned cache entries are deliberately never scanned. The permanent lock inode stays put. */
final class RestoreScratch implements Closeable {
    static final String AREA="full-restore-preview-v1", SLOT="pending", OWNER="owner-v1";
    static final long ZIP_LIMIT=128L*1024*1024, EXPANDED_LIMIT=64L*1024*1024;
    interface Input{InputStream open()throws IOException;}
    // One channel per canonical slot in this process throughout its OS lock lifetime.
    // Two Activity instances must never open a second descriptor for an owned slot.
    private static final java.util.Set<Path> LOCAL=new java.util.HashSet<>();
    private static synchronized boolean reserve(Path p){return LOCAL.add(p);}
    private static synchronized void forget(Path p){LOCAL.remove(p);}
    private final Path identity;private final FileChannel channel;private final FileLock lock;private final Path slot;private boolean closed;
    private RestoreScratch(FileChannel ch,FileLock l,Path slot,Path identity){this.identity=identity;channel=ch;lock=l;this.slot=slot;}
    static void verify(boolean ok,String why)throws IOException{if(!ok)throw new IOException(why);}
    private static boolean dir(Path p){return Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS);}
    private static boolean file(Path p){return Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS);}
    private static void clean(Path s)throws IOException{
        if(Files.notExists(s,LinkOption.NOFOLLOW_LINKS))return;verify(dir(s),"Unknown private restore slot");Path marker=s.resolve(OWNER);
        if(Files.notExists(marker,LinkOption.NOFOLLOW_LINKS)){try(DirectoryStream<Path> names=Files.newDirectoryStream(s)){verify(!names.iterator().hasNext(),"Unmarked nonempty restore slot; preserved");}Files.delete(s);return;}
        verify(file(marker)&&Files.size(marker)==0,"Invalid private restore marker");
        // Validate the entire owned shape before removing anything. Never follow links.
        try(DirectoryStream<Path> entries=Files.newDirectoryStream(s)){for(Path p:entries){String n=p.getFileName().toString();if(n.equals(OWNER))continue;if(n.equals("chosen.zip")){verify(file(p),"Unexpected chosen file");continue;}verify(n.equals("unpacked")&&dir(p),"Unknown restore staging entry; preserved");
            try(DirectoryStream<Path> dirs=Files.newDirectoryStream(p)){for(Path d:dirs){verify(dir(d)&&d.getFileName().toString().matches("restore-[0-9]{1,20}"),"Unknown staged directory; preserved");try(DirectoryStream<Path> fs=Files.newDirectoryStream(d)){for(Path f:fs){String k=f.getFileName().toString();verify(file(f)&&(k.equals("state.bin")||k.matches("[0-9a-f]{64}")),"Unknown staged file; preserved");}}}}}}
        // Marker is removed last, so losing the process mid-clean leaves a recoverable slot.
        Path chosen=s.resolve("chosen.zip"),unpacked=s.resolve("unpacked");Files.deleteIfExists(chosen);if(Files.exists(unpacked,LinkOption.NOFOLLOW_LINKS))BackupArchive.deleteTree(unpacked);Files.delete(marker);Files.delete(s);
    }
    private static RestoreScratch acquire(Path cache,boolean make)throws IOException{
        Path parent=cache.toAbsolutePath().normalize();verify(dir(parent),"Private cache unavailable");Path base=parent.toRealPath().resolve(AREA);
        if(!make&&Files.notExists(base,LinkOption.NOFOLLOW_LINKS))return null;
        if(make){try{Files.createDirectory(base);}catch(FileAlreadyExistsException exists){/* inspect the existing object, never replace it */}}
        verify(dir(base)&&base.equals(base.toRealPath()),"Invalid restore area");Path l=base.resolve("lease.lock");
        if(!reserve(l)){if(make)throw new IOException("Another restore preview is active");return null;}
        FileChannel c=null;FileLock lock=null;boolean handed=false;
        try{if(Files.exists(l,LinkOption.NOFOLLOW_LINKS))verify(file(l),"Invalid restore lock");
            c=FileChannel.open(l,StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);
            lock=c.tryLock();if(lock==null){if(make)throw new IOException("Another restore preview is active");return null;}
            Path slot=base.resolve(SLOT);clean(slot);if(make){Files.createDirectory(slot);Files.createFile(slot.resolve(OWNER));}
            RestoreScratch r=new RestoreScratch(c,lock,slot,l);handed=true;return r;
        }finally{if(!handed){try{if(lock!=null)lock.release();}finally{try{if(c!=null)c.close();}finally{forget(l);}}}}}
    static boolean reclaimIfIdle(Path cache)throws IOException{try(RestoreScratch r=acquire(cache,false)){return r!=null;}}
    static AppDatabase.RestorePlan prepare(Path cache,AppDatabase db,Input input)throws IOException{
        if(db==null||input==null)throw new IllegalArgumentException("Missing selected backup");RestoreScratch lease=acquire(cache,true);AppDatabase.RestorePlan p=null;boolean transferred=false;
        try{Path zip=lease.slot.resolve("chosen.zip");try(InputStream in=input.open();OutputStream out=Files.newOutputStream(zip,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)){verify(in!=null,"Backup cannot be opened");byte[] buf=new byte[16384];long used=0;int n;while((n=in.read(buf))!=-1){verify(n>0&&n<=ZIP_LIMIT-used,"Selected backup exceeds transfer budget or stalled");out.write(buf,0,n);used+=n;}verify(used>0,"Empty backup");}
            p=db.prepareRestore(zip,lease.slot.resolve("unpacked"),EXPANDED_LIMIT);Files.delete(zip);p.ownScratch(lease);transferred=true;return p;
        }finally{if(!transferred){try{if(p!=null)p.close();}finally{lease.close();}}}}
    @Override public synchronized void close()throws IOException{if(closed)return;closed=true;try{clean(slot);}finally{try{lock.release();}finally{try{channel.close();}finally{forget(identity);}}}}
}
