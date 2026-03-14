import * as http from "http";
import * as path from "path";
import * as fs from "fs";
import { WebSocketServer, WebSocket } from "ws";
import { DEFAULT_PORT } from "../shared/types";

const PORT = parseInt(process.env.PORT ?? String(DEFAULT_PORT), 10) || 12393;
const ROOT_DIR = path.join(__dirname, "..", "..");
const MODELS_DIR = path.join(ROOT_DIR, "models");

function serveStatic(
  req: http.IncomingMessage,
  res: http.ServerResponse,
  baseDir: string
): boolean {
  const url = new URL(req.url ?? "/", "http://localhost");
  const segs = url.pathname
    .replace(/^\//, "")
    .split("/")
    .filter((s) => s && s !== "..");
  const filePath = path.join(baseDir, ...segs);
  if (!filePath.startsWith(path.resolve(baseDir))) {
    res.writeHead(403).end();
    return true;
  }
  try {
    const stat = fs.statSync(filePath);
    const toRead = stat.isDirectory() ? path.join(filePath, "index.html") : filePath;
    const data = fs.readFileSync(toRead);
    const ext = path.extname(toRead);
    const ct =
      ext === ".json"
        ? "application/json"
        : ext === ".png"
          ? "image/png"
          : "application/octet-stream";
    res.writeHead(200, { "Content-Type": ct }).end(data);
  } catch {
    return false;
  }
  return true;
}

const server = http.createServer((req, res) => {
  if (req.url?.startsWith("/models/")) {
    if (serveStatic(req, res, ROOT_DIR)) return;
  }
  res.writeHead(404).end("Not found");
});

const wss = new WebSocketServer({ server, path: "/client-ws" });

wss.on("connection", (ws: WebSocket) => {
  ws.on("message", (raw: Buffer) => {
    try {
      const obj = JSON.parse(raw.toString()) as { type?: string };
      if (obj.type === "request-init-config") {
        ws.send(
          JSON.stringify({
            type: "set-model-and-conf",
            model_info: {
              name: "mao_pro",
              path: `http://localhost:${PORT}/models/mao_pro/runtime/mao_pro.model3.json`,
            },
            conf_name: "default",
            conf_uid: "poc",
            client_uid: "electron-poc",
          })
        );
      }
    } catch {
      // ignore
    }
  });
});

server.listen(PORT, () => {
  console.log(
    `Backend: http://localhost:${PORT} (WebSocket: ws://localhost:${PORT}/client-ws)`
  );
  console.log(
    `Place Live2D model in: ${MODELS_DIR}/mao_pro/runtime/ (e.g. mao_pro.model3.json)`
  );
});
