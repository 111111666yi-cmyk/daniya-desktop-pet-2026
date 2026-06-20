from __future__ import annotations

from PySide6.QtCore import QPoint

from src.locomotion_controller import LocomotionController
from src.motion_catalog import LocomotionProfile


def test_locomotion_controller_reaches_target_without_overshoot() -> None:
    controller = LocomotionController(LocomotionProfile())
    current = QPoint(0, 0)
    target = QPoint(120, 0)

    controller.start(current, target)
    seen_positions: list[int] = []
    for _ in range(200):
        step = controller.step(current, 33)
        assert step is not None
        current = step.position
        seen_positions.append(current.x())
        assert current.x() <= target.x()
        if step.arrived:
            break

    assert current == target
    assert seen_positions == sorted(seen_positions)
    assert controller.cumulative_distance_px > 0


def test_locomotion_controller_speed_respects_profile_limits() -> None:
    profile = LocomotionProfile(min_speed_px_per_s=48, default_speed_px_per_s=72, max_speed_px_per_s=96)
    controller = LocomotionController(profile)
    controller.start(QPoint(0, 0), QPoint(500, 0))

    speeds: list[float] = []
    current = QPoint(0, 0)
    for _ in range(30):
        step = controller.step(current, 33)
        assert step is not None
        current = step.position
        speeds.append(step.speed_px_per_s)
        if step.arrived:
            break

    assert min(speeds) >= 0.0
    assert max(speeds) <= profile.max_speed_px_per_s + 0.001
