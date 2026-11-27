import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import (
    QEasingCurve, QRectF, QTimer, QVariantAnimation, Qt, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QConicalGradient, QFont,
    QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from particles import ParticleOverlay
from settings import Settings
from settings_dialog import SettingsDialog
from tracker import TrackDatChest


def _mci(cmd: str) -> None:
    if sys.platform != "win32":
        return
    winmm = ctypes.windll.winmm
    winmm.mciSendStringW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HANDLE
    ]
    winmm.mciSendStringW.restype = wintypes.DWORD
    winmm.mciSendStringW(cmd, None, 0, None)


class CounterWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = "0"
        self._base_color = QColor("#f2c14e")
        self._flash_color = QColor("#ffffff")
        self._font = QFont("Segoe UI", 72, QFont.Bold)
        self._scale = 1.0
        self._flash = 0.0

        self.setMinimumHeight(136)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_step)

    def set_text(self, text: str) -> None:
        if self._text != text:
            self._text = text
            self.update()

    def set_style(self, font_family: str, color_hex: str) -> None:
        self._font = QFont(font_family, 72, QFont.Bold)
        self._base_color = QColor(color_hex)
        self._flash_color = QColor(
            min(255, int(self._base_color.red() * 0.25 + 255 * 0.75)),
            min(255, int(self._base_color.green() * 0.25 + 255 * 0.75)),
            min(255, int(self._base_color.blue() * 0.25 + 255 * 0.75)),
        )
        self.update()

    def trigger_pop(self) -> None:
        self._anim.stop()
        self._anim.start()

    def reset_anim(self) -> None:
        self._anim.stop()
        self._scale = 1.0
        self._flash = 0.0
        self.update()

    def _on_anim_step(self, value: float) -> None:
        self._flash = value
        self._scale = 1.0 + 0.20 * value
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setFont(self._font)

        if self._flash > 0.001:
            t = self._flash
            inv = 1.0 - t
            c = QColor(
                int(self._base_color.red() * inv + self._flash_color.red() * t),
                int(self._base_color.green() * inv + self._flash_color.green() * t),
                int(self._base_color.blue() * inv + self._flash_color.blue() * t),
            )
            p.setPen(c)
            cx = self.width() * 0.5
            cy = self.height() * 0.5
            p.translate(cx, cy)
            p.scale(self._scale, self._scale)
            p.drawText(
                QRectF(-cx, -cy, self.width(), self.height()),
                Qt.AlignCenter,
                self._text,
            )
        else:
            p.setPen(self._base_color)
            p.drawText(self.rect(), Qt.AlignCenter, self._text)


