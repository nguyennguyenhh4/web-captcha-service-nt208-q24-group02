import { dom } from "./dom.js";

export function setStatus(message, color = "black") {
  dom.status.innerText = message;
  dom.status.style.color = color;
}