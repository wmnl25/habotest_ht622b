# HT622B Protocol Reverse Engineering — Data Collection Guide

## The Problem (Recap)

Your HT622B sound level meter sends 23-byte frames over USB-serial. The display
digits are encoded in bytes 7 (tens), 8 (units), and 9 (tenths). **However**, the
same byte value can represent completely different digits depending on:
- Which digit position it's in (tens vs units vs tenths)
- The value of frame[14] (a context/state byte)
- Possibly other state flags (mode, range, hold)

This is because the bytes are **raw LCD segment activation patterns**, not encoded
digit values. The meter's microcontroller (likely Holtek HT49R70A) streams its
internal LCD display RAM directly.

## What You Need to Capture

### Hardware Setup
1. HT622B meter connected via USB
2. A stable sound source (phone/laptop with tone generator app)
3. The collection script running on your computer

### Software
- `ht622b_collector.py` — interactive capture tool
- `ht622b_analyzer.py` — generates decoder from captured data

## Step-by-Step Collection Protocol

### Phase 1: Baseline Coverage (30 minutes)

**Goal**: Capture at least one example of every digit (0-9) in every position.

Use a tone generator app. Set the meter to **30-80 dB range**, **NORMAL mode**,
**SLOW speed**, **dBA weighting**, **HOLD=OFF**.

For each target value below, hold the tone steady for 3 seconds while the
capture script records:

```
30.0, 30.1, 30.2, 30.3, 30.4, 30.5, 30.6, 30.7, 30.8, 30.9
31.0, 31.1, 31.2, 31.3, 31.4, 31.5, 31.6, 31.7, 31.8, 31.9
32.0, 32.1, 32.2, 32.3, 32.4, 32.5, 32.6, 32.7, 32.8, 32.9
...
39.0, 39.1, 39.2, 39.3, 39.4, 39.5, 39.6, 39.7, 39.8, 39.9
```

**Why 30.x?** Because 30-39 covers digits 0-9 in the units position, and 3 in
the tens position. This is the most efficient way to get full digit coverage.

For each capture, enter:
- Target dB: `30.0`
- Notes: `range=30-80 mode=NORMAL speed=SLOW weight=A hold=OFF`

### Phase 2: Context Variations (20 minutes)

**Goal**: Determine which state flags change the digit encoding.

From your existing data, we know `frame[14]` is critical. We need to see if
other flags (MIN/MAX mode, different ranges) also create new contexts.

Repeat Phase 1 values but with different settings:

1. **MIN mode**: Press MIN button, capture 30.0-39.9
2. **MAX mode**: Press MAX button, capture 30.0-39.9
3. **HOLD=ON**: Press HOLD, capture 30.0-39.9
4. **dBC weighting**: Switch to dBC, capture 30.0-39.9
5. **FAST speed**: Switch to FAST, capture 30.0-39.9

After each batch, run the analyzer and check if new "contexts" appeared in the
mapping. If the digit bytes are identical across contexts, those flags don't
affect encoding.

### Phase 3: Range Coverage (30 minutes)

**Goal**: Capture values across all meter ranges.

The meter has these ranges: 30-80, 40-90, 50-100, 60-110, 70-120, 30-130(auto)

For each range, capture:
- The minimum value (e.g., 30.0 for 30-80 range)
- The maximum value (e.g., 79.9 for 30-80 range)
- A mid-range value with all digits changing (e.g., 45.6, 67.8)

This tests if the range setting changes the digit encoding context.

### Phase 4: Edge Cases (10 minutes)

1. **All segments on**: Hold MAX + power on (or HOLD + power on) to light all
   LCD segments. Capture this "test pattern" — it reveals the full segment map.
2. **Over-range**: Expose meter to very loud sound (>130 dB) to capture "OL"
   (overload) display pattern.
3. **Under-range**: Very quiet room to capture "UNDER" indicator.
4. **Battery low**: If possible, trigger low battery warning.

### Phase 5: Full Sweep (Optional, 2+ hours)

If you want a 100% complete decoder, capture every 0.1 dB step from 30.0 to
130.0. This is tedious but guarantees no gaps. Use an automated tone generator
that can sweep slowly.

## How to Use the Capture Script

```bash
python ht622b_collector.py
```

The script will:
1. Connect to the meter at 9600 baud
2. Prompt you for target dB and notes
3. Capture 3 seconds of frames (~60 frames at 20 Hz)
4. Save to `ht622b_capture.csv`

**Pro tip**: The meter sends data at ~20 Hz. 3 seconds gives you ~60 samples
per reading. The analyzer will use all of them to verify consistency.

## How to Analyze Results

After each collection session:

```bash
python ht622b_analyzer.py ht622b_capture.csv
```

This will:
1. Build lookup tables for each digit position and context
2. Check for ambiguous mappings (same byte mapping to multiple digits)
3. Generate `ht622b_decoder_generated.py` — a ready-to-use decoder
4. Generate `ht622b_mapping.json` — human-readable mapping tables
5. Report coverage gaps (missing digits/contexts)

## Reading the Coverage Report

The analyzer outputs something like:

```
TENS:
  Total contexts: 2
  Unambiguous mappings: 5
  Conflicts: 0

UNITS:
  Total contexts: 2
  Unambiguous mappings: 8
  Conflicts: 2
  Conflicting mappings:
    Context ('0x00', 'NORMAL', '0x05'): byte 0xBF -> digits {8, 9}
```

**Conflicts** mean the same byte appears for two different digits in the same
context. This happens when:
- The tone wasn't stable during capture
- The digit actually changed mid-capture
- There's a real ambiguity that needs more context bits to resolve

If you see conflicts, re-capture those specific values with HOLD=ON to freeze
the display.

## Expected Data Size

| Phase | Readings | Frames | File Size |
|-------|----------|--------|-----------|
| Phase 1 (30-39.9) | 100 | ~6,000 | ~2 MB |
| Phase 2 (contexts) | 500 | ~30,000 | ~10 MB |
| Phase 3 (ranges) | 50 | ~3,000 | ~1 MB |
| Phase 4 (edge cases) | 20 | ~1,200 | ~400 KB |
| Phase 5 (full sweep) | 1000 | ~60,000 | ~20 MB |

## Success Criteria

Your decoder is "complete" when:
- [ ] All digits 0-9 are mapped for TENS position in all contexts
- [ ] All digits 0-9 are mapped for UNITS position in all contexts
- [ ] All digits 0-9 are mapped for TENTHS position in all contexts
- [ ] No conflicts remain in the mapping
- [ ] The generated decoder correctly predicts all your test values

## Troubleshooting

**"No frames captured"**
- Check serial port name (`ls /dev/tty.*` on Mac, `ls /dev/ttyUSB*` on Linux)
- Ensure meter is powered on and USB is connected
- Try pressing SETUP button on meter to start streaming

**"Inconsistent readings for same target"**
- Use HOLD mode to freeze display during capture
- Ensure sound source is stable (not fluctuating)
- Increase capture time to 5 seconds

**"Too many contexts"**
- If every capture creates a new context, you're including too many state flags
- The analyzer uses (byte14, mode, range) as context. If you have 20 contexts,
  check if some flags (like speed or hold) are unnecessarily changing the hash.
  Edit `get_context()` in the analyzer to remove irrelevant flags.

## Next Steps After Collection

Once you have complete coverage:
1. The generated decoder will work for 99% of cases
2. For the remaining 1%, we can derive the actual LCD segment bit patterns
3. With segment patterns, we can build a "true" decoder that works for ANY value,
   even ones you didn't explicitly capture
