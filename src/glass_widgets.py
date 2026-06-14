"""Reusable Liquid Glass widget system for PySide6.

Provides GlassWidget (light) and GlassWidgetStrong (heavy blur) base classes
that paint Apple-style frosted glass material over a shared backdrop-blur pixmap.
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    QEasingCurve,
    Signal,
)
from PySide6.QtCore import QPoint
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintEvent


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    p = QPainterPath()
    p.addRoundedRect(rect, radius, radius)
    return p


_GLOW_CACHE: dict[tuple[int, int, int], QPixmap] = {}


def _glow_sprite(r: int, g: int, b: int) -> QPixmap:
    """A soft radial-glow sprite for one colour, rendered once and cached.

    Blitting a pre-rendered sprite is far cheaper than building a QRadialGradient
    per particle per frame, and the soft falloff reads as a real glow."""
    key = (r, g, b)
    pm = _GLOW_CACHE.get(key)
    if pm is None:
        size = 48
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        pp = QPainter(pm)
        pp.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QRadialGradient(size / 2, size / 2, size / 2)
        grad.setColorAt(0.0, QColor(r, g, b, 255))
        grad.setColorAt(0.30, QColor(r, g, b, 160))
        grad.setColorAt(0.65, QColor(r, g, b, 50))
        grad.setColorAt(1.0, QColor(r, g, b, 0))
        pp.setPen(Qt.PenStyle.NoPen)
        pp.setBrush(grad)
        pp.drawEllipse(0, 0, size, size)
        pp.end()
        _GLOW_CACHE[key] = pm
    return pm


class GlassWidget(QWidget):
    """Light liquid-glass material (blur 6px, alpha 0.02).

    Reads the host window's ``_bg_blur`` pixmap and ``_glass_tint`` float,
    crops the region under this widget, then layers frosted tint, specular
    highlight, gradient rim, and optional mouse-follow glow.

    Subclass or set ``radius`` to control corner rounding.
    Set ``mouse_glow = True`` to enable the radial follow-highlight.
    """

    radius: float = 12.0
    mouse_glow: bool = False

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, self.mouse_glow)
        self.setMouseTracking(self.mouse_glow)
        self._glow_pos = QPointF(0, 0)
        self._glow_visible = False

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def _tint(self) -> float:
        return getattr(self.window(), "_glass_tint", 0.5)

    def _blur_pixmap(self) -> QPixmap | None:
        blur = getattr(self.window(), "_bg_blur", None)
        if blur is not None and not blur.isNull():
            return blur
        return None

    # Depth of the refractive edge lip (px). Strong glass uses a thicker lip.
    _edge_inset: float = 1.5

    def _paint_glass(self, p: QPainter, rect: QRectF, path: QPainterPath) -> None:
        t = self._tint()
        p.setClipPath(path)

        blur = self._blur_pixmap()
        if blur is not None:
            tl = self.mapTo(self.window(), QPoint(0, 0))
            p.setOpacity(1.0 - t * 0.30)
            p.drawPixmap(-tl.x(), -tl.y(), blur)
            p.setOpacity(1.0)

        # Frosted body — brighter at top, faint cool tint mid for glass depth.
        top_a = int(14 + t * 70)
        bot_a = int(6 + t * 46)
        fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        fill.setColorAt(0.0, QColor(255, 255, 255, top_a))
        fill.setColorAt(0.5, QColor(244, 247, 255, int(bot_a * 0.7)))
        fill.setColorAt(1.0, QColor(255, 255, 255, bot_a))
        p.fillPath(path, fill)

        # Top specular sheen — short, crisp.
        spec_a = int(24 + t * 78)
        spec = QLinearGradient(
            rect.topLeft(),
            QPointF(rect.left(), rect.top() + rect.height() * 0.45),
        )
        spec.setColorAt(0.0, QColor(255, 255, 255, spec_a))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, spec)

        if self.mouse_glow and self._glow_visible:
            glow = QRadialGradient(self._glow_pos, 200.0)
            glow.setColorAt(0.0, QColor(255, 255, 255, int(16 + t * 18)))
            glow.setColorAt(0.7, QColor(255, 255, 255, 0))
            p.fillPath(path, glow)

        p.setClipping(False)

        # Refractive inner edge — bright top lip + bottom counter-light. This
        # is the signature liquid-glass "thick edge catching light" look.
        ei = self._edge_inset
        inner_rect = rect.adjusted(ei, ei, -ei, -ei)
        inner = rounded_path(inner_rect, max(1.0, self.radius - ei))
        inner_g = QLinearGradient(inner_rect.topLeft(), inner_rect.bottomLeft())
        inner_g.setColorAt(0.0, QColor(255, 255, 255, int(55 + t * 120)))
        inner_g.setColorAt(0.16, QColor(255, 255, 255, 0))
        inner_g.setColorAt(0.84, QColor(255, 255, 255, 0))
        inner_g.setColorAt(1.0, QColor(255, 255, 255, int(26 + t * 64)))
        p.setPen(QPen(QBrush(inner_g), 1.0))
        p.drawPath(inner)

        # Outer rim — defines the silhouette.
        rim_top = int(78 + t * 78)
        rim_mid = int(20 + t * 28)
        rim_bot = int(38 + t * 52)
        rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, rim_top))
        rim.setColorAt(0.5, QColor(255, 255, 255, rim_mid))
        rim.setColorAt(1.0, QColor(255, 255, 255, rim_bot))
        p.setPen(QPen(QBrush(rim), 1.0))
        p.drawPath(path)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = rounded_path(rect, self.radius)
        self._paint_glass(p, rect, path)
        p.end()

    def enterEvent(self, event: object) -> None:
        self._glow_visible = True
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        self._glow_visible = False
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.mouse_glow:
            self._glow_pos = event.position()
            self.update()
        super().mouseMoveEvent(event)


class GlassWidgetStrong(GlassWidget):
    """Heavy liquid-glass material (blur 60px, alpha 0.04).

    Same painting pipeline as GlassWidget but with deeper frosting,
    stronger shadow and more prominent specular.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    _edge_inset: float = 2.0

    def _paint_glass(self, p: QPainter, rect: QRectF, path: QPainterPath) -> None:
        t = self._tint()
        p.setClipPath(path)

        blur = self._blur_pixmap()
        if blur is not None:
            tl = self.mapTo(self.window(), QPoint(0, 0))
            p.setOpacity(1.0 - t * 0.20)
            p.drawPixmap(-tl.x(), -tl.y(), blur)
            p.setOpacity(1.0)

        top_a = int(26 + t * 88)
        bot_a = int(12 + t * 64)
        fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        fill.setColorAt(0.0, QColor(255, 255, 255, top_a))
        fill.setColorAt(0.5, QColor(243, 246, 255, int(bot_a * 0.75)))
        fill.setColorAt(1.0, QColor(255, 255, 255, bot_a))
        p.fillPath(path, fill)

        spec_a = int(36 + t * 84)
        spec = QLinearGradient(
            rect.topLeft(),
            QPointF(rect.left(), rect.top() + rect.height() * 0.42),
        )
        spec.setColorAt(0.0, QColor(255, 255, 255, spec_a))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, spec)

        if self.mouse_glow and self._glow_visible:
            glow = QRadialGradient(self._glow_pos, 200.0)
            glow.setColorAt(0.0, QColor(255, 255, 255, int(22 + t * 22)))
            glow.setColorAt(0.7, QColor(255, 255, 255, 0))
            p.fillPath(path, glow)

        p.setClipping(False)

        # Refractive inner edge — pronounced for heavy glass.
        ei = self._edge_inset
        inner_rect = rect.adjusted(ei, ei, -ei, -ei)
        inner = rounded_path(inner_rect, max(1.0, self.radius - ei))
        inner_g = QLinearGradient(inner_rect.topLeft(), inner_rect.bottomLeft())
        inner_g.setColorAt(0.0, QColor(255, 255, 255, int(80 + t * 140)))
        inner_g.setColorAt(0.15, QColor(255, 255, 255, 0))
        inner_g.setColorAt(0.85, QColor(255, 255, 255, 0))
        inner_g.setColorAt(1.0, QColor(255, 255, 255, int(40 + t * 80)))
        p.setPen(QPen(QBrush(inner_g), 1.3))
        p.drawPath(inner)

        rim_top = int(104 + t * 56)
        rim_mid = int(28 + t * 35)
        rim_bot = int(52 + t * 48)
        rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, rim_top))
        rim.setColorAt(0.5, QColor(255, 255, 255, rim_mid))
        rim.setColorAt(1.0, QColor(255, 255, 255, rim_bot))
        p.setPen(QPen(QBrush(rim), 1.3))
        p.drawPath(path)


