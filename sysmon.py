"""System monitor for the overlay: CPU, memory, GPU, temperatures, disk, network, load,
the busiest process and wireless peripheral batteries, read straight from /proc and
/sys every couple of seconds (no extra packages), plus developer-minded alarms.

An alarm fires when its condition has held for a while (so a compile spike does not
nag), and stays until it clears or is dismissed; a dismissed alarm stays quiet for
SNOOZE seconds and comes back if the problem is still there.
"""

import os
import time
from pathlib import Path

SNOOZE = 15 * 60
PAGE = os.sysconf("SC_PAGE_SIZE")
CLK = os.sysconf("SC_CLK_TCK")

# name: (warn at, alarm at, held for seconds). Percent unless the name says otherwise.
LIMITS = {
    "cpu": (75, 90, 30),
    "mem": (80, 90, 10),
    "swap": (25, 50, 30),
    "disk": (85, 92, 0),
    "vram": (85, 95, 20),
    "cpu_temp": (80, 90, 10),  # °C
    "gpu_temp": (85, 100, 10),  # °C, junction (hotspot)
    "nvme_temp": (60, 70, 30),  # °C
    "load": (1.0, 2.0, 60),  # load average per core
    "battery": (25, 10, 0),  # % left: lower is worse
}


def _read(path, default=None):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def _num(path, scale=1.0):
    v = _read(path)
    try:
        return float(v) / scale
    except (TypeError, ValueError):
        return None


def _gb(nbytes):
    return f"{nbytes / 2**30:.1f}"


def _rate(bps):
    for unit, size in (("GB/s", 2**30), ("MB/s", 2**20), ("KB/s", 2**10)):
        if bps >= size:
            return f"{bps / size:.1f} {unit}"
    return f"{bps:.0f} B/s"


