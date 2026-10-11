# IP and Weather

Scrolls the current Tufts weather (temperature and a word, e.g. `48F CLOUD`)
and the board's IP address on the LED matrix, alternating between them. If the
weather can't be fetched (no internet yet), it shows `--F` and tries again a few
seconds later -- so seeing a real reading also confirms the board has a live web
connection.

It also **publishes the full current weather over MQTT** for the ME193 Project 5
ping-pong game, which draws its arena to match (rain, snow, night, wind...):

- Broker: `test.mosquitto.org:1883`
- Topic: `ME193/WilliamGoldman/weather` -- JSON, **retained** (QoS 1), so a
  subscriber gets the latest reading immediately
- Refreshed from Open-Meteo every 5 minutes; re-published every 60 s as a heartbeat
- `ME193/WilliamGoldman/weather/status`: `online` / `offline` (MQTT last will)

Payload (schema v1, built by `python/weather_payload.py`):
`{v, src, place, lat, lon, obs, utc_offset_s, sent, temp_f, feels_f, rh, code
(WMO), precip_mm, rain_mm, showers_mm, snow_cm, cloud, wind_mph, gust_mph,
wind_dir, is_day, vis_m, sunrise, sunset}`

Intended as the board's startup app, so you can read its IP without a cable.
