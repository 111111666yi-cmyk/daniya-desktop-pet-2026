from __future__ import annotations

from unittest.mock import Mock
from types import SimpleNamespace

from src.app import AppController
from src.feedback_coordinator import FeedbackCoordinator


def build_coordinator(
    *,
    clock: Mock,
    is_dragging: Mock | None = None,
    is_settings_open: Mock | None = None,
    is_user_busy: Mock | None = None,
    is_talking: Mock | None = None,
    is_focus_suppressed: Mock | None = None,
) -> tuple[FeedbackCoordinator, Mock, Mock, Mock, Mock]:
    show_text = Mock()
    trigger_action = Mock()
    play_sound = Mock()
    return_to_idle = Mock()
    coordinator = FeedbackCoordinator(
        show_text=show_text,
        trigger_action=trigger_action,
        play_sound=play_sound,
        return_to_idle=return_to_idle,
        is_dragging=is_dragging or Mock(return_value=False),
        is_settings_open=is_settings_open or Mock(return_value=False),
        is_user_busy=is_user_busy or Mock(return_value=False),
        is_talking=is_talking or Mock(return_value=False),
        is_focus_suppressed=is_focus_suppressed or Mock(return_value=False),
        clock=clock,
        default_cooldown_seconds=3,
    )
    return coordinator, show_text, trigger_action, play_sound, return_to_idle


def test_passive_feedback_runs_action_sound_and_text_then_returns_idle() -> None:
    clock = Mock(return_value=10.0)
    coordinator, show_text, trigger_action, play_sound, return_to_idle = build_coordinator(clock=clock)

    accepted = coordinator.present(
        source="idle_chat",
        text="……休息一下。",
        action="happy",
        sound="soft",
    )

    assert accepted is True
    trigger_action.assert_called_once_with("happy")
    play_sound.assert_called_once_with("soft")
    show_text.assert_called_once_with("……休息一下。")
    assert coordinator.is_active is True

    coordinator.complete()

    assert coordinator.is_active is False
    return_to_idle.assert_called_once_with()


def test_active_feedback_blocks_overlap_and_global_cooldown() -> None:
    clock = Mock(return_value=10.0)
    coordinator, show_text, _, _, _ = build_coordinator(clock=clock)

    assert coordinator.present(source="idle_chat", text="first", action="happy") is True
    assert coordinator.present(source="system_status", text="overlap", action="remind") is False

    coordinator.complete()
    clock.return_value = 12.0
    assert coordinator.present(source="system_status", text="too soon", action="remind") is False

    clock.return_value = 13.1
    assert coordinator.present(source="system_status", text="ready", action="remind") is True
    assert [call.args[0] for call in show_text.call_args_list] == ["first", "ready"]


def test_interaction_guards_block_passive_feedback() -> None:
    clock = Mock(return_value=20.0)

    for guard_name in ("is_dragging", "is_settings_open", "is_user_busy", "is_talking"):
        guards = {guard_name: Mock(return_value=True)}
        coordinator, show_text, _, _, _ = build_coordinator(clock=clock, **guards)

        assert coordinator.present(source=guard_name, text="blocked", action="remind") is False
        show_text.assert_not_called()


def test_focus_guard_uses_request_specific_config_key() -> None:
    clock = Mock(return_value=30.0)
    focus_guard = Mock(side_effect=lambda key: key == "focus_mode_silence_clipboard")
    coordinator, show_text, _, _, _ = build_coordinator(
        clock=clock,
        is_focus_suppressed=focus_guard,
    )

    assert coordinator.present(
        source="clipboard",
        text="blocked",
        action="remind",
        focus_config_key="focus_mode_silence_clipboard",
    ) is False
    assert coordinator.present(
        source="focus_state",
        text="shown",
        action="idle",
    ) is True
    focus_guard.assert_called_once_with("focus_mode_silence_clipboard")
    show_text.assert_called_once_with("shown")


def test_empty_feedback_is_rejected_without_side_effects() -> None:
    clock = Mock(return_value=40.0)
    coordinator, show_text, trigger_action, play_sound, _ = build_coordinator(clock=clock)

    assert coordinator.present(source="system_status", text="   ", action="remind") is False
    show_text.assert_not_called()
    trigger_action.assert_not_called()
    play_sound.assert_not_called()


def test_app_routes_passive_sources_through_feedback_coordinator() -> None:
    feedback = Mock()
    controller = SimpleNamespace(
        feedback_coordinator=feedback,
        app_config={
            "system_status_enabled": True,
            "clipboard_interaction_enabled": True,
        },
        utility_text=Mock(side_effect=lambda key: key),
    )

    AppController.speak_remind(controller, "hourly")
    AppController.speak_happy(controller, "idle")
    AppController._on_system_status_alert(controller, "cpu", "system")
    AppController._on_clipboard_alert(controller, {"status": "sensitive", "message": "clipboard"})
    AppController._on_focus_state_changed(controller, True)

    assert feedback.present.call_count == 5
    assert feedback.present.call_args_list[0].kwargs["focus_config_key"] == "focus_mode_silence_hourly_chime"
    assert feedback.present.call_args_list[1].kwargs["focus_config_key"] == "focus_mode_silence_idle_chat"
    assert feedback.present.call_args_list[2].kwargs["source"] == "system_status:cpu"
    assert feedback.present.call_args_list[3].kwargs["source"] == "clipboard:sensitive"
    assert feedback.present.call_args_list[4].kwargs["source"] == "focus_enter"


def test_idle_behavior_is_blocked_while_completed_text_is_still_visible() -> None:
    controller = SimpleNamespace(
        _focus_suppresses=Mock(return_value=False),
        _is_feedback_dragging=Mock(return_value=False),
        worker=None,
        window=SimpleNamespace(
            typewriter=SimpleNamespace(is_typing=False),
            bubble=SimpleNamespace(isVisible=Mock(return_value=True)),
            input_box=SimpleNamespace(
                isVisible=Mock(return_value=False),
                hasFocus=Mock(return_value=False),
                text=Mock(return_value=""),
            ),
        ),
        settings_window=None,
        reminder_boxes=[],
    )

    assert AppController.is_idle_behavior_allowed(controller) is False