class MainWindow(QWidget):
    CORNER_RADIUS = 16
    hotkeys_changed = Signal()
    pause_hotkeys = Signal()
    resume_hotkeys = Signal()

    def __init__(self):
        super().__init__()
        self.tdc = TrackDatChest()
        self.settings = Settings()
        self.settings.load()
        self._dialog: SettingsDialog | None = None
        self._input_mgr = None
        self._drag_pos = None

        self._cached_wall_path = ""
        self._raw_wallpaper: QPixmap | None = None
        self._bg_cache: QPixmap | None = None

        self._loaded_sound_path = ""
        self._rgb_angle = 0.0

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self.tdc.flush)

        self._pace_timer = QTimer(self)
        self._pace_timer.setTimerType(Qt.CoarseTimer)
        self._pace_timer.setInterval(1000)
        self._pace_timer.timeout.connect(self._update_pace)

        self._rgb_timer = QTimer(self)
        self._rgb_timer.setTimerType(Qt.CoarseTimer)
        self._rgb_timer.setInterval(33)
        self._rgb_timer.timeout.connect(self._tick_rgb)

        self.setWindowTitle("Pirate Chest Counter")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.overlay = ParticleOverlay(self)

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setObjectName("close")
        self.btn_close.setToolTip("Close")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.close)

        caption = QLabel("CHESTS THIS MATCH")
        caption.setObjectName("caption")
        caption.setAlignment(Qt.AlignCenter)

        self.count = CounterWidget(self)

        self.stats = QLabel()
        self.stats.setObjectName("stats")
        self.stats.setAlignment(Qt.AlignCenter)

        self.pace = QLabel()
        self.pace.setObjectName("pace")
        self.pace.setAlignment(Qt.AlignCenter)

        btn_add = QPushButton("+1 Chest")
        btn_undo = QPushButton("Undo")
        btn_split = QPushButton("Split")
        btn_split.setObjectName("split")
        btn_settings = QPushButton("⚙")
        btn_settings.setFixedWidth(44)

        btn_add.clicked.connect(self.on_add)
        btn_undo.clicked.connect(self.on_undo)
        btn_split.clicked.connect(self.on_split)
        btn_settings.clicked.connect(self.open_settings)

        buttons = QHBoxLayout()
        for b in (btn_add, btn_undo, btn_split, btn_settings):
            buttons.addWidget(b)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 40, 24, 24)
        layout.addWidget(caption)
        layout.addWidget(self.count)
        layout.addWidget(self.stats)
        layout.addWidget(self.pace)
        layout.addStretch()
        layout.addLayout(buttons)

        self.resize(400, 480)
        self._apply_settings()
        self._reposition_close()
        self.btn_close.raise_()
        self.refresh()

    def attach_input_manager(self, input_mgr) -> None:
        self._input_mgr = input_mgr

    def _sync_sound(self) -> None:
        path = self.settings.sound_path
        if path == self._loaded_sound_path:
            return
        self.close_sound()
        if path:
            safe = path.replace('"', "")
            _mci(f'open "{safe}" alias pcc_sfx')
            self._loaded_sound_path = path

    def _play_sound(self) -> None:
        if self._loaded_sound_path:
            _mci("play pcc_sfx from 0")

    def close_sound(self) -> None:
        if self._loaded_sound_path:
            _mci("close pcc_sfx")
            self._loaded_sound_path = ""

    def _tick_rgb(self) -> None:
        self._rgb_angle = (self._rgb_angle + 3.0) % 360.0
        self.update()

    def _reposition_close(self) -> None:
        self.btn_close.move(self.width() - self.btn_close.width() - 8, 8)

    def resizeEvent(self, event) -> None:
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self._reposition_close()
        self.btn_close.raise_()
        self._rebuild_bg_cache()
        super().resizeEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, _event) -> None:
        self._drag_pos = None

    def _sync_raw_wallpaper(self) -> None:
        path = self.settings.wallpaper_path
        if path == self._cached_wall_path:
            return
        self._cached_wall_path = path
        if not path:
            self._raw_wallpaper = None
            return
        pm = QPixmap(path)
        self._raw_wallpaper = pm if not pm.isNull() else None

    def _rebuild_bg_cache(self) -> None:
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        self._sync_raw_wallpaper()
        s = self.settings

        cache = QPixmap(w, h)
        cache.fill(Qt.transparent)

        p = QPainter(cache)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        clip = QPainterPath()
        clip.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        p.setClipPath(clip)

        drew_bg = False
        if self._raw_wallpaper is not None:
            self._draw_wallpaper(p, self._raw_wallpaper, s.wallpaper_mode, w, h)
            drew_bg = True

        if not drew_bg and not s.transparent:
            p.fillRect(0, 0, w, h, QColor(s.bg_color))

        if not s.rgb_outline:
            p.setClipping(False)
            pen = QPen(QColor(s.count_color), 1.0)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        p.end()
        self._bg_cache = cache

    def _draw_wallpaper(
        self, p: QPainter, pm: QPixmap, mode: str, w: int, h: int
    ) -> None:
        if mode == "stretch":
            scaled = pm.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(0, 0, scaled)
        elif mode == "contain":
            scaled = pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
        else:
            scaled = pm.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.drawPixmap(
                0, 0, scaled,
                (scaled.width() - w) // 2,
                (scaled.height() - h) // 2,
                w, h,
            )

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        if self._bg_cache is not None:
            p.drawPixmap(0, 0, self._bg_cache)

        if self.settings.rgb_outline:
            colors = self.settings.rgb_colors
            n = len(colors)
            if n >= 2:
                p.setRenderHint(QPainter.Antialiasing, True)
                w, h = self.width(), self.height()
                grad = QConicalGradient(w * 0.5, h * 0.5, self._rgb_angle)
                for i, hex_c in enumerate(colors):
                    grad.setColorAt(i / n, QColor(hex_c))
                grad.setColorAt(1.0, QColor(colors[0]))

                p.setPen(QPen(QBrush(grad), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(
                    QRectF(0.75, 0.75, w - 1.5, h - 1.5),
                    self.CORNER_RADIUS,
                    self.CORNER_RADIUS,
                )

    def _apply_settings(self) -> None:
        s = self.settings
        self.setStyleSheet(f"""
            QWidget {{ font-family: '{s.font_family}'; }}
            QLabel#caption {{ color: #6e7681; font-size: 12px; letter-spacing: 3px; }}
            QLabel#stats {{ color: #8b949e; font-size: 15px; }}
            QLabel#pace {{ color: #8b949e; font-size: 13px; }}
            QPushButton {{
                background-color: #000000; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 8px;
                padding: 10px; font-size: 14px;
            }}
            QPushButton:hover {{ border-color: {s.count_color}; }}
            QPushButton#split {{ background-color: {s.count_color};
                                 color: #0d1117; font-weight: bold; }}
            QPushButton#close {{
                background: transparent; color: #8b949e;
                border: none; font-size: 15px; padding: 0;
            }}
            QPushButton#close:hover {{
                background: #da3633; color: white; border-radius: 14px;
            }}
        """)
        self.count.set_style(s.font_family, s.count_color)
        if not s.animate_count:
            self.count.reset_anim()
        self.overlay.set_mode(s.animation)
        self._sync_sound()

        if s.rgb_outline:
            if not self._rgb_timer.isActive():
                self._rgb_timer.start()
        else:
            self._rgb_timer.stop()

        self._rebuild_bg_cache()
        self.update()

    def open_settings(self) -> None:
        if self._dialog is None:
            self._dialog = SettingsDialog(self.settings, self.tdc, self._input_mgr, self)
            self._dialog.changed.connect(self._on_settings_changed)
            self._dialog.data_changed.connect(self.refresh)
            self._dialog.hotkeys_changed.connect(self.hotkeys_changed.emit)
            self._dialog.pause_hotkeys.connect(self.pause_hotkeys.emit)
            self._dialog.resume_hotkeys.connect(self.resume_hotkeys.emit)
            self._dialog.finished.connect(self._on_settings_closed)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def _on_settings_changed(self) -> None:
        self._apply_settings()
        self.refresh()

    def _on_settings_closed(self, _result: int) -> None:
        self._dialog = None

    def on_add(self) -> None:
        self.tdc.daChest()
        self._save_timer.start()
        self._play_sound()
        if self.settings.animate_count:
            self.count.trigger_pop()
        self.refresh()

    def on_undo(self) -> None:
        prev = self.tdc.current
        self.tdc.undo()
        if self.tdc.current != prev:
            self._save_timer.start()
            if self.settings.animate_count:
                self.count.trigger_pop()
            self.refresh()

    def on_split(self) -> None:
        self._save_timer.stop()
        self.tdc.split()
        if self.settings.animate_count:
            self.count.trigger_pop()
        self.refresh()

    def _update_pace(self) -> None:
        t = self.tdc
        if t.is_timing:
            secs = int(t.elapsed_seconds)
            mins, rem = divmod(secs, 60)
            if secs >= 5:
                rate = t.current / (t.elapsed_seconds / 60.0)
                self.pace.setText(f"Time elapsed: {mins:02d}:{rem:02d}  •  {rate:.1f}/min")
            else:
                self.pace.setText(f"Time elapsed: {mins:02d}:{rem:02d}")
        elif t.last_split_summary:
            self.pace.setText(t.last_split_summary)
        else:
            self.pace.setText("Time elapsed: 00:00")

    def refresh(self) -> None:
        t = self.tdc
        self.count.set_text(str(t.current))
        avg = f"{t.average:.2f}" if self.settings.decimals else f"{round(t.average)}"
        self.stats.setText(
            f"Matches: {len(t.matches)}   |   Total: {t.total}   |   Avg: {avg}"
        )

        if t.is_timing:
            if not self._pace_timer.isActive():
                self._pace_timer.start()
        else:
            self._pace_timer.stop()

        self._update_pace()