"""v7 step 4: the monopoly race - progress, buying order, victory and balance."""

import statistics

import logic
import simulation as sim
from config import CONFIG


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def next_day(state):
    state, _ = go(state, t=21.0, type="tick")
    state, _ = go(state, t=21.0, type="next_day")
    return state


def test_monopoly_progress_counts_shops_with_a_manager():
    state = logic.new_game(seed=1)
    assert logic.monopoly_progress(state) == {"done": 0, "owned": 1, "total": len(CONFIG["shops"])}
    state["money"] = 10_000_000
    state, _ = go(state, type="hire_manager", shop="cafe")
    assert logic.view(state)["monopoly"]["done"] == 1


def test_the_for_sale_sign_moves_from_shop_to_shop():
    state = logic.new_game(seed=2)
    state["money"] = 10_000_000
    state, _ = go(state, type="hire_manager", shop="cafe")
    seen = []
    for shop in logic.SHOP_ORDER[1:]:
        view = logic.view(state)
        assert view["for_sale"] == view["next_target"] == shop
        seen.append(shop)
        state, _ = go(state, type="buy_shop", shop=shop)
        assert logic.view(state)["for_sale"] is None  # nothing for sale until tomorrow
        state = next_day(state)
        state, _ = go(state, type="hire_manager", shop=shop)
    assert seen == logic.SHOP_ORDER[1:]
    assert state["status"] == logic.VICTORY
    assert logic.view(state)["next_target"] is None and logic.objective(state) == "Monopoly reached!"


def test_victory_needs_every_shop_and_every_manager():
    state = logic.new_game(seed=3)
    state["money"] = 10_000_000
    for shop in logic.SHOP_ORDER:
        state["shops"][shop].update({"owner": "player", "manager_hired": True})
    state["shops"][logic.SHOP_ORDER[-1]]["manager_hired"] = False
    logic._check_victory(state)
    assert state["status"] == logic.RUNNING
    state, _ = go(state, type="hire_manager", shop=logic.SHOP_ORDER[-1])
    assert state["status"] == logic.VICTORY


def test_balance_first_shop_and_the_days_between_purchases():
    """A short version of `uv run python simulation.py --campaign` (3 seeds)."""
    target = CONFIG["balance_target"]
    runs = [sim.simulate_campaign(seed, max_days=26) for seed in (1, 2, 3)]
    first = statistics.median(r["bought"].get("rival", 99) for r in runs)
    assert abs(first - target["first_purchase_day"]) <= 3, first
    second = statistics.median(r["bought"].get(logic.SHOP_ORDER[2], 99) for r in runs)
    assert 1 <= second - first <= 8, (first, second)
