# SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
#
# SPDX-License-Identifier: MPL-2.0

from arduino.app_utils import App, Bridge, Frame
from arduino.app_bricks.web_ui import WebUI
import numpy as np

ROWS = 8
COLS = 13
BRIGHTNESS = 7  # max value for the matrix's 3-bit grayscale

pos = [ROWS // 2, COLS // 2]

ui = WebUI()


def render():
    frame_array = np.zeros((ROWS, COLS), dtype=np.uint8)
    frame_array[pos[0], pos[1]] = BRIGHTNESS
    frame = Frame(frame_array)
    Bridge.call("draw", frame.to_board_bytes())
    ui.send_message("position", {"row": pos[0], "col": pos[1]})


def move(sid, data):
    direction = data.get("dir")
    if direction == "up":
        pos[0] = max(0, pos[0] - 1)
    elif direction == "down":
        pos[0] = min(ROWS - 1, pos[0] + 1)
    elif direction == "left":
        pos[1] = max(0, pos[1] - 1)
    elif direction == "right":
        pos[1] = min(COLS - 1, pos[1] + 1)
    render()


ui.on_message("move", move)
ui.on_connect(lambda sid: render())

render()

App.run()
