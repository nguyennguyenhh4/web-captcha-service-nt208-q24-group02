import json
import math
import time
import uuid
import random
import requests
 
API_URL = "http://127.0.0.1:5000/captcha/verify"
N_REQUESTS = 10
 
 
# ──────────────────────────────────────────────
#  Chiến lược 1: Speed variation đơn giản
# ──────────────────────────────────────────────
 
def build_advanced_bot_v1(n_points: int = 25) -> dict:
    """
    Tốc độ biến thiên theo sine để speed_std > 0.
    Y có drift nhỏ.
    """
    events = []
    t = 0
    y_start = 0.50
 
    for i in range(n_points):
        progress = i / (n_points - 1)
        x = round(progress, 4)
 
        # y drift: rất nhỏ nhưng > 0
        y = round(y_start + 0.005 * math.sin(progress * math.pi * 2), 4)
 
        # dt biến thiên: sine wave → tạo speed_std
        dt = int(15 + 10 * math.sin(progress * math.pi * 3))
        t += dt
 
        dx = 1 / (n_points - 1)
        speed = round(dx / max(dt, 1), 6)
 
        events.append({
            "x": x, "y": y,
            "t": t, "dt": dt, "speed": speed,
            "type": "mousemove" if i > 0 else "mousedown",
            "area": "puzzle"
        })
 
    return _wrap(events)
 
 
# ──────────────────────────────────────────────
#  Chiến lược 2: Ease-in-out + micro-pause
# ──────────────────────────────────────────────
 
def ease_in_out(t: float) -> float:
    return 3 * t**2 - 2 * t**3
 
 
def build_advanced_bot_v2(n_points: int = 30) -> dict:
    """
    Ease-in-out → tốc độ tự nhiên hơn.
    Thêm micro-pause ngẫu nhiên.
    """
    events = []
    t = 0
    prev_x, prev_y = 0.0, 0.50
 
    for i in range(n_points):
        progress = i / (n_points - 1)
        x = round(ease_in_out(progress), 4)
        y = round(0.50 + random.uniform(-0.008, 0.008), 4)   # jitter nhỏ
 
        base_dt = random.randint(14, 26)
        if random.random() < 0.07:    # micro-pause 7%
            base_dt += random.randint(50, 120)
        t += base_dt
 
        dist  = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
        speed = round(dist / max(base_dt, 1), 6)
 
        events.append({
            "x": x, "y": y,
            "t": t, "dt": base_dt, "speed": speed,
            "type": "mousemove" if i > 0 else "mousedown",
            "area": "puzzle"
        })
        prev_x, prev_y = x, y
 
    return _wrap(events)
 
 
# ──────────────────────────────────────────────
#  Chiến lược 3: Overshoot + correction
#  (người thật đôi khi kéo quá và kéo lại)
# ──────────────────────────────────────────────
 
def build_advanced_bot_v3(target_x: float = 0.62) -> dict:
    """
    Kéo quá target, dừng, kéo ngược lại một chút rồi dừng ở target.
    Rất khó phân biệt với người thật.
    """
    overshoot = target_x + random.uniform(0.04, 0.10)
    events = []
    t = 0
 
    def add_segment(x_start, x_end, n, y_base=0.50):
        nonlocal t
        for i in range(n):
            prog = i / (n - 1)
            x = round(x_start + (x_end - x_start) * ease_in_out(prog), 4)
            y = round(y_base + random.uniform(-0.006, 0.006), 4)
            dt = random.randint(15, 28)
            t += dt
            events.append({
                "x": x, "y": y,
                "t": t, "dt": dt, "speed": 0.0,
                "type": "mousemove", "area": "puzzle"
            })
 
    # Phase 1: kéo đến overshoot
    add_segment(0.0, overshoot, n=20)
    # Phase 2: pause nhỏ
    t += random.randint(80, 180)
    # Phase 3: kéo ngược về target
    add_segment(overshoot, target_x, n=10)
    # mouseup
    events.append({
        "x": target_x, "y": 0.50,
        "t": t + 20, "dt": 20, "speed": 0.0,
        "type": "mouseup", "area": "puzzle"
    })
 
    return _wrap(events)
 
 
# ──────────────────────────────────────────────
#  Helper
# ──────────────────────────────────────────────
 
def _wrap(events: list) -> dict:
    return {
        "token": "demo_" + uuid.uuid4().hex[:8],
        "startTime": int(time.time() * 1000),
        "device": "mouse",
        "expectedShape": "tròn",
        "events": events
    }
 
 
def attack(payload: dict, label: str, idx: int):
    print(f"\n[{idx+1}] {label} – {len(payload['events'])} events ...")
    try:
        r = requests.post(API_URL, json=payload, timeout=5)
        result = r.json()
        verdict = result.get("result") or ("human" if result.get("is_human") else "bot")
        score   = result.get("score", "?")
        print(f"    HTTP {r.status_code} → result={verdict}  score={score}")
        return {"label": label, "result": verdict, "score": score}
    except requests.exceptions.ConnectionError:
        result = offline_score(payload)
        verdict = result.get("result", "?")
        score   = result.get("score", "?")
        print(f"    (offline) result={verdict}  score={score}")
        return {"label": label, "result": verdict, "score": score}
    except Exception as e:
        print(f"    ❌ {e}")
        return None
 
 
def offline_score(payload: dict) -> dict:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        from scoring_logic import BehaviorScorer
        return BehaviorScorer(payload).get_final_score()
    except ImportError:
        return {"result": "unknown", "score": 0}
 
 
# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────
 
if __name__ == "__main__":
    STRATEGIES = [
        ("v1 – Speed variation (sine)",  build_advanced_bot_v1),
        ("v2 – Ease-in-out + micro-pause", build_advanced_bot_v2),
        ("v3 – Overshoot + correction",  lambda: build_advanced_bot_v3()),
    ]
 
    print("=" * 65)
    print("BOT NÂNG CAO – Bypass scoring bằng dữ liệu mô phỏng người thật")
    print("=" * 65)
 
    all_results = []
    for idx in range(N_REQUESTS):
        label, builder = random.choice(STRATEGIES)
        payload = builder()
        res = attack(payload, label, idx)
        if res:
            all_results.append(res)
        time.sleep(0.05)
 
    # Tổng kết theo chiến lược
    print("\n" + "=" * 65)
    print("📊 Tổng kết theo chiến lược:")
    for strat_label, _ in STRATEGIES:
        subset = [r for r in all_results if r["label"] == strat_label]
        if not subset:
            continue
        passed = [r for r in subset if r["result"] == "human"]
        print(f"   {strat_label}")
        print(f"     → {len(passed)}/{len(subset)} lần BYPASS ({len(passed)/len(subset)*100:.0f}%)")
 
    total_passed = [r for r in all_results if r["result"] == "human"]
    print(f"\n   Tổng bypass: {len(total_passed)}/{len(all_results)} = "
          f"{len(total_passed)/len(all_results)*100:.1f}%")
    print("\n⚠️  Xem report.md để biết điểm yếu cụ thể và cách khắc phục.")