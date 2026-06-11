from __future__ import annotations

import json
import random
from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from .utils import resource_path


class AmbientEventTheater(QObject):
    event_ready = Signal(object)

    def __init__(
        self,
        character_id: str = "daniya",
        *,
        enabled: bool = False,
        interval_seconds: int = 1800,
        catalog_root: Path | None = None,
        chooser: random.Random | None = None,
    ) -> None:
        super().__init__()
        self.character_id = character_id
        self.enabled = bool(enabled)
        self.interval_seconds = max(900, int(interval_seconds))
        self.catalog_root = catalog_root or resource_path("characters", character_id)
        self.chooser = chooser or random.Random()
        self.events = self._load_events()
        self.last_event_id = ""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.trigger_once)
        self.set_enabled(self.enabled)

    def reload_character(
        self,
        character_id: str,
        catalog_root: Path | None = None,
    ) -> None:
        self.character_id = character_id
        self.catalog_root = catalog_root or resource_path("characters", character_id)
        self.events = self._load_events()
        self.last_event_id = ""

    def configure(self, interval_seconds: int) -> None:
        self.interval_seconds = max(900, min(21600, int(interval_seconds)))
        if self.timer.isActive():
            self.timer.start(self.interval_seconds * 1000)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if self.enabled:
            self.timer.start(self.interval_seconds * 1000)
        else:
            self.timer.stop()

    def trigger_once(self, force: bool = False) -> dict[str, Any] | None:
        if not force and not self.enabled:
            return None
        candidates = [
            event
            for event in self.events
            if str(event.get("id", "")) != self.last_event_id
        ]
        if not candidates:
            candidates = self.events
        if not candidates:
            return None
        event = deepcopy(self.chooser.choice(candidates))
        self.last_event_id = str(event.get("id", ""))
        self.event_ready.emit(event)
        return event

    def _load_events(self) -> list[dict[str, Any]]:
        path = self.catalog_root / "ambient_events.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        events = payload.get("events", []) if isinstance(payload, dict) else []
        if not isinstance(events, list):
            return []
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for event in events:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id", "")).strip()
            text = str(event.get("text", "")).strip()
            action = str(event.get("action", "keep")).strip() or "keep"
            if not event_id or not text or event_id in seen:
                continue
            result.append({"id": event_id, "text": text, "action": action})
            seen.add(event_id)
        return result
