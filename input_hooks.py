import ctypes
import sys
import threading
from ctypes import wintypes

import keyboard
from PySide6.QtCore import QObject, Signal

_MOD_NAMES = {
    "alt", "left alt", "right alt",
    "ctrl", "left ctrl", "right ctrl",
    "shift", "left shift", "right shift",
    "windows", "left windows", "right windows",
}


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


_HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)


class InputManager(QObject):
    """Global keyboard + extra mouse buttons and single-input bind capture."""
    add = Signal()
    undo = Signal()
    split = Signal()
    captured = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._active_kb: list = []
        self._mouse_binds: dict[str, Signal] = {}
        self._paused = False

        self._capturing = False
        self._capture_hook = None
        self._pending_mod: str | None = None

        self._mouse_tid = 0
        self._mouse_proc = None
        if sys.platform == "win32":
            threading.Thread(target=self._mouse_loop, daemon=True).start()

    def _mouse_loop(self) -> None:
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        u32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, _HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
        ]
        u32.SetWindowsHookExW.restype = wintypes.HHOOK
        u32.CallNextHookEx.argtypes = [
            wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        ]
        u32.CallNextHookEx.restype = ctypes.c_ssize_t

        self._mouse_tid = k32.GetCurrentThreadId()

        def low_level_mouse(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0 and wParam in (0x0207, 0x020B):
                btn = None
                if wParam == 0x0207:
                    btn = "middle"
                else:
                    info = ctypes.cast(lParam, ctypes.POINTER(_MSLLHOOKSTRUCT)).contents
                    xbtn = (info.mouseData >> 16) & 0xFFFF
                    if xbtn == 1:
                        btn = "mouse4"
                    elif xbtn == 2:
                        btn = "mouse5"

                if btn:
                    if self._capturing:
                        self.stop_capture()
                        self.captured.emit(btn)
                    elif not self._paused:
                        sig = self._mouse_binds.get(btn)
                        if sig is not None:
                            sig.emit()

            return u32.CallNextHookEx(None, nCode, wParam, lParam)

        self._mouse_proc = _HOOKPROC(low_level_mouse)
        hook = u32.SetWindowsHookExW(14, self._mouse_proc, None, 0)
        if not hook:
            return

        msg = wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
        u32.UnhookWindowsHookEx(hook)

    def clear_hotkeys(self) -> None:
        while self._active_kb:
            try:
                keyboard.remove_hotkey(self._active_kb.pop())
            except Exception:
                pass
        self._mouse_binds.clear()

    def register_hotkeys(self) -> None:
        self.clear_hotkeys()
        s = self._settings
        for combo, sig in (
            (s.key_add, self.add),
            (s.key_undo, self.undo),
            (s.key_split, self.split),
        ):
            key = (combo or "").strip().lower()
            if not key:
                continue
            if key in ("mouse4", "mouse5", "middle"):
                self._mouse_binds[key] = sig
            else:
                try:
                    self._active_kb.append(keyboard.add_hotkey(key, sig.emit))
                except Exception:
                    pass

    def pause(self) -> None:
        self._paused = True
        self.clear_hotkeys()

    def resume(self) -> None:
        self._paused = False
        self.register_hotkeys()

    def start_capture(self) -> None:
        self.stop_capture()
        self.pause()
        self._capturing = True
        self._pending_mod = None

        def on_key(event) -> None:
            if not self._capturing or not event.name:
                return
            name = event.name.lower()

            if event.event_type == "down":
                if name == "esc":
                    self.stop_capture()
                    self.captured.emit("")
                    return
                if name in _MOD_NAMES:
                    if self._pending_mod is None:
                        self._pending_mod = name
                    return
                combo = f"{self._pending_mod}+{name}" if self._pending_mod else name
                self.stop_capture()
                self.captured.emit(combo)

            elif event.event_type == "up" and name == self._pending_mod:
                self.stop_capture()
                self.captured.emit(name)

        self._capture_hook = keyboard.hook(on_key)

    def stop_capture(self) -> None:
        self._capturing = False
        self._pending_mod = None
        if self._capture_hook is not None:
            try:
                keyboard.unhook(self._capture_hook)
            except Exception:
                pass
            self._capture_hook = None

    def shutdown(self) -> None:
        self.stop_capture()
        self.clear_hotkeys()
        if sys.platform == "win32" and self._mouse_tid:
            ctypes.windll.user32.PostThreadMessageW(self._mouse_tid, 0x0012, 0, 0)
        keyboard.unhook_all()