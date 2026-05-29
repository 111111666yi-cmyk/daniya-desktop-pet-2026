import json

from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine
from core.memory_engine import data_root, load_event_log, load_user_memory
from core.relationship_engine import load_state


def test_special_response_updates_relationship_and_event_log():
    pack = load_character("daniya")
    result = DialogueEngine(pack, model_client=lambda prompt: "unused").handle_user_message("我不会先走")
    assert result.response == "......随便你。反正我也懒得赶。"
    assert result.source == "special_response"
    assert result.state["trust"] == 37
    assert result.state["softness_leak"] == 21
    assert result.state["stay_tendency"] == 91
    log = load_event_log()
    assert log[-1]["event_id"] == "user_says_wont_leave"
    assert log[-1]["source"] == "special_response"


def test_hug_event_updates_relationship_and_memory():
    pack = load_character("daniya")
    result = DialogueEngine(pack, model_client=lambda prompt: "unused").handle_user_message("抱抱")
    assert result.state["softness_leak"] == 20
    assert result.state["heartbeat"] == 11
    memory = load_user_memory()
    assert "抱抱" in memory["important_user_phrases"]


def test_negative_mood_event_updates_state_and_short_response():
    pack = load_character("daniya")
    result = DialogueEngine(pack, model_client=lambda prompt: "你一定很难过吧，我理解你。").handle_user_message("我好累")
    assert result.event_id == "user_negative_mood"
    assert result.state["empathy_load"] == 85
    assert result.state["stay_tendency"] == 91
    assert len(result.response) <= 100
    assert "理解你" not in result.response


def test_birthday_event_records_unlocked_lore_without_full_lore_injection():
    pack = load_character("daniya")
    result = DialogueEngine(pack, model_client=lambda prompt: "蛋糕而已。").handle_user_message("生日")
    assert result.event_id == "birthday_orange_cake"
    assert result.state["softness_leak"] == 19
    assert "birthday_orange_cake" in load_user_memory()["unlocked_lore"]
    assert "生日是存在主权，不只是庆祝" not in (result.prompt or "")


def test_engine_result_state_exists_for_normal_and_special():
    pack = load_character("daniya")
    engine = DialogueEngine(pack, model_client=lambda prompt: "哦。")
    normal = engine.handle_user_message("普通聊天")
    special = engine.handle_user_message("我不会先走")
    assert normal.state is not None
    assert special.state is not None


def test_old_data_files_are_not_created_or_touched_in_relation_engine(tmp_path):
    pack = load_character("daniya")
    DialogueEngine(pack, model_client=lambda prompt: "哦。").handle_user_message("普通聊天")
    relation_root = data_root()
    assert (relation_root / "relationship_state.json").exists()
    assert (relation_root / "event_log.json").exists()
    assert (relation_root / "user_memory.json").exists()
    assert not (relation_root.parent / "affinity.json").exists()
    assert not (relation_root.parent / "chat_history.jsonl").exists()
    assert not (relation_root.parent / "reminders.json").exists()
    assert not (relation_root.parent / "notes.txt").exists()

