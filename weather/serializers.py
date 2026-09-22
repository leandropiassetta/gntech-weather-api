from rest_framework import serializers

from weather.models import WeatherReading


class CountryCodeValidationMixin:
    def validate_country_code(self, value):
        normalized_country_code = value.upper()
        is_valid_country_code = (
            normalized_country_code.isascii()
            and normalized_country_code.isalpha()
        )
        if not is_valid_country_code:
            raise serializers.ValidationError(
                "Enter a valid two-letter country code."
            )
        return normalized_country_code


class WeatherCollectionSerializer(
    CountryCodeValidationMixin,
    serializers.Serializer,
):
    city = serializers.CharField(max_length=100, trim_whitespace=True)
    country_code = serializers.CharField(
        min_length=2,
        max_length=2,
        trim_whitespace=True,
    )


class WeatherReadingFilterSerializer(
    CountryCodeValidationMixin,
    serializers.Serializer,
):
    city = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
        required=False,
    )
    country_code = serializers.CharField(
        min_length=2,
        max_length=2,
        trim_whitespace=True,
        required=False,
    )


class WeatherReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherReading
        fields = (
            "id",
            "requested_city",
            "city",
            "state",
            "country_code",
            "provider_location_id",
            "latitude",
            "longitude",
            "temperature",
            "feels_like",
            "humidity",
            "pressure",
            "condition",
            "description",
            "wind_speed",
            "observed_at",
            "created_at",
        )
        read_only_fields = fields


class PaginatedWeatherReadingSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = WeatherReadingSerializer(many=True)


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField()
