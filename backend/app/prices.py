"""Mandi (wholesale market) prices for crops and vegetables.

Two sources:
  * SAMPLE (default): realistic-looking prices made from typical levels, the season and the date. They are NOT real
    market rates. The API marks them with  "source": "sample"  and the app shows a clear banner.
  * LIVE: official daily mandi prices from Agmarknet through the data.gov.in API. Switch it on by setting the
    DATA_GOV_API_KEY environment variable (a free key from data.gov.in). If the live call fails or returns nothing for
    a market, the API falls back to sample prices and says so in "note".
"""

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

from .auth import require_auth
from .climate import seasonal
from .data import STATIONS
from .errors import ApiError
from .validation import iso_date

bp = Blueprint("prices", __name__, url_prefix="/api/v1")

UNIT = "INR per quintal"  # 1 quintal = 100 kg
LIVE_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"  # "Current Daily Price of Various Commodities from Various Markets (Mandi)"
LIVE_URL = f"https://api.data.gov.in/resource/{LIVE_RESOURCE_ID}"
LIVE_CACHE_SECONDS = 1800

# id, English, Bengali, Hindi, group, colour, typical price (INR/quintal), daily swing, month-by-month price level, live-name keywords
_RAW = [
    ("potato", "Potato", "আলু", "आलू", "vegetable", "#C9A15B", 1900, 0.03, [.85,.85,.9,1,1.1,1.2,1.25,1.25,1.15,1.05,.95,.88], ["potato"]),
    ("onion", "Onion", "পেঁয়াজ", "प्याज़", "vegetable", "#B8508A", 2300, 0.04, [.9,.8,.75,.8,.9,1,1.1,1.25,1.4,1.45,1.3,1.1], ["onion"]),
    ("tomato", "Tomato", "টমেটো", "टमाटर", "vegetable", "#D2412F", 2600, 0.07, [.7,.65,.7,.9,1.2,1.5,1.7,1.6,1.3,1.1,.9,.75], ["tomato"]),
    ("brinjal", "Brinjal", "বেগুন", "बैंगन", "vegetable", "#5B3A8C", 2600, 0.05, [.9,.85,.9,1,1.1,1.15,1.15,1.1,1.05,1,.95,.9], ["brinjal"]),
    ("cauliflower", "Cauliflower", "ফুলকপি", "फूलगोभी", "vegetable", "#D8D2B8", 2400, 0.06, [.7,.65,.8,1.2,1.6,1.8,1.7,1.5,1.2,.9,.7,.65], ["cauliflower"]),
    ("cabbage", "Cabbage", "বাঁধাকপি", "पत्तागोभी", "vegetable", "#7FB069", 1600, 0.05, [.7,.65,.8,1,1.3,1.5,1.4,1.3,1.1,.9,.7,.65], ["cabbage"]),
    ("greenchilli", "Green chilli", "কাঁচা লঙ্কা", "हरी मिर्च", "vegetable", "#2E8B3E", 4800, 0.05, [.9,.85,.9,1,1.15,1.3,1.3,1.2,1.1,1,.95,.9], ["green chilli"]),
    ("pointedgourd", "Pointed gourd (Potol)", "পটল", "परवल", "vegetable", "#6BA368", 4200, 0.05, [1.2,1.15,1,.85,.8,.85,.95,1.05,1.1,1.15,1.2,1.25], ["pointed gourd", "parval"]),
    ("bottlegourd", "Bottle gourd", "লাউ", "लौकी", "vegetable", "#A8C686", 1900, 0.05, [1,.9,.8,.75,.8,.9,1,1.1,1.2,1.2,1.15,1.1], ["bottle gourd"]),
    ("okra", "Okra (Bhindi)", "ঢেঁড়স", "भिंडी", "vegetable", "#4F8F3A", 3600, 0.05, [1.3,1.2,1,.85,.8,.8,.85,.9,.95,1,1.15,1.3], ["bhindi", "ladies finger", "okra"]),
    ("pumpkin", "Pumpkin", "কুমড়ো", "कद्दू", "vegetable", "#E08A1E", 1500, 0.04, [.9,.9,.95,1,1.05,1.1,1.1,1.05,1,.95,.9,.9], ["pumpkin"]),
    ("cucumber", "Cucumber", "শসা", "खीरा", "vegetable", "#3E9B6B", 2300, 0.05, [1.2,1.1,.9,.8,.8,.85,.9,.95,1,1.05,1.1,1.2], ["cucumb"]),
    ("bittergourd", "Bitter gourd", "করলা", "करेला", "vegetable", "#2F6B3A", 3900, 0.05, [1.1,1,.9,.85,.85,.9,.95,1,1.05,1.1,1.1,1.15], ["bitter gourd"]),
    ("ridgegourd", "Ridge gourd", "ঝিঙে", "तोरई", "vegetable", "#8DB35A", 3200, 0.05, [1.1,1,.9,.85,.85,.9,.95,1,1.05,1.1,1.1,1.15], ["ridge gourd", "turai"]),
    ("carrot", "Carrot", "গাজর", "गाजर", "vegetable", "#E5701F", 2900, 0.05, [.7,.65,.8,1.1,1.4,1.5,1.4,1.3,1.1,.95,.75,.7], ["carrot"]),
    ("greenpeas", "Green peas", "কড়াইশুঁটি", "हरी मटर", "vegetable", "#5FAE4A", 5800, 0.06, [.7,.7,.9,1.3,1.6,1.7,1.7,1.6,1.4,1.2,.85,.7], ["peas wet", "green peas"]),
    ("spinach", "Spinach", "পালং শাক", "पालक", "vegetable", "#2A7A3B", 1500, 0.05, [.7,.7,.8,.95,1.1,1.2,1.2,1.1,1,.9,.75,.7], ["spinach"]),
    ("paddy", "Paddy", "ধান", "धान", "crop", "#C9B24A", 2400, 0.008, [1.02,1.04,1.05,1.05,1.04,1.03,1.02,1,.97,.95,.97,1], ["paddy"]),
    ("maize", "Maize", "ভুট্টা", "मक्का", "crop", "#E3B82B", 2300, 0.008, [1,1,1.02,1.05,1.05,1.04,1.02,1,.97,.95,.97,1], ["maize"]),
    ("wheat", "Wheat", "গম", "गेहूँ", "crop", "#CDA24A", 2700, 0.008, [1,1,.97,.95,.97,1,1.02,1.03,1.04,1.04,1.03,1.02], ["wheat"]),
    ("mustard", "Mustard seed", "সর্ষে", "सरसों", "crop", "#C8A400", 6100, 0.008, [1,.97,.95,.95,.97,1,1.02,1.03,1.04,1.04,1.03,1.02], ["mustard"]),
    ("lentil", "Lentil (Masoor)", "মসুর", "मसूर", "crop", "#B5651D", 6700, 0.008, [1,.98,.97,.97,.98,1,1.02,1.03,1.04,1.04,1.03,1.02], ["lentil", "masur"]),
]
COMMODITIES = [
    {"id": r[0], "name": {"en": r[1], "bn": r[2], "hi": r[3]}, "group": r[4], "color": r[5], "base": r[6], "vol": r[7], "season": r[8], "keywords": r[9]}
    for r in _RAW
]

