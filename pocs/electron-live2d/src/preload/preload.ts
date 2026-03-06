import { contextBridge, ipcRenderer } from "electron";
import type { ServerConfig, ModelConfig, WaifuSetupConfig } from "../shared/types";

// Renderer pulls config via invoke when ready (avoids race with main send timing)
contextBridge.exposeInMainWorld("electronAPI", {
  getServerConfig(): Promise<ServerConfig> {
    return ipcRenderer.invoke("get-server-config");
  },
  getModelConfig(): Promise<ModelConfig> {
    return ipcRenderer.invoke("get-model-config");
  },
  getWaifuSetup(): Promise<WaifuSetupConfig> {
    return ipcRenderer.invoke("get-waifu-setup");
  },
});
