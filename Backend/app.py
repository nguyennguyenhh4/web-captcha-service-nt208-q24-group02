from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import random
import time
from scoring_logic import BehaviorScorer

app = Flask(__name__)
CORS(app)

captcha_db = {}
EXPIRE_DURATION = 300  

@app.route('/captcha/init', methods=['GET'])
def init_captcha():
    """Khởi tạo session: sinh tọa độ ngẫu nhiên, không cần ảnh"""
    token = str(uuid.uuid4())

    target_x = random.randint(80, 240)
    target_y = random.randint(10, 90)

    captcha_db[token] = {
        "target_x": target_x,
        "expire_time": time.time() + EXPIRE_DURATION,
        "status": "unused"
    }

    return jsonify({
        "token": token,
        "target_x": target_x,   
        "target_y": target_y,
    })

@app.route('/captcha/verify', methods=['POST'])
def verify():
    """API Task 3, 4, 5: Xác thực dữ liệu"""
    try:
        data = request.get_json()
        token = data.get("token")
        user_x = data.get("user_x") 

        if token not in captcha_db:
            return jsonify({"result": "bot", "msg": "Token không tồn tại"}), 400
        
        session = captcha_db[token]
        
        if time.time() > session["expire_time"]:
            session["status"] = "expired"
            return jsonify({"result": "bot", "msg": "Token đã hết hạn"}), 400
        
        if session["status"] == "used":
            return jsonify({"result": "bot", "msg": "Token đã được sử dụng"}), 400

        session["status"] = "used"

        diff = abs(user_x - session["target_x"])
        if diff > 10:
            return jsonify({"result": "bot", "msg": "Vị trí không chính xác"}), 200

        scorer = BehaviorScorer(data)
        behavior_result = scorer.analyze_behavior()
        
        return jsonify(behavior_result), 200

    except Exception as e:
        return jsonify({"result": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)