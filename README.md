# Daniya Summer Desktop Pet

**Current source milestone: v0.83 · Published packages: see GitHub Releases**

[Source](https://github.com/111111666yi-cmyk/daniya-desktop-pet-2026) · [GitHub Releases](https://github.com/111111666yi-cmyk/daniya-desktop-pet-2026/releases) · [Documentation](docs/index.md) · [Release Checklist](docs/release_checklist.md)

达妮娅夏日桌宠是一个 Windows 桌面陪伴应用，基于 Python + PySide6 构建。它提供透明置顶桌宠、拖拽移动、气泡对话、设置中心、角色关系、记忆备忘录、提醒、文件整理预览、系统状态感知、隐私剪贴板交互和专注/游戏模式。

本项目是非官方同人作品。仓库不分发官方游戏资源、私有角色素材、用户聊天记录、关系数据或 API Key。

v0.83 源码候选包含离线电影式 24 章剧情站、默认关闭的本地养成、隐私受限的天气/媒体/小剧场感知，以及用户可见、可清空的对话级长期记忆与手动观察日记。源码版本、Windows 包和 GitHub Release 是三个独立状态；请用文件名和应用版本确认自己运行的构建。

## Quick Start

### 方式一：下载 Windows 包

1. 从 GitHub Releases 下载所需版本的 `DaniyaSummerPet-vX.XX-win-x64.zip`。
2. 解压到桌面、下载目录或其他普通文件夹。
3. 运行 `DaniyaSummerPet.exe`。

下载版运行数据保存在：

```text
%APPDATA%\DaniyaSummerPet\
```

程序目录可以只读；聊天记录、提醒、记忆、窗口位置和 API 配置不会写回 Git 仓库。

### 方式二：从源码运行

```bat
git clone https://github.com/111111666yi-cmyk/daniya-desktop-pet-2026.git
cd daniya-desktop-pet-2026
install.bat
```

开发时也可以手动运行：

```bat
pip install -r requirements.txt
python main.py
```

## What You Get

| 能力 | 说明 |
|---|---|
| 桌宠窗口 | 透明置顶、拖拽、右键菜单、气泡、打字机效果 |
| 对话系统 | 云端 API、本地 fallback、角色包、关系状态、剧情片段控制 |
| 设置中心 | 默认简单模式保留常用入口，进阶模式提供模型、本地部署、角色资源、关系状态和诊断 |
| 记忆备忘录 | 用户可见、可清空，运行态保存在本地，不进入 Git 或 release 包 |
| 长期记忆 | 默认关闭；对话记录本地向量检索，只注入当前问题最相关的少量记录 |
| 观察日记 | 默认关闭且仅手动生成；发送前确认，Provider fallback 不会冒充成功日记 |
| 剧情阅读 | 本机回环地址打开电影式 24 章阅读器；浏览器不可用时回退 Qt 阅读窗 |
| 本地养成 | 默认关闭；硬币、补给、背包、成长与衣柜状态只保存在本机 |
| 环境感知 | 默认关闭；Open-Meteo 天气、播放器进程存在性与角色包小剧场 |
| 自然语言提醒 | 支持相对时间、绝对时间和循环提醒解析 |
| 文件整理预览 | 先预览再执行，避免直接移动用户文件 |
| 系统状态感知 | 本地 CPU、内存、电量、磁盘和网络状态提示 |
| 隐私剪贴板 | 默认拦截 API Key、Bearer token、凭据、手机号、身份证号等敏感文本 |
| 专注/游戏模式 | 降低非必要打扰，减少“自己动/自己说”的感觉 |

## Defaults And Privacy

当前 v0.83 源码采用安静启动策略：

- 默认不展开输入框。
- 默认关闭空闲小动作。
- 默认关闭空闲闲聊和整点主动提醒。
- 默认关闭边缘探头。
- 用户记忆、聊天历史、提醒、便签和 API Key 只保存在本地运行态目录。
- 长期记忆和观察日记默认关闭，内容可在设置中心查看并清空。
- 观察日记只有在用户手动确认后才会把近期事件摘要发送给当前文本 Provider。
- `.env`、`data/`、`assets/private/`、`models/`、`dist/`、`build/` 和 `release/` 不应提交到 Git。

## AI Providers

支持的主要接入方式：

- DeepSeek
- OpenAI-compatible API
- Z.AI / GLM（需要 `ZAI_API_KEY`）
- Claude、Gemini、Mistral、Groq 等 Provider 配置
- Ollama / LM Studio 等本地模型服务
- 无 API Key 的本地 fallback 模式

可复制 `.env.example` 为 `.env`，也可以在设置中心里配置。

```bat
copy .env.example .env
```

常见环境变量：

```text
DEEPSEEK_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ZAI_API_KEY=your_key_here
```

## System Requirements

- Windows 10 或更新版本
- Python 3.10 / 3.11 / 3.12（源码运行）
- 推荐 PySide6 版本：`PySide6==6.6.3`
- 可选：Ollama 或 LM Studio，用于本地模型

如果遇到高 DPI、多显示器、拖拽或闪退问题，请先看 [Troubleshooting](docs/troubleshooting.md)。

## Project Layout

| 路径 | 用途 |
|---|---|
| `src/` | PySide6 应用、窗口、设置中心、Provider 管理 |
| `core/` | 对话引擎、角色加载、关系引擎、speech filter |
| `characters/daniya/` | 默认公开示例角色包 |
| `characters/template/` | 新角色包模板 |
| `config/` | 可公开的默认配置和模板 |
| `docs/` | 用户文档、开发文档和 release checklist |
| `tests/` | pytest 自动化测试 |

运行态数据目录：

| 模式 | 数据位置 |
|---|---|
| 源码运行 | `data/` |
| Windows 下载包 | `%APPDATA%\DaniyaSummerPet\` |

## Version And Validation Status

| 项目 | 当前状态 |
|---|---|
| 当前源码 | `v0.83 memory continuity candidate` |
| 已发布 Windows Release | 以 [GitHub Releases](https://github.com/111111666yi-cmyk/daniya-desktop-pet-2026/releases) 页面为准 |
| 本地候选包 | `DaniyaSummerPet-v0.83-win-x64.zip` |
| 自动检查 | pytest、敏感文件、角色包、配置模板、文档链接、公开面审查 |
| 发布包检查 | `pack.bat`、zip 内容扫描、隔离运行态 exe 启动烟测 |
| 仍需外部证据 | 真实 Provider Key、第二块实体混合 DPI 显示器、不同 Windows/杀软策略 |

v0.83 自动验收记录在 [V0.83 Integration Acceptance](docs/V0.83_INTEGRATION_ACCEPTANCE.md)，人工项目见 [V0.83 Manual QA Checklist](docs/V0.83_MANUAL_QA_CHECKLIST.md)。

Local candidate:

```text
DaniyaSummerPet-v0.83-win-x64.zip
SHA256: verify locally with `Get-FileHash`; publish only after separate release approval.
```

## Useful Docs

- [First Run Guide](docs/first_run_guide.md)
- [API Configuration](docs/api_config.md)
- [Local Models](docs/local_models.md)
- [LLM Providers](docs/LLM_PROVIDERS.md)
- [Natural Reminders](docs/natural_reminders.md)
- [File Organizer](docs/file_organizer.md)
- [System Status](docs/system_status.md)
- [Clipboard Privacy](docs/clipboard_privacy.md)
- [Focus Mode](docs/focus_mode.md)
- [Memory And Observation Diary](docs/memory_and_diary.md)
- [Known Issues](docs/KNOWN_ISSUES.md)
- [Development Workflow](docs/dev_workflow.md)
- [Version Log](VERSION_LOG.md)

## For Contributors

Before submitting changes:

```bat
python tools\check_sensitive_files.py
python tools\check_character_packs.py
python tools\check_config_templates.py
python tools\check_docs_links.py
python tools\check_public_surface.py
pytest -q
```

Before validating the v0.83 Windows candidate:

```bat
pack.bat
python tools\check_release_zip.py release\DaniyaSummerPet-v0.83-win-x64.zip
```

Keep changes stage-scoped. Do not commit `.env`, runtime `data/`, private assets, model files, packaged `release/` output, `dist/`, or `build/`.

## License

Repository code and documentation are licensed under the MIT License.

The license does not cover user-provided character assets, third-party assets, official game resources, private files, API keys, or runtime data stored under ignored directories.
