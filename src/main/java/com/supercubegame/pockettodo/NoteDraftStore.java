package com.supercubegame.pockettodo;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.charset.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.UUID;

/**
 * Explicit private text drafts, separate from the canonical database and exports.
 * Call off the UI thread. Cooperating writers use one permanent OS lock plus a
 * JVM lock. A slot's tombstone prevents absent-token ABA; never unlink its lock.
 * The caller must verify note ownership/existence and compare the canonical base
 * again inside the final DB write transaction. This class cannot do that.
 * Atomic rename is not a promise of power-loss durability or hostile-directory safety.
 */
public final class NoteDraftStore {
    private static final int MAGIC=0x50544452, VERSION=1;
    // Provisional resource policy aligned with the existing state-byte ceiling.
    public static final int TEXT_BYTES=8*1024*1024;
    private static final int FILE_BYTES=TEXT_BYTES+4096;
    private static final Object PROCESS_LOCK=new Object();
    private final Path root;

    public static final class Slot {
        public final long owner;
        public final String note,block;
        /** null block means a new-text draft, not an existing block with a magic ID. */
        public Slot(long owner,String note,String block){
            if(owner<=0)throw new IllegalArgumentException("Invalid draft owner");
            identity(note);
            if(block!=null)identity(block);
            this.owner=owner;this.note=note;this.block=block;
        }
    }

    public static final class Record {
        public final String token,base,text;
        private Record(String token,String base,String text){this.token=token;this.base=base;this.text=text;}
        public String requireBase(String current){
            fingerprint(current);
            if(text==null||!base.equals(current))throw new IllegalStateException("Draft base changed; do not overwrite");
            return text;
        }
    }

