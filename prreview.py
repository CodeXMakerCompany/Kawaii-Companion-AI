"""PR review in Kiro: pick a repo folder and a branch, and Kiro opens on that folder with a
new chat holding the review prompt, typed in but not sent (you run it).

Kiro has no outside way to put text in its chat, but inside Kiro the command
kiroAgent.focusChatInput takes {newSession, prompt} and fills the input without sending.
So a small Kiro extension (the bridge below, installed into Kiro the first time a review
is asked for) watches a request file; the Kiro window that has the requested folder open
claims it and starts the chat. Requests older than two minutes are ignored.
"""

import json
import os
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path

START = Path.home() / "Projects"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "shark-viewer"
REQUEST = CACHE / "kiro-request.json"
EXTENSION_ID = "shark-viewer.pr-review"
VERSION = "0.0.1"
PROMPT = ("Check the branch {branch}, compare it with {base} and use /pr-review as guidelines. Ensure no logic is "
          "broken. Prepare the proper questions in a pr-summary.md with the line references so I can review it "
          "personally.")


# ---- folders and branches ------------------------------------------------------

def is_repo(path):
    return (Path(path) / ".git").exists()


def folders(path):
    """Subfolders of `path` (no hidden ones), as [(name, is a git repo)], repos first."""
    try:
        names = [e.name for e in os.scandir(path) if e.is_dir() and not e.name.startswith(".")]
    except OSError:
        return []
    return sorted(((n, is_repo(Path(path) / n)) for n in names), key=lambda e: (not e[1], e[0].lower()))


def git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=10)
    return out.stdout if out.returncode == 0 else ""


def branches(repo):
    """([(branch, is the current one)], newest commit first; remote-only ones as origin/...),
    and the base to compare with (main or master)."""
    current = git(repo, "branch", "--show-current").strip()
    local, remote = [], []
    for ref in git(repo, "for-each-ref", "--sort=-committerdate", "--format=%(refname)",
                   "refs/heads", "refs/remotes").split():
        if ref.startswith("refs/heads/"):
            local.append(ref[len("refs/heads/"):])
        elif not ref.endswith("/HEAD"):
            remote.append(ref[len("refs/remotes/"):])
    shown = local + [r for r in remote if r.split("/", 1)[-1] not in local]
    names = {b.split("/", 1)[-1] if b in remote else b for b in shown}
    base = next((b for b in ("main", "master") if b in names), "main")
    return [(b, b == current) for b in shown], base


# ---- Kiro ------------------------------------------------------------------------

def kiro():
    return shutil.which("kiro") or ("/usr/share/kiro/bin/kiro" if os.path.exists("/usr/share/kiro/bin/kiro") else None)


def bridge_installed():
    exe = kiro()
    if not exe:
        return False
    out = subprocess.run([exe, "--list-extensions"], capture_output=True, text=True, timeout=30)
    return EXTENSION_ID in out.stdout.split()


def install_bridge():
    """Package the bridge as a .vsix and install it into Kiro. Returns an error or None."""
    CACHE.mkdir(parents=True, exist_ok=True)
    vsix = CACHE / f"{EXTENSION_ID}-{VERSION}.vsix"
    with zipfile.ZipFile(vsix, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("extension.vsixmanifest", MANIFEST)
        z.writestr("extension/package.json", json.dumps(PACKAGE, indent=2))
        z.writestr("extension/extension.js", EXTENSION_JS)
    out = subprocess.run([kiro(), "--install-extension", str(vsix), "--force"], capture_output=True, text=True,
                         timeout=120)
    return None if out.returncode == 0 else (out.stderr.strip() or out.stdout.strip() or "install failed")


class Reviewer:
    """Starts a review in the background (installing the bridge can take a few seconds);
    poll() returns the outcome message once."""

    def __init__(self):
        self.result = None
        self.busy = False

    def start(self, repo, branch, base):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._run, args=(repo, branch, base), daemon=True, name="prreview").start()

    def poll(self):
        result, self.result = self.result, None
        if result:
            self.busy = False
        return result

    def _run(self, repo, branch, base):
        try:
            if not kiro():
                self.result = (False, "Kiro is not installed")
                return
            if not bridge_installed():
                error = install_bridge()
                if error:
                    self.result = (False, f"Could not add the bridge to Kiro: {error.splitlines()[0]}")
                    return
            prompt = PROMPT.format(branch=branch, base=base)
            CACHE.mkdir(parents=True, exist_ok=True)
            tmp = REQUEST.with_suffix(".tmp")
            tmp.write_text(json.dumps({"folder": str(Path(repo).resolve()), "prompt": prompt, "at": time.time()}))
            tmp.replace(REQUEST)  # whole, or not at all: the bridge never reads half a request
            subprocess.Popen([kiro(), str(repo)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            self.result = (True, f"Kiro is opening {Path(repo).name}: the review prompt is in a new chat, not sent")
        except (OSError, subprocess.SubprocessError) as e:
            self.result = (False, f"Could not open Kiro: {e}")


# ---- the bridge extension ---------------------------------------------------------

PACKAGE = {
    "name": "pr-review", "publisher": "shark-viewer", "version": VERSION,
    "displayName": "Shark Viewer PR Review",
    "description": "Starts a Kiro chat with a PR review prompt typed in (not sent), when the Shark Viewer overlay asks.",
    "engines": {"vscode": "^1.90.0"},
    "activationEvents": ["onStartupFinished"],
    "main": "./extension.js",
}

EXTENSION_JS = r"""// Shark Viewer bridge: when the overlay asks for a PR review of the folder open in this
// window, start a new Kiro chat with the review prompt typed in. It is never sent: you run it.
const vscode = require("vscode");
const fs = require("fs");
const os = require("os");
const path = require("path");

const DIR = path.join(process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache"), "shark-viewer");
const FILE = path.join(DIR, "kiro-request.json");
const FRESH_MS = 120000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function isMine(folder) {
  return (vscode.workspace.workspaceFolders || []).some((f) => path.resolve(f.uri.fsPath) === path.resolve(folder));
}

async function check() {
  let req;
  try { req = JSON.parse(fs.readFileSync(FILE, "utf8")); } catch { return; }
  if (!req || !req.prompt || !isMine(req.folder) || Date.now() - req.at * 1000 > FRESH_MS) return;
  try { fs.unlinkSync(FILE); } catch { return; }  // another window got it first
  // The first call opens the chat (a window that just started may not have it yet); the
  // second starts a new session with the prompt in its input, without submitting it.
  await vscode.commands.executeCommand("kiroAgent.focusChatInput");
  await sleep(1500);
  await vscode.commands.executeCommand("kiroAgent.focusChatInput", { newSession: true, prompt: req.prompt });
}

function activate(context) {
  fs.mkdirSync(DIR, { recursive: true });
  const watcher = fs.watch(DIR, (_, name) => { if (name === "kiro-request.json") setTimeout(check, 300); });
  context.subscriptions.push({ dispose: () => watcher.close() });
  setTimeout(check, 3000);  // a window opened for this request: let Kiro's chat load first
}

module.exports = { activate, deactivate() {} };
"""

MANIFEST = f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="pr-review" Version="{VERSION}" Publisher="shark-viewer" />
    <DisplayName>Shark Viewer PR Review</DisplayName>
    <Description xml:space="preserve">{PACKAGE["description"]}</Description>
    <Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.90.0" /></Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code" /></Installation>
  <Dependencies />
  <Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" /></Assets>
</PackageManifest>
"""

CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json" />
  <Default Extension=".js" ContentType="application/javascript" />
  <Default Extension=".vsixmanifest" ContentType="text/xml" />
</Types>
"""
