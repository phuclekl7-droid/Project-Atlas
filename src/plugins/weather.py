"""
Weather Plugin — fetches 5-day weather forecast from OpenWeatherMap API.

Uses the OpenWeatherMap free tier:
  - Geocoding API: city → lat/lon
  - 5-day / 3-hour forecast API: lat/lon → forecast data

Usage:
    "weather in Hanoi"
    "thời tiết Hà Nội"
    "nhiệt độ Tokyo"
    "forecast London"
    "dự báo thời tiết Đà Nẵng"
"""

import os
import re
from datetime import datetime, timezone
from typing import Optional

import requests

from src.plugin import BasePlugin, PluginResult

# ── Constants ──

_GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
_REQUEST_TIMEOUT = 10  # seconds

# Weather condition code → emoji mapping
_WEATHER_EMOJIS: dict[str, str] = {
    "clear": "☀️",
    "few clouds": "🌤️",
    "scattered clouds": "⛅",
    "broken clouds": "☁️",
    "overcast": "☁️",
    "shower rain": "🌦️",
    "rain": "🌧️",
    "thunderstorm": "⛈️",
    "snow": "🌨️",
    "mist": "🌫️",
    "fog": "🌫️",
    "haze": "🌫️",
    "dust": "🌪️",
    "sand": "🌪️",
    "squall": "🌬️",
    "tornado": "🌪️",
    "default": "🌡️",
}

# ── Helper Functions ──


def _get_weather_emoji(description: str, code_id: int) -> str:
    """Map weather condition to emoji."""
    desc_lower = description.lower()

    # Thunderstorm (2xx)
    if 200 <= code_id < 300:
        return "⛈️"
    # Drizzle (3xx)
    if 300 <= code_id < 400:
        return "🌦️"
    # Rain (5xx)
    if 500 <= code_id < 600:
        return "🌧️" if code_id >= 502 else "🌦️"
    # Snow (6xx)
    if 600 <= code_id < 700:
        return "🌨️"
    # Atmosphere (7xx)
    if 700 <= code_id < 800:
        return "🌫️"
    # Clear (800)
    if code_id == 800:
        return "☀️"
    # Clouds (80x)
    if code_id == 801:
        return "🌤️"
    if code_id == 802:
        return "⛅"
    if code_id == 803 or code_id == 804:
        return "☁️"

    # Fallback by description keywords
    for keyword, emoji in _WEATHER_EMOJIS.items():
        if keyword in desc_lower:
            return emoji

    return _WEATHER_EMOJIS["default"]


def _get_api_key() -> str:
    """Get OpenWeatherMap API key from settings or environment."""
    # First try: already configured in Settings (injected by Workflow)
    try:
        from src.settings import load_settings
        settings = load_settings()
        if settings.weather_api_key:
            return settings.weather_api_key
    except Exception:
        pass

    # Fallback: direct env var
    key = os.environ.get("WEATHER_API_KEY", "")
    if key:
        return key

    raise ValueError(
        "WEATHER_API_KEY chưa được cấu hình. "
        "Thêm vào file .env: WEATHER_API_KEY=your_key_here\n\n"
        "Đăng ký API key miễn phí tại: https://openweathermap.org/api"
    )


