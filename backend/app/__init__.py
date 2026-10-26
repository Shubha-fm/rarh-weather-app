"""Rarh Weather backend: a Flask app with farmer accounts, weather predictions from a trained model, and market prices."""

import os
import secrets

from flask import Flask, jsonify

from . import auth, prices
from .api import bp as api_bp
from .db import close_db, init_db
from .errors import ApiError
from .ml import WeatherModel

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL_PATH = os.path.join(BACKEND_DIR, "models", "model.joblib")
DEFAULT_DATABASE = os.path.join(BACKEND_DIR, "data", "rarh.db")


def _secret_key(path):
    """Use SECRET_KEY from the environment. Otherwise make one and keep it in a file so logins survive a restart."""
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    key = secrets.token_hex(32)
    with open(path, "w") as f:
        f.write(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def create_app(config=None):
    app = Flask(__name__)
    database = os.environ.get("DATABASE", DEFAULT_DATABASE)
    app.config.update(
        MODEL_PATH=os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH),
        DATABASE=database,
        # Which web pages may call this API from a browser. "*" allows any page; set your site's address in production.
        CORS_ORIGINS=os.environ.get("CORS_ORIGINS", "*"),
        # Optional free key from data.gov.in. With it, market prices come from the official daily mandi data.
        DATA_GOV_API_KEY=os.environ.get("DATA_GOV_API_KEY", ""),
        TOKEN_MAX_AGE=7 * 24 * 3600,  # a login lasts 7 days
        LAT_RANGE=(20.0, 27.0),
        LON_RANGE=(82.0, 90.0),
    )
    if config:
        app.config.update(config)
    if not app.config.get("SECRET_KEY"):  # Flask defines SECRET_KEY as None, so check the value, not the name
        app.config["SECRET_KEY"] = _secret_key(os.path.join(os.path.dirname(app.config["DATABASE"]), "secret.key"))

    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)
    app.extensions["login_attempts"] = {}
    app.extensions["weather_model"] = WeatherModel.load_or_train(app.config["MODEL_PATH"])

    app.register_blueprint(api_bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(prices.bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify(err.body()), err.status

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = app.config["CORS_ORIGINS"]
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": {"code": "not_found", "message": "No such endpoint. See /api/v1/."}}), 404

    @app.errorhandler(405)
    def not_allowed(_):
        return jsonify({"error": {"code": "method_not_allowed", "message": "This method is not allowed here."}}), 405

    @app.errorhandler(500)
    def server_error(_):
        return jsonify({"error": {"code": "server_error", "message": "The server hit an unexpected error."}}), 500

    return app
