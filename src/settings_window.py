from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import QThread, QTimer, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
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


SIMPLE_SETTINGS_TABS = {
    "模型与引擎",
    "桌宠",
    "角色与资源",
    "关系与事件",
    "养成",
    "提醒",
    "隐私与安全",
}


def normalize_settings_mode(value: Any) -> str:
    return "advanced" if str(value or "").strip().lower() == "advanced" else "simple"


class _ApiTestWorker(QThread):
    finished_with_result = Signal(bool, str)

    def __init__(
        self,
        settings_manager: SettingsManager,
        profile: dict[str, Any] | None = None,
        api_key_override: str | None = None,
    ) -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.profile = profile
        self.api_key_override = api_key_override

    def run(self) -> None:
        if self.profile is None:
            ok, message = self.settings_manager.test_api_connection()
        else:
            from .chat_client import mask_key
            from .llm.provider_manager import ProviderManager

            pm = ProviderManager(api_config=self.settings_manager.load_api_config())
            pm.model_profiles_path = self.settings_manager.model_profiles_path
            pm.env_path = self.settings_manager.env_path
            ok, message = pm.test_profile_model(
                self.profile,
                api_key_override=self.api_key_override,
            )
            provider = str(self.profile.get("provider", ""))
            env_key_name = str(self.profile.get("api_key_env", ""))
            raw_key = self.api_key_override or self.settings_manager.current_api_key(env_key_name)
            if provider not in (Provider.OLLAMA,) and raw_key:
                message += f" (key={mask_key(raw_key)})"
        self.finished_with_result.emit(ok, message)


class _DiagnosticsWorker(QThread):
    finished_with_text = Signal(str)

    def __init__(self, settings_manager: SettingsManager, controller: "AppController") -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.controller = controller

    def run(self) -> None:
        chat_client = getattr(self.controller, "chat_client", None)
        results = run_diagnostics(self.settings_manager, getattr(self.controller, "asset_manager", None), chat_client=chat_client)
        text = format_diagnostics(results)
        startup_timer = getattr(self.controller, "startup_timer", None)
        if startup_timer is not None:
            text += "\n\n" + startup_timer.format_summary()
        self.finished_with_text.emit(text)


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


_RELATIONSHIP_LABELS = {
    "character_id": "角色",
    "relationship_stage": "关系阶段",
    "week": "当前周目",
    "weekly_action_points": "本周行动点",
    "max_weekly_action_points": "行动点上限",
    "affection": "好感",
    "familiarity": "熟悉",
    "trust": "信任",
    "dependency": "依赖",
    "heartbeat": "心跳",
    "jealousy": "吃醋",
    "boundary": "边界感",
    "empathy_load": "共情负荷",
    "softness_leak": "软化泄露",
    "defense_level": "防御强度",
    "stay_tendency": "留下倾向",
    "last_update_reason": "最近变化",
}

_RELATIONSHIP_ORDER = [
    "character_id",
    "relationship_stage",
    "week",
    "weekly_action_points",
    "max_weekly_action_points",
    "affection",
    "familiarity",
    "trust",
    "dependency",
    "heartbeat",
    "jealousy",
    "boundary",
    "empathy_load",
    "softness_leak",
    "defense_level",
    "stay_tendency",
    "last_update_reason",
]

_EVENT_LABELS = {
    "user_drag": "拖拽互动",
    "user_click": "点击互动",
    "idle_chat": "空闲对话",
    "user_message": "主动对话",
    "birthday": "生日事件",
    "reminder": "提醒事件",
    "local": "本地记录",
}

_DATA_FILE_LABELS = {
    "relationship_state": "关系状态",
    "event_log": "事件日志",
    "user_memory": "用户记忆",
}

_PACK_FILE_DESCRIPTIONS = {
    "character.yaml": "角色身份、核心人格、能力、禁用行为。",
    "speech.yaml": "说话方式、特殊回应、语言过滤规则。",
    "relationship.yaml": "关系阶段、数值字段、升级条件。",
    "events.yaml": "点击、拖拽、回归、生日等事件规则。",
    "lore.md": "完整剧情与人格背景正文，只按需检索。",
    "lore_index.yaml": "剧情标签、触发词、剧透等级和检索规则。",
    "actions.yaml": "动作状态到素材的映射。",
    "prompt_pack.md": "说话方式参考和角色片段。",
    "story.yaml": "剧情阅读章节，属于角色包内容。",
}


def _api_key_placeholder(masked_key: str | None) -> str:
    if masked_key and masked_key != "<empty>":
        return "输入新的 API Key；留空则继续使用已保存 Key"
    return "输入 API Key；保存后会写入本地 .env"


def _saved_api_key_status(masked_key: str | None) -> str:
    if masked_key and masked_key != "<empty>":
        return f"已保存 Key：{masked_key}（这里只显示脱敏值）"
    return "未保存 Key；输入后点击「保存 API 设置」"


def _format_relationship_summary(state: dict[str, Any]) -> str:
    if not state:
        return "关系状态不可读或为空。"
    lines = []
    for key in _RELATIONSHIP_ORDER:
        if key in state:
            lines.append(f"{_RELATIONSHIP_LABELS[key]}：{state[key]}")
    hidden = [key for key in state if key not in _RELATIONSHIP_ORDER]
    if hidden:
        lines.append(f"其他内部字段：{len(hidden)} 项，可导出关系状态查看原始 JSON。")
    return "\n".join(lines)


def _format_relationship_effect(effect: Any) -> str:
    if not isinstance(effect, dict) or not effect:
        return "关系无明显变化"
    parts = []
    for key, value in effect.items():
        label = _RELATIONSHIP_LABELS.get(key, key)
        if isinstance(value, (int, float)):
            parts.append(f"{label} {value:+g}")
        else:
            parts.append(f"{label}: {value}")
    return "，".join(parts)


def _format_event_log_summary(events: list[Any]) -> str:
    valid_events = [event for event in events if isinstance(event, dict)]
    if not valid_events:
        return "暂无事件记录。"
    lines = []
    for event in valid_events[-20:]:
        event_id = event.get("event_id")
        source = event.get("source")
        if not event_id or event_id == "None":
            event_name = _EVENT_LABELS.get(str(source), "普通记录")
        else:
            event_name = _EVENT_LABELS.get(str(event_id), str(event_id))
        timestamp = str(event.get("timestamp") or "未知时间")
        effect = _format_relationship_effect(event.get("relationship_effect"))
        stage_before = event.get("stage_before")
        stage_after = event.get("stage_after")
        stage_text = ""
        if stage_before and stage_after and stage_before != stage_after:
            stage_text = f"；阶段 {stage_before} → {stage_after}"
        lore_used = event.get("lore_fragments_used")
        lore_text = ""
        if isinstance(lore_used, list) and lore_used:
            lore_text = f"；调用剧情片段 {len(lore_used)} 个"
        lines.append(f"{timestamp}｜{event_name}｜{effect}{stage_text}{lore_text}")
    return "\n".join(lines)


def _format_user_memory_summary(profile: dict[str, str], memory: dict[str, Any], notes: list[str]) -> str:
    lines = [
        "用户档案",
        f"- 称呼：{profile.get('user_name', '你')}",
        f"- 生日（月日）：{profile.get('birthday') or '未填写'}",
        f"- 关系：{profile.get('relationship', '陪伴角色与用户')}",
        f"- 偏好风格：{profile.get('style', '')}",
        "",
        "自动记忆",
    ]
    preferences = memory.get("user_preferences")
    if isinstance(preferences, dict) and preferences:
        for key, value in sorted(preferences.items()):
            lines.append(f"- 偏好 {key}: {value}")
    phrases = memory.get("important_user_phrases")
    if isinstance(phrases, list) and phrases:
        lines.append("- 重要表达：" + "、".join(str(item) for item in phrases[-10:]))
    unlocked_lore = memory.get("unlocked_lore")
    if isinstance(unlocked_lore, list) and unlocked_lore:
        lines.append("- 已解锁剧情：" + "、".join(str(item) for item in unlocked_lore[-10:]))
    last_events = memory.get("last_events")
    if isinstance(last_events, list) and last_events:
        lines.append("- 最近事件：" + "、".join(str(item) for item in last_events[-10:]))
    if len(lines) == 6:
        lines.append("- 暂无自动记忆。")
    lines.extend(["", "手动备忘"])
    if notes:
        lines.extend(f"- {note}" for note in notes[-12:])
    else:
        lines.append("- 暂无手动备忘。")
    return "\n".join(lines)


def _read_recent_text_lines(path: Path, limit: int) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    cleaned = [line.strip() for line in lines if line.strip()]
    return cleaned[-limit:]


def _format_data_status_summary(status: dict[str, Any], paths: dict[str, Path]) -> str:
    lines = [f"数据目录：{'可用' if status.get('exists') else '尚未创建'}"]
    for key, path in paths.items():
        exists = path.exists()
        readable = status.get(key + "_readable")
        error = status.get(key + "_error")
        label = _DATA_FILE_LABELS.get(key, key)
        if error:
            state = f"异常（{error}）"
        elif exists and readable:
            state = "可读"
        elif exists:
            state = "存在但不可读"
        else:
            state = "暂无记录，运行后会自动生成"
        lines.append(f"{label}：{state}")
    lines.append("需要排查时可点「导出备份」或展开原始详情。")
    return "\n".join(lines)


