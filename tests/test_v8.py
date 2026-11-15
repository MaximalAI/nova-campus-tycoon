"""V8 rules: monopoly counter, competitors in the summary, manager plans, easter eggs."""

import math

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
    state = logic.new_game(seed=8)
    state["money"] = 500_000
    return state


# ------------------------------------------------------------ fixes


def test_monopoly_counter_starts_at_one_of_nine(game):
    m = logic.view(game)["monopoly"]
    assert m["owned"] == 1 and m["total"] == len(CONFIG["shops"])


def test_the_second_shop_costs_three_hundred_euros():
    assert logic.acquisition_cost("rival") == 30_000
    costs = [logic.acquisition_cost(s) for s in logic.SHOP_ORDER[1:]]
    assert costs == sorted(costs)  # every further shop costs more


def test_summary_lists_every_competitor(game):
    state = next_day(game)
    rivals = state["history"][-1]["competitors"]
    assert {r["shop"] for r in rivals} == {s for s in CONFIG["shops"] if s != "cafe"}
    assert all({"name", "icon", "revenue", "served", "zone_open"} <= set(r) for r in rivals)


def test_summary_keeps_the_sales_of_every_shop(game):
    state = next_day(game)
    assert set(state["history"][-1]["by_shop"]) == set(CONFIG["shops"])


def test_manager_plan_counts_the_customers_who_found_it_sold_out(game):
    state, _ = go(game, type="hire_manager", shop="cafe")
    state["stats"]["shops"]["cafe"]["sold"] = {"coffee": 10, "orange_juice": 10, "pastel_de_nata": 10}
    state["stats"]["shops"]["cafe"]["sold_out_products"] = {"coffee": 6}
    state = next_day(state)
    plan = state["manager_proposals"]["cafe"]["plan"]
    buffer = CONFIG["manager"]["sold_out_buffer"]
    m = CONFIG["manager"]  # v13: missed customers count half, capped at 1.5 x the best day
    assert plan["coffee"] == min(math.ceil((10 + 6 * m["missed_weight"]) * buffer), math.ceil(10 * m["max_vs_best_day"]))
    assert plan["coffee"] > plan["orange_juice"]


# ------------------------------------------------------------ Jep


def test_jep_stands_at_a_seeded_spot_every_day(game):
    spot = logic.view(game)["jep"]
    assert [spot["x"], spot["z"]] in CONFIG["easter_eggs"]["jep"]["spots"]
    assert spot == easter_eggs.jep_spot(game["seed"], 1)
    days = {tuple(easter_eggs.jep_spot(game["seed"], d).values()) for d in range(1, 30)}
    assert len(days) > 1  # he moves around


def test_buying_from_jep_costs_money_and_makes_you_high_for_ten_minutes(game):
    money = game["money"]
    state, _ = go(game, t=8.0, type="buy_from_jep")
    price = CONFIG["easter_eggs"]["jep"]["price"]
    assert state["money"] == money - price
    assert state["high_until"] == pytest.approx(8.0 + 10 / 60)
    assert logic.view(state)["today"]["jep"] == price
    with pytest.raises(GameError, match="still flying"):
        go(state, t=8.1, type="buy_from_jep")
    state, _ = go(state, t=8.2, type="buy_from_jep")  # the effect is over
    assert state["money"] == money - 2 * price


def test_jep_wants_cash(game):
    game["money"] = 100
    with pytest.raises(GameError, match="cash"):
        go(game, type="buy_from_jep")


def test_jep_counts_in_the_day_profit(game):
    state, _ = go(game, t=8.0, type="buy_from_jep")
    state = next_day(state)
    s = state["history"][-1]
    assert s["jep"] == CONFIG["easter_eggs"]["jep"]["price"]
    assert s["profit"] == s["revenue"] + s["tips"] - s["purchase_cost"] - s["spending"] - s["jep"] + s["casino"]


# ------------------------------------------------------------ casino


@pytest.mark.parametrize("bet,number,won", [
    ("red", 1, True), ("red", 2, False), ("black", 2, True), ("black", 0, False),
    ("even", 36, True), ("even", 0, False), ("odd", 35, True),
    ("dozen1", 12, True), ("dozen2", 13, True), ("dozen2", 25, False), ("dozen3", 36, True), ("dozen1", 0, False),
])
def test_roulette_rules(bet, number, won):
    assert easter_eggs.wins(bet, number) is won


def test_roulette_pays_one_to_one_and_two_to_one(game):
    state, _ = go(game, type="enter_casino")
    for bet in ("red", "dozen2"):
        money = state["money"]
        state, res = go(state, type="roulette", bet=bet, amount=1_000)
        pays = CONFIG["easter_eggs"]["casino"]["bets"][bet]["pays"]
        assert res["change"] == (1_000 * pays if res["won"] else -1_000)
        assert state["money"] == money + res["change"]
        assert res["won"] == easter_eggs.wins(bet, res["number"])
    assert state["casino"]["spins"] == 2 and state["casino"]["found"]


def test_roulette_is_seeded_and_fair_over_many_spins(game):
    a, _ = go(game, type="roulette", bet="red", amount=1_000)
    b, _ = go(game, type="roulette", bet="red", amount=1_000)
    assert a["money"] == b["money"]  # same game, same spin, same number
    numbers = set()
    state = game
    for _ in range(300):
        state, res = go(state, type="roulette", bet="odd", amount=100)
        numbers.add(res["number"])
    assert numbers <= set(range(37)) and len(numbers) > 30


def test_roulette_limits(game):
    with pytest.raises(GameError, match="Unknown bet"):
        go(game, type="roulette", bet="green", amount=1_000)
    with pytest.raises(GameError):
        go(game, type="roulette", bet="red", amount=CONFIG["easter_eggs"]["casino"]["max_bet"] + 1)
    game["money"] = 500
    with pytest.raises(GameError, match="more than you have"):
        go(game, type="roulette", bet="red", amount=1_000)


def test_old_saves_get_jep_and_the_casino(game):
    for key in ("jep", "high_until"):
        game.pop(key)
    del game["stats"]["jep"], game["stats"]["casino"]
    state = logic.migrate(game)
    assert state["jep"] and state["high_until"] == 0
    view = logic.view(state)
    assert view["casino"] == {"spins": 0, "net": 0}
