from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.app import AppController
from src.config_manager import ConfigManager, DEFAULT_APP_CONFIG
from src.growth_dialog import GrowthDialog
from src.growth_manager import GrowthManager


def _catalog(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "items.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "snack",
                        "name": "测试点心",
                        "price": 10,
                        "growth": 65,
                        "affinity": 2,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "outfits.json").write_text(
        json.dumps(
            {
                "outfits": [
                    {
                        "id": "default",
                        "name": "默认服装",
                        "price": 0,
                        "required_level": 1,
                        "required_affinity": 0,
                    },
                    {
                        "id": "ribbon",
                        "name": "测试发带",
                        "price": 40,
                        "required_level": 2,
                        "required_affinity": 35,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _manager(monkeypatch, tmp_path: Path) -> GrowthManager:
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path / "runtime"))
    config_manager = ConfigManager()
    app_config = config_manager.load_app_config()
    catalog = tmp_path / "catalog"
    _catalog(catalog)
    return GrowthManager(config_manager, app_config, catalog_root=catalog)


def test_growth_is_disabled_by_default_and_blocks_state_changes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager = _manager(monkeypatch, tmp_path)

    assert DEFAULT_APP_CONFIG["growth"]["enabled"] is False
    assert manager.is_enabled() is False
    assert manager.claim_daily(date(2026, 6, 12)).ok is False
    assert manager.buy_item("snack").ok is False
    assert manager.feed("snack").ok is False
    assert manager.snapshot()["coins"] == 100


def test_daily_shop_feed_and_level_progression_are_pure_local(
    monkeypatch,
    tmp_path: Path,
) -> None:
    manager = _manager(monkeypatch, tmp_path)
    manager.set_enabled(True)

    assert manager.claim_daily(date(2026, 6, 12)).ok is True
    assert manager.claim_daily(date(2026, 6, 12)).ok is False
    assert manager.buy_item("snack").ok is True
    result = manager.feed("snack")
    state = manager.snapshot()

    assert result.ok is True
    assert result.affinity_delta == 2
    assert state["level"] == 2
    assert state["experience"] == 5
    assert state["coins"] == 115
    assert manager.state_path == manager.config_manager.data_dir / "growth_state.json"
    assert manager.state_path.exists()


def test_outfit_unlock_requires_growth_and_affinity(monkeypatch, tmp_path: Path) -> None:
    manager = _manager(monkeypatch, tmp_path)
    manager.set_enabled(True)

    assert manager.buy_outfit("ribbon", affinity=34).ok is False
    manager.buy_item("snack")
    manager.feed("snack")
    assert manager.buy_outfit("ribbon", affinity=35).ok is True
    assert manager.equip_outfit("ribbon", affinity=35).ok is True
    assert manager.snapshot(affinity=35)["equipped_outfit"] == "ribbon"


def test_broken_catalog_and_state_fall_back_without_crashing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path / "runtime"))
    config_manager = ConfigManager()
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "items.json").write_text("{broken", encoding="utf-8")
    (catalog / "outfits.json").write_text("[]", encoding="utf-8")
    config_manager.data_dir.mkdir(parents=True, exist_ok=True)
    (config_manager.data_dir / "growth_state.json").write_text(
        "{broken",
        encoding="utf-8",
    )
    manager = GrowthManager(
        config_manager,
        config_manager.load_app_config(),
        catalog_root=catalog,
    )

    assert manager.items() == []
    assert manager.outfits() == []
    assert manager.snapshot()["level"] == 1
    assert list(config_manager.data_dir.glob("growth_state.json.broken-*"))


def test_growth_dialog_exposes_opt_in_and_local_state(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path / "runtime"))
    app = QApplication.instance() or QApplication([])
    controller = AppController(app)
    dialog = GrowthDialog(controller)
    try:
        assert dialog.enabled.isChecked() is False
        assert "已关闭" in dialog.status.text()

        dialog.enabled.click()

        assert controller.growth_manager.is_enabled() is True
        assert controller.config_manager.load_app_config()["growth"]["enabled"] is True
        assert dialog.daily_button.isEnabled() is True
    finally:
        dialog.close()
        controller.window.close()
