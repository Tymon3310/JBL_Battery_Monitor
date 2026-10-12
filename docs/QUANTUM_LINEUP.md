# JBL Quantum Lineup (from QuantumENGINE 2.8.6, 2026-10-12)

All VID `0x0ECB` unless noted. Sources: `ProductID.cs`, `aux_device_list.json`,
`apo/EqConfig-*.xml`, `Q*` product classes. See `docs/QUANTUM610_PACKETS.md`
for the 610's decoded protocol (applies to all HIDV1 dongle models).

## 2.4 GHz wireless (dongle + headset PIDs)

| Model | Dongle | Headset | DFU | Lighting |
|---|---|---|---|---|
| Q350B | `2047` | `2048` | — | — |
| Q350 (V1/V2) | `206B`/`20B2` | `206C` | `206E`/`206F` | — |
| Q360 | `2115` | `2113` | `2116`/`2114` | — |
| Q360P (PS) | `20AB` | `20AC` | `20AD`/`20AE` | — |
| Q360X (+Xbox `20A9`) | `20A5` | `20A6` | `20A7`/`20A8` | — |
| Q360XB (+Xbox `2143`) | `2142` | `2145` | `2144`/`2146` | — |
| Q520 | `218D` | `218E` | — | — |
| Q520X (+Xbox `21AA`) | `21A7` | `21A9` | — | — |
| Q600 (V1/V2) | `1F46`/`203C` | `1F4B` | — | LOGO |
| **Q610** | **`205C`** | **`205B`** | — | LOGO |
| Q650 | `2125` | `2126` | — | — |
| Q650X (+Xbox `213C`) | `213B` | `213D` | — | — |
| Q800 (V1/V2) | `1F47`/`203E` | USB `1F4A`/AUX `1F49` | `0100`/`0101` | LOGO+RING |
| Q810 | `2069` | `206A` | — | LOGO+RING |
| Q850 (HIDV3) | HID `2199`+`219A` | `219B`/HRTF `219C` | — | — |
| Q910 | `2088` | `2089`/HRTF `209C` | — | LOGO+RING+NOTCH |
| Q910P (PS) | `20A2` | `20A3`/HRTF `20A4` | — | LOGO+RING+NOTCH |
| Q910X (+Xbox `20A0`) | `209D` | `209E`/HRTF `209F` | — | LOGO+RING+NOTCH |
| Q910XB (+Xbox `2148`) | `2147` | `2149`/HRTF `214A` | — | LOGO+RING+NOTCH |
| Q950 (+BS) | `2127`+HID `2186` | `2128`/HRTF `2129` | — | BS only |
| Q950X (+Xbox `213F`,+BS) | `213E`+HID `2187` | `2140`/HRTF `2141` | — | BS only |

## Wired USB (single PID)

| Model | PID | Lighting |
|---|---|---|
| Q300 | `1F52` | — |
| Q400 (V1/V2) | `1F4C`/`2039` | LOGO |
| Q400B | `20EE` | LOGO |
| Q50C (USB-C) | `2112` | — |
| QOne (V1/V2) | `1F48`/`203A` | LOGO+RING+NOTCH |
| QOne P1 | `20C2` | LOGO+RING+NOTCH |

## Wired AUX (analog, no USB)

Q50, Q50N, Q50C, Q100, Q100P/X/N CONSOLE, Q100M2, Q120, Q200, Q250, Q255.

## TWS / mics / base stations

| Model | PID | Notes |
|---|---|---|
| QTWS / QTWSCN | `208A`/`209B` | earbuds |
| QTWS Air | `20BE` | earbuds |
| QStream (mic) | `205F` | RING lighting |
| QStream Talk (mic) | `20AF` | DFU `01ED` on C-Media `0D8C` |
| QStream Studio (mic) | `20B0` | RING+Volume+VU; DFU `0069` on C-Media |
| QStream Wireless (mic) | `20ED` | lighting on/off card |

Notes: Xbox variants expose a second dongle PID in console mode. HRTF PIDs
are separate USB devices for head-tracking audio. Q600 presets are shared
with Q610 (`Q610_DEFAULT = Q600_SERIES_DEFAULT`). spin effects exist only on
RING groups — never send them to LOGO-only models (firmware crash, §8).
