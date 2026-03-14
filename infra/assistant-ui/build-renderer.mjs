import * as esbuild from "esbuild";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { existsSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "src");
const out = join(__dirname, "public", "renderer", "index.js");

/** Resolve .js specifiers to .ts/.tsx when the .js file doesn't exist (TS ESM convention). */
function resolveJsToTsPlugin() {
  return {
    name: "resolve-js-to-ts",
    setup(build) {
      build.onResolve({ filter: /\.js$/ }, (args) => {
        const resolvedDir = args.resolveDir || root;
        if (resolvedDir.startsWith(root)) {
          const base = join(resolvedDir, args.path.replace(/\.js$/, ""));
          for (const ext of [".tsx", ".ts"]) {
            const p = base + ext;
            if (existsSync(p)) return { path: p };
          }
        }
        return null;
      });
    },
  };
}

await esbuild
  .build({
    entryPoints: [join(root, "renderer", "index.tsx")],
    bundle: true,
    format: "esm",
    platform: "browser",
    target: "es2020",
    outfile: out,
    jsx: "automatic",
    loader: { ".ts": "ts", ".tsx": "tsx", ".js": "js" },
    plugins: [resolveJsToTsPlugin()],
  })
  .catch(() => process.exit(1));

console.log("Renderer bundle:", out);
