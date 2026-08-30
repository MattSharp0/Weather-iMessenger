import httpx

from app.config import config

NWS_BASE = "https://api.weather.gov"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_forecast(lat: float, lon: float) -> str:
    nws_result = _try_nws(lat, lon)
    if nws_result is not None:
        return nws_result
    return _open_meteo(lat, lon)


def _try_nws(lat: float, lon: float) -> str | None:
    headers = {"User-Agent": f"Weather-Messenger ({config.nws_contact})"}
    with httpx.Client(headers=headers, timeout=15) as client:
        points = client.get(f"{NWS_BASE}/points/{lat},{lon}")
        if points.status_code != 200:
            return None
        points_data = points.json()["properties"]

        forecast = client.get(points_data["forecast"])
        forecast.raise_for_status()
        period = forecast.json()["properties"]["periods"][0]
        # TODO: let the incoming text specify timing (now/later/tomorrow) to pick
        # a different period instead of always the immediate one.
        summary = f"{period['name']}: {period['detailedForecast']}"

        alerts_resp = client.get(
            f"{NWS_BASE}/alerts/active", params={"point": f"{lat},{lon}"}
        )
        alerts_resp.raise_for_status()
        alerts = alerts_resp.json()["features"]
        alert_prefix = ""
        if alerts:
            headline = alerts[0]["properties"].get("headline", "Active alert")
            alert_prefix = f"⚠️ {headline}. "

        return _truncate(alert_prefix + summary)


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
