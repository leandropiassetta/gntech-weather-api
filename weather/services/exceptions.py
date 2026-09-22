class OpenWeatherError(Exception):
    """Base exception for OpenWeather integration errors."""


class OpenWeatherConfigurationError(OpenWeatherError):
    """Raised when the integration is not configured correctly."""


class OpenWeatherLocationNotFoundError(OpenWeatherError):
    """Raised when OpenWeather cannot resolve a requested location."""


class OpenWeatherProviderError(OpenWeatherError):
    """Base exception for failures returned by OpenWeather."""


class OpenWeatherAuthenticationError(OpenWeatherProviderError):
    """Raised when OpenWeather rejects the configured API key."""


class OpenWeatherRateLimitError(OpenWeatherProviderError):
    """Raised when the OpenWeather request limit is reached."""

    def __init__(self, retry_after=None):
        super().__init__("OpenWeather rate limit exceeded.")
        self.retry_after = retry_after


class OpenWeatherUnavailableError(OpenWeatherProviderError):
    """Raised when OpenWeather cannot be reached or is unavailable."""


class OpenWeatherTimeoutError(OpenWeatherUnavailableError):
    """Raised when OpenWeather does not respond within the timeout."""


class OpenWeatherResponseError(OpenWeatherProviderError):
    """Raised when OpenWeather returns an invalid or unexpected response."""

