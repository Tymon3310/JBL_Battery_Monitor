# JBL Quantum Battery Tray (Linux)

**Real** battery monitor for JBL Quantum 910 and 610 Wireless: shows **battery % in the tray** and can start automatically at login via **`systemd --user`**.

The confirmed battery pattern for these headsets is:

```
[Report ID, Battery%]
08 1e => 30%
```

## ✅ What this project does

- **Tray/AppIndicator**: shows "30%" in the tray and updates automatically.
- **Support**: JBL Quantum 910 Wireless and JBL Quantum 610 Wireless.
- **Reliable reading**: uses the same method as `jbl_battery_simple.py` (PyUSB, interface 3).
- **Service at login**: installs as `systemd --user` (no need for root running the app).
- **Tools and docs**: analysis scripts and documentation organized in folders.

## 📁 Project Structure

- **`jbl_quantum_tray.py`**: tray app (main, supports 910 and 610)
- **`install.sh` / `uninstall.sh`**: install/remove as a service at login
- **`systemd/`**: `systemd --user` unit file
- **`autostart/`**: alternative via `.desktop` file
- **`tools/`**: auxiliary/experimental capture/analysis scripts
- **`docs/`**: detailed documentation (permissions, troubleshooting, etc.)

## ✅ Battery Pattern (confirmed for 910 and 610)

- **Byte 0**: Report ID = `0x08`
- **Byte 1**: battery in % (0–100)

Details: `docs/BATTERY_PATTERN.md`.

## 🚀 Quick Start

### 1) Check permissions

```bash
./check_permissions.sh
```

### 2) Configure permissions (recommended)

```bash
sudo ./setup_udev_rules.sh
# Then disconnect and reconnect the headset
```

### 3) Run the tray

```bash
python3 ./jbl_quantum_tray.py
```

If you want to test only the reading (CLI), use:

```bash
python3 ./jbl_battery_simple.py
```

## 🔧 Requirements

### Python Dependencies (CLI/reading)

```bash
pip3 install pyusb --user
# or
pip3 install hidapi --user
```

### Requirements (Tray / AppIndicator)

For the tray, installation is via system packages (not via pip):

```bash
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
# (on some distros it may be: gir1.2-appindicator3-0.1)
```

## 🖥️ Tray (AppIndicator) - How to use

### Run manually

```bash
python3 ./jbl_quantum_tray.py
```

Useful options:

```bash
python3 ./jbl_quantum_tray.py --refresh 1.0
python3 ./jbl_quantum_tray.py --prefer-hidraw
```

## 📦 Installation (recommended) — starts with the system (login)

This installs it as a **`systemd --user` service** (starts when you log into the desktop).

```bash
chmod +x ./install.sh
./install.sh
```

To remove:

```bash
chmod +x ./uninstall.sh
./uninstall.sh
```

## 🧰 Tools (auxiliary scripts)

The scripts below are in `tools/` and are useful for analysis/debug:

- `tools/jbl_battery_hidraw.py`: full dump/analysis (has `--log`)
- `tools/jbl_battery_monitor.py`: alternative via pyusb
- `tools/jbl_battery_hidapi.py`: alternative via hidapi
- `tools/jbl_battery_capture.py`: capture on connection/disconnection
- `tools/jbl_battery_force.py`: brute force/experimental
- `tools/find_hidraw.py`: finds the `/dev/hidrawX`

## 📝 Notes

- **IDs**: VID `0x0ecb` / PIDs `0x2088` (910), `0x205c` (610)
- **HID**: interface 3, endpoint IN (used by the `pyusb` method)
- **Update**: the headset may remain "quiet" — use the headset (volume/buttons) to generate traffic
- **Permissions**: it is ideal to use `setup_udev_rules.sh` to avoid `sudo`

## 🐛 Troubleshooting

See:

- `docs/TROUBLESHOOTING.md`
- `docs/INSTRUCTIONS.md`

## 📄 License

Scripts created for personal/educational use.
