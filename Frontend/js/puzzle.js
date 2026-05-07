import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { dom } from "./dom.js";
import { randomInt } from "./utils.js";
import { captureEvent } from "./capture.js";
import { setStatus } from "./ui.js";

// ─── Metrics ────────────────────────────────────────────────────────────────

function getPuzzleMetrics() {
  const containerWidth  = dom.puzzleContainer.offsetWidth;
  const containerHeight = dom.puzzleContainer.offsetHeight;
  const pieceSize       = CONFIG.pieceSize;
  const maxMove         = containerWidth - pieceSize;
  return { containerWidth, containerHeight, pieceSize, maxMove };
}

// ─── UI hint ────────────────────────────────────────────────────────────────

function updatePuzzleHint() {
  if (!dom.puzzleHint) return;
  dom.puzzleHint.textContent = state.puzzleSolved ? "Đã khớp ✓" : "Chưa hoàn thành";
}

// ─── Image ──────────────────────────────────────────────────────────────────

function buildImageUrl() {
  return `https://picsum.photos/640/360?grayscale&t=${Date.now()}&r=${Math.random()}`;
}

function applyImage(url) {
  const { containerWidth, containerHeight } = getPuzzleMetrics();

  dom.bgImage.style.backgroundImage  = `url("${url}")`;
  dom.bgImage.style.backgroundSize   = `${containerWidth}px ${containerHeight}px`;
  dom.bgImage.style.backgroundRepeat = "no-repeat";

  dom.piece.style.backgroundImage  = `url("${url}")`;
  dom.piece.style.backgroundSize   = `${containerWidth}px ${containerHeight}px`;
  dom.piece.style.backgroundRepeat = "no-repeat";
}

// ─── Render ─────────────────────────────────────────────────────────────────

export function renderPuzzle() {
  const { pieceSize } = getPuzzleMetrics();

  dom.hole.style.left   = state.targetX + "px";
  dom.hole.style.top    = state.targetY + "px";
  dom.hole.style.width  = pieceSize + "px";
  dom.hole.style.height = pieceSize + "px";

  dom.piece.style.left   = "0px";
  dom.piece.style.top    = state.targetY + "px";
  dom.piece.style.width  = pieceSize + "px";
  dom.piece.style.height = pieceSize + "px";
  dom.piece.style.backgroundPosition = `-${state.targetX}px -${state.targetY}px`;

  updatePuzzleHint();
}

// ─── Randomise target (offline fallback) ────────────────────────────────────

export function randomizeTargetPosition() {
  const { containerWidth, containerHeight, pieceSize, maxMove } = getPuzzleMetrics();

  const safeMinX = Math.max(80, Math.floor(containerWidth * 0.35));
  const safeMaxX = Math.min(maxMove - 10, containerWidth - pieceSize - 10);
  const safeMinY = 10;
  const safeMaxY = Math.max(10, containerHeight - pieceSize - 10);

  state.targetX = randomInt(safeMinX, safeMaxX);
  state.targetY = randomInt(safeMinY, safeMaxY);
}

// ─── Slider → piece X ───────────────────────────────────────────────────────

export function movePieceBySlider(percent) {
  const { maxMove } = getPuzzleMetrics();
  const currentX = Math.round((percent / 100) * maxMove);
  dom.piece.style.left = currentX + "px";
  return currentX;
}

// ─── Snap check ─────────────────────────────────────────────────────────────

export function snapCheck() {
  const currentX = parseFloat(dom.piece.style.left || "0");
  const diff     = Math.abs(currentX - state.targetX);

  if (diff <= CONFIG.snapThreshold) {
    dom.piece.style.transition = "left 0.15s ease";
    dom.piece.style.left = state.targetX + "px";
    setTimeout(() => { dom.piece.style.transition = ""; }, 200);

    // Đồng bộ slider
    const { maxMove } = getPuzzleMetrics();
    dom.slider.value = String(Math.round((state.targetX / maxMove) * 100));

    state.puzzleSolved = true;
    setStatus("Puzzle khớp ✓ Bạn có thể tiếp tục vẽ.", "green");
  } else {
    state.puzzleSolved = false;
    setStatus("Puzzle chưa khớp.", "red");
  }

  updatePuzzleHint();
}

// ─── Reset ──────────────────────────────────────────────────────────────────

export function resetPuzzle(targetX, targetY) {
  dom.slider.value = "0";
  state.puzzleSolved = false;
  state.lastPointByArea.puzzle = null;

  // Đổi ảnh mới mỗi lần reset/load
  applyImage(buildImageUrl());

  // Vị trí lỗ — từ backend hoặc random nếu offline
  if (targetX != null && targetY != null) {
    state.targetX = targetX;
    state.targetY = targetY;
  } else {
    randomizeTargetPosition();
  }

  renderPuzzle();
}

// ─── Events ─────────────────────────────────────────────────────────────────

export function initPuzzleEvents() {

  dom.slider.addEventListener("mousedown", () => {
    state.device = "mouse";
    const rect = dom.piece.getBoundingClientRect();
    captureEvent({
      clientX: rect.left + rect.width / 2,
      clientY: rect.top  + rect.height / 2,
      type: "mousedown", area: dom.puzzleContainer, areaName: "puzzle",
    });
  });

  dom.slider.addEventListener("input", () => {
    state.device = "mouse";
    const currentX = movePieceBySlider(Number(dom.slider.value));
    const rect = dom.puzzleContainer.getBoundingClientRect();
    captureEvent({
      clientX: rect.left + currentX + CONFIG.pieceSize / 2,
      clientY: rect.top  + state.targetY + CONFIG.pieceSize / 2,
      type: "mousemove", area: dom.puzzleContainer, areaName: "puzzle",
    });
    state.puzzleSolved = false;
    updatePuzzleHint();
  });

  dom.slider.addEventListener("mouseup", () => {
    const rect = dom.piece.getBoundingClientRect();
    captureEvent({
      clientX: rect.left + rect.width / 2,
      clientY: rect.top  + rect.height / 2,
      type: "mouseup", area: dom.puzzleContainer, areaName: "puzzle",
    });
    snapCheck();
  });

  dom.slider.addEventListener("touchstart", () => {
    state.device = "touch";
    const rect = dom.piece.getBoundingClientRect();
    captureEvent({
      clientX: rect.left + rect.width / 2,
      clientY: rect.top  + rect.height / 2,
      type: "touchstart", area: dom.puzzleContainer, areaName: "puzzle",
    });
  }, { passive: true });

  dom.slider.addEventListener("touchmove", () => {
    state.device = "touch";
    const currentX = movePieceBySlider(Number(dom.slider.value));
    const rect = dom.puzzleContainer.getBoundingClientRect();
    captureEvent({
      clientX: rect.left + currentX + CONFIG.pieceSize / 2,
      clientY: rect.top  + state.targetY + CONFIG.pieceSize / 2,
      type: "touchmove", area: dom.puzzleContainer, areaName: "puzzle",
    });
    state.puzzleSolved = false;
    updatePuzzleHint();
  }, { passive: true });

  dom.slider.addEventListener("touchend", () => {
    const rect = dom.piece.getBoundingClientRect();
    captureEvent({
      clientX: rect.left + rect.width / 2,
      clientY: rect.top  + rect.height / 2,
      type: "touchend", area: dom.puzzleContainer, areaName: "puzzle",
    });
    snapCheck();
  });
}