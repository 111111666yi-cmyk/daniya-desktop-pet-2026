# Daniya Summer Desktop Pet · 达妮娅夏日桌宠

Current version: **DaniyaSummerPet v0.65 Integrated Preview**

达妮娅是一款基于 Python + PySide6 的开源桌宠应用。提供透明置顶窗口、拖拽移动、右键菜单、输入框对话、气泡消息、打字机效果、云端/本地 AI 对话、角色关系、记忆备忘录、自然语言提醒、文件整理预览、系统状态感知、隐私剪贴板交互、专注/游戏模式和设置中心等功能。

这是一个非官方同人作品。本仓库不分发官方游戏资源、私有角色素材、用户关系数据或 API Key。

## 快速开始

### 1. 下载安装

```bat
# 克隆仓库
git clone https://github.com/111111666yi-cmyk/daniya-desktop-pet-2026.git
cd daniya-desktop-pet-2026

# 运行安装脚本（创建虚拟环境 + 安装依赖 + 创建桌面快捷方式）
install.bat
```

安装完成后会自动启动达妮娅，并创建桌面快捷方式「达妮娅桌宠」，以后双击即可启动。

### 2. 首次配置

首次启动时会弹出**首次运行向导**，可选择：
- **A. 快速体验模式** — 无需 API Key，本地假回复
- **B. API 云模型模式** — 接入 DeepSeek/OpenAI/Claude
- **C. 本地大模型模式** — 接入 Ollama/LM Studio 等本地服务
- **D. 单机测试模式** — 断网开发测试

### 3. 日常使用

- **对话**：右键输入框发送消息，达妮娅会通过 AI 回复
- **设置中心**：右键菜单 → 对话 → 设置中心，管理 API、模型、桌宠行为、角色资源、关系状态和记忆备忘录
- **本地模型**：设置中心 → 模型与引擎 → 本地部署，可浏览推荐模型目录并一键拉取
- **v0.61-v0.65 扩展能力**：自然语言提醒、文件整理预览、系统状态感知、隐私剪贴板交互、专注/游戏模式

## 系统要求

- Python 3.10 / 3.11 / 3.12
- Windows 10+（主要支持平台）
- PySide6 兼容性建议：推荐使用 `PySide6==6.6.3`（社区反馈 `6.7.2+` 版本在特定高 DPI 或双屏系统下容易出现闪退或拖拽失效）
- （可选）Ollama — 用于本地模型拉取和运行

## 项目结构

| 目录 | 说明 |
|---|---|
| `src/` | 应用源码（GUI、API边界、Provider管理） |
| `core/` | 对话引擎（角色系统、关系引擎、Speech Filter） |
| `characters/` | 角色包（template 模板 + daniya 公开示例） |
| `config/` | 配置文件（API、模型目录、系统提示词） |
| `assets/icons/` | UI 图标（来自 Nieobie/Game-Icon-Pack） |
| `data/` | 运行时数据（关系状态、事件日志，Git忽略） |
| `docs/` | 项目文档 |
| `tests/` | pytest 测试用例 |

## API 配置

```bat
copy .env.example .env
```

编辑 `.env` 填入 API Key：

```text
DEEPSEEK_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

也可在设置中心 → 模型与引擎 → 云端 API 配置中直接填写。

## Windows 发布包运行态

从 v0.55.3 开始，下载版 exe 会把运行态写入：

```text
%APPDATA%\DaniyaSummerPet\
```

这里会保存 `.env`、`config/api_config.json`、聊天历史、关系状态、提醒、便签和窗口位置。程序文件本身可以放在桌面、下载目录、D 盘或 `Program Files` 等位置；运行态不再依赖 exe 所在目录可写。

## 开发

```bat
# 安装依赖
pip install -r requirements.txt

# 运行
python main.py

