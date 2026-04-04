"""
Tool functions for the Travel Assistant.

These are registered with Gemini as callable tools. The SDK automatically
invokes them when the model decides they are needed and feeds the results
back into the response.

All APIs used here are free and require no API keys.
"""

import logging

import requests

logger = logging.getLogger(__name__)

_TIMEOUT = 10

_WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _geocode(city: str, country: str) -> dict | None:
    """Resolve a city/place name to lat/lon via Nominatim (OpenStreetMap)."""
    query = f"{city}, {country}" if country else city

    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": "TravelAssistantChatbot/1.0"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json()

    if not results:
        return None

    r = results[0]
    return {
        "name": r.get("name", city),
        "latitude": float(r["lat"]),
        "longitude": float(r["lon"]),
        "display_name": r.get("display_name", ""),
    }


def get_weather(city: str, country: str = "India") -> dict:
    """Get current weather for a city. Call this when the user asks about
    weather, or when planning a trip where weather info would be useful.

    Args:
        city: City name, e.g. "Paris", "Tokyo", "Goa", "Panaji".
        country: Country name to disambiguate, e.g. "India", "France".
                 Defaults to "India".

    Returns:
        Dict with temperature, description, humidity, and wind speed.
    """
    try:
        loc = _geocode(city, country)
        if not loc:
            return {"error": f"Could not find location '{city}'."}

        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "current": "temperature_2m,relative_humidity_2m,"
                           "apparent_temperature,weather_code,wind_speed_10m",
            },
            timeout=_TIMEOUT,
        )
        weather.raise_for_status()
        cur = weather.json()["current"]

        display = loc.get("display_name", city)
        return {
            "location": display,
            "temperature_celsius": cur["temperature_2m"],
            "feels_like_celsius": cur["apparent_temperature"],
            "description": _WEATHER_CODES.get(cur["weather_code"], "Unknown"),
            "humidity_percent": cur["relative_humidity_2m"],
            "wind_speed_kmh": cur["wind_speed_10m"],
        }
    except requests.RequestException as exc:
        logger.error("Weather API error for '%s': %s", city, exc)
        return {"error": f"Could not fetch weather for '{city}'."}


def get_currency_rate(
    from_currency: str, to_currency: str, amount: float = 1.0
) -> dict:
    """Convert an amount between currencies. Call this when the user asks
    about exchange rates or needs a budget converted to another currency.

    Args:
        from_currency: Source currency code, e.g. "USD", "EUR".
        to_currency: Target currency code, e.g. "INR", "THB".
        amount: The amount to convert. Defaults to 1.0.

    Returns:
        Dict with the converted amount and exchange rate.
    """
    base = from_currency.upper()
    target = to_currency.upper()

    try:
        resp = requests.get(
            f"https://open.er-api.com/v6/latest/{base}",
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") != "success":
            return {"error": f"Currency API returned an error for {base}."}

        rate = data["rates"].get(target)
        if rate is None:
            return {"error": f"Currency '{target}' is not supported."}

        converted = round(amount * rate, 2)
        return {
            "from_currency": base,
            "to_currency": target,
            "original_amount": amount,
            "converted_amount": converted,
            "exchange_rate": round(rate, 4),
        }
    except requests.RequestException as exc:
        logger.error("Currency API error (%s→%s): %s", base, target, exc)
        return {"error": f"Could not fetch exchange rate for {base} → {target}."}
