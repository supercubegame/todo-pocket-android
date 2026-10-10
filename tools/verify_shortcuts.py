#!/usr/bin/env python3
"""Opt-in schema4 storage gates. No UI activation, no APK release, no retry."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "src/main/java/com/supercubegame/pockettodo/Schema4Store.java"
DEVICE = ROOT / "src/androidTest/java/com/supercubegame/pockettodo/Schema4DeviceTest.java"
PACKAGE = "com.supercubegame.pockettodo.v12.preview"
SCOPE = "OPT_IN_SCHEMA4_STORAGE_NOT_LIVE_UI_NOT_RELEASE"
LABELS = {
    "seed": [
        "all_18_tables_nonempty_before_migration",
        "migration_preserves_all_old_cells", "migration_only_adds_shortcut_table",
        "stable_ids_and_multi_category_links", "repeat_setting_is_exact_noop",
        "same_name_targets_not_confused", "invalid_targets_leave_exact_state",
        "remove_relation_only_and_repeat_noop",
        "navigation_read_is_pure_and_excludes_archived",
        "missing_navigation_no_business_writes",
        "late_sql_failure_rolls_back_link_and_revision",
        "unknown_tables_never_silently_omitted",
        "backup_preserves_source_and_original_media",
        "restore_preview_is_read_only_and_counts_complete",
        "restore_counts_immutable",
        "cancel_and_replay_preserve_state",
        "foreign_owner_refused_without_consuming_valid_plan",
        "helper_close_invalidates_restore_session",
        "same_revision_stale_restore_refused",
        "new_backup_restore_exact_and_single_use",
        "old_backup_replacement_clears_new_relationships",
        "late_restore_failure_rolls_back_every_table",
        "changed_staged_media_refused_without_live_damage",
        "reviewed_source_frozen_against_file_replacement",
        "staging_closed_and_original_media_exact",
        "restore_suite_preserves_all_business_cells",
        "v2_backup_normalizes_empty_shortcuts", "v3_backup_normalizes_empty_shortcuts",
        "malformed_and_new_to_old_backups_refused",
        "migration_conflict_keeps_version_and_schema",
        "future_schema_refused_without_damage", "live_ui_database_never_opened",
    ],
    "reopen": [
        "separate_process_exact_state", "separate_process_all_business_cells",
        "separate_process_relationships_and_read_only_targets",
        "separate_process_original_media", "separate_process_backup_restore_exact",
        "separate_process_no_live_ui_database",
    ],
}


def need(ok, reason):
    if not ok:
        raise AssertionError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse_phase(raw, phase, api):
    need(phase in LABELS and api in (26, 34), "phase/API identity")
    text = raw.decode("utf-8", "strict").replace("\r\n","\n")
    found = re.findall(r"(?:^|stream=)SHORTCUT_PASS ([a-z0-9_]+)$", text, re.M)
    need(found == LABELS[phase], "ordered complete device labels")
    expected = f"SHORTCUT_RESULT {phase} {api} {len(found)} PASS"
    need(re.findall(r"(?:^|stream=)(SHORTCUT_RESULT [^\n]+)$", text, re.M) == [expected],
         "single matching device result")
    need(re.findall(r"^INSTRUMENTATION_CODE: (-?\d+)$", text, re.M) == ["-1"],
         "normal instrumentation exit")
    need(not re.search(r"SHORTCUT_FAILED|INSTRUMENTATION_FAILED|INSTRUMENTATION_ABORTED|FATAL EXCEPTION|Process crashed", text),
         "original device failure")
    return found


def fixture(phase="seed", api=26):
    return ("\n".join("SHORTCUT_PASS " + label for label in LABELS[phase]) +
            f"\nSHORTCUT_RESULT {phase} {api} {len(LABELS[phase])} PASS\n"
            "INSTRUMENTATION_CODE: -1\n").encode()


def parser_selftest():
    positive = negative = 0
    for phase in LABELS:
        for api in (26, 34):
            raw = fixture(phase, api)
            for valid in (raw,raw.replace(b"\n",b"\r\n"),
                          b"INSTRUMENTATION_RESULT: stream="+raw,
                          b"INSTRUMENTATION_RESULT: stream="+raw.replace(b"\n",b"\r\n")):
                parse_phase(valid, phase, api)
                positive += 1
            bads = [raw.replace(f"SHORTCUT_PASS {x}\n".encode(), b"", 1)
                    for x in LABELS[phase]]
            bads += [raw + b"SHORTCUT_FAILED\n",
                     raw.replace(b"INSTRUMENTATION_CODE: -1", b"INSTRUMENTATION_CODE: 0"),
                     raw.replace(f" {api} ".encode(), b" 99 "),
                     raw + raw, raw.replace(b" PASS\n", b" SKIPPED\n")]
            for bad in bads:
                try:
                    parse_phase(bad, phase, api)
                except (AssertionError, UnicodeError):
                    negative += 1
                else:
                    raise AssertionError("report accepted incomplete or failed result")
    print(f"SHORTCUT_PARSER positive={positive} negative={negative} PASS")


HARNESS = r'''
import java.io.*;import java.util.*;import java.nio.*;
class WireTest {
__WIRE__
static void need(boolean ok,String s){if(!ok)throw new AssertionError(s);}
interface Action {void run()throws Exception;}
static int positive,negative;
static void rejected(Action run,String message)throws Exception{
 try{run.run();}catch(IllegalArgumentException e){
  need(message.equals(e.getMessage()),"wrong rejection: "+e.getMessage());negative++;return;
 }
 throw new AssertionError("MISSED "+message);
}
static byte[] independent(byte[] old,long[][] links)throws Exception{
 ByteArrayOutputStream b=new ByteArrayOutputStream();DataOutputStream d=new DataOutputStream(b);
 d.writeInt(0x50544442);d.writeInt(3);d.writeInt(4);d.writeInt(old.length);d.write(old);
 d.writeInt(links.length);for(long[] x:links){d.writeLong(x[0]);d.writeLong(x[1]);}d.flush();return b.toByteArray();
}
public static void main(String[] args)throws Exception{
 byte[] old=ByteBuffer.allocate(16).putInt(0x50544442).putInt(2).putInt(3).putInt(18).array();
 byte[] good=independent(old,new long[][]{{7,10},{7,11},{8,10}});
 Wire parsed=Wire.read(good);
 need(Arrays.equals(good,Wire.encode(parsed.base(),parsed.links)),"wire roundtrip");positive++;
 need(parsed.links.size()==3&&parsed.links.get(2).category==8&&parsed.links.get(2).application==10,"typed identities");positive++;
 System.out.println("VALID_WIRE_WITNESS");
 if(args.length>0)return;
 byte[] copy=parsed.base();copy[0]^=1;need(Arrays.equals(old,parsed.base()),"base ownership");positive++;
 boolean immutable=false;try{parsed.links.clear();}catch(UnsupportedOperationException expected){immutable=true;}
 need(immutable,"immutable links");positive++;
 byte[] empty=independent(old,new long[][]{});
 need(Arrays.equals(empty,Wire.encode(old,List.of()))&&Wire.read(empty).links.isEmpty(),"empty roundtrip");positive++;
 rejected(()->Wire.read(null),"Envelope budget");
 rejected(()->Wire.read(new byte[0]),"Envelope budget");
 rejected(()->Wire.read(new byte[Wire.LIMIT+1]),"Envelope budget");
 byte[] bad=good.clone();bad[0]^=1;final byte[] magic=bad;rejected(()->Wire.read(magic),"Envelope version");
 bad=good.clone();bad[7]=2;final byte[] version=bad;rejected(()->Wire.read(version),"Envelope version");
 bad=good.clone();bad[11]=3;final byte[] schema=bad;rejected(()->Wire.read(schema),"Envelope version");
 for(int n:new int[]{-1,0,15,Integer.MAX_VALUE,good.length}){
  byte[] x=good.clone();ByteBuffer.wrap(x).putInt(12,n);
  rejected(()->Wire.read(x),"Embedded state length");
 }
 byte[] baseBad=old.clone();baseBad[7]=1;
 rejected(()->Wire.read(independent(baseBad,new long[][]{})),"Embedded schema3 header");
 for(int n:new int[]{-1,4,Integer.MAX_VALUE}){
  byte[] x=good.clone();ByteBuffer.wrap(x).putInt(16+old.length,n);
  rejected(()->Wire.read(x),"Shortcut count");
 }
 rejected(()->Wire.read(independent(old,new long[][]{{0,10}})),"Invalid identity");
 rejected(()->Wire.read(independent(old,new long[][]{{7,-1}})),"Invalid identity");
 rejected(()->Wire.read(independent(old,new long[][]{{7,10},{7,10}})),"Shortcut order");
 rejected(()->Wire.read(independent(old,new long[][]{{8,10},{7,11}})),"Shortcut order");
 rejected(()->Wire.read(independent(old,new long[][]{{7,11},{7,10}})),"Shortcut order");
 rejected(()->Wire.read(Arrays.copyOf(good,good.length+1)),"Trailing envelope bytes");
 rejected(()->Wire.read(Arrays.copyOf(good,good.length-1)),"Shortcut count");
 need(Arrays.equals(good,Wire.encode(old,List.of(new Link(7,10),new Link(7,11),new Link(8,10)))),"encode independent oracle");positive++;
 need(positive==6&&negative==22,"control population "+positive+"/"+negative);
 System.out.println("SHORTCUT_WIRE positive="+positive+" negative="+negative+" PASS");
}
}
'''


def java_run(source, args=()):
    with tempfile.TemporaryDirectory(prefix="shortcut-java-") as directory:
        root = Path(directory)
        file = root / "WireTest.java"
        file.write_text(source)
        # JDK modules work on minimal images that lack the javac launcher.
        compiled = subprocess.run(["java", "-m", "jdk.compiler/com.sun.tools.javac.Main",
                                   "-encoding", "UTF-8", "-d", str(root), str(file)],
                                  capture_output=True, text=True, timeout=60)
        need(compiled.returncode == 0, "actual Java compile failed:\n" + compiled.stdout + compiled.stderr)
        return subprocess.run(["java", "-cp", str(root), "WireTest", *args],
                              capture_output=True, text=True, timeout=60)


def wire_source():
    source = JAVA.read_text()
    start, end = "    // BEGIN_PURE_WIRE\n", "    // END_PURE_WIRE\n"
    need(source.count(start) == source.count(end) == 1, "single pure Java codec region")
    return source.split(start, 1)[1].split(end, 1)[0]


def wire_selftest():
    wire = wire_source()
    source = HARNESS.replace("__WIRE__", wire)
    result = java_run(source)
    need(result.returncode == 0, result.stdout + result.stderr)
    print(result.stdout.strip())
    mutations = [
        ('require(category>0&&application>0,"Invalid identity");', '', "Invalid identity"),
        ('require(prior==null||prior.category<link.category||(prior.category==link.category&&prior.application<link.application),"Shortcut order");', '', "Shortcut order"),
        ('require(in.available()==0,"Trailing envelope bytes");', '', "Trailing envelope bytes"),
    ]
    for old, new, expected in mutations:
        need(wire.count(old) == 1, "mutation anchor " + expected)
        mutated = HARNESS.replace("__WIRE__", wire.replace(old, new, 1))
        witness = java_run(mutated, ("witness",))
        need(witness.returncode == 0 and "VALID_WIRE_WITNESS" in witness.stdout,
             "invalid implementation mutant")
        killed = java_run(mutated)
        need(killed.returncode != 0 and "MISSED " + expected in killed.stderr,
             "implementation mutant survived or failed for unrelated reason")
    print(f"SHORTCUT_WIRE witnessed_behavior_mutants={len(mutations)} PASS")


def sql_selftest():
    source = JAVA.read_text()
    values = re.findall(r'^    static final String SHORTCUT_DDL=(".*");$', source, re.M)
    need(len(values) == 1, "one literal production DDL")
    ddl = json.loads(values[0])
    with sqlite3.connect(":memory:") as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("CREATE TABLE categories(id INTEGER PRIMARY KEY)")
        db.execute("CREATE TABLE applications(id INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO categories VALUES(7),(8)")
        db.execute("INSERT INTO applications VALUES(10),(11)")
        db.execute(ddl)
        db.execute("INSERT INTO category_shortcuts VALUES(7,10)")
        db.execute("INSERT INTO category_shortcuts VALUES(8,10)")
        negative = 0
        for sql in ("INSERT INTO category_shortcuts VALUES(7,10)",
                    "INSERT INTO category_shortcuts VALUES(999,10)",
                    "INSERT INTO category_shortcuts VALUES(7,999)",
                    "INSERT INTO category_shortcuts VALUES(-1,10)",
                    "INSERT INTO category_shortcuts VALUES(7,NULL)"):
            try:
                db.execute(sql)
            except sqlite3.IntegrityError:
                negative += 1
            else:
                raise AssertionError("SQL constraint missing: " + sql)
        need(db.execute("SELECT * FROM category_shortcuts ORDER BY category_id,application_id").fetchall() ==
             [(7, 10), (8, 10)], "failed SQL changed links")
    print(f"SHORTCUT_SQL positive=2 negative={negative} HOST_SQLITE_NOT_ANDROID PASS")


STUBS = {
    "android/content/Context.java": """package android.content;public class Context{
public Context getApplicationContext(){return this;}public String getPackageName(){return "";}
public java.io.File getFilesDir(){return null;}public java.io.File getCacheDir(){return null;}
public java.io.File getDatabasePath(String n){return null;}public boolean deleteDatabase(String n){return false;}
public android.database.sqlite.SQLiteDatabase openOrCreateDatabase(String n,int m,Object f){return null;}
}""",
    "android/database/Cursor.java": """package android.database;public interface Cursor extends AutoCloseable{
int FIELD_TYPE_NULL=0,FIELD_TYPE_INTEGER=1,FIELD_TYPE_STRING=3,FIELD_TYPE_BLOB=4;
boolean moveToFirst();boolean moveToNext();int getType(int i);long getLong(int i);
String getString(int i);byte[] getBlob(int i);int getCount();int getColumnCount();
String[] getColumnNames();void close();
}""",
    "android/database/sqlite/SQLiteDatabase.java": """package android.database.sqlite;public class SQLiteDatabase implements AutoCloseable{
public static SQLiteDatabase create(Object f){return null;}public void close(){}
public void setForeignKeyConstraintsEnabled(boolean b){}public void setVersion(int n){}
public int getVersion(){return 0;}public boolean isOpen(){return true;}public boolean inTransaction(){return false;}
public void beginTransaction(){}public void endTransaction(){}public void setTransactionSuccessful(){}
public android.database.Cursor rawQuery(String q,String[] a){return null;}
public void execSQL(String q){}public void execSQL(String q,Object[] a){}
public int delete(String t,String w,String[] a){return 0;}
}""",
    "android/database/sqlite/SQLiteOpenHelper.java": """package android.database.sqlite;public abstract class SQLiteOpenHelper implements AutoCloseable{
public SQLiteOpenHelper(android.content.Context c,String n,Object f,int v){}
public void setWriteAheadLoggingEnabled(boolean b){}public SQLiteDatabase getReadableDatabase(){return null;}
public SQLiteDatabase getWritableDatabase(){return null;}public void close(){}
public void onConfigure(SQLiteDatabase d){}public abstract void onCreate(SQLiteDatabase d);
public abstract void onUpgrade(SQLiteDatabase d,int f,int t);public void onDowngrade(SQLiteDatabase d,int f,int t){}
}""",
    "android/app/Activity.java": "package android.app;public class Activity{public static final int RESULT_OK=-1,RESULT_CANCELED=0;}",
    "android/app/Instrumentation.java": """package android.app;public class Instrumentation{
public void onCreate(android.os.Bundle b){}public void onStart(){}public void start(){}
public android.content.Context getTargetContext(){return null;}
public void finish(int n,android.os.Bundle b){}
}""",
    "android/os/Bundle.java": "package android.os;public class Bundle{public String getString(String n){return null;}public void putString(String a,String b){}}",
    "android/os/Build.java": "package android.os;public class Build{public static class VERSION{public static int SDK_INT=26;}}",
    "com/supercubegame/pockettodo/Schema3Store.java": """package com.supercubegame.pockettodo;
