#!/usr/bin/env python3
"""
Script simplificado para monitorar apenas o nível de bateria do JBL Quantum910
Usa pyusb (como jbl_battery_monitor.py) para garantir compatibilidade
"""

import sys
import time
import os
from datetime import datetime

try:
    import usb.core
    import usb.util
except ImportError:
    print("Erro: pyusb não instalado")
    print("Execute: pip3 install pyusb --user")
    print("Ou para root: sudo pip3 install pyusb")
    sys.exit(1)

# IDs do dispositivo JBL Quantum910
VENDOR_ID = 0x0ecb
PRODUCT_ID = 0x2088

# Caminho do arquivo de log
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

def log_print(*args, **kwargs):
    """Imprime no terminal e grava no arquivo de log"""
    # Imprime no terminal
    print(*args, **kwargs)
    
    # Grava no arquivo de log
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            # Remove quebra de linha do print e adiciona timestamp
            if args:
                message = ' '.join(str(arg) for arg in args)
            else:
                message = ''  # Linha vazia
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] {message}\n")
            f.flush()  # Garante que os dados sejam escritos imediatamente
    except Exception as e:
        # Se não conseguir escrever no log, apenas continua
        pass

def log_raw_data(data_bytes, description=""):
    """Grava dados brutos recebidos no arquivo de log"""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            hex_data = ' '.join([f'{b:02x}' for b in data_bytes])
            if description:
                f.write(f"[{timestamp}] RAW DATA [{description}]: {hex_data} (len={len(data_bytes)})\n")
            else:
                f.write(f"[{timestamp}] RAW DATA: {hex_data} (len={len(data_bytes)})\n")
            f.flush()
    except Exception as e:
        pass

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
        pass  # Ignora se não conseguir
    
    # Configura a interface HID (interface 3)
    try:
        usb.util.claim_interface(device, 3)
    except usb.core.USBError as e:
        log_print(f"Erro ao reivindicar interface: {e}")
        log_print("Tente executar como root ou configure udev rules")
        sys.exit(1)
    
    return device

