# VERSION_LOG — Daniya Summer Pet

本文档记录架构级变更。细节见 `git log`。

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
