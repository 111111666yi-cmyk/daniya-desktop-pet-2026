"""Book-style story reader with a 3D page-curl turn and glassmorphism UI."""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_PAGE_CHARS = 320


def _paginate(text: str) -> list[str]:
    """Split chapter body into pages at paragraph boundaries."""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return [text or ""]
    pages: list[str] = []
    buf: list[str] = []
    count = 0
    for line in lines:
        if count + len(line) > _PAGE_CHARS and buf:
            pages.append("\n".join(buf))
            buf = [line]
            count = len(line)
        else:
            buf.append(line)
            count += len(line)
    if buf:
        pages.append("\n".join(buf))
    return pages or [text]


def _chapter_header_html(title: str) -> str:
    """Render chapter title as centered HTML."""
    esc = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<div style="text-align:center; margin:2px 0 18px 0;">'
        f'<p style="font-size:19px; font-weight:bold; color:#26241f;'
        f' margin:0; letter-spacing:1px;">{esc}</p>'
        '<p style="color:#c4a35a; font-size:12px; margin:11px 0 0 0;">'
        "── ✦ ──</p></div>"
    )


def _body_html(text: str) -> str:
    """Render body text as styled, readable HTML paragraphs."""
    parts: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(
            f'<p style="text-indent:2em; line-height:1.95; margin:0.45em 0;'
            f' font-size:14.5px; color:#211f1b;">{esc}</p>'
        )
    return "".join(parts)


# Apple-style font stack (PingFang on macOS, graceful Windows fallbacks).
_FONT_STACK = ["PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"]

# Background color presets shown as swatches in the settings popover.
_BG_PRESETS: list[tuple[str, str]] = [
    ("默认", "preset"),       # deep indigo gradient with light blooms
    ("曜黑", "#0a0a0f"),
    ("云白", "#eef0f4"),
    ("樱粉", "#f6d9e4"),
    ("雾蓝", "#1b2740"),
    ("暖棕", "#241b14"),
]


def _rounded(rect: QRectF, radius: float) -> QPainterPath:
    """A rounded-rectangle path (Apple-ish continuous feel via generous radius)."""
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def _frosted(src: QPixmap, scale: float = 0.08) -> QPixmap:
    """Cheap, fast frosted blur via downscale → smooth upscale."""
    if src.isNull():
        return src
    w = max(1, int(src.width() * scale))
    h = max(1, int(src.height() * scale))
    small = src.scaled(
        w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return small.scaled(
        src.width(), src.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ── 3D page-curl overlay ───────────────────────────────────


class _PageCurl(QWidget):
    """Transient overlay that animates a single leaf curling around the spine."""

    STRIPS = 20
    _CURL = 0.58       # how much the free edge curls past vertical
    _PERSP = 0.16      # vertical foreshorten per unit depth
    _DURATION = 1100

    def __init__(
        self,
        parent: QWidget,
        old_pix: QPixmap,
        new_pix: QPixmap,
        *,
        forward: bool,
        on_done: Callable[[], object],
    ) -> None:
        super().__init__(parent)
        self._forward = forward
        self._on_done = on_done
        # Geometry uses logical px; pixmap.width() returns physical px at high DPI.
        w, h = parent.width(), parent.height()
        self.setGeometry(0, 0, w, h)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._w, self._h = float(w), float(h)
        self._cx = w / 2.0
        self._hw = w / 2.0
        pw, ph = old_pix.width(), old_pix.height()
        phw = pw // 2
        self._old_left = old_pix.copy(0, 0, phw, ph)
        self._old_right = old_pix.copy(phw, 0, pw - phw, ph)
        self._new_left = new_pix.copy(0, 0, phw, ph)
        self._new_right = new_pix.copy(phw, 0, pw - phw, ph)
        self._p = 0.0

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(self._DURATION)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_p)
        self._anim.finished.connect(self._finish)

    def start(self) -> None:
        self.show()
        self.raise_()
        self._anim.start()

    def _set_p(self, v: object) -> None:
        self._p = float(v)
        self.update()

    def _finish(self) -> None:
        cb = self._on_done
        self.hide()
        self.deleteLater()
        cb()

    # ── geometry ──

    def _arc(self, p: float) -> tuple[list[float], list[float], list[float]]:
        """Return per-sample x positions, vertical insets, and rotation angles.

        The leaf rotates about the spine through depth: at p=0 it lies flat on
        its start side, at p=0.5 it stands edge-on (a thin sliver), and at p=1
        it lies flat on the far side. The free edge curls slightly past vertical.
        """
        n = self.STRIPS
        hw, cx, hgt = self._hw, self._cx, self._h
        alpha0 = p * math.pi
        curl = self._CURL * math.sin(p * math.pi)
        dirn = 1.0 if self._forward else -1.0
        xs: list[float] = []
        insets: list[float] = []
        phis: list[float] = []
        for j in range(n + 1):
            s = j / n
            d = s * hw
            alpha = alpha0 + curl * s
            xs.append(cx + dirn * d * math.cos(alpha))
            z = d * math.sin(alpha)
            insets.append(min(max(z, 0.0) * self._PERSP, hgt * 0.42))
            phis.append(alpha)
        return xs, insets, phis

    # ── painting ──

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        hw = int(self._hw)

        # Static background: the half that stays + the half being revealed
        if self._forward:
            p.drawPixmap(0, 0, self._old_left)
            p.drawPixmap(hw, 0, self._new_right)
        else:
            p.drawPixmap(0, 0, self._new_left)
            p.drawPixmap(hw, 0, self._old_right)

        # Soft gutter shadow that deepens as the leaf lifts off the spine.
        sweep = math.sin(self._p * math.pi)
        if sweep > 0.02:
            gx = self._cx
            band = 64.0
            sh = QLinearGradient(gx - band, 0, gx + band, 0)
            sh.setColorAt(0.0, QColor(0, 0, 0, 0))
            sh.setColorAt(0.5, QColor(0, 0, 0, int(80 * sweep)))
            sh.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.fillRect(QRectF(gx - band, 0, 2 * band, self._h), sh)

        # Choose the leaf face and its source-x mapping (spine -> free edge)
        front = self._p < 0.5
        if self._forward and front:
            pix, reverse = self._old_right, False
        elif self._forward:
            pix, reverse = self._new_left, True
        elif front:
            pix, reverse = self._old_left, True
        else:
            pix, reverse = self._new_right, False

        xs, insets, phis = self._arc(self._p)
        self._paint_leaf(p, pix, xs, insets, phis, reverse=reverse)
        p.end()

    def _paint_leaf(
        self,
        p: QPainter,
        pix: QPixmap,
        xs: list[float],
        insets: list[float],
        phis: list[float],
        *,
        reverse: bool,
    ) -> None:
        n = self.STRIPS
        pw, ph = pix.width(), pix.height()
        h = self._h
        sweep = math.sin(self._p * math.pi)  # 0 at rest, 1 at the upright fold

        for i in range(n):
            sl, sr = i / n, (i + 1) / n
            # Source sub-rectangle (reverse maps spine to the pixmap's right edge)
            ax_l = (1.0 - sl) * pw if reverse else sl * pw
            ax_r = (1.0 - sr) * pw if reverse else sr * pw
            src = QPolygonF(
                [
                    QPointF(ax_l, 0.0),
                    QPointF(ax_r, 0.0),
                    QPointF(ax_r, ph),
                    QPointF(ax_l, ph),
                ]
            )
            dst = QPolygonF(
                [
                    QPointF(xs[i], insets[i]),
                    QPointF(xs[i + 1], insets[i + 1]),
                    QPointF(xs[i + 1], h - insets[i + 1]),
                    QPointF(xs[i], h - insets[i]),
                ]
            )
            tf = QTransform()
            if not QTransform.quadToQuad(src, dst, tf):
                continue
            # Clip to this strip's quad so the warped pixmap is not smeared
            # beyond the strip's own slice.
            clip = QPainterPath()
            clip.addPolygon(dst)
            clip.closeSubpath()
            p.save()
            p.setClipPath(clip)
            p.setTransform(tf)
            p.drawPixmap(0, 0, pix)
            p.restore()

            # Per-strip shading: darken as the strip turns edge-on
            facing = abs(math.cos(0.5 * (phis[i] + phis[i + 1])))
            dark = int((1.0 - facing) * 95 * sweep)
            if dark > 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(20, 16, 10, dark))
                p.drawPolygon(dst)
            # Glossy sheen sweeping toward the curling free edge
            if sr > 0.62:
                sheen = int((sr - 0.62) / 0.38 * 70 * sweep)
                if sheen > 0:
                    p.setBrush(QColor(255, 252, 245, sheen))
                    p.drawPolygon(dst)


