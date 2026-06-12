# VERSION_LOG — Daniya Summer Pet

本文档记录架构级变更。细节见 `git log`。

---

## v0.82 — 轻量环境与内容感知 (2026-06-12)

- 新增默认关闭的 Open-Meteo 天气感知；坐标必须由用户确认，网络请求在后台线程执行，不使用 API Key。
- 降雨状态可触发低频带伞提醒，设置页展示独立透明雨伞 PNG。
- 媒体感知只扫描受支持播放器的进程名，不读取窗口标题、歌名、歌词、文件名或播放列表。
- 随机事件小剧场从角色包 `ambient_events.json` 读取，默认间隔 30 分钟，支持手动试播。
- 天气、媒体和小剧场都受专注模式统一静默控制，且默认不启动。

---

## v0.81 — 本地养成内容包 (2026-06-12)

- 新增默认关闭的养成中心：每日补给、硬币、背包、喂食、成长等级、衣柜和服装装备。
- 服装解锁同时检查成长等级和好感度，不绕过现有 `AffinityManager`。
- 物品与服装目录进入角色包的 `items.json` / `outfits.json`；模板角色包同步提供结构示例。
- 用户状态只写 ignored 的 `data/growth_state.json`，不进入 Git、发布 ZIP 或 Provider 上下文。
- 设置中心和右键菜单均提供明确入口；未启用时所有改变状态的操作都会被拒绝。

---

## v0.80.1 — 电影式剧情站热修 (2026-06-12)

- 合入 `eee9816` 的电影式玻璃拟态剧情站，保留完整 24 章、章节目录、回忆区和阅读设置。
- 桌宠“剧情”入口通过仅监听 `127.0.0.1` 的随机端口提供本地静态页面，并调用系统默认浏览器。
- Web 文件缺失或浏览器无法启动时继续回退旧 Qt 阅读窗，避免入口完全不可用。
- Windows 打包和 ZIP 扫描新增 `web/story_ui` 页面及背景视频必含检查。
- 不合入功能分支中的 TTS、语音素材、旧配置和重复的流式/档案实现。

---

## v0.80 — v0.75-v0.80 稳定整合候选 (2026-06-11)

- 汇总 v0.75 触发与长回答边界、v0.76 启动和运行态可靠性、v0.77 多屏拖拽吸附，以及 v0.7x 设置/档案补齐，不增加 v0.81+ 功能。
- 统一源码版本、公开配置模板、候选包名、zip 必含清单、README、已知问题、release checklist 和 v0.80 验收文档。
- headless Qt 平台不再调用原生屏幕枚举，修复 Windows Actions 在 offscreen 测试中的堆损坏；真实桌面仍按物理屏幕计算。
- LLM 真流式因整段 speech filter、历史、气泡、fallback 和语音契约尚未具备而延期；TTS 只保留既有接口，不进入独立功能线。
- 候选包继续排除 API Key、用户档案、记忆、聊天历史、运行态、私有素材、模型和缓存，并扫描本机路径泄露。
- 真实 Provider、第二块实体混合 DPI 显示器、物理鼠标手感、SmartScreen、杀软与代码签名保持人工或环境签收。

---

## v0.7x — 设置分层与档案补齐 (2026-06-11)

- 设置中心默认进入简单模式，只保留常用 Provider、桌宠、角色、档案/记忆、提醒和隐私入口；进阶模式恢复全部页面与高级配置。
- 模式切换只改变显示范围，不重置旧设置，也不自动开启文件整理、系统状态、剪贴板等高风险功能。
- 用户档案增加可选的月日生日字段，不保存年份；旧档案缺字段时使用空值，保存时保留未知扩展字段。
- 关系状态继续使用“默认字段合并 + 已有字段优先”的迁移方式，并增加缺字段与扩展字段保留测试。
- 当前 Provider、speech filter、气泡、历史和 fallback 都是整段响应契约，因此本阶段只完成流式技术方案，不加入会暴露未过滤 token 的半成品实现。

---

## v0.77 — 多屏 DPI、拖拽与吸附收尾 (2026-06-11)

