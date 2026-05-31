# FULL_BUG_LIST v0.1-v0.55

审计阶段：第一阶段，只读静态审计
基准提交：`db7af9b`

## 严重等级说明

- P0：程序无法启动 / 启动即崩溃 / 主链路完全不可用
- P1：核心功能损坏，如 API、对话、角色加载、动作系统、设置中心、打包
- P2：逻辑锁死、状态冲突、fallback 异常、明显误触发
- P3：UI、文档、提示、体验问题
- P4：未来优化项

## 汇总

| 严重等级 | 数量 | Bug ID |
|---|---:|---|
| P0 | 0 | 无 |
| P1 | 0 open / 1 fixed | FA-PKG-001 fixed in second stage |
| P2 | 4 open / 1 fixed | FA-PKG-002 fixed; FA-STATE-001, FA-TIMER-001, FA-CHAR-001, FA-CONFIG-001 remain open |
| P3 | 2 | FA-REL-001, FA-DEBUG-001 |
| P4 | 1 | FA-DOC-001 |

## FA-PKG-001

Bug ID：FA-PKG-001
版本来源：v0.44-v0.55
模块：打包 / 发布安全
严重等级：P1
标题：`pack.bat` 复制整个 `config/`，可能把 ignored 本地配置打进 release
现象：`.gitignore` 已忽略 `config/api_config.json` 和 `config/multimodal_config.json`，但 `pack.bat` 使用 `--add-data "config;config"` 和 `robocopy "config" ... /E` 整体复制本地 config。
复现步骤：第一阶段未执行打包；静态复现为读取 `pack.bat`。
预期结果：release 只包含公开默认配置或 example 配置，不包含本地用户配置。
实际结果：静态上本地 ignored config 文件仍会被目录级复制。
影响范围：发布包、PyInstaller `_internal/config`、release/config。
可能原因：Git ignore 与打包复制白名单没有统一。
涉及文件：`pack.bat`, `.gitignore`, `config/api_config.json`, `config/multimodal_config.json`
涉及函数：不适用，批处理脚本
是否影响启动：可能间接影响，取决于 release 配置
是否影响 API：可能，若本地 provider/base_url/model 被打包
是否影响角色：否
是否影响动作：否
是否影响事件：否
是否影响行为：否
是否影响打包：是
建议修复方式：已在第二阶段将 `pack.bat` 改为临时白名单 package input；release 中 `config/app_config.json` 来自 `app_config.example.json`，只保留公开 example/default config，不复制 ignored 本地配置。
是否建议立即修复：已修复
状态：Fixed in second stage
回归结果：`pack.bat` 通过；release/dist/zip 均不包含 `.env`, `config/api_config.json`, `config/multimodal_config.json`, `data/`, `assets/private/`, `models/`。

## FA-PKG-002

Bug ID：FA-PKG-002
版本来源：v0.51-v0.55
模块：打包 / 文档产物
严重等级：P2
标题：`pack.bat` 复制整个 `docs/`，可能把 ignored 本地审计截图目录打进 release
现象：`.gitignore` 已忽略 `docs/v0.51_patch_audit/`，但 `pack.bat` 使用 `--add-data "docs;docs"` 和 `robocopy "docs" ... /E`。
复现步骤：第一阶段未执行打包；静态复现为读取 `pack.bat` 和 `.gitignore`。
预期结果：ignored 本地审计证据不进入 release。
实际结果：静态上只要本地目录存在，打包脚本会复制它。
影响范围：release 包体积、用户可见文档、潜在本地截图泄露。
可能原因：发布脚本缺少 docs 排除列表。
涉及文件：`pack.bat`, `.gitignore`, `docs/v0.51_patch_audit/`
涉及函数：不适用
是否影响启动：否
是否影响 API：否
是否影响角色：否
是否影响动作：否
是否影响事件：否
是否影响行为：否
是否影响打包：是
建议修复方式：已在第二阶段通过临时 docs 白名单目录复制，并在 `robocopy` 中排除 `v0.51_patch_audit`, `screenshots`, `debug`, `debug_logs`, `tmp`, `*.tmp`, `*.log`, `debug_*`。
是否建议立即修复：已修复
状态：Fixed in second stage
回归结果：release/dist/zip 均不包含 `docs/v0.51_patch_audit/`，zip entry count=427。

