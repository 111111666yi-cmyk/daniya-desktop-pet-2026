# Release Checklist

Current source target: `v0.83 memory continuity candidate`

Expected local Windows asset: `DaniyaSummerPet-v0.83-win-x64.zip`

Published packages remain independent from the source candidate until a separate tag and GitHub Release are explicitly approved.

## Source Freeze

- Do not add v0.84+ features.
- Do not implement vision, realtime voice, or multi-character orchestration.
- Confirm v0.80.1, v0.81, v0.82, and v0.83 changes remain independently reviewable.
- Confirm `src/version.py`, `config/app_config.json`, and `config/app_config.example.json` all report `v0.83`.
- Confirm the worktree is clean before the final package.

## Repository Gates

Run:

```bat
git diff --check
.venv\Scripts\python.exe tools\validate_character_pack.py characters\daniya
.venv\Scripts\python.exe tools\check_sensitive_files.py
.venv\Scripts\python.exe tools\check_character_packs.py
.venv\Scripts\python.exe tools\check_config_templates.py
.venv\Scripts\python.exe tools\check_docs_links.py
.venv\Scripts\python.exe tools\check_public_surface.py
.venv\Scripts\python.exe -m pytest -q
run.bat
```

The following command must print no tracked private paths:

```bat
git ls-files .env data assets/private models backups dist build release characters/test_dummy characters/daniya/assets
```

## Runtime Reliability

- Run `tools/measure_startup.py`.
- Run `tools/check_runtime_data.py`.
- Run the finite `tools/check_long_run.py`.
- Keep real 30-minute idle behavior, Windows RSS/GDI/handle trends, and audio-device behavior as manual items unless directly observed.
- Confirm disabled timers do not poll and the checks make no network request.

## Windows Package

Build and scan:

```bat
pack.bat
.venv\Scripts\python.exe tools\check_release_zip.py release\DaniyaSummerPet-v0.83-win-x64.zip
```

Required package evidence:

- zip opens and `testzip()` reports no corrupt member;
- package root and packaged config version are `v0.83`;
- package contains Daniya and template `story.yaml`;
- package contains v0.83 integration acceptance and manual QA documents;
- packaged exe starts with an isolated `DANIYA_RUNTIME_ROOT`;
- runtime files are written outside the package directory;
- size, SHA256, entry count, required-entry count, forbidden-entry count, secret scan, and local-path scan are reported externally.

## Forbidden Package Content

- `.env` or real API keys;
- `data/`, user profile, memory, history, reminders, or window state;
- `assets/private/` or `characters/daniya/assets/`;
- `characters/test_dummy/`;
- `models/`, model cache, audio cache, `backups/`, `build/`, `dist/`, or nested `release/`;
- `config/api_config.json` or `config/multimodal_config.json`;
- local user paths, logs, specs, caches, broken-file backups, screenshots, or internal audit archives.

## Functional Matrix

- startup and exit;
- input show/hide, typing, send, and persistence;
- exact trigger phrases and technical-routing precedence;
- long technical answers and companion-response boundaries;
- simple/advanced Settings Center without value loss;
- optional month-day birthday and legacy profile migration;
- reminders;
- drag, snap, edge peek, edge recovery, and topmost;
- character-pack loading and missing-resource fallback;
- AppData runtime isolation and broken-config recovery;
- no-network and wrong-key fallback;
- file organizer, system status, clipboard, and focus-mode safe defaults.
- story reader, local growth, environment awareness, long-term memory, and observation-diary safe defaults.

## Manual Sign-Off

Complete `docs/V0.83_MANUAL_QA_CHECKLIST.md`.

Automation must not claim PASS for:

- a real cloud Provider without a user-owned key and quota;
- a second physical mixed-DPI monitor that was not attached;
- subjective physical mouse feel;
- SmartScreen, antivirus, or unsigned-executable behavior on other Windows systems;
- code signing when no signing operation occurred.

## Remote Gates

After pushing the reviewed branch:

- GitHub Actions `Test`: PASS;
- GitHub Actions `Public Surface Audit`: PASS;
- inspect any test, docs-link, secret, zip, or public-surface failure;
- do not merge, tag, or create a GitHub Release without separate user approval.
