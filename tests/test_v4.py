"""V4 rules: reputation perks and penalties, tips, cancelling, stock report, reset."""

import pytest

import db
import logic
import simulation as sim
import students as st
from config import CONFIG
from logic import GameError

REP = CONFIG["reputation"]


def go(state, t, **event):
    return logic.apply(state, dict(event, t=t))


def opened(seed=4, plan=True):
    """A game at 08:00 whose stock came in through the normal morning (so it is tracked)."""
    state = sim.morning_setup(logic.new_game(seed=seed)) if plan else logic.new_game(seed=seed)
    state, _ = go(state, 8.0, type="tick")
    return state


def queue(state, sid="s0", items=("coffee",), t=8.1):
    s = state["students"][sid]
    s["status"] = st.WALKING_TO_SHOP
    s["intent"] = {"shop": "cafe", "items": list(items)}
    state, _ = go(state, t, type="join_queue", student=sid, shop="cafe")
    return state


def accept(state, sid="s0", t=8.2):
    state, _ = go(state, t, type="at_counter", shop="cafe", student=sid)
    state, _ = go(state, t, type="accept", shop="cafe", student=sid, player_inside=True)
    return state


# --- reputation goes down when customers leave unhappy -------------------------


def test_sold_out_customer_who_leaves_costs_reputation():
    state = queue(opened(plan=False), items=("coffee",))  # no stock at all
    state, res = go(state, 8.2, type="at_counter", shop="cafe", student="s0")
    assert res["leaves"]
    assert res["rep_delta"] == REP["sold_out_left"]
    assert state["reputation"] == 50 + REP["sold_out_left"]
    assert state["stats"]["shops"]["cafe"]["lost"] == 1
    assert state["stats"]["shops"]["cafe"]["sold_out"] == 1


def test_waiting_too_long_costs_more_than_before():
    assert REP["customer_lost"] <= -3
    state = queue(opened())
    state, _ = go(state, 9.0, type="patience_expired", shop="cafe", student="s0")
    assert state["reputation"] == 50 + REP["customer_lost"]


def test_turning_a_customer_away_costs_reputation():
    state = queue(opened())
    state, _ = go(state, 8.2, type="reject", shop="cafe", student="s0")
    assert state["reputation"] == 50 + REP["rejected"]
    assert state["stats"]["shops"]["cafe"]["rejected"] == 1


def test_staff_with_empty_shelves_loses_reputation():
    state = opened(plan=False)
    state["shops"]["cafe"]["manager"] = True
    state = queue(state, items=("coffee",))
    state, res = go(state, 8.2, type="auto_serve", shop="cafe", student="s0")
    assert res["items"] == [] and res["rep_delta"] == REP["sold_out_left"]


def test_reputation_never_leaves_0_to_100():
    state = queue(opened())
    state["reputation"] = 1
    state, res = go(state, 9.0, type="patience_expired", shop="cafe", student="s0")
    assert state["reputation"] == 0 and res["rep_delta"] == -1


# --- what reputation brings ---------------------------------------------------------


def test_reputation_perks_rise_with_reputation():
    assert logic.tip_rate(50) == 0
    assert logic.tip_rate(60) == 0.05 and logic.tip_rate(80) == 0.10 and logic.tip_rate(95) == 0.15
    assert logic.patience_factor(0) < logic.patience_factor(50) < logic.patience_factor(100)
    assert logic.reputation_factor(0) < 1 < logic.reputation_factor(100)
    perks = logic.view(opened())["rep_perks"]
    assert perks["tip"] == 0 and perks["next_tip"] == 60
    assert perks["demand_today"] == pytest.approx(logic.reputation_factor(50) - 1)


def test_happy_customers_tip_with_good_reputation():
    state = accept(queue(opened(), items=("coffee", "pastel_de_nata")))
    state["reputation"] = 80
    money = state["money"]
    state, _ = go(state, 8.25, type="prepare", shop="cafe", product="coffee", player_inside=True)
    state, _ = go(state, 8.25, type="prepare", shop="cafe", product="pastel_de_nata", player_inside=True)
    state, res = go(state, 8.3, type="handover", shop="cafe", student="s0", player_inside=True)
    assert res["amount"] == 220 and res["tip"] == 22
    assert state["money"] == money + 242
    assert "tip" in res["toast"]
    assert state["stats"]["shops"]["cafe"]["tips"] == 22


