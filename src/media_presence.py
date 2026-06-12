from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject, QTimer, Signal

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore


SUPPORTED_PLAYERS = {
    "spotify.exe": "Spotify",
    "cloudmusic.exe": "网易云音乐",
    "qqmusic.exe": "QQ 音乐",
    "foobar2000.exe": "foobar2000",
    "vlc.exe": "VLC",
    "musicbee.exe": "MusicBee",
    "potplayermini64.exe": "PotPlayer",
}


def detect_supported_player(process_names: Iterable[str]) -> str:
    normalized = {str(name).strip().lower() for name in process_names}
    for process_name, display_name in SUPPORTED_PLAYERS.items():
        if process_name in normalized:
            return display_name
    return ""


class MediaPresenceManager(QObject):
    presence_changed = Signal(str)

    def __init__(self, enabled: bool = False, interval_seconds: int = 60) -> None:
        super().__init__()
        self.enabled = bool(enabled)
        self.interval_seconds = max(30, int(interval_seconds))
        self.current_player = ""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_now)
        self.set_enabled(self.enabled)

    def configure(self, interval_seconds: int) -> None:
        self.interval_seconds = max(30, min(3600, int(interval_seconds)))
        if self.timer.isActive():
            self.timer.start(self.interval_seconds * 1000)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if self.enabled:
            self.timer.start(self.interval_seconds * 1000)
        else:
            self.timer.stop()
            self.current_player = ""

    def detect_now(self) -> str:
        if psutil is None:
            return ""
        names: list[str] = []
        try:
            for process in psutil.process_iter(["name"]):
                name = process.info.get("name")
                if name:
                    names.append(str(name))
        except (psutil.Error, OSError):
            return ""
        return detect_supported_player(names)

    def check_now(self) -> str:
        if not self.enabled:
            return ""
        detected = self.detect_now()
        if detected != self.current_player:
            self.current_player = detected
            if detected:
                self.presence_changed.emit(detected)
        return detected
