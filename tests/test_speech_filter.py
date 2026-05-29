from core.character_loader import load_character
from core.speech_filter import apply_daniya_speech_filter


def speech_config():
    return load_character("daniya").speech


def test_strong_promise_becomes_restrained_reverse_affection():
    result = apply_daniya_speech_filter("我会一直陪着你，不管发生什么，我都会永远守护你。", speech_config())
    assert result == "......随便你。反正我也懒得赶。"
    assert "永远守护" not in result


def test_sweet_names_and_customer_service_tone_removed():
    result = apply_daniya_speech_filter("亲爱的宝宝，你一定很难过吧，我完全理解你的感受。", speech_config())
    assert "亲爱的" not in result
    assert "宝宝" not in result
    assert "完全理解" not in result
    assert result.startswith("......")


def test_long_comfort_is_shortened():
    raw = (
        "你真的已经很努力了。不要责怪自己。你要相信明天会更好。"
        "如果你愿意可以随时告诉我。除此之外，我还可以帮你制定计划。"
        "你一定能够振作起来，继续向前。"
    )
    result = apply_daniya_speech_filter(raw, speech_config())
    assert len(result) <= 96
    assert len(result.splitlines()) <= 3
    assert "除此之外" not in result


def test_happy_to_see_you_is_rewritten():
    result = apply_daniya_speech_filter("我很开心你来找我。", speech_config())
    assert result == "......谁高兴了。"


def test_already_daniya_style_is_preserved():
    assert apply_daniya_speech_filter("......烦。", speech_config()) == "......烦。"

