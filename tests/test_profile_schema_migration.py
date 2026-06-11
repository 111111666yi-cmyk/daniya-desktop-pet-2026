from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.profile_manager import ProfileManager, sanitize_birthday


class FakeConfigManager:
    def __init__(self, root: Path) -> None:
        self.config_dir = root / "config"
        self.data_dir = root / "data"
        self.config_dir.mkdir(parents=True)
        self.data_dir.mkdir(parents=True)

    def load_json(self, path: Path, fallback: Any) -> Any:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))

    def save_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def test_old_profile_adds_empty_birthday_without_losing_existing_fields(tmp_path: Path) -> None:
    manager = ProfileManager(FakeConfigManager(tmp_path))
    manager.path.write_text(
        json.dumps(
            {
                "user_name": "小夏",
                "relationship": "朋友",
                "style": "简短",
                "custom_preserved": {"enabled": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    profile = manager.load()
    manager.save({**profile, "birthday": "3月14日"})
    stored = json.loads(manager.path.read_text(encoding="utf-8"))

    assert profile["birthday"] == ""
    assert stored["birthday"] == "03-14"
    assert stored["custom_preserved"] == {"enabled": True}


def test_birthday_accepts_month_day_only() -> None:
    assert sanitize_birthday("02-29") == "02-29"
    assert sanitize_birthday("3/14") == "03-14"
    assert sanitize_birthday("2026-03-14") == ""
    assert sanitize_birthday("02-30") == ""
    assert sanitize_birthday("") == ""


def test_prompt_includes_optional_month_day_but_not_a_year(tmp_path: Path) -> None:
    manager = ProfileManager(FakeConfigManager(tmp_path))
    manager.save(
        {
            "user_name": "小夏",
            "birthday": "03-14",
            "relationship": "朋友",
            "style": "简短",
        }
    )

    prompt = manager.prompt_prefix()

    assert "生日（月日）：03-14" in prompt
    assert "2026-03-14" not in prompt
