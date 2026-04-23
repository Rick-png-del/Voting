import json
from pathlib import Path


DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8765,
    "database_path": "data/votes.sqlite3",
    "poll_interval_seconds": 300,
    "source": {
        "type": "sample",
        "url": "",
        "headers": {"User-Agent": "Mozilla/5.0"},
        "regex": {
            "item_pattern": r"<tr>\s*<td class=\"name\">(?P<name>.*?)</td>\s*<td class=\"votes\">(?P<votes>[\d,]+)</td>\s*</tr>"
        },
    },
}


def load_config(path="config.json"):
    config_path = Path(path)
    if not config_path.exists():
        return DEFAULT_CONFIG.copy()

    with config_path.open("r", encoding="utf-8") as file:
        user_config = json.load(file)

    return _deep_merge(DEFAULT_CONFIG.copy(), user_config)


def _deep_merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base

