package com.supercubegame.pockettodo;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.ExifInterface;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * First export adapter: Android PNG/JPEG bytes to a cropped/redacted PNG.
 * No file publication, database writes, intents, sharing UI or automatic selection.
 * Caller must explicitly select a non-private block and review output before sharing.
 */
public final class ShareExporter {
    private ShareExporter() {}
    /** Read-only frozen export input. Caller must build this from a consistent
     * database snapshot and revalidate that snapshot before presenting/sending it.
     * No origin/backup asset field exists here: only the selected displayed image.
     * This backend is not a stale-preview token or a redaction certificate.
     */
    public static final class MarkdownItem {
        private final String key,text,caption;
        private final byte[] image;
        private final boolean privateContent;
        public MarkdownItem(String noteId,String blockId,String text,byte[] image,String caption,boolean privateContent){
            if(noteId==null||blockId==null||!noteId.matches("[A-Za-z0-9_-]{1,128}")||!blockId.matches("[A-Za-z0-9_-]{1,128}"))
                throw new IllegalArgumentException("Stable note and block identity required");
            if((text==null)==(image==null)||caption==null||image!=null&&(image.length==0||image.length>8*1024*1024))
                throw new IllegalArgumentException("Exactly one bounded text/image block required");
            this.key=noteId+"/"+blockId;this.text=text;this.image=image==null?null:image.clone();
            this.caption=caption;this.privateContent=privateContent;
        }
    }
    /** Escape user prose, never interpret it as Markdown/HTML or an asset path. */
    private static String literal(String text){
        if(text.length()>262144)throw new IllegalArgumentException("Share text exceeds 262144 characters");
        StringBuilder out=new StringBuilder();
        for(int i=0;i<text.length();i++){
            char c=text.charAt(i);
            if(c=='\r'){if(i+1<text.length()&&text.charAt(i+1)=='\n')i++;out.append('\n');}
            else if(c=='\n'||c=='\t')out.append(c);
            else if(Character.isHighSurrogate(c)){
                if(i+1>=text.length()||!Character.isLowSurrogate(text.charAt(i+1)))throw new IllegalArgumentException("Malformed share text");
                out.append(c).append(text.charAt(++i));
            }else if(Character.isLowSurrogate(c)||Character.isISOControl(c))throw new IllegalArgumentException("Invalid share text control");
            else if(c=='<')out.append("&lt;");
            else if(c=='>')out.append("&gt;");
            else if(c=='&')out.append("&amp;");
            else if(c>=33&&c<=126&&!Character.isLetterOrDigit(c))out.append("&#").append((int)c).append(';');
            else out.append(c);
            if(out.length()>1048576)throw new IllegalArgumentException("Escaped share text budget exceeded");
        }
        return out.toString();
    }
    private static final class ZipBytes extends java.io.OutputStream {
        private final ByteArrayOutputStream out=new ByteArrayOutputStream();
        @Override public void write(int b)throws IOException{if(out.size()>=16*1024*1024)throw new IOException("Share ZIP exceeds 16 MiB");out.write(b);}
        @Override public void write(byte[] b,int off,int n)throws IOException{
            if(n<0||n>16*1024*1024-out.size())throw new IOException("Share ZIP exceeds 16 MiB");
            out.write(b,off,n);
        }
    }
    private static void zipEntry(java.util.zip.ZipOutputStream zip,String name,byte[] bytes)throws IOException{
        java.util.zip.ZipEntry entry=new java.util.zip.ZipEntry(name);entry.setTime(0);
        zip.putNextEntry(entry);zip.write(bytes);zip.closeEntry();
    }
    /**
     * Explicit selection, private excluded even when selected, document order retained.
     * New PNG encoding strips container metadata; it does NOT discover/redact secrets.
     * Dedup compares actual encoded bytes, retaining every selected caption/reference.
     * Fixed ZIP names cannot contain note titles, source filenames, IDs or user paths.
     * Provisional bounded policy: 1000 items, 1 MiB Markdown, 16 MiB expanded/ZIP.
     * No files, database writes, automatic selection or partial output on failure.
     */
    public static byte[] markdownZip(List<MarkdownItem> items,java.util.Set<String> selected)throws IOException{
        if(items==null||selected==null||selected.isEmpty()||items.size()>1000||selected.size()>1000)
            throw new IllegalArgumentException("Explicit bounded share selection required");
        List<MarkdownItem> snapshot=new ArrayList<>(items);
        java.util.Set<String> wanted=new java.util.HashSet<>(selected),known=new java.util.HashSet<>();
        for(MarkdownItem item:snapshot)if(item==null||!known.add(item.key))throw new IllegalArgumentException("Duplicate/missing share identity");
        if(wanted.contains(null)||!known.containsAll(wanted))throw new IllegalArgumentException("Unknown share selection");
        StringBuilder md=new StringBuilder("# Pocket Todo\n\n");
        List<byte[]> assets=new ArrayList<>();long imageBytes=0;int count=0;
        for(MarkdownItem item:snapshot){
            if(!wanted.contains(item.key)||item.privateContent)continue;
            count++;
            if(item.image==null)md.append(literal(item.text)).append("\n\n");
            else{
                byte[] clean=fullVisualPng(item.image);
                int index=-1;
                for(int i=0;i<assets.size();i++)if(java.util.Arrays.equals(assets.get(i),clean)){index=i;break;}
                if(index<0){
                    if(clean.length>16*1024*1024-imageBytes)throw new IOException("Expanded share asset budget exceeded");
                    imageBytes+=clean.length;assets.add(clean);index=assets.size()-1;
                }
                md.append("![Image](assets/image-").append(index+1).append(".png)\n\n");
                if(!item.caption.isEmpty())md.append(literal(item.caption)).append("\n\n");
            }
            if(md.length()>1048576)throw new IllegalArgumentException("Markdown budget exceeded");
        }
        if(count==0)throw new IllegalArgumentException("No non-private content selected");
        byte[] markdown=md.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
        if(markdown.length>1048576||imageBytes+markdown.length>16*1024*1024)throw new IOException("Expanded share budget exceeded");
        ZipBytes bytes=new ZipBytes();
        try(java.util.zip.ZipOutputStream zip=new java.util.zip.ZipOutputStream(bytes)){
            zipEntry(zip,"notes.md",markdown);
            for(int i=0;i<assets.size();i++)zipEntry(zip,"assets/image-"+(i+1)+".png",assets.get(i));
        }
        return bytes.out.toByteArray();
    }
    // Deliberately smaller than import limits: full-resolution processing is bounded.
    // Reject larger images, never silently downsample or remap the supplied coordinates.
    private static final int MAX_BYTES = 8 * 1024 * 1024;
    private static final int MAX_EDGE = 2048;
    private static final long MAX_PIXELS = 1000000L;

