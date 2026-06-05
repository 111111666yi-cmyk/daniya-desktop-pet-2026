from __future__ import annotations

import sys
import logging
from pathlib import Path
from datetime import datetime
import pytest
from PySide6.QtWidgets import QApplication

from src.app import AppController


@pytest.fixture()
def mock_app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "relation"))
    
    first_run_file = tmp_path / "data" / "first_run_done.json"
    first_run_file.parent.mkdir(parents=True, exist_ok=True)
    first_run_file.write_text('{"first_run_complete": true}', encoding="utf-8")
    
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def test_render_cache_hits_and_clear(mock_app_env) -> None:
    controller = AppController(mock_app_env)
    window = controller.window
    
    icon_path = window.asset_manager.icon_path()
    assert icon_path.exists()
    
    # 1. Clear default startup cache and then render
    window.clear_render_cache()
    window.render_pet_pixmap(icon_path, visual_scale=1.0)
    assert len(window._scaled_pixmap_cache) == 1
    
    # 2. Verify cache hit (same reference returned)
    target_height = window.asset_manager.target_height()
    dpr = window._current_device_pixel_ratio()
    
    res1 = window._get_scaled_pixmap(icon_path, target_height, dpr)
    res2 = window._get_scaled_pixmap(icon_path, target_height, dpr)
    assert res1[0] is res2[0]  # Same QPixmap object reference
    
    # 3. Test clear_render_cache
    window.clear_render_cache()
    assert len(window._scaled_pixmap_cache) == 0
    
    # 4. Test cache clear on set_pet_height
    window.render_pet_pixmap(icon_path, visual_scale=1.0)
    old_key = (str(icon_path), target_height, round(dpr, 2))
    assert old_key in window._scaled_pixmap_cache
    window.set_pet_height(120)
    assert old_key not in window._scaled_pixmap_cache


def test_physical_event_serialization_queue(mock_app_env, monkeypatch) -> None:
    started_workers = []
    
    class MockWorker:
        def __init__(self, adapter, event_name):
            self.event_name = event_name
            self.finished = self
            self._callbacks = []
            
        def connect(self, callback):
            self._callbacks.append(callback)
            
        def start(self):
            started_workers.append(self)
            
        def deleteLater(self):
            pass
            
        def trigger_finished(self):
            for cb in self._callbacks:
                cb()

    monkeypatch.setattr("src.app.PhysicalEventWorker", MockWorker)
    
    controller = AppController(mock_app_env)
    assert controller.daniya_adapter.state_manager is controller.thread_safe_anim_manager
    
    # Fire 3 events concurrently
    controller._fire_physical_event("event_1")
    controller._fire_physical_event("event_2")
    controller._fire_physical_event("event_3")
    
    # Assert only the first one started (serialized execution)
    assert len(started_workers) == 1
    assert started_workers[0].event_name == "event_1"
    assert controller._phys_busy is True
    assert len(controller._pending_phys_events) == 2
    
    # Finish the first event
    started_workers[0].trigger_finished()
    
    # Assert the second one started
    assert len(started_workers) == 2
    assert started_workers[1].event_name == "event_2"
    assert len(controller._pending_phys_events) == 1
    
    # Finish the second event
    started_workers[1].trigger_finished()
    
    # Assert the third one started
    assert len(started_workers) == 3
    assert started_workers[2].event_name == "event_3"
    assert len(controller._pending_phys_events) == 0
    
    # Finish the third event
    started_workers[2].trigger_finished()
    
    # Assert busy flag cleared
    assert controller._phys_busy is False
    assert len(controller._pending_phys_events) == 0


def test_logging_setup_excepthook(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    
    from src.logging_setup import configure_logging, install_excepthook
    
    # Initialize log
    log_file = configure_logging()
    assert log_file.exists()
    
    # Write a test log
    logger = logging.getLogger("daniya")
    logger.info("Audit log testing info message")
    
    # Flush logs
    for h in logging.getLogger().handlers:
        h.flush()
        
    log_content = log_file.read_text(encoding="utf-8")
    assert "Audit log testing info message" in log_content
    
    # Test excepthook registration
    install_excepthook()
    assert sys.excepthook is not None


def test_shortcut_name_consistency() -> None:
    install_content = Path("install.bat").read_text(encoding="utf-8")
    create_shortcut_content = Path("create_shortcut.bat").read_text(encoding="utf-8")
    
    assert "达妮娅桌宠.lnk" in install_content
    assert "达妮娅桌宠.lnk" in create_shortcut_content
