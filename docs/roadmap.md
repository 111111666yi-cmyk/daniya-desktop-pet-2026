# Roadmap

The project advances through explicit version stages. Each stage should be implemented, tested, and accepted independently.

## v0.41 - Action Resource System

Goal:
- Provide action resource loading and fallback behavior for the desktop pet.
- Support base actions such as idle, talk, clicked, drag, sleep, happy, and remind.

Not in scope:
- New private action asset production.
- Large animation system rewrites.

Acceptance:
- Placeholder assets display.
- Missing private frames fall back safely.
- The pet never disappears because an action resource is missing.

Status: completed/integrated.

## v0.415 - Character Pack And Relationship Engine

Goal:
- Integrate `characters/daniya/`, `characters/template/`, schema validation, special responses, speech filtering, `DialogueEngine`, relationship state, event/memory handling, action routing, lore retrieval, and the read-only Daniya settings window.

Not in scope:
- Settings center editing.
- Multi-model Provider backend.
- Full lore injection on every prompt.

Acceptance:
- `tools/validate_character_pack.py` passes.
- Special responses are prioritized.
- Relationship state and lore retrieval work with fallback.
- v0.41 action fallback remains intact.

Status: completed/integrated.

## v0.42 - Settings Center

Goal:
- Add settings center pages for API, pet settings, action resources, character pack status/editing, relationship state, data, and diagnostics.

Not in scope:
- Full multi-model Provider architecture.
- Local model downloader.
- TTS or Vision.

Acceptance:
- Settings center opens from the right-click menu.
- YAML edits are backup-protected and validated.
- Relationship reset is confirmation and backup protected.
- v0.415 regression tests pass.

Status: completed/integrated.

## v0.43 - GitHub Open Source Cleanup

Goal:
- Prepare the repository for public GitHub use.
- Document sensitive file policy, asset policy, development workflow, roadmap, and release checklist.
- Keep public character template and example pack.

Not in scope:
- Packaging exe.
- Publishing Release.
- Multi-model Provider work.

Acceptance:
- `.gitignore` protects secrets, data, private assets, models, backups, and build output.
- README and open source docs are complete.
- Sensitive files are not tracked.
- Tests and character validation pass.

Status: current stage.

## v0.44 - EXE Packaging Test

Goal:
- Test executable packaging and runtime startup.

Not in scope:
- Publishing the final public Release.
- Adding multi-model Provider work.

Acceptance:
- Packaged exe starts.
- Placeholder assets work.
- Private assets remain excluded by default.
- No secrets or runtime data are bundled.

Status: next stage.

## v0.45 - Multi-Model Backend

Goal:
- Add a provider abstraction for multiple model backends.

Not in scope:
- Local model downloader.
- TTS or Vision.

Acceptance:
- Existing DeepSeek-compatible flow still works.
- Provider errors fall back safely.
- Settings do not expose API keys.

Status: planned.

## v0.46 - Local Model Connection

Goal:
- Connect to supported local model runtimes.

Not in scope:
- Bundling model weights.
- Downloading large models by default.

Acceptance:
- Local mode can be enabled safely.
- API mode remains intact.
- UI does not block during model calls.

Status: planned.

## v0.47 - Action Asset Pack Integration

Goal:
- Add structured support for richer action asset packs.

Not in scope:
- Shipping unauthorized assets.

Acceptance:
- Asset pack manifests validate.
- Missing assets fall back.
- Placeholder mode still works.

Status: planned.

## v0.48 - Release Candidate

Goal:
- Freeze major behavior and run full regression.

Not in scope:
- New feature expansion.

Acceptance:
- Tests pass.
- Startup, settings center, action fallback, data fallback, and no-API fallback pass.

Status: planned.

## v0.49 - Public Release

Goal:
- Publish the final public release package.

Not in scope:
- Unreviewed new features.

Acceptance:
- Release checklist is complete.
- No secrets, private assets, models, runtime data, or unauthorized assets are included.

Status: planned.
