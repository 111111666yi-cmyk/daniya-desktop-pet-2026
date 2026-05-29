from core.action_router import route_action
from core.character_loader import load_character


def test_physical_user_click_route():
    route = route_action(physical_event="user_click", character_pack=load_character("daniya"))
    assert route["action"] == "clicked"
    assert route["fallback_chain"][:3] == ["clicked", "normal2", "idle"]
    assert "physical_event:user_click" in route["reason"]


def test_physical_user_drag_route():
    route = route_action(physical_event="user_drag", character_pack=load_character("daniya"))
    assert route["action"] == "drag"
    assert route["fallback_chain"][:3] == ["drag", "normal2", "idle"]


def test_physical_reminder_due_route():
    route = route_action(physical_event="reminder_due", character_pack=load_character("daniya"))
    assert route["action"] == "remind"
    assert route["fallback_chain"][:3] == ["remind", "normal2", "idle"]


def test_special_response_action_and_available_fallback():
    pack = load_character("daniya")
    special = {"id": "hug", "action": "close_idle"}
    route = route_action(user_text="抱抱", special_response=special, character_pack=pack)
    assert route["action"] == "close_idle"
    assert route["fallback_chain"][:3] == ["close_idle", "happy", "idle"]

    fallback = route_action(
        user_text="抱抱",
        special_response=special,
        character_pack=pack,
        available_actions={"idle", "happy", "talk"},
    )
    assert fallback["action"] == "happy"
    assert fallback["fallback_chain"][:3] == ["close_idle", "happy", "idle"]


def test_negative_emotion_and_missing_action_mapping_do_not_crash():
    pack = load_character("daniya")
    route = route_action(user_text="我好累", response="......坐会儿。", character_pack=pack)
    assert route["action"] in {"soft_idle", "idle"}
    assert "idle" in route["fallback_chain"]

    missing = route_action(user_text="我好累", response="......坐会儿。", character_pack={"action_mapping": {}})
    assert missing["action"] == "soft_idle"
    assert "idle" in missing["fallback_chain"]

