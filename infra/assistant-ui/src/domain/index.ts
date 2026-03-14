/**
 * Domain layer: types, value objects, and re-exports from shared.
 * No framework or I/O here.
 */

export type {
  ServerConfig,
  ModelConfig,
  WaifuSetupConfig,
  WSClientMessage,
  WSServerMessage,
} from "../shared/types.js";
export { DEFAULT_HOST, DEFAULT_PORT } from "../shared/types.js";

/** Single expression action the user can trigger (toggle or one-shot) */
export interface ExpressionAction {
  file: string;
  name: string;
  emoji: string;
  toggle: boolean;
}

/** Parsed model URL parts for LApp config */
export interface ModelUrlParts {
  baseUrl: string;
  modelName: string;
}