    public NoteDraftStore(Path directory)throws IOException{
        if(directory==null)throw new IllegalArgumentException("Missing draft directory");
        Path path=directory.toAbsolutePath().normalize();
        Files.createDirectories(path);
        if(!Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS)||Files.isSymbolicLink(path))
            throw new IOException("Draft directory is not private regular directory");
        root=path.toRealPath();
    }

    private static byte[] utf8(String value,int limit){
        if(value==null||value.length()>limit)throw new IllegalArgumentException("Draft text budget or null");
        try{
            ByteBuffer buffer=StandardCharsets.UTF_8.newEncoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).encode(java.nio.CharBuffer.wrap(value));
            if(buffer.remaining()>limit)throw new IllegalArgumentException("Draft text byte budget");
            byte[] out=new byte[buffer.remaining()];buffer.get(out);return out;
        }catch(CharacterCodingException e){throw new IllegalArgumentException("Invalid draft Unicode",e);}
    }
    private static void identity(String value){
        if(value==null||value.trim().isEmpty())throw new IllegalArgumentException("Missing draft identity");
        utf8(value,512);
    }
    private static void fingerprint(String value){
        if(value==null||!value.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Invalid draft base");
    }
    private static void token(String value){
        if(value==null||!(value.isEmpty()||value.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")))
            throw new IllegalArgumentException("Invalid draft token");
    }
    private static byte[] digest(byte[] bytes){
        try{return MessageDigest.getInstance("SHA-256").digest(bytes);}
        catch(NoSuchAlgorithmException e){throw new AssertionError(e);}
    }
    private static String hex(byte[] bytes){
        char[] chars="0123456789abcdef".toCharArray();StringBuilder out=new StringBuilder();
        for(byte b:bytes){out.append(chars[(b&255)>>>4]);out.append(chars[b&15]);}
        return out.toString();
    }
    private static void string(DataOutputStream out,String value,int limit)throws IOException{
        byte[] bytes=utf8(value,limit);out.writeInt(bytes.length);out.write(bytes);
    }
    private static String string(DataInputStream in,int limit)throws IOException{
        int n=in.readInt();
        if(n<0||n>limit||n>in.available())throw new IOException("Invalid draft string length");
        byte[] bytes=new byte[n];in.readFully(bytes);
        try{return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();}
        catch(CharacterCodingException e){throw new IOException("Invalid stored draft Unicode",e);}
    }
    private static boolean flag(DataInputStream in)throws IOException{
        int value=in.readUnsignedByte();
        if(value!=0&&value!=1)throw new IOException("Invalid draft boolean");
        return value==1;
    }
    private static void slot(DataOutputStream out,Slot key)throws IOException{
        out.writeLong(key.owner);string(out,key.note,512);out.writeBoolean(key.block!=null);
        if(key.block!=null)string(out,key.block,512);
    }
    private Path path(Slot key)throws IOException{
        if(key==null)throw new IllegalArgumentException("Missing draft slot");
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try(DataOutputStream out=new DataOutputStream(bytes)){slot(out,key);}
        return root.resolve(hex(digest(bytes.toByteArray()))+".draft");
    }
    private interface Work<T>{T run()throws IOException;}
    private <T>T locked(Work<T> work)throws IOException{
        synchronized(PROCESS_LOCK){
            if(!Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS))throw new IOException("Draft directory changed");
            Path lock=root.resolve(".lock");
            if(Files.exists(lock,LinkOption.NOFOLLOW_LINKS)&&!Files.isRegularFile(lock,LinkOption.NOFOLLOW_LINKS))
                throw new IOException("Invalid draft lock");
            try(FileChannel channel=FileChannel.open(lock,StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS);
                FileLock held=channel.lock()){
                if(!held.isValid())throw new IOException("Draft lock not held");
                return work.run();
            }
        }
    }
    public Record read(Slot key)throws IOException{
        final Path file=path(key);
        return locked(()->readLocked(file,key));
    }
    private Record readLocked(Path file,Slot key)throws IOException{
        if(!Files.exists(file,LinkOption.NOFOLLOW_LINKS))return new Record("",null,null);
        if(!Files.isRegularFile(file,LinkOption.NOFOLLOW_LINKS))throw new IOException("Invalid draft file");
        long length=Files.size(file);
        if(length<32||length>FILE_BYTES)throw new IOException("Draft file budget");
        byte[] raw=new byte[(int)length];
        try(DataInputStream in=new DataInputStream(Files.newInputStream(file,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS))){
            in.readFully(raw);if(in.read()!=-1)throw new IOException("Draft grew while reading");
        }
        byte[] body=Arrays.copyOf(raw,raw.length-32);
        if(!MessageDigest.isEqual(digest(body),Arrays.copyOfRange(raw,raw.length-32,raw.length)))
            throw new IOException("Draft checksum differs");
        try(DataInputStream in=new DataInputStream(new ByteArrayInputStream(body))){
            if(in.readInt()!=MAGIC||in.readInt()!=VERSION)throw new IOException("Unknown draft format");
            long owner=in.readLong();String note=string(in,512);String block=flag(in)?string(in,512):null;
            if(owner!=key.owner||!note.equals(key.note)||!java.util.Objects.equals(block,key.block))
                throw new IOException("Draft slot differs");
            String revision=string(in,64);token(revision);
            if(revision.isEmpty())throw new IOException("Stored draft has no token");
            boolean present=flag(in);String base=present?string(in,64):null,text=present?string(in,TEXT_BYTES):null;
            if(present)fingerprint(base);
            if(in.read()!=-1)throw new IOException("Trailing draft fields");
            return new Record(revision,base,text);
        }catch(IllegalArgumentException e){throw new IOException("Invalid draft fields",e);}
    }
    public Record save(Slot key,String expectedToken,String base,String text)throws IOException{
        token(expectedToken);fingerprint(base);utf8(text,TEXT_BYTES);
        return change(key,expectedToken,base,text);
    }
    /** Caller obtains explicit discard/commit consent. Tombstone is not file deletion. */
    public Record clear(Slot key,String expectedToken)throws IOException{
        token(expectedToken);return change(key,expectedToken,null,null);
    }
    private Record change(Slot key,String expectedToken,String base,String text)throws IOException{
        final Path file=path(key);
        return locked(()->{
            Record before=readLocked(file,key);
            if(!before.token.equals(expectedToken))throw new IllegalStateException("Draft changed; reopen");
            if(java.util.Objects.equals(before.base,base)&&java.util.Objects.equals(before.text,text))return before;
            Record after=new Record(UUID.randomUUID().toString(),base,text);
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();
            try(DataOutputStream out=new DataOutputStream(bytes)){
                out.writeInt(MAGIC);out.writeInt(VERSION);slot(out,key);string(out,after.token,64);
                out.writeBoolean(text!=null);
                if(text!=null){string(out,base,64);string(out,text,TEXT_BYTES);}
            }
            byte[] body=bytes.toByteArray();
            Path temp=Files.createTempFile(root,"pending-",".part");
            try{
                try(FileChannel channel=FileChannel.open(temp,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){
                    ByteBuffer buffer=ByteBuffer.wrap(body);
                    while(buffer.hasRemaining())channel.write(buffer);
                    buffer=ByteBuffer.wrap(digest(body));
                    while(buffer.hasRemaining())channel.write(buffer);
                    channel.force(true);
                }
                Record staged=readLocked(temp,key);
                if(!staged.token.equals(after.token)||!java.util.Objects.equals(staged.text,text)||!java.util.Objects.equals(staged.base,base))
                    throw new IOException("Draft staged readback differs");
                Files.move(temp,file,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
                // Failure here is an uncertain write, not a rollback guarantee.
                Record saved=readLocked(file,key);
                if(!saved.token.equals(after.token)||!java.util.Objects.equals(saved.text,text)||!java.util.Objects.equals(saved.base,base))
                    throw new IOException("Draft published readback differs");
                return saved;
            }finally{Files.deleteIfExists(temp);}
        });
    }
}
