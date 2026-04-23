import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vote_tracker.config import load_config  # noqa: E402
from vote_tracker.scraper import fetch_votes  # noqa: E402


DATA_PATH = ROOT / "docs" / "data" / "history.json"


def main():
    config = load_config(ROOT / "config.json")
    rows = fetch_votes(config)
    checked_at = _utc_now()
    candidate_names = _candidate_names(config)
    data = _load_data()

    data["updated_at"] = checked_at
    data["poll_interval_seconds"] = config.get("poll_interval_seconds")
    data["tracked_candidates"] = candidate_names
    data["source"] = {
        "type": config.get("source", {}).get("type"),
        "activity_id": config.get("source", {}).get("activity_id"),
        "group_name": config.get("source", {}).get("group_name"),
        "page_url": config.get("source", {}).get("page_url"),
    }
    data["latest"] = {
        "checked_at": checked_at,
        "rows": sorted(rows, key=lambda row: (-int(row["votes"]), row["name"])),
    }
    data["series"] = _append_points(data.get("series", []), rows, checked_at, candidate_names)

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {DATA_PATH} with {len(rows)} vote rows at {checked_at}")


def _load_data():
    if not DATA_PATH.exists():
        return {
            "updated_at": None,
            "poll_interval_seconds": None,
            "tracked_candidates": [],
            "source": {},
            "latest": {"checked_at": None, "rows": []},
            "series": [],
        }

    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _append_points(series, rows, checked_at, candidate_names):
    by_name = {item.get("name"): item for item in series}
    ordered_names = candidate_names or [row["name"] for row in rows]

    for row in rows:
        item = by_name.setdefault(row["name"], {"name": row["name"], "points": []})
        item["points"].append({"checked_at": checked_at, "votes": int(row["votes"])})

    return [by_name[name] for name in ordered_names if name in by_name]


def _candidate_names(config):
    names = config.get("source", {}).get("candidate_names", [])
    return [str(name).strip() for name in names if str(name).strip()]


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    main()

