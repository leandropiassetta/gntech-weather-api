"""API views for weather data."""

import logging

from django.db import DatabaseError, connection
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from weather.models import WeatherReading
from weather.pagination import WeatherReadingPagination
from weather.serializers import (
    ErrorSerializer,
    HealthCheckSerializer,
    PaginatedWeatherReadingSerializer,
    WeatherCollectionSerializer,
    WeatherReadingFilterSerializer,
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


logger = logging.getLogger(__name__)


def error_response(code, detail, status_code, headers=None):
    return Response(
        {"code": code, "detail": detail},
        status=status_code,
        headers=headers,
    )


class WeatherReadingCollectionView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Weather"],
        operation_id="list_weather_readings",
        summary="List stored weather readings",
        parameters=[
            OpenApiParameter(
                name="city",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by resolved city name (case-insensitive).",
            ),
            OpenApiParameter(
                name="country_code",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by two-letter country code.",
            ),
            OpenApiParameter(
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Page number. Each page contains up to 20 readings.",
            ),
        ],
        responses={
            200: PaginatedWeatherReadingSerializer,
            400: OpenApiResponse(description="Invalid filter value."),
            404: OpenApiResponse(description="Invalid page number."),
        },
    )
    def get(self, request):
        filters = WeatherReadingFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)

        queryset = WeatherReading.objects.all()
        city = filters.validated_data.get("city")
        country_code = filters.validated_data.get("country_code")

        if city:
            queryset = queryset.filter(city__iexact=city)
        if country_code:
            queryset = queryset.filter(country_code=country_code)

        paginator = WeatherReadingPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = WeatherReadingSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Weather"],
        operation_id="collect_weather_reading",
        summary="Collect and store the current weather",
        request=WeatherCollectionSerializer,
        responses={
            201: WeatherReadingSerializer,
            400: OpenApiResponse(description="Invalid request data."),
            404: OpenApiResponse(
                response=ErrorSerializer,
                description="Location not found.",
            ),
            502: OpenApiResponse(
                response=ErrorSerializer,
                description="Weather provider failure.",
            ),
            503: OpenApiResponse(
                response=ErrorSerializer,
                description="Weather provider unavailable or not configured.",
            ),
        },
    )
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


class WeatherReadingDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Weather"],
        operation_id="retrieve_weather_reading",
        summary="Retrieve a stored weather reading",
        responses={
            200: WeatherReadingSerializer,
            404: OpenApiResponse(
                response=ErrorSerializer,
                description="Weather reading not found.",
            ),
        },
    )
    def get(self, request, pk):
        try:
            reading = WeatherReading.objects.get(pk=pk)
        except WeatherReading.DoesNotExist:
            return error_response(
                code="weather_reading_not_found",
                detail="The requested weather reading was not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return Response(WeatherReadingSerializer(reading).data)


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Health"],
        operation_id="health_check",
        summary="Check API and database availability",
        responses={
            200: HealthCheckSerializer,
            503: HealthCheckSerializer,
        },
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            logger.exception("Database health check failed.")
            return Response(
                {"status": "unhealthy", "database": "unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"status": "ok", "database": "ok"})

