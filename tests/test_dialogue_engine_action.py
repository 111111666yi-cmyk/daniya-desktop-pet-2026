from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine


def test_hug_special_response_routes_close_idle_without_model_call():
    pack = load_character("daniya")
    calls = []

    def model(prompt: str) -> str:
        calls.append(prompt)
        return "unused"

    result = DialogueEngine(pack, model_client=model).handle_user_message("抱抱")
    assert result.response == "......烦死了。过来。"
    assert result.action == "close_idle"
    assert result.fallback_chain[:3] == ["close_idle", "happy", "idle"]
    assert calls == []


def test_negative_emotion_routes_soft_idle_or_idle():
    pack = load_character("daniya")
    result = DialogueEngine(pack, model_client=lambda prompt: "你一定很难过吧，我理解你。").handle_user_message("我好累")
    assert result.action in {"soft_idle", "idle"}
    assert "idle" in result.fallback_chain
    assert len(result.response) <= 100


def test_normal_model_response_routes_talk_or_idle_and_is_filtered():
    pack = load_character("daniya")
    result = DialogueEngine(pack, model_client=lambda prompt: "我很开心你来找我。").handle_user_message("普通聊天")
    assert result.action in {"talk", "idle"}
    assert result.response == "......谁高兴了。"
    assert result.filtered is True


def test_physical_context_routes_click_drag_reminder():
    pack = load_character("daniya")
    engine = DialogueEngine(pack, model_client=lambda prompt: "哦。")
    clicked = engine.handle_user_message("[click]", context={"physical_event": "user_click"})
    dragged = engine.handle_user_message("[drag]", context={"physical_event": "user_drag"})
    reminded = engine.handle_user_message("[reminder]", context={"physical_event": "reminder_due"})
    assert clicked.action == "clicked"
    assert dragged.action == "drag"
    assert reminded.action == "remind"

