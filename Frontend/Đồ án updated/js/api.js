import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { dom } from "./dom.js";
import { setStatus } from "./ui.js";

export async function submitCaptcha() {
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
    targetPoints:  state.targetPoints,
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    console.log("RESPONSE:", data);

    // ✅ BUG FIX #1: Backend trả về {"result":"human"} hoặc {"result":"bot"},
    // KHÔNG phải {"status":"success"}. Code cũ luôn vào nhánh else → luôn fail!
    if (data.result === "human") {
      setStatus("✅ Xác thực thành công!", "green");
      window.parent.postMessage({ type: "CAPTCHA_RESULT", status: "success", token: payload.token }, "*");
    } else {
      // Lấy message từ data.message hoặc data.msg (backend dùng cả hai tên)
      const msg = data.message || data.msg || "❌ Xác thực thất bại!";
      setStatus(msg, "red");
      window.parent.postMessage({ type: "CAPTCHA_RESULT", status: "failed" }, "*");
      setTimeout(() => { document.getElementById("resetBtn").click(); }, 1500);
    }
  } catch (err) {
    console.error(err);
    setStatus("Không gửi được backend.", "red");
  }
}