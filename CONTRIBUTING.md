# Contributing

Thanks for helping with Daniya Summer Desktop Pet. This project is organized by version stages, so contributions should stay focused and avoid crossing into future roadmap work.

## Development Setup

Install Python 3.10, 3.11, or 3.12, then install dependencies:

```bat
pip install -r requirements.txt
```

You may also run:

```bat
install.bat
```

Copy local environment settings if you want API chat:

```bat
copy .env.example .env
```

Do not commit `.env`.

## Running The App

```bat
run.bat
```

Or:

```bat
python main.py
```

The app should still run without an API key by using local fallback.

## Running Tests

```bat
python tools\validate_character_pack.py characters\daniya
pytest -q
```

For UI regressions, also start `run.bat` and confirm the pet appears, the right-click menu opens, settings center opens, bubbles render, and typewriter text still works.

## Adding A Character Pack

1. Copy `characters/template/` to `characters/<character_id>/`.
2. Fill in `character.yaml`, `speech.yaml`, `relationship.yaml`, `events.yaml`, `actions.yaml`, `lore.md`, and `lore_index.yaml`.
3. Keep private user data out of the character pack.
4. Validate:

```bat
python tools\validate_character_pack.py characters\<character_id>
```

Do not hard-code character lore into Python. Do not inject full `lore.md` every turn.

## Adding Action Assets

Public placeholder assets live under `assets/placeholder/`.

Private or user-provided assets belong under:

```text
assets/private/
```

Use transparent PNG files when possible. Keep canvas size and character center consistent within each action. Do not commit official game resources or unauthorized character assets.

Missing actions must keep fallback behavior. Do not rewrite the v0.41 animation system for asset additions.

## Pull Request Rules

- Keep PRs small and scoped to one version stage or bug fix.
- Explain what changed and what was verified.
- Include docs updates when behavior changes.
- Preserve local fallback and asset fallback.
- Avoid blocking work on the PySide6 main thread.
- Never commit secrets, private assets, models, runtime data, or build output.

## Pre-Submit Checklist

- `python tools\validate_character_pack.py characters\daniya`
- `pytest -q`
- `run.bat`
- `git status --short`
- Confirm no tracked `.env`, `data/`, `data/daniya_relation/`, `assets/private/`, `models/`, `backups/`, `dist/`, or `build/`.
