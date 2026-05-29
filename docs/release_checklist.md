# Release Checklist

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
