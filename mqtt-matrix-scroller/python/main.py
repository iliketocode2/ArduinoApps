import json
import threading
import time

import numpy as np
import paho.mqtt.client as mqtt

from arduino.app_utils import App, Bridge, Frame

BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883
TOPIC = "ME193/Rogers"

ROWS = 8
COLS = 13
BRIGHTNESS = 7
SCROLL_INTERVAL = 0.12  # seconds per column step

# 5x7 pixel font (7 rows tall, variable width), '#' = lit pixel.
FONT = {
    " ": ("...", "...", "...", "...", "...", "...", "..."),
    "A": ("..#..", ".#.#.", "#...#", "#...#", "#####", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"),
    "Y": ("#...#", ".#.#.", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": (".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    ".": (".", ".", ".", ".", ".", ".", "#"),
    ",": ("..", "..", "..", "..", "..", ".#", "#."),
    "!": ("#", "#", "#", "#", "#", ".", "#"),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "'": ("#", "#", ".", ".", ".", ".", "."),
    "-": ("....", "....", "....", "####", "....", "....", "...."),
    ":": (".", "#", ".", ".", "#", ".", "."),
}
DEFAULT_GLYPH = FONT[" "]


def _columns_for_char(ch):
    glyph = FONT.get(ch.upper(), DEFAULT_GLYPH)
    width = len(glyph[0])
    columns = []
    for x in range(width):
        column = [1 if row[x] == "#" else 0 for row in glyph]
        column += [0] * (ROWS - len(column))
        columns.append(column)
    return columns


def text_to_columns(text):
    columns = []
    for ch in text:
        columns.extend(_columns_for_char(ch))
        columns.append([0] * ROWS)
    return columns or [[0] * ROWS]


state_lock = threading.Lock()
state = {"columns": text_to_columns("WAITING FOR ME193..."), "offset": 0}


def set_message(text):
    columns = text_to_columns(text)
    with state_lock:
        state["columns"] = columns
        state["offset"] = 0


def render_frame():
    with state_lock:
        columns = state["columns"]
        offset = state["offset"]

    if len(columns) <= COLS:
        window = columns + [[0] * ROWS] * (COLS - len(columns))
    else:
        padded = [[0] * ROWS] * COLS + columns + [[0] * ROWS] * COLS
        span = len(padded) - COLS
        pos = offset % span
        window = padded[pos : pos + COLS]
        with state_lock:
            state["offset"] = offset + 1

    frame_array = np.array(window, dtype=np.uint8).T * BRIGHTNESS
    frame = Frame(frame_array)
    Bridge.call("draw", frame.to_board_bytes())


def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="replace").strip()
    if not payload:
        return
    try:
        data = json.loads(payload)
    except ValueError:
        data = None
    if isinstance(data, dict) and "text" in data:
        text = f"{data.get('sender', '?')}: {data['text']}"
    else:
        text = payload
    print(f"[ME193] {text}")
    set_message(text)


mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_message = on_message
mqtt_client.connect(BROKER_HOST, BROKER_PORT)
mqtt_client.subscribe(TOPIC, qos=0)
mqtt_client.loop_start()


def loop():
    render_frame()
    time.sleep(SCROLL_INTERVAL)


App.run(user_loop=loop)
