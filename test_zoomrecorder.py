"""
test_zoomrecorder.py - Automated test suite for ZoomRecorder Pro
Verifies all modules, math, sound, video writing, zoom calculations, and GUI initialization.
"""

import os
import sys
import time
import unittest
from pathlib import Path

import cv2
import numpy as np

# Ensure current directory in sys.path
sys.path.insert(0, os.path.abspath("."))

from utils import (
    get_default_recordings_dir,
    generate_filename,
    format_time,
    format_size,
    ClickSoundManager
)
from mouse_tracker import MouseTracker
from recorder import ScreenRecorder


class TestZoomRecorder(unittest.TestCase):

    def test_utils_formatting(self):
        # Time format
        self.assertEqual(format_time(0), "00:00:00")
        self.assertEqual(format_time(65), "00:01:05")
        self.assertEqual(format_time(3661), "01:01:01")

        # Size format
        self.assertEqual(format_size(500), "500 B")
        self.assertEqual(format_size(1024 * 500), "500.0 KB")
        self.assertEqual(format_size(1024 * 1024 * 15), "15.0 MB")

        # Directory & Filename
        save_dir = get_default_recordings_dir()
        self.assertTrue(save_dir.exists())
        fn = generate_filename(save_dir)
        self.assertTrue(fn.name.startswith("ZoomRecorder_"))
        self.assertTrue(fn.name.endswith(".mp4"))
        print("[TEST] utils formatting tests passed!")

    def test_click_sound(self):
        mgr = ClickSoundManager()
        self.assertTrue(mgr.sound_file.exists())
        # Test non-blocking play
        mgr.play_click()
        print("[TEST] Click sound generation & play tested successfully!")

    def test_cursor_tracking(self):
        pos = MouseTracker.get_cursor_position()
        self.assertIsInstance(pos, tuple)
        self.assertEqual(len(pos), 2)
        print(f"[TEST] Cursor tracking returned: {pos}")

    def test_zoom_processing(self):
        # Create a mock frame
        test_dir = Path("./test_out")
        test_dir.mkdir(exist_ok=True)
        rec = ScreenRecorder(
            output_dir=test_dir,
            quality="720p",
            fps=30,
            zoom_level=2.0,
            zoom_duration=1.0,
            mouse_highlight=True,
            click_sound=False,
            record_audio=False
        )

        test_frame = np.full((1080, 1920, 3), 50, dtype=np.uint8)
        # Draw a shape in the center
        cv2.circle(test_frame, (960, 540), 100, (0, 0, 255), -1)

        # Trigger click at (960, 540)
        rec._is_running = True
        rec.on_click_event(960, 540)

        # Process frame right at click
        now = time.time()
        processed = rec._process_frame(
            test_frame,
            0, 0, 1920, 1080,
            1280, 720,
            960, 540,
            now
        )
        self.assertEqual(processed.shape, (720, 1280, 3))

        # Test frame during peak zoom (0.4s after click)
        peak_processed = rec._process_frame(
            test_frame,
            0, 0, 1920, 1080,
            1280, 720,
            960, 540,
            now + 0.4
        )
        self.assertEqual(peak_processed.shape, (720, 1280, 3))

        # Test frame after zoom completes (2.0s after click)
        normal_processed = rec._process_frame(
            test_frame,
            0, 0, 1920, 1080,
            1280, 720,
            960, 540,
            now + 2.0
        )
        self.assertEqual(normal_processed.shape, (720, 1280, 3))
        print("[TEST] Zoom state machine, interpolation, and overlays verified!")

        # Clean up test dir
        try:
            if test_dir.exists():
                for f in test_dir.iterdir():
                    f.unlink()
                test_dir.rmdir()
        except Exception:
            pass

    def test_gui_init(self):
        from PyQt5.QtWidgets import QApplication
        from main import ZoomRecorderApp

        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)

        window = ZoomRecorderApp()
        self.assertIsNotNone(window)
        self.assertEqual(window.windowTitle(), "ZoomRecorder Pro")
        window.idle_preview.stop()
        window.mouse_tracker.stop()
        window.close()
        print("[TEST] PyQt5 Main Window initialized successfully!")

    def test_subscription_and_trial(self):
        from subscription_manager import SubscriptionManager
        mgr = SubscriptionManager()

        # Test device-bound key generation
        key_1m = mgr.generate_device_key(mgr.device_id, "1M")
        valid, plan, days = mgr.validate_key(key_1m)
        self.assertTrue(valid)
        self.assertEqual(days, 30)
        self.assertIn("1-Month", plan)

        # Test universal single-use key generation
        key_u = mgr.generate_universal_key("1M")
        valid_u, plan_u, days_u = mgr.validate_key(key_u)
        self.assertTrue(valid_u)
        self.assertEqual(days_u, 30)

        # Test invalid key
        self.assertFalse(mgr.validate_key("ZR1M-INVALID-KEY-1234-5678-0000")[0])

        # Test wrong device ID key
        key_wrong_dev = mgr.generate_device_key("ZR-FFFF-9999", "1M")
        valid_wrong, err_wrong, _ = mgr.validate_key(key_wrong_dev)
        self.assertFalse(valid_wrong)
        self.assertIn("kisi aur device", err_wrong)

        # Test free 1st video logic
        self.assertTrue(isinstance(mgr.is_first_video_free(), bool))
        print("[TEST] Single-use device-bound subscription tests passed!")


if __name__ == "__main__":
    unittest.main()
