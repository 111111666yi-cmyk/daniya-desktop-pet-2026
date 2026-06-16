"""Cinematic story landing window — native Qt Liquid Glass design.

Provides StoryLandingWindow: a frameless dialog with animated gradient
background, 3D card carousel for chapter selection, glass navbar,
description panel, and integrated reader.

Background options (user-selectable via settings):
  A) Animated QPainter gradient (default, lightweight)
  B) GIF/APNG via QMovie
  C) QMediaPlayer video
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Property,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.glass_widgets import (
    CardCarousel,
    GlassPill,
    GlassWidget,
    GlassWidgetStrong,
    rounded_path,
)

if TYPE_CHECKING:
    from src.app import AppController

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_story_data() -> dict:
    p = _DATA_DIR / "story_data.json"
    if p.exists():
        return json.loads(p.read_text("utf-8"))
    return {"parts": [], "chapters": [], "chapter_content": {}, "chapter_prompts": {}, "memories": []}


# Book-page base tones shown when the wallpaper is dimmed/off (#5).
_BASE_COLORS: list[tuple[str, QColor]] = [
    ("墨黑", QColor(10, 10, 20)),
    ("暖白", QColor(244, 241, 234)),
    ("书页", QColor(234, 224, 203)),
    ("樱粉", QColor(244, 223, 228)),
]


def _scan_wallpapers() -> list[tuple[str, str, "Path | None"]]:
    """Discover wallpapers. Returns (label, mode, path) where mode is
    'video' | 'image' | 'none'. Drop extra files in data/story_bg/wallpapers/.
    """
    bg = _DATA_DIR / "story_bg"
    items: list[tuple[str, str, Path | None]] = []
    default_video = bg / "background.mp4"
    if default_video.exists():
        items.append(("花园 · 视频", "video", default_video))
    extra = bg / "wallpapers"
    if extra.is_dir():
        for f in sorted(extra.iterdir()):
            suf = f.suffix.lower()
            if suf in (".mp4", ".mov", ".webm"):
                items.append((f.stem, "video", f))
            elif suf in (".jpg", ".jpeg", ".png", ".webp"):
                items.append((f.stem, "image", f))
    poster = bg / "poster.jpg"
    if poster.exists():
        items.append(("花园 · 静帧", "image", poster))
    items.append(("纯色", "none", None))
    return items


# ── Animated Gradient Background ────────────────────────────

class _AnimatedBackground(QWidget):
    """Layered background: static image → video → gradient fallback + orbs.

    Layer priority:
      1. poster.jpg shown instantly (no black screen)
      2. background.mp4 fades in when buffered
      3. QPainter gradient if neither exists
    Light orbs always paint on top as subtle overlay.
    """

    _BG_DIR = _DATA_DIR / "story_bg"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase: float = 0.0
        self._opacity: float = 1.0
        self._base_color = QColor(10, 10, 20)
        # mode: "video" | "image" | "none" (none = base colour only)
        self._mode: str = "video"
        self._poster: QPixmap | None = None
        self._poster_scaled: QPixmap | None = None
        self._poster_scaled_size: QSize | None = None
        self._video_ready = False

        poster_path = self._BG_DIR / "poster.jpg"
        if poster_path.exists():
            self._poster = QPixmap(str(poster_path))

        self._player = None
        self._sink = None
        self._frame_skip = 0
        self._video_frame: QPixmap | None = None
        self._video_frame_scaled: QPixmap | None = None
        self._video_scaled_size: QSize | None = None
        video_path = self._BG_DIR / "background.mp4"
        if video_path.exists():
            self._start_video(video_path)
        elif self._poster is not None:
            self._mode = "image"
        else:
            self._mode = "none"

        self._orb_overlay = _OrbOverlay(self)

        # Orbs drift slowly — a low refresh keeps the big radial-gradient
        # repaints off the hot path (was 33ms / 30fps over the whole window).
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _start_video(self, video_path: Path) -> None:
        """Create (or reuse) the media player and play ``video_path`` on loop."""
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
            from PySide6.QtCore import QUrl
        except Exception:
            log.debug("QtMultimedia unavailable; falling back to image/gradient")
            self._mode = "image" if self._poster is not None else "none"
            return
        if self._player is None:
            self._sink = QVideoSink(self)
            self._sink.videoFrameChanged.connect(self._on_video_frame)
            self._player = QMediaPlayer(self)
            self._player.setVideoOutput(self._sink)
            self._player.setLoops(QMediaPlayer.Loops.Infinite)
        self._video_ready = False
        self._video_frame = None
        self._video_frame_scaled = None
        self._player.setSource(QUrl.fromLocalFile(str(video_path)))
        self._player.play()
        self._mode = "video"

    def _on_video_frame(self, frame: object) -> None:
        # Halve the effective frame rate — an ambient background doesn't need
        # full 24fps and a full-window pixmap repaint is the main cost.
        self._frame_skip ^= 1
        if self._frame_skip:
            return
        img = frame.toImage()
        if not img.isNull():
            self._video_frame = QPixmap.fromImage(img)
            self._video_frame_scaled = None
            self._video_ready = True
            self.update()

    def _tick(self) -> None:
        self._phase += 0.029  # tuned for the 120ms interval (same drift speed)
        self._orb_overlay.set_phase(self._phase)

    def set_bg_opacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    def set_base_color(self, color: QColor) -> None:
        """Base colour shown when the wallpaper is dimmed or off (book-page tone)."""
        self._base_color = QColor(color)
        self.update()

    def apply_wallpaper(self, mode: str, path: Path | None = None) -> None:
        """Switch wallpaper. mode: 'video' | 'image' | 'none'."""
        if mode == "none":
            if self._player is not None:
                self._player.stop()
            self._mode = "none"
        elif mode == "image" and path is not None:
            if self._player is not None:
                self._player.stop()
            pm = QPixmap(str(path))
            if not pm.isNull():
                self._poster = pm
                self._poster_scaled = None
                self._mode = "image"
        elif mode == "video" and path is not None:
            self._start_video(path)
        self.update()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._orb_overlay.setGeometry(self.rect())
        self._poster_scaled = None
        self._video_frame_scaled = None

    def _scale_cover(self, pm: QPixmap) -> tuple[QPixmap, int, int]:
        """Scale pixmap to cover widget area (center crop)."""
        scaled = pm.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        sx = (self.width() - scaled.width()) // 2
        sy = (self.height() - scaled.height()) // 2
        return scaled, sx, sy

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        p.fillRect(self.rect(), self._base_color)
        if self._opacity < 0.01 or self._mode == "none":
            p.end()
            return
        p.setOpacity(self._opacity)

        drawn = False
        if self._mode == "video" and self._video_ready and self._video_frame is not None:
            if self._video_frame_scaled is None or self._video_scaled_size != self.size():
                self._video_frame_scaled, *_ = self._scale_cover(self._video_frame)
                self._video_scaled_size = self.size()
            sx = (w - self._video_frame_scaled.width()) // 2
            sy = (h - self._video_frame_scaled.height()) // 2
            p.drawPixmap(sx, sy, self._video_frame_scaled)
            drawn = True

        if not drawn and self._poster is not None and not self._poster.isNull():
            if self._poster_scaled is None or self._poster_scaled_size != self.size():
                self._poster_scaled, *_ = self._scale_cover(self._poster)
                self._poster_scaled_size = self.size()
            sx = (w - self._poster_scaled.width()) // 2
            sy = (h - self._poster_scaled.height()) // 2
            p.drawPixmap(sx, sy, self._poster_scaled)
            drawn = True

        if not drawn:
            bg = QLinearGradient(0, 0, w, h)
            bg.setColorAt(0.0, QColor(10, 10, 20))
            bg.setColorAt(0.4, QColor(16, 16, 31))
            bg.setColorAt(1.0, QColor(12, 10, 24))
            p.fillRect(self.rect(), bg)

        p.setOpacity(1.0)
        p.end()


class _OrbOverlay(QWidget):
    """Transparent overlay with drifting light orbs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._phase: float = 0.0

    def set_phase(self, phase: float) -> None:
        self._phase = phase
        self.update()

    def paintEvent(self, event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        phase = self._phase
        orbs = [
            (0.3 + 0.15 * math.sin(phase * 0.7), 0.25 + 0.1 * math.cos(phase * 0.5), 200, QColor(196, 163, 90, 6)),
            (0.7 + 0.1 * math.cos(phase * 0.9), 0.6 + 0.15 * math.sin(phase * 0.6), 260, QColor(90, 130, 196, 5)),
            (0.5 + 0.2 * math.sin(phase * 1.1), 0.8 + 0.08 * math.cos(phase * 0.8), 180, QColor(160, 100, 180, 4)),
        ]
        for ox, oy, radius, color in orbs:
            cx, cy = ox * w, oy * h
            grad = QRadialGradient(cx, cy, radius)
            grad.setColorAt(0.0, color)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), radius, radius)
        p.end()