def _format_pack_file_summary(name: str, text: str, editable: bool) -> str:
    description = _PACK_FILE_DESCRIPTIONS.get(name, "角色包文件。")
    lines = [
        f"当前文件：{name}",
        f"用途：{description}",
        f"权限：{'可在此编辑，保存前会自动备份并校验' if editable else '只读；如需修改请先确认角色包规则'}",
        f"内容规模：{len(text.splitlines())} 行，约 {len(text)} 字。",
    ]
    if name.endswith((".yaml", ".yml")):
        keys = []
        for line in text.splitlines():
            stripped = line.strip()
            if line and not line.startswith((" ", "-")) and ":" in stripped:
                keys.append(stripped.split(":", 1)[0])
            if len(keys) >= 8:
                break
        if keys:
            lines.append("主要段落：" + "、".join(keys))
    if name == "story.yaml":
        count = sum(1 for line in text.splitlines() if line.strip().startswith("- id:"))
        lines.append(f"剧情章节：{count} 章。")
    return "\n".join(lines)


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
        self.relationship_viewer = RelationshipStateViewer(character_id=char_id)
        self.api_worker: _ApiTestWorker | None = None
        self.diagnostics_worker: _DiagnosticsWorker | None = None
        self.ollama_worker: _OllamaPullWorker | None = None
        self.ollama_health_worker: _OllamaHealthWorker | None = None
        self._lazy_tab_loaders: dict[int, Callable[[], None]] = {}
        self.setWindowTitle("设置中心")
        self.resize(860, 640)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )

        layout = QVBoxLayout(self)
        self._build_settings_mode_switch(layout)
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        layout.addWidget(self.tabs)

        self._build_model_tab()
        self._build_pet_tab()
        self._build_character_resources_tab()
        self._build_relationship_events_tab()
        self._build_growth_tab()
        self._build_system_tab()
        self._build_reminder_tab()
        self._build_file_organizer_tab()
        self._build_system_status_tab()
        self._build_clipboard_tab()
        self._build_focus_tab()
        self._build_privacy_tab()
        self._build_diagnostics_tab()
        self.tabs.currentChanged.connect(self._load_lazy_tab)
        self._apply_settings_mode(self._settings_mode, persist=False)

        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _build_settings_mode_switch(self, layout: QVBoxLayout) -> None:
        config = self.settings_manager.load_app_config()
        self._settings_mode = normalize_settings_mode(config.get("settings_mode", "simple"))
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.addWidget(QLabel("设置显示"))
        self.simple_mode_button = QPushButton("简单")
        self.advanced_mode_button = QPushButton("进阶")
        for button in (self.simple_mode_button, self.advanced_mode_button):
            button.setCheckable(True)
            button.setMinimumWidth(72)
        self.settings_mode_group = QButtonGroup(self)
        self.settings_mode_group.setExclusive(True)
        self.settings_mode_group.addButton(self.simple_mode_button)
        self.settings_mode_group.addButton(self.advanced_mode_button)
        self.simple_mode_button.clicked.connect(lambda: self._apply_settings_mode("simple"))
        self.advanced_mode_button.clicked.connect(lambda: self._apply_settings_mode("advanced"))
        bar_layout.addWidget(self.simple_mode_button)
        bar_layout.addWidget(self.advanced_mode_button)
        bar_layout.addStretch(1)
        layout.addWidget(bar)
        self.settings_mode_hint = QLabel()
        self.settings_mode_hint.setWordWrap(True)
        layout.addWidget(self.settings_mode_hint)

    def _apply_settings_mode(self, mode: str, persist: bool = True) -> None:
        mode = normalize_settings_mode(mode)
        self._settings_mode = mode
        advanced = mode == "advanced"
        self.simple_mode_button.setChecked(not advanced)
        self.advanced_mode_button.setChecked(advanced)

        for index in range(self.tabs.count()):
            visible = advanced or self.tabs.tabText(index) in SIMPLE_SETTINGS_TABS
            self.tabs.setTabVisible(index, visible)

        for name in (
            "profile_switch_group",
            "local_model_group",
            "tts_group",
            "image_group",
            "video_group",
            "multimodal_hint",
            "actions_group",
            "pack_group",
            "relationship_group",
            "events_group",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(advanced)

        current = self.tabs.currentIndex()
        if current < 0 or not self.tabs.isTabVisible(current):
            for index in range(self.tabs.count()):
                if self.tabs.isTabVisible(index):
                    self.tabs.setCurrentIndex(index)
                    break

        self.settings_mode_hint.setText(
            "简单模式只显示常用入口；进阶模式显示本地模型、诊断、日志和高风险功能。切换不会删除或重置已有设置。"
            if not advanced
            else "进阶模式显示全部配置。文件整理、系统状态和剪贴板等高风险功能仍保持各自的关闭默认值。"
        )
        if persist:
            config = self.settings_manager.load_app_config()
            config["settings_mode"] = mode
            self.settings_manager.save_app_config(config)
            self.controller.app_config.update(config)

    def _register_lazy_tab(self, index: int, loader: Callable[[], None]) -> None:
        self._lazy_tab_loaders[index] = loader

    def _load_lazy_tab(self, index: int) -> None:
        loader = self._lazy_tab_loaders.pop(index, None)
        if loader is not None:
            QTimer.singleShot(0, loader)

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
        mm_config = self.settings_manager.load_multimodal_config()
        tts_value = str(mm_config.get("tts", "none"))
        self.voice_status_label = QLabel(
            "语音状态：未启用；主线仅保留配置接口。"
            if tts_value == "none"
            else f"语音状态：已保存 {tts_value} 配置；本阶段不新增语音执行能力。"
        )
        self.voice_status_label.setWordWrap(True)
        scroll_layout.addWidget(self.voice_status_label)
        self._build_profile_switcher(scroll_layout)

        # 云端 API 配置
        api_group = QGroupBox("云端 API 配置 (Cloud Service)")
        api_group_layout = QVBoxLayout(api_group)
        self._build_api_section(api_group_layout)
        scroll_layout.addWidget(api_group)

        # 本地部署与引擎配置
        self.local_model_group = QGroupBox("本地部署与引擎配置 (Local Service)")
        local_group_layout = QVBoxLayout(self.local_model_group)
        self._build_local_model_section(local_group_layout)
        scroll_layout.addWidget(self.local_model_group)

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
        self.auth_header_input = QComboBox()
        self.auth_header_input.addItems(["bearer", "api-key", "x-api-key", "none"])
        self.auth_header_input.setCurrentText(str(prov_conf.get("auth_header") or ProviderMeta.get_auth_header(active)))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.saved_api_key_label = QLabel()
        self.saved_api_key_label.setWordWrap(True)

        # 小眼睛切换明文/密码
        self.api_key_toggle_btn = QPushButton("显")
        self.api_key_toggle_btn.setFixedWidth(32)
        self.api_key_toggle_btn.setCheckable(True)
        self.api_key_toggle_btn.toggled.connect(self._toggle_api_key_visibility)
        key_widget = QWidget()
        key_col = QVBoxLayout(key_widget)
        key_col.setContentsMargins(0, 0, 0, 0)
        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.addWidget(self.api_key_input)
        key_row.addWidget(self.api_key_toggle_btn)
        key_col.addLayout(key_row)
        key_col.addWidget(self.saved_api_key_label)
        self._update_saved_api_key_label(active, prov_conf)

        self.local_mode_input = QCheckBox("启用本地 fallback 模式")
        self.local_mode_input.setChecked(bool(self.api.get("local_mode", False)))
        self.api_result = QLabel("选择 Provider → 输入新 Key 或留空沿用旧 Key → 测试连接 → 保存后点击「设为当前模型」生效。")
        self.api_result.setWordWrap(True)

        self.provider_input.currentTextChanged.connect(self._on_provider_changed)

        form.addRow("Provider", self.provider_input)
        form.addRow("Base URL", self.base_url_input)
        form.addRow("Model", self.model_input)
        form.addRow("Auth Header", self.auth_header_input)
        form.addRow("API Key", key_widget)
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
        self.tts_group = QGroupBox("TTS 语音播报")
        tts_layout = QFormLayout(self.tts_group)
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
        parent_layout.addWidget(self.tts_group)

        # ── 图像生成 ──
        self.image_group = QGroupBox("文生图 / 图生图")
        img_layout = QFormLayout(self.image_group)
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
        parent_layout.addWidget(self.image_group)

        # ── 视频生成 ──
        self.video_group = QGroupBox("视频生成")
        vid_layout = QFormLayout(self.video_group)
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
        parent_layout.addWidget(self.video_group)

        self.multimodal_hint = QLabel("多模态功能需要对应服务运行中。留空或选 none 则不启用。")
        self.multimodal_hint.setWordWrap(True)
        self.multimodal_hint.setStyleSheet("color: gray; margin-top: 8px;")
        parent_layout.addWidget(self.multimodal_hint)
        parent_layout.addStretch(1)

    def _build_profile_switcher(self, parent_layout: Any) -> None:
        self.profile_switch_group = QGroupBox("文本模型切换")
        layout = QVBoxLayout(self.profile_switch_group)
        row = QHBoxLayout()
        self.profile_switch_combo = QComboBox()
        self.profile_switch_combo.setMinimumWidth(360)
        self.profile_switch_btn = QPushButton("直接切换"); self.profile_switch_btn.setIcon(get_icon("chip"))
        self.profile_enable_btn = QPushButton("启用"); self.profile_enable_btn.setIcon(get_icon("save"))
        self.profile_disable_btn = QPushButton("停用"); self.profile_disable_btn.setIcon(get_icon("settings"))
        row.addWidget(self.profile_switch_combo, 1)
        row.addWidget(self.profile_switch_btn)
        row.addWidget(self.profile_enable_btn)
        row.addWidget(self.profile_disable_btn)
        layout.addLayout(row)

        self.profile_switch_status = QLabel("历史与已保存模型可在这里直接切换。")
        self.profile_switch_status.setWordWrap(True)
        layout.addWidget(self.profile_switch_status)

        self.profile_switch_btn.clicked.connect(self._switch_selected_text_profile)
        self.profile_enable_btn.clicked.connect(lambda: self._set_selected_text_profile_enabled(True))
        self.profile_disable_btn.clicked.connect(lambda: self._set_selected_text_profile_enabled(False))
        parent_layout.addWidget(self.profile_switch_group)
        self._refresh_profile_switcher()

    def _refresh_profile_switcher(self) -> None:
        combo = getattr(self, "profile_switch_combo", None)
        if combo is None:
            return
        current_data = combo.currentData()
        combo.blockSignals(True)
        combo.clear()

        profiles_data = self.settings_manager.load_model_profiles()
        active_id = profiles_data.get("active_text_profile_id", "")
        profiles = [p for p in profiles_data.get("profiles", []) if _profile_has_text(p)]
        by_id = {str(p.get("id", "")): p for p in profiles if p.get("id")}
        history = profiles_data.get("profile_history", {}).get("text", [])
        ordered_ids: list[str] = []
        for profile_id in [active_id] + [str(item) for item in history] + [str(p.get("id", "")) for p in profiles]:
            if profile_id and profile_id in by_id and profile_id not in ordered_ids:
                ordered_ids.append(profile_id)

        for profile_id in ordered_ids:
            profile = by_id[profile_id]
            marker = "当前" if profile_id == active_id else ("停用" if profile.get("enabled", True) is False else "可用")
            source = "本地" if profile.get("source") == "local" else "云端"
            name = str(profile.get("name") or profile_id)
            model = str(profile.get("model") or "")
            combo.addItem(f"[{marker}] {source} · {name} · {model}", profile_id)

        if current_data:
            index = combo.findData(current_data)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _switch_selected_text_profile(self) -> None:
        profile_id = self.profile_switch_combo.currentData()
        if not profile_id:
            self.profile_switch_status.setText("状态：没有可切换的文本模型。")
            self.profile_switch_status.setStyleSheet("color: red;")
            return
        self._do_switch_profile(str(profile_id), str(profile_id), self.profile_switch_status)

    def _set_selected_text_profile_enabled(self, enabled: bool) -> None:
        profile_id = self.profile_switch_combo.currentData()
        if not profile_id:
            self.profile_switch_status.setText("状态：没有选中的文本模型。")
            self.profile_switch_status.setStyleSheet("color: red;")
            return
        ok, msg = self.settings_manager.set_profile_enabled(str(profile_id), enabled, slot="text")
        self._refresh_active_status()
        self._refresh_profile_switcher()
        self.profile_switch_status.setText(f"状态：{msg}")
        self.profile_switch_status.setStyleSheet("color: green;" if ok else "color: red;")

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

    def _save_local_model_settings(self) -> str | None:
        service = self.local_service_combo.currentText()
        url = self.local_base_url.text().strip()
        model = self.local_model_list.currentText().strip()

        if not url or not model:
            self.local_status.setText("状态：请填写 Base URL 和模型名称")
            self.local_status.setStyleSheet("color: red;")
            return

        provider = ProviderMeta.service_label_to_key(service)

        self.settings_manager.save_local_model_profile(
            provider=provider,
            base_url=url,
            model=model,
            service_label=service,
        )
        target_id = ProviderMeta.make_profile_id(provider, model)
        self.local_status.setText(f"状态：已保存 {provider} → {model}；点击「设为当前模型」后才会验证并生效。")
        self.local_status.setStyleSheet("color: green;")
        self._refresh_active_status()
        self._refresh_profile_switcher()
        return target_id

    def _refresh_active_status(self) -> None:
        """刷新顶部文本模型状态标签。"""
        api_config = self.settings_manager.load_api_config()
        local_mode = bool(api_config.get("local_mode", False))
        profiles_data = self.settings_manager.load_model_profiles()
        active_id = profiles_data.get("active_text_profile_id", "")
        profiles = profiles_data.get("profiles", [])
        active_profile = next((p for p in profiles if p.get("id") == active_id), None)

        if not active_profile:
            self.active_profile_status.setText("当前文本模型：无；云端未连接。")
            self.active_profile_status.setStyleSheet(
                "background: #f8d7da; border: 1px solid #f5c6cb; padding: 8px; margin-bottom: 10px; color: #721c24;"
            )
            return

        name = active_profile.get("name", active_id)
        model = active_profile.get("model", "")
        source = active_profile.get("source", "cloud")
        source_label = "本地" if source == "local" else "云端"

        if local_mode:
            text = (
                f"当前文本模型：{name} ({model}) [{source_label}]；"
                "本地 fallback 模式已开启，云端 Provider 当前不会实际调用。"
            )
            self.active_profile_status.setText(text)
            self.active_profile_status.setStyleSheet(
                "background: #fff3cd; border: 1px solid #ffeeba; padding: 8px; margin-bottom: 10px; color: #856404;"
            )
            return

        text = f"当前文本模型：{name} ({model}) [{source_label}]；上次切换通过，实时连通性请看下方「测试连接」。"
        self.active_profile_status.setText(text)
        self.active_profile_status.setStyleSheet(
            "background: #e7f1ff; border: 1px solid #b6d4fe; padding: 8px; margin-bottom: 10px; color: #084298;"
        )

    def _activate_cloud_profile(self) -> None:
        """保存云端 API 设置并切换为当前生效模型。"""
        target_id = self._save_api_settings(notify=False, reload_client=False)
        provider = self._current_provider_key()
        self._do_switch_profile(target_id, f"云端 {provider}", self.api_result)

    def _activate_local_profile(self) -> None:
        """保存本地模型设置并切换为当前生效模型。"""
        target_id = self._save_local_model_settings()
        if not target_id:
            return

        service = self.local_service_combo.currentText()
        model = self.local_model_list.currentText().strip()

        self._do_switch_profile(target_id, f"本地 {service} → {model}", self.local_status)

    def _do_switch_profile(self, target_id: str, label: str, status_label: QLabel | None = None) -> bool:
        """执行模型切换，失败时回退。"""
        target_status = status_label or self.local_status
        ok, msg = self.settings_manager.activate_text_profile(target_id)

        if ok:
            self._refresh_active_status()
            self._refresh_profile_switcher()
            self.local_mode_input.setChecked(False)
            self.controller.chat_client.reload()
            target_status.setText(f"状态：已切换至 {label}  ✓ 已生效")
            target_status.setStyleSheet("color: green;")
            return True
        else:
            self._refresh_active_status()
            self._refresh_profile_switcher()
            target_status.setText(f"状态：切换失败 ({msg}) — 当前生效模型未改变")
            target_status.setStyleSheet("color: red;")
            return False

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
        self.show_input = QCheckBox("显示输入框")
        self.show_input.setChecked(bool(window.get("show_input", True)))
        self.always_on_top = QCheckBox("保持置顶")
        self.always_on_top.setChecked(bool(window.get("always_on_top", True)))
        self.opacity = QSpinBox()
        self.opacity.setRange(30, 100)
        self.opacity.setSuffix("%")
        self.opacity.setValue(int(window.get("opacity_percent", 100)))
        self.idle_chat = QCheckBox("启用闲聊")
        self.idle_chat.setChecked(bool(app_config.get("idle_chat_enabled", False)))
        self.idle_minutes = QSpinBox()
        self.idle_minutes.setRange(1, 240)
        self.idle_minutes.setValue(int(app_config.get("idle_chat_minutes", 10)))
        self.idle_behavior = QCheckBox("启用空闲小动作")
        self.idle_behavior.setChecked(bool(app_config.get("idle_behavior_enabled", False)))
        self.idle_behavior_seconds = QSpinBox()
        self.idle_behavior_seconds.setRange(600, 3600)
        self.idle_behavior_seconds.setSuffix(" 秒")
        self.idle_behavior_seconds.setValue(int(app_config.get("idle_behavior_seconds", 600)))
        self.hourly_chime = QCheckBox("整点报时")
        self.hourly_chime.setChecked(bool(app_config.get("hourly_chime_enabled", False)))
        self.edge_peek = QCheckBox("左右边缘趴墙")
        self.edge_peek.setToolTip("开启后，把达妮娅拖到屏幕左右边缘时会半隐藏趴在边上；默认关闭，避免首次运行时自己动。")
        self.edge_peek.setChecked(bool(pet.get("edge_peek_enabled", False)))
        self.day_night = QCheckBox("昼夜作息")
        self.day_night.setChecked(bool(app_config.get("day_night_enabled", True)))

        form.addRow("桌宠大小", self.pet_size)
        form.addRow("输入框", self.show_input)
        form.addRow("置顶", self.always_on_top)
        form.addRow("透明度", self.opacity)
        form.addRow("闲聊", self.idle_chat)
        form.addRow("闲聊间隔", self.idle_minutes)
        form.addRow("空闲小动作", self.idle_behavior)
        form.addRow("小动作等待", self.idle_behavior_seconds)
        form.addRow("整点报时", self.hourly_chime)
        form.addRow("趴墙", self.edge_peek)
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
        self.actions_group = QGroupBox("动作资源")
        actions_layout = QVBoxLayout(self.actions_group)
        self.action_status = QTextEdit()
        self.action_status.setReadOnly(True)
        self.action_combo = QComboBox()
        self.action_combo.addItems(["idle", "talk", "clicked", "drag", "sleep", "happy", "remind", "soft_idle", "close_idle", "bubble", "look_away"])
        btn_row = QHBoxLayout()
        reload_btn = QPushButton("重载动作资源"); reload_btn.setIcon(get_icon("refresh"))
        test_btn = QPushButton("测试动作"); test_btn.setIcon(get_icon("chip"))
        self.action_details_btn = QPushButton("显示原始详情")
        self.action_details_btn.setIcon(get_icon("info"))
        reload_btn.clicked.connect(self._reload_actions)
        test_btn.clicked.connect(self._test_action)
        self.action_details_btn.clicked.connect(self._toggle_action_details)
        btn_row.addWidget(self.action_combo)
        btn_row.addWidget(test_btn)
        btn_row.addWidget(reload_btn)
        btn_row.addWidget(self.action_details_btn)
        btn_row.addStretch(1)
        self.action_raw_details = QTextEdit()
        self.action_raw_details.setReadOnly(True)
        self.action_raw_details.setVisible(False)
        self.action_raw_details.setMaximumHeight(160)
        actions_layout.addLayout(btn_row)
        actions_layout.addWidget(self.action_status)
        actions_layout.addWidget(self.action_raw_details)
        layout.addWidget(self.actions_group)

        # 下半部分：角色包编辑器
        self.pack_group = QGroupBox("角色包编辑器")
        pack_layout = QVBoxLayout(self.pack_group)
        self.character_status = QLabel("")
        self.character_status.setWordWrap(True)
        self.pack_file_combo = QComboBox()
        self.pack_file_combo.addItems(["character.yaml", "speech.yaml", "relationship.yaml", "events.yaml", "lore.md", "lore_index.yaml", "actions.yaml", "story.yaml"])
        self.pack_file_combo.currentTextChanged.connect(self._load_pack_file)
        self.pack_summary_text = QTextEdit()
        self.pack_summary_text.setReadOnly(True)
        self.pack_summary_text.setMaximumHeight(120)
        self.pack_editor_text = QTextEdit()
        self.pack_editor_text.setVisible(False)
        pack_btn_row = QHBoxLayout()
        save = QPushButton("备份并保存 YAML"); save.setIcon(get_icon("save"))
        validate = QPushButton("重新校验"); validate.setIcon(get_icon("info"))
        open_file = QPushButton("打开文件"); open_file.setIcon(get_icon("document"))
        self.pack_raw_toggle_btn = QPushButton("显示原始文件")
        self.pack_raw_toggle_btn.setIcon(get_icon("info"))
        save.clicked.connect(self._save_pack_file)
        validate.clicked.connect(self._refresh_character_status)
        open_file.clicked.connect(self._open_pack_file)
        self.pack_raw_toggle_btn.clicked.connect(self._toggle_pack_raw_file)
        pack_btn_row.addWidget(self.pack_file_combo)
        pack_btn_row.addWidget(save)
        pack_btn_row.addWidget(validate)
        pack_btn_row.addWidget(open_file)
        pack_btn_row.addWidget(self.pack_raw_toggle_btn)
        pack_btn_row.addStretch(1)
        pack_layout.addWidget(self.character_status)
        pack_layout.addLayout(pack_btn_row)
        pack_layout.addWidget(self.pack_summary_text)
        pack_layout.addWidget(self.pack_editor_text)
        layout.addWidget(self.pack_group)

        self.tabs.addTab(tab, get_icon("document"), "角色与资源")
        self._refresh_action_status()
        self._refresh_character_status()
        self._load_pack_file(self.pack_file_combo.currentText())
        self._refresh_character_list()
        self._refresh_char_info()

    def _refresh_character_list(self) -> None:
        self.char_selector.clear()
        from core.character_loader import discover_character_ids
        self.char_selector.addItems(discover_character_ids())
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

        profile = self.controller.profile_manager.load()
        profile_group = QGroupBox("用户档案")
        profile_layout = QFormLayout(profile_group)
        self.profile_user_name = QLineEdit(profile.get("user_name", "你"))
        self.profile_birthday = QLineEdit(profile.get("birthday", ""))
        self.profile_birthday.setPlaceholderText("月-日，例如 03-14")
        self.profile_birthday.setMaxLength(5)
        self.profile_relationship = QLineEdit(profile.get("relationship", "陪伴角色与用户"))
        self.profile_style = QLineEdit(profile.get("style", ""))
        profile_layout.addRow("用户称呼", self.profile_user_name)
        profile_layout.addRow("生日（月-日，可留空）", self.profile_birthday)
        profile_layout.addRow("关系设定", self.profile_relationship)
        profile_layout.addRow("期望风格", self.profile_style)
        profile_hint = QLabel("生日只保存月和日，不读取系统账户资料；档案和记忆保存在本地运行态目录。")
        profile_hint.setWordWrap(True)
        profile_layout.addRow("", profile_hint)
        profile_save = QPushButton("保存用户档案")
        profile_save.setIcon(get_icon("save"))
        profile_save.clicked.connect(self._save_profile_settings)
        self.profile_status = QLabel()
        self.profile_status.setWordWrap(True)
        profile_layout.addRow("", profile_save)
        profile_layout.addRow("", self.profile_status)
        layout.addWidget(profile_group)

        self.relationship_group = QGroupBox("关系状态")
        rel_layout = QVBoxLayout(self.relationship_group)
        self.relationship_text = QTextEdit()
        self.relationship_text.setReadOnly(True)
        rel_buttons = QHBoxLayout()
        refresh = QPushButton("刷新"); refresh.setIcon(get_icon("refresh"))
        export = QPushButton("导出关系状态"); export.setIcon(get_icon("upload"))
        reset = QPushButton("备份后重置"); reset.setIcon(get_icon("protect"))
        self.relationship_raw_toggle_btn = QPushButton("显示原始数据")
        self.relationship_raw_toggle_btn.setIcon(get_icon("info"))
        refresh.clicked.connect(self._refresh_relationship)
        export.clicked.connect(self._export_relationship)
        reset.clicked.connect(self._reset_relationship)
        self.relationship_raw_toggle_btn.clicked.connect(self._toggle_relationship_raw)
        rel_buttons.addWidget(refresh)
        rel_buttons.addWidget(export)
        rel_buttons.addWidget(reset)
        rel_buttons.addWidget(self.relationship_raw_toggle_btn)
        rel_buttons.addStretch(1)
        self.relationship_raw_text = QTextEdit()
        self.relationship_raw_text.setReadOnly(True)
        self.relationship_raw_text.setVisible(False)
        self.relationship_raw_text.setMaximumHeight(160)
        rel_layout.addLayout(rel_buttons)
        rel_layout.addWidget(self.relationship_text)
        rel_layout.addWidget(self.relationship_raw_text)
        layout.addWidget(self.relationship_group)

        memory_group = QGroupBox("记忆备忘录")
        memory_layout = QVBoxLayout(memory_group)
        self.memory_text = QTextEdit()
        self.memory_text.setReadOnly(True)
        memory_buttons = QHBoxLayout()
        memory_refresh = QPushButton("刷新记忆"); memory_refresh.setIcon(get_icon("refresh"))
        memory_refresh.clicked.connect(self._refresh_memory)
        self.memory_note_input = QLineEdit()
        self.memory_note_input.setPlaceholderText("写一条希望达妮娅记住的事")
        memory_add = QPushButton("记住这条"); memory_add.setIcon(get_icon("save"))
        memory_add.clicked.connect(self._add_memory_note)
        memory_clear = QPushButton("清空记忆"); memory_clear.setIcon(get_icon("settings"))
        memory_clear.clicked.connect(self._clear_memory)
        memory_buttons.addWidget(memory_refresh)
        memory_buttons.addWidget(self.memory_note_input, 1)
        memory_buttons.addWidget(memory_add)
        memory_buttons.addWidget(memory_clear)
        memory_layout.addLayout(memory_buttons)
        memory_layout.addWidget(self.memory_text)
        layout.addWidget(memory_group)

        self.events_group = QGroupBox("事件日志")
        evt_layout = QVBoxLayout(self.events_group)
        self.events_text = QTextEdit()
        self.events_text.setReadOnly(True)
        evt_buttons = QHBoxLayout()
        evt_refresh = QPushButton("刷新事件"); evt_refresh.setIcon(get_icon("refresh"))
        self.events_raw_toggle_btn = QPushButton("显示原始日志")
        self.events_raw_toggle_btn.setIcon(get_icon("info"))
        evt_refresh.clicked.connect(self._refresh_events)
        self.events_raw_toggle_btn.clicked.connect(self._toggle_events_raw)
        evt_buttons.addWidget(evt_refresh)
        evt_buttons.addWidget(self.events_raw_toggle_btn)
        evt_buttons.addStretch(1)
        self.events_raw_text = QTextEdit()
        self.events_raw_text.setReadOnly(True)
        self.events_raw_text.setVisible(False)
        self.events_raw_text.setMaximumHeight(180)
        evt_layout.addLayout(evt_buttons)
        evt_layout.addWidget(self.events_text)
        evt_layout.addWidget(self.events_raw_text)
        layout.addWidget(self.events_group)

        self.relationship_text.setPlainText("打开本页后加载关系状态。")
        self.memory_text.setPlainText("打开本页后加载记忆备忘录。")
        self.events_text.setPlainText("打开本页后加载最近事件。")
        index = self.tabs.addTab(tab, get_icon("download"), "关系与事件")
        self._register_lazy_tab(index, self._refresh_relationship_bundle)

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
        self.data_raw_toggle_btn = QPushButton("显示原始详情")
        self.data_raw_toggle_btn.setIcon(get_icon("info"))
        refresh_data.clicked.connect(self._refresh_data)
        backup.clicked.connect(self._backup_data)
        open_dir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.relationship_viewer.data_dir))))
        self.data_raw_toggle_btn.clicked.connect(self._toggle_data_raw)
        data_buttons.addWidget(refresh_data)
        data_buttons.addWidget(backup)
        data_buttons.addWidget(open_dir)
        data_buttons.addWidget(self.data_raw_toggle_btn)
        data_buttons.addStretch(1)
        self.data_raw_text = QTextEdit()
        self.data_raw_text.setReadOnly(True)
        self.data_raw_text.setVisible(False)
        self.data_raw_text.setMaximumHeight(160)
        data_layout.addLayout(data_buttons)
        data_layout.addWidget(self.data_text)
        data_layout.addWidget(self.data_raw_text)
        layout.addWidget(data_group)

        onboarding_group = QGroupBox("首次启动向导")
        onboarding_layout = QVBoxLayout(onboarding_group)
        onboarding_layout.addWidget(QLabel("需要重新查看新手流程、API 配置或素材放置说明时，可以重新打开向导。"))
        open_wizard = QPushButton("重新打开首次启动向导"); open_wizard.setIcon(get_icon("info"))
        open_wizard.clicked.connect(self._open_first_run_wizard)
        onboarding_layout.addWidget(open_wizard, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(onboarding_group)

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
        guide_text.setMaximumHeight(360)
        guide_text.setPlainText(
            "【模型与 API】\n"
            "1.「保存 API 设置」只保存 Provider/Base URL/Model/Auth Header/Key，不立即切换当前模型。\n"
            "2.「设为当前模型」会先验证连接；验证失败不会切换，也不会覆盖上一套可用模型。\n"
            "3. API Key 行上方显示已保存的脱敏 Key；输入框只用于填写新 Key，留空保存会沿用旧 Key。\n"
            "4. Auth Header 要和服务商一致：DeepSeek/OpenAI 通常用 bearer；MiMo 等 OpenAI 兼容服务可选 api-key/x-api-key。\n"
            "5. 文本模型、TTS、图像、视频是独立槽位；切换文本模型不会改动未来的 TTS 或图像配置。\n"
            "【本地模型】\n"
            "6. Ollama/LM Studio 等本地服务要先启动，再拉取模型列表或手动填模型名。\n"
            "7. 本地 fallback 只表示云端不可用时允许回退，本地模型本身仍需「测试服务连接」和「设为当前模型」。\n"
            "【切换与历史】\n"
            "8. 上方「文本模型切换」用于直接切换、启用、停用；历史会保留最近使用过的文本模型，方便 DeepSeek/MiMo/本地模型来回换。\n"
            "9. 顶部状态只表示当前选择的文本模型；实时连通性以「测试连接」结果为准。\n"
            "【窗口】\n"
            "10. 设置中心是独立窗口，可最小化后从任务栏找回；右键角色仍可再次唤起并恢复原窗口。\n"
            "【角色与资源】\n"
            "11. 前台只显示摘要；原始 YAML、日志和路径放在「显示原始」按钮里，避免误把原始配置数据当成可读内容。\n"
            "12. 可编辑文件只有 character/speech/relationship/events 四类 YAML；lore、story、actions 默认只读，避免误改核心剧情资产。\n"
            "【关系与事件】\n"
            "13. 关系数值不是攻略条，而是达妮娅防御、信任、共情负荷和留下倾向的运行状态。\n"
            "14. 事件日志会记录点击、拖拽、回归、情绪与剧情触发；前台会翻译成可读摘要，原始日志仅用于排查。\n"
            "【数据安全】\n"
            "15. .env、data、assets/private、models、backups、dist、build 不应提交；导出备份会放在本地备份目录。"
        )
        help_content_layout.addWidget(guide_text)
        help_layout.addWidget(self.help_content)
        layout.addWidget(help_group)

        self.data_text.setPlainText("打开本页后加载运行态数据摘要。")
        index = self.tabs.addTab(tab, get_icon("settings"), "系统")
        self._register_lazy_tab(index, self._refresh_data)

    def _build_reminder_tab(self) -> None:
        config = self.settings_manager.load_app_config()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        description = QLabel("提醒由用户主动创建；自然语言提醒只解析明确的时间表达，不会代替用户决定任务。")
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QFormLayout()
        self.reminder_enabled = QCheckBox("启用到期提醒")
        self.reminder_enabled.setChecked(bool(config.get("reminder_enabled", True)))
        self.natural_reminder_enabled = QCheckBox("启用自然语言提醒识别")
        self.natural_reminder_enabled.setChecked(bool(config.get("natural_reminder_enabled", True)))
        form.addRow("提醒服务", self.reminder_enabled)
        form.addRow("自然语言", self.natural_reminder_enabled)
        layout.addLayout(form)
        self.reminder_status = QLabel()
        self.reminder_status.setWordWrap(True)
        buttons = QHBoxLayout()
        save = QPushButton("保存提醒设置"); save.setIcon(get_icon("save"))
        reset = QPushButton("恢复提醒默认"); reset.setIcon(get_icon("refresh"))
        save.clicked.connect(self._save_reminder_settings)
        reset.clicked.connect(self._reset_reminder_defaults)
        buttons.addWidget(save)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.reminder_status)
        layout.addStretch(1)
        self._refresh_reminder_status()
        self.tabs.addTab(tab, get_icon("remind"), "提醒")

    def _build_growth_tab(self) -> None:
        config = self.settings_manager.load_app_config()
        growth = config.get("growth", {})
        if not isinstance(growth, dict):
            growth = {}
        tab = QWidget()
        layout = QVBoxLayout(tab)
        description = QLabel(
            "纯本地功能，默认关闭。硬币、背包、成长和衣柜保存在 data/growth_state.json，"
            "不会发送给 Provider，也不会进入 Git 或发布包。"
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.growth_enabled = QCheckBox("启用本地养成")
        self.growth_enabled.setChecked(bool(growth.get("enabled", False)))
        self.growth_status = QLabel()
        self.growth_status.setWordWrap(True)
        buttons = QHBoxLayout()
        save = QPushButton("保存养成设置")
        save.setIcon(get_icon("save"))
        open_center = QPushButton("打开养成中心")
        open_center.setIcon(get_icon("protect"))
        reset = QPushButton("恢复关闭")
        reset.setIcon(get_icon("refresh"))
        save.clicked.connect(self._save_growth_settings)
        open_center.clicked.connect(self.controller.open_growth_center)
        reset.clicked.connect(self._reset_growth_settings)
        buttons.addWidget(save)
        buttons.addWidget(open_center)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        layout.addWidget(self.growth_enabled)
        layout.addLayout(buttons)
        layout.addWidget(self.growth_status)
        layout.addStretch(1)
        self._refresh_growth_status()
        self.tabs.addTab(tab, get_icon("protect"), "养成")

    def _build_file_organizer_tab(self) -> None:
        config = self.settings_manager.load_app_config()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        description = QLabel(
            "高风险功能，默认关闭。只会在你主动选择源目录和目标目录后生成预览；执行前仍需二次确认。"
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QFormLayout()
        self.file_organizer_enabled = QCheckBox("启用文件整理助手（预览）")
        self.file_organizer_enabled.setChecked(bool(config.get("file_organizer_enabled", False)))
        open_organizer = QPushButton("打开文件整理助手"); open_organizer.setIcon(get_icon("document"))
        open_organizer.clicked.connect(self.controller.open_file_organizer)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_organizer_enabled)
        file_row.addWidget(open_organizer)
        file_row.addStretch(1)
        form.addRow("文件整理", file_row)
        layout.addLayout(form)
        self.file_organizer_status = QLabel()
        self.file_organizer_status.setWordWrap(True)
        buttons = QHBoxLayout()
        save = QPushButton("保存文件整理设置"); save.setIcon(get_icon("save"))
        reset = QPushButton("恢复安全默认"); reset.setIcon(get_icon("refresh"))
        save.clicked.connect(self._save_integrated_features)
        reset.clicked.connect(self._reset_file_organizer_defaults)
        buttons.addWidget(save)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.file_organizer_status)
        layout.addStretch(1)
        self._refresh_integrated_feature_status()
        self.tabs.addTab(tab, get_icon("document"), "文件整理")

    def _build_system_status_tab(self) -> None:
        config = self.settings_manager.load_app_config()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        description = QLabel("默认关闭，仅在本机低频检查 CPU、内存、电池、磁盘和可选网络状态，不向 Provider 上传硬件信息。")
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QFormLayout()
        self.system_status_enabled = QCheckBox("启用系统状态感知")
        self.system_status_enabled.setChecked(bool(config.get("system_status_enabled", False)))
        self.system_status_interval = QSpinBox()
        self.system_status_interval.setRange(300, 7200)
        self.system_status_interval.setSuffix(" 秒")
        self.system_status_interval.setValue(int(config.get("system_status_interval_seconds", 300)))
        self.system_status_cooldown = QSpinBox()
        self.system_status_cooldown.setRange(300, 7200)
        self.system_status_cooldown.setSuffix(" 秒")
        self.system_status_cooldown.setValue(int(config.get("system_status_cooldown_seconds", 300)))
        self.system_status_cpu = QSpinBox(); self.system_status_cpu.setRange(1, 100); self.system_status_cpu.setSuffix("%")
        self.system_status_cpu.setValue(int(config.get("system_status_cpu_threshold", 90)))
        self.system_status_memory = QSpinBox(); self.system_status_memory.setRange(1, 100); self.system_status_memory.setSuffix("%")
        self.system_status_memory.setValue(int(config.get("system_status_memory_threshold", 90)))
        self.system_status_battery = QSpinBox(); self.system_status_battery.setRange(1, 100); self.system_status_battery.setSuffix("%")
        self.system_status_battery.setValue(int(config.get("system_status_battery_threshold", 20)))
        self.system_status_network = QCheckBox("检测网络断开")
        self.system_status_network.setChecked(bool(config.get("system_status_network_check_enabled", False)))
        form.addRow("系统状态", self.system_status_enabled)
        form.addRow("状态检查间隔", self.system_status_interval)
        form.addRow("状态提醒冷却", self.system_status_cooldown)
        form.addRow("CPU 阈值", self.system_status_cpu)
        form.addRow("内存阈值", self.system_status_memory)
        form.addRow("电池阈值", self.system_status_battery)
        form.addRow("网络检查", self.system_status_network)
        layout.addLayout(form)
        self.system_status_result = QLabel()
        self.system_status_result.setWordWrap(True)
        buttons = QHBoxLayout()
        save = QPushButton("保存系统状态设置"); save.setIcon(get_icon("save"))
        test = QPushButton("读取一次当前状态"); test.setIcon(get_icon("info"))
        reset = QPushButton("恢复安全默认"); reset.setIcon(get_icon("refresh"))
        save.clicked.connect(self._save_integrated_features)
        test.clicked.connect(self._test_system_status)
        reset.clicked.connect(self._reset_system_status_defaults)
        buttons.addWidget(save)
        buttons.addWidget(test)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.system_status_result)
        layout.addStretch(1)
        self._refresh_integrated_feature_status()
        self.tabs.addTab(tab, get_icon("laptop"), "系统状态")

    def _build_clipboard_tab(self) -> None:
        config = self.settings_manager.load_app_config()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        description = QLabel("隐私功能，默认关闭。只处理文本，不自动发送 API，不保存完整剪贴板内容；敏感内容会在本地拦截。")
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QFormLayout()
        self.clipboard_enabled = QCheckBox("启用剪贴板互动")
        self.clipboard_enabled.setChecked(bool(config.get("clipboard_interaction_enabled", False)))
        self.clipboard_max_chars = QSpinBox()
        self.clipboard_max_chars.setRange(100, 10000)
        self.clipboard_max_chars.setValue(int(config.get("clipboard_max_chars", 1000)))
        self.clipboard_show_preview = QCheckBox("显示截断预览")
        self.clipboard_show_preview.setChecked(bool(config.get("clipboard_show_preview", False)))
        self.clipboard_allow_api = QCheckBox("允许确认后进入 API 对话")
        self.clipboard_allow_api.setChecked(bool(config.get("clipboard_allow_api_after_confirm", True)))
        self.clipboard_sensitive_block = QCheckBox("启用敏感内容拦截")
        self.clipboard_sensitive_block.setChecked(bool(config.get("clipboard_sensitive_block_enabled", True)))
        form.addRow("剪贴板", self.clipboard_enabled)
        form.addRow("剪贴板最大字符", self.clipboard_max_chars)
        form.addRow("剪贴板预览", self.clipboard_show_preview)
        form.addRow("剪贴板 API", self.clipboard_allow_api)
        form.addRow("敏感拦截", self.clipboard_sensitive_block)
        layout.addLayout(form)
        self.clipboard_result = QLabel()
        self.clipboard_result.setWordWrap(True)
        buttons = QHBoxLayout()
        save = QPushButton("保存剪贴板设置"); save.setIcon(get_icon("save"))
        clear = QPushButton("清空互动状态"); clear.setIcon(get_icon("refresh"))
        test = QPushButton("测试本地拦截"); test.setIcon(get_icon("info"))
        reset = QPushButton("恢复隐私默认"); reset.setIcon(get_icon("refresh"))
        save.clicked.connect(self._save_integrated_features)
        clear.clicked.connect(self._clear_clipboard_state)
        test.clicked.connect(self._test_clipboard_filter)
        reset.clicked.connect(self._reset_clipboard_defaults)
        buttons.addWidget(save)
        buttons.addWidget(clear)
        buttons.addWidget(test)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.clipboard_result)
        layout.addStretch(1)
        self._refresh_integrated_feature_status()
        self.tabs.addTab(tab, get_icon("document"), "剪贴板")

    def _build_focus_tab(self) -> None:
        config = self.settings_manager.load_app_config()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        description = QLabel("默认关闭。专注模式只静默非必要主动提示，不会拦截用户输入、设置窗口、安全警告或重要提醒。")
        description.setWordWrap(True)
        layout.addWidget(description)
        form = QFormLayout()
        self.focus_enabled = QCheckBox("启用专注 / 游戏模式")
        self.focus_enabled.setChecked(bool(config.get("focus_mode_enabled", False)))
        self.focus_manual = QCheckBox("手动进入专注模式")
        self.focus_manual.setChecked(bool(config.get("focus_mode_manual", False)))
        self.focus_auto = QCheckBox("按进程白名单自动进入")
        self.focus_auto.setChecked(bool(config.get("focus_mode_auto_game_detect", False)))
        self.focus_whitelist = QTextEdit()
        self.focus_whitelist.setMaximumHeight(70)
        whitelist = config.get("focus_mode_process_whitelist", [])
        self.focus_whitelist.setPlainText("\n".join(str(item) for item in whitelist if str(item).strip()))
        self.focus_silence_idle = QCheckBox("静默闲聊/空闲动作")
        self.focus_silence_idle.setChecked(bool(config.get("focus_mode_silence_idle_chat", True)))
        self.focus_silence_hourly = QCheckBox("静默整点报时")
        self.focus_silence_hourly.setChecked(bool(config.get("focus_mode_silence_hourly_chime", True)))
        self.focus_silence_edge = QCheckBox("静默左右边缘趴墙")
        self.focus_silence_edge.setChecked(bool(config.get("focus_mode_silence_edge_peek", True)))
        self.focus_silence_system = QCheckBox("静默系统状态提醒")
        self.focus_silence_system.setChecked(bool(config.get("focus_mode_silence_system_status", True)))
        self.focus_silence_clipboard = QCheckBox("静默剪贴板提示")
        self.focus_silence_clipboard.setChecked(bool(config.get("focus_mode_silence_clipboard", True)))
        self.focus_allow_important = QCheckBox("允许重要提醒")
        self.focus_allow_important.setChecked(bool(config.get("focus_mode_allow_important_reminders", True)))
        form.addRow("专注模式", self.focus_enabled)
        form.addRow("手动专注", self.focus_manual)
        form.addRow("自动检测", self.focus_auto)
        form.addRow("进程白名单", self.focus_whitelist)
        form.addRow("专注静默", self.focus_silence_idle)
        form.addRow("", self.focus_silence_hourly)
        form.addRow("", self.focus_silence_edge)
        form.addRow("", self.focus_silence_system)
        form.addRow("", self.focus_silence_clipboard)
        form.addRow("重要提醒", self.focus_allow_important)
        layout.addLayout(form)
        self.focus_result = QLabel()
        self.focus_result.setWordWrap(True)
        buttons = QHBoxLayout()
        save = QPushButton("保存专注模式设置"); save.setIcon(get_icon("save"))
        exit_focus = QPushButton("退出专注模式"); exit_focus.setIcon(get_icon("refresh"))
        reset = QPushButton("恢复专注默认"); reset.setIcon(get_icon("refresh"))
        save.clicked.connect(self._save_integrated_features)
        exit_focus.clicked.connect(self._exit_focus_mode)
        reset.clicked.connect(self._reset_focus_defaults)
        buttons.addWidget(save)
        buttons.addWidget(exit_focus)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.focus_result)
        layout.addStretch(1)
        self._refresh_integrated_feature_status()
        self.tabs.addTab(tab, get_icon("chip"), "专注模式")

    def _build_privacy_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        group = QGroupBox("本地数据与隐私边界")
        group_layout = QVBoxLayout(group)
        text = QLabel(
            "API Key、聊天记录、提醒、记忆和关系状态只保存在本机运行态目录。"
            " `.env`、`data/`、`assets/private/`、`models/`、`backups/`、`dist/`、`build/` 和 `release/`"
            " 不应进入 Git。剪贴板、系统状态和文件整理均默认关闭。"
        )
        text.setWordWrap(True)
        group_layout.addWidget(text)
        self.privacy_status = QLabel()
        self.privacy_status.setWordWrap(True)
        group_layout.addWidget(self.privacy_status)
        buttons = QHBoxLayout()
        refresh = QPushButton("刷新隐私状态"); refresh.setIcon(get_icon("refresh"))
        defaults = QPushButton("关闭高风险功能"); defaults.setIcon(get_icon("settings"))
        refresh.clicked.connect(self._refresh_privacy_status)
        defaults.clicked.connect(self._restore_privacy_defaults)
        buttons.addWidget(refresh)
        buttons.addWidget(defaults)
        buttons.addStretch(1)
        group_layout.addLayout(buttons)
        layout.addWidget(group)
        layout.addStretch(1)
        self._refresh_privacy_status()
        self.tabs.addTab(tab, get_icon("info"), "隐私与安全")

    def _build_diagnostics_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        description = QLabel("诊断只显示脱敏后的配置、资源和运行态结果，不显示完整 API Key。")
        description.setWordWrap(True)
        layout.addWidget(description)
        self.diagnostics_text = QTextEdit()
        self.diagnostics_text.setReadOnly(True)
        run = QPushButton("运行诊断"); run.setIcon(get_icon("settings"))
        run.clicked.connect(self._run_diagnostics)
        layout.addWidget(run, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.diagnostics_text)
        self.tabs.addTab(tab, get_icon("settings"), "诊断")

    def _save_reminder_settings(self) -> None:
        config = self.settings_manager.load_app_config()
        config["reminder_enabled"] = self.reminder_enabled.isChecked()
        config["natural_reminder_enabled"] = self.natural_reminder_enabled.isChecked()
        self.settings_manager.save_app_config(config)
        self.controller.app_config.update(config)
        self._refresh_reminder_status()

    def _save_growth_settings(self) -> None:
        enabled = self.growth_enabled.isChecked()
        self.controller.growth_manager.set_enabled(enabled)
        self.controller.app_config.setdefault("growth", {})["enabled"] = enabled
        self.controller.window.set_context_menu(self.controller.menu_manager.create_menu())
        self._refresh_growth_status()

    def _reset_growth_settings(self) -> None:
        self.growth_enabled.setChecked(False)
        self._save_growth_settings()

    def _refresh_growth_status(self) -> None:
        state = self.controller.growth_manager.snapshot(
            self.controller.affinity_manager.value()
        )
        self.growth_status.setText(
            f"当前状态：{'已启用' if self.growth_enabled.isChecked() else '已关闭'}；"
            f"硬币 {state['coins']}；成长等级 {state['level']}；"
            f"背包 {sum(state['inventory'].values())} 件；"
            f"衣柜 {len(state['owned_outfits'])} 套。"
        )

    def _reset_reminder_defaults(self) -> None:
        self.reminder_enabled.setChecked(True)
        self.natural_reminder_enabled.setChecked(True)
        self._save_reminder_settings()

    def _refresh_reminder_status(self) -> None:
        enabled = self.reminder_enabled.isChecked()
        natural = self.natural_reminder_enabled.isChecked()
        self.reminder_status.setText(
            f"当前状态：到期提醒{'已启用' if enabled else '已关闭'}；自然语言识别{'已启用' if natural else '已关闭'}。"
        )

    def _reset_file_organizer_defaults(self) -> None:
        self.file_organizer_enabled.setChecked(False)
        self._save_integrated_features()

    def _reset_system_status_defaults(self) -> None:
        self.system_status_enabled.setChecked(False)
        self.system_status_interval.setValue(300)
        self.system_status_cooldown.setValue(300)
        self.system_status_cpu.setValue(90)
        self.system_status_memory.setValue(90)
        self.system_status_battery.setValue(20)
        self.system_status_network.setChecked(False)
        self._save_integrated_features()

    def _test_system_status(self) -> None:
        status = self.controller.system_status_manager.get_current_status()
        battery = "不可用" if status.battery_percent is None else f"{status.battery_percent:.0f}%"
        self.system_status_result.setText(
            f"本地读取结果：CPU {status.cpu_percent:.0f}%；内存 {status.memory_percent:.0f}%；"
            f"磁盘 {status.disk_percent:.0f}%；电池 {battery}。本次结果未发送给 Provider。"
        )

    def _clear_clipboard_state(self) -> None:
        self.controller.clipboard_interaction.last_text = ""
        self.clipboard_result.setText("剪贴板互动状态已清空；未读取或保存当前剪贴板正文。")

    def _test_clipboard_filter(self) -> None:
        result = self.controller.clipboard_interaction.check_text("测试文本，不包含敏感信息。")
        self.clipboard_result.setText(f"本地过滤测试：{result.get('message', '完成')} 未调用 Provider。")

    def _reset_clipboard_defaults(self) -> None:
        self.clipboard_enabled.setChecked(False)
        self.clipboard_max_chars.setValue(1000)
        self.clipboard_show_preview.setChecked(False)
        self.clipboard_allow_api.setChecked(True)
        self.clipboard_sensitive_block.setChecked(True)
        self._save_integrated_features()

    def _exit_focus_mode(self) -> None:
        self.focus_manual.setChecked(False)
        self.controller.focus_mode_manager.exit_focus_mode()
        self._save_integrated_features()

    def _reset_focus_defaults(self) -> None:
        self.focus_enabled.setChecked(False)
        self.focus_manual.setChecked(False)
        self.focus_auto.setChecked(False)
        self.focus_whitelist.clear()
        self.focus_silence_idle.setChecked(True)
        self.focus_silence_hourly.setChecked(True)
        self.focus_silence_edge.setChecked(True)
        self.focus_silence_system.setChecked(True)
        self.focus_silence_clipboard.setChecked(True)
        self.focus_allow_important.setChecked(True)
        self._save_integrated_features()

    def _refresh_integrated_feature_status(self) -> None:
        if hasattr(self, "file_organizer_status"):
            self.file_organizer_status.setText(
                f"当前状态：{'已启用，仍需手动选择目录和确认执行' if self.file_organizer_enabled.isChecked() else '已关闭'}。"
            )
        if hasattr(self, "system_status_result") and not self.system_status_result.text():
            self.system_status_result.setText(
                f"当前状态：{'已启用低频本地检查' if self.system_status_enabled.isChecked() else '已关闭'}。"
            )
        if hasattr(self, "clipboard_result") and not self.clipboard_result.text():
            self.clipboard_result.setText(
                f"当前状态：{'已启用本地文本监听' if self.clipboard_enabled.isChecked() else '已关闭，不监听剪贴板'}。"
            )
        if hasattr(self, "focus_result"):
            active = bool(getattr(self.controller.focus_mode_manager, "is_active", False))
            self.focus_result.setText(
                f"当前状态：配置{'已启用' if self.focus_enabled.isChecked() else '已关闭'}；"
                f"运行态{'正在专注' if active else '未进入专注'}。"
            )

    def _refresh_privacy_status(self) -> None:
        config = self.settings_manager.load_app_config()
        active = [
            name
            for name, enabled in (
                ("文件整理", config.get("file_organizer_enabled", False)),
                ("系统状态", config.get("system_status_enabled", False)),
                ("剪贴板", config.get("clipboard_interaction_enabled", False)),
                ("专注模式", config.get("focus_mode_enabled", False)),
            )
            if bool(enabled)
        ]
        self.privacy_status.setText(
            "高风险功能状态：" + ("、".join(active) + " 已启用。" if active else "均为关闭。")
        )

    def _restore_privacy_defaults(self) -> None:
        config = self.settings_manager.load_app_config()
        config["file_organizer_enabled"] = False
        config["system_status_enabled"] = False
        config["clipboard_interaction_enabled"] = False
        config["focus_mode_enabled"] = False
        config["focus_mode_manual"] = False
        config["focus_mode_auto_game_detect"] = False
        self.settings_manager.save_app_config(config)
        self.controller.app_config.update(config)
        self.controller.apply_integrated_feature_config()
        if hasattr(self, "file_organizer_enabled"):
            self.file_organizer_enabled.setChecked(False)
            self.system_status_enabled.setChecked(False)
            self.clipboard_enabled.setChecked(False)
            self.focus_enabled.setChecked(False)
            self.focus_manual.setChecked(False)
            self.focus_auto.setChecked(False)
        self._refresh_integrated_feature_status()
        self._refresh_privacy_status()

    def _save_integrated_features(self) -> None:
        config = self.settings_manager.load_app_config()
        config["file_organizer_enabled"] = self.file_organizer_enabled.isChecked()
        config["system_status_enabled"] = self.system_status_enabled.isChecked()
        config["system_status_interval_seconds"] = self.system_status_interval.value()
        config["system_status_cooldown_seconds"] = self.system_status_cooldown.value()
        config["system_status_cpu_threshold"] = self.system_status_cpu.value()
        config["system_status_memory_threshold"] = self.system_status_memory.value()
        config["system_status_battery_threshold"] = self.system_status_battery.value()
        config["system_status_network_check_enabled"] = self.system_status_network.isChecked()
        config["clipboard_interaction_enabled"] = self.clipboard_enabled.isChecked()
        config["clipboard_max_chars"] = self.clipboard_max_chars.value()
        config["clipboard_show_preview"] = self.clipboard_show_preview.isChecked()
        config["clipboard_allow_api_after_confirm"] = self.clipboard_allow_api.isChecked()
        config["clipboard_sensitive_block_enabled"] = self.clipboard_sensitive_block.isChecked()
        config["focus_mode_enabled"] = self.focus_enabled.isChecked()
        config["focus_mode_manual"] = self.focus_manual.isChecked()
        config["focus_mode_auto_game_detect"] = self.focus_auto.isChecked()
        config["focus_mode_process_whitelist"] = [
            line.strip() for line in self.focus_whitelist.toPlainText().splitlines() if line.strip()
        ]
        config["focus_mode_silence_idle_chat"] = self.focus_silence_idle.isChecked()
        config["focus_mode_silence_hourly_chime"] = self.focus_silence_hourly.isChecked()
        config["focus_mode_silence_edge_peek"] = self.focus_silence_edge.isChecked()
        config["focus_mode_silence_system_status"] = self.focus_silence_system.isChecked()
        config["focus_mode_silence_clipboard"] = self.focus_silence_clipboard.isChecked()
        config["focus_mode_allow_important_reminders"] = self.focus_allow_important.isChecked()
        self.settings_manager.save_app_config(config)
        self.controller.app_config.update(config)
        self.controller.apply_integrated_feature_config()
        self.controller.window.set_context_menu(self.controller.menu_manager.create_menu())
        self._refresh_integrated_feature_status()
        if hasattr(self, "privacy_status"):
            self._refresh_privacy_status()

    def _masked_api_key_for_provider(self, provider: str, prov_conf: dict[str, Any] | None = None) -> str:
        from .chat_client import mask_key

        env_key = str((prov_conf or {}).get("api_key_env") or ProviderMeta.get_api_key_env(provider))
        return mask_key(self.settings_manager.current_api_key(env_key))

    def _update_saved_api_key_label(self, provider: str, prov_conf: dict[str, Any] | None = None) -> None:
        masked = self._masked_api_key_for_provider(provider, prov_conf)
        self.api_key_input.setPlaceholderText(_api_key_placeholder(masked))
        self.saved_api_key_label.setText(_saved_api_key_status(masked))
        if masked and masked != "<empty>":
            self.saved_api_key_label.setStyleSheet("color: #22863a; font-size: 11px;")
        else:
            self.saved_api_key_label.setStyleSheet("color: #6a737d; font-size: 11px;")

    def _toggle_api_key_visibility(self, checked: bool) -> None:
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.api_key_toggle_btn.setText("隐" if checked else "显")

    def _current_provider_key(self) -> str:
        return self._provider_display_map.get(self.provider_input.currentText(), "deepseek")

    def _on_provider_changed(self, display_or_id: str) -> None:
        key = self._provider_display_map.get(display_or_id, display_or_id)
        prov_conf = self.api.get("providers", {}).get(key, {})
        meta = ProviderMeta.get(key)
        self.base_url_input.setText(str(prov_conf.get("base_url") or meta.get("base_url", "")))
        self.model_input.setText(str(prov_conf.get("model") or meta.get("default_model", "")))
        self.auth_header_input.setCurrentText(str(prov_conf.get("auth_header") or meta.get("auth_header", "bearer")))
        self._update_saved_api_key_label(key, prov_conf)

    def _save_api_settings(self, notify: bool = True, reload_client: bool = True) -> str:
        api_key = self.api_key_input.text()
        provider = self._current_provider_key()
        base_url = self.base_url_input.text().strip()
        model = self.model_input.text().strip()
        self.settings_manager.save_api_settings(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key if api_key else None,
            auth_header=self.auth_header_input.currentText(),
            local_mode=self.local_mode_input.isChecked(),
        )
        if reload_client:
            self.controller.chat_client.reload()
        self.api_key_input.clear()
        self.api = self.settings_manager.load_api_config()
        self._update_saved_api_key_label(provider, self.api.get("providers", {}).get(provider, {}))
        if notify:
            self.api_result.setText("API 设置已保存；API Key 已写入 .env 或保持原值。点击「设为当前模型」后才会验证并生效。")
            self.controller.window.speak("……API 设置保存好了。希望你没填错。")
            self.controller.window.animation_manager.trigger_happy()
        self._refresh_active_status()
        self._refresh_profile_switcher()
        return ProviderMeta.make_profile_id(provider)

    def _test_api_connection(self) -> None:
        if self.api_worker is not None and self.api_worker.isRunning():
            return
        self.api_result.setText("正在后台测试连接...")
        api_key = self.api_key_input.text().strip()
        self.api_worker = _ApiTestWorker(
            self.settings_manager,
            profile=self._cloud_profile_from_form(),
            api_key_override=api_key or None,
        )
        self.api_worker.finished_with_result.connect(lambda ok, msg: self.api_result.setText(("通过：" if ok else "失败：") + msg))
        self.api_worker.finished.connect(self.api_worker.deleteLater)
        self.api_worker.start()

    def _cloud_profile_from_form(self) -> dict[str, Any]:
        provider = self._current_provider_key()
        base_url = self.base_url_input.text().strip()
        model = self.model_input.text().strip()
        meta = ProviderMeta.get(provider)
        auth_header = self.settings_manager.resolve_auth_header(provider, base_url, self.auth_header_input.currentText())
        return {
            "id": ProviderMeta.make_profile_id(provider),
            "name": f"{ProviderMeta.get_display_name(provider)} ({model or meta.get('default_model', '')})",
            "type": "text",
            "provider": provider,
            "api_style": ProviderMeta.get_api_style(provider),
            "base_url": base_url or str(meta.get("base_url", "")),
            "model": model or str(meta.get("default_model", "")),
            "api_key_env": ProviderMeta.get_api_key_env(provider),
            "auth_header": auth_header,
            "enabled": True,
            "capabilities": ["text"],
            "source": "cloud",
            "timeout": ProviderMeta.get_timeout(provider),
            "max_tokens": ProviderMeta.get_max_tokens(provider),
        }

    def _save_pet_settings(self) -> None:
        config = self.settings_manager.load_app_config()
        config.setdefault("pet", {})["pet_height"] = self.pet_size.value()
        config.setdefault("pet", {})["target_height"] = self.pet_size.value()
        config.setdefault("window", {})["show_input"] = self.show_input.isChecked()
        config.setdefault("window", {})["always_on_top"] = self.always_on_top.isChecked()
        config.setdefault("window", {})["opacity_percent"] = self.opacity.value()
        config.setdefault("pet", {})["edge_peek_enabled"] = self.edge_peek.isChecked()
        config["idle_chat_enabled"] = self.idle_chat.isChecked()
        config["idle_chat_minutes"] = self.idle_minutes.value()
        config["idle_behavior_enabled"] = self.idle_behavior.isChecked()
        config["idle_behavior_seconds"] = self.idle_behavior_seconds.value()
        config["hourly_chime_enabled"] = self.hourly_chime.isChecked()
        config["day_night_enabled"] = self.day_night.isChecked()
        self.settings_manager.save_app_config(config)
        self.controller.app_config.update(config)
        self.controller.save_pet_height(self.pet_size.value())
        self.controller.window.set_input_visible(self.show_input.isChecked(), expand=self.show_input.isChecked())
        self.controller.window.set_always_on_top(self.always_on_top.isChecked())
        self.controller.window.setWindowOpacity(self.opacity.value() / 100)
        self.controller.window.behavior_engine.reload_config(self.controller.app_config)
        self.controller.window.set_context_menu(self.controller.menu_manager.create_menu())
        self.pet_result.setText("已保存。大小、输入框、置顶、透明度、趴墙已即时生效；部分定时器配置重启后完全生效。")
        self.controller.window.speak("……保存好啦。别又忘了哦。")
        self.controller.window.animation_manager.trigger_happy()

    def _refresh_action_status(self) -> None:
        asset_manager = self.controller.asset_manager
        try:
            manifest = asset_manager.manifest()
            source = "private" if "assets\\private" in str(asset_manager.active_asset_dir()) or "assets/private" in str(asset_manager.active_asset_dir()) else "placeholder"
            raw_lines = [f"资源来源: {source}", f"资源目录: {asset_manager.active_asset_dir()}", "manifest: OK"]
            available = []
            missing = []
            for action in ["idle", "talk", "clicked", "drag", "sleep", "happy", "remind", "soft_idle", "close_idle", "bubble", "look_away"]:
                frames = asset_manager.frames_for_state(action)
                status = "available" if frames and any(frame.exists() for frame in frames) else "missing"
                (available if status == "available" else missing).append(action)
                raw_lines.append(f"- {action}: {status}; frames={[str(frame.name) for frame in frames[:3]]}")
            lines = [
                f"资源来源：{'私有素材' if source == 'private' else '占位素材'}",
                "资源清单：可读取",
                f"可用动作：{len(available)} 个",
                f"缺失动作：{('、'.join(missing) if missing else '无')}",
                "需要查看素材目录和帧文件时可展开原始详情。",
            ]
        except Exception as exc:
            lines = [f"动作资源读取失败：{exc.__class__.__name__}"]
            raw_lines = [f"manifest: FAILED {exc.__class__.__name__}"]
        self.action_status.setPlainText("\n".join(lines))
        if hasattr(self, "action_raw_details"):
            self.action_raw_details.setPlainText("\n".join(raw_lines))

    def _toggle_action_details(self) -> None:
        visible = not self.action_raw_details.isVisible()
        self.action_raw_details.setVisible(visible)
        self.action_details_btn.setText("隐藏原始详情" if visible else "显示原始详情")

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
        files = status.get("files", {})
        missing = [name for name, file_status in files.items() if not file_status.get("exists")]
        yaml_errors = [name for name, file_status in files.items() if file_status.get("yaml_ok") is False]
        lines = [
            f"角色包：{'已加载' if status['loaded'] else '加载失败'}",
            f"结构校验：{'通过' if status['validation_ok'] else '异常'}",
            "可编辑配置：character.yaml、speech.yaml、relationship.yaml、events.yaml",
            "只读资产：lore.md、lore_index.yaml、actions.yaml、story.yaml",
        ]
        if missing:
            lines.append("缺失文件：" + "、".join(missing))
        if yaml_errors:
            lines.append("YAML 异常：" + "、".join(yaml_errors))
        if status.get("validation_errors"):
            lines.append("校验信息：" + str(status["validation_errors"]))
        self.character_status.setText("\n".join(lines))

    def _load_pack_file(self, name: str) -> None:
        try:
            text = self.character_editor.read_file(name)
            editable = name in EDITABLE_FILES
            self.pack_editor_text.setPlainText(text)
            self.pack_editor_text.setReadOnly(not editable)
            self.pack_summary_text.setPlainText(_format_pack_file_summary(name, text, editable))
        except Exception as exc:
            self.pack_editor_text.setPlainText(f"读取失败：{exc.__class__.__name__}")
            self.pack_editor_text.setReadOnly(True)
            self.pack_summary_text.setPlainText(f"读取失败：{exc.__class__.__name__}")

    def _toggle_pack_raw_file(self) -> None:
        visible = not self.pack_editor_text.isVisible()
        self.pack_editor_text.setVisible(visible)
        self.pack_raw_toggle_btn.setText("隐藏原始文件" if visible else "显示原始文件")

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
        self.relationship_text.setPlainText(_format_relationship_summary(state))
        if hasattr(self, "relationship_raw_text"):
            raw_lines = [f"{key}: {value}" for key, value in state.items()]
            self.relationship_raw_text.setPlainText("\n".join(raw_lines) or "relationship_state.json 不可读或为空。")

    def _refresh_relationship_bundle(self) -> None:
        self._refresh_relationship()
        self._refresh_memory()
        self._refresh_events()

    def _refresh_events(self) -> None:
        status = self.relationship_viewer.status()
        events = status["event_log"][-20:]
        raw_event_lines = [
            f"- {e.get('timestamp','')} event={e.get('event_id')} source={e.get('source')} effect={e.get('relationship_effect')} lore={e.get('lore_fragments_used')} {e.get('stage_before')}->{e.get('stage_after')}"
            for e in events
            if isinstance(e, dict)
        ]
        if hasattr(self, "events_text"):
            self.events_text.setPlainText(_format_event_log_summary(events))
        if hasattr(self, "events_raw_text"):
            self.events_raw_text.setPlainText("\n".join(raw_event_lines) or "暂无事件记录。")

    def _refresh_memory(self) -> None:
        status = self.relationship_viewer.status()
        memory = status.get("user_memory")
        if not isinstance(memory, dict):
            memory = {}
        profile = self.controller.profile_manager.load()
        notes = _read_recent_text_lines(self.controller.notes_manager.path, limit=12)
        if hasattr(self, "memory_text"):
            self.memory_text.setPlainText(_format_user_memory_summary(profile, memory, notes))

    def _save_profile_settings(self) -> None:
        self.controller.save_profile(
            {
                "user_name": self.profile_user_name.text(),
                "birthday": self.profile_birthday.text(),
                "relationship": self.profile_relationship.text(),
                "style": self.profile_style.text(),
            }
        )
        profile = self.controller.profile_manager.load()
        self.profile_user_name.setText(profile["user_name"])
        self.profile_birthday.setText(profile.get("birthday", ""))
        self.profile_relationship.setText(profile["relationship"])
        self.profile_style.setText(profile["style"])
        self.profile_status.setText("用户档案已保存；生日仅保留月和日。")
        self._refresh_memory()

    def _add_memory_note(self) -> None:
        text = self.memory_note_input.text().strip()
        if not text:
            QMessageBox.information(self, "记忆备忘录", "先写一条要记住的内容。")
            return
        self.controller.add_note(text)
        self.memory_note_input.clear()
        self._refresh_memory()

    def _clear_memory(self) -> None:
        result = QMessageBox.question(
            self,
            "清空记忆",
            "会清空自动记忆和手动备忘，但不会重置关系状态。继续吗？",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        from core.memory_engine import clear_user_memory

        clear_user_memory()
        self.controller.notes_manager.clear()
        if hasattr(self.controller, "chat_client"):
            self.controller.chat_client.reload()
        self._refresh_memory()
        QMessageBox.information(self, "记忆备忘录", "已清空自动记忆和手动备忘。")

    def _toggle_relationship_raw(self) -> None:
        visible = not self.relationship_raw_text.isVisible()
        self.relationship_raw_text.setVisible(visible)
        self.relationship_raw_toggle_btn.setText("隐藏原始数据" if visible else "显示原始数据")

    def _toggle_events_raw(self) -> None:
        visible = not self.events_raw_text.isVisible()
        self.events_raw_text.setVisible(visible)
        self.events_raw_toggle_btn.setText("隐藏原始日志" if visible else "显示原始日志")

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
        self.data_text.setPlainText(_format_data_status_summary(status, paths))
        lines = [f"data_dir: {status['data_dir']} exists={status['exists']}"]
        for key, path in paths.items():
            lines.append(f"- {key}: exists={path.exists()} readable={status.get(key + '_readable')} error={status.get(key + '_error')}")
        if hasattr(self, "data_raw_text"):
            self.data_raw_text.setPlainText("\n".join(lines))

    def _toggle_data_raw(self) -> None:
        visible = not self.data_raw_text.isVisible()
        self.data_raw_text.setVisible(visible)
        self.data_raw_toggle_btn.setText("隐藏原始详情" if visible else "显示原始详情")

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

    def _open_first_run_wizard(self) -> None:
        from .first_run_wizard import FirstRunWizard
        from .setup_state_manager import SetupStateManager

        wizard = FirstRunWizard(SetupStateManager(root=self.settings_manager.root))
        wizard.exec()
        self.api = self.settings_manager.load_api_config()
        active = self.api.get("active_provider", "deepseek")
        active_display = next((display for display, key in self._provider_display_map.items() if key == active), None)
        if active_display:
            self.provider_input.setCurrentText(active_display)
        self.local_mode_input.setChecked(bool(self.api.get("local_mode", False)))
        self.api_key_input.clear()
        self._on_provider_changed(self.provider_input.currentText())
        self._refresh_active_status()

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
            ("Z.AI (GLM)", "zai", "https://api.z.ai/api/paas/v4", "glm-5.1",
             "https://docs.z.ai/", "OpenAI-compatible GLM API，需要 ZAI_API_KEY"),
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
            self.api = self.settings_manager.load_api_config()
            self._update_saved_api_key_label(provider, self.api.get("providers", {}).get(provider, {}))
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
            self.auth_header_input.setCurrentText(str(meta.get("auth_header", "bearer")))
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
            self._refresh_profile_switcher()
            dialog.accept()

        ok.clicked.connect(do_import)
        cancel.clicked.connect(dialog.reject)
        dialog.exec()


def _profile_has_text(profile: dict[str, Any]) -> bool:
    capabilities = profile.get("capabilities", [])
    return str(profile.get("type", "")) == "text" or (isinstance(capabilities, list) and "text" in capabilities)