# ── Painted chrome widgets ─────────────────────────────────


class _BookSpread(QWidget):
    """Two-page book spread with painted paper, spine, and glass edge."""

    turn_forward = Signal()
    turn_backward = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        self.left_browser = QTextBrowser()
        self.left_num = QLabel()
        layout.addWidget(self._make_page(self.left_browser, self.left_num, 34, 18), 1)
        self.right_browser = QTextBrowser()
        self.right_num = QLabel()
        layout.addWidget(self._make_page(self.right_browser, self.right_num, 18, 34), 1)
        self.left_browser.installEventFilter(self)
        self.right_browser.installEventFilter(self)

    @staticmethod
    def _make_page(
        browser: QTextBrowser, num_lbl: QLabel, pad_l: int, pad_r: int
    ) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(pad_l, 24, pad_r, 10)
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet("QTextBrowser{background:transparent; border:none;}")
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(browser, 1)
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_lbl.setStyleSheet("color:#a8a08c; font-size:10px; background:transparent;")
        lay.addWidget(num_lbl)
        return w

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            if obj is self.left_browser:
                self.turn_backward.emit()
                return True
            if obj is self.right_browser:
                self.turn_forward.emit()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().x() < self.width() / 2:
                self.turn_backward.emit()
            else:
                self.turn_forward.emit()

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        for i in range(7):
            sp = QPainterPath()
            sp.addRoundedRect(rect.adjusted(-i, i + 1, i, i + 4), 16, 16)
            p.fillPath(sp, QColor(0, 0, 0, 15 - i * 2))
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
        grad.setColorAt(0.00, QColor(255, 252, 246))
        grad.setColorAt(0.45, QColor(250, 245, 234))
        grad.setColorAt(0.50, QColor(231, 223, 205))
        grad.setColorAt(0.55, QColor(250, 245, 234))
        grad.setColorAt(1.00, QColor(255, 252, 246))
        p.fillPath(path, grad)
        bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg.setColorAt(0.0, QColor(255, 255, 255, 110))
        bg.setColorAt(0.35, QColor(214, 206, 188, 50))
        bg.setColorAt(0.7, QColor(196, 180, 150, 60))
        bg.setColorAt(1.0, QColor(255, 255, 255, 95))
        p.setPen(QPen(QBrush(bg), 1.6))
        p.drawPath(path)
        p.setPen(QPen(QColor(255, 255, 255, 100), 0.7))
        p.drawLine(
            int(rect.left() + 22), int(rect.top() + 3),
            int(rect.right() - 22), int(rect.top() + 3),
        )
        mid_x = int(rect.center().x())
        p.setPen(QPen(QColor(188, 176, 154, 50), 1.0))
        p.drawLine(mid_x, int(rect.top() + 16), mid_x, int(rect.bottom() - 16))
        p.end()


