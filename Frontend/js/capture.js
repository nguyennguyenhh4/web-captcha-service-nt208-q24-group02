import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { clamp, distance } from "./utils.js";

function ensureStartTime() {
  if (state.startTime === null) state.startTime = Date.now();
}

function normalizePoint(clientX, clientY, area) {
  const rect = area.getBoundingClientRect();
  const localX = clamp(clientX - rect.left, 0, rect.width);
  const localY = clamp(clientY - rect.top, 0, rect.height);

  return {
    localX,
    localY,
    x: Number((localX / rect.width).toFixed(4)),
    y: Number((localY / rect.height).toFixed(4)),
  };
}

export function captureEvent({ clientX, clientY, type, area, areaName }) {
  ensureStartTime();

  const now = Date.now();
  const isMove = type.includes("move");

  if (isMove && now - state.lastSampleTime < CONFIG.samplingRate) return;

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