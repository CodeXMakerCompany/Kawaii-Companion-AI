/** Minimal declarations for Live2D Cubism Web SDK globals used by the renderer. */

interface Live2DCubismCore {
  default: unknown;
}

interface LAppDefine {
  ResourcesPath: string;
  ModelDir: string[];
  ModelFileNames: string[];
  CurrentModelIndex: number;
  CurrentKScale: number;
  CanvasScale: number;
}

interface LAppDelegate {
  getInstance(): LAppDelegate;
  initialize(): boolean;
  run(): void;
  release(): void;
}

interface LAppLive2DManager {
  getInstance(): LAppLive2DManager;
}

declare const Live2DCubismCore: Live2DCubismCore;
declare const LAppDelegate: { getInstance(): LAppDelegate };
declare const LAppDefine: LAppDefine;
declare const LAppLive2DManager: { getInstance(): LAppLive2DManager };
