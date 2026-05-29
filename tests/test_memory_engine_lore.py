from core.memory_engine import load_user_memory, lore_ids_from_text, unlock_lore_fragments, update_memory_from_interaction


def zh(*codes):
    return "".join(chr(code) for code in codes)


def test_lore_ids_from_text_for_required_fragments():
    assert lore_ids_from_text(zh(0x751f, 0x65e5)) == ["birthday_orange_cake"]
    assert lore_ids_from_text(zh(0x6ce1, 0x6ce1, 0x788e, 0x4e86)) == ["bubble_symbol"]
    assert lore_ids_from_text(zh(0x5f52, 0x671f, 0x5230, 0x4e86)) == ["goodbye_name"]


def test_update_memory_records_lore_keywords_without_sensitive_fields():
    memory = update_memory_from_interaction(zh(0x6ce1, 0x6ce1, 0x788e, 0x4e86))
    assert "bubble_symbol" in memory["unlocked_lore"]
    assert "api_key" not in memory


def test_unlock_lore_fragments_dedupes_values():
    unlock_lore_fragments(["birthday_orange_cake", "birthday_orange_cake"])
    memory = load_user_memory()
    assert memory["unlocked_lore"].count("birthday_orange_cake") == 1
