#!/usr/bin/env python3
"""
Script to read JBL Quantum910 data without detaching the kernel driver.
Uses a more passive approach to monitor communication.
"""

import usb.core
import usb.util
import sys
import time
import struct

VENDOR_ID = 0x0ecb
PRODUCT_IDS = [0x2088, 0x205c]  # 910, 610


def find_device():
    """Finds the USB device"""
    device = None
    for pid in PRODUCT_IDS:
        device = usb.core.find(idVendor=VENDOR_ID, idProduct=pid)
        if device:
            break
    if device is None:
        raise ValueError("Device not found. Make sure the headset is connected.")
    return device


def get_device_info(device):
    """Gets device information"""
    print("=" * 60)
    print("Device Information")
    print("=" * 60)
    print(f"Vendor ID: 0x{device.idVendor:04x}")
    print(f"Product ID: 0x{device.idProduct:04x}")
    try:
        print(f"Manufacturer: {usb.util.get_string(device, device.iManufacturer)}")
    except Exception:
        print(f"Manufacturer: (not available)")
    try:
        print(f"Product: {usb.util.get_string(device, device.iProduct)}")
    except Exception:
        print(f"Product: (not available)")
    print()

    # HID interface information
    try:
        cfg = device.get_active_configuration()
        intf = cfg[(3, 0)]
        print(f"HID Interface: {intf.bInterfaceNumber}")
        print(f"Endpoints: {len(intf)}")
        for ep in intf:
            print(
                f"  - Endpoint 0x{ep.bEndpointAddress:02x}: "
                f"{'IN' if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else 'OUT'}, "
                f"Maximum size: {ep.wMaxPacketSize} bytes"
            )
    except Exception as e:
        print(f"Error getting interface information: {e}")
    print("=" * 60)
    print()


def try_read_without_claim(device):
    """Tries to read data without claiming the interface"""
    print("Trying to read data without detaching driver...")
    print("(May need to be run as root)")
    print()

    try:
        # Tries to access the endpoint directly
        cfg = device.get_active_configuration()
        intf = cfg[(3, 0)]
        endpoint = intf[0]  # First endpoint (usually the IN)

        print(f"Endpoint: 0x{endpoint.bEndpointAddress:02x}")
        print(f"Maximum size: {endpoint.wMaxPacketSize} bytes")
        print()
        print("Monitoring... (Press Ctrl+C to stop)")
        print()

        battery_level = None

        for i in range(100):  # Tries to read 100 times
            try:
                # Tries to read with short timeout
                data = device.read(endpoint.bEndpointAddress, endpoint.wMaxPacketSize, 100)
                data_bytes = list(data)

                hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                print(f"[{time.strftime('%H:%M:%S')}] Data ({len(data_bytes)} bytes): {hex_data}")
                print(f"  Bytes: {data_bytes}")

                # Tries to interpret battery
                for j, byte in enumerate(data_bytes):
                    if 0 <= byte <= 100:
                        if battery_level != byte:
                            battery_level = byte
                            print(f"  ⚡ Battery level: {battery_level}% (position {j})")

                if len(data_bytes) >= 2:
                    val_16 = struct.unpack('<H', bytes(data_bytes[:2]))[0]
                    if 0 <= val_16 <= 100 and battery_level != val_16:
                        battery_level = val_16
                        print(f"  ⚡ Battery level (16-bit): {battery_level}%")

                print()

            except usb.core.USBError as e:
                if e.errno == 110:  # ETIMEDOUT
                    if i % 10 == 0:
                        print(f"[{time.strftime('%H:%M:%S')}] Waiting for data... (attempt {i+1})")
                elif e.errno == 13:  # Permission denied
                    print(f"Permission error: {e}")
                    print("Try running as root: sudo python3 jbl_battery_readonly.py")
                    break
                else:
                    print(f"USB Error: {e}")

            time.sleep(0.5)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("JBL Quantum - Battery Monitor (Read-Only Mode)")
    print("=" * 60)
    print()

    try:
        device = find_device()
        get_device_info(device)
        try_read_without_claim(device)

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
