package com.supercubegame.pockettodo;

import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Outbound intent only. The UI must consume fresh explicit consent; URI generation must use
 * the app's non-exported exact-URI provider limited to approved-exports under private cache.
 * No URI from incoming intents, source media, the database or user-supplied documents here. */
final class PagedShareIntent {
    static Intent chooser(String packageName,String mime,List<Uri> ready) {
        if(packageName==null||packageName.isEmpty()||ready==null)throw new IllegalArgumentException("missing export identity");
        boolean pdf="application/pdf".equals(mime);List<Uri> input=new ArrayList<>(ready);
        if(input.isEmpty()||input.size()>64||(pdf&&input.size()!=1)||(!pdf&&!"image/png".equals(mime)))throw new IllegalArgumentException("invalid export MIME/count");
        String authority=packageName+".exports",session=null;ArrayList<Uri> streams=new ArrayList<>(input.size());
        for(int i=0;i<input.size();i++){
            Uri u=input.get(i);
            if(u==null||!"content".equals(u.getScheme())||!authority.equals(u.getEncodedAuthority())||u.getEncodedQuery()!=null||u.getEncodedFragment()!=null)throw new IllegalArgumentException("non-export URI");
            String raw=u.getEncodedPath();String[] s=raw==null?new String[0]:raw.split("/",-1);
            if(s.length!=4||!s[0].isEmpty()||!s[1].equals("exports")||!s[2].matches("export-[0-9A-Za-z_-]{1,80}"))throw new IllegalArgumentException("non-export path");
            if(i==0)session=s[2];
            String name=pdf?"PocketTodo-notes.pdf":String.format(Locale.ROOT,"page-%03d.png",i+1);
            if(!session.equals(s[2])||!name.equals(s[3]))throw new IllegalArgumentException("wrong export session, document or order");
            streams.add(u);
        }
        boolean one=streams.size()==1;
        Intent target=new Intent(one?Intent.ACTION_SEND:Intent.ACTION_SEND_MULTIPLE).setType(mime);
        if(one)target.putExtra(Intent.EXTRA_STREAM,streams.get(0));else target.putParcelableArrayListExtra(Intent.EXTRA_STREAM,streams);
        ClipData clips=new ClipData("口袋待办导出",new String[]{mime},new ClipData.Item(streams.get(0)));
        for(int i=1;i<streams.size();i++)clips.addItem(new ClipData.Item(streams.get(i)));
        target.setClipData(clips);target.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        Intent chooser=Intent.createChooser(target,"发送到其他应用");chooser.setClipData(clips);chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);return chooser;
    }
}
