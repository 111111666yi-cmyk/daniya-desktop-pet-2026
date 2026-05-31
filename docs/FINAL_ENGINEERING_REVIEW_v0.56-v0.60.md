# Final Engineering Review v0.56-v0.60

Date: 2026-05-31
Branch: `stabilize-v0.56-v0.60`

## Scope

This review closes the staged hardening series from v0.56 through v0.60. It does not introduce future-stage features beyond the accepted scope.

Protected behavior:

- Transparent pet window
- Dragging and edge snapping
- Right-click menu
- Input box
- Bubble and typewriter text
- API conversation and no-key local fallback
- v0.41 action system
- v0.415 `DialogueEngine`, `RelationshipState`, `ActionRouter`, and `LoreRetriever`
- v0.42 settings center

## Stage Summary

| Stage | Commit | Result |
| --- | --- | --- |
| v0.56 | `160c9e1 chore: harden runtime data safety and release packaging` | Runtime data policy, backup/restore tooling, and release safety hardening completed. |
| v0.57 | `8ea2ed8 test: add manual QA freeze checklist` | Manual QA freeze matrix and release freeze checklist added. Real human/API-only items are marked without fake PASS results. |
| v0.58 | `e2bf90d feat: add first-run onboarding flow` | First-run onboarding added with API skip/local fallback, provider setup, non-blocking API test worker, AppData setup state, docs, and tests. |
| v0.59 | `a2076ee ci: add automated project checks` | Local automated checks, GitHub Actions workflow files, and issue/PR templates added. |
| v0.60 | this final review commit | Stable Preview version metadata, package naming, user docs, and final release scan prepared. |

## v0.56 Data Safety

Implemented and verified:

- `docs/DESTRUCTIVE_TEST_POLICY.md`
- `tools/backup_runtime_state.py`
- `tools/restore_runtime_state.py`
- `.gitignore` keeps runtime and backup paths ignored.
- Backup/restore was tested with a sandboxed target and did not touch real `.env`, `data/`, `assets/private/`, or `models/`.

Rules now documented:

- Do not directly delete `data/`, `.env`, `config/api_config.json`, `config/multimodal_config.json`, `assets/private/`, `models/`, or `backups/`.
- Missing-file tests must use backup/restore or a temporary sandbox.
- Backup/restore tools are developer utilities and are not part of the release package.

## v0.57 Manual QA Freeze

Added:

- `docs/MANUAL_QA_v0.57.md`
- `docs/RELEASE_FREEZE_CHECKLIST.md`

Manual-only items remain explicitly blocked until a human tester records results:

- Real multi-monitor drag behavior
- Real right-click menu feel
- Real long text bubble visual check
- Correct live provider API reply with a valid user-owned API key

These were not marked as passing without evidence.

## v0.58 First-Run Onboarding

Implemented:

- `src/first_run_wizard.py`
- `src/setup_state_manager.py`
- Settings Center entry for reopening the wizard
- `docs/first_run_guide.md`
- `docs/troubleshooting.md`

Validated:

- Bad setup JSON falls back safely.
- First-run state uses AppData in packaged mode.
- API setup can be skipped.
- API test runs through a worker thread instead of blocking the UI thread.
- Removed reserved future-feature toggles for TTS, image, and video.

## v0.59 Automated Checks

Added:

- `tools/check_sensitive_files.py`
- `tools/check_release_zip.py`
- `tools/check_character_packs.py`
- `tools/check_config_templates.py`
- `tools/check_docs_links.py`
- `.github/workflows/test.yml`
- `.github/workflows/release-check.yml`
- GitHub issue and pull request templates

Local checks passed before commit. Remote GitHub Actions are prepared, but cannot be reported as passed until this branch is pushed and the workflows run on GitHub.

## v0.60 Stable Preview

Prepared:

- `src/version.py`: `v0.60`
- `pack.bat`: `DaniyaSummerPet-v0.60-win-x64`
- `config/app_config.json`: `v0.60`
- `config/app_config.example.json`: `v0.60`
- `README.md`: current release track and v0.60 package scan command
- `docs/index.md`
- `docs/installation.md`
- `docs/api_config.md`
- `docs/release_checklist.md`: v0.60 target
- `CHANGELOG.md`: v0.60 summary

## Final Local Verification

Commands executed with the project virtual environment Python (`.venv\Scripts\python.exe`) unless a batch file is shown:

```bat
.venv\Scripts\python.exe tools\check_sensitive_files.py
.venv\Scripts\python.exe tools\check_character_packs.py
.venv\Scripts\python.exe tools\check_config_templates.py
.venv\Scripts\python.exe tools\check_docs_links.py
.venv\Scripts\python.exe tools\validate_character_pack.py characters\daniya
.venv\Scripts\python.exe tools\validate_character_pack.py characters\template
.venv\Scripts\python.exe -m pytest -q
pack.bat
.venv\Scripts\python.exe tools\check_release_zip.py release\DaniyaSummerPet-v0.60-win-x64.zip
```

Results:

- Sensitive tracked paths: PASS
- Character pack checks: PASS
- Config template checks: PASS
- Documentation link checks: PASS
- `characters/daniya` validation: PASS
- `characters/template` validation: PASS
- Test suite: `218 passed, 3 skipped`
- Packaging: PASS
- Release zip scan: PASS
- Zip entry count: `445`
- Forbidden zip entries: none
- Secret hits: none

Release exe smoke:

- Executable: `release\DaniyaSummerPet-v0.60-win-x64\DaniyaSummerPet.exe`
- Isolated runtime root: temporary `%APPDATA%\DaniyaSummerPet`
- Alive after 10 seconds: PASS
- Package runtime files found in release directory: none

## Release Package Safety

Confirmed absent from the v0.60 zip:

- `.env`
- `config/api_config.json`
- `config/multimodal_config.json`
- `data/`
- `assets/private/`
- `models/`
- `backups/`
- `characters/test_dummy/`
- `docs/v0.51_patch_audit/`
- `screenshots/`
- `debug/`
- `*.log`

No real API keys were detected by the release zip scanner. The final review and user setup docs are included in the release zip.

## Known Limits

- A correct live cloud API reply was not marked PASS because no user-owned valid provider key was supplied for this final review. The no-key path and local fallback were verified by automated and packaging checks; live provider behavior still requires user-side manual QA with the actual key, quota, and network.
- Real multi-monitor physical drag behavior still requires human observation on the target monitor setup.
- No `v0.60` tag, GitHub Release, or branch push has been performed in this stage.

## Recommendation

The local v0.56-v0.60 hardening series is ready for user review and a controlled branch push or pull request. Do not tag `v0.60` or publish a release until the manual QA freeze checklist is accepted.
