from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import QPoint

from .motion_catalog import LocomotionProfile


@dataclass(frozen=True)
class LocomotionStep:
    position: QPoint
    distance_moved_px: float
    cumulative_distance_px: float
    speed_px_per_s: float
    arrived: bool


class LocomotionController:
    def __init__(self, profile: LocomotionProfile | None = None) -> None:
        self.profile = profile or LocomotionProfile()
        self.target: QPoint | None = None
        self.active = False
        self._speed_px_per_s = 0.0
        self._cumulative_distance_px = 0.0

    @property
    def cumulative_distance_px(self) -> float:
        return self._cumulative_distance_px

    def start(self, start: QPoint, target: QPoint) -> None:
        self.target = QPoint(target)
        self.active = True
        self._speed_px_per_s = min(self.profile.default_speed_px_per_s, self.profile.max_speed_px_per_s)
        self._cumulative_distance_px = 0.0

    def cancel(self) -> None:
        self.target = None
        self.active = False
        self._speed_px_per_s = 0.0
        self._cumulative_distance_px = 0.0

    def update_profile(self, profile: LocomotionProfile | None) -> None:
        self.profile = profile or LocomotionProfile()

    def step(self, current: QPoint, dt_ms: int) -> LocomotionStep | None:
        if not self.active or self.target is None:
            return None

        dx = float(self.target.x() - current.x())
        dy = float(self.target.y() - current.y())
        remaining = math.hypot(dx, dy)
        if remaining <= 1.5:
            self.active = False
            self._speed_px_per_s = 0.0
            return LocomotionStep(QPoint(self.target), 0.0, self._cumulative_distance_px, 0.0, True)

        dt_s = max(0.001, dt_ms / 1000.0)
        desired_speed = self._desired_speed(remaining)
        accel_px_per_s2 = 260.0
        delta = accel_px_per_s2 * dt_s
        if self._speed_px_per_s < desired_speed:
            self._speed_px_per_s = min(desired_speed, self._speed_px_per_s + delta)
        else:
            self._speed_px_per_s = max(desired_speed, self._speed_px_per_s - delta)

        step_distance = min(remaining, self._speed_px_per_s * dt_s)
        nx = current.x() + int(round(dx / remaining * step_distance))
        ny = current.y() + int(round(dy / remaining * step_distance))
        next_pos = QPoint(nx, ny)

        actual_dx = float(next_pos.x() - current.x())
        actual_dy = float(next_pos.y() - current.y())
        moved = math.hypot(actual_dx, actual_dy)
        self._cumulative_distance_px += moved

        arrived = math.hypot(self.target.x() - next_pos.x(), self.target.y() - next_pos.y()) <= 2.5
        if arrived:
            next_pos = QPoint(self.target)
            self.active = False
            self._speed_px_per_s = 0.0

        return LocomotionStep(
            position=next_pos,
            distance_moved_px=moved,
            cumulative_distance_px=self._cumulative_distance_px,
            speed_px_per_s=self._speed_px_per_s,
            arrived=arrived,
        )

    def _desired_speed(self, remaining_px: float) -> float:
        if remaining_px <= self.profile.stop_distance_px:
            return self.profile.min_speed_px_per_s
        if remaining_px >= self.profile.cycle_distance_px * 2:
            return self.profile.max_speed_px_per_s
        ramp = remaining_px / max(1.0, self.profile.cycle_distance_px * 2)
        speed = self.profile.min_speed_px_per_s + (
            (self.profile.max_speed_px_per_s - self.profile.min_speed_px_per_s) * ramp
        )
        return max(self.profile.min_speed_px_per_s, min(self.profile.max_speed_px_per_s, speed))
