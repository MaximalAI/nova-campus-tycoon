"""V5 rules: throwing away single products, price boards, closed shops, demand during lectures."""

import collections

import pytest

import logic
import simulation as sim
import students as st
from config import CONFIG
from logic import GameError


def go(state, t, **event):
    return logic.apply(state, dict(event, t=t))


def serving(items=("coffee",), seed=4):
    state = sim.morning_setup(logic.new_game(seed=seed))
    state, _ = go(state, 8.0, type="tick")
    s = state["students"]["s0"]
    s["status"], s["intent"] = st.WALKING_TO_SHOP, {"shop": "cafe", "items": list(items)}
    state, _ = go(state, 8.1, type="join_queue", student="s0", shop="cafe")
    state, _ = go(state, 8.2, type="at_counter", shop="cafe", student="s0")
    state, _ = go(state, 8.2, type="accept", shop="cafe", student="s0", player_inside=True)
    return state


def make(state, product, t=8.25):
    state, _ = go(state, t, type="prepare", shop="cafe", product=product, player_inside=True)
    return state


# --- throw away only what the customer does not want ------------------------------


def test_throw_away_a_single_product():
    state = make(make(serving(("coffee",)), "coffee"), "orange_juice")
    state, res = go(state, 8.3, type="discard_tray", shop="cafe", product="orange_juice", player_inside=True)
    assert state["tray"] == ["coffee"] and res["removed"] == ["orange_juice"]
    state, res = go(state, 8.35, type="handover", shop="cafe", student="s0", player_inside=True)
    assert res["correct"]


def test_throw_away_only_the_extras():
    state = serving(("coffee", "pastel_de_nata"))
    for p in ("coffee", "coffee", "orange_juice", "pastel_de_nata"):
        state = make(state, p)
    state, res = go(state, 8.3, type="discard_tray", shop="cafe", only_extras=True, player_inside=True)
    assert sorted(state["tray"]) == ["coffee", "pastel_de_nata"]
    assert sorted(res["removed"]) == ["coffee", "orange_juice"]
    assert state["stats"]["wasted"] == 2
    with pytest.raises(GameError, match="belongs to the order"):
        go(state, 8.31, type="discard_tray", shop="cafe", only_extras=True, player_inside=True)


def test_unknown_product_cannot_be_thrown_away():
    state = make(serving(), "coffee")
    with pytest.raises(GameError, match="not on the tray"):
        go(state, 8.3, type="discard_tray", shop="cafe", product="tea", player_inside=True)


# --- price boards ----------------------------------------------------------------------


def test_price_board_shows_dash_until_prices_are_set_or_the_shop_opens():
    state = logic.new_game(seed=1)
    assert not logic.view(state)["shops"]["cafe"]["prices_set"]
    assert logic.view(state)["shops"]["rival"]["prices_set"]  # the competitor's prices are always known
    state, _ = go(state, 6.0, type="set_prices", shop="cafe", prices={"coffee": 100})
    assert logic.view(state)["shops"]["cafe"]["prices_set"]
    other = logic.new_game(seed=2)
    other, _ = go(other, 8.0, type="tick")
    assert other["shops"]["cafe"]["prices_set"]  # opening fixes yesterday's prices
    other, _ = go(other, 21.0, type="tick")
    other, _ = go(other, 21.0, type="next_day")
    assert not other["shops"]["cafe"]["prices_set"]


# --- shops that are closed do not get customers ----------------------------------------


def test_a_shop_you_do_not_run_and_has_no_manager_gets_no_customers():
    state = logic.new_game(seed=3)
    state["shops"]["rival"].update({"owner": "player", "staff": False, "opens_day": 2})
    state, _ = go(state, 8.0, type="tick")
    for sid, s in state["students"].items():
        s["status"] = st.WANDERING
        res = logic._decide(state, sid)
        assert res.get("shop") != "rival"


def test_the_view_tells_which_shop_you_run():
    v = logic.view(logic.new_game(seed=1))
    assert v["work_shop"] == "cafe"
    assert v["shops"]["cafe"]["operating"] and v["shops"]["rival"]["operating"]


# --- the reason why a customer stays or leaves at a sold-out counter --------------------


def test_sold_out_result_explains_the_reaction():
    state = logic.new_game(seed=4)
    state["shops"]["cafe"]["stock"] = [{"item": "coffee_beans", "units": 25, "age": 0}]
    state, _ = go(state, 8.0, type="tick")
    reasons = set()
    for sid in list(state["students"])[:12]:
        s = state["students"][sid]
        s["status"], s["intent"] = st.QUEUING, {"shop": "cafe", "items": ["coffee", "pastel_de_nata"]}
        state, res = go(state, 8.1, type="at_counter", shop="cafe", student=sid)
        reasons.add(res["reason"])
        assert res["sold_out"] == ["pastel_de_nata"]
        if not res.get("leaves"):
            assert res["items"] and "pastel_de_nata" not in res["items"]
    assert reasons  # every reaction comes with a reason
    assert state["stats"]["shops"]["cafe"]["sold_out_products"]["pastel_de_nata"] == 12


# --- day gain and charts ------------------------------------------------------------------


def test_today_shows_the_running_day_gain():
    state = serving(("coffee",))
    state = make(state, "coffee")
    state, _ = go(state, 8.3, type="handover", shop="cafe", student="s0", player_inside=True)
    today = logic.view(state)["today"]
    assert today["revenue"] == 90 and today["served"] == 1
    assert today["gain"] == 90 + today["tips"] - today["purchase_cost"] - today["spending"]


def test_chart_data_covers_every_day():
    state = logic.new_game(seed=2)
    for _ in range(9):
        state, _ = go(state, 21.0, type="tick")
        state, _ = go(state, 21.0, type="next_day")
    chart = logic.view(state)["chart"]
    assert [d["day"] for d in chart] == list(range(1, 10))
    assert {"market_share", "revenue", "profit", "reputation", "competitor_revenue"} <= set(chart[0])


# --- customers also come during lectures ------------------------------------------------


def test_customers_keep_coming_during_lectures():
    per_hour = collections.Counter()
    for seed in (1, 2, 3):
        state = sim.morning_setup(logic.new_game(seed=seed))
        original = logic._decide

        def spy(state, sid, exclude=frozenset(), sold_out=frozenset(), original=original):
            res = original(state, sid, exclude, sold_out)
            if res.get("action") == "shop" and not exclude and not sold_out:
                per_hour[int(state["time"])] += 1
            return res

        logic._decide = spy
        try:
            sim.simulate_day(state, speed=8)
        finally:
            logic._decide = original
    for hour in (9, 10, 11, 13, 14, 15):
        assert per_hour[hour] / 3 >= 6, f"only {per_hour[hour] / 3:.1f} customers at {hour}:00"


def test_lecture_phases_have_more_students_than_v4():
    for t in (10.0, 14.0):
        phase = next(p for p in CONFIG["phases"] if p["from"] <= t < p["to"])
        assert phase["target"] >= 10 and phase["cafe_probability"] >= 0.5
