#!/bin/bash
# Script to check permissions and configuration for JBL Quantum devices

echo "=== JBL Quantum Permission Check ==="
echo

# Check if the device is connected
echo "1. Checking if the device is connected..."
if lsusb | grep -qE "0ecb:(2088|205c)"; then
    echo "   ✓ Device found"
    lsusb | grep -E "0ecb:(2088|205c)"
else
    echo "   ✗ Device not found"
    echo "   Connect the JBL Quantum (910 or 610) headset via USB"
    exit 1
fi

echo

# Check USB device permissions
echo "2. Checking USB device permissions..."
DEVICE_PATH=$(lsusb | grep -E "0ecb:(2088|205c)" | head -1 | sed 's/.*Bus \([0-9]*\) Device \([0-9]*\).*/\/dev\/bus\/usb\/\1\/\2/')
if [ -e "$DEVICE_PATH" ]; then
    PERMS=$(stat -c "%a" "$DEVICE_PATH" 2>/dev/null)
    OWNER=$(stat -c "%U" "$DEVICE_PATH" 2>/dev/null)
    echo "   Path: $DEVICE_PATH"
    echo "   Permissions: $PERMS"
    echo "   Owner: $OWNER"
    
    if [ "$PERMS" = "666" ] || [ "$PERMS" = "664" ]; then
        echo "   ✓ Adequate permissions"
    else
        echo "   ⚠ Permissions may be insufficient"
        echo "   Run: sudo chmod 666 $DEVICE_PATH"
    fi
else
    echo "   ⚠ Device path not found"
fi

echo

# Check user group
echo "3. Checking user group..."
if groups | grep -q plugdev; then
    echo "   ✓ User is in the plugdev group"
else
    echo "   ⚠ User is not in the plugdev group"
    echo "   Run: sudo usermod -a -G plugdev $USER"
    echo "   (then logout and login)"
fi

echo

# Check udev rules
echo "4. Checking udev rules..."
if [ -f "/etc/udev/rules.d/99-jbl-quantum.rules" ] || [ -f "/etc/udev/rules.d/99-jbl-quantum910.rules" ]; then
    echo "   ✓ udev rule found"
    cat /etc/udev/rules.d/99-jbl-quantum*.rules
else
    echo "   ⚠ udev rule not found"
    echo "   Create: /etc/udev/rules.d/99-jbl-quantum.rules"
    echo "   With content:"
    echo "   SUBSYSTEM==\"usb\", ATTR{idVendor}==\"0ecb\", ATTR{idProduct}==\"2088\", MODE=\"0666\""
    echo "   SUBSYSTEM==\"usb\", ATTR{idVendor}==\"0ecb\", ATTR{idProduct}==\"205c\", MODE=\"0666\""
fi

echo

# Check Python libraries
echo "5. Checking Python libraries..."
if python3 -c "import usb.core" 2>/dev/null; then
    echo "   ✓ pyusb installed"
else
    echo "   ⚠ pyusb not installed"
    echo "   Run: pip3 install pyusb --user"
fi

if python3 -c "import hid" 2>/dev/null; then
    echo "   ✓ hidapi installed"
else
    echo "   ⚠ hidapi not installed"
    echo "   Run: pip3 install hidapi --user"
fi

echo
echo "=== End of Check ==="
