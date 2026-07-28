"""
Unit tests for the Weather Plugin.

Tests:
- City name parsing from natural language
- API key retrieval
- Geocoding (mocked requests)
- Forecast fetching (mocked requests)
- Date grouping and formatting
- Plugin execution end-to-end (mocked)
- Error handling (no key, city not found, API errors)
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.plugin import PluginResult
from src.plugins.weather import (
    WeatherPlugin,
    _fetch_forecast,
    _geocode_city,
    _get_api_key,
    _get_weather_emoji,
    _group_by_date,
    _parse_city,
)


# ============================================================
# Weather Emoji Tests
# ============================================================


class TestWeatherEmoji:
    def test_thunderstorm(self):
        assert _get_weather_emoji("thunderstorm", 211) == "⛈️"

    def test_drizzle(self):
        assert _get_weather_emoji("drizzle", 310) == "🌦️"

    def test_rain(self):
        assert _get_weather_emoji("moderate rain", 501) == "🌦️"
        assert _get_weather_emoji("heavy rain", 502) == "🌧️"

    def test_snow(self):
        assert _get_weather_emoji("light snow", 601) == "🌨️"

    def test_clear(self):
        assert _get_weather_emoji("clear sky", 800) == "☀️"

    def test_few_clouds(self):
        assert _get_weather_emoji("few clouds", 801) == "🌤️"

    def test_scattered_clouds(self):
        assert _get_weather_emoji("scattered clouds", 802) == "⛅"

    def test_broken_clouds(self):
        assert _get_weather_emoji("broken clouds", 803) == "☁️"

    def test_overcast(self):
        assert _get_weather_emoji("overcast clouds", 804) == "☁️"

    def test_mist(self):
        assert _get_weather_emoji("mist", 701) == "🌫️"

    def test_fallthrough_by_keyword(self):
        """Should match by keyword description when code isn't in the map."""
        assert _get_weather_emoji("sand whirls", 730) == "🌪️"

    def test_unknown_returns_default(self):
        """Unknown condition codes should return the default emoji."""
        emoji = _get_weather_emoji("unknown condition", 999)
        assert emoji == "🌡️"


# ============================================================
# City Parsing Tests
# ============================================================


class TestParseCity:
    def test_weather_in_city_english(self):
        """weather in Hanoi → Hanoi"""
        assert _parse_city("weather in Hanoi") == "Hanoi"

    def test_weather_city_english(self):
        """weather Hanoi → Hanoi"""
        assert _parse_city("weather Hanoi") == "Hanoi"

    def test_forecast_city(self):
        """forecast London → London"""
        assert _parse_city("forecast London") == "London"

    def test_thoi_tiet_vietnamese(self):
        """thời tiết Hà Nội → Hà Nội"""
        assert _parse_city("thời tiết Hà Nội") == "Hà Nội"

    def test_nhiet_do_vietnamese(self):
        """nhiệt độ Tokyo → Tokyo"""
        assert _parse_city("nhiệt độ Tokyo") == "Tokyo"

    def test_du_bao_vietnamese(self):
        """dự báo Đà Nẵng → Đà Nẵng"""
        assert _parse_city("dự báo Đà Nẵng") == "Đà Nẵng"

    def test_weather_for_city(self):
        """weather for Paris → Paris"""
        assert _parse_city("weather for Paris") == "Paris"

    def test_no_weather_keyword(self):
        """No weather keyword should return None (falls through to LLM)."""
        assert _parse_city("Hello, how are you?") is None

    def test_just_city_name(self):
        """Just a city name with no keyword should return None."""
        assert _parse_city("Hanoi") is None

    def test_city_with_trailing_punctuation(self):
        """weather in Hanoi? → Hanoi"""
        assert _parse_city("weather in Hanoi?") == "Hanoi"

    def test_empty_input(self):
        """Empty input should return None."""
        assert _parse_city("") is None

    def test_case_insensitive(self):
        """WEATHER in London → London"""
        assert _parse_city("WEATHER in London") == "London"

    def test_city_with_spaces(self):
        """weather in Ho Chi Minh → Ho Chi Minh"""
        assert _parse_city("weather in Ho Chi Minh") == "Ho Chi Minh"


# ============================================================
# API Key Tests
# ============================================================


