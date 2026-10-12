#!/bin/bash
# Script to configure udev rules for JBL Quantum (910/610) access without root

echo "=== UDEV Rule Configuration for JBL Quantum (910/610) ==="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "This script must be run as root"
    echo "Run: sudo $0"
    exit 1
fi

# Create udev rule
UDEV_RULE="/etc/udev/rules.d/99-jbl-quantum.rules"

echo "Creating udev rule in $UDEV_RULE..."

cat > "$UDEV_RULE" << 'EOF'
# Rules for JBL Quantum Wireless (910, 610)
SUBSYSTEM=="hidraw", KERNEL=="hidraw*", ATTRS{idVendor}=="0ecb", ATTRS{idProduct}=="2088", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="hidraw", KERNEL=="hidraw*", ATTRS{idVendor}=="0ecb", ATTRS{idProduct}=="205c", MODE="0666", GROUP="plugdev"

# Alternative rules for direct USB access
SUBSYSTEM=="usb", ATTR{idVendor}=="0ecb", ATTR{idProduct}=="2088", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0ecb", ATTR{idProduct}=="205c", MODE="0666", GROUP="plugdev"
EOF

echo "✓ Rule created"
echo
echo "Rule content:"
cat "$UDEV_RULE"
echo

# Reload udev rules
echo "Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger

echo
echo "✓ Rules reloaded"
echo
echo "Next steps:"
echo "1. Disconnect and reconnect the USB headset"
echo "2. Or run: sudo udevadm trigger"
echo "3. Check permissions: ls -la /dev/hidraw*"
echo
echo "After that, you will be able to run the scripts without sudo!"