- 多屏边界从“所有屏幕外接矩形”改为真实屏幕集合，支持负坐标、左右/上下扩展、屏幕间空洞和跨屏窗口。
- 窗口移动到新屏幕、系统缩放变化或显示器增删时，重新生成对应 DPR 的 pixmap，并把失效位置纠正到可见屏幕。
- 吸附、回弹和 edge peek 以当前屏幕 availableGeometry 为准；快速拖拽缩短回弹时间但保留稳定下限。
- 输入忙碌改为检查实际编辑框焦点或草稿；打开输入、设置中心或进入专注模式会立即收回半隐藏状态。
- 提醒到期只让提醒框临时置顶，不再永久覆盖用户关闭桌宠置顶的选择。
- 自动测试覆盖多屏几何、DPI、保存位置修复、点击/双击/长按/拖拽互斥；物理鼠标与第二台混合 DPI 显示器继续人工签收。

---

## v0.76 — 启动性能与运行态可靠性 (2026-06-11)

- 冷启动诊断覆盖 process、QApplication、运行目录、配置、管理器、角色包、主窗口、首次显示和可选服务九个阶段；默认只进入 debug/诊断输出。
- 首屏显示后才初始化可选服务；设置中心的关系、事件、记忆与系统诊断数据改为进入对应页时加载。
- 未启用的 idle、整点、边缘检测、全局点击、行走和空闲动作定时器不再后台轮询。
- 历史与 event log 增加大小上限和尾部读取；半写 JSONL 自动跳过，坏 JSON 保留备份并回退。
- 配置、首次运行、关系、记忆、提醒和历史替换统一使用临时文件原子写，失败时保留旧文件。
- 新增离线启动计时、运行态恢复和有限长跑检查；真实 30 分钟空闲、Windows RSS/GDI/句柄趋势继续标为人工验收。

---

## v0.75 — 角色触发与长回答边界 (2026-06-11)

- 精确触发与轻微格式变体继续进入角色特殊回应；技术问题和提醒句中的嵌套词不再产生关系、lore 或动作副作用。
- 对话过滤区分陪伴与技术回答：陪伴文本保留短、慢、克制的收束，技术文本保留完整步骤、表格、代码和错误堆栈。
- 陪伴长句截断改为按完整句边界收尾，并记录过滤日志，避免无记录地静默删除大段内容。
- 新增触发句、speech filter 与路由优先级回归测试，保持命令、物理事件、自然提醒和本地 fallback 的既有优先级。

---

## v0.70 — v0.61-v0.70 全链路验收 (2026-06-05)

- 停止新增功能，统一核对提醒、文件整理、系统状态、剪贴板、专注模式、设置中心、右键菜单、角色包、Provider、本地 fallback 和发布包。
- 公开文档、Windows 包名和发布签收统一到 v0.70；发布元数据记录最终外部 zip 哈希。
- 发布包必须包含 v0.70 自动验收记录和人工 QA 清单，并继续排除私有素材、运行态数据、API Key、本机路径与本地测试角色。
- 修复拖拽收尾与趴墙暂停条件不一致的问题：设置中心、说话、输入或专注模式阻止趴墙时，不再留下“窗口半隐藏但停靠状态为空”的异常状态。
- 文件整理器改用 Windows 自带 API 检查隐藏属性，不再依赖开发机额外安装的 `pywin32`，本地与 GitHub 构建保持相同隐私规则。
- 关系状态、用户记忆和事件日志的读取与写入共用锁，并采用临时文件原子替换，避免并发读取把半写入内容误判为损坏数据。
- 对话与物理事件共用串行事务；后台物理事件通过线程安全动画桥接更新状态，不再直接操作 Qt 窗口。
- 文件整理器拒绝敏感/隐藏根目录，预览阶段为同名文件预留唯一目标，执行阶段再次检查路径与目标冲突，防止覆盖和篡改计划。
- 系统网络探测改为单 socket 超时；非 Windows 环境不再访问 `ctypes.windll`；普通“到底……”问题不再误入剧情；新提醒显式保存 `notified=false`。
- 最终测试数字、zip SHA256、exe 烟测和 GitHub Actions 结果记录在 `docs/V0.70_INTEGRATION_ACCEPTANCE.md`。

---

## v0.69 — 角色包与多角色稳定性 (2026-06-05)