class SystemMonitor:
    INTERVAL = 2.0

    def __init__(self):
        self.next_at = 0.0
        self.cores = os.cpu_count() or 1
        self.prev_cpu = self._cpu_times()
        self.prev_net = self._net_bytes()
        self.prev_procs = self._proc_times()
        self.prev_t = self.prev_procs_t = time.monotonic()
        self.samples = 0
        self.held = {}  # alarm name -> since when its condition holds
        self.snoozed = {}  # alarm name -> quiet until
        self.data = {}
        self.alarms = []  # [(name, message)] currently firing and not snoozed

        # The discrete GPU is the amdgpu card with the most VRAM; find its sensors once.
        self.gpu = None
        best = 0
        for card in Path("/sys/class/drm").glob("card[0-9]"):
            dev = card / "device"
            vram = _num(dev / "mem_info_vram_total") or 0
            if vram > best:
                best, self.gpu = vram, dev
        self.gpu_hwmon = next(iter(sorted(self.gpu.glob("hwmon/hwmon*"))), None) if self.gpu else None
        self.cpu_hwmon = self.nvme_hwmon = None
        for h in Path("/sys/class/hwmon").glob("hwmon*"):
            name = _read(h / "name", "")
            if name in ("k10temp", "coretemp", "zenpower") and not self.cpu_hwmon:
                self.cpu_hwmon = h
            elif name == "nvme" and not self.nvme_hwmon:
                self.nvme_hwmon = h
        self.batteries = [p for p in Path("/sys/class/power_supply").glob("*")
                          if _read(p / "scope", "") == "Device" or p.name.startswith("hidpp_battery")]

    # ---- raw readings -------------------------------------------------------
    @staticmethod
    def _cpu_times():
        parts = _read("/proc/stat", "cpu 0").splitlines()[0].split()[1:]
        vals = [int(v) for v in parts]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return sum(vals), idle

    @staticmethod
    def _net_bytes():
        rx = tx = 0
        for line in (_read("/proc/net/dev", "") or "").splitlines()[2:]:
            name, rest = line.split(":", 1)
            if name.strip() == "lo":
                continue
            f = rest.split()
            rx, tx = rx + int(f[0]), tx + int(f[8])
        return rx, tx

    @staticmethod
    def _proc_times():
        out = {}
        for d in os.scandir("/proc"):
            if not d.name.isdigit():
                continue
            try:
                with open(f"/proc/{d.name}/stat", "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            r = raw.rfind(b")")
            fields = raw[r + 2:].split()
            # utime, stime are fields 14/15 (1-based); rss pages is field 24
            out[int(d.name)] = (raw[raw.find(b"(") + 1:r].decode(errors="replace"),
                                int(fields[11]) + int(fields[12]), int(fields[21]))
        return out

    @staticmethod
    def _meminfo():
        info = {}
        for line in (_read("/proc/meminfo", "") or "").splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
        return info

    def _battery(self, p):
        cap = _num(p / "capacity")
        if cap is not None:
            return cap, f"{cap:.0f}%"
        level = _read(p / "capacity_level", "")
        approx = {"Full": 100, "High": 75, "Normal": 50, "Low": 15, "Critical": 5}.get(level)
        return approx, level or "?"

    # ---- sampling -----------------------------------------------------------
    def due(self, now):
        return now >= self.next_at

    def sample(self, now, detail=False):
        """Take a reading. The process scan (the costly part) runs every 5th sample, or
        every time while the panel is open (`detail`) or CPU/memory are running high."""
        self.next_at = now + self.INTERVAL
        self.samples += 1
        t = time.monotonic()
        dt = max(1e-3, t - self.prev_t)
        self.prev_t = t
        d = {}

        total, idle = self._cpu_times()
        pt, pi = self.prev_cpu
        self.prev_cpu = (total, idle)
        d["cpu"] = 100.0 * (1 - (idle - pi) / max(1, total - pt))

        m = self._meminfo()
        d["mem_total"], d["mem_used"] = m.get("MemTotal", 1), m.get("MemTotal", 1) - m.get("MemAvailable", 0)
        d["mem"] = 100.0 * d["mem_used"] / d["mem_total"]
        d["swap_total"] = m.get("SwapTotal", 0)
        d["swap_used"] = d["swap_total"] - m.get("SwapFree", 0)
        d["swap"] = 100.0 * d["swap_used"] / d["swap_total"] if d["swap_total"] else 0.0

        if self.gpu:
            d["gpu"] = _num(self.gpu / "gpu_busy_percent")
            d["vram_used"] = _num(self.gpu / "mem_info_vram_used") or 0
            d["vram_total"] = _num(self.gpu / "mem_info_vram_total") or 1
            d["vram"] = 100.0 * d["vram_used"] / d["vram_total"]
        if self.gpu_hwmon:
            d["gpu_edge"] = _num(self.gpu_hwmon / "temp1_input", 1000)
            d["gpu_temp"] = _num(self.gpu_hwmon / "temp2_input", 1000) or d["gpu_edge"]  # junction if present
            d["gpu_power"] = _num(self.gpu_hwmon / "power1_average", 1e6) or _num(self.gpu_hwmon / "power1_input", 1e6)
        if self.cpu_hwmon:
            d["cpu_temp"] = _num(self.cpu_hwmon / "temp1_input", 1000)
        if self.nvme_hwmon:
            d["nvme_temp"] = _num(self.nvme_hwmon / "temp1_input", 1000)

        st = os.statvfs("/")
        d["disk_total"] = st.f_blocks * st.f_frsize
        d["disk_used"] = d["disk_total"] - st.f_bavail * st.f_frsize
        d["disk"] = 100.0 * d["disk_used"] / max(1, d["disk_total"])

        rx, tx = self._net_bytes()
        prx, ptx = self.prev_net
        self.prev_net = (rx, tx)
        d["rx"], d["tx"] = max(0, rx - prx) / dt, max(0, tx - ptx) / dt

        d["loadavg"] = os.getloadavg()
        d["load"] = d["loadavg"][0] / self.cores

        busy = d["cpu"] >= LIMITS["cpu"][1] or d["mem"] >= LIMITS["mem"][1]  # alarm level: name the culprit
        if detail or busy or self.samples % 5 == 0 or "top" not in self.data:
            procs = self._proc_times()
            pdt = max(1e-3, t - self.prev_procs_t)
            best = None
            for pid, (name, ticks, rss) in procs.items():
                prev = self.prev_procs.get(pid)
                if prev and prev[0] == name:
                    share = 100.0 * (ticks - prev[1]) / CLK / pdt
                    if best is None or share > best[1]:
                        best = (name, share, rss * PAGE)
            self.prev_procs, self.prev_procs_t = procs, t
            d["top"] = best
        else:
            d["top"] = self.data.get("top")

        d["batteries"] = []
        for p in self.batteries:
            pct, text = self._battery(p)
            name = _read(p / "model_name", p.name)
            d["batteries"].append((name, pct, text, _read(p / "status", "")))

        self.data = d
        self._update_alarms(t)
        return True

    # ---- alarms ---------------------------------------------------------------
    def level(self, name, value):
        if value is None:
            return "ok"
        warn, alarm, _ = LIMITS[name]
        if name == "battery":  # lower is worse
            return "alarm" if value <= alarm else "warn" if value <= warn else "ok"
        return "alarm" if value >= alarm else "warn" if value >= warn else "ok"

    def _update_alarms(self, t):
        d = self.data
        top = d.get("top")
        top_txt = f" (top: {top[0]})" if top else ""
        checks = {
            "cpu": (d["cpu"], f"CPU at {d['cpu']:.0f}% for a while{top_txt}"),
            "mem": (d["mem"], f"Memory almost full: {_gb(d['mem_used'])} / {_gb(d['mem_total'])} GB{top_txt}"),
            "swap": (d["swap"] if d["swap_total"] else None,
                     f"Swapping hard: {_gb(d['swap_used'])} / {_gb(d['swap_total'])} GB swap used"),
            "disk": (d["disk"], f"Disk / is {d['disk']:.0f}% full ({_gb(d['disk_total'] - d['disk_used'])} GB left)"),
            "vram": (d.get("vram"), f"VRAM almost full: {_gb(d.get('vram_used', 0))} / {_gb(d.get('vram_total', 1))} GB"),
            "cpu_temp": (d.get("cpu_temp"), f"CPU is hot: {d.get('cpu_temp') or 0:.0f}°C"),
            "gpu_temp": (d.get("gpu_temp"), f"GPU hotspot is hot: {d.get('gpu_temp') or 0:.0f}°C"),
            "nvme_temp": (d.get("nvme_temp"), f"SSD is hot: {d.get('nvme_temp') or 0:.0f}°C"),
            "load": (d["load"], f"Load {d['loadavg'][0]:.1f} on {self.cores} cores for a minute{top_txt}"),
        }
        for name, pct, text, status in d["batteries"]:
            if status != "Charging":
                checks[f"battery:{name}"] = (pct, f"{name} battery low: {text}")

        alarms = []
        for key, (value, message) in checks.items():
            kind = key.split(":")[0]
            if self.level(kind, value) == "alarm":
                self.held.setdefault(key, t)
                if t - self.held[key] >= LIMITS[kind][2] and t >= self.snoozed.get(key, 0):
                    alarms.append((key, message))
            else:
                self.held.pop(key, None)
        self.alarms = alarms

    def snooze(self, name):
        self.snoozed[name] = time.monotonic() + SNOOZE
        self.alarms = [a for a in self.alarms if a[0] != name]

    # ---- for the UI -------------------------------------------------------------
    def view(self, opened):
        """The pill and (when opened) panel rows for ui.Overlay._monitor."""
        d = self.data
        if not d:
            return None
        lv = self.level
        gpu = d.get("gpu")
        pill = [("CPU", f"{d['cpu']:.0f}%"), ("GPU", f"{gpu:.0f}%" if gpu is not None else "–"),
                ("RAM", f"{d['mem']:.0f}%")]
        rows = []
        temp = f" · {d['cpu_temp']:.0f}°C" if d.get("cpu_temp") else ""
        rows.append(("CPU", f"{d['cpu']:.0f}%{temp}", d["cpu"] / 100,
                     max(lv("cpu", d["cpu"]), lv("cpu_temp", d.get("cpu_temp")), key=_rank)))
        rows.append(("Memory", f"{_gb(d['mem_used'])} / {_gb(d['mem_total'])} GB", d["mem"] / 100, lv("mem", d["mem"])))
        if d["swap_total"]:
            rows.append(("Swap", f"{_gb(d['swap_used'])} / {_gb(d['swap_total'])} GB", d["swap"] / 100,
                         lv("swap", d["swap"])))
        if gpu is not None:
            extra = "".join([f" · {d['gpu_edge']:.0f}°C" if d.get("gpu_edge") else "",
                             f" · {d['gpu_power']:.0f} W" if d.get("gpu_power") else ""])
            rows.append(("GPU", f"{gpu:.0f}%{extra}", gpu / 100, lv("gpu_temp", d.get("gpu_temp"))))
            rows.append(("VRAM", f"{_gb(d['vram_used'])} / {_gb(d['vram_total'])} GB", d["vram"] / 100,
                         lv("vram", d["vram"])))
        disk_txt = f"{d['disk']:.0f}% · {_gb(d['disk_total'] - d['disk_used'])} GB free"
        if d.get("nvme_temp"):
            disk_txt += f" · {d['nvme_temp']:.0f}°C"
        rows.append(("Disk /", disk_txt, d["disk"] / 100,
                     max(lv("disk", d["disk"]), lv("nvme_temp", d.get("nvme_temp")), key=_rank)))
        rows.append(("Network", f"rx {_rate(d['rx'])} · tx {_rate(d['tx'])}", None, "ok"))
        la = d["loadavg"]
        rows.append(("Load", f"{la[0]:.1f} {la[1]:.1f} {la[2]:.1f} ({self.cores} cores)", min(1.0, d["load"] / 2),
                     lv("load", d["load"])))
        for name, pct, text, status in d["batteries"]:
            noise = {"Wireless", "Mouse", "Keyboard", "Gaming", "Mechanical", "RGB", "LIGHTSPEED"}
            short = " ".join(w for w in name.split() if w not in noise)[:20] or name[:20]
            rows.append((short, text + (" · charging" if status == "Charging" else ""),
                         pct / 100 if pct is not None else None,
                         "ok" if status == "Charging" else lv("battery", pct)))
        top = d.get("top")
        levels = [r[3] for r in rows]
        level = "alarm" if self.alarms else "warn" if "warn" in levels or "alarm" in levels else "ok"
        return {"open": opened, "level": level, "pill": pill, "rows": rows,
                "top": f"{top[0]}  {top[1]:.0f}% CPU · {_gb(top[2])} GB" if top else None}


def _rank(level):
    return {"ok": 0, "warn": 1, "alarm": 2}[level]
