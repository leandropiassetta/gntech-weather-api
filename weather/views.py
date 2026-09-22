"""API views for weather data."""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from weather.serializers import (
    WeatherCollectionSerializer,
    WeatherReadingSerializer,
)
from weather.services.collection import collect_weather_reading
from weather.services.exceptions import (
    OpenWeatherAuthenticationError,
    OpenWeatherConfigurationError,
    OpenWeatherLocationNotFoundError,
    OpenWeatherRateLimitError,
    OpenWeatherResponseError,
    OpenWeatherTimeoutError,
    OpenWeatherUnavailableError,
)


def error_response(code, detail, status_code, headers=None):
    return Response(
        {"code": code, "detail": detail},
        status=status_code,
        headers=headers,
    )


class WeatherReadingCollectionView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = WeatherCollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            reading = collect_weather_reading(**serializer.validated_data)
        except OpenWeatherLocationNotFoundError:
            return error_response(
                code="location_not_found",
                detail="The requested location was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except OpenWeatherConfigurationError:
            return error_response(
                code="weather_provider_not_configured",
                detail="The weather provider is not configured.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except OpenWeatherAuthenticationError:
            return error_response(
                code="weather_provider_authentication_failed",
                detail="The weather provider authentication failed.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except OpenWeatherRateLimitError as exc:
            headers = None
            if exc.retry_after:
                headers = {"Retry-After": str(exc.retry_after)}
            return error_response(
                code="weather_provider_rate_limited",
                detail="The weather provider rate limit was exceeded.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                headers=headers,
            )
        except (OpenWeatherTimeoutError, OpenWeatherUnavailableError):
            return error_response(
                code="weather_provider_unavailable",
                detail="The weather provider is unavailable.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )
        except OpenWeatherResponseError:
            return error_response(
                code="weather_provider_invalid_response",
                detail="The weather provider returned an invalid response.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            WeatherReadingSerializer(reading).data,
            status=status.HTTP_201_CREATED,
        )

