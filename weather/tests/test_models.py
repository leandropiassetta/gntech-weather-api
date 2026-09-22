from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from weather.models import WeatherReading


class WeatherReadingModelTests(TestCase):
    def setUp(self):
        self.observed_at = timezone.now()
        self.valid_data = {
            "requested_city": "Florianópolis",
            "city": "Florianópolis",
            "state": "Santa Catarina",
            "country_code": "BR",
            "provider_location_id": 3463237,
            "latitude": Decimal("-27.596900"),
            "longitude": Decimal("-48.549500"),
            "temperature": Decimal("22.80"),
            "feels_like": Decimal("23.10"),
            "humidity": 78,
            "pressure": 1015,
            "condition": "Clouds",
            "description": "nublado",
            "wind_speed": Decimal("4.20"),
            "observed_at": self.observed_at,
        }

    def test_creates_weather_reading(self):
        reading = WeatherReading.objects.create(**self.valid_data)

        self.assertIsNotNone(reading.id)
        self.assertIsNotNone(reading.created_at)
        self.assertEqual(reading.country_code, "BR")
        self.assertEqual(
            str(reading),
            f"Florianópolis, BR - {self.observed_at.isoformat()}",
        )

    def test_default_ordering_returns_latest_observation_first(self):
        older_data = {
            **self.valid_data,
            "observed_at": self.observed_at - timedelta(hours=1),
        }
        older = WeatherReading.objects.create(**older_data)
        newer = WeatherReading.objects.create(**self.valid_data)

        self.assertEqual(list(WeatherReading.objects.all()), [newer, older])

    def test_model_validation_rejects_invalid_values(self):
        invalid_fields = {
            "country_code": "Brazil",
            "latitude": Decimal("-91"),
            "longitude": Decimal("181"),
            "humidity": 101,
            "pressure": 0,
            "wind_speed": Decimal("-0.01"),
        }

        for field, value in invalid_fields.items():
            with self.subTest(field=field):
                reading = WeatherReading(**{**self.valid_data, field: value})

                with self.assertRaises(ValidationError) as error:
                    reading.full_clean()

                self.assertIn(field, error.exception.message_dict)

    def test_database_constraint_rejects_invalid_humidity(self):
        invalid_data = {**self.valid_data, "humidity": 101}

        with self.assertRaises(IntegrityError), transaction.atomic():
            WeatherReading.objects.create(**invalid_data)