class GlassPill(GlassWidgetStrong):
    """Pill-shaped (capsule) glass bar — for navbars and toolbars."""

    @property
    def radius(self) -> float:  # type: ignore[override]
        return self.height() / 2.0


# ── Card Theme Particles ──────────────────────────────────────

_CARD_THEMES = [
    # 0 rain – 没有生日的人
    {"rgb": (160, 190, 220), "bg": ((20, 30, 55), (8, 14, 30)),
     "spawn": "top", "vx": (-0.01, 0.01), "vy": (0.2, 0.4),
     "sz": (0.004, 0.025), "life": (1.5, 3.5),
     "idle": 15, "hover": 40, "draw": "line_v", "wobble": 0.3},
    # 1 fog – 学会伪装不怕
    {"rgb": (180, 200, 190), "bg": ((18, 32, 22), (8, 18, 12)),
     "spawn": "random", "vx": (0.02, 0.05), "vy": (-0.005, 0.005),
     "sz": (0.06, 0.12), "life": (3.0, 6.0),
     "idle": 8, "hover": 18, "draw": "blob", "wobble": 0.0},
    # 2 prism – 影子背后的平衡
    {"rgb": (200, 160, 255), "bg": ((28, 16, 48), (14, 8, 28)),
     "spawn": "random", "vx": (-0.02, 0.02), "vy": (-0.02, 0.02),
     "sz": (0.008, 0.018), "life": (2.0, 5.0),
     "idle": 12, "hover": 30, "draw": "dot", "wobble": 0.0, "rainbow": True},
    # 3 moonlight – 阴影边的
    {"rgb": (170, 190, 240), "bg": ((10, 16, 44), (5, 8, 24)),
     "spawn": "left", "vx": (0.05, 0.12), "vy": (-0.008, 0.008),
     "sz": (0.03, 0.06), "life": (3.0, 5.0),
     "idle": 6, "hover": 14, "draw": "line_h", "wobble": 0.5},
    # 4 dandelion – 愿系于她
    {"rgb": (230, 230, 200), "bg": ((22, 36, 16), (10, 20, 8)),
     "spawn": "bottom", "vx": (-0.015, 0.015), "vy": (-0.12, -0.04),
     "sz": (0.01, 0.02), "life": (3.0, 6.0),
     "idle": 10, "hover": 28, "draw": "cross", "wobble": 0.4},
    # 5 stars – 黑夜群星
    {"rgb": (255, 255, 230), "bg": ((6, 8, 26), (3, 4, 14)),
     "spawn": "random", "vx": (0.0, 0.0), "vy": (0.0, 0.0),
     "sz": (0.005, 0.012), "life": (2.0, 8.0),
     "idle": 15, "hover": 40, "draw": "twinkle", "wobble": 0.0},
    # 6 dawn – 黎明可能
    {"rgb": (255, 200, 100), "bg": ((44, 28, 10), (24, 14, 6)),
     "spawn": "bottom", "vx": (-0.01, 0.02), "vy": (-0.1, -0.03),
     "sz": (0.008, 0.018), "life": (2.0, 5.0),
     "idle": 12, "hover": 30, "draw": "dot", "wobble": 0.2},
    # 7 embers – 灰烬接与归途上
    {"rgb": (255, 130, 40), "bg": ((40, 14, 8), (22, 6, 4)),
     "spawn": "bottom", "vx": (-0.03, 0.03), "vy": (-0.18, -0.06),
     "sz": (0.007, 0.02), "life": (1.5, 3.5),
     "idle": 10, "hover": 28, "draw": "flicker", "wobble": 0.3},
    # 8 sakura – 再见是另一种失
    {"rgb": (255, 180, 200), "bg": ((40, 14, 28), (20, 6, 14)),
     "spawn": "top", "vx": (0.03, 0.08), "vy": (0.06, 0.15),
     "sz": (0.012, 0.025), "life": (2.5, 5.0),
     "idle": 10, "hover": 28, "draw": "petal", "wobble": 0.6},
]


