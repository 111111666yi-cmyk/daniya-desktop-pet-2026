from core.character_loader import load_character
from core.lore_retriever import extract_fragment, retrieve


def zh(*codes):
    return "".join(chr(code) for code in codes)


def test_plain_chat_does_not_retrieve_lore_or_l4():
    pack = load_character("daniya")
    fragments = retrieve(zh(0x4eca, 0x5929, 0x5403, 0x4ec0, 0x4e48), pack)
    assert fragments == []


def test_birthday_keyword_retrieves_trimmed_l2_fragment():
    pack = load_character("daniya")
    fragments = retrieve(zh(0x751f, 0x65e5), pack)
    assert fragments
    fragment = fragments[0]
    assert fragment["id"] == "birthday_sovereignty"
    assert fragment["level"] == "L2"
    assert len(fragment["content"]) <= fragment["max_chars"] + 3


def test_bubble_keyword_retrieves_bubble_without_l4():
    pack = load_character("daniya")
    fragments = retrieve(zh(0x6ce1, 0x6ce1, 0x788e, 0x4e86), pack)
    ids = [fragment["id"] for fragment in fragments]
    assert "bubble_symbol" in ids
    assert "deep_void_spoiler" not in ids


def test_negative_emotion_retrieves_empathy_overload_only():
    pack = load_character("daniya")
    fragments = retrieve(zh(0x6211, 0x597d, 0x7d2f, 0xff0c, 0x60c5, 0x7eea, 0x6491, 0x4e0d, 0x4f4f), pack)
    ids = [fragment["id"] for fragment in fragments]
    assert "empathy_overload" in ids
    assert "deep_void_spoiler" not in ids


def test_l4_only_when_explicit_story_question():
    pack = load_character("daniya")
    plain = retrieve(zh(0x6211, 0x4eca, 0x5929, 0x6709, 0x70b9, 0x7d2f), pack)
    assert "deep_void_spoiler" not in [fragment["id"] for fragment in plain]

    explicit = retrieve(zh(0x8fbe, 0x59ae, 0x5a05, 0x548c, 0x865a, 0x65e0, 0x3001, 0x6697, 0x9762, 0x5230, 0x5e95, 0x6709, 0x4ec0, 0x4e48, 0x5173, 0x7cfb), pack)
    assert "deep_void_spoiler" in [fragment["id"] for fragment in explicit]
    deep = next(fragment for fragment in explicit if fragment["id"] == "deep_void_spoiler")
    assert len(deep["content"]) <= deep["max_chars"] + 3


def test_missing_lore_index_fields_and_missing_fragment_do_not_crash():
    pack = load_character("daniya")
    broken = dict(pack.lore_index)
    broken["fragments"] = [
        {"id": "missing_fields"},
        {"id": "ghost", "level": "L1", "keywords": ["ghost"], "max_chars": "bad"},
    ]
    ghost_pack = type(
        "Pack",
        (),
        {
            "lore_index": broken,
            "lore": pack.lore,
        },
    )()
    assert retrieve("ghost", ghost_pack) == [
        {
            "id": "ghost",
            "title": "ghost",
            "level": "L1",
            "content": "",
            "source": "keyword",
            "max_chars": 220,
            "warning": "lore fragment not found: ghost",
        }
    ]
    assert extract_fragment(pack.lore, "not_exists", {"keywords": ["not_exists"]}) == ""
