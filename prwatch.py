"""New comments on your open pull requests, checked with the GitHub CLI (gh) every 15 minutes.

One read-only GraphQL query through `gh api graphql` lists your open PRs with their
latest conversation comments, reviews and inline review comments; anything not by you
and not seen before is new. Seen ids are saved with the still-unread comments, so a
restart neither announces old comments again nor forgets the unread ones; the very first
check only learns what is already there. gh runs in a thread, so a slow network never
stalls the overlay. Nothing here writes to GitHub.
"""

import json
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

INTERVAL = 15 * 60  # seconds between checks
FIRST_CHECK = 10  # seconds after start
KEEP_SEEN = 3000  # ids remembered

QUERY = """
query {
  viewer {
    login
    pullRequests(states: OPEN, first: 25, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        number title url
        repository { nameWithOwner }
        comments(last: 15) { nodes { id author { login } body createdAt url } }
        reviews(last: 15) {
          nodes {
            id author { login } body state submittedAt url
            comments(first: 15) { nodes { id author { login } body path line originalLine createdAt url } }
          }
        }
      }
    }
  }
}
"""


class PRWatcher:
    def __init__(self, state_file, interval=None):
        self.state_file = Path(state_file)
        self.interval = interval or INTERVAL
        self.available = shutil.which("gh") is not None
        self.next_look = 0.0  # without gh: when to look for it again (installed later)
        self.next_check = None  # set on the first due()
        self.busy = False
        self.results = queue.Queue()
        self.error = None
        self.checked_at = None  # wall-clock time of the last good check
        try:
            saved = json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            saved = None
        self.first = saved is None  # nothing saved yet: the first check only learns
        saved = saved or {}
        self.seen = list(saved.get("seen", []))
        self.unread = list(saved.get("unread", []))  # comments to review, oldest first

    def due(self, now):
        if not self.available and now >= self.next_look:
            self.available, self.next_look = shutil.which("gh") is not None, now + 60
        if not self.available or self.busy:
            return False
        if self.next_check is None:
            self.next_check = now + FIRST_CHECK
        return now >= self.next_check

    def check(self, now):
        """Start a check in the background."""
        self.busy, self.next_check = True, now + self.interval
        threading.Thread(target=self._fetch, daemon=True, name="prwatch").start()

    def poll(self):
        """Comments that arrived since the last poll ([] most of the time)."""
        new = []
        while True:
            try:
                kind, payload = self.results.get_nowait()
            except queue.Empty:
                return new
            self.busy = False
            if kind == "error":
                if payload != self.error:
                    print(f"prwatch: {payload}", file=sys.stderr)
                self.error = payload
                continue
            self.error = None
            self.checked_at, comments = payload
            seen = set(self.seen)
            fresh = [c for c in comments if c["id"] not in seen]
            self.seen = (self.seen + [c["id"] for c in fresh])[-KEEP_SEEN:]
            if self.first:  # what was already there is not news
                self.first = False
            else:
                fresh.sort(key=lambda c: c["at"])
                self.unread += fresh
                new += fresh
            self._save()

    def mark_read(self):
        if self.unread:
            self.unread = []
            self._save()

    def _save(self):
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps({"seen": self.seen, "unread": self.unread}))
        except OSError as e:
            print(f"prwatch: cannot save {self.state_file}: {e}", file=sys.stderr)

    def _fetch(self):
        import time
        try:
            out = subprocess.run(["gh", "api", "graphql", "-f", f"query={QUERY}"], capture_output=True,
                                 text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            self.results.put(("error", f"gh failed: {e}"))
            return
        if out.returncode != 0:
            self.results.put(("error", (out.stderr.strip() or "gh failed").splitlines()[0]))
            return
        try:
            viewer = json.loads(out.stdout)["data"]["viewer"]
        except (ValueError, KeyError, TypeError):
            self.results.put(("error", "gh: unexpected answer"))
            return
        self.results.put(("ok", (time.time(), comments_of(viewer))))


def comments_of(viewer):
    """Everyone else's comments, reviews and inline comments on the viewer's open PRs."""
    me = viewer.get("login")
    out = []
    for pr in viewer["pullRequests"]["nodes"]:
        base = {"repo": pr["repository"]["nameWithOwner"], "number": pr["number"], "title": pr["title"]}

        def add(node, kind, at_key="createdAt", **extra):
            who = (node.get("author") or {}).get("login") or "ghost"
            if who != me:
                out.append({**base, "id": node["id"], "kind": kind, "author": who, "body": node.get("body") or "",
                            "at": node.get(at_key) or "", "url": node.get("url") or pr["url"], **extra})

        for c in pr["comments"]["nodes"]:
            add(c, "comment")
        for r in pr["reviews"]["nodes"]:
            if r["body"] or r["state"] in ("APPROVED", "CHANGES_REQUESTED"):  # a bare COMMENTED just holds inline ones
                add(r, "review", "submittedAt", state=r["state"])
            for c in r["comments"]["nodes"]:
                add(c, "inline", path=c.get("path") or "", line=c.get("line") or c.get("originalLine"))
    return out
