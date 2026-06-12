# TTS 发布检查清单

每次更新语音包或 TTS 相关代码时，依照此清单确认。

## 语音包发布

- [ ] `daniya_clip_pack_v1.zip` 已从本地验证通过的目录重新打包
- [ ] SHA256 已计算并写入 `voice_manifest.json`
- [ ] `size_bytes` 已更新
- [ ] `download_url` 和 `urls` 指向正确的 Release / 镜像地址
- [ ] GitHub Release 上的 zip 已替换为最新版本
- [ ] 下载后 SHA256 与 manifest 一致（手动验证）

## 代码发布

- [ ] `pytest` 全量通过
- [ ] 默认 `pack.bat`（不设置 `INCLUDE_VOICE_CLIPS`）构建成功
- [ ] 默认 release zip 不含 voice_clips / wav / model / cache / runtime
- [ ] `INCLUDE_VOICE_CLIPS=1` 构建成功，仅含 clip_pack，不含 runtime / model / cache
- [ ] `tools/check_release_zip.py` 验证通过：无 forbidden entries、无 secrets、无 local paths

## 安全检查

- [ ] 文档中无本机绝对路径（如盘符开头的用户目录、临时目录等）
- [ ] 文档中无真实 API key
- [ ] `.gitignore` 排除 `assets/voice_clips/*/`、`assets/voices/*/`、`cache/tts/`、`models/`
- [ ] `config/api_config.json` 不在仓库中
- [ ] `git diff --cached --name-only` 无 `.wav`、`.mp3`、`.ckpt`、`.pth`、`.zip` 文件

## 文档检查

- [ ] 文档不承诺能自动还原特定角色声线
- [ ] 文档不承诺本项目直接提供 TTS 服务
- [ ] 文档明确 API / local 用户需要自备 voice_id / ref_audio / model
- [ ] 配置模板只含 placeholder，无真实密钥
