# Codex Notes

本项目按模块化桌面应用组织，避免把所有逻辑塞进一个 `oc.py`。

- `main.py` 只负责启动。
- `src/app.py` 负责对象装配和信号连接。
- `src/pet_window.py` 负责桌宠窗口和交互。
- `src/chat_client.py` 负责 OpenAI-compatible API 调用与本地降级回复。
- `src/typewriter.py` 负责气泡打字机和口型切换节奏。
- `src/asset_manager.py` 负责 private/placeholder 资源选择。
- `src/history_manager.py` 负责 JSONL 聊天历史。
- `src/config_manager.py` 和 `src/profile_manager.py` 负责配置和档案。
- `src/menu_manager.py` 负责右键菜单和设置弹窗。

真实角色素材只应存在于 `assets/private/`，不要提交到 GitHub。

