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
            return jsonify({"result": "bot", "msg": f"Coordinate mismatch: {coord_msg}"}), 200

        evt_hash = _event_hash(events)
        if evt_hash in recent_event_hashes:
            return jsonify({"result": "bot", "msg": "Replay attack detected"}), 200
        recent_event_hashes[evt_hash] = time.time()

        scorer = BehaviorScorer(data)
        result = scorer.analyze_behavior()

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)