from __future__ import annotations

from copy import deepcopy
import json

from src.config_manager import DEFAULT_APP_CONFIG, ConfigManager, QUIET_DEFAULTS_MIGRATION, deep_merge
from tools.check_config_templates import _check_quiet_defaults, _check_setup_defaults


def test_default_app_config_is_quiet_by_default() -> None:
    pet = DEFAULT_APP_CONFIG["pet"]

    assert DEFAULT_APP_CONFIG["idle_chat_enabled"] is False
    assert DEFAULT_APP_CONFIG["hourly_chime_enabled"] is False
    assert DEFAULT_APP_CONFIG["idle_behavior_enabled"] is False
    assert DEFAULT_APP_CONFIG["idle_behavior_seconds"] == 600
    assert pet["edge_peek_enabled"] is False
    assert DEFAULT_APP_CONFIG["quiet_defaults_migration"] == QUIET_DEFAULTS_MIGRATION


def test_app_config_normalization_clamps_idle_behavior_delay() -> None:
    manager = ConfigManager.__new__(ConfigManager)
    config = deep_merge(DEFAULT_APP_CONFIG, {"idle_behavior_seconds": 9})

    normalized = manager._normalize_app_config(config)

    assert normalized["idle_behavior_seconds"] == 600


def test_config_template_check_rejects_noisy_defaults() -> None:
    noisy = deepcopy(DEFAULT_APP_CONFIG)
    noisy["idle_chat_enabled"] = True
    noisy["hourly_chime_enabled"] = True
    noisy["idle_behavior_enabled"] = True
    noisy["idle_behavior_seconds"] = 90
    noisy["pet"]["edge_peek_enabled"] = True

    failures = _check_quiet_defaults("config/app_config.json", noisy)

    assert any("idle_chat_enabled=false" in failure for failure in failures)
    assert any("hourly_chime_enabled=false" in failure for failure in failures)
    assert any("idle_behavior_enabled=false" in failure for failure in failures)
    assert any("pet.edge_peek_enabled=false" in failure for failure in failures)
    assert any("idle_behavior_seconds >= 600" in failure for failure in failures)


def test_setup_template_check_rejects_skipped_first_run_or_future_toggles() -> None:
    failures = _check_setup_defaults(
        "config/setup_config.json",
        {
            "first_run_setup": True,
            "run_mode": "api_cloud",
            "multimodal_enabled": {
                "tts": True,
                "text_to_image": False,
                "image_to_image": True,
                "video": False,
            },
        },
    )

    assert any("first_run_setup=false" in failure for failure in failures)
    assert any("run_mode='local_fallback'" in failure for failure in failures)
    assert any("multimodal_enabled.tts=false" in failure for failure in failures)
    assert any("multimodal_enabled.image_to_image=false" in failure for failure in failures)


def test_legacy_noisy_config_is_migrated_once_to_quiet_defaults() -> None:
    manager = ConfigManager.__new__(ConfigManager)
    legacy = deepcopy(DEFAULT_APP_CONFIG)
    legacy.pop("quiet_defaults_migration")
    legacy["idle_chat_enabled"] = True
    legacy["hourly_chime_enabled"] = True
    legacy["idle_behavior_enabled"] = True
    legacy["idle_behavior_seconds"] = 9
    legacy["pet"]["edge_peek_enabled"] = True

    migrated = manager._apply_quiet_defaults_migration(legacy)

    assert migrated["idle_chat_enabled"] is False
    assert migrated["hourly_chime_enabled"] is False
    assert migrated["idle_behavior_enabled"] is False
    assert migrated["idle_behavior_seconds"] == 600
    assert migrated["pet"]["edge_peek_enabled"] is False
    assert migrated["quiet_defaults_migration"] == QUIET_DEFAULTS_MIGRATION


def test_quiet_defaults_migration_preserves_post_migration_user_choices() -> None:
    manager = ConfigManager.__new__(ConfigManager)
    config = deepcopy(DEFAULT_APP_CONFIG)
    config["quiet_defaults_migration"] = QUIET_DEFAULTS_MIGRATION
    config["idle_chat_enabled"] = True
    config["hourly_chime_enabled"] = True
    config["idle_behavior_enabled"] = True
    config["idle_behavior_seconds"] = 900
    config["pet"]["edge_peek_enabled"] = True

    migrated = manager._apply_quiet_defaults_migration(config)

    assert migrated["idle_chat_enabled"] is True
    assert migrated["hourly_chime_enabled"] is True
    assert migrated["idle_behavior_enabled"] is True
    assert migrated["idle_behavior_seconds"] == 900
    assert migrated["pet"]["edge_peek_enabled"] is True


def test_load_app_config_migrates_legacy_runtime_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("src.config_manager.runtime_root", lambda: tmp_path)
    monkeypatch.setattr("src.config_manager.bundled_root", lambda: tmp_path / "bundle")
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    legacy = deepcopy(DEFAULT_APP_CONFIG)
    legacy.pop("quiet_defaults_migration")
    legacy["idle_chat_enabled"] = True
    legacy["hourly_chime_enabled"] = True
    legacy["idle_behavior_enabled"] = True
    legacy["idle_behavior_seconds"] = 9
    legacy["pet"]["edge_peek_enabled"] = True
    (config_dir / "app_config.json").write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

    manager = ConfigManager()
    loaded = manager.load_app_config()

    assert loaded["idle_chat_enabled"] is False
    assert loaded["hourly_chime_enabled"] is False
    assert loaded["idle_behavior_enabled"] is False
    assert loaded["idle_behavior_seconds"] == 600
    assert loaded["pet"]["edge_peek_enabled"] is False
    assert loaded["quiet_defaults_migration"] == QUIET_DEFAULTS_MIGRATION
