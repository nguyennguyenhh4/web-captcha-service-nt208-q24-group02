import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { clamp, distance } from "./utils.js";

function ensureStartTime() {
  if (state.startTime === null) state.startTime = Date.now();
}

function normalizePoint(clientX, clientY, area) {
  const rect = area.getBoundingClientRect();

  // FIX Bug #2: <canvas> has .width/.height as internal pixel dimensions (e.g. 300×150),
  // which can differ from CSS display size. Scale accordingly so coordinates match backend.
  // For non-canvas elements (div, etc.) .width is undefined → fall back to rect size (correct).
  const internalW = (area.tagName === "CANVAS" && area.width)  ? area.width  : rect.width;
  const internalH = (area.tagName === "CANVAS" && area.height) ? area.height : rect.height;
  const scaleX    = internalW / rect.width;
  const scaleY    = internalH / rect.height;

  const localX = clamp(clientX - rect.left, 0, rect.width)  * scaleX;
  const localY = clamp(clientY - rect.top,  0, rect.height) * scaleY;

  return {
    localX,
    localY,
    x: Number((localX / internalW).toFixed(4)),
    y: Number((localY / internalH).toFixed(4)),
  };
}

// FIX Bug #4: Thêm tham số `force` (mặc định false).
// canvas.js truyền force:true khi chuột/touch vừa chạm đỉnh polygon (hitNew=true),
// để event này không bị throttle 16ms bỏ qua → backend _validate_shape không bị fail.
export function captureEvent({ clientX, clientY, type, area, areaName, force = false }) {
  ensureStartTime();

  const now = Date.now();
  const isMove = type.includes("move");

  if (isMove && !force && now - state.lastSampleTime < CONFIG.samplingRate) return;

  const point = normalizePoint(clientX, clientY, area);
  const prev = state.lastPointByArea[areaName];

  let dt = 0;
  let speed = 0;

  if (prev) {
    dt = now - prev.timestamp;
    const dist = distance(prev.localX, prev.localY, point.localX, point.localY);
    speed = dt > 0 ? Number((dist / dt).toFixed(4)) : 0;
  }

  const event = {
    x: point.x,
    y: point.y,
    t: now - state.startTime,
    dt,
    speed,
    type,
    area: areaName,
  };

  if (prev && isMove && prev.x === event.x && prev.y === event.y) {
    return;
  }

  state.events.push(event);

  state.lastPointByArea[areaName] = {
    x: event.x,
    y: event.y,
    localX: point.localX,
    localY: point.localY,
    timestamp: now,
  };

  state.lastSampleTime = now;
}