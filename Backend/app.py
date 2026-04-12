from flask import Flask, request, jsonify
from flask_cors import CORS
from scoring_logic import BehaviorScorer

app = Flask(__name__)
# Cho phép Frontend từ file/domain khác gọi vào API
CORS(app) 

@app.route('/captcha/verify', methods=['POST'])
def verify_captcha():
    try:
        # --- BƯỚC 1: NHẬN REQUEST ---
        # Lấy payload từ body của request mà JS gửi lên
        payload = request.get_json()
        
        if not payload:
            return jsonify({"status": "error", "message": "No data received"}), 400

        # --- BƯỚC 2: XỬ LÝ LOGIC (CHẤM ĐIỂM) ---
        # Khởi tạo Class Logic và nạp payload vào
        scorer = BehaviorScorer(payload)
        # Thực hiện phân tích và lấy kết quả
        result = scorer.analyze() 

        # --- BƯỚC 3: TRẢ VỀ RESPONSE ---
        # Tạo cấu trúc JSON trả về để Frontend hiển thị
        response = {
            "status": "success",
            "is_human": result["is_human"],
            "score": result["score"],
            "received_events": len(payload.get("events", [])),
            "message": "Xác thực hoàn tất"
        }
        
        return jsonify(response), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)