import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { dom, ctx } from "./dom.js";
import { captureEvent } from "./capture.js";
import { setStatus } from "./ui.js";

// ✅ Đã xóa chooseRandomShape() — frontend không tự sinh hình nữa.
// Điểm target phải lấy từ server qua drawServerPoints().

const DOT_RADIUS      = 12;  // BUG FIX #2: tăng vùng hit từ 8→12px  // Bán kính vùng hit-test của mỗi chấm (pixel)
const DOT_DRAW_RADIUS = 5;  // Bán kính vẽ chấm trên canvas

/**
 * ✅ HÀM MỚI — Nhận targetPoints từ server và vẽ lên canvas.
 * Thay thế hoàn toàn buildPoints() + drawDots() cũ vốn tự sinh hình riêng.
 *
 * @param {Array<{x: number, y: number, index: number}>} serverPoints
 *   Tọa độ pixel canvas (trong không gian 300×150) do server tạo ra từ /captcha/init.
 */
export function drawServerPoints(serverPoints) {
  const canvasCtx = dom.canvas.getContext("2d");

  // Lưu vào state — đây là bộ điểm backend sẽ validate, phải khớp 1-1
  state.targetPoints = serverPoints.map((p, i) => ({ x: p.x, y: p.y, index: i }));
  state.visitedDots  = new Array(serverPoints.length).fill(false);

  // Xóa canvas rồi vẽ lại điểm mới
  canvasCtx.clearRect(0, 0, dom.canvas.width, dom.canvas.height);

  serverPoints.forEach((point, i) => {
    // point.x, point.y là pixel tọa độ trong canvas 300×150 (gửi từ server)
    canvasCtx.beginPath();
    canvasCtx.arc(point.x, point.y, DOT_DRAW_RADIUS, 0, 2 * Math.PI);
    canvasCtx.fillStyle = "#FF0000";
    canvasCtx.fill();

    // Số thứ tự nhỏ bên cạnh chấm
    canvasCtx.fillStyle = "#cc0000";
    canvasCtx.font = "bold 11px sans-serif";
    canvasCtx.fillText(i + 1, point.x + 7, point.y - 5);
  });

  // BUG 3 FIX — Reset hint về trạng thái ban đầu khi có bộ điểm mới
  _hideCloseHint();
}

/**
 * Kiểm tra điểm vẽ (px, py) có chạm vào chấm nào chưa visited không.
 * Nếu có → đánh dấu visited, đổi màu chấm xanh lá.
 * Trả về true nếu vừa hit ít nhất một chấm mới (dùng cho Bug 1 fix).
 *
 * @returns {boolean}
 */
function checkDotHit(px, py) {
  const canvasCtx = dom.canvas.getContext("2d");
  let hitNew = false;

  state.targetPoints.forEach((dot, i) => {
    if (state.visitedDots[i]) return;
    const dx = px - dot.x;
    const dy = py - dot.y;
    if (Math.sqrt(dx * dx + dy * dy) <= DOT_RADIUS) {
      state.visitedDots[i] = true;
      hitNew = true;
      canvasCtx.beginPath();
      canvasCtx.arc(dot.x, dot.y, DOT_DRAW_RADIUS, 0, 2 * Math.PI);
      canvasCtx.fillStyle = "#00aa44";
      canvasCtx.fill();
    }
  });

  return hitNew;
}

// ---------------------------------------------------------------------------
// BUG 3 HELPERS — Close-shape hint
// ---------------------------------------------------------------------------

/**
 * Hiện gợi ý "Kéo về điểm đầu để khép kín hình" sau khi user bắt đầu vẽ.
 * Chỉ hiện một lần mỗi phiên (biến _hintShown đặt lại khi có điểm mới).
 */
let _hintShown = false;

function _showCloseHint() {
  if (_hintShown) return;
  _hintShown = true;
  setStatus("Vẽ qua tất cả các điểm rồi kéo về điểm xuất phát để khép kín hình.", "blue");
}

function _hideCloseHint() {
  _hintShown = false;
}

// ---------------------------------------------------------------------------

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
      // BUG FIX #2: bỏ canvasLocked — timer chỉ là thông tin, không khóa canvas
      clearInterval(state.canvasTimerId);
      state.canvasTimerId = null;
      updateCanvasTimerText("Hết giờ");
    }
  }, 100);
}

function getCanvasPos(e) {
  const rect   = dom.canvas.getBoundingClientRect();
  // Scale tọa độ CSS → canvas internal pixel
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
  _hideCloseHint(); // BUG 3 FIX — reset hint khi clear
}

// ✅ resetCanvas() giờ chỉ clear — KHÔNG tự sinh hình nữa.
// main.js sẽ gọi initSession() → drawServerPoints() sau khi clear.
export function resetCanvas() {
  clearCanvasOnly();
}

export function initCanvasEvents() {
  dom.canvas.addEventListener("mousedown", (e) => {
    // BUG FIX #2: removed canvasLocked check — timer is informational only

    state.device = "mouse";
    state.drawing = true;
    startCanvasTimer();
    _showCloseHint(); // BUG 3 FIX — hint khép kín lần đầu vẽ

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
    if (!state.drawing) return; // BUG FIX #2: removed canvasLocked check

    state.device = "mouse";

    const p = getCanvasPos(e);
    drawPoint(p.x, p.y);

    // BUG 1 FIX — checkDotHit trả về true nếu vừa chạm chấm mới.
    // Khi đó truyền force:true để captureEvent bỏ qua throttle 16ms,
    // đảm bảo backend nhận đúng tọa độ hit dù chuột đi qua rất nhanh.
    const hitNew = checkDotHit(p.x, p.y);

    captureEvent({
      clientX: p.clientX,
      clientY: p.clientY,
      type: "mousemove",
      area: dom.canvas,
      areaName: "canvas",
      force: hitNew, // BUG 1 FIX
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
      // BUG FIX #2: removed canvasLocked check — timer is informational only

      state.device = "touch";
      state.drawing = true;
      startCanvasTimer();
      _showCloseHint(); // BUG 3 FIX — hint khép kín lần đầu vẽ

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
      if (!state.drawing) return; // BUG FIX #2: removed canvasLocked check

      state.device = "touch";

      const p = getCanvasPos(e);
      drawPoint(p.x, p.y);

      // BUG 1 FIX — same force logic as mousemove
      const hitNew = checkDotHit(p.x, p.y);

      captureEvent({
        clientX: p.clientX,
        clientY: p.clientY,
        type: "touchmove",
        area: dom.canvas,
        areaName: "canvas",
        force: hitNew, // BUG 1 FIX
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

  dom.clearCanvas.addEventListener("click", async () => {
    // ✅ Khi clear: reset state, gọi lại server để lấy targetPoints mới
    clearCanvasOnly();
    setStatus("Đang tải hình mới...", "blue");
    try {
      const res = await fetch(CONFIG.initUrl);
      const data = await res.json();
      // Cập nhật token và điểm mới từ server
      state.token = data.token;  // BUG FIX #7: dùng trực tiếp state đã import, không dùng dynamic import()
      if (data.targetPoints && data.targetPoints.length > 0) {
        drawServerPoints(data.targetPoints);
      }
      setStatus("Đã xóa canvas. Vẽ lại theo mẫu mới.", "blue");
    } catch (err) {
      setStatus("Không lấy được hình mới từ server.", "red");
    }
  });
}