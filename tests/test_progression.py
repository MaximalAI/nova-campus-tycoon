"""Upgrades, manager, acquisition, victory, bot and manager serving (brief 8.4 and 9.3)."""

import pytest

import logic
import students as st
from config import CONFIG
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


def next_day(state):
    state, _ = go(state, t=21.0, type="tick")
    state, _ = go(state, t=21.0, type="next_day")
    return state


def test_manager_and_acquisition(rich):
    with pytest.raises(GameError, match="manager"):
        go(rich, type="buy_competitor")
    state, res = go(rich, type="hire_manager", shop="cafe")
    assert "tomorrow" in res["toast"]
    assert state["shops"]["cafe"]["manager_hired"] and not state["shops"]["cafe"]["manager"]
    with pytest.raises(GameError):
        go(state, type="hire_manager", shop="cafe")
    state, _ = go(state, type="buy_competitor")  # possible as soon as the manager is hired
    assert state["shops"]["rival"]["owner"] == "player"
    assert state["money"] == 200_000 - CONFIG["manager_cost"] - CONFIG["acquisition_cost"]
    assert state["status"] == logic.RUNNING


def test_victory_when_both_shops_have_a_manager(rich):
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
    assert state["students"]["s2"]["budget"] == CONFIG["students"]["budget"] - 270


