# ARCHITECTURE_RISK_MAP

审计阶段：第一阶段，只读静态审计
基准提交：`db7af9b`

## 总览

最高风险区域：

1. 打包链路：Git ignore 与 pack copy 白名单不一致。
2. 状态链路：动作、事件、行为、提醒、昼夜、idle 均可影响 UI/动作状态。
3. Timer 链路：多个 QTimer 与 QPropertyAnimation 并行。
4. 配置链路：tracked 默认配置与运行态配置仍有混用。

## API 链路

静态链路：

`ChatClient.reply()` -> `ProviderManager.chat()` -> `deepseek_api/openai_api/anthropic_api/ollama_api`

证据：

- `src/chat_client.py` 使用 `ProviderManager`。
- `src/llm/provider_manager.py` 从 `.env` 读取 key，不直接硬编码。
- `src/llm/boundaries/*` 使用 timeout 与 typed errors。

风险：

- 真实网络、错误 key、错误 model、timeout 未在第一阶段运行。
- `SettingsWindow` API test worker 需动态确认不冻结 UI。

## 角色链路

静态链路：

`AppController` -> `DaniyaEngineAdapter` -> `safe_load_character/load_character` -> `CharacterPack`

证据：

- `characters/daniya`, `characters/template`, `characters/test_dummy` 本地均可校验。
- `current_character` 存在于 `config/app_config.json`。

风险：

- `characters/test_dummy/` 未跟踪。
- `characters/*/assets/` 默认忽略，只允许 template assets。

## 事件链路

静态链路：

`DialogueEngine.handle()` -> `match_event()` / special response / hidden command -> relationship/memory/action

证据：

- `core/dialogue_engine.py` 含 `_pet_command_event()`。
- `core/event_engine.py` 使用 keyword matching。
- `core/special_response_matcher.py` 含 normalize/match。

风险：

- 情绪短句 + 任务请求是否误吞必须动态验证。
- sleep/random/cooldown/pending event 未在第一阶段执行。

## 动作链路

静态链路：

`ActionRouter` -> `ThreadSafeAnimationManager` -> `AnimationManager` -> `StateManager` -> `ActionManifest` -> `AssetManager`

风险：

- 多模块可触发 `clicked/happy/remind/sleep/drag/idle`。
- manifest 损坏、图片损坏、尺寸不一未动态验证。

## 行为链路

静态链路：

`PetAvatar` mouse signals -> `InteractionDetector` -> `PetBehaviorEngine` -> `DragController/SnapController/IdleBehavior`

风险：

- 单击/双击/长按/拖拽误判需要动态测试。
- `SnapController` 写 `data/window_state.json`，需损坏文件测试。

## 配置链路

静态链路：

`ConfigManager` 处理 app/profile/system/bookmarks；`SettingsManager` 处理 api/model/multimodal。

风险：

- `config/app_config.json` tracked 且可写。
- `config/api_config.json` ignored 但可能被打包复制。
- `config/multimodal_config.json` ignored 但可能被打包复制。

## 数据链路

静态链路：

`HistoryManager`, `AffinityManager`, `NotesManager`, `ReminderManager`, `memory_engine`, `relationship_engine`, `SnapController`

风险：

- data 损坏/坏行/权限只读未在第一阶段测试。
- relation data 路径支持 `DANIYA_RELATION_DATA_DIR`，测试需隔离真实 data。

## 打包链路

静态链路：

`pack.bat` -> PyInstaller `--add-data` -> robocopy release -> cleanup -> zip

风险：

- P1：整体复制 `config/`。
- P2：整体复制 `docs/`。
- 本地 release 旧版本存在，人工审计需避免混淆。

## GitHub 发布链路

证据：

- README/LICENSE/CONTRIBUTING/CHANGELOG/docs 存在。
- `.gitignore` 覆盖敏感/运行态/构建产物。

风险：

- `characters/test_dummy/` 已在 v0.56 确认为 local-only，不进入正式回归或 release。
- 发布前必须重新执行 `git status`, `git ls-files` 和 zip 内容检查。
