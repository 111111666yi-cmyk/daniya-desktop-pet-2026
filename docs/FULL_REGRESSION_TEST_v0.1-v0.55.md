# FULL_REGRESSION_TEST v0.1-v0.55

审计阶段：第一阶段，只读静态审计
基准提交：`db7af9b`

## 状态说明

- PASS：第一阶段静态检查通过。
- FAIL：第一阶段静态检查发现明确失败。
- BLOCKED：需要 GUI、网络、打包、破坏性文件操作或用户环境，本阶段未执行。
- NOT RUN：排查书要求的后续阶段测试，第一阶段禁止进入。

## 静态测试结果

| 编号 | 测试目标 | 操作步骤 | 预期结果 | 实际结果 | 状态 | 证据 | 相关 Bug |
|---|---|---|---|---|---|---|---|
| RT-001 | 根目录结构 | 检查 main/requirements/bat/docs/src/config/data/assets/characters | 必需路径存在 | 全部存在 | PASS | `Test-Path` 清单 | 无 |
| RT-002 | Python 版本 | `python --version`, `.venv\Scripts\python.exe --version` | Python 3.10+ | 3.10.11 | PASS | 命令输出 | 无 |
| RT-003 | pip 版本 | `.venv\Scripts\pip.exe --version` | pip 可用 | pip 26.1.1 | PASS | 命令输出 | 无 |
| RT-004 | Git 敏感路径 | `git ls-files .env data assets/private models backups dist build release config/api_config.json 'characters/*/assets/*'` | 无敏感跟踪，仅允许 template assets | 仅 `characters/template/assets/*` | PASS | 命令输出 | 无 |
| RT-005 | `.gitignore` 覆盖 | `git check-ignore` | `.env`, data, release, ignored config 等被忽略 | 均被规则覆盖 | PASS | `.gitignore` 行 2/7/17/27/28/53-55 | 无 |
| RT-006 | 配置解析 | Python json/yaml/utf8 读取 | 配置可解析 | app/api/model/multimodal/profile/system prompt 均 OK | PASS | 解析脚本输出 | FA-CONFIG-001 |
| RT-007 | 角色包校验 daniya | `validate_character_pack.py characters\daniya` | OK | OK | PASS | 命令输出 | 无 |
| RT-008 | 角色包校验 template | `validate_character_pack.py characters\template` | OK | OK | PASS | 命令输出 | 无 |
| RT-009 | 角色包校验 test_dummy（local-only 可选） | `validate_character_pack.py characters\test_dummy` | 本地存在时可校验；正式回归不要求 | 本地 OK；clean clone 不要求存在 | OPTIONAL(local) | 命令输出 / v0.56 策略 | FA-CHAR-001 |
| RT-010 | 模块 AST 索引 | Python AST 扫描 src/core | 能解析模块 | 76 个 src/core Python 文件完成索引 | PASS | AST 输出 | FA-STATE-001, FA-TIMER-001 |
| RT-011 | QTimer/Signal 静态扫描 | `Select-String QTimer/.connect/QThread` | 找到 owner | 找到多 timer/worker | PASS(risk found) | 扫描输出 | FA-TIMER-001 |
| RT-012 | 打包脚本静态安全 | 读取 `pack.bat` | 不复制 ignored 本地配置 | 发现复制整个 config/docs | FAIL(static) | `pack.bat --add-data "config;config"` | FA-PKG-001, FA-PKG-002 |
| RT-013 | tracked secret scan | 对 `git ls-files` 扫描 key pattern | 无真实 key | 命中示例 key 与测试 fixture | PASS(with note) | `.env.example`, README, tests | 无 |
| RT-014 | 本地 release 状态 | `Get-ChildItem release` | 当前审计能区分历史产物 | 发现 v0.44 旧产物 | PASS(risk found) | 目录输出 | FA-REL-001 |

## 启动审计测试矩阵

