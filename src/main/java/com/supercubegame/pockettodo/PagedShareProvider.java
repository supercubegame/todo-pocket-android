package com.supercubegame.pockettodo;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.content.pm.ProviderInfo;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.provider.OpenableColumns;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.*;

/** Exact, temporary grants are still enforced by
 * Android: exported=false, grantUriPermissions=true. A private marker additionally limits
 * names and lifetime. A viewer that already copied a file cannot be forced to forget it. */
public final class PagedShareProvider extends ContentProvider {
    // Proposed handoff window, not a measured receiver performance promise.
    static final long WINDOW_MS=30L*60*1000, BYTE_LIMIT=16L*1024*1024;
    static final Pattern SESSION=Pattern.compile("export-[0-9A-Za-z_-]{1,80}");
    static final Pattern PATH=Pattern.compile("/exports/(export-[0-9A-Za-z_-]{1,80})/(PocketTodo-notes\\.pdf|page-[0-9]{3}\\.png)");
    private static final String MARKER=".share-ready";
    static void require(boolean v)throws IOException{if(!v)throw new IOException("Unavailable share output");}
    @Override public void attachInfo(Context c,ProviderInfo p){
        if(p==null||p.exported||!p.grantUriPermissions||!(c.getPackageName()+".exports").equals(p.authority))throw new IllegalStateException("Private export provider configuration required");
        super.attachInfo(c,p);
    }
    @Override public boolean onCreate(){return true;}
    static Path outbox(Context c)throws IOException{
        Path root=c.getCacheDir().toPath().resolve("approved-exports");Files.createDirectories(root);require(Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS));return root;
    }
    // Before staging, remove only expired private session directories. Never evict live grants.
    static void prune(Path root)throws IOException{
        long now=System.currentTimeMillis();int retained=0;
        try(DirectoryStream<Path> sessions=Files.newDirectoryStream(root)){
            for(Path dir:sessions){
                require(SESSION.matcher(dir.getFileName().toString()).matches()&&Files.isDirectory(dir,LinkOption.NOFOLLOW_LINKS));
                Path marker=dir.resolve(MARKER);long at=Files.getLastModifiedTime(Files.exists(marker,LinkOption.NOFOLLOW_LINKS)?marker:dir,LinkOption.NOFOLLOW_LINKS).toMillis();
                if(at>now||now-at>=WINDOW_MS){
                    try(DirectoryStream<Path> files=Files.newDirectoryStream(dir)){for(Path f:files)Files.delete(f);}Files.delete(dir);
                }else retained++;
            }
        }
        require(retained<4);
    }
    static boolean alive(long thenWall,long thenMono,long wall,long mono){
        return thenWall>0&&thenMono>=0&&wall>=thenWall&&mono>=thenMono&&wall-thenWall<WINDOW_MS&&mono-thenMono<WINDOW_MS;
    }
    static String name(boolean pdf,int index){return pdf?"PocketTodo-notes.pdf":String.format(Locale.ROOT,"page-%03d.png",index+1);}
    static List<Uri> makeReady(Context c,FinalShareAttachments.Batch batch)throws IOException{
        Path root=outbox(c),dir=batch.directory;String session=dir.getFileName().toString();
        require(root.equals(dir.getParent())&&SESSION.matcher(session).matches()&&Files.isDirectory(dir,LinkOption.NOFOLLOW_LINKS));
        boolean pdf="application/pdf".equals(batch.mime);int count=batch.files.size();require((pdf&&count==1)||("image/png".equals(batch.mime)&&count>0&&count<=64));
        Path marker=dir.resolve(MARKER);List<Uri> uris=new ArrayList<>();long total=0;
        ByteArrayOutputStream sink=new ByteArrayOutputStream();
        try(DataOutputStream m=new DataOutputStream(sink)){
            m.writeInt(1);m.writeLong(System.currentTimeMillis());m.writeLong(SystemClock.elapsedRealtime());m.writeBoolean(pdf);m.writeInt(count);
            for(int i=0;i<count;i++){
                String n=name(pdf,i);Path f=dir.resolve(n);require(f.equals(batch.files.get(i))&&Files.isRegularFile(f,LinkOption.NOFOLLOW_LINKS));long b=Files.size(f);require(b>0&&b<=BYTE_LIMIT-total);total+=b;m.writeLong(b);
                uris.add(new Uri.Builder().scheme("content").authority(c.getPackageName()+".exports").appendPath("exports").appendPath(session).appendPath(n).build());
            }
        }
        // Marker is written in full, before any URI is offered for a grant. Duplicate handoff fails.
        Files.write(marker,sink.toByteArray(),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);
        return Collections.unmodifiableList(uris);
    }
    static final class FileInfo {final Path path;final String name,mime;final long size; FileInfo(Path p,String n,String m,long s){path=p;name=n;mime=m;size=s;}}
    static FileInfo lookup(Path root,String raw,long wall,long mono)throws IOException{
        require(raw!=null&&Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS));Matcher m=PATH.matcher(raw);require(m.matches());
        String session=m.group(1),target=m.group(2);Path dir=root.resolve(session);require(Files.isDirectory(dir,LinkOption.NOFOLLOW_LINKS));Path marker=dir.resolve(MARKER);
        require(Files.isRegularFile(marker,LinkOption.NOFOLLOW_LINKS)&&Files.size(marker)<=600L);
        FileInfo selected=null;long total=0;
        try(DataInputStream in=new DataInputStream(Files.newInputStream(marker,LinkOption.NOFOLLOW_LINKS))){
            require(in.readInt()==1&&alive(in.readLong(),in.readLong(),wall,mono));boolean pdf=in.readBoolean();int count=in.readInt();require(pdf?count==1:count>0&&count<=64);
            for(int i=0;i<count;i++){long b=in.readLong();require(b>0&&b<=BYTE_LIMIT-total);total+=b;String n=name(pdf,i);if(n.equals(target))selected=new FileInfo(dir.resolve(n),n,pdf?"application/pdf":"image/png",b);}
            require(in.read()==-1);
        }
        require(selected!=null&&Files.isRegularFile(selected.path,LinkOption.NOFOLLOW_LINKS)&&Files.size(selected.path)==selected.size);return selected;
    }
    private FileInfo info(Uri u)throws IOException{
        Context c=getContext();require(c!=null&&u!=null&&"content".equals(u.getScheme())&&(c.getPackageName()+".exports").equals(u.getEncodedAuthority())&&u.getEncodedQuery()==null&&u.getEncodedFragment()==null);
        return lookup(c.getCacheDir().toPath().resolve("approved-exports"),u.getEncodedPath(),System.currentTimeMillis(),SystemClock.elapsedRealtime());
    }
    @Override public String getType(Uri u){try{return info(u).mime;}catch(IOException e){return null;}}
    @Override public ParcelFileDescriptor openFile(Uri u,String mode)throws FileNotFoundException{
        if(!"r".equals(mode))throw new FileNotFoundException("Read only");try{return ParcelFileDescriptor.open(info(u).path.toFile(),ParcelFileDescriptor.MODE_READ_ONLY);}catch(IOException e){throw new FileNotFoundException("Unavailable share output");}
    }
    @Override public Cursor query(Uri u,String[] projection,String selection,String[] args,String order){
        FileInfo f;try{f=info(u);}catch(IOException e){return null;}
        if(selection!=null||args!=null||order!=null)return null;
        String[] requested=projection==null?new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE}:projection;
        List<String> cols=new ArrayList<>();List<Object> vals=new ArrayList<>();for(String col:requested){if(OpenableColumns.DISPLAY_NAME.equals(col)){cols.add(col);vals.add(f.name);}else if(OpenableColumns.SIZE.equals(col)){cols.add(col);vals.add(f.size);}}
        MatrixCursor cursor=new MatrixCursor(cols.toArray(new String[0]),1);cursor.addRow(vals.toArray());return cursor;
    }
    @Override public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException("Read only");}
    @Override public int delete(Uri u,String s,String[] args){throw new UnsupportedOperationException("Read only");}
    @Override public int update(Uri u,ContentValues v,String s,String[] args){throw new UnsupportedOperationException("Read only");}
}
