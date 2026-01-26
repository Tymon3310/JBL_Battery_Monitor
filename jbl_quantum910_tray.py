#!/usr/bin/env python3
"""
JBL Quantum910 - Tray Battery Monitor (Linux)

- Shows headset battery percentage in the system tray (AppIndicator).
- Reads battery primarily via hidraw (least intrusive).
- Falls back to pyusb if hidraw is unavailable.

Battery format confirmed in this repo:
  [Report ID, Battery%] => 0x08 <0..100>
"""

from __future__ import annotations

import argparse
import errno
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


VENDOR_ID_HEX = "0ecb"
PRODUCT_ID_HEX = "2088"
VENDOR_ID = int(VENDOR_ID_HEX, 16)
PRODUCT_ID = int(PRODUCT_ID_HEX, 16)


def _import_appindicator():
    """
    AppIndicator naming varies by distro:
    - Ubuntu/Debian often provide AppIndicator3
    - Some distros provide AyatanaAppIndicator3
    """
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
    except Exception as e:
        print("Erro: dependências do tray não encontradas (PyGObject/AppIndicator).", file=sys.stderr)
        print(f"Detalhe: {e}", file=sys.stderr)
        print("\nPython em uso:", file=sys.stderr)
        print(f"  Executável: {sys.executable}", file=sys.stderr)
        print(f"  Versão: {sys.version.split()[0]}", file=sys.stderr)
        print("\nInstale (Debian/Ubuntu):", file=sys.stderr)
        print("  sudo apt install -y python3-gi gir1.2-ayatanaappindicator3-0.1", file=sys.stderr)
        print("  # ou: gir1.2-appindicator3-0.1", file=sys.stderr)
        print("\nDica:", file=sys.stderr)
        print("  Se você usa pyenv/conda/venv, rode com o Python do sistema:", file=sys.stderr)
        print("    /usr/bin/python3 ./jbl_quantum910_tray.py", file=sys.stderr)
        sys.exit(1)


def find_hidraw_device() -> Optional[str]:
    """Find the first hidraw device matching JBL Quantum910 vendor/product."""
    # Look through /sys/bus/hid/devices/*/{idVendor,idProduct}/hidraw/hidraw*
    base = "/sys/bus/hid/devices"
    if os.path.isdir(base):
        for device_dir in sorted(os.listdir(base)):
            full = os.path.join(base, device_dir)
            vendor_file = os.path.join(full, "idVendor")
            product_file = os.path.join(full, "idProduct")
            if not (os.path.exists(vendor_file) and os.path.exists(product_file)):
                continue
            try:
                with open(vendor_file, "r", encoding="utf-8") as f:
                    vendor = f.read().strip().lower()
                with open(product_file, "r", encoding="utf-8") as f:
                    product = f.read().strip().lower()
                if vendor != VENDOR_ID_HEX or product != PRODUCT_ID_HEX:
                    continue
                hidraw_path = os.path.join(full, "hidraw")
                if not os.path.isdir(hidraw_path):
                    continue
                for entry in sorted(os.listdir(hidraw_path)):
                    if entry.startswith("hidraw"):
                        dev = f"/dev/{entry}"
                        if os.path.exists(dev):
                            return dev
            except Exception:
                continue

    # Fallback: first existing hidraw (best-effort)
    for i in range(0, 32):
        dev = f"/dev/hidraw{i}"
        if os.path.exists(dev):
            return dev
    return None


def parse_battery_from_packet(packet: bytes) -> Optional[int]:
    """Parse battery percent from a single packet (strict known pattern)."""
    if len(packet) >= 2 and packet[0] == 0x08:
        b = packet[1]
        if 0 <= b <= 100:
            return int(b)
    return None


