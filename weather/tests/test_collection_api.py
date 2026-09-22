from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from weather.models import WeatherReading
from weather.services.exceptions import (
    OpenWeatherAuthenticationError,
    OpenWeatherConfigurationError,
    OpenWeatherLocationNotFoundError,
    OpenWeatherRateLimitError,
    OpenWeatherResponseError,
    OpenWeatherTimeoutError,
    OpenWeatherUnavailableError,
)
from weather.services.openweather import CurrentWeather, GeocodedLocation


class WeatherReadingCollectionApiTests(APITestCase):
    def setUp(self):
        self.url = reverse("weather:weather-reading-list")
        self.payload = {
            "city": "Florianópolis",
            "country_code": "br",
        }

    @patch("weather.services.collection.OpenWeatherClient")
    def test_collects_and_returns_weather_reading(self, client_class):
        provider_client = client_class.return_value
        provider_client.geocode.return_value = GeocodedLocation(
            name="Florianópolis",
            state="Santa Catarina",
            country_code="BR",
            latitude=Decimal("-27.596900"),
            longitude=Decimal("-48.549500"),
        )
        provider_client.get_current_weather.return_value = CurrentWeather(
            provider_location_id=3463237,
            temperature=Decimal("22.80"),
            feels_like=Decimal("23.10"),
            humidity=78,
            pressure=1015,
            condition="Clouds",
            description="nublado",
            wind_speed=Decimal("4.20"),
            observed_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        )

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WeatherReading.objects.count(), 1)
        self.assertEqual(response.data["requested_city"], "Florianópolis")
        self.assertEqual(response.data["country_code"], "BR")
        self.assertEqual(response.data["temperature"], "22.80")
        self.assertIn("id", response.data)
        self.assertIn("created_at", response.data)

    @patch("weather.services.collection.OpenWeatherClient")
    def test_rejects_invalid_request_data_before_calling_provider(
        self,
        client_class,
    ):
        invalid_payloads = [
            {},
            {"city": "", "country_code": "BR"},
            {"city": "Florianópolis", "country_code": "B"},
            {"city": "Florianópolis", "country_code": "12"},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        client_class.assert_not_called()
        self.assertFalse(WeatherReading.objects.exists())

    @patch("weather.views.collect_weather_reading")
    def test_maps_provider_errors_to_api_responses(self, collect):
        scenarios = [
            (
                OpenWeatherLocationNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "location_not_found",
            ),
            (
                OpenWeatherConfigurationError(),
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "weather_provider_not_configured",
            ),
            (
                OpenWeatherAuthenticationError(),
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "weather_provider_authentication_failed",
            ),
            (
                OpenWeatherTimeoutError(),
                status.HTTP_502_BAD_GATEWAY,
                "weather_provider_unavailable",
            ),
            (
                OpenWeatherUnavailableError(),
                status.HTTP_502_BAD_GATEWAY,
                "weather_provider_unavailable",
            ),
            (
                OpenWeatherResponseError(),
                status.HTTP_502_BAD_GATEWAY,
                "weather_provider_invalid_response",
            ),
        ]

        for exception, expected_status, expected_code in scenarios:
            with self.subTest(exception=exception):
                collect.side_effect = exception

                response = self.client.post(self.url, self.payload, format="json")

                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.data["code"], expected_code)

    @patch("weather.views.collect_weather_reading")
    def test_returns_retry_after_when_provider_is_rate_limited(self, collect):
        collect.side_effect = OpenWeatherRateLimitError(retry_after="60")

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "weather_provider_rate_limited")
        self.assertEqual(response["Retry-After"], "60")
