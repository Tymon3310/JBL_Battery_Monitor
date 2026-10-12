#!/usr/bin/env python3
"""
Script to force battery information reporting from JBL Quantum headsets.
Analyzes what is sent during connection and attempts to replicate commands.
"""

import os
import sys
import time
import struct
import glob

def find_hidraw_device():
    """Find the first hidraw device matching JBL Quantum vendor/product."""
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


def send_feature_report(device, report_id, data=None):
    """Send a HID feature report (command to the device)."""
    if data is None:
        payload = bytes([report_id] + [0] * 63)  # 64 bytes total
    else:
        payload = bytes([report_id] + list(data[:63]))  # Report ID + data

    try:
        import fcntl
        # HIDIOCSFEATURE(len) - sends feature report
        HIDIOCSFEATURE = 0xC0094806 | (len(payload) << 16)
        
        # Attempt to send feature report
        fcntl.ioctl(device.fileno(), HIDIOCSFEATURE, payload)
        return True
    except Exception as e:
        print(f"  Error sending feature report: {e}")
        return False


def try_commands(device):
    """Try different commands to request battery info."""
    print("\n🔧 Attempting to send commands to request battery info...")
    print("=" * 60)

    # Common commands to request battery on HID devices
    commands_to_try = [
        # Simple command with Report ID 0x08 (what we receive)
        (0x08, [0x08]),

        # Feature report with Report ID 0x08
        (0x08, None),

        # Other common Report IDs
        (0x01, [0x01]),
        (0x02, [0x02]),
        (0x03, [0x03]),
        (0x04, [0x04]),
        (0x05, [0x05]),
        (0x06, [0x06]),
        (0x07, [0x07]),
        (0x09, [0x09]),

        # Status request commands
        (0x01, [0x01, 0x00]),  # Request status
        (0x08, [0x08, 0x00]),  # Specifically request battery

        # Common pattern: [Report ID, Command, ...]
        (0x08, [0x08, 0x01]),  # Command 0x01 = request
        (0x08, [0x08, 0x02]),  # Command 0x02 = status
    ]

    for report_id, data in commands_to_try:
        hex_cmd = ' '.join([f'{b:02x}' for b in ([report_id] + (data or []))[:8]])
        print(f"\n📤 Trying: Report ID 0x{report_id:02x}, Data: {hex_cmd}")

        # Try writing directly to hidraw
        try:
            if data:
                cmd_bytes = bytes([report_id] + list(data))
            else:
                cmd_bytes = bytes([report_id] + [0] * 63)

            device.write(cmd_bytes)
            print(f"  ✓ Command sent: {hex_cmd}")

            # Wait for response
            time.sleep(0.3)

            # Try to read response
            import select
            ready, _, _ = select.select([device], [], [], 0.5)
            if ready:
                try:
                    response = device.read(64)
                    if response:
                        resp_bytes = list(response)
                        hex_resp = ' '.join([f'{b:02x}' for b in resp_bytes[:8]])
                        print(f"  📥 Response received: {hex_resp}")

                        # Check if it's battery info
                        if len(resp_bytes) >= 2 and resp_bytes[0] == 0x08 and 0 <= resp_bytes[1] <= 100:
                            print(f"  ⚡⚡⚡ BATTERY FOUND: {resp_bytes[1]}% ⚡⚡⚡")
                            return resp_bytes[1]
                except Exception:
                    pass
        except Exception as e:
            print(f"  ✗ Error: {e}")

        time.sleep(0.1)

    return None


