# FULL_FIX_PLAN v0.1-v0.55

审计阶段：第一阶段，只读静态审计
状态：仅计划，不修复

## 修复顺序总览

第一批 P0：

- 当前第一阶段未发现 P0。

第二批 P1：

- FA-PKG-001：`pack.bat` 复制 ignored 本地配置。

第三批 P2：

- FA-PKG-002：`pack.bat` 复制 ignored 本地审计截图目录。
- FA-STATE-001：多个状态 owner 缺显式优先级。
- FA-TIMER-001：多 QTimer/animation/worker 需动态复核。
- FA-CHAR-001：`characters/test_dummy/` 仓库态未决。
- FA-CONFIG-001：tracked `app_config.json` 与运行态混用。

第四批 P3：

- FA-REL-001：本地旧 release 产物干扰。
- FA-DEBUG-001：本地 debug 脚本与日志。

P4：

- FA-DOC-001：历史报告索引优化。

## 修复项：FA-PKG-001

修复目标：确保 release 不包含 ignored 本地配置。
对应 Bug ID：FA-PKG-001
最小修改范围：`pack.bat`
涉及文件：`pack.bat`, possibly `config/app_config.example.json`
风险：修改打包脚本可能导致 release 缺少必要默认配置。
回滚方法：恢复 `pack.bat` 到 `db7af9b` 后重新运行打包。
修复后测试：

- `pack.bat`
- 检查 release 中不存在 `.env`, `config/api_config.json` 本地版, `config/multimodal_config.json`
- exe 冒烟

是否需要更新文档：是，更新 `PATH_AND_PACKAGING_AUDIT.md` 与 regression test。
状态：Done in second stage
实际修改：`pack.bat` 使用 `%TEMP%` 下的临时白名单 package input；只复制公开默认 config，并显式删除 forbidden config。
验证结果：release/dist/zip 均不包含 `.env`, `config/api_config.json`, `config/multimodal_config.json`, `data/`, `assets/private/`, `models/`。

## 修复项：FA-PKG-002

修复目标：确保 release 不包含 ignored 本地审计截图目录。
对应 Bug ID：FA-PKG-002
最小修改范围：`pack.bat`
涉及文件：`pack.bat`, `.gitignore`
风险：文档复制白名单过窄可能漏掉用户帮助文档。
回滚方法：恢复 docs 复制规则。
修复后测试：

- `pack.bat`
- 检查 release/docs 不含 `v0.51_patch_audit`

是否需要更新文档：是
状态：Done in second stage
实际修改：`pack.bat` 使用临时 docs 白名单目录，并排除 `v0.51_patch_audit`, `screenshots`, `debug`, `debug_logs`, `tmp`, `*.tmp`, `*.log`, `debug_*`。
验证结果：release/dist/zip 均不包含 `docs/v0.51_patch_audit/`。

## 修复项：FA-STATE-001

修复目标：确认并修复状态抢占。
对应 Bug ID：FA-STATE-001
最小修改范围：待动态复现后决定。
涉及文件：`src/app.py`, `src/animation_manager.py`, `src/behavior/behavior_engine.py`, `src/pet_window.py`
风险：过早改状态机会破坏透明窗口、拖拽、typewriter、API 回复。
回滚方法：逐 bug 小提交回滚。
修复后测试：

- API 回复中等待 idle
- 拖拽中触发 idle/random/remind
- 设置中心打开时 idle
- sleep 后技术问题

是否需要更新文档：是，更新 `STATE_MACHINE_AUDIT.md`
状态：Dynamic tests passed; no state-machine code change in second stage
第二阶段结果：API 回复、设置中心、拖拽中 idle/random 检查均通过；长文本 typewriter 可回 idle；sleep 后技术问题不锁死。未获得稳定复现证据，因此未修改状态机。

## 修复项：FA-TIMER-001

修复目标：确认 timer 是否重复启动、互相覆盖或泄露。
对应 Bug ID：FA-TIMER-001
最小修改范围：待动态复现后决定。
涉及文件：`src/typewriter.py`, `src/animation_manager.py`, `src/behavior/*.py`, `src/app.py`, `src/reminder_manager.py`, `src/time_event_manager.py`
风险：timer 修改易引入卡 idle、口型不动、提醒不触发。
回滚方法：逐模块小补丁回滚。
修复后测试：

- 单击/双击/长按/拖拽组合
- 长文本 typewriter
- reminder due
- hourly chime
- idle behavior

是否需要更新文档：是
状态：Dynamic tests passed; no timer code change in second stage
第二阶段结果：连续单击 10 次、连续双击 5 次、长文本 typewriter、连续 reload 3 次均通过。未获得稳定复现证据，因此未修改 Timer。

## 修复项：FA-CHAR-001

修复目标：确定 `test_dummy` 是否公开入仓。
对应 Bug ID：FA-CHAR-001
最小修改范围：文档/角色包归属决策。
涉及文件：`characters/test_dummy/`, `.gitignore`, `docs/character_pack_guide.md`
风险：强行提交 assets 可能违反 asset policy；不提交可能让 v0.53 文档与 clean clone 不一致。
回滚方法：移除提交或恢复忽略策略。
修复后测试：

- `validate_character_pack.py characters\test_dummy`
- clean clone 角色切换测试

是否需要更新文档：是
状态：Needs user decision
第二阶段观察：当前 `test_dummy` 是本地占位测试包，assets 是 placeholder 图；本阶段未提交，等待用户决定。

## 修复项：FA-CONFIG-001

修复目标：分离默认配置与用户运行态配置。
对应 Bug ID：FA-CONFIG-001
最小修改范围：先设计，不立即改。
涉及文件：`src/config_manager.py`, `config/app_config.json`, `config/app_config.example.json`
风险：配置迁移可能影响所有用户启动。
回滚方法：恢复原配置路径。
修复后测试：

- 无 config 启动
- 损坏 config 启动
- 设置中心保存重启
- 打包后首次启动

是否需要更新文档：是
状态：P2 later

## 暂不修复

- FA-REL-001：本地 release 旧产物；第二阶段打包前清理即可。
- FA-DEBUG-001：本地 debug 文件已 ignore；可手动删除但不影响仓库。
- FA-DOC-001：文档索引优化，不影响主链路。
