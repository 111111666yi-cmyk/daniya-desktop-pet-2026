from __future__ import annotations

import time
from collections.abc import Callable


class FeedbackCoordinator:
    """Coordinate non-essential bubble, action, and sound feedback."""

    def __init__(
        self,
        *,
        show_text: Callable[[str], None],
        trigger_action: Callable[[str], None],
        return_to_idle: Callable[[], None],
        is_dragging: Callable[[], bool],
        is_settings_open: Callable[[], bool],
        is_user_busy: Callable[[], bool],
        is_talking: Callable[[], bool],
        is_focus_suppressed: Callable[[str], bool],
        play_sound: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        default_cooldown_seconds: float = 3.0,
    ) -> None:
        self.show_text = show_text
        self.trigger_action = trigger_action
        self.return_to_idle = return_to_idle
        self.is_dragging = is_dragging
        self.is_settings_open = is_settings_open
        self.is_user_busy = is_user_busy
        self.is_talking = is_talking
        self.is_focus_suppressed = is_focus_suppressed
        self.play_sound = play_sound
        self.clock = clock
        self.default_cooldown_seconds = max(0.0, float(default_cooldown_seconds))
        self._cooldown_until = 0.0
        self._active_source: str | None = None

    @property
    def is_active(self) -> bool:
        return self._active_source is not None

    def present(
        self,
        *,
        source: str,
        text: str,
        action: str,
        sound: str | None = None,
        focus_config_key: str | None = None,
        cooldown_seconds: float | None = None,
    ) -> bool:
        clean_text = text.strip()
        if not clean_text:
            return False
        if focus_config_key and self.is_focus_suppressed(focus_config_key):
            return False
        if (
            self.is_active
            or self.is_dragging()
            or self.is_settings_open()
            or self.is_user_busy()
            or self.is_talking()
        ):
            return False

        now = self.clock()
        if now < self._cooldown_until:
            return False

        cooldown = self.default_cooldown_seconds if cooldown_seconds is None else max(0.0, float(cooldown_seconds))
        self._active_source = source
        self._cooldown_until = now + cooldown
        self.trigger_action(action)
        if sound and self.play_sound is not None:
            self.play_sound(sound)
        self.show_text(clean_text)
        return True

    def complete(self) -> None:
        if not self.is_active:
            return
        self._active_source = None
        self.return_to_idle()
