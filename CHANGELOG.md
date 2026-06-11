# Changelog

## v0.82 (2026-06-12) - Environment Awareness

- Added opt-in Open-Meteo weather reads on a background thread, with user-confirmed coordinates and rain reminders.
- Added privacy-limited media presence detection that checks only an allow-list of player process names and never reads titles, lyrics, or file paths.
- Added low-frequency, character-pack-driven ambient event theater with focus-mode suppression and manual preview.
- Added a generated transparent umbrella asset and synchronized packaging/release checks.

## v0.81 (2026-06-12) - Local Growth

- Added an opt-in, pure-local growth center with coins, daily supplies, inventory, feeding, levels, outfits, and affinity-gated unlocks.
- Added public `items.json` and `outfits.json` character-pack catalogs for Daniya and the template pack.
- Stored all user growth state under ignored `data/growth_state.json`; no growth data is sent to Providers or included in release archives.
- Added settings and context-menu entry points while keeping the feature disabled by default.

## v0.80.1 (2026-06-12) - Cinematic Story Hotfix

- Integrated the cinematic liquid-glass 24-chapter story site from `eee9816`.
- Routed the desktop pet's existing Story command to a loopback-only local web server and the user's default browser.
- Kept the legacy Qt chapter dialog as a fallback when the packaged web files or browser launch are unavailable.
- Added the story HTML and background video to Windows packaging and release ZIP validation.
- Did not import the unrelated TTS, voice-pack, streaming, or legacy settings changes from the source feature branches.

## v0.80 (2026-06-11) - Stable Integration Candidate

- Integrated the independently verified v0.75 character-routing, v0.76 runtime-reliability, v0.77 window-interaction, and v0.7x settings/profile backfill stages.
- Unified source version, public config seeds, package name, release scanner, README, known issues, release checklist, and v0.80 acceptance documents.
- Kept true LLM streaming deferred and preserved TTS interfaces without adding TTS execution behavior.
- Added v0.80 package requirements for versioned config, acceptance documents, story assets, private/runtime/model exclusions, secrets, and local-path scans.
- Avoided native screen enumeration on Qt offscreen/minimal platforms, preventing a Windows CI heap crash while keeping real-screen enumeration unchanged in production.
- Kept real Provider, second physical mixed-DPI monitor, physical mouse feel, SmartScreen, antivirus, and code-signing results explicitly manual or environment-specific.

## v0.7x Backfill (2026-06-11) - Settings And Profile Safety

- Added a persistent simple/advanced Settings Center display mode that hides advanced pages and groups without resetting existing values.
- Kept common Provider, character, pet, reminder, privacy, profile, memory, and voice-status entry points in the default simple mode.
- Added an optional month-day birthday profile field, preserved unknown legacy profile fields, and exposed the profile in Settings Center.
- Added profile and relationship-state migration regression tests.
- Deferred true LLM streaming after documenting that the current Provider, speech-filter, bubble, history, fallback, and voice contracts are final-response only.

## v0.77 (2026-06-11) - Window Interaction Hardening

- Replaced virtual-desktop bounding-box clamping with real per-screen geometry selection, including negative coordinates, gaps, and screens above or below the primary display.
- Added screen and logical-DPI change repair so cached pixmaps refresh and saved positions return to a visible screen after monitor changes.
- Made snap, rebound, and edge-peek calculations use the pet's active screen; fast drags use a shorter bounded rebound animation.
- Fixed input focus detection and immediately released edge peek when input, Settings Center, focus mode, or the disabled feature requires a quiet state.
- Kept reminder dialogs temporarily topmost without permanently changing the user's pet topmost setting.
- Added multi-monitor geometry, snap, drag-state, DPI-layout, and interaction-guard tests plus a manual physical-mouse checklist.

## v0.76 (2026-06-11) - Runtime Reliability

