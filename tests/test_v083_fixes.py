"""S1-S4 修复的回归测试（v0.83）。

覆盖：
  S1 — quit() 统一清理：停全部 manager/timer/worker、保存、关弹窗、退出路径不抛异常
  S2 — TTS 物理事件语音接入：click/drag/reminder 触发 voice_router.play_pet_event
  S3 — 单实例锁：_acquire_single_instance_lock 第二次占用失败
  S4 — run() 首启崩溃反馈：AppController 初始化失败时走 critical 弹窗 + sys.exit(1)
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from src.app import AppController, _acquire_single_instance_lock


@pytest.fixture()
def mock_app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> QApplication:
    """构造 offscreen QApplication + 隔离 runtime root（自包含，不依赖其它测试文件）。"""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "relation"))

    first_run_file = tmp_path / "data" / "first_run_done.json"
    first_run_file.parent.mkdir(parents=True, exist_ok=True)
    first_run_file.write_text('{"first_run_complete": true}', encoding="utf-8")

    app = QApplication.instance() or QApplication(sys.argv)
    return app


# 复用项目现有风格：真实构造 AppController（offscreen），再按需注入 mock。
@pytest.fixture()
def controller(mock_app_env: QApplication) -> AppController:
    return AppController(mock_app_env)


# ---------------------------------------------------------------------------
# S1 — quit() 统一清理
# ---------------------------------------------------------------------------

def _timer_driven_managers(controller: AppController) -> list[tuple[str, object]]:
    """收集 controller 上所有 QTimer 驱动的后台 manager（用于断言 timer 已停）。"""
    pairs = []
    for attr in (
        "system_status_manager",
        "focus_mode_manager",
        "idle_manager",
        "time_event_manager",
        "media_presence_manager",
        "ambient_event_theater",
    ):
        mgr = getattr(controller, attr, None)
        if mgr is not None and hasattr(mgr, "timer"):
            pairs.append((attr, mgr))
    return pairs


def test_s1_quit_stops_all_timer_managers(controller: AppController) -> None:
    """S1: quit() 后所有后台 manager 的 QTimer 都应停止。"""
    managers = _timer_driven_managers(controller)
    # 至少应该识别到若干 timer manager（防御性下限）
    assert len(managers) >= 3, f"未识别到足够的 timer manager: {[a for a, _ in managers]}"

    controller.quit()

    for attr, mgr in managers:
        assert not mgr.timer.isActive(), f"quit() 后 {attr}.timer 仍在运行"


def test_s1_quit_calls_weather_shutdown(controller: AppController) -> None:
    """S1: quit() 应调用 weather_manager.shutdown()（含等飞行 worker）。"""
    weather = getattr(controller, "weather_manager", None)
    if weather is None:
        pytest.skip("weather_manager 未初始化（可能默认禁用）")
    # 记录原始 timer 状态后调用
    controller.quit()
    assert not weather.timer.isActive(), "weather_manager.timer 退出后仍运行"


def test_s1_quit_never_raises_on_manager_error(controller: AppController) -> None:
    """S1 关键：退出路径必须永不抛异常。

    即便某个 manager.stop/shutdown 抛异常，quit() 仍应正常返回（否则用户退出反而崩溃）。
    注意：异常防护在 quit()->_shutdown_background_managers 层（每步 try/except），
    而非 _stop_timer_manager 裸函数——后者保持纯粹，由调用方负责兜底。
    用一个 timer.stop 会抛异常的对象替换 manager，验证 quit() 整体不被它拖垮。
    """
    class _BadTimer:
        def __init__(self) -> None:
            class _T:
                def stop(self) -> None:
                    raise RuntimeError("simulated stop failure")

            self.timer = _T()

    controller.system_status_manager = _BadTimer()

    # 完整 quit() 不应被坏 manager 拖垮
    controller.quit()


def test_s1_quit_clears_reminder_boxes(controller: AppController) -> None:
    """S1: quit() 应清空 reminder_boxes 列表。"""
    controller.reminder_boxes.append(MagicMock())
    controller.reminder_boxes.append(MagicMock())
    assert len(controller.reminder_boxes) == 2

    controller.quit()

    assert controller.reminder_boxes == []


# ---------------------------------------------------------------------------
# S2 — TTS 物理事件语音接入
# ---------------------------------------------------------------------------

def test_s2_voice_play_event_dispatches_to_router(controller: AppController) -> None:
    """S2: _voice_play_event 应转发给 voice_router.play_pet_event。"""
    mock_router = MagicMock()
    controller.voice_router = mock_router

    controller._voice_play_event("pet_click")
    mock_router.play_pet_event.assert_called_once_with("pet_click", None)

    controller._voice_play_event("reminder", text="该喝水了")
    mock_router.play_pet_event.assert_called_with("reminder", "该喝水了")


def test_s2_voice_play_event_noop_without_router(controller: AppController) -> None:
    """S2: voice_router 未初始化时不抛异常（首启安全）。"""
    # 确保没有 voice_router 属性
    if hasattr(controller, "voice_router"):
        del controller.voice_router

    # 不应抛异常
    controller._voice_play_event("pet_click")
    controller._voice_play_event("reminder", text="x")


def test_s2_drag_event_triggers_voice(controller: AppController) -> None:
    """S2: _fire_drag_event 应触发 drag 类语音（验证接入点存在）。"""
    mock_router = MagicMock()
    controller.voice_router = mock_router

    # _fire_drag_event 内部先 _voice_play_event 再 _fire_physical_event；
    # 用 mock 避免真起 worker
    controller._pending_phys_events.clear()
    controller._fire_drag_event()

    mock_router.play_pet_event.assert_called_once_with("pet_drag", None)


# ---------------------------------------------------------------------------
# S3 — 单实例锁
# ---------------------------------------------------------------------------

def test_s3_single_instance_lock_second_acquire_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """S3: 已持锁时第二次 bind 同端口应失败 → 返回 False。

    用真实 socket 占住端口，验证 _acquire_single_instance_lock 的冲突检测。
    """
    import src.app as app_module

    # 重置模块级锁状态，确保干净的起点
    monkeypatch.setattr(app_module, "_SINGLE_INSTANCE_LOCK", None)

    # 先用独立 socket 占住目标端口，模拟"已有实例在跑"
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", app_module._SINGLE_INSTANCE_PORT))
    try:
        # 第二次占用应失败
        result = _acquire_single_instance_lock()
        assert result is False
    finally:
        holder.close()

    # 释放后应能成功占用
    monkeypatch.setattr(app_module, "_SINGLE_INSTANCE_LOCK", None)
    result = _acquire_single_instance_lock()
    assert result is True


def test_s3_single_instance_lock_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """S3: 已持锁时再次调用直接返回 True（幂等）。"""
    import src.app as app_module
    fake_lock = MagicMock()
    monkeypatch.setattr(app_module, "_SINGLE_INSTANCE_LOCK", fake_lock)

    assert _acquire_single_instance_lock() is True


# ---------------------------------------------------------------------------
# S4 — run() 首启崩溃反馈
# ---------------------------------------------------------------------------

def test_s4_report_fatal_startup_error(
    mock_app_env: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S4: 首启崩溃反馈函数应弹 critical + 写日志。

    run() 整体含阻塞的 FirstRunWizard，不宜直接单测；改为测抽出的纯函数
    _report_fatal_startup_error。它被 run() 的 except 分支调用。
    """
    import src.app as app_module

    critical_calls: list[tuple] = []
    monkeypatch.setattr(
        app_module.QMessageBox,
        "critical",
        lambda *a, **k: critical_calls.append(a),
    )

    logger = MagicMock()
    app_module._report_fatal_startup_error(logger)

    # 应弹 1 次 critical
    assert len(critical_calls) == 1, f"期望弹 1 次 critical，实际 {len(critical_calls)}"
    # 标题应是"达妮娅启动失败"
    assert critical_calls[0][1] == "达妮娅启动失败"
    # 应写日志（含 traceback）
    logger.exception.assert_called_once()
    call_msg = logger.exception.call_args[0][0]
    assert "fatal" in call_msg and "AppController" in call_msg


def test_s4_report_fatal_content_mentions_log_file(
    mock_app_env: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S4: 错误提示正文应引导用户查看 logs\\app.log（console=False 下唯一线索）。"""
    import src.app as app_module

    critical_calls: list[tuple] = []
    monkeypatch.setattr(
        app_module.QMessageBox,
        "critical",
        lambda *a, **k: critical_calls.append(a),
    )

    app_module._report_fatal_startup_error(MagicMock())

    body_text = critical_calls[0][2]
    assert "logs" in body_text and "app.log" in body_text
