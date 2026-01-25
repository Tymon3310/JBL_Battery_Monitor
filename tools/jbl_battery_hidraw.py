#!/usr/bin/env python3
"""
Script para ler dados do JBL Quantum910 via hidraw
Tenta usar hidraw, mas usa pyusb como fallback se não funcionar
"""

import os
import sys
import time
import struct


# Tenta detectar o hidraw automaticamente
def find_hidraw_device():
    """Encontra automaticamente qual hidraw corresponde ao JBL Quantum910"""
    import glob
    VENDOR_ID = "0ecb"
    PRODUCT_ID = "2088"

    # Procura em /sys/bus/hid/devices
    for device_dir in glob.glob("/sys/bus/hid/devices/*"):
        vendor_file = os.path.join(device_dir, "idVendor")
        product_file = os.path.join(device_dir, "idProduct")

        if os.path.exists(vendor_file) and os.path.exists(product_file):
            try:
                with open(vendor_file, 'r') as f:
                    vendor = f.read().strip().lower()
                with open(product_file, 'r') as f:
                    product = f.read().strip().lower()

                if vendor == VENDOR_ID and product == PRODUCT_ID:
                    # Encontrou! Procura o hidraw
                    hidraw_path = os.path.join(device_dir, "hidraw")
                    if os.path.exists(hidraw_path):
                        hidraw_dirs = [d for d in os.listdir(hidraw_path) if d.startswith("hidraw")]
                        if hidraw_dirs:
                            hidraw_device = f"/dev/{hidraw_dirs[0]}"
                            if os.path.exists(hidraw_device):
                                return hidraw_device
            except Exception:
                pass

    # Fallback: tenta hidraw comum
    for i in range(10):
        hidraw = f"/dev/hidraw{i}"
        if os.path.exists(hidraw):
            return hidraw

    return None


HIDRAW_DEVICE = find_hidraw_device()
USE_PYUSB_FALLBACK = True  # Usa pyusb se hidraw não funcionar


def check_permissions():
    """Verifica se temos permissão para acessar o hidraw"""
    if not os.path.exists(HIDRAW_DEVICE):
        print(f"Erro: {HIDRAW_DEVICE} não encontrado")
        return False

    if not os.access(HIDRAW_DEVICE, os.R_OK):
        print(f"Erro: Sem permissão para ler {HIDRAW_DEVICE}")
        print(f"Permissões atuais: {oct(os.stat(HIDRAW_DEVICE).st_mode)[-3:]}")
        print("\nSoluções:")
        print(f"1. Execute como root: sudo python3 {sys.argv[0]}")
        print(f"2. Ou ajuste permissões: sudo chmod 666 {HIDRAW_DEVICE}")
        return False

    return True


def analyze_byte(byte_val, position):
    """Analisa um byte individual e retorna interpretações possíveis"""
    interpretations = []

    # Interpretação como porcentagem
    if 0 <= byte_val <= 100:
        interpretations.append(f"Possível porcentagem: {byte_val}%")

    # Interpretação como booleano/flags
    if byte_val in [0, 1]:
        interpretations.append(f"Booleano: {bool(byte_val)}")

    # Interpretação como código ASCII (se imprimível)
    if 32 <= byte_val <= 126:
        interpretations.append(f"ASCII: '{chr(byte_val)}'")

    # Interpretação como status code comum
    status_codes = {0: "OK/Desligado", 1: "Ativo", 255: "Máximo/Desconhecido"}
    if byte_val in status_codes:
        interpretations.append(f"Status: {status_codes[byte_val]}")

    # Bits individuais
    if byte_val > 0 and byte_val < 256:
        bits = format(byte_val, '08b')
        set_bits = [i for i, bit in enumerate(bits) if bit == '1']
        if len(set_bits) <= 4:  # Se poucos bits setados, pode ser flags
            interpretations.append(f"Bits setados: {set_bits} (bin: {bits})")

    return interpretations


