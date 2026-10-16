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
SCOPE = "ACTIVATION_BACKEND_CANDIDATE_NOT_PRODUCT_NOT_LIVE_UI_NOT_RELEASE"
LABELS = {'seed': ['all_18_tables_nonempty_before_migration', 'migration_preserves_all_old_cells', 'migration_only_adds_shortcut_table', 'stable_ids_and_multi_category_links', 'repeat_setting_is_exact_noop', 'same_name_targets_not_confused', 'invalid_targets_leave_exact_state', 'remove_relation_only_and_repeat_noop', 'navigation_read_is_pure_and_excludes_archived', 'missing_navigation_no_business_writes', 'late_sql_failure_rolls_back_link_and_revision', 'unknown_tables_never_silently_omitted', 'backup_preserves_source_and_original_media', 'restore_preview_is_read_only_and_counts_complete', 'restore_counts_immutable', 'cancel_and_replay_preserve_state', 'foreign_owner_refused_without_consuming_valid_plan', 'helper_close_invalidates_restore_session', 'same_revision_stale_restore_refused', 'new_backup_restore_exact_and_single_use', 'old_backup_replacement_clears_new_relationships', 'late_restore_failure_rolls_back_every_table', 'changed_staged_media_refused_without_live_damage', 'reviewed_source_frozen_against_file_replacement', 'staging_closed_and_original_media_exact', 'restore_suite_preserves_all_business_cells', 'v2_backup_normalizes_empty_shortcuts', 'v3_backup_normalizes_empty_shortcuts', 'malformed_and_new_to_old_backups_refused', 'migration_conflict_keeps_version_and_schema', 'future_schema_refused_without_damage', 'live_ui_database_never_opened', 'bridge_one_connection_and_schema4', 'bridge_note_write_preserves_links_and_origins', 'bridge_field_and_field_note_operations', 'bridge_catalog_paths_archive_and_pure_navigation', 'bridge_todo_delete_undo_preserves_shortcuts', 'bridge_same_revision_relation_change_invalidates_plan', 'bridge_late_business_failure_rolls_back_exactly', 'bridge_unrelated_relation_mutation_rolls_back', 'bridge_backup_preview_has_all_tables_and_no_writes', 'bridge_foreign_restore_does_not_consume_owner_plan', 'bridge_restore_detects_same_revision_link_edit', 'bridge_restore_late_failure_preserves_every_table', 'bridge_close_invalidates_business_session', 'bridge_unknown_table_refused_without_partial_write', 'bridge_live_database_name_refused', 'activation_original_schema3_nonempty', 'activation_resume_schema3_never_migrates', 'activation_resume_missing_never_creates', 'activation_resume_empty_preserved', 'activation_resume_corrupt_never_deleted', 'activation_resume_future_exact_preservation', 'activation_resume_symlink_refused', 'activation_preview_backup_without_migration', 'activation_cancel_refuses_replay', 'activation_foreign_attempt_never_opens_database', 'activation_same_revision_change_refused', 'activation_failed_attempt_consumed', 'activation_changed_backup_refused', 'activation_missing_backup_refused', 'activation_changed_media_refused', 'activation_helper_close_expires_consent', 'activation_outer_transaction_refused', 'activation_atomic_schema4_preserves_all_cells', 'activation_retains_verified_backup_and_media', 'activation_new_facade_supports_shortcuts', 'activation_resume_one_existing_connection', 'activation_resume_exact_state_and_links', 'activation_resume_closed_cannot_reopen', 'activation_never_touches_phone_database', 'startup_fresh_stays_schema3', 'startup_existing_schema3_keeps_data', 'startup_invalid_files_exact_preservation', 'startup_symlink_refused_without_reset', 'startup_schema2_uses_frozen_migration', 'startup_cancelled_activation_stays_schema3', 'startup_activated_schema4_resumes_exactly', 'startup_closed_facade_cannot_reopen', 'startup_never_touches_phone_database', 'ui_preview_cancel_is_read_only', 'ui_closed_preview_cannot_write_after_relaunch', 'ui_add_exact_relation_no_business_copy', 'ui_targets_exclude_archived_and_do_not_write', 'ui_same_name_navigation_exact_and_pure', 'ui_detached_callback_cannot_replay', 'ui_removed_link_refuses_stale_navigation', 'ui_remove_retains_other_category_and_history', 'ui_api_repeat_setting_exact_noop', 'ui_api_same_revision_edit_refused', 'ui_api_foreign_attempt_preserves_owner_plan', 'ui_api_close_invalidates_plan', 'ui_api_late_failure_rolls_back_all_cells', 'ui_api_unrelated_write_rolls_back', 'ui_backup_restore_keeps_relations_and_history', 'ui_activity_relaunch_preserves_exact_state', 'ui_never_opens_phone_database'], 'reopen': ['separate_process_exact_state', 'separate_process_all_business_cells', 'separate_process_relationships_and_read_only_targets', 'separate_process_original_media', 'separate_process_backup_restore_exact', 'separate_process_no_live_ui_database', 'bridge_separate_process_all_cells_and_wire_exact', 'bridge_separate_process_business_reads_are_pure', 'activation_separate_process_exact_state', 'activation_separate_process_relations', 'activation_separate_process_phone_database_absent', 'startup_separate_process_exact_state', 'startup_separate_process_relations', 'ui_separate_process_exact_state', 'ui_separate_process_navigation_pure', 'ui_separate_process_live_database_absent']}


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


STUBS = {'android/content/Context.java': 'package android.content;public class Context{\npublic Context getApplicationContext(){return this;}public String getPackageName(){return "";}\npublic java.io.File getFilesDir(){return null;}public java.io.File getCacheDir(){return null;}\npublic java.io.File getDatabasePath(String n){return null;}public boolean deleteDatabase(String n){return false;}\npublic android.database.sqlite.SQLiteDatabase openOrCreateDatabase(String n,int m,Object f){return null;}\n}', 'android/database/Cursor.java': 'package android.database;public interface Cursor extends AutoCloseable{\nint FIELD_TYPE_NULL=0,FIELD_TYPE_INTEGER=1,FIELD_TYPE_STRING=3,FIELD_TYPE_BLOB=4;\nboolean moveToFirst();boolean moveToNext();int getType(int i);long getLong(int i);\nString getString(int i);byte[] getBlob(int i);int getCount();int getColumnCount();\nString[] getColumnNames();void close();\n}', 'android/database/sqlite/SQLiteDatabase.java': 'package android.database.sqlite;public class SQLiteDatabase implements AutoCloseable{\npublic static SQLiteDatabase create(Object f){return null;}public void close(){}\npublic void setForeignKeyConstraintsEnabled(boolean b){}public void setVersion(int n){}\npublic int getVersion(){return 0;}public boolean isOpen(){return true;}public boolean inTransaction(){return false;}\npublic void beginTransaction(){}public void endTransaction(){}public void setTransactionSuccessful(){}\npublic android.database.Cursor rawQuery(String q,String[] a){return null;}\npublic void execSQL(String q){}public void execSQL(String q,Object[] a){}\npublic int delete(String t,String w,String[] a){return 0;}\n}', 'android/database/sqlite/SQLiteOpenHelper.java': 'package android.database.sqlite;public abstract class SQLiteOpenHelper implements AutoCloseable{\npublic SQLiteOpenHelper(android.content.Context c,String n,Object f,int v){}\npublic void setWriteAheadLoggingEnabled(boolean b){}public SQLiteDatabase getReadableDatabase(){return null;}\npublic SQLiteDatabase getWritableDatabase(){return null;}public void close(){}\npublic void onConfigure(SQLiteDatabase d){}public abstract void onCreate(SQLiteDatabase d);\npublic abstract void onUpgrade(SQLiteDatabase d,int f,int t);public void onDowngrade(SQLiteDatabase d,int f,int t){}\n}', 'android/app/Activity.java': 'package android.app;public class Activity{public static final int RESULT_OK=-1,RESULT_CANCELED=0;}', 'android/app/Instrumentation.java': 'package android.app;public class Instrumentation{\npublic void onCreate(android.os.Bundle b){}public void onStart(){}public void start(){}\npublic android.content.Context getTargetContext(){return null;}\npublic void finish(int n,android.os.Bundle b){}\n}', 'android/os/Bundle.java': 'package android.os;public class Bundle{public String getString(String n){return null;}public void putString(String a,String b){}}', 'android/os/Build.java': 'package android.os;public class Build{public static class VERSION{public static int SDK_INT=26;}}', 'com/supercubegame/pockettodo/Schema3Store.java': 'package com.supercubegame.pockettodo;\nimport android.database.sqlite.*;public class Schema3Store implements AutoCloseable{\npublic interface BusinessConnection{SQLiteDatabase database();byte[] snapshot(SQLiteDatabase d);void validate(SQLiteDatabase d);}\npublic Schema3Store(android.content.Context c,String n){}public Schema3Store(android.content.Context c,String n,BusinessConnection b){}public SQLiteDatabase getWritableDatabase(){return null;}\npublic byte[] exportState(){return null;}public void close(){}\nstatic void createSchema3(SQLiteDatabase d){}static SQLiteDatabase stateCandidate(byte[] b){return null;}\nstatic class ComparisonBuffer extends java.io.ByteArrayOutputStream{ComparisonBuffer(int n){}}\n}', 'com/supercubegame/pockettodo/AppDatabase.java': 'package com.supercubegame.pockettodo;\nimport java.util.*;import java.nio.file.*;import java.io.*;import android.database.sqlite.*;\npublic class AppDatabase implements AutoCloseable {\npublic AppDatabase(android.content.Context c,String n){}\npublic static AppDatabase openSchema4(android.content.Context c,String n){return null;}\npublic SQLiteDatabase getWritableDatabase(){return null;}public SQLiteDatabase getReadableDatabase(){return null;}\npublic byte[] exportState(){return null;}public void close(){}\npublic void addCategory(long id,String n){}public void addApplication(long id,String n,String p){}\npublic void addActivity(long id,long c,long a,String t){}public boolean setShortcut(long c,long a,boolean b){return false;}\npublic List<Long> shortcutApplications(long c){return null;}public List<Long> activityTargets(long c,long a){return null;}\npublic void createNote(String id,long a,String t){}public void registerMedia(String id,String m,long n){}\npublic void saveNote(String id,List<NoteDocument.Block> b){}public List<NoteDocument.Block> noteBlocks(String n){return null;}\npublic void defineField(String id,String n,String t,List<String> opts){}\npublic static class FieldEditPlan{}\npublic FieldEditPlan prepareFieldEdit(long a,String f){return null;}\npublic void confirmFieldValue(FieldEditPlan p,List<String> v){}public void confirmFieldRename(FieldEditPlan p,String n){}\npublic void confirmFieldNoteCreate(FieldEditPlan p,String n,String t){}\npublic List<String> fieldValue(long a,String f){return null;}public List<String> fieldNoteIds(long a,String f){return null;}\npublic static class ApplicationRenamePlan{}\npublic ApplicationRenamePlan prepareApplicationRename(long id){return null;}\npublic boolean confirmApplicationRename(ApplicationRenamePlan p,String n){return true;}\npublic static class ActivityStringsPlan{}public ActivityStringsPlan prepareActivityStrings(long a,boolean t){return null;}\npublic boolean confirmActivityStrings(ActivityStringsPlan p,List<String> v){return true;}\npublic static class ActivityArchivePlan{}public ActivityArchivePlan prepareActivityArchive(long a,boolean t){return null;}\npublic boolean confirmActivityArchive(ActivityArchivePlan p){return true;}\npublic void addTodo(String id,String t){}public List<String> todoIds(){return null;}\npublic static class TodoDeletionPlan{}public static class TodoDeletionUndo{}\npublic TodoDeletionPlan prepareTodoDeletion(String id){return null;}\npublic TodoDeletionUndo confirmTodoDeletion(TodoDeletionPlan p){return null;}public void undoTodoDeletion(TodoDeletionUndo u){}\npublic static class RestorePlan implements AutoCloseable{\npublic Map<String,Long> currentCounts(){return null;}public Map<String,Long> incomingCounts(){return null;}public void close()throws IOException{}}\npublic void exportBackup(Path p,MediaRepository m)throws IOException{}\npublic RestorePlan prepareRestore(Path p,Path s,long n)throws IOException{return null;}\npublic void confirmRestore(RestorePlan p,MediaRepository m)throws IOException{}\n}', 'com/supercubegame/pockettodo/V12DeviceTest.java': 'package com.supercubegame.pockettodo;public class V12DeviceTest{}', 'com/supercubegame/pockettodo/MediaRepository.java': 'package com.supercubegame.pockettodo;\nimport java.io.*;import java.nio.file.*;public class MediaRepository{\npublic MediaRepository(Path p,long n)throws IOException{}static void validId(String s){}\npublic String copy(InputStream i)throws IOException{return null;}public void verify(String s)throws IOException{}\npublic Path path(String s)throws IOException{return null;}static java.security.MessageDigest sha(){return null;}\nstatic String hex(byte[] b){return null;}\n}', 'com/supercubegame/pockettodo/BackupArchive.java': 'package com.supercubegame.pockettodo;\nimport java.io.*;import java.nio.file.*;import java.util.*;public class BackupArchive{\npublic static Snapshot read(Path p,Path s,long n)throws IOException{return null;}\npublic static void write(Path p,byte[] b,Set<String> ids,MediaRepository m)throws IOException{}\npublic static class Snapshot implements AutoCloseable{\npublic byte[] state(){return null;}public Map<String,Path> assets(){return null;}public void close()throws IOException{}\n}\n}', 'com/supercubegame/pockettodo/NoteDocument.java': 'package com.supercubegame.pockettodo;public class NoteDocument{\npublic static class Block{\npublic static Block text(String i,String t,boolean p){return null;}\npublic static Block image(String i,String a,String c,boolean p){return null;}\n}}'}


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
    'src/main/java/com/supercubegame/pockettodo/MainActivity.java',
    'src/main/java/com/supercubegame/pockettodo/TodayScreen.java',
    'src/main/java/com/supercubegame/pockettodo/ActivitiesScreen.java',
    "src/main/java/com/supercubegame/pockettodo/AppDatabase.java",
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
                   snapshots={}, business_snapshots={}, ui_snapshots={}, activation_snapshots={}, startup_snapshots={}, installed={}, release_ready=False, live_ui_enabled=False)
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
            need("schema4-business.db" in names, "business fixture absent")
            for name in ("schema4-business.db","schema4-business.db-wal"):
                if name in names:
                    data=command(["exec-out","run-as",PACKAGE,"cat","databases/"+name])
                    need(0<len(data)<=8*1024*1024,"business database read budget")
                    (folder/name).write_bytes(data)
            receipt["business_snapshots"][phase]=bridge_database_snapshot(folder/"schema4-business.db")
            need("schema4-ui.db" in names,"UI fixture absent")
            for name in ("schema4-ui.db","schema4-ui.db-wal"):
                if name in names:
                    data=command(["exec-out","run-as",PACKAGE,"cat","databases/"+name])
                    need(0<len(data)<=8*1024*1024,"UI database read budget")
                    (folder/name).write_bytes(data)
            receipt["ui_snapshots"][phase]=database_snapshot(folder/"schema4-ui.db")
            collect_activation_ui(command, names, folder, receipt, phase)
            collect_native_ui(command, names, folder, receipt, phase)
            need("schema4-activation.db" in names,"activation database absent")
            for name in ("schema4-activation.db","schema4-activation.db-wal"):
                if name in names:
                    data=command(["exec-out","run-as",PACKAGE,"cat","databases/"+name])
                    need(0<len(data)<=8*1024*1024,"activation database read budget")
                    (folder/name).write_bytes(data)
            receipt["activation_snapshots"][phase]=database_snapshot(folder/"schema4-activation.db")
            need("schema4-startup.db" in names,"startup database absent")
            for name in ("schema4-startup.db","schema4-startup.db-wal"):
                if name in names:
                    data=command(["exec-out","run-as",PACKAGE,"cat","databases/"+name])
                    need(0<len(data)<=8*1024*1024,"startup database read budget")
                    (folder/name).write_bytes(data)
            receipt["startup_snapshots"][phase]=database_snapshot(folder/"schema4-startup.db")


            if phase=="seed":
                shot=command(["exec-out","run-as",PACKAGE,"cat","files/schema4-ui.png"])
                need(shot.startswith(b"\x89PNG\r\n\x1a\n") and len(shot)<=8*1024*1024,"UI screenshot PNG budget")
                (out/"schema4-ui.png").write_bytes(shot)


            media = command(["exec-out", "run-as", PACKAGE, "cat", "files/schema4-media/ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"])
            need(media == b"abc", "independent original media bytes")
            receipt["phases"][phase]["media_sha256"] = digest(media)
            save()
        need(receipt["snapshots"]["seed"] == receipt["snapshots"]["reopen"],
             "independent restart/restore cells differ")
        bridge_receipt(receipt)
        validate_activation_ui_receipt(receipt)
        validate_native_ui_receipt(receipt)
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
    bridge_receipt(value)
    ui_receipt(value)
    activation_receipt(value)
    ui_receipt({'ui_snapshots':value['startup_snapshots']})
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
                 business_snapshots={p:copy.deepcopy(snapshots) for p in LABELS},
                 ui_snapshots={p:copy.deepcopy(snapshots) for p in LABELS},
                 activation_snapshots={p:copy.deepcopy(snapshots) for p in LABELS},
                 startup_snapshots={p:copy.deepcopy(snapshots) for p in LABELS},
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
                replay_shortcut_databases(folder,receipt,phase)
                replay_activation_ui(folder, receipt, phase)
                replay_native_ui(folder, receipt, phase)
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


def report_selftest(target=None):
    if target is None:target=report
    """Actual report entry; scripted files/database/publisher, not real CI proof."""
    import contextlib
    import io
    import types
    from unittest.mock import patch
    modes=("valid","missing26","failed26","failed34","wrong_attempt",
           "corrupt_log","missing_label","failed_job","snapshot_mismatch","publish_failure","business_missing","business_mismatch","ui_missing","ui_mismatch","activation_missing","activation_mismatch","startup_missing","startup_mismatch")
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
                if path.name=="schema4-startup.db" and mode=="startup_missing":raise OSError("startup DB missing")
                if path.name=="schema4-startup.db" and mode=="startup_mismatch":
                    changed=copy.deepcopy(value["startup_snapshots"]["seed"]);changed["todos"]["rows"]=[];return changed
                if path.name=="schema4-activation.db" and mode=="activation_missing":raise OSError("activation DB missing")
                if path.name=="schema4-activation.db" and mode=="activation_mismatch":
                    changed=copy.deepcopy(value["activation_snapshots"]["seed"]);changed["todos"]["rows"]=[];return changed
                if path.name=="schema4-ui.db" and mode=="ui_missing":raise OSError("original missing UI DB")
                data=copy.deepcopy(value["snapshots"]["seed"])
                if path.name=="schema4-ui.db" and mode=="ui_mismatch":data["todos"]["rows"]=[]
                if mode=="snapshot_mismatch":data["todos"]["rows"]=[]
                return data
            def business_snapshot(path):
                if mode=="business_missing":raise OSError("original missing business DB")
                data=copy.deepcopy(value["business_snapshots"]["seed"])
                if mode=="business_mismatch":data["todos"]["rows"]=[]
                return data
            scope=dict(globals(),ROOT=root,source_identity=lambda:sources,database_snapshot=snapshot,
                       bridge_database_snapshot=business_snapshot)
            # Rebind this helper too, so scripted readers cover the real report call.
            scope["replay_shortcut_databases"]=types.FunctionType(replay_shortcut_databases.__code__,scope)
            scope["replay_activation_ui"]=legacy_activation_report_double
            scope["replay_native_ui"]=legacy_native_report_double
            runner=types.FunctionType(target.__code__,scope)
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
            else:need(type(error) is AssertionError and sent[0]["status"]=="FAIL","invalid report not rejected: "+mode)
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


"""Execute actual Java snapshot transformers, not Python reimplementations."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

TABLES = "revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports".split()


def code_mask(text):
    """Keep offsets, strip Java strings/chars/comments before balancing braces."""
    out = list(text)
    i = 0
    while i < len(text):
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            assert end >= 0, "unterminated Java comment"
            end += 2
        elif text[i] in "\"'":
            quote, end = text[i], i + 1
            while end < len(text):
                if text[end] == "\\":
                    end += 2
                elif text[end] == quote:
                    end += 1
                    break
                else:
                    end += 1
            else:
                raise AssertionError("unterminated Java literal")
        else:
            i += 1
            continue
        for n in range(i, end):
            if text[n] != "\n":
                out[n] = " "
        i = end
    return "".join(out)


def region(text, signature):
    masked = code_mask(text)
    assert masked.count(signature) == 1, ("missing/ambiguous declaration", signature)
    start = masked.index(signature)
    brace = masked.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        assert end < len(text), "unbalanced Java region"
        depth += (masked[end] == "{") - (masked[end] == "}")
        end += 1
    return start, end


def extract(text, signature):
    a, b = region(text, signature)
    return text[a:b]


SUPPORT = r'''
import java.io.*;import java.nio.charset.*;import java.util.*;
public class BridgeGate {
static class Cursor {static final int FIELD_TYPE_NULL=0,FIELD_TYPE_INTEGER=1,FIELD_TYPE_STRING=3,FIELD_TYPE_BLOB=4;}
static final String[] SNAPSHOT_TABLES="revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports".split(" ");
static class LimitedBytes extends ByteArrayOutputStream {}
static void require(boolean b,String s){if(!b)throw new IllegalArgumentException(s);}
static void utf8(DataOutputStream out,String s)throws IOException{blob(out,s.getBytes(StandardCharsets.UTF_8));}
static void blob(DataOutputStream out,byte[] b)throws IOException{out.writeInt(b.length);out.write(b);}
static byte[] readBlob(DataInputStream in)throws IOException{int n=in.readInt();require(n>=0&&n<=in.available(),"size");byte[] b=new byte[n];in.readFully(b);return b;}
static String readText(DataInputStream in)throws IOException{return new String(readBlob(in),StandardCharsets.UTF_8);}
__METHODS__
static byte[] fixture(int version,boolean renamed,long application)throws Exception{
 ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);
 out.writeInt(0x4e444c31);out.writeInt(version);out.writeInt(version==4?19:18);
 for(String table:SNAPSHOT_TABLES){
  utf8(out,table);
  if(table.equals("revision")){
   out.writeInt(3);for(String n:new String[]{"id","id","value"})utf8(out,n);out.writeInt(1);
   for(long v:new long[]{1,1,renamed?43:42}){out.writeByte(1);out.writeLong(v);}
  }else if(table.equals("applications")){
   out.writeInt(4);for(String n:new String[]{"id","id","name","package_name"})utf8(out,n);out.writeInt(1);
   out.writeByte(1);out.writeLong(10);out.writeByte(1);out.writeLong(10);
   out.writeByte(3);utf8(out,renamed?"new":"old");out.writeByte(3);utf8(out,"");
  }else{out.writeInt(1);utf8(out,"sentinel");out.writeInt(0);}
 }
 if(version==4){utf8(out,"category_shortcuts");out.writeInt(2);utf8(out,"category_id");utf8(out,"application_id");out.writeInt(1);out.writeByte(1);out.writeLong(7);out.writeByte(1);out.writeLong(application);}
 out.flush();return bytes.toByteArray();
}
public static void main(String[] args)throws Exception{
 for(int version:new int[]{2,3}){
  byte[] old=fixture(version,false,10),want=fixture(version,true,10);
  if(!Arrays.equals(want,applicationRenameExpected(old,10,"new",43)))throw new AssertionError("LEGACY_CHANGED");
 }
 System.out.println("LEGACY_2_3_BEHAVIOR_WITNESS");
 if(args.length>0&&args[0].equals("legacy"))return;
 byte[] before=fixture(4,false,10),expected=fixture(4,true,10),actual;
 try{actual=applicationRenameExpected(before,10,"new",43);}
 catch(IllegalArgumentException missing){throw new AssertionError("BRIDGE_SCHEMA4_REJECTED",missing);}
 if(!Arrays.equals(expected,actual))throw new AssertionError("BRIDGE_RELATION_NOT_PRESERVED");
 if(Arrays.equals(actual,fixture(4,true,11)))throw new AssertionError("BRIDGE_RELATION_NOT_OBSERVED");
 byte[] tail=Arrays.copyOf(before,before.length+1);
 try{applicationRenameExpected(tail,10,"new",43);throw new AssertionError("TRAILING_ACCEPTED");}
 catch(IllegalArgumentException expectedRejection){}
 System.out.println("BRIDGE_TRANSFORM_BEHAVIOR_PASS");
}
}
'''


def java_source(text):
    methods = [extract(text, "private static byte[] applicationRenameExpected(")]
    if "private static String[] comparisonTables(" in code_mask(text):
        methods.insert(0, extract(text, "private static String[] comparisonTables("))
    return SUPPORT.replace("__METHODS__", "\n".join(methods))


def execute(text, args=()):
    with tempfile.TemporaryDirectory(prefix="bridge-java-") as directory:
        p = Path(directory)
        (p / "BridgeGate.java").write_text(java_source(text))
        command = ["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", "-encoding", "UTF-8", "-d", directory, str(p / "BridgeGate.java")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, "GATE_COMPILE_FAILED\n" + result.stdout + result.stderr
        return subprocess.run(["java", "-cp", directory, "BridgeGate", *args], capture_output=True, text=True, timeout=60)


def scanner_test():
    text = '// private static void x( {\nprivate static void x(){String s="}";char c=\'{\';/* } */ if(true){}}\n'
    assert extract(text, "private static void x(").endswith("if(true){}}")
    try:
        region(text + text, "private static void x(")
    except AssertionError:
        pass
    else:
        raise AssertionError("ambiguous declaration accepted")
    print("JAVA_SCANNER_LITERAL_COMMENT_AND_AMBIGUITY_CONTROLS_PASS")



def bridge_selftest():
    scanner_test()
    source = (ROOT / "src/main/java/com/supercubegame/pockettodo/AppDatabase.java").read_text()
    result = execute(source)
    need(result.returncode == 0, result.stdout + result.stderr)
    print(result.stdout.strip())
    a,b=region(source,"private static byte[] applicationRenameExpected(")
    target=source[a:b]
    anchor = "if(version==4){"
    need(target.count(anchor) == 1, "bridge mutation anchor")
    mutant = source[:a]+target.replace(anchor,"if(version==5){",1)+source[b:]
    witness = execute(mutant, ("legacy",))
    killed = execute(mutant)
    need(witness.returncode == 0 and "LEGACY_2_3_BEHAVIOR_WITNESS" in witness.stdout,
         "bridge mutant invalid legacy witness")
    need(killed.returncode != 0 and "BRIDGE_SCHEMA4_REJECTED" in killed.stderr,
         "bridge omitted relation mutant survived")
    need((ROOT / "AGENTS.md").read_bytes() == (ROOT / "CLAUDE.md").read_bytes() and
         len((ROOT / "AGENTS.md").read_text().splitlines()) <= 200, "bridge instructions match and fit")
    print("BRIDGE_TRANSFORM_LEGACY_AND_MUTATION_PASS")


def bridge_database_snapshot(path):
    result = {}
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as db:
        need(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "bridge integrity")
        need(db.execute("PRAGMA foreign_key_check").fetchall() == [], "bridge foreign keys")
        need(db.execute("PRAGMA user_version").fetchone() == (4,), "bridge version")
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                 if not r[0].startswith("sqlite_") and r[0] != "android_metadata"}
        need(names == set(OLD_TABLES+["category_shortcuts"]), "bridge complete table set")
        for table in OLD_TABLES+["category_shortcuts"]:
            old = table != "category_shortcuts"
            cursor = db.execute("SELECT "+("rowid,*" if old else "*")+" FROM "+table+" ORDER BY "+("rowid" if old else "category_id,application_id"))
            columns = [x[0] for x in cursor.description]
            rows = []
            for row in cursor:
                typed = []
                for value in row:
                    need(value is None or type(value) in (int,str,bytes), "bridge typed cell")
                    typed.append(["null",None] if value is None else ["integer",value] if type(value) is int else ["text",value] if type(value) is str else ["blob",value.hex()])
                rows.append(typed)
            result[table] = dict(columns=columns,rows=rows)
        need(db.execute("SELECT category_id,application_id FROM category_shortcuts ORDER BY 1,2").fetchall()==[(7,10),(8,10)], "bridge exact links")
        need(db.execute("SELECT id,name FROM applications").fetchall()==[(10,"新应用")], "bridge renamed application")
        need(db.execute("SELECT id,title,done FROM todos").fetchall()==[("bt","待办",0)], "bridge restored todo")
        need(db.execute("SELECT activity_id,field_id,value FROM field_values").fetchall()==[(20,"bf","值")], "bridge field value")
        need(db.execute("SELECT note_id,field_id FROM field_notes").fetchall()==[("bfn","bf")], "bridge field note")
        need(db.execute("SELECT count(*) FROM blocks").fetchone()==(3,), "bridge all note blocks")
    return result


def bridge_receipt(value):
    need(set(value["business_snapshots"]) == {"seed","reopen"}, "bridge phase population")
    for phase in ("seed","reopen"):
        snapshot = value["business_snapshots"][phase]
        need(set(snapshot) == set(OLD_TABLES+["category_shortcuts"]), "bridge receipt tables")
        for table in ("revision","categories","applications","activities","paths","tags","media","notes","blocks","fields","field_values","field_notes","todos","category_shortcuts"):
            need(snapshot[table]["rows"], "bridge required rows "+table)
    need(value["business_snapshots"]["seed"] == value["business_snapshots"]["reopen"], "bridge restart typed cells")


def bridge_receipt_selftest():
    good,_,_ = receipt_fixture()
    bridge_receipt(good)
    cases = []
    bad=copy.deepcopy(good);del bad["business_snapshots"];cases.append(bad)
    for phase in ("seed","reopen"):
        bad=copy.deepcopy(good);del bad["business_snapshots"][phase];cases.append(bad)
        for table in OLD_TABLES+["category_shortcuts"]:
            bad=copy.deepcopy(good);del bad["business_snapshots"][phase][table];cases.append(bad)
        bad=copy.deepcopy(good);bad["business_snapshots"][phase]["category_shortcuts"]["rows"]=[];cases.append(bad)
    for bad in cases:
        try:bridge_receipt(bad)
        except (KeyError,AssertionError):pass
        else:raise AssertionError("bridge evidence omission accepted")
    print("BRIDGE_RECEIPT_OMISSION_CONTROLS_PASS",len(cases))


"""Permanent host contract for actual Java need-call labels, not all strings."""
BRIDGE_LABELS = {
    "seed": [
        "bridge_one_connection_and_schema4",
        "bridge_note_write_preserves_links_and_origins",
        "bridge_field_and_field_note_operations",
        "bridge_catalog_paths_archive_and_pure_navigation",
        "bridge_todo_delete_undo_preserves_shortcuts",
        "bridge_same_revision_relation_change_invalidates_plan",
        "bridge_late_business_failure_rolls_back_exactly",
        "bridge_unrelated_relation_mutation_rolls_back",
        "bridge_backup_preview_has_all_tables_and_no_writes",
        "bridge_foreign_restore_does_not_consume_owner_plan",
        "bridge_restore_detects_same_revision_link_edit",
        "bridge_restore_late_failure_preserves_every_table",
        "bridge_close_invalidates_business_session",
        "bridge_unknown_table_refused_without_partial_write",
        "bridge_live_database_name_refused",
    ],
    "reopen": [
        "bridge_separate_process_all_cells_and_wire_exact",
        "bridge_separate_process_business_reads_are_pure",
    ],
}

LABEL_AST = r'''
import java.nio.file.*;import java.util.*;import javax.tools.*;
import com.sun.source.tree.*;import com.sun.source.util.*;
public class WireTest {
 public static void main(String[] args)throws Exception{
  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();
  if(compiler==null)throw new AssertionError("JDK_REQUIRED");
  for(int index=0;index<args.length;index++){
   final int file=index;
   DiagnosticCollector<JavaFileObject> diagnostics=new DiagnosticCollector<>();
   try(StandardJavaFileManager manager=compiler.getStandardFileManager(diagnostics,null,null)){
    JavacTask task=(JavacTask)compiler.getTask(null,manager,diagnostics,List.of("-proc:none"),null,
       manager.getJavaFileObjects(Path.of(args[index]).toFile()));
    List<CompilationUnitTree> units=new ArrayList<>();
    for(CompilationUnitTree unit:task.parse())units.add(unit);
    if(diagnostics.getDiagnostics().stream().anyMatch(d->d.getKind()==Diagnostic.Kind.ERROR))
      throw new AssertionError("JAVA_PARSE_ERROR "+diagnostics.getDiagnostics());
    SourcePositions positions=Trees.instance(task).getSourcePositions();
    Map<String,Integer> methods=new HashMap<>();
    for(CompilationUnitTree unit:units)new TreeScanner<Void,Void>(){
     @Override public Void visitMethod(MethodTree method,Void ignored){
      String name=method.getName().toString();
      if(!name.equals("bridgeSeed")&&!name.equals("bridgeReopen"))return null;
      methods.merge(name,1,Integer::sum);
      if(method.getBody()==null)throw new AssertionError("MISSING_METHOD_BODY");
      new TreeScanner<Void,Void>(){
       @Override public Void visitMethodInvocation(MethodInvocationTree call,Void unused){
        ExpressionTree select=call.getMethodSelect();
        boolean target=select instanceof IdentifierTree && ((IdentifierTree)select).getName().contentEquals("need");
        if(select instanceof MemberSelectTree){
         MemberSelectTree member=(MemberSelectTree)select;
         target=member.getIdentifier().contentEquals("need")&&member.getExpression().toString().equals("this");
        }
        if(target){
         if(call.getArguments().size()!=2)throw new AssertionError("LABEL_ARGUMENT_COUNT");
         ExpressionTree label=call.getArguments().get(1);
         if(!(label instanceof LiteralTree)||!(((LiteralTree)label).getValue() instanceof String))
           throw new AssertionError("LITERAL_LABEL_REQUIRED");
         String value=(String)((LiteralTree)label).getValue();
         if(!value.matches("bridge_[a-z0-9_]+"))throw new AssertionError("LABEL_FORMAT");
         System.out.println(file+"\t"+name+"\t"+value+"\t"+positions.getStartPosition(unit,call)+"\t"+positions.getEndPosition(unit,call));
        }
        return super.visitMethodInvocation(call,unused);
       }
      }.scan(method.getBody(),null);
      return null;
     }
    }.scan(unit,null);
    if(!methods.equals(Map.of("bridgeSeed",1,"bridgeReopen",1)))
      throw new AssertionError("EXACT_BRIDGE_METHODS "+methods);
   }
  }
 }
}
'''


def java_label_calls(sources):
    # Actual JDK parser, parse-only: Android names are deliberately not resolved.
    # This proves call-site structure, not device execution or branch reachability.
    with tempfile.TemporaryDirectory(prefix="shortcut-label-ast-") as temp:
        paths=[]
        for index, text in enumerate(sources):
            path=Path(temp)/("Source"+str(index)+".java")
            path.write_text(text)
            paths.append(str(path))
        result=java_run(LABEL_AST, paths)
    need(result.returncode==0, "label AST failed:\n"+result.stdout+result.stderr)
    rows=[[] for _ in sources]
    for line in result.stdout.splitlines():
        index,method,label,start,end=line.split("\t")
        rows[int(index)].append((method,label,int(start),int(end)))
    return rows


def check_bridge_labels(rows, expected=BRIDGE_LABELS):
    observed={p:[r[1] for r in rows if r[0]==m]
              for p,m in (("seed","bridgeSeed"),("reopen","bridgeReopen"))}
    need(observed==expected, "actual Java need-call label contract differs: "+repr(observed))


def label_contract_selftest():
    source=DEVICE.read_text()
    # Independent hand-written oracle. Neither the runtime parser nor AST output
    # generates this expected list. Comments/exception strings are not checks.
    sample=r'''class Sample {
      void bridgeSeed(){
        // need(false,"bridge_comment");
        String s="need(false,\"bridge_string\");";
        refused(()->work(),"bridge_late_fault");
        need(true,"bridge_sample4");
        this.need(true,"bridge_sample_tail");
      }
      void bridgeReopen(){refused(()->work(),"bridge_restore_late");}
    }'''
    rows,sample_rows=java_label_calls([source,sample])
    check_bridge_labels(rows)
    check_bridge_labels(sample_rows,{"seed":["bridge_sample4","bridge_sample_tail"],"reopen":[]})
    for phase, count in (("seed",32),("reopen",6)):
        need(len(LABELS[phase])==count+len(BRIDGE_LABELS[phase])+len(UI_LABELS[phase])+len(ACTIVATION_LABELS[phase])+len(STARTUP_LABELS[phase]) and
             LABELS[phase][count:count+len(BRIDGE_LABELS[phase])]==BRIDGE_LABELS[phase], "fixed phase label population "+phase)
    variants=[]
    # AST positions refer to Java UTF-16 indices. Convert before Python slicing.
    def offset(value):
        return len(source.encode("utf-16-le")[:value*2].decode("utf-16-le"))
    for row in rows:
        a,b=offset(row[2]),offset(row[3])
        call=source[a:b]
        need(call.startswith(("need(","this.need(")), "AST source position witness")
        variants.append(source[:a]+source[b:])
    first,second=rows[:2]
    a,b,c,d=map(offset,(first[2],first[3],second[2],second[3]))
    variants.append(source[:a]+source[a:b]+";"+source[a:])
    variants.append(source[:a]+source[c:d]+source[b:c]+source[a:b]+source[d:])
    literal='"'+first[1]+'"'
    call=source[a:b]
    need(call.count(literal)==1,"literal rename witness")
    variants.append(source[:a]+call.replace(literal,'"bridge_wrong4"',1)+source[b:])
    killed=0
    for actual in java_label_calls(variants):
        try:check_bridge_labels(actual)
        except AssertionError:killed+=1
        else:raise AssertionError("Java label call-site mutant survived")
    need(killed==len(rows)+3,"label mutant population")
    # Runtime ordered-label controls also reject duplicate/reordered/foreign
    # checks; the existing per-label omission controls remain unchanged.
    for phase in LABELS:
        for api in (26,34):
            raw=fixture(phase,api);parse_phase(raw,phase,api)
            lines=raw.splitlines(keepends=True)
            bads=[b"".join([lines[1],lines[0],*lines[2:]]),
                  lines[0]+raw,raw.replace(lines[0],b"SHORTCUT_PASS bridge_wrong4\n",1)]
            for bad in bads:
                try:parse_phase(bad,phase,api)
                except AssertionError:pass
                else:raise AssertionError("runtime ordered-label mutant survived")
    print("SHORTCUT_LABEL_AST actual_checks=17 callsite_mutants="+str(killed)+
          " runtime_controls=12 DIGIT_COMMENT_STRING_EXCEPTION_CONTROLS_PASS")


UI_LABELS = {
    "seed": [
        "ui_preview_cancel_is_read_only",
        "ui_closed_preview_cannot_write_after_relaunch",
        "ui_add_exact_relation_no_business_copy",
        "ui_targets_exclude_archived_and_do_not_write",
        "ui_same_name_navigation_exact_and_pure",
        "ui_detached_callback_cannot_replay",
        "ui_removed_link_refuses_stale_navigation",
        "ui_remove_retains_other_category_and_history",
        "ui_api_repeat_setting_exact_noop",
        "ui_api_same_revision_edit_refused",
        "ui_api_foreign_attempt_preserves_owner_plan",
        "ui_api_close_invalidates_plan",
        "ui_api_late_failure_rolls_back_all_cells",
        "ui_api_unrelated_write_rolls_back",
        "ui_backup_restore_keeps_relations_and_history",
        "ui_activity_relaunch_preserves_exact_state",
        "ui_never_opens_phone_database",
    ],
    "reopen": [
        "ui_separate_process_exact_state",
        "ui_separate_process_navigation_pure",
        "ui_separate_process_live_database_absent",
    ],
}


def ui_receipt(value):
    need(set(value["ui_snapshots"])=={"seed","reopen"},"UI phase population")
    for phase in ("seed","reopen"):
        snapshot=value["ui_snapshots"][phase]
        need(set(snapshot)==set(OLD_TABLES+["category_shortcuts"]),"UI complete table set")
        need(all(row["rows"] for row in snapshot.values()),"UI all-table nonempty fixture")
    need(value["ui_snapshots"]["seed"]==value["ui_snapshots"]["reopen"],"UI restart exact cells")


def replay_shortcut_databases(folder,receipt,phase):
    need(bridge_database_snapshot(folder/phase/"schema4-business.db")==receipt["business_snapshots"][phase],
         "report independent business replay differs")
    need(database_snapshot(folder/phase/"schema4-ui.db")==receipt["ui_snapshots"][phase],
         "report independent UI replay differs")
    need(database_snapshot(folder/phase/"schema4-startup.db")==receipt["startup_snapshots"][phase],
         "report independent startup replay differs")
    need(database_snapshot(folder/phase/"schema4-activation.db")==receipt["activation_snapshots"][phase],
         "report independent activation replay differs")


def ui_host_selftest():
    ui_shape_dependency_selftest()
    """Actual Java guard plus actual Java call sites, not Android acceptance."""
    import types
    source=(ROOT/"src/main/java/com/supercubegame/pockettodo/ActivitiesScreen.java").read_text()
    actual=extract(source,"static boolean shortcutCanAct(")
    controls=r'''
class ShortcutGuard {
__METHOD__
public static void main(String[] args){
 if(!shortcutCanAct(true,false,true,true,false,false))throw new AssertionError("positive");
 if(args.length>0)return;
 boolean[][] cases={{false,false,true,true,false,false},{true,true,true,true,false,false},
   {true,false,false,true,false,false},{true,false,true,false,false,false},
   {true,false,true,true,true,false},{true,false,true,true,false,true}};
 for(int i=0;i<cases.length;i++){
  boolean[] c=cases[i];
  if(shortcutCanAct(c[0],c[1],c[2],c[3],c[4],c[5]))throw new AssertionError("GUARD_NEGATIVE_"+i);
 }
 System.out.println("SHORTCUT_GUARD_REAL_JAVA_PASS");
}}
'''
    def execute_guard(method,args=()):
        with tempfile.TemporaryDirectory(prefix="shortcut-guard-") as temp:
            p=Path(temp)/"ShortcutGuard.java";p.write_text(controls.replace("__METHOD__",method))
            c=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-encoding","UTF-8",str(p)],capture_output=True,text=True,timeout=30)
            need(c.returncode==0,"UI guard compile "+c.stderr)
            return subprocess.run(["java","-cp",temp,"ShortcutGuard",*args],capture_output=True,text=True,timeout=30)
    good=execute_guard(actual);need(good.returncode==0,good.stdout+good.stderr)
    for index,(old,new) in enumerate((("return alive","return true"),("!submitted","true"),
            ("&&attached","&&true"),("&&enabled","&&true"),("!finishing","true"),("!destroyed","true"))):
        need(actual.count(old)==1,"UI mutation anchor")
        mutant=actual.replace(old,new,1)
        need(execute_guard(mutant,("positive",)).returncode==0,"UI mutant positive witness")
        result=execute_guard(mutant)
        need(result.returncode!=0 and "GUARD_NEGATIVE_"+str(index) in result.stderr,"UI guard mutant survived")
    test=DEVICE.read_text()
    ast_source=LABEL_AST.replace("bridgeSeed","uiSeed").replace("bridgeReopen","uiReopen").replace("bridge_[a-z0-9_]+","ui_[a-z0-9_]+")
    parse=types.FunctionType(java_label_calls.__code__,dict(globals(),LABEL_AST=ast_source))
    rows=parse([test])[0]
    def check(rows):
        observed={p:[r[1] for r in rows if r[0]==m] for p,m in (("seed","uiSeed"),("reopen","uiReopen"))}
        need(observed==UI_LABELS,"UI actual Java need-call label contract")
    check(rows)
    for phase in UI_LABELS:
        need(LABELS[phase][-len(UI_LABELS[phase]):]==UI_LABELS[phase],"UI ordered runtime labels")
    mutants=[]
    for row in rows:
        a=len(test.encode("utf-16-le")[:row[2]*2].decode("utf-16-le"))
        b=len(test.encode("utf-16-le")[:row[3]*2].decode("utf-16-le"))
        mutants.append(test[:a]+test[b:])
    for parsed in parse(mutants):
        try:check(parsed)
        except AssertionError:pass
        else:raise AssertionError("UI omitted check survived")
    value,expected,sources=receipt_fixture()
    ui_receipt(value)
    bad=copy.deepcopy(value);bad["ui_snapshots"]["reopen"]["todos"]["rows"]=[]
    try:validate_receipt(bad,expected,26,sources)
    except AssertionError:pass
    else:raise AssertionError("UI missing snapshot accepted")
    import ast,inspect
    tree=ast.parse(inspect.getsource(report))
    removed=[]
    class OmitReplay(ast.NodeTransformer):
        def visit_Expr(self,node):
            if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=="replay_shortcut_databases":
                removed.append(node);return None
            return self.generic_visit(node)
    changed=OmitReplay().visit(tree);need(len(removed)==1,"report replay mutation applied")
    scope=dict(globals());exec(compile(ast.fix_missing_locations(changed),"<omitted-db-replay>","exec"),scope)
    try:report_selftest(scope["report"])
    except AssertionError as exc:need(str(exc)=="invalid report not rejected: business_missing","wrong replay mutant witness")
    else:raise AssertionError("omitted business DB replay survived")
    print("SHORTCUT_UI_HOST guard_positive=1 guard_negatives=6 witnessed_guard_mutants=6 omitted_call_mutants="+str(len(mutants))+" PASS_NOT_ANDROID")


"""API shapes only. No modeled UI behavior and no Android acceptance claim."""
SHAPE_BASELINE_STUBS = dict(STUBS)
_app = "com/supercubegame/pockettodo/AppDatabase.java"
need(STUBS[_app].endswith("\n}"), "AppDatabase shape anchor")
STUBS[_app] = STUBS[_app][:-2] + """
public static class ShortcutPlan implements AutoCloseable{public void close(){}}
public ShortcutPlan prepareShortcut(long c,long a){return null;}
public boolean confirmShortcut(ShortcutPlan p,boolean enabled){return false;}
}
"""
_instrumentation = "android/app/Instrumentation.java"
need(STUBS[_instrumentation].endswith("\n}"), "Instrumentation shape anchor")
STUBS[_instrumentation] = STUBS[_instrumentation][:-2] + """
public void runOnMainSync(Runnable r){}
public void waitForIdleSync(){}
public void sendPointerSync(android.view.MotionEvent event){}
public Activity startActivitySync(android.content.Intent intent){return null;}
public UiAutomation getUiAutomation(){return null;}
}
"""
STUBS.update({
    "android/content/Intent.java": """package android.content;public class Intent{
public static final int FLAG_ACTIVITY_NEW_TASK=0x10000000;
public Intent(Context context,Class<?> cls){}public Intent addFlags(int flags){return this;}
}""",
    "android/view/View.java": """package android.view;public class View{
public CharSequence getContentDescription(){return null;}
public boolean isAttachedToWindow(){return false;}public boolean isEnabled(){return false;}
public int getWidth(){return 0;}public int getHeight(){return 0;}
public boolean requestRectangleOnScreen(android.graphics.Rect r,boolean immediate){return false;}
public boolean getGlobalVisibleRect(android.graphics.Rect r){return false;}
public boolean performClick(){return false;}
}""",
    "android/view/ViewGroup.java": """package android.view;public class ViewGroup extends View{
public int getChildCount(){return 0;}public View getChildAt(int index){return null;}
}""",
    "android/view/Window.java": """package android.view;public class Window{
public View getDecorView(){return null;}
}""",
    "android/graphics/Rect.java": """package android.graphics;public class Rect{
public Rect(){}public Rect(int l,int t,int r,int b){}
public int width(){return 0;}public int height(){return 0;}
public float exactCenterX(){return 0;}public float exactCenterY(){return 0;}
}""",
    "android/view/MotionEvent.java": """package android.view;public class MotionEvent{
public static final int ACTION_DOWN=0,ACTION_UP=1;
public static MotionEvent obtain(long down,long event,int action,float x,float y,int meta){return null;}
public void recycle(){}
}""",
    "android/os/SystemClock.java": """package android.os;public class SystemClock{
public static long uptimeMillis(){return 0;}
}""",
    "android/widget/TextView.java": """package android.widget;public class TextView extends android.view.View{
public CharSequence getText(){return null;}
}""",
    "android/graphics/Bitmap.java": """package android.graphics;public class Bitmap{
public enum CompressFormat{PNG}
public boolean compress(CompressFormat format,int quality,java.io.OutputStream out){return false;}
public void recycle(){}
}""",
    "android/app/UiAutomation.java": """package android.app;public class UiAutomation{
public android.graphics.Bitmap takeScreenshot(){return null;}
}""",
    "com/supercubegame/pockettodo/MainActivity.java": """package com.supercubegame.pockettodo;
