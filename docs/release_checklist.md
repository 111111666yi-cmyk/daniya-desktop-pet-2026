# Release Checklist

Current source target: `v0.70`

Latest published Windows Release: `v0.65.2`

## Source Freeze

- Do not add v0.71 features during v0.70 acceptance.
- Confirm `master` is the intended source branch.
- Confirm the worktree contains only reviewed v0.70 version, documentation, test, and packaging changes.
- Confirm `src/version.py`, `config/app_config.json`, and `config/app_config.example.json` all report `v0.70`.

## Repository Gates

Run:

```bat
git diff --check
python tools\validate_character_pack.py characters\daniya
python tools\check_sensitive_files.py
python tools\check_character_packs.py
python tools\check_config_templates.py
python tools\check_docs_links.py
python tools\check_public_surface.py
pytest -q
run.bat
```

The following command must print no tracked private paths:

```bat
git ls-files .env data assets/private models backups dist build release characters/test_dummy characters/daniya/assets
```

## Windows Package

Build and scan:

```bat
pack.bat
python tools\check_release_zip.py release\DaniyaSummerPet-v0.70-win-x64.zip
```

Required package evidence:

- zip opens and `testzip()` reports no corrupt member;
- packaged config version is `v0.70`;
- package contains Daniya and template story files;
- package contains v0.70 integration and manual QA documents;
- packaged exe starts with an isolated `DANIYA_RUNTIME_ROOT`;
- runtime files are written outside the package directory;
- entry count is recorded in `docs/V0.70_INTEGRATION_ACCEPTANCE.md`;
- SHA256 is recorded in the external final build report or GitHub release metadata because an archive cannot contain its own stable hash.

## Forbidden Package Content

- `.env` or real API keys;
- `data/` or user memory/history/reminders;
- `assets/private/` or `characters/daniya/assets/`;
- `characters/test_dummy/`;
- `models/`, `backups/`, `build/`, `dist/`, or nested `release/`;
- `config/api_config.json` or `config/multimodal_config.json`;
- local user paths, logs, specs, caches, or broken-file backups;
- internal audit archives and screenshots.

## Functional Matrix

- natural reminder parsing, confirmation, cancellation, and due event;
- file organizer preview, sensitive-path skip, confirmation, and rollback data;
- system status disabled default, interval, thresholds, and cooldown;
- clipboard disabled default, sensitive blocking, and preview privacy;
- focus-mode suppression;
- twelve-page Settings Center;
- input bar show/hide persistence;
- left/right edge peek and interaction guards;
- Provider status without false PASS;
- local fallback and API-error fallback;
- passive feedback overlap prevention and idle return;
- character discovery, fallback, reload, story/lore/action/manifest fallback, and per-character state.

## Manual Sign-Off

Complete `docs/V0.70_MANUAL_QA_CHECKLIST.md`.

Automation must not claim PASS for:

- real cloud Provider replies without a user-owned key and quota;
- multi-monitor or mixed-DPI behavior on hardware not present;
- subjective drag, right-click, animation, and long-text visual feel;
- antivirus or SmartScreen behavior on another Windows installation.

## Remote Gates

After pushing the reviewed v0.70 source commit:

- GitHub Actions `Test`: PASS;
- GitHub Actions `Public Surface Audit`: PASS;
- inspect failures for tests, docs links, secrets, package assumptions, or public-surface wording;
- run `Release Check` manually before uploading a v0.70 release asset.

Do not upload or publish a v0.70 GitHub Release until local package evidence, remote Actions, and required manual sign-off are accepted.
