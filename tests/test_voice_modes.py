"""Tests for voice mode router, clip pack, API TTS adapter, and remote manifest."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.tts.clip_pack import ClipPackVoiceService
from core.tts.voice_mode_router import VoiceModeRouter, VoiceMode
from core.tts.remote_clip_manifest import fetch_manifest, RemoteManifestError
from core.tts.api_tts_adapter import ApiTTSAdapter, ApiTTSError, mask_key


# ── Helpers ──

def _make_clip_manifest(**overrides: object) -> dict:
    base = {
        "clip_pack_id": "test_pack",
        "display_name": "Test Clip Pack",
        "engine": "clip-pack",
        "official": False,
        "user_imported": True,
        "license_status": "user_responsible",
        "default_volume": 70,
        "categories": {
            "click": ["click_001.wav"],
            "idle": ["idle_001.wav"],
        },
        "fallback": {
            "missing_category": "silent",
            "missing_file": "silent",
        },
    }
    base.update(overrides)
    return base


def _create_clip_pack(root: Path, manifest_overrides: dict | None = None) -> Path:
    m = _make_clip_manifest(**(manifest_overrides or {}))
    pack_dir = root / m["clip_pack_id"]
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    for cat, files in m["categories"].items():
        cat_dir = pack_dir / cat
        cat_dir.mkdir(exist_ok=True)
        for fname in files:
            (cat_dir / fname).write_bytes(b"RIFF" + b"\x00" * 40)
    return pack_dir


def _isolated_config(mode: str = "off", **overrides: object) -> dict:
    cfg: dict = {
        "voice": {
            "mode": mode,
            "clip_pack": {"clip_pack_id": "test_pack", "volume": 70},
            "api_tts": {"provider": "custom", "endpoint": "", "api_key": "", "voice_id": "", "timeout_sec": 30, "cache_enabled": True, "volume": 70},
            "local_gpt_sovits": {"voice_id": "test_voice", "api_base_url": "http://127.0.0.1:9880", "volume": 70, "cache_enabled": True},
        }
    }
    for k, v in overrides.items():
        parts = k.split(".")
        d = cfg
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = v
    return cfg


# ── ClipPackVoiceService tests ──

class TestClipPackVoiceService:
    def test_load_pack_success(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            assert svc.load_pack("test_pack") is True
            assert svc.loaded_id == "test_pack"

    def test_load_pack_not_found(self, tmp_path: Path) -> None:
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            assert svc.load_pack("nonexistent") is False

    def test_verify_pack_success(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            ok, errors = ClipPackVoiceService().verify_pack("test_pack")
            assert ok is True and errors == []

    def test_verify_pack_missing(self, tmp_path: Path) -> None:
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            ok, errors = ClipPackVoiceService().verify_pack("missing")
            assert ok is False and "CLIP_PACK_NOT_FOUND" in errors

    def test_verify_pack_missing_clip_file(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        (tmp_path / "test_pack" / "click" / "click_001.wav").unlink()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            ok, errors = ClipPackVoiceService().verify_pack("test_pack")
            assert ok is False and any("CLIP_FILE_MISSING" in e for e in errors)

    def test_play_category_no_crash_when_no_pack(self) -> None:
        ClipPackVoiceService().play_category("click")

    def test_play_category_no_crash_missing_category(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            svc.load_pack("test_pack")
            svc.play_category("nonexistent")

    def test_play_category_no_crash_missing_file(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        (tmp_path / "test_pack" / "click" / "click_001.wav").unlink()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            svc.load_pack("test_pack")
            svc.play_category("click")

    def test_test_play_success(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        player = MagicMock()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            ok, msg = ClipPackVoiceService(audio_player=player).test_play("test_pack")
            assert ok is True and msg == "TEST_OK"
            player.play_wav.assert_called_once()

    def test_list_installed_packs(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            assert "test_pack" in ClipPackVoiceService.list_installed_packs()


# ── VoiceModeRouter tests ──

class TestVoiceModeRouter:
    def test_off_mode_does_nothing(self) -> None:
        router = VoiceModeRouter(config=_isolated_config("off"))
        router.play_pet_event("pet_click", "test")
        router.play_text("test")
        assert router.mode == VoiceMode.OFF

    def test_clip_pack_mode_plays_clip(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        player = MagicMock()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService(audio_player=player)
            router = VoiceModeRouter(config=_isolated_config("clip_pack"), clip_pack_service=svc)
            assert router.mode == VoiceMode.CLIP_PACK

    def test_clip_pack_never_calls_api_tts(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        api_tts = MagicMock()
        tts = MagicMock()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            router = VoiceModeRouter(config=_isolated_config("clip_pack"), clip_pack_service=svc, tts_service=tts, api_tts_adapter=api_tts)
            router.play_pet_event("pet_click", "hello")
            router.play_text("hello")
            api_tts.synthesize.assert_not_called()
            tts.play.assert_not_called()

    def test_clip_pack_never_calls_local_gpt_sovits(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        tts = MagicMock()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            router = VoiceModeRouter(config=_isolated_config("clip_pack"), clip_pack_service=svc, tts_service=tts)
            router.play_pet_event("pet_click", "text")
            tts.play.assert_not_called()

    def test_api_tts_mode(self) -> None:
        api_tts = MagicMock()
        api_tts.endpoint = "http://test"
        api_tts.synthesize.return_value = Path("/tmp/test.wav")
        config = _isolated_config("api_tts")
        config["voice"]["api_tts"]["endpoint"] = "http://test"
        router = VoiceModeRouter(config=config, api_tts_adapter=api_tts, audio_player=MagicMock())
        assert router.mode == VoiceMode.API_TTS

    def test_api_tts_never_calls_local_gpt_sovits(self) -> None:
        tts = MagicMock()
        config = _isolated_config("api_tts")
        router = VoiceModeRouter(config=config, tts_service=tts)
        router.play_pet_event("pet_click", "hello")
        router.play_text("hello")
        tts.play.assert_not_called()

    def test_api_tts_never_calls_clip_pack(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            clip = ClipPackVoiceService(audio_player=MagicMock())
            clip.load_pack("test_pack")
            clip_player = clip._audio_player
            config = _isolated_config("api_tts")
            router = VoiceModeRouter(config=config, clip_pack_service=clip)
            router.play_pet_event("pet_click", "hello")
            clip_player.play_wav.assert_not_called()

    def test_local_gpt_sovits_mode(self) -> None:
        tts = MagicMock()
        tts.enabled = True
        router = VoiceModeRouter(config=_isolated_config("local_gpt_sovits"), tts_service=tts)
        assert router.mode == VoiceMode.LOCAL_GPT_SOVITS
        router.play_pet_event("pet_click", "hello")
        tts.play.assert_called_once_with("hello")

    def test_local_gpt_sovits_never_calls_api_tts(self) -> None:
        api_tts = MagicMock()
        tts = MagicMock(); tts.enabled = True
        router = VoiceModeRouter(config=_isolated_config("local_gpt_sovits"), tts_service=tts, api_tts_adapter=api_tts)
        router.play_pet_event("pet_click", "hello")
        api_tts.synthesize.assert_not_called()

    def test_local_gpt_sovits_never_calls_clip_pack(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            clip = ClipPackVoiceService(audio_player=MagicMock())
            clip.load_pack("test_pack")
            clip_player = clip._audio_player
            tts = MagicMock(); tts.enabled = True
            router = VoiceModeRouter(config=_isolated_config("local_gpt_sovits"), tts_service=tts, clip_pack_service=clip)
            router.play_pet_event("pet_click", "hello")
            clip_player.play_wav.assert_not_called()

    def test_invalid_mode_defaults_to_off(self) -> None:
        router = VoiceModeRouter(config={"voice": {"mode": "invalid"}})
        assert router.mode == VoiceMode.OFF

    def test_get_status_api_tts(self) -> None:
        config = _isolated_config("api_tts")
        config["voice"]["api_tts"]["endpoint"] = "http://test"
        config["voice"]["api_tts"]["api_key"] = "sk-testkey1234"
        router = VoiceModeRouter(config=config)
        status = router.get_status()
        assert status["mode"] == "api_tts"
        assert "****" in status["key_masked"]
        assert "testkey1234" not in status["key_masked"]

    def test_update_config_preserves_mode_switch(self) -> None:
        config = _isolated_config("off")
        router = VoiceModeRouter(config=config)
        assert router.mode == VoiceMode.OFF
        config["voice"]["mode"] = "clip_pack"
        router.update_config(config)
        assert router.mode == VoiceMode.CLIP_PACK

    def test_test_play_off(self) -> None:
        ok, msg = VoiceModeRouter(config=_isolated_config("off")).test_play()
        assert ok is False and "OFF" in msg

    def test_play_text_clip_pack_is_noop(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        player = MagicMock()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService(audio_player=player)
            router = VoiceModeRouter(config=_isolated_config("clip_pack"), clip_pack_service=svc)
            router.play_text("hello")
            player.play_wav.assert_not_called()


# ── Config namespace isolation tests ──

class TestConfigIsolation:
    def test_config_namespaces_exist(self) -> None:
        cfg = _isolated_config("off")
        voice = cfg["voice"]
        assert "clip_pack" in voice
        assert "api_tts" in voice
        assert "local_gpt_sovits" in voice

    def test_switching_modes_preserves_other_configs(self) -> None:
        cfg = _isolated_config("clip_pack")
        cfg["voice"]["api_tts"]["endpoint"] = "http://saved-endpoint"
        cfg["voice"]["api_tts"]["api_key"] = "sk-saved"
        cfg["voice"]["local_gpt_sovits"]["voice_id"] = "saved_voice"
        router = VoiceModeRouter(config=cfg)
        cfg["voice"]["mode"] = "api_tts"
        router.update_config(cfg)
        assert cfg["voice"]["clip_pack"]["clip_pack_id"] == "test_pack"
        assert cfg["voice"]["local_gpt_sovits"]["voice_id"] == "saved_voice"
        cfg["voice"]["mode"] = "off"
        router.update_config(cfg)
        assert cfg["voice"]["api_tts"]["endpoint"] == "http://saved-endpoint"
        assert cfg["voice"]["api_tts"]["api_key"] == "sk-saved"

    def test_missing_namespace_fails_gracefully(self) -> None:
        router = VoiceModeRouter(config={"voice": {"mode": "clip_pack"}})
        assert router.mode == VoiceMode.CLIP_PACK
        status = router.get_status()
        assert "mode" in status


# ── ApiTTSAdapter tests ──

class TestApiTTSAdapter:
    def test_missing_endpoint_fails_gracefully(self) -> None:
        adapter = ApiTTSAdapter({"provider": "custom", "endpoint": "", "api_key": "", "voice_id": ""})
        with pytest.raises(ApiTTSError, match="No API endpoint"):
            adapter.synthesize("hello")

    def test_missing_key_fish_audio_fails(self) -> None:
        from core.tts.api_tts_adapter import FishAudioProvider
        with pytest.raises(ApiTTSError, match="API key"):
            FishAudioProvider().call("http://x", "", "v1", "test", 10)

    def test_missing_key_minimax_fails(self) -> None:
        from core.tts.api_tts_adapter import MiniMaxProvider
        with pytest.raises(ApiTTSError, match="API key"):
            MiniMaxProvider().call("http://x", "", "v1", "test", 10)

    def test_health_check_no_endpoint(self) -> None:
        adapter = ApiTTSAdapter({"endpoint": ""})
        assert adapter.health_check() is False

    def test_masked_key(self) -> None:
        adapter = ApiTTSAdapter({"endpoint": "http://x", "api_key": "sk-abcdefgh1234"})
        masked = adapter.masked_key
        assert "abcdefgh" not in masked
        assert "****" in masked
        assert masked.startswith("sk-")
        assert masked.endswith("1234")

    def test_api_key_not_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        key = "sk-supersecretkey99"
        adapter = ApiTTSAdapter({"endpoint": "http://127.0.0.1:1/tts", "api_key": key})
        with caplog.at_level(logging.DEBUG):
            try:
                adapter.synthesize("test")
            except ApiTTSError:
                pass
        assert key not in caplog.text


# ── API key masking tests ──

class TestMaskKey:
    def test_mask_normal(self) -> None:
        assert mask_key("sk-abcdefgh1234") == "sk-****1234"

    def test_mask_short(self) -> None:
        assert mask_key("short") == "****"

    def test_mask_empty(self) -> None:
        assert mask_key("") == "****"


# ── Remote manifest tests ──

class TestRemoteManifest:
    def test_valid_manifest(self) -> None:
        from core.tts.remote_clip_manifest import _validate_manifest
        _validate_manifest({
            "latest_clip_pack": "test",
            "packs": [{"clip_pack_id": "test", "download_url": "https://example.com/test.zip"}],
        })

    def test_invalid_manifest_no_packs(self) -> None:
        from core.tts.remote_clip_manifest import _validate_manifest
        with pytest.raises(RemoteManifestError, match="packs"):
            _validate_manifest({})

    def test_invalid_manifest_missing_field(self) -> None:
        from core.tts.remote_clip_manifest import _validate_manifest
        with pytest.raises(RemoteManifestError, match="clip_pack_id"):
            _validate_manifest({"packs": [{"download_url": "x"}]})

    def test_fetch_empty_url(self) -> None:
        with pytest.raises(RemoteManifestError, match="No manifest URL"):
            fetch_manifest("")

    def test_fetch_unreachable(self) -> None:
        with pytest.raises(RemoteManifestError):
            fetch_manifest("http://127.0.0.1:1/nonexistent")


# ── Safety tests ──

class TestSafety:
    def test_no_voice_model_files_staged(self) -> None:
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        staged = result.stdout.strip().splitlines()
        forbidden_exts = {".ckpt", ".pth", ".wav", ".mp3", ".ogg", ".flac"}
        forbidden_dirs = {"assets/voices/", "assets/voice_clips/", "cache/tts/", "models/"}
        for f in staged:
            ext = Path(f).suffix.lower()
            assert ext not in forbidden_exts, f"Model/audio file staged: {f}"
            for d in forbidden_dirs:
                assert not f.startswith(d), f"File in forbidden dir staged: {f}"
