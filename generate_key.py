"""
generate_key.py - Single-Use License Key Generator for ZoomRecorder Pro
Run this script whenever a customer pays you 1,000 PKR.
Each key generated can ONLY be used once.
"""

import sys
from subscription_manager import SubscriptionManager


def main():
    print("=" * 65)
    print("      ZoomRecorder Pro - Single-Use License Key Generator")
    print("=" * 65)
    print("Har key sirf 1 martaba use ho sakti hai (Single-Use Only).")
    print("Agar customer kisi aur ko bhejega to dosri device par kaam nahi karegi!")
    print("=" * 65)
    print("Key Type:")
    print("  [1] Device-Bound Key (Customer ki Device ID k mutabiq - RECOMMENDED)")
    print("  [2] Universal 1-Time Key (Kisi bhi 1 device par 1 dafa lag sakti hai)")
    print("-" * 65)

    mode = input("Select Option [1 or 2, default is 1]: ").strip()
    if mode != "2":
        dev_id = input("\nCustomer ki Device ID enter karein (e.g. ZR-24A2-BD46): ").strip().upper()
        if not dev_id:
            print("[Error] Device ID lazmi hai.")
            input("\nPress Enter to exit...")
            return

        key = SubscriptionManager.generate_device_key(dev_id, plan_type="1M")
        print("\n" + "=" * 65)
        print("  DEVICE-BOUND LICENSE KEY GENERATED:")
        print("=" * 65)
        print(f"  Target Device ID :  {dev_id}")
        print(f"  Plan             :  1-Month Pro Plan (1,000 PKR)")
        print(f"  Activation Key   :  {key}")
        print("=" * 65)
        print("Customer ko yeh key WhatsApp par send kar dein.")
        print("Yeh key sirf isi customer ki device par chalegi aur sirf 1 bar use hogi.")
    else:
        key = SubscriptionManager.generate_universal_key(plan_type="1M")
        print("\n" + "=" * 65)
        print("  UNIVERSAL SINGLE-USE LICENSE KEY GENERATED:")
        print("=" * 65)
        print(f"  Plan             :  1-Month Pro Plan (1,000 PKR)")
        print(f"  Activation Key   :  {key}")
        print("=" * 65)
        print("Yeh key kisi bhi 1 device par activate hogi aur us k baad burn ho jayegi.")

    print("=" * 65)
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
