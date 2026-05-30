# LLM Provider 架构

v0.49.1 架构 — 边界模块 + ProviderRegistry + ProviderManager 路由。

## Provider 列表

| Key | 类型 | 端点 | 边界模块 |
|---|---|---|---|
| `deepseek` | 云端 | `/chat/completions` | `openai_api.py` |
| `openai` | 云端 | `/chat/completions` | `openai_api.py` |
| `claude` | 云端 | `/messages` | `anthropic_api.py` |
| `ollama` | 本地 | `/api/chat` | `ollama_api.py` |
| `lm_studio` | 本地 | `/chat/completions` | `openai_api.py` |
| `llama_cpp` | 本地 | `/chat/completions` | `openai_api.py` |
| `local_openai_compatible` | 本地 | `/chat/completions` | `openai_api.py` |

全部 Provider 字符串从 `src/llm/provider_registry.py` 导入，禁止硬编码。

## 调用链

`ChatClient.reply()` → `ProviderManager.chat()` → 读 `model_profiles.json` `active_text_profile_id` → dispatch 对应 `boundary.chat()`

## 配置文件

- `config/api_config.json` — 用户可见 API 设置（兼容层）
- `config/model_profiles.json` — ProviderManager 真实读取的 profile 配置
- `.env` — API Key 存储，不进 Git
- `config/model_catalog.json` — 推荐本地模型目录（元数据，不含权重）

## 错误处理

所有边界异常继承 `BoundaryError`（`boundaries/__init__.py`）：
`AuthError` | `RateLimitError` | `ServerError` | `NetworkError` | `MalformedResponse` | `ModelNotFoundError`

`_retry_request()` 对 429/502/503/504/连接错误 自动指数退避重试（最多 3 次）。

## 安全

- API Key 只存 `.env`，不入 JSON，不进 Git
- UI 只显示脱敏 Key（`sk-****1234`）
- 下载模型前必须确认许可证（3 个勾选框）