import android.database.sqlite.*;public class Schema3Store implements AutoCloseable{
public Schema3Store(android.content.Context c,String n){}public SQLiteDatabase getWritableDatabase(){return null;}
public byte[] exportState(){return null;}public void close(){}
static void createSchema3(SQLiteDatabase d){}static SQLiteDatabase stateCandidate(byte[] b){return null;}
static class ComparisonBuffer extends java.io.ByteArrayOutputStream{ComparisonBuffer(int n){}}
}""",
    "com/supercubegame/pockettodo/AppDatabase.java": """package com.supercubegame.pockettodo;
public class AppDatabase implements AutoCloseable{public AppDatabase(android.content.Context c,String n){}
public byte[] exportState(){return null;}public void close(){}}
""",
    "com/supercubegame/pockettodo/V12DeviceTest.java": "package com.supercubegame.pockettodo;public class V12DeviceTest{}",
    "com/supercubegame/pockettodo/MediaRepository.java": """package com.supercubegame.pockettodo;
import java.io.*;import java.nio.file.*;public class MediaRepository{
public MediaRepository(Path p,long n)throws IOException{}static void validId(String s){}
public String copy(InputStream i)throws IOException{return null;}public void verify(String s)throws IOException{}
public Path path(String s)throws IOException{return null;}static java.security.MessageDigest sha(){return null;}
static String hex(byte[] b){return null;}
}""",
    "com/supercubegame/pockettodo/BackupArchive.java": """package com.supercubegame.pockettodo;
