# JBL Quantum Wireless Battery Monitor (910, 610)

Scripts to intercept USB communication from JBL Quantum 910/610 headsets and extract battery information.

## Available Scripts

### 1. `tools/jbl_battery_monitor.py` (using pyusb)
Main script that uses the `pyusb` library for direct communication with the USB device.

### 2. `tools/jbl_battery_hidapi.py` (using hidapi)
Alternative script using `hidapi`, which may be easier to use on some systems.

## Requirements

```bash
pip3 install pyusb --user
# or
pip3 install hidapi --user
```

## Permissions

To access USB devices, you may need special permissions:

### Option 1: Run as root (not recommended)
```bash
sudo python3 tools/jbl_battery_monitor.py
```

### Option 2: Configure udev rules (recommended)
Create the file `/etc/udev/rules.d/99-jbl-quantum.rules`:

```
SUBSYSTEM=="usb", ATTR{idVendor}=="0ecb", ATTR{idProduct}=="2088", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="0ecb", ATTR{idProduct}=="205c", MODE="0666"
```

Then reload the rules:
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Option 3: Add user to plugdev group
```bash
sudo usermod -a -G plugdev $USER
# Logout and login again
```

## How to Use

1. Connect the JBL Quantum (910 or 610) headset via USB
2. Run one of the scripts:
   ```bash
   python3 tools/jbl_battery_monitor.py
   # or
   python3 tools/jbl_battery_hidapi.py
   ```
3. The script will:
   - Show device information
   - Continuously monitor USB communication
   - Attempt to identify battery level in received data
   - Display raw data in hexadecimal and decimal

## Data Interpretation

The script attempts various interpretations of the received data:
- Searches for values between 0-100 that may represent percentage
- Interprets data as 8-bit or 16-bit
- Searches for common HID report patterns

## Notes

- The battery level may not be sent continuously by the device
- It may be necessary to use the headset actively for it to send data
- The exact data format depends on the manufacturer's implementation
- Some devices only send battery information when requested

## Troubleshooting

If the script does not find the device:
- Check if the headset is connected: `lsusb | grep 0ecb`
- Check permissions: `ls -la /dev/bus/usb/001/007`
- Try running as root to test

If no data is received:
- The device may not be sending data continuously
- Try using the headset (play audio, adjust volume) to trigger communication
- Some devices require specific commands to report battery
