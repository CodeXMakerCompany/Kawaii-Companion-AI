/** Infrastructure: config from Electron main process (renderer) */
export function createElectronConfig() {
  return {
    async getWaifuSetup() {
      if (!window.electronAPI) return null;
      return window.electronAPI.getWaifuSetup().catch(() => null);
    },
    async getModelConfig() {
      if (!window.electronAPI) {
        return { modelUrl: "models/SharkGirl/SharkGirl.model3.json", kScale: 1 };
      }
      return window.electronAPI.getModelConfig();
    },
  };
}
