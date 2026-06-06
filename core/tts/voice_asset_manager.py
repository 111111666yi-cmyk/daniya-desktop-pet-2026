"""VoiceAssetManager — discover, import, validate local voice packs."""
from __future__ import annotations

import json
import os
import shutil
import zipfile
from enum import Enum
from pathlib import Path
from typing import Any

from src.utils import runtime_root

from .voice_asset import (
    ChecksumFailed,
    FileMissing,
    ManifestInvalid,
    ManifestMissing,
    VoiceAsset,
    VoiceAssetError,
)


class VoiceStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED_NOT_VERIFIED = "installed_but_not_verified"
    VERIFIED = "verified"
    CHECKSUM_FAILED = "checksum_failed"
    FILE_MISSING = "file_missing"
    MANIFEST_ERROR = "manifest_error"
    ERROR = "error"


class VoiceAssetManager:
    def __init__(self, voices_dir: Path | None = None) -> None:
        self.voices_dir = voices_dir or (runtime_root() / "assets" / "voices")

    def list_installed_voices(self) -> list[VoiceAsset]:
        """Discover all voice packs under voices_dir."""
        if not self.voices_dir.exists():
            return []
        results: list[VoiceAsset] = []
        for entry in sorted(self.voices_dir.iterdir()):
            if not entry.is_dir():
                continue
            if not (entry / "manifest.json").exists():
                continue
            try:
                results.append(VoiceAsset.load(entry))
            except VoiceAssetError:
                continue
        return results

    def get_voice(self, voice_id: str) -> VoiceAsset | None:
        for voice in self.list_installed_voices():
            if voice.voice_id == voice_id:
                return voice
        return None

    def verify_voice(self, voice_id: str) -> tuple[VoiceStatus, list[str]]:
        voice = self.get_voice(voice_id)
        if voice is None:
            return VoiceStatus.NOT_INSTALLED, ["VOICE_NOT_INSTALLED"]
        errors = voice.full_validate()
        if not errors:
            return VoiceStatus.VERIFIED, []
        for e in errors:
            if "CHECKSUM_FAILED" in e:
                return VoiceStatus.CHECKSUM_FAILED, errors
            if "FILE_MISSING" in e:
                return VoiceStatus.FILE_MISSING, errors
        return VoiceStatus.ERROR, errors

    def import_from_local_zip(self, zip_path: Path) -> VoiceAsset:
        """Import a voice pack from a zip file. Validates after extraction."""
        if not zip_path.exists():
            raise VoiceAssetError(f"Zip file not found: {zip_path}")

        self.voices_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir = self.voices_dir / f"_importing_{os.getpid()}"
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Security: check for path traversal
                for info in zf.infolist():
                    if info.filename.startswith("/") or ".." in info.filename:
                        raise VoiceAssetError(f"Unsafe path in zip: {info.filename}")
                zf.extractall(tmp_dir)

            # Find manifest — might be in a subdirectory
            manifest_candidates = list(tmp_dir.rglob("manifest.json"))
            if not manifest_candidates:
                raise ManifestMissing("No manifest.json found in zip")

            pack_root = manifest_candidates[0].parent
            manifest = json.loads(manifest_candidates[0].read_text(encoding="utf-8"))
            voice_id = str(manifest.get("voice_id", pack_root.name))

            target_dir = self.voices_dir / voice_id
            if target_dir.exists():
                shutil.rmtree(target_dir)

            if pack_root == tmp_dir:
                tmp_dir.rename(target_dir)
            else:
                shutil.move(str(pack_root), str(target_dir))
                shutil.rmtree(tmp_dir, ignore_errors=True)

            voice = VoiceAsset.load(target_dir)
            errors = voice.full_validate()
            if errors:
                raise VoiceAssetError(f"Imported but validation failed: {'; '.join(errors)}")
            return voice

        except VoiceAssetError:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise VoiceAssetError(f"Import failed: {exc}") from exc