public class MainActivity extends android.app.Activity{
static boolean isolatedShortcutTest;
TodayScreen shortcutTestScreen(){return null;}
public android.view.Window getWindow(){return null;}public void finish(){}
}""",
    "com/supercubegame/pockettodo/TodayScreen.java": """package com.supercubegame.pockettodo;
public class TodayScreen{boolean awaitShortcutClose()throws InterruptedException{return false;}}
""",
})


def ui_shape_dependency_selftest():
    """Same whole-source compiler for GREEN, original RED and omitted declarations."""
    import contextlib,io,types
    def compile_with(stubs):
        scope=dict(globals(),STUBS=stubs)
        runner=types.FunctionType(syntax_selftest.__code__,scope)
        with contextlib.redirect_stdout(io.StringIO()):
            runner()
    # The complete candidate is the input in every case. Nothing is sliced out.
    compile_with(STUBS)
    cases=[("original",SHAPE_BASELINE_STUBS,"ShortcutPlan")]
    for path,old,new,witness in (
        (_app,"public ShortcutPlan prepareShortcut(","public ShortcutPlan omittedPrepareShortcut(","prepareShortcut"),
        (_instrumentation,"public void sendPointerSync(","public void omittedSendPointerSync(","sendPointerSync"),
        ("com/supercubegame/pockettodo/TodayScreen.java","boolean awaitShortcutClose(","boolean omittedAwaitShortcutClose(","awaitShortcutClose"),
    ):
        mutant=dict(STUBS)
        need(mutant[path].count(old)==1,"shape omission declaration anchor")
        mutant[path]=mutant[path].replace(old,new,1)
        need(mutant[path]!=STUBS[path],"shape omission did not occur")
        cases.append((witness,mutant,witness))
    for name,stubs,witness in cases:
        try:compile_with(stubs)
        except AssertionError as exc:
            message=str(exc)
            need("new-class Java syntax failed:" in message and
                 "cannot find symbol" in message and witness in message,
                 "shape RED for wrong reason: "+name+"\n"+message)
        else:raise AssertionError("shape declaration omission survived: "+name)
    print("SHORTCUT_UI_API_SHAPE original RED / full-source GREEN / 3 omission controls PASS; NOT_ANDROID")


ACTIVATION_LABELS={'seed': ['activation_original_schema3_nonempty', 'activation_resume_schema3_never_migrates', 'activation_resume_missing_never_creates', 'activation_resume_empty_preserved', 'activation_resume_corrupt_never_deleted', 'activation_resume_future_exact_preservation', 'activation_resume_symlink_refused', 'activation_preview_backup_without_migration', 'activation_cancel_refuses_replay', 'activation_foreign_attempt_never_opens_database', 'activation_same_revision_change_refused', 'activation_failed_attempt_consumed', 'activation_changed_backup_refused', 'activation_missing_backup_refused', 'activation_changed_media_refused', 'activation_helper_close_expires_consent', 'activation_outer_transaction_refused', 'activation_atomic_schema4_preserves_all_cells', 'activation_retains_verified_backup_and_media', 'activation_new_facade_supports_shortcuts', 'activation_resume_one_existing_connection', 'activation_resume_exact_state_and_links', 'activation_resume_closed_cannot_reopen', 'activation_never_touches_phone_database'], 'reopen': ['activation_separate_process_exact_state', 'activation_separate_process_relations', 'activation_separate_process_phone_database_absent']}
"""Execute the actual Java consent class extracted from complete product source.
SQL, Android storage, UI and phone behavior are explicitly outside this host gate.
"""
import hashlib,json,pathlib,subprocess,tempfile

def activation_extract(source):
    # Reuse the existing language-aware scanner; do not regex nested Java.
    from verify_shortcuts import extract as region
    return region(source,"static final class ActivationConsent ")

ACTIVATION_JAVA=r'''
import java.util.*;
public class ActivationGate{
__CLASS__
static int checks;
static void need(boolean b,String reason){if(!b)throw new AssertionError(reason);checks++;}
interface Action{void run();}
static void reject(Action action,String reason){
 try{action.run();}catch(IllegalArgumentException|IllegalStateException expected){
  need(expected.getMessage().contains(reason),"wrong refusal "+reason);return;
 }throw new AssertionError("accepted "+reason);
}
static byte[] digest(int n){byte[] b=new byte[32];b[0]=(byte)n;return b;}
static void valid(){
 Object o=new Object(),s=new Object(),c=new Object();
 ActivationConsent p=new ActivationConsent(o,s,c,new byte[]{1},digest(2));
 p.consume(o,s,c,new byte[]{1},digest(2));checks++;
}
public static void main(String[] args){
 valid();System.out.println("VALID_CONSENT_WITNESS");
 if(args.length>0&&args[0].equals("witness"))return;
 Object o=new Object(),s=new Object(),c=new Object();
 ActivationConsent p=new ActivationConsent(o,s,c,new byte[]{1},digest(2));
 reject(()->p.consume(new Object(),s,c,new byte[]{1},digest(2)),"Foreign");
 p.consume(o,s,c,new byte[]{1},digest(2));checks++;
 reject(()->p.consume(o,s,c,new byte[]{1},digest(2)),"expired");
 ActivationConsent cancelled=new ActivationConsent(o,s,c,new byte[]{1},digest(2));
 cancelled.close();reject(()->cancelled.consume(o,s,c,new byte[]{1},digest(2)),"expired");
 for(int mode=0;mode<4;mode++){
  ActivationConsent x=new ActivationConsent(o,s,c,new byte[]{1},digest(2));
  final int m=mode;
  reject(()->x.consume(o,m==0?new Object():s,m==1?new Object():c,
                      m==2?new byte[]{9}:new byte[]{1},digest(m==3?9:2)),"changed");
  reject(()->x.consume(o,s,c,new byte[]{1},digest(2)),"expired");
 }
 byte[] cells={1},archive=digest(2);
 ActivationConsent copied=new ActivationConsent(o,s,c,cells,archive);
 cells[0]=9;archive[0]=9;
 boolean copyAccepted=true;
 try{copied.consume(o,s,c,new byte[]{1},digest(2));}catch(IllegalStateException bad){copyAccepted=false;}
 need(copyAccepted,"constructor did not freeze bytes");
 reject(()->new ActivationConsent(null,s,c,new byte[]{1},digest(2)),"Invalid");
 reject(()->new ActivationConsent(o,null,c,new byte[]{1},digest(2)),"Invalid");
 reject(()->new ActivationConsent(o,s,null,new byte[]{1},digest(2)),"Invalid");
 reject(()->new ActivationConsent(o,s,c,new byte[0],digest(2)),"Invalid");
 reject(()->new ActivationConsent(o,s,c,new byte[8*1024*1024+1],digest(2)),"Invalid");
 reject(()->new ActivationConsent(o,s,c,new byte[]{1},new byte[31]),"Invalid");
 System.out.println("ACTUAL_JAVA_CONSENT_PASS checks="+checks);
}
}
'''

def activation_execute(declaration,mode=None):
    with tempfile.TemporaryDirectory() as folder:
        folder=pathlib.Path(folder)
        (folder/"ActivationGate.java").write_text(ACTIVATION_JAVA.replace("__CLASS__",declaration))
        compiled=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-encoding","UTF-8",
                                 "-d",str(folder),str(folder/"ActivationGate.java")],
                                text=True,capture_output=True,timeout=60)
        assert compiled.returncode==0,compiled.stdout+compiled.stderr
        return subprocess.run(["java","-cp",str(folder),"ActivationGate"]+([] if mode is None else [mode]),
                              text=True,capture_output=True,timeout=30)

def activation_controls(source):
    declaration=activation_extract(source);good=activation_execute(declaration)
    assert good.returncode==0,good.stdout+good.stderr
    edits=[
        ("foreign_owner","attemptedOwner!=owner","false"),
        ("expired",'if(terminal)throw new IllegalStateException("Activation plan expired");\n            try{','if(false)throw new IllegalStateException("Activation plan expired");\n            try{'),
        ("session","if(currentSession!=session||currentConnection!=connection||","if(false||currentConnection!=connection||"),
        ("connection","currentConnection!=connection","false"),
        ("cells","!Arrays.equals(cells,currentCells)","false"),
        ("backup","!Arrays.equals(archive,currentArchive)","false"),
        ("consume_failure","finally{close();}","finally{}"),
        ("copy_cells","this.cells=cells.clone();","this.cells=cells;"),
        ("copy_archive","this.archive=archive.clone();","this.archive=archive;"),
    ]
    rejected=[]
    for name,old,new in edits:
        assert declaration.count(old)==1,("mutation anchor",name)
        mutant=declaration.replace(old,new,1)
        witness=activation_execute(mutant,"witness")
        assert witness.returncode==0 and "VALID_CONSENT_WITNESS" in witness.stdout,name
        result=activation_execute(mutant)
        assert result.returncode!=0 and "AssertionError" in result.stderr,(name,result.stdout,result.stderr)
        rejected.append(dict(name=name,stderr=result.stderr))
    return dict(status="PASS",scope="ACTUAL_JAVA_CONSENT_NOT_SQL_ANDROID_UI_OR_UPGRADE",
                stdout=good.stdout,mutants=rejected,
                declaration_sha256=hashlib.sha256(declaration.encode()).hexdigest())


def activation_receipt(value):
    ui_receipt({"ui_snapshots":value["activation_snapshots"]})

def activation_host_selftest():
    source=JAVA.read_text()
    result=activation_controls(source)
    print("ACTIVATION_CONSENT_HOST "+json.dumps(result))
    import types,ast,inspect
    ast_source=LABEL_AST.replace("bridgeSeed","activationSeed").replace("bridgeReopen","activationReopen").replace("bridge_[a-z0-9_]+","activation_[a-z0-9_]+")
    parse=types.FunctionType(java_label_calls.__code__,dict(globals(),LABEL_AST=ast_source))
    test=DEVICE.read_text()
    def check(rows):
        observed={p:[r[1] for r in rows if r[0]==m] for p,m in (("seed","activationSeed"),("reopen","activationReopen"))}
        need(observed==ACTIVATION_LABELS,"activation actual Java label contract")
    rows=parse([test])[0];check(rows)
    variants=[]
    for row in rows:
        a=len(test.encode("utf-16-le")[:row[2]*2].decode("utf-16-le"))
        b=len(test.encode("utf-16-le")[:row[3]*2].decode("utf-16-le"))
        need(test[a:b].startswith(("need(","this.need(")),"activation AST witness")
        variants.append(test[:a]+test[b:])
    for parsed in parse(variants):
        try:check(parsed)
        except AssertionError:pass
        else:raise AssertionError("activation missing check survived")
    need(len(variants)==27,"activation expected omission population")
    tree=ast.parse(inspect.getsource(replay_shortcut_databases))
    calls=tree.body[0].body
    need(isinstance(calls[-1],ast.Expr) and isinstance(calls[-1].value,ast.Call) and
         isinstance(calls[-1].value.args[-1],ast.Constant) and
         calls[-1].value.args[-1].value=="report independent activation replay differs",
         "activation replay mutation anchor")
    calls.pop()
    scope=dict(globals());exec(compile(ast.fix_missing_locations(tree),"<activation-replay-omission>","exec"),scope)
    probe=types.FunctionType(report_selftest.__code__,scope,report_selftest.__name__,report_selftest.__defaults__)
    try:probe()
    except AssertionError as exc:need(str(exc)=="invalid report not rejected: activation_missing","wrong activation replay witness")
    else:raise AssertionError("activation database replay omission survived")
    print("ACTIVATION_JAVA_CALLSITE_OMISSIONS 27 PASS_NOT_DEVICE")

# Declaration-only compiler dependencies. Actual behavior belongs to Android.
_activation_stub=STUBS[_app]
_activation_at=_activation_stub.rfind("}")
need(_activation_at>=0 and not _activation_stub[_activation_at+1:].strip(),"activation shape anchor")
STUBS[_app]=_activation_stub[:_activation_at]+"""
public static AppDatabase openSchema3(android.content.Context c,String n){return null;}
public static class ShortcutActivationPlan implements AutoCloseable{
public String backupName(){return null;}public void close(){}
}
public ShortcutActivationPlan prepareShortcutActivation(Path p,MediaRepository m)throws IOException{return null;}
public void confirmShortcutActivation(ShortcutActivationPlan p,MediaRepository m)throws IOException{}
}
"""


"""Real Java NIO checks of the actual product file guard; not Android SQLite."""
import pathlib,subprocess,tempfile,json
RESUME_FILE_HARNESS=r'''
import java.io.*;import java.nio.file.*;import java.util.*;
class FileGate{
 MEMBER
 static int checks;
 static void check(boolean value,String name){if(!value)throw new AssertionError(name);checks++;}
 static void refused(Path p,String name)throws Exception{
  boolean denied=false;try{resumeFile(p);}catch(IOException expected){denied=true;}
  check(denied,name);
 }
 public static void main(String[] args)throws Exception{
  Path root=Paths.get(args[0]);Files.createDirectories(root);
  Path valid=root.resolve("existing.db");Files.write(valid,new byte[]{1,2,3});
  resumeFile(valid);check(Arrays.equals(Files.readAllBytes(valid),new byte[]{1,2,3}),"valid unchanged");
  if(args.length>1)return;
  Path missing=root.resolve("absent.db");refused(missing,"missing");check(!Files.exists(missing),"missing never created");
  Path empty=root.resolve("empty.db");Files.write(empty,new byte[0]);refused(empty,"empty");check(Files.size(empty)==0,"empty retained");
  refused(root,"directory");
  Path link=root.resolve("link.db");Files.createSymbolicLink(link,valid);
  refused(link,"symlink");check(Arrays.equals(Files.readAllBytes(valid),new byte[]{1,2,3}),"linked target unchanged");
  Path broken=root.resolve("broken.db");Files.createSymbolicLink(broken,missing);
  refused(broken,"broken link");check(Files.isSymbolicLink(broken),"broken link retained");
  System.out.println(checks);
 }
}
'''
def resume_file_run(member,witness=False):
 with tempfile.TemporaryDirectory() as directory:
  root=pathlib.Path(directory);source=root/"FileGate.java"
  source.write_text(RESUME_FILE_HARNESS.replace("MEMBER",member))
  c=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",str(root),str(source)],capture_output=True,text=True,timeout=30)
  assert c.returncode==0,c.stderr
  return subprocess.run(["java","-cp",str(root),"FileGate",str(root/"files")]+(["witness"] if witness else []),capture_output=True,text=True,timeout=10)
def resume_file_controls(member):
 good=resume_file_run(member);assert good.returncode==0,good.stderr
 mutations={
  "symlinks_followed":("Files.isSymbolicLink(path)||!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)","!Files.isRegularFile(path)"),
  "empty_accepted":("Files.size(path)==0","Files.size(path)<0"),
  "directory_accepted":("!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)","!Files.exists(path,LinkOption.NOFOLLOW_LINKS)"),
 }
 rows={}
 for name,(old,new) in mutations.items():
  assert member.count(old)==1,(name,"anchor")
  mutant=member.replace(old,new,1)
  witness=resume_file_run(mutant,True);assert witness.returncode==0,(name,witness.stderr)
  rejected=resume_file_run(mutant);assert rejected.returncode!=0 and "AssertionError" in rejected.stderr,(name,rejected.stderr)
  rows[name]={"valid_witness":True,"negative_rejected":True}
 return {"checks":int(good.stdout.strip()),"mutants":rows,"scope":"ACTUAL_JAVA_NIO_NOT_ANDROID_SQLITE"}


STUBS["android/database/DatabaseErrorHandler.java"]="package android.database;public interface DatabaseErrorHandler{void onCorruption(android.database.sqlite.SQLiteDatabase db);}"
STUBS["android/database/sqlite/SQLiteException.java"]="package android.database.sqlite;public class SQLiteException extends RuntimeException{}"
_resume_sql="android/database/sqlite/SQLiteDatabase.java"
STUBS[_resume_sql]=STUBS[_resume_sql].replace("public static SQLiteDatabase create(", "public static final int OPEN_READWRITE=0;public static SQLiteDatabase openDatabase(String p,Object f,int flags,android.database.DatabaseErrorHandler h){return null;}public static SQLiteDatabase create(",1)
STUBS[_app]=STUBS[_app].replace("public static AppDatabase openSchema4(", "public static AppDatabase resumeActivated(android.content.Context c,String n){return null;}public static AppDatabase openSchema4(",1)
def resume_file_selftest():
    member=extract(JAVA.read_text(),"static void resumeFile(")
    result=resume_file_controls(member)
    need(result["checks"]==10 and len(result["mutants"])==3,"resume file control population")
    print("RESUME_FILE_GUARD "+json.dumps(result))

STARTUP_LABELS={'seed': ['startup_fresh_stays_schema3', 'startup_existing_schema3_keeps_data', 'startup_invalid_files_exact_preservation', 'startup_symlink_refused_without_reset', 'startup_schema2_uses_frozen_migration', 'startup_cancelled_activation_stays_schema3', 'startup_activated_schema4_resumes_exactly', 'startup_closed_facade_cannot_reopen', 'startup_never_touches_phone_database'], 'reopen': ['startup_separate_process_exact_state', 'startup_separate_process_relations']}
"""Actual Java startup policy checks. No Android/SQLite behavior is simulated."""
from pathlib import Path
import json,subprocess,tempfile

STARTUP_POLICY_HARNESS=r'''
final class ResumeHarness {
    // MEMBER
    static void need(boolean ok,String why){if(!ok)throw new AssertionError(why);}
    static void denied(int version,boolean exists){
        try{startupSchema(exists,version);}
        catch(IllegalStateException expected){return;}
        throw new AssertionError("unsafe startup accepted "+exists+"/"+version);
    }
    public static void main(String[] args){
        need(startupSchema(false,0)==3,"new install stays schema3");
        need(startupSchema(true,2)==3,"existing schema2 retains old schema3 path");
        need(startupSchema(true,3)==3,"ordinary schema3 must not activate");
        need(startupSchema(true,4)==4,"already activated schema4 resumes");
        if(args.length>0)return;
        denied(0,true);denied(1,true);denied(-1,true);
        denied(5,true);denied(Integer.MAX_VALUE,true);denied(Integer.MIN_VALUE,true);
        denied(2,false);denied(3,false);denied(4,false);
        System.out.println("STARTUP_POLICY 13 PASS_NOT_ANDROID");
    }
}
'''
def startup_policy_run(member,args=()):
 with tempfile.TemporaryDirectory() as directory:
  p=Path(directory);source=p/"ResumeHarness.java"
  source.write_text(STARTUP_POLICY_HARNESS.replace("// MEMBER",member))
  c=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",str(p),str(source)],text=True,capture_output=True,timeout=30)
  if c.returncode:return c
  return subprocess.run(["java","-cp",str(p),"ResumeHarness",*args],text=True,capture_output=True,timeout=10)

def startup_policy_controls(member):
 good=startup_policy_run(member);assert good.returncode==0,(good.stdout,good.stderr)
 mutations={
  "unknown_existing_falls_back":('throw new IllegalStateException("Unsupported database; preserve file");','return 3;'),
  "missing_nonzero_accepted":('if(version==0)return 3;','if(version>=0)return 3;'),
  "future_version_resumes":('if(version==4)return 4;','if(version>=4)return 4;'),
  "empty_existing_auto_creates":('if(version==2||version==3)return 3;','if(version==0||version==2||version==3)return 3;')
 }
 result={}
 for name,(old,new) in mutations.items():
  assert member.count(old)==1
  mutant=member.replace(old,new,1)
  witness=startup_policy_run(mutant,("witness",));assert witness.returncode==0,(name,witness.stderr)
  bad=startup_policy_run(mutant);assert bad.returncode!=0 and "AssertionError" in bad.stderr,(name,bad.stdout,bad.stderr)
  result[name]={"valid_witness":True,"negative_rejected":True}
 return {"checks":13,"mutants":result,"scope":"ACTUAL_JAVA_STARTUP_POLICY_NOT_SQLITE_OR_ANDROID"}



_startup_app="com/supercubegame/pockettodo/AppDatabase.java"
STUBS[_startup_app]=STUBS[_startup_app].replace("public static AppDatabase resumeActivated(",
    "public static AppDatabase openForStartup(android.content.Context c,String n){return null;}public boolean shortcutsEnabled(){return false;}public static AppDatabase resumeActivated(",1)
_startup_s3="com/supercubegame/pockettodo/Schema3Store.java"
STUBS[_startup_s3]=STUBS[_startup_s3].replace("static SQLiteDatabase stateCandidate(",
    "static SQLiteDatabase normalizeLegacyState(byte[] b){return null;}static SQLiteDatabase stateCandidate(",1)
def startup_host_selftest():
    import types,ast,inspect
    actual=(ROOT/"src/main/java/com/supercubegame/pockettodo/AppDatabase.java").read_text()
    result=startup_policy_controls(extract(actual,"static int startupSchema("))
    need(result["checks"]==13 and len(result["mutants"])==4,"startup policy population")
    print("STARTUP_POLICY "+json.dumps(result))
    ast_source=LABEL_AST.replace("bridgeSeed","startupSeed").replace("bridgeReopen","startupReopen").replace("bridge_[a-z0-9_]+","startup_[a-z0-9_]+")
    parse=types.FunctionType(java_label_calls.__code__,dict(globals(),LABEL_AST=ast_source))
    test=DEVICE.read_text()
    def check(rows):
        observed={p:[r[1] for r in rows if r[0]==m] for p,m in (("seed","startupSeed"),("reopen","startupReopen"))}
        need(observed==STARTUP_LABELS,"startup actual callsites")
    rows=parse([test])[0];check(rows);variants=[]
    for row in rows:
        a=len(test.encode("utf-16-le")[:row[2]*2].decode("utf-16-le"))
        b=len(test.encode("utf-16-le")[:row[3]*2].decode("utf-16-le"))
        variants.append(test[:a]+test[b:])
    for parsed in parse(variants):
        try:check(parsed)
        except AssertionError:pass
        else:raise AssertionError("startup omission survived")
    need(len(variants)==11,"startup omission count")
    tree=ast.parse(inspect.getsource(replay_shortcut_databases))
    chosen=[n for n in tree.body[0].body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
            and isinstance(n.value.args[-1],ast.Constant) and n.value.args[-1].value=="report independent startup replay differs"]
    need(len(chosen)==1,"startup replay mutation anchor");tree.body[0].body.remove(chosen[0])
    scope=dict(globals());exec(compile(ast.fix_missing_locations(tree),"<startup-replay-omitted>","exec"),scope)
    probe=types.FunctionType(report_selftest.__code__,scope,report_selftest.__name__,report_selftest.__defaults__)
    try:probe()
    except AssertionError as exc:need(str(exc)=="invalid report not rejected: startup_missing","wrong startup replay witness")
    else:raise AssertionError("startup replay omitted silently")
    print("STARTUP_ACTUAL_JAVA_CALLS_11_OMISSIONS_AND_REPORT_REPLAY_OMISSION_PASS_NOT_ANDROID")

def selftest():
    startup_host_selftest()
    resume_file_selftest()
    activation_host_selftest()
    ui_host_selftest()
    label_contract_selftest()
    bridge_selftest()
    bridge_receipt_selftest()
    parser_selftest()
    wire_selftest()
    sql_selftest()
    syntax_selftest()
    receipt_selftest()
    report_selftest()
    workflow_selftest()


NATIVE_STARTUP_LABELS = {
    "seed": [
        "native_startup_fresh_schema3",
        "native_startup_existing_schema3_exact",
        "native_startup_corrupt_file_retained",
        "native_startup_schema4_exact",
        "native_startup_relaunch_exact",
        "native_startup_phone_database_absent",
    ],
    "reopen": [
        "native_startup_separate_process_exact",
        "native_startup_separate_process_phone_absent",
    ],
}


def parse_native_startup(raw, phase):
    text = raw.decode("utf-8", "strict").replace("\r\n", "\n")
    found = re.findall(r"(?:^|stream=)STARTUP_NATIVE_PASS ([a-z0-9_]+)$", text, re.M)
    need(found == NATIVE_STARTUP_LABELS[phase], "native startup complete ordered checks")
    return found


_startup_original_parse_phase = parse_phase
def parse_phase(raw, phase, api):
    parse_native_startup(raw, phase)
    return _startup_original_parse_phase(raw, phase, api)


_startup_original_fixture = fixture
def fixture(phase="seed", api=26):
    native = "".join("STARTUP_NATIVE_PASS " + label + "\n"
                     for label in NATIVE_STARTUP_LABELS[phase]).encode()
    return _startup_original_fixture(phase, api) + native


def native_startup_parser_selftest(fixture=fixture, parse_phase=parse_phase):
    positive = negative = 0
    for phase in NATIVE_STARTUP_LABELS:
        for api in (26, 34):
            raw = fixture(phase, api)
            need(raw.startswith(_startup_original_fixture(phase, api)), "legacy fixture prefix preserved")
            parse_phase(raw, phase, api); positive += 1
            bads = [raw.replace(("STARTUP_NATIVE_PASS " + label + "\n").encode(), b"", 1)
                    for label in NATIVE_STARTUP_LABELS[phase]]
            native = [("STARTUP_NATIVE_PASS " + label + "\n").encode() for label in NATIVE_STARTUP_LABELS[phase]]
            bads += [raw + native[0],
                     raw.replace(native[0] + native[1], native[1] + native[0], 1),
                     raw.replace(b"STARTUP_NATIVE_PASS", b"IGNORED_STARTUP_PASS"),
                     raw.replace(native[0], b"STARTUP_NATIVE_PASS wrong\n", 1)]
            for bad in bads:
                try:
                    parse_phase(bad, phase, api)
                except AssertionError:
                    negative += 1
                else:
                    raise AssertionError("native startup omission accepted")
    # Demonstrate why the unchanged old parser is insufficient: valid legacy
    # result remains valid when every new native check has been omitted.
    legacy = _startup_original_fixture("seed", 26)
    _startup_original_parse_phase(legacy, "seed", 26)
    try:
        parse_phase(legacy, "seed", 26)
    except AssertionError as exc:
        need(str(exc) == "native startup complete ordered checks", "wrong native RED")
    else:
        raise AssertionError("legacy-only result accepted as native startup proof")
    need(positive == 4 and negative == 32, "native parser population")
    print("NATIVE_STARTUP_PARSER positive=4 negative=32 LEGACY_WITNESS_OMISSION_RED PASS")


_startup_original_selftest = selftest
def selftest():
    native_startup_parser_selftest()
    native_startup_source_selftest()
    _startup_original_selftest()


def native_startup_source_selftest():
    import types
    source = DEVICE.read_text()
    grammar = LABEL_AST.replace("bridgeSeed", "startupUiSeed").replace(
        "bridgeReopen", "startupUiReopen").replace('"need"', '"nativeStartupNeed"').replace(
        "bridge_[a-z0-9_]+", "native_startup_[a-z0-9_]+")
    parser = types.FunctionType(java_label_calls.__code__, dict(globals(), LABEL_AST=grammar))
    def check(rows):
        observed = {phase: [row[1] for row in rows if row[0] == method]
                    for phase, method in (("seed", "startupUiSeed"), ("reopen", "startupUiReopen"))}
        need(observed == NATIVE_STARTUP_LABELS, "native startup actual Java check calls")
    rows = parser([source])[0]; check(rows)
    variants = []
    for row in rows:
        a = len(source.encode("utf-16-le")[:row[2]*2].decode("utf-16-le"))
        b = len(source.encode("utf-16-le")[:row[3]*2].decode("utf-16-le"))
        need(source[a:b].startswith("nativeStartupNeed("), "native callsite witness")
        variants.append(source[:a]+source[b:])
    need(len(variants) == 8, "native omission population")
    for variant in parser(variants):
        try: check(variant)
        except AssertionError: pass
        else: raise AssertionError("native Java check omission survived")
    print("NATIVE_STARTUP_JAVA_AST checks=8 omission_mutants=8 PASS_NOT_DEVICE")


STUBS["com/supercubegame/pockettodo/MainActivity.java"] = STUBS["com/supercubegame/pockettodo/MainActivity.java"].replace("static boolean isolatedShortcutTest;", "static boolean isolatedShortcutTest; static boolean isolatedStartupTest;")

ACTIVATION_UI_LABELS = {
    "seed": [
        "activation_ui_preview_keeps_schema3",
        "activation_ui_unchecked_cannot_commit",
        "activation_ui_cancel_keeps_backup_and_cells",
        "activation_ui_stale_confirm_refused",
        "activation_ui_changed_backup_refused",
        "activation_ui_confirm_recreates_with_exact_history",
        "activation_ui_repeat_entry_is_noop",
        "activation_ui_phone_database_absent",
    ],
    "reopen": [
        "activation_ui_separate_process_exact",
        "activation_ui_separate_process_phone_absent",
    ],
}


def parse_activation_ui(raw, phase):
    text = raw.decode("utf-8", "strict").replace("\r\n", "\n")
    found = re.findall(r"(?:^|stream=)ACTIVATION_UI_PASS ([a-z0-9_]+)$", text, re.M)
    need(found == ACTIVATION_UI_LABELS[phase], "activation UI complete ordered checks")
    return found


_activation_original_parse_phase = parse_phase
def parse_phase(raw, phase, api):
    parse_activation_ui(raw, phase)
    return _activation_original_parse_phase(raw, phase, api)


_activation_original_fixture = fixture
def fixture(phase="seed", api=26):
    native = "".join("ACTIVATION_UI_PASS " + label + "\n"
                     for label in ACTIVATION_UI_LABELS[phase]).encode()
    return _activation_original_fixture(phase, api) + native


def activation_ui_parser_selftest(fixture=fixture, parse_phase=parse_phase):
    positive = negative = 0
    for phase in ACTIVATION_UI_LABELS:
        for api in (26, 34):
            raw = fixture(phase, api)
            need(raw.startswith(_activation_original_fixture(phase, api)), "legacy fixture prefix preserved")
            parse_phase(raw, phase, api); positive += 1
            bads = [raw.replace(("ACTIVATION_UI_PASS " + label + "\n").encode(), b"", 1)
                    for label in ACTIVATION_UI_LABELS[phase]]
            native = [("ACTIVATION_UI_PASS " + label + "\n").encode() for label in ACTIVATION_UI_LABELS[phase]]
            bads += [raw + native[0],
                     raw.replace(native[0] + native[1], native[1] + native[0], 1),
                     raw.replace(b"ACTIVATION_UI_PASS", b"IGNORED_ACTIVATION_PASS"),
                     raw.replace(native[0], b"ACTIVATION_UI_PASS wrong\n", 1)]
            for bad in bads:
                try:
                    parse_phase(bad, phase, api)
                except AssertionError:
                    negative += 1
                else:
                    raise AssertionError("activation UI omission accepted")
    # Demonstrate why the unchanged old parser is insufficient: valid legacy
    # result remains valid when every new native check has been omitted.
    legacy = _activation_original_fixture("seed", 26)
    _activation_original_parse_phase(legacy, "seed", 26)
    try:
        parse_phase(legacy, "seed", 26)
    except AssertionError as exc:
        need(str(exc) == "activation UI complete ordered checks", "wrong native RED")
    else:
        raise AssertionError("legacy-only result accepted as activation UI proof")
    need(positive == 4 and negative == 36, "native parser population")
    print("NATIVE_STARTUP_PARSER positive=4 negative=36 LEGACY_WITNESS_OMISSION_RED PASS")


_activation_original_selftest = selftest

def combined_ui_parser_check(parser):
    positive = negative = 0
    groups = (
        ("STARTUP_NATIVE_PASS", NATIVE_STARTUP_LABELS, "native startup complete ordered checks"),
        ("ACTIVATION_UI_PASS", ACTIVATION_UI_LABELS, "activation UI complete ordered checks"),
    )
    for phase in ("seed", "reopen"):
        for api in (26, 34):
            raw = fixture(phase, api)
            parser(raw, phase, api)
            positive += 1
            for prefix, labels, reason in groups:
                for label in labels[phase]:
                    line = (prefix + " " + label + "\n").encode()
                    need(raw.count(line) == 1, "combined omission exact witness")
                    bad = raw.replace(line, b"", 1)
                    try:
                        parser(bad, phase, api)
                    except AssertionError as exc:
                        need(str(exc) == reason, "combined wrong omission reason")
                        negative += 1
                    else:
                        raise AssertionError("combined accepted " + prefix + " omission")
    need(positive == 4 and negative == 36, "combined parser population")


def combined_ui_parser_selftest():
    import types
    combined_ui_parser_check(parse_phase)
    # Both weakened parsers first accept every complete fixture. Their failure
    # must then be the intended missing-label witness, not an unrelated error.
    def skip_activation(raw, phase, api):
        return _activation_original_parse_phase(raw, phase, api)
    def skip_startup(raw, phase, api):
        parse_activation_ui(raw, phase)
        return _startup_original_parse_phase(raw, phase, api)
    for mutant, prefix in ((skip_activation, "ACTIVATION_UI_PASS"),
                           (skip_startup, "STARTUP_NATIVE_PASS")):
        for phase in ("seed", "reopen"):
            for api in (26, 34):
                mutant(fixture(phase, api), phase, api)
        try:
            combined_ui_parser_check(mutant)
        except AssertionError as exc:
            need(str(exc) == "combined accepted " + prefix + " omission",
                 "combined mutant wrong witness")
        else:
            raise AssertionError("combined parser bypass survived")
    # Remove only the captured defaults to recreate the original late binding.
    original = native_startup_parser_selftest
    rebound = types.FunctionType(original.__code__, globals(), original.__name__,
                                 (fixture, parse_phase))
    try:
        rebound()
    except AssertionError as exc:
        need(str(exc) == "wrong native RED", "late binding mutant wrong witness")
    else:
        raise AssertionError("late binding regression survived")
    print("COMBINED_UI_PARSER positive=4 omissions=36 bypass_mutants=2 late_binding_mutant=1 PASS")


def selftest():
    combined_ui_parser_selftest()
    activation_ui_parser_selftest()
    activation_ui_source_selftest()
    scope={"__name__":"activation_member_gate"}
    exec(compile(ACTIVATION_MEMBER_GATE,"activation_member_gate","exec"),scope)
    source=(DEVICE.parents[6]/"src/main/java/com/supercubegame/pockettodo/TodayScreen.java").read_text()
    members=source.split("    // BEGIN_EXPLICIT_ACTIVATION_UI",1)[1].split("    // END_EXPLICIT_ACTIVATION_UI",1)[0]
    scope["check"](members)
    _activation_original_selftest()


def activation_ui_source_selftest():
    import types
    source = DEVICE.read_text()
    grammar = LABEL_AST.replace("bridgeSeed", "activationUiSeed").replace(
        "bridgeReopen", "activationUiReopen").replace('"need"', '"activationUiNeed"').replace(
        "bridge_[a-z0-9_]+", "activation_ui_[a-z0-9_]+")
    parser = types.FunctionType(java_label_calls.__code__, dict(globals(), LABEL_AST=grammar))
    def check(rows):
        observed = {phase: [row[1] for row in rows if row[0] == method]
                    for phase, method in (("seed", "activationUiSeed"), ("reopen", "activationUiReopen"))}
        need(observed == ACTIVATION_UI_LABELS, "activation UI actual Java check calls")
    rows = parser([source])[0]; check(rows)
    variants = []
    for row in rows:
        a = len(source.encode("utf-16-le")[:row[2]*2].decode("utf-16-le"))
        b = len(source.encode("utf-16-le")[:row[3]*2].decode("utf-16-le"))
        need(source[a:b].startswith("activationUiNeed("), "native callsite witness")
        variants.append(source[:a]+source[b:])
    need(len(variants) == 10, "native omission population")
    for variant in parser(variants):
        try: check(variant)
        except AssertionError: pass
        else: raise AssertionError("activation Java check omission survived")
    print("NATIVE_STARTUP_JAVA_AST checks=10 omission_mutants=10 PASS_NOT_DEVICE")


ACTIVATION_MEMBER_GATE='"""Actual added TodayScreen members, explicit widget/database doubles; not Android."""\nimport pathlib,subprocess,tempfile\nHARNESS=r\'\'\'\nimport java.nio.file.*;import java.util.concurrent.*;import java.util.function.*;\nclass View {void setContentDescription(String s){} void setEnabled(boolean b){} }\nclass TextView extends View {String text="";TextView(){} void setText(String s){text=s;}}\nclass Button extends View {Runnable click;void setMinHeight(int n){} void setOnClickListener(Consumer<View> c){click=()->c.accept(this);}void click(){if(click!=null)click.run();}}\nclass CheckBox extends TextView {static CheckBox last;boolean yes;CheckBox(Object a){last=this;}boolean isChecked(){return yes;}void setMinHeight(int n){}}\nclass LinearLayout extends View {void setPadding(int a,int b,int c,int d){}void addView(View v){}}\nclass ScrollView extends View {ScrollView(Object a){}void addView(View v){}}\nclass AlertDialog {\n static final int BUTTON_POSITIVE=1,BUTTON_NEGATIVE=0;Consumer<Object> show,dismiss;\n final Button pos=new Button(),neg=new Button();boolean dismissed;\n void setOnShowListener(Consumer<Object> c){show=c;}void setOnDismissListener(Consumer<Object> c){dismiss=c;}\n void setCancelable(boolean v){} Button getButton(int k){return k==1?pos:neg;}\n void show(){show.accept(null);}void dismiss(){dismissed=true;if(dismiss!=null)dismiss.accept(null);}\n static class Builder{\n Builder(Object a){}Builder setTitle(String s){return this;}Builder setView(View v){return this;}\n Builder setNegativeButton(String s,Object v){return this;}Builder setPositiveButton(String s,Object v){return this;}\n AlertDialog create(){return new AlertDialog();}\n }\n}\nclass Activity {\n boolean destroyed,finishing;boolean isDestroyed(){return destroyed;}boolean isFinishing(){return finishing;}\n java.io.File getFilesDir(){return new java.io.File("/synthetic-only");}\n}\nclass MainActivity extends Activity {\n int restart,failed;void restartAfterShortcutActivation(TodayScreen s){restart++;}\n void activationNeedsRestart(TodayScreen s){failed++;}\n}\nclass MediaRepository {MediaRepository(Path p,long b)throws java.io.IOException{}}\nclass AppDatabase {\n int version=3,prepared,confirmed;boolean fail;ShortcutActivationPlan last;\n static class ShortcutActivationPlan {boolean closed;String backupName(){return "backup.zip";}void close(){closed=true;}}\n AppDatabase getReadableDatabase(){return this;}int getVersion(){return version;}\n ShortcutActivationPlan prepareShortcutActivation(Path p,MediaRepository m){prepared++;return last=new ShortcutActivationPlan();}\n void confirmShortcutActivation(ShortcutActivationPlan p,MediaRepository m)throws Exception{\n  if(p.closed)throw new Exception("expired");p.close();if(fail)throw new Exception("backup changed");\n  confirmed++;version=4;\n }\n}\npublic class TodayScreen {\n MainActivity activity=new MainActivity();AppDatabase db=new AppDatabase();\n boolean busy,closed;String notice;int INK=1,ERROR=2;\n void rememberDraft(){}void leaveTodoSession(){}int dp(int n){return n;}\n LinearLayout column(){return new LinearLayout();}\n TextView text(String s,int size,int color){TextView t=new TextView();t.setText(s);return t;}\n void message(String s,boolean e){notice=s;}\n <T> void work(Callable<T> c,Consumer<T> ok,Runnable fail){work(c,ok,fail,x->{});}\n <T> void work(Callable<T> c,Consumer<T> ok,Runnable fail,Consumer<T> abandoned){\n  try{T result=c.call();if(closed||activity.destroyed)abandoned.accept(result);else ok.accept(result);}\n  catch(Exception e){if(fail!=null)fail.run();}\n }\n /* MEMBERS */\n static int count;\n static void need(boolean v,String s){if(!v)throw new AssertionError(s);count++;System.out.println("PASS "+s);}\n static TodayScreen preview(){TodayScreen s=new TodayScreen();s.requestShortcutActivation();return s;}\n public static void main(String[] a){\n  TodayScreen s=preview();need(s.db.prepared==1&&s.db.confirmed==0&&s.db.version==3,"preview_only");\n  AlertDialog dialog=s.activationDialog;AppDatabase.ShortcutActivationPlan plan=s.activationPlan;\n  dialog.pos.click();need(s.db.confirmed==0&&s.activationPlan==plan,"unchecked");\n  dialog.dismiss();need(plan.closed&&s.activationPlan==null&&s.db.version==3,"cancel");\n  dialog.pos.click();need(s.db.confirmed==0,"stale");\n  s=preview();dialog=s.activationDialog;CheckBox.last.yes=true;dialog.pos.click();\n  need(s.db.confirmed==1&&s.db.version==4&&s.activity.restart==1,"confirmed");\n  dialog.pos.click();need(s.db.confirmed==1&&s.activity.restart==1,"double_click");\n  s=preview();plan=s.activationPlan;s.closed=true;s.clearActivation();\n  need(plan.closed&&s.activationPlan==null&&s.activationDialog==null,"closed_cleanup");\n  s=preview();s.activity.finishing=true;CheckBox.last.yes=true;s.activationDialog.pos.click();\n  need(s.db.confirmed==0,"finishing_refused");\n  s=preview();s.db.fail=true;CheckBox.last.yes=true;s.activationDialog.pos.click();\n  need(s.activity.failed==1&&s.activity.restart==0&&s.db.confirmed==0,"failure_requires_restart");\n  s=new TodayScreen();s.db.version=4;s.requestShortcutActivation();\n  need(s.db.prepared==0&&s.activationDialog==null,"already_enabled");\n  s=new TodayScreen();s.busy=true;s.requestShortcutActivation();\n  need(s.db.prepared==0,"busy_refused");\n  s=preview();s.requestShortcutActivation();need(s.db.prepared==1,"duplicate_preview");\n  need(count==12,"population");\n }\n}\n\'\'\'\ndef run(members):\n    with tempfile.TemporaryDirectory() as tmp:\n        p=pathlib.Path(tmp)/"TodayScreen.java";p.write_text(HARNESS.replace("/* MEMBERS */",members))\n        c=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",tmp,str(p)],capture_output=True,text=True,timeout=30)\n        if c.returncode:return c,None\n        return c,subprocess.run(["java","-cp",tmp,"TodayScreen"],capture_output=True,text=True,timeout=30)\ndef check(members):\n    c,r=run(members);assert c.returncode==0,c.stderr;assert r.returncode==0,(r.stdout,r.stderr)\n    for old,new,label in [\n        (\'if(!consent.isChecked())\',\'if(false)\',\'unchecked\'),\n        (\'        if(plan!=null)plan.close();\\n        if(attempt!=null)\', \'        if(false)plan.close();\\n        if(attempt!=null)\',\'closed_cleanup\'),\n        (\'||!activationCurrent(expected))return;\',\'||false)return;\',\'finishing_refused\'),\n    ]:\n        assert members.count(old)==1,old\n        c,r=run(members.replace(old,new));assert c.returncode==0,c.stderr\n        assert r.returncode==1 and "PASS preview_only" in r.stdout and "AssertionError: "+label in r.stderr,(label,r)\n    print("ACTIVATION_UI_MEMBERS 12_behavior_checks 3_witnessed_mutants PASS_ANDROID_DB_DOUBLES")\nif __name__=="__main__":\n    import sys\n    check(pathlib.Path(sys.argv[1]).read_text())\n'
_activation_stub=STUBS["com/supercubegame/pockettodo/MainActivity.java"]
need(_activation_stub.rstrip().endswith("}"),"activation stub class end")
_activation_head,_activation_tail=_activation_stub.rsplit("}",1)
STUBS["com/supercubegame/pockettodo/MainActivity.java"]=_activation_head+" static boolean isolatedActivationTest; void restartAfterShortcutActivation(TodayScreen s){} void activationNeedsRestart(TodayScreen s){} }"+_activation_tail

"""Declarations only; whole-source compile remains distinct from Android."""
ACTIVATION_SHAPE_BEFORE = dict(STUBS)
_activation_instrumentation = "android/app/Instrumentation.java"
_activation_monitor_members = """
public static class ActivityResult {}
public static class ActivityMonitor {}
public ActivityMonitor addMonitor(String name,ActivityResult result,boolean block){return null;}
public Activity waitForMonitorWithTimeout(ActivityMonitor monitor,long timeout){return null;}
public void removeMonitor(ActivityMonitor monitor){}
"""
need("ActivityMonitor" not in STUBS[_activation_instrumentation],
     "activation monitor declaration already present")
_activation_ihead, _activation_itail = STUBS[_activation_instrumentation].rsplit("}", 1)
need(not _activation_itail.strip(), "instrumentation declaration end")
STUBS[_activation_instrumentation] = _activation_ihead + _activation_monitor_members + "}" + _activation_itail
need("android/app/AlertDialog.java" not in STUBS, "activation dialog declaration already present")
STUBS["android/app/AlertDialog.java"] = """package android.app;public class AlertDialog{
public android.view.Window getWindow(){return null;}
}
"""


def activation_shape_selftest():
    import contextlib, io, types
    def compile_with(stubs):
        runner = types.FunctionType(syntax_selftest.__code__, dict(globals(), STUBS=stubs))
        with contextlib.redirect_stdout(io.StringIO()):
            runner()
    # Preserve the actual first missing-declaration path on the full new source.
    try:
        compile_with(ACTIVATION_SHAPE_BEFORE)
    except AssertionError as exc:
        message = str(exc)
        need("new-class Java syntax failed:" in message and
             "cannot find symbol" in message and
             "class AlertDialog" in message and "class ActivityMonitor" in message,
             "activation shape original RED changed")
        print("ACTIVATION_SHAPE_ORIGINAL_RED\n" + message)
    else:
        raise AssertionError("activation shape original missing declarations accepted")
    compile_with(STUBS)
    cases = [
        ("android/app/AlertDialog.java", "getWindow(", "omittedGetWindow(", "getWindow"),
        (_activation_instrumentation, "addMonitor(", "omittedAddMonitor(", "addMonitor"),
        (_activation_instrumentation, "waitForMonitorWithTimeout(", "omittedWaitForMonitorWithTimeout(", "waitForMonitorWithTimeout"),
        (_activation_instrumentation, "removeMonitor(", "omittedRemoveMonitor(", "removeMonitor"),
    ]
    for path, old, new, witness in cases:
        mutant = dict(STUBS)
        need(mutant[path].count(old) == 1, "activation declaration omission anchor")
        mutant[path] = mutant[path].replace(old, new, 1)
        try:
            compile_with(mutant)
        except AssertionError as exc:
            message = str(exc)
            need("new-class Java syntax failed:" in message and
                 "cannot find symbol" in message and witness in message,
                 "activation declaration wrong omission witness " + witness)
        else:
            raise AssertionError("activation declaration omission survived " + witness)
    print("ACTIVATION_API_SHAPE original_RED full_source_GREEN omitted_methods=4 PASS_NOT_ANDROID")


_activation_shape_original_selftest = selftest
def selftest():
    activation_shape_selftest()
    _activation_shape_original_selftest()

def activation_touch_selftest():
    source=DEVICE.read_text()
    helper=extract(source,"private static android.graphics.Rect activationTouchRect(")
    scope={"__name__":"activation_touch_gate"}
    exec(compile('"""Actual coordinate helper with explicit View/Rect doubles, not Android."""\nimport pathlib,subprocess,tempfile\nHARNESS=r\'\'\'\npublic class WireTest {\nstatic void assertThat(boolean ok,String reason){if(!ok)throw new AssertionError(reason);}\nstatic class android {\n static class graphics {\n  static class Rect {\n   int left,top,right,bottom;\n   int width(){return right-left;}int height(){return bottom-top;}\n   void offset(int x,int y){left+=x;right+=x;top+=y;bottom+=y;}\n  }\n }\n static class view {\n  static class View {\n   boolean enabled=true,attached=true,visible=true;int x,y,l,t,r=100,b=60;\n   boolean isEnabled(){return enabled;}boolean isAttachedToWindow(){return attached;}\n   boolean getLocalVisibleRect(graphics.Rect out){out.left=l;out.top=t;out.right=r;out.bottom=b;return visible;}\n   void getLocationOnScreen(int[] out){out[0]=x;out[1]=y;}\n  }\n }\n}\n__HELPER__\nstatic void check(android.view.View view,int l,int t,int r,int b,String label){\n android.graphics.Rect actual=activationTouchRect(view);\n assertThat(actual.left==l&&actual.top==t&&actual.right==r&&actual.bottom==b,label);\n}\npublic static void main(String[] args){\n android.view.View v=new android.view.View();check(v,0,0,100,60,"origin");\n System.out.println("ORIGIN_WITNESS");\n if(args.length>0)return;\n v.x=80;v.y=300;check(v,80,300,180,360,"dialog_screen_offset");\n v.l=10;v.t=12;v.r=70;v.b=55;check(v,90,312,150,355,"clipped_dialog");\n v.x=-5;v.y=24;check(v,5,36,65,79,"screen_insets");\n for(int i=0;i<4;i++){\n  v=new android.view.View();\n  if(i==0)v.enabled=false;if(i==1)v.attached=false;if(i==2)v.visible=false;if(i==3)v.r=0;\n  try{activationTouchRect(v);throw new AssertionError("accepted_invisible_"+i);}\n  catch(AssertionError e){assertThat(e.getMessage().equals("activation visible screen bounds"),"wrong_refusal_"+i);}\n }\n System.out.println("TOUCH_GEOMETRY positives=4 refused=4 PASS");\n}}\n\'\'\'\ndef run(helper,args=()):\n    with tempfile.TemporaryDirectory() as tmp:\n        f=pathlib.Path(tmp)/"WireTest.java";f.write_text(HARNESS.replace("__HELPER__",helper))\n        c=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",tmp,str(f)],capture_output=True,text=True,timeout=30)\n        assert c.returncode==0,c.stderr\n        return subprocess.run(["java","-cp",tmp,"WireTest",*args],capture_output=True,text=True,timeout=30)\ndef check(helper):\n    good=run(helper);assert good.returncode==0,(good.stdout,good.stderr)\n    old="rect.offset(screen[0],screen[1]);";assert helper.count(old)==1\n    mutant=helper.replace(old,"",1)\n    witness=run(mutant,("origin",));assert witness.returncode==0 and "ORIGIN_WITNESS" in witness.stdout\n    red=run(mutant);assert red.returncode==1 and "AssertionError: dialog_screen_offset" in red.stderr\n    print("ACTUAL_TOUCH_COORDINATE_HELPER 4_positive 4_refusals 1_witnessed_offset_mutant PASS_NOT_ANDROID")\nif __name__=="__main__":\n    check(pathlib.Path(__file__).with_name("activation-touch-helper.java").read_text())\n',"activation-touch-gate","exec"),scope)
    scope["check"](helper)
    touch=extract(source,"private android.view.View touchActivation(")
    need(touch.count("r.set(activationTouchRect(v))")==1 and
         "getGlobalVisibleRect" not in touch and touch.count("sendPointerSync(down)")==1 and
         touch.count("sendPointerSync(up)")==1,"activation single screen-space touch")

_touch_original_selftest=selftest
def selftest():
    activation_touch_selftest()
    _touch_original_selftest()

_touch_view="android/view/View.java"
_touch_head,_touch_tail=STUBS[_touch_view].rsplit("}",1)
STUBS[_touch_view]=_touch_head+" public boolean getLocalVisibleRect(android.graphics.Rect r){return false;} public void getLocationOnScreen(int[] out){} }"+_touch_tail
_touch_rect="android/graphics/Rect.java"
_touch_head,_touch_tail=STUBS[_touch_rect].rsplit("}",1)
STUBS[_touch_rect]=_touch_head+" public void offset(int x,int y){} public void set(Rect other){} }"+_touch_tail

def activation_lifecycle_selftest():
    scope={"__name__":"actual_activation_lifecycle"}
    exec(compile('"""Real candidate Java members, deterministic executor, explicit Android/DB doubles."""\nimport pathlib\nimport subprocess\nimport tempfile\n\nJAVA = r\'\'\'\nimport java.nio.file.*;import java.util.*;import javax.tools.*;\nimport com.sun.source.tree.*;import com.sun.source.util.*;\npublic class LifecycleMembers {\n public static void main(String[] args)throws Exception{\n  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();\n  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();\n  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){\n   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,List.of("-proc:none"),null,\n       files.getJavaFileObjects(args[0]));\n   Iterable<? extends CompilationUnitTree> units=task.parse();\n   Trees trees=Trees.instance(task);\n   for(CompilationUnitTree unit:units)for(Tree top:unit.getTypeDecls()){\n    if(!(top instanceof ClassTree)||!((ClassTree)top).getSimpleName().contentEquals("TodayScreen"))continue;\n    for(Tree member:((ClassTree)top).getMembers())if(member instanceof MethodTree){\n     MethodTree method=(MethodTree)member;\n     String name=method.getName().toString();\n     if(!name.equals("work")&&!name.equals("close"))continue;\n     long a=trees.getSourcePositions().getStartPosition(unit,member);\n     long b=trees.getSourcePositions().getEndPosition(unit,member);\n     System.out.println(name+"\\t"+method.getParameters().size()+"\\t"+a+"\\t"+b);\n    }\n   }\n   for(Diagnostic<?> error:errors.getDiagnostics())if(error.getKind()==Diagnostic.Kind.ERROR)\n    throw new AssertionError(error.toString());\n  }\n }\n}\n\'\'\'\n\n\ndef extract_members(full):\n    with tempfile.TemporaryDirectory() as tmp:\n        root = pathlib.Path(tmp)\n        (root / "LifecycleMembers.java").write_text(JAVA)\n        (root / "TodayScreen.java").write_text(full)\n        c = subprocess.run(["java", "-m", "jdk.compiler/com.sun.tools.javac.Main",\n                            "-d", tmp, str(root / "LifecycleMembers.java")],\n                           capture_output=True, text=True, timeout=30)\n        assert c.returncode == 0, c.stderr\n        r = subprocess.run(["java", "-cp", tmp, "LifecycleMembers",\n                            str(root / "TodayScreen.java")],\n                           capture_output=True, text=True, timeout=10)\n        assert r.returncode == 0, r.stderr\n        rows = [line.split("\\t") for line in r.stdout.splitlines()]\n        assert [(row[0], int(row[1])) for row in rows] == [\n            ("work", 3), ("work", 4), ("close", 0)], rows\n        raw = full.encode("utf-16-le")\n        selected = [raw[int(row[2])*2:int(row[3])*2].decode("utf-16-le") for row in rows]\n        assert selected[0].startswith("<T> void work(")\n        assert selected[1].startswith("<T> void work(")\n        assert selected[2].startswith("public void close(")\n        return "\\n".join(selected[:2]), selected[2]\n\n\ndef one(text, old, new):\n    assert text.count(old) == 1, ("lifecycle unique anchor", old)\n    return text.replace(old, new, 1)\n\n\ndef source(members, work, close, harness, tests):\n    text = one(harness,\n        "int version=3,prepared,confirmed;boolean fail;ShortcutActivationPlan last;",\n        "int version=3,prepared,confirmed;boolean fail,closed;ShortcutActivationPlan last;void close(){closed=true;}")\n    text = one(text, "int restart,failed;void restartAfterShortcutActivation",\n        "final java.util.Queue<Runnable> ui=new java.util.concurrent.ConcurrentLinkedQueue<>();\\n"\n        " void runOnUiThread(Runnable r){ui.add(r);}\\n int restart,failed;void restartAfterShortcutActivation")\n    begin = text.index(" <T> void work(Callable<T> c,")\n    end = text.index(" /* MEMBERS */", begin)\n    text = text[:begin]+work+"\\n"+close+"\\n"+text[end:]\n    text = one(text, "boolean busy,closed;String notice;int INK=1,ERROR=2;",\n        "boolean busy,closed;Object notice;int INK=1,ERROR=2;\\n"\n        "final ExecutorService io=Executors.newSingleThreadExecutor();View root=new View();"\n        "void pause(View v){}void resume(){}")\n    text = one(text, "void message(String s,boolean e){notice=s;}",\n        "void message(String s,boolean e){notice=new Object();}")\n    text = text[:text.index(" static int count;")]+tests+"\\n}\\n"\n    return one(text, "/* MEMBERS */", members)\n\n\ndef run(members, work, close, harness, tests):\n    with tempfile.TemporaryDirectory() as tmp:\n        path = pathlib.Path(tmp) / "TodayScreen.java"\n        path.write_text(source(members, work, close, harness, tests))\n        compiled = subprocess.run(["java", "-m", "jdk.compiler/com.sun.tools.javac.Main",\n                                   "-d", tmp, str(path)],\n                                  capture_output=True, text=True, timeout=30)\n        assert compiled.returncode == 0, compiled.stderr\n        return subprocess.run(["java", "-cp", tmp, "TodayScreen"],\n                              capture_output=True, text=True, timeout=20)\n\n\ndef check(full, harness, tests):\n    start = "    // BEGIN_EXPLICIT_ACTIVATION_UI"\n    end = "    // END_EXPLICIT_ACTIVATION_UI"\n    assert full.count(start) == full.count(end) == 1\n    members = full.split(start, 1)[1].split(end, 1)[0]\n    work, close = extract_members(full)\n    args = (members, work, close, harness, tests)\n    good = run(*args)\n    assert good.returncode == 0, (good.stdout, good.stderr)\n    expected = [\n        "close_before_prepare_abandons_plan",\n        "close_before_callback_abandons_plan",\n        "finishing_callback_abandons_plan",\n        "destroyed_callback_abandons_plan",\n        "close_invalidates_visible_consent",\n        "close_before_confirm_refuses_commit",\n        "close_after_commit_never_reopens_old_activity",\n        "closed_failure_never_reopens_old_activity",\n    ]\n    labels = [line.removeprefix("ASYNC_PASS ") for line in good.stdout.splitlines()]\n    assert [label for label in labels if label in expected] == expected, good.stdout\n    mutants = [\n        (0, \'plan->{if(plan!=null)plan.close();});\', \'plan->{});\',\n         "prepare_really_queued", "close_before_prepare_abandons_plan"),\n        (0, \'if(attempt!=null)attempt.close();\', \'if(false)attempt.close();\',\n         "confirm_really_queued", "close_before_confirm_refuses_commit"),\n        (0, \'&&!activity.isFinishing()&&activationView==expected\', \'&&activationView==expected\',\n         "prepared_callback_pending", "finishing_callback_abandons_plan"),\n        (2, \'clearActivation();\', \'\',\n         "preview_witness", "close_invalidates_visible_consent"),\n    ]\n    for index, old, new, witness, target in mutants:\n        changed = list(args)\n        changed[index] = one(changed[index], old, new)\n        result = run(*changed)\n        assert result.returncode == 1 and "ASYNC_PASS "+witness in result.stdout, (\n            target, result.stdout, result.stderr)\n        assert "AssertionError: "+target in result.stderr, (target, result.stdout, result.stderr)\n    print("ACTUAL_CANDIDATE_LIFECYCLE 8_scenarios 4_witnessed_mutants JAVA_AST_members PASS_NOT_ANDROID")\n',"actual_activation_lifecycle","exec"),scope)
    base={"__name__":"activation_lifecycle_doubles"}
    exec(compile(ACTIVATION_MEMBER_GATE,"activation_lifecycle_doubles","exec"),base)
    actual=(DEVICE.parents[6]/"src/main/java/com/supercubegame/pockettodo/TodayScreen.java").read_text()
    scope["check"](actual,base["HARNESS"],'\n static void need(boolean ok,String label){\n  if(!ok)throw new AssertionError(label);System.out.println("ASYNC_PASS "+label);\n }\n static final class Barrier implements AutoCloseable{\n  final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);\n  final TodayScreen owner;\n  Barrier(TodayScreen s)throws Exception{\n   owner=s;s.io.execute(()->{entered.countDown();try{\n    if(!release.await(5,TimeUnit.SECONDS))throw new AssertionError("barrier_release_deadline");\n   }catch(InterruptedException e){throw new AssertionError(e);}});\n   if(!entered.await(5,TimeUnit.SECONDS))throw new AssertionError("barrier_enter_deadline");\n  }\n  public void close(){release.countDown();}\n }\n static void workerDone(TodayScreen s)throws Exception{\n  if(s.io.isShutdown()){\n   if(!s.io.awaitTermination(5,TimeUnit.SECONDS))throw new AssertionError("worker_close_deadline");\n  }else s.io.submit(()->{}).get(5,TimeUnit.SECONDS);\n }\n static void drain(TodayScreen s){Runnable r;while((r=s.activity.ui.poll())!=null)r.run();}\n static TodayScreen preview()throws Exception{\n  TodayScreen s=new TodayScreen();s.requestShortcutActivation();workerDone(s);drain(s);\n  need(s.activationPlan!=null&&s.db.version==3,"preview_witness");return s;\n }\n static void finish(TodayScreen s)throws Exception{s.close();workerDone(s);drain(s);}\n static void runTests()throws Exception{\n  TodayScreen s=new TodayScreen();\n  try(Barrier hold=new Barrier(s)){\n   s.requestShortcutActivation();need(s.db.prepared==0,"prepare_really_queued");s.close();\n  }\n  workerDone(s);drain(s);\n  need(s.db.prepared==1&&s.db.last.closed&&s.db.closed&&s.activationDialog==null&&s.db.version==3,\n       "close_before_prepare_abandons_plan");\n\n  s=new TodayScreen();s.requestShortcutActivation();workerDone(s);\n  need(s.db.last!=null&&!s.db.last.closed&&s.activationDialog==null,"prepared_callback_pending");\n  finish(s);\n  need(s.db.last.closed&&s.activationDialog==null&&s.db.version==3,"close_before_callback_abandons_plan");\n\n  s=new TodayScreen();s.requestShortcutActivation();workerDone(s);s.activity.finishing=true;drain(s);\n  need(s.db.last.closed&&s.activationDialog==null&&s.db.version==3,"finishing_callback_abandons_plan");finish(s);\n\n  s=new TodayScreen();s.requestShortcutActivation();workerDone(s);s.activity.destroyed=true;drain(s);\n  need(s.db.last.closed&&s.activationDialog==null&&s.db.version==3,"destroyed_callback_abandons_plan");finish(s);\n\n  s=preview();AlertDialog stale=s.activationDialog;AppDatabase.ShortcutActivationPlan plan=s.activationPlan;\n  finish(s);CheckBox.last.yes=true;stale.pos.click();\n  need(plan.closed&&s.activationPlan==null&&s.db.confirmed==0,"close_invalidates_visible_consent");\n\n  s=preview();\n  try(Barrier hold=new Barrier(s)){\n   CheckBox.last.yes=true;s.activationDialog.pos.click();\n   need(s.activationAttempt!=null&&s.db.confirmed==0,"confirm_really_queued");s.close();\n  }\n  workerDone(s);drain(s);\n  need(s.db.confirmed==0&&s.db.version==3&&s.db.last.closed&&s.db.closed&&s.activity.restart==0,\n       "close_before_confirm_refuses_commit");\n\n  s=preview();CheckBox.last.yes=true;s.activationDialog.pos.click();workerDone(s);\n  need(s.db.confirmed==1&&s.db.version==4&&s.activity.restart==0,"commit_before_callback_witness");\n  finish(s);\n  need(s.db.version==4&&s.db.closed&&s.activationAttempt==null&&s.activity.restart==0&&s.activity.failed==0,\n       "close_after_commit_never_reopens_old_activity");\n\n  s=preview();s.db.fail=true;CheckBox.last.yes=true;s.activationDialog.pos.click();workerDone(s);\n  need(s.db.version==3&&s.activity.failed==0,"failed_confirm_callback_pending");\n  finish(s);\n  need(s.db.version==3&&s.db.closed&&s.activationAttempt==null&&s.activity.restart==0&&s.activity.failed==0,\n       "closed_failure_never_reopens_old_activity");\n }\n public static void main(String[] ignored){\n  try{runTests();}catch(Throwable failed){failed.printStackTrace();System.exit(1);}\n }\n')

_lifecycle_previous_selftest=selftest
def selftest():
    activation_lifecycle_selftest()
    _lifecycle_previous_selftest()

# Persist the already enforced UI labels without changing legacy parse results.
def ui_phase_evidence(raw, phase, api):
    import hashlib
    import json
    legacy = parse_phase(raw, phase, api)
    value = {
        "phase": phase, "api": api,
        "legacy_labels": legacy,
        "native_startup_labels": parse_native_startup(raw, phase),
        "activation_ui_labels": parse_activation_ui(raw, phase),
        "raw_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }
    return json.loads(json.dumps(value, ensure_ascii=False))


def require_ui_evidence(value, raw, phase, api):
    import hashlib
    need(set(value) == {"phase", "api", "legacy_labels", "native_startup_labels",
                       "activation_ui_labels", "raw_bytes", "raw_sha256"},
         "UI evidence exact fields")
    need(value["phase"] == phase and value["api"] == api, "UI evidence phase identity")
    need(value["legacy_labels"] == parse_phase(raw, phase, api), "UI evidence legacy preserved")
    need(value["native_startup_labels"] == NATIVE_STARTUP_LABELS[phase],
         "UI evidence startup labels")
    need(value["activation_ui_labels"] == ACTIVATION_UI_LABELS[phase],
         "UI evidence activation labels")
    need(value["raw_bytes"] == len(raw) and
         value["raw_sha256"] == hashlib.sha256(raw).hexdigest(),
         "UI evidence raw identity")


def ui_evidence_selftest():
    import copy
    import json
    positive = negative = 0
    for phase in ("seed", "reopen"):
        for api in (26, 34):
            raw = fixture(phase, api)
            # The old parser still accepts this stream, but alone cannot expose
            # either new family as its own serialized report field.
            old = {"phase": phase, "api": api, "legacy_labels": parse_phase(raw, phase, api)}
            try:
                require_ui_evidence(old, raw, phase, api)
            except AssertionError as exc:
                need(str(exc) == "UI evidence exact fields", "UI evidence original RED")
            else:
                raise AssertionError("old report hides UI coverage")
            good = json.loads(json.dumps(ui_phase_evidence(raw, phase, api)))
            require_ui_evidence(good, raw, phase, api)
            positive += 1
            bads = []
            for key in good:
                bad = copy.deepcopy(good); del bad[key]
                bads.append((bad, "UI evidence exact fields"))
            for key, wrong, reason in (
                ("phase", "wrong", "UI evidence phase identity"),
                ("api", 99, "UI evidence phase identity"),
                ("legacy_labels", [], "UI evidence legacy preserved"),
                ("native_startup_labels", [], "UI evidence startup labels"),
                ("activation_ui_labels", [], "UI evidence activation labels"),
                ("raw_bytes", len(raw)+1, "UI evidence raw identity"),
                ("raw_sha256", "0"*64, "UI evidence raw identity"),
            ):
                bad = copy.deepcopy(good); bad[key] = wrong
                bads.append((bad, reason))
            for bad, reason in bads:
                try:
                    require_ui_evidence(bad, raw, phase, api)
                except AssertionError as exc:
                    need(str(exc) == reason, "UI evidence exact negative witness")
                    negative += 1
                else:
                    raise AssertionError("UI evidence mutation survived")
    need((positive, negative) == (4, 56), "UI evidence test population")
    print("UI_EVIDENCE_SERIALIZATION 4_positive 56_witnessed_negative ORIGINAL_REPORT_RED PASS")


_ui_evidence_previous_selftest = selftest
def selftest():
    ui_evidence_selftest()
    _ui_evidence_previous_selftest()

ACTIVATION_READER_SOURCE='"""Read-only independent activation-UI oracle. Not yet wired into device CI."""\nimport pathlib\nimport sqlite3\nimport struct\nimport hashlib\n\nOLD_TABLES = "revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports".split()\nLIMIT = 8 * 1024 * 1024\n\n\ndef require(ok, message):\n    if not ok:\n        raise AssertionError(message)\n\n\ndef old_cells(raw):\n    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, "oracle byte budget")\n    at = 0\n    def take(n):\n        nonlocal at\n        require(0 <= n <= len(raw)-at, "oracle truncated")\n        value = raw[at:at+n]\n        at += n\n        return value\n    def integer():\n        return struct.unpack(">i", take(4))[0]\n    def text():\n        return take(integer()).decode("utf-8", "strict")\n    result = {}\n    for table in OLD_TABLES:\n        require(text() == table, "oracle exact ordered tables")\n        count, width = integer(), integer()\n        require(0 < count <= 100000 and 1 < width <= 100, "oracle nonempty row and column budget")\n        columns = [text() for _ in range(width)]\n        rows = []\n        for _ in range(count):\n            row = []\n            for _ in range(width):\n                kind = take(1)[0]\n                if kind == 0: value = ["null", None]\n                elif kind == 1: value = ["integer", struct.unpack(">q", take(8))[0]]\n                elif kind == 3: value = ["text", text()]\n                elif kind == 4: value = ["blob", take(integer()).hex()]\n                else: raise AssertionError("oracle SQL type")\n                row.append(value)\n            rows.append(row)\n        result[table] = dict(columns=columns, rows=rows)\n    require(at == len(raw), "oracle trailing bytes")\n    return result\n\n\ndef activation_snapshot(path, expected):\n    path = pathlib.Path(path)\n    require(not path.is_symlink() and path.is_file() and 0 < path.stat().st_size <= LIMIT,\n            "activation database file budget")\n    want = old_cells(expected)\n    observed = {}\n    with sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True) as db:\n        require(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "activation SQLite integrity")\n        require(db.execute("PRAGMA foreign_key_check").fetchall() == [], "activation SQLite foreign keys")\n        require(db.execute("PRAGMA user_version").fetchone() == (4,), "activation schema4")\n        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type=\'table\'")\n                 if not r[0].startswith("sqlite_") and r[0] != "android_metadata"}\n        require(names == set(OLD_TABLES + ["category_shortcuts"]), "activation exact table set")\n        for table in OLD_TABLES:\n            cursor = db.execute("SELECT rowid,* FROM " + table + " ORDER BY rowid")\n            rows = []\n            for row in cursor:\n                values = []\n                for value in row:\n                    if value is None: cell = ["null", None]\n                    elif type(value) is int: cell = ["integer", value]\n                    elif type(value) is str: cell = ["text", value]\n                    elif type(value) is bytes: cell = ["blob", value.hex()]\n                    else: raise AssertionError("activation SQL type")\n                    values.append(cell)\n                rows.append(values)\n            observed[table] = dict(columns=[c[0] for c in cursor.description], rows=rows)\n        require(observed == want, "activation all old typed cells and rowids")\n        cursor = db.execute("SELECT * FROM category_shortcuts ORDER BY category_id,application_id")\n        require([c[0] for c in cursor.description] == ["category_id", "application_id"] and\n                cursor.fetchall() == [], "activation empty exact shortcut table")\n    return dict(schema=4, old_cells=observed,\n                expected_sha256=hashlib.sha256(expected).hexdigest(), category_shortcuts=[])\n'
ACTIVATION_ORACLE_JAVA='\nimport java.io.*;import java.nio.file.*;\nclass Oracle {\nstatic final String[] OLD="revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports".split(" ");\nstatic void assertThat(boolean ok,String s){if(!ok)throw new AssertionError(s);}\nstatic class SQLiteDatabase {\n Cursor rawQuery(String sql,Object ignored){return new Cursor();}\n}\nstatic class Cursor implements AutoCloseable {\n boolean moved;\n int getCount(){return 1;}int getColumnCount(){return 5;}\n String[] getColumnNames(){return new String[]{"rowid","empty","num","label","payload"};}\n boolean moveToNext(){if(moved)return false;moved=true;return true;}\n int getType(int i){return new int[]{1,0,1,3,4}[i];}\n long getLong(int i){return i==0?7:-9007199254740993L;}\n String getString(int i){return "中文😀";}byte[] getBlob(int i){return new byte[]{0,1,(byte)255};}\n public void close(){}\n}\n    private static void text(DataOutputStream out,String s)throws IOException{\n        byte[] b=s.getBytes(java.nio.charset.StandardCharsets.UTF_8);out.writeInt(b.length);out.write(b);\n    }\n    private static byte[] cells(SQLiteDatabase db,boolean includeRevision)throws IOException{\n        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);\n        for(String table:OLD){\n            if(!includeRevision&&table.equals("revision"))continue;\n            try(Cursor c=db.rawQuery("SELECT rowid,* FROM "+table+" ORDER BY rowid",null)){\n                text(out,table);out.writeInt(c.getCount());out.writeInt(c.getColumnCount());\n                for(String column:c.getColumnNames())text(out,column);\n                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){\n                    int type=c.getType(i);out.writeByte(type);\n                    if(type==1)out.writeLong(c.getLong(i));\n                    else if(type==3)text(out,c.getString(i));\n                    else if(type==4){byte[] b=c.getBlob(i);out.writeInt(b.length);out.write(b);}\n                    else assertThat(type==0,"unexpected SQL type");\n                }\n            }\n        }out.flush();return bytes.toByteArray();\n    }\npublic static void main(String[] args)throws Exception{Files.write(Path.of(args[0]),cells(new SQLiteDatabase(),true));}\n}\n'

# Reader lives in an isolated namespace: no legacy verifier globals are replaced.
_activation_reader_scope = {"__name__": "independent_activation_reader"}
exec(compile(ACTIVATION_READER_SOURCE, "independent_activation_reader", "exec"),
     _activation_reader_scope)

def activation_file_bytes(path):
    import pathlib
    path = pathlib.Path(path)
    need(not path.is_symlink() and path.is_file(), "activation evidence regular file")
    with path.open("rb") as stream:
        raw = stream.read(8*1024*1024+1)
    need(0 < len(raw) <= 8*1024*1024, "activation evidence byte budget")
    return raw


def activation_file_identity(raw):
    import hashlib
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def collect_activation_ui(command, names, folder, receipt, phase):
    import pathlib
    folder = pathlib.Path(folder)
    need(phase in ("seed", "reopen"), "activation collection phase")
    need("schema4-activation-ui.db" in names, "activation UI fixture absent")
    files = {}
    for name in ("schema4-activation-ui.db", "schema4-activation-ui.db-wal"):
        if name in names:
            raw = command(["exec-out", "run-as", PACKAGE, "cat", "databases/"+name])
            need(0 < len(raw) <= 8*1024*1024, "activation collection byte budget")
            (folder/name).write_bytes(raw)
            files[name] = activation_file_identity(raw)
    expected = command(["exec-out", "run-as", PACKAGE, "cat",
                        "files/activation-ui-expected.bin"])
    need(0 < len(expected) <= 8*1024*1024, "activation oracle collection budget")
    (folder/"activation-ui-expected.bin").write_bytes(expected)
    files["activation-ui-expected.bin"] = activation_file_identity(expected)
    snapshot = _activation_reader_scope["activation_snapshot"](
        folder/"schema4-activation-ui.db", expected)
    receipt.setdefault("activation_ui_snapshots", {})[phase] = {
        "files": files, "snapshot": snapshot}


def validate_activation_ui_receipt(receipt):
    phases = receipt.get("activation_ui_snapshots")
    need(isinstance(phases, dict) and set(phases) == {"seed", "reopen"},
         "activation UI both phases collected")
    for phase in ("seed", "reopen"):
        value = phases[phase]
        need(set(value) == {"files", "snapshot"}, "activation UI receipt fields")
        names = set(value["files"])
        required = {"schema4-activation-ui.db", "activation-ui-expected.bin"}
        need(names in (required, required | {"schema4-activation-ui.db-wal"}),
             "activation UI exact evidence files")
        for identity in value["files"].values():
            need(set(identity) == {"bytes", "sha256"} and
                 type(identity["bytes"]) is int and 0 < identity["bytes"] <= 8*1024*1024 and
                 re.fullmatch("[0-9a-f]{64}", identity["sha256"]) is not None,
                 "activation UI file identity shape")
        need(value["snapshot"]["schema"] == 4 and
             value["snapshot"]["category_shortcuts"] == [] and
             value["snapshot"]["expected_sha256"] ==
             value["files"]["activation-ui-expected.bin"]["sha256"],
             "activation UI oracle binding")
    need(phases["seed"]["snapshot"] == phases["reopen"]["snapshot"],
         "activation UI exact cross process snapshot")
    return phases


def replay_activation_ui(folder, receipt, phase):
    import pathlib
    phases = validate_activation_ui_receipt(receipt)
    local = pathlib.Path(folder)/phase
    value = phases[phase]
    for name, identity in value["files"].items():
        need(activation_file_identity(activation_file_bytes(local/name)) == identity,
             "activation UI report file identity differs")
    wal = local/"schema4-activation-ui.db-wal"
    need(wal.exists() == ("schema4-activation-ui.db-wal" in value["files"]),
         "activation UI unrecorded WAL")
    expected = activation_file_bytes(local/"activation-ui-expected.bin")
    independent = _activation_reader_scope["activation_snapshot"](
        local/"schema4-activation-ui.db", expected)
    need(independent == value["snapshot"], "activation UI independent replay differs")
    return True


def activation_replay_source_gate(source):
    import ast
    tree = ast.parse(source)
    definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    androids = [n for n in definitions if n.name == "android"]
    reports = [n for n in definitions if n.name == "report"]
    need(len(androids) == len(reports) == 1, "activation source entrypoints")
    def calls(node, name):
        return [n for n in ast.walk(node) if isinstance(n, ast.Call) and
                isinstance(n.func, ast.Name) and n.func.id == name]
    collection = calls(androids[0], "collect_activation_ui")
    need(len(collection) == 1, "activation actual collection hook")
    need([ast.unparse(n) for n in collection[0].args] ==
         ["command", "names", "folder", "receipt", "phase"],
         "activation collection arguments")
    # Require the collector directly in the same seed/reopen body, after the
    # existing stop and old-UI snapshot, not in an uncalled nested helper.
    owners = [n for n in ast.walk(androids[0]) if isinstance(n, ast.For) and
              any(isinstance(s, ast.Expr) and s.value is collection[0] for s in n.body)]
    need(len(owners) == 1 and ast.unparse(owners[0].target) == "phase" and
         ast.literal_eval(owners[0].iter) == ("seed", "reopen"),
         "activation collector actual phase loop")
    statements = owners[0].body
    index = next(i for i,n in enumerate(statements) if isinstance(n, ast.Expr) and n.value is collection[0])
    need(index > 0 and isinstance(statements[index-1], ast.Assign) and
         ast.unparse(statements[index-1].targets[0]) == "receipt['ui_snapshots'][phase]",
         "activation collector follows original UI snapshot")
    need(any(calls(n,"stop") for n in statements[:index]), "activation collector stopped phase")
    need(len(calls(reports[0], "replay_shortcut_databases")) == 1,
         "activation report invokes independent replay")
    need(len(calls(reports[0], "replay_activation_ui")) == 1,
         "activation independent replay hook")
    need(len(calls(androids[0], "validate_activation_ui_receipt")) == 1,
         "activation collection completion gate")


_activation_replay_previous_selftest = selftest
def selftest():
    activation_replay_selftest()
    activation_replay_wiring_selftest(pathlib.Path(__file__).read_text())
    _activation_replay_previous_selftest()

def activation_replay_selftest():
    import copy
    import pathlib
    import shutil
    import sqlite3
    import subprocess
    import tempfile
    import ast
    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        java = root/"Oracle.java"
        java.write_text(ACTIVATION_ORACLE_JAVA)
        compile_result = subprocess.run(
            ["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", "-d", temp, str(java)],
            capture_output=True, timeout=30)
        need(compile_result.returncode == 0, "activation oracle compiler: "+compile_result.stderr.decode(errors="replace"))
        encoded = subprocess.run(["java", "-cp", temp, "Oracle", str(root/"expected.bin")],
                                 capture_output=True, timeout=10)
        need(encoded.returncode == 0, "activation Java oracle execution")
        oracle = (root/"expected.bin").read_bytes()
        dbfile = root/"fixture.db"
        with sqlite3.connect(dbfile) as db:
            for table in _activation_reader_scope["OLD_TABLES"]:
                db.execute("CREATE TABLE "+table+"(empty,num INTEGER,label TEXT,payload BLOB)")
                db.execute("INSERT INTO "+table+"(rowid,empty,num,label,payload) VALUES(7,NULL,?,?,?)",
                           (-9007199254740993, "中文😀", b"\0\1\xff"))
            db.execute("CREATE TABLE category_shortcuts(category_id INTEGER,application_id INTEGER)")
            db.execute("PRAGMA user_version=4")
        data = dbfile.read_bytes()
        commands = []
        def command(args):
            commands.append(args)
            need(args[:4] == ["exec-out", "run-as", PACKAGE, "cat"], "collection exact adb argv")
            values = {"databases/schema4-activation-ui.db": data,
                      "files/activation-ui-expected.bin": oracle}
            return values[args[4]]
        receipt = {}
        for phase in ("seed", "reopen"):
            target=root/phase;target.mkdir()
            collect_activation_ui(command, ["schema4-activation-ui.db"], target, receipt, phase)
        need(len(commands) == 4, "activation exact collection population")
        validate_activation_ui_receipt(receipt)
        need(all(replay_activation_ui(root, receipt, phase) for phase in ("seed","reopen")),
             "activation both independent replays")
        need(dbfile.read_bytes() == data, "activation fixture remained unchanged")
        negative=0
        def reject(action, reason):
            nonlocal negative
            try:
                action()
            except AssertionError as exc:
                need(str(exc) == reason, "activation replay precise witness: "+str(exc))
                negative+=1
            else:
                raise AssertionError("activation replay negative survived "+reason)
        reject(lambda: validate_activation_ui_receipt({}), "activation UI both phases collected")
        for phase in ("seed","reopen"):
            bad=copy.deepcopy(receipt);del bad["activation_ui_snapshots"][phase]
            reject(lambda: validate_activation_ui_receipt(bad), "activation UI both phases collected")
        bad=copy.deepcopy(receipt);del bad["activation_ui_snapshots"]["seed"]["files"]["activation-ui-expected.bin"]
        reject(lambda: validate_activation_ui_receipt(bad), "activation UI exact evidence files")
        bad=copy.deepcopy(receipt)
        bad["activation_ui_snapshots"]["seed"]["files"]["schema4-activation-ui.db"]["bytes"]=0
        reject(lambda: validate_activation_ui_receipt(bad), "activation UI file identity shape")
        reject(lambda: collect_activation_ui(command, [], root/"seed", {}, "seed"),
               "activation UI fixture absent")
        for filename in ("schema4-activation-ui.db","activation-ui-expected.bin"):
            target=root/"seed"/filename
            original=target.read_bytes();target.write_bytes(original+b"x")
            reject(lambda: replay_activation_ui(root,receipt,"seed"),
                   "activation UI report file identity differs")
            target.write_bytes(original)
        # Spoofing a device snapshot or refreshing its digest must not bypass
        # actual independent SQLite content checks.
        with sqlite3.connect(root/"seed/schema4-activation-ui.db") as db:
            db.execute("UPDATE todos SET label='tampered'")
        bad=copy.deepcopy(receipt)
        bad["activation_ui_snapshots"]["seed"]["files"]["schema4-activation-ui.db"] = \
            activation_file_identity((root/"seed/schema4-activation-ui.db").read_bytes())
        reject(lambda: replay_activation_ui(root,bad,"seed"), "activation all old typed cells and rowids")
        (root/"seed/schema4-activation-ui.db").write_bytes(data)
        bad=copy.deepcopy(receipt)
        for phase in ("seed","reopen"):
            bad["activation_ui_snapshots"][phase]["snapshot"]["old_cells"]["todos"]["rows"][0][3][1]="false claim"
        reject(lambda: replay_activation_ui(root,bad,"seed"), "activation UI independent replay differs")
        wal=root/"seed/schema4-activation-ui.db-wal";wal.write_bytes(b"unrecorded")
        reject(lambda: replay_activation_ui(root,receipt,"seed"), "activation UI unrecorded WAL")
        wal.unlink()
        absent=root/"seed/activation-ui-expected.bin"
        original=absent.read_bytes();absent.unlink()
        reject(lambda: replay_activation_ui(root,receipt,"seed"), "activation evidence regular file")
        need(not absent.exists(), "missing evidence read must not create")
        absent.write_bytes(original)
        # A WAL-only committed change is invisible in main-only copy but must
        # be rejected when the adjacent WAL is present.
        live=sqlite3.connect(dbfile)
        try:
            need(live.execute("PRAGMA journal_mode=WAL").fetchone()==("wal",), "WAL mode witness")
            live.execute("PRAGMA wal_autocheckpoint=0")
            live.execute("UPDATE todos SET label='committed WAL mutation'")
            live.commit()
            main=root/"main-only.db";shutil.copyfile(dbfile,main)
            _activation_reader_scope["activation_snapshot"](main,oracle)
            pair=root/"paired.db";shutil.copyfile(dbfile,pair)
            pairwal=pathlib.Path(str(pair)+"-wal")
            shutil.copyfile(str(dbfile)+"-wal",pairwal)
            frozen=(pair.read_bytes(),pairwal.read_bytes())
            reject(lambda: _activation_reader_scope["activation_snapshot"](pair,oracle),
                   "activation all old typed cells and rowids")
            need((pair.read_bytes(),pairwal.read_bytes())==frozen, "WAL and DB unchanged after read")
        finally:
            live.close()
        need(negative==13, "activation replay exact negative population")
    print("ACTIVATION_UI_INDEPENDENT_REPLAY collection=2 report_replay=2 Java_oracle=1 witnessed_negative=13 WAL_only_mutation=1 PASS_NOT_ANDROID")


def activation_replay_wiring_selftest(source):
    import ast
    activation_replay_source_gate(source)
    negative=0
    for target, reason in (
        ("collect_activation_ui", "activation actual collection hook"),
        ("replay_activation_ui", "activation independent replay hook"),
        ("replay_shortcut_databases", "activation report invokes independent replay"),
        ("validate_activation_ui_receipt", "activation collection completion gate"),
    ):
        tree=ast.parse(source)
        function="android" if target in ("collect_activation_ui", "validate_activation_ui_receipt") else "report"
        definitions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==function]
        need(bool(definitions), "wiring mutant function witness")
        calls=[n for n in ast.walk(definitions[-1]) if isinstance(n,ast.Call) and
               isinstance(n.func,ast.Name) and n.func.id==target]
        need(len(calls)==1, "wiring mutant call witness")
        calls[0].func.id="omitted_"+target
        try:
            activation_replay_source_gate(ast.unparse(tree))
        except AssertionError as exc:
            need(str(exc)==reason, "wiring exact omission witness")
            negative+=1
        else:
            raise AssertionError("whole-stage omission accepted")
    need(negative==4, "wiring negative population")
    print("ACTIVATION_UI_WIRING actual_source_positive=1 whole_stage_omissions=4 PASS")
"""Keep legacy scripted-I/O fixtures isolated; real report entry tested below."""
def legacy_activation_report_double(folder, receipt, phase):
    # Deliberately a scoped scripted-I/O double for OLD report fixtures only.
    # Never installed in production globals and not claimed as DB acceptance.
    need(phase in ("seed", "reopen") and receipt["api"] in (26, 34),
         "legacy activation report double inputs")
    return True


def activation_report_entry_selftest():
    import ast, contextlib, copy, inspect, io, json, os, pathlib
    import sqlite3, subprocess, sys, tempfile, types
    from unittest.mock import patch
    target = report
    with tempfile.TemporaryDirectory() as temporary:
        base = pathlib.Path(temporary)
        (base/"Oracle.java").write_text(ACTIVATION_ORACLE_JAVA)
        compiled = subprocess.run(
            ["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", "-d", temporary,
             str(base/"Oracle.java")], capture_output=True, timeout=30)
        need(compiled.returncode == 0, "report Java oracle compile")
        encoded = subprocess.run(["java", "-cp", temporary, "Oracle", str(base/"oracle.bin")],
                                 capture_output=True, timeout=10)
        need(encoded.returncode == 0, "report Java oracle execution")
        oracle = (base/"oracle.bin").read_bytes()
        with sqlite3.connect(base/"fixture.db") as db:
            for table in _activation_reader_scope["OLD_TABLES"]:
                db.execute("CREATE TABLE "+table+"(empty,num INTEGER,label TEXT,payload BLOB)")
                db.execute("INSERT INTO "+table+"(rowid,empty,num,label,payload) VALUES(7,NULL,?,?,?)",
                           (-9007199254740993, "中文😀", b"\0\1\xff"))
            db.execute("CREATE TABLE category_shortcuts(category_id INTEGER,application_id INTEGER)")
            db.execute("PRAGMA user_version=4")
        database = (base/"fixture.db").read_bytes()
        def run_case(case, entry):
            with tempfile.TemporaryDirectory() as temp:
                root=pathlib.Path(temp)
                sample, expected, sources = receipt_fixture()
                for api in (26,34):
                    local,_,_=receipt_fixture(api)
                    place=root/f"collected-shortcuts/shortcut-device-api-{api}/shortcut-device"
                    place.mkdir(parents=True)
                    def command(args):
                        need(args[:4] == ["exec-out","run-as",PACKAGE,"cat"], "report fixture collection argv")
                        return {"databases/schema4-activation-ui.db":database,
                                "files/activation-ui-expected.bin":oracle}[args[4]]
                    for phase in ("seed","reopen"):
                        stage=place/phase;stage.mkdir()
                        collect_activation_ui(command,["schema4-activation-ui.db"],stage,local,phase)
                        (place/(phase+".log")).write_bytes(fixture(phase,api))
                    if api==26:
                        if case=="missing_database":
                            (place/"seed/schema4-activation-ui.db").unlink()
                        elif case=="wrong_hash":
                            local["activation_ui_snapshots"]["seed"]["files"]["schema4-activation-ui.db"]["sha256"]="0"*64
                        elif case=="wrong_cells":
                            path=place/"seed/schema4-activation-ui.db"
                            with sqlite3.connect(path) as db:db.execute("UPDATE todos SET label='changed'")
                            local["activation_ui_snapshots"]["seed"]["files"]["schema4-activation-ui.db"]=activation_file_identity(path.read_bytes())
                        elif case=="missing_receipt":
                            del local["activation_ui_snapshots"]
                        elif case=="missing_reopen":
                            del local["activation_ui_snapshots"]["reopen"]
                        elif case=="forged_snapshot":
                            for phase in ("seed","reopen"):
                                local["activation_ui_snapshots"][phase]["snapshot"]["old_cells"]["todos"]["rows"][0][3][1]="forged"
                    if api==34 and case=="missing_oracle34":
                        (place/"reopen/activation-ui-expected.bin").unlink()
                    (place/"result.json").write_text(json.dumps(local))
                    built=dict(status="PASS",restored=True,source_files=sources,**expected,
                               product=dict(bytes=1,sha256="b"*64,certificate="c"*64),
                               test=dict(bytes=1,sha256="b"*64,certificate="c"*64))
                    (place.parent/"shortcut-build.json").write_text(json.dumps(built))
                sent=[];observed=[]
                class Publisher:
                    @staticmethod
                    def publish(api,path,raw):
                        sent.append(json.loads(raw))
                        if case=="publish_failure":raise OSError("original publisher failure")
                        return {"html_url":"https://example.invalid/evidence"}
                def replay(folder, receipt, phase):
                    observed.append((receipt["api"],phase))
                    return replay_activation_ui(folder,receipt,phase)
                # Existing database families have their own legacy tests.
                # Only their reads are scripted here; activation SQLite is REAL.
                scope=dict(globals(), ROOT=root, source_identity=lambda:sources,
                    database_snapshot=lambda path:copy.deepcopy(sample["snapshots"]["seed"]),
                    replay_shortcut_databases=lambda folder,receipt,phase:None,
                    replay_activation_ui=replay)
                scope["replay_native_ui"]=legacy_native_report_double
                runner=types.FunctionType(entry.__code__,scope)
                env=dict(GITHUB_SHA=expected["commit"],GITHUB_RUN_ID="1",GITHUB_RUN_ATTEMPT="1",
                    NEEDS_JSON=json.dumps({k:{"result":"success"} for k in ("shortcut_host","shortcut_device")}))
                error=None
                with patch.dict(os.environ,env),patch.dict(sys.modules,{"verify_evidence":Publisher}),contextlib.redirect_stdout(io.StringIO()):
                    try:runner()
                    except Exception as exc:error=exc
                need(len(sent)==1, "activation report publishes original outcome")
                return sent[0],error,observed
        good,error,observed=run_case("valid",target)
        need(error is None and good["status"]=="PASS" and observed==[(26,"seed"),(26,"reopen"),(34,"seed"),(34,"reopen")],
             "activation actual report positive and four reads")
        reasons={
            "missing_database":"activation evidence regular file",
            "missing_oracle34":"activation evidence regular file",
            "wrong_hash":"activation UI report file identity differs",
            "wrong_cells":"activation all old typed cells and rowids",
            "missing_receipt":"activation UI both phases collected",
            "missing_reopen":"activation UI both phases collected",
            "forged_snapshot":"activation UI independent replay differs"}
        for case,reason in reasons.items():
            value,error,observed=run_case(case,target)
            api="34" if case=="missing_oracle34" else "26"
            need(type(error) is AssertionError and value["status"]=="FAIL" and
                 value["device_validation_errors"].get(api)=="AssertionError("+repr(reason)+")",
                 "activation actual report precise rejection "+case)
            need(set(value["devices"])=={"26","34"} and
                 (api=="34" or (34,"reopen") in observed), "activation first API cannot hide second")
        value,error,observed=run_case("publish_failure",target)
        need(type(error) is OSError and str(error)=="original publisher failure",
             "activation report preserves publisher failure")
        tree=ast.parse(inspect.getsource(target))
        removed=[]
        class Omit(ast.NodeTransformer):
            def visit_Expr(self,node):
                if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=="replay_activation_ui":
                    removed.append(node);return None
                return self.generic_visit(node)
        tree=Omit().visit(tree);need(len(removed)==1,"actual report replay omission applied")
        scope=dict(globals());exec(compile(ast.fix_missing_locations(tree),"<actual-report-omit>","exec"),scope)
        mutant=scope["report"]
        value,error,_=run_case("valid",mutant)
        need(error is None and value["status"]=="PASS", "report omission positive witness")
        value,error,observed=run_case("missing_database",mutant)
        need(error is None and value["status"]=="PASS" and observed==[],
             "report omission must demonstrate false acceptance")
        print("ACTIVATION_ACTUAL_REPORT real_SQLite positive=1 precise_negative=7 publisher_failure=1 whole_replay_omission_witness=1 PASS_NOT_GITHUB_NOT_ANDROID")


_activation_report_previous_selftest=selftest
def selftest():
    activation_report_entry_selftest()
    _activation_report_previous_selftest()

NATIVE_READER_SOURCE='"""Independent replay of the fixed native-startup fixture, not a general decoder.\n\nThe device\'s bridgeCells oracle is old typed cells followed by a count and two\nordered pairs. The pair values here are frozen independently from startupUiSeed,\nnot derived from a database or a receipt. No product encoder is imported.\n"""\nimport hashlib\nimport pathlib\nimport sqlite3\nimport struct\n\nNATIVE_STARTUP_LINKS = [[7, 10], [8, 10]]\n\n\ndef native_startup_snapshot(path, expected, old_reader):\n    need = old_reader["require"]\n    limit = old_reader["LIMIT"]\n    path = pathlib.Path(path)\n    need(not path.is_symlink() and path.is_file() and\n         0 < path.stat().st_size <= limit, "native database file budget")\n    need(type(expected) is bytes and 36 < len(expected) <= limit,\n         "native oracle byte budget")\n    # bridgeCells: int32 count, then count pairs of big-endian int64 identities.\n    # This fixed fixture must contain both known links, never a self-derived set.\n    need(expected[-36:] == struct.pack(">iqqqq", 2, 7, 10, 8, 10),\n         "native fixed bridge oracle relations")\n    want = old_reader["old_cells"](expected[:-36])\n    observed = {}\n    with sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True) as db:\n        need(db.execute("PRAGMA integrity_check").fetchall() == [("ok",)],\n             "native SQLite integrity")\n        need(db.execute("PRAGMA foreign_key_check").fetchall() == [],\n             "native SQLite foreign keys")\n        need(db.execute("PRAGMA user_version").fetchone() == (4,),\n             "native schema4")\n        names = {row[0] for row in db.execute(\n            "SELECT name FROM sqlite_master WHERE type=\'table\'")\n            if not row[0].startswith("sqlite_") and row[0] != "android_metadata"}\n        need(names == set(old_reader["OLD_TABLES"] + ["category_shortcuts"]),\n             "native exact table set")\n        for table in old_reader["OLD_TABLES"]:\n            cursor = db.execute("SELECT rowid,* FROM "+table+" ORDER BY rowid")\n            rows = []\n            for row in cursor:\n                values = []\n                for value in row:\n                    if value is None:\n                        cell = ["null", None]\n                    elif type(value) is int:\n                        cell = ["integer", value]\n                    elif type(value) is str:\n                        cell = ["text", value]\n                    elif type(value) is bytes:\n                        cell = ["blob", value.hex()]\n                    else:\n                        raise AssertionError("native SQL type")\n                    values.append(cell)\n                rows.append(values)\n            observed[table] = {\n                "columns": [column[0] for column in cursor.description],\n                "rows": rows}\n        need(observed == want, "native all old typed cells and rowids")\n        cursor = db.execute(\n            "SELECT * FROM category_shortcuts ORDER BY category_id,application_id")\n        need([column[0] for column in cursor.description] ==\n             ["category_id", "application_id"], "native shortcut columns")\n        links = [list(row) for row in cursor]\n        need(all(type(value) is int for row in links for value in row) and\n             links == NATIVE_STARTUP_LINKS, "native exact typed shortcut relations")\n    return dict(schema=4, old_cells=observed,\n                expected_sha256=hashlib.sha256(expected).hexdigest(),\n                category_shortcuts=links)\n'
NATIVE_ORACLE_JAVA='\nimport java.io.*;import java.nio.file.*;\nclass Oracle {\nstatic final String[] OLD="revision categories applications activities paths tags batches ledger checkins media notes blocks fields field_options field_values field_notes todos legacy_imports".split(" ");\nstatic void assertThat(boolean ok,String s){if(!ok)throw new AssertionError(s);}\nstatic class SQLiteDatabase {\n Cursor rawQuery(String sql,Object ignored){return new Cursor(sql.contains("category_id"));}\n}\nstatic class Cursor implements AutoCloseable {\n boolean moved;boolean links;int row;\n Cursor(boolean links){this.links=links;}\n int getCount(){return links?2:1;}int getColumnCount(){return 5;}\n String[] getColumnNames(){return new String[]{"rowid","empty","num","label","payload"};}\n boolean moveToNext(){if(links)return ++row<=2;if(moved)return false;moved=true;return true;}\n int getType(int i){return links?1:new int[]{1,0,1,3,4}[i];}\n long getLong(int i){return links?(i==0?(row==1?7:8):10):(i==0?7:-9007199254740993L);}\n String getString(int i){return "中文😀";}byte[] getBlob(int i){return new byte[]{0,1,(byte)255};}\n public void close(){}\n}\n    private static void text(DataOutputStream out,String s)throws IOException{\n        byte[] b=s.getBytes(java.nio.charset.StandardCharsets.UTF_8);out.writeInt(b.length);out.write(b);\n    }\n    private static byte[] cells(SQLiteDatabase db,boolean includeRevision)throws IOException{\n        ByteArrayOutputStream bytes=new ByteArrayOutputStream();DataOutputStream out=new DataOutputStream(bytes);\n        for(String table:OLD){\n            if(!includeRevision&&table.equals("revision"))continue;\n            try(Cursor c=db.rawQuery("SELECT rowid,* FROM "+table+" ORDER BY rowid",null)){\n                text(out,table);out.writeInt(c.getCount());out.writeInt(c.getColumnCount());\n                for(String column:c.getColumnNames())text(out,column);\n                while(c.moveToNext())for(int i=0;i<c.getColumnCount();i++){\n                    int type=c.getType(i);out.writeByte(type);\n                    if(type==1)out.writeLong(c.getLong(i));\n                    else if(type==3)text(out,c.getString(i));\n                    else if(type==4){byte[] b=c.getBlob(i);out.writeInt(b.length);out.write(b);}\n                    else assertThat(type==0,"unexpected SQL type");\n                }\n            }\n        }out.flush();return bytes.toByteArray();\n    }\n\n    private static byte[] bridgeCells(SQLiteDatabase db)throws Exception{\n        ByteArrayOutputStream bytes=new ByteArrayOutputStream();bytes.write(cells(db,true));\n        DataOutputStream out=new DataOutputStream(bytes);\n        try(Cursor c=db.rawQuery("SELECT category_id,application_id FROM category_shortcuts ORDER BY category_id,application_id",null)){\n            out.writeInt(c.getCount());\n            while(c.moveToNext()){assertThat(c.getType(0)==1&&c.getType(1)==1,"bridge typed keys");out.writeLong(c.getLong(0));out.writeLong(c.getLong(1));}\n        }\n        out.flush();return bytes.toByteArray();\n    }\n\npublic static void main(String[] args)throws Exception{Files.write(Path.of(args[0]),bridgeCells(new SQLiteDatabase()));}\n}\n'
_native_reader_scope={"__name__":"native_reader"}
exec(compile(NATIVE_READER_SOURCE,"native_reader","exec"),_native_reader_scope)
_native_reader_scope["OLD_TABLES"]=_activation_reader_scope["OLD_TABLES"]
_native_reader_scope["native_snapshot"]=lambda path,expected:_native_reader_scope["native_startup_snapshot"](path,expected,_activation_reader_scope)
def native_file_bytes(path):
    import pathlib
    path = pathlib.Path(path)
    need(not path.is_symlink() and path.is_file(), "native evidence regular file")
    with path.open("rb") as stream:
        raw = stream.read(8*1024*1024+1)
    need(0 < len(raw) <= 8*1024*1024, "native evidence byte budget")
    return raw


