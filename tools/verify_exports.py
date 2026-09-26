#!/usr/bin/env python3
"""JDK pixel contracts only. Not Android codecs, persisted derivatives or sharing."""
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/main/java/com/supercubegame/pockettodo/ExportRenderer.java"
HARNESS = r'''
import com.supercubegame.pockettodo.ExportRenderer;
import com.supercubegame.pockettodo.ExportRenderer.Rect;
import com.supercubegame.pockettodo.ExportRenderer.Raster;
import java.util.*;
import java.io.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;
public final class PixelContractTest {
    static int checks;
    interface Action { void run() throws Exception; }
    static void ok(boolean value,String name) {
        if(!value) throw new AssertionError(name);
        checks++;System.out.println("PASS "+name);
    }
    static void reject(Action action,String name)throws Exception {
        boolean rejected=false;
        try {action.run();} catch(IllegalArgumentException e) {rejected=true;}
        ok(rejected,name);
    }
    static Raster render(int[] pixels,int w,int h,Rect crop,List<Rect> masks) {
        return ExportRenderer.render(pixels,w,h,crop,masks,20000000L);
    }
    static int[] fixture() {
        int[] p=new int[35];
        for(int i=0;i<p.length;i++)p[i]=0xff000000|((i+1)*0x010203);
        return p;
    }
    static void basic() {
        Raster r=render(new int[]{0xff102030,0xff405060},2,1,new Rect(0,0,2,1),List.of());
        ok(r.width==2&&r.height==1&&Arrays.equals(r.copyPixels(),new int[]{0xff102030,0xff405060}),"identity_smoke");
    }
    static void crop() {
        int[] p=fixture(),before=p.clone();
        Raster r=render(p,7,5,new Rect(2,1,6,4),List.of());
        ok(r.width==4&&r.height==3,"crop_dimensions");
        int[] expected={p[9],p[10],p[11],p[12],p[16],p[17],p[18],p[19],p[23],p[24],p[25],p[26]};
        ok(Arrays.equals(r.copyPixels(),expected),"crop_nonzero_origin_pixels");
        ok(Arrays.equals(p,before),"crop_source_unchanged");
        Raster corner=render(p,7,5,new Rect(6,4,7,5),List.of());
        ok(corner.width==1&&corner.height==1&&corner.copyPixels()[0]==p[34],"crop_last_pixel_exclusive_edges");
        int[] transparent={0x00123456,0x7f234567,0xff345678,0x01456789};
        ok(Arrays.equals(render(transparent,2,2,new Rect(0,0,2,2),List.of()).copyPixels(),transparent),"unmasked_argb_preserved_exactly");
    }
    static void mask() {
        int[] p=fixture(),before=p.clone();
        // These are OUTPUT coordinates, not coordinates of the 7x5 source.
        List<Rect> masks=List.of(new Rect(1,0,3,2),new Rect(2,1,4,3));
        Raster r=render(p,7,5,new Rect(2,1,6,4),masks);
        int[] expected={p[9],0xff000000,0xff000000,p[12],p[16],0xff000000,0xff000000,0xff000000,p[23],p[24],0xff000000,0xff000000};
        ok(Arrays.equals(r.copyPixels(),expected),"mask_exact_black_and_outside_pixels");
        ok(Arrays.equals(p,before),"mask_source_unchanged");
        int[] alpha={0x00123456,0x40223344,0x80556677,0xff8899aa};
        int[] all=render(alpha,2,2,new Rect(0,0,2,2),List.of(new Rect(0,0,2,2))).copyPixels();
        ok(Arrays.equals(all,new int[]{0xff000000,0xff000000,0xff000000,0xff000000}),"mask_transparent_source_fully_opaque");
        List<Rect> reversed=List.of(masks.get(1),masks.get(0),masks.get(0));
        ok(Arrays.equals(render(p,7,5,new Rect(2,1,6,4),reversed).copyPixels(),expected),"mask_overlap_order_and_duplicate_invariant");
    }
    static void ownership() {
        int[] p=fixture(),before=p.clone();
        Raster r=render(p,7,5,new Rect(0,0,7,5),List.of());
        p[0]=0;ok(Arrays.equals(r.copyPixels(),before),"result_does_not_alias_source");
        int[] got=r.copyPixels();got[1]=0;
        ok(Arrays.equals(r.copyPixels(),before),"result_defensive_copy");
        render(before,7,5,new Rect(0,0,7,5),List.of(new Rect(0,0,7,5)));
        ok(Arrays.equals(r.copyPixels(),before),"later_render_cannot_change_prior_result");
    }
    static void invalid()throws Exception {
        int[] p=fixture(),before=p.clone();
        reject(()->render(null,7,5,new Rect(0,0,7,5),List.of()),"null_source_rejected");
        reject(()->render(p,0,5,new Rect(0,0,1,1),List.of()),"zero_width_rejected");
        reject(()->render(p,7,-5,new Rect(0,0,1,1),List.of()),"negative_height_rejected");
        reject(()->render(p,7,6,new Rect(0,0,1,1),List.of()),"source_length_mismatch_rejected");
        reject(()->render(p,Integer.MAX_VALUE,Integer.MAX_VALUE,new Rect(0,0,1,1),List.of()),"dimension_overflow_rejected");
        reject(()->render(new int[16385],16385,1,new Rect(0,0,1,1),List.of()),"source_edge_policy_rejected");
        reject(()->render(p,5000,4001,new Rect(0,0,1,1),List.of()),"source_pixel_policy_rejected");
        reject(()->render(p,7,5,null,List.of()),"explicit_crop_required");
        reject(()->render(p,7,5,new Rect(0,0,7,5),null),"explicit_mask_list_required");
        reject(()->render(p,7,5,new Rect(-1,0,1,1),List.of()),"negative_crop_rejected");
        reject(()->render(p,7,5,new Rect(0,0,8,5),List.of()),"crop_outside_source_rejected");
        reject(()->render(p,7,5,new Rect(0,0,7,6),List.of()),"crop_bottom_outside_rejected");
        reject(()->render(p,7,5,new Rect(2,1,2,4),List.of()),"zero_area_crop_rejected");
        reject(()->render(p,7,5,new Rect(6,4,2,1),List.of()),"reversed_crop_rejected");
        reject(()->render(p,7,5,new Rect(2,1,6,4),Arrays.asList((Rect)null)),"null_mask_rejected");
        reject(()->render(p,7,5,new Rect(2,1,6,4),List.of(new Rect(0,0,5,3))),"mask_uses_output_bounds");
        reject(()->render(p,7,5,new Rect(2,1,6,4),List.of(new Rect(0,0,4,4))),"mask_bottom_outside_rejected");
        reject(()->render(p,7,5,new Rect(2,1,6,4),List.of(new Rect(-1,0,1,1))),"negative_mask_rejected");
        reject(()->render(p,7,5,new Rect(2,1,6,4),List.of(new Rect(1,1,1,2))),"empty_mask_rejected");
        reject(()->render(p,7,5,new Rect(2,1,6,4),List.of(new Rect(2,2,1,1))),"reversed_mask_rejected");
        reject(()->render(p,7,5,new Rect(2,1,6,4),List.of(new Rect(0,0,1,1),new Rect(0,0,5,3))),"late_invalid_mask_rejects_whole_request");
        reject(()->ExportRenderer.render(p,7,5,new Rect(2,1,6,4),List.of(),11),"output_budget_rejected");
        reject(()->ExportRenderer.render(p,7,5,new Rect(0,0,1,1),List.of(),0),"zero_budget_rejected");
        reject(()->ExportRenderer.render(p,7,5,new Rect(0,0,1,1),List.of(),20000001L),"budget_above_policy_rejected");
        ok(ExportRenderer.render(p,7,5,new Rect(2,1,6,4),List.of(),12).copyPixels().length==12,"exact_output_budget_accepted");
        ok(Arrays.equals(p,before),"all_rejections_preserve_source");
        int[] edge=new int[16384];edge[16383]=0xff123456;
        ok(render(edge,16384,1,new Rect(16383,0,16384,1),List.of()).copyPixels()[0]==0xff123456,"exact_source_edge_accepted");
        // Valid full-sized buffer: the pixel boundary must not hide behind length validation.
        int[] limit=new int[20000000];limit[limit.length-1]=0xff654321;
        ok(render(limit,5000,4000,new Rect(4999,3999,5000,4000),List.of()).copyPixels()[0]==0xff654321,"exact_source_pixel_limit_accepted");
        int[] over=new int[20005000];
        reject(()->render(over,5000,4001,new Rect(0,0,1,1),List.of()),"valid_length_over_pixel_limit_rejected");
    }
    static void png()throws Exception {
        int[] p=fixture();
        Raster r=render(p,7,5,new Rect(2,1,6,4),List.of(new Rect(1,0,3,2),new Rect(2,1,4,3)));
        BufferedImage image=new BufferedImage(r.width,r.height,BufferedImage.TYPE_INT_ARGB);
        image.setRGB(0,0,r.width,r.height,r.copyPixels(),0,r.width);
        ByteArrayOutputStream out=new ByteArrayOutputStream();
        ok(ImageIO.write(image,"png",out),"jdk_png_encoder_available");
        byte[] bytes=out.toByteArray();
        ok(Arrays.equals(Arrays.copyOf(bytes,8),new byte[]{(byte)137,80,78,71,13,10,26,10}),"actual_png_signature");
        BufferedImage decoded=ImageIO.read(new ByteArrayInputStream(bytes));
        ok(decoded!=null&&decoded.getWidth()==4&&decoded.getHeight()==3,"independent_png_decode_dimensions");
        int[] expected={p[9],0xff000000,0xff000000,p[12],p[16],0xff000000,0xff000000,0xff000000,p[23],p[24],0xff000000,0xff000000};
        ok(Arrays.equals(decoded.getRGB(0,0,4,3,null,0,4),expected),"independent_png_decode_all_pixels");
    }
    public static void main(String[] args)throws Exception {
        String mode=args.length==0?"all":args[0];
        if(mode.equals("basic")) basic();
        else if(mode.equals("crop")) crop();
        else if(mode.equals("mask")) mask();
        else if(mode.equals("ownership")) ownership();
        else if(mode.equals("all")) {basic();crop();mask();ownership();invalid();png();}
        else throw new IllegalArgumentException("unknown test mode");
        System.out.println("PIXEL_RESULT "+checks+"/"+checks+" PASS");
    }
}
'''

