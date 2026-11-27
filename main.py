import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from input_hooks import InputManager
from window import MainWindow

BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
ASSETS_DIR = BUNDLE_DIR / "assets"


def _load_icon() -> QIcon:
    for name in ("icon.ico", "icon.png"):
        p = ASSETS_DIR / name
        if p.is_file():
            img = QImage.fromData(p.read_bytes())
            if not img.isNull():
                icon = QIcon()
                for size in (16, 24, 32, 48, 64, 128, 256):
                    icon.addPixmap(
                        QPixmap.fromImage(
                            img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        )
                    )
                return icon
    return QIcon()


def main() -> None:
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "piratechestcounter.overlay.app.1"
        )

    app = QApplication(sys.argv)
    icon = _load_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()

    inputs = InputManager(window.settings, app)
    window.attach_input_manager(inputs)
    inputs.register_hotkeys()

    inputs.add.connect(window.on_add)
    inputs.undo.connect(window.on_undo)
    inputs.split.connect(window.on_split)
    window.hotkeys_changed.connect(inputs.register_hotkeys)
    window.pause_hotkeys.connect(inputs.pause)
    window.resume_hotkeys.connect(inputs.resume)

    app.aboutToQuit.connect(inputs.shutdown)
    app.aboutToQuit.connect(window.close_sound)
    app.aboutToQuit.connect(window.tdc.flush)
    app.aboutToQuit.connect(window.settings.save)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()