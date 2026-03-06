/// <reference types="./preload.d.ts" />
import type { ModelConfig } from "../shared/types.js";

const statusEl = document.getElementById("status") as HTMLDivElement;

function setStatus(text: string): void {
  if (statusEl) statusEl.textContent = text;
}

function parseModelUrl(modelUrl: string): {
  baseUrl: string;
  modelName: string;
} {
  const lastSlash = modelUrl.lastIndexOf("/");
  const baseUrl = lastSlash >= 0 ? modelUrl.slice(0, lastSlash + 1) : "";
  const file = modelUrl.slice(lastSlash + 1);
  const modelName = file.replace(/\.model3\.json$/i, "") || "model";
  return { baseUrl, modelName };
}

/** Set so lapp.min.js (when it loads) reads this and uses our model paths. */
function setLAppModelConfig(
  baseUrl: string,
  modelName: string,
  kScale: number,
): void {
  const win = window as any;

  // Set config for library to read
  win.__LAPP_MODEL_CONFIG__ = {
    baseUrl,
    modelDir: [""],
    modelFileNames: [modelName],
    kScale,
  };

  console.log("Model config set:", {
    baseUrl,
    modelName,
    kScale,
  });
}

function startLive2D(hideBackground: boolean): void {
  const win = window as unknown as {
    Live2DCubismCore?: unknown;
    LAppDelegate?: { getInstance(): { initialize(): boolean; run(): void } };
    LAppLive2DManager?: any;
    LAppDefine?: any;
  };

  const LAppDelegate = win.LAppDelegate;
  if (!LAppDelegate?.getInstance) {
    if (win.Live2DCubismCore != null) {
      setStatus(
        "LApp not exposed. In Demo src/main.ts add: (window as any).LAppDelegate = LAppDelegate; (window as any).LAppDefine = LAppDefine; then rebuild and copy new lapp.min.js",
      );
    } else {
      setStatus(
        "Live2D SDK not loaded. Add live2dcubismcore.min.js and lapp.min.js to public/libs/ (see SETUP_LIVE2D.md).",
      );
    }
    return;
  }

  try {
    const delegate = LAppDelegate.getInstance();
    if (delegate.initialize()) {
      setStatus("Live2D running");

      // Show test buttons after Live2D is initialized
      setTimeout(() => {
        const testButtons = document.getElementById("test-buttons");
        if (testButtons) testButtons.style.display = "block";
        setupTestButtons();
      }, 1000);

      delegate.run(); // never returns (render loop)
    } else {
      setStatus("Live2D initialize failed");
    }
  } catch (e) {
    setStatus("Live2D error: " + String(e));
  }
}

