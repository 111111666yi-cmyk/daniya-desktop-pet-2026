# FULL_AUDIT v0.1-v0.55

审计阶段：第一阶段，只读静态审计
审计时间：2026-05-31 16:58 +08:00
基准提交：`db7af9b chore: audit and stabilize v0.55.2`

## 0. 范围声明

本文件只记录第一阶段静态审计结论。

本阶段已执行：

- 文件结构检查
- Git 跟踪/忽略检查
- Python / pip 版本读取
- 配置 JSON/YAML UTF-8 解析检查
- 角色包静态校验
- `src/`、`core/` AST 模块索引
- QTimer / Signal / QThread / 文件读写 / API 调用静态扫描
- `pack.bat`、`run.bat`、`.gitignore` 静态审计

本阶段未执行：

- 未启动 `run.bat`
- 未启动 GUI
- 未执行四类 `.env` 环境启动测试
- 未执行 `pack.bat`
- 未执行 exe 冒烟
- 未执行多显示器测试
- 未修改任何代码

动态项目在 `FULL_REGRESSION_TEST_v0.1-v0.55.md` 中标为 `Blocked` 或 `Not Run - Phase 1`。

## 1. 项目是否能启动

结论：第一阶段不直接运行启动链路，状态为 `Not Run - Phase 1`。

静态证据：

- `main.py` 存在，内容为 `from src.app import run` 并执行 `run()`。
- `run.bat` 存在，使用 `.venv\Scripts\pythonw.exe main.py` detached 启动。
- `src/app.py` 存在 `run()`，创建 `QApplication`、首启向导、`AppController` 并进入 `app.exec()`。

风险：

- `run.bat` 是 detached 启动，脚本自身无法直接反映 GUI 是否初始化成功。
- 真实启动必须在第二阶段按 `.env` 四类环境执行。

## 2. Python 与依赖

证据：

- `python --version`: `Python 3.10.11`
- `.venv\Scripts\python.exe --version`: `Python 3.10.11`
- `.venv\Scripts\pip.exe --version`: `pip 26.1.1`
- `requirements.txt` 包含：`PySide6`、`Pillow`、`requests`、`python-dotenv`、`pyinstaller`、`psutil`、`pyperclip`、`PyYAML`、`pytest`

结论：静态依赖文件存在；依赖安装完整性未在第一阶段重新安装验证。

## 3. 文件结构审计

检查项全部存在：

| 路径 | 结果 |
|---|---|
| `main.py` | 存在 |
| `requirements.txt` | 存在 |
| `install.bat` | 存在 |
| `run.bat` | 存在 |
| `pack.bat` | 存在 |
| `README.md` | 存在 |
| `LICENSE` | 存在 |
| `AGENTS.md` | 存在 |
| `CONTRIBUTING.md` | 存在 |
| `CHANGELOG.md` | 存在 |
| `.env.example` | 存在 |
| `.gitignore` | 存在 |
| `src/` | 存在 |
| `core/` | 存在 |
| `config/` | 存在 |
| `data/` | 本地存在，Git 忽略 |
| `assets/` | 存在 |
| `characters/` | 存在 |
| `docs/` | 存在 |

补充观察：

- 本地存在 `.env`、`data/`、`release/`、`build/`、`dist/`、`models/`、`scratch/`、`drag_debug.log` 等运行/构建产物，均由 `.gitignore` 覆盖。
- `characters/test_dummy/` 已在 v0.56 确认为 local-only，并由 `.gitignore` 忽略。

## 4. Git 状态与跟踪安全

证据：

- `git status --short`: v0.56 后不再显示 `characters/test_dummy/`
- `git ls-files .env data assets/private models backups dist build release config/api_config.json 'characters/*/assets/*'` 输出仅包含 `characters/template/assets/*`

结论：

- 敏感/运行目录未被 Git 跟踪。
- `characters/template/assets/*` 是有意允许的公开 placeholder fallback。
- `characters/test_dummy/` 不入仓；clean clone 不要求它存在。

## 5. 当前关键模块列表

静态 AST 统计：

- Git 跟踪文件数：223
- `src/` + `core/` Python 文件数：76
- `tests/` Python 文件数：37
- `docs/` 跟踪文件数：37

关键模块：

