import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { setStatus } from "./ui.js";

export async function submitCaptcha() {
  const payload = {
    token: state.token,
    startTime: state.startTime,
    device: state.device,
    expectedShape: state.expectedShape,
    events: state.events,
  };

  console.log("PAYLOAD:", payload);

  if (!state.puzzleSolved) {
    setStatus("Puzzle chưa khớp.", "red");
    return;
  }

  if (payload.events.length < 6) {
    setStatus("Dữ liệu hành vi quá ít.", "red");
    return;
  }

  try {
    const res = await fetch(CONFIG.verifyUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    setStatus("Gửi thành công: " + JSON.stringify(data), "green");
  } catch (err) {
    console.log(payload);
    setStatus("Không gửi được backend, nhưng payload đã sẵn sàng.", "orange");
  }
}