"""Acceptance checks from specs/first-feature.md (Done when 1 to 7)."""

import pytest

import db
import logic
from logic import GameError


def inventory(game):
    return game.shops["player_cafe"].inventory


def test_new_game_starts_with_100_euros_and_empty_inventory():
    game = logic.new_game(seed=1)
    assert game.day == 1
    assert game.balance_cents == 10_000
    assert game.phase == "morning"
    assert game.status == "running"
    assert inventory(game) == {"coffee_beans": 0, "oranges": 0, "frozen_pastel": 0}


def test_1_allowed_purchase():
    game = logic.new_game(seed=1)
    game = logic.buy_ingredients(game, {"coffee_beans": 10, "oranges": 5, "frozen_pastel": 4})
    assert game.balance_cents == 9_100
    assert inventory(game) == {"coffee_beans": 10, "oranges": 5, "frozen_pastel": 4}


def test_2_repeated_purchases_add_up():
    game = logic.new_game(seed=1)
    game = logic.buy_ingredients(game, {"coffee_beans": 10})
    game = logic.buy_ingredients(game, {"coffee_beans": 10})
    assert inventory(game)["coffee_beans"] == 20
    assert game.balance_cents == 9_200


def test_3_spending_the_exact_balance_is_allowed():
    game = logic.new_game(seed=1)
    game = logic.buy_ingredients(game, {"coffee_beans": 250})
    assert game.balance_cents == 0


def test_4_too_expensive_is_rejected_and_nothing_changes():
    game = logic.new_game(seed=1)
    with pytest.raises(GameError):
        logic.buy_ingredients(game, {"oranges": 200})
    assert game.balance_cents == 10_000
    assert sum(inventory(game).values()) == 0


@pytest.mark.parametrize(
    "quantities",
    [
        {"coffee_beans": -1},
        {"coffee_beans": 0, "oranges": 0, "frozen_pastel": 0},
        {},
        {"coffee_beans": 1.5},
        {"coffee_beans": True},
    ],
)
def test_5_invalid_quantities_are_rejected(quantities):
    game = logic.new_game(seed=1)
    with pytest.raises(GameError):
        logic.buy_ingredients(game, quantities)
    assert game.balance_cents == 10_000
    assert sum(inventory(game).values()) == 0


def test_6_purchase_outside_the_morning_is_rejected():
    game = logic.open_shop(logic.new_game(seed=1))
    assert game.phase == "selling"
    before = game.balance_cents
    with pytest.raises(GameError):
        logic.buy_ingredients(game, {"coffee_beans": 1})
    assert game.balance_cents == before


def test_7_purchase_survives_a_restart(tmp_path):
    path = tmp_path / "game.db"
    conn = db.connect(path)
    game = logic.buy_ingredients(
        logic.new_game(seed=1), {"coffee_beans": 10, "oranges": 5, "frozen_pastel": 4}
    )
    game_id = db.save_game(conn, game)
    conn.close()

    conn = db.connect(path)
    assert db.latest_game_id(conn) == game_id
    loaded = db.load_game(conn, game_id)
    conn.close()
    assert loaded.balance_cents == 9_100
    assert inventory(loaded) == {"coffee_beans": 10, "oranges": 5, "frozen_pastel": 4}


def test_rejected_purchase_does_not_change_the_database(tmp_path):
    path = tmp_path / "game.db"
    conn = db.connect(path)
    game = logic.new_game(seed=1)
    game_id = db.save_game(conn, game)
    with pytest.raises(GameError):
        game = logic.buy_ingredients(game, {"oranges": 200})
    db.save_game(conn, game)
    loaded = db.load_game(conn, game_id)
    assert loaded.balance_cents == 10_000
    assert sum(inventory(loaded).values()) == 0
