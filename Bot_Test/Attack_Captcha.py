"""
Attack_Captcha.py — Task 4: Kiểm tra bảo mật hệ thống CAPTCHA
================================================================
4 chiến lược tấn công:
  [A] Replay Attack        — Ghi lại request hợp lệ rồi gửi lại nhiều lần
  [B] Sửa tọa độ          — Lấy token thật, chỉnh sửa tọa độ puzzle/canvas
  [C] Reuse Token          — Dùng cùng 1 token cho nhiều request khác nhau

Mỗi chiến lược in ra kết quả chi tiết và thống kê tổng cuối.

GHI CHÚ: File này chỉ dùng để kiểm tra (pentest) hệ thống CAPTCHA do chính bạn
         xây dựng hoặc được phép kiểm tra.
"""

import copy
import json
import math
import random
import time
import threading
import requests

# ─── Cấu hình ────────────────────────────────────────────────────────────────

API_URL    = "http://127.0.0.1:5000/captcha/verify"
API_INIT   = "http://127.0.0.1:5000/captcha/init"
TRACK_WIDTH = 300

# Số lượng request cho mỗi chiến lược
REPLAY_COUNT    = 8    # [A] Replay bao nhiêu lần
COORD_COUNT     = 6    # [B] Bao nhiêu biến thể tọa độ
REUSE_COUNT     = 8    # [C] Dùng lại token bao nhiêu lần

# ─── Helpers chung ────────────────────────────────────────────────────────────

def get_token(retries=5, delay=15.0):
    """Lấy token mới từ server."""
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


def ease_in_out(t):
    return 3 * t**2 - 2 * t**3


def build_canvas_events(target_points, canvas_w=300, canvas_h=150, start_t=0):
    """Dựng sự kiện canvas theo polygon từ server."""
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


def build_puzzle_events(target_norm, n_points=28, start_t=0):
    """Dựng sự kiện kéo puzzle cơ bản (ease-in-out + jitter)."""
    events = []
    t = start_t
    prev_x, prev_y = 0.0, 0.50

    for i in range(n_points):
        progress = i / (n_points - 1)
        x  = round(ease_in_out(progress) * target_norm, 4)
        y  = round(0.50 + random.uniform(-0.010, 0.010), 4)
        dt = random.randint(13, 35)
        if random.random() < 0.07:
            dt += random.randint(50, 120)
        t += dt
        dist  = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
        speed = round(dist / max(dt, 1), 6)
        events.append({"x": x, "y": y, "t": t, "dt": dt, "speed": speed,
                       "type": "mousemove" if i > 0 else "mousedown",
                       "area": "puzzle"})
        prev_x, prev_y = x, y

    t += random.randint(15, 30)
    events.append({"x": target_norm, "y": 0.50, "t": t,
                   "dt": t - events[-1]["t"], "speed": 0.0,
                   "type": "mouseup", "area": "puzzle"})
    return events


def build_fresh_payload():
    """Dựng payload hợp lệ hoàn chỉnh từ token mới."""
    token, target_x, target_points, canvas_w, canvas_h = get_token()
    if not token:
        return None

    canvas_evts, canvas_end = build_canvas_events(
        target_points, canvas_w, canvas_h, start_t=0
    )
    gap = random.randint(300, 700)
    target_norm = round(target_x / TRACK_WIDTH, 4)
    puzzle_evts = build_puzzle_events(target_norm, start_t=canvas_end + gap)

    return {
        "token":         token,
        "user_x":        target_x,
        "startTime":     int(time.time() * 1000),
        "device":        "mouse",
        "expectedShape": f"polygon_{len(target_points)}pts",
        "events":        canvas_evts + puzzle_evts,
    }


def send_payload(payload, label=""):
    """Gửi payload lên server và trả về kết quả."""
    try:
        r = requests.post(API_URL, json=payload, timeout=5)
        d = r.json()
        return {
            "label":   label,
            "http":    r.status_code,
            "result":  d.get("result", "?"),
            "score":   d.get("score", "?"),
            "msg":     d.get("msg", ""),
        }
    except requests.exceptions.ConnectionError:
        return {"label": label, "http": 0, "result": "offline", "score": None, "msg": ""}
    except Exception as e:
        return {"label": label, "http": -1, "result": "error", "score": None, "msg": str(e)}


