from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from core.schema import CharacterPack
from src.utils import runtime_root
from src.atomic_io import atomic_write_text

# Relationship state reads and writes share one lock so a reader never
# interprets an in-progress write as corrupt user data.
_state_lock = threading.Lock()
logger = logging.getLogger(__name__)

METRIC_FIELDS = {
    "affection",
    "trust",
    "dependency",
    "heartbeat",
    "jealousy",
    "boundary",
    "empathy_load",
    "softness_leak",
    "defense_level",
    "stay_tendency",
}


def data_root() -> Path:
    return Path(os.environ.get("DANIYA_RELATION_DATA_DIR", runtime_root() / "data" / "daniya_relation"))


def state_path(character_id: str = "daniya") -> Path:
    if character_id == "daniya":
        return data_root() / "relationship_state.json"
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", character_id).strip("._") or "character"
    return data_root() / f"relationship_state.{safe_id}.json"


def init_state_if_missing(character_pack: CharacterPack) -> dict[str, Any]:
    path = state_path(character_pack.character_id)
    if path.exists():
        return load_state(character_pack.character_id, character_pack.relationship)
    state = _initial_state(character_pack.character_id, character_pack.relationship)
    save_state(state)
    return state


def load_state(character_id: str = "daniya", relationship_config: dict[str, Any] | None = None) -> dict[str, Any]:
    path = state_path(character_id)
    fallback = _initial_state(character_id, relationship_config or {})
    if not path.exists():
        migrated = _migrate_legacy_state(character_id)
        if migrated is not None:
            return clamp_metrics(migrated)
        save_state(fallback)
        return fallback
    data = _read_json(path, fallback)
    if not isinstance(data, dict):
        return fallback
    stored_character_id = str(data.get("character_id") or "")
    if stored_character_id and stored_character_id != character_id:
        _preserve_foreign_state(data)
        save_state(fallback)
        return fallback
    state = dict(fallback)
    state.update(data)
    state["character_id"] = character_id
    return clamp_metrics(state)


def save_state(state: dict[str, Any]) -> None:
    character_id = str(state.get("character_id") or "daniya")
    path = state_path(character_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _state_lock:
        _write_state_unlocked(path, state)


def apply_effect(state: dict[str, Any], effect: dict[str, Any] | None, reason: str) -> dict[str, Any]:
    updated = dict(state)
    if isinstance(effect, dict):
        for key, value in effect.items():
            if key not in METRIC_FIELDS:
                continue
            try:
                delta = int(value)
            except (TypeError, ValueError):
                continue
            updated[key] = int(updated.get(key, 0)) + delta
    updated["last_update_reason"] = reason
    return clamp_metrics(updated)


def update_from_event(state: dict[str, Any], event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return state
    effect = event.get("relationship_effect") or event.get("state_delta") or {}
    return apply_effect(state, effect, f"event:{event.get('id', 'unknown')}")


def calculate_stage(state: dict[str, Any], relationship_config: dict[str, Any]) -> str:
    current = str(state.get("relationship_stage") or relationship_config.get("initial_state", {}).get("relationship_stage") or "default_stay")
    score = state.get("relationship_score")
    if score is None:
        return current
    try:
        numeric_score = int(score)
    except (TypeError, ValueError):
        return current
    selected = current
    stages = relationship_config.get("relationship_stages") or relationship_config.get("stages") or []
    if not isinstance(stages, list):
        return current
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        try:
            if numeric_score >= int(stage.get("min_score", 0)):
                selected = str(stage.get("id") or selected)
        except (TypeError, ValueError):
            continue
    return selected


def clamp_metrics(state: dict[str, Any]) -> dict[str, Any]:
    updated = dict(state)
    for field in METRIC_FIELDS:
        value = updated.get(field, 0)
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = 0
        updated[field] = max(0, min(100, numeric))
    return updated


def build_state_summary(state: dict[str, Any]) -> dict[str, Any]:
    keys = ["character_id", "relationship_stage", "affection", "trust", "softness_leak", "defense_level", "empathy_load", "stay_tendency", "last_update_reason"]
    return {key: state.get(key) for key in keys if key in state}


def _initial_state(character_id: str, relationship_config: dict[str, Any]) -> dict[str, Any]:
    state = dict(relationship_config.get("initial_state") or {})
    state.setdefault("character_id", character_id)
    state.setdefault("relationship_stage", "default_stay")
    state.setdefault("affection", 45)
    state.setdefault("trust", 35)
    state.setdefault("dependency", 20)
    state.setdefault("heartbeat", 10)
    state.setdefault("jealousy", 5)
    state.setdefault("boundary", 75)
    state.setdefault("empathy_load", 80)
    state.setdefault("softness_leak", 18)
    state.setdefault("defense_level", 70)
    state.setdefault("stay_tendency", 90)
    state.setdefault("last_update_reason", "initial_default_desktop_pet")
    return clamp_metrics(state)


def _read_json(path: Path, fallback: Any) -> Any:
    with _state_lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = path.with_suffix(path.suffix + f".broken-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            try:
                path.replace(backup)
            except OSError:
                pass
            _write_state_unlocked(path, fallback)
            return fallback
        except OSError:
            return fallback


def _migrate_legacy_state(character_id: str) -> dict[str, Any] | None:
    if character_id == "daniya":
        return None
    legacy_path = state_path("daniya")
    if not legacy_path.exists():
        return None
    with _state_lock:
        try:
            data = json.loads(legacy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
    if not isinstance(data, dict) or str(data.get("character_id") or "") != character_id:
        return None
    save_state(data)
    return data


def _preserve_foreign_state(state: dict[str, Any]) -> None:
    foreign_id = str(state.get("character_id") or "")
    if not foreign_id or foreign_id == "daniya":
        return
    foreign_path = state_path(foreign_id)
    if foreign_path.exists():
        return
    save_state(state)


def _write_state_unlocked(path: Path, state: dict[str, Any]) -> None:
    content = json.dumps(clamp_metrics(state), ensure_ascii=False, indent=2)
    if not atomic_write_text(path, content):
        logger.warning("relationship_write_failed file=%s", path.name)
