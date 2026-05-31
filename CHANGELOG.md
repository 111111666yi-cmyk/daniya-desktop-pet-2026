# Changelog

## v0.57 (2026-05-31) - Release Freeze QA Checklist

- Added the manual QA matrix for startup, GUI, API, Daniya character behavior, hidden commands, behavior engine states, packaging, and release smoke checks.
- Added the release freeze checklist that blocks future-stage feature work and makes P0/P1/P2 handling explicit before v0.58.
- Reaffirmed that manual acceptance must use temporary runtime state or documented human evidence instead of destructive scripts that touch real `data/`.

## v0.56 (2026-05-31) - Runtime Data Safety Hardening

- Tightened destructive-test policy so `backups/` is also treated as protected runtime state.
- Aligned runtime backup/restore tooling with the v0.56 policy: explicit backup directories, `BACKUP_MANIFEST.json`, pre-restore copies, and no automatic restore from an implicit latest backup.
- Restricted `models/` backups to small metadata files and skipped model body extensions such as `.gguf`, `.safetensors`, `.bin`, `.pt`, and `.onnx`.
- Verified backup/restore behavior in a temporary sandbox without touching real ignored user runtime data.

## v0.55.3 (2026-05-31) - AppData Runtime Patch

- Packaged Windows exe now stores runtime state in `%APPDATA%\DaniyaSummerPet\` instead of the exe directory.
- First-run files such as `config/app_config.json`, `config/api_config.json`, `.env`, `data/`, `data/window_state.json`, relationship state, notes, reminders, and backups no longer require write permission in the install/extract directory.
- Resource loading still reads bundled `config/`, `characters/`, `assets/`, and docs from the release package, with AppData overrides supported when present.
- Added runtime path regression tests that simulate frozen PyInstaller execution and verify no `config/` or `data/` directories are created beside the exe.

## Unreleased - Second Phase Dynamic Audit

- Hardened `pack.bat` packaging safety by replacing whole-directory `config/` and `docs/` copying with temporary public whitelist package inputs.
- Verified the v0.55.2 release package, dist folder, and zip do not contain `.env`, ignored local config, runtime `data/`, private assets, local models, or local audit screenshots.
- Ran second-stage dynamic startup, API fallback/API source, GUI, role-routing, hidden-command, behavior, state, timer, character-pack, pytest, and release exe smoke checks.
- Confirmed FA-PKG-001 and FA-PKG-002 are fixed; FA-STATE-001 and FA-TIMER-001 remain watch items because no stable conflict was reproduced.
- Confirmed `characters/test_dummy/` is local-only, ignored, not required by clean clone, and not included in formal regression or release packages.
- Added v0.56 destructive-test guardrails with runtime-state backup/restore tooling and a documented policy for future missing-file/fallback tests.

## v0.55.2 (2026-05-31) - Engineering Audit Patch

- Fixed `reminder_due` event routing so ordinary user requests such as “晚安，顺便提醒我明天喝水” are no longer treated as an already-due reminder event.
- Added local `/pet ...` command handling for status, reload, event, sleep, and wake commands so hidden commands do not fall through to the misleading weekly-advance response.
- Tightened `pack.bat` character packaging to include only public Daniya YAML/lore files and the public template pack, preventing ignored character asset folders from entering release builds.
- Synchronized version metadata and package naming to `v0.55.2`.

## v0.55.1 (2026-05-31) - Drag and Snap Bugfix Patch

- **Fixed Edge-Lock Bug**: Resolved a critical issue where the pet would snap to the screen edges and get locked, refusing to be dragged back to the center of the screen.
- **Removed Polling Timer Release Checks**: Eliminated the redundant win32 `GetAsyncKeyState` polling inside the 80ms `_tick_global_click` timer, which prematurely aborted active drags in laggy or high-DPI environments.
- **Enhanced Safe Interacting Check**: Added `is_pressed` flags to track raw mouse click states. Upgraded `_tick_edge_peek` to intercept snapping when the user is actively dragging, pressing, context-menu viewing, or when the `SnapController` animation is running.
- **Fixed Activity Detected Signal Crash**: Resolved a `TypeError: native Qt signal instance 'activity_detected' is not callable` bug in `behavior_engine.py` when executing native PySide6 signals.
- **Verified with Automated OS Simulation**: Added `scratch/physical_mouse_simulation.py` to simulate actual Windows mouse events and verify correct docking and pull-away behavior.

## v0.55 - Behavior Engine & Advanced Interaction Layer

- **Added Behavior Engine (PetBehaviorEngine)**: Introduced a coordinator engine for desktop pet physics and high-level interaction tracking.
- **Improved Interaction Classification**: Handled single click ("clicked"), double click ("happy"), and dragging ("drag") via `InteractionDetector` to prevent conflicts between movement and clicking.
- **Implemented Edge Snapping & Screen Boundaries**: Snaps the pet window to left, right, and bottom screen boundaries when released within a 24px range. Ensures at least 32px of the pet remains on-screen.
- **Implemented Elastic Bounce Animation**: Smoothly bounces the window to boundaries or safe limits using `QPropertyAnimation`.
- **Added Position Persistence**: Saves positions and snapping states to `data/window_state.json` on drag completion and application shutdown, and restores it on startup.
- **Lightweight Idle Behavior**: Triggers small movements or dialogue bubbles if the user is inactive for 90s, with cooling periods to avoid spamming.

## v0.54 - Dialogue Router & Lore Triggers

- **Implemented Dialogue Router**: Categorized user inputs into Command, Emotion, Task, Story, and Chat to handle different routing pathways.
- **Prevented Keyword Interception**: Normal conversational inputs containing emotional keywords (e.g. "累", "抱抱") are now routed to the LLM instead of being intercepted by static response matchers.
- **Story Trigger Divergence**: Lore queries related to Daniya's backstory bypass static responses and invoke the LLM with relevant lore fragments.

## v0.51 - Post-Release Patches

- **Fixed Packaging Resource Path (Issue #2 & #10)**: Bundled and copied `assets/icons/` SVG files in `pack.bat`, ensuring that SettingsWindow icons are displayed correctly in the packaged standalone executable.
- **Fixed Packaged Startup Crash (Issue #1 & #2)**: Improved `character_pack_path()` in `core/character_loader.py` to check for specific subfolders (like `characters/daniya`) instead of only checking the root directory, preventing startup failures if an empty external `characters/` folder is present.
- **Improved Settings Saving Resilience (Issue #3)**: Wrapped atomic file replacements with try-except blocks in `ConfigManager.save_json()` and `SettingsManager._save_json_atomic()`, falling back to direct file writing to prevent GUI crashes due to Windows file locking.
- **Fixed API Key Retrieval Safety (Issue #4)**: Added empty/falsy check for `env_key_name` in `SettingsManager.current_api_key()` to prevent potential OS-specific errors.
- **Fixed Local Fallback Message (Issue #5)**: Corrected `missing_key` flag passing in `ChatClient.reply()` when `local_mode` is enabled, so it displays the friendly offline prompt rather than connection failure error message.
- **Fixed Action Manifest Fallback (Issue #6)**: Enhanced `ActionManifest._verify_frames()` to automatically fall back to public placeholder assets via `resource_path` if custom/private frames are missing, avoiding broken image rendering issues.
- **Fixed Settings Event Log Loading (Issue #8)**: Updated `RelationshipStateViewer.status()` to load event records using `load_event_log()`, enabling compatibility with the new JSONL event logging format (`event_log.jsonl`).

## v0.50 - Official Open Source Release (Stable)

- **Completed v0.50 Release**: Confirmed stable release status, containing all features from v0.49.1 settings layout updates and UI dialog improvements.

## v0.49.1 - Settings Optimization & Window Controls Patch

- **Window Control Enhancement**: Added window minimize/maximize flags (`Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint`) to SettingsWindow, DaniyaSettingsDialog, HistoryDialog, FirstRunWizard, and the model downloader dialog.
- **Tab Consolidation**: Unified settings panels by merging `API / 模型` and `本地模型` into `模型与引擎` tab, and merging `关系与事件` and `系统` into a scrollable `数据与系统` tab to optimize page real-estate and user flow.
- **Local Model Auto-Activation**: Implemented `save_and_activate_local_model_profile` to automatically switch and activate local model profiles upon saving, resolving configuration sync conflicts.
- **Test Encoding Resilience**: Fixed CP936/UTF-8 console decoding timeout issues on Windows in subprocess tests by using Unicode escapes for non-ASCII tab names.

## v0.49 - Official Open Source Release

- Prepared the official open source release.
- Updated project version metadata to `v0.49`.
- Generated the formal Windows package name `DaniyaSummerPet-v0.49-win-x64`.
- Prepared GitHub Release Notes for the public release.
- Confirmed sensitive files must not enter the release package.
- Confirmed v0.48 blocking issues are clear based on the RC report.
- Preserved known non-blocking issue handling for the release notes.

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