class _ChapterDots(QWidget):
    """Chapter progress indicator rendered as glowing gold dots."""

    def __init__(self, total: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._total = max(total, 1)
        self._current = 0
        self.setFixedHeight(22)

    def set_current(self, idx: int) -> None:
        self._current = idx
        self.update()

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 3.5
        gap = 14.0
        total_w = self._total * (2 * r + gap) - gap
        sx = (self.width() - total_w) / 2
        cy = self.height() / 2.0
        for i in range(self._total):
            cx = sx + i * (2 * r + gap) + r
            if i == self._current:
                glow = QRadialGradient(cx, cy, r + 5)
                glow.setColorAt(0.0, QColor(196, 163, 90, 150))
                glow.setColorAt(1.0, QColor(196, 163, 90, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawEllipse(QRectF(cx - r - 5, cy - r - 5, 2 * r + 10, 2 * r + 10))
                p.setBrush(QColor(214, 180, 100))
                p.drawEllipse(QRectF(cx - r - 1, cy - r - 1, 2 * r + 2, 2 * r + 2))
            elif i < self._current:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(196, 163, 90, 120))
                p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 40), 1.0))
                p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.end()


class _GlassBar(QWidget):
    """Apple Liquid Glass material: blurs and refracts the background behind it.

    Reads the host dialog's pre-blurred background pixmap, crops the region
    sitting under this widget, then layers a frosted tint, a specular highlight
    and a bright hairline rim — the signature translucent-glass look.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 95))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.height() / 2.0  # pill / capsule shape
        path = _rounded(rect, radius)

        dlg = self.window()
        t = getattr(dlg, "_glass_tint", 0.5)

        p.setClipPath(path)
        # 1) Backdrop: blurred background cropped to this widget's position.
        blur = getattr(dlg, "_bg_blur", None)
        if blur is not None and not blur.isNull():
            tl = self.mapTo(dlg, QPoint(0, 0))
            p.setOpacity(1.0 - t * 0.35)
            p.drawPixmap(-tl.x(), -tl.y(), blur)
            p.setOpacity(1.0)
        # 2) Frosted tint — alpha scales with glass tint (clear→thin, tinted→heavy).
        top_a = int(10 + t * 62)
        bot_a = int(5 + t * 42)
        fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        fill.setColorAt(0.0, QColor(255, 255, 255, top_a))
        fill.setColorAt(1.0, QColor(255, 255, 255, bot_a))
        p.fillPath(path, fill)
        # 3) Specular highlight — subtle when clear, prominent when tinted.
        spec_a = int(18 + t * 62)
        spec = QLinearGradient(
            rect.topLeft(), QPointF(rect.left(), rect.top() + rect.height() * 0.6)
        )
        spec.setColorAt(0.0, QColor(255, 255, 255, spec_a))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, spec)
        p.setClipping(False)
        # 4) Liquid-glass rim — scales with tint.
        rim_top = int(80 + t * 75)
        rim_mid = int(22 + t * 28)
        rim_bot = int(40 + t * 50)
        rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, rim_top))
        rim.setColorAt(0.5, QColor(255, 255, 255, rim_mid))
        rim.setColorAt(1.0, QColor(255, 255, 255, rim_bot))
        p.setPen(QPen(QBrush(rim), 1.0))
        p.drawPath(path)
        p.end()


# ── Shared QSS ─────────────────────────────────────────────

_COMBO_SS = (
    "QComboBox { background:rgba(255,255,255,0.10); color:#d9bd7e;"
    "  border:1px solid rgba(255,255,255,0.18); padding:4px 12px;"
    "  border-radius:9px; font-size:12px; min-width:180px; }"
    "QComboBox::drop-down { border:none; width:18px; }"
    "QComboBox QAbstractItemView {"
    "  background:#16162a; color:#d4c5a0; outline:none;"
    "  selection-background-color:rgba(196,163,90,0.30);"
    "  border:1px solid rgba(255,255,255,0.12); border-radius:6px; }"
)

_NAV_BTN = (
    "QPushButton { background:rgba(255,255,255,0.08); color:rgba(255,255,255,0.7);"
    "  border:1px solid rgba(255,255,255,0.20); border-radius:16px; font-size:15px; }"
    "QPushButton:hover { background:rgba(196,163,90,0.30); color:#fff; }"
    "QPushButton:disabled { color:rgba(255,255,255,0.14);"
    "  background:transparent; border-color:rgba(255,255,255,0.06); }"
)

_SEND_BTN = (
    "QPushButton { background:rgba(196,163,90,0.22); color:#e6c885;"
    "  border:1px solid rgba(196,163,90,0.40); padding:5px 16px;"
    "  border-radius:9px; font-size:12px; font-weight:bold; }"
    "QPushButton:hover { background:rgba(196,163,90,0.40); color:#fff; }"
)

_CLOSE_BTN = (
    "QPushButton { background:rgba(255,255,255,0.08); color:rgba(255,255,255,0.55);"
    "  border:1px solid rgba(255,255,255,0.18); padding:5px 18px;"
    "  border-radius:9px; font-size:12px; }"
    "QPushButton:hover { background:rgba(255,255,255,0.16); color:#fff; }"
)

_GHOST_BTN = (
    "QPushButton { background:rgba(255,255,255,0.10); color:rgba(255,255,255,0.7);"
    "  border:1px solid rgba(255,255,255,0.20); padding:4px 13px;"
    "  border-radius:10px; font-size:12px; }"
    "QPushButton:hover { background:rgba(240,215,154,0.28); color:#fff; }"
)


# ── Main dialog ────────────────────────────────────────────


class StoryBookDialog(QDialog):
    """Two-page book reader with a 3D page-curl turn."""

    def __init__(
        self,
        chapters: list[tuple],
        controller: object = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._chapters = chapters
        self._controller = controller
        self._ch_idx = 0
        self._spread_idx = 0
        self._pages: list[str] = []
        self._total_pages = 0
        self._animating = False
        self._curl: _PageCurl | None = None
        self._armed: str | None = None  # "next"/"prev" awaiting a confirming flick
        self._arm_timer = QTimer(self)
        self._arm_timer.setSingleShot(True)
        self._arm_timer.setInterval(1500)
        self._arm_timer.timeout.connect(self._disarm)

        # Background state (persisted under app_config["story_reader"]).
        s = self._load_bg_settings()
        self._bg_kind: str = s["kind"]       # "preset" | "color" | "image"
        self._bg_color: str = s["color"]
        self._bg_image: str = s["image"]
        self._bg_opacity: int = s["opacity"]  # 0-100, applies to image
        self._glass_tint: float = s["glass_tint"]  # 0.0=clear liquid glass, 1.0=frosted
        self._bg_base: QPixmap | None = None
        self._bg_blur: QPixmap | None = None
        self._glass_bars: list[QWidget] = []
        self._popover: QWidget | None = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(100)
        self._resize_timer.timeout.connect(self._rebuild_bg)

        font = QFont()
        font.setFamilies(_FONT_STACK)
        self.setFont(font)

        self._setup_ui()
        self._setup_chapter()
        self._render()
        self._rebuild_bg()

    def _setup_ui(self) -> None:
        self.setWindowTitle("达妮娅的故事")
        self.resize(980, 680)
        self.setMinimumSize(780, 540)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 12)
        root.setSpacing(9)

        # Header — floating capsule with wallpaper previews
        hdr = _GlassBar()
        hdr.setFixedHeight(44)
        self._glass_bars.append(hdr)
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(20, 0, 16, 0)
        title_lbl = QLabel("《再见以前，她学过怎样活着》")
        title_lbl.setStyleSheet(
            "color:#f0d79a; font-size:13px; font-weight:bold; background:transparent;"
        )
        hdr_lay.addWidget(title_lbl)
        hdr_lay.addStretch()
        # Wallpaper preview circles (background presets inline)
        self._swatch_btns: list[tuple[str, QPushButton]] = []
        for label, value in _BG_PRESETS:
            sw = QPushButton()
            sw.setFixedSize(22, 22)
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            sw.setToolTip(label)
            if value == "preset":
                face = (
                    "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                    "stop:0 #2a2848, stop:1 #0c0c18);"
                )
            else:
                face = f"background:{value};"
            active = (
                self._bg_kind == "preset" and value == "preset"
            ) or (self._bg_kind == "color" and self._bg_color == value)
            border = "border:2px solid #f0d79a;" if active else "border:1.5px solid rgba(255,255,255,0.35);"
            sw.setStyleSheet(
                "QPushButton{" + face + border
                + "border-radius:11px;} QPushButton:hover{border-color:#f0d79a;}"
            )
            sw.clicked.connect(self._make_preset_cb(value))
            self._swatch_btns.append((value, sw))
            hdr_lay.addWidget(sw)
        hdr_lay.addSpacing(6)
        self._combo = QComboBox()
        for ch in self._chapters:
            self._combo.addItem(ch[1])
        self._combo.setStyleSheet(_COMBO_SS)
        self._combo.currentIndexChanged.connect(self._on_combo)
        hdr_lay.addWidget(self._combo)
        self._bg_btn = QPushButton("设置")
        self._bg_btn.setStyleSheet(_GHOST_BTN)
        self._bg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bg_btn.clicked.connect(self._open_bg_popover)
        hdr_lay.addWidget(self._bg_btn)
        root.addWidget(hdr)

        # Book
        self._book = _BookSpread()
        self._book.turn_forward.connect(
            lambda: self._request_turn("next", require_confirm=False)
        )
        self._book.turn_backward.connect(
            lambda: self._request_turn("prev", require_confirm=False)
        )
        root.addWidget(self._book, 1)

        # Small fluorescent confirm hint, floating over the book bottom
        self._hint = QLabel(self._book)
        self._hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._hint.hide()

        # Navigation
        nav = _GlassBar()
        nav.setFixedHeight(44)
        self._glass_bars.append(nav)
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(16, 0, 16, 0)
        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedSize(32, 32)
        self._prev_btn.setStyleSheet(_NAV_BTN)
        self._prev_btn.clicked.connect(
            lambda: self._request_turn("prev", require_confirm=False)
        )
        nav_lay.addWidget(self._prev_btn)
        nav_lay.addStretch()
        self._dots = _ChapterDots(len(self._chapters))
        self._dots.setFixedWidth(max(160, len(self._chapters) * 22))
        nav_lay.addWidget(self._dots)
        self._ch_label = QLabel()
        self._ch_label.setStyleSheet(
            "color:rgba(255,255,255,0.45); font-size:11px; background:transparent;"
        )
        nav_lay.addWidget(self._ch_label)
        nav_lay.addStretch()
        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedSize(32, 32)
        self._next_btn.setStyleSheet(_NAV_BTN)
        self._next_btn.clicked.connect(
            lambda: self._request_turn("next", require_confirm=False)
        )
        nav_lay.addWidget(self._next_btn)
        root.addWidget(nav)

        # Prompt / actions
        self._prompt_bar = _GlassBar()
        self._prompt_bar.setFixedHeight(42)
        self._glass_bars.append(self._prompt_bar)
        pb_lay = QHBoxLayout(self._prompt_bar)
        pb_lay.setContentsMargins(18, 0, 18, 0)
        self._prompt_lbl = QLabel()
        self._prompt_lbl.setWordWrap(True)
        self._prompt_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self._prompt_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.55); font-size:12px; background:transparent;"
        )
        pb_lay.addWidget(self._prompt_lbl, 1)
        self._send_btn = QPushButton("发给达妮娅")
        self._send_btn.setStyleSheet(_SEND_BTN)
        self._send_btn.clicked.connect(self._send)
        pb_lay.addWidget(self._send_btn)
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(_CLOSE_BTN)
        close_btn.clicked.connect(self.accept)
        pb_lay.addWidget(close_btn)
        root.addWidget(self._prompt_bar)

    # ── background ──

    def _paint_default_gradient(self, p: QPainter, w: int, h: int) -> None:
        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, QColor(24, 22, 42))
        base.setColorAt(0.5, QColor(14, 13, 28))
        base.setColorAt(1.0, QColor(9, 8, 18))
        p.fillRect(0, 0, w, h, base)
        warm = QRadialGradient(w * 0.5, h * 0.12, w * 0.55)
        warm.setColorAt(0.0, QColor(120, 95, 60, 45))
        warm.setColorAt(1.0, QColor(120, 95, 60, 0))
        p.fillRect(0, 0, w, h, warm)
        cool = QRadialGradient(w * 0.15, h * 0.95, w * 0.5)
        cool.setColorAt(0.0, QColor(70, 80, 150, 40))
        cool.setColorAt(1.0, QColor(70, 80, 150, 0))
        p.fillRect(0, 0, w, h, cool)

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._bg_base is not None and not self._bg_base.isNull():
            p.drawPixmap(0, 0, self._bg_base)
        else:
            self._paint_default_gradient(p, self.width(), self.height())
        p.end()

    def _rebuild_bg(self) -> None:
        """Render the chosen background to a pixmap and a blurred copy."""
        w, h = max(1, self.width()), max(1, self.height())
        base = QPixmap(w, h)
        base.fill(Qt.GlobalColor.black)
        p = QPainter(base)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._bg_kind == "color":
            p.fillRect(0, 0, w, h, QColor(self._bg_color))
        elif self._bg_kind == "image" and self._bg_image:
            self._paint_default_gradient(p, w, h)
            img = QPixmap(self._bg_image)
            if not img.isNull():
                scaled = img.scaled(
                    w, h,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                ox = (scaled.width() - w) // 2
                oy = (scaled.height() - h) // 2
                p.setOpacity(max(0.0, min(1.0, self._bg_opacity / 100.0)))
                p.drawPixmap(0, 0, scaled, ox, oy, w, h)
                p.setOpacity(1.0)
        else:
            self._paint_default_gradient(p, w, h)
        p.end()
        self._bg_base = base
        self._bg_blur = _frosted(base)
        self.update()
        for bar in self._glass_bars:
            bar.update()

    # ── background settings ──

    def _load_bg_settings(self) -> dict:
        cfg: dict = {}
        ctrl = self._controller
        if ctrl is not None:
            app_cfg = getattr(ctrl, "app_config", None)
            if isinstance(app_cfg, dict) and isinstance(app_cfg.get("story_reader"), dict):
                cfg = app_cfg["story_reader"]
        try:
            opacity = int(cfg.get("bg_opacity", 100))
        except (TypeError, ValueError):
            opacity = 100
        try:
            glass_tint = float(cfg.get("glass_tint", 0.5))
        except (TypeError, ValueError):
            glass_tint = 0.5
        return {
            "kind": cfg.get("bg_kind", "preset"),
            "color": cfg.get("bg_color", "#0d0d1a"),
            "image": cfg.get("bg_image", ""),
            "opacity": opacity,
            "glass_tint": glass_tint,
        }

    def _save_bg_settings(self) -> None:
        ctrl = self._controller
        if ctrl is None:
            return
        app_cfg = getattr(ctrl, "app_config", None)
        cm = getattr(ctrl, "config_manager", None)
        if not isinstance(app_cfg, dict) or cm is None:
            return
        app_cfg["story_reader"] = {
            "bg_kind": self._bg_kind,
            "bg_color": self._bg_color,
            "bg_image": self._bg_image,
            "bg_opacity": self._bg_opacity,
            "glass_tint": self._glass_tint,
        }
        try:
            cm.save_app_config(app_cfg)
        except Exception:
            logging.getLogger(__name__).warning(
                "story_reader settings not saved", exc_info=True
            )

    def set_bg_preset(self) -> None:
        self._bg_kind = "preset"
        self._rebuild_bg()
        self._save_bg_settings()

    def set_bg_color(self, hex_color: str) -> None:
        self._bg_kind = "color"
        self._bg_color = hex_color
        self._rebuild_bg()
        self._save_bg_settings()

    def set_bg_image(self, path: str) -> None:
        if not path:
            return
        self._bg_kind = "image"
        self._bg_image = path
        self._rebuild_bg()
        self._save_bg_settings()

    def set_bg_opacity(self, value: int, *, save: bool = True) -> None:
        self._bg_opacity = int(value)
        self._rebuild_bg()
        if save:
            self._save_bg_settings()

    def set_glass_tint(self, value: int, *, save: bool = True) -> None:
        """Set glass tint directly (0-100 slider value → 0.0-1.0)."""
        self._glass_tint = max(0.0, min(1.0, value / 100.0))
        for bar in self._glass_bars:
            bar.update()
        if save:
            self._save_bg_settings()

    def animate_glass_tint(self, target: float) -> None:
        """Smoothly animate glass tint to *target* (0.0 clear → 1.0 frosted)."""
        anim = getattr(self, "_tint_anim", None)
        if anim is not None:
            anim.stop()
        anim = QVariantAnimation(self)
        anim.setStartValue(self._glass_tint)
        anim.setEndValue(max(0.0, min(1.0, target)))
        anim.setDuration(350)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _tick(v: object) -> None:
            self._glass_tint = float(v)
            for bar in self._glass_bars:
                bar.update()

        anim.valueChanged.connect(_tick)
        anim.finished.connect(self._save_bg_settings)
        self._tint_anim = anim
        anim.start()

    def _make_preset_cb(self, value: str):
        def _cb() -> None:
            if value == "preset":
                self.set_bg_preset()
            else:
                self.set_bg_color(value)
            self._refresh_swatches()
        return _cb

    def _refresh_swatches(self) -> None:
        for value, sw in self._swatch_btns:
            if value == "preset":
                face = (
                    "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                    "stop:0 #2a2848, stop:1 #0c0c18);"
                )
            else:
                face = f"background:{value};"
            active = (
                self._bg_kind == "preset" and value == "preset"
            ) or (self._bg_kind == "color" and self._bg_color == value)
            border = "border:2px solid #f0d79a;" if active else "border:1.5px solid rgba(255,255,255,0.35);"
            sw.setStyleSheet(
                "QPushButton{" + face + border
                + "border-radius:11px;} QPushButton:hover{border-color:#f0d79a;}"
            )

    def _open_bg_popover(self) -> None:
        pop = _BackgroundPopover(self)
        pop.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        pop.adjustSize()
        anchor = self._bg_btn.mapToGlobal(
            QPoint(self._bg_btn.width() - pop.width(), self._bg_btn.height() + 8)
        )
        pop.move(anchor)
        self._popover = pop
        pop.show()

    # ── chapter / page state ──

    def _setup_chapter(self, *, go_to_last: bool = False) -> None:
        _, _, body, _, _ = self._chapters[self._ch_idx]
        self._pages = _paginate(body)
        self._total_pages = len(self._pages)
        if go_to_last:
            self._spread_idx = max(0, (self._total_pages - 1) // 2 * 2)
        else:
            self._spread_idx = 0
        self._combo.blockSignals(True)
        self._combo.setCurrentIndex(self._ch_idx)
        self._combo.blockSignals(False)

    def _render(self) -> None:
        _, title, _, prompt, _ = self._chapters[self._ch_idx]
        if self._spread_idx < self._total_pages:
            header = _chapter_header_html(title) if self._spread_idx == 0 else ""
            self._book.left_browser.setHtml(
                header + _body_html(self._pages[self._spread_idx])
            )
            self._book.left_num.setText(str(self._spread_idx + 1))
        else:
            self._book.left_browser.setHtml("")
            self._book.left_num.setText("")
        ri = self._spread_idx + 1
        if ri < self._total_pages:
            self._book.right_browser.setHtml(_body_html(self._pages[ri]))
            self._book.right_num.setText(str(ri + 1))
        else:
            self._book.right_browser.setHtml(
                '<div style="margin-top:42%; text-align:center;">'
                '<p style="color:#c4a35a; font-size:15px; margin:0;">✦</p>'
                '<p style="color:#b3a98f; font-size:11px; margin-top:8px;">'
                "本章终</p></div>"
            )
            self._book.right_num.setText("")

        is_first = self._ch_idx == 0 and self._spread_idx == 0
        is_last_spread = self._spread_idx + 2 >= self._total_pages
        is_last_ch = self._ch_idx >= len(self._chapters) - 1
        self._prev_btn.setEnabled(not is_first)
        self._next_btn.setEnabled(not (is_last_spread and is_last_ch))
        self._dots.set_current(self._ch_idx)
        self._ch_label.setText(f"  {title}")
        self._prompt_lbl.setText(f"「 {prompt} 」" if prompt else "")
        self._prompt_bar.setVisible(is_last_spread and bool(prompt))

    # ── navigation ──

    def _request_turn(self, direction: str, *, require_confirm: bool) -> None:
        """Gate a turn through boundary checks and the two-flick confirm.

        ``require_confirm`` is True for scroll/wheel turns (always need a second
        flick) and False for clicks/keys (instant within a chapter, but still
        confirmed when crossing a chapter boundary).
        """
        if self._animating:
            return
        total_ch = len(self._chapters)
        at_first = self._ch_idx == 0 and self._spread_idx == 0
        at_last = (
            self._ch_idx >= total_ch - 1
            and self._spread_idx + 2 >= self._total_pages
        )
        if direction == "prev" and at_first:
            self._flash_hint("已经是最初的一页", boundary=True)
            return
        if direction == "next" and at_last:
            self._flash_hint("已经读到最后一页", boundary=True)
            return

        if direction == "next":
            crossing = self._spread_idx + 2 >= self._total_pages
        else:
            crossing = self._spread_idx == 0

        if not (require_confirm or crossing):
            self._disarm()
            self._execute_turn(direction)
            return
        if self._armed == direction:
            self._disarm()
            self._execute_turn(direction)
            return

        # Arm: show the small fluorescent hint and wait for a second flick.
        self._armed = direction
        if crossing:
            msg = "再翻一下 进入下一章 →" if direction == "next" else "← 再翻一下 回到上一章"
        else:
            msg = "再翻一下 到下一页" if direction == "next" else "再翻一下 回上一页"
        self._flash_hint(msg, boundary=crossing)
        self._arm_timer.start()

    def _execute_turn(self, direction: str) -> None:
        if direction == "next":
            self._do_next()
        else:
            self._do_prev()

    def _do_next(self) -> None:
        if self._spread_idx + 2 < self._total_pages:
            self._spread_idx += 2
            self._animate(self._render, forward=True)
        elif self._ch_idx < len(self._chapters) - 1:
            self._ch_idx += 1
            self._animate(lambda: (self._setup_chapter(), self._render()), forward=True)

    def _do_prev(self) -> None:
        if self._spread_idx > 0:
            self._spread_idx -= 2
            self._animate(self._render, forward=False)
        elif self._ch_idx > 0:
            self._ch_idx -= 1
            self._animate(
                lambda: (self._setup_chapter(go_to_last=True), self._render()),
                forward=False,
            )

    # ── confirm hint ──

    def _flash_hint(self, text: str, *, boundary: bool) -> None:
        color = "#ff5a5a" if boundary else "#42e884"  # 荧光红 / 荧光绿
        self._hint.setText(text)
        self._hint.setStyleSheet(
            f"color:{color}; font-size:11px; font-weight:bold;"
            f" background:rgba(10,10,20,0.55); border-radius:9px;"
            f" padding:3px 12px;"
        )
        self._hint.adjustSize()
        self._reposition_hint()
        self._hint.show()
        self._hint.raise_()

    def _reposition_hint(self) -> None:
        x = (self._book.width() - self._hint.width()) // 2
        y = self._book.height() - self._hint.height() - 24
        self._hint.move(max(0, x), max(0, y))

    def _disarm(self) -> None:
        self._armed = None
        self._arm_timer.stop()
        self._hint.hide()

    def _on_combo(self, idx: int) -> None:
        if self._animating:
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(self._ch_idx)
            self._combo.blockSignals(False)
            return
        if idx != self._ch_idx:
            forward = idx > self._ch_idx
            self._ch_idx = idx
            self._disarm()
            self._animate(
                lambda: (self._setup_chapter(), self._render()), forward=forward
            )

    # ── animation ──

    def _animate(self, update_fn: Callable[[], object], *, forward: bool) -> None:
        book = self._book
        w, h = book.width(), book.height()
        if w <= 0 or h <= 0:
            update_fn()
            return
        self._animating = True
        old_pix = book.grab()
        update_fn()
        new_pix = book.grab()

        def done() -> None:
            self._animating = False
            self._curl = None

        self._curl = _PageCurl(book, old_pix, new_pix, forward=forward, on_done=done)
        self._curl.start()

    # ── actions ──

    def _send(self) -> None:
        _, _, _, prompt, _ = self._chapters[self._ch_idx]
        if prompt and self._controller:
            self._controller.send_message(prompt)

    # ── input ──

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._resize_timer.start()
        if self._hint.isVisible():
            self._reposition_hint()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Space, Qt.Key.Key_PageDown):
            self._request_turn("next", require_confirm=False)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self._request_turn("prev", require_confirm=False)
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Scroll page content first; only turn at the content edge.

        Up/down past the top/bottom edge turns the page, with the two-flick
        confirm. The left page can only go back; only the right page advances.
        """
        if self._animating:
            return
        bp = self._book.mapFrom(self, event.position().toPoint())
        if not self._book.rect().contains(bp):
            return
        over_left = bp.x() < self._book.width() / 2
        browser = self._book.left_browser if over_left else self._book.right_browser
        sb = browser.verticalScrollBar()
        delta = event.angleDelta().y()
        if delta > 0:  # scroll up → toward previous
            if sb.value() > sb.minimum():
                sb.setValue(sb.value() - 80)
                return
            if over_left:
                self._request_turn("prev", require_confirm=True)
        elif delta < 0:  # scroll down → toward next
            if sb.value() < sb.maximum():
                sb.setValue(sb.value() + 80)
                return
            if over_left:
                return  # the left page never advances forward
            self._request_turn("next", require_confirm=True)


