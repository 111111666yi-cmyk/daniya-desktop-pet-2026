import json

from core.character_loader import load_character
from core.relationship_engine import apply_effect, data_root, init_state_if_missing, load_state


def test_init_relationship_state_from_character_pack():
    pack = load_character("daniya")
    path = data_root() / "relationship_state.json"
    assert not path.exists()
    state = init_state_if_missing(pack)
    assert path.exists()
    assert state["character_id"] == "daniya"
    assert state["relationship_stage"] == "default_stay"
    assert state["trust"] == 35
    assert state["softness_leak"] == 18


def test_apply_effect_clamps_metrics():
    state = {"character_id": "daniya", "relationship_stage": "default_stay", "trust": 99, "softness_leak": 1}
    updated = apply_effect(state, {"trust": 5, "softness_leak": -10}, "test")
    assert updated["trust"] == 100
    assert updated["softness_leak"] == 0
    assert updated["last_update_reason"] == "test"


def test_bad_relationship_json_falls_back_and_backs_up():
    pack = load_character("daniya")
    path = data_root() / "relationship_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ broken json", encoding="utf-8")
    state = load_state("daniya", pack.relationship)
    assert state["relationship_stage"] == "default_stay"
    assert state["trust"] == 35
    assert list(path.parent.glob("relationship_state.json.broken-*"))
    assert json.loads(path.read_text(encoding="utf-8"))["character_id"] == "daniya"

