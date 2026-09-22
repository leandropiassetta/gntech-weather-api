from rest_framework import serializers

from weather.models import WeatherReading


class WeatherCollectionSerializer(serializers.Serializer):
    city = serializers.CharField(max_length=100, trim_whitespace=True)
    country_code = serializers.CharField(
        min_length=2,
        max_length=2,
        trim_whitespace=True,
    )

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
