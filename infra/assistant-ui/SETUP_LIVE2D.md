# Live2D SDK setup for this POC

The app needs two files in **`public/libs/`**:

1. **Cubism Core** — `live2dcubismcore.min.js`
2. **LApp / Framework** — a **built** script that defines `LAppDelegate` (we load it as `lapp.min.js`). The `.ts` files in Demo/src are **source**; you must build the Demo first to get a single `.js` bundle.

---

## Step 1: Core — copy the minified file

From your **Core** folder (e.g. `CubismSdkForWeb-5-r.4/Core` or `Cubism_SDK_for_Web_4_0_0/.../Core`):

- Copy **`live2dcubismcore.min.js`** into this POC:

```bash
mkdir -p pocs/electron-live2d/public/libs
cp "/path/to/your/Core/live2dcubismcore.min.js" pocs/electron-live2d/public/libs/
```

Example if the SDK is in your Downloads folder:

```bash
mkdir -p pocs/electron-live2d/public/libs
cp "$HOME/Downloads/CubismSdkForWeb-5-r.4/Core/live2dcubismcore.min.js" pocs/electron-live2d/public/libs/
```

---

## Step 2: LApp — build the Demo, then copy the bundle

The **Demo/src** folder (lappdelegate.ts, lappdefine.ts, etc.) is **source**. The app needs a **built** JavaScript file that exposes `LAppDelegate`. So you must build the Demo once, then copy the output.

1. **Build the Demo** (from the **root of your SDK**, not only Demo/src):
   - Open the SDK folder in VS Code and run the build task: **Ctrl+Shift+B** → choose **“npm: build – Samples/TypeScript/Demo”**, or
   - Or from a terminal, from the SDK root (where the Demo’s `package.json` lives):
     ```bash
     cd /path/to/Cubism_SDK_for_Web_4_0_0/Samples/TypeScript/Demo
     npm install
     npm run build
     ```
2. After the build, the Demo creates **`dist/`** with:
   - **`dist/assets/index-XXXXX.js`** — the main bundle (~200 KB, hash like `index-DAhHvHok.js`). This is the LApp/Framework bundle.
   - `dist/Core/`, `dist/Resources/`, `dist/index.html` — used by the Demo’s own page; we only need the bundle from `assets/`.
3. **Copy the bundle from `dist/assets/`** (the one `.js` file with the long name) into this POC **and name it exactly `lapp.min.js`** (the HTML loads that filename):

```bash
# Replace XXXXX with your actual hash (e.g. DAhHvHok), or use a glob:
cp "$HOME/Downloads/CubismSdkForWeb-5-r.4/Samples/TypeScript/Demo/dist/assets/index-"*.js pocs/electron-live2d/public/libs/lapp.min.js
```

Or copy the file manually: from `dist/assets/index-XXXXX.js` → `public/libs/lapp.min.js`.

**Note:** The Demo build may warn that `./Core/live2dcubismcore.js` in its `index.html` can’t be bundled without `type="module"`. You can ignore that — we don’t use the Demo’s index.html. We load Core and your copied bundle in our own HTML.

---

### Expose LAppDelegate on `window` (required)

The Vite-built bundle **does not** attach `LAppDelegate` or `LAppDefine` to `window`, so our app cannot see them. You must expose them in the Demo source once, then rebuild.

**Option A — Edit by hand**

1. Open **`Samples/TypeScript/Demo/src/main.ts`** in your Cubism SDK folder (e.g. `~/Downloads/CubismSdkForWeb-5-r.4/...`).
2. Add these two lines **immediately after** the line `import * as LAppDefine from './lappdefine';` (and before the comment `/** ブラウザロード...`):

   ```ts
   (window as any).LAppDelegate = LAppDelegate;
   (window as any).LAppDefine = LAppDefine;
   ```

3. Save, then rebuild and copy:
   ```bash
   cd Samples/TypeScript/Demo
   npm run build
   cp dist/assets/index-*.js /path/to/Kawaii-Companion-AI/pocs/electron-live2d/public/libs/lapp.min.js
   ```

**Option B — Patch from this repo**

From the **Kawaii-Companion-AI** repo root, if your SDK is at e.g. `~/Downloads/CubismSdkForWeb-5-r.4`:

```bash
DEMO_MAIN=~/Downloads/CubismSdkForWeb-5-r.4/Samples/TypeScript/Demo/src/main.ts
sed -i "/import \* as LAppDefine from '\.\/lappdefine';/a\\
(window as any).LAppDelegate = LAppDelegate;\\
(window as any).LAppDefine = LAppDefine;" "$DEMO_MAIN"
```

Then rebuild the Demo and copy the new bundle to `pocs/electron-live2d/public/libs/lapp.min.js` as above.

Without this step, you will see "LApp not exposed" even when both script files are present.

---

## Check

You should have:

```text
pocs/electron-live2d/public/libs/
├── live2dcubismcore.min.js   # from Step 1
└── lapp.min.js               # from Step 2 (LAppDelegate / Framework)
```

---

## Quick copy (replace with your SDK paths)

From the **root of this repo** (Kawaii-Companion-AI):

```bash
# 1) Create folder
mkdir -p pocs/electron-live2d/public/libs

# 2) Core (use your actual Core path, e.g. ~/Downloads/CubismSdkForWeb-5-r.4/Core)
cp "$HOME/Downloads/CubismSdkForWeb-5-r.4/Core/live2dcubismcore.min.js" pocs/electron-live2d/public/libs/

# 3) LApp — copy the built bundle from dist/assets/ (hash in filename changes each build)
cp "$HOME/Downloads/CubismSdkForWeb-5-r.4/Samples/TypeScript/Demo/dist/assets/index-"*.js pocs/electron-live2d/public/libs/lapp.min.js
```

Then run:

```bash
cd pocs/electron-live2d
npm run build
npm start
```

If the SDK is loaded correctly, the status will move to **"Connecting to…"** and then **"Live2D running"** (or **"Live2D SDK not loaded"** will disappear). If you still see **"Live2D SDK not loaded"**, open DevTools (View → Toggle Developer Tools) and check the Console for script load errors (e.g. 404 for `libs/lapp.min.js` or `libs/live2dcubismcore.min.js`).
