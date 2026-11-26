"""Decode whatever you paste: recognise what a piece of text is and show it readable.

decode(text) -> Result, trying the decoders below in order (the first that recognises
the text wins, plain text is the fallback). All local: nothing leaves the machine
except a stack trace you choose to send for an explanation (the viewer does that).

  JWT              header and claims, with issued/expiry times (the signature is not checked)
  Stack trace      exception and the frames that matter (Python, JS, Java, Go, Rust); Explain?
  JSON             pretty-printed (also a JSON string holding JSON)
  Timestamp        epoch seconds/ms/µs/ns -> date; an ISO 8601 date -> epoch
  UUID / ULID      version, and the time inside v1/v6/v7 UUIDs and ULIDs
  URL              its parts and query parameters, percent-decoded
  URL-encoded      a query string or %XX text, decoded
  Color            hex / rgb() -> hex, rgb, hsl (with a swatch)
  Number           0x / 0b / 0o / decimal -> every base, and the size in bytes
  Permissions      755 <-> rwxr-xr-x
  Cron             a 5-field cron expression in words
  IP / CIDR        address class, network range and host count
  Escapes          HTML entities, \\uXXXX, \\xXX
  Hex              bytes as text
  Base64           text, JSON, or a file type and hex dump for binary
  Text             length, words, lines and hashes

Paste and Copy use wl-clipboard (wl-paste / wl-copy) and only run when you click them.
"""

import base64
import binascii
import colorsys
import datetime
import hashlib
import html
import ipaddress
import json
import queue
import re
import shutil
import subprocess
import threading
import urllib.parse
import uuid

MAX_LINES = 400  # of output shown


class Result:
    def __init__(self, kind, sections, copy=None, explain=False, swatch=None):
        self.kind = kind  # what it was: "JWT", "JSON", ...
        self.sections = sections  # [(heading, text)]
        self.copy = copy if copy is not None else "\n\n".join(t for _, t in sections)  # what Copy puts on the clipboard
        self.explain = explain  # a stack trace: offer to explain it
        self.swatch = swatch  # (r, g, b) for colors


def decode(text):
    text = text.strip()
    if not text:
        return None
    for decoder in DECODERS:
        try:
            result = decoder(text)
        except (ValueError, TypeError, KeyError, IndexError, OverflowError, UnicodeError, binascii.Error):
            result = None
        if result:
            return result
    return None


# ---- helpers -------------------------------------------------------------------

def when(dt):
    """'2026-11-20 15:42:07 · 21:42 UTC · 3h ago' (the first part in local time)"""
    delta = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    return f"{dt.astimezone():%Y-%m-%d %H:%M:%S} · {dt.astimezone(datetime.timezone.utc):%H:%M} UTC · {relative(delta)}"


