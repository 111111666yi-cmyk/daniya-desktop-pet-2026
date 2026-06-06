"""VoiceAsset — represents a single local voice pack."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class VoiceAssetError(Exception):
    """Base error for voice asset operations."""


class ManifestMissing(VoiceAssetError):
    pass


class ManifestInvalid(VoiceAssetError):
    pass


class FileMissing(VoiceAssetError):
    pass


class ChecksumFailed(VoiceAssetError):
    pass


class LicenseMissing(VoiceAssetError):
    pass


_REQUIRED_MANIFEST_KEYS = ("voice_id", "display_name", "engine", "gpt_weights", "sovits_weights", "ref_audio", "prompt_text_file")
_REQUIRED_FILES = ("gpt_weights", "sovits_weights", "ref_audio", "prompt_text_file")


@dataclass
class VoiceAsset:
    voice_id: str
    display_name: str
    engine: str
    official: bool
    user_imported: bool
    locked: bool
    root_dir: Path
    manifest: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, root_dir: Path) -> "VoiceAsset":
        manifest_path = root_dir / "manifest.json"
        if not manifest_path.exists():
            raise ManifestMissing(f"manifest.json not found in {root_dir}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ManifestInvalid(f"Cannot parse manifest.json: {exc}") from exc

        for key in _REQUIRED_MANIFEST_KEYS:
            if key not in manifest:
                raise ManifestInvalid(f"Missing required field '{key}' in manifest.json")

        return cls(
            voice_id=str(manifest["voice_id"]),
            display_name=str(manifest.get("display_name", manifest["voice_id"])),
            engine=str(manifest.get("engine", "gpt-sovits")),
            official=bool(manifest.get("official", False)),
            user_imported=bool(manifest.get("user_imported", True)),
            locked=bool(manifest.get("locked", True)),
            root_dir=root_dir,
            manifest=manifest,
        )

    # ── file access ──

    def get_gpt_weights_path(self) -> Path:
        return self.root_dir / self.manifest["gpt_weights"]

    def get_sovits_weights_path(self) -> Path:
        return self.root_dir / self.manifest["sovits_weights"]

    def get_ref_audio_path(self) -> Path:
        return self.root_dir / self.manifest["ref_audio"]

    def get_prompt_text(self) -> str:
        path = self.root_dir / self.manifest["prompt_text_file"]
        if not path.exists():
            raise FileMissing(f"prompt text file missing: {path.name}")
        return path.read_text(encoding="utf-8").strip()

    # ── validation ──

    def validate_files(self) -> list[str]:
        """Return list of error messages. Empty means all OK."""
        errors: list[str] = []
        for key in _REQUIRED_FILES:
            filename = self.manifest.get(key, "")
            if not filename or not (self.root_dir / filename).exists():
                errors.append(f"VOICE_FILE_MISSING: {key} ({filename})")
        if not (self.root_dir / "license.txt").exists():
            errors.append("VOICE_LICENSE_MISSING: license.txt")
        return errors

    def verify_checksums(self) -> list[str]:
        """Verify sha256 checksums. Return list of errors."""
        checksum_path = self.root_dir / "checksums.sha256"
        if not checksum_path.exists():
            if self.manifest.get("sha256_required", False):
                return ["VOICE_CHECKSUM_FAILED: checksums.sha256 missing but required"]
            return []

        errors: list[str] = []
        for line in checksum_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            expected_hash, filename = parts
            filepath = self.root_dir / filename.strip()
            if not filepath.exists():
                errors.append(f"VOICE_CHECKSUM_FAILED: {filename} missing")
                continue
            actual_hash = _sha256(filepath)
            if actual_hash != expected_hash.lower():
                errors.append(f"VOICE_CHECKSUM_FAILED: {filename} hash mismatch")
        return errors

    def full_validate(self) -> list[str]:
        """Run all validations, return combined errors."""
        return self.validate_files() + self.verify_checksums()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
