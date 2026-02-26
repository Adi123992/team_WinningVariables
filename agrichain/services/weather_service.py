"""
AgriChain — Weather Service
─────────────────────────────
Currently uses a deterministic mock that simulates IMD-style 7-day forecasts.
To switch to a real API, implement `_fetch_openweather()` and toggle USE_REAL_API.

Plug-in points for real integration:
  - OpenWeatherMap One Call 3.0  →  https://api.openweathermap.org/data/3.0/onecall
  - IMD API (when available)
"""

import os
import math
import random
import hashlib
from datetime import date, timedelta
from typing import List

from models.schemas import WeatherForecast, WeatherDay

# ── Toggle this to True once you have an OWM API key in env ──
USE_REAL_API: bool = os.getenv("USE_REAL_WEATHER", "false").lower() == "true"
OWM_API_KEY:  str  = os.getenv("OWM_API_KEY", "")

# Approximate lat/lon per district (extend as needed)
DISTRICT_COORDS: dict[str, tuple[float, float]] = {
    "nashik":      (19.9975, 73.7898),
    "pune":        (18.5204, 73.8567),
    "nagpur":      (21.1458, 79.0882),
    "amravati":    (20.9374, 77.7796),
    "kolhapur":    (16.7050, 74.2433),
    "aurangabad":  (19.8762, 75.3433),
    "indore":      (22.7196, 75.8577),
    "bhopal":      (23.2599, 77.4126),
    "jaipur":      (26.9124, 75.7873),
    "lucknow":     (26.8467, 80.9462),
    "chandigarh":  (30.7333, 76.7794),
    "ahmedabad":   (23.0225, 72.5714),
    "bengaluru":   (12.9716, 77.5946),
    "hyderabad":   (17.3850, 78.4867),
    "default":     (20.5937, 78.9629),   # India center
}

# Seasonal weather profiles per month (temperature ranges °C, humidity %)
MONTHLY_PROFILE: dict[int, dict] = {
    1:  {"tmax": 28, "tmin": 12, "hum": 55, "rain_prob": 0.05},
    2:  {"tmax": 32, "tmin": 15, "hum": 45, "rain_prob": 0.05},
    3:  {"tmax": 37, "tmin": 19, "hum": 35, "rain_prob": 0.08},
    4:  {"tmax": 41, "tmin": 23, "hum": 30, "rain_prob": 0.10},
    5:  {"tmax": 43, "tmin": 26, "hum": 35, "rain_prob": 0.15},
    6:  {"tmax": 35, "tmin": 25, "hum": 75, "rain_prob": 0.55},
    7:  {"tmax": 32, "tmin": 24, "hum": 85, "rain_prob": 0.70},
    8:  {"tmax": 31, "tmin": 23, "hum": 88, "rain_prob": 0.65},
    9:  {"tmax": 32, "tmin": 23, "hum": 78, "rain_prob": 0.45},
    10: {"tmax": 33, "tmin": 20, "hum": 65, "rain_prob": 0.20},
    11: {"tmax": 30, "tmin": 15, "hum": 55, "rain_prob": 0.08},
    12: {"tmax": 27, "tmin": 11, "hum": 50, "rain_prob": 0.05},
}


def _deterministic_seed(district: str, d: date) -> float:
    """Generate a repeatable pseudo-random value in [0,1] for a district+date pair."""
    key = f"{district}:{d.isoformat()}"
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    return (h % 10000) / 10000.0


def _mock_weather_forecast(district: str, days: int = 7) -> WeatherForecast:
    """
    Generate a deterministic mock 7-day forecast for a given district.
    Uses monthly seasonal profiles + a small pseudo-random variation.
    """
    district = district.lower().strip()
    today = date.today()
    profile = MONTHLY_PROFILE[today.month]

    day_entries: List[WeatherDay] = []
    rain_day_count = 0

    for i in range(days):
        d = today + timedelta(days=i)
        seed = _deterministic_seed(district, d)
        variation = (seed - 0.5) * 6          # ±3 °C variation

        tmax = round(profile["tmax"] + variation, 1)
        tmin = round(profile["tmin"] + variation * 0.6, 1)
        humidity = round(profile["hum"] + (seed - 0.5) * 20, 1)
        humidity = max(20.0, min(100.0, humidity))

        is_rain = seed < profile["rain_prob"]
        rainfall = round(seed * 25, 1) if is_rain else 0.0
        if is_rain:
            rain_day_count += 1

        if is_rain:
            condition = "rain"
        elif humidity > 70:
            condition = "cloudy"
        else:
            condition = "sunny"

        day_entries.append(WeatherDay(
            date=d.isoformat(),
            temp_max_c=tmax,
            temp_min_c=tmin,
            humidity_pct=humidity,
            rainfall_mm=rainfall,
            condition=condition,
        ))

    avg_temp = round(sum(d.temp_max_c for d in day_entries) / days, 1)
    avg_hum  = round(sum(d.humidity_pct for d in day_entries) / days, 1)

    return WeatherForecast(
        location=district.title(),
        days=day_entries,
        avg_temp=avg_temp,
        avg_humidity=avg_hum,
        rain_days=rain_day_count,
    )


async def get_weather_forecast(district: str, days: int = 7) -> WeatherForecast:
    """
    Public entry point.  Calls the real API if configured, else uses mock.

    To enable real weather:
        export USE_REAL_WEATHER=true
        export OWM_API_KEY=your_key_here
    """
    if USE_REAL_API and OWM_API_KEY:
        return await _fetch_openweather(district, days)
    return _mock_weather_forecast(district, days)


async def _fetch_openweather(district: str, days: int) -> WeatherForecast:
    """
    ── REAL API PLACEHOLDER ──
    Replace this implementation once an OWM key is available.

    import httpx
    lat, lon = DISTRICT_COORDS.get(district.lower(), DISTRICT_COORDS["default"])
    url = (
        f"https://api.openweathermap.org/data/3.0/onecall"
        f"?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts"
        f"&appid={OWM_API_KEY}&units=metric"
    )
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10)
        r.raise_for_status()
        raw = r.json()
    # Parse raw["daily"] → List[WeatherDay] and return WeatherForecast(...)
    """
    raise NotImplementedError("Real weather API not yet wired up.")
