import math
import random
import pickle
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model.pkl")
_ISO_PATH   = os.path.join(os.path.dirname(__file__), "iso_model.pkl")


def _gen_human_events(n: int = None) -> list:
    n = n or random.randint(40, 120)
    events, t = [], 0
    x = 0.0
    y = 0.5 + random.uniform(-0.05, 0.05)
    target_x = random.uniform(0.55, 0.85)

    for i in range(n):
        progress = i / (n - 1)
        if progress < 0.1:
            sf = progress / 0.1 * 0.8 + 0.2
        elif progress < 0.85:
            sf = 0.8 + random.gauss(0, 0.15)
        else:
            sf = max(0.1, (1 - progress) / 0.15)

        dx = (target_x / n) * sf * random.uniform(0.7, 1.3)
        dy = random.gauss(0, 0.006)
        x  = min(1.0, x + dx)
        y  = max(0.0, min(1.0, y + dy))

        dt = int(random.gauss(18, 6))
        if random.random() < 0.06:
            dt += random.randint(60, 200)
        t += max(5, dt)
        events.append({"x": x, "y": y, "t": t, "area": "canvas"})

    return events


def _gen_bot_simple(n: int = None) -> list:
    n = n or random.randint(10, 20)
    events, t = [], 0
    target_x = random.uniform(0.55, 0.85)
    for i in range(n):
        t += random.randint(18, 22)
        events.append({"x": round(i / (n-1) * target_x, 4), "y": 0.5, "t": t, "area": "puzzle"})
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
    def ease(v): return 3*v**2 - 2*v**3
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
    def ease(v): return 3*v**2 - 2*v**3
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


def extract_feature_vector(events: list) -> np.ndarray:
    if len(events) < 3:
        return np.zeros(20)

    events = sorted(events, key=lambda e: e.get("t", 0))
    xs = [e["x"] for e in events]
    ys = [e["y"] for e in events]
    ts = [e["t"] for e in events]
    n  = len(events)

    dts = [ts[i] - ts[i-1] for i in range(1, n) if ts[i] - ts[i-1] > 0]
    dxs = [xs[i] - xs[i-1] for i in range(1, n)]
    dys = [ys[i] - ys[i-1] for i in range(1, n)]

    def smean(a): return sum(a)/len(a) if a else 0.0
    def sstd(a):
        if len(a) < 2: return 0.0
        m = smean(a)
        return math.sqrt(sum((v-m)**2 for v in a)/len(a))
    def scv(a): m = smean(a); return sstd(a)/m if m > 1e-9 else 0.0

    mean_dt = smean(dts); std_dt = sstd(dts); cv_dt = scv(dts)
    max_dt  = max(dts) if dts else 0
    min_dt  = min(dts) if dts else 0

    vels = []
    for i in range(1, n):
        dt_s = (ts[i]-ts[i-1])/1000.0
        if dt_s <= 0: continue
        vels.append(math.sqrt(dxs[i-1]**2 + dys[i-1]**2) / dt_s)
    mean_vel = smean(vels); std_vel = sstd(vels); cv_vel = scv(vels)

    mean_abs_dy = smean([abs(d) for d in dys])
    std_dy      = sstd(dys)

    fwd = [d for d in dxs if d >= 0]
    cv_dx = scv(fwd) if fwd else 0.0

    ac1 = 0.0
    if len(dts) >= 4:
        m = smean(dts); c = [d - m for d in dts]
        var = sum(v**2 for v in c) / len(c)
        if var > 1e-9:
            pairs = [(c[i], c[i+1]) for i in range(len(c)-1)]
            ac1   = abs(sum(a*b for a,b in pairs) / len(pairs) / var)

    total_ms         = ts[-1] - ts[0]
    event_count_norm = min(n / 100.0, 2.0)
    canvas_ratio     = sum(1 for e in events if e.get("area") == "canvas") / n

    devs = []
    for i in range(1, n-1):
        p1, p2, p3 = events[i-1], events[i], events[i+1]
        dx, dy = p3["x"]-p1["x"], p3["y"]-p1["y"]
        seg = math.sqrt(dx**2+dy**2)
        if seg < 1e-9: continue
        devs.append(abs(dx*(p1["y"]-p2["y"]) - dy*(p1["x"]-p2["x"])) / seg)
    mean_tremor = smean(devs)

    dc, ts2 = 0, 0
    for i in range(1, n-1):
        v1x=xs[i]-xs[i-1]; v1y=ys[i]-ys[i-1]
        v2x=xs[i+1]-xs[i]; v2y=ys[i+1]-ys[i]
        l1=math.sqrt(v1x**2+v1y**2); l2=math.sqrt(v2x**2+v2y**2)
        if l1<1e-9 or l2<1e-9: continue
        cos_a=max(-1.0,min(1.0,(v1x*v2x+v1y*v2y)/(l1*l2)))
        ts2 += 1
        if math.acos(cos_a) > math.radians(5): dc += 1
    dir_change_ratio = dc / ts2 if ts2 else 0.0

    return np.array([
        mean_dt, std_dt, cv_dt, max_dt, min_dt,         
        mean_vel, std_vel, cv_vel,                         
        mean_abs_dy, std_dy, cv_dx, ac1,                 
        total_ms, event_count_norm, canvas_ratio,          
        mean_tremor, dir_change_ratio,                    
        std_vel / (mean_vel + 1e-9),                       
        max_dt  / (mean_dt  + 1e-9),                       
        mean_abs_dy / (cv_dx + 1e-9),                     
    ], dtype=float)


