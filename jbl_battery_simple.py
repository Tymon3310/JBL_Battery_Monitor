#!/usr/bin/env python3
"""
Simple JBL Quantum battery monitor using the shared core backend.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

from jbl_quantum_core import (
    get_jbl_device,
    parse_battery_from_packet,
    parse_mute_from_packet,
)


LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def log_print(*args, **kwargs):
    print(*args, **kwargs)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        pass
    try:
        log_path = os.path.join(LOG_DIR, "jbl_battery_simple.log")
        with open(log_path, "a", encoding="utf-8") as f:
            message = " ".join(str(arg) for arg in args) if args else ""
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def render_bar(percent: int) -> str:
    bar_length = 20
    filled = int((percent / 100) * bar_length)
    return "█" * filled + "░" * (bar_length - filled)


def monitor(prefer_pyusb: bool = False):
    log_print("JBL Quantum - Simple Battery Monitor")
    log_print("=" * 60)

    device = get_jbl_device(prefer_hidraw=not prefer_pyusb, prefer_pyusb=prefer_pyusb)
    if device is None:
        raise RuntimeError("Device not found or could not be opened.")

    log_print(f"✓ Connected to {device.product_name} via {type(device).__name__}")
    log_print("Monitoring... Press Ctrl+C to stop")
    log_print("=" * 60)

    last_battery = None
    last_mute = None
    last_link = None
    last_poll_time = 0.0
    update_count = 0
    is_610 = device.is_610

    try:
        while True:
            now = time.time()

            if now - last_poll_time >= 2.0:
                link = device.poll_link()
                if link is not None and link != last_link:
                    status = "CONNECTED" if link else "DISCONNECTED/OFF"
                    icon = "✅" if link else "❌"
                    log_print(f"[{time.strftime('%H:%M:%S')}] {icon} Headset Status: {status}")
                    last_link = link

                polled_battery = device.poll_battery()
                if polled_battery is not None:
                    battery, charging = polled_battery
                    if battery != last_battery:
                        charge_tag = " charging" if charging else ""
                        log_print(f"[{time.strftime('%H:%M:%S')}] ⚡ BATTERY: {battery}%{charge_tag}")
                        log_print(f"  [{render_bar(battery)}] {battery}%")
                        last_battery = battery
                        update_count += 1

                mute = device.poll_mute()
                if mute is not None and mute != last_mute:
                    icon = "🔇" if mute else "🎤"
                    state = "MUTED" if mute else "UNMUTED"
                    log_print(f"[{time.strftime('%H:%M:%S')}] {icon} MICROPHONE {state}")
                    last_mute = mute

                last_poll_time = now

            packet = device.read(timeout_ms=250)
            if packet:
                battery_data = parse_battery_from_packet(packet)
                if battery_data is not None and not is_610:
                    battery, charging = battery_data
                    if battery != last_battery:
                        charge_tag = " charging" if charging else ""
                        log_print(f"[{time.strftime('%H:%M:%S')}] ⚡ BATTERY: {battery}%{charge_tag}")
                        log_print(f"  [{render_bar(battery)}] {battery}%")
                        last_battery = battery
                        update_count += 1

                mute_data = parse_mute_from_packet(packet)
                if mute_data is not None:
                    if mute_data[0]:
                        mute = not bool(last_mute)
                    else:
                        mute = mute_data[1]
                    if mute != last_mute:
                        icon = "🔇" if mute else "🎤"
                        state = "MUTED" if mute else "UNMUTED"
                        log_print(f"[{time.strftime('%H:%M:%S')}] {icon} MICROPHONE {state}")
                        last_mute = mute

            time.sleep(0.05)
    except KeyboardInterrupt:
        log_print("\n" + "=" * 60)
        log_print("SUMMARY")
        log_print("=" * 60)
        if last_battery is not None:
            log_print(f"Last battery level: {last_battery}%")
            log_print(f"Total updates: {update_count}")
        else:
            log_print("No battery data received")
        log_print("=" * 60)
    finally:
        device.close()


def main():
    parser = argparse.ArgumentParser(description="Simple JBL Quantum battery monitor")
    parser.add_argument("--prefer-pyusb", action="store_true", help="Prefer PyUSB over hidraw")
    args = parser.parse_args()

    try:
        monitor(prefer_pyusb=args.prefer_pyusb)
    except Exception as e:
        log_print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
