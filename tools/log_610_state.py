#!/usr/bin/env python3
"""
Long-running logger for JBL Quantum 610 state changes on interface 5.
"""

from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import usb.core
import usb.util


VENDOR_ID = 0x0ECB
PRODUCT_ID = 0x205C
INTERFACE = 5
REPORT_LEN = 64


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fmt_hex(data: bytes | None, limit: int = 24) -> str:
    if data is None:
        return ""
    return " ".join(f"{b:02x}" for b in data[:limit])


def find_and_claim():
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        return None, "device_not_found"
    try:
        usb.util.claim_interface(dev, INTERFACE)
        return dev, None
    except Exception as e:
        return None, f"claim_failed:{e}"


def safe_release(dev) -> None:
    if dev is None:
        return
    try:
        usb.util.release_interface(dev, INTERFACE)
    except Exception:
        pass


def read_report(dev, wvalue: int) -> bytes | None:
    try:
        return bytes(dev.ctrl_transfer(0xA1, 0x01, wvalue, INTERFACE, REPORT_LEN, timeout=500))
    except Exception:
        return None


def decode_bool(data: bytes | None, expected_rid: int) -> int | None:
    if not data or len(data) < 2 or data[0] != expected_rid:
        return None
    return data[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Log JBL Quantum 610 state changes over time")
    parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds")
    parser.add_argument("--output", default=None, help="CSV output path")
    args = parser.parse_args()

    output = Path(args.output) if args.output else Path(f"/tmp/jbl_610_log_{int(time.time())}.csv")
    print(f"Logging to {output}")

    last = {
        "present": None,
        "link": None,
        "mute": None,
        "battery": None,
        "legacy_7c": None,
        "power_50": None,
        "power_67": None,
        "power_68": None,
        "power_75": None,
        "raw_49": None,
        "raw_50": None,
        "raw_67": None,
        "raw_68": None,
        "raw_75": None,
        "raw_7c": None,
        "error": None,
    }

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "present", "link", "mute", "battery", "legacy_7c",
            "power_50", "power_67", "power_68", "power_75",
            "raw_49", "raw_50", "raw_67", "raw_68", "raw_75", "raw_7c",
            "error", "event"
        ])
        dev = None
        try:
            while True:
                if dev is None:
                    dev, err = find_and_claim()
                    if dev is None:
                        state = {
                            "present": 0,
                            "link": None,
                            "mute": None,
                            "battery": None,
                            "legacy_7c": None,
                            "power_50": None,
                            "power_67": None,
                            "power_68": None,
                            "power_75": None,
                            "raw_49": None,
                            "raw_50": None,
                            "raw_67": None,
                            "raw_68": None,
                            "raw_75": None,
                            "raw_7c": None,
                            "error": err,
                        }
                    else:
                        state = None
                else:
                    state = None

                if state is None:
                    raw_49 = read_report(dev, 0x0149)
                    raw_50 = read_report(dev, 0x0150)
                    raw_67 = read_report(dev, 0x0167)
                    raw_68 = read_report(dev, 0x0168)
                    raw_75 = read_report(dev, 0x0175)
                    raw_7c = read_report(dev, 0x037C)

                    if raw_49 is None and raw_50 is None and raw_67 is None and raw_68 is None and raw_75 is None and raw_7c is None:
                        safe_release(dev)
                        dev = None
                        state = {
                            "present": 0,
                            "link": None,
                            "mute": None,
                            "battery": None,
                            "legacy_7c": None,
                            "power_50": None,
                            "power_67": None,
                            "power_68": None,
                            "power_75": None,
                            "raw_49": None,
                            "raw_50": None,
                            "raw_67": None,
                            "raw_68": None,
                            "raw_75": None,
                            "raw_7c": None,
                            "error": "read_failed_or_disconnected",
                        }
                    else:
                        battery = None
                        legacy_7c = None
                        if raw_49 and len(raw_49) >= 2 and raw_49[0] == 0x49:
                            battery = raw_49[1]
                        if raw_7c and len(raw_7c) >= 2 and raw_7c[0] == 0x7C:
                            legacy_7c = raw_7c[1]
                        state = {
                            "present": 1,
                            "link": decode_bool(raw_68, 0x68),
                            "mute": decode_bool(raw_67, 0x67),
                            "battery": battery,
                            "legacy_7c": legacy_7c,
                            "power_50": raw_50[2] if raw_50 and len(raw_50) >= 3 and raw_50[0] == 0x50 else None,
                            "power_67": raw_67[2] if raw_67 and len(raw_67) >= 3 and raw_67[0] == 0x67 else None,
                            "power_68": raw_68[2] if raw_68 and len(raw_68) >= 3 and raw_68[0] == 0x68 else None,
                            "power_75": raw_75[2] if raw_75 and len(raw_75) >= 3 and raw_75[0] == 0x75 else None,
                            "raw_49": fmt_hex(raw_49),
                            "raw_50": fmt_hex(raw_50),
                            "raw_67": fmt_hex(raw_67),
                            "raw_68": fmt_hex(raw_68),
                            "raw_75": fmt_hex(raw_75),
                            "raw_7c": fmt_hex(raw_7c),
                            "error": None,
                        }

                changed_keys = [k for k, v in state.items() if last[k] != v]
                event = ",".join(changed_keys) if changed_keys else ""
                writer.writerow([
                    now(),
                    state["present"],
                    state["link"],
                    state["mute"],
                    state["battery"],
                    state["legacy_7c"],
                    state["power_50"],
                    state["power_67"],
                    state["power_68"],
                    state["power_75"],
                    state["raw_49"],
                    state["raw_50"],
                    state["raw_67"],
                    state["raw_68"],
                    state["raw_75"],
                    state["raw_7c"],
                    state["error"],
                    event,
                ])
                f.flush()

                if changed_keys:
                    summary = ", ".join(
                        f"{k}={state[k]}" for k in changed_keys
                        if k in ("present", "link", "mute", "battery", "legacy_7c", "power_50", "power_67", "power_68", "power_75", "error")
                    )
                    if not summary:
                        summary = event
                    print(f"[{now()}] {summary}")
                    last.update(state)

                time.sleep(max(0.5, args.interval))
        except KeyboardInterrupt:
            pass
        finally:
            safe_release(dev)

    print("Stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
