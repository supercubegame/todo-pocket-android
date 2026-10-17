package com.supercubegame.pockettodo;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.*;

/** Integrity-checked transport, NOT database restore. State is opaque at this layer.
 * Database adapter must validate schema/IDs/relationships and commit atomically.
 * References must come from that validated state. No encryption or authenticity guarantee.
 * 8 MiB metadata/state budget is provisional memory protection, not a photo-count quota.
 * Write only to app-private directories; system SAF delivery must copy a validated snapshot.
 */
public final class BackupArchive {
    private static final int META_LIMIT = 8 * 1024 * 1024;
    private static final String HEADER = "POCKET_TODO_ARCHIVE\n1\n";
    private BackupArchive() {}
    public static final class Snapshot implements AutoCloseable {
        private final Path directory;
        private final byte[] state;
        private final Map<String,Path> assets;
        private boolean closed;
        private Snapshot(Path directory, byte[] state, Map<String,Path> assets) {
            this.directory = directory; this.state = state;
            this.assets = Collections.unmodifiableMap(new LinkedHashMap<>(assets));
        }
        private void live() { if (closed) throw new IllegalStateException("暂存预览已关闭"); }
        public byte[] state() { live(); return state.clone(); }
        public Map<String,Path> assets() { live(); return assets; }
        @Override public void close() throws IOException { if (!closed) { deleteTree(directory); closed = true; } }
    }
    private static final class Spec {
        final String hash; final long size;
        Spec(String hash,long size) { this.hash=hash; this.size=size; }
    }
    static void deleteTree(Path root) throws IOException {
        if (!Files.exists(root, LinkOption.NOFOLLOW_LINKS)) return;
        Files.walkFileTree(root, new SimpleFileVisitor<Path>() {
            @Override public FileVisitResult visitFile(Path p, BasicFileAttributes attrs) throws IOException { Files.delete(p); return FileVisitResult.CONTINUE; }
            @Override public FileVisitResult postVisitDirectory(Path p, IOException e) throws IOException { if(e!=null)throw e;Files.delete(p);return FileVisitResult.CONTINUE; }
        });
    }
    private static byte[] bounded(InputStream in,int limit) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream(); byte[] buffer=new byte[16384];int n;
        while((n=in.read(buffer))!=-1) { if(n==0)throw new IOException("读取未取得进展"); if(n>limit-bytes.size())throw new IOException("元数据超过预算");bytes.write(buffer,0,n); }
        return bytes.toByteArray();
    }
    private static Spec spec(String line, boolean allowEmpty) throws IOException {
        String[] pair=line.split(" ",-1);
        if(pair.length!=2 || !pair[0].matches("[0-9a-f]{64}") || !pair[1].matches("0|[1-9][0-9]*"))throw new IOException("备份清单格式错误");
        long size;try{size=Long.parseLong(pair[1]);}catch(NumberFormatException e){throw new IOException("大小溢出",e);}
        if(!allowEmpty&&size==0)throw new IOException("空媒体条目");return new Spec(pair[0],size);
    }
    public static Snapshot read(Path archive, Path stagingRoot, long byteBudget) throws IOException {
        if(archive==null||stagingRoot==null||byteBudget<=0)throw new IllegalArgumentException("无效的备份或展开预算");
        if(!Files.isRegularFile(archive,LinkOption.NOFOLLOW_LINKS))throw new IOException("备份不是普通文件");
        Files.createDirectories(stagingRoot);
        if(Files.isSymbolicLink(stagingRoot)||!Files.isDirectory(stagingRoot,LinkOption.NOFOLLOW_LINKS))throw new IOException("暂存目录无效");
        Path stage=Files.createTempDirectory(stagingRoot,"restore-");boolean success=false;
        try(ZipFile zip=new ZipFile(archive.toFile())) {
            Map<String,ZipEntry> actual=new HashMap<>();Enumeration<? extends ZipEntry> entries=zip.entries();
            while(entries.hasMoreElements()) {
                ZipEntry e=entries.nextElement();String name=e.getName();
                if(e.isDirectory()||!(name.equals("manifest.txt")||name.equals("state.bin")||name.matches("media/[0-9a-f]{64}"))||actual.put(name,e)!=null)
                    throw new IOException("重复或未知的备份条目");
                if(actual.size()>META_LIMIT/67+2)throw new IOException("清单条目超过元数据预算");
            }
            if(!actual.containsKey("manifest.txt")||!actual.containsKey("state.bin"))throw new IOException("备份缺少清单或数据");
            byte[] raw;try(InputStream in=zip.getInputStream(actual.get("manifest.txt"))){raw=bounded(in,META_LIMIT);}
            String text=new String(raw,StandardCharsets.US_ASCII);
            if(!Arrays.equals(raw,text.getBytes(StandardCharsets.US_ASCII))||!text.startsWith(HEADER)||!text.endsWith("\n"))throw new IOException("未知的备份版本或编码");
            String[] lines=text.substring(HEADER.length()).split("\n",-1);
            if(lines.length<2||!lines[lines.length-1].isEmpty())throw new IOException("备份清单不完整");
            Spec stateSpec=spec(lines[0],true);if(stateSpec.size>META_LIMIT)throw new IOException("数据超过内存预算");
            Map<String,Spec> expected=new LinkedHashMap<>();expected.put("state.bin",stateSpec);Set<String> ids=new HashSet<>();long total=stateSpec.size;
            if(total>byteBudget)throw new IOException("备份展开超过字节预算");
            for(int i=1;i<lines.length-1;i++) {
                Spec s=spec(lines[i],false);if(!ids.add(s.hash))throw new IOException("清单重复媒体标识");
                if(s.size>byteBudget-total)throw new IOException("备份展开超过字节预算");total+=s.size;expected.put("media/"+s.hash,s);
            }
            Set<String> expectedNames=new HashSet<>(expected.keySet());expectedNames.add("manifest.txt");
            if(!actual.keySet().equals(expectedNames))throw new IOException("备份文件集合与清单不一致");
            Map<String,Path> media=new LinkedHashMap<>();
            for(Map.Entry<String,Spec> item:expected.entrySet()) {
                String name=item.getKey();Spec s=item.getValue();ZipEntry e=actual.get(name);
                if(e.getSize()!=s.size)throw new IOException("条目大小与清单不符");
                Path target=stage.resolve(name.equals("state.bin")?"state.bin":s.hash);
                MessageDigest hash=MediaRepository.sha();long size=0;
                try(InputStream in=zip.getInputStream(e);OutputStream out=Files.newOutputStream(target,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE)) {
                    byte[] buffer=new byte[16384];int n;while((n=in.read(buffer))!=-1) {
                        if(n==0)throw new IOException("备份读取未取得进展");if(n>s.size-size)throw new IOException("条目展开超过声明大小");
                        size+=n;hash.update(buffer,0,n);out.write(buffer,0,n);
                    }
                }
                if(size!=s.size||!MediaRepository.hex(hash.digest()).equals(s.hash))throw new IOException("备份内容校验失败");
                if(!name.equals("state.bin"))media.put(s.hash,target);
            }
            byte[] state=Files.readAllBytes(stage.resolve("state.bin"));Snapshot snapshot=new Snapshot(stage,state,media);success=true;return snapshot;
        } finally { if(!success)deleteTree(stage); }
    }
    private static void entry(ZipOutputStream zip,String name,InputStream in) throws IOException {
        zip.putNextEntry(new ZipEntry(name));byte[] buffer=new byte[16384];int n;
        while((n=in.read(buffer))!=-1){if(n==0)throw new IOException("备份来源未取得进展");zip.write(buffer,0,n);}zip.closeEntry();
    }
    public static void write(Path destination, byte[] state, Set<String> references, MediaRepository media) throws IOException {
        if(destination==null||state==null||references==null||media==null)throw new IllegalArgumentException("缺少备份输入");
        if(state.length>META_LIMIT)throw new IOException("数据超过元数据预算");
        byte[] owned=state.clone();TreeSet<String> ids=new TreeSet<>();
        for(String id:references){MediaRepository.validId(id);ids.add(id);}
        Path dest=destination.toAbsolutePath().normalize();Path parent=dest.getParent();
        if(!Files.isDirectory(parent)||Files.exists(dest,LinkOption.NOFOLLOW_LINKS))throw new IOException("导出目录无效或目标已经存在");
        StringBuilder manifest=new StringBuilder(HEADER).append(MediaRepository.digest(owned)).append(' ').append(owned.length).append('\n');
        long total=owned.length;
        for(String id:ids){media.verify(id);long size=Files.size(media.path(id));if(size>Long.MAX_VALUE-total)throw new IOException("备份大小溢出");total+=size;manifest.append(id).append(' ').append(size).append('\n');if(manifest.length()>META_LIMIT)throw new IOException("清单超过元数据预算");}
        Path temp=Files.createTempFile(parent,".backup-",".part");
        try {
            try(ZipOutputStream zip=new ZipOutputStream(Files.newOutputStream(temp,StandardOpenOption.TRUNCATE_EXISTING))) {
                entry(zip,"manifest.txt",new java.io.ByteArrayInputStream(manifest.toString().getBytes(StandardCharsets.US_ASCII)));
                entry(zip,"state.bin",new java.io.ByteArrayInputStream(owned));
                for(String id:ids)try(InputStream in=Files.newInputStream(media.path(id),StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)){entry(zip,"media/"+id,in);}
            }
            try(FileChannel channel=FileChannel.open(temp,StandardOpenOption.WRITE)){channel.force(true);}
            try(Snapshot snapshot=read(temp,parent,Math.max(1,total))){if(!Arrays.equals(owned,snapshot.state())||!snapshot.assets().keySet().equals(ids))throw new IOException("备份回读不一致");}
            MediaRepository.publishNewFile(temp,dest);
        } finally {Files.deleteIfExists(temp);}
    }
}