- 角色选择器只列出包含 `character.yaml` 的公开角色包，隐藏目录和本地 `test_dummy` 不进入用户界面。
- Daniya 继续使用兼容路径 `relationship_state.json`，其他角色使用独立状态文件；旧版误写入全局文件的其他角色状态会先迁移再恢复 Daniya 默认状态。
- 热重载只保存实际成功加载的角色 ID，fallback 后不会反复保存不存在的角色，也不重建提醒、空闲、事件或反馈管理器。
- 补齐缺 lore、缺失/损坏 story、缺 manifest、缺动作、角色发现与切换数据隔离回归测试。

---

## v0.68 — 反馈调度与动作收尾 (2026-06-05)

- 新增统一被动反馈协调器，集中管理气泡、动作、可选音效入口、冷却和完成后回到 idle。
- 空闲闲聊、整点提示、系统状态、剪贴板与行为引擎随机气泡不再打断拖拽、输入、已有气泡、设置窗口或专注模式。
- 边缘趴墙在说话、输入、拖拽和设置中心打开时暂停，用户主动聊天、点击和重要到期提醒保持即时响应。
- 增加调度互斥、交互保护、专注模式、冷却、接线与动作收尾回归测试。

---

## v0.67 — 达妮娅角色体验回归 (2026-06-05)

- 提醒、文件整理、剪贴板、系统状态和专注模式提示语改由角色包 `speech.yaml` 提供，避免把角色语气硬编码在 Python。
- 清理“本地脑袋”“API 没接稳”等工程视角表达，以及与任务无关的过度玩笑。
- 增加工具提示语回归测试，确保不出现“御主”“剧情模式”等公开面禁用表达。

---

## v0.66 — 统一设置中心整理 (2026-06-05)

- 设置中心从 5 个拥挤大页整理为 12 个明确页签，覆盖模型、桌宠、角色、关系、系统、提醒、文件整理、系统状态、剪贴板、专注模式、隐私和诊断。
- v0.61-v0.65 功能增加当前状态与恢复默认入口，高风险功能继续默认关闭。
- 保留原配置键和运行时接线，不改变旧设置语义，不进入 v0.67 的角色文案调整。

---

## v0.65.2 — Acceptance Package Revision (2026-06-05)

- 统一应用版本、公开配置模板、文档、Git tag 和 Windows 压缩包名称为 `v0.65.2`。
- 基于已验收的 v0.65 功能状态重新打包，不增加 v0.66 功能，不改变产品行为。
- 推送源码 tag 前重新执行仓库检查、release zip 内容扫描和打包 exe 启动烟测。

---

## v0.65.1 — Manual Acceptance Hotfix (2026-06-05)

- 完成本地鼠标模拟验收：启动、安静默认、输入框开关、左右边缘趴墙、Provider 状态、文件整理预览、专注模式、设置持久化和基础 UI 稳定性均通过。
- 修复真实拖拽吸附路径：左右趴墙在渲染帧约束后仍保持半隐藏，不再退化为普通贴边。
- 文件整理预览会把 `assets/private` 等敏感目录记录到 skipped 结果中，避免审计输出看不到被跳过的目录。
- 公开默认配置恢复 `window.show_input=false`，保持首次启动安静，并与 public surface CI 检查一致。

---

## Unreleased — v0.62-v0.65 Wiring Recovery

- 修复 `show_input=false` 后输入框无法恢复的问题：显示输入框时会重新显示 `InputBar` 父控件并展开输入栏。
- 修复左右趴墙退化为普通贴边的问题：`_docked_position(side, visible)` 现在会按 `visible` 宽度把窗口半隐藏到屏幕左右边缘。
- 设置中心新增“输入框”和“左右边缘趴墙”开关，保存后即时作用到主窗口和右键菜单。
- Provider 顶部状态从“绿色生效”改为“当前文本模型 / 本地 fallback / 实时连接看测试结果”三类语义，避免未连通时误判为 PASS。
- `file_organizer_enabled`、`system_status_enabled`、`clipboard_interaction_enabled`、`focus_mode_enabled` 等 v0.62-v0.65 配置项补入默认配置与模板检查。
- v0.62 文件整理助手接入右键菜单与独立预览 Dialog：仅手动选择目录、生成预览、二次确认后执行，move log 写入运行时目录。
- v0.63 系统状态感知接入运行时：默认关闭，间隔/冷却下限由配置校验保证，网络检查默认关闭。
- v0.64 剪贴板互动接入运行时：默认关闭，敏感内容本地拦截，默认不保留剪贴板预览文本。
- v0.65 专注模式接入运行时：默认关闭，可手动/白名单自动进入，并可静默闲聊、整点、边缘趴墙、系统状态和剪贴板提示。

