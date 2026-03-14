import type { BrowserWindowConstructorOptions } from "electron";
import type { WaifuSetupConfig } from "../shared/types";

/**
 * Delegates setup use cases to achieve the desired initial waifu look.
 * Use cases:
 * - hideWindowControls: frameless window (no title bar)
 * - hideBackground: transparent window + transparent page background
 */
export class WaifuSetup {
  constructor(private readonly config: WaifuSetupConfig) {}

  /** BrowserWindow options to apply when creating the main window */
  getBrowserWindowOptions(): Partial<BrowserWindowConstructorOptions> {
    const opts: Partial<BrowserWindowConstructorOptions> = {};
    if (this.config.hideWindowControls) {
      opts.frame = false;
    }
    if (this.config.hideBackground) {
      opts.transparent = true;
    }
    return opts;
  }

  /** Config to send to renderer (e.g. for transparent body when hideBackground) */
  getRendererConfig(): WaifuSetupConfig {
    return { ...this.config };
  }
}
