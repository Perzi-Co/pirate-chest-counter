from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QCompleter, QDialog,
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout,
)

from settings import Settings
from tracker import TrackDatChest

_FONT_FAMILIES_CACHE: list[str] | None = None


def _get_font_families() -> list[str]:
    global _FONT_FAMILIES_CACHE
    if _FONT_FAMILIES_CACHE is None:
        _FONT_FAMILIES_CACHE = QFontDatabase.families()
    return _FONT_FAMILIES_CACHE


class HotkeyCaptureButton(QPushButton):
    hotkey_changed = Signal(str)

    def __init__(self, hotkey: str, input_mgr=None, parent=None):
        super().__init__(parent)
        self._hotkey = hotkey
        self._input_mgr = input_mgr
        self._listening = False
        self.setMinimumWidth(110)
        self.setCursor(Qt.PointingHandCursor)
        self._refresh_label()
        self.clicked.connect(self._start_listening)

    def hotkey(self) -> str:
        return self._hotkey

    def set_hotkey(self, hotkey: str) -> None:
        self._hotkey = hotkey
        self._listening = False
        self._refresh_label()

    def _refresh_label(self) -> None:
        if self._listening:
            self.setText("Press key/btn…")
            self.setStyleSheet(
                "QPushButton { border: 1px solid #f2c14e; color: #f2c14e; }"
            )
        else:
            self.setText(self._hotkey.upper())
            self.setStyleSheet("")

    def _start_listening(self) -> None:
        if self._listening or self._input_mgr is None:
            return
        self._listening = True
        self._refresh_label()
        self._input_mgr.captured.connect(self._on_captured)
        self._input_mgr.start_capture()

    def _on_captured(self, combo: str) -> None:
        if self._input_mgr is not None:
            try:
                self._input_mgr.captured.disconnect(self._on_captured)
            except Exception:
                pass
            self._input_mgr.resume()

        self._listening = False
        if combo:
            self._hotkey = combo
            self._refresh_label()
            self.hotkey_changed.emit(combo)
        else:
            self._refresh_label()


class ColorButton(QPushButton):
    color_changed = Signal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(56, 26)
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._color}; "
            f"border: 1px solid #30363d; border-radius: 4px; }}"
        )

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Choose color")
        if c.isValid():
            self._color = c.name()
            self._refresh()
            self.color_changed.emit(self._color)

    def set_color(self, color: str) -> None:
        self._color = color
        self._refresh()

    def color(self) -> str:
        return self._color


class EditDataDialog(QDialog):
    def __init__(self, tdc: TrackDatChest, decimals: bool, parent=None):
        super().__init__(parent)
        self.tdc = tdc
        self.decimals = decimals
        self.setWindowTitle("Edit Stats Data")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        curr_row = QHBoxLayout()
        curr_row.addWidget(QLabel("Current match chests:"))
        self.current_spin = QSpinBox()
        self.current_spin.setRange(0, 99999)
        self.current_spin.setValue(tdc.current)
        curr_row.addWidget(self.current_spin)
        curr_row.addStretch()
        layout.addLayout(curr_row)

        layout.addWidget(QLabel("Completed matches (comma-separated chest counts):"))
        self.matches_edit = QLineEdit(", ".join(str(m) for m in tdc.matches))
        self.matches_edit.setPlaceholderText("e.g. 4, 6, 3, 7  (leave empty for 0 matches)")
        self.matches_edit.textChanged.connect(self._update_preview)
        layout.addWidget(self.matches_edit)

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(self.preview_label)

        foot = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        self.btn_save = QPushButton("Save")
        btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._save)
        foot.addStretch()
        foot.addWidget(btn_cancel)
        foot.addWidget(self.btn_save)
        layout.addLayout(foot)

        self._update_preview()

    def _parse_matches(self) -> list[int] | None:
        raw = self.matches_edit.text().strip()
        if not raw:
            return []
        parsed: list[int] = []
        for token in raw.split(","):
            part = token.strip()
            if not part:
                continue
            if not part.isdigit():
                return None
            parsed.append(int(part))
        return parsed

    def _update_preview(self) -> None:
        matches = self._parse_matches()
        if matches is None:
            self.preview_label.setText("Invalid format — use non-negative integers separated by commas.")
            self.preview_label.setStyleSheet("color: #f85149; font-size: 12px;")
            self.btn_save.setEnabled(False)
            return

        total = sum(matches)
        avg_val = total / len(matches) if matches else 0.0
        avg_str = f"{avg_val:.2f}" if self.decimals else f"{round(avg_val)}"
        self.preview_label.setText(
            f"Preview → Matches: {len(matches)}   |   Total: {total}   |   Avg: {avg_str}"
        )
        self.preview_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self.btn_save.setEnabled(True)

    def _save(self) -> None:
        matches = self._parse_matches()
        if matches is None:
            return
        self.tdc.set_data(self.current_spin.value(), matches)
        self.accept()


