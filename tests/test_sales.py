"""Sales process, reputation, closing and summary (brief sections 6 and 7)."""

import pytest

import logic
import students as st
from logic import GameError


def go(state, t, **event):
    return logic.apply(state, dict(event, t=t))


def open_game(stock=None):
    """A game at 08:00 with stock in the café and one student walking to it."""
    state = logic.new_game(seed=4)
    state["shops"]["cafe"]["stock"] = stock if stock is not None else [
        {"item": "coffee_beans", "units": 25, "age": 0},
        {"item": "oranges", "units": 12, "age": 0},
        {"item": "nata", "units": 5, "age": 0},
    ]
    state, _ = go(state, 8.0, type="tick")
    return state


def send_student(state, sid="s0", items=("coffee", "pastel_de_nata"), shop="cafe", t=8.1):
    s = state["students"][sid]
    s["status"] = st.WALKING_TO_SHOP
    s["intent"] = {"shop": shop, "items": list(items)}
    state, _ = go(state, t, type="join_queue", student=sid, shop=shop)
    return state


def serve(state, sid="s0", t=8.2):
    state, res = go(state, t, type="at_counter", shop="cafe", student=sid)
    state, _ = go(state, t, type="accept", shop="cafe", student=sid, player_inside=True)
    for p in res["items"]:
        state, _ = go(state, t, type="prepare", shop="cafe", product=p, player_inside=True)
    return go(state, t + 0.05, type="handover", shop="cafe", student=sid, player_inside=True)


def test_full_order_credits_money_only_at_handover():
    state = send_student(open_game())
    state, _ = go(state, 8.2, type="at_counter", shop="cafe", student="s0")
    state, _ = go(state, 8.2, type="accept", shop="cafe", student="s0", player_inside=True)
    state, _ = go(state, 8.25, type="prepare", shop="cafe", product="coffee", player_inside=True)
    state, _ = go(state, 8.3, type="prepare", shop="cafe", product="pastel_de_nata", player_inside=True)
    assert state["money"] == 5_000
    assert state["tray"] == ["coffee", "pastel_de_nata"]
    state, res = go(state, 8.32, type="handover", shop="cafe", student="s0", player_inside=True)
    assert state["money"] == 5_000 + 90 + 130
    assert res["correct"] and res["toast"] == "Kunde zufrieden: +2,20 €"
    assert state["students"]["s0"]["budget"] == 1_000 - 220
    assert state["students"]["s0"]["status"] == st.WANDERING
    assert state["current_order"] is None


def test_student_only_buys_after_counter_and_acceptance():
    state = send_student(open_game())
    with pytest.raises(GameError):
        go(state, 8.2, type="handover", shop="cafe", student="s0", player_inside=True)
    with pytest.raises(GameError):
        go(state, 8.2, type="auto_serve", shop="cafe", student="s0")
    assert state["students"]["s0"]["purchases"] == []


def test_one_order_at_a_time():
    state = send_student(open_game())
    state = send_student(state, sid="s1", items=("coffee",))
    state, _ = go(state, 8.2, type="accept", shop="cafe", student="s0", player_inside=True)
    with pytest.raises(GameError, match="schon eine Bestellung"):
        go(state, 8.2, type="accept", shop="cafe", student="s1", player_inside=True)


def test_serving_requires_the_player_inside():
    state = send_student(open_game())
    with pytest.raises(GameError, match="im Laden"):
        go(state, 8.2, type="accept", shop="cafe", student="s0", player_inside=False)


def test_wrong_items_lower_reputation():
    state = send_student(open_game(), items=("coffee",))
    state, _ = go(state, 8.2, type="accept", shop="cafe", student="s0", player_inside=True)
    state, _ = go(state, 8.25, type="prepare", shop="cafe", product="pastel_de_nata", player_inside=True)
    state, res = go(state, 8.3, type="handover", shop="cafe", student="s0", player_inside=True)
    assert not res["correct"]
    assert state["reputation"] == 50 - 4
    assert state["money"] == 5_000
    assert state["stats"]["shops"]["cafe"]["wrong"] == 1


def test_fast_correct_service_raises_reputation():
    state, _ = serve(send_student(open_game(), items=("coffee",)))
    assert state["reputation"] == 50 + 2 + 1


def test_sold_out_item_greyed_and_student_redecides():
    state = send_student(open_game(stock=[{"item": "coffee_beans", "units": 25, "age": 0}]))
    state, res = go(state, 8.2, type="at_counter", shop="cafe", student="s0")
    assert res["sold_out"] == ["pastel_de_nata"]
    assert "pastel_de_nata" not in res["items"]
    if not res.get("leaves"):
        assert state["students"]["s0"]["status"] == st.QUEUING


