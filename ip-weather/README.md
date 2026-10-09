# IP and Weather

Scrolls the current Boston temperature and the board's IP address on the LED
matrix, alternating between them. If the weather can't be fetched (no internet
yet), it shows `--F` and tries again a few seconds later — so seeing a real
temperature also confirms the board has a live web connection.

Intended as the board's startup app, so you can read its IP without a cable.
