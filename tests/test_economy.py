"""Planning, wholesaler, stock and shelf life (brief sections 6 and 9)."""

import pytest

import logic
from logic import GameError


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


@pytest.fixture
def game():
    return logic.new_game(seed=1)


def test_new_game(game):
    assert game["day"] == 1 and game["time"] == 5.0
    assert game["money"] == 5_000
    assert game["day_state"] == logic.MORNING_PLANNING
    assert game["shops"]["cafe"]["prices"] == {"coffee": 90, "orange_juice": 250, "pastel_de_nata": 130}


def test_shopping_list_in_wholesale_units(game):
    state, res = go(game, type="confirm_plan", plan={"coffee": 30, "orange_juice": 5, "pastel_de_nata": 12})
    # 30 coffee -> 2 packs of 25, 5 juices -> 15 oranges -> 3 nets of 6, 12 nata -> 12 pieces
    assert res["shopping_list"] == {"coffee_beans": 2, "oranges": 3, "nata": 12}
    assert state["day_state"] == logic.WALK_TO_WHOLESALE
    assert res["toast"].startswith("Shopping list ready")


def test_shopping_list_subtracts_usable_stock(game):
    game["shops"]["cafe"]["stock"] = [{"item": "coffee_beans", "units": 20, "age": 3}]
    state, res = go(game, type="confirm_plan", plan={"coffee": 30, "orange_juice": 0, "pastel_de_nata": 0})
    assert res["shopping_list"] == {"coffee_beans": 1}


def test_invalid_plan_is_rejected(game):
    with pytest.raises(GameError):
        go(game, type="confirm_plan", plan={"coffee": -1})
    with pytest.raises(GameError):
        go(game, type="confirm_plan", plan={"tea": 3})


def shop_at_wholesaler(game, cart):
    state, _ = go(game, type="enter_wholesaler")
    for item, qty in cart.items():
        state, _ = go(state, type="set_cart_item", item=item, qty=qty)
    return state


def test_cart_starts_empty_and_the_shopping_list_is_only_a_reference(game):
    # v5: the player takes every product from its stand himself
    state, _ = go(game, type="confirm_plan", plan={"coffee": 10, "orange_juice": 2, "pastel_de_nata": 4})
    state, _ = go(state, type="enter_wholesaler")
    assert state["cart"] == {}
    assert state["shopping_list"] == {"coffee_beans": 1, "oranges": 1, "nata": 4}
    state, _ = go(state, type="set_cart_item", item="nata", qty=6)  # more than on the list is fine
    state, _ = go(state, type="set_cart_item", item="coffee_beans", qty=1)
    assert state["cart"] == {"nata": 6, "coffee_beans": 1}


def test_pay_moves_cart_into_bag(game):
    state = shop_at_wholesaler(game, {"coffee_beans": 1, "nata": 10})
    state, res = go(state, type="pay")
    assert state["money"] == 5_000 - 400 - 600
    assert state["bag"] == {"coffee_beans": 1, "nata": 10}
    assert state["cart"] == {}
    assert res["toast"] == "Purchase paid: €10.00"
    assert state["day_state"] == logic.WALK_TO_CAFE


def test_cart_above_balance_blocks_payment(game):
    state = shop_at_wholesaler(game, {"coffee_beans": 13})  # 52 €
    with pytest.raises(GameError, match="Not enough money"):
        go(state, type="pay")
    assert state["money"] == 5_000


def test_unpaid_cart_blocks_the_exit(game):
    state = shop_at_wholesaler(game, {"oranges": 1})
    with pytest.raises(GameError, match="unpaid goods"):
        go(state, type="leave_wholesaler")
    state, _ = go(state, type="set_cart_item", item="oranges", qty=0)
    state, _ = go(state, type="leave_wholesaler")
    assert not state["in_wholesaler"]


def test_competitor_items_only_after_acquisition(game):
    state, _ = go(game, type="enter_wholesaler")
    with pytest.raises(GameError):
        go(state, type="set_cart_item", item="tea_leaves", qty=1)


