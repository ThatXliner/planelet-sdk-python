"""
Open-Meteo Weather planelet — demonstrates actions.

Usage:
  python examples/weather.py

Requires: pip install httpx
"""

from __future__ import annotations

import os

import httpx

from planelet_sdk import (
    ActionContext,
    Param,
    ParamOption,
    create_planelet,
)

WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
}


def weather_description(code: int | None) -> str:
    if code is None:
        return "Unknown conditions"
    return WEATHER_CODES.get(code, f"WMO weather code {code}")


planelet = create_planelet(
    id="weather",
    label="Open-Meteo Weather",
    icon="cloud-sun",
    description="Weather forecast planelet powered by Open-Meteo.",
)


@planelet.action(
    "weather-briefing",
    label="Weather Briefing",
    icon="cloud-sun",
    description="Fetches an Open-Meteo forecast summary for a location.",
    parameters={
        "locationLabel": Param(
            label="Location Label",
            type="string",
            required=True,
            default="San Francisco",
        ),
        "latitude": Param(label="Latitude", type="number", required=True, default=37.7749),
        "longitude": Param(label="Longitude", type="number", required=True, default=-122.4194),
        "forecastDays": Param(label="Forecast Days", type="number", default=3),
        "temperatureUnit": Param(
            label="Temperature Unit",
            type="select",
            default="fahrenheit",
            options=[
                ParamOption(label="Fahrenheit", value="fahrenheit"),
                ParamOption(label="Celsius", value="celsius"),
            ],
        ),
    },
)
async def weather_briefing(ctx: ActionContext) -> dict:
    p = ctx.parameters
    label = str(p.get("locationLabel", "San Francisco"))
    lat = float(p.get("latitude", 37.7749))
    lon = float(p.get("longitude", -122.4194))
    days = max(1, min(7, int(p.get("forecastDays", 3))))
    temp_unit = p.get("temperatureUnit", "fahrenheit")

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}&timezone=auto&forecast_days={days}"
        f"&temperature_unit={temp_unit}"
        f"&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        forecast = resp.json()

    current = forecast.get("current", {})
    current_temp = current.get("temperature_2m")
    conditions = weather_description(current.get("weather_code"))

    daily_times = forecast.get("daily", {}).get("time", [])
    daily_highs = forecast.get("daily", {}).get("temperature_2m_max", [])
    daily_lows = forecast.get("daily", {}).get("temperature_2m_min", [])
    daily_precip = forecast.get("daily", {}).get("precipitation_probability_max", [])
    daily_codes = forecast.get("daily", {}).get("weather_code", [])

    daily = [
        {
            "date": daily_times[i],
            "high": daily_highs[i] if i < len(daily_highs) else None,
            "low": daily_lows[i] if i < len(daily_lows) else None,
            "precipitationProbability": daily_precip[i] if i < len(daily_precip) else None,
            "conditions": weather_description(daily_codes[i] if i < len(daily_codes) else None),
        }
        for i in range(len(daily_times))
    ]

    unit_label = forecast.get("current_units", {}).get("temperature_2m", temp_unit)
    today = daily[0] if daily else {}

    return {
        "source": "open-meteo",
        "location": {"label": label, "latitude": lat, "longitude": lon},
        "current": {
            "temperature": current_temp,
            "temperatureUnit": unit_label,
            "conditions": conditions,
        },
        "daily": daily,
        "summary": (
            f"{label}: {current_temp}{unit_label} and {conditions.lower()} now. "
            f"Today's range is {today.get('low')}-{today.get('high')}{unit_label}."
        ),
    }


planelet.listen(int(os.environ.get("PORT", "3011")))
