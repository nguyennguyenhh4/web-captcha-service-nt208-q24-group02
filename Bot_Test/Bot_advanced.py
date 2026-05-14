"""
Bot_advanced.py — 4 chiến lược bypass behavioral scoring

CHIẾN LƯỢC:
  v1 — Gaussian timing (slow-start / fast-middle / slow-end)
  v2 — Ease-in-out + micro-pause 10% + y-jitter ±0.012
  v3 — Overshoot + tremor correction
  v4 — Speed burst giữa chừng
"""
import json, math, time, random
import requests

API_URL    = "http://127.0.0.1:5000/captcha/verify"
API_INIT   = "http://127.0.0.1:5000/captcha/init"
N_REQUESTS = 12
TRACK_WIDTH = 300


# ─── Token ────────────────────────────────────────────────────────────────────

def get_token(retries=5, delay=15.0):
    for attempt in range(retries):
        try:
            r = requests.get(API_INIT, timeout=3)
            if r.status_code == 429:
                print(f"    [!] Rate limited — chờ {delay:.0f}s...")
                time.sleep(delay)
                continue
            d = r.json()
            if d.get("token"):
                return (
                    d["token"],
                    d.get("target_x", 120),
                    d.get("targetPoints", []),
                    d.get("canvasWidth",  300),
                    d.get("canvasHeight", 150),
                )
            print(f"    [!] Không có token: {d}")
        except Exception as e:
            print(f"    [!] Lỗi lần {attempt+1}: {e}")
        time.sleep(2.0)
    return None, None, [], 300, 150


# ─── Canvas event builder ─────────────────────────────────────────────────────

def build_canvas_events(target_points, canvas_w=300, canvas_h=150, start_t=0):
    STEPS_PER_SEG = 12
    events = []
    t = start_t

    pts_px = sorted(target_points, key=lambda p: p["index"])
    n = len(pts_px)

    if n == 0:
        for i in range(24):
            angle = 2 * math.pi * i / 23
            x = round(0.5 + 0.25 * math.cos(angle), 4)
            y = round(0.5 + 0.25 * math.sin(angle), 4)
            dt = random.randint(28, 65)
            if random.random() < 0.09:
                dt += random.randint(60, 140)
            t += dt
            events.append({"x": x, "y": y, "t": t, "dt": dt,
                           "area": "canvas",
                           "type": "mousedown" if i == 0 else "mousemove"})
        t += 40
        last = events[-1]
        events.append({"x": last["x"], "y": last["y"], "t": t, "dt": 40,
                        "area": "canvas", "type": "mouseup"})
        return events, t

    def norm(px, py):
        return (
            max(0.0, min(1.0, round(px / canvas_w, 4))),
            max(0.0, min(1.0, round(py / canvas_h, 4))),
        )

    pts_norm = [norm(p["x"], p["y"]) for p in pts_px]
    pts_loop  = pts_norm + [pts_norm[0]]

    first_event = True
    for seg in range(len(pts_loop) - 1):
        x0, y0 = pts_loop[seg]
        x1, y1 = pts_loop[seg + 1]
        steps = STEPS_PER_SEG if seg < len(pts_loop) - 2 else STEPS_PER_SEG // 2

        for i in range(steps):
            prog = i / max(steps - 1, 1)
            x = round(x0 + (x1 - x0) * prog + random.uniform(-0.003, 0.003), 4)
            y = round(y0 + (y1 - y0) * prog + random.uniform(-0.003, 0.003), 4)
            x = max(0.0, min(1.0, x))
            y = max(0.0, min(1.0, y))
            dt = random.randint(28, 65)
            if random.random() < 0.09:
                dt += random.randint(60, 140)
            t += dt
            etype = "mousedown" if first_event else "mousemove"
            first_event = False
            events.append({"x": x, "y": y, "t": t, "dt": dt,
                           "area": "canvas", "type": etype})

    close_x, close_y = pts_norm[0]
    t += 40
    events.append({"x": close_x, "y": close_y, "t": t, "dt": 40,
                   "area": "canvas", "type": "mouseup"})
    return events, t


# ─── Puzzle event builders ────────────────────────────────────────────────────

def ease_in_out(t):
    return 3 * t**2 - 2 * t**3


