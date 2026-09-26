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

## 2026-09-26 13:32 approved pagination extension

User explicitly approved the ClickKit scope: add src/main/java/com/supercubegame/pockettodo/PagedNoteRenderer.java and tools/verify_paged_exports.py; modify ShareExporter.java, MainActivity.java, tools/verify_exports.py, tools/verify_schema3.py and this plan, plus the existing ClickUp recovery entry. Seven repository paths and one recovery document, implemented in stages. This does not authorize merge, release, signing changes or replacement of the phone APK.

First slice: shared bounded PDF/PNG-page backend, immutable stable-ID selected inputs, private exclusion before decoding, ordered text and captions, current-image reencoding via the existing guarded PNG adapter, line-aware pages and explicit page/byte-budget errors. Fixed 595x842 pages,36 margins,16 text size,64-page and16MiB budgets are provisional policies, not measured phone capacity. Images fit within a page at preserved aspect ratio and are never enlarged. No source filenames, ledger, backup or origin sets are inputs. PDF and segmented PNG use the same page plan.

Verification is separate from UI: retain existing fast and slow checks, add observer selftests to the fast export gate and actual APK API calls on API26/34. Independently parse PDF text/pages and rasterize with Poppler; enumerate ZIP pages and use JDK ImageIO for page dimensions and current-image/mask pixels. Require selected text order without duplication/loss, private/unselected absence, exclusion-invariant pixels, exact PNG members and explicit invalid/over-budget failures. Propagate failures, publish paged-result.json and nested codec evidence under the same commit/run. Poppler is a disposable CI test dependency, not an app dependency.

Not complete in the backend slice: native format selector/actual-output preview/SAF, same-revision stale consent in the new formats, receiver apps, full multilingual layout/large-font/memory/lifecycle proof. Only after the backend result is read should native integration advance. release_ready=false throughout these slices.