function setupTestButtons(): void {
  const win = window as any;

  // Action dictionary mapping expression files to their display names and emojis
  const actionDictionary = [
    // Custom expressions
    { file: "mouth_open", name: "Open Mouth", emoji: "👄", toggle: true },
    { file: "tongue_out", name: "Tongue Out", emoji: "👅", toggle: true },

    // Built-in expressions (mapped from parameter names in cdi3.json)
    { file: "expression1", name: "Dots", emoji: "⚫", toggle: false }, // 点点
    { file: "expression2", name: "Microphone", emoji: "🎤", toggle: false }, // 麦克
    { file: "expression3", name: "Heart Hands", emoji: "💝", toggle: false }, // 笔芯
    { file: "expression4", name: "Scratch", emoji: "✋", toggle: false }, // 抓抓
    { file: "expression5", name: "Peace Sign", emoji: "✌️", toggle: false }, // 比耶
    { file: "expression6", name: "Crying", emoji: "😭", toggle: false }, // 哭哭
    { file: "expression7", name: "Love", emoji: "💕", toggle: false }, // 爱心
    { file: "expression8", name: "Star Eyes", emoji: "🤩", toggle: false }, // 星星眼
    { file: "expression9", name: "Speechless", emoji: "😑", toggle: false }, // 无语
    { file: "expression10", name: "Sweat", emoji: "😅", toggle: false }, // 汗
    { file: "expression11", name: "Angry", emoji: "😠", toggle: false }, // 生气
    { file: "expression12", name: "Question", emoji: "❓", toggle: false }, // 疑问
    { file: "expression13", name: "Surprised", emoji: "😲", toggle: false }, // 惊讶
    { file: "expression14", name: "Super Happy", emoji: "😄", toggle: false }, // 超开心
    { file: "expression15", name: "Band-Aid", emoji: "🩹", toggle: false }, // 创可贴
    { file: "expression16", name: "Lollipop", emoji: "🍭", toggle: false }, // 棒棒糖
    { file: "expression17", name: "Shark Hat", emoji: "🦈", toggle: false }, // 头顶鲨鱼
    { file: "expression18", name: "Jacket", emoji: "🧥", toggle: false }, // 外套
    { file: "expression19", name: "Socks", emoji: "🧦", toggle: false }, // 堆堆袜
    { file: "expression20", name: "Tail", emoji: "🐟", toggle: false }, // 尾巴
    { file: "expression21", name: "Right Chirp", emoji: "🎵", toggle: false }, // 右啾啾
    { file: "expression22", name: "Left Chirp", emoji: "🎶", toggle: false }, // 左啾啾
    { file: "expression23", name: "Tail Alt", emoji: "🐠", toggle: false }, // 尾巴
  ];

  // Track loaded expressions
  const loadedExpressions = new Map<string, any>();
  const activeToggles = new Map<string, boolean>();

  // Helper to get the model
  function getModel() {
    try {
      let manager = win.LAppLive2DManager?._instance;
      if (manager && manager._models && manager._models.getSize() > 0) {
        return manager._models.at(0);
      }

      const delegate = win.LAppDelegate?.getInstance();
      if (delegate && delegate._view && delegate._view._subdelegate) {
        manager = delegate._view._subdelegate.getLive2DManager();
        if (manager && manager._models && manager._models.getSize() > 0) {
          return manager._models.at(0);
        }
      }
    } catch (e) {
      console.error("Error getting model:", e);
    }
    return null;
  }

  // Load all custom expressions
  async function loadCustomExpressions() {
    const model = getModel();
    if (!model) {
      console.warn("Model not available for loading expressions");
      return;
    }

    for (const action of actionDictionary) {
      try {
        const response = await fetch(
          `models/SharkGirl/${action.file}.exp3.json`,
        );
        if (!response.ok) continue;

        const data = await response.arrayBuffer();
        if (model.loadExpression) {
          const expression = model.loadExpression(
            data,
            data.byteLength,
            action.file,
          );
          if (expression) {
            loadedExpressions.set(action.file, expression);
            console.log(`Loaded expression: ${action.name}`);
          }
        }
      } catch (e) {
        console.warn(`Failed to load ${action.file}:`, e);
      }
    }

    console.log(`Loaded ${loadedExpressions.size} expressions`);
  }

  // Trigger an action
  function triggerAction(
    action: (typeof actionDictionary)[0],
    button: HTMLButtonElement,
  ) {
    const model = getModel();
    if (!model || !model._expressionManager) {
      console.warn("Model or expression manager not available");
      return;
    }

    const expression = loadedExpressions.get(action.file);
    if (!expression) {
      console.warn(`Expression ${action.file} not loaded`);
      return;
    }

    if (action.toggle) {
      // Toggle behavior
      const isActive = activeToggles.get(action.file) || false;

      if (isActive) {
        // Deactivate
        model._expressionManager.stopAllMotions();
        activeToggles.set(action.file, false);
        button.style.opacity = "1";
        button.style.transform = "scale(1)";
        console.log(`Deactivated: ${action.name}`);
      } else {
        // Activate
        model._expressionManager.startMotion(expression, false);
        activeToggles.set(action.file, true);
        button.style.opacity = "0.7";
        button.style.transform = "scale(0.95)";
        console.log(`Activated: ${action.name}`);
      }
    } else {
      // One-shot behavior
      model._expressionManager.startMotion(expression, false);
      console.log(`Triggered: ${action.name}`);

      // Visual feedback
      button.style.transform = "scale(0.9)";
      setTimeout(() => {
        button.style.transform = "scale(1)";
      }, 150);
    }
  }

  // Create dynamic buttons
  function createActionButtons() {
    const container = document.getElementById("test-buttons");
    if (!container) return;

    // Clear existing buttons
    container.innerHTML = "";

    // Create buttons for each action
    actionDictionary.forEach((action) => {
      const button = document.createElement("button");
      button.className = "action-btn";
      button.innerHTML = `${action.emoji} ${action.name}`;
      button.title = action.name;

      button.style.cssText = `
        margin: 5px;
        padding: 10px 15px;
        font-size: 13px;
        cursor: pointer;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        transition: all 0.2s ease;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
      `;

      button.addEventListener("mouseenter", () => {
        button.style.boxShadow = "0 4px 8px rgba(0,0,0,0.3)";
      });

      button.addEventListener("mouseleave", () => {
        button.style.boxShadow = "0 2px 5px rgba(0,0,0,0.2)";
      });

      button.addEventListener("click", () => triggerAction(action, button));

      container.appendChild(button);
    });

    console.log(`Created ${actionDictionary.length} action buttons`);
  }

  // Initialize
  setTimeout(async () => {
    await loadCustomExpressions();
    createActionButtons();
  }, 1500);

  console.log("Action system initialized");
}

