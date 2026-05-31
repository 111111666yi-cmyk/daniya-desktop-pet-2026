from core.character_loader import load_character
from core.special_response_matcher import match_special_response


def speech_config():
    return load_character("daniya").speech


def test_match_name_exact():
    result = match_special_response("达妮娅", speech_config())
    assert result["matched"] is True
    assert result["id"] == "call_name"
    assert result["response"] == "嗯。"
    assert result["match_type"] == "exact"


def test_match_wont_leave_first_with_effect():
    result = match_special_response("我不会先走", speech_config())
    assert result["matched"] is True
    assert result["id"] == "wont_leave_first"
    assert result["response"] == "......随便你。反正我也懒得赶。"
    assert result["action"] == "talk"
    assert result["relationship_effect"]["trust"] == 2


def test_match_recently_and_hug():
    assert match_special_response("最近怎么样", speech_config())["response"] == "......还行。懒得说。"
    assert match_special_response("抱抱", speech_config())["response"] == "......烦死了。过来。"


def test_match_loosened_string_follow_up():
    first = match_special_response("那根弦松了一点", speech_config())
    assert first["matched"] is True
    assert first["id"] == "loosened_string"
    assert first["response"] == "......错觉。"
    follow = match_special_response("我知道", speech_config(), {"last_special_response_id": "loosened_string"})
    assert follow["matched"] is True
    assert follow["response"] == "嗯。"
    assert follow["match_type"] == "follow_up"


def test_normalized_contains_fuzzy_and_unmatched():
    normalized = match_special_response(" 我 不 会 先 走！", speech_config())
    assert normalized["matched"] is True
    assert normalized["match_type"] == "normalized"
    contains = match_special_response("现在想抱抱一下。", speech_config())
    assert contains["matched"] is True
    assert contains["response"] == "......烦死了。过来。"
    fuzzy = match_special_response("我们是不是同一个入", speech_config())
    assert fuzzy["matched"] is True
    unrelated = match_special_response("今天想研究一下文件结构", speech_config())
    assert unrelated == {
        "matched": False,
        "id": None,
        "response": None,
        "action": None,
        "relationship_effect": {},
        "match_type": None,
    }
