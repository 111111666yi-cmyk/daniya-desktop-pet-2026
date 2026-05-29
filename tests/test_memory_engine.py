from core.character_loader import load_character
from core.event_engine import match_event
from core.memory_engine import data_root, load_event_log, load_user_memory, update_memory_from_interaction


def test_memory_records_key_phrase_and_unlocked_lore():
    pack = load_character("daniya")
    event = match_event("生日想吃橘子蛋糕", pack.events)
    memory = update_memory_from_interaction("抱抱，我不会先走，生日", event)
    assert "抱抱" in memory["important_user_phrases"]
    assert "我不会先走" in memory["important_user_phrases"]
    assert "birthday_orange_cake" in memory["unlocked_lore"]
    assert "birthday_orange_cake" in memory["last_events"]


def test_bad_memory_json_is_rebuilt():
    path = data_root() / "user_memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ broken", encoding="utf-8")
    memory = load_user_memory()
    assert memory["user_preferences"]["likes_short_reply"] is True
    assert list(path.parent.glob("user_memory.json.broken-*"))


def test_event_log_defaults_to_list():
    assert load_event_log() == []