    private static void rect(int l,int t,int r,int b,int w,int h) {
        if(l<0||t<0||r<=l||b<=t||r>w||b>h)throw new IllegalArgumentException("Rectangle outside image");
    }

    /** Raw raster coordinates only. Reject orientation metadata we cannot yet honor. */
    private static int u16(byte[] b,int p,boolean little) {
        return little?(b[p]&255)|((b[p+1]&255)<<8):((b[p]&255)<<8)|(b[p+1]&255);
    }
    private static long u32(byte[] b,int p,boolean little) {
        return little?((long)u16(b,p+2,true)<<16)|u16(b,p,true):
            ((long)u16(b,p,false)<<16)|u16(b,p+2,false);
    }
    /** Check primary TIFF orientation independently of version-dependent framework parsing.
     * Bounded JPEG segment walk, not a general EXIF reader. Ambiguity fails closed.
     * EXIF without an explicit primary orientation is not editable in this stage.
     */
    private static void jpegOrientation(byte[] b)throws IOException { jpegTag(b,true); }
    private static int jpegTag(byte[] b,boolean rawOnly)throws IOException {
        if(b.length<4||(b[0]&255)!=255||(b[1]&255)!=216)throw new IOException("Invalid JPEG");
        int p=2,exifCount=0,direction=1;
        while(p<b.length) {
            if((b[p++]&255)!=255)throw new IOException("Invalid JPEG marker");
            while(p<b.length&&(b[p]&255)==255)p++;
            if(p>=b.length)throw new IOException("Truncated JPEG marker");
            int marker=b[p++]&255;
            if(marker==218||marker==217)return direction; // Do not scan entropy-coded image bytes.
            if(marker==1||(marker>=208&&marker<=215))continue;
            if(marker==0||marker==216||p>b.length-2)throw new IOException("Invalid JPEG segment");
            int n=u16(b,p,false);
            if(n<2||n>b.length-p)throw new IOException("Truncated JPEG segment");
            int start=p+2,end=p+n;
            if(marker==225&&end-start>=6&&b[start]==69&&b[start+1]==120&&b[start+2]==105&&
               b[start+3]==102&&b[start+4]==0&&b[start+5]==0) {
                if(++exifCount!=1)throw new IOException("Ambiguous JPEG EXIF");
                int t=start+6;
                if(end-t<8)throw new IOException("Truncated TIFF header");
                boolean little=b[t]==73&&b[t+1]==73;
                if(!little&&!(b[t]==77&&b[t+1]==77))throw new IOException("Invalid TIFF byte order");
                if(u16(b,t+2,little)!=42)throw new IOException("Invalid TIFF header");
                long offset=u32(b,t+4,little);
                if(offset<8||offset>(long)end-t-2)throw new IOException("Invalid primary IFD");
                int ifd=t+(int)offset,count=u16(b,ifd,little);
                if((long)ifd+2+12L*count+4>end)throw new IOException("Truncated primary IFD");
                boolean seen=false;
                for(int i=0,q=ifd+2;i<count;i++,q+=12) {
                    if(u16(b,q,little)!=274)continue;
                    if(seen||u16(b,q+2,little)!=3||u32(b,q+4,little)!=1)
                        throw new IOException("Ambiguous primary orientation");
                    seen=true;
                    direction=u16(b,q+8,little);
                    if(u16(b,q+8,little)!=1){
                        if(rawOnly)throw new IOException("Image orientation must be normalized before editing");
                        if(direction<2||direction>8)throw new IOException("Invalid EXIF orientation");
                    }
                }
                if(!seen)throw new IOException("EXIF orientation cannot be confirmed");
            }
            p=end;
        }
        throw new IOException("Incomplete JPEG header");
    }

