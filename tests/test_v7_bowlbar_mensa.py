"""v7 step 3: Bowl Bar (assembly of two-ingredient products) and Nova Mensa (lunch rush)."""

import pytest

import logic
import mechanics
import simulation as sim
import students as st
from config import CONFIG
from logic import GameError

BOWL = next(s for s, spec in CONFIG["shops"].items() if spec["mechanic"]["type"] == "assembly")
MENSA = next(s for s, spec in CONFIG["shops"].items() if spec["mechanic"]["type"] == "lunch_rush")


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def own(shop, seed=31):
    state = logic.new_game(seed=seed)
    state["money"] = 500_000
    for s in logic.SHOP_ORDER:
        if s == shop:
            break
        state["shops"][s].update({"owner": "player", "manager": True, "manager_hired": True, "staff": False})
    state["shops"][shop].update({"owner": "player", "staff": False})
    for p in CONFIG["shops"][shop]["products"]:
        for item, q in CONFIG["products"][p]["uses"].items():
            state["shops"][shop]["stock"].append({"item": item, "units": 20 * q, "age": 0})
    return state


def with_order(state, shop, items, t):
    state, _ = go(state, t=t, type="tick")
    s = state["students"]["s7"]
    s["status"], s["intent"] = st.QUEUING, {"shop": shop, "items": list(items)}
    state, _ = go(state, t=t + 0.01, type="accept", shop=shop, student="s7", player_inside=True)
    return state


# --- Bowl Bar ---------------------------------------------------------------------------


def two_ingredient_product():
    return next(p for p in CONFIG["shops"][BOWL]["products"] if len(CONFIG["products"][p]["uses"]) == 2)


def test_the_right_ingredients_make_the_product():
    poke = two_ingredient_product()
    state = with_order(own(BOWL), BOWL, [poke], 8.0)
    uses = list(CONFIG["products"][poke]["uses"])
    before = {i: logic.stock_units(state, BOWL, i) for i in uses}
    state, res = go(state, t=8.1, type="assemble", shop=BOWL, ingredients=uses, player_inside=True)
    assert res["product"] == poke and state["tray"] == [poke]
    assert all(logic.stock_units(state, BOWL, i) == before[i] - 1 for i in uses)
    state, res = go(state, t=8.2, type="handover", shop=BOWL, student="s7", player_inside=True)
    assert res["correct"]


def test_a_wrong_set_is_a_wrong_bowl_and_a_wrong_order():
    poke = two_ingredient_product()
    state = with_order(own(BOWL), BOWL, [poke], 8.0)
    one = list(CONFIG["products"][poke]["uses"])[:1]
    other = next(i for i in CONFIG["shops"][BOWL]["mechanic"]["ingredients"] if i not in CONFIG["products"][poke]["uses"])
    state, res = go(state, t=8.1, type="assemble", shop=BOWL, ingredients=one + [other], player_inside=True)
    wrong = CONFIG["shops"][BOWL]["mechanic"]["wrong"]
    assert res["product"] == wrong and res["toast"] == "Wrong bowl"
    rep = state["reputation"]
    state, res = go(state, t=8.2, type="handover", shop=BOWL, student="s7", player_inside=True)
    assert not res["correct"] and state["reputation"] < rep
    assert state["stats"]["shops"][BOWL]["wrong"] == 1


def test_one_ingredient_alone_is_also_wrong_for_a_two_ingredient_bowl():
    poke = two_ingredient_product()
    state = with_order(own(BOWL), BOWL, [poke], 8.0)
    first = next(iter(CONFIG["products"][poke]["uses"]))
    state, res = go(state, t=8.1, type="assemble", shop=BOWL, ingredients=[first], player_inside=True)
    assert res["product"] == CONFIG["shops"][BOWL]["mechanic"]["wrong"]


