# Daniya Summer Desktop Pet v0.49

## Version Summary

v0.49 is the official open source release of Daniya Summer Desktop Pet.
This build is intended to be downloadable, runnable, and reproducible from the public repository.

It supports the transparent desktop pet window, API and local fallback, the action system, settings center, Daniya character pack, multi-model Provider configuration, local model connection fallback, and action resource fallback.

## Main Features

- Transparent borderless desktop pet window.
- Dragging, right-click menu, input box, speech bubble, and typewriter effect.
- Local companion features: notes, reminders, time chime, casual chat, and day/night behavior.
- Action system: `idle`, `talk`, `clicked`, `drag`, `sleep`, `happy`, and `remind`.
- Daniya character pack and relationship engine.
- Special responses, relationship state, event log, and lore retrieval.
- Settings center.
- Multi-model Provider configuration.
- Local model connection fallback.
- Placeholder asset fallback.
- No API Key / incorrect API Key fallback.

## Installation

1. Download `DaniyaSummerPet-v0.49-win-x64.zip`.
2. Unzip it.
3. Run `DaniyaSummerPet.exe`.
4. Optional: copy `.env.example` to `.env` and fill in your API Key.
5. Optional: place authorized custom assets under `assets/private/`.

## API Configuration

Supported configuration targets:

- DeepSeek.
- OpenAI-compatible.
- OpenAI.
- Claude.
- Local OpenAI-compatible.

When no usable key is configured, the app falls back locally instead of crashing.

## Asset Notes

- The default release only includes public placeholder assets.
- It does not include official or unauthorized private assets.
- User private assets belong under `assets/private/`.
- `assets/private/` is excluded from Git and from the default release package.

## Data Notes

- `data/` is used for local chat history, relationship state, reminders, notes, and runtime state.
- `data/` is excluded from Git.
- `data/` is excluded from the default release package.
- The app may create `data/` locally after first launch.

## Known Issues

No known blocking issues.

The v0.48 known-issues document records no non-blocking issues to migrate.

## Security Notes

This release package does not include:

- `.env`
- API keys
- `data/`
- `assets/private/`
- `models/`
- `backups/`
- raw `build/` or `dist/` work directories

## Verification

- `validate_character_pack.py`: passed.
- `validate_assets.py`: passed.
- `pytest -q`: passed, 99 tests.
- `run.bat`: startup smoke passed.
- `pack.bat`: passed.
- Independent directory exe startup smoke: passed.
- No `.env` startup smoke: passed.
- Incorrect API Key startup smoke: passed.
- No private assets startup smoke: passed with neutral placeholder fallback.
- Window boundary regression: passed; the pet is clamped inside the screen.
