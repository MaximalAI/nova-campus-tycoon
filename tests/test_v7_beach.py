"""v7 step 5: the beach zone - unlock, visitors, weather, Surf Shack, Praia Bar, Gelado Kiosk."""

import pytest

import logic
import mechanics
import students as st
from config import CONFIG, SUNSET
from logic import GameError

BEACH = [s for s in logic.SHOP_ORDER if CONFIG["shops"][s]["zone"] == "beach"]
CAMPUS = [s for s in logic.SHOP_ORDER if CONFIG["shops"][s]["zone"] == "campus"]
SURF = next(s for s in BEACH if CONFIG["shops"][s]["mechanic"]["type"] == "rental")
BAR = next(s for s in BEACH if CONFIG["shops"][s]["mechanic"]["type"] == "sunset_bar")
ICE = next(s for s in BEACH if CONFIG["shops"][s]["mechanic"]["type"] == "melting")


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def next_day(state):
    state, _ = go(state, t=21.0, type="tick")
    state, _ = go(state, t=21.0, type="next_day")
    return state


def own(shop, seed=41):
    state = logic.new_game(seed=seed)
    state["money"] = 1_000_000
    for s in logic.SHOP_ORDER:
        if s == shop:
            break
        state["shops"][s].update({"owner": "player", "manager": True, "manager_hired": True, "staff": False})
    state["shops"][shop].update({"owner": "player", "staff": False})
    return state


def stock(state, shop, item, units):
    state["shops"][shop]["stock"].append({"item": item, "units": units, "age": 0})


def sell(state, shop, product, t, sid="s9"):
    s = state["students"][sid]
    s["status"], s["intent"] = st.QUEUING, {"shop": shop, "items": [product]}
    state["shops"][shop]["manager"] = True  # served automatically
    state, res = go(state, t=t, type="auto_serve", shop=shop, student=sid)
    return state, res


# --- zone and visitors ------------------------------------------------------------------


def test_the_beach_opens_once_every_campus_shop_is_yours():
    state = logic.new_game(seed=1)
    state["money"] = 50_000_000
    assert not logic.zone_open(state, "beach")
    assert all(not s["presence"] for sid, s in state["schedule"].items() if sid.startswith("b"))
    for shop in CAMPUS:
        if state["shops"][shop]["owner"] != "player":
            state, _ = go(state, type="buy_shop", shop=shop)
            state = next_day(state)
        state, _ = go(state, type="hire_manager", shop=shop)
    assert logic.next_target(state) == BEACH[0]
    state, _ = go(state, type="buy_shop", shop=BEACH[0])
    state = next_day(state)
    assert logic.zone_open(state, "beach")
    assert any(s["presence"] for sid, s in state["schedule"].items() if sid.startswith("b"))


def test_the_last_campus_purchase_announces_the_beach():
    state = logic.new_game(seed=2)
    state["money"] = 50_000_000
    for shop in CAMPUS[:-1]:
        state["shops"][shop].update({"owner": "player", "manager": True, "manager_hired": True})
    state, _ = go(state, type="buy_shop", shop=CAMPUS[-1])
    state = next_day(state)
    assert state["zone_news"] == ["beach"] and logic.view(state)["zone_news"] == ["beach"]
    state = next_day(state)
    assert state["zone_news"] == []


def test_a_beach_shop_cannot_be_bought_before_the_beach_opens():
    state = logic.new_game(seed=3)
    state["money"] = 50_000_000
    for shop in CAMPUS[:-1]:
        state["shops"][shop].update({"owner": "player", "manager_hired": True})
    with pytest.raises(GameError, match="first"):
        go(state, type="buy_shop", shop=BEACH[0])


def test_beach_visitors_stay_at_the_beach():
    state = own(SURF)
    state = next_day(state)
    state, _ = go(state, t=12.0, type="tick")
    for sid, s in state["students"].items():
        if s["zone"] != "beach":
            continue
        s["status"] = st.WANDERING
        res = logic._decide(state, sid)
        if res["action"] == "shop":
            assert CONFIG["shops"][res["shop"]]["zone"] == "beach"
    campus_choice = {logic._decide(state, sid).get("shop") for sid, s in state["students"].items()
                     if s["zone"] == "campus" and s["status"] == st.OFF_MAP and not s.update(status=st.WANDERING)}
    assert not campus_choice & set(BEACH)


# --- weather ----------------------------------------------------------------------------


def test_weather_is_seeded_and_in_range():
    a, b = logic.weather_for(5, 3), logic.weather_for(5, 3)
    assert a == b
    days = [logic.weather_for(5, d) for d in range(1, 40)]
    assert {d["waves"] for d in days} <= set(range(1, 6)) and len({d["waves"] for d in days}) > 2
    assert all(16 <= d["temperature"] <= 34 for d in days)