class TestGetApiKey:
    def test_raises_error_when_not_configured(self, monkeypatch):
        """No API key configured should raise ValueError."""
        monkeypatch.delenv("WEATHER_API_KEY", raising=False)
        with pytest.raises(ValueError, match="WEATHER_API_KEY"):
            _get_api_key()

    def test_reads_from_env(self, monkeypatch):
        """Should read WEATHER_API_KEY from environment."""
        monkeypatch.setenv("WEATHER_API_KEY", "test_key_123")
        assert _get_api_key() == "test_key_123"


# ============================================================
# Geocoding Tests (mocked)
# ============================================================


class TestGeocodeCity:
    def test_successful_geocode(self):
        """Successful geocoding should return lat/lon/name/country."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "lat": 21.0278,
                "lon": 105.8342,
                "name": "Hanoi",
                "country": "VN",
                "state": "",
            }
        ]

        with patch("src.plugins.weather.requests.get", return_value=mock_response):
            result = _geocode_city("Hanoi", "test_key")

        assert result is not None
        assert result["lat"] == 21.0278
        assert result["lon"] == 105.8342
        assert result["name"] == "Hanoi"
        assert result["country"] == "VN"

    def test_city_not_found(self):
        """No results should return None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("src.plugins.weather.requests.get", return_value=mock_response):
            result = _geocode_city("InvalidCityXYZ", "test_key")

        assert result is None

    def test_http_error(self):
        """HTTP error should return None."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")

        with patch("src.plugins.weather.requests.get", return_value=mock_response):
            result = _geocode_city("Hanoi", "bad_key")

        assert result is None

    def test_connection_error(self):
        """Connection error should return None."""
        with patch(
            "src.plugins.weather.requests.get",
            side_effect=requests.ConnectionError("No route to host"),
        ):
            result = _geocode_city("Hanoi", "test_key")

        assert result is None


# ============================================================
# Forecast Fetching Tests (mocked)
# ============================================================


class TestFetchForecast:
    @pytest.fixture
    def mock_forecast_data(self):
        """Sample forecast data matching OpenWeatherMap structure."""
        return {
            "cod": "200",
            "message": 0,
            "cnt": 8,
            "list": [
                {
                    "dt": 1700000000 + i * 10800,  # 3-hour intervals
                    "main": {
                        "temp": 25.0 + i * 0.5,
                        "feels_like": 24.0 + i * 0.5,
                        "temp_min": 23.0 + i * 0.5,
                        "temp_max": 26.0 + i * 0.5,
                        "pressure": 1013,
                        "humidity": 70 + i,
                        "sea_level": 1013,
                        "grnd_level": 1009,
                    },
                    "weather": [
                        {"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}
                    ],
                    "clouds": {"all": 10},
                    "wind": {"speed": 3.5, "deg": 180, "gust": 5.0},
                    "visibility": 10000,
                    "pop": 0.1,
                    "sys": {"pod": "d"},
                    "dt_txt": f"2024-11-{15 + i // 8:02d} 12:00:00",
                }
                for i in range(8)
            ],
            "city": {
                "id": 1581130,
                "name": "Hanoi",
                "coord": {"lat": 21.0278, "lon": 105.8342},
                "country": "VN",
                "timezone": 25200,
                "sunrise": 1700000000,
                "sunset": 1700040000,
            },
        }

    def test_successful_fetch(self, mock_forecast_data):
        """Successful forecast fetch should return entry list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_forecast_data

        with patch("src.plugins.weather.requests.get", return_value=mock_response):
            entries = _fetch_forecast(21.0278, 105.8342, "test_key")

        assert entries is not None
        assert len(entries) == 8
        assert entries[0]["main"]["temp"] == 25.0

    def test_empty_response(self):
        """Empty API response should return None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"cod": "200", "list": []}

        with patch("src.plugins.weather.requests.get", return_value=mock_response):
            entries = _fetch_forecast(0, 0, "test_key")

        assert entries is not None
        assert len(entries) == 0

    def test_http_error(self):
        """HTTP error should return None."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")

        with patch("src.plugins.weather.requests.get", return_value=mock_response):
            entries = _fetch_forecast(21.0, 105.0, "bad_key")

        assert entries is None


# ============================================================
# Date Grouping Tests
# ============================================================