## FA-STATE-001

Bug ID：FA-STATE-001
版本来源：v0.41-v0.55
模块：动作状态 / 行为状态 / 事件状态
严重等级：P2
标题：多个模块可写动作状态，缺少显式全局优先级表
现象：静态扫描显示 `AnimationManager`、`PetBehaviorEngine`、`DayNightManager`、`ReminderManager`、`IdleManager`、`DialogueEngine` 都可能触发动作或状态变化。
复现步骤：静态扫描 `src/app.py`, `src/animation_manager.py`, `src/behavior/behavior_engine.py`, `core/dialogue_engine.py`。
预期结果：talking/dragging/remind/sleep/settings_open/API responding 有统一优先级和互斥规则。
实际结果：已有 `is_idle_behavior_allowed()` 等局部保护，但未形成完整状态机审计表。
影响范围：拖拽、API 回复中 idle、提醒、sleep、随机事件、动作回 idle。
可能原因：v0.41 动作系统、v0.54 事件系统、v0.55 行为系统分阶段引入。
涉及文件：`src/app.py`, `src/animation_manager.py`, `src/behavior/behavior_engine.py`, `src/pet_window.py`, `core/dialogue_engine.py`
涉及函数：`AppController.is_idle_behavior_allowed`, `AnimationManager.set_state`, `PetBehaviorEngine._handle_*`, `DialogueEngine.handle`
是否影响启动：否
是否影响 API：可能，API 回复状态可能被 idle 打断
是否影响角色：否
是否影响动作：是
是否影响事件：是
是否影响行为：是
是否影响打包：否
建议修复方式：先完成动态复现；如确认冲突，再增加状态优先级文档/断言或最小互斥保护。
是否建议立即修复：否，先动态验证
状态：Open
第二阶段动态结果：未稳定复现卡死或状态永久占用。验证项包括 API 回复中 idle 阻断、设置中心 idle 阻断、拖拽中 idle/random 检查、长文本 typewriter 回 idle、边缘吸附、拖出屏幕、坏 `window_state.json`。最终结果 PASS。一次早期脚本运行中观察到拖拽时额外 idle action，但复跑未复现，暂记为 transient observation，不作为确认 bug 修复。

## FA-TIMER-001

Bug ID：FA-TIMER-001
版本来源：v0.1-v0.55
模块：QTimer / QPropertyAnimation / worker
严重等级：P2
标题：多 QTimer 链路叠加，需要动态验证是否重复启动或互相打断
现象：静态扫描发现 `AnimationManager.animation_timer`、`Typewriter` 三个 timer、`IdleManager.timer`、`IdleBehavior.timer`、`InteractionDetector` 两个 timer、`ReminderManager.timer`、`TimeEventManager.timer`、`AppController._drag_debounce`、`SnapController._anim`。
复现步骤：静态扫描 `QTimer`、`.start(`、`.connect(`。
预期结果：每个 timer 有明确 owner、启动条件、停止条件。
实际结果：部分 timer 有保护，仍需动态验证高频点击、拖拽、API 回复、设置中心打开等组合场景。
影响范围：打字机、动作帧、idle、拖拽判定、提醒、整点报时、吸附动画。
可能原因：多版本叠加。
涉及文件：`src/animation_manager.py`, `src/typewriter.py`, `src/idle_manager.py`, `src/behavior/*.py`, `src/reminder_manager.py`, `src/time_event_manager.py`, `src/app.py`
涉及函数：各 timer 初始化和 `start()` 调用点
是否影响启动：否
是否影响 API：可能，API 回复期间 idle/timer 可能干扰 UI
是否影响角色：否
是否影响动作：是
是否影响事件：是
是否影响行为：是
是否影响打包：否
建议修复方式：先建立 timer 矩阵和动态复现，再按单 bug 修复。
是否建议立即修复：否，先测试
状态：Open
第二阶段动态结果：连续单击 10 次、连续双击 5 次、长文本 typewriter、连续 reload 3 次均通过；未发现重复写历史、重复 signal 注册、UI 卡顿或临时状态永久卡住。状态保持 Open 是因为仍建议后续补充更长 wall-clock 观察，但本阶段没有足够证据触发 Timer 修复。

