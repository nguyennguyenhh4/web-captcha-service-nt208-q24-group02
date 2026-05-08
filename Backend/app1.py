from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import base64
import random
import os
import time
from io import BytesIO
from PIL import Image, ImageDraw

# Import logic chấm điểm từ file của thành viên 3
from scoring_logic import BehaviorScorer

app = Flask(__name__)
CORS(app)  # Cho phép Frontend gọi API mà không bị chặn

# --- CẤU HÌNH HỆ THỐNG ---
captcha_db = {} 
EXPIRE_DURATION = 300  # Token hết hạn sau 5 phút (300 giây)
IMAGE_DIR = "images"   # Thư mục chứa ảnh nền của bạn

def create_captcha_images():
    """
    Task 1: Sinh ảnh Captcha (Background và Piece)
    """
    size = 50 # Kích thước mảnh ghép vuông
    
    # Kiểm tra thư mục ảnh
    if os.path.exists(IMAGE_DIR) and os.listdir(IMAGE_DIR):
        files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        bg = Image.open(os.path.join(IMAGE_DIR, random.choice(files))).convert('RGB')
    else:
        # Nếu không có ảnh, tạo nền xám mặc định
        bg = Image.new('RGB', (300, 150), color=(200, 200, 200))
    
    bg = bg.resize((300, 150))
    target_x = random.randint(80, 240)
    target_y = random.randint(10, 90)
    
    # Cắt mảnh ghép
    piece = bg.crop((target_x, target_y, target_x + size, target_y + size))
    
    # Tạo lỗ đen trên ảnh nền
    bg_with_hole = bg.copy()
    draw = ImageDraw.Draw(bg_with_hole)
    draw.rectangle([target_x, target_y, target_x + size, target_y + size], fill=(0, 0, 0, 180))

    def to_base64(img):
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    return to_base64(bg_with_hole), to_base64(piece), target_x, target_y

# --- ROUTES ---

@app.route('/captcha/init', methods=['GET'])
def init_captcha():
    """
    API Khởi tạo: Sinh thử thách và tạo Token
    """
    try:
        bg_b64, piece_b64, tx, ty = create_captcha_images()
        token = str(uuid.uuid4())
        
        # Lưu vào bộ nhớ tạm
        captcha_db[token] = {
            "target_x": tx,
            "expire_time": time.time() + EXPIRE_DURATION,
            "status": "unused"
        }
        
        print(f"[INIT] Đã tạo Token: {token} | Target X: {tx}")
        
        return jsonify({
            "token": token,
            "bg": "data:image/png;base64," + bg_b64,
            "piece": "data:image/png;base64," + piece_b64,
            "y": ty
        })
    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500

@app.route('/captcha/verify', methods=['POST'])
def verify():
    """
    API dùng để TEST: Bỏ qua kiểm tra Token và Vị trí, 
    chỉ tập trung chạy scoring_logic.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"result": "error", "msg": "Dữ liệu JSON rỗng"}), 400

        print("--- Đang test Scoring Logic ---")
        
        # BƯỚC QUAN TRỌNG: Gọi thẳng BehaviorScorer mà không check token/vị trí
        scorer = BehaviorScorer(data)
        behavior_result = scorer.analyze_behavior()
        
        # Log kết quả ra console để bạn theo dõi
        print(f"Kết quả phân tích: {behavior_result}")
        
        # Trả về kết quả cho Frontend
        return jsonify({
            "status": "testing_mode",
            "scoring_output": behavior_result
        }), 200

    except Exception as e:
        print(f"Lỗi khi chạy logic: {str(e)}")
        return jsonify({"result": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Chạy server ở port 5000
    print("--- Captcha Backend đang chạy tại http://127.0.0.1:5000 ---")
    app.run(debug=True, port=5000)