def read_battery():
    """Lê e exibe o nível de bateria"""
    log_print("JBL Quantum910 - Monitor de Bateria Simplificado")
    log_print("=" * 60)
    log_print("Padrão identificado: [Report ID=0x08, Bateria%]")
    log_print("Exemplo: 08 1e = [8, 30] = 30% de bateria")
    log_print()
    
    try:
        # Encontra o dispositivo
        device = find_device()
        log_print(f"✓ Dispositivo encontrado: 0x{device.idVendor:04x}:0x{device.idProduct:04x}")
        
        # Configura o dispositivo
        device = setup_device(device)
        
        # Endpoint IN: 0x83 (interface 3, endpoint 3 IN)
        endpoint = device[0][(3, 0)][0]
        
        log_print("Monitorando nível de bateria...")
        log_print("Pressione Ctrl+C para parar\n")
        log_print("=" * 60)
        
        last_battery = None
        last_report_id = None
        last_update_time = None
        update_count = 0
        timeout_count = 0
        last_timeout_log = 0
        is_muted = False  # Estado do mute
        
        try:
            while True:
                try:
                    # Lê dados do endpoint (máximo 64 bytes conforme wMaxPacketSize)
                    data = device.read(endpoint.bEndpointAddress, endpoint.wMaxPacketSize, 1000)
                    
                    # Converte para lista de bytes
                    data_bytes = list(data)
                    
                    # Padrão identificado: [Report ID=0x08, Bateria%]
                    if len(data_bytes) >= 2:
                        report_id = data_bytes[0]
                        battery = data_bytes[1]
                        
                        # Verifica se é o padrão de mute (Report ID 0x2f)
                        if report_id == 0x2f:
                            timestamp = time.strftime('%H:%M:%S')
                            if battery == 0x02:
                                # Botão de mute pressionado - alterna estado
                                is_muted = not is_muted
                                status_text = "MUTADO" if is_muted else "DESMUTADO"
                                emoji = "🔇" if is_muted else "🎤"
                                log_print(f"\n[{timestamp}] {emoji} MICROFONE {status_text} (botão pressionado)")
                                log_raw_data(data_bytes, f"MUTE TOGGLE -> {status_text}")
                                log_print()
                            elif battery == 0x00:
                                # Estado de desmutado (release do botão ou estado inicial)
                                if is_muted:
                                    # Se estava mutado, pode ser o release
                                    log_raw_data(data_bytes, "MUTE RELEASE (0x2f 0x00)")
                                else:
                                    log_raw_data(data_bytes, "MUTE STATE: DESMUTADO (0x2f 0x00)")
                            else:
                                # Outro valor de 0x2f - grava como desconhecido
                                log_raw_data(data_bytes, f"UNKNOWN MUTE PATTERN (Report ID: 0x2f, Value: 0x{battery:02x})")
                            continue
                        
                        # Verifica se é o padrão de bateria conhecido
                        if report_id == 0x08 and 0 <= battery <= 100:
                            # GRAVA TODOS OS DADOS RECEBIDOS NO LOG (padrão de bateria)
                            log_raw_data(data_bytes, f"BATTERY: {battery}%")
                            
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
                                
                                log_print(f"\n[{timestamp}] ⚡ BATERIA: {battery}%{interval_str}")
                                
                                # Barra visual de bateria
                                bar_length = 20
                                filled = int((battery / 100) * bar_length)
                                bar = "█" * filled + "░" * (bar_length - filled)
                                log_print(f"  [{bar}] {battery}%")
                                
                                # Status da bateria
                                if battery >= 80:
                                    status = "🔋 Carregada"
                                elif battery >= 50:
                                    status = "🔋 Boa"
                                elif battery >= 20:
                                    status = "🔋 Média"
                                else:
                                    status = "🔋 Baixa"
                                
                                log_print(f"  Status: {status}")
                                
                                # Mostra dados brutos
                                hex_data = ' '.join([f'{b:02x}' for b in data_bytes[:min(8, len(data_bytes))]])
                                log_print(f"  Dados: {hex_data} = [Report ID: {report_id}, Bateria: {battery}%]")
                                log_print()
                                
                                last_battery = battery
                                last_report_id = report_id
                                last_update_time = current_time
                        else:
                            # Dados recebidos mas não são o padrão esperado - grava no log
                            log_raw_data(data_bytes, f"UNKNOWN PATTERN (Report ID: 0x{report_id:02x}, Battery: {battery})")
                    else:
                        # Dados recebidos mas com tamanho insuficiente - grava no log
                        log_raw_data(data_bytes, f"INSUFFICIENT DATA (len={len(data_bytes)})")
                
                except usb.core.USBError as e:
                    if e.errno == 110:  # ETIMEDOUT
                        # Timeout é normal se não há dados - grava no log periodicamente
                        timeout_count += 1
                        current_time = time.time()
                        # Grava timeout a cada 10 ocorrências ou a cada 30 segundos
                        if timeout_count % 10 == 0 or (current_time - last_timeout_log) > 30:
                            try:
                                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    f.write(f"[{timestamp}] TIMEOUT: Nenhum dado recebido (ETIMEDOUT) - Total: {timeout_count}\n")
                                    f.flush()
                                last_timeout_log = current_time
                            except:
                                pass
                        continue
                    elif e.errno == 5:  # Input/output error
                        log_print(f"\n⚠ Erro de I/O USB: Dispositivo pode estar em uso")
                        log_print(f"   Aguardando 2 segundos...\n")
                        time.sleep(2)
                    else:
                        log_print(f"⚠ Erro USB: {e} (errno: {e.errno})")
                        # Grava erro detalhado no log
                        try:
                            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                f.write(f"[{timestamp}] USB ERROR: {e} (errno: {e.errno})\n")
                                f.flush()
                        except:
                            pass
                        time.sleep(1)
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            log_print("\n" + "=" * 60)
            log_print("📊 RESUMO")
            log_print("=" * 60)
            if last_battery is not None:
                log_print(f"⚡ Último nível de bateria: {last_battery}%")
                log_print(f"📦 Report ID: {last_report_id} (0x{last_report_id:02x})")
                log_print(f"📈 Total de atualizações recebidas: {update_count}")
                if last_update_time:
                    time_since_update = time.time() - last_update_time
                    log_print(f"⏱️  Última atualização há {time_since_update:.1f} segundos")
            else:
                log_print("⚠ Nenhum dado de bateria recebido")
            log_print("=" * 60)
        finally:
            # Libera a interface
            try:
                usb.util.release_interface(device, 3)
            except:
                pass
        
    except ValueError as e:
        log_print(f"Erro: {e}")
        sys.exit(1)
    except PermissionError:
        log_print("Erro: Permissão negada. Execute como root ou configure udev rules")
        sys.exit(1)
    except Exception as e:
        log_print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    read_battery()
