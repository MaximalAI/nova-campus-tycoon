"""SQLite storage for Nova Campus Tycoon.

One row per saved game. Key values are columns (easy to query), the full
game state is stored as JSON. No game rules here.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(os.environ.get("NCT_DB_PATH", "data/game.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS saves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day INTEGER NOT NULL,
    money INTEGER NOT NULL,
    reputation INTEGER NOT NULL,
    status TEXT NOT NULL,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open the database. v8 safety: write-ahead log and full sync, so a crash, a closed
    browser or an empty laptop battery never leaves a half-written save behind. A damaged
    database file is moved aside and a fresh one is started."""
    path = Path(path or os.environ.get("NCT_DB_PATH", DEFAULT_DB_PATH))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    try:
        ok = conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.DatabaseError:
        ok = False
    if not ok:
        conn.close()
        path.rename(path.with_suffix(".damaged"))
        conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.executescript(SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(saves)")}
    if "backup_json" not in cols:  # v8: the previous good state of every save
        with conn:
            conn.execute("ALTER TABLE saves ADD COLUMN backup_json TEXT")
    return conn


def save_game(conn: sqlite3.Connection, state: dict, game_id: int | None = None) -> int:
    """Save in one transaction; the state before this save stays as a backup (v8)."""
    values = (state["day"], state["money"], round(state["reputation"]), state["status"], json.dumps(state))
    with conn:
        if game_id is None:
            cur = conn.execute(
                "INSERT INTO saves (day, money, reputation, status, state_json) VALUES (?, ?, ?, ?, ?)", values
            )
            return cur.lastrowid
        conn.execute(
            "UPDATE saves SET backup_json=state_json, day=?, money=?, reputation=?, status=?, state_json=?,"
            " updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*values, game_id),
        )
    return game_id


def _parse(text: str | None) -> dict | None:
    try:
        state = json.loads(text) if text else None
    except (TypeError, ValueError):
        return None
    return state if isinstance(state, dict) and "day" in state and "shops" in state else None


def load_game(conn: sqlite3.Connection, game_id: int) -> dict | None:
    """The saved state; if it cannot be read, the backup of the save before (v8)."""
    cols = [row[1] for row in conn.execute("PRAGMA table_info(saves)")]
    backup = ", backup_json" if "backup_json" in cols else ", NULL"
    row = conn.execute(f"SELECT state_json{backup} FROM saves WHERE id=?", (game_id,)).fetchone()
    if not row:
        return None
    return _parse(row[0]) or _parse(row[1])


def abandon_running(conn: sqlite3.Connection) -> None:
    """Starting over: running games are no longer offered for "Continue"."""
    with conn:
        conn.execute("UPDATE saves SET status='abandoned', updated_at=CURRENT_TIMESTAMP WHERE status='running'")


def latest_game_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM saves WHERE status='running' ORDER BY updated_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None