## FA-CHAR-001

Bug ID：FA-CHAR-001
版本来源：v0.53
模块：多角色系统 / 测试角色包
严重等级：P2
标题：`characters/test_dummy/` 本地测试包策略未明确
现象：早期 `git status --short` 显示 `?? characters/test_dummy/`，本地角色包校验通过，但不在 Git。
复现步骤：执行 `git status --short` 与 `validate_character_pack.py characters\test_dummy`。
预期结果：如果 v0.53 要求公开 `test_dummy`，应进入仓库并定义 assets 策略；如果不公开，应从审计范围标为本地测试夹具。
实际结果：v0.56 已确认 `test_dummy` 为 local-only，加入 `.gitignore`，正式回归不依赖它。
影响范围：多角色 fallback 审计、clean clone 测试、文档一致性。
可能原因：测试角色包在本地生成但未提交。
涉及文件：`characters/test_dummy/`, `.gitignore`
涉及函数：`core.character_loader.safe_load_character`, `CharacterPackEditor`
是否影响启动：否
是否影响 API：否
是否影响角色：否，正式 fallback 依赖 `characters/template`
是否影响动作：否，local-only dummy 不参与正式动作回归
是否影响事件：可能
是否影响行为：否
是否影响打包：否，release/zip 不包含 `characters/test_dummy/`
建议修复方式：已执行：`.gitignore` 增加 `characters/test_dummy/`，`docs/character_pack_guide.md` 明确 clean clone 不要求它存在，正式回归只要求 daniya/template。
是否建议立即修复：已修复
状态：Resolved(local-only)
第二阶段动态结果：`characters/test_dummy/` 当前内容为占位测试角色包，YAML 主要为“待填写/阶段 1”，assets 为 public placeholder 的 `normal1.png`/`normal2.png`。v0.56 决策为 local-only，不提交、不发布、不作为正式回归必过项。

## AUDIT-SIDE-EFFECT-001

Bug ID：AUDIT-SIDE-EFFECT-001
版本来源：v0.56 审计执行
模块：测试自动化 / 运行态保护
严重等级：P1
标题：临时脚本误删 ignored `data/` 与 `config/api_config.json`
现象：一次临时自动化脚本在恢复逻辑中发生二次 restore，误删 ignored `data/` 与 `config/api_config.json`。
复现步骤：该事故来自一次性临时脚本，不作为常规复现步骤保留。
预期结果：缺文件/坏文件测试应先备份或在临时沙盒中执行，中断后可恢复。
实际结果：已重新生成安全默认 `data/` 与 `config/api_config.json`，但旧本地运行态历史无法从 Git 恢复。
影响范围：本地运行态历史；不影响 Git，不影响 release/zip。
可能原因：破坏性 fallback 测试缺少统一 backup/restore 策略。
涉及文件：`data/`, `config/api_config.json`, `docs/DESTRUCTIVE_TEST_POLICY.md`, `tools/backup_runtime_state.py`, `tools/restore_runtime_state.py`
是否影响启动：否，默认文件已补齐
是否影响 API：可能，若用户原本的 ignored `config/api_config.json` 有本地配置，需要用户自行恢复
是否影响角色：否
是否影响动作：否
是否影响事件：否
是否影响行为：否
是否影响打包：否
建议修复方式：v0.56 新增数据保护政策与 backup/restore 工具，后续破坏性测试必须使用临时沙盒或备份恢复。
是否建议立即修复：已修复流程缺口；旧数据不伪造恢复
状态：Resolved(policy/tooling)

## FA-CONFIG-001

