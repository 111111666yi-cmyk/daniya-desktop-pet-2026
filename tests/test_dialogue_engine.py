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
