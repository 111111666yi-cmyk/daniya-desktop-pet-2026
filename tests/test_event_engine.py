from core.character_loader import load_character
from core.event_engine import match_event


def test_event_engine_matches_required_events():
    events = load_character("daniya").events
    cases = {
        "抱抱": "user_hug_request",
        "我不会先走": "user_says_wont_leave",
        "我好累": "user_negative_mood",
        "生日": "birthday_orange_cake",
        "[click]": "user_click",
        "[drag]": "user_drag",
        "[reminder]": "reminder_due",
    }
    for text, event_id in cases.items():
        assert match_event(text, events)["id"] == event_id


def test_event_engine_unmatched_returns_none():
    assert match_event("今天只是普通聊天", load_character("daniya").events) is None

