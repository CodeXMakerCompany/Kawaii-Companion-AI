import type { ServerConfig, ModelConfig, WaifuSetupConfig } from "../shared/types";

export interface ElectronAPI {
  getServerConfig(): Promise<ServerConfig>;
  getModelConfig(): Promise<ModelConfig>;
  getWaifuSetup(): Promise<WaifuSetupConfig>;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

export {};
