import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { dom, ctx } from "./dom.js";
import { randomInt } from "./utils.js";
import { captureEvent } from "./capture.js";
import { setStatus } from "./ui.js";

export function chooseRandomShape() {
  const shapes = ["vuông", "tròn", "tam giác"];
  state.expectedShape = shapes[randomInt(0, shapes.length - 1)];

  if (dom.shapePrompt) {
    dom.shapePrompt.innerText = `Hãy vẽ theo mẫu: ${state.expectedShape}`;
  }
}

function updateCanvasTimerText(text) {
  if (dom.canvasTimer) dom.canvasTimer.textContent = text;
}

export function startCanvasTimer() {
  if (state.canvasStartTime !== null) return;

  state.canvasStartTime = Date.now();
  state.canvasLocked = false;
  updateCanvasTimerText("3.0s");

  state.canvasTimerId = setInterval(() => {
    const elapsed = Date.now() - state.canvasStartTime;
    const remain = Math.max(0, CONFIG.minCanvasDurationMs - elapsed);

    updateCanvasTimerText((remain / 1000).toFixed(1) + "s");

    if (elapsed >= CONFIG.minCanvasDurationMs) {
      state.canvasLocked = true;
      clearInterval(state.canvasTimerId);
      state.canvasTimerId = null;
      updateCanvasTimerText("Hết giờ");
      setStatus("Hết 3 giây vẽ.", "orange");
    }
  }, 100);
}

function getCanvasPos(e) {
  const rect = dom.canvas.getBoundingClientRect();

  if (e.touches && e.touches[0]) {
    return {
      x: e.touches[0].clientX - rect.left,
      y: e.touches[0].clientY - rect.top,
      clientX: e.touches[0].clientX,
      clientY: e.touches[0].clientY,
    };
  }

  if (e.changedTouches && e.changedTouches[0]) {
    return {
      x: e.changedTouches[0].clientX - rect.left,
      y: e.changedTouches[0].clientY - rect.top,
      clientX: e.changedTouches[0].clientX,
      clientY: e.changedTouches[0].clientY,
    };
  }

  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
    clientX: e.clientX,
    clientY: e.clientY,
  };
}

function drawPoint(x, y) {
  ctx.fillStyle = "#000";
  ctx.fillRect(x, y, 2, 2);
}

export function clearCanvasOnly() {
  ctx.clearRect(0, 0, dom.canvas.width, dom.canvas.height);
  state.canvasLocked = false;
  state.canvasStartTime = null;
  state.drawing = false;
  state.lastPointByArea.canvas = null;

  if (state.canvasTimerId) {
    clearInterval(state.canvasTimerId);
    state.canvasTimerId = null;
  }

  updateCanvasTimerText("3.0s");
}

export function resetCanvas() {
  clearCanvasOnly();
  chooseRandomShape();
}

export function initCanvasEvents() {
  dom.canvas.addEventListener("mousedown", (e) => {
    if (state.canvasLocked) return;

    state.device = "mouse";
    state.drawing = true;
    startCanvasTimer();

    const p = getCanvasPos(e);
    drawPoint(p.x, p.y);

    captureEvent({
      clientX: p.clientX,
      clientY: p.clientY,
      type: "mousedown",
      area: dom.canvas,
      areaName: "canvas",
    });
  });

  dom.canvas.addEventListener("mousemove", (e) => {
    if (!state.drawing || state.canvasLocked) return;

    state.device = "mouse";

    const p = getCanvasPos(e);
    drawPoint(p.x, p.y);

    captureEvent({
      clientX: p.clientX,
      clientY: p.clientY,
      type: "mousemove",
      area: dom.canvas,
      areaName: "canvas",
    });
  });

  window.addEventListener("mouseup", (e) => {
    if (!state.drawing) return;

    state.drawing = false;
    state.device = "mouse";

    const p = getCanvasPos(e);
    captureEvent({
      clientX: p.clientX,
      clientY: p.clientY,
      type: "mouseup",
      area: dom.canvas,
      areaName: "canvas",
    });
  });

  dom.canvas.addEventListener(
    "touchstart",
    (e) => {
      e.preventDefault();
      if (state.canvasLocked) return;

      state.device = "touch";
      state.drawing = true;
      startCanvasTimer();

      const p = getCanvasPos(e);
      drawPoint(p.x, p.y);

      captureEvent({
        clientX: p.clientX,
        clientY: p.clientY,
        type: "touchstart",
        area: dom.canvas,
        areaName: "canvas",
      });
    },
    { passive: false }
  );

  dom.canvas.addEventListener(
    "touchmove",
    (e) => {
      e.preventDefault();
      if (!state.drawing || state.canvasLocked) return;

      state.device = "touch";

      const p = getCanvasPos(e);
      drawPoint(p.x, p.y);

      captureEvent({
        clientX: p.clientX,
        clientY: p.clientY,
        type: "touchmove",
        area: dom.canvas,
        areaName: "canvas",
      });
    },
    { passive: false }
  );

  window.addEventListener("touchend", (e) => {
    if (!state.drawing) return;

    state.drawing = false;
    state.device = "touch";

    const p = getCanvasPos(e);
    captureEvent({
      clientX: p.clientX,
      clientY: p.clientY,
      type: "touchend",
      area: dom.canvas,
      areaName: "canvas",
    });
  });

  dom.clearCanvas.addEventListener("click", () => {
    resetCanvas();
    setStatus("Đã xóa canvas. Vẽ lại theo mẫu mới.", "blue");
  });
}