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


class SettingsWindow(QDialog):
    def __init__(self, controller: "AppController", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = SettingsManager(controller.config_manager)
        self.character_editor = CharacterPackEditor()
        self.relationship_viewer = RelationshipStateViewer()
        self.api_worker: _ApiTestWorker | None = None
        self.diagnostics_worker: _DiagnosticsWorker | None = None
        self.setWindowTitle("设置中心")
        self.resize(860, 640)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_api_tab()
        self._build_multimodal_tab()
        self._build_local_model_tab()
        self._build_pet_tab()
        self._build_actions_tab()
        self._build_character_tab()
        self._build_relationship_tab()
        self._build_events_tab()
        self._build_data_tab()
        self._build_diagnostics_tab()

        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _build_api_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
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
        layout.addLayout(form)

        buttons = QHBoxLayout()
        save = QPushButton("保存 API 设置")
        test = QPushButton("测试连接")
        save.clicked.connect(self._save_api_settings)
        test.clicked.connect(self._test_api_connection)
        buttons.addWidget(save)
        buttons.addWidget(test)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.api_result)
        layout.addStretch(1)
        self.tabs.addTab(tab, "API / 模型")

    def _build_multimodal_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
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
        
        form.addRow("TTS 语音引擎 (v0.46预留)", self.tts_combo)
        form.addRow("文生图/图生图引擎 (预留)", self.t2i_combo)
        form.addRow("视频引擎 (预留)", self.video_combo)
        
        layout.addLayout(form)
        
        hint = QLabel("提示：当前版本这些选项仅作为架构占位，修改不产生实际效果。真正的多模态能力将在 v0.46 后续版本实现。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; margin-top: 20px;")
        layout.addWidget(hint)
        
        layout.addStretch(1)
        self.tabs.addTab(tab, "多模态配置")

    def _build_local_model_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        from .provider_capability_schema import ProviderCapabilitySchema
        from .local_model_manager import LocalModelManager
        schema = ProviderCapabilitySchema(root=self.settings_manager.root)
        
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
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        self.fetch_models_btn = QPushButton("拉取模型列表")
        self.test_local_btn = QPushButton("测试服务连接")
        btn_layout.addWidget(self.fetch_models_btn)
        btn_layout.addWidget(self.test_local_btn)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)
        
        self.local_status = QLabel("状态：未测试")
        self.local_status.setWordWrap(True)
        layout.addWidget(self.local_status)
        
        self.fetch_models_btn.clicked.connect(self._fetch_local_models)
        self.test_local_btn.clicked.connect(self._test_local_service)
        
        # 许可证占位区
        license_label = QLabel("⚠️ 本地模型下载器预留入口 (v0.47)\n您必须同意并遵守对应模型 (如 Llama 3 / Gemma / Qwen) 的开源许可证和商业使用条款，才能进行下载。目前此功能仅作为 UI 占位，无法下载模型。")
        license_label.setWordWrap(True)
        license_label.setStyleSheet("color: #856404; background-color: #fff3cd; border: 1px solid #ffeeba; padding: 10px; margin-top: 15px;")
        layout.addWidget(license_label)
        
        downloader_btn = QPushButton("打开内置下载器 (不可用)")
        downloader_btn.setEnabled(False)
        layout.addWidget(downloader_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        layout.addStretch(1)
        self.tabs.addTab(tab, "本地模型")

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
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.action_status = QTextEdit()
        self.action_status.setReadOnly(True)
        self.action_combo = QComboBox()
        self.action_combo.addItems(["idle", "talk", "clicked", "drag", "sleep", "happy", "remind", "soft_idle", "close_idle", "bubble", "look_away"])
        buttons = QHBoxLayout()
        reload_btn = QPushButton("重载动作资源")
        test_btn = QPushButton("测试动作")
        reload_btn.clicked.connect(self._reload_actions)
        test_btn.clicked.connect(self._test_action)
        buttons.addWidget(self.action_combo)
        buttons.addWidget(test_btn)
        buttons.addWidget(reload_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.action_status)
        self.tabs.addTab(tab, "动作资源")
        self._refresh_action_status()

    def _build_character_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.character_status = QLabel("")
        self.character_status.setWordWrap(True)
        self.pack_file_combo = QComboBox()
        self.pack_file_combo.addItems(["character.yaml", "speech.yaml", "relationship.yaml", "events.yaml", "lore.md", "lore_index.yaml", "actions.yaml"])
        self.pack_file_combo.currentTextChanged.connect(self._load_pack_file)
        self.pack_editor_text = QTextEdit()
        buttons = QHBoxLayout()
        save = QPushButton("备份并保存 YAML")
        validate = QPushButton("重新校验")
        open_file = QPushButton("打开文件")
        save.clicked.connect(self._save_pack_file)
        validate.clicked.connect(self._refresh_character_status)
        open_file.clicked.connect(self._open_pack_file)
        buttons.addWidget(self.pack_file_combo)
        buttons.addWidget(save)
        buttons.addWidget(validate)
        buttons.addWidget(open_file)
        buttons.addStretch(1)
        layout.addWidget(self.character_status)
        layout.addLayout(buttons)
        layout.addWidget(self.pack_editor_text)
        self.tabs.addTab(tab, "角色包")
        self._refresh_character_status()
        self._load_pack_file(self.pack_file_combo.currentText())

    def _build_relationship_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.relationship_text = QTextEdit()
        self.relationship_text.setReadOnly(True)
        buttons = QHBoxLayout()
        refresh = QPushButton("刷新")
        export = QPushButton("导出关系状态")
        reset = QPushButton("备份后重置")
        refresh.clicked.connect(self._refresh_relationship)
        export.clicked.connect(self._export_relationship)
        reset.clicked.connect(self._reset_relationship)
        buttons.addWidget(refresh)
        buttons.addWidget(export)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.relationship_text)
        self.tabs.addTab(tab, "关系状态")
        self._refresh_relationship()

    def _build_events_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.events_text = QTextEdit()
        self.events_text.setReadOnly(True)
        refresh = QPushButton("刷新事件")
        refresh.clicked.connect(self._refresh_relationship)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.events_text)
        self.tabs.addTab(tab, "事件")

    def _build_data_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        buttons = QHBoxLayout()
        refresh = QPushButton("刷新数据状态")
        backup = QPushButton("导出备份")
        open_dir = QPushButton("打开数据目录")
        refresh.clicked.connect(self._refresh_data)
        backup.clicked.connect(self._backup_data)
        open_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.relationship_viewer.data_dir))))
        buttons.addWidget(refresh)
        buttons.addWidget(backup)
        buttons.addWidget(open_dir)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.data_text)
        self.tabs.addTab(tab, "数据")
        self._refresh_data()

    def _build_diagnostics_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.diagnostics_text = QTextEdit()
        self.diagnostics_text.setReadOnly(True)
        run = QPushButton("运行诊断")
        run.clicked.connect(self._run_diagnostics)
        layout.addWidget(run, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.diagnostics_text)
        self.tabs.addTab(tab, "诊断")

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
        events = status["event_log"][-20:]
        event_lines = [
            f"- {e.get('timestamp','')} event={e.get('event_id')} source={e.get('source')} effect={e.get('relationship_effect')} lore={e.get('lore_fragments_used')} {e.get('stage_before')}->{e.get('stage_after')}"
            for e in events
            if isinstance(e, dict)
        ]
        self.relationship_text.setPlainText("\n".join(state_lines) or "relationship_state.json 不可读或为空。")
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