- Added diagnostic-only timing for all cold-start stages without recording keys or local paths.
- Deferred optional services and Settings Center runtime data until after first show or the relevant tab opens.
- Prevented disabled idle, time-event, edge, click, walk, and behavior timers from polling in the background.
- Bounded history and relationship event logs, added recent-record tail reads, and skipped incomplete JSONL records safely.
- Unified config, setup, relationship, memory, reminder, and history replacements on atomic temporary-file writes.
- Added isolated startup, runtime recovery, and finite long-run tools; the stress check performs no network requests and keeps 30-minute/GDI checks explicitly manual.

## v0.75 (2026-06-11) - Character Experience Polish

- Kept the five required Daniya trigger phrases stable for exact and normalized input.
- Prevented trigger words embedded in technical questions or reminder requests from writing relationship events, injecting lore, or selecting emotion actions.
- Added a technical response mode that preserves long explanations, transition words, Markdown tables, code blocks, and stack traces.
- Replaced silent companion-response hard cuts with boundary-aware shortening, a short closing line, and an audit log entry.
- Added dedicated trigger, speech-filter, and routing-precedence regression suites.

## v0.70 (2026-06-05) - Integration Acceptance

- Froze feature development after v0.69 and moved the project into full v0.61-v0.70 acceptance.
- Unified public version, package, installation, release-check, known-issue, and QA documentation for the v0.70 source milestone.
- Added packaged-content requirements for the v0.70 automated acceptance report and manual QA checklist.
- Fixed edge-peek drag completion so Settings Center, active speech, input, and focus-mode pauses cannot leave a half-hidden window with an empty dock state.
- Replaced the undeclared optional `pywin32` hidden-file check with the Windows API through `ctypes`, keeping file-organizer privacy behavior consistent between local and GitHub builds.
- Serialized relationship and memory file access and switched state replacement to atomic temporary files, preventing concurrent readers from treating an in-progress write as corrupt user data.
- Serialized dialogue-engine transactions and routed physical-event state changes through the thread-safe animation bridge instead of touching the Qt window from a worker.
- Hardened file organization against sensitive roots, hidden paths, duplicate preview destinations, post-preview collisions, and tampered execution plans.
- Removed process-wide socket timeout mutation, guarded Windows-native click probing on other platforms, narrowed overly broad story keywords, and persisted the initial reminder notification state explicitly.
- Re-ran repository checks, 312 tests, isolated source startup, Windows packaging, zip scanning, packaged-executable interaction QA, virtual mixed-DPI regression checks, SmartScreen observation, and local antivirus invocation.

## v0.69 (2026-06-05) - Character Pack Stability

- Added public character discovery that ignores hidden folders, invalid folders, and the local-only `test_dummy` pack.
- Isolated relationship state by character while preserving the legacy `relationship_state.json` path for Daniya and migrating legacy foreign-character state safely.
- Changed hot reload to persist the character that actually loaded after fallback, without replacing long-lived reminder, idle, event, or feedback managers.
- Added regression coverage for missing lore, missing or invalid story data, manifest/action fallback, character discovery, resolved-character persistence, and per-character relationship state.

## v0.68 (2026-06-05) - Feedback Coordination

- Added one coordinator for non-essential bubbles, character actions, optional sound hooks, completion, and cooldown handling.
- Prevented idle chat, hourly chimes, system alerts, clipboard notices, and idle-behavior bubbles from interrupting dragging, active input, existing speech, Settings Center work, or focus-mode suppression.
- Kept user-initiated chat, reminder confirmation, clicks, and important due reminders on their existing immediate-response paths.
- Added regression coverage for overlap prevention, interaction guards, focus-specific suppression, cooldown, wiring, and return-to-idle behavior.

## v0.67 (2026-06-05) - Daniya Character Experience Regression

- Moved reminder, file organizer, clipboard, system-status, and focus-mode character copy into each character pack's `speech.yaml`.
- Replaced engineering-facing and overly playful utility messages with concise Daniya-style wording that avoids meta language and does not obscure the user's task.
- Added regression tests for character-pack utility copy, neutral template fallback, sensitive clipboard wording, system alerts, reminders, and connection fallback.

## v0.66 (2026-06-05) - Unified Settings Center