def run(args, expected_failure=None):
    result = subprocess.run(list(map(str, args)), text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=90)
    if expected_failure is None:
        print(result.stdout, end="", flush=True)
        if result.returncode:
            raise RuntimeError(f"JDK command failed ({result.returncode}): {args}")
    else:
        if result.returncode == 0 or ("java.lang.AssertionError: " + expected_failure) not in result.stdout:
            print(result.stdout, flush=True)
            raise AssertionError("Mutation not rejected by intended assertion: " + expected_failure)
        print("PASS mutation rejected by " + expected_failure, flush=True)
    return result.stdout

def compile_and_run(folder, source, mode):
    folder.mkdir()
    java = folder / "ExportRenderer.java"
    java.write_text(source, encoding="utf-8")
    harness = folder / "PixelContractTest.java"
    harness.write_text(HARNESS, encoding="utf-8")
    run(["javac", "-encoding", "UTF-8", "-d", folder, java, harness])
    return run(["java", "-Xmx512m", "-Djava.awt.headless=true", "-cp", folder, "PixelContractTest", mode])

def main():
    from verify_paged_exports import selftest as paged_observer_selftest
    paged_observer_selftest()
    source = SOURCE.read_text(encoding="utf-8")
    # Each mutant compiles, then passes the SAME unedited basic checker.
    # Only its targeted nontrivial input should expose the defect.
    mutations = [
        ("skip_mask", "result[y * outWidth + x] = 0xff000000;",
         "result[y * outWidth + x] = result[y * outWidth + x];",
         "mask", "mask_exact_black_and_outside_pixels"),
        ("transparent_mask", "result[y * outWidth + x] = 0xff000000;",
         "result[y * outWidth + x] = 0x00000000;",
         "mask", "mask_exact_black_and_outside_pixels"),
        ("ignore_crop_origin", "(crop.top + y) * width + crop.left",
         "y * width", "crop", "crop_nonzero_origin_pixels"),
        ("expose_result", "return pixels.clone();", "return pixels;",
         "ownership", "result_defensive_copy"),
    ]
    with tempfile.TemporaryDirectory(prefix="pocket-pixels-") as temp:
        root = Path(temp)
        output = compile_and_run(root / "baseline", source, "all")
        labels = re.findall(r"^PASS (.+)$", output, re.M)
        summary = re.findall(r"^PIXEL_RESULT (\d+)/(\d+) PASS$", output, re.M)
        assert len(summary) == 1 and summary[0] == (str(len(labels)), str(len(labels)))
        assert len(labels) == len(set(labels)) and len(labels) > 0
        for name, old, new, mode, failure in mutations:
            assert source.count(old) == 1, "Mutation anchor drift: " + name
            mutant = source.replace(old, new, 1)
            assert mutant != source
            folder = root / name
            compile_and_run(folder, mutant, "basic")
            run(["java", "-Xmx512m", "-Djava.awt.headless=true", "-cp", folder,
                 "PixelContractTest", mode], expected_failure=failure)
        print("PIXEL_CONTRACT_EVIDENCE " + json.dumps({
            "status": "PASS", "scope": "JDK_PURE_ARGB_CROP_OPAQUE_MASK_NOT_ANDROID_OR_SHARE",
            "checks": len(labels), "labels": labels, "mutants_rejected": len(mutations),
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "android_codec": "NOT_TESTED", "persistence_ui_share": "NOT_IMPLEMENTED",
            "release_ready": False
        }), flush=True)

