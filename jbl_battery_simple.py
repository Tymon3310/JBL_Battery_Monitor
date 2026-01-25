#!/usr/bin/env python3
"""
Script simplificado para monitorar apenas o nível de bateria do JBL Quantum910
Usa pyusb (como jbl_battery_monitor.py) para garantir compatibilidade
"""

import sys
import time

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
        print(f"Erro ao reivindicar interface: {e}")
        print("Tente executar como root ou configure udev rules")
        sys.exit(1)
    
    return device

def read_battery():
    """Lê e exibe o nível de bateria"""
    print("JBL Quantum910 - Monitor de Bateria Simplificado")
    print("=" * 60)
    print("Padrão identificado: [Report ID=0x08, Bateria%]")
    print("Exemplo: 08 1e = [8, 30] = 30% de bateria")
    print()
    
    try:
        # Encontra o dispositivo
        device = find_device()
        print(f"✓ Dispositivo encontrado: 0x{device.idVendor:04x}:0x{device.idProduct:04x}")
        
        # Configura o dispositivo
        device = setup_device(device)
        
        # Endpoint IN: 0x83 (interface 3, endpoint 3 IN)
        endpoint = device[0][(3, 0)][0]
        
        print("Monitorando nível de bateria...")
        print("Pressione Ctrl+C para parar\n")
        print("=" * 60)
        
        last_battery = None
        last_report_id = None
        last_update_time = None
        update_count = 0
        
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
                        
                        # Verifica se é o padrão de bateria conhecido
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
                
                except usb.core.USBError as e:
                    if e.errno == 110:  # ETIMEDOUT
                        # Timeout é normal se não há dados
                        continue
                    elif e.errno == 5:  # Input/output error
                        print(f"\n⚠ Erro de I/O USB: Dispositivo pode estar em uso")
                        print(f"   Aguardando 2 segundos...\n")
                        time.sleep(2)
                    else:
                        print(f"⚠ Erro USB: {e} (errno: {e.errno})")
                        time.sleep(1)
                
                time.sleep(0.1)
                
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
        finally:
            # Libera a interface
            try:
                usb.util.release_interface(device, 3)
            except:
                pass
        
    except ValueError as e:
        print(f"Erro: {e}")
        sys.exit(1)
    except PermissionError:
        print("Erro: Permissão negada. Execute como root ou configure udev rules")
        sys.exit(1)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    read_battery()