def native_file_identity(raw):
    import hashlib
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def collect_native_ui(command, names, folder, receipt, phase):
    import pathlib
    folder = pathlib.Path(folder)
    need(phase in ("seed", "reopen"), "native collection phase")
    need("schema4-startup-ui.db" in names, "native UI fixture absent")
    files = {}
    for name in ("schema4-startup-ui.db", "schema4-startup-ui.db-wal"):
        if name in names:
            raw = command(["exec-out", "run-as", PACKAGE, "cat", "databases/"+name])
            need(0 < len(raw) <= 8*1024*1024, "native collection byte budget")
            (folder/name).write_bytes(raw)
            files[name] = native_file_identity(raw)
    expected = command(["exec-out", "run-as", PACKAGE, "cat",
                        "files/startup-ui-expected.bin"])
    need(0 < len(expected) <= 8*1024*1024, "native oracle collection budget")
    (folder/"startup-ui-expected.bin").write_bytes(expected)
    files["startup-ui-expected.bin"] = native_file_identity(expected)
    snapshot = _native_reader_scope["native_snapshot"](
        folder/"schema4-startup-ui.db", expected)
    receipt.setdefault("native_ui_snapshots", {})[phase] = {
        "files": files, "snapshot": snapshot}


def validate_native_ui_receipt(receipt):
    phases = receipt.get("native_ui_snapshots")
    need(isinstance(phases, dict) and set(phases) == {"seed", "reopen"},
         "native UI both phases collected")
    for phase in ("seed", "reopen"):
        value = phases[phase]
        need(set(value) == {"files", "snapshot"}, "native UI receipt fields")
        names = set(value["files"])
        required = {"schema4-startup-ui.db", "startup-ui-expected.bin"}
        need(names in (required, required | {"schema4-startup-ui.db-wal"}),
             "native UI exact evidence files")
        for identity in value["files"].values():
            need(set(identity) == {"bytes", "sha256"} and
                 type(identity["bytes"]) is int and 0 < identity["bytes"] <= 8*1024*1024 and
                 re.fullmatch("[0-9a-f]{64}", identity["sha256"]) is not None,
                 "native UI file identity shape")
        need(value["snapshot"]["schema"] == 4 and
             value["snapshot"]["category_shortcuts"] == [[7,10],[8,10]] and
             value["snapshot"]["expected_sha256"] ==
             value["files"]["startup-ui-expected.bin"]["sha256"],
             "native UI oracle binding")
    need(phases["seed"]["snapshot"] == phases["reopen"]["snapshot"],
         "native UI exact cross process snapshot")
    return phases


