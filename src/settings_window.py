from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .character_pack_editor import EDITABLE_FILES, CharacterPackEditor
from .diagnostics_panel import format_diagnostics, run_diagnostics
from .icon_utils import icon as get_icon
from .relationship_state_viewer import RelationshipStateViewer
from .settings_manager import SettingsManager
from .llm.provider_registry import Provider, ProviderMeta

if TYPE_CHECKING:
    from .app import AppController


class _ApiTestWorker(QThread):
    finished_with_result = Signal(bool, str)

    def __init__(self, settings_manager: SettingsManager) -> None:
        super().__init__()
        self.settings_manager = settings_manager

    def run(self) -> None:
        ok, message = self.settings_manager.test_api_connection()
        self.finished_with_result.emit(ok, message)


class _DiagnosticsWorker(QThread):
    finished_with_text = Signal(str)

    def __init__(self, settings_manager: SettingsManager, controller: "AppController") -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.controller = controller

    def run(self) -> None:
        results = run_diagnostics(self.settings_manager, getattr(self.controller, "asset_manager", None))
        self.finished_with_text.emit(format_diagnostics(results))


class _OllamaHealthWorker(QThread):
    finished_with_result = Signal(bool, str)

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        super().__init__()
        self.base_url = base_url

    def run(self) -> None:
        import requests
        try:
            resp = requests.get(self.base_url, timeout=5)
            if resp.status_code == 200 and "Ollama" in resp.text:
                self.finished_with_result.emit(True, "Ollama 服务已运行")
            else:
                self.finished_with_result.emit(False, "Ollama 服务未响应，请先启动 Ollama。")
        except Exception as e:
            self.finished_with_result.emit(False, f"无法连接 Ollama: {e}")


