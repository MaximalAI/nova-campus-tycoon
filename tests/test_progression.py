"""Upgrades, manager, acquisition, victory, bot and manager serving (brief 8.4 and 9.3)."""

import pytest

import logic
import students as st
from logic import GameError


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


@pytest.fixture
def rich():
    state = logic.new_game(seed=2)
    state["money"] = 200_000
    return state


def test_upgrade_raises_factor(rich):
    state, _ = go(rich, type="buy_upgrade", shop="cafe", upgrade="coffee_machine")
    assert logic.shop_factor(state, "cafe") == pytest.approx(1.15 * state["rep_factor"])
    with pytest.raises(GameError):
        go(state, type="buy_upgrade", shop="cafe", upgrade="coffee_machine")


def test_upgrade_needs_money():
    with pytest.raises(GameError, match="Not enough money"):
        go(logic.new_game(seed=1), type="buy_upgrade", shop="cafe", upgrade="branding")


def test_manager_and_acquisition(rich):
    with pytest.raises(GameError, match="manager"):
        go(rich, type="buy_competitor")
    state, _ = go(rich, type="hire_manager", shop="cafe")
    assert state["shops"]["cafe"]["manager"]
    with pytest.raises(GameError):
        go(state, type="hire_manager", shop="cafe")
    state, res = go(state, type="buy_competitor")
    assert state["shops"]["rival"]["owner"] == "player"
    restock = res["restock"]["cost"]  # V3: the barista restocks right after the purchase
    assert state["money"] == 200_000 - 20_000 - 50_000 - restock
    assert state["status"] == logic.RUNNING
    state, _ = go(state, type="enter_wholesaler")
    state, _ = go(state, type="set_cart_item", item="tea_leaves", qty=1)


def test_victory(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    state, _ = go(state, type="buy_competitor")
    state, _ = go(state, type="hire_manager", shop="rival")
    assert state["status"] == logic.VICTORY
    with pytest.raises(GameError):
        go(state, type="enter_wholesaler")


def queued(state, sid, shop, items):
    s = state["students"][sid]
    s["status"], s["intent"] = st.QUEUING, {"shop": shop, "items": list(items)}
    return state


def test_bot_serves_without_touching_player_money():
    state, _ = go(logic.new_game(seed=3), t=8.0, type="tick")
    state = queued(state, "s2", "rival", ["tea", "croissant"])
    state, res = go(state, t=8.2, type="auto_serve", shop="rival", student="s2")
    assert res["amount"] == 270
    assert state["money"] == 5_000
    assert state["stats"]["rival_revenue"] == 270
    assert state["students"]["s2"]["budget"] == 730


def test_manager_serves_from_stock(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    state["shops"]["cafe"]["stock"] = [{"item": "coffee_beans", "units": 1, "age": 0}]
    state, _ = go(state, t=8.0, type="tick")
    state = queued(state, "s1", "cafe", ["coffee", "pastel_de_nata"])
    before = state["money"]
    state, res = go(state, t=8.2, type="auto_serve", shop="cafe", student="s1")
    assert res["items"] == ["coffee"]
    assert state["money"] == before + 90
    assert state["shops"]["cafe"]["stock"] == []


def test_player_cannot_serve_manually_where_a_manager_works(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    state, _ = go(state, t=8.0, type="tick")
    state = queued(state, "s1", "cafe", ["coffee"])
    with pytest.raises(GameError):
        go(state, t=8.1, type="accept", shop="cafe", student="s1", player_inside=True)


# V3: the bought competitor keeps selling automatically -------------------------


def bought(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    state, res = go(state, type="buy_competitor")
    return state, res


def test_bought_competitor_keeps_its_barista_and_sells_automatically(rich):
    state, res = bought(rich)
    assert state["shops"]["rival"]["staff"] is True
    assert logic.is_auto(state, "rival")
    assert "barista restocked" in res["toast"]


def test_purchase_restocks_the_competitor_immediately(rich):
    state, res = bought(rich)
    stock = {b["item"]: b["units"] for b in state["shops"]["rival"]["stock"]}
    # 20 coffee + 15 tea + 15 croissants -> 1 pack beans, 1 box tea, 15 croissants
    assert stock == {"coffee_beans": 25, "tea_leaves": 20, "croissant_dough": 15}
    assert res["restock"]["cost"] == 400 + 240 + 15 * 50
    assert state["money"] == 200_000 - 20_000 - 50_000 - 1_390


def test_customers_of_the_bought_competitor_get_their_order_and_pay(rich):
    state, _ = bought(rich)
    state, _ = go(state, t=8.0, type="tick")
    state = queued(state, "s3", "rival", ["tea", "croissant"])
    before = state["money"]
    state, res = go(state, t=8.2, type="auto_serve", shop="rival", student="s3")
    assert res["items"] == ["tea", "croissant"]
    assert res["amount"] == 120 + 150
    assert state["money"] == before + 270
    assert state["students"]["s3"]["budget"] == 1_000 - 270
    assert state["students"]["s3"]["status"] == st.WANDERING
    assert state["stats"]["shops"]["rival"]["served"] == 1


def test_competitor_restocks_every_morning(rich):
    state, _ = bought(rich)
    state, _ = go(state, t=21.0, type="tick")  # croissants spoil overnight
    state, _ = go(state, t=21.0, type="next_day")
    stock = {}
    for b in state["shops"]["rival"]["stock"]:
        stock[b["item"]] = stock.get(b["item"], 0) + b["units"]
    assert stock["croissant_dough"] == 15
    assert state["restock"]["items"]["croissant_dough"] == 15
    assert state["stats"]["purchase_cost"] == state["restock"]["cost"]


def test_restock_only_buys_what_the_money_allows(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    state["money"] = 50_000 + 500  # after the purchase only €5.00 are left
    state, res = go(state, type="buy_competitor")
    assert res["restock"]["cost"] <= 500
    assert state["money"] >= 0


def test_v2_save_without_staff_still_works():
    state = logic.new_game(seed=5)
    state["money"] = 200_000
    state, _ = go(state, type="hire_manager", shop="cafe")
    state, _ = go(state, type="buy_competitor")
    for shop in state["shops"].values():
        del shop["staff"]  # what a v2 save looks like
    del state["restock"]
    logic.migrate(state)
    assert state["shops"]["rival"]["staff"] is True
    assert state["shops"]["cafe"]["staff"] is False
    assert logic.is_auto(state, "rival")