def parse_mute_from_packet(packet: bytes) -> Optional[tuple[bool, bool]]:
    """
    Parse mute status from a packet (Report ID 0x2f).
    - 0x2f 0x02 = toggle mute (botão pressionado) -> retorna (True, True) = toggle
    - 0x2f 0x00 = estado desmutado -> retorna (False, False) = desmutado
    Returns (is_toggle, is_muted) or None if not a mute packet.
    """
    if len(packet) >= 2 and packet[0] == 0x2f:
        if packet[1] == 0x02:
            return (True, True)  # Toggle - precisa alternar estado
        elif packet[1] == 0x00:
            return (False, False)  # Estado desmutado
    return None


def _log(msg: str) -> None:
    # Journald/systemd friendly: timestamp + flush
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


@dataclass
class BatterySample:
    percent: int
    source: str
    raw_hex: str
    ts: float


@dataclass
class MuteSample:
    is_toggle: bool  # True se é toggle (0x02), False se é estado (0x00)
    muted: bool  # True se mutado, False se desmutado
    source: str
    raw_hex: str
    ts: float


class HidrawBatteryReader:
    def __init__(self, path: str):
        self.path = path
        self._fd: Optional[int] = None

    def close(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
        self._fd = None

    def _ensure_open(self) -> None:
        if self._fd is not None:
            return
        self._fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)

    def poll(self) -> Optional[BatterySample]:
        """Poll for battery updates. Also checks for mute in the same read."""
        try:
            self._ensure_open()
        except Exception:
            self.close()
            return None

        last_battery: Optional[BatterySample] = None
        # Drain available packets (non-blocking) to get the latest updates.
        for _ in range(32):
            try:
                data = os.read(self._fd, 64)  # type: ignore[arg-type]
                if not data:
                    break
                # Check for battery
                percent = parse_battery_from_packet(data)
                if percent is not None:
                    last_battery = BatterySample(
                        percent=percent,
                        source=f"hidraw:{self.path}",
                        raw_hex=" ".join(f"{b:02x}" for b in data[:8]),
                        ts=time.time(),
                    )
                # Also check for mute (but don't return it here, handled separately)
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                # Device went away / permission error / etc. Reopen next time.
                self.close()
                return None
            except Exception:
                self.close()
                return None

        return last_battery

    def poll_all(self) -> tuple[Optional[BatterySample], Optional[MuteSample]]:
        """Poll for both battery and mute updates in a single read pass."""
        try:
            self._ensure_open()
        except Exception:
            self.close()
            return None, None

        last_battery: Optional[BatterySample] = None
        last_mute: Optional[MuteSample] = None
        # Drain available packets (non-blocking) to get the latest updates.
        for _ in range(32):
            try:
                data = os.read(self._fd, 64)  # type: ignore[arg-type]
                if not data:
                    break
                # Check for battery
                percent = parse_battery_from_packet(data)
                if percent is not None:
                    last_battery = BatterySample(
                        percent=percent,
                        source=f"hidraw:{self.path}",
                        raw_hex=" ".join(f"{b:02x}" for b in data[:8]),
                        ts=time.time(),
                    )
                # Check for mute
                mute_info = parse_mute_from_packet(data)
                if mute_info is not None:
                    is_toggle, is_muted = mute_info
                    last_mute = MuteSample(
                        is_toggle=is_toggle,
                        muted=is_muted,
                        source=f"hidraw:{self.path}",
                        raw_hex=" ".join(f"{b:02x}" for b in data[:8]),
                        ts=time.time(),
                    )
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                self.close()
                return None, None
            except Exception:
                self.close()
                return None, None

        return last_battery, last_mute


