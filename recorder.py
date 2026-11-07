"""
recorder.py - High-Performance Screen Capture, Video Writing, and Zoom Logic
Handles:
- Screen capture via mss with fallback to QScreen
- Mouse click zoom animation with smoothstep interpolation
- Yellow cursor highlight and expanding click ripple effects
- Multi-resolution scaling (1080p, 720p, Original) and FPS pacing (30/60 FPS)
- Audio capture and FFmpeg muxing
"""

import os
import sys
import time
import math
import threading
from pathlib import Path
from typing import Optional, Tuple, List, Dict

import cv2
import numpy as np

try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtGui import QGuiApplication, QImage

from utils import (
    ClickSoundManager,
    AudioRecorder,
    mux_audio_video,
    generate_filename
)
from mouse_tracker import MouseTracker


class ScreenRecorder(QThread):
    """
    Background worker thread capturing screen, applying smooth zoom,
    drawing overlays, and encoding to MP4.
    """

    frame_ready = pyqtSignal(np.ndarray)       # Emits frame for UI Live Preview
    stats_updated = pyqtSignal(float, int, int) # elapsed_sec, frames, file_size_bytes
    recording_finished = pyqtSignal(str)       # final output file path
    error_occurred = pyqtSignal(str)           # error description

    def __init__(
        self,
        output_dir: Path,
        capture_rect: Optional[Tuple[int, int, int, int]] = None,
        quality: str = "1080p",
        fps: int = 30,
        zoom_level: float = 2.0,
        zoom_duration: float = 1.5,
        mouse_highlight: bool = True,
        click_sound: bool = True,
        record_audio: bool = True,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.output_dir = output_dir
        self.capture_rect = capture_rect  # (x, y, w, h) in desktop coordinates
        self.quality = quality            # "1080p", "720p", "Original"
        self.fps = fps                    # 30 or 60
        self.zoom_level = zoom_level      # 1.5, 2.0, 3.0
        self.zoom_duration = zoom_duration # 1.0 to 3.0 seconds
        self.mouse_highlight = mouse_highlight
        self.click_sound = click_sound
        self.record_audio = record_audio

        # Runtime control flags
        self._is_running = False
        self._is_paused = False
        self._stop_requested = False

        # Click Sound Manager
        self.sound_mgr = ClickSoundManager()

        # Audio recorder
        self.audio_recorder = AudioRecorder()
        self.temp_wav_path: Optional[Path] = None
        self.temp_mp4_path: Optional[Path] = None
        self.final_mp4_path: Optional[Path] = None

        # Zoom state
        self._zoom_active = False
        self._zoom_start_time = 0.0
        self._zoom_start_factor = 1.0
        self._zoom_target_factor = 1.0
        self._zoom_center = (0.0, 0.0)
        self._zoom_curr_center = (0.0, 0.0)
        self._zoom_anim_time = 0.3  # 0.3s zoom-in, 0.3s zoom-out

        # Ripples list: list of dicts {'x', 'y', 'start_time', 'duration', 'max_r'}
        self._ripples: List[Dict] = []
        self._state_lock = threading.Lock()

        # MSS screen capture instance
        self._sct = None
        self._use_qt_capture = False

    def on_click_event(self, global_x: int, global_y: int):
        """Called immediately when mouse left-click occurs."""
        if not self._is_running or self._is_paused:
            return

        # Check if click is inside our capture rectangle
        rx, ry, rw, rh = self._get_effective_rect()
        if not (rx <= global_x < rx + rw and ry <= global_y < ry + rh):
            return

        # Play click sound if enabled
        if self.click_sound:
            self.sound_mgr.play_click()

        local_x = float(global_x - rx)
        local_y = float(global_y - ry)
        now = time.time()

        with self._state_lock:
            # Trigger Zoom Animation
            self._zoom_active = True
            self._zoom_start_time = now
            self._zoom_start_factor = 1.0
            self._zoom_target_factor = float(self.zoom_level)
            self._zoom_center = (local_x, local_y)
            self._zoom_curr_center = (local_x, local_y)

            # Trigger Ripple Effect
            self._ripples.append({
                "x": local_x,
                "y": local_y,
                "start_time": now,
                "duration": 0.45,
                "max_radius": 50
            })

    def pause(self):
        self._is_paused = True
        if self.record_audio and self.audio_recorder:
            self.audio_recorder.pause()

    def resume(self):
        self._is_paused = False
        if self.record_audio and self.audio_recorder:
            self.audio_recorder.resume()

    def stop(self):
        self._stop_requested = True

    def _get_effective_rect(self) -> Tuple[int, int, int, int]:
        """Return capture area (x, y, w, h). If None, captures primary screen."""
        if self.capture_rect:
            return self.capture_rect

        # Default to primary screen
        screen = QGuiApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            return (geom.x(), geom.y(), geom.width(), geom.height())
        return (0, 0, 1920, 1080)

    def _determine_output_size(self, cap_w: int, cap_h: int) -> Tuple[int, int]:
        """Calculate target output resolution according to selected Quality."""
        if self.quality == "1080p":
            target_w, target_h = 1920, 1080
        elif self.quality == "720p":
            target_w, target_h = 1280, 720
        else:
            # Original resolution, ensure even dimensions for video codecs
            target_w, target_h = cap_w, cap_h

        # OpenCV VideoWriter requires even width and height
        target_w = target_w - (target_w % 2)
        target_h = target_h - (target_h % 2)
        return (target_w, target_h)

    def _init_capture(self) -> bool:
        """Initialize mss capture; fallback to Qt if mss fails."""
        if MSS_AVAILABLE:
            try:
                self._sct = mss.mss()
                # Test grab
                rx, ry, rw, rh = self._get_effective_rect()
                mon = {"left": rx, "top": ry, "width": rw, "height": rh}
                _ = self._sct.grab(mon)
                self._use_qt_capture = False
                return True
            except Exception as e:
                print(f"[Recorder] mss init warning ({e}), falling back to QScreen grab.")
                self._use_qt_capture = True
        else:
            self._use_qt_capture = True
        return True

    def _grab_frame(self, rect: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Grab a single screen frame as BGR numpy array."""
        rx, ry, rw, rh = rect
        if not self._use_qt_capture and self._sct:
            try:
                mon = {"left": rx, "top": ry, "width": rw, "height": rh}
                sct_img = self._sct.grab(mon)
                # mss returns BGRA array
                frame = np.array(sct_img, dtype=np.uint8)
                # Convert BGRA to BGR
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            except Exception:
                # Switch to Qt fallback
                self._use_qt_capture = True

        # Qt Screen grab fallback
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return None

        try:
            pixmap = screen.grabWindow(0, rx, ry, rw, rh)
            qimage = pixmap.toImage().convertToFormat(QImage.Format_RGB888)
            width = qimage.width()
            height = qimage.height()
            ptr = qimage.bits()
            ptr.setsize(qimage.byteCount())
            arr = np.array(ptr, dtype=np.uint8).reshape((height, width, 3))
            # Qt RGB to OpenCV BGR
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"[Recorder] Frame grab error: {e}")
            return None

    def run(self):
        self._is_running = True
        self._stop_requested = False

        self._init_capture()
        rx, ry, rw, rh = self._get_effective_rect()
        out_w, out_h = self._determine_output_size(rw, rh)

        # File paths
        self.final_mp4_path = generate_filename(self.output_dir)
        self.temp_mp4_path = self.output_dir / f"temp_{self.final_mp4_path.name}"
        self.temp_wav_path = self.output_dir / f"temp_{self.final_mp4_path.stem}.wav"

        # OpenCV VideoWriter with mp4v
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            str(self.temp_mp4_path),
            fourcc,
            float(self.fps),
            (out_w, out_h)
        )

        if not writer.isOpened():
            self.error_occurred.emit("Failed to open OpenCV VideoWriter.")
            self._is_running = False
            return

        # Start Audio recording if enabled
        if self.record_audio:
            self.audio_recorder.start(self.temp_wav_path)

        frame_duration = 1.0 / self.fps
        start_time = time.time()
        frames_written = 0
        last_stats_time = start_time
        total_paused_time = 0.0
        pause_start = 0.0

        try:
            while not self._stop_requested:
                loop_start = time.time()

                if self._is_paused:
                    if pause_start == 0.0:
                        pause_start = loop_start
                    time.sleep(0.05)
                    continue
                else:
                    if pause_start > 0.0:
                        total_paused_time += (loop_start - pause_start)
                        pause_start = 0.0

                # 1. Grab raw screen frame
                raw_frame = self._grab_frame((rx, ry, rw, rh))
                if raw_frame is None:
                    time.sleep(frame_duration)
                    continue

                # 2. Process Zoom & Overlay effects
                now = time.time()
                cur_x, cur_y = MouseTracker.get_cursor_position()
                processed_frame = self._process_frame(
                    raw_frame,
                    rx, ry, rw, rh,
                    out_w, out_h,
                    cur_x, cur_y,
                    now
                )

                # 3. Write frame to video
                writer.write(processed_frame)
                frames_written += 1

                # 4. Emit live preview frame (subsampled or throttled for smooth UI)
                if frames_written % 2 == 0 or self.fps <= 30:
                    self.frame_ready.emit(processed_frame)

                # 5. Periodically emit stats
                if now - last_stats_time >= 0.5:
                    elapsed = now - start_time - total_paused_time
                    file_size = 0
                    if self.temp_mp4_path.exists():
                        file_size = self.temp_mp4_path.stat().st_size
                    self.stats_updated.emit(elapsed, frames_written, file_size)
                    last_stats_time = now

                # 6. Precise FPS pacing
                elapsed_loop = time.time() - loop_start
                sleep_time = frame_duration - elapsed_loop
                if sleep_time > 0.001:
                    time.sleep(sleep_time)

        except Exception as e:
            self.error_occurred.emit(f"Recording error: {e}")
        finally:
            writer.release()
            if self._sct:
                try:
                    self._sct.close()
                except Exception:
                    pass

            # Finalize audio and mux
            audio_saved = False
            if self.record_audio:
                saved_wav = self.audio_recorder.stop()
                if saved_wav and saved_wav.exists() and saved_wav.stat().st_size > 1000:
                    audio_saved = True

            final_file = self.final_mp4_path
            if audio_saved and self.temp_wav_path and self.temp_wav_path.exists():
                mux_success = mux_audio_video(self.temp_mp4_path, self.temp_wav_path, self.final_mp4_path)
                if not mux_success:
                    # Rename temp video to final video
                    if self.temp_mp4_path.exists():
                        self.temp_mp4_path.rename(self.final_mp4_path)
            else:
                if self.temp_mp4_path.exists():
                    self.temp_mp4_path.rename(self.final_mp4_path)

            self._is_running = False
            self.recording_finished.emit(str(final_file))

    def _process_frame(
        self,
        frame: np.ndarray,
        rx: int, ry: int, rw: int, rh: int,
        out_w: int, out_h: int,
        cursor_x: int, cursor_y: int,
        now: float
    ) -> np.ndarray:
        """
        Calculates current zoom factor with smoothstep interpolation,
        crops ROI, resizes to output dimensions, and overlays cursor/ripples.
        """
        orig_h, orig_w = frame.shape[:2]

        # Calculate current zoom factor
        zoom_factor, (cx, cy) = self._compute_zoom_state(now, orig_w, orig_h)

        # Apply Zoom Cropping if zoom > 1.0
        is_zoomed = zoom_factor > 1.005
        if is_zoomed:
            crop_w = max(40, int(orig_w / zoom_factor))
            crop_h = max(30, int(orig_h / zoom_factor))

            x1 = int(cx - crop_w // 2)
            y1 = int(cy - crop_h // 2)

            # Clamp boundaries
            x1 = max(0, min(x1, orig_w - crop_w))
            y1 = max(0, min(y1, orig_h - crop_h))
            x2 = x1 + crop_w
            y2 = y1 + crop_h

            cropped = frame[y1:y2, x1:x2]
            scaled_frame = cv2.resize(cropped, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        else:
            x1, y1 = 0, 0
            crop_w, crop_h = orig_w, orig_h
            if orig_w != out_w or orig_h != out_h:
                scaled_frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
            else:
                scaled_frame = frame.copy()

        # Coordinate transformation helper from original captured pixels to output frame
        def to_output_coords(px: float, py: float) -> Tuple[int, int]:
            if is_zoomed:
                norm_x = (px - x1) / float(crop_w)
                norm_y = (py - y1) / float(crop_h)
            else:
                norm_x = px / float(orig_w)
                norm_y = py / float(orig_h)
            ox = int(norm_x * out_w)
            oy = int(norm_y * out_h)
            return ox, oy

        # 1. Draw Expanding Click Ripples
        self._draw_ripples(scaled_frame, to_output_coords, now, out_w, out_h)

        # 2. Draw Mouse Highlight & Cursor Pointer
        # Map global cursor coordinates to capture frame coordinates
        cur_local_x = float(cursor_x - rx)
        cur_local_y = float(cursor_y - ry)
        out_cur_x, out_cur_y = to_output_coords(cur_local_x, cur_local_y)

        # Check if cursor is inside output frame
        if 0 <= out_cur_x < out_w and 0 <= out_cur_y < out_h:
            # Always draw yellow highlight if enabled, or if currently zoomed
            if self.mouse_highlight or is_zoomed:
                self._draw_cursor_highlight(scaled_frame, out_cur_x, out_cur_y, is_zoomed)
            # Draw crisp modern mouse pointer arrow
            self._draw_cursor_pointer(scaled_frame, out_cur_x, out_cur_y)

        return scaled_frame

    def _compute_zoom_state(self, now: float, orig_w: int, orig_h: int) -> Tuple[float, Tuple[float, float]]:
        """Calculate zoom factor using smoothstep easing."""
        with self._state_lock:
            if not self._zoom_active:
                return 1.0, (orig_w / 2.0, orig_h / 2.0)

            t_elapsed = now - self._zoom_start_time
            t_in = self._zoom_anim_time
            t_hold = self.zoom_duration
            t_out = self._zoom_anim_time
            t_total = t_in + t_hold + t_out

            target_z = self._zoom_target_factor

            if t_elapsed < t_in:
                # Zoom-In Phase: 0.0 to 1.0 progress
                p = max(0.0, min(1.0, t_elapsed / t_in))
                # Smoothstep: 3p^2 - 2p^3
                easing = 3.0 * (p ** 2) - 2.0 * (p ** 3)
                curr_z = 1.0 + (target_z - 1.0) * easing
            elif t_elapsed < (t_in + t_hold):
                # Hold Phase
                curr_z = target_z
            elif t_elapsed < t_total:
                # Zoom-Out Phase: 1.0 down to 0.0
                p = max(0.0, min(1.0, (t_elapsed - t_in - t_hold) / t_out))
                easing = 1.0 - (3.0 * (p ** 2) - 2.0 * (p ** 3))
                curr_z = 1.0 + (target_z - 1.0) * easing
            else:
                # Completed
                self._zoom_active = False
                curr_z = 1.0

            return curr_z, self._zoom_center

    def _draw_ripples(self, img: np.ndarray, to_out_fn, now: float, out_w: int, out_h: int):
        """Draw expanding click ripples with smooth fading alpha."""
        with self._state_lock:
            active_ripples = []
            for r in self._ripples:
                dt = now - r["start_time"]
                if dt < r["duration"]:
                    active_ripples.append(r)
                    p = dt / r["duration"]  # 0.0 to 1.0
                    radius = int(8 + (r["max_radius"] - 8) * p)
                    alpha = max(0.0, min(0.9, (1.0 - p) * 0.9))

                    ox, oy = to_out_fn(r["x"], r["y"])
                    if 0 <= ox < out_w and 0 <= oy < out_h:
                        self._draw_circle_alpha(img, ox, oy, radius, (0, 220, 255), alpha, thickness=3)
                        # Secondary concentric ripple
                        if radius > 14:
                            self._draw_circle_alpha(img, ox, oy, int(radius * 0.65), (0, 255, 255), alpha * 0.7, thickness=2)

            self._ripples = active_ripples

    def _draw_cursor_highlight(self, img: np.ndarray, x: int, y: int, is_zoomed: bool):
        """Draw soft yellow glowing circle around cursor."""
        radius = 28 if is_zoomed else 22
        # Soft yellow glow
        self._draw_circle_alpha(img, x, y, radius, (0, 220, 255), 0.35, thickness=-1)
        # Crisp outer circle ring
        cv2.circle(img, (x, y), radius, (0, 255, 255), 2, lineType=cv2.LINE_AA)
        # Center subtle dot
        cv2.circle(img, (x, y), 3, (0, 180, 255), -1, lineType=cv2.LINE_AA)

    def _draw_cursor_pointer(self, img: np.ndarray, x: int, y: int):
        """Draw standard white pointer cursor with black outline."""
        # Standard cursor shape polygon points
        pts = np.array([
            [x, y],
            [x, y + 16],
            [x + 4, y + 13],
            [x + 8, y + 20],
            [x + 11, y + 18],
            [x + 7, y + 12],
            [x + 13, y + 12]
        ], dtype=np.int32)

        # White fill
        cv2.fillPoly(img, [pts], (255, 255, 255), lineType=cv2.LINE_AA)
        # Black outline
        cv2.polylines(img, [pts], isClosed=True, color=(0, 0, 0), thickness=1, lineType=cv2.LINE_AA)

    @staticmethod
    def _draw_circle_alpha(
        img: np.ndarray,
        cx: int, cy: int,
        radius: int,
        color: Tuple[int, int, int],
        alpha: float,
        thickness: int = -1
    ):
        """Draw circle with alpha blending on sub-region (fast, zero frame drop)."""
        h, w = img.shape[:2]
        pad = abs(thickness) + radius + 2
        x1 = max(0, cx - pad)
        y1 = max(0, cy - pad)
        x2 = min(w, cx + pad + 1)
        y2 = min(h, cy + pad + 1)

        if x2 <= x1 or y2 <= y1:
            return

        roi = img[y1:y2, x1:x2]
        overlay = roi.copy()
        cv2.circle(overlay, (cx - x1, cy - y1), radius, color, thickness, lineType=cv2.LINE_AA)
        cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0, roi)
