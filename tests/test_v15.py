"""V15: one reputation rule for all customers, partly served customers, broken machines,
what you had vs. sold, and game over when you are stuck (see specs/v15-reputation-snackbots-docs.md)."""

import logic
import students as st
from config import CONFIG

REP = CONFIG["reputation"]


def go(state, t, **event):
    return logic.apply(state, dict(event, t=t))


def open_game(stock=None, seed=4):
    state = logic.new_game(seed=seed)
    state["shops"]["cafe"]["stock"] = stock if stock is not None else [
        {"item": "coffee_beans", "units": 25, "age": 0}, {"item": "oranges", "units": 12, "age": 0},
        {"item": "nata", "units": 5, "age": 0}]
    state, _ = go(state, 8.0, type="tick")
    return state


def queue(state, sid="s0", items=("coffee",), shop="cafe"):
    s = state["students"][sid]
    s["status"] = st.WALKING_TO_SHOP
    s["intent"] = {"shop": shop, "items": list(items)}
    state, _ = go(state, 8.1, type="join_queue", student=sid, shop=shop)
    return state


def serve(state, sid="s0", t=8.2):
    state, res = go(state, t, type="at_counter", shop="cafe", student=sid)
    if res.get("leaves"):
        return state, res
    state, _ = go(state, t, type="accept", shop="cafe", student=sid, player_inside=True)
    for p in res["items"]:
        state, _ = go(state, t, type="prepare", shop="cafe", product=p, player_inside=True)
    return go(state, t + 0.01, type="handover", shop="cafe", student=sid, player_inside=True)


# ------------------------------------------------------------------ one rule for all customers


def test_a_customer_of_a_manager_counts_like_one_of_yours():
    assert REP["staff_served"] == REP["correct_order"]


def test_all_customer_changes_share_one_daily_budget():
    """Sold-out losses had their own -15 cap, so a big empire could only sink (v14)."""
    state = open_game()
    state["reputation"] = 50
    cap = REP["customer_daily_cap"]
    for _ in range(30):
        logic._sold_out_penalty(state, state["students"]["s0"])
    assert state["reputation"] == 50 - cap
    for _ in range(30):  # happy customers make up for the sold-out ones on the same day
        logic._customer_reputation(state, REP["correct_order"], "served")
    assert state["reputation"] == 50 + cap


def test_the_summary_says_why_the_reputation_changed():
    state = queue(open_game())
    state, res = serve(state)
    assert res["correct"] and res["rep_delta"] > 0
    assert state["stats"]["rep_sources"]["served"] == res["rep_delta"]


def test_a_partly_served_customer_brings_no_plus():
    state = queue(open_game(stock=[{"item": "coffee_beans", "units": 25, "age": 0}]), items=("coffee", "pastel_de_nata"))
    before = state["reputation"]
    state, res = serve(state)
    if res.get("leaves"):  # he may prefer another shop; then he is not served at all
        assert state["reputation"] < before
        return
    assert res["partly"] and res["rep_delta"] == 0 and "Partly happy" in res["toast"]
    assert state["reputation"] == before + REP["sold_out_partial"]
    assert state["stats"]["shops"]["cafe"]["partly"] == 1


# ------------------------------------------------------------------ SnackBots


def snackbots_open():
    state = logic.new_game(seed=5)
    for s in logic.SHOP_ORDER[:logic.SHOP_ORDER.index("snackbots") + 1]:
        state["shops"][s].update({"owner": "player", "manager": True, "manager_hired": True, "staff": False})
    state, _ = go(state, 8.0, type="tick")
    return state


def test_a_broken_machine_says_broken_not_empty():
    state = snackbots_open()
    import mechanics
    mid = mechanics.of("snackbots").machine_ids()[0]
    machines = mechanics.of("snackbots").machines(state)
    machines[mid]["broken"] = True
    machines[mid]["stock"] = {p: 5 for p in CONFIG["shops"]["snackbots"]["products"]}
    sid = "s1"
    state = queue(state, sid=sid, items=(CONFIG["shops"]["snackbots"]["products"][0],), shop="snackbots")
    before = state["reputation"]
    state, res = go(state, 8.2, type="auto_serve", student=sid, shop="snackbots", machine=mid)
    assert res["broken"] and res["items"] == [] and state["reputation"] == before + REP["machine_broken"]
    assert state["stats"]["rep_sources"]["broken"] == REP["machine_broken"]


def test_collected_cash_says_it_is_not_in_the_account_yet():
    state = snackbots_open()
    import mechanics
    mid = mechanics.of("snackbots").machine_ids()[0]
    mechanics.of("snackbots").machines(state)[mid]["cash"] = 420
    state["shops"]["snackbots"]["manager"] = False
    state, res = go(state, 8.2, type="collect_cash", shop="snackbots", machine=mid)
    assert "not in your account yet" in res["toast"]
    assert "not in your account yet" in mechanics.of("snackbots").objective(state, "SHOP_OPEN")


# ------------------------------------------------------------------ summary: what you had


def test_you_never_sell_more_than_you_had():
    state = queue(open_game())
    state, _ = serve(state)
    state, _ = go(state, 21.0, type="tick")
    s = state["summary"]
    for p, n in s["sold"].items():
        assert s["available"][p] >= n
    assert s["available"]["coffee"] >= 1


# ------------------------------------------------------------------ game over when stuck


def test_game_over_when_you_have_no_stock_and_too_little_money():
    state = logic.new_game(seed=6)
    state["money"] = 57  # €0.57: less than the cheapest item at the wholesaler
    state["shops"]["cafe"]["stock"] = []
    assert logic.is_stuck(state)
    state, _ = go(state, 21.0, type="tick")
    assert state["status"] == logic.GAME_OVER and state["end_reason"] == "stuck"
    assert logic.view(state)["end_reason"] == "stuck"


def test_not_stuck_while_something_can_still_be_sold():
    state = logic.new_game(seed=6)
    state["money"] = 57
    state["shops"]["cafe"]["stock"] = [{"item": "coffee_beans", "units": 3, "age": 0}]
    assert not logic.is_stuck(state)
    state["shops"]["cafe"]["stock"] = []
    state["carried_cash"] = 300  # cash from the machines still to deposit
    assert not logic.is_stuck(state)
