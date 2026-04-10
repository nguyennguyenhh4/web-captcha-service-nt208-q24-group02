export const dom = {
  puzzleContainer: document.getElementById("puzzleContainer"),
  hole: document.getElementById("target-hole"),
  piece: document.getElementById("puzzle-piece"),
  slider: document.getElementById("captchaSlider"),
  canvas: document.getElementById("drawCanvas"),
  clearCanvas: document.getElementById("clearCanvas"),
  submitBtn: document.getElementById("submitBtn"),
  resetBtn: document.getElementById("resetBtn"),
  status: document.getElementById("status-msg"),
  shapePrompt: document.getElementById("shapePrompt"),
  canvasTimer: document.getElementById("canvasTimer"),
  puzzleHint: document.getElementById("puzzleHint"),
};

export const ctx = dom.canvas.getContext("2d");