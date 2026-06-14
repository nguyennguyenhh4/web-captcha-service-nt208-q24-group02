"""
train.py — offline model training script.

Run this script to regenerate ml_model.pkl and iso_model.pkl:
    python train.py

IMPORTANT: This file must NEVER be deployed to production or committed
to a public repository.  It contains the exact feature targets and bot
templates used to train the classifier — publishing them gives attackers
a blueprint for building adversarial inputs that evade detection.
"""

import math
import random
import pickle
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from scoring_logic import extract_feature_vector

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model.pkl")
_ISO_PATH   = os.path.join(os.path.dirname(__file__), "iso_model.pkl")


# ---------------------------------------------------------------------------
# Synthetic event generators
# ---------------------------------------------------------------------------

def _gen_human_events(n_points=None) -> list:
    """
    Sinh dữ liệu mô phỏng người thật vẽ polygon.
    """

    n_points = n_points or random.randint(3, 6)

    cx = random.uniform(80, 220)
    cy = random.uniform(40, 110)

    radius = random.randint(35, 55)

    polygon = []

    for i in range(n_points):
        angle = (
            2 * math.pi * i / n_points
            + random.uniform(-0.15, 0.15)
        )

        polygon.append((
            (cx + radius * math.cos(angle)) / 300,
            (cy + radius * math.sin(angle)) / 150,
        ))

    # close polygon
    polygon.append(polygon[0])

    events = []
    t = 0

    for seg_idx in range(len(polygon) - 1):

        x0, y0 = polygon[seg_idx]
        x1, y1 = polygon[seg_idx + 1]

        n_seg = random.randint(15, 40)

        # tốc độ khác nhau giữa các cạnh
        segment_speed = random.uniform(0.7, 1.4)

        for i in range(n_seg):

            p = i / max(n_seg - 1, 1)

            # ease in/out
            ease_p = 3 * p**2 - 2 * p**3

            x = x0 + (x1 - x0) * ease_p
            y = y0 + (y1 - y0) * ease_p

            # hand tremor
            x += math.sin(i * 0.3) * random.uniform(0.001, 0.004)
            y += math.cos(i * 0.3) * random.uniform(0.001, 0.004)

            # gaussian noise
            x += random.gauss(0, 0.003)
            y += random.gauss(0, 0.003)

            # overshoot gần vertex
            if i > n_seg * 0.85 and random.random() < 0.35:
                x += random.gauss(0, 0.01)
                y += random.gauss(0, 0.01)

            x = max(0.0, min(1.0, x))
            y = max(0.0, min(1.0, y))

            dt = int(
                random.gauss(20 * segment_speed, 6)
            )

            # pause ngẫu nhiên
            if random.random() < 0.05:
                dt += random.randint(50, 180)

            t += max(5, dt)

            events.append({
                "x": round(x, 4),
                "y": round(y, 4),
                "t": t,
                "area": "canvas",
            })

    return events


def _gen_bot_simple(n: int = None) -> list:
    n = n or random.randint(10, 20)
    events, t = [], 0
    target_x = random.uniform(0.55, 0.85)
    for i in range(n):
        t += random.randint(18, 22)
        events.append({"x": round(i / (n - 1) * target_x, 4), "y": 0.5,
                       "t": t, "area": "puzzle"})
    return events


def _gen_bot_sine(n: int = 25) -> list:
    events, t = [], 0
    target_x = random.uniform(0.55, 0.85)
    for i in range(n):
        p = i / (n - 1)
        t += max(5, int(15 + 10 * math.sin(p * math.pi * 3)))
        events.append({"x": round(p * target_x, 4),
                       "y": round(0.5 + 0.005 * math.sin(p * math.pi * 2), 4),
                       "t": t, "area": "puzzle"})
    return events


def _gen_bot_easeinout(n: int = 30) -> list:
    def ease(v): return 3 * v ** 2 - 2 * v ** 3
    events, t = [], 0
    target_x = random.uniform(0.55, 0.85)
    for i in range(n):
        p  = i / (n - 1)
        dt = random.randint(14, 26)
        if random.random() < 0.07:
            dt += random.randint(50, 120)
        t += dt
        events.append({"x": round(ease(p) * target_x, 4),
                       "y": round(0.5 + random.uniform(-0.008, 0.008), 4),
                       "t": t, "area": "puzzle"})
    return events


def _gen_bot_overshoot() -> list:
    def ease(v): return 3 * v ** 2 - 2 * v ** 3
    target_x = random.uniform(0.55, 0.85)
    over     = target_x + random.uniform(0.04, 0.10)
    events, t = [], 0

    for i in range(20):
        p = i / 19
        t += random.randint(15, 28)
        events.append({"x": round(ease(p) * over, 4),
                       "y": round(0.5 + random.uniform(-0.006, 0.006), 4),
                       "t": t, "area": "puzzle"})
    t += random.randint(80, 180)
    for i in range(10):
        p = i / 9
        t += random.randint(15, 28)
        events.append({"x": round(over + (target_x - over) * ease(p), 4),
                       "y": round(0.5 + random.uniform(-0.006, 0.006), 4),
                       "t": t, "area": "puzzle"})
    return events


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def _make_training_data(n: int = 2000):
    X, y = [], []
    bots = [_gen_bot_simple, _gen_bot_sine, _gen_bot_easeinout, _gen_bot_overshoot]
    for _ in range(n):
        X.append(extract_feature_vector(_gen_human_events())); y.append(1)
        X.append(extract_feature_vector(random.choice(bots)())); y.append(0)
    return np.array(X), np.array(y)


def train_rf():
    print("[ML] Training RandomForest...")
    X, y = _make_training_data(2000)
    m = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=200, max_depth=10, min_samples_leaf=5,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )),
    ])
    m.fit(X, y)
    with open(_MODEL_PATH, "wb") as f:
        pickle.dump(m, f)
    print(f"[ML] RandomForest saved → {_MODEL_PATH}")
    return m


def train_iso():
    print("[ML] Training IsolationForest...")
    X_human = [extract_feature_vector(_gen_human_events()) for _ in range(1000)]
    m = Pipeline([
        ("scaler", StandardScaler()),
        ("iso", IsolationForest(contamination=0.05, random_state=42, n_jobs=-1)),
    ])
    m.fit(np.array(X_human))
    with open(_ISO_PATH, "wb") as f:
        pickle.dump(m, f)
    print(f"[ML] IsolationForest saved → {_ISO_PATH}")
    return m


if __name__ == "__main__":
    train_rf()
    train_iso()
    print("Done. Do NOT commit the .pkl files or this script to a public repo.")
