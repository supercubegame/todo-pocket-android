# Pocket Todo: cross-account continuation checkpoint

Snapshot: 2026-10-14, Asia/Shanghai. This is an engineering handoff, NOT an APK, product release, full-source backup, or assertion that all remaining work is complete. Re-read branch heads and CI before writing. Keep one writer per branch.

## Resume prompt

Continue supercubegame/todo-pocket-android. First verify the product branch, isolated candidate workflow and pinned CI/report below. Continue the already approved controlled shortcut activation scope. Do not restart the project or ask the user to upload source or run scripts by default. Complete integration and original host gates, submit atomically without force, verify exact remote content, then verify API26/API34 against that final product commit. Documentation and old green commits do not replace code delivery. No automatic merge, release, credentials changes, external app launch, or phone-data operation.

## Keep three versions separate

- Product branch: `feature/v1.2-activity-notes-ledger`.
- Product head independently rechecked on this handoff: `3a5a17e1fdc570c73804007cd9a4d2ef36c0966b`.
- Existing PR: https://github.com/supercubegame/todo-pocket-android/pull/4 ; historical base `feature/v1.1-edit-backup`. Recheck current PR metadata before changing it.
- Candidate workflow branch: `ci/shortcut-storage-preflight-4d8742`.
- Candidate workflow head: `56e57bb43453540fa2912c9518a1b5ab71254234`.
- The candidate is materialized into a disposable checkout pinned at product 3a5a. Product pushes remain ZERO. Default startup/activation UI is not integrated.
- Last delivered phone APK: `PocketTodo-v1.2-preview-4d8742d5671f.apk`, 9376689 bytes, SHA256 `e098732d6d420acc750a7a3d2833f533e5e5c1e127df9f2de7f3c109684c0962`.
- Certificate SHA256: `c0f2373329a622978b9f22d7f2212ac0e131c14839af85b277ecf5fe728bf86d`.
- Package: `com.supercubegame.pockettodo.v12.preview`, version 1.2/code3.
- Historical APK artifact: https://github.com/supercubegame/todo-pocket-android/actions/runs/38012763048/artifacts/11656547355 . Availability was not rechecked this turn.
- Phone feedback was apparent successful restore/open/navigation, not exact full-restoration or commercial acceptance. Never recommend clearing app data or uninstalling valuable data.

## Latest newly verified acceptance

Run: https://github.com/supercubegame/todo-pocket-android/actions/runs/38147585377

Exact workflow head 56e57, push, attempt 1. All five jobs succeeded: host, readable receipt, API26, API34, aggregate. Both Android builds and actual device execution steps succeeded, not skipped.

Full host receipt was read: https://github.com/supercubegame/todo-pocket-android/runs/114494720068

All original 21 commands passed, each attempt 1 / budget 300 seconds / exit 0 / not timed out. Product pushes 0, live_ui_enabled=false, release_ready=false.

Complete candidate artifact: https://github.com/supercubegame/todo-pocket-android/actions/runs/38147585377/artifacts/11705194025

Immutable report: https://github.com/supercubegame/todo-pocket-android/blob/3b14b36e87e32652fb0966ef538544cfc27a7214/reports/shortcuts-56e57bb43453540fa2912c9518a1b5ab71254234-38147585377-1.json

Report blob `74ebb2ca952ab7150ae83132d4b783fc7a585d1e`, top-level PASS, scope `ACTIVATION_BACKEND_CANDIDATE_NOT_PRODUCT_NOT_LIVE_UI_NOT_RELEASE`. Expected device contract is 97 seed + 16 reopen = 113/API. API26 labels/source binding were read; the response truncated later in snapshots. Full API34 labels, all snapshots and raw ZIPs were not personally audited this turn. Do not call this a complete byte audit.

## Exact candidate recovery pins

The activation-host artifact contains `receipt.json`, `candidate/` and payload extensions. Its 14-day retention is NOT permanent backup. Restore only into a disposable checkout and verify exact identities before use.

| Candidate path | Bytes | Git blob | SHA256 |
| --- | ---: | --- | --- |
| src/main/java/com/supercubegame/pockettodo/AppDatabase.java | 139068 | 0aaa2875c9c445800f25a7a0caa594541a24bec3 | f3be495c2d4ca175b10b446eacab69d46d2588c8fdc74eecb34c0c84f8ac886c |
| src/main/java/com/supercubegame/pockettodo/Schema4Store.java | 39699 | 1b88780386f99597bfc34dd40457a5730f2f4cd6 | 7c1e1beddbcca686ed04049d7082991d2a9ca022f8235b320edf771d6f83e574 |
| src/androidTest/java/com/supercubegame/pockettodo/Schema4DeviceTest.java | 57152 | 251155aa169c681beac01a3849eb2dd8a37d99fc | a138d877f7f7fcff2ef59cd8d25d7b99da8dc33132885185becad71647c65a27 |
| tools/verify_shortcuts.py | 111849 | 73c556d39736115e624153c398e064f171ec6c0c | 2e6e5dfdf0b4d3a4ad1c73f1f36015ab9b2c44fcc7c0b14821c9a9a0102efe1b |

