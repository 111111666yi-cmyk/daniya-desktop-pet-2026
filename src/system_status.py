from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from typing import Any
from PySide6.QtCore import QObject, QTimer, Signal

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

@dataclass
class SystemStatus:
    cpu_percent: float
    memory_percent: float
    battery_percent: float | None
    is_battery_charging: bool | None
    network_online: bool
    disk_percent: float

class SystemStatusManager(QObject):
    status_alert = Signal(str, str)  # alert_type ("cpu", "memory", "battery", "network"), message

    def __init__(self, sample_interval_ms: int = 60_000, cooldown_seconds: int = 300) -> None:
        super().__init__()
        self.sample_interval_ms = sample_interval_ms
        self.cooldown_seconds = cooldown_seconds
        self.enabled = True
        self.last_alert_times: dict[str, float] = {}

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_status)
        # Low frequency sampling, default 60s
        self.timer.start(self.sample_interval_ms)

    def set_enabled(self, val: bool) -> None:
        self.enabled = val
        if val:
            if not self.timer.isActive():
                self.timer.start(self.sample_interval_ms)
        else:
            self.timer.stop()

    def is_network_online(self) -> bool:
        # Check network connectivity quickly without blocking
        try:
            # Try connecting to DNS server
            socket.setdefaulttimeout(1.5)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("8.8.8.8", 53))
            s.close()
            return True
        except Exception:
            return False

    def get_current_status(self) -> SystemStatus:
        cpu = 0.0
        mem = 0.0
        bat_percent = None
        bat_charging = None
        disk = 0.0

        if psutil:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                bat = psutil.sensors_battery()
                if bat:
                    bat_percent = bat.percent
                    bat_charging = bat.power_plugged
                disk = psutil.disk_usage("/").percent
            except Exception:
                pass

        net = self.is_network_online()

        return SystemStatus(
            cpu_percent=cpu,
            memory_percent=mem,
            battery_percent=bat_percent,
            is_battery_charging=bat_charging,
            network_online=net,
            disk_percent=disk
        )

    def check_status(self) -> None:
        if not self.enabled:
            return

        status = self.get_current_status()
        now = time.time()

        # Check CPU
        if status.cpu_percent > 90.0:
            self._trigger_alert("cpu", f"……电脑CPU占用太高了（{status.cpu_percent}%）。你在烤红薯吗？", now)

        # Check Memory
        if status.memory_percent > 90.0:
            self._trigger_alert("memory", f"……内存快满了（{status.memory_percent}%）。要不要关掉一些没用的浏览器标签页？", now)

        # Check Battery
        if status.battery_percent is not None and status.battery_percent < 20.0 and not status.is_battery_charging:
            self._trigger_alert("battery", f"……电量只剩 {status.battery_percent}% 了，还没接电源。等会儿关机了别哭哦。", now)

        # Check Network
        if not status.network_online:
            self._trigger_alert("network", "……网络断开了。是不是网线被家里的猫咬断了？", now)

    def _trigger_alert(self, alert_type: str, message: str, current_time: float) -> None:
        last_time = self.last_alert_times.get(alert_type, 0.0)
        if current_time - last_time >= self.cooldown_seconds:
            self.last_alert_times[alert_type] = current_time
            self.status_alert.emit(alert_type, message)
