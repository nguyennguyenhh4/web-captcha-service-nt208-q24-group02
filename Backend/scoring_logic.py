# scoring_logic.py
import math


class BehaviorScorer:
    def __init__(self, raw_data):
        all_events = raw_data.get("events", [])
        self._events_by_area = {}
        for e in all_events:
            area = e.get("area", "unknown")
            self._events_by_area.setdefault(area, []).append(e)

        self.events = sorted(all_events, key=lambda e: e.get("t", 0))

        self.velocities = []
        self.accelerations = []

    def compute_physics(self):
        if len(self.events) < 2:
            return

        for i in range(1, len(self.events)):
            p1 = self.events[i - 1]
            p2 = self.events[i]

            dist = math.sqrt((p2["x"] - p1["x"]) ** 2 + (p2["y"] - p1["y"]) ** 2)
            dt_ms = p2["t"] - p1["t"]

            if dt_ms <= 0:
                continue

            dt_s = dt_ms / 1000.0        
            v = dist / dt_s
            self.velocities.append(v)

            if len(self.velocities) > 1:
                dv = self.velocities[-1] - self.velocities[-2]
                self.accelerations.append(dv / dt_s)

    def feature_velocity_stddev(self):
        if not self.velocities:
            return 0.0

        avg_v = sum(self.velocities) / len(self.velocities)
        variance = sum((v - avg_v) ** 2 for v in self.velocities) / len(self.velocities)
        std_dev = math.sqrt(variance)

        return min(std_dev * 3.0, 1.0)

    def feature_acceleration_profile(self):
        if len(self.accelerations) < 2:
            return 0.0

        avg_a = sum(self.accelerations) / len(self.accelerations)
        variance = sum((a - avg_a) ** 2 for a in self.accelerations) / len(self.accelerations)
        std_dev_a = math.sqrt(variance)

        return min(std_dev_a * 0.5, 1.0)

    def feature_tremor(self):
        if len(self.events) < 3:
            return 0.0

        deviations = []
        for i in range(1, len(self.events) - 1):
            p1 = self.events[i - 1]
            p2 = self.events[i]
            p3 = self.events[i + 1]

            dx = p3["x"] - p1["x"]
            dy = p3["y"] - p1["y"]
            seg_len = math.sqrt(dx ** 2 + dy ** 2)

            if seg_len < 1e-9:
                continue
            cross = abs(dx * (p1["y"] - p2["y"]) - dy * (p1["x"] - p2["x"]))
            deviation = cross / seg_len
            deviations.append(deviation)

        if not deviations:
            return 0.0

        avg_deviation = sum(deviations) / len(deviations)

        return min(avg_deviation * 80.0, 1.0)

    def feature_pause_hesitation(self):
        if len(self.events) < 3:
            return 0.0

        dts = []
        for i in range(1, len(self.events)):
            dt = self.events[i]["t"] - self.events[i - 1]["t"]
            if dt > 0:
                dts.append(dt)

        if not dts:
            return 0.0

        sorted_dts = sorted(dts)
        mid = len(sorted_dts) // 2
        median_dt = sorted_dts[mid]

        pause_threshold = max(median_dt * 2, 100)  
        pause_count = sum(1 for dt in dts if dt > pause_threshold)

        ratio = pause_count / len(dts)

        if ratio == 0.0:
            return 0.0
        elif ratio <= 0.25:
            return min(ratio * 4.0, 1.0)  
        else:
            return max(1.0 - (ratio - 0.25) * 4.0, 0.0)  

    def feature_direction_changes(self):

        if len(self.events) < 3:
            return 0.0

        change_count = 0
        total_segments = 0
        THRESHOLD_RAD = math.radians(5)  

        for i in range(1, len(self.events) - 1):
            p0 = self.events[i - 1]
            p1 = self.events[i]
            p2 = self.events[i + 1]

            v1x, v1y = p1["x"] - p0["x"], p1["y"] - p0["y"]
            v2x, v2y = p2["x"] - p1["x"], p2["y"] - p1["y"]

            len1 = math.sqrt(v1x ** 2 + v1y ** 2)
            len2 = math.sqrt(v2x ** 2 + v2y ** 2)

            if len1 < 1e-9 or len2 < 1e-9:
                continue

            cos_angle = (v1x * v2x + v1y * v2y) / (len1 * len2)
            cos_angle = max(-1.0, min(1.0, cos_angle))  
            angle = math.acos(cos_angle)

            total_segments += 1
            if angle > THRESHOLD_RAD:
                change_count += 1

        if total_segments == 0:
            return 0.0

        ratio = change_count / total_segments
        return min(ratio * 1.5, 1.0)

    def feature_linearity(self):

        if len(self.events) < 2:
            return 0.0

        path_length = 0.0
        for i in range(1, len(self.events)):
            dx = self.events[i]["x"] - self.events[i - 1]["x"]
            dy = self.events[i]["y"] - self.events[i - 1]["y"]
            path_length += math.sqrt(dx ** 2 + dy ** 2)

        start, end = self.events[0], self.events[-1]
        displacement = math.sqrt(
            (end["x"] - start["x"]) ** 2 + (end["y"] - start["y"]) ** 2
        )

        if displacement < 1e-9:
            return 0.0

        ratio = path_length / displacement 

        return min((ratio - 1.0) * 10.0, 1.0)

    def analyze_behavior(self):
        try:
            if len(self.events) < 5:
                return {"result": "bot", "score": 0, "msg": "Quá ít dữ liệu"}

            puzzle_events = [e for e in self.events if e.get("area") == "puzzle"]
            canvas_events = [e for e in self.events if e.get("area") == "canvas"]

            self.events = canvas_events if len(canvas_events) >= 5 else self.events

            self.compute_physics()

            if not self.velocities:
                return {"result": "bot", "score": 0.1, "msg": "Không tính được vận tốc"}

            f1 = self.feature_velocity_stddev()
            f2 = self.feature_acceleration_profile()
            f3 = self.feature_tremor()
            f4 = self.feature_pause_hesitation()
            f5 = self.feature_direction_changes()
            f6 = self.feature_linearity()

            WEIGHTS = {
                "velocity_stddev":      0.25,
                "acceleration_profile": 0.10,
                "tremor":               0.20,
                "pause_hesitation":     0.15,
                "direction_changes":    0.20,
                "linearity":            0.10,
            }

            score = round(
                f1 * WEIGHTS["velocity_stddev"]      +
                f2 * WEIGHTS["acceleration_profile"] +
                f3 * WEIGHTS["tremor"]               +
                f4 * WEIGHTS["pause_hesitation"]     +
                f5 * WEIGHTS["direction_changes"]    +
                f6 * WEIGHTS["linearity"],
                2
            )

            return {
                "result": "human" if score > 0.35 else "bot",
                "score": score,
                "debug": {
                    "total_events":         len(self.events),
                    "puzzle_events":        len(puzzle_events),
                    "canvas_events":        len(canvas_events),
                    "f1_velocity_stddev":   round(f1, 3),
                    "f2_accel_profile":     round(f2, 3),
                    "f3_tremor":            round(f3, 3),
                    "f4_pause_hesitation":  round(f4, 3),
                    "f5_direction_changes": round(f5, 3),
                    "f6_linearity":         round(f6, 3),
                },
            }

        except Exception as e:
            return {"result": "error", "score": 0, "msg": str(e)}