# Live API QA v0.60 - MiMo Addendum

Date: 2026-06-01
Branch: `stabilize-v0.56-v0.60`

## Scope

This addendum records the post-review live API check for Xiaomi MiMo during the v0.60 acceptance pass.

No API key is stored in this document, in Git, or in release artifacts.

## Finding

MiMo presents an OpenAI-compatible `/chat/completions` endpoint, but its working authentication mode is not the default Bearer header used by most OpenAI-compatible providers.

Verified configuration:

```text
Provider: OpenAI-compatible
Base URL: https://api.xiaomimimo.com/v1
Model: mimo-v2.5
Auth Header: api-key
API Key Env: OPENAI_COMPATIBLE_API_KEY
```

Observed behavior:

- `auth_header=api-key` with `mimo-v2.5` returned a real response through `ProviderManager` with `source=api`.
- `auth_header=bearer` can return HTTP 200 with empty content, which must be treated as malformed and should not be marked PASS.
- Very small `max_tokens` values can produce empty `content` on Chinese prompts because output budget may be consumed before final content is emitted.
- The project default `max_tokens=360` is sufficient for the lightweight MiMo probe used in this check.

## Implemented Fixes

- `openai_api.chat()` now accepts `auth_header`.
- Supported OpenAI-compatible auth modes: `bearer`, `api-key`, `x-api-key`, and `none`.
- `ProviderManager` forwards profile `auth_header` into OpenAI-compatible calls and tests.
- `SettingsManager` saves and syncs `auth_header` into `api_config.json` and `model_profiles.json`.
- MiMo URLs under `xiaomimimo.com` are normalized to `auth_header=api-key`.
- Settings Center exposes an `Auth Header` selector.
- OpenAI-compatible first-run setup now has a real `OPENAI_COMPATIBLE_API_KEY` env binding.
- `DialogueEngine` preserves `(reply, source)` tuples so successful cloud replies can be recorded as `source=api`.
- The public Daniya fallback asset path is preferred over the generic template for the default `daniya` character.

## Verification

Commands run:

```bat
.venv\Scripts\python.exe -m pytest tests\test_boundaries.py tests\test_provider_registry.py tests\test_provider_manager_switching.py tests\test_model_profiles_config.py tests\test_first_run_wizard.py tests\test_dialogue_engine.py -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe tools\check_sensitive_files.py
.venv\Scripts\python.exe tools\validate_character_pack.py characters\daniya
.venv\Scripts\python.exe tools\validate_character_pack.py characters\template
.venv\Scripts\python.exe tools\check_character_packs.py
.venv\Scripts\python.exe tools\check_config_templates.py
.venv\Scripts\python.exe tools\check_docs_links.py
git diff --check
pack.bat
.venv\Scripts\python.exe tools\check_release_zip.py release\DaniyaSummerPet-v0.60-win-x64.zip
```

Results:

- Focused API/settings/dialogue tests: `89 passed`
- Full test suite: `224 passed, 3 skipped`
- Sensitive tracked-path check: PASS
- Character pack validation: PASS for `daniya` and `template`
- Character pack aggregate check: PASS
- Config template check: PASS
- Docs local link check: PASS
- Whitespace check: PASS
- Rebuilt release package: PASS
- Release zip scan: PASS
- Release zip entry count: `449`
- MiMo addendum included in zip: PASS
- Release exe smoke: PASS, alive after 10 seconds with isolated AppData runtime
- Source startup smoke: PASS, alive after 8 seconds with isolated runtime and no leftover `main.py` process

## Remaining Manual Items

- Z.AI remains blocked for a successful live reply unless the user account has sufficient quota/resource package.
- Automated GUI acceptance was completed in `docs/GUI_ACCEPTANCE_QA_v0.60.md`; real mouse/monitor visual feel still requires human observation.
