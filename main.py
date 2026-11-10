"""
main.py - ZoomRecorder Pro Main User Interface
Modern dark UI (OBS Studio inspired) built with PyQt5.
Features live preview, recording controls, zoom parameters, area selection,
tray integration, and global hotkeys.
"""

import os
import sys
import time
import ctypes
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QComboBox, QSlider, QCheckBox,
    QFileDialog, QMessageBox, QFrame, QSystemTrayIcon, QMenu, QAction,
    QGraphicsDropShadowEffect, QSizePolicy, QDialog
)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSlot, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QIcon, QFont, QColor, QPainter

from utils import (
    get_default_recordings_dir,
    format_time,
    format_size,
    AreaSelectOverlay,
    WindowSelectDialog,
    list_open_windows
)
from mouse_tracker import MouseTracker
from recorder import ScreenRecorder
from subscription_manager import subscription_mgr
from subscription_dialog import SubscriptionDialog


def get_app_icon_path() -> Path:
    """Resolve icon path for both raw python and PyInstaller frozen executable."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parent

    ico = base_dir / "icon.ico"
    if ico.exists():
        return ico
    png = base_dir / "icon.png"
    if png.exists():
        return png
    return ico


class PreviewThread(QThread):
    """Low-overhead background preview generator when recorder is idle."""
    preview_ready = pyqtSignal(np.ndarray)

    def __init__(self, get_rect_fn, parent=None):
        super().__init__(parent)
        self.get_rect_fn = get_rect_fn
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            try:
                rect = self.get_rect_fn()
                # Fast grab using Qt primary screen
                screen = QApplication.primaryScreen()
                if screen:
                    rx, ry, rw, rh = rect
                    pix = screen.grabWindow(0, rx, ry, rw, rh)
                    qimg = pix.toImage().convertToFormat(QImage.Format_RGB888)
                    w, h = qimg.width(), qimg.height()
                    ptr = qimg.bits()
                    ptr.setsize(qimg.byteCount())
                    arr = np.array(ptr, dtype=np.uint8).reshape((h, w, 3))
                    # Downscale preview for ultra-smooth UI performance
                    target_w = 960
                    target_h = int(h * (target_w / float(w)))
                    small = cv2.resize(arr, (target_w, target_h), interpolation=cv2.INTER_AREA)
                    self.preview_ready.emit(small)
            except Exception:
                pass
            time.sleep(0.06)  # ~16 FPS idle preview

    def stop(self):
        self._running = False
        self.wait(500)


class ZoomRecorderApp(QMainWindow):
    """Main Application Window for ZoomRecorder Pro."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZoomRecorder Pro")
        self.resize(1080, 780)
        self.setMinimumSize(920, 680)

        # Output save directory
        self.save_dir = get_default_recordings_dir()

        # Selected recording area: None means Full Screen
        self.selected_rect: Optional[Tuple[int, int, int, int]] = None
        self.custom_rect_desc = "Full Screen"

        # Recorder & Tracker instances
        self.recorder: Optional[ScreenRecorder] = None
        self.mouse_tracker = MouseTracker(self)
        self.mouse_tracker.hotkey_start_stop.connect(self._toggle_recording)
        self.mouse_tracker.hotkey_pause.connect(self._toggle_pause)
        self.mouse_tracker.start()

        # Idle preview thread
        self.idle_preview = PreviewThread(self._get_current_capture_rect, self)
        self.idle_preview.preview_ready.connect(self._update_preview_pixmap)

        # Subscription & Trial tracking
        self._trial_limit_hit = False
        self._recording_elapsed_sec = 0.0

        # Init UI
        self._apply_stylesheet()
        self._init_ui()
        self._refresh_subscription_ui()
        self._init_tray()

        # Start idle preview
        self.idle_preview.start()

    def _get_current_capture_rect(self) -> Tuple[int, int, int, int]:
        if self.selected_rect:
            return self.selected_rect
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            return (geom.x(), geom.y(), geom.width(), geom.height())
        return (0, 0, 1920, 1080)

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121215;
            }
            QWidget {
                color: #e5e5eb;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QFrame#headerPanel {
                background-color: #18181d;
                border-bottom: 1px solid #282830;
                padding: 10px 18px;
            }
            QFrame#previewCard {
                background-color: #0b0b0e;
                border: 1px solid #22222a;
                border-radius: 8px;
            }
            QFrame#controlPanel {
                background-color: #18181d;
                border-top: 1px solid #282830;
                border-radius: 8px;
                padding: 12px 18px;
            }
            QLabel {
                color: #d1d1db;
            }
            QLabel#appTitle {
                font-size: 20px;
                font-weight: 800;
                color: #ffffff;
                letter-spacing: 0.5px;
            }
            QLabel#badgeIdle {
                background-color: #272732;
                color: #a0a0b0;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#badgeRec {
                background-color: #ff1e42;
                color: #ffffff;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#badgePause {
                background-color: #f59e0b;
                color: #121215;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#timerLabel {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 22px;
                font-weight: bold;
                color: #ffffff;
            }
            QLabel#statLabel {
                color: #8c8c9a;
                font-size: 12px;
            }
            /* Push Buttons */
            QPushButton {
                background-color: #25252e;
                border: 1px solid #363644;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                color: #f0f0f5;
            }
            QPushButton:hover {
                background-color: #31313e;
                border-color: #4a4a5c;
            }
            QPushButton:pressed {
                background-color: #1c1c24;
            }
            QPushButton#btnRecord {
                background-color: #e5173f;
                border: none;
                border-radius: 8px;
                padding: 10px 22px;
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
            }
            QPushButton#btnRecord:hover {
                background-color: #ff2a54;
            }
            QPushButton#btnRecord:pressed {
                background-color: #bf1032;
            }
            QPushButton#btnStop {
                background-color: #3b3b4a;
                border: 1px solid #525266;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
            }
            QPushButton#btnStop:hover {
                background-color: #ff334b;
                border-color: #ff334b;
            }
            QPushButton#btnPause {
                background-color: #2e281b;
                border: 1px solid #785a1a;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                color: #fbbf24;
            }
            QPushButton#btnPause:hover {
                background-color: #f59e0b;
                color: #121215;
            }
            /* ComboBox */
            QComboBox {
                background-color: #202028;
                border: 1px solid #333342;
                border-radius: 5px;
                padding: 5px 10px;
                color: #ffffff;
                font-weight: 500;
                min-width: 90px;
            }
            QComboBox:hover {
                border-color: #4f4f66;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #333342;
            }
            QComboBox QAbstractItemView {
                background-color: #1c1c24;
                border: 1px solid #333342;
                selection-background-color: #e5173f;
                selection-color: #ffffff;
                padding: 4px;
            }
            /* Slider */
            QSlider::groove:horizontal {
                height: 5px;
                background: #2b2b38;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #e5173f;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #e5173f;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #ff5c7a;
            }
            /* Checkbox */
            QCheckBox {
                spacing: 8px;
                color: #d1d1db;
                font-weight: 500;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #444455;
                background-color: #202028;
            }
            QCheckBox::indicator:hover {
                border-color: #666680;
            }
            QCheckBox::indicator:checked {
                background-color: #e5173f;
                border-color: #e5173f;
            }
        """)

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----------------- TOP HEADER -----------------
        header = QFrame()
        header.setObjectName("headerPanel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)

        # App Title & Icon badge
        title_box = QHBoxLayout()
        title_box.setSpacing(10)
        title_label = QLabel("ZoomRecorder Pro")
        title_label.setObjectName("appTitle")
        title_box.addWidget(title_label)

        self.status_pill = QLabel("● IDLE")
        self.status_pill.setObjectName("badgeIdle")
        title_box.addWidget(self.status_pill)

        # Subscription Plan Badge & Upgrade Button
        self.plan_badge = QLabel("⚡ FREE TRIAL (10s)")
        self.plan_badge.setObjectName("badgePlan")
        title_box.addWidget(self.plan_badge)

        self.btn_upgrade = QPushButton("💎 Upgrade (1,000 PKR)")
        self.btn_upgrade.setCursor(Qt.PointingHandCursor)
        self.btn_upgrade.clicked.connect(self._open_subscription_dialog)
        title_box.addWidget(self.btn_upgrade)

        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Timer & File Size strip
        stats_box = QHBoxLayout()
        stats_box.setSpacing(16)
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerLabel")
        stats_box.addWidget(self.timer_label)

        self.size_label = QLabel("0.0 MB")
        self.size_label.setObjectName("statLabel")
        stats_box.addWidget(self.size_label)

        # Shortcut hints pill
        hint_label = QLabel("F9: Record | F10: Pause")
        hint_label.setStyleSheet("color: #727282; font-size: 11px; background: #1f1f26; padding: 4px 8px; border-radius: 4px;")
        stats_box.addWidget(hint_label)

        header_layout.addLayout(stats_box)
        main_layout.addWidget(header)

        # ----------------- CENTER PREVIEW -----------------
        preview_container = QWidget()
        preview_container.setStyleSheet("background-color: #101013; padding: 12px;")
        pc_layout = QVBoxLayout(preview_container)
        pc_layout.setContentsMargins(12, 12, 12, 12)

        self.preview_card = QFrame()
        self.preview_card.setObjectName("previewCard")
        preview_card_layout = QVBoxLayout(self.preview_card)
        preview_card_layout.setContentsMargins(4, 4, 4, 4)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_label.setText("Initializing live preview...")
        self.preview_label.setStyleSheet("color: #555566; font-size: 15px; font-weight: bold;")
        preview_card_layout.addWidget(self.preview_label)

        pc_layout.addWidget(self.preview_card)
        main_layout.addWidget(preview_container, stretch=1)

        # ----------------- BOTTOM CONTROLS -----------------
        controls = QFrame()
        controls.setObjectName("controlPanel")
        ctrl_layout = QVBoxLayout(controls)
        ctrl_layout.setContentsMargins(18, 14, 18, 14)
        ctrl_layout.setSpacing(12)

        # Row 1: Primary Action Buttons & Main Options
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        # Start / Stop Record button
        self.btn_record = QPushButton("● START RECORDING")
        self.btn_record.setObjectName("btnRecord")
        self.btn_record.setCursor(Qt.PointingHandCursor)
        self.btn_record.clicked.connect(self._toggle_recording)
        row1.addWidget(self.btn_record)

        # Pause button
        self.btn_pause = QPushButton("❚❚ PAUSE")
        self.btn_pause.setObjectName("btnPause")
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._toggle_pause)
        row1.addWidget(self.btn_pause)

        # Stop button
        self.btn_stop = QPushButton("■ STOP")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_recording)
        row1.addWidget(self.btn_stop)

        row1.addSpacing(16)

        # Record Area Dropdown
        lbl_area = QLabel("Area:")
        lbl_area.setStyleSheet("font-weight: bold; color: #a0a0b2;")
        row1.addWidget(lbl_area)
        self.combo_area = QComboBox()
        self.combo_area.addItems(["Full Screen", "Select Area...", "Specific Window..."])
        self.combo_area.currentIndexChanged.connect(self._on_area_changed)
        row1.addWidget(self.combo_area)

        # Quality Dropdown
        lbl_quality = QLabel("Quality:")
        lbl_quality.setStyleSheet("font-weight: bold; color: #a0a0b2;")
        row1.addWidget(lbl_quality)
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["1080p", "720p", "Original"])
        row1.addWidget(self.combo_quality)

        # FPS Dropdown
        lbl_fps = QLabel("FPS:")
        lbl_fps.setStyleSheet("font-weight: bold; color: #a0a0b2;")
        row1.addWidget(lbl_fps)
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["30", "60"])
        row1.addWidget(self.combo_fps)

        row1.addStretch()

        # Save Folder Selector
        self.btn_folder = QPushButton("📁 Save Folder")
        self.btn_folder.setToolTip(str(self.save_dir))
        self.btn_folder.clicked.connect(self._choose_save_folder)
        row1.addWidget(self.btn_folder)

        ctrl_layout.addLayout(row1)

        # Row 2: Zoom & Visual Effect Controls
        row2 = QHBoxLayout()
        row2.setSpacing(18)

        # Zoom Level Dropdown
        lbl_zoom = QLabel("Zoom Level:")
        lbl_zoom.setStyleSheet("font-weight: bold; color: #a0a0b2;")
        row2.addWidget(lbl_zoom)
        self.combo_zoom = QComboBox()
        self.combo_zoom.addItems(["1.5x", "2.0x", "3.0x"])
        self.combo_zoom.setCurrentIndex(1)  # Default 2.0x
        row2.addWidget(self.combo_zoom)

        # Zoom Duration Slider
        lbl_duration = QLabel("Zoom Duration:")
        lbl_duration.setStyleSheet("font-weight: bold; color: #a0a0b2;")
        row2.addWidget(lbl_duration)

        self.slider_duration = QSlider(Qt.Horizontal)
        self.slider_duration.setRange(10, 30)  # 1.0s to 3.0s in tenths
        self.slider_duration.setValue(15)      # Default 1.5s
        self.slider_duration.setFixedWidth(120)
        self.slider_duration.valueChanged.connect(self._on_duration_slider_changed)
        row2.addWidget(self.slider_duration)

        self.lbl_duration_val = QLabel("1.5s")
        self.lbl_duration_val.setStyleSheet("color: #e5173f; font-weight: bold; min-width: 32px;")
        row2.addWidget(self.lbl_duration_val)

        row2.addSpacing(10)

        # Mouse Highlight Toggle
        self.chk_highlight = QCheckBox("Mouse Highlight")
        self.chk_highlight.setChecked(True)
        row2.addWidget(self.chk_highlight)

        # Click Sound Toggle
        self.chk_sound = QCheckBox("Click Sound")
        self.chk_sound.setChecked(True)
        row2.addWidget(self.chk_sound)

        # Audio Recording Toggle
        self.chk_audio = QCheckBox("Record Audio (Mic)")
        self.chk_audio.setChecked(True)
        row2.addWidget(self.chk_audio)

        row2.addStretch()

        # Minimize to tray checkbox
        self.chk_minimize_tray = QCheckBox("Minimize to Tray when Recording")
        self.chk_minimize_tray.setChecked(False)
        row2.addWidget(self.chk_minimize_tray)

        ctrl_layout.addLayout(row2)
        main_layout.addWidget(controls)

    def _init_tray(self):
        """Configure System Tray Icon & Context Menu."""
        self.tray_icon = QSystemTrayIcon(self)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            app_icon = QIcon(str(icon_path))
            self.tray_icon.setIcon(app_icon)
            self.setWindowIcon(app_icon)
        else:
            # Fallback tray icon pixmap
            pix = QPixmap(32, 32)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor(229, 23, 63))
            p.setPen(Qt.NoPen)
            p.drawEllipse(4, 4, 24, 24)
            p.setBrush(QColor(255, 255, 255))
            p.drawEllipse(11, 11, 10, 10)
            p.end()

            self.tray_icon.setIcon(QIcon(pix))
            self.setWindowIcon(QIcon(pix))

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e24;
                color: #ffffff;
                border: 1px solid #33333d;
            }
            QMenu::item:selected {
                background-color: #e5173f;
            }
        """)

        act_show = QAction("Show ZoomRecorder", self)
        act_show.triggered.connect(self._show_window)
        tray_menu.addAction(act_show)

        self.act_tray_record = QAction("Start Recording (F9)", self)
        self.act_tray_record.triggered.connect(self._toggle_recording)
        tray_menu.addAction(self.act_tray_record)

        self.act_tray_pause = QAction("Pause Recording (F10)", self)
        self.act_tray_pause.triggered.connect(self._toggle_pause)
        self.act_tray_pause.setEnabled(False)
        tray_menu.addAction(self.act_tray_pause)

        tray_menu.addSeparator()

        act_folder = QAction("Open Recordings Folder", self)
        act_folder.triggered.connect(self._open_recordings_folder)
        tray_menu.addAction(act_folder)

        act_sub = QAction("💎 Upgrade to Pro (1,000 PKR)", self)
        act_sub.triggered.connect(self._open_subscription_dialog)
        tray_menu.addAction(act_sub)

        act_quit = QAction("Exit", self)
        act_quit.triggered.connect(self.close)
        tray_menu.addAction(act_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _open_subscription_dialog(self, is_locked: bool = False):
        """Open subscription plan & single-use key activation modal."""
        dlg = SubscriptionDialog(self, is_locked_video=is_locked)
        dlg.activated.connect(self._refresh_subscription_ui)
        dlg.exec_()
        self._refresh_subscription_ui()

    def _refresh_subscription_ui(self):
        """Update Pro badges and button states based on subscription status."""
        if subscription_mgr.is_subscribed():
            days = subscription_mgr.get_remaining_days()
            self.plan_badge.setText(f"👑 PRO ({days}d)")
            self.plan_badge.setStyleSheet(
                "background-color: #10b981; color: #ffffff; border-radius: 12px; "
                "padding: 4px 12px; font-size: 11px; font-weight: bold;"
            )
            self.btn_upgrade.setText("👑 Pro Member")
            self.btn_upgrade.setStyleSheet(
                "background-color: #1a2234; color: #34d399; border: 1px solid #10b981; "
                "border-radius: 6px; padding: 5px 12px; font-weight: bold; font-size: 11px;"
            )
        else:
            if subscription_mgr.is_first_video_free():
                self.plan_badge.setText("⚡ 1st VIDEO FREE (Any Length)")
                self.plan_badge.setStyleSheet(
                    "background-color: #10b981; color: #ffffff; border-radius: 12px; "
                    "padding: 4px 12px; font-size: 11px; font-weight: bold;"
                )
            else:
                self.plan_badge.setText("🔒 1st FREE VIDEO USED")
                self.plan_badge.setStyleSheet(
                    "background-color: #dc2626; color: #ffffff; border-radius: 12px; "
                    "padding: 4px 12px; font-size: 11px; font-weight: bold;"
                )
            self.btn_upgrade.setText("💎 Upgrade (1,000 PKR)")
            self.btn_upgrade.setStyleSheet(
                "background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e5173f, stop:1 #7c3aed); "
                "color: #ffffff; font-weight: bold; border-radius: 6px; padding: 6px 14px; font-size: 12px;"
            )

    def _on_duration_slider_changed(self, val):
        sec = val / 10.0
        self.lbl_duration_val.setText(f"{sec:.1f}s")

    def _on_area_changed(self, idx):
        if idx == 0:
            # Full Screen
            self.selected_rect = None
            self.custom_rect_desc = "Full Screen"
        elif idx == 1:
            # Select Area
            self._open_area_selector()
        elif idx == 2:
            # Specific Window
            self._open_window_selector()

    def _open_area_selector(self):
        """Open drag-and-drop transparent overlay to select custom area."""
        self.hide()
        overlay = AreaSelectOverlay()
        overlay.area_selected.connect(self._on_custom_area_selected)
        res = overlay.exec_()
        self.show()
        if res != AreaSelectOverlay.Accepted:
            # Revert to Full Screen
            self.combo_area.setCurrentIndex(0)

    def _on_custom_area_selected(self, x, y, w, h):
        self.selected_rect = (x, y, w, h)
        self.custom_rect_desc = f"Area ({w}×{h})"
        # Update combobox text without infinite loop
        self.combo_area.blockSignals(True)
        self.combo_area.setItemText(1, f"Selected: {w}×{h}")
        self.combo_area.setCurrentIndex(1)
        self.combo_area.blockSignals(False)

    def _open_window_selector(self):
        """Open dialog listing active windows."""
        windows = list_open_windows()
        if not windows:
            QMessageBox.information(self, "No Windows", "No visible open application windows detected.")
            self.combo_area.setCurrentIndex(0)
            return

        dlg = WindowSelectDialog(windows, self)
        if dlg.exec_() == WindowSelectDialog.Accepted and dlg.selected_window:
            win = dlg.selected_window
            self.selected_rect = win["rect"]
            self.custom_rect_desc = win["title"][:20]
            self.combo_area.blockSignals(True)
            self.combo_area.setItemText(2, f"Window: {self.custom_rect_desc}")
            self.combo_area.setCurrentIndex(2)
            self.combo_area.blockSignals(False)
        else:
            self.combo_area.setCurrentIndex(0)

    def _choose_save_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Recordings Save Folder",
            str(self.save_dir)
        )
        if folder:
            self.save_dir = Path(folder)
            self.btn_folder.setToolTip(str(self.save_dir))

    def _open_recordings_folder(self):
        if self.save_dir.exists():
            os.startfile(str(self.save_dir))

    @pyqtSlot(np.ndarray)
    def _update_preview_pixmap(self, frame_bgr: np.ndarray):
        """Renders live frame on Center Preview QLabel with high performance."""
        if frame_bgr is None or frame_bgr.size == 0:
            return

        # Skip rendering when window is minimized or hidden (zero CPU overhead)
        if self.isHidden() or self.isMinimized() or not self.isVisible():
            return

        h, w, ch = frame_bgr.shape
        bytes_per_line = ch * w
        # Frame is BGR from OpenCV, convert to RGB for QImage
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

        avail_w = max(100, self.preview_card.width() - 16)
        avail_h = max(100, self.preview_card.height() - 16)

        pix = QPixmap.fromImage(qimg).scaled(
            avail_w, avail_h,
            Qt.KeepAspectRatio,
            Qt.FastTransformation
        )
        self.preview_label.setPixmap(pix)

    @pyqtSlot()
    def _toggle_recording(self):
        if self.recorder and self.recorder.isRunning():
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        # Stop idle preview thread cleanly
        self.idle_preview.stop()

        # Parse zoom level
        zoom_text = self.combo_zoom.currentText().replace("x", "")
        zoom_level = float(zoom_text)
        zoom_duration = self.slider_duration.value() / 10.0

        # Quality & FPS
        quality = self.combo_quality.currentText()
        fps = int(self.combo_fps.currentText())

        # Instantiate ScreenRecorder
        self.recorder = ScreenRecorder(
            output_dir=self.save_dir,
            capture_rect=self.selected_rect,
            quality=quality,
            fps=fps,
            zoom_level=zoom_level,
            zoom_duration=zoom_duration,
            mouse_highlight=self.chk_highlight.isChecked(),
            click_sound=self.chk_sound.isChecked(),
            record_audio=self.chk_audio.isChecked(),
            parent=self
        )

        # Connect zero-latency direct click callback
        self.mouse_tracker.set_click_callback(self.recorder.on_click_event)

        # Connect signals
        self.recorder.frame_ready.connect(self._update_preview_pixmap)
        self.recorder.stats_updated.connect(self._on_stats_updated)
        self.recorder.recording_finished.connect(self._on_recording_finished)
        self.recorder.error_occurred.connect(self._on_recording_error)

        self.recorder.start()

        # Update UI Controls
        self.btn_record.setText("■ STOP RECORDING")
        self.btn_record.setObjectName("btnRecord")
        self.btn_stop.setEnabled(True)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("❚❚ PAUSE")
        self.status_pill.setText("● REC")
        self.status_pill.setObjectName("badgeRec")
        self.status_pill.setStyle(self.status_pill.style())

        self.combo_area.setEnabled(False)
        self.combo_quality.setEnabled(False)
        self.combo_fps.setEnabled(False)

        self.act_tray_record.setText("Stop Recording (F9)")
        self.act_tray_pause.setEnabled(True)

        if self.chk_minimize_tray.isChecked():
            self.hide()
            self.tray_icon.showMessage(
                "ZoomRecorder Pro",
                "Recording started in background. Press F9 to stop.",
                QSystemTrayIcon.Information,
                2500
            )

    @pyqtSlot()
    def _toggle_pause(self):
        if not self.recorder or not self.recorder.isRunning():
            return

        if self.recorder._is_paused:
            self.recorder.resume()
            self.btn_pause.setText("❚❚ PAUSE")
            self.status_pill.setText("● REC")
            self.status_pill.setObjectName("badgeRec")
            self.act_tray_pause.setText("Pause Recording (F10)")
        else:
            self.recorder.pause()
            self.btn_pause.setText("▶ RESUME")
            self.status_pill.setText("❚❚ PAUSED")
            self.status_pill.setObjectName("badgePause")
            self.act_tray_pause.setText("Resume Recording (F10)")

        self.status_pill.setStyle(self.status_pill.style())

    @pyqtSlot()
    def _stop_recording(self):
        if self.recorder and self.recorder.isRunning():
            self.btn_record.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_pause.setEnabled(False)
            self.status_pill.setText("SAVING...")
            self.recorder.stop()

    @pyqtSlot(float, int, int)
    def _on_stats_updated(self, elapsed_sec: float, frames: int, file_size: int):
        self.timer_label.setText(format_time(elapsed_sec))
        self.size_label.setText(format_size(file_size))

    @pyqtSlot(str)
    def _on_recording_finished(self, saved_path: str):
        # Reset UI
        self.btn_record.setEnabled(True)
        self.btn_record.setText("● START RECORDING")
        self.btn_stop.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("❚❚ PAUSE")
        self.status_pill.setText("● IDLE")
        self.status_pill.setObjectName("badgeIdle")
        self.status_pill.setStyle(self.status_pill.style())

        self.combo_area.setEnabled(True)
        self.combo_quality.setEnabled(True)
        self.combo_fps.setEnabled(True)

        self.act_tray_record.setText("Start Recording (F9)")
        self.act_tray_pause.setEnabled(False)

        # Restore window if hidden
        if self.isHidden():
            self.showNormal()
            self.activateWindow()

        # Restart idle preview
        self.idle_preview.start()

        if not saved_path:
            return

        video_path = Path(saved_path)

        # ----------------- SUBSCRIPTION CHECK ON VIDEO FINISH -----------------
        if subscription_mgr.is_subscribed():
            # Pro user: normal save and view
            self._show_saved_dialog(str(video_path))
        elif subscription_mgr.is_first_video_free():
            # 1st Video on this device: 100% FREE!
            subscription_mgr.record_free_video_completed()
            self._refresh_subscription_ui()
            self._show_saved_dialog(str(video_path))
        else:
            # 2nd Video onwards on this device:
            # Video recorded, but DO NOT save unless Pro Plan is activated!
            dlg = SubscriptionDialog(self, is_locked_video=True)
            res = dlg.exec_()
            self._refresh_subscription_ui()

            if res == QDialog.Accepted and subscription_mgr.is_subscribed():
                # User activated license! Video is unlocked and saved!
                self._show_saved_dialog(str(video_path))
            else:
                # User did not activate license -> video is NOT saved!
                try:
                    if video_path.exists():
                        video_path.unlink()
                except Exception:
                    pass
                QMessageBox.warning(
                    self,
                    "Recording Not Saved",
                    "Aap ka 1st free video trial mukammal ho chuka tha.<br><br>"
                    "Kyun k 1-Month Pro Plan activate nahi kiya gaya, is liye yeh video save nahi ki gayi."
                )

    def _show_saved_dialog(self, saved_path: str):
        p = Path(saved_path)
        size_str = format_size(p.stat().st_size) if p.exists() else "0 B"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Recording Saved")
        msg_box.setText(f"<b>Recording successfully saved!</b><br><br><b>File:</b> {p.name}<br><b>Size:</b> {size_str}<br><b>Path:</b> {p.parent}")
        msg_box.setIcon(QMessageBox.Information)

        btn_open_file = msg_box.addButton("▶ Play Video", QMessageBox.ActionRole)
        btn_open_folder = msg_box.addButton("📁 Open Folder", QMessageBox.ActionRole)
        btn_close = msg_box.addButton("Close", QMessageBox.RejectRole)

        msg_box.exec_()

        if msg_box.clickedButton() == btn_open_file:
            if p.exists():
                os.startfile(str(p))
        elif msg_box.clickedButton() == btn_open_folder:
            if p.parent.exists():
                os.startfile(str(p.parent))

    @pyqtSlot(str)
    def _on_recording_error(self, err_msg: str):
        QMessageBox.critical(self, "Recording Error", err_msg)
        self._on_recording_finished("")

    def closeEvent(self, event):
        """Cleanup threads and hooks on close."""
        if self.recorder and self.recorder.isRunning():
            reply = QMessageBox.question(
                self,
                "Recording in Progress",
                "A recording is currently running. Stop and save before exiting?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self.recorder.stop()
                self.recorder.wait(3000)
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return

        self.idle_preview.stop()
        self.mouse_tracker.stop()
        self.tray_icon.hide()
        event.accept()


def main():
    # Set Windows Process AppUserModelID so Windows Taskbar groups under our app icon instead of python.exe
    try:
        myappid = "zoomrecorder.pro.screenrecorder.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    # High DPI scaling support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("ZoomRecorder Pro")

    # Set Application Icon
    icon_path = get_app_icon_path()
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    window = ZoomRecorderApp()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
