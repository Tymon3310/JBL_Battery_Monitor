#!/usr/bin/env python3
"""
Generate a convolution WAV with JBL's factory Q610 tuning, for PipeWire.

Source: QuantumENGINE apo/EqConfig-Q610.xml (LeftDriverPost/RightDriverPost):
  +3.5 dB @  360 Hz, Q 2.5
  -2.0 dB @ 2000 Hz, Q 1.4
  +5.0 dB @13000 Hz, Q 0.8
(all other bands are 0 dB placeholders; Pre blocks disabled)

Method: RBJ peaking biquads @ 48 kHz cascaded over an impulse -> stereo
float32 WAV. Use with pipewire/q610-eq.conf (filter-chain convolver),
same pattern as Pakrohk/linux-hifi-suite's eq.conf.

  python3 tools/generate_q610_eq.py [--out DIR] [--taps N]

Then enable (user scope, no root):
  mkdir -p ~/.config/pipewire/filter-chain.conf.d/
  cp pipewire/q610-eq.conf ~/.config/pipewire/filter-chain.conf.d/
  # edit filename path inside to point at the generated wav, then:
  systemctl --user restart pipewire
"""
from __future__ import annotations
import argparse
import math
import os
import numpy as np
from scipy.io import wavfile

FS = 48000
# (freq, gain_db, Q) — straight from EqConfig-Q610.xml
BANDS = [(360.0, 3.5, 2.5), (2000.0, -2.0, 1.4), (13000.0, 5.0, 0.8)]


def peaking(f0: float, gain_db: float, q: float):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f0 / FS
    alpha = math.sin(w0) / (2.0 * q)
    cw = math.cos(w0)
    b0 = 1.0 + alpha * a
    b1 = -2.0 * cw
    b2 = 1.0 - alpha * a
    a0 = 1.0 + alpha / a
    a1 = -2.0 * cw
    a2 = 1.0 - alpha / a
    return (np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0]))


def impulse_response(taps: int) -> np.ndarray:
    from scipy.signal import lfilter, freqz
    x = np.zeros(taps)
    x[0] = 1.0
    for f0, gdb, q in BANDS:
        b, a = peaking(f0, gdb, q)
        x = lfilter(b, a, x)
    # unity gain at 1 kHz (not peak): keeps Harman relative curve, sane level
    _, h = freqz(x, worN=[1000 / (FS / 2) * math.pi])
    ref = abs(h[0])
    x = x / ref
    peak = np.max(np.abs(x))
    if peak > 0.99:
        x = x / peak * 0.99  # uniform level trim, curve shape intact
    return x.astype(np.float32)


def check(ir: np.ndarray) -> None:
    from scipy.signal import freqz
    _, href = freqz(ir, worN=[1000 / (FS / 2) * math.pi])
    ref = 20 * math.log10(max(abs(href[0]), 1e-9))
    for f0, gdb, _ in BANDS:
        _, h = freqz(ir, worN=[f0 / (FS / 2) * math.pi])
        got = 20 * math.log10(max(abs(h[0]), 1e-9)) - ref
        print(f"  {f0:7.0f} Hz: target {gdb:+.1f} dB, got {got:+.2f} dB (rel. 1 kHz)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser("~/.local/share/jbl-quantum-linux"))
    ap.add_argument("--taps", type=int, default=32768)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ir = impulse_response(a.taps)
    stereo = np.stack([ir, ir], axis=1)
    path = os.path.join(a.out, "q610_factory_eq_48k.wav")
    wavfile.write(path, FS, stereo)
    print(f"wrote {path} ({a.taps} taps, float32 stereo)")
    check(ir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