def _geocode_city(city: str, api_key: str) -> Optional[dict]:
    """
    Convert a city name to lat/lon coordinates using OpenWeatherMap Geocoding API.

    Args:
        city: City name (e.g., "Hanoi", "London")
        api_key: OpenWeatherMap API key

    Returns:
        Dict with lat, lon, name, country or None on failure
    """
    params = {
        "q": city,
        "limit": 1,
        "appid": api_key,
    }

    try:
        response = requests.get(_GEOCODING_URL, params=params, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if not data:
            return None

        return {
            "lat": data[0]["lat"],
            "lon": data[0]["lon"],
            "name": data[0].get("name", city),
            "country": data[0].get("country", ""),
            "state": data[0].get("state", ""),
        }
    except requests.RequestException:
        return None


def _fetch_forecast(lat: float, lon: float, api_key: str) -> Optional[list[dict]]:
    """
    Fetch 5-day / 3-hour forecast data.

    Args:
        lat: Latitude
        lon: Longitude
        api_key: OpenWeatherMap API key

    Returns:
        List of forecast entries (each = 3-hour interval), or None on failure
    """
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",  # Celsius
        "lang": "vi",       # Vietnamese descriptions if available
    }

    try:
        response = requests.get(_FORECAST_URL, params=params, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        return data.get("list", [])
    except requests.RequestException:
        return None


def _group_by_date(entries: list[dict]) -> list[dict]:
    """
    Group 3-hour forecast entries by date.

    Returns a list of day groups, each containing:
      - date: "Thứ 2, 15/04"
      - entries: list of forecast entries for that day
      - temp_min: min temp for the day
      - temp_max: max temp for the day
      - weather_main: dominant weather condition
      - weather_emoji: corresponding emoji
      - humidity_avg: average humidity
      - wind_max: max wind speed
    """
    from collections import OrderedDict

    day_map: OrderedDict[str, list[dict]] = OrderedDict()

    for entry in entries:
        dt = datetime.fromtimestamp(entry["dt"], tz=timezone.utc)
        date_key = dt.strftime("%Y-%m-%d")
        if date_key not in day_map:
            day_map[date_key] = []
        day_map[date_key].append(entry)

    # Vietnamese day names
    viet_weekdays = {
        0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư",
        3: "Thứ Năm", 4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật",
    }

    day_groups = []
    for date_key, entries_list in day_map.items():
        dt = datetime.strptime(date_key, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        weekday = viet_weekdays[dt.weekday()]
        day_month = dt.strftime("%d/%m")
        display_date = f"{weekday}, {day_month}"

        temps = [e["main"]["temp"] for e in entries_list]
        weather_main = max(
            set(e["weather"][0]["description"] for e in entries_list),
            key=lambda w: sum(1 for e in entries_list if e["weather"][0]["description"] == w),
        )
        weather_id = max(
            e["weather"][0]["id"] for e in entries_list
        )
        humids = [e["main"]["humidity"] for e in entries_list]
        winds = [e["wind"]["speed"] for e in entries_list]

        day_groups.append({
            "date": display_date,
            "date_key": date_key,
            "entries": entries_list,
            "temp_min": min(temps),
            "temp_max": max(temps),
            "weather_main": weather_main,
            "weather_emoji": _get_weather_emoji(weather_main, weather_id),
            "humidity_avg": sum(humids) / len(humids),
            "wind_max": max(winds),
        })

    return day_groups


def _parse_city(input_str: str) -> Optional[str]:
    """
    Extract city name from user input.

    Supports patterns:
      - "weather in Hanoi"
      - "thời tiết Hà Nội"
      - "nhiệt độ Tokyo"
      - "forecast London"
      - "dự báo thời tiết Đà Nẵng"
      - "weather Paris tomorrow"
      - "Hanoi" (falls through to LLM if just a city name)

    Returns:
        City name or None if no weather-related keywords found
    """
    text = input_str.strip()

    # Patterns: keyword + [optional words] + city
    patterns = [
        re.compile(r"(?:weather|forecast)\s+(?:in|for|at|of)?\s*(.+)", re.IGNORECASE),
        re.compile(r"(?:thời tiết|nhiệt độ|dự báo)\s+(.+)", re.IGNORECASE),
        re.compile(r"(.+)\s+(?:weather|forecast)", re.IGNORECASE),
        re.compile(r"(.+)\s+(?:thời tiết|nhiệt độ|dự báo)", re.IGNORECASE),
    ]

    # Only trigger if weather-related keyword is present
    weather_keywords = [
        "weather", "forecast", "temperature",
        "thời tiết", "nhiệt độ", "dự báo", "thoitiet", "nhiet do",
    ]

    has_keyword = any(kw in text.lower() for kw in weather_keywords)
    if not has_keyword:
        return None

    for pattern in patterns:
        match = pattern.search(text)
        if match:
            city = match.group(1).strip().rstrip("?.,!;:")
            # Remove trailing "tomorrow", "today", "now"
            city = re.sub(r"\s+(tomorrow|today|now|hôm nay|ngày mai|tuần này)$", "", city, flags=re.IGNORECASE)
            city = city.strip()
            if city and len(city) >= 2:
                return city

    # If no pattern matched but has keyword, try extracting last word as city
    words = text.split()
    for word in reversed(words):
        word = word.strip("?.,!;:")
        if word.lower() not in weather_keywords and len(word) >= 2:
            return word

    return None


# ============================================================
# Weather Plugin
# ============================================================


class WeatherPlugin(BasePlugin):
    """
    Fetches 5-day weather forecast using OpenWeatherMap API.

    Extracts the city name from natural language input,
    geocodes it to coordinates, fetches forecast data,
    and returns a beautifully formatted weather report.

    Examples:
        "weather in Hanoi"
        "thời tiết Hà Nội"
        "nhiệt độ Tokyo"
        "forecast London"
        "dự báo thời tiết Đà Nẵng"
    """

    name = "weather"
    description = "Dự báo thời tiết 5 ngày với OpenWeatherMap"

    def execute(self, input_str: str) -> PluginResult:
        """
        Fetch and display weather forecast for a given city.

        Args:
            input_str: Natural language query (e.g., "weather in Hanoi")

        Returns:
            PluginResult with formatted weather data
        """
        text = input_str.strip()

        if not text:
            return PluginResult(
                success=False,
                error="Vui lòng nhập tên thành phố. Ví dụ: weather in Hanoi",
            )

        # Parse city name
        city = _parse_city(text)
        if city is None:
            return PluginResult(
                success=False,
                error=(
                    f"Không tìm thấy tên thành phố trong: '{text}'\n\n"
                    f"Cách dùng:\n"
                    f"  • weather in Hanoi\n"
                    f"  • thời tiết Hà Nội\n"
                    f"  • forecast London\n"
                    f"  • nhiệt độ Tokyo"
                ),
            )

        # Get API key
        try:
            api_key = _get_api_key()
        except ValueError as e:
            return PluginResult(
                success=False,
                error=str(e),
            )

        # Geocode city → lat/lon
        try:
            location = _geocode_city(city, api_key)
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Không thể tra cứu tọa độ thành phố: {e}",
            )

        if location is None:
            return PluginResult(
                success=False,
                error=(
                    f"Không tìm thấy thành phố '{city}'. "
                    f"Vui lòng kiểm tra lại tên thành phố."
                ),
            )

        # Fetch forecast
        try:
            forecast_entries = _fetch_forecast(location["lat"], location["lon"], api_key)
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Không thể lấy dữ liệu thời tiết: {e}",
            )

        if not forecast_entries:
            return PluginResult(
                success=False,
                error=f"Không có dữ liệu thời tiết cho {city}.",
            )

        # Group by date and format
        day_groups = _group_by_date(forecast_entries)

        # Build location header
        location_name = location["name"]
        country = location.get("country", "")
        state = location.get("state", "")
        loc_parts = [location_name]
        if state:
            loc_parts.append(state)
        if country:
            loc_parts.append(country)

        # Current conditions (first entry)
        current = forecast_entries[0]
        current_temp = round(current["main"]["temp"])
        current_feels = round(current["main"]["feels_like"])
        current_desc = current["weather"][0]["description"]
        current_id = current["weather"][0]["id"]
        current_emoji = _get_weather_emoji(current_desc, current_id)
        current_humidity = current["main"]["humidity"]
        current_wind = round(current["wind"]["speed"], 1)

        lines = [
            f"## 🌤️ Dự báo thời tiết: {', '.join(loc_parts)}",
            "",
            f"### {current_emoji} Hiện tại",
            f"| Chỉ số | Giá trị |",
            f"|---|---|",
            f"| 🌡️ Nhiệt độ | **{current_temp}°C** (cảm giác {current_feels}°C) |",
            f"| ☁️ Trạng thái | {current_desc.title()} |",
            f"| 💧 Độ ẩm | {current_humidity}% |",
            f"| 💨 Gió | {current_wind} m/s |",
            "",
            f"### 📅 Dự báo 5 ngày",
        ]

        for day in day_groups:
            t_min = round(day["temp_min"])
            t_max = round(day["temp_max"])
            hum = round(day["humidity_avg"])
            wind = round(day["wind_max"], 1)
            emoji = day["weather_emoji"]
            desc = day["weather_main"].title()

            lines.append(
                f"**{emoji} {day['date']}**  "
                f"{t_min}°C ~ {t_max}°C  ·  {desc}  ·  💧{hum}%  ·  💨{wind} m/s"
            )

        lines.append("")
        lines.append("---")
        lines.append(
            f"🌐 Dữ liệu từ [OpenWeatherMap](https://openweathermap.org) · "
            f"{location['lat']:.2f}°N, {location['lon']:.2f}°E"
        )

        output = "\n".join(lines)

        return PluginResult(
            success=True,
            output=output,
            data={
                "city": location["name"],
                "country": country,
                "lat": location["lat"],
                "lon": location["lon"],
                "current_temp": current_temp,
                "forecast_days": len(day_groups),
            },
        )


# ============================================================
# Standalone test (run directly)
# ============================================================

if __name__ == "__main__":
    """Quick test: python -m src.plugins.weather"""
    plugin = WeatherPlugin()
    test_inputs = [
        "weather in Hanoi",
        "thời tiết Hà Nội",
        "nhiệt độ Tokyo",
        "forecast London",
    ]
    for test in test_inputs:
        print(f"\n{'='*60}")
        print(f"Input: {test}")
        print("=" * 60)
        result = plugin.execute(test)
        print(f"Success: {result.success}")
        if result.success:
            print(result.output)
        else:
            print(f"Error: {result.error}")
