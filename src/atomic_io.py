from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def atomic_write_text(path: Path, content: str) -> bool:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError as exc:
        logger.warning(
            "atomic_write_failed file=%s error=%s",
            path.name,
            exc.__class__.__name__,
        )
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def atomic_write_json(path: Path, value: Any) -> bool:
    return atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2))
