# v0.52-v0.55 工程级 Bug 全量排查报告

审计日期：2026-05-31
当前补丁版本：v0.55.2
基线：`HEAD` / `v0.50` 之后的工作区改动

## 1. 项目当前能否启动

- 结论：可以启动。
- 受控启动检查：使用 Qt offscreen 创建 `QApplication -> AppController -> PetWindow`，角色包解析为 `daniya`，主窗口对象可见，随后正常退出。
- 打包后 exe 冒烟：`release/DaniyaSummerPet-v0.55.2-win-x64/DaniyaSummerPet.exe` 启动 4 秒未提前退出，随后手动停止进程。
- 说明：未直接执行 `run.bat` 常驻检查，因为该脚本使用 `pythonw.exe` detached 启动，会留下交互窗口；本轮用受控启动覆盖同一初始化链路。

## 2. Bug 清单

| ID | 版本 | 模块 | 等级 | 状态 | 影响启动 | 影响 API 对话 | 影响人设 | 影响动作 | 影响打包 |
|---|---|---|---|---|---|---|---|---|---|
| BUG-55-001 | v0.54 | 事件路由 | P1 | 已修复 | 否 | 是 | 是 | 是 | 否 |
| BUG-55-002 | v0.54 | hidden command | P2 | 已修复 | 否 | 否 | 是 | 是 | 否 |
| BUG-55-003 | v0.55 / 发布 | 打包脚本 | P1 | 已修复 | 否 | 否 | 否 | 否 | 是 |
| BUG-55-004 | v0.55.1 | 版本元数据 | P3 | 已修复 | 否 | 否 | 否 | 否 | 是 |
| BUG-55-005 | 全局 | 提交卫生 | P3 | 已修复 | 否 | 否 | 否 | 否 | 否 |

## 3. 详细问题

### BUG-55-001：普通“提醒我”请求被误判为提醒到期

- 复现步骤：向 `DialogueEngine` 输入 `晚安，顺便提醒我明天喝水`。
- 修复前结果：命中 `reminder_due`，`source=physical_event`，跳过模型，返回 `......哦。`。
- 原因：`characters/daniya/events.yaml` 中 `reminder_due` 同时包含 `[reminder]`、`提醒我`、`该做事`，事件引擎使用包含匹配，导致普通提醒请求被当成系统到期事件。
- 涉及文件：`characters/daniya/events.yaml`、`tests/test_dialogue_routing.py`。
- 修复建议/结果：`reminder_due` 只保留内部触发词 `[reminder]`；新增回归测试确认普通提醒请求进入模型链路。
- 是否建议立即修复：是，已修复。

### BUG-55-002：`/pet ...` 隐藏命令落入错误默认文案

- 复现步骤：输入 `/pet status`、`/pet sleep`。
- 修复前结果：命令不发送给 API，但统一返回 `......行。那就下周。`，`/pet sleep` 不触发 sleep 动作。
- 原因：`DialogueEngine._execute_command_response()` 没有区分 pet hidden command，所有未知 slash 命令复用 weekly 默认文案。
- 涉及文件：`core/dialogue_engine.py`、`tests/test_dialogue_routing.py`。
- 修复建议/结果：增加最小本地命令表：status/reload/event/sleep/wake；未知 slash 命令返回中性确认，不进入 API。
- 是否建议立即修复：是，已修复。

### BUG-55-003：打包会带入被 Git 忽略的角色素材

- 复现步骤：本地存在 `characters/daniya/assets/` 或 `characters/test_dummy/assets/`，运行旧版 `pack.bat`。
- 修复前风险：`--add-data "characters;characters"` 和 release 阶段复制整个 `characters/`，可能把忽略素材带入 exe/release。
- 原因：打包范围按目录粗粒度复制，没有遵守 `.gitignore` 中 `characters/*/assets/` 的隔离意图。
- 涉及文件：`pack.bat`。
- 修复建议/结果：Daniya 只打包 YAML/lore 文本，template 完整打包公开 assets；release 验证显示 `.env`、`data`、`assets/private`、`models`、`characters/daniya/assets`、`characters/test_dummy` 均不存在。
- 是否建议立即修复：是，已修复。

### BUG-55-004：版本元数据仍停留在 v0.51

- 复现步骤：检查 `src/version.py`、`config/app_config.example.json`、`pack.bat`。
- 原因：v0.54/v0.55/v0.55.1 变更已进入工作区，但应用版本和包名未同步。
- 涉及文件：`src/version.py`、`config/app_config.example.json`、`config/app_config.json`、`pack.bat`、`README.md`、`CHANGELOG.md`、`VERSION_LOG.md`。
- 修复结果：同步为 `v0.55.2`。
- 是否建议立即修复：是，已修复。

### BUG-55-005：diff 中存在尾随空格

- 复现步骤：运行 `git diff --check`。
- 原因：多处工作区改动残留尾随空格或 EOF 多余空行。
- 修复结果：机械清理尾随空格；`git diff --check` 仅剩 Git 行尾转换警告，无 whitespace error。
- 是否建议立即修复：是，已修复。

## 4. 分版本检查结论

- v0.52：短情绪特殊回应仍只拦截短句；长任务输入会进入模型链路。完整 lore 未注入普通聊天 prompt。
- v0.53：`daniya` 和 `template` 角色包校验通过；错误角色、缺文件和动作缺图 fallback 已有测试覆盖。
- v0.54：修复提醒事件误触发和 hidden command 默认文案；`/pet ...` 不进入 API。
- v0.55：行为引擎测试通过；拖拽、吸边、window_state 损坏 fallback、idle gating 均有回归覆盖。

## 5. 安全与发布检查

- `git ls-files .env data assets/private models backups dist build release`：无输出。
- `git ls-files 'characters/*/assets/*'`：无输出。
- release 检查：禁止项均未出现在 `release/DaniyaSummerPet-v0.55.2-win-x64/`。
- zip：`release/DaniyaSummerPet-v0.55.2-win-x64.zip` 已生成。

## 6. 结论

当前未发现 P0。已修复 2 个 P1、1 个 P2、2 个 P3。项目可启动、可测试、可打包，且 release 已避免带入本地私有/忽略角色素材。
