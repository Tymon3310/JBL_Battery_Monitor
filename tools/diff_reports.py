#!/usr/bin/env python3
"""
Snapshot and diff JBL Quantum 610 control-report replies on interface 5.
"""

from __future__ import annotations

import argparse
import time

import usb.core
import usb.util


VENDOR_ID = 0x0ECB
PRODUCT_ID = 0x205C
INTERFACE = 5
REPORT_LEN = 64


def read_space(device, base: int) -> dict[int, bytes]:
    out: dict[int, bytes] = {}
    for rid in range(1, 256):
        try:
            data = bytes(device.ctrl_transfer(0xA1, 0x01, base | rid, INTERFACE, REPORT_LEN, timeout=150))
        except Exception:
            continue
        out[rid] = data
    return out


def snapshot(device) -> dict[str, dict[int, bytes]]:
    return {
        "input": read_space(device, 0x0100),
        "feature": read_space(device, 0x0300),
    }


def fmt_hex(data: bytes, limit: int) -> str:
    return " ".join(f"{b:02x}" for b in data[:limit])


def print_group_summary(name: str, reports: dict[int, bytes], limit: int) -> None:
    grouped: dict[bytes, list[int]] = {}
    for rid, data in reports.items():
        grouped.setdefault(data[:24], []).append(rid)

    print(f"{name} groups: {len(grouped)}")
    for payload, ids in sorted(grouped.items(), key=lambda item: (item[0], item[1][0])):
        label = ",".join(f"0x{rid:02x}" for rid in ids[:12])
        suffix = "..." if len(ids) > 12 else ""
        print(f"  ids={label}{suffix} data={fmt_hex(payload, limit)}")


def print_diff(before: dict[int, bytes], after: dict[int, bytes], name: str, limit: int) -> None:
    changed = 0
    all_ids = sorted(set(before) | set(after))
    for rid in all_ids:
        b = before.get(rid)
        a = after.get(rid)
        if b == a:
            continue
        changed += 1
        print(f"{name} 0x{rid:02x}")
        if b is None:
            print(f"  before: <missing>")
            print(f"  after : {fmt_hex(a or b'', limit)}")
            continue
        if a is None:
            print(f"  before: {fmt_hex(b, limit)}")
            print(f"  after : <missing>")
            continue
        print(f"  before: {fmt_hex(b, limit)}")
        print(f"  after : {fmt_hex(a, limit)}")
        byte_changes = []
        for i, (bv, av) in enumerate(zip(b, a)):
            if bv != av:
                byte_changes.append(f"{i}:{bv:02x}->{av:02x}")
        if len(a) != len(b):
            byte_changes.append(f"len:{len(b)}->{len(a)}")
        print(f"  diff  : {' '.join(byte_changes[:32])}")
    if changed == 0:
        print(f"{name}: no changes")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff JBL Quantum 610 control-report snapshots")
    parser.add_argument("--wait", type=float, default=8.0, help="Seconds to wait between snapshots")
    parser.add_argument("--limit", type=int, default=24, help="Bytes to print per report")
    args = parser.parse_args()

    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("Device not found")
        return 1

    usb.util.claim_interface(dev, INTERFACE)
    try:
        print("Capturing baseline snapshot...")
        first = snapshot(dev)
        print_group_summary("input", first["input"], args.limit)
        print_group_summary("feature", first["feature"], args.limit)
        print()
        print(f"Now perform one action within {args.wait:.1f}s: mute, volume wheel, power, reconnect, etc.")
        time.sleep(args.wait)
        print("Capturing second snapshot...")
        second = snapshot(dev)
    finally:
        usb.util.release_interface(dev, INTERFACE)

    print()
    print("Diff")
    print("----")
    print_diff(first["input"], second["input"], "input", args.limit)
    print_diff(first["feature"], second["feature"], "feature", args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
