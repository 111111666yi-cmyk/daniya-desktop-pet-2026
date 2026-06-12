# TTS 本地 GPT-SoVITS 指南

本地 GPT-SoVITS 模式允许你在本机运行 TTS 推理服务，实现动态文本转语音。这是最灵活但也最复杂的方案。

## 前提条件

- 用户自行安装 GPT-SoVITS runtime
- 用户自行准备模型权重（`.ckpt`、`.pth`）或参考音频（`ref_audio.wav`）
- 用户自行启动本地 API 服务
- **本项目不打包 runtime / model / cache**
- **本项目不保证复刻任何特定真人或角色声线**

## 配置步骤

1. 安装 GPT-SoVITS（参见其官方文档）
2. 准备你的模型文件或参考音频
3. 启动本地 API 服务，默认地址 `http://127.0.0.1:9880`
4. 打开桌宠 → 设置中心 → 多模态 / 语音
5. 语音模式选择 **本地 GPT-SoVITS 动态合成（进阶）**
6. 填写 endpoint（本地 API 地址）
7. 填写 voice_id（你在本地配置的声线 ID）
8. 点击 **检查 GPT-SoVITS 服务** 确认引擎在线
9. 点击 **测试播放** 验证

## 配置模板

参见 `config/local_gpt_sovits_config.example.json`：

```json
{
  "mode": "local_gpt_sovits",
  "endpoint": "http://127.0.0.1:9880",
  "voice_id": "your_voice_id",
  "ref_audio_path": "/path/to/your/ref_audio.wav",
  "prompt_text": "参考音频对应的文本内容",
  "prompt_lang": "zh",
  "text_lang": "zh",
  "speed_factor": 0.95,
  "temperature": 0.8,
  "top_k": 15,
  "top_p": 0.9
}
```

## 如何获得达妮娅风格声音

本项目不提供模型权重或参考音频。如果你想使用达妮娅风格声音：

1. 参阅 `assets/voice_clips/daniya_voice_profile.yaml` 了解风格参数
2. 准备你有权使用的参考音频
3. 使用 GPT-SoVITS 训练或零样本推理
4. 推荐参数：speed_factor 0.92-0.98, temperature 0.75-0.9

风格描述只是方向参考，**没有 ref_audio / model / prompt_text，本地模式不可能知道目标音色**。

## 用户需要自行准备的文件

| 文件 | 说明 |
|------|------|
| GPT-SoVITS runtime | 推理引擎，从官方仓库获取 |
| `.ckpt` (GPT 权重) | GPT 模型文件 |
| `.pth` (SoVITS 权重) | SoVITS 模型文件 |
| `ref_audio.wav` | 参考音频 |
| `prompt.txt` | 参考音频对应的文本 |

## 安全须知

- ref_audio 必须是你有权使用的音频
- **不要上传未授权的角色原声、声优原始音频、游戏抽取音频**
- 本项目不打包、不分发 runtime / model / cache
- 本项目不公开分发未授权声音素材
- 所有本地文件路径仅保存在你本地的 `config/app_config.json` 中，不会上传
