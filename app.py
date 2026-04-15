from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import base64
import random
import os
import time
from io import BytesIO
from PIL import Image, ImageDraw
from scoring_logic import BehaviorScorer

app = Flask(__name__)
CORS(app)

# --- CẤU HÌNH TASK 2 ---
captcha_db = {} 
EXPIRE_DURATION = 300 # Token hết hạn sau 5 phút (300 giây)

def create_captcha_images():
    """Task 1: Sinh ảnh. Trả về: bg_b64, piece_b64, target_x, target_y"""
    img_dir = "images"
    size = 50
    if os.path.exists(img_dir) and os.listdir(img_dir):
        files = [f for f in os.listdir(img_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        bg = Image.open(os.path.join(img_dir, random.choice(files))).convert('RGB')
    else:
        bg = Image.new('RGB', (300, 150), color=(200, 200, 200))
    
    bg = bg.resize((300, 150))
    target_x = random.randint(80, 240)
    target_y = random.randint(10, 90)
    
    piece = bg.crop((target_x, target_y, target_x + size, target_y + size))
    draw = ImageDraw.Draw(bg)
    draw.rectangle([target_x, target_y, target_x + size, target_y + size], fill=(0, 0, 0, 180))

    def to_base64(img):
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    return to_base64(bg), to_base64(piece), target_x, target_y

@app.route('/captcha/init', methods=['GET'])
def init_captcha():
    """API Task 1 & 2: Khởi tạo và lưu Session"""
    bg_b64, piece_b64, tx, ty = create_captcha_images()
    token = str(uuid.uuid4())
    
    # --- TASK 2: LƯU DB ---
    captcha_db[token] = {
        "target_x": tx,
        "expire_time": time.time() + EXPIRE_DURATION,
        "status": "unused"
    }
    
    return jsonify({
        "token": token,
        "bg": "data:image/png;base64," + bg_b64,
        "piece": "data:image/png;base64," + piece_b64,
        "y": ty
    })

@app.route('/captcha/verify', methods=['POST'])
def verify():
    """API Task 3, 4, 5: Xác thực dữ liệu"""
    try:
        data = request.get_json()
        token = data.get("token")
        user_x = data.get("user_x") # Vị trí X người dùng đã kéo tới

        # 1. Kiểm tra Token (Task 2 & 5)
        if token not in captcha_db:
            return jsonify({"result": "bot", "msg": "Token không tồn tại"}), 400
        
        session = captcha_db[token]
        
        if time.time() > session["expire_time"]:
            session["status"] = "expired"
            return jsonify({"result": "bot", "msg": "Token đã hết hạn"}), 400
        
        if session["status"] == "used":
            return jsonify({"result": "bot", "msg": "Token đã được sử dụng"}), 400

        # Đánh dấu đã sử dụng (Anti-replay)
        session["status"] = "used"

        # 2. Kiểm tra vị trí khớp (Task 4: sai số < 10px)
        diff = abs(user_x - session["target_x"])
        if diff > 10:
            return jsonify({"result": "bot", "msg": "Vị trí không chính xác"}), 200

        # 3. Kiểm tra hành vi (Task 7: Scoring)
        scorer = BehaviorScorer(data)
        behavior_result = scorer.analyze_behavior()
        
        return jsonify(behavior_result), 200

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)