import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { dom } from "./dom.js";
import { randomInt } from "./utils.js";
import { captureEvent } from "./capture.js";
import { setStatus } from "./ui.js";

function getPuzzleMetrics() {
  const containerWidth = dom.puzzleContainer.offsetWidth;
  const containerHeight = dom.puzzleContainer.offsetHeight;
  const maxMove = containerWidth - CONFIG.pieceSize;

  return {
    containerWidth,
    containerHeight,
    maxMove,
  };
}

function updatePuzzleHint() {
  if (!dom.puzzleHint) return;
  dom.puzzleHint.textContent = state.puzzleSolved ? "Đã khớp" : "Chưa hoàn thành";
}

export function randomizeTargetPosition() {
  const { containerWidth, containerHeight, maxMove } = getPuzzleMetrics();

  const safeMinX = Math.max(80, Math.floor(containerWidth * 0.35));
  const safeMaxX = Math.min(maxMove - 10, containerWidth - CONFIG.pieceSize - 10);

  const safeMinY = 10;
  const safeMaxY = Math.max(10, containerHeight - CONFIG.pieceSize - 10);

  state.targetX = randomInt(safeMinX, safeMaxX);
  state.targetY = randomInt(safeMinY, safeMaxY);
}

export function renderPuzzle() {
  dom.hole.style.left = state.targetX + "px";
  dom.hole.style.top = state.targetY + "px";

  dom.piece.style.left = "0px";
  dom.piece.style.top = state.targetY + "px";
  dom.piece.style.backgroundPosition = `-${state.targetX}px -${state.targetY}px`;

  updatePuzzleHint();
}

export function movePieceBySlider(percent) {
  const { maxMove } = getPuzzleMetrics();
  const currentX = (percent / 100) * maxMove;
  dom.piece.style.left = currentX + "px";
  return currentX;
}

export function snapCheck() {
  const currentX = parseFloat(dom.piece.style.left || "0");
  const diff = Math.abs(currentX - state.targetX);

  if (diff <= CONFIG.snapThreshold) {
    dom.piece.style.left = state.targetX + "px";
    state.puzzleSolved = true;
    setStatus("Puzzle khớp. Bạn có thể tiếp tục vẽ.", "green");
  } else {
    state.puzzleSolved = false;
    setStatus("Puzzle chưa khớp.", "red");
  }

  updatePuzzleHint();
}

export function resetPuzzle() {
  dom.slider.value = "0";
  state.puzzleSolved = false;
  state.lastPointByArea.puzzle = null;
  
  const newImageUrl = `https://picsum.photos/640/360?grayscale&t=${Date.now()}&rand=${Math.random()}`;
  dom.bgImage.style.backgroundImage = `url("${newImageUrl}")`;
  dom.piece.style.backgroundImage = `url("${newImageUrl}")`;
  
  randomizeTargetPosition();
  renderPuzzle();
}

export function initPuzzleEvents() {
  dom.slider.addEventListener("mousedown", () => {
    state.device = "mouse";

    const rect = dom.piece.getBoundingClientRect();
    captureEvent({
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
      type: "mousedown",
      area: dom.puzzleContainer,
      areaName: "puzzle",
    });
  });

  dom.slider.addEventListener("input", () => {
    state.device = "mouse";

    const currentX = movePieceBySlider(Number(dom.slider.value));
    const rect = dom.puzzleContainer.getBoundingClientRect();

    captureEvent({
      clientX: rect.left + currentX + CONFIG.pieceSize / 2,
      clientY: rect.top + state.targetY + CONFIG.pieceSize / 2,
      type: "mousemove",
      area: dom.puzzleContainer,
      areaName: "puzzle",
    });

    state.puzzleSolved = false;
    updatePuzzleHint();
  });

  dom.slider.addEventListener("mouseup", () => {
    const rect = dom.piece.getBoundingClientRect();

    captureEvent({
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
      type: "mouseup",
      area: dom.puzzleContainer,
      areaName: "puzzle",
    });

    snapCheck();
  });

  dom.slider.addEventListener(
    "touchstart",
    () => {
      state.device = "touch";

      const rect = dom.piece.getBoundingClientRect();
      captureEvent({
        clientX: rect.left + rect.width / 2,
        clientY: rect.top + rect.height / 2,
        type: "touchstart",
        area: dom.puzzleContainer,
        areaName: "puzzle",
      });
    },
    { passive: true }
  );

  dom.slider.addEventListener(
    "touchmove",
    () => {
      state.device = "touch";

      const currentX = movePieceBySlider(Number(dom.slider.value));
      const rect = dom.puzzleContainer.getBoundingClientRect();

      captureEvent({
        clientX: rect.left + currentX + CONFIG.pieceSize / 2,
        clientY: rect.top + state.targetY + CONFIG.pieceSize / 2,
        type: "touchmove",
        area: dom.puzzleContainer,
        areaName: "puzzle",
      });

      state.puzzleSolved = false;
      updatePuzzleHint();
    },
    { passive: true }
  );

  dom.slider.addEventListener("touchend", () => {
    const rect = dom.piece.getBoundingClientRect();

    captureEvent({
      clientX: rect.left + rect.width / 2,
      clientY: rect.top + rect.height / 2,
      type: "touchend",
      area: dom.puzzleContainer,
      areaName: "puzzle",
    });

    snapCheck();
  });
}