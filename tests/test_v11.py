"""V11 rules: vending manager rounds, cleaning penalty, Surf Shack costs, Praia Bar prices,
investments outside the profit, plan of every shop in the summary, market share per zone."""

import json

import pytest

import logic
import mechanics
import students as st
from config import CONFIG, SUNSET
from logic import GameError

VEND = "snackbots"
MACHINES = [m["id"] for m in CONFIG["shops"][VEND]["mechanic"]["machines"]]
BEACH = [s for s in logic.SHOP_ORDER if CONFIG["shops"][s]["zone"] == "beach"]
CAMPUS = [s for s in logic.SHOP_ORDER if CONFIG["shops"][s]["zone"] == "campus"]


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def owning(*shops, managers=(), seed=11, money=900_000):
    state = logic.new_game(seed=seed)
    state["money"] = money
    for s in shops:
        state["shops"][s]["owner"] = "player"
    for s in managers:
        state["shops"][s]["manager"] = state["shops"][s]["manager_hired"] = True
    logic._start_day(state, 1)
    return state


def test_the_view_can_be_sent_to_the_browser():
    # v11 bug found in testing: a method name in the view broke the JSON sent to the browser
    state = owning("cafe", VEND, managers=["cafe", VEND])
    json.dumps(logic.view(state))


# ------------------------------------------------------------ vending manager


def stocked_vending():
    state = owning("cafe", VEND, managers=["cafe", VEND])
    for p in CONFIG["shops"][VEND]["products"]:
        for item in CONFIG["products"][p]["uses"]:
            logic._add_stock(state, VEND, item, 30)
    state["day_state"], state["open"] = logic.SHOP_OPEN, True
    return state


def test_the_manager_fills_a_machine_when_he_reaches_it():
    state = stocked_vending()
    state, res = go(state, t=8.1, type="manager_service", shop=VEND, machine=MACHINES[0])
    machines = mechanics.of(VEND).machines(state)
    assert sum(machines[MACHINES[0]]["stock"].values()) > 0
    assert sum(machines[MACHINES[1]]["stock"].values()) == 0  # the others wait for him
    assert "refilled" in res["toast"]


def test_the_cash_he_collects_goes_into_the_balance():
    state = stocked_vending()
    mechanics.of(VEND).machines(state)[MACHINES[1]]["cash"] = 750
    money = state["money"]
    state, res = go(state, t=9.0, type="manager_service", shop=VEND, machine=MACHINES[1])
    assert state["money"] == money + 750 and res["amount"] == 750
    assert mechanics.of(VEND).machines(state)[MACHINES[1]]["cash"] == 0


def test_he_repairs_a_broken_machine_on_his_round():
    state = stocked_vending()
    mechanics.of(VEND).machines(state)[MACHINES[2]]["broken"] = True
    money = state["money"]
    state, res = go(state, t=9.0, type="manager_service", shop=VEND, machine=MACHINES[2])
    assert not mechanics.of(VEND).machines(state)[MACHINES[2]]["broken"]
    assert state["money"] == money - CONFIG["shops"][VEND]["mechanic"]["repair_cost"]
    assert "repaired" in res["toast"]


def test_breakdowns_are_not_repaired_by_magic(monkeypatch):
    state = stocked_vending()
    state, _ = go(state, t=8.0, type="manager_service", shop=VEND, machine=MACHINES[0])  # a round just happened
    monkeypatch.setitem(mechanics.of(VEND).p, "breakdown_per_hour", 1.0)
    state, _ = go(state, t=9.5, type="tick")
    assert all(mechanics.of(VEND).broken(state).values())


def test_without_rounds_from_the_browser_python_does_them():
    state = stocked_vending()
    state, _ = go(state, t=CONFIG["time"]["manager_buys_at"], type="tick")  # the managers buy first
    mechanics.of(VEND).machines(state)[MACHINES[0]]["cash"] = 300
    money = state["money"]
    state, _ = go(state, t=CONFIG["time"]["open"] + 0.4, type="tick")
    assert state["money"] == money  # not yet: the browser has half an hour
    state, _ = go(state, t=CONFIG["time"]["open"] + 0.5, type="tick")
    assert state["money"] == money + 300


def test_only_a_shop_with_a_manager_gets_rounds():
    state = owning("cafe", VEND, managers=["cafe"])
    with pytest.raises(GameError, match="no manager"):
        go(state, t=9.0, type="manager_service", shop=VEND, machine=MACHINES[0])


# ------------------------------------------------------------ reputation


def test_missed_cleaning_costs_15_reputation():
    assert CONFIG["reputation"]["cleaning_missed"] == -15
    state = owning("cafe", managers=[])
    state, _ = go(state, t=20.0, type="tick")
    rep = state["reputation"]
    state, _ = go(state, t=21.0, type="tick")
    assert state["reputation"] == rep - 15


def beach_shop(shop, manager=True):
    state = owning(*CAMPUS, shop, managers=[s for s in CAMPUS if s != "cafe"] + ([shop] if manager else []))
    state["day_state"], state["open"] = logic.SHOP_OPEN, True
    state["time"] = SUNSET + 0.5 if CONFIG["shops"][shop]["open_hours"] else 12.0
    return state


def queue(state, shop, product, sid="b1"):
    s = state["students"][sid]
    s["status"], s["intent"] = st.QUEUING, {"shop": shop, "items": [product]}
    return sid


