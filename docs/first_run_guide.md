# First Run Guide

更新日期：2026-05-31

v0.58 起，首次启动向导用于帮助新用户完成最小配置。它不新增 TTS、Vision、长期记忆、Live2D 或插件系统，只解释现有能力和安全放置方式。

## 触发条件

- `data/first_run_done.json` 不存在。
- `data/first_run_done.json` 损坏或不是有效完成状态。
- 旧版 `config/setup_config.json` 存在且标记已完成时，会自动迁移到 `data/first_run_done.json`；新的 setup 状态写入 ignored 的 `data/setup_config.json`，不再写 tracked config。
- 用户在设置中心的“系统”页点击“重新打开首次启动向导”。

打包版 Windows exe 的该文件位于 `%APPDATA%\DaniyaSummerPet\data\first_run_done.json`；源码运行时位于 ignored `data/`。

## 五个页面

1. 欢迎：说明 Daniya 是本地桌宠，无 API Key 也可用 local fallback，私有素材不会进入 Git 或 release。
2. API 设置：可跳过 API，也可选择 Provider、填写 Base URL、Model、API Key，并后台测试连接。
3. 素材说明：解释 `assets/private/`、placeholder、normal1/normal2 与 manifest 用途。
4. 角色包说明：解释 `characters/daniya/`、`characters/template/` 和 local-only `characters/test_dummy/`。
5. 完成：提示启动桌宠、设置中心、README 与本地 fallback；可选创建 `daniya521` 桌面快捷方式，默认不勾选，失败不阻止启动。

## API Key

- API Key 写入本机 `.env`。
- 设置中心和向导都使用密码框，不显示完整 Key。
- 测试连接在后台线程执行，不应冻结 UI。
- 跳过 API 后仍可使用 local fallback；之后可在设置中心补填。

## 素材目录按钮

- `assets/private/`：不存在时自动创建，只在本地使用。
- `characters/daniya/`：打开公开示例角色包。
- `docs/character_pack_guide.md`：打开角色包指南。
- `README.md`：打开项目说明。

向导不会创建 `characters/test_dummy/`，也不会下载任何素材。

## 重置或重新打开

在设置中心打开“系统”页，点击“重新打开首次启动向导”。重新打开不会清空现有设置；只有用户在向导中保存或跳过时才会更新 `.env`、API 设置和 `data/first_run_done.json`。
