"""共享图标加载工具。从 assets/icons/ 加载 SVG 图标用于 UI。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

from .utils import runtime_root


_ICON_CACHE: dict[str, QIcon] = {}


def icon(icon_key: str, root: Path | None = None) -> QIcon:
    """从 assets/icons 加载图标。icon_key 支持 'chip', 'settings', 'download' 等。"""
    cache_key = f"{icon_key}_{root}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    _MAP: dict[str, str] = {
        "chip": "microchip.svg",
        "cloud": "cloud-download.svg",
        "download": "download.svg",
        "upload": "upload.svg",
        "document": "document.svg",
        "license": "document.svg",
        "settings": "settings.svg",
        "info": "info.svg",
        "internet": "internet.svg",
        "official": "internet.svg",
        "laptop": "laptop.svg",
        "protect": "protect.svg",
        "save": "save.svg",
        "refresh": "refresh.svg",
        "size": "memory-card.svg",
        "host": "computer-host.svg",
    }
    base = root or runtime_root()
    filename = _MAP.get(icon_key, icon_key)
    icon_path = base / "assets" / "icons" / filename
    if icon_path.exists():
        res = QIcon(str(icon_path))
    else:
        res = QIcon()
    _ICON_CACHE[cache_key] = res
    return res
