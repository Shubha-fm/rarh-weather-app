"""API tests. Run from the backend folder:  python -m unittest discover -s tests -v"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sklearn  # noqa: E402

from app import create_app, prices  # noqa: E402
from app.ml import WeatherModel  # noqa: E402

_TMP = None
_MODEL_PATH = None


def setUpModule():
    """Train the model once and share it between all tests."""
    global _TMP, _MODEL_PATH
    _TMP = tempfile.TemporaryDirectory()
    _MODEL_PATH = os.path.join(_TMP.name, "model.joblib")
    create_app({"MODEL_PATH": _MODEL_PATH, "DATABASE": os.path.join(_TMP.name, "seed.db"), "SECRET_KEY": "x"})


def tearDownModule():
    _TMP.cleanup()


class Base(unittest.TestCase):
    phone_counter = 0

    def setUp(self):
        self.app = create_app(
            {
                "MODEL_PATH": _MODEL_PATH,
                "DATABASE": os.path.join(_TMP.name, self.id() + ".db"),
                "SECRET_KEY": "test-secret",
                "TESTING": True,
            }
        )
        self.client = self.app.test_client()

    def register(self, name="Ramesh Mahato", phone="9876543210", password="secret123"):
        return self.client.post("/api/v1/auth/register", json={"name": name, "phone": phone, "password": password})

    def login_headers(self):
        user_id = self.register().get_json()["user_id"]
        token = self.client.post("/api/v1/auth/login", json={"user_id": user_id, "password": "secret123"}).get_json()["token"]
        return {"Authorization": "Bearer " + token}


class SecretKeyTests(unittest.TestCase):
    """The app must make its own signing key when none is given (this is how a real run starts)."""

    def _app(self, folder, env=None):
        with mock.patch.dict(os.environ, env or {}, clear=False):
            if not env or "SECRET_KEY" not in env:
                os.environ.pop("SECRET_KEY", None)
            return create_app({"MODEL_PATH": _MODEL_PATH, "DATABASE": os.path.join(folder, "rarh.db")})

    def _register_and_login(self, client):
        uid = client.post("/api/v1/auth/register", json={"name": "Ramesh Mahato", "phone": "9876543210", "password": "secret123"}).get_json()["user_id"]
        return client.post("/api/v1/auth/login", json={"user_id": uid, "password": "secret123"})

    def test_login_works_without_configured_key_and_key_is_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            app = self._app(folder)
            r = self._register_and_login(app.test_client())
            self.assertEqual(r.status_code, 200)
            token = r.get_json()["token"]
            key_file = os.path.join(folder, "secret.key")
            self.assertTrue(os.path.exists(key_file))
            # A restart (a new app on the same folder) reads the same key, so the old login still works.
            again = self._app(folder).test_client().get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
            self.assertEqual(again.status_code, 200)

    def test_secret_key_from_environment_is_used(self):
        with tempfile.TemporaryDirectory() as folder:
            app = self._app(folder, {"SECRET_KEY": "from-the-environment"})
            self.assertEqual(app.config["SECRET_KEY"], "from-the-environment")
            self.assertEqual(self._register_and_login(app.test_client()).status_code, 200)
            self.assertFalse(os.path.exists(os.path.join(folder, "secret.key")))


class HostingTests(Base):
    """The backend serves the web page, so one service can host the whole app."""

    def test_page_and_assets_are_served(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Rarh Weather", page.data)
        self.assertEqual(self.client.get("/css/styles.css").status_code, 200)
        self.assertEqual(self.client.get("/js/app.js").status_code, 200)
        self.assertIn(b"API_BASE", self.client.get("/js/config.js").data)

    def test_nothing_outside_the_page_folders_is_served(self):
        urls = [
            "/js/../../backend/run.py",
            "/js/%2e%2e/%2e%2e/backend/app/data.py",
            "/css/..%2f..%2fbackend%2frun.py",
            "/run.py",
            "/backend/app/data.py",
            "/data/rarh.db",
        ]
        for url in urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 404, url)
            self.assertNotIn(b"STATIONS", r.data, url)

    def test_api_still_wins_over_the_page(self):
        self.assertEqual(self.client.get("/api/v1/health").get_json()["status"], "ok")
        self.assertEqual(self.client.get("/api/v1/nothing").get_json()["error"]["code"], "not_found")

    def test_can_serve_api_only(self):
        app = create_app({"MODEL_PATH": _MODEL_PATH, "DATABASE": os.path.join(_TMP.name, "apionly.db"), "SECRET_KEY": "k", "SERVE_FRONTEND": False})
        self.assertEqual(app.test_client().get("/").status_code, 404)
        self.assertEqual(app.test_client().get("/api/v1/health").status_code, 200)


class ModelFileTests(unittest.TestCase):
    def test_model_from_another_scikit_learn_version_is_retrained(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "model.joblib")
            old = WeatherModel.load(_MODEL_PATH)
            old.meta = dict(old.meta, scikit_learn="0.0.1")
            old.save(path)
            fresh = WeatherModel.load_or_train(path)
            self.assertEqual(fresh.meta["scikit_learn"], sklearn.__version__)
            self.assertEqual(WeatherModel.load(path).meta["scikit_learn"], sklearn.__version__)  # the file was replaced

    def test_matching_version_is_loaded_as_is(self):
        first = WeatherModel.load_or_train(_MODEL_PATH)
        again = WeatherModel.load_or_train(_MODEL_PATH)
        self.assertEqual(first.meta["trained_at"], again.meta["trained_at"])

    def test_read_only_folder_still_gives_a_model(self):
        missing = os.path.join(tempfile.gettempdir(), "no-such-model-file.joblib")
        with mock.patch.object(WeatherModel, "save", side_effect=PermissionError("read-only")):
            model = WeatherModel.load_or_train(missing)
        self.assertGreater(model.predict(23.3, 85.3, [100])["tmax"][0], 20)


class PublicTests(Base):
    def test_health(self):
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["model_ready"])

    def test_stations_are_public_and_hide_raw_data(self):
        stations = self.client.get("/api/v1/stations").get_json()["stations"]
        self.assertEqual(len(stations), 17)
        self.assertEqual(set(stations[0]["name"]), {"en", "bn", "hi"})
        self.assertNotIn("tmax_c", stations[0])

    def test_model_info(self):
        meta = self.client.get("/api/v1/model").get_json()
        self.assertLess(meta["validation_mae_c"], 1.0)

    def test_unknown_route_is_json(self):
        r = self.client.get("/api/v1/nothing")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["error"]["code"], "not_found")

    def test_cors_headers(self):
        r = self.client.get("/api/v1/health")
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("Authorization", r.headers["Access-Control-Allow-Headers"])


class RegistrationTests(Base):
    def test_register_gives_unique_user_id(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        body = r.get_json()
        self.assertRegex(body["user_id"], r"^RF\d{6}$")
        self.assertEqual(body["name"], "Ramesh Mahato")
        second = self.register(phone="9876543211").get_json()["user_id"]
        self.assertNotEqual(body["user_id"], second)

    def test_password_is_not_stored_in_plain_text(self):
        self.register(password="secret123")
        import sqlite3

        conn = sqlite3.connect(self.app.config["DATABASE"])
        try:
            row = conn.execute("SELECT password_hash, phone FROM users").fetchone()
        finally:
            conn.close()
        self.assertNotIn("secret123", row[0])
        self.assertEqual(row[1], "9876543210")

    def test_phone_formats_are_normalised(self):
        for i, raw in enumerate(["+91 98765-43210", "09876543210", "919876543210"]):
            r = self.register(phone=raw, name=f"Farmer {i}")
            self.assertEqual(r.status_code if i == 0 else r.status_code, 201 if i == 0 else 409)

    def test_duplicate_phone(self):
        self.register()
        r = self.register(name="Someone Else")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["error"]["code"], "phone_taken")

    def test_validation(self):
        cases = [
            ({"name": "A", "phone": "9876543210", "password": "secret123"}, "invalid_name"),
            ({"name": "<b>x</b>", "phone": "9876543210", "password": "secret123"}, "invalid_name"),
            ({"name": "Ramesh", "phone": "12345", "password": "secret123"}, "invalid_phone"),
            ({"name": "Ramesh", "phone": "5876543210", "password": "secret123"}, "invalid_phone"),
            ({"name": "Ramesh", "phone": "9876543210", "password": "123"}, "invalid_password"),
            ({"name": "Ramesh", "phone": "9876543210"}, "invalid_password"),
        ]
        for body, code in cases:
            r = self.client.post("/api/v1/auth/register", json=body)
            self.assertEqual(r.status_code, 422, body)
            self.assertEqual(r.get_json()["error"]["code"], code, body)

    def test_bad_json(self):
        r = self.client.post("/api/v1/auth/register", data="nope", content_type="application/json")
        self.assertEqual(r.status_code, 400)


class LoginTests(Base):
    def test_login_success_and_me(self):
        user_id = self.register().get_json()["user_id"]
        r = self.client.post("/api/v1/auth/login", json={"user_id": user_id, "password": "secret123"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["user"]["name"], "Ramesh Mahato")
        self.assertEqual(body["user"]["phone_hint"], "******3210")
        me = self.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + body["token"]})
        self.assertEqual(me.get_json()["user"]["user_id"], user_id)

    def test_user_id_is_forgiving_about_case_and_spaces(self):
        user_id = self.register().get_json()["user_id"]
        typed = user_id.lower()[:2] + " " + user_id[2:]
        r = self.client.post("/api/v1/auth/login", json={"user_id": typed, "password": "secret123"})
        self.assertEqual(r.status_code, 200)

    def test_wrong_password_and_unknown_id_look_the_same(self):
        user_id = self.register().get_json()["user_id"]
        a = self.client.post("/api/v1/auth/login", json={"user_id": user_id, "password": "wrong-one"})
        b = self.client.post("/api/v1/auth/login", json={"user_id": "RF000000", "password": "wrong-one"})
        self.assertEqual(a.status_code, 401)
        self.assertEqual(a.get_json(), b.get_json())
        self.assertEqual(a.get_json()["error"]["code"], "wrong_credentials")

    def test_lockout_after_five_wrong_passwords(self):
        user_id = self.register().get_json()["user_id"]
        for _ in range(5):
            r = self.client.post("/api/v1/auth/login", json={"user_id": user_id, "password": "bad-guess"})
        self.assertEqual(r.status_code, 401)
        locked = self.client.post("/api/v1/auth/login", json={"user_id": user_id, "password": "secret123"})
        self.assertEqual(locked.status_code, 429)
        self.assertEqual(locked.get_json()["error"]["code"], "too_many_attempts")
        self.assertGreater(locked.get_json()["error"]["retry_after"], 0)

    def test_success_resets_failed_count(self):
        user_id = self.register().get_json()["user_id"]
        for _ in range(4):
            self.client.post("/api/v1/auth/login", json={"user_id": user_id, "password": "bad-guess"})
        ok = self.client.post("/api/v1/auth/login", json={"user_id": user_id, "password": "secret123"})
        self.assertEqual(ok.status_code, 200)
        again = self.client.post("/api/v1/auth/login", json={"user_id": user_id, "password": "bad-guess"})
        self.assertEqual(again.status_code, 401)

    def test_protected_routes_need_a_valid_token(self):
        for url in ["/api/v1/predict?latitude=23&longitude=85", "/api/v1/prices", "/api/v1/markets", "/api/v1/auth/me"]:
            self.assertEqual(self.client.get(url).status_code, 401, url)
            bad = self.client.get(url, headers={"Authorization": "Bearer not.a.token"})
            self.assertEqual(bad.status_code, 401, url)

    def test_expired_token(self):
        self.app.config["TOKEN_MAX_AGE"] = -1
        headers = self.login_headers()
        r = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error"]["code"], "token_expired")


class PredictTests(Base):
    def setUp(self):
        super().setUp()
        self.h = self.login_headers()

    def test_ranchi_october(self):
        r = self.client.post("/api/v1/predict", json={"latitude": 23.34, "longitude": 85.31, "date": "2026-10-18"}, headers=self.h)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        p = body["prediction"]
        self.assertTrue(26 <= p["temp_max_c"] <= 32)
        self.assertTrue(14 <= p["temp_min_c"] <= 21)
        self.assertEqual(body["season"]["key"], "hemanta")
        self.assertEqual(body["nearest_station"]["id"], "ranchi")
        self.assertEqual(body["confidence"], "high")
        self.assertGreater(len(body["yearly"]), 80)
        self.assertTrue(body["advice"])

    def test_get_matches_post_and_monsoon_advice(self):
        a = self.client.get("/api/v1/predict?latitude=22.57&longitude=88.36&date=2026-07-15", headers=self.h).get_json()
        b = self.client.post("/api/v1/predict", json={"latitude": 22.57, "longitude": 88.36, "date": "2026-07-15"}, headers=self.h).get_json()
        self.assertEqual(a["prediction"], b["prediction"])
        self.assertEqual(a["condition"], "heavy_rain")
        self.assertIn("drain_fields", a["advice"])

    def test_monsoon_wetter_than_winter(self):
        july = self.client.get("/api/v1/predict?latitude=23.2&longitude=87.1&date=2026-07-15", headers=self.h).get_json()["prediction"]
        jan = self.client.get("/api/v1/predict?latitude=23.2&longitude=87.1&date=2026-01-15", headers=self.h).get_json()["prediction"]
        self.assertGreater(july["rain_mm_per_day"], jan["rain_mm_per_day"] + 3)

    def test_far_from_stations_has_low_confidence(self):
        body = self.client.get("/api/v1/predict?latitude=20.2&longitude=82.2&date=2026-10-18", headers=self.h).get_json()
        self.assertEqual(body["confidence"], "low")

    def test_validation_errors(self):
        cases = [
            ("/api/v1/predict?latitude=abc&longitude=85", "invalid_number"),
            ("/api/v1/predict?longitude=85", "invalid_number"),
            ("/api/v1/predict?latitude=40&longitude=85", "out_of_range"),
            ("/api/v1/predict?latitude=23&longitude=120", "out_of_range"),
            ("/api/v1/predict?latitude=23&longitude=85&date=18-10-2026", "invalid_date"),
            ("/api/v1/predict?latitude=nan&longitude=85", "invalid_number"),
        ]
        for url, code in cases:
            r = self.client.get(url, headers=self.h)
            self.assertEqual(r.status_code, 422, url)
            self.assertEqual(r.get_json()["error"]["code"], code, url)


class PriceTests(Base):
    def setUp(self):
        super().setUp()
        self.h = self.login_headers()

    def test_markets(self):
        body = self.client.get("/api/v1/markets", headers=self.h).get_json()
        self.assertEqual(body["source"], "sample")
        self.assertEqual(len(body["markets"]), 8)
        self.assertEqual({m["state"] for m in body["markets"]}, {"West Bengal", "Jharkhand"})

    def test_sample_prices_shape(self):
        body = self.client.get("/api/v1/prices?market=ranchi&date=2026-10-18", headers=self.h).get_json()
        self.assertEqual(body["source"], "sample")
        self.assertEqual(body["unit"], "INR per quintal")
        self.assertEqual(len(body["items"]), 22)
        groups = {i["group"] for i in body["items"]}
        self.assertEqual(groups, {"vegetable", "crop"})
        for i in body["items"]:
            self.assertLess(i["min_price"], i["modal_price"], i["id"])
            self.assertLess(i["modal_price"], i["max_price"], i["id"])
            self.assertIsNotNone(i["change_pct"])
            self.assertEqual(set(i["name"]), {"en", "bn", "hi"})

    def test_same_day_same_prices_other_market_differs(self):
        url = "/api/v1/prices?market={}&date=2026-10-18"
        a = self.client.get(url.format("ranchi"), headers=self.h).get_json()["items"]
        b = self.client.get(url.format("ranchi"), headers=self.h).get_json()["items"]
        c = self.client.get(url.format("kolkata"), headers=self.h).get_json()["items"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_prices_follow_the_season(self):
        def modal(item_id, day):
            items = self.client.get(f"/api/v1/prices?market=ranchi&date={day}", headers=self.h).get_json()["items"]
            return next(i for i in items if i["id"] == item_id)["modal_price"]

        self.assertGreater(modal("tomato", "2026-07-15"), modal("tomato", "2026-01-15") * 1.5)

    def test_unknown_market_and_bad_date(self):
        r = self.client.get("/api/v1/prices?market=mars", headers=self.h)
        self.assertEqual((r.status_code, r.get_json()["error"]["code"]), (422, "unknown_market"))
        r = self.client.get("/api/v1/prices?market=ranchi&date=oops", headers=self.h)
        self.assertEqual(r.get_json()["error"]["code"], "invalid_date")


class LivePriceTests(Base):
    RECORDS = [
        {"State": "Jharkhand", "District": "Ranchi", "Market": "Ranchi", "Commodity": "Potato", "Variety": "Other",
         "Arrival_Date": "17/10/2026", "Min_Price": "1800", "Max_Price": "2200", "Modal_Price": "2000"},
        {"State": "Jharkhand", "District": "Ranchi", "Market": "Piska More", "Commodity": "Potato", "Variety": "Other",
         "Arrival_Date": "17/10/2026", "Min_Price": "1900", "Max_Price": "2300", "Modal_Price": "2100"},
        {"State": "Jharkhand", "District": "Ranchi", "Market": "Ranchi", "Commodity": "Potato", "Variety": "Other",
         "Arrival_Date": "10/10/2026", "Min_Price": "1", "Max_Price": "2", "Modal_Price": "1"},
        {"State": "Jharkhand", "District": "Ranchi", "Market": "Ranchi", "Commodity": "Bhindi(Ladies Finger)", "Variety": "Other",
         "Arrival_Date": "16/10/2026", "Min_Price": "3000", "Max_Price": "4000", "Modal_Price": "3500"},
        {"State": "Jharkhand", "District": "Ranchi", "Market": "Ranchi", "Commodity": "Something Unknown", "Variety": "Other",
         "Arrival_Date": "17/10/2026", "Min_Price": "10", "Max_Price": "20", "Modal_Price": "15"},
    ]

    def setUp(self):
        super().setUp()
        self.app.config["DATA_GOV_API_KEY"] = "test-key"
        self.h = self.login_headers()

    def test_live_records_are_parsed_and_averaged(self):
        with mock.patch.object(prices, "fetch_live", return_value=self.RECORDS) as fetch:
            body = self.client.get("/api/v1/prices?market=ranchi", headers=self.h).get_json()
        fetch.assert_called_once_with("test-key", "Jharkhand", "Ranchi")
        self.assertEqual(body["source"], "agmarknet")
        self.assertEqual(body["price_date"], "2026-10-17")
        ids = {i["id"]: i for i in body["items"]}
        self.assertEqual(set(ids), {"potato", "okra"})  # unknown commodity ignored
        self.assertEqual(ids["potato"]["modal_price"], 2050)  # average of the two markets, latest date only
        self.assertEqual((ids["potato"]["min_price"], ids["potato"]["max_price"]), (1850, 2250))
        self.assertIsNone(ids["potato"]["change_pct"])

    def test_live_failure_falls_back_to_sample(self):
        with mock.patch.object(prices, "fetch_live", side_effect=OSError("offline")):
            body = self.client.get("/api/v1/prices?market=ranchi", headers=self.h).get_json()
        self.assertEqual(body["source"], "sample")
        self.assertEqual(body["note"], "live_unavailable")
        self.assertEqual(len(body["items"]), 22)

    def test_live_empty_falls_back_to_sample(self):
        with mock.patch.object(prices, "fetch_live", return_value=[]):
            body = self.client.get("/api/v1/prices?market=ranchi", headers=self.h).get_json()
        self.assertEqual((body["source"], body["note"]), ("sample", "live_empty"))

    def test_live_results_are_cached(self):
        with mock.patch.object(prices, "fetch_live", return_value=self.RECORDS) as fetch:
            self.client.get("/api/v1/prices?market=ranchi", headers=self.h)
            self.client.get("/api/v1/prices?market=ranchi", headers=self.h)
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
