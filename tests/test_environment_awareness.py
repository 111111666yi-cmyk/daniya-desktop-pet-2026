from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from PIL import Image

from src.ambient_event_theater import AmbientEventTheater
from src.media_presence import detect_supported_player
from src.weather_manager import (
    OPEN_METEO_FORECAST_URL,
    WeatherError,
    WeatherManager,
    fetch_weather,
    parse_weather_payload,
)


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return

    def json(self) -> object:
        return self.payload


def test_weather_payload_marks_rain_and_maps_wmo_description() -> None:
    snapshot = parse_weather_payload(
        {
            "current": {
                "temperature_2m": 22.5,
                "weather_code": 63,
                "precipitation": 1.2,
                "rain": 1.2,
                "showers": 0,
                "time": "2026-06-12T01:00",
            }
        }
    )

    assert snapshot.description == "下雨"
    assert snapshot.is_raining is True
    assert snapshot.temperature_c == 22.5
    assert snapshot.source == "Open-Meteo"


def test_weather_fetch_uses_official_no_key_endpoint() -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _FakeResponse(
            {
                "current": {
                    "temperature_2m": 18,
                    "weather_code": 1,
                    "precipitation": 0,
                    "rain": 0,
                    "showers": 0,
                    "time": "2026-06-12T01:00",
                }
            }
        )

    snapshot = fetch_weather(31.2304, 121.4737, request_get=fake_get)

    assert captured["url"] == OPEN_METEO_FORECAST_URL
    assert captured["params"]["latitude"] == 31.2304
    assert "api_key" not in captured["params"]
    assert snapshot.is_raining is False


def test_weather_manager_requires_explicit_location_confirmation() -> None:
    manager = WeatherManager(enabled=False, location_configured=False)
    errors: list[str] = []
    manager.request_failed.connect(errors.append)

    assert manager.refresh(force=True) is False
    assert errors == ["请先在设置中心确认天气坐标。"]


def test_weather_payload_rejects_missing_current_data() -> None:
    with pytest.raises(WeatherError):
        parse_weather_payload({})


def test_media_presence_only_reports_allow_listed_process_names() -> None:
    assert detect_supported_player(["explorer.exe", "Spotify.exe"]) == "Spotify"
    assert detect_supported_player(["chrome.exe", "unknown-player.exe"]) == ""


def test_ambient_theater_is_opt_in_and_avoids_immediate_repeat(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / "character"
    catalog.mkdir()
    (catalog / "ambient_events.json").write_text(
        json.dumps(
            {
                "events": [
                    {"id": "one", "text": "第一条", "action": "keep"},
                    {"id": "two", "text": "第二条", "action": "happy"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    theater = AmbientEventTheater(
        enabled=False,
        catalog_root=catalog,
        chooser=random.Random(1),
    )

    assert theater.trigger_once() is None
    first = theater.trigger_once(force=True)
    second = theater.trigger_once(force=True)

    assert first is not None
    assert second is not None
    assert first["id"] != second["id"]


def test_weather_umbrella_asset_has_transparency() -> None:
    path = Path(__file__).resolve().parents[1] / "assets" / "icons" / "weather_umbrella.png"
    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")

    assert image.size == (128, 128)
    assert alpha.getextrema()[0] == 0
    assert alpha.getextrema()[1] == 255