def analyze_data(data_bytes, last_data=None):
    """Analisa os dados recebidos em detalhes"""
    analysis = []

    # Análise byte a byte
    analysis.append("\n  📊 ANÁLISE DETALHADA:")
    analysis.append("  " + "-" * 56)

    for i, byte_val in enumerate(data_bytes):
        interpretations = analyze_byte(byte_val, i)
        if interpretations:
            analysis.append(f"  Byte[{i:2d}] = 0x{byte_val:02x} ({byte_val:3d}) | {', '.join(interpretations[:2])}")
        else:
            analysis.append(f"  Byte[{i:2d}] = 0x{byte_val:02x} ({byte_val:3d})")

    # Análise de padrões multi-byte
    analysis.append("\n  🔍 ANÁLISE DE PADRÕES:")
    analysis.append("  " + "-" * 56)

    # Valores 16-bit little-endian
    if len(data_bytes) >= 2:
        for i in range(len(data_bytes) - 1):
            val_le = struct.unpack('<H', bytes(data_bytes[i:i+2]))[0]
            val_be = struct.unpack('>H', bytes(data_bytes[i:i+2]))[0]
            if 0 <= val_le <= 65535:
                analysis.append(f"  Bytes[{i}-{i+1}] LE: {val_le} | BE: {val_be}")
                if 0 <= val_le <= 100:
                    analysis.append(f"    → Possível bateria (LE): {val_le}%")

    # Valores 32-bit
    if len(data_bytes) >= 4:
        for i in range(len(data_bytes) - 3):
            val_le = struct.unpack('<I', bytes(data_bytes[i:i+4]))[0]
            if val_le < 1000000:  # Valores razoáveis
                analysis.append(f"  Bytes[{i}-{i+3}] LE: {val_le}")

    # Comparação com dados anteriores
    if last_data and len(data_bytes) == len(last_data):
        analysis.append("\n  🔄 COMPARAÇÃO COM DADOS ANTERIORES:")
        analysis.append("  " + "-" * 56)
        changes = []
        for i, (curr, prev) in enumerate(zip(data_bytes, last_data)):
            if curr != prev:
                changes.append(f"Byte[{i}]: {prev:3d} → {curr:3d} (Δ{curr-prev:+d})")
        if changes:
            for change in changes[:10]:  # Limita a 10 mudanças
                analysis.append(f"  {change}")
        else:
            analysis.append("  (Nenhuma mudança detectada)")

    # Análise de estrutura HID comum
    analysis.append("\n  🎯 INTERPRETAÇÕES HID:")
    analysis.append("  " + "-" * 56)

    # Report ID (geralmente primeiro byte)
    if len(data_bytes) > 0:
        if data_bytes[0] > 0:
            analysis.append(f"  Report ID: 0x{data_bytes[0]:02x} ({data_bytes[0]})")

    # Possíveis campos de bateria
    battery_candidates = []
    for i, byte_val in enumerate(data_bytes):
        if 0 <= byte_val <= 100:
            battery_candidates.append((i, byte_val))

    if battery_candidates:
        analysis.append(f"  ⚡ Candidatos a bateria encontrados:")
        for pos, val in battery_candidates:
            analysis.append(f"    Posição {pos}: {val}%")
    else:
        analysis.append("  ⚡ Nenhum candidato óbvio a bateria (0-100)")

    # Análise de sequências
    if len(data_bytes) >= 3:
        # Procura por sequências crescentes/decrescentes
        sequences = []
        for i in range(len(data_bytes) - 2):
            seq = data_bytes[i:i+3]
            if seq[0] < seq[1] < seq[2]:
                sequences.append(f"Bytes[{i}-{i+2}]: Crescente {seq}")
            elif seq[0] > seq[1] > seq[2]:
                sequences.append(f"Bytes[{i}-{i+2}]: Decrescente {seq}")
        if sequences:
            analysis.append("\n  📈 SEQUÊNCIAS DETECTADAS:")
            for seq in sequences[:3]:
                analysis.append(f"  {seq}")

    return "\n".join(analysis)


