package com.supercubegame.pockettodo;

import android.app.Activity;
import android.os.Bundle;

/** Isolated native v1.2 workbench. Does not read or overwrite v1.0/v1.1 storage. */
public final class MainActivity extends Activity {
    private TodayScreen screen;
    @Override public void onCreate(Bundle saved){super.onCreate(saved);screen=new TodayScreen(this);screen.show(saved);}
    @Override protected void onSaveInstanceState(Bundle out){if(screen!=null)screen.save(out);super.onSaveInstanceState(out);}
    @Override public void onBackPressed(){if(screen==null||!screen.back())super.onBackPressed();}
    @Override protected void onDestroy(){if(screen!=null)screen.close();super.onDestroy();}
}
