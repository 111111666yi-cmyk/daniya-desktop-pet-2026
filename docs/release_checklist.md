# Release Checklist

Use this checklist before proposing a public release or release-candidate
branch. v0.43 cleanup work should keep the repository publishable; later
packaging or provider stages still require explicit stage acceptance.

## Required Checks

Run from the repository root:

```bat
git status --short
python tools\audit_repo_surface.py
python tools\validate_character_pack.py characters\daniya
pytest -q
run.bat
```

Also verify that no sensitive paths are tracked:

```bat
git ls-files .env data assets/private models backups dist build
```

The sensitive-path command must print nothing.

## Forbidden In Release Packages

Do not include:

- `.env` or `.env.*` except `.env.example`
- `config/api_config.json`
- `config/multimodal_config.json`
- `assets/private/`
- `characters/*/assets/` except `characters/template/assets/`
- `data/`
- `data/daniya_relation/`
- `models/`
- `backups/`
- `build/`
- `dist/` before final package assembly
- `__pycache__/`
- `*.spec`
- `*.log`
- `*.broken-*`
- local audit reports or document exports
- real chat history, relationship state, reminders, or notes
- official game resources or unauthorized third-party assets

## Allowed Public Inputs

Allowed after review:

- source code under `src/` and `core/`
- public tools under `tools/`
- example character metadata under `characters/daniya/`
- template character pack under `characters/template/`
- placeholder assets under `assets/placeholder/`
- public icons under `assets/icons/`
- config defaults and example configs
- `.env.example`
- `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`
- curated docs under `docs/`
- launch and packaging scripts

## Package Smoke Matrix

Before a release, verify:

- no API key startup path
- incorrect API key fallback path
- valid API key conversation path, if a test key is available
- missing private assets fallback
- broken config fallback
- broken runtime data fallback
- broken character pack fallback
- settings center opens
- desktop pet displays with transparent window
- dragging works
- right-click menu opens
- input box sends text
- bubble and typewriter text render
- local fallback works
- action fallback works
- package zip contains only whitelisted content

## Documentation

Confirm these are current:

- `README.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `docs/README.md`
- `docs/asset_policy.md`
- `docs/roadmap.md`
- `docs/dev_workflow.md`
- `docs/known_issues.md`