# ── Background settings popover ────────────────────────────

_SLIDER_SS = (
    "QSlider::groove:horizontal { height:4px; background:rgba(255,255,255,0.18);"
    "  border-radius:2px; }"
    "QSlider::sub-page:horizontal { background:#f0d79a; border-radius:2px; }"
    "QSlider::handle:horizontal { width:14px; height:14px; margin:-6px 0;"
    "  border-radius:7px; background:#ffffff; border:1px solid rgba(0,0,0,0.25); }"
)


class _BackgroundPopover(QWidget):
    """Apple-style frosted popover — background + glass material controls."""

    _TINT_BTN = (
        "QPushButton { background:rgba(255,255,255,0.08); color:rgba(255,255,255,0.6);"
        "  border:1px solid rgba(255,255,255,0.15); padding:4px 14px;"
        "  border-radius:12px; font-size:11px; }"
        "QPushButton:hover { background:rgba(255,255,255,0.16); color:#fff; }"
    )
    _TINT_BTN_ACTIVE = (
        "QPushButton { background:rgba(240,215,154,0.22); color:#f0d79a;"
        "  border:1px solid rgba(240,215,154,0.50); padding:4px 14px;"
        "  border-radius:12px; font-size:11px; font-weight:bold; }"
    )

    def __init__(self, dialog: "StoryBookDialog") -> None:
        super().__init__(dialog)
        self._dlg = dialog
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        # ── Section 1: Import image ──
        import_btn = QPushButton("从本地导入图片…")
        import_btn.setStyleSheet(_GHOST_BTN)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_image)
        lay.addWidget(import_btn)

        # ── Section 2: Background opacity ──
        sec_bg = QLabel("背景透明度")
        sec_bg.setStyleSheet(
            "color:#f0d79a; font-size:12px; font-weight:bold; background:transparent;"
        )
        lay.addWidget(sec_bg)
        op_row = QHBoxLayout()
        op_row.setSpacing(8)
        self._op_slider = QSlider(Qt.Orientation.Horizontal)
        self._op_slider.setRange(20, 100)
        self._op_slider.setValue(int(self._dlg._bg_opacity))
        self._op_slider.setStyleSheet(_SLIDER_SS)
        self._op_slider.valueChanged.connect(lambda v: self._dlg.set_bg_opacity(v, save=False))
        self._op_slider.sliderReleased.connect(self._dlg._save_bg_settings)
        op_row.addWidget(self._op_slider, 1)
        lay.addLayout(op_row)

        # ── Section 3: Glass material (frosted ↔ liquid glass) ──
        sec_glass = QLabel("玻璃材质")
        sec_glass.setStyleSheet(
            "color:#f0d79a; font-size:12px; font-weight:bold; background:transparent;"
        )
        lay.addWidget(sec_glass)

        tint_row = QHBoxLayout()
        tint_row.setSpacing(8)
        self._btn_clear = QPushButton("液态玻璃")
        self._btn_clear.setFixedHeight(26)
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.clicked.connect(lambda: self._set_tint_mode(0.0))
        tint_row.addWidget(self._btn_clear)
        self._tint_slider = QSlider(Qt.Orientation.Horizontal)
        self._tint_slider.setRange(0, 100)
        self._tint_slider.setValue(int(self._dlg._glass_tint * 100))
        self._tint_slider.setStyleSheet(_SLIDER_SS)
        self._tint_slider.valueChanged.connect(lambda v: self._dlg.set_glass_tint(v, save=False))
        self._tint_slider.sliderReleased.connect(self._dlg._save_bg_settings)
        tint_row.addWidget(self._tint_slider, 1)
        self._btn_frosted = QPushButton("磨砂")
        self._btn_frosted.setFixedHeight(26)
        self._btn_frosted.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_frosted.clicked.connect(lambda: self._set_tint_mode(1.0))
        tint_row.addWidget(self._btn_frosted)
        self._update_tint_btns()
        lay.addLayout(tint_row)

        note = QLabel('动态达妮娅壁纸：下载后用「导入图片」选择即可')
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:rgba(255,255,255,0.32); font-size:10px; background:transparent;"
        )
        lay.addWidget(note)

        self.setFixedWidth(296)

    def _update_tint_btns(self) -> None:
        t = self._dlg._glass_tint
        self._btn_clear.setStyleSheet(
            self._TINT_BTN_ACTIVE if t < 0.25 else self._TINT_BTN
        )
        self._btn_frosted.setStyleSheet(
            self._TINT_BTN_ACTIVE if t > 0.75 else self._TINT_BTN
        )

    def _set_tint_mode(self, target: float) -> None:
        self._dlg.animate_glass_tint(target)
        self._tint_slider.blockSignals(True)
        self._tint_slider.setValue(int(target * 100))
        self._tint_slider.blockSignals(False)
        self._update_tint_btns()

    def _import_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._dlg, "选择背景图片", "",
            "图片 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self._dlg.set_bg_image(path)

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = _rounded(rect, 18)
        p.fillPath(path, QColor(22, 22, 34, 240))
        spec = QLinearGradient(
            rect.topLeft(), QPointF(rect.left(), rect.top() + rect.height() * 0.5)
        )
        spec.setColorAt(0.0, QColor(255, 255, 255, 26))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, spec)
        rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        rim.setColorAt(0.0, QColor(255, 255, 255, 120))
        rim.setColorAt(1.0, QColor(255, 255, 255, 35))
        p.setPen(QPen(QBrush(rim), 1.0))
        p.drawPath(path)
        p.end()