---

## v0.61-v0.65 Integrated Preview (2026-06-04)

- 新增 `tools/check_public_surface.py`，把公开文案、本机路径、静默默认值和记忆清空入口纳入自动审查。
- 默认关闭闲聊、整点提醒、边缘探头和空闲小动作，降低首次运行时“自己动/自己说”的风险。
- 空闲小动作的配置下限统一为 600 秒，避免用户开启后出现高频打扰。
- 记忆备忘录增加清空入口；清空范围覆盖自动记忆和手动备忘，不重置关系状态。
- Provider 消息构造测试覆盖用户档案与记忆备忘录注入，确保云端和本地文本 Provider 共用同一上下文入口。

---

## v0.56-v0.60 Stable Preview Hardening (2026-05-31 → 2026-06-02)

这段内容对应 `stabilize-v0.56-v0.60` 的稳定化工作。内部审计长报告已从公开 `docs/` 面移出，但公开版本日志保留阶段摘要，避免 v0.55.2 后直接跳到 v0.61-v0.65。

### v0.56 — 运行态数据安全与打包加固

- 增加运行态数据安全策略，明确 `.env`、`data/`、`assets/private/`、`models/`、`backups/` 等目录不得被破坏或提交。
- 增加 `tools/backup_runtime_state.py` 与 `tools/restore_runtime_state.py`，用于沙盒化备份/恢复验证。
- 加固 release 打包边界，确保用户运行态数据不进入公开包。

### v0.57 — 人工 QA 冻结清单

- 增加人工 QA 冻结矩阵和 release freeze checklist。
- 将真实鼠标、真实显示器、多显示器、真实 API Key 等项目明确标记为人工签收项，不再用自动化结果冒充 PASS。

### v0.58 — 首次启动向导

- 增加首次启动向导、setup state 管理和设置中心重新打开入口。
- 支持跳过 API 配置并进入 local fallback；API 测试通过后台 worker 执行，不阻塞 UI。
- 首次启动状态在打包模式下写入 AppData 运行时目录。

### v0.59 — 自动化检查与 CI

- 增加敏感文件、角色包、配置模板、文档链接、release zip 等检查工具。
- 增加 GitHub Actions workflow 与 issue/PR 模板，为公开协作和远端验证准备基础门禁。

### v0.60 — 稳定预览包与验收

- 同步版本元数据、打包命名、用户文档、安装/API 配置文档和 release checklist。
- 修复 MiMo/OpenAI-compatible `auth_header=api-key` 路径，Provider 切换改为验证事务，失败不覆盖上一套可用模型。
- 增加 GUI smoke、release exe smoke、zip 扫描、公开文案清理和运行态隔离检查。
- 保留未完成项：真实 Z.AI API、真实多显示器/鼠标手感和人工 GUI 体验仍需人工签收。

---

## v0.55.2 (2026-05-31) — 工程审计补丁

- 修复 `reminder_due` 事件触发词过宽的问题，普通“提醒我……”请求不再被误判为提醒到期事件。
- 为 `/pet status`、`/pet reload`、`/pet event`、`/pet sleep`、`/pet wake` 增加明确的本地命令回应，避免隐藏命令落到“推进到下一周”的默认文案。
- 收紧 `pack.bat` 的角色包打包范围：Daniya 只发布 YAML/lore 文本，公开图片资源只来自 template/placeholder，避免被 Git 忽略的角色素材误入 release。
- 同步 `src/version.py`、示例配置和打包包名到 `v0.55.2`。

---

## v0.55.1 (2026-05-31) — 拖动与贴边锁死修复 (Bugfix Patch)

### 交互层逻辑排斥架构与物理捕获

- **移除轮询监听器**：彻底移除了 `_tick_global_click` 计时器中每 80ms 轮询 `GetAsyncKeyState(0x01)` 来强行释放拖拽的底层设计。改用 Qt 的 `grabMouse()` 独占事件响应机制，由 Qt 保证 `mouseReleaseEvent` 一定在释放时投递到 `PetAvatar`。
- **用户交互防护拦截 (Interacting Blocker)**：在吸边计时器 `_tick_edge_peek` 中引入了精确的拦截器。当以下任一状态发生时，均屏蔽吸边动作：
  - 用户按下鼠标且未松开（由 `InteractionDetector.is_pressed` 物理捕获跟踪）
  - 用户正在拖拽（`is_dragging`）
  - 弹性吸附动画正在运行（`SnapController._anim` 状态为 `Running`）
  - 右键菜单处于打开状态