ANDROID_TEST = r'''
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
public final class AndroidCodecTest {
 static int checks;
 static void ok(boolean b,String label) {if(!b)throw new AssertionError(label);checks++;System.out.println("CODEC_PASS "+label);}
 interface Action {void run()throws Exception;}
 static byte[] read(File p)throws IOException {ByteArrayOutputStream o=new ByteArrayOutputStream();try(InputStream i=new FileInputStream(p)){byte[] b=new byte[8192];int n;while((n=i.read(b))!=-1)o.write(b,0,n);}return o.toByteArray();}
 static byte[] png(byte[] b,int l,int t,int r,int d,int[][] masks,long budget)throws Exception {
  try {return(byte[])Class.forName("com.supercubegame.pockettodo.ShareExporter").getMethod("png",byte[].class,int.class,int.class,int.class,int.class,int[][].class,long.class).invoke(null,b,l,t,r,d,masks,budget);}
  catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
 }
 static void reject(Action action,String label)throws Exception {boolean bad=false;try{action.run();}catch(IOException|IllegalArgumentException e){bad=true;}ok(bad,label);}
 static void save(File p,byte[] b)throws IOException {try(OutputStream o=new FileOutputStream(p)){o.write(b);}}
 static int shareChecks;
 static void shareOk(boolean b,String name){if(!b)throw new AssertionError(name);shareChecks++;System.out.println("SHARE_PASS "+name);}
 static Object item(String note,String id,String text,byte[] image,String caption,boolean secret)throws Exception{
  return Class.forName("com.supercubegame.pockettodo.ShareExporter$MarkdownItem").getConstructor(String.class,String.class,String.class,byte[].class,String.class,boolean.class).newInstance(note,id,text,image,caption,secret);
 }
 static byte[] share(List<Object> items,Set<String> selected)throws Exception{
  try{return(byte[])Class.forName("com.supercubegame.pockettodo.ShareExporter").getMethod("markdownZip",List.class,Set.class).invoke(null,items,selected);}
  catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
 }
 static void shareReject(Action action,String name)throws Exception{
  boolean bad=false;try{action.run();}catch(IOException|IllegalArgumentException e){bad=true;}shareOk(bad,name);
 }
 static Set<String> keys(String... ids){return new LinkedHashSet<>(Arrays.asList(ids));}
 static Map<String,byte[]> unzip(byte[] bytes)throws Exception{
  Map<String,byte[]> files=new LinkedHashMap<>();
  try(java.util.zip.ZipInputStream z=new java.util.zip.ZipInputStream(new ByteArrayInputStream(bytes))){
   java.util.zip.ZipEntry e;while((e=z.getNextEntry())!=null){ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[1024];int n;while((n=z.read(b))!=-1)out.write(b,0,n);if(files.put(e.getName(),out.toByteArray())!=null)throw new AssertionError("duplicate ZIP member");}
  }return files;
 }
 static void sharing(File root,byte[] source,byte[] redacted)throws Exception{
  byte[] before=redacted.clone();
  Object text=item("n1","t","Visible ![bad](../original.png)\n<img src=\"secret\"> & 中文",null,"",false);
  Object image=item("n2","i",null,redacted,"Selected caption",false);
  Object repeat=item("n2","j",null,redacted,"Repeated caption",false);
  Object hidden=item("n1","p","PRIVATE_NOTE_SECRET",null,"",true);
  Object unselected=item("n1","u",null,source,"UNSELECTED_ORIGINAL_SECRET",false);
  List<Object> items=new ArrayList<>(Arrays.asList(text,image,repeat,hidden,unselected));
  byte[] zip=share(items,keys("n2/j","n1/p","n2/i","n1/t"));
  save(new File(root,"share.zip"),zip);
  Map<String,byte[]> files=unzip(zip);
  shareOk(files.keySet().equals(keys("notes.md","assets/image-1.png")),"exact_selected_zip_members");
  String md=new String(files.get("notes.md"),java.nio.charset.StandardCharsets.UTF_8);
  shareOk(!md.contains("PRIVATE_NOTE_SECRET")&&!md.contains("UNSELECTED_ORIGINAL_SECRET")&&!md.contains("PRIVATE_GPS_SECRET"),"private_and_unselected_text_absent");
  shareOk(md.indexOf("Visible")<md.indexOf("Selected caption")&&md.indexOf("Selected caption")<md.indexOf("Repeated caption")&&md.split("!\\[Image\\]",-1).length==3,"document_order_and_duplicate_references");
  shareOk(!md.contains("<img")&&!md.contains("![bad]")&&md.contains("&lt;img")&&md.contains("中文"),"literal_markdown_html_text");
  Bitmap b=BitmapFactory.decodeByteArray(files.get("assets/image-1.png"),0,files.get("assets/image-1.png").length);
  int[] pixels=new int[12];if(b!=null&&b.getWidth()==4&&b.getHeight()==3)b.getPixels(pixels,0,4,0,0,4,3);
  shareOk(b!=null&&b.getWidth()==4&&b.getHeight()==3&&Arrays.equals(pixels,new int[]{0xff0a141e,0xff000000,0xff000000,0xff0d1a27,0xff112233,0xff000000,0xff000000,0xff000000,0xff183048,0xff19324b,0xff000000,0xff000000}),"share_redaction_pixels_preserved");
  if(b!=null)b.recycle();
  shareOk(Arrays.equals(redacted,before),"share_source_bytes_unchanged");
  Arrays.fill(redacted,(byte)0);items.clear();
  shareOk(Arrays.equals(share(Arrays.asList(text,image,repeat,hidden,unselected),keys("n1/t","n2/i","n2/j","n1/p")),zip),"frozen_input_ownership_and_repeatability");
  shareReject(()->share(Arrays.asList(text),keys()),"empty_selection_refused_not_all");
  shareReject(()->share(Arrays.asList(hidden),keys("n1/p")),"private_only_selection_refused");
  shareReject(()->share(Arrays.asList(text),keys("missing/id")),"unknown_selection_refused");
  shareReject(()->share(Arrays.asList(text,text),keys("n1/t")),"duplicate_identity_refused");
  shareReject(()->share(Arrays.asList(text),null),"null_selection_refused");
  Object broken=item("n3","bad",null,new byte[]{1,2,3},"BROKEN",false);
  shareReject(()->share(Arrays.asList(text,broken),keys("n1/t","n3/bad")),"selected_invalid_image_refuses_entire_export");
  shareOk(unzip(share(Arrays.asList(text,broken),keys("n1/t"))).keySet().equals(keys("notes.md")),"unselected_image_never_decoded_or_packaged");
  Object raw=item("n4","raw",null,source,"Clean reencoding",false);
  byte[] clean=share(Arrays.asList(raw),keys("n4/raw"));save(new File(root,"share-clean.zip"),clean);
  shareOk(!Arrays.equals(unzip(clean).get("assets/image-1.png"),source),"selected_original_is_reencoded_not_copied");
  Object over=item("n4","over",null,read(new File(root,"over.png")),"Large",false);
  shareReject(()->share(Arrays.asList(over),keys("n4/over")),"share_source_budget_retained");
  shareOk(!new String(zip,java.nio.charset.StandardCharsets.ISO_8859_1).contains("original.png"),"no_original_named_zip_member");
  StringBuilder large=new StringBuilder();for(int i=0;i<=262144;i++)large.append('x');
  Object excessive=item("n5","big",large.toString(),null,"",false);
  shareReject(()->share(Arrays.asList(excessive),keys("n5/big")),"share_text_budget_refuses_not_truncates");
  System.out.println("ANDROID_SHARE_RESULT "+shareChecks+"/"+shareChecks+" PASS");
 }
 public static void main(String[] args) {
  try {
   if(args.length==1&&args[0].equals("--diagnostic-selftest"))throw new AssertionError("codec_diagnostic_sentinel");
   verify(args);
  }catch(Throwable failure){
   System.err.println("CODEC_FATAL "+failure.getClass().getName()+": "+failure.getMessage());
   failure.printStackTrace(System.err);System.err.flush();System.out.flush();
   System.exit(1);
  }
 }
 static void verify(String[] args)throws Exception {
  File root=new File(args[0]);ok(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args[1]),"actual_android_api");
  // Loaded from the exact application APK, not a recompiled product test copy.
  ok(Class.forName("com.supercubegame.pockettodo.ShareExporter").getClassLoader()==AndroidCodecTest.class.getClassLoader(),"apk_class_available_in_device_runtime");
  byte[] source=read(new File(root,"source.png")),before=source.clone();
  byte[] result=png(source,2,1,6,4,new int[][]{{1,0,3,2},{2,1,4,3}},12);
  save(new File(root,"derived.png"),result);
  Bitmap decoded=BitmapFactory.decodeByteArray(result,0,result.length);
  ok(decoded!=null&&decoded.getWidth()==4&&decoded.getHeight()==3,"android_output_decodes_at_crop_dimensions");
  int[] expected={0xff0a141e,0xff000000,0xff000000,0xff0d1a27,0xff112233,0xff000000,0xff000000,0xff000000,0xff183048,0xff19324b,0xff000000,0xff000000};
  int[] actual=new int[12];decoded.getPixels(actual,0,4,0,0,4,3);decoded.recycle();
  ok(Arrays.equals(actual,expected),"android_exact_crop_and_opaque_mask_pixels");
  ok(Arrays.equals(source,before),"successful_codec_preserves_original_bytes");
  ok(!Arrays.equals(source,result),"derivative_is_not_original_container");
  byte[] again=png(source,2,1,6,4,new int[][]{{2,1,4,3},{1,0,3,2}},12);
  ok(Arrays.equals(result,again),"same_pixels_repeat_without_accumulating_edits");
  reject(()->png(source,2,1,6,4,new int[][]{{0,0,5,3}},12),"invalid_output_mask_rejected");
  reject(()->png(source,2,1,8,4,new int[0][],12),"out_of_source_crop_rejected");
  reject(()->png(source,2,1,6,4,new int[][]{{0,0,1,1},{1}},12),"late_malformed_mask_rejected");
  reject(()->png(source,2,1,6,4,null,12),"null_masks_rejected");
  reject(()->png(source,2,1,6,4,new int[][]{null},12),"null_mask_row_rejected");
  reject(()->png(source,2,1,6,4,new int[0][],11),"exact_output_budget_enforced");
  reject(()->png(source,2,1,6,4,new int[0][],0),"zero_output_budget_rejected");
  reject(()->png(source,2,1,6,4,new int[0][],1000001),"output_policy_not_relaxed");
  reject(()->png(null,0,0,1,1,new int[0][],1),"null_source_rejected");
  reject(()->png(new byte[0],0,0,1,1,new int[0][],1),"empty_source_rejected");
  reject(()->png(new byte[]{1,2,3,4},0,0,1,1,new int[0][],1),"non_image_rejected");
  reject(()->png(new byte[8*1024*1024+1],0,0,1,1,new int[0][],1),"over_byte_policy_rejected");
  byte[] limit=read(new File(root,"limit.png")),over=read(new File(root,"over.png"));
  save(new File(root,"limit-derived.png"),png(limit,999,999,1000,1000,new int[0][],1));
  ok(true,"exact_android_source_pixel_budget_accepted");
  reject(()->png(over,0,0,1,1,new int[0][],1),"valid_image_over_source_budget_rejected");
  byte[] alpha=read(new File(root,"alpha.png"));
  save(new File(root,"alpha-derived.png"),png(alpha,0,0,2,2,new int[][]{{0,0,2,2}},4));
  ok(true,"transparent_source_mask_encoded");
  byte[] jpeg=read(new File(root,"source.jpg")),jpegBefore=jpeg.clone();
  save(new File(root,"jpeg-derived.png"),png(jpeg,0,0,8,6,new int[][]{{0,0,8,6}},48));
  ok(Arrays.equals(jpeg,jpegBefore),"jpeg_decode_preserves_original_bytes");
  byte[] rotated=read(new File(root,"rotated.jpg"));
  reject(()->png(rotated,0,0,8,6,new int[0][],48),"non_normal_exif_requires_orientation_support");
  byte[] pngExif=read(new File(root,"exif.png"));
  reject(()->png(pngExif,0,0,1,1,new int[0][],1),"png_exif_refused_on_both_platforms");
  byte[] edge=read(new File(root,"edge.png")),wide=read(new File(root,"wide.png"));
  ok(png(edge,2047,0,2048,1,new int[0][],1).length>0,"exact_android_edge_accepted");
  reject(()->png(wide,0,0,1,1,new int[0][],1),"valid_wide_image_rejected");
  ok(Arrays.equals(source,before),"all_rejections_preserve_source_bytes");
  ok(Arrays.equals(result,read(new File(root,"derived.png"))),"later_operations_preserve_earlier_derivative");
  sharing(root,source,result);
  System.out.println("ANDROID_CODEC_RESULT "+checks+"/"+checks+" PASS");
 }
}
'''

