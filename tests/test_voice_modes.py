"""Tests for voice mode router, clip pack service, and remote manifest."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.tts.clip_pack import ClipPackVoiceService
from core.tts.voice_mode_router import VoiceModeRouter, VoiceMode
from core.tts.remote_clip_manifest import fetch_manifest, RemoteManifestError


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
            assert svc.loaded_id == ""

    def test_verify_pack_success(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            ok, errors = svc.verify_pack("test_pack")
            assert ok is True
            assert errors == []

    def test_verify_pack_missing(self, tmp_path: Path) -> None:
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            ok, errors = svc.verify_pack("missing")
            assert ok is False
            assert "CLIP_PACK_NOT_FOUND" in errors

    def test_verify_pack_missing_clip_file(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        (tmp_path / "test_pack" / "click" / "click_001.wav").unlink()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            ok, errors = svc.verify_pack("test_pack")
            assert ok is False
            assert any("CLIP_FILE_MISSING" in e for e in errors)

    def test_play_category_does_not_crash_when_no_pack(self) -> None:
        svc = ClipPackVoiceService()
        svc.play_category("click")

    def test_play_category_does_not_crash_missing_category(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            svc.load_pack("test_pack")
            svc.play_category("nonexistent_category")

    def test_play_category_does_not_crash_missing_file(self, tmp_path: Path) -> None:
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
            svc = ClipPackVoiceService(audio_player=player)
            ok, msg = svc.test_play("test_pack")
            assert ok is True
            assert msg == "TEST_OK"
            player.play_wav.assert_called_once()

    def test_test_play_pack_not_found(self, tmp_path: Path) -> None:
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            svc = ClipPackVoiceService()
            ok, msg = svc.test_play("missing")
            assert ok is False

    def test_list_installed_packs(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            packs = ClipPackVoiceService.list_installed_packs()
            assert "test_pack" in packs

    def test_list_installed_packs_empty(self, tmp_path: Path) -> None:
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            assert ClipPackVoiceService.list_installed_packs() == []


# ── VoiceModeRouter tests ──

class TestVoiceModeRouter:
    def test_off_mode_does_nothing(self) -> None:
        router = VoiceModeRouter(config={"voice": {"mode": "off"}})
        router.play_pet_event("pet_click", "test")
        assert router.mode == VoiceMode.OFF

    def test_clip_pack_mode(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        player = MagicMock()
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            clip_svc = ClipPackVoiceService(audio_player=player)
            config = {"voice": {"mode": "clip_pack", "clip_pack_id": "test_pack"}}
            router = VoiceModeRouter(config=config, clip_pack_service=clip_svc)
            assert router.mode == VoiceMode.CLIP_PACK

    def test_local_gpt_sovits_mode(self) -> None:
        tts = MagicMock()
        tts.enabled = True
        config = {"voice": {"mode": "local_gpt_sovits"}}
        router = VoiceModeRouter(config=config, tts_service=tts)
        assert router.mode == VoiceMode.LOCAL_GPT_SOVITS
        router.play_pet_event("pet_click", "hello")
        tts.play.assert_called_once_with("hello")

    def test_local_gpt_sovits_no_text(self) -> None:
        tts = MagicMock()
        tts.enabled = True
        config = {"voice": {"mode": "local_gpt_sovits"}}
        router = VoiceModeRouter(config=config, tts_service=tts)
        router.play_pet_event("pet_click")
        tts.play.assert_not_called()

    def test_invalid_mode_defaults_to_off(self) -> None:
        router = VoiceModeRouter(config={"voice": {"mode": "invalid_mode"}})
        assert router.mode == VoiceMode.OFF

    def test_get_status_off(self) -> None:
        router = VoiceModeRouter(config={"voice": {"mode": "off"}})
        status = router.get_status()
        assert status["mode"] == "off"

    def test_get_status_clip_pack(self, tmp_path: Path) -> None:
        _create_clip_pack(tmp_path)
        with patch("core.tts.clip_pack._CLIP_PACK_ROOT", tmp_path):
            clip_svc = ClipPackVoiceService()
            config = {"voice": {"mode": "clip_pack", "clip_pack_id": "test_pack"}}
            router = VoiceModeRouter(config=config, clip_pack_service=clip_svc)
            status = router.get_status()
            assert status["mode"] == "clip_pack"
            assert status["verified"] is True

    def test_get_status_gpt_sovits(self) -> None:
        tts = MagicMock()
        from core.tts.tts_service import TTSStatus
        tts.get_status.return_value = TTSStatus.ENGINE_NOT_RUNNING
        config = {"voice": {"mode": "local_gpt_sovits"}}
        router = VoiceModeRouter(config=config, tts_service=tts)
        status = router.get_status()
        assert status["tts_status"] == "engine_not_running"

    def test_test_play_off(self) -> None:
        router = VoiceModeRouter(config={"voice": {"mode": "off"}})
        ok, msg = router.test_play()
        assert ok is False
        assert "OFF" in msg

    def test_update_config(self) -> None:
        router = VoiceModeRouter(config={"voice": {"mode": "off"}})
        assert router.mode == VoiceMode.OFF
        router.update_config({"voice": {"mode": "local_gpt_sovits"}})
        assert router.mode == VoiceMode.LOCAL_GPT_SOVITS

    def test_play_text_off(self) -> None:
        router = VoiceModeRouter(config={"voice": {"mode": "off"}})
        router.play_text("hello")

    def test_play_text_gpt_sovits(self) -> None:
        tts = MagicMock()
        tts.enabled = True
        config = {"voice": {"mode": "local_gpt_sovits"}}
        router = VoiceModeRouter(config=config, tts_service=tts)
        router.play_text("hello")
        tts.play.assert_called_once_with("hello")


# ── Remote manifest tests ──

class TestRemoteManifest:
    def test_valid_manifest(self) -> None:
        manifest = {
            "latest_clip_pack": "test_pack",
            "packs": [
                {
                    "clip_pack_id": "test_pack",
                    "display_name": "Test Pack",
                    "download_url": "https://example.com/packs/test.zip",
                    "sha256_url": "https://example.com/checksums/test.sha256",
                    "size_bytes": 1024,
                    "license_status": "user_responsible",
                }
            ],
        }
        from core.tts.remote_clip_manifest import _validate_manifest
        _validate_manifest(manifest)

    def test_invalid_manifest_no_packs(self) -> None:
        from core.tts.remote_clip_manifest import _validate_manifest
        with pytest.raises(RemoteManifestError, match="packs"):
            _validate_manifest({})

    def test_invalid_manifest_missing_pack_field(self) -> None:
        from core.tts.remote_clip_manifest import _validate_manifest
        with pytest.raises(RemoteManifestError, match="clip_pack_id"):
            _validate_manifest({"packs": [{"download_url": "x"}]})

    def test_fetch_manifest_empty_url(self) -> None:
        with pytest.raises(RemoteManifestError, match="No manifest URL"):
            fetch_manifest("")

    def test_fetch_manifest_unreachable(self) -> None:
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
