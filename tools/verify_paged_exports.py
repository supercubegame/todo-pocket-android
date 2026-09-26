#!/usr/bin/env python3
"""Actual APK pagination API + independent Poppler/PNG checks. NOT app UI or SAF."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

JAVA = r'''
import java.io.*;
import java.lang.reflect.*;
import java.util.*;
public final class PagedContractTest {
 static int checks;
 static Class<?> renderer,block,format;
 static void ok(boolean value,String label){if(!value)throw new AssertionError(label);checks++;System.out.println("PAGED_PASS "+label);}
 interface Action{void run()throws Exception;}
 static void reject(Action action,String label)throws Exception{
  boolean failed=false;try{action.run();}catch(IOException|IllegalArgumentException e){failed=true;}ok(failed,label);
 }
 static Set<String> keys(String... s){return new LinkedHashSet<>(Arrays.asList(s));}
 static Object block(String note,String id,String text,byte[] image,String caption,boolean secret)throws Exception{
  return block.getConstructor(String.class,String.class,String.class,byte[].class,String.class,boolean.class)
   .newInstance(note,id,text,image,caption,secret);
 }
 @SuppressWarnings({"rawtypes","unchecked"})
 static Object render(List<Object> blocks,Set<String> selected,String kind)throws Exception{
  try{return renderer.getMethod("render",List.class,Set.class,format).invoke(null,blocks,selected,Enum.valueOf((Class)format,kind));}
  catch(InvocationTargetException e){if(e.getCause() instanceof Exception)throw(Exception)e.getCause();throw e;}
 }
 static byte[] bytes(Object result)throws Exception{return(byte[])result.getClass().getMethod("bytes").invoke(result);}
 static int pages(Object result)throws Exception{return result.getClass().getField("pages").getInt(result);}
 static void write(File root,String name,Object result)throws Exception{
  AndroidCodecTest.save(new File(root,name),bytes(result));
 }
 public static void main(String[] args){
  try{
   File root=new File(args[0]);
   renderer=Class.forName("com.supercubegame.pockettodo.PagedNoteRenderer");
   block=Class.forName("com.supercubegame.pockettodo.PagedNoteRenderer$Block");
   format=Class.forName("com.supercubegame.pockettodo.PagedNoteRenderer$Format");
   ok(android.os.Build.VERSION.SDK_INT==Integer.parseInt(args[1]),"actual_api");
   byte[] image=AndroidCodecTest.read(new File(root,"derived.png")),original=image.clone();
   Object picture=block("n","i",null,image,"CAPTION_END",false);
   Arrays.fill(image,(byte)0);
   StringBuilder text=new StringBuilder("BEGIN_SELECTED\n");
   for(int i=0;i<90;i++)text.append(String.format(java.util.Locale.ROOT,"ROW%03d selected text\n",i));
   text.append("END_SELECTED\n中文说明");
   Object prose=block("n","t",text.toString(),null,"",false);
   Object hidden=block("n","p","PRIVATE_PAGED_SECRET",null,"",true);
   Object badPrivate=block("n","q",null,new byte[]{1,2,3},"PRIVATE_IMAGE_SECRET",true);
   Object unwanted=block("other","t","UNSELECTED_PAGED_SECRET",null,"",false);
   List<Object> input=new ArrayList<>(Arrays.asList(prose,picture,hidden,badPrivate,unwanted));
   for(String kind:new String[]{"PDF","PNG_ZIP"}){
    Object result=render(input,keys("n/i","n/t","n/p","n/q"),kind);
    int pageCount=pages(result);
    ok(pageCount>=3&&pageCount<=5,"multiple_pages_"+kind);
    write(root,kind.equals("PDF")?"paged.pdf":"paged.zip",result);
    byte[] first=bytes(result);byte value=first[0];first[0]^=1;
    ok(bytes(result)[0]==value,"result_ownership_"+kind);
    Object filtered=render(Arrays.asList(prose,picture),keys("n/t","n/i"),kind);
    // PDF may contain timestamps; page pixels/text are compared independently below.
    ok(pages(filtered)==pageCount,"excluded_blocks_do_not_add_pages_"+kind);
    write(root,kind.equals("PDF")?"filtered.pdf":"filtered.zip",filtered);
    Object only=render(Arrays.asList(picture),keys("n/i"),kind);
    ok(pages(only)==1,"single_page_"+kind);
    write(root,kind.equals("PDF")?"picture.pdf":"picture.zip",only);
    reject(()->render(input,keys(),kind),"empty_selection_"+kind);
    reject(()->render(input,keys("missing/id"),kind),"unknown_selection_"+kind);
    reject(()->render(input,keys("n/p","n/q"),kind),"private_only_"+kind);
    reject(()->render(Arrays.asList(prose,prose),keys("n/t"),kind),"duplicate_identity_"+kind);
    Object broken=block("n","broken",null,new byte[]{1,2,3},"",false);
    reject(()->render(Arrays.asList(prose,broken),keys("n/t","n/broken"),kind),"selected_bad_image_"+kind);
    ok(pages(render(Arrays.asList(picture,broken),keys("n/i"),kind))==1,"unselected_bad_image_ignored_"+kind);
    Object over=block("n","large",null,AndroidCodecTest.read(new File(root,"over.png")),"",false);
    reject(()->render(Arrays.asList(over),keys("n/large"),kind),"source_pixel_budget_"+kind);
    Object invalid=block("n","invalid","bad\u0001",null,"",false);
    reject(()->render(Arrays.asList(invalid),keys("n/invalid"),kind),"invalid_text_"+kind);
    StringBuilder huge=new StringBuilder();for(int i=0;i<3000;i++)huge.append("line\n");
    Object tooMany=block("n","long",huge.toString(),null,"",false);
    reject(()->render(Arrays.asList(tooMany),keys("n/long"),kind),"page_limit_refuses_not_truncates_"+kind);
   }
   ok(Arrays.equals(original,AndroidCodecTest.read(new File(root,"derived.png"))),"source_file_unchanged");
   Object empty=block("n","empty","",null,"",false);
   reject(()->render(Arrays.asList(empty),keys("n/empty"),"PDF"),"blank_document_rejected");
   if(checks!=29)throw new AssertionError("coverage_count_"+checks);
   System.out.println("PAGED_RESULT 29/29 PASS BACKEND_NOT_NATIVE_UI_SAF_OR_RECEIVER");
  }catch(Throwable e){e.printStackTrace(System.err);System.err.flush();System.out.flush();System.exit(1);}
 }
}
'''

HOST = r'''
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import javax.imageio.ImageIO;
public final class PagedHostCheck {
 static void need(boolean v,String s){if(!v)throw new AssertionError(s);}
 public static void main(String[] a)throws Exception{
  BufferedImage image=ImageIO.read(new File(a[0]));
  need(image!=null&&image.getWidth()==595&&image.getHeight()==842,"page_dimensions");
  need(image.getRGB(0,0)==0xffffffff&&image.getRGB(594,841)==0xffffffff,"white_page");
  if(a[1].equals("picture")){
   int[] expected={0xff0a141e,0xff000000,0xff000000,0xff0d1a27,0xff112233,0xff000000,0xff000000,0xff000000,0xff183048,0xff19324b,0xff000000,0xff000000};
   need(Arrays.equals(image.getRGB(36,36,4,3,null,0,4),expected),"current_only_exact_crop_mask");
  }else{
   int count=0;for(int y=36;y<806;y++)for(int x=36;x<559;x++)if(image.getRGB(x,y)!=0xffffffff)count++;
   need(count>0,"page_not_empty");
  }
  System.out.println("PAGED_HOST_PASS");
 }
}
'''

def run(args,timeout=90):
    p=subprocess.run(list(map(str,args)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    print(p.stdout,flush=True)
    if p.returncode:raise RuntimeError("Paged command failed: "+str(args)+"\n"+p.stdout[-6000:])
    return p.stdout

def text_check(text):
    assert not any(s in text for s in ("PRIVATE_PAGED_SECRET","PRIVATE_IMAGE_SECRET","UNSELECTED_PAGED_SECRET"))
    assert text.count("BEGIN_SELECTED")==text.count("END_SELECTED")==text.count("CAPTION_END")==1
    rows=re.findall(r"ROW\d{3}",text)
    assert rows==["ROW%03d"%i for i in range(90)],"PDF row loss/duplication/order"
    assert text.index("BEGIN_SELECTED")<text.index("ROW000")<text.index("ROW089")<text.index("END_SELECTED")<text.index("CAPTION_END")
    assert "中文说明" in text.replace(" ","").replace("\n",""),"Chinese PDF text missing"

def selftest():
    good="BEGIN_SELECTED\n"+"\n".join("ROW%03d"%i for i in range(90))+"\nEND_SELECTED\n中文说明\nCAPTION_END"
    text_check(good)
    bad=(good.replace("ROW050",""),good.replace("ROW050","ROW049"),good+"PRIVATE_PAGED_SECRET",
         good.replace("中文说明",""),good.replace("ROW000","ROW999"))
    for value in bad:
        try:text_check(value)
        except AssertionError:continue
        raise AssertionError("PDF observer accepted corrupt text")
    print("PAGED_TEXT_OBSERVER 1 positive 5 negatives PASS NOT_PDF_EXECUTION",flush=True)

def verify(folder,classes,android,prefix,remote,gate):
    """Called inside the existing codec job; failures propagate to its exit status."""
    selftest()
    # Independent PDF parser/rasterizer. Install only in disposable CI when absent.
    if not all(shutil.which(x) for x in ("pdftotext","pdftoppm","pdfinfo")):
        run(["sudo","apt-get","update"],timeout=240)
        run(["sudo","apt-get","install","-y","poppler-utils"],timeout=240)
    java=folder/"PagedContractTest.java";java.write_text(JAVA,encoding="utf-8")
    run(["javac","--release","8","-encoding","UTF-8","-cp",str(android)+os.pathsep+str(classes),"-d",classes,java])
    jar=folder/"paged-tests.jar"
    run([gate.SDK/"build-tools/35.0.0/d8","--min-api","26","--lib",android,"--output",jar,*sorted(classes.rglob("*.class"))])
    run([*prefix,"push",jar,remote+"/paged-tests.jar"])
    assert subprocess.check_output([*prefix,"exec-out","cat",remote+"/paged-tests.jar"],timeout=30)==jar.read_bytes()
    output=run([*prefix,"shell","CLASSPATH="+remote+"/paged-tests.jar:"+remote+"/app.apk",
                "app_process","/system/bin","PagedContractTest",remote,str(gate.API)],timeout=180)
    labels=re.findall(r"^PAGED_PASS (.+)$",output,re.M)
    assert len(labels)==len(set(labels))==29 and "PAGED_RESULT 29/29 PASS" in output
    host=folder/"PagedHostCheck.java";host.write_text(HOST,encoding="utf-8")
    run(["javac","-encoding","UTF-8","-d",folder,host])
    def check_image(file,mode):
        return run(["java","-Djava.awt.headless=true","-cp",folder,"PagedHostCheck",file,mode])
    evidence={}
    for stem in ("paged","filtered","picture"):
        for ext in ("pdf","zip"):run([*prefix,"pull",remote+"/"+stem+"."+ext,folder/(stem+"."+ext)])
        info=run(["pdfinfo",folder/(stem+".pdf")])
        match=re.search(r"^Pages:\s+(\d+)",info,re.M);assert match,info
        pages=int(match[1]);assert pages==1 if stem=="picture" else 3<=pages<=5
        run(["pdftotext","-enc","UTF-8",folder/(stem+".pdf"),folder/(stem+".txt")])
        text=(folder/(stem+".txt")).read_text()
        if stem!="picture":text_check(text)
        else:assert text.count("CAPTION_END")==1 and "ROW" not in text
        run(["pdftoppm","-r","72","-png",folder/(stem+".pdf"),folder/(stem+"-pdf")])
        rendered=sorted(folder.glob(stem+"-pdf-*.png"));assert len(rendered)==pages
        for file in rendered:check_image(file,"picture" if stem=="picture" else "text")
        with zipfile.ZipFile(folder/(stem+".zip")) as archive:
            names=archive.namelist()
            assert names==["pages/page-%03d.png"%i for i in range(1,pages+1)],"PNG page set/order"
            assert sum(e.file_size for e in archive.infolist())<=16777216
            for i,name in enumerate(names):
                data=archive.read(name);assert b"PRIVATE_GPS_SECRET" not in data
                file=folder/("%s-png-%03d.png"%(stem,i+1));file.write_bytes(data)
                check_image(file,"picture" if stem=="picture" else "text")
        evidence[stem]={"pages":pages,"pdf_sha256":hashlib.sha256((folder/(stem+".pdf")).read_bytes()).hexdigest(),
                        "zip_sha256":hashlib.sha256((folder/(stem+".zip")).read_bytes()).hexdigest()}
    assert (folder/"paged.txt").read_bytes()==(folder/"filtered.txt").read_bytes(),"excluded content affected PDF text"
    assert (folder/"paged.zip").read_bytes()==(folder/"filtered.zip").read_bytes(),"excluded content affected PNG pages"
    for a,b in zip(sorted(folder.glob("paged-pdf-*.png")),sorted(folder.glob("filtered-pdf-*.png"))):
        assert a.read_bytes()==b.read_bytes(),"excluded content affected PDF pixels"
    report={"commit":os.environ["GITHUB_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],"api":gate.API,
            "status":"PASS","scope":"APK_PAGED_BACKEND_POPPLER_AND_JDK_NOT_UI_SAF_RECEIVER",
            "checks":29,"labels":labels,"independent_outputs":evidence,"text_observer_negative_controls":5,
            "release_ready":False}
    target=gate.ROOT/"native-ui" if hasattr(gate,"ROOT") else Path("native-ui")
    target.mkdir(exist_ok=True)
    (target/"paged-result.json").write_text(json.dumps(report,indent=2)+"\n")
    print("PAGED_EXPORT_EVIDENCE "+json.dumps(report),flush=True)
    return report

if __name__=="__main__":selftest()
