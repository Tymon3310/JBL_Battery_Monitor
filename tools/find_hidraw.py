#!/usr/bin/env python3
"""
Script para encontrar automaticamente qual hidraw corresponde ao JBL Quantum910
"""

import os
import sys

VENDOR_ID = "0ecb"
PRODUCT_ID = "2088"


def find_jbl_hidraw():
    """Encontra o hidraw correspondente ao JBL Quantum910"""
    print("Procurando dispositivo JBL Quantum910...")
    print(f"Vendor ID: 0x{VENDOR_ID}, Product ID: 0x{PRODUCT_ID}")
    print()

    # Procura em /sys/bus/hid/devices
    hid_devices_path = "/sys/bus/hid/devices"

    if not os.path.exists(hid_devices_path):
        print("Erro: /sys/bus/hid/devices não encontrado")
        return None

    found_devices = []

    for device_dir in os.listdir(hid_devices_path):
        device_path = os.path.join(hid_devices_path, device_dir)

        if not os.path.isdir(device_path):
            continue

        vendor_file = os.path.join(device_path, "idVendor")
        product_file = os.path.join(device_path, "idProduct")

        if os.path.exists(vendor_file) and os.path.exists(product_file):
            try:
                with open(vendor_file, 'r') as f:
                    vendor = f.read().strip().lower()
                with open(product_file, 'r') as f:
                    product = f.read().strip().lower()

                if vendor == VENDOR_ID and product == PRODUCT_ID:
                    # Encontrou o dispositivo!
                    print(f"✓ Dispositivo encontrado: {device_dir}")

                    # Procura o hidraw correspondente
                    hidraw_path = os.path.join(device_path, "hidraw")
                    if os.path.exists(hidraw_path):
                        hidraw_dirs = [d for d in os.listdir(hidraw_path) if d.startswith("hidraw")]
                        if hidraw_dirs:
                            hidraw_name = hidraw_dirs[0]
                            hidraw_device = f"/dev/{hidraw_name}"

                            if os.path.exists(hidraw_device):
                                print(f"✓ Hidraw encontrado: {hidraw_device}")

                                # Verifica permissões
                                if os.access(hidraw_device, os.R_OK):
                                    print(f"✓ Permissão de leitura: OK")
                                else:
                                    print(f"⚠ Permissão de leitura: NEGADA")
                                    print(f"  Execute: sudo chmod 666 {hidraw_device}")

                                found_devices.append({
                                    'device_dir': device_dir,
                                    'hidraw': hidraw_device,
                                    'hidraw_name': hidraw_name
                                })
                            else:
                                print(f"⚠ Hidraw {hidraw_device} não existe ainda")
                        else:
                            print(f"⚠ Nenhum hidraw encontrado em {hidraw_path}")
                    else:
                        print(f"⚠ Caminho hidraw não encontrado: {hidraw_path}")
            except Exception:
                pass

    # Se não encontrou, verifica lsusb
    if not found_devices:
        print("\n⚠ Dispositivo não encontrado em /sys/bus/hid/devices")
        print("\nVerificando lsusb...")
        import subprocess
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if '0ecb' in result.stdout.lower() or 'jbl' in result.stdout.lower() or 'quantum' in result.stdout.lower():
                print("✓ Dispositivo encontrado no lsusb:")
                for line in result.stdout.split('\n'):
                    if '0ecb' in line.lower() or 'jbl' in line.lower() or 'quantum' in line.lower():
                        print(f"  {line}")
                print("\n⚠ Mas não foi encontrado em /sys/bus/hid/devices")
                print("  Isso pode significar que:")
                print("  - O dispositivo ainda está sendo inicializado")
                print("  - O driver HID não foi carregado")
                print("  - Aguarde alguns segundos e tente novamente")
            else:
                print("✗ Dispositivo não encontrado no lsusb")
                print("\nPossíveis causas:")
                print("1. O fone não está conectado via USB")
                print("2. O cabo USB está com problema")
                print("3. Tente desconectar e reconectar o fone")
        except Exception:
            pass

        return None

    print(f"\n{'='*60}")
    print(f"RESUMO")
    print(f"{'='*60}")
    print(f"Dispositivos encontrados: {len(found_devices)}")

    for i, dev in enumerate(found_devices, 1):
        print(f"\nDispositivo {i}:")
        print(f"  Diretório: {dev['device_dir']}")
        print(f"  Hidraw: {dev['hidraw']}")
        print(f"  Nome: {dev['hidraw_name']}")

    # Retorna o primeiro (ou o único)
    return found_devices[0]['hidraw'] if found_devices else None


if __name__ == "__main__":
    hidraw = find_jbl_hidraw()

    if hidraw:
        print(f"\n{'='*60}")
        print(f"✅ USE ESTE HIDRAW:")
        print(f"   {hidraw}")
        print(f"{'='*60}")
        print(f"\nPara usar nos scripts, edite a variável HIDRAW_DEVICE:")
        print(f"  HIDRAW_DEVICE = \"{hidraw}\"")
        print(f"\nOu execute os scripts que detectam automaticamente.")
    else:
        print("\n❌ Não foi possível encontrar o dispositivo")
        sys.exit(1)

