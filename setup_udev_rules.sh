#!/bin/bash
# Script para configurar regras udev para acesso ao JBL Quantum910 sem root

echo "=== Configuração de Regras UDEV para JBL Quantum910 ==="
echo

# Verifica se está executando como root
if [ "$EUID" -ne 0 ]; then 
    echo "Este script precisa ser executado como root"
    echo "Execute: sudo $0"
    exit 1
fi

# Cria a regra udev
UDEV_RULE="/etc/udev/rules.d/99-jbl-quantum910.rules"

echo "Criando regra udev em $UDEV_RULE..."

cat > "$UDEV_RULE" << 'EOF'
# Regra para JBL Quantum910 Wireless (HID)
SUBSYSTEM=="hidraw", KERNEL=="hidraw*", ATTRS{idVendor}=="0ecb", ATTRS{idProduct}=="2088", MODE="0666", GROUP="plugdev"

# Regra alternativa para acesso USB direto
SUBSYSTEM=="usb", ATTR{idVendor}=="0ecb", ATTR{idProduct}=="2088", MODE="0666", GROUP="plugdev"
EOF

echo "✓ Regra criada"
echo
echo "Conteúdo da regra:"
cat "$UDEV_RULE"
echo

# Recarrega regras udev
echo "Recarregando regras udev..."
udevadm control --reload-rules
udevadm trigger

echo
echo "✓ Regras recarregadas"
echo
echo "Próximos passos:"
echo "1. Desconecte e reconecte o fone USB"
echo "2. Ou execute: sudo udevadm trigger"
echo "3. Verifique permissões: ls -la /dev/hidraw5"
echo
echo "Depois disso, você poderá executar os scripts sem sudo!"