HOST_CODEC = r'''
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import javax.imageio.ImageIO;
public final class CodecHostCheck {
 static void need(boolean b,String s){if(!b)throw new AssertionError(s);}
 static void check(Path file,int w,int h,int[] expected)throws Exception {
  BufferedImage image=ImageIO.read(file.toFile());
  need(image!=null&&image.getWidth()==w&&image.getHeight()==h,"host_decode_dimensions");
  need(Arrays.equals(image.getRGB(0,0,w,h,null,0,w),expected),"host_decode_exact_pixels");
  byte[] bytes=Files.readAllBytes(file);
  DataInputStream in=new DataInputStream(new ByteArrayInputStream(bytes));
  need(in.readLong()==0x89504e470d0a1a0aL,"PNG_signature");
  Set<String> allowed=Set.of("IHDR","IDAT","IEND","sRGB","gAMA","cHRM","sBIT");
  boolean end=false;while(!end){int n=in.readInt();need(n>=0&&n<=bytes.length,"chunk_length");byte[] name=new byte[4];in.readFully(name);String kind=new String(name,java.nio.charset.StandardCharsets.US_ASCII);need(allowed.contains(kind),"unexpected_metadata_"+kind);byte[] data=new byte[n];in.readFully(data);in.readInt();end=kind.equals("IEND");}
  need(in.available()==0,"no_trailing_original_bytes");
  need(!new String(bytes,java.nio.charset.StandardCharsets.ISO_8859_1).contains("PRIVATE_GPS_SECRET"),"no_private_marker");
  System.out.println("HOST_CODEC_PASS "+file.getFileName());
 }
 public static void main(String[] args)throws Exception {
  Path root=Paths.get(args[1]);
  if(args[0].equals("fixture")){
   BufferedImage image=new BufferedImage(8,6,BufferedImage.TYPE_INT_RGB);
   for(int y=0;y<6;y++)for(int x=0;x<8;x++)image.setRGB(x,y,0xff345678);
   need(ImageIO.write(image,"jpeg",root.resolve("source.jpg").toFile()),"jpeg_encoder");
   BufferedImage actual=ImageIO.read(root.resolve("source.jpg").toFile());need(actual.getWidth()==8&&actual.getHeight()==6,"jpeg_fixture_real");
  }else{
   check(root.resolve("derived.png"),4,3,new int[]{0xff0a141e,0xff000000,0xff000000,0xff0d1a27,0xff112233,0xff000000,0xff000000,0xff000000,0xff183048,0xff19324b,0xff000000,0xff000000});
   check(root.resolve("limit-derived.png"),1,1,new int[]{0xff2468ac});
   int[] alpha=new int[4];Arrays.fill(alpha,0xff000000);check(root.resolve("alpha-derived.png"),2,2,alpha);
   int[] jpeg=new int[48];Arrays.fill(jpeg,0xff000000);check(root.resolve("jpeg-derived.png"),8,6,jpeg);
  }
 }
}
'''

