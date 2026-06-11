from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from src.window_geometry import (
    FALLBACK_SCREEN,
    available_screen_geometries,
    ensure_fully_visible,
    geometry_for_point,
    geometry_for_window,
    visibility_ratio,
    virtual_bounds,
    window_rect,
)


SCREENS = [
    QRect(0, 0, 1920, 1040),
    QRect(-1280, 0, 1280, 1024),
    QRect(1920, -200, 2560, 1440),
    QRect(0, -1100, 1600, 900),
]


def test_offscreen_platform_does_not_enumerate_native_screens(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    def fail_if_called():
        raise AssertionError("offscreen geometry must not call QGuiApplication.screens()")

    monkeypatch.setattr("src.window_geometry.QGuiApplication.screens", fail_if_called)

    assert available_screen_geometries() == [FALLBACK_SCREEN]


def test_virtual_bounds_include_negative_left_right_and_upper_screens() -> None:
    bounds = virtual_bounds(SCREENS)

    assert bounds.left() == -1280
    assert bounds.top() == -1100
    assert bounds.right() == 4479
    assert bounds.bottom() == 1239


def test_window_selects_screen_with_largest_real_intersection() -> None:
    size = QSize(240, 180)

    assert geometry_for_window(QPoint(-1000, 200), size, SCREENS) == SCREENS[1]
    assert geometry_for_window(QPoint(2300, -100), size, SCREENS) == SCREENS[2]
    assert geometry_for_window(QPoint(300, -900), size, SCREENS) == SCREENS[3]


def test_point_selection_uses_nearest_real_screen_for_gap_coordinates() -> None:
    screens = [QRect(0, 0, 1000, 800), QRect(1400, 0, 1000, 800)]

    assert geometry_for_point(QPoint(1100, 300), screens) == screens[0]
    assert geometry_for_point(QPoint(1350, 300), screens) == screens[1]


def test_clamp_does_not_treat_virtual_desktop_gap_as_visible() -> None:
    screens = [QRect(0, 0, 1000, 800), QRect(1400, 0, 1000, 800)]
    size = QSize(180, 160)
    requested = QPoint(1110, 240)

    repaired = ensure_fully_visible(requested, size, screens)
    repaired_rect = window_rect(repaired, size)

    assert repaired != requested
    assert any(screen.contains(repaired_rect) for screen in screens)
    assert visibility_ratio(window_rect(requested, size), screens) == 0.0


def test_adjacent_cross_screen_window_is_preserved() -> None:
    screens = [QRect(0, 0, 1000, 800), QRect(1000, 0, 1000, 800)]
    size = QSize(200, 160)
    requested = QPoint(900, 240)

    assert visibility_ratio(window_rect(requested, size), screens) == 1.0
    assert ensure_fully_visible(requested, size, screens) == requested


def test_far_offscreen_window_repairs_to_nearest_screen() -> None:
    size = QSize(200, 160)
    repaired = ensure_fully_visible(QPoint(-9000, 9000), size, SCREENS)
    repaired_rect = window_rect(repaired, size)

    assert any(screen.contains(repaired_rect) for screen in SCREENS)