class TestGroupByDate:
    def test_groups_by_date(self):
        """Entries from different dates should be grouped separately."""
        entries = [
            {
                "dt": 1700000000,  # Some date
                "main": {"temp": 25, "humidity": 70},
                "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
                "wind": {"speed": 3.0},
            },
            {
                "dt": 1700086400,  # Next day
                "main": {"temp": 22, "humidity": 75},
                "weather": [{"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02d"}],
                "wind": {"speed": 4.0},
            },
            {
                "dt": 1700172800,  # Another day
                "main": {"temp": 20, "humidity": 80},
                "weather": [{"id": 500, "main": "Rain", "description": "light rain", "icon": "10d"}],
                "wind": {"speed": 5.0},
            },
        ]

        groups = _group_by_date(entries)
        assert len(groups) >= 2  # At least 2 different dates

    def test_temp_min_max(self):
        """Should calculate min/max temperature per day."""
        entries = [
            {
                "dt": 1700000000,
                "main": {"temp": 20, "humidity": 70},
                "weather": [{"id": 800, "description": "clear sky"}],
                "wind": {"speed": 3.0},
            },
            {
                "dt": 1700010000,  # Same day, ~3 hours later
                "main": {"temp": 25, "humidity": 65},
                "weather": [{"id": 800, "description": "clear sky"}],
                "wind": {"speed": 4.0},
            },
            {
                "dt": 1700020000,  # Same day, ~6 hours later
                "main": {"temp": 22, "humidity": 68},
                "weather": [{"id": 800, "description": "clear sky"}],
                "wind": {"speed": 3.5},
            },
        ]

        groups = _group_by_date(entries)
        assert len(groups) == 1
        assert groups[0]["temp_min"] == 20
        assert groups[0]["temp_max"] == 25

    def test_dominant_weather(self):
        """Should pick the most frequent weather description."""
        entries = [
            {
                "dt": 1700000000 + i * 10800,
                "main": {"temp": 25, "humidity": 70},
                "weather": [{"id": 802, "description": "scattered clouds"}],
                "wind": {"speed": 3.0},
            }
            for i in range(5)  # 5 entries, all scattered clouds
        ]

        groups = _group_by_date(entries)
        assert "scattered clouds" in groups[0]["weather_main"]

    def test_humidity_and_wind(self):
        """Should calculate average humidity and max wind."""
        entries = [
            {
                "dt": 1700000000,
                "main": {"temp": 25, "humidity": 60},
                "weather": [{"id": 800, "description": "clear sky"}],
                "wind": {"speed": 2.0},
            },
            {
                "dt": 1700010000,
                "main": {"temp": 26, "humidity": 70},
                "weather": [{"id": 800, "description": "clear sky"}],
                "wind": {"speed": 5.0},
            },
        ]

        groups = _group_by_date(entries)
        assert groups[0]["humidity_avg"] == 65.0  # (60 + 70) / 2
        assert groups[0]["wind_max"] == 5.0


# ============================================================
# Shared Fixtures (module-level for cross-class access)
# ============================================================


