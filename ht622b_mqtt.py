#!/usr/bin/env python3
"""
HT622B Sound Level Meter - MQTT Publisher with Home Assistant Auto-Discovery
===========================================================================
Publishes decoded readings to MQTT with full Home Assistant device discovery.

Requirements:
    pip install paho-mqtt pyserial

Environment Variables:
    MQTT_HOST     - MQTT broker address (default: homeassistant.local)
    MQTT_PORT     - MQTT broker port (default: 1883)
    MQTT_USER     - MQTT username (default: mqtt)
    MQTT_PASS     - MQTT password (default: mqtt)
    MQTT_TOPIC    - Topic prefix (default: homeassistant/sensor/ht622b)
    HA_DISCOVERY  - Enable HA discovery (default: true)

Home Assistant will auto-create sensors when MQTT integration is enabled.
No manual YAML configuration needed.
"""

import os
import sys
import serial
import json
import time
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

# --- SERIAL CONFIGURATION ---
SERIAL_PORT = os.environ.get("SERIAL_PORT", "/dev/tty.usbserial-111230")
BAUD_RATE = 9600
FRAME_LEN = 23
# -----------------------------

# --- MQTT CONFIGURATION ---
MQTT_HOST = os.environ.get("MQTT_HOST", "homeassistant.local")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "")
MQTT_PASS = os.environ.get("MQTT_PASS", "")
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC", "homeassistant/sensor/ht622b")
HA_DISCOVERY = os.environ.get("HA_DISCOVERY", "true").lower() == "true"
# --------------------------

DEVICE_INFO = {
    "identifiers": ["ht622b"],
    "name": "Habotest HT622B",
    "model": "HT622B",
    "manufacturer": "Habotest",
    "sw_version": "1.0.0"
}

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
    """Decode a standard LCD digit split across two HT1621 PIN addresses."""
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


def get_range_setting(byte4, byte9):
    """Determine measurement range from raw LCD RAM bytes."""
    base_byte4 = byte4 & 0xFE
    range_id = (base_byte4, byte9 & 0xF0)
    ranges = {
        (0x04, 0x30): "30-130",
        (0x04, 0x00): "30-80",
        (0x0C, 0x00): "40-90",
        (0x0C, 0x30): "50-100",
        (0x00, 0x30): "70-120",
        (0x0E, 0x30): "60-110 / 80-130",
    }
    return ranges.get(range_id, f"UNKNOWN {range_id}")


def decode_frame(frame):
    """Decode a 23-byte HT622B frame into a dict."""
    if len(frame) != 23 or frame[0] != 0x06 or frame[1] != 0x2A or frame[2] != 0x11:
        return None

    pins = {}
    for i in range(16):
        byte_val = frame[4 + i]
        pins[5 + (i * 2)] = byte_val & 0x0F
        pins[6 + (i * 2)] = (byte_val >> 4) & 0x0F

    tens, p3   = decode_digit(pins[10], pins[11])
    units, p2  = decode_digit(pins[12], pins[13])
    tenths, p1 = decode_digit(pins[14], pins[15])

    value_str = f"{tens}{'.' if p2 else ''}{units}{'.' if p1 else ''}{tenths}"
    try:
        value_float = float(value_str)
    except ValueError:
        value_float = None

    is_hold    = bool(pins[7] & 0x04)
    weight_dba = bool(pins[5] & 0x01)
    weight_dbc = bool(pins[7] & 0x01)
    speed_fast = bool(pins[35] & 0x02)
    speed_slow = bool(pins[25] & 0x08)
    is_max     = bool(pins[29] & 0x08)
    is_min     = bool(pins[27] & 0x08)
    is_under   = bool(pins[9] & 0x04)
    is_over    = bool(pins[16] & 0x08)

    weight = "dBA" if weight_dba else ("dBC" if weight_dbc else "UNKNOWN")
    speed = "FAST" if speed_fast else ("SLOW" if speed_slow else "UNKNOWN")
    mode = "MAX" if is_max else ("MIN" if is_min else "NORMAL")
    limit = "UNDER" if is_under else ("OVER" if is_over else "NORMAL")

    # Range detection from raw LCD RAM bytes (not decoded nibbles)
    range_text = get_range_setting(frame[4], frame[9])

    return {
        "value": value_float,
        "value_str": value_str,
        "unit": weight,
        "speed": speed,
        "mode": mode,
        "limit": limit,
        "range": range_text,
        "hold": is_hold,
        "timestamp": datetime.now().isoformat(),
    }