# Markets: the district towns of the weather stations. factor = how this market's prices sit against the typical level.
# agmarknet = the state and district names used by the live data source.
_MARKET_INFO = {
    "kolkata": (1.10, "West Bengal", "Kolkata"),
    "burdwan": (0.95, "West Bengal", "Burdwan"),
    "bankura": (0.93, "West Bengal", "Bankura"),
    "purulia": (0.95, "West Bengal", "Purulia"),
    "ranchi": (1.02, "Jharkhand", "Ranchi"),
    "jamshedpur": (1.05, "Jharkhand", "East Singhbum"),
    "dhanbad": (1.04, "Jharkhand", "Dhanbad"),
    "hazaribagh": (0.97, "Jharkhand", "Hazaribagh"),
}
_STATIONS_BY_ID = {s["id"]: s for s in STATIONS}
MARKETS = {
    mid: {"id": mid, "name": _STATIONS_BY_ID[mid]["name"], "state": state, "factor": factor, "district": district}
    for mid, (factor, state, district) in _MARKET_INFO.items()
}


def _item(c, low, modal, high, previous):
    change = None if not previous else round((modal - previous) / previous * 100, 1)
    return {
        "id": c["id"], "name": c["name"], "group": c["group"], "color": c["color"],
        "min_price": int(low), "modal_price": int(modal), "max_price": int(high),
        "previous_modal_price": None if previous is None else int(previous), "change_pct": change,
    }


# ---------- sample provider ----------

