from __future__ import annotations

from core.long_term_memory import LongTermMemoryStore, cosine_similarity, text_vector


def test_vector_similarity_prefers_related_chinese_text() -> None:
    query = text_vector("我明天要继续学钢琴")
    related = text_vector("用户说周末会练钢琴，达妮娅提醒她慢慢练")
    unrelated = text_vector("今天外面下雨，记得带伞")

    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)


def test_store_retrieves_top_k_and_hides_vectors(tmp_path) -> None:
    store = LongTermMemoryStore(tmp_path / "long_term_memory.jsonl")
    store.remember_exchange("我周末要练钢琴", "……那就别半途跑掉。", source="api")
    store.remember_exchange("今天午饭吃面", "……记得别吃太快。", source="api")

    matches = store.retrieve("钢琴练习安排", top_k=1, min_score=0.01)

    assert len(matches) == 1
    assert "钢琴" in matches[0]["user"]
    assert "vector" not in matches[0]
    assert matches[0]["score"] > 0


def test_store_rejects_secret_and_can_clear(tmp_path) -> None:
    store = LongTermMemoryStore(tmp_path / "long_term_memory.jsonl")

    assert store.remember_exchange(
        "API Key: sk-1234567890abcdefgh",
        "收到",
        source="api",
    ) is None
    store.remember_exchange("我喜欢安静", "……知道了。", source="api")
    assert len(store.records()) == 1

    store.clear()

    assert store.records() == []
