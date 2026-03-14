export function createLive2DAdapter(setStatus) {
  const loadedExpressions = new Map();
  const activeToggles = new Map();
  function getModel() {
    const win = window;
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
  function applyTransparentBackground() {
    document.body.style.background = "transparent";
    const waitForCanvas = setInterval(() => {
      const canvases = document.querySelectorAll("canvas");
      if (canvases.length > 0) {
        clearInterval(waitForCanvas);
        canvases.forEach((canvas) => {
          canvas.style.setProperty("background", "transparent", "important");
          canvas.style.setProperty("position", "fixed", "important");
          canvas.style.setProperty("top", "0", "important");
          canvas.style.setProperty("left", "0", "important");
          canvas.style.setProperty("width", "100vw", "important");
          canvas.style.setProperty("height", "100vh", "important");
          canvas.width = window.innerWidth;
          canvas.height = window.innerHeight;
        });
        window.addEventListener("resize", () => {
          document.querySelectorAll("canvas").forEach((canvas) => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
          });
        });
        const gl = canvases[0].getContext("webgl") || canvases[0].getContext("webgl2");
        if (gl) {
          const origClear = gl.clear.bind(gl);
          const origClearColor = gl.clearColor.bind(gl);
          gl.clear = function (mask) {
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
  return {
    setModelConfig(baseUrl, modelName, kScale) {
      window.__LAPP_MODEL_CONFIG__ = {
        baseUrl,
        modelDir: [""],
        modelFileNames: [modelName],
        kScale,
      };
    },
    start(hideBackground, onReady) {
      const LAppDelegate = window.LAppDelegate;
      if (!LAppDelegate?.getInstance) {
        setStatus(
          window.Live2DCubismCore != null
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
    async loadExpressions(actions, modelBasePath) {
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
    createExpressionButtons(container, actions, _onTrigger) {
      container.innerHTML = "";
      const trigger = (action, button) => {
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
    showExpressionUI(show) {
      const el = document.getElementById("test-buttons");
      if (el) el.style.display = show ? "block" : "none";
    },
  };
}
