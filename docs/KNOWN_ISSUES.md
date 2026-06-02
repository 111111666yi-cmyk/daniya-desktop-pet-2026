# KNOWN_ISSUES

## v0.60 Manual QA Open Items (2026-06-02)

| ID | Level | Item | Status / Rationale |
|---|---|---|---|
| QA60-ZAI-001 | P1 | Z.AI real API reply not accepted | BLOCKED: tested release runtime has no Z.AI/Zhipu/GLM provider entry and no Z.AI key. Do not mark live-provider QA PASS until a real configured provider reply is observed. |
| QA60-BUBBLE-001 | P3 | Long text bubble visual not accepted | NEEDS POLISH: local fallback replies are short; a live model or dedicated long local response is needed for visual acceptance. This does not block the v0.60 release candidate. |
| QA60-MONITOR-001 | P2 | Multi-monitor drag not accepted | BLOCKED: current Windows session exposes only one monitor. |
| QA60-SHORTCUT-001 | P3 | First-run wizard does not offer optional desktop shortcut creation | Suggested improvement: add a non-forcing checkbox for creating a `Daniya521` desktop shortcut; creation failure must not block startup or corrupt setup state. |
| QA60-INSTANCE-001 | P3 | Old development instance can coexist with packaged release instance during QA | Documented test risk: make sure manual QA targets the packaged exe process, not an already-running `pythonw.exe main.py` development instance. |

## v0.60 Release Blocker Follow-Up (2026-06-02)

Resolved in the v0.60 blocker fix after baseline `862beda`:

- Release package story assets: `characters/daniya/story.yaml` is now explicitly packaged; `characters/template/story.yaml` remains covered by the public template package.
- Release zip validation: the scanner now requires both story files and rejects Daniya private assets, forbidden runtime/build paths, local user paths, and obvious API key patterns.
- Local audit report risk: `*_audit_report.docx` is ignored so `DaniyaSummerPet_v0.60_audit_report.docx` remains local-only.
- Historical docs local paths: the known `<local-user-path>` / `<local-file-uri>` references in tracked docs were sanitized.
- Config diff cleanup: unrelated runtime `config/app_config.json` window-position noise was reverted; public fallback reply arrays and `config/model_profiles.json` profile history defaults are kept.

Still manual before tag or GitHub Release:

- Valid real-provider API response with a user-owned key and quota.
- Multi-monitor physical drag behavior.
- Right-click menu feel.
- Long text bubble visual behavior.

更新日期：2026-05-31
审计阶段：第二阶段，动态验证后

## 暂不修复清单

| ID | 等级 | 问题 | 为什么暂不修 |
|---|---|---|---|
| FA-STATE-001 | P2 | 多个模块可写动作/行为状态 | 第二阶段未稳定复现卡死；无证据不改状态机 |
| FA-TIMER-001 | P2 | 多 QTimer / QPropertyAnimation / worker 叠加 | 第二阶段连续点击/双击/typewriter/reload 通过；无证据不改 Timer |
| FA-CONFIG-001 | P2 | tracked `config/app_config.json` 包含运行态字段 | 涉及兼容性和配置迁移，不适合第一阶段修 |
| FA-REL-001 | P3 | 本地 `release/` 有旧 v0.44 产物 | 已被 `.gitignore` 覆盖，不影响 Git；打包前清理即可 |
| FA-DEBUG-001 | P3 | 本地 `run_verify.py` 与 `drag_debug.log` | 已被 `.gitignore` 覆盖，不影响仓库 |
| FA-DOC-001 | P4 | 历史报告很多，需要索引 | 维护体验项，不影响启动/API/UI |

## 第二阶段已关闭

| ID | 等级 | 修复结果 |
|---|---|---|
| FA-PKG-001 | P1 | `pack.bat` 已改为 config 白名单 package input，release/dist/zip 不包含 ignored 本地 config |
| FA-PKG-002 | P2 | `pack.bat` 已排除本地审计截图/debug/tmp/log，release/dist/zip 不包含 `docs/v0.51_patch_audit/` |
| FA-CHAR-001 | P2 | v0.56 已确认 `characters/test_dummy/` 为 local-only，加入 `.gitignore`；正式回归只要求 `characters/daniya` 与 `characters/template` |

## 既有 Known Issues

### KI-001：自然语言提醒创建尚未接入输入框主链路

- 等级：P4
- 现状：`ReminderManager` 支持通过菜单添加明确时间格式的提醒；输入框中的“提醒我明天喝水”目前不会被错误吞成 `reminder_due`，但也不会自动创建提醒。
- 原因：自然语言时间解析属于新功能，不适合本轮稳定性修复顺手实现。
- 建议：后续单独设计提醒意图解析，明确格式、时区、失败提示和测试用例。

### KI-002：`run.bat` 使用 detached `pythonw.exe`

- 等级：P4
- 现状：适合用户双击启动，但不适合自动化判断退出码。
- 本轮处理：第二阶段使用 `Start-Process cmd.exe /c run.bat` 模拟真实双击启动。
- 建议：若未来需要 CI 级启动检查，可增加只用于测试的 smoke 命令或环境变量。

### KI-003：本地忽略角色素材仍存在于工作区

- 等级：P4
- 现状：`characters/daniya/assets/` 存在大量本地素材，但被 `.gitignore` 忽略，且 v0.55.2 打包已排除。
- 建议：继续保留在本地或移动到更明确的私有素材目录；不要提交。

## 既有已关闭项

- BUG-55-001：普通“提醒我”请求误触发 `reminder_due`，已在 v0.55.2 修复。
- BUG-55-002：`/pet ...` 隐藏命令返回 weekly 默认文案，已在 v0.55.2 修复。
- BUG-55-003：release 可能带入忽略角色素材，已在 v0.55.2 修复。

## 审计执行副作用

- 第二阶段临时自动化脚本曾误删 ignored `data/` 与 `config/api_config.json`；已重新生成安全默认文件。
- 该副作用不影响 Git 和发布包，但旧本地运行态历史无法从 Git 恢复。
- v0.56 已新增 `docs/DESTRUCTIVE_TEST_POLICY.md`、`tools/backup_runtime_state.py`、`tools/restore_runtime_state.py`，后续缺文件/坏文件测试必须使用备份恢复或临时沙盒。
- v0.56 复核后，restore 必须显式传入 `backups/runtime_backup_YYYYMMDD_HHMMSS/`，并在恢复前创建二次备份；`models/` 只备份小型 metadata，不复制大模型本体。
