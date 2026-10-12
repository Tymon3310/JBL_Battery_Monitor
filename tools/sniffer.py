#!/usr/bin/env python3
import usb.core
import usb.util
import sys
import time

def sniff():
    dev = usb.core.find(idVendor=0x0ecb, idProduct=0x205c)
    if not dev:
        print("Headset not found")
        return

    # Claim interface 5
    if dev.is_kernel_driver_active(5):
        dev.detach_kernel_driver(5)
    usb.util.claim_interface(dev, 5)
    
    # Find Interrupt IN endpoint
    cfg = dev.get_active_configuration()
    intf = usb.util.find_descriptor(cfg, bInterfaceNumber=5)
    ep = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)

    print("=== JBL Quantum 610 Sniffer ===")
    print(f"Listening on Interface 5, Endpoint {hex(ep.bEndpointAddress)}")
    print("Move Dials, Press Buttons, and Toggle RGB now...")
    print("Press Ctrl+C to stop\n")

    seen_patterns = {}

    try:
        while True:
            try:
                data = dev.read(ep.bEndpointAddress, ep.wMaxPacketSize, 100)
                if data:
                    pkt = list(data)
                    rid = pkt[0]
                    hex_str = " ".join(f"{b:02x}" for b in pkt)
                    
                    # Only print if the value changed for that Report ID
                    # or if it's a new Report ID
                    if seen_patterns.get(rid) != hex_str:
                        ts = time.strftime('%H:%M:%S')
                        print(f"[{ts}] ID 0x{rid:02x}: {hex_str}")
                        seen_patterns[rid] = hex_str
            except usb.core.USBError as e:
                if e.errno != 110: # Ignore timeouts
                    print(f"USB Error: {e}")
                    break
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        usb.util.release_interface(dev, 5)

if __name__ == "__main__":
    sniff()
