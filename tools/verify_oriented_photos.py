"""Photo orientation: run actual product Java with headless ImageIO doubles on host.
Android BitmapFactory, native preview, PDF, two SQLite modes and restore must run
in V12DeviceTest. A host pass is deliberately not a device receipt.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LABELS = ('all_eight_exact_preview_and_full_pixels', 'all_eight_visual_crops_and_opaque_masks',
          'metadata_conflict_and_size_limits_fail_closed', 'markdown_current_public_pixels_only',
          'png_page_exact_and_pdf_marker_positions', 'schema3_cancel_stale_confirm_reopen_restore',
          'schema4_cancel_stale_confirm_reopen_restore_with_shortcut')

def parse_receipt(out, api):
    lines = [s.removeprefix('INSTRUMENTATION_RESULT: stream=') for s in out.splitlines()]
    target = [s for s in lines if s.startswith(('ORIENTED_PHOTO', 'DEVICE_DATABASE_RESULT', 'INSTRUMENTATION_CODE:'))]
    expected = [f'ORIENTED_PHOTO_SCOPE api={api} package=com.supercubegame.pockettodo.v12.preview hardware=ranchu synthetic=true']
    expected += ['ORIENTED_PHOTO_NATIVE '+s+' PASS' for s in LABELS]
    expected += ['DEVICE_DATABASE_RESULT oriented_photo 2/2 PASS', 'INSTRUMENTATION_CODE: -1']
    if api not in (26,34) or target != expected or re.search(r'DEVICE_DATABASE_FAILED|INSTRUMENTATION_FAILED|INSTRUMENTATION_ABORTED|Process crashed|(?:Exception|AssertionError)(?::|\b at\b)',out):
        raise AssertionError('Oriented photo device phase not accepted: see device-oriented-photo.txt')
    return tuple(LABELS)

# Keep the product class intact. These three doubles use the host JPEG/PNG codec,
# not Android. ExifInterface is deliberately controllable independent of TIFF bytes.
BITMAP='''package android.graphics;
import java.awt.image.BufferedImage;import java.io.*;import javax.imageio.ImageIO;
public final class Bitmap {
 public enum Config{ARGB_8888} public enum CompressFormat{PNG}
 final BufferedImage b; Bitmap(BufferedImage i){b=i;}
 public int getWidth(){return b.getWidth();} public int getHeight(){return b.getHeight();}
 public int getAllocationByteCount(){return getWidth()*getHeight()*4;}
 public void getPixels(int[] a,int off,int stride,int x,int y,int w,int h){b.getRGB(x,y,w,h,a,off,stride);}
 public static Bitmap createBitmap(int[] a,int w,int h,Config c){BufferedImage i=new BufferedImage(w,h,BufferedImage.TYPE_INT_ARGB);i.setRGB(0,0,w,h,a,0,w);return new Bitmap(i);}
 public boolean compress(CompressFormat f,int q,OutputStream out){try{return ImageIO.write(b,"png",out);}catch(IOException e){return false;}}
 public void recycle(){} }
'''
FACTORY='''package android.graphics;import java.io.*;import java.awt.image.BufferedImage;import javax.imageio.ImageIO;
public final class BitmapFactory{public static final class Options{public boolean inJustDecodeBounds,inScaled;public int outWidth,outHeight;public String outMimeType;public Bitmap.Config inPreferredConfig;}
 public static Bitmap decodeByteArray(byte[] a,int offset,int size,Options o){try{BufferedImage b=ImageIO.read(new ByteArrayInputStream(a,offset,size));if(b==null)return null;o.outWidth=b.getWidth();o.outHeight=b.getHeight();o.outMimeType=(a[offset]&255)==255?"image/jpeg":"image/png";return o.inJustDecodeBounds?null:new Bitmap(b);}catch(IOException e){return null;}}}
'''
EXIF='''package android.media;import java.io.*;public final class ExifInterface{public static final int ORIENTATION_UNDEFINED=0,ORIENTATION_NORMAL=1;public static final String TAG_ORIENTATION="Orientation";public static int reported;public ExifInterface(InputStream in)throws IOException{}public int getAttributeInt(String n,int def){return reported;}}'''
TEST=r'''package com.supercubegame.pockettodo;
import java.awt.image.BufferedImage;import java.io.*;import java.nio.*;import java.nio.file.*;import java.util.*;import java.util.zip.*;import javax.imageio.ImageIO;import android.media.ExifInterface;
public final class PhotoHost {
 static int assertions;static void need(boolean v,String n){if(!v)throw new AssertionError(n);assertions++;}
 interface Act{void run()throws Exception;}
 static void no(Act a,String msg)throws Exception{try{a.run();}catch(IOException|IllegalArgumentException e){need(e.getMessage()!=null&&e.getMessage().contains(msg),"wrong refusal "+msg+": "+e);return;}throw new AssertionError("missing refusal: "+msg);}
 static byte[] jpeg(int w,int h)throws Exception{BufferedImage b=new BufferedImage(w,h,BufferedImage.TYPE_INT_RGB);for(int y=0;y<h;y++)for(int x=0;x<w;x++)b.setRGB(x,y,0xff000000 | ((22+x*5+y)%215+20)<<16 | ((18+y*7+x/3)%200+24)<<8 | (16+(x*3+y*11)%220));ByteArrayOutputStream o=new ByteArrayOutputStream();need(ImageIO.write(b,"jpeg",o),"jpeg writer");return o.toByteArray();}
 static byte[] tag(byte[] b,int n,boolean little)throws Exception{ByteBuffer t=ByteBuffer.allocate(26).order(little?ByteOrder.LITTLE_ENDIAN:ByteOrder.BIG_ENDIAN);t.put((byte)(little?'I':'M')).put((byte)(little?'I':'M')).putShort((short)42).putInt(8).putShort((short)1).putShort((short)274).putShort((short)3).putInt(1).putShort((short)n).putShort((short)0).putInt(0);ByteArrayOutputStream o=new ByteArrayOutputStream();DataOutputStream d=new DataOutputStream(o);d.write(b,0,2);d.writeShort(0xffe1);d.writeShort(34);d.write(new byte[]{69,120,105,102,0,0});d.write(t.array());d.write(b,2,b.length-2);return o.toByteArray();}
 static int want(BufferedImage b,int d,int x,int y){int w=b.getWidth(),h=b.getHeight();int[][] at={{x,y},{w-1-x,y},{w-1-x,h-1-y},{x,h-1-y},{y,x},{y,h-1-x},{w-1-y,h-1-x},{w-1-y,x}};return b.getRGB(at[d-1][0],at[d-1][1]);}
 static BufferedImage img(byte[] x)throws Exception{return ImageIO.read(new ByteArrayInputStream(x));}
 static void compare(BufferedImage b,BufferedImage raw,int d,int l,int t,int w,int h,boolean mask)throws Exception{need(b!=null&&b.getWidth()==w&&b.getHeight()==h,"visual dimensions "+d);for(int y=0;y<h;y++)for(int x=0;x<w;x++){int expected=mask&&x>=3&&x<12&&y>=4&&y<11?0xff000000:want(raw,d,x+l,y+t);if(b.getRGB(x,y)!=expected)throw new AssertionError("visual pixel "+d+" @"+x+","+y+" expected="+Integer.toHexString(expected)+" got="+Integer.toHexString(b.getRGB(x,y)));}assertions++;}
 static Map<String,byte[]> zip(byte[] b)throws Exception{Map<String,byte[]> v=new LinkedHashMap<>();try(ZipInputStream z=new ZipInputStream(new ByteArrayInputStream(b))){for(ZipEntry e;(e=z.getNextEntry())!=null;){ByteArrayOutputStream o=new ByteArrayOutputStream();byte[] a=new byte[2048];for(int n;(n=z.read(a))!=-1;)o.write(a,0,n);need(v.put(e.getName(),o.toByteArray())==null,"unique member");}}return v;}
 static void clean(byte[] b)throws Exception{try(DataInputStream in=new DataInputStream(new ByteArrayInputStream(b))){need(in.readLong()==0x89504e470d0a1a0aL,"png magic");boolean first=true,data=false;for(;;){int n=in.readInt(),k=in.readInt();need(n>=0&&n<=in.available()-4,"chunk bounds");need((first&&k==0x49484452)||(!first&&(k==0x49444154||k==0x49454e44)),"no source metadata");first=false;if(k==0x49444154)data=true;need(in.skipBytes(n)==n,"chunk body");in.readInt();if(k==0x49454e44){need(n==0&&data&&in.available()==0,"png terminal");break;}}}}
 static void one(byte[] source,BufferedImage raw,int d,boolean share)throws Exception{int w=d<5?80:48,h=d<5?48:80;int l=d<5?16:9,t=d<5?12:20,r=d<5?64:39,b=d<5?36:60;byte[] before=source.clone();byte[] whole=ShareExporter.fullVisualPng(source);clean(whole);compare(img(whole),raw,d,0,0,w,h,false);byte[] cut=ShareExporter.visualPng(source,l,t,r,b,new int[][]{{3,4,12,11}},1000000);compare(img(cut),raw,d,l,t,r-l,b-t,true);android.graphics.Bitmap rawBmp=android.graphics.BitmapFactory.decodeByteArray(source,0,source.length,new android.graphics.BitmapFactory.Options());android.graphics.Bitmap preview=ShareExporter.uprightPreview(rawBmp,d);need(preview.getWidth()==w&&preview.getHeight()==h,"preview dimensions");int[] px=new int[w*h];preview.getPixels(px,0,w,0,0,w,h);for(int y=0;y<h;y++)for(int x=0;x<w;x++)if(px[y*w+x]!=want(raw,d,x,y))throw new AssertionError("preview pixel "+d);assertions++;
 if(share){java.util.List<ShareExporter.MarkdownItem> items=Arrays.asList(new ShareExporter.MarkdownItem("n","i",null,source,"public",false),new ShareExporter.MarkdownItem("n","private",null,new byte[]{0},"secret",true));Map<String,byte[]> z=zip(ShareExporter.markdownZip(items,new HashSet<>(Arrays.asList("n/i","n/private"))));need(new ArrayList<>(z.keySet()).equals(Arrays.asList("notes.md","assets/image-1.png")),"only two selected public members");need(new String(z.get("notes.md"),"UTF-8").equals("# Pocket Todo\n\n![Image](assets/image-1.png)\n\npublic\n\n"),"explicit public prose only");clean(z.get("assets/image-1.png"));compare(img(z.get("assets/image-1.png")),raw,d,0,0,w,h,false);}
 need(Arrays.equals(source,before),"original bytes changed");}
 public static void main(String[] args)throws Exception{byte[] raw=jpeg(80,48);BufferedImage ref=img(raw);ExifInterface.reported=0;one(raw,ref,1,true);for(int d=1;d<=8;d++){for(boolean le:new boolean[]{true,false}){byte[] s=tag(raw,d,le);if(args.length>0&&le){s=Files.readAllBytes(Paths.get(args[0],"orientation-"+d+".jpg"));ref=img(s);}else ref=img(raw);ExifInterface.reported=d;one(s,ref,d,true);ExifInterface.reported=0;need(ShareExporter.visualOrientation(s,"image/jpeg")==d,"explicit primary survives absent framework");if(d!=1){final byte[] test=s;no(()->ShareExporter.png(test,0,0,1,1,new int[0][],1),"must be normalized");}System.out.println("HOST_PHOTO direction="+d+" little="+le+" exact preview/crop/opaque/markdown");}}
 byte[] six=tag(raw,6,true);ExifInterface.reported=1;no(()->ShareExporter.fullVisualPng(six),"Conflicting EXIF");ExifInterface.reported=0;no(()->ShareExporter.fullVisualPng(tag(six,6,false)),"Ambiguous JPEG EXIF");no(()->ShareExporter.fullVisualPng(tag(raw,9,false)),"Invalid EXIF orientation");no(()->ShareExporter.visualPng(six,0,0,79,12,new int[0][],1000000),"Rectangle outside image");no(()->ShareExporter.visualPng(six,0,0,12,10,new int[][]{{0,0,13,1}},1000000),"Rectangle outside image");no(()->ShareExporter.visualPng(six,0,0,10,10,new int[0][],99),"Output pixel budget");no(()->ShareExporter.fullVisualPng(jpeg(1200,850)),"1 million pixels");need(assertions>0,"nonempty");System.out.println("PHOTO_HOST_PASS orientations=8 endian_cases=16 checks="+assertions+" scope=JDK_IMAGEIO_NOT_ANDROID");}
}'''

def java_cases(source=ROOT, fixture=None):
    with tempfile.TemporaryDirectory(prefix='photo-host-') as temp:
        d=Path(temp); files=[]
        for name,text in [('android/graphics/Bitmap.java',BITMAP),('android/graphics/BitmapFactory.java',FACTORY),('android/media/ExifInterface.java',EXIF),('PhotoHost.java',TEST)]:
            f=d/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text);files.append(str(f))
        p=source/'src/main/java/com/supercubegame/pockettodo'
        subprocess.run(['javac','--release','8','-encoding','UTF-8','-d',str(d),*files,str(p/'ExportRenderer.java'),str(p/'ShareExporter.java')],check=True,timeout=45)
        cmd=['java','-Djava.awt.headless=true','-cp',str(d),'com.supercubegame.pockettodo.PhotoHost']
        r=subprocess.run(cmd+([str(fixture)] if fixture else []),capture_output=True,text=True,timeout=45);print(r.stdout,end='')
        if r.returncode:raise AssertionError(r.stderr[-2200:])
        if not re.search(r'(?m)^PHOTO_HOST_PASS orientations=8 endian_cases=16 checks=[1-9][0-9]* scope=JDK_IMAGEIO_NOT_ANDROID$',r.stdout):raise AssertionError('no photo host result')

def receipt_selftest():
    for api in (26,34):
        sample=[f'ORIENTED_PHOTO_SCOPE api={api} package=com.supercubegame.pockettodo.v12.preview hardware=ranchu synthetic=true',*['ORIENTED_PHOTO_NATIVE '+l+' PASS' for l in LABELS],'DEVICE_DATABASE_RESULT oriented_photo 2/2 PASS','INSTRUMENTATION_CODE: -1'];joined='\n'.join(sample)+'\n';assert parse_receipt(joined,api)==LABELS
        bad=[joined.replace(s+'\n','',1) for s in sample]+[joined+s+'\n' for s in sample]+[joined.replace('2/2','1/2'),joined.replace('-1','0'),joined+'DEVICE_DATABASE_FAILED\n',joined+'java.lang.IllegalStateException: fixture\n',joined.replace('ranchu','physical'),joined.replace(str(api),'34' if api==26 else '26'),joined.replace(sample[1]+'\n'+sample[2],sample[2]+'\n'+sample[1])]
        for v in bad:
            try:parse_receipt(v,api)
            except AssertionError:continue
            raise AssertionError('false photo device receipt accepted')
        print('PHOTO_RECEIPTS api=%d refused=%d scope=HOST_ONLY'%(api,len(bad)))

def host_selftest():
    receipt_selftest();java_cases()

if __name__=='__main__':host_selftest()
