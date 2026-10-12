#!/usr/bin/env python3
"""
Script to read JBL Quantum910 data via hidraw.
Tries to use hidraw, but uses pyusb as fallback if it fails.
"""

import os
import sys
import time
import struct


# Tries to detect hidraw automatically
def find_hidraw_device():
    """Automatically finds which hidraw corresponds to JBL Quantum"""
    import glob
    VENDOR_ID = "0ecb"
    PRODUCT_IDS = ["2088", "205c"]  # 910, 610

    # Looks in /sys/bus/hid/devices
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
                    # Found! Looking for hidraw
                    hidraw_path = os.path.join(device_dir, "hidraw")
                    if os.path.exists(hidraw_path):
                        hidraw_dirs = [d for d in os.listdir(hidraw_path) if d.startswith("hidraw")]
                        if hidraw_dirs:
                            hidraw_device = f"/dev/{hidraw_dirs[0]}"
                            if os.path.exists(hidraw_device):
                                return hidraw_device
            except Exception:
                pass

    # Fallback: tries common hidraw
    for i in range(10):
        hidraw = f"/dev/hidraw{i}"
        if os.path.exists(hidraw):
            return hidraw

    return None


HIDRAW_DEVICE = find_hidraw_device()
USE_PYUSB_FALLBACK = True  # Uses pyusb if hidraw fails


def check_permissions():
    """Checks if we have permission to access hidraw"""
    if not os.path.exists(HIDRAW_DEVICE):
        print(f"Error: {HIDRAW_DEVICE} not found")
        return False

    if not os.access(HIDRAW_DEVICE, os.R_OK):
        print(f"Error: No permission to read {HIDRAW_DEVICE}")
        print(f"Current permissions: {oct(os.stat(HIDRAW_DEVICE).st_mode)[-3:]}")
        print("\nSolutions:")
        print(f"1. Run as root: sudo python3 {sys.argv[0]}")
        print(f"2. Or adjust permissions: sudo chmod 666 {HIDRAW_DEVICE}")
        return False

    return True


def analyze_byte(byte_val, position):
    """Analyzes an individual byte and returns possible interpretations"""
    interpretations = []

    # Interpretation as percentage
    if 0 <= byte_val <= 100:
        interpretations.append(f"Possible percentage: {byte_val}%")

    # Interpretation as boolean/flags
    if byte_val in [0, 1]:
        interpretations.append(f"Boolean: {bool(byte_val)}")

    # Interpretation as ASCII code (if printable)
    if 32 <= byte_val <= 126:
        interpretations.append(f"ASCII: '{chr(byte_val)}'")

    # Interpretation as common status code
    status_codes = {0: "OK/Off", 1: "Active", 255: "Maximum/Unknown"}
    if byte_val in status_codes:
        interpretations.append(f"Status: {status_codes[byte_val]}")

    # Individual bits
    if byte_val > 0 and byte_val < 256:
        bits = format(byte_val, '08b')
        set_bits = [i for i, bit in enumerate(bits) if bit == '1']
        if len(set_bits) <= 4:  # If few bits set, could be flags
            interpretations.append(f"Set bits: {set_bits} (bin: {bits})")

    return interpretations


