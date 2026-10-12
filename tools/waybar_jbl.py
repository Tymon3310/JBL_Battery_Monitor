#!/usr/bin/env python3
import json
import os
import argparse

def get_status(mode, hide_disconnected=False, show_balance=False):
    uid = os.getuid()
    path = f"/run/user/{uid}/jbl_quantum"
    
    # Check if connected
    conn_file = os.path.join(path, "connected")
    is_connected = os.path.exists(conn_file) and open(conn_file).read().strip() == "1"
    
    if not is_connected:
        if hide_disconnected:
            return {"text": "", "class": "disconnected", "hidden": True}
        else:
            return {
                "text": "󰋋 OFF", # nf-md-headset_off
                "tooltip": "JBL Quantum: DISCONNECTED",
                "class": "disconnected"
            }

    try:
        cap = open(os.path.join(path, "capacity")).read().strip()
        mic = open(os.path.join(path, "mic_status")).read().strip()
        model = open(os.path.join(path, "model_name")).read().strip()
        p = int(cap) if cap.isdigit() else None
        
        # Battery icons (Nerd Font)
        if p is None: b_icon = " "
        elif p >= 90: b_icon = " "
        elif p >= 70: b_icon = " "
        elif p >= 40: b_icon = " "
        elif p >= 15: b_icon = " "
        else: b_icon = " "
        
        # Mic icons (Nerd Font)
        m_icon = " " if mic == "MUTED" else " "
        
        # Kept for CLI compatibility; balance tracking was removed from the exporter.
        bal_text = ""
        
        # Mode Selection
        if mode == "icons":
            text = f"{m_icon} {b_icon}{bal_text}"
        elif mode == "mic":
            text = f"{m_icon}{p if p is not None else '--'}%{bal_text}"
        elif mode == "both":
            text = f"{m_icon} {b_icon}{p if p is not None else '--'}%{bal_text}"
        else: # battery mode (default)
            icon = m_icon if mic == "MUTED" else b_icon
            text = f"{icon}{p if p is not None else '--'}%{bal_text}"

        return {
            "text": text,
            "tooltip": f"{model}\nBattery: {p if p is not None else '--'}%\nMic: {mic}",
            "class": "muted" if mic == "MUTED" else "connected",
            "percentage": p if p is not None else 0
        }
    except:
        return {"text": "err", "class": "error"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["battery", "mic", "both", "icons"], default="battery", 
                        help="Display mode: battery, mic, both, or icons")
    parser.add_argument("--hide-disconnected", action="store_true", help="Hide module when disconnected")
    parser.add_argument("--show-balance", action="store_true", help="Deprecated; balance tracking is disabled")
    args = parser.parse_args()
    print(json.dumps(get_status(args.mode, args.hide_disconnected, args.show_balance)))
