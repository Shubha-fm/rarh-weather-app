"""Weather prediction endpoints."""
from flask import Blueprint,current_app,jsonify,request
from .auth import require_auth
from .data import STATIONS
from .errors import ApiError
from .services import forecast,public_station
from .validation import iso_date,number
bp=Blueprint("api_v1",__name__,url_prefix="/api/v1")
def _parse_request():
 if request.method=="POST":
  data=request.get_json(silent=True)
  if not isinstance(data,dict):raise ApiError(400,"invalid_json","Send a JSON object with latitude, longitude and optional date.")
 else:data=request.args
 lat_min,lat_max=current_app.config["LAT_RANGE"];lon_min,lon_max=current_app.config["LON_RANGE"]
 latitude=number(data.get("latitude"),"latitude");longitude=number(data.get("longitude"),"longitude")
 if not lat_min<=latitude<=lat_max:raise ApiError(422,"out_of_range",f"latitude must be between {lat_min} and {lat_max}.","latitude")
 if not lon_min<=longitude<=lon_max:raise ApiError(422,"out_of_range",f"longitude must be between {lon_min} and {lon_max}.","longitude")
 return latitude,longitude,iso_date(data.get("date"))
@bp.get("/")
def index():
 return jsonify({"name":"Rarh Weather API","version":"v1","endpoints":{"health":"GET /api/v1/health","stations":"GET /api/v1/stations","model":"GET /api/v1/model","register":"POST /api/v1/auth/register","login":"POST /api/v1/auth/login","me":"GET /api/v1/auth/me","predict":"POST /api/v1/predict","markets":"GET /api/v1/markets","prices":"GET /api/v1/prices"}})
@bp.get("/health")
def health():
 ready=current_app.extensions.get("weather_model") is not None
 return jsonify({"status":"ok" if ready else "starting","model_ready":ready})
@bp.get("/stations")
def stations():return jsonify({"stations":[public_station(s) for s in STATIONS]})
@bp.get("/model")
def model_info():return jsonify(current_app.extensions["weather_model"].meta)
@bp.route("/predict",methods=["GET","POST"])
@require_auth
def predict():
 latitude,longitude,on_date=_parse_request()
 return jsonify(forecast(current_app.extensions["weather_model"],latitude,longitude,on_date))