- Reorganized the Settings Center into twelve focused pages: models, pet, character resources, relationships, system, reminders, file organizer, system status, clipboard, focus mode, privacy, and diagnostics.
- Added visible state summaries and restore-default actions for the v0.61-v0.65 user-facing controls.
- Kept file organization, system monitoring, clipboard interaction, focus mode, and other high-risk behavior disabled by default.

## v0.65.2 (2026-06-05) - Acceptance Package Revision

- Aligned the application version, public configuration templates, documentation, tag, and Windows package name on `v0.65.2`.
- Rebuilt the Windows package from the accepted v0.65 code state without adding v0.66 features or changing product behavior.
- Re-ran the full repository, package-content, and packaged-executable verification gates before publishing the source tag.

## v0.65.1 (2026-06-05) - Manual Acceptance Hotfix

- Passed local simulated mouse acceptance for the v0.65 desktop flows: startup, quiet defaults, input toggle, edge peek, Provider status, file organizer preview, focus mode, persistence, and basic UI stability.
- Fixed the real drag/snap path so left and right edge peek stays half-hidden after render-frame clamping.
- File organizer previews now record skipped sensitive directories such as `assets/private` instead of silently omitting them from the audit result.
- Restored the public runtime default `window.show_input=false` so first launch remains quiet and CI public-surface checks stay green.

## Unreleased - v0.62-v0.65 Recovery Wiring

- Fixed the hidden input bar recovery path: when `window.show_input=false` hides the parent `InputBar`, enabling it from Settings now restores the whole widget and expands the editable field.
- Restored left/right edge peek positioning so the pet can cling partly off-screen again when the setting is enabled, while keeping the release default quiet.
- Changed the Provider status banner so local fallback and real cloud connectivity are no longer reported as a green active/PASS state without a successful connection test.
- Added Settings Center controls and runtime wiring for the v0.62-v0.65 preview features: file organizer preview, system status, clipboard interaction, and focus/game mode.
- Restored the public v0.56-v0.60 summary in `VERSION_LOG.md`; internal audit logs remain outside the public docs surface.

## v0.65 (2026-06-03) - Focus and Game Mode

- Added `src/focus_mode.py` coordinating manual focus states and local process game whitelist matching for automated silencing.
- Integrated event suppression checks to prevent idle popups, chimes, and non-essential alert signals from executing when focus is active.
- Added focus mode documentation `docs/focus_mode.md`.
- Added tests `tests/test_focus_mode.py` verifying manual state changes, process iteration matching, automatic entry and exit, and state transition signals.

## v0.64 (2026-06-03) - Privacy-Safe Clipboard Interaction

- Added `src/clipboard_interaction.py` supporting PySide6 QClipboard data listening, local regular expression filtering of API keys, Bearer tokens, credentials, phone numbers, and ID cards.
- Integrated text length bounds to prevent automatic transmission of texts over 1000 characters without explicit confirmation.
- Added clipboard privacy documentation `docs/clipboard_privacy.md`.
- Added tests `tests/test_clipboard_interaction.py` verifying sensitive token blocking, mobile and ID filtering, length truncation thresholds, duplicate detection, and disabled status checks.

## v0.63 (2026-06-03) - System Status Awareness

- Added `src/system_status.py` providing low-overhead local hardware (CPU, Memory, Battery, Disk) and network connection checks.
- Integrated time-based alert cooldown logic (default 300s) to prevent bubble alert notification flooding.
- Added system status documentation `docs/system_status.md`.
- Added tests `tests/test_system_status.py` verifying high CPU load alerts, high memory alerts, discharging low battery alerts, offline network status, alert silencing when disabled, and cooldown behavior.

## v0.62 (2026-06-03) - Safe File Organizer Assistant

- Added `src/file_organizer.py` supporting dry-run previews, duplicate file renaming, and rollback mapping.
- Implemented folder pruning to bypass `.git`, `.venv`, `models`, `backups`, and `.env` files automatically.
- Added file organizer documentation `docs/file_organizer.md`.
- Added tests `tests/test_file_organizer.py` verifying empty structures, renaming collision avoidance, folder pruning, dry-runs, move execution, and rollback/undo capabilities.