def replay_native_ui(folder, receipt, phase):
    import pathlib
    phases = validate_native_ui_receipt(receipt)
    local = pathlib.Path(folder)/phase
    value = phases[phase]
    for name, identity in value["files"].items():
        need(native_file_identity(native_file_bytes(local/name)) == identity,
             "native UI report file identity differs")
    wal = local/"schema4-startup-ui.db-wal"
    need(wal.exists() == ("schema4-startup-ui.db-wal" in value["files"]),
         "native UI unrecorded WAL")
    expected = native_file_bytes(local/"startup-ui-expected.bin")
    independent = _native_reader_scope["native_snapshot"](
        local/"schema4-startup-ui.db", expected)
    need(independent == value["snapshot"], "native UI independent replay differs")
    return True



def native_replay_selftest():
    import copy
    import pathlib
    import shutil
    import sqlite3
    import subprocess
    import tempfile
    import ast
    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        java = root/"Oracle.java"
        java.write_text(NATIVE_ORACLE_JAVA)
        compile_result = subprocess.run(
            ["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", "-d", temp, str(java)],
            capture_output=True, timeout=30)
        need(compile_result.returncode == 0, "native oracle compiler: "+compile_result.stderr.decode(errors="replace"))
        encoded = subprocess.run(["java", "-cp", temp, "Oracle", str(root/"expected.bin")],
                                 capture_output=True, timeout=10)
        need(encoded.returncode == 0, "native Java oracle execution")
        oracle = (root/"expected.bin").read_bytes()
        dbfile = root/"fixture.db"
        with sqlite3.connect(dbfile) as db:
            for table in _native_reader_scope["OLD_TABLES"]:
                db.execute("CREATE TABLE "+table+"(empty,num INTEGER,label TEXT,payload BLOB)")
                db.execute("INSERT INTO "+table+"(rowid,empty,num,label,payload) VALUES(7,NULL,?,?,?)",
                           (-9007199254740993, "中文😀", b"\0\1\xff"))
            db.execute("CREATE TABLE category_shortcuts(category_id INTEGER,application_id INTEGER)")
            db.execute("INSERT INTO category_shortcuts VALUES(7,10),(8,10)")
            db.execute("PRAGMA user_version=4")
        data = dbfile.read_bytes()
        commands = []
        def command(args):
            commands.append(args)
            need(args[:4] == ["exec-out", "run-as", PACKAGE, "cat"], "collection exact adb argv")
            values = {"databases/schema4-startup-ui.db": data,
                      "files/startup-ui-expected.bin": oracle}
            return values[args[4]]
        receipt = {}
        for phase in ("seed", "reopen"):
            target=root/phase;target.mkdir()
            collect_native_ui(command, ["schema4-startup-ui.db"], target, receipt, phase)
        need(len(commands) == 4, "native exact collection population")
        validate_native_ui_receipt(receipt)
        need(all(replay_native_ui(root, receipt, phase) for phase in ("seed","reopen")),
             "native both independent replays")
        need(dbfile.read_bytes() == data, "native fixture remained unchanged")
        negative=0
        def reject(action, reason):
            nonlocal negative
            try:
                action()
            except AssertionError as exc:
                need(str(exc) == reason, "native replay precise witness: "+str(exc))
                negative+=1
            else:
                raise AssertionError("native replay negative survived "+reason)
        reject(lambda: validate_native_ui_receipt({}), "native UI both phases collected")
        for phase in ("seed","reopen"):
            bad=copy.deepcopy(receipt);del bad["native_ui_snapshots"][phase]
            reject(lambda: validate_native_ui_receipt(bad), "native UI both phases collected")
        bad=copy.deepcopy(receipt);del bad["native_ui_snapshots"]["seed"]["files"]["startup-ui-expected.bin"]
        reject(lambda: validate_native_ui_receipt(bad), "native UI exact evidence files")
        bad=copy.deepcopy(receipt)
        bad["native_ui_snapshots"]["seed"]["files"]["schema4-startup-ui.db"]["bytes"]=0
        reject(lambda: validate_native_ui_receipt(bad), "native UI file identity shape")
        reject(lambda: collect_native_ui(command, [], root/"seed", {}, "seed"),
               "native UI fixture absent")
        for filename in ("schema4-startup-ui.db","startup-ui-expected.bin"):
            target=root/"seed"/filename
            original=target.read_bytes();target.write_bytes(original+b"x")
            reject(lambda: replay_native_ui(root,receipt,"seed"),
                   "native UI report file identity differs")
            target.write_bytes(original)
        # Spoofing a device snapshot or refreshing its digest must not bypass
        # actual independent SQLite content checks.
        with sqlite3.connect(root/"seed/schema4-startup-ui.db") as db:
            db.execute("UPDATE todos SET label='tampered'")
        bad=copy.deepcopy(receipt)
        bad["native_ui_snapshots"]["seed"]["files"]["schema4-startup-ui.db"] = \
            native_file_identity((root/"seed/schema4-startup-ui.db").read_bytes())
        reject(lambda: replay_native_ui(root,bad,"seed"), "native all old typed cells and rowids")
        (root/"seed/schema4-startup-ui.db").write_bytes(data)
        bad=copy.deepcopy(receipt)
        for phase in ("seed","reopen"):
            bad["native_ui_snapshots"][phase]["snapshot"]["old_cells"]["todos"]["rows"][0][3][1]="false claim"
        reject(lambda: replay_native_ui(root,bad,"seed"), "native UI independent replay differs")
        wal=root/"seed/schema4-startup-ui.db-wal";wal.write_bytes(b"unrecorded")
        reject(lambda: replay_native_ui(root,receipt,"seed"), "native UI unrecorded WAL")
        wal.unlink()
        absent=root/"seed/startup-ui-expected.bin"
        original=absent.read_bytes();absent.unlink()
        reject(lambda: replay_native_ui(root,receipt,"seed"), "native evidence regular file")
        need(not absent.exists(), "missing evidence read must not create")
        absent.write_bytes(original)
        # A WAL-only committed change is invisible in main-only copy but must
        # be rejected when the adjacent WAL is present.
        live=sqlite3.connect(dbfile)
        try:
            need(live.execute("PRAGMA journal_mode=WAL").fetchone()==("wal",), "WAL mode witness")
            live.execute("PRAGMA wal_autocheckpoint=0")
            live.execute("UPDATE todos SET label='committed WAL mutation'")
            live.commit()
            main=root/"main-only.db";shutil.copyfile(dbfile,main)
            _native_reader_scope["native_snapshot"](main,oracle)
            pair=root/"paired.db";shutil.copyfile(dbfile,pair)
            pairwal=pathlib.Path(str(pair)+"-wal")
            shutil.copyfile(str(dbfile)+"-wal",pairwal)
            frozen=(pair.read_bytes(),pairwal.read_bytes())
            reject(lambda: _native_reader_scope["native_snapshot"](pair,oracle),
                   "native all old typed cells and rowids")
            need((pair.read_bytes(),pairwal.read_bytes())==frozen, "WAL and DB unchanged after read")
        finally:
            live.close()
        need(negative==13, "native replay exact negative population")
    print("NATIVE_UI_INDEPENDENT_REPLAY collection=2 report_replay=2 Java_oracle=1 witnessed_negative=13 WAL_only_mutation=1 PASS_NOT_ANDROID")