def read_with_pyusb_fallback():
    """Fallback usando pyusb se hidraw não funcionar"""
    try:
        import usb.core
        import usb.util

        VENDOR_ID = 0x0ecb
        PRODUCT_ID = 0x2088

        device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if device is None:
            return False

        try:
            if device.is_kernel_driver_active(3):
                device.detach_kernel_driver(3)
        except Exception:
            pass

        usb.util.claim_interface(device, 3)
        endpoint = device[0][(3, 0)][0]

        print("✓ Usando pyusb (fallback do hidraw)")
        print("Monitorando comunicação...\n")

        while True:
            try:
                data = device.read(endpoint.bEndpointAddress, endpoint.wMaxPacketSize, 1000)
                data_bytes = list(data)

                if data_bytes:
                    hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
                    timestamp = time.strftime('%H:%M:%S')
                    print(f"[{timestamp}] Dados ({len(data_bytes)} bytes): {hex_data}")

                    if len(data_bytes) >= 2 and data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                        print(f"  ⚡⚡⚡ BATERIA: {data_bytes[1]}% ⚡⚡⚡")
                    print()
            except usb.core.USBError as e:
                if e.errno != 110:  # Não é timeout
                    break
            time.sleep(0.1)

        usb.util.release_interface(device, 3)
        return True
    except Exception:
        return False


