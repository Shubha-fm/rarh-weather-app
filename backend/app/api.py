"""Weather and model routes, version 1. Everything lives under /api/v1.

Public:     GET /health, GET /stations, GET /model
Logged in:  GET or POST /predict   (see auth.py for login, prices.py for market prices)
"""

from flask import Blueprint, current_app, jsonify, request

from .auth import require_auth
from .data import STATIONS
from .errors import ApiError
from .services import forecast, public_station
from .validation import iso_date, number

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def _parse_request():
    """Read latitude, longitude and optional date from a JSON body (POST) or query string (GET)."""
    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ApiError(400, "invalid_json", "Send a JSON object with latitude, longitude and optional date.")
    else:
        data = request.args

    lat_min, lat_max = current_app.config["LAT_RANGE"]
    lon_min, lon_max = current_app.config["LON_RANGE"]

    latitude = number(data.get("latitude"), "latitude")
    longitude = number(data.get("longitude"), "longitude")
    if not lat_min <= latitude <= lat_max:
        raise ApiError(422, "out_of_range", f"latitude must be between {lat_min} and {lat_max}.", "latitude")
    if not lon_min <= longitude <= lon_max:
        raise ApiError(422, "out_of_range", f"longitude must be between {lon_min} and {lon_max}.", "longitude")
    return latitude, longitude, iso_date(data.get("date"))


@bp.get("/")
def index():
    return jsonify(
        {
            "name": "Rarh Weather API",
            "version": "v1",
            "endpoints": {
                "health": "GET /api/v1/health",
                "stations": "GET /api/v1/stations",
                "model": "GET /api/v1/model",
                "register": "POST /api/v1/auth/register  {name, phone, password}",
                "login": "POST /api/v1/auth/login  {user_id, password}",
                "me": "GET /api/v1/auth/me  (login required)",
                "predict": "POST /api/v1/predict  or  GET /api/v1/predict?latitude=..&longitude=..&date=YYYY-MM-DD  (login required)",
                "markets": "GET /api/v1/markets  (login required)",
                "prices": "GET /api/v1/prices?market=ranchi&date=YYYY-MM-DD  (login required)",
            },
        }
    )


@bp.get("/health")
def health():
    ready = current_app.extensions.get("weather_model") is not None
    return jsonify({"status": "ok" if ready else "starting", "model_ready": ready})


@bp.get("/stations")
def stations():
    return jsonify({"stations": [public_station(s) for s in STATIONS]})


@bp.get("/model")
def model_info():
    return jsonify(current_app.extensions["weather_model"].meta)


@bp.route("/predict", methods=["GET", "POST"])
@require_auth
def predict():
    latitude, longitude, on_date = _parse_request()
    model = current_app.extensions["weather_model"]
    return jsonify(forecast(model, latitude, longitude, on_date))
