#!/usr/bin/env python3
"""
HT622B Sound Level Meter - MQTT Publisher
==========================================
Publishes decoded readings to MQTT for Home Assistant integration.

Requirements:
    pip install paho-mqtt

Configuration:
    Edit the MQTT_* variables below or set environment variables.
"""

import os
import serial
import json
import time
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt not installed. Run: pip install paho-mqtt")
    raise

# --- SERIAL CONFIGURATION ---
SERIAL_PORT = "/dev/tty.usbserial-111230"
BAUD_RATE = 9600
FRAME_LEN = 23
# -----------------------------

# --- MQTT CONFIGURATION ---
MQTT_HOST = os.environ.get("MQTT_HOST", "homeassistant.local")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "mqtt")
MQTT_PASS = os.environ.get("MQTT_PASS", "mqtt")
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC", "homeassistant/sensor/ht622b")
# --------------------------

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

    # Build decimal string
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

    return {
        "value": value_float,
        "value_str": value_str,
        "unit": weight,
        "speed": speed,
        "mode": mode,
        "limit": limit,
        "hold": is_hold,
        "timestamp": datetime.now().isoformat(),
    }


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"MQTT connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"MQTT connection failed with code {rc}")


def on_disconnect(client, userdata, rc):
    print(f"MQTT disconnected (code {rc}), will retry...")


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    # Publish Home Assistant discovery config
    discovery_topic = f"{MQTT_TOPIC_PREFIX}/config"
    discovery_payload = {
        "name": "HT622B Sound Level",
        "state_topic": f"{MQTT_TOPIC_PREFIX}/state",
        "unit_of_measurement": "dBA",
        "device_class": "sound_pressure",
        "value_template": "{{ value_json.value }}",
        "json_attributes_topic": f"{MQTT_TOPIC_PREFIX}/state",
        "unique_id": "ht622b_sound_level",
        "device": {
            "identifiers": ["ht622b"],
            "name": "Habotest HT622B",
            "model": "HT622B",
            "manufacturer": "Habotest"
        }
    }
    client.publish(discovery_topic, json.dumps(discovery_payload), retain=True)
    print(f"Published HA discovery to {discovery_topic}")

    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            print(f"Reading from {SERIAL_PORT} at {BAUD_RATE} baud...")
            while True:
                frame = ser.read(FRAME_LEN)
                if len(frame) == FRAME_LEN and frame[0:2] == b'\x06\x2A' and frame[3] == 0x01:
                    data = decode_frame(frame)
                    if data and data["value"] is not None:
                        payload = json.dumps(data)
                        client.publish(f"{MQTT_TOPIC_PREFIX}/state", payload)
                        print(f"Published: {data['value_str']} {data['unit']} ({data['mode']}, {data['speed']})")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
