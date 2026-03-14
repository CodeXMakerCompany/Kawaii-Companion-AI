import type { ModelConfig } from "../shared/types.js";
import type { ModelUrlParts } from "../domain/index.js";
import { EXPRESSION_ACTIONS } from "../domain/expression-actions.js";
import type { IConfigPort, ILive2DPort } from "./ports.js";

const DEFAULT_MODEL: ModelConfig = {
  modelUrl: "models/SharkGirl/SharkGirl.model3.json",
  kScale: 1,
};

function parseModelUrl(modelUrl: string): ModelUrlParts {
  const lastSlash = modelUrl.lastIndexOf("/");
  const baseUrl = lastSlash >= 0 ? modelUrl.slice(0, lastSlash + 1) : "";
  const file = modelUrl.slice(lastSlash + 1);
  const modelName = file.replace(/\.model3\.json$/i, "") || "model";
  return { baseUrl, modelName };
}

function withTimeout<T>(promise: Promise<T>, ms: number, fallback: T): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((resolve) => setTimeout(() => resolve(fallback), ms)),
  ]);
}

export interface InitLive2DResult {
  status: "ok" | "error";
  message: string;
}

/**
 * Use case: initialize Live2D with config from Electron and start the render loop.
 * Updates status via callback and shows expression UI when ready.
 */
export async function initLive2D(
  config: IConfigPort,
  live2d: ILive2DPort,
  setStatus: (text: string) => void
): Promise<InitLive2DResult> {
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

  let container = document.getElementById("test-buttons");
  if (!container) {
    container = document.createElement("div");
    container.id = "test-buttons";
    container.className = "hidden";
    container.setAttribute("aria-hidden", "true");
    document.body.appendChild(container);
  }

  live2d.start(waifuSetup?.hideBackground ?? false, async () => {
    setStatus("Live2D running");
    const modelBasePath = baseUrl.replace(/\/?$/, "/");
    await live2d.loadExpressions(EXPRESSION_ACTIONS, modelBasePath);
    // live2d.createExpressionButtons(container, EXPRESSION_ACTIONS, () => {});
    live2d.showExpressionUI(true);
  });

  return { status: "ok", message: "Live2D running" };
}
