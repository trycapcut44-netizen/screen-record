"""
subscription_manager.py - License Key and Trial Management for ZoomRecorder Pro
Handles:
- Free trial tracking (10 seconds limit for non-subscribers)
- Secure HMAC-SHA256 license key generation and validation
- Encrypted / tamper-proof local license persistence
- Support for 1-Month (1,000 PKR) and Lifetime subscription plans
"""

import os
import sys
import time
import json
import hmac
import hashlib
import secrets
from pathlib import Path
from typing import Dict, Tuple, Optional

# Secret salt for cryptographic signature verification (Keep secure)
SECRET_SALT = b"ZR_PRO_2026_SECURE_SALT_v1_9a8fdb83"

# Free trial recording duration in seconds
FREE_TRIAL_SECONDS = 10.0


def get_data_dir() -> Path:
    """Get system application data directory for ZoomRecorder."""
    app_data = os.environ.get("APPDATA")
    if app_data:
        base = Path(app_data) / "ZoomRecorder"
    else:
        base = Path.home() / ".zoomrecorder"
    base.mkdir(parents=True, exist_ok=True)
    return base


class SubscriptionManager:
    """
    Manages trial state and subscription activation.
    Guarantees tamper-resistance with HMAC signatures.
    """

    def __init__(self):
        self.data_dir = get_data_dir()
        self.license_file = self.data_dir / "license.dat"
        self.trial_file = self.data_dir / "trial.dat"

        self._state = self._load_state()

    # ----------------- Cryptographic Helpers -----------------

    @staticmethod
    def _sign(text: str) -> str:
        """Generate HMAC-SHA256 hex digest for tamper verification."""
        return hmac.new(SECRET_SALT, text.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def generate_license_key(plan_type: str = "1M") -> str:
        """
        Generates a valid license key.
        Format: ZR1M-XXXX-XXXX-YYYY-YYYY
        ZR1M = 1 Month (30 Days)
        ZRLF = Lifetime
        """
        prefix = "ZR1M" if plan_type == "1M" else "ZRLF"
        # 8 hex chars random token
        token_raw = secrets.token_hex(4).upper()  # 8 characters, e.g. 'A1B2C3D4'
        token_part1 = token_raw[:4]
        token_part2 = token_raw[4:]

        # Sign prefix + token
        signature = hmac.new(SECRET_SALT, f"{prefix}-{token_raw}".encode("utf-8"), hashlib.sha256).hexdigest().upper()
        sig_part1 = signature[:4]
        sig_part2 = signature[4:8]

        return f"{prefix}-{token_part1}-{token_part2}-{sig_part1}-{sig_part2}"

    @classmethod
    def validate_key(cls, key: str) -> Tuple[bool, str, int]:
        """
        Validates license key format and HMAC signature.
        Returns: (is_valid, plan_type, duration_days)
        """
        cleaned = key.strip().upper().replace(" ", "")
        parts = cleaned.split("-")
        if len(parts) != 5:
            return False, "", 0

        prefix, t1, t2, s1, s2 = parts
        if prefix not in ("ZR1M", "ZRLF"):
            return False, "", 0

        token_raw = f"{t1}{t2}"
        sig_expected = hmac.new(SECRET_SALT, f"{prefix}-{token_raw}".encode("utf-8"), hashlib.sha256).hexdigest().upper()[:8]
        sig_given = f"{s1}{s2}"

        if not hmac.compare_digest(sig_expected, sig_given):
            return False, "", 0

        if prefix == "ZR1M":
            return True, "1-Month Pro Plan (1,000 PKR)", 30
        else:
            return True, "Lifetime Pro Plan", 3650

    # ----------------- State Persistence -----------------

    def _load_state(self) -> Dict:
        """Load and verify signed license data from disk."""
        if not self.license_file.exists():
            return {"active": False}

        try:
            with open(self.license_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            key = data.get("key", "")
            expires_at = data.get("expires_at", 0)
            sig = data.get("signature", "")

            # Verify integrity
            expected_sig = self._sign(f"{key}:{expires_at}")
            if not hmac.compare_digest(sig, expected_sig):
                # Tampered file!
                return {"active": False}

            # Check expiration
            current_time = time.time()
            if current_time > expires_at:
                return {"active": False, "expired": True, "key": key}

            return {
                "active": True,
                "key": key,
                "plan": data.get("plan", "1-Month Pro"),
                "activated_at": data.get("activated_at", 0),
                "expires_at": expires_at
            }
        except Exception:
            return {"active": False}

    def _save_state(self, key: str, plan: str, duration_days: int) -> bool:
        """Persist verified license with cryptographic signature."""
        try:
            now = time.time()
            expires_at = now + (duration_days * 86400)
            sig = self._sign(f"{key}:{expires_at}")

            payload = {
                "key": key,
                "plan": plan,
                "activated_at": now,
                "expires_at": expires_at,
                "signature": sig
            }

            with open(self.license_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            self._state = {
                "active": True,
                "key": key,
                "plan": plan,
                "activated_at": now,
                "expires_at": expires_at
            }
            return True
        except Exception:
            return False

    # ----------------- Subscription Checks -----------------

    def is_subscribed(self) -> bool:
        """Check if user has an active, valid, non-expired subscription."""
        if not self._state.get("active", False):
            return False

        expires_at = self._state.get("expires_at", 0)
        if time.time() > expires_at:
            self._state["active"] = False
            return False

        return True

    def get_remaining_days(self) -> int:
        """Return number of days left on active subscription."""
        if not self.is_subscribed():
            return 0
        expires_at = self._state.get("expires_at", 0)
        secs_left = max(0.0, expires_at - time.time())
        return int(secs_left // 86400) + 1

    def get_plan_name(self) -> str:
        """Return human-readable plan description."""
        if self.is_subscribed():
            days = self.get_remaining_days()
            return f"Pro Active ({days} days left)"
        return "Free Trial (10s Limit)"

    def activate_license(self, key: str) -> Tuple[bool, str]:
        """
        Attempt to activate subscription using key.
        Returns: (success: bool, message: str)
        """
        is_valid, plan_name, duration_days = self.validate_key(key)
        if not is_valid:
            return False, "Invalid activation key. Please check the code and try again."

        success = self._save_state(key=key.strip().upper(), plan=plan_name, duration_days=duration_days)
        if success:
            return True, f"Subscription successfully activated! Enjoy {duration_days} days of unlimited ZoomRecorder Pro."
        else:
            return False, "Could not save activation data. Please run as administrator."

    # ----------------- Free Trial Tracking -----------------

    def get_trial_seconds_limit(self) -> float:
        """Free trial limit in seconds."""
        return FREE_TRIAL_SECONDS

    def is_trial_used(self) -> bool:
        """Returns True if the user has already consumed their 10s free recording."""
        if self.is_subscribed():
            return False

        if not self.trial_file.exists():
            return False

        try:
            with open(self.trial_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            recorded = data.get("recorded_seconds", 0.0)
            sig = data.get("sig", "")
            if not hmac.compare_digest(sig, self._sign(f"trial:{recorded}")):
                # Tampered trial file -> treat as expired
                return True
            return recorded >= FREE_TRIAL_SECONDS
        except Exception:
            return True

    def get_trial_seconds_used(self) -> float:
        """Get total recorded seconds under free trial."""
        if not self.trial_file.exists():
            return 0.0

        try:
            with open(self.trial_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return float(data.get("recorded_seconds", 0.0))
        except Exception:
            return FREE_TRIAL_SECONDS

    def record_trial_usage(self, duration_sec: float):
        """Update trial recorded duration."""
        if self.is_subscribed():
            return

        current = self.get_trial_seconds_used()
        new_total = min(FREE_TRIAL_SECONDS, current + duration_sec)
        sig = self._sign(f"trial:{new_total}")

        try:
            with open(self.trial_file, "w", encoding="utf-8") as f:
                json.dump({"recorded_seconds": new_total, "sig": sig}, f)
        except Exception:
            pass


# Global singleton instance
subscription_mgr = SubscriptionManager()