| 编号 | 测试目标 | 操作步骤 | 预期结果 | 实际结果 | 状态 | 相关 Bug |
|---|---|---|---|---|---|---|
| RT-START-001 | `run.bat` 常规启动 | `run.bat` | GUI 启动 | 第一阶段未运行 | BLOCKED | 无 |
| RT-START-002 | 无 `.env` 启动 | 临时移走 `.env`, run.bat | local fallback, 不崩溃 | 第一阶段未运行 | BLOCKED | 无 |
| RT-START-003 | 空 Key 启动 | `.env` Key 为空, run.bat | local fallback | 第一阶段未运行 | BLOCKED | 无 |
| RT-START-004 | 错 Key 启动 | `.env` Key 错误, run.bat | API fallback, 不泄露 Key | 第一阶段未运行 | BLOCKED | 无 |
| RT-START-005 | 正确 Key 启动 | `.env` Key 正确, run.bat | source=api, UI 不冻结 | 第一阶段未运行 | BLOCKED | 无 |

## 主链路回归矩阵

| 编号 | 测试目标 | 操作步骤 | 预期结果 | 实际结果 | 状态 | 相关 Bug |
|---|---|---|---|---|---|---|
| RT-UI-001 | 透明窗口/无边框/置顶 | 启动 GUI | 正常显示 | 第一阶段未运行 | BLOCKED | 无 |
| RT-UI-002 | 左键拖拽 | 鼠标拖动 | 不误判/不消失 | 第一阶段未运行 | BLOCKED | FA-STATE-001, FA-TIMER-001 |
| RT-UI-003 | 右键菜单逐项 | 打开菜单各项 | 均可打开保存 | 第一阶段未运行 | BLOCKED | 无 |
| RT-CHAT-001 | 普通对话 | 输入“你好/你是谁/技术问题” | API/local 正确，历史写入 | 第一阶段未运行 | BLOCKED | 无 |
| RT-SPECIAL-001 | 特殊触发 | 抱抱/晚安/我好累/任务混合 | 不误吞任务 | 第一阶段未运行 | BLOCKED | FA-STATE-001 |
| RT-ROLE-001 | current_character 切换 | daniya/template/not_exist | fallback 不崩溃，正式 fallback 依赖 template | 第一阶段未运行 | BLOCKED | FA-CHAR-001 |
| RT-EVENT-001 | hidden command 路由 | `/pet status/reload/event/sleep/wake` | 不进 API | 第一阶段未运行 | BLOCKED | 无 |
| RT-BEH-001 | 单击/双击/长按/拖拽 | 鼠标操作 | 不误判，不刷好感 | 第一阶段未运行 | BLOCKED | FA-TIMER-001 |
| RT-ACTION-001 | 动作缺资源 fallback | 临时移除/损坏 manifest/png | fallback 不崩溃 | 第一阶段未运行 | BLOCKED | 无 |
| RT-SET-001 | 设置中心保存 | 修改 provider/key/size/toggles/角色 | 即时生效，不泄露 Key | 第一阶段未运行 | BLOCKED | FA-CONFIG-001 |
| RT-PACK-001 | `pack.bat` | 执行打包 | release 无敏感文件 | 第一阶段未运行；静态发现风险 | BLOCKED | FA-PKG-001, FA-PKG-002 |

## Blocked 项说明

原因：

- 第一阶段明确要求只读静态审计，禁止进入动态启动/GUI/打包/破坏性 fallback 测试。

已完成替代检查：

- 静态读取 `run.bat`、`pack.bat`
- 配置解析
- 角色包校验
- Git 安全检查
- 模块 AST 扫描

仍需用户手动或后续阶段执行：

- GUI 人工/自动化验收
- `.env` 四类启动
- provider 错误场景
- 文件损坏/缺失 fallback
- pack.bat 与 release zip 检查
- 多显示器拖拽

## 第二阶段动态回归结果

更新日期：2026-05-31

