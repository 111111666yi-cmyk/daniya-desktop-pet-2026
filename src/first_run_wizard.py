from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .llm.provider_registry import Provider, ProviderMeta
from .settings_manager import SettingsManager
from .ui.liquid_glass import LiquidGlassDialog
from .setup_state_manager import SetupStateManager
from .utils import ensure_dir, resource_path


class _WizardApiTestWorker(QThread):
    finished_with_result = Signal(bool, str)

    def __init__(
        self,
        settings_manager: SettingsManager,
        profile: dict[str, Any],
        api_key_override: str | None = None,
        activate_profile_id: str | None = None,
    ) -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.profile = profile
        self.api_key_override = api_key_override
        self.activate_profile_id = activate_profile_id

    def run(self) -> None:
        from .llm.provider_manager import ProviderManager

        pm = ProviderManager(api_config=self.settings_manager.load_api_config())
        pm.model_profiles_path = self.settings_manager.model_profiles_path
        pm.env_path = self.settings_manager.env_path
        ok, message = pm.test_profile_model(self.profile, api_key_override=self.api_key_override, timeout=8)
        if ok and self.activate_profile_id:
            ok, message = self.settings_manager.activate_text_profile(self.activate_profile_id)
        self.finished_with_result.emit(ok, message)


class FirstRunWizard(LiquidGlassDialog):
    """Five-page first-run guide for new users."""

    def __init__(self, setup_manager: SetupStateManager) -> None:
        super().__init__(title="达妮娅首次启动向导")
        self.setup_manager = setup_manager
        self.settings_manager = SettingsManager(root=setup_manager.root)
        self.api_worker: _WizardApiTestWorker | None = None
        self._validated_api_fingerprint: tuple[str, str, str, str, bool] | None = None
        self.page_titles = ["欢迎", "API 设置", "素材说明", "角色包", "完成"]

        self.setMinimumSize(640, 520)
        self.setModal(True)

        layout = QVBoxLayout()
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(self.title_label)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_welcome_page())
        self.stack.addWidget(self._build_api_page())
        self.stack.addWidget(self._build_assets_page())
        self.stack.addWidget(self._build_character_page())
        self.stack.addWidget(self._build_finish_page())
        self.stack.currentChanged.connect(self._refresh_nav)
        layout.addWidget(self.stack, 1)

        buttons = QHBoxLayout()
        self.skip_btn = QPushButton("跳过向导")
        self.back_btn = QPushButton("上一步")
        self.next_btn = QPushButton("下一步")
        self.finish_btn = QPushButton("完成")
        self.skip_btn.clicked.connect(self._skip_wizard)
        self.back_btn.clicked.connect(self._back)
        self.next_btn.clicked.connect(self._next)
        self.finish_btn.clicked.connect(self._finish_setup)
        buttons.addWidget(self.skip_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.back_btn)
        buttons.addWidget(self.next_btn)
        buttons.addWidget(self.finish_btn)
        layout.addLayout(buttons)
        self.setLayout(layout)

        self._refresh_nav()

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setStyleSheet("line-height: 1.35;")
        return label

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_label(
            "欢迎使用 Daniya Summer Desktop Pet。\n\n"
            "这是一个本地桌宠应用，可以透明置顶、拖拽移动、右键打开菜单，并通过输入框和达妮娅对话。\n\n"
            "没有 API Key 也可以启动，程序会使用 local fallback。私有素材和运行态数据只保存在本机，不会被提交到 Git，也不会进入 release 包。"
        ))
        layout.addStretch(1)
        return page

    def _build_api_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        mode_group = QGroupBox("API 模式")
        mode_layout = QVBoxLayout(mode_group)
        self.skip_api_radio = QRadioButton("跳过 API，先使用 local fallback")
        self.configure_api_radio = QRadioButton("配置云端 API")
        self.skip_api_radio.setChecked(True)
        api_mode = QButtonGroup(self)
        api_mode.addButton(self.skip_api_radio)
        api_mode.addButton(self.configure_api_radio)
        mode_layout.addWidget(self.skip_api_radio)
        mode_layout.addWidget(self.configure_api_radio)
        layout.addWidget(mode_group)

        form_group = QGroupBox("云端 API 配置")
        form = QFormLayout(form_group)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(Provider.all_cloud() + [Provider.OPENAI_COMPATIBLE])
        self.base_url_input = QLineEdit()
        self.model_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("API Key 会写入本机 .env，不会显示完整内容")
        form.addRow("Provider", self.provider_combo)
        form.addRow("Base URL", self.base_url_input)
        form.addRow("Model", self.model_input)
        form.addRow("API Key", self.api_key_input)
        layout.addWidget(form_group)
        self.api_form_group = form_group

        actions = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.api_result = QLabel("跳过 API 后仍可使用 local fallback。")
        self.api_result.setWordWrap(True)
        self.test_btn.clicked.connect(self._test_connection)
        actions.addWidget(self.test_btn)
        actions.addWidget(self.api_result, 1)
        layout.addLayout(actions)

        self.skip_api_radio.toggled.connect(self._refresh_api_controls)
        self.configure_api_radio.toggled.connect(self._refresh_api_controls)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self._on_provider_changed(self.provider_combo.currentText())
        self._refresh_api_controls()
        layout.addStretch(1)
        return page

    def _build_assets_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_label(
            "素材放置说明：\n\n"
            "1. 私有素材请放在 assets/private/，该目录被 Git 忽略。\n"
            "2. 角色包素材不要提交到 Git；缺素材时会使用 placeholder。\n"
            "3. normal1/normal2 是基础站立或待机占位图。\n"
            "4. manifest 用于描述动作资源映射。"
        ))
        buttons = QHBoxLayout()
        private_btn = QPushButton("打开 assets/private")
        daniya_btn = QPushButton("打开 characters/daniya")
        guide_btn = QPushButton("打开角色包指南")
        readme_btn = QPushButton("打开 README")
        private_btn.clicked.connect(lambda: self._open_runtime_path("assets", "private", create=True))
        daniya_btn.clicked.connect(lambda: self._open_resource_path("characters", "daniya"))
        guide_btn.clicked.connect(lambda: self._open_resource_path("docs", "character_pack_guide.md"))
        readme_btn.clicked.connect(lambda: self._open_resource_path("README.md"))
        for button in (private_btn, daniya_btn, guide_btn, readme_btn):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return page

    def _build_character_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_label(
            "角色包说明：\n\n"
            "1. 默认公开示例角色是 characters/daniya/。\n"
            "2. characters/template/ 是新角色起点和 fallback 模板。\n"
            "3. characters/test_dummy/ 只允许本地测试，clean clone 不要求它存在，也不进入 release。\n"
            "4. 创建新角色时，复制 template 后再改 metadata、speech、lore 与动作映射。\n"
            "5. 修改角色包后，可在右键菜单或设置中心重新加载。"
        ))
        layout.addStretch(1)
        return page

    def _build_finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_label(
            "准备完成。\n\n"
            "完成后会启动桌宠。之后可通过右键菜单打开设置中心，继续配置 API、本地模型、角色资源和数据诊断。\n\n"
            "如果需要重新查看本向导，可在设置中心的“系统”页点击“重新打开首次启动向导”。"
        ))
        self.create_shortcut_check = QCheckBox("创建桌面快捷方式：daniya521")
        self.create_shortcut_check.setChecked(False)
        layout.addWidget(self.create_shortcut_check)
        self.shortcut_result = QLabel("")
        self.shortcut_result.setWordWrap(True)
        layout.addWidget(self.shortcut_result)
        layout.addStretch(1)
        return page

    def _refresh_nav(self) -> None:
        index = self.stack.currentIndex()
        self.title_label.setText(f"{index + 1}/5  {self.page_titles[index]}")
        self.back_btn.setEnabled(index > 0)
        self.next_btn.setVisible(index < self.stack.count() - 1)
        self.finish_btn.setVisible(index == self.stack.count() - 1)

    def _refresh_api_controls(self) -> None:
        enabled = self.configure_api_radio.isChecked()
        self.api_form_group.setEnabled(enabled)
        self.test_btn.setEnabled(enabled)
        if not enabled:
            self.api_result.setText("已选择跳过 API。local fallback 可用，之后可在设置中心补填 Key。")

    def _on_provider_changed(self, provider: str) -> None:
        meta = ProviderMeta.get(provider)
        self.base_url_input.setText(str(meta.get("base_url", "")))
        self.model_input.setText(str(meta.get("default_model", "")))

    def _back(self) -> None:
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))

    def _next(self) -> None:
        self.stack.setCurrentIndex(min(self.stack.count() - 1, self.stack.currentIndex() + 1))

    def _save_current_api_settings(self) -> tuple[str, bool, bool, str]:
        if self.skip_api_radio.isChecked():
            meta = ProviderMeta.get(Provider.DEEPSEEK)
            self.settings_manager.save_api_settings(
                provider=Provider.DEEPSEEK,
                base_url=str(meta.get("base_url", "")),
                model=str(meta.get("default_model", "")),
                api_key=None,
                local_mode=True,
                activate=False,
            )
            return "local_fallback", False, True, ProviderMeta.make_profile_id(Provider.DEEPSEEK)

        provider = self.provider_combo.currentText()
        self.settings_manager.save_api_settings(
            provider=provider,
            base_url=self.base_url_input.text().strip(),
            model=self.model_input.text().strip(),
            api_key=self.api_key_input.text().strip() or None,
            local_mode=False,
            activate=False,
        )
        return "api_cloud", bool(self.api_key_input.text().strip()), False, ProviderMeta.make_profile_id(provider)

    def _test_connection(self) -> None:
        if self.api_worker is not None and self.api_worker.isRunning():
            return
        _, _, _, target_id = self._save_current_api_settings()
        self.api_result.setText("正在后台测试连接...")
        self.api_worker = _WizardApiTestWorker(
            self.settings_manager,
            profile=self._cloud_profile_from_form(),
            api_key_override=self.api_key_input.text().strip() or None,
            activate_profile_id=target_id,
        )
        self.api_worker.finished_with_result.connect(self._on_api_test_finished)
        self.api_worker.finished.connect(self.api_worker.deleteLater)
        self.api_worker.start()

    def _on_api_test_finished(self, ok: bool, message: str) -> None:
        if ok:
            self._validated_api_fingerprint = self._api_form_fingerprint()
        self.api_result.setText(("通过：" if ok else "失败：") + message)

    def _finish_setup(self) -> None:
        if self.configure_api_radio.isChecked() and self._validated_api_fingerprint != self._api_form_fingerprint():
            self.api_result.setText("请先测试连接；只有测试通过的配置才会设为当前模型。")
            self.stack.setCurrentIndex(1)
            return
        run_mode, api_configured, skipped_api, _target_id = self._save_current_api_settings()
        self._create_shortcut_if_requested()
        self.setup_manager.mark_first_run_complete(run_mode, api_configured=api_configured, skipped_api=skipped_api)
        self.accept()

    def _skip_wizard(self) -> None:
        self.skip_api_radio.setChecked(True)
        run_mode, api_configured, skipped_api, _target_id = self._save_current_api_settings()
        self.setup_manager.mark_first_run_complete(run_mode, api_configured=api_configured, skipped_api=skipped_api)
        self.accept()

    def _cloud_profile_from_form(self) -> dict[str, Any]:
        provider = self.provider_combo.currentText()
        base_url = self.base_url_input.text().strip()
        model = self.model_input.text().strip()
        meta = ProviderMeta.get(provider)
        auth_header = self.settings_manager.resolve_auth_header(provider, base_url)
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

    def _api_form_fingerprint(self) -> tuple[str, str, str, str, bool]:
        profile = self._cloud_profile_from_form()
        return (
            str(profile.get("provider", "")),
            str(profile.get("base_url", "")),
            str(profile.get("model", "")),
            str(profile.get("auth_header", "")),
            bool(self.api_key_input.text().strip()),
        )

    def _open_runtime_path(self, *parts: str, create: bool = False) -> None:
        path = self.setup_manager.root.joinpath(*parts)
        if create:
            ensure_dir(path)
        self._open_path(path)

    def _open_resource_path(self, *parts: str) -> None:
        self._open_path(resource_path(*parts))

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "无法打开", f"路径不存在：{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _create_shortcut_if_requested(self) -> None:
        if not self.create_shortcut_check.isChecked():
            self.shortcut_result.setText("")
            return
        ok, message = self._create_desktop_shortcut()
        self.shortcut_result.setText(message)
        if not ok:
            print(f"[Daniya] Desktop shortcut creation skipped/failed: {message}")

    def _create_desktop_shortcut(self) -> tuple[bool, str]:
        if os.name != "nt":
            return False, "桌面快捷方式仅支持 Windows。"

        target, working_dir = self._shortcut_launch_target()
        icon_path = resource_path("assets", "placeholder", "app.ico")
        script_path = Path(tempfile.gettempdir()) / f"daniya_shortcut_{os.getpid()}.ps1"
        script = """
param(
    [string]$TargetPath,
    [string]$WorkingDirectory,
    [string]$IconLocation,
    [string]$ShortcutName
)
$desktop = [Environment]::GetFolderPath('Desktop')
if ([string]::IsNullOrWhiteSpace($desktop)) {
    throw 'Desktop path unavailable'
}
$shortcutPath = [System.IO.Path]::Combine($desktop, ($ShortcutName + '.lnk'))
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $TargetPath
$shortcut.WorkingDirectory = $WorkingDirectory
if ($IconLocation -and (Test-Path -LiteralPath $IconLocation)) {
    $shortcut.IconLocation = $IconLocation
}
$shortcut.Save()
Write-Output $shortcutPath
""".strip()
        try:
            script_path.write_text(script, encoding="utf-8")
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    str(target),
                    str(working_dir),
                    str(icon_path),
                    "daniya521",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except Exception as exc:
            return False, f"创建桌面快捷方式失败：{exc.__class__.__name__}: {exc}"
        finally:
            try:
                script_path.unlink(missing_ok=True)
            except OSError:
                pass

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return False, f"创建桌面快捷方式失败：{detail or 'PowerShell 返回错误'}"
        created_path = result.stdout.strip() or "桌面"
        return True, f"已创建桌面快捷方式：{created_path}"

    def _shortcut_launch_target(self) -> tuple[Path, Path]:
        if getattr(sys, "frozen", False):
            exe_path = Path(sys.executable).resolve()
            return exe_path, exe_path.parent

        run_bat = resource_path("run.bat")
        if run_bat.exists():
            return run_bat.resolve(), run_bat.parent.resolve()

        return Path(sys.executable).resolve(), Path.cwd().resolve()