class _OllamaPullWorker(QThread):
    progress_update = Signal(str)
    finished_with_result = Signal(bool, str)

    def __init__(self, model_name: str, base_url: str = "http://localhost:11434") -> None:
        super().__init__()
        self.model_name = model_name
        self.base_url = base_url
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True
        self.progress_update.emit("正在取消...")

    def run(self) -> None:
        import subprocess
        import shutil
        ollama = shutil.which("ollama")
        if not ollama:
            self.finished_with_result.emit(False, "未找到 ollama 命令，请先安装 Ollama。")
            return
        try:
            self.progress_update.emit(f"正在拉取 {self.model_name} ...")
            proc = subprocess.Popen(
                [ollama, "pull", self.model_name],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            for line in proc.stdout:
                if self._cancel:
                    proc.terminate()
                    self.finished_with_result.emit(False, "拉取已取消。")
                    return
                line = line.strip()
                if line:
                    self.progress_update.emit(line)
            proc.wait()
            if self._cancel:
                self.finished_with_result.emit(False, "拉取已取消。")
            elif proc.returncode == 0:
                self.finished_with_result.emit(True, f"模型 {self.model_name} 拉取完成。")
            else:
                self.finished_with_result.emit(False, f"拉取失败 (exit code {proc.returncode})")
        except Exception as exc:
            self.finished_with_result.emit(False, f"拉取出错: {exc}")


class SettingsWindow(QDialog):
    def __init__(self, controller: "AppController", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = SettingsManager(controller.config_manager)
        char_id = "daniya"
        if hasattr(controller, "daniya_adapter") and hasattr(controller.daniya_adapter, "character_pack"):
            pack = controller.daniya_adapter.character_pack
            if hasattr(pack, "character_id") and isinstance(pack.character_id, str):
                char_id = pack.character_id
        self.character_editor = CharacterPackEditor(character_id=char_id)
        self.relationship_viewer = RelationshipStateViewer()
        self.api_worker: _ApiTestWorker | None = None
        self.diagnostics_worker: _DiagnosticsWorker | None = None
        self.ollama_worker: _OllamaPullWorker | None = None
        self.ollama_health_worker: _OllamaHealthWorker | None = None
        self.setWindowTitle("设置中心")
        self.resize(860, 640)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_model_tab()
        self._build_pet_tab()
        self._build_character_resources_tab()
        self._build_relationship_events_tab()
        self._build_system_tab()

        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _build_model_tab(self) -> None:
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # ── 当前生效状态 ──
        self.active_profile_status = QLabel()
        self.active_profile_status.setWordWrap(True)
        self._refresh_active_status()
        scroll_layout.addWidget(self.active_profile_status)

        # 云端 API 配置
        api_group = QGroupBox("云端 API 配置 (Cloud Service)")
        api_group_layout = QVBoxLayout(api_group)
        self._build_api_section(api_group_layout)
        scroll_layout.addWidget(api_group)

        # 本地部署与引擎配置
        local_group = QGroupBox("本地部署与引擎配置 (Local Service)")
        local_group_layout = QVBoxLayout(local_group)
        self._build_local_model_section(local_group_layout)
        scroll_layout.addWidget(local_group)

        # 多模态配置
        self._build_multimodal_section(scroll_layout)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        self.tabs.addTab(tab, get_icon("chip"), "模型与引擎")

    def _build_api_section(self, parent_layout: Any) -> None:
        form = QFormLayout()
        self.api = self.settings_manager.load_api_config()
        active = self.api.get("active_provider", "deepseek")
        providers = self.api.get("providers", {})
        prov_conf = providers.get(active, {})

        # 全部云端 Provider（显示名 → key）
        all_cloud = Provider.all_cloud() + [Provider.OPENAI_COMPATIBLE]
        self._provider_display_map: dict[str, str] = {}
        display_items: list[str] = []
        for k in all_cloud:
            display = f"{ProviderMeta.get_display_name(k)}"
            self._provider_display_map[display] = k
            display_items.append(display)

        self.provider_input = QComboBox()
        self.provider_input.addItems(display_items)
        # 反查当前 active 对应的显示名
        active_display = next((d for d, k in self._provider_display_map.items() if k == active), display_items[0])
        self.provider_input.setCurrentText(active_display)
        self.base_url_input = QLineEdit(str(prov_conf.get("base_url", "")))
        self.model_input = QLineEdit(str(prov_conf.get("model", "")))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText(str(prov_conf.get("api_key_masked", "<empty>")))

        # 小眼睛切换明文/密码
        self.api_key_toggle_btn = QPushButton("显"); self.api_key_toggle_btn.setFixedWidth(32)
        self.api_key_toggle_btn.setCheckable(True)
        self.api_key_toggle_btn.toggled.connect(
            lambda checked: self.api_key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))
        key_row = QHBoxLayout(); key_row.addWidget(self.api_key_input); key_row.addWidget(self.api_key_toggle_btn)

        self.local_mode_input = QCheckBox("启用本地 fallback 模式")
        self.local_mode_input.setChecked(bool(self.api.get("local_mode", False)))
        self.api_result = QLabel("选择 Provider → 填写 API Key → 测试连接 → 保存后点击「设为当前模型」生效。\n留空 API Key 保存则不改当前 key。")
        self.api_result.setWordWrap(True)

        self.provider_input.currentTextChanged.connect(self._on_provider_changed)

        form.addRow("Provider", self.provider_input)
        form.addRow("Base URL", self.base_url_input)
        form.addRow("Model", self.model_input)
        form.addRow("API Key", key_row)
        form.addRow("本地模式", self.local_mode_input)
        parent_layout.addLayout(form)

        # 按钮行 1：保存 / 测试 / 激活
        btn1 = QHBoxLayout()
        save = QPushButton("保存 API 设置"); save.setIcon(get_icon("save"))
        test = QPushButton("测试连接"); test.setIcon(get_icon("refresh"))
        activate = QPushButton("设为当前模型"); activate.setIcon(get_icon("chip"))
        save.clicked.connect(self._save_api_settings)
        test.clicked.connect(self._test_api_connection)
        activate.clicked.connect(self._activate_cloud_profile)
        btn1.addWidget(save); btn1.addWidget(test); btn1.addWidget(activate); btn1.addStretch(1)
        parent_layout.addLayout(btn1)

        # 按钮行 2：清除 / 重置
        btn2 = QHBoxLayout()
        clear_key = QPushButton("清除当前 Key"); clear_key.setIcon(get_icon("settings"))
        clear_key.clicked.connect(self._clear_api_key)
        reset_prov = QPushButton("重置此 Provider"); reset_prov.setIcon(get_icon("refresh"))
        reset_prov.clicked.connect(self._reset_current_provider)
        btn2.addWidget(clear_key); btn2.addWidget(reset_prov); btn2.addStretch(1)
        parent_layout.addLayout(btn2)

        # "有问题？" 帮助入口
        help_btn = QPushButton("有问题？"); help_btn.setIcon(get_icon("info"))
        help_btn.setStyleSheet("QPushButton { color: #0366d6; border: 1px solid #0366d6; border-radius: 4px; padding: 4px 12px; } QPushButton:hover { background: #f0f7ff; }")
        help_btn.clicked.connect(self._show_api_help)
        parent_layout.addWidget(help_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        parent_layout.addWidget(self.api_result)
        parent_layout.addStretch(1)

    def _build_multimodal_section(self, parent_layout: Any) -> None:
        """多模态配置 — 分为 TTS / 图像 / 视频三个独立功能组，均可保存。"""
        from .provider_capability_schema import ProviderCapabilitySchema
        schema = ProviderCapabilitySchema(root=self.settings_manager.root)
        mm_config = self.settings_manager.load_multimodal_config()

        # ── TTS 语音 ──
        tts_group = QGroupBox("TTS 语音播报")
        tts_layout = QFormLayout(tts_group)
        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["none", "cloud_tts (OpenAI TTS)", "edge_tts (本地)", "system_tts (系统内置)"])
        self.tts_combo.setCurrentText(mm_config.get("tts", "none"))
        self.tts_lang = QComboBox()
        self.tts_lang.addItems(["zh-CN", "zh-TW", "en-US", "ja-JP"])
        self.tts_lang.setCurrentText(mm_config.get("tts_lang", "zh-CN"))
        tts_layout.addRow("引擎", self.tts_combo)
        tts_layout.addRow("语言", self.tts_lang)
        tts_save = QPushButton("保存 TTS 设置"); tts_save.setIcon(get_icon("save"))
        tts_save.clicked.connect(lambda: self._save_multimodal("tts"))
        tts_reset = QPushButton("重置 TTS"); tts_reset.setIcon(get_icon("refresh"))
        tts_reset.clicked.connect(lambda: self._reset_multimodal("tts"))
        tts_btns = QWidget()
        tts_btn_row = QHBoxLayout(tts_btns); tts_btn_row.setContentsMargins(0,0,0,0)
        tts_btn_row.addWidget(tts_save); tts_btn_row.addWidget(tts_reset); tts_btn_row.addStretch(1)
        tts_layout.addRow(tts_btns)
        parent_layout.addWidget(tts_group)

        # ── 图像生成 ──
        img_group = QGroupBox("文生图 / 图生图")
        img_layout = QFormLayout(img_group)
        self.t2i_combo = QComboBox()
        self.t2i_combo.addItems(["none", "openai_dalle", "stable_diffusion_local", "comfyui_local", "custom_api"])
        self.t2i_combo.setCurrentText(mm_config.get("image", "none"))
        self.i2i_combo = QComboBox()
        self.i2i_combo.addItems(["none", "stable_diffusion_local", "comfyui_local", "custom_api"])
        self.i2i_combo.setCurrentText(mm_config.get("image_to_image", "none"))
        img_layout.addRow("文生图引擎", self.t2i_combo)
        img_layout.addRow("图生图引擎", self.i2i_combo)
        img_save = QPushButton("保存图像设置"); img_save.setIcon(get_icon("save"))
        img_save.clicked.connect(lambda: self._save_multimodal("image"))
        img_reset = QPushButton("重置图像"); img_reset.setIcon(get_icon("refresh"))
        img_reset.clicked.connect(lambda: self._reset_multimodal("image"))
        img_btns = QWidget()
        img_btn_row = QHBoxLayout(img_btns); img_btn_row.setContentsMargins(0,0,0,0)
        img_btn_row.addWidget(img_save); img_btn_row.addWidget(img_reset); img_btn_row.addStretch(1)
        img_layout.addRow(img_btns)
        parent_layout.addWidget(img_group)

        # ── 视频生成 ──
        vid_group = QGroupBox("视频生成")
        vid_layout = QFormLayout(vid_group)
        self.video_combo = QComboBox()
        self.video_combo.addItems(["none", "stable_video_diffusion_local", "runway_api", "custom_api"])
        self.video_combo.setCurrentText(mm_config.get("video", "none"))
        vid_layout.addRow("视频引擎", self.video_combo)
        vid_save = QPushButton("保存视频设置"); vid_save.setIcon(get_icon("save"))
        vid_save.clicked.connect(lambda: self._save_multimodal("video"))
        vid_reset = QPushButton("重置视频"); vid_reset.setIcon(get_icon("refresh"))
        vid_reset.clicked.connect(lambda: self._reset_multimodal("video"))
        vid_btns = QWidget()
        vid_btn_row = QHBoxLayout(vid_btns); vid_btn_row.setContentsMargins(0,0,0,0)
        vid_btn_row.addWidget(vid_save); vid_btn_row.addWidget(vid_reset); vid_btn_row.addStretch(1)
        vid_layout.addRow(vid_btns)
        parent_layout.addWidget(vid_group)

        hint = QLabel("多模态功能需要对应服务运行中。留空或选 none 则不启用。")
        hint.setWordWrap(True); hint.setStyleSheet("color: gray; margin-top: 8px;")
        parent_layout.addWidget(hint)
        parent_layout.addStretch(1)

    def _build_local_model_section(self, parent_layout: Any) -> None:
        from .model_catalog import ModelCatalog

        # ── 服务配置表单 ──
        form = QFormLayout()

        self.local_service_combo = QComboBox()
        self.local_service_combo.addItems(["Ollama", "LM Studio", "llama.cpp server", "OpenAI-compatible local", "Custom"])

        self.local_base_url = QLineEdit()
        self.local_base_url.setPlaceholderText("http://localhost:11434")

        self.local_model_list = QComboBox()
        self.local_model_list.setEditable(True)

        form.addRow("服务类型", self.local_service_combo)
        form.addRow("Base URL", self.local_base_url)
        form.addRow("模型", self.local_model_list)
        parent_layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.fetch_models_btn = QPushButton("拉取模型列表"); self.fetch_models_btn.setIcon(get_icon("download"))
        self.test_local_btn = QPushButton("测试服务连接"); self.test_local_btn.setIcon(get_icon("refresh"))
        self.save_local_btn = QPushButton("保存本地模型"); self.save_local_btn.setIcon(get_icon("save"))
        self.activate_local_btn = QPushButton("设为当前模型"); self.activate_local_btn.setIcon(get_icon("chip"))
        btn_layout.addWidget(self.fetch_models_btn)
        btn_layout.addWidget(self.test_local_btn)
        btn_layout.addWidget(self.save_local_btn)
        btn_layout.addWidget(self.activate_local_btn)
        btn_layout.addStretch(1)
        parent_layout.addLayout(btn_layout)

        self.local_status = QLabel("状态：未测试")
        self.local_status.setWordWrap(True)
        parent_layout.addWidget(self.local_status)

        self.fetch_models_btn.clicked.connect(self._fetch_local_models)
        self.test_local_btn.clicked.connect(self._test_local_service)
        self.save_local_btn.clicked.connect(self._save_local_model_settings)
        self.activate_local_btn.clicked.connect(self._activate_local_profile)

        # 本地模型重置按钮
        local_reset_btn = QPushButton("清空本地配置"); local_reset_btn.setIcon(get_icon("refresh"))
        local_reset_btn.clicked.connect(self._clear_local_config)
        parent_layout.addWidget(local_reset_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # ── 推荐模型目录 ──
        catalog = ModelCatalog(root=self.settings_manager.root)
        recommended = catalog.get_recommended_models()

        if recommended:
            rec_group = QGroupBox("推荐模型（内置目录）")
            rec_layout = QVBoxLayout(rec_group)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMinimumHeight(220)
            scroll.setMaximumHeight(380)
            cards_widget = QWidget()
            cards_layout = QVBoxLayout(cards_widget)
            cards_layout.setSpacing(8)

            for m in recommended:
                card = self._build_model_card(m)
                cards_layout.addWidget(card)

            cards_layout.addStretch(1)
            scroll.setWidget(cards_widget)
            rec_layout.addWidget(scroll)
            parent_layout.addWidget(rec_group)

        # ── 许可证与下载器 ──
        lic_label = QLabel(
            "使用本地模型前请确认已阅读并同意对应模型的许可证条款。\n"
            "点击下方按钮可查看模型详情并启动 Ollama 拉取。"
        )
        lic_label.setWordWrap(True)
        lic_label.setStyleSheet(
            "color: #856404; background-color: #fff3cd; border: 1px solid #ffeeba; padding: 10px; margin-top: 15px;"
        )
        parent_layout.addWidget(lic_label)

        self.downloader_btn = QPushButton("打开内置下载器"); self.downloader_btn.setIcon(get_icon("download"))
        self.downloader_btn.clicked.connect(self._open_model_downloader)
        parent_layout.addWidget(self.downloader_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # 导入自定义模型
        import_model_btn = QPushButton("导入自定义模型"); import_model_btn.setIcon(get_icon("upload"))
        import_model_btn.clicked.connect(self._import_custom_model)
        parent_layout.addWidget(import_model_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        parent_layout.addStretch(1)

    def _build_model_card(self, m: dict) -> QWidget:
        card = QWidget()
        card.setStyleSheet(
            "QWidget#modelCard { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 6px; padding: 10px; }"
        )
        card.setObjectName("modelCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)

        # 第一行：模型名 + 厂商
        header = QHBoxLayout()
        name_label = QLabel(f"<b>{m.get('display_name', m.get('id', ''))}</b>")
        vendor_label = QLabel(f"{m.get('vendor', '')}  |  {m.get('size_class', '')}  |  ~{m.get('estimated_disk_size', '')}")
        vendor_label.setStyleSheet("color: #6c757d;")
        header.addWidget(name_label)
        header.addStretch(1)
        header.addWidget(vendor_label)
        layout.addLayout(header)

        # 第二行：硬件要求
        hw = m.get("recommended_hardware", "")
        if hw:
            hw_label = QLabel(f"硬件：{hw}")
            hw_label.setStyleSheet("color: #495057; font-size: 12px;")
            layout.addWidget(hw_label)

        # 第三行：许可证
        lic = m.get("license_name", "")
        lic_url = m.get("license_url", "")
        if lic:
            lic_text = f"许可：<a href='{lic_url}'>{lic}</a>" if lic_url else f"许可：{lic}"
            lic_label = QLabel(lic_text)
            lic_label.setOpenExternalLinks(True)
            lic_label.setStyleSheet("font-size: 12px;")
            layout.addWidget(lic_label)

        # 第四行：适用场景
        rec_for = m.get("recommended_for", [])
        if rec_for:
            tags = ", ".join(rec_for)
            tags_label = QLabel(f"适用：{tags}")
            tags_label.setStyleSheet("color: #28a745; font-size: 12px;")
            layout.addWidget(tags_label)

        # 按钮行
        btn_row = QHBoxLayout()
        select_btn = QPushButton("选择此模型")
        select_btn.setFixedWidth(100)
        select_btn.clicked.connect(lambda: self._on_select_recommended_model(m))

        pull_btn = QPushButton("Ollama 拉取"); pull_btn.setIcon(get_icon("download"))
        pull_btn.setFixedWidth(100)
        pull_btn.clicked.connect(lambda: self._on_ollama_pull_model(m))

        official_url = m.get("official_url", "")
        if official_url:
            official_btn = QPushButton("官方页面")
            official_btn.setFixedWidth(80)
            official_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(official_url)))
            btn_row.addWidget(official_btn)

        lic_url = m.get("license_url", "")
        if lic_url:
            lic_btn = QPushButton("许可证")
            lic_btn.setFixedWidth(70)
            lic_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(lic_url)))
            btn_row.addWidget(lic_btn)

        detail_btn = QPushButton("详情")
        detail_btn.setFixedWidth(50)
        detail_btn.clicked.connect(lambda: self._on_show_model_detail(m))

        btn_row.addWidget(select_btn)
        btn_row.addWidget(pull_btn)
        btn_row.addWidget(detail_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        return card

    def _on_select_recommended_model(self, m: dict) -> None:
        ollama_method = None
        for dm in m.get("download_methods", []):
            if dm.get("type") == "ollama":
                ollama_method = dm
                break

        model_name = ollama_method["model"] if ollama_method else m.get("display_name", "")

        # 自动设置服务类型为 Ollama 和默认 URL
        self.local_service_combo.setCurrentText("Ollama")
        self.local_base_url.setText("http://localhost:11434")
        self.local_model_list.setCurrentText(model_name)
        self.local_status.setText(f"状态：已选择 {model_name}（请点击「保存本地模型」完成配置）")
        self.local_status.setStyleSheet("color: green;")

    def _on_ollama_pull_model(self, m: dict) -> None:
        ollama_method = None
        for dm in m.get("download_methods", []):
            if dm.get("type") == "ollama":
                ollama_method = dm
                break

        if not ollama_method:
            QMessageBox.information(self, "提示", "该模型暂不支持 Ollama 一键拉取，请通过详情页手动下载。")
            return

        model_name = ollama_method["model"]
        lic_name = m.get("license_name", "未知许可证")
        lic_url = m.get("license_url", "")
        disk_size = m.get("estimated_disk_size", "未知")
        hardware = m.get("recommended_hardware", "未知")

        # 许可证确认（含磁盘和硬件提示）
        msg = (
            f"即将通过 Ollama 拉取模型：\n\n"
            f"  模型：{model_name}\n"
            f"  磁盘占用：~{disk_size}\n"
            f"  硬件要求：{hardware}\n"
            f"  许可证：{lic_name}\n\n"
        )
        if lic_url:
            msg += f"许可证详情：{lic_url}\n\n"
        msg += "请确认您已阅读并同意该模型的许可证条款。\n继续拉取？"

        reply = QMessageBox.question(
            self, "许可证确认", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 先检查 Ollama 是否运行
        self.local_status.setText("状态：正在检测 Ollama 服务...")
        self.local_status.setStyleSheet("color: #007bff;")
        self.downloader_btn.setEnabled(False)

        self.ollama_health_worker = _OllamaHealthWorker()
        self.ollama_health_worker.finished_with_result.connect(
            lambda ok, msg: self._on_health_check_done(ok, msg, model_name)
        )
        self.ollama_health_worker.finished.connect(self.ollama_health_worker.deleteLater)
        self.ollama_health_worker.start()

    def _on_health_check_done(self, ok: bool, msg: str, model_name: str) -> None:
        if not ok:
            self.downloader_btn.setEnabled(True)
            self.local_status.setText(f"状态：{msg}")
            self.local_status.setStyleSheet("color: red;")
            return

        self.local_status.setText(f"状态：正在拉取 {model_name} ...")
        self.local_status.setStyleSheet("color: #007bff;")

        self.ollama_worker = _OllamaPullWorker(model_name)
        self.ollama_worker.progress_update.connect(
            lambda text: self.local_status.setText(f"状态：[拉取中] {text}")
        )
        self.ollama_worker.finished_with_result.connect(self._on_ollama_pull_finished)
        self.ollama_worker.finished.connect(self.ollama_worker.deleteLater)
        self.ollama_worker.start()

    def _on_ollama_pull_finished(self, ok: bool, msg: str) -> None:
        self.downloader_btn.setEnabled(True)
        if ok:
            self.local_status.setText(f"状态：{msg}")
            self.local_status.setStyleSheet("color: green;")
            # 自动刷新模型列表
            self._fetch_local_models()
        else:
            self.local_status.setText(f"状态：{msg}")
            self.local_status.setStyleSheet("color: red;")

    def _on_show_model_detail(self, m: dict) -> None:
        lines = [
            f"模型：{m.get('display_name', '')}",
            f"厂商：{m.get('vendor', '')}",
            f"参数量：{m.get('size_class', '')}",
            f"磁盘占用：~{m.get('estimated_disk_size', '')}",
            f"硬件要求：{m.get('recommended_hardware', '')}",
            f"许可证：{m.get('license_name', '')}",
            f"许可链接：{m.get('license_url', '')}",
            f"官网：{m.get('official_url', '')}",
            f"文档：{m.get('docs_url', '')}",
            "",
            "下载方式：",
        ]
        for dm in m.get("download_methods", []):
            t = dm.get("type", "")
            if t == "ollama":
                lines.append(f"  Ollama: ollama pull {dm.get('model', '')}")
            elif t == "direct_gguf":
                lines.append(f"  GGUF 直链: {dm.get('filename', '')}")
            elif t == "external_link":
                lines.append(f"  外部链接: {dm.get('label', '')} - {dm.get('model_id', '')}")

        QMessageBox.information(self, f"模型详情 - {m.get('display_name', '')}", "\n".join(lines))

    def _open_model_downloader(self) -> None:
        from .model_catalog import ModelCatalog
        catalog = ModelCatalog(root=self.settings_manager.root)
        recommended = catalog.get_recommended_models()

        if not recommended:
            QMessageBox.information(self, "内置下载器", "当前推荐模型目录为空。")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("内置下载器 - 选择模型")
        dialog.setMinimumWidth(550)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        dlg_layout = QVBoxLayout(dialog)

        dlg_layout.addWidget(QLabel("请选择要查看/下载的推荐模型："))

        combo = QComboBox()
        for m in recommended:
            combo.addItem(
                f"{m.get('display_name', '')} ({m.get('vendor', '')}, ~{m.get('estimated_disk_size', '')})",
                m.get("id"),
            )
        dlg_layout.addWidget(combo)

        # 模型信息展示
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(180)

        def _update_info():
            idx = combo.currentIndex()
            if idx < 0:
                return
            m = recommended[idx]
            lines = [
                f"名称: {m.get('display_name', '')}",
                f"厂商: {m.get('vendor', '')}  |  参数量: {m.get('size_class', '')}  |  磁盘: ~{m.get('estimated_disk_size', '')}",
                f"硬件要求: {m.get('recommended_hardware', '')}",
                f"许可证: {m.get('license_name', '')}",
                f"许可链接: {m.get('license_url', '')}",
                f"官网: {m.get('official_url', '')}",
                "",
                "下载方式:",
            ]
            for dm in m.get("download_methods", []):
                t = dm.get("type", "")
                if t == "ollama":
                    lines.append(f"  • Ollama: ollama pull {dm.get('model', '')}")
                elif t == "direct_gguf":
                    lines.append(f"  • GGUF 直链: {dm.get('filename', '')}")
                elif t == "external_link":
                    lines.append(f"  • {dm.get('label', '')}: {dm.get('model_id', '')}")
            info_text.setPlainText("\n".join(lines))

        combo.currentIndexChanged.connect(_update_info)
        _update_info()
        dlg_layout.addWidget(info_text)

        # 三个许可证确认勾选框
        dlg_layout.addWidget(QLabel("<b>使用前请确认：</b>"))
        cb1 = QCheckBox("我已阅读并同意该模型的许可证条款")
        cb2 = QCheckBox("我理解商业使用需自行确认授权")
        cb3 = QCheckBox("我理解本项目不随包分发模型权重")
        dlg_layout.addWidget(cb1)
        dlg_layout.addWidget(cb2)
        dlg_layout.addWidget(cb3)

        # 按钮行
        btn_row = QHBoxLayout()
        pull_btn = QPushButton("Ollama 拉取"); pull_btn.setIcon(get_icon("download"))
        pull_btn.setEnabled(False)
        select_btn = QPushButton("选择并填入配置"); select_btn.setIcon(get_icon("chip"))
        cancel_btn = QPushButton("取消"); cancel_btn.setIcon(get_icon("settings"))

        def _on_check_changed():
            all_checked = cb1.isChecked() and cb2.isChecked() and cb3.isChecked()
            pull_btn.setEnabled(all_checked)

        cb1.toggled.connect(lambda _: _on_check_changed())
        cb2.toggled.connect(lambda _: _on_check_changed())
        cb3.toggled.connect(lambda _: _on_check_changed())

        def _do_pull():
            idx = combo.currentIndex()
            if idx >= 0:
                dialog.accept()
                self._on_ollama_pull_model(recommended[idx])

        def _do_select():
            idx = combo.currentIndex()
            if idx >= 0:
                dialog.accept()
                self._on_select_recommended_model(recommended[idx])

        pull_btn.clicked.connect(_do_pull)
        select_btn.clicked.connect(_do_select)
        cancel_btn.clicked.connect(dialog.reject)

        btn_row.addWidget(pull_btn)
        btn_row.addWidget(select_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        dlg_layout.addLayout(btn_row)

        dialog.exec()

    def _fetch_local_models(self) -> None:
        from .local_model_manager import LocalModelManager
        service = self.local_service_combo.currentText()
        url = self.local_base_url.text()
        self.local_status.setText("状态：正在获取...")
        try:
            models = LocalModelManager.fetch_model_list(service, url)
            self.local_model_list.clear()
            if models:
                self.local_model_list.addItems(models)
                self.local_status.setText(f"状态：成功获取 {len(models)} 个模型")
            else:
                self.local_status.setText("状态：未获取到模型列表，请检查服务或手动输入模型名")
        except Exception as e:
            self.local_status.setText(f"状态：获取失败 ({str(e)})")

    def _test_local_service(self) -> None:
        from .local_model_manager import LocalModelManager
        service = self.local_service_combo.currentText()
        url = self.local_base_url.text()
        self.local_status.setText("状态：正在连接...")
        ok, msg = LocalModelManager.test_connection(service, url)
        self.local_status.setText(f"状态：{msg}")
        if ok:
            self.local_status.setStyleSheet("color: green;")
        else:
            self.local_status.setStyleSheet("color: red;")

    def _save_local_model_settings(self) -> None:
        service = self.local_service_combo.currentText()
        url = self.local_base_url.text().strip()
        model = self.local_model_list.currentText().strip()

        if not url or not model:
            self.local_status.setText("状态：请填写 Base URL 和模型名称")
            self.local_status.setStyleSheet("color: red;")
            return

        provider = ProviderMeta.service_label_to_key(service)

        # 保存并激活为本地 profile
        self.settings_manager.save_and_activate_local_model_profile(
            provider=provider,
            base_url=url,
            model=model,
            service_label=service,
        )
        self.controller.chat_client.reload()
        self.local_status.setText(f"状态：已保存并激活 {provider} → {model}  ✓ 已生效")
        self.local_status.setStyleSheet("color: green;")
        self._refresh_active_status()

    def _refresh_active_status(self) -> None:
        """刷新顶部「当前生效模型」状态标签。"""
        profiles_data = self.settings_manager.load_model_profiles()
        active_id = profiles_data.get("active_text_profile_id", "")
        profiles = profiles_data.get("profiles", [])
        active_profile = next((p for p in profiles if p.get("id") == active_id), None)

        if not active_profile:
            self.active_profile_status.setText("当前生效模型：无")
            self.active_profile_status.setStyleSheet(
                "background: #f8d7da; border: 1px solid #f5c6cb; padding: 8px; margin-bottom: 10px; color: #721c24;"
            )
            return

        name = active_profile.get("name", active_id)
        model = active_profile.get("model", "")
        source = active_profile.get("source", "cloud")
        source_label = "本地" if source == "local" else "云端"
        provider = active_profile.get("provider", "")

        text = f"当前生效模型：{name} ({model}) [{source_label}]"
        self.active_profile_status.setText(text)
        self.active_profile_status.setStyleSheet(
            "background: #d4edda; border: 1px solid #c3e6cb; padding: 8px; margin-bottom: 10px; color: #155724;"
        )

    def _activate_cloud_profile(self) -> None:
        """保存云端 API 设置并切换为当前生效模型。"""
        self._save_api_settings()
        provider = self._current_provider_key()
        target_id = ProviderMeta.make_profile_id(provider)
        self._do_switch_profile(target_id, f"云端 {provider}")

    def _activate_local_profile(self) -> None:
        """保存本地模型设置并切换为当前生效模型。"""
        self._save_local_model_settings()

        service = self.local_service_combo.currentText()
        model = self.local_model_list.currentText().strip()
        provider = ProviderMeta.service_label_to_key(service)

        target_id = ProviderMeta.make_profile_id(provider, model)
        self._do_switch_profile(target_id, f"本地 {service} → {model}")

    def _do_switch_profile(self, target_id: str, label: str) -> None:
        """执行模型切换，失败时回退。"""
        from .llm.provider_manager import ProviderManager
        pm = ProviderManager(api_config=self.settings_manager.load_api_config())
        ok, msg = pm.switch_active_profile(target_id)

        if ok:
            self._refresh_active_status()
            self.controller.chat_client.reload()
            self.local_status.setText(f"状态：已切换至 {label}  ✓ 已生效")
            self.local_status.setStyleSheet("color: green;")
        else:
            self._refresh_active_status()
            self.local_status.setText(f"状态：切换失败 ({msg}) — 已回退到上一个可用模型")
            self.local_status.setStyleSheet("color: red;")

    def _build_pet_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        app_config = self.settings_manager.load_app_config()
        pet = app_config.get("pet", {})
        window = app_config.get("window", {})

        self.pet_size = QSpinBox()
        self.pet_size.setRange(int(pet.get("min_pet_height", 80)), int(pet.get("max_pet_height", 160)))
        self.pet_size.setValue(int(pet.get("pet_height", 96)))
        self.always_on_top = QCheckBox("保持置顶")
        self.always_on_top.setChecked(bool(window.get("always_on_top", True)))
        self.opacity = QSpinBox()
        self.opacity.setRange(30, 100)
        self.opacity.setSuffix("%")
        self.opacity.setValue(int(window.get("opacity_percent", 100)))
        self.idle_chat = QCheckBox("启用闲聊")
        self.idle_chat.setChecked(bool(app_config.get("idle_chat_enabled", True)))
        self.idle_minutes = QSpinBox()
        self.idle_minutes.setRange(1, 240)
        self.idle_minutes.setValue(int(app_config.get("idle_chat_minutes", 10)))
        self.hourly_chime = QCheckBox("整点报时")
        self.hourly_chime.setChecked(bool(app_config.get("hourly_chime_enabled", True)))
        self.reminder_enabled = QCheckBox("提醒功能")
        self.reminder_enabled.setChecked(bool(app_config.get("reminder_enabled", True)))
        self.day_night = QCheckBox("昼夜作息")
        self.day_night.setChecked(bool(app_config.get("day_night_enabled", True)))

        form.addRow("桌宠大小", self.pet_size)
        form.addRow("置顶", self.always_on_top)
        form.addRow("透明度", self.opacity)
        form.addRow("闲聊", self.idle_chat)
        form.addRow("闲聊间隔", self.idle_minutes)
        form.addRow("整点报时", self.hourly_chime)
        form.addRow("提醒", self.reminder_enabled)
        form.addRow("昼夜作息", self.day_night)
        layout.addLayout(form)
        save = QPushButton("保存并尽量即时生效"); save.setIcon(get_icon("save"))
        save.clicked.connect(self._save_pet_settings)
        self.pet_timer_hint = QLabel("提示：闲聊、整点报时、提醒、昼夜作息等定时器配置保存后，可能需要重启后完全生效。")
        self.pet_timer_hint.setWordWrap(True)
        self.pet_result = QLabel("")
        self.pet_result.setWordWrap(True)
        layout.addWidget(save, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.pet_timer_hint)
        layout.addWidget(self.pet_result)
        layout.addStretch(1)
        self.tabs.addTab(tab, get_icon("internet"), "桌宠")

    def _build_actions_tab(self) -> None:
        """已合并到 _build_character_resources_tab"""
        pass

    def _build_character_tab(self) -> None:
        """已合并到 _build_character_resources_tab"""
        pass

    def _build_character_resources_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 最顶部的角色信息区域
        char_group = QGroupBox("当前角色信息")
        char_layout = QFormLayout(char_group)

        self.char_id_label = QLabel()
        self.char_path_label = QLabel()
        self.char_status_label = QLabel()
        self.char_status_label.setWordWrap(True)

        # 角色选择下拉框
        self.char_selector = QComboBox()

        btn_char_row = QHBoxLayout()
        switch_char_btn = QPushButton("切换并加载角色")
        switch_char_btn.clicked.connect(self._switch_character)
        reload_char_btn = QPushButton("重新加载当前角色")
        reload_char_btn.clicked.connect(self._reload_character)
        btn_char_row.addWidget(switch_char_btn)
        btn_char_row.addWidget(reload_char_btn)
        btn_char_row.addStretch(1)

        char_layout.addRow("当前角色 ID:", self.char_id_label)
        char_layout.addRow("角色包路径:", self.char_path_label)
        char_layout.addRow("加载/校验状态:", self.char_status_label)
        char_layout.addRow("切换角色 (本地):", self.char_selector)
        char_layout.addRow("", btn_char_row)

        layout.addWidget(char_group)

        # 上半部分：动作资源
        actions_group = QGroupBox("动作资源")
        actions_layout = QVBoxLayout(actions_group)
        self.action_status = QTextEdit()
        self.action_status.setReadOnly(True)
        self.action_combo = QComboBox()
        self.action_combo.addItems(["idle", "talk", "clicked", "drag", "sleep", "happy", "remind", "soft_idle", "close_idle", "bubble", "look_away"])
        btn_row = QHBoxLayout()
        reload_btn = QPushButton("重载动作资源"); reload_btn.setIcon(get_icon("refresh"))
        test_btn = QPushButton("测试动作"); test_btn.setIcon(get_icon("chip"))
        reload_btn.clicked.connect(self._reload_actions)
        test_btn.clicked.connect(self._test_action)
        btn_row.addWidget(self.action_combo)
        btn_row.addWidget(test_btn)
        btn_row.addWidget(reload_btn)
        btn_row.addStretch(1)
        actions_layout.addLayout(btn_row)
        actions_layout.addWidget(self.action_status)
        layout.addWidget(actions_group)

        # 下半部分：角色包编辑器
        pack_group = QGroupBox("角色包编辑器")
        pack_layout = QVBoxLayout(pack_group)
        self.character_status = QLabel("")
        self.character_status.setWordWrap(True)
        self.pack_file_combo = QComboBox()
        self.pack_file_combo.addItems(["character.yaml", "speech.yaml", "relationship.yaml", "events.yaml", "lore.md", "lore_index.yaml", "actions.yaml"])
        self.pack_file_combo.currentTextChanged.connect(self._load_pack_file)
        self.pack_editor_text = QTextEdit()
        pack_btn_row = QHBoxLayout()
        save = QPushButton("备份并保存 YAML"); save.setIcon(get_icon("save"))
        validate = QPushButton("重新校验"); validate.setIcon(get_icon("info"))
        open_file = QPushButton("打开文件"); open_file.setIcon(get_icon("document"))
        save.clicked.connect(self._save_pack_file)
        validate.clicked.connect(self._refresh_character_status)
        open_file.clicked.connect(self._open_pack_file)
        pack_btn_row.addWidget(self.pack_file_combo)
        pack_btn_row.addWidget(save)
        pack_btn_row.addWidget(validate)
        pack_btn_row.addWidget(open_file)
        pack_btn_row.addStretch(1)
        pack_layout.addWidget(self.character_status)
        pack_layout.addLayout(pack_btn_row)
        pack_layout.addWidget(self.pack_editor_text)
        layout.addWidget(pack_group)

        self.tabs.addTab(tab, get_icon("document"), "角色与资源")
        self._refresh_action_status()
        self._refresh_character_status()
        self._load_pack_file(self.pack_file_combo.currentText())
        self._refresh_character_list()
        self._refresh_char_info()

    def _refresh_character_list(self) -> None:
        self.char_selector.clear()
        import os
        from core.character_loader import default_character_root
        root_path = default_character_root()
        if root_path.exists():
            for name in sorted(os.listdir(root_path)):
                if (root_path / name).is_dir():
                    self.char_selector.addItem(name)
        curr = self.controller.app_config.get("current_character", "daniya")
        index = self.char_selector.findText(curr)
        if index >= 0:
            self.char_selector.setCurrentIndex(index)

    def _refresh_char_info(self) -> None:
        adapter = self.controller.daniya_adapter
        char_pack = adapter.character_pack
        self.char_id_label.setText(char_pack.character_id)
        self.char_path_label.setText(str(char_pack.root))

        if adapter.load_errors:
            self.char_status_label.setText("异常 (已回退)\n" + "\n".join(adapter.load_errors))
            self.char_status_label.setStyleSheet("color: red;")
        else:
            self.char_status_label.setText("正常")
            self.char_status_label.setStyleSheet("color: green;")

    def _switch_character(self) -> None:
        target = self.char_selector.currentText()
        if not target:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.controller.reload_character(target)
            self._refresh_char_info()
            self._refresh_character_status()
            self._refresh_action_status()
            self._load_pack_file(self.pack_file_combo.currentText())
            index = self.char_selector.findText(self.controller.daniya_adapter.character_pack.character_id)
            if index >= 0:
                self.char_selector.setCurrentIndex(index)
        finally:
            QApplication.restoreOverrideCursor()

    def _reload_character(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.controller.reload_character()
            self._refresh_char_info()
            self._refresh_character_status()
            self._refresh_action_status()
            self._load_pack_file(self.pack_file_combo.currentText())
            index = self.char_selector.findText(self.controller.daniya_adapter.character_pack.character_id)
            if index >= 0:
                self.char_selector.setCurrentIndex(index)
        finally:
            QApplication.restoreOverrideCursor()

    def _build_relationship_tab(self) -> None:
        """已合并到 _build_relationship_events_tab"""
        pass

    def _build_events_tab(self) -> None:
        """已合并到 _build_relationship_events_tab"""
        pass

    def _build_relationship_events_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        rel_group = QGroupBox("关系状态")
        rel_layout = QVBoxLayout(rel_group)
        self.relationship_text = QTextEdit()
        self.relationship_text.setReadOnly(True)
        rel_buttons = QHBoxLayout()
        refresh = QPushButton("刷新"); refresh.setIcon(get_icon("refresh"))
        export = QPushButton("导出关系状态"); export.setIcon(get_icon("upload"))
        reset = QPushButton("备份后重置"); reset.setIcon(get_icon("protect"))
        refresh.clicked.connect(self._refresh_relationship)
        export.clicked.connect(self._export_relationship)
        reset.clicked.connect(self._reset_relationship)
        rel_buttons.addWidget(refresh)
        rel_buttons.addWidget(export)
        rel_buttons.addWidget(reset)
        rel_buttons.addStretch(1)
        rel_layout.addLayout(rel_buttons)
        rel_layout.addWidget(self.relationship_text)
        layout.addWidget(rel_group)

        evt_group = QGroupBox("事件日志")
        evt_layout = QVBoxLayout(evt_group)
        self.events_text = QTextEdit()
        self.events_text.setReadOnly(True)
        evt_refresh = QPushButton("刷新事件"); evt_refresh.setIcon(get_icon("refresh"))
        evt_refresh.clicked.connect(self._refresh_events)
        evt_layout.addWidget(evt_refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        evt_layout.addWidget(self.events_text)
        layout.addWidget(evt_group)

        self.tabs.addTab(tab, get_icon("download"), "关系与事件")
        self._refresh_relationship()
        self._refresh_events()

    def _build_system_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        data_group = QGroupBox("数据管理")
        data_layout = QVBoxLayout(data_group)
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        data_buttons = QHBoxLayout()
        refresh_data = QPushButton("刷新数据状态"); refresh_data.setIcon(get_icon("refresh"))
        backup = QPushButton("导出备份"); backup.setIcon(get_icon("save"))
        open_dir = QPushButton("打开数据目录"); open_dir.setIcon(get_icon("laptop"))
        refresh_data.clicked.connect(self._refresh_data)
        backup.clicked.connect(self._backup_data)
        open_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.relationship_viewer.data_dir))))
        data_buttons.addWidget(refresh_data)
        data_buttons.addWidget(backup)
        data_buttons.addWidget(open_dir)
        data_buttons.addStretch(1)
        data_layout.addLayout(data_buttons)
        data_layout.addWidget(self.data_text)
        layout.addWidget(data_group)

        # 使用帮助（可折叠）
        help_group = QGroupBox("使用帮助")
        help_layout = QVBoxLayout(help_group)
        self.help_toggle_btn = QPushButton("展开使用帮助 ▼"); self.help_toggle_btn.setIcon(get_icon("info"))
        self.help_toggle_btn.setStyleSheet("QPushButton { text-align: left; font-size: 12px; color: #0366d6; border: none; }")
        self.help_toggle_btn.clicked.connect(self._toggle_help)
        help_layout.addWidget(self.help_toggle_btn)

        self.help_content = QWidget()
        self.help_content.setVisible(False)
        help_content_layout = QVBoxLayout(self.help_content)
        guide_text = QTextEdit()
        guide_text.setReadOnly(True)
        guide_text.setMaximumHeight(200)
        guide_text.setPlainText(
            "【模型与引擎】\n"
            "1. 在云端 API 配置中选择 Provider，填写 API Key，测试连接后点「设为当前模型」。\n"
            "2. 本地模型：选择服务类型，拉取模型列表或手动输入，保存后点「设为当前模型」。\n"
            "3. 云端/本地 Provider 独立存储，切换不冲突。绿色状态栏显示当前生效模型。\n"
            "4. 切换失败自动回退上一个可用模型。\n\n"
            "【多模态】\n"
            "5. TTS/图像/视频独立选择。none 则不启用。保存写入 multimodal_config.json。\n\n"
            "【常见操作】\n"
            "6. 清除当前 Key → 从 .env 删除。重置 Provider → 恢复默认值。\n"
            "7. 自定义云端可接入任意 OpenAI 兼容 API（智谱/Kimi/豆包等 16+）。\n"
            "8. 所有危险操作均有确认弹窗。"
        )
        help_content_layout.addWidget(guide_text)
        help_layout.addWidget(self.help_content)
        layout.addWidget(help_group)

        diag_group = QGroupBox("系统诊断")
        diag_layout = QVBoxLayout(diag_group)
        self.diagnostics_text = QTextEdit()
        self.diagnostics_text.setReadOnly(True)
        run = QPushButton("运行诊断"); run.setIcon(get_icon("settings"))
        run.clicked.connect(self._run_diagnostics)
        diag_layout.addWidget(run, alignment=Qt.AlignmentFlag.AlignLeft)
        diag_layout.addWidget(self.diagnostics_text)
        layout.addWidget(diag_group)

        self.tabs.addTab(tab, get_icon("settings"), "系统")
        self._refresh_data()

    def _current_provider_key(self) -> str:
        return self._provider_display_map.get(self.provider_input.currentText(), "deepseek")

    def _on_provider_changed(self, display_or_id: str) -> None:
        key = self._provider_display_map.get(display_or_id, display_or_id)
        prov_conf = self.api.get("providers", {}).get(key, {})
        meta = ProviderMeta.get(key)
        self.base_url_input.setText(str(prov_conf.get("base_url") or meta.get("base_url", "")))
        self.model_input.setText(str(prov_conf.get("model") or meta.get("default_model", "")))
        self.api_key_input.setPlaceholderText(str(prov_conf.get("api_key_masked", "<empty>")))

    def _save_api_settings(self) -> None:
        api_key = self.api_key_input.text()
        self.settings_manager.save_api_settings(
            provider=self._current_provider_key(),
            base_url=self.base_url_input.text(),
            model=self.model_input.text(),
            api_key=api_key if api_key else None,
            local_mode=self.local_mode_input.isChecked(),
        )
        self.controller.chat_client.reload()
        self.api_key_input.clear()
        self.api_result.setText("API 设置已保存；API Key 已写入 .env 或保持原值。")
        self.controller.window.speak("……API 设置保存好了。希望你没填错。")
        self.controller.window.animation_manager.trigger_happy()
        self._refresh_active_status()

    def _test_api_connection(self) -> None:
        if self.api_worker is not None and self.api_worker.isRunning():
            return
        self.api_result.setText("正在后台测试连接...")
        self.api_worker = _ApiTestWorker(self.settings_manager)
        self.api_worker.finished_with_result.connect(lambda ok, msg: self.api_result.setText(("通过：" if ok else "失败：") + msg))
        self.api_worker.finished.connect(self.api_worker.deleteLater)
        self.api_worker.start()

    def _save_pet_settings(self) -> None:
        config = self.settings_manager.load_app_config()
        config.setdefault("pet", {})["pet_height"] = self.pet_size.value()
        config.setdefault("pet", {})["target_height"] = self.pet_size.value()
        config.setdefault("window", {})["always_on_top"] = self.always_on_top.isChecked()
        config.setdefault("window", {})["opacity_percent"] = self.opacity.value()
        config["idle_chat_enabled"] = self.idle_chat.isChecked()
        config["idle_chat_minutes"] = self.idle_minutes.value()
        config["hourly_chime_enabled"] = self.hourly_chime.isChecked()
        config["reminder_enabled"] = self.reminder_enabled.isChecked()
        config["day_night_enabled"] = self.day_night.isChecked()
        self.settings_manager.save_app_config(config)
        self.controller.app_config.update(config)
        self.controller.save_pet_height(self.pet_size.value())
        self.controller.window.set_always_on_top(self.always_on_top.isChecked())
        self.controller.window.setWindowOpacity(self.opacity.value() / 100)
        self.pet_result.setText("已保存。大小、置顶、透明度已即时生效；部分定时器配置重启后完全生效。")
        self.controller.window.speak("……保存好啦。别又忘了哦。")
        self.controller.window.animation_manager.trigger_happy()

    def _refresh_action_status(self) -> None:
        asset_manager = self.controller.asset_manager
        try:
            manifest = asset_manager.manifest()
            source = "private" if "assets\\private" in str(asset_manager.active_asset_dir()) or "assets/private" in str(asset_manager.active_asset_dir()) else "placeholder"
            lines = [f"资源来源: {source}", f"资源目录: {asset_manager.active_asset_dir()}", f"manifest: OK"]
            for action in ["idle", "talk", "clicked", "drag", "sleep", "happy", "remind", "soft_idle", "close_idle", "bubble", "look_away"]:
                frames = asset_manager.frames_for_state(action)
                status = "available" if frames and any(frame.exists() for frame in frames) else "missing"
                lines.append(f"- {action}: {status}; frames={[str(frame.name) for frame in frames[:3]]}")
        except Exception as exc:
            lines = [f"manifest: FAILED {exc.__class__.__name__}"]
        self.action_status.setPlainText("\n".join(lines))

    def _reload_actions(self) -> None:
        self.controller.asset_manager._manifest = None
        self.controller.asset_manager._asset_dir = None
        self.controller.window.animation_manager.refresh()
        self._refresh_action_status()

    def _test_action(self) -> None:
        action = self.action_combo.currentText()
        self.controller.window.set_pet_state(action)
        self._refresh_action_status()

    def _refresh_character_status(self) -> None:
        status = self.character_editor.status()
        lines = [f"路径: {status['path']}", f"加载: {status['loaded']}", f"校验: {status['validation_ok']}"]
        if status.get("validation_errors"):
            lines.append(str(status["validation_errors"]))
        for name, file_status in status.get("files", {}).items():
            lines.append(f"- {name}: exists={file_status['exists']} editable={file_status['editable']} yaml_ok={file_status['yaml_ok']}")
        self.character_status.setText("\n".join(lines))

    def _load_pack_file(self, name: str) -> None:
        try:
            self.pack_editor_text.setPlainText(self.character_editor.read_file(name))
            self.pack_editor_text.setReadOnly(name not in EDITABLE_FILES)
        except Exception as exc:
            self.pack_editor_text.setPlainText(f"读取失败：{exc.__class__.__name__}")
            self.pack_editor_text.setReadOnly(True)

    def _save_pack_file(self) -> None:
        name = self.pack_file_combo.currentText()
        ok, message, backup = self.character_editor.save_yaml_safely(name, self.pack_editor_text.toPlainText())
        QMessageBox.information(self, "角色包保存", message + (f"\n备份: {backup}" if backup else ""))
        self._refresh_character_status()

    def _open_pack_file(self) -> None:
        path = self.character_editor.pack_path / self.pack_file_combo.currentText()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _refresh_relationship(self) -> None:
        status = self.relationship_viewer.status()
        state = status["relationship_state"]
        state_lines = [f"{key}: {value}" for key, value in state.items()]
        self.relationship_text.setPlainText("\n".join(state_lines) or "relationship_state.json 不可读或为空。")

    def _refresh_events(self) -> None:
        status = self.relationship_viewer.status()
        events = status["event_log"][-20:]
        event_lines = [
            f"- {e.get('timestamp','')} event={e.get('event_id')} source={e.get('source')} effect={e.get('relationship_effect')} lore={e.get('lore_fragments_used')} {e.get('stage_before')}->{e.get('stage_after')}"
            for e in events
            if isinstance(e, dict)
        ]
        if hasattr(self, "events_text"):
            self.events_text.setPlainText("\n".join(event_lines) or "暂无事件记录。")

    def _export_relationship(self) -> None:
        path = self.relationship_viewer.export_state()
        QMessageBox.information(self, "导出完成", f"已导出到：{path}")

    def _reset_relationship(self) -> None:
        result = QMessageBox.question(self, "重置关系状态", "会先自动备份，再重置 relationship_state。继续吗？")
        if result != QMessageBox.StandardButton.Yes:
            return
        ok, message, backup = self.relationship_viewer.reset_state_with_backup()
        if ok:
            QMessageBox.information(self, "关系状态", message + (f"\n备份: {backup}" if backup else ""))
            self._refresh_relationship()
        else:
            QMessageBox.warning(self, "关系状态", message)

    def _refresh_data(self) -> None:
        status = self.relationship_viewer.status()
        paths = self.relationship_viewer.paths()
        lines = [f"data_dir: {status['data_dir']} exists={status['exists']}"]
        for key, path in paths.items():
            lines.append(f"- {key}: exists={path.exists()} readable={status.get(key + '_readable')} error={status.get(key + '_error')}")
        self.data_text.setPlainText("\n".join(lines))

    def _backup_data(self) -> None:
        path = self.relationship_viewer.backup_data_dir()
        QMessageBox.information(self, "数据备份", f"已备份到：{path}")
        self._refresh_data()

    def _toggle_help(self) -> None:
        if self.help_content.isVisible():
            self.help_content.setVisible(False)
            self.help_toggle_btn.setText("展开使用帮助 ▼")
        else:
            self.help_content.setVisible(True)
            self.help_toggle_btn.setText("收起使用帮助 ▲")

    def _run_diagnostics(self) -> None:
        if self.diagnostics_worker is not None and self.diagnostics_worker.isRunning():
            return
        self.diagnostics_text.setPlainText("正在后台诊断...")
        self.diagnostics_worker = _DiagnosticsWorker(self.settings_manager, self.controller)
        self.diagnostics_worker.finished_with_text.connect(self.diagnostics_text.setPlainText)
        self.diagnostics_worker.finished.connect(self.diagnostics_worker.deleteLater)
        self.diagnostics_worker.start()

    def _show_api_help(self) -> None:
        """弹出云端 API 配置帮助窗口。分三区：预设 Provider / CC Switch / 自部署代理。"""
        dialog = QDialog(self)
        dialog.setWindowTitle("云端 API 帮助 — 去哪获取 Key 和 Base URL")
        dialog.setMinimumSize(680, 560)
        layout = QVBoxLayout(dialog)

        tabs = QTabWidget()

        # ── Tab 1: 云端 API 厂商 ──
        cloud_tab = QWidget()
        cloud_layout = QVBoxLayout(cloud_tab)
        cloud_intro = QLabel(
            "<b>预设 Provider</b> — 直接在下方选择，或点「填入配置」一键填入<br>"
            "<b>第三方/国产 API</b> — 选「自定义云端 (Custom)」后填入对应 URL"
        )
        cloud_intro.setWordWrap(True)
        cloud_layout.addWidget(cloud_intro)

        cloud_scroll = QScrollArea()
        cloud_scroll.setWidgetResizable(True)
        cloud_content = QWidget()
        cloud_content_layout = QVBoxLayout(cloud_content)
        cloud_content_layout.setSpacing(6)

        providers_help = [
            ("DeepSeek", "deepseek", "https://api.deepseek.com", "deepseek-chat",
             "https://platform.deepseek.com/api_keys", "国内性价比最高，中文能力极强，2026年新款 V3"),
            ("OpenAI", "openai", "https://api.openai.com/v1", "gpt-4.1-mini",
             "https://platform.openai.com/api-keys", "GPT-4.1系列，性价比极高的默认模型"),
            ("Claude (Anthropic)", "claude", "https://api.anthropic.com/v1", "claude-sonnet-4-6",
             "https://console.anthropic.com/keys", "2026年最新 Sonnet 4.6，多文件编码王者"),
            ("Google Gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash",
             "https://aistudio.google.com/apikey", "2026年 Gemini 2.5 Flash，多模态 + 超长上下文"),
            ("Mistral AI", "mistral", "https://api.mistral.ai/v1", "mistral-large-latest",
             "https://console.mistral.ai/api-keys", "欧洲领先 AI，开源友好"),
            ("Groq", "groq", "https://api.groq.com/openai/v1", "llama-4-maverick-17b-128e-instruct",
             "https://console.groq.com/keys", "Llama 4 Maverick，开源旗舰级推理速度"),
            ("智谱 GLM", "custom_cloud", "https://open.bigmodel.cn/api/paas/v4", "glm-4.5-flash",
             "https://open.bigmodel.cn/", "2026年 GLM-4.5，清华系中文能力最强"),
            ("硅基流动 (SiliconFlow)", "custom_cloud", "https://api.siliconflow.cn/v1", "Qwen/Qwen3-235B-A22B",
             "https://siliconflow.cn/", "Qwen3-235B，国产开源最强旗舰"),
            ("月之暗面 Kimi", "custom_cloud", "https://api.moonshot.cn/v1", "kimi-k2.5",
             "https://platform.moonshot.cn/", "Kimi K2.5，超长上下文+深度推理"),
            ("零一万物", "custom_cloud", "https://api.lingyiwanwu.com/v1", "yi-lightning",
             "https://platform.lingyiwanwu.com/", "Yi Lightning，速度极快，开源可商用"),
            ("字节豆包", "custom_cloud", "https://ark.cn-beijing.volces.com/api/v3", "需在控制台创建 endpoint",
             "https://console.volcengine.com/ark", "火山引擎 Ark，超低延迟企业级"),
            ("腾讯混元", "custom_cloud", "https://api.hunyuan.cloud.tencent.com/v1", "hunyuan-lite",
             "https://cloud.tencent.com/product/hunyuan", "腾讯出品，企业级稳定"),
            ("OpenRouter", "custom_cloud", "https://openrouter.ai/api/v1", "openai/gpt-4o",
             "https://openrouter.ai/keys", "聚合 200+ 模型，统一 API 访问"),
            ("Together AI", "custom_cloud", "https://api.together.xyz/v1", "mistralai/Mixtral-8x7B",
             "https://api.together.xyz/", "开源模型推理平台"),
        ]

        for name, provider_key, url, model, reg_url, desc in providers_help:
            card = self._build_help_card(name, provider_key, url, model, reg_url, desc, dialog)
            cloud_content_layout.addWidget(card)
        cloud_content_layout.addStretch(1)
        cloud_scroll.setWidget(cloud_content)
        cloud_layout.addWidget(cloud_scroll)
        tabs.addTab(cloud_tab, get_icon("cloud"), "云端 API 厂商")

        # ── Tab 2: CC Switch 本地代理 ──
        cc_tab = QWidget()
        cc_layout = QVBoxLayout(cc_tab)
        cc_scroll = QScrollArea()
        cc_scroll.setWidgetResizable(True)
        cc_content = QWidget()
        cc_content_layout = QVBoxLayout(cc_content)
        cc_content_layout.setSpacing(10)

        cc_title = QLabel(
            "<b>CC Switch — 本地 AI API 代理</b><br>"
            "免费开源跨平台桌面应用，启动本地 HTTP 代理统一管理和转发 AI API 请求。"
        )
        cc_title.setWordWrap(True)
        cc_content_layout.addWidget(cc_title)

        cc_what = QLabel(
            "<b>是什么</b><br>"
            "CC Switch 在你的电脑上启动一个本地代理服务器（默认 127.0.0.1:15721），"
            "所有 AI 工具的 API 请求先发到代理，代理再转发到你选择的供应商。"
            "支持 50+ 预设供应商，一键切换，无需改任何代码。"
        )
        cc_what.setWordWrap(True)
        cc_what.setStyleSheet("background:#f0f7ff; border:1px solid #b6d4fe; border-radius:6px; padding:10px;")
        cc_content_layout.addWidget(cc_what)

        cc_why = QLabel(
            "<b>为什么用</b>"
            "<table cellspacing='4'>"
            "<tr><td>✓</td><td>图形界面一键切换模型，告别手动改 JSON</td></tr>"
            "<tr><td>✓</td><td>统一代理入口，一个地址覆盖 Claude Code / Codex / Gemini CLI / 达妮娅</td></tr>"
            "<tr><td>✓</td><td>自动故障转移 + 熔断，主供应商挂了自动切备用</td></tr>"
            "<tr><td>✓</td><td>Anthropic ↔ OpenAI ↔ Gemini 协议自动转换</td></tr>"
            "<tr><td>✓</td><td>实时请求日志 + Token 用量统计</td></tr>"
            "</table>"
        )
        cc_why.setWordWrap(True)
        cc_content_layout.addWidget(cc_why)

        cc_how = QLabel(
            "<b>工作原理</b><br>"
            "<code>达妮娅 → 127.0.0.1:15721 (CC Switch) → GLM / DeepSeek / Kimi / Claude / ...</code>"
        )
        cc_how.setWordWrap(True)
        cc_how.setStyleSheet("background:#f8f9fa; border:1px solid #e1e4e8; border-radius:6px; padding:10px;")
        cc_content_layout.addWidget(cc_how)

        cc_setup = QLabel(
            "<b>在达妮娅中接入 CC Switch</b><br>"
            "1. 下载安装 CC Switch（GitHub: "
            "<a href='https://github.com/farion1231/cc-switch'>farion1231/cc-switch</a>，官网: cswitch.io）<br>"
            "2. 启动 CC Switch，在界面中选择要用的模型供应商<br>"
            "3. 在达妮娅设置中心填入：<br>"
            "&nbsp;&nbsp;&nbsp;Provider: <b>自定义云端 (Custom)</b><br>"
            "&nbsp;&nbsp;&nbsp;Base URL: <code>http://127.0.0.1:15721/v1</code><br>"
            "&nbsp;&nbsp;&nbsp;Model: 与 CC Switch 中显示的模型名一致<br>"
            "&nbsp;&nbsp;&nbsp;API Key: 任意非空字符串（如 cc-switch）<br>"
            "4. 点「测试连接」→「设为当前模型」<br><br>"
            "<b>之后在 CC Switch 界面切换模型，达妮娅无需任何改动，立即生效。</b>"
        )
        cc_setup.setWordWrap(True)
        cc_setup.setStyleSheet("background:#fff3cd; border:1px solid #ffeeba; border-radius:6px; padding:10px;")
        cc_content_layout.addWidget(cc_setup)

        cc_protocol = QLabel(
            "<b>协议转换能力</b><br>"
            "CC Switch 自动完成 Anthropic Messages ↔ OpenAI Chat/Responses ↔ Gemini Native 格式互转。"
            "达妮娅发出的是 OpenAI 格式请求，CC Switch 可将其转发到任何供应商。"
        )
        cc_protocol.setWordWrap(True)
        cc_content_layout.addWidget(cc_protocol)

        cc_links = QHBoxLayout()
        cc_gh_btn = QPushButton(" GitHub 仓库"); cc_gh_btn.setIcon(get_icon("internet"))
        cc_gh_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/farion1231/cc-switch")))
        cc_dl_btn = QPushButton(" 下载 CC Switch"); cc_dl_btn.setIcon(get_icon("download"))
        cc_dl_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/farion1231/cc-switch/releases")))
        cc_fill_btn = QPushButton(" 填入达妮娅配置")
        cc_fill_btn.setIcon(get_icon("chip"))
        def _fill_cc():
            display = next((d for d, v in self._provider_display_map.items() if v == "custom_cloud"), None)
            if display:
                self.provider_input.setCurrentText(display)
            self.base_url_input.setText("http://127.0.0.1:15721/v1")
            dialog.accept()
        cc_fill_btn.clicked.connect(_fill_cc)
        cc_links.addWidget(cc_gh_btn); cc_links.addWidget(cc_dl_btn); cc_links.addWidget(cc_fill_btn); cc_links.addStretch(1)
        cc_content_layout.addLayout(cc_links)

        cc_content_layout.addStretch(1)
        cc_scroll.setWidget(cc_content)
        cc_layout.addWidget(cc_scroll)
        tabs.addTab(cc_tab, get_icon("download"), "CC Switch 代理")

        # ── Tab 3: 自部署代理 ──
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        custom_scroll = QScrollArea()
        custom_scroll.setWidgetResizable(True)
        custom_content = QWidget()
        custom_content_layout = QVBoxLayout(custom_content)
        custom_content_layout.setSpacing(10)

        custom_title = QLabel(
            "<b>自部署 API 代理 / 中转</b><br>"
            "如果你不想用 CC Switch，也可以自己搭建代理服务。以下方案均可提供 OpenAI 兼容端点，"
            "填入达妮娅的「自定义云端 (Custom)」即可使用。"
        )
        custom_title.setWordWrap(True)
        custom_content_layout.addWidget(custom_title)

        # one-api
        oa_card = QWidget()
        oa_card.setStyleSheet("QWidget#proxyCard { background:#f8f9fa; border:1px solid #e1e4e8; border-radius:6px; }")
        oa_card.setObjectName("proxyCard")
        oa_inner = QVBoxLayout(oa_card)
        oa_inner.addWidget(QLabel("<b>one-api</b> — 最成熟的中文社区 OpenAI 代理管理面板"))
        oa_inner.addWidget(QLabel(
            "• GitHub: <a href='https://github.com/songquanpeng/one-api'>songquanpeng/one-api</a><br>"
            "• 部署: <code>docker run -d -p 3000:3000 justsong/one-api</code><br>"
            "• 功能: 多供应商管理、Key 池、额度控制、用量统计、Web 管理面板<br>"
            "• 支持 30+ 供应商: OpenAI / Claude / Gemini / DeepSeek / 智谱 / 讯飞 / 百度 / 阿里 / 腾讯 / 字节<br>"
            "• 接入达妮娅: 自定义云端 → <code>http://你的服务器:3000/v1</code> → 在面板中选的模型名"
        ))
        oa_btn_row = QHBoxLayout()
        oa_gh = QPushButton(" GitHub"); oa_gh.setIcon(get_icon("internet"))
        oa_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/songquanpeng/one-api")))
        oa_btn_row.addWidget(oa_gh); oa_btn_row.addStretch(1)
        oa_inner.addLayout(oa_btn_row)
        custom_content_layout.addWidget(oa_card)

        # new-api
        na_card = QWidget()
        na_card.setStyleSheet("QWidget#proxyCard { background:#f8f9fa; border:1px solid #e1e4e8; border-radius:6px; }")
        na_card.setObjectName("proxyCard")
        na_inner = QVBoxLayout(na_card)
        na_inner.addWidget(QLabel("<b>new-api</b> — one-api 增强分支，界面更现代"))
        na_inner.addWidget(QLabel(
            "• GitHub: <a href='https://github.com/Calcium-Ion/new-api'>Calcium-Ion/new-api</a><br>"
            "• 部署: <code>docker run -d -p 3000:3000 calciumion/new-api</code><br>"
            "• 额外功能: 马甲包、RPM/TPM 精细化控制、数据看板<br>"
            "• 接入达妮娅: 同 one-api，自定义云端 → <code>http://你的服务器:3000/v1</code>"
        ))
        na_btn_row = QHBoxLayout()
        na_gh = QPushButton(" GitHub"); na_gh.setIcon(get_icon("internet"))
        na_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Calcium-Ion/new-api")))
        na_btn_row.addWidget(na_gh); na_btn_row.addStretch(1)
        na_inner.addLayout(na_btn_row)
        custom_content_layout.addWidget(na_card)

        # AI Worker Proxy
        aw_card = QWidget()
        aw_card.setStyleSheet("QWidget#proxyCard { background:#f8f9fa; border:1px solid #e1e4e8; border-radius:6px; }")
        aw_card.setObjectName("proxyCard")
        aw_inner = QVBoxLayout(aw_card)
        aw_inner.addWidget(QLabel("<b>AI Worker Proxy</b> — Cloudflare Workers 免费方案，零服务器成本"))
        aw_inner.addWidget(QLabel(
            "• GitHub: <a href='https://github.com/zxcloli666/AI-Worker-Proxy'>zxcloli666/AI-Worker-Proxy</a><br>"
            "• 部署: 复制代码到 Cloudflare Workers → 1 分钟上线<br>"
            "• 功能: 自动故障转移、Token 轮换、免费托管<br>"
            "• 注意: Cloudflare 在国内部分网络可能较慢<br>"
            "• 接入达妮娅: 自定义云端 → <code>https://你的worker名.workers.dev/v1</code>"
        ))
        aw_btn_row = QHBoxLayout()
        aw_gh = QPushButton(" GitHub"); aw_gh.setIcon(get_icon("internet"))
        aw_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/zxcloli666/AI-Worker-Proxy")))
        aw_btn_row.addWidget(aw_gh); aw_btn_row.addStretch(1)
        aw_inner.addLayout(aw_btn_row)
        custom_content_layout.addWidget(aw_card)

        # Proxify
        px_card = QWidget()
        px_card.setStyleSheet("QWidget#proxyCard { background:#f8f9fa; border:1px solid #e1e4e8; border-radius:6px; }")
        px_card.setObjectName("proxyCard")
        px_inner = QVBoxLayout(px_card)
        px_inner.addWidget(QLabel("<b>Proxify</b> — 轻量级 Go 实现，适合低配 VPS"))
        px_inner.addWidget(QLabel(
            "• GitHub: <a href='https://github.com/poixeai/proxify'>poixeai/proxify</a><br>"
            "• 部署: 单二进制文件，10MB 以内，一行命令启动<br>"
            "• 接入达妮娅: 自定义云端 → <code>http://你的VPS:端口/v1</code>"
        ))
        px_btn_row = QHBoxLayout()
        px_gh = QPushButton(" GitHub"); px_gh.setIcon(get_icon("internet"))
        px_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/poixeai/proxify")))
        px_btn_row.addWidget(px_gh); px_btn_row.addStretch(1)
        px_inner.addLayout(px_btn_row)
        custom_content_layout.addWidget(px_card)

        # 通用接入公式
        formula = QLabel(
            "<b>接入达妮娅的通用公式</b><br>"
            "无论用哪种代理方案，在达妮娅中只需填 3 个字段：<br><br>"
            "&nbsp;&nbsp;Base URL = <code>&lt;你的代理地址&gt;/v1</code><br>"
            "&nbsp;&nbsp;Model = 代理转发的模型名<br>"
            "&nbsp;&nbsp;API Key = 代理要求的 Key（没有就任意填）<br><br>"
            "达妮娅只做 <code>POST {Base URL}/chat/completions</code> + Bearer Auth，<b>不区分厂商、不校验来源、不做白名单</b>。"
        )
        formula.setWordWrap(True)
        formula.setStyleSheet("background:#f0f7ff; border:1px solid #b6d4fe; border-radius:6px; padding:10px;")
        custom_content_layout.addWidget(formula)

        custom_content_layout.addStretch(1)
        custom_scroll.setWidget(custom_content)
        custom_layout.addWidget(custom_scroll)
        tabs.addTab(custom_tab, get_icon("host"), "自部署代理")

        layout.addWidget(tabs)

        close_btn = QPushButton("关闭"); close_btn.setIcon(get_icon("settings"))
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _build_help_card(self, name: str, provider_key: str, url: str, model: str,
                         reg_url: str, desc: str, dialog: QDialog) -> QWidget:
        card = QWidget()
        card.setStyleSheet(
            "QWidget#apiHelpCard { background: #f8f9fa; border: 1px solid #e1e4e8; "
            "border-radius: 6px; } QWidget#apiHelpCard:hover { border-color: #0366d6; }"
        )
        card.setObjectName("apiHelpCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(10, 6, 10, 6)

        tr = QHBoxLayout()
        tr.addWidget(QLabel(f"<b>{name}</b>")); tr.addStretch(1)
        if provider_key in Provider.all_cloud():
            tag = QLabel("预设"); tag.setStyleSheet("color:#22863a;font-size:10px;border:1px solid #22863a;border-radius:3px;padding:0 4px;")
        else:
            tag = QLabel("自定义"); tag.setStyleSheet("color:#6f42c1;font-size:10px;border:1px solid #6f42c1;border-radius:3px;padding:0 4px;")
        tr.addWidget(tag); cl.addLayout(tr)

        info = QLabel(desc); info.setWordWrap(True); info.setStyleSheet("color:#586069;font-size:11px;"); cl.addWidget(info)
        cl.addWidget(QLabel(f"<span style='color:#586069;font-size:11px;'>URL:</span> <code style='font-size:11px;'>{url}</code>"))
        cl.addWidget(QLabel(f"<span style='color:#586069;font-size:11px;'>Model:</span> <code style='font-size:11px;'>{model}</code>"))

        br = QHBoxLayout()
        reg_btn = QPushButton(" 注册获取 Key"); reg_btn.setIcon(get_icon("internet"))
        reg_btn.setFixedHeight(26); reg_btn.setStyleSheet("font-size:11px;")
        reg_btn.clicked.connect(lambda _, u=reg_url: QDesktopServices.openUrl(QUrl(u)))
        br.addWidget(reg_btn)

        copy_btn = QPushButton(" 复制 URL"); copy_btn.setFixedHeight(26); copy_btn.setStyleSheet("font-size:11px;")
        def _mkcopy(_u, _b):
            def _h(): QApplication.clipboard().setText(_u); _b.setText(" 已复制!")
            return _h
        copy_btn.clicked.connect(_mkcopy(url, copy_btn))
        br.addWidget(copy_btn)

        def _mkfill(_k, _u, _m):
            def _h():
                d = next((x for x, v in self._provider_display_map.items() if v == _k), None)
                if d: self.provider_input.setCurrentText(d)
                self.base_url_input.setText(_u); self.model_input.setText(_m); dialog.accept()
            return _h
        fill_btn = QPushButton(" 填入配置"); fill_btn.setFixedHeight(26); fill_btn.setStyleSheet("font-size:11px;")
        fill_btn.clicked.connect(_mkfill(provider_key, url, model))
        br.addWidget(fill_btn); br.addStretch(1); cl.addLayout(br)
        return card

    def _clear_api_key(self) -> None:
        """清除当前选中 Provider 的 API Key。"""
        provider = self._current_provider_key()
        env_key = ProviderMeta.get_api_key_env(provider)
        if not env_key:
            QMessageBox.information(self, "提示", f"{provider} 不需要 API Key（通过本地服务连接）。")
            return
        reply = QMessageBox.question(
            self, "确认清除",
            f"确定要从 .env 中删除 {env_key} 吗？\n此操作不可恢复，之后需要重新填写。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings_manager.clear_api_key(env_key)
            self.api_key_input.clear()
            self.api_key_input.setPlaceholderText("<empty>")
            self.api_result.setText(f"已清除 {env_key}。")

    def _reset_current_provider(self) -> None:
        """将当前 Provider 恢复到默认 Base URL 和 Model。"""
        provider = self._current_provider_key()
        meta = ProviderMeta.get(provider)
        reply = QMessageBox.question(
            self, "确认重置",
            f"将 {provider} 的 Base URL 和 Model 恢复为默认值：\n\n"
            f"URL: {meta['base_url']}\nModel: {meta['default_model']}\n\n继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.base_url_input.setText(meta["base_url"])
            self.model_input.setText(meta["default_model"])
            self.api_result.setText(f"{provider} 已重置为默认值（需点击保存和设为当前模型生效）。")

    def _clear_local_config(self) -> None:
        """清空本地模型配置。"""
        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空本地模型配置吗？\n这将清空服务类型、Base URL 和模型名称。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.local_service_combo.setCurrentIndex(0)
            self.local_base_url.clear()
            self.local_model_list.clear()
            self.local_status.setText("状态：已清空本地配置")
            self.local_status.setStyleSheet("color: #6c757d;")

    def _reset_multimodal(self, section: str) -> None:
        """重置多模态配置为 none。"""
        config = self.settings_manager.load_multimodal_config()
        if section == "tts":
            config["tts"] = "none"
            config["tts_lang"] = "zh-CN"
            self.tts_combo.setCurrentText("none")
            self.tts_lang.setCurrentText("zh-CN")
        elif section == "image":
            config["image"] = "none"
            config["image_to_image"] = "none"
            self.t2i_combo.setCurrentText("none")
            self.i2i_combo.setCurrentText("none")
        elif section == "video":
            config["video"] = "none"
            self.video_combo.setCurrentText("none")
        self.settings_manager.save_multimodal_config(config)
        QMessageBox.information(self, "已重置", f"多模态 {section} 已重置为 none。")

    def _save_multimodal(self, section: str) -> None:
        """保存多模态配置。"""
        config = self.settings_manager.load_multimodal_config()
        if section == "tts":
            config["tts"] = self.tts_combo.currentText()
            config["tts_lang"] = self.tts_lang.currentText()
        elif section == "image":
            config["image"] = self.t2i_combo.currentText()
            config["image_to_image"] = self.i2i_combo.currentText()
        elif section == "video":
            config["video"] = self.video_combo.currentText()
        self.settings_manager.save_multimodal_config(config)
        QMessageBox.information(self, "已保存", f"多模态 {section} 配置已保存。")
        self.controller.window.speak(f"……多模态{section}配置保存好啦。别又忘了哦。")
        self.controller.window.animation_manager.trigger_happy()

    def _import_custom_model(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("导入自定义模型")
        dialog.setMinimumWidth(500)
        form = QFormLayout(dialog)

        name_input = QLineEdit(); name_input.setPlaceholderText("my-custom-model")
        provider_combo = QComboBox()
        provider_combo.addItems([Provider.LOCAL_OPENAI_COMPATIBLE, Provider.LLAMA_CPP, Provider.LM_STUDIO, Provider.CUSTOM])
        url_input = QLineEdit(); url_input.setPlaceholderText("http://localhost:8080/v1")
        model_input = QLineEdit(); model_input.setPlaceholderText(" custom-model-name")
        desc_input = QLineEdit(); desc_input.setPlaceholderText("我的魔改模型 · 0.5B · ~500MB")

        form.addRow("模型名称", name_input)
        form.addRow("Provider 类型", provider_combo)
        form.addRow("Base URL", url_input)
        form.addRow("模型 ID (API 用)", model_input)
        form.addRow("描述 (厂商 · 大小 · 磁盘)", desc_input)

        btn_row = QHBoxLayout()
        ok = QPushButton("导入"); ok.setIcon(get_icon("save"))
        cancel = QPushButton("取消"); cancel.setIcon(get_icon("settings"))
        btn_row.addStretch(1); btn_row.addWidget(ok); btn_row.addWidget(cancel)
        form.addRow(btn_row)

        def do_import():
            name = name_input.text().strip()
            url = url_input.text().strip()
            model = model_input.text().strip()
            if not name or not url or not model:
                QMessageBox.warning(dialog, "错误", "请填写模型名称、Base URL 和模型 ID。")
                return
            provider = provider_combo.currentText()
            self.settings_manager.save_local_model_profile(
                provider=provider, base_url=url, model=model, service_label=name,
            )
            self.local_model_list.addItem(model)
            self.local_model_list.setCurrentText(model)
            self.local_service_combo.setCurrentText(
                next((s for s in [self.local_service_combo.itemText(i) for i in range(self.local_service_combo.count())]
                      if provider in s.lower().replace(" ", "_") or s.lower().startswith(provider[:4])),
                     self.local_service_combo.currentText()))
            self.local_base_url.setText(url)
            self.local_status.setText(f"状态：已导入 {name} ({model})")
            dialog.accept()

        ok.clicked.connect(do_import)
        cancel.clicked.connect(dialog.reject)
        dialog.exec()
