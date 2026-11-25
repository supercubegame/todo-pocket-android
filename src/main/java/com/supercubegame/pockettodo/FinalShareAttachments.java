package com.supercubegame.pockettodo;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import java.util.zip.*;

/** Stages approved bytes, not a content provider. Caller passes only an internally rendered,
 * already decoded preview after ShareTicket.take(currentState), not external PDFs or ZIPs.
 * No media or database handles enter this class. Caller owns grant lifetime/expiry.
 */
final class FinalShareAttachments {
    private static final int LIMIT=16*1024*1024, MAX_PAGES=64, WIDTH=595, HEIGHT=842;
    static final class Batch implements AutoCloseable {
        final String mime; final Path directory; final List<Path> files;
        Batch(String m,Path d,List<Path> f){mime=m; directory=d; files=Collections.unmodifiableList(new ArrayList<>(f));}
        @Override public void close() throws IOException { erase(directory); }
    }
    // Fixed generated names only; never expand an archive-supplied path.
    private static void erase(Path dir) throws IOException {
        if(!Files.exists(dir,LinkOption.NOFOLLOW_LINKS))return;
        try(DirectoryStream<Path> ds=Files.newDirectoryStream(dir)){for(Path p:ds)Files.deleteIfExists(p);}
        Files.deleteIfExists(dir);
    }
    private static void require(boolean good,String name)throws IOException {if(!good)throw new IOException(name);}
    static byte[] digest(byte[] b){try{return MessageDigest.getInstance("SHA-256").digest(b);}catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}}
    private static int be(byte[] b,int i){return ((b[i]&255)<<24)|((b[i+1]&255)<<16)|((b[i+2]&255)<<8)|(b[i+3]&255);}
    private static int le16(byte[] b,int i){return (b[i]&255)|((b[i+1]&255)<<8);}
    private static void checkPng(byte[] h, byte[] tail, long count)throws IOException{
        require(count>=45 && be(h,0)==0x89504e47 && be(h,4)==0x0d0a1a0a && be(h,8)==13 && be(h,12)==0x49484452 && be(h,16)==WIDTH && be(h,20)==HEIGHT,"unexpected generated PNG header or geometry");
        require(be(tail,0)==0 && be(tail,4)==0x49454e44 && be(tail,8)==0xae426082,"incomplete generated PNG");
    }
    static Batch stage(Path outbox,int format,int previewPages,byte[] approved,byte[] previewDigest)throws IOException {
        require(format==1 || format==2,"not a paged format");
        require(previewPages>0 && previewPages<=MAX_PAGES,"preview page count");
        require(approved!=null && approved.length>0 && approved.length<=LIMIT && previewDigest!=null && previewDigest.length==32,"output budget or identity");
        byte[] payload=approved.clone(); require(MessageDigest.isEqual(previewDigest,digest(payload)),"output differs from preview");
        require(outbox!=null && Files.isDirectory(outbox, LinkOption.NOFOLLOW_LINKS),"private staging directory required");
        Path d=Files.createTempDirectory(outbox,"export-");List<Path> files=new ArrayList<>();boolean success=false;
        try {
            if(format==1){
                require(payload.length>=8 && payload[0]=='%' && payload[1]=='P' && payload[2]=='D' && payload[3]=='F' && payload[4]=='-',"unexpected generated PDF");
                Path dst=d.resolve("PocketTodo-notes.pdf");Files.write(dst,payload,StandardOpenOption.CREATE_NEW);files.add(dst);
            }else{
                // Our renderer emits a single-disk standard ZIP with no archive comment.
                int e=payload.length-22;require(e>=0 && be(payload,e)==0x504b0506 && le16(payload,e+4)==0 && le16(payload,e+6)==0 && le16(payload,e+8)==previewPages && le16(payload,e+10)==previewPages && le16(payload,e+20)==0,"page archive terminator or count");
                long total=0;byte[] buf=new byte[16384];
                try(ZipInputStream z=new ZipInputStream(new ByteArrayInputStream(payload))){
                    for(int index=1;index<=previewPages;index++){
                        ZipEntry ent=z.getNextEntry();String name=String.format(Locale.ROOT,"page-%03d.png",index);
                        require(ent!=null && !ent.isDirectory() && ("pages/"+name).equals(ent.getName()),"unexpected page number, member or order");
                        byte[] h=new byte[24], ring=new byte[12];int head=0,pos=0,n;long count=0;Path dst=d.resolve(name);
                        try(OutputStream w=Files.newOutputStream(dst,StandardOpenOption.CREATE_NEW)){
                            while((n=z.read(buf))!=-1){require(n>0 && n<=LIMIT-total,"expanded page budget");total+=n;count+=n;int take=Math.min(n,h.length-head);System.arraycopy(buf,0,h,head,take); head+=take;
                                if(n>=ring.length){System.arraycopy(buf,n-ring.length,ring,0,ring.length);pos=0;}else for(int i=0;i<n;i++){ring[pos]=buf[i];pos=(pos+1)%ring.length;} w.write(buf,0,n);}
                        }
                        byte[] tail=new byte[ring.length];for(int i=0;i<tail.length;i++)tail[i]=ring[(pos+i)%ring.length];
                        checkPng(h,tail,count);z.closeEntry();files.add(dst);
                    }
                    require(z.getNextEntry()==null,"unexpected extra page or asset");
                }
            }
            Batch batch=new Batch(format==1?"application/pdf":"image/png",d,files);success=true;return batch;
        }finally{if(!success)erase(d);}
    }
}