"""Keep legacy scripted-I/O fixtures isolated; real report entry tested below."""
def legacy_native_report_double(folder, receipt, phase):
    # Deliberately a scoped scripted-I/O double for OLD report fixtures only.
    # Never installed in production globals and not claimed as DB acceptance.
    need(phase in ("seed", "reopen") and receipt["api"] in (26, 34),
         "legacy native report double inputs")
    return True


def native_report_entry_selftest():
    import ast, contextlib, copy, inspect, io, json, os, pathlib
    import sqlite3, subprocess, sys, tempfile, types
    from unittest.mock import patch
    target = report
    with tempfile.TemporaryDirectory() as temporary:
        base = pathlib.Path(temporary)
        (base/"Oracle.java").write_text(NATIVE_ORACLE_JAVA)
        compiled = subprocess.run(
            ["java", "-m", "jdk.compiler/com.sun.tools.javac.Main", "-d", temporary,
             str(base/"Oracle.java")], capture_output=True, timeout=30)
        need(compiled.returncode == 0, "report Java oracle compile")
        encoded = subprocess.run(["java", "-cp", temporary, "Oracle", str(base/"oracle.bin")],
                                 capture_output=True, timeout=10)
        need(encoded.returncode == 0, "report Java oracle execution")
        oracle = (base/"oracle.bin").read_bytes()
        with sqlite3.connect(base/"fixture.db") as db:
            for table in _native_reader_scope["OLD_TABLES"]:
                db.execute("CREATE TABLE "+table+"(empty,num INTEGER,label TEXT,payload BLOB)")
                db.execute("INSERT INTO "+table+"(rowid,empty,num,label,payload) VALUES(7,NULL,?,?,?)",
                           (-9007199254740993, "中文😀", b"\0\1\xff"))
            db.execute("CREATE TABLE category_shortcuts(category_id INTEGER,application_id INTEGER)")
            db.execute("INSERT INTO category_shortcuts VALUES(7,10),(8,10)")
            db.execute("PRAGMA user_version=4")
        database = (base/"fixture.db").read_bytes()
        def run_case(case, entry):
            with tempfile.TemporaryDirectory() as temp:
                root=pathlib.Path(temp)
                sample, expected, sources = receipt_fixture()
                for api in (26,34):
                    local,_,_=receipt_fixture(api)
                    place=root/f"collected-shortcuts/shortcut-device-api-{api}/shortcut-device"
                    place.mkdir(parents=True)
                    def command(args):
                        need(args[:4] == ["exec-out","run-as",PACKAGE,"cat"], "report fixture collection argv")
                        return {"databases/schema4-startup-ui.db":database,
                                "files/startup-ui-expected.bin":oracle}[args[4]]
                    for phase in ("seed","reopen"):
                        stage=place/phase;stage.mkdir()
                        collect_native_ui(command,["schema4-startup-ui.db"],stage,local,phase)
                        (place/(phase+".log")).write_bytes(fixture(phase,api))
                    if api==26:
                        if case=="missing_database":
                            (place/"seed/schema4-startup-ui.db").unlink()
                        elif case=="wrong_hash":
                            local["native_ui_snapshots"]["seed"]["files"]["schema4-startup-ui.db"]["sha256"]="0"*64
                        elif case=="wrong_cells":
                            path=place/"seed/schema4-startup-ui.db"
                            with sqlite3.connect(path) as db:db.execute("UPDATE todos SET label='changed'")
                            local["native_ui_snapshots"]["seed"]["files"]["schema4-startup-ui.db"]=native_file_identity(path.read_bytes())
                        elif case=="missing_receipt":
                            del local["native_ui_snapshots"]
                        elif case=="missing_reopen":
                            del local["native_ui_snapshots"]["reopen"]
                        elif case=="forged_snapshot":
                            for phase in ("seed","reopen"):
                                local["native_ui_snapshots"][phase]["snapshot"]["old_cells"]["todos"]["rows"][0][3][1]="forged"
                    if api==34 and case=="missing_oracle34":
                        (place/"reopen/startup-ui-expected.bin").unlink()
                    (place/"result.json").write_text(json.dumps(local))
                    built=dict(status="PASS",restored=True,source_files=sources,**expected,
                               product=dict(bytes=1,sha256="b"*64,certificate="c"*64),
                               test=dict(bytes=1,sha256="b"*64,certificate="c"*64))
                    (place.parent/"shortcut-build.json").write_text(json.dumps(built))
                sent=[];observed=[]
                class Publisher:
                    @staticmethod
                    def publish(api,path,raw):
                        sent.append(json.loads(raw))
                        if case=="publish_failure":raise OSError("original publisher failure")
                        return {"html_url":"https://example.invalid/evidence"}
                def replay(folder, receipt, phase):
                    observed.append((receipt["api"],phase))
                    return replay_native_ui(folder,receipt,phase)
                # Existing database families have their own legacy tests.
                # Only their reads are scripted here; native SQLite is REAL.
                scope=dict(globals(), ROOT=root, source_identity=lambda:sources,
                    database_snapshot=lambda path:copy.deepcopy(sample["snapshots"]["seed"]),
                    replay_shortcut_databases=lambda folder,receipt,phase:None,
                    replay_activation_ui=legacy_activation_report_double,
                    replay_native_ui=replay)
                runner=types.FunctionType(entry.__code__,scope)
                env=dict(GITHUB_SHA=expected["commit"],GITHUB_RUN_ID="1",GITHUB_RUN_ATTEMPT="1",
                    NEEDS_JSON=json.dumps({k:{"result":"success"} for k in ("shortcut_host","shortcut_device")}))
                error=None
                with patch.dict(os.environ,env),patch.dict(sys.modules,{"verify_evidence":Publisher}),contextlib.redirect_stdout(io.StringIO()):
                    try:runner()
                    except Exception as exc:error=exc
                need(len(sent)==1, "native report publishes original outcome")
                return sent[0],error,observed
        good,error,observed=run_case("valid",target)
        need(error is None and good["status"]=="PASS" and observed==[(26,"seed"),(26,"reopen"),(34,"seed"),(34,"reopen")],
             "native actual report positive and four reads")
        reasons={
            "missing_database":"native evidence regular file",
            "missing_oracle34":"native evidence regular file",
            "wrong_hash":"native UI report file identity differs",
            "wrong_cells":"native all old typed cells and rowids",
            "missing_receipt":"native UI both phases collected",
            "missing_reopen":"native UI both phases collected",
            "forged_snapshot":"native UI independent replay differs"}
        for case,reason in reasons.items():
            value,error,observed=run_case(case,target)
            api="34" if case=="missing_oracle34" else "26"
            need(type(error) is AssertionError and value["status"]=="FAIL" and
                 value["device_validation_errors"].get(api)=="AssertionError("+repr(reason)+")",
                 "native actual report precise rejection "+case)
            need(set(value["devices"])=={"26","34"} and
                 (api=="34" or (34,"reopen") in observed), "native first API cannot hide second")
        value,error,observed=run_case("publish_failure",target)
        need(type(error) is OSError and str(error)=="original publisher failure",
             "native report preserves publisher failure")
        tree=ast.parse(inspect.getsource(target))
        removed=[]
        class Omit(ast.NodeTransformer):
            def visit_Expr(self,node):
                if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=="replay_native_ui":
                    removed.append(node);return None
                return self.generic_visit(node)
        tree=Omit().visit(tree);need(len(removed)==1,"actual report replay omission applied")
        scope=dict(globals());exec(compile(ast.fix_missing_locations(tree),"<actual-report-omit>","exec"),scope)
        mutant=scope["report"]
        value,error,_=run_case("valid",mutant)
        need(error is None and value["status"]=="PASS", "report omission positive witness")
        value,error,observed=run_case("missing_database",mutant)
        need(error is None and value["status"]=="PASS" and observed==[],
             "report omission must demonstrate false acceptance")
        print("NATIVE_ACTUAL_REPORT real_SQLite positive=1 precise_negative=7 publisher_failure=1 whole_replay_omission_witness=1 PASS_NOT_GITHUB_NOT_ANDROID")


"""Append exact native collection/replay hooks without replacing older gates."""
import ast

def wire_native_replay(source):
    tree=ast.parse(source);patches=[]
    for function, anchor, addition in (
        ("android","collect_activation_ui","collect_native_ui(command, names, folder, receipt, phase)"),
        ("android","validate_activation_ui_receipt","validate_native_ui_receipt(receipt)"),
        ("report","replay_activation_ui","replay_native_ui(folder, receipt, phase)"),
    ):
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==function]
        assert len(functions)==1
        calls=[n for n in ast.walk(functions[0]) if isinstance(n,ast.Expr) and
               isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and
               n.value.func.id==anchor]
        assert len(calls)==1
        n=calls[0];patches.append((n.end_lineno," "*n.col_offset+addition+"\n"))
    # Isolate only older report fixtures, never the production namespace.
    for function in ("report_selftest","activation_report_entry_selftest"):
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==function]
        assert len(functions)==1
        runners=[n for n in ast.walk(functions[0]) if isinstance(n,ast.Assign) and
                 any(isinstance(t,ast.Name) and t.id=="runner" for t in n.targets)]
        assert len(runners)==1
        n=runners[0]
        patches.append((n.lineno-1," "*n.col_offset+
                        'scope["replay_native_ui"]=legacy_native_report_double\n'))
    lines=source.splitlines(keepends=True)
    for at,content in sorted(patches,reverse=True):lines.insert(at,content)
    result="".join(lines);restored=result.splitlines(keepends=True)
    for offset,(at,content) in reversed(list(enumerate(sorted(patches)))):
        assert restored[at+offset]==content
        del restored[at+offset]
    assert "".join(restored)==source
    ast.parse(result)
    return result


def native_wiring_gate(source):
    tree=ast.parse(source)
    for function,target,prior in (
        ("android","collect_native_ui","collect_activation_ui"),
        ("android","validate_native_ui_receipt","validate_activation_ui_receipt"),
        ("report","replay_native_ui","replay_activation_ui"),
    ):
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==function]
        assert len(functions)==1,"native entrypoint "+function
        pairs=[]
        for n in ast.walk(functions[0]):
            for field in ("body","orelse","finalbody"):
                body=getattr(n,field,None)
                if not isinstance(body,list):continue
                for i,s in enumerate(body):
                    if isinstance(s,ast.Expr) and isinstance(s.value,ast.Call) and isinstance(s.value.func,ast.Name) and s.value.func.id==target:
                        pairs.append((n,body,i))
        assert len(pairs)==1,"native actual hook "+target
        owner,body,i=pairs[0]
        assert i>0 and isinstance(body[i-1],ast.Expr) and isinstance(body[i-1].value,ast.Call) and ast.unparse(body[i-1].value.func)==prior,"native predecessor "+target
        if target=="collect_native_ui":
            assert isinstance(owner,ast.For) and ast.literal_eval(owner.iter)==("seed","reopen"),"native both-phase collection"
        expected=(["command","names","folder","receipt","phase"] if target=="collect_native_ui"
                  else ["receipt"] if target=="validate_native_ui_receipt" else ["folder","receipt","phase"])
        assert [ast.unparse(a) for a in body[i].value.args]==expected,"native arguments "+target


def native_wiring_selftest(source):
    native_wiring_gate(source)
    for target in ("collect_native_ui","validate_native_ui_receipt","replay_native_ui"):
        tree=ast.parse(source);matches=[]
        fn="report" if target=="replay_native_ui" else "android"
        for n in tree.body:
            if isinstance(n,ast.FunctionDef) and n.name==fn:
                matches += [c for c in ast.walk(n) if isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id==target]
        assert len(matches)==1
        matches[0].func.id="omitted_"+target
        try:native_wiring_gate(ast.unparse(tree))
        except AssertionError as exc:assert str(exc)=="native actual hook "+target
        else:raise AssertionError("native hook omission survived")
    print("NATIVE_ACTUAL_WIRING positive=1 whole_hook_omissions=3 PASS")
def native_snapshot_selftest():
    import ast,hashlib,pathlib,shutil,sqlite3,subprocess,tempfile
    old=_activation_reader_scope
    native=_native_reader_scope
    snapshot=native["native_startup_snapshot"]
    java=NATIVE_ORACLE_JAVA
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        src = root/"Oracle.java"
        src.write_text(java)
        subprocess.run(["java", "-m", "jdk.compiler/com.sun.tools.javac.Main",
                        "-d", tmp, str(src)], capture_output=True, check=True, timeout=30)
        subprocess.run(["java", "-cp", tmp, "Oracle", str(root/"expected.bin")],
                       capture_output=True, check=True, timeout=10)
        expected = (root/"expected.bin").read_bytes()
        baseline = root/"baseline.db"
        with sqlite3.connect(baseline) as db:
            for table in old["OLD_TABLES"]:
                db.execute("CREATE TABLE "+table+"(empty,num INTEGER,label TEXT,payload BLOB)")
                db.execute("INSERT INTO "+table+"(rowid,empty,num,label,payload) VALUES(7,NULL,?,?,?)",
                           (-9007199254740993, "中文😀", b"\0\1\xff"))
            db.execute("CREATE TABLE category_shortcuts(category_id INTEGER,application_id INTEGER)")
            db.executemany("INSERT INTO category_shortcuts VALUES(?,?)", [(7, 10), (8, 10)])
            db.execute("PRAGMA user_version=4")
        before = digest(baseline)
        value = snapshot(baseline, expected, old)
        assert value["category_shortcuts"] == [[7, 10], [8, 10]]
        assert digest(baseline) == before
        negatives = 0
        for sql, reason in [
            ("PRAGMA user_version=3", "native schema4"),
            ("CREATE TABLE unknown(x)", "native exact table set"),
            ("DROP TABLE notes", "native exact table set"),
            ("UPDATE todos SET label='changed'", "native all old typed cells and rowids"),
            ("UPDATE todos SET rowid=8", "native all old typed cells and rowids"),
            ("UPDATE revision SET num=-9007199254740992", "native all old typed cells and rowids"),
            ("UPDATE blocks SET payload=X'0001FE'", "native all old typed cells and rowids"),
            ("UPDATE notes SET empty=''", "native all old typed cells and rowids"),
            ("DELETE FROM fields", "native all old typed cells and rowids"),
            ("DELETE FROM category_shortcuts WHERE category_id=8", "native exact typed shortcut relations"),
            ("UPDATE category_shortcuts SET application_id=11", "native exact typed shortcut relations"),
            ("INSERT INTO category_shortcuts VALUES(7,10)", "native exact typed shortcut relations"),
            ("ALTER TABLE category_shortcuts ADD COLUMN extra", "native shortcut columns"),
        ]:
            target = root/"mutant.db"
            shutil.copyfile(baseline, target)
            with sqlite3.connect(target) as db:
                db.execute(sql)
            try:
                snapshot(target, expected, old)
            except AssertionError as exc:
                assert str(exc) == reason, (sql, str(exc))
                negatives += 1
            else:
                raise AssertionError("database mutation survived "+sql)
        for bad, reason in [
            (expected[:-1], "native fixed bridge oracle relations"),
            (expected+b"\0", "native fixed bridge oracle relations"),
            (b"", "native oracle byte budget"),
            (expected[:-36]+b"\0"*36, "native fixed bridge oracle relations"),
            (expected[:-36]+expected[-36:-16]+expected[-32:-16], "native fixed bridge oracle relations"),
        ]:
            try:
                snapshot(baseline, bad, old)
            except AssertionError as exc:
                assert str(exc) == reason, str(exc)
                negatives += 1
            else:
                raise AssertionError("oracle mutation survived")
        absent = root/"must-not-be-created.db"
        try:
            snapshot(absent, expected, old)
        except AssertionError as exc:
            assert str(exc) == "native database file budget"
            negatives += 1
        else:
            raise AssertionError("missing database accepted")
        assert not absent.exists()
        link = root/"symlink.db"
        link.symlink_to(baseline)
        try:
            snapshot(link, expected, old)
        except AssertionError as exc:
            assert str(exc) == "native database file budget"
            negatives += 1
        else:
            raise AssertionError("symlink accepted")
        # A committed link deletion visible only through adjacent WAL must be seen.
        wal_db = root/"wal.db"
        shutil.copyfile(baseline, wal_db)
        writer = sqlite3.connect(wal_db)
        try:
            assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("DELETE FROM category_shortcuts WHERE category_id=8")
            writer.commit()
            wal = root/"wal.db-wal"
            assert wal.is_file() and wal.stat().st_size > 0
            main_only = root/"main-only.db"
            shutil.copyfile(wal_db, main_only)
            assert snapshot(main_only, expected, old) == value
            hashes = (digest(wal_db), digest(wal))
            try:
                snapshot(wal_db, expected, old)
            except AssertionError as exc:
                assert str(exc) == "native exact typed shortcut relations"
            else:
                raise AssertionError("WAL-only link deletion survived")
            assert hashes == (digest(wal_db), digest(wal))
        finally:
            writer.close()
        assert negatives == 20
        # Same checker, omission mutant. First a genuine positive witness, then a
        # changed link table is wrongly accepted only when that assertion is removed.
        source = NATIVE_READER_SOURCE
        parsed = ast.parse(source)
        matches = [n for n in ast.walk(parsed) if isinstance(n, ast.Expr) and
                   isinstance(n.value, ast.Call) and n.value.args and
                   isinstance(n.value.args[-1], ast.Constant) and
                   n.value.args[-1].value == "native exact typed shortcut relations"]
        assert len(matches) == 1
        node = matches[0]
        lines = source.splitlines(keepends=True)
        mutant = "".join(lines[:node.lineno-1]+["    pass\n"]+lines[node.end_lineno:])
        scope = {"__name__": "native_mutant"}
        exec(compile(mutant, "native-mutant", "exec"), scope)
        assert scope["native_startup_snapshot"](baseline, expected, old) == value
        target = root/"omitted-links.db"
        shutil.copyfile(baseline, target)
        with sqlite3.connect(target) as db:
            db.execute("DELETE FROM category_shortcuts WHERE category_id=8")
        accepted = scope["native_startup_snapshot"](target, expected, old)
        assert accepted["category_shortcuts"] == [[7, 10]]
        print("NATIVE_STARTUP_REPLAY real_Java_bridge=1 SQLite_positive=1 precise_negative=20 WAL_only_link_mutation=1 whole_link_assertion_omission_witness=1 PASS_LOCAL_NOT_CI_NOT_ANDROID")

_native_previous_selftest=selftest
def selftest():
    native_snapshot_selftest()
    native_replay_selftest()
    native_report_entry_selftest()
    native_wiring_selftest(pathlib.Path(__file__).read_text())
    _native_previous_selftest()

_device_thread_previous_selftest=selftest
def selftest():
    scope={}
    exec(compile('"""Actual Java AST + same-language execution. Android behavior remains a double."""\nimport pathlib\nimport subprocess\nimport tempfile\n\nAST = r\'\'\'\nimport java.nio.file.*;import java.util.*;import javax.tools.*;\nimport com.sun.source.tree.*;import com.sun.source.util.*;\npublic class ScreenReads {\n public static void main(String[] args)throws Exception{\n  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();\n  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();\n  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){\n   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,List.of("-proc:none"),null,\n      files.getJavaFileObjects(args[0]));\n   var units=task.parse();SourcePositions pos=Trees.instance(task).getSourcePositions();\n   for(CompilationUnitTree unit:units)new TreePathScanner<Void,Void>(){\n    int reads=0;\n    public Void visitMethod(MethodTree method,Void unused){\n     String name=method.getName().toString();\n     if(name.equals("captureScreenOnMain")||name.equals("closeShortcutUi"))\n      System.out.println("METHOD\\t"+name+"\\t"+pos.getStartPosition(unit,method)+"\\t"+pos.getEndPosition(unit,method));\n     return super.visitMethod(method,unused);\n    }\n    public Void visitMethodInvocation(MethodInvocationTree call,Void unused){\n     if(call.getMethodSelect() instanceof MemberSelectTree\n        &&((MemberSelectTree)call.getMethodSelect()).getIdentifier().contentEquals("shortcutTestScreen")){\n      reads++;boolean main=false;\n      for(TreePath path=getCurrentPath().getParentPath();path!=null;path=path.getParentPath()){\n       Tree node=path.getLeaf();\n       if(node instanceof MethodTree||node instanceof ClassTree)break;\n       if(node instanceof LambdaExpressionTree){\n        Tree parent=path.getParentPath().getLeaf();\n        if(parent instanceof MethodInvocationTree){\n         MethodInvocationTree invoke=(MethodInvocationTree)parent;\n         main=invoke.getMethodSelect().toString().equals("runOnMainSync")\n              &&invoke.getArguments().size()==1&&invoke.getArguments().get(0)==node;\n        }\n        break;\n       }\n      }\n      System.out.println((main?"MAIN":"OFF_MAIN")+"\\t"+pos.getStartPosition(unit,call));\n     }\n     return super.visitMethodInvocation(call,unused);\n    }\n   }.scan(unit,null);\n   for(Diagnostic<?> error:errors.getDiagnostics())if(error.getKind()==Diagnostic.Kind.ERROR)\n    throw new AssertionError(error.toString());\n  }\n }\n}\n\'\'\'\n\nHARNESS = r\'\'\'\nimport java.util.concurrent.*;\npublic class ThreadHarness {\n static Thread mainThread;\n static final ExecutorService main=Executors.newSingleThreadExecutor(r->{\n  Thread t=new Thread(r);mainThread=t;return t;\n });\n static void assertThat(boolean ok,String label){if(!ok)throw new AssertionError(label);}\n static void runOnMainSync(Runnable action){\n  try{main.submit(action).get(5,TimeUnit.SECONDS);}\n  catch(ExecutionException e){\n   if(e.getCause() instanceof Error)throw (Error)e.getCause();\n   throw new RuntimeException(e.getCause());\n  }catch(Exception e){throw new RuntimeException(e);}\n }\n static void waitForIdleSync(){runOnMainSync(()->{});}\n static class TodayScreen {\n  int closed,awaited;\n  boolean awaitShortcutClose(){\n   assertThat(Thread.currentThread()!=mainThread,"await must stay off main");\n   awaited++;return closed==1;\n  }\n }\n static class MainActivity {\n  static boolean isolatedShortcutTest;\n  TodayScreen screen=new TodayScreen();int finished,reads;\n  TodayScreen shortcutTestScreen(){\n   assertThat(Thread.currentThread()==mainThread,"screen read off main");\n   reads++;return screen;\n  }\n  void finish(){\n   assertThat(Thread.currentThread()==mainThread,"finish off main");\n   finished++;if(screen!=null)screen.closed++;screen=null;\n  }\n }\n MainActivity uiActivity;\n /* METHODS */\n public static void main(String[] ignored)throws Exception{\n  try{\n   ThreadHarness test=new ThreadHarness();MainActivity activity=new MainActivity();\n   test.uiActivity=activity;TodayScreen original=activity.screen;\n   MainActivity.isolatedShortcutTest=true;test.closeShortcutUi();\n   assertThat(activity.reads==1&&activity.finished==1&&original.awaited==1&&test.uiActivity==null\n       &&!MainActivity.isolatedShortcutTest,"capture close wait ownership");\n   test.closeShortcutUi();\n   assertThat(activity.reads==1&&activity.finished==1&&original.awaited==1,"null close exact noop");\n   MainActivity empty=new MainActivity();empty.screen=null;\n   try{test.captureScreenOnMain(empty);throw new AssertionError("missing screen accepted");}\n   catch(AssertionError error){assertThat(error.getMessage().equals("UI screen capture missing"),"wrong missing screen");}\n   System.out.println("ACTUAL_DEVICE_THREAD_MEMBERS scenarios=3 PASS_JAVA_ANDROID_DOUBLES");\n  }finally{main.shutdownNow();}\n }\n}\n\'\'\'\n\ndef inspect(source):\n    with tempfile.TemporaryDirectory() as tmp:\n        root = pathlib.Path(tmp)\n        (root/"ScreenReads.java").write_text(AST)\n        (root/"Source.java").write_text(source)\n        c = subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main",\n                            "-d",tmp,str(root/"ScreenReads.java")],\n                           capture_output=True,text=True,timeout=30)\n        assert c.returncode == 0, c.stderr\n        r = subprocess.run(["java","-cp",tmp,"ScreenReads",str(root/"Source.java")],\n                           capture_output=True,text=True,timeout=10)\n        assert r.returncode == 0, r.stderr\n        return [row.split("\\t") for row in r.stdout.splitlines()]\n\ndef validate(source):\n    rows = inspect(source)\n    reads = [row for row in rows if row[0] in ("MAIN","OFF_MAIN")]\n    assert reads, "no actual screen reads"\n    assert all(row[0]=="MAIN" for row in reads), "screen read off main"\n    members = {}\n    encoded = source.encode("utf-16-le")\n    for row in rows:\n        if row[0] == "METHOD":\n            assert row[1] not in members, "duplicate thread member"\n            members[row[1]] = encoded[int(row[2])*2:int(row[3])*2].decode("utf-16-le")\n    assert set(members)=={"captureScreenOnMain","closeShortcutUi"}, "missing actual thread members"\n    return "\\n".join(members.values())\n\ndef run(members):\n    with tempfile.TemporaryDirectory() as tmp:\n        path = pathlib.Path(tmp)/"ThreadHarness.java"\n        path.write_text(HARNESS.replace("/* METHODS */",members,1))\n        c = subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",tmp,str(path)],\n                           capture_output=True,text=True,timeout=30)\n        assert c.returncode == 0, c.stderr\n        return subprocess.run(["java","-cp",tmp,"ThreadHarness"],\n                              capture_output=True,text=True,timeout=10)\n\ndef check(source):\n    members = validate(source)\n    good = run(members)\n    assert good.returncode==0, good.stderr\n    assert "scenarios=3 PASS_JAVA_ANDROID_DOUBLES" in good.stdout\n    # Each mutant still compiles. Witness the relevant actual operation failing.\n    for before, after, reason in (\n        (\'runOnMainSync(()->captured[0]=activity.shortcutTestScreen());\',\n         \'captured[0]=activity.shortcutTestScreen();\',"screen read off main"),\n        (\'TodayScreen screen=captureScreenOnMain(old);\',\n         \'TodayScreen screen=null;\',"NullPointerException"),\n        (\'runOnMainSync(old::finish);waitForIdleSync();\',\n         \'waitForIdleSync();\',"UI close executor deadline"),\n    ):\n        assert members.count(before)==1\n        mutated = run(members.replace(before,after,1))\n        assert mutated.returncode!=0 and reason in mutated.stderr, (reason,mutated.stderr)\n    for name in ("old","retired"):\n        before="TodayScreen "+name+"=captureScreenOnMain(uiActivity);"\n        after="TodayScreen "+name+"=uiActivity.shortcutTestScreen();"\n        assert source.count(before)==1, "missing activation main capture "+name\n        try:validate(source.replace(before,after,1))\n        except AssertionError as error:assert str(error)=="screen read off main"\n        else:raise AssertionError("activation off-main regression survived")\n    print("DEVICE_THREAD_GATE actual_members=2 scenarios=3 runtime_mutants=3 caller_mutants=2 PASS_NOT_ANDROID")\n',"device-thread-gate","exec"),scope)
    scope["check"](DEVICE.read_text())
    _device_thread_previous_selftest()
ACTIVATION_LIFE_LABELS = [
    "activation_life_rotation_stale_consent_preserves_exact",
    "activation_life_recreate_stale_consent_preserves_exact",
    "activation_life_finish_stale_consent_preserves_exact",
]


def parse_activation_life(raw, phase):
    found = re.findall(r"(?:^|stream=)ACTIVATION_LIFE_PASS ([a-z0-9_]+)$",
                       raw.decode("utf-8", "strict").replace("\r\n", "\n"), re.M)
    need(found == (ACTIVATION_LIFE_LABELS if phase == "seed" else []),
         "activation lifecycle complete ordered checks")
    return found


_life_previous_fixture = fixture
def fixture(phase="seed", api=26):
    raw = _life_previous_fixture(phase, api)
    if phase == "seed":
        raw += "".join("ACTIVATION_LIFE_PASS "+x+"\n" for x in ACTIVATION_LIFE_LABELS).encode()
    return raw


# Preserve old parser/selftest contracts. The actual device/report evidence
# entry enforces this additional family and retains its complete raw stream.
_life_previous_evidence = ui_phase_evidence
def ui_phase_evidence(raw, phase, api):
    parse_activation_life(raw, phase)
    return _life_previous_evidence(raw, phase, api)


def activation_life_parser_selftest():
    positive = negative = 0
    for api in (26, 34):
        for phase in ("seed", "reopen"):
            raw = fixture(phase, api)
            ui_phase_evidence(raw, phase, api); positive += 1
            lines = [("ACTIVATION_LIFE_PASS "+x+"\n").encode() for x in ACTIVATION_LIFE_LABELS]
            bads = [raw+lines[0]]
            if phase == "seed":
                bads += [raw.replace(x, b"", 1) for x in lines]
                bads += [raw.replace(b"ACTIVATION_LIFE_PASS", b"IGNORED_LIFE_PASS"),
                         raw.replace(lines[0]+lines[1], lines[1]+lines[0], 1),
                         raw.replace(lines[0], b"ACTIVATION_LIFE_PASS wrong\n", 1)]
                # The omission mutant accepts a complete stream first, then
                # falsely accepts omission of this entire new family.
                _life_previous_evidence(raw, phase, api)
                old = _life_previous_fixture(phase, api)
                _life_previous_evidence(old, phase, api)
                bads += [old]
            for bad in bads:
                try: ui_phase_evidence(bad, phase, api)
                except AssertionError as exc:
                    need(str(exc) == "activation lifecycle complete ordered checks",
                         "activation lifecycle wrong rejection")
                    negative += 1
                else: raise AssertionError("activation lifecycle omission accepted")
    need((positive, negative) == (4, 18), "activation lifecycle parser population")
    print("ACTIVATION_LIFE_PARSER positives=4 negatives=18 WHOLE_FAMILY_OMISSION_WITNESS PASS")


def activation_life_source_selftest():
    import types
    source = DEVICE.read_text()
    grammar = LABEL_AST.replace("bridgeSeed", "activationLifecycle").replace(
        "bridgeReopen", "activationUiReopen").replace('"need"', '"activationLifeNeed"').replace(
        "bridge_[a-z0-9_]+", "activation_life_[a-z0-9_]+")
    parser = types.FunctionType(java_label_calls.__code__, dict(globals(), LABEL_AST=grammar))
    def check(rows):
        need([(x[0], x[1]) for x in rows] ==
             [("activationLifecycle", x) for x in ACTIVATION_LIFE_LABELS],
             "activation lifecycle actual Java assertions")
    rows = parser([source])[0]; check(rows)
    variants = []
    encoded = source.encode("utf-16-le")
    for row in rows:
        a = len(encoded[:row[2]*2].decode("utf-16-le"))
        b = len(encoded[:row[3]*2].decode("utf-16-le"))
        need(source[a:b].startswith("activationLifeNeed("), "lifecycle AST callsite")
        variants.append(source[:a]+source[b:])
    need(len(variants) == 3, "lifecycle source mutation population")
    for rows in parser(variants):
        try: check(rows)
        except AssertionError as exc:
            need(str(exc) == "activation lifecycle actual Java assertions",
                 "lifecycle wrong source rejection")
        else: raise AssertionError("lifecycle assertion omission survived")
    # Reuse the JDK AST visitor for the actual call from the original seed
    # method. A comment containing the call must never count as integration.
    entry = LABEL_AST.replace("bridgeSeed", "activationUiSeed").replace(
        "bridgeReopen", "activationUiReopen").replace('"need"', '"activationLifecycle"')
    begin = entry.index('         if(call.getArguments().size()!=2)')
    end = entry.index('         System.out.println', begin)
    entry = entry[:begin]+'''         if(call.getArguments().size()!=1)throw new AssertionError("LIFE_ENTRY_ARGUMENT_COUNT");
         String value="activation_life_entry";
'''+entry[end:]
    entry_parser = types.FunctionType(java_label_calls.__code__, dict(globals(), LABEL_AST=entry))
    def entry_check(text):
        rows = entry_parser([text])[0]
        need([(x[0], x[1]) for x in rows] == [("activationUiSeed", "activation_life_entry")],
             "activation lifecycle actual seed entry")
        return rows
    rows = entry_check(source)
    a = len(encoded[:rows[0][2]*2].decode("utf-16-le"))
    b = len(encoded[:rows[0][3]*2].decode("utf-16-le"))
    try: entry_check(source[:a]+"/* "+source[a:b]+" */"+source[b:])
    except AssertionError as exc:
        need(str(exc) == "activation lifecycle actual seed entry", "lifecycle entry wrong rejection")
    else: raise AssertionError("lifecycle whole entry omission survived")
    print("ACTIVATION_LIFE_JAVA_AST checks=3 omission_mutants=3 PASS_NOT_DEVICE")
    print("ACTIVATION_LIFE_SEED_WIRING whole_call_comment_mutant=1 PASS_NOT_DEVICE")


_life_previous_selftest = selftest
def selftest():
    activation_life_parser_selftest()
    activation_life_source_selftest()
    _life_previous_selftest()

"""Only host Android declarations. Never replaces real Android compilation."""
LIFE_SHAPE_BEFORE=dict(STUBS)
_life_activity_path="android/app/Activity.java"
_life_activity_members="""
public boolean isDestroyed(){return false;}
public android.content.res.Resources getResources(){return null;}
public void setRequestedOrientation(int orientation){}
public void recreate(){}
"""
_life_head,_life_tail=STUBS[_life_activity_path].rsplit("}",1)
need(not _life_tail.strip(),"lifecycle Activity declaration end")
for _method in ("isDestroyed(","getResources(","setRequestedOrientation(","recreate("):
    need(_method not in STUBS[_life_activity_path],"lifecycle duplicate Activity declaration")
STUBS[_life_activity_path]=_life_head+_life_activity_members+"}"+_life_tail
LIFE_SHAPE_NEW={
 "android/content/res/Resources.java":
 "package android.content.res;public class Resources{public Configuration getConfiguration(){return null;}}",
 "android/content/res/Configuration.java":
 "package android.content.res;public class Configuration{public int orientation;}",
 "android/content/pm/ActivityInfo.java":
 "package android.content.pm;public class ActivityInfo{public static final int SCREEN_ORIENTATION_LANDSCAPE=0,SCREEN_ORIENTATION_PORTRAIT=1;}",
}
for _path,_source in LIFE_SHAPE_NEW.items():
    need(_path not in STUBS,"lifecycle duplicate type declaration "+_path)
    STUBS[_path]=_source


def lifecycle_shape_selftest():
    import contextlib,io,types
    def compile_with(stubs):
        runner=types.FunctionType(syntax_selftest.__code__,dict(globals(),STUBS=stubs))
        with contextlib.redirect_stdout(io.StringIO()):runner()
    try:compile_with(LIFE_SHAPE_BEFORE)
    except AssertionError as exc:
        message=str(exc)
        need("new-class Java syntax failed:" in message and
             all(x in message for x in ("isDestroyed","getResources","setRequestedOrientation","recreate","android.content.pm")),
             "lifecycle shape original RED changed")
        print("LIFECYCLE_SHAPE_ORIGINAL_RED\n"+message)
    else:raise AssertionError("lifecycle original declarations unexpectedly compile")
    compile_with(STUBS)
    cases=[
      (_life_activity_path,"isDestroyed(","missingDestroyed(","isDestroyed"),
      (_life_activity_path,"getResources(","missingResources(","getResources"),
      (_life_activity_path,"setRequestedOrientation(","missingOrientation(","setRequestedOrientation"),
      (_life_activity_path,"recreate(","missingRecreate(","recreate"),
      ("android/content/res/Resources.java","getConfiguration(","missingConfiguration(","getConfiguration"),
      ("android/content/res/Configuration.java","int orientation;","int missingOrientation;","orientation"),
      ("android/content/pm/ActivityInfo.java","SCREEN_ORIENTATION_LANDSCAPE","MISSING_LANDSCAPE","SCREEN_ORIENTATION_LANDSCAPE"),
      ("android/content/pm/ActivityInfo.java","SCREEN_ORIENTATION_PORTRAIT","MISSING_PORTRAIT","SCREEN_ORIENTATION_PORTRAIT"),
    ]
    for path,old,new,witness in cases:
        mutant=dict(STUBS);need(mutant[path].count(old)==1,"lifecycle shape mutation anchor")
        mutant[path]=mutant[path].replace(old,new,1)
        try:compile_with(mutant)
        except AssertionError as exc:
            need("new-class Java syntax failed:" in str(exc) and witness in str(exc),
                 "lifecycle wrong missing declaration "+witness)
        else:raise AssertionError("lifecycle declaration omission survived "+witness)
    print("LIFECYCLE_API_SHAPE original_RED GREEN omissions=8 PASS_NOT_ANDROID")