class _Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'size', 'alpha', 'age', 'life', 'phase')

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 size: float, alpha: float, life: float) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.alpha = alpha
        self.age = 0.0
        self.life = life
        self.phase = random.random() * 6.283


class _ParticleField:
    def __init__(self, theme_idx: int) -> None:
        self._cfg = _CARD_THEMES[theme_idx % len(_CARD_THEMES)]
        self.particles: list[_Particle] = []
        self._blend = 0.0
        self._acc = 0.0

    def update(self, dt: float, hovered: bool) -> None:
        tgt = 1.0 if hovered else 0.0
        self._blend += (tgt - self._blend) * min(1.0, dt * 3.0)
        c = self._cfg
        w = c["wobble"]
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.age += dt
            if w:
                p.x += math.sin(p.phase + p.age * 2.5) * w * dt * 0.1

        self.particles = [
            p for p in self.particles
            if p.age < p.life and -0.15 < p.x < 1.15 and -0.15 < p.y < 1.15
        ]

        target = c["idle"] + (c["hover"] - c["idle"]) * self._blend
        deficit = target - len(self.particles)
        if deficit > 0:
            self._acc += dt * deficit * 1.5
            cap = int(target) + 5
            while self._acc >= 1.0 and len(self.particles) < cap:
                self._acc -= 1.0
                self.particles.append(self._spawn())

    def _spawn(self) -> _Particle:
        c = self._cfg
        s = c["spawn"]
        if s == "top":
            x, y = random.random(), -0.05
        elif s == "bottom":
            x, y = random.random(), 1.05
        elif s == "left":
            x, y = -0.05, random.random()
        else:
            x, y = random.random(), random.random()
        return _Particle(
            x, y,
            random.uniform(*c["vx"]), random.uniform(*c["vy"]),
            random.uniform(*c["sz"]), random.uniform(0.4, 1.0),
            random.uniform(*c["life"]),
        )

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        c = self._cfg
        r, g, b = c["rgb"]
        draw = c["draw"]
        rx, ry, rw, rh = rect.x(), rect.y(), rect.width(), rect.height()
        nopen = Qt.PenStyle.NoPen
        sprite = _glow_sprite(r, g, b)
        srect = sprite.rect()

        def blit(cx: float, cy: float, diam: float, opacity: float) -> None:
            painter.setOpacity(max(0.0, min(1.0, opacity)))
            painter.drawPixmap(
                QRectF(cx - diam / 2, cy - diam / 2, diam, diam), sprite, srect,
            )

        for p in self.particles:
            frac = p.age / p.life
            fade = min(1.0, frac * 4.0, (1.0 - frac) * 3.0)
            of = p.alpha * fade
            if of < 0.02:
                continue
            px = rx + p.x * rw
            py = ry + p.y * rh
            sz = p.size * rw
            a = int(of * 255)

            if draw == "line_v":  # rain — glowing streak with a bright head
                painter.setOpacity(of * 0.8)
                painter.setPen(QPen(QColor(r, g, b, 200), max(1.0, sz * 0.32)))
                painter.drawLine(QPointF(px, py), QPointF(px, py + sz * 5))
                blit(px, py + sz * 5, sz * 3.0, of)
            elif draw == "blob":  # fog — large soft volume
                blit(px, py, sz * 5.5, of * 0.5)
            elif draw == "line_h":  # moonlight — drifting horizontal gleam
                wy = py + math.sin(p.phase + p.x * 8) * sz * 2
                painter.setOpacity(of * 0.8)
                painter.setPen(QPen(QColor(r, g, b, 200), max(1.0, sz * 0.4)))
                painter.drawLine(QPointF(px, wy), QPointF(px + sz * 3, wy))
                blit(px + sz * 3, wy, sz * 2.6, of)
            elif draw == "cross":  # dandelion seed — soft 4-point sparkle
                painter.setOpacity(of)
                painter.setPen(QPen(QColor(r, g, b, a), max(1.0, sz * 0.25)))
                painter.drawLine(QPointF(px - sz * 1.4, py), QPointF(px + sz * 1.4, py))
                painter.drawLine(QPointF(px, py - sz * 1.4), QPointF(px, py + sz * 1.4))
                blit(px, py, sz * 2.4, of)
            elif draw == "petal":  # sakura — rotating soft petal
                painter.setOpacity(of)
                painter.setBrush(QColor(r, g, b, a))
                painter.setPen(nopen)
                painter.save()
                painter.translate(px, py)
                painter.rotate(p.phase * 57.3 + p.age * 60)
                painter.drawEllipse(QPointF(0, 0), sz, sz * 0.5)
                painter.restore()
            elif draw == "twinkle":  # stars — slow breathing glow
                tw = 0.35 + 0.65 * abs(math.sin(p.phase + p.age * 2.0))
                blit(px, py, sz * 4.0, of * tw)
            elif draw == "flicker":  # embers — fast flicker glow
                fl = 0.4 + 0.6 * abs(math.sin(p.phase + p.age * 8.0))
                blit(px, py, sz * 3.6, of * fl)
            else:  # prism / default — glowing dot (rainbow tint optional)
                if c.get("rainbow"):
                    hue = (int(p.phase / 6.283 * 12) * 30) % 360  # 12 buckets → bounded cache
                    rc = QColor.fromHsv(hue, 180, 255)
                    blit2 = _glow_sprite(rc.red(), rc.green(), rc.blue())
                    painter.setOpacity(of)
                    d = sz * 3.4
                    painter.drawPixmap(
                        QRectF(px - d / 2, py - d / 2, d, d), blit2, blit2.rect(),
                    )
                else:
                    blit(px, py, sz * 3.4, of)
        painter.setOpacity(1.0)


