# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from scoring_logic import BehaviorScorer
import traceback

app = Flask(__name__)
CORS(app)

@app.route('/captcha/verify', methods=['POST'])
def verify():
    try:
        data = request.get_json()
        
        # Khởi tạo lớp logic
        scorer = BehaviorScorer(data)
        # Gọi hàm xử lý
        result = scorer.analyze_behavior()
        
        return jsonify(result), 200

    except Exception as e:
        # In chi tiết lỗi ra Terminal để bạn sửa code
        print("--- SERVER ERROR ---")
        traceback.print_exc() 
        return jsonify({"result": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)