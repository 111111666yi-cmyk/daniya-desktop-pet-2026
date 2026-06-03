# VERSION_LOG — Daniya Summer Pet

本文档记录架构级变更。细节见 `git log`。

---

## Unreleased v0.61-v0.65 review hardening

- 新增 `tools/check_public_surface.py`，把公开文案、本机路径、静默默认值和记忆清空入口纳入自动审查。
- 默认关闭闲聊、整点提醒、边缘探头和空闲小动作，降低首次运行时“自己动/自己说”的风险。
- 空闲小动作的配置下限统一为 600 秒，避免用户开启后出现高频打扰。
- 记忆备忘录增加清空入口；清空范围覆盖自动记忆和手动备忘，不重置关系状态。
- Provider 消息构造测试覆盖用户档案与记忆备忘录注入，确保云端和本地文本 Provider 共用同一上下文入口。

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
