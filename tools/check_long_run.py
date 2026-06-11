from __future__ import annotations

import gc
import os
import sys
import tempfile
import threading
import tracemalloc
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory(prefix="daniya-long-run-") as temp_dir:
        runtime = Path(temp_dir) / "runtime"
        os.environ["DANIYA_RUNTIME_ROOT"] = str(runtime)
        os.environ["DANIYA_RELATION_DATA_DIR"] = str(runtime / "data" / "daniya_relation")

        from PySide6.QtCore import QCoreApplication, QEvent, QTimer
        from PySide6.QtWidgets import QApplication
        import requests

        from src.app import AppController
        from src.settings_window import SettingsWindow

        network_calls = 0

        def block_network(*_args, **_kwargs):
            nonlocal network_calls
            network_calls += 1
            raise RuntimeError("network disabled in long-run check")

        original_request = requests.sessions.Session.request
        requests.sessions.Session.request = block_network
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with redirect_stdout(StringIO()):
            controller = AppController(app)
            controller.chat_client.reply = lambda _prompt: ("离线压力测试响应。", "local")
            controller.show()
            for _ in range(4):
                app.processEvents()

        gc.collect()
        baseline_widgets = len(app.allWidgets())
        baseline_timers = len(controller.findChildren(QTimer))
        baseline_threads = threading.active_count()
        baseline_pixmaps = len(controller.window._scaled_pixmap_cache)
        tracemalloc.start()
        start_current, _ = tracemalloc.get_traced_memory()

        with redirect_stdout(StringIO()):
            for index in range(50):
                controller.daniya_adapter.handle_user_text(f"普通对话回归第 {index + 1} 轮")

            for index in range(100):
                controller.window.show_message(f"bubble-{index}")
                controller.window.bubble.hide()

            states = ("idle", "happy", "clicked", "remind", "sleeping")
            for index in range(100):
                controller.window.animation_manager.set_state(states[index % len(states)])

            for _ in range(10):
                settings = SettingsWindow(controller)
                settings.show()
                app.processEvents()
                settings.close()
                settings.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()

            for _ in range(20):
                controller.window.set_input_visible(True)
                app.processEvents()
                controller.window.set_input_visible(False)
                app.processEvents()

            controller.reminder_manager.add("2099-01-01 00:00", "long-run-check")
            controller.reminder_manager.records()
            for _ in range(6):
                app.processEvents()

        gc.collect()
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        widget_delta = len(app.allWidgets()) - baseline_widgets
        timer_delta = len(controller.findChildren(QTimer)) - baseline_timers
        thread_delta = threading.active_count() - baseline_threads
        pixmap_delta = len(controller.window._scaled_pixmap_cache) - baseline_pixmaps
        retained_mib = max(0, current_bytes - start_current) / 1024 / 1024
        peak_mib = peak_bytes / 1024 / 1024
        workers_running = any(worker.isRunning() for worker in controller._phys_workers)

        failures = []
        if widget_delta > 4:
            failures.append(f"widget delta too large: {widget_delta}")
        if timer_delta > 2:
            failures.append(f"timer delta too large: {timer_delta}")
        if thread_delta > 1 or workers_running:
            failures.append("worker thread remained active")
        if pixmap_delta > 20:
            failures.append(f"pixmap cache delta too large: {pixmap_delta}")
        if network_calls:
            failures.append(f"network calls attempted: {network_calls}")

        print("Finite long-run stress check")
        print("- dialogue_turns: 50")
        print("- bubble_cycles: 100")
        print("- action_switches: 100")
        print("- settings_cycles: 10")
        print("- input_cycles: 20")
        print(f"- widget_delta: {widget_delta}")
        print(f"- timer_delta: {timer_delta}")
        print(f"- thread_delta: {thread_delta}")
        print(f"- pixmap_cache_delta: {pixmap_delta}")
        print(f"- network_calls: {network_calls}")
        print(f"- retained_traced_mib: {retained_mib:.2f}")
        print(f"- peak_traced_mib: {peak_mib:.2f}")
        print("- idle_30_minutes: MANUAL REQUIRED")
        print("- Windows RSS/GDI/handle trend: MANUAL REQUIRED")
        print("- real animation and audio cache trend: MANUAL REQUIRED")

        requests.sessions.Session.request = original_request
        controller.window.close()
        app.processEvents()
        if failures:
            print("Long-run stress check failed:")
            for failure in failures:
                print(f"- {failure}")
            return 1
        print("Finite long-run stress check passed.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
