import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.first_run_wizard import FirstRunWizard
from src.setup_state_manager import SetupStateManager


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_first_run_wizard_has_five_pages_and_no_future_feature_toggles(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)

    assert wizard.stack.count() == 5
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


def test_first_run_wizard_saves_api_key_to_runtime_env(tmp_path):
    _app()
    manager = SetupStateManager(root=tmp_path)
    wizard = FirstRunWizard(manager)
    wizard.configure_api_radio.setChecked(True)
    wizard.api_key_input.setText("secret-key-for-test")

    wizard._finish_setup()

    assert (tmp_path / ".env").read_text(encoding="utf-8").find("secret-key-for-test") >= 0
    assert manager.load_first_run_done()["api_configured"] is True
