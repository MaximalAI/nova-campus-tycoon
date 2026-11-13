"""V10 rules: upgrades per shop, cleaning per shop, the vending manager, Mercado & Go."""

import pytest

import logic
import mechanics
from config import CONFIG
from logic import GameError

MARKET = "mercado"


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def owning(*shops, managers=(), seed=10, money=900_000):
    """A game where the player owns these shops (and these have a working manager)."""
    state = logic.new_game(seed=seed)
    state["money"] = money
    for s in shops:
        state["shops"][s]["owner"] = "player"
    for s in managers:
        state["shops"][s]["manager"] = state["shops"][s]["manager_hired"] = True
    logic._start_day(state, 1)
    return state


# ------------------------------------------------------------ upgrades


def test_every_shop_has_three_upgrades_that_fit_it():
    for shop, spec in CONFIG["shops"].items():
        assert len(spec["upgrades"]) == 3, shop
    assert "coffee_machine" in CONFIG["shops"]["cafe"]["upgrades"]
    assert "coffee_machine" not in CONFIG["shops"]["snackbots"]["upgrades"]  # no coffee there
    assert "coffee_machine" not in CONFIG["shops"][MARKET]["upgrades"]


def test_a_shop_only_sells_its_own_upgrades():
    state = owning("cafe", "snackbots", managers=["cafe"])
    with pytest.raises(GameError, match="does not fit"):
        go(state, type="buy_upgrade", shop="snackbots", upgrade="coffee_machine")
    before = logic.shop_factor(state, "snackbots")
    state, _ = go(state, type="buy_upgrade", shop="snackbots", upgrade="card_reader")
    bonus = CONFIG["shops"]["snackbots"]["upgrades"]["card_reader"]["factor_bonus"]
    assert logic.shop_factor(state, "snackbots") == pytest.approx(before + bonus * state["rep_factor"], abs=1e-3)


def test_old_upgrades_become_the_same_tier_of_the_new_list():
    state = owning("cafe", "snackbots", managers=["cafe"])
    state["shops"]["snackbots"]["upgrades"] = ["coffee_machine", "branding"]
    state = logic.migrate(state)
    assert state["shops"]["snackbots"]["upgrades"] == ["card_reader", "branding"]
    assert state["shops"]["cafe"]["upgrades"] == []


# ------------------------------------------------------------ cleaning


def closing(state):
    state, _ = go(state, t=20.0, type="tick")
    assert state["day_state"] == logic.CLOSING
    return state


def test_every_staffed_shop_is_cleaned_after_closing_but_not_the_vending_shop():
    state = closing(owning("cafe", "rival", "snackbots", MARKET, managers=["cafe", "rival", "snackbots"]))
    assert set(state["cleaning"]) == {"cafe", "rival", MARKET}
    assert set(state["cleaning"][MARKET]) == set(CONFIG["shops"][MARKET]["cleaning"])


def test_the_player_cleans_the_shop_he_ran():
    state = closing(owning("cafe", "rival", "snackbots", MARKET, managers=["cafe", "rival", "snackbots"]))
    assert "Clean up Mercado & Go" in logic.view(state)["objective"]
    with pytest.raises(GameError, match="Unknown cleaning spot"):
        go(state, t=20.1, type="clean", shop=MARKET, spot="coffee_machine")
    with pytest.raises(GameError, match="does not need cleaning"):
        go(state, t=20.1, type="clean", shop="gelado", spot="floor")
    for spot in CONFIG["shops"][MARKET]["cleaning"]:
        state, _ = go(state, t=20.1, type="clean", shop=MARKET, spot=spot)
    assert all(state["cleaning"][MARKET].values())
    assert state["day_state"] == logic.CLOSING  # the managers are still busy
    for shop in ("cafe", "rival"):
        for spot in state["cleaning"][shop]:
            state, _ = go(state, t=20.3, type="clean", shop=shop, spot=spot, manager=True)
    assert state["day_state"] == logic.DAY_SUMMARY  # everything clean: the day ends


