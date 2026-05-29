from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
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
from .relationship_state_viewer import RelationshipStateViewer
from .settings_manager import SettingsManager

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
        self.character_editor = CharacterPackEditor()
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
        self._build_data_system_tab()

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

        # 多模态配置（预留，折叠）
        multi_group = QGroupBox("多模态配置 (v0.46+ 预留)")
        multi_group.setStyleSheet("QGroupBox { color: gray; }")
        multi_layout = QVBoxLayout(multi_group)
        self._build_multimodal_section(multi_layout)
        scroll_layout.addWidget(multi_group)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        self.tabs.addTab(tab, "模型与引擎")

    def _build_api_section(self, parent_layout: Any) -> None:
        form = QFormLayout()
        self.api = self.settings_manager.load_api_config()
        active = self.api.get("active_provider", "deepseek")
        providers = self.api.get("providers", {})
        prov_conf = providers.get(active, {})

        self.provider_input = QComboBox()
        self.provider_input.addItems(["deepseek", "openai", "claude", "openai_compatible", "local_openai_compatible"])
        self.provider_input.setCurrentText(str(active))
        self.base_url_input = QLineEdit(str(prov_conf.get("base_url", "")))
        self.model_input = QLineEdit(str(prov_conf.get("model", "")))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText(str(prov_conf.get("api_key_masked", "<empty>")))
        self.local_mode_input = QCheckBox("启用本地 fallback 模式")
        self.local_mode_input.setChecked(bool(self.api.get("local_mode", False)))
        self.api_result = QLabel("API Key 不会完整写入日志；留空保存则不改当前 key。")
        self.api_result.setWordWrap(True)

        self.provider_input.currentTextChanged.connect(self._on_provider_changed)

        form.addRow("Provider", self.provider_input)
        form.addRow("Base URL", self.base_url_input)
        form.addRow("Model", self.model_input)
        form.addRow("API Key", self.api_key_input)
        form.addRow("本地模式", self.local_mode_input)
        parent_layout.addLayout(form)

        buttons = QHBoxLayout()
        save = QPushButton("保存 API 设置")
        test = QPushButton("测试连接")
        activate = QPushButton("设为当前模型")
        save.clicked.connect(self._save_api_settings)
        test.clicked.connect(self._test_api_connection)
        activate.clicked.connect(self._activate_cloud_profile)
        buttons.addWidget(save)
        buttons.addWidget(test)
        buttons.addWidget(activate)
        buttons.addStretch(1)
        parent_layout.addLayout(buttons)
        parent_layout.addWidget(self.api_result)
        parent_layout.addStretch(1)

    def _build_multimodal_section(self, parent_layout: Any) -> None:
        from .provider_capability_schema import ProviderCapabilitySchema
        schema = ProviderCapabilitySchema(root=self.settings_manager.root)

        form = QFormLayout()

        self.tts_combo = QComboBox()
        self.tts_combo.addItems(schema.get_tts_providers())
        self.tts_combo.setCurrentText("none")

        self.t2i_combo = QComboBox()
        self.t2i_combo.addItems(schema.get_image_providers())
        self.t2i_combo.setCurrentText("none")

        self.video_combo = QComboBox()
        self.video_combo.addItems(schema.get_video_providers())
        self.video_combo.setCurrentText("none")

        form.addRow("TTS 语音引擎", self.tts_combo)
        form.addRow("文生图/图生图引擎", self.t2i_combo)
        form.addRow("视频引擎", self.video_combo)

        parent_layout.addLayout(form)

        hint = QLabel("当前版本这些选项仅作为架构占位，修改不产生实际效果。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; margin-top: 10px;")
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
        self.fetch_models_btn = QPushButton("拉取模型列表")
        self.test_local_btn = QPushButton("测试服务连接")
        self.save_local_btn = QPushButton("保存本地模型")
        self.activate_local_btn = QPushButton("设为当前模型")
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

        self.downloader_btn = QPushButton("打开内置下载器")
        self.downloader_btn.clicked.connect(self._open_model_downloader)
        parent_layout.addWidget(self.downloader_btn, alignment=Qt.AlignmentFlag.AlignLeft)

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

        pull_btn = QPushButton("Ollama 拉取")
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
        pull_btn = QPushButton("Ollama 拉取")
        pull_btn.setEnabled(False)
        select_btn = QPushButton("选择并填入配置")
        cancel_btn = QPushButton("取消")

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

        provider = service.lower().replace(" ", "_")
        if "openai-compatible" in provider:
            provider = "local_openai_compatible"
        elif "llama.cpp" in provider:
            provider = "llama_cpp"
        elif "lm studio" in provider:
            provider = "lm_studio"
        elif provider == "custom":
            provider = "local_openai_compatible"

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
        provider = self.provider_input.currentText()
        target_id = f"{provider}_default"
        self._do_switch_profile(target_id, f"云端 {provider}")

    def _activate_local_profile(self) -> None:
        """保存本地模型设置并切换为当前生效模型。"""
        self._save_local_model_settings()

        service = self.local_service_combo.currentText()
        model = self.local_model_list.currentText().strip()
        provider = service.lower().replace(" ", "_")
        if "openai-compatible" in provider:
            provider = "local_openai_compatible"
        elif "llama.cpp" in provider:
            provider = "llama_cpp"
        elif "lm studio" in provider:
            provider = "lm_studio"
        elif provider == "custom":
            provider = "local_openai_compatible"

        target_id = f"{provider}_{model.replace(':', '_').replace('.', '_')}"
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
        save = QPushButton("保存并尽量即时生效")
        save.clicked.connect(self._save_pet_settings)
        self.pet_timer_hint = QLabel("提示：闲聊、整点报时、提醒、昼夜作息等定时器配置保存后，可能需要重启后完全生效。")
        self.pet_timer_hint.setWordWrap(True)
        self.pet_result = QLabel("")
        self.pet_result.setWordWrap(True)
        layout.addWidget(save, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.pet_timer_hint)
        layout.addWidget(self.pet_result)
        layout.addStretch(1)
        self.tabs.addTab(tab, "桌宠")

    def _build_actions_tab(self) -> None:
        """已合并到 _build_character_resources_tab"""
        pass

    def _build_character_tab(self) -> None:
        """已合并到 _build_character_resources_tab"""
        pass

    def _build_character_resources_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 上半部分：动作资源
        actions_group = QGroupBox("动作资源")
        actions_layout = QVBoxLayout(actions_group)
        self.action_status = QTextEdit()
        self.action_status.setReadOnly(True)
        self.action_combo = QComboBox()
        self.action_combo.addItems(["idle", "talk", "clicked", "drag", "sleep", "happy", "remind", "soft_idle", "close_idle", "bubble", "look_away"])
        btn_row = QHBoxLayout()
        reload_btn = QPushButton("重载动作资源")
        test_btn = QPushButton("测试动作")
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
        save = QPushButton("备份并保存 YAML")
        validate = QPushButton("重新校验")
        open_file = QPushButton("打开文件")
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

        self.tabs.addTab(tab, "角色与资源")
        self._refresh_action_status()
        self._refresh_character_status()
        self._load_pack_file(self.pack_file_combo.currentText())

    def _build_relationship_tab(self) -> None:
        """已合并到 _build_relationship_events_tab"""
        pass

    def _build_events_tab(self) -> None:
        """已合并到 _build_relationship_events_tab"""
        pass

    def _build_data_system_tab(self) -> None:
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # 1. 关系状态
        rel_group = QGroupBox("关系状态")
        rel_layout = QVBoxLayout(rel_group)
        self.relationship_text = QTextEdit()
        self.relationship_text.setReadOnly(True)
        rel_buttons = QHBoxLayout()
        refresh = QPushButton("刷新")
        export = QPushButton("导出关系状态")
        reset = QPushButton("备份后重置")
        refresh.clicked.connect(self._refresh_relationship)
        export.clicked.connect(self._export_relationship)
        reset.clicked.connect(self._reset_relationship)
        rel_buttons.addWidget(refresh)
        rel_buttons.addWidget(export)
        rel_buttons.addWidget(reset)
        rel_buttons.addStretch(1)
        rel_layout.addLayout(rel_buttons)
        rel_layout.addWidget(self.relationship_text)
        scroll_layout.addWidget(rel_group)

        # 2. 事件日志
        evt_group = QGroupBox("事件日志")
        evt_layout = QVBoxLayout(evt_group)
        self.events_text = QTextEdit()
        self.events_text.setReadOnly(True)
        evt_refresh = QPushButton("刷新事件")
        evt_refresh.clicked.connect(self._refresh_events)
        evt_layout.addWidget(evt_refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        evt_layout.addWidget(self.events_text)
        scroll_layout.addWidget(evt_group)

        # 3. 数据管理
        data_group = QGroupBox("数据管理")
        data_layout = QVBoxLayout(data_group)
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        data_buttons = QHBoxLayout()
        refresh_data = QPushButton("刷新数据状态")
        backup = QPushButton("导出备份")
        open_dir = QPushButton("打开数据目录")
        refresh_data.clicked.connect(self._refresh_data)
        backup.clicked.connect(self._backup_data)
        open_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.relationship_viewer.data_dir))))
        data_buttons.addWidget(refresh_data)
        data_buttons.addWidget(backup)
        data_buttons.addWidget(open_dir)
        data_buttons.addStretch(1)
        data_layout.addLayout(data_buttons)
        data_layout.addWidget(self.data_text)
        scroll_layout.addWidget(data_group)

        # 4. 系统诊断
        diag_group = QGroupBox("系统诊断")
        diag_layout = QVBoxLayout(diag_group)
        self.diagnostics_text = QTextEdit()
        self.diagnostics_text.setReadOnly(True)
        run = QPushButton("运行诊断")
        run.clicked.connect(self._run_diagnostics)
        diag_layout.addWidget(run, alignment=Qt.AlignmentFlag.AlignLeft)
        diag_layout.addWidget(self.diagnostics_text)
        scroll_layout.addWidget(diag_group)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        self.tabs.addTab(tab, "数据与系统")

        self._refresh_relationship()
        self._refresh_events()
        self._refresh_data()
        self._refresh_data()

    def _on_provider_changed(self, provider_id: str) -> None:
        prov_conf = self.api.get("providers", {}).get(provider_id, {})
        self.base_url_input.setText(str(prov_conf.get("base_url", "")))
        self.model_input.setText(str(prov_conf.get("model", "")))
        self.api_key_input.setPlaceholderText(str(prov_conf.get("api_key_masked", "<empty>")))

    def _save_api_settings(self) -> None:
        api_key = self.api_key_input.text()
        self.settings_manager.save_api_settings(
            provider=self.provider_input.currentText(),
            base_url=self.base_url_input.text(),
            model=self.model_input.text(),
            api_key=api_key if api_key else None,
            local_mode=self.local_mode_input.isChecked(),
        )
        self.controller.chat_client.reload()
        self.api_key_input.clear()
        self.api_result.setText("API 设置已保存；API Key 已写入 .env 或保持原值。")
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

    def _run_diagnostics(self) -> None:
        if self.diagnostics_worker is not None and self.diagnostics_worker.isRunning():
            return
        self.diagnostics_text.setPlainText("正在后台诊断...")
        self.diagnostics_worker = _DiagnosticsWorker(self.settings_manager, self.controller)
        self.diagnostics_worker.finished_with_text.connect(self.diagnostics_text.setPlainText)
        self.diagnostics_worker.finished.connect(self.diagnostics_worker.deleteLater)
        self.diagnostics_worker.start()
