#!/usr/bin/env python3
"""
Shared JBL Quantum USB and HIDRAW helpers for the tray and CLI tools.
"""

from __future__ import annotations

import os
import glob
import time
import re
from abc import ABC, abstractmethod
from typing import Iterable, Optional, Tuple


VENDOR_ID_HEX = "0ecb"
PRODUCT_IDS_HEX = ["2088", "205c"]  # 910, 610
VENDOR_ID = int(VENDOR_ID_HEX, 16)
PRODUCT_IDS = [int(pid, 16) for pid in PRODUCT_IDS_HEX]

INTERRUPT_BATTERY_REPORT_IDS = {0x08}
POLL_BATTERY_REPORT_IDS = {0x49}


def _parse_extra_product_ids() -> list[int]:
    raw = os.environ.get("JBL_QUANTUM_EXTRA_PRODUCT_IDS", "")
    parsed: list[int] = []
    for chunk in raw.split(","):
        value = chunk.strip().lower()
        if not value:
            continue
        if value.startswith("0x"):
            value = value[2:]
        try:
            parsed.append(int(value, 16))
        except ValueError:
            continue
    return parsed


ALL_PRODUCT_IDS = sorted(set(PRODUCT_IDS + _parse_extra_product_ids()))

def parse_battery_from_packet(packet: bytes, allowed_report_ids: Iterable[int] = INTERRUPT_BATTERY_REPORT_IDS) -> Optional[Tuple[int, bool]]:
    if len(packet) < 2:
        return None
    if packet[0] not in set(allowed_report_ids):
        return None

    percent = int(packet[1])
    if not 0 <= percent <= 100:
        return None

    charging = len(packet) > 2 and (packet[2] & 0x01 == 0x01)
    return percent, charging


def parse_mute_from_packet(packet: bytes) -> Optional[Tuple[bool, bool]]:
    if len(packet) < 2:
        return None

    report_id = packet[0]
    if report_id == 0x2F:
        if packet[1] == 0x02:
            return False, True   # Absolute Muted
        if packet[1] == 0x00:
            return False, False  # Absolute Unmuted
    if report_id == 0x06:
        return False, packet[1] == 0x00  # Muted if 0x00
    return None


def _read_sysfs_hex(path: str) -> Optional[int]:
    try:
        with open(path, "r") as f:
            return int(f.read().strip(), 16)
    except Exception:
        return None


def _parse_hid_uevent(uevent: str) -> Optional[Tuple[int, int]]:
    match = re.search(r"^HID_ID=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8}):([0-9A-Fa-f]{8})$", uevent, re.M)
    if not match:
        return None
    vendor = int(match.group(2), 16)
    product = int(match.group(3), 16)
    return vendor, product


def _find_hidraw_from_hid_bus() -> Optional[Tuple[int, int, str]]:
    for device_dir in glob.glob("/sys/bus/hid/devices/*"):
        try:
            vid = _read_sysfs_hex(os.path.join(device_dir, "idVendor"))
            pid = _read_sysfs_hex(os.path.join(device_dir, "idProduct"))
            if vid is None or pid is None:
                uevent_path = os.path.join(device_dir, "uevent")
                try:
                    with open(uevent_path, "r") as f:
                        parsed = _parse_hid_uevent(f.read())
                except Exception:
                    parsed = None
                if parsed is None:
                    continue
                vid, pid = parsed

            if vid == VENDOR_ID and pid in ALL_PRODUCT_IDS:
                hidraw_path = os.path.join(device_dir, "hidraw")
                if os.path.exists(hidraw_path):
                    hidraw_dirs = sorted(d for d in os.listdir(hidraw_path) if d.startswith("hidraw"))
                    for hidraw_dir in hidraw_dirs:
                        path = f"/dev/{hidraw_dir}"
                        if os.path.exists(path):
                            return vid, pid, path
        except Exception:
            continue
    return None


def _find_hidraw_from_class() -> Optional[Tuple[int, int, str]]:
    for hidraw_dir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent_path = os.path.join(hidraw_dir, "device", "uevent")
            with open(uevent_path, "r") as f:
                parsed = _parse_hid_uevent(f.read())
            if parsed is None:
                continue
            vid, pid = parsed
            if vid != VENDOR_ID or pid not in ALL_PRODUCT_IDS:
                continue

            path = f"/dev/{os.path.basename(hidraw_dir)}"
            if os.path.exists(path):
                return vid, pid, path
        except Exception:
            continue
    return None


class JBLDevice(ABC):
    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.is_610 = (product_id == 0x205c)
        self.product_name = "JBL Quantum 610" if self.is_610 else "JBL Quantum 910"

    @abstractmethod
    def open(self) -> bool:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def read(self, timeout_ms: int = 1000) -> Optional[bytes]:
        pass

    @abstractmethod
    def poll_battery(self) -> Optional[Tuple[int, bool]]:
        pass

    @abstractmethod
    def poll_mute(self) -> Optional[bool]:
        pass

    @abstractmethod
    def poll_link(self) -> Optional[bool]:
        pass


