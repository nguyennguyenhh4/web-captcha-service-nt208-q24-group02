from flask import Blueprint, jsonify, request, current_app
from services.session_service import SessionService
from services.behavior_analyzer import BehaviorAnalyzer
from services.puzzle_validator import PuzzleValidator
from storage.session_store import session_store
from storage.image_store import image_store

captcha_bp = Blueprint("captcha", __name__)


# ─────────────────────────────────────────────
# GET /captcha/init
# Trả về: token, target_x, target_y, image_url
# ─────────────────────────────────────────────
@captcha_bp.route("/init", methods=["GET"])
def init():
    cfg = current_app.config

    # Chọn ảnh ngẫu nhiên và tính tọa độ đích
    image_name = image_store.random_image()
    target_x, target_y = PuzzleValidator.generate_target(
        canvas_width=cfg["CANVAS_WIDTH"],
        piece_size=cfg["PIECE_SIZE"],
    )

    # Tạo token và lưu session
    token = SessionService.create_token()
    session_store.save(token, {
        "target_x":   target_x,
        "target_y":   target_y,
        "image_name": image_name,
    }, ttl=cfg["TOKEN_TTL_SECONDS"])

    return jsonify({
        "token":     token,
        "target_x":  target_x,
        "target_y":  target_y,
        "image_url": f"/captcha/image/{image_name}",
    }), 200


# ─────────────────────────────────────────────
# POST /captcha/verify
# Body JSON: token, user_x, events[], device, pattern, timestamp
# Trả về: success bool + reason
# ─────────────────────────────────────────────
@captcha_bp.route("/verify", methods=["POST"])
def verify():
    cfg  = current_app.config
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"success": False, "reason": "Không có dữ liệu JSON"}), 400

    token   = data.get("token")
    user_x  = data.get("user_x")
    events  = data.get("events", [])

    # 1. Kiểm tra token hợp lệ
    session = session_store.get(token)
    if not session:
        return jsonify({"success": False, "reason": "Token không hợp lệ hoặc đã hết hạn"}), 401

    # 2. Kiểm tra số lượng events tối thiểu
    if len(events) < cfg["MIN_EVENTS"]:
        return jsonify({"success": False, "reason": f"Dữ liệu hành vi không đủ (cần ≥ {cfg['MIN_EVENTS']} điểm)"}), 400

    # 3. Xác thực vị trí mảnh ghép
    puzzle_ok, puzzle_reason = PuzzleValidator.validate(
        user_x=user_x,
        target_x=session["target_x"],
        threshold=cfg["SNAP_THRESHOLD"],
    )
    if not puzzle_ok:
        session_store.delete(token)
        return jsonify({"success": False, "reason": puzzle_reason}), 200

    # 4. Phân tích hành vi
    behavior_ok, behavior_reason = BehaviorAnalyzer.analyze(
        events=events,
        max_avg_speed=cfg["MAX_AVG_SPEED"],
        min_avg_speed=cfg["MIN_AVG_SPEED"],
        min_direction_changes=cfg["MIN_DIRECTION_CHANGES"],
    )

    # Xóa token sau khi dùng (one-time use)
    session_store.delete(token)

    if not behavior_ok:
        return jsonify({"success": False, "reason": behavior_reason}), 200

    return jsonify({"success": True, "reason": "Xác thực thành công"}), 200


# ─────────────────────────────────────────────
# GET /captcha/image/<filename>
# Phục vụ ảnh puzzle từ static/images/
# ─────────────────────────────────────────────
@captcha_bp.route("/image/<filename>", methods=["GET"])
def serve_image(filename):
    from flask import send_from_directory
    import os
    images_dir = os.path.join(current_app.root_path, current_app.config["IMAGES_DIR"])
    return send_from_directory(images_dir, filename)
