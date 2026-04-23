import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from vote_tracker.config import load_config
from vote_tracker.scraper import ScrapeError, fetch_votes
from vote_tracker.storage import VoteStore


ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"


class AppState:
    def __init__(self, config):
        self.config = config
        self.candidate_names = _configured_candidate_names(config)
        self.store = VoteStore(ROOT / config["database_path"])
        self.lock = threading.Lock()
        self.last_check = None
        self.last_error = None

    def run_check(self):
        with self.lock:
            try:
                rows = fetch_votes(self.config)
                snapshot_id = self.store.add_snapshot(rows)
                self.last_check = {
                    "ok": True,
                    "snapshot_id": snapshot_id,
                    "row_count": len(rows),
                    "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                self.last_error = None
            except ScrapeError as exc:
                self.last_check = {
                    "ok": False,
                    "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                self.last_error = str(exc)
            return self.last_check


def create_handler(state):
    class VoteTrackerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_file(STATIC_DIR / "index.html")
            elif parsed.path == "/api/status":
                self._send_json(
                    {
                        "source_type": state.config.get("source", {}).get("type"),
                        "poll_interval_seconds": state.config.get("poll_interval_seconds"),
                        "tracked_candidates": state.candidate_names,
                        "database_path": str(state.store.database_path),
                        "snapshot_count": state.store.snapshot_count(),
                        "last_check": state.last_check,
                        "last_error": state.last_error,
                    }
                )
            elif parsed.path == "/api/latest":
                self._send_json(_filter_latest(state.store.latest(), state.candidate_names))
            elif parsed.path == "/api/history":
                query = parse_qs(parsed.query)
                candidate = query.get("candidate", [None])[0]
                series = state.store.history(candidate)
                self._send_json({"series": _filter_history(series, state.candidate_names)})
            elif parsed.path.startswith("/static/"):
                target = STATIC_DIR / parsed.path.removeprefix("/static/")
                self._send_file(target)
            else:
                self._send_json({"error": "Not found"}, status=404)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/check":
                result = state.run_check()
                self._send_json(result, status=200 if result.get("ok") else 500)
            else:
                self._send_json({"error": "Not found"}, status=404)

        def log_message(self, format, *args):
            print("%s - %s" % (self.address_string(), format % args))

        def _send_json(self, payload, status=200):
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_file(self, path):
            if not path.exists() or not path.is_file():
                self._send_json({"error": "File not found"}, status=404)
                return

            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            content = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return VoteTrackerHandler


def _configured_candidate_names(config):
    names = config.get("source", {}).get("candidate_names", [])
    return [str(name).strip() for name in names if str(name).strip()]


def _filter_latest(payload, candidate_names):
    if not candidate_names:
        return payload
    allowed = set(candidate_names)
    return {
        **payload,
        "rows": [row for row in payload.get("rows", []) if row.get("name") in allowed],
    }


def _filter_history(series, candidate_names):
    if not candidate_names:
        return series
    allowed = set(candidate_names)
    return [item for item in series if item.get("name") in allowed]


def start_scheduler(state):
    def loop():
        state.run_check()
        while True:
            time.sleep(int(state.config.get("poll_interval_seconds", 300)))
            state.run_check()

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


def main():
    config = load_config(ROOT / "config.json")
    state = AppState(config)
    start_scheduler(state)

    host = config.get("host", "127.0.0.1")
    port = int(config.get("port", 8765))
    server = ThreadingHTTPServer((host, port), create_handler(state))
    print(f"Vote Tracker running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
