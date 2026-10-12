import usb.core
import usb.util
import sys
import time

VENDOR_ID = 0x0ecb
PRODUCT_ID = 0x205c
INTERFACE = 5
ENDPOINT = 0x83

dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

if dev is None:
    print("Device not found")
    sys.exit(1)

print(f"Found Device: {dev.idVendor:04x}:{dev.idProduct:04x}")

try:
    if dev.is_kernel_driver_active(INTERFACE):
        print(f"Detaching kernel driver for interface {INTERFACE}...")
        dev.detach_kernel_driver(INTERFACE)
    
    usb.util.claim_interface(dev, INTERFACE)
    print(f"Interface {INTERFACE} claimed successfully")
    
    print("Waiting for data (press buttons, adjust volume, or wait for periodic battery report)...")
    print("This will run for about 60 seconds.")
    for i in range(600):
        try:
            data = dev.read(ENDPOINT, 64, timeout=100)
            print(f"[{time.strftime('%H:%M:%S')}] Received: {' '.join([f'{b:02x}' for b in data])}")
        except usb.core.USBError as e:
            if e.errno == 110: # Timeout
                if i % 50 == 0: print(".", end="", flush=True)
            else:
                print(f"\nUSB Error: {e}")
        time.sleep(0.1)
    print("\nTest finished.")

finally:
    try:
        usb.util.release_interface(dev, INTERFACE)
        print("Interface released")
    except:
        pass
