# Instructions for Monitoring JBL Quantum Battery (910/610)

## Current Status

✅ Supported devices: JBL Quantum 910 and 610 Wireless
✅ VID:PID: 0ecb:2088 (910), 0ecb:205c (610)
⚠️ Permissions required: Requires root access or udev configuration

## Available Scripts

1. **`jbl_battery_hidraw.py`** ⭐ **RECOMMENDED**
   - Reads directly from the hidraw device
   - More efficient and direct
   - File: `tools/jbl_battery_hidraw.py`

2. **`jbl_battery_monitor.py`**
   - Uses pyusb for direct USB communication
   - File: `tools/jbl_battery_monitor.py`

3. **`jbl_battery_hidapi.py`**
   - Alternative version using hidapi
   - File: `tools/jbl_battery_hidapi.py`

## How to Use (Option 1: With Sudo)

Run directly with root permissions:

```bash
sudo python3 tools/jbl_battery_hidraw.py
```

## How to Use (Option 2: Configure Permanent Permissions)

### Step 1: Configure udev rules

```bash
sudo ./setup_udev_rules.sh
```

Or manually:

```bash
sudo nano /etc/udev/rules.d/99-jbl-quantum.rules
```

Add:
```
SUBSYSTEM=="hidraw", KERNEL=="hidraw*", ATTRS{idVendor}=="0ecb", ATTRS{idProduct}=="2088", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="hidraw", KERNEL=="hidraw*", ATTRS{idVendor}=="0ecb", ATTRS{idProduct}=="205c", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0ecb", ATTR{idProduct}=="2088", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0ecb", ATTR{idProduct}=="205c", MODE="0666", GROUP="plugdev"
```

### Step 2: Reload rules and reconnect

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
# Disconnect and reconnect the headset
```

### Step 3: Add user to plugdev group (if necessary)

```bash
sudo usermod -a -G plugdev $USER
# Logout and login again
```

### Step 4: Run the script

```bash
python3 tools/jbl_battery_hidraw.py
```

## How It Works

The script:
1. Opens the `/dev/hidrawX` device (corresponding to the JBL Quantum)
2. Reads real-time data from HID communication
3. Analyzes received data looking for values representing battery
4. Displays raw data in hexadecimal and decimal
5. Attempts to automatically identify the battery level

## Data Interpretation

The script attempts several interpretations:
- **Method 1**: Searches for values between 0-100 that could be percentage (Report ID 0x08)
- **Method 2**: Interprets as 16-bit values (little-endian)
- **Method 3**: Searches for common patterns in HID reports

## Tips

- The device may not send data continuously
- Try using the headset actively (play audio, adjust volume) to trigger communication
- Raw data is always displayed for manual analysis
- The exact format depends on the manufacturer's implementation

## Troubleshooting

### "Permission denied"
- Run with `sudo` or configure udev rules

### "Device not found"
- Check if the headset is connected: `lsusb | grep 0ecb`
- Check which hidraw corresponds using: `python3 tools/find_hidraw.py`

### "No data received"
- The device may not be sending data automatically
- Try using the headset (play audio, adjust buttons)
- Some devices require specific commands to report battery

### Hidraw change
If the hidraw number changes, use the automatic detection script:
```bash
python3 tools/jbl_battery_auto.py
```

To find out which hidraw corresponds to the device:
```bash
python3 tools/find_hidraw.py
```
