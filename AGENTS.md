# Pocket Todo development

- Native Java Android app. No network permissions, accounts, telemetry or cloud resources.
- Gate first: `python3 tools/verify.py core`; Android: `python3 tools/verify.py build`.
- Emulator: `python3 tools/ui_test.py` against a disposable, booted emulator only.
- Core model must remain Android-free, deterministic and independent of clocks or I/O.
- SharedPreferences persistence belongs to the Activity; do not silently reset corrupt storage.
- Min SDK 26 / target 34 must agree with APK package assertions. This is a test build, not store release.
- State limit 500 tasks / 200 UTF-16 code units must agree with boundary tests and UI input limit.
- Fast core and slow Android checks have distinct logs. Preserve real subprocess exit codes.
- Reports land on the evidence branch with source SHA and run ID and are read back byte-for-byte.
- APK signing is disposable debug signing. Never publish a private signing key.
- Every failure retains its log. Missing emulator evidence is NOT_TESTED, never PASS.
- Keep this file byte-identical to CLAUDE.md and no more than 200 lines.
- Known limits: physical devices, vendor-specific behavior and official distribution signing are untested.
