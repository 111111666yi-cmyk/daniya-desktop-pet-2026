from __future__ import annotations

import os
import sys
import tempfile
import tracemalloc
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    process_started_at = perf_counter()
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    with tempfile.TemporaryDirectory(prefix="daniya-startup-") as temp_dir:
        runtime = Path(temp_dir) / "runtime"
        os.environ["DANIYA_RUNTIME_ROOT"] = str(runtime)
        os.environ["DANIYA_RELATION_DATA_DIR"] = str(runtime / "data" / "daniya_relation")

        from PySide6.QtWidgets import QApplication

        from src.app import AppController
        from src.startup_timing import REQUIRED_STARTUP_STAGES, StartupTimer

        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        tracemalloc.start()
        timer = StartupTimer(started_at=process_started_at, detailed=False)
        with redirect_stdout(StringIO()):
            controller = AppController(app, startup_timer=timer)
            controller.show()
            for _ in range(4):
                app.processEvents()

        snapshot = timer.snapshot()
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        recorded = [row["stage"] for row in snapshot]
        missing = [stage for stage in REQUIRED_STARTUP_STAGES if stage not in recorded]

        print("Daniya startup timing")
        for row in snapshot:
            print(
                f"- {row['stage']}: {row['elapsed_ms']:.2f} ms "
                f"(+{row['delta_ms']:.2f} ms)"
            )
        print(f"- traced_current_mib: {current_bytes / 1024 / 1024:.2f}")
        print(f"- traced_peak_mib: {peak_bytes / 1024 / 1024:.2f}")
        print(f"- optional_services_deferred: {controller._optional_services_initialized}")
        print(f"- missing_stages: {len(missing)}")

        controller.window.close()
        app.processEvents()
        if missing:
            print("Startup timing check failed: missing required stages.")
            return 1
        print("Startup timing check passed.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
