# First Run Wizard 架构设计

在 v0.45 阶段，达妮娅引入了“First Run Wizard（首次运行向导）”。它是一套独立于核心业务逻辑之外的引导工具，旨在帮助小白用户更轻松地建立起初步的配置文件，并在未来连接更广阔的多模态生态。

## 拦截与检测机制
向导在程序入口 `main.py` -> `src/app.py` 的 `run()` 阶段进行拦截：

```python
setup_manager = SetupStateManager()
if not setup_manager.is_first_run_complete():
    wizard = FirstRunWizard(setup_manager)
    wizard.exec()
```

- 检测文件：`config/setup_config.json`
- 关键状态：`first_run_setup: bool`
- **防御机制**：如果向导被强制关闭（点击 X），主程序将直接结束 (`sys.exit(0)`)，避免在缺少关键配置的前提下强行加载出报错的桌宠。

## 运行模式设计

向导当前提供四种核心运行模式（对应不同的 Provider 设定）：

1. **快速体验模式 (A)**：直接利用 local fallback 逻辑体验基础点击交互，不需要任何 API Key。
2. **API 云模型模式 (B)**：填写真实的云端大模型配置（DeepSeek、OpenAI、Claude），完成设置后生成 `.env`。
3. **本地大模型模式 (C)**：填写本地代理地址（如 `http://localhost:1234/v1`），由 v0.45 新加入的 `local_openai_compatible` 提供商进行驱动。
4. **单机测试模式 (D)**：主要面向开发者调试桌宠动画、状态机及 UI。

## 静态能力架构预留

为了支持 v0.46 及未来的版本，我们在 `src/provider_capability_schema.py` 内预先声明了全量的 Provider 支持边界：

```json
{
  "tts_providers": ["cloud_tts", "local_tts", "none"],
  "image_providers": ["text_to_image", "image_to_image", "none"],
  "video_providers": ["image_to_video", "text_to_video", "none"]
}
```

目前，向导及系统设置中心仅展示上述配置清单作为**占位**，并将其写入 `setup_config.json`，不会真的发起多模态请求。真正的能力映射将在后续架构设计中由 `MultiModalManager` 处理。
