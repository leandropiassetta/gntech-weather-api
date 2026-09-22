"""URL configuration for the weather API."""

from django.urls import include, path


urlpatterns = [
    path("api/v1/", include("weather.urls")),
]
