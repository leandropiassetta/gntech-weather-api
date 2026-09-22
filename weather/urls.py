from django.urls import path

from weather.views import WeatherReadingCollectionView


app_name = "weather"

urlpatterns = [
    path(
        "weather-readings/",
        WeatherReadingCollectionView.as_view(),
        name="weather-reading-list",
    ),
]
