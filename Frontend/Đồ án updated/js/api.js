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
    setStatus("Kết quả: " + JSON.stringify(data), "green");
  } catch (err) {
    console.error(err);
    setStatus("Không gửi được backend.", "red");
  }
}