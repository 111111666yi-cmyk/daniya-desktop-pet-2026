"""ClipPackVoiceService — play pre-generated voice clips by category."""
from __future__ import annotations

import json
import random
import threading
from pathlib import Path
from typing import Any

_CLIP_PACK_ROOT = Path(__file__).resolve().parents[2] / "assets" / "voice_clips"

_VALID_CATEGORIES = frozenset([
    "click", "drag", "reminder", "sleep", "wake", "comfort", "error", "idle",
])


class ClipPackError(Exception):
    pass


class ClipPackVoiceService:
    def __init__(self, audio_player: Any = None) -> None:
        self._audio_player = audio_player
        self._manifest: dict[str, Any] = {}
        self._pack_root: Path | None = None
        self._loaded_id: str = ""

    def load_pack(self, clip_pack_id: str) -> bool:
        manifest_path = _CLIP_PACK_ROOT / clip_pack_id / "manifest.json"
        if not manifest_path.exists():
            self._manifest = {}
            self._pack_root = None
            self._loaded_id = ""
            return False
        try:
            self._manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._pack_root = manifest_path.parent
            self._loaded_id = clip_pack_id
            return True
        except (json.JSONDecodeError, OSError):
            self._manifest = {}
            self._pack_root = None
            self._loaded_id = ""
            return False

    def verify_pack(self, clip_pack_id: str) -> tuple[bool, list[str]]:
        pack_dir = _CLIP_PACK_ROOT / clip_pack_id
        errors: list[str] = []
        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.exists():
            return False, ["CLIP_PACK_NOT_FOUND"]
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return False, [f"MANIFEST_INVALID: {exc}"]

        for key in ("clip_pack_id", "display_name", "engine", "categories"):
            if key not in manifest:
                errors.append(f"MANIFEST_MISSING_FIELD: {key}")
        if errors:
            return False, errors

        categories = manifest.get("categories", {})
        for cat_name, files in categories.items():
            cat_dir = pack_dir / cat_name
            if not cat_dir.is_dir():
                errors.append(f"CATEGORY_DIR_MISSING: {cat_name}")
                continue
            for fname in files:
                if not (cat_dir / fname).exists():
                    errors.append(f"CLIP_FILE_MISSING: {cat_name}/{fname}")
        return len(errors) == 0, errors

    def play_category(self, category: str) -> None:
        if not self._pack_root or not self._manifest:
            return
        fallback = self._manifest.get("fallback", {})
        categories = self._manifest.get("categories", {})
        clips = categories.get(category, [])
        if not clips:
            if fallback.get("missing_category") == "silent":
                return
            return
        chosen = random.choice(clips)
        clip_path = self._pack_root / category / chosen
        if not clip_path.exists():
            if fallback.get("missing_file") == "silent":
                return
            return
        if self._audio_player is not None:
            threading.Thread(
                target=self._audio_player.play_wav,
                args=(clip_path,),
                daemon=True,
            ).start()

    def test_play(self, clip_pack_id: str) -> tuple[bool, str]:
        if not self.load_pack(clip_pack_id):
            return False, "CLIP_PACK_NOT_FOUND"
        ok, errors = self.verify_pack(clip_pack_id)
        if not ok:
            return False, f"VERIFY_FAILED: {errors[0]}"
        categories = self._manifest.get("categories", {})
        for cat, clips in categories.items():
            if clips:
                clip_path = self._pack_root / cat / clips[0]
                if clip_path.exists() and self._audio_player is not None:
                    self._audio_player.play_wav(clip_path)
                    return True, "TEST_OK"
        return False, "NO_CLIPS_AVAILABLE"

    @property
    def loaded_id(self) -> str:
        return self._loaded_id

    @staticmethod
    def list_installed_packs() -> list[str]:
        if not _CLIP_PACK_ROOT.is_dir():
            return []
        return [
            d.name for d in sorted(_CLIP_PACK_ROOT.iterdir())
            if d.is_dir() and (d / "manifest.json").exists()
        ]
