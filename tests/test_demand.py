"""Student demand model (product brief section 6.3)."""

import itertools

import pytest

import logic

PLAYER = [("player_cafe", "coffee"), ("player_cafe", "orange_juice"), ("player_cafe", "pastel_de_nata")]
COMP = [("competitor", "coffee"), ("competitor", "tea"), ("competitor", "croissant")]
PAIRS = PLAYER + COMP
FACTORS = {"player_cafe": 1.0, "competitor": 1.2}


def flat(value):
    return {pair: value for pair in PAIRS}


def test_buys_nothing_when_every_price_is_above_its_utility():
    utilities = flat(100.0)
    prices = {pair: 500 for pair in PAIRS}
    assert logic.best_bundle(utilities, prices, {"player_cafe": 1.0, "competitor": 1.0}, 1_000) == []


def test_buys_a_product_when_utility_exceeds_price():
    utilities = flat(50.0)
    utilities[("player_cafe", "orange_juice")] = 300.0
    prices = {pair: 200 for pair in PAIRS}
    bundle = logic.best_bundle(utilities, prices, FACTORS, 1_000)
    assert bundle == [("player_cafe", "orange_juice")]


def test_shop_factor_can_tip_the_decision():
    utilities = flat(50.0)
    utilities[("competitor", "tea")] = 180.0  # 180 * 1.2 = 216 > 200
    prices = {pair: 200 for pair in PAIRS}
    assert logic.best_bundle(utilities, prices, FACTORS, 1_000) == [("competitor", "tea")]
    no_bonus = {"player_cafe": 1.0, "competitor": 1.0}
    assert logic.best_bundle(utilities, prices, no_bonus, 1_000) == []


def test_at_most_one_coffee():
    utilities = flat(50.0)
    utilities[("player_cafe", "coffee")] = 400.0
    utilities[("competitor", "coffee")] = 380.0
    prices = {pair: 100 for pair in PAIRS}
    bundle = logic.best_bundle(utilities, prices, FACTORS, 1_000)
    coffees = [p for p in bundle if p[1] == "coffee"]
    assert len(coffees) == 1
    assert coffees == [("competitor", "coffee")]  # 380 * 1.2 = 456 > 400


def test_budget_constraint_is_respected():
    utilities = flat(400.0)
    prices = {pair: 400 for pair in PAIRS}
    # Each item gives surplus but only 2 fit into €10.00.
    bundle = logic.best_bundle(utilities, prices, {"player_cafe": 1.5, "competitor": 1.5}, 1_000)
    assert len(bundle) == 2
    assert sum(prices[p] for p in bundle) <= 1_000


def test_bundle_matches_full_enumeration():
    """Brute force check against an independent enumeration of all 64 bundles."""
    utilities = logic.draw_utilities(seed=3, day=1)[0]
    prices = {
        ("player_cafe", "coffee"): 150, ("player_cafe", "orange_juice"): 220,
        ("player_cafe", "pastel_de_nata"): 160, ("competitor", "coffee"): 200,
        ("competitor", "tea"): 180, ("competitor", "croissant"): 220,
    }
    best_value = 1_000.0
    for mask in itertools.product([0, 1], repeat=6):
        bundle = [p for p, m in zip(PAIRS, mask) if m]
        if sum(1 for p in bundle if p[1] == "coffee") > 1:
            continue
        spent = sum(prices[p] for p in bundle)
        if spent > 1_000:
            continue
        value = sum(FACTORS[s] * utilities[(s, q)] for s, q in bundle) + 1_000 - spent
        best_value = max(best_value, value)
    chosen = logic.best_bundle(utilities, prices, FACTORS, 1_000)
    chosen_value = (
        sum(FACTORS[s] * utilities[(s, q)] for s, q in chosen) + 1_000 - sum(prices[p] for p in chosen)
    )
    assert chosen_value == pytest.approx(best_value)


def test_utilities_are_in_range_and_change_every_day():
    day1 = logic.draw_utilities(seed=5, day=1)
    day2 = logic.draw_utilities(seed=5, day=2)
    assert len(day1) == 10
    assert all(50 <= u <= 400 for student in day1 for u in student.values())
    assert day1 != day2
    assert logic.draw_utilities(seed=5, day=1) == day1  # reproducible


def test_generate_demand_is_reproducible_and_each_student_appears_at_most_once_per_shop():
    game = logic.new_game(seed=11)
    q1 = logic.generate_demand(game)
    q2 = logic.generate_demand(game)
    assert [(o.student, o.items) for o in q1["player_cafe"]] == [
        (o.student, o.items) for o in q2["player_cafe"]
    ]
    for shop in ["player_cafe", "competitor"]:
        students = [o.student for o in q1[shop]]
        assert len(students) == len(set(students))
