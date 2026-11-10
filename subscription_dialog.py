"""
subscription_dialog.py - Modern Subscription Modal with Device ID and Video Unlock
"""

import os
import webbrowser
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor

from subscription_manager import subscription_mgr

PAYMENT_INFO = {
    "easypaisa": "0300-1234567 (ZoomRecorder Pro)",
    "jazzcash": "0300-1234567 (ZoomRecorder Pro)",
    "whatsapp": "+923001234567"
}


class SubscriptionDialog(QDialog):
    """Modern dark modal for subscription plans, device ID copy, and activation."""
    activated = pyqtSignal()

    def __init__(self, parent=None, is_locked_video: bool = False):
        super().__init__(parent)
        self.setWindowTitle("ZoomRecorder Pro - 1 Month Plan")
        self.setFixedSize(580, 710)
        self.setModal(True)
        self.is_locked_video = is_locked_video

        self._apply_stylesheet()
        self._init_ui()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #121217;
                color: #e5e5eb;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#cardPricing {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a24, stop:1 #241a2c);
                border: 2px solid #e5173f;
                border-radius: 12px;
                padding: 14px;
            }
            QFrame#cardDevice {
                background-color: #161620;
                border: 1px dashed #4b4b60;
                border-radius: 8px;
                padding: 10px 14px;
            }
            QFrame#cardPayment {
                background-color: #181820;
                border: 1px solid #2a2a38;
                border-radius: 10px;
                padding: 12px;
            }
            QLabel {
                color: #d1d1db;
            }
            QLabel#title {
                font-size: 20px;
                font-weight: 800;
                color: #ffffff;
            }
            QLabel#badgeLocked {
                background-color: #dc2626;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                border-radius: 10px;
                padding: 4px 10px;
            }
            QLabel#priceTag {
                font-size: 28px;
                font-weight: 900;
                color: #ff335c;
            }
            QLabel#priceSub {
                font-size: 12px;
                color: #9c9cb0;
            }
            QLabel#featureItem {
                font-size: 13px;
                color: #e0e0ea;
                padding: 2px 0px;
            }
            QLineEdit#keyInput {
                background-color: #0e0e12;
                border: 1px solid #3d3d52;
                border-radius: 6px;
                padding: 10px 14px;
                color: #ffffff;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QLineEdit#keyInput:focus {
                border-color: #e5173f;
            }
            QPushButton#btnActivate {
                background-color: #e5173f;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
            }
            QPushButton#btnActivate:hover {
                background-color: #ff2a54;
            }
            QPushButton#btnCopy {
                background-color: #262635;
                color: #38bdf8;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btnCopy:hover {
                background-color: #38bdf8;
                color: #000;
            }
            QPushButton#btnWhatsApp {
                background-color: #25D366;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton#btnWhatsApp:hover {
                background-color: #20ba59;
            }
            QPushButton#btnClose {
                background-color: #252530;
                color: #a0a0b0;
                border: 1px solid #363644;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton#btnClose:hover {
                background-color: #31313e;
                color: #ffffff;
            }
        """)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        # Header with Title and Status
        header_layout = QHBoxLayout()
        title_label = QLabel("⭐ ZoomRecorder Pro")
        title_label.setObjectName("title")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        if self.is_locked_video:
            locked_badge = QLabel("🔒 Video Save Locked")
            locked_badge.setObjectName("badgeLocked")
            header_layout.addWidget(locked_badge)
        layout.addLayout(header_layout)

        # Subtitle
        if self.is_locked_video:
            sub_text = (
                "<b>Aap ki pehli free recording mukammal ho chuki thi.</b><br>"
                "Is recording ko <b>unlock aur save</b> karne ke liye 1-Month Pro Plan activate karein:"
            )
        else:
            sub_text = "Tamam restrictions khatam karein aur unlimited recordings unlock karein:"

        sub_label = QLabel(sub_text)
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet("color: #b0b0c2; font-size: 12px; line-height: 1.4;")
        layout.addWidget(sub_label)

        # ----------------- DEVICE ID BOX -----------------
        dev_frame = QFrame()
        dev_frame.setObjectName("cardDevice")
        dev_layout = QHBoxLayout(dev_frame)
        dev_layout.setContentsMargins(10, 6, 10, 6)

        lbl_dev_title = QLabel("Aap ki Device ID:")
        lbl_dev_title.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600;")
        dev_layout.addWidget(lbl_dev_title)

        self.lbl_device_val = QLabel(subscription_mgr.device_id)
        self.lbl_device_val.setStyleSheet("font-family: Consolas, monospace; font-size: 13px; font-weight: bold; color: #38bdf8;")
        dev_layout.addWidget(self.lbl_device_val)

        dev_layout.addStretch()

        btn_copy_dev = QPushButton("📋 Copy Device ID")
        btn_copy_dev.setObjectName("btnCopy")
        btn_copy_dev.setCursor(Qt.PointingHandCursor)
        btn_copy_dev.clicked.connect(self._copy_device_id)
        dev_layout.addWidget(btn_copy_dev)

        layout.addWidget(dev_frame)

        # ----------------- PRICING CARD -----------------
        card = QFrame()
        card.setObjectName("cardPricing")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(6)

        plan_header = QHBoxLayout()
        plan_title = QLabel("👑 1-MONTH PRO SUBSCRIPTION")
        plan_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #fbbf24; letter-spacing: 0.5px;")
        plan_header.addWidget(plan_title)

        plan_header.addStretch()
        popular_badge = QLabel("SINGLE-USE SECURE")
        popular_badge.setStyleSheet("background-color: #e5173f; color: #fff; font-size: 9px; font-weight: bold; padding: 2px 7px; border-radius: 6px;")
        plan_header.addWidget(popular_badge)
        card_layout.addLayout(plan_header)

        price_box = QHBoxLayout()
        price_tag = QLabel("1,000 PKR")
        price_tag.setObjectName("priceTag")
        price_box.addWidget(price_tag)

        price_sub = QLabel(" / 1 Month (30 Days Unlimited)")
        price_sub.setObjectName("priceSub")
        price_box.addWidget(price_sub)
        price_box.addStretch()
        card_layout.addLayout(price_box)

        features = [
            "✔ Unlimited Screen Recording & Instant Video Saving",
            "✔ Ultra-Smooth Auto-Zoom & Click Ripple Focus",
            "✔ Yellow Mouse Highlight & Custom Pointer",
            "✔ Full HD 1080p & 60 FPS Export Quality",
            "✔ System Audio & Microphone Voice Recording",
            "✔ 100% Watermark-Free for YouTube & Client Work"
        ]
        for f in features:
            f_lbl = QLabel(f)
            f_lbl.setObjectName("featureItem")
            card_layout.addWidget(f_lbl)

        layout.addWidget(card)

        # ----------------- PAYMENT INSTRUCTIONS -----------------
        pay_card = QFrame()
        pay_card.setObjectName("cardPayment")
        pay_layout = QVBoxLayout(pay_card)
        pay_layout.setSpacing(5)

        pay_title = QLabel("💳 Payment & How to Buy:")
        pay_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #ffffff;")
        pay_layout.addWidget(pay_title)

        pay_desc = QLabel(
            "<b>1.</b> 1,000 PKR EasyPaisa ya JazzCash send karein.<br>"
            "<b>2.</b> Screenshot aur apni <b>Device ID</b> WhatsApp par send karein.<br>"
            "<b>3.</b> Aap ko apni device ki <b>Single-Use Key</b> mil jayegi."
        )
        pay_desc.setWordWrap(True)
        pay_desc.setStyleSheet("color: #a0a0b2; font-size: 11px; line-height: 1.3;")
        pay_layout.addWidget(pay_desc)

        wa_layout = QHBoxLayout()
        btn_wa = QPushButton("💬 Buy Key via WhatsApp")
        btn_wa.setObjectName("btnWhatsApp")
        btn_wa.setCursor(Qt.PointingHandCursor)
        btn_wa.clicked.connect(self._open_whatsapp)
        wa_layout.addWidget(btn_wa)
        wa_layout.addStretch()
        pay_layout.addLayout(wa_layout)

        layout.addWidget(pay_card)

        # ----------------- ACTIVATION SECTION -----------------
        act_box = QVBoxLayout()
        act_box.setSpacing(5)

        lbl_input = QLabel("Enter Single-Use Activation Key:")
        lbl_input.setStyleSheet("font-weight: 600; font-size: 11px; color: #ffffff;")
        act_box.addWidget(lbl_input)

        input_row = QHBoxLayout()
        self.input_key = QLineEdit()
        self.input_key.setObjectName("keyInput")
        self.input_key.setPlaceholderText("ZR1M-XXXX-XXXX-XXXX-XXXX-XXXX")
        self.input_key.returnPressed.connect(self._on_activate_clicked)
        input_row.addWidget(self.input_key)

        btn_text = "⚡ Unlock & Save Video" if self.is_locked_video else "⚡ Activate Pro"
        self.btn_activate = QPushButton(btn_text)
        self.btn_activate.setObjectName("btnActivate")
        self.btn_activate.setCursor(Qt.PointingHandCursor)
        self.btn_activate.clicked.connect(self._on_activate_clicked)
        input_row.addWidget(self.btn_activate)
        act_box.addLayout(input_row)

        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setStyleSheet("font-size: 11px; font-weight: bold;")
        act_box.addWidget(self.lbl_feedback)

        layout.addLayout(act_box)

        # Bottom Close Row
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_close = QPushButton("Discard & Close" if self.is_locked_video else "Close")
        btn_close.setObjectName("btnClose")
        btn_close.clicked.connect(self._on_close_clicked)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def _copy_device_id(self):
        cb = QApplication.clipboard()
        cb.setText(subscription_mgr.device_id)
        self.lbl_feedback.setText(f"📋 Device ID ({subscription_mgr.device_id}) copied to clipboard!")
        self.lbl_feedback.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")

    def _open_whatsapp(self):
        phone = PAYMENT_INFO.get("whatsapp", "").replace("+", "").replace("-", "").replace(" ", "")
        dev_id = subscription_mgr.device_id
        msg = f"Salam! Mujhe ZoomRecorder Pro ki 1-Month Subscription (1,000 PKR) buy karni hai. Meri Device ID yeh hai: {dev_id}"
        url = f"https://wa.me/{phone}?text={msg}"
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _on_activate_clicked(self):
        key = self.input_key.text().strip()
        if not key:
            self.lbl_feedback.setText("⚠️ Please enter your single-use activation key.")
            self.lbl_feedback.setStyleSheet("color: #ff9900; font-size: 11px; font-weight: bold;")
            return

        success, message = subscription_mgr.activate_license(key)
        if success:
            self.lbl_feedback.setText(f"✅ {message}")
            self.lbl_feedback.setStyleSheet("color: #22c55e; font-size: 11px; font-weight: bold;")
            QMessageBox.information(self, "Pro Activated!", message)
            self.activated.emit()
            self.accept()
        else:
            self.lbl_feedback.setText(f"❌ {message}")
            self.lbl_feedback.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold;")

    def _on_close_clicked(self):
        if self.is_locked_video:
            reply = QMessageBox.question(
                self,
                "Discard Recording?",
                "Agar aap ne Pro activate nahi kiya to yeh video save nahi hogi aur delete ho jayegi.<br><br>Kya aap waqai is video ko discard karna chahte hain?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        self.reject()
