# Hướng dẫn tích hợp CAPTCHA - Nhóm 02 (Đã sẵn sàng cho Vercel)

Tài liệu này hướng dẫn cách chạy thử dự án ở môi trường Local và cách Deploy lên Server (đặc biệt là Vercel).
Dự án đã được cấu trúc lại chuẩn Serverless: Frontend tĩnh được phục vụ ở thư mục gốc, và Backend API (Python) nằm trong thư mục `api/`.

## 1. Khởi chạy hệ thống để kiểm thử (Local)

Hệ thống đã được tinh chỉnh để chỉ cần chạy **1 lệnh Python duy nhất** là có thể khởi động cả giao diện web lẫn API.

### Bước 1: Cài đặt thư viện
1. Mở Terminal (CMD/PowerShell) tại thư mục gốc của dự án.
2. (Chỉ cần làm lần đầu) Cài đặt các thư viện bắt buộc bằng lệnh:
   ```bash
   pip install -r requirements.txt
   ```

### Bước 2: Chạy Server
1. Di chuyển vào thư mục `api`:
   ```bash
   cd api
   ```
2. Khởi chạy hệ thống:
   ```bash
   python index.py
   ```
3. Mở trình duyệt web và truy cập vào: **http://127.0.0.1:5000**
   -> Trang Đăng Nhập Demo có nhúng Captcha sẽ xuất hiện. Có thể test luồng xác thực bot ngay tại đây!

---

## 2. Triển khai (Deploy) lên Vercel

Dự án đã được thiết lập sẵn mọi cấu hình tự động (thông qua `vercel.json` và cấu trúc thư mục `api/`). 

Cách Deploy:
1. Đẩy toàn bộ mã nguồn này (bao gồm file `.gitignore`) lên một kho lưu trữ (Repository) trên **GitHub**.
2. Đăng nhập vào [Vercel](https://vercel.com).
3. Nhấn **Add New Project** ➔ Chọn **Import** kho lưu trữ GitHub vừa tạo.
4. Bấm **Deploy** (giữ nguyên mọi tùy chọn mặc định, không cần chỉnh sửa gì thêm).

Vercel sẽ tự động:
- Phục vụ các file tĩnh `index.html`, `captcha.html`, `js/`, `style_fixed.css` ra ngoài internet.
- Nhận diện thư mục `api/` và file `requirements.txt` để build mã Python thành API Serverless.
- Định tuyến các request gọi đến `/api/...` vào đúng logic Backend.