class PyUsbBatteryReader:
    """
    PyUSB reader intentionally mirrors the known-good logic from `jbl_battery_simple.py`:
    - find device by VID/PID
    - (best-effort) detach kernel driver on interface 3
    - claim interface 3
    - read endpoint device[0][(3,0)][0] with timeout
    """

    def __init__(self, timeout_ms: int = 1000):
        self.timeout_ms = timeout_ms
        self._usb = None
        self._device = None
        self._endpoint = None
        self._claimed = False
        self.last_error: Optional[str] = None

    def close(self) -> None:
        if self._usb is not None and self._device is not None and self._claimed:
            try:
                self._usb.util.release_interface(self._device, 3)
            except Exception:
                pass
        self._usb = None
        self._device = None
        self._endpoint = None
        self._claimed = False
        self.last_error = None

    def _ensure_ready(self) -> bool:
        if self._device is not None and self._endpoint is not None:
            return True
        try:
            import usb.core  # type: ignore
            import usb.util  # type: ignore

            self._usb = type("USB", (), {"core": usb.core, "util": usb.util})
            dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
            if dev is None:
                self.last_error = "Dispositivo não encontrado"
                return False

            try:
                # Mirror `jbl_battery_simple.py`: best-effort detach if active.
                if dev.is_kernel_driver_active(3):
                    dev.detach_kernel_driver(3)
            except Exception:
                pass

            # Mirror `jbl_battery_simple.py`: must claim interface 3.
            try:
                usb.util.claim_interface(dev, 3)
            except Exception as e:
                self.last_error = f"Erro ao reivindicar interface 3: {e}"
                self._claimed = False
                return False

            self._claimed = True

            endpoint = dev[0][(3, 0)][0]
            self._device = dev
            self._endpoint = endpoint
            self.last_error = None
            return True
        except Exception:
            self.last_error = "Falha ao inicializar pyusb"
            self.close()
            return False

    def poll(self) -> Optional[BatterySample]:
        if not self._ensure_ready():
            return None

        try:
            dev = self._device
            ep = self._endpoint
            if dev is None or ep is None:
                return None
            data = dev.read(ep.bEndpointAddress, ep.wMaxPacketSize, self.timeout_ms)
            data_bytes = bytes(data)
            percent = parse_battery_from_packet(data_bytes)
            if percent is None:
                return None
            return BatterySample(
                percent=percent,
                source="pyusb",
                raw_hex=" ".join(f"{b:02x}" for b in data_bytes[:8]),
                ts=time.time(),
            )
        except Exception as e:
            # Treat timeouts like "no new data yet", and reset on other errors.
            try:
                if hasattr(e, "errno") and e.errno == 110:  # ETIMEDOUT in PyUSB
                    return None
            except Exception:
                pass
            # Re-init next time.
            self.last_error = str(e)
            self.close()
            return None

    def poll_all(self) -> tuple[Optional[BatterySample], Optional[MuteSample]]:
        """Poll for both battery and mute updates, draining multiple packets like hidraw."""
        try:
            if not self._ensure_ready():
                return None, None

            last_battery: Optional[BatterySample] = None
            last_mute: Optional[MuteSample] = None
            
            # Drain multiple packets (non-blocking) to get the latest updates
            # Similar to hidraw implementation, but with reasonable timeout
            # Read a few packets with short timeout, then one with longer timeout
            for i in range(5):
                try:
                    dev = self._device
                    ep = self._endpoint
                    if dev is None or ep is None:
                        break
                    # Use shorter timeout for first few reads (non-blocking)
                    timeout_ms = 50 if i < 4 else self.timeout_ms
                    data = dev.read(ep.bEndpointAddress, ep.wMaxPacketSize, timeout_ms)
                    data_bytes = bytes(data)
                    
                    # Check for battery
                    percent = parse_battery_from_packet(data_bytes)
                    if percent is not None:
                        last_battery = BatterySample(
                            percent=percent,
                            source="pyusb",
                            raw_hex=" ".join(f"{b:02x}" for b in data_bytes[:8]),
                            ts=time.time(),
                        )
                    
                    # Check for mute
                    mute_info = parse_mute_from_packet(data_bytes)
                    if mute_info is not None:
                        is_toggle, is_muted = mute_info
                        last_mute = MuteSample(
                            is_toggle=is_toggle,
                            muted=is_muted,
                            source="pyusb",
                            raw_hex=" ".join(f"{b:02x}" for b in data_bytes[:8]),
                            ts=time.time(),
                        )
                except Exception as e:
                    # Timeout is expected when no more data
                    try:
                        if hasattr(e, "errno") and e.errno == 110:  # ETIMEDOUT
                            # On timeout, return what we have so far
                            if last_battery is not None or last_mute is not None:
                                return last_battery, last_mute
                            # If no data yet and it's the last read, break
                            if i >= 4:
                                break
                            # Otherwise continue to next read
                            continue
                    except Exception:
                        pass
                    # Other errors - stop reading and return what we have
                    break
            
            return last_battery, last_mute
        except Exception as e:
            try:
                if hasattr(e, "errno") and e.errno == 110:  # ETIMEDOUT
                    return None, None
            except Exception:
                pass
            self.last_error = str(e)
            self.close()
            return None, None


