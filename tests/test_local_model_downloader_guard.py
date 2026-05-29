import os
import subprocess
import sys
from pathlib import Path

import pytest

@pytest.mark.skip(reason="ModelWizardDialog / LicenseConfirmationDialog 尚未实现")
def test_wizard_dialog_license_guard_in_subprocess(tmp_path):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANIYA_RELATION_DATA_DIR"] = str(tmp_path / "relation")
    
    script = rf"""
import os, sys
from PySide6.QtWidgets import QApplication
from src.settings_manager import SettingsManager
from src.settings_window import ModelWizardDialog, LicenseConfirmationDialog
from pathlib import Path

# Setup settings manager
class FakeConfigManager:
    def load_app_config(self):
        return {{}}
    def save_app_config(self, v):
        pass

app = QApplication.instance() or QApplication(sys.argv)
settings = SettingsManager(FakeConfigManager(), root=Path(r"{tmp_path}"))
settings.ensure_configs()

# 1. Test LicenseConfirmationDialog
dialog = LicenseConfirmationDialog()
assert dialog.accepted_license is False
dialog.on_agree()
assert dialog.accepted_license is True

# 2. Test ModelWizardDialog license checkboxes guarding download button
wizard = ModelWizardDialog(settings)
app.processEvents()

# Button should be disabled initially
assert wizard.btn_download_ollama.isEnabled() is False

# Toggling one checkbox should still keep it disabled
wizard.chk_license.setChecked(True)
wizard.update_button_states()
assert wizard.btn_download_ollama.isEnabled() is False

# Toggling all checkboxes should enable download button
wizard.chk_comm.setChecked(True)
wizard.chk_disclaimer.setChecked(True)
wizard.update_button_states()
assert wizard.btn_download_ollama.isEnabled() is True

print("WIZARD_GUARD_OK", flush=True)
os._exit(0)
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "WIZARD_GUARD_OK" in completed.stdout
