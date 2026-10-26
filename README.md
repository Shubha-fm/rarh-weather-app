# Rarh Weather

Weather prediction and market prices for farmers in Rarh Bengal and Jharkhand, in English, Bengali and Hindi.

A farmer registers with a name, phone number and password, and gets a unique User ID (for example `RF482915`). After logging in with the User ID and password, the farmer picks a language, then chooses **Weather prediction** or **Market prices**.

```
rarh-weather-app/
  backend/    Python API (Flask). Accounts, the machine learning model, market prices.
  frontend/   Web page (HTML, CSS, JavaScript). Talks to the API. No build step.
```

## Run it

You need Python 3.10 or newer. Use two terminals.

**1. Backend (the API)**

```
cd backend
pip install -r requirements.txt
python run.py
```

The API starts at http://127.0.0.1:8000/api/v1/. The first start creates the user database and a signing key in `backend/data/`. The trained model is already included in `backend/models/model.joblib`. To retrain it, run `python train.py` (add `--evaluate` to also measure how it does on a station it has never seen).

**2. Frontend (the web page)**

```
cd frontend
python -m http.server 5500
```

Open http://localhost:5500. If the backend runs somewhere else, change `API_BASE` in `frontend/js/config.js`.

## What the farmer sees

1. **Register** with name, phone number (10-digit mobile) and password. The screen shows the User ID. The farmer must keep it, because login needs it.
2. **Log in** with User ID and password. A login lasts 7 days on that browser.
3. **Choose a language**: English, Bengali or Hindi. It can be changed any time from the top bar.
4. **Weather prediction**: enter latitude and longitude (or tap a town) and a date. The model gives the day's high and low, humidity, chance of rain, short field advice, and the temperature through the year.
5. **Market prices**: prices for 17 vegetables and 5 crops in 8 markets (Kolkata, Burdwan, Bankura, Purulia, Ranchi, Jamshedpur, Dhanbad, Hazaribagh). Each row is a bar for the typical price with a line from the day's lowest to highest rate, and the change since yesterday. Prices are in rupees per quintal (100 kg), with the price per kg underneath.

## Important: what is real and what is not

- **Market prices are samples by default.** Without a key, the API makes realistic prices from typical levels, the season and the date, and the page shows a banner saying so. They are not real mandi rates and must not be used to decide a sale.
- **To show real prices**, get a free API key from https://data.gov.in and start the backend with it:

  ```
  DATA_GOV_API_KEY=your-key python run.py
  ```

  Prices then come from the official daily mandi data (Agmarknet) for each market's district. If the live service fails or has nothing for a district, the API falls back to sample prices and the banner says so. Live results are cached for 30 minutes.
- **The climate numbers behind the weather model are approximate** long-term monthly averages for 17 stations. They are not an official dataset, and the result is a climate-based estimate, not a live forecast. For better accuracy, replace the values in `backend/app/data.py` with IMD or ERA5 averages and run `python train.py`. Average error on stations the model had not seen was about 1.2 °C in testing. It was larger for Daltonganj (about 4 °C), which is hot and dry compared with the other stations.
- **Bengali and Hindi text has not been checked by a native speaker.** Text lives in `frontend/js/i18n.js`.

## Accounts and security

- Passwords are stored only as salted hashes (never the password itself).
- 5 wrong passwords for one User ID lock that ID for 5 minutes.
- Login tokens are signed. The signing key comes from the `SECRET_KEY` environment variable, or is created once in `backend/data/secret.key`. Keep that file private and out of version control.
- The weather and market routes need a login. Health, station list and model info are public.
- **There is no way to recover a lost User ID or password yet.** A farmer who loses either has to register again with a different phone number, so adding recovery (for example an SMS code) is the most important next feature.
- Phone numbers are not verified. Anyone can register with any number.

## Settings (environment variables for the backend)

| Variable | What it does | Default |
|---|---|---|
| `DATABASE` | Path of the user database file | `backend/data/rarh.db` |
| `SECRET_KEY` | Key used to sign logins | made once, kept in `backend/data/secret.key` |
| `CORS_ORIGINS` | Website address allowed to call the API | `*` (any) |
| `DATA_GOV_API_KEY` | Turns on live mandi prices | off |
| `MODEL_PATH` | Where the trained model file is | `backend/models/model.joblib` |
| `HOST`, `PORT` | Where `run.py` listens | `127.0.0.1`, `8000` |

## API

All routes are under `/api/v1`. Errors are JSON like `{"error": {"code": "out_of_range", "message": "...", "field": "latitude"}}`. Protected routes need the header `Authorization: Bearer <token>`.

| Route | Needs login | Purpose |
|---|---|---|
| `GET /health` | no | Is the server and model ready |
| `GET /stations` | no | Reference weather stations (names in 3 languages, position) |
| `GET /model` | no | Model type and error on validation data |
| `POST /auth/register` | no | `{name, phone, password}` gives `{user_id, name}` |
| `POST /auth/login` | no | `{user_id, password}` gives `{token, expires_in, user}` |
| `GET /auth/me` | yes | The logged-in farmer |
| `GET` or `POST /predict` | yes | `latitude`, `longitude`, optional `date` (YYYY-MM-DD) |
| `GET /markets` | yes | Markets and whether prices are `sample` or `agmarknet` |
| `GET /prices?market=ranchi&date=YYYY-MM-DD` | yes | Min, typical and max price per quintal, and change since yesterday |

Latitude must be 20 to 27 and longitude 82 to 90.

## Tests

```
cd backend
python -m unittest discover -s tests
```

The tests cover registration, login, lockout, token expiry, the weather model, sample and live prices, and starting the app with no configured key.

## Putting it on a real server

- Serve the backend with a production server, for example `pip install gunicorn` then `gunicorn "app:create_app()" --bind 0.0.0.0:8000`, behind HTTPS.
- Set `SECRET_KEY` and set `CORS_ORIGINS` to your website's address.
- Back up the file named in `DATABASE`. It holds all accounts.
- The page keeps the login token in the browser's local storage. Use HTTPS so it cannot be read on the way.
