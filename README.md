# Daniya Summer Desktop Pet

Daniya Summer Desktop Pet 是一个 Python / PySide6 桌宠项目模板。当前版本实现了透明无边框置顶窗口、拖动、右键菜单、隐藏输入框、气泡打字机、normal1/normal2 口型切换、DeepSeek/OpenAI-compatible 对话、本地兜底回复，以及一组低风险本地陪伴功能。

> 非官方粉丝项目。本仓库不提供《鸣潮》官方资源，也不提供未经授权的角色素材。

## 功能

- 96px 推荐小桌宠尺寸，右键可切换 80/96/112/128/144/160px。
- 高 DPI 渲染：从高清源图按屏幕 DPR 即时缩放，避免 Windows 缩放下发糊。
- 动作状态：idle、talking、hover、clicked、dragging、sleeping、happy、remind。
- 对话：支持 DeepSeek API；没有 API Key 或请求失败时自动使用本地回复。
- 陪伴：随手记、日程提醒、整点报时、闲聊陪伴、昼夜作息、猜拳/骰子/随机数、网站传送门。

## 安装

请安装 Python 3.10、3.11 或 3.12，并勾选 `Add Python to PATH`。

```bat
install.bat
```

## 启动

```bat
run.bat
```

没有 `.env` 或没有 API Key 时，桌宠仍会启动，并使用本地假回复。

## 放置素材

推荐新目录：

```text
assets/private/daniya_summer/normal1.png
assets/private/daniya_summer/normal2.png
assets/private/daniya_summer/app.ico
```

兼容旧目录：

```text
assets/private/normal1.png
assets/private/normal2.png
```

`assets/private/` 已被 `.gitignore` 忽略，不会提交到 GitHub。仓库只保留 `assets/placeholder/` 示例图。

动作图片可放在：

```text
assets/private/daniya_summer/idle/
assets/private/daniya_summer/talk/
assets/private/daniya_summer/drag/
assets/private/daniya_summer/sleep/
assets/private/daniya_summer/happy/
assets/private/daniya_summer/remind/
assets/private/daniya_summer/clicked/
```

然后编辑 `assets/private/daniya_summer/manifest.json`，把对应图片文件名写入 `animations`。如果动作图不存在，程序会自动回退到 `normal1.png` / `normal2.png`。

如果手里是 JPG 或白底图，可以运行：

```bat
python scripts\prepare_assets.py --normal1 "第一张jpg路径" --normal2 "第二张jpg路径"
```

脚本会输出透明 PNG 到 `assets/private/daniya_summer/`。

## 配置 DeepSeek API

复制 `.env.example` 为 `.env`：

```bat
copy .env.example .env
```

填写：

```text
DEEPSEEK_API_KEY=你的真实 key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

`.env` 必须放在项目根目录，也就是和 `main.py` 同一层。控制台会显示当前回复来源，例如 `source=api` 或 `source=local`，但不会打印完整 API Key。

常见 API 问题：

- `.env` 没放在项目根目录。
- API Key 填错、为空，或仍是 `your_api_key_here`。
- 网络连接失败或请求超时。
- DeepSeek 余额不足。
- `DEEPSEEK_MODEL` 模型名错误。
- `DEEPSEEK_BASE_URL` 不要写 `/chat/completions`，程序会自动拼接。

## 修改人设

可直接编辑：

```text
config/system_prompt.txt
config/profile.json
```

也可右键打开“对话 / 人设设置”和“对话 / 御主档案”。保存后下一次对话立即生效。

## 陪伴功能

- 记一笔：右键“陪伴 / 记一笔”，保存到 `data/notes.txt`。
- 日程提醒：右键“陪伴 / 日程提醒”，添加时间和事项，数据保存到 `data/reminders.json`。
- 整点报时：配置 `config/app_config.json` 的 `hourly_chime_enabled`。
- 闲聊陪伴：配置 `idle_chat_enabled` 和 `idle_chat_minutes`。
- 昼夜作息：配置 `day_night_enabled`、`night_start_hour`、`night_end_hour`。
- 小游戏：右键“陪伴 / 小游戏”，包含猜拳、掷骰子、随机数。
- 传送门：书签保存在 `config/bookmarks.json`，可手动修改。

## 打包

```bat
pack.bat
```

输出：

```text
dist/DaniyaSummerPet.exe
```

打包不会包含 `assets/private/`。如果要让 exe 使用私有素材，请在 exe 同级目录创建：

```text
assets/private/daniya_summer/normal1.png
assets/private/daniya_summer/normal2.png
assets/private/daniya_summer/app.ico
```

## 验证口型切换

1. 运行 `run.bat`。
2. 右键“基础 / 显示输入框”。
3. 输入任意消息并回车。
4. 气泡打字期间，角色应在 `normal1.png` 和 `normal2.png` 之间切换。
5. 打字结束后应回到待机图。

## 开源与版权

本项目使用 MIT License。代码可自由学习、修改和分发。

本项目不提供官方游戏拆包资源，不提供未经授权角色素材。达妮娅、《鸣潮》及相关角色、美术、商标、世界观权利归原权利方所有。本项目为非官方粉丝项目。