_life_shape_previous_selftest=selftest
def selftest():
    lifecycle_shape_selftest()
    _life_shape_previous_selftest()

LIFECYCLE_EXECUTION_GATE='import pathlib\nimport subprocess\nimport tempfile\nAST = \'\\nimport java.nio.file.*;import java.util.*;import javax.tools.*;\\nimport com.sun.source.tree.*;import com.sun.source.util.*;\\npublic class ScreenReads {\\n public static void main(String[] args)throws Exception{\\n  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();\\n  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();\\n  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){\\n   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,List.of("-proc:none"),null,\\n      files.getJavaFileObjects(args[0]));\\n   var units=task.parse();SourcePositions pos=Trees.instance(task).getSourcePositions();\\n   for(CompilationUnitTree unit:units)new TreePathScanner<Void,Void>(){\\n    int reads=0;\\n    public Void visitMethod(MethodTree method,Void unused){\\n     String name=method.getName().toString();\\n     if(name.equals("activationLifeNeed")||name.equals("awaitActivationRetired")||name.equals("activationLifecycle"))\\n      System.out.println("METHOD\\\\t"+name+"\\\\t"+pos.getStartPosition(unit,method)+"\\\\t"+pos.getEndPosition(unit,method));\\n     return super.visitMethod(method,unused);\\n    }\\n    public Void visitMethodInvocation(MethodInvocationTree call,Void unused){\\n     if(call.getMethodSelect() instanceof MemberSelectTree\\n        &&((MemberSelectTree)call.getMethodSelect()).getIdentifier().contentEquals("shortcutTestScreen")){\\n      reads++;boolean main=false;\\n      for(TreePath path=getCurrentPath().getParentPath();path!=null;path=path.getParentPath()){\\n       Tree node=path.getLeaf();\\n       if(node instanceof MethodTree||node instanceof ClassTree)break;\\n       if(node instanceof LambdaExpressionTree){\\n        Tree parent=path.getParentPath().getLeaf();\\n        if(parent instanceof MethodInvocationTree){\\n         MethodInvocationTree invoke=(MethodInvocationTree)parent;\\n         main=invoke.getMethodSelect().toString().equals("runOnMainSync")\\n              &&invoke.getArguments().size()==1&&invoke.getArguments().get(0)==node;\\n        }\\n        break;\\n       }\\n      }\\n      System.out.println((main?"MAIN":"OFF_MAIN")+"\\\\t"+pos.getStartPosition(unit,call));\\n     }\\n     return super.visitMethodInvocation(call,unused);\\n    }\\n   }.scan(unit,null);\\n   for(Diagnostic<?> error:errors.getDiagnostics())if(error.getKind()==Diagnostic.Kind.ERROR)\\n    throw new AssertionError(error.toString());\\n  }\\n }\\n}\\n\'\n\ndef inspect(source):\n    with tempfile.TemporaryDirectory() as tmp:\n        root = pathlib.Path(tmp)\n        (root / \'ScreenReads.java\').write_text(AST)\n        (root / \'Source.java\').write_text(source)\n        c = subprocess.run([\'java\', \'-m\', \'jdk.compiler/com.sun.tools.javac.Main\', \'-d\', tmp, str(root / \'ScreenReads.java\')], capture_output=True, text=True, timeout=30)\n        assert c.returncode == 0, c.stderr\n        r = subprocess.run([\'java\', \'-cp\', tmp, \'ScreenReads\', str(root / \'Source.java\')], capture_output=True, text=True, timeout=10)\n        assert r.returncode == 0, r.stderr\n        return [row.split(\'\\t\') for row in r.stdout.splitlines()]\n\nrows=inspect(DEVICE_SOURCE)\nencoded=DEVICE_SOURCE.encode("utf-16-le")\nselected={}\nfor row in rows:\n    if row[0]=="METHOD":\n        assert row[1] not in selected,"duplicate lifecycle method"\n        selected[row[1]]=encoded[int(row[2])*2:int(row[3])*2].decode("utf-16-le")\nassert set(selected)=={"activationLifeNeed","awaitActivationRetired","activationLifecycle"},"missing lifecycle method"\nmembers="\\n".join(selected.values())\n\n"""Execute the actual new device members in Java with explicit Android doubles.\n\nThis proves assertion behavior and Java member type shape, not Android events.\nThe submitted CI owns actual Android compilation and lifecycle execution.\n"""\nimport pathlib,subprocess,tempfile\nHARNESS=r\'\'\'\nimport java.nio.file.*;import java.util.*;import java.util.concurrent.*;\nclass android {\n static class view {static class View {Runnable action;View(Runnable x){action=x;}boolean performClick(){action.run();return true;}}}\n static class content {static class pm {static class ActivityInfo {\n  static final int SCREEN_ORIENTATION_LANDSCAPE=0,SCREEN_ORIENTATION_PORTRAIT=1;\n }}}\n}\npublic class LifeHarness {\n static String fault;static int event,orientation=1,assertions;\n static byte[] cells={1,2,3};static Path root,backup;static MainActivity replacement;\n static class Resources {Configuration getConfiguration(){return new Configuration();}}\n static class Configuration {int orientation=LifeHarness.orientation;}\n static class Activity {}\n static class MainActivity extends Activity {\n  final ExecutorService startupIo=Executors.newSingleThreadExecutor();final TodayScreen screen=new TodayScreen();\n  boolean destroyed;\n  Resources getResources(){return new Resources();}\n  boolean isDestroyed(){return destroyed;}\n  void retire(int n)throws Exception{\n   event=n;destroyed=!fault.equals("destroyed");\n   screen.closed=!fault.equals("screen");\n   startupIo.shutdown();\n   if(fault.equals("backup-"+n))Files.write(backup,new byte[]{9});\n   if(fault.equals("cells-"+n))cells=new byte[]{9};\n  }\n  void setRequestedOrientation(int value){\n   try{\n    if(!fault.equals("orientation"))orientation=value==0?2:1;\n    retire(1);replacement=fault.equals("replacement")?this:new MainActivity();\n   }catch(Exception e){throw new RuntimeException(e);}\n  }\n  void recreate(){try{retire(2);replacement=new MainActivity();}catch(Exception e){throw new RuntimeException(e);}}\n }\n static class TodayScreen {boolean closed;boolean awaitShortcutClose(){return closed;}}\n static class ActivityMonitor {}\n MainActivity uiActivity=new MainActivity();\n static void assertThat(boolean value,String reason){assertions++;if(!value)throw new AssertionError(reason);}\n static void runOnMainSync(Runnable r){r.run();}\n static void waitForIdleSync(){}\n final StringBuilder log=new StringBuilder();\n void touchUi(String id)throws Exception{\n  backup=Files.createTempFile(root,"verified-", ".zip");Files.write(backup,new byte[]{4,5,6});\n }\n android.view.View awaitActivation(String id){\n  MainActivity owner=uiActivity;\n  return new android.view.View(()->{\n   if(!owner.destroyed||fault.equals("stale-"+event))cells=new byte[]{9};\n  });\n }\n Path activationUiBackup(){return backup;}\n void touchActivation(String id){}\n TodayScreen captureScreenOnMain(MainActivity activity){return activity.screen;}\n ActivityMonitor addMonitor(String name,Object unused,boolean block){return new ActivityMonitor();}\n Activity waitForMonitorWithTimeout(ActivityMonitor monitor,long timeout){return replacement;}\n void removeMonitor(ActivityMonitor monitor){}\n void awaitUi(String id){}\n byte[] activationUiCells(int version){return cells.clone();}\n void closeActivationUi()throws Exception{uiActivity.retire(3);uiActivity=null;}\n void launchActivationUi(){uiActivity=new MainActivity();}\n /* ACTUAL_DEVICE_MEMBERS */\n public static void main(String[] args)throws Exception{\n  fault=args[0];root=Paths.get(args[1]);LifeHarness test=new LifeHarness();\n  try{\n   test.activationLifecycle(cells.clone());\n   assertThat(test.log.toString().lines().count()==3,"life complete population");\n   System.out.print(test.log);\n   System.out.println("JAVA_LIFECYCLE_ACTUAL_MEMBERS_ASSERTIONS "+assertions);\n  }finally{\n   if(test.uiActivity!=null)test.uiActivity.startupIo.shutdownNow();\n   if(replacement!=null)replacement.startupIo.shutdownNow();\n  }\n }\n}\n\'\'\'\nlabels=[\n "activation_life_rotation_stale_consent_preserves_exact",\n "activation_life_recreate_stale_consent_preserves_exact",\n "activation_life_finish_stale_consent_preserves_exact"]\ndef check(source,mode="good"):\n    with tempfile.TemporaryDirectory() as tmp:\n        root=pathlib.Path(tmp);file=root/"LifeHarness.java"\n        file.write_text(HARNESS.replace("/* ACTUAL_DEVICE_MEMBERS */",source))\n        c=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",tmp,str(file)],\n                         capture_output=True,text=True,timeout=30)\n        assert c.returncode==0,c.stderr\n        def run(fault):\n            return subprocess.run(["java","-cp",tmp,"LifeHarness",fault,tmp],\n                                  capture_output=True,text=True,timeout=10)\n        good=run("good");assert good.returncode==0,(good.stdout,good.stderr)\n        cases=[(f"{kind}-{i}",labels[i-1]) for kind in ("cells","backup","stale") for i in (1,2,3)]\n        cases += [\n            ("orientation","activation lifecycle actual orientation changed"),\n            ("destroyed","activation lifecycle old Activity destroyed"),\n            ("screen","activation lifecycle screen executor retired"),\n            ("replacement","activation lifecycle rotation replacement")]\n        for fault,label in cases:\n            result=run(fault)\n            if result.returncode!=1 or "AssertionError: "+label not in result.stderr:\n                raise AssertionError("accepted lifecycle fault "+fault)\n        return good.stdout,len(cases)\nstdout,total=check(members)\nprint(stdout,end="")\nprint("ACTUAL_DEVICE_MEMBERS_ANDROID_DOUBLES negatives="+str(total))\n# Whole predicate omission must still pass normal input, then falsely accept\n# its intended defect in the same behavior checker.\nfor label in labels:\n    target=\'activationLifeNeed(Arrays.equals(before,activationUiCells(3))&&\'\n    prefix,labelpart=members.split(\'"\'+label+\'"\',1)\n    at=prefix.rfind(target);assert at>=0\n    tail=prefix.index(\',\\n\',at)\n    mutant=members[:at]+\'activationLifeNeed(true\'+members[tail:]\n    try:check(mutant)\n    except AssertionError as exc:\n        expected="accepted lifecycle fault cells-"+str(labels.index(label)+1)\n        assert str(exc)==expected,(expected,str(exc))\n    else:raise AssertionError("whole lifecycle predicate omission survived")\nprint("WHOLE_LIFECYCLE_PREDICATE_MUTANTS=3 GOOD_WITNESS_THEN_BAD_ACCEPTANCE PASS")\nprint("LOCAL_JAVA_EXECUTION_ONLY_NOT_ANDROID_NOT_FULL_CHECKOUT")\n'

def actual_lifecycle_execution_selftest():
    scope={"DEVICE_SOURCE":DEVICE.read_text(),"__name__":"actual_device_lifecycle_members"}
    exec(compile(LIFECYCLE_EXECUTION_GATE,"actual_device_lifecycle_members","exec"),scope)

_life_execution_previous_selftest=selftest
def selftest():
    actual_lifecycle_execution_selftest()
    _life_execution_previous_selftest()

ACTIVATION_QUEUE_LABELS = [
    "activation_queue_prepare_finish_preserves_exact",
    "activation_queue_confirm_finish_preserves_exact",
]


def parse_activation_queue(raw, phase):
    found = re.findall(r"(?:^|stream=)ACTIVATION_QUEUE_PASS ([a-z0-9_]+)$",
                       raw.decode("utf-8", "strict").replace("\r\n", "\n"), re.M)
    need(found == (ACTIVATION_QUEUE_LABELS if phase == "seed" else []),
         "activation queue complete ordered checks")
    return found


_queue_previous_fixture = fixture
def fixture(phase="seed", api=26):
    raw = _queue_previous_fixture(phase, api)
    if phase == "seed":
        raw += "".join("ACTIVATION_QUEUE_PASS "+x+"\n" for x in ACTIVATION_QUEUE_LABELS).encode()
    return raw


# Preserve old parser/selftest contracts. The actual device/report evidence
# entry enforces this additional family and retains its complete raw stream.
_queue_previous_evidence = ui_phase_evidence
def ui_phase_evidence(raw, phase, api):
    parse_activation_queue(raw, phase)
    result = _queue_previous_evidence(raw, phase, api)
    result["activation_queue_labels"] = parse_activation_queue(raw, phase)
    result["activation_life_labels"] = parse_activation_life(raw, phase)
    return result


def activation_queue_parser_selftest():
    positive = negative = 0
    for api in (26, 34):
        for phase in ("seed", "reopen"):
            raw = fixture(phase, api)
            ui_phase_evidence(raw, phase, api); positive += 1
            lines = [("ACTIVATION_QUEUE_PASS "+x+"\n").encode() for x in ACTIVATION_QUEUE_LABELS]
            bads = [raw+lines[0]]
            if phase == "seed":
                bads += [raw.replace(x, b"", 1) for x in lines]
                bads += [raw.replace(b"ACTIVATION_QUEUE_PASS", b"IGNORED_LIFE_PASS"),
                         raw.replace(lines[0]+lines[1], lines[1]+lines[0], 1),
                         raw.replace(lines[0], b"ACTIVATION_QUEUE_PASS wrong\n", 1)]
                # The omission mutant accepts a complete stream first, then
                # falsely accepts omission of this entire new family.
                _queue_previous_evidence(raw, phase, api)
                old = _queue_previous_fixture(phase, api)
                _queue_previous_evidence(old, phase, api)
                bads += [old]
            for bad in bads:
                try: ui_phase_evidence(bad, phase, api)
                except AssertionError as exc:
                    need(str(exc) == "activation queue complete ordered checks",
                         "activation queue wrong rejection")
                    negative += 1
                else: raise AssertionError("activation queue omission accepted")
    need((positive, negative) == (4, 16), "activation queue parser population")
    print("ACTIVATION_QUEUE_PARSER positives=4 negatives=16 WHOLE_FAMILY_OMISSION_WITNESS PASS")


def activation_queue_source_selftest():
    import types
    source = DEVICE.read_text()
    grammar = LABEL_AST.replace("bridgeSeed", "activationQueuedLifecycle").replace(
        "bridgeReopen", "activationUiReopen").replace('"need"', '"activationQueueNeed"').replace(
        "bridge_[a-z0-9_]+", "activation_queue_[a-z0-9_]+")
    parser = types.FunctionType(java_label_calls.__code__, dict(globals(), LABEL_AST=grammar))
    def check(rows):
        need([(x[0], x[1]) for x in rows] ==
             [("activationQueuedLifecycle", x) for x in ACTIVATION_QUEUE_LABELS],
             "activation queue actual Java assertions")
    rows = parser([source])[0]; check(rows)
    variants = []
    encoded = source.encode("utf-16-le")
    for row in rows:
        a = len(encoded[:row[2]*2].decode("utf-16-le"))
        b = len(encoded[:row[3]*2].decode("utf-16-le"))
        need(source[a:b].startswith("activationQueueNeed("), "queue AST callsite")
        variants.append(source[:a]+source[b:])
    need(len(variants) == 2, "queue source mutation population")
    for rows in parser(variants):
        try: check(rows)
        except AssertionError as exc:
            need(str(exc) == "activation queue actual Java assertions",
                 "queue wrong source rejection")
        else: raise AssertionError("queue assertion omission survived")
    # Reuse the JDK AST visitor for the actual call from the original seed
    # method. A comment containing the call must never count as integration.
    entry = LABEL_AST.replace("bridgeSeed", "activationUiSeed").replace(
        "bridgeReopen", "activationUiReopen").replace('"need"', '"activationQueuedLifecycle"')
    begin = entry.index('         if(call.getArguments().size()!=2)')
    end = entry.index('         System.out.println', begin)
    entry = entry[:begin]+'''         if(call.getArguments().size()!=1)throw new AssertionError("LIFE_ENTRY_ARGUMENT_COUNT");
         String value="activation_queue_entry";
'''+entry[end:]
    entry_parser = types.FunctionType(java_label_calls.__code__, dict(globals(), LABEL_AST=entry))
    def entry_check(text):
        rows = entry_parser([text])[0]
        need([(x[0], x[1]) for x in rows] == [("activationUiSeed", "activation_queue_entry")],
             "activation queue actual seed entry")
        return rows
    rows = entry_check(source)
    a = len(encoded[:rows[0][2]*2].decode("utf-16-le"))
    b = len(encoded[:rows[0][3]*2].decode("utf-16-le"))
    try: entry_check(source[:a]+"/* "+source[a:b]+" */"+source[b:])
    except AssertionError as exc:
        need(str(exc) == "activation queue actual seed entry", "queue entry wrong rejection")
    else: raise AssertionError("queue whole entry omission survived")
    print("ACTIVATION_QUEUE_JAVA_AST checks=2 omission_mutants=2 PASS_NOT_DEVICE")
    print("ACTIVATION_QUEUE_SEED_WIRING whole_call_comment_mutant=1 PASS_NOT_DEVICE")


_queue_previous_selftest = selftest
def selftest():
    activation_queue_parser_selftest()
    activation_queue_source_selftest()
    # Prior parser mutation tests intentionally supply old-family-only streams.
    # Scope their original entry contract here, never in device/report execution.
    global ui_phase_evidence
    current=ui_phase_evidence
    try:
        ui_phase_evidence=_queue_previous_evidence
        _queue_previous_selftest()
    finally:
        ui_phase_evidence=current

QUEUE_EXECUTION_GATE='import pathlib\nimport subprocess\nimport tempfile\nAST = \'\\nimport java.nio.file.*;import java.util.*;import javax.tools.*;\\nimport com.sun.source.tree.*;import com.sun.source.util.*;\\npublic class ScreenReads {\\n public static void main(String[] args)throws Exception{\\n  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();\\n  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();\\n  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){\\n   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,List.of("-proc:none"),null,\\n      files.getJavaFileObjects(args[0]));\\n   var units=task.parse();SourcePositions pos=Trees.instance(task).getSourcePositions();\\n   for(CompilationUnitTree unit:units)new TreePathScanner<Void,Void>(){\\n    int reads=0;\\n    public Void visitMethod(MethodTree method,Void unused){\\n     String name=method.getName().toString();\\n     if(name.equals("activationQueueNeed")||name.equals("activationQueueField")||name.equals("finishQueuedActivation")||name.equals("activationQueuedLifecycle"))\\n      System.out.println("METHOD\\\\t"+name+"\\\\t"+pos.getStartPosition(unit,method)+"\\\\t"+pos.getEndPosition(unit,method));\\n     return super.visitMethod(method,unused);\\n    }\\n    public Void visitMethodInvocation(MethodInvocationTree call,Void unused){\\n     if(call.getMethodSelect() instanceof MemberSelectTree\\n        &&((MemberSelectTree)call.getMethodSelect()).getIdentifier().contentEquals("shortcutTestScreen")){\\n      reads++;boolean main=false;\\n      for(TreePath path=getCurrentPath().getParentPath();path!=null;path=path.getParentPath()){\\n       Tree node=path.getLeaf();\\n       if(node instanceof MethodTree||node instanceof ClassTree)break;\\n       if(node instanceof LambdaExpressionTree){\\n        Tree parent=path.getParentPath().getLeaf();\\n        if(parent instanceof MethodInvocationTree){\\n         MethodInvocationTree invoke=(MethodInvocationTree)parent;\\n         main=invoke.getMethodSelect().toString().equals("runOnMainSync")\\n              &&invoke.getArguments().size()==1&&invoke.getArguments().get(0)==node;\\n        }\\n        break;\\n       }\\n      }\\n      System.out.println((main?"MAIN":"OFF_MAIN")+"\\\\t"+pos.getStartPosition(unit,call));\\n     }\\n     return super.visitMethodInvocation(call,unused);\\n    }\\n   }.scan(unit,null);\\n   for(Diagnostic<?> error:errors.getDiagnostics())if(error.getKind()==Diagnostic.Kind.ERROR)\\n    throw new AssertionError(error.toString());\\n  }\\n }\\n}\\n\'\n\ndef inspect(source):\n    with tempfile.TemporaryDirectory() as tmp:\n        root = pathlib.Path(tmp)\n        (root / \'ScreenReads.java\').write_text(AST)\n        (root / \'Source.java\').write_text(source)\n        c = subprocess.run([\'java\', \'-m\', \'jdk.compiler/com.sun.tools.javac.Main\', \'-d\', tmp, str(root / \'ScreenReads.java\')], capture_output=True, text=True, timeout=30)\n        assert c.returncode == 0, c.stderr\n        r = subprocess.run([\'java\', \'-cp\', tmp, \'ScreenReads\', str(root / \'Source.java\')], capture_output=True, text=True, timeout=10)\n        assert r.returncode == 0, r.stderr\n        return [row.split(\'\\t\') for row in r.stdout.splitlines()]\n\nrows=inspect(DEVICE_SOURCE)\nencoded=DEVICE_SOURCE.encode("utf-16-le")\nselected={}\nfor row in rows:\n    if row[0]=="METHOD":\n        assert row[1] not in selected,"duplicate queue member"\n        selected[row[1]]=encoded[int(row[2])*2:int(row[3])*2].decode("utf-16-le")\nassert set(selected)=={\'activationQueueNeed\', \'finishQueuedActivation\', \'activationQueuedLifecycle\', \'activationQueueField\'},"missing queue member"\nmembers="\\n".join(selected.values())\n\n"""Actual candidate members on a real Java executor, explicit Android/DB doubles."""\nimport pathlib,subprocess,tempfile\nHARNESS=r\'\'\'\nimport java.nio.file.*;import java.util.*;import java.util.concurrent.*;\nclass android {static class os {static class SystemClock {\n static long uptimeMillis(){return System.nanoTime()/1000000;}\n}}}\npublic class QueueHarness {\n static String fault;static String phase="prepare";static byte[] cells={1,2,3};\n static Path root,backup;static int actions;\n static class Plan {volatile boolean closed;void close(){closed=true;}}\n static class TodayScreen {\n  final ExecutorService io=Executors.newSingleThreadExecutor();\n  volatile boolean busy,closed;volatile Object activationDialog;\n  volatile Plan activationPlan,activationAttempt;\n }\n static class MainActivity {\n  final TodayScreen screen=new TodayScreen();boolean destroyed;\n  void finish(){\n   destroyed=!fault.equals("destroy");\n   screen.closed=!fault.equals("close");\n   if(screen.activationPlan!=null)screen.activationPlan.close();\n   if(screen.activationAttempt!=null)screen.activationAttempt.close();\n   screen.activationPlan=null;screen.activationAttempt=null;screen.activationDialog=null;\n   if(!fault.equals("shutdown"))screen.io.shutdown();\n  }\n  boolean isDestroyed(){return destroyed;}\n }\n MainActivity uiActivity=new MainActivity();\n final StringBuilder log=new StringBuilder();\n static void assertThat(boolean ok,String message){if(!ok)throw new AssertionError(message);}\n static void runOnMainSync(Runnable r){r.run();}\n static void waitForIdleSync(){}\n TodayScreen captureScreenOnMain(MainActivity a){return a.screen;}\n void awaitActivation(String id){}\n Path activationUiBackup(){return backup;}\n void preparePreview()throws Exception{\n  backup=Files.createTempFile(root,"backup-", ".bin");Files.write(backup,new byte[]{4,5,6});\n  uiActivity.screen.activationPlan=new Plan();uiActivity.screen.activationDialog=new Object();\n }\n void touchUi(String id)throws Exception{\n  // The second scenario\'s preview is intentionally complete before holding io.\n  if(phase.equals("confirm")){preparePreview();return;}\n  enqueue(false);\n }\n void touchActivation(String id)throws Exception{if(id.equals("activation-confirm"))enqueue(true);}\n void enqueue(boolean confirm){\n  TodayScreen s=uiActivity.screen;String event=confirm?"confirm":"prepare";\n  s.busy=!fault.equals("busy");\n  Plan plan=s.activationPlan;\n  if(confirm){s.activationAttempt=plan;s.activationPlan=null;}\n  s.io.execute(()->{\n   actions++;\n   if(confirm&&(!plan.closed||fault.equals("stale-confirm")))cells=new byte[]{9};\n   if(fault.equals("cells-"+event))cells=new byte[]{9};\n   try{if(fault.equals("backup-confirm")&&confirm)Files.write(backup,new byte[]{9});}\n   catch(Exception e){throw new RuntimeException(e);}\n   if(fault.equals("dialog-"+event))s.activationDialog=new Object();\n   if(fault.equals("plan-"+event))s.activationPlan=new Plan();\n  });\n }\n void awaitActivationRetired(MainActivity a,TodayScreen s)throws Exception{\n  assertThat(a.isDestroyed(),"owner destroyed");\n  assertThat(s.io.awaitTermination(10,TimeUnit.SECONDS),"worker terminated");\n }\n byte[] activationUiCells(int version){return cells.clone();}\n void closeActivationUi(){}\n void launchActivationUi(){uiActivity=new MainActivity();phase="confirm";}\n /* ACTUAL_QUEUE_MEMBERS */\n public static void main(String[] args)throws Exception{\n  fault=args[0];root=Paths.get(args[1]);QueueHarness h=new QueueHarness();\n  try{\n   h.activationQueuedLifecycle(cells.clone());\n   assertThat(actions==2,"both actual executor actions ran");\n   assertThat(h.log.toString().lines().count()==2,"two queue labels");\n   System.out.print(h.log);\n  }finally{if(h.uiActivity!=null)h.uiActivity.screen.io.shutdownNow();}\n }\n}\n\'\'\'\ndef check_queue_members(members):\n    with tempfile.TemporaryDirectory() as temp:\n        file=pathlib.Path(temp)/"QueueHarness.java"\n        file.write_text(HARNESS.replace("/* ACTUAL_QUEUE_MEMBERS */",members))\n        result=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",temp,str(file)],\n                              capture_output=True,text=True,timeout=30)\n        assert result.returncode==0,result.stderr\n        def run(fault):\n            return subprocess.run(["java","-cp",temp,"QueueHarness",fault,temp],\n                                  capture_output=True,text=True,timeout=15)\n        good=run("good");assert good.returncode==0,(good.stdout,good.stderr)\n        labels={x:"activation_queue_"+x+"_finish_preserves_exact" for x in ("prepare","confirm")}\n        cases=[("cells-"+x,labels[x]) for x in labels]+[\n            ("backup-confirm",labels["confirm"]),("stale-confirm",labels["confirm"]),\n            ("busy","activation queue request actually pending"),\n            ("shutdown","activation queue destruction precedes worker release"),\n            ("destroy","activation queue destruction precedes worker release"),\n            ("close","activation queue destruction precedes worker release")]\n        cases += [(kind+"-"+x,"activation queue no late dialog or owned plan") for kind in ("dialog","plan") for x in labels]\n        for fault,message in cases:\n            result=run(fault)\n            if result.returncode!=1 or "AssertionError: "+message not in result.stderr:\n                raise AssertionError("accepted queue fault "+fault)\n        return good.stdout,len(cases)\nstdout,total=check_queue_members(members)\nprint(stdout,end="")\nprint("ACTUAL_QUEUE_MEMBERS_REAL_EXECUTOR_ANDROID_DB_DOUBLES negatives="+str(total))\ntarget="return exact&&Arrays.equals(before,activationUiCells(3));"\nassert members.count(target)==1\nmutant=members.replace(target,"return true;",1)\ntry:check_queue_members(mutant)\nexcept AssertionError as e:assert str(e)=="accepted queue fault cells-prepare",str(e)\nelse:raise AssertionError("whole queue state predicate omission survived")\nprint("QUEUE_WHOLE_STATE_PREDICATE_MUTANT GOOD_THEN_BAD_ACCEPTANCE PASS_NOT_ANDROID")\n'
def actual_queue_execution_selftest():
    exec(compile(QUEUE_EXECUTION_GATE,"actual_queue_members","exec"),
         {"DEVICE_SOURCE":DEVICE.read_text(),"__name__":"actual_queue_members"})
_queue_exec_previous_selftest=selftest
def selftest():
    actual_queue_execution_selftest()
    _queue_exec_previous_selftest()

# Extend, rather than weaken, the exact report schema.
_queue_legacy_require = require_ui_evidence
_queue_report_fields = {"phase", "api", "legacy_labels", "native_startup_labels",
                        "activation_ui_labels", "raw_bytes", "raw_sha256"}
def require_ui_evidence(value, raw, phase, api):
    extra = {"activation_queue_labels", "activation_life_labels"}
    need(set(value) == _queue_report_fields | extra, "queue evidence exact fields")
    need(value["activation_queue_labels"] == parse_activation_queue(raw, phase),
         "queue evidence labels")
    need(value["activation_life_labels"] == parse_activation_life(raw, phase),
         "life evidence labels")
    _queue_legacy_require({key:value[key] for key in _queue_report_fields},raw,phase,api)

def queue_report_schema_selftest():
    import copy,json
    positive=negative=0
    checker=require_ui_evidence
    for phase in ("seed","reopen"):
        for api in (26,34):
            raw=fixture(phase,api)
            good=json.loads(json.dumps(ui_phase_evidence(raw,phase,api)))
            try:_queue_legacy_require(good,raw,phase,api)
            except AssertionError as exc:
                need(str(exc)=="UI evidence exact fields","original report schema RED")
            else:raise AssertionError("original report incompatibility not reproduced")
            checker(good,raw,phase,api);positive+=1
            bads=[]
            for key in good:
                bad=copy.deepcopy(good);del bad[key]
                bads.append((bad,"queue evidence exact fields"))
            bad=dict(good,unexpected=True);bads.append((bad,"queue evidence exact fields"))
            for key,reason in (("activation_queue_labels","queue evidence labels"),
                               ("activation_life_labels","life evidence labels")):
                bad=copy.deepcopy(good);bad[key]=["wrong"];bads.append((bad,reason))
            for key,wrong,reason in (
                ("phase","wrong","UI evidence phase identity"),
                ("api",99,"UI evidence phase identity"),
                ("legacy_labels",[],"UI evidence legacy preserved"),
                ("native_startup_labels",[],"UI evidence startup labels"),
                ("activation_ui_labels",[],"UI evidence activation labels"),
                ("raw_bytes",len(raw)+1,"UI evidence raw identity"),
                ("raw_sha256","0"*64,"UI evidence raw identity")):
                bad=copy.deepcopy(good);bad[key]=wrong;bads.append((bad,reason))
            for bad,reason in bads:
                try:checker(bad,raw,phase,api)
                except AssertionError as exc:need(str(exc)==reason,"report schema precise rejection")
                else:raise AssertionError("report schema accepted mutation")
                negative+=1
            # A whole new-field-validation omission still passes normal input,
            # but accepts corrupted new fields. The real checker above rejects.
            def omit_new_fields(value):
                _queue_legacy_require({k:value[k] for k in _queue_report_fields},raw,phase,api)
            omit_new_fields(good)
            for key in ("activation_queue_labels","activation_life_labels"):
                bad=copy.deepcopy(good);bad[key]=["wrong"];omit_new_fields(bad)
    need((positive,negative)==(4,76),"queue report schema test population")
    print("QUEUE_REPORT_SCHEMA original_RED positives=4 negatives=76 two_new_field_omission_witnesses PASS")

_queue_report_previous_selftest=selftest
def selftest():
    queue_report_schema_selftest()
    # Old tests deliberately invoke the old evidence producer. Pair its
    # original exact checker only within that pre-existing selftest scope.
    global require_ui_evidence
    current=require_ui_evidence
    try:
        require_ui_evidence=_queue_legacy_require
        _queue_report_previous_selftest()
    finally:
        require_ui_evidence=current

CALLBACK_LABEL="prepare_complete_finish_before_delivery_exact"
def parse_activation_callback(raw,phase):
    labels=re.findall(r"(?:^|stream=)ACTIVATION_CALLBACK_PASS ([a-z0-9_]+)$",
                      raw.decode("utf-8","strict").replace("\r\n","\n"),re.M)
    need(labels==([CALLBACK_LABEL] if phase=="seed" else []),"callback complete ordered checks")
    return labels

_callback_fixture=fixture
def fixture(phase="seed",api=26):
    raw=_callback_fixture(phase,api)
    return raw+(("ACTIVATION_CALLBACK_PASS "+CALLBACK_LABEL+"\n").encode() if phase=="seed" else b"")

_callback_producer=ui_phase_evidence
_callback_consumer=require_ui_evidence
def ui_phase_evidence(raw,phase,api):
    parse_activation_callback(raw,phase)
    return _callback_producer(raw,phase,api)
def require_ui_evidence(value,raw,phase,api):
    parse_activation_callback(raw,phase)
    _callback_consumer(value,raw,phase,api)

def callback_parser_selftest():
    import json
    positive=negative=0
    for phase in ("seed","reopen"):
        for api in (26,34):
            raw=fixture(phase,api);value=json.loads(json.dumps(ui_phase_evidence(raw,phase,api)))
            require_ui_evidence(value,raw,phase,api);positive+=1
            line=("ACTIVATION_CALLBACK_PASS "+CALLBACK_LABEL+"\n").encode()
            bads=[raw+line,raw+b"ACTIVATION_CALLBACK_PASS wrong\n"]
            if phase=="seed":bads.append(raw.replace(line,b"",1))
            for bad in bads:
                for check in (lambda:ui_phase_evidence(bad,phase,api),
                              lambda:require_ui_evidence(value,bad,phase,api)):
                    try:check()
                    except AssertionError as exc:need(str(exc)=="callback complete ordered checks","callback wrong rejection")
                    else:raise AssertionError("callback evidence omission survived")
                    negative+=1
            # Whole callback-validation omission: old pair accepts good input
            # and a stream without the callback family. Actual entries reject.
            _callback_consumer(_callback_producer(raw,phase,api),raw,phase,api)
            if phase=="seed":
                bad=raw.replace(line,b"",1)
                _callback_consumer(_callback_producer(bad,phase,api),bad,phase,api)
    need((positive,negative)==(4,20),"callback parser population")
    print("CALLBACK_PRODUCER_CONSUMER positives=4 negatives=20 omission_witness PASS")

def callback_source_selftest():
    import types
    source=DEVICE.read_text()
    entry=LABEL_AST.replace("bridgeSeed","activationUiSeed").replace(
        "bridgeReopen","activationUiReopen").replace('"need"','"activationCallbackLifecycle"')
    begin=entry.index('         if(call.getArguments().size()!=2)')
    end=entry.index('         System.out.println',begin)
    entry=entry[:begin]+'''         if(call.getArguments().size()!=1)throw new AssertionError("CALLBACK_ARGUMENTS");
         String value="callback_entry";
'''+entry[end:]
    parser=types.FunctionType(java_label_calls.__code__,dict(globals(),LABEL_AST=entry))
    def check(text):
        rows=parser([text])[0]
        need([(x[0],x[1]) for x in rows]==[("activationUiSeed","callback_entry")],"callback actual seed entry")
        return rows
    rows=check(source);encoded=source.encode("utf-16-le")
    a=len(encoded[:rows[0][2]*2].decode("utf-16-le"))
    b=len(encoded[:rows[0][3]*2].decode("utf-16-le"))
    try:check(source[:a]+"/* "+source[a:b]+" */"+source[b:])
    except AssertionError as exc:need(str(exc)=="callback actual seed entry","callback source wrong rejection")
    else:raise AssertionError("callback call comment survived")
    print("CALLBACK_JAVA_AST actual_seed_call whole_call_comment_mutant PASS_NOT_ANDROID")

_callback_selftest=selftest
def selftest():
    callback_parser_selftest()
    callback_source_selftest()
    global ui_phase_evidence,require_ui_evidence,fixture
    old=(ui_phase_evidence,require_ui_evidence,fixture)
    try:
        ui_phase_evidence=_callback_producer;require_ui_evidence=_callback_consumer;fixture=_callback_fixture
        _callback_selftest()
    finally:
        ui_phase_evidence,require_ui_evidence,fixture=old

