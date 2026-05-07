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

  // Vẽ dấu chấm theo hình đã chọn
  drawDots(state.expectedShape);
}
function drawDots(shape) {
  const ctx = dom.canvas.getContext("2d");
  ctx.fillStyle = "#FF0000";  // Màu đỏ cho dấu chấm
  const canvasWidth = dom.canvas.width;
  const canvasHeight = dom.canvas.height;

  const sideLength = 100;  // Độ dài cạnh cho hình vuông
  const radius = 50;  // Bán kính cho hình tròn
  const points = [];  // Mảng chứa các điểm vẽ dấu chấm

  // Vẽ dấu chấm theo hình vuông
  if (shape === "vuông") {
    points.push(
      { x: canvasWidth / 2 - sideLength / 2, y: canvasHeight / 2 - sideLength / 2 },  // Góc trái trên
      { x: canvasWidth / 2 + sideLength / 2, y: canvasHeight / 2 - sideLength / 2 },  // Góc phải trên
      { x: canvasWidth / 2 - sideLength / 2, y: canvasHeight / 2 + sideLength / 2 },  // Góc trái dưới
      { x: canvasWidth / 2 + sideLength / 2, y: canvasHeight / 2 + sideLength / 2 }   // Góc phải dưới
    );
  }

  // Vẽ dấu chấm theo hình tròn
  else if (shape === "tròn") {
    const centerX = canvasWidth / 2;
    const centerY = canvasHeight / 2;
    for (let angle = 0; angle < 360; angle += 45) {  // Chia thành các điểm trên vòng tròn
      const radian = (angle * Math.PI) / 180;
      const x = centerX + radius * Math.cos(radian);
      const y = centerY + radius * Math.sin(radian);
      points.push({ x, y });
    }
  }

  // Vẽ dấu chấm theo hình tam giác
  else if (shape === "tam giác") {
    points.push(
      { x: canvasWidth / 2, y: canvasHeight / 2 - sideLength / 2 },  // Đỉnh tam giác
      { x: canvasWidth / 2 - sideLength / 2, y: canvasHeight / 2 + sideLength / 2 },  // Góc trái dưới
      { x: canvasWidth / 2 + sideLength / 2, y: canvasHeight / 2 + sideLength / 2 }   // Góc phải dưới
    );
  }

  // Vẽ các dấu chấm
  points.forEach(point => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, 5, 0, 2 * Math.PI);  // Vẽ dấu chấm nhỏ
    ctx.fill();
  });
}

function updateCanvasTimerText(text) {
  if (dom.canvasTimer) dom.canvasTimer.textContent = text;
}

export function startCanvasTimer() {
  if (state.canvasStartTime !== null) return;

  state.canvasStartTime = Date.now();
  state.canvasLocked = false;
  updateCanvasTimerText("5.0s");

  state.canvasTimerId = setInterval(() => {
    const elapsed = Date.now() - state.canvasStartTime;
    const remain = Math.max(0, CONFIG.minCanvasDurationMs - elapsed);

    updateCanvasTimerText((remain / 1000).toFixed(1) + "s");

    if (elapsed >= CONFIG.minCanvasDurationMs) {
      state.canvasLocked = true;
      clearInterval(state.canvasTimerId);
      state.canvasTimerId = null;
      updateCanvasTimerText("Hết giờ");
      // [ĐÃ XÓA] setStatus("Hết 5 giây vẽ.", "orange");
    }
  }, 100);
}

function getCanvasPos(e) {
  const rect   = dom.canvas.getBoundingClientRect();
  // [ĐÃ SỬA] Scale tọa độ CSS → canvas internal pixel
  const scaleX = dom.canvas.width  / rect.width;
  const scaleY = dom.canvas.height / rect.height;

  if (e.touches && e.touches[0]) {
    return {
      x: (e.touches[0].clientX - rect.left) * scaleX,
      y: (e.touches[0].clientY - rect.top)  * scaleY,
      clientX: e.touches[0].clientX,
      clientY: e.touches[0].clientY,
    };
  }

  if (e.changedTouches && e.changedTouches[0]) {
    return {
      x: (e.changedTouches[0].clientX - rect.left) * scaleX,
      y: (e.changedTouches[0].clientY - rect.top)  * scaleY,
      clientX: e.changedTouches[0].clientX,
      clientY: e.changedTouches[0].clientY,
    };
  }

  return {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top)  * scaleY,
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

  updateCanvasTimerText("5.0s");
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