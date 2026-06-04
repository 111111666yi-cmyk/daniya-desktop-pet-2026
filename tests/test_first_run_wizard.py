import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.first_run_wizard import FirstRunWizard
from src.llm.provider_registry import Provider
from src.setup_state_manager import SetupStateManager


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_first_run_wizard_has_five_pages_and_no_future_feature_toggles(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)

    assert wizard.stack.count() == 5
    assert wizard.create_shortcut_check.isChecked() is False
    assert not hasattr(wizard, "check_tts")
    assert not hasattr(wizard, "check_t2i")
    assert not hasattr(wizard, "check_video")


def test_first_run_wizard_skip_marks_local_fallback(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)

    wizard._skip_wizard()

    first_run = manager.load_first_run_done()
    assert first_run["completed"] is True
    assert first_run["run_mode"] == "local_fallback"
    assert first_run["skipped_api"] is True


def test_first_run_wizard_writes_setup_state_to_data_not_tracked_config(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)

    wizard._skip_wizard()

    assert (tmp_path / "data" / "setup_config.json").exists()
    assert not (tmp_path / "config" / "setup_config.json").exists()


def test_setup_state_manager_migrates_legacy_tracked_setup_config(tmp_path):
    legacy_config = tmp_path / "config" / "setup_config.json"
    legacy_config.parent.mkdir(parents=True)
    legacy_config.write_text('{"first_run_setup": true, "run_mode": "fast"}', encoding="utf-8")
    manager = SetupStateManager(root=tmp_path)

    assert manager.is_first_run_complete() is True

    first_run = manager.load_first_run_done()
    assert first_run["completed"] is True
    assert first_run["run_mode"] == "fast"
    assert (tmp_path / "data" / "setup_config.json").exists()


def test_first_run_wizard_creates_optional_shortcut_on_finish(tmp_path, monkeypatch):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)
    calls = []

    def fake_create_shortcut(self):
        calls.append(self)
        return True, "created"

    monkeypatch.setattr(FirstRunWizard, "_create_desktop_shortcut", fake_create_shortcut)
    wizard.create_shortcut_check.setChecked(True)

    wizard._finish_setup()

    assert calls == [wizard]
    assert wizard.shortcut_result.text() == "created"
    assert manager.load_first_run_done()["completed"] is True


def test_first_run_wizard_shortcut_failure_does_not_block_completion(tmp_path, monkeypatch):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)

    monkeypatch.setattr(
        FirstRunWizard,
        "_create_desktop_shortcut",
        lambda _self: (False, "shortcut failed"),
    )
    wizard.create_shortcut_check.setChecked(True)

    wizard._finish_setup()

    assert wizard.shortcut_result.text() == "shortcut failed"
    assert manager.load_first_run_done()["completed"] is True


def test_first_run_wizard_saves_api_key_to_runtime_env(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)
    wizard.configure_api_radio.setChecked(True)
    wizard.api_key_input.setText("secret-key-for-test")

    wizard._save_current_api_settings()

    assert (tmp_path / ".env").read_text(encoding="utf-8").find("secret-key-for-test") >= 0
    assert manager.load_first_run_done().get("completed") is not True


def test_first_run_wizard_saves_openai_compatible_key_to_runtime_env(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)
    wizard.configure_api_radio.setChecked(True)
    wizard.provider_combo.setCurrentText(Provider.OPENAI_COMPATIBLE)
    wizard.base_url_input.setText("https://api.z.ai/api/paas/v4")
    wizard.model_input.setText("glm-4.7")
    wizard.api_key_input.setText("openai-compatible-secret")

    wizard._save_current_api_settings()

    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "OPENAI_COMPATIBLE_API_KEY=openai-compatible-secret" in env_text
    assert manager.load_first_run_done().get("completed") is not True


def test_first_run_wizard_saves_mimo_openai_compatible_auth_header(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)
    wizard.configure_api_radio.setChecked(True)
    wizard.provider_combo.setCurrentText(Provider.OPENAI_COMPATIBLE)
    wizard.base_url_input.setText("https://api.xiaomimimo.com/v1")
    wizard.model_input.setText("mimo-v2.5")
    wizard.api_key_input.setText("mimo-secret")

    wizard._save_current_api_settings()

    profiles = wizard.settings_manager.load_model_profiles()
    profile = next(p for p in profiles["profiles"] if p["id"] == "openai_compatible_default")
    assert profile["provider"] == Provider.OPENAI_COMPATIBLE
    assert profile["auth_header"] == "api-key"
    assert profiles["active_text_profile_id"] == "deepseek_default"
    assert "OPENAI_COMPATIBLE_API_KEY=mimo-secret" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_first_run_wizard_blocks_unvalidated_api_finish(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)
    wizard.configure_api_radio.setChecked(True)
    wizard.api_key_input.setText("secret-key-for-test")

    wizard._finish_setup()

    assert manager.load_first_run_done().get("completed") is not True
    assert "请先测试连接" in wizard.api_result.text()