import java.io.*;import java.nio.file.*;import java.util.*;public class BackupArchive{
public static Snapshot read(Path p,Path s,long n)throws IOException{return null;}
public static void write(Path p,byte[] b,Set<String> ids,MediaRepository m)throws IOException{}
public static class Snapshot implements AutoCloseable{
public byte[] state(){return null;}public Map<String,Path> assets(){return null;}public void close()throws IOException{}
}
}""",
}


def syntax_selftest():
    """Real JDK compiles whole new classes against API-shape stubs, not Android."""
    with tempfile.TemporaryDirectory(prefix="shortcut-shape-") as directory:
        root = Path(directory)
        for name, text in STUBS.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        sources = sorted(map(str, root.rglob("*.java"))) + [str(JAVA), str(DEVICE)]
        result = subprocess.run(["java", "-m", "jdk.compiler/com.sun.tools.javac.Main",
                                 "-encoding", "UTF-8", "-d", str(root / "classes"), *sources],
                                capture_output=True, text=True, timeout=60)
        need(result.returncode == 0, "new-class Java syntax failed:\n" + result.stdout + result.stderr)
    print("SHORTCUT_WHOLE_NEW_CLASSES_COMPILE API_SHAPE_STUBS_NOT_ANDROID PASS")


PROJECT_PATHS = (
    "src/main/java/com/supercubegame/pockettodo/Schema3Store.java",
    "src/main/java/com/supercubegame/pockettodo/Schema4Store.java",
    "src/androidTest/java/com/supercubegame/pockettodo/Schema4DeviceTest.java",
    "tools/verify_shortcuts.py", ".github/workflows/shortcut-storage.yml",
    "AGENTS.md", "CLAUDE.md",
)
OLD_TABLES = "revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports".split()


def source_identity():
    return {p: digest((ROOT / p).read_bytes()) for p in PROJECT_PATHS}


def binding():
    values = {k: os.environ[v] for k, v in
              (("commit", "GITHUB_SHA"), ("run_id", "GITHUB_RUN_ID"),
               ("run_attempt", "GITHUB_RUN_ATTEMPT"))}
    need(re.fullmatch("[0-9a-f]{40}", values["commit"]) is not None and
         all(re.fullmatch("[1-9][0-9]*", values[k]) for k in ("run_id", "run_attempt")),
         "run identity")
    return values


def build():
    need(os.environ.get("GITHUB_ACTIONS") == "true", "disposable CI only")
    need("POCKET_STABLE_SIGNING" not in os.environ, "storage probes use disposable signing only")
    path = ROOT / "build.gradle"
    original = path.read_bytes()
    old, new = "'com.supercubegame.pockettodo.V12DeviceTest'", "'com.supercubegame.pockettodo.Schema4DeviceTest'"
    text = original.decode()
    need(text.count(old) == 1 and new not in text, "unique default runner")
    candidate = text.replace(old, new, 1).encode()
    receipt = dict(status="FAIL", scope=SCOPE, **binding(), source_files=source_identity(),
                   build_gradle_before=digest(original), build_gradle_probe=digest(candidate),
                   restored=False, release_ready=False)
    target = ROOT / "shortcut-build.json"
    try:
        path.write_bytes(candidate)
        # Reuse the existing configuration-only retry classifier and exact build.
        # Never retry device assertions or replace the original build failure.
        lines = (ROOT / ".github/workflows/android.yml").read_text().splitlines()
        anchor = "        run: &verified_build |"
        need(lines.count(anchor) == 1, "one established build guard")
        body = []
        for line in lines[lines.index(anchor) + 1:]:
            if line and not line.startswith("          "):
                break
            body.append(line[10:] if line else "")
        script = "\n".join(body) + "\n"
        need(script.startswith("set -euo pipefail\npython3 - <<'PY'\n") and
             script.endswith("PY\n") and "rate_limited_configuration" in script and
             "selftest()" in script, "existing build guard boundaries")
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)
        subprocess.run(["bash", "-euo", "pipefail", "-c", script],
                       text=True, check=True, timeout=900)
        for key, folder in (("product", "build/outputs/apk/debug"),
                            ("test", "build/outputs/apk/androidTest/debug")):
            apks = list((ROOT / folder).glob("*.apk"))
            need(len(apks) == 1, "single " + key + " APK")
            receipt[key] = dict(path=str(apks[0].relative_to(ROOT)),
                                bytes=apks[0].stat().st_size,
                                sha256=digest(apks[0].read_bytes()))
            tools=Path(os.environ["ANDROID_HOME"])/"build-tools/35.0.0"
            checked=subprocess.run([str(tools/"apksigner"),"verify","--verbose","--print-certs",str(apks[0])],
                                   text=True,capture_output=True,check=True,timeout=30)
            certificates=re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})$",checked.stdout,re.M)
            need(len(certificates)==1,"one verified APK signer")
            receipt[key]["certificate"]=certificates[0]
        need(receipt["product"]["certificate"]==receipt["test"]["certificate"],"app/test certificates differ")
        receipt["status"] = "PASS"
    except BaseException as exc:
        receipt["error"] = repr(exc)
        raise
    finally:
        path.write_bytes(original)
        receipt["restored"] = path.read_bytes() == original
        target.write_text(json.dumps(receipt, indent=2) + "\n")
        need(receipt["restored"], "original Gradle bytes not restored")


def database_snapshot(path):
    """Independent SQLite reader; include every typed cell and old rowid."""
    result = {}
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as db:
        need(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)],
             "SQLite integrity")
        need(db.execute("PRAGMA foreign_key_check").fetchall() == [], "SQLite foreign keys")
        need(db.execute("PRAGMA user_version").fetchone() == (4,), "actual schema4")
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                 if not r[0].startswith("sqlite_") and r[0] != "android_metadata"}
        need(names == set(OLD_TABLES + ["category_shortcuts"]), "exact 19 business tables")
        for table in OLD_TABLES + ["category_shortcuts"]:
            old = table != "category_shortcuts"
            sql = "SELECT " + ("rowid,*" if old else "*") + " FROM " + table + " ORDER BY " + ("rowid" if old else "category_id,application_id")
            rows = db.execute(sql)
            cols = [c[0] for c in rows.description]
            typed = []
            for row in rows:
                cells = []
                for value in row:
                    need(value is None or type(value) in (int, str, bytes), "unexpected storage type")
                    cells.append(["null", None] if value is None else
                                 ["integer", value] if type(value) is int else
                                 ["text", value] if type(value) is str else ["blob", value.hex()])
                typed.append(cells)
            need(bool(typed), "nonempty all-table fixture: " + table)
            result[table] = dict(columns=cols, rows=typed)
        need(db.execute("SELECT category_id,application_id FROM category_shortcuts ORDER BY 1,2").fetchall() ==
             [(7, 10), (8, 10)], "independent exact shortcut links")
        need(db.execute("SELECT count(*) FROM applications").fetchone() == (2,), "no duplicated applications")
        need(db.execute("SELECT count(*) FROM activities").fetchone() == (4,), "no auto-created activities")
    return result


def android():
    import emulator_gate as gate
    from verify_process_control import stop_verified
    from verify_adb_transfer import pull_exact
    need(os.environ.get("GITHUB_ACTIONS") == "true", "disposable runner only")
    out = ROOT / "shortcut-device"
    out.mkdir(exist_ok=False)
    receipt = dict(status="FAIL", scope=SCOPE, **binding(), api=gate.API,
                   source_files=source_identity(), phases={}, commands=[], stops=[],
                   snapshots={}, installed={}, release_ready=False, live_ui_enabled=False)
    completed = []

    def save():
        (out / "result.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")

    def execute(adb):
        built = json.loads((ROOT / "shortcut-build.json").read_bytes())
        need(built["status"] == "PASS" and built["restored"] is True and
             built["source_files"] == receipt["source_files"] and
             all(built[k] == receipt[k] for k in ("commit", "run_id", "run_attempt")),
             "current build receipt")
        prefix = [str(adb), "-s", gate.SERIAL]

        def command(args, timeout=40):
            # Every invocation has one attempt and keeps both complete streams.
            number = len(receipt["commands"])
            entry = dict(args=list(map(str, args)), timeout=timeout, attempts=1)
            receipt["commands"].append(entry)
            save()
            stdout = stderr = b""
            try:
                p = subprocess.run(prefix + list(map(str, args)), stdin=subprocess.DEVNULL,
                                   capture_output=True, timeout=timeout, check=False)
                stdout, stderr = p.stdout, p.stderr
                entry["returncode"] = p.returncode
                if p.returncode:
                    entry.update(stdout_tail=stdout[-8000:].decode(errors="replace"),
                                 stderr_tail=stderr[-8000:].decode(errors="replace"),
                                 tail_truncated=len(stdout)>8000 or len(stderr)>8000)
                p.check_returncode()
                return stdout
            except subprocess.TimeoutExpired as exc:
                stdout, stderr = exc.stdout or b"", exc.stderr or b""
                entry["timed_out"] = True
                entry.update(stdout_tail=stdout[-8000:].decode(errors="replace"),
                             stderr_tail=stderr[-8000:].decode(errors="replace"),
                             tail_truncated=len(stdout)>8000 or len(stderr)>8000)
                raise
            finally:
                for stream, data in (("stdout", stdout), ("stderr", stderr)):
                    name = f"command-{number}-{stream}.bin"
                    (out / name).write_bytes(data)
                    entry[stream] = dict(file=name, bytes=len(data), sha256=digest(data))
                save()

        def shell(*args, timeout=40):
            return command(["shell", "-n", "-T", *args], timeout)

        def stop():
            stop_verified(adb, gate.SERIAL, PACKAGE, emit=receipt["stops"].append)
            save()

        for key in ("product", "test"):
            identity = built[key]
            apk = ROOT / identity["path"]
            expected = apk.read_bytes()
            need(len(expected) == identity["bytes"] and digest(expected) == identity["sha256"], "built APK changed")
            command(["install", "-r", "-t", apk], 120)
            package = PACKAGE if key == "product" else PACKAGE + ".test"
            paths = shell("pm", "path", package).decode().splitlines()
            need(len(paths) == 1 and paths[0].startswith("package:/data/app/"), "one installed APK")
            trace = {}
            actual = pull_exact(adb, gate.SERIAL, paths[0][8:], expected, trace)
            need(actual == expected, "installed APK differs")
            receipt["installed"][key] = dict(bytes=len(actual), sha256=digest(actual), transfer=trace)
            save()
        instrumentation = shell("pm", "list", "instrumentation").decode()
        component = PACKAGE + ".test/com.supercubegame.pockettodo.Schema4DeviceTest"
        need("instrumentation:" + component + " (target=" + PACKAGE + ")" in instrumentation,
             "actual isolated runner identity")
        for phase in ("seed", "reopen"):
            stop()
            raw = command(["shell", "-n", "-T", "am", "instrument", "-w", "-r",
                           "-e", "expectedApi", str(gate.API), "-e", "phase", phase, component], 180)
            (out / (phase + ".log")).write_bytes(raw)
            # Preserve original failure stream before parsing labels.
            receipt["phases"][phase] = dict(bytes=len(raw), sha256=digest(raw))
            save()
            receipt["phases"][phase]["labels"] = parse_phase(raw, phase, gate.API)
            stop()
            names = shell("run-as", PACKAGE, "ls", "databases").decode().splitlines()
            need(not any(n.startswith("pocket-v12.db") for n in names), "live UI DB was created")
            need("schema4-contract.db" in names, "fixture database absent")
            folder = out / phase
            folder.mkdir()
            for name in ("schema4-contract.db", "schema4-contract.db-wal"):
                if name in names:
                    data = command(["exec-out", "run-as", PACKAGE, "cat", "databases/" + name])
                    need(0 < len(data) <= 8 * 1024 * 1024, "database read budget")
                    (folder / name).write_bytes(data)
            receipt["snapshots"][phase] = database_snapshot(folder / "schema4-contract.db")
            media = command(["exec-out", "run-as", PACKAGE, "cat", "files/schema4-media/ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"])
            need(media == b"abc", "independent original media bytes")
            receipt["phases"][phase]["media_sha256"] = digest(media)
            save()
        need(receipt["snapshots"]["seed"] == receipt["snapshots"]["reopen"],
             "independent restart/restore cells differ")
        completed.append("storage_checked")

    def finish(adb):
        need(completed == ["storage_checked"], "storage callback omitted")

    old_database, old_native = gate.verify_database, gate.verify_native_ui
    gate.verify_database, gate.verify_native_ui = execute, finish
    save()
    try:
        gate.main()
        need(completed == ["storage_checked"], "storage not executed")
        receipt["status"] = "PASS"
    except BaseException as exc:
        receipt.update(status="FAIL", error=repr(exc))
        raise
    finally:
        gate.verify_database, gate.verify_native_ui = old_database, old_native
        save()


def validate_receipt(value, expected, api, sources):
    need(value["status"] == "PASS" and value["scope"] == SCOPE, "device status/scope")
    need(all(value[k] == expected[k] for k in ("commit", "run_id", "run_attempt")) and
         value["api"] == api, "device source/run/API binding")
    need(value["source_files"] == sources, "actual tested source files")
    need(value["release_ready"] is False and value["live_ui_enabled"] is False, "storage-only scope")
    need(set(value["phases"]) == set(LABELS) and
         set(value["snapshots"]) == set(LABELS), "complete phase population")
    for phase, labels in LABELS.items():
        need(value["phases"][phase]["labels"] == labels, "complete ordered phase checks")
        need(value["phases"][phase]["media_sha256"] == digest(b"abc"), "phase media bytes")
        need(set(value["snapshots"][phase]) == set(OLD_TABLES + ["category_shortcuts"]),
             "snapshot complete business tables")
        need(all(x["rows"] for x in value["snapshots"][phase].values()),
             "snapshot all-table nonempty witness")
    need(value["snapshots"]["seed"] == value["snapshots"]["reopen"], "restart exact typed rows")
    need(set(value["installed"]) == {"product", "test"} and value["stops"], "APK and process evidence")
    for apk in value["installed"].values():
        need(type(apk["bytes"]) is int and apk["bytes"]>0 and
             type(apk["sha256"]) is str and re.fullmatch("[0-9a-f]{64}",apk["sha256"]) is not None,
             "installed APK identity shape")
    need(value["commands"] and all(x.get("returncode") == 0 and
         x.get("attempts") == 1 and not x.get("timed_out") for x in value["commands"]),
         "original single-attempt commands all passed")


def receipt_fixture(api=26):
    expected = dict(commit="a"*40, run_id="1", run_attempt="1")
    sources = {p: digest(p.encode()) for p in PROJECT_PATHS}
    snapshots = {table: dict(columns=["fixture"], rows=[[["text", "synthetic"]]])
                 for table in OLD_TABLES + ["category_shortcuts"]}
    value = dict(status="PASS", scope=SCOPE, **expected, api=api, source_files=sources,
                 phases={p: dict(labels=list(v), media_sha256=digest(b"abc"),
                                 bytes=len(fixture(p,api)),sha256=digest(fixture(p,api)))
                         for p,v in LABELS.items()},
                 snapshots={p:copy.deepcopy(snapshots) for p in LABELS},
                 installed={p:dict(sha256="b"*64,bytes=1) for p in ("product","test")},
                 stops=[{"fixture":"normal stopped"}],
                 commands=[dict(returncode=0,attempts=1)],
                 release_ready=False,live_ui_enabled=False)
    return value,expected,sources


def receipt_controls(checker=validate_receipt):
    value,expected,sources=receipt_fixture()
    checker(value,expected,26,sources)
    cases=[]
    for key,replacement in (("commit","c"*40),("run_id","2"),("run_attempt","2"),("api",34),
                            ("status","FAIL"),("scope","FULL_V12"),("release_ready",True),
                            ("live_ui_enabled",True),("source_files",{}),
                            ("installed",{}),("stops",[]),("commands",[])):
        bad=copy.deepcopy(value);bad[key]=replacement;cases.append(bad)
    for phase in LABELS:
        for label in LABELS[phase]:
            bad=copy.deepcopy(value);bad["phases"][phase]["labels"].remove(label);cases.append(bad)
        bad=copy.deepcopy(value);del bad["phases"][phase];cases.append(bad)
        bad=copy.deepcopy(value);bad["phases"][phase]["media_sha256"]="0"*64;cases.append(bad)
        for table in OLD_TABLES+["category_shortcuts"]:
            bad=copy.deepcopy(value);del bad["snapshots"][phase][table];cases.append(bad)
        bad=copy.deepcopy(value);bad["snapshots"][phase]["todos"]["rows"]=[];cases.append(bad)
    for change in (dict(returncode=255),dict(attempts=2),dict(timed_out=True)):
        bad=copy.deepcopy(value);bad["commands"][0].update(change);cases.append(bad)
    for i,bad in enumerate(cases):
        try:checker(bad,expected,26,sources)
        except (AssertionError,KeyError,TypeError):pass
        else:raise AssertionError("MISSED_RECEIPT_CASE "+str(i))
    return len(cases)


def receipt_selftest():
    import inspect
    count=receipt_controls()
    source=inspect.getsource(validate_receipt)
    original='need(all(value[k] == expected[k] for k in ("commit", "run_id", "run_attempt")) and\n         value["api"] == api, "device source/run/API binding")'
    need(source.count(original)==1,"receipt binding mutant anchor")
    scope=dict(globals())
    exec(compile(source.replace(original,'need(True, "device source/run/API binding")',1),"<receipt-mutant>","exec"),scope)
    mutant=scope["validate_receipt"]
    value,expected,sources=receipt_fixture()
    mutant(value,expected,26,sources) # Actual valid witness before the same checker.
    try:receipt_controls(mutant)
    except AssertionError as exc:need(str(exc)=="MISSED_RECEIPT_CASE 0","wrong binding mutant rejection")
    else:raise AssertionError("receipt binding mutant survived")
    print(f"SHORTCUT_RECEIPT positive=1 negative={count} witnessed_mutants=1 PASS")


def report():
    import urllib.request
    from verify_evidence import publish
    value = dict(status="FAIL", scope=SCOPE, **binding(), devices={},
                 device_read_errors={}, device_validation_errors={},
                 release_ready=False, live_ui_enabled=False)
    sources = source_identity()
    for api in (26, 34):
        folder = ROOT / f"collected-shortcuts/shortcut-device-api-{api}/shortcut-device"
        try:
            with (folder / "result.json").open("rb") as stream:
                raw = stream.read(2 * 1024 * 1024 + 1)
            need(0 < len(raw) <= 2 * 1024 * 1024, "device receipt budget")
            value.setdefault("raw_receipts", {})[str(api)] = dict(bytes=len(raw), sha256=digest(raw))
            value["devices"][str(api)] = json.loads(raw)
        except (OSError, ValueError, AssertionError) as exc:
            value["device_read_errors"][str(api)] = repr(exc)
            continue
        try:
            receipt = value["devices"][str(api)]
            validate_receipt(receipt, value, api, sources)
            build_path=folder.parent/"shortcut-build.json"
            with build_path.open("rb") as stream:build_raw=stream.read(65537)
            need(0<len(build_raw)<=65536,"build receipt budget")
            built=json.loads(build_raw)
            need(built["status"]=="PASS" and built["restored"] is True and
                 built["source_files"]==sources and
                 all(built[k]==value[k] for k in ("commit","run_id","run_attempt")),
                 "current build and exact Gradle restoration")
            need(built["product"]["certificate"]==built["test"]["certificate"] and
                 re.fullmatch("[0-9a-f]{64}",built["product"]["certificate"]) is not None,
                 "build signing identity")
            for apk in ("product","test"):
                need(all(built[apk][k]==receipt["installed"][apk][k] for k in ("bytes","sha256")),
                     "installed APK not the compiled candidate")
            for phase in LABELS:
                with (folder / (phase + ".log")).open("rb") as stream:
                    raw = stream.read(2 * 1024 * 1024 + 1)
                need(0 < len(raw) <= 2 * 1024 * 1024, "raw device log budget")
                need(parse_phase(raw, phase, api) == receipt["phases"][phase]["labels"] and
                     len(raw) == receipt["phases"][phase]["bytes"] and
                     digest(raw) == receipt["phases"][phase]["sha256"], "raw phase evidence differs")
                independently = database_snapshot(folder / phase / "schema4-contract.db")
                need(independently == receipt["snapshots"][phase], "report independent database replay differs")
        except (OSError, ValueError, KeyError, TypeError, AssertionError, sqlite3.Error) as exc:
            value["device_validation_errors"][str(api)] = repr(exc)
    try:
        jobs = json.loads(os.environ["NEEDS_JSON"])
        need(jobs["shortcut_host"]["result"] == jobs["shortcut_device"]["result"] == "success", "host/device job not success")
        need(set(value["devices"]) == {"26", "34"} and not value["device_read_errors"] and
             not value["device_validation_errors"], "dual API storage acceptance incomplete")
        value["status"] = "PASS"
    except (KeyError, TypeError, ValueError, AssertionError) as exc:
        value["error"] = repr(exc)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    (ROOT / "shortcut-report.json").write_bytes(raw)

    def api(path, method="GET", body=None):
        request = urllib.request.Request("https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + "/" + path,
                    method=method, data=None if body is None else json.dumps(body).encode(),
                    headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                             "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    published = publish(api, "reports/shortcuts-" + value["commit"] + "-" +
                        value["run_id"] + "-" + value["run_attempt"] + ".json", raw)
    print("SHORTCUT_EVIDENCE " + json.dumps(published), flush=True)
    need(value["status"] == "PASS", "SHORTCUT_STORAGE_NOT_ACCEPTED: see original evidence")


def report_selftest():
    """Actual report entry; scripted files/database/publisher, not real CI proof."""
    import contextlib
    import io
    import types
    from unittest.mock import patch
    modes=("valid","missing26","failed26","failed34","wrong_attempt",
           "corrupt_log","missing_label","failed_job","snapshot_mismatch","publish_failure")
    for mode in modes:
        with tempfile.TemporaryDirectory(prefix="shortcut-report-") as folder:
            root=Path(folder);value,expected,sources=receipt_fixture()
            for api in (26,34):
                local,_,_=receipt_fixture(api)
                place=root/f"collected-shortcuts/shortcut-device-api-{api}/shortcut-device"
                place.mkdir(parents=True)
                if mode=="missing26" and api==26:continue
                if mode==f"failed{api}":local.update(status="FAIL",error="ORIGINAL_255_FAILURE")
                if mode=="wrong_attempt" and api==26:local["run_attempt"]="2"
                (place/"result.json").write_text(json.dumps(local))
                built=dict(status="PASS",restored=True,source_files=sources,**expected,
                           product=dict(bytes=1,sha256="b"*64,certificate="c"*64),
                           test=dict(bytes=1,sha256="b"*64,certificate="c"*64))
                (place.parent/"shortcut-build.json").write_text(json.dumps(built))
                for phase in LABELS:
                    raw=fixture(phase,api)
                    if api==26 and phase=="seed":
                        if mode=="corrupt_log":raw+=b"SHORTCUT_FAILED\n"
                        if mode=="missing_label":raw=raw.replace(("SHORTCUT_PASS "+LABELS["seed"][0]+"\n").encode(),b"",1)
                    (place/(phase+".log")).write_bytes(raw)
            sent=[]
            class Publisher:
                @staticmethod
                def publish(api,path,raw):
                    sent.append(json.loads(raw))
                    if mode=="publish_failure":raise OSError("original publisher failure")
                    return dict(html_url="https://example.invalid/evidence")
            def snapshot(path):
                data=copy.deepcopy(value["snapshots"]["seed"])
                if mode=="snapshot_mismatch":data["todos"]["rows"]=[]
                return data
            scope=dict(globals(),ROOT=root,source_identity=lambda:sources,database_snapshot=snapshot)
            runner=types.FunctionType(report.__code__,scope)
            jobs={k:dict(result="success") for k in ("shortcut_host","shortcut_device")}
            if mode=="failed_job":jobs["shortcut_host"]["result"]="failure"
            env=dict(GITHUB_SHA=expected["commit"],GITHUB_RUN_ID="1",GITHUB_RUN_ATTEMPT="1",
                     NEEDS_JSON=json.dumps(jobs))
            error=None
            with patch.dict(os.environ,env),patch.dict(sys.modules,{"verify_evidence":Publisher}),contextlib.redirect_stdout(io.StringIO()):
                try:runner()
                except Exception as exc:error=exc
            need(len(sent)==1,"report must publish even with missing/failed device")
            if mode=="valid":need(error is None and sent[0]["status"]=="PASS","valid actual report entry")
            elif mode=="publish_failure":need(type(error) is OSError and str(error)=="original publisher failure","publisher failure preserved")
            else:need(type(error) is AssertionError and sent[0]["status"]=="FAIL","invalid report not rejected")
            if mode in ("missing26","failed26"):
                need("34" in sent[0]["devices"] and sent[0]["devices"]["34"]["status"]=="PASS","first device failure hides second")
            if mode.startswith("failed") and mode[-2:] in ("26","34"):
                need(sent[0]["devices"][mode[-2:]]["error"]=="ORIGINAL_255_FAILURE","original device failure discarded")
    print(f"SHORTCUT_REPORT_ENTRY cases={len(modes)} SCRIPTED_IO_NOT_GITHUB PASS")


def workflow_contract(text):
    """Known workflow shape, scoped job blocks; comments cannot supply commands."""
    lines=[line for line in text.splitlines() if not line.lstrip().startswith("#")]
    source="\n".join(lines)
    starts=list(re.finditer(r"^  (shortcut_[a-z]+):$",source,re.M))
    blocks={m.group(1):source[m.end():starts[i+1].start() if i+1<len(starts) else len(source)]
            for i,m in enumerate(starts)}
    need(set(blocks)=={"shortcut_host","shortcut_device","shortcut_report"},"workflow job population")
    for name,command in (("shortcut_host","selftest"),("shortcut_device","build"),
                         ("shortcut_device","android"),("shortcut_report","report")):
        executable=re.findall(r"^          python3 tools/verify_shortcuts\.py ([a-z]+) 2>&1 \| tee [^\n]+$",blocks[name],re.M)
        need(executable.count(command)==1,"workflow executable "+command)
        need("          set -euo pipefail" in blocks[name],"workflow pipefail "+name)
    need("    needs: shortcut_host" in blocks["shortcut_device"] and
         "      fail-fast: false" in blocks["shortcut_device"] and
         "        api: [26, 34]" in blocks["shortcut_device"],"workflow both devices after host")
    need("    needs: [shortcut_host, shortcut_device]" in blocks["shortcut_report"] and
         "    if: always() && github.event_name != 'pull_request'" in blocks["shortcut_report"] and
         "      contents: write" in blocks["shortcut_report"],"workflow final failure report")
    need("          pattern: shortcut-*" in blocks["shortcut_report"] and
         "          path: collected-shortcuts" in blocks["shortcut_report"] and
         "          NEEDS_JSON: ${{ toJSON(needs) }}" in blocks["shortcut_report"],"workflow evidence bindings")
    actions=re.findall(r"^\s+- uses: ([^\s]+)$",source,re.M)
    need(actions and all(re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}",a) for a in actions),"immutable action versions")
    need("POCKET_STABLE_SIGNING" not in source and "POCKET_DELIVERY_TOKEN" not in source,
         "no signing/delivery credentials in storage workflow")


def workflow_selftest():
    source=(ROOT/".github/workflows/shortcut-storage.yml").read_text()
    workflow_contract(source)
    variants=[
        ("python3 tools/verify_shortcuts.py selftest","echo tools/verify_shortcuts.py selftest"),
        ("python3 tools/verify_shortcuts.py android","echo tools/verify_shortcuts.py android"),
        ("python3 tools/verify_shortcuts.py build","echo tools/verify_shortcuts.py build"),
        ("python3 tools/verify_shortcuts.py report","echo tools/verify_shortcuts.py report"),
        ("api: [26, 34]","api: [34]"),
        ("needs: [shortcut_host, shortcut_device]","needs: shortcut_device"),
        ("pattern: shortcut-*","pattern: catalog-*"),
    ]
    for old,new in variants:
        need(source.count(old)==1,"workflow mutant anchor")
        bad=source.replace(old,new,1)
        try:workflow_contract(bad)
        except AssertionError:pass
        else:raise AssertionError("workflow mutant survived "+old)
    print(f"SHORTCUT_WORKFLOW positive=1 omission_controls={len(variants)} PASS")


def selftest():
    parser_selftest()
    wire_selftest()
    sql_selftest()
    syntax_selftest()
    receipt_selftest()
    report_selftest()
    workflow_selftest()


if __name__ == "__main__":
    need(len(sys.argv) == 2 and sys.argv[1] in ("selftest", "build", "android", "report"),
         "usage: verify_shortcuts.py selftest|build|android|report")
    globals()[sys.argv[1]]()