# ── Glass Navbar ────────────────────────────────────────────

class _Navbar(GlassPill):
    """Top navigation bar with section buttons."""

    navigate = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setGraphicsEffect(None)
        self.setFixedHeight(52)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(4)

        logo = QLabel("d")
        logo.setStyleSheet(
            "font-family: serif; font-style: italic; font-size: 22px;"
            "color: white; padding: 0 8px;"
        )
        layout.addWidget(logo)
        layout.addStretch()

        btn_style = (
            "QPushButton { background: transparent; color: rgba(255,255,255,0.85);"
            "  border: none; padding: 8px 16px; font-size: 13px;"
            "  border-radius: 16px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); }"
        )
        from PySide6.QtWidgets import QPushButton

        for label, target in [("首页", "home"), ("故事", "story"), ("章节", "chapters"), ("回忆", "memories")]:
            btn = QPushButton(label)
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, t=target: self.navigate.emit(t))
            layout.addWidget(btn)

        enter_btn = QPushButton("进入剧情  ↗")
        enter_btn.setStyleSheet(
            "QPushButton { background: white; color: #111; border: none;"
            "  padding: 8px 20px; font-size: 13px; font-weight: 600;"
            "  border-radius: 16px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.9); }"
        )
        enter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        enter_btn.clicked.connect(lambda _=False: self.navigate.emit("reader"))
        layout.addWidget(enter_btn)

        settings_btn = QPushButton("⚙")
        settings_btn.setStyleSheet(
            "QPushButton { background: transparent; color: rgba(255,255,255,0.5);"
            "  border: none; font-size: 16px; padding: 8px; }"
            "QPushButton:hover { color: white; }"
        )
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(lambda _=False: self.navigate.emit("settings"))
        layout.addWidget(settings_btn)


# ── Hero Section ────────────────────────────────────────────

class _HeroSection(QWidget):
    """Full-height hero with centered title, badge, CTAs and stat cards."""

    navigate = Signal(str)

    def __init__(self, data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = data
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 30)
        layout.setSpacing(0)
        layout.addStretch(3)

        from PySide6.QtWidgets import QPushButton

        # Badge: "New" pill + chapter name
        badge_row = QHBoxLayout()
        badge_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_container = QWidget()
        badge_container.setStyleSheet(
            "background: rgba(255,255,255,0.06);"
            "border-radius: 18px; border: 1px solid rgba(255,255,255,0.1);"
        )
        bl = QHBoxLayout(badge_container)
        bl.setContentsMargins(4, 4, 16, 4)
        bl.setSpacing(8)
        new_pill = QLabel("New")
        new_pill.setStyleSheet(
            "background: white; color: #111; font-size: 11px; font-weight: 700;"
            "padding: 3px 10px; border-radius: 12px;"
        )
        new_pill.setFixedHeight(22)
        bl.addWidget(new_pill)
        ch_hint = QLabel("第一章 · 没有生日的人")
        ch_hint.setStyleSheet("color: rgba(255,255,255,0.85); font-size: 13px; background: transparent; border: none;")
        bl.addWidget(ch_hint)
        badge_row.addWidget(badge_container)
        layout.addLayout(badge_row)
        layout.addSpacing(24)

        # Main title — explicit min-height so the tall italic-serif glyphs
        # have vertical room and don't bleed onto the subtitle below.
        title = QLabel("达妮娅的故事")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setMinimumHeight(110)
        title.setStyleSheet(
            "color: white; font-size: 64px; font-weight: 300;"
            "font-family: serif; font-style: italic;"
        )
        layout.addWidget(title)
        layout.addSpacing(18)

        # Subtitle — fixed width + word wrap added directly to the VBox so
        # heightForWidth is honored (nesting in an HBox collapses the height
        # and overlaps the wrapped lines).
        subtitle = QLabel("她不知道这句话是什么意思。她只知道，从那以后，进房间的人说话更小声了。")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "color: rgba(255,255,255,0.65); font-size: 15px;"
        )
        subtitle.setWordWrap(True)
        subtitle.setFixedWidth(520)
        # Reserve height for two wrapped lines — with an alignment flag set the
        # VBox uses sizeHint (one line) and the wrapped text would overlap.
        subtitle.setMinimumHeight(56)
        layout.addWidget(subtitle, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(28)

        # CTA buttons
        cta_row = QHBoxLayout()
        cta_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cta_row.setSpacing(24)

        start_btn = QPushButton("开始阅读  ↗")
        start_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.08);"
            "  color: white; border: 1px solid rgba(255,255,255,0.15);"
            "  padding: 12px 28px; font-size: 14px; font-weight: 500;"
            "  border-radius: 20px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.15); }"
        )
        start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        start_btn.clicked.connect(lambda: self.navigate.emit("reader"))
        cta_row.addWidget(start_btn)

        view_btn = QPushButton("查看章节  ▸")
        view_btn.setStyleSheet(
            "QPushButton { background: transparent; color: rgba(255,255,255,0.8);"
            "  border: none; padding: 12px 20px; font-size: 14px; }"
            "QPushButton:hover { color: white; }"
        )
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.clicked.connect(lambda: self.navigate.emit("chapters"))
        cta_row.addWidget(view_btn)

        layout.addLayout(cta_row)
        layout.addSpacing(32)

        # Stats cards (reading time + chapter count)
        chapters = data.get("chapters", [])
        memories = data.get("memories", [])
        stats_row = QHBoxLayout()
        stats_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_row.setSpacing(16)

        stat_items = [
            ("⏱", "72 min", "全篇预估阅读时长"),
            ("📖", str(len(chapters)), "章节 · 完整故事线"),
        ]
        for icon, num, label in stat_items:
            card = GlassWidget(self)
            card.radius = 16
            card.setFixedSize(180, 100)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(4)
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size: 20px; background: transparent;")
            cl.addWidget(icon_lbl)
            cl.addStretch()
            n_lbl = QLabel(num)
            n_lbl.setStyleSheet(
                "color: white; font-size: 28px; font-weight: 300;"
                "font-family: serif; font-style: italic;"
            )
            cl.addWidget(n_lbl)
            t_lbl = QLabel(label)
            t_lbl.setStyleSheet("color: rgba(255,255,255,0.45); font-size: 11px;")
            cl.addWidget(t_lbl)
            stats_row.addWidget(card)

        layout.addLayout(stats_row)
        layout.addSpacing(20)

        # Bottom tag line
        tagline = QLabel("一个关于记忆、实验、生日与归期的故事")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            "color: rgba(255,255,255,0.4); font-size: 12px;"
            "background: rgba(255,255,255,0.04); padding: 6px 18px;"
            "border-radius: 14px; border: 1px solid rgba(255,255,255,0.06);"
        )
        tag_row = QHBoxLayout()
        tag_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag_row.addWidget(tagline)
        layout.addLayout(tag_row)
        layout.addSpacing(10)

        # Mood tags
        moods = QLabel("温柔          克制          疼痛感")
        moods.setAlignment(Qt.AlignmentFlag.AlignCenter)
        moods.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 13px; letter-spacing: 2px;")
        layout.addWidget(moods)
        layout.addStretch(1)


