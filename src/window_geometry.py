"""Screen geometry helpers using Qt logical device-independent coordinates."""

from __future__ import annotations

import os
from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QGuiApplication


FALLBACK_SCREEN = QRect(0, 0, 1920, 1080)
HEADLESS_QPA_PLATFORMS = {"offscreen", "minimal", "minimalegl"}


def available_screen_geometries() -> list[QRect]:
    configured_platform = os.environ.get("QT_QPA_PLATFORM", "").split(":", 1)[0].strip().lower()
    if configured_platform in HEADLESS_QPA_PLATFORMS:
        return [QRect(FALLBACK_SCREEN)]
    app = QGuiApplication.instance()
    if app is None:
        return [QRect(FALLBACK_SCREEN)]
    try:
        if str(app.platformName()).lower() in HEADLESS_QPA_PLATFORMS:
            return [QRect(FALLBACK_SCREEN)]
        screens = [QRect(screen.availableGeometry()) for screen in app.screens()]
    except RuntimeError:
        return [QRect(FALLBACK_SCREEN)]
    return normalize_geometries(screens)


def normalize_geometries(geometries: Sequence[QRect]) -> list[QRect]:
    valid = [QRect(rect) for rect in geometries if rect.isValid() and not rect.isEmpty()]
    return valid or [QRect(FALLBACK_SCREEN)]


def virtual_bounds(geometries: Sequence[QRect]) -> QRect:
    screens = normalize_geometries(geometries)
    bounds = QRect(screens[0])
    for screen in screens[1:]:
        bounds = bounds.united(screen)
    return bounds


def window_rect(position: QPoint, size: QSize) -> QRect:
    return QRect(position, QSize(max(1, size.width()), max(1, size.height())))


def visible_area(rect: QRect, geometries: Sequence[QRect]) -> int:
    total = max(1, rect.width() * rect.height())
    area = sum(_rect_area(rect.intersected(screen)) for screen in normalize_geometries(geometries))
    return min(total, area)


def visibility_ratio(rect: QRect, geometries: Sequence[QRect]) -> float:
    total = max(1, rect.width() * rect.height())
    return visible_area(rect, geometries) / total


def geometry_for_window(position: QPoint, size: QSize, geometries: Sequence[QRect]) -> QRect:
    screens = normalize_geometries(geometries)
    rect = window_rect(position, size)
    intersections = [(_rect_area(rect.intersected(screen)), index, screen) for index, screen in enumerate(screens)]
    best_area, _, best_screen = max(intersections, key=lambda item: (item[0], -item[1]))
    if best_area > 0:
        return QRect(best_screen)
    center = rect.center()
    return QRect(min(screens, key=lambda screen: _distance_squared_to_rect(center, screen)))


def geometry_for_point(point: QPoint, geometries: Sequence[QRect]) -> QRect:
    screens = normalize_geometries(geometries)
    for screen in screens:
        if screen.contains(point):
            return QRect(screen)
    return QRect(min(screens, key=lambda screen: _distance_squared_to_rect(point, screen)))


def clamp_to_geometry(position: QPoint, size: QSize, geometry: QRect) -> QPoint:
    width = max(1, size.width())
    height = max(1, size.height())
    min_x = geometry.left()
    max_x = max(min_x, geometry.right() + 1 - width)
    min_y = geometry.top()
    max_y = max(min_y, geometry.bottom() + 1 - height)
    return QPoint(
        max(min_x, min(max_x, position.x())),
        max(min_y, min(max_y, position.y())),
    )


def ensure_fully_visible(position: QPoint, size: QSize, geometries: Sequence[QRect]) -> QPoint:
    screens = normalize_geometries(geometries)
    rect = window_rect(position, size)
    if visible_area(rect, screens) >= rect.width() * rect.height():
        return QPoint(position)
    target = geometry_for_window(position, size, screens)
    return clamp_to_geometry(position, size, target)


def _rect_area(rect: QRect) -> int:
    if rect.isNull() or rect.isEmpty():
        return 0
    return max(0, rect.width()) * max(0, rect.height())


def _distance_squared_to_rect(point: QPoint, rect: QRect) -> int:
    if point.x() < rect.left():
        dx = rect.left() - point.x()
    elif point.x() > rect.right():
        dx = point.x() - rect.right()
    else:
        dx = 0
    if point.y() < rect.top():
        dy = rect.top() - point.y()
    elif point.y() > rect.bottom():
        dy = point.y() - rect.bottom()
    else:
        dy = 0
    return dx * dx + dy * dy
