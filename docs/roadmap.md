# Roadmap

The project advances through explicit version stages. Each stage should be implemented, tested, and accepted independently.

## v0.60 - Stable Preview Hardening

Goal:
- Consolidate the v0.56-v0.60 hardening work into a stable public preview baseline.
- Keep runtime data, private assets, model files, local reports, and API keys out of Git and release packages.

Not in scope:
- Tagging or publishing a GitHub Release before manual acceptance.
- Claiming real-provider QA without a real configured key and quota.

Acceptance:
- Local checks, tests, packaging, and release zip scanning pass.
- Public character copy no longer exposes old owner title, internal engineering wording, or default story spoilers.
- Manual-required GUI and real-provider items are documented instead of falsely marked pass.

Status: branch pushed; release/tag still gated by manual acceptance.

## v0.61 - Public Surface And Quiet Defaults

Goal:
- Remove public copy that feels like internal engineering commentary or god-view narration.
- Make the first-run and default desktop pet behavior quiet unless the user explicitly enables active behavior.
- Give users visible control over automatic memory and manual memory notes.

Not in scope:
- Publishing a tag or GitHub Release.
- Claiming real-provider QA without a real configured key and quota.

Acceptance:
- `tools/check_public_surface.py` passes.
- Idle chat, hourly chime, edge peek, and idle behavior default to off.
- Idle behavior cannot be configured below 600 seconds through normal config paths.
- Settings Center exposes visible memory review, add, refresh, and clear actions.

Status: in progress.

## v0.62 - Provider And Memory Continuity Review

Goal:
- Ensure user profile, automatic memory, unlocked story memory, and manual notes flow through cloud and local text Provider channels.
- Keep API keys in `.env` or environment variables, never in tracked config or release packages.

Not in scope:
- Adding TTS, image, video, or new future-stage model capabilities.

Acceptance:
- Provider prompt construction includes profile and memory context before DeepSeek/OpenAI-compatible/Ollama text calls.
- Real Z.AI/API acceptance remains manual until a user-owned key and quota are available.
- Sensitive-file checks and release zip checks remain green.

Status: in progress.

## v0.63 - Runtime Behavior And GUI Acceptance

Goal:
- Verify the pet does not move or speak unexpectedly under default settings.
- Re-test right-click menu feel, long bubble layout, Settings Center lifecycle, and story reading flow.

Not in scope:
- Rewriting the UI framework.
- Shipping new character art or unauthorized assets.

Acceptance:
- Default runtime behavior is passive until user interaction or explicit setting changes.
- Long text bubble and story reading are manually accepted.
- Multi-monitor drag is tested on a real multi-monitor machine before final release claims.

Status: planned/manual acceptance required.

## v0.64 - Public Repository And Package Audit

Goal:
- Keep the GitHub repository and release package free of local reports, local paths, runtime data, private assets, models, API keys, and stale internal audit logs.

Not in scope:
- Uploading release zip artifacts without explicit user confirmation.

Acceptance:
- Public docs link check passes.
- Public-surface check passes.
- Release zip scan passes after a fresh package build.
- GitHub Actions are green for the branch state being reviewed.

Status: planned.

## v0.65 - Final Sign-Off Gate

Goal:
- Convert v0.61-v0.64 evidence into a final human-readable review report and release decision.

Not in scope:
- Tagging, releasing, or merging without explicit confirmation.

Acceptance:
- Final report lists automated pass/fail evidence and manual-required items.
- Z.AI/API, GUI feel, long bubble, and multi-monitor items are either signed off with evidence or explicitly left as manual required.

Status: planned.

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

Status: completed.

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

Status: completed.

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

Status: integrated.

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

Status: integrated.

## v0.47 - Action Asset Pack Integration

Goal:
- Add structured support for richer action asset packs.

Not in scope:
- Shipping unauthorized assets.

Acceptance:
- Asset pack manifests validate.
- Missing assets fall back.
- Placeholder mode still works.

Status: integrated.

## v0.48 - Release Candidate

Goal:
- Freeze major behavior and run full regression.

Not in scope:
- New feature expansion.

Acceptance:
- Tests pass.
- Startup, settings center, action fallback, data fallback, and no-API fallback pass.

Status: accepted.

## v0.49 - Public Release

Goal:
- Publish the final public release package.

Not in scope:
- Unreviewed new features.

Acceptance:
- Release checklist is complete.
- No secrets, private assets, models, runtime data, or unauthorized assets are included.

Status: historical public release baseline.
