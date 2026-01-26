#!/usr/bin/env python3
"""
Encontra quais /dev/hidrawX pertencem ao JBL Quantum910 (VID:PID 0ecb:2088).

Uso:
  python3 tools/find_jbl_hidraw.py
  sudo python3 tools/find_jbl_hidraw.py --bind-usbhid

Saída:
  Lista todos os hidraw e destaca os que batem com o VID:PID.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


TARGET_VENDOR = 0x0ECB
TARGET_PRODUCT = 0x2088


def parse_hid_id(uevent_text: str) -> tuple[int, int] | None:
    """
    HID_ID normalmente vem assim:
      HID_ID=0003:00000ECB:00002088
    """
    m = re.search(r"^HID_ID=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8}):([0-9A-Fa-f]{8})$", uevent_text, re.M)
    if not m:
        return None
    # bus = int(m.group(1), 16)  # não usado
    vendor = int(m.group(2), 16)
    product = int(m.group(3), 16)
    return vendor, product


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return None


def _find_unbound_usb_hid_interfaces_for_target() -> list[str]:
    """
    Procura interfaces USB HID (bInterfaceClass=03) do dispositivo alvo que
    estejam sem driver (sem symlink em .../driver). Retorna nomes tipo:
      ['1-3:1.3', ...]
    """
    usb_root = Path("/sys/bus/usb/devices")
    out: list[str] = []

    # Encontra dispositivos USB com idVendor/idProduct que batem
    for dev in usb_root.iterdir():
        idv = dev / "idVendor"
        idp = dev / "idProduct"
        if not (idv.exists() and idp.exists()):
            continue
        try:
            v = int(idv.read_text().strip(), 16)
            p = int(idp.read_text().strip(), 16)
        except Exception:
            continue
        if v != TARGET_VENDOR or p != TARGET_PRODUCT:
            continue

        # Interfaces aparecem como "<devname>:1.<n>"
        parent = dev.parent
        for iface in sorted(parent.glob(dev.name + ":1.*")):
            cls = iface / "bInterfaceClass"
            if not cls.exists():
                continue
            try:
                icls = int(cls.read_text().strip(), 16)
            except Exception:
                continue
            if icls != 0x03:
                continue
            drv = iface / "driver"
            if not (drv.exists() and drv.is_symlink()):
                out.append(iface.name)

    return out


def _bind_to_usbhid(iface_names: list[str]) -> None:
    bind_path = Path("/sys/bus/usb/drivers/usbhid/bind")
    if not bind_path.exists():
        raise RuntimeError("Caminho /sys/bus/usb/drivers/usbhid/bind não existe (driver usbhid indisponível).")

    # Precisa de root para escrever
    for name in iface_names:
        try:
            bind_path.write_text(name)
            print(f"✓ bind usbhid: {name}")
        except PermissionError as e:
            raise RuntimeError("Permissão negada ao tentar fazer bind (rode com sudo).") from e
        except OSError as e:
            raise RuntimeError(f"Falha ao fazer bind do {name} no usbhid: {e}") from e


def main() -> int:
    parser = argparse.ArgumentParser(description="Encontra hidraw do JBL Quantum910 (0ecb:2088)")
    parser.add_argument(
        "--bind-usbhid",
        action="store_true",
        help="Se a interface HID do JBL estiver sem driver, tenta fazer bind no usbhid (requer sudo).",
    )
    args = parser.parse_args()

    # Diagnóstico: o seu caso típico é o USB HID estar sem driver, então não nasce hidraw.
    unbound_hid_ifaces = _find_unbound_usb_hid_interfaces_for_target()
    if unbound_hid_ifaces:
        print("⚠ Interface(s) USB HID do JBL detectadas, mas SEM driver (por isso não aparece /dev/hidrawX):")
        for n in unbound_hid_ifaces:
            print(f"  - {n}")
        if args.bind_usbhid:
            print("\nTentando fazer bind no driver usbhid...")
            _bind_to_usbhid(unbound_hid_ifaces)
            print("\nReescaneando hidraw...\n")
        else:
            print("\nDica: rode com:")
            print("  sudo python3 tools/find_jbl_hidraw.py --bind-usbhid")
            print("ou replugue o dongle do fone (desconecta/reconecta).")
            print()

    hidraw_root = Path("/sys/class/hidraw")
    if not hidraw_root.exists():
        print("Erro: /sys/class/hidraw não existe (hidraw indisponível neste sistema).")
        return 1

    hidraws = sorted([p for p in hidraw_root.glob("hidraw*") if p.is_dir()], key=lambda p: p.name)
    if not hidraws:
        print("Nenhum hidraw encontrado em /sys/class/hidraw.")
        return 1

    matches: list[str] = []

    for entry in hidraws:
        devnode = f"/dev/{entry.name}"
        uevent_path = entry / "device" / "uevent"
        uevent = read_text(uevent_path) or ""

        vid_pid = parse_hid_id(uevent)
        hid_name = None
        mname = re.search(r"^HID_NAME=(.*)$", uevent, re.M)
        if mname:
            hid_name = mname.group(1).strip()

        if vid_pid is None:
            print(f"{devnode}: (sem HID_ID) name={hid_name or '?'}")
            continue

        vendor, product = vid_pid
        ok = (vendor == TARGET_VENDOR and product == TARGET_PRODUCT)
        tag = "  <-- JBL Quantum910" if ok else ""

        print(f"{devnode}: vid:pid={vendor:04x}:{product:04x} name={hid_name or '?'}{tag}")
        if ok:
            matches.append(devnode)

    if matches:
        print("\nSugestão: comece testando estes hidraw (nessa ordem):")
        for d in matches:
            print(f"  - {d}")
    else:
        print("\nNenhum /dev/hidrawX bateu com vid:pid 0ecb:2088.")
        print("Se o fone estiver conectado, confira com: lsusb | grep -i 0ecb")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

