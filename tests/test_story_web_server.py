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


def test_menu_manager_opens_bundled_story_site(monkeypatch, tmp_path) -> None:
    root = tmp_path / "story"
    root.mkdir()
    (root / "index.html").write_text("<title>story</title>", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr(menu_manager_module, "resource_path", lambda *_parts: root)
    monkeypatch.setattr(
        menu_manager_module.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )
    manager = MenuManager(window=object(), controller=object())

    try:
        assert manager._open_story_site() is True
        assert opened == [manager._story_web_server.url()]
    finally:
        manager._story_web_server.close()


def test_story_command_falls_back_when_site_cannot_open(monkeypatch) -> None:
    manager = MenuManager(window=object(), controller=object())
    fallback_calls: list[bool] = []
    monkeypatch.setattr(manager, "_open_story_site", lambda: False)
    monkeypatch.setattr(
        manager,
        "_show_legacy_story_dialog",
        lambda: fallback_calls.append(True),
    )

    manager.show_story_dialog()

    assert fallback_calls == [True]
