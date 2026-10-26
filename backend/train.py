"""Train the model and save it to models/model.joblib.

    python train.py              train and save
    python train.py --evaluate   also measure how well it predicts a station it has never seen
"""

import argparse
import os

import numpy as np

from app import DEFAULT_MODEL_PATH
from app.climate import station_targets
from app.data import STATIONS
from app.ml import WeatherModel


def leave_one_station_out():
    days = np.arange(1, 366, 5)
    errors = []
    for s in STATIONS:
        m = WeatherModel.train(exclude_station_id=s["id"])
        p = m.predict(s["latitude"], s["longitude"], days)
        t = station_targets(s, days)
        e = (np.abs(p["tmax"] - t[:, 0]).mean() + np.abs(p["tmin"] - t[:, 1]).mean()) / 2
        errors.append(e)
        print(f"  {s['name']['en']:<12} average temperature error {e:.2f} C")
    print(f"Mean error at a station left out of training: {np.mean(errors):.2f} C")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH))
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    model = WeatherModel.train()
    model.save(args.out)
    print("Saved", args.out)
    for k, v in model.meta.items():
        print(f"  {k}: {v}")
    if args.evaluate:
        print("Leave-one-station-out check:")
        leave_one_station_out()