| ID | 范围 | 操作 | 结果 | 状态 | 证据 |
|---|---|---|---|---|---|
| RT2-001 | 打包 | `pack.bat` | 成功生成 `release/DaniyaSummerPet-v0.55.2-win-x64` 与 zip | PASS | `scratch/second_phase/package_security_results.json` |
| RT2-002 | release 黑名单 | 扫描 `.env`, `config/api_config.json`, `config/multimodal_config.json`, `data/`, `assets/private/`, `models/`, `docs/v0.51_patch_audit/` | release/dist/zip 均未命中 | PASS | `package_security_results.json` |
| RT2-003 | 真实 Key 扫描 | release 与 zip 文本扫描 | `release_secret_hits=[]`, `zip_secret_hits=[]` | PASS | `package_security_results.json` |
| RT2-004 | run.bat 无 `.env` | 分离方式启动 5 秒后检查进程 | 进程存活，随后关闭并恢复 | PASS | `scenario=no_env alive=True` |
| RT2-005 | run.bat 空 Key | 分离方式启动 5 秒后检查进程 | 进程存活，随后关闭并恢复 | PASS | `scenario=empty_key alive=True` |
| RT2-006 | run.bat 错 Key | 分离方式启动 5 秒后检查进程 | 进程存活，随后关闭并恢复 | PASS | `scenario=wrong_key alive=True` |
| RT2-007 | run.bat 正确 Key | 使用本地原始 `.env` 启动 | 进程存活，随后关闭并恢复 | PASS | `scenario=correct_key alive=True` |
| RT2-008 | ChatClient fallback | 无 `.env` / 空 Key / 错 Key | source 均为 `local`，错误 Key 未出现在日志 | PASS | `scratch/second_phase/chat_probe_results.json` |
| RT2-009 | ChatClient API | 正确 Key | source=`api`, fallback=false | PASS | `chat_probe_results.json` |
| RT2-010 | GUI 主链路 | 透明窗口、拖拽到边缘再拉回、右键菜单、输入框、长文本气泡、设置中心 | 全部通过 | PASS | `scratch/ui_acceptance_v0552/SUMMARY.md` |
| RT2-011 | v0.52 角色体验 | 11 条输入含“抱抱/我好累/晚安 + 任务” | 无任务误吞 | PASS | `scratch/second_phase/route_command_results.json` |
| RT2-012 | v0.54 hidden command | `/pet status/reload/event/sleep/wake` | source=`command`，不调用模型 | PASS | `route_command_results.json` |
| RT2-013 | sleep 后继续技术问题 | `/pet sleep` 后问 TypeError | 后续 source=`model`，未锁死 | PASS | `route_command_results.json` |
| RT2-014 | v0.55 行为 | 单击、双击、长按、小移动、大拖拽、左/右/底边缘、拖出屏幕 | 全部通过 | PASS | `scratch/second_phase/gui_behavior_results.json` |
| RT2-015 | window_state | 保存、缺失、坏坐标 | 均安全回退 | PASS | `gui_behavior_results.json` |
| RT2-016 | 状态/Timer 冲突 | API 回复中、设置中心、拖拽中 idle/random 检查；连续点击/双击；长文本 typewriter；连续 reload | 最终复跑全部通过 | PASS | `gui_behavior_results.json` |
| RT2-017 | exe 冒烟 | 启动 release exe 5 秒 | 进程存活，随后关闭；之后重新打包清理运行态产物 | PASS | `release_exe_alive_after_5s=True` |
| RT2-018 | 单元回归 | `.venv\Scripts\python.exe -m pytest -q` | `209 passed, 3 skipped` | PASS | pytest 输出 |

备注：

- `cmd /c run.bat` 在自动化捕获 stdout 的工具环境中会因 `pythonw` 继承管道句柄而等待；第二阶段使用 `Start-Process cmd.exe /c run.bat` 模拟真实双击启动。
- 一次临时脚本超时后的恢复逻辑误删了 ignored `data/` 与 `config/api_config.json`，随后已重新生成安全默认文件；该副作用不影响 Git 和 release，但旧本地运行态历史无法从 Git 恢复，详见 `CODEX_EXECUTION_LOG.md`。
- v0.56 已新增 `docs/DESTRUCTIVE_TEST_POLICY.md`、`tools/backup_runtime_state.py`、`tools/restore_runtime_state.py`。后续缺文件/坏文件测试必须使用临时沙盒或 backup/restore。
- v0.56 已确认 `characters/test_dummy/` 为 local-only；正式回归必过项只包含 `characters/daniya` 与 `characters/template`。
