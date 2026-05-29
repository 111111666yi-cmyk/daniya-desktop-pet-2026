# 达妮娅 v0.49 设置中心核验计划

## 核验环境

```
Python: 3.10.11
测试框架: pytest 9.0.3
平台: Windows 11
项目根: C:\Users\23775\Documents\daniya2026523
```

---

## 一、自动化测试核验

### 1.1 全量 pytest

```bash
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short
```

**预期**: 110 passed, 3 skipped, 0 failed

### 1.2 关键测试逐项确认

| 测试文件 | 测试用例 | 核验点 |
|---|---|---|
| `test_settings_center.py` | `test_settings_window_opens_with_expected_tabs_in_subprocess` | 4 个标签页名称正确 |
| `test_settings_center.py` | `test_settings_manager_saves_api_config_without_plain_key` | api_key 不写入 JSON |
| `test_settings_center.py` | `test_diagnostics_do_not_expose_full_api_key` | 诊断不泄露 key |
| `test_provider_manager_switching.py` | `test_switch_active_profile_success` | 切换成功 → active_text_profile_id 持久化 |
| `test_provider_manager_switching.py` | `test_switch_active_profile_failure_and_rollback` | 切换失败 → 回退旧 profile |
| `test_provider_manager_switching.py` | `test_chat_error_fallback_handling` | API 错误 → local fallback |
| `test_model_profiles_config.py` | `test_model_profiles_sanitization_on_save` | api_key 脱敏存储 |
| `test_local_model_catalog.py` | `test_load_default_model_catalog` | 4 个推荐模型可读取 |
| `test_local_model_manager.py` | 全部 4 个 | 连接测试 + 模型列表获取 |
| `test_settings_model_apply.py` | `test_gitignore_excludes_sensitive_files` | .env / api_config.json 不进 Git |

---

## 二、Provider 配置冲突核验

### 2.1 云端配置持久性

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 打开设置中心 → 模型与引擎 | 「当前生效模型」横幅显示 DeepSeek |
| 2 | 云端 API 区域填写 DeepSeek 配置 | 正常保存 |
| 3 | 切换到本地模型区域，填写 Ollama 配置 → 点击「保存本地模型」 | 状态显示「未改变当前活跃 Provider」 |
| 4 | 关闭设置中心，重新打开 | 云端 DeepSeek 配置仍在，本地 Ollama 配置仍在 |
| 5 | 检查 `config/api_config.json` | DeepSeek 字段完整，未被 Ollama 覆盖 |
| 6 | 检查 `config/model_profiles.json` | `active_text_profile_id` 仍为 `deepseek_default` |

### 2.2 本地模型切换与回退

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 本地模型区域填写 `Ollama` + `http://localhost:11434` + `qwen2.5:0.5b` | - |
| 2 | 点击「保存本地模型」 | 绿色提示「已保存，未改变当前活跃 Provider」 |
| 3 | 点击「设为当前模型」 | 若 Ollama 未运行 → 红色提示「切换失败，已回退」 |
| 4 | 「当前生效模型」横幅 | 仍显示 DeepSeek（回退成功） |
| 5 | 启动 Ollama 后重试「设为当前模型」 | 绿色提示「已切换至 Ollama」 |
| 6 | 「当前生效模型」横幅 | 显示 `ollama_qwen25_05b [本地]` |
| 7 | 云端区域点击「设为当前模型」 | 切回 DeepSeek |

### 2.3 切换生效验证

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 当前生效设为 DeepSeek | 发送消息，控制台输出 `provider=deepseek, model=deepseek-chat, source=cloud` |
| 2 | 当前生效设为 Ollama（Ollama 已运行且有模型） | 发送消息，控制台输出 `provider=ollama` |
| 3 | 切换回 DeepSeek | 发送消息走云端 |

---

## 三、推荐模型面板核验

### 3.1 面板渲染

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 打开设置中心 → 模型与引擎 | 滚动到「推荐模型（内置目录）」区域 |
| 2 | 检查卡片数量 | 4 张卡片 |
| 3 | 检查卡片内容 | 每张含：模型名、厂商、参数量、磁盘、硬件、许可证链接、场景标签 |

### 3.2 卡片按钮功能

| 按钮 | 核验点 |
|---|---|
| 「选择此模型」 | 自动填入 `local_service_combo=Ollama`、`local_base_url=http://localhost:11434`、`local_model_list=对应模型名` |
| 「Ollama 拉取」 | 弹出许可证确认对话框 → 确认后检查 Ollama 运行 → 开始拉取 |
| 「官方页面」 | 浏览器打开对应模型的 official_url |
| 「许可证」 | 浏览器打开对应模型的 license_url |
| 「详情」 | 弹窗显示完整模型信息 |

### 3.3 模型数据完整性

| 模型 ID | 核验项 |
|---|---|
| `qwen2_5_0_5b_instruct` | 所有字段非空，Ollama 模型名 `qwen2.5:0.5b` |
| `qwen2_5_1_5b_instruct` | 所有字段非空，Ollama 模型名 `qwen2.5:1.5b` |
| `gemma2_2b_instruct` | 所有字段非空，Ollama 模型名 `gemma2:2b`，`gated_access: true` |
| `llama3_8b_instruct` | 所有字段非空，Ollama 模型名 `llama3:8b`，`gated_access: true` |

