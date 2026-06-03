# Release Checklist

## v0.49 Release Check Result

Status: passed for local packaging and smoke verification on 2026-05-29.

- v0.48 RC report exists: pass.
- v0.48 known issues file exists: pass.
- Blocking issues: none recorded in `docs/V0.48_RC_REPORT.md` or `docs/KNOWN_ISSUES_v0.48.md`.
- Version metadata updated to `v0.49`: pass.
- Public placeholder assets are neutral abstract placeholders: pass.
- Pet window startup, drag, docking, resize, and offscreen recovery are constrained inside the screen: pass, covered by regression tests.
- `python tools\validate_character_pack.py characters\daniya`: pass.
- `python tools\validate_assets.py assets\private`: pass.
- `pytest -q`: pass, 99 tests.
- `run.bat`: startup smoke pass.
- `pack.bat`: pass.
- Official zip: `release/DaniyaSummerPet-v0.49-win-x64.zip`.
- Independent unpack smoke test: pass.
- Wrong API key startup smoke test: pass.
- No `.env`, `data/`, `assets/private/`, `models/`, `backups/`, `build/`, `dist/`, `__pycache__/`, `*.log`, `*.spec`, or `*.broken-*` in zip: pass.
- Git tracked sensitive file check: pass.
- Real valid API key network test: not run; no valid release-test key was provided in this environment.

v0.43 does not publish a Release. This checklist prepares future v0.44/v0.49 release work.

## Forbidden In Release Packages

Do not include:

- `.env`
- `.env.*` except `.env.example`
- `assets/private/`
- `data/`
- `data/daniya_relation/`
- `models/`
- `backups/`
- `build/`
- `dist/` before final packaging review
- `__pycache__/`
- `*.spec`
- `*.log`
- real chat history
- real relationship state
- real reminders or notes
- private API keys
- official or unauthorized third-party assets

## Automated Release Checks

Run before sharing a release package:

```bat
python tools\check_sensitive_files.py
python tools\check_character_packs.py
python tools\check_config_templates.py
python tools\check_docs_links.py
python tools\check_public_surface.py
pytest -q
pack.bat
python tools\check_release_zip.py release\DaniyaSummerPet-v0.60-win-x64.zip
```

The GitHub `Release Check` workflow performs the package build and zip scan manually via `workflow_dispatch`. It must not require real API keys, private assets, or `characters/test_dummy/`.

## v0.60 Target

- Release name: `DaniyaSummerPet v0.60 Stable Preview`
- Zip name: `DaniyaSummerPet-v0.60-win-x64.zip`
- Do not create or push the `v0.60` tag until the final local report is accepted.

## v0.60 Post-Audit Release Blocker Checklist

Baseline for the blocker fix: `862beda`.

- Ignore local audit report files with `*_audit_report.docx`: required before commit.
- Revert unexplained runtime `config/app_config.json` changes before release; keep only public default fallback reply structures.
- Keep public `config/model_profiles.json` aligned with v0.60 profile history defaults.
- Ensure `pack.bat` includes `characters/daniya/story.yaml`.
- Ensure the release zip contains `characters/daniya/story.yaml` and `characters/template/story.yaml`.
- Ensure the release zip excludes `characters/daniya/assets/`, `assets/private/`, `data/`, `models/`, `.env`, `config/api_config.json`, `config/multimodal_config.json`, `characters/test_dummy/`, real API keys, private assets, and user chat records.
- Sanitize docs so tracked files do not contain local user paths.
- Re-run `pack.bat` and `tools\check_release_zip.py` after docs are updated.
- Keep live API reply, multi-monitor drag, right-click feel, and long text bubble visual behavior as manual confirmation items.

## Allowed Public Files

Allowed after review:

- packaged exe in later v0.44/v0.49 stages
- `config/` defaults and example configs
- `.env.example`
- `characters/template/`
- `characters/daniya/` public example or placeholder pack
- `assets/placeholder/`
- `core/`
- `src/`
- `tools/`
- `docs/`
- `README.md`
- `LICENSE`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `requirements.txt`
- `install.bat`
- `run.bat`
- `pack.bat`

## Regression Matrix

Before release, test:

- no API key
- incorrect API key
- valid API key
- no `assets/private/`
- broken private manifest
- missing action frames
- broken config
- broken runtime data
- broken character pack
- settings center opens
- Daniya read-only settings window opens
- main desktop pet displays
- right-click menu opens
- input box sends text
- bubble displays
- typewriter effect runs
- local fallback works
- action fallback works

## Git Safety

Run:

```bat
git status --short
git ls-files .env data assets/private models backups dist build
```

The sensitive file command should return no tracked private files.

## Documentation

Confirm these are current:

- `README.md`
- `LICENSE`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `docs/asset_policy.md`
- `docs/roadmap.md`
- `docs/dev_workflow.md`
- stage integration report
