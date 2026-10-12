#!/usr/bin/env python3
"""
Script to capture what happens during connection/disconnection
and attempt to force battery information reporting.
"""

import os
import sys
import time
import struct
import fcntl

# Use a generic name or list of possibilities
HIDRAW_DEVICES = [f"/dev/hidraw{i}" for i in range(16)]

# HID IOCTLs
HIDIOCSFEATURE = lambda length: 0xC0094806 | (length << 16)  # Send feature report
HIDIOCGFEATURE = lambda length: 0xC0094807 | (length << 16)  # Get feature report


def find_hidraw_device():
    """Find the first hidraw device matching JBL Quantum vendor/product."""
    import glob
    VENDOR_ID = "0ecb"
    PRODUCT_IDS = ["2088", "205c"]  # 910, 610

    # Look through /sys/bus/hid/devices
    for device_dir in glob.glob("/sys/bus/hid/devices/*"):
        vendor_file = os.path.join(device_dir, "idVendor")
        product_file = os.path.join(device_dir, "idProduct")

        if os.path.exists(vendor_file) and os.path.exists(product_file):
            try:
                with open(vendor_file, 'r') as f:
                    vendor = f.read().strip().lower()
                with open(product_file, 'r') as f:
                    product = f.read().strip().lower()

                if vendor == VENDOR_ID and product in PRODUCT_IDS:
                    hidraw_path = os.path.join(device_dir, "hidraw")
                    if os.path.exists(hidraw_path):
                        hidraw_dirs = [d for d in os.listdir(hidraw_path) if d.startswith("hidraw")]
                        if hidraw_dirs:
                            hidraw_device = f"/dev/{hidraw_dirs[0]}"
                            if os.path.exists(hidraw_device):
                                return hidraw_device
            except Exception:
                pass
    return None


def check_permissions(device_path):
    """Check if we have permission to access the hidraw device."""
    if not device_path or not os.path.exists(device_path):
        return False

    if not os.access(device_path, os.R_OK | os.W_OK):
        print(f"Error: No permission to read/write {device_path}")
        print(f"Current permissions: {oct(os.stat(device_path).st_mode)[-3:]}")
        print("\nSolutions:")
        print(f"1. Run as root: sudo python3 {sys.argv[0]}")
        print(f"2. Or adjust permissions: sudo chmod 666 {device_path}")
        return False

    return True


def send_feature_report(fd, report_id, data=None):
    """Send a feature report using ioctl."""
    if data is None:
        payload = bytes([report_id] + [0] * 63)
    else:
        payload = bytes([report_id] + list(data[:63]))

    try:
        fcntl.ioctl(fd, HIDIOCSFEATURE(len(payload)), payload)
        return True
    except Exception:
        return False


def get_feature_report(fd, report_id, length=64):
    """Receive a feature report using ioctl."""
    payload = bytes([report_id] + [0] * (length - 1))
    try:
        fcntl.ioctl(fd, HIDIOCGFEATURE(length), payload)
        return list(payload)
    except Exception:
        return None