def build_v1_puzzle(target_norm, n_points=28, start_t=0):
    events = []
    t = start_t
    for i in range(n_points):
        progress = i / (n_points - 1)
        x  = round(progress * target_norm, 4)   # ← scale về target_norm
        y  = round(0.50 + random.uniform(-0.010, 0.010), 4)
        mean_dt = 30 - 15 * math.sin(progress * math.pi)
        dt = max(8, int(random.gauss(mean_dt, 5)))
        if random.random() < 0.06:
            dt += random.randint(40, 100)
        t += dt
        speed = round((target_norm / (n_points - 1)) / max(dt, 1), 6)
        events.append({"x": x, "y": y, "t": t, "dt": dt, "speed": speed,
                       "type": "mousemove" if i > 0 else "mousedown",
                       "area": "puzzle"})
    # mouseup tại đúng target_norm
    t += random.randint(15, 30)
    events.append({"x": target_norm, "y": round(0.50 + random.uniform(-0.01, 0.01), 4),
                   "t": t, "dt": t - events[-1]["t"],
                   "speed": 0.0, "type": "mouseup", "area": "puzzle"})
    return events


def build_v2_puzzle(target_norm, n_points=32, start_t=0):
    events = []
    t = start_t
    prev_x, prev_y = 0.0, 0.50
    for i in range(n_points):
        progress = i / (n_points - 1)
        x  = round(ease_in_out(progress) * target_norm, 4)   # ← scale
        y  = round(0.50 + random.uniform(-0.012, 0.012), 4)
        dt = random.randint(13, 28)
        if random.random() < 0.10:
            dt += random.randint(55, 130)
        t += dt
        dist  = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
        speed = round(dist / max(dt, 1), 6)
        events.append({"x": x, "y": y, "t": t, "dt": dt, "speed": speed,
                       "type": "mousemove" if i > 0 else "mousedown",
                       "area": "puzzle"})
        prev_x, prev_y = x, y
    t += random.randint(15, 30)
    events.append({"x": target_norm, "y": round(0.50 + random.uniform(-0.01, 0.01), 4),
                   "t": t, "dt": t - events[-1]["t"],
                   "speed": 0.0, "type": "mouseup", "area": "puzzle"})
    return events


def build_v3_puzzle(target_norm, start_t=0):
    overshoot = min(1.0, target_norm + random.uniform(0.04, 0.10))
    events = []
    t = start_t

    def add_segment(x0, x1, n, y_base=0.50):
        nonlocal t
        for i in range(n):
            prog = i / max(n - 1, 1)
            x = round(x0 + (x1 - x0) * ease_in_out(prog), 4)
            y = round(y_base + random.uniform(-0.004, 0.004) +
                      random.gauss(0, 0.002), 4)
            dt = random.randint(14, 30)
            t += dt
            events.append({"x": x, "y": y, "t": t, "dt": dt, "speed": 0.0,
                           "type": "mousemove", "area": "puzzle"})

    # mousedown đầu tiên
    t += 0
    events.append({"x": 0.0, "y": 0.50, "t": t, "dt": 0, "speed": 0.0,
                   "type": "mousedown", "area": "puzzle"})

    add_segment(0.0, overshoot, n=22)
    t += random.randint(80, 200)   # pause tại overshoot
    add_segment(overshoot, target_norm, n=10)

    t += 20
    events.append({"x": target_norm, "y": 0.50, "t": t, "dt": 20,
                   "speed": 0.0, "type": "mouseup", "area": "puzzle"})
    return events


def build_v4_puzzle(target_norm, n_points=26, start_t=0):
    events = []
    t = start_t
    burst_start = int(n_points * 0.40)
    burst_end   = int(n_points * 0.60)
    prev_x, prev_y = 0.0, 0.50

    for i in range(n_points):
        progress = i / (n_points - 1)
        x  = round(ease_in_out(progress) * target_norm, 4)   # ← scale
        y  = round(0.50 + random.uniform(-0.010, 0.010), 4)
        if burst_start <= i < burst_end:
            dt = random.randint(7, 13)
        else:
            dt = random.randint(20, 40)
        if random.random() < 0.06:
            dt += random.randint(50, 110)
        t += dt
        dist  = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
        speed = round(dist / max(dt, 1), 6)
        events.append({"x": x, "y": y, "t": t, "dt": dt, "speed": speed,
                       "type": "mousemove" if i > 0 else "mousedown",
                       "area": "puzzle"})
        prev_x, prev_y = x, y

    t += 20
    events.append({"x": target_norm, "y": 0.50, "t": t, "dt": 20,
                   "speed": 0.0, "type": "mouseup", "area": "puzzle"})
    return events


# ─── Wrap payload ────────────────────────────────────────────────────────────

