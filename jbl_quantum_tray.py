#!/usr/bin/env python3
"""
JBL Quantum - Tray & Background Monitor (Linux)
"""

from __future__ import annotations

import argparse
import os
import time
import threading
import subprocess
import logging
from datetime import datetime
from typing import Optional

from jbl_quantum_core import (
    get_jbl_device,
    parse_battery_from_packet,
    parse_mute_from_packet,
)


def _import_appindicator():
    try:
        import gi  # type: ignore
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, GLib  # type: ignore
        try:
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3 as AppIndicator  # type: ignore
        except Exception:
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AppIndicator  # type: ignore
        return Gtk, GLib, AppIndicator
    except Exception:
        return None, None, None

def _log(msg: str, level: int = logging.INFO) -> None:
    logging.log(level, msg)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if level >= logging.WARNING:
        print(f"[{ts}] {msg}", flush=True)


class BatteryTrayApp:
    def __init__(self, refresh_seconds: float, icon_mode: str, export: bool,
                 headless: bool, notifications: bool, swayosd: bool,
                 prefer_hidraw: bool = True, prefer_pyusb: bool = False, 
                 pyusb_detach_kernel: bool = False,
                 low_battery_threshold: int = 15,
                 full_battery_threshold: int = 100):
        
        self.refresh_seconds = max(0.1, refresh_seconds)
        self.icon_mode = icon_mode
        self.export_enabled = export
        self.headless = headless
        self.notifications = notifications
        self.swayosd = swayosd
        self.prefer_hidraw = prefer_hidraw
        self.prefer_pyusb = prefer_pyusb
        self.pyusb_detach_kernel = pyusb_detach_kernel
        self.low_battery_threshold = low_battery_threshold
        self.full_battery_threshold = full_battery_threshold
        
        self._setup_logging()

        if not self.headless:
            self.Gtk, self.GLib, self.AppIndicator = _import_appindicator()
            if self.Gtk is None:
                _log("Warning: UI dependencies not found. Falling back to --headless mode.", logging.WARNING)
                self.headless = True
        
        # Shared state
        self.current_percent: Optional[int] = None
        self.is_muted: bool = False
        self.is_charging: bool = False
        self.link_status: bool = False
        self.last_error: Optional[str] = None
        self.running = True
        self.product_name = "JBL Quantum"
        self.product_id: Optional[int] = None
        
        self._last_icon, self._last_label, self._last_tip = None, None, None
        self._last_logged_percent = None
        self._last_logged_mute = None
        self._last_logged_charging = None
        self._last_notified_link = None
        self._last_notified_battery = None 
        self._swayosd_icon = self._resolve_swayosd_icon()

        if self.export_enabled:
            uid = os.getuid()
            self.export_dir = f"/run/user/{uid}/jbl_quantum"
            try: os.makedirs(self.export_dir, exist_ok=True)
            except: pass

        if not self.headless:
            self.indicator = self.AppIndicator.Indicator.new("jbl-quantum-battery", "audio-headset-symbolic", self.AppIndicator.IndicatorCategory.HARDWARE)
            self.indicator.set_status(self.AppIndicator.IndicatorStatus.ACTIVE)
            self._setup_menu()
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        if not self.headless:
            self._render()
            self.GLib.timeout_add(int(self.refresh_seconds * 1000), self._tick)
        else:
            self._headless_loop()

    def _setup_logging(self):
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        try: os.makedirs(log_dir, exist_ok=True)
        except: log_dir = "/tmp"
        
        log_file = os.path.join(log_dir, "jbl_quantum_tray.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        _log(f"Started JBL Quantum Tray (Headless: {self.headless})")

    def _trigger_swayosd(self, muted: bool):
        if not self.swayosd: return
        try:
            msg = "Microphone Muted" if muted else "Microphone ON"
            cmd = ["swayosd-client", "--custom-message", msg]
            if self._swayosd_icon:
                cmd.extend(["--custom-icon", self._swayosd_icon[muted]])
            subprocess.run(cmd, capture_output=True)
        except: pass

    def _resolve_swayosd_icon(self):
        icon_names = {
            False: [
                "audio-input-microphone",
                "audio-input-microphone-symbolic",
                "audio-card",
                "audio-card-symbolic",
            ],
            True: [
                "microphone-sensitivity-muted",
                "microphone-sensitivity-muted-symbolic",
                "audio-input-microphone-muted",
                "audio-input-microphone-muted-symbolic",
                "audio-card",
                "audio-card-symbolic",
            ],
        }

        if self.headless or self.Gtk is None:
            return None

        try:
            theme = self.Gtk.IconTheme.get_default()
            if theme is None:
                return None
            resolved = {}
            for muted, candidates in icon_names.items():
                for name in candidates:
                    if theme.has_icon(name):
                        resolved[muted] = name
                        break
            if False in resolved and True in resolved:
                return resolved
        except Exception:
            pass
        return None

    def _setup_menu(self):
        self.menu = self.Gtk.Menu()
        self.status_item = self.Gtk.MenuItem(label="Status: Checking...")
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)
        self.battery_item = self.Gtk.MenuItem(label="Battery: --%")
        self.battery_item.set_sensitive(False)
        self.menu.append(self.battery_item)
        self.mic_item = self.Gtk.MenuItem(label="Mic: --")
        self.mic_item.set_sensitive(False)
        self.menu.append(self.mic_item)
        self.menu.append(self.Gtk.SeparatorMenuItem())
        item_quit = self.Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", lambda *_: self._quit())
        self.menu.append(item_quit)
        self.menu.show_all()
        self.indicator.set_menu(self.menu)

    def _headless_loop(self):
        try:
            while self.running:
                self._tick()
                time.sleep(self.refresh_seconds)
        except KeyboardInterrupt:
            self._quit()

    def _export_status(self):
        if not self.export_enabled: return
        try:
            def write_attr(name, val):
                with open(os.path.join(self.export_dir, name), "w") as f: f.write(str(val) + "\n")
            write_attr("capacity", self.current_percent if self.current_percent is not None else "--")
            write_attr("status", "Charging" if self.is_charging else ("Discharging" if self.link_status else "Unknown"))
            write_attr("present", "1" if self.link_status else "0")
            write_attr("model_name", self.product_name)
            write_attr("mic_muted", "1" if self.is_muted else "0")
            write_attr("mic_status", "MUTED" if self.is_muted else "ON")
            write_attr("battery_level", self.current_percent if self.current_percent is not None else "--")
            write_attr("connected", "1" if self.link_status else "0")
            write_attr("charging", "1" if self.is_charging else "0")
        except: pass

    def _send_notify(self, title: str, msg: str, icon: str = "audio-headset"):
        if not self.notifications: return
        try:
            subprocess.run(["notify-send", "-a", "JBL Quantum", "-i", icon, title, msg], capture_output=True)
        except: pass

    def _monitor_loop(self):
        device = None
        last_poll_time = 0
        
        while self.running:
            if not device:
                try:
                    _log("Searching for JBL device...", logging.DEBUG)
                    device = get_jbl_device(
                        prefer_hidraw=self.prefer_hidraw, 
                        prefer_pyusb=self.prefer_pyusb,
                        detach_kernel=self.pyusb_detach_kernel
                    )
                    if device:
                        self.product_name = device.product_name
                        self.product_id = device.product_id
                        _log(f"Connected to {self.product_name} via {type(device).__name__}")
                        
                        res = device.poll_battery()
                        if res:
                            self.current_percent, self.is_charging = res
                        mute_status = device.poll_mute()
                        if mute_status is not None:
                            self.is_muted = mute_status
                        
                        self.last_error = None
                    else: 
                        self.last_error = "Not found"
                        _log("No JBL device found, will retry in 2s...", logging.DEBUG)
                except Exception as e: 
                    self.last_error, device = str(e), None
                    _log(f"Connection error: {e}", logging.ERROR)
                
                if not device: 
                    self.link_status = False; self._export_status(); time.sleep(2); continue

            try:
                cur_t = time.time()
                # Poll periodically (especially for 610)
                if cur_t - last_poll_time > 2.0:
                    try:
                        link_status = device.poll_link()
                        if link_status is not None:
                            self.link_status = link_status
                            if self.link_status:
                                res = device.poll_battery()
                                if res:
                                    self.current_percent, self.is_charging = res
                                mute_status = device.poll_mute()
                                if mute_status is not None:
                                    self.is_muted = mute_status
                            else:
                                self.current_percent = None
                                self.is_charging = False
                    except Exception as e:
                        _log(f"Polling error: {e}", logging.DEBUG)
                        self.link_status = False
                    last_poll_time = cur_t

                # Read interrupt reports (910 battery and both 610/910 mute toggle)
                try:
                    data = device.read(timeout_ms=50)
                    if data:
                        # 910 sends battery updates via interrupt
                        res = parse_battery_from_packet(data)
                        if res: 
                            self.current_percent, self.is_charging = res
                        
                        # Both can send mute updates via interrupt
                        m = parse_mute_from_packet(data)
                        if m:
                            if m[0]: # Toggle
                                self.is_muted = not self.is_muted
                            else: # Absolute state
                                self.is_muted = m[1]
                except Exception as e:
                    _log(f"Read error: {e}", logging.DEBUG)
                
                time.sleep(0.01)
            except Exception as e:
                _log(f"Monitor loop error: {e}", logging.ERROR)
                self.last_error = str(e)
                try: device.close()
                except: pass
                device, self.link_status = None, False
                self._export_status()

    def _tick(self):
        if self.current_percent != self._last_logged_percent:
            if self.current_percent is not None:
                _log(f"Battery: {self.current_percent}%")
                if self.current_percent <= self.low_battery_threshold and self._last_notified_battery != 1:
                    self._send_notify("Battery Low", f"{self.product_name}: {self.current_percent}%", "battery-low")
                    self._last_notified_battery = 1
                elif self.current_percent >= self.full_battery_threshold and self._last_notified_battery != 2:
                    self._send_notify("Battery Full", f"{self.product_name}: {self.current_percent}%", "battery-full")
                    self._last_notified_battery = 2
                elif self.low_battery_threshold < self.current_percent < self.full_battery_threshold: 
                    self._last_notified_battery = 0
            self._last_logged_percent = self.current_percent; self._export_status()
            
        if self.is_muted != self._last_logged_mute:
            _log(f"Mute: {'🔇 MUTED' if self.is_muted else '🎤 ON'}")
            if self._last_logged_mute is not None:
                self._trigger_swayosd(self.is_muted)
            self._last_logged_mute = self.is_muted; self._export_status()

        if self.is_charging != self._last_logged_charging:
            _log(f"Charging: {self.is_charging}"); self._last_logged_charging = self.is_charging; self._export_status()
            
        if self.link_status != self._last_notified_link:
            if self.link_status:
                batt = f" ({self.current_percent}%)" if self.current_percent is not None else ""
                self._send_notify("Headset Online", f"{self.product_name} is connected{batt}.", "audio-headset")
            else:
                self._send_notify("Headset Offline", f"{self.product_name} turned off.", "audio-headset")
            self._last_notified_link = self.link_status; self._export_status()

        if not self.headless: self._render()
        return True

    def _render(self, force=False):
        percent, is_muted, charging, err = self.current_percent, self.is_muted, self.is_charging, self.last_error
        if is_muted: icon = "microphone-sensitivity-muted-symbolic"
        elif percent is None: icon = "audio-headset-symbolic"
        elif charging: icon = "battery-good-charging-symbolic"
        elif percent >= 80: icon = "battery-full-symbolic"
        elif percent >= 50: icon = "battery-good-symbolic"
        elif percent >= 20: icon = "battery-low-symbolic"
        else: icon = "battery-caution-symbolic"
        
        if percent is not None:
            char_sym = "⚡" if charging else ""
            label = f"{char_sym}{percent}%{' 🔇' if is_muted else ''}"
            status_txt, batt_txt = "CONNECTED", f"Battery: {percent}%"
        elif err == "Headset OFF":
            label = "OFF"; status_txt, batt_txt = "OFF", "Battery: --%"
        else:
            label = "--%"; status_txt, batt_txt = err or "Waiting...", "Battery: --%"

        if force or icon != self._last_icon: self.indicator.set_icon_full(icon, ""); self._last_icon = icon
        if force or label != self._last_label: self.indicator.set_label(label, "100% 🔇"); self._last_label = label
        self.status_item.set_label(f"Status: {status_txt}")
        self.battery_item.set_label(batt_txt)
        self.mic_item.set_label(f"Mic: {'🔇 MUTED' if is_muted else '🎤 ON'}")
        tip = f"JBL Quantum\nStatus: {status_txt}\nBattery: {batt_txt}\nMic: {'MUTED' if is_muted else 'ON'}"
        if force or tip != self._last_tip: self.indicator.set_title("JBL Quantum"); self._last_tip = tip

    def _quit(self):
        self.running = False
        if not self.headless: self.Gtk.main_quit()

    def run(self):
        if not self.headless:
            import signal
            signal.signal(signal.SIGINT, lambda *_: self._quit())
            signal.signal(signal.SIGTERM, lambda *_: self._quit())
            self.Gtk.main()
        else: self.monitor_thread.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JBL Quantum (910/610) Monitor")
    parser.add_argument("--refresh", type=float, default=0.2)
    parser.add_argument("--icon-mode", choices=["both", "battery", "mic"], default="both")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--notifications", action="store_true")
    parser.add_argument("--swayosd", action="store_true")
    parser.add_argument("--prefer-hidraw", action="store_true", default=True)
    parser.add_argument("--prefer-pyusb", action="store_true")
    parser.add_argument("--pyusb-detach-kernel", action="store_true")
    parser.add_argument("--low-battery", type=int, default=15)
    parser.add_argument("--full-battery", type=int, default=100)
    args = parser.parse_args()
    
    BatteryTrayApp(
        refresh_seconds=args.refresh, 
        icon_mode=args.icon_mode, 
        export=args.export, 
        headless=args.headless, 
        notifications=args.notifications, 
        swayosd=args.swayosd,
        prefer_hidraw=args.prefer_hidraw,
        prefer_pyusb=args.prefer_pyusb,
        pyusb_detach_kernel=args.pyusb_detach_kernel,
        low_battery_threshold=args.low_battery,
        full_battery_threshold=args.full_battery
    ).run()
