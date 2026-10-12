# JBL Quantum Wireless Protocol Documentation

## 1. Passive Events (Interrupt Endpoint)

### Microphone Status (Report ID 0x06)
- `06 00`: **MUTED**
- `06 01`: **UNMUTED**

### Battery Status (Report ID 0x08)
- **910**: Sent periodically (~10s).
- **610**: Sent only on **Power On/Off** events.
- Format: `[08, percentage, ...]` (percentage is 0-100 decimal).

### Game/Chat Balance (Report ID 0x10) - 610 Only
- Format: `[10, balance, ...]`
- Range: `0x00` (Game) to `0x10` (Chat). Mid-point is `0x08`.

---

## 2. Polled Data (Control Transfer)

### Battery Level (Report ID 0x7c) - 610 Only
- Used to get battery level when the headset is already on (since 610 doesn't send 0x08 periodically).
- Request: `Feature Report 0x7c`.

---

## 3. RGB Control (Experimental)
RGB is handled via `SET_REPORT` commands on Endpoint 0.
- Standard JBL pattern usually involves Report IDs `0x64` or `0x65`.
- Requires further sniffing from Windows to confirm the color byte offsets.
