# TTS 进阶指南

本项目支持三种语音路线：

| 模式 | 适合谁 | 需要什么 | 能做什么 |
|------|--------|---------|---------|
| **clip_pack** | 普通用户 | 下载语音包 | 播放预录语音 |
| **api_tts (BYOK)** | 有 API 账号的用户 | 第三方 TTS API 密钥 | 动态文本转语音 |
| **local_gpt_sovits** | 本地部署玩家 | GPT-SoVITS runtime + 模型 | 本地动态合成 |

## 重要：项目不会凭空知道达妮娅音色

达妮娅的声音不是代码能产生的。音色来源只有以下三种：

1. **预生成 clip_pack**：由维护者预先录制/生成的 WAV 文件，打包为 `daniya_clip_pack_v1.zip`
2. **第三方平台 voice_id**：用户在 Fish Audio / MiniMax / ElevenLabs 等平台自行创建或克隆的声音 ID
3. **本地 GPT-SoVITS 模型/参考音频**：用户自行准备的 `.ckpt`、`.pth`、`ref_audio.wav` 等文件

**频率表、风格描述、参数推荐** 只能辅助调音方向，不能替代 voice_id / ref_audio / model。没有这些素材，API 模式只会输出平台默认声音，本地模式无法启动。

## 各模式详细指南

- 普通用户：[TTS_USER_GUIDE.md](TTS_USER_GUIDE.md)
- API BYOK：[TTS_BYOK_API_GUIDE.md](TTS_BYOK_API_GUIDE.md)
- 本地 GPT-SoVITS：[TTS_LOCAL_GPT_SOVITS_GUIDE.md](TTS_LOCAL_GPT_SOVITS_GUIDE.md)

## 模式切换

三种模式的配置互相独立。切换模式不会丢失其他模式的设置（API 密钥、voice_id、本地端点等都会保留）。

## 镜像下载

语音包支持多个下载源。`voice_manifest.json` 中的 `urls` 数组可以包含多个镜像地址，程序会按顺序尝试直到成功。无论从哪个源下载，都必须通过 SHA256 校验。

用户也可以手动下载 zip 后离线导入，不依赖任何在线服务。

## 安全原则

- 本项目不出售、不代理、不提供任何 TTS API 服务
- 本项目不存储、不转发用户的 API 密钥到任何第三方
- 本项目不打包 GPT-SoVITS runtime、模型权重、推理缓存
- 本项目不公开分发未授权的角色原声、声优音频、游戏抽取音频
- API 密钥在 UI 中始终以 `sk-****xxxx` 形式遮蔽显示
