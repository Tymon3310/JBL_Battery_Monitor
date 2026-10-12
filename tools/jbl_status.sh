#!/usr/bin/env bash
# Simple CLI to check JBL Quantum status from exported files

UID_VAL=$(id -u)
EXPORT_DIR="/run/user/${UID_VAL}/jbl_quantum"

if [ ! -d "$EXPORT_DIR" ]; then
    echo "JBL Quantum export directory not found."
    echo "Make sure the tray app is running with the --export flag."
    exit 1
fi

CONNECTED=$(cat "${EXPORT_DIR}/connected" 2>/dev/null || echo "0")
if [ "$CONNECTED" != "1" ]; then
    echo "Headset: DISCONNECTED"
    exit 0
fi

MODEL=$(cat "${EXPORT_DIR}/model_name" 2>/dev/null || echo "JBL Quantum")
BATT=$(cat "${EXPORT_DIR}/battery_level" 2>/dev/null || echo "--")
MIC=$(cat "${EXPORT_DIR}/mic_status" 2>/dev/null || echo "--")

echo "--- ${MODEL} ---"
echo "Status:  CONNECTED"
echo "Battery: ${BATT}%"
echo "Mic:     ${MIC}"