def publish_discovery(client):
    """Publish Home Assistant MQTT discovery configs for all sensors."""

    sensors = [
        {
            "name": "HT622B Sound Level",
            "object_id": "ht622b_sound_level",
            "unique_id": "ht622b_sound_level",
            "state_topic": f"{MQTT_TOPIC_PREFIX}/state",
            "unit_of_measurement": "dBA",
            "device_class": "sound_pressure",
            "value_template": "{{ value_json.value }}",
            "icon": "mdi:volume-high",
        },
        {
            "name": "HT622B Mode",
            "object_id": "ht622b_mode",
            "unique_id": "ht622b_mode",
            "state_topic": f"{MQTT_TOPIC_PREFIX}/state",
            "value_template": "{{ value_json.mode }}",
            "icon": "mdi:toggle-switch",
        },
        {
            "name": "HT622B Speed",
            "object_id": "ht622b_speed",
            "unique_id": "ht622b_speed",
            "state_topic": f"{MQTT_TOPIC_PREFIX}/state",
            "value_template": "{{ value_json.speed }}",
            "icon": "mdi:speedometer",
        },
        {
            "name": "HT622B Limit",
            "object_id": "ht622b_limit",
            "unique_id": "ht622b_limit",
            "state_topic": f"{MQTT_TOPIC_PREFIX}/state",
            "value_template": "{{ value_json.limit }}",
            "icon": "mdi:alert-circle",
        },
        {
            "name": "HT622B Range",
            "object_id": "ht622b_range",
            "unique_id": "ht622b_range",
            "state_topic": f"{MQTT_TOPIC_PREFIX}/state",
            "value_template": "{{ value_json.range }}",
            "icon": "mdi:tune-vertical",
        },
        {
            "name": "HT622B Hold",
            "object_id": "ht622b_hold",
            "unique_id": "ht622b_hold",
            "state_topic": f"{MQTT_TOPIC_PREFIX}/state",
            "value_template": "{{ value_json.hold }}",
            "icon": "mdi:pause-circle",
            "payload_on": True,
            "payload_off": False,
        },
    ]

    for sensor in sensors:
        discovery_topic = f"homeassistant/sensor/{sensor['unique_id']}/config"
        payload = {**sensor, "device": DEVICE_INFO}
        client.publish(discovery_topic, json.dumps(payload), retain=True)
        print(f"Published HA discovery: {sensor['name']} -> {discovery_topic}")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"MQTT connected to {MQTT_HOST}:{MQTT_PORT}")
        if HA_DISCOVERY:
            publish_discovery(client)
    else:
        print(f"MQTT connection failed with code {rc}")


def on_disconnect(client, userdata, rc):
    print(f"MQTT disconnected (code {rc}), will retry...")


def main():
    print("=" * 60)
    print("HT622B MQTT Publisher")
    print("=" * 60)
    print(f"Serial: {SERIAL_PORT} @ {BAUD_RATE} baud")
    print(f"MQTT: {MQTT_HOST}:{MQTT_PORT}")
    print(f"Topic: {MQTT_TOPIC_PREFIX}/state")
    print(f"HA Discovery: {'enabled' if HA_DISCOVERY else 'disabled'}")
    print("=" * 60)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
    except Exception as e:
        print(f"Failed to connect to MQTT: {e}")
        sys.exit(1)

    client.loop_start()

    # Give MQTT time to connect and publish discovery
    time.sleep(2)

    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            print(f"\nReading from {SERIAL_PORT}...")
            print("Press Ctrl+C to stop.\n")
            while True:
                frame = ser.read(FRAME_LEN)
                if len(frame) == FRAME_LEN and frame[0:2] == b'\x06\x2A' and frame[3] == 0x01:
                    data = decode_frame(frame)
                    if data and data["value"] is not None:
                        payload = json.dumps(data)
                        client.publish(f"{MQTT_TOPIC_PREFIX}/state", payload)
                        print(f"{data['value_str']} {data['unit']} | {data['mode']} | {data['speed']} | {data['range']} | HOLD={'ON' if data['hold'] else 'OFF'}")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
