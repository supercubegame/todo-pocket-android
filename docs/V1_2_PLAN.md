# Pocket Todo v1.2: approved implementation plan

User approved the 32-project-file scope on 2026-09-21 21:47 Asia/Shanghai. This is implementation authorization, NOT merge authorization.

## Baseline and stages

Branch feature/v1.2-activity-notes-ledger starts at verified v1.1 source 7146894687f785a7191b84e7c62070fe0fe6aa8d. PR #3 and main stay unchanged. Native Android, no HTML substitute. First commit installs executable contracts and evidence readback BEFORE features. Stage 1 only checks pure domain behavior; Android UI/export/restore remain NOT_TESTED and no release is published. Later stages add database/media persistence, native views, exports, complete restore and isolated APK gates.

Target preview package: com.supercubegame.pockettodo.v12.preview, coexisting with original and v1.1. Existing v1.1 package/build files remain baseline until APK stage; they must NOT be represented as a v1.2 release. Disposable debug signing is not a sustainable update channel. Durable keys require secure local user setup, never chat/source/logs. Real-phone feel and receiving-app sharing need user acceptance. User reported v1.1 seems normal on Android; no claim of complete itemized acceptance.

## Product contract

Categories rename/reorder/archive; reusable applications and category shortcuts; ordered paths and tags; ordinary todos and persistent activities; custom typed fields; today/search/templates. Daily or weekday check-ins independent of money. RMB cents, actual expense/refund/income distinct from planned amounts. Multi-date read-only summaries and variable daily batch entry with replay protection. Missing record is not zero expenditure. IDs survive renaming. No duplicated accounting across filters.

Text/image blocks and captions for activity/field notes; private persistent image copies and on-demand thumbnails; drafts. PDF, segmented images and Markdown+assets ZIP share a preview and selected scope. Basic crop/opaque redaction applies to exported derivatives only; never include original images in a redacted share. No private ledger by default. Complete backup includes image bytes and relationships, unlike share exports. Legacy backup imports as ordinary tasks without invented dates or application assignments.

No artificial small content quota, but bounded decoding/import/export/storage with explicit errors and no silent truncation. No claim of physical infinity. No cloud sync, automated check-ins, credentials, auto-posting, formulas, currency conversion, cost allocation, video, OCR, store release or paid services. Small usability improvements within scope allowed.

## Verification

Fast Java domain and legacy regression gate, real nonzero failures. Slow Android build/lint/package/signature and disposable emulator gate added when UI is ready. Verify real picker/media copies, process restart, exact money, repeated batch submission, full backup restoration, corrupted input, exports parsed/decoded and real screenshots. Check redacted output pixels/assets, not just flags. Failed or missing stages never count as passed.

Reports: evidence branch reports/<source-SHA>-<run-ID>.json with failure tails, exact commit/run identity and byte-for-byte readback. Public artifacts use synthetic data only. Real user pictures, ledger and app inventory never belong in repository/evidence. Release only after all required stages AND report verification. No main merge, no old release replacement.

## Authorized files: 10 modified + 22 new

Modified: AGENTS.md, CLAUDE.md, README.md, build.gradle, src/main/AndroidManifest.xml, src/main/java/com/supercubegame/pockettodo/MainActivity.java, .github/workflows/android.yml, tools/verify.py, tools/ui_test.py, tools/emulator_gate.py.

New: docs/V1_2_PLAN.md; src/main/java/com/supercubegame/pockettodo/{ActivityModel,Ledger,CalendarRules,CustomFields,NoteDocument,BackupArchive,LegacyImport,AppDatabase,MediaRepository,ExportRenderer,ShareExporter,AppCatalog,TodayScreen,ActivitiesScreen,CalendarScreen,NoteEditorScreen}.java; src/main/res/values/styles.xml; src/main/res/xml/filepaths.xml; tests/V12CoreTest.java; src/androidTest/java/com/supercubegame/pockettodo/V12DeviceTest.java; tools/verify_exports.py.

Generated schema/build/evidence outputs are not extra hand-authored product files. Any expansion of hand-authored scope requires review. Legacy TodoModel, BackupCodec and CoreTest stay intact.
