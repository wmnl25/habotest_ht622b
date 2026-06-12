import serial
import csv
import time
from datetime import datetime

# --- CONFIGURATION ---
SERIAL_PORT = "/dev/tty.usbserial-111230"  # Change to your port
BAUD_RATE = 9600
FRAME_LEN = 23
OUTPUT_FILE = "ht622b_capture.csv"
# ---------------------

def get_frame(ser):
    """Read one valid frame from serial"""
    while True:
        byte = ser.read(1)
        if not byte:
            return None
        if byte[0] == 0x06:
            rest = ser.read(FRAME_LEN - 1)
            if len(rest) == FRAME_LEN - 1 and rest[1] == 0x2A and rest[2] == 0x11:
                return bytes([0x06]) + rest
    return None

def extract_state(frame):
    """Extract all state flags from a frame"""
    return {
        'frame_valid': len(frame) == FRAME_LEN and frame[0:3] == b'\x06\x2a\x11',
        'byte3': f"0x{frame[3]:02X}",
        'byte4': f"0x{frame[4]:02X}",
        'byte5': f"0x{frame[5]:02X}",
        'byte6': f"0x{frame[6]:02X}",
        'byte7_tens': f"0x{frame[7]:02X}",
        'byte8_units': f"0x{frame[8]:02X}",
        'byte9_tenths': f"0x{frame[9]:02X}",
        'byte10': f"0x{frame[10]:02X}",
        'byte11': f"0x{frame[11]:02X}",
        'byte12': f"0x{frame[12]:02X}",
        'byte13': f"0x{frame[13]:02X}",
        'byte14': f"0x{frame[14]:02X}",
        'byte15': f"0x{frame[15]:02X}",
        'byte16': f"0x{frame[16]:02X}",
        'byte17': f"0x{frame[17]:02X}",
        'byte18': f"0x{frame[18]:02X}",
        'byte19': f"0x{frame[19]:02X}",
        'byte20': f"0x{frame[20]:02X}",
        'byte21': f"0x{frame[21]:02X}",
        'byte22': f"0x{frame[22]:02X}",
        'is_hold': bool(frame[5] & 0x04),
        'is_dbc': bool(frame[5] & 0x01),
        'speed': 'FAST' if frame[19] == 0x02 else 'SLOW',
        'mode': 'MIN' if frame[15] & 0x08 else ('MAX' if frame[16] & 0x08 else 'NORMAL'),
        'limit': 'UNDER' if frame[6] & 0x04 else 'NORMAL',
        'raw_frame': ' '.join(f"{b:02X}" for b in frame)
    }

def main():
    print("=" * 60)
    print("HT622B Data Collection Tool")
    print("=" * 60)
    print(f"\nConnect meter to {SERIAL_PORT}")
    print("Set meter to desired range and mode.")
    print("When ready, enter the target dB value and press ENTER.")
    print("The script will capture 3 seconds of frames.")
    print("Type 'quit' to exit.\n")

    fieldnames = ['timestamp', 'target_db', 'notes'] + list(extract_state(b'\x00' * 23).keys())

    with open(OUTPUT_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if f.tell() == 0:
            writer.writeheader()

        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
                print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud\n")

                while True:
                    target = input("Target dB (or 'quit'): ").strip()
                    if target.lower() == 'quit':
                        break

                    notes = input("Notes (mode/range/hold/etc): ").strip()

                    print(f"Capturing 3 seconds of data for {target} dB...")
                    frames_captured = 0
                    start_time = time.time()

                    while time.time() - start_time < 3:
                        frame = get_frame(ser)
                        if frame:
                            state = extract_state(frame)
                            state['timestamp'] = datetime.now().isoformat()
                            state['target_db'] = target
                            state['notes'] = notes
                            writer.writerow(state)
                            frames_captured += 1

                    print(f"Captured {frames_captured} frames. Saved to {OUTPUT_FILE}\n")

        except serial.SerialException as e:
            print(f"Serial error: {e}")
        except KeyboardInterrupt:
            print("\nStopped by user.")

    print(f"\nData saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