def monitor_connection():
    """Monitor during connection/disconnection to capture commands."""
    print("JBL Quantum - Connection Analysis and Force Battery")
    print("=" * 60)
    
    hidraw_device = find_hidraw_device()
    if hidraw_device:
        print(f"Device found: {hidraw_device}")
    else:
        print("Device not found yet. Searching...")
    print()

    print("📋 INSTRUCTIONS:")
    print("1. This script will monitor the device.")
    print("2. DISCONNECT the USB headset now.")
    print("3. Wait 2 seconds.")
    print("4. RECONNECT the USB headset.")
    print("5. The script will capture everything that happens.")
    print()
    print("Press Enter when ready to start...")
    input()

    print("\n⏳ Waiting for disconnection...")
    print("(Disconnect the USB headset now)")

    # Monitor until device disappears
    while hidraw_device and os.path.exists(hidraw_device):
        hidraw_device = find_hidraw_device()
        time.sleep(0.1)

    print("✓ Device disconnected")
    time.sleep(2)

    print("\n⏳ Waiting for reconnection...")
    print("(Connect the USB headset now)")

    # Wait for reconnection
    timeout = 10
    start_time = time.time()
    while not hidraw_device:
        hidraw_device = find_hidraw_device()
        if time.time() - start_time > timeout:
            print("✗ Timeout: Device not reconnected")
            sys.exit(1)
        time.sleep(0.1)

    print("✓ Device reconnected!")
    time.sleep(0.5)  # Wait for stabilization

    if not check_permissions(hidraw_device):
        print("Permission error. Please run with sudo or fix udev rules.")
        sys.exit(1)

    # Now monitor everything that happens
    print("\n📡 Monitoring communication during initialization...")
    print("=" * 60)

    try:
        with open(hidraw_device, 'rb+') as f:  # rb+ for reading and writing
            # First, try to read everything the device sends
            print("\n📥 Reading data received from device...")
            packets_received = []

            # Set non-blocking for reading
            import fcntl
            flags = fcntl.fcntl(f.fileno(), fcntl.F_GETFL)
            fcntl.fcntl(f.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

            for i in range(50):  # Try to read many packets
                try:
                    import select
                    ready, _, _ = select.select([f], [], [], 0.1)
                    if ready:
                        data = f.read(64)
                        if data:
                            data_bytes = list(data)
                            hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                            timestamp = time.strftime('%H:%M:%S.%f')[:-3]
                            print(f"[{timestamp}] 📥 Received ({len(data_bytes)} bytes): {hex_data}")

                            # Check if it's battery info
                            if len(data_bytes) >= 2 and data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                                print(f"  ⚡⚡⚡ BATTERY: {data_bytes[1]}% ⚡⚡⚡")

                            packets_received.append(data_bytes)
                    else:
                        if i > 20: break # Break if no data for a while
                except Exception:
                    break
                time.sleep(0.05)

            # Restore blocking mode for try_commands which uses select itself
            fcntl.fcntl(f.fileno(), fcntl.F_SETFL, flags)

            # Now try to send commands
            if packets_received:
                print(f"\n✓ Received {len(packets_received)} packets during initialization")
                print("\nNow attempting to force battery info reporting with commands...")
            else:
                print("\n⚠ No packets received automatically")
                print("Attempting to force with commands...")

            battery = try_commands(f)

            if battery is not None:
                print(f"\n✅ SUCCESS! Battery level obtained: {battery}%")
            else:
                print("\n⚠ Could not force battery info reporting")
                print("The attempted commands did not work.")
                print("\n💡 Tip: The device may send battery info only:")
                print("  - During initialization (connection)")
                print("  - When you press buttons")
                print("  - At specific intervals")

            # Continue monitoring
            print("\n📡 Continuing monitoring... (Ctrl+C to stop)")
            print("=" * 60)

            last_battery = None
            while True:
                try:
                    import select
                    ready, _, _ = select.select([f], [], [], 1.0)
                    if ready:
                        data = f.read(64)
                        if data:
                            data_bytes = list(data)
                            hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                            timestamp = time.strftime('%H:%M:%S')

                            if len(data_bytes) >= 2 and data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                                battery = data_bytes[1]
                                if battery != last_battery:
                                    print(f"[{timestamp}] ⚡ BATTERY: {battery}%")
                                    last_battery = battery
                            else:
                                # Only print other data if it's not spamming
                                pass
                except Exception:
                    time.sleep(0.5)

    except PermissionError:
        print(f"Error: Permission denied for {hidraw_device}")
        print("Run as root or adjust permissions")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    monitor_connection()
