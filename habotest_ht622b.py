#!/usr/bin/env python3
"""
HT622B Sound Level Meter - Real-Time Decoder
=============================================
Based on official protocol: HT622B上位机通讯协议-V0.0

Frame structure (23 bytes, 9600 baud, 8N1):
  Bytes 0-1:  Model1=0x06, Model2=0x2A (header)
  Byte 2:     SumBytes=0x11 (17 data bytes)
  Byte 3:     Type=0x01 (real-time)
  Bytes 4-19: D15-D0 (16 bytes of HT1621 LCD RAM)
  Bytes 20-22: Footer 0x0D 0x0A 0x00

Digit Mapping (cross-byte HT1621 RAM layout):
  Tens:   PIN 10 (byte 6 high) + PIN 11 (byte 7 low)
  Units:  PIN 12 (byte 7 high) + PIN 13 (byte 8 low)
  Tenths: PIN 14 (byte 8 high) + PIN 15 (byte 9 low)
"""

import serial

# --- CONFIGURATION ---
SERIAL_PORT = "/dev/tty.usbserial-111230"
BAUD_RATE = 9600
FRAME_LEN = 23
# ---------------------

# Standard 7-segment: (a, b, c, d, e, f, g)
SEGMENTS_TO_NUM = {
    (1, 1, 1, 1, 1, 1, 0): "0",
    (0, 1, 1, 0, 0, 0, 0): "1",
    (1, 1, 0, 1, 1, 0, 1): "2",
    (1, 1, 1, 1, 0, 0, 1): "3",
    (0, 1, 1, 0, 0, 1, 1): "4",
    (1, 0, 1, 1, 0, 1, 1): "5",
    (1, 0, 1, 1, 1, 1, 1): "6",
    (1, 1, 1, 0, 0, 0, 0): "7",
    (1, 1, 1, 1, 1, 1, 1): "8",
    (1, 1, 1, 1, 0, 1, 1): "9",
}


def decode_digit(pin_left, pin_right):
    """
    Decode a standard LCD digit split across two HT1621 PIN addresses.
    pin_left  contains: COM3=f, COM2=g, COM1=e, COM0=DecimalPoint
    pin_right contains: COM3=a, COM2=b, COM1=c, COM0=d
    """
    f = (pin_left >> 3) & 1
    g = (pin_left >> 2) & 1
    e = (pin_left >> 1) & 1
    p = (pin_left >> 0) & 1

    a = (pin_right >> 3) & 1
    b = (pin_right >> 2) & 1
    c = (pin_right >> 1) & 1
    d = (pin_right >> 0) & 1

    char = SEGMENTS_TO_NUM.get((a, b, c, d, e, f, g), "?")
    return char, p


def print_frame_and_decode(frame):
    # Extract 32 PINs from 16 bytes (D15-D0)
    # Each byte = 2 PINs: low nibble = odd PIN, high nibble = even PIN
    pins = {}
    for i in range(16):
        byte_val = frame[4 + i]
        pins[5 + (i * 2)] = byte_val & 0x0F          # Odd PIN
        pins[6 + (i * 2)] = (byte_val >> 4) & 0x0F   # Even PIN

    # Decode digits using cross-byte HT1621 RAM mapping
    tens, p3   = decode_digit(pins[10], pins[11])  # Digit 3 (P3, leftmost)
    units, p2  = decode_digit(pins[12], pins[13])  # Digit 2 (P2, middle)
    tenths, p1 = decode_digit(pins[14], pins[15])  # Digit 1 (P1, rightmost)

    # Format decimal dynamically based on active hardware flags
    # P2 decimal sits between tens and units. P1 decimal sits between units and tenths.
    measured_value = f"{tens}{'.' if p2 else ''}{units}{'.' if p1 else ''}{tenths}"

    # Extract UI Flags by masking specific PIN/COM intersections
    is_hold    = bool(pins[7] & 0x04)   # PIN 7, COM2 (H icon)
    weight_dba = bool(pins[5] & 0x01)   # PIN 5, COM0 (A icon)
    weight_dbc = bool(pins[7] & 0x01)   # PIN 7, COM0 (C icon)

    speed_fast = bool(pins[35] & 0x02)  # PIN 35, COM1 (FAST text)
    speed_slow = bool(pins[25] & 0x08)  # PIN 25, COM3 (SLOW text)

    is_max     = bool(pins[29] & 0x08)  # PIN 29, COM3 (MAX text)
    is_min     = bool(pins[27] & 0x08)  # PIN 27, COM3 (MIN text)

    is_under   = bool(pins[9] & 0x04)   # PIN 9, COM2 (UNDER text)
    is_over    = bool(pins[16] & 0x08)  # PIN 16, COM3 (OVER text)

    # Determine active states
    weight_text = "dBA" if weight_dba else ("dBC" if weight_dbc else "UNKNOWN")
    speed_text  = "FAST" if speed_fast else ("SLOW" if speed_slow else "UNKNOWN")

    mode_text = "NORMAL"
    if is_max: mode_text = "MAX"
    if is_min: mode_text = "MIN"

    limit_text = "NORMAL"
    if is_under: limit_text = "UNDER"
    if is_over: limit_text = "OVER"

    print("\n" + "=" * 40)
    print(f"Raw: {' '.join(f'{b:02X}' for b in frame)}")
    print(f"Modes: HOLD={'ON' if is_hold else 'OFF'} | SPEED={speed_text} | WEIGHT={weight_text} | MODE={mode_text} | LIMIT={limit_text}")
    print(f"Value: {measured_value} {weight_text}")
    print("=" * 40)


def main():
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            print(f"HT622B Decoder running on {SERIAL_PORT} at {BAUD_RATE} baud...")
            print("Press Ctrl+C to stop.\n")
            while True:
                frame = ser.read(FRAME_LEN)
                if len(frame) == FRAME_LEN and frame[0:2] == b'\x06\x2A' and frame[3] == 0x01:
                    print_frame_and_decode(frame)
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()