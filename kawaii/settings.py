"""state.json: what she remembers between runs (per-monitor layouts, open panels, choices)."""

import json


class StateStore:
    def __init__(self, path):
        self.path = path
        try:
            self.data = json.loads(path.read_text())
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("layouts", {})  # per monitor name: margin, model_size, left, scale, offset

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def layout_for(self, output_name):
        return self.data["layouts"].get(output_name) if output_name else None

    def remember_layout(self, output_name, layout):
        """Store and save right away, so a crash or kill never loses it."""
        self.data["layouts"][output_name] = layout
        self.data["output"] = output_name
        self.save()

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1))
        except OSError:
            pass