## v0.62 (2026-06-03) - Memory Control, Provider Memory Injection, and Z.AI Provider

- Added a visible Settings Center action to clear automatic memory and manual memory notes without resetting relationship state.
- Verified Provider prompt construction keeps profile and memory memo context before all text Provider channels.
- Added support for Z.AI standard Provider (GLM-5.1, `https://api.z.ai/api/paas/v4`, `ZAI_API_KEY`) following standard developer guidelines.

## v0.61 (2026-06-03) - Natural Language Reminder System

- Added `src/natural_reminder_parser.py` supporting rules-based extraction of Chinese relative, absolute, and recurring time expressions.
- Added `src/natural_reminder_service.py` to bridge natural language inputs with `ReminderManager`.
- Wired natural language reminder processing into `AppController.send_message` main chat input processing pipeline.
- Hardened natural language reminder controls by adding the `natural_reminder_enabled` configuration switch (defaulting to `true`).
- Ensured that when `natural_reminder_enabled` is set to `false`, the natural reminder service and any pending confirmation states are bypassed entirely, falling back cleanly to standard LLM chat.
- Added natural language reminders documentation `docs/natural_reminders.md`.
- Added integration tests `tests/test_natural_reminder_wiring.py` covering relative, absolute, recurring, ambiguous confirmation flows, cancellation, and switch-disabled fallback behaviors.

## v0.61 (2026-06-03) - Quiet Defaults and Public Surface Audit

- Made the default desktop pet experience quieter: idle chat, hourly chime, edge peek, and idle behavior are disabled by default, while user settings can still enable them.
- Raised the idle behavior lower bound to 600 seconds so enabling it does not create high-frequency unexpected movement.
- Added a public-surface audit check for forbidden character copy, local user paths, template repository URLs, quiet default settings, and visible memory controls.
- Cleaned the README clone instructions to use the actual public repository URL.

## v0.60 Release Blocker Fix (2026-06-02)

- Fixed the v0.60 release package story asset gap by adding `characters/daniya/story.yaml` to `pack.bat`; `characters/template/story.yaml` remains included through the public template package.
- Tightened release zip scanning so the package must contain both story files and must not contain Daniya private assets, local user paths, forbidden runtime directories, or obvious API keys.
- Ignored local audit report documents with `*_audit_report.docx` so `DaniyaSummerPet_v0.60_audit_report.docx` cannot be accidentally committed or packaged.
- Sanitized historical docs that contained local `<local-user-path>` references while keeping the original audit content.
- Kept `config/model_profiles.json` aligned with the v0.60 text profile history structure; removed unrelated runtime `config/app_config.json` noise and aligned public fallback reply arrays.

## v0.60 Stable Preview

- Consolidates the v0.56-v0.60 hardening series into a stable public preview baseline.
- Includes runtime data safety policy and backup/restore tooling, safer release packaging, first-run onboarding, manual QA freeze checklists, local automated checks, and GitHub Actions preparation.
- Keeps known non-blocking issues documented instead of changing state machines or Timer logic without reproduction evidence.
- Prepares the final Windows package name `DaniyaSummerPet-v0.60-win-x64.zip`.

## v0.59 (2026-05-31) - Automated Checks and CI Preparation

- Added local project checks for sensitive tracked paths, release zip safety, required character packs, config templates, and local documentation links.
- Added Windows GitHub Actions for test and manual release package verification without requiring real API keys, private assets, or `characters/test_dummy/`.
- Added bug report, feature request, and pull request templates for safer open source collaboration.

## v0.58 (2026-05-31) - First-Run Onboarding Flow

- Reworked the existing first-run dialog into a five-page onboarding guide covering welcome, API setup, private assets, character packs, and final startup.
- Moved the canonical completion marker to `data/first_run_done.json` while keeping old `config/setup_config.json` compatibility.
- Added a Settings Center entry to reopen the first-run guide without clearing existing settings.
- Removed future-feature onboarding toggles for TTS, image, and video so v0.58 stays within the no-new-capability freeze rules.

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
