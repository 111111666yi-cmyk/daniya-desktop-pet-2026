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


def test_long_reply_is_length_capped():
    raw = "。".join(f"这是第{i}个需要说明的要点内容" for i in range(1, 9)) + "。"
    result = apply_daniya_speech_filter(raw, speech_config())
    assert len(result) <= 96
    assert len(result.splitlines()) <= 3


def test_continuation_phrase_is_preserved():
    raw = "第一步先备份配置。除此之外，记得检查端口是否被占用。"
    result = apply_daniya_speech_filter(raw, speech_config())
    assert "除此之外" in result
    assert "检查端口" in result


def test_digression_phrase_is_truncated():
    raw = "这个问题先按文档里的步骤处理好。顺便，你今天吃饭了吗。"
    result = apply_daniya_speech_filter(raw, speech_config())
    assert "顺便" not in result
    assert "吃饭" not in result


def test_happy_to_see_you_is_rewritten():
    result = apply_daniya_speech_filter("我很开心你来找我。", speech_config())
    assert result == "......谁高兴了。"


def test_already_daniya_style_is_preserved():
    assert apply_daniya_speech_filter("......烦。", speech_config()) == "......烦。"


def test_already_has_ellipsis_is_not_duplicated():
    assert apply_daniya_speech_filter("……嗯。", speech_config()) == "……嗯。"
    assert apply_daniya_speech_filter("...嗯。", speech_config()) == "...嗯。"
    assert apply_daniya_speech_filter("…嗯。", speech_config()) == "…嗯。"
    assert apply_daniya_speech_filter("嗯。", speech_config()) == "嗯。"
    assert apply_daniya_speech_filter("你好", speech_config()) == "......你好"


def test_code_block_bypasses_speech_filter():
    code_text = "……好哦。\n```python\ndef test():\n    print('hello')\n```"
    assert apply_daniya_speech_filter(code_text, speech_config()) == code_text


def test_forbidden_user_addressing_is_sanitized():
    forbidden_terms = (
        "".join(["御", "主"]),
        "".join(["主", "人"]),
        "mas" + "ter",
        "Mas" + "ter",
        "ご" + "".join(["主", "人"]),
        "".join(["指", "挥", "官"]),
        "".join(["漂", "泊", "者"]),
    )
    result = apply_daniya_speech_filter(
        "，".join(forbidden_terms) + "。",
        speech_config(),
    )
    for forbidden in forbidden_terms:
        assert forbidden not in result
    assert "你" in result


def test_master_branch_context_is_preserved():
    result = apply_daniya_speech_filter("请保留 origin/master 分支。", speech_config())
    assert "origin/master 分支" in result
