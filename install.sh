#!/usr/bin/env bash
set -euo pipefail

APP_NAME="jbl-quantum-tray"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SHARE_DIR="${HOME}/.local/share/${APP_NAME}"
BIN_DIR="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"

SERVICE_SRC="${ROOT_DIR}/systemd/jbl-quantum-tray.service"
SERVICE_DST="${SYSTEMD_DIR}/jbl-quantum-tray.service"

# Default flags
FLAGS="--prefer-hidraw"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --only-mic)
      FLAGS="$FLAGS --icon-mode mic"
      shift
      ;;
    --only-bat|--only-battery)
      FLAGS="$FLAGS --icon-mode battery"
      shift
      ;;
    --export)
      FLAGS="$FLAGS --export"
      shift
      ;;
    --headless)
      FLAGS="$FLAGS --headless"
      shift
      ;;
    --notifications)
      FLAGS="$FLAGS --notifications"
      shift
      ;;
    --swayosd)
      FLAGS="$FLAGS --swayosd"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./install.sh [--only-mic] [--only-bat] [--export] [--headless] [--notifications] [--swayosd]"
      exit 1
      ;;
  esac
done

echo "==> Installing ${APP_NAME} (user-level)"
mkdir -p "${SHARE_DIR}" "${BIN_DIR}" "${SYSTEMD_DIR}"

# Copy the app
cp -f "${ROOT_DIR}/jbl_quantum_tray.py" "${SHARE_DIR}/jbl_quantum_tray.py"
chmod +x "${SHARE_DIR}/jbl_quantum_tray.py"
cp -f "${ROOT_DIR}/jbl_quantum_core.py" "${SHARE_DIR}/jbl_quantum_core.py"

# Create wrapper with specific flags
echo "==> Creating wrapper in ${BIN_DIR}/${APP_NAME}"
cat <<EOF > "${BIN_DIR}/${APP_NAME}"
#!/bin/sh
exec python3 "${SHARE_DIR}/jbl_quantum_tray.py" ${FLAGS} "\$@"
EOF
chmod +x "${BIN_DIR}/${APP_NAME}"

# Update service file ExecStart before copying
echo "==> Installing systemd --user service"
# Create a temporary service file with the correct path and flags
sed "s|ExecStart=.*|ExecStart=${BIN_DIR}/${APP_NAME}|" "${SERVICE_SRC}" > "${SERVICE_DST}"

echo "==> Reloading systemd (user) and enabling"
systemctl --user daemon-reload
systemctl --user enable jbl-quantum-tray.service
systemctl --user restart jbl-quantum-tray.service

echo
echo "OK. Installed and started with flags: ${FLAGS}"
echo
echo "Useful commands:"
echo "  - status:  systemctl --user status jbl-quantum-tray.service"
echo "  - logs:    journalctl --user -u jbl-quantum-tray.service -f"
echo "  - stop:    systemctl --user stop jbl-quantum-tray.service"
echo
echo "Virtual Device location (if --export used):"
echo "  /run/user/$(id -u)/jbl_quantum/"
echo
