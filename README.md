# Daniya Summer Desktop Pet

Daniya Summer Desktop Pet is a Python + PySide6 desktop pet application. It provides a transparent always-on-top pet window, drag movement, right-click menus, an optional input box, speech bubbles, typewriter text, API chat with local fallback, action animation fallback, the Daniya character pack and relationship engine, and a settings center.

This is an unofficial fan project. The repository does not distribute official game resources, private character assets, user relationship data, or API keys.

## Version Status

- v0.41 action resource system: integrated baseline with placeholder/private asset fallback.
- v0.415 Daniya character pack and relationship engine: integrated.
- v0.42 settings center: integrated.
- v0.43 GitHub open source cleanup: completed.
- v0.44 executable packaging test: completed.
- v0.45 multi-model Provider support: integrated.
- v0.46 local model connection fallback: integrated.
- v0.47 action asset pack fallback: integrated.
- v0.48 release candidate: accepted with no known blocking issues.
- v0.49 official open source release: current stable version.

The public release does not include official game resources, private character assets, model weights, user runtime data, or API keys.

## Features

- Transparent PySide6 desktop pet window with drag, right-click menu, input box, bubble, and typewriter effect.
- API conversation through the existing chat client, with local fallback when no API key is configured or a request fails.
- Action states and fallback paths for idle, talk, clicked, drag, sleep, happy, remind, and v0.415 extended actions.
- Character pack structure under `characters/`, including `characters/template/` for new roles and `characters/daniya/` as the public example pack.
- Relationship state, event log, and user memory runtime data under `data/daniya_relation/`, ignored by Git.
- Settings center for API settings, pet settings, action resources, character pack status/editing, relationship status, data, and diagnostics.
- Multi-model Provider configuration for DeepSeek, OpenAI-compatible, OpenAI, Claude, and local OpenAI-compatible endpoints.
- Local fallback behavior when no API key is configured, an API key is invalid, or the local model service is unavailable.

## Requirements

- Python 3.10, 3.11, or 3.12.
- Windows is the primary target for the current batch scripts.

Install dependencies:

```bat
pip install -r requirements.txt
```

Or use:

```bat
install.bat
```

## Run

For the official Windows build, download `DaniyaSummerPet-v0.49-win-x64.zip` from the GitHub Release, unzip it, and run `DaniyaSummerPet.exe`.

```bat
run.bat
```

Or:

```bat
python main.py
```

Without `.env` or without an API key, the app still starts and uses local fallback replies. API failures should not crash the desktop pet.

## API Configuration

Copy the example environment file:

```bat
copy .env.example .env
```

Fill in your local key:

```text
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

`.env` is ignored by Git. Do not commit real API keys. v0.49 supports DeepSeek, OpenAI-compatible, OpenAI, Claude, and local OpenAI-compatible configuration, with local fallback when no usable key is available.

Optional default config examples are provided:

- `config/app_config.example.json`
- `config/api_config.example.json`

## Assets

The public repository only includes placeholder assets under `assets/placeholder/`.

Put your own authorized private assets under:

```text
assets/private/
```

`assets/private/` is ignored by Git and is not included in public release packages. The project does not distribute official game assets or unauthorized character material. See `docs/asset_policy.md`.

Action images should usually be transparent PNGs. Keep canvas size and character center consistent within the same action group. Missing private action frames must fall back to placeholder or base idle/talk frames.

## Character Packs

- `characters/template/` is the public template for adding new characters.
- `characters/daniya/` is the public example character pack used by the current integration tests.
- Real user relationship data, chat history, reminders, notes, API keys, and private assets do not belong in character packs and are ignored separately under `data/` or `assets/private/`.

Character packs should keep identity, speech style, lore index, relationship rules, events, and actions in YAML/Markdown files. Do not hard-code character lore or personality into Python.

Validate a character pack:

```bat
python tools\validate_character_pack.py characters\daniya
```

## Settings Center

Open the right-click menu and choose the settings center entry. It includes:

- API settings and background connection test.
- Pet size, opacity, always-on-top, idle chat, hourly chime, reminders, and day/night settings.
- Action resource status, reload, and test controls.
- Character pack status and safe YAML editing with backup and validation.
- Relationship state view, export, and backup-protected reset.
- Event log and data status pages.
- Diagnostics for character pack validation, API config, manifest, fallback resources, writable data, and Git ignore safety.

Some timer-related settings may require restart to fully refresh runtime timers.

## Data Directories

Runtime data is stored under `data/`, including:

- `data/chat_history.jsonl`
- `data/affinity.json`
- `data/reminders.json`
- `data/notes.txt`
- `data/daniya_relation/relationship_state.json`
- `data/daniya_relation/event_log.json`
- `data/daniya_relation/user_memory.json`

`data/` and `data/daniya_relation/` are ignored by Git. Do not commit real user relationship state or chat history.

## Development

Common checks:

```bat
python tools\validate_character_pack.py characters\daniya
pytest -q
run.bat
git status --short
```

Read:

- `AGENTS.md` for AI coding agent rules.
- `CONTRIBUTING.md` for contribution workflow.
- `docs/dev_workflow.md` for stage-by-stage validation.
- `docs/roadmap.md` for planned versions.
- `docs/release_checklist.md` for future release checks.

## Roadmap

- v0.44: exe packaging test, completed.
- v0.45: multi-model backend, integrated.
- v0.46: local model connection, integrated.
- v0.47: action asset pack integration, integrated.
- v0.48: release candidate, accepted.
- v0.49: official open source release, current stable version.

## License

Code in this repository is licensed under the MIT License. The license only covers repository code and documentation. It does not cover user-provided character assets, third-party assets, official game resources, or any private files placed under ignored directories.
