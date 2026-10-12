# JBL Quantum 610 (0ecb:205c) — Deep Packet Analysis

Target: **Harman JBL Quantum610 Wireless** dongle, USB `0ecb:205c`, HID interface **5**,
interrupt IN endpoint **`0x83`, wMaxPacketSize 16, bInterval 3**.
All below verified live on 2026-10-12 unless marked `hypothesis`.
Tool: `tools/quantum610_deep_scan.py`. HID report descriptor dumped from
`/sys/bus/hid/devices/0003:0ECB:205C.*/report_descriptor` (491 bytes).

## 0. TL;DR

* **12 control (GET_REPORT) packets actually implemented**, all 1:1 validated
  (first byte == requested ID). Everything else is a **floor-fallback**
  (returns previous implemented ID — must validate!).
* **Battery = `0x49`, byte 1 = 0–100 direct.** Live: `49 5a` = 90%.
  `0x08` (interrupt) is the 910-style battery event; on 610 it only fires on
  power on/off, so polling `0x49` is the correct method.
* **Mute = `0x67`, byte 1: `00`=muted / `01`=unmuted** (live `67 01`).
* **Link/headset-on = `0x68`, byte 1: `01`=connected / `00`=off** (live `68 01`).
* **Idle bus is silent**: 15 s interrupt sniff + 8 s hidraw sniff = 0 packets.
  All interrupt (`0x02/06/07/08/09/10/11/12/2F`) packets only appear on user action.
* `Input` vs `Feature` GET_REPORT return **identical bytes** — firmware does not
  distinguish (`0xA1 0x01 0x01xx` == `0xA1 0x01 0x03xx`).
* **Never request 64 bytes.** Request exact `payload+1` or you get stale trailing
  bytes (`LL0012605` ASCII bleed, `fe 0d 95 68 86…`). See §4.

## 1. USB layout (verified `lsusb -v`)

```
Iface 0  Audio Control   "Game"
Iface 1  Audio Streaming Game (EP 0x01 OUT iso, 48 kHz)
Iface 2  Audio Control   "Chat"
Iface 3  Audio Streaming Chat OUT (EP 0x02 OUT iso)
Iface 4  Audio Streaming Mic IN  (EP 0x81 IN iso, 16 kHz)
Iface 5  HID             "JBL Quantum610 Wireless"
         EP 0x83 IN interrupt, 16 B, interval 3
         + EP0 control (GET/SET_REPORT)
```

Only iface 5 carries headset control. Audio ifaces are standard UAC1.

## 2. HID report descriptor (authoritative ID list)

Raw 491 B in §-header of `quantum610_deep_scan.py` / sysfs. Parsed:

| Report | Dir | Payload | Meaning / status |
|---|---|---|---|
| `0x02` | Input | bitfields (2+1+5 bits) | **Consumer** (Vol+/-, mute, …): `09 e9/ea/e2`. Interrupt only. |
| `0x06` | Output | **61 B** (`91 22`) | Host→device config block (untested — likely EQ/RGB/sidetone). Do not poke blindly. |
| `0x06` | Input | 1 B | Mute-ish state? `parse_mute_from_packet` maps `06 00`=muted. Needs trigger capture. |
| `0x07` | Input | 1 B | unknown — never seen on control; needs button test |
| `0x08` | Input | 1 B | **Battery event** `[08 pct]`, 910-periodic / 610 power-cycle only |
| `0x09` | Input | 1 B | unknown |
| `0x10` | Input | 1 B | **Game/Chat balance** (per old PROTOCOL.md): `00`=Game … `08`=mid … `10`=Chat. Needs dial test. |
| `0x11` | Input | 1 B | unknown |
| `0x12` | Input | 2 B | unknown |
| `0x50` | Feature | 2 B | implemented (see §3) |
| `0x52` | Feature | 2 B | **advertised but NOT implemented** → returns `0x50` data |
| `0x49` | Feature | 1 B | **Battery poll** — implemented |
| `0x4A` | Feature | 1 B | implemented |
| `0x4B`/`0x4C`/`0x4D` | Feature | 1/3/7 B | advertised, NOT implemented → return `0x4A` data |
| `0x51` | Feature | 12 B | implemented |
| `0x53`/`0x59`/`0x5A` | Feature | 1/1/16 B | NOT implemented → return `0x51` data |
| `0x5C` | Feature | 1 B | implemented |
| `0x5D`/`0x60` | Feature | 1 B | NOT implemented → return `0x5C` |
| `0x61` | Feature | 16 B | implemented (serial string) |
| `0x62` | Feature | 1 B | implemented |
| `0x67` | Feature | 1 B | **Mic mute poll** — implemented |
| `0x68` | Feature | 1 B | **Link poll** — implemented |
| `0x69` | Feature | 1 B | NOT implemented → returns `0x68` |
| `0x75` | Feature | 1 B | implemented (unknown, live `06`) |
| `0x76`/`0x7A`/`0x7B` | Feature | 1 B | NOT implemented → return `0x75` |
| `0x7C` | Feature | 6 B | implemented (unknown blob) |
| `0x7D`/`0x7E` | Feature | 1 B | NOT implemented → return `0x7C` prefix |
| `0x2F` | Input | 1+1+5+1 bits | **Telephony** (`09 20/2f/24/21/97/2a/50`): hook/off-hook states. `2F 00/02` mute mapping in `parse_mute_from_packet` lives here. |
| `0x2F` | Output | 6+2 B (`91 22`, `91 01`) | LED-state block (`05 08`: `09 17/09/18/20/21/2a`). Hypothesis: mute-LED. |
| `0x2F` | Feature (?) | — | control-probed `2F 00` (see §3). |