def test_no_tip_for_a_wrong_order():
    state = accept(queue(opened(), items=("coffee",)))
    state["reputation"] = 95
    state, _ = go(state, 8.25, type="prepare", shop="cafe", product="pastel_de_nata", player_inside=True)
    state, res = go(state, 8.3, type="handover", shop="cafe", student="s0", player_inside=True)
    assert not res["correct"] and res["tip"] == 0


# --- fixing a mistake while serving -----------------------------------------------


def test_wrong_product_can_be_thrown_away_and_order_finished():
    state = accept(queue(opened(), items=("orange_juice",)))
    state, _ = go(state, 8.25, type="prepare", shop="cafe", product="coffee", player_inside=True)
    state, res = go(state, 8.26, type="discard_tray", shop="cafe", player_inside=True)
    assert state["tray"] == [] and state["stats"]["wasted"] == 1
    assert state["current_order"] is not None  # the customer still waits
    state, _ = go(state, 8.3, type="prepare", shop="cafe", product="orange_juice", player_inside=True)
    state, res = go(state, 8.32, type="handover", shop="cafe", student="s0", player_inside=True)
    assert res["correct"]


def test_empty_tray_cannot_be_thrown_away():
    state = accept(queue(opened()))
    with pytest.raises(GameError, match="empty"):
        go(state, 8.25, type="discard_tray", shop="cafe", player_inside=True)


def test_cancelling_an_order_sends_the_customer_away():
    state = accept(queue(opened()))
    state, res = go(state, 8.25, type="cancel_order", shop="cafe", player_inside=True)
    assert state["current_order"] is None and state["tray"] == []
    assert state["reputation"] == 50 + REP["order_cancelled"]
    assert res["student"] == "s0" and res["action"] in ("shop", "wander")
    if res["action"] == "shop":
        assert res["shop"] == "rival"
    with pytest.raises(GameError, match="no order"):
        go(state, 8.3, type="cancel_order", shop="cafe", player_inside=True)


# --- daily summary -------------------------------------------------------------------


def finish_day(state):
    state, _ = go(state, 20.0, type="tick")
    state, _ = go(state, 21.0, type="tick")
    return state


def test_stock_report_adds_up():
    state = accept(queue(opened(), items=("coffee", "orange_juice")))
    for p in ("coffee", "orange_juice"):
        state, _ = go(state, 8.25, type="prepare", shop="cafe", product=p, player_inside=True)
    state, _ = go(state, 8.3, type="handover", shop="cafe", student="s0", player_inside=True)
    s = finish_day(state)["summary"]
    beans = s["stock"]["cafe"]["coffee_beans"]
    assert beans["open"] == 0 and beans["in"] == 25 and beans["used"] == 1 and beans["close"] == 24
    oranges = s["stock"]["cafe"]["oranges"]
    assert oranges["used"] == 3
    for row in s["stock"]["cafe"].values():
        assert row["open"] + row["in"] - row["used"] - row["spoiled"] == row["close"]
        assert row["change"] == row["close"] - row["open"]


def test_next_day_opens_with_yesterdays_closing_stock():
    state = finish_day(opened())
    state, _ = go(state, 21.0, type="next_day")
    flow = state["stats"]["flow"]["cafe"]
    assert flow["coffee_beans"]["open"] == 25
    assert "nata" not in flow  # pastéis spoil overnight


def test_summary_shows_competitor_and_prices():
    state = opened()
    state["stats"]["shops"]["rival"]["served"] = 7
    state["stats"]["rival_revenue"] = 840
    s = finish_day(state)["summary"]
    comp = s["competitor"]
    assert comp["name"] == CONFIG["shops"]["rival"]["name"]
    assert comp["served"] == 7 and comp["revenue"] == 840
    assert comp["prices"] == CONFIG["shops"]["rival"]["start_prices"]
    assert s["prices"]["cafe"] == CONFIG["shops"]["cafe"]["start_prices"]


def test_profit_includes_tips():
    state = accept(queue(opened(), items=("coffee",)))
    state["reputation"] = 95
    state, _ = go(state, 8.25, type="prepare", shop="cafe", product="coffee", player_inside=True)
    state, _ = go(state, 8.3, type="handover", shop="cafe", student="s0", player_inside=True)
    s = finish_day(state)["summary"]
    assert s["tips"] > 0
    assert s["profit"] == s["revenue"] + s["tips"] - s["purchase_cost"] - s["spending"]


