from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.profile_manager import ProfileManager


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


def test_prompt_prefix_includes_profile_memory_and_notes(tmp_path, monkeypatch) -> None:
    relation_dir = tmp_path / "relation"
    relation_dir.mkdir()
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(relation_dir))
    (relation_dir / "user_memory.json").write_text(
        json.dumps(
            {
                "user_preferences": {"likes_short_reply": True},
                "important_user_phrases": ["我不会先走"],
                "unlocked_lore": ["birthday_sovereignty"],
                "last_events": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = ProfileManager(FakeConfigManager(tmp_path))
    manager.save({"user_name": "snow", "relationship": "桌宠与主人", "style": "简短"})
    (tmp_path / "data" / "notes.txt").write_text("[2026-06-03 00:00:00] 喜欢安静陪伴\n", encoding="utf-8")

    prefix = manager.prompt_prefix()

    assert "称呼：snow" in prefix
    assert "用户记忆偏好" in prefix
    assert "我不会先走" in prefix
    assert "birthday_sovereignty" in prefix
    assert "达妮娅记忆备忘录" in prefix
    assert "喜欢安静陪伴" in prefix
