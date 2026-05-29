# Settings Center

The v0.42 settings center is opened from the desktop pet right-click menu:

```text
对话 -> 设置中心
```

It is an operational panel for the current local desktop pet. It does not replace the main `PetWindow`, does not edit `lore.md`, and does not introduce v0.45 multi-provider model architecture.

## Pages

- API / 模型: DeepSeek-compatible provider metadata, base URL, model, local fallback switch, API key save to `.env`, and non-blocking connection test.
- 桌宠: pet size, always-on-top, opacity, idle chat, idle interval, hourly chime, reminders, and day/night mode.
- 动作资源: current asset source, manifest status, action frame/fallback status, reload, and test action.
- 角色包: current `characters/daniya/` status and safe editing for `character.yaml`, `speech.yaml`, `relationship.yaml`, and `events.yaml`.
- 关系状态: current `relationship_state.json`, export, and backup-before-reset.
- 事件: read-only recent `event_log.json` entries.
- 数据: `data/daniya_relation/` readability, backup export, and open data directory.
- 诊断: character validation, API config, manifest, action resources, writable data directory, and gitignore safety checks.

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
