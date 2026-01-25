#!/usr/bin/env python3
"""
Script para forçar o envio de informações de bateria do JBL Quantum910
Analisa o que é enviado durante conexão e tenta replicar comandos
"""

import os
import sys
import time
import struct

HIDRAW_DEVICE = "/dev/hidraw5"


def check_permissions():
    """Verifica se temos permissão para acessar o hidraw"""
    if not os.path.exists(HIDRAW_DEVICE):
        print(f"Erro: {HIDRAW_DEVICE} não encontrado")
        return False

    if not os.access(HIDRAW_DEVICE, os.R_OK | os.W_OK):
        print(f"Erro: Sem permissão para ler/escrever {HIDRAW_DEVICE}")
        print(f"Permissões atuais: {oct(os.stat(HIDRAW_DEVICE).st_mode)[-3:]}")
        print("\nSoluções:")
        print(f"1. Execute como root: sudo python3 {sys.argv[0]}")
        print(f"2. Ou ajuste permissões: sudo chmod 666 {HIDRAW_DEVICE}")
        return False

    return True


def send_feature_report(device, report_id, data=None):
    """Envia um feature report HID (comando para o dispositivo)"""
    # Feature reports geralmente começam com o Report ID
    if data is None:
        payload = bytes([report_id] + [0] * 63)  # 64 bytes total
    else:
        payload = bytes([report_id] + list(data[:63]))  # Report ID + dados

    try:
        # IOCTL para enviar feature report
        # Linux usa ioctl HIDIOCSFEATURE
        import fcntl
        import termios

        # HIDIOCSFEATURE(len) - envia feature report
        # HIDIOCGFEATURE(len) - recebe feature report
        HIDIOCSFEATURE = 0xC0094806  # _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x06, len)
        HIDIOCGFEATURE = 0xC0094807  # _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x07, len)

        # Tenta enviar feature report
        result = fcntl.ioctl(device.fileno(), HIDIOCSFEATURE, payload)
        return True
    except Exception as e:
        print(f"  Erro ao enviar feature report: {e}")
        return False


def try_commands(device):
    """Tenta diferentes comandos para solicitar bateria"""
    print("\n🔧 Tentando enviar comandos para solicitar bateria...")
    print("=" * 60)

    # Comandos comuns para solicitar bateria em dispositivos HID
    commands_to_try = [
        # Comando simples com Report ID 0x08 (o que recebemos)
        (0x08, [0x08]),

        # Feature report com Report ID 0x08
        (0x08, None),

        # Outros Report IDs comuns
        (0x01, [0x01]),
        (0x02, [0x02]),
        (0x03, [0x03]),
        (0x04, [0x04]),
        (0x05, [0x05]),
        (0x06, [0x06]),
        (0x07, [0x07]),
        (0x09, [0x09]),

        # Comandos de solicitação de status
        (0x01, [0x01, 0x00]),  # Solicitar status
        (0x08, [0x08, 0x00]),  # Solicitar bateria especificamente

        # Padrão comum: [Report ID, Comando, ...]
        (0x08, [0x08, 0x01]),  # Comando 0x01 = solicitar
        (0x08, [0x08, 0x02]),  # Comando 0x02 = status
    ]

    for report_id, data in commands_to_try:
        hex_cmd = ' '.join([f'{b:02x}' for b in ([report_id] + (data or []))[:8]])
        print(f"\n📤 Tentando: Report ID 0x{report_id:02x}, Dados: {hex_cmd}")

        # Tenta escrever diretamente no hidraw
        try:
            if data:
                cmd_bytes = bytes([report_id] + list(data))
            else:
                cmd_bytes = bytes([report_id] + [0] * 63)

            device.write(cmd_bytes)
            print(f"  ✓ Comando enviado: {hex_cmd}")

            # Aguarda resposta
            time.sleep(0.3)

            # Tenta ler resposta (sem settimeout, usa select ou polling)
            import select
            ready, _, _ = select.select([device], [], [], 0.5)
            if ready:
                try:
                    response = device.read(64)
                    if response:
                        resp_bytes = list(response)
                        hex_resp = ' '.join([f'{b:02x}' for b in resp_bytes[:8]])
                        print(f"  📥 Resposta recebida: {hex_resp}")

                        # Verifica se é bateria
                        if len(resp_bytes) >= 2 and resp_bytes[0] == 0x08 and 0 <= resp_bytes[1] <= 100:
                            print(f"  ⚡⚡⚡ BATERIA ENCONTRADA: {resp_bytes[1]}% ⚡⚡⚡")
                            return resp_bytes[1]
                except Exception:
                    pass
            else:
                # Tenta ler mesmo sem select (pode bloquear, mas tentamos)
                try:
                    # Configura modo não-bloqueante se possível
                    import fcntl
                    flags = fcntl.fcntl(device.fileno(), fcntl.F_GETFL)
                    fcntl.fcntl(device.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)

                    response = device.read(64)
                    if response:
                        resp_bytes = list(response)
                        hex_resp = ' '.join([f'{b:02x}' for b in resp_bytes[:8]])
                        print(f"  📥 Resposta recebida: {hex_resp}")

                        if len(resp_bytes) >= 2 and resp_bytes[0] == 0x08 and 0 <= resp_bytes[1] <= 100:
                            print(f"  ⚡⚡⚡ BATERIA ENCONTRADA: {resp_bytes[1]}% ⚡⚡⚡")
                            return resp_bytes[1]

                    # Restaura flags
                    fcntl.fcntl(device.fileno(), fcntl.F_SETFL, flags)
                except Exception:
                    pass

        except Exception as e:
            print(f"  ✗ Erro: {e}")

        time.sleep(0.1)

    return None


