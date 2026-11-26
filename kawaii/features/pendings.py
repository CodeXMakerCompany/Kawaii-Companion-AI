"""Today's pending list, saved as JSON."""

import datetime
import json


class Pendings:
    """Today's pending list, saved as JSON. Unfinished items carry over to a new day."""

    def __init__(self, path):
        self.path = path
        self.date = None
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        self.items = [
            {"text": str(i["text"]), "done": bool(i.get("done"))}
            for i in data.get("items", []) if isinstance(i, dict) and i.get("text")
        ]
        self.date = data.get("date")
        self.roll_day()

    def roll_day(self):
        today = datetime.date.today().isoformat()
        if self.date != today:
            self.items = [i for i in self.items if not i["done"]]
            self.date = today
            self.save()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"date": self.date, "items": self.items}, ensure_ascii=False, indent=1))
        except OSError:
            pass

    @property
    def open_count(self):
        return sum(not i["done"] for i in self.items)

    def add(self, text):
        self.items.append({"text": text, "done": False})
        self.save()

    def toggle(self, index):
        self.items[index]["done"] = not self.items[index]["done"]
        self.save()

    def remove(self, index):
        del self.items[index]
        self.save()