Bug ID：FA-CONFIG-001
版本来源：v0.1-v0.55
模块：配置 / 运行态
严重等级：P2
标题：`config/app_config.json` 被 Git 跟踪且包含运行态窗口坐标
现象：`config/app_config.json` 是 tracked 文件，包含 `window.start_x/start_y`、行为开关等，运行 GUI/验收脚本可能改动坐标并污染工作树。
复现步骤：静态读取 `config/app_config.json` 和 `git ls-files config/app_config.json`。
预期结果：默认配置与用户运行态配置应分离，或者运行时只写 ignored user config。
实际结果：默认配置和运行态配置仍有混用风险。
影响范围：开发者工作树、发布默认配置、回归脚本。
可能原因：早期版本直接使用 `config/app_config.json` 作为可写配置。
涉及文件：`config/app_config.json`, `src/config_manager.py`
涉及函数：`ConfigManager.load_app_config`, `save_app_config`
是否影响启动：否
是否影响 API：否
是否影响角色：可能，`current_character`
是否影响动作：可能，行为/动作配置
是否影响事件：否
是否影响行为：是
是否影响打包：可能，默认坐标被打包
建议修复方式：后续设计 user config 与 example config 分离；本轮只记录。
是否建议立即修复：否，涉及兼容性
状态：Open

## FA-REL-001

Bug ID：FA-REL-001
版本来源：v0.44-v0.55
模块：本地 release 产物
严重等级：P3
标题：本地 `release/` 存在旧 v0.44 产物，可能干扰人工发布判断
现象：静态列目录发现 `release/DaniyaSummerPet-v0.44-win-x64/` 和 zip。
复现步骤：`Get-ChildItem release -Recurse`
预期结果：发布审计时只判断当前版本产物。
实际结果：本地存在历史版本产物。
影响范围：人工检查、误读 zip 结构。
可能原因：历史打包遗留。
涉及文件：`release/`
涉及函数：不适用
是否影响启动：否
是否影响 API：否
是否影响角色：否
是否影响动作：否
是否影响事件：否
是否影响行为：否
是否影响打包：可能影响人工判断
建议修复方式：打包测试前清理或明确只检查当前 package name。
是否建议立即修复：否
状态：Open

## FA-DEBUG-001

Bug ID：FA-DEBUG-001
版本来源：v0.55
模块：本地调试产物
严重等级：P3
标题：本地存在 `run_verify.py` 与 `drag_debug.log`
现象：根目录存在本地拖拽调试脚本和日志，已被 `.gitignore` 覆盖。
复现步骤：根目录文件列表与 `git check-ignore`。
预期结果：调试脚本/日志不进入 Git，不干扰用户。
实际结果：Git 安全，但本地文件仍存在。
影响范围：人工目录审计、误运行调试脚本。
可能原因：v0.55 行为引擎验收遗留。
涉及文件：`run_verify.py`, `drag_debug.log`
涉及函数：不适用
是否影响启动：否
是否影响 API：否
是否影响角色：否
是否影响动作：否
是否影响事件：否
是否影响行为：否
是否影响打包：若手动复制根目录可能有干扰；`pack.bat` 当前不直接复制根目录脚本
建议修复方式：保持忽略；最终发布前可删除本地文件。
是否建议立即修复：否
状态：Open

## FA-DOC-001

Bug ID：FA-DOC-001
版本来源：v0.1-v0.55
模块：审计文档
严重等级：P4
标题：历史版本报告很多，full audit 需要建立单一索引
现象：`docs/` 已有大量版本报告，新 full audit 会与历史报告并存。
复现步骤：`Get-ChildItem docs -File`
预期结果：有总览入口说明哪些报告是历史，哪些是当前主报告。
实际结果：本次正在生成 full audit；后续可优化目录索引。
影响范围：维护体验。
可能原因：多轮 AI/人工迭代积累。
涉及文件：`docs/`
涉及函数：不适用
是否影响启动：否
是否影响 API：否
是否影响角色：否
是否影响动作：否
是否影响事件：否
是否影响行为：否
是否影响打包：否
建议修复方式：后续追加 `docs/README.md` 或索引页。
是否建议立即修复：否
状态：Known
