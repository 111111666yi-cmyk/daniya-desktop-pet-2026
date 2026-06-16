from __future__ import annotations

from types import SimpleNamespace

import src.menu_manager as menu_manager_module
from src.menu_manager import MenuManager


def test_show_story_dialog_uses_native_book_reader(monkeypatch, tmp_path) -> None:
    story_file = tmp_path / "story.yaml"
    story_file.write_text(
        "chapters:\n- id: 0\n  title: 测试\n  body: 内容\n",
        encoding="utf-8",
    )

    pack = SimpleNamespace(character_root=tmp_path)
    adapter = SimpleNamespace(character_pack=pack)
    controller = SimpleNamespace(daniya_adapter=adapter)
    manager = MenuManager(window=object(), controller=controller)

    exec_calls: list[bool] = []

    class FakeStoryLandingWindow:
        def __init__(self, ctrl, parent):
            self.ctrl = ctrl
        def exec(self):
            exec_calls.append(True)

    monkeypatch.setattr(menu_manager_module, "StoryLandingWindow", FakeStoryLandingWindow)

    manager.show_story_dialog()

    assert exec_calls == [True]
