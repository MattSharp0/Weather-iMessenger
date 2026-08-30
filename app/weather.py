import re
from datetime import datetime, timedelta

import httpx

from app.config import config

NWS_BASE = "https://api.weather.gov"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_forecast(lat: float, lon: float, option: str = "default") -> str:
    # The forecast option (forecast/tonight/tomorrow) only applies to NWS —
    # Open-Meteo's response shape isn't set up to support it, so a fallback
    # to Open-Meteo just returns its normal current-conditions summary.
    nws_result = _try_nws(lat, lon, option)
    if nws_result is not None:
        return nws_result
    return _open_meteo(lat, lon)


def _try_nws(lat: float, lon: float, option: str) -> str | None:
    headers = {"User-Agent": f"Weather-Messenger ({config.nws_contact})"}
    with httpx.Client(headers=headers, timeout=15) as client:
        points = client.get(f"{NWS_BASE}/points/{lat},{lon}")
        if points.status_code != 200:
            return None
        points_data = points.json()["properties"]

        forecast = client.get(points_data["forecast"])
        forecast.raise_for_status()
        periods = forecast.json()["properties"]["periods"]

        alerts_resp = client.get(
            f"{NWS_BASE}/alerts/active", params={"point": f"{lat},{lon}"}
        )
        alerts_resp.raise_for_status()
        alerts = alerts_resp.json()["features"]
        alert_prefix = ""
        if alerts:
            headline = alerts[0]["properties"].get("headline", "Active alert")
            alert_prefix = f"⚠️ {headline}. "

        if option == "forecast":
            combined = alert_prefix + _period_summary(periods[:3])
            return _truncate(combined)

        period = _select_period(periods, option)
        combined = alert_prefix + f"{period['name']}: {_shorten(period['detailedForecast'])}"
        if len(combined) <= 300:
            return combined

        # detailedForecast (plus any alert) didn't fit — fall back to the
        # short compiled form for that period rather than splitting into
        # multiple messages.
        short = alert_prefix + _period_line(period)
        return _truncate(short)


def _select_period(periods: list[dict], option: str) -> dict:
    if option == "tonight":
        for p in periods:
            if not p["isDaytime"] and p["name"].strip().lower() == "tonight":
                return p
        for p in periods:
            if not p["isDaytime"]:
                return p
        return periods[0]

    if option == "tomorrow":
        now = datetime.fromisoformat(periods[0]["startTime"])
        tomorrow = (now + timedelta(days=1)).date()
        for p in periods:
            if p["isDaytime"] and datetime.fromisoformat(p["startTime"]).date() == tomorrow:
                return p
        daytimes = [p for p in periods if p["isDaytime"]]
        return daytimes[1] if len(daytimes) > 1 else periods[0]

    return periods[0]


def _period_line(period: dict) -> str:
    precip = (period.get("probabilityOfPrecipitation") or {}).get("value") or 0
    return (
        f"{period['name']}: {_shorten(period['shortForecast'])}, {period['temperature']}°, "
        f"Rain {precip}%, Wind {period['windDirection']} {period['windSpeed']}"
    )


def _period_summary(periods: list[dict]) -> str:
    return " | ".join(_period_line(p) for p in periods)


def _shorten(text: str) -> str:
    return re.sub(r"(?i)\band\b", "&", text)


def _open_meteo(lat: float, lon: float) -> str:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "auto",
        "forecast_days": 2,
    }
    response = httpx.get(OPEN_METEO_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    current = data["current"]
    daily = data["daily"]
    summary = (
        f"Now: {current['temperature_2m']}°F, wind {current['wind_speed_10m']}mph. "
        f"Today: high {daily['temperature_2m_max'][0]}°F / low {daily['temperature_2m_min'][0]}°F, "
        f"{daily['precipitation_probability_max'][0]}% precip."
    )
    return _truncate(summary)


def _truncate(text: str, limit: int = 300) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
