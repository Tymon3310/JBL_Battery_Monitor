#!/usr/bin/env python3
"""
Script para capturar o que acontece durante conexão/desconexão
e tentar forçar o envio de informações de bateria
"""

import os
import sys
import time
import struct
import fcntl

HIDRAW_DEVICE = "/dev/hidraw5"

# IOCTLs para HID
HIDIOCSFEATURE = lambda len: 0xC0094806 | (len << 16)  # Enviar feature report
HIDIOCGFEATURE = lambda len: 0xC0094807 | (len << 16)  # Receber feature report


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


def send_feature_report(fd, report_id, data=None):
    """Envia um feature report usando ioctl"""
    if data is None:
        payload = bytes([report_id] + [0] * 63)
    else:
        payload = bytes([report_id] + list(data[:63]))

    try:
        fcntl.ioctl(fd, HIDIOCSFEATURE(len(payload)), payload)
        return True
    except Exception:
        return False


def get_feature_report(fd, report_id, length=64):
    """Recebe um feature report usando ioctl"""
    payload = bytes([report_id] + [0] * (length - 1))
    try:
        fcntl.ioctl(fd, HIDIOCGFEATURE(length), payload)
        return list(payload)
    except Exception:
        return None


def monitor_connection():
    """Monitora durante conexão para capturar o que acontece"""
    print("JBL Quantum910 - Captura de Dados Durante Conexão")
    print("=" * 60)
    print(f"Dispositivo: {HIDRAW_DEVICE}")
    print()

    if not check_permissions():
        sys.exit(1)

    print("📋 INSTRUÇÕES:")
    print("1. O script vai monitorar continuamente")
    print("2. DESCONECTE o fone USB")
    print("3. CONECTE o fone USB novamente")
    print("4. O script vai capturar tudo que acontece")
    print()
    print("Pressione Ctrl+C para parar\n")
    print("=" * 60)

    last_seen = os.path.exists(HIDRAW_DEVICE)
    packets_during_connection = []

    try:
        while True:
            # Verifica se dispositivo está conectado
            if os.path.exists(HIDRAW_DEVICE):
                if not last_seen:
                    # Dispositivo acabou de ser conectado!
                    print(f"\n{'='*60}")
                    print(f"🔌 DISPOSITIVO CONECTADO - {time.strftime('%H:%M:%S')}")
                    print(f"{'='*60}\n")

                    time.sleep(0.5)  # Aguarda estabilizar

                    # Abre e monitora intensamente
                    with open(HIDRAW_DEVICE, 'rb') as f:
                        print("📡 Capturando dados durante inicialização...")
                        print("-" * 60)

                        # Lê tudo que vem nos primeiros segundos
                        start_time = time.time()
                        import select
                        while time.time() - start_time < 3:  # 3 segundos
                            try:
                                # Usa select para não bloquear
                                ready, _, _ = select.select([f], [], [], 0.1)
                                if not ready:
                                    continue
                                data = f.read(64)
                                if data:
                                    data_bytes = list(data)
                                    hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                                    timestamp = time.strftime('%H:%M:%S.%f')[:-3]

                                    print(f"[{timestamp}] 📥 Recebido ({len(data_bytes)} bytes)")
                                    print(f"  Hex: {hex_data}")
                                    print(f"  Dec: {data_bytes}")

                                    # Verifica se é bateria
                                    if len(data_bytes) >= 2:
                                        if data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                                            print(f"  ⚡⚡⚡ BATERIA: {data_bytes[1]}% ⚡⚡⚡")

                                        # Análise do pacote
                                        print(f"  📊 Análise:")
                                        print(f"    - Byte[0] (Report ID): 0x{data_bytes[0]:02x} ({data_bytes[0]})")
                                        if len(data_bytes) > 1:
                                            print(f"    - Byte[1] (Bateria?): 0x{data_bytes[1]:02x} ({data_bytes[1]})")

                                    packets_during_connection.append(data_bytes)
                                    print()

                            except Exception:
                                pass

                        print(f"✓ Capturados {len(packets_during_connection)} pacotes durante conexão")
                        print("-" * 60)

                        # Agora tenta forçar com feature reports
                        print("\n🔧 Tentando forçar envio de bateria...")
                        print("-" * 60)

                        # Tenta diferentes feature reports
                        for report_id in [0x08, 0x01, 0x02, 0x03, 0x04, 0x05]:
                            print(f"\n📤 Tentando Feature Report 0x{report_id:02x}...")

                            # Tenta receber feature report
                            try:
                                with open(HIDRAW_DEVICE, 'rb+') as f2:
                                    result = get_feature_report(f2.fileno(), report_id)
                                    if result:
                                        hex_resp = ' '.join([f'{b:02x}' for b in result[:8]])
                                        print(f"  📥 Resposta: {hex_resp}")

                                        if len(result) >= 2 and result[0] == 0x08 and 0 <= result[1] <= 100:
                                            print(f"  ⚡⚡⚡ BATERIA: {result[1]}% ⚡⚡⚡")
                                    else:
                                        print(f"  (Sem resposta)")

                                    # Tenta enviar feature report
                                    if send_feature_report(f2.fileno(), report_id):
                                        print(f"  ✓ Comando enviado")
                                        time.sleep(0.2)

                                    # Tenta ler resposta
                                    try:
                                        import select
                                        ready, _, _ = select.select([f2], [], [], 0.3)
                                        if ready:
                                            resp = f2.read(64)
                                            if resp:
                                                resp_bytes = list(resp)
                                                hex_resp = ' '.join([f'{b:02x}' for b in resp_bytes[:8]])
                                                print(f"  📥 Resposta: {hex_resp}")

                                                if len(resp_bytes) >= 2 and resp_bytes[0] == 0x08 and 0 <= resp_bytes[1] <= 100:
                                                    print(f"  ⚡⚡⚡ BATERIA: {resp_bytes[1]}% ⚡⚡⚡")
                                    except Exception:
                                        pass
                            except Exception as e:
                                print(f"  ✗ Erro: {e}")

                            time.sleep(0.2)

                last_seen = True

                # Monitora continuamente
                try:
                    with open(HIDRAW_DEVICE, 'rb') as f:
                        import select
                        ready, _, _ = select.select([f], [], [], 0.5)
                        if ready:
                            data = f.read(64)
                            if data:
                                data_bytes = list(data)
                                hex_data = ' '.join([f'{b:02x}' for b in data_bytes])

                                if len(data_bytes) >= 2 and data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                                    timestamp = time.strftime('%H:%M:%S')
                                    print(f"[{timestamp}] ⚡ BATERIA: {data_bytes[1]}%")
                except Exception:
                    pass
            else:
                if last_seen:
                    print(f"\n🔌 Dispositivo desconectado - {time.strftime('%H:%M:%S')}")
                    packets_during_connection = []
                last_seen = False

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("📊 RESUMO")
        print("=" * 60)
        if packets_during_connection:
            print(f"Pacotes capturados durante conexão: {len(packets_during_connection)}")
            print("\nPacotes únicos:")
            seen = set()
            for pkt in packets_during_connection:
                pkt_str = ' '.join([f'{b:02x}' for b in pkt])
                if pkt_str not in seen:
                    print(f"  {pkt_str}")
                    seen.add(pkt_str)
        print("=" * 60)


if __name__ == "__main__":
    monitor_connection()

