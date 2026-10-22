import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))
USER_AGENT = "WeatherClassroomApp/1.0 (student weather project)"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRIENDLY_API_ERROR = "Weather information is currently unavailable. Please try again."
INVALID_ZIP_MESSAGE = "Enter a valid 5-digit U.S. ZIP code."


class WeatherApiError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def parse_coordinates(latitude, longitude):
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        raise ValueError("The ZIP code lookup returned invalid coordinates.")

    if not math.isfinite(lat) or not math.isfinite(lon):
        raise ValueError("The ZIP code lookup returned invalid coordinates.")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("The ZIP code lookup returned invalid coordinates.")
    return lat, lon


def is_nws_url(url):
    try:
        parts = urlsplit(url)
        return (
            parts.scheme == "https"
            and parts.hostname == "api.weather.gov"
            and parts.username is None
            and parts.password is None
            and parts.port in (None, 443)
        )
    except ValueError:
        return False


def fetch_json(url):
    request = Request(
        url,
        headers={
            "Accept": "application/geo+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise WeatherApiError(
            "The weather service returned an error.",
            status_code=error.code,
        ) from error
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeatherApiError(FRIENDLY_API_ERROR) from error


def fetch_nws_json(url):
    if not is_nws_url(url):
        raise WeatherApiError("The weather service returned an invalid forecast link.")
    return fetch_json(url)


def fetch_zip_location(zip_code):
    if not isinstance(zip_code, str) or not re.fullmatch(r"\d{5}", zip_code):
        raise ValueError(INVALID_ZIP_MESSAGE)

    query = urlencode(
        {
            "name": zip_code,
            "count": 1,
            "language": "en",
            "format": "json",
            "countryCode": "US",
        }
    )
    request = Request(
        f"https://geocoding-api.open-meteo.com/v1/search?{query}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise WeatherApiError(
            "ZIP code lookup is currently unavailable. Please try again.",
            status_code=error.code,
        ) from error
    except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeatherApiError(
            "ZIP code lookup is currently unavailable. Please try again."
        ) from error

    places = [
        place for place in data.get("results", [])
        if place.get("country_code") == "US"
    ]
    if not places:
        raise WeatherApiError(
            "That ZIP code could not be found. Check it and try again.",
            status_code=404,
        )

    place = places[0]
    latitude, longitude = parse_coordinates(
        place.get("latitude"),
        place.get("longitude"),
    )
    return {
        "latitude": latitude,
        "longitude": longitude,
        "city": place.get("name") or "Unknown city",
        "state": place.get("admin1") or "",
        "zip": zip_code,
    }


def _fetch_optional(url):
    try:
        return fetch_nws_json(url), None
    except WeatherApiError:
        return None, FRIENDLY_API_ERROR


def fetch_weather(zip_code):
    place = fetch_zip_location(zip_code)
    latitude = place["latitude"]
    longitude = place["longitude"]
    point_url = f"https://api.weather.gov/points/{latitude:.4f},{longitude:.4f}"
    point_data = fetch_nws_json(point_url)
    point_properties = point_data.get("properties", {})
    forecast_url = point_properties.get("forecast")
    hourly_url = point_properties.get("forecastHourly")
    if not forecast_url or not is_nws_url(forecast_url):
        raise WeatherApiError("The weather service did not provide a valid forecast link.")

    forecast = fetch_nws_json(forecast_url)
    with ThreadPoolExecutor(max_workers=2) as executor:
        hourly_future = executor.submit(_fetch_optional, hourly_url) if hourly_url else None
        alerts_url = (
            "https://api.weather.gov/alerts/active?"
            + urlencode({"point": f"{latitude:.4f},{longitude:.4f}"})
        )
        alerts_future = executor.submit(_fetch_optional, alerts_url)
        hourly, hourly_error = (
            hourly_future.result() if hourly_future else (None, FRIENDLY_API_ERROR)
        )
        alerts, alerts_error = alerts_future.result()

    return {
        "latitude": latitude,
        "longitude": longitude,
        "provider": "National Weather Service",
        "location": place,
        "forecastUrl": forecast_url,
        "forecast": forecast.get("properties", {}).get("periods", []),
        "hourly": (hourly or {}).get("properties", {}).get("periods", []),
        "alerts": (alerts or {}).get("features", []),
        "hourlyError": hourly_error,
        "alertsError": alerts_error,
    }


class WeatherHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == "/api/weather":
            self._serve_weather(parse_qs(path.query))
        else:
            self._serve_static(path.path)

    def _serve_weather(self, query):
        zip_code = query.get("zip", [""])[0].strip()
        if not isinstance(zip_code, str) or not re.fullmatch(r"\d{5}", zip_code):
            self._send_json(400, {"error": INVALID_ZIP_MESSAGE})
            return
        try:
            self._send_json(200, fetch_weather(zip_code))
        except WeatherApiError as error:
            if error.status_code == 404:
                message = str(error)
                if message == "The weather service returned an error.":
                    message = "The National Weather Service does not have a forecast for that ZIP code."
                self._send_json(
                    404,
                    {"error": message},
                )
            else:
                self._send_json(502, {"error": str(error) or FRIENDLY_API_ERROR})

    def _serve_static(self, path):
        requested = "index.html" if path == "/" else path.lstrip("/")
        if requested not in {"index.html", "styles.css", "app.js"}:
            self.send_error(404)
            return

        file_path = os.path.join(BASE_DIR, requested)
        content_type = {
            "index.html": "text/html; charset=utf-8",
            "styles.css": "text/css; charset=utf-8",
            "app.js": "text/javascript; charset=utf-8",
        }[requested]
        try:
            with open(file_path, "rb") as file:
                body = file.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string, *args):
        super().log_message(format_string, *args)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), WeatherHandler)
    print(f"Weather app is running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping weather app...")
    finally:
        server.server_close()
