# Identified Battery Pattern - JBL Quantum (910/610)

## ✅ Confirmed Pattern

**Battery packet format:**
```
[Report ID, Battery Level]
```

**Identified example:**
```
08 1e = [8, 30] = 30% battery
```

## 📊 Data Structure

- **Byte 0**: Report ID = `0x08` (8 in decimal)
- **Byte 1**: Battery level = `0x1e` (30 in decimal) = **30%**

## 🔍 Analysis

- The **Report ID** (`0x08`) seems to be fixed for battery packets.
- The **battery level** is in byte 1, in direct decimal format (0-100).
- The packet has at least 2 bytes, but may have more (likely zeros or other data).

## 📝 Scripts

### Simplified Script
Use `jbl_battery_simple.py` to monitor only the battery:

```bash
python3 jbl_battery_simple.py
```

This script:
- Focuses only on byte 1 when the Report ID is 0x08.
- Shows a visual battery bar.
- Displays status (Charged/Good/Medium/Low).
- Ignores other packets.

### Full Script
Use `tools/jbl_battery_hidraw.py` for a full analysis of all data:

```bash
sudo python3 tools/jbl_battery_hidraw.py
```

## 🧪 Recommended Tests

1. **Test with different battery levels:**
   - Charge the headset and observe if the value increases.
   - Use the headset and observe if the value decreases.
   - Compare with the system indicator (if available).

2. **Check other packets:**
   - Press different buttons.
   - Adjust volume.
   - Observe if the Report ID changes for other values.

3. **Confirm the pattern:**
   - Is the Report ID always 0x08 for battery?
   - Is byte 1 always between 0-100?
   - Are there other relevant bytes in the packet?

## 💡 Notes

- The device may not send data continuously.
- You may need to press buttons to trigger the sending.
- The format may vary across different models/firmwares.

## 📅 Identification Date

January 25, 2025
