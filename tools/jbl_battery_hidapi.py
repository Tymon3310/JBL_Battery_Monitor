#!/usr/bin/env python3
"""
Script alternativo usando hidapi para interceptar comunicação USB
do JBL Quantum910 Wireless e extrair informações de bateria
"""

import sys

try:
    import hid
except ImportError:
    print("Instalando hidapi...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "hidapi", "--user"])
    import hid

VENDOR_ID = 0x0ecb
PRODUCT_ID = 0x2088


def find_and_monitor():
    """Encontra o dispositivo e monitora comunicação"""
    print("JBL Quantum910 - Monitor de Bateria via HID")
    print("=" * 60)
    print()

    # Lista todos os dispositivos HID
    print("Procurando dispositivos HID...")
    devices = hid.enumerate()

    jbl_device = None
    for device_info in devices:
        if device_info['vendor_id'] == VENDOR_ID and device_info['product_id'] == PRODUCT_ID:
            jbl_device = device_info
            print(f"Dispositivo encontrado!")
            print(f"  Caminho: {device_info['path']}")
            print(f"  Fabricante: {device_info['manufacturer_string']}")
            print(f"  Produto: {device_info['product_string']}")
            print(f"  Serial: {device_info['serial_number']}")
            print(f"  Interface: {device_info['interface_number']}")
            break

    if jbl_device is None:
        print("Dispositivo não encontrado!")
        return

    print()
    print("=" * 60)
    print("Monitorando comunicação...")
    print("Pressione Ctrl+C para parar\n")

    try:
        # Abre o dispositivo
        device = hid.device()
        device.open_path(jbl_device['path'])

        # Configura modo não-bloqueante se possível
        device.set_nonblocking(True)

        print("Lendo dados do dispositivo...\n")

        battery_level = None

        while True:
            try:
                # Lê dados (máximo 64 bytes)
                data = device.read(64)

                if data:
                    hex_data = ' '.join([f'{b:02x}' for b in data])
                    print(f"[{__import__('time').strftime('%H:%M:%S')}] Dados ({len(data)} bytes): {hex_data}")
                    print(f"  Bytes: {list(data)}")

                    # Tenta interpretar nível de bateria
                    for i, byte in enumerate(data):
                        if 0 <= byte <= 100:
                            if battery_level != byte:
                                battery_level = byte
                                print(f"  ⚡ Nível de bateria: {battery_level}% (posição {i})")

                    # Verifica se há padrão de 16 bits
                    if len(data) >= 2:
                        val_16 = int.from_bytes(data[:2], 'little')
                        if 0 <= val_16 <= 100 and battery_level != val_16:
                            battery_level = val_16
                            print(f"  ⚡ Nível de bateria (16-bit): {battery_level}%")

                    print()

                # Pequeno delay
                __import__('time').sleep(0.1)

            except Exception as e:
                if "would block" not in str(e).lower():
                    print(f"Erro ao ler: {e}")
                __import__('time').sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário")
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            device.close()
        except Exception:
            pass


if __name__ == "__main__":
    find_and_monitor()

