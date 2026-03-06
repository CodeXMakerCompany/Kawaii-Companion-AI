import type {
  RequestInitConfigMessage,
  SetModelAndConfMessage,
  WSServerMessage,
} from "../shared/types.js";

export function openWS(wsUrl: string): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => resolve(ws);
    ws.onerror = () => reject(new Error("WebSocket connection failed"));
  });
}

export function sendRequestInitConfig(ws: WebSocket): void {
  const msg: RequestInitConfigMessage = { type: "request-init-config" };
  ws.send(JSON.stringify(msg));
}

export function parseWSMessage(data: string): WSServerMessage | null {
  try {
    const obj = JSON.parse(data) as { type?: string };
    if (obj.type === "set-model-and-conf") {
      return obj as SetModelAndConfMessage;
    }
  } catch {
    // ignore
  }
  return null;
}

export function onSetModelAndConf(
  ws: WebSocket,
  handler: (msg: SetModelAndConfMessage) => void
): void {
  ws.addEventListener("message", (event) => {
    if (typeof event.data !== "string") return;
    try {
      const obj = JSON.parse(event.data) as { type?: string };
      if (obj.type === "set-model-and-conf") {
        handler(obj as SetModelAndConfMessage);
      }
    } catch {
      // ignore
    }
  });
}
