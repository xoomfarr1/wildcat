"""Frosted-glass connection-bar panel with an animated sparkle overlay."""
from __future__ import annotations

import random

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from wildcat.gui.sparkle_logic import (
    DEFAULT_COUNT,
    DT,
    alpha_at,
    init_particles,
    step,
)


class GlassPanel(QWidget):
    """Frosted-glass container that hosts a layout (the connection bar) and a
    drifting sparkle layer.

    The bar layout is set as this panel's layout, so the native controls render
    *above* the painted glass + sparkles; glitter is visible in the bar's glass
    margins rather than obscuring the controls. Hovering the panel intensifies
    the sparkle (the mica shimmer you get on watch cat).
    """

    def __init__(self, parent: QWidget | None = None, children_layout=None) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        if children_layout is not None:
            children_layout.setContentsMargins(12, 8, 12, 8)
            self.setLayout(children_layout)
        self._rng = random.Random(id(self))
        self._t = 0.0
        self._hover = False
        self._particles: list = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, ev):
        if not self._particles:
            self._particles = init_particles(
                DEFAULT_COUNT, max(100, self.width()), max(30, self.height()), self._rng
            )
        self._timer.start(int(DT * 1000))
        super().showEvent(ev)

    def hideEvent(self, ev):
        self._timer.stop()
        super().hideEvent(ev)

    def _tick(self) -> None:
        self._t += DT
        w, h = max(100, self.width()), max(30, self.height())
        self._particles = step(self._particles, self._t, DT, w, h, self._rng)
        self.update()

    def enterEvent(self, ev):
        self._hover = True
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hover = False
        self.update()
        super().leaveEvent(ev)

    def resizeEvent(self, ev):
        if self._particles and (self.width() < 10 or self.height() < 10):
            self._particles = []
        super().resizeEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        # --- frosted glass background ---
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 12, 12)
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(46, 46, 72, 150))
        grad.setColorAt(1, QColor(30, 30, 46, 215))
        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        # --- drifting sparkles ---
        for prt in self._particles:
            a = alpha_at(prt.phase, self._t)
            if self._hover:
                a = min(0.95, a + 0.35)
            if a < 0.08:
                continue
            col = QColor(255, 255, max(210, int(255 * a)), int(255 * a * 0.85))
            p.setBrush(QBrush(col))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(prt.x, prt.y, prt.size, prt.size))
