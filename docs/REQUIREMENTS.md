# Requirements and Installation

## Required Python Libraries

### For `tools/jbl_battery_monitor.py` (pyusb)
```bash
# Install for normal user
pip3 install pyusb --user

# Install for root (required if using sudo)
sudo pip3 install pyusb
```

### For `tools/jbl_battery_hidapi.py` (hidapi)
```bash
# Install for normal user
pip3 install hidapi --user

# Install for root (required if using sudo)
sudo pip3 install hidapi
```

### For `tools/jbl_battery_hidraw.py` and `jbl_battery_simple.py`
**No external libraries needed!** Uses only Python standard libraries.

## Verification

### Check if pyusb is installed
```bash
python3 -c "import usb.core; print('OK')"
sudo python3 -c "import usb.core; print('OK')"  # For root
```

### Check if hidapi is installed
```bash
python3 -c "import hid; print('OK')"
sudo python3 -c "import hid; print('OK')"  # For root
```

## Recommendation

**Use scripts that do not require external libraries:**
- `jbl_battery_simple.py` ⭐ (recommended)
- `tools/jbl_battery_hidraw.py` (full analysis)

These scripts use only Python standard libraries and work with `sudo` without installing anything additional.

## Quick Solution

If you get a module not found error when using `sudo`:

```bash
# Option 1: Install for root
sudo pip3 install pyusb

# Option 2: Use scripts that do not require libraries
sudo python3 jbl_battery_simple.py
# or
sudo python3 tools/jbl_battery_hidraw.py
```
