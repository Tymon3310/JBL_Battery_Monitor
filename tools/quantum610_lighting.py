#!/usr/bin/env python3
"""
JBL Quantum 610 lighting control (HIDV1, from QuantumENGINE RE).

Wire format (Feature reports, Pack=1, report ID first):
  GET  0x4A [4A]            -> [4A, on/off]            lighting state
  SET  0x4B [4B, on/off]                               on=1 off=0
  SET  0x4D [4D,grp,kf,R,G,B,fx,seg] (8B)              key frame
    fx: 0 breathing 1 solid 2 wave 3 glitch 4 spin-cw 5 spin-ccw 6 rise
    grp: 0 DEFAULT_LOGO (earcup logos)
  SET  0x4C [4C,grp,speed,count] (4B)                  animation
    speed in {100,75,50,25}
Ref: decompiled JBLQuantumControl: LightingKeyFrameProp(77), LightingAnimationProp(76),
     HIDV1LightingStateProp(74,75,7), LIGHTING_KEY_FRAME/LIGHTING_ANIMATION structs.

SET_REPORT Feature: bmRequestType 0x21, bRequest 0x09, wValue 0x03xx.
"""
from __future__ import annotations
import argparse, time

VENDOR_ID = 0x0ECB
PRODUCT_ID = 0x205C
IFACE = 5

FX = {"breathing": 0, "solid": 1, "wave": 2, "glitch": 3,
      "spin_cw": 4, "spin_ccw": 5, "rise": 6}


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


def feat_get(dev, rid: int, length: int, timeout=500) -> bytes | None:
    try:
        return bytes(dev.ctrl_transfer(0xA1, 0x01, 0x0300 | rid, IFACE, length, timeout=timeout))
    except Exception as e:
        print(f"GET 0x{rid:02x} ERR {str(e)[:80]}")
        return None


def feat_set(dev, rid: int, payload: bytes, timeout=500) -> bool:
    try:
        dev.ctrl_transfer(0x21, 0x09, 0x0300 | rid, IFACE, bytes([rid]) + bytes(payload), timeout=timeout)
        return True
    except Exception as e:
        print(f"SET 0x{rid:02x} ERR {str(e)[:80]}")
        return False


