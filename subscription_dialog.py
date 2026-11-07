"""
subscription_dialog.py - Modern Subscription & License Activation Modal
Displays pricing card (1,000 PKR / 1 Month), payment options (EasyPaisa/JazzCash/WhatsApp),
and real-time license key activation.
"""

import os
import webbrowser
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor

from subscription_manager import subscription_mgr, FREE_TRIAL_SECONDS

# Payment details (can be updated by developer)
PAYMENT_INFO = {
    "easypaisa": "0301-4235143 (ZoomRecorder Pro)",
    "jazzcash": "0301-4235143 (ZoomRecorder Pro)",
    "whatsapp": "+923014235143"
}


class SubscriptionDialog(QDialog):
    """Modern dark themed modal for subscription plans and activation."""
    activated = pyqtSignal()

    def __init__(self, parent=None, is_trial_expired: bool = False):
        super().__init__(parent)
        self.setWindowTitle("ZoomRecorder Pro - Subscription Plan")
        self.setFixedSize(560, 660)
        self.setModal(True)
        self.is_trial_expired = is_trial_expired

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
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a24, stop:1 #221c2e);
                border: 2px solid #e5173f;
                border-radius: 12px;
                padding: 16px;
            }
            QFrame#cardPayment {
                background-color: #181820;
                border: 1px solid #2a2a38;
                border-radius: 10px;
                padding: 14px;
            }
            QLabel {
                color: #d1d1db;
            }
            QLabel#title {
                font-size: 20px;
                font-weight: 800;
                color: #ffffff;
            }
            QLabel#badgeTrial {
                background-color: #ff2a54;
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
                font-size: 14px;
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
                font-size: 14px;
                border: none;
                border-radius: 6px;
                padding: 10px 18px;
            }
            QPushButton#btnActivate:hover {
                background-color: #ff2a54;
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
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header with Title and Status
        header_layout = QHBoxLayout()
        title_label = QLabel("⭐ ZoomRecorder Pro")
        title_label.setObjectName("title")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        if self.is_trial_expired:
            trial_badge = QLabel("⏱ 10s Free Trial Reached")
            trial_badge.setObjectName("badgeTrial")
            header_layout.addWidget(trial_badge)
        layout.addLayout(header_layout)

        # Subtitle
        sub_text = (
            "Aap ka 10-second free trial mukammal ho chuka hai.<br>"
            "Unlimited recording aur tamam Pro features unlock karne ke liye Pro plan choose karein:"
            if self.is_trial_expired else
            "Unlock unlimited recording duration, 1080p Full HD export & premium features."
        )
        sub_label = QLabel(sub_text)
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet("color: #a5a5b5; font-size: 12px; line-height: 1.4;")
        layout.addWidget(sub_label)

        # ----------------- PRICING CARD -----------------
        card = QFrame()
        card.setObjectName("cardPricing")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        # Plan Name & Badge
        plan_header = QHBoxLayout()
        plan_title = QLabel("👑 1-MONTH PRO SUBSCRIPTION")
        plan_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #fbbf24; letter-spacing: 0.5px;")
        plan_header.addWidget(plan_title)

        plan_header.addStretch()
        popular_badge = QLabel("MOST POPULAR")
        popular_badge.setStyleSheet("background-color: #e5173f; color: #fff; font-size: 10px; font-weight: bold; padding: 2px 8px; border-radius: 8px;")
        plan_header.addWidget(popular_badge)
        card_layout.addLayout(plan_header)

        # Price tag
        price_box = QHBoxLayout()
        price_tag = QLabel("1,000 PKR")
        price_tag.setObjectName("priceTag")
        price_box.addWidget(price_tag)

        price_sub = QLabel(" / 1 Month (30 Days Unlimited)")
        price_sub.setObjectName("priceSub")
        price_box.addWidget(price_sub)
        price_box.addStretch()
        card_layout.addLayout(price_box)

        # Features list
        features = [
            "✔ Unlimited Recording Duration (No 10s limit)",
            "✔ Ultra-Smooth Auto-Zoom & Focus Animations",
            "✔ Yellow Mouse Highlight & Click Ripples",
            "✔ Full HD 1080p / 60 FPS Export Quality",
            "✔ System Audio & Microphone Voice Recording",
            "✔ 100% Watermark Free & Commercial Use"
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
        pay_layout.setSpacing(6)

        pay_title = QLabel("💳 Payment & How to Buy:")
        pay_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #ffffff;")
        pay_layout.addWidget(pay_title)

        pay_desc = QLabel(
            "<b>1.</b> 1,000 PKR send karein via <b>EasyPaisa</b> ya <b>JazzCash</b>.<br>"
            "<b>2.</b> Payment screenshot WhatsApp per send kar k <b>Activation Key</b> hasil karein."
        )
        pay_desc.setWordWrap(True)
        pay_desc.setStyleSheet("color: #a0a0b2; font-size: 11px;")
        pay_layout.addWidget(pay_desc)

        # WhatsApp Order Button
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
        act_box.setSpacing(6)

        lbl_input = QLabel("Enter Activation Key:")
        lbl_input.setStyleSheet("font-weight: 600; font-size: 12px; color: #ffffff;")
        act_box.addWidget(lbl_input)

        input_row = QHBoxLayout()
        self.input_key = QLineEdit()
        self.input_key.setObjectName("keyInput")
        self.input_key.setPlaceholderText("ZR1M-XXXX-XXXX-XXXX-XXXX")
        self.input_key.returnPressed.connect(self._on_activate_clicked)
        input_row.addWidget(self.input_key)

        btn_activate = QPushButton("⚡ Activate")
        btn_activate.setObjectName("btnActivate")
        btn_activate.setCursor(Qt.PointingHandCursor)
        btn_activate.clicked.connect(self._on_activate_clicked)
        input_row.addWidget(btn_activate)
        act_box.addLayout(input_row)

        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setWordWrap(True)
        self.lbl_feedback.setStyleSheet("font-size: 12px; font-weight: bold;")
        act_box.addWidget(self.lbl_feedback)

        layout.addLayout(act_box)

        # Bottom Close Row
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setObjectName("btnClose")
        btn_close.clicked.connect(self.reject)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def _open_whatsapp(self):
        """Open WhatsApp in browser for payment & key support."""
        phone = PAYMENT_INFO.get("whatsapp", "").replace("+", "").replace("-", "").replace(" ", "")
        msg = "Salam! Mujhe ZoomRecorder Pro ki 1-Month Subscription (1000 PKR) buy karni hai."
        url = f"https://wa.me/{phone}?text={msg}"
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _on_activate_clicked(self):
        key = self.input_key.text().strip()
        if not key:
            self.lbl_feedback.setText("⚠️ Please enter your activation key.")
            self.lbl_feedback.setStyleSheet("color: #ff9900; font-size: 12px; font-weight: bold;")
            return

        success, message = subscription_mgr.activate_license(key)
        if success:
            self.lbl_feedback.setText(f"✅ {message}")
            self.lbl_feedback.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: bold;")
            QMessageBox.information(self, "Pro Activated!", message)
            self.activated.emit()
            self.accept()
        else:
            self.lbl_feedback.setText(f"❌ {message}")
            self.lbl_feedback.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: bold;")
