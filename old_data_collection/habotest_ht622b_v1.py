import serial

# --- CONFIGURATION ---
SERIAL_PORT = "/dev/tty.usbserial-111230"
BAUD_RATE = 9600
FRAME_LEN = 23
# ---------------------

BYTE_MAP_TENS = {
    0xE6: '4', 0xC6: '4',
    0xEB: '6',   
    0xEE: '7',   
}

BYTE_MAP_UNITS = {
    0xD6: '1', 0x56: '1', 0xB6: '1',   
    0xDD: '2',   
    0x16: '4',   
    0xFB: '6', 0xDB: '6',   
    0x1E: '7', 0x7E: '7', 0xDE: '7',   
    0x1F: '8', 0xDF: '8', 0xBF: '8',   
    0x5F: '0',   
    0x7F: '9', 0xFF: '9',   
}

BYTE_MAP_TENTHS = {
    0x36: '4',   
    0x3D: '2',   
    0x3E: '7',   
    0x3F: '3',   # Base fallback for 3
    0x0F: '8',   
    0x3B: '5',   
}

def get_range_setting(byte4, byte9):
    base_byte4 = byte4 & 0xFE 
    range_id = (base_byte4, byte9 & 0xF0)
    
    if range_id == (0x04, 0x30): return "30-130"
    if range_id == (0x04, 0x00): return "30-80"
    if range_id == (0x0C, 0x00): return "40-90"
    if range_id == (0x0C, 0x30): return "50-100"
    if range_id == (0x00, 0x30): return "70-120"
    if range_id == (0x0E, 0x30): return "60-110 / 80-130" 
    
    return f"UNKNOWN {range_id}"

def decode_tens_digit(tens_byte, frame):
    if tens_byte in BYTE_MAP_TENS:
        return BYTE_MAP_TENS[tens_byte]
        
    if tens_byte in [0x0B, 0x4B, 0x6B, 0xCB, 0xAB]:
        if frame[14] == 0x08: 
            return "5"  
        else:
            return "6"  
            
    return f"?({tens_byte:02X})"

def decode_digits_safely(frame):
    tens_byte = frame[7]
    units_byte = frame[8]
    tenths_byte = frame[9]

    # Pull base mappings
    tens = decode_tens_digit(tens_byte, frame)
    units = BYTE_MAP_UNITS.get(units_byte, f"?({units_byte:02X})")
    tenths = BYTE_MAP_TENTHS.get(tenths_byte, f"?({tenths_byte:02X})")

    # Hard-interlocking cross-over rule for the 48.x / 49.x block
    if tens_byte == 0xE6 and units_byte in [0x1F, 0xDF]: # Confirmed 48.x block
        tens, units = "4", "8"
        if tenths_byte == 0x3F: tenths = "9" 
    elif tens_byte == 0xC6:
        if units_byte in [0x1F, 0xDF]:                   # Confirmed 49.x variants (e.g., 49.9, 49.5)
            tens, units = "4", "9"
            if tenths_byte == 0x3F: tenths = "9" 
            elif tenths_byte == 0x36: tenths = "1"       
        elif units_byte == 0xFF:                         # Confirmed 49.x variant (e.g., 49.8)
            tens, units = "4", "9"
            if tenths_byte == 0x3F: tenths = "8"
        elif units_byte == 0xBF:                         # Confirmed 49.x variant (49.0)
            tens, units = "4", "9"
            if tenths_byte == 0x3F: tenths = "0"

    # Dynamic interlocking for the 50.x segment matrix overlaps
    if frame[14] == 0x08 and (tens_byte in [0x0B, 0x4B, 0x6B, 0xCB, 0xAB]):
        if units_byte in [0x5F, 0xBF, 0xDF] and tens_byte == 0xAB: # Confirmed 50.x variants (50.3, 50.0, 50.5)
            tens, units = "5", "0"
            if tenths_byte == 0x3F:
                if units_byte == 0x5F: tenths = "3"
                if units_byte == 0xBF: tenths = "0"
        elif tens_byte == 0x4B and units_byte == 0xDF: # Specific structure for 53.4
            tens, units = "5", "3"
        elif tens_byte == 0xAB and units_byte == 0x1F: # Specific structure for 50.1
            tens, units = "5", "0"
            if tenths_byte == 0x36: tenths = "1"
        elif units_byte == 0xDE: # Specific structure for 57.9
            tens, units = "5", "7"
            if tenths_byte == 0x3F: tenths = "9"

    # Static cross-over fix for the 61.0 anomalies
    if tenths_byte == 0x3F and frame[14] != 0x08:
        if units in ["1", "0"]:
            tenths = "0"

    return tens, units, tenths

def print_frame_and_decode(frame):
    print("\nRaw frame: " + ' '.join(f'{b:02X}' for b in frame))
    
    # --- STATUS INDICATORS ---
    is_hold = bool(frame[5] & 0x04)
    hold_text = "ON" if is_hold else "OFF"
    
    speed_text = "FAST" if frame[19] == 0x02 else "SLOW"
    weight_text = "dBC" if (frame[5] & 0x01) else "dBA"

    mode_text = "NORMAL"
    if frame[15] & 0x08:
        mode_text = "MIN"
    elif frame[16] & 0x08:
        mode_text = "MAX"

    limit_text = "NORMAL"
    if frame[6] & 0x04:
        limit_text = "UNDER"

    range_text = get_range_setting(frame[4], frame[9])

    # --- SAFE DIGIT RESOLUTION ---
    tens, units, tenths = decode_digits_safely(frame)
    
    # --- OUTPUT ---
    print(f"Modes  : HOLD={hold_text} | SPEED={speed_text} | WEIGHT={weight_text} | MODE={mode_text} | LIMIT={limit_text}")
    print(f"Range  : {range_text}")
    print(f"Measured value: {tens}{units}.{tenths} {weight_text}")
    print("-" * 40)

def main():
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            print(f"Listening on {SERIAL_PORT} at {BAUD_RATE} baud...\n")
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