# AGENTS.md

This file defines working rules for Codex and other AI coding agents in this repository.

## Project Stage Rules

- Each version stage must be implemented and accepted independently.
- Do not implement future-stage features without explicit user confirmation.
- v0.43 is only for GitHub open source cleanup.
- Do not enter v0.44 packaging, v0.45 multi-model Provider work, v0.46 local model work, v0.47 asset pack work, v0.48 RC, or v0.49 release tasks unless the user explicitly starts that stage.

## Do Not Break

- Do not refactor the whole project.
- Do not break the transparent pet window.
- Do not break dragging, right-click menus, input box, bubbles, or typewriter text.
- Do not break API conversation.
- Do not break local fallback.
- Do not break the v0.41 action system.
- Do not break the v0.415 `DialogueEngine`, `RelationshipState`, `ActionRouter`, or `LoreRetriever`.
- Do not break the v0.42 settings center.
- Do not submit `.env`, `data/`, `data/daniya_relation/`, `assets/private/`, `models/`, `backups/`, `dist/`, or `build/`.

## Code Change Rules

- Make small, focused changes.
- Prefer existing project patterns over new frameworks.
- Keep fallback behavior for API, config, data, and assets.
- PySide6 UI tasks must not block the main thread.
- Broken config files must fall back safely.
- Missing resources must fall back safely.
- Do not delete existing DeepSeek-compatible API logic.
- Do not delete the v0.30 local companion features.

## Character Pack Rules

- Do not hard-code character personality or lore into Python.
- Character identity, speech style, lore, relationships, events, and action mapping belong under `characters/`.
- New character work should start from `characters/template/`.
- Do not inject full `lore.md` into every prompt.
- Do not bypass `speech_filter`, `relationship_engine`, or `action_router`.
- `characters/daniya/` is the public example pack for this repo; runtime user data belongs under ignored `data/`.

## Pre-Commit Checks

Run these before proposing a commit:

```bat
git status --short
python tools\validate_character_pack.py characters\daniya
pytest -q
run.bat
```

Also check that no sensitive files are tracked:

```bat
git ls-files .env data assets/private models backups dist build
```
