import React, { useEffect, useState } from "react";
import { initLive2D } from "../application/init-live2d.js";
import { createElectronConfig } from "../infrastructure/electron-config.js";
import { createLive2DAdapter } from "../infrastructure/live2d-adapter.js";
import SocketServerStatus from "./components/socketsServerStatus/index.js";
import { openWS } from "../infrastructure/ws-client.js";
import { dispatchExpression } from "../infrastructure/live2d-adapter.js";
import { playLlmResponseVoice } from "../infrastructure/speech-playback.js";
import { SOCKET_URL } from "../domain/constants.js";
import { EXPRESSION_ACTIONS } from "../domain/expression-actions.js";
import AssistantMenu from "./components/shared/menu/index.js";
import { AutomationsMenu } from "./components/shared/menu/assistant_operations.js";

function StatusBar({ text }: { text: string }) {
  return (
    <div
      id="status"
      className="absolute left-0 right-0 top-0 z-[1] px-3 py-1.5 font-mono text-xs bg-[rgba(42,42,42,0.9)]"
    >
      {text}
    </div>
  );
}

function ChatBox({ ws }: { ws: WebSocket | null }) {
  const [input, setInput] = useState("");

  const send = () => {
    const text = input.trim();
    if (!text || ws?.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "voice_input", text }));
    setInput("");
  };

  return (
    <div
      className="fixed bottom-20 left-1/2 z-[1000] flex max-w-[90vw] -translate-x-1/2 items-center gap-2 rounded-2xl bg-black/70 p-3 shadow-lg backdrop-blur-md"
      aria-label="Chat"
    >
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && send()}
        placeholder="Message Neuma…"
        className="min-w-[200px] flex-1 rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 font-mono text-sm text-white placeholder:text-gray-400 focus:border-white/40 focus:outline-none"
      />
      <button
        type="button"
        onClick={send}
        disabled={!input.trim() || ws?.readyState !== WebSocket.OPEN}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/20 text-white transition hover:bg-white/30 disabled:opacity-50 disabled:hover:bg-white/20"
        aria-label="Send"
      >
        <svg
          className="h-5 w-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M14 5l7 7m0 0l-7 7m7-7H3"
          />
        </svg>
      </button>
    </div>
  );
}

function ExpressionButtonsContainer() {
  return (
    <div
      id="test-buttons"
      className="fixed bottom-5 left-1/2 z-[1000] hidden max-h-[200px] max-w-[90vw] -translate-x-1/2 overflow-x-auto overflow-y-auto rounded-2xl bg-black/70 p-4 shadow-lg backdrop-blur-md"
    />
  );
}

export function App() {
  const [status, setStatus] = useState("Loading…");
  const [ws, setWs] = useState<WebSocket | null>(null);

  const sendModelExpresions = (socket: WebSocket) => {
    socket.send(
      JSON.stringify({
        type: "save_model_expressions",
        expressions: EXPRESSION_ACTIONS.map((expression) => expression.name),
      })
    );
  };

  useEffect(() => {
    const config = createElectronConfig();
    const live2d = createLive2DAdapter(setStatus);
    void initLive2D(config, live2d, setStatus);

    const wsUrlPromise =
      window.electronAPI?.getWakeupWsUrl?.() ?? Promise.resolve(SOCKET_URL);
    wsUrlPromise
      .then((url) => openWS(url))
      .then((socket) => {
        setWs(socket);

        sendModelExpresions(socket);
        socket.onmessage = (event) => {
          try {
            const data = typeof event.data === "string" ? JSON.parse(event.data) : null;
            if (data?.type === "llm_response") {
              setStatus(data.text ?? "—");
              if (data.expression) dispatchExpression(data.expression);
              void playLlmResponseVoice().catch(() => {});
            }
            if (data?.type === "voice_input_ack") console.log("Voice ack:", data.text);
          } catch {
            // ignore
          }
        };
        socket.onclose = () => setWs(null);
      })
      .catch(() => setWs(null));
  }, []);

  return (
    <>
      <StatusBar text={status} />
      <ChatBox ws={ws} />
      {/* <ExpressionButtonsContainer /> */}
      <AssistantMenu menu={new AutomationsMenu()} />
      <div className="fixed bottom-5 right-5 z-[1000] px-3 py-2 backdrop-blur-md">
        <SocketServerStatus active={ws?.readyState === WebSocket.OPEN} />
      </div>
    </>
  );
}