def monitor_connection():
    """Monitor during connection to capture what happens."""
    print("JBL Quantum - Connection Data Capture")
    print("=" * 60)
    
    hidraw_device = find_hidraw_device()
    if hidraw_device:
        print(f"Device found: {hidraw_device}")
    else:
        print("Device not found yet. Searching...")
    print()

    print("📋 INSTRUCTIONS:")
    print("1. The script will monitor continuously.")
    print("2. DISCONNECT the USB headset.")
    print("3. RECONNECT the USB headset.")
    print("4. The script will capture everything that happens.")
    print()
    print("Press Ctrl+C to stop\n")
    print("=" * 60)

    last_seen = hidraw_device is not None
    packets_during_connection = []

    try:
        while True:
            hidraw_device = find_hidraw_device()
            
            # Check if device is connected
            if hidraw_device and os.path.exists(hidraw_device):
                if not last_seen:
                    # Device just connected!
                    print(f"\n{'='*60}")
                    print(f"🔌 DEVICE CONNECTED - {time.strftime('%H:%M:%S')}")
                    print(f"{'='*60}\n")

                    if not check_permissions(hidraw_device):
                        print("Permission error. Please run with sudo or fix udev rules.")
                        last_seen = True
                        continue

                    time.sleep(0.5)  # Wait for stabilization

                    # Open and monitor intensely
                    with open(hidraw_device, 'rb') as f:
                        print("📡 Capturing data during initialization...")
                        print("-" * 60)

                        # Read everything in the first few seconds
                        start_time = time.time()
                        import select
                        while time.time() - start_time < 3:  # 3 seconds
                            try:
                                # Use select for non-blocking read
                                ready, _, _ = select.select([f], [], [], 0.1)
                                if not ready:
                                    continue
                                data = f.read(64)
                                if data:
                                    data_bytes = list(data)
                                    hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                                    timestamp = time.strftime('%H:%M:%S.%f')[:-3]

                                    print(f"[{timestamp}] 📥 Received ({len(data_bytes)} bytes)")
                                    print(f"  Hex: {hex_data}")
                                    print(f"  Dec: {data_bytes}")

                                    # Check if it's battery info
                                    if len(data_bytes) >= 2:
                                        if data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                                            print(f"  ⚡⚡⚡ BATTERY: {data_bytes[1]}% ⚡⚡⚡")

                                        # Packet analysis
                                        print(f"  📊 Analysis:")
                                        print(f"    - Byte[0] (Report ID): 0x{data_bytes[0]:02x} ({data_bytes[0]})")
                                        if len(data_bytes) > 1:
                                            print(f"    - Byte[1] (Battery?): 0x{data_bytes[1]:02x} ({data_bytes[1]})")

                                    packets_during_connection.append(data_bytes)
                                    print()

                            except Exception:
                                pass

                        print(f"✓ Captured {len(packets_during_connection)} packets during connection")
                        print("-" * 60)

                        # Now try to force with feature reports
                        print("\n🔧 Attempting to force battery info reporting...")
                        print("-" * 60)

                        # Try different feature reports
                        for report_id in [0x08, 0x01, 0x02, 0x03, 0x04, 0x05]:
                            print(f"\n📤 Trying Feature Report 0x{report_id:02x}...")

                            # Try to receive feature report
                            try:
                                with open(hidraw_device, 'rb+') as f2:
                                    result = get_feature_report(f2.fileno(), report_id)
                                    if result:
                                        hex_resp = ' '.join([f'{b:02x}' for b in result[:8]])
                                        print(f"  📥 Response: {hex_resp}")

                                        if len(result) >= 2 and result[0] == 0x08 and 0 <= result[1] <= 100:
                                            print(f"  ⚡⚡⚡ BATTERY: {result[1]}% ⚡⚡⚡")
                                    else:
                                        print(f"  (No response)")

                                    # Try to send feature report
                                    if send_feature_report(f2.fileno(), report_id):
                                        print(f"  ✓ Command sent")
                                        time.sleep(0.2)

                                    # Try to read response
                                    try:
                                        import select
                                        ready, _, _ = select.select([f2], [], [], 0.3)
                                        if ready:
                                            resp = f2.read(64)
                                            if resp:
                                                resp_bytes = list(resp)
                                                hex_resp = ' '.join([f'{b:02x}' for b in resp_bytes[:8]])
                                                print(f"  📥 Response: {hex_resp}")

                                                if len(resp_bytes) >= 2 and resp_bytes[0] == 0x08 and 0 <= resp_bytes[1] <= 100:
                                                    print(f"  ⚡⚡⚡ BATTERY: {resp_bytes[1]}% ⚡⚡⚡")
                                    except Exception:
                                        pass
                            except Exception as e:
                                print(f"  ✗ Error: {e}")

                            time.sleep(0.2)

                last_seen = True

                # Monitor continuously
                try:
                    with open(hidraw_device, 'rb') as f:
                        import select
                        ready, _, _ = select.select([f], [], [], 0.5)
                        if ready:
                            data = f.read(64)
                            if data:
                                data_bytes = list(data)
                                if len(data_bytes) >= 2 and data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                                    timestamp = time.strftime('%H:%M:%S')
                                    print(f"[{timestamp}] ⚡ BATTERY: {data_bytes[1]}%")
                except Exception:
                    pass
            else:
                if last_seen:
                    print(f"\n🔌 Device disconnected - {time.strftime('%H:%M:%S')}")
                    packets_during_connection = []
                last_seen = False

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        if packets_during_connection:
            print(f"Packets captured during connection: {len(packets_during_connection)}")
            print("\nUnique packets:")
            seen = set()
            for pkt in packets_during_connection:
                pkt_str = ' '.join([f'{b:02x}' for b in pkt])
                if pkt_str not in seen:
                    print(f"  {pkt_str}")
                    seen.add(pkt_str)
        print("=" * 60)


if __name__ == "__main__":
    monitor_connection()
