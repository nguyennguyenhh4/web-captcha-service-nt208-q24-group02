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
const DOT_RADIUS = 8;         // Bán kính vùng hit-test của mỗi chấm (pixel)
const DOT_DRAW_RADIUS = 5;    // Bán kính vẽ chấm trên canvas

function buildPoints(shape, canvasWidth, canvasHeight) {
  const sideLength = 100;
  const radius = 50;
  const cx = canvasWidth / 2;
  const cy = canvasHeight / 2;
  const points = [];

  if (shape === "vuông") {
    // Thứ tự CW: trái-trên → phải-trên → phải-dưới → trái-dưới
    points.push(
      { x: cx - sideLength / 2, y: cy - sideLength / 2 },
      { x: cx + sideLength / 2, y: cy - sideLength / 2 },
      { x: cx + sideLength / 2, y: cy + sideLength / 2 },
      { x: cx - sideLength / 2, y: cy + sideLength / 2 },
    );
  } else if (shape === "tròn") {
    // 8 điểm CW bắt đầu từ 0°
    for (let angle = 0; angle < 360; angle += 45) {
      const rad = (angle * Math.PI) / 180;
      points.push({ x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) });
    }
  } else if (shape === "tam giác") {
    // Thứ tự CW: đỉnh → phải-dưới → trái-dưới
    points.push(
      { x: cx,                  y: cy - sideLength / 2 },
      { x: cx + sideLength / 2, y: cy + sideLength / 2 },
      { x: cx - sideLength / 2, y: cy + sideLength / 2 },
    );
  }

  return points.map((p, i) => ({ ...p, index: i }));
}

function drawDots(shape) {
  const ctx = dom.canvas.getContext("2d");
  const canvasWidth  = dom.canvas.width;
  const canvasHeight = dom.canvas.height;

  const points = buildPoints(shape, canvasWidth, canvasHeight);

  // Lưu vào state để dùng khi validate và gửi lên backend
  state.targetPoints = points;
  state.visitedDots  = new Array(points.length).fill(false);

  points.forEach((point, i) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, DOT_DRAW_RADIUS, 0, 2 * Math.PI);
    ctx.fillStyle = "#FF0000";
    ctx.fill();

    // Số thứ tự nhỏ bên cạnh chấm
    ctx.fillStyle = "#cc0000";
    ctx.font = "bold 11px sans-serif";
    ctx.fillText(i + 1, point.x + 7, point.y - 5);
  });
}

/**
 * Kiểm tra điểm vẽ (px, py) có chạm vào chấm nào chưa visited không.
 * Nếu có → đánh dấu visited, đổi màu chấm xanh lá.
 */
function checkDotHit(px, py) {
  const ctx = dom.canvas.getContext("2d");
  state.targetPoints.forEach((dot, i) => {
    if (state.visitedDots[i]) return;
    const dx = px - dot.x;
    const dy = py - dot.y;
    if (Math.sqrt(dx * dx + dy * dy) <= DOT_RADIUS) {
      state.visitedDots[i] = true;
      ctx.beginPath();
      ctx.arc(dot.x, dot.y, DOT_DRAW_RADIUS, 0, 2 * Math.PI);
      ctx.fillStyle = "#00aa44";
      ctx.fill();
    }
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
  state.targetPoints = [];
  state.visitedDots  = [];

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
    checkDotHit(p.x, p.y);

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
    checkDotHit(p.x, p.y);

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
      checkDotHit(p.x, p.y);

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
      checkDotHit(p.x, p.y);

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