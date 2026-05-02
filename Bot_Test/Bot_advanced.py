import json, math, time, uuid, random
import requests

API_URL    = "http://127.0.0.1:5000/captcha/verify"
API_INIT   = "http://127.0.0.1:5000/captcha/init"
N_REQUESTS = 10


def get_token(retries=3, delay=1.0):
    for attempt in range(retries):
        try:
            r = requests.get(API_INIT, timeout=3)
            if r.status_code == 429:
                print(f"    [!] Rate limited (429) — chờ {delay}s...")
                time.sleep(delay)
                continue
            d = r.json()
            token = d.get("token")
            if token:
                return token, d.get("target_x", 120)
            print(f"    [!] Không có token: {d}")
        except Exception as e:
            print(f"    [!] Lỗi lần {attempt+1}: {e}")
        time.sleep(delay)
    return None, None


def build_advanced_bot_v1(n_points=25):
    events = []
    t = 0
    for i in range(n_points):
        progress = i / (n_points - 1)
        x  = round(progress, 4)
        y  = round(0.50 + 0.005 * math.sin(progress * math.pi * 2), 4)
        dt = int(15 + 10 * math.sin(progress * math.pi * 3))
        t += dt
        dx    = 1 / (n_points - 1)
        speed = round(dx / max(dt, 1), 6)
        events.append({
            "x": x, "y": y, "t": t, "dt": dt, "speed": speed,
            "type": "mousemove" if i > 0 else "mousedown",
            "area": "puzzle",
        })
    return _wrap(events)


def ease_in_out(t):
    return 3 * t**2 - 2 * t**3


def build_advanced_bot_v2(n_points=30):
    events = []
    t = 0
    prev_x, prev_y = 0.0, 0.50
    for i in range(n_points):
        progress = i / (n_points - 1)
        x  = round(ease_in_out(progress), 4)
        y  = round(0.50 + random.uniform(-0.008, 0.008), 4)
        dt = random.randint(14, 26)
        if random.random() < 0.07:
            dt += random.randint(50, 120)
        t += dt
        dist  = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
        speed = round(dist / max(dt, 1), 6)
        events.append({
            "x": x, "y": y, "t": t, "dt": dt, "speed": speed,
            "type": "mousemove" if i > 0 else "mousedown",
            "area": "puzzle",
        })
        prev_x, prev_y = x, y
    return _wrap(events)


def build_advanced_bot_v3(target_x=0.62):
    overshoot = target_x + random.uniform(0.04, 0.10)
    events = []
    t = 0

    def add_segment(x_start, x_end, n, y_base=0.50):
        nonlocal t
        for i in range(n):
            prog = i / (n - 1)
            x    = round(x_start + (x_end - x_start) * ease_in_out(prog), 4)
            y    = round(y_base + random.uniform(-0.006, 0.006), 4)
            dt   = random.randint(15, 28)
            t   += dt
            events.append({
                "x": x, "y": y, "t": t, "dt": dt, "speed": 0.0,
                "type": "mousemove", "area": "puzzle",
            })

    add_segment(0.0, overshoot, n=20)
    t += random.randint(80, 180)
    add_segment(overshoot, target_x, n=10)
    events.append({
        "x": target_x, "y": 0.50,
        "t": t + 20, "dt": 20, "speed": 0.0,
        "type": "mouseup", "area": "puzzle",
    })
    return _wrap(events)


def _wrap(events):
    token, target_x = get_token()
    if token is None:
        return None
    return {
        "token":         token,
        "user_x":        target_x,
        "startTime":     int(time.time() * 1000),
        "device":        "mouse",
        "expectedShape": "tròn",
        "events":        events,
    }


def attack(payload, label, idx):
    print(f"\n[{idx+1}] {label} — {len(payload['events'])} events")
    try:
        r      = requests.post(API_URL, json=payload, timeout=5)
        result = r.json()
        verdict = result.get("result", "?")
        score   = result.get("score", "?")
        print(f"    HTTP {r.status_code} → result={verdict}  score={score}")
        return {"label": label, "result": verdict, "score": score}
    except requests.exceptions.ConnectionError:
        result  = offline_score(payload)
        verdict = result.get("result", "?")
        score   = result.get("score", "?")
        print(f"    (offline) result={verdict}  score={score}")
        return {"label": label, "result": verdict, "score": score}
    except Exception as e:
        print(f"   {e}")
        return None


def offline_score(payload):
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scoring_logic import BehaviorScorer
    return BehaviorScorer(payload).analyze_behavior()


if __name__ == "__main__":
    STRATEGIES = [
        ("v1 – Speed variation (sine)",    build_advanced_bot_v1),
        ("v2 – Ease-in-out + micro-pause", build_advanced_bot_v2),
        ("v3 – Overshoot + correction",    build_advanced_bot_v3),
    ]

    print("=" * 65)
    print("BOT NÂNG CAO — Bypass scoring bằng dữ liệu mô phỏng người thật")
    print("=" * 65)

    all_results = []
    for idx in range(N_REQUESTS):
        label, builder = random.choice(STRATEGIES)
        payload = builder()
        if payload is None:
            print(f"\n[{idx+1}] Bỏ qua — không lấy được token")
            time.sleep(1.0)
            continue
        res = attack(payload, label, idx)
        if res:
            all_results.append(res)
        time.sleep(7)  

    print("\n" + "=" * 65)
    print(" Tổng kết theo chiến lược:")
    for strat_label, _ in STRATEGIES:
        subset = [r for r in all_results if r["label"] == strat_label]
        if not subset:
            continue
        passed = [r for r in subset if r["result"] == "human"]
        print(f"   {strat_label}")
        print(f"     → {len(passed)}/{len(subset)} lần BYPASS ({len(passed)/len(subset)*100:.0f}%)")

    if all_results:
        total_passed = [r for r in all_results if r["result"] == "human"]
        print(f"\n   Tổng bypass: {len(total_passed)}/{len(all_results)} = "
              f"{len(total_passed)/len(all_results)*100:.1f}%")
    else:
        print("\n   Không có kết quả nào")