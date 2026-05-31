# v0.52-v0.55 回归测试记录

日期：2026-05-31
版本：v0.55.2

## 自动化检查

| 命令 | 结果 |
|---|---|
| `python --version` | Python 3.10.11 |
| `.venv\Scripts\python.exe -m compileall -q main.py core src tools scripts tests` | 通过 |
| `.venv\Scripts\python.exe tools\validate_character_pack.py characters\daniya` | `Character pack OK: daniya` |
| `.venv\Scripts\python.exe tools\validate_character_pack.py characters\template` | `Character pack OK: template` |
| `.venv\Scripts\python.exe -m pytest -q` | `209 passed, 3 skipped in 30.43s` |
| `git diff --check` | 无 whitespace error，仅 Git 行尾转换 warning |
| `git ls-files .env data assets/private models backups dist build release` | 无输出 |
| `git ls-files 'characters/*/assets/*'` | 无输出 |

## 对话与事件路由

- `抱抱`：`source=special_response`，触发 `happy`。
- `抱抱，然后帮我整理项目计划`：进入模型链路，不被特殊回应吞掉。
- `我好累`：`source=special_response`，触发 `remind`。
- `我好累，帮我分析这个 Python 报错`：进入模型链路。
- `晚安`：`source=special_response`，触发 `sleep`。
- `晚安，顺便提醒我明天喝水`：进入模型链路，不再命中 `reminder_due`。
- `/pet status`、`/pet reload`、`/pet event`、`/pet sleep`、`/pet wake`：本地命令处理，不进入 API。

## 启动与打包

- 受控启动：Qt offscreen 下 `AppController` 成功创建窗口，角色为 `daniya`。
- `run.bat`：实际拉起 `pythonw.exe main.py` 常驻进程，冒烟后手动停止测试进程。
- `pack.bat`：成功生成 `release/DaniyaSummerPet-v0.55.2-win-x64/` 与 zip。
- exe 冒烟：`DaniyaSummerPet.exe` 启动 4 秒未提前退出，随后停止进程。
- release 禁止项检查：`.env`、`data`、`assets/private`、`models`、`backups`、`characters/daniya/assets`、`characters/test_dummy` 均不存在。
- `characters/template/assets/normal1.png` 存在，公开 fallback assets 可用。

## API 云端回复

- active provider：`deepseek`
- key 检测：`DEEPSEEK_API_KEY` 存在，未输出明文。
- 请求链路：`ChatClient.reply()` -> `ProviderManager.chat()` -> `deepseek_api.chat()`。
- 结果：PASS，`source=api`，`fallback_used=False`，`last_error=无`。
- 回复摘要：收到真实云端回复，长度 17。

## 真实 UI 模拟验收

脚本：`scratch/ui_acceptance_v0552.py`
结果：PASS

| 场景 | 结果 |
|---|---|
| 启动并显示透明桌宠窗口 | PASS |
| 拖到左边缘并吸附 | PASS，`pos=(0, 260)`，`dock_side=left` |
| 从左边缘拖回屏幕内 | PASS，`pos=(360, 260)`，`dock_side=None` |
| 右键菜单打开并关闭 | PASS |
| 输入框展开、发送文本、显示长文本气泡 | PASS，气泡 `257x130`，文本长度 105 |
| 设置中心打开 | PASS，经 `controller.open_settings_center()` 真实入口打开，窗口大小 `860x711` |

截图输出：

- `scratch/ui_acceptance_v0552/01_initial.png`
- `scratch/ui_acceptance_v0552/02_docked_left.png`
- `scratch/ui_acceptance_v0552/03_dragged_back.png`
- `scratch/ui_acceptance_v0552/04_context_menu.png`
- `scratch/ui_acceptance_v0552/05_long_bubble.png`
- `scratch/ui_acceptance_v0552/06_settings_center.png`

## 未直接执行项

- 未覆盖真实多显示器边缘；本机仅检测到一个显示器，行为引擎、snap、window_state 由自动化测试和单屏真实 UI 模拟覆盖。
- 未覆盖自然语言“提醒我明天喝水”自动创建提醒；该能力属于新功能，不纳入本轮 bugfix 回归。
