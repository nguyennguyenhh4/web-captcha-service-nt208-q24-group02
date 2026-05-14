import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { setStatus } from "./ui.js";
import { submitCaptcha } from "./api.js";
import { initPuzzleEvents, resetPuzzle } from "./puzzle.js";
import { initCanvasEvents, clearCanvasOnly, drawServerPoints } from "./canvas.js"; // drawServerPoints

async function initSession() {
  try {
    const res = await fetch(CONFIG.initUrl);
    const data = await res.json();
    state.token = data.token;
    resetPuzzle(data.target_x, data.target_y);
    console.log("Token:", state.token, "| targetX:", data.target_x, "| targetY:", data.target_y);

    // Dùng targetPoints từ server để vẽ lên canvas
    if (data.targetPoints && data.targetPoints.length > 0) {
      drawServerPoints(data.targetPoints);
    } else {
      console.warn("Server không trả về targetPoints!");
    }
  } catch (err) {
    console.warn("Backend offline — không lấy được targetPoints:", err);
    resetPuzzle(null, null);
    // Khi offline không có điểm nào để vẽ → báo user
    setStatus("Không kết nối được backend.", "red");
  }
}

function resetSessionState() {
  // Phải clear interval TRƯỚC khi null hóa — nếu null hóa trước thì clearCanvasOnly()
  // sẽ không còn tham chiếu để clearInterval(), interval cũ vẫn chạy ngầm
  // và sẽ set canvasLocked = true cho session mới → canvas bị treo.
  if (state.canvasTimerId) {
    clearInterval(state.canvasTimerId);
  }
  state.token = "demo_" + Math.random().toString(36).slice(2, 10);
  state.startTime = null;
  state.device = "unknown";
  state.events = [];
  state.lastSampleTime = 0;
  state.lastPointByArea = { puzzle: null, canvas: null };
  state.drawing = false;
  state.canvasLocked = false;
  state.canvasStartTime = null;
  state.canvasTimerId = null;
  state.puzzleSolved = false;
}

async function resetAll() {
  resetSessionState();
  clearCanvasOnly(); // Chỉ clear canvas, đợi server trả về targetPoints
  await initSession();
  setStatus("CAPTCHA sẵn sàng.", "blue");
}

window.onload = async () => {
  clearCanvasOnly(); // Chỉ clear canvas khi load, KHÔNG gọi resetCanvas() (vốn sinh hình ngẫu nhiên)
  initPuzzleEvents();
  initCanvasEvents();

  await initSession(); // initSession sẽ gọi drawServerPoints với điểm từ server

  document.getElementById("submitBtn").addEventListener("click", submitCaptcha);
  document.getElementById("resetBtn").addEventListener("click", resetAll);

  setStatus("CAPTCHA sẵn sàng.", "blue");
};
