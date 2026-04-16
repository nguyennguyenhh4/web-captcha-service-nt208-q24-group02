import json
import math
import time
import uuid
import random
import requests          # pip install requests
 
API_URL = "http://127.0.0.1:5000/captcha/verify"
N_REQUESTS = 10          # số lần tấn công
 
 
# ──────────────────────────────────────────────
#  Sinh payload bot đơn giản
# ──────────────────────────────────────────────
 
def build_simple_bot_payload(
    n_points: int = 12,
    interval_ms: int = 20,
    y_fixed: float = 0.5
) -> dict:
    """
    Kéo thẳng từ x=0 đến x=1 với tốc độ hoàn toàn đều.
    Đây là dấu hiệu rõ nhất của bot:
      - y không đổi
      - dt đều
      - speed đều
    """
    events = []
    for i in range(n_points):
        x = round(i / (n_points - 1), 4)
        t = i * interval_ms
        dt = interval_ms if i > 0 else 0
 
        # Tốc độ: dx/dt (không đổi)
        dx = round(1 / (n_points - 1), 4)
        speed = round(dx / interval_ms, 4) if i > 0 else 0.0
 
        events.append({
            "x": x,
            "y": y_fixed,
            "t": t,
            "dt": dt,
            "speed": speed,
            "type": "mousemove" if i > 0 else "mousedown",
            "area": "puzzle"
        })
 
    # mouseup ở cuối
    events.append({
        "x": 1.0, "y": y_fixed,
        "t": n_points * interval_ms,
        "dt": interval_ms, "speed": 0.0,
        "type": "mouseup", "area": "puzzle"
    })
 
    return {
        "token": "demo_" + uuid.uuid4().hex[:8],
        "startTime": int(time.time() * 1000),
        "device": "mouse",
        "expectedShape": "vuông",
        "events": events
    }
 
 
# ──────────────────────────────────────────────
#  Gửi request và in kết quả
# ──────────────────────────────────────────────
 
def attack(payload: dict, idx: int):
    print(f"\n[{idx+1}] Gửi bot đơn giản – {len(payload['events'])} events ...")
    print(f"    Token: {payload['token']}")
    try:
        r = requests.post(API_URL, json=payload, timeout=5)
        result = r.json()
        print(f"    ✅ Response HTTP {r.status_code}: {json.dumps(result)}")
        return result
    except requests.exceptions.ConnectionError:
        print("    ⚠️  Không kết nối được backend.")
        print("    📦 Payload (offline test):")
        print(json.dumps(payload, indent=6))
        # Chạy offline qua scoring_logic
        return offline_score(payload)
    except Exception as e:
        print(f"    ❌ Lỗi: {e}")
        return None
 
 
def offline_score(payload: dict) -> dict:
    """Gọi trực tiếp BehaviorScorer khi không có backend."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        from scoring_logic import BehaviorScorer
        scorer = BehaviorScorer(payload)
        return scorer.get_final_score()
    except ImportError:
        return {"note": "scoring_logic không tìm thấy – chạy riêng file này"}
 
 
# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────
 
if __name__ == "__main__":
    print("=" * 60)
    print("BOT ĐƠN GIẢN – Tấn công /captcha/verify")
    print("=" * 60)
 
    results = []
    for i in range(N_REQUESTS):
        payload = build_simple_bot_payload(
            n_points=random.randint(8, 13),
            interval_ms=20,
            y_fixed=0.5
        )
        res = attack(payload, i)
        if res:
            results.append(res)
        time.sleep(0.1)
 
    # Tổng kết
    print("\n" + "=" * 60)
    passed  = [r for r in results if r.get("result") == "human" or r.get("is_human") is True]
    blocked = [r for r in results if r.get("result") == "bot"   or r.get("is_human") is False]
    print(f"📊 Kết quả sau {len(results)} lần thử:")
    print(f"   Qua được  (False Negative): {len(passed)}")
    print(f"   Bị chặn   (True Positive) : {len(blocked)}")
    print(f"   Tỉ lệ bypass: {len(passed)/len(results)*100:.1f}%")