def test_a_dirty_shop_costs_reputation_only_when_it_was_yours_to_clean():
    state = closing(owning("cafe", "rival", MARKET, managers=["cafe", "rival"]))
    rep = state["reputation"]
    state, _ = go(state, t=21.0, type="tick")  # nobody cleaned
    assert state["reputation"] == rep + CONFIG["reputation"]["cleaning_missed"]  # once: Mercado
    assert all(all(spots.values()) for s, spots in state["cleaning"].items() if s != MARKET)


def test_v9_saves_keep_the_cafe_cleaning():
    state = owning("cafe")
    state["cleaning"] = {"counter": True, "coffee_machine": False, "tables": False, "floor": False}
    state = logic.migrate(state)
    assert state["cleaning"] == {"cafe": {"counter": True, "coffee_machine": False, "tables": False, "floor": False}}


# ------------------------------------------------------------ vending manager


def test_the_vending_manager_plans_enough_for_every_machine():
    state = owning("cafe", "snackbots", managers=["cafe", "snackbots"])
    plan = state["manager_proposals"]["snackbots"]["plan"]
    m = CONFIG["shops"]["snackbots"]["mechanic"]
    assert all(n >= m["capacity"] * len(m["machines"]) for n in plan.values())


def test_the_vending_manager_fills_all_machines_evenly():
    state = owning("cafe", "snackbots", managers=["cafe", "snackbots"])
    state, _ = go(state, t=CONFIG["time"]["manager_buys_at"], type="tick")
    state, _ = go(state, t=CONFIG["time"]["open"] + 0.5, type="tick")  # v11: the fallback round (no browser here)
    machines = mechanics.of("snackbots").machines(state)
    for product in CONFIG["shops"]["snackbots"]["products"]:
        counts = [m["stock"].get(product, 0) for m in machines.values()]
        assert max(counts) - min(counts) <= 1 and sum(counts) > 0, (product, counts)


def test_refilling_all_machines_shares_the_goods_out():
    state = owning("cafe", "snackbots", managers=["cafe"])
    logic._add_stock(state, "snackbots", "water", 12)  # one pack for three machines
    moved = mechanics.of("snackbots").refill(state, None)
    assert moved["water"] == 12
    assert sorted(m["stock"].get("water", 0) for m in mechanics.of("snackbots").machines(state).values()) == [4, 4, 4]


# ------------------------------------------------------------ Mercado & Go


def market_morning():
    state = owning("cafe", MARKET, managers=["cafe"])
    for item, units in {"bread": 20, "cheese": 40, "iced_tea": 24, "apples": 24}.items():
        logic._add_stock(state, MARKET, item, units)
    state["day_state"] = logic.SET_PRICES
    return state


def test_the_objective_leads_through_the_mercado_steps():
    state = market_morning()
    assert "on the shelves" in logic.view(state)["objective"]
    state, _ = go(state, t=6.5, type="fill_front", shop=MARKET)
    assert "prices" in logic.view(state)["objective"]
    state["shops"][MARKET]["front"]["apple"] = []
    state["day_state"] = logic.SHOP_OPEN
    assert "Shelf empty: Apple" in logic.view(state)["objective"]


def test_a_customer_who_finds_part_of_his_order_missing_costs_reputation():
    state = market_morning()
    state, _ = go(state, t=7.0, type="fill_front", shop=MARKET, amounts={"apple": 5})
    state, _ = go(state, t=8.0, type="tick")
    sid = "s3"
    student = state["students"][sid]
    for p in CONFIG["shops"][MARKET]["products"]:  # wants an apple most, a sandwich too
        student["utilities"][f"{MARKET}:{p}"] = 900 if p == "apple" else 600 if p == "sandwich" else 0
    student["status"], student["intent"] = "queuing", {"shop": MARKET, "items": ["sandwich", "apple"]}
    rep = state["reputation"]
    state, res = go(state, t=8.1, type="at_counter", shop=MARKET, student=sid)
    assert res["items"] == ["apple"] and res["sold_out"] == ["sandwich"]
    assert res["rep_delta"] == CONFIG["reputation"]["sold_out_partial"]
    assert state["reputation"] == rep + CONFIG["reputation"]["sold_out_partial"]
