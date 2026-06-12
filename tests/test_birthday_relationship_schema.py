"""B0-3: birthday and relationship schema backfill tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.profile_manager import DEFAULT_PROFILE, ProfileManager


class FakeConfigManager:
    def __init__(self, root: Path) -> None:
        self.config_dir = root / "config"
        self.data_dir = root / "data"
        self.config_dir.mkdir(parents=True)
        self.data_dir.mkdir(parents=True)

    def load_json(self, path: Path, fallback: Any) -> Any:
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return fallback

    def save_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def test_old_profile_missing_birthday_auto_backfills(tmp_path):
    """Loading a pre-B0-3 profile without birthday fields should backfill them."""
    cm = FakeConfigManager(tmp_path)
    old_profile = {"user_name": "测试用户", "relationship": "桌宠与用户", "style": "温柔"}
    cm.save_json(cm.config_dir / "profile.json", old_profile)
    pm = ProfileManager(cm)
    loaded = pm.load()
    assert loaded["birthday"] == ""
    assert loaded["birthday_display"] == ""
    assert loaded["birthday_source"] == "unset"
    assert loaded["birthday_updated_at"] == ""
    assert loaded["user_name"] == "测试用户"


def test_existing_birthday_values_not_overwritten(tmp_path):
    """If the profile already has birthday data, loading must preserve it."""
    cm = FakeConfigManager(tmp_path)
    profile = {
        "user_name": "你",
        "relationship": "桌宠与用户",
        "style": "温柔",
        "birthday": "01-15",
        "birthday_display": "1月15日",
        "birthday_source": "user_input",
        "birthday_updated_at": "2026-06-01T12:00:00",
    }
    cm.save_json(cm.config_dir / "profile.json", profile)
    pm = ProfileManager(cm)
    loaded = pm.load()
    assert loaded["birthday"] == "01-15"
    assert loaded["birthday_display"] == "1月15日"
    assert loaded["birthday_source"] == "user_input"
    assert loaded["birthday_updated_at"] == "2026-06-01T12:00:00"


def test_bad_json_profile_does_not_crash(tmp_path):
    """Corrupted profile.json should fall back to defaults without crashing."""
    cm = FakeConfigManager(tmp_path)
    (cm.config_dir / "profile.json").write_text("{invalid json", encoding="utf-8")
    pm = ProfileManager(cm)
    loaded = pm.load()
    assert loaded["user_name"] == DEFAULT_PROFILE["user_name"]
    assert loaded["birthday"] == ""
    assert loaded["birthday_source"] == "unset"


def test_default_profile_has_all_birthday_fields():
    required = {"birthday", "birthday_display", "birthday_source", "birthday_updated_at"}
    assert required.issubset(set(DEFAULT_PROFILE.keys()))


def test_birthday_fields_empty_in_default_profile():
    assert DEFAULT_PROFILE["birthday"] == ""
    assert DEFAULT_PROFILE["birthday_display"] == ""
    assert DEFAULT_PROFILE["birthday_source"] == "unset"
    assert DEFAULT_PROFILE["birthday_updated_at"] == ""


def test_relationship_state_backfills_tracking_fields(tmp_path, monkeypatch):
    """Loading old relationship state without tracking fields should backfill them."""
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path))
    old_state = {
        "character_id": "daniya",
        "relationship_stage": "default_stay",
        "affection": 50,
        "trust": 40,
    }
    (tmp_path / "relationship_state.json").write_text(
        json.dumps(old_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    from core.relationship_engine import load_state
    state = load_state("daniya", {})
    assert state["last_interaction_at"] is None
    assert state["interaction_count"] == 0
    assert state["last_event_id"] is None
    assert state["schema_version"] == 2
    assert state["affection"] == 50
    assert state["trust"] == 40


def test_relationship_state_existing_tracking_not_overwritten(tmp_path, monkeypatch):
    """Existing tracking fields must be preserved on load."""
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path))
    state_data = {
        "character_id": "daniya",
        "relationship_stage": "default_stay",
        "affection": 60,
        "trust": 50,
        "last_interaction_at": "2026-06-10T08:00:00",
        "interaction_count": 42,
        "last_event_id": "evt_123",
        "schema_version": 2,
    }
    (tmp_path / "relationship_state.json").write_text(
        json.dumps(state_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    from core.relationship_engine import load_state
    state = load_state("daniya", {})
    assert state["last_interaction_at"] == "2026-06-10T08:00:00"
    assert state["interaction_count"] == 42
    assert state["last_event_id"] == "evt_123"


def test_character_yaml_birthday_null():
    """Character YAML birthday field must be null (not fabricated)."""
    import yaml
    char_path = Path(__file__).resolve().parent.parent / "characters" / "daniya" / "character.yaml"
    data = yaml.safe_load(char_path.read_text(encoding="utf-8"))
    assert data["birthday"] is None
    assert data["birthday_display"] == ""
    assert data["birthday_lore_note"] == ""


def test_no_relationship_state_in_repo():
    """relationship_state.json must never be committed to the repo."""
    repo_root = Path(__file__).resolve().parent.parent
    state_files = list(repo_root.rglob("relationship_state*.json"))
    tracked = [f for f in state_files if "data" not in f.parts and "runtime" not in f.parts]
    assert tracked == [], f"relationship_state files found in tracked dirs: {tracked}"


def test_no_user_birthday_in_public_templates():
    """Public config templates must not contain actual user birthday data."""
    repo_root = Path(__file__).resolve().parent.parent
    example = repo_root / "config" / "profile.json"
    if example.exists():
        data = json.loads(example.read_text(encoding="utf-8"))
        assert data.get("birthday", "") == ""
        assert data.get("birthday_source", "unset") in ("", "unset")
