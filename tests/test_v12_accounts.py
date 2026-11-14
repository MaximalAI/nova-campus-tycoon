"""V12: accounts with e-mail and password, one account per address, saves per player."""

from datetime import UTC, datetime, timedelta

import pytest

import auth
import db
import logic


@pytest.fixture()
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    yield c
    c.close()


# ------------------------------------------------------------ passwords


def test_passwords_are_stored_as_salted_hashes():
    stored = auth.hash_password("campus-coffee")
    assert "campus-coffee" not in stored and stored.startswith("pbkdf2_sha256$")
    assert auth.verify_password("campus-coffee", stored)
    assert not auth.verify_password("campus-cofee", stored)
    assert auth.hash_password("campus-coffee") != stored  # a new salt every time


def test_broken_hashes_never_log_in():
    assert not auth.verify_password("x", "nonsense")
    assert not auth.verify_password("x", "md5$1$00$00")


@pytest.mark.parametrize("email", ["", "maxi", "maxi@", "@nova.pt", "maxi@nova", "ma xi@nova.pt"])
def test_invalid_email_addresses_are_rejected(email):
    with pytest.raises(auth.AuthError, match="valid e-mail"):
        auth.check_email(email)


def test_short_passwords_are_rejected():
    with pytest.raises(auth.AuthError, match="at least 8"):
        auth.check_password("1234567")
    assert auth.check_password("12345678") == "12345678"


# ------------------------------------------------------------ accounts


def test_one_account_per_email_address(conn):
    db.create_user(conn, "maxi@novasbe.pt", "secret-123")
    with pytest.raises(auth.AuthError, match="already an account"):
        db.create_user(conn, "maxi@novasbe.pt", "other-pass-1")
    with pytest.raises(auth.AuthError, match="already an account"):
        db.create_user(conn, "  Maxi@NovaSBE.pt ", "other-pass-1")  # case and spaces do not count
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_login_needs_the_right_password(conn):
    uid = db.create_user(conn, "maxi@novasbe.pt", "secret-123")
    assert db.check_login(conn, "MAXI@novasbe.pt", "secret-123") == uid
    with pytest.raises(auth.AuthError, match="Wrong e-mail address or password"):
        db.check_login(conn, "maxi@novasbe.pt", "secret-124")
    with pytest.raises(auth.AuthError, match="Wrong e-mail address or password"):
        db.check_login(conn, "nobody@novasbe.pt", "secret-123")


def test_the_database_keeps_no_password_and_no_token(conn):
    uid = db.create_user(conn, "maxi@novasbe.pt", "secret-123")
    token = db.create_session(conn, uid)
    dump = "\n".join(conn.iterdump())
    assert "secret-123" not in dump and token not in dump


def test_a_kept_login_works_until_logout(conn):
    uid = db.create_user(conn, "maxi@novasbe.pt", "secret-123")
    token = db.create_session(conn, uid)
    assert db.session_user(conn, token) == uid
    assert db.session_user(conn, "made-up-token") is None
    db.end_session(conn, token)
    assert db.session_user(conn, token) is None


def test_an_expired_login_does_not_work(conn):
    uid = db.create_user(conn, "maxi@novasbe.pt", "secret-123")
    token = db.create_session(conn, uid)
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    with conn:
        conn.execute("UPDATE sessions SET expires_at=?", (past,))
    assert db.session_user(conn, token) is None


# ------------------------------------------------------------ saves per player


def test_every_player_continues_his_own_game(conn):
    a = db.create_user(conn, "a@novasbe.pt", "secret-123")
    b = db.create_user(conn, "b@novasbe.pt", "secret-123")
    game_a = db.save_game(conn, logic.new_game(seed=1), user_id=a)
    assert db.latest_game_id(conn, b) is None  # b has no game, a's is not offered to him
    game_b = db.save_game(conn, logic.new_game(seed=2), user_id=b)
    assert db.latest_game_id(conn, a) == game_a and db.latest_game_id(conn, b) == game_b
    assert db.game_owner(conn, game_a) == a


def test_a_new_game_only_replaces_your_own(conn):
    a = db.create_user(conn, "a@novasbe.pt", "secret-123")
    b = db.create_user(conn, "b@novasbe.pt", "secret-123")
    db.save_game(conn, logic.new_game(seed=1), user_id=a)
    game_b = db.save_game(conn, logic.new_game(seed=2), user_id=b)
    db.abandon_running(conn, a)
    assert db.latest_game_id(conn, a) is None
    assert db.latest_game_id(conn, b) == game_b


def test_the_first_account_keeps_the_games_saved_before_accounts(conn):
    old = db.save_game(conn, logic.new_game(seed=3))  # no account (before v12)
    first = db.create_user(conn, "maxi@novasbe.pt", "secret-123")
    second = db.create_user(conn, "marvin@novasbe.pt", "secret-123")
    assert db.latest_game_id(conn, first) == old
    assert db.latest_game_id(conn, second) is None


def test_an_old_database_gets_the_account_column(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    c = sqlite3.connect(path)
    c.executescript("CREATE TABLE saves (id INTEGER PRIMARY KEY AUTOINCREMENT, day INTEGER NOT NULL, money INTEGER NOT NULL,"
                    " reputation INTEGER NOT NULL, status TEXT NOT NULL, state_json TEXT NOT NULL,"
                    " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);")
    c.close()
    conn = db.connect(path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(saves)")}
    assert {"user_id", "backup_json"} <= cols
    conn.close()