def test_assembly_rules():
    poke = two_ingredient_product()
    state = own(BOWL)
    with pytest.raises(GameError):  # no order yet
        go(state, t=8.0, type="assemble", shop=BOWL, ingredients=list(CONFIG["products"][poke]["uses"]), player_inside=True)
    state = with_order(state, BOWL, [poke], 8.0)
    with pytest.raises(GameError, match="Pick"):
        go(state, t=8.1, type="assemble", shop=BOWL, ingredients=["coffee_beans"], player_inside=True)
    with pytest.raises(GameError, match="station"):
        go(state, t=8.1, type="prepare", shop=BOWL, product=poke, player_inside=True)
    state["shops"][BOWL]["stock"] = []
    with pytest.raises(GameError, match="Out of"):
        go(state, t=8.1, type="assemble", shop=BOWL, ingredients=list(CONFIG["products"][poke]["uses"]), player_inside=True)


def test_staff_always_assemble_correctly():
    poke = two_ingredient_product()
    state = own(BOWL)
    state["shops"][BOWL]["manager"] = True
    state, _ = go(state, t=8.0, type="tick")
    s = state["students"]["s8"]
    s["status"], s["intent"] = st.QUEUING, {"shop": BOWL, "items": [poke]}
    state, res = go(state, t=8.1, type="auto_serve", shop=BOWL, student="s8")
    assert res["items"] == [poke] and res["rep_delta"] >= 0


# --- Nova Mensa -------------------------------------------------------------------------


def test_the_mensa_only_takes_customers_at_lunch():
    state = own(MENSA)
    a, b = CONFIG["shops"][MENSA]["open_hours"]
    state, _ = go(state, t=8.0, type="tick")
    assert logic.shop_operating(state, MENSA) and not logic.shop_open_now(state, MENSA)
    state, _ = go(state, t=a, type="tick")
    assert logic.shop_open_now(state, MENSA)
    state, _ = go(state, t=b, type="tick")
    assert not logic.shop_open_now(state, MENSA)
    assert logic.view(state)["shops"][MENSA]["open_now"] is False


def test_students_do_not_choose_a_closed_mensa():
    state, _ = go(logic.new_game(seed=12), t=9.0, type="tick")
    for sid in state["students"]:
        state["students"][sid]["status"] = st.WANDERING
        state["students"][sid]["utilities"] = {k: (2_000 if k.startswith(MENSA) else 1) for k in state["students"][sid]["utilities"]}
        res = logic._decide(state, sid)
        assert res.get("shop") != MENSA
        state["students"][sid]["status"] = st.WANDERING
    state["time"] = 12.5
    res = logic._decide(state, "s0")
    assert res["shop"] == MENSA


def test_lunch_rush_announces_itself_and_draws_students():
    state = own(MENSA)
    state, _ = go(state, t=11.0, type="tick")
    factor = logic.shop_factor(state, MENSA)
    state, res = go(state, t=12.0, type="tick")
    assert CONFIG["shops"][MENSA]["mechanic"]["toast"] in res.get("toasts", [])
    assert logic.shop_factor(state, MENSA) == pytest.approx(factor * CONFIG["shops"][MENSA]["mechanic"]["rush_factor"])
    state, res = go(state, t=13.0, type="tick")
    assert CONFIG["shops"][MENSA]["mechanic"]["toast"] not in res.get("toasts", [])  # once per day


def test_the_mensa_queue_is_long_and_the_rush_is_busy():
    assert CONFIG["shops"][MENSA]["max_queue"] == 8 > CONFIG["max_queue"]
    state = own(MENSA)
    state["shops"][MENSA]["manager"] = True
    state = sim.simulate_day(state, speed=8)
    served = state["stats"]["shops"][MENSA]["served"]
    assert served >= 15, served


def test_objective_before_the_mensa_opens():
    state = own(MENSA)
    state, _ = go(state, t=7.0, type="stock_goods", shop=MENSA) if state["bag"] else (state, None)
    state["day_state"] = logic.SET_PRICES
    assert "opens at 11:30" in logic.objective(state)
    assert mechanics.of(MENSA).view(state)["in_rush"] is False