class SettingsDialog(QDialog):
    changed = Signal()
    data_changed = Signal()
    hotkeys_changed = Signal()
    pause_hotkeys = Signal()
    resume_hotkeys = Signal()

    def __init__(self, settings: Settings, tdc: TrackDatChest, input_mgr=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.tdc = tdc
        self._input_mgr = input_mgr
        self.setWindowTitle("Pirate Chest Counter — Settings")
        self.setMinimumWidth(470)
        self._build()
        self._sync()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Wallpaper"))
        wall_row = QHBoxLayout()
        btn_pick = QPushButton("Choose Image…")
        btn_clear = QPushButton("Clear")
        btn_pick.clicked.connect(self._pick_wallpaper)
        btn_clear.clicked.connect(self._clear_wallpaper)
        wall_row.addWidget(btn_pick)
        wall_row.addWidget(btn_clear)
        wall_row.addStretch()
        layout.addLayout(wall_row)
        self.wall_label = QLabel("(none)")
        self.wall_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        self.wall_label.setWordWrap(True)
        layout.addWidget(self.wall_label)

        wall_mode_row = QHBoxLayout()
        wall_mode_row.addWidget(QLabel("Wallpaper fit"))
        self.wall_mode_combo = QComboBox()
        self.wall_mode_combo.addItems(["cover", "stretch", "contain"])
        self.wall_mode_combo.currentTextChanged.connect(self._on_wall_mode)
        wall_mode_row.addWidget(self.wall_mode_combo)
        wall_mode_row.addStretch()
        layout.addLayout(wall_mode_row)

        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("Background color"))
        self.bg_btn = ColorButton(self.settings.bg_color)
        self.bg_btn.color_changed.connect(self._on_bg_color)
        bg_row.addWidget(self.bg_btn)
        bg_row.addStretch()
        layout.addLayout(bg_row)

        self.transparent_cb = QCheckBox("Transparent background (needs no wallpaper)")
        self.transparent_cb.toggled.connect(self._on_transparent)
        layout.addWidget(self.transparent_cb)

        num_row = QHBoxLayout()
        num_row.addWidget(QLabel("Accent / Number color"))
        self.count_btn = ColorButton(self.settings.count_color)
        self.count_btn.color_changed.connect(self._on_count_color)
        num_row.addWidget(self.count_btn)
        num_row.addStretch()
        layout.addLayout(num_row)

        # RGB Outline (2 to 3 looping colors)
        rgb_row = QHBoxLayout()
        self.rgb_cb = QCheckBox("RGB outline")
        self.rgb_cb.toggled.connect(self._on_rgb_toggle)
        rgb_row.addWidget(self.rgb_cb)

        self.rgb_btns = [
            ColorButton("#f2c14e"),
            ColorButton("#38bdf8"),
            ColorButton("#a855f7"),
        ]
        for idx, btn in enumerate(self.rgb_btns):
            btn.color_changed.connect(lambda col, i=idx: self._on_rgb_color(i, col))
            rgb_row.addWidget(btn)

        self.btn_rgb_third = QPushButton("+ 3rd")
        self.btn_rgb_third.setFixedWidth(54)
        self.btn_rgb_third.clicked.connect(self._on_rgb_toggle_third)
        rgb_row.addWidget(self.btn_rgb_third)
        rgb_row.addStretch()
        layout.addLayout(rgb_row)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font"))
        self.font_combo = QComboBox()
        families = _get_font_families()
        self.font_combo.addItems(families)
        self.font_combo.setEditable(True)
        self.font_combo.setInsertPolicy(QComboBox.NoInsert)
        completer = QCompleter(families, self.font_combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.font_combo.setCompleter(completer)
        self.font_combo.currentTextChanged.connect(self._on_font)
        font_row.addWidget(self.font_combo, 1)
        layout.addLayout(font_row)

        anim_row = QHBoxLayout()
        anim_row.addWidget(QLabel("Background animation"))
        self.anim_combo = QComboBox()
        self.anim_combo.addItems(["none", "rain", "snow", "sparkles"])
        self.anim_combo.currentTextChanged.connect(self._on_anim)
        anim_row.addWidget(self.anim_combo)
        anim_row.addStretch()
        layout.addLayout(anim_row)

        # Custom +1 Sound Effect
        sfx_row = QHBoxLayout()
        sfx_row.addWidget(QLabel("+1 Sound"))
        btn_sfx = QPushButton("Choose Audio…")
        btn_sfx_clear = QPushButton("Clear")
        btn_sfx.clicked.connect(self._pick_sound)
        btn_sfx_clear.clicked.connect(self._clear_sound)
        self.sfx_label = QLabel("(none)")
        self.sfx_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        sfx_row.addWidget(btn_sfx)
        sfx_row.addWidget(btn_sfx_clear)
        sfx_row.addWidget(self.sfx_label, 1)
        layout.addLayout(sfx_row)

        self.anim_count_cb = QCheckBox("Animate counter on change")
        self.anim_count_cb.toggled.connect(self._on_anim_count)
        layout.addWidget(self.anim_count_cb)

        self.decimals_cb = QCheckBox("Show average with decimals")
        self.decimals_cb.toggled.connect(self._on_decimals)
        layout.addWidget(self.decimals_cb)

        # Keybinds (keyboard keys + extra mouse buttons)
        layout.addWidget(QLabel("Keybinds (click a button, then press any key or mouse button)"))
        keys_row = QHBoxLayout()
        self.key_add_btn = HotkeyCaptureButton(self.settings.key_add, self._input_mgr)
        self.key_undo_btn = HotkeyCaptureButton(self.settings.key_undo, self._input_mgr)
        self.key_split_btn = HotkeyCaptureButton(self.settings.key_split, self._input_mgr)

        for label_text, btn, handler in (
            ("+1:", self.key_add_btn, self._on_key_add),
            ("Undo:", self.key_undo_btn, self._on_key_undo),
            ("Split:", self.key_split_btn, self._on_key_split),
        ):
            keys_row.addWidget(QLabel(label_text))
            keys_row.addWidget(btn)
            btn.hotkey_changed.connect(handler)
        keys_row.addStretch()
        layout.addLayout(keys_row)

        # Stats data actions
        layout.addWidget(QLabel("Stats data"))
        data_row = QHBoxLayout()
        btn_edit_data = QPushButton("Edit Data…")
        btn_reset_stats = QPushButton("Reset All Stats")
        btn_reset_stats.setStyleSheet("QPushButton { color: #f85149; }")
        btn_edit_data.clicked.connect(self._on_edit_data)
        btn_reset_stats.clicked.connect(self._on_reset_stats)
        data_row.addWidget(btn_edit_data)
        data_row.addWidget(btn_reset_stats)
        data_row.addStretch()
        layout.addLayout(data_row)

        layout.addStretch()

        foot = QHBoxLayout()
        btn_reset = QPushButton("Reset settings")
        btn_reset.clicked.connect(self._on_reset_settings)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        foot.addWidget(btn_reset)
        foot.addStretch()
        foot.addWidget(btn_close)
        layout.addLayout(foot)

    def _sync_rgb_ui(self) -> None:
        s = self.settings
        has_third = len(s.rgb_colors) >= 3
        self.rgb_cb.blockSignals(True)
        self.rgb_cb.setChecked(s.rgb_outline)
        self.rgb_cb.blockSignals(False)

        self.rgb_btns[0].set_color(s.rgb_colors[0])
        self.rgb_btns[1].set_color(s.rgb_colors[1])
        self.rgb_btns[2].set_color(s.rgb_colors[2] if has_third else "#a855f7")

        self.rgb_btns[0].setEnabled(s.rgb_outline)
        self.rgb_btns[1].setEnabled(s.rgb_outline)
        self.rgb_btns[2].setVisible(has_third)
        self.rgb_btns[2].setEnabled(s.rgb_outline and has_third)
        self.btn_rgb_third.setEnabled(s.rgb_outline)
        self.btn_rgb_third.setText("− 3rd" if has_third else "+ 3rd")

    def _sync(self) -> None:
        s = self.settings
        self.wall_label.setText(s.wallpaper_path or "(none)")
        self.sfx_label.setText(Path(s.sound_path).name if s.sound_path else "(none)")
        self.transparent_cb.blockSignals(True)
        self.transparent_cb.setChecked(s.transparent)
        self.transparent_cb.setEnabled(not bool(s.wallpaper_path))
        self.transparent_cb.blockSignals(False)

        self.font_combo.blockSignals(True)
        idx = self.font_combo.findText(s.font_family, Qt.MatchFixedString)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        else:
            self.font_combo.setEditText(s.font_family)
        self.font_combo.blockSignals(False)

        self.anim_combo.blockSignals(True)
        self.anim_combo.setCurrentText(s.animation)
        self.anim_combo.blockSignals(False)
        self.anim_count_cb.blockSignals(True)
        self.anim_count_cb.setChecked(s.animate_count)
        self.anim_count_cb.blockSignals(False)
        self.wall_mode_combo.blockSignals(True)
        self.wall_mode_combo.setCurrentText(s.wallpaper_mode)
        self.wall_mode_combo.blockSignals(False)
        self.decimals_cb.blockSignals(True)
        self.decimals_cb.setChecked(s.decimals)
        self.decimals_cb.blockSignals(False)
        self.bg_btn.set_color(s.bg_color)
        self.count_btn.set_color(s.count_color)
        self._sync_rgb_ui()
        self.key_add_btn.set_hotkey(s.key_add)
        self.key_undo_btn.set_hotkey(s.key_undo)
        self.key_split_btn.set_hotkey(s.key_split)

    def _pick_wallpaper(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose wallpaper", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path:
            return
        self.settings.wallpaper_path = path
        self.settings.transparent = False
        self.wall_label.setText(path)
        self.transparent_cb.blockSignals(True)
        self.transparent_cb.setChecked(False)
        self.transparent_cb.setEnabled(False)
        self.transparent_cb.blockSignals(False)
        self.changed.emit()

    def _clear_wallpaper(self) -> None:
        self.settings.wallpaper_path = ""
        self.wall_label.setText("(none)")
        self.transparent_cb.setEnabled(True)
        self.changed.emit()

    def _pick_sound(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose +1 Chest sound", "",
            "Audio (*.mp3 *.wav *.wma *.m4a)")
        if not path:
            return
        self.settings.sound_path = path
        self.sfx_label.setText(Path(path).name)
        self.changed.emit()

    def _clear_sound(self) -> None:
        self.settings.sound_path = ""
        self.sfx_label.setText("(none)")
        self.changed.emit()

    def _on_rgb_toggle(self, checked: bool) -> None:
        self.settings.rgb_outline = checked
        self._sync_rgb_ui()
        self.changed.emit()

    def _on_rgb_color(self, idx: int, color: str) -> None:
        if idx < len(self.settings.rgb_colors):
            self.settings.rgb_colors[idx] = color
            self.changed.emit()

    def _on_rgb_toggle_third(self) -> None:
        if len(self.settings.rgb_colors) >= 3:
            self.settings.rgb_colors = self.settings.rgb_colors[:2]
        else:
            self.settings.rgb_colors.append(self.rgb_btns[2].color())
        self._sync_rgb_ui()
        self.changed.emit()

    def _on_wall_mode(self, mode: str) -> None:
        self.settings.wallpaper_mode = mode
        self.changed.emit()

    def _on_bg_color(self, color: str) -> None:
        self.settings.bg_color = color
        self.changed.emit()

    def _on_count_color(self, color: str) -> None:
        self.settings.count_color = color
        self.changed.emit()

    def _on_font(self, family: str) -> None:
        if family and family in _get_font_families():
            self.settings.font_family = family
            self.changed.emit()

    def _on_anim(self, mode: str) -> None:
        self.settings.animation = mode
        self.changed.emit()

    def _on_anim_count(self, checked: bool) -> None:
        self.settings.animate_count = checked
        self.changed.emit()

    def _on_decimals(self, checked: bool) -> None:
        self.settings.decimals = checked
        self.changed.emit()

    def _on_transparent(self, checked: bool) -> None:
        self.settings.transparent = checked
        self.changed.emit()

    def _on_key_add(self, combo: str) -> None:
        self.settings.key_add = combo
        self.hotkeys_changed.emit()

    def _on_key_undo(self, combo: str) -> None:
        self.settings.key_undo = combo
        self.hotkeys_changed.emit()

    def _on_key_split(self, combo: str) -> None:
        self.settings.key_split = combo
        self.hotkeys_changed.emit()

    def _on_edit_data(self) -> None:
        dlg = EditDataDialog(self.tdc, self.settings.decimals, self)
        if dlg.exec() == QDialog.Accepted:
            self.data_changed.emit()

    def _on_reset_stats(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset All Stats",
            "Reset current chests, matches, total, and average to 0?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.tdc.reset_all()
            self.data_changed.emit()

    def _on_reset_settings(self) -> None:
        d = Settings()
        for k, v in asdict(d).items():
            setattr(self.settings, k, v)
        self._sync()
        self.changed.emit()
        self.hotkeys_changed.emit()

    def done(self, result: int) -> None:
        if self._input_mgr is not None:
            self._input_mgr.stop_capture()
            self._input_mgr.resume()
        self.settings.save()
        super().done(result)