# ── Chapter Selection Section ───────────────────────────────

class _ChapterSection(QWidget):
    """Chapter carousel framed in glass, with a rich detail panel on the right."""

    chapter_opened = Signal(int)

    def __init__(self, data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = data
        chapters = data.get("chapters", [])

        from PySide6.QtWidgets import QPushButton

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 22, 48, 34)
        layout.setSpacing(16)

        header = QLabel("选择章节")
        header.setStyleSheet(
            "color: white; font-size: 24px; font-weight: 300;"
            "font-family: serif; font-style: italic;"
        )
        layout.addWidget(header)

        # ── Glass frame: carousel (left) + detail (right) ──
        frame = GlassWidgetStrong(self)
        frame.radius = 24
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(16, 12, 24, 12)
        frame_layout.setSpacing(0)

        self._carousel = CardCarousel(chapters, frame)
        self._carousel.card_selected.connect(self._on_card_selected)
        frame_layout.addWidget(self._carousel, 1)

        divider = QWidget()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background: rgba(255,255,255,0.10);")
        frame_layout.addSpacing(8)
        frame_layout.addWidget(divider)
        frame_layout.addSpacing(24)

        # ── Detail panel ──
        detail = QWidget()
        detail.setFixedWidth(304)
        detail.setStyleSheet("background: transparent;")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(0, 14, 0, 14)
        dl.setSpacing(10)

        self._d_index = QLabel()
        self._d_index.setStyleSheet("color: #d9bd7e; font-size: 12px; letter-spacing: 3px;")
        dl.addWidget(self._d_index)

        self._d_title = QLabel()
        self._d_title.setWordWrap(True)
        self._d_title.setStyleSheet(
            "color: white; font-size: 23px; font-weight: 300; font-family: serif;"
        )
        dl.addWidget(self._d_title)

        self._d_part = QLabel()
        self._d_part.setWordWrap(True)
        self._d_part.setStyleSheet("color: rgba(255,255,255,0.55); font-size: 12px;")
        dl.addWidget(self._d_part)

        self._d_tags = QLabel()
        self._d_tags.setWordWrap(True)
        self._d_tags.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px;")
        dl.addWidget(self._d_tags)

        dl.addSpacing(2)
        self._d_excerpt = QLabel()
        self._d_excerpt.setWordWrap(True)
        self._d_excerpt.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._d_excerpt.setStyleSheet(
            "color: rgba(255,255,255,0.62); font-size: 13px;"
        )
        dl.addWidget(self._d_excerpt, 1)

        self._d_prompt = QLabel()
        self._d_prompt.setWordWrap(True)
        self._d_prompt.setStyleSheet(
            "color: rgba(217,189,126,0.85); font-size: 12px; font-style: italic;"
            "padding: 10px 12px; background: rgba(196,163,90,0.08);"
            "border-radius: 10px; border: 1px solid rgba(196,163,90,0.18);"
        )
        dl.addWidget(self._d_prompt)

        read_btn = QPushButton("阅读本章  →")
        read_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.12); color: white;"
            "  border: 1px solid rgba(255,255,255,0.22); padding: 10px 20px;"
            "  border-radius: 14px; font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background: rgba(196,163,90,0.32);"
            "  border-color: rgba(196,163,90,0.5); }"
        )
        read_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        read_btn.clicked.connect(lambda: self.chapter_opened.emit(self._carousel.current_index()))
        dl.addWidget(read_btn)

        frame_layout.addWidget(detail)
        layout.addWidget(frame, 1)

        if chapters:
            self._on_card_selected(0)

    def _excerpt_for(self, idx: int, limit: int = 96) -> str:
        paras = self._data.get("chapter_content", {}).get(str(idx), [])
        text = ""
        for para in paras:
            s = para.strip()
            if not s:
                continue
            text += s
            if len(text) >= limit:
                break
        return (text[:limit] + "……") if len(text) > limit else text

    def _on_card_selected(self, idx: int) -> None:
        chapters = self._data.get("chapters", [])
        prompts = self._data.get("chapter_prompts", {})
        if not (0 <= idx < len(chapters)):
            return
        ch = chapters[idx]
        parts = self._data.get("parts", [])
        part_title = ""
        part_desc = ""
        for pt in parts:
            if pt["id"] == ch["part"]:
                part_title = pt["title"]
                if pt.get("subtitle"):
                    part_title += f" · {pt['subtitle']}"
                part_desc = pt.get("desc", "")
                break

        self._d_index.setText(f"{idx + 1:02d}  /  {len(chapters):02d}")
        self._d_title.setText(ch["title"])
        part_line = f"{part_title}　·　{ch.get('time', '')}"
        if part_desc:
            part_line += f"\n{part_desc}"
        self._d_part.setText(part_line)
        tags = ch.get("tags", [])
        self._d_tags.setText("  ".join(f"#{t}" for t in tags) if tags else "")
        self._d_tags.setVisible(bool(tags))
        self._d_excerpt.setText(self._excerpt_for(idx))
        self._d_prompt.setText(f"「{prompts.get(str(idx), '')}」")


