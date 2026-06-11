from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine
from core.special_response_matcher import match_special_response


class RecordingModel:
    def __init__(self, response: str = "这是功能性回答。") -> None:
        self.response = response
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def speech_config():
    return load_character("daniya").speech


def test_required_trigger_phrases_match_exactly():
    cases = {
        "我不会先走": "wont_leave_first",
        "抱抱": "hug",
        "我们是不是同一个人": "same_person",
        "归期到了": "return_date",
        "那根弦松了一点": "loosened_string",
    }

    for text, expected_id in cases.items():
        result = match_special_response(text, speech_config())
        assert result["matched"] is True
        assert result["id"] == expected_id
        assert result["match_type"] == "exact"


def test_required_trigger_phrases_accept_normalized_variants():
    cases = {
        " 我 不 会 先 走！": "wont_leave_first",
        "抱 抱。": "hug",
        "我们是不是同一个人？": "same_person",
        "归期到了。": "return_date",
        "那 根 弦 松 了 一 点！": "loosened_string",
    }

    for text, expected_id in cases.items():
        result = match_special_response(text, speech_config())
        assert result["matched"] is True
        assert result["id"] == expected_id
        assert result["match_type"] == "normalized"


def test_technical_question_with_trigger_phrase_routes_to_model_without_event_effect():
    pack = load_character("daniya")
    model = RecordingModel("可以使用 re.escape 处理“抱抱”这个字符串，另外再编译正则。")
    direct_match = match_special_response(
        "Python 中“抱抱”这个字符串应该怎么做正则匹配？",
        speech_config(),
    )

    result = DialogueEngine(pack, model_client=model).handle_user_message(
        "Python 中“抱抱”这个字符串应该怎么做正则匹配？"
    )

    assert direct_match["matched"] is False
    assert result.source == "model"
    assert result.matched_special_response is False
    assert result.event_id is None
    assert result.relationship_effect == {}
    assert len(model.calls) == 1
    assert "另外再编译正则" in result.response


def test_reminder_sentence_with_trigger_phrase_is_not_special_response():
    pack = load_character("daniya")
    model = RecordingModel("明白，这是一个提醒请求。")

    result = DialogueEngine(pack, model_client=model).handle_user_message(
        "请提醒我明天告诉你“我不会先走”"
    )

    assert result.source == "model"
    assert result.matched_special_response is False
    assert result.event_id is None
    assert result.relationship_effect == {}
    assert len(model.calls) == 1
