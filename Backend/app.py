from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import random
import time
import hashlib
import json
import math
from scoring_logic import BehaviorScorer

app = Flask(__name__)

# ─── FIX #1: Giới hạn CORS theo origin thay vì mở toàn bộ ───────────────────
# Thay "https://yourdomain.com" bằng domain thật của frontend
ALLOWED_ORIGINS = ["http://127.0.0.1:5500", "http://localhost:5500"]
CORS(app, origins=ALLOWED_ORIGINS)

EXPIRE_DURATION = 300
CANVAS_W = 300
CANVAS_H = 150

# ─── FIX #2: Trusted proxy flag ───────────────────────────────────────────────
# Đặt True nếu chạy sau reverse proxy (nginx/caddy) đã cấu hình đúng
# Đặt False khi chạy trực tiếp (development, expose thẳng ra internet)
BEHIND_TRUSTED_PROXY = False

captcha_db: dict = {}


def _generate_target_points(n: int = None) -> list:
    n = n or random.randint(3, 6)
    cx = CANVAS_W / 2 + random.uniform(-30, 30)
    cy = CANVAS_H / 2 + random.uniform(-10, 10)
    radius = random.randint(35, 55)
    points = []
    for i in range(n):
        angle = 2 * math.pi * i / n + random.uniform(-0.15, 0.15)
        px = max(10, min(CANVAS_W - 10, cx + radius * math.cos(angle)))
        py = max(10, min(CANVAS_H - 10, cy + radius * math.sin(angle)))
        points.append({"x": round(px, 2), "y": round(py, 2), "index": i})
    return points


recent_event_hashes: dict = {}
REPLAY_WINDOW = 600

rate_limit_log: dict = {}
RATE_LIMITS = {
    "init":   (10, 60),
    "verify": (20, 60),
}


# ─── FIX #1 (tiếp): Hàm lấy IP an toàn ──────────────────────────────────────
def _get_ip() -> str:
    """
    Chỉ tin X-Forwarded-For khi BEHIND_TRUSTED_PROXY=True.
    Ngược lại dùng remote_addr trực tiếp để tránh IP spoofing.
    """
    if BEHIND_TRUSTED_PROXY:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr


def _check_rate_limit(ip: str, endpoint: str) -> bool:
    max_calls, window = RATE_LIMITS[endpoint]
    now = time.time()
    log = rate_limit_log.setdefault(ip, [])
    rate_limit_log[ip] = [ts for ts in log if now - ts < window]
    if len(rate_limit_log[ip]) >= max_calls:
        return False
    rate_limit_log[ip].append(now)
    return True


def _evict_expired():
    now = time.time()
    expired_tokens = [t for t, s in captcha_db.items() if now > s["expire_time"]]
    for t in expired_tokens:
        del captcha_db[t]
    expired_hashes = [h for h, ts in recent_event_hashes.items() if now - ts > REPLAY_WINDOW]
    for h in expired_hashes:
        del recent_event_hashes[h]