# ── Memory Gallery ──────────────────────────────────────────

class _MemorySection(QWidget):
    """Memory fragment cards in a flowing grid."""

    def __init__(self, data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        memories = data.get("memories", [])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 30, 60, 40)
        layout.setSpacing(20)

        header = QLabel("回忆碎片")
        header.setStyleSheet(
            "color: white; font-size: 24px; font-weight: 300;"
            "font-family: serif; font-style: italic;"
        )
        layout.addWidget(header)

        from PySide6.QtWidgets import QGridLayout

        grid = QGridLayout()
        grid.setSpacing(16)
        for i, mem in enumerate(memories):
            card = GlassWidget(self)
            card.radius = 14
            card.mouse_glow = True
            card.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            card.setMouseTracking(True)
            card.setMinimumHeight(130)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(6)

            type_lbl = QLabel(mem.get("type", ""))
            type_lbl.setStyleSheet(
                "color: #d9bd7e; font-size: 10px; background: rgba(196,163,90,0.15);"
                "padding: 2px 8px; border-radius: 8px; border: 1px solid rgba(196,163,90,0.2);"
            )
            type_lbl.setFixedWidth(type_lbl.sizeHint().width() + 12)
            cl.addWidget(type_lbl)

            title_lbl = QLabel(mem.get("title", ""))
            title_lbl.setStyleSheet("color: white; font-size: 15px; font-weight: 500;")
            cl.addWidget(title_lbl)

            text_lbl = QLabel(mem.get("text", ""))
            text_lbl.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px;")
            text_lbl.setWordWrap(True)
            cl.addWidget(text_lbl)

            row, col = divmod(i, 3)
            grid.addWidget(card, row, col)

        layout.addLayout(grid)


# ── Reader Panel ────────────────────────────────────────────

