from __future__ import annotations

import logging
import os
from time import perf_counter
from typing import Any


REQUIRED_STARTUP_STAGES = (
    "process start",
    "QApplication created",
    "runtime root resolved",
    "config loaded",
    "managers initialized",
    "character pack loaded",
    "main window created",
    "first show",
    "optional services initialized",
)


class StartupTimer:
    def __init__(self, started_at: float | None = None, detailed: bool | None = None) -> None:
        self.started_at = perf_counter() if started_at is None else float(started_at)
        self.detailed = (
            os.environ.get("DANIYA_STARTUP_TIMING", "").strip() == "1"
            if detailed is None
            else bool(detailed)
        )
        self._marks: dict[str, float] = {"process start": self.started_at}

    def mark(self, stage: str, timestamp: float | None = None) -> None:
        if stage not in REQUIRED_STARTUP_STAGES or stage in self._marks:
            return
        try:
            value = perf_counter() if timestamp is None else float(timestamp)
            self._marks[stage] = max(self.started_at, value)
            logger = logging.getLogger("daniya.startup")
            log = logger.info if self.detailed else logger.debug
            log("startup_stage stage=%s elapsed_ms=%.2f", stage, self.elapsed_ms(stage))
        except Exception:
            return

    def elapsed_ms(self, stage: str) -> float:
        value = self._marks.get(stage, self.started_at)
        return max(0.0, (value - self.started_at) * 1000.0)

    def snapshot(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        previous = self.started_at
        for stage in REQUIRED_STARTUP_STAGES:
            if stage not in self._marks:
                continue
            current = self._marks[stage]
            rows.append(
                {
                    "stage": stage,
                    "elapsed_ms": round(max(0.0, (current - self.started_at) * 1000.0), 2),
                    "delta_ms": round(max(0.0, (current - previous) * 1000.0), 2),
                }
            )
            previous = current
        return rows

    def format_summary(self) -> str:
        lines = ["冷启动阶段耗时："]
        lines.extend(
            f"- {row['stage']}: {row['elapsed_ms']:.2f} ms (+{row['delta_ms']:.2f} ms)"
            for row in self.snapshot()
        )
        return "\n".join(lines)
