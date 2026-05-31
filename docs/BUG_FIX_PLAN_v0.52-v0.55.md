# v0.52-v0.55 Bug 修复计划

审计补丁版本：v0.55.2

## 修复顺序

1. P0：未发现。
2. P1：先修会破坏对话主链路或发布安全的问题。
3. P2：再修局部逻辑误导、状态错乱和 fallback 不完整。
4. P3：最后处理版本、文档、diff 卫生。

## 已执行修复

| ID | 等级 | 修复方案 | 回归 |
|---|---|---|---|
| BUG-55-001 | P1 | `reminder_due` 只保留内部 `[reminder]` 触发词，避免普通“提醒我”请求被事件系统吞掉。 | `tests/test_dialogue_routing.py` |
| BUG-55-002 | P2 | 在 `DialogueEngine` 增加最小 `/pet ...` 命令表，status/reload/event/sleep/wake 均本地处理。 | `tests/test_dialogue_routing.py` |
| BUG-55-003 | P1 | `pack.bat` 只发布公开角色文本和 template 公开 assets，不再复制整个 `characters/`。 | `pack.bat` + release 内容检查 |
| BUG-55-004 | P3 | 同步版本到 `v0.55.2`，更新 README / CHANGELOG / VERSION_LOG。 | 元数据检查 |
| BUG-55-005 | P3 | 清理尾随空格和 EOF 多余空行。 | `git diff --check` |

## 暂不扩展

- 不实现自然语言提醒解析器；本轮只保证“提醒我……”不会被误判为提醒到期事件。
- 不实现持久 sleep 状态机；`/pet sleep` 当前只做本地回应和 sleep 动作。
- 不重构事件系统；仅修复已复现的关键词误触发。
- 不把本地 `characters/daniya/assets/` 转成公开素材；继续保持被 Git 和 release 隔离。