- **信号总线修复**：修复了 `behavior_engine.py` 直接调用 PySide6 信号对象的崩溃。在 mock 和原生运行环境下兼容通过 `.emit()` 或直接调用的方法。
- **真机模拟验证框架**：创建了 `scratch/physical_mouse_simulation.py` 通过 Windows user32 + Qt 事件投递实现 100% 确定性的真实鼠标拖曳模拟验证。

## v0.55 (2026-05-30) — 行为与交互引擎架构 (Behavior Engine)

### 引入 PetBehaviorEngine (解耦核心交互逻辑)

- **InteractionDetector**：负责分析单击、双击、长按和拖动状态，并对点击和拖拽进行物理阈值隔离（8 像素门槛），彻底解决“点按误触拖拽”导致的界面抖动。
- **SnapController**：接管贴边吸附和弹性回弹属性动画 (`QPropertyAnimation`)，使用配置保存与读取状态文件，防止关闭软件时数据丢失。
- **IdleBehavior**：轻量级闲置行为调度，90s 闲置后触发微小位移或闲置气泡台词，引入冷却时间避免打扰。

---

## v0.49.1 (2026-05-30) — 架构巩固

### 新增：ProviderRegistry（变速箱）

`src/llm/provider_registry.py`

项目中所有 Provider 字符串的 **唯一来源**。禁止在其他文件中硬编码 `"deepseek"` / `"ollama"` 等字面量。

```
Provider.DEEPSEEK          # 常量
ProviderMeta.normalize()   # 任意字符串→规范key (含8个别名)
ProviderMeta.get()         # 取元数据 (url/model/timeout/api_style/…)
ProviderMeta.make_profile_id()   # 生成标准 profile ID
ProviderMeta.service_label_to_key()  # UI标签→key
```

**已接入**：`provider_manager.py`, `settings_manager.py`, `settings_window.py`, `first_run_wizard.py`

### 合并：DeepSeek/OpenAI 边界

`src/llm/boundaries/deepseek_api.py` → 现在是 `openai_api.py` 的 re-export。

DeepSeek 与 OpenAI 共用 `/chat/completions` 端点，唯一差异是 DeepSeek 必传 Bearer auth。合并后逻辑只在一处维护。

```python
# deepseek_api.py (2行)
from .openai_api import chat, test_connection
```

### 新增：推荐模型面板 + 下载助手

**位置**：设置中心 → 模型与引擎 → 本地部署区域

- 4 张推荐模型卡片（Qwen2.5 0.5B/1.5B, Gemma2 2B, Llama3 8B），数据源 `config/model_catalog.json`
- 每张卡片：选择填入 / Ollama拉取 / 官方页面 / 许可证 / 详情
- 「打开内置下载器」→ 模型选择 → **3 个许可证勾选框**（全部勾选后才启用下载）
- 拉取前自动检测 Ollama 是否运行（`_OllamaHealthWorker`）
- 实时进度 + 取消支持（`_OllamaPullWorker`，Popen 逐行读取）
- 下载完成后自动刷新模型列表

### 修复：Provider 配置冲突

- 本地模型保存 **不再覆盖** 云端 active profile（`save_local_model_profile()` 不改变 `active_text_profile_id`）
- UI 顶部显示「当前生效模型」绿色横幅
- 「设为当前模型」按钮 → `ProviderManager.switch_active_profile()`，失败自动回退
- `chat_client.py` **未写死** DeepSeek — 始终读取 `model_profiles.json` → `active_text_profile_id`

### 新增测试

| 文件 | 用例 | 覆盖 |
|---|---|---|
| `tests/test_boundaries.py` | 40 | `_retry_request` 退避重试(12) + openai(8) + ollama(7) + anthropic(6) + 错误继承链(7) |
| `tests/test_provider_registry.py` | 29 | normalize 别名(11) + getter(11) + service_label(2) + profile_id(4) + 往返一致性(3) |

