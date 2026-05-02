import json, math, time, uuid, random
import requests

API_URL  = "http://127.0.0.1:5000/captcha/verify"
API_INIT = "http://127.0.0.1:5000/captcha/init"
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


def build_simple_bot_payload(token, user_x, n_points=12, interval_ms=20, y_fixed=0.5):
    events = []
    for i in range(n_points):
        x     = round(i / (n_points - 1), 4)
        t     = i * interval_ms
        dt    = interval_ms if i > 0 else 0
        dx    = round(1 / (n_points - 1), 4)
        speed = round(dx / interval_ms, 4) if i > 0 else 0.0
        events.append({
            "x": x, "y": y_fixed,
            "t": t, "dt": dt, "speed": speed,
            "type": "mousemove" if i > 0 else "mousedown",
            "area": "puzzle",
        })
    events.append({
        "x": 1.0, "y": y_fixed,
        "t": n_points * interval_ms, "dt": interval_ms,
        "speed": 0.0, "type": "mouseup", "area": "puzzle",
    })
    return {
        "token":         token,
        "user_x":        user_x,
        "startTime":     int(time.time() * 1000),
        "device":        "mouse",
        "expectedShape": "vuông",
        "events":        events,
    }


def attack(payload, idx):
    print(f"\n[{idx+1}] Gửi bot đơn giản — {len(payload['events'])} events")
    print(f"    Token: {payload['token']}")
    try:
        r = requests.post(API_URL, json=payload, timeout=5)
        result = r.json()
        print(f"    HTTP {r.status_code}: {json.dumps(result)}")
        return result
    except requests.exceptions.ConnectionError:
        print("    Backend offline — chạy offline")
        return offline_score(payload)
    except Exception as e:
        print(f"    Lỗi: {e}")
        return None


def offline_score(payload):
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scoring_logic import BehaviorScorer
    return BehaviorScorer(payload).analyze_behavior()


if __name__ == "__main__":
    print("=" * 60)
    print("BOT ĐƠN GIẢN — Tấn công /captcha/verify")
    print("=" * 60)

    results = []
    for i in range(N_REQUESTS):
        token, target_x = get_token()
        if token is None:
            print(f"\n[{i+1}] Bỏ qua — không lấy được token")
            time.sleep(1.0)
            continue
        payload = build_simple_bot_payload(
            token=token,
            user_x=target_x,
            n_points=random.randint(8, 13),
            interval_ms=20,
            y_fixed=0.5,
        )
        res = attack(payload, i)
        if res:
            results.append(res)
        time.sleep(7)  

    print("\n" + "=" * 60)
    if results:
        passed  = [r for r in results if r.get("result") == "human"]
        blocked = [r for r in results if r.get("result") == "bot"]
        print(f" Kết quả {len(results)} lần:")
        print(f"   Qua được  (False Negative): {len(passed)}")
        print(f"   Bị chặn   (True Positive) : {len(blocked)}")
        print(f"   Bypass rate: {len(passed)/len(results)*100:.1f}%")
    else:
        print(" Không có kết quả nào")