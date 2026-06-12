# Habotest HT622B Sound Level Meter - Serial Protocol Decoder

A complete Python decoder and MQTT publisher for the **Habotest HT622B Digital Sound Level Meter**, including Home Assistant integration.

---

## 🔍 The Protocol

The HT622B streams data over USB-serial (9600 baud, 8N1) as **23-byte frames** containing raw LCD display RAM. The manufacturer protocol document (`HT622B上位机通讯协议-V0.0`) confirms:

| Bytes | Field | Value |
|-------|-------|-------|
| 0-1 | Header | `0x06 0x2A` |
| 2 | Length | `0x11` (17 data bytes) |
| 3 | Type | `0x01` (real-time) |
| 4-19 | D15-D0 | 16 bytes of **HT1621 LCD RAM** |
| 20-22 | Footer | `0x0D 0x0A 0x00` |

### The LCD RAM Trick

The 16 data bytes are **packed HT1621 display RAM** — not encoded digit values. Each byte contains two 4-bit PIN states (high/low nibbles). The digits are split across byte boundaries:

| Digit | PINs | Source Bytes |
|-------|------|--------------|
| **Tens** (P3) | PIN 10 + PIN 11 | Byte 6 (high) + Byte 7 (low) |
| **Units** (P2) | PIN 12 + PIN 13 | Byte 7 (high) + Byte 8 (low) |
| **Tenths** (P1) | PIN 14 + PIN 15 | Byte 8 (high) + Byte 9 (low) |

Each PIN is a 4-bit nibble representing **COM line states** (COM3, COM2, COM1, COM0). The segment mapping follows standard 7-segment:

```
    a (COM3)
  f(COM2) b(COM2)
    g(COM1)
  e(COM1) c(COM1)
    d(COM0)  + dp(COM0)
```

This is why naive byte-level decoding fails — the same byte value (`0xE6`, `0x3F`, etc.) contains **fragments of multiple digits** depending on which nibble you read.

---

## 🚀 Quick Start

### 1. Standalone Decoder

```bash
pip install pyserial
python ht622b_decoder.py
```

Connect the HT622B via USB and edit `SERIAL_PORT` in the script if needed.

### 2. MQTT Publisher (for Home Assistant)

```bash
pip install pyserial paho-mqtt
export MQTT_HOST=homeassistant.local
export MQTT_USER=mqtt
export MQTT_PASS=your_password
python ht622b_mqtt.py
```

The script auto-publishes Home Assistant discovery config so the sensor appears automatically.

### 3. Home Assistant Configuration

See [`homeassistant_config.yaml`](homeassistant_config.yaml) for:
- Manual MQTT sensor setup
- Automatic discovery (handled by script)
- Lovelace dashboard card example

---

## 📊 Decoded Output

```
========================================
Raw: 06 2A 11 01 05 0E C0 E6 BF 3F 00 0F 00 00 00 08 00 00 00 02 0D 0A 00
Modes: HOLD=OFF | SPEED=SLOW | WEIGHT=dBA | MODE=NORMAL | LIMIT=NORMAL
Value: 48.0 dBA
========================================
```

### Status Flags Extracted

| Flag | PIN/COM | Description |
|------|---------|-------------|
| HOLD | PIN 7, COM2 | Hold mode active |
| dBA | PIN 5, COM0 | A-weighting filter |
| dBC | PIN 7, COM0 | C-weighting filter |
| FAST | PIN 35, COM1 | Fast response (125ms) |
| SLOW | PIN 25, COM3 | Slow response (1s) |
| MAX | PIN 29, COM3 | Max hold mode |
| MIN | PIN 27, COM3 | Min hold mode |
| UNDER | PIN 9, COM2 | Under-range alarm |
| OVER | PIN 16, COM3 | Over-range alarm |

---

## 🛠️ Files

| File | Purpose |
|------|---------|
| `ht622b_decoder.py` | Standalone real-time decoder |
| `ht622b_mqtt.py` | MQTT publisher with HA discovery |
| `homeassistant_config.yaml` | HA sensor/card configuration |
| `HT622B上位机通讯协议-V0.0.docx` | Official manufacturer protocol |


---

## License

MIT
