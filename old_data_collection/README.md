# Habotest HT622B Sound Level Meter - Protocol Reverse Engineering

A Python-based parser and protocol specification for reverse-engineering the serial data stream of the **Habotest HT622B Digital Sound Level Meter**.

---

## 🚀 The Core Discovery: Raw LCD Display RAM Streaming

Initial reverse-engineering attempts treated the serial stream from the Habotest HT622B as a standard byte-to-digit lookup protocol. **This assumption was proven fundamentally wrong.** Through systematic frame analysis, we discovered that the device is actually streaming the **raw, multiplexed physical display RAM directly from the microcontroller/LCD driver** (akin to a Holtek HT1621 matrix arrangement).

### The COM / SEG Multiplexing Challenge

The bytes sent in the data stream represent segment activation patterns across shared **COM (Common)** and **SEG (Segment)** lines on the physical glass panel. Because lines are shared to save pins:

* The same raw byte value represents completely different digits depending on its position and the hardware's active multiplexing state.
* For example, the byte `0x3F` can decode to **0, 3, 8, or 9** depending entirely on cross-frame context flags.
* A single state change in the meter (such as crossing from the 40 dB to the 50 dB block) alters the electrical routing, shifting the data matrix completely.

---

## 📊 Hardware-Level Protocol Structure

Each raw data frame is exactly **23 bytes** long, updating fluidly based on the device's sampling configuration.

| Byte Index | Purpose | Hardware Mechanics / Observed Behavior |
| :--- | :--- | :--- |
| **0 - 3** | **Header** | Fixed preamble: `06 2A 11 01` |
| **4** | **Range Mask** | Base measurement boundaries (e.g., 30-130 dB) |
| **5** | **Control Flags** | Bit `0x04` manages `HOLD`; Lowest bit toggles `dBA` vs `dBC` |
| **6** | **Limits** | Detects display `UNDER` or `OVER` alarm bounds |
| **7** | **Tens Digit** | Raw multiplexed LCD segments for the primary digit (`4x.x`, `5x.x`) |
| **8** | **Units Digit** | Raw multiplexed LCD segments for the secondary digit |
| **9** | **Tenths Digit** | Raw multiplexed LCD segments for the decimal digit |
| **14** | **Matrix Switch Flag** | **The Master Tie-Breaker:** Dictates LCD COM state (`0x08` for 40s/50s; `0x00` for 60s) |
| **15 - 16** | **Mode Selector** | Active UI flags for `MAX` or `MIN` profile indicators |
| **19** | **Speed Flag** | `0x02` for `FAST` response mode; `0x00` for `SLOW` mode |
| **20 - 22** | **Footer** | Consistent frame termination delimiter: `0D 0A 00` (CR / LF) |

---

## 🛠️ Current Progress

### Tens Digit (Byte 7) — Partially Mapped

We have observed these byte-to-digit mappings:

| Byte | Byte 14 | Digit | Example |
|------|---------|-------|---------|
| `0xE6` | `0x00` | 4 | 48.x range |
| `0xC6` | `0x08` | 4 | 49.x range |
| `0xAB` | `0x08` | 5 | 50.x range |
| `0x0B` | `0x08` | 5 | 51.x, 57.x range |
| `0x4B` | `0x08` | 5 | 53.x range |
| `0x0B` | `0x00` | 6 | 61.x range |

**Hypothesis:** Bits 7, 5, and 4 carry position/state data. Masking with `0x4F` (0100 1111) isolates the segment pattern:

* `0xE6 (1110 0110) & 0x4F` → `0x46`
* `0xC6 (1100 0110) & 0x4F` → `0x46`
* `0xAB (1010 1011) & 0x4F` → `0x0B`
* `0x0B (0000 1011) & 0x4F` → `0x0B`
* `0x4B (0100 1011) & 0x4F` → `0x0B`

This suggests `0x46` = digit **4**, and `0x0B` = digit **5** or **6** (split by Byte 14 state).

**Status:** Validated for digits 4, 5, 6. Needs data for digits 0, 1, 2, 3, 7, 8, 9.

### Units Digit (Byte 8) — Context-Dependent

Same byte value maps to different digits depending on Byte 14 and possibly other flags.

| Byte | Context | Digit | Example |
|------|---------|-------|---------|
| `0xBF` | `0x00` | 8 | 48.0 |
| `0xBF` | `0x08` | 9 | 49.0 |
| `0xBF` | `0x08` | 0 | 50.0 |
| `0x1F` | `0x00` | 8 | 48.7 |
| `0x1F` | `0x08` | 9 | 49.1 |
| `0x1F` | `0x08` | 0 | 50.1 |
| `0x5F` | `0x00` | 8 | 48.3 |
| `0x5F` | `0x08` | 0 | 50.3 |
| `0xDF` | `0x00` | 8 | 48.4 |
| `0xDF` | `0x08` | 9 | 49.9 |
| `0xDF` | `0x08` | 0 | 50.5 |
| `0xFF` | `0x00` | 8 | 48.8 |
| `0xFF` | `0x08` | 9 | 49.8 |
| `0xD6` | `0x08` | 1 | 51.5 |
| `0xB6` | `0x00` | 1 | 61.0 |
| `0x7E` | `0x00` | 7 | 57.2 |
| `0x1E` | `0x00` | 7 | 57.7 |
| `0xDE` | `0x08` | 7 | 57.9 |

No stable masking found yet. Needs systematic data.

### Tenths Digit (Byte 9) — Partially Mapped

