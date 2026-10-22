# Weather Desk

A simple U.S. weather dashboard. Enter a 5-digit ZIP code to see the National Weather Service forecast, hourly weather, and active alerts for that area.

## Run it

Requires Python 3.9 or newer; no packages need to be installed.

1. Open a terminal in this folder.
2. Run `python app.py` (on Windows, `py app.py` also works).
3. Open <http://127.0.0.1:8000>.
4. Enter a U.S. ZIP code, such as `10001`.

Saved ZIP codes stay in this browser using local storage. Older saved locations that are not ZIP codes will no longer appear.

## How the API requests work

1. Enter a 5-digit U.S. ZIP code.
2. The server looks up the ZIP code's coordinates using Open-Meteo's geocoding service, restricted to the United States.
3. The server sends those coordinates to the NWS `/points` endpoint to find the local forecast URLs.
4. The server retrieves the NWS forecast, hourly forecast, and active alerts.
5. The app displays temperatures in the NWS units, conditions, wind, and any active alerts.

The app only accepts five-digit U.S. ZIP codes. It does not provide worldwide forecasts or coordinate-based searching. NWS requests include the required descriptive `User-Agent` header in `app.py`. No API key is required.

If the ZIP lookup or forecast request fails, the page displays an error instead of crashing. Hourly forecast or alert failures do not prevent the regular forecast from displaying.

## Tests

Run the built-in tests with `python -m unittest`.
