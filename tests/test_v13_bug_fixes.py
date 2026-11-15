"""V13: fixes from the playtest bug hunt (see specs/v13-playtest-bug-fixes.md)."""

import math

import pytest

import logic
import mechanics
import students as st
from config import CONFIG

SURF = "surf_shack"


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def next_day(state):
    state, _ = go(state, 21.0, type="tick")
    state, _ = go(state, 21.0, type="next_day")
    return state


@pytest.fixture
def managed_cafe():
    state = logic.new_game(seed=13)
    state["money"] = 500_000
    state, _ = go(state, type="hire_manager", shop="cafe")
    return state


def owning(managed, seed=13, money=900_000):
    """Own every shop up to the last of ``managed``, all of them with a manager."""
    state = logic.new_game(seed=seed)
    state["money"] = money
    for s in logic.SHOP_ORDER:
        state["shops"][s].update({"owner": "player", "manager": True, "manager_hired": True, "staff": False})
        if s == managed[-1]:
            break
    return state


# ------------------------------------------------------------ bug 1: plans explode


def test_sold_out_customers_count_half_and_the_plan_is_capped(managed_cafe):
    state = managed_cafe
    state["stats"]["shops"]["cafe"]["sold"] = {"coffee": 10, "orange_juice": 10, "pastel_de_nata": 10}
    state["stats"]["shops"]["cafe"]["sold_out_products"] = {"coffee": 100}
    state = next_day(state)
    plan = state["manager_proposals"]["cafe"]["plan"]
    # before v13: (10 + 100) * 1.5 = 165 coffees; now at most 1.5 x the best day
    assert plan["coffee"] == math.ceil(10 * CONFIG["manager"]["max_vs_best_day"])


def test_the_cap_grows_with_the_best_day_ever(managed_cafe):
    state = managed_cafe
    state["stats"]["shops"]["cafe"]["sold"] = {"coffee": 40}
    state = next_day(state)
    state["stats"]["shops"]["cafe"]["sold"] = {"coffee": 10}
    state["stats"]["shops"]["cafe"]["sold_out_products"] = {"coffee": 40}
    state = next_day(state)
    # (10 + 40 / 2) * 1.5 = 45, below the cap of 1.5 x 40 = 60
    assert state["manager_proposals"]["cafe"]["plan"]["coffee"] == 45


# ------------------------------------------------------------ bug 2: cash runs out


def test_a_short_budget_buys_complete_portions(managed_cafe):
    state = next_day(managed_cafe)
    proposal = state["manager_proposals"]["cafe"]
    proposal["plan"] = {"coffee": 40, "orange_juice": 40, "pastel_de_nata": 40}
    proposal["shopping_list"] = logic.shopping_list(state, proposal["plan"], "cafe")
    full = logic.cart_total(proposal["shopping_list"])
    state["money"] = full // 2
    state, res = go(state, t=5.5, type="confirm_manager_plan", shop="cafe")
    assert 0 < res["share"] < 1 and "only buy" in res["toast"]
    assert state["money"] >= 0
    # every product can be made: the money was not spent on one item only
    assert all(logic.can_make(state, "cafe", p) for p in ("coffee", "orange_juice", "pastel_de_nata"))


def test_at_seven_the_money_is_shared_between_all_managers():
    state = owning(["cafe", "rival", "snackbots", "mercado", "bowl_bar"])
    state["stats"]["shops"]["bowl_bar"]["sold"] = {"poke_bowl": 30, "acai_bowl": 30, "smoothie": 30}
    state = next_day(state)
    todo = state["manager_proposals"]
    total = sum(p["cost"] for p in todo.values())
    state["money"] = total // 3
    state, res = go(state, t=7.0, type="tick")
    assert all(p["done"] for p in state["manager_proposals"].values())
    # the last shop in the buying order still got its share (it used to get nothing)
    assert state["manager_proposals"]["bowl_bar"]["paid"] > 0
    assert "Not enough cash" in res["toast"]


def test_accept_all_shares_the_money_too():
    state = owning(["cafe", "rival", "snackbots", "mercado", "bowl_bar"])
    state["stats"]["shops"]["bowl_bar"]["sold"] = {"poke_bowl": 30, "acai_bowl": 30, "smoothie": 30}
    state = next_day(state)
    total = sum(p["cost"] for p in state["manager_proposals"].values())
    state["money"] = total // 2
    state, res = go(state, t=5.5, type="confirm_all_manager_plans")
    assert set(res["manager_bought"]) == set(state["manager_proposals"])
    assert state["manager_proposals"]["bowl_bar"]["paid"] > 0
    with pytest.raises(logic.GameError, match="already"):
        go(state, t=5.6, type="confirm_all_manager_plans")


def test_enough_money_buys_the_whole_plan(managed_cafe):
    state = next_day(managed_cafe)
    state, res = go(state, t=7.0, type="tick")
    proposal = state["manager_proposals"]["cafe"]
    assert proposal["share"] == 1 and "bought supplies" in res["toast"]


