from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.app import AppController
from src.settings_window import SIMPLE_SETTINGS_TABS, SettingsWindow


@pytest.fixture
def qapp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path / "runtime"))
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


def test_settings_center_defaults_to_simple_without_resetting_hidden_values(
    qapp: QApplication,
) -> None:
    controller = AppController(qapp)
    config = controller.config_manager.load_app_config()
    config["clipboard_interaction_enabled"] = True
    controller.config_manager.save_app_config(config)
    controller.app_config.update(config)
    window = SettingsWindow(controller)
    try:
        visible_tabs = {
            window.tabs.tabText(index)
            for index in range(window.tabs.count())
            if window.tabs.isTabVisible(index)
        }

        assert window._settings_mode == "simple"
        assert visible_tabs == SIMPLE_SETTINGS_TABS
        assert window.local_model_group.isHidden()
        assert window.pack_group.isHidden()
        assert window.events_group.isHidden()
        assert controller.config_manager.load_app_config()["clipboard_interaction_enabled"] is True
    finally:
        window.close()
        controller.window.close()


def test_advanced_mode_is_persisted_and_reveals_existing_pages(qapp: QApplication) -> None:
    controller = AppController(qapp)
    window = SettingsWindow(controller)
    try:
        window.advanced_mode_button.click()

        assert window._settings_mode == "advanced"
        assert all(window.tabs.isTabVisible(index) for index in range(window.tabs.count()))
        assert not window.local_model_group.isHidden()
        assert not window.pack_group.isHidden()
        assert not window.events_group.isHidden()
        assert controller.config_manager.load_app_config()["settings_mode"] == "advanced"
    finally:
        window.close()
        controller.window.close()