class JBLPyUSBDevice(JBLDevice):
    def __init__(self, vendor_id: int, product_id: int, detach_kernel: bool = False):
        super().__init__(vendor_id, product_id)
        self.detach_kernel = detach_kernel
        self.dev = None
        self.endpoint = None
        self.iface_num = None
        self.usb_core = None
        self.usb_util = None

    def open(self) -> bool:
        import usb.core
        import usb.util
        self.usb_core = usb.core
        self.usb_util = usb.util
        
        self.dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
        if not self.dev:
            return False

        try:
            self.dev.set_configuration()
        except Exception:
            pass

        cfg = self.dev.get_active_configuration()
        for intf in cfg:
            if intf.bInterfaceNumber not in (3, 5) and intf.bInterfaceClass != 3:
                continue
            iface_num = intf.bInterfaceNumber
            try:
                if self.dev.is_kernel_driver_active(iface_num):
                    if self.detach_kernel:
                        self.dev.detach_kernel_driver(iface_num)
                    else:
                        continue # Skip if driver active and we shouldn't detach

                usb.util.claim_interface(self.dev, iface_num)
                endpoint = usb.util.find_descriptor(
                    intf,
                    custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN,
                )
                if endpoint is not None:
                    self.iface_num = iface_num
                    self.endpoint = endpoint
                    return True
                usb.util.release_interface(self.dev, iface_num)
            except Exception:
                continue
        return False

    def close(self) -> None:
        if self.dev and self.iface_num is not None:
            try:
                self.usb_util.release_interface(self.dev, self.iface_num)
            except Exception:
                pass
        self.dev = None

    def read(self, timeout_ms: int = 1000) -> Optional[bytes]:
        if not self.dev or not self.endpoint:
            return None
        try:
            return bytes(self.dev.read(self.endpoint.bEndpointAddress, self.endpoint.wMaxPacketSize, timeout_ms))
        except self.usb_core.USBError as e:
            if e.errno == 110: # Timeout
                return None
            raise e

    def poll_battery(self) -> Optional[Tuple[int, bool]]:
        if not self.is_610:
            return None # 910 uses interrupt reports
        try:
            data = self.dev.ctrl_transfer(0xA1, 0x01, 0x0149, self.iface_num, 64, timeout=500)
            if len(data) >= 2 and data[0] in POLL_BATTERY_REPORT_IDS:
                return int(data[1]), False
        except Exception:
            pass
        return None

    def poll_mute(self) -> Optional[bool]:
        if not self.is_610:
            return None
        try:
            data = self.dev.ctrl_transfer(0xA1, 0x01, 0x0167, self.iface_num, 64, timeout=500)
            if len(data) >= 2 and data[0] == 0x67:
                return data[1] == 0x00
        except Exception:
            pass
        return None

    def poll_link(self) -> Optional[bool]:
        if not self.is_610:
            return True # Assume online if we can talk to it via PyUSB?
        try:
            data = self.dev.ctrl_transfer(0xA1, 0x01, 0x0168, self.iface_num, 64, timeout=500)
            if len(data) >= 2 and data[0] == 0x68:
                return data[1] == 0x01
        except Exception:
            pass
        return None


class JBLHIDRawDevice(JBLDevice):
    def __init__(self, vendor_id: int, product_id: int, path: str):
        super().__init__(vendor_id, product_id)
        self.path = path
        self.fd = None

    def open(self) -> bool:
        try:
            self.fd = open(self.path, "rb", buffering=0)
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self.fd:
            try:
                self.fd.close()
            except Exception:
                pass
        self.fd = None

    def read(self, timeout_ms: int = 1000) -> Optional[bytes]:
        if not self.fd:
            return None
        import select
        try:
            ready, _, _ = select.select([self.fd], [], [], timeout_ms / 1000.0)
            if ready:
                return self.fd.read(64)
        except Exception:
            pass
        return None

    def poll_battery(self) -> Optional[Tuple[int, bool]]:
        # Poll via HIDRAW usually requires ioctl or just reading.
        # For 610, it's mostly polling. For 910, it's interrupts.
        # Implementation of polling via HIDRAW is complex and might not be needed
        # if the device sends updates periodically anyway.
        return None

    def poll_mute(self) -> Optional[bool]:
        return None

    def poll_link(self) -> Optional[bool]:
        return os.path.exists(self.path)


def find_hidraw_device() -> Optional[Tuple[int, int, str]]:
    return _find_hidraw_from_hid_bus() or _find_hidraw_from_class()


def get_jbl_device(prefer_hidraw: bool = True, prefer_pyusb: bool = False, detach_kernel: bool = False) -> Optional[JBLDevice]:
    import usb.core

    hidraw_candidate: Optional[Tuple[int, int, str]] = None
    if prefer_hidraw:
        hidraw_candidate = find_hidraw_device()

    # The 610 relies on polled control transfers for battery/link state, which
    # the hidraw backend does not implement. Prefer PyUSB when that model is found.
    if hidraw_candidate and hidraw_candidate[1] == 0x205C and not prefer_pyusb:
        prefer_pyusb = True

    if prefer_pyusb:
        for pid in ALL_PRODUCT_IDS:
            dev = JBLPyUSBDevice(VENDOR_ID, pid, detach_kernel=detach_kernel)
            if dev.open():
                return dev
            if pid == 0x205C and not detach_kernel:
                retry_dev = JBLPyUSBDevice(VENDOR_ID, pid, detach_kernel=True)
                if retry_dev.open():
                    return retry_dev

    if hidraw_candidate and prefer_hidraw:
        vid, pid, path = hidraw_candidate
        dev = JBLHIDRawDevice(vid, pid, path)
        if dev.open():
            return dev

    for pid in ALL_PRODUCT_IDS:
        dev = JBLPyUSBDevice(VENDOR_ID, pid, detach_kernel=detach_kernel)
        if dev.open():
            return dev
        if pid == 0x205C and not detach_kernel:
            retry_dev = JBLPyUSBDevice(VENDOR_ID, pid, detach_kernel=True)
            if retry_dev.open():
                return retry_dev
    
    return None
