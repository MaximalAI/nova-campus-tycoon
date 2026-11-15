"""V14: something sells out while a student waits at the counter (see specs/v14-world-ui-and-performance.md)."""

import logic
import students as st
from config import CONFIG


def go(state, t, **event):
    return logic.apply(state, dict(event, t=t))


def at_counter(stock, items=("coffee", "pastel_de_nata"), sid="s0", t=8.2):
    """A student at the café counter who checked his order while everything was in stock."""
    state = logic.new_game(seed=4)
    state["shops"]["cafe"]["stock"] = stock
    state, _ = go(state, 8.0, type="tick")
    s = state["students"][sid]
    s["status"] = st.WALKING_TO_SHOP
    s["intent"] = {"shop": "cafe", "items": list(items)}
    state, _ = go(state, 8.1, type="join_queue", student=sid, shop="cafe")
    state, res = go(state, t, type="at_counter", shop="cafe", student=sid)
    assert res["sold_out"] == []
    return state


def test_a_product_that_sold_out_while_waiting_costs_reputation_at_accept():
    state = at_counter([{"item": "coffee_beans", "units": 25, "age": 0}, {"item": "nata", "units": 1, "age": 0}])
    state["shops"]["cafe"]["stock"] = [lot for lot in state["shops"]["cafe"]["stock"] if lot["item"] != "nata"]
    before = state["reputation"]
    state, res = go(state, 8.3, type="accept", shop="cafe", student="s0", player_inside=True)
    # before v14 the order was accepted without the pastel and nothing happened to the reputation
    assert res["sold_out"] == ["pastel_de_nata"] and state["reputation"] < before
    assert res["rep_delta"] == CONFIG["reputation"]["sold_out_partial"] or res.get("leaves")
    if not res.get("leaves"):
        assert state["current_order"]["items"] == ["coffee"]


def test_a_customer_whose_whole_order_sold_out_leaves_instead_of_an_error():
    state = at_counter([{"item": "nata", "units": 1, "age": 0}], items=("pastel_de_nata",))
    state["shops"]["cafe"]["stock"] = []
    before = state["reputation"]
    state, res = go(state, 8.3, type="accept", shop="cafe", student="s0", player_inside=True)  # no GameError any more
    assert res["leaves"] and res["sold_out"] == ["pastel_de_nata"]
    assert state["current_order"] is None and state["reputation"] < before
    assert state["stats"]["shops"]["cafe"]["lost"] == 1


def test_asking_again_at_the_counter_shows_the_sold_out_product():
    state = at_counter([{"item": "coffee_beans", "units": 25, "age": 0}, {"item": "nata", "units": 1, "age": 0}])
    state["shops"]["cafe"]["stock"] = [lot for lot in state["shops"]["cafe"]["stock"] if lot["item"] != "nata"]
    state, res = go(state, 8.3, type="at_counter", shop="cafe", student="s0")
    assert res["sold_out"] == ["pastel_de_nata"]


def test_the_view_history_keeps_only_the_summary_fields():
    state = logic.new_game(seed=4)
    state, _ = go(state, 21.0, type="tick")
    state, _ = go(state, 21.0, type="next_day")
    h = logic.view(state)["history"][-1]
    assert set(h) <= {"day", "revenue", "tips", "profit", "served", "lost", "reputation", "money", "competitor"}
    assert h["day"] == 1
