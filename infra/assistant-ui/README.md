# Electron Live2D Frontend POC

Frontend-only Electron app in TypeScript: loads a Live2D model and connects to the Open-LLM-VTuber backend over WebSocket. Configurable host/port; can run with a minimal mock backend in Docker.

## Goals

- **Electron app** — Main, preload, and renderer in TypeScript.
- **Live2D** — Load one `.model3.json` model via Cubism Web SDK (Core + LApp).
- **WebSocket** — Connect to `ws://<host>:<port>/client-ws`; send `request-init-config`, handle `set-model-and-conf`.
- **Docker** — Optional backend container that exposes the WebSocket port.

## Prerequisites

- Node.js 18+ (LTS)
- npm or pnpm
- [Live2D Cubism SDK for Web](https://www.live2d.com/en/sdk/download/web/) — download and place Core (and optionally LApp/Framework) as below.

## 1. Place Live2D SDK

**→ See [SETUP_LIVE2D.md](./SETUP_LIVE2D.md) for step-by-step instructions.**

You need two files in **`public/libs/`**:

| File                      | Source                                                                                         |
| ------------------------- | ---------------------------------------------------------------------------------------------- |
| `live2dcubismcore.min.js` | Cubism SDK for Web → Core folder ([download](https://www.live2d.com/en/sdk/download/web/))     |
| `lapp.min.js`             | Framework/LApp script that defines `LAppDelegate` (from CubismWebSamples build or SDK package) |

Create the folder and copy the files; the app loads Core first, then LApp.

## 2. Default character (model)

Models use a `.model3.json` descriptor (e.g. like the shizuku example in the guide). For the mock backend:

- Place your model under `models/mao_pro/runtime/`, e.g.:
  - `mao_pro.model3.json`
  - Referenced assets (`.moc3`, textures, physics, motions, etc.) in the same directory or paths relative to it.

You can use a sample from [Live2D Cubism samples](https://www.live2d.com/en/learn/sample/) (agree to the license and download), then rename/copy the folder to `models/mao_pro/runtime/` and ensure the descriptor is named `mao_pro.model3.json` (or adjust the backend’s `model_info.path` and the main process’s default model URL).

## 3. Run with Docker (backend only)

Backend exposes WebSocket and HTTP for model files:

```bash
cd pocs/electron-live2d
docker-compose up --build
```

Port **12393** is exposed. Then run the Electron app on the host (see below) with default host/port so it connects to `localhost:12393`.

## 4. Run the Electron app

From this directory:

```bash
npm install
npm run build
npm start
```

Custom host/port:

```bash
npm start -- --host=192.168.1.2 --port=12393
```

Or with env:

```bash
OPEN_LLM_VTUBER_HOST=192.168.1.2 OPEN_LLM_VTUBER_PORT=12393 npm start
```

## 5. Run mock backend locally (no Docker)

```bash
npm run build:backend
npm run backend
```

Then in another terminal:

```bash
npm start
```

## Project layout

- `src/main/main.ts` — Main process: window, preload, parse `--host`/`--port`, send server and model config via IPC.
- `src/preload/preload.ts` — Preload: expose `getServerConfig()` and `getModelConfig()` to the renderer.
- `src/renderer/main.ts` — Renderer: get config, open WebSocket, send `request-init-config`, apply `set-model-and-conf`, bootstrap Live2D (LApp path/scale, `LAppDelegate.getInstance().initialize()` and `run()`).
- `src/shared/types.ts` — `ServerConfig`, `ModelConfig`, WebSocket message types.
- `src/backend/server.ts` — Minimal WebSocket + static server for POC (optional; used by Docker).
- `public/index.html` — Canvas, status div, SDK script tags, renderer module.
- `public/libs/` — You add Cubism Core and LApp here.

## TypeScript

- Strict mode; avoid `any`; use `src/renderer/live2d.d.ts` for Cubism/LApp globals.
- Config and WebSocket message types are defined in `src/shared/types.ts`.

## Reference

For a full frontend implementation (Electron, TypeScript, Live2D, WebSocket, configurable host/port), see the **Open-LLM-VTuber-Web** repository.
