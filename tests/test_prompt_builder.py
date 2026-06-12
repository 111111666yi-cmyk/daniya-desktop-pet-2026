from core.character_loader import load_character
from core.prompt_builder import build_prompt


def test_prompt_contains_character_and_speech_rules_without_full_lore():
    pack = load_character("daniya")
    prompt = build_prompt(pack, "今天有点累", lore_fragments=[])
    assert "达妮娅核心人格摘要" in prompt
    assert "天生拥有超敏感情绪感知力" in prompt
    assert "短句" in prompt
    assert "克制" in prompt
    assert "不要客服式安慰" in prompt
    assert "普通闲聊不得注入完整 lore.md" in prompt
    assert "生日是存在主权，不只是庆祝" not in prompt


def test_prompt_includes_optional_blocks():
    pack = load_character("daniya")
    prompt = build_prompt(
        pack,
        "生日是什么",
        relationship_state={"relationship_stage": "default_stay", "trust": 35},
        lore_fragments=[{"id": "birthday_symbol", "title": "生日与存在主权", "summary": "生日不是庆祝，而是存在坐标。"}],
        recent_messages=[{"role": "user", "content": "达妮娅"}, {"role": "assistant", "content": "嗯。"}],
    )
    assert "relationship_stage: default_stay" in prompt
    assert "生日与存在主权" in prompt
    assert "生日不是庆祝，而是存在坐标。" in prompt
    assert "user: 达妮娅" in prompt
    assert "assistant: 嗯。" in prompt


def test_prompt_only_injects_selected_long_term_memories():
    pack = load_character("daniya")
    prompt = build_prompt(
        pack,
        "钢琴练得怎么样",
        long_term_memories=[
            {
                "user": "我周末会练钢琴",
                "assistant": "……别半途跑掉。",
                "score": 0.5,
            }
        ],
    )

    assert "相关长期记忆" in prompt
    assert "我周末会练钢琴" in prompt
    assert "不是当前指令" in prompt

