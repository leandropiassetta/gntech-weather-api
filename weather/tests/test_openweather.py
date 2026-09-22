from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import requests
from django.test import SimpleTestCase, override_settings

from weather.services.exceptions import (
    OpenWeatherAuthenticationError,
    OpenWeatherConfigurationError,
    OpenWeatherLocationNotFoundError,
    OpenWeatherRateLimitError,
    OpenWeatherResponseError,
    OpenWeatherTimeoutError,
    OpenWeatherUnavailableError,
)
from weather.services.openweather import OpenWeatherClient


def make_response(payload, status_code=200, headers=None):
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = payload
    return response


class OpenWeatherClientTests(SimpleTestCase):
    def setUp(self):
        self.session = Mock(spec=requests.Session)
        self.client = OpenWeatherClient(
            api_key="test-api-key",
            session=self.session,
            timeout=4.0,
        )

    @override_settings(OPENWEATHER_API_KEY="")
    def test_requires_an_api_key(self):
        with self.assertRaises(OpenWeatherConfigurationError):
            OpenWeatherClient(session=self.session)

    def test_geocodes_city_and_country(self):
        self.session.get.return_value = make_response(
            [
                {
                    "name": "Florianópolis",
                    "state": "Santa Catarina",
                    "country": "BR",
                    "lat": -27.5969,
                    "lon": -48.5495,
                }
            ]
        )

        location = self.client.geocode(" Florianópolis ", "br")

        self.assertEqual(location.name, "Florianópolis")
        self.assertEqual(location.state, "Santa Catarina")
        self.assertEqual(location.country_code, "BR")
        self.assertEqual(location.latitude, Decimal("-27.5969"))
        self.assertEqual(location.longitude, Decimal("-48.5495"))
        self.session.get.assert_called_once_with(
            self.client.GEOCODING_URL,
            params={
                "q": "Florianópolis,BR",
                "limit": 1,
                "appid": "test-api-key",
            },
            timeout=4.0,
        )

    def test_raises_when_location_is_not_found(self):
        self.session.get.return_value = make_response([])

        with self.assertRaises(OpenWeatherLocationNotFoundError):
            self.client.geocode("Invalid City", "BR")

    def test_gets_current_weather_in_metric_units(self):
        observed_at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
        self.session.get.return_value = make_response(
            {
                "id": 3463237,
                "main": {
                    "temp": 22.8,
                    "feels_like": 23.1,
                    "humidity": 78,
                    "pressure": 1015,
                },
                "weather": [
                    {
                        "main": "Clouds",
                        "description": "nublado",
                    }
                ],
                "wind": {"speed": 4.2},
                "dt": int(observed_at.timestamp()),
            }
        )

        weather = self.client.get_current_weather(
            Decimal("-27.596900"),
            Decimal("-48.549500"),
        )

        self.assertEqual(weather.provider_location_id, 3463237)
        self.assertEqual(weather.temperature, Decimal("22.8"))
        self.assertEqual(weather.feels_like, Decimal("23.1"))
        self.assertEqual(weather.humidity, 78)
        self.assertEqual(weather.pressure, 1015)
        self.assertEqual(weather.condition, "Clouds")
        self.assertEqual(weather.description, "nublado")
        self.assertEqual(weather.wind_speed, Decimal("4.2"))
        self.assertEqual(weather.observed_at, observed_at)
        self.session.get.assert_called_once_with(
            self.client.CURRENT_WEATHER_URL,
            params={
                "lat": "-27.596900",
                "lon": "-48.549500",
                "appid": "test-api-key",
                "units": "metric",
                "lang": "pt_br",
            },
            timeout=4.0,
        )

    def test_maps_provider_http_errors(self):
        scenarios = [
            (401, OpenWeatherAuthenticationError),
            (403, OpenWeatherAuthenticationError),
            (404, OpenWeatherResponseError),
            (500, OpenWeatherUnavailableError),
        ]

        for status_code, exception_class in scenarios:
            with self.subTest(status_code=status_code):
                self.session.get.return_value = make_response(
                    {},
                    status_code=status_code,
                )

                with self.assertRaises(exception_class):
                    self.client.geocode("Florianópolis", "BR")

    def test_preserves_retry_after_on_rate_limit(self):
        self.session.get.return_value = make_response(
            {},
            status_code=429,
            headers={"Retry-After": "60"},
        )

        with self.assertRaises(OpenWeatherRateLimitError) as error:
            self.client.geocode("Florianópolis", "BR")

        self.assertEqual(error.exception.retry_after, "60")

    def test_maps_network_failures(self):
        scenarios = [
            (requests.Timeout(), OpenWeatherTimeoutError),
            (requests.ConnectionError(), OpenWeatherUnavailableError),
        ]

        for request_error, exception_class in scenarios:
            with self.subTest(exception_class=exception_class):
                self.session.get.side_effect = request_error

                with self.assertRaises(exception_class):
                    self.client.geocode("Florianópolis", "BR")

    def test_rejects_non_json_response(self):
        response = make_response({})
        response.json.side_effect = ValueError
        self.session.get.return_value = response

        with self.assertRaises(OpenWeatherResponseError):
            self.client.geocode("Florianópolis", "BR")

    def test_rejects_malformed_weather_response(self):
        self.session.get.return_value = make_response(
            {
                "main": {},
                "weather": [],
                "wind": {},
                "dt": "invalid",
            }
        )

        with self.assertRaises(OpenWeatherResponseError):
            self.client.get_current_weather(
                Decimal("-27.596900"),
                Decimal("-48.549500"),
            )
