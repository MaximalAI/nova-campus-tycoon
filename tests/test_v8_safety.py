"""v8: saves survive crashes - full sync, a backup of the previous state, recovery."""

import json
import sqlite3

import db
import logic


def test_the_database_writes_safely(tmp_path):
    conn = db.connect(tmp_path / "game.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL


def test_a_damaged_save_falls_back_to_the_state_before(tmp_path):
    conn = db.connect(tmp_path / "game.db")
    state = logic.new_game(seed=1)
    gid = db.save_game(conn, state)
    state["money"] = 1234
    db.save_game(conn, state, gid)
    with conn:  # a crash in the middle of writing would leave something like this
        conn.execute("UPDATE saves SET state_json=? WHERE id=?", ('{"day": 1, "shop', gid))
    loaded = db.load_game(conn, gid)
    assert loaded is not None and loaded["money"] == logic.CONFIG["start_money"]  # the backup


def test_a_damaged_database_file_is_moved_aside(tmp_path):
    path = tmp_path / "game.db"
    path.write_bytes(b"this is not a database" * 100)
    conn = db.connect(path)
    gid = db.save_game(conn, logic.new_game(seed=2))
    assert db.load_game(conn, gid)["day"] == 1
    assert (tmp_path / "game.damaged").exists()


def test_old_databases_get_the_backup_column(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(db.SCHEMA)
    with old:
        old.execute("INSERT INTO saves (day, money, reputation, status, state_json) VALUES (1, 5000, 50, 'running', ?)",
                    (json.dumps(logic.new_game(seed=3)),))
    old.close()
    conn = db.connect(path)
    assert db.load_game(conn, 1)["day"] == 1


def test_autosave_keeps_the_game_time():
    state = logic.new_game(seed=4)
    state, res = logic.apply(state, {"type": "autosave", "t": 6.5})
    assert res == {} and state["time"] == 6.5