def relative(seconds):
    future, s = seconds > 0, abs(seconds)
    for unit, size in (("y", 31557600), ("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        if s >= size or unit == "s":
            n = f"{int(s // size)}{unit}"
            return f"in {n}" if future else f"{n} ago"


def b64(s):
    """Standard or URL-safe base64, padding optional."""
    s = re.sub(r"\s+", "", s)
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.replace("+", "-").replace("/", "_"))


def pretty(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


def printable(data):
    try:
        t = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return t if all(c.isprintable() or c in "\n\r\t" for c in t) else None


MAGIC = [(b"\x89PNG", "PNG image"), (b"\xff\xd8\xff", "JPEG image"), (b"GIF8", "GIF image"), (b"%PDF", "PDF"),
         (b"PK\x03\x04", "ZIP archive (or docx/xlsx/jar)"), (b"\x1f\x8b", "gzip data"), (b"RIFF", "RIFF (WAV/WebP)"),
         (b"\x7fELF", "ELF executable"), (b"BZh", "bzip2 data"), (b"\xfd7zXZ", "xz data"), (b"OggS", "Ogg media")]


def hexdump(data, rows=8):
    out = []
    for i in range(0, min(len(data), rows * 16), 16):
        chunk = data[i:i + 16]
        out.append(f"{i:04x}  {chunk.hex(' '):<47}  {''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)}")
    if len(data) > rows * 16:
        out.append(f"… {len(data)} bytes in all")
    return "\n".join(out)


def bytes_view(data, what):
    text = printable(data)
    if text is not None:
        try:
            return Result(f"{what} → JSON", [("JSON", pretty(json.loads(text)))])
        except ValueError:
            return Result(f"{what} → text", [("Decoded", text)])
    kind = next((name for sig, name in MAGIC if data.startswith(sig)), "binary data")
    return Result(f"{what} → {kind}", [(f"{kind}, {len(data)} bytes", hexdump(data))], copy=data.hex())


# ---- decoders ------------------------------------------------------------------

def jwt(t):
    parts = t.split(".")
    if len(parts) != 3 or not t.startswith("eyJ"):
        return None
    header, claims = json.loads(b64(parts[0])), json.loads(b64(parts[1]))
    times = []
    for key, label in (("iat", "issued"), ("nbf", "valid from"), ("exp", "expires")):
        if isinstance(claims.get(key), (int, float)):
            dt = datetime.datetime.fromtimestamp(claims[key], datetime.timezone.utc)
            times.append(f"{label:<10} {when(dt)}")
    if isinstance(claims.get("exp"), (int, float)):
        left = claims["exp"] - datetime.datetime.now(datetime.timezone.utc).timestamp()
        times.append("EXPIRED" if left < 0 else f"still valid for {relative(left)[3:]}")
    sections = [("Header", pretty(header)), ("Claims", pretty(claims))]
    if times:
        sections.insert(0, ("Times", "\n".join(times)))
    sections.append(("Signature", f"{header.get('alg', '?')}, not verified ({len(parts[2])} chars)"))
    return Result("JWT", sections, copy=pretty(claims))


TRACE = re.compile(r"Traceback \(most recent call last\)|^\s+at [\w$.<>]+.*\(.*:\d+(:\d+)?\)|^\s+at .+:\d+:\d+|"
                   r"Exception in thread|^\s+at [\w.$]+\([\w.]+:\d+\)|^goroutine \d+ \[|panicked at|"
                   r"^\s*File \".+\", line \d+", re.M)


def stack_trace(t):
    if len(TRACE.findall(t)) < 1 or "\n" not in t:
        return None
    lines = [ln.rstrip() for ln in t.splitlines() if ln.strip()]
    error = next((ln.strip() for ln in reversed(lines) if re.match(r"\s*[\w.]*(Error|Exception|Exit|Interrupt)\b", ln)
                  or "panicked at" in ln), None) or lines[-1].strip()
    frames = [ln.strip() for ln in lines if re.match(r'\s*(File "|at |\S+\.go:\d+)', ln)]
    language = ("Python" if "Traceback" in t or 'File "' in t else "Go" if "goroutine" in t else
                "Rust" if "panicked at" in t else "Java" if re.search(r"at [\w.$]+\([\w.]+\.java:\d+\)", t) else
                "JavaScript")
    shown = frames[-6:] if language == "Python" else frames[:6]  # where it broke: last in Python, first elsewhere
    body = [("Error", error), (f"{language} · {len(frames)} frames, the ones nearest the error", "\n".join(shown) or "—")]
    return Result(f"Stack trace ({language})", body, copy=t, explain=True)


def json_text(t):
    if not (t[0] in "{[" or (t[0] == '"' and t[-1] == '"')):
        return None
    obj = json.loads(t)
    if isinstance(obj, str):  # a JSON string holding JSON
        obj = json.loads(obj)
    if not isinstance(obj, (dict, list)):
        return None
    size = f"{len(obj)} {'keys' if isinstance(obj, dict) else 'items'}"
    return Result("JSON", [(f"Pretty ({size})", pretty(obj))], copy=pretty(obj))


def timestamp(t):
    if re.fullmatch(r"\d{9,19}(\.\d+)?", t):
        n = float(t)
        digits = len(t.split(".")[0])
        unit, scale = next((u, sc) for most, u, sc in ((11, "seconds", 1), (14, "milliseconds", 1e3),
                                                       (17, "microseconds", 1e6), (19, "nanoseconds", 1e9))
                           if digits <= most)
        dt = datetime.datetime.fromtimestamp(n / scale, datetime.timezone.utc)
        if not 1970 < dt.year < 2200:
            return None
        iso = dt.isoformat().replace("+00:00", "Z")
        return Result(f"Epoch ({unit})", [("Date", when(dt)), ("ISO 8601", iso)], copy=iso)
    m = re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?", t)
    if m:
        dt = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.astimezone()  # no zone given: local time
        secs = int(dt.timestamp())
        return Result("ISO date", [("Epoch", f"{secs}  (ms: {secs * 1000})"), ("Date", when(dt))], copy=str(secs))
    return None


def uuid_text(t):
    if re.fullmatch(r"\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?", t):
        u = uuid.UUID(t)
        info = [f"version {u.version}", f"variant {u.variant}"]
        if u.version == 1:
            secs = (u.time - 0x01b21dd213814000) / 1e7
            info.append("time      " + when(datetime.datetime.fromtimestamp(secs, datetime.timezone.utc)))
            info.append(f"node      {u.node:012x}")
        elif u.version == 7:
            ms = int(u.hex[:12], 16)
            info.append("time      " + when(datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)))
        elif u.version == 4:
            info.append("random: no time inside")
        return Result(f"UUID v{u.version}", [("UUID", str(u)), ("Inside", "\n".join(info))], copy=str(u))
    if re.fullmatch(r"[0-7][0-9A-HJKMNP-TV-Z]{25}", t.upper()) and not t.isdigit():  # ULID (Crockford base32)
        alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
        ms = 0
        for c in t.upper()[:10]:
            ms = ms * 32 + alphabet.index(c)
        dt = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)
        return Result("ULID", [("Time", when(dt)), ("Random part", t[10:])], copy=dt.isoformat())
    return None


