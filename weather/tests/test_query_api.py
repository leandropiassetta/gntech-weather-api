from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from weather.models import WeatherReading


def create_reading(
    city="Florianópolis",
    country_code="BR",
    observed_at=None,
):
    return WeatherReading.objects.create(
        requested_city=city,
        city=city,
        state="Santa Catarina" if country_code == "BR" else "",
        country_code=country_code,
        provider_location_id=3463237,
        latitude=Decimal("-27.596900"),
        longitude=Decimal("-48.549500"),
        temperature=Decimal("22.80"),
        feels_like=Decimal("23.10"),
        humidity=78,
        pressure=1015,
        condition="Clouds",
        description="nublado",
        wind_speed=Decimal("4.20"),
        observed_at=observed_at or timezone.now(),
    )


class WeatherReadingQueryApiTests(APITestCase):
    def setUp(self):
        self.list_url = reverse("weather:weather-reading-list")

    def test_lists_readings_in_paginated_latest_first_order(self):
        now = timezone.now()
        older = create_reading(observed_at=now - timedelta(hours=1))
        newer = create_reading(city="São Paulo", observed_at=now)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertIsNone(response.data["next"])
        self.assertIsNone(response.data["previous"])
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [newer.id, older.id],
        )

    def test_filters_readings_by_city_and_country(self):
        expected = create_reading()
        create_reading(city="São Paulo")
        create_reading(city="Porto", country_code="PT")

        response = self.client.get(
            self.list_url,
            {"city": "florianópolis", "country_code": "br"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], expected.id)

    def test_rejects_invalid_country_filter(self):
        response = self.client.get(
            self.list_url,
            {"country_code": "123"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("country_code", response.data)

    def test_paginates_twenty_readings_per_page(self):
        observed_at = timezone.now()
        for index in range(21):
            create_reading(
                observed_at=observed_at - timedelta(minutes=index),
            )

        first_page = self.client.get(self.list_url)
        second_page = self.client.get(self.list_url, {"page": 2})

        self.assertEqual(first_page.data["count"], 21)
        self.assertEqual(len(first_page.data["results"]), 20)
        self.assertIsNotNone(first_page.data["next"])
        self.assertEqual(len(second_page.data["results"]), 1)
        self.assertIsNotNone(second_page.data["previous"])

    def test_retrieves_reading_by_id(self):
        reading = create_reading()
        detail_url = reverse(
            "weather:weather-reading-detail",
            kwargs={"pk": reading.pk},
        )

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], reading.id)

    def test_returns_not_found_for_unknown_reading(self):
        detail_url = reverse(
            "weather:weather-reading-detail",
            kwargs={"pk": 999999},
        )

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "weather_reading_not_found")