Permanent recovery sources are immutable versions of `.github/workflows/shortcut-storage.yml`, with hash-bound compressed payloads. Inspect the full source, not an excerpt; preserve the original failure and all guards.

| Workflow commit | Bytes | SHA256 |
| --- | ---: | --- |
| 1ca2404a7b6d75c0645bd19ab07731205f2f6f63 | 26535 | 1a571d49a33c79c46e934dc5b9ee7a8e44cfeca3055089be326f8f51a7d41ae0 |
| 2214ee4af8eadca66b9e3bf71caf0925c0432daa | 15949 | d3ccf20d029c5139cfe9e3c6332ed8944a894ceac0e90d9b0f3eecf5300eb27b |
| 04bb1c5fd574bd8e1666634bf8b22269d2819b6c | 20444 | 6cca32c572e738f86ab8a65472c54a14b6f9fd22054997bebb3fbef83e810d1e |
| 56e57bb43453540fa2912c9518a1b5ab71254234 | 21962 | 4786a65ce08f30c787536adfad91599dcfb9ee58e9c2ea7ca41ae049435c0d83 |

Order: original activation payload in 1ca, evidence-path repair in 2214, resume extension in 04bb, startup extension in 56e57. Preserve materializer transformations and aliases. Do not directly rerun 1ca: it has the known checkout-cleanliness fixture defect.

The prior sandbox development directory was absent on October 14. Historical local paths are NOT portable deliverables. Full local source reconstruction has not been completed. The handoff download contains a read-only candidate validator, not the candidate files or full repository. Its synthetic tests passed: 1 positive, 23 negatives, 2 hash known answers and 4 implementation mutations with valid witnesses. These tests are not Android acceptance.

## Implemented candidate behavior

Verified private backup before explicit single-use activation; consent bound to owner/session/connection/full cells/archive digest; preparation/cancel do not migrate. Transactional migration rechecks source, media and backup, preserves historical typed cells/rowids and starts empty shortcut links. Old facade retires after success.

Non-creating schema4 resume refuses missing, empty, corrupt, symlink and future-version files without deleting/resetting them. `AppDatabase.openForStartup(Context,String)` initializes schema3 only for genuinely missing files, migrates validated schema2 through the frozen old schema3 path, keeps existing schema3 unchanged, and resumes validated schema4. Other versions, including schema1, currently fail closed. Do not silently broaden policy.

## Next actual delivery work

1. Recover the exact candidate and full current source. Do not manually replace full files with snippets.
2. Wire default MainActivity startup to openForStartup off the UI thread, with loading/error UI, lifecycle-safe ownership and cleanup of late results. Preserve the isolated UI test path and no-live-database guard.
3. Add explicit TodayScreen activation entry/dialog. Cancel/replay/stale/foreign/closed/double-tap/recreation must be safe. Close abandoned plans, retire the old facade, replace the screen, invalidate old callbacks.
4. If migration committed but reopening the UI fails, do NOT report that the original data was unchanged and do NOT use the old backupFailed message.
5. Add stable-signature old-APK-to-new-APK overwrite acceptance. Direct database tests are not proof of overwrite upgrade.
6. Update AGENTS.md and CLAUDE.md identically, and integrate the product workflow.
7. Run all 21 original hosts, atomically non-force submit the complete approved integration, independently verify exact remote bytes, then accept API26/API34 against that final PRODUCT commit.

No new default UI code, product commit, APK, merge or release was produced in this handoff turn.

## Active approved scope

October 11, 18:34 explicit approval remains valid for these eleven existing targets. Do not ask again for the same scope:

1. src/main/java/com/supercubegame/pockettodo/AppDatabase.java
2. src/main/java/com/supercubegame/pockettodo/Schema4Store.java
3. src/main/java/com/supercubegame/pockettodo/TodayScreen.java
4. src/main/java/com/supercubegame/pockettodo/MainActivity.java
5. src/androidTest/java/com/supercubegame/pockettodo/Schema4DeviceTest.java
6. tools/verify_shortcuts.py
7. tools/verify_upgrade.py
8. AGENTS.md
9. CLAUDE.md
10. Product branch .github/workflows/shortcut-storage.yml
11. Existing isolated branch .github/workflows/shortcut-storage.yml