def _make_training_data(n: int = 2000):
    X, y = [], []
    bots = [_gen_bot_simple, _gen_bot_sine, _gen_bot_easeinout, _gen_bot_overshoot]
    for _ in range(n):
        X.append(extract_feature_vector(_gen_human_events())); y.append(1)
        X.append(extract_feature_vector(random.choice(bots)())); y.append(0)
    return np.array(X), np.array(y)


def _train_rf():
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
    with open(_MODEL_PATH, "wb") as f: pickle.dump(m, f)
    print(f"[ML] RandomForest saved → {_MODEL_PATH}")
    return m


def _train_iso():
    print("[ML] Training IsolationForest...")
    X_human = [extract_feature_vector(_gen_human_events()) for _ in range(1000)]
    m = Pipeline([
        ("scaler", StandardScaler()),
        ("iso", IsolationForest(contamination=0.05, random_state=42, n_jobs=-1)),
    ])
    m.fit(np.array(X_human))
    with open(_ISO_PATH, "wb") as f: pickle.dump(m, f)
    print(f"[ML] IsolationForest saved → {_ISO_PATH}")
    return m


def _load(path, trainer):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return trainer()


_RF_MODEL  = _load(_MODEL_PATH, _train_rf)
_ISO_MODEL = _load(_ISO_PATH,   _train_iso)


