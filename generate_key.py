"""
generate_key.py - License Key Generator for ZoomRecorder Pro
Run this script whenever a customer pays you 1,000 PKR to generate a valid 1-Month activation key.
You can also generate Lifetime keys.
"""

import sys
from subscription_manager import SubscriptionManager


def main():
    print("=" * 60)
    print("      ZoomRecorder Pro - License Key Generator")
    print("=" * 60)
    print("Plans Available:")
    print("  [1] 1-Month Subscription Plan (1,000 PKR - 30 Days)")
    print("  [2] Lifetime Pro License (Unlimited Access)")
    print("=" * 60)

    choice = input("Select plan [1 or 2, default is 1]: ").strip()
    plan_type = "1M" if choice != "2" else "LF"
    plan_desc = "1-Month Pro Plan (1,000 PKR)" if plan_type == "1M" else "Lifetime Pro License"

    how_many_str = input("How many keys do you want to generate? [Default 1]: ").strip()
    try:
        count = int(how_many_str) if how_many_str else 1
    except ValueError:
        count = 1

    print("\n" + "-" * 60)
    print(f"Generated {count} Key(s) for: {plan_desc}")
    print("-" * 60)

    for i in range(count):
        key = SubscriptionManager.generate_license_key(plan_type)
        print(f"  Key #{i+1}:  {key}")

    print("-" * 60)
    print("Customer ko yeh key copy kar k send kar dein.")
    print("Customer app me ja kar yeh key enter karega to uska Pro activate ho jayega.")
    print("=" * 60)
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
