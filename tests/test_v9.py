"""V9 rules: casino bar and slot machines, the wholesaler sells every base product."""

import pytest

import easter_eggs
import logic
from config import CONFIG
from logic import GameError


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def next_day(state):
    state, _ = go(state, 21.0, type="tick")
    state, _ = go(state, 21.0, type="next_day")
    return state


@pytest.fixture
def game():
    state = logic.new_game(seed=9)
    state["money"] = 500_000
    return state


# ------------------------------------------------------------ wholesaler


def test_every_base_product_of_every_shop_is_sold_at_the_wholesaler():
    items = CONFIG["wholesale_items"]
    for shop, spec in CONFIG["shops"].items():
        for product in spec["products"]:
            for item in CONFIG["products"][product]["uses"]:
                assert item in items, (shop, product, item)


def test_the_vending_products_are_sold_once_you_own_snackbots(game):
    for item in ("water", "coke_zero", "protein_bars"):
        assert not logic.item_available(game, item)
    game["shops"]["snackbots"]["owner"] = "player"
    for item in ("water", "coke_zero", "protein_bars"):
        assert logic.item_available(game, item)
        assert item in logic.view(game)["items_available"]


# ------------------------------------------------------------ bar


def test_a_drink_costs_money_and_makes_you_tipsy_for_ten_minutes(game):
    money = game["money"]
    state, _ = go(game, t=9.0, type="buy_drink", drink="beer")
    price = CONFIG["easter_eggs"]["casino"]["bar"]["drinks"]["beer"]["price"]
    assert state["money"] == money - price
    assert state["drunk_until"] == pytest.approx(9.0 + 10 / 60)
    assert logic.view(state)["drunk_until"] == state["drunk_until"]
    assert logic.view(state)["today"]["bar"] == price
    with pytest.raises(GameError, match="enough"):
        go(state, t=9.1, type="buy_drink", drink="caipirinha")
    state, _ = go(state, t=9.2, type="buy_drink", drink="caipirinha")  # sober again
    assert state["stats"]["bar"] == price + CONFIG["easter_eggs"]["casino"]["bar"]["drinks"]["caipirinha"]["price"]


def test_the_bar_wants_cash_and_known_drinks(game):
    with pytest.raises(GameError, match="know"):
        go(game, type="buy_drink", drink="absinth")
    game["money"] = 100
    with pytest.raises(GameError, match="Cash"):
        go(game, type="buy_drink", drink="beer")


def test_bar_money_counts_in_the_day_profit(game):
    state, _ = go(game, t=9.0, type="buy_drink", drink="port")
    state = next_day(state)
    s = state["history"][-1]
    assert s["bar"] == CONFIG["easter_eggs"]["casino"]["bar"]["drinks"]["port"]["price"]
    assert s["profit"] == (s["revenue"] + s["tips"] - s["purchase_cost"] - s["spending"] - s["jep"]
                           + s["casino"] - s["bar"])


# ------------------------------------------------------------ slot machines


@pytest.mark.parametrize("reels,pays", [
    (["seven", "seven", "seven"], 100), (["cherry", "cherry", "cherry"], 5), (["star", "star", "star"], 40),
    (["cherry", "cherry", "lemon"], 1), (["cherry", "lemon", "cherry"], 1), (["lemon", "lemon", "bell"], 0),
    (["cherry", "bell", "star"], 0),
])
def test_slot_payouts(reels, pays):
    assert easter_eggs.slot_payout(reels) == pays


def test_the_house_wins_in_the_long_run_but_not_by_much():
    assert 0.8 < easter_eggs.slot_return_rate() < 0.95


def test_a_pull_changes_the_money_by_the_payout(game):
    state = game
    for _ in range(40):
        money = state["money"]
        state, res = go(state, type="slot", machine="slot2", amount=500)
        assert res["change"] == 500 * res["pays"] - 500
        assert res["pays"] == easter_eggs.slot_payout(res["reels"])
        assert state["money"] == money + res["change"]
        assert len(res["icons"]) == 3
    assert state["casino"]["pulls"] == 40
    assert state["stats"]["casino"] == state["casino"]["net"]


def test_pulls_are_seeded(game):
    _, ra = go(game, type="slot", machine="slot1", amount=100)
    _, rb = go(game, type="slot", machine="slot3", amount=100)
    assert ra["reels"] == rb["reels"]  # same game, same day, same pull number


def test_slot_limits(game):
    with pytest.raises(GameError, match="Unknown slot"):
        go(game, type="slot", machine="slot9", amount=100)
    with pytest.raises(GameError, match="coins"):
        go(game, type="slot", machine="slot1", amount=300)
    game["money"] = 50
    with pytest.raises(GameError, match="more than you have"):
        go(game, type="slot", machine="slot1", amount=100)


def test_old_saves_get_the_bar_fields(game):
    game.pop("drunk_until")
    del game["stats"]["bar"]
    state = logic.migrate(game)
    assert state["drunk_until"] == 0 and state["stats"]["bar"] == 0
