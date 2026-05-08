# CAPTCHA Service — Backend

Flask backend cho hệ thống CAPTCHA hành vi (slider puzzle + canvas drawing).

## Cài đặt

```bash
cd captcha_backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Cấu hình

```bash
cp .env.example .env
# Mở .env và đổi SECRET_KEY
```

## Thêm ảnh puzzle

Đặt các file `.jpg` / `.png` vào thư mục `static/images/`.
Backend sẽ random chọn ảnh mỗi lần gọi `/captcha/init`.

## Chạy

```bash
python app.py
```

Server khởi động tại `http://127.0.0.1:5000`.

## API

### GET /captcha/init

Khởi tạo phiên CAPTCHA mới.

**Response:**
```json
{
  "token":     "abc123...",
  "target_x":  210,
  "target_y":  0,
  "image_url": "/captcha/image/puzzle1.jpg"
}
```

---

### POST /captcha/verify

Gửi kết quả xác thực.

**Request body:**
```json
{
  "token":   "abc123...",
  "user_x":  208,
  "events":  [
    { "x": 10, "y": 50, "t": 1000, "dt": 20, "speed": 150 },
    ...
  ],
  "device":  "mouse",
  "pattern": "square"
}
```

**Response:**
```json
{ "success": true,  "reason": "Xác thực thành công" }
{ "success": false, "reason": "Mảnh ghép chưa khớp (sai số 25px, cho phép 10px)" }
```

---

### GET /captcha/image/\<filename\>

Phục vụ ảnh puzzle từ `static/images/`.

## Cấu trúc thư mục

```
captcha_backend/
├── app.py
├── config.py
├── routes/
│   ├── __init__.py
│   └── captcha_routes.py
├── services/
│   ├── session_service.py
│   ├── behavior_analyzer.py
│   └── puzzle_validator.py
├── storage/
│   ├── session_store.py
│   └── image_store.py
├── static/
│   └── images/          ← đặt ảnh puzzle vào đây
├── .env.example
├── requirements.txt
└── README.md
```
