package com.supercubegame.pockettodo;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.pdf.PdfDocument;
import android.text.Layout;
import android.text.StaticLayout;
import android.text.TextPaint;
import com.tom_roush.pdfbox.cos.COSDictionary;
import com.tom_roush.pdfbox.cos.COSName;
import com.tom_roush.pdfbox.cos.COSString;
import com.tom_roush.pdfbox.multipdf.LayerUtility;
import com.tom_roush.pdfbox.pdmodel.PDDocument;
import com.tom_roush.pdfbox.pdmodel.PDPage;
import com.tom_roush.pdfbox.pdmodel.PDPageContentStream;
import com.tom_roush.pdfbox.pdmodel.common.PDRectangle;
import com.tom_roush.pdfbox.contentstream.operator.Operator;
import com.tom_roush.pdfbox.pdfwriter.ContentStreamWriter;
import com.tom_roush.pdfbox.pdmodel.graphics.form.PDFormXObject;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Bounded, read-only document backend. No DB, files, intents or consent token.
 * Caller supplies ONLY current displayed images, never the backup/origin set.
 * Selection, privacy and document order are enforced here before image decoding.
 * Physical page fitting is explicit: images keep aspect ratio within page margins.
 * These provisional resource limits are not an Android memory-capacity guarantee.
 */
public final class PagedNoteRenderer {
    private PagedNoteRenderer() {}
    public enum Format { PDF, PNG_ZIP }
    public static final int WIDTH=595, HEIGHT=842, MARGIN=36, MAX_PAGES=64;
    private static final int CONTENT=WIDTH-2*MARGIN, BOTTOM=HEIGHT-MARGIN;
    private static final int MAX_BYTES=16*1024*1024;