def test_waves_and_temperature_change_the_demand():
    state = own(SURF)
    state["weather"] = {"waves": 1, "temperature": 16}
    calm_surf, cold_ice = logic.shop_factor(state, SURF), logic.shop_factor(state, ICE)
    state["weather"] = {"waves": 5, "temperature": 34}
    assert logic.shop_factor(state, SURF) == pytest.approx(calm_surf * 4)  # 0.4 -> 1.6
    assert logic.shop_factor(state, ICE) > 3 * cold_ice
    assert logic.view(state)["weather"] == {"waves": 5, "temperature": 34}


# --- Surf Shack -------------------------------------------------------------------------


def rental_products():
    rentals = CONFIG["shops"][SURF]["mechanic"]["rentals"]
    board = next(p for p in rentals if "dry_hours" not in rentals[p])
    suit = next(p for p in rentals if "dry_hours" in rentals[p])
    return board, suit


def test_a_rented_board_comes_back_after_some_hours():
    board, _ = rental_products()
    item = next(iter(CONFIG["products"][board]["uses"]))
    hours = CONFIG["shops"][SURF]["mechanic"]["rentals"][board]["hours"]
    state = own(SURF)
    stock(state, SURF, item, 1)
    state, _ = go(state, t=8.0, type="tick")
    state, res = sell(state, SURF, board, 9.0)
    assert res["items"] == [board]
    assert logic.stock_units(state, SURF, item) == 0 and not logic.can_make(state, SURF, board)
    state, _ = go(state, t=9.0 + hours - 0.5, type="tick")
    assert logic.stock_units(state, SURF, item) == 0
    state, res = go(state, t=9.0 + hours, type="tick")
    assert logic.stock_units(state, SURF, item) == 1
    assert any("returned" in t for t in res["toasts"])


def test_a_wetsuit_dries_before_the_next_rental():
    _, suit = rental_products()
    rule = CONFIG["shops"][SURF]["mechanic"]["rentals"][suit]
    item = next(iter(CONFIG["products"][suit]["uses"]))
    state = own(SURF)
    stock(state, SURF, item, 1)
    state, _ = go(state, t=8.0, type="tick")
    state, _ = sell(state, SURF, suit, 9.0)
    state, _ = go(state, t=9.0 + rule["hours"], type="tick")
    view = logic.view(state)["shops"][SURF]["mech"]
    assert len(view["drying"]) == 1 and logic.stock_units(state, SURF, item) == 0
    state, res = go(state, t=9.0 + rule["hours"] + rule["dry_hours"], type="tick")
    assert logic.stock_units(state, SURF, item) == 1 and any("dry again" in t for t in res["toasts"])


def test_rentals_return_overnight_and_the_shopping_list_counts_turns():
    board, _ = rental_products()
    item = next(iter(CONFIG["products"][board]["uses"]))
    turns = CONFIG["shops"][SURF]["mechanic"]["turns_per_day"]
    state = own(SURF)
    stock(state, SURF, item, 2)
    state, _ = go(state, t=8.0, type="tick")
    state, _ = sell(state, SURF, board, 19.5)
    assert logic.shopping_list(state, {board: 2 * turns}, SURF) == {}  # the rented board still counts
    assert logic.shopping_list(state, {board: 3 * turns}, SURF) == {item: 1}
    state, _ = go(state, t=21.0, type="tick")
    assert logic.stock_units(state, SURF, item) == 2


def test_the_instructor_is_booked_for_one_day():
    cls = next(p for p in CONFIG["shops"][SURF]["products"] if p not in CONFIG["shops"][SURF]["mechanic"]["rentals"])
    item = next(iter(CONFIG["products"][cls]["uses"]))
    assert CONFIG["wholesale_items"][item]["shelf_days"] == 1
    state = own(SURF)
    stock(state, SURF, item, CONFIG["wholesale_items"][item]["base_units"])
    state = next_day(state)
    assert logic.stock_units(state, SURF, item) == 0


def test_expensive_beach_products_have_their_own_price_limit():
    cls = max(CONFIG["shops"][SURF]["products"], key=lambda p: CONFIG["products"][p].get("max_price", 0))
    state = own(SURF)
    state, _ = go(state, type="set_prices", shop=SURF, prices={cls: 3_000})
    with pytest.raises(GameError, match="between"):
        go(state, type="set_prices", shop="cafe", prices={"coffee": 3_000})


# --- Praia Bar --------------------------------------------------------------------------