CALLBACK_EXECUTION_GATE='import pathlib\nimport subprocess\nimport tempfile\nAST = \'\\nimport java.nio.file.*;import java.util.*;import javax.tools.*;\\nimport com.sun.source.tree.*;import com.sun.source.util.*;\\npublic class ScreenReads {\\n public static void main(String[] args)throws Exception{\\n  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();\\n  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();\\n  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){\\n   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,List.of("-proc:none"),null,\\n      files.getJavaFileObjects(args[0]));\\n   var units=task.parse();SourcePositions pos=Trees.instance(task).getSourcePositions();\\n   for(CompilationUnitTree unit:units)new TreePathScanner<Void,Void>(){\\n    int reads=0;\\n    public Void visitMethod(MethodTree method,Void unused){\\n     String name=method.getName().toString();\\n     if(name.equals("activationCallbackLifecycle"))\\n      System.out.println("METHOD\\\\t"+name+"\\\\t"+pos.getStartPosition(unit,method)+"\\\\t"+pos.getEndPosition(unit,method));\\n     return super.visitMethod(method,unused);\\n    }\\n    public Void visitMethodInvocation(MethodInvocationTree call,Void unused){\\n     if(call.getMethodSelect() instanceof MemberSelectTree\\n        &&((MemberSelectTree)call.getMethodSelect()).getIdentifier().contentEquals("shortcutTestScreen")){\\n      reads++;boolean main=false;\\n      for(TreePath path=getCurrentPath().getParentPath();path!=null;path=path.getParentPath()){\\n       Tree node=path.getLeaf();\\n       if(node instanceof MethodTree||node instanceof ClassTree)break;\\n       if(node instanceof LambdaExpressionTree){\\n        Tree parent=path.getParentPath().getLeaf();\\n        if(parent instanceof MethodInvocationTree){\\n         MethodInvocationTree invoke=(MethodInvocationTree)parent;\\n         main=invoke.getMethodSelect().toString().equals("runOnMainSync")\\n              &&invoke.getArguments().size()==1&&invoke.getArguments().get(0)==node;\\n        }\\n        break;\\n       }\\n      }\\n      System.out.println((main?"MAIN":"OFF_MAIN")+"\\\\t"+pos.getStartPosition(unit,call));\\n     }\\n     return super.visitMethodInvocation(call,unused);\\n    }\\n   }.scan(unit,null);\\n   for(Diagnostic<?> error:errors.getDiagnostics())if(error.getKind()==Diagnostic.Kind.ERROR)\\n    throw new AssertionError(error.toString());\\n  }\\n }\\n}\\n\'\n\ndef inspect(source):\n    with tempfile.TemporaryDirectory() as tmp:\n        root = pathlib.Path(tmp)\n        (root / \'ScreenReads.java\').write_text(AST)\n        (root / \'Source.java\').write_text(source)\n        c = subprocess.run([\'java\', \'-m\', \'jdk.compiler/com.sun.tools.javac.Main\', \'-d\', tmp, str(root / \'ScreenReads.java\')], capture_output=True, text=True, timeout=30)\n        assert c.returncode == 0, c.stderr\n        r = subprocess.run([\'java\', \'-cp\', tmp, \'ScreenReads\', str(root / \'Source.java\')], capture_output=True, text=True, timeout=10)\n        assert r.returncode == 0, r.stderr\n        return [row.split(\'\\t\') for row in r.stdout.splitlines()]\n\nrows=[r for r in inspect(DEVICE_SOURCE) if r[0]=="METHOD"]\nassert len(rows)==1 and rows[0][1]=="activationCallbackLifecycle","actual callback member"\nencoded=DEVICE_SOURCE.encode("utf-16-le")\nmembers=encoded[int(rows[0][2])*2:int(rows[0][3])*2].decode("utf-16-le")\n\nimport pathlib,subprocess,tempfile\nHARNESS=r\'\'\'\nimport java.nio.file.*;import java.util.*;import java.util.concurrent.*;\npublic class CallbackHarness {\n static String fault;static Path root,backup;static byte[] cells={1,2,3};\n static final Queue<Runnable> callbacks=new ConcurrentLinkedQueue<>();\n static class TodayScreen {\n  final ExecutorService io=Executors.newSingleThreadExecutor();\n  boolean busy;Object activationPlan,activationDialog,activationAttempt;\n  private void requestShortcutActivation(){\n   busy=!fault.equals("busy");\n   io.execute(()->{\n    try{\n     if(fault.equals("no-backup"))return;\n     Files.createDirectories(root.resolve("activation-backups"));\n     backup=Files.createTempFile(root.resolve("activation-backups"),"prepared-", ".zip");\n     try(java.util.zip.ZipOutputStream zip=new java.util.zip.ZipOutputStream(Files.newOutputStream(backup))){\n      zip.putNextEntry(new java.util.zip.ZipEntry("data"));zip.write(new byte[]{1,2,3});zip.closeEntry();\n     }\n     if(fault.equals("bad-zip"))Files.write(backup,new byte[]{9});\n     if(fault.equals("early"))activationPlan=new Object();\n     callbacks.add(()->{if(fault.equals("late-ui"))activationDialog=new Object();});\n    }catch(Exception error){throw new RuntimeException(error);}\n   });\n  }\n }\n static class MainActivity{\n  final TodayScreen screen=new TodayScreen();boolean finishing;\n  void finish(){finishing=!fault.equals("finish");}\n  boolean isFinishing(){return finishing;}\n }\n MainActivity uiActivity=new MainActivity();final StringBuilder log=new StringBuilder();\n static void assertThat(boolean ok,String label){if(!ok)throw new AssertionError(label);}\n Path root(){return root;}\n void runOnMainSync(Runnable action){action.run();Runnable callback;while((callback=callbacks.poll())!=null)callback.run();}\n void waitForIdleSync(){}\n TodayScreen captureScreenOnMain(MainActivity old){return old.screen;}\n Object activationQueueField(TodayScreen screen,String name)throws Exception{\n  var field=TodayScreen.class.getDeclaredField(name);field.setAccessible(true);return field.get(screen);\n }\n void awaitActivationRetired(MainActivity old,TodayScreen screen)throws Exception{\n  screen.io.shutdown();assertThat(screen.io.awaitTermination(10,TimeUnit.SECONDS),"executor retired");\n  if(fault.equals("cells"))cells=new byte[]{9};\n  if(fault.equals("backup"))Files.write(backup,new byte[]{9});\n }\n byte[] activationUiCells(int version){return cells.clone();}\n void closeActivationUi(){}\n void launchActivationUi(){uiActivity=new MainActivity();if(fault.equals("relaunch"))cells=new byte[]{9};}\n /* ACTUAL_CALLBACK_MEMBER */\n public static void main(String[] args)throws Exception{\n  fault=args[0];root=Paths.get(args[1]);CallbackHarness h=new CallbackHarness();\n  MainActivity original=h.uiActivity;\n  try{\n   h.activationCallbackLifecycle(cells.clone());\n   assertThat(h.log.toString().equals("ACTIVATION_CALLBACK_PASS prepare_complete_finish_before_delivery_exact\\n"),"exact callback log");\n   System.out.print(h.log);\n  }finally{\n   original.screen.io.shutdownNow();\n   if(h.uiActivity!=null)h.uiActivity.screen.io.shutdownNow();\n  }\n }\n}\n\'\'\'\ndef check_callback_member(member):\n    with tempfile.TemporaryDirectory() as temp:\n        file=pathlib.Path(temp)/"CallbackHarness.java"\n        file.write_text(HARNESS.replace("/* ACTUAL_CALLBACK_MEMBER */",member))\n        compiled=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",temp,str(file)],\n                                capture_output=True,text=True,timeout=30)\n        assert compiled.returncode==0,compiled.stderr\n        def run(fault):\n            with tempfile.TemporaryDirectory() as data:\n                return subprocess.run(["java","-cp",temp,"CallbackHarness",fault,data],\n                                      capture_output=True,text=True,timeout=15)\n        good=run("good");assert good.returncode==0,(good.stdout,good.stderr)\n        cases=[\n          ("busy","activation callback worker done before UI dispatch"),\n          ("early","activation callback worker done before UI dispatch"),\n          ("no-backup","activation callback setup"),\n          ("bad-zip","activation callback setup"),\n          ("finish","activation callback finish precedes delivery"),\n          ("late-ui","activation callback no late owned UI"),\n          ("cells","activation callback exact cells and retained backup"),\n          ("backup","activation callback exact cells and retained backup"),\n          ("relaunch","activation callback relaunch exact history")]\n        for fault,message in cases:\n            result=run(fault)\n            reason=message in result.stderr or (fault=="cells" and "activation callback relaunch exact history" in result.stderr)\n            if result.returncode!=1 or not reason:\n                raise AssertionError("accepted callback fault "+fault)\n        return good.stdout,len(cases)\nstdout,total=check_callback_member(members)\nprint(stdout,end="")\nprint("ACTUAL_CALLBACK_MEMBER_REAL_EXECUTOR_ZIP_ANDROID_DB_DOUBLES negatives="+str(total))\ntarget=\'\'\'assertThat(Arrays.equals(before,activationUiCells(3))&&\n            Arrays.equals(archived[0],Files.readAllBytes(retained[0])),\n            "activation callback exact cells and retained backup");\'\'\'\nassert members.count(target)==1\nmutant=members.replace(target,";",1)\ntry:check_callback_member(mutant)\nexcept AssertionError as exc:assert str(exc)=="accepted callback fault backup",str(exc)\nelse:raise AssertionError("callback whole history backup assertion omission survived")\nprint("CALLBACK_WHOLE_PREDICATE_MUTANT GOOD_THEN_BAD_ACCEPTANCE PASS_NOT_ANDROID")\n'
_callback_execution_selftest=selftest
def selftest():
    exec(compile(CALLBACK_EXECUTION_GATE,"callback_actual_member","exec"),
         {"DEVICE_SOURCE":DEVICE.read_text()})
    _callback_execution_selftest()

# Declaration-only fix. Real Android compilation remains a separate CI gate.
CALLBACK_SHAPE_BEFORE=dict(STUBS)
_callback_activity="android/app/Activity.java"
_callback_declaration="public boolean isFinishing(){return false;}"
need("isFinishing(" not in STUBS[_callback_activity],"callback duplicate Activity declaration")
_callback_head,_callback_tail=STUBS[_callback_activity].rsplit("}",1)
need(not _callback_tail.strip(),"callback Activity declaration end")
STUBS[_callback_activity]=_callback_head+_callback_declaration+"}"+_callback_tail

def callback_shape_selftest():
    import contextlib,io,types
    def check(stubs):
        runner=types.FunctionType(syntax_selftest.__code__,dict(globals(),STUBS=stubs))
        with contextlib.redirect_stdout(io.StringIO()):runner()
    try:check(CALLBACK_SHAPE_BEFORE)
    except AssertionError as exc:
        need("new-class Java syntax failed:" in str(exc) and "isFinishing" in str(exc),
             "callback shape original failure changed")
        print("CALLBACK_SHAPE_ORIGINAL_RED\n"+str(exc))
    else:raise AssertionError("callback original declarations unexpectedly compile")
    check(STUBS)
    # Same checker and full candidate, good input then whole declaration omission.
    mutant=dict(STUBS)
    need(mutant[_callback_activity].count(_callback_declaration)==1,"callback declaration mutation anchor")
    mutant[_callback_activity]=mutant[_callback_activity].replace(_callback_declaration,"",1)
    need(mutant==CALLBACK_SHAPE_BEFORE,"callback repair exact inverse")
    try:check(mutant)
    except AssertionError as exc:
        need("new-class Java syntax failed:" in str(exc) and "isFinishing" in str(exc),
             "callback missing declaration wrong rejection")
    else:raise AssertionError("callback whole declaration omission survived")
    print("CALLBACK_SHAPE original_RED GREEN whole_declaration_omission=1 PASS_NOT_ANDROID")

_callback_shape_previous_selftest=selftest
def selftest():
    # Fail the actual full candidate syntax check before slower behavioral tests.
    callback_shape_selftest()
    _callback_shape_previous_selftest()

CALLBACK_OLD_LAYOUT='''                assertThat(added.size()==1&&Files.isRegularFile(added.get(0)),
                    "activation callback exactly one completed backup");
                retained[0]=added.get(0);archived[0]=Files.readAllBytes(retained[0]);'''
CALLBACK_NEW_LAYOUT='''                java.util.List<Path> archives=new java.util.ArrayList<>();
                java.util.List<Path> verification=new java.util.ArrayList<>();
                for(Path path:added){
                    assertThat(!Files.isSymbolicLink(path),"activation callback no backup symlinks");
                    if(Files.isRegularFile(path,java.nio.file.LinkOption.NOFOLLOW_LINKS))archives.add(path);
                    else if(Files.isDirectory(path,java.nio.file.LinkOption.NOFOLLOW_LINKS))verification.add(path);
                }
                assertThat(added.size()==2&&archives.size()==1&&verification.size()==1&&
                    archives.get(0).getFileName().toString().startsWith("before-shortcuts-")&&
                    archives.get(0).getFileName().toString().endsWith(".zip")&&
                    verification.get(0).getFileName().toString().startsWith("verify-"),
                    "activation callback exact archive and verification root: "+added);
                try(java.util.stream.Stream<Path> files=Files.list(verification.get(0))){
                    assertThat(!files.findAny().isPresent(),"activation callback verification root empty");
                }
                retained[0]=archives.get(0);archived[0]=Files.readAllBytes(retained[0]);'''

def callback_layout_gate(gate):
    """Keep original actual-member gate; replace only its inaccurate filesystem double."""
    import ast
    old='''     backup=Files.createTempFile(root.resolve("activation-backups"),"prepared-", ".zip");
     try(java.util.zip.ZipOutputStream zip=new java.util.zip.ZipOutputStream(Files.newOutputStream(backup))){
      zip.putNextEntry(new java.util.zip.ZipEntry("data"));zip.write(new byte[]{1,2,3});zip.closeEntry();
     }'''
    new='''     backup=root.resolve("activation-backups").resolve("before-shortcuts-"+UUID.randomUUID()+".zip");
     com.supercubegame.pockettodo.MediaRepository media=new com.supercubegame.pockettodo.MediaRepository(root.resolve("media"),1024);
     com.supercubegame.pockettodo.BackupArchive.write(backup,new byte[]{1,2,3},Collections.emptySet(),media);
     Path verify=root.resolve("activation-backups").resolve("verify-"+UUID.randomUUID());
     try(com.supercubegame.pockettodo.BackupArchive.Snapshot snapshot=
         com.supercubegame.pockettodo.BackupArchive.read(backup,verify,1024)){
      assertThat(Arrays.equals(snapshot.state(),new byte[]{1,2,3}),"real archive state");
     }
     if(fault.equals("no-verify"))Files.delete(verify);
     if(fault.equals("dirty-verify"))Files.write(verify.resolve("leftover"),new byte[]{1});
     if(fault.equals("extra-file"))Files.write(root.resolve("activation-backups").resolve("unknown"),new byte[]{1});
     if(fault.equals("extra-directory"))Files.createDirectory(root.resolve("activation-backups").resolve("unknown"));
     if(fault.equals("symlink")){
      Path target=root.resolve("backup-target.zip");Files.move(backup,target);Files.createSymbolicLink(backup,target);
     }'''
    assert gate.count(old)==1
    gate=gate.replace(old,new,1)
    old_compile='["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",temp,str(file)]'
    new_compile='["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",temp,str(file),str(BACKUP_SOURCE),str(MEDIA_SOURCE)]'
    assert gate.count(old_compile)==1
    gate=gate.replace(old_compile,new_compile,1)
    anchor='("relaunch","activation callback relaunch exact history")]'
    assert gate.count(anchor)==1
    gate=gate.replace(anchor,'''("relaunch","activation callback relaunch exact history"),
          ("no-verify","activation callback exact archive and verification root"),
          ("dirty-verify","activation callback verification root empty"),
          ("extra-file","activation callback exact archive and verification root"),
          ("extra-directory","activation callback exact archive and verification root"),
          ("symlink","activation callback no backup symlinks")]''',1)
    anchor='good=run("good");assert good.returncode==0,(good.stdout,good.stderr)'
    assert gate.count(anchor)==1
    gate=gate.replace(anchor,'''good=run("good")
        if EXPECT_LAYOUT_RED:
            assert good.returncode==1 and "activation callback exactly one completed backup" in good.stderr,(good.stdout,good.stderr)
            print("ORIGINAL_CALLBACK_LAYOUT_RED_REAL_BACKUP_ARCHIVE",good.stderr)
            return good.stdout,0
        assert good.returncode==0,(good.stdout,good.stderr)''',1)
    anchor="stdout,total=check_callback_member(members)"
    assert gate.count(anchor)==1
    gate=gate.replace(anchor,'''if EXPECT_LAYOUT_RED:
    check_callback_member(members)
stdout,total=check_callback_member(members)''',1)
    # The previous whole retained-backup predicate omission still runs on GREEN.
    start=gate.index("stdout,total=check_callback_member(members)")
    additional=('''
layout=LAYOUT
assert members.count(layout)==1
unchecked='''+"'"+'''                retained[0]=added.stream().filter(Files::isRegularFile).findFirst().get();archived[0]=Files.readAllBytes(retained[0]);'''+ "'"+'''
mutant=members.replace(layout,unchecked,1)
try:check_callback_member(mutant)
except AssertionError as exc:assert str(exc)=="accepted callback fault no-verify",str(exc)
else:raise AssertionError("callback whole layout assertion omission survived")
assert total==14,"callback layout fault population"
print("CALLBACK_LAYOUT_WHOLE_OMISSION GOOD_THEN_BAD_ACCEPTANCE PASS_NOT_ANDROID")
''').replace("LAYOUT",repr(CALLBACK_NEW_LAYOUT),1)
    tail=ast.parse(gate[start:]+additional)
    wrapped=ast.If(test=ast.UnaryOp(op=ast.Not(),operand=ast.Name(id="EXPECT_LAYOUT_RED",ctx=ast.Load())),
                   body=tail.body,orelse=[])
    gate=gate[:start]+ast.unparse(ast.fix_missing_locations(ast.Module(body=[wrapped],type_ignores=[])))+"\n"
    return gate

_callback_layout_gate=callback_layout_gate(CALLBACK_EXECUTION_GATE)
_callback_layout_prior_gate=CALLBACK_EXECUTION_GATE
# Existing selftest reads this global; retain its Android/DB doubles, but use
# actual checked-out transport and publication Java for the filesystem behavior.
CALLBACK_EXECUTION_GATE='''from pathlib import Path
BACKUP_SOURCE=Path(DEVICE_SOURCE_ROOT)/"src/main/java/com/supercubegame/pockettodo/BackupArchive.java"
MEDIA_SOURCE=Path(DEVICE_SOURCE_ROOT)/"src/main/java/com/supercubegame/pockettodo/MediaRepository.java"
EXPECT_LAYOUT_RED=False
'''+_callback_layout_gate

_callback_layout_previous_selftest=selftest
def selftest():
    global CALLBACK_EXECUTION_GATE
    source=DEVICE.read_text()
    need(source.count(CALLBACK_NEW_LAYOUT)==1,"callback exact fixed layout member")
    original=source.replace(CALLBACK_NEW_LAYOUT,CALLBACK_OLD_LAYOUT,1)
    root=DEVICE.parents[6]
    env={"DEVICE_SOURCE":original,"BACKUP_SOURCE":root/"src/main/java/com/supercubegame/pockettodo/BackupArchive.java",
         "MEDIA_SOURCE":root/"src/main/java/com/supercubegame/pockettodo/MediaRepository.java","EXPECT_LAYOUT_RED":True}
    exec(compile(_callback_layout_gate,"callback_original_layout_red","exec"),env)
    saved=CALLBACK_EXECUTION_GATE
    # Existing entry supplies only DEVICE_SOURCE, so bind the checked-out root
    # into the gate text without altering earlier function globals or fixtures.
    CALLBACK_EXECUTION_GATE="DEVICE_SOURCE_ROOT="+repr(str(root))+"\n"+saved
    try:_callback_layout_previous_selftest()
    finally:CALLBACK_EXECUTION_GATE=saved

RETIRE_OLD="        awaitActivationRetired(old,screen);waitForIdleSync();"
RETIRE_NEW='''        // Idleness is not lifecycle completion. Observe on the main thread;
        // finish() was requested exactly once above, never retried here.
        boolean[] destroyed={false};
        long destroyEnd=android.os.SystemClock.uptimeMillis()+5000;
        while(!destroyed[0]&&android.os.SystemClock.uptimeMillis()<destroyEnd){
            runOnMainSync(()->destroyed[0]=old.isDestroyed());
            if(!destroyed[0])Thread.sleep(10);
        }
        assertThat(destroyed[0],"activation callback destroy observation deadline");
        awaitActivationRetired(old,screen);waitForIdleSync();'''

def retire_gate(gate):
    import ast
    pairs=[
      ('public class CallbackHarness {',
       '''class android {static class os {static class SystemClock {
        static long tick;static long uptimeMillis(){tick+=1000;return tick;}
       }}}
       public class CallbackHarness {
       static boolean mainThread;'''),
      ('final TodayScreen screen=new TodayScreen();boolean finishing;',
       'final TodayScreen screen=new TodayScreen();boolean finishing;int observations;'),
      ('boolean isFinishing(){return finishing;}',
       '''boolean isFinishing(){return finishing;}
       boolean isDestroyed(){
        assertThat(mainThread,"destroy observation must own main thread");
        return finishing&&!fault.equals("never-destroyed")&&++observations>=2;
       }'''),
      ('void runOnMainSync(Runnable action){action.run();Runnable callback;while((callback=callbacks.poll())!=null)callback.run();}',
       '''void runOnMainSync(Runnable action){
        mainThread=true;
        try{action.run();Runnable callback;while((callback=callbacks.poll())!=null)callback.run();}
        finally{mainThread=false;}
       }'''),
      ('void awaitActivationRetired(MainActivity old,TodayScreen screen)throws Exception{',
       '''void awaitActivationRetired(MainActivity old,TodayScreen screen)throws Exception{
        boolean[] destroyed={false};runOnMainSync(()->destroyed[0]=old.isDestroyed());
        assertThat(destroyed[0],"activation lifecycle old Activity destroyed");'''),
      ('assert good.returncode==0,(good.stdout,good.stderr)',
       '''if EXPECT_DESTROY_RED:
            assert good.returncode==1 and "activation lifecycle old Activity destroyed" in good.stderr,(good.stdout,good.stderr)
            print("CALLBACK_IDLE_IS_NOT_DESTROY_RED_ANDROID_DOUBLE",good.stderr)
            return good.stdout,0
        assert good.returncode==0,(good.stdout,good.stderr)'''),
      ('("symlink","activation callback no backup symlinks")]',
       '''("symlink","activation callback no backup symlinks"),
          ("never-destroyed","activation callback destroy observation deadline")]'''),
    ]
    # ast.unparse in the prior layout gate changes quote/space style in its tail,
    # but the harness and function prefix above remain exact source.
    for old,new in pairs:
        assert gate.count(old)==1,("retirement harness anchor",old)
        gate=gate.replace(old,new,1)
    tree=ast.parse(gate)
    start=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.If) and
               isinstance(n.test,ast.Name) and n.test.id=="EXPECT_LAYOUT_RED")
    tail=tree.body[start:]
    # Preserve original whole-backup and whole-layout omission tests, now 15 faults.
    class Population(ast.NodeTransformer):
        count=0
        def visit_Assert(self,node):
            if isinstance(node.test,ast.Compare) and isinstance(node.test.left,ast.Name) and node.test.left.id=="total":
                assert ast.literal_eval(node.test.comparators[0])==14
                node.test.comparators[0]=ast.Constant(15);self.count+=1
            return node
    pop=Population();tail=[pop.visit(n) for n in tail];assert pop.count==1
    branch=ast.If(test=ast.Name(id="EXPECT_DESTROY_RED",ctx=ast.Load()),
                  body=ast.parse("check_callback_member(members)").body,orelse=tail)
    tree.body=tree.body[:start]+[branch]
    return ast.unparse(ast.fix_missing_locations(tree))+"\n"

_retire_layout_before=_callback_layout_gate
_retire_execution_before=CALLBACK_EXECUTION_GATE
_callback_layout_gate="EXPECT_DESTROY_RED=False\n"+retire_gate(_callback_layout_gate)
CALLBACK_EXECUTION_GATE="EXPECT_DESTROY_RED=False\n"+retire_gate(CALLBACK_EXECUTION_GATE)
_retire_previous_selftest=selftest
def selftest():
    source=DEVICE.read_text()
    need(source.count(RETIRE_NEW)==1,"callback retirement exact member")
    root=DEVICE.parents[6]
    original=source.replace(RETIRE_NEW,RETIRE_OLD,1)
    env={"DEVICE_SOURCE":original,"EXPECT_DESTROY_RED":True,"EXPECT_LAYOUT_RED":False,
         "BACKUP_SOURCE":root/"src/main/java/com/supercubegame/pockettodo/BackupArchive.java",
         "MEDIA_SOURCE":root/"src/main/java/com/supercubegame/pockettodo/MediaRepository.java"}
    exec(compile(retire_gate(_retire_layout_before),"callback_retire_original_red","exec"),env)
    _retire_previous_selftest()

INFLIGHT_LABEL="prepare_running_finish_preserves_exact"
def parse_activation_inflight(raw,phase):
    labels=re.findall(r"(?:^|stream=)ACTIVATION_INFLIGHT_PASS ([a-z0-9_]+)$",
                      raw.decode("utf-8","strict").replace("\r\n","\n"),re.M)
    need(labels==([INFLIGHT_LABEL] if phase=="seed" else []),"inflight complete ordered checks")
    return labels

_inflight_fixture=fixture
def fixture(phase="seed",api=26):
    raw=_inflight_fixture(phase,api)
    return raw+(("ACTIVATION_INFLIGHT_PASS "+INFLIGHT_LABEL+"\n").encode() if phase=="seed" else b"")

_inflight_producer=ui_phase_evidence
_inflight_consumer=require_ui_evidence
def ui_phase_evidence(raw,phase,api):
    parse_activation_inflight(raw,phase)
    return _inflight_producer(raw,phase,api)
def require_ui_evidence(value,raw,phase,api):
    parse_activation_inflight(raw,phase)
    _inflight_consumer(value,raw,phase,api)

def inflight_parser_selftest():
    import json
    positive=negative=0
    for phase in ("seed","reopen"):
        for api in (26,34):
            raw=fixture(phase,api);value=json.loads(json.dumps(ui_phase_evidence(raw,phase,api)))
            require_ui_evidence(value,raw,phase,api);positive+=1
            line=("ACTIVATION_INFLIGHT_PASS "+INFLIGHT_LABEL+"\n").encode()
            bads=[raw+line,raw+b"ACTIVATION_INFLIGHT_PASS wrong\n"]
            if phase=="seed":bads.append(raw.replace(line,b"",1))
            for bad in bads:
                for check in (lambda:ui_phase_evidence(bad,phase,api),
                              lambda:require_ui_evidence(value,bad,phase,api)):
                    try:check()
                    except AssertionError as exc:need(str(exc)=="inflight complete ordered checks","inflight wrong rejection")
                    else:raise AssertionError("inflight evidence omission survived")
                    negative+=1
            # Whole inflight-validation omission: old pair accepts good input
            # and a stream without the inflight family. Actual entries reject.
            _inflight_consumer(_inflight_producer(raw,phase,api),raw,phase,api)
            if phase=="seed":
                bad=raw.replace(line,b"",1)
                _inflight_consumer(_inflight_producer(bad,phase,api),bad,phase,api)
    need((positive,negative)==(4,20),"inflight parser population")
    print("INFLIGHT_PRODUCER_CONSUMER positives=4 negatives=20 omission_witness PASS")

def inflight_source_selftest():
    import types
    source=DEVICE.read_text()
    entry=LABEL_AST.replace("bridgeSeed","activationUiSeed").replace(
        "bridgeReopen","activationUiReopen").replace('"need"','"activationInflightLifecycle"')
    begin=entry.index('         if(call.getArguments().size()!=2)')
    end=entry.index('         System.out.println',begin)
    entry=entry[:begin]+'''         if(call.getArguments().size()!=1)throw new AssertionError("INFLIGHT_ARGUMENTS");
         String value="inflight_entry";
'''+entry[end:]
    parser=types.FunctionType(java_label_calls.__code__,dict(globals(),LABEL_AST=entry))
    def check(text):
        rows=parser([text])[0]
        need([(x[0],x[1]) for x in rows]==[("activationUiSeed","inflight_entry")],"inflight actual seed entry")
        return rows
    rows=check(source);encoded=source.encode("utf-16-le")
    a=len(encoded[:rows[0][2]*2].decode("utf-16-le"))
    b=len(encoded[:rows[0][3]*2].decode("utf-16-le"))
    try:check(source[:a]+"/* "+source[a:b]+" */"+source[b:])
    except AssertionError as exc:need(str(exc)=="inflight actual seed entry","inflight source wrong rejection")
    else:raise AssertionError("inflight call comment survived")
    print("INFLIGHT_JAVA_AST actual_seed_call whole_call_comment_mutant PASS_NOT_ANDROID")

_inflight_selftest=selftest
def selftest():
    inflight_parser_selftest()
    inflight_source_selftest()
    global ui_phase_evidence,require_ui_evidence,fixture
    old=(ui_phase_evidence,require_ui_evidence,fixture)
    try:
        ui_phase_evidence=_inflight_producer;require_ui_evidence=_inflight_consumer;fixture=_inflight_fixture
        _inflight_selftest()
    finally:
        ui_phase_evidence,require_ui_evidence,fixture=old

INFLIGHT_EXECUTION_GATE='import pathlib\nimport subprocess\nimport tempfile\nAST = \'\\nimport java.nio.file.*;import java.util.*;import javax.tools.*;\\nimport com.sun.source.tree.*;import com.sun.source.util.*;\\npublic class ScreenReads {\\n public static void main(String[] args)throws Exception{\\n  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();\\n  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();\\n  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){\\n   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,List.of("-proc:none"),null,\\n      files.getJavaFileObjects(args[0]));\\n   var units=task.parse();SourcePositions pos=Trees.instance(task).getSourcePositions();\\n   for(CompilationUnitTree unit:units)new TreePathScanner<Void,Void>(){\\n    int reads=0;\\n    public Void visitMethod(MethodTree method,Void unused){\\n     String name=method.getName().toString();\\n     if(name.equals("activationInflightLifecycle"))\\n      System.out.println("METHOD\\\\t"+name+"\\\\t"+pos.getStartPosition(unit,method)+"\\\\t"+pos.getEndPosition(unit,method));\\n     return super.visitMethod(method,unused);\\n    }\\n    public Void visitMethodInvocation(MethodInvocationTree call,Void unused){\\n     if(call.getMethodSelect() instanceof MemberSelectTree\\n        &&((MemberSelectTree)call.getMethodSelect()).getIdentifier().contentEquals("shortcutTestScreen")){\\n      reads++;boolean main=false;\\n      for(TreePath path=getCurrentPath().getParentPath();path!=null;path=path.getParentPath()){\\n       Tree node=path.getLeaf();\\n       if(node instanceof MethodTree||node instanceof ClassTree)break;\\n       if(node instanceof LambdaExpressionTree){\\n        Tree parent=path.getParentPath().getLeaf();\\n        if(parent instanceof MethodInvocationTree){\\n         MethodInvocationTree invoke=(MethodInvocationTree)parent;\\n         main=invoke.getMethodSelect().toString().equals("runOnMainSync")\\n              &&invoke.getArguments().size()==1&&invoke.getArguments().get(0)==node;\\n        }\\n        break;\\n       }\\n      }\\n      System.out.println((main?"MAIN":"OFF_MAIN")+"\\\\t"+pos.getStartPosition(unit,call));\\n     }\\n     return super.visitMethodInvocation(call,unused);\\n    }\\n   }.scan(unit,null);\\n   for(Diagnostic<?> error:errors.getDiagnostics())if(error.getKind()==Diagnostic.Kind.ERROR)\\n    throw new AssertionError(error.toString());\\n  }\\n }\\n}\\n\'\n\ndef inspect(source):\n    with tempfile.TemporaryDirectory() as tmp:\n        root = pathlib.Path(tmp)\n        (root / \'ScreenReads.java\').write_text(AST)\n        (root / \'Source.java\').write_text(source)\n        c = subprocess.run([\'java\', \'-m\', \'jdk.compiler/com.sun.tools.javac.Main\', \'-d\', tmp, str(root / \'ScreenReads.java\')], capture_output=True, text=True, timeout=30)\n        assert c.returncode == 0, c.stderr\n        r = subprocess.run([\'java\', \'-cp\', tmp, \'ScreenReads\', str(root / \'Source.java\')], capture_output=True, text=True, timeout=10)\n        assert r.returncode == 0, r.stderr\n        return [row.split(\'\\t\') for row in r.stdout.splitlines()]\n\nrows=[r for r in inspect(DEVICE_SOURCE) if r[0]=="METHOD"]\nassert len(rows)==1 and rows[0][1]=="activationInflightLifecycle","actual inflight member"\nencoded=DEVICE_SOURCE.encode("utf-16-le")\nmembers=encoded[int(rows[0][2])*2:int(rows[0][3])*2].decode("utf-16-le")\n\n"""Execute the actual device member; Android/DB/backup are explicit doubles.\nReal JDK executor, monitor blocking, stack observation and ZIP filesystem I/O.\n"""\nHARNESS=r\'\'\'\nimport java.nio.file.*;import java.util.*;import java.util.concurrent.*;\nclass android {static class os {static class SystemClock {\n static long uptimeMillis(){return System.nanoTime()/1000000;}\n}}}\npublic class InflightHarness {\n static String fault;static Path dir;static byte[] cells={1,2,3};static boolean main;\n static final Queue<Runnable> callbacks=new ConcurrentLinkedQueue<>();\n static class MediaRepository {\n  static synchronized void publishNewFile()throws Exception{\n   if(fault.equals("no-backup"))return;\n   Files.createDirectories(dir.resolve("verify-1"));\n   Path zip=dir.resolve("before-shortcuts-1.zip");\n   try(java.util.zip.ZipOutputStream out=new java.util.zip.ZipOutputStream(Files.newOutputStream(zip))){\n    out.putNextEntry(new java.util.zip.ZipEntry("state"));out.write(cells);out.closeEntry();\n   }\n   if(fault.equals("extra"))Files.write(dir.resolve("extra"),new byte[]{9});\n   if(fault.equals("verify-dirty"))Files.write(dir.resolve("verify-1/left"),new byte[]{9});\n  }\n }\n static class BackupArchive {static void write()throws Exception{MediaRepository.publishNewFile();}}\n static class Schema4Store {static void prepareActivation()throws Exception{BackupArchive.write();}}\n static class TodayScreen {\n  final ExecutorService io=Executors.newSingleThreadExecutor();\n  volatile boolean busy,closed;Object activationPlan,activationDialog,activationAttempt;\n  void requestShortcutActivation(){\n   busy=!fault.equals("not-busy");\n   io.submit(()->{\n    try{\n     if(fault.equals("wrong-stack"))BackupArchive.write();else Schema4Store.prepareActivation();\n     if(fault.equals("cells"))cells=new byte[]{9};\n     callbacks.add(()->{if(fault.equals("late-ui"))activationDialog=new Object();});\n    }catch(Exception e){throw new RuntimeException(e);}\n   });\n  }\n }\n static class MainActivity {\n  final TodayScreen screen=new TodayScreen();boolean destroyed;\n  void finish(){destroyed=!fault.equals("not-destroyed");screen.closed=!fault.equals("not-closed");screen.io.shutdown();}\n  boolean isDestroyed(){assertThat(main,"inflight destroyed read main");return destroyed;}\n }\n MainActivity uiActivity=new MainActivity();final StringBuilder log=new StringBuilder();\n static void assertThat(boolean value,String reason){if(!value)throw new AssertionError(reason);}\n Path root(){return dir.getParent();}\n TodayScreen captureScreenOnMain(MainActivity a){return a.screen;}\n Object activationQueueField(TodayScreen s,String name)throws Exception{\n  java.lang.reflect.Field f=TodayScreen.class.getDeclaredField(name);f.setAccessible(true);return f.get(s);\n }\n void runOnMainSync(Runnable r){main=true;try{r.run();}finally{main=false;}}\n void waitForIdleSync(){Runnable r;while((r=callbacks.poll())!=null)runOnMainSync(r);}\n void awaitActivationRetired(MainActivity a,TodayScreen s)throws Exception{\n  assertThat(s.io.awaitTermination(10,TimeUnit.SECONDS),"inflight executor retirement");waitForIdleSync();\n }\n byte[] activationUiCells(int version){assertThat(version==3,"inflight schema expectation");return cells.clone();}\n void closeActivationUi(){}\n void launchActivationUi(){if(fault.equals("relaunch"))cells=new byte[]{8};}\n /* ACTUAL_MEMBER */\n public static void main(String[] args)throws Exception{\n  fault=args[0];dir=Paths.get(args[1]).resolve("activation-backups");Files.createDirectories(dir);\n  InflightHarness test=new InflightHarness();TodayScreen screen=test.uiActivity.screen;\n  try{test.activationInflightLifecycle(cells.clone());System.out.print(test.log);}\n  finally{screen.io.shutdown();screen.io.awaitTermination(10,TimeUnit.SECONDS);}\n }\n}\n\'\'\'\nimport pathlib,subprocess,tempfile\ndef check_inflight(members,mode="good"):\n    with tempfile.TemporaryDirectory() as tmp:\n        root=pathlib.Path(tmp);file=root/"InflightHarness.java"\n        file.write_text(HARNESS.replace("/* ACTUAL_MEMBER */",members))\n        r=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",tmp,str(file)],capture_output=True,text=True,timeout=30)\n        assert r.returncode==0,r.stderr\n        return subprocess.run(["java","-cp",tmp,"InflightHarness",mode,tmp],capture_output=True,text=True,timeout=20)\ngood=check_inflight(members)\nassert good.returncode==0 and "ACTIVATION_INFLIGHT_PASS prepare_running_finish_preserves_exact" in good.stdout,(good.stdout,good.stderr)\nfaults=[\n ("wrong-stack","inflight real prepare publication stack"),\n ("not-busy","inflight prepare has no completed plan"),\n ("not-destroyed","inflight destruction precedes prepare release"),\n ("not-closed","inflight destruction precedes prepare release"),\n ("late-ui","inflight no late owned UI"),\n ("no-backup","inflight completed backup layout"),\n ("extra","inflight completed backup layout"),\n ("verify-dirty","inflight verification root empty"),\n ("cells","inflight exact schema3 history"),\n ("relaunch","inflight relaunch preserves history and backup"),\n]\nfor mode,witness in faults:\n    result=check_inflight(members,mode)\n    assert result.returncode==1 and "AssertionError: "+witness in result.stderr,(mode,result.stdout,result.stderr)\n# Whole stack-witness omission accepts good input and wrongly accepts a worker\n# inside backup publication without the real prepare frame. Same checker both times.\nold=\'assertThat(entered,"inflight real prepare publication stack: "+worker.getState()+" "+Arrays.toString(worker.getStackTrace()));\'\nassert members.count(old)==1\nomitted=members.replace(old,"",1)\nassert check_inflight(omitted).returncode==0\nassert check_inflight(omitted,"wrong-stack").returncode==0\nold=\'assertThat(Arrays.equals(before,activationUiCells(3))&&Arrays.equals(archived,Files.readAllBytes(retained)),\\n            "inflight relaunch preserves history and backup");\'\nassert members.count(old)==1\nomitted=members.replace(old,"",1)\nassert check_inflight(omitted).returncode==0\nassert check_inflight(omitted,"relaunch").returncode==0\nprint("INFLIGHT_ACTUAL_MEMBER executor_monitor_stack_ZIP GREEN faults=10 whole_assertion_omissions=2 NOT_ANDROID_DB_TRANSPORT_DOUBLES")\n'
_inflight_execution_selftest=selftest
def selftest():
    exec(compile(INFLIGHT_EXECUTION_GATE,"inflight_actual_member","exec"),
         {"DEVICE_SOURCE":DEVICE.read_text()})
    _inflight_execution_selftest()

CONFIRM_RUNNING_LABEL="confirm_transaction_before_consent_finish_preserves_exact"
def parse_activation_confirm_running(raw,phase):
    labels=re.findall(r"(?:^|stream=)ACTIVATION_CONFIRM_RUNNING_PASS ([a-z0-9_]+)$",
                      raw.decode("utf-8","strict").replace("\r\n","\n"),re.M)
    need(labels==([CONFIRM_RUNNING_LABEL] if phase=="seed" else []),"confirm_running complete ordered checks")
    return labels

_confirm_running_fixture=fixture
def fixture(phase="seed",api=26):
    raw=_confirm_running_fixture(phase,api)
    return raw+(("ACTIVATION_CONFIRM_RUNNING_PASS "+CONFIRM_RUNNING_LABEL+"\n").encode() if phase=="seed" else b"")

_confirm_running_producer=ui_phase_evidence
_confirm_running_consumer=require_ui_evidence
def ui_phase_evidence(raw,phase,api):
    parse_activation_confirm_running(raw,phase)
    return _confirm_running_producer(raw,phase,api)
def require_ui_evidence(value,raw,phase,api):
    parse_activation_confirm_running(raw,phase)
    _confirm_running_consumer(value,raw,phase,api)