| Byte | Context | Digit | Example |
|------|---------|-------|---------|
| `0x3F` | `0x00` | 0 | 48.0 |
| `0x3F` | `0x00` | 3 | 48.3 |
| `0x3F` | `0x08` | 0 | 49.0 |
| `0x3F` | `0x08` | 8 | 49.8 |
| `0x3F` | `0x08` | 9 | 49.9 |
| `0x3F` | `0x08` | 3 | 50.3 |
| `0x36` | `0x00` | 4 | 48.4 |
| `0x36` | `0x08` | 1 | 49.1 |
| `0x36` | `0x08` | 4 | 53.4 |
| `0x3E` | `0x00` | 7 | 48.7 |
| `0x3E` | `0x00` | 7 | 57.7 |
| `0x3B` | `0x08` | 5 | 49.5 |
| `0x3B` | `0x08` | 5 | 50.5 |
| `0x3B` | `0x08` | 5 | 51.5 |
| `0x3D` | `0x00` | 2 | 57.2 |
| `0x0F` | `0x00` | 8 | 48.8 |

Same context-dependency problem. Needs decade sweeps.

---

## 📋 Data Collection Checklist

We need **at least one frame** for each of the following. Check off what you can provide in an Issue or PR.

### Tens Digit (needs digits 0, 1, 2, 3, 7, 8, 9)
- [ ] 30.x dB (tens digit = 3)
- [ ] 70.x dB (tens digit = 7)
- [ ] 80.x dB (tens digit = 8)
- [ ] 90.x dB (tens digit = 9)
- [ ] 100.x dB (tens digit = 0)
- [ ] 20.x dB (tens digit = 2) — if your meter supports it
- [ ] 10.x dB (tens digit = 1) — if your meter supports it

### Units Digit (needs digits 2, 4, 5, 6)
- [ ] x2.x dB (units digit = 2) — e.g., 32.0, 42.0, 52.0
- [ ] x4.x dB (units digit = 4) — e.g., 34.0, 44.0, 54.0
- [ ] x5.x dB (units digit = 5) — e.g., 35.0, 45.0, 55.0
- [ ] x6.x dB (units digit = 6) — e.g., 36.0, 46.0, 56.0

### Tenths Digit (needs digits 1, 2, 5, 6, 7 in all contexts)
- [ ] xx.1 dB with byte14=0x00
- [ ] xx.2 dB with byte14=0x08
- [ ] xx.5 dB with byte14=0x00
- [ ] xx.6 dB with byte14=0x08
- [ ] xx.7 dB with byte14=0x08

### Full Decade Sweeps
- [ ] 50.0 through 59.9 (to chart sequential bit stepping)
- [ ] 60.0 through 69.9
- [ ] 70.0 through 79.9
- [ ] 80.0 through 89.9
- [ ] 90.0 through 99.9

### Edge Cases
- [ ] All segments lit (hold MAX while powering on)
- [ ] Over-range / OL display
- [ ] Under-range display
- [ ] Low battery warning
- [ ] Bar graph at various levels

---

## 📝 How to Submit Data

Open a GitHub Issue with this template:

```
### Data Submission
**Target Reading:** 52.3 dB
**Range:** 50-100
**Mode:** NORMAL
**Speed:** SLOW
**Weight:** dBA
**HOLD:** OFF

**Raw Frame:**
```
06 2A 11 01 05 0E C0 AB 5F 3F 00 0F 00 00 08 00 00 00 00 00 0D 0A 00
```

**Quick Decode Check:**
- Byte 14 = `0x08` (shifted context)
- Byte 7 = `0xAB` → tens digit = 5
- Byte 8 = `0x5F` → units digit = 2
- Byte 9 = `0x3F` → tenths digit = 3
```

### Quick Frame Decode Guide

For any captured frame, you can immediately check:

| Byte/Bit | Meaning |
|----------|---------|
| **Byte 14 = `0x00`** | "Standard" context (used for 40s, 60s, 70s digits) |
| **Byte 14 = `0x08`** | "Shifted" context (used for 50s digits, some 40s/60s) |
| **Byte 5 & 0x04** | HOLD = ON if set |
| **Byte 5 & 0x01** | dBC if set, dBA if clear |
| **Byte 19 = 0x02** | FAST mode, otherwise SLOW |
| **Byte 15 & 0x08** | MIN mode active |
| **Byte 16 & 0x08** | MAX mode active |
| **Byte 6 & 0x04** | UNDER limit triggered |

---

## 💻 Quick Start

### Prerequisites
```bash
pip install pyserial
```

### Running the Parser

1. Connect the HT622B via its serial/USB interface.
2. Edit `SERIAL_PORT` in `habotest_parser.py` to point to your device node (`/dev/tty...` or `COMx`).
3. Run:

```bash
python habotest_parser.py
```

---

## 🤝 Contributing

If you have access to an HT622B and want to contribute missing segment mappings, please open an Issue! Always include:

1. Your physical screen reading
2. The raw 23-byte hex output frame
3. The meter's current settings (range, mode, speed, weighting, hold state)
4. The value of Byte 14 from the frame

---

## 📚 References

- [Holtek HT1621 LCD Driver Datasheet](https://www.holtek.com/productdetail/-/vg/HT1621) — For understanding COM/SEG multiplexing
- [CEM DT-8852 Protocol (sigrok)](https://sigrok.org/wiki/CEM_DT-8852) — Similar meter, different protocol, useful for comparison
- [7-Segment Display Encoding](https://en.wikipedia.org/wiki/Seven-segment_display) — Standard segment layouts

---

## License

MIT License — See LICENSE file for details.
