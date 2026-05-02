import json, math, random, time, uuid, requests

API_VERIFY = "http://127.0.0.1:5000/captcha/verify"
API_INIT   = "http://127.0.0.1:5000/captcha/init"


def ease_in_out(t):
    return 3*t**2 - 2*t**3

def build_realistic_events(n=30):
    events, ts, px, py = [], 0, 0.0, 0.5
    for i in range(n):
        prog = i/(n-1)
        x    = round(ease_in_out(prog), 4)
        y    = round(0.5 + random.uniform(-0.008, 0.008), 4)
        dt   = random.randint(14, 26)
        if random.random() < 0.07:
            ts += random.randint(50, 120)
        ts  += dt
        dist = math.sqrt((x-px)**2 + (y-py)**2)
        events.append({
            "x": x, "y": y, "t": ts, "dt": dt,
            "speed": round(dist/max(dt,1), 6),
            "type": "mousemove" if i else "mousedown",
            "area": "puzzle",
        })
        px, py = x, y
    events.append({"x": 1.0, "y": 0.5, "t": ts+20, "dt": 20,
                   "speed": 0.0, "type": "mouseup", "area": "puzzle"})
    return events

def get_real_token(retries=3, delay=1.0):
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


def send(payload, label):
    try:
        r = requests.post(API_VERIFY, json=payload, timeout=5)
        d = r.json()
        verdict = d.get("result", "?")
        score   = d.get("score", "?")
        print(f"    HTTP {r.status_code} | result={verdict} | score={score}")
        return d
    except requests.exceptions.ConnectionError:
        print("    Backend offline — chạy offline")
        import sys, os; sys.path.insert(0, os.path.dirname(__file__))
        from scoring_logic import BehaviorScorer
        d = BehaviorScorer(payload).analyze_behavior()
        print(f"    (offline) result={d.get('result')} | score={d.get('score')}")
        return d
    except Exception as e:
        print(f"    {e}")
        return {}


def attack_replay(n=5):
    print("\n" + "="*60)
    print("ATTACK 1: REPLAY ATTACK")
    print("="*60)
    print("Strategy: capture realistic events once, replay N times with fresh tokens.\n")

    base_events = build_realistic_events(30)
    results = []
    for i in range(n):
        token, target_x = get_real_token()
        if token is None:                       
            print(f"  [{i+1}] Bỏ qua — không lấy được token")
            continue
        payload = {
            "token": token, "user_x": target_x,
            "startTime": int(time.time()*1000),
            "device": "mouse", "expectedShape": "tròn",
            "events": base_events,
        }
        print(f"  [{i+1}] token={token[:20]}…")
        results.append(send(payload, "replay"))
        time.sleep(7)                           

    passed = [r for r in results if r.get("result") == "human"]
    total  = len(results)
    print(f"\n  Result: {len(passed)}/{total} bypassed ({len(passed)/total*100:.0f}%)" if total else "\n  Result: không có kết quả")
    return results


def attack_coord_tamper(n=5):
    print("\n" + "="*60)
    print("ATTACK 2: COORDINATE TAMPERING")
    print("="*60)
    print("Strategy: generate events ending at x≈0, then shift all x to hit target.\n")

    results = []
    for i in range(n):
        token, target_x = get_real_token()
        if token is None:                   
            print(f"  [{i+1}] Bỏ qua — không lấy được token")
            continue
        target_norm = round(target_x / 270, 4)
        events = build_realistic_events(30)
        for e in events:
            e["x"] = round(min(1.0, e["x"] * target_norm), 4)
        payload = {
            "token": token, "user_x": target_x,
            "startTime": int(time.time()*1000),
            "device": "mouse", "expectedShape": "tròn",
            "events": events,
        }
        print(f"  [{i+1}] target_x={target_x} → user_x={target_x}")
        results.append(send(payload, "coord_tamper"))
        time.sleep(7)                     

    passed = [r for r in results if r.get("result") == "human"]
    total  = len(results)
    print(f"\n  Result: {len(passed)}/{total} bypassed ({len(passed)/total*100:.0f}%)" if total else "\n  Result: không có kết quả")
    return results


def attack_token_reuse(n=5):
    print("\n" + "="*60)
    print("ATTACK 3: TOKEN REUSE")
    print("="*60)
    print("Strategy: use a token on attempt 1, then try the exact same token again.\n")

    results = []
    for i in range(n):
        token, target_x = get_real_token()
        if token is None:                       
            print(f"  [{i+1}] Bỏ qua — không lấy được token")
            continue
        payload = {
            "token": token, "user_x": target_x,
            "startTime": int(time.time()*1000),
            "device": "mouse", "expectedShape": "tròn",
            "events": build_realistic_events(30),
        }
        print(f"  [{i+1}] First use  — token={token[:20]}…")
        r1 = send(payload, "first")
        print(f"  [{i+1}] Second use — same token:")
        r2 = send(payload, "second")
        results.append({"first": r1, "second": r2,
                        "second_blocked": r2.get("result") != "human"})
        time.sleep(7)                   

    blocked = sum(1 for r in results if r["second_blocked"])
    total   = len(results)
    print(f"\n  Result: {blocked}/{total} reuse attempts correctly blocked" if total else "\n  Result: không có kết quả")
    return results


def attack_spam(n=20, delay_ms=200):             
    print("\n" + "="*60)
    print("ATTACK 4: API SPAM")
    print("="*60)
    print(f"Strategy: send {n} requests with {delay_ms}ms delay between each.\n")

    results = []
    t0 = time.time()
    for i in range(n):
        token, target_x = get_real_token()
        if token is None:                      
            print(f"  [{i+1:02d}] Bỏ qua — không lấy được token")
            continue
        payload = {
            "token": token, "user_x": target_x,
            "startTime": int(time.time()*1000),
            "device": "mouse", "expectedShape": "vuông",
            "events": build_realistic_events(random.randint(20, 35)),
        }
        print(f"  [{i+1:02d}] ", end="", flush=True)
        results.append(send(payload, "spam"))
        time.sleep(delay_ms / 1000)

    elapsed = time.time() - t0
    passed  = [r for r in results if r.get("result") == "human"]
    errors  = [r for r in results if r.get("result") == "error"]
    total   = len(results)
    if total:
        print(f"\n  {total} requests in {elapsed:.2f}s ({total/elapsed:.1f} req/s)")
        print(f"  Bypassed: {len(passed)}/{total} | Errors: {len(errors)}/{total}")
    else:
        print("\n  Không có kết quả")
    return results


if __name__ == "__main__":
    print("╔" + "═"*58 + "╗")
    print("║   CAPTCHA ATTACK SUITE — Task 4                         ║")
    print("╚" + "═"*58 + "╝")

    r1 = attack_replay(n=5)
    r2 = attack_coord_tamper(n=5)
    r3 = attack_token_reuse(n=5)
    r4 = attack_spam(n=10, delay_ms=200)

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "replay":       r1,
        "coord_tamper": r2,
        "token_reuse":  r3,
        "spam":         r4,
    }
    with open("attack_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("\n  attack_results.json saved.")