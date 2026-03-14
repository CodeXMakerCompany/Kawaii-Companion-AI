/// <reference types="../renderer/preload.d.ts" />
import type { IConfigPort } from "../application/ports.js";
import type { ModelConfig, WaifuSetupConfig } from "../shared/types.js";

/** Infrastructure: config from Electron main process (renderer) */
export function createElectronConfig(): IConfigPort {
  return {
    async getWaifuSetup(): Promise<WaifuSetupConfig | null> {
      if (!window.electronAPI) return null;
      return window.electronAPI.getWaifuSetup().catch(() => null);
    },
    async getModelConfig(): Promise<ModelConfig> {
      if (!window.electronAPI) {
        return { modelUrl: "models/SharkGirl/SharkGirl.model3.json", kScale: 1 };
      }
      return window.electronAPI.getModelConfig();
    },
  };
}