EXIF_TEST = r'''
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import java.io.*;
import java.lang.reflect.*;
import java.nio.*;
import java.util.*;
public final class AndroidExifTest {
 static int checks;
 static byte[] jpeg;
 static void ok(boolean b,String name){if(!b)throw new AssertionError(name);checks++;System.out.println("EXIF_PASS "+name);}
 static byte[] join(byte[]... pieces)throws Exception{ByteArrayOutputStream o=new ByteArrayOutputStream();for(byte[] p:pieces)o.write(p);return o.toByteArray();}
 static byte[] tiff(boolean le,int... values){
  ByteBuffer b=ByteBuffer.allocate(14+12*values.length).order(le?ByteOrder.LITTLE_ENDIAN:ByteOrder.BIG_ENDIAN);
  b.put((byte)(le?'I':'M')).put((byte)(le?'I':'M')).putShort((short)42).putInt(8).putShort((short)values.length);
  for(int v:values)b.putShort((short)274).putShort((short)3).putInt(1).putShort((short)v).putShort((short)0);
  b.putInt(0);byte[] result=b.array();
  // Independent fixture self-check via ByteBuffer, not the product TIFF reader.
  ByteBuffer read=ByteBuffer.wrap(result).order(le?ByteOrder.LITTLE_ENDIAN:ByteOrder.BIG_ENDIAN);
  if(read.getShort(2)!=42||read.getInt(4)!=8||read.getShort(8)!=values.length)throw new AssertionError("fixture_header");
  for(int i=0;i<values.length;i++)if(read.getShort(10+12*i)!=274||read.getShort(18+12*i)!=values[i])throw new AssertionError("fixture_orientation");
  return result;
 }
 static byte[] image(byte[]... tiffs)throws Exception{
  ByteArrayOutputStream o=new ByteArrayOutputStream();o.write(jpeg,0,2);
  for(byte[] t:tiffs){o.write(255);o.write(225);int n=t.length+8;o.write(n>>>8);o.write(n);o.write(new byte[]{69,120,105,102,0,0});o.write(t);}
  o.write(jpeg,2,jpeg.length-2);return o.toByteArray();
 }
 static void parse(byte[] b)throws Exception{
  Method m=Class.forName("com.supercubegame.pockettodo.ShareExporter").getDeclaredMethod("jpegOrientation",byte[].class);m.setAccessible(true);
  try{m.invoke(null,(Object)b);}catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
 }
 static void accepted(byte[] b,String name)throws Exception{byte[] before=b.clone();parse(b);ok(Arrays.equals(b,before),name);}
 static void rejected(byte[] b,String name)throws Exception{
  byte[] before=b.clone();boolean bad=false;try{parse(b);}catch(IOException e){bad=true;}
  ok(bad&&Arrays.equals(b,before),name);
 }
 static void codec(byte[] b,boolean reject,String name)throws Exception{
  byte[] before=b.clone(),out=null;boolean bad=false;
  Bitmap fixture=BitmapFactory.decodeByteArray(b,0,b.length);
  if(fixture==null||fixture.getWidth()!=8||fixture.getHeight()!=6)throw new AssertionError("fixture_real_jpeg_"+name);
  fixture.recycle();
  try{out=AndroidCodecTest.png(b,0,0,8,6,new int[][]{{0,0,8,6}},48);}catch(IOException e){bad=true;}
  if(reject){ok(bad&&Arrays.equals(b,before),name);return;}
  if(bad||out==null)throw new AssertionError(name);
  Bitmap d=BitmapFactory.decodeByteArray(out,0,out.length);
  boolean pixels=d!=null&&d.getWidth()==8&&d.getHeight()==6;
  if(pixels){int[] p=new int[48];d.getPixels(p,0,8,0,0,8,6);for(int v:p)if(v!=0xff000000)pixels=false;}
  if(d!=null)d.recycle();ok(pixels&&Arrays.equals(b,before),name);
 }
 static void basic()throws Exception{
  accepted(jpeg,"parser_no_exif_accepted");
  accepted(image(tiff(true,1)),"parser_little_normal_accepted");
  accepted(image(tiff(false,1)),"parser_big_normal_accepted");
  codec(jpeg,false,"codec_no_exif_exact_black");
  codec(image(tiff(true,1)),false,"codec_little_normal_exact_black");
  codec(image(tiff(false,1)),false,"codec_big_normal_exact_black");
 }
 static void rotated()throws Exception{
  for(boolean le:new boolean[]{true,false})for(int v=2;v<=8;v++){
   rejected(image(tiff(le,v)),"parser_orientation_"+(le?"II":"MM")+"_"+v);
   codec(image(tiff(le,v)),true,"codec_orientation_"+(le?"II":"MM")+"_"+v);
  }
 }
 static void duplicate()throws Exception{
  rejected(image(tiff(true,1),tiff(true,1)),"parser_duplicate_exif_rejected");
 }
 static void all()throws Exception{
  basic();rotated();duplicate();
  for(boolean le:new boolean[]{true,false}){
   String e=le?"II":"MM";ByteOrder order=le?ByteOrder.LITTLE_ENDIAN:ByteOrder.BIG_ENDIAN;
   rejected(image(tiff(le,0)),"parser_undefined_"+e+"_rejected");
   rejected(image(tiff(le,9)),"parser_invalid_value_"+e+"_rejected");
   rejected(image(tiff(le)),"parser_missing_orientation_"+e+"_rejected");
   rejected(image(tiff(le,1,1)),"parser_duplicate_field_"+e+"_rejected");
   byte[] type=tiff(le,1);ByteBuffer.wrap(type).order(order).putShort(12,(short)4);
   rejected(image(type),"parser_wrong_type_"+e+"_rejected");
   byte[] count=tiff(le,1);ByteBuffer.wrap(count).order(order).putInt(14,2);
   rejected(image(count),"parser_wrong_count_"+e+"_rejected");
   byte[] zero=tiff(le,1);ByteBuffer.wrap(zero).order(order).putInt(4,0);
   rejected(image(zero),"parser_zero_offset_"+e+"_rejected");
   byte[] huge=tiff(le,1);ByteBuffer.wrap(huge).order(order).putInt(4,-1);
   rejected(image(huge),"parser_unsigned_offset_"+e+"_rejected");
   byte[] entries=tiff(le,1);ByteBuffer.wrap(entries).order(order).putShort(8,(short)65535);
   rejected(image(entries),"parser_truncated_entries_"+e+"_rejected");
   rejected(image(Arrays.copyOf(tiff(le,1),7)),"parser_short_header_"+e+"_rejected");
   rejected(image(Arrays.copyOf(tiff(le,1),25)),"parser_missing_ifd_tail_"+e+"_rejected");
   byte[] magic=tiff(le,1);ByteBuffer.wrap(magic).order(order).putShort(2,(short)43);
   rejected(image(magic),"parser_wrong_magic_"+e+"_rejected");
  }
  byte[] endian=tiff(true,1);endian[0]=88;rejected(image(endian),"parser_invalid_byte_order_rejected");
  rejected(new byte[]{(byte)255,(byte)216,(byte)255},"parser_truncated_marker_rejected");
  rejected(new byte[]{(byte)255,(byte)216,(byte)255,(byte)225,0,1},"parser_short_segment_rejected");
  rejected(new byte[]{(byte)255,(byte)216,(byte)255,(byte)225,127,(byte)255},"parser_segment_outside_bytes_rejected");
 }
 public static void main(String[] args){
  try{
   jpeg=AndroidCodecTest.read(new File(args[0],"source.jpg"));
   if(args[1].equals("basic"))basic();else if(args[1].equals("rotated"))rotated();else if(args[1].equals("duplicate"))duplicate();else if(args[1].equals("all"))all();else throw new AssertionError("unknown mode");
   System.out.println("EXIF_RESULT "+checks+"/"+checks+" PASS");
  }catch(Throwable failure){failure.printStackTrace(System.err);System.err.flush();System.out.flush();System.exit(1);}
 }
}
'''

