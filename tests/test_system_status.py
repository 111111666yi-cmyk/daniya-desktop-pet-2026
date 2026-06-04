from __future__ import annotations

import time
from unittest.mock import MagicMock
import pytest
from src import system_status as status_module
from src.system_status import SystemStatusManager

def test_system_status_sampling_and_alerts(monkeypatch) -> None:
    # 1. Mock psutil metrics
    mock_psutil = MagicMock()
    monkeypatch.setattr(status_module, "psutil", mock_psutil)

    # Set normal values
    mock_psutil.cpu_percent.return_value = 15.0
    mock_psutil.virtual_memory.return_value.percent = 45.0
    mock_psutil.sensors_battery.return_value = MagicMock(percent=85.0, power_plugged=True)
    mock_psutil.disk_usage.return_value.percent = 30.0

    # Instantiate manager with 1s cooldown for fast testing
    manager = SystemStatusManager(sample_interval_ms=10_000, cooldown_seconds=1)
    manager.timer.stop()  # Stop QTimer in tests

    # Mock network status
    monkeypatch.setattr(manager, "is_network_online", lambda: True)

    # Track signals
    alerts = []
    manager.status_alert.connect(lambda t, msg: alerts.append((t, msg)))

    # Run check under normal values
    manager.check_status()
    assert len(alerts) == 0

    # 2. Test CPU High Load Alert
    mock_psutil.cpu_percent.return_value = 95.0
    manager.check_status()
    assert len(alerts) == 1
    assert alerts[0][0] == "cpu"
    assert "CPU" in alerts[0][1]

    # 3. Test Cooldown Effect (should block duplicate alert)
    manager.check_status()
    assert len(alerts) == 1  # No new alert due to cooldown

    # Fast-forward cooldown (1s cooldown set in manager)
    time.sleep(1.1)
    manager.check_status()
    assert len(alerts) == 2  # Alert sent again after cooldown

    # 4. Test Memory High Load Alert
    # Fast-forward cooldown again
    time.sleep(1.1)
    mock_psutil.cpu_percent.return_value = 10.0
    mock_psutil.virtual_memory.return_value.percent = 92.0
    manager.check_status()
    assert len(alerts) == 3
    assert alerts[2][0] == "memory"
    assert "内存快满了" in alerts[2][1]

    # 5. Test Low Battery Alert
    time.sleep(1.1)
    mock_psutil.virtual_memory.return_value.percent = 40.0
    mock_psutil.sensors_battery.return_value = MagicMock(percent=15.0, power_plugged=False)
    manager.check_status()
    assert len(alerts) == 4
    assert alerts[3][0] == "battery"
    assert "电量只剩" in alerts[3][1]

    # 6. Test Offline Alert
    time.sleep(1.1)
    mock_psutil.sensors_battery.return_value = MagicMock(percent=15.0, power_plugged=True)  # Charging now
    manager.network_check_enabled = True
    monkeypatch.setattr(manager, "is_network_online", lambda: False)
    manager.check_status()
    assert len(alerts) == 5
    assert alerts[4][0] == "network"
    assert "网络断开了" in alerts[4][1]

    # 7. Test Disabled Manager (no alert should trigger)
    time.sleep(1.1)
    manager.set_enabled(False)
    monkeypatch.setattr(manager, "is_network_online", lambda: False)
    manager.check_status()
    assert len(alerts) == 5  # Alert count remains same
