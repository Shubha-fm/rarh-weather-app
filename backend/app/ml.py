"""The machine learning model: a small neural network (scikit-learn MLPRegressor).

It learns how temperature, humidity and rain change with latitude, longitude and time of year,
using the climate curves of the reference stations.
"""

import os
import warnings
from datetime import datetime, timezone

import joblib
import numpy as np
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor

from .climate import build_dataset, features

HIDDEN_LAYERS = (32, 24)


class WeatherModel:
    def __init__(self, net, y_mean, y_std, meta):
        self.net = net
        self.y_mean = y_mean
        self.y_std = y_std
        self.meta = meta

    # ---- training -------------------------------------------------------------------------

    @classmethod
    def train(cls, seed=7, exclude_station_id=None):
        x_train, y_train, x_val, y_val = build_dataset(exclude_station_id)
        y_mean, y_std = y_train.mean(axis=0), y_train.std(axis=0)
        y_std[y_std == 0] = 1.0
        net = MLPRegressor(
            hidden_layer_sizes=HIDDEN_LAYERS,
            activation="tanh",
            solver="adam",
            alpha=1e-4,
            batch_size=32,
            learning_rate_init=0.005,
            max_iter=400,
            tol=1e-7,
            n_iter_no_change=40,
            random_state=seed,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            net.fit(x_train, (y_train - y_mean) / y_std)
        model = cls(net, y_mean, y_std, {})
        pred = model._raw(x_val)
        mae_c = float(np.abs(pred[:, :2] - y_val[:, :2]).mean())
        model.meta = {
            "type": "MLPRegressor (neural network)",
            "hidden_layers": list(HIDDEN_LAYERS),
            "training_rows": int(len(x_train)),
            "iterations": int(net.n_iter_),
            "validation_mae_c": round(mae_c, 2),
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "scikit_learn": sklearn.__version__,
        }
        return model

    # ---- saving and loading ---------------------------------------------------------------

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        joblib.dump({"net": self.net, "y_mean": self.y_mean, "y_std": self.y_std, "meta": self.meta}, path)

    @classmethod
    def load(cls, path):
        blob = joblib.load(path)
        return cls(blob["net"], blob["y_mean"], blob["y_std"], blob["meta"])

    @classmethod
    def load_or_train(cls, path):
        """Use the saved model if it exists and loads, otherwise train a new one and save it."""
        if os.path.exists(path):
            try:
                return cls.load(path)
            except Exception:
                pass  # a model saved by another scikit-learn version: retrain below
        model = cls.train()
        model.save(path)
        return model

    # ---- prediction -----------------------------------------------------------------------

    def _raw(self, x):
        return self.net.predict(x) * self.y_std + self.y_mean

    def predict(self, latitude, longitude, day_of_year):
        """Prediction for one or many days at one place. Returns a dict of arrays (one value per day)."""
        v = self._raw(features(latitude, longitude, day_of_year))
        tmax = v[:, 0]
        tmin = np.minimum(v[:, 1], tmax - 2)
        return {
            "tmax": tmax,
            "tmin": tmin,
            "rh": np.clip(v[:, 2], 10, 99),
            "rain": np.maximum(v[:, 3], 0),
            "chance": np.clip(v[:, 4], 0, 0.95),
        }
