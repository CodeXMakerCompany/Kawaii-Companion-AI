import type { ExpressionAction } from "../domain/index.js";
import type { ILive2DPort } from "../application/ports.js";
import { EXPRESSION_ACTIONS } from "../domain/expression-actions.js";
import { MOUTH_LEVEL_EVENT, STOP_TALKING_EVENT } from "./speech-playback.js";

declare global {
  interface Window {
    LAppDelegate?: { getInstance(): { initialize(): boolean; run(): void; _view?: any } };
    LAppLive2DManager?: {
      _instance?: { _models?: { getSize(): number; at(i: number): any } };
    };
    __LAPP_MODEL_CONFIG__?: unknown;
  }
}

export function createLive2DAdapter(setStatus: (text: string) => void): ILive2DPort {
  const loadedExpressions = new Map<string, unknown>();
  const activeToggles = new Map<string, boolean>();

  function getModel(): any {
    const win = window as any;
    try {
      let manager = win.LAppLive2DManager?._instance;
      if (manager?._models?.getSize() > 0) return manager._models.at(0);
      const delegate = win.LAppDelegate?.getInstance();
      if (delegate?._view?._subdelegate) {
        manager = delegate._view._subdelegate.getLive2DManager();
        if (manager?._models?.getSize() > 0) return manager._models.at(0);
      }
    } catch (e) {
      console.error("Error getting model:", e);
    }
    return null;
  }

  function applyTransparentBackground(): void {
    document.body.style.background = "transparent";
    const waitForCanvas = setInterval(() => {
      const canvases = document.querySelectorAll("canvas");
      if (canvases.length > 0) {
        clearInterval(waitForCanvas);
        canvases.forEach((canvas) => {
          (canvas as HTMLCanvasElement).style.setProperty(
            "background",
            "transparent",
            "important"
          );
          (canvas as HTMLCanvasElement).style.setProperty(
            "position",
            "fixed",
            "important"
          );
          (canvas as HTMLCanvasElement).style.setProperty("top", "0", "important");
          (canvas as HTMLCanvasElement).style.setProperty("left", "0", "important");
          (canvas as HTMLCanvasElement).style.setProperty("width", "100vw", "important");
          (canvas as HTMLCanvasElement).style.setProperty("height", "100vh", "important");
          (canvas as HTMLCanvasElement).width = window.innerWidth;
          (canvas as HTMLCanvasElement).height = window.innerHeight;
        });
        window.addEventListener("resize", () => {
          document.querySelectorAll("canvas").forEach((canvas) => {
            (canvas as HTMLCanvasElement).width = window.innerWidth;
            (canvas as HTMLCanvasElement).height = window.innerHeight;
          });
        });
        const gl =
          (canvases[0] as HTMLCanvasElement).getContext("webgl") ||
          (canvases[0] as HTMLCanvasElement).getContext("webgl2");
        if (gl) {
          const origClear = gl.clear.bind(gl);
          const origClearColor = gl.clearColor.bind(gl);
          (gl as any).clear = function (mask: number) {
            origClearColor(0, 0, 0, 0);
            return origClear(mask);
          };
        }
      }
    }, 100);
    const styleEl = document.createElement("style");
    styleEl.textContent = `canvas { background: transparent !important; position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important; }`;
    document.head.appendChild(styleEl);
  }

  const adapter = {
    setModelConfig(baseUrl: string, modelName: string, kScale: number): void {
      (window as any).__LAPP_MODEL_CONFIG__ = {
        baseUrl,
        modelDir: [""],
        modelFileNames: [modelName],
        kScale,
      };
    },

    start(hideBackground: boolean, onReady?: () => void | Promise<void>): void {
      const LAppDelegate = window.LAppDelegate;
      if (!LAppDelegate?.getInstance) {
        setStatus(
          (window as any).Live2DCubismCore != null
            ? "LApp not exposed. Rebuild lapp.min.js with LAppDelegate on window."
            : "Live2D SDK not loaded. Add libs to public/libs/."
        );
        return;
      }
      if (hideBackground) applyTransparentBackground();
      try {
        const delegate = LAppDelegate.getInstance();
        if (!delegate.initialize()) {
          setStatus("Live2D initialize failed");
          return;
        }
        setTimeout(() => {
          void (async () => {
            await onReady?.();
          })();
        }, 1000);
        delegate.run(); // never returns
      } catch (e) {
        setStatus("Live2D error: " + String(e));
      }
    },

    async loadExpressions(
      actions: ExpressionAction[],
      modelBasePath: string
    ): Promise<void> {
      const model = getModel();
      if (!model?.loadExpression) return;
      for (const action of actions) {
        try {
          const url = `${modelBasePath}${action.file}.exp3.json`;
          const response = await fetch(url);
          if (!response.ok) continue;
          const data = await response.arrayBuffer();
          const expression = model.loadExpression(data, data.byteLength, action.file);
          if (expression) loadedExpressions.set(action.file, expression);
        } catch (e) {
          console.warn(`Failed to load ${action.file}:`, e);
        }
      }
    },

    createExpressionButtons(
      container: HTMLElement,
      actions: ExpressionAction[],
      _onTrigger: (action: ExpressionAction) => void
    ): void {
      container.innerHTML = "";
      const trigger = (action: ExpressionAction, button: HTMLButtonElement) => {
        const model = getModel();
        if (!model?._expressionManager) return;
        const expression = loadedExpressions.get(action.file);
        if (!expression) return;
        if (action.toggle) {
          const isActive = activeToggles.get(action.file) ?? false;
          if (isActive) {
            model._expressionManager.stopAllMotions();
            activeToggles.set(action.file, false);
            button.style.opacity = "1";
            button.style.transform = "scale(1)";
          } else {
            model._expressionManager.startMotion(expression, false);
            activeToggles.set(action.file, true);
            button.style.opacity = "0.7";
            button.style.transform = "scale(0.95)";
          }
        } else {
          model._expressionManager.startMotion(expression, false);
          button.style.transform = "scale(0.9)";
          setTimeout(() => {
            button.style.transform = "scale(1)";
          }, 150);
        }
      };
      actions.forEach((action) => {
        const button = document.createElement("button");
        button.className = "action-btn";
        button.innerHTML = `${action.emoji} ${action.name}`;
        button.title = action.name;
        button.style.cssText =
          "margin:5px;padding:10px 15px;font-size:13px;cursor:pointer;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;border-radius:8px;transition:all 0.2s ease;box-shadow:0 2px 5px rgba(0,0,0,0.2);";
        button.addEventListener("click", () => trigger(action, button));
        container.appendChild(button);
      });
    },

    showExpressionUI(show: boolean): void {
      const el = document.getElementById("test-buttons");
      if (el) el.style.display = show ? "block" : "none";
    },

    /** Trigger an expression by display name (e.g. from LLM response). Call from anywhere or dispatch "live2d-expression" with detail.name */
    triggerExpressionByName(name: string): boolean {
      const action = EXPRESSION_ACTIONS.find(
        (a) => a.name.toLowerCase().trim() === (name || "").toLowerCase().trim()
      );
      if (!action) return false;
      const model = getModel();
      if (!model?._expressionManager) return false;
      const expression = loadedExpressions.get(action.file);
      if (!expression) return false;
      if (action.toggle) {
        const isActive = activeToggles.get(action.file) ?? false;
        if (!isActive) {
          model._expressionManager.startMotion(expression, false);
          activeToggles.set(action.file, true);
        }
      } else {
        model._expressionManager.startMotion(expression, false);
      }
      return true;
    },

    /** Stop mouth / all expression motions (e.g. when voice playback ends). */
    stopTalking(): void {
      const model = getModel();
      model?._expressionManager?.stopAllMotions?.();
      activeToggles.set("mouth_open", false);
    },
  };

  window.addEventListener(LIVE2D_EXPRESSION_EVENT, ((e: CustomEvent<{ name?: string }>) => {
    const name = e.detail?.name;
    if (name) adapter.triggerExpressionByName(name);
  }) as EventListener);

  (() => {
    const OPEN_THRESHOLD = 0.12;
    const CLOSE_THRESHOLD = 0.06;
    const MIN_HOLD_MS = 40;
    let mouthOpen = false;
    let lastToggle = 0;

    window.addEventListener(
      MOUTH_LEVEL_EVENT,
      ((e: CustomEvent<{ level?: number }>) => {
        const level = e.detail?.level ?? 0;
        const now = performance.now();
        if (level > OPEN_THRESHOLD && !mouthOpen && now - lastToggle > MIN_HOLD_MS) {
          adapter.triggerExpressionByName("Open Mouth");
          mouthOpen = true;
          lastToggle = now;
        } else if (level <= CLOSE_THRESHOLD && mouthOpen && now - lastToggle > MIN_HOLD_MS) {
          adapter.stopTalking();
          mouthOpen = false;
          lastToggle = now;
        }
      }) as EventListener
    );

    window.addEventListener(STOP_TALKING_EVENT, () => {
      if (mouthOpen) adapter.stopTalking();
      mouthOpen = false;
    });
  })();

  return adapter;
}

/** Fire this event to trigger an expression from anywhere (e.g. when LLM returns expression name). */
export const LIVE2D_EXPRESSION_EVENT = "live2d-expression";

export function dispatchExpression(name: string): void {
  window.dispatchEvent(new CustomEvent(LIVE2D_EXPRESSION_EVENT, { detail: { name } }));
}
