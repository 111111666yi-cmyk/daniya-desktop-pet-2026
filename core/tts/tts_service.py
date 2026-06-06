"""TTSService — single entry point for text-to-speech in the main app."""
from __future__ import annotations

import threading
from enum import Enum
from pathlib import Path
from typing import Any

from .audio_player import AudioPlayer
from .gpt_sovits_adapter import EngineError, GPTSoVITSAdapter
from .voice_asset import VoiceAsset, VoiceAssetError
from .voice_asset_manager import VoiceAssetManager, VoiceStatus


class TTSStatus(str, Enum):
    DISABLED = "disabled"
    NO_VOICE = "no_voice"
    VOICE_ERROR = "voice_error"
    ENGINE_NOT_RUNNING = "engine_not_running"
    READY = "ready"
    ERROR = "error"


_DEFAULT_TEST_TEXT = "……嗯，我在。不是特别想说话，但可以陪你一会儿。"
_MAX_TEXT_LENGTH = 120


class TTSService:
    def __init__(
        self,
        voice_asset_manager: VoiceAssetManager,
        audio_player: AudioPlayer,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.voice_manager = voice_asset_manager
        self.audio_player = audio_player
        self._config = config or {}
        self._adapter: GPTSoVITSAdapter | None = None
        self._current_voice: VoiceAsset | None = None
        self._reload_adapter()

    def _reload_adapter(self) -> None:
        engine = self._config.get("engine", "gpt-sovits")
        if engine == "gpt-sovits":
            base_url = self._config.get("local_api_base_url", "http://127.0.0.1:9880")
            self._adapter = GPTSoVITSAdapter(api_base_url=base_url)

    def update_config(self, config: dict[str, Any]) -> None:
        self._config = config
        self._reload_adapter()

    @property
    def enabled(self) -> bool:
        return bool(self._config.get("enabled", False))

    @property
    def voice_id(self) -> str:
        return str(self._config.get("voice_id", ""))

    @property
    def cache_enabled(self) -> bool:
        return bool(self._config.get("cache_enabled", True))

    def get_status(self) -> TTSStatus:
        if not self.enabled:
            return TTSStatus.DISABLED
        voice = self.voice_manager.get_voice(self.voice_id)
        if voice is None:
            return TTSStatus.NO_VOICE
        errors = voice.full_validate()
        if errors:
            return TTSStatus.VOICE_ERROR
        if self._adapter and not self._adapter.health_check():
            return TTSStatus.ENGINE_NOT_RUNNING
        return TTSStatus.READY

    def synthesize(self, text: str, voice_id: str | None = None) -> Path | None:
        """Synthesize text to wav. Returns path or None on failure."""
        vid = voice_id or self.voice_id
        voice = self.voice_manager.get_voice(vid)
        if voice is None or self._adapter is None:
            return None
        try:
            self._adapter.set_weights(voice)
            return self._adapter.synthesize(text[:_MAX_TEXT_LENGTH], voice, cache_enabled=self.cache_enabled)
        except (EngineError, VoiceAssetError):
            return None

    def play(self, text: str, voice_id: str | None = None) -> None:
        """Synthesize and play in a background thread. Never blocks UI."""
        if not self.enabled or not text.strip():
            return
        vid = voice_id or self.voice_id

        def _worker() -> None:
            try:
                wav = self.synthesize(text, vid)
                if wav and wav.exists():
                    self.audio_player.play_wav(wav)
            except Exception:
                pass  # Fail silently — bubble text is always shown regardless

        threading.Thread(target=_worker, daemon=True).start()

    def test_play(self, voice_id: str | None = None) -> tuple[bool, str]:
        """Synchronous test play. Returns (success, message)."""
        vid = voice_id or self.voice_id
        voice = self.voice_manager.get_voice(vid)
        if voice is None:
            return False, "VOICE_NOT_INSTALLED"
        errors = voice.full_validate()
        if errors:
            return False, f"VOICE_FILE_MISSING: {errors[0]}"
        if self._adapter is None:
            return False, "ENGINE_NOT_CONFIGURED"
        if not self._adapter.health_check():
            return False, "ENGINE_NOT_RUNNING"
        try:
            self._adapter.set_weights(voice)
            wav = self._adapter.synthesize(_DEFAULT_TEST_TEXT, voice, cache_enabled=False)
            self.audio_player.play_wav(wav)
            return True, "TEST_OK"
        except (EngineError, VoiceAssetError) as exc:
            return False, f"SYNTHESIS_FAILED: {exc}"
        except Exception as exc:
            return False, f"AUDIO_PLAYBACK_FAILED: {exc}"

    def clear_cache(self) -> int:
        if self._adapter:
            return self._adapter.clear_cache()
        return 0
