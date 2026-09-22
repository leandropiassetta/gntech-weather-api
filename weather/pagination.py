from rest_framework.pagination import PageNumberPagination


class WeatherReadingPagination(PageNumberPagination):
    page_size = 20