# 测试
pytest tests/ -q
```

## 版本历史

- v0.41 — 动作资源系统
- v0.415 — 角色包 + 关系引擎
- v0.42 — 设置中心
- v0.43 — GitHub 开源整理
- v0.44-v0.48 — 多轮迭代（多模型Provider、本地模型接入、打包测试）
- v0.49 — Provider 架构重构（Boundary 模式 + ProviderRegistry）
- v0.50 — 首个正式开源发布版（推荐模型目录、内置下载器、许可证确认、图标系统、桌面快捷方式）
- v0.51 — 发布后补丁修复版（修复打包资源路径、本地与动作 fallback 异常、设置原子写入防锁保护等）
- v0.52 — 角色体验、人设回应、关系与 lore 注入精修
- v0.53 — 多角色模板、角色 fallback 与热重载
- v0.54 — 对话路由与剧情事件分流系统
- v0.55 — 桌宠行为引擎（屏幕边缘吸附、防止移出屏幕、点击分流检测、空闲小动作）
- **v0.55.2** — 工程审计补丁（提醒事件误触发、隐藏命令回应、发布包角色素材隔离）
- **v0.55.3** — AppData 运行态补丁（下载版配置和数据写入 `%APPDATA%\DaniyaSummerPet\`）
- **v0.61** — 自然语言提醒系统，支持相对、绝对、循环提醒解析和输入链路接入
- **v0.62** — 安全文件整理预览、记忆清理入口、Provider 记忆注入与 Z.AI Provider 支持
- **v0.63** — 本地系统状态感知，覆盖 CPU、内存、电量、磁盘与网络提示
- **v0.64** — 隐私安全剪贴板交互，默认拦截 API Key、Bearer、凭据、手机号、身份证号等敏感内容
- **v0.65** — 专注/游戏模式，降低游戏或专注状态下的非必要打扰

## 许可证

本项目代码采用 MIT License。角色设定与行为脚本为同人创作。

图标素材来自 [Nieobie/Game-Icon-Pack](https://github.com/Nieobie/Game-Icon-Pack)（B站创作者 UID:3493118095657529）。

## Data Directories

Source/development mode stores runtime data under `data/`. Packaged Windows releases store runtime data under `%APPDATA%\DaniyaSummerPet\`. Runtime data includes:

- `data/chat_history.jsonl`
- `data/affinity.json`
- `data/reminders.json`
- `data/notes.txt`
- `data/daniya_relation/relationship_state.json`
- `data/daniya_relation/event_log.json`
- `data/daniya_relation/user_memory.json`

`data/` and `data/daniya_relation/` are ignored by Git. Do not commit real user relationship state or chat history. Packaged release runtime data under `%APPDATA%\DaniyaSummerPet\` is outside the repository.

## First-Run Wizard

v0.58 adds a five-page first-run guide for welcome, API setup, private assets, character packs, and final startup. Users can skip API and use local fallback, or save a provider/base URL/model/API Key to the local `.env`.

The Settings Center also exposes relationship state, recent events, and a memory memo view. User profile, relationship memory, unlocked story fragments, and manual notes are local runtime data and are not committed to Git.

The completion marker is stored in `data/first_run_done.json` in source mode and `%APPDATA%\DaniyaSummerPet\data\first_run_done.json` in the Windows package. Open Settings Center -> System -> Reopen first-run wizard to view it again without clearing existing settings.

See `docs/first_run_guide.md` and `docs/troubleshooting.md`.

## Development

Common checks:

```bat
python tools\validate_character_pack.py characters\daniya
pytest -q
run.bat
git status --short
```

Automated project checks:

```bat
python tools\check_sensitive_files.py
python tools\check_character_packs.py
python tools\check_config_templates.py
python tools\check_docs_links.py
python tools\check_public_surface.py
python tools\check_release_zip.py release\DaniyaSummerPet-v0.65-win-x64.zip
```

Use GitHub Issues for reproducible bugs and Pull Requests for focused, stage-scoped changes. Do not include `.env`, runtime `data/`, private assets, model files, or `characters/test_dummy/`.

Read:

- `AGENTS.md` for AI coding agent rules.
- `CONTRIBUTING.md` for contribution workflow.
- `docs/dev_workflow.md` for stage-by-stage validation.
- `docs/roadmap.md` for planned versions.
- `docs/release_checklist.md` for future release checks.

## Roadmap

- v0.44: exe packaging test, completed.
- v0.45: multi-model backend, integrated.
- v0.46: local model connection, integrated.
- v0.47: action asset pack integration, integrated.
- v0.48: release candidate, accepted.
- v0.49: official open source release.
- v0.54: dialogue router and lore triggers.
- v0.55: behavior engine (dragging, snapping, idle behavior).
- v0.55.3: AppData runtime patch.
- v0.58: first-run onboarding guide.
- v0.59: automated local checks and CI preparation.
- v0.60: release preparation.
- v0.61-v0.65: reminders, file organizer preview, system status, privacy clipboard, focus/game mode.

## 已知限制与问题反馈

为提升同人开发阶段的使用体验，以下是整理的已知系统边界与环境限制，如遇异常可参考排查：

1. **PySide6 6.7.2+ 崩溃与性能抖动**: 社区报告指出，新版 PySide6 库在某些 Windows DPI 缩放配置下可能发生异常退出。若遇到崩溃，推荐锁定安装 `PySide6==6.6.3`。
2. **多显示器与高 DPI 缩放**: 在非标准 DPI 缩放比例（例如 125%、150% 等）或多屏幕环境下，桌宠边缘判定或拖动可能产生微小偏差，可使用右键菜单内的设置中心微调动作边界。
3. **休眠/唤醒与定时提醒延迟**: 操作系统深度睡眠可能导致基于 QTimer 的本地提醒时间轮中断。当系统唤醒时，调度器会补偿已过期的提醒，但实时性受系统休眠时长影响。
4. **数据隐私安全红线**:
   - 项目在本地保存的 `.env` 配置文件与 `data/` 目录默认存有聊天记录、API Keys 及人物亲密度状态，均已写入 `.gitignore`，**强烈建议切勿提交此类私有数据到任何公共版本库**。
   - 对安全性要求极高或需要在公共设备运行的用户，可直接在启动向导中选择本地脱机模型或离线体验模式。
5. **Bug 提交与反馈反馈渠道**: 欢迎在 GitHub 提报 Issue，建议附带脱敏后的 `drag_debug.log` 以及复现步骤。

## License

Code in this repository is licensed under the MIT License. The license only covers repository code and documentation. It does not cover user-provided character assets, third-party assets, official game resources, or any private files placed under ignored directories.
