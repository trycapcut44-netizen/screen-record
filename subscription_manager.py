"""
subscription_manager.py - Single-Use Licensing & Free Video Policy for ZoomRecorder Pro
Policies:
- 1st Video on device: 100% Free, unlimited duration, saves normally.
- 2nd Video onwards: Can record, but when ended, video is NOT saved unless 1,000 PKR Pro Plan is activated.
- Single-Use Keys:
  * Device-bound keys tied to customer's unique Device ID (cannot be shared).
  * Burned into tamper-signed used_keys registry once redeemed (cannot be reused).
"""

import os
import sys
import time
import json
import hmac
import hashlib
import secrets
from pathlib import Path
from typing import Dict, Tuple, Optional, List

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False

# Secret cryptographic salt
SECRET_SALT = b"ZR_PRO_2026_SECURE_SALT_v2_9a8fdb83_single_use"


def get_data_dir() -> Path:
    """Get system application data directory for ZoomRecorder."""
    app_data = os.environ.get("APPDATA")
    if app_data:
        base = Path(app_data) / "ZoomRecorder"
    else:
        base = Path.home() / ".zoomrecorder"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_device_id() -> str:
    """
    Returns unique, hardware-derived Device ID (e.g. ZR-24A2-BD46).
    Uses Windows Cryptography MachineGuid with fallback to MAC/CPU.
    """
    guid = ""
    if WINREG_AVAILABLE:
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(k, "MachineGuid")
            winreg.CloseKey(k)
        except Exception:
            pass

    if not guid:
        # Fallback to user and machine name
        guid = f"{os.environ.get('COMPUTERNAME', '')}-{os.environ.get('USERNAME', '')}-ZR2026"

    h = hashlib.sha256(guid.encode("utf-8")).hexdigest().upper()
    return f"ZR-{h[:4]}-{h[4:8]}"


