#!/usr/bin/env python3
"""
Script to automatically find which hidraw corresponds to the JBL Quantum.
"""

import os
import sys

VENDOR_ID = "0ecb"
PRODUCT_IDS = ["2088", "205c"]  # 910, 610


def find_jbl_hidraw():
    """Find the hidraw corresponding to the JBL Quantum."""
    print("Searching for JBL Quantum device (910 or 610)...")
    print(f"Vendor ID: 0x{VENDOR_ID}, Product IDs: {PRODUCT_IDS}")
    print()

    # Search in /sys/bus/hid/devices
    hid_devices_path = "/sys/bus/hid/devices"

    if not os.path.exists(hid_devices_path):
        print("Error: /sys/bus/hid/devices not found")
        return None

    found_devices = []

    for device_dir in os.listdir(hid_devices_path):
        device_path = os.path.join(hid_devices_path, device_dir)

        if not os.path.isdir(device_path):
            continue

        vendor_file = os.path.join(device_path, "idVendor")
        product_file = os.path.join(device_path, "idProduct")

        if os.path.exists(vendor_file) and os.path.exists(product_file):
            try:
                with open(vendor_file, 'r') as f:
                    vendor = f.read().strip().lower()
                with open(product_file, 'r') as f:
                    product = f.read().strip().lower()

                if vendor == VENDOR_ID and product in PRODUCT_IDS:
                    # Found the device!
                    print(f"✓ Device found: {device_dir} (Product ID: {product})")

                    # Look for corresponding hidraw
                    hidraw_path = os.path.join(device_path, "hidraw")
                    if os.path.exists(hidraw_path):
                        hidraw_dirs = [d for d in os.listdir(hidraw_path) if d.startswith("hidraw")]
                        if hidraw_dirs:
                            hidraw_name = hidraw_dirs[0]
                            hidraw_device = f"/dev/{hidraw_name}"

                            if os.path.exists(hidraw_device):
                                print(f"✓ Hidraw found: {hidraw_device}")

                                # Check permissions
                                if os.access(hidraw_device, os.R_OK):
                                    print(f"✓ Read permission: OK")
                                else:
                                    print(f"⚠ Read permission: DENIED")
                                    print(f"  Run: sudo chmod 666 {hidraw_device}")

                                found_devices.append({
                                    'device_dir': device_dir,
                                    'hidraw': hidraw_device,
                                    'hidraw_name': hidraw_name
                                })
                            else:
                                print(f"⚠ Hidraw {hidraw_device} does not exist yet")
                        else:
                            print(f"⚠ No hidraw found in {hidraw_path}")
                    else:
                        print(f"⚠ Hidraw path not found: {hidraw_path}")
            except Exception:
                pass

    # If not found, check lsusb
    if not found_devices:
        print("\n⚠ Device not found in /sys/bus/hid/devices")
        print("\nChecking lsusb...")
        import subprocess
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if '0ecb' in result.stdout.lower() or 'jbl' in result.stdout.lower() or 'quantum' in result.stdout.lower():
                print("✓ Device found in lsusb:")
                for line in result.stdout.split('\n'):
                    if '0ecb' in line.lower() or 'jbl' in line.lower() or 'quantum' in line.lower():
                        print(f"  {line}")
                print("\n⚠ But it was not found in /sys/bus/hid/devices")
                print("  This could mean:")
                print("  - The device is still initializing")
                print("  - The HID driver was not loaded")
                print("  - Wait a few seconds and try again")
            else:
                print("✗ Device not found in lsusb")
                print("\nPossible causes:")
                print("1. The headset is not connected via USB")
                print("2. The USB cable is faulty")
                print("3. Try disconnecting and reconnecting the headset")
        except Exception:
            pass

        return None

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Devices found: {len(found_devices)}")

    for i, dev in enumerate(found_devices, 1):
        print(f"\nDevice {i}:")
        print(f"  Directory: {dev['device_dir']}")
        print(f"  Hidraw: {dev['hidraw']}")
        print(f"  Name: {dev['hidraw_name']}")

    # Return the first (or only) one
    return found_devices[0]['hidraw'] if found_devices else None


if __name__ == "__main__":
    hidraw = find_jbl_hidraw()

    if hidraw:
        print(f"\n{'='*60}")
        print(f"✅ USE THIS HIDRAW:")
        print(f"   {hidraw}")
        print(f"{'='*60}")
        print(f"\nTo use in scripts, edit the HIDRAW_DEVICE variable:")
        print(f"  HIDRAW_DEVICE = \"{hidraw}\"")
        print(f"\nOr run scripts that detect it automatically.")
    else:
        print("\n❌ Could not find the device")
        sys.exit(1)