# ------------------------------------------------------------ bug 3: reputation swings


def queuing(state, n, shop="cafe"):
    sids = list(state["students"])[:n]
    for sid in sids:
        state["students"][sid]["status"] = st.QUEUING
    return sids


def test_customers_who_wait_too_long_cost_at_most_the_daily_cap():
    state = logic.new_game(seed=13)
    state["reputation"] = 90
    for sid in queuing(state, 20):
        state, _ = go(state, t=9.0, type="patience_expired", student=sid, shop="cafe")
    assert state["reputation"] == 90 - CONFIG["reputation"]["customer_daily_cap"]
    state = next_day(state)  # a new day: the cap starts again
    sid = queuing(state, 1)[0]
    before = state["reputation"]
    state, res = go(state, t=9.0, type="patience_expired", student=sid, shop="cafe")
    assert res["rep_delta"] == CONFIG["reputation"]["customer_lost"] and state["reputation"] < before


def test_waiting_losses_and_staff_gains_share_one_net_budget():
    state = logic.new_game(seed=13)
    state["reputation"] = 50
    cap = CONFIG["reputation"]["customer_daily_cap"]
    for _ in range(40):  # 40 happy manager customers: at most +cap
        logic._customer_reputation(state, 1)
    assert state["reputation"] == 50 + cap
    for _ in range(3):  # losses first use up the day's gains ...
        logic._customer_reputation(state, -3)
    assert state["reputation"] == 50 + cap - 9
    for _ in range(40):  # ... and the net change never goes below -cap
        logic._customer_reputation(state, -3)
    assert state["reputation"] == 50 - cap
    for _ in range(40):  # gains make up for losses again
        logic._customer_reputation(state, 1)
    assert state["reputation"] == 50 + cap


# ------------------------------------------------------------ bug 4: buying leaves you broke


def test_the_view_estimates_tomorrows_manager_costs():
    state = owning(["cafe"])
    state["stats"]["shops"]["cafe"]["sold"] = {"coffee": 30, "orange_juice": 20, "pastel_de_nata": 20}
    state = next_day(state)
    before = logic.manager_cost_estimate(state)  # not bought yet: today's proposal
    assert before == state["manager_proposals"]["cafe"]["cost"] > 0
    state, _ = go(state, t=7.0, type="tick")
    # bought this morning: tomorrow he needs about the same again
    assert logic.manager_cost_estimate(state) == state["manager_proposals"]["cafe"]["paid"] > 0
    v = logic.view(state)
    assert v["manager_cost_estimate"] == (logic.manager_cost_estimate(state) if v["for_sale"] else 0)


# ------------------------------------------------------------ bug 5: flat sea


def surf_owned(waves):
    state = owning(logic.SHOP_ORDER[:logic.SHOP_ORDER.index(SURF) + 1])
    state["weather"] = {"waves": waves, "temperature": 25}
    return state


def test_flat_sea_means_fewer_surfers_not_lower_prices():
    calm, normal = surf_owned(1), surf_owned(3)
    assert mechanics.of(SURF).visit_chance(calm) == pytest.approx(CONFIG["weather"]["wave_factor"]["1"])
    assert mechanics.of(SURF).visit_chance(normal) == 1.0
    assert logic.shop_factor(calm, SURF) == logic.shop_factor(normal, SURF)  # same willingness to pay
    sids = [f"s{i}" for i in range(2000)]
    share = sum(logic._comes_today(calm, sid, SURF) for sid in sids) / len(sids)
    assert share == pytest.approx(0.4, abs=0.05)
    # the same student decides the same way all day
    assert [logic._comes_today(calm, s, SURF) for s in sids[:50]] == [logic._comes_today(calm, s, SURF) for s in sids[:50]]
    assert all(logic._comes_today(normal, s, SURF) for s in sids[:50])


def test_the_surf_manager_plans_with_the_waves():
    state = surf_owned(3)
    yesterday = {"day": 4, "by_shop": {SURF: {"sold": {"surf_rental": 20, "wetsuit_rental": 20, "surf_class": 20},
                                              "sold_out_products": {}}}}
    state["history"] = [yesterday]
    state["day"] = 5
    ratio = mechanics.of(SURF).plan_scale(state, 4)
    plan = logic.manager_proposal(state, SURF)["plan"]
    assert plan["surf_rental"] == max(CONFIG["manager"]["min_portions"], math.ceil(20 * CONFIG["manager"]["buffer"] * ratio))
    w = CONFIG["weather"]["wave_factor"]
    assert ratio == pytest.approx(w["3"] / w[str(logic.weather_for(state["seed"], 4)["waves"])])


# ------------------------------------------------------------ bug 7: objective after saving prices


def test_the_objective_moves_on_once_the_prices_are_saved():
    state = logic.new_game(seed=13)
    state["day_state"] = logic.SET_PRICES
    assert "Set your prices" in logic.objective(state)
    state["shops"]["cafe"]["prices_set"] = True
    assert logic.objective(state) == "Prices set - open the café at the counter."