| 链路 | 主要文件 |
|---|---|
| 启动/UI 控制 | `main.py`, `src/app.py`, `src/pet_window.py`, `src/menu_manager.py` |
| UI 组件 | `src/ui/input_bar.py`, `src/ui/modern_bubble.py`, `src/ui/pet_avatar.py`, `src/ui/status_badge.py`, `src/ui/liquid_glass.py` |
| 行为引擎 | `src/behavior/behavior_engine.py`, `drag_controller.py`, `snap_controller.py`, `interaction_detector.py`, `idle_behavior.py` |
| 动作系统 | `src/action_manifest.py`, `src/animation_manager.py`, `src/asset_manager.py`, `src/state_manager.py`, `core/action_router.py` |
| 对话引擎 | `core/dialogue_engine.py`, `core/prompt_builder.py`, `core/speech_filter.py`, `src/daniya_engine_adapter.py`, `src/chat_client.py` |
| 角色系统 | `core/character_loader.py`, `src/character_pack_editor.py`, `characters/*` |
| 事件/记忆/关系 | `core/event_engine.py`, `core/memory_engine.py`, `core/relationship_engine.py`, `core/lore_retriever.py` |
| Provider | `src/llm/provider_manager.py`, `src/llm/provider_registry.py`, `src/llm/boundaries/*.py` |
| 设置中心 | `src/settings_window.py`, `src/settings_manager.py`, `src/config_manager.py` |
| 本地陪伴 | `src/history_manager.py`, `src/affinity_manager.py`, `src/reminder_manager.py`, `src/notes_manager.py`, `src/time_event_manager.py`, `src/day_night_manager.py`, `src/mini_games.py`, `src/bookmark_manager.py` |
| 打包发布 | `pack.bat`, `.gitignore`, `docs/release_checklist.md` |

## 6. 当前配置文件列表

解析检查结果：

| 文件 | 结果 |
|---|---|
| `config/app_config.json` | JSON OK |
| `config/api_config.json` | JSON OK，本地忽略文件 |
| `config/model_profiles.json` | JSON OK |
| `config/multimodal_config.json` | JSON OK，本地忽略文件 |
| `config/profile.json` | JSON OK |
| `config/system_prompt.txt` | UTF-8 OK |
| `.env.example` | UTF-8 OK |

风险：

- `config/app_config.json` 是跟踪文件，包含 `window.start_x/start_y` 与行为配置，容易被运行时改动造成工作树噪声。
- `config/api_config.json` 被 `.gitignore` 忽略，但 `pack.bat` 当前静态上会整体复制 `config/`，存在打包包含本地用户配置的风险。详见 `PATH_AND_PACKAGING_AUDIT.md`。

## 7. 当前角色包列表

发现角色包：

- `characters/daniya/`
- `characters/template/`
- `characters/test_dummy/`（local-only，可选）

校验命令：

- `python tools\validate_character_pack.py characters\daniya`: PASS
- `python tools\validate_character_pack.py characters\template`: PASS
- `python tools\validate_character_pack.py characters\test_dummy`: PASS(local-only，可选；正式回归不要求)

解析检查：

- `characters/daniya/` 与 `characters/template/` 的 `character.yaml`、`speech.yaml`、`relationship.yaml`、`events.yaml`、`actions.yaml`、`lore.md`、`lore_index.yaml` 均可 UTF-8/YAML 解析。
- `characters/test_dummy/` 本地存在时也可解析，但它是 local-only 可选测试包。

风险：

- `characters/test_dummy/` 已忽略，不参与正式回归或发布。
- `.gitignore` 忽略 `characters/*/assets/`，仅放行 `characters/template/assets/`。

## 8. 当前 data 文件列表

本地发现：

- `data/.gitkeep`
- `data/affinity.json`
- `data/chat_history.jsonl`
- `data/chat_history.jsonl.bak`
- `data/notes.txt`
- `data/reminders.json`
- `data/window_state.json`
- `data/daniya_relation/`

证据：

- `.gitignore` 覆盖 `data/` 和 `data/daniya_relation/`
- `git ls-files data` 无输出

结论：

- Git 安全状态合格。
- 文件损坏恢复、坏行跳过、只读权限等需要后续动态/破坏性 fallback 测试，第一阶段未执行。

## 9. 逐版本静态审计结果

| 版本范围 | 静态结论 | 风险 |
|---|---|---|
| v0.1/v0.10 | PySide6、透明窗口、拖拽、右键菜单、输入框、typewriter 相关模块存在 | 未做 GUI 启动，动态状态 Blocked |
| v0.2/v0.20 | `.env`、ProviderManager、ChatClient、fallback 代码存在 | `.env` 四环境未在本阶段执行 |
| v0.3/v0.30 | history/profile/affinity/notes/reminder/time/mini_games/bookmark 模块存在 | data 损坏测试未执行 |
| v0.41 | `ActionManifest`、`AnimationManager`、manifest fallback 存在 | manifest 损坏/缺图动态测试未执行 |
| v0.42 | `SettingsWindow`、`SettingsManager`、API key 写 `.env` 路径存在 | 设置中心 GUI 操作未执行 |
| v0.43 | README/LICENSE/AGENTS/CONTRIBUTING/CHANGELOG/docs/.gitignore 存在 | 安全静态通过，发布产物需后续动态检查 |
| v0.44 | `pack.bat` 存在且版本为 `v0.55.2` | P1：打包脚本静态上会复制整个 `config/`，可能带入 ignored 本地配置 |
| v0.45 | ProviderManager、DeepSeek/OpenAI/Claude/Ollama/OpenAI-compatible 配置存在 | Provider 切换动态测试未执行 |
| v0.46 | Ollama/LM Studio/llama.cpp 相关本地 provider 配置与本地 manager 存在 | 本地服务不可用场景未执行 |
| v0.47 | 私有素材忽略、placeholder/template assets 存在 | 私有素材本地缺失/打包排除需动态验证 |
| v0.48/v0.49 | 文档与 release checklist 存在，安全忽略规则存在 | 本地 `release/` 有旧 v0.44 残留，可能干扰人工判断 |
| v0.50/v0.51 | v0.51 审计/修复文档存在 | 需整合到本轮 full 报告 |
| v0.52 | speech/special response/relationship/lore/prompt 链路存在 | 需动态验证误吞任务 |
| v0.53 | daniya/template/test_dummy 本地存在并可解析 | `test_dummy` 未跟踪，仓库态不稳定 |
| v0.54 | `EventEngine`、hidden command、本地 `/pet` 命令存在 | 事件锁死/关键词地雷需动态路由测试 |
| v0.55 | behavior engine、drag/snap/idle/interaction detector 存在 | 多状态 owner 和多 QTimer 是静态高风险点 |

