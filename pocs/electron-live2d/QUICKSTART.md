# Quick start

## 1. Backend in Docker (expose WebSocket port)

```bash
cd pocs/electron-live2d
docker-compose up --build
```

Port **12393** is exposed. Optional: place a Live2D model in `models/mao_pro/runtime/` (e.g. `mao_pro.model3.json` + assets) and mount is already configured.

## 2. Electron app (on host)

```bash
cd pocs/electron-live2d
npm install
npm run build
npm start
```

Uses `localhost:12393` by default. Override:

```bash
npm start -- --host=192.168.1.2 --port=12393
```

## 3. Live2D SDK (required for model rendering)

Download [Cubism SDK for Web](https://www.live2d.com/en/sdk/download/web/) and put in `public/libs/`:

- `live2dcubismcore.min.js`
- LApp/Framework script(s) so `LAppDelegate` is available (e.g. `lapp.min.js`)

Without these, the app opens but shows "Live2D SDK not loaded" and no model.