def test_rejected_student_redecides_without_this_cafe():
    state = send_student(open_game())
    state, res = go(state, 8.2, type="reject", shop="cafe", student="s0")
    assert res["action"] in ("shop", "wander")
    if res["action"] == "shop":
        assert res["shop"] == "rival"


def test_patience_runs_out():
    state = send_student(open_game())
    state, _ = go(state, 8.2, type="accept", shop="cafe", student="s0", player_inside=True)
    state, res = go(state, 9.0, type="patience_expired", shop="cafe", student="s0")
    assert res["toast"] == "Kunde ist gegangen"
    assert state["current_order"] is None
    assert state["stats"]["shops"]["cafe"]["lost"] == 1
    assert state["reputation"] == 49


def test_closing_cancels_order_and_sends_queue_away():
    state = send_student(open_game())
    state = send_student(state, sid="s1", items=("coffee",))
    state, _ = go(state, 19.9, type="accept", shop="cafe", student="s0", player_inside=True)
    state, _ = go(state, 19.95, type="prepare", shop="cafe", product="coffee", player_inside=True)
    state, res = go(state, 20.0, type="tick")
    assert res["closed"] and res["cancelled"] == "s0"
    assert state["current_order"] is None and state["tray"] == []
    assert state["money"] == 5_000
    assert state["students"]["s1"]["status"] == st.WANDERING
    with pytest.raises(GameError):
        go(state, 20.1, type="accept", shop="cafe", student="s1", player_inside=True)


def test_last_customers_toast():
    state, res = go(open_game(), 19.75, type="tick")
    assert res["toast"] == "Letzte Kunden"


def test_no_new_customers_after_last_call():
    state = open_game()
    state, _ = go(state, 19.76, type="tick")
    s = state["students"]["s3"]
    s["status"] = st.WANDERING
    state, res = go(state, 19.8, type="decide", student="s3")
    assert res["action"] == "wander"


def test_cleaning_then_summary():
    state, _ = go(open_game(), 20.0, type="tick")
    with pytest.raises(GameError):
        go(state, 20.1, type="clean", spot="mirror")
    for spot in ("counter", "coffee_machine", "tables"):
        state, res = go(state, 20.2, type="clean", spot=spot)
        assert res["toast"] == "Erledigt"
    state, res = go(state, 20.3, type="clean", spot="floor")
    assert state["day_state"] == logic.DAY_SUMMARY
    assert res["summary"]["day"] == 1


def test_missed_cleaning_costs_reputation():
    state, _ = go(open_game(), 20.0, type="tick")
    state, _ = go(state, 21.0, type="tick")
    assert state["day_state"] == logic.DAY_SUMMARY
    assert state["reputation"] == 45


def test_summary_numbers_add_up():
    state = open_game()
    state["stats"]["purchase_cost"] = 1_000
    state, _ = serve(send_student(state, items=("coffee", "pastel_de_nata")))
    state, _ = go(state, 21.0, type="tick")
    s = state["summary"]
    assert s["revenue"] == 220
    assert s["profit"] == s["revenue"] - s["purchase_cost"] - s["spending"]
    assert s["sold"] == {"coffee": 1, "pastel_de_nata": 1}
    assert s["served"] == 1


def test_reputation_scales_next_days_factor():
    state = open_game()
    state["reputation"] = 100
    state, _ = go(state, 20.0, type="tick")
    for spot in ("counter", "coffee_machine", "tables", "floor"):  # no cleaning penalty
        state, _ = go(state, 20.5, type="clean", spot=spot)
    state, _ = go(state, 21.0, type="next_day")
    assert state["rep_factor"] == pytest.approx(1.2)
    assert logic.shop_factor(state, "cafe") == pytest.approx(1.2)
    state["reputation"] = 0
    assert logic.reputation_factor(0) == pytest.approx(0.8)


def test_game_over_when_money_is_gone():
    state = open_game()
    state["money"] = 0
    state, _ = go(state, 21.0, type="tick")
    assert state["status"] == logic.GAME_OVER
    with pytest.raises(GameError):
        go(state, 21.0, type="next_day")


def test_next_day_resets_the_day():
    state, _ = serve(send_student(open_game()))
    state, _ = go(state, 21.0, type="tick")
    state, res = go(state, 21.0, type="next_day")
    assert res["new_day"] == 2
    assert state["time"] == 5.0 and state["day_state"] == logic.MORNING_PLANNING
    assert state["students"]["s0"]["budget"] == 1_000
    assert state["stats"]["shops"]["cafe"]["revenue"] == 0
    assert len(state["history"]) == 1