def print_result(idx, res):
    msg_part = f"  [{res['msg']}]" if res.get("msg") else ""
    print(f"  [{idx+1:02d}] HTTP {res['http']:>3} → result={res['result']:<6}  "
          f"score={res['score']}{msg_part}")


def print_section(title):
    print(f"\n{'='*68}")
    print(f"  {title}")
    print(f"{'='*68}")


def summarize(results, title="Tổng kết"):
    if not results:
        print("  Không có kết quả.\n")
        return
    passed = [r for r in results if r.get("result") == "human"]
    scores = [r["score"] for r in results
              if isinstance(r.get("score"), (int, float))]
    rate = len(passed) / len(results) * 100
    avg  = round(sum(scores) / len(scores), 3) if scores else "n/a"
    mn   = round(min(scores), 3) if scores else "n/a"
    mx   = round(max(scores), 3) if scores else "n/a"

    http_429 = sum(1 for r in results if r.get("http") == 429)
    http_400 = sum(1 for r in results if r.get("http") == 400)

    print(f"\n  ► {title}")
    print(f"    Bypass (result=human): {len(passed)}/{len(results)}  ({rate:.1f}%)")
    print(f"    Score: avg={avg}  min={mn}  max={mx}")
    if http_429 or http_400:
        print(f"    Server chặn: 429 Rate-limit={http_429}  400 Bad={http_400}")


# ═══════════════════════════════════════════════════════════════════════════════
# [A] REPLAY ATTACK — Ghi lại 1 request hợp lệ rồi gửi lại nhiều lần
# ═══════════════════════════════════════════════════════════════════════════════

def attack_replay(n=REPLAY_COUNT):
    """
    Mục tiêu kiểm tra:
      - Server có nhận ra token đã dùng không? (token blacklist)
      - Cùng 1 bộ event_signature có bị chặn lần 2 không?
      - Timestamp cũ có bị phát hiện không?
    """
    print_section("[A] REPLAY ATTACK")
    print("  Bước 1: Lấy 1 payload hợp lệ...")

    original = build_fresh_payload()
    if not original:
        print("  [!] Không lấy được payload gốc.")
        return []

    print(f"  Token: {original['token'][:20]}...  target_x={original['user_x']}")
    print(f"  Bước 2: Gửi lại {n} lần (không đổi gì)...\n")

    results = []
    for i in range(n):
        # Giữ nguyên TOÀN BỘ payload — kể cả token và startTime
        payload = copy.deepcopy(original)
        res = send_payload(payload, label="replay")
        results.append(res)
        print_result(i, res)
        time.sleep(random.uniform(0.3, 0.8))

    summarize(results, "Replay Attack")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# [B] SỬA TỌA ĐỘ — Lấy token thật, chỉnh user_x và tọa độ cuối cùng
# ═══════════════════════════════════════════════════════════════════════════════

