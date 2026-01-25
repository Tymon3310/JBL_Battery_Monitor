#!/usr/bin/env python3
"""
Script para ler dados do JBL Quantum910 sem desanexar o driver do kernel
Usa uma abordagem mais passiva para monitorar comunicação
"""

import usb.core
import usb.util
import sys
import time
import struct

VENDOR_ID = 0x0ecb
PRODUCT_ID = 0x2088


def find_device():
    """Encontra o dispositivo USB"""
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if device is None:
        raise ValueError("Dispositivo não encontrado. Certifique-se de que o fone está conectado.")
    return device


def get_device_info(device):
    """Obtém informações do dispositivo"""
    print("=" * 60)
    print("Informações do Dispositivo")
    print("=" * 60)
    print(f"Vendor ID: 0x{device.idVendor:04x}")
    print(f"Product ID: 0x{device.idProduct:04x}")
    try:
        print(f"Fabricante: {usb.util.get_string(device, device.iManufacturer)}")
    except Exception:
        print(f"Fabricante: (não disponível)")
    try:
        print(f"Produto: {usb.util.get_string(device, device.iProduct)}")
    except Exception:
        print(f"Produto: (não disponível)")
    print()

    # Informações da interface HID
    try:
        cfg = device.get_active_configuration()
        intf = cfg[(3, 0)]
        print(f"Interface HID: {intf.bInterfaceNumber}")
        print(f"Endpoints: {len(intf)}")
        for ep in intf:
            print(
                f"  - Endpoint 0x{ep.bEndpointAddress:02x}: "
                f"{'IN' if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else 'OUT'}, "
                f"Tamanho máximo: {ep.wMaxPacketSize} bytes"
            )
    except Exception as e:
        print(f"Erro ao obter informações da interface: {e}")
    print("=" * 60)
    print()


def try_read_without_claim(device):
    """Tenta ler dados sem reivindicar a interface"""
    print("Tentando ler dados sem desanexar driver...")
    print("(Pode ser necessário executar como root)")
    print()

    try:
        # Tenta acessar o endpoint diretamente
        cfg = device.get_active_configuration()
        intf = cfg[(3, 0)]
        endpoint = intf[0]  # Primeiro endpoint (geralmente o IN)

        print(f"Endpoint: 0x{endpoint.bEndpointAddress:02x}")
        print(f"Tamanho máximo: {endpoint.wMaxPacketSize} bytes")
        print()
        print("Monitorando... (Pressione Ctrl+C para parar)")
        print()

        battery_level = None

        for i in range(100):  # Tenta ler 100 vezes
            try:
                # Tenta ler com timeout curto
                data = device.read(endpoint.bEndpointAddress, endpoint.wMaxPacketSize, 100)
                data_bytes = list(data)

                hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                print(f"[{time.strftime('%H:%M:%S')}] Dados ({len(data_bytes)} bytes): {hex_data}")
                print(f"  Bytes: {data_bytes}")

                # Tenta interpretar bateria
                for j, byte in enumerate(data_bytes):
                    if 0 <= byte <= 100:
                        if battery_level != byte:
                            battery_level = byte
                            print(f"  ⚡ Nível de bateria: {battery_level}% (posição {j})")

                if len(data_bytes) >= 2:
                    val_16 = struct.unpack('<H', bytes(data_bytes[:2]))[0]
                    if 0 <= val_16 <= 100 and battery_level != val_16:
                        battery_level = val_16
                        print(f"  ⚡ Nível de bateria (16-bit): {battery_level}%")

                print()

            except usb.core.USBError as e:
                if e.errno == 110:  # ETIMEDOUT
                    if i % 10 == 0:
                        print(f"[{time.strftime('%H:%M:%S')}] Aguardando dados... (tentativa {i+1})")
                elif e.errno == 13:  # Permission denied
                    print(f"Erro de permissão: {e}")
                    print("Tente executar como root: sudo python3 jbl_battery_readonly.py")
                    break
                else:
                    print(f"Erro USB: {e}")

            time.sleep(0.5)

    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("JBL Quantum910 - Monitor de Bateria (Modo Read-Only)")
    print("=" * 60)
    print()

    try:
        device = find_device()
        get_device_info(device)
        try_read_without_claim(device)

    except ValueError as e:
        print(f"Erro: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

