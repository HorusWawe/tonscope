from __future__ import annotations

import json
import os
from pathlib import Path

from tonscope.integrations.public_checker import DEFAULT_API


def data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif os.name == "posix" and os.environ.get("XDG_CONFIG_HOME"):
        root = Path(os.environ["XDG_CONFIG_HOME"])
    else:
        root = Path.home() / ".config"
    path = root / "TONSCOPE"
    path.mkdir(parents=True, exist_ok=True)
    return path


class AppConfig:
    def __init__(self):
        self.path = data_dir() / "config.json"
        self.values = {
            "api_url": DEFAULT_API,
            "requests_per_minute": 20,
            "min_score": 5,
            "profile": "default",
        }
        self.load()

    def load(self) -> dict:
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.values.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass
        return self.values

    def save(self) -> None:
        self.path.write_text(json.dumps(self.values, ensure_ascii=False, indent=2), encoding="utf-8")
