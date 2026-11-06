"""Morning rules and invalid actions (product brief sections 6.1, 7, 9 and 12)."""

import pytest

import logic
from logic import GameError


@pytest.fixture
def game():
    return logic.new_game(seed=7)


def rich(game, cents=200_000):
    """A copy of the game with more money, to test progression rules."""
    game.balance_cents = cents
    return game


# Prices -------------------------------------------------------------------


def test_set_prices(game):
    game = logic.set_prices(game, "player_cafe", {"coffee": 220, "orange_juice": 300})
    assert game.shops["player_cafe"].prices["coffee"] == 220
    assert game.shops["player_cafe"].prices["orange_juice"] == 300


@pytest.mark.parametrize("price", [0, -10, 1_001, 2.5])
def test_invalid_prices_are_rejected(game, price):
    with pytest.raises(GameError):
        logic.set_prices(game, "player_cafe", {"coffee": price})
    assert game.shops["player_cafe"].prices["coffee"] == 200


def test_price_of_ten_euros_is_allowed(game):
    game = logic.set_prices(game, "player_cafe", {"coffee": 1_000})
    assert game.shops["player_cafe"].prices["coffee"] == 1_000


def test_cannot_set_prices_of_the_bot_competitor(game):
    with pytest.raises(GameError):
        logic.set_prices(game, "competitor", {"coffee": 100})


def test_cannot_set_price_for_product_not_sold(game):
    with pytest.raises(GameError):
        logic.set_prices(game, "player_cafe", {"tea": 100})


# Upgrades -----------------------------------------------------------------


def test_upgrade_raises_shop_factor_and_costs_money(game):
    game = logic.buy_upgrade(game, "player_cafe", "coffee_machine")
    assert game.balance_cents == 4_000
    assert logic.shop_factor(game.shops["player_cafe"]) == pytest.approx(1.15)


def test_all_three_upgrades_stack(game):
    game = rich(game)
    for upgrade in ["coffee_machine", "seating", "branding"]:
        game = logic.buy_upgrade(game, "player_cafe", upgrade)
    assert logic.shop_factor(game.shops["player_cafe"]) == pytest.approx(1.6)
    assert game.balance_cents == 200_000 - 38_000


def test_same_upgrade_twice_is_rejected(game):
    game = logic.buy_upgrade(game, "player_cafe", "coffee_machine")
    with pytest.raises(GameError):
        logic.buy_upgrade(game, "player_cafe", "coffee_machine")


def test_upgrade_without_enough_money_is_rejected(game):
    with pytest.raises(GameError):
        logic.buy_upgrade(game, "player_cafe", "seating")
    assert game.balance_cents == 10_000
    assert game.shops["player_cafe"].upgrades == []


# Employee and acquisition -------------------------------------------------


def test_hire_employee(game):
    game = logic.hire_employee(rich(game), "player_cafe")
    assert game.shops["player_cafe"].has_employee
    assert game.balance_cents == 180_000
    assert game.manual_shop is None


def test_hire_employee_without_money_is_rejected(game):
    with pytest.raises(GameError):
        logic.hire_employee(game, "player_cafe")
    assert not game.shops["player_cafe"].has_employee


def test_second_employee_in_same_shop_is_rejected(game):
    game = logic.hire_employee(rich(game), "player_cafe")
    with pytest.raises(GameError):
        logic.hire_employee(game, "player_cafe")


def test_buy_competitor_requires_employee_in_own_cafe(game):
    with pytest.raises(GameError):
        logic.buy_competitor(rich(game))


def test_buy_competitor(game):
    game = logic.hire_employee(rich(game), "player_cafe")
    game = logic.buy_competitor(game)
    assert game.shops["competitor"].owner == "player"
    assert game.balance_cents == 200_000 - 20_000 - 50_000
    assert game.manual_shop == "competitor"
    assert game.status == "running"


def test_buy_competitor_twice_is_rejected(game):
    game = logic.buy_competitor(logic.hire_employee(rich(game), "player_cafe"))
    with pytest.raises(GameError):
        logic.buy_competitor(game)


def test_buy_competitor_without_money_is_rejected(game):
    game = logic.hire_employee(rich(game, 60_000), "player_cafe")  # 40_000 left
    with pytest.raises(GameError):
        logic.buy_competitor(game)
    assert game.shops["competitor"].owner == "bot"


def test_competitor_ingredients_only_after_acquisition(game):
    with pytest.raises(GameError):
        logic.buy_ingredients(game, {"tea_leaves": 5}, shop_id="competitor")
    with pytest.raises(GameError):
        logic.buy_ingredients(game, {"tea_leaves": 5}, shop_id="player_cafe")
    game = logic.buy_competitor(logic.hire_employee(rich(game), "player_cafe"))
    game = logic.buy_ingredients(
        game, {"tea_leaves": 5, "frozen_croissants": 2, "coffee_beans": 1}, shop_id="competitor"
    )
    assert game.shops["competitor"].inventory == {
        "coffee_beans": 1, "tea_leaves": 5, "frozen_croissants": 2,
    }
    assert game.shops["player_cafe"].inventory["coffee_beans"] == 0


def test_victory_when_both_shops_owned_and_staffed(game):
    game = logic.buy_competitor(logic.hire_employee(rich(game), "player_cafe"))
    game = logic.hire_employee(game, "competitor")
    assert game.status == "victory"
    assert game.phase == "finished"


def test_no_action_after_victory(game):
    game = logic.buy_competitor(logic.hire_employee(rich(game), "player_cafe"))
    game = logic.hire_employee(game, "competitor")
    with pytest.raises(GameError):
        logic.buy_ingredients(game, {"coffee_beans": 1})
    with pytest.raises(GameError):
        logic.open_shop(game)


# Phase rules --------------------------------------------------------------


def test_planning_actions_are_rejected_while_selling(game):
    game = logic.open_shop(game)
    with pytest.raises(GameError):
        logic.set_prices(game, "player_cafe", {"coffee": 100})
    with pytest.raises(GameError):
        logic.buy_upgrade(game, "player_cafe", "coffee_machine")
    with pytest.raises(GameError):
        logic.hire_employee(rich(game), "player_cafe")


def test_selling_actions_are_rejected_in_the_morning(game):
    with pytest.raises(GameError):
        logic.accept_next_order(game)
    with pytest.raises(GameError):
        logic.end_day(game)


def test_set_manual_shop_only_for_own_shops(game):
    with pytest.raises(GameError):
        logic.set_manual_shop(game, "competitor")
