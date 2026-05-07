export const state = {
  token: "demo_" + Math.random().toString(36).slice(2, 10),
  startTime: null,
  device: "unknown",
  events: [],
  lastSampleTime: 0,

  lastPointByArea: {
    puzzle: null,
    canvas: null,
  },

  drawing: false,
  canvasLocked: false,
  canvasStartTime: null,
  canvasTimerId: null,

  puzzleSolved: false,
  targetX: 0,
  targetY: 0,
  expectedShape: "",
};