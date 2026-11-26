"""Customer clocks: the time where the people you work with are, under the Focus switch.
A sun or a moon says if it is day there, and the time is dimmed outside their working
hours (Monday to Friday, 8 am to 6 pm), so you can tell at a glance whether to ping them.
Under them, the zones developers watch: UTC (logs) and the popular AWS regions, which
never look asleep. Those fold away with the toggle at the bottom of the card.

The list is state.json's "clocks" ([{"name", "tz", "place"?, "group"?}], IANA time
zones; a "group" makes it a cloud zone): Costa Rica, Argentina and Colombia first by default."""

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CLOUD = "Cloud · AWS"
DEFAULT_CLOCKS = [{"name": "Costa Rica", "tz": "America/Costa_Rica"},
                  {"name": "Argentina", "tz": "America/Argentina/Buenos_Aires"},
                  {"name": "Colombia", "tz": "America/Bogota"},
                  {"name": "UTC", "tz": "UTC", "place": "logs", "group": CLOUD},
                  {"name": "us-east-1", "tz": "America/New_York", "place": "Virginia", "group": CLOUD},
                  {"name": "us-east-2", "tz": "America/New_York", "place": "Ohio", "group": CLOUD},
                  {"name": "us-west-2", "tz": "America/Los_Angeles", "place": "Oregon", "group": CLOUD},
                  {"name": "eu-west-1", "tz": "Europe/Dublin", "place": "Ireland", "group": CLOUD},
                  {"name": "eu-central-1", "tz": "Europe/Berlin", "place": "Frankfurt", "group": CLOUD},
                  {"name": "ap-south-1", "tz": "Asia/Kolkata", "place": "Mumbai", "group": CLOUD},
                  {"name": "ap-southeast-1", "tz": "Asia/Singapore", "place": "Singapore", "group": CLOUD},
                  {"name": "sa-east-1", "tz": "America/Sao_Paulo", "place": "São Paulo", "group": CLOUD}]
WORK_HOURS = (8, 18)
DAYLIGHT = (6, 18)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class Clocks:
    def __init__(self, store, now=_now, local=None):
        self.store, self.now, self.local = store, now, local  # local: your time zone (None: the system's)

    def zones(self):
        out = []
        for c in self.store.get("clocks") or DEFAULT_CLOCKS:
            try:
                out.append((c, ZoneInfo(c["tz"])))
            except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
                continue  # a typo in state.json: skip that clock, keep the rest
        return out

    @property
    def expanded(self):
        return self.store.get("clocks_expanded", True)

    def toggle(self):
        """Fold the cloud zones away (or show them again); remembered."""
        self.store.set("clocks_expanded", not self.expanded)

    def payload(self):
        """What the card draws: {rows, expanded, hidden (cloud zones folded away)}."""
        rows = self.rows()
        shown = rows if self.expanded else [r for r in rows if not r["group"]]
        return {"rows": shown, "expanded": self.expanded, "hidden": len(rows) - len(shown)}

    def rows(self):
        """[{name, place, group, time "9:05 am", diff "+3h" from you ("" when the same), day,
        working (None for cloud zones: servers don't sleep)}]; they only change once a minute."""
        now = self.now().replace(second=0, microsecond=0)
        mine = now.astimezone(self.local).utcoffset() if self.local else now.astimezone().utcoffset()
        rows = []
        for clock, zone in self.zones():
            there = now.astimezone(zone)
            hours = (there.utcoffset() - mine).total_seconds() / 3600
            diff = "" if not hours else f"{'+' if hours > 0 else '−'}{abs(hours):g}h"
            hour12 = there.hour % 12 or 12
            group = clock.get("group")
            working = there.weekday() < 5 and WORK_HOURS[0] <= there.hour < WORK_HOURS[1]
            rows.append({"name": clock["name"], "place": clock.get("place", ""), "group": group,
                         "time": f"{hour12}:{there.minute:02d} {'am' if there.hour < 12 else 'pm'}",
                         "diff": diff, "day": DAYLIGHT[0] <= there.hour < DAYLIGHT[1],
                         "working": None if group else working})
        return rows