    private static void orientation(byte[] source,String mime)throws IOException {
        if("image/jpeg".equals(mime)) {
            jpegOrientation(source);
            ExifInterface exif=new ExifInterface(new ByteArrayInputStream(source));
            int value=exif.getAttributeInt(ExifInterface.TAG_ORIENTATION,ExifInterface.ORIENTATION_UNDEFINED);
            if(value!=ExifInterface.ORIENTATION_UNDEFINED&&value!=ExifInterface.ORIENTATION_NORMAL)
                throw new IOException("Image orientation must be normalized before editing");
        }else{
            // PNG eXIf support differs between Android versions; conservatively refuse it.
            DataInputStream in=new DataInputStream(new ByteArrayInputStream(source));
            if(in.readLong()!=0x89504e470d0a1a0aL)throw new IOException("Invalid PNG");
            boolean end=false;
            while(!end) {
                int n=in.readInt(),kind=in.readInt();
                if(n<0||n>in.available()-4)throw new IOException("Invalid PNG chunk");
                if(kind==0x65584966)throw new IOException("PNG EXIF must be normalized before editing");
                if(in.skipBytes(n)!=n)throw new IOException("Truncated PNG");
                in.readInt();end=kind==0x49454e44;
            }
            if(in.available()!=0)throw new IOException("Unexpected trailing PNG data");
        }
    }

    /** Visual coordinates have a separate entry point; callers of the raw codec still fail closed. */
    static int visualOrientation(byte[] source,String mime)throws IOException {
        if(source==null||source.length==0||source.length>MAX_BYTES)throw new IOException("Invalid image byte budget");
        if("image/png".equals(mime)){orientation(source,mime);return 1;}
        if(!"image/jpeg".equals(mime))throw new IOException("Only PNG/JPEG supported");
        int primary=jpegTag(source,false);
        int reported=new ExifInterface(new ByteArrayInputStream(source)).getAttributeInt(ExifInterface.TAG_ORIENTATION,ExifInterface.ORIENTATION_UNDEFINED);
        // Older readers may have no opinion. A concrete disagreement is never guessed away.
        if(reported!=ExifInterface.ORIENTATION_UNDEFINED&&reported!=primary)throw new IOException("Conflicting EXIF orientation");
        return primary;
    }
    static int visualWidth(int width,int height,int direction){return direction>=5?height:width;}
    static int visualHeight(int width,int height,int direction){return direction>=5?width:height;}
    /** A single visual raster and one scanline, with no interpolation. Source bitmap is borrowed. */
    private static int[] visualPixels(Bitmap input,int direction,long budget)throws IOException {
        int w=input.getWidth(),h=input.getHeight();
        if(direction<1||direction>8||w<1||h<1||budget<=0||budget>1048576L||(long)w*h>budget)throw new IOException("Visual raster outside budget");
        int[] out=new int[w*h];
        if(direction==1){input.getPixels(out,0,w,0,0,w,h);return out;}
        int[] row=new int[w];int stride=visualWidth(w,h,direction);
        for(int y=0;y<h;y++){
            input.getPixels(row,0,w,0,y,w,1);
            int first,step;
            switch(direction){
                case 2:first=y*w+w-1;step=-1;break;
                case 3:first=(h-y)*w-1;step=-1;break;
                case 4:first=(h-1-y)*w;step=1;break;
                case 5:first=y;step=stride;break;
                case 6:first=h-1-y;step=stride;break;
                case 7:first=(w-1)*stride+h-1-y;step=-stride;break;
                case 8:first=(w-1)*stride+y;step=-stride;break;
                default:throw new IOException("Invalid EXIF orientation");
            }
            for(int x=0;x<w;x++)out[first+x*step]=row[x];
        }
        return out;
    }
    static Bitmap uprightPreview(Bitmap input,int direction)throws IOException {
        if(direction==1)return input;
        return Bitmap.createBitmap(visualPixels(input,direction,1048576),visualWidth(input.getWidth(),input.getHeight(),direction),visualHeight(input.getWidth(),input.getHeight(),direction),Bitmap.Config.ARGB_8888);
    }
    static byte[] fullVisualPng(byte[] source)throws IOException {return encode(source,0,0,0,0,new int[0][],MAX_PIXELS,true,true);}
    static byte[] visualPng(byte[] source,int l,int t,int r,int b,int[][] masks,long limit)throws IOException {return encode(source,l,t,r,b,masks,limit,true,false);}