def url(t):
    if not re.match(r"[a-zA-Z][\w+.-]*://\S+$", t):
        return None
    p = urllib.parse.urlsplit(t)
    parts = [f"scheme    {p.scheme}", f"host      {p.hostname or ''}" + (f"  port {p.port}" if p.port else "")]
    if p.username:
        parts.append(f"user      {urllib.parse.unquote(p.username)}")
    parts.append(f"path      {urllib.parse.unquote(p.path) or '/'}")
    if p.fragment:
        parts.append(f"fragment  {urllib.parse.unquote(p.fragment)}")
    sections = [("Parts", "\n".join(parts))]
    query = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    if query:
        width = min(18, max(len(k) for k, _ in query))
        sections.append((f"Query ({len(query)})", "\n".join(f"{k:<{width}}  {v}" for k, v in query)))
    return Result("URL", sections, copy=urllib.parse.unquote(t))


def url_encoded(t):
    if not re.search(r"%[0-9a-fA-F]{2}", t) and not re.fullmatch(r"[\w.~-]+=[^&\s]*(&[\w.~-]+=[^&\s]*)+", t):
        return None
    decoded = urllib.parse.unquote_plus(t)
    sections = [("Decoded", decoded)]
    if re.fullmatch(r"[^=&\s]+=[^&]*(&[^=&\s]+=[^&]*)*", t):
        query = urllib.parse.parse_qsl(t, keep_blank_values=True)
        width = min(18, max(len(k) for k, _ in query))
        sections.append((f"Parameters ({len(query)})", "\n".join(f"{k:<{width}}  {v}" for k, v in query)))
    return Result("URL-encoded", sections, copy=decoded)


