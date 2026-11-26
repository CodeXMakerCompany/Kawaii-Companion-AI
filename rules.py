"""Business Rules: a company name and the rules written for it, a plain text list for now
(the start of a little RAG: later these get searched and handed to the AI as context).

Saved as {"companies": [{"name", "rules": [{"text", "added"}]}]}.
"""

import datetime
import json
import sys
from pathlib import Path


class Rulebook:
    def __init__(self, path):
        self.path = Path(path)
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        self.companies = list(saved.get("companies", []))

    def find(self, name):
        name = " ".join(name.split()).lower()
        return next((i for i, c in enumerate(self.companies) if c["name"].lower() == name), None)

    def add_company(self, name):
        """Index of the company called `name` (added if new), or None for a blank name."""
        name = " ".join(name.split())
        if not name:
            return None
        index = self.find(name)
        if index is None:
            self.companies.append({"name": name, "rules": []})
            self.save()
            index = len(self.companies) - 1
        return index

    def remove_company(self, index):
        if 0 <= index < len(self.companies):
            del self.companies[index]
            self.save()

    def add_rule(self, company, text):
        text = text.strip()
        if not text or not 0 <= company < len(self.companies):
            return False
        self.companies[company]["rules"].append({"text": text, "added": datetime.date.today().isoformat()})
        self.save()
        return True

    def remove_rule(self, company, index):
        rules = self.companies[company]["rules"] if 0 <= company < len(self.companies) else []
        if 0 <= index < len(rules):
            del rules[index]
            self.save()

    def as_text(self, company):
        """The company's rules as a numbered list, to paste into a prompt."""
        c = self.companies[company]
        return "\n".join([f"{c['name']} business rules:"] +
                         [f"{n}. {r['text']}" for n, r in enumerate(c["rules"], 1)])

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"companies": self.companies}, indent=1, ensure_ascii=False),
                                 encoding="utf-8")
        except OSError as e:
            print(f"rules: cannot save {self.path}: {e}", file=sys.stderr)