## 10. 逐模块审计结果

重点静态发现：

- `src/app.py` 同时连接 UI、worker、reminder、idle、behavior、animation，是最高耦合控制器。
- `src/pet_window.py` 同时持有 UI 组件、动画、行为引擎、托盘、鼠标行为，是状态冲突核心区域。
- `core/dialogue_engine.py` 同时处理 special response、event、command、prompt、relationship、memory，是输入路由核心区域。
- `src/settings_window.py` 超过多个功能区，含 API 测试 worker、诊断 worker、Ollama worker、角色编辑、关系事件、系统诊断，是 UI 风险集中点。
- `pack.bat` 是发布安全关键点，存在目录整体复制带来的 ignored 文件打包风险。

## 11. 逐链路静态审计结果

### 输入到回复链路

静态链路：

`InputBar` -> `PetWindow.message_submitted` -> `AppController.send_message()` -> `ChatWorker` -> `DaniyaEngineAdapter` -> `DialogueEngine` -> `PromptBuilder/ProviderManager` -> `AppController._handle_reply()` -> `HistoryManager.append()` -> `PetWindow.speak()`

风险：

- `DialogueEngine` 也会写关系/记忆事件；`AppController` 写聊天历史。需要动态确认是否重复写同类记录。

### 动作链路

静态链路：

`ActionRouter/DialogueEngine action` -> `DaniyaEngineAdapter` -> `ThreadSafeAnimationManager` -> `AnimationManager` -> `StateManager` -> `ActionManifest` -> `AssetManager`

风险：

- `BehaviorEngine`、`DayNightManager`、`ReminderManager`、`IdleManager` 均可触发动作，需要状态优先级。

### 行为链路

静态链路：

`PetAvatar mouse event` -> `InteractionDetector` -> `PetBehaviorEngine` -> `DragController/SnapController/IdleBehavior` -> `PetWindow` signals -> `AppController`

风险：

- 单击/双击/长按/拖拽共享同一 detector，动态误判必须测试。

### 设置链路

静态链路：

`MenuManager` -> `AppController.open_settings_center()` -> `SettingsWindow` -> `SettingsManager/ConfigManager`

风险：

- 设置中心涉及 API key、provider、角色包、动作、数据备份，必须动态验证保存即时生效和 key 不泄露。

## 12. 打包审计结果

静态结论：存在 P1 打包风险。

证据：

- `pack.bat` 使用 `--add-data "config;config"`。
- `pack.bat` 后续 `robocopy "config" "release\%PACKAGE_NAME%\config" /E`。
- `.gitignore` 仅影响 Git，不影响 `pack.bat` 对本地目录的复制。
- 本地存在 ignored `config/api_config.json`、`config/multimodal_config.json`。

风险：

- 即使 Git 不跟踪，本地用户配置仍可能进入 PyInstaller 内部目录或 release 目录。

## 13. 安全审计结果

静态结论：

- Git 跟踪安全：通过。
- 打包安全：存在待修 P1 风险。

证据：

- `.gitignore` 覆盖 `.env`、`data/`、`assets/private/`、`characters/*/assets/`、`models/`、`backups/`、`release/`、`dist/`、`build/`、`config/api_config.json`、`config/multimodal_config.json`。
- `git ls-files` 敏感路径检查仅输出 `characters/template/assets/*`。
- tracked secret scan 命中项均为示例 key 或测试 fixture，例如 `.env.example`、README 示例、`tests/test_*` 中的 `sk-test`/`secret-key`。

## 14. 最终结论

第一阶段静态审计完成。

项目结构、核心模块、配置解析、角色包静态校验、Git 安全状态整体可用。

必须优先关注：

1. `pack.bat` 复制 ignored 本地配置/文档目录的发布安全风险。
2. v0.55 行为引擎与既有动画/idle/reminder/day-night 状态抢占风险。
3. 多 QTimer、多 signal、多 worker 的动态重复触发风险。
4. `characters/test_dummy/` 本地存在但未跟踪，v0.53 仓库态不完整风险。
5. 大量 GUI/API/打包/破坏性 fallback 项尚未在本阶段执行，必须在第二阶段按计划补测。
