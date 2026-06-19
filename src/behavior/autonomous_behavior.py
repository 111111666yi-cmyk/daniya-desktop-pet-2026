from __future__ import annotations

import random
from typing import Any, Callable

from PySide6.QtCore import QObject, QPoint, QTimer, Signal


BEHAVIOR_TABLE: list[dict[str, Any]] = [
    {
        "name": "taskbar_walk",
        "action": "walking",
        "weight": 0.30,
        "min_intensity": "lively",
        "precondition": "near_bottom",
        "move": "taskbar_lateral",
    },
    {
        "name": "taskbar_sit",
        "action": "taskbar_sit",
        "weight": 0.20,
        "min_intensity": "lively",
        "precondition": "near_bottom",
        "move": "taskbar_snap",
    },
    {
        "name": "wall_cling_left",
        "action": "edge_peek_left",
        "weight": 0.10,
        "min_intensity": "lively",
        "precondition": "near_left",
        "move": "wall_snap_left",
    },
    {
        "name": "wall_cling_right",
        "action": "edge_peek_right",
        "weight": 0.10,
        "min_intensity": "lively",
        "precondition": "near_right",
        "move": "wall_snap_right",
    },
    {
        "name": "wander_far",
        "action": "walking",
        "weight": 0.25,
        "min_intensity": "lively",
        "precondition": "any",
        "move": "wander_far",
    },
    {
        "name": "wander_near",
        "action": "walking",
        "weight": 0.35,
        "min_intensity": "quiet",
        "precondition": "any",
        "move": "wander_near",
    },
    {
        "name": "idle_pose",
        "action": "idle",
        "weight": 0.20,
        "min_intensity": "quiet",
        "precondition": "any",
        "move": None,
    },
]

_INTENSITY_ORDER = {"quiet": 0, "lively": 1, "demo": 2}


class AutonomousBehavior(QObject):
    action_requested = Signal(str)
    move_requested = Signal(QPoint)

    def __init__(
        self,
        get_position: Callable[[], QPoint],
        get_screen_bounds: Callable[[], tuple[int, int, int, int]],
        get_window_size: Callable[[], tuple[int, int]],
    ) -> None:
        super().__init__()
        self._get_position = get_position
        self._get_screen_bounds = get_screen_bounds
        self._get_window_size = get_window_size

    def pick_behavior(self, intensity: str = "lively") -> dict[str, Any] | None:
        pos = self._get_position()
        bx, by, bw, bh = self._get_screen_bounds()
        ww, wh = self._get_window_size()
        int_level = _INTENSITY_ORDER.get(intensity, 1)

        eligible = []
        weights = []
        for b in BEHAVIOR_TABLE:
            min_level = _INTENSITY_ORDER.get(b["min_intensity"], 1)
            if int_level < min_level:
                continue
            if not self._check_precondition(b["precondition"], pos, bx, by, bw, bh, ww, wh):
                continue
            eligible.append(b)
            w = b["weight"]
            if intensity == "demo":
                w *= 1.5
            weights.append(w)

        if not eligible:
            return None

        total = sum(weights)
        if total <= 0:
            return None
        pick = random.uniform(0, total)
        upto = 0.0
        for b, w in zip(eligible, weights):
            upto += w
            if pick <= upto:
                return b
        return eligible[-1]

    def compute_move_target(self, behavior: dict[str, Any]) -> QPoint | None:
        move_type = behavior.get("move")
        if not move_type:
            return None

        pos = self._get_position()
        bx, by, bw, bh = self._get_screen_bounds()
        ww, wh = self._get_window_size()
        margin = 40

        if move_type == "taskbar_lateral":
            dx = random.randint(-300, 300)
            tx = max(bx + margin, min(bx + bw - ww - margin, pos.x() + dx))
            ty = by + bh - wh
            return QPoint(tx, ty)

        if move_type == "taskbar_snap":
            ty = by + bh - wh
            return QPoint(pos.x(), ty)

        if move_type == "wall_snap_left":
            return QPoint(bx, pos.y())

        if move_type == "wall_snap_right":
            return QPoint(bx + bw - ww, pos.y())

        if move_type == "wander_far":
            dx = random.randint(-400, 400)
            dy = random.randint(-80, 80)
            tx = max(bx + margin, min(bx + bw - ww - margin, pos.x() + dx))
            ty = max(by + margin, min(by + bh - wh - margin, pos.y() + dy))
            return QPoint(tx, ty)

        if move_type == "wander_near":
            dx = random.randint(-220, 220)
            dy = random.randint(-40, 40)
            tx = max(bx + margin, min(bx + bw - ww - margin, pos.x() + dx))
            ty = max(by + margin, min(by + bh - wh - margin, pos.y() + dy))
            return QPoint(tx, ty)

        return None

    def _check_precondition(
        self,
        precondition: str,
        pos: QPoint,
        bx: int,
        by: int,
        bw: int,
        bh: int,
        ww: int,
        wh: int,
    ) -> bool:
        if precondition == "any":
            return True
        edge_threshold = 80
        if precondition == "near_bottom":
            return pos.y() + wh >= by + bh - edge_threshold
        if precondition == "near_left":
            return pos.x() <= bx + edge_threshold
        if precondition == "near_right":
            return pos.x() + ww >= bx + bw - edge_threshold
        return False