def analyze_data(data_bytes, last_data=None):
    """Analyzes received data in detail"""
    analysis = []

    # Byte-by-byte analysis
    analysis.append("\n  📊 DETAILED ANALYSIS:")
    analysis.append("  " + "-" * 56)

    for i, byte_val in enumerate(data_bytes):
        interpretations = analyze_byte(byte_val, i)
        if interpretations:
            analysis.append(f"  Byte[{i:2d}] = 0x{byte_val:02x} ({byte_val:3d}) | {', '.join(interpretations[:2])}")
        else:
            analysis.append(f"  Byte[{i:2d}] = 0x{byte_val:02x} ({byte_val:3d})")

    # Pattern analysis
    analysis.append("\n  🔍 PATTERN ANALYSIS:")
    analysis.append("  " + "-" * 56)

    # 16-bit little-endian values
    if len(data_bytes) >= 2:
        for i in range(len(data_bytes) - 1):
            val_le = struct.unpack('<H', bytes(data_bytes[i:i+2]))[0]
            val_be = struct.unpack('>H', bytes(data_bytes[i:i+2]))[0]
            if 0 <= val_le <= 65535:
                analysis.append(f"  Bytes[{i}-{i+1}] LE: {val_le} | BE: {val_be}")
                if 0 <= val_le <= 100:
                    analysis.append(f"    → Possible battery (LE): {val_le}%")

    # 32-bit values
    if len(data_bytes) >= 4:
        for i in range(len(data_bytes) - 3):
            val_le = struct.unpack('<I', bytes(data_bytes[i:i+4]))[0]
            if val_le < 1000000:  # Reasonable values
                analysis.append(f"  Bytes[{i}-{i+3}] LE: {val_le}")

    # Comparison with previous data
    if last_data and len(data_bytes) == len(last_data):
        analysis.append("\n  🔄 COMPARISON WITH PREVIOUS DATA:")
        analysis.append("  " + "-" * 56)
        changes = []
        for i, (curr, prev) in enumerate(zip(data_bytes, last_data)):
            if curr != prev:
                changes.append(f"Byte[{i}]: {prev:3d} → {curr:3d} (Δ{curr-prev:+d})")
        if changes:
            for change in changes[:10]:  # Limit to 10 changes
                analysis.append(f"  {change}")
        else:
            analysis.append("  (No change detected)")

    # Common HID structure analysis
    analysis.append("\n  🎯 HID INTERPRETATIONS:")
    analysis.append("  " + "-" * 56)

    # Report ID (usually first byte)
    if len(data_bytes) > 0:
        if data_bytes[0] > 0:
            analysis.append(f"  Report ID: 0x{data_bytes[0]:02x} ({data_bytes[0]})")

    # Possible battery fields
    battery_candidates = []
    for i, byte_val in enumerate(data_bytes):
        if 0 <= byte_val <= 100:
            battery_candidates.append((i, byte_val))

    if battery_candidates:
        analysis.append(f"  ⚡ Battery candidates found:")
        for pos, val in battery_candidates:
            analysis.append(f"    Position {pos}: {val}%")
    else:
        analysis.append("  ⚡ No obvious battery candidate (0-100)")

    # Sequence analysis
    if len(data_bytes) >= 3:
        # Looks for increasing/decreasing sequences
        sequences = []
        for i in range(len(data_bytes) - 2):
            seq = data_bytes[i:i+3]
            if seq[0] < seq[1] < seq[2]:
                sequences.append(f"Bytes[{i}-{i+2}]: Increasing {seq}")
            elif seq[0] > seq[1] > seq[2]:
                sequences.append(f"Bytes[{i}-{i+2}]: Decreasing {seq}")
        if sequences:
            analysis.append("\n  📈 SEQUENCES DETECTED:")
            for seq in sequences[:3]:
                analysis.append(f"  {seq}")

    return "\n".join(analysis)


def read_with_pyusb_fallback():
    """Fallback using pyusb if hidraw fails"""
    try:
        import usb.core
        import usb.util

        VENDOR_ID = 0x0ecb
        PRODUCT_IDS = [0x2088, 0x205c]  # 910, 610

        device = None
        for pid in PRODUCT_IDS:
            device = usb.core.find(idVendor=VENDOR_ID, idProduct=pid)
            if device:
                break
        
        if device is None:
            return False

        try:
            if device.is_kernel_driver_active(3):
                device.detach_kernel_driver(3)
        except Exception:
            pass

        usb.util.claim_interface(device, 3)
        endpoint = device[0][(3, 0)][0]

        print("✓ Using pyusb (hidraw fallback)")
        print("Monitoring communication...\n")

        while True:
            try:
                data = device.read(endpoint.bEndpointAddress, endpoint.wMaxPacketSize, 1000)
                data_bytes = list(data)

                if data_bytes:
                    hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                    timestamp = time.strftime('%H:%M:%S')
                    print(f"[{timestamp}] Data ({len(data_bytes)} bytes): {hex_data}")

                    if len(data_bytes) >= 2 and data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                        print(f"  ⚡⚡⚡ BATTERY: {data_bytes[1]}% ⚡⚡⚡")
                    print()
            except usb.core.USBError as e:
                if e.errno != 110:  # Not a timeout
                    break
            time.sleep(0.1)

        usb.util.release_interface(device, 3)
        return True
    except Exception:
        return False