def _mutate_coords(payload, strategy="random_x"):
    """
    Trả về bản sao payload đã bị chỉnh tọa độ theo strategy:
      "random_x"    — đặt user_x ngẫu nhiên [0, TRACK_WIDTH], sửa điểm mouseup
      "zero_x"      — đặt user_x = 0 (chưa kéo gì)
      "overflow_x"  — đặt user_x > TRACK_WIDTH (kéo quá biên)
      "wrong_end"   — giữ user_x đúng nhưng điểm mouseup lệch xa
      "all_zero"    — toàn bộ x của puzzle = 0 (không di chuyển)
      "teleport"    — event cuối nhảy thẳng tới đích, bỏ hành trình
    """
    p = copy.deepcopy(payload)

    puzzle_events = [e for e in p["events"] if e.get("area") == "puzzle"]
    other_events  = [e for e in p["events"] if e.get("area") != "puzzle"]

    if strategy == "random_x":
        new_x = random.randint(10, TRACK_WIDTH - 10)
        p["user_x"] = new_x
        new_norm = round(new_x / TRACK_WIDTH, 4)
        for e in puzzle_events:
            if e["type"] == "mouseup":
                e["x"] = new_norm

    elif strategy == "zero_x":
        p["user_x"] = 0
        for e in puzzle_events:
            e["x"] = 0.0

    elif strategy == "overflow_x":
        p["user_x"] = TRACK_WIDTH + random.randint(20, 80)
        for e in puzzle_events:
            if e["type"] == "mouseup":
                e["x"] = round(p["user_x"] / TRACK_WIDTH, 4)

    elif strategy == "wrong_end":
        # user_x đúng, nhưng mouseup lệch ±0.25 norm
        for e in puzzle_events:
            if e["type"] == "mouseup":
                original_x = e["x"]
                offset = random.choice([-1, 1]) * random.uniform(0.20, 0.35)
                e["x"] = round(max(0.0, min(1.0, original_x + offset)), 4)

    elif strategy == "all_zero":
        for e in puzzle_events:
            e["x"] = 0.0
        p["user_x"] = 0

    elif strategy == "teleport":
        # Bỏ toàn bộ mousemove, chỉ giữ mousedown + mouseup
        target_norm = round(p["user_x"] / TRACK_WIDTH, 4)
        t_base = other_events[-1]["t"] if other_events else 0
        puzzle_events = [
            {"x": 0.0, "y": 0.5, "t": t_base + 50,  "dt": 50,  "speed": 0.0,
             "type": "mousedown", "area": "puzzle"},
            {"x": target_norm, "y": 0.5, "t": t_base + 80, "dt": 30, "speed": 0.0,
             "type": "mouseup",   "area": "puzzle"},
        ]

    p["events"] = other_events + puzzle_events
    return p


COORD_STRATEGIES = [
    "random_x",
    "zero_x",
    "overflow_x",
    "wrong_end",
    "all_zero",
    "teleport",
]


def attack_mutate_coords(n=COORD_COUNT):
    """
    Mục tiêu kiểm tra:
      - Server có xác thực user_x khớp với tọa độ mouseup không?
      - Server có từ chối tọa độ ngoài biên không?
      - Phát hiện teleport (thiếu hành trình chuột) không?
    """
    print_section("[B] SỬA TỌA ĐỘ (Coordinate Mutation)")
    print(f"  Lấy {n} token mới, mỗi token áp dụng 1 chiến lược sửa tọa độ...\n")

    results = []
    for i in range(n):
        strategy = COORD_STRATEGIES[i % len(COORD_STRATEGIES)]
        print(f"  [{i+1:02d}] strategy={strategy:<12}", end="  ")

        base = build_fresh_payload()
        if not base:
            print("[!] skip — không lấy được token")
            continue

        payload = _mutate_coords(base, strategy)
        res = send_payload(payload, label=strategy)
        results.append(res)

        msg_part = f"  [{res['msg']}]" if res.get("msg") else ""
        print(f"HTTP {res['http']:>3} → result={res['result']:<6}  "
              f"score={res['score']}{msg_part}")
        time.sleep(random.uniform(0.4, 1.0))

    summarize(results, "Coordinate Mutation")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# [C] REUSE TOKEN — Dùng cùng 1 token nhiều lần với payload khác nhau
# ═══════════════════════════════════════════════════════════════════════════════

