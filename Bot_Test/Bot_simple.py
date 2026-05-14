"""
Bot_simple.py — Bot đơn giản với trajectory tuyến tính 
"""
import json, math, time, random
import requests

API_URL  = "http://127.0.0.1:5000/captcha/verify"
API_INIT = "http://127.0.0.1:5000/captcha/init"
N_REQUESTS = 10
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
                    d.get("targetPoints", []),   # ← MỚI: polygon server sinh ra
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
        # Fallback: vẽ hình tròn nhỏ nếu không có target_points
        for i in range(24):
            angle = 2 * math.pi * i / 23
            x = round(0.5 + 0.25 * math.cos(angle), 4)
            y = round(0.5 + 0.25 * math.sin(angle), 4)
            dt = random.randint(28, 65)
            t += dt
            events.append({"x": x, "y": y, "t": t, "dt": dt,
                           "area": "canvas",
                           "type": "mousedown" if i == 0 else "mousemove"})
        t += 40
        last = events[-1]
        events.append({"x": last["x"], "y": last["y"], "t": t, "dt": 40,
                        "area": "canvas", "type": "mouseup"})
        return events, t

    # Chuẩn hóa toạ độ pixel → [0,1]
    def norm(px, py):
        return (
            max(0.0, min(1.0, round(px / canvas_w, 4))),
            max(0.0, min(1.0, round(py / canvas_h, 4))),
        )

    # Tạo danh sách điểm khép kín: 0→1→…→n-1→0
    pts_norm = [norm(p["x"], p["y"]) for p in pts_px]
    pts_loop  = pts_norm + [pts_norm[0]]   # khép kín

    first_event = True
    for seg in range(len(pts_loop) - 1):
        x0, y0 = pts_loop[seg]
        x1, y1 = pts_loop[seg + 1]
        steps = STEPS_PER_SEG if seg < len(pts_loop) - 2 else STEPS_PER_SEG // 2

        for i in range(steps):
            prog = i / max(steps - 1, 1)
            # Nội suy tuyến tính + jitter nhỏ (≤ 0.003 norm ≈ 0.9px << HIT_RADIUS=12px)
            x = round(x0 + (x1 - x0) * prog + random.uniform(-0.003, 0.003), 4)
            y = round(y0 + (y1 - y0) * prog + random.uniform(-0.003, 0.003), 4)
            x = max(0.0, min(1.0, x))
            y = max(0.0, min(1.0, y))

            dt = random.randint(28, 65)
            if random.random() < 0.08:
                dt += random.randint(60, 130)
            t += dt

            etype = "mousedown" if first_event else "mousemove"
            first_event = False
            events.append({"x": x, "y": y, "t": t, "dt": dt,
                           "area": "canvas", "type": etype})

    # mouseup khép kín tại điểm đầu (đảm bảo CLOSE_RADIUS ≤ 15px)
    close_x, close_y = pts_norm[0]
    t += 40
    events.append({"x": close_x, "y": close_y, "t": t, "dt": 40,
                   "area": "canvas", "type": "mouseup"})
    return events, t


# ─── Puzzle event builder ─────────────────────────────────────────────────────

