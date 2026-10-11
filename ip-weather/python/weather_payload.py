"""The weather this board publishes, as plain data (no board imports, so it
can be tested on a PC).

The ping-pong game (ME193 Project 5, weather.py) reads it from MQTT and
draws the arena to match. build_payload() must stay identical to the game's
weather.normalize() -- the game's test_weather.py checks both against the
same Open-Meteo reading.
"""

import time

PLACE = "Tufts"
LAT, LON = 42.4075, -71.1190          # Tufts University, Medford MA
TOPIC = "ME193/WilliamGoldman/weather"
URL = ("https://api.open-meteo.com/v1/forecast"
       f"?latitude={LAT}&longitude={LON}"
       "&current=temperature_2m,apparent_temperature,relative_humidity_2m,is_day,precipitation,rain,showers,"
       "snowfall,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility"
       "&daily=sunrise,sunset&temperature_unit=fahrenheit&wind_speed_unit=mph"
       "&timezone=America%2FNew_York&forecast_days=1")

# WMO weather code -> a short word for the LED matrix
LABELS = {0: "CLEAR", 1: "CLEAR", 2: "CLOUD", 3: "CLOUD", 45: "FOG", 48: "FOG",
          51: "RAIN", 53: "RAIN", 55: "RAIN", 56: "ICE", 57: "ICE", 61: "RAIN", 63: "RAIN", 65: "RAIN",
          66: "ICE", 67: "ICE", 71: "SNOW", 73: "SNOW", 75: "SNOW", 77: "SNOW", 80: "RAIN", 81: "RAIN",
          82: "RAIN", 85: "SNOW", 86: "SNOW", 95: "STORM", 96: "STORM", 99: "STORM"}


def build_payload(om, src="unoq", sent=None):
    """Open-Meteo forecast JSON -> payload (schema v1)."""
    c, d = om["current"], om.get("daily") or {}
    first = lambda key: (d.get(key) or [None])[0]   # noqa: E731
    return {
        "v": 1, "src": src, "place": PLACE, "lat": LAT, "lon": LON,
        "obs": c["time"], "utc_offset_s": int(om.get("utc_offset_seconds", 0)),
        "sent": int(time.time() if sent is None else sent),
        "temp_f": round(float(c["temperature_2m"]), 1), "feels_f": round(float(c["apparent_temperature"]), 1),
        "rh": int(c.get("relative_humidity_2m", 50)), "code": int(c["weather_code"]),
        "precip_mm": round(float(c.get("precipitation", 0)), 2), "rain_mm": round(float(c.get("rain", 0)), 2),
        "showers_mm": round(float(c.get("showers", 0)), 2), "snow_cm": round(float(c.get("snowfall", 0)), 2),
        "cloud": int(c.get("cloud_cover", 0)), "wind_mph": round(float(c.get("wind_speed_10m", 0)), 1),
        "gust_mph": round(float(c.get("wind_gusts_10m", 0)), 1), "wind_dir": int(c.get("wind_direction_10m", 0)),
        "is_day": int(c.get("is_day", 1)), "vis_m": int(c.get("visibility", 20000)),
        "sunrise": first("sunrise"), "sunset": first("sunset"),
    }


def short_label(p):
    """'48F CLOUD' for the matrix, or '--F' without a reading."""
    if not p:
        return "--F"
    return f"{round(p['temp_f'])}F {LABELS.get(p['code'], '')}".strip()
