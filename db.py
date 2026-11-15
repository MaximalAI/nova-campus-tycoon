"""SQLite storage for Nova Campus Tycoon.

One row per saved game. Key values are columns (easy to query), the full
game state is stored as JSON. No game rules here.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import auth

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
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL
);
"""


# v14: the full check (PRAGMA quick_check reads the whole file) and the schema update run
# once per database file and process, not on every request: the server answered slower
# the more games were saved.
_READY: set[str] = set()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open the database. v8 safety: write-ahead log and full sync, so a crash, a closed
    browser or an empty laptop battery never leaves a half-written save behind. A damaged
    database file is moved aside and a fresh one is started."""
    path = Path(path or os.environ.get("NCT_DB_PATH", DEFAULT_DB_PATH))
    if str(path) in _READY and path.exists():  # v14: checked and migrated already in this process
        conn = sqlite3.connect(path, timeout=10)
        conn.execute("PRAGMA synchronous=FULL")
        return conn
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
    if "user_id" not in cols:  # v12: every save belongs to an account
        with conn:
            conn.execute("ALTER TABLE saves ADD COLUMN user_id INTEGER")
    _READY.add(str(path))
    return conn


def save_game(conn: sqlite3.Connection, state: dict, game_id: int | None = None, user_id: int | None = None) -> int:
    """Save in one transaction; the state before this save stays as a backup (v8).
    A new save belongs to the account user_id (v12)."""
    values = (state["day"], state["money"], round(state["reputation"]), state["status"], json.dumps(state))
    with conn:
        if game_id is None:
            cur = conn.execute(
                "INSERT INTO saves (day, money, reputation, status, state_json, user_id) VALUES (?, ?, ?, ?, ?, ?)",
                (*values, user_id),
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


def _owner(user_id: int | None) -> tuple[str, tuple]:
    """v12: saves of one account (user_id None: saves without an account, from before v12)."""
    return ("user_id IS NULL", ()) if user_id is None else ("user_id=?", (user_id,))


def abandon_running(conn: sqlite3.Connection, user_id: int | None = None) -> None:
    """Starting over: this player's running games are no longer offered for "Continue"."""
    where, args = _owner(user_id)
    with conn:
        conn.execute(f"UPDATE saves SET status='abandoned', updated_at=CURRENT_TIMESTAMP WHERE status='running' AND {where}", args)


def latest_game_id(conn: sqlite3.Connection, user_id: int | None = None) -> int | None:
    where, args = _owner(user_id)
    row = conn.execute(
        f"SELECT id FROM saves WHERE status='running' AND {where} ORDER BY updated_at DESC, id DESC LIMIT 1", args
    ).fetchone()
    return row[0] if row else None


def game_owner(conn: sqlite3.Connection, game_id: int) -> int | None:
    row = conn.execute("SELECT user_id FROM saves WHERE id=?", (game_id,)).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------- v12 accounts


def create_user(conn: sqlite3.Connection, email: str, password: str) -> int:
    """A new account. One account per e-mail address (the column is UNIQUE, case does not matter)."""
    email = auth.check_email(email)
    password = auth.check_password(password)
    try:
        with conn:
            first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            uid = conn.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)",
                               (email, auth.hash_password(password))).lastrowid
            if first:  # the first account on this database keeps the games saved before accounts existed
                conn.execute("UPDATE saves SET user_id=? WHERE user_id IS NULL", (uid,))
    except sqlite3.IntegrityError:
        raise auth.AuthError("There is already an account with this e-mail address. Please log in.") from None
    return uid


def check_login(conn: sqlite3.Connection, email: str, password: str) -> int:
    row = conn.execute("SELECT id, password_hash FROM users WHERE email=?", (auth.normalize_email(email),)).fetchone()
    if not row or not auth.verify_password(password, row[1]):
        raise auth.AuthError("Wrong e-mail address or password.")
    return row[0]


def user_email(conn: sqlite3.Connection, user_id: int) -> str | None:
    row = conn.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
    return row[0] if row else None


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    """A login that the browser keeps (as a token) for SESSION_DAYS days."""
    token = auth.new_token()
    expires = (datetime.now(UTC) + timedelta(days=auth.SESSION_DAYS)).isoformat()
    with conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(UTC).isoformat(),))
        conn.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                     (auth.token_hash(token), user_id, expires))
    return token


def session_user(conn: sqlite3.Connection, token: str) -> int | None:
    row = conn.execute("SELECT user_id, expires_at FROM sessions WHERE token_hash=?", (auth.token_hash(token),)).fetchone()
    if not row or row[1] < datetime.now(UTC).isoformat():
        return None
    return row[0]


def end_session(conn: sqlite3.Connection, token: str) -> None:
    with conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (auth.token_hash(token),))
