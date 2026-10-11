import json
import os
import threading
import time

import numpy as np
import paho.mqtt.client as mqtt
import requests
from arduino.app_utils import App, Bridge, Frame

from weather_payload import TOPIC, URL, build_payload, short_label

BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883
REFRESH_SECONDS = 300  # re-fetch weather every 5 minutes (Open-Meteo updates "current" every 15)
RETRY_SECONDS = 15  # retry sooner if the last fetch failed (e.g. WiFi not up yet)
HEARTBEAT_SECONDS = 60  # re-publish the latest reading so listeners know the board is alive
SCROLL_DELAY = 0.12  # seconds between animation steps
MATRIX_ROWS = 8
MATRIX_COLS = 13
BRIGHTNESS = 7  # 0-7 (sketch uses 3 grayscale bits)

# 3-column-wide, 5-row-tall bitmap font
FONT = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "001", "001", "001"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "-": ["000", "000", "111", "000", "000"],
    "F": ["111", "100", "111", "100", "100"],
    ".": ["000", "000", "000", "000", "010"],
    " ": ["000", "000", "000", "000", "000"],
    # letters for the weather word (CLEAR, CLOUD, FOG, RAIN, ICE, SNOW, STORM)
    "A": ["010", "101", "111", "101", "101"],
    "C": ["111", "100", "100", "100", "111"],
    "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "111", "100", "111"],
    "G": ["111", "100", "101", "101", "111"],
    "I": ["111", "010", "010", "010", "111"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101"],
    "N": ["110", "101", "101", "101", "101"],
    "O": ["111", "101", "101", "101", "111"],
    "R": ["110", "101", "110", "101", "101"],
    "S": ["111", "100", "111", "001", "111"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"],
    "W": ["101", "101", "111", "111", "101"],
}


def build_bitmap(text: str) -> np.ndarray:
    rows = ["" for _ in range(5)]
    for ch in text:
        pattern = FONT.get(ch, FONT[" "])
        for i in range(5):
            rows[i] += pattern[i] + "0"  # 1-column gap after each character

    width = len(rows[0])
    bitmap = np.zeros((MATRIX_ROWS, width), dtype=np.uint8)
    for i, row in enumerate(rows):
        for x, bit in enumerate(row):
            if bit == "1":
                bitmap[1 + i, x] = BRIGHTNESS  # vertically centered in the 8 rows
    return bitmap


def fetch_weather():
    """The weather payload (see weather_payload.py), or None if the web
    request fails (no internet, API down)."""
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()
        return build_payload(response.json())
    except (requests.RequestException, KeyError, ValueError, TypeError) as e:
        print(f"Weather fetch failed: {e}")
        return None


def get_ip_address() -> str:
    # the app runs in its own network namespace (container eth0), so the
    # board's real LAN address is only available via the host-injected env var
    return os.environ.get("HOST_IP", "0.0.0.0")


class Marquee:
    def __init__(self, text: str):
        bitmap = build_bitmap(text)
        # trailing blank columns so the message fully scrolls off before looping
        self.width = bitmap.shape[1] + MATRIX_COLS
        self.padded = np.zeros((MATRIX_ROWS, self.width), dtype=np.uint8)
        self.padded[:, : bitmap.shape[1]] = bitmap
        self.offset = 0

    def next_frame(self) -> np.ndarray:
        idx = (np.arange(MATRIX_COLS) + self.offset) % self.width
        self.offset = (self.offset + 1) % self.width
        return self.padded[:, idx]


# ------------------------------------------------------------------- MQTT
# Retained: a game that subscribes later gets the latest reading at once.
# connect_async + loop_start: a broker that's down at boot doesn't crash the
# app; paho keeps reconnecting in the background.
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"MQTT connected ({reason_code}); publishing weather to {TOPIC}")
    client.publish(TOPIC + "/status", "online", qos=1, retain=True)


mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.will_set(TOPIC + "/status", "offline", qos=1, retain=True)
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=60)
mqtt_client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=30)
mqtt_client.loop_start()


# ---------------------------------------------------------------- weather
# Fetching runs on its own thread so a slow request never stalls the scroll.
state_lock = threading.Lock()
latest = None  # newest weather payload


def publish(payload):
    msg = json.dumps(dict(payload, sent=int(time.time())), separators=(",", ":"))
    mqtt_client.publish(TOPIC, msg, qos=1, retain=True)


def weather_loop():
    global latest
    next_fetch = 0.0
    last_publish = 0.0
    while True:
        now = time.monotonic()
        if now >= next_fetch:
            payload = fetch_weather()
            if payload is not None:
                with state_lock:
                    latest = payload
                print(f"Tufts weather: {short_label(payload)}, board IP: {get_ip_address()}")
                publish(payload)
                last_publish = now
            next_fetch = now + (REFRESH_SECONDS if payload is not None else RETRY_SECONDS)
        with state_lock:
            payload = latest
        if payload is not None and now - last_publish >= HEARTBEAT_SECONDS:
            publish(payload)
            last_publish = now
        time.sleep(1)


threading.Thread(target=weather_loop, name="weather", daemon=True).start()


# ---------------------------------------------------------------- display
temp_marquee = None
temp_text = None
ip_marquee = None
showing_temp = True


def update_display():
    global temp_marquee, temp_text, ip_marquee, showing_temp

    with state_lock:
        text = short_label(latest)
    if text != temp_text:
        temp_text, temp_marquee = text, Marquee(text)
        ip_marquee = Marquee(get_ip_address())

    marquee = temp_marquee if showing_temp else ip_marquee
    frame_bytes = Frame(marquee.next_frame()).to_board_bytes()
    if marquee.offset == 0:  # finished a full scroll pass
        showing_temp = not showing_temp
    Bridge.call("draw", frame_bytes)
    time.sleep(SCROLL_DELAY)


App.run(user_loop=update_display)
