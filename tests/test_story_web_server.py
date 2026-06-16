from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

import src.menu_manager as menu_manager_module
from src.menu_manager import MenuManager
from src.story_web_server import StoryWebServer


def test_story_web_server_is_loopback_only_and_serves_assets(tmp_path) -> None:
    root = tmp_path / "story"
    video = root / "assets" / "videos"
    video.mkdir(parents=True)
    (root / "index.html").write_text("<title>达妮娅的故事</title>", encoding="utf-8")
    (video / "daniya_bg.mp4").write_bytes(b"video")
    server = StoryWebServer(root)

    try:
        url = server.url()
        assert url.startswith("http://127.0.0.1:")
        with urlopen(url, timeout=2) as response:
            assert "达妮娅的故事" in response.read().decode("utf-8")
        with urlopen(url.replace("index.html", "assets/videos/daniya_bg.mp4"), timeout=2) as response:
            assert response.read() == b"video"
        assert server.url() == url
    finally:
        server.close()


def test_story_web_server_rejects_missing_site(tmp_path) -> None:
    server = StoryWebServer(tmp_path / "missing")

    try:
        server.url()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing story site must not start a server")


def test_bundled_story_site_uses_local_runtime_dependencies() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "web" / "story_ui" / "index.html"
    ).read_text(encoding="utf-8")

    assert "https://" not in html
    assert "./assets/fonts/fonts.css" in html
    assert "./vendor/tailwindcss-3.4.17.js" in html
    assert "./vendor/react-18.3.1.production.min.js" in html
    assert "./vendor/react-dom-18.3.1.production.min.js" in html
    assert "./vendor/babel-7.29.0.min.js" in html


def test_show_story_dialog_uses_native_book_reader(monkeypatch, tmp_path) -> None:
    story_file = tmp_path / "story.yaml"
    story_file.write_text(
        "chapters:\n- id: 0\n  title: 测试\n  body: 内容\n",
        encoding="utf-8",
    )
    from types import SimpleNamespace

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
