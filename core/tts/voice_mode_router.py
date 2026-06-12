"""VoiceModeRouter — routes pet events to the active voice backend."""
from __future__ import annotations

import threading
from enum import Enum
from typing import Any

from .clip_pack import ClipPackVoiceService


class VoiceMode(str, Enum):
    OFF = "off"
    CLIP_PACK = "clip_pack"
    API_TTS = "api_tts"
    LOCAL_GPT_SOVITS = "local_gpt_sovits"


_EVENT_TO_CATEGORY = {
    "pet_click": "click",
    "pet_drag": "drag",
    "reminder": "reminder",
    "sleep": "sleep",
    "wake": "wake",
    "comfort": "comfort",
    "error": "error",
    "idle": "idle",
}


class VoiceModeRouter:
    def __init__(
        self,
        config: dict[str, Any],
        clip_pack_service: ClipPackVoiceService | None = None,
        tts_service: Any | None = None,
        api_tts_adapter: Any | None = None,
        audio_player: Any | None = None,
    ) -> None:
        self._config = config
        self._clip_pack = clip_pack_service
        self._tts_service = tts_service
        self._api_tts = api_tts_adapter
        self._audio_player = audio_player
        self._load_from_config()

    # ── config helpers ──

    def _voice_cfg(self) -> dict[str, Any]:
        return self._config.get("voice", {})

    def _clip_pack_cfg(self) -> dict[str, Any]:
        return self._voice_cfg().get("clip_pack", {})

    def _api_tts_cfg(self) -> dict[str, Any]:
        return self._voice_cfg().get("api_tts", {})

    def _local_gpt_sovits_cfg(self) -> dict[str, Any]:
        return self._voice_cfg().get("local_gpt_sovits", {})

    # ── lifecycle ──

    def _load_from_config(self) -> None:
        try:
            self._mode = VoiceMode(self._voice_cfg().get("mode", "off"))
        except ValueError:
            self._mode = VoiceMode.OFF
        if self._mode == VoiceMode.CLIP_PACK and self._clip_pack is not None:
            pack_id = self._clip_pack_cfg().get("clip_pack_id", "")
            if pack_id:
                self._clip_pack.load_pack(pack_id)
        if self._mode == VoiceMode.API_TTS:
            self._reload_api_tts()

    def _reload_api_tts(self) -> None:
        from .api_tts_adapter import ApiTTSAdapter
        cfg = self._api_tts_cfg()
        if cfg.get("endpoint"):
            self._api_tts = ApiTTSAdapter(cfg)

    def update_config(self, config: dict[str, Any]) -> None:
        self._config = config
        self._load_from_config()

    @property
    def mode(self) -> VoiceMode:
        return self._mode

    # ── playback ──

    def play_pet_event(self, event_type: str, text: str | None = None) -> None:
        if self._mode == VoiceMode.OFF:
            return
        if self._mode == VoiceMode.CLIP_PACK:
            category = _EVENT_TO_CATEGORY.get(event_type)
            if category and self._clip_pack is not None:
                self._clip_pack.play_category(category)
            return
        if self._mode == VoiceMode.API_TTS:
            if text:
                self._play_api_tts(text)
            return
        if self._mode == VoiceMode.LOCAL_GPT_SOVITS:
            if text and self._tts_service is not None and self._tts_service.enabled:
                self._tts_service.play(text)
            return

    def play_text(self, text: str) -> None:
        if self._mode == VoiceMode.OFF:
            return
        if self._mode == VoiceMode.CLIP_PACK:
            return
        if self._mode == VoiceMode.API_TTS:
            self._play_api_tts(text)
            return
        if self._mode == VoiceMode.LOCAL_GPT_SOVITS:
            if self._tts_service is not None and self._tts_service.enabled:
                self._tts_service.play(text)

    def _play_api_tts(self, text: str) -> None:
        if self._api_tts is None or not text.strip():
            return

        def _worker() -> None:
            try:
                from .api_tts_adapter import ApiTTSError
                wav = self._api_tts.synthesize(text)
                if wav and wav.exists() and self._audio_player is not None:
                    self._audio_player.play_wav(wav)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    # ── test / status ──

    def test_play(self) -> tuple[bool, str]:
        if self._mode == VoiceMode.OFF:
            return False, "VOICE_MODE_OFF"
        if self._mode == VoiceMode.CLIP_PACK:
            if self._clip_pack is None:
                return False, "CLIP_PACK_SERVICE_UNAVAILABLE"
            pack_id = self._clip_pack_cfg().get("clip_pack_id", "")
            return self._clip_pack.test_play(pack_id)
        if self._mode == VoiceMode.API_TTS:
            if self._api_tts is None:
                return False, "API_TTS_NOT_CONFIGURED"
            if not self._api_tts.endpoint:
                return False, "API_TTS_NO_ENDPOINT"
            try:
                wav = self._api_tts.synthesize("test")
                if wav and wav.exists() and self._audio_player is not None:
                    self._audio_player.play_wav(wav)
                    return True, "TEST_OK"
                return False, "API_TTS_NO_AUDIO"
            except Exception as exc:
                return False, f"API_TTS_FAILED: {exc}"
        if self._mode == VoiceMode.LOCAL_GPT_SOVITS:
            if self._tts_service is None:
                return False, "TTS_SERVICE_UNAVAILABLE"
            return self._tts_service.test_play()
        return False, "UNKNOWN_MODE"

    def get_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {"mode": self._mode.value}
        if self._mode == VoiceMode.OFF:
            status["detail"] = "Voice is disabled."
        elif self._mode == VoiceMode.CLIP_PACK:
            pack_id = self._clip_pack_cfg().get("clip_pack_id", "")
            status["clip_pack_id"] = pack_id
            if self._clip_pack is not None:
                ok, errors = self._clip_pack.verify_pack(pack_id)
                status["verified"] = ok
                if errors:
                    status["errors"] = errors
            else:
                status["verified"] = False
        elif self._mode == VoiceMode.API_TTS:
            from .api_tts_adapter import mask_key
            cfg = self._api_tts_cfg()
            status["provider"] = cfg.get("provider", "custom")
            status["endpoint"] = cfg.get("endpoint", "")
            status["key_masked"] = mask_key(cfg.get("api_key", ""))
            status["connected"] = self._api_tts.health_check() if self._api_tts else False
        elif self._mode == VoiceMode.LOCAL_GPT_SOVITS:
            if self._tts_service is not None:
                status["tts_status"] = self._tts_service.get_status().value
            else:
                status["tts_status"] = "unavailable"
        return status
