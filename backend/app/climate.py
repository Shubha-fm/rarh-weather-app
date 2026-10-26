"""Turns monthly station normals into smooth daily climate curves.

These curves are the training targets for the neural network in ml.py.
"""

import numpy as np

from .data import STATIONS

DAYS_IN_MONTH = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], dtype=float)

# Day of year at the middle of each month, repeated one year before and after so curves wrap around.
_MID = np.cumsum(DAYS_IN_MONTH) - DAYS_IN_MONTH / 2 + 0.5
_XS = np.concatenate([_MID - 365, _MID, _MID + 365])


def _catmull_rom(p0, p1, p2, p3, t):
    return 0.5 * (
        2 * p1
        + (-p0 + p2) * t
        + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t**2
        + (-p0 + 3 * p1 - 3 * p2 + p3) * t**3
    )


def seasonal(monthly_values, day_of_year):
    """Smooth, year-periodic interpolation of 12 monthly values at any day of the year (1 to 365)."""
    ys = np.tile(np.asarray(monthly_values, dtype=float), 3)
    d = np.asarray(day_of_year, dtype=float)
    j = np.clip(np.searchsorted(_XS, d, side="right") - 1, 1, len(_XS) - 3)
    t = (d - _XS[j]) / (_XS[j + 1] - _XS[j])
    return _catmull_rom(ys[j - 1], ys[j], ys[j + 1], ys[j + 2], t)


def station_targets(station, day_of_year):
    """Daily climate for one station.

    Returns an array of shape (n_days, 5) with columns:
    max temperature C, min temperature C, relative humidity %, rain mm/day, chance of a rainy day (0 to 1).
    """
    d = np.atleast_1d(np.asarray(day_of_year, dtype=float))
    rate = np.maximum(0.0, seasonal(np.asarray(station["rain_mm"]) / DAYS_IN_MONTH, d))
    chance = np.clip(0.03 + rate * 30 / 430, 0.02, 0.8)
    return np.column_stack(
        [seasonal(station["tmax_c"], d), seasonal(station["tmin_c"], d), seasonal(station["rh_pct"], d), rate, chance]
    )


def features(latitude, longitude, day_of_year):
    """Model inputs: scaled position plus the time of year as two sine/cosine pairs."""
    d = np.atleast_1d(np.asarray(day_of_year, dtype=float))
    a = 2 * np.pi * d / 365
    lat = np.full_like(d, latitude)
    lon = np.full_like(d, longitude)
    return np.column_stack([(lat - 23.5) / 1.5, (lon - 86.5) / 1.8, np.sin(a), np.cos(a), np.sin(2 * a), np.cos(2 * a)])


def build_dataset(exclude_station_id=None):
    """Training rows (every 4th day from day 1) and validation rows (every 4th day from day 3) for all stations."""
    xs_train, ys_train, xs_val, ys_val = [], [], [], []
    days = np.arange(1, 366, 2)
    train_mask = days % 4 == 1
    for s in STATIONS:
        if s["id"] == exclude_station_id:
            continue
        x = features(s["latitude"], s["longitude"], days)
        y = station_targets(s, days)
        xs_train.append(x[train_mask])
        ys_train.append(y[train_mask])
        xs_val.append(x[~train_mask])
        ys_val.append(y[~train_mask])
    return np.vstack(xs_train), np.vstack(ys_train), np.vstack(xs_val), np.vstack(ys_val)
