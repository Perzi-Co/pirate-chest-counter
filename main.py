import ctypes
import sys
from pathlib import Path

import keyboard
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from window import HotkeyBridge, MainWindow

BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
ASSETS_DIR = BUNDLE_DIR / "assets"


def _set_windows_app_id() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "piratechestcounter.overlay.app.1"
            )
        except Exception:
            pass


def _load_icon() -> QIcon:
    for name in ("icon.ico", "icon.png"):
        p = ASSETS_DIR / name
        if p.is_file():
            img = QImage.fromData(p.read_bytes())
            if not img.isNull():
                icon = QIcon()
                for size in (16, 24, 32, 48, 64, 128, 256):
                    pm = QPixmap.fromImage(
                        img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                    icon.addPixmap(pm)
                return icon
    return QIcon()

def main() -> None:
    _set_windows_app_id()
    app = QApplication(sys.argv)

    icon = _load_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()

    bridge = HotkeyBridge()
    bridge.add.connect(window.on_add)
    bridge.undo.connect(window.on_undo)
    bridge.split.connect(window.on_split)

    active_hotkeys: list = []

    def clear_hotkeys() -> None:
        while active_hotkeys:
            hk = active_hotkeys.pop()
            try:
                keyboard.remove_hotkey(hk)
            except (KeyError, ValueError, AttributeError):
                pass

    def register_hotkeys() -> None:
        clear_hotkeys()
        s = window.settings
        for key_combo, callback in (
            (s.key_add, bridge.add.emit),
            (s.key_undo, bridge.undo.emit),
            (s.key_split, bridge.split.emit),
        ):
            if key_combo:
                try:
                    active_hotkeys.append(keyboard.add_hotkey(key_combo, callback))
                except (ValueError, KeyError):
                    pass

    register_hotkeys()
    window.hotkeys_changed.connect(register_hotkeys)
    window.pause_hotkeys.connect(clear_hotkeys)
    window.resume_hotkeys.connect(register_hotkeys)

    app.aboutToQuit.connect(clear_hotkeys)
    app.aboutToQuit.connect(keyboard.unhook_all)
    app.aboutToQuit.connect(window.tdc.flush)
    app.aboutToQuit.connect(window.settings.save)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()