def attack_reuse_token(n=REUSE_COUNT):
    """
    Mục tiêu kiểm tra:
      - [C1] Token Blacklist: cùng token + events MỚI mỗi lần
             → Server chặn vì "token đã dùng" (token blacklist)
      - [C2] Event Fingerprinting: token MỚI + events Y CHANG lần đầu
             → Nếu server chặn → có event-fingerprint detection
             → Nếu server chấp nhận → chỉ có token blacklist, không có event check
    """
    print_section("[C] REUSE TOKEN  +  EVENT FINGERPRINTING")

    # ── Sub-test C1: Token Blacklist ──────────────────────────────────────────
    print("  [C1] Token Blacklist — token giữ nguyên, events mới mỗi lần")
    print("  Bước 1: Lấy 1 token duy nhất...")

    token, target_x, target_points, canvas_w, canvas_h = get_token()
    if not token:
        print("  [!] Không lấy được token.")
        return []

    print(f"  Token: {token[:20]}...  target_x={target_x}")
    print(f"  Bước 2: Gửi {n} request, tất cả dùng TOKEN này (events khác nhau)...\n")

    results_c1 = []
    frozen_events = None  # Lưu lại events lần đầu để dùng cho C2

    for i in range(n):
        canvas_evts, canvas_end = build_canvas_events(
            target_points, canvas_w, canvas_h, start_t=0
        )
        gap = random.randint(200, 800)
        target_norm = round(target_x / TRACK_WIDTH, 4)
        puzzle_evts = build_puzzle_events(target_norm, start_t=canvas_end + gap)
        all_events = canvas_evts + puzzle_evts

        if i == 0:
            frozen_events = copy.deepcopy(all_events)  # Đóng băng events lần 1

        payload = {
            "token":         token,          # GIỐNG NHAU mọi lần
            "user_x":        target_x,
            "startTime":     int(time.time() * 1000),
            "device":        "mouse",
            "expectedShape": f"polygon_{len(target_points)}pts",
            "events":        all_events,
        }

        tag = "1st" if i == 0 else f"{i+1}th-reuse"
        res = send_payload(payload, label=tag)
        results_c1.append(res)
        print_result(i, res)
        time.sleep(random.uniform(0.5, 1.2))

    summarize(results_c1, "[C1] Token Blacklist")

    # ── Sub-test C2: Event Fingerprinting ─────────────────────────────────────
    print("\n  [C2] Event Fingerprinting — token MỚI nhưng events Y CHANG lần đầu")
    print("       Mục tiêu: server chặn → có event fingerprint; pass → không có\n")

    if frozen_events is None:
        print("  [!] Không có frozen events để test C2.")
        return results_c1

    results_c2 = []
    n_fp = max(3, n // 2)  

    for i in range(n_fp):
        # Lấy token HOÀN TOÀN MỚI
        new_token, new_tx, _, _, _ = get_token()
        if not new_token:
            print(f"  [{i+1:02d}] [!] Không lấy được token mới — bỏ qua")
            continue

        # Dùng lại ĐÚNG BỘ EVENTS đã đóng băng từ C1 lần đầu
        payload = {
            "token":         new_token,              #  TOKEN MỚI
            "user_x":        target_x,
            "startTime":     int(time.time() * 1000),  #  startTime cập nhật
            "device":        "mouse",
            "expectedShape": f"polygon_{len(target_points)}pts",
            "events":        copy.deepcopy(frozen_events),  #  EVENTS CŨ Y CHANG
        }

        tag = f"fp-{i+1}"
        res = send_payload(payload, label=tag)
        results_c2.append(res)
        print_result(i, res)
        time.sleep(random.uniform(0.5, 1.2))

    summarize(results_c2, "[C2] Event Fingerprinting")

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Kiểm tra bảo mật CAPTCHA "
    )
    parser.add_argument(
        "--attack", "-a",
        choices=["replay", "coords", "reuse", "spam", "all"],
        default="all",
        help="Chọn chiến lược tấn công (mặc định: all)",
    )
    args = parser.parse_args()

    print("=" * 68)
    print("  CAPTCHA SECURITY TESTER ")
    print("  Các chiến lược: Replay | Sửa tọa độ | Reuse Token ")
    print("=" * 68)

    all_results = {}

    if args.attack in ("replay", "all"):
        all_results["replay"] = attack_replay()
        time.sleep(2.0)

    if args.attack in ("coords", "all"):
        all_results["coords"] = attack_mutate_coords()
        time.sleep(2.0)

    if args.attack in ("reuse", "all"):
        all_results["reuse"] = attack_reuse_token()
        time.sleep(2.0)

    print()