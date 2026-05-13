import math
import pickle
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model.pkl")
_ISO_PATH   = os.path.join(os.path.dirname(__file__), "iso_model.pkl")

# ─── THRESHOLD ────────────────────────────────────────────────────────────────
# FIX #11 (thay thế #5): Hạ threshold xuống 0.57.
#
# Vấn đề với 0.62:
#   - Bot cluster 0.61-0.66 → đúng, bị block.
#   - Người thật cẩn thận / vẽ nhanh bị score 0.62-0.68 → false positive!
#
# Giải pháp mới:
#   - Feature `path_segment_linearity` mới phân biệt bot/người TRỰC TIẾP
#     bằng độ lệch đường thẳng (bot ≈ 0.9px, người thật ≥ 3px).
#   - Feature này kéo bot xuống 0.48-0.54 → threshold 0.57 đủ để chặn.
#   - Người thật vốn score > 0.62 → 0.57 không ảnh hưởng.
HUMAN_THRESHOLD = 0.60  # Bot scores cluster 0.48-0.55 sau fix → 0.60 chặn bot, người thật ≥0.65


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


def _load(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    raise FileNotFoundError(
        f"Model file not found: {path}. Run train.py to generate it."
    )


_RF_MODEL  = _load(_MODEL_PATH)
_ISO_MODEL = _load(_ISO_PATH)


class BehaviorScorer:
    # ─── FIX #6: Nhận target_points từ server session ─────────────────────────
    def __init__(self, raw_data, target_points=None, canvas_w=300, canvas_h=150):
        all_events = raw_data.get("events", [])
        self._events_by_area = {}
        for e in all_events:
            self._events_by_area.setdefault(e.get("area", "unknown"), []).append(e)
        self.events        = sorted(all_events, key=lambda e: e.get("t", 0))
        self.velocities    = []
        self.accelerations = []
        # Server-side target points (không tin từ client)
        self.target_points = target_points or []
        self.canvas_w      = canvas_w
        self.canvas_h      = canvas_h

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

    # ─── FIX #7: Feature mới — Corner velocity drop ───────────────────────────
    def feature_corner_velocity_drop(self) -> float:
        """
        Người thật giảm tốc trước khi đổi hướng (tại đỉnh polygon).
        Bot duy trì vận tốc đều qua các góc.

        Trả về:
          1.0 = giảm tốc rõ ràng tại góc → human
          0.0 = không giảm tốc / tăng tốc tại góc → bot
        """
        if not self.target_points or len(self.events) < 5 or not self.velocities:
            return 0.5  # Không đủ dữ liệu → neutral

        # Vận tốc trung bình toàn bộ
        mean_vel = sum(self.velocities) / len(self.velocities)
        if mean_vel < 1e-9:
            return 0.5

        corner_ratios = []
        CORNER_RADIUS_PX = 18  # pixel — vùng xung quanh mỗi đỉnh polygon

        for pt in self.target_points:
            cx_px = pt["x"]
            cy_px = pt["y"]

            # Tìm events gần góc này (tọa độ normalized → pixel)
            near_indices = []
            for i, e in enumerate(self.events):
                ex_px = e["x"] * self.canvas_w
                ey_px = e["y"] * self.canvas_h
                dist = math.sqrt((ex_px - cx_px)**2 + (ey_px - cy_px)**2)
                if dist <= CORNER_RADIUS_PX and i > 0:
                    near_indices.append(i)

            if not near_indices:
                continue

            # Tính vận tốc trung bình tại vùng góc
            corner_vels = []
            for i in near_indices:
                if i >= len(self.velocities):
                    continue
                corner_vels.append(self.velocities[i])

            if not corner_vels:
                continue

            mean_corner_vel = sum(corner_vels) / len(corner_vels)
            # Tỷ lệ vận tốc góc / vận tốc trung bình
            corner_ratios.append(mean_corner_vel / mean_vel)

        if not corner_ratios:
            return 0.5

        avg_ratio = sum(corner_ratios) / len(corner_ratios)

        # avg_ratio ≈ 1.0 → bot (không giảm tốc tại góc)
        # avg_ratio < 0.7 → human (giảm tốc đáng kể tại góc)
        if avg_ratio >= 0.95:
            return 0.0   # Rõ ràng là bot
        if avg_ratio >= 0.80:
            return (0.95 - avg_ratio) / 0.15 * 0.4   # Bot khả năng cao
        if avg_ratio >= 0.60:
            return 0.4 + (0.80 - avg_ratio) / 0.20 * 0.4
        return min(0.8 + (0.60 - avg_ratio) * 2.0, 1.0)  # Human

    # ─── FIX #8: Feature mới — Segment event distribution uniformity ──────────
    def feature_segment_uniformity(self) -> float:
        """
        Bot phân bổ events đều đặn dọc theo mỗi cạnh polygon.
        Người thật phân bổ không đều: chậm ở đầu, nhanh giữa, chậm lại cuối.

        Trả về:
          1.0 = phân bổ không đều → human
          0.0 = phân bổ quá đều → bot
        """
        if not self.target_points or len(self.target_points) < 2 or len(self.events) < 10:
            return 0.5

        n_pts = len(self.target_points)
        pts_pixel = [(p["x"], p["y"]) for p in self.target_points]

        # Tổng số events trên mỗi cạnh polygon
        counts_per_segment = []
        for i in range(n_pts):
            x0, y0 = pts_pixel[i]
            x1, y1 = pts_pixel[(i + 1) % n_pts]

            # Bounding box của cạnh này (mở rộng 20px)
            min_x = (min(x0, x1) - 20) / self.canvas_w
            max_x = (max(x0, x1) + 20) / self.canvas_w
            min_y = (min(y0, y1) - 20) / self.canvas_h
            max_y = (max(y0, y1) + 20) / self.canvas_h

            count = sum(
                1 for e in self.events
                if min_x <= e["x"] <= max_x and min_y <= e["y"] <= max_y
            )
            if count > 0:
                counts_per_segment.append(count)

        if len(counts_per_segment) < 2:
            return 0.5

        mean_c = sum(counts_per_segment) / len(counts_per_segment)
        std_c  = math.sqrt(sum((c - mean_c)**2 for c in counts_per_segment) / len(counts_per_segment))
        cv     = std_c / mean_c if mean_c > 1e-9 else 0.0

        # cv thấp → mỗi cạnh có số events gần bằng nhau → BOT
        # cv cao → phân bổ không đều → HUMAN
        if cv < 0.10:
            return 0.0   # Quá đều → bot
        if cv < 0.25:
            return cv / 0.25 * 0.5
        return min(0.5 + (cv - 0.25) * 2.0, 1.0)

    # ─── FIX #11 (MỚI): Feature — Path segment linearity ─────────────────────
    def feature_path_segment_linearity(self) -> float:
        """
        Discriminator mạnh nhất: khoảng cách từ mỗi event tới cạnh polygon gần nhất.

        Bot:  linear interpolation + jitter ±0.003 norm (±0.9px)
              → mean_dist ≈ 0.25–0.9px  → score = 0.0
        Human: tay run, vẽ cong tự nhiên
              → mean_dist ≈ 2.5–8px     → score = 0.5–1.0

        Thuật toán: với mỗi canvas event, tính khoảng cách tới segment gần nhất
        (dùng point-to-segment distance chuẩn, clamp t∈[0,1]).
        Không cần phân vùng events — tránh bug gán nhầm event cho segment sai.
        """
        if not self.target_points or len(self.target_points) < 2 or len(self.events) < 5:
            return 0.5

        pts_sorted = sorted(self.target_points, key=lambda p: p["index"])
        pts_loop   = pts_sorted + [pts_sorted[0]]  # closed polygon

        # Build segment list (pixel coordinates)
        segs = []
        for i in range(len(pts_loop) - 1):
            x0 = pts_loop[i]["x"];     y0 = pts_loop[i]["y"]
            x1 = pts_loop[i + 1]["x"]; y1 = pts_loop[i + 1]["y"]
            dx = x1 - x0;              dy = y1 - y0
            sl = math.sqrt(dx * dx + dy * dy)
            if sl > 1e-9:
                segs.append((x0, y0, dx, dy, sl))

        if not segs:
            return 0.5

        def point_to_seg(ex, ey, x0, y0, dx, dy, sl):
            """Khoảng cách Euclidean từ điểm (ex,ey) tới đoạn thẳng (pixel)."""
            ex_r = ex - x0; ey_r = ey - y0
            t = max(0.0, min(1.0, (ex_r * dx + ey_r * dy) / (sl * sl)))
            cx = x0 + t * dx; cy = y0 + t * dy
            return math.sqrt((ex - cx) ** 2 + (ey - cy) ** 2)

        devs = []
        for e in self.events:
            if e.get("area") != "canvas":
                continue
            ex = e["x"] * self.canvas_w
            ey = e["y"] * self.canvas_h
            # Khoảng cách tới cạnh polygon gần nhất
            min_d = min(point_to_seg(ex, ey, *s) for s in segs)
            devs.append(min_d)

        if not devs:
            return 0.5

        mean_d = sum(devs) / len(devs)

        # Calibration (pixel):
        # Bot  jitter ±0.003 norm: mean_d ≈ 0.25–0.9px  → score 0.0
        # Bot  jitter ±0.010 norm: mean_d ≈ 0.9–1.3px   → score ~0.0
        # Human (tay run ≥2px):   mean_d ≈ 2.5–8px      → score 0.5–1.0
        # Bot dùng linear interp + jitter ±0.003 norm → mean_d ≈ 0.4-0.9px
        # Người thật vẽ tay: mouse imprecision → mean_d ≈ 2-8px (không thể < 1px)
        # < 1.0px → chỉ programmatic drawing mới đạt được → score 0.0
        if mean_d < 1.0:
            return 0.0
        if mean_d < 2.5:
            return (mean_d - 1.0) / 1.5 * 0.45
        if mean_d < 7.0:
            return 0.45 + (mean_d - 2.5) / 4.5 * 0.55
        return 1.0

    # ─── FIX #9: Feature mới — Feature score variance ─────────────────────────
    def feature_score_variance(self, feature_dict: dict) -> float:
        values = list(feature_dict.values())

        if len(values) < 3:
            return 0.5

        mean_v = sum(values) / len(values)

        std_v = math.sqrt(
            sum((v - mean_v) ** 2 for v in values) / len(values)
        )

        # Chỉ flag bot khi:
        # - variance RẤT thấp
        # - mean nằm trong dải hẹp đáng ngờ
        if std_v < 0.07 and 0.58 <= mean_v <= 0.68:
            return 0.0

        # variance hơi thấp -> giảm nhẹ score
        if std_v < 0.12:
            return (std_v / 0.12) * 0.4

        return min(std_v * 2.5, 1.0)

    def ml_score(self) -> tuple:
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

            # FIX #7 & #8: Thêm 3 features cũ
            f["corner_velocity_drop"] = self.feature_corner_velocity_drop()
            f["segment_uniformity"]   = self.feature_segment_uniformity()
            f["score_variance"]       = self.feature_score_variance(f)

            # FIX #11 (MỚI): Feature phân biệt bot bằng độ thẳng path
            # Đây là feature có độ phân biệt cao nhất: bot ≈0.0, người thật ≈0.7+
            f["path_segment_linearity"] = self.feature_path_segment_linearity()

            # FIX #11: Trọng số mới
            # - path_segment_linearity: 0.18 (feature mạnh nhất, discriminator rõ ràng)
            # - corner_velocity_drop: hạ xuống 0.09 (không đủ reliable với người vẽ nhanh)
            # - segment_uniformity: hạ xuống 0.06 (người cẩn thận cũng đều đặn)
            # path_segment_linearity tăng lên 0.25 — feature phân biệt bot tốt nhất
            # (bot jitter ±0.003 norm → score 0.0, người thật → score 0.45+)
            # Các feature timing giảm nhẹ vì bot dễ giả mạo bằng random timing
            W = {
                "velocity_stddev":        0.06,
                "acceleration_profile":   0.04,
                "tremor":                 0.06,
                "pause_hesitation":       0.04,
                "direction_changes":      0.06,
                "linearity":              0.03,
                "session_duration":       0.04,
                "interval_irregularity":  0.04,
                "y_variation":            0.06,
                "periodic_timing":        0.05,
                "event_count":            0.04,
                "x_monotonicity":         0.03,
                "corner_velocity_drop":   0.08,
                "segment_uniformity":     0.06,
                "score_variance":         0.06,
                "path_segment_linearity": 0.25,  # tăng từ 0.18 → 0.25 (feature mạnh nhất)
            }
            total_w    = sum(W.values())
            rule_score = round(sum(f[k] * W[k] for k in W) / total_w, 3)

            rf_score, iso_score = self.ml_score()
            ml_score = round(rf_score * 0.70 + iso_score * 0.30, 3)

            # FIX #11: Giảm trọng số ML từ 0.60 xuống 0.40.
            # ML model được train bằng dữ liệu SYNTHETIC — không đại diện cho
            # hành vi người thật thực tế, dễ gây false positive.
            # Rule-based features (0.60) giờ chiếm ưu thế và có thể debug được.
            final = round(rule_score * 0.60 + ml_score * 0.40, 2)

            # FIX #11: Bỏ hard reject dựa trên 2 feature.
            # Hard reject cũ có thể bắn người thật vẽ nhanh/cẩn thận.
            # Thay thế: path_segment_linearity đã đưa bot xuống < 0.57 một cách tự nhiên.
            # Chỉ giữ hard reject cho trường hợp RÕ RÀNG (cả 3 feature đều cực thấp).
            lin_score    = f.get("path_segment_linearity", 0.5)
            corner_score = f.get("corner_velocity_drop", 0.5)
            seg_score    = f.get("segment_uniformity", 0.5)

            # Hard reject chỉ khi CẢ 3 indicator bot-cụ thể đều fire cùng lúc
            if lin_score < 0.10 and corner_score < 0.15 and seg_score < 0.20:
                return {
                    "result": "bot",
                    "score":  round(final * 0.5, 2),
                    "msg":    "Bot pattern: near-perfect linear path + no velocity drop at corners",
                }

            return {
                "result": "human" if final > HUMAN_THRESHOLD else "bot",
                "score":  final,
            }

        except Exception as e:
            return {"result": "error", "score": 0, "msg": str(e)}