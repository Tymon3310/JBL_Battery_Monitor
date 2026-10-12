#!/usr/bin/env python3
"""
Script que detecta automaticamente o hidraw do JBL Quantum910
e monitora a bateria - funciona mesmo se o número do hidraw mudar
"""

import os
import sys
import time
import glob

VENDOR_ID = "0ecb"
PRODUCT_IDS = ["2088", "205c"]  # 910, 610


def find_hidraw_device():
    """Encontra automaticamente qual hidraw corresponde ao JBL Quantum"""
    # Método 1: Procura em /sys/bus/hid/devices
    for device_dir in glob.glob("/sys/bus/hid/devices/*"):
        vendor_file = os.path.join(device_dir, "idVendor")
        product_file = os.path.join(device_dir, "idProduct")

        if os.path.exists(vendor_file) and os.path.exists(product_file):
            try:
                with open(vendor_file, 'r') as f:
                    vendor = f.read().strip().lower()
                with open(product_file, 'r') as f:
                    product = f.read().strip().lower()

                if vendor == VENDOR_ID and product in PRODUCT_IDS:
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

    # Método 2: Tenta todos os hidraw disponíveis
    print("⚠ Não encontrado em /sys, tentando todos os hidraw disponíveis...")
    for hidraw in sorted(glob.glob("/dev/hidraw*")):
        try:
            # Tenta ler um byte para ver se é o dispositivo correto
            with open(hidraw, 'rb') as f:
                import select
                ready, _, _ = select.select([f], [], [], 0.1)
                if ready:
                    data = f.read(64)
                    if data and len(data) >= 2:
                        data_bytes = list(data)
                        # Verifica se tem o padrão de bateria conhecido
                        if data_bytes[0] == 0x08 and 0 <= data_bytes[1] <= 100:
                            print(f"✓ Encontrado padrão de bateria em {hidraw}")
                            return hidraw
        except Exception:
            pass

    return None


def check_permissions(hidraw_device):
    """Verifica se temos permissão para acessar o hidraw"""
    if not os.path.exists(hidraw_device):
        print(f"Erro: {hidraw_device} não encontrado")
        return False

    if not os.access(hidraw_device, os.R_OK):
        print(f"Erro: Sem permissão para ler {hidraw_device}")
        print(f"Permissões atuais: {oct(os.stat(hidraw_device).st_mode)[-3:]}")
        print("\nSoluções:")
        print(f"1. Execute como root: sudo python3 {sys.argv[0]}")
        print(f"2. Ou ajuste permissões: sudo chmod 666 {hidraw_device}")
        return False

    return True


def read_battery():
    """Lê e exibe o nível de bateria"""
    print("JBL Quantum - Monitor de Bateria (Detecção Automática)")
    print("=" * 60)

    # Detecta o dispositivo
    print("Procurando dispositivo...")
    hidraw_device = find_hidraw_device()

    if not hidraw_device:
        print("\n✗ Dispositivo JBL Quantum não encontrado")
        print("\nPossíveis causas:")
        print("1. O fone não está conectado via USB")
        print("2. O dispositivo não está sendo reconhecido como HID")
        print("3. Verifique com: lsusb | grep JBL")
        print("\n💡 Dica: Tente desconectar e reconectar o fone")
        sys.exit(1)

    print(f"✓ Dispositivo encontrado: {hidraw_device}")
    print("Padrão identificado: [Report ID=0x08, Bateria%]")
    print("Exemplo: 08 1e = [8, 30] = 30% de bateria")
    print()

    if not check_permissions(hidraw_device):
        sys.exit(1)

    print("Monitorando nível de bateria...")
    print("Pressione Ctrl+C para parar\n")

    last_battery = None
    last_report_id = None
    last_update_time = None
    update_count = 0

    try:
        with open(hidraw_device, 'rb') as f:
            print("Aguardando dados... (O dispositivo envia periodicamente)\n")
            print("=" * 60)

            while True:
                try:
                    # Lê dados (máximo 64 bytes)
                    data = f.read(64)

                    if data and len(data) >= 2:
                        data_bytes = list(data)
                        report_id = data_bytes[0]
                        battery = data_bytes[1]

                        # Verifica se é um pacote de bateria válido
                        if report_id == 0x08 and 0 <= battery <= 100:
                            update_count += 1
                            current_time = time.time()

                            # Só mostra se mudou ou se é a primeira vez
                            if battery != last_battery or last_battery is None:
                                timestamp = time.strftime('%H:%M:%S')

                                # Calcula intervalo desde última atualização
                                interval_str = ""
                                if last_update_time:
                                    interval = current_time - last_update_time
                                    if interval > 1:
                                        interval_str = f" (após {interval:.1f}s)"

                                print(f"\n[{timestamp}] ⚡ BATERIA: {battery}%{interval_str}")

                                # Barra visual de bateria
                                bar_length = 20
                                filled = int((battery / 100) * bar_length)
                                bar = "█" * filled + "░" * (bar_length - filled)
                                print(f"  [{bar}] {battery}%")

                                # Status da bateria
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
                                hex_data = ' '.join([f'{b:02x}' for b in data_bytes[:min(8, len(data_bytes))]])
                                print(f"  Dados: {hex_data} = [Report ID: {report_id}, Bateria: {battery}%]")
                                print()

                                last_battery = battery
                                last_report_id = report_id
                                last_update_time = current_time

                    time.sleep(0.1)

                except BlockingIOError:
                    # Não há dados disponíveis - normal
                    time.sleep(0.5)
                except OSError as e:
                    # Erros de I/O (dispositivo desconectado, em uso, etc)
                    if e.errno == 5:  # Input/output error
                        print(f"\n⚠ Erro de I/O: Dispositivo pode estar em uso ou desconectado")
                        print(f"   Verifique se o fone está conectado e não está sendo usado por outro programa")
                        print(f"   Aguardando 2 segundos antes de tentar novamente...\n")
                        time.sleep(2)
                        # Tenta detectar novamente
                        new_hidraw = find_hidraw_device()
                        if new_hidraw and new_hidraw != hidraw_device:
                            print(f"⚠ Dispositivo mudou de {hidraw_device} para {new_hidraw}")
                            print("   Reconectando...")
                            hidraw_device = new_hidraw
                            f.close()
                            f = open(hidraw_device, 'rb')
                    else:
                        print(f"⚠ Erro de sistema: {e} (errno: {e.errno})")
                        time.sleep(1)
                except Exception as e:
                    print(f"⚠ Erro inesperado: {e}")
                    time.sleep(1)

    except PermissionError:
        print(f"Erro: Permissão negada para {hidraw_device}")
        print("Execute como root ou ajuste permissões")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("📊 RESUMO")
        print("=" * 60)
        if last_battery is not None:
            print(f"⚡ Último nível de bateria: {last_battery}%")
            print(f"📦 Report ID: {last_report_id} (0x{last_report_id:02x})")
            print(f"📈 Total de atualizações recebidas: {update_count}")
            if last_update_time:
                time_since_update = time.time() - last_update_time
                print(f"⏱️  Última atualização há {time_since_update:.1f} segundos")
        else:
            print("⚠ Nenhum dado de bateria recebido")
        print("=" * 60)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    read_battery()

