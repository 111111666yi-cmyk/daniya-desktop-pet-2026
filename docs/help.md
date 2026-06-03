# Daniya Summer Desktop Pet 帮助

## 菜单结构

右键桌宠可以打开菜单：

- 基础：显示/隐藏输入框、置顶开关、大小。
- 对话：历史记录、人设设置、主人档案。
- 陪伴：记一笔、日程提醒、小游戏、传送门。
- 系统：帮助、退出。

如果你看到的是“取消置顶、显示/隐藏输入框、历史记录、人设设置、主人档案、帮助、退出”这种扁平菜单，说明旧版桌宠进程还在运行。请先退出旧桌宠，再重新运行 `run.bat`。

## 桌宠大小和清晰度

默认推荐大小是 96px，接近经典小桌宠尺寸。右键“基础 / 大小”可以切换：

- 迷你 80px
- 推荐 96px
- 稍大 112px
- 清楚 128px
- 大号 144px
- 最大 160px

程序会从高清原图重新缩放显示，不会覆盖你的原始素材。控制台会输出原图尺寸、DPI、渲染 pixmap 尺寸和 QLabel 显示尺寸。

## 素材放置

推荐目录：

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

`assets/private/` 不会提交到 GitHub。

动作图片可以后续放入：

```text
assets/private/daniya_summer/idle/
assets/private/daniya_summer/talk/
assets/private/daniya_summer/drag/
assets/private/daniya_summer/sleep/
assets/private/daniya_summer/happy/
assets/private/daniya_summer/remind/
assets/private/daniya_summer/clicked/
```

如果缺少动作图，程序自动回退到 `normal1.png` 和 `normal2.png`。

## 输入和对话

1. 右键“基础 / 显示输入框”。
2. 输入内容后回车发送。
3. 请求期间会显示“达妮娅正在想...”。
4. 回复回来后会用打字机效果显示。
5. 打字期间 normal1/normal2 会切换模拟口型。

没有 `.env` 或 API Key 为空时，会自动使用本地回复，不会崩溃。

## DeepSeek API 配置

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

`.env` 必须放在项目根目录，也就是和 `main.py` 同一层。控制台只会显示脱敏 key，例如 `abcd****wxyz`。

## 陪伴功能

### 记一笔

右键“陪伴 / 记一笔”，输入内容后保存到：

```text
data/notes.txt
```

空内容不会保存，达妮娅会提示“空白的东西我就不记啦。”

### 日程提醒

右键“陪伴 / 日程提醒”，填写时间和事项。数据保存到：

```text
data/reminders.json
```

到时间后，达妮娅会弹气泡并弹出提醒窗口。点击“知道了”或关闭提醒后，这条提醒会标记为 `done=true`。

### 整点报时

默认关闭。开启后每分钟检查一次系统时间，分钟为 00 时触发整点报时。同一小时只触发一次。

开关在：

```json
"hourly_chime_enabled": false
```

### 闲聊陪伴

默认关闭。开启后如果 10 分钟无互动，达妮娅才会主动冒一句本地气泡。

配置：

```json
"idle_chat_enabled": false,
"idle_chat_minutes": 10
```

点击、拖动、发送消息都会刷新无互动计时。

### 空闲小动作

默认关闭。开启后至少 600 秒无互动才会触发小幅度动作；旧配置首次进入 v0.61 核审版本时会自动迁移为安静默认，之后用户在设置中心手动开启的选择会被保留。

### 昼夜作息

默认 23:00-07:00 为夜间模式。夜间点击达妮娅时，更容易出现休息提醒，例如：

```text
这么晚啦，要不要睡觉呀？
Zzz……啊，主人还醒着？
```

不会禁止聊天，只做温柔提醒。

### 小游戏

右键“陪伴 / 小游戏”：

- 猜拳：石头 / 剪刀 / 布，主人赢时好感度 +1。
- 掷骰子：随机 1-6。
- 随机数 1-100。

小游戏不调用 API。

### 传送门

右键“陪伴 / 传送门”，默认包含：

- GitHub
- ChatGPT
- Bilibili
- DeepSeek

书签配置在：

```text
config/bookmarks.json
```

URL 写错时不会崩溃，达妮娅会提示地址不对。

## 人设和档案

右键“对话 / 人设设置”可以修改：

```text
config/system_prompt.txt
```

右键“对话 / 主人档案”可以修改：

```text
config/profile.json
```

保存后下一次对话立即生效。

## 常见问题

### 看不到新菜单

旧桌宠进程还在运行。请右键旧桌宠退出，或者关闭所有 `main.py` 进程后重新运行：

```bat
run.bat
```

### 看不到自己的素材

确认文件路径：

```text
assets/private/daniya_summer/normal1.png
assets/private/daniya_summer/normal2.png
```

如果没有 private 素材，程序会使用 placeholder。

### API 没有响应

程序会自动回退到本地回复。请检查：

- `.env` 是否在项目根目录。
- `DEEPSEEK_API_KEY` 是否正确。
- 网络是否能访问 DeepSeek。
- 账户余额是否足够。
- 模型名是否正确。
- `DEEPSEEK_BASE_URL` 不要带 `/chat/completions`。

### 桌宠仍然模糊

请确认 private 中放的是高清 PNG，不是已经缩成 96px 的小图。推荐源图至少 512x512，更推荐 1024x1024 或以上。
