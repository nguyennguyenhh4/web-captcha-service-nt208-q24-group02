from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import random
import time
import hashlib
import json
from scoring_logic import BehaviorScorer

app = Flask(__name__)
CORS(app)

EXPIRE_DURATION = 300         

captcha_db: dict = {}         

recent_event_hashes: dict = {}  
REPLAY_WINDOW = 600             

rate_limit_log: dict = {}
RATE_LIMITS = {
    "init":   (10, 60),  
    "verify": (20, 60),   
}


def _get_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()


def _check_rate_limit(ip: str, endpoint: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
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


def _validate_events_timing(events: list, session_start: float) -> tuple[bool, str]:
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


def _validate_coordinate_consistency(events: list, user_x: float, target_x: int) -> tuple[bool, str]:
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
    if abs(last_x_norm - user_x_norm) > 0.05:
        return False, (
            f"user_x ({user_x_norm:.3f} normalised) doesn't match "
            f"last puzzle event x ({last_x_norm:.3f})"
        )

    return True, "ok"


def _cross(o, a, b):
    """Cross product của vector OA và OB."""
    return (a["x"] - o["x"]) * (b["y"] - o["y"]) - (a["y"] - o["y"]) * (b["x"] - o["x"])


def _segments_intersect(p1, p2, p3, p4):
    """
    Kiểm tra đoạn thẳng p1-p2 và p3-p4 có cắt nhau không (không tính chung đầu mút).
    """
    d1 = _cross(p3, p4, p1)
    d2 = _cross(p3, p4, p2)
    d3 = _cross(p1, p2, p3)
    d4 = _cross(p1, p2, p4)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def _validate_shape(events: list, target_points: list, canvas_w: float, canvas_h: float) -> tuple[bool, str]:
    """
    Kiểm tra người dùng có vẽ đúng hình không:
    1. Đi qua đủ tất cả các điểm (theo thứ tự, CW hoặc CCW đều được).
    2. Không có cạnh nào cắt chéo nhau.

    target_points: [{x, y, index}] — tọa độ pixel canvas gửi từ frontend.
    canvas_w/canvas_h: kích thước canvas (để quy đổi tọa độ normalized event về pixel).
    """
    if not target_points or len(target_points) < 2:
        return False, "No target points provided"

    n = len(target_points)

    # --- Bước 1: Tìm thứ tự user đi qua các điểm ---
    # Với mỗi canvas event (tọa độ normalized 0-1), kiểm tra có chạm điểm nào không.
    HIT_RADIUS = 8  # pixel — rộng hơn frontend một chút để bù sai số normalize

    visited_order = []   # index của điểm theo thứ tự user chạm
    visited_set   = set()

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

    # --- Bước 2: Kiểm tra đã đi qua đủ tất cả điểm chưa ---
    if len(visited_set) < n:
        missing = sorted(set(range(n)) - visited_set)
        return False, f"Chưa đi qua đủ các điểm. Thiếu: {[m+1 for m in missing]}"

    # --- Bước 2.5: Kiểm tra điểm đầu trùng điểm cuối ---
    # Lấy tọa độ pixel của điểm đầu và điểm cuối trong canvas_events
    canvas_events = [e for e in events if e.get("area") == "canvas"]
    if len(canvas_events) < 2:
        return False, "Không đủ canvas events để kiểm tra điểm đầu/cuối"

    first = canvas_events[0]
    last  = canvas_events[-1]

    first_px = first["x"] * canvas_w
    first_py = first["y"] * canvas_h
    last_px  = last["x"]  * canvas_w
    last_py  = last["y"]  * canvas_h

    CLOSE_RADIUS = 15  # pixel — khoảng cách tối đa coi là "trùng nhau"
    dist = ((last_px - first_px) ** 2 + (last_py - first_py) ** 2) ** 0.5
    if dist > CLOSE_RADIUS:
        return False, f"Điểm đầu và điểm cuối chưa khép kín (cách nhau {dist:.1f}px, tối đa {CLOSE_RADIUS}px)"

    # --- Bước 3: Kiểm tra thứ tự hợp lệ ---
    # Thứ tự hợp lệ là: 0,1,2,...,n-1 (CW) hoặc n-1,...,1,0 (CCW)
    cw_order  = list(range(n))
    ccw_order = list(reversed(range(n)))

    # Normalize visited_order thành thứ tự bắt đầu từ 0 để so sánh
    start_idx   = visited_order[0]
    rotated_cw  = [(i - start_idx) % n for i in cw_order]
    rotated_ccw = [(i - start_idx) % n for i in ccw_order]
    normalized  = [(i - start_idx) % n for i in visited_order]

    if normalized != rotated_cw and normalized != rotated_ccw:
        return False, f"Thứ tự vẽ không hợp lệ. Thứ tự nhận được: {[v+1 for v in visited_order]}"

    # --- Bước 4: Kiểm tra các cạnh không cắt chéo nhau ---
    # Xây dựng polygon từ thứ tự user đã vẽ (đã khớp CW hoặc CCW ở trên)
    pts = [target_points[i] for i in visited_order]
    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]

    for i in range(len(edges)):
        for j in range(i + 2, len(edges)):
            # Bỏ qua cặp cạnh đầu-cuối liền kề nhau (chung đỉnh)
            if i == 0 and j == len(edges) - 1:
                continue
            if _segments_intersect(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                return False, f"Hình vẽ bị cắt chéo giữa cạnh {i+1} và cạnh {j+1}"

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

    captcha_db[token] = {
        "target_x":   target_x,
        "created_at": time.time(),
        "expire_time": time.time() + EXPIRE_DURATION,
        "status":     "unused",
        "ip":         ip,
    }

    return jsonify({
        "token":    token,
        "target_x": target_x,
        "target_y": target_y,
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
            return jsonify({"result": "bot", "msg": f"Timing invalid: {timing_msg}"}), 200

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
            return jsonify({"result": "bot", "msg": "Replay attack detected"}), 200
        recent_event_hashes[evt_hash] = time.time()

        # --- Kiểm tra hình vẽ canvas ---
        # 1. Chấm điểm hành vi AI (Human vs Bot)
        scorer = BehaviorScorer(data)
        behavior_result = scorer.analyze_behavior()

        if behavior_result.get("result") == "bot":
            return jsonify({
                "status": "fail", 
                "code": "bot_detected",
                "message": "❌ Xác thực thất bại (Hành vi không hợp lệ)!"
            }), 200

        # 2. Nếu đã là Human -> Kiểm tra hình vẽ canvas
        target_points = data.get("targetPoints", [])
        canvas_w      = data.get("canvasWidth",  300)
        canvas_h      = data.get("canvasHeight", 150)

        if target_points:
            shape_ok, shape_msg = _validate_shape(events, target_points, canvas_w, canvas_h)
            if not shape_ok:
                return jsonify({
                    "status": "fail", 
                    "code": "wrong_shape",
                    "message": "❌ Vẽ sai hình! Vui lòng vẽ đúng thứ tự."
                }), 200

        # 3. Thành công hoàn toàn (Human + Vẽ đúng)
        return jsonify({
            "status": "success", 
            "code": "pass",
            "message": "✅ Xác thực thành công!"
        }), 200

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)