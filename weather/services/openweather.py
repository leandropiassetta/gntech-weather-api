from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings

from weather.services.exceptions import (
    OpenWeatherAuthenticationError,
    OpenWeatherConfigurationError,
    OpenWeatherLocationNotFoundError,
    OpenWeatherRateLimitError,
    OpenWeatherResponseError,
    OpenWeatherTimeoutError,
    OpenWeatherUnavailableError,
)


@dataclass(frozen=True, slots=True)
class GeocodedLocation:
    name: str
    state: str
    country_code: str
    latitude: Decimal
    longitude: Decimal


@dataclass(frozen=True, slots=True)
class CurrentWeather:
    provider_location_id: int | None
    temperature: Decimal
    feels_like: Decimal
    humidity: int
    pressure: int
    condition: str
    description: str
    wind_speed: Decimal
    observed_at: datetime


class OpenWeatherClient:
    GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
    CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, api_key=None, session=None, timeout=None):
        resolved_api_key = settings.OPENWEATHER_API_KEY if api_key is None else api_key
        if not resolved_api_key or not resolved_api_key.strip():
            raise OpenWeatherConfigurationError(
                "OPENWEATHER_API_KEY is not configured."
            )

        resolved_timeout = (
            settings.OPENWEATHER_TIMEOUT_SECONDS if timeout is None else timeout
        )
        if resolved_timeout <= 0:
            raise OpenWeatherConfigurationError(
                "OPENWEATHER_TIMEOUT_SECONDS must be greater than zero."
            )

        self.api_key = resolved_api_key.strip()
        self.session = session or requests.Session()
        self.timeout = resolved_timeout

    def geocode(self, city, country_code):
        payload = self._get_json(
            self.GEOCODING_URL,
            params={
                "q": f"{city.strip()},{country_code.strip().upper()}",
                "limit": 1,
                "appid": self.api_key,
            },
        )

        if not isinstance(payload, list):
            raise OpenWeatherResponseError(
                "OpenWeather returned an invalid geocoding response."
            )
        if not payload:
            raise OpenWeatherLocationNotFoundError(
                "The requested location was not found."
            )

        try:
            location = payload[0]
            name = self._required_string(location, "name")
            country = self._required_string(location, "country").upper()
            state = location.get("state") or ""
            latitude = self._decimal(location["lat"])
            longitude = self._decimal(location["lon"])

            if not isinstance(state, str):
                raise TypeError
            if len(country) != 2:
                raise ValueError
            if not Decimal("-90") <= latitude <= Decimal("90"):
                raise ValueError
            if not Decimal("-180") <= longitude <= Decimal("180"):
                raise ValueError
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise OpenWeatherResponseError(
                "OpenWeather returned an invalid geocoding response."
            ) from exc

        return GeocodedLocation(
            name=name,
            state=state,
            country_code=country,
            latitude=latitude,
            longitude=longitude,
        )

    def get_current_weather(self, latitude, longitude):
        payload = self._get_json(
            self.CURRENT_WEATHER_URL,
            params={
                "lat": format(latitude, "f"),
                "lon": format(longitude, "f"),
                "appid": self.api_key,
                "units": "metric",
                "lang": "pt_br",
            },
        )

        if not isinstance(payload, dict):
            raise OpenWeatherResponseError(
                "OpenWeather returned an invalid weather response."
            )

        try:
            main = payload["main"]
            weather_items = payload["weather"]
            wind = payload["wind"]
            weather = weather_items[0]

            provider_location_id = payload.get("id")
            if provider_location_id is not None:
                provider_location_id = int(provider_location_id)
                if provider_location_id < 0:
                    raise ValueError

            temperature = self._decimal(main["temp"])
            feels_like = self._decimal(main["feels_like"])
            humidity = int(main["humidity"])
            pressure = int(main["pressure"])
            condition = self._required_string(weather, "main")
            description = self._required_string(weather, "description")
            wind_speed = self._decimal(wind["speed"])
            observed_at = datetime.fromtimestamp(int(payload["dt"]), tz=UTC)

            if not 0 <= humidity <= 100:
                raise ValueError
            if pressure < 1 or wind_speed < 0:
                raise ValueError
        except (
            AttributeError,
            IndexError,
            KeyError,
            OSError,
            OverflowError,
            TypeError,
            ValueError,
        ) as exc:
            raise OpenWeatherResponseError(
                "OpenWeather returned an invalid weather response."
            ) from exc

        return CurrentWeather(
            provider_location_id=provider_location_id,
            temperature=temperature,
            feels_like=feels_like,
            humidity=humidity,
            pressure=pressure,
            condition=condition,
            description=description,
            wind_speed=wind_speed,
            observed_at=observed_at,
        )

    def _get_json(self, url, params):
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise OpenWeatherTimeoutError("OpenWeather request timed out.") from exc
        except requests.RequestException as exc:
            raise OpenWeatherUnavailableError("OpenWeather is unavailable.") from exc

        if response.status_code in {401, 403}:
            raise OpenWeatherAuthenticationError(
                "OpenWeather rejected the configured API key."
            )
        if response.status_code == 429:
            raise OpenWeatherRateLimitError(
                retry_after=response.headers.get("Retry-After")
            )
        if response.status_code >= 500:
            raise OpenWeatherUnavailableError("OpenWeather is unavailable.")
        if not 200 <= response.status_code < 300:
            raise OpenWeatherResponseError(
                f"OpenWeather returned status code {response.status_code}."
            )

        try:
            return response.json()
        except ValueError as exc:
            raise OpenWeatherResponseError(
                "OpenWeather returned a non-JSON response."
            ) from exc

    @staticmethod
    def _decimal(value):
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError from exc

    @staticmethod
    def _required_string(data, key):
        value = data[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError
        return value
