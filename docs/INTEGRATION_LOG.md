# Daniya v0.415 接入集成修改日志

> **目的**：本文件详细记录每一次代码变更的具体位置、改动原因、影响范围和还原方法，便于后续回溯与还原。
> **版本起点**：v0.415（基于 v0.43 仓库清理后的代码状态）
> **编辑者**：Antigravity Agent
> **创建时间**：2026-05-29

---

## 变更记录

---

### [CHANGE-001] src/app.py — 接入 DaniyaEngineAdapter 初始化

**文件**：`src/app.py`  
**影响范围**：`AppController.__init__` 方法  
**改动类型**：新增代码（非破坏性，不删除旧逻辑）

**改动说明**：
- 在 `AppController.__init__` 中新增 `from .daniya_engine_adapter import DaniyaEngineAdapter` 导入。
- 在所有现有 manager 初始化完成之后，新增一行 `self.daniya_adapter = DaniyaEngineAdapter(...)` 来实例化适配器。
- 适配器接收 `model_client=self.chat_client`，内部通过 `_wrap_model_client` 自动包装为 `DialogueEngine` 所需的接口。
- **不删除** `self.chat_client`（DeepSeek API 仍在使用中）。
- **不删除** `self.affinity_manager`（作为兼容层保留，后续 v0.42 阶段才考虑迁移）。

**改动原因**：
当前 `src/app.py` 中的对话循环和物理交互直接绕过了整个 `core/` 引擎。引入 `DaniyaEngineAdapter` 后，对话和物理事件将经过 `DialogueEngine → SpeechFilter → LoreRetriever → RelationshipEngine` 的完整管线。

**还原方法**：
1. 删除 `from .daniya_engine_adapter import DaniyaEngineAdapter` 导入行。
2. 删除 `self.daniya_adapter = DaniyaEngineAdapter(...)` 初始化行。
3. 无其他副作用。

---

### [CHANGE-002] src/app.py — ChatWorker 接入适配器对话管线

**文件**：`src/app.py`  
**影响范围**：`ChatWorker` 类、`AppController.send_message`、`AppController._handle_reply`  
**改动类型**：修改现有代码（保留原逻辑作为注释）

**改动说明**：
- `ChatWorker.__init__` 改为接收 `DaniyaEngineAdapter` 而非 `ChatClient`。
- `ChatWorker.run()` 改为调用 `adapter.handle_user_text(user_text)` 返回 `EngineResult`。
- 信号 `reply_ready` 改为传递 `EngineResult` 对象（通过序列化或直接传递）。
- `_handle_reply` 中从 `EngineResult` 提取 `response` 和 `source`。
- **原 `chat_client.reply()` 调用链被注释保留**，标记为 `# [LEGACY] 原 DeepSeek 直连逻辑 — 由 CHANGE-002 替换`。

**改动原因**：
让用户对话经过完整的引擎管线（特殊回复匹配 → 事件匹配 → Lore 检索 → 语气过滤 → 关系数值更新）。

**还原方法**：
1. 恢复 `ChatWorker.__init__` 的参数为 `chat_client: ChatClient`。
2. 恢复 `ChatWorker.run()` 中的 `self.chat_client.reply(self.user_text)` 调用。
3. 恢复 `reply_ready` 信号为 `Signal(str, str)`。
4. 取消注释 `send_message` 中原来的 `ChatWorker(self.chat_client, user_text)` 行。

---

### [CHANGE-003] src/app.py — 物理交互接入引擎

**文件**：`src/app.py`  
**影响范围**：`AppController.on_pet_clicked`、`AppController.on_reminder_due`  
**改动类型**：新增代码行（非破坏性）

**改动说明**：
- `on_pet_clicked` 中新增 `self.daniya_adapter.handle_physical_event("user_click")`。
- `on_reminder_due` 中新增 `self.daniya_adapter.handle_physical_event("reminder_due")`。
- 拖拽释放事件通过 `position_changed` 信号触发 `handle_physical_event("user_drag")`。
- **不删除** 原有的 `affinity_manager.add_click()` 和 `day_night_manager` 动画逻辑（双写兼容期）。

**改动原因**：
当前物理交互事件没有流入关系引擎，导致 `relationship_state.json` 中的 `defense_level` 等数值永远不更新。

**还原方法**：
1. 删除所有 `self.daniya_adapter.handle_physical_event(...)` 调用行。
2. 无其他副作用。

---

## 注意事项

- **绝对不删除** DeepSeek API 相关逻辑（`ChatClient`、`.env` 配置）。
- **绝对不改动** `src/pet_window.py` 中的 `_print_render_debug` 和 `contextMenuEvent` 修复。
- **绝对不改动** `core/` 目录下的任何引擎文件（它们已通过全部 73 个单元测试）。
- 所有修改都遵循"加法优先"原则，不删除只新增或注释标记。

---

### [CHANGE-004] tests/test_integration_verify.py — 端到端集成验证测试

**文件**：`tests/test_integration_verify.py`（新增）  
**影响范围**：仅测试目录，不影响任何生产代码  
**改动类型**：新增文件

**改动说明**：
- 5 个测试用例验证 `DaniyaEngineAdapter` 的端到端数据流：
  - `test_special_response_updates_state`：`我不会先走` → 特殊回复 + state 更新
  - `test_physical_click_updates_defense`：物理点击 → `defense_level` 增加
  - `test_physical_drag_updates_defense`：物理拖拽 → `defense_level` 增加
  - `test_hug_special_response`：`抱抱` → 拥抱特殊回复
  - `test_engine_result_has_correct_fields`：`EngineResult` 字段完整性
- 使用 `tmp_path` + `monkeypatch` 隔离测试数据，不影响用户真实的 `data/` 目录。

**还原方法**：
1. 删除 `tests/test_integration_verify.py` 文件。
2. 无其他副作用。

