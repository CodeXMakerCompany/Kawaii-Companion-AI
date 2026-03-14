import { app, BrowserWindow, ipcMain } from "electron";
import * as path from "path";
import {
  DEFAULT_HOST,
  DEFAULT_PORT,
  ServerConfig,
  ModelConfig,
  WaifuSetupConfig,
} from "../shared/types";
import { WaifuSetup } from "./waifu-setup";

function parseArgv(): { host: string; port: number } {
  let host = DEFAULT_HOST;
  let port = DEFAULT_PORT;
  for (const arg of process.argv.slice(1)) {
    if (arg.startsWith("--host=")) host = arg.slice("--host=".length).trim();
    if (arg.startsWith("--port=")) {
      const n = parseInt(arg.slice("--port=".length), 10);
      if (!Number.isNaN(n)) port = n;
    }
  }
  if (process.env.OPEN_LLM_VTUBER_HOST) host = process.env.OPEN_LLM_VTUBER_HOST;
  if (process.env.OPEN_LLM_VTUBER_PORT) {
    const n = parseInt(process.env.OPEN_LLM_VTUBER_PORT, 10);
    if (!Number.isNaN(n)) port = n;
  }
  return { host, port };
}

function buildServerConfig(host: string, port: number): ServerConfig {
  return {
    host,
    port,
    wsUrl: `ws://${host}:${port}/client-ws`,
  };
}

function buildModelConfig(host: string, port: number): ModelConfig {
  // Use local model instead of remote server
  return {
    modelUrl: "models/SharkGirl/SharkGirl.model3.json",
    kScale: 1,
  };
}

const defaultWaifuSetupConfig: WaifuSetupConfig = {
  hideWindowControls: false, // temporarily show title bar; focus on transparent model background only
  hideBackground: true,
};

let mainWindow: BrowserWindow | null = null;
let cachedServerConfig: ServerConfig;
let cachedModelConfig: ModelConfig;
let waifuSetup: WaifuSetup = new WaifuSetup(defaultWaifuSetupConfig);

function createWindow(): void {
  const { host, port } = parseArgv();
  cachedServerConfig = buildServerConfig(host, port);
  cachedModelConfig = buildModelConfig(host, port);
  waifuSetup = new WaifuSetup(defaultWaifuSetupConfig);

  mainWindow = new BrowserWindow({
    width: 960,
    height: 720,
    ...waifuSetup.getBrowserWindowOptions(),
    webPreferences: {
      preload: path.join(__dirname, "..", "preload", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "..", "..", "public", "index.html"));

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// Wakeup WebSocket URL (for Docker: set WAKEUP_WS_URL=ws://wakeup-server:7769)
const WAKEUP_WS_BASE = process.env.WAKEUP_WS_URL || "ws://localhost:7769";
const WAKEUP_WS_URL_FULL = `${WAKEUP_WS_BASE.replace(/\/$/, "")}/waifu-client-ws`;

// Renderer pulls config when ready (no race with dom-ready / did-finish-load)
ipcMain.handle("get-server-config", (): ServerConfig => cachedServerConfig);
ipcMain.handle("get-model-config", (): ModelConfig => cachedModelConfig);
ipcMain.handle("get-waifu-setup", (): WaifuSetupConfig => waifuSetup.getRendererConfig());
ipcMain.handle("get-wakeup-ws-url", (): string => WAKEUP_WS_URL_FULL);

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
