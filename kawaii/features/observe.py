"""Observability: endpoints you add get a GET every 20 minutes, green when they answer (401
and 403 too, marked unauth), red when they don't (404 and other errors, timeouts, refused
connections).

The list and each endpoint's last result are saved, so a restart keeps the lights as they
were until the next round. Requests run in a thread, so a slow server never stalls the
overlay.
"""

import json
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

INTERVAL = 20 * 60  # seconds between rounds
FIRST_CHECK = 5  # seconds after start
TIMEOUT = 10  # seconds per request


class Pinger:
    def __init__(self, state_file, interval=None):
        self.state_file = Path(state_file)
        self.interval = interval or INTERVAL
        self.next_check = None  # set on the first due()
        self.busy = False
        self.results = queue.Queue()
        self.checked_at = None  # wall-clock time of the last round
        try:
            saved = json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            saved = {}
        # [{url, title, ok (True/False/None: not checked yet), status ("200", "404", "timeout"...)}]
        self.endpoints = list(saved.get("endpoints", []))
        self.checked_at = saved.get("checked_at")

    @property
    def down(self):
        return [e for e in self.endpoints if e.get("ok") is False]

    def add(self, url, title=""):
        url = url.strip()
        if not url:
            return False
        if "://" not in url:
            url = "https://" + url
        if any(e["url"] == url for e in self.endpoints):
            return False
        self.endpoints.append({"url": url, "title": title.strip(), "ok": None, "status": ""})
        self._save()
        self.next_check = 0.0  # check the new one right away
        return True

    def remove(self, index):
        if 0 <= index < len(self.endpoints):
            del self.endpoints[index]
            self._save()

    def due(self, now):
        if self.busy or not self.endpoints:
            return False
        if self.next_check is None:
            self.next_check = now + FIRST_CHECK
        return now >= self.next_check

    def check(self, now):
        """Start a round in the background."""
        self.busy, self.next_check = True, now + self.interval
        urls = [e["url"] for e in self.endpoints]
        threading.Thread(target=self._fetch, args=(urls,), daemon=True, name="observe").start()

    def poll(self):
        """None until a round finishes; then the endpoints that went down in it (maybe [])."""
        try:
            at, results = self.results.get_nowait()
        except queue.Empty:
            return None
        self.busy, self.checked_at = False, at
        went_down = []
        for e in self.endpoints:
            if e["url"] in results:
                ok, status = results[e["url"]]
                if not ok and e.get("ok") is not False:
                    went_down.append(e)
                e["ok"], e["status"] = ok, status
        self._save()
        return went_down

    def _save(self):
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps({"endpoints": self.endpoints, "checked_at": self.checked_at},
                                                  indent=1))
        except OSError as e:
            print(f"observe: cannot save {self.state_file}: {e}", file=sys.stderr)

    def _fetch(self, urls):
        self.results.put((time.time(), {url: ping(url) for url in urls}))


def ping(url):
    """(answered fine, short status) for one GET."""
    req = urllib.request.Request(url, headers={"User-Agent": "shark-viewer/observe"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status < 400, str(r.status)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):  # it answers, it just wants credentials: up
            return True, f"{e.code} · unauth"
        return False, str(e.code)
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, TimeoutError) or "timed out" in str(reason):
            return False, "timeout"
        return False, "off" if isinstance(reason, ConnectionRefusedError) else "not found"
    except (TimeoutError, OSError, ValueError) as e:
        return False, "timeout" if isinstance(e, TimeoutError) else "error"