def read_hidraw(save_log=False):
    """Lê dados do dispositivo hidraw"""
    print("JBL Quantum910 - Monitor Completo de Dados via HIDRAW")
    print("=" * 60)

    if HIDRAW_DEVICE:
        print(f"Dispositivo: {HIDRAW_DEVICE}")
    else:
        print("Dispositivo: (não encontrado, usando pyusb)")
    print()

    if HIDRAW_DEVICE and os.path.exists(HIDRAW_DEVICE):
        if not check_permissions():
            if USE_PYUSB_FALLBACK:
                print("Tentando usar pyusb como fallback...\n")
                if read_with_pyusb_fallback():
                    return
            sys.exit(1)
    else:
        if USE_PYUSB_FALLBACK:
            print("Hidraw não encontrado, usando pyusb...\n")
            if read_with_pyusb_fallback():
                return
        print("Erro: Hidraw não encontrado e pyusb fallback não disponível")
        sys.exit(1)

    log_file = None
    if save_log:
        log_filename = f"/tmp/jbl_battery_log_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')
        print(f"💾 Salvando log em: {log_filename}")
        print()

    print("Monitorando TODOS os dados recebidos...")
    print("Pressione Ctrl+C para parar\n")

    battery_level = None
    last_data = None
    packet_count = 0
    all_packets = []  # Armazena todos os pacotes para análise

    def log_output(text):
        """Escreve no console e no arquivo de log"""
        print(text, end='')
        if log_file:
            log_file.write(text)
            log_file.flush()

    try:
        with open(HIDRAW_DEVICE, 'rb') as f:
            print("Aguardando dados do dispositivo...")
            print("(Tente usar o fone - reproduzir áudio, ajustar volume, etc.)\n")
            print("=" * 60)

            while True:
                try:
                    # Lê dados (máximo 64 bytes, conforme wMaxPacketSize)
                    data = f.read(64)

                    if data:
                        data_bytes = list(data)
                        packet_count += 1

                        # Ignora dados duplicados consecutivos (mas mostra que recebeu)
                        if data_bytes == last_data:
                            time.sleep(0.1)
                            continue

                        timestamp = time.strftime('%H:%M:%S.%f')[:-3]
                        all_packets.append((timestamp, data_bytes.copy()))

                        # ========== EXIBIÇÃO COMPLETA DOS DADOS ==========
                        output = []
                        output.append(f"\n{'='*60}\n")
                        output.append(f"📦 PACOTE #{packet_count} - {timestamp}\n")
                        output.append(f"{'='*60}\n")
                        output.append(f"Tamanho: {len(data_bytes)} bytes\n")
                        output.append("\n")

                        # Formato hexadecimal com espaçamento
                        output.append("🔢 DADOS EM HEXADECIMAL:\n")
                        output.append("  " + " ".join([f"{b:02x}" for b in data_bytes]) + "\n")
                        output.append("\n")

                        # Formato hexadecimal agrupado (8 bytes por linha)
                        output.append("🔢 HEXADECIMAL FORMATADO (8 bytes/linha):\n")
                        for i in range(0, len(data_bytes), 8):
                            chunk = data_bytes[i:i+8]
                            hex_chunk = " ".join([f"{b:02x}" for b in chunk])
                            offset = f"{i:02d}"
                            output.append(f"  [{offset}] {hex_chunk}\n")
                        output.append("\n")

                        # Formato decimal
                        output.append("🔢 DADOS EM DECIMAL:\n")
                        output.append("  " + " ".join([f"{b:3d}" for b in data_bytes]) + "\n")
                        output.append("\n")

                        # Tabela detalhada byte a byte
                        output.append("📋 TABELA DETALHADA (Byte | Hex | Dec | Bin | ASCII):\n")
                        output.append("  " + "-" * 56 + "\n")
                        for i, byte_val in enumerate(data_bytes):
                            hex_str = f"0x{byte_val:02x}"
                            dec_str = f"{byte_val:3d}"
                            bin_str = format(byte_val, '08b')
                            ascii_str = chr(byte_val) if 32 <= byte_val <= 126 else '.'
                            output.append(f"  [{i:2d}] {hex_str:4s} | {dec_str:3s} | {bin_str} | '{ascii_str}'\n")
                        output.append("\n")

                        # Análise detalhada
                        analysis = analyze_data(data_bytes, last_data)
                        output.append(analysis)
                        output.append("\n\n")

                        # Tenta identificar bateria
                        found_battery = False
                        for i, byte_val in enumerate(data_bytes):
                            if 0 <= byte_val <= 100:
                                if battery_level != byte_val:
                                    battery_level = byte_val
                                    found_battery = True
                                    output.append(f"  ⚡⚡⚡ NÍVEL DE BATERIA DETECTADO: {battery_level}% (byte {i}) ⚡⚡⚡\n")

                        if not found_battery:
                            output.append("  ⚠ Nenhum valor de bateria óbvio detectado neste pacote\n")

                        output.append(f"{'='*60}\n\n")

                        # Exibe tudo
                        output_text = "".join(output)
                        log_output(output_text)

                        last_data = data_bytes

                    time.sleep(0.1)

                except BlockingIOError:
                    # Não há dados disponíveis
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Erro ao ler: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)

    except PermissionError:
        print(f"Erro: Permissão negada para {HIDRAW_DEVICE}")
        print("Execute como root ou ajuste permissões")
        sys.exit(1)
    except KeyboardInterrupt:
        summary = []
        summary.append("\n\n" + "=" * 60 + "\n")
        summary.append("📊 RESUMO DA SESSÃO\n")
        summary.append("=" * 60 + "\n")
        summary.append(f"Total de pacotes recebidos: {packet_count}\n")
        if battery_level is not None:
            summary.append(f"⚡ Último nível de bateria detectado: {battery_level}%\n")
        else:
            summary.append("⚠ Nenhum nível de bateria foi detectado automaticamente\n")

        # Análise de todos os pacotes únicos
        if all_packets:
            unique_packets = {}
            for ts, data in all_packets:
                data_str = " ".join([f"{b:02x}" for b in data])
                if data_str not in unique_packets:
                    unique_packets[data_str] = (ts, data)
            summary.append(f"Pacotes únicos: {len(unique_packets)} de {packet_count}\n")

        summary.append("\n💡 Dica: Analise os dados brutos acima para identificar padrões\n")
        if log_file:
            summary.append(f"💾 Log completo salvo em: {log_file.name}\n")
        summary.append("=" * 60 + "\n")

        log_output("".join(summary))

        if log_file:
            log_file.close()
            print(f"\n💾 Log salvo em: {log_file.name}")
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Monitor de bateria JBL Quantum910')
    parser.add_argument('--log', '-l', action='store_true',
                        help='Salvar log completo em arquivo')
    args = parser.parse_args()

    # Tenta hidraw primeiro, depois pyusb como fallback
    try:
        read_hidraw(save_log=args.log)
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"\n⚠ Erro com hidraw: {e}")
        if USE_PYUSB_FALLBACK:
            print("Tentando usar pyusb como fallback...\n")
            if not read_with_pyusb_fallback():
                print("✗ Não foi possível usar nenhum método")
                sys.exit(1)
        else:
            raise