def test_stocking_converts_to_base_units(game):
    state = shop_at_wholesaler(game, {"coffee_beans": 1, "oranges": 2, "nata": 3})
    state, _ = go(state, type="pay")
    state, res = go(state, type="stock_goods", shop="cafe")
    stock = {b["item"]: b["units"] for b in state["shops"]["cafe"]["stock"]}
    assert stock == {"coffee_beans": 25, "oranges": 12, "nata": 3}
    assert state["bag"] == {}
    assert state["day_state"] == logic.SET_PRICES


def test_set_prices_rules(game):
    state, _ = go(game, type="set_prices", shop="cafe", prices={"coffee": 120})
    assert state["shops"]["cafe"]["prices"]["coffee"] == 120
    for bad in (0, 1_010, 125, 1.5):
        with pytest.raises(GameError):
            go(game, type="set_prices", shop="cafe", prices={"coffee": bad})
    with pytest.raises(GameError):
        go(game, type="set_prices", shop="rival", prices={"coffee": 50})


def test_prices_cannot_change_while_open(game):
    state, _ = go(game, t=8.0, type="tick")
    assert state["open"]
    with pytest.raises(GameError):
        go(state, t=9.0, type="set_prices", shop="cafe", prices={"coffee": 100})


def test_open_rules(game):
    with pytest.raises(GameError):
        go(game, t=6.5, type="open_shop")
    state, res = go(game, t=7.2, type="open_shop")
    assert state["open"] and res["toast"].startswith("Open")


def test_cafe_opens_automatically_at_8(game):
    state, res = go(game, t=8.0, type="tick")
    assert state["open"] and res["opened"]


def test_shelf_life_per_batch(game):
    game["shops"]["cafe"]["stock"] = [
        {"item": "coffee_beans", "units": 10, "age": 0},
        {"item": "oranges", "units": 6, "age": 0},
        {"item": "oranges", "units": 6, "age": 2},
        {"item": "nata", "units": 4, "age": 0},
    ]
    state, _ = go(game, t=21.0, type="tick")
    summary = state["summary"]
    left = sorted((b["item"], b["units"], b["age"]) for b in state["shops"]["cafe"]["stock"])
    assert left == [("coffee_beans", 10, 1), ("oranges", 6, 1)]
    assert summary["spoiled"] == {"oranges": 6, "nata": 4}
    assert summary["spoiled_value"] == 200 + 4 * 60


def test_oranges_last_three_days(game):
    game["shops"]["cafe"]["stock"] = [{"item": "oranges", "units": 6, "age": 0}]
    state = game
    for day in range(3):
        state, _ = go(state, t=21.0, type="tick")
        if day < 2:
            assert state["shops"]["cafe"]["stock"], day
            state, _ = go(state, t=21.0, type="next_day")
    assert state["shops"]["cafe"]["stock"] == []


def test_ingredients_are_used_oldest_first(game):
    game["shops"]["cafe"]["stock"] = [{"item": "oranges", "units": 2, "age": 0},
                                      {"item": "oranges", "units": 2, "age": 2}]
    logic._consume(game, "cafe", "orange_juice")
    assert game["shops"]["cafe"]["stock"] == [{"item": "oranges", "units": 1, "age": 0}]


def test_euro_format():
    assert logic.euro(3450) == "€34.50"
    assert logic.euro(-90) == "-€0.90"


def test_second_visit_does_not_refill_the_cart(game):
    state, _ = go(game, type="confirm_plan", plan={"coffee": 10, "orange_juice": 0, "pastel_de_nata": 0})
    state, _ = go(state, type="enter_wholesaler")
    state, _ = go(state, type="set_cart_item", item="coffee_beans", qty=1)
    state, _ = go(state, type="pay")
    state, _ = go(state, type="leave_wholesaler")
    state, _ = go(state, type="enter_wholesaler")
    assert state["cart"] == {}
