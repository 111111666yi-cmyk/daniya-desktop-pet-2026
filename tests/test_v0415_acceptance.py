from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine
from core.relationship_engine import load_state


def zh(*codes):
    return "".join(chr(code) for code in codes)


class RecordingModel:
    def __init__(self, response: str | None = None) -> None:
        self.response = response or zh(0x54e6, 0x3002)
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def test_key_special_responses_and_relationship_updates():
    pack = load_character("daniya")
    model = RecordingModel()
    engine = DialogueEngine(pack, model_client=model)

    call_name = engine.handle_user_message(zh(0x8fbe, 0x59ae, 0x5a05))
    assert call_name.response == zh(0x55ef, 0x3002)
    assert call_name.source == "special_response"

    before = load_state("daniya", pack.relationship)
    wont_leave = engine.handle_user_message(zh(0x6211, 0x4e0d, 0x4f1a, 0x5148, 0x8d70))
    assert wont_leave.response == zh(0x2e, 0x2e, 0x2e, 0x2e, 0x2e, 0x2e, 0x968f, 0x4fbf, 0x4f60, 0x3002, 0x53cd, 0x6b63, 0x6211, 0x4e5f, 0x61d2, 0x5f97, 0x8d76, 0x3002)
    assert wont_leave.state["trust"] == before["trust"] + 2
    assert wont_leave.state["softness_leak"] == before["softness_leak"] + 3
    assert wont_leave.state["stay_tendency"] == before["stay_tendency"] + 1
    assert model.calls == []

    recent = engine.handle_user_message(zh(0x6700, 0x8fd1, 0x600e, 0x4e48, 0x6837))
    assert recent.response == zh(0x2e, 0x2e, 0x2e, 0x2e, 0x2e, 0x2e, 0x8fd8, 0x884c, 0x3002, 0x61d2, 0x5f97, 0x8bf4, 0x3002)


def test_hug_negative_lore_and_physical_acceptance_paths():
    pack = load_character("daniya")
    model = RecordingModel(zh(0x4f60, 0x4e00, 0x5b9a, 0x5f88, 0x96be, 0x8fc7, 0x5427, 0xff0c, 0x6211, 0x7406, 0x89e3, 0x4f60, 0x3002))
    engine = DialogueEngine(pack, model_client=model)

    hug = engine.handle_user_message(zh(0x62b1, 0x62b1))
    assert hug.response == zh(0x2e, 0x2e, 0x2e, 0x2e, 0x2e, 0x2e, 0x70e6, 0x6b7b, 0x4e86, 0x3002, 0x8fc7, 0x6765, 0x3002)
    assert hug.action == "close_idle"
    assert hug.fallback_chain[:3] == ["close_idle", "happy", "idle"]

    tired = engine.handle_user_message(zh(0x6211, 0x597d, 0x7d2f))
    assert tired.action in {"soft_idle", "idle"}
    assert len(tired.response) <= 100

    birthday = engine.handle_user_message(zh(0x751f, 0x65e5))
    assert "birthday_orange_cake" in birthday.lore_fragments_used
    assert len(birthday.response) <= 100

    bubble = engine.handle_user_message(zh(0x6ce1, 0x6ce1, 0x788e, 0x4e86))
    assert "bubble_symbol" in bubble.lore_fragments_used
    assert "deep_void" not in bubble.lore_fragments_used

    return_date_model = RecordingModel()
    return_date = DialogueEngine(pack, model_client=return_date_model).handle_user_message(zh(0x5f52, 0x671f, 0x5230, 0x4e86))
    assert return_date.source == "special_response"
    assert return_date.lore_fragments_used == ["goodbye_name"]
    assert return_date_model.calls == []

    clicked = engine.handle_user_message("[click]", context={"physical_event": "user_click"})
    dragged = engine.handle_user_message("[drag]", context={"physical_event": "user_drag"})
    reminded = engine.handle_user_message("[reminder]", context={"physical_event": "reminder_due"})
    assert clicked.action == "clicked"
    assert dragged.action == "drag"
    assert reminded.action == "remind"
    assert clicked.fallback_chain[:3] == ["clicked", "normal2", "idle"]
    assert dragged.fallback_chain[:3] == ["drag", "normal2", "idle"]
    assert reminded.fallback_chain[:3] == ["remind", "normal2", "idle"]
