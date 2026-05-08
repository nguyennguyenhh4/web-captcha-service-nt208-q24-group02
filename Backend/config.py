import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Bảo mật
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

    # Session
    TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", 300))   # token hết hạn sau 5 phút

    # Puzzle
    SNAP_THRESHOLD = int(os.getenv("SNAP_THRESHOLD", 10))           # sai số cho phép (px)
    PIECE_SIZE     = int(os.getenv("PIECE_SIZE", 60))               # kích thước mảnh ghép (px)
    CANVAS_WIDTH   = int(os.getenv("CANVAS_WIDTH", 400))            # chiều rộng ảnh puzzle

    # Hành vi (behavior)
    MIN_EVENTS          = int(os.getenv("MIN_EVENTS", 6))           # số events tối thiểu
    MAX_AVG_SPEED       = float(os.getenv("MAX_AVG_SPEED", 5))      # px/ms - quá nhanh → bot (~5px mỗi ms)
    MIN_AVG_SPEED       = float(os.getenv("MIN_AVG_SPEED", 0.001))  # px/ms - quá chậm/teleport
    MIN_DIRECTION_CHANGES = int(os.getenv("MIN_DIRECTION_CHANGES", 1))  # phải có thay đổi hướng

    # Ảnh puzzle
    IMAGES_DIR = os.getenv("IMAGES_DIR", "static/images")