def exif_boundaries(folder, classes, android, prefix, remote, gate):
    """APK parser/codec coverage, then explicitly separate recompiled mutant jars."""
    import os
    source_path=ROOT/"src/main/java/com/supercubegame/pockettodo/ShareExporter.java"
    source=source_path.read_text(encoding="utf-8")
    test=folder/"AndroidExifTest.java";test.write_text(EXIF_TEST,encoding="utf-8")
    run(["javac","-encoding","UTF-8","--release","8","-cp",str(android)+os.pathsep+str(classes),"-d",classes,test])
    def dex_and_push(where,name):
        jar=where/(name+".jar")
        run([gate.SDK/"build-tools/35.0.0/d8","--min-api","26","--lib",android,"--output",jar,*sorted(where.rglob("*.class"))])
        run([*prefix,"push",jar,remote+"/"+name+".jar"])
        assert subprocess.check_output([*prefix,"exec-out","cat",remote+"/"+name+".jar"],timeout=30)==jar.read_bytes()
        return remote+"/"+name+".jar"
    test_jar=dex_and_push(classes,"exif-tests")
    def command(extra,mode):
        cp=test_jar+(":"+extra if extra else "")+":"+remote+"/app.apk"
        return [*prefix,"shell","CLASSPATH="+cp,"app_process","/system/bin","AndroidExifTest",remote,mode]
    output=run(command(None,"all"))
    labels=re.findall(r"^EXIF_PASS (.+)$",output,re.M)
    summary=re.findall(r"^EXIF_RESULT (\d+)/(\d+) PASS$",output,re.M)
    assert len(labels)==63 and len(set(labels))==63 and summary==[("63","63")],output
    mutations=(
        ("allow_rotated","if(u16(b,q+8,little)!=1)","if(u16(b,q+8,little)<1)","rotated","parser_orientation_II_2"),
        ("allow_duplicate","if(++exifCount!=1)","if(++exifCount<1)","duplicate","parser_duplicate_exif_rejected"),
    )
    for name,old,new,mode,failure in mutations:
        assert source.count(old)==1,"EXIF mutation anchor drift: "+name
        changed=source.replace(old,new,1);assert changed!=source
        target=folder/name;target.mkdir(exist_ok=True)
        java=target/"ShareExporter.java";java.write_text(changed,encoding="utf-8")
        run(["javac","-encoding","UTF-8","--release","8","-cp",android,"-d",target,java,SOURCE])
        mutant_jar=dex_and_push(target,name)
        positive=run(command(mutant_jar,"basic"))
        assert "EXIF_RESULT 6/6 PASS" in positive
        run(command(mutant_jar,mode),expected_failure=failure)
    return {"scope":"ACTUAL_APK_ANDROID_PRIVATE_PARSER_AND_PUBLIC_CODEC",
            "checks":len(labels),"labels":labels,"mutants_rejected":len(mutations),
            "mutant_scope":"SEPARATE_RECOMPILED_PRODUCT_JARS_NOT_DELIVERY_APK",
            "source_sha256":hashlib.sha256(source.encode()).hexdigest()}