def build_simple_bot_payload(token, target_x, target_points,
                              canvas_w, canvas_h, n_points=14):
    """
    [SỬA LỖI #1] Puzzle events kết thúc tại x = target_x / TRACK_WIDTH.
    Bản cũ kết thúc tại x=1.0 trong khi user_x/300 ≠ 1.0 → mismatch.
    """
    target_norm = round(target_x / TRACK_WIDTH, 4)

    # 1. Canvas events — vẽ đúng polygon server yêu cầu
    canvas_evts, canvas_end = build_canvas_events(
        target_points, canvas_w, canvas_h, start_t=0
    )

    # 2. Puzzle events — bắt đầu sau canvas + khoảng dừng ngắn
    gap     = random.randint(300, 600)
    p_start = canvas_end + gap
    puzzle_evts = []
    t = p_start
    y_base = 0.5

    for i in range(n_points):
        x  = round(i / (n_points - 1) * target_norm, 4)
        dt = random.randint(14, 35) if i > 0 else 0
        if i > 0 and random.random() < 0.07:
            dt += random.randint(50, 120)   # micro-pause
        t += dt
        y = round(y_base + random.uniform(-0.015, 0.015), 4)
        speed = round((target_norm / (n_points - 1)) / max(dt, 1), 4) if i > 0 else 0.0
        puzzle_evts.append({
            "x": x, "y": y, "t": t, "dt": dt, "speed": speed,
            "type": "mousemove" if i > 0 else "mousedown",
            "area": "puzzle",
        })

    t += random.randint(15, 30)
    puzzle_evts.append({
        "x": target_norm,
        "y": round(y_base + random.uniform(-0.01, 0.01), 4),
        "t": t, "dt": t - puzzle_evts[-1]["t"],
        "speed": 0.0, "type": "mouseup", "area": "puzzle",
    })

    return {
        "token":         token,
        "user_x":        target_x,    # pixel — server so sánh với target_x ±10
        "startTime":     int(time.time() * 1000),
        "device":        "mouse",
        "expectedShape": f"polygon_{len(target_points)}pts",
        "events":        canvas_evts + puzzle_evts,
    }


# ─── Attack ───────────────────────────────────────────────────────────────────

def attack(payload, idx):
    n_canvas = sum(1 for e in payload["events"] if e.get("area") == "canvas")
    n_puzzle = sum(1 for e in payload["events"] if e.get("area") == "puzzle")
    dur = payload["events"][-1]["t"] - payload["events"][0]["t"]
    n_pts = payload.get("expectedShape", "?")
    print(f"\n[{idx+1}] shape={n_pts}  canvas={n_canvas} puzzle={n_puzzle} dur={dur}ms")
    try:
        r      = requests.post(API_URL, json=payload, timeout=5)
        result = r.json()
        verdict = result.get("result", "?")
        score   = result.get("score", "?")
        msg     = result.get("msg", "")
        print(f"    HTTP {r.status_code} → result={verdict}  score={score}"
              + (f"  [{msg}]" if msg else ""))
        return result
    except requests.exceptions.ConnectionError:
        print("    Backend offline — chạy offline")
        return offline_score(payload)
    except Exception as e:
        print(f"    Lỗi: {e}")
        return None


def offline_score(payload):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Backend"))
    from scoring_logic import BehaviorScorer
    return BehaviorScorer(payload).analyze_behavior()


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("BOT ĐƠN GIẢN ")
    print("=" * 60)

    results = []
    for i in range(N_REQUESTS):
        token, target_x, target_points, canvas_w, canvas_h = get_token()
        if token is None:
            print(f"\n[{i+1}] Bỏ qua — không lấy được token")
            time.sleep(2.0)
            continue

        think_time = random.uniform(0.8, 2.5)
        print(f"\n[{i+1}] think={think_time:.2f}s  target_x={target_x}"
              f"  pts={len(target_points)} ...", end=" ", flush=True)
        time.sleep(think_time)

        payload = build_simple_bot_payload(
            token=token,
            target_x=target_x,
            target_points=target_points,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            n_points=random.randint(10, 15),
        )
        res = attack(payload, i)
        if res:
            results.append(res)
        time.sleep(random.uniform(4.0, 6.0))

    print("\n" + "=" * 60)
    if results:
        passed  = [r for r in results if r.get("result") == "human"]
        blocked = [r for r in results if r.get("result") == "bot"]
        errors  = [r for r in results if r.get("result") not in ("human", "bot")]
        scores  = [r["score"] for r in results if isinstance(r.get("score"), (int, float))]

        print(f" Kết quả {len(results)} lần:")
        print(f"   Qua được   (False Negative): {len(passed)}")
        print(f"   Bị chặn    (True Positive) : {len(blocked)}")
        print(f"   Lỗi / khác               : {len(errors)}")
        print(f"   Bypass rate: {len(passed)/len(results)*100:.1f}%")
        if scores:
            print(f"   Score: avg={sum(scores)/len(scores):.3f}  "
                  f"min={min(scores):.3f}  max={max(scores):.3f}")
    else:
        print(" Không có kết quả nào")