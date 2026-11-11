"""V6 rules: the bought café becomes yours the next morning, objectives, open mode."""

import logic
from config import CONFIG


def go(state, t, **event):
    return logic.apply(state, dict(event, t=t))


def next_day(state):
    state, _ = go(state, 21.0, type="tick")
    state, _ = go(state, 21.0, type="next_day")
    return state


def rich_with_manager():
    state = logic.new_game(seed=5)
    state["money"] = 200_000
    state, _ = go(state, 6.0, type="hire_manager", shop="cafe")
    return next_day(state)  # the manager works from today


def test_objective_while_the_purchase_is_pending():
    state = rich_with_manager()
    assert "buy the competitor" in logic.objective(state)
    state, _ = go(state, 9.0, type="buy_competitor")
    text = logic.objective(state)
    assert "Tomorrow you start in" in text and CONFIG["shops"]["rival"]["name"] in text


def test_objective_after_the_takeover_says_who_runs_what():
    state = rich_with_manager()
    state, _ = go(state, 9.0, type="buy_competitor")
    state = next_day(state)
    assert logic.work_shop(state) == "rival"
    text = logic.objective(state)
    assert "both cafés" not in text
    assert CONFIG["shops"]["rival"]["name"] in text


def test_competitor_keeps_selling_on_the_day_of_the_purchase():
    state = rich_with_manager()
    state, _ = go(state, 8.0, type="tick")
    state, _ = go(state, 9.0, type="buy_competitor")
    assert logic.is_auto(state, "rival") and logic.shop_operating(state, "rival")
    assert state["shops"]["rival"]["owner"] == "bot"
    s = state["students"]["s1"]
    s["status"], s["intent"] = "queuing", {"shop": "rival", "items": ["tea"]}
    state, res = go(state, 9.1, type="auto_serve", shop="rival", student="s1")
    assert res["items"] == ["tea"]
    assert state["stats"]["rival_revenue"] == CONFIG["shops"]["rival"]["start_prices"]["tea"]


def test_victory_dialog_can_be_followed_by_open_mode():
    state = rich_with_manager()
    state, _ = go(state, 9.0, type="buy_competitor")
    state = next_day(state)
    state, _ = go(state, 9.0, type="hire_manager", shop="rival")
    assert state["status"] == logic.VICTORY
    state, _ = go(state, 9.1, type="continue_open_mode")
    state = next_day(state)
    assert state["status"] == logic.RUNNING
    assert logic.objective(state) == "Your managers run both cafés."


def test_a_newly_hired_manager_already_cleans_tonight():
    state = logic.new_game(seed=6)
    state["money"] = 100_000
    state, _ = go(state, 9.0, type="hire_manager", shop="cafe")
    state, _ = go(state, 20.0, type="tick")
    assert "manager cleans" in logic.objective(state)