def color(t):
    m = re.fullmatch(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", t)
    if m and (t.startswith("#") or len(m.group(1)) in (6, 8) and not t.isdigit()):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        alpha = int(h[6:8], 16) / 255 if len(h) == 8 else None
    else:
        m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", t)
        if not m:
            return None
        r, g, b = (min(255, int(v)) for v in m.groups()[:3])
        alpha = float(m.group(4)) if m.group(4) else None
    hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    hexs = f"#{r:02x}{g:02x}{b:02x}" + (f"{round(alpha * 255):02x}" if alpha is not None else "")
    lines = [f"hex   {hexs}", f"rgb   rgb({r}, {g}, {b}" + (f", {alpha:.2f})" if alpha is not None else ")"),
             f"hsl   hsl({round(hh * 360)}, {round(ss * 100)}%, {round(ll * 100)}%)"]
    return Result("Color", [("Color", "\n".join(lines))], copy=hexs, swatch=(r, g, b))


def number(t):
    m = re.fullmatch(r"(0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+|-?\d{1,8})", t)
    if not m:
        return None
    n = int(t, 0) if not t.lstrip("-").isdigit() else int(t)
    lines = [f"dec   {n}", f"hex   {hex(n)}", f"oct   {oct(n)}", f"bin   {bin(n)}"]
    if n >= 1024:
        size, unit = float(n), "B"
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if size < 1024:
                break
            size /= 1024
        lines.append(f"size  {size:.2f} {unit}")
    return Result("Number", [("Bases", "\n".join(lines))], copy=str(n))


def permissions(t):
    if re.fullmatch(r"[0-7]?[0-7]{3}", t) and len(t) in (3, 4):
        bits = t[-3:]
        rwx = "".join("rwx"[i] if int(d) & (4 >> i) else "-" for d in bits for i in range(3))
        who = [f"{name:<7}{rwx[i * 3:i * 3 + 3]}" for i, name in enumerate(("owner", "group", "others"))]
        return Result("Permissions", [("Symbolic", rwx), ("Who", "\n".join(who))], copy=rwx)
    if re.fullmatch(r"[d-]?[r-][w-][x-][r-][w-][x-][r-][w-][x-]", t):
        s = t[-9:]
        octal = "".join(str(sum(v for c, v in zip(s[i:i + 3], (4, 2, 1)) if c != "-")) for i in (0, 3, 6))
        return Result("Permissions", [("Octal", octal)], copy=octal)
    return None


CRON_FIELDS = ("minute", "hour", "day of month", "month", "day of week")
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def cron(t):
    fields = t.split()
    if len(fields) != 5 or not all(re.fullmatch(r"[\d*/,-]+|[A-Za-z]{3}(-[A-Za-z]{3})?", f) for f in fields):
        return None
    if all(f == "*" for f in fields[2:]) and fields[0].isdigit() and fields[1].isdigit():
        words = f"every day at {int(fields[1]):02d}:{int(fields[0]):02d}"
    else:
        words = None

    def say(f, name):
        if f == "*":
            return f"every {name}"
        if f.startswith("*/"):
            return f"every {f[2:]} {name}s"
        if name == "day of week" and f.isdigit():
            return DAYS[int(f)]
        return f"{name} {f}"
    explained = "\n".join(f"{n:<13} {f:<6} {say(f, n)}" for n, f in zip(CRON_FIELDS, fields))
    sections = [("Fields", explained)]
    if words:
        sections.insert(0, ("In words", words))
    return Result("Cron", sections, copy=words or explained)


def ip(t):
    try:
        if "/" in t:
            net = ipaddress.ip_network(t, strict=False)
            hosts = net.num_addresses - (2 if net.version == 4 and net.prefixlen < 31 else 0)
            lines = [f"network    {net.network_address}/{net.prefixlen}", f"netmask    {net.netmask}",
                     f"first      {next(iter(net.hosts()), net.network_address)}",
                     f"last       {net.broadcast_address if net.version == 6 else list(net.hosts())[-1] if hosts > 0 else net.broadcast_address}",
                     f"hosts      {hosts:,}"]
            return Result(f"IPv{net.version} network", [("Range", "\n".join(lines))], copy=str(net))
        addr = ipaddress.ip_address(t)
    except ValueError:
        return None
    kind = ("loopback" if addr.is_loopback else "private" if addr.is_private else "link-local" if addr.is_link_local
            else "multicast" if addr.is_multicast else "public")
    lines = [f"kind       {kind}", f"version    IPv{addr.version}", f"integer    {int(addr)}"]
    if addr.version == 6:
        lines.append(f"expanded   {addr.exploded}")
    return Result(f"IPv{addr.version} address", [("Address", "\n".join(lines))], copy=str(addr))


def escapes(t):
    if re.search(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);", t):
        out = html.unescape(t)
        return Result("HTML entities", [("Unescaped", out)], copy=out) if out != t else None
    if re.search(r"\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}|\\n", t):
        out = t.encode("latin-1", "backslashreplace").decode("unicode_escape")
        return Result("Escaped text", [("Unescaped", out)], copy=out)
    return None


def hex_text(t):
    h = re.sub(r"[\s:]|^0x", "", t)
    if len(h) < 8 or len(h) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", h):
        return None
    if len(h) in (32, 40, 64, 128) and printable(bytes.fromhex(h)) is None:
        algo = {32: "MD5", 40: "SHA-1", 64: "SHA-256", 128: "SHA-512"}[len(h)]
        return Result("Hash", [("Looks like", f"a {algo} hash ({len(h) // 2} bytes): one way, nothing to decode")],
                      copy=h.lower())
    return bytes_view(bytes.fromhex(h), "Hex")


def base64_text(t):
    s = re.sub(r"\s+", "", t)
    if len(s) < 8 or not re.fullmatch(r"[A-Za-z0-9+/_-]+={0,2}", s) or (s.isalpha() and s.islower()):
        return None
    data = b64(s)
    if not data or (printable(data) is None and len(s) < 16):  # short words are rarely base64
        return None
    return bytes_view(data, "Base64")


def plain(t):
    data = t.encode()
    n = {"characters": len(t), "words": len(t.split()), "lines": t.count("\n") + 1, "bytes UTF-8": len(data)}
    stats = ", ".join(f"{v} {k[:-1] if v == 1 and k.endswith('s') else k}" for k, v in n.items())
    hashes = "\n".join(f"{name:<7} {hashlib.new(name, data).hexdigest()}" for name in ("md5", "sha1", "sha256"))
    return Result("Text", [("Stats", stats), ("Hashes", hashes)], copy=hashlib.sha256(data).hexdigest())


DECODERS = [jwt, stack_trace, json_text, timestamp, uuid_text, url, url_encoded, color, permissions, number, cron, ip,
            escapes, hex_text, base64_text, plain]


# ---- clipboard (wl-clipboard) and explanations ------------------------------------

def clipboard_get():
    """The clipboard's text, or None (needs wl-paste from wl-clipboard)."""
    try:
        out = subprocess.run(["wl-paste", "--no-newline", "--type", "text"], capture_output=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8", "replace") if out.returncode == 0 else None


def clipboard_set(text):
    """Put text on the clipboard; False when wl-copy is missing or failed."""
    try:
        return subprocess.run(["wl-copy"], input=text.encode(), timeout=3).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def has_clipboard():
    return shutil.which("wl-paste") is not None and shutil.which("wl-copy") is not None


EXPLAIN = ("You are a senior engineer. Explain the stack trace you are given, in plain English, in at most "
           "120 words: what went wrong, where (file and line), and the most likely fix. No preamble, no markdown "
           "headings; short sentences.")


class Explainer:
    """Sends a stack trace for an explanation on its own thread, only when you click
    Explain?. ask(system, text) -> (reply, error), e.g. voice.openrouter with its key."""

    def __init__(self, ask):
        self.ask = ask
        self.results = queue.Queue()
        self.busy = False

    def start(self, trace):
        if not self.busy:
            self.busy = True
            threading.Thread(target=lambda: self.results.put(self.ask(EXPLAIN, trace[:6000])), daemon=True,
                             name="explain").start()

    def poll(self):
        """(explanation, error) once it is back, else None."""
        try:
            reply = self.results.get_nowait()
        except queue.Empty:
            return None
        self.busy = False
        return reply
