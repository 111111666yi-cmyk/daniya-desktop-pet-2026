from __future__ import annotations

import json
from pathlib import Path

from core.relationship_engine import load_state, save_state, state_path


def test_old_relationship_state_gains_defaults_and_preserves_unknown_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    relation_root = tmp_path / "relation"
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(relation_root))
    relation_root.mkdir()
    path = state_path("daniya")
    path.write_text(
        json.dumps(
            {
                "character_id": "daniya",
                "relationship_stage": "default_stay",
                "trust": 44,
                "custom_preserved": "keep",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    state = load_state("daniya", {"initial_state": {"affection": 45}})

    assert state["trust"] == 44
    assert state["affection"] == 45
    assert state["defense_level"] == 70
    assert state["custom_preserved"] == "keep"

    save_state(state)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["custom_preserved"] == "keep"
    assert stored["defense_level"] == 70
