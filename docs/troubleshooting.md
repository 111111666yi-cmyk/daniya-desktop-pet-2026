# Troubleshooting

更新日期：2026-05-31

## 首次启动向导没有出现

- 检查 `data/first_run_done.json` 是否已经存在并包含 `completed: true`。
- 打包版 Windows exe 的运行态在 `%APPDATA%\DaniyaSummerPet\`。
- 需要重新查看时，在设置中心“系统”页点击“重新打开首次启动向导”。

## 没有 API Key

可以跳过 API。程序会使用 local fallback，不应崩溃，也不应冻结 UI。之后可以在设置中心补填 API Key。

## API Key 错误或网络失败

- 向导和设置中心会显示连接失败原因。
- 完整 Key 不会显示在普通界面。
- 检查 Provider、Base URL、Model、网络连接和账户额度。
- 智谱、Kimi、豆包等 OpenAI-compatible 服务通常需要对应的 Base URL、Model 和 Key。

## 配置损坏

坏 JSON/YAML 应 fallback 或重建，不应直接删除真实运行态。测试或修复前先阅读 `docs/DESTRUCTIVE_TEST_POLICY.md`。

## 角色包缺文件

- 公开示例角色：`characters/daniya/`。
- 新角色模板：`characters/template/`。
- `characters/test_dummy/` 是 local-only，clean clone 不要求它存在。
- 运行 `python tools/validate_character_pack.py characters/daniya` 和 `python tools/validate_character_pack.py characters/template` 检查角色包。

## 图片资源缺失

缺私有素材时应 fallback 到 placeholder。私有素材放在 ignored `assets/private/` 或本地角色素材目录，不要提交到 Git。

## 发布包写入失败

v0.55.3 起，Windows 打包 exe 的运行态写入 `%APPDATA%\DaniyaSummerPet\`，不依赖 exe 所在目录可写。如果仍失败，检查杀毒软件、目录权限和磁盘空间。
