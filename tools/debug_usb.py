import usb.core
import usb.util
import sys

VENDOR_ID = 0x0ecb
PRODUCT_ID = 0x205c

dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

if dev is None:
    print("Device not found")
    sys.exit(1)

print(f"Found Device: {dev.idVendor:04x}:{dev.idProduct:04x}")

for cfg in dev:
    print(f"Configuration {cfg.bConfigurationValue}")
    for intf in cfg:
        print(f"  Interface {intf.bInterfaceNumber}, Alt {intf.bAlternateSetting}, Class {intf.bInterfaceClass}")
        for ep in intf:
            print(f"    Endpoint {ep.bEndpointAddress:02x}, Attr {ep.bmAttributes:02x}, Type {usb.util.endpoint_type(ep.bmAttributes)}, Dir {usb.util.endpoint_direction(ep.bEndpointAddress)}")
