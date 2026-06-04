from __future__ import annotations

from unittest.mock import MagicMock
from src.clipboard_interaction import ClipboardInteraction

def test_clipboard_interaction_checks() -> None:
    # Test text filtering rules directly
    inter = ClipboardInteraction()

    # 1. Empty clipboard
    res = inter.check_text("")
    assert not res["ok"]
    assert res["status"] == "empty"

    # 2. Safe short text
    res2 = inter.check_text("hello daniya, how are you?")
    assert res2["ok"]
    assert res2["status"] == "safe"
    assert "help" in res2["message"] or "分析" in res2["message"]

    # 3. Sensitive items (API key, password, phone, ID)
    res_key = inter.check_text("my key is sk-abcdefghijklmnopqrstuvwxyz123456")
    assert not res_key["ok"]
    assert res_key["status"] == "sensitive"
    assert "忽略" in res_key["message"]

    res_bearer = inter.check_text("Authorization: Bearer mytoken12345")
    assert not res_bearer["ok"]
    assert res_bearer["status"] == "sensitive"

    res_pwd = inter.check_text("password = secret_p@ssw0rd")
    assert not res_pwd["ok"]
    assert res_pwd["status"] == "sensitive"

    res_phone = inter.check_text("我的电话是13812345678")
    assert not res_phone["ok"]
    assert res_phone["status"] == "sensitive"

    # 4. Too long text
    long_txt = "a" * 1500
    res_long = inter.check_text(long_txt)
    assert res_long["ok"]
    assert res_long["status"] == "too_long"
    assert res_long["clean_text"] == ""

    preview = ClipboardInteraction(show_preview=True, max_chars=500)
    res_preview = preview.check_text(long_txt)
    assert len(res_preview["clean_text"]) == 500

def test_clipboard_interaction_signals() -> None:
    # Mock PySide6 Clipboard object
    mock_clip = MagicMock()
    mock_clip.text.return_value = "hello world"

    inter = ClipboardInteraction(mock_clip)
    
    # Track signal emits
    emitted = []
    inter.clipboard_alert.connect(emitted.append)

    # 1. Enabled check
    inter.set_enabled(True)
    inter.on_clipboard_change()
    assert len(emitted) == 1
    assert emitted[0]["status"] == "safe"

    # 2. Duplicate check (last_text equals current clipboard text, should not emit again)
    inter.on_clipboard_change()
    assert len(emitted) == 1

    # 3. Disabled check
    inter.set_enabled(False)
    mock_clip.text.return_value = "something else"
    inter.on_clipboard_change()
    assert len(emitted) == 1  # Should not emit when disabled
