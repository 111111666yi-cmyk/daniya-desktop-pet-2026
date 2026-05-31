# v0.57 Release Freeze Checklist

更新日期：2026-05-31

v0.57 是稳定冻结阶段，不新增功能，不重构 UI，不修改状态机、Timer、Provider 架构或角色包结构。所有检查必须遵守 `docs/DESTRUCTIVE_TEST_POLICY.md`。

## 1. 启动检查

- [ ] 无 `.env`：可启动，local fallback，不崩溃。
- [ ] 空 API Key：可启动，local fallback，不崩溃。
- [ ] 错误 API Key：API 失败后 fallback，不泄露完整 Key。
- [ ] 正确 API Key：API 回复正常，`chat_history` 记录 `source=api`。
- [ ] 无网络：API fallback，不崩溃。

## 2. GUI 检查

- [ ] 透明窗口。
- [ ] 无边框。
- [ ] 置顶。
- [ ] 拖拽。
- [ ] 左边缘吸附与拉回。
- [ ] 右边缘吸附与拉回。
- [ ] 底部吸附与拉回。
- [ ] 拖出屏幕后自动保持可见。
- [ ] 关闭重开恢复位置。
- [ ] 右键菜单。
- [ ] 输入框显示/隐藏。
- [ ] 设置中心打开/关闭。
- [ ] 退出程序无残留进程。

## 3. API 检查

- [ ] Key 缺失时不报 traceback。
- [ ] Key 错误时不泄露完整 Key。
- [ ] 网络失败时提示可理解。
- [ ] Base URL / Model 错误时 fallback。
- [ ] API 测试不冻结 UI。

## 4. 角色检查

- [ ] `characters/daniya` 校验通过。
- [ ] `characters/template` 校验通过。
- [ ] clean clone 不依赖 `characters/test_dummy`。
- [ ] 角色特殊触发不吞掉任务请求。
- [ ] 角色回复保持达妮娅设定。

## 5. 事件检查

- [ ] `/pet status` 不调用 API。
- [ ] `/pet reload` 不调用 API。
- [ ] `/pet event` 不调用 API。
- [ ] `/pet sleep` 不锁死对话。
- [ ] `/pet wake` 可恢复对话。
- [ ] `reminder_due` 不误触发普通“提醒我”请求。

## 6. 行为检查

- [ ] 单击触发 clicked。
- [ ] 双击触发 happy。
- [ ] 长按不锁死状态。
- [ ] 拖拽不误触发 click。
- [ ] idle 不打断 talking。
- [ ] random event 不打断 dragging。
- [ ] temporary state 不永久卡住。

## 7. 数据检查

- [ ] 不直接删除 `data/`。
- [ ] 不直接删除 `.env`。
- [ ] 不直接删除 `assets/private/`。
- [ ] 不直接删除 `models/`。
- [ ] 破坏性测试先 backup 或使用临时沙盒。
- [ ] packaged exe 运行态写入 `%APPDATA%\DaniyaSummerPet\`。

## 8. 打包检查

- [ ] `pack.bat` 成功。
- [ ] exe 生成。
- [ ] zip 生成。
- [ ] release exe 可启动。
- [ ] zip entry count 已记录。

## 9. 安全检查

- [ ] zip 不含 `.env`。
- [ ] zip 不含 `config/api_config.json`。
- [ ] zip 不含 `config/multimodal_config.json`。
- [ ] zip 不含 `data/`。
- [ ] zip 不含 `assets/private/`。
- [ ] zip 不含 `models/`。
- [ ] zip 不含 `characters/test_dummy/`。
- [ ] zip 不含 `docs/v0.51_patch_audit/`。
- [ ] zip 不含 `*.log` / `*.tmp`。
- [ ] 未发现真实 API Key。

## 10. Git 检查

- [ ] `git status --short` 已记录。
- [ ] `git diff --check` 通过。
- [ ] `git ls-files` 敏感路径无输出。
- [ ] 未提交 `.env`、`data/`、`backups/`、`release/`、`dist/`、`build/`。

## 11. Release 检查

- [ ] release notes 列出已知问题。
- [ ] release 包结构符合公开发布规则。
- [ ] 不自动 push。
- [ ] 不自动发布 GitHub Release。
- [ ] P0/P1 为 0 后才允许进入下一阶段。
