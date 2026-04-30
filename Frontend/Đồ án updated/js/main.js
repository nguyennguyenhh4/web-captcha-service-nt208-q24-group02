import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { setStatus } from "./ui.js";
import { submitCaptcha } from "./api.js";
import { initPuzzleEvents, resetPuzzle } from "./puzzle.js";
import { initCanvasEvents, resetCanvas } from "./canvas.js";

async function initSession() {
  try {
    const res = await fetch(CONFIG.initUrl);
    const data = await res.json();
    state.token = data.token;
    console.log("Token:", state.token);
  } catch (err) {
    console.error("Lỗi kết nối backend:", err);
    setStatus("Không kết nối được backend.", "red");
  }
}

function resetSessionState() {
  state.token = null;
  state.startTime = null;
  state.device = "unknown";
  state.events = [];
  state.lastSampleTime = 0;
  state.lastPointByArea = {
    puzzle: null,
    canvas: null,
  };
  state.drawing = false;
  state.canvasLocked = false;
  state.canvasStartTime = null;
  state.canvasTimerId = null;
  state.puzzleSolved = false;
}

async function resetAll() {
  resetSessionState();
  resetPuzzle();
  resetCanvas();
  await initSession();
  setStatus("CAPTCHA sẵn sàng.", "blue");
}

window.onload = async () => {
  resetPuzzle();
  resetCanvas();
  initPuzzleEvents();
  initCanvasEvents();

  await initSession();

  document.getElementById("submitBtn").addEventListener("click", submitCaptcha);
  document.getElementById("resetBtn").addEventListener("click", resetAll);

  setStatus("CAPTCHA sẵn sàng.", "blue");
};