function withTimeout<T>(
  promise: Promise<T>,
  ms: number,
  fallback: T,
): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((resolve) => setTimeout(() => resolve(fallback), ms)),
  ]);
}

async function run(): Promise<void> {
  setStatus("Loading model…");
  if (!window.electronAPI) {
    setStatus("No electron API");
    return;
  }

  // Apply waifu setup (e.g. transparent background)
  const waifuSetup = await window.electronAPI.getWaifuSetup().catch(() => null);

  // Style any canvas LApp will create so it doesn’t show an opaque fill

  const configTimeoutMs = 3000;
  const defaultModel: ModelConfig = {
    modelUrl: "models/SharkGirl/SharkGirl.model3.json",
    kScale: 1,
  };

  const modelConfig = await withTimeout(
    window.electronAPI.getModelConfig(),
    configTimeoutMs,
    defaultModel,
  );

  // Resolve model URL relative to current page (public/ when loaded via loadFile)
  const modelUrl =
    modelConfig.modelUrl.startsWith("http") ||
    modelConfig.modelUrl.startsWith("file")
      ? modelConfig.modelUrl
      : new URL(modelConfig.modelUrl, window.location.href).href;
  const { baseUrl: bUrl, modelName: mName } = parseModelUrl(modelUrl);

  // Log the model being used
  console.log("=== Live2D Model Configuration ===");
  console.log("Model URL:", modelUrl);
  console.log("Base URL:", bUrl);
  console.log("Model Name:", mName);
  console.log("Scale (kScale):", modelConfig.kScale ?? 1);
  console.log("Hide Background:", waifuSetup?.hideBackground ?? false);
  console.log("==================================");

  setLAppModelConfig(bUrl, mName, modelConfig.kScale ?? 1);

  // Apply transparent background styling if needed
  // The automatic window.load handler will be blocked by our patch
  console.log("Model config set, now initializing Live2D...");

  // Apply transparent background styling if needed
  if (waifuSetup?.hideBackground) {
    document.body.style.background = "transparent";

    // Wait for canvas to be created and style it
    const waitForCanvas = setInterval(() => {
      const canvases = document.querySelectorAll("canvas");
      console.log("Canvas check - found", canvases.length, "canvas elements");

      if (canvases.length > 0) {
        clearInterval(waitForCanvas);

        // Warn if multiple canvases but don't remove them
        if (canvases.length > 1) {
          console.warn("Multiple canvas elements detected:", canvases.length);
        }

        // Style all canvases
        canvases.forEach((canvas, index) => {
          console.log(`Styling canvas ${index + 1}/${canvases.length}`);
          canvas.style.setProperty("background", "transparent", "important");
          canvas.style.setProperty("position", "fixed", "important");
          canvas.style.setProperty("top", "0", "important");
          canvas.style.setProperty("left", "0", "important");
          canvas.style.setProperty("width", "100vw", "important");
          canvas.style.setProperty("height", "100vh", "important");

          // Resize canvas internal dimensions to match window
          canvas.width = window.innerWidth;
          canvas.height = window.innerHeight;
        });

        console.log(
          "Canvas dimensions:",
          canvases[0].width,
          "x",
          canvases[0].height,
        );

        // Handle window resize
        window.addEventListener("resize", () => {
          const allCanvases = document.querySelectorAll("canvas");
          allCanvases.forEach((canvas) => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
          });
        });

        // Patch WebGL for transparency
        const gl =
          canvases[0].getContext("webgl") || canvases[0].getContext("webgl2");
        if (gl) {
          console.log("Patching WebGL context for transparency");
          const origClear = gl.clear.bind(gl);
          const origClearColor = gl.clearColor.bind(gl);

          // Force transparent clear color before every clear
          gl.clear = function (mask: number) {
            origClearColor(0, 0, 0, 0);
            return origClear(mask);
          };

          console.log("WebGL context patched successfully");
        }
      }
    }, 100);

    // Also inject CSS for any future canvas elements
    const styleEl = document.createElement("style");
    styleEl.textContent = `
      canvas {
        background: transparent !important;
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
      }
    `;
    document.head.appendChild(styleEl);
  }

  setStatus("Loading LApp…");
  // lapp.min.js is already loaded by index.html; loading it again causes "Identifier 'dt' has already been declared"
  startLive2D(waifuSetup?.hideBackground ?? false);
}

run();
