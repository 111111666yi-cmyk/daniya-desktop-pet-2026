# Changelog

## v0.43 - GitHub Open Source Cleanup

- Organized the repository for public GitHub use.
- Expanded `.gitignore` for secrets, runtime data, private assets, models, backups, build output, Python cache files, logs, and editor files.
- Updated README with project scope, install/run instructions, no-API fallback, asset policy, character pack policy, settings center overview, data directory rules, roadmap, and license note.
- Added or updated `AGENTS.md`, `CONTRIBUTING.md`, `docs/asset_policy.md`, `docs/roadmap.md`, `docs/dev_workflow.md`, and `docs/release_checklist.md`.
- Documented that `.env`, `data/`, `data/daniya_relation/`, `assets/private/`, `models/`, and generated build output must not enter Git.
- Kept `characters/template/` as the public character template.
- Documented `characters/daniya/` as the public example character pack strategy.
- Included v0.415 and v0.42 docs and reports in the open source documentation set.
- Removed tracked runtime `data/.gitkeep` from Git tracking without deleting the local file.
- Did not package an exe.
- Did not publish a Release.
- Did not enter the v0.45 multi-model Provider stage.

## v0.42 - Settings Center

- Added the settings center for API, pet, action resources, character pack status, relationship state, data, and diagnostics.
- Added safe YAML editing with backup and validation.
- Added relationship state export and backup-protected reset.

## v0.415 - Daniya Character Pack And Relationship Engine

- Added Daniya character pack files.
- Added schema, loader, validator, special response matcher, speech filter, dialogue engine, relationship state, event memory, action routing, lore retrieval, and read-only Daniya settings window.

## v0.41 - Action Resource System

- Integrated action resource loading and fallback behavior for desktop pet animation states.
