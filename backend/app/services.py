"""Turns raw model output into the answer the API returns."""

import math
from datetime import date

import numpy as np

from .data import STATIONS

SEASONS = ["basanta", "grishma", "barsha", "sharat", "hemanta", "sheet"]


def day_of_year(d: date) -> int:
    """Day of the year from 1 to 365 (29 February and 31 December of a leap year share the nearest day)."""
    return min(365, d.timetuple().tm_yday)


def season_index(doy: int) -> int:
    """The six traditional Bengali seasons, each about two months long."""
    if 46 <= doy < 105:
        return 0
    if 105 <= doy < 166:
        return 1
    if 166 <= doy < 227:
        return 2
    if 227 <= doy < 288:
        return 3
    if 288 <= doy < 349:
        return 4
    return 5


def condition(tmax, tmin, rh, rain, chance) -> str:
    if chance >= 0.6 and rain >= 8:
        return "heavy_rain"
    if chance >= 0.45:
        return "rain_likely"
    if chance >= 0.2:
        return "showers"
    if tmax >= 37:
        return "hot_dry"
    if tmax >= 32 and rh >= 70:
        return "hot_humid"
    if tmax < 27:
        return "cool_dry"
    return "mostly_clear"


ADVICE = {
    "heavy_rain": ["drain_fields", "delay_harvest", "no_spray"],
    "rain_likely": ["no_spray", "cover_harvest"],
    "showers": ["no_spray"],
    "hot_dry": ["irrigate_evening", "mulch"],
    "hot_humid": ["watch_pests", "irrigate_evening"],
    "cool_dry": ["good_field_work"],
    "mostly_clear": ["good_field_work"],
}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = math.pi / 180
    dlat, dlon = (lat2 - lat1) * r, (lon2 - lon1) * r
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def nearest_station(latitude, longitude):
    best = min(STATIONS, key=lambda s: haversine_km(latitude, longitude, s["latitude"], s["longitude"]))
    return best, haversine_km(latitude, longitude, best["latitude"], best["longitude"])


def confidence(latitude, longitude, distance_km) -> str:
    """High near a reference station, low far from all of them or outside the area they cover."""
    lats = [s["latitude"] for s in STATIONS]
    lons = [s["longitude"] for s in STATIONS]
    outside = (
        latitude < min(lats) - 0.6
        or latitude > max(lats) + 0.6
        or longitude < min(lons) - 0.6
        or longitude > max(lons) + 0.6
    )
    if outside or distance_km > 150:
        return "low"
    return "medium" if distance_km > 70 else "high"


def public_station(s):
    return {"id": s["id"], "name": s["name"], "latitude": s["latitude"], "longitude": s["longitude"]}


def forecast(model, latitude, longitude, on_date: date) -> dict:
    doy = day_of_year(on_date)
    today = {k: float(v[0]) for k, v in model.predict(latitude, longitude, [doy]).items()}

    days = np.concatenate([np.arange(1, 366, 4), [365]])
    year = model.predict(latitude, longitude, days)
    yearly = [
        {"day": int(d), "temp_max_c": round(float(a), 1), "temp_min_c": round(float(b), 1)}
        for d, a, b in zip(days, year["tmax"], year["tmin"])
    ]

    station, km = nearest_station(latitude, longitude)
    si = season_index(doy)
    cond = condition(today["tmax"], today["tmin"], today["rh"], today["rain"], today["chance"])
    return {
        "location": {"latitude": latitude, "longitude": longitude},
        "date": on_date.isoformat(),
        "day_of_year": doy,
        "prediction": {
            "temp_max_c": round(today["tmax"], 1),
            "temp_min_c": round(today["tmin"], 1),
            "humidity_pct": round(today["rh"], 1),
            "rain_probability": round(today["chance"], 2),
            "rain_mm_per_day": round(today["rain"], 1),
        },
        "condition": cond,
        "advice": ADVICE[cond],
        "season": {"index": si, "key": SEASONS[si]},
        "nearest_station": {"id": station["id"], "name": station["name"], "distance_km": round(km, 1)},
        "confidence": confidence(latitude, longitude, km),
        "yearly": yearly,
        "model": {"type": model.meta.get("type"), "validation_mae_c": model.meta.get("validation_mae_c")},
    }
