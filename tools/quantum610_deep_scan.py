#!/usr/bin/env python3
"""
Deep scan for JBL Quantum 610 (0ecb:205c), interface 5 (HID).

Does (safely, with detach/reattach of iface 5 only):
 1. USB descriptor summary (interfaces / EP 0x83 wMaxPacketSize 16)
 2. HID report-descriptor parse (authoritative report-ID list)
 3. Validated GET_REPORT dump (exact lengths, first-byte must match;
     device returns floor-ID fallback for unimplemented IDs - filtered)
 4. Interrupt sniff on EP 0x83 + concurrent control polling,
     logging every change with timestamps to CSV.

Usage:
  python3 tools/quantum610_deep_scan.py [--poll-only] [--sniff 30] [--out /tmp/jbl610.json]
  python3 tools/quantum610_deep_scan.py --monitor --duration 120 --csv /tmp/jbl610.csv
      # then press buttons / mute / volume / game-chat dial / power-cycle
"""
from __future__ import annotations
import argparse, csv, json, sys, time
from datetime import datetime
from pathlib import Path

VENDOR_ID = 0x0ECB
PRODUCT_ID = 0x205C
IFACE = 5
EP_ADDR = 0x83

# payload lengths from HID report descriptor (excludes report-ID byte)
# 0x06 has Output 61 + Input 1; rest as parsed
PAYLOAD_LEN = {
    0x06: ("in/out", 1, 61),
    0x07: ("in", 1, None),
    0x08: ("in", 1, None),
    0x09: ("in", 1, None),
    0x10: ("in", 1, None),
    0x11: ("in", 1, None),
    0x12: ("in", 2, None),
    0x50: ("feat", 2, None),
    0x52: ("feat", 2, None),
    0x49: ("feat", 1, None),
    0x4A: ("feat", 1, None),
    0x4B: ("feat", 1, None),
    0x4C: ("feat", 3, None),
    0x4D: ("feat", 7, None),
    0x51: ("feat", 12, None),
    0x53: ("feat", 1, None),
    0x59: ("feat", 1, None),
    0x5A: ("feat", 16, None),
    0x5C: ("feat", 1, None),
    0x5D: ("feat", 1, None),
    0x60: ("feat", 1, None),
    0x61: ("feat", 16, None),
    0x62: ("feat", 1, None),
    0x67: ("feat", 1, None),
    0x68: ("feat", 1, None),
    0x69: ("feat", 1, None),
    0x75: ("feat", 1, None),
    0x76: ("feat", 1, None),
    0x7A: ("feat", 1, None),
    0x7B: ("feat", 1, None),
    0x7C: ("feat", 6, None),
    0x7D: ("feat", 1, None),
    0x7E: ("feat", 1, None),
    0x02: ("in", None, None),  # consumer, variable bitfields
    0x2F: ("in/out", 1, 8),     # telephony + LED, see descriptor
}

# control reports worth polling in monitor mode (implemented set, verified)
POLL_IDS = [0x49, 0x4A, 0x50, 0x51, 0x5C, 0x61, 0x62, 0x67, 0x68, 0x75, 0x7C, 0x2F]


def open_dev():
    import usb.core, usb.util
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        return None
    try:
        if dev.is_kernel_driver_active(IFACE):
            dev.detach_kernel_driver(IFACE)
    except Exception:
        pass
    try:
        usb.util.claim_interface(dev, IFACE)
    except Exception as e:
        print(f"claim iface {IFACE} failed: {e}", file=sys.stderr)
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


def get_report(dev, rid: int, rtype: int, length: int, timeout=300) -> bytes | None:
    try:
        return bytes(dev.ctrl_transfer(0xA1, 0x01, (rtype << 8) | rid, IFACE, length, timeout=timeout))
    except Exception:
        return None


def dump_reports(validated_only=True):
    import usb.util
    dev = open_dev()
    if dev is None:
        print("device not found / cannot claim")
        return {}
    out = {}
    # each RID tested in a fresh claim would be ideal, but one session + first-byte
    # validation is enough to separate implemented vs floor-fallback
    for rid, spec in sorted(PAYLOAD_LEN.items()):
        kind = spec[0]
        lens = []
        if rid == 0x06:
            lens = [2, 62]
        elif rid == 0x02:
            lens = [2, 4]
        elif rid == 0x2F:
            lens = [2, 9]
        else:
            plen = spec[1]
            lens = [plen + 1]
        for ln in lens:
            for rtype, rname in ((0x01, "input"), (0x03, "feature")):
                data = get_report(dev, rid, rtype, ln)
                if data is None:
                    res = {"ok": False, "error": "stall/timeout"}
                else:
                    ok = len(data) > 0 and data[0] == rid
                    res = {"ok": ok,
                           "len": len(data),
                           "hex": " ".join(f"{b:02x}" for b in data),
                           "fallback": (len(data) > 0 and data[0] != rid)}
                out.setdefault(f"0x{rid:02x}", {}).setdefault(f"{rname}:{ln}", res)
    close_dev(dev)
    if validated_only:
        print("Implemented control reports (first byte == requested ID):")
        for k, v in sorted(out.items()):
            for rk, r in v.items():
                if r.get("ok"):
                    print(f"  {k} {rk}: {r['hex']}")
                    break
    else:
        print(json.dumps(out, indent=2))
    return out


