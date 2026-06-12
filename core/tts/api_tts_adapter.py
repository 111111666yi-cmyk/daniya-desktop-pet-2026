"""ApiTTSAdapter — BYOK API TTS with pluggable providers."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import requests

from src.utils import runtime_root


class ApiTTSError(Exception):
    pass


def mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "****"
    return key[:3] + "****" + key[-4:]


class ApiTTSAdapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self._provider = config.get("provider", "custom")
        self._endpoint = config.get("endpoint", "")
        self._api_key = config.get("api_key", "")
        self._voice_id = config.get("voice_id", "")
        self._timeout = int(config.get("timeout_sec", 30))
        self._cache_enabled = bool(config.get("cache_enabled", True))
        self._cache_dir = runtime_root() / "cache" / "tts"

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def voice_id(self) -> str:
        return self._voice_id

    @property
    def masked_key(self) -> str:
        return mask_key(self._api_key)

    def health_check(self) -> bool:
        if not self._endpoint:
            return False
        try:
            resp = requests.get(self._endpoint, timeout=5)
            return resp.status_code < 500
        except Exception:
            return False

    def synthesize(self, text: str) -> Path | None:
        if not self._endpoint:
            raise ApiTTSError("No API endpoint configured.")
        if not text.strip():
            return None

        cache_key = self._make_cache_key(text)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self._cache_dir / f"{cache_key}.wav"
        if self._cache_enabled and cached.exists():
            return cached

        provider = _get_provider(self._provider)
        try:
            audio_bytes = provider.call(
                endpoint=self._endpoint,
                api_key=self._api_key,
                voice_id=self._voice_id,
                text=text,
                timeout=self._timeout,
            )
        except Exception as exc:
            raise ApiTTSError(f"API call failed: {exc}") from exc

        if not audio_bytes:
            raise ApiTTSError("Empty audio response.")

        out = cached if self._cache_enabled else (self._cache_dir / f"api_{int(time.time() * 1000)}.wav")
        out.write_bytes(audio_bytes)
        return out

    def _make_cache_key(self, text: str) -> str:
        raw = f"{self._provider}|{self._endpoint}|{self._voice_id}|{text}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def clear_cache(self) -> int:
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


# ── Provider interface ──

class BaseProvider:
    def call(self, endpoint: str, api_key: str, voice_id: str, text: str, timeout: int) -> bytes:
        raise NotImplementedError


class CustomAPIProvider(BaseProvider):
    def call(self, endpoint: str, api_key: str, voice_id: str, text: str, timeout: int) -> bytes:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"text": text, "voice_id": voice_id}
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            raise ApiTTSError(f"API returned {resp.status_code}")
        return resp.content


class FishAudioProvider(BaseProvider):
    """Placeholder — users supply their own Fish Audio API key."""
    def call(self, endpoint: str, api_key: str, voice_id: str, text: str, timeout: int) -> bytes:
        if not api_key:
            raise ApiTTSError("Fish Audio requires an API key (BYOK).")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"text": text, "reference_id": voice_id}
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            raise ApiTTSError(f"Fish Audio API returned {resp.status_code}")
        return resp.content


class MiniMaxProvider(BaseProvider):
    """Placeholder — users supply their own MiniMax API key."""
    def call(self, endpoint: str, api_key: str, voice_id: str, text: str, timeout: int) -> bytes:
        if not api_key:
            raise ApiTTSError("MiniMax requires an API key (BYOK).")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"text": text, "voice_id": voice_id}
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            raise ApiTTSError(f"MiniMax API returned {resp.status_code}")
        return resp.content


_PROVIDERS: dict[str, BaseProvider] = {
    "custom": CustomAPIProvider(),
    "fish_audio": FishAudioProvider(),
    "minimax": MiniMaxProvider(),
}


def _get_provider(name: str) -> BaseProvider:
    return _PROVIDERS.get(name, _PROVIDERS["custom"])