class BehaviorScorer:
    def __init__(self, raw_data):
        all_events = raw_data.get("events", [])
        self._events_by_area = {}
        for e in all_events:
            self._events_by_area.setdefault(e.get("area", "unknown"), []).append(e)
        self.events        = sorted(all_events, key=lambda e: e.get("t", 0))
        self.velocities    = []
        self.accelerations = []


    def compute_physics(self):
        for i in range(1, len(self.events)):
            p1, p2 = self.events[i-1], self.events[i]
            dt = p2["t"] - p1["t"]
            if dt <= 0: continue
            d = math.sqrt((p2["x"]-p1["x"])**2 + (p2["y"]-p1["y"])**2)
            v = d / (dt / 1000.0)
            self.velocities.append(v)
            if len(self.velocities) > 1:
                self.accelerations.append((v - self.velocities[-2]) / (dt / 1000.0))


    def _f(self, name):
        return getattr(self, f"feature_{name}")()

    def feature_velocity_stddev(self):
        if not self.velocities: return 0.0
        m = sum(self.velocities)/len(self.velocities)
        return min(math.sqrt(sum((v-m)**2 for v in self.velocities)/len(self.velocities))*3.0, 1.0)

    def feature_acceleration_profile(self):
        if len(self.accelerations) < 2: return 0.0
        m = sum(self.accelerations)/len(self.accelerations)
        return min(math.sqrt(sum((a-m)**2 for a in self.accelerations)/len(self.accelerations))*0.5, 1.0)

    def feature_tremor(self):
        devs = []
        for i in range(1, len(self.events)-1):
            p1,p2,p3 = self.events[i-1],self.events[i],self.events[i+1]
            dx,dy = p3["x"]-p1["x"], p3["y"]-p1["y"]
            seg = math.sqrt(dx**2+dy**2)
            if seg < 1e-9: continue
            devs.append(abs(dx*(p1["y"]-p2["y"])-dy*(p1["x"]-p2["x"]))/seg)
        return min(sum(devs)/len(devs)*80.0, 1.0) if devs else 0.0

    def feature_pause_hesitation(self):
        dts = [self.events[i]["t"]-self.events[i-1]["t"] for i in range(1, len(self.events))
               if self.events[i]["t"]-self.events[i-1]["t"] > 0]
        if not dts: return 0.0
        med  = sorted(dts)[len(dts)//2]
        thr  = max(med*2, 100)
        r    = sum(1 for d in dts if d > thr) / len(dts)
        if r == 0: return 0.5
        return min(r*4.0, 1.0) if r <= 0.25 else max(1.0-(r-0.25)*4.0, 0.0)

    def feature_direction_changes(self):
        dc = ts = 0
        for i in range(1, len(self.events)-1):
            p0,p1,p2 = self.events[i-1],self.events[i],self.events[i+1]
            v1x,v1y = p1["x"]-p0["x"], p1["y"]-p0["y"]
            v2x,v2y = p2["x"]-p1["x"], p2["y"]-p1["y"]
            l1=math.sqrt(v1x**2+v1y**2); l2=math.sqrt(v2x**2+v2y**2)
            if l1<1e-9 or l2<1e-9: continue
            ts += 1
            if math.acos(max(-1.,min(1.,(v1x*v2x+v1y*v2y)/(l1*l2)))) > math.radians(5): dc += 1
        return min(dc/ts*1.5, 1.0) if ts else 0.0

    def feature_linearity(self):
        if len(self.events) < 2: return 0.0
        pl = sum(math.sqrt((self.events[i]["x"]-self.events[i-1]["x"])**2 +
                           (self.events[i]["y"]-self.events[i-1]["y"])**2)
                 for i in range(1, len(self.events)))
        s,e = self.events[0],self.events[-1]
        d   = math.sqrt((e["x"]-s["x"])**2+(e["y"]-s["y"])**2)
        return min((pl/d-1.0)*10.0, 1.0) if d > 1e-9 else 0.0

    def feature_session_duration(self):
        if len(self.events) < 2: return 0.0
        ms = self.events[-1]["t"] - self.events[0]["t"]
        if ms < 300: return 0.0
        if ms < 500: return (ms-300)/200*0.4
        if ms <= 3000: return 1.0
        if ms <= 6000: return max(1.0-(ms-3000)/3000*0.5, 0.5)
        return 0.3

    def feature_interval_irregularity(self):
        dts = [self.events[i]["t"]-self.events[i-1]["t"] for i in range(1, len(self.events))
               if self.events[i]["t"]-self.events[i-1]["t"] > 0]
        if len(dts) < 4 or max(dts)-min(dts) < 1: return 0.0
        m   = sum(dts)/len(dts)
        std = math.sqrt(sum((d-m)**2 for d in dts)/len(dts))
        cv  = std/m if m > 0 else 0
        if cv < 0.12: return 0.0
        if cv < 0.25: return (cv-0.12)/0.13*0.5
        return min(0.5+(cv-0.25)*2.0, 1.0)

    def feature_y_variation(self):
        dy = [abs(self.events[i]["y"]-self.events[i-1]["y"]) for i in range(1, len(self.events))]
        m  = sum(dy)/len(dy) if dy else 0
        return 0.0 if m < 0.001 else min(m*120.0, 1.0)

    def feature_periodic_timing(self):
        if len(self.events) < 10: return 0.5
        dts = [self.events[i]["t"]-self.events[i-1]["t"] for i in range(1, len(self.events))
               if self.events[i]["t"]-self.events[i-1]["t"] > 0]
        if len(dts) < 5: return 0.5
        m   = sum(dts)/len(dts); c = [d-m for d in dts]
        var = sum(v**2 for v in c)/len(c)
        if var < 1e-9: return 0.0
        max_ac = max(
            abs(sum(c[i]*c[i+lag] for i in range(len(c)-lag)) / len(c) / var)
            for lag in range(1, min(6, len(c)))
        )
        if max_ac > 0.8: return 0.0
        if max_ac > 0.5: return (0.8-max_ac)/0.3*0.5
        return min(1.0-max_ac, 1.0)

    def feature_event_count(self):
        n = len(self.events)
        if n < 15:  return 0.0
        if n < 30:  return (n-15)/15*0.6
        if n <= 200: return 1.0
        return max(1.0-(n-200)/200, 0.3)

    def feature_x_monotonicity(self):
        dxs = [self.events[i]["x"]-self.events[i-1]["x"] for i in range(1, len(self.events))]
        fwd = [d for d in dxs if d >= 0]
        if not fwd: return 0.5
        m   = sum(fwd)/len(fwd)
        if m < 1e-9: return 0.0
        std = math.sqrt(sum((d-m)**2 for d in fwd)/len(fwd))
        cv  = std/m
        if cv < 0.05: return 0.0
        if cv < 0.15: return (cv-0.05)/0.10*0.5
        return min(cv*2.0, 1.0)

    def ml_score(self) -> tuple:
        """Trả về (rf_prob_human, iso_is_human)."""
        vec = extract_feature_vector(self.events).reshape(1, -1)
        rf_prob   = float(_RF_MODEL.predict_proba(vec)[0][1])
        iso_human = 1.0 if _ISO_MODEL.predict(vec)[0] == 1 else 0.0
        return rf_prob, iso_human

    def analyze_behavior(self) -> dict:
        try:
            canvas_events = [e for e in self.events if e.get("area") == "canvas"]
            puzzle_events = [e for e in self.events if e.get("area") == "puzzle"]

            if len(canvas_events) < 8:
                return {"result": "bot", "score": 0.1, "msg": "Insufficient canvas interaction"}

            self.events = canvas_events
            if len(self.events) < 15:
                return {"result": "bot", "score": 0.0, "msg": "Too few events"}

            self.compute_physics()
            if not self.velocities:
                return {"result": "bot", "score": 0.1, "msg": "Không tính được vận tốc"}

            f = {
                "velocity_stddev":       self.feature_velocity_stddev(),
                "acceleration_profile":  self.feature_acceleration_profile(),
                "tremor":                self.feature_tremor(),
                "pause_hesitation":      self.feature_pause_hesitation(),
                "direction_changes":     self.feature_direction_changes(),
                "linearity":             self.feature_linearity(),
                "session_duration":      self.feature_session_duration(),
                "interval_irregularity": self.feature_interval_irregularity(),
                "y_variation":           self.feature_y_variation(),
                "periodic_timing":       self.feature_periodic_timing(),
                "event_count":           self.feature_event_count(),
                "x_monotonicity":        self.feature_x_monotonicity(),
            }
            W = {
                "velocity_stddev":0.10, "acceleration_profile":0.05,
                "tremor":0.08,          "pause_hesitation":0.07,
                "direction_changes":0.08,"linearity":0.03,
                "session_duration":0.07, "interval_irregularity":0.07,
                "y_variation":0.08,     "periodic_timing":0.08,
                "event_count":0.05,     "x_monotonicity":0.04,
            }
            total_w = sum(W.values())
            rule_score = round(sum(f[k]*W[k] for k in W) / total_w, 3)

            rf_score, iso_score = self.ml_score()
            ml_score = round(rf_score * 0.70 + iso_score * 0.30, 3)

            final = round(rule_score * 0.40 + ml_score * 0.60, 2)

            return {
                "result": "human" if final > 0.50 else "bot",
                "score":  final,
                "debug": {
                    "total_events":   len(self.events),
                    "puzzle_events":  len(puzzle_events),
                    "canvas_events":  len(canvas_events),
                    "rule_score":     rule_score,
                    "ml_rf_score":    round(rf_score, 3),
                    "ml_iso_score":   round(iso_score, 3),
                    "ml_score":       ml_score,
                    **{f"f{i+1}_{k}": round(v, 3) for i,(k,v) in enumerate(f.items())},
                },
            }

        except Exception as e:
            return {"result": "error", "score": 0, "msg": str(e)}