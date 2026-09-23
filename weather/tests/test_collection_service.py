from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from django.test import TestCase

from weather.models import WeatherReading
from weather.services.collection import collect_weather_reading
from weather.services.exceptions import (
    OpenWeatherResponseError,
    OpenWeatherTimeoutError,
)
from weather.services.openweather import (
    CurrentWeather,
    GeocodedLocation,
    OpenWeatherClient,
)


class CollectWeatherReadingTests(TestCase):
    def setUp(self):
        self.client = Mock(spec=OpenWeatherClient)
        self.location = GeocodedLocation(
            name="Florianópolis",
            state="Santa Catarina",
            country_code="BR",
            latitude=Decimal("-27.596900"),
            longitude=Decimal("-48.549500"),
        )
        self.current_weather = CurrentWeather(
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
        self.client.geocode.return_value = self.location
        self.client.get_current_weather.return_value = self.current_weather

    def test_collects_and_persists_weather_reading(self):
        reading = collect_weather_reading(
            " Florianópolis ",
            "br",
            client=self.client,
        )

        self.assertEqual(WeatherReading.objects.count(), 1)
        self.assertEqual(reading.requested_city, "Florianópolis")
        self.assertEqual(reading.city, "Florianópolis")
        self.assertEqual(reading.state, "Santa Catarina")
        self.assertEqual(reading.country_code, "BR")
        self.assertEqual(reading.temperature, Decimal("22.80"))
        self.assertEqual(reading.observed_at, self.current_weather.observed_at)
        self.client.geocode.assert_called_once_with("Florianópolis", "BR")
        self.client.get_current_weather.assert_called_once_with(
            self.location.latitude,
            self.location.longitude,
        )

    def test_does_not_persist_when_provider_fails(self):
        self.client.get_current_weather.side_effect = OpenWeatherTimeoutError()

        with self.assertRaises(OpenWeatherTimeoutError):
            collect_weather_reading("Florianópolis", "BR", client=self.client)

        self.assertFalse(WeatherReading.objects.exists())

    def test_rounds_provider_coordinates_to_model_precision(self):
        self.client.geocode.return_value = replace(
            self.location,
            latitude=Decimal("-27.5973002"),
            longitude=Decimal("-48.5496098"),
        )

        reading = collect_weather_reading(
            "Florianópolis",
            "BR",
            client=self.client,
        )

        self.assertEqual(reading.latitude, Decimal("-27.597300"))
        self.assertEqual(reading.longitude, Decimal("-48.549610"))

    def test_rejects_provider_data_outside_model_limits(self):
        self.client.get_current_weather.return_value = replace(
            self.current_weather,
            description="x" * 256,
        )

        with self.assertRaises(OpenWeatherResponseError):
            collect_weather_reading("Florianópolis", "BR", client=self.client)

        self.assertFalse(WeatherReading.objects.exists())
