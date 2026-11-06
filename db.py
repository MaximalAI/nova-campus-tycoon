"""SQLite storage for Nova Campus Tycoon v2.

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
    path = Path(path or os.environ.get("NCT_DB_PATH", DEFAULT_DB_PATH))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def save_game(conn: sqlite3.Connection, state: dict, game_id: int | None = None) -> int:
    values = (state["day"], state["money"], round(state["reputation"]), state["status"], json.dumps(state))
    with conn:
        if game_id is None:
            cur = conn.execute(
                "INSERT INTO saves (day, money, reputation, status, state_json) VALUES (?, ?, ?, ?, ?)", values
            )
            return cur.lastrowid
        conn.execute(
            "UPDATE saves SET day=?, money=?, reputation=?, status=?, state_json=?,"
            " updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*values, game_id),
        )
    return game_id


def load_game(conn: sqlite3.Connection, game_id: int) -> dict | None:
    row = conn.execute("SELECT state_json FROM saves WHERE id=?", (game_id,)).fetchone()
    return json.loads(row[0]) if row else None


def latest_game_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM saves WHERE status='running' ORDER BY updated_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None