def wheel(n: int) -> tuple[int, int, int]:
    """Constant-brightness hue wheel (0-359 -> R,G,B), full saturation/value."""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((n % 360) / 360.0, 1.0, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


FACTORY_FRAMES = [  # Q600-series "SOUND IS SURVIVAL" (Q610 default)
    (0, 51, 255, 204, 2, 0), (1, 51, 255, 204, 2, 2), (2, 255, 0, 204, 2, 4),
    (3, 51, 255, 204, 2, 6), (4, 51, 255, 204, 2, 8),
]


PRESETS = {
    # name: (speed, [(kfID, R, G, B, fx, seg)])
    "survival": (100, [(0, 51, 255, 204, 2, 0), (1, 51, 255, 204, 2, 2), (2, 255, 0, 204, 2, 4),
                       (3, 51, 255, 204, 2, 6), (4, 51, 255, 204, 2, 8)]),  # SOUND IS SURVIVAL (factory)
    "dystopia": (100, [(0, 255, 25, 0, 0, 0), (1, 255, 127, 0, 0, 5)]),      # DYSTOPIA, breathing orange
    "sniper": (100, [(0, 77, 128, 0, 0, 0), (1, 0, 0, 0, 0, 4), (2, 0, 128, 73, 0, 7)]),  # SNIPER
    "spectrum": (60, [(0, 30, 255, 0, 0, 0), (1, 255, 0, 0, 0, 2), (2, 191, 0, 134, 0, 4),
                      (3, 51, 0, 255, 0, 6), (4, 0, 255, 255, 0, 8)]),       # SPECTRUM, breathing rainbow
}


EFFECTS = ["solid", "breathing", "wave", "glitch", "spin_cw", "spin_ccw", "rise"]
# SAFE on 610 logo (verified live): solid, breathing, wave, glitch.
# TOXIC: spin_cw + spin_ccw crash firmware; rise blanks logo + mutes audio (2026-10-12).
SAFE_EFFECTS = ["solid", "breathing", "wave", "glitch"]


def apply_frames(dev, speed: int, frames):
    import time
    feat_set(dev, 0x4B, bytes([0]))
    time.sleep(1)
    feat_set(dev, 0x4C, bytes([0, speed, len(frames)]))
    time.sleep(0.3)
    for kf, r, g, b, fx, seg in frames:
        feat_set(dev, 0x4D, bytes([0, kf, r, g, b, fx, seg]))
        time.sleep(0.2)
    feat_set(dev, 0x4C, bytes([0, speed, len(frames)]))
    time.sleep(0.5)
    feat_set(dev, 0x4B, bytes([1]))


def apply_preset(dev, name: str):
    speed, frames = PRESETS[name]
    apply_frames(dev, speed, frames)
    print(f"preset '{name}' applied.")


def restore_factory(dev):
    import time
    feat_set(dev, 0x4B, bytes([0]))
    time.sleep(1)
    feat_set(dev, 0x4C, bytes([0, 100, 5]))
    time.sleep(0.3)
    for kf, r, g, b, fx, seg in FACTORY_FRAMES:
        feat_set(dev, 0x4D, bytes([0, kf, r, g, b, fx, seg]))
        time.sleep(0.2)
    feat_set(dev, 0x4C, bytes([0, 100, 5]))
    time.sleep(0.5)
    feat_set(dev, 0x4B, bytes([1]))
    print("factory preset restored.")


def cycle(dev, interval=0.15, duration=0.0):
    import time
    print(f"Software spectrum: SOLID hue steps every {interval}s. Ctrl+C stops.")
    t0 = time.time()
    hue = 0
    try:
        while True:
            r, g, b = wheel(hue)
            feat_set(dev, 0x4D, bytes([0, 0, r, g, b, 1, 0]))  # SOLID
            feat_set(dev, 0x4C, bytes([0, 100, 1]))
            hue = (hue + 6) % 360
            time.sleep(interval)
            if duration and time.time() - t0 >= duration:
                break
    except KeyboardInterrupt:
        print("\nstopped.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", action="store_true", help="GET 0x4A lighting on/off")
    ap.add_argument("--on", action="store_true", help="SET 0x4B on")
    ap.add_argument("--off", action="store_true", help="SET 0x4B off")
    ap.add_argument("--keyframe", nargs=7, metavar=("GRP", "KF", "R", "G", "B", "FX", "SEG"),
                    help="SET 0x4D key frame (fx int 0-6 or name)")
    ap.add_argument("--anim", nargs=3, metavar=("GRP", "SPEED", "COUNT"), help="SET 0x4C animation")
    ap.add_argument("--get-anim", type=int, metavar="GRP", help="keyed GET 0x4C attempt (experimental)")
    ap.add_argument("--get-kf", type=int, metavar="GRP", help="keyed GET 0x4D attempt (experimental)")
    ap.add_argument("--cycle", action="store_true", help="software smooth-spectrum loop (SOLID hue steps)")
    ap.add_argument("--restore-factory", action="store_true", help="restore stock pulse")
    ap.add_argument("--preset", choices=sorted(PRESETS), help="apply stock preset")
    ap.add_argument("--demo-effects", action="store_true", help="tour all 7 effects, 10s each")
    ap.add_argument("--interval", type=float, default=0.15)
    ap.add_argument("--duration", type=float, default=0.0, help="cycle seconds, 0=infinite")
    a = ap.parse_args()

    dev = open_dev()
    if dev is None:
        return 1
    try:
        if a.state:
            d = feat_get(dev, 0x4A, 2)
            if d:
                print(f"state: {' '.join(f'{b:02x}' for b in d)} -> {'ON' if d[1] else 'OFF'}")
        if a.on:
            print("SET 0x4B on:", feat_set(dev, 0x4B, bytes([1])))
        if a.off:
            print("SET 0x4B off:", feat_set(dev, 0x4B, bytes([0])))
        if a.keyframe:
            g, k, r, gg, b, fx, seg = a.keyframe
            fxv = FX.get(str(fx).lower(), fx)
            payload = bytes([int(g), int(k), int(r), int(gg), int(b), int(fxv), int(seg)])
            print(f"SET 0x4D [{payload.hex(' ')}]:", feat_set(dev, 0x4D, payload))
        if a.anim:
            g, s, c = (int(x) for x in a.anim)
            print(f"SET 0x4C grp={g} speed={s} count={c}:", feat_set(dev, 0x4C, bytes([g, s, c])))
        if a.get_anim is not None:
            d = feat_get(dev, 0x4C, 4)
            if d:
                print(f"GET 0x4C: {' '.join(f'{b:02x}' for b in d)}")
        if a.get_kf is not None:
            d = feat_get(dev, 0x4D, 8)
            if d:
                print(f"GET 0x4D: {' '.join(f'{b:02x}' for b in d)}")
        if a.cycle:
            cycle(dev, a.interval, a.duration)
        if a.restore_factory:
            restore_factory(dev)
        if a.preset:
            apply_preset(dev, a.preset)
        if a.demo_effects:
            import time
            cols = [(128, 0, 255), (0, 255, 255), (255, 0, 128)]
            for fx in SAFE_EFFECTS:  # spin_cw crashes fw; spin_ccw/rise untested
                frames = [(i, r, g, b, FX[fx], i * 2) for i, (r, g, b) in enumerate(cols)]
                if fx == "solid":
                    frames = frames[:1]
                apply_frames(dev, 100, frames)
                print(f"effect '{fx}' showing 10s...", flush=True)
                time.sleep(10)
            print("demo done.")
    finally:
        close_dev(dev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
