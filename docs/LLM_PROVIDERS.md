# LLM Providers Configuration

在 v0.45 架构中，达妮娅正式支持了多模型接入。目前内置以下大模型提供商（Provider）：

## 支持的 Provider

| Provider ID | 显示名称 | 描述 | API Key 环境变量 | 默认 Base URL |
|------------|---------|------|------------------|--------------|
| `deepseek` | DeepSeek | 原生 DeepSeek API，推荐作为主模型 | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` |
| `openai` | OpenAI | 官方 OpenAI 接口 | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `claude` | Claude | Anthropic Messages API，支持其特有的 system prompt 逻辑 | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` |
| `openai_compatible` | OpenAI-Compatible | 其他通用第三方 OpenAI 兼容 API | `OPENAI_COMPATIBLE_API_KEY` | 需手动填写 |
| `local_openai_compatible` | Local OpenAI-Compatible | 本地托管的兼容大模型（如 LM Studio, Ollama），不需要真实 Key | `OPENAI_COMPATIBLE_API_KEY` (非必须) | `http://localhost:1234/v1` 等 |

## 配置文件 (api_config.json)

`api_config.json` 现支持存储所有 Provider 的状态，并由 `active_provider` 控制当前激活的模型：

```json
{
  "active_provider": "claude",
  "providers": {
    "deepseek": {
      "base_url": "https://api.deepseek.com",
      "model": "deepseek-chat",
      "timeout": 20,
      "max_tokens": 360,
      "temperature": 0.8
    },
    "claude": {
      "base_url": "https://api.anthropic.com/v1",
      "model": "claude-3-5-sonnet-20240620",
      "timeout": 30,
      "max_tokens": 1024,
      "temperature": 0.8
    }
  },
  "local_mode": false,
  "chat": {
    "fallback_reply": "达妮娅现在还没有连上大脑，但我已经在这里啦！",
    "api_error_fallback_reply": "达妮娅刚刚走神了一下……但我还在哦。"
  }
}
```

## 安全性声明

达妮娅绝对不会在代码仓库和日志中记录明文的 API Key。
1. 您在设置中心填写的 API Key 会立刻写入 `.env` 文件，该文件已被加入 `.gitignore`。
2. UI 上只会显示脱敏后的 Key，如 `sk-****1234` 或 `<empty>`。
3. 若您不在此处输入 Key，达妮娅将尊重您的操作，并回退到“达妮娅刚刚走神了一下……”模式。
