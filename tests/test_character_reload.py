from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from src.app import AppController


class FakeAdapter:
    def __init__(self, model_client, config) -> None:
        resolved = config.character_id if config.character_id in {"daniya", "template"} else "daniya"
        self.character_pack = SimpleNamespace(character_id=resolved)
        self.load_errors = [] if resolved == config.character_id else ["fallback"]
        self.animation_manager = None
        self.state_manager = None


class FakeAssetManager:
    def __init__(self, app_config, character_id) -> None:
        self.app_config = app_config
        self.character_id = character_id


def test_reload_character_persists_resolved_character_and_keeps_runtime_managers(monkeypatch):
    from src import app as app_module

    monkeypatch.setattr(app_module, "DaniyaEngineAdapter", FakeAdapter)
    monkeypatch.setattr(app_module, "AssetManager", FakeAssetManager)

    animation_manager = SimpleNamespace(
        asset_manager=None,
        reload_manifest=Mock(),
        refresh=Mock(),
    )
    behavior_engine = SimpleNamespace(
        reload_config=Mock(),
        idle_behavior=SimpleNamespace(is_allowed=None, is_night=None),
    )
    window = SimpleNamespace(
        clear_render_cache=Mock(),
        asset_manager=None,
        animation_manager=animation_manager,
        behavior_engine=behavior_engine,
    )
    sentinels = {
        "reminder_manager": object(),
        "idle_manager": object(),
        "time_event_manager": object(),
        "feedback_coordinator": object(),
    }
    controller = SimpleNamespace(
        app_config={"current_character": "daniya"},
        config_manager=SimpleNamespace(save_app_config=Mock()),
        chat_client=object(),
        thread_safe_anim_manager=object(),
        window=window,
        settings_window=None,
        is_idle_behavior_allowed=Mock(),
        is_night_behavior=Mock(),
        **sentinels,
    )

    assert AppController.reload_character(controller, "missing-pack") is True

    assert controller.daniya_adapter.character_pack.character_id == "daniya"
    assert controller.app_config["current_character"] == "daniya"
    controller.config_manager.save_app_config.assert_called_once_with(controller.app_config)
    for name, value in sentinels.items():
        assert getattr(controller, name) is value