    /**
     * Rectangles use exclusive right/bottom; masks are in cropped OUTPUT coordinates.
     * Source bytes are never modified. Returns only a newly encoded PNG, no original
     * container or copied metadata. Caller must not mutate input during this call.
     * JPEGs with rotated/mirrored EXIF and PNG eXIf are explicitly refused for now.
     */
    public static byte[] png(byte[] source,int left,int top,int right,int bottom,
                             int[][] masks,long maxOutputPixels)throws IOException {
        return encode(source,left,top,right,bottom,masks,maxOutputPixels,false,false);
    }
    private static byte[] encode(byte[] source,int left,int top,int right,int bottom,int[][] masks,long maxOutputPixels,boolean visual,boolean whole)throws IOException {
        if(source==null||source.length==0||source.length>MAX_BYTES)
            throw new IllegalArgumentException("Source byte budget exceeded");
        if(masks==null||maxOutputPixels<=0||maxOutputPixels>MAX_PIXELS)
            throw new IllegalArgumentException("Explicit masks and bounded output required");
        BitmapFactory.Options header=new BitmapFactory.Options();header.inJustDecodeBounds=true;
        BitmapFactory.decodeByteArray(source,0,source.length,header);
        if(header.outWidth<=0||header.outHeight<=0||header.outWidth>MAX_EDGE||header.outHeight>MAX_EDGE||
           (long)header.outWidth*header.outHeight>MAX_PIXELS||
           !("image/png".equals(header.outMimeType)||"image/jpeg".equals(header.outMimeType)))
            throw new IOException("Only PNG/JPEG up to 1 million pixels and edge 2048 can be edited");
        int direction=visual?visualOrientation(source,header.outMimeType):1;
        int vw=visualWidth(header.outWidth,header.outHeight,direction),vh=visualHeight(header.outWidth,header.outHeight,direction);
        if(whole){right=vw;bottom=vh;}
        rect(left,top,right,bottom,vw,vh);
        int w=right-left,h=bottom-top;
        if((long)w*h>maxOutputPixels)throw new IllegalArgumentException("Output pixel budget exceeded");
        List<ExportRenderer.Rect> regions=new ArrayList<>();
        for(int[] mask:masks) {
            if(mask==null||mask.length!=4)throw new IllegalArgumentException("Mask needs four coordinates");
            rect(mask[0],mask[1],mask[2],mask[3],w,h);
            regions.add(new ExportRenderer.Rect(mask[0],mask[1],mask[2],mask[3]));
        }
        if(!visual)orientation(source,header.outMimeType);
        Bitmap decoded=null,output=null;
        try {
            BitmapFactory.Options options=new BitmapFactory.Options();
            options.inPreferredConfig=Bitmap.Config.ARGB_8888;options.inScaled=false;
            decoded=BitmapFactory.decodeByteArray(source,0,source.length,options);
            if(decoded==null||decoded.getWidth()!=header.outWidth||decoded.getHeight()!=header.outHeight||
               decoded.getAllocationByteCount()>4*MAX_PIXELS)throw new IOException("Unexpected decoded image");
            int[] pixels=visualPixels(decoded,direction,MAX_PIXELS);
            decoded.recycle();decoded=null;
            ExportRenderer.Raster raster=ExportRenderer.render(pixels,vw,vh,
                new ExportRenderer.Rect(left,top,right,bottom),regions,maxOutputPixels);
            output=Bitmap.createBitmap(raster.copyPixels(),w,h,Bitmap.Config.ARGB_8888);
            ByteArrayOutputStream encoded=new ByteArrayOutputStream();
            if(!output.compress(Bitmap.CompressFormat.PNG,100,encoded))throw new IOException("PNG encoding failed");
            if(encoded.size()==0||encoded.size()>MAX_BYTES)throw new IOException("PNG output byte budget exceeded");
            return encoded.toByteArray();
        }finally{
            if(decoded!=null)decoded.recycle();
            if(output!=null)output.recycle();
        }
    }
}