# ── Card Carousel ─────────────────────────────────────────────

class CardCarousel(QWidget):
    """3D perspective card carousel with drag-to-browse physics and
    per-card themed particle effects.
    """

    card_selected = Signal(int)

    CARD_W = 220
    CARD_H = 300
    CARD_GAP = 60
    PERSPECTIVE_SCALE = 0.78
    DRAG_FRICTION = 0.92

    def __init__(
        self,
        cards: list[dict],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cards = cards
        self._offset: float = 0.0
        self._velocity: float = 0.0
        self._drag_start_x: float | None = None
        self._drag_start_offset: float = 0.0
        self._last_drag_x: float = 0.0
        self._card_pixmaps: dict[int, QPixmap] = {}
        self._hovered_card: int | None = None
        self._last_emitted: int = 0

        self._fields = [_ParticleField(i) for i in range(len(cards))]

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)
        self._anim.finished.connect(self._emit_if_changed)

        self._inertia_timer = QTimer(self)
        self._inertia_timer.setInterval(16)
        self._inertia_timer.timeout.connect(self._tick_inertia)

        self._ptimer = QTimer(self)
        self._ptimer.setInterval(33)
        self._ptimer.timeout.connect(self._tick_particles)

        self.setMinimumHeight(self.CARD_H + 80)
        self.setMouseTracking(True)

    # ── particle lifecycle ──

    def _tick_particles(self) -> None:
        dt = 0.033
        for i, field in enumerate(self._fields):
            rel = i + self._offset
            if abs(rel) < 4:
                field.update(dt, i == self._hovered_card)
        self.update()

    def showEvent(self, event: object) -> None:
        self._ptimer.start()
        super().showEvent(event)

    def hideEvent(self, event: object) -> None:
        self._ptimer.stop()
        super().hideEvent(event)

    # ── public API ──

    def set_card_pixmap(self, index: int, pixmap: QPixmap) -> None:
        self._card_pixmaps[index] = pixmap
        self.update()

    def current_index(self) -> int:
        return max(0, min(round(-self._offset), len(self._cards) - 1))

    def _emit_if_changed(self) -> None:
        """Emit card_selected whenever the centred card changes — live during
        drag/inertia/snap, so the detail panel always tracks the front card."""
        idx = self.current_index()
        if idx != self._last_emitted:
            self._last_emitted = idx
            self.card_selected.emit(idx)

    # ── snap animation ──

    def _snap_to(self, index: int) -> None:
        target = float(-index)
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_anim_value(self, val: object) -> None:
        self._offset = float(val)  # type: ignore[arg-type]
        self.update()
        self._emit_if_changed()

    # ── inertia ──

    def _tick_inertia(self) -> None:
        self._velocity *= self.DRAG_FRICTION
        if abs(self._velocity) < 0.3:
            self._inertia_timer.stop()
            self._snap_to(self.current_index())
            return
        self._offset += self._velocity * 0.016
        n = len(self._cards)
        self._offset = max(-(n - 1), min(0.0, self._offset))
        self._emit_if_changed()
        self.update()

    # ── mouse interaction ──

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._anim.stop()
            self._inertia_timer.stop()
            self._drag_start_x = event.position().x()
            self._drag_start_offset = self._offset
            self._velocity = 0.0
            self._last_drag_x = event.position().x()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start_x is not None:
            dx = event.position().x() - self._drag_start_x
            sensitivity = self.CARD_W + self.CARD_GAP
            self._offset = self._drag_start_offset + dx / sensitivity
            n = len(self._cards)
            self._offset = max(-(n - 1) - 0.3, min(0.3, self._offset))
            self._velocity = (event.position().x() - self._last_drag_x) / sensitivity
            self._last_drag_x = event.position().x()
            self._emit_if_changed()
            self.update()
        else:
            hit = self._hit_test(event.position())
            if hit != self._hovered_card:
                self._hovered_card = hit

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_x is not None:
            if abs(event.position().x() - self._drag_start_x) < 5:
                clicked = self._hit_test(event.position())
                if clicked is not None:
                    self._snap_to(clicked)
                    self._drag_start_x = None
                    return
            self._drag_start_x = None
            if abs(self._velocity) > 0.02:
                self._inertia_timer.start()
            else:
                self._snap_to(self.current_index())

    def leaveEvent(self, event: object) -> None:
        self._hovered_card = None
        super().leaveEvent(event)

    def _hit_test(self, pos: QPointF) -> int | None:
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        for i in reversed(range(len(self._cards))):
            rel = i + self._offset
            x = cx + rel * (self.CARD_W + self.CARD_GAP) * 0.65
            scale = max(0.5, 1.0 - abs(rel) * (1.0 - self.PERSPECTIVE_SCALE))
            w = self.CARD_W * scale
            h = self.CARD_H * scale
            r = QRectF(x - w / 2, cy - h / 2, w, h)
            if r.contains(pos):
                return i
        return None

    # ── paint ──

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        n = len(self._cards)

        draw_order: list[tuple[float, int]] = []
        for i in range(n):
            rel = i + self._offset
            draw_order.append((abs(rel), i))
        draw_order.sort(key=lambda x: -x[0])

        for _, i in draw_order:
            rel = i + self._offset
            if abs(rel) > 4:
                continue

            scale = max(0.5, 1.0 - abs(rel) * (1.0 - self.PERSPECTIVE_SCALE))
            x = cx + rel * (self.CARD_W + self.CARD_GAP) * 0.65
            w = self.CARD_W * scale
            h = self.CARD_H * scale
            card_rect = QRectF(x - w / 2, cy - h / 2, w, h)
            radius = 16.0 * scale
            path = rounded_path(card_rect, radius)

            p.save()
            p.setOpacity(max(0.3, 1.0 - abs(rel) * 0.25))

            # ─ background ─
            pm = self._card_pixmaps.get(i)
            if pm is not None and not pm.isNull():
                p.setClipPath(path)
                p.drawPixmap(card_rect.toRect(), pm)
                p.setClipping(False)
                overlay = QColor(0, 0, 0, int(abs(rel) * 40))
                p.fillPath(path, overlay)
            else:
                theme = _CARD_THEMES[i % len(_CARD_THEMES)]
                bg0, bg1 = theme["bg"]
                grad = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
                grad.setColorAt(0.0, QColor(*bg0, 220))
                grad.setColorAt(1.0, QColor(*bg1, 240))
                p.fillPath(path, grad)

                vig = QRadialGradient(card_rect.center(), max(w, h) * 0.7)
                vig.setColorAt(0.0, QColor(0, 0, 0, 0))
                vig.setColorAt(1.0, QColor(0, 0, 0, 50))
                p.fillPath(path, vig)

            # ─ particles ─
            if i < len(self._fields):
                p.save()
                p.setClipPath(path)
                self._fields[i].paint(p, card_rect)
                p.setClipping(False)
                p.restore()

            # ─ bottom text bar gradient ─
            if abs(rel) < 2:
                bar_h = h * 0.35
                bar_rect = QRectF(card_rect.left(), card_rect.bottom() - bar_h,
                                  card_rect.width(), bar_h)
                p.setClipPath(path)
                bar_grad = QLinearGradient(bar_rect.topLeft(), bar_rect.bottomLeft())
                bar_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
                bar_grad.setColorAt(0.4, QColor(0, 0, 0, 80))
                bar_grad.setColorAt(1.0, QColor(0, 0, 0, 160))
                p.fillRect(bar_rect, bar_grad)
                p.setClipping(False)

            # ─ rim ─
            rim_a = int(60 + (1.0 - abs(rel)) * 80)
            rim = QLinearGradient(card_rect.topLeft(), card_rect.bottomLeft())
            rim.setColorAt(0.0, QColor(255, 255, 255, min(255, rim_a + 40)))
            rim.setColorAt(0.5, QColor(255, 255, 255, rim_a // 3))
            rim.setColorAt(1.0, QColor(255, 255, 255, rim_a // 2))
            p.setPen(QPen(QBrush(rim), 1.5 * scale))
            p.drawPath(path)

            # ─ text ─
            if abs(rel) < 1.5:
                card = self._cards[i]
                font = p.font()

                title = card.get("title", "")
                p.setPen(QColor(255, 255, 255, int(230 * (1.0 - abs(rel) * 0.4))))
                font.setPixelSize(max(10, int(15 * scale)))
                font.setBold(True)
                p.setFont(font)
                text_rect = card_rect.adjusted(
                    14 * scale, h - 55 * scale, -14 * scale, -8 * scale,
                )
                p.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                    title,
                )

                tags = card.get("tags", [])
                time_str = card.get("time", "")
                info = ("  ".join(f"#{t}" for t in tags[:2]) + "  " if tags else "") + time_str
                if info.strip():
                    font.setPixelSize(max(8, int(11 * scale)))
                    font.setBold(False)
                    p.setFont(font)
                    p.setPen(QColor(255, 255, 255, int(150 * (1.0 - abs(rel) * 0.5))))
                    info_rect = card_rect.adjusted(
                        14 * scale, h - 72 * scale, -14 * scale, -52 * scale,
                    )
                    p.drawText(
                        info_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                        info,
                    )

            p.restore()

        p.end()
