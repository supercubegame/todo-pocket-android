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
    // Deliberately smaller than import limits: full-resolution processing is bounded.
    // Reject larger images, never silently downsample or remap the supplied coordinates.
    private static final int MAX_BYTES = 8 * 1024 * 1024;
    private static final int MAX_EDGE = 2048;
    private static final long MAX_PIXELS = 1000000L;

    private static void rect(int l,int t,int r,int b,int w,int h) {
        if(l<0||t<0||r<=l||b<=t||r>w||b>h)throw new IllegalArgumentException("Rectangle outside image");
    }

    /** Raw raster coordinates only. Reject orientation metadata we cannot yet honor. */
    private static void orientation(byte[] source,String mime)throws IOException {
        if("image/jpeg".equals(mime)) {
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

    /**
     * Rectangles use exclusive right/bottom; masks are in cropped OUTPUT coordinates.
     * Source bytes are never modified. Returns only a newly encoded PNG, no original
     * container or copied metadata. Caller must not mutate input during this call.
     * JPEGs with rotated/mirrored EXIF and PNG eXIf are explicitly refused for now.
     */
    public static byte[] png(byte[] source,int left,int top,int right,int bottom,
                             int[][] masks,long maxOutputPixels)throws IOException {
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
        rect(left,top,right,bottom,header.outWidth,header.outHeight);
        int w=right-left,h=bottom-top;
        if((long)w*h>maxOutputPixels)throw new IllegalArgumentException("Output pixel budget exceeded");
        List<ExportRenderer.Rect> regions=new ArrayList<>();
        for(int[] mask:masks) {
            if(mask==null||mask.length!=4)throw new IllegalArgumentException("Mask needs four coordinates");
            rect(mask[0],mask[1],mask[2],mask[3],w,h);
            regions.add(new ExportRenderer.Rect(mask[0],mask[1],mask[2],mask[3]));
        }
        orientation(source,header.outMimeType);
        Bitmap decoded=null,output=null;
        try {
            BitmapFactory.Options options=new BitmapFactory.Options();
            options.inPreferredConfig=Bitmap.Config.ARGB_8888;options.inScaled=false;
            decoded=BitmapFactory.decodeByteArray(source,0,source.length,options);
            if(decoded==null||decoded.getWidth()!=header.outWidth||decoded.getHeight()!=header.outHeight||
               decoded.getAllocationByteCount()>4*MAX_PIXELS)throw new IOException("Unexpected decoded image");
            int[] pixels=new int[header.outWidth*header.outHeight];
            decoded.getPixels(pixels,0,header.outWidth,0,0,header.outWidth,header.outHeight);
            decoded.recycle();decoded=null;
            ExportRenderer.Raster raster=ExportRenderer.render(pixels,header.outWidth,header.outHeight,
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
