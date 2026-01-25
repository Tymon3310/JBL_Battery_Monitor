#!/bin/bash
# Script para verificar permissões e configuração do dispositivo JBL Quantum910

echo "=== Verificação de Permissões JBL Quantum910 ==="
echo

# Verifica se o dispositivo está conectado
echo "1. Verificando se o dispositivo está conectado..."
if lsusb | grep -q "0ecb:2088"; then
    echo "   ✓ Dispositivo encontrado"
    lsusb | grep "0ecb:2088"
else
    echo "   ✗ Dispositivo não encontrado"
    echo "   Conecte o fone JBL Quantum910 via USB"
    exit 1
fi

echo

# Verifica permissões do dispositivo USB
echo "2. Verificando permissões do dispositivo USB..."
DEVICE_PATH=$(lsusb | grep "0ecb:2088" | head -1 | sed 's/.*Bus \([0-9]*\) Device \([0-9]*\).*/\/dev\/bus\/usb\/\1\/\2/')
if [ -e "$DEVICE_PATH" ]; then
    PERMS=$(stat -c "%a" "$DEVICE_PATH" 2>/dev/null)
    OWNER=$(stat -c "%U" "$DEVICE_PATH" 2>/dev/null)
    echo "   Caminho: $DEVICE_PATH"
    echo "   Permissões: $PERMS"
    echo "   Proprietário: $OWNER"
    
    if [ "$PERMS" = "666" ] || [ "$PERMS" = "664" ]; then
        echo "   ✓ Permissões adequadas"
    else
        echo "   ⚠ Permissões podem ser insuficientes"
        echo "   Execute: sudo chmod 666 $DEVICE_PATH"
    fi
else
    echo "   ⚠ Caminho do dispositivo não encontrado"
fi

echo

# Verifica se o usuário está no grupo plugdev
echo "3. Verificando grupo do usuário..."
if groups | grep -q plugdev; then
    echo "   ✓ Usuário está no grupo plugdev"
else
    echo "   ⚠ Usuário não está no grupo plugdev"
    echo "   Execute: sudo usermod -a -G plugdev $USER"
    echo "   (depois faça logout e login)"
fi

echo

# Verifica regras udev
echo "4. Verificando regras udev..."
if [ -f "/etc/udev/rules.d/99-jbl-quantum910.rules" ]; then
    echo "   ✓ Regra udev encontrada"
    cat /etc/udev/rules.d/99-jbl-quantum910.rules
else
    echo "   ⚠ Regra udev não encontrada"
    echo "   Crie: /etc/udev/rules.d/99-jbl-quantum910.rules"
    echo "   Com conteúdo:"
    echo "   SUBSYSTEM==\"usb\", ATTR{idVendor}==\"0ecb\", ATTR{idProduct}==\"2088\", MODE=\"0666\""
fi

echo

# Verifica bibliotecas Python
echo "5. Verificando bibliotecas Python..."
if python3 -c "import usb.core" 2>/dev/null; then
    echo "   ✓ pyusb instalado"
else
    echo "   ⚠ pyusb não instalado"
    echo "   Execute: pip3 install pyusb --user"
fi

if python3 -c "import hid" 2>/dev/null; then
    echo "   ✓ hidapi instalado"
else
    echo "   ⚠ hidapi não instalado"
    echo "   Execute: pip3 install hidapi --user"
fi

echo
echo "=== Fim da Verificação ==="

