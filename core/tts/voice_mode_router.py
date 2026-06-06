"""VoiceModeRouter — routes pet events to the active voice backend."""
from __future__ import annotations

from enum import Enum
from typing import Any

from .clip_pack import ClipPackVoiceService


class VoiceMode(str, Enum):
    OFF = "off"
    CLIP_PACK = "clip_pack"
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
    ) -> None:
        self._config = config
        self._clip_pack = clip_pack_service
        self._tts_service = tts_service
        self._load_from_config()

    def _load_from_config(self) -> None:
        voice_cfg = self._config.get("voice", {})
        try:
            self._mode = VoiceMode(voice_cfg.get("mode", "off"))
        except ValueError:
            self._mode = VoiceMode.OFF
        if self._mode == VoiceMode.CLIP_PACK and self._clip_pack is not None:
            pack_id = voice_cfg.get("clip_pack_id", "")
            if pack_id:
                self._clip_pack.load_pack(pack_id)

    def update_config(self, config: dict[str, Any]) -> None:
        self._config = config
        self._load_from_config()

    @property
    def mode(self) -> VoiceMode:
        return self._mode

    def play_pet_event(self, event_type: str, text: str | None = None) -> None:
        if self._mode == VoiceMode.OFF:
            return
        if self._mode == VoiceMode.CLIP_PACK:
            category = _EVENT_TO_CATEGORY.get(event_type)
            if category and self._clip_pack is not None:
                self._clip_pack.play_category(category)
            return
        if self._mode == VoiceMode.LOCAL_GPT_SOVITS:
            if text and self._tts_service is not None and self._tts_service.enabled:
                self._tts_service.play(text)
            return

    def play_text(self, text: str) -> None:
        if self._mode == VoiceMode.OFF:
            return
        if self._mode == VoiceMode.LOCAL_GPT_SOVITS:
            if self._tts_service is not None and self._tts_service.enabled:
                self._tts_service.play(text)

    def test_play(self) -> tuple[bool, str]:
        if self._mode == VoiceMode.OFF:
            return False, "VOICE_MODE_OFF"
        if self._mode == VoiceMode.CLIP_PACK:
            if self._clip_pack is None:
                return False, "CLIP_PACK_SERVICE_UNAVAILABLE"
            voice_cfg = self._config.get("voice", {})
            pack_id = voice_cfg.get("clip_pack_id", "")
            return self._clip_pack.test_play(pack_id)
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
            voice_cfg = self._config.get("voice", {})
            pack_id = voice_cfg.get("clip_pack_id", "")
            status["clip_pack_id"] = pack_id
            if self._clip_pack is not None:
                ok, errors = self._clip_pack.verify_pack(pack_id)
                status["verified"] = ok
                if errors:
                    status["errors"] = errors
            else:
                status["verified"] = False
        elif self._mode == VoiceMode.LOCAL_GPT_SOVITS:
            if self._tts_service is not None:
                status["tts_status"] = self._tts_service.get_status().value
            else:
                status["tts_status"] = "unavailable"
        return status
