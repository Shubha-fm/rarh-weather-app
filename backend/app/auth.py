"""Farmer registration and login.

Flow:
  1. POST /auth/register  with name, phone, password  ->  the server makes a unique user ID (for example RF482915).
  2. POST /auth/login     with user ID and password   ->  a signed token, valid for 7 days.
  3. The app sends the token as  Authorization: Bearer <token>  on every protected call.
"""

import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .errors import ApiError

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

MAX_FAILED_LOGINS = 5
LOCK_SECONDS = 300
_DUMMY_HASH = generate_password_hash("not-a-real-password")  # keeps timing equal when the user ID does not exist


# ---------- input checks ----------

def clean_name(raw):
    name = " ".join(str(raw or "").split())
    if not 2 <= len(name) <= 60 or not any(ch.isalpha() for ch in name) or re.search(r"[<>]", name):
        raise ApiError(422, "invalid_name", "Enter your name (2 to 60 letters).", "name")
    return name


def clean_phone(raw):
    digits = re.sub(r"[\s\-]", "", str(raw or ""))
    if digits.startswith("+91"):
        digits = digits[3:]
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ApiError(422, "invalid_phone", "Enter a valid 10-digit mobile number.", "phone")
    return digits


def clean_password(raw):
    password = raw if isinstance(raw, str) else ""
    if not 6 <= len(password) <= 128:
        raise ApiError(422, "invalid_password", "Password must have 6 to 128 characters.", "password")
    return password


def normalise_user_id(raw):
    return re.sub(r"[\s\-]", "", str(raw or "")).upper()


def public_user(row):
    return {"user_id": row["user_id"], "name": row["name"], "phone_hint": "******" + row["phone"][-4:]}


# ---------- tokens ----------

def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="rarh-weather-auth")


def make_token(user_id):
    return _serializer().dumps({"uid": user_id})


def require_auth(view):
    """Protect a route. Puts the logged-in user in g.user."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError(401, "unauthorized", "Log in first.")
        try:
            data = _serializer().loads(header[7:].strip(), max_age=current_app.config["TOKEN_MAX_AGE"])
        except SignatureExpired:
            raise ApiError(401, "token_expired", "Your session ended. Please log in again.")
        except BadSignature:
            raise ApiError(401, "unauthorized", "Log in first.")
        row = get_db().execute("SELECT * FROM users WHERE user_id = ?", (data.get("uid"),)).fetchone()
        if row is None:
            raise ApiError(401, "unauthorized", "Log in first.")
        g.user = row
        return view(*args, **kwargs)

    return wrapper


# ---------- routes ----------

def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "Send a JSON object.")
    return data


def _new_user_id(db):
    for _ in range(30):
        candidate = "RF" + str(100000 + secrets.randbelow(900000))
        if db.execute("SELECT 1 FROM users WHERE user_id = ?", (candidate,)).fetchone() is None:
            return candidate
    raise ApiError(500, "server_error", "Could not make a user ID. Try again.")


@bp.post("/register")
def register():
    data = _json_body()
    name = clean_name(data.get("name"))
    phone = clean_phone(data.get("phone"))
    password = clean_password(data.get("password"))

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE phone = ?", (phone,)).fetchone():
        raise ApiError(409, "phone_taken", "This phone number is already registered.", "phone")

    password_hash = generate_password_hash(password)
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for _ in range(5):  # a second request could take the same random ID a moment earlier: pick another
        user_id = _new_user_id(db)
        try:
            db.execute(
                "INSERT INTO users (user_id, name, phone, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, phone, password_hash, created),
            )
            db.commit()
            return jsonify({"user_id": user_id, "name": name}), 201
        except sqlite3.IntegrityError as exc:
            if "phone" in str(exc):
                raise ApiError(409, "phone_taken", "This phone number is already registered.", "phone")
    raise ApiError(500, "server_error", "Could not make a user ID. Try again.")


@bp.post("/login")
def login():
    data = _json_body()
    user_id = normalise_user_id(data.get("user_id"))
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    if not user_id:
        raise ApiError(422, "invalid_user_id", "Enter your user ID.", "user_id")

    attempts = current_app.extensions["login_attempts"]
    now = time.time()
    state = attempts.get(user_id, {"fails": 0, "locked_until": 0.0})
    if state["locked_until"] > now:
        raise ApiError(
            429, "too_many_attempts", "Too many wrong attempts. Try again in a few minutes.",
            retry_after=int(state["locked_until"] - now) + 1,
        )

    row = get_db().execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password)
    if not (row and ok):
        state["fails"] += 1
        if state["fails"] >= MAX_FAILED_LOGINS:
            state = {"fails": 0, "locked_until": now + LOCK_SECONDS}
        if len(attempts) > 10000:  # keep memory bounded
            attempts.clear()
        attempts[user_id] = state
        raise ApiError(401, "wrong_credentials", "User ID or password is wrong.")

    attempts.pop(user_id, None)
    return jsonify(
        {"token": make_token(user_id), "expires_in": current_app.config["TOKEN_MAX_AGE"], "user": public_user(row)}
    )


@bp.get("/me")
@require_auth
def me():
    return jsonify({"user": public_user(g.user)})
