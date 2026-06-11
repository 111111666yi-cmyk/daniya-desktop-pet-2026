from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine


class RecordingModel:
    def __init__(self, response: str = "普通模型回复。") -> None:
        self.response = response
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def test_explicit_command_precedes_character_trigger():
    model = RecordingModel()
    engine = DialogueEngine(load_character("daniya"), model_client=model)

    result = engine.handle_user_message("/pet status 抱抱")

    assert result.source == "command"
    assert result.event_id == "pet_unknown_command"
    assert model.calls == []


def test_exact_character_trigger_precedes_ordinary_chat():
    model = RecordingModel()
    engine = DialogueEngine(load_character("daniya"), model_client=model)

    result = engine.handle_user_message("归期到了")

    assert result.source == "special_response"
    assert result.special_response_id == "return_date"
    assert model.calls == []


def test_technical_request_prevents_embedded_emotion_event_side_effect():
    model = RecordingModel(
        "累加器可以先初始化为零，同时在循环中累加；除此之外要处理空输入。"
    )
    engine = DialogueEngine(load_character("daniya"), model_client=model)

    result = engine.handle_user_message("Python 的累加器怎么实现？请给出步骤和代码。")

    assert result.source == "model"
    assert result.event_id is None
    assert result.relationship_effect == {}
    assert result.action == "talk"
    assert "除此之外要处理空输入" in result.response
    assert len(model.calls) == 1


def test_physical_event_uses_task_route_without_matching_text_trigger():
    model = RecordingModel()
    engine = DialogueEngine(load_character("daniya"), model_client=model)

    result = engine.handle_user_message(
        "抱抱这个词在代码里是什么意思？",
        context={"physical_event": "user_drag"},
    )

    assert result.source == "physical_event"
    assert result.event_id == "user_drag"
    assert result.relationship_effect == {"defense_level": 1}
    assert model.calls == []
