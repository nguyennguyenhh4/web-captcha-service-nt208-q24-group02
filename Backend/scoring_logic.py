# scoring_logic.py
import math

class BehaviorScorer:
    def __init__(self, raw_data):
        # Lấy mảng events từ payload
        self.events = raw_data.get("events", [])
        self.velocities = []
        self.accelerations = []

    def compute_physics(self):
        """Tính toán dựa trên x, y, t đã được chuẩn hóa từ JS"""
        if len(self.events) < 2:
            return

        for i in range(1, len(self.events)):
            p1 = self.events[i-1]
            p2 = self.events[i]

            # Tính khoảng cách trên hệ tọa độ chuẩn hóa (0 -> 1)
            dist = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
            
            # Tính khoảng cách thời gian (t)
            dt = (p2['t'] - p1['t'])
            
            # Tránh lỗi chia cho 0 (ZeroDivisionError -> Lỗi 500)
            if dt <= 0:
                continue 
            
            v = dist / dt
            self.velocities.append(v)

            # Tính gia tốc (nếu đã có 2 vận tốc)
            if len(self.velocities) > 1:
                dv = self.velocities[-1] - self.velocities[-2]
                self.accelerations.append(dv / dt)

    def analyze_behavior(self):
        try:
            if len(self.events) < 5:
                return {"result": "bot", "score": 0, "msg": "Quá ít dữ liệu"}

            self.compute_physics()

            if not self.velocities:
                return {"result": "bot", "score": 0.1, "msg": "Không tính được vận tốc"}

            # Tính độ lệch chuẩn của vận tốc (Đặc trưng quan trọng nhất)
            avg_v = sum(self.velocities) / len(self.velocities)
            variance = sum((v - avg_v)**2 for v in self.velocities) / len(self.velocities)
            std_dev = math.sqrt(variance)

            # Thuật toán quyết định: 
            # Người thường có vận tốc thay đổi liên tục (std_dev cao)
            # Bot thường có vận tốc không đổi (std_dev cực thấp)
            score = round(min(std_dev * 2000, 1.0), 2) # Nhân hệ số để ra thang điểm 1

            return {
                "result": "human" if score > 0.3 else "bot",
                "score": score,
                "debug": {"std_dev": std_dev, "event_count": len(self.events)}
            }
        except Exception as e:
            # Trả về lỗi dưới dạng JSON thay vì để Server crash lỗi 500
            return {"result": "error", "score": 0, "msg": str(e)}