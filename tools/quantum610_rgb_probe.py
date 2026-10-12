#!/usr/bin/env python3
"""
Blind RGB/output probe for JBL Quantum 610 (0ecb:205c), iface 5.

Two stages:
 1. --test-led : safe Output 0x2F (mute LED, 8B payload) on/off.
    Reversible, kernel also drives this LED via input194::mute.
 2. --walk06   : single-byte walk over Output 0x06 (61B payload).
    Sends base(zeros) with byte[off]=val, one probe per --step seconds.
    User watches the earcup logo glow and notes which probe # changed it.
    WARNING: 0x06 is the vendor config channel (EQ/RGB/sidetone?) — a probe
    may also alter audio settings. Restore via QuantumENGINE defaults.

SET_REPORT Output: bmRequestType 0x21, bRequest 0x09, wValue 0x02xx.
"""
from __future__ import annotations
import argparse, sys, time

VENDOR_ID = 0x0ECB
PRODUCT_ID = 0x205C
IFACE = 5


def open_dev():
    import usb.core, usb.util
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("device not found")
        return None
    try:
        if dev.is_kernel_driver_active(IFACE):
            dev.detach_kernel_driver(IFACE)
    except Exception as e:
        print(f"detach note: {e}")
    try:
        usb.util.claim_interface(dev, IFACE)
    except Exception as e:
        print(f"claim failed: {e}")
        return None
    return dev


def close_dev(dev):
    import usb.util
    try:
        usb.util.release_interface(dev, IFACE)
    except Exception:
        pass
    try:
        dev.attach_kernel_driver(IFACE)
    except Exception:
        pass


def set_output(dev, rid: int, payload: bytes, timeout=500) -> bool:
    try:
        dev.ctrl_transfer(0x21, 0x09, 0x0200 | rid, IFACE, bytes([rid]) + bytes(payload), timeout=timeout)
        return True
    except Exception as e:
        print(f"    SET 0x{rid:02x} ERR {str(e)[:100]}")
        return False


def test_led():
    dev = open_dev()
    if dev is None:
        return 1
    try:
        print("Output 0x2F = mic mute LED (boom LED). Watch it.")
        print("[1/4] all-zero ...")
        set_output(dev, 0x2F, bytes(8))
        time.sleep(3)
        print("[2/4] byte0=0x3f ...")
        set_output(dev, 0x2F, bytes([0x3F] + [0] * 7))
        time.sleep(3)
        print("[3/4] all-ones ...")
        set_output(dev, 0x2F, bytes([0xFF] * 8))
        time.sleep(3)
        print("[4/4] restore all-zero ...")
        set_output(dev, 0x2F, bytes(8))
        print("done. Tell me which step (if any) lit/changed the mic LED.")
    finally:
        close_dev(dev)
    return 0


def walk06(start=0, end=61, val=0x01, step=3.0, base=None):
    dev = open_dev()
    if dev is None:
        return 1
    try:
        print(f"Walking Output 0x06 bytes {start}..{end-1} = 0x{val:02x}, {step}s apart.")
        print("Watch the EAR CUP LOGO glow. Note probe numbers that change it.")
        print("Also report any audio change (EQ/volume/sidetone). Ctrl+C aborts.")
        time.sleep(2)
        n = 0
        t_start = time.time()
        print(f"t=0s wall={time.strftime('%H:%M:%S')}")
        for off in range(start, end):
            payload = bytearray(base or bytes(61))
            payload[off] = val
            ok = set_output(dev, 0x06, bytes(payload))
            el = time.time() - t_start
            print(f"  probe #{n}: byte[{off}] = 0x{val:02x} {'sent' if ok else 'FAILED'} (t={el:.0f}s wall={time.strftime('%H:%M:%S')})")
            sys.stdout.flush()
            n += 1
            time.sleep(step)
        print("walk done. Restoring zeros.")
        set_output(dev, 0x06, bytes(base or bytes(61)))
    except KeyboardInterrupt:
        print("\naborted, restoring zeros.")
        try:
            set_output(dev, 0x06, bytes(61))
        except Exception:
            pass
    finally:
        close_dev(dev)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-led", action="store_true")
    ap.add_argument("--walk06", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=61)
    ap.add_argument("--val", type=lambda s: int(s, 0), default=0x01)
    ap.add_argument("--step", type=float, default=3.0)
    a = ap.parse_args()
    if a.test_led:
        return test_led()
    if a.walk06:
        return walk06(a.start, a.end, a.val, a.step)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
