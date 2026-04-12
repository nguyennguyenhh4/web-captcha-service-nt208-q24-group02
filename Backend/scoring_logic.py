import math
import json

class BehaviorScorer:
    def __init__(self, payload):
        # --- Task 1: Input Handler ---
        self.events = payload.get("events", [])
        self.results = {}
        
    def calculate_metrics(self):
        # Kiểm tra điều kiện tối thiểu
        if len(self.events) < 5:
            return None

        # Tách mảng dữ liệu
        x = [e['x'] for e in self.events]
        y = [e['y'] for e in self.events]
        t = [e['t'] for e in self.events]

        # --- Task 2 & 3: Tính toán vật lý & Feature Extraction ---
        velocities = []
        accelerations = []
        
        for i in range(1, len(x)):
            dt = (t[i] - t[i-1]) or 1 # Tránh chia cho 0
            dist = math.sqrt((x[i] - x[i-1])**2 + (y[i] - y[i-1])**2)
            v = dist / dt
            velocities.append(v)
            
            if len(velocities) > 1:
                dv = velocities[-1] - velocities[-2]
                accelerations.append(dv / dt)

        # Tính độ lệch chuẩn của tốc độ (Speed Std) - Chỉ số quan trọng nhất
        avg_speed = sum(velocities) / len(velocities)
        speed_std = math.sqrt(sum((v - avg_speed)**2 for v in velocities) / len(velocities))
        
        # Kiểm tra độ thẳng (linearity)
        # Nếu y hầu như không đổi, khả năng cao là bot kéo slider bằng script
        y_diff = max(y) - min(y)

        self.results = {
            "avg_speed": avg_speed,
            "speed_std": speed_std,
            "accel_max": max(accelerations) if accelerations else 0,
            "y_variance": y_diff,
            "point_count": len(self.events)
        }
        return self.results

    def get_final_score(self):
        metrics = self.calculate_metrics()
        if not metrics:
            return {"score": 0, "result": "bot", "reason": "Too few events"}

        # --- Task 6: Scoring Logic ---
        score = 0
        # Người thật thường có tốc độ thay đổi (speed_std cao)
        if metrics['speed_std'] > 0.0001: score += 0.5
        # Người thật thường kéo hơi lệch tay (y không thẳng tuyệt đối)
        if metrics['y_variance'] > 0: score += 0.3
        # Người thật thường tạo ra nhiều điểm dữ liệu hơn do tay rung
        if metrics['point_count'] > 15: score += 0.2

        return {
            "score": round(score, 2),
            "result": "human" if score >= 0.6 else "bot",
            "metrics": metrics
        }

# --- Task 7: Output & Testing với Data giả ---
if __name__ == "__main__":
    # GIẢ LẬP DỮ LIỆU TỪ FRONTEND
    # 1. Mẫu dữ liệu giống BOT (kéo thẳng, tốc độ đều)
    bot_data = {
        "events": [{"x": i/10, "y": 0.5, "t": i*20} for i in range(10)]
    }

    # 2. Mẫu dữ liệu giống NGƯỜI (có rung lắc, tốc độ thay đổi)
    human_data = {
        "events": [
            {"x": 0.0, "y": 0.5, "t": 0},
            {"x": 0.12, "y": 0.51, "t": 25},
            {"x": 0.35, "y": 0.49, "t": 45},
            {"x": 0.75, "y": 0.52, "t": 80},
            {"x": 0.98, "y": 0.5, "t": 120},
            {"x": 1.0, "y": 0.5, "t": 150}
        ]
    }

    # IN KẾT QUẢ RA MÀN HÌNH
    for name, data in [("BOT CASE", bot_data), ("HUMAN CASE", human_data)]:
        scorer = BehaviorScorer(data)
        final = scorer.get_final_score()
        print(f"=== PHÂN TÍCH: {name} ===")
        print(json.dumps(final, indent=4))
        print("\n")