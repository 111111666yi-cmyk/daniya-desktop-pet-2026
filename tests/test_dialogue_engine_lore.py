from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine
from core.memory_engine import load_event_log, load_user_memory


def zh(*codes):
    return "".join(chr(code) for code in codes)


class RecordingModel:
    def __init__(self, response: str | None = None) -> None:
        self.response = response or zh(0x54e6, 0x3002)
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def test_birthday_lore_reaches_prompt_result_memory_and_log():
    pack = load_character("daniya")
    model = RecordingModel()
    result = DialogueEngine(pack, model_client=model).handle_user_message(zh(0x751f, 0x65e5))
    assert "birthday_sovereignty" in result.lore_fragments_used
    assert model.calls
    assert "fragment_id: birthday_sovereignty" in model.calls[0]
    assert pack.lore not in model.calls[0]
    assert "birthday_sovereignty" in load_user_memory()["unlocked_lore"]
    assert load_event_log()[-1]["lore_fragments_used"] == result.lore_fragments_used


def test_bubble_lore_reaches_prompt_without_deep_void_spoiler():
    pack = load_character("daniya")
    model = RecordingModel()
    result = DialogueEngine(pack, model_client=model).handle_user_message(zh(0x6ce1, 0x6ce1, 0x788e, 0x4e86))
    assert "bubble_symbol" in result.lore_fragments_used
    assert "fragment_id: bubble_symbol" in model.calls[0]
    assert "deep_void_spoiler" not in model.calls[0]


def test_return_date_special_response_records_goodbye_lore_without_model_call():
    pack = load_character("daniya")
    model = RecordingModel()
    result = DialogueEngine(pack, model_client=model).handle_user_message(zh(0x5f52, 0x671f, 0x5230, 0x4e86))
    assert result.source == "special_response"
    assert result.response == zh(0x2e, 0x2e, 0x2e, 0x2e, 0x2e, 0x2e, 0x55ef, 0x3002, 0x5230, 0x4e86, 0x3002)
    assert result.lore_fragments_used == ["void_and_goodbye"]
    assert model.calls == []
    assert load_event_log()[-1]["lore_fragments_used"] == ["void_and_goodbye"]


def test_plain_chat_does_not_put_l4_or_full_lore_in_prompt():
    pack = load_character("daniya")
    model = RecordingModel()
    result = DialogueEngine(pack, model_client=model).handle_user_message(zh(0x4eca, 0x5929, 0x5403, 0x4ec0, 0x4e48))
    assert result.lore_fragments_used == []
    assert pack.lore not in model.calls[0]
    assert "deep_void_spoiler" not in model.calls[0]


def test_explicit_l4_question_adds_only_trimmed_deep_void_spoiler():
    pack = load_character("daniya")
    model = RecordingModel()
    result = DialogueEngine(pack, model_client=model).handle_user_message(
        zh(0x8fbe, 0x59ae, 0x5a05, 0x548c, 0x865a, 0x65e0, 0x3001, 0x6697, 0x9762, 0x5230, 0x5e95, 0x6709, 0x4ec0, 0x4e48, 0x5173, 0x7cfb)
    )
    assert "deep_void_spoiler" in result.lore_fragments_used
    assert "fragment_id: deep_void_spoiler" in model.calls[0]
    assert pack.lore not in model.calls[0]
