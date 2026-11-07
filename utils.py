"""
utils.py - Helper utilities for ZoomRecorder Pro
Includes:
- Crisp click sound generator and async player
- Background audio recording & FFmpeg audio/video muxing
- Transparent screen area selection overlay
- Window enumeration for window capture
- File naming and path helpers
"""

import os
import sys
import wave
import struct
import math
import time
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional, Tuple, List, Dict

try:
    import winsound
except ImportError:
    winsound = None

try:
    import sounddevice as sd
    import numpy as np
    AUDIO_AVAILABLE = True
except Exception:
    AUDIO_AVAILABLE = False
    np = None

try:
    import win32gui
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QCursor


def get_default_recordings_dir() -> Path:
    """Return default folder: Desktop/ZoomRecorder or Videos/ZoomRecorder."""
    desktop = Path.home() / "Desktop" / "ZoomRecorder"
    try:
        desktop.mkdir(parents=True, exist_ok=True)
        return desktop
    except Exception:
        videos = Path.home() / "Videos" / "ZoomRecorder"
        videos.mkdir(parents=True, exist_ok=True)
        return videos


def generate_filename(output_dir: Path) -> Path:
    """Generate timestamped filename: ZoomRecorder_YYYY-MM-DD_HH-MM-SS.mp4"""
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    return output_dir / f"ZoomRecorder_{timestamp}.mp4"


