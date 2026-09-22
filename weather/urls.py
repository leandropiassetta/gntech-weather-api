from django.urls import path

from weather.views import (
    WeatherReadingCollectionView,
    WeatherReadingDetailView,
)

app_name = "weather"

urlpatterns = [
    path(
        "weather-readings/",
        WeatherReadingCollectionView.as_view(),
        name="weather-reading-list",
    ),
    path(
        "weather-readings/<int:pk>/",
        WeatherReadingDetailView.as_view(),
        name="weather-reading-detail",
    ),
]
