import { state } from "./state.js";
import { setStatus } from "./ui.js";
import { submitCaptcha } from "./api.js";
import { initPuzzleEvents, resetPuzzle } from "./puzzle.js";
import { initCanvasEvents, resetCanvas } from "./canvas.js";

function resetSessionState() {
  state.token = "demo_" + Math.random().toString(36).slice(2, 10);
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

function resetAll() {
  resetSessionState();
  resetPuzzle();
  resetCanvas();
  setStatus("CAPTCHA sẵn sàng.", "blue");
}

window.onload = () => {
  resetPuzzle();
  resetCanvas();
  initPuzzleEvents();
  initCanvasEvents();

  document.getElementById("submitBtn").addEventListener("click", submitCaptcha);
  document.getElementById("resetBtn").addEventListener("click", resetAll);

  setStatus("CAPTCHA sẵn sàng.", "blue");
};