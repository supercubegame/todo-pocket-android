package com.supercubegame.pockettodo;

import android.content.Context;
import java.io.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.Arrays;

/** One app-private schedule book. No live AppDatabase, active-db pointer, caller-supplied path or replacement operation. */
final class ScheduleBookHome {
    static final long LIMIT=64L*1024*1024;
    final Path root; private final Path active;
    ScheduleBookHome(Context c)throws IOException{this(c.getApplicationContext().getDir("schedule-book-v1",Context.MODE_PRIVATE).toPath());}
    ScheduleBookHome(Path owned)throws IOException{if(!Files.isDirectory(owned,LinkOption.NOFOLLOW_LINKS))throw new IOException("Private book directory unavailable");root=owned.toRealPath();active=root.resolve("book");}
    ActivityScheduleStore open()throws IOException{if(Files.notExists(active,LinkOption.NOFOLLOW_LINKS))return null;return ActivityScheduleStore.openOwned(active,LIMIT);}
    interface Input{InputStream open()throws IOException;} interface Output{OutputStream open()throws IOException;}
    private static void ok(boolean v,String m)throws IOException{if(!v)throw new IOException(m);}
    private final class Lease implements AutoCloseable{
        final FileChannel channel; final FileLock lock; Path scratch; boolean closed;
        Lease(String lane)throws IOException{channel=FileChannel.open(root.resolve("transfer.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);FileLock l;
            try{l=channel.tryLock();if(l==null)throw new IOException("Another book operation is in progress");}catch(IOException|RuntimeException e){channel.close();throw new IOException("Book is busy",e);}lock=l;
            try{for(String s:new String[]{"incoming","outgoing"}){Path p=root.resolve(s);if(Files.notExists(p,LinkOption.NOFOLLOW_LINKS))continue;ok(Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS),"Unexpected staging entry");BackupArchive.deleteTree(p);}scratch=Files.createDirectory(root.resolve(lane));}catch(IOException|RuntimeException e){close();throw e;}}
        public void close()throws IOException{if(closed)return;closed=true;try{if(scratch!=null)BackupArchive.deleteTree(scratch);}finally{try{lock.release();}finally{channel.close();}}}
    }
    private static void copy(InputStream in,OutputStream out,long budget)throws IOException{ok(in!=null&&out!=null,"Stream unavailable");byte[] buf=new byte[16384];long used=0;int n;while((n=in.read(buf))!=-1){ok(n>0&&n<=budget-used,"Input stalled or too large");out.write(buf,0,n);used+=n;}ok(used>0,"Empty input");}
    final class Incoming implements AutoCloseable{private Lease lease;private final Path candidate;private final byte[] snapshot;final int[] counts;
        private Incoming(Lease l,Path f,byte[] b,int[] n){lease=l;candidate=f;snapshot=b;counts=n;}
        synchronized void confirm()throws IOException{Lease l=lease;ok(l!=null,"Import preview expired");lease=null;try(Lease use=l){ok(Files.notExists(active,LinkOption.NOFOLLOW_LINKS),"Existing book will not be replaced");try(ActivityScheduleStore s=ActivityScheduleStore.openOwned(candidate,LIMIT)){ok(Arrays.equals(snapshot,s.verifiedBookState()),"Import snapshot changed");}Files.move(candidate,active,StandardCopyOption.ATOMIC_MOVE);}}
        public synchronized void close()throws IOException{Lease l=lease;lease=null;if(l!=null)l.close();}}
    Incoming prepare(Input input)throws IOException{ok(Files.notExists(active,LinkOption.NOFOLLOW_LINKS),"Existing book will not be replaced");Lease l=new Lease("incoming");boolean give=false;try{ok(Files.notExists(active,LinkOption.NOFOLLOW_LINKS),"Existing book will not be replaced");Path zip=l.scratch.resolve("chosen.zip"),target=l.scratch.resolve("copy");try(InputStream in=input.open();OutputStream out=Files.newOutputStream(zip,StandardOpenOption.CREATE_NEW)){copy(in,out,LIMIT);}
        Incoming x;try(ActivityScheduleStore s=ActivityScheduleStore.importFresh(target,zip,LIMIT)){x=new Incoming(l,target,s.state(),s.bookCounts());}Files.delete(zip);give=true;return x;}finally{if(!give)l.close();}}
    final class Outgoing implements AutoCloseable{private Lease lease;private final Path file;private final byte[] before;private final ActivityScheduleStore owner;final int[] counts;
        private Outgoing(Lease l,Path f,byte[] b,ActivityScheduleStore w,int[] n){lease=l;file=f;before=b;owner=w;counts=n;}
        synchronized void deliver(Output target,Input readback)throws IOException{Lease l=lease;ok(l!=null,"Export preview expired");lease=null;try(Lease used=l){ok(Arrays.equals(before,owner.verifiedBookState()),"Book changed; review again");try(InputStream src=Files.newInputStream(file);OutputStream out=target.open()){copy(src,out,LIMIT);}try(InputStream src=Files.newInputStream(file);InputStream got=readback.open()){ok(got!=null,"Cannot reopen destination");byte[] a=new byte[16384],b=new byte[a.length];int n;while((n=src.read(a))!=-1){ok(n>0,"Stalled source");for(int i=0;i<n;){int k=got.read(b,0,n-i);ok(k>0&&k<=n-i,"Short readback");for(int j=0;j<k;j++)ok(b[j]==a[i+j],"Readback differs");i+=k;}}ok(got.read()==-1,"Trailing destination bytes");}}}
        public synchronized void close()throws IOException{Lease l=lease;lease=null;if(l!=null)l.close();}}
    Outgoing export(ActivityScheduleStore owner)throws IOException{ok(owner!=null&&owner.ownsDirectory(active),"Book not open");Lease l=new Lease("outgoing");boolean give=false;try{byte[] before=owner.state();Path f=l.scratch.resolve("snapshot.zip");owner.exportBackup(f);ok(Files.size(f)<=LIMIT&&Arrays.equals(before,owner.state()),"Oversize or changed export");Outgoing x=new Outgoing(l,f,before,owner,owner.bookCounts());give=true;return x;}finally{if(!give)l.close();}}
}
