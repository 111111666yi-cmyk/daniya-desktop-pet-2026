# TTS 语音素材政策

## 可以公开上传

以下内容可以提交到仓库或上传到 GitHub Release：

- 预生成语音包 `daniya_clip_pack_v1.zip`
- `voice_manifest.json`（下载索引与 SHA256）
- `.sha256` 校验文件
- 文档（用户指南、进阶指南、配置说明）
- Placeholder 示例配置（`api_tts_config.example.json`、`local_gpt_sovits_config.example.json`）
- 不含真实密钥的 example json
- 风格描述文件 `daniya_voice_profile.yaml`（不含音频路径）

## 不应该公开上传

以下内容不得提交到仓库、不得上传到 Release、不得包含在构建产物中：

- 未授权的角色原声
- 声优原始音频
- 游戏抽取音频
- GPT-SoVITS runtime
- 模型权重文件（`.ckpt`、`.pth`）
- TTS 推理缓存（`cache/tts/`）
- 真实 API 密钥（`api_key`、`.env`）
- 用户本地路径（任何绝对路径、盘符开头的个人目录）

## .gitignore 保障

仓库 `.gitignore` 已排除：

```
assets/voices/*/
assets/voice_clips/*/
cache/tts/
models/
runtime/
config/api_config.json
config/multimodal_config.json
.env
```

## 可选高级包（未来）

如果以后有完全授权的参考音频，可以单独制作 `daniya_voice_seed_pack_v1.zip`，需要满足：

- 与普通 clip_pack 分开发布
- 包含独立的 `LICENSE`、`README.md`、`CHECKSUMS.sha256`
- 在 `voice_manifest.json` 中作为独立条目
- 明确标注授权来源和使用限制
- 不包含完整模型权重（仅包含参考音频和 prompt）
