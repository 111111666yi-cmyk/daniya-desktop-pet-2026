from core.daniya_status import build_daniya_status, render_daniya_status_text


def test_daniya_status_is_readonly_summary():
    status = build_daniya_status("daniya", available_actions={"idle", "talk", "happy", "clicked", "drag", "remind"})
    assert status["loaded"] is True
    assert status["validation_ok"] is True
    assert status["character_summary"]["id"] == "daniya"
    assert status["speech_summary"]["special_response_ids"]
    assert "relationship_stage" in status["relationship_state"]
    assert any(action["id"] == "close_idle" for action in status["actions"])
    assert any(fragment["id"] == "birthday_orange_cake" for fragment in status["lore_fragments"])


def test_daniya_status_text_contains_required_readonly_sections():
    text = render_daniya_status_text(build_daniya_status("daniya"))
    assert "达妮娅设定 / v0.415 只读状态" in text
    assert "[character.yaml]" in text
    assert "[speech.yaml]" in text
    assert "[relationship_state.json]" in text
    assert "[event_log 最近记录]" in text
    assert "[user_memory.json]" in text
    assert "[actions.yaml]" in text
    assert "[lore_index.yaml]" in text
