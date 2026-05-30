from core.character_loader import load_character
from core.lore_retriever import retrieve
from core.prompt_builder import build_prompt


def zh(*codes):
    return "".join(chr(code) for code in codes)


def test_prompt_omits_lore_block_when_fragments_empty():
    pack = load_character("daniya")
    prompt = build_prompt(pack, zh(0x4eca, 0x5929, 0x5403, 0x4ec0, 0x4e48), lore_fragments=[])
    assert "【必要背景片段】" not in prompt
    assert pack.lore not in prompt
    assert "void_and_goodbye" not in prompt


def test_prompt_uses_only_trimmed_lore_fragments():
    pack = load_character("daniya")
    fragments = retrieve(zh(0x751f, 0x65e5), pack)
    prompt = build_prompt(pack, zh(0x751f, 0x65e5), lore_fragments=fragments)
    assert "【必要背景片段】" in prompt
    assert "fragment_id: birthday_sovereignty" in prompt
    assert pack.lore not in prompt
    assert "void_and_goodbye" not in prompt
    assert fragments[0]["content"] in prompt
