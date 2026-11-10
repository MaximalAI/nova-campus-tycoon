"""Batches of browser events (docs/architecture.md)."""

import bridge
import logic


def test_batch_runs_in_order_and_reports_errors():
    state = logic.new_game(seed=1)
    events = [
        {"cid": 1, "type": "confirm_plan", "plan": {"coffee": 10}, "t": 5.1},
        {"cid": 2, "type": "pay", "t": 5.2},  # not in the wholesaler yet
        {"cid": 3, "type": "enter_wholesaler", "t": 5.6},
        {"cid": 4, "type": "set_cart_item", "item": "coffee_beans", "qty": 1, "t": 5.65},
        {"cid": 5, "type": "pay", "t": 5.7},
    ]
    new, results = bridge.process_batch(state, events)
    assert [r["ok"] for r in results] == [True, False, True, True, True]
    assert results[1]["error"] == "You are not inside the wholesaler."
    assert new["bag"] == {"coffee_beans": 1}
    assert new["money"] == 5_000 - 400
    assert state["money"] == 5_000  # input untouched


def test_unknown_event_is_an_error_not_a_crash():
    _, results = bridge.process_batch(logic.new_game(seed=1), [{"cid": 9, "type": "teleport"}])
    assert results == [{"cid": 9, "ok": False, "error": "Unknown event: teleport."}]


def test_time_never_runs_backwards():
    state = logic.new_game(seed=1)
    state, _ = bridge.process_batch(state, [{"cid": 1, "type": "tick", "t": 9.0}])
    state, _ = bridge.process_batch(state, [{"cid": 2, "type": "tick", "t": 8.5}])
    assert state["time"] == 9.0