---

## 四、下载助手 + 许可证确认核验

### 4.1 许可证阻断

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 点击「打开内置下载器」 | 弹出模型选择对话框 |
| 2 | 选择一个模型 | 模型信息面板更新 |
| 3 | 检查「Ollama 拉取」按钮 | **禁用**（灰色） |
| 4 | 勾选第 1 个复选框 | 「Ollama 拉取」仍禁用 |
| 5 | 勾选第 2 个复选框 | 「Ollama 拉取」仍禁用 |
| 6 | 勾选第 3 个复选框 | 「Ollama 拉取」**启用** |
| 7 | 取消任意一个勾选 | 「Ollama 拉取」**恢复禁用** |

### 4.2 Ollama 健康检查

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 关闭 Ollama 服务 | - |
| 2 | 勾选全部 3 个复选框 → 点击「Ollama 拉取」 | 对话框关闭 |
| 3 | 观察本地状态标签 | 显示「正在检测 Ollama 服务...」→ 红色「无法连接 Ollama」 |
| 4 | 下载器按钮 | 恢复可用 |

### 4.3 Ollama 拉取流程（需 Ollama 运行）

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 启动 Ollama | - |
| 2 | 选择 Qwen2.5 0.5B → 勾选 3 项 → 点击「Ollama 拉取」 | 状态显示实时进度（如 `pulling manifest`、`verifying sha256` 等） |
| 3 | 等待拉取完成 | 状态变绿色「模型 qwen2.5:0.5b 拉取完成」 |
| 4 | 检查 `local_model_list` 下拉 | 自动刷新，包含刚拉取的模型 |
| 5 | 点击「保存本地模型」→「设为当前模型」 | 切换成功 |

---

## 五、UI 与交互核验

### 5.1 标签页结构

| 标签页 | 内容核验 |
|---|---|
| 模型与引擎 | 当前生效横幅 + 云端 API + 本地部署 + 推荐模型 + 下载器 + 多模态预留 |
| 桌宠 | 大小/置顶/透明度/闲聊/整点报时/提醒/昼夜作息 |
| 角色与资源 | 动作资源 + 角色包编辑器 |
| 数据与系统 | 关系状态 + 事件日志 + 数据管理 + 系统诊断 |

### 5.2 状态显示一致性

| 场景 | 预期状态标签 |
|---|---|
| 仅保存云端 | `当前生效模型：DeepSeek (deepseek-chat) [云端]` |
| 保存本地但不激活 | `当前生效模型：DeepSeek (deepseek-chat) [云端]` + 本地状态「已保存」 |
| 激活本地 | `当前生效模型：Ollama qwen2.5:0.5b [本地]` |
| 切换失败 | 保持上一个模型 + 红色提示「切换失败 — 已回退」 |

---

## 六、安全与合规核验

### 6.1 敏感信息保护

| 核验项 | 方法 |
|---|---|
| api_key 不写入 JSON | `grep -r "sk-" config/*.json` 无结果 |
| .env 不进 Git | `git status` 不包含 .env |
| models/ 不进 Git | `git ls-files models/` 无输出 |
| 模型权重不进入发布包 | `release/` 在 .gitignore |

### 6.2 许可证合规

| 核验项 |
|---|
| 所有推荐模型的 `requires_license_confirmation: true` |
| 下载前必须展示许可证名称和链接 |
| 3 个勾选框全部勾选后才可下载 |
| 不静默下载 |
| 不自动接受许可证 |

---

## 七、回归核验

### 7.1 已有功能不受影响

| 核验项 | 方法 |
|---|---|
| DialogueEngine 正常 | `test_dialogue_engine.py` 全部通过 |
| speech_filter 正常 | `test_speech_filter.py` 全部通过 |
| relationship_engine 正常 | `test_relationship_engine.py` 全部通过 |
| action_router 正常 | `test_action_router.py` 全部通过 |
| 动画管理器正常 | `test_animation_manager.py` 全部通过 |

### 7.2 启动核验

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | `run.bat` 启动 | 达妮娅桌宠正常显示 |
| 2 | 右键菜单 → 设置中心 | 设置中心正常打开 |
| 3 | 发送消息 | 对话正常，无崩溃 |
| 4 | 点击桌宠 | 交互正常 |
| 5 | 拖拽桌宠 | 拖拽正常 |

---

## 八、核验执行顺序

```
Phase 1: pytest -q                        ← 5 分钟内完成
Phase 2: Provider 配置冲突核验 (2.1-2.3)  ← 10 分钟内完成
Phase 3: 推荐模型面板核验 (3.1-3.3)       ← 5 分钟内完成
Phase 4: 下载助手核验 (4.1-4.2)           ← 5 分钟内完成（不需要 Ollama）
Phase 5: 安全合规核验 (6.1-6.2)           ← 5 分钟内完成
Phase 6: 回归核验 (7.1-7.2)               ← 5 分钟内完成
Phase 7: [可选] Ollama 拉取核验 (4.3)     ← 需要 Ollama 运行，视网络情况
```

**预计总耗时**: 35 分钟（不含 Ollama 拉取）
