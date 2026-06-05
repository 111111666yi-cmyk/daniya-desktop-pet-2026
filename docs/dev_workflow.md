# Development Workflow

This document describes the expected development and validation flow for Daniya Summer Desktop Pet.

## Version Flow

1. Work on one version stage at a time.
2. Keep changes scoped to that stage.
3. Run the stage acceptance checks.
4. Update the stage report under `docs/`.
5. Wait for user confirmation before moving to the next version.

Do not mix future-stage features into the current accepted version stage.

## Character Pack Workflow

Create a new character from the template:

```bat
xcopy characters\template characters\new_character /E /I
```

Edit:

- `character.yaml`
- `speech.yaml`
- `relationship.yaml`
- `events.yaml`
- `actions.yaml`
- `lore.md`
- `lore_index.yaml`

Validate:

```bat
python tools\validate_character_pack.py characters\new_character
```

Do not place runtime user data, chat history, API keys, or private assets in a character pack.

## Standard Checks

Character pack:

```bat
python tools\validate_character_pack.py characters\daniya
```

Tests:

```bat
pytest -q
```

Automated project checks:

```bat
python tools\check_sensitive_files.py
python tools\check_character_packs.py
python tools\check_config_templates.py
python tools\check_docs_links.py
python tools\check_public_surface.py
```

Release zip scan:

```bat
python tools\check_release_zip.py release\DaniyaSummerPet-v0.70-win-x64.zip
```

Startup:

```bat
run.bat
```

Git status:

```bat
git status --short
git ls-files .env data assets/private models backups dist build
```

## Resource Fallback Checks

- Start without `assets/private/`.
- Confirm placeholder assets display.
- Trigger idle, talk, clicked, drag, sleep, happy, and remind.
- Trigger v0.415 actions such as soft_idle, close_idle, bubble, and look_away.
- Confirm missing action frames fall back to v0.41-compatible actions.

## Settings Center Checks

- Open the right-click menu.
- Open Settings Center.
- Confirm API settings page loads without printing full API keys.
- Confirm pet settings save.
- Confirm action resource page shows available/missing/fallback status.
- Confirm character pack page validates `characters/daniya/`.
- Confirm relationship reset requires confirmation and creates a backup.
- Confirm diagnostics can run without crashing the desktop pet.

## Behavior Engine Checks

- Press and hold to drag the pet. Confirm it enters the dragging state and switches to the "drag" animation.
- Release the pet close to the screen edges (within 24px). Confirm it snaps smoothly.
- Release the pet in the middle of the screen. Confirm it remains there.
- Verify snapping returns and keeps at least 32px of the pet visible when dragged off-screen.
- Click once. Confirm "clicked" animation triggers.
- Double-click. Confirm "happy" animation and custom line triggers.
- Verify `data/window_state.json` is created/updated on exit and drag release.
- Delete `data/window_state.json` and ensure startup proceeds gracefully.

## Sensitive File Checks

These must not be tracked:

- `.env`
- `data/`
- `data/daniya_relation/`
- `assets/private/`
- `models/`
- `backups/`
- `dist/`
- `build/`
- `__pycache__/`
- `*.spec`
- `*.log`

Use `git rm --cached <path>` if a local file should remain on disk but leave Git tracking.

## Integration Reports

Each accepted stage should have a report under `docs/`, for example:

- `docs/V0.415_INTEGRATION_REPORT.md`
- `docs/V0.42_SETTINGS_ADJUSTMENT_REPORT.md`
- `docs/V0.43_GITHUB_OPEN_SOURCE_REPORT.md`

Reports should list scope, files changed, tests run, regressions checked, sensitive file status, and remaining issues.
