import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS vote_counts (
    snapshot_id INTEGER NOT NULL,
    candidate TEXT NOT NULL,
    votes INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, candidate),
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vote_counts_candidate ON vote_counts(candidate);
CREATE INDEX IF NOT EXISTS idx_snapshots_checked_at ON snapshots(checked_at);
"""


class VoteStore:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def add_snapshot(self, rows):
        with self._connect() as connection:
            cursor = connection.execute("INSERT INTO snapshots DEFAULT VALUES")
            snapshot_id = cursor.lastrowid
            connection.executemany(
                """
                INSERT INTO vote_counts (snapshot_id, candidate, votes)
                VALUES (?, ?, ?)
                """,
                [(snapshot_id, row["name"], int(row["votes"])) for row in rows],
            )

        return snapshot_id

    def latest(self):
        with self._connect() as connection:
            snapshot = connection.execute(
                "SELECT id, checked_at FROM snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()

            if snapshot is None:
                return {"checked_at": None, "rows": []}

            rows = connection.execute(
                """
                SELECT candidate AS name, votes
                FROM vote_counts
                WHERE snapshot_id = ?
                ORDER BY votes DESC, candidate ASC
                """,
                (snapshot["id"],),
            ).fetchall()

        return {
            "checked_at": snapshot["checked_at"],
            "rows": [dict(row) for row in rows],
        }

    def history(self, candidate=None):
        params = []
        candidate_filter = ""

        if candidate:
            candidate_filter = "WHERE vc.candidate = ?"
            params.append(candidate)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT s.checked_at, vc.candidate AS name, vc.votes
                FROM snapshots s
                JOIN vote_counts vc ON vc.snapshot_id = s.id
                {candidate_filter}
                ORDER BY s.checked_at ASC, vc.candidate ASC
                """,
                params,
            ).fetchall()

        series = {}
        for row in rows:
            series.setdefault(row["name"], []).append(
                {"checked_at": row["checked_at"], "votes": row["votes"]}
            )

        return [{"name": name, "points": points} for name, points in series.items()]

    def snapshot_count(self):
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM snapshots").fetchone()
        return row["total"]
