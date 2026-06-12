# TTS API BYOK 指南

API TTS 模式允许你使用自己的第三方 TTS 服务实现动态文本转语音。

## 前提条件

- 你需要自己在第三方 TTS 平台注册账号
- 你需要自己创建或选择 voice_id
- 你需要自己获取 api_key
- **本项目不出售 API、不代理 API、不提供官方达妮娅 voice_id**

## 支持的平台

| 平台 | 提供商 ID | 说明 |
|------|----------|------|
| Fish Audio | `fish_audio` | 支持声音克隆 |
| MiniMax | `minimax` | 支持多种声音 |
| 自定义 API | `custom` | 任何兼容的 TTS 端点 |

## 配置步骤

1. 打开桌宠 → 设置中心 → 多模态 / 语音
2. 语音模式选择 **API TTS（进阶，自备密钥）**
3. 选择提供商或填写自定义 API 端点
4. 填写 API 密钥（UI 中以 `sk-****xxxx` 遮蔽显示）
5. 填写 voice_id
6. 点击 **测试播放** 验证

## 配置模板

参见 `config/api_tts_config.example.json`：

```json
{
  "mode": "api_tts",
  "provider": "custom",
  "endpoint": "https://your-tts-provider.example.com/v1/tts",
  "api_key": "YOUR_API_KEY_HERE",
  "voice_id": "YOUR_VOICE_ID_HERE",
  "timeout_sec": 30,
  "cache_enabled": true
}
```

## 如何获得达妮娅风格声音

本项目不提供官方达妮娅 voice_id。如果你想在 API 模式下使用达妮娅风格声音：

1. 在你选择的 TTS 平台上使用声音克隆功能
2. 上传你有权使用的参考音频（参见 `assets/voice_clips/daniya_voice_profile.yaml` 了解风格描述）
3. 平台会返回一个 voice_id，将其填入设置中心

如果你没有创建达妮娅风格的 voice_id，API 模式只会使用平台默认声音。

## 安全须知

- **真实 api_key 不得提交到 git**
- UI 中 api_key 始终以 `sk-****xxxx` 形式显示
- 本项目不接收、不存储、不代理用户的 API 音频
- 本项目不会将你的 api_key 发送到除你填写的 endpoint 以外的任何服务器
- `config/api_config.json` 已在 `.gitignore` 中排除
