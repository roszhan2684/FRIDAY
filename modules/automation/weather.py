"""Weather fetching via wttr.in (free, no auth, works offline-ish with cache).

Falls back gracefully when offline.
Caches last fetch in SQLite preferences for use when offline.
"""
from __future__ import annotations
import json
import logging
import httpx
from datetime import datetime

from database import db

logger = logging.getLogger(__name__)

WTTR_URL = "https://wttr.in/{location}?format=j1"
CACHE_KEY = "weather_cache"
CACHE_MAX_AGE_MINUTES = 30


def _get_location() -> str:
    loc = db.fetchone("SELECT value FROM preferences WHERE key='weather_location'")
    location = loc["value"] if loc else "Fullerton, CA"
    # wttr.in uses URL encoding — replace spaces with +
    return location.replace(" ", "+") if location and location != "auto" else ""


def get_current_weather() -> dict | None:
    """
    Fetch current weather from wttr.in.
    Returns: {temp_f, temp_c, condition, feels_like_f, humidity, city}
    Falls back to cached data if unavailable.
    """
    # Check cache freshness
    cached = db.fetchone(f"SELECT value, updated_at FROM preferences WHERE key='{CACHE_KEY}'")
    if cached:
        try:
            cache_data = json.loads(cached["value"])
            cached_at = datetime.fromisoformat(cached["updated_at"])
            age_minutes = (datetime.now() - cached_at).total_seconds() / 60
            if age_minutes < CACHE_MAX_AGE_MINUTES:
                return cache_data
        except Exception:
            pass

    location = _get_location()
    try:
        url = WTTR_URL.format(location=location)
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()

        current = data["current_condition"][0]
        nearest_area = data.get("nearest_area", [{}])[0]
        city = nearest_area.get("areaName", [{}])[0].get("value", "your area")

        weather = {
            "temp_f": int(current["temp_F"]),
            "temp_c": int(current["temp_C"]),
            "condition": current["weatherDesc"][0]["value"],
            "feels_like_f": int(current["FeelsLikeF"]),
            "humidity": int(current["humidity"]),
            "city": city,
            "fetched_at": datetime.now().isoformat(),
        }

        # Cache it
        db.execute(
            "INSERT INTO preferences(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
            (CACHE_KEY, json.dumps(weather)),
        )
        return weather

    except httpx.TimeoutException:
        logger.warning("Weather fetch timed out — using cached data")
    except Exception as exc:
        logger.warning("Weather fetch failed: %s — using cached data", exc)

    # Return cached even if stale
    if cached:
        try:
            return json.loads(cached["value"])
        except Exception:
            pass
    return None


def format_weather_naturally(weather: dict) -> str:
    """Format weather for spoken briefing."""
    temp = weather.get("temp_f")
    condition = weather.get("condition", "").lower()
    city = weather.get("city", "your area")

    condition_spoken = {
        "sunny": "sunny", "clear": "clear", "partly cloudy": "partly cloudy",
        "cloudy": "cloudy", "overcast": "overcast",
        "light rain": "lightly raining", "rain": "raining",
        "heavy rain": "raining heavily", "thunderstorm": "stormy",
        "snow": "snowing", "fog": "foggy", "mist": "misty",
    }.get(condition.lower(), condition)

    return f"In {city} it's {temp} degrees and {condition_spoken}"
