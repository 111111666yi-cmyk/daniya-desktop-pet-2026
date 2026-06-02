# v0.57 Manual QA Checklist

## v0.60 Release Package Manual QA - 2026-06-02

Test target: `release/DaniyaSummerPet-v0.60-win-x64.zip`, extracted to a local scratch QA directory. The packaged `DaniyaSummerPet.exe` was launched with isolated temporary AppData/LocalAppData so existing user runtime data was not modified.

Important test isolation note: one older development instance was also running on the desktop (`pythonw.exe main.py`). Results below target the packaged release process only. The older instance was not killed.

| Item | Result | Evidence / Notes |
|---|---|---|
| exe startup | PASS | Packaged exe process stayed alive beyond 15 seconds and displayed the desktop pet. |
| first-run wizard | PASS | Clean AppData launch displayed `达妮娅首次启动向导`; skip/enter-main path worked. |
| Z.AI API real reply | BLOCKED | No Z.AI/Zhipu/GLM provider entry and no Z.AI key were present in the tested release/runtime environment. |
| no-key local fallback | PASS | Clean runtime with no saved key produced `source=local` fallback for `你好`. |
| settings center | PASS | Opened from the release process right-click menu and displayed the v0.60 model/settings UI without freezing. |
| right-click menu | PASS | Menu opened from the release process and submenus were clickable. |
| drag / snap | PASS | Release pet dragged to the left edge, snapped at `L0`, and could be pulled back on-screen. |
| long text bubble visual | NEEDS POLISH | P3 polish item. No live model/Z.AI response was available; local fallback stayed short, so real long-model-response visual QA remains unaccepted. This does not block the v0.60 release candidate. |
| special trigger: 抱抱 | PASS | `抱抱` returned `source=special_response` with the expected local character response. |
| 晚安，顺便提醒我明天喝水 | PASS | Did not create a reminder; `reminders.json` remained `[]`; no `reminder_due` misfire was observed. |
| multi-monitor drag | BLOCKED | Current Windows session exposes only one monitor, so cross-monitor dragging could not be tested. |
| first-run desktop shortcut option | NEEDS POLISH | The guide does not offer an optional `Daniya521` desktop shortcut checkbox. This is UX polish, not a startup blocker. |

更新日期：2026-05-31

本清单用于 v0.57 稳定版冻结验收。所有会破坏运行态的测试必须遵守 `docs/DESTRUCTIVE_TEST_POLICY.md`，优先使用临时 runtime、临时 AppData 或人工记录，不得直接删除真实 `data/`、`.env`、`assets/private/`、`models/`。

