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
    with pytest.raises(GameError, match="Nicht genug Geld"):
        go(logic.new_game(seed=1), type="buy_upgrade", shop="cafe", upgrade="branding")


def test_manager_and_acquisition(rich):
    with pytest.raises(GameError, match="Manager"):
        go(rich, type="buy_competitor")
    state, _ = go(rich, type="hire_manager", shop="cafe")
    assert state["shops"]["cafe"]["manager"]
    with pytest.raises(GameError):
        go(state, type="hire_manager", shop="cafe")
    state, res = go(state, type="buy_competitor")
    assert state["shops"]["rival"]["owner"] == "player"
    assert state["money"] == 200_000 - 20_000 - 50_000
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