def test_view_has_history_of_the_last_days_and_portions():
    state = opened()
    v = logic.view(state)
    assert v["shops"]["cafe"]["portions"] == {"coffee": 25, "orange_juice": 6, "pastel_de_nata": 12}
    assert v["shops"]["rival"]["portions"]["coffee"] is None  # the bot is never sold out
    for _ in range(3):
        state = finish_day(state)
        state, _ = go(state, 21.0, type="next_day")
        state, _ = go(state, 8.0, type="tick")
    assert [d["day"] for d in logic.view(state)["history"]] == [1, 2, 3]


# --- cheaper upgrades, faster preparation ------------------------------------------


def test_upgrades_cost_less_than_in_v3():
    v3 = {"coffee_machine": 6_000, "seating": 12_000, "branding": 20_000}
    for key, cost in v3.items():
        assert CONFIG["upgrades"][key]["cost"] < cost
    assert CONFIG["manager_cost"] < 20_000 and CONFIG["acquisition_cost"] < 50_000


def test_preparation_is_faster_than_in_v3():
    v3 = {"coffee": 5, "orange_juice": 6, "tea": 4}
    for product, minutes in v3.items():
        assert CONFIG["products"][product]["prep_minutes"] < minutes


# --- saving, continue and reset ------------------------------------------------------


def test_reset_starts_over_and_old_game_is_not_continued(tmp_path):
    conn = db.connect(tmp_path / "game.db")
    old = db.save_game(conn, logic.new_game(seed=1))
    assert db.latest_game_id(conn) == old
    db.abandon_running(conn)
    assert db.latest_game_id(conn) is None
    new = db.save_game(conn, logic.new_game(seed=2))
    assert db.latest_game_id(conn) == new


def test_v3_save_gets_new_statistics_fields():
    state = opened()
    for shop in state["stats"]["shops"].values():
        for key in ("sold_out", "rejected", "tips"):
            del shop[key]
    del state["stats"]["flow"], state["stats"]["wasted"]
    logic.migrate(state)
    state = queue(state)
    state, _ = go(state, 8.2, type="reject", shop="cafe", student="s0")
    assert state["stats"]["shops"]["cafe"]["rejected"] == 1
    s = finish_day(state)["summary"]
    assert s["sold_out"] == 0 and "cafe" in s["stock"]


def test_sold_out_disappoints_each_student_only_once_a_day():
    state = queue(opened(plan=False), items=("coffee",))
    state, _ = go(state, 8.2, type="at_counter", shop="cafe", student="s0")
    rep_after_first = state["reputation"]
    s = state["students"]["s0"]
    s["status"], s["intent"] = st.WALKING_TO_SHOP, {"shop": "cafe", "items": ["coffee"]}
    state, _ = go(state, 9.0, type="join_queue", student="s0", shop="cafe")
    state, res = go(state, 9.1, type="at_counter", shop="cafe", student="s0")
    assert res["leaves"] and res["rep_delta"] == 0
    assert state["reputation"] == rep_after_first
    assert state["stats"]["shops"]["cafe"]["lost"] == 2


def test_continue_inside_the_wholesaler_starts_outside_with_an_empty_cart():
    state = logic.new_game(seed=3)
    state, _ = go(state, 5.2, type="confirm_plan", plan={"coffee": 25})
    state, _ = go(state, 5.6, type="enter_wholesaler")
    state, _ = go(state, 5.65, type="set_cart_item", item="coffee_beans", qty=1)
    assert state["cart"]
    state, _ = go(state, 5.7, type="resume")
    assert not state["in_wholesaler"] and state["cart"] == {}
    state, _ = go(state, 5.8, type="enter_wholesaler")
    assert state["cart"] == {}  # v5: the cart always starts empty


def test_float_clock_just_below_the_mark_still_counts():
    state = opened()
    state, res = go(state, 19.9999999, type="tick")
    assert state["closed"]
    state, res = go(state, 20.9999999, type="tick")
    assert state["day_state"] == logic.DAY_SUMMARY and "summary" in res