def test_the_bar_opens_at_sunset():
    assert CONFIG["shops"][BAR]["open_hours"][0] == SUNSET == 17.5
    state = own(BAR)
    state, _ = go(state, t=12.0, type="tick")
    assert logic.shop_operating(state, BAR) and not logic.shop_open_now(state, BAR)
    state, res = go(state, t=SUNSET, type="tick")
    assert logic.shop_open_now(state, BAR)
    assert CONFIG["shops"][BAR]["mechanic"]["toast"] in res["toasts"]


def test_happy_hour_lowers_the_prices_for_one_hour():
    state = own(BAR)
    product = CONFIG["shops"][BAR]["products"][0]
    base = state["shops"][BAR]["prices"][product]
    for item, q in CONFIG["products"][product]["uses"].items():
        stock(state, BAR, item, 5 * q)
    state, _ = go(state, t=10.0, type="set_happy_hour", shop=BAR, discount=0.4)
    state, _ = go(state, t=SUNSET + 0.5, type="tick")
    assert logic.price_now(state, BAR, product) == int(base * 0.6 // 10) * 10
    assert logic.shop_factor(state, BAR) > CONFIG["shops"][BAR]["base_factor"] * state["rep_factor"]
    state, res = sell(state, BAR, product, SUNSET + 0.6)
    assert res["amount"] == int(base * 0.6 // 10) * 10
    state, _ = go(state, t=SUNSET + 1.0, type="tick")
    assert logic.price_now(state, BAR, product) == base


def test_happy_hour_rules():
    state = own(BAR)
    with pytest.raises(GameError, match="between"):
        go(state, t=10.0, type="set_happy_hour", shop=BAR, discount=0.9)
    with pytest.raises(GameError, match="steps"):
        go(state, t=10.0, type="set_happy_hour", shop=BAR, discount=0.33)
    with pytest.raises(GameError, match="before the bar opens"):
        go(state, t=SUNSET + 0.1, type="set_happy_hour", shop=BAR, discount=0.2)
    with pytest.raises(GameError, match="no happy hour"):
        go(state, t=10.0, type="set_happy_hour", shop="cafe", discount=0.2)


# --- Gelado Kiosk -----------------------------------------------------------------------


def ice_ready(t=8.0):
    state = own(ICE)
    for p in CONFIG["shops"][ICE]["products"]:
        for item, q in CONFIG["products"][p]["uses"].items():
            stock(state, ICE, item, 40 * q)
    state, _ = go(state, t=t, type="tick")
    return state


def test_ice_cream_in_the_display_melts_after_a_few_hours():
    state = ice_ready()
    scoop = CONFIG["shops"][ICE]["mechanic"]["front"][0]
    melt = CONFIG["shops"][ICE]["mechanic"]["melt_hours"]
    state, _ = go(state, t=9.0, type="fill_front", shop=ICE, amounts={scoop: 10})
    assert logic.portions(state, ICE, scoop) == 10
    state, _ = go(state, t=9.0 + melt - 0.5, type="tick")
    assert logic.portions(state, ICE, scoop) == 10
    state, res = go(state, t=9.0 + melt, type="tick")
    assert logic.portions(state, ICE, scoop) == 0 and any("melted" in t for t in res["toasts"])


def test_the_freezer_keeps_and_the_display_melts_overnight():
    state = ice_ready()
    scoop = CONFIG["shops"][ICE]["mechanic"]["front"][0]
    item = next(iter(CONFIG["products"][scoop]["uses"]))
    state, _ = go(state, t=19.0, type="fill_front", shop=ICE, amounts={scoop: 5})
    left = logic.stock_units(state, ICE, item)
    state, res = go(state, t=21.0, type="tick")
    assert res["summary"]["spoiled_value"] >= round(5 * logic.unit_cost(scoop))
    assert logic.stock_units(state, ICE, item) == left  # the freezer keeps


def test_iced_coffee_uses_the_freezer_not_the_display():
    state = ice_ready()
    coffee = next(p for p in CONFIG["shops"][ICE]["products"] if len(CONFIG["products"][p]["uses"]) == 2)
    assert coffee not in mechanics.of(ICE).front_products()
    assert logic.can_make(state, ICE, coffee)


def test_the_gelado_manager_keeps_the_display_half_full():
    state = ice_ready()
    state["shops"][ICE]["manager"] = True
    state, _ = go(state, t=9.0, type="tick")
    half = CONFIG["shops"][ICE]["mechanic"]["capacity"] // 2
    for p in CONFIG["shops"][ICE]["mechanic"]["front"]:
        assert logic.front_units(state, ICE, p) == half