def android_codec(adb, gate):
    """Run APK code under real Android app_process, no product hidden entrypoints.

    This is a codec/API check as shell, NOT an app sandbox/lifecycle/UI acceptance.
    The outer runner still executes all existing DB and native UI suites exactly once.
    """
    import os
    import struct
    import zlib
    folder = ROOT / "build/codec-contract"
    folder.mkdir(parents=True, exist_ok=True)
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    def fixture(name, width, height, row):
        raw = b"".join(b"\0" + row(y) for y in range(height))
        data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        data += chunk(b"tEXt", b"Comment\0PRIVATE_GPS_SECRET")
        data += chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
        (folder / name).write_bytes(data)
        return data
    fixture("source.png", 7, 5, lambda y: b"".join(bytes((i, i*2, i*3, 255)) for i in range(y*7+1,y*7+8)))
    fixture("alpha.png", 2, 2, lambda y: bytes((10,20,30,0,40,50,60,64)))
    for name, h in (("limit.png",1000),("over.png",1001)):
        fixture(name,1000,h,lambda y: bytes((36,104,172,255))*1000)
    host = folder / "CodecHostCheck.java";host.write_text(HOST_CODEC,encoding="utf-8")
    run(["javac","-encoding","UTF-8","-d",folder,host])
    run(["java","-Djava.awt.headless=true","-cp",folder,"CodecHostCheck","fixture",folder])
    jpeg=(folder/"source.jpg").read_bytes()
    exif=b"Exif\0\0"+b"II"+struct.pack("<H",42)+struct.pack("<I",8)+struct.pack("<H",1)+struct.pack("<HHI",0x112,3,1)+struct.pack("<H",6)+b"\0\0"+struct.pack("<I",0)
    (folder/"rotated.jpg").write_bytes(jpeg[:2]+b"\xff\xe1"+struct.pack(">H",len(exif)+2)+exif+jpeg[2:])
    base=(folder/"source.png").read_bytes()
    (folder/"exif.png").write_bytes(base[:-12]+chunk(b"eXIf",exif[6:])+base[-12:])
    fixture("edge.png",2048,1,lambda y:bytes((36,104,172,255))*2048)
    fixture("wide.png",2049,1,lambda y:bytes((36,104,172,255))*2049)
    test=folder/"AndroidCodecTest.java";test.write_text(ANDROID_TEST,encoding="utf-8")
    classes=folder/"classes";classes.mkdir(exist_ok=True)
    android=gate.SDK/"platforms/android-35/android.jar"
    run(["javac","-encoding","UTF-8","--release","8","-cp",android,"-d",classes,test])
    dex=folder/"codec-test.jar"
    run([gate.SDK/"build-tools/35.0.0/d8","--min-api","26","--lib",android,"--output",dex,*sorted(classes.glob("*.class"))])
    apks=list((ROOT/"build/outputs/apk/debug").glob("*.apk"));assert len(apks)==1
    original_apk=apks[0].read_bytes()
    remote="/data/local/tmp/pocket-codec-contract"
    prefix=[str(adb),"-s",gate.SERIAL]
    run([*prefix,"shell","mkdir","-p",remote])
    run([*prefix,"push",apks[0],remote+"/app.apk"])
    run([*prefix,"push",dex,remote+"/test.jar"])
    sources=("source.png","alpha.png","limit.png","over.png","source.jpg","rotated.jpg","exif.png","edge.png","wide.png")
    for name in sources:run([*prefix,"push",folder/name,remote+"/"+name])
    command=[*prefix,"shell","CLASSPATH="+remote+"/test.jar:"+remote+"/app.apk","app_process","/system/bin","AndroidCodecTest"]
    # Prove an assertion becomes visible text AND exit 1, not a silent Android kill.
    probe=subprocess.run([*command,"--diagnostic-selftest"],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90)
    assert probe.returncode==1 and "CODEC_FATAL java.lang.AssertionError: codec_diagnostic_sentinel" in probe.stdout,probe.stdout
    print("CODEC_DIAGNOSTIC_SELFTEST PASS exit=1 sentinel_stack_visible",flush=True)
    try:
        text=run([*command,remote,str(gate.API)])
    except Exception:
        # Only disposable synthetic CI data. Capture before emulator cleanup; never retry.
        try:
            diagnostic=subprocess.run([*prefix,"logcat","-d","-t","120","-v","brief"],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
            print("CODEC_FAILURE_LOGCAT_BEGIN rc="+str(diagnostic.returncode),flush=True)
            print(diagnostic.stdout[-12000:],flush=True)
            print("CODEC_FAILURE_LOGCAT_END",flush=True)
        except Exception as diagnostic_error:
            print("CODEC_FAILURE_LOGCAT_UNAVAILABLE "+repr(diagnostic_error),flush=True)
        raise
    labels=re.findall(r"^CODEC_PASS (.+)$",text,re.M)
    summary=re.findall(r"^ANDROID_CODEC_RESULT (\d+)/(\d+) PASS$",text,re.M)
    assert len(summary)==1 and summary[0]==(str(len(labels)),str(len(labels))) and len(labels)==29 and len(set(labels))==29
    share_labels=re.findall(r"^SHARE_PASS (.+)$",text,re.M)
    assert len(share_labels)==18 and len(set(share_labels))==18
    assert re.findall(r"^ANDROID_SHARE_RESULT (\d+)/(\d+) PASS$",text,re.M)==[("18","18")]
    # Independent host ZIP membership, UTF-8 text and PNG pixels, not exporter readback.
    import zipfile
    for archive in ("share.zip","share-clean.zip"):
        run([*prefix,"pull",remote+"/"+archive,folder/archive])
        with zipfile.ZipFile(folder/archive) as z:
            assert z.namelist()==["notes.md","assets/image-1.png"]
            md=z.read("notes.md").decode("utf-8")
            assert not any(s in md for s in ("PRIVATE_NOTE_SECRET","UNSELECTED_ORIGINAL_SECRET","<img","![bad]"))
            asset=z.read("assets/image-1.png")
            assert b"PRIVATE_GPS_SECRET" not in asset
            if archive=="share.zip":
                (folder/"share-derived.png").write_bytes(asset)
            else:
                assert asset!=(folder/"source.png").read_bytes()
                (folder/"share-clean.png").write_bytes(asset)
    share_host=folder/"ShareHost.java"
    share_host.write_text('''import java.nio.file.*; public class ShareHost {
      public static void main(String[] a)throws Exception {
        Path p=Paths.get(a[0]); CodecHostCheck.check(p.resolve("share-derived.png"),4,3,new int[]{0xff0a141e,0xff000000,0xff000000,0xff0d1a27,0xff112233,0xff000000,0xff000000,0xff000000,0xff183048,0xff19324b,0xff000000,0xff000000});
        int[] source=new int[35];for(int i=0;i<35;i++)source[i]=0xff000000|((i+1)*0x010203);
        CodecHostCheck.check(p.resolve("share-clean.png"),7,5,source);
      }}''',encoding="utf-8")
    run(["javac","-encoding","UTF-8","-cp",folder,"-d",folder,share_host])
    share_host_result=run(["java","-Djava.awt.headless=true","-cp",folder,"ShareHost",folder])
    assert re.findall(r"^HOST_CODEC_PASS (.+)$",share_host_result,re.M)==["share-derived.png","share-clean.png"]
    for name in sources:
        actual=subprocess.check_output([*prefix,"exec-out","cat",remote+"/"+name],timeout=30)
        assert actual==(folder/name).read_bytes(),"device fixture/source changed: "+name
    files=("derived.png","limit-derived.png","alpha-derived.png","jpeg-derived.png")
    for name in files:run([*prefix,"pull",remote+"/"+name,folder/name])
    host_result=run(["java","-Djava.awt.headless=true","-cp",folder,"CodecHostCheck","check",folder])
    assert re.findall(r"^HOST_CODEC_PASS (.+)$",host_result,re.M)==list(files)
    # The SAME independent host reader first passed genuine outputs. Each mutation
    # remains a readable file, but breaks one privacy/pixel boundary intentionally.
    import shutil
    original=(folder/"derived.png").read_bytes()
    wrong=fixture("wrong-pixels.png",4,3,lambda y:bytes((255,255,255,255))*4)
    # Strip fixture metadata so the pixel mutant differs on pixels, not metadata.
    marker=chunk(b"tEXt",b"Comment\0PRIVATE_GPS_SECRET")
    wrong=wrong.replace(marker,b"")
    mutations=(("wrong_pixels",wrong,"host_decode_exact_pixels"),
               ("metadata",original[:-12]+marker+original[-12:],"unexpected_metadata_tEXt"),
               ("trailing_original",original+(folder/"source.png").read_bytes(),"no_trailing_original_bytes"),
               ("original_substitution",(folder/"source.png").read_bytes(),"host_decode_dimensions"))
    for name,bad,label in mutations:
        mutant=folder/name;mutant.mkdir(exist_ok=True)
        for item in files:shutil.copyfile(folder/item,mutant/item)
        (mutant/"derived.png").write_bytes(bad)
        run(["java","-Djava.awt.headless=true","-cp",folder,"CodecHostCheck","check",mutant],expected_failure=label)
    assert apks[0].read_bytes()==original_apk
    assert subprocess.check_output([*prefix,"exec-out","cat",remote+"/app.apk"],timeout=30)==original_apk
    exif_report=exif_boundaries(folder,classes,android,prefix,remote,gate)
    from verify_paged_exports import verify as verify_paged
    paged_report=verify_paged(folder,classes,android,prefix,remote,gate)
    assert apks[0].read_bytes()==original_apk
    assert subprocess.check_output([*prefix,"exec-out","cat",remote+"/app.apk"],timeout=30)==original_apk
    report={"commit":os.environ["GITHUB_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],
            "api":gate.API,"status":"PASS","scope":"ANDROID_APK_CODEC_SHELL_NOT_APP_UI_OR_PERSISTENCE",
            "apk_sha256":hashlib.sha256(original_apk).hexdigest(),"checks":len(labels),"labels":labels,
            "independent_host_decodes":list(files),"original_files_unchanged":True,
            "host_negative_controls":len(mutations),"device_apk_readback":"EXACT_BYTES",
            "output_metadata":"PNG_CHUNK_ALLOWLIST_NO_TEXT_EXIF_TRAILING_BYTES",
            "exif_boundaries":exif_report,"release_ready":False}
    report["paged_exports"]=paged_report
    report["markdown_share"]={"status":"PASS","checks":18,"labels":share_labels,
                             "independent_host_png_checks":2,"scope":"READ_ONLY_ZIP_BACKEND_NOT_UI_STALE_PREVIEW_OR_RECEIVER"}
    out=ROOT/"native-ui";out.mkdir(exist_ok=True)
    (out/"codec-result.json").write_text(json.dumps(report,indent=2)+"\n")
    print("ANDROID_CODEC_EVIDENCE "+json.dumps(report),flush=True)

def android_main():
    # Explicit composition: call the untouched DB runner, then codec checks, then
    # emulator_gate.main continues its untouched native UI runner and shutdown.
    import emulator_gate as gate
    original=gate.verify_database
    def database_and_codec(adb):
        original(adb)
        android_codec(adb,gate)
    gate.verify_database=database_and_codec
    gate.main()

if __name__ == "__main__":
    import sys
    if sys.argv[1:]==["android"]:android_main()
    elif not sys.argv[1:]:main()
    else:raise SystemExit("usage: verify_exports.py [android]")
