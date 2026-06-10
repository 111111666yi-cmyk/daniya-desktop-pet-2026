# TTS 语音使用指南（普通用户）

本项目推荐使用 **预录语音包（clip_pack）** 模式。无需 API、无需 GPT-SoVITS、无需训练、无需显卡。

## 快速开始

1. 前往 [GitHub Release](https://github.com/111111666yi-cmyk/daniya-desktop-pet-2026/releases/tag/voice-pack-daniya-v1) 下载 `daniya_clip_pack_v1.zip`
2. 打开桌宠 → 设置中心 → 多模态 / 语音
3. 语音模式选择 **预录语音包**
4. 点击 **导入语音包 (ZIP/文件夹)**
   - 选择下载的 `.zip` 文件，或解压后的文件夹
5. 点击 **校验语音包** — 确认 SHA256 通过
6. 点击 **测试播放** — 听到达妮娅语音即成功

完成后，点击、拖拽、提醒等交互都会播放达妮娅语音。

## 离线导入

如果无法在线下载，可以通过 U 盘等方式拷贝 `daniya_clip_pack_v1.zip`，然后在设置中心手动导入。语音包导入后完全离线工作。

## 该模式的限制

- 只能播放语音包中预录好的固定语音片段
- 不支持自由文本转语音
- 如需动态语音，请参阅 [TTS_ADVANCED_GUIDE.md](TTS_ADVANCED_GUIDE.md)

## 故障排查

| 症状 | 可能原因 | 解决方法 |
|------|---------|---------|
| 校验失败 | 下载了旧版本 zip | 重新从 Release 页面下载最新版 |
| SHA256 不匹配 | zip 下载不完整或被篡改 | 删除后重新下载，对比 Release 页面的 SHA256 |
| 导入后无声 | zip 损坏 | 用解压工具打开 zip 确认内含 manifest.json 和 wav 文件 |
| 导入失败 | 路径权限问题 | 将 zip 放到桌面等有写入权限的位置再导入 |
| 测试播放失败 | 语音包 ID 不匹配 | 确认设置中心语音包 ID 为 `daniya_clip_pack_v1` |
| 导入成功但播放异常 | Release 上的 zip 与 manifest 不一致 | 等待维护者更新 Release，或手动对比 SHA256 |

## 当前版本信息

- 语音包：`daniya_clip_pack_v1`
- 包含 32 个 WAV 片段，覆盖 8 个交互场景
- SHA256：`b5445643e8d2e51a519fd8c3f4b6b93c78dfa7afe3b0f531d016ba75ee1b1f42`
- 大小：约 2.7 MB
