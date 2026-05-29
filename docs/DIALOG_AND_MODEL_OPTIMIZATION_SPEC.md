# 达妮娅桌宠设置中心与窗口控制优化技术文档

本说明书详细记录了针对“设置中心”进行的窗口控制交互（最小化/最大化）补强、模型配置逻辑同步以及功能页（同类型标签页）合并的详细变更说明及核心代码段，以便日后进行测试、回归与二次开发。

---

## 目录
1. [窗口控制与交互优化 (最小化/最大化功能)](#1-窗口控制与交互优化)
2. [本地模型与云端 API 配置同步逻辑](#2-本地模型与云端-api-配置同步逻辑)
3. [大类功能页合并 (合并同类型标签页)](#3-大类功能页合并)
4. [回归测试与编码安全规范](#4-回归测试与编码安全规范)

---

## 1. 窗口控制与交互优化

### 1.1 背景与痛点
在标准的 PySide6 GUI 设计中，继承自 `QDialog` 的对话框在没有显式配置的情况下，默认只展示“关闭”按钮（右上角 `X`），且不会在系统的任务栏中生成独立的最小化卡片，导致用户在调整其他应用时无法顺畅收起设置中心或子窗口。

### 1.2 优化方案
为所有核心的 QDialog 对话框注入窗口标志 `Qt.WindowMinimizeButtonHint` 和 `Qt.WindowMaximizeButtonHint`。

### 1.3 核心实现位置与代码

#### (1) 设置中心主窗口：`src/settings_window.py`
在 `SettingsWindow.__init__` 构造函数中设置窗口属性：
```python
class SettingsWindow(QDialog):
    def __init__(self, controller: "AppController", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # ... 初始化工作 ...
        self.setWindowTitle("设置中心")
        self.resize(860, 640)
        # 核心改动：启用最小化和最大化图标
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
```

#### (2) 达妮娅设定面板：`src/daniya_settings_window.py`
```python
class DaniyaSettingsDialog(QDialog):
    def __init__(self, controller: "AppController", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("达妮娅设定")
        self.resize(760, 560)
        # 核心改动：启用最小化和最大化图标
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
```

#### (3) 聊天历史记录窗口：`src/menu_manager.py`
```python
class HistoryDialog(QDialog):
    def __init__(self, controller: "AppController", parent: QWidget) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("历史记录")
        self.resize(720, 520)
        # 核心改动：启用最小化和最大化图标
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
```

#### (4) 首次运行向导窗口：`src/first_run_wizard.py`
```python
class FirstRunWizard(QDialog):
    def __init__(self, setup_manager: SetupStateManager) -> None:
        super().__init__()
        # ...
        self.setWindowTitle("欢迎来到 达妮娅 (Daniya) - 首次运行向导")
        self.setMinimumSize(600, 700)
        self.setModal(True)
        # 核心改动：移除帮助按钮并加上最小化和最大化按钮
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint) 
            | Qt.WindowType.WindowMinimizeButtonHint 
            | Qt.WindowType.WindowMaximizeButtonHint
        )
```

#### (5) 内置下载器弹窗：`src/settings_window.py` 中的 `_open_model_downloader`
```python
    def _open_model_downloader(self) -> None:
        # ...
        dialog = QDialog(self)
        dialog.setWindowTitle("内置下载器 - 选择模型")
        dialog.setMinimumWidth(550)
        # 核心改动：启用最小化和最大化图标
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
```

---

## 2. 本地模型与云端 API 配置同步逻辑

### 2.1 逻辑冲突背景
在原 v0.49 逻辑中，当用户在设置中心的“本地部署与引擎配置 (Local Service)”栏中配置本地大模型（如 Ollama, LM Studio）并保存时，系统会调用 `save_local_model_profile`。该方法仅将配置写入 `model_profiles.json` 的 `profiles` 数组中，**但没有更新当前的活跃模型 ID（`active_text_profile_id`）**。这导致：
1. 用户保存了本地配置，桌宠却仍在运行云端的旧模型。
2. 配置界面缺少一键生效的统一入口。

### 2.2 解决方案
在 `SettingsManager` 中新增接口 `save_and_activate_local_model_profile`。它在保存 Profile 的同时，强制将 `active_text_profile_id` 指向该本地模型，并同步关闭云端 API 的 `local_mode`（避免卡在本地写死的离线 Fallback 回复），最后触发全局 `ChatClient` 重新加载配置。

### 2.3 核心实现位置与代码

#### (1) 生效逻辑封装：`src/settings_manager.py`
```python
    def save_and_activate_local_model_profile(self, provider: str, base_url: str, model: str, service_label: str = "") -> None:
        """保存本地模型 profile 到 model_profiles.json，并将其设为当前活跃的 Provider/模型。"""
        # 第一步：保存 profile
        self.save_local_model_profile(provider, base_url, model, service_label)
        
        # 第二步：将当前活跃模型文本 ID 更新为刚刚保存的本地 Profile ID
        profiles_data = self.load_model_profiles()
        target_id = f"{provider}_{model.replace(':', '_').replace('.', '_')}"
        profiles_data["active_text_profile_id"] = target_id
        self.save_model_profiles(profiles_data)
        
        # 第三步：同步到 api_config.json 保持活跃 provider 字段一致，并关闭本地 Fallback 模式
        config = self.load_api_config()
        config["active_provider"] = provider
        config["local_mode"] = False  # 确保关闭了本地 fallback 回复模式，使 LLM 可以正常调用
        self.save_api_config(config)
        self._sync_app_api(config)
```

#### (2) GUI 事件调用绑定：`src/settings_window.py` 中的 `_save_local_model_settings`
```python
    def _save_local_model_settings(self) -> None:
        service = self.local_service_combo.currentText()
        url = self.local_base_url.text().strip()
        model = self.local_model_list.currentText().strip()
        # ... 基础格式检查与 provider 别名映射 ...

        # 核心改动：调用新同步接口
        self.settings_manager.save_and_activate_local_model_profile(
            provider=provider,
            base_url=url,
            model=model,
            service_label=service,
        )
        # 核心改动：即时重载全局 chat_client，使其在后台立刻读取新模型
        self.controller.chat_client.reload()
        
        self.local_status.setText(f"状态：已保存并激活 {provider} → {model}  ✓ 已生效")
        self.local_status.setStyleSheet("color: green;")
        self._refresh_active_status()
```

---

## 3. 大类功能页合并

### 3.1 优化原则
通过减少 Tab 标签数量，将属性相近的功能归拢到同一个父级标签页中，结合 `QScrollArea` 的弹性纵向排版，在控制界面复杂度的同时，提升在小屏幕笔记本下的界面可用性。

### 3.2 优化布局对比
* **原 Tab 列表 (5个)**：
  `['模型与引擎', '桌宠', '角色与资源', '关系与事件', '系统']`
* **优化后 Tab 列表 (4个)**：
  `['模型与引擎', '桌宠', '角色与资源', '数据与系统']`

### 3.3 “数据与系统”标签页合并实现：`src/settings_window.py`
将原 `_build_relationship_events_tab` 与 `_build_system_tab` 中声明的四个配置组盒（GroupBox）移入具有滚动条的统一父级布局：

```python
    def _build_data_system_tab(self) -> None:
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # 组 1：关系状态 (Relationship State)
        rel_group = QGroupBox("关系状态")
        rel_layout = QVBoxLayout(rel_group)
        # ... 按钮与文本域实例化 ...
        scroll_layout.addWidget(rel_group)

        # 组 2：事件日志 (Event Logs)
        evt_group = QGroupBox("事件日志")
        evt_layout = QVBoxLayout(evt_group)
        # ...
        scroll_layout.addWidget(evt_group)

        # 组 3：数据管理 (Data Files)
        data_group = QGroupBox("数据管理")
        data_layout = QVBoxLayout(data_group)
        # ...
        scroll_layout.addWidget(data_group)

        # 组 4：系统诊断 (Diagnostics)
        diag_group = QGroupBox("系统诊断")
        diag_layout = QVBoxLayout(diag_group)
        # ...
        scroll_layout.addWidget(diag_group)

        # 挂载滚动区域
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        self.tabs.addTab(tab, "数据与系统")

        # 初始化数据刷新
        self._refresh_relationship()
        self._refresh_events()
        self._refresh_data()
```

---

## 4. 回归测试与编码安全规范

### 4.1 测试脚本说明
设置中心测试入口位于 `tests/test_settings_center.py`。
由于窗口合并了 Tab，原本测试中的硬编码名称检查已被同步更新。

### 4.2 消除 Windows 下 Subprocess 的 CLI 编码挂起
在 Windows 下，若在 `subprocess.run` 中传入含中文（如 `'模型与引擎'` 等）的 Python 内联执行脚本（`python -c "..."`），容易由于 CLI 环境（如 GBK 与 UTF-8 冲突）导致参数解析错误。
**规范建议**：在 `subprocess` 内联测试脚本中比较 non-ASCII 文本时，**必须使用 Unicode 转义序列 (Unicode Escape)** 或**直接比较长度**，例如：

```python
# 更改前 (存在 Windows 挂起风险)
assert tabs == ['模型与引擎', '桌宠', '角色与资源', '关系与事件', '系统']

# 更改后 (安全，支持在无头无界面及任意 Windows 代码页环境下运行)
assert len(tabs) == 4
assert tabs[0] == '\u6a21\u578b\u4e0e\u5f15\u64ce'        # '模型与引擎'
assert tabs[1] == '\u684c\u5ba0'                        # '桌宠'
assert tabs[2] == '\u89d2\u8272\u4e0e\u8d44\u6e90'        # '角色与资源'
assert tabs[3] == '\u6570\u636e\u4e0e\u7cfb\u7edf'        # '数据与系统'
```