Explicit opt-in only; no automatic schema3-to4 activation. Verified backup before migration, fail closed, no data clearing. Preserve original commands, assertions, budgets, output and first failure. Original RED, minimal GREEN, meaningful negative/mutation controls. Existing authorized credentials only. No phone operation, external launch, new credential, merge or release. The October 14 request additionally authorizes preparing this cross-account handoff, not expanding product permissions.

## Original host commands

Each original budget 300 seconds, one attempt; save original output and stop on failure.

```sh
python3 tools/verify_app_catalog.py selftest
python3 tools/verify.py v12
python3 tools/verify_process_control.py selftest
python3 tools/verify_ui_observer.py selftest
python3 tools/verify_adb_transfer.py
python3 tools/verify_evidence.py
python3 tools/verify_schema3.py selftest
python3 tools/verify_note_drafts.py selftest
python3 tools/verify_todo_management.py selftest
python3 tools/verify_custom_fields.py selftest
python3 tools/verify_category_drag.py selftest
python3 -c 'import sys;sys.path.insert(0,"tools");import emulator_gate;emulator_gate.parser_selftest()'
python3 tools/verify_batch_exports.py selftest
python3 tools/verify_upgrade.py selftest
python3 tools/verify_upgrade.py workflow-selftest
python3 tools/verify_process_control.py server-log-selftest
python3 tools/verify_process_control.py isolated-selftest
python3 tools/verify_process_control.py absence-selftest
python3 tools/verify_paged_exports.py selftest
python3 tools/verify_note_management.py selftest
python3 tools/verify_shortcuts.py selftest
```

## Outstanding limitations

- 2b94 API26 directory ADB255: run38024836899, after103 checks, 0.111276seconds against original40seconds, attempt1. EOF before shell-v2 exit packet; root cause not proven.
- b212 run38000599082: after164 checks, 0.154196seconds. Similar symptoms do not prove a common cause.
- Diagnostic run38105137754:20/20 per API on synthetic filenames, NOT_REPRODUCED_NOT_FIXED.
- Separate API34 export ANR in run37918657686 remains unexplained.
- Original1ca run38133227698 failed before hosts because evidence dirtied the checkout.2214 moved only evidence to RUNNER_TEMP, preserving payload/guards and actual Git RED/GREEN/negative controls. Zero product pushes in the failure.
- Activation media fixture is three-byte abc, not real photo/EXIF/performance coverage.
- Private backups disappear on app-data clearing/uninstall. Off-device recovery, power-loss durability, persistent ABA and malicious same-UID races are not proven.
- Historical eleven open parent areas: image derivation, three-format sharing, notes/drafts, catalog/shortcuts, custom fields/field notes, calendar/ledger undo, todos/category drag, schedules/search/templates/archive, restore undo/cleanup/legacy import, lifecycle/storage/large font, full acceptance/stable delivery. Re-query task status before reporting counts. Open status is not proof that features are entirely unimplemented.
- Full UI consistency, real media/IME/large-font testing, performance/storage failure, recipient-app sharing, commercial signing/distribution/privacy/license acceptance remain incomplete.

## Switching ClickUp accounts safely

Keep this GitHub repository and owner. Merely changing ClickUp account does not require fork, transfer, public visibility changes, new Secrets, or a new product branch.

Personal MCP connections are scoped to their creator and Workspace. The new account needs its own authorized GitHub connection. Do not copy tokens, signing keys, one-time codes or secret values. ClickUp memory, chat, Docs, installed skills, Super Agents and sandbox files must not be assumed to transfer automatically.

First perform a read-only delivery check: read this handoff, the pinned report, product source and CI results. This project has readable reports on its evidence branch; do not invent a dependency on another shared reporting repository. A ClickUp-account switch alone does not require rewriting the publisher or rerunning unchanged devices. A future GitHub-owner/CI migration needs a separate permission/reference/report-delivery audit.

Read access does not prove write access. Verify exact remote content and report delivery on the first genuinely authorized new submission. Never launch two branch writers from different accounts.

Current ClickUp support states Brain usage limits apply at Workspace level: switching users within the same Workspace does not reset that allowance. Actual plan, billing and credit balance were not read. Do not promise that another account solves the limit.

Check skill availability in the new account; consult current support before prescribing skill import. No new background developer or automatic progress notifications were configured. The historical hourly read-only Casey agent was not reverified this turn.

## Execution optimization

Stop multiplying backend-only candidates without closing the integrated default-UI and same-commit overwrite-upgrade milestone. Keep fast local gates before expensive Android CI, retain all original regression gates, and parallelize API26/API34 rather than branch writers. Update a short checkpoint after a real submission, final CI outcome or actual blocker. Keep immutable links instead of replaying the entire chat history each turn.