def _event_hash(events: list) -> str:
    canonical = json.dumps(
        [{"x": e.get("x"), "y": e.get("y"), "t": e.get("t")} for e in events],
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_events_timing(events: list, session_start: float) -> tuple:
    if len(events) < 2:
        return False, "Too few events"
    ts = [e.get("t", 0) for e in events]
    for i in range(1, len(ts)):
        if ts[i] < ts[i - 1]:
            return False, "Non-monotonic timestamps"
    duration = ts[-1] - ts[0]
    if duration < 300:
        return False, f"Duration too short ({duration} ms)"
    if duration > 30_000:
        return False, f"Duration too long ({duration} ms)"
    real_elapsed_ms = (time.time() - session_start) * 1000
    if real_elapsed_ms < 200:
        return False, "Verified too quickly after init"
    return True, "ok"


def _validate_coordinate_consistency(events: list, user_x: float, target_x: int) -> tuple:
    TRACK_WIDTH = 300
    if abs(user_x - target_x) > 10:
        return False, "user_x too far from target_x"
    puzzle_events = [e for e in events if e.get("area") == "puzzle"]
    if not puzzle_events:
        return False, "No puzzle events found"
    last_x_norm = puzzle_events[-1].get("x", None)
    if last_x_norm is None:
        return False, "Missing x in last puzzle event"
    user_x_norm = user_x / TRACK_WIDTH
    # Tolerance nới từ 0.05 → 0.10 (tương đương 30px trên track 300px).
    # user_x ghi nhận lúc mouseup, last puzzle event x là mousemove cuối —
    # hai thời điểm có độ trễ thực tế, người thật dễ bị false-positive với ngưỡng hẹp.
    if abs(last_x_norm - user_x_norm) > 0.10:
        return False, (
            f"user_x ({user_x_norm:.3f}) doesn't match "
            f"last puzzle event x ({last_x_norm:.3f})"
        )
    return True, "ok"


def _cross(o, a, b):
    return (a["x"] - o["x"]) * (b["y"] - o["y"]) - (a["y"] - o["y"]) * (b["x"] - o["x"])


def _segments_intersect(p1, p2, p3, p4):
    d1 = _cross(p3, p4, p1)
    d2 = _cross(p3, p4, p2)
    d3 = _cross(p1, p2, p3)
    d4 = _cross(p1, p2, p4)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def _validate_shape(events: list, target_points: list, canvas_w: float, canvas_h: float) -> tuple:
    if not target_points or len(target_points) < 2:
        return False, "No target points provided"
    n = len(target_points)
    HIT_RADIUS = 12
    visited_order = []
    visited_set = set()
    for e in events:
        if e.get("area") != "canvas":
            continue
        px = e["x"] * canvas_w
        py = e["y"] * canvas_h
        for pt in target_points:
            idx = pt["index"]
            if idx in visited_set:
                continue
            dx = px - pt["x"]
            dy = py - pt["y"]
            if (dx * dx + dy * dy) <= HIT_RADIUS * HIT_RADIUS:
                visited_order.append(idx)
                visited_set.add(idx)
    if len(visited_set) < n:
        missing = sorted(set(range(n)) - visited_set)
        return False, f"Chưa đi qua đủ các điểm. Thiếu: {[m+1 for m in missing]}"
    canvas_events = [e for e in events if e.get("area") == "canvas"]
    if len(canvas_events) < 2:
        return False, "Không đủ canvas events để kiểm tra điểm đầu/cuối"
    first = canvas_events[0]
    last  = canvas_events[-1]
    first_px = first["x"] * canvas_w
    first_py = first["y"] * canvas_h
    last_px  = last["x"]  * canvas_w
    last_py  = last["y"]  * canvas_h
    CLOSE_RADIUS = 25  # BUG FIX #3: nới từ 15→25px để dễ khép kín hơn
    dist = ((last_px - first_px) ** 2 + (last_py - first_py) ** 2) ** 0.5
    if dist > CLOSE_RADIUS:
        return False, f"Chưa khép kín (cách {dist:.1f}px, tối đa {CLOSE_RADIUS}px)"
    cw_order  = list(range(n))
    ccw_order = list(reversed(range(n)))
    start_idx   = visited_order[0]
    rotated_cw  = [(i - start_idx) % n for i in cw_order]
    rotated_ccw = [(i - start_idx) % n for i in ccw_order]
    normalized  = [(i - start_idx) % n for i in visited_order]
    if normalized != rotated_cw and normalized != rotated_ccw:
        return False, f"Thứ tự vẽ không hợp lệ: {[v+1 for v in visited_order]}"
    pts = [target_points[i] for i in visited_order]
    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    for i in range(len(edges)):
        for j in range(i + 2, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            if _segments_intersect(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                return False, f"Hình vẽ bị cắt chéo giữa cạnh {i+1} và {j+1}"
    return True, "ok"


# ─── FIX #3 (cải tiến #11): Kiểm tra mật độ events canvas ───────────────────
def _validate_canvas_event_density(events: list, n_target_points: int) -> tuple:
    """
    Phát hiện bot qua 2 cơ chế:

    A) EXACT COUNT CHECK (mới, FIX #11):
       Bot dùng STEPS_PER_SEG=12 cố định → tổng canvas events = 12n - 5.
       Đây là signature chính xác nhất, không thể "ngẫu nhiên" khớp.
         n=3: 31 events | n=4: 43 | n=5: 55 | n=6: 67

    B) RATIO + TIMING CHECK (giữ từ FIX #3):
       events/pts trong khoảng 9.5-11.5 kết hợp với cv_dt thấp.
    """
    canvas_events = [e for e in events if e.get("area") == "canvas"]
    n = len(canvas_events)

    if n < 8:
        return False, "Too few canvas events"

    min_events = max(15, n_target_points * 8)
    if n < min_events:
        return False, f"Canvas events ({n}) quá thấp cho polygon {n_target_points} điểm (min {min_events})"

    ts = [e.get("t", 0) for e in canvas_events]
    dts = [ts[i] - ts[i-1] for i in range(1, len(ts)) if ts[i] - ts[i-1] > 0]
    cv_dt = 0.0
    if dts:
        mean_dt = sum(dts) / len(dts)
        std_dt  = math.sqrt(sum((d - mean_dt)**2 for d in dts) / len(dts))
        cv_dt   = std_dt / mean_dt if mean_dt > 0 else 0

    # ── A) Exact bot count check ──────────────────────────────────────────────
    # Bot advanced/simple đều dùng công thức: total = (n-1)*12 + 6 + 1 = 12n - 5
    bot_expected = 12 * n_target_points - 5
    if abs(n - bot_expected) <= 3 and cv_dt < 0.75:  # FIX: raise threshold (bot random timing cv_dt ≈ 0.57)
        # Xác nhận thêm: phân bổ giữa các segment có đều không?
        # Bot: mỗi segment (trừ cuối) có đúng 12 events → ratio cố định
        return False, (
            f"Bot pattern: exact step count detected "
            f"(events={n}, expected_bot={bot_expected}, cv_dt={cv_dt:.3f})"
        )

    # ── B) Ratio + timing check (backup) ─────────────────────────────────────
    ratio = n / n_target_points
    if 9.5 <= ratio <= 11.5:
        if cv_dt < 0.40 and ratio < 12.0:
            return False, (
                f"Canvas event pattern đáng ngờ: "
                f"events/pts={ratio:.2f}, cv_dt={cv_dt:.3f}"
            )

    return True, "ok"


@app.route("/captcha/init", methods=["GET"])
def init_captcha():
    _evict_expired()
    ip = _get_ip()
    if not _check_rate_limit(ip, "init"):
        return jsonify({"result": "bot", "msg": "Too many requests"}), 429

    token = str(uuid.uuid4())
    target_x = random.randint(80, 240)
    target_y = random.randint(10, 90)
    target_points = _generate_target_points()

    captcha_db[token] = {
        "target_x":      target_x,
        "target_points": target_points,
        "canvas_w":      CANVAS_W,
        "canvas_h":      CANVAS_H,
        "created_at":    time.time(),
        "expire_time":   time.time() + EXPIRE_DURATION,
        "status":        "unused",
        "ip":            ip,
    }

    return jsonify({
        "token":        token,
        "target_x":     target_x,
        "target_y":     target_y,
        "targetPoints": target_points,
        "canvasWidth":  CANVAS_W,
        "canvasHeight": CANVAS_H,
    })


@app.route("/captcha/verify", methods=["POST"])
def verify():
    _evict_expired()
    ip = _get_ip()
    if not _check_rate_limit(ip, "verify"):
        return jsonify({"result": "bot", "msg": "Too many requests — rate limited"}), 429

    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"result": "bot", "msg": "No JSON body"}), 400

        token  = data.get("token")
        user_x = data.get("user_x")
        events = data.get("events", [])

        if token not in captcha_db:
            return jsonify({"result": "bot", "msg": "Token không tồn tại"}), 400

        session = captcha_db[token]

        if time.time() > session["expire_time"]:
            session["status"] = "expired"
            return jsonify({"result": "bot", "msg": "Token đã hết hạn"}), 400

        if session["status"] == "used":
            return jsonify({"result": "bot", "msg": "Token đã được sử dụng"}), 400

        session["status"] = "used"

        if session["ip"] != ip:
            return jsonify({"result": "bot", "msg": "IP mismatch"}), 400

        timing_ok, timing_msg = _validate_events_timing(events, session["created_at"])
        if not timing_ok:
            return jsonify({"result": "bot", "message": f"❌ Timing không hợp lệ: {timing_msg}"}), 200

        if user_x is None:
            return jsonify({"result": "bot", "msg": "Missing user_x"}), 400

        coord_ok, coord_msg = _validate_coordinate_consistency(
            events, float(user_x), session["target_x"]
        )
        if not coord_ok:
            return jsonify({
                "status": "fail",
                "code": "coordinate_mismatch",
                "message": "❌ Thao tác trượt không hợp lệ! Vui lòng thử lại."
            }), 200

        evt_hash = _event_hash(events)
        if evt_hash in recent_event_hashes:
            return jsonify({"result": "bot", "message": "❌ Yêu cầu trùng lặp. Vui lòng tải lại."}), 200
        recent_event_hashes[evt_hash] = time.time()

        # Lấy target_points từ SESSION (server-side) — không tin dữ liệu từ client
        target_points = session["target_points"]
        canvas_w      = session["canvas_w"]
        canvas_h      = session["canvas_h"]

        if target_points:
            shape_ok, shape_msg = _validate_shape(events, target_points, canvas_w, canvas_h)
            if not shape_ok:
                return jsonify({
                    "status": "fail",
                    "code": "wrong_shape",
                    "message": "❌ Vẽ sai hình! Vui lòng vẽ đúng thứ tự."
                }), 200

        # Truyền target_points vào scorer để dùng cho corner velocity analysis
        scorer = BehaviorScorer(data, target_points=target_points,
                                canvas_w=canvas_w, canvas_h=canvas_h)
        result = scorer.analyze_behavior()

        # BUG FIX #4: Thêm "message" để frontend hiển thị đúng
        result["message"] = "✅ Xác thực thành công!" if result.get("result") == "human" else "❌ Xác thực thất bại! Vui lòng thử lại."
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500


if __name__ == "__main__":
    # FIX #4: Tắt debug=True trong production
    import os
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, port=5000)