class SubscriptionManager:
    """
    Manages trial status, device binding, and single-use license verification.
    """

    def __init__(self):
        self.data_dir = get_data_dir()
        self.license_file = self.data_dir / "license.dat"
        self.trial_file = self.data_dir / "trial.dat"
        self.used_keys_file = self.data_dir / "used_keys.dat"
        self.device_id = get_device_id()

        self._state = self._load_license_state()

    # ----------------- Signatures & Crypto -----------------

    @staticmethod
    def _sign(text: str) -> str:
        """HMAC-SHA256 signature."""
        return hmac.new(SECRET_SALT, text.encode("utf-8"), hashlib.sha256).hexdigest()

    # ----------------- Key Generation (For Owner) -----------------

    @classmethod
    def generate_device_key(cls, device_id: str, plan_type: str = "1M") -> str:
        """
        Generate a single-use key bound to a customer's Device ID.
        Format: ZR1M-DEV1-DEV2-SALT-SIG1-SIG2
        Example: ZR1M-24A2-BD46-9E1A-B8F2-7A1C
        """
        prefix = "ZR1M" if plan_type == "1M" else "ZRLF"
        cleaned_dev = device_id.upper().replace("ZR-", "").replace("-", "").strip()
        if len(cleaned_dev) < 8:
            cleaned_dev = (cleaned_dev + "00000000")[:8]
        else:
            cleaned_dev = cleaned_dev[:8]

        dev_part1 = cleaned_dev[:4]
        dev_part2 = cleaned_dev[4:8]

        # 4 hex chars random issue salt to ensure renewal keys are unique
        salt = secrets.token_hex(2).upper()

        raw_payload = f"{prefix}:{cleaned_dev}:{salt}:30"
        sig = hmac.new(SECRET_SALT, raw_payload.encode("utf-8"), hashlib.sha256).hexdigest().upper()[:8]
        sig_part1 = sig[:4]
        sig_part2 = sig[4:8]

        return f"{prefix}-{dev_part1}-{dev_part2}-{salt}-{sig_part1}-{sig_part2}"

    @classmethod
    def generate_universal_key(cls, plan_type: str = "1M") -> str:
        """
        Generate a single-use universal key (usable on any 1 PC, then burned).
        Format: ZR1U-TOK1-TOK2-SALT-SIG1-SIG2
        """
        prefix = "ZR1U" if plan_type == "1M" else "ZRLU"
        token = secrets.token_hex(4).upper()  # 8 chars
        salt = secrets.token_hex(2).upper()   # 4 chars

        tok_part1 = token[:4]
        tok_part2 = token[4:8]

        raw_payload = f"{prefix}:{token}:{salt}:30"
        sig = hmac.new(SECRET_SALT, raw_payload.encode("utf-8"), hashlib.sha256).hexdigest().upper()[:8]
        sig_part1 = sig[:4]
        sig_part2 = sig[4:8]

        return f"{prefix}-{tok_part1}-{tok_part2}-{salt}-{sig_part1}-{sig_part2}"

    # ----------------- Used Keys Management -----------------

    def _load_used_keys(self) -> List[str]:
        """Load list of keys already redeemed on this device."""
        if not self.used_keys_file.exists():
            return []
        try:
            with open(self.used_keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            keys = data.get("keys", [])
            sig = data.get("sig", "")
            raw = ":".join(sorted(keys))
            if not hmac.compare_digest(sig, self._sign(f"used:{raw}")):
                # Tampered used_keys file
                return keys
            return keys
        except Exception:
            return []

    def _mark_key_used(self, key: str):
        """Burn key so it can never be used again."""
        cleaned = key.strip().upper()
        used = self._load_used_keys()
        if cleaned not in used:
            used.append(cleaned)
        raw = ":".join(sorted(used))
        sig = self._sign(f"used:{raw}")
        try:
            with open(self.used_keys_file, "w", encoding="utf-8") as f:
                json.dump({"keys": used, "sig": sig}, f, indent=2)
        except Exception:
            pass

    def is_key_used(self, key: str) -> bool:
        """Check if key has already been burned."""
        cleaned = key.strip().upper()
        return cleaned in self._load_used_keys()

    # ----------------- Key Validation -----------------

    def validate_key(self, key: str) -> Tuple[bool, str, int]:
        """
        Validates format, signature, device binding, and single-use status.
        Returns: (is_valid, plan_description_or_error, duration_days)
        """
        cleaned = key.strip().upper().replace(" ", "")
        parts = cleaned.split("-")

        # Support 6-part keys: PREFIX-PART1-PART2-SALT-SIG1-SIG2
        if len(parts) != 6:
            # Also support legacy 5-part key if needed
            if len(parts) == 5:
                prefix, t1, t2, s1, s2 = parts
                if self.is_key_used(cleaned):
                    return False, "Yeh key pehle hi use ho chuki hai! Ek key sirf 1 bar use ho sakti hai.", 0
                raw = f"{prefix}-{t1}{t2}"
                sig_exp = hmac.new(SECRET_SALT, raw.encode("utf-8"), hashlib.sha256).hexdigest().upper()[:8]
                if hmac.compare_digest(sig_exp, f"{s1}{s2}"):
                    return True, "1-Month Pro Plan (1,000 PKR)", 30
            return False, "Invalid key format. Please check the key and try again.", 0

        prefix, p1, p2, salt, s1, s2 = parts
        sig_given = f"{s1}{s2}"

        # 1. Check if key is already burned
        if self.is_key_used(cleaned):
            return False, "Yeh key pehle hi use ho chuki hai! Ek key sirf 1 bar use hoti hai.", 0

        # 2. Check Device-Bound Key
        if prefix in ("ZR1M", "ZRLF"):
            embedded_dev = f"ZR-{p1}-{p2}"
            if embedded_dev != self.device_id:
                return (
                    False,
                    f"Yeh key kisi aur device ke liye hai!\nAap ki Device ID '{self.device_id}' hai.",
                    0
                )
            raw_payload = f"{prefix}:{p1}{p2}:{salt}:30"
            sig_exp = hmac.new(SECRET_SALT, raw_payload.encode("utf-8"), hashlib.sha256).hexdigest().upper()[:8]
            if not hmac.compare_digest(sig_exp, sig_given):
                return False, "Invalid activation key signature.", 0

            duration = 30 if prefix == "ZR1M" else 3650
            return True, "1-Month Pro Plan (1,000 PKR)", duration

        # 3. Check Universal 1-Time Key
        elif prefix in ("ZR1U", "ZRLU"):
            raw_payload = f"{prefix}:{p1}{p2}:{salt}:30"
            sig_exp = hmac.new(SECRET_SALT, raw_payload.encode("utf-8"), hashlib.sha256).hexdigest().upper()[:8]
            if not hmac.compare_digest(sig_exp, sig_given):
                return False, "Invalid activation key signature.", 0

            duration = 30 if prefix == "ZR1U" else 3650
            return True, "1-Month Pro Plan (1,000 PKR)", duration

        return False, "Unrecognized key type.", 0

    # ----------------- License Activation & Persistence -----------------

    def _load_license_state(self) -> Dict:
        """Load and verify signed license data from disk."""
        if not self.license_file.exists():
            return {"active": False}

        try:
            with open(self.license_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            key = data.get("key", "")
            expires_at = data.get("expires_at", 0)
            dev_id = data.get("device_id", "")
            sig = data.get("signature", "")

            # Verify integrity & device match
            expected_sig = self._sign(f"{key}:{dev_id}:{expires_at}")
            if not hmac.compare_digest(sig, expected_sig):
                return {"active": False}

            if dev_id != self.device_id:
                return {"active": False}

            if time.time() > expires_at:
                return {"active": False, "expired": True, "key": key}

            return {
                "active": True,
                "key": key,
                "plan": data.get("plan", "1-Month Pro"),
                "activated_at": data.get("activated_at", 0),
                "expires_at": expires_at,
                "device_id": dev_id
            }
        except Exception:
            return {"active": False}

    def activate_license(self, key: str) -> Tuple[bool, str]:
        """
        Validate, burn, and activate single-use license for this device.
        """
        is_valid, desc_or_err, duration_days = self.validate_key(key)
        if not is_valid:
            return False, desc_or_err

        cleaned = key.strip().upper().replace(" ", "")
        now = time.time()
        expires_at = now + (duration_days * 86400)
        sig = self._sign(f"{cleaned}:{self.device_id}:{expires_at}")

        payload = {
            "key": cleaned,
            "plan": desc_or_err,
            "device_id": self.device_id,
            "activated_at": now,
            "expires_at": expires_at,
            "signature": sig
        }

        try:
            with open(self.license_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            # Burn the key so it cannot be used again
            self._mark_key_used(cleaned)

            self._state = {
                "active": True,
                "key": cleaned,
                "plan": desc_or_err,
                "device_id": self.device_id,
                "activated_at": now,
                "expires_at": expires_at
            }
            return True, f"Pro Subscription activated! Enjoy {duration_days} days of unlimited screen recording."
        except Exception as e:
            return False, f"Activation error: {e}"

    # ----------------- Free Video Trial Policy -----------------

    def get_free_recordings_used(self) -> int:
        """Returns how many free videos have been saved on this device."""
        if not self.trial_file.exists():
            return 0
        try:
            with open(self.trial_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            count = int(data.get("free_recordings_used", 0))
            sig = data.get("sig", "")
            if not hmac.compare_digest(sig, self._sign(f"free_vids:{count}:{self.device_id}")):
                # Tampered trial file -> treat as 1 (expired)
                return 1
            return count
        except Exception:
            return 1

    def record_free_video_completed(self):
        """Mark the 1st free video as completed."""
        count = max(1, self.get_free_recordings_used() + 1)
        sig = self._sign(f"free_vids:{count}:{self.device_id}")
        try:
            with open(self.trial_file, "w", encoding="utf-8") as f:
                json.dump({"free_recordings_used": count, "sig": sig}, f, indent=2)
        except Exception:
            pass

    def is_first_video_free(self) -> bool:
        """Returns True if the 1st free video has not been consumed yet."""
        if self.is_subscribed():
            return True
        return self.get_free_recordings_used() == 0

    def is_subscribed(self) -> bool:
        """Returns True if active Pro subscription exists on this device."""
        if not self._state.get("active", False):
            return False
        expires_at = self._state.get("expires_at", 0)
        if time.time() > expires_at:
            self._state["active"] = False
            return False
        return True

    def get_remaining_days(self) -> int:
        """Days remaining on subscription."""
        if not self.is_subscribed():
            return 0
        expires_at = self._state.get("expires_at", 0)
        secs_left = max(0.0, expires_at - time.time())
        return int(secs_left // 86400) + 1

    def get_status_text(self) -> str:
        if self.is_subscribed():
            return f"👑 PRO ACTIVE ({self.get_remaining_days()}d)"
        if self.is_first_video_free():
            return "⚡ 1st VIDEO FREE (Any Length)"
        return "🔒 PAID PLAN REQUIRED"


# Global singleton instance
subscription_mgr = SubscriptionManager()
