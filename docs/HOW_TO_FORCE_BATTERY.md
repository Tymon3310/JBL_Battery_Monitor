# How to Force Battery Information Reporting

## Problem

The JBL Quantum (910/610) only sends battery information when:
- The USB cable is connected/disconnected
- Buttons are pressed
- At specific intervals (not continuous)

## Solutions

### 1. Connection Capture Script

Use `tools/jbl_battery_capture.py` to:
- Capture everything that happens during connection
- Analyze received packets
- Try to force reporting using feature reports

```bash
sudo python3 tools/jbl_battery_capture.py
```

**How to use:**
1. Run the script
2. Disconnect the USB headset
3. Reconnect the USB headset
4. The script will capture and analyze everything

### 2. Brute Force Script

Use `tools/jbl_battery_force.py` to:
- Try several different commands
- Use HID feature reports
- Force the device to respond

```bash
sudo python3 tools/jbl_battery_force.py
```

### 3. Continuous Monitoring with Buttons

The `jbl_battery_simple.py` script works when you:
- Press headset buttons
- Adjust volume
- Use headset controls

```bash
python3 jbl_battery_simple.py
```

## Data Analysis

### Identified Pattern

When the device sends battery info:
```
08 1e = [8, 30] = 30% battery
```

- **Byte 0**: Report ID = `0x08` (fixed)
- **Byte 1**: Battery level = `0x1e` (30) = **30%**

### What to Try

1. **HID Feature Reports**
   - Report ID 0x08 (what we receive)
   - Other common Report IDs (0x01-0x09)

2. **Request Commands**
   - Some devices respond to GET feature reports
   - May need to send a specific command

3. **Timing**
   - The device may send battery info only at specific times
   - During initialization is the most reliable

## Limitations

- The device may not respond to external commands
- Physical buttons may need to be used
- Some devices only send when there is a state change

## Next Steps

1. Run `tools/jbl_battery_capture.py` and analyze packets
2. Try to identify if there is any pattern in the commands
3. Use the headset buttons to trigger sending when necessary
