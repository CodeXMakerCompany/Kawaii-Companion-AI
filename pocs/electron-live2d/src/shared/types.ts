/** Single source of truth for default host and port */
export const DEFAULT_HOST = "localhost";
export const DEFAULT_PORT = 12393;

export interface ServerConfig {
  host: string;
  port: number;
  wsUrl: string;
}

export interface ModelConfig {
  modelUrl: string;
  kScale?: number;
}

/** Waifu window/screen setup use cases (main + renderer) */
export interface WaifuSetupConfig {
  /** Hide native window controls (title bar, traffic lights) → frameless window */
  hideWindowControls: boolean;
  /** Transparent background so only the model is visible */
  hideBackground: boolean;
}

/** WebSocket: client -> server */
export interface RequestInitConfigMessage {
  type: "request-init-config";
}

/** WebSocket: server -> client */
export interface SetModelAndConfMessage {
  type: "set-model-and-conf";
  model_info?: { name?: string; path?: string };
  conf_name?: string;
  conf_uid?: string;
  client_uid?: string;
}

export type WSClientMessage = RequestInitConfigMessage;
export type WSServerMessage = SetModelAndConfMessage;
