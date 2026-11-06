"""Saving and restarting (product brief sections 3 and 11)."""

import db
import logic


def roundtrip(tmp_path, game):
    path = tmp_path / "game.db"
    conn = db.connect(path)
    game_id = db.save_game(conn, game)
    conn.close()
    conn = db.connect(path)
    loaded = db.load_game(conn, game_id)
    conn.close()
    return loaded


def test_open_selling_day_survives_a_restart(tmp_path):
    game = logic.new_game(seed=42)
    game = logic.buy_ingredients(game, {"coffee_beans": 10, "oranges": 10, "frozen_pastel": 10})
    game = logic.set_prices(game, "player_cafe", {"coffee": 180})
    game = logic.buy_upgrade(game, "player_cafe", "coffee_machine")
    game = logic.open_shop(game)
    game = logic.accept_next_order(game)

    loaded = roundtrip(tmp_path, game)
    loaded.game_id = None
    game.game_id = None
    assert loaded == game


def test_history_and_progression_survive_a_restart(tmp_path):
    game = logic.new_game(seed=3)
    game.balance_cents = 200_000
    game = logic.hire_employee(game, "player_cafe")
    game = logic.buy_competitor(game)
    game = logic.open_shop(game)
    game = logic.end_day(game)
    game = logic.next_day(game)

    loaded = roundtrip(tmp_path, game)
    assert loaded.day == 2
    assert loaded.shops["competitor"].owner == "player"
    assert loaded.shops["player_cafe"].has_employee
    assert loaded.history == game.history
    assert loaded.manual_shop == game.manual_shop


def test_saving_twice_updates_the_same_game(tmp_path):
    conn = db.connect(tmp_path / "game.db")
    game = logic.new_game(seed=1)
    first_id = db.save_game(conn, game)
    game = logic.buy_ingredients(game, {"coffee_beans": 1})
    second_id = db.save_game(conn, game)
    assert first_id == second_id
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    assert db.load_game(conn, first_id).balance_cents == 9_960


def test_no_saved_game():
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    assert db.latest_game_id(conn) is None
    assert db.load_game(conn, 1) is None
