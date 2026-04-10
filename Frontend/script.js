// 1. Cấu hình
const CONFIG = {
    targetX: 200, // Vị trí ngang của lỗ
    targetY: 50,  // Vị trí dọc của lỗ
    samplingRate: 20, 
};

let behaviorData = [];
let startTime = null;
let lastSampleTime = 0;

// 2. Hàm khởi tạo (Chạy ngay khi load trang)
window.onload = function() {
    const piece = document.getElementById('puzzle-piece');
    const hole = document.getElementById('target-hole');
    const slider = document.getElementById('captchaSlider');

    // Đặt vị trí lỗ
    hole.style.left = CONFIG.targetX + 'px';
    hole.style.top = CONFIG.targetY + 'px';

    // Đặt vị trí mảnh ghép ban đầu
    piece.style.top = CONFIG.targetY + 'px';
    piece.style.left = '0px';

    // Cắt ảnh cho mảnh ghép khớp với vị trí lỗ
    piece.style.backgroundPosition = `-${CONFIG.targetX}px -${CONFIG.targetY}px`;

    // 3. Logic kéo thanh trượt
    slider.addEventListener('input', function(e) {
        if (!startTime) startTime = Date.now();

        const val = e.target.value; // Giá trị từ 0 đến 100
        const containerWidth = 300;
        const pieceSize = 50;
        const maxMove = containerWidth - pieceSize;
        
        // Tính toán vị trí X mới
        const currentX = (val / 100) * maxMove;
        
        // CẬP NHẬT VỊ TRÍ MẢNH GHÉP (Quan trọng nhất)
        piece.style.left = currentX + 'px';

        // Thu thập dữ liệu hành vi (Dùng tọa độ của chính mảnh ghép để không bị lỗi)
        const rect = piece.getBoundingClientRect();
        captureData(rect.left, rect.top, 'slider-move');
    });
};

// 4. Hàm thu thập dữ liệu (Task 4, 5, 6)
function captureData(rawX, rawY, type) {
    const now = Date.now();
    if (now - lastSampleTime < CONFIG.samplingRate) return;
    lastSampleTime = now;

    // Chuẩn hóa tọa độ x, y về khoảng 0 -> 1
    const normX = (rawX / window.innerWidth).toFixed(4);
    const normY = (rawY / window.innerHeight).toFixed(4);

    behaviorData.push({
        x: parseFloat(normX),
        y: parseFloat(normY),
        t: now - startTime,
        type: type
    });
}

// 5. Logic Vẽ Canvas (Giữ nguyên)
const canvas = document.getElementById('drawCanvas');
const ctx = canvas.getContext('2d');
let isDrawing = false;

canvas.addEventListener('mousedown', () => isDrawing = true);
window.addEventListener('mouseup', () => isDrawing = false);
canvas.addEventListener('mousemove', (e) => {
    if (!isDrawing) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    ctx.fillStyle = "#000";
    ctx.fillRect(x, y, 2, 2);
    captureData(e.clientX, e.clientY, 'drawing');
});

// 6. Gửi dữ liệu (Task 7)
document.getElementById('submitBtn').addEventListener('click', function() {
    const piece = document.getElementById('puzzle-piece');
    const finalX = parseFloat(piece.style.left);
    
    const payload = {
        token: "session_" + Math.random().toString(36).substr(2, 9),
        device: 'mouse',
        events: behaviorData
    };

    console.log("Dữ liệu gửi Backend:", payload);

    const diff = Math.abs(finalX - CONFIG.targetX);
    const status = document.getElementById('status-msg');

    if (diff < 10 && behaviorData.length > 5) {
        status.innerText = "Xác thực THÀNH CÔNG!";
        status.style.color = "green";
    } else {
        status.innerText = "Xác thực THẤT BẠI. Hãy kéo khớp hình!";
        status.style.color = "red";
    }
});