def confirm_running_parser_selftest():
    import json
    positive=negative=0
    for phase in ("seed","reopen"):
        for api in (26,34):
            raw=fixture(phase,api);value=json.loads(json.dumps(ui_phase_evidence(raw,phase,api)))
            require_ui_evidence(value,raw,phase,api);positive+=1
            line=("ACTIVATION_CONFIRM_RUNNING_PASS "+CONFIRM_RUNNING_LABEL+"\n").encode()
            bads=[raw+line,raw+b"ACTIVATION_CONFIRM_RUNNING_PASS wrong\n"]
            if phase=="seed":bads.append(raw.replace(line,b"",1))
            for bad in bads:
                for check in (lambda:ui_phase_evidence(bad,phase,api),
                              lambda:require_ui_evidence(value,bad,phase,api)):
                    try:check()
                    except AssertionError as exc:need(str(exc)=="confirm_running complete ordered checks","confirm_running wrong rejection")
                    else:raise AssertionError("confirm_running evidence omission survived")
                    negative+=1
            # Whole confirm_running-validation omission: old pair accepts good input
            # and a stream without the confirm_running family. Actual entries reject.
            _confirm_running_consumer(_confirm_running_producer(raw,phase,api),raw,phase,api)
            if phase=="seed":
                bad=raw.replace(line,b"",1)
                _confirm_running_consumer(_confirm_running_producer(bad,phase,api),bad,phase,api)
    need((positive,negative)==(4,20),"confirm_running parser population")
    print("CONFIRM_RUNNING_PRODUCER_CONSUMER positives=4 negatives=20 omission_witness PASS")

def confirm_running_source_selftest():
    import types
    source=DEVICE.read_text()
    entry=LABEL_AST.replace("bridgeSeed","activationUiSeed").replace(
        "bridgeReopen","activationUiReopen").replace('"need"','"activationConfirmRunningLifecycle"')
    begin=entry.index('         if(call.getArguments().size()!=2)')
    end=entry.index('         System.out.println',begin)
    entry=entry[:begin]+'''         if(call.getArguments().size()!=1)throw new AssertionError("CONFIRM_RUNNING_ARGUMENTS");
         String value="confirm_running_entry";
'''+entry[end:]
    parser=types.FunctionType(java_label_calls.__code__,dict(globals(),LABEL_AST=entry))
    def check(text):
        rows=parser([text])[0]
        need([(x[0],x[1]) for x in rows]==[("activationUiSeed","confirm_running_entry")],"confirm_running actual seed entry")
        return rows
    rows=check(source);encoded=source.encode("utf-16-le")
    a=len(encoded[:rows[0][2]*2].decode("utf-16-le"))
    b=len(encoded[:rows[0][3]*2].decode("utf-16-le"))
    try:check(source[:a]+"/* "+source[a:b]+" */"+source[b:])
    except AssertionError as exc:need(str(exc)=="confirm_running actual seed entry","confirm_running source wrong rejection")
    else:raise AssertionError("confirm_running call comment survived")
    print("CONFIRM_RUNNING_JAVA_AST actual_seed_call whole_call_comment_mutant PASS_NOT_ANDROID")

_confirm_running_selftest=selftest
def selftest():
    confirm_running_parser_selftest()
    confirm_running_source_selftest()
    global ui_phase_evidence,require_ui_evidence,fixture
    old=(ui_phase_evidence,require_ui_evidence,fixture)
    try:
        ui_phase_evidence=_confirm_running_producer;require_ui_evidence=_confirm_running_consumer;fixture=_confirm_running_fixture
        _confirm_running_selftest()
    finally:
        ui_phase_evidence,require_ui_evidence,fixture=old

CONFIRM_RUNNING_EXECUTION_GATE='import pathlib\nimport subprocess\nimport tempfile\nAST = \'\\nimport java.nio.file.*;import java.util.*;import javax.tools.*;\\nimport com.sun.source.tree.*;import com.sun.source.util.*;\\npublic class ScreenReads {\\n public static void main(String[] args)throws Exception{\\n  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();\\n  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();\\n  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){\\n   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,List.of("-proc:none"),null,\\n      files.getJavaFileObjects(args[0]));\\n   var units=task.parse();SourcePositions pos=Trees.instance(task).getSourcePositions();\\n   for(CompilationUnitTree unit:units)new TreePathScanner<Void,Void>(){\\n    int reads=0;\\n    public Void visitMethod(MethodTree method,Void unused){\\n     String name=method.getName().toString();\\n     if(name.equals("activationConfirmRunningLifecycle"))\\n      System.out.println("METHOD\\\\t"+name+"\\\\t"+pos.getStartPosition(unit,method)+"\\\\t"+pos.getEndPosition(unit,method));\\n     return super.visitMethod(method,unused);\\n    }\\n    public Void visitMethodInvocation(MethodInvocationTree call,Void unused){\\n     if(call.getMethodSelect() instanceof MemberSelectTree\\n        &&((MemberSelectTree)call.getMethodSelect()).getIdentifier().contentEquals("shortcutTestScreen")){\\n      reads++;boolean main=false;\\n      for(TreePath path=getCurrentPath().getParentPath();path!=null;path=path.getParentPath()){\\n       Tree node=path.getLeaf();\\n       if(node instanceof MethodTree||node instanceof ClassTree)break;\\n       if(node instanceof LambdaExpressionTree){\\n        Tree parent=path.getParentPath().getLeaf();\\n        if(parent instanceof MethodInvocationTree){\\n         MethodInvocationTree invoke=(MethodInvocationTree)parent;\\n         main=invoke.getMethodSelect().toString().equals("runOnMainSync")\\n              &&invoke.getArguments().size()==1&&invoke.getArguments().get(0)==node;\\n        }\\n        break;\\n       }\\n      }\\n      System.out.println((main?"MAIN":"OFF_MAIN")+"\\\\t"+pos.getStartPosition(unit,call));\\n     }\\n     return super.visitMethodInvocation(call,unused);\\n    }\\n   }.scan(unit,null);\\n   for(Diagnostic<?> error:errors.getDiagnostics())if(error.getKind()==Diagnostic.Kind.ERROR)\\n    throw new AssertionError(error.toString());\\n  }\\n }\\n}\\n\'\n\ndef inspect(source):\n    with tempfile.TemporaryDirectory() as tmp:\n        root = pathlib.Path(tmp)\n        (root / \'ScreenReads.java\').write_text(AST)\n        (root / \'Source.java\').write_text(source)\n        c = subprocess.run([\'java\', \'-m\', \'jdk.compiler/com.sun.tools.javac.Main\', \'-d\', tmp, str(root / \'ScreenReads.java\')], capture_output=True, text=True, timeout=30)\n        assert c.returncode == 0, c.stderr\n        r = subprocess.run([\'java\', \'-cp\', tmp, \'ScreenReads\', str(root / \'Source.java\')], capture_output=True, text=True, timeout=10)\n        assert r.returncode == 0, r.stderr\n        return [row.split(\'\\t\') for row in r.stdout.splitlines()]\n\nrows=[r for r in inspect(DEVICE_SOURCE) if r[0]=="METHOD"]\nassert len(rows)==1 and rows[0][1]=="activationConfirmRunningLifecycle","actual confirm running member"\nencoded=DEVICE_SOURCE.encode("utf-16-le")\nmembers=encoded[int(rows[0][2])*2:int(rows[0][3])*2].decode("utf-16-le")\n\n"""Actual device method, real JCA provider/executor/latches/stack and files.\nAndroid lifecycle, SQLite transaction and archive operations are explicit doubles.\nThis does not stand in for actual Android execution of the same method.\n"""\nHARNESS=r\'\'\'\nimport java.nio.file.*;import java.util.*;import java.util.concurrent.*;\nclass android {static class os {static class SystemClock {\n static long uptimeMillis(){return System.nanoTime()/1000000;}\n}}}\npublic class ConfirmRunningHarness {\n static String fault;static Path dir,backup;static byte[] cells={1,2,3};static boolean main;\n static final Queue<Runnable> callbacks=new ConcurrentLinkedQueue<>();\n static class DB {\n  boolean transaction;int version=3;\n  boolean inTransaction(){return transaction&&!fault.equals("no-transaction");}\n  int getVersion(){return version;}\n }\n static class AppDatabase {\n  final DB db=new DB();boolean consentClosed;\n  DB getReadableDatabase(){return db;}\n }\n static class Schema4Store {\n  static byte[] activationDigest()throws Exception{\n   return java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(backup));\n  }\n  static void confirmActivation(AppDatabase a)throws Exception{\n   a.db.transaction=true;\n   try{\n    activationDigest();\n    if(!a.consentClosed||fault.equals("commit-after-close"))a.db.version=4;\n    if(fault.equals("cells"))cells=new byte[]{9};\n    if(fault.equals("backup"))Files.write(backup,new byte[]{9});\n   }finally{a.db.transaction=false;}\n  }\n }\n static class TodayScreen {\n  final ExecutorService io=Executors.newSingleThreadExecutor();\n  final AppDatabase db=new AppDatabase();\n  volatile boolean busy,closed;Object activationPlan=new Object(),activationDialog=new Object(),activationAttempt;\n  void confirm(){\n   busy=!fault.equals("not-busy");activationAttempt=fault.equals("no-attempt")?null:activationPlan;activationPlan=null;\n   io.submit(()->{\n    try{\n     if(fault.equals("wrong-stack"))Schema4Store.activationDigest();else Schema4Store.confirmActivation(db);\n     callbacks.add(()->{if(fault.equals("late-ui"))activationDialog=new Object();});\n    }catch(Exception error){throw new RuntimeException(error);}\n   });\n  }\n }\n static class MainActivity {\n  final TodayScreen screen=new TodayScreen();boolean destroyed;\n  void finish(){\n   destroyed=!fault.equals("not-destroyed");screen.closed=!fault.equals("not-closed");screen.db.consentClosed=true;\n   screen.activationDialog=null;screen.activationPlan=null;screen.activationAttempt=null;screen.io.shutdown();\n  }\n  boolean isDestroyed(){assertThat(main,"confirm destroyed read main");return destroyed;}\n }\n MainActivity uiActivity=new MainActivity();final StringBuilder log=new StringBuilder();\n AppDatabase database=uiActivity.screen.db;\n static void assertThat(boolean value,String reason){if(!value)throw new AssertionError(reason);}\n void touchUi(String id){}\n void awaitActivation(String id){}\n Path activationUiBackup(){return backup;}\n void touchActivation(String id){if(id.equals("activation-confirm"))uiActivity.screen.confirm();}\n TodayScreen captureScreenOnMain(MainActivity a){return a.screen;}\n Object activationQueueField(TodayScreen s,String name)throws Exception{\n  java.lang.reflect.Field f=TodayScreen.class.getDeclaredField(name);f.setAccessible(true);return f.get(s);\n }\n void runOnMainSync(Runnable r){main=true;try{r.run();}finally{main=false;}}\n void waitForIdleSync(){Runnable r;while((r=callbacks.poll())!=null)runOnMainSync(r);}\n void awaitActivationRetired(MainActivity a,TodayScreen s)throws Exception{\n  assertThat(s.io.awaitTermination(10,TimeUnit.SECONDS),"confirm executor retirement");waitForIdleSync();\n }\n byte[] activationUiCells(int version){\n  assertThat(database.db.version==version,"confirm expected schema");return cells.clone();\n }\n void closeActivationUi(){}\n void launchActivationUi(){if(fault.equals("relaunch"))cells=new byte[]{8};}\n /* ACTUAL_MEMBER */\n public static void main(String[] args)throws Exception{\n  fault=args[0];dir=Paths.get(args[1]);backup=dir.resolve("before-shortcuts-1.zip");Files.write(backup,new byte[]{4,5,6});\n  java.security.Provider original=java.security.MessageDigest.getInstance("SHA-256").getProvider();\n  ConfirmRunningHarness test=new ConfirmRunningHarness();TodayScreen screen=test.uiActivity.screen;\n  try{test.activationConfirmRunningLifecycle(cells.clone());System.out.print(test.log);}\n  finally{\n   screen.io.shutdown();screen.io.awaitTermination(10,TimeUnit.SECONDS);\n   assertThat(java.security.Security.getProvider("PocketConfirmObservation")==null,"provider cleanup on every outcome");\n   assertThat(java.security.MessageDigest.getInstance("SHA-256").getProvider()==original,"original provider order restored");\n  }\n }\n}\n\'\'\'\nimport pathlib,subprocess,tempfile\ndef check_confirm_running(member,mode="good"):\n    with tempfile.TemporaryDirectory() as tmp:\n        root=pathlib.Path(tmp);file=root/"ConfirmRunningHarness.java"\n        file.write_text(HARNESS.replace("/* ACTUAL_MEMBER */",member))\n        compile_result=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",tmp,str(file)],\n            capture_output=True,text=True,timeout=30)\n        assert compile_result.returncode==0,compile_result.stderr\n        return subprocess.run(["java","-cp",tmp,"ConfirmRunningHarness",mode,tmp],\n            capture_output=True,text=True,timeout=20)\ngood=check_confirm_running(members)\nassert good.returncode==0 and "ACTIVATION_CONFIRM_RUNNING_PASS confirm_transaction_before_consent_finish_preserves_exact" in good.stdout,(good.stdout,good.stderr)\nfaults=[\n ("wrong-stack","confirm running transaction entered"),\n ("no-transaction","confirm running transaction entered"),\n ("not-busy","confirm running owns active attempt"),\n ("no-attempt","confirm running owns active attempt"),\n ("not-destroyed","confirm running destruction precedes digest release"),\n ("not-closed","confirm running destruction precedes digest release"),\n ("late-ui","confirm running no late owned UI"),\n ("commit-after-close","confirm expected schema"),\n ("cells","confirm running rollback preserves history and backup"),\n ("backup","confirm running rollback preserves history and backup"),\n ("relaunch","confirm running relaunch preserves history and backup"),\n]\nfor mode,witness in faults:\n    result=check_confirm_running(members,mode)\n    assert result.returncode==1 and "AssertionError: "+witness in result.stderr,(mode,result.stdout,result.stderr)\n    assert "AssertionError: provider cleanup" not in result.stderr\n    assert "AssertionError: original provider" not in result.stderr\n# Whole transaction assertion omission: good still passes; false transaction\n# state now also passes. Actual same method/checker rejects that fault above.\nold=\'\'\'assertThat(database.getReadableDatabase().inTransaction()&&\n                                            database.getReadableDatabase().getVersion()==3,"confirm running actual schema3 transaction");\'\'\'\nassert members.count(old)==1\nomitted=members.replace(old,"",1)\nassert check_confirm_running(omitted).returncode==0\nassert check_confirm_running(omitted,"no-transaction").returncode==0\n# Whole relaunch assertion omission, not a malformed-function surrogate.\nold=\'\'\'assertThat(Arrays.equals(before,activationUiCells(3))&&Arrays.equals(archived,Files.readAllBytes(backup)),\n            "confirm running relaunch preserves history and backup");\'\'\'\nassert members.count(old)==1\nomitted=members.replace(old,"",1)\nassert check_confirm_running(omitted).returncode==0\nassert check_confirm_running(omitted,"relaunch").returncode==0\nprint("CONFIRM_RUNNING_ACTUAL_MEMBER positives=1 faults=11 whole_assertion_omissions=2 PASS_REAL_JCA_NOT_ANDROID")\n'
_confirm_running_execution_selftest=selftest
def selftest():
    exec(compile(CONFIRM_RUNNING_EXECUTION_GATE,"confirm_running_actual_member","exec"),
         {"DEVICE_SOURCE":DEVICE.read_text()})
    _confirm_running_execution_selftest()

POSTDDL_LABEL="postddl_success_finish_commits_exact"
POSTDDL_SECOND="postddl_failure_finish_rolls_back_exact"
def parse_activation_postddl(raw,phase):
    labels=re.findall(r"(?:^|stream=)ACTIVATION_POSTDDL_PASS ([a-z0-9_]+)$",
                      raw.decode("utf-8","strict").replace("\r\n","\n"),re.M)
    need(labels==([POSTDDL_LABEL,POSTDDL_SECOND] if phase=="seed" else []),"postddl complete ordered checks")
    return labels

_postddl_fixture=fixture
def fixture(phase="seed",api=26):
    raw=_postddl_fixture(phase,api)
    return raw+(("ACTIVATION_POSTDDL_PASS "+POSTDDL_LABEL+"\nACTIVATION_POSTDDL_PASS "+POSTDDL_SECOND+"\n").encode() if phase=="seed" else b"")

_postddl_producer=ui_phase_evidence
_postddl_consumer=require_ui_evidence
def ui_phase_evidence(raw,phase,api):
    parse_activation_postddl(raw,phase)
    return _postddl_producer(raw,phase,api)
def require_ui_evidence(value,raw,phase,api):
    parse_activation_postddl(raw,phase)
    _postddl_consumer(value,raw,phase,api)

def postddl_parser_selftest():
    import json
    positive=negative=0
    for phase in ("seed","reopen"):
        for api in (26,34):
            raw=fixture(phase,api);value=json.loads(json.dumps(ui_phase_evidence(raw,phase,api)))
            require_ui_evidence(value,raw,phase,api);positive+=1
            line=("ACTIVATION_POSTDDL_PASS "+POSTDDL_LABEL+"\n").encode()
            bads=[raw+line,raw+b"ACTIVATION_POSTDDL_PASS wrong\n"]
            if phase=="seed":bads.append(raw.replace(line,b"",1))
            for bad in bads:
                for check in (lambda:ui_phase_evidence(bad,phase,api),
                              lambda:require_ui_evidence(value,bad,phase,api)):
                    try:check()
                    except AssertionError as exc:need(str(exc)=="postddl complete ordered checks","postddl wrong rejection")
                    else:raise AssertionError("postddl evidence omission survived")
                    negative+=1
            # Whole postddl-validation omission: old pair accepts good input
            # and a stream without the postddl family. Actual entries reject.
            _postddl_consumer(_postddl_producer(raw,phase,api),raw,phase,api)
            if phase=="seed":
                bad=raw.replace(line,b"",1)
                _postddl_consumer(_postddl_producer(bad,phase,api),bad,phase,api)
    need((positive,negative)==(4,20),"postddl parser population")
    print("POSTDDL_PRODUCER_CONSUMER positives=4 negatives=20 omission_witness PASS")

def postddl_source_selftest():
    import types
    source=DEVICE.read_text()
    entry=LABEL_AST.replace("bridgeSeed","activationUiSeed").replace(
        "bridgeReopen","activationUiReopen").replace('"need"','"activationPostDdlLifecycle"')
    begin=entry.index('         if(call.getArguments().size()!=2)')
    end=entry.index('         System.out.println',begin)
    entry=entry[:begin]+'''         if(call.getArguments().size()!=1)throw new AssertionError("POSTDDL_ARGUMENTS");
         String value="postddl_entry";
'''+entry[end:]
    parser=types.FunctionType(java_label_calls.__code__,dict(globals(),LABEL_AST=entry))
    def check(text):
        rows=parser([text])[0]
        need([(x[0],x[1]) for x in rows]==[("activationUiSeed","postddl_entry")],"postddl actual seed entry")
        return rows
    rows=check(source);encoded=source.encode("utf-16-le")
    a=len(encoded[:rows[0][2]*2].decode("utf-16-le"))
    b=len(encoded[:rows[0][3]*2].decode("utf-16-le"))
    try:check(source[:a]+"/* "+source[a:b]+" */"+source[b:])
    except AssertionError as exc:need(str(exc)=="postddl actual seed entry","postddl source wrong rejection")
    else:raise AssertionError("postddl call comment survived")
    print("POSTDDL_JAVA_AST actual_seed_call whole_call_comment_mutant PASS_NOT_ANDROID")


def postddl_outcome_selftest():
    count=0
    for api in (26,34):
        raw=fixture("seed",api);value=ui_phase_evidence(raw,"seed",api)
        one=("ACTIVATION_POSTDDL_PASS "+POSTDDL_LABEL+"\n").encode()
        two=("ACTIVATION_POSTDDL_PASS "+POSTDDL_SECOND+"\n").encode()
        for bad in (raw.replace(two,b"",1),raw.replace(one+two,two+one,1),raw+two):
            for check in (lambda:ui_phase_evidence(bad,"seed",api),
                          lambda:require_ui_evidence(value,bad,"seed",api)):
                try:check()
                except AssertionError as exc:need(str(exc)=="postddl complete ordered checks","postddl second outcome rejection")
                else:raise AssertionError("postddl second outcome omission/order survived")
                count+=1
    need(count==12,"postddl second outcome population")
    print("POSTDDL_SECOND_OUTCOME negatives=12 PASS")

_postddl_selftest=selftest
def selftest():
    postddl_parser_selftest()
    postddl_outcome_selftest()
    postddl_source_selftest()
    global ui_phase_evidence,require_ui_evidence,fixture
    old=(ui_phase_evidence,require_ui_evidence,fixture)
    try:
        ui_phase_evidence=_postddl_producer;require_ui_evidence=_postddl_consumer;fixture=_postddl_fixture
        _postddl_selftest()
    finally:
        ui_phase_evidence,require_ui_evidence,fixture=old

POSTDDL_EXECUTION_GATE='import pathlib\nimport subprocess\nimport tempfile\nAST = \'\\nimport java.nio.file.*;import java.util.*;import javax.tools.*;\\nimport com.sun.source.tree.*;import com.sun.source.util.*;\\npublic class ScreenReads {\\n public static void main(String[] args)throws Exception{\\n  JavaCompiler compiler=ToolProvider.getSystemJavaCompiler();\\n  DiagnosticCollector<JavaFileObject> errors=new DiagnosticCollector<>();\\n  try(StandardJavaFileManager files=compiler.getStandardFileManager(errors,null,null)){\\n   JavacTask task=(JavacTask)compiler.getTask(null,files,errors,List.of("-proc:none"),null,\\n      files.getJavaFileObjects(args[0]));\\n   var units=task.parse();SourcePositions pos=Trees.instance(task).getSourcePositions();\\n   for(CompilationUnitTree unit:units)new TreePathScanner<Void,Void>(){\\n    int reads=0;\\n    public Void visitMethod(MethodTree method,Void unused){\\n     String name=method.getName().toString();\\n     if(name.equals("activationPostDdlScenario")||name.equals("activationPostDdlLifecycle"))\\n      System.out.println("METHOD\\\\t"+name+"\\\\t"+pos.getStartPosition(unit,method)+"\\\\t"+pos.getEndPosition(unit,method));\\n     return super.visitMethod(method,unused);\\n    }\\n    public Void visitMethodInvocation(MethodInvocationTree call,Void unused){\\n     if(call.getMethodSelect() instanceof MemberSelectTree\\n        &&((MemberSelectTree)call.getMethodSelect()).getIdentifier().contentEquals("shortcutTestScreen")){\\n      reads++;boolean main=false;\\n      for(TreePath path=getCurrentPath().getParentPath();path!=null;path=path.getParentPath()){\\n       Tree node=path.getLeaf();\\n       if(node instanceof MethodTree||node instanceof ClassTree)break;\\n       if(node instanceof LambdaExpressionTree){\\n        Tree parent=path.getParentPath().getLeaf();\\n        if(parent instanceof MethodInvocationTree){\\n         MethodInvocationTree invoke=(MethodInvocationTree)parent;\\n         main=invoke.getMethodSelect().toString().equals("runOnMainSync")\\n              &&invoke.getArguments().size()==1&&invoke.getArguments().get(0)==node;\\n        }\\n        break;\\n       }\\n      }\\n      System.out.println((main?"MAIN":"OFF_MAIN")+"\\\\t"+pos.getStartPosition(unit,call));\\n     }\\n     return super.visitMethodInvocation(call,unused);\\n    }\\n   }.scan(unit,null);\\n   for(Diagnostic<?> error:errors.getDiagnostics())if(error.getKind()==Diagnostic.Kind.ERROR)\\n    throw new AssertionError(error.toString());\\n  }\\n }\\n}\\n\'\n\ndef inspect(source):\n    with tempfile.TemporaryDirectory() as tmp:\n        root = pathlib.Path(tmp)\n        (root / \'ScreenReads.java\').write_text(AST)\n        (root / \'Source.java\').write_text(source)\n        c = subprocess.run([\'java\', \'-m\', \'jdk.compiler/com.sun.tools.javac.Main\', \'-d\', tmp, str(root / \'ScreenReads.java\')], capture_output=True, text=True, timeout=30)\n        assert c.returncode == 0, c.stderr\n        r = subprocess.run([\'java\', \'-cp\', tmp, \'ScreenReads\', str(root / \'Source.java\')], capture_output=True, text=True, timeout=10)\n        assert r.returncode == 0, r.stderr\n        return [row.split(\'\\t\') for row in r.stdout.splitlines()]\n\nrows=[r for r in inspect(DEVICE_SOURCE) if r[0]=="METHOD"]\nassert len(rows)==2 and {r[1] for r in rows}=={"activationPostDdlScenario","activationPostDdlLifecycle"},"actual postddl members"\nencoded=DEVICE_SOURCE.encode("utf-16-le")\nmembers="\\n".join(encoded[int(r[2])*2:int(r[3])*2].decode("utf-16-le") for r in rows)\n\n"""Execute actual scenario AND actual two-scenario caller with real JCA.\nAndroid, SQLite, fixture reset and archive implementation are explicit doubles.\nCompile once per source variant; never drop any fault execution or deadline.\n"""\nHARNESS=r\'\'\'\nimport java.nio.file.*;import java.util.*;import java.util.concurrent.*;\nclass android {static class os {static class SystemClock {\n static long uptimeMillis(){return System.nanoTime()/1000000;}\n}}}\npublic class PostDdlHarness {\n static String fault;static Path dir,backup;static byte[] cells={1,2,3};static boolean main;\n static final Queue<Runnable> callbacks=new ConcurrentLinkedQueue<>();\n static class DB {\n  boolean transaction;int version=3;\n  boolean inTransaction(){return transaction&&!fault.equals("no-transaction");}\n  int getVersion(){return fault.equals("pre-ddl")?3:version;}\n }\n static class AppDatabase {\n  final DB db=new DB();boolean consentClosed;\n  DB getReadableDatabase(){return db;}\n }\n static class Schema4Store {\n  static byte[] activationDigest()throws Exception{\n   return java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(backup));\n  }\n  static void confirmActivation(AppDatabase a)throws Exception{\n   a.db.transaction=true;boolean committed=false;\n   try{\n    activationDigest();\n    if(a.consentClosed)throw new IllegalStateException("consent already closed");\n    a.db.version=4;activationDigest();committed=true;\n    if(fault.equals("cells"))cells=new byte[]{9};\n    if(fault.equals("backup"))Files.write(backup,new byte[]{9});\n    if(fault.equals("lost-commit"))a.db.version=3;\n   }finally{\n    if(!committed&&!fault.equals("lost-rollback"))a.db.version=3;\n    a.db.transaction=false;\n   }\n  }\n }\n static class TodayScreen {\n  final ExecutorService io=Executors.newSingleThreadExecutor();final AppDatabase db=new AppDatabase();\n  volatile boolean busy,closed;Object activationPlan=new Object(),activationDialog=new Object(),activationAttempt;\n  void confirm(){\n   busy=!fault.equals("not-busy");activationAttempt=fault.equals("no-attempt")?null:activationPlan;activationPlan=null;\n   io.submit(()->{\n    try{\n     if(fault.equals("wrong-stack"))Schema4Store.activationDigest();else Schema4Store.confirmActivation(db);\n    }catch(Exception error){}\n    callbacks.add(()->{if(fault.equals("late-ui"))activationDialog=new Object();});\n   });\n  }\n }\n static class MainActivity {\n  final TodayScreen screen=new TodayScreen();boolean destroyed;\n  void finish(){\n   destroyed=!fault.equals("not-destroyed");screen.closed=!fault.equals("not-closed");screen.db.consentClosed=true;\n   screen.activationDialog=null;screen.activationPlan=null;screen.activationAttempt=null;screen.io.shutdown();\n  }\n  boolean isDestroyed(){assertThat(main,"postddl destroyed read main");return destroyed;}\n }\n MainActivity uiActivity;AppDatabase database;int resets;\n final List<TodayScreen> screens=new ArrayList<>();final StringBuilder log=new StringBuilder();\n static void assertThat(boolean value,String reason){if(!value)throw new AssertionError(reason);}\n void touchUi(String id){}\n void awaitActivation(String id){}\n Path activationUiBackup(){return backup;}\n void touchActivation(String id){if(id.equals("activation-confirm"))uiActivity.screen.confirm();}\n TodayScreen captureScreenOnMain(MainActivity a){return a.screen;}\n Object activationQueueField(TodayScreen s,String name)throws Exception{\n  java.lang.reflect.Field f=TodayScreen.class.getDeclaredField(name);f.setAccessible(true);return f.get(s);\n }\n void runOnMainSync(Runnable r){main=true;try{r.run();}finally{main=false;}}\n void waitForIdleSync(){Runnable r;while((r=callbacks.poll())!=null)runOnMainSync(r);}\n void awaitActivationRetired(MainActivity a,TodayScreen s)throws Exception{\n  assertThat(s.io.awaitTermination(10,TimeUnit.SECONDS),"postddl executor retirement");waitForIdleSync();\n }\n byte[] activationUiCells(int version){\n  assertThat(database.db.version==version,"postddl expected schema");return cells.clone();\n }\n void closeActivationUi(){}\n void launchActivationUi(){\n  if(database==null){\n   uiActivity=new MainActivity();database=uiActivity.screen.db;screens.add(uiActivity.screen);\n  }else if(fault.equals("relaunch"))cells=new byte[]{8};\n }\n void resetPostDdlFixture(byte[] before)throws Exception{\n  assertThat(uiActivity==null,"postddl fixture closed");database=null;cells=before.clone();resets++;\n }\n /* ACTUAL_MEMBERS */\n public static void main(String[] args)throws Exception{\n  fault=args[0];dir=Paths.get(args[1]);backup=dir.resolve("backup.zip");Files.write(backup,new byte[]{4,5,6});\n  java.security.Provider original=java.security.MessageDigest.getInstance("SHA-256").getProvider();\n  PostDdlHarness test=new PostDdlHarness();\n  try{\n   test.activationPostDdlLifecycle(cells.clone());\n   assertThat(test.resets==2,"postddl actual caller both scenarios");\n   assertThat(test.log.toString().equals("ACTIVATION_POSTDDL_PASS postddl_success_finish_commits_exact\\nACTIVATION_POSTDDL_PASS postddl_failure_finish_rolls_back_exact\\n"),"postddl actual caller ordered outcomes");\n   System.out.print(test.log);\n  }finally{\n   for(TodayScreen screen:test.screens){screen.io.shutdown();screen.io.awaitTermination(10,TimeUnit.SECONDS);}\n   assertThat(java.security.Security.getProvider("PocketPostDdlObservation")==null,"provider cleanup on every outcome");\n   assertThat(java.security.MessageDigest.getInstance("SHA-256").getProvider()==original,"original provider order restored");\n  }\n }\n}\n\'\'\'\nimport pathlib,subprocess,tempfile\nclass Compiled:\n    def __init__(self,member):\n        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)\n        file=self.root/"PostDdlHarness.java";file.write_text(HARNESS.replace("/* ACTUAL_MEMBERS */",member))\n        result=subprocess.run(["java","-m","jdk.compiler/com.sun.tools.javac.Main","-d",str(self.root),str(file)],\n            capture_output=True,text=True,timeout=30)\n        assert result.returncode==0,result.stderr\n    def run(self,mode="good"):\n        with tempfile.TemporaryDirectory() as files:\n            return subprocess.run(["java","-cp",str(self.root),"PostDdlHarness",mode,files],\n                capture_output=True,text=True,timeout=20)\n    def close(self):self.tmp.cleanup()\ntest=Compiled(members)\ntry:\n    good=test.run()\n    assert good.returncode==0,(good.stdout,good.stderr)\n    faults=[\n     ("wrong-stack","postddl transaction entered"),\n     ("no-transaction","postddl transaction entered"),\n     ("pre-ddl","postddl transaction entered"),\n     ("not-busy","postddl owns active attempt"),\n     ("no-attempt","postddl owns active attempt"),\n     ("not-destroyed","postddl destruction precedes digest release"),\n     ("not-closed","postddl destruction precedes digest release"),\n     ("late-ui","postddl no late owned UI"),\n     ("lost-commit","postddl expected schema"),\n     ("lost-rollback","postddl expected schema"),\n     ("cells","postddl exact outcome preserves history and backup"),\n     ("backup","postddl exact outcome preserves history and backup"),\n     ("relaunch","postddl relaunch preserves history and backup"),\n    ]\n    for mode,witness in faults:\n        result=test.run(mode)\n        assert result.returncode==1 and "AssertionError: "+witness in result.stderr,(mode,result.stdout,result.stderr)\n        assert "AssertionError: provider cleanup" not in result.stderr\n        assert "AssertionError: original provider" not in result.stderr\nfinally:test.close()\nfor old,mode in [\n (\'\'\'assertThat(database.getReadableDatabase().inTransaction()&&\n                                            database.getReadableDatabase().getVersion()==4,"postddl actual schema4 transaction");\'\'\',"pre-ddl"),\n (\'\'\'assertThat(Arrays.equals(before,activationUiCells(rollback?3:4))&&Arrays.equals(archived,Files.readAllBytes(backup)),\n            "postddl relaunch preserves history and backup");\'\'\',"relaunch")]:\n    assert members.count(old)==1\n    test=Compiled(members.replace(old,"",1))\n    try:\n        assert test.run().returncode==0\n        assert test.run(mode).returncode==0\n    finally:test.close()\nold=\'activationPostDdlScenario(before,true);\'\nassert members.count(old)==1\ntest=Compiled(members.replace(old,"",1))\ntry:\n    result=test.run()\n    assert result.returncode==1 and "postddl actual caller ordered outcomes" in result.stderr\nfinally:test.close()\nprint("POSTDDL_ACTUAL_MEMBERS outcomes=2 faults=13 whole_assertion_omissions=2 caller_omission=1 PASS_REAL_JCA_NOT_ANDROID")\n'
_postddl_execution_selftest=selftest
def selftest():
    exec(compile(POSTDDL_EXECUTION_GATE,"postddl_actual_members","exec"),
         {"DEVICE_SOURCE":DEVICE.read_text()})
    _postddl_execution_selftest()

CONNECTION_OLD='''        Thread worker=executor.submit(()->Thread.currentThread()).get(2,java.util.concurrent.TimeUnit.SECONDS);'''
CONNECTION_NEW='''        // Capture this facade's existing connection on its owner before migration.
        // Reopening through the schema3 facade after DDL correctly fails closed.
        SQLiteDatabase observed=executor.submit(()->database.getReadableDatabase()).get(2,java.util.concurrent.TimeUnit.SECONDS);
        Thread worker=executor.submit(()->Thread.currentThread()).get(2,java.util.concurrent.TimeUnit.SECONDS);'''
WITNESS_OLD='''assertThat(database.getReadableDatabase().inTransaction()&&
                                            database.getReadableDatabase().getVersion()==4,"postddl actual schema4 transaction");'''
WITNESS_NEW='''assertThat(observed.inTransaction()&&
                                            observed.getVersion()==4,"postddl actual schema4 transaction");'''

def connection_repair(source):
    # Scope to the uniquely named scenario. The pre-consent scenario stays unchanged.
    begin=source.index("    private void activationPostDdlScenario(")
    end=source.index("    private void activationPostDdlLifecycle(",begin)
    member=source[begin:end]
    assert member.count(CONNECTION_OLD)==member.count(WITNESS_OLD)==1
    fixed=member.replace(CONNECTION_OLD,CONNECTION_NEW,1).replace(WITNESS_OLD,WITNESS_NEW,1)
    assert fixed.replace(CONNECTION_NEW,CONNECTION_OLD,1).replace(WITNESS_NEW,WITNESS_OLD,1)==member
    return source[:begin]+fixed+source[end:]

def connection_gate(gate):
    import ast
    tree=ast.parse(gate)
    harness=next(n for n in tree.body if isinstance(n,ast.Assign) and
                 any(isinstance(t,ast.Name) and t.id=="HARNESS" for t in n.targets))
    value=ast.literal_eval(harness.value)
    old=''' static class AppDatabase {
  final DB db=new DB();boolean consentClosed;
  DB getReadableDatabase(){return db;}
 }'''
    new=''' static class AppDatabase {
  final SQLiteDatabase db=new SQLiteDatabase();boolean consentClosed;
  SQLiteDatabase startupConnection=db;boolean startupOwned=true,startupClosed;
  /* ACTUAL_STARTUP_DATABASE */
  SQLiteDatabase getReadableDatabase(){return startupDatabase();}
 }'''
    assert value.count(old)==1
    value=value.replace(old,new,1).replace(" static class DB {"," static class SQLiteDatabase {\n  boolean isOpen(){return true;}",1)
    harness.value=ast.Constant(value)
    # Extract the real production guard with the same JDK AST, not a copied rule.
    inject='''
saved_ast=AST
try:
    AST=AST.replace('name.equals("activationPostDdlScenario")||name.equals("activationPostDdlLifecycle")',
                    'name.equals("startupDatabase")')
    methods=[r for r in inspect(APP_SOURCE) if r[0]=="METHOD"]
    assert len(methods)==1 and methods[0][1]=="startupDatabase"
    row=methods[0];raw=APP_SOURCE.encode("utf-16-le")
    guard=raw[int(row[2])*2:int(row[3])*2].decode("utf-16-le")
finally:AST=saved_ast
HARNESS=HARNESS.replace("/* ACTUAL_STARTUP_DATABASE */",guard,1)
'''
    at=tree.body.index(harness)+1
    tree.body[at:at]=ast.parse(inject).body
    # Original device scenario must fail against the actual startup guard.
    at=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Assign) and
        isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=="Compiled")
    red='''
assert members.count(CONNECTION_NEW.strip())==1
original=members.replace(CONNECTION_NEW.strip(),CONNECTION_OLD.strip(),1).replace(WITNESS_NEW,WITNESS_OLD,1)
red=Compiled(original)
try:
    result=red.run()
    assert result.returncode==1 and "Startup schema changed; preserve database" in result.stderr,(result.stdout,result.stderr)
    print("POSTDDL_ORIGINAL_FACADE_REENTRY_RED_ACTUAL_GUARD",result.stderr)
finally:red.close()
'''
    tree.body[at:at]=ast.parse(red).body
    # Only update the omission's target, leaving its entire behavior test intact.
    class Witness(ast.NodeTransformer):
        count=0
        def visit_Constant(self,node):
            if isinstance(node.value,str) and node.value==WITNESS_OLD:
                self.count+=1;return ast.copy_location(ast.Constant(WITNESS_NEW),node)
            return node
    change=Witness();tree=change.visit(tree);assert change.count==1
    constants="CONNECTION_OLD="+repr(CONNECTION_OLD)+"\nCONNECTION_NEW="+repr(CONNECTION_NEW)+"\nWITNESS_OLD="+repr(WITNESS_OLD)+"\nWITNESS_NEW="+repr(WITNESS_NEW)+"\n"
    return constants+ast.unparse(ast.fix_missing_locations(tree))+"\n"

POSTDDL_EXECUTION_GATE=connection_gate(POSTDDL_EXECUTION_GATE)
_connection_previous_selftest=selftest
def selftest():
    # Existing selftest executes the replaced global gate and all original tests.
    global POSTDDL_EXECUTION_GATE
    previous=POSTDDL_EXECUTION_GATE
    app=pathlib.Path("src/main/java/com/supercubegame/pockettodo/AppDatabase.java").read_text()
    POSTDDL_EXECUTION_GATE="APP_SOURCE="+repr(app)+"\n"+previous
    try:_connection_previous_selftest()
    finally:POSTDDL_EXECUTION_GATE=previous

if __name__ == "__main__":
    need(len(sys.argv) == 2 and sys.argv[1] in ("selftest", "build", "android", "report"),
         "usage: verify_shortcuts.py selftest|build|android|report")
    globals()[sys.argv[1]]()