class BatteryTrayApp:
    def __init__(self, refresh_seconds: float, prefer_pyusb: bool, pyusb_detach: bool):
        self.refresh_seconds = max(0.2, refresh_seconds)
        self.prefer_pyusb = prefer_pyusb

        self.Gtk, self.GLib, self.AppIndicator = _import_appindicator()

        self.last_sample: Optional[BatterySample] = None
        self.last_mute_sample: Optional[MuteSample] = None
        self._last_label: Optional[str] = None
        self._last_logged_error: Optional[str] = None
        self._last_logged_percent: Optional[int] = None
        self._is_muted: bool = False

        hidraw = find_hidraw_device()
        self.hidraw_reader = HidrawBatteryReader(hidraw) if hidraw else None
        # Keep `pyusb_detach` for CLI compatibility, but the default behavior
        # now mirrors `jbl_battery_simple.py` (best-effort detach if active).
        self.pyusb_reader = PyUsbBatteryReader(timeout_ms=1000)

        self.indicator = self.AppIndicator.Indicator.new(
            "jbl-quantum910-battery",
            "battery-missing-symbolic",
            self.AppIndicator.IndicatorCategory.HARDWARE,
        )
        self.indicator.set_status(self.AppIndicator.IndicatorStatus.ACTIVE)

        self.menu = self._build_menu()
        self.indicator.set_menu(self.menu)

        # First render
        self._render()
        _log(f"Tray iniciado. prefer_pyusb={self.prefer_pyusb} hidraw={hidraw!s}")

        # Periodic updates
        self.GLib.timeout_add(int(self.refresh_seconds * 1000), self._tick)

    def _build_menu(self):
        menu = self.Gtk.Menu()

        item_refresh = self.Gtk.MenuItem(label="Atualizar agora")
        item_refresh.connect("activate", lambda *_: self._force_refresh())
        menu.append(item_refresh)

        item_sep = self.Gtk.SeparatorMenuItem()
        menu.append(item_sep)

        item_quit = self.Gtk.MenuItem(label="Sair")
        item_quit.connect("activate", lambda *_: self._quit())
        menu.append(item_quit)

        menu.show_all()
        return menu

    def _quit(self):
        try:
            if self.hidraw_reader:
                self.hidraw_reader.close()
            self.pyusb_reader.close()
        finally:
            self.Gtk.main_quit()

    def _battery_icon_name(self, percent: Optional[int], is_muted: bool = False) -> str:
        """Get icon name based on battery level and mute status."""
        if is_muted:
            # Use microphone-muted icon when muted
            # Try multiple icon names for compatibility
            return "microphone-sensitivity-muted-symbolic"
            # Alternatives: "audio-input-microphone-muted-symbolic", "microphone-disabled-symbolic"
        
        if percent is None:
            return "battery-missing-symbolic"
        if percent >= 95:
            return "battery-full-symbolic"
        if percent >= 75:
            return "battery-good-symbolic"
        if percent >= 40:
            return "battery-medium-symbolic"
        if percent >= 15:
            return "battery-low-symbolic"
        return "battery-caution-symbolic"

    def _read_once(self) -> Optional[BatterySample]:
        # Choose reading order.
        readers = []
        if self.prefer_pyusb:
            readers = [("pyusb", self.pyusb_reader.poll), ("hidraw", (self.hidraw_reader.poll if self.hidraw_reader else None))]
        else:
            readers = [("hidraw", (self.hidraw_reader.poll if self.hidraw_reader else None)), ("pyusb", self.pyusb_reader.poll)]

        for _, fn in readers:
            if fn is None:
                continue
            sample = fn()
            if sample is not None:
                return sample
        return None

    def _read_all_once(self) -> tuple[Optional[BatterySample], Optional[MuteSample]]:
        """Read both battery and mute status from device."""
        # Priority: read battery using poll (original method that worked)
        # Then try to read mute separately if needed
        readers = []
        if self.prefer_pyusb:
            readers = [("pyusb", self.pyusb_reader.poll), ("hidraw", (self.hidraw_reader.poll if self.hidraw_reader else None))]
        else:
            readers = [("hidraw", (self.hidraw_reader.poll if self.hidraw_reader else None)), ("pyusb", self.pyusb_reader.poll)]

        battery_sample = None
        for _, fn in readers:
            if fn is None:
                continue
            try:
                battery_sample = fn()
                if battery_sample is not None:
                    break
            except Exception:
                continue
        
        # Try to read mute using poll_all (non-blocking, won't interfere if no data)
        mute_sample = None
        try:
            # Only try hidraw for mute (less intrusive)
            if self.hidraw_reader:
                try:
                    _, mute = self.hidraw_reader.poll_all()
                    if mute is not None:
                        mute_sample = mute
                except Exception:
                    pass
            # Also try pyusb poll_all if hidraw didn't work
            if mute_sample is None:
                try:
                    _, mute = self.pyusb_reader.poll_all()
                    if mute is not None:
                        mute_sample = mute
                except Exception:
                    pass
        except Exception:
            pass
        
        return battery_sample, mute_sample

    def _force_refresh(self):
        sample = self._read_once()
        if sample is not None:
            self.last_sample = sample
        self._render()

    def _tick(self):
        # Read both battery and mute in a single pass
        battery_sample, mute_sample = self._read_all_once()
        
        needs_render = False
        
        if battery_sample is not None:
            # Force render if battery changed
            if self.last_sample is None or self.last_sample.percent != battery_sample.percent:
                needs_render = True
            self.last_sample = battery_sample
            if self._last_logged_percent != battery_sample.percent:
                _log(f"Bateria: {battery_sample.percent}% (fonte={battery_sample.source}, dados={battery_sample.raw_hex})")
                self._last_logged_percent = battery_sample.percent
                self._last_logged_error = None
        else:
            # Surface pyusb errors (most common: permission / claim interface)
            err = getattr(self.pyusb_reader, "last_error", None)
            if err and err != self._last_logged_error:
                _log(f"Sem leitura. Erro pyusb: {err}")
                self._last_logged_error = err
            # Even if no new battery data, keep rendering with last known value
        
        if mute_sample is not None:
            old_muted = self._is_muted
            self.last_mute_sample = mute_sample
            if mute_sample.is_toggle:
                # O código 0x2f 0x02 é um toggle - alterna o estado
                self._is_muted = not self._is_muted
                status = "MUTADO" if self._is_muted else "DESMUTADO"
                emoji = "🔇" if self._is_muted else "🎤"
                _log(f"Microfone {emoji} {status} (toggle detectado, fonte={mute_sample.source}, dados={mute_sample.raw_hex})")
            else:
                # 0x2f 0x00 = estado desmutado
                self._is_muted = False
                _log(f"Microfone 🎤 DESMUTADO (estado recebido, fonte={mute_sample.source}, dados={mute_sample.raw_hex})")
            
            # Force render if mute state changed
            if old_muted != self._is_muted:
                needs_render = True
        
        # Always render, but force update if something changed
        if needs_render or (battery_sample is not None and self._last_label == "--%"):
            self._last_label = None  # Force label update
        self._render()
        return True  # keep timer

    def _render(self):
        percent = self.last_sample.percent if self.last_sample else None
        icon = self._battery_icon_name(percent, self._is_muted)
        # Force icon update by setting it again
        self.indicator.set_icon_full(icon, "JBL Quantum910 Battery")
        # Also try setting status to force refresh
        self.indicator.set_status(self.AppIndicator.IndicatorStatus.ACTIVE)

        err = getattr(self.pyusb_reader, "last_error", None)
        if percent is not None:
            mute_indicator = " 🔇" if self._is_muted else ""
            label = f"{percent}%{mute_indicator}"
        elif err:
            label = "ERR"
        else:
            label = "--%"
        
        # Always update label if we have battery data or if label changed
        # Force update if we have data but label is still showing "--%"
        should_update = (
            label != self._last_label or 
            self._last_label is None or
            (percent is not None and self._last_label == "--%")
        )
        
        if should_update:
            try:
                self.indicator.set_label(label, "")
                self._last_label = label
                # Log when label is updated for debugging
                if percent is not None:
                    _log(f"Tray label atualizado: {label}")
            except Exception as e:
                # Some tray implementations don't support set_label
                _log(f"Erro ao atualizar label: {e}")
                pass

        # Tooltip with freshness + source + mute status
        if self.last_sample:
            age_s = max(0.0, time.time() - self.last_sample.ts)
            mute_status = "🔇 MUTADO" if self._is_muted else "🎤 Ativo"
            tip = f"JBL Quantum910: {self.last_sample.percent}%\nMicrofone: {mute_status}\nFonte: {self.last_sample.source}\nAtualizado há: {age_s:.0f}s\nDados: {self.last_sample.raw_hex}"
        else:
            src = "hidraw" if self.hidraw_reader else "pyusb"
            extra = ""
            if src == "pyusb" and getattr(self.pyusb_reader, "last_error", None):
                extra = f"\nErro: {self.pyusb_reader.last_error}"
            mute_status = "🔇 MUTADO" if self._is_muted else "🎤 Ativo"
            tip = f"JBL Quantum910: sem leitura ainda\nMicrofone: {mute_status}\nTentando via: {src}{extra}\nDica: use o fone (volume/botões) para gerar tráfego."
        try:
            self.indicator.set_title("JBL Quantum910 Battery")
        except Exception:
            pass
        # Some implementations show tooltip via icon description:
        try:
            self.indicator.set_icon_desc(tip)
        except Exception:
            pass

    def run(self):
        # Handle Ctrl+C nicely when launched from terminal
        import signal

        signal.signal(signal.SIGINT, lambda *_: self._quit())
        signal.signal(signal.SIGTERM, lambda *_: self._quit())
        self.Gtk.main()


def main() -> int:
    parser = argparse.ArgumentParser(description="JBL Quantum910 tray battery monitor (AppIndicator)")
    parser.add_argument("--refresh", type=float, default=1.0, help="Intervalo de atualização em segundos (default: 1.0)")
    parser.add_argument(
        "--prefer-pyusb",
        action="store_true",
        help="(padrão) Tenta pyusb primeiro",
    )
    parser.add_argument(
        "--prefer-hidraw",
        action="store_true",
        help="Prefere hidraw primeiro (pode funcionar sem 'claim interface')",
    )
    parser.add_argument(
        "--pyusb-detach-kernel",
        action="store_true",
        help="(compat) Ignorado: o comportamento padrão já tenta detach best-effort como no jbl_battery_simple.py",
    )
    args = parser.parse_args()

    app = BatteryTrayApp(
        refresh_seconds=args.refresh,
        prefer_pyusb=(not args.prefer_hidraw),
        pyusb_detach=args.pyusb_detach_kernel,
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