def monitor(duration=120, csv_path=None, poll_interval=1.0):
    import usb.core, usb.util
    dev = open_dev()
    if dev is None:
        print("device not found")
        return 1
    try:
        cfg = dev.get_active_configuration()
        intf = usb.util.find_descriptor(cfg, bInterfaceNumber=IFACE)
        ep = usb.util.find_descriptor(
            intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
        print(f"EP {hex(ep.bEndpointAddress)} maxPacket={ep.wMaxPacketSize}")
    except Exception as e:
        print(f"EP lookup failed: {e}")
        close_dev(dev)
        return 1

    # per-report exact lengths for polling
    req_len = {0x49: 2, 0x4A: 2, 0x50: 3, 0x51: 13, 0x5C: 2, 0x61: 17,
               0x62: 2, 0x67: 2, 0x68: 2, 0x75: 2, 0x7C: 7, 0x2F: 2}
    last = {}
    f = None
    wr = None
    if csv_path:
        f = open(csv_path, "w", newline="", encoding="utf-8")
        wr = csv.writer(f)
        wr.writerow(["t", "elapsed_s", "source", "report_id", "hex", "event"])
        f.flush()
    t0 = time.time()
    print(f"Monitoring {duration}s. DO NOW: mute on/off, volume wheel, "
          "game/chat dial min/mid/max, power off/on, plug/unplug, play audio.")
    try:
        while time.time() - t0 < duration:
            el = time.time() - t0
            # 1) interrupt
            try:
                data = bytes(dev.read(ep.bEndpointAddress, ep.wMaxPacketSize, 100))
                if data:
                    hx = " ".join(f"{b:02x}" for b in data)
                    key = ("irq", data[0], hx)
                    if last.get(("irq", data[0])) != hx:
                        print(f"[{el:6.1f}s] IRQ ID 0x{data[0]:02x} len={len(data)} {hx}")
                        if wr:
                            wr.writerow([datetime.now().isoformat(timespec="seconds"),
                                         f"{el:.1f}", "irq", f"0x{data[0]:02x}", hx, "change"])
                            f.flush()
                    last[("irq", data[0])] = hx
            except Exception:
                pass  # timeouts normal when idle
            # 2) polls at interval
            if el - last.get("_poll_t", -99) >= poll_interval:
                last["_poll_t"] = el
                for rid in POLL_IDS:
                    d = get_report(dev, rid, 0x01, req_len[rid], timeout=200)
                    if d is None or len(d) == 0 or d[0] != rid:
                        continue
                    hx = " ".join(f"{b:02x}" for b in d)
                    if last.get(rid) != hx:
                        if rid in last:
                            print(f"[{el:6.1f}s] POLL ID 0x{rid:02x}: {hx}")
                            if wr:
                                wr.writerow([datetime.now().isoformat(timespec="seconds"),
                                             f"{el:.1f}", "poll", f"0x{rid:02x}", hx, "change"])
                                f.flush()
                        last[rid] = hx
    except KeyboardInterrupt:
        print("stopped by user")
    finally:
        close_dev(dev)
        if f:
            f.close()
            print(f"CSV saved to {csv_path}")
    print("done. Unique IRQ IDs seen:", sorted([f"0x{k[1]:02x}" for k in last if isinstance(k, tuple) and k[0] == "irq"]))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poll-only", action="store_true")
    ap.add_argument("--monitor", action="store_true")
    ap.add_argument("--duration", type=float, default=120)
    ap.add_argument("--csv", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--interval", type=float, default=1.0)
    a = ap.parse_args()
    if a.monitor:
        csv_path = a.csv or f"/tmp/jbl610_{int(time.time())}.csv"
        return monitor(duration=a.duration, csv_path=csv_path, poll_interval=a.interval)
    out = dump_reports(validated_only=True)
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"saved {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