@pytest.fixture
def mock_geocode_response():
    """Mock successful geocoding response for Hanoi."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = [
        {"lat": 21.0278, "lon": 105.8342, "name": "Hanoi", "country": "VN", "state": ""}
    ]
    return mock


@pytest.fixture
def mock_forecast_response():
    """A mock 8-entry (1 day) forecast response."""
    entries = []
    for i in range(8):
        entries.append({
            "dt": 1700000000 + i * 10800,
            "main": {
                "temp": 25.0 + i * 0.5,
                "feels_like": 24.0 + i * 0.5,
                "temp_min": 23.0,
                "temp_max": 27.0,
                "pressure": 1013,
                "humidity": 70 + i,
                "sea_level": 1013,
                "grnd_level": 1009,
            },
            "weather": [
                {"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}
            ],
            "clouds": {"all": 10},
            "wind": {"speed": 3.5, "deg": 180, "gust": 5.0},
            "visibility": 10000,
            "pop": 0.0,
            "sys": {"pod": "d"},
            "dt_txt": f"2024-11-{15 + i // 8:02d} 12:00:00",
        })
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"cod": "200", "message": 0, "cnt": 8, "list": entries}
    return mock


# ============================================================
# Plugin Execution Tests (end-to-end, mocked)
# ============================================================


class TestWeatherPluginExecute:
    def test_successful_weather_query(self, monkeypatch, mock_geocode_response, mock_forecast_response):
        """Full weather query should return a successful PluginResult with formatted output."""
        monkeypatch.setenv("WEATHER_API_KEY", "test_key_123")

        # Mock both API calls
        with patch("src.plugins.weather.requests.get") as mock_get:
            # First call: geocoding, Second call: forecast
            mock_get.side_effect = [mock_geocode_response, mock_forecast_response]

            plugin = WeatherPlugin()
            result = plugin.execute("weather in Hanoi")

        assert result.success is True
        assert isinstance(result.output, str)
        assert len(result.output) > 0
        assert "Hanoi" in result.output
        assert "°C" in result.output
        assert "☀️" in result.output or "🌡️" in result.output

    def test_no_city_identified(self):
        """Input with no weather keywords should return error."""
        plugin = WeatherPlugin()
        result = plugin.execute("Hello!")
        assert result.success is False
        assert "Không tìm thấy" in result.error

    def test_empty_input(self):
        """Empty input should return error."""
        plugin = WeatherPlugin()
        result = plugin.execute("")
        assert result.success is False

    def test_no_api_key(self, monkeypatch):
        """No API key should return error."""
        monkeypatch.delenv("WEATHER_API_KEY", raising=False)
        plugin = WeatherPlugin()
        result = plugin.execute("weather in Hanoi")
        assert result.success is False
        assert "WEATHER_API_KEY" in result.error

    def test_city_not_found(self, monkeypatch):
        """Unrecognized city should return error."""
        monkeypatch.setenv("WEATHER_API_KEY", "test_key_123")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("src.plugins.weather.requests.get", return_value=mock_response):
            plugin = WeatherPlugin()
            result = plugin.execute("weather in Xyzinvalid")

        assert result.success is False
        assert "Không tìm thấy" in result.error

    def test_vietnamese_query(self, monkeypatch, mock_geocode_response, mock_forecast_response):
        """Vietnamese query should work too."""
        monkeypatch.setenv("WEATHER_API_KEY", "test_key_123")

        with patch("src.plugins.weather.requests.get") as mock_get:
            mock_get.side_effect = [mock_geocode_response, mock_forecast_response]
            plugin = WeatherPlugin()
            result = plugin.execute("thời tiết Hà Nội")

        assert result.success is True
        assert "Hanoi" in result.output

    def test_forecast_query(self, monkeypatch, mock_geocode_response, mock_forecast_response):
        """'forecast' keyword should work."""
        monkeypatch.setenv("WEATHER_API_KEY", "test_key_123")

        with patch("src.plugins.weather.requests.get") as mock_get:
            mock_get.side_effect = [mock_geocode_response, mock_forecast_response]
            plugin = WeatherPlugin()
            result = plugin.execute("forecast London")

        assert result.success is True

    def test_plugin_data_structure(self, monkeypatch, mock_geocode_response, mock_forecast_response):
        """Plugin result data should contain structured weather info."""
        monkeypatch.setenv("WEATHER_API_KEY", "test_key_123")

        with patch("src.plugins.weather.requests.get") as mock_get:
            mock_get.side_effect = [mock_geocode_response, mock_forecast_response]
            plugin = WeatherPlugin()
            result = plugin.execute("weather in Hanoi")

        assert result.data is not None
        assert result.data["city"] == "Hanoi"
        assert "current_temp" in result.data
        assert result.data["forecast_days"] >= 1


# ============================================================
# Plugin Discovery Test
# ============================================================


class TestWeatherPluginDiscovery:
    def test_plugin_has_correct_metadata(self):
        """WeatherPlugin should have proper name and description."""
        plugin = WeatherPlugin()
        assert plugin.name == "weather"
        assert plugin.description is not None
        assert len(plugin.description) > 0

    def test_plugin_is_baseplugin_subclass(self):
        """WeatherPlugin should inherit from BasePlugin."""
        from src.plugin import BasePlugin
        assert issubclass(WeatherPlugin, BasePlugin)


# ============================================================
# Workflow Integration Test
# ============================================================


class TestWeatherPluginWorkflow:
    def test_workflow_detects_weather_plugin(self, workflow):
        """Workflow should route weather queries to the WeatherPlugin."""
        # Check that weather plugin is loaded
        plugin = workflow.plugin_loader.get("weather")
        assert plugin is not None, "Weather plugin should be discovered by PluginLoader"
        assert plugin.name == "weather"

    def test_workflow_plugin_routing(self, monkeypatch, workflow, memory, mock_geocode_response, mock_forecast_response):
        """Workflow should route 'weather in Hanoi' to plugin."""
        monkeypatch.setenv("WEATHER_API_KEY", "test_key_123")

        with patch("src.plugins.weather.requests.get") as mock_get:
            mock_get.side_effect = [mock_geocode_response, mock_forecast_response]
            session_id = memory.create_session()
            result = workflow.process("weather in Hanoi", session_id=session_id)

        assert result.source == "plugin"
        assert result.plugin_result is not None
        assert result.plugin_result.success is True
        assert "Hanoi" in result.plugin_result.output
