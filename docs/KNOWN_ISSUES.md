# KNOWN_ISSUES

## v0.70 Acceptance Boundaries (2026-06-05)

| ID | Level | Status | Required evidence |
|---|---|---|---|
| QA70-PROVIDER-001 | P1 | MANUAL REQUIRED | One real cloud reply using a user-owned API Key and available quota. Do not record the key. |
| QA70-MONITOR-001 | P2 | PARTIAL / MANUAL REQUIRED | Single physical 2880x1800 monitor at 200% DPI and virtual negative-origin/DPR 1.0-2.0 tests passed. A second physical mixed-DPI monitor was not available. |
| QA70-GUI-001 | P2 | ASSISTED PASS / HUMAN FEEL REQUIRED | Packaged GUI interaction, input, edge peek, preview-only file organization, default-off controls, and long bubble layout passed message-level Windows automation. Final subjective mouse feel still requires a human pass. |
| QA70-SMARTSCREEN-001 | P3 | WARNING OBSERVED | The unsigned EXE with `ZoneId=3` triggered `smartscreen.exe` and Windows cancelled launch. Users may need to confirm the warning; code signing is not included. |
| QA70-ANTIVIRUS-001 | P3 | PARTIAL / MANUAL REQUIRED | Lenovo Anti-Virus powered by Huorong scan was invoked for the final candidate. No deletion or quarantine was observed, but the custom result window was not machine-readable. |

Closed by automated v0.66-v0.69 work:

- Settings Center page organization and default-state visibility.
- Daniya utility wording regression.
- Passive bubble/action overlap and idle-return coordination.
- Character discovery, fallback, hot reload, and per-character relationship-state isolation.

## v0.60 Manual QA Open Items (2026-06-02)

| ID | Level | Item | Status / Rationale |
|---|---|---|---|
| QA60-ZAI-001 | P1 | Z.AI real API reply not accepted | MANUAL REQUIRED: v0.61 source now has a standard `zai` text Provider entry, but live-provider QA still requires a user-owned `ZAI_API_KEY`, quota, and one observed real reply. Do not mark live-provider QA PASS until that evidence exists. |
| QA60-BUBBLE-001 | P3 | Long text bubble visual acceptance | CLOSED IN v0.70 ASSISTED QA: a dedicated long local response wrapped without overflow or overlap in the packaged application. |
| QA60-MONITOR-001 | P2 | Multi-monitor drag not accepted | BLOCKED: current Windows session exposes only one monitor. |
| QA60-SHORTCUT-001 | P3 | First-run wizard optional desktop shortcut creation | SOURCE FIXED / NEEDS PACKAGE QA: a non-default checkbox now creates a `daniya521` desktop shortcut and failure does not block setup completion. Rebuild and manually verify before closing. |
| QA60-WINDOW-001 | P1 | Pet/settings window lifecycle can make the app disappear | SOURCE FIXED / NEEDS PACKAGE QA: the app now disables quit-on-last-window-closed behavior, so Settings Center minimize/close and pet hidden/tray states should not terminate the process. Rebuild and manually verify before closing. |
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

更新日期：2026-06-05
审计阶段：第二阶段，动态验证后

## 暂不修复清单

| ID | 等级 | 问题 | 为什么暂不修 |
|---|---|---|---|
| FA-TIMER-001 | P2 | 多 QTimer / QPropertyAnimation / worker 叠加 | 第二阶段连续点击/双击/typewriter/reload 通过；无证据不改 Timer |
| FA-CONFIG-001 | P2 | tracked `config/app_config.json` 包含运行态字段 | 涉及兼容性和配置迁移，不适合第一阶段修 |
| FA-REL-001 | P3 | 本地 `release/` 有旧 v0.44 产物 | 已被 `.gitignore` 覆盖，不影响 Git；打包前清理即可 |
| FA-DEBUG-001 | P3 | 本地 `run_verify.py` 与 `drag_debug.log` | 已被 `.gitignore` 覆盖，不影响仓库 |
| FA-DOC-001 | P4 | 历史报告很多，需要索引 | 维护体验项，不影响启动/API/UI |

## 第二阶段已关闭

| ID | 等级 | 修复结果 / 进展 |
|---|---|---|
| FA-PKG-001 | P1 | `pack.bat` 已改为 config 白名单 package input，release/dist/zip 不包含 ignored 本地 config |
| FA-PKG-002 | P2 | `pack.bat` 已排除本地审计截图/debug/tmp/log，release/dist/zip 不包含 `docs/v0.51_patch_audit/` |
| FA-CHAR-001 | P2 | v0.56 已确认 `characters/test_dummy/` 为 local-only，加入 `.gitignore`；正式回归只要求 `characters/daniya` 与 `characters/template` |
| FA-STATE-001 | P2 | v0.68 已增加统一被动反馈协调、交互保护、冷却和完成后回 idle 回归测试。 |
| KI-001 | P4 | **[已解决]** 自然语言提醒解析与创建已在 v0.61 接入输入框主链路，并通过 `natural_reminder_enabled` 开关安全隔离。 |

## 既有 Known Issues (环境与边界限制说明)

### KI-004：PySide6 6.7.2+ 崩溃与不稳定性兼容问题

- 等级：P2
- 现状：部分开发环境和特定 Windows 系统中，使用 `PySide6>=6.7.2` 时存在随机闪退或 UI 刷新不稳定的情况。
- 原因：PySide6 6.7 之后版本的窗口事件循环在特定 DPI 和显卡驱动下存在兼容性抖动。
- 建议：推荐并在 requirements 中锁定安装稳定的旧版：`PySide6==6.6.3`。

### KI-005：非标准 DPI 缩放与多屏幕拖动判定偏斜

- 等级：P3
- 现状：在双显示器或具有非 100% 缩放率（如 125%、150% 等）的屏幕中，桌宠边缘吸附检测与长按拖拽偶尔会出现判定偏差。
- 原因：Windows API 坐标体系与 Qt 内部高 DPI 坐标映射的不一致引起。
- 建议：若遇到移动失效，可在右键菜单中调用设置中心，微调参数（双击阈值与边缘安全间距）或临时切换到主屏幕运行。

### KI-006：系统进入睡眠/休眠可能导致定时器阻塞

- 等级：P3
- 现状：当 Windows 系统进入深度休眠或睡眠状态后，基于本地 QTimer 和时间轮的调度将被中断。
- 原因：系统休眠会挂起整个 Python 进程的时间计数器。
- 建议：系统重新唤醒后，调度引擎会自动检测错过的提醒事件并补发消息，但休眠期间的定时器无法做到绝对精准，对于强实时性业务建议依赖外部成熟系统调度。

### KI-007：本地 API Key 与隐私数据存储安全

- 等级：P3
- 现状：云端服务所需的各种 API 密钥及本地用户的聊天历史记录以明文存放在本地 `.env` 及 `data/` 中。
- 原因：简化本地同人项目单机部署与开发的复杂度。
- 建议：项目已预置了 `.gitignore` 防止意外上传，**绝对不要将个人生产环境的密钥和运行时文件提交回公共 Git 仓库**。高危安全场景推荐完全脱机运行本地大模型。

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
