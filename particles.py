import math
import random
import time

from PySide6.QtCore import QLineF, QRectF, QTimer, Qt
from PySide6.QtGui import (
    QColor, QPainter, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import QWidget


def _make_soft_sprite(radius: float, color: QColor) -> QPixmap:
    """Pre-render a soft radial-gradient particle sprite once."""
    size = max(4, int(math.ceil(radius * 2 + 2)))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    center = size * 0.5
    grad = QRadialGradient(center, center, radius)
    c0 = QColor(color)
    c1 = QColor(color)
    c1.setAlpha(int(color.alpha() * 0.45))
    c2 = QColor(color)
    c2.setAlpha(0)
    grad.setColorAt(0.0, c0)
    grad.setColorAt(0.55, c1)
    grad.setColorAt(1.0, c2)

    p = QPainter(pm)
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawEllipse(QRectF(1.0, 1.0, radius * 2, radius * 2))
    p.end()
    return pm


class ParticleOverlay(QWidget):
    """Lightweight 60fps sprite-cached particle layer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self._mode = "none"
        self._last_time = 0.0

        # Parallel arrays avoid per-particle dict overhead
        self._x: list[float] = []
        self._y: list[float] = []
        self._vx: list[float] = []
        self._vy: list[float] = []
        self._phase: list[float] = []
        self._aux: list[float] = []     # length (rain), sprite_idx (snow), freq (sparkles)
        self._bucket: list[int] = []    # alpha/sprite bucket index

        # Pre-rendered sprite & pen caches
        self._snow_sprites: list[QPixmap] = []
        self._sparkle_sprites: list[QPixmap] = []
        self._rain_pens: list[QPen] = []
        self._build_assets()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(16)  # ~60 fps
        self._timer.timeout.connect(self._tick)

    def _build_assets(self) -> None:
        # 4 snow sizes with soft edges (no runtime Antialiasing needed)
        self._snow_sprites = [
            _make_soft_sprite(r, QColor(255, 255, 255, a))
            for r, a in ((1.8, 145), (2.4, 175), (3.1, 200), (3.8, 220))
        ]
        # 12 sparkle brightness steps
        self._sparkle_sprites = [
            _make_soft_sprite(2.6, QColor(255, 224, 135, int(40 + 215 * (i / 11))))
            for i in range(12)
        ]
        # 4 rain alpha buckets
        self._rain_pens = [
            QPen(QColor(180, 205, 255, a), 1.15)
            for a in (85, 115, 145, 175)
        ]

    def set_mode(self, mode: str) -> None:
        if mode == self._mode and self._x:
            return
        self._mode = mode
        self._clear()
        if mode == "none":
            self._timer.stop()
        else:
            self._seed_initial()
            self._last_time = time.perf_counter()
            if self.isVisible():
                self._timer.start()
        self.update()

    def _clear(self) -> None:
        self._x.clear()
        self._y.clear()
        self._vx.clear()
        self._vy.clear()
        self._phase.clear()
        self._aux.clear()
        self._bucket.clear()

    def _target(self) -> int:
        return {"rain": 95, "snow": 65, "sparkles": 42}.get(self._mode, 0)

    def _spawn(self, scatter_y: bool) -> None:
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        self._x.append(random.uniform(0, w))

        if self._mode == "rain":
            self._y.append(random.uniform(-h, h) if scatter_y else random.uniform(-40, -5))
            self._vy.append(random.uniform(620, 880))
            self._vx.append(random.uniform(-55, -15))
            self._phase.append(0.0)
            self._aux.append(random.uniform(10, 17))
            self._bucket.append(random.randrange(len(self._rain_pens)))
        elif self._mode == "snow":
            self._y.append(random.uniform(0, h) if scatter_y else random.uniform(-20, -2))
            self._vy.append(random.uniform(32, 78))
            self._vx.append(random.uniform(-16, 16))
            self._phase.append(random.uniform(0.0, math.tau))
            self._aux.append(0.0)
            self._bucket.append(random.randrange(len(self._snow_sprites)))
        else:  # sparkles
            self._y.append(random.uniform(0, h))
            self._vx.append(random.uniform(-14, 14))
            self._vy.append(random.uniform(-14, 14))
            self._phase.append(random.uniform(0.0, math.tau))
            self._aux.append(random.uniform(2.2, 4.8))
            self._bucket.append(0)

    def _seed_initial(self) -> None:
        if self.width() <= 1 or self.height() <= 1:
            return
        target = self._target()
        while len(self._x) < target:
            self._spawn(scatter_y=True)

    def resizeEvent(self, event) -> None:
        if self._mode != "none" and not self._x:
            self._seed_initial()
        super().resizeEvent(event)

    def showEvent(self, event) -> None:
        if self._mode != "none" and not self._timer.isActive():
            self._last_time = time.perf_counter()
            self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def _tick(self) -> None:
        if self._mode == "none":
            return

        now = time.perf_counter()
        dt = min(now - self._last_time, 0.05) if self._last_time else 0.016
        self._last_time = now

        w = max(self.width(), 1)
        h = max(self.height(), 1)
        target = self._target()
        while len(self._x) < target:
            self._spawn(scatter_y=False)

        xs, ys, vxs, vys = self._x, self._y, self._vx, self._vy
        phases, auxs, buckets = self._phase, self._aux, self._bucket
        mode = self._mode
        n = len(xs)

        if mode == "rain":
            for i in range(n):
                ny = ys[i] + vys[i] * dt
                nx = xs[i] + vxs[i] * dt
                if ny > h + 20:
                    ny = random.uniform(-35, -5)
                    nx = random.uniform(0, w)
                xs[i] = nx
                ys[i] = ny

        elif mode == "snow":
            sin = math.sin
            dt2 = dt * 2.0
            sway = 24.0 * dt
            for i in range(n):
                ph = phases[i] + dt2
                ny = ys[i] + vys[i] * dt
                nx = xs[i] + sin(ph) * sway + vxs[i] * dt
                if ny > h + 10:
                    ny = random.uniform(-16, -2)
                    nx = random.uniform(0, w)
                elif nx < -10:
                    nx += w + 20
                elif nx > w + 10:
                    nx -= w + 20
                phases[i] = ph
                xs[i] = nx
                ys[i] = ny

        else:  # sparkles
            sin = math.sin
            max_idx = len(self._sparkle_sprites) - 1
            for i in range(n):
                ph = phases[i] + auxs[i] * dt
                xs[i] = (xs[i] + vxs[i] * dt) % w
                ys[i] = (ys[i] + vys[i] * dt) % h
                phases[i] = ph
                buckets[i] = int((0.5 + 0.5 * sin(ph)) * max_idx)

        self.update()

    def paintEvent(self, _event) -> None:
        if self._mode == "none" or not self._x:
            return

        p = QPainter(self)
        xs, ys = self._x, self._y
        buckets = self._bucket
        n = len(xs)

        if self._mode == "rain":
            vxs, auxs = self._vx, self._aux
            batches: list[list[QLineF]] = [[] for _ in self._rain_pens]
            for i in range(n):
                x0, y0 = xs[i], ys[i]
                batches[buckets[i]].append(
                    QLineF(x0, y0, x0 + vxs[i] * 0.02, y0 + auxs[i])
                )
            for pen, lines in zip(self._rain_pens, batches):
                if lines:
                    p.setPen(pen)
                    p.drawLines(lines)

        elif self._mode == "snow":
            sprites = self._snow_sprites
            for i in range(n):
                sp = sprites[buckets[i]]
                p.drawPixmap(int(xs[i] - sp.width() * 0.5),
                             int(ys[i] - sp.height() * 0.5), sp)

        else:  # sparkles
            sprites = self._sparkle_sprites
            for i in range(n):
                sp = sprites[buckets[i]]
                p.drawPixmap(int(xs[i] - sp.width() * 0.5),
                             int(ys[i] - sp.height() * 0.5), sp)