总测试：110 → **179**（+69）

---

## v0.49 (2026-05-29) — 正式开源

### LLM Provider 系统边界重构

删除 8 个旧 `ChatProvider` 类，替换为 4 个边界模块 + 1 个路由层：

| 边界模块 | 端点 | 失败模式 |
|---|---|---|
| `boundaries/openai_api.py` | `/chat/completions` | 401/429/5xx/网络/格式 |
| `boundaries/ollama_api.py` | `/api/chat` | 服务不可达/模型不存在(404) |
| `boundaries/anthropic_api.py` | `/messages` | 401/429/5xx/网络/格式 |

`boundaries/__init__.py` 包含 `_retry_request()`（指数退避，3次重试）+ 错误类层次（全部继承 `BoundaryError`）。

`provider_manager.py` 是纯路由层 — 读 `model_profiles.json`，匹配 provider → 调用对应 boundary。

### v0.415 引擎接入

- `DaniyaEngineAdapter` 将 `ChatClient` 包装为 `DialogueEngine` 所需的 `model_client`
- `ChatWorker` + `PhysicalEventWorker`（QThread 后台）
- `ThreadSafeAnimationManager` 防止 GUI 线程冻结
- 调用链：`send_message → ChatWorker → Adapter → DialogueEngine → ChatClient.reply() → ProviderManager.chat() → boundary`

### 设置中心整合

9 标签页 → **4 标签页**：模型与引擎 / 桌宠 / 角色与资源 / 数据与系统

### P0-P2 修复

- `QGroupBox` 缺失 import
- 事件日志刷新按钮绑定错误
- `ModelNotFoundError` 继承 `BoundaryError`
- `_retry_request` 对 4xx/5xx 抛出类型化错误
- `max_tokens` 配置穿透到边界调用
- 最小化到托盘、窗口最小/最大化按钮

---

## v0.41-v0.48 摘要

| 版本 | 变更 |
|---|---|
| v0.48 RC | 动作资源回退策略、已知问题清零 |
| v0.47 | 动作资产系统（manifest.json）、本地模型下载器占位 |
| v0.46 | 本地模型连接回退、License 确认占位 |
| v0.45 | 缺失（编号跳过） |
| v0.44 | 打包测试（pack.bat, PyInstaller） |
| v0.43 | GitHub 开源准备（.gitignore, 清理敏感文件） |
| v0.42 | 设置中心初版 |
| v0.41 | 动作系统（idle/talk/clicked/drag/sleep/happy/remind） |

---

## 调用链速查

```
用户输入
  → PetWindow.message_submitted
  → AppController.send_message()
  → ChatWorker (QThread)
  → DaniyaEngineAdapter.handle_user_text()
  → DialogueEngine.handle_user_message()
    → PromptBuilder (角色包+lore+历史)
    → ChatClient.reply()
      → ProviderManager.chat()
        → get_active_profile() → model_profiles.json
        → boundary.chat()   (openai_api/ollama_api/anthropic_api)
    → speech_filter
    → relationship_engine
    → action_router
  → reply_ready signal → PetWindow.speak()
```

## 关键文件地图

| 文件 | 角色 |
|---|---|
| `src/app.py` | 入口控制器，组装所有组件 |
| `src/chat_client.py` | ChatClient → ProviderManager 适配器 |
| `src/llm/provider_manager.py` | 路由：读 model_profiles.json → dispatch boundary |
| `src/llm/provider_registry.py` | **唯一真相**：所有 Provider 常量+元数据 |
| `src/llm/boundaries/openai_api.py` | DeepSeek/OpenAI/LM Studio/llama.cpp 共用 |
| `src/llm/boundaries/ollama_api.py` | Ollama `/api/chat` |
| `src/llm/boundaries/anthropic_api.py` | Claude `/messages` |
| `src/settings_manager.py` | 配置读写、api_config.json + model_profiles.json 同步 |
| `src/settings_window.py` | 设置中心 UI（4 标签页） |
| `src/daniya_engine_adapter.py` | v0.415 引擎适配器 |
| `core/dialogue_engine.py` | 对话引擎（lore/speech/relationship/action） |
| `config/model_catalog.json` | 推荐模型目录（4 个模型元数据） |
| `config/model_profiles.json` | 运行时模型配置、active_text_profile_id |
