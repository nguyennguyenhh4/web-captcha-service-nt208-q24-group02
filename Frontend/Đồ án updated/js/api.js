import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { dom } from "./dom.js";
import { setStatus } from "./ui.js";

export async function submitCaptcha() {
  // Tính vị trí X thực tế từ slider
  const sliderEl = document.getElementById("captchaSlider");
  const container = document.getElementById("puzzleContainer");
  const maxMove = container.offsetWidth - CONFIG.pieceSize;
  const user_x = Math.round((Number(sliderEl.value) / 100) * maxMove);

  const payload = {
    token: state.token,
    user_x: user_x,
    startTime: state.startTime,
    device: state.device,
    expectedShape: state.expectedShape,
    targetPoints:  state.targetPoints,                      // [{x, y, index}]
    canvasWidth:   dom.canvas?.width  || 300,
    canvasHeight:  dom.canvas?.height || 150,
    events: state.events,
  };

  console.log("PAYLOAD:", payload);

  if (!state.token) {
    setStatus("Chưa có token. Tải lại trang.", "red");
    return;
  }

  if (!state.puzzleSolved) {
    setStatus("Puzzle chưa khớp.", "red");
    return;
  }

  if (payload.events.length < 6) {
    setStatus("Dữ liệu hành vi quá ít.", "red");
    return;
  }

  try {
    const res = await fetch(CONFIG.verifyUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

   if (data.status === "success") {
        // In ra màn hình dòng chữ "✅ Xác thực thành công!" màu xanh
        setStatus(data.message, "green");
        
        // Báo cho Web Khách (website nhúng iframe) biết để mở khóa nút Đăng nhập
        window.parent.postMessage({
            type: "CAPTCHA_RESULT",
            status: "success",
            token: payload.token
        }, "*");
    } else {
        // In ra màn hình dòng chữ báo lỗi màu đỏ
        setStatus(data.message || "❌ Xác thực thất bại!", "red");
        
        // Báo cho Web Khách biết là thất bại
        window.parent.postMessage({
            type: "CAPTCHA_RESULT",
            status: "failed"
        }, "*");
        
        // Tự động bấm nút "Tải lại trang/hình mới" sau 1.5 giây để người dùng làm lại
        setTimeout(() => {
            document.getElementById("resetBtn").click();
        }, 1500);
    }
  }
  catch (err) {
    console.error(err);
    setStatus("Không gửi được backend.", "red");
  }
}