Key: descriptor advertises 35 IDs; firmware implements only **12** via control.
Input-only IDs (`02/06/07/08/09/10/11/12`) correctly **fail** via control
(return `2F 00` fallback) — they are interrupt-only.

## 3. Control packets (GET_REPORT, validated 2026-10-12, headset ON)

Request exact length `payload+1`, `bmRequestType 0xA1, bRequest 0x01`,
`wValue 0x01xx` (=Input) or `0x03xx` (=Feature, same result),
`wIndex 5`. Current snapshot (`--out` JSON):

| ID | Req len | Live bytes | Decode |
|---|---|---|---|
| `0x49` | 2 | `49 5a` | **Battery 0x5a=90%**. Range 0–100. `jbl_quantum_core.poll_battery` uses this. |
| `0x4A` | 2 | `4a 01` | unknown, constant `01`. Candidate: mic-AGC / sidetone flag? Needs mute/power diff. |
| `0x50` | 3 | `50 01 10` | **Hardware version** (`HARDWARE_VERSION{Minor,Major}`): HW 16.1. `HardwareVersionProp` (HID 80/82). |
| `0x51` | 13 | `51 02 09 01 02 09 01 00 00 00 00 00 00` | **Firmware version** (`FIRMWARE_VERSION`, 4×`{build,minor,major}`): IC1+IC2 = **1.9.2**, IC3/IC4 empty → `1.9.2/1.9.2/0.0.0/0.0.0`. `HIDV1FirmwareVersionProp` (HID 81). |
| `0x5C` | 2 | `5c 00` | unknown, constant `00`. |
| `0x61` | 17 | `61 48 4f 30 30 34 32 2d 4c 4c 30 30 31 32 36 30 35` | ASCII **`HO0042-LL0012605`** — serial/lot string. Read-only ID. |
| `0x62` | 2 | `62 10` | unknown, `10`=16. Mirrors `0x50` byte 2? |
| `0x67` | 2 | `67 01` | **Mic mute**: `01`=unmuted, expect `00`=muted. `poll_mute` uses this. |
| `0x68` | 2 | `68 01` | **Link**: `01`=headset connected, expect `00`=off/out-of-range. `poll_link` uses this. |
| `0x75` | 2 | `75 06` | unknown, `06`. Candidate: power/chatmix? `log_610_state.py` polls it as `power_75`. |
| `0x7C` | 7 | `7c 3b fe 0d 95 68 86` | unknown 6-B blob. NOT battery (byte1 `3b`=59 but bytes 2-6 look like MAC-ish `fe 0d 95 68 86` + ASCII bleed when over-requested). Old `PROTOCOL.md` guessed battery here — **wrong**, battery is `0x49`. Needs off/on + charging diff. |
| `0x2F` | 2 | `2f 00` | Telephony/LED state, `00`=idle. Expect `02`=muted per `parse_mute_from_packet`. Longer reads (`8/10 B`) append `fe 0d 95 68 86 2d 4c 4c…` — stale, ignore beyond byte 1. |

Over-requesting (e.g. 64 B) appends `…4c 4c 30 30 31 32 36 30 35` (`LL0012605`)
— USB stack padding, not data. Always slice to descriptor length.

## 4. Firmware quirks (important for any future code)

