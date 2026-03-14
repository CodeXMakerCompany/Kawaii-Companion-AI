# Architecture (DDD-style)

Lightweight layered structure for the Electron Live2D POC.

## Layout

```
src/
├── domain/           # Domain layer – types, value objects, domain data
│   ├── index.ts      # Re-exports shared types + ExpressionAction, ModelUrlParts
│   └── expression-actions.ts   # EXPRESSION_ACTIONS (domain data)
│
├── application/      # Application layer – use cases, ports
│   ├── ports.ts      # IConfigPort, ILive2DPort (interfaces for infra)
│   └── init-live2d.ts # Use case: init Live2D with config, start, load expressions
│
├── infrastructure/   # Infrastructure – adapters to external systems
│   ├── electron-config.ts  # IConfigPort impl (window.electronAPI)
│   ├── live2d-adapter.ts   # ILive2DPort impl (LApp globals, DOM)
│   └── ws-client.ts       # WebSocket client (open, send, parse backend messages)
│
├── renderer/         # Presentation – React UI (renderer process)
│   ├── index.tsx     # Entry: mount React root
│   ├── App.tsx       # Root component, runs init use case
│   ├── main.ts       # Legacy entry (replaced by index.tsx)
│   ├── preload.d.ts  # Window.electronAPI types
│   └── ...
│
├── main/             # Electron main process (unchanged)
├── preload/          # Context bridge (unchanged)
├── shared/            # Shared types (used by domain + main/preload)
└── backend/           # Optional HTTP/WS server
```

## Flow

1. **Entry:** `public/index.html` loads Live2D libs then `renderer/index.js` (from `src/renderer/index.tsx`).
2. **React** mounts `App`; `App` runs the **init Live2D** use case in `useEffect`.
3. **Use case** `initLive2D(config, live2d, setStatus)` uses **ports** (`IConfigPort`, `ILive2DPort`) and updates status via callback.
4. **Infrastructure** implements ports: `createElectronConfig()`, `createLive2DAdapter(setStatus)`.
5. **Domain** supplies types and expression list; no I/O or framework.

## Conventions

- **Domain:** No React, no Node, no `window` – only types and domain data.
- **Application:** Use cases depend on ports (interfaces); no concrete infra.
- **Infrastructure:** Implements ports; talks to Electron, Live2D (globals/DOM), and external services (e.g. WebSocket via ws-client).
- **Renderer:** React components and hooks; composes use cases and infra.

Migration was non-aggressive: Live2D and expression logic live in the adapter; React owns the root and status bar; expression buttons are still created by the adapter and appended to the container div.
