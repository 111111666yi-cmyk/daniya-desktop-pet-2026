from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .provider_capability_schema import ProviderCapabilitySchema
from .settings_manager import SettingsManager
from .setup_state_manager import SetupStateManager


class FirstRunWizard(QDialog):
    """
    首次启动达妮娅时的向导窗口。
    用于引导用户选择运行模式，设置 API Key，并预留多模态能力的入口。
    """

    def __init__(self, setup_manager: SetupStateManager) -> None:
        super().__init__()
        self.setup_manager = setup_manager
        self.settings_manager = SettingsManager(root=setup_manager.root)
        self.schema = ProviderCapabilitySchema(root=setup_manager.root)
        
        self.setWindowTitle("欢迎来到 达妮娅 (Daniya) - 首次运行向导")
        self.setMinimumSize(600, 700)
        self.setModal(True)
        # 移除帮助按钮
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # UI 构建
        layout = QVBoxLayout(self)

        title = QLabel("欢迎使用达妮娅桌宠！")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-top: 10px; margin-bottom: 5px;")
        layout.addWidget(title)

        desc = QLabel("看起来这是您第一次启动达妮娅。在她出现在您的桌面前，请选择您想要赋予她的能力和运行模式。")
        desc.setWordWrap(True)
        desc.setStyleSheet("margin-bottom: 15px;")
        layout.addWidget(desc)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)

        # 1. 运行模式选择
        mode_group = QButtonGroup(self)
        self.radio_fast = QRadioButton("A. 快速体验模式（无需 API Key，仅限本地假回复体验基础动作）")
        self.radio_api = QRadioButton("B. API 云模型模式（推荐，需提供 DeepSeek/OpenAI 等平台的 API Key）")
        self.radio_local = QRadioButton("C. 本地大模型模式（需自行启动 LM Studio / Ollama 等兼容服务）")
        self.radio_mock = QRadioButton("D. 单机测试模式（断网开发测试专用）")
        
        mode_group.addButton(self.radio_fast, 1)
        mode_group.addButton(self.radio_api, 2)
        mode_group.addButton(self.radio_local, 3)
        mode_group.addButton(self.radio_mock, 4)

        self.radio_api.setChecked(True) # 默认推荐 API 模式
        
        mode_layout = QVBoxLayout()
        mode_label = QLabel("1. 请选择运行模式：")
        mode_label.setStyleSheet("font-weight: bold;")
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.radio_fast)
        mode_layout.addWidget(self.radio_api)
        mode_layout.addWidget(self.radio_local)
        mode_layout.addWidget(self.radio_mock)
        scroll_layout.addLayout(mode_layout)

        # 2. 详细配置项 (跟随模式切换)
        self.config_widget = QWidget()
        config_form = QFormLayout(self.config_widget)
        
        self.api_provider_combo = QComboBox()
        self.api_provider_combo.addItems(["deepseek", "openai", "claude", "openai_compatible"])
        
        self.local_provider_combo = QComboBox()
        self.local_provider_combo.addItems(self.schema.get_local_model_providers())

        self.base_url_input = QLineEdit()
        self.model_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("在此填入您的 API Key")

        config_form.addRow("Provider 选择", self.api_provider_combo)
        config_form.addRow("本地服务类型", self.local_provider_combo)
        config_form.addRow("Base URL", self.base_url_input)
        config_form.addRow("Model 名称", self.model_input)
        config_form.addRow("API Key", self.api_key_input)
        
        scroll_layout.addWidget(self.config_widget)

        # 信号绑定
        self.radio_fast.toggled.connect(self._on_mode_changed)
        self.radio_api.toggled.connect(self._on_mode_changed)
        self.radio_local.toggled.connect(self._on_mode_changed)
        self.radio_mock.toggled.connect(self._on_mode_changed)
        self.api_provider_combo.currentTextChanged.connect(self._on_provider_combo_changed)
        
        # 3. 多模态能力模块选择
        multi_label = QLabel("2. 能力模块选择（v0.46 预留）：")
        multi_label.setStyleSheet("font-weight: bold;")
        scroll_layout.addWidget(multi_label)

        multi_desc = QLabel("这些选项目前仅作为架构预留展示，勾选后将在后续版本自动生效。")
        multi_desc.setStyleSheet("color: gray;")
        scroll_layout.addWidget(multi_desc)

        self.check_tts = QCheckBox("启用 TTS 语音播报")
        self.check_t2i = QCheckBox("启用 文生图 能力")
        self.check_i2i = QCheckBox("启用 图生图 能力")
        self.check_video = QCheckBox("启用 视频生成 能力")
        
        scroll_layout.addWidget(self.check_tts)
        scroll_layout.addWidget(self.check_t2i)
        scroll_layout.addWidget(self.check_i2i)
        scroll_layout.addWidget(self.check_video)

        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # 底部按钮
        buttons_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test_connection)
        self.finish_btn = QPushButton("完成配置，召唤达妮娅！")
        self.finish_btn.setStyleSheet("font-weight: bold; padding: 10px;")
        self.finish_btn.clicked.connect(self._finish_setup)

        buttons_layout.addWidget(self.test_btn)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.finish_btn)
        layout.addLayout(buttons_layout)

        # 初始化状态
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        if self.radio_fast.isChecked() or self.radio_mock.isChecked():
            self.config_widget.hide()
            self.test_btn.hide()
        elif self.radio_api.isChecked():
            self.config_widget.show()
            self.test_btn.show()
            # 隐藏本地专属框，显示 API 专属框
            self.local_provider_combo.hide()
            self.api_provider_combo.show()
            self.api_provider_combo.parentWidget().layout().labelForField(self.local_provider_combo).hide()
            self.api_provider_combo.parentWidget().layout().labelForField(self.api_provider_combo).show()
            self._on_provider_combo_changed()
        elif self.radio_local.isChecked():
            self.config_widget.show()
            self.test_btn.show()
            # 隐藏 API 专属框，显示本地专属框
            self.api_provider_combo.hide()
            self.local_provider_combo.show()
            self.api_provider_combo.parentWidget().layout().labelForField(self.api_provider_combo).hide()
            self.api_provider_combo.parentWidget().layout().labelForField(self.local_provider_combo).show()
            self.base_url_input.setText("http://localhost:1234/v1")
            self.model_input.setText("local-model")
            self.api_key_input.setText("not-needed")

    def _on_provider_combo_changed(self) -> None:
        if not self.radio_api.isChecked():
            return
        provider = self.api_provider_combo.currentText()
        if provider == "deepseek":
            self.base_url_input.setText("https://api.deepseek.com")
            self.model_input.setText("deepseek-chat")
        elif provider == "openai":
            self.base_url_input.setText("https://api.openai.com/v1")
            self.model_input.setText("gpt-4o")
        elif provider == "claude":
            self.base_url_input.setText("https://api.anthropic.com/v1")
            self.model_input.setText("claude-3-5-sonnet-20240620")
        elif provider == "openai_compatible":
            self.base_url_input.setText("https://...")
            self.model_input.setText("")

    def _test_connection(self) -> None:
        # 临时保存配置以测试
        self._save_to_settings_manager()
        ok, msg = self.settings_manager.test_api_connection(timeout=5)
        if ok:
            QMessageBox.information(self, "连接成功", msg)
        else:
            QMessageBox.warning(self, "连接失败", msg)

    def _save_to_settings_manager(self) -> str:
        """保存当前界面配置到 api_config，返回 run_mode"""
        run_mode = ""
        local_mode = False
        provider = "deepseek"
        base_url = ""
        model = ""
        api_key = None

        if self.radio_fast.isChecked():
            run_mode = "fast"
            local_mode = True
        elif self.radio_mock.isChecked():
            run_mode = "mock"
            local_mode = True
        elif self.radio_api.isChecked():
            run_mode = "api_cloud"
            provider = self.api_provider_combo.currentText()
            base_url = self.base_url_input.text()
            model = self.model_input.text()
            api_key = self.api_key_input.text()
        elif self.radio_local.isChecked():
            run_mode = "local_model"
            provider = "local_openai_compatible"
            base_url = self.base_url_input.text()
            model = self.model_input.text()
            api_key = self.api_key_input.text()
            
            # 同时也将其作为默认记录写入 model_catalog.json，以备日后展示
            try:
                from .model_catalog import ModelCatalog
                catalog = ModelCatalog(root=self.setup_manager.root)
                cfg = catalog.load_config()
                cfg["last_local_service"] = self.local_provider_combo.currentText()
                cfg["last_local_url"] = base_url
                catalog._save(cfg)
            except Exception:
                pass

        self.settings_manager.save_api_settings(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key if api_key else None,
            local_mode=local_mode
        )
        return run_mode

    def _finish_setup(self) -> None:
        run_mode = self._save_to_settings_manager()
        
        # 保存能力选项
        multimodal = {
            "tts": self.check_tts.isChecked(),
            "text_to_image": self.check_t2i.isChecked(),
            "image_to_image": self.check_i2i.isChecked(),
            "video": self.check_video.isChecked()
        }
        
        self.setup_manager.mark_first_run_complete(run_mode, multimodal)
        self.accept()