def format_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_size(num_bytes: int) -> str:
    """Format byte size into human readable string (KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


class ClickSoundManager:
    """Generates and plays crisp mouse click sound without blocking."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ClickSoundManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.sound_file = Path(os.environ.get("TEMP", ".")) / "zoomrecorder_click.wav"
        self._ensure_click_sound()

    def _ensure_click_sound(self):
        """Create a clean mechanical mouse-click sound wave file."""
        try:
            sample_rate = 44100
            duration = 0.035  # 35 milliseconds
            num_samples = int(sample_rate * duration)
            samples = []

            for i in range(num_samples):
                t = i / sample_rate
                # High-pass click transient with exponential decay
                decay = math.exp(-i / (sample_rate * 0.007))
                wave_val = (
                    0.6 * math.sin(2 * math.pi * 1800 * t) +
                    0.3 * math.sin(2 * math.pi * 3200 * t) +
                    0.1 * math.sin(2 * math.pi * 800 * t)
                )
                val = int(28000.0 * decay * wave_val)
                # Clamp
                val = max(-32767, min(32767, val))
                samples.append(val)

            with wave.open(str(self.sound_file), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        except Exception as e:
            print(f"[ClickSoundManager] Warning: Failed to generate click.wav: {e}")

    def play_click(self):
        """Play click sound asynchronously."""
        if not winsound:
            return
        try:
            if self.sound_file.exists():
                winsound.PlaySound(str(self.sound_file), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass


class AudioRecorder:
    """Records microphone / default system audio to a WAV file."""

    def __init__(self, sample_rate: int = 44100, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_recording = False
        self.is_paused = False
        self.audio_frames = []
        self.output_wav: Optional[Path] = None
        self.stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def start(self, output_wav: Path):
        """Start audio recording."""
        if not AUDIO_AVAILABLE:
            return False

        self.output_wav = output_wav
        self.audio_frames = []
        self.is_recording = True
        self.is_paused = False

        def audio_callback(indata, frames, time_info, status):
            if self.is_recording and not self.is_paused:
                with self._lock:
                    self.audio_frames.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=audio_callback,
            )
            self.stream.start()
            return True
        except Exception as e:
            print(f"[AudioRecorder] Failed to start stream: {e}")
            self.is_recording = False
            return False

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self) -> Optional[Path]:
        """Stop recording and write WAV file."""
        self.is_recording = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if not self.audio_frames or not self.output_wav:
            return None

        try:
            with self._lock:
                all_data = np.concatenate(self.audio_frames, axis=0)
            with wave.open(str(self.output_wav), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(all_data.tobytes())
            return self.output_wav
        except Exception as e:
            print(f"[AudioRecorder] Error saving audio file: {e}")
            return None


def mux_audio_video(video_path: Path, audio_path: Path, final_path: Path) -> bool:
    """
    Merge video and audio using FFmpeg if available.
    Returns True if merged successfully, False otherwise.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return False

    temp_final = final_path.with_name(final_path.stem + "_muxed.mp4")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(temp_final)
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if res.returncode == 0 and temp_final.exists() and temp_final.stat().st_size > 0:
            if video_path.exists():
                try:
                    video_path.unlink()
                except Exception:
                    pass
            temp_final.rename(final_path)
            if audio_path.exists():
                try:
                    audio_path.unlink()
                except Exception:
                    pass
            return True
    except Exception as e:
        print(f"[Mux] FFmpeg mux error: {e}")

    return False


def list_open_windows() -> List[Dict]:
    """Return visible desktop windows with their HWND, title, and coordinates."""
    windows = []
    if not WIN32_AVAILABLE:
        return windows

    def enum_cb(hwnd, _):
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return
        # Filter common hidden / background shell windows
        if title in ["Program Manager", "Settings", "Default IME", "MSCTFIME UI"]:
            return
        rect = win32gui.GetWindowRect(hwnd)
        x1, y1, x2, y2 = rect
        w = x2 - x1
        h = y2 - y1
        if w > 80 and h > 80:
            windows.append({
                "hwnd": hwnd,
                "title": title,
                "rect": (x1, y1, w, h)
            })

    win32gui.EnumWindows(enum_cb, None)
    return windows


class AreaSelectOverlay(QDialog):
    """
    Full-screen semi-transparent overlay to select custom capture rectangle.
    """
    area_selected = pyqtSignal(int, int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)
        self.showFullScreen()

        self.start_pos: Optional[QPoint] = None
        self.current_pos: Optional[QPoint] = None
        self.is_selecting = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.current_pos = event.pos()
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            rect = self._get_rect()
            if rect.width() >= 40 and rect.height() >= 40:
                self.area_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
                self.accept()
            else:
                self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            rect = self._get_rect()
            if rect.width() >= 40 and rect.height() >= 40:
                self.area_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
                self.accept()
            else:
                self.reject()

    def _get_rect(self) -> QRect:
        if not self.start_pos or not self.current_pos:
            return QRect()
        x1 = min(self.start_pos.x(), self.current_pos.x())
        y1 = min(self.start_pos.y(), self.current_pos.y())
        x2 = max(self.start_pos.x(), self.current_pos.x())
        y2 = max(self.start_pos.y(), self.current_pos.y())
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dark semi-transparent scrim
        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))

        # Tip at top
        painter.setPen(QColor(240, 240, 240))
        painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
        tip_text = "DRAG TO SELECT RECORDING AREA  •  PRESS ESC TO CANCEL"
        painter.drawText(0, 40, self.width(), 30, Qt.AlignHCenter, tip_text)

        rect = self._get_rect()
        if not rect.isEmpty():
            # Clear selected area
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # Draw glowing selection border
            pen = QPen(QColor(0, 200, 255), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw size badge
            badge_text = f"{rect.width()} × {rect.height()} px"
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            badge_w, badge_h = 130, 26
            bx = max(10, rect.x() + (rect.width() - badge_w) // 2)
            by = rect.y() - badge_h - 6
            if by < 60:
                by = rect.y() + 8

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(20, 20, 24, 220))
            painter.drawRoundedRect(bx, by, badge_w, badge_h, 4, 4)

            painter.setPen(QColor(0, 255, 200))
            painter.drawText(bx, by, badge_w, badge_h, Qt.AlignCenter, badge_text)


class WindowSelectDialog(QDialog):
    """Dialog to pick a specific active window to record."""

    def __init__(self, windows: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Window to Record")
        self.resize(520, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #f0f0f0;
            }
            QListWidget {
                background-color: #151518;
                border: 1px solid #33333d;
                border-radius: 6px;
                padding: 6px;
                color: #e0e0e0;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #272730;
            }
            QListWidget::item:selected {
                background-color: #ff334b;
                color: #ffffff;
            }
            QPushButton {
                background-color: #2b2b35;
                color: #ffffff;
                border: 1px solid #3a3a46;
                border-radius: 5px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3b3b4a;
            }
            QPushButton#btnSelect {
                background-color: #ff334b;
                border: none;
            }
            QPushButton#btnSelect:hover {
                background-color: #ff4b60;
            }
        """)

        self.selected_window: Optional[Dict] = None
        self.windows = windows

        layout = QVBoxLayout(self)
        title_label = QLabel("Choose an open window:")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; margin-bottom: 4px;")
        layout.addWidget(title_label)

        self.list_widget = QListWidget()
        for win in windows:
            rect = win["rect"]
            item_text = f"{win['title']}   [{rect[2]} × {rect[3]}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, win)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_select = QPushButton("Select Window")
        btn_select.setObjectName("btnSelect")
        btn_select.clicked.connect(self._on_select)
        btn_box.addWidget(btn_select)
        layout.addLayout(btn_box)

        self.list_widget.itemDoubleClicked.connect(self._on_select)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_select(self):
        curr = self.list_widget.currentItem()
        if curr:
            self.selected_window = curr.data(Qt.UserRole)
            self.accept()
