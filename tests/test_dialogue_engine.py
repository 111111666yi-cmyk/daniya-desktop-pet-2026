from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine
from src.daniya_engine_adapter import DaniyaEngineAdapter


class RecordingModel:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


class FailingModel:
    def __call__(self, prompt: str) -> str:
        raise RuntimeError("network down")


class SequenceModel:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        if not self.responses:
            return "......嗯。"
        return self.responses.pop(0)


class ExistingChatClientShape:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def reply(self, prompt: str) -> tuple[str, str]:
        self.prompts.append(prompt)
        return "我很开心你来找我。", "api"


def test_special_response_has_priority_and_does_not_call_model():
    pack = load_character("daniya")
    model = RecordingModel("should not be used")
    result = DialogueEngine(pack, model_client=model).handle_user_message("我不会先走")
    assert result.response == "......随便你。反正我也懒得赶。"
    assert result.source == "special_response"
    assert result.matched_special_response is True
    assert model.calls == []


def test_normal_input_uses_prompt_builder_model_and_speech_filter():
    pack = load_character("daniya")
    model = RecordingModel("我很开心你来找我。")
    result = DialogueEngine(pack, model_client=model).handle_user_message("今天有点累")
    assert model.calls
    assert "用户当前输入：\n今天有点累" in model.calls[0]
    assert result.source == "model"
    assert result.raw_model_response == "我很开心你来找我。"
    assert result.response == "......谁高兴了。"
    assert result.filtered is True


def test_model_failure_uses_filtered_local_fallback():
    pack = load_character("daniya")
    result = DialogueEngine(pack, model_client=FailingModel()).handle_user_message("今天有点累")
    assert result.source == "local_fallback"
    assert result.errors
    assert result.response.startswith("......")
    assert len(result.response) <= 100


def test_adapter_initializes_and_wraps_existing_chat_client_shape():
    chat_client = ExistingChatClientShape()
    adapter = DaniyaEngineAdapter(model_client=chat_client)
    result = adapter.handle_user_text("普通聊天")
    assert adapter.character_pack.character_id == "daniya"
    assert chat_client.prompts
    assert result.response == "......谁高兴了。"
    assert result.source == "api"


def test_dialogue_engine_accepts_existing_chat_client_shape_directly():
    pack = load_character("daniya")
    chat_client = ExistingChatClientShape()
    result = DialogueEngine(pack, model_client=chat_client).handle_user_message("普通聊天")
    assert chat_client.prompts
    assert result.response == "......谁高兴了。"
    assert result.source == "api"


def test_dialogue_engine_preserves_tuple_source_from_callable_model():
    pack = load_character("daniya")

    def model(prompt: str) -> tuple[str, str]:
        return "我很开心你来找我。", "api"

    result = DialogueEngine(pack, model_client=model).handle_user_message("普通聊天")

    assert result.response == "......谁高兴了。"
    assert result.source == "api"


def test_dialogue_engine_sanitizes_forbidden_addressing_across_turns():
    pack = load_character("daniya")
    forbidden_terms = (
        "".join(["御", "主"]),
        "".join(["主", "人"]),
        "Mas" + "ter",
        "ご" + "".join(["主", "人"]),
    )
    model = SequenceModel(
        [
            f"{forbidden_terms[0]}，我在。",
            f"{forbidden_terms[1]}，别硬撑。",
            f"{forbidden_terms[2]}, sit down.",
            f"{forbidden_terms[3]}、少熬夜。",
        ]
    )
    engine = DialogueEngine(pack, model_client=model)

    outputs = [
        engine.handle_user_message("第一轮").response,
        engine.handle_user_message("第二轮").response,
        engine.handle_user_message("第三轮").response,
        engine.handle_user_message("第四轮").response,
    ]

    assert len(model.calls) == 4
    assert "禁止用主仆" in model.calls[0]
    for output in outputs:
        for forbidden in forbidden_terms:
            assert forbidden not in output