def read_hidraw(save_log=False):
    """Reads data from hidraw device"""
    print("JBL Quantum - Complete Data Monitor via HIDRAW")
    print("=" * 60)

    if HIDRAW_DEVICE:
        print(f"Device: {HIDRAW_DEVICE}")
    else:
        print("Device: (not found, using pyusb)")
    print()

    if HIDRAW_DEVICE and os.path.exists(HIDRAW_DEVICE):
        if not check_permissions():
            if USE_PYUSB_FALLBACK:
                print("Trying to use pyusb as fallback...\n")
                if read_with_pyusb_fallback():
                    return
            sys.exit(1)
    else:
        if USE_PYUSB_FALLBACK:
            print("Hidraw not found, using pyusb...\n")
            if read_with_pyusb_fallback():
                return
        print("Error: Hidraw not found and pyusb fallback not available")
        sys.exit(1)

    log_file = None
    if save_log:
        log_filename = f"/tmp/jbl_battery_log_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')
        print(f"💾 Saving log to: {log_filename}")
        print()

    print("Monitoring ALL received data...")
    print("Press Ctrl+C to stop\n")

    battery_level = None
    last_data = None
    packet_count = 0
    all_packets = []  # Stores all packets for analysis

    def log_output(text):
        """Writes to console and log file"""
        print(text, end='')
        if log_file:
            log_file.write(text)
            log_file.flush()

    try:
        with open(HIDRAW_DEVICE, 'rb') as f:
            print("Waiting for device data...")
            print("(Try using the headset - play audio, adjust volume, etc.)\n")
            print("=" * 60)

            while True:
                try:
                    # Reads data (max 64 bytes, per wMaxPacketSize)
                    data = f.read(64)

                    if data:
                        data_bytes = list(data)
                        packet_count += 1

                        # Ignores consecutive duplicate data (but shows it was received)
                        if data_bytes == last_data:
                            time.sleep(0.1)
                            continue

                        timestamp = time.strftime('%H:%M:%S.%f')[:-3]
                        all_packets.append((timestamp, data_bytes.copy()))

                        # ========== COMPLETE DATA DISPLAY ==========
                        output = []
                        output.append(f"\n{'='*60}\n")
                        output.append(f"📦 PACKET #{packet_count} - {timestamp}\n")
                        output.append(f"{'='*60}\n")
                        output.append(f"Size: {len(data_bytes)} bytes\n")
                        output.append("\n")

                        # Hexadecimal format with spacing
                        output.append("🔢 DATA IN HEXADECIMAL:\n")
                        output.append("  " + " ".join([f"{b:02x}" for b in data_bytes]) + "\n")
                        output.append("\n")

                        # Formatted hexadecimal (8 bytes per line)
                        output.append("🔢 FORMATTED HEXADECIMAL (8 bytes/line):\n")
                        for i in range(0, len(data_bytes), 8):
                            chunk = data_bytes[i:i+8]
                            hex_chunk = " ".join([f"{b:02x}" for b in chunk])
                            offset = f"{i:02d}"
                            output.append(f"  [{offset}] {hex_chunk}\n")
                        output.append("\n")

                        # Decimal format
                        output.append("🔢 DATA IN DECIMAL:\n")
                        output.append("  " + " ".join([f"{b:3d}" for b in data_bytes]) + "\n")
                        output.append("\n")

                        # Detailed table byte by byte
                        output.append("📋 DETAILED TABLE (Byte | Hex | Dec | Bin | ASCII):\n")
                        output.append("  " + "-" * 56 + "\n")
                        for i, byte_val in enumerate(data_bytes):
                            hex_str = f"0x{byte_val:02x}"
                            dec_str = f"{byte_val:3d}"
                            bin_str = format(byte_val, '08b')
                            ascii_str = chr(byte_val) if 32 <= byte_val <= 126 else '.'
                            output.append(f"  [{i:2d}] {hex_str:4s} | {dec_str:3s} | {bin_str} | '{ascii_str}'\n")
                        output.append("\n")

                        # Detailed analysis
                        analysis = analyze_data(data_bytes, last_data)
                        output.append(analysis)
                        output.append("\n\n")

                        # Tries to identify battery
                        found_battery = False
                        for i, byte_val in enumerate(data_bytes):
                            if 0 <= byte_val <= 100:
                                if battery_level != byte_val:
                                    battery_level = byte_val
                                    found_battery = True
                                    output.append(f"  ⚡⚡⚡ BATTERY LEVEL DETECTED: {battery_level}% (byte {i}) ⚡⚡⚡\n")

                        if not found_battery:
                            output.append("  ⚠ No obvious battery value detected in this packet\n")

                        output.append(f"{'='*60}\n\n")

                        # Display all
                        output_text = "".join(output)
                        log_output(output_text)

                        last_data = data_bytes

                    time.sleep(0.1)

                except BlockingIOError:
                    # No data available
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Error reading: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)

    except PermissionError:
        print(f"Error: No permission to read {HIDRAW_DEVICE}")
        print("Run as root or adjust permissions")
        sys.exit(1)
    except KeyboardInterrupt:
        summary = []
        summary.append("\n\n" + "=" * 60 + "\n")
        summary.append("📊 SESSION SUMMARY\n")
        summary.append("=" * 60 + "\n")
        summary.append(f"Total packets received: {packet_count}\n")
        if battery_level is not None:
            summary.append(f"⚡ Last battery level detected: {battery_level}%\n")
        else:
            summary.append("⚠ No battery level was detected automatically\n")

        # Analysis of all unique packets
        if all_packets:
            unique_packets = {}
            for ts, data in all_packets:
                data_str = " ".join([f"{b:02x}" for b in data])
                if data_str not in unique_packets:
                    unique_packets[data_str] = (ts, data)
            summary.append(f"Unique packets: {len(unique_packets)} of {packet_count}\n")

        summary.append("\n💡 Tip: Analyze the raw data above to identify patterns\n")
        if log_file:
            summary.append(f"💾 Complete log saved in: {log_file.name}\n")
        summary.append("=" * 60 + "\n")

        log_output("".join(summary))

        if log_file:
            log_file.close()
            print(f"\n💾 Log saved in: {log_file.name}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='JBL Quantum910 battery monitor')
    parser.add_argument('--log', '-l', action='store_true',
                        help='Save complete log to file')
    args = parser.parse_args()

    # Tries hidraw first, then pyusb as fallback
    try:
        read_hidraw(save_log=args.log)
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"\n⚠ Error with hidraw: {e}")
        if USE_PYUSB_FALLBACK:
            print("Trying to use pyusb as fallback...\n")
            if not read_with_pyusb_fallback():
                print("✗ Could not use any method")
                sys.exit(1)
        else:
            raise
