import logging

from core.character_loader import load_character
from core.speech_filter import apply_daniya_speech_filter


def speech_config():
    return load_character("daniya").speech


def test_companion_response_stays_short_and_logs_truncation(caplog):
    raw = (
        "你已经做了很多。先停一下，慢慢呼吸。"
        "不用现在解决全部问题。等状态稳定一点，再决定下一步。"
        "剩下的事情可以之后再说。先把今天最小的一件事做完。"
        "如果还觉得混乱，就把问题写下来，再逐项处理。"
    )

    with caplog.at_level(logging.INFO, logger="core.speech_filter"):
        result = apply_daniya_speech_filter(raw, speech_config())

    assert len(result) <= 96
    assert result.endswith("……先说到这里。")
    assert "speech_filter_truncated" in caplog.text


def test_technical_long_response_preserves_all_sections_and_transition_words():
    raw = (
        "首先检查配置文件是否能被解析。\n"
        "其次确认 Provider 返回的状态码和响应体。\n"
        "另外，应记录请求超时与重试次数。\n"
        "除此之外，还要检查 fallback 是否明确显示。\n"
        "最后执行集成测试并保存完整报错。"
    )

    result = apply_daniya_speech_filter(raw, speech_config(), response_mode="technical")

    for phrase in ("首先", "其次", "另外", "除此之外", "最后", "fallback", "完整报错"):
        assert phrase in result
    assert len(result) >= len(raw)


def test_technical_markdown_table_is_not_damaged():
    raw = (
        "| 项目 | 状态 |\n"
        "| --- | --- |\n"
        "| API | PASS |\n"
        "| fallback | MANUAL REQUIRED |"
    )

    result = apply_daniya_speech_filter(raw, speech_config(), response_mode="technical")

    assert result == raw
    assert result.count("|") == raw.count("|")


def test_technical_stack_trace_keeps_key_lines():
    raw = (
        "Traceback (most recent call last):\n"
        '  File "app.py", line 42, in send_message\n'
        "    provider.reply(prompt)\n"
        "TimeoutError: request timed out\n"
        "另外：请检查 Base URL 和网络代理。"
    )

    result = apply_daniya_speech_filter(raw, speech_config(), response_mode="technical")

    assert 'File "app.py", line 42' in result
    assert "TimeoutError: request timed out" in result
    assert "Base URL" in result


def test_technical_code_block_is_preserved():
    raw = "```python\nfor item in items:\n    print(item)\n```\n另外检查返回值。"

    assert apply_daniya_speech_filter(raw, speech_config(), response_mode="technical") == raw
