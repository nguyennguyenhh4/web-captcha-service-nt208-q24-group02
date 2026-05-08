import math
from typing import List, Tuple


class BehaviorAnalyzer:
    """
    Phân tích mảng events[] ghi lại từ frontend (capture.js).

    Mỗi event có dạng:
        { x, y, t (timestamp ms), dt (ms từ event trước), speed (px/ms) }

    Các kiểm tra:
        1. Tốc độ trung bình — quá nhanh (> 5 px/ms) → bot tự động
        2. Tốc độ trung bình — quá thấp (< 0.001 px/ms) → teleport giả lập
        3. Thay đổi hướng — di chuyển thẳng tuyệt đối → bot theo đường thẳng
        4. Khoảng cách thực tế — events tụ lại 1 điểm → click giả
    """

    @staticmethod
    def analyze(
        events: List[dict],
        max_avg_speed: float,
        min_avg_speed: float,
        min_direction_changes: int,
    ) -> Tuple[bool, str]:
        """
        Trả về (passed: bool, reason: str).
        passed = True nghĩa là hành vi có vẻ của người thật.
        """

        if len(events) < 2:
            return False, "Quá ít điểm hành vi để phân tích"

        speeds   = []
        angles   = []
        prev_angle = None

        for i, ev in enumerate(events):
            # Lấy tốc độ từ frontend (đã tính sẵn trong capture.js)
            speed = ev.get("speed", 0)
            if isinstance(speed, (int, float)) and speed >= 0:
                speeds.append(speed)

            # Tính góc di chuyển giữa 2 điểm liên tiếp
            if i > 0:
                prev = events[i - 1]
                dx = ev.get("x", 0) - prev.get("x", 0)
                dy = ev.get("y", 0) - prev.get("y", 0)
                if dx != 0 or dy != 0:
                    angle = math.atan2(dy, dx)
                    angles.append(angle)

        # ── Kiểm tra 1: tốc độ trung bình ──────────────────────────
        if speeds:
            avg_speed = sum(speeds) / len(speeds)

            if avg_speed > max_avg_speed:
                return False, f"Tốc độ di chuyển bất thường ({avg_speed:.3f} px/ms)"

            if avg_speed < min_avg_speed and avg_speed > 0:
                return False, f"Tốc độ di chuyển quá thấp, có thể giả lập"

        # ── Kiểm tra 2: thay đổi hướng ──────────────────────────────
        if len(angles) >= 2:
            direction_changes = 0
            for i in range(1, len(angles)):
                delta = abs(angles[i] - angles[i - 1])
                # Chuẩn hóa góc về [0, π]
                delta = min(delta, 2 * math.pi - delta)
                if delta > 0.15:   # ~8.6 độ, lọc nhiễu nhỏ
                    direction_changes += 1

            if direction_changes < min_direction_changes:
                return False, "Quỹ đạo di chuyển quá thẳng, nghi ngờ bot"

        # ── Kiểm tra 3: tổng khoảng cách thực tế ────────────────────
        total_dist = 0.0
        for i in range(1, len(events)):
            dx = events[i].get("x", 0) - events[i-1].get("x", 0)
            dy = events[i].get("y", 0) - events[i-1].get("y", 0)
            total_dist += math.sqrt(dx*dx + dy*dy)

        if total_dist < 5:
            return False, "Không phát hiện di chuyển thực sự"

        return True, "Hành vi bình thường"

    @staticmethod
    def summary(events: List[dict]) -> dict:
        """
        Trả về bản tóm tắt thống kê để debug / logging.
        """
        if not events:
            return {}

        speeds = [ev.get("speed", 0) for ev in events if "speed" in ev]
        xs     = [ev.get("x", 0) for ev in events]
        ys     = [ev.get("y", 0) for ev in events]

        return {
            "event_count": len(events),
            "avg_speed":   round(sum(speeds) / len(speeds), 2) if speeds else 0,
            "max_speed":   round(max(speeds), 2) if speeds else 0,
            "x_range":     round(max(xs) - min(xs), 2),
            "y_range":     round(max(ys) - min(ys), 2),
        }