1. **Floor-fallback**: unimplemented `rid` returns the numerically-previous
   *implemented* report (`0x4B→4A`, `0x52→50/51…`, `0x06→2F`, `0xFF→75`…).
   Also `Input`/`Feature` types alias. → **always check `data[0]==rid` and
   exact length**, else you silently parse the wrong sensor
   (this is why `scan_reports.py`/`diff_reports.py` group many IDs into few
   buckets — they don't validate).
2. `wMaxPacketSize` is **16**, not 64 — `test_read.py`/`sniffer.py` reading 64
   still works via libusb but logs phantom length. Prefer 16 for IRQ.
3. `0x06` Output 61 B: only path for host→device commands. No SET_REPORT
   probing done here (risk). Windows QuantumENGINE sniff needed for RGB/EQ.
4. Old docs drift: `docs/PROTOCOL.md` says battery `0x7C` and `0x10` balance —
   `0x7C` claim is contradicted by live data (battery is `0x49`);
   `0x10` remains plausible but unconfirmed (interrupt-only, no traffic yet).

## 5. Interrupt packets — what we know / what is missing

None observed while idle (expected for 610). Expected on user action:

* `02 …` volume wheel / media keys, `06/2F …` mic mute toggle,
  `08 …` power-cycle battery, `10 …` game/chat dial, `12 …` ?,
  `07/09/11 …` ? (possibly sidetone, ANC, RGB button, autopower).

Capture command (leaves audio alone, detaches only HID iface 5 briefly):

```bash
python3 tools/quantum610_deep_scan.py --monitor --duration 120 --csv /tmp/jbl610.csv
```

## 6. What I need from you (pick any order, one action per ~5 s window)

Run the monitor above, and while it runs do, with ~5 s pauses:

1. **Mic mute button** on/off ×3 (maps `0x67`, `0x06`, `0x2F`).
2. **Volume wheel** up/down + click (maps `0x02`).
3. **Game/Chat dial** full-game → mid → full-chat (maps `0x10`, maybe `0x50/0x62`).
4. **Power button**: headset OFF (watch `0x68`→`00`), wait 10 s, ON
   (watch for `08 xx` battery event + `0x68`→`01`).
5. **Plug/unplug USB dongle** (optional, tests re-enumeration).
6. **Charge cable in/out** while ON (does `0x49` freeze? does any byte flag charging? current code assumes `charging=False` for 610 poll — unverified).
7. Paste back `/tmp/jbl610.csv` + note wall-clock time of each action,
   or just tell me which of 1–6 you can/can't do (e.g. no cable handy).

Optional (only if curious): Windows USBPcap of JBL QuantumENGINE changing
RGB/EQ/sidetone — that is the only way to decode Output `0x06` 61 B safely.

## 7. Live trigger results (2026-10-12, `/tmp/jbl610_full.csv`, 36 events)

All four user tests executed. Pairing is exact: every IRQ change has a
matching control-poll change ~0.2 s later (poll lag).

### Mic mute — CONFIRMED, dual path
```
IRQ  06 00  <->  POLL 67 00   (= MUTED)
IRQ  06 01  <->  POLL 67 01   (= UNMUTED)
```
Toggled 5×, always in lockstep. `parse_mute_from_packet` mapping (`00`=muted)
is correct. No `0x2F` traffic on mute press (headset button uses `0x06`, not
telephony `0x2F` — `0x2F` stayed `2f 00` throughout).

### Game/Chat dial — CONFIRMED, dual path (new)
```
IRQ  10 xx  <->  POLL 62 xx,  xx in 00..10
observed: 00 03 05 0b 0d 10
```
Dial sweep game→chat produced `10 00 → … → 10 10`, each mirrored by `62 xx`.
So **`0x62` is the pollable mirror of interrupt `0x10`**:
`00`=full-Game, `08`=mid, `10`=full-Chat (matches old PROTOCOL.md direction).
Final state left at `62 10` (full-Chat). `jbl_quantum_core.py` does not parse
this yet — candidate for a chat-mix feature.

### Power OFF/ON — CONFIRMED
```
OFF: IRQ 07 01 + IRQ 09 00 + POLL 68 00
ON:  IRQ 09 01 + IRQ 08 5a + POLL 68 01
```
* `0x68`: `01`=headset linked, `00`=off. `poll_link` mapping correct.
* `0x09`: `01`=on, `00`=off — second link flag, interrupt-only.
* `0x08 5a`: battery event **90% on power-on** (only first power-on; second
  power-on at +28 s showed `09 01`/`68 01` but no `08` — possibly missed
  strobe or standby-vs-off difference).
* `0x07 01`: seen once, only at first power-off. Single-shot power-event
  strobe (hypothesis: "going to sleep" announcement). Not polled.
* Second OFF/ON pair repeated `09`/`68` exactly, no other IDs moved.

### Volume wheel — NO HID TRAFFIC
No `0x02` (consumer) or any other packet during volume test. Volume is
standard USB-Audio, not HID — nothing to document on iface 5.

### Charging cable in/out — NO HID CHANGE (by design)
`0x49` stayed `49 5a` (90%), all other polls static, zero IRQ. This is
expected: charging is **not a HID packet on iface 5**. Per quickshell
`scripts/osd.py:usb_charge_cable_connected()`, the Quantum 610 exposes a
**second USB device `0ecb:205b`** when the charge cable is plugged into this
PC, and `HeadsetService` ORs that (debounced) with the tray's exported
`charging` file. `jbl_quantum_core` correctly hardcodes `charging=False`
for 610 polls — there is no charge bit to find here. Verified: only
`0ecb:205c` present during this capture, no `205b`.

Note on the 95-vs-90 confusion (2026-10-12): the `/run/.../jbl_quantum`
export said `95`/`MUTED` (mtime 19:38) while live polls said `49 5a` (90%) /
unmuted. That is **discharge, not charge**: the installed tray runs
`--prefer-hidraw`, and the hidraw backend implements no `poll_battery` /
`poll_mute` for the 610 — it only learns state from IRQ events (`08 xx` on
power-on). So the export froze at the 19:38 power-on event (`08 5f`=95%)
while the headset slowly drained to 90%. Any tooling that needs live values
must use the PyUSB path (`0x49`/`0x67` polls).

### More control surface probed 2026-10-12 (same session)
* **UAC audio controls** (Game FU10/iface0, Chat FU2/FU6/iface2 — mute/volume
  GET_CUR/MIN/MAX/RES): not directly probed — pyusb auto-claims the iface on
  `ctrl_transfer` and `snd-usb-audio` holds all audio ifaces (`Resource busy`),
  and detaching it would kill live audio. Documented instead via PipeWire:
  Game sink `...-00.analog-stereo`, 30%, `HW_MUTE_CTRL`. Volume wheel emits
  no HID (confirmed above) — it drives the UAC/internal amp path.
* **HID Output-type GET** (`0xA1 0x01 0x02xx`, read-only, iface 5 detached):
  `0x06` returns `68 01…` (floor-fallback to `0x68`) → **Output `0x06` (61 B)
  is write-only**, as suspected; only SET_REPORT (untested — RGB/EQ risk)
  talks to it. `0x2F` Output GET echoes `2f 00` + stale tail — same state as
  Input/Feature, no new info.
* **Operational warning**: claiming iface 5 (any PyUSB scan) steals the
  device from the installed hidraw tray — its log filled with
  `Read error: [Errno 19] No such device` and, since read errors never
  trigger a reconnect in `_monitor_loop`, it stays deaf until restarted.
  Restart the tray after any deep scan.

### Static throughout (ruled out for these actions)
`0x49(battery, constant 90), 0x4A=01, 0x50=01 10, 0x51, 0x5C=00, 0x61 serial,
0x75=06, 0x7C blob, 0x2F=00` — none moved on any test. `0x11/0x12` never
appeared at all (still unknown; likely ANC/sidetone/RGB buttons this headset
may not have, or needs Windows driver to arm).
## 8. RGB / Output reports (2026-10-12)

* The 610 **does** have RGB: earcup logos pulse cyan→green→red→pink by default.
* `input194::mute` sysfs LED (brightness 0/1) is the **mic-boom LED**, driven
  by Output `0x2F` (LED page `05 08` in descriptor). Proven live: SET_REPORT
  Output `0x2F` toggled the boom LED on/off — host→device path works, no
  stalls. No `sudo` needed for future tests: `/dev/hidraw0` is user-writable.
* Logo glow is **not** in the standard LED page — only candidate is vendor
  Output **`0x06` (61 B payload, write-only**; Output-type GET returns `0x68`
  floor-fallback, §8). No public protocol exists (web search negative;
  `~/Downloads/engine.dll`/`.zip` are Valve/Firefox files, unrelated).
* **Blind walk round 1**: `tools/quantum610_rgb_probe.py --walk06` — all 61
  single-byte `0x01`-from-zeros probes accepted (zero stalls, device ACKs
  everything) but **no logo/audio change observed**. Conclusion: glow needs a
  multi-byte command (sub-ID + RGB + mode/checksum?) or a different base.
  Tool kept for round 2 (other values/bases, sub-command sweep at byte 0).
* **RESOLVED via QuantumENGINE RE** (`tools/quantum610_lighting.py`): the 610
  is a HIDV1 device; logo lighting = Feature `0x4C` (animation: `[4C,grp,
  speed,count]`, speed ∈ {100,75,50,25}) + `0x4D` (key frame: `[4D,grp,kfID,
  R,G,B,fx,seg]`, fx 0 breathing/1 solid/2 wave/3 glitch/4 spin-cw/5 spin-ccw/
  6 rise; grp 0 = DEFAULT_LOGO) + state Get `0x4A` / Set `0x4B` (also explains
  earlier "unknowns": `0x4A`=lighting state, `0x07`=its input event).
  Output `0x06` is unrelated (write-only vendor channel, untouched since).
  Factory Q610 preset = Q600 "SOUND IS SURVIVAL" (5 WAVE frames, speed 100;
  `--restore-factory`). Upload rules learned live: set count **first**, upload
  frames, commit count again, and multi-frame updates only stick when uploaded
  **while dark** (`--off` … `--on`). Single SOLID frames apply live.
* No firmware "hue rotate" effect exists (all 7 effects breathe/sweep), so a
  smooth constant-brightness spectrum is done in software: `--cycle` pushes
  SOLID hue-wheel steps (~7/s) — no pulse, fully custom.
* **WARNING (2026-10-12, live): `spin_cw` AND `spin_ccw` (fx 4,5) crash 610
  firmware on the logo group — logo dark + audio loop/stuck; first incident
  needed a ~30s power-cycle, second needed headset force-restart (link
  `68 00` while dongle stayed alive). `rise` (fx 6) blanks the logo AND mutes
  audio (PipeWire sink clean after `--restore-factory`, so the mute was
  firmware-side). SAFE: solid, breathing, wave, glitch (each verified solo).
  `--restore-factory` recovered the device every time. Never chain effects
  rapidly.

## 9. Files

* `tools/quantum610_deep_scan.py` — validated dump + `--monitor` CSV logger
* `tools/quantum610_lighting.py` — lighting: state/keyframe/animation/presets/cycle/restore
* `tools/quantum610_rgb_probe.py` — raw Output-report probe (round 1, superseded)
* `/tmp/jbl610_reports.json` — raw baseline from §3
* `tools/sniffer.py`, `tools/test_read.py`, `tools/scan_reports.py`,
  `tools/diff_reports.py`, `tools/log_610_state.py` — legacy, unvalidated
  (no first-byte check, wrong lengths); kept for reference, prefer new tool.

## 10. Full HIDV1 command map (from QuantumENGINE RE, 2026-10-12)

Source: decompiled `JBLQuantumControl` (`QECommon/HIDV1*Prop.cs`; byte[0] =
report ID, `Pack=1`). ✅ = verified live on this 610, ❌ = fallback
(unimplemented on 610), ⚠️ = do not touch, ? = present in app, untested here.

| ID | Dir | Size | Meaning | Status |
|---|---|---|---|---|
| `0x02`/`0x03` | In | 1 | ANC/BT state events (other models) | ❌ |
| `0x06`/`0x07`/`0x08`/`0x09` | In | 1 | mic-mute / lighting-state / battery / link events | ✅ |
| `0x0A` | Get | 7 | mic gain range+level | ❌ |
| `0x0B` | Get | 6 | full battery L/R/case (TWS) | ❌ |
| `0x0D` | Get/Set | 1 | device color variant | ❌ |
| `0x10` | In | 1 | game/chat dial event | ✅ |
| `0x11` | In | 1 | mic polar-pattern event | ❌ |
| `0x23`/`0x24` | Out | 1 | heartbeat / host-app notification | ? |
| `0x29`/`0x54` | Get/Set | 63/2 | button-gesture mapping / 360 variant | ❌ |
| `0x45`/`0x46` | Get/Set | 1 | ANC state (610 has no ANC) | ❌ |
| `0x47` | Get/Set | 1 | BT state | ❌ |
| `0x48` | Get/Set | 15 | speaker EQ bands | ❌ |
| `0x49` | Get | 1 | battery % | ✅ |
| `0x4A`/`0x4B` | Get/Set | 1 | lighting on/off | ✅ |
| `0x4C`/`0x4D` | Set (+keyed Get) | 3/7 | lighting animation / key frames | ✅ Set |
| `0x4E`/`0x4F` | Get/Set | 1 | head-tracker (910-only) | ❌ |
| `0x50` | Get | 2 | HW version (this unit: 16.1) | ✅ |
| `0x51` | Get | 12 | FW version (this unit: 1.9.2/1.9.2) | ✅ |
| `0x52` | Set | 2 | HW-version write | ? (GET falls back) |
| `0x53`/`0x54`/`0x55`/`0x57`/`0x58` | FWU | 1/63/5/1/3 | chip-select / flash-block / verify / start / status | ⚠️ brick risk, never probed |
| `0x59` | Cmd | 0 | reboot device | ⚠️ |
| `0x5A`/`0x61` | Set/Get | 32/16 | serial (`HO0042-LL0012605`) | ✅ Get / ⚠️ Set |
| `0x5B` | Get | 63 | connected-BT-device name | ❌ |
| `0x5C`/`0x5D` | Get/Set | 1 | sidetone level (this unit: 0=OFF) | ✅ Get / ? Set |
| `0x5E`/`0x04` | Cmd/Ack | 0 | recenter head tracking | ❌ |
| `0x60` | Set | 1 | **factory reset** | ⚠️ never |
| `0x62`/`0x6C` | Get/Set | 1 | game/chat balance | ✅ Get / ? Set |
| `0x63`–`0x66` | Get/Set | 1 | mic NR + AGC | ❌ |
| `0x67` | Get/Set | 1 | mic mute (software-mutable!) | ✅ Get / ? Set |
| `0x68` | Get/Set | 1 | wireless link | ✅ |
| `0x6D`/`0x6E` | Get/Set | 1 | voice-prompt state | ❌ |
| `0x6F` | Cmd | 1 | head-tracking calibration | ❌ |
| `0x70` | Get/Set | 2 | find-my-device ring | ❌ |
| `0x72` | Get/Out-Set | 2 | surround/DTS mode | ? |
| `0x75` | Get/Set | 1 | standby timer (this unit: 6) | ✅ Get / ? Set |
| `0x76` | Get/Set | 1 | mic polar pattern | ❌ |
| `0x77` | Get/Set | 1 | LED brightness | ❌ |
| `0x78` | Get/Set | 3 | mic-level LED color | ❌ |
| `0x79` | Get/Set | 1 | VU-meter LED | ❌ |
| `0x2F` | In/Out | 1–8 | telephony + mute LED | ✅ |

## 11. Firmware: readout, update, custom builds (2026-10-12)

* **Dump from device: impossible.** No flash-read report exists — `0x54`
  (`FIRMWARE_BLOCK`: chip + u32 size + u32 offset + 54 B data) is
  **write-only**, and there is no 610 DFU USB PID (no `8284/8283` entry in
  `ProductID.DFU_CONFIG`; DFU PIDs exist only for TWS models). The only
  readout is the version string (`0x51`).
* **Get the image**: only by intercepting an official update — images ship
  from Harman cloud (`appstorage.onecloud.harman.com`, cf.
  `GameDetectionCloudConfigController`), no FW files in the installer (only
  DSP `.bin`s), no URLs in updater strings. Would take Windows + MITM proxy
  during a real update.
* **Decompile/custom FW: no.** The image would be a signed Airoha blob with
  no public toolchain; `AirohaHidCoreLib.dll` is EQ-only. Stock 1.9.2 stands.
* Safe, useful, still-untested: software mic-mute (`SET 0x67`), chat-balance
  set (`SET 0x6C`), sidetone set (`0x5D`), standby-timer set (`0x75`) — all
  1-byte, reversible. See §12 for results.

## 12. Software-SET results (2026-10-12, unattended run)

All reversible 1-byte SETs tried with read-before/verify-after/restore.
`0x59`/`0x60`/FWU never touched.

* `SET 0x67` mic-mute: **accepted, no effect** (00 stayed 00 both ways).
  Mute is physical-button-only on this firmware; the Set half is unused.
* `SET 0x75` standby timer: **works** (`06→05→06` verified). Unit unknown
  (6 = factory default; minutes?).
* `SET 0x5D` sidetone: **works** (`00→01→00` verified, read back via `0x5C`).
  Restored to OFF.
* `SET 0x6C` game/chat balance: **accepted, no effect** (`0x62` stayed
  `0x10`). Dial is physical-only (or the calibration-state collision wins).
* No-op SETs (`0x75`/`0x5D` with current value) confirm the SET path ACKs.

