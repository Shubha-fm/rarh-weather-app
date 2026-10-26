"""Small input checks shared by the API routes."""

import math
from datetime import date

from .errors import ApiError


def number(raw, field):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ApiError(422, "invalid_number", f"{field} must be a number.", field)
    if not math.isfinite(value):
        raise ApiError(422, "invalid_number", f"{field} must be a finite number.", field)
    return value


def iso_date(raw, field="date"):
    """Parse YYYY-MM-DD. A missing value means today."""
    if raw in (None, ""):
        return date.today()
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        raise ApiError(422, "invalid_date", f"{field} must look like 2026-10-18.", field)
