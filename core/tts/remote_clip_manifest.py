"""Remote clip-pack manifest — fetch, validate, and download clip packs."""
from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError

_CLIP_PACK_ROOT = Path(__file__).resolve().parents[2] / "assets" / "voice_clips"
_TIMEOUT = 15
_MAX_MANIFEST_SIZE = 64 * 1024
_MAX_PACK_SIZE = 500 * 1024 * 1024


class RemoteManifestError(Exception):
    pass


def fetch_manifest(url: str) -> dict[str, Any]:
    if not url:
        raise RemoteManifestError("No manifest URL configured.")
    try:
        req = Request(url, headers={"User-Agent": "DaniaSummerPet"})
        with urlopen(req, timeout=_TIMEOUT) as resp:
            data = resp.read(_MAX_MANIFEST_SIZE)
    except (URLError, OSError) as exc:
        raise RemoteManifestError(f"Failed to fetch manifest: {exc}") from exc
    try:
        manifest = json.loads(data)
    except json.JSONDecodeError as exc:
        raise RemoteManifestError(f"Invalid manifest JSON: {exc}") from exc
    _validate_manifest(manifest)
    return manifest


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if "packs" not in manifest or not isinstance(manifest["packs"], list):
        raise RemoteManifestError("Manifest missing 'packs' array.")
    for pack in manifest["packs"]:
        for key in ("clip_pack_id", "download_url"):
            if key not in pack:
                raise RemoteManifestError(f"Pack entry missing '{key}'.")


def download_pack(
    pack_info: dict[str, Any],
    verify_sha256: bool = True,
) -> Path:
    pack_id = pack_info["clip_pack_id"]
    download_url = pack_info["download_url"]
    sha256_url = pack_info.get("sha256_url", "")

    try:
        req = Request(download_url, headers={"User-Agent": "DaniaSummerPet"})
        with urlopen(req, timeout=60) as resp:
            pack_data = resp.read(_MAX_PACK_SIZE)
    except (URLError, OSError) as exc:
        raise RemoteManifestError(f"Download failed: {exc}") from exc

    if verify_sha256 and sha256_url:
        try:
            req = Request(sha256_url, headers={"User-Agent": "DaniaSummerPet"})
            with urlopen(req, timeout=_TIMEOUT) as resp:
                expected = resp.read(256).decode().strip().split()[0].lower()
        except (URLError, OSError) as exc:
            raise RemoteManifestError(f"SHA256 fetch failed: {exc}") from exc
        actual = hashlib.sha256(pack_data).hexdigest()
        if actual != expected:
            raise RemoteManifestError(
                f"SHA256 mismatch: expected {expected}, got {actual}"
            )

    dest = _CLIP_PACK_ROOT / pack_id
    try:
        with zipfile.ZipFile(BytesIO(pack_data)) as zf:
            zf.extractall(dest)
    except zipfile.BadZipFile as exc:
        raise RemoteManifestError(f"Invalid zip: {exc}") from exc
    return dest
