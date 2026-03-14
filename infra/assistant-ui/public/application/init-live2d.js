import { EXPRESSION_ACTIONS } from "../domain/expression-actions.js";
const DEFAULT_MODEL = {
  modelUrl: "models/SharkGirl/SharkGirl.model3.json",
  kScale: 1,
};
function parseModelUrl(modelUrl) {
  const lastSlash = modelUrl.lastIndexOf("/");
  const baseUrl = lastSlash >= 0 ? modelUrl.slice(0, lastSlash + 1) : "";
  const file = modelUrl.slice(lastSlash + 1);
  const modelName = file.replace(/\.model3\.json$/i, "") || "model";
  return { baseUrl, modelName };
}
function withTimeout(promise, ms, fallback) {
  return Promise.race([
    promise,
    new Promise((resolve) => setTimeout(() => resolve(fallback), ms)),
  ]);
}
/**
 * Use case: initialize Live2D with config from Electron and start the render loop.
 * Updates status via callback and shows expression UI when ready.
 */
export async function initLive2D(config, live2d, setStatus) {
  setStatus("Loading model…");
  const waifuSetup = await config.getWaifuSetup().catch(() => null);
  const modelConfig = await withTimeout(config.getModelConfig(), 3000, DEFAULT_MODEL);
  const modelUrl =
    modelConfig.modelUrl.startsWith("http") || modelConfig.modelUrl.startsWith("file")
      ? modelConfig.modelUrl
      : new URL(modelConfig.modelUrl, window.location.href).href;
  const { baseUrl, modelName } = parseModelUrl(modelUrl);
  const kScale = modelConfig.kScale ?? 1;
  live2d.setModelConfig(baseUrl, modelName, kScale);
  setStatus("Loading LApp…");
  const container = document.getElementById("test-buttons");
  if (!container) {
    return { status: "error", message: "Missing #test-buttons container" };
  }
  live2d.start(waifuSetup?.hideBackground ?? false, async () => {
    setStatus("Live2D running");
    const modelBasePath = baseUrl.replace(/\/?$/, "/");
    await live2d.loadExpressions(EXPRESSION_ACTIONS, modelBasePath);
    live2d.createExpressionButtons(container, EXPRESSION_ACTIONS, () => {});
    live2d.showExpressionUI(true);
  });
  return { status: "ok", message: "Live2D running" };
}