@pytest.mark.parametrize("shop", BEACH)
def test_sold_out_at_the_beach_costs_reputation(shop):
    state = beach_shop(shop)
    product = CONFIG["shops"][shop]["products"][0]
    sid = queue(state, shop, product)
    rep = state["reputation"]
    state, res = go(state, t=state["time"], type="auto_serve", shop=shop, student=sid)
    assert res["rep_delta"] < 0 and state["reputation"] < rep


@pytest.mark.parametrize("shop", BEACH)
def test_waiting_too_long_at_the_beach_costs_reputation(shop):
    state = beach_shop(shop, manager=False)
    sid = queue(state, shop, CONFIG["shops"][shop]["products"][0])
    state, res = go(state, t=state["time"], type="patience_expired", shop=shop, student=sid)
    assert res["rep_delta"] == CONFIG["reputation"]["customer_lost"]


# ------------------------------------------------------------ Surf Shack and Praia Bar


def test_surf_shack_start_prices_have_a_margin():
    shop = CONFIG["shops"]["surf_shack"]
    for p, price in shop["start_prices"].items():
        assert price > logic.unit_cost(p), p


def test_a_rental_costs_the_board_spread_over_its_rentals():
    board = CONFIG["wholesale_items"]["surfboard"]
    assert logic.unit_cost("surf_rental") == board["price"] / board["lifetime_uses"]


def test_the_manager_does_not_push_rental_prices_up_to_the_board_price():
    state = owning("cafe", "surf_shack", managers=["cafe", "surf_shack"])
    state["history"].append({"by_shop": {"surf_shack": {"sold": {}, "sold_out_products": {}}}})
    proposal = logic.manager_proposal(state, "surf_shack")
    assert proposal["prices"]["surf_rental"] < CONFIG["wholesale_items"]["surfboard"]["price"]


def test_praia_bar_prices_can_change_until_sunset():
    state = owning("cafe", "praia_bar", managers=["cafe", "praia_bar"])
    state["open"], state["day_state"] = True, logic.SHOP_OPEN
    state, _ = go(state, t=12.0, type="set_prices", shop="praia_bar", prices={"beer": 300})
    assert state["shops"]["praia_bar"]["prices"]["beer"] == 300
    state, _ = go(state, t=12.0, type="set_happy_hour", shop="praia_bar", discount=0.2)
    with pytest.raises(GameError, match="before opening"):
        go(state, t=SUNSET + 0.1, type="set_prices", shop="praia_bar", prices={"beer": 350})
    with pytest.raises(GameError, match="before opening"):
        go(state, t=12.0, type="set_prices", shop="cafe", prices={"coffee": 100})  # the café is open


# ------------------------------------------------------------ day summary


def test_investments_are_not_taken_off_the_profit():
    state = owning("cafe", managers=[])
    state, _ = go(state, type="buy_upgrade", shop="cafe", upgrade=next(iter(logic.upgrade_catalogue("cafe"))))
    state, _ = go(state, type="hire_manager", shop="cafe")
    state, _ = go(state, t=20.0, type="tick")
    state, res = go(state, t=21.0, type="tick")
    s = res["summary"]
    assert s["investments"] > 0 and s["spending"] == 0
    assert s["profit"] == s["revenue"] + s["tips"] - s["purchase_cost"] - s["spending"] - s["jep"] + s["casino"] - s["bar"]


def test_the_plan_includes_the_managers_plans():
    state = owning("cafe", "rival", managers=["rival"])
    rival_plan = state["manager_proposals"]["rival"]["plan"]
    state["plan"] = {"coffee": 5, "orange_juice": 2, "pastel_de_nata": 3}
    state, _ = go(state, t=20.0, type="tick")
    state, res = go(state, t=21.0, type="tick")
    s = res["summary"]
    assert s["plan"]["tea"] == rival_plan["tea"]
    assert s["plan"]["coffee"] == 5 + rival_plan["coffee"]
    assert s["by_shop"]["rival"]["plan"] == rival_plan


def test_market_share_counts_the_campus_until_the_beach_opens():
    state = owning("cafe")
    assert logic.market_zones(state) == ["campus"]
    beach_bot = BEACH[0]
    state["stats"]["shops"][beach_bot]["revenue"] = 10_000  # cannot happen, but must not count
    assert logic._bot_revenue(state) == 0
    for s in CAMPUS:
        state["shops"][s]["owner"] = "player"
    assert logic.market_zones(state) == ["campus", "beach"]
    assert logic._bot_revenue(state) == 10_000


# ------------------------------------------------------------ day change


def test_a_late_event_from_yesterday_does_not_end_the_new_day():
    # found in the v11 browser check: an autosave stamped 21:00 arrived after "next_day"
    state = owning("cafe", managers=[])
    state, _ = go(state, t=20.0, type="tick")
    state, _ = go(state, t=21.0, type="tick")
    state, _ = go(state, t=21.0, type="next_day", day=1)
    state, _ = go(state, t=21.0, type="autosave", day=1)  # sent before the browser knew of day 2
    assert state["time"] == CONFIG["time"]["day_start"]
    state, res = go(state, t=7.0, type="tick", day=2)
    assert state["day_state"] != logic.DAY_SUMMARY and "summary" not in res
