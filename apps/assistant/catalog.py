import json
import re
from functools import cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "destinations.json"


class DestinationCatalog:
    def __init__(self, destinations, aliases):
        self.destinations = destinations
        self.aliases = aliases

    @classmethod
    def from_file(cls, path=DATA_FILE):
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(payload["destinations"], payload["aliases"])

    def get(self, name):
        key = (name or "").strip().lower()
        return self.destinations.get(self.aliases.get(key, key))

    def keys(self):
        return [*self.destinations, *self.aliases]

    def find_in_text(self, text, exclude=None):
        excluded = (exclude or "").lower()
        for key in self.keys():
            if key == excluded:
                continue
            if re.search(r"\b%s\b" % re.escape(key), text):
                return self.get(key)["name"]
        return None

    def of_type(self, trip_type):
        matches = [
            data for data in self.destinations.values() if data["type"] == trip_type
        ]
        return matches or list(self.destinations.values())


@cache
def destination_catalog():
    return DestinationCatalog.from_file()
