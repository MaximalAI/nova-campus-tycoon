"""Selling phase and end of day (product brief sections 6.4, 6.5 and 10)."""

import pytest

import logic
from logic import GameError, Order


def selling_game(orders, inventory=None, balance=10_000, time_left=720):
    """A game in the selling phase with a hand-made queue for the player café."""
    game = logic.new_game(seed=1)
    game.phase = "selling"
    game.balance_cents = balance
    game.queues = {"player_cafe": [Order(i, items) for i, items in enumerate(orders)], "competitor": []}
    game.stats["player_cafe"].time_left = time_left
    if inventory:
        game.shops["player_cafe"].inventory.update(inventory)
    return game


def test_accepting_an_order_sells_items_and_uses_time():
    game = selling_game([["coffee", "pastel_de_nata"]], {"coffee_beans": 5, "frozen_pastel": 5})
    game = logic.accept_next_order(game)
    assert game.balance_cents == 10_000 + 200 + 180
    assert game.stats["player_cafe"].time_left == 720 - 15 - 20
    assert game.shops["player_cafe"].inventory["coffee_beans"] == 4
    assert game.stats["player_cafe"].sold == {"coffee": 1, "pastel_de_nata": 1}
    assert game.stats["player_cafe"].served == 1
    assert game.queues["player_cafe"] == []


def test_out_of_stock_items_are_dropped():
    game = selling_game([["coffee", "orange_juice"]], {"coffee_beans": 1})
    game = logic.accept_next_order(game)
    assert game.balance_cents == 10_200
    assert game.stats["player_cafe"].sold == {"coffee": 1}
    assert game.stats["player_cafe"].time_left == 705


def test_order_with_nothing_in_stock_counts_as_lost():
    game = selling_game([["orange_juice"]])
    game = logic.accept_next_order(game)
    assert game.balance_cents == 10_000
    assert game.stats["player_cafe"].lost == 1


def test_order_is_rejected_when_time_is_too_short():
    game = selling_game([["orange_juice"]], {"oranges": 1}, time_left=20)
    with pytest.raises(GameError):
        logic.accept_next_order(game)
    assert game.balance_cents == 10_000
    assert len(game.queues["player_cafe"]) == 1


def test_accept_with_empty_queue_is_rejected():
    with pytest.raises(GameError):
        logic.accept_next_order(selling_game([]))


def test_end_day_loses_waiting_customers_and_spoils_inventory():
    game = selling_game([["coffee"], ["coffee"]], {"coffee_beans": 3, "oranges": 2})
    game.stats["player_cafe"].ingredient_cost = 3 * 40 + 2 * 60
    game = logic.accept_next_order(game)
    game = logic.end_day(game)
    stats = game.history[-1]["shops"]["player_cafe"]
    assert game.phase == "summary"
    assert stats["served"] == 1
    assert stats["lost"] == 1
    assert stats["revenue"] == 200
    assert stats["spoiled_value"] == 2 * 40 + 2 * 60
    assert stats["profit"] == 200 - 240
    assert all(q == 0 for q in game.shops["player_cafe"].inventory.values())


def test_game_over_when_balance_is_zero_at_end_of_day():
    game = selling_game([], balance=0)
    game = logic.end_day(game)
    assert game.status == "game_over"
    assert game.phase == "finished"
    with pytest.raises(GameError):
        logic.next_day(game)


def test_no_game_over_with_positive_balance():
    game = logic.end_day(selling_game([], balance=1))
    assert game.status == "running"
    assert game.phase == "summary"


def test_next_day_resets_the_day():
    game = logic.end_day(selling_game([["coffee"]], {"coffee_beans": 1}))
    game = logic.next_day(game)
    assert game.day == 2
    assert game.phase == "morning"
    assert game.stats["player_cafe"].revenue == 0
    assert len(game.history) == 1


def test_full_day_with_real_demand():
    game = logic.new_game(seed=42)
    game = logic.buy_ingredients(game, {"coffee_beans": 10, "oranges": 10, "frozen_pastel": 10})
    game = logic.open_shop(game)
    waiting = len(game.queues["player_cafe"])
    while game.queues["player_cafe"]:
        game = logic.accept_next_order(game)
    game = logic.end_day(game)
    summary = game.history[-1]
    player = summary["shops"]["player_cafe"]
    assert player["served"] + player["lost"] == waiting
    assert game.balance_cents == 10_000 - 1_500 + player["revenue"]
    assert summary["profit"] == player["revenue"] - 1_500
    assert 0 <= summary["market_share"] <= 1


def test_bot_serves_its_customers_without_touching_the_balance():
    game = logic.open_shop(logic.new_game(seed=42))
    assert game.queues["competitor"] == []
    served = game.stats["competitor"].served
    assert served == len([o for o in logic.generate_demand(game)["competitor"]])
    assert game.balance_cents == 10_000


def test_employee_serves_automatically():
    game = logic.new_game(seed=42)
    game.balance_cents = 50_000
    game = logic.hire_employee(game, "player_cafe")
    game = logic.buy_ingredients(game, {"coffee_beans": 20, "oranges": 20, "frozen_pastel": 20})
    before = game.balance_cents
    game = logic.open_shop(game)
    assert game.queues["player_cafe"] == []
    assert game.balance_cents == before + game.stats["player_cafe"].revenue
    assert game.stats["player_cafe"].revenue > 0
    with pytest.raises(GameError):
        logic.accept_next_order(game, "player_cafe")


def test_unstaffed_shop_that_player_does_not_serve_loses_all_orders():
    game = logic.new_game(seed=42)
    game.balance_cents = 200_000
    game = logic.hire_employee(game, "player_cafe")
    game = logic.buy_competitor(game)
    game = logic.set_manual_shop(game, "player_cafe")  # competitor has no one
    game = logic.open_shop(game)
    assert game.queues["competitor"] == []
    assert game.stats["competitor"].revenue == 0
    assert game.stats["competitor"].lost == len(logic.generate_demand(game)["competitor"])
