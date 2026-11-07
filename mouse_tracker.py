"""
mouse_tracker.py - Mouse Click Detection and Global Hotkeys for ZoomRecorder Pro
Tracks left clicks with coordinates and manages global keyboard shortcuts.
"""

import sys
import ctypes
from ctypes import wintypes
from typing import Tuple, Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal

from pynput import mouse, keyboard


class MouseTracker(QObject):
    """
    Detects mouse clicks, tracks cursor coordinates,
    and listens for global hotkeys (F9 = Start/Stop, F10 = Pause).
    """

    left_clicked = pyqtSignal(int, int)  # x, y global desktop coords
    mouse_moved = pyqtSignal(int, int)   # x, y global desktop coords
    hotkey_start_stop = pyqtSignal()
    hotkey_pause = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mouse_listener: Optional[mouse.Listener] = None
        self._hotkey_listener: Optional[keyboard.GlobalHotKeys] = None
        self._running = False
        self._click_callback: Optional[Callable[[int, int], None]] = None

    def set_click_callback(self, cb: Callable[[int, int], None]):
        """Direct recorder thread callback for zero latency."""
        self._click_callback = cb

    def start(self):
        """Start mouse and hotkey background listeners."""
        if self._running:
            return
        self._running = True

        # Mouse Listener
        self._mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_move=self._on_move
        )
        self._mouse_listener.daemon = True
        self._mouse_listener.start()

        # Keyboard Global HotKeys
        try:
            self._hotkey_listener = keyboard.GlobalHotKeys({
                '<f9>': self._on_f9,
                '<f10>': self._on_f10
            })
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
        except Exception as e:
            print(f"[MouseTracker] GlobalHotKeys init warning: {e}")

    def stop(self):
        """Stop background listeners cleanly."""
        self._running = False
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

        if self._hotkey_listener:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None

    def _on_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            # Emit direct callback for recording thread
            if self._click_callback:
                try:
                    self._click_callback(int(x), int(y))
                except Exception:
                    pass
            # Emit Qt Signal for main thread
            self.left_clicked.emit(int(x), int(y))

    def _on_move(self, x, y):
        # We also have fast GetCursorPos, but emit signal if needed
        self.mouse_moved.emit(int(x), int(y))

    def _on_f9(self):
        self.hotkey_start_stop.emit()

    def _on_f10(self):
        self.hotkey_pause.emit()

    @staticmethod
    def get_cursor_position() -> Tuple[int, int]:
        """Fast Win32 cursor position retrieval (sub-microsecond)."""
        try:
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            return int(pt.x), int(pt.y)
        except Exception:
            return (0, 0)