def monitor_connection():
    """Monitora durante conexão/desconexão para capturar comandos"""
    print("JBL Quantum910 - Análise de Conexão e Forçar Bateria")
    print("=" * 60)
    print(f"Dispositivo: {HIDRAW_DEVICE}")
    print()

    if not check_permissions():
        sys.exit(1)

    print("📋 INSTRUÇÕES:")
    print("1. Este script vai monitorar o dispositivo")
    print("2. DESCONECTE o fone USB agora")
    print("3. Aguarde 2 segundos")
    print("4. CONECTE o fone USB novamente")
    print("5. O script vai capturar tudo que acontece")
    print()
    print("Pressione Enter quando estiver pronto para começar...")
    input()

    print("\n⏳ Aguardando desconexão...")
    print("(Desconecte o fone USB agora)")

    # Monitora até o dispositivo desaparecer
    while os.path.exists(HIDRAW_DEVICE):
        time.sleep(0.1)

    print("✓ Dispositivo desconectado")
    time.sleep(2)

    print("\n⏳ Aguardando reconexão...")
    print("(Conecte o fone USB agora)")

    # Aguarda reconexão
    timeout = 10
    start_time = time.time()
    while not os.path.exists(HIDRAW_DEVICE):
        if time.time() - start_time > timeout:
            print("✗ Timeout: Dispositivo não reconectado")
            sys.exit(1)
        time.sleep(0.1)

    print("✓ Dispositivo reconectado!")
    time.sleep(0.5)  # Aguarda estabilizar

    # Agora monitora tudo que acontece
    print("\n📡 Monitorando comunicação durante inicialização...")
    print("=" * 60)

    try:
        with open(HIDRAW_DEVICE, 'rb+') as f:  # rb+ para leitura e escrita
            # Primeiro, tenta ler tudo que o dispositivo envia
            print("\n📥 Lendo dados recebidos do dispositivo...")
            packets_received = []

            for i in range(20):  # Tenta ler até 20 pacotes
                try:
                    f.settimeout(0.5)
                    data = f.read(64)
                    if data:
                        data_bytes = list(data)
                        hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                        timestamp = time.strftime('%H:%M:%S.%f')[:-3]
                        print(f"[{timestamp}] 📥 Recebido ({len(data_bytes)} bytes): {hex_data}")

                        # Verifica se é bateria
                        if len(data_bytes) >= 2 and data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                            print(f"  ⚡⚡⚡ BATERIA: {data_bytes[1]}% ⚡⚡⚡")

                        packets_received.append(data_bytes)
                    else:
                        break
                except Exception:
                    break
                time.sleep(0.1)

            # Agora tenta enviar comandos
            if packets_received:
                print(f"\n✓ Recebidos {len(packets_received)} pacotes durante inicialização")
                print("\nAgora tentando forçar envio de bateria com comandos...")
            else:
                print("\n⚠ Nenhum pacote recebido automaticamente")
                print("Tentando forçar com comandos...")

            battery = try_commands(f)

            if battery is not None:
                print(f"\n✅ SUCESSO! Bateria obtida: {battery}%")
            else:
                print("\n⚠ Não foi possível forçar o envio de bateria")
                print("Os comandos tentados não funcionaram.")
                print("\n💡 Dica: O dispositivo pode enviar bateria apenas:")
                print("  - Durante inicialização (conexão)")
                print("  - Quando você pressiona botões")
                print("  - Em intervalos específicos")

            # Continua monitorando
            print("\n📡 Continuando monitoramento... (Ctrl+C para parar)")
            print("=" * 60)

            last_battery = None
            while True:
                try:
                    f.settimeout(1.0)
                    data = f.read(64)
                    if data:
                        data_bytes = list(data)
                        hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                        timestamp = time.strftime('%H:%M:%S')

                        if len(data_bytes) >= 2 and data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                            battery = data_bytes[1]
                            if battery != last_battery:
                                print(f"[{timestamp}] ⚡ BATERIA: {battery}%")
                                last_battery = battery
                        else:
                            print(f"[{timestamp}] Dados: {hex_data}")

                except Exception:
                    time.sleep(0.5)

    except PermissionError:
        print(f"Erro: Permissão negada para {HIDRAW_DEVICE}")
        print("Execute como root ou ajuste permissões")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário")
    except Exception as e:
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    monitor_connection()

