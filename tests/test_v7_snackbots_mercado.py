"""v7 step 2: SnackBots (vending machines) and Mercado & Go (limited shelf space)."""

import pytest

import logic
import mechanics
import simulation as sim
import students as st
from config import CONFIG
from logic import GameError

VEND = next(s for s, spec in CONFIG["shops"].items() if spec["mechanic"]["type"] == "vending")
MARKET = next(s for s, spec in CONFIG["shops"].items() if spec["mechanic"]["type"] == "shelves")


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def own(shop, seed=21):
    """A game where you run ``shop`` yourself (your other shops have managers)."""
    state = logic.new_game(seed=seed)
    state["money"] = 500_000
    for s in logic.SHOP_ORDER:
        if s == shop:
            break
        state["shops"][s].update({"owner": "player", "manager": True, "manager_hired": True, "staff": False})
    state["shops"][shop].update({"owner": "player", "staff": False, "prices_set": False})
    assert logic.work_shop(state) == shop
    return state


def stock(state, shop, item, units):
    state["shops"][shop]["stock"].append({"item": item, "units": units, "age": 0})
    return state


def queued(state, sid, shop, items):
    s = state["students"][sid]
    s["status"], s["intent"] = st.QUEUING, {"shop": shop, "items": list(items)}
    return state


# --- SnackBots ----------------------------------------------------------------------------


def test_vending_needs_no_staff_and_sells_only_what_is_in_the_machine():
    state = own(VEND)
    water = CONFIG["shops"][VEND]["products"][0]
    item = next(iter(CONFIG["products"][water]["uses"]))
    assert logic.is_auto(state, VEND)  # nobody has to stand behind a counter
    stock(state, VEND, item, 30)
    assert logic.portions(state, VEND, water) == 0  # in the storage, not in the machine
    state, res = go(state, type="fill_front", shop=VEND, amounts={water: 50})
    cap = CONFIG["shops"][VEND]["mechanic"]["capacity"]
    assert res["moved"] == {water: cap}  # a machine holds a limited number
    assert logic.portions(state, VEND, water) == cap
    assert logic.stock_units(state, VEND, item) == 30 - cap
    state, _ = go(state, t=8.0, type="tick")
    queued(state, "s4", VEND, [water])
    state, res = go(state, t=8.1, type="auto_serve", shop=VEND, student="s4")
    assert res["items"] == [water]
    assert logic.portions(state, VEND, water) == cap - 1


def test_a_broken_machine_sells_nothing_until_repaired(monkeypatch):
    state = own(VEND)
    water = CONFIG["shops"][VEND]["products"][0]
    stock(state, VEND, next(iter(CONFIG["products"][water]["uses"])), 12)
    state, _ = go(state, type="fill_front", shop=VEND, amounts={water: 12})
    monkeypatch.setitem(mechanics.of(VEND).p, "breakdown_per_hour", 1.0)
    state, _ = go(state, t=8.0, type="tick")
    state, res = go(state, t=9.0, type="tick")
    assert any("Machine broken" in t for t in res["toasts"])
    assert not logic.can_make(state, VEND, water)
    assert logic.view(state)["shops"][VEND]["mech"]["broken"][water]
    money = state["money"]
    state, _ = go(state, t=9.1, type="repair", shop=VEND, product=water)
    assert money - state["money"] == CONFIG["shops"][VEND]["mechanic"]["repair_cost"]
    assert logic.can_make(state, VEND, water)
    with pytest.raises(GameError, match="works"):
        go(state, t=9.2, type="repair", shop=VEND, product=water)


def test_breakdowns_are_reproducible_and_rare():
    broken = []
    for seed in range(40):
        state = own(VEND, seed=seed)
        state, _ = go(state, t=8.0, type="tick")
        state, _ = go(state, t=20.0, type="tick")
        broken.append(sum(mechanics.of(VEND).broken(state).values()))
    again = own(VEND, seed=7)
    again, _ = go(again, t=8.0, type="tick")
    again, _ = go(again, t=20.0, type="tick")
    assert sum(mechanics.of(VEND).broken(again).values()) == broken[7]
    assert 0 < sum(broken) / 40 < 2  # about one machine every two days


def test_the_vending_manager_refills_and_repairs(monkeypatch):
    state = own(VEND)
    state["shops"][VEND].update({"manager": True, "manager_hired": True})
    state["manager_proposals"] = {VEND: logic.manager_proposal(state, VEND)}
    state, _ = go(state, t=7.0, type="tick")  # he buys his proposal at 07:00 ...
    for p in CONFIG["shops"][VEND]["products"]:
        assert logic.portions(state, VEND, p) > 0  # ... and fills the machines
    monkeypatch.setitem(mechanics.of(VEND).p, "breakdown_per_hour", 1.0)
    state, _ = go(state, t=8.0, type="tick")
    state, res = go(state, t=9.0, type="tick")
    assert any("repaired" in t for t in res["toasts"])
    assert not any(mechanics.of(VEND).broken(state).values())


