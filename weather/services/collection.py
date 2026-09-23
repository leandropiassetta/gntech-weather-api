from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from weather.models import WeatherReading
from weather.services.exceptions import OpenWeatherResponseError
from weather.services.openweather import OpenWeatherClient

COORDINATE_QUANTUM = Decimal("0.000001")


def collect_weather_reading(city, country_code, client=None):
    normalized_city = city.strip()
    normalized_country_code = country_code.strip().upper()
    weather_client = client if client is not None else OpenWeatherClient()

    location = weather_client.geocode(
        normalized_city,
        normalized_country_code,
    )
    current_weather = weather_client.get_current_weather(
        location.latitude,
        location.longitude,
    )

    reading = WeatherReading(
        requested_city=normalized_city,
        city=location.name,
        state=location.state,
        country_code=location.country_code,
        provider_location_id=current_weather.provider_location_id,
        latitude=location.latitude.quantize(COORDINATE_QUANTUM),
        longitude=location.longitude.quantize(COORDINATE_QUANTUM),
        temperature=current_weather.temperature,
        feels_like=current_weather.feels_like,
        humidity=current_weather.humidity,
        pressure=current_weather.pressure,
        condition=current_weather.condition,
        description=current_weather.description,
        wind_speed=current_weather.wind_speed,
        observed_at=current_weather.observed_at,
    )

    try:
        with transaction.atomic():
            reading.full_clean()
            reading.save()
    except ValidationError as exc:
        raise OpenWeatherResponseError(
            "OpenWeather returned data outside the expected limits."
        ) from exc

    return reading
