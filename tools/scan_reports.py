import usb.core
import usb.util
import sys
import time

VENDOR_ID = 0x0ecb
PRODUCT_ID = 0x205c

dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

if dev is None:
    print("Device not found")
    sys.exit(1)

# Find HID interface
hid_iface = None
cfg = dev.get_active_configuration()
for intf in cfg:
    if intf.bInterfaceClass == 3:
        hid_iface = intf.bInterfaceNumber
        break

if hid_iface is None:
    print("HID Interface not found")
    sys.exit(1)

print(f"Testing GET_REPORT on interface {hid_iface}...")

try:
    if dev.is_kernel_driver_active(hid_iface):
        dev.detach_kernel_driver(hid_iface)
    usb.util.claim_interface(dev, hid_iface)
except Exception as e:
    print(f"Error claiming interface: {e}")
    sys.exit(1)

# bmRequestType: 0xa1 (Class, Interface, Device-to-host)
# bRequest: 0x01 (GET_REPORT)
# wValue: 0x03XX (Feature Report XX)
for rid in range(1, 256):
    try:
        # Try to get feature report
        data = dev.ctrl_transfer(0xa1, 0x01, 0x0300 | rid, hid_iface, 64, timeout=100)
        print(f"Report 0x{rid:02x} (Feature): {' '.join([f'{b:02x}' for b in data])}")
    except:
        pass

for rid in range(1, 256):
    try:
        # Try to get input report
        data = dev.ctrl_transfer(0xa1, 0x01, 0x0100 | rid, hid_iface, 64, timeout=100)
        print(f"Report 0x{rid:02x} (Input):   {' '.join([f'{b:02x}' for b in data])}")
    except:
        pass

usb.util.release_interface(dev, hid_iface)