class _ReaderPanel(QWidget):
    """Modern glass-styled chapter reader with sidebar TOC.

    Key story beats carry inline highlighted "问问达妮娅" markers; clicking one
    emits ``ask_daniya(question, answer)`` which the window routes to the pet.
    """

    back_requested = Signal()
    ask_daniya = Signal(str, str)  # (question, pre-written answer or "")
    character_changed = Signal(str)  # active character id (preview switcher)

    def __init__(self, data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = data
        self._current_chapter = 0
        # Per-window character context (#2). Isolated: switching here never
        # touches global state. Only daniya is live; others are placeholders.
        self._characters = [("daniya", "达妮娅", True), ("siglica", "西格莉卡", False)]
        self._active_char = "daniya"
        self._interactions: list[tuple[str, str]] = []
        chapters = data.get("chapters", [])

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar TOC
        sidebar = GlassWidget(self)
        sidebar.radius = 0
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 20)
        sidebar_layout.setSpacing(4)

        from PySide6.QtWidgets import QPushButton

        back_btn = QPushButton("← 返回")
        back_btn.setStyleSheet(
            "QPushButton { color: rgba(255,255,255,0.6); background: transparent;"
            "  border: none; font-size: 12px; padding: 6px; text-align: left; }"
            "QPushButton:hover { color: white; }"
        )
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_requested.emit)
        sidebar_layout.addWidget(back_btn)
        sidebar_layout.addSpacing(8)

        toc_title = QLabel("目录")
        toc_title.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px; padding: 4px 8px;")
        sidebar_layout.addWidget(toc_title)

        toc_scroll = QScrollArea()
        toc_scroll.setWidgetResizable(True)
        toc_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        toc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        toc_content = QWidget()
        self._toc_layout = QVBoxLayout(toc_content)
        self._toc_layout.setContentsMargins(0, 0, 0, 0)
        self._toc_layout.setSpacing(2)
        self._toc_buttons: list[QPushButton] = []

        for ch in chapters:
            btn = QPushButton(f"  {ch['title']}")
            btn.setStyleSheet(
                "QPushButton { color: rgba(255,255,255,0.55); background: transparent;"
                "  border: none; font-size: 11px; padding: 6px 8px; text-align: left;"
                "  border-radius: 6px; }"
                "QPushButton:hover { background: rgba(255,255,255,0.08); color: white; }"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ch_id = ch["id"]
            btn.clicked.connect(lambda _, c=ch_id: self.open_chapter(c))
            self._toc_layout.addWidget(btn)
            self._toc_buttons.append(btn)

        self._toc_layout.addStretch()
        toc_scroll.setWidget(toc_content)
        sidebar_layout.addWidget(toc_scroll, 1)
        main_layout.addWidget(sidebar)

        # Main reading area
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(40, 30, 40, 30)
        center_layout.setSpacing(16)

        self._ch_title = QLabel()
        self._ch_title.setStyleSheet(
            "color: white; font-size: 26px; font-weight: 300;"
            "font-family: serif; font-style: italic;"
        )
        center_layout.addWidget(self._ch_title)

        self._ch_part = QLabel()
        self._ch_part.setStyleSheet("color: #d9bd7e; font-size: 12px;")
        center_layout.addWidget(self._ch_part)

        self._reader = QTextBrowser()
        self._reader.setOpenLinks(False)
        self._reader.setOpenExternalLinks(False)
        self._reader.anchorClicked.connect(self._on_anchor)
        self._reader.setStyleSheet(
            "QTextBrowser { background: transparent; border: none;"
            "  color: rgba(255,255,255,0.82); font-size: 15px; line-height: 1.8;"
            "  selection-background-color: rgba(196,163,90,0.3); }"
        )
        center_layout.addWidget(self._reader, 1)

        # Nav buttons
        nav_row = QHBoxLayout()
        self._prev_btn = QPushButton("← 上一章")
        self._next_btn = QPushButton("下一章 →")
        nav_style = (
            "QPushButton { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.7);"
            "  border: 1px solid rgba(255,255,255,0.12); border-radius: 12px;"
            "  padding: 8px 20px; font-size: 12px; }"
            "QPushButton:hover { background: rgba(196,163,90,0.2); color: white; }"
            "QPushButton:disabled { color: rgba(255,255,255,0.2); border-color: rgba(255,255,255,0.05); }"
        )
        self._prev_btn.setStyleSheet(nav_style)
        self._next_btn.setStyleSheet(nav_style)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prev_btn.clicked.connect(lambda: self.open_chapter(self._current_chapter - 1))
        self._next_btn.clicked.connect(lambda: self.open_chapter(self._current_chapter + 1))
        nav_row.addWidget(self._prev_btn)
        nav_row.addStretch()
        nav_row.addWidget(self._next_btn)
        center_layout.addLayout(nav_row)

        main_layout.addWidget(center, 1)

        # Right info panel
        info = GlassWidget(self)
        info.radius = 0
        info.setFixedWidth(248)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(16, 30, 16, 30)
        info_layout.setSpacing(12)

        info_header = QLabel("章节信息")
        info_header.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px; letter-spacing: 1px;")
        info_layout.addWidget(info_header)

        self._info_part = QLabel()
        self._info_part.setStyleSheet("color: #d9bd7e; font-size: 12px;")
        self._info_part.setWordWrap(True)
        info_layout.addWidget(self._info_part)

        # 简介 — chapter synopsis
        syn_label = QLabel("简介")
        syn_label.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 10px; padding-top: 6px;")
        info_layout.addWidget(syn_label)
        self._info_synopsis = QLabel()
        self._info_synopsis.setWordWrap(True)
        self._info_synopsis.setStyleSheet(
            "color: rgba(255,255,255,0.72); font-size: 12px; line-height: 1.6;"
        )
        info_layout.addWidget(self._info_synopsis)

        self._info_tags = QLabel()
        self._info_tags.setStyleSheet("color: rgba(255,255,255,0.45); font-size: 11px;")
        self._info_tags.setWordWrap(True)
        info_layout.addWidget(self._info_tags)

        self._info_prompt = QLabel()
        self._info_prompt.setStyleSheet(
            "color: rgba(217,189,126,0.75); font-size: 12px;"
            "font-style: italic; padding: 12px; border-radius: 8px;"
            "background: rgba(196,163,90,0.07);"
            "border: 1px solid rgba(196,163,90,0.18);"
        )
        self._info_prompt.setWordWrap(True)
        info_layout.addWidget(self._info_prompt)

        info_layout.addStretch()

        # ── Character switcher (preview, #2) ──
        char_header = QLabel("切换角色（预览）")
        char_header.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px;")
        info_layout.addWidget(char_header)

        self._char_buttons: list[QPushButton] = []
        for cid, name, avail in self._characters:
            cb = QPushButton(name if avail else f"{name} · 敬请期待")
            cb.setCheckable(True)
            cb.setEnabled(avail)
            cb.setCursor(Qt.CursorShape.PointingHandCursor if avail else Qt.CursorShape.ArrowCursor)
            cb.clicked.connect(lambda _=False, c=cid: self._select_char(c))
            self._char_buttons.append(cb)
            info_layout.addWidget(cb)
        self._restyle_chars()

        self._pet_hint = QLabel("点击正文里的高光「问问达妮娅」，她会在桌宠上回应你。")
        self._pet_hint.setWordWrap(True)
        self._pet_hint.setStyleSheet("color: rgba(217,189,126,0.55); font-size: 10px; padding-top: 8px;")
        info_layout.addWidget(self._pet_hint)

        main_layout.addWidget(info)

    def open_chapter(self, ch_id: int) -> None:
        chapters = self._data.get("chapters", [])
        content = self._data.get("chapter_content", {})
        prompts = self._data.get("chapter_prompts", {})
        parts = self._data.get("parts", [])

        if ch_id < 0 or ch_id >= len(chapters):
            return
        self._current_chapter = ch_id
        ch = chapters[ch_id]

        part_title = ""
        for pt in parts:
            if pt["id"] == ch["part"]:
                part_title = pt["title"]
                if pt.get("subtitle"):
                    part_title += f" · {pt['subtitle']}"
                break

        self._ch_title.setText(ch["title"])
        self._ch_part.setText(f"{part_title}  ·  {ch.get('time', '')}")

        lines = content.get(str(ch_id), [])
        self._reader.setHtml(self._build_body(ch_id, lines))
        self._apply_line_spacing(180.0)

        self._info_part.setText(f"{part_title}　·　{ch.get('time', '')}")
        synopsis = self._data.get("chapter_synopsis", {}).get(str(ch_id), "")
        if not synopsis:
            synopsis = "".join(p.strip() for p in lines if p.strip())[:110] + "……"
        self._info_synopsis.setText(synopsis)
        tags_text = "  ".join(f"#{t}" for t in ch.get("tags", []))
        self._info_tags.setText(tags_text)
        self._info_tags.setVisible(bool(tags_text))
        self._info_prompt.setText(f"「{prompts.get(str(ch_id), '')}」")

        self._prev_btn.setEnabled(ch_id > 0)
        self._next_btn.setEnabled(ch_id < len(chapters) - 1)

        for i, btn in enumerate(self._toc_buttons):
            if i == ch_id:
                btn.setStyleSheet(
                    "QPushButton { color: #d9bd7e; background: rgba(196,163,90,0.12);"
                    "  border: none; font-size: 11px; padding: 6px 8px; text-align: left;"
                    "  border-radius: 6px; font-weight: 500; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { color: rgba(255,255,255,0.55); background: transparent;"
                    "  border: none; font-size: 11px; padding: 6px 8px; text-align: left;"
                    "  border-radius: 6px; }"
                    "QPushButton:hover { background: rgba(255,255,255,0.08); color: white; }"
                )

    # ── interaction markers ──

    def _chapter_interactions(self, ch_id: int, n_lines: int) -> list[tuple[int, str, str]]:
        """Return [(after_paragraph_index, question, answer), ...] for a chapter.

        Explicit placements live in story_data.json['chapter_interactions'];
        otherwise the chapter's single prompt is placed ~62% through so it
        lands at a natural beat rather than at the very end.
        """
        ci = self._data.get("chapter_interactions", {}).get(str(ch_id))
        answers = self._data.get("chapter_answers", {})
        ch_answer = answers.get(str(ch_id), "")
        result: list[tuple[int, str, str]] = []
        if ci:
            for j, item in enumerate(ci):
                q = item.get("q", "")
                a = item.get("a") or (ch_answer if j == 0 and isinstance(ch_answer, str) else "")
                if not q:
                    continue
                if "at" in item:  # fractional position (0.0–1.0) of the chapter
                    pos = max(0, min(n_lines - 1, int(n_lines * float(item["at"]))))
                else:
                    pos = max(0, min(n_lines - 1, int(item.get("after", n_lines - 1))))
                result.append((pos, q, a))
        else:
            prompt = self._data.get("chapter_prompts", {}).get(str(ch_id), "")
            if prompt:
                pos = max(0, min(n_lines - 1, int(n_lines * 0.62)))
                result.append((pos, prompt, ch_answer if isinstance(ch_answer, str) else ""))
        return result

    def _build_body(self, ch_id: int, lines: list[str]) -> str:
        interactions = self._chapter_interactions(ch_id, len(lines))
        self._interactions = [(q, a) for (_, q, a) in interactions]
        insert_map: dict[int, list[int]] = {}
        for idx, (pos, _q, _a) in enumerate(interactions):
            insert_map.setdefault(pos, []).append(idx)

        parts: list[str] = []
        for i, ln in enumerate(lines):
            if ln:
                # One <p> block per paragraph. Even line spacing inside wrapped
                # paragraphs is enforced programmatically after setHtml (Qt does
                # not reliably honour CSS line-height on soft-wrapped lines).
                parts.append(
                    f'<p style="margin:0 0 14px 0; color:rgba(255,255,255,0.82);">{ln}</p>'
                )
            for k in insert_map.get(i, []):
                q = self._interactions[k][0]
                # A bgcolor table cell — Qt's rich text honours table bgcolor
                # (it ignores background-color on inline <a>), so the marker
                # stays legible over any wallpaper.
                parts.append(
                    f'<table align="center" border="0" cellpadding="8" cellspacing="0" '
                    f'style="margin:20px 0;"><tr><td bgcolor="#2c2614">'
                    f'<a href="ask:{k}" style="color:#f3d692; text-decoration:none;">'
                    f'✦&nbsp;&nbsp;问问达妮娅 · {q}&nbsp;&nbsp;→</a></td></tr></table>'
                )
        body = "".join(parts)
        return f'<div style="font-family: sans-serif; font-size: 15px;">{body}</div>'

    def _apply_line_spacing(self, percent: float) -> None:
        """Force even proportional line spacing on every text block.

        Qt ignores CSS line-height on soft-wrapped lines, so we set it on the
        document's block format directly — this is what keeps the long
        paragraphs from collapsing into a dense wall of text."""
        from PySide6.QtGui import QTextCursor, QTextBlockFormat

        doc = self._reader.document()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextBlockFormat()
        fmt.setLineHeight(percent, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        cursor.mergeBlockFormat(fmt)

    def _on_anchor(self, url: object) -> None:
        s = url.toString()
        if not s.startswith("ask:"):
            return
        try:
            k = int(s[4:])
        except ValueError:
            return
        if 0 <= k < len(self._interactions):
            q, a = self._interactions[k]
            self.flash_hint("达妮娅正在桌宠上回应你…")
            self.ask_daniya.emit(q, a)

    # ── character switcher ──

    def _select_char(self, char_id: str) -> None:
        self._active_char = char_id
        self._restyle_chars()
        avail = dict((c, a) for c, _n, a in self._characters).get(char_id, False)
        if not avail:
            self.flash_hint("该角色尚未登场，敬请期待。")
        self.character_changed.emit(char_id)

    def _restyle_chars(self) -> None:
        for (cid, _name, avail), btn in zip(self._characters, self._char_buttons):
            active = cid == self._active_char
            if active:
                btn.setStyleSheet(
                    "QPushButton { color: white; background: rgba(196,163,90,0.28);"
                    "  border: 1px solid rgba(196,163,90,0.6); border-radius: 10px;"
                    "  padding: 7px 10px; font-size: 12px; text-align: left; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { color: rgba(255,255,255,0.5); background: rgba(255,255,255,0.04);"
                    "  border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;"
                    "  padding: 7px 10px; font-size: 12px; text-align: left; }"
                    "QPushButton:hover:enabled { background: rgba(255,255,255,0.09); color: white; }"
                    "QPushButton:disabled { color: rgba(255,255,255,0.25); }"
                )
            btn.setChecked(active)

    def active_character(self) -> str:
        return self._active_char

    def flash_hint(self, text: str) -> None:
        self._pet_hint.setText(text)
        QTimer.singleShot(
            4000,
            lambda: self._pet_hint.setText(
                "点击正文里的高光「问问达妮娅」，她会在桌宠上回应你。"
            ),
        )


# ── Settings Panel ─────────────────────────────────────────

_SLIDER_STYLE = (
    "QSlider::groove:horizontal {"
    "  background: rgba(255,255,255,0.08); height: 4px; border-radius: 2px; }"
    "QSlider::handle:horizontal {"
    "  background: white; width: 14px; height: 14px;"
    "  margin: -5px 0; border-radius: 7px; }"
    "QSlider::sub-page:horizontal {"
    "  background: rgba(196,163,90,0.6); border-radius: 2px; }"
)


class _SettingsPanel(GlassWidgetStrong):
    """Slide-out overlay: wallpaper switch, opacity, base colour, glass, music."""

    bg_opacity_changed = Signal(float)
    glass_tint_changed = Signal(float)
    base_color_changed = Signal(QColor)
    wallpaper_changed = Signal(str, object)  # (mode, Path | None)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.radius = 22
        self.setFixedWidth(300)
        self.setVisible(False)
        self.setAutoFillBackground(False)

        from PySide6.QtWidgets import QPushButton, QScrollArea

        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 6px; margin: 4px 2px; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,0.2); border-radius: 3px; min-height: 30px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }"
        )
        scroll.viewport().setStyleSheet("background: transparent;")
        outer.addWidget(scroll)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 18, 16, 20)
        layout.setSpacing(10)
        scroll.setWidget(body)

        # ── Header ──
        header_row = QHBoxLayout()
        header = QLabel("设置")
        header.setStyleSheet("color: white; font-size: 18px; font-weight: 300; font-family: serif;")
        header_row.addWidget(header)
        header_row.addStretch()
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: rgba(255,255,255,0.5);"
            "  border: none; font-size: 18px; padding: 2px 6px; }"
            "QPushButton:hover { color: white; }"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(lambda: self.setVisible(False))
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        # ── Wallpaper switcher (#9) ──
        layout.addWidget(self._section("壁纸"))
        from PySide6.QtWidgets import QGridLayout

        self._wp_items = _scan_wallpapers()
        self._wp_buttons: list[QPushButton] = []
        wp_grid = QGridLayout()
        wp_grid.setSpacing(6)
        for i, (label, mode, path) in enumerate(self._wp_items):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, idx=i: self._choose_wallpaper(idx))
            self._wp_buttons.append(btn)
            wp_grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(wp_grid)

        # ── Wallpaper opacity ──
        layout.addWidget(self._caption("透明度"))
        op_row = QHBoxLayout()
        self._op_slider = QSlider(Qt.Orientation.Horizontal)
        self._op_slider.setRange(0, 100)
        self._op_slider.setValue(100)
        self._op_slider.setStyleSheet(_SLIDER_STYLE)
        op_row.addWidget(self._op_slider, 1)
        self._op_val = QLabel("100%")
        self._op_val.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px; min-width: 34px;")
        op_row.addWidget(self._op_val)
        layout.addLayout(op_row)
        self._op_slider.valueChanged.connect(self._on_opacity)

        # ── Base colour (#5) ──
        layout.addWidget(self._section("基底色"))
        hint = QLabel("透明度降低时显露的书页底色")
        hint.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 10px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._color_buttons: list[QPushButton] = []
        sw_row = QHBoxLayout()
        sw_row.setSpacing(10)
        for i, (cname, color) in enumerate(_BASE_COLORS):
            sw = QPushButton()
            sw.setFixedSize(30, 30)
            sw.setCheckable(True)
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            sw.setToolTip(cname)
            sw.clicked.connect(lambda _=False, idx=i: self._choose_color(idx))
            self._color_buttons.append(sw)
            sw_row.addWidget(sw)
        sw_row.addStretch()
        layout.addLayout(sw_row)

        # ── Glass effect (#7 control) ──
        layout.addWidget(self._section("玻璃效果"))
        gl_labels = QHBoxLayout()
        gl_left = QLabel("磨砂")
        gl_left.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 10px;")
        gl_right = QLabel("液态玻璃")
        gl_right.setStyleSheet("color: rgba(255,255,255,0.35); font-size: 10px;")
        gl_labels.addWidget(gl_left)
        gl_labels.addStretch()
        gl_labels.addWidget(gl_right)
        layout.addLayout(gl_labels)
        gl_row = QHBoxLayout()
        self._gl_slider = QSlider(Qt.Orientation.Horizontal)
        self._gl_slider.setRange(0, 100)
        self._gl_slider.setValue(50)
        self._gl_slider.setStyleSheet(_SLIDER_STYLE)
        gl_row.addWidget(self._gl_slider, 1)
        self._gl_val = QLabel("50%")
        self._gl_val.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px; min-width: 34px;")
        gl_row.addWidget(self._gl_val)
        layout.addLayout(gl_row)
        self._gl_slider.valueChanged.connect(self._on_glass)

        # ── Background music (#6, disabled shell) ──
        layout.addWidget(self._section("背景音乐"))
        layout.addWidget(self._build_music_shell())

        layout.addStretch()

        # initial selections
        self._choose_wallpaper(0, emit=False)
        self._choose_color(0, emit=False)

    # ── builders ──

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: rgba(255,255,255,0.85); font-size: 12px; font-weight: 600;"
            "letter-spacing: 1px; padding-top: 6px;"
        )
        return lbl

    def _caption(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 11px;")
        return lbl

    def _build_music_shell(self) -> QWidget:
        from PySide6.QtWidgets import QPushButton

        self._music = None
        self._audio_out = None

        card = QWidget()
        card.setStyleSheet(
            "background: rgba(255,255,255,0.05); border-radius: 14px;"
            "border: 1px solid rgba(255,255,255,0.08);"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)
        self._music_play = QPushButton("▶")
        self._music_play.setFixedSize(34, 34)
        self._music_play.setEnabled(False)
        self._music_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._music_play.setStyleSheet(
            "QPushButton { background: rgba(196,163,90,0.2); color: #f3d692;"
            "  border: none; border-radius: 17px; font-size: 13px; }"
            "QPushButton:hover:enabled { background: rgba(196,163,90,0.35); }"
            "QPushButton:disabled { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.4); }"
        )
        self._music_play.clicked.connect(self._toggle_music)
        top.addWidget(self._music_play)

        self._music_track = QLabel("未导入音乐")
        self._music_track.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px;")
        top.addWidget(self._music_track, 1)

        import_btn = QPushButton("导入")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.8);"
            "  border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; padding: 5px 12px; font-size: 11px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.15); }"
        )
        import_btn.clicked.connect(self._import_music)
        top.addWidget(import_btn)
        cl.addLayout(top)

        vol_row = QHBoxLayout()
        vol_row.setSpacing(8)
        vol_icon = QLabel("♪")
        vol_icon.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 12px;")
        vol_row.addWidget(vol_icon)
        self._music_vol = QSlider(Qt.Orientation.Horizontal)
        self._music_vol.setRange(0, 100)
        self._music_vol.setValue(60)
        self._music_vol.setStyleSheet(_SLIDER_STYLE)
        self._music_vol.valueChanged.connect(self._on_volume)
        vol_row.addWidget(self._music_vol, 1)
        cl.addLayout(vol_row)
        return card

    def _ensure_music_player(self) -> bool:
        if self._music is not None:
            return True
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        except Exception:
            return False
        self._audio_out = QAudioOutput(self)
        self._audio_out.setVolume(self._music_vol.value() / 100.0)
        self._music = QMediaPlayer(self)
        self._music.setAudioOutput(self._audio_out)
        self._music.setLoops(QMediaPlayer.Loops.Infinite)
        return True

    def _import_music(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtCore import QUrl

        path, _ = QFileDialog.getOpenFileName(
            self, "导入背景音乐", "",
            "音频 (*.mp3 *.m4a *.wav *.ogg *.flac);;所有文件 (*.*)",
        )
        if not path:
            return
        if not self._ensure_music_player():
            self._music_track.setText("无法初始化播放器")
            return
        from pathlib import Path as _P
        self._music.setSource(QUrl.fromLocalFile(path))
        self._music_track.setText(_P(path).name)
        self._music_play.setEnabled(True)
        self._music.play()
        self._music_play.setText("⏸")

    def _toggle_music(self) -> None:
        if self._music is None:
            return
        from PySide6.QtMultimedia import QMediaPlayer
        if self._music.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._music.pause()
            self._music_play.setText("▶")
        else:
            self._music.play()
            self._music_play.setText("⏸")

    def _on_volume(self, v: int) -> None:
        if self._audio_out is not None:
            self._audio_out.setVolume(v / 100.0)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = rounded_path(rect, self.radius)
        p.fillPath(path, QColor(18, 18, 28, 232))
        self._paint_glass(p, rect, path)
        p.end()

    # ── handlers ──

    def _choose_wallpaper(self, idx: int, emit: bool = True) -> None:
        for i, b in enumerate(self._wp_buttons):
            b.setChecked(i == idx)
            b.setStyleSheet(self._chip_style(i == idx))
        label, mode, path = self._wp_items[idx]
        if emit:
            self.wallpaper_changed.emit(mode, path)

    def _chip_style(self, active: bool) -> str:
        if active:
            return (
                "QPushButton { background: rgba(196,163,90,0.28); color: white;"
                "  border: 1px solid rgba(196,163,90,0.6); border-radius: 11px;"
                "  padding: 7px 6px; font-size: 11px; }"
            )
        return (
            "QPushButton { background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.65);"
            "  border: 1px solid rgba(255,255,255,0.1); border-radius: 11px;"
            "  padding: 7px 6px; font-size: 11px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); }"
        )

    def _choose_color(self, idx: int, emit: bool = True) -> None:
        for i, b in enumerate(self._color_buttons):
            cname, color = _BASE_COLORS[i]
            ring = "white" if i == idx else "rgba(255,255,255,0.25)"
            b.setChecked(i == idx)
            b.setStyleSheet(
                f"QPushButton {{ background: rgb({color.red()},{color.green()},{color.blue()});"
                f"  border: 2px solid {ring}; border-radius: 15px; }}"
            )
        if emit:
            self.base_color_changed.emit(_BASE_COLORS[idx][1])

    def _on_opacity(self, v: int) -> None:
        self._op_val.setText(f"{v}%")
        self.bg_opacity_changed.emit(v / 100.0)

    def _on_glass(self, v: int) -> None:
        self._gl_val.setText(f"{v}%")
        self.glass_tint_changed.emit(v / 100.0)


# ── Main Landing Window ─────────────────────────────────────

class StoryLandingWindow(QDialog):
    """Cinematic frameless landing window with Liquid Glass design."""

    def __init__(self, controller: AppController | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._glass_tint: float = 0.5
        self._bg_blur: QPixmap | None = None

        self.setWindowTitle("达妮娅的故事")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(960, 640)
        self.resize(1100, 720)

        self._data = _load_story_data()

        # Background
        self._bg = _AnimatedBackground(self)

        # Main layout stacks over background
        self._root = QWidget(self)
        root_layout = QVBoxLayout(self._root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Navbar (wrapped in a container so it can be hidden entirely in the reader)
        self._navbar = _Navbar(self)
        self._navbar.navigate.connect(self._on_navigate)
        self._nav_container = QWidget()
        nav_container = QHBoxLayout(self._nav_container)
        nav_container.setContentsMargins(40, 16, 40, 0)
        nav_container.addWidget(self._navbar)
        root_layout.addWidget(self._nav_container)

        # Stacked content
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; }")
        root_layout.addWidget(self._stack, 1)

        # Page 0: Hero
        self._hero = _HeroSection(self._data)
        self._hero.setStyleSheet("background: transparent;")
        self._hero.navigate.connect(self._on_navigate)
        self._stack.addWidget(self._hero)

        # Page 1: Chapters
        self._chapters = _ChapterSection(self._data)
        self._chapters.setStyleSheet("background: transparent;")
        self._chapters.chapter_opened.connect(self._open_reader)
        self._stack.addWidget(self._chapters)

        # Page 2: Memories
        mem_scroll = QScrollArea()
        mem_scroll.setWidgetResizable(True)
        mem_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        mem_scroll.viewport().setStyleSheet("background: transparent;")
        mem_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._memories = _MemorySection(self._data)
        self._memories.setStyleSheet("background: transparent;")
        mem_scroll.setWidget(self._memories)
        self._stack.addWidget(mem_scroll)

        # Page 3: Reader
        self._reader = _ReaderPanel(self._data)
        self._reader.setStyleSheet("background: transparent;")
        self._reader.back_requested.connect(lambda: self._fade_to_page(1))
        self._reader.ask_daniya.connect(self._on_ask_daniya)
        self._stack.addWidget(self._reader)

        self._stack.setCurrentIndex(0)

        # Settings panel (overlay on right)
        self._settings = _SettingsPanel(self)
        self._settings.bg_opacity_changed.connect(self._bg.set_bg_opacity)
        self._settings.glass_tint_changed.connect(self._set_glass_tint)
        self._settings.base_color_changed.connect(self._bg.set_base_color)
        self._settings.wallpaper_changed.connect(self._bg.apply_wallpaper)

        # Ensure content is above video background
        self._root.raise_()

        # Drag support
        self._drag_pos: QPoint | None = None

        # Generate blur cache after first paint
        QTimer.singleShot(100, self._update_blur_cache)

    def _update_blur_cache(self) -> None:
        pm = QPixmap(self.size())
        self._bg.render(pm)
        from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsScene, QGraphicsPixmapItem

        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(pm)
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(30)
        item.setGraphicsEffect(blur_effect)
        scene.addItem(item)
        result = QPixmap(pm.size())
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        scene.render(painter)
        painter.end()
        self._bg_blur = result

    def _set_glass_tint(self, value: float) -> None:
        self._glass_tint = max(0.0, min(1.0, value))
        self._update_blur_cache()
        self.update()

    def _toggle_settings(self) -> None:
        vis = not self._settings.isVisible()
        if vis:
            self._settings.setGeometry(
                self.width() - 320, 64, 300, self.height() - 84,
            )
        self._settings.setVisible(vis)
        if vis:
            self._settings.raise_()

    def _on_navigate(self, target: str) -> None:
        if target == "settings":
            self._toggle_settings()
            return
        page_map = {"home": 0, "story": 0, "chapters": 1, "memories": 2, "reader": 3}
        idx = page_map.get(target, 0)
        if target == "reader":
            self._reader.open_chapter(0)
        self._fade_to_page(idx)

    def _fade_to_page(self, idx: int) -> None:
        # Reader page (idx 3) has its own sidebar/back button — hide the
        # global navbar there so the brand "d" doesn't sit redundantly on top.
        self._nav_container.setVisible(idx != 3)
        if idx == self._stack.currentIndex():
            return
        target_widget = self._stack.widget(idx)
        effect = QGraphicsOpacityEffect(target_widget)
        target_widget.setGraphicsEffect(effect)
        self._stack.setCurrentIndex(idx)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: target_widget.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _open_reader(self, ch_id: int) -> None:
        self._reader.open_chapter(ch_id)
        self._fade_to_page(3)

    def _on_ask_daniya(self, question: str, answer: str) -> None:
        """Route a story interaction to the desktop pet (#3).

        With a pre-written answer the pet speaks it verbatim; otherwise the
        question goes through the normal local-model pipeline. Both surface in
        the pet's chat bubble with its typewriter (slow, sentence-by-sentence).
        """
        ctrl = self._controller
        pet = getattr(ctrl, "window", None) if ctrl is not None else None
        if pet is None:
            # Standalone/preview (no live pet) — nothing to route to.
            return
        try:
            pet.show()
            pet.raise_()
        except Exception:
            pass
        if answer:
            pet.speak(answer)
        else:
            ctrl.send_message(question)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())
        self._root.setGeometry(self.rect())
        self._settings.setGeometry(
            self.width() - 320, 64, 300, self.height() - 84,
        )
        self._root.raise_()
        if self._settings.isVisible():
            self._settings.raise_()
        QTimer.singleShot(50, self._update_blur_cache)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 60:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: object) -> None:
        self._bg._timer.stop()
        if self._bg._player is not None:
            self._bg._player.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event: object) -> None:
        from PySide6.QtGui import QKeyEvent

        if isinstance(event, QKeyEvent):
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close()
                return
            if key == Qt.Key.Key_S and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._toggle_settings()
                return
            if key == Qt.Key.Key_1:
                self._fade_to_page(0)
                return
            if key == Qt.Key.Key_2:
                self._fade_to_page(1)
                return
            if key == Qt.Key.Key_3:
                self._fade_to_page(2)
                return
            if key == Qt.Key.Key_4:
                self._reader.open_chapter(0)
                self._fade_to_page(3)
                return
        super().keyPressEvent(event)
