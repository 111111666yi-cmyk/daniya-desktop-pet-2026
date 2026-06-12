"""AudioPlayer — async wav playback using Qt multimedia."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class AudioPlayer(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._volume = 70
        self._audio_output.setVolume(self._volume / 100.0)

    def play_wav(self, path: Path) -> None:
        """Play a wav file. Stops any current playback first."""
        if not path.exists():
            return
        self.stop_current()
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()

    def stop_current(self) -> None:
        if self._player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self._player.stop()

    def set_volume(self, volume: int) -> None:
        self._volume = max(0, min(100, volume))
        self._audio_output.setVolume(self._volume / 100.0)

    @property
    def volume(self) -> int:
        return self._volume

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