def _noise(*parts):
    """A repeatable number in [-1, 1) that depends only on the inputs."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32 * 2 - 1


def _round10(x):
    return int(round(x / 10.0) * 10)


def _sample_modal(c, market_id, day):
    doy = min(365, day.timetuple().tm_yday)
    level = float(seasonal(c["season"], doy))
    daily = _noise(market_id, c["id"], day.isoformat())
    weekly = _noise(market_id, c["id"], *day.isocalendar()[:2])
    return c["base"] * MARKETS[market_id]["factor"] * level * (1 + c["vol"] * (0.7 * daily + 0.3 * weekly))


def sample_items(market_id, day):
    items = []
    for c in COMMODITIES:
        modal = _round10(_sample_modal(c, market_id, day))
        previous = _round10(_sample_modal(c, market_id, day - timedelta(days=1)))
        low = _round10(modal * (1 - (0.06 + 0.06 * abs(_noise(market_id, c["id"], day.isoformat(), "lo")))))
        high = _round10(modal * (1 + (0.06 + 0.08 * abs(_noise(market_id, c["id"], day.isoformat(), "hi")))))
        items.append(_item(c, low, modal, high, previous))
    return items


# ---------- live provider (Agmarknet through data.gov.in) ----------

def fetch_live(api_key, state, district, timeout=8):
    """Download recent mandi price records for one district. Returns a list of dicts."""
    query = urllib.parse.urlencode(
        {"api-key": api_key, "format": "json", "limit": "500", "filters[state]": state, "filters[district]": district}
    )
    request_ = urllib.request.Request(f"{LIVE_URL}?{query}", headers={"User-Agent": "rarh-weather/1.0"})
    with urllib.request.urlopen(request_, timeout=timeout) as response:
        return json.load(response).get("records", [])


def _key(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower().replace("_x0020_", "_")).strip("_")


def _to_number(value):
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _to_date(value):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _match(commodity_name):
    name = commodity_name.lower()
    for c in COMMODITIES:
        if any(k in name for k in c["keywords"]):
            return c
    return None


def live_items(records):
    """Turn raw records into API items: latest date per commodity, averaged over the district's markets."""
    by_commodity = {}
    for rec in records:
        r = {_key(k): v for k, v in rec.items()}
        c = _match(str(r.get("commodity", "")))
        day = _to_date(r.get("arrival_date"))
        modal = _to_number(r.get("modal_price"))
        if not c or day is None or modal is None:
            continue
        low = _to_number(r.get("min_price")) or modal
        high = _to_number(r.get("max_price")) or modal
        by_commodity.setdefault(c["id"], {}).setdefault(day, []).append((min(low, modal), modal, max(high, modal)))

    items, newest = [], None
    for c in COMMODITIES:
        days = by_commodity.get(c["id"])
        if not days:
            continue
        day = max(days)
        rows = days[day]
        avg = [sum(col) / len(rows) for col in zip(*rows)]
        items.append(_item(c, avg[0], avg[1], avg[2], None))
        newest = day if newest is None else max(newest, day)
    return items, newest


def _live_for_market(market):
    cache = current_app.extensions.setdefault("price_cache", {})
    key = (market["state"], market["district"])
    hit = cache.get(key)
    if hit and time.time() - hit[0] < LIVE_CACHE_SECONDS:
        records = hit[1]
    else:
        records = fetch_live(current_app.config["DATA_GOV_API_KEY"], market["state"], market["district"])
        cache[key] = (time.time(), records)
    return live_items(records)


# ---------- routes ----------

def _public_market(m):
    return {"id": m["id"], "name": m["name"], "state": m["state"]}


@bp.get("/markets")
@require_auth
def markets():
    source = "agmarknet" if current_app.config.get("DATA_GOV_API_KEY") else "sample"
    return jsonify({"markets": [_public_market(m) for m in MARKETS.values()], "source": source})


@bp.get("/prices")
@require_auth
def prices():
    market_id = request.args.get("market", "ranchi")
    market = MARKETS.get(market_id)
    if market is None:
        raise ApiError(422, "unknown_market", "Unknown market.", "market")
    day = iso_date(request.args.get("date"))

    source, note, price_date, items = "sample", None, day, None
    if current_app.config.get("DATA_GOV_API_KEY"):
        try:
            live, live_date = _live_for_market(market)
            if live:
                source, items, price_date = "agmarknet", live, live_date
            else:
                note = "live_empty"
        except Exception:
            note = "live_unavailable"
    if items is None:
        items = sample_items(market_id, day)

    body = {
        "market": _public_market(market),
        "date": day.isoformat(),
        "price_date": price_date.isoformat(),
        "source": source,
        "unit": UNIT,
        "items": items,
    }
    if note:
        body["note"] = note
    return jsonify(body)
