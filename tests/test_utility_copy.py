from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.character_loader import load_character
from core.utility_copy import utility_text
from src.clipboard_interaction import ClipboardInteraction
from src.reminder_manager import ReminderManager
from src.system_status import SystemStatusManager


def test_daniya_utility_copy_is_loaded_from_character_pack() -> None:
    pack = load_character("daniya")

    assert utility_text(pack, "focus_enter").startswith("……")
    assert "API" not in utility_text(pack, "clipboard_sensitive")
    assert "Provider" not in utility_text(pack, "clipboard_sensitive")
    assert "剧情模式" not in "\n".join(pack.speech["utility_responses"].values())
    assert "御主" not in "\n".join(pack.speech["utility_responses"].values())


def test_utility_copy_has_neutral_fallback_for_other_characters() -> None:
    pack = SimpleNamespace(speech={})

    assert utility_text(pack, "reminder_due", text="喝水") == "时间到了：喝水。"


def test_utility_copy_reaches_reminder_clipboard_and_system_status(tmp_path, monkeypatch) -> None:
    from src.config_manager import ConfigManager

    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    pack = load_character("daniya")
    lookup = lambda key, **values: utility_text(pack, key, **values)

    reminder = ReminderManager(ConfigManager())
    reminder.timer.stop()
    reminder.set_message_lookup(lookup)
    ok, message = reminder.add("2026-06-05 20:00", "喝水")
    assert ok is True
    assert message == "……记下了。到时间我会叫你。"

    clipboard = ClipboardInteraction()
    clipboard.message_lookup = lookup
    sensitive = clipboard.check_text("token = abcdefghijklmnop")
    assert sensitive["status"] == "sensitive"
    assert "不会显示、保存" in sensitive["message"]

    status = SystemStatusManager()
    status.timer.stop()
    status.message_lookup = lookup
    assert status._message("system_cpu", "", value="95") == "……CPU 使用率到 95% 了。先看看是不是有程序占得太多。"
