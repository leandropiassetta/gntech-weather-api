"""Database models for weather data."""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


country_code_validator = RegexValidator(
    regex=r"^[A-Z]{2}$",
    message="Enter a valid two-letter uppercase country code.",
    code="invalid_country_code",
)


class WeatherReading(models.Model):
    """A weather observation collected from an external provider."""

    requested_city = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True, default="")
    country_code = models.CharField(
        max_length=2,
        validators=[country_code_validator],
    )
    provider_location_id = models.PositiveBigIntegerField(null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(Decimal("-90")),
            MaxValueValidator(Decimal("90")),
        ],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[
            MinValueValidator(Decimal("-180")),
            MaxValueValidator(Decimal("180")),
        ],
    )
    temperature = models.DecimalField(max_digits=6, decimal_places=2)
    feels_like = models.DecimalField(max_digits=6, decimal_places=2)
    humidity = models.PositiveSmallIntegerField(
        validators=[MaxValueValidator(100)],
    )
    pressure = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    condition = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    wind_speed = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    observed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weather_readings"
        ordering = ["-observed_at", "-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["country_code", "city"],
                name="weather_location_idx",
            ),
            models.Index(
                fields=["-observed_at"],
                name="weather_observed_at_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(humidity__gte=0, humidity__lte=100),
                name="weather_humidity_range",
            ),
            models.CheckConstraint(
                condition=models.Q(latitude__gte=-90, latitude__lte=90),
                name="weather_latitude_range",
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__gte=-180, longitude__lte=180),
                name="weather_longitude_range",
            ),
            models.CheckConstraint(
                condition=models.Q(pressure__gte=1),
                name="weather_positive_pressure",
            ),
            models.CheckConstraint(
                condition=models.Q(wind_speed__gte=0),
                name="weather_nonnegative_wind",
            ),
        ]

    def __str__(self):
        return f"{self.city}, {self.country_code} - {self.observed_at.isoformat()}"
