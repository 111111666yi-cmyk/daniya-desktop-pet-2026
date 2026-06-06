"""GPT-SoVITS API adapter — connect to local GPT-SoVITS inference server."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import requests

from src.utils import runtime_root

from .voice_asset import VoiceAsset


class EngineError(Exception):
    pass


class GPTSoVITSAdapter:
    def __init__(self, api_base_url: str = "http://127.0.0.1:9880") -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self._cache_dir = runtime_root() / "cache" / "tts"

    def health_check(self, timeout: int = 5) -> bool:
        """Check if the GPT-SoVITS API server is running."""
        try:
            resp = requests.get(f"{self.api_base_url}/", timeout=timeout)
            return resp.status_code < 500
        except Exception:
            return False

    def set_weights(self, voice: VoiceAsset, timeout: int = 30) -> None:
        """Tell the server to load specific GPT and SoVITS weights."""
        gpt_path = str(voice.get_gpt_weights_path())
        sovits_path = str(voice.get_sovits_weights_path())

        try:
            resp = requests.get(
                f"{self.api_base_url}/set_gpt_weights",
                params={"weights_path": gpt_path},
                timeout=timeout,
            )
            if resp.status_code != 200:
                raise EngineError(f"Failed to set GPT weights: {resp.status_code}")
        except requests.RequestException as exc:
            raise EngineError(f"Failed to set GPT weights: {exc}") from exc

        try:
            resp = requests.get(
                f"{self.api_base_url}/set_sovits_weights",
                params={"weights_path": sovits_path},
                timeout=timeout,
            )
            if resp.status_code != 200:
                raise EngineError(f"Failed to set SoVITS weights: {resp.status_code}")
        except requests.RequestException as exc:
            raise EngineError(f"Failed to set SoVITS weights: {exc}") from exc

    def synthesize(self, text: str, voice: VoiceAsset, cache_enabled: bool = True) -> Path:
        """Synthesize speech and return path to wav file."""
        ref_audio_path = str(voice.get_ref_audio_path())
        prompt_text = voice.get_prompt_text()

        payload: dict[str, Any] = {
            "text": text,
            "text_lang": voice.manifest.get("default_text_lang", "zh"),
            "ref_audio_path": ref_audio_path,
            "prompt_text": prompt_text,
            "prompt_lang": voice.manifest.get("prompt_lang", "zh"),
            "speed_factor": voice.manifest.get("default_speed", 1.0),
            "seed": voice.manifest.get("default_seed", 114514),
            "streaming_mode": voice.manifest.get("streaming_mode", False),
        }

        # Check cache
        cache_key = _cache_key(voice.voice_id, text, payload)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cached_path = self._cache_dir / f"{cache_key}.wav"
        if cache_enabled and cached_path.exists():
            return cached_path

        try:
            resp = requests.post(
                f"{self.api_base_url}/tts",
                json=payload,
                timeout=60,
            )
            if resp.status_code != 200:
                raise EngineError(f"SYNTHESIS_FAILED: API returned {resp.status_code}")
            if not resp.content:
                raise EngineError("SYNTHESIS_FAILED: Empty response")
        except requests.RequestException as exc:
            raise EngineError(f"SYNTHESIS_FAILED: {exc}") from exc

        output_path = cached_path if cache_enabled else (self._cache_dir / f"tts_{int(time.time() * 1000)}.wav")
        output_path.write_bytes(resp.content)
        return output_path

    def clear_cache(self) -> int:
        """Remove cached wav files. Returns count of files removed."""
        if not self._cache_dir.exists():
            return 0
        count = 0
        for f in self._cache_dir.glob("*.wav"):
            try:
                f.unlink()
                count += 1
            except OSError:
                pass
        return count


def _cache_key(voice_id: str, text: str, payload: dict[str, Any]) -> str:
    raw = f"{voice_id}|{text}|{payload.get('speed_factor')}|{payload.get('seed')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