def test_machine_stock_counts_for_the_shopping_list():
    state = own(VEND)
    water = CONFIG["shops"][VEND]["products"][0]
    item = next(iter(CONFIG["products"][water]["uses"]))
    stock(state, VEND, item, 12)
    state, _ = go(state, type="fill_front", shop=VEND, amounts={water: 12})
    assert logic.shopping_list(state, {water: 12}) == {}
    assert logic.shopping_list(state, {water: 13}) == {item: 1}


# --- Mercado & Go ---------------------------------------------------------------------------


def market_stocked():
    state = own(MARKET)
    for p in CONFIG["shops"][MARKET]["products"]:
        for item, q in CONFIG["products"][p]["uses"].items():
            stock(state, MARKET, item, 50 * q)
    return state


def test_shelves_hold_a_limited_number_of_items_in_total():
    state = market_stocked()
    cap = CONFIG["shops"][MARKET]["mechanic"]["capacity"]
    a, b, c = CONFIG["shops"][MARKET]["products"]
    state, res = go(state, type="fill_front", shop=MARKET, amounts={a: 40, b: 40, c: 40})
    assert sum(res["moved"].values()) == cap
    assert res["moved"][a] == 40 and res["moved"][b] == cap - 40 and c not in res["moved"]
    with pytest.raises(GameError, match="no room"):
        go(state, type="fill_front", shop=MARKET, amounts={c: 1})


def test_sandwiches_are_made_from_bread_and_cheese_when_stocking():
    state = market_stocked()
    sandwich = next(p for p in CONFIG["shops"][MARKET]["products"] if len(CONFIG["products"][p]["uses"]) > 1)
    uses = CONFIG["products"][sandwich]["uses"]
    before = {i: logic.stock_units(state, MARKET, i) for i in uses}
    state, _ = go(state, type="fill_front", shop=MARKET, amounts={sandwich: 10})
    for item, q in uses.items():
        assert logic.stock_units(state, MARKET, item) == before[item] - 10 * q


def test_shelves_can_only_be_filled_in_the_morning():
    state = market_stocked()
    p = CONFIG["shops"][MARKET]["products"][1]
    until = CONFIG["shops"][MARKET]["mechanic"]["fill_until"]
    state, _ = go(state, t=until - 0.5, type="fill_front", shop=MARKET, amounts={p: 5})
    with pytest.raises(GameError, match="morning"):
        go(state, t=until + 0.1, type="fill_front", shop=MARKET, amounts={p: 5})


def test_students_only_buy_what_is_on_the_shelves_and_pay_at_the_checkout():
    state = market_stocked()
    a, b, _ = CONFIG["shops"][MARKET]["products"]
    state, _ = go(state, t=7.0, type="fill_front", shop=MARKET, amounts={a: 3})
    assert logic.can_make(state, MARKET, a) and not logic.can_make(state, MARKET, b)  # b is only in storage
    state, _ = go(state, t=8.0, type="tick")
    queued(state, "s5", MARKET, [a])
    state, res = go(state, t=8.2, type="checkout", shop=MARKET, student="s5", player_inside=True)
    assert res["correct"] and res["amount"] == state["shops"][MARKET]["prices"][a]
    assert logic.front_units(state, MARKET, a) == 2
    with pytest.raises(GameError, match="checkout"):
        go(state, t=8.3, type="checkout", shop="cafe", student="s6", player_inside=True)


def test_sandwiches_on_the_shelf_spoil_overnight():
    state = market_stocked()
    sandwich = next(p for p in CONFIG["shops"][MARKET]["products"] if len(CONFIG["products"][p]["uses"]) > 1)
    state, _ = go(state, type="fill_front", shop=MARKET, amounts={sandwich: 6})
    state, res = go(state, t=21.0, type="tick")
    assert res["summary"]["spoiled"].get(sandwich) == 6
    assert logic.front_units(state, MARKET, sandwich) == 0


def test_the_market_manager_shares_the_shelves():
    state = market_stocked()
    state["shops"][MARKET]["manager"] = True
    mechanics.of(MARKET).manager_fill(state)
    cap = CONFIG["shops"][MARKET]["mechanic"]["capacity"]
    filled = [logic.front_units(state, MARKET, p) for p in CONFIG["shops"][MARKET]["products"]]
    assert sum(filled) <= cap and min(filled) == cap // 3


def test_a_simulated_day_in_the_market_sells_from_the_shelves():
    state = market_stocked()
    state, _ = go(state, t=5.5, type="set_prices", shop=MARKET, prices=dict(state["shops"][MARKET]["prices"]))
    state, _ = go(state, t=6.0, type="fill_front", shop=MARKET,
                  amounts={p: 20 for p in CONFIG["shops"][MARKET]["products"]})
    state = sim.simulate_day(state, speed=8)
    assert state["summary"]["by_shop"][MARKET]["served"] > 0
