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

if __name__ == "__main__":
    main()
