# Hướng dẫn tích hợp CAPTCHA - Nhóm 03

Tài liệu này hướng dẫn cách chạy Backend và nhúng giao diện CAPTCHA vào một trang web đăng nhập đơn giản ở môi trường Local.

## 1. Khởi chạy hệ thống (Local)

Hệ thống của chúng ta gồm 2 phần chạy độc lập trên 2 Terminal (CMD) khác nhau.

### Bước 1: Khởi chạy Backend (API & AI Scoring)
1. Mở CMD, di chuyển vào thư mục Backend.
2. (Lần đầu) Cài đặt thư viện: pip install Flask flask-cors Pillow scikit-learn
3. Chạy lệnh: py app.py
-> Server Backend sẽ hoạt động tại http://127.0.0.1:5000

### Bước 2: Khởi chạy Frontend (Giao diện Captcha)
1. Mở một cửa sổ CMD mới, di chuyển vào thư mục Frontend (thư mục chứa file index_fixed.html).
2. Chạy lệnh: py -m http.server 3000
-> Giao diện Frontend sẽ hoạt động tại http://127.0.0.1:3000/index_fixed.html


## 2. Chú ý trước khi Deploy (Lên Server Thật)
1. Tạo requirements.txt: Ở thư mục Backend, chạy lệnh: pip freeze > requirements.txt
2. Đổi URL: Trong file js/config.js, đổi 127.0.0.1:5000 thành link backend thực tế.
3. Cấu hình CORS: Trong file Backend/app.py, giới hạn CORS(app) để chỉ cho phép domain web khách truy cập nhằm bảo mật API.