# Settings Center

The v0.42 settings center is opened from the desktop pet right-click menu:

```text
对话 -> 设置中心
```

It is an operational panel for the current local desktop pet. It does not replace the main `PetWindow`, does not edit `lore.md`, and does not introduce v0.45 multi-provider model architecture.

## Pages

- 模型与引擎: Provider metadata, API connection tests, local fallback, local-model services, and model switching.
- 桌宠: size, input visibility, always-on-top, opacity, idle behavior, hourly chime, edge peek, and day/night mode.
- 角色与资源: character switching, action preview, character-pack summary, validation, and guarded editing.
- 关系与事件: relationship state, memory memo, event history, export, reset, and clear controls.
- 记忆与日记: opt-in conversation memory, top-k retrieval limits, visible records, manual Provider diary generation, and independent clear controls.
- 系统: runtime data, backup, first-run wizard, and help.
- 提醒: reminder service and natural-language reminder recognition.
- 文件整理: explicit enable switch, preview launcher, current state, and safe-default reset.
- 系统状态: low-frequency local checks, thresholds, current state, one-shot local test, and safe-default reset.
- 剪贴板: text-only interaction, local sensitive-content blocking, state clearing, local filter test, and privacy-default reset.
- 专注模式: manual/automatic focus controls, suppression options, current state, exit, and default reset.
- 隐私与安全: local-data boundary summary and one-click shutdown for high-risk optional features.
- 诊断: character validation, API config, manifest, action resources, writable data directory, and gitignore safety checks.

v0.66 organizes these controls into separate pages without changing the existing configuration keys or enabling high-risk features by default.

v0.83 adds the Memory And Diary page. Both features remain disabled by default and store records only under ignored runtime `data/`.

## Safety Rules

- API keys are written to `.env`; they are not stored in tracked config files.
- YAML edits are backed up to `backups/` before save.
- Character pack validation runs after YAML save.
- Invalid YAML or failed validation is rejected and rolled back.
- Relationship reset backs up the old state first.
- `data/`, `data/daniya_relation/`, `.env`, `assets/private/`, `models/`, `backups/`, `dist/`, and `build/` must remain untracked.

## Non-Goals

v0.42 does not add:

- multi-model Provider backend
- local model downloader
- TTS
- Vision
- YAML editing for `lore.md`
- action asset generation
- main UI rewrite