| 测试编号 | 测试模块 | 测试步骤 | 预期结果 | 实际结果 | 状态 | 截图或日志路径 | 相关 Bug ID |
|---|---|---|---|---|---|---|---|
| QA57-001 | 启动 | 临时 runtime 中无 `.env` 启动 | 程序可启动，local fallback，不崩溃，不冻结 UI | 待人工记录 | BLOCKED |  |  |
| QA57-002 | 启动 | 临时 runtime 中 `.env` 存在但 Key 为空 | 程序可启动，local fallback，不崩溃 | 待人工记录 | BLOCKED |  |  |
| QA57-003 | 启动 | 临时 runtime 中填写错误 API Key | API 失败后 fallback，不泄露完整 Key | 待人工记录 | BLOCKED |  |  |
| QA57-004 | 启动 | 使用用户确认可用的正确 API Key | API 回复正常，`chat_history` 记录 `source=api`，UI 不冻结 | 需可用 Key | BLOCKED |  |  |
| QA57-005 | 启动 | 断网或临时阻断 API 网络后启动 | API fallback，不崩溃 | 待人工记录 | BLOCKED |  |  |
| QA57-006 | GUI | 检查桌宠窗口 | 透明、无边框、置顶 | 待人工记录 | BLOCKED |  |  |
| QA57-007 | GUI | 拖拽桌宠 | 可拖动，不误触发单击 | 待人工记录 | BLOCKED |  |  |
| QA57-008 | GUI | 拖到左边缘再拉回 | 可吸附，可拉回 | 待人工记录 | BLOCKED |  |  |
| QA57-009 | GUI | 拖到右边缘再拉回 | 可吸附，可拉回 | 待人工记录 | BLOCKED |  |  |
| QA57-010 | GUI | 拖到底部再拉回 | 可吸附，可拉回 | 待人工记录 | BLOCKED |  |  |
| QA57-011 | GUI | 拖出屏幕后释放 | 自动保持可见或拉回屏幕内 | 待人工记录 | BLOCKED |  |  |
| QA57-012 | GUI | 关闭重开 | 位置恢复，不跑出屏幕 | 待人工记录 | BLOCKED |  |  |
| QA57-013 | GUI | 右键桌宠 | 右键菜单正常显示，菜单项可点击 | 待人工记录 | BLOCKED |  |  |
| QA57-014 | GUI | 显示/隐藏输入框 | 输入框不遮挡、不错位 | 待人工记录 | BLOCKED |  |  |
| QA57-015 | GUI | 打开/关闭设置中心 | 设置中心不报错，不阻塞桌宠主窗口 | 待人工记录 | BLOCKED |  |  |
| QA57-016 | GUI | 退出程序 | 进程退出，无后台残留 | 待人工记录 | BLOCKED |  |  |
| QA57-017 | 对话 | 输入“你好” | 有回复，typewriter 正常，写入历史 | 待人工记录 | BLOCKED |  |  |
| QA57-018 | 对话 | 输入“你是谁” | 保持达妮娅角色，不变成通用助手 | 待人工记录 | BLOCKED |  |  |
| QA57-019 | 对话 | 输入“帮我解释一下 Python 报错” | 不被特殊触发吞掉，能处理技术问题 | 待人工记录 | BLOCKED |  |  |
| QA57-020 | 对话 | 输入“帮我整理一下项目计划” | 不重复回复，UI 不冻结 | 待人工记录 | BLOCKED |  |  |
| QA57-021 | 角色 | 输入“达妮娅” | 角色响应正常，历史写入 | 待人工记录 | BLOCKED |  |  |
| QA57-022 | 角色 | 输入“抱抱” | 特殊触发正常，好感度/动作联动正常 | 待人工记录 | BLOCKED |  |  |
| QA57-023 | 角色 | 输入“我好累” | 情绪响应正常，不误判任务 | 待人工记录 | BLOCKED |  |  |
| QA57-024 | 角色 | 输入“我好累，帮我分析这个 Python 报错” | 不误吞任务请求 | 待人工记录 | BLOCKED |  |  |
| QA57-025 | 角色 | 输入“晚安” | sleep/晚安体验正常 | 待人工记录 | BLOCKED |  |  |
| QA57-026 | 角色 | 输入“晚安，顺便提醒我明天喝水” | 不误吞任务，不错误触发 due reminder | 待人工记录 | BLOCKED |  |  |
| QA57-027 | 角色 | 输入“我不会先走” | 不出现身份错乱或固定错误文案 | 待人工记录 | BLOCKED |  |  |
| QA57-028 | 角色 | 输入“我们是不是同一个人” | 保持角色边界 | 待人工记录 | BLOCKED |  |  |
| QA57-029 | 角色 | 输入“你是不是 AI” | 保持设定策略，不变成通用助手 | 待人工记录 | BLOCKED |  |  |
| QA57-030 | Hidden Command | 输入 `/pet status` | 不调用 API，返回本地状态 | 待人工记录 | BLOCKED |  |  |
| QA57-031 | Hidden Command | 输入 `/pet reload` | 不调用 API，角色/动作重载正常 | 待人工记录 | BLOCKED |  |  |
| QA57-032 | Hidden Command | 输入 `/pet event` | 不调用 API，事件状态正常 | 待人工记录 | BLOCKED |  |  |
| QA57-033 | Hidden Command | 输入 `/pet sleep` | 不调用 API，进入 sleep 且不锁死对话 | 待人工记录 | BLOCKED |  |  |
| QA57-034 | Hidden Command | 输入 `/pet wake` | 不调用 API，可恢复对话 | 待人工记录 | BLOCKED |  |  |
| QA57-035 | 行为 | 单击 | 触发 clicked，不误触发 drag | 待人工记录 | BLOCKED |  |  |
| QA57-036 | 行为 | 双击 | 触发 happy，不泄漏单击 | 待人工记录 | BLOCKED |  |  |
| QA57-037 | 行为 | 长按 | 不锁死状态，不误弹事件 | 待人工记录 | BLOCKED |  |  |
| QA57-038 | 行为 | API 回复中等待 idle | idle 不打断 talking | 待人工记录 | BLOCKED |  |  |
| QA57-039 | 行为 | 设置中心打开时等待 idle | idle 不打断设置中心 | 待人工记录 | BLOCKED |  |  |
| QA57-040 | 行为 | 拖拽中等待 random event | random event 不打断 dragging | 待人工记录 | BLOCKED |  |  |
| QA57-041 | 打包 | 执行 `pack.bat` | exe/zip 生成 | 待命令记录 | BLOCKED |  |  |
| QA57-042 | 打包 | 扫描 release zip | 不含敏感文件、test_dummy、data、private assets、models | 待命令记录 | BLOCKED |  |  |
| QA57-043 | 打包 | 启动 release exe | 可启动，运行态写入 AppData | 待命令记录 | BLOCKED |  |  |

## P0 / P1 / P2 处理规则

- P0：停止发布，写入 `docs/FULL_BUG_LIST_v0.1-v0.55.md` 或后续 bug list，不进入 v0.58。
- P1：停止发布，只修该问题，修完重跑 v0.57。
- P2：判断是否阻塞发布；阻塞则修，不阻塞则写入 `docs/KNOWN_ISSUES.md`。
- P3/P4：写入 `docs/KNOWN_ISSUES.md`，不阻塞 v0.58。
