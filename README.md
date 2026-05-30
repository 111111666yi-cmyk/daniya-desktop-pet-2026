# Daniya Summer Desktop Pet · 达妮娅夏日桌宠

达妮娅是一款基于 Python + PySide6 的开源桌宠应用。提供透明置顶窗口、拖拽移动、右键菜单、输入框对话、气泡消息、打字机效果、云端/本地 AI 对话、角色关系引擎、设置中心等功能。

这是一个非官方同人作品。本仓库不分发官方游戏资源、私有角色素材、用户关系数据或 API Key。

## 快速开始

### 1. 下载安装

```bat
# 克隆仓库
git clone https://github.com/<your-username>/daniya2026523.git
cd daniya2026523

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
- **设置中心**：右键菜单 → 对话 → 设置中心，管理 API、模型、桌宠行为、角色资源
- **本地模型**：设置中心 → 模型与引擎 → 本地部署，可浏览推荐模型目录并一键拉取

## 系统要求

- Python 3.10 / 3.11 / 3.12
- Windows 10+（主要支持平台）
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
| `tests/` | 测试用例（179 通过） |

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
- **v0.50** — 首个正式开源发布版（推荐模型目录、内置下载器、许可证确认、图标系统、桌面快捷方式）

## 许可证

本项目代码采用 MIT License。角色设定与行为脚本为同人创作。

图标素材来自 [Nieobie/Game-Icon-Pack](https://github.com/Nieobie/Game-Icon-Pack)（B站创作者 UID:3493118095657529）。

## Data Directories

Runtime data is stored under `data/`, including:

- `data/chat_history.jsonl`
- `data/affinity.json`
- `data/reminders.json`
- `data/notes.txt`
- `data/daniya_relation/relationship_state.json`
- `data/daniya_relation/event_log.json`
- `data/daniya_relation/user_memory.json`

`data/` and `data/daniya_relation/` are ignored by Git. Do not commit real user relationship state or chat history.

## Development

Common checks:

```bat
python tools\validate_character_pack.py characters\daniya
pytest -q
run.bat
git status --short
```

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
- v0.49: official open source release, current stable version.

## License

Code in this repository is licensed under the MIT License. The license only covers repository code and documentation. It does not cover user-provided character assets, third-party assets, official game resources, or any private files placed under ignored directories.