def _wrap(puzzle_events_fn, **kwargs):
    token, target_x, target_points, canvas_w, canvas_h = get_token()
    if token is None:
        return None

    think_time = random.uniform(0.8, 2.5)
    print(f"    think={think_time:.2f}s  target_x={target_x}"
          f"  pts={len(target_points)} ...", end=" ", flush=True)
    time.sleep(think_time)

    # Canvas events — vẽ đúng polygon
    canvas_evts, canvas_end = build_canvas_events(
        target_points, canvas_w, canvas_h, start_t=0
    )

    # Puzzle events — bắt đầu sau canvas + gap
    gap     = random.randint(300, 700)
    p_start = canvas_end + gap

    #target_norm nhất quán cho tất cả builders
    target_norm = round(target_x / TRACK_WIDTH, 4)

    puzzle_evts = puzzle_events_fn(
        target_norm=target_norm, start_t=p_start, **kwargs
    )

    return {
        "token":         token,
        "user_x":        target_x,
        "startTime":     int(time.time() * 1000),
        "device":        "mouse",
        "expectedShape": f"polygon_{len(target_points)}pts",
        "events":        canvas_evts + puzzle_evts,
    }


def build_advanced_bot_v1(): return _wrap(build_v1_puzzle)
def build_advanced_bot_v2(): return _wrap(build_v2_puzzle)
def build_advanced_bot_v3(): return _wrap(build_v3_puzzle)
def build_advanced_bot_v4(): return _wrap(build_v4_puzzle)


# ─── Attack ───────────────────────────────────────────────────────────────────

def attack(payload, label, idx):
    n_canvas = sum(1 for e in payload["events"] if e.get("area") == "canvas")
    n_puzzle = sum(1 for e in payload["events"] if e.get("area") == "puzzle")
    dur = payload["events"][-1]["t"] - payload["events"][0]["t"]
    print(f"\n[{idx+1}] {label} — canvas={n_canvas} puzzle={n_puzzle} dur={dur}ms")
    try:
        r       = requests.post(API_URL, json=payload, timeout=5)
        result  = r.json()
        verdict = result.get("result", "?")
        score   = result.get("score", "?")
        msg     = result.get("msg", "")
        print(f"    HTTP {r.status_code} → result={verdict}  score={score}"
              + (f"  [{msg}]" if msg else ""))
        return {"label": label, "result": verdict, "score": score}
    except requests.exceptions.ConnectionError:
        result  = offline_score(payload)
        verdict = result.get("result", "?")
        score   = result.get("score", "?")
        print(f"    (offline) result={verdict}  score={score}")
        return {"label": label, "result": verdict, "score": score}
    except Exception as e:
        print(f"    {e}")
        return None


def offline_score(payload):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Backend"))
    from scoring_logic import BehaviorScorer
    return BehaviorScorer(payload).analyze_behavior()


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    STRATEGIES = [
        ("v1 – Gaussian timing",               build_advanced_bot_v1),
        ("v2 – Ease-in-out + micro-pause 10%", build_advanced_bot_v2),
        ("v3 – Overshoot + tremor correction", build_advanced_bot_v3),
        ("v4 – Speed burst",                   build_advanced_bot_v4),
    ]

    print("=" * 70)
    print("BOT NÂNG CAO — Bypass scoring mô phỏng người thật")
    print("=" * 70)

    all_results = []
    for idx in range(N_REQUESTS):
        label, builder = STRATEGIES[idx % len(STRATEGIES)]
        print(f"\n[{idx+1}] Đang build {label}...")
        payload = builder()
        if payload is None:
            print(f"  Bỏ qua — không lấy được token")
            time.sleep(2.0)
            continue
        res = attack(payload, label, idx)
        if res:
            all_results.append(res)
        time.sleep(random.uniform(4.0, 6.0))

    print("\n" + "=" * 70)
    print(" Tổng kết theo chiến lược:")
    for strat_label, _ in STRATEGIES:
        subset = [r for r in all_results if r["label"] == strat_label]
        if not subset:
            continue
        passed = [r for r in subset if r["result"] == "human"]
        scores = [r["score"] for r in subset if isinstance(r.get("score"), (int, float))]
        avg_s  = round(sum(scores) / len(scores), 3) if scores else "n/a"
        print(f"   {strat_label}")
        print(f"     → {len(passed)}/{len(subset)} BYPASS ({len(passed)/len(subset)*100:.0f}%)  "
              f"avg_score={avg_s}")

    if all_results:
        total_passed = [r for r in all_results if r["result"] == "human"]
        scores_all   = [r["score"] for r in all_results if isinstance(r.get("score"), (int, float))]
        print(f"\n   Tổng bypass: {len(total_passed)}/{len(all_results)} = "
              f"{len(total_passed)/len(all_results)*100:.1f}%")
        if scores_all:
            print(f"   Score: avg={sum(scores_all)/len(scores_all):.3f}  "
                  f"min={min(scores_all):.3f}  max={max(scores_all):.3f}")
    else:
        print("\n   Không có kết quả nào")