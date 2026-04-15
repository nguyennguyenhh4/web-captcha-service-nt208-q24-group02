let behaviorData = [];
let startTime = null;
let lastSampleTime = 0;
let currentToken = null;

function loadNewCaptcha() {
    fetch('http://127.0.0.1:5000/captcha/init')
        .then(res => res.json())
        .then(data => {
            currentToken = data.token;
            document.getElementById('bg-image').style.backgroundImage = `url(${data.bg})`;
            const piece = document.getElementById('puzzle-piece');
            piece.style.backgroundImage = `url(${data.piece})`;
            piece.style.top = data.y + 'px';
            piece.style.left = '0px';
            
            // Reset dữ liệu
            document.getElementById('captchaSlider').value = 0;
            document.getElementById('status-msg').innerText = "";
            behaviorData = [];
            startTime = null;
            console.log("Captcha loaded. Token:", currentToken);
        });
}

window.onload = loadNewCaptcha;

// Thu thập dữ liệu di chuyển
document.getElementById('captchaSlider').addEventListener('input', function(e) {
    if (!startTime) startTime = Date.now();
    const val = e.target.value;
    const currentX = (val / 100) * (300 - 50); // containerWidth - pieceSize
    document.getElementById('puzzle-piece').style.left = currentX + 'px';

    // Capture behavior
    const now = Date.now();
    if (now - lastSampleTime < 20) return;
    lastSampleTime = now;
    behaviorData.push({
        x: parseFloat((currentX / window.innerWidth).toFixed(4)),
        y: 0, // Trục Y coi như cố định trên slider
        t: now - startTime,
        type: 'slider-move'
    });
});

// Gửi xác thực
document.getElementById('submitBtn').addEventListener('click', function() {
    const finalX = parseFloat(document.getElementById('puzzle-piece').style.left);
    
    const payload = {
        token: currentToken,
        user_x: finalX, // Gửi vị trí cuối cùng để server check Task 4
        events: behaviorData
    };

    fetch('http://127.0.0.1:5000/captcha/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        const status = document.getElementById('status-msg');
        if (data.result === "human") {
            status.innerText = "Xác thực THÀNH CÔNG! Score: " + data.score;
            status.style.color = "green";
        } else {
            status.innerText = "Thất bại: " + (data.msg || "Phát hiện Bot!");
            status.style.color = "red";
            // Tự động đổi hình mới khi thất bại
            setTimeout(loadNewCaptcha, 1500);
        }
    });
});

document.getElementById('clearCanvas').addEventListener('click', function() {
    // 1. Gọi lại hàm loadNewCaptcha đã viết ở Task 1
    loadNewCaptcha(); 
    
    // 2. Xóa các dữ liệu cũ để đảm bảo tính chính xác cho lần kéo mới
    behaviorData = []; 
    startTime = null;
    
    // 3. (Tùy chọn) Xóa hình đã vẽ trên Canvas nếu bạn có dùng phần vẽ
    const canvas = document.getElementById('drawCanvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    console.log("Đã làm mới thử thách Captcha.");
});
