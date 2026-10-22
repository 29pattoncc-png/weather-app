import json
import unittest
from unittest.mock import MagicMock, patch

from app import (
    WeatherApiError,
    fetch_weather,
    fetch_zip_location,
    is_nws_url,
)


class ZipCodeTests(unittest.TestCase):
    def test_rejects_non_five_digit_zip_codes(self):
        for zip_code in ("", "1234", "123456", "12a45", " 10001"):
            with self.subTest(zip_code=zip_code), self.assertRaises(ValueError):
                fetch_zip_location(zip_code)

    def test_resolves_us_zip_and_excludes_non_us_results(self):
        payload = {
            "results": [
                {
                    "name": "New York",
                    "admin1": "New York",
                    "country_code": "US",
                    "latitude": 40.71427,
                    "longitude": -74.00597,
                },
                {
                    "name": "Other country",
                    "admin1": "Other region",
                    "country_code": "CA",
                    "latitude": 45.0,
                    "longitude": -73.0,
                },
            ]
        }
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()

        with patch("app.urlopen", return_value=response) as urlopen:
            place = fetch_zip_location("10001")

        self.assertEqual(place, {
            "latitude": 40.71427,
            "longitude": -74.00597,
            "city": "New York",
            "state": "New York",
            "zip": "10001",
        })
        request = urlopen.call_args.args[0]
        self.assertIn("countryCode=US", request.full_url)

    def test_returns_clear_error_for_unknown_zip(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"results":[]}'
        with patch("app.urlopen", return_value=response):
            with self.assertRaisesRegex(WeatherApiError, "ZIP code could not be found"):
                fetch_zip_location("00000")


class ForecastUrlTests(unittest.TestCase):
    def test_accepts_nws_https_endpoint(self):
        self.assertTrue(is_nws_url("https://api.weather.gov/gridpoints/TOP/31,80/forecast"))

    def test_rejects_non_nws_or_insecure_endpoint(self):
        for url in (
            "http://api.weather.gov/forecast",
            "https://example.com/forecast",
            "https://api.weather.gov.example.com/forecast",
            "https://user@api.weather.gov/forecast",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_nws_url(url))

    def test_weather_request_uses_zip_lookup_and_nws_data(self):
        place = {
            "latitude": 40.71427,
            "longitude": -74.00597,
            "city": "New York",
            "state": "New York",
            "zip": "10001",
        }
        point = {
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/OKX/33,37/forecast",
                "forecastHourly": "https://api.weather.gov/gridpoints/OKX/33,37/forecast/hourly",
            }
        }

        def fetch_nws(url):
            if "/points/" in url:
                return point
            if url.endswith("/hourly"):
                return {"properties": {"periods": [{"temperature": 72}]}}
            if "/alerts/" in url:
                return {"features": []}
            return {"properties": {"periods": [{"name": "Today"}]}}

        with (
            patch("app.fetch_zip_location", return_value=place) as zip_lookup,
            patch("app.fetch_nws_json", side_effect=fetch_nws),
        ):
            weather = fetch_weather("10001")

        zip_lookup.assert_called_once_with("10001")
        self.assertEqual(weather["provider"], "National Weather Service")
        self.assertEqual(weather["location"]["zip"], "10001")
        self.assertEqual(weather["forecast"][0]["name"], "Today")
        self.assertEqual(weather["hourly"][0]["temperature"], 72)
        self.assertEqual(weather["alerts"], [])


if __name__ == "__main__":
    unittest.main()