    /** Immutable ordered input; key is stable noteId/blockId, not a title/path. */
    public static final class Block {
        private final String key,text,caption;
        private final byte[] image;
        private final boolean secret;
        public Block(String note,String id,String text,byte[] image,String caption,boolean secret) {
            if(note==null||id==null||!note.matches("[A-Za-z0-9_-]{1,128}")||
               !id.matches("[A-Za-z0-9_-]{1,128}")||caption==null||
               (text==null)==(image==null)||image!=null&&(image.length==0||image.length>8388608))
                throw new IllegalArgumentException("Invalid paged block");
            this.key=note+"/"+id;this.text=text;this.caption=caption;
            this.image=image==null?null:image.clone();this.secret=secret;
        }
    }
    public static final class Result {
        public final Format format;
        public final int pages;
        private final byte[] data;
        private Result(Format format,int pages,byte[] data){this.format=format;this.pages=pages;this.data=data;}
        public byte[] bytes(){return data.clone();}
    }
    private static final class Bounded extends OutputStream {
        final ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        @Override public void write(int b)throws IOException{
            if(bytes.size()==MAX_BYTES)throw new IOException("Paged output exceeds 16 MiB");
            bytes.write(b);
        }
        @Override public void write(byte[] b,int offset,int length)throws IOException{
            if(length<0||length>MAX_BYTES-bytes.size())throw new IOException("Paged output exceeds 16 MiB");
            bytes.write(b,offset,length);
        }
    }
    private static String plain(String value)throws IOException{
        if(value.length()>262144)throw new IOException("Paged text exceeds 262144 characters");
        String text=value.replace("\r\n","\n").replace('\r','\n');
        for(int i=0;i<text.length();i++){
            char c=text.charAt(i);
            if(Character.isHighSurrogate(c)){
                if(++i==text.length()||!Character.isLowSurrogate(text.charAt(i)))throw new IOException("Malformed paged text");
            }else if(Character.isLowSurrogate(c)||Character.isISOControl(c)&&c!='\n'&&c!='\t')
                throw new IOException("Invalid paged text control");
        }
        return text;
    }
    private static final class Draw {
        StaticLayout text;int start,end,y,height;
        String original;
        byte[] image;int width;
    }
    private static final class Plan {
        final List<List<Draw>> pages=new ArrayList<>();
        int y=MARGIN;
        Plan(){pages.add(new ArrayList<Draw>());}
        void next()throws IOException{
            if(pages.size()==MAX_PAGES)throw new IOException("Paged output exceeds 64 pages; reduce selection");
            pages.add(new ArrayList<Draw>());y=MARGIN;
        }
        void text(String text)throws IOException{
            if(text.isEmpty())return;
            StaticLayout layout=typeset(text);
            int line=0;
            while(line<layout.getLineCount()){
                int first=line,top=layout.getLineTop(first);
                while(line<layout.getLineCount()&&layout.getLineBottom(line)-top<=BOTTOM-y)line++;
                if(first==line){
                    if(y==MARGIN)throw new IOException("Text line cannot fit on a page");
                    next();continue;
                }
                String fragment=text.substring(layout.getLineStart(first),layout.getLineEnd(line-1));
                if(fragment.endsWith("\n"))fragment=fragment.substring(0,fragment.length()-1);
                Draw d=new Draw();d.original=fragment;d.text=typeset(fragment);d.start=0;d.end=d.text.getHeight();
                d.y=y;d.height=layout.getLineBottom(line-1)-top;
                if(d.end>d.height)throw new IOException("Page text reflow changed; reduce selection");
                pages.get(pages.size()-1).add(d);y+=d.height;
                if(line<layout.getLineCount())next();
            }
            y+=12;
        }
        void image(byte[] clean)throws IOException{
            BitmapFactory.Options o=new BitmapFactory.Options();o.inJustDecodeBounds=true;
            BitmapFactory.decodeByteArray(clean,0,clean.length,o);
            if(o.outWidth<=0||o.outHeight<=0)throw new IOException("Invalid clean page image");
            double scale=Math.min(1.0,Math.min((double)CONTENT/o.outWidth,(double)(BOTTOM-MARGIN)/o.outHeight));
            int w=Math.max(1,(int)Math.floor(o.outWidth*scale)),h=Math.max(1,(int)Math.floor(o.outHeight*scale));
            if(h>BOTTOM-y)next();
            Draw d=new Draw();d.image=clean;d.width=w;d.height=h;d.y=y;
            pages.get(pages.size()-1).add(d);y+=h+12;
        }
    }
    private static StaticLayout typeset(String text){
        TextPaint paint=new TextPaint(Paint.ANTI_ALIAS_FLAG);
        paint.setColor(Color.BLACK);paint.setTextSize(16);
        // Builder.obtain defaults to SIMPLE on 23+; avoid the newer LineBreaker API.
        return StaticLayout.Builder.obtain(text,0,text.length(),paint,CONTENT)
            .setAlignment(Layout.Alignment.ALIGN_NORMAL).setIncludePad(false)
            .setLineSpacing(2,1)
            .setHyphenationFrequency(Layout.HYPHENATION_FREQUENCY_NONE).build();
    }
    public static Result render(List<Block> input,Set<String> selected,Format format)throws IOException{
        if(input==null||selected==null||format==null||input.size()>1000||
           selected.isEmpty()||selected.size()>1000)throw new IllegalArgumentException("Explicit bounded selection required");
        List<Block> blocks=new ArrayList<>(input);Set<String> wanted=new HashSet<>(selected),known=new HashSet<>();
        for(Block b:blocks)if(b==null||!known.add(b.key))throw new IllegalArgumentException("Duplicate/missing paged identity");
        if(wanted.contains(null)||!known.containsAll(wanted))throw new IllegalArgumentException("Unknown paged selection");
        // Validate text and aggregate source budgets before creating any page.
        int count=0;long sourceBytes=0,textBytes=0;
        for(Block b:blocks){
            if(!wanted.contains(b.key)||b.secret)continue;
            count++;textBytes+=plain(b.image==null?b.text:b.caption).getBytes(java.nio.charset.StandardCharsets.UTF_8).length;
            if(b.image!=null)sourceBytes+=b.image.length;
            if(sourceBytes>MAX_BYTES||textBytes>1048576)throw new IOException("Paged selected content budget exceeded");
        }
        if(count==0)throw new IllegalArgumentException("No non-private content selected");
        Plan plan=new Plan();long encoded=0;
        for(Block b:blocks){
            if(!wanted.contains(b.key)||b.secret)continue;
            if(b.image==null)plan.text(plain(b.text));
            else{
                BitmapFactory.Options o=new BitmapFactory.Options();o.inJustDecodeBounds=true;
                BitmapFactory.decodeByteArray(b.image,0,b.image.length,o);
                byte[] clean=ShareExporter.png(b.image,0,0,o.outWidth,o.outHeight,new int[0][],1000000);
                encoded+=clean.length;if(encoded>MAX_BYTES)throw new IOException("Paged clean image budget exceeded");
                plan.image(clean);plan.text(plain(b.caption));
            }
        }
        if(plan.pages.get(0).isEmpty())throw new IllegalArgumentException("No visible content selected");
        Bounded output=new Bounded();
        if(format==Format.PDF){
            pdf(plan,output);
        }else{
            long expanded=0;
            try(ZipOutputStream zip=new ZipOutputStream(output)){
                for(int i=0;i<plan.pages.size();i++){
                    Bitmap page=Bitmap.createBitmap(WIDTH,HEIGHT,Bitmap.Config.ARGB_8888);
                    try{
                        draw(new Canvas(page),plan.pages.get(i));Bounded png=new Bounded();
                        if(!page.compress(Bitmap.CompressFormat.PNG,100,png))throw new IOException("Page PNG encode failed");
                        byte[] bytes=png.bytes.toByteArray();expanded+=bytes.length;
                        if(expanded>MAX_BYTES)throw new IOException("Expanded page PNG budget exceeded");
                        ZipEntry entry=new ZipEntry(String.format(java.util.Locale.ROOT,"pages/page-%03d.png",i+1));
                        entry.setTime(0);zip.putNextEntry(entry);zip.write(bytes);zip.closeEntry();
                    }finally{page.recycle();}
                }
            }
        }
        return new Result(format,plan.pages.size(),output.bytes.toByteArray());
    }
    /** Import only our own bounded visual fragments, never arbitrary external PDFs.
     * Skia knows glyph IDs, not necessarily the original Unicode. ActualText wraps
     * each corresponding text fragment, without replacing glyphs, normalizing
     * radicals, adding invisible duplicate text, or flattening vector text.
     * Keep all fragments in one source document so shared font resources dedupe.
     */
    private static void pdf(Plan plan,Bounded output)throws IOException{
        // One ActualText span per visible line. A page-height text span can be
        // reordered after a later caption by readers' geometric block sorting.
        // Retain physical positions and refuse any unexpected per-line reflow.
        List<List<Draw>> fragments=new ArrayList<>();
        for(List<Draw> page:plan.pages){
            List<Draw> parts=new ArrayList<>();fragments.add(parts);
            for(Draw d:page){
                if(d.text==null){parts.add(d);continue;}
                for(int line=0;line<d.text.getLineCount();line++){
                    String original=d.original.substring(d.text.getLineStart(line),d.text.getLineEnd(line));
                    String value=original;
                    if(value.endsWith("\n"))value=value.substring(0,value.length()-1);
                    Draw part=new Draw();part.original=original;part.text=typeset(value);
                    part.y=d.y+d.text.getLineTop(line);part.start=0;part.end=part.text.getHeight();
                    part.height=d.text.getLineBottom(line)-d.text.getLineTop(line);
                    if(part.text.getLineCount()!=1||part.end>part.height)
                        throw new IOException("PDF line reflow changed; reduce selection");
                    parts.add(part);
                }
            }
        }
        Bounded raw=new Bounded();
        PdfDocument visual=new PdfDocument();
        try{
            int number=0;
            for(List<Draw> page:fragments)for(Draw d:page){
                PdfDocument.Page fragment=visual.startPage(
                    new PdfDocument.PageInfo.Builder(WIDTH,HEIGHT,++number).create());
                try{drawOne(fragment.getCanvas(),d);}finally{visual.finishPage(fragment);}
            }
            visual.writeTo(raw);
        }finally{visual.close();}
        try(PDDocument source=PDDocument.load(raw.bytes.toByteArray());
            PDDocument document=new PDDocument()){
            document.setVersion(1.7f);
            LayerUtility importer=new LayerUtility(document);
            int index=0;
            for(List<Draw> draws:fragments){
                PDPage page=new PDPage(new PDRectangle(WIDTH,HEIGHT));
                document.addPage(page);
                try(PDPageContentStream stream=new PDPageContentStream(document,page)){
                    // Forms inherit the caller's graphics state. Do not let the
                    // white background turn default-black source glyphs white.
                    stream.saveGraphicsState();
                    stream.setNonStrokingColor(1f);
                    stream.addRect(0,0,WIDTH,HEIGHT);stream.fill();
                    stream.restoreGraphicsState();
                    for(Draw d:draws){
                        PDFormXObject form=importer.importPageAsForm(source,index++);
                        if(d.text!=null){
                            COSDictionary properties=new COSDictionary();
                            properties.setItem(COSName.getPDFName("ActualText"),new COSString(
                                ("\uFEFF"+d.original).getBytes(java.nio.charset.StandardCharsets.UTF_16BE)));
                            // Some readers ignore ActualText through named Properties.
                            // Serialize a typed inline dictionary; never interpolate user text as PDF syntax.
                            ByteArrayOutputStream marker=new ByteArrayOutputStream();
                            new ContentStreamWriter(marker).writeTokens(COSName.getPDFName("Span"),
                                properties,Operator.getOperator("BDC"));
                            stream.appendRawCommands(marker.toByteArray());
                        }
                        stream.saveGraphicsState();stream.drawForm(form);stream.restoreGraphicsState();
                        if(d.text!=null)stream.endMarkedContent();
                    }
                }
            }
            document.save(output);
        }
    }
    private static void draw(Canvas canvas,List<Draw> draws)throws IOException{
        canvas.drawColor(Color.WHITE);
        for(Draw d:draws)drawOne(canvas,d);
    }
    private static void drawOne(Canvas canvas,Draw d)throws IOException{
            if(d.text!=null){
                int saved=canvas.save();
                try{
                    canvas.clipRect(MARGIN,d.y,WIDTH-MARGIN,d.y+d.height);
                    canvas.translate(MARGIN,d.y-d.start);d.text.draw(canvas);
                }finally{canvas.restoreToCount(saved);}
            }else{
                Bitmap image=BitmapFactory.decodeByteArray(d.image,0,d.image.length);
                if(image==null)throw new IOException("Page image decode failed");
                int flags=Paint.ANTI_ALIAS_FLAG;
                // At native size, preserve the exact current pixels. Filtering is
                // useful only when reducing an image, not for a 1:1 PDF image.
                if(d.width!=image.getWidth()||d.height!=image.getHeight())flags|=Paint.FILTER_BITMAP_FLAG;
                try{canvas.drawBitmap(image,null,new RectF(MARGIN,d.y,MARGIN+d.width,d.y+d.height),
                    new Paint(flags));}
                finally{image.recycle();}
            }
    }
}
