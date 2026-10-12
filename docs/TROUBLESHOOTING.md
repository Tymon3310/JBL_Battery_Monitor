# Troubleshooting - Common Errors

## Error: `[Errno 5] Input/output error`

### Cause
This error usually occurs when:
1. The device is being used by another program.
2. The device was disconnected during reading.
3. The kernel driver is controlling the device.
4. There is a conflict in accessing the device.

### Solutions

#### 1. Check if another program is using the device

```bash
# See processes using the device
lsof /dev/hidrawX
# or
fuser /dev/hidrawX
```

If there are processes, terminate them:
```bash
sudo kill <PID>
```

#### 2. Check if the device is connected

```bash
lsusb | grep 0ecb
ls -la /dev/hidraw*
```

If it doesn't appear, the device was disconnected.

#### 3. Detach kernel driver (if using pyusb)

```bash
# Check which driver is using it
lsmod | grep usbhid

# Detach (may be necessary)
sudo modprobe -r usbhid
sudo modprobe usbhid
```

**Caution:** This may affect other USB HID devices.

#### 4. Reset the device

1. Disconnect the USB headset.
2. Wait 2 seconds.
3. Reconnect the USB headset.
4. Run the script again.

#### 5. Check permissions

```bash
ls -la /dev/hidrawX
# Should show: crw-rw-rw- or crw-rw----

# If you don't have permission:
sudo chmod 666 /dev/hidrawX
```

#### 6. Use scripts that do not require pyusb

If the error occurs with `tools/jbl_battery_monitor.py` (pyusb), use:

```bash
python3 jbl_battery_simple.py
# or
sudo python3 tools/jbl_battery_hidraw.py
```

These scripts use hidraw directly and are more stable.

## Error: `Permission denied`

### Solution
```bash
sudo python3 jbl_battery_simple.py
```

Or configure udev rules (see `setup_udev_rules.sh`).

## Error: `ModuleNotFoundError: No module named 'usb'`

### Solution
```bash
# For normal user
pip3 install pyusb --user

# For root (if using sudo)
sudo pip3 install pyusb
```

Or use scripts that do not require pyusb:
```bash
python3 jbl_battery_simple.py
```

## Device does not send data

### Possible causes:
1. Device is not sending periodically.
2. Needs button press to activate.
3. Device in power saving mode.

### Solutions:
1. **Wait** - The device sends every 7-11 seconds.
2. **Press buttons** on the headset to trigger communication.
3. **Use the headset** - Play audio, adjust volume.
4. **Reconnect** the device.

## Script hangs or does not respond

### Solution:
1. Press `Ctrl+C` to interrupt.
2. Check if the device is connected.
3. Restart the script.

## Multiple I/O Errors

If you receive many I/O errors:

1. **Disconnect and reconnect** the headset.
2. **Restart the script**.
3. **Check** if there are other programs using the device:
   ```bash
   ps aux | grep -i jbl
   ps aux | grep -i quantum
   ```

## General Tips

1. **Use `jbl_battery_simple.py`** - It is the most stable.
2. **Run with sudo** (if udev rules are not set) - Avoids permission problems.
3. **Wait a few seconds** - The device sends periodically.
4. **Do not use multiple scripts at the same time** - May cause conflict.

## If Nothing Works

1. Disconnect the headset.
2. Wait 5 seconds.
3. Reconnect the headset.
4. Wait 2 seconds.
5. Run:
   ```bash
   python3 jbl_battery_simple.py
   ```

If it still doesn't work, check:
- If the device appears in `lsusb`.
- If the hidraw exists: `ls -la /dev/hidraw*`.
- If there are errors in dmesg: `dmesg | tail -20`.
