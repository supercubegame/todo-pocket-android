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
    private static void markdownPng(byte[] b)throws IOException{
        require(b.length>=45&&be(b,0)==0x89504e47&&be(b,4)==0x0d0a1a0a&&be(b,8)==13&&be(b,12)==0x49484452,"invalid rendered image");
        int w=be(b,16),h=be(b,20);require(w>0&&h>0&&w<=2048&&h<=2048&&(long)w*h<=1000000L,"rendered image geometry");
        int p=8;boolean pixels=false;
        while(p<=b.length-12){
            int n=be(b,p),tag=be(b,p+4);require(n>=0&&n<=b.length-p-12,"rendered image chunk length");
            // The renderer makes fresh PNGs; ancillary text, arbitrary binary payloads and trailing bytes are not part of the reviewed image.
            require((tag==0x49484452&&p==8)||tag==0x49444154||tag==0x49454e44||tag==0x73524742||tag==0x67414d41||tag==0x6348524d||tag==0x73424954,"unexpected rendered image chunk");
            CRC32 crc=new CRC32();crc.update(b,p+4,4+n);require(crc.getValue()==(be(b,p+8+n)&0xffffffffL),"rendered image integrity");
            if(tag==0x49444154&&n>0)pixels=true;p+=n+12;
            if(tag==0x49454e44){require(n==0&&pixels&&p==b.length,"nonfinal rendered image end");return;}
        }
        throw new IOException("incomplete rendered image");
    }
    // Only the in-process ShareExporter wire on this Android runtime is eligible. Do not use this to import external files.
    // Rebuild the canonical container into a digest sink; this binds names, order, metadata and EOF without storing a second ZIP.
    static void verifyMarkdownWire(byte[] payload,int previewAssets,byte[] expected)throws IOException{
        require(previewAssets>=0&&previewAssets<=1000,"Markdown asset count");
        MessageDigest identity;try{identity=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}
        OutputStream discard=new OutputStream(){public void write(int b){} @Override public void write(byte[] b,int off,int n){}};
        try(ZipInputStream in=new ZipInputStream(new ByteArrayInputStream(payload));ZipOutputStream canonical=new ZipOutputStream(new DigestOutputStream(discard,identity))){
            byte[] buf=new byte[16384];long total=0;
            for(int i=0;i<=previewAssets;i++){
                String name=i==0?"notes.md":"assets/image-"+i+".png";ZipEntry e=in.getNextEntry();
                require(e!=null&&!e.isDirectory()&&name.equals(e.getName()),"unexpected Markdown member or order");
                ByteArrayOutputStream content=new ByteArrayOutputStream();int n;
                while((n=in.read(buf))!=-1){require(n>0&&n<=LIMIT-total&&(i!=0||n<=1048576-content.size()),"Markdown contents over budget");total+=n;content.write(buf,0,n);}
                in.closeEntry();byte[] bytes=content.toByteArray();
                if(i==0){
                    String md=java.nio.charset.StandardCharsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(bytes)).toString();
                    require(md.startsWith("# Pocket Todo\n\n"),"unrecognized Markdown document");
                    java.util.regex.Matcher refs=java.util.regex.Pattern.compile("(?m)^!\\[Image\\]\\(assets/image-([1-9][0-9]{0,3})\\.png\\)$").matcher(md);int highest=0;
                    while(refs.find()){int id=Integer.parseInt(refs.group(1));require(id<=previewAssets&&id<=highest+1,"unreviewed image reference");highest=Math.max(highest,id);}
                    require(highest==previewAssets,"unreferenced Markdown image");
                }else markdownPng(bytes);
                ZipEntry clean=new ZipEntry(name);clean.setTime(0);canonical.putNextEntry(clean);canonical.write(bytes);canonical.closeEntry();
            }
            require(in.getNextEntry()==null,"extra Markdown member");
        }
        require(MessageDigest.isEqual(identity.digest(),expected),"Markdown archive contains bytes outside the rendered document");
    }
    static Batch stage(Path outbox,int format,int previewPages,byte[] approved,byte[] previewDigest)throws IOException {
        require(format>=0&&format<=2,"unsupported share format");
        if(format==0)require(previewPages>=0&&previewPages<=1000,"Markdown asset count");
        else require(previewPages>0 && previewPages<=MAX_PAGES,"preview page count");
        require(approved!=null && approved.length>0 && approved.length<=LIMIT && previewDigest!=null && previewDigest.length==32,"output budget or identity");
        byte[] payload=approved.clone(); require(MessageDigest.isEqual(previewDigest,digest(payload)),"output differs from preview");
        require(outbox!=null && Files.isDirectory(outbox, LinkOption.NOFOLLOW_LINKS),"private staging directory required");
        Path d=Files.createTempDirectory(outbox,"export-");List<Path> files=new ArrayList<>();boolean success=false;
        try {
            if(format==0){
                verifyMarkdownWire(payload,previewPages,previewDigest);Path dst=d.resolve("PocketTodo-notes.zip");
                Files.write(dst,payload,StandardOpenOption.CREATE_NEW);
                // Actual staged bytes, not a write-count promise. A failed readback leaves no live batch.
                MessageDigest check;try{check=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}
                try(InputStream in=Files.newInputStream(dst,LinkOption.NOFOLLOW_LINKS)){byte[] buf=new byte[16384];int n;long size=0;while((n=in.read(buf))!=-1){require(n>0&&n<=payload.length-size,"staged Markdown length");check.update(buf,0,n);size+=n;}require(size==payload.length&&MessageDigest.isEqual(check.digest(),previewDigest),"staged Markdown differs from preview");}
                files.add(dst);
            }else if(format==1){
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
            Batch batch=new Batch(format==0?"application/zip":format==1?"application/pdf":"image/png",d,files);success=true;return batch;
        }finally{if(!success)erase(d);}
    }
}
