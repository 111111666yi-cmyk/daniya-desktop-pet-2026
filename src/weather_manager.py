from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable

import requests
from PySide6.QtCore import QObject, QThread, QTimer, Signal


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class WeatherSnapshot:
    temperature_c: float
    weather_code: int
    description: str
    precipitation_mm: float
    is_raining: bool
    observed_at: str
    source: str = "Open-Meteo"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WeatherError(RuntimeError):
    pass


def fetch_weather(
    latitude: float,
    longitude: float,
    timeout: float = 5.0,
    request_get: Callable[..., Any] = requests.get,
) -> WeatherSnapshot:
    response = request_get(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": float(latitude),
            "longitude": float(longitude),
            "current": "temperature_2m,weather_code,precipitation,rain,showers",
            "timezone": "auto",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise WeatherError("天气服务返回了无法解析的数据。") from exc
    return parse_weather_payload(payload)


def parse_weather_payload(payload: Any) -> WeatherSnapshot:
    if not isinstance(payload, dict) or not isinstance(payload.get("current"), dict):
        raise WeatherError("天气服务缺少 current 数据。")
    current = payload["current"]
    try:
        temperature = float(current.get("temperature_2m"))
        weather_code = int(current.get("weather_code"))
        precipitation = max(0.0, float(current.get("precipitation", 0.0) or 0.0))
        rain = max(0.0, float(current.get("rain", 0.0) or 0.0))
        showers = max(0.0, float(current.get("showers", 0.0) or 0.0))
    except (TypeError, ValueError) as exc:
        raise WeatherError("天气服务返回的数值无效。") from exc
    observed_at = str(current.get("time") or datetime.now().isoformat(timespec="minutes"))
    is_raining = (
        weather_code in _RAIN_CODES
        or precipitation > 0
        or rain > 0
        or showers > 0
    )
    return WeatherSnapshot(
        temperature_c=temperature,
        weather_code=weather_code,
        description=_weather_description(weather_code),
        precipitation_mm=precipitation,
        is_raining=is_raining,
        observed_at=observed_at,
    )


class _WeatherWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, latitude: float, longitude: float) -> None:
        super().__init__()
        self.latitude = latitude
        self.longitude = longitude

    def run(self) -> None:
        try:
            snapshot = fetch_weather(self.latitude, self.longitude)
        except (requests.RequestException, WeatherError, OSError) as exc:
            self.failed.emit(f"天气读取失败：{exc}")
            return
        self.succeeded.emit(snapshot.to_dict())


class WeatherManager(QObject):
    snapshot_ready = Signal(object)
    request_failed = Signal(str)

    def __init__(
        self,
        *,
        enabled: bool = False,
        location_configured: bool = False,
        latitude: float = 0.0,
        longitude: float = 0.0,
        interval_seconds: int = 1800,
    ) -> None:
        super().__init__()
        self.enabled = bool(enabled)
        self.location_configured = bool(location_configured)
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.interval_seconds = max(900, int(interval_seconds))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self._worker: _WeatherWorker | None = None
        self.set_enabled(self.enabled)

    def configure(
        self,
        *,
        location_configured: bool,
        latitude: float,
        longitude: float,
        interval_seconds: int,
    ) -> None:
        self.location_configured = bool(location_configured)
        self.latitude = max(-90.0, min(90.0, float(latitude)))
        self.longitude = max(-180.0, min(180.0, float(longitude)))
        self.interval_seconds = max(900, min(21600, int(interval_seconds)))
        if self.timer.isActive():
            self.timer.start(self.interval_seconds * 1000)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if self.enabled:
            self.timer.start(self.interval_seconds * 1000)
        else:
            self.timer.stop()

    def refresh(self, force: bool = False) -> bool:
        if not force and not self.enabled:
            return False
        if not self.location_configured:
            self.request_failed.emit("请先在设置中心确认天气坐标。")
            return False
        if self._worker is not None and self._worker.isRunning():
            return False
        worker = _WeatherWorker(self.latitude, self.longitude)
        self._worker = worker
        worker.succeeded.connect(self._finish_success)
        worker.failed.connect(self._finish_failure)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        return True

    def _finish_success(self, snapshot: object) -> None:
        self.snapshot_ready.emit(snapshot)

    def _finish_failure(self, message: str) -> None:
        self.request_failed.emit(message)

    def _worker_finished(self) -> None:
        self._worker = None

    def shutdown(self, timeout_ms: int = 6000) -> None:
        self.timer.stop()
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(max(0, int(timeout_ms)))


_RAIN_CODES = {
    51,
    53,
    55,
    56,
    57,
    61,
    63,
    65,
    66,
    67,
    80,
    81,
    82,
    95,
    96,
    99,
}


def _weather_description(code: int) -> str:
    if code == 0:
        return "晴朗"
    if code in {1, 2, 3}:
        return "多云"
    if code in {45, 48}:
        return "有雾"
    if code in {51, 53, 55, 56, 57}:
        return "毛毛雨"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "下雨"
    if code in {71, 73, 75, 77, 85, 86}:
        return "下雪"
    if code in {95, 96, 99}:
        return "雷雨"
    return f"天气代码 {code}"
