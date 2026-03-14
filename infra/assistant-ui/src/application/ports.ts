import type { ModelConfig, WaifuSetupConfig } from "../shared/types.js";
import type { ExpressionAction } from "../domain/index.js";

/** Port: how the app gets config (implemented by infrastructure) */
export interface IConfigPort {
  getWaifuSetup(): Promise<WaifuSetupConfig | null>;
  getModelConfig(): Promise<ModelConfig>;
}

/** Port: Live2D runtime (implemented by infrastructure). start() calls onReady when initialized then starts the render loop (never returns). */
export interface ILive2DPort {
  setModelConfig(baseUrl: string, modelName: string, kScale: number): void;
  start(hideBackground: boolean, onReady?: () => void | Promise<void>): void;
  loadExpressions(actions: ExpressionAction[], modelBasePath: string): Promise<void>;
  createExpressionButtons(
    container: HTMLElement,
    actions: ExpressionAction[],
    onTrigger: (action: ExpressionAction) => void
  ): void;
  showExpressionUI(show: boolean): void;
}
