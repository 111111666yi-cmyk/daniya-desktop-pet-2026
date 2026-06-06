"""Tests for TTS subsystem: voice asset, manager, service status."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.tts.voice_asset import (
    VoiceAsset,
    ManifestMissing,
    ManifestInvalid,
    FileMissing,
)
from core.tts.voice_asset_manager import VoiceAssetManager, VoiceStatus
from core.tts.tts_service import TTSService, TTSStatus


# ── Helpers ──

def _make_manifest(**overrides: object) -> dict:
    base = {
        "voice_id": "test_voice",
        "display_name": "Test Voice",
        "engine": "gpt-sovits",
        "official": False,
        "user_imported": True,
        "locked": True,
        "gpt_weights": "gpt_model.ckpt",
        "sovits_weights": "sovits_model.pth",
        "ref_audio": "ref_audio.wav",
        "prompt_text_file": "prompt.txt",
        "prompt_lang": "zh",
        "default_text_lang": "zh",
        "default_speed": 1.0,
        "default_seed": 114514,
        "sha256_required": False,
        "license_status": "user_responsible",
    }
    base.update(overrides)
    return base


def _create_voice_pack(root: Path, manifest_overrides: dict | None = None) -> Path:
    """Create a minimal valid voice pack directory."""
    m = _make_manifest(**(manifest_overrides or {}))
    voice_dir = root / m["voice_id"]
    voice_dir.mkdir(parents=True, exist_ok=True)
    (voice_dir / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    (voice_dir / "gpt_model.ckpt").write_bytes(b"fake_gpt")
    (voice_dir / "sovits_model.pth").write_bytes(b"fake_sovits")
    (voice_dir / "ref_audio.wav").write_bytes(b"fake_audio")
    (voice_dir / "prompt.txt").write_text("测试参考文本", encoding="utf-8")
    (voice_dir / "license.txt").write_text("User imported. User responsible for licensing.", encoding="utf-8")
    return voice_dir


# ── VoiceAsset tests ──

def test_voice_asset_load_valid(tmp_path: Path) -> None:
    _create_voice_pack(tmp_path)
    voice = VoiceAsset.load(tmp_path / "test_voice")
    assert voice.voice_id == "test_voice"
    assert voice.engine == "gpt-sovits"
    assert voice.user_imported is True
    assert voice.locked is True


def test_voice_asset_manifest_missing(tmp_path: Path) -> None:
    empty_dir = tmp_path / "no_manifest"
    empty_dir.mkdir()
    with pytest.raises(ManifestMissing):
        VoiceAsset.load(empty_dir)


def test_voice_asset_manifest_missing_field(tmp_path: Path) -> None:
    voice_dir = tmp_path / "bad"
    voice_dir.mkdir()
    (voice_dir / "manifest.json").write_text('{"voice_id": "bad"}', encoding="utf-8")
    with pytest.raises(ManifestInvalid, match="display_name"):
        VoiceAsset.load(voice_dir)


def test_voice_asset_validate_files_all_present(tmp_path: Path) -> None:
    _create_voice_pack(tmp_path)
    voice = VoiceAsset.load(tmp_path / "test_voice")
    assert voice.validate_files() == []


def test_voice_asset_validate_files_missing_weight(tmp_path: Path) -> None:
    _create_voice_pack(tmp_path)
    (tmp_path / "test_voice" / "gpt_model.ckpt").unlink()
    voice = VoiceAsset.load(tmp_path / "test_voice")
    errors = voice.validate_files()
    assert any("gpt_weights" in e for e in errors)


def test_voice_asset_validate_license_missing(tmp_path: Path) -> None:
    _create_voice_pack(tmp_path)
    (tmp_path / "test_voice" / "license.txt").unlink()
    voice = VoiceAsset.load(tmp_path / "test_voice")
    errors = voice.validate_files()
    assert any("LICENSE_MISSING" in e for e in errors)


def test_voice_asset_checksum_pass(tmp_path: Path) -> None:
    _create_voice_pack(tmp_path)
    voice_dir = tmp_path / "test_voice"
    # Create valid checksums
    h = hashlib.sha256((voice_dir / "ref_audio.wav").read_bytes()).hexdigest()
    (voice_dir / "checksums.sha256").write_text(f"{h} ref_audio.wav\n", encoding="utf-8")
    voice = VoiceAsset.load(voice_dir)
    assert voice.verify_checksums() == []


def test_voice_asset_checksum_fail(tmp_path: Path) -> None:
    _create_voice_pack(tmp_path)
    voice_dir = tmp_path / "test_voice"
    (voice_dir / "checksums.sha256").write_text("0000 ref_audio.wav\n", encoding="utf-8")
    voice = VoiceAsset.load(voice_dir)
    errors = voice.verify_checksums()
    assert any("hash mismatch" in e for e in errors)


def test_voice_asset_get_prompt_text(tmp_path: Path) -> None:
    _create_voice_pack(tmp_path)
    voice = VoiceAsset.load(tmp_path / "test_voice")
    assert voice.get_prompt_text() == "测试参考文本"


def test_voice_asset_prompt_missing(tmp_path: Path) -> None:
    _create_voice_pack(tmp_path)
    (tmp_path / "test_voice" / "prompt.txt").unlink()
    voice = VoiceAsset.load(tmp_path / "test_voice")
    with pytest.raises(FileMissing):
        voice.get_prompt_text()


# ── VoiceAssetManager tests ──

def test_manager_list_empty(tmp_path: Path) -> None:
    mgr = VoiceAssetManager(voices_dir=tmp_path / "voices")
    assert mgr.list_installed_voices() == []


def test_manager_list_installed(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    _create_voice_pack(voices_dir)
    mgr = VoiceAssetManager(voices_dir=voices_dir)
    voices = mgr.list_installed_voices()
    assert len(voices) == 1
    assert voices[0].voice_id == "test_voice"


def test_manager_get_voice(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    _create_voice_pack(voices_dir)
    mgr = VoiceAssetManager(voices_dir=voices_dir)
    assert mgr.get_voice("test_voice") is not None
    assert mgr.get_voice("nonexistent") is None


def test_manager_verify_voice_ok(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    _create_voice_pack(voices_dir)
    mgr = VoiceAssetManager(voices_dir=voices_dir)
    status, errors = mgr.verify_voice("test_voice")
    assert status == VoiceStatus.VERIFIED
    assert errors == []


def test_manager_verify_voice_not_installed(tmp_path: Path) -> None:
    mgr = VoiceAssetManager(voices_dir=tmp_path)
    status, errors = mgr.verify_voice("missing")
    assert status == VoiceStatus.NOT_INSTALLED


def test_manager_verify_voice_file_missing(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    _create_voice_pack(voices_dir)
    (voices_dir / "test_voice" / "sovits_model.pth").unlink()
    mgr = VoiceAssetManager(voices_dir=voices_dir)
    status, errors = mgr.verify_voice("test_voice")
    assert status == VoiceStatus.FILE_MISSING


# ── TTSService status tests ──

def test_tts_service_disabled(tmp_path: Path) -> None:
    mgr = VoiceAssetManager(voices_dir=tmp_path)
    player = MagicMock()
    svc = TTSService(mgr, player, {"enabled": False})
    assert svc.get_status() == TTSStatus.DISABLED


def test_tts_service_no_voice(tmp_path: Path) -> None:
    mgr = VoiceAssetManager(voices_dir=tmp_path)
    player = MagicMock()
    svc = TTSService(mgr, player, {"enabled": True, "voice_id": "missing"})
    assert svc.get_status() == TTSStatus.NO_VOICE


def test_tts_service_engine_not_running(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    _create_voice_pack(voices_dir)
    mgr = VoiceAssetManager(voices_dir=voices_dir)
    player = MagicMock()
    svc = TTSService(mgr, player, {"enabled": True, "voice_id": "test_voice"})
    # GPT-SoVITS not running → health_check fails
    assert svc.get_status() == TTSStatus.ENGINE_NOT_RUNNING


def test_tts_service_play_does_not_crash_when_disabled(tmp_path: Path) -> None:
    mgr = VoiceAssetManager(voices_dir=tmp_path)
    player = MagicMock()
    svc = TTSService(mgr, player, {"enabled": False})
    svc.play("test text")  # Should not raise


def test_tts_service_play_does_not_crash_with_empty_text(tmp_path: Path) -> None:
    voices_dir = tmp_path / "voices"
    _create_voice_pack(voices_dir)
    mgr = VoiceAssetManager(voices_dir=voices_dir)
    player = MagicMock()
    svc = TTSService(mgr, player, {"enabled": True, "voice_id": "test_voice"})
    svc.play("")  # Should not raise
    svc.play("   ")  # Should not raise


# ── Settings TTS state tests ──

def test_settings_tts_not_available_without_voice() -> None:
    """When no voice is installed, status should be NO_VOICE."""
    mgr = VoiceAssetManager(voices_dir=Path("/nonexistent"))
    player = MagicMock()
    svc = TTSService(mgr, player, {"enabled": True, "voice_id": "daniya_voice_v1"})
    assert svc.get_status() == TTSStatus.NO_VOICE
