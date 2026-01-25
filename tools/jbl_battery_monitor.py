#!/usr/bin/env python3
"""
Script para interceptar comunicação USB do JBL Quantum910 Wireless
e extrair informações de bateria
"""

import usb.core
import usb.util
import sys
import time
import struct

# IDs do dispositivo JBL Quantum910
VENDOR_ID = 0x0ecb
PRODUCT_ID = 0x2088


def find_device():
    """Encontra o dispositivo USB"""
    device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if device is None:
        raise ValueError("Dispositivo não encontrado. Certifique-se de que o fone está conectado.")
    return device


def setup_device(device):
    """Configura o dispositivo para comunicação"""
    # Tenta desanexar o driver do kernel se necessário
    try:
        if device.is_kernel_driver_active(3):
            device.detach_kernel_driver(3)
    except (ValueError, usb.core.USBError) as e:
        print(f"Aviso: Não foi possível desanexar driver do kernel: {e}")

    # Configura a interface HID (interface 3)
    try:
        usb.util.claim_interface(device, 3)
    except usb.core.USBError as e:
        print(f"Erro ao reivindicar interface: {e}")
        print("Tente executar como root ou configure udev rules")
        sys.exit(1)

    return device


def read_hid_reports(device, timeout=1000):
    """Lê relatórios HID do dispositivo"""
    # Endpoint IN: 0x83 (interface 3, endpoint 3 IN)
    endpoint = device[0][(3, 0)][0]

    print("Monitorando comunicação USB...")
    print("Padrão identificado: [Report ID=0x08, Bateria%]")
    print("Pressione Ctrl+C para parar\n")

    battery_level = None
    last_battery = None
    last_report_id = None
    last_update_time = None
    update_count = 0
    silent_mode = False  # Modo silencioso - só mostra quando muda

    try:
        while True:
            try:
                # Lê dados do endpoint (máximo 64 bytes conforme wMaxPacketSize)
                data = device.read(endpoint.bEndpointAddress, endpoint.wMaxPacketSize, timeout)

                # Converte para lista de bytes
                data_bytes = list(data)

                # Padrão identificado: [Report ID=0x08, Bateria%]
                if len(data_bytes) >= 2:
                    report_id = data_bytes[0]
                    battery = data_bytes[1]

                    # Verifica se é o padrão de bateria conhecido
                    if report_id == 0x08 and 0 <= battery <= 100:
                        update_count += 1
                        current_time = time.time()

                        # Só mostra se mudou ou se é a primeira vez
                        if battery != last_battery or last_battery is None:
                            battery_level = battery
                            timestamp = time.strftime('%H:%M:%S')

                            # Calcula intervalo desde última atualização
                            interval_str = ""
                            if last_update_time:
                                interval = current_time - last_update_time
                                if interval > 1:
                                    interval_str = f" (após {interval:.1f}s)"

                            print(f"\n[{timestamp}] ⚡⚡⚡ BATERIA: {battery_level}% ⚡⚡⚡{interval_str}")

                            # Barra visual
                            bar_length = 20
                            filled = int((battery / 100) * bar_length)
                            bar = "█" * filled + "░" * (bar_length - filled)
                            print(f"  [{bar}] {battery}%")

                            # Status
                            if battery >= 80:
                                status = "🔋 Carregada"
                            elif battery >= 50:
                                status = "🔋 Boa"
                            elif battery >= 20:
                                status = "🔋 Média"
                            else:
                                status = "🔋 Baixa"
                            print(f"  Status: {status}")

                            # Mostra dados brutos
                            hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                            print(f"  Dados: {hex_data} = [Report ID: {report_id}, Bateria: {battery}%]")

                            last_battery = battery
                            last_report_id = report_id
                            last_update_time = current_time
                        elif not silent_mode:
                            # Modo verbose - mostra todas as atualizações
                            timestamp = time.strftime('%H:%M:%S')
                            print(f"[{timestamp}] Bateria: {battery}% (sem mudança) - Total de atualizações: {update_count}")
                    else:
                        # Outros pacotes - mostra apenas se não for silencioso
                        if not silent_mode:
                            hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                            timestamp = time.strftime('%H:%M:%S')
                            print(f"[{timestamp}] Outro pacote: {hex_data}")

                            # Tenta outros métodos para outros pacotes
                            for i, byte in enumerate(data_bytes):
                                if 0 <= byte <= 100:
                                    if battery_level != byte:
                                        battery_level = byte
                                        print(f"  → Possível nível de bateria encontrado: {battery_level}% (byte {i})")

                time.sleep(0.1)  # Pequeno delay para não sobrecarregar

                time.sleep(0.1)  # Pequeno delay para não sobrecarregar

            except usb.core.USBError as e:
                if e.errno == 110:  # ETIMEDOUT
                    # Timeout é normal se não há dados
                    continue
                elif e.errno == 5:  # Input/output error
                    print(f"\n⚠ Erro de I/O USB: Dispositivo pode estar em uso ou desconectado")
                    print(f"   Verifique se o fone está conectado e não está sendo usado por outro programa")
                    print(f"   Aguardando 2 segundos...\n")
                    time.sleep(2)
                else:
                    print(f"⚠ Erro USB: {e} (errno: {e.errno})")
                    time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("📊 RESUMO")
        print("=" * 60)
        if battery_level is not None:
            print(f"⚡ Último nível de bateria: {battery_level}%")
            if last_report_id is not None:
                print(f"📦 Report ID: {last_report_id} (0x{last_report_id:02x})")
            print(f"📈 Total de atualizações recebidas: {update_count}")
            if last_update_time:
                time_since_update = time.time() - last_update_time
                print(f"⏱️  Última atualização há {time_since_update:.1f} segundos")
        else:
            print("⚠ Nenhum dado de bateria recebido")
        print("=" * 60)
    finally:
        # Libera a interface
        try:
            usb.util.release_interface(device, 3)
        except Exception:
            pass


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
    try:
        print(f"Serial: {usb.util.get_string(device, device.iSerialNumber)}")
    except Exception:
        print(f"Serial: (não disponível)")
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
    except Exception:
        pass
    print("=" * 60)
    print()


def main():
    print("JBL Quantum910 - Monitor de Bateria via USB")
    print("=" * 60)
    print()

    try:
        # Encontra o dispositivo
        device = find_device()

        # Obtém informações
        get_device_info(device)

        # Configura o dispositivo
        device = setup_device(device)

        # Inicia monitoramento
        read_hid_reports(device)

    except ValueError as e:
        print(f"Erro: {e}")
        sys.exit(1)
    except PermissionError:
        print("Erro: Permissão negada. Execute como root ou configure udev rules:")
        print("  sudo chmod 666 /dev/bus/usb/001/007")
        print("  ou crie uma regra udev para acesso permanente")
        sys.exit(1)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

