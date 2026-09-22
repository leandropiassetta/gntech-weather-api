from unittest.mock import patch

from django.db import DatabaseError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class OperationalApiTests(APITestCase):
    def test_health_check_reports_database_availability(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok", "database": "ok"})

    @patch("weather.views.logger.exception")
    @patch("weather.views.connection.cursor", side_effect=DatabaseError)
    def test_health_check_reports_database_failure(self, cursor, log_exception):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.data,
            {"status": "unhealthy", "database": "unavailable"},
        )
        cursor.assert_called_once_with()
        log_exception.assert_called_once_with("Database health check failed.")

    def test_openapi_schema_describes_public_endpoints(self):
        response = self.client.get(
            reverse("schema"),
            {"format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("/api/v1/weather-readings/", response.data["paths"])
        self.assertIn("/api/v1/weather-readings/{id}/", response.data["paths"])
        self.assertIn("/health/", response.data["paths"])

    def test_swagger_ui_is_available(self):
        response = self.client.get(reverse("swagger-ui"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["Content-Type"])