def manager_working(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    return next_day(state)


def test_manager_starts_the_next_day(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    assert not logic.is_auto(state, "cafe")  # today you still serve yourself
    assert logic.work_shop(state) == "cafe"
    state = next_day(state)
    assert state["shops"]["cafe"]["manager"] and logic.is_auto(state, "cafe")
    assert logic.work_shop(state) is None  # nothing left to run yourself until you buy the competitor


def test_manager_serves_from_stock(rich):
    state = manager_working(rich)
    state["shops"]["cafe"]["stock"] = [{"item": "coffee_beans", "units": 1, "age": 0}]
    state["manager_proposals"]["cafe"]["done"] = True
    state, _ = go(state, t=8.0, type="tick")
    state = queued(state, "s1", "cafe", ["coffee", "pastel_de_nata"])
    before = state["money"]
    state, res = go(state, t=8.2, type="auto_serve", shop="cafe", student="s1")
    assert res["items"] == ["coffee"]
    assert state["money"] == before + 90
    assert state["shops"]["cafe"]["stock"] == []


def test_player_cannot_serve_manually_where_a_manager_works(rich):
    state = manager_working(rich)
    state, _ = go(state, t=8.0, type="tick")
    state = queued(state, "s1", "cafe", ["coffee"])
    with pytest.raises(GameError):
        go(state, t=8.1, type="accept", shop="cafe", student="s1", player_inside=True)


def test_happy_customers_of_the_manager_raise_reputation(rich):
    state = manager_working(rich)
    state["shops"]["cafe"]["stock"] = [{"item": "coffee_beans", "units": 25, "age": 0}]
    state, _ = go(state, t=8.0, type="tick")
    rep = state["reputation"]
    state = queued(state, "s1", "cafe", ["coffee"])
    state, res = go(state, t=8.2, type="auto_serve", shop="cafe", student="s1")
    assert res["rep_delta"] == CONFIG["reputation"]["staff_served"]
    assert state["reputation"] == rep + CONFIG["reputation"]["staff_served"]


# v5: manager proposals -----------------------------------------------------------


def test_manager_proposes_shopping_list_and_prices_in_the_morning(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    state["stats"]["shops"]["cafe"]["sold"] = {"coffee": 30, "orange_juice": 0, "pastel_de_nata": 10}
    state["stats"]["shops"]["cafe"]["sold_out_products"] = {"pastel_de_nata": 3}
    state = next_day(state)
    p = state["manager_proposals"]["cafe"]
    assert p["plan"] == {"coffee": 36, "orange_juice": 8, "pastel_de_nata": 15}
    start = CONFIG["shops"]["cafe"]["start_prices"]
    assert p["prices"]["pastel_de_nata"] == start["pastel_de_nata"] + 10  # sold out -> a bit more
    assert p["prices"]["orange_juice"] == start["orange_juice"] - 10  # nobody bought it -> a bit less
    assert p["prices"]["coffee"] == start["coffee"]
    assert p["shopping_list"]["coffee_beans"] == 2 and p["cost"] > 0 and not p["done"]


def test_accepting_or_changing_the_proposal_buys_right_away(rich):
    state = manager_working(rich)
    money = state["money"]
    state, res = go(state, t=5.5, type="confirm_manager_plan", shop="cafe",
                    plan={"coffee": 25, "orange_juice": 0, "pastel_de_nata": 5}, prices={"coffee": 100})
    assert res["bought"] == {"coffee_beans": 1, "nata": 5}
    assert state["money"] == money - 400 - 5 * 60
    assert state["shops"]["cafe"]["prices"]["coffee"] == 100
    assert state["shops"]["cafe"]["prices_set"]
    assert logic.stock_units(state, "cafe", "coffee_beans") == 25
    with pytest.raises(GameError, match="already"):
        go(state, t=5.6, type="confirm_manager_plan", shop="cafe")


def test_manager_buys_the_proposal_at_seven_if_you_did_nothing(rich):
    state = manager_working(rich)
    cost = state["manager_proposals"]["cafe"]["cost"]
    money = state["money"]
    state, res = go(state, t=7.0, type="tick")
    assert state["manager_proposals"]["cafe"]["done"]
    assert state["money"] == money - cost
    assert res["manager_bought"] == ["cafe"]


# v5: running the bought competitor yourself ---------------------------------------


def bought(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    state, res = go(state, type="buy_competitor")
    return state, res


def test_bought_competitor_has_no_staff_and_opens_tomorrow(rich):
    state, res = bought(rich)
    rival = state["shops"]["rival"]
    assert rival["staff"] is False and not rival["manager"] and rival["stock"] == []
    assert not logic.shop_operating(state, "rival")  # closed for the rest of today
    assert logic.work_shop(state) == "cafe"
    assert "tomorrow" in res["toast"]


def test_next_day_you_work_in_the_new_shop_and_the_manager_runs_the_cafe(rich):
    state, _ = bought(rich)
    state = next_day(state)
    assert logic.work_shop(state) == "rival"
    assert logic.shop_operating(state, "rival") and logic.shop_operating(state, "cafe")
    assert not logic.is_auto(state, "rival") and logic.is_auto(state, "cafe")
    assert "cafe" in state["manager_proposals"] and "rival" not in state["manager_proposals"]
    assert set(state["plan"]) == set(CONFIG["shops"]["rival"]["products"])
    # your own shopping list only covers the new shop
    state, res = go(state, t=5.2, type="confirm_plan", plan={"coffee": 10, "tea": 10, "croissant": 5})
    assert res["shopping_list"] == {"coffee_beans": 1, "tea_leaves": 1, "croissant_dough": 5}
    with pytest.raises(GameError):
        go(state, t=5.3, type="confirm_plan", plan={"orange_juice": 5})


def test_you_serve_the_new_shop_by_hand(rich):
    state, _ = bought(rich)
    state = next_day(state)
    state["shops"]["rival"]["stock"] = [{"item": "tea_leaves", "units": 20, "age": 0}]
    state, _ = go(state, t=8.0, type="tick")
    state = queued(state, "s3", "rival", ["tea"])
    state, _ = go(state, t=8.1, type="at_counter", shop="rival", student="s3")
    state, _ = go(state, t=8.1, type="accept", shop="rival", student="s3", player_inside=True)
    state, _ = go(state, t=8.15, type="prepare", shop="rival", product="tea", player_inside=True)
    before = state["money"]
    state, res = go(state, t=8.2, type="handover", shop="rival", student="s3", player_inside=True)
    assert res["correct"] and state["money"] == before + 120


def test_old_save_with_barista_runs_the_new_shop_yourself(rich):
    state, _ = bought(rich)
    rival = state["shops"]["rival"]
    rival["staff"] = True  # what a v3/v4 save looks like
    for key in ("manager_hired", "opens_day", "prices_set"):
        for shop in state["shops"].values():
            shop.pop(key, None)
    state["shops"]["cafe"]["manager"] = True
    del state["manager_proposals"]
    logic.migrate(state)
    assert rival["staff"] is False and state["shops"]["cafe"]["manager_hired"]
    assert logic.work_shop(state) == "rival"
