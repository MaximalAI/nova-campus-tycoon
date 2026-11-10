"""Student pool, schedule, state machine and decisions (brief section 8)."""

import pytest

import logic
import simulation as sim
import students as st
import timeclock as tc
from config import CONFIG


@pytest.fixture
def schedule():
    return st.make_schedule(seed=7, day=1)


def test_pool_has_25_students_with_budget_utilities_and_traits():
    pool = st.make_pool(seed=1, day=1)
    assert len(pool) == 25
    for s in pool.values():
        assert s["budget"] == CONFIG["students"]["budget"]
        assert len(s["utilities"]) == 6
        assert all(30 <= u <= 300 for u in s["utilities"].values())
        assert 30 <= s["traits"]["patience"] <= 60
        assert s["status"] == st.OFF_MAP


def test_utilities_are_new_every_day_and_reproducible():
    day1, day2 = st.make_pool(1, 1), st.make_pool(1, 2)
    assert day1["s0"]["utilities"] != day2["s0"]["utilities"]
    assert st.make_pool(1, 1) == day1


def test_never_more_than_25_on_the_map(schedule):
    t = 5.0
    while t < 21.0:
        assert st.on_map_count(schedule, t) <= 25
        t += 1 / 60


def test_cap_holds_even_when_the_phase_table_asks_for_more():
    phases = [{"name": "x", "from": 5.0, "to": 21.0, "target": 60, "cafe_probability": 1.0}]
    schedule = st.make_schedule(seed=3, day=1, phases=phases)
    for minute in range(0, 16 * 60, 5):
        assert st.on_map_count(schedule, 5.0 + minute / 60) <= 25


@pytest.mark.parametrize("t", [7.9, 8.75, 10.5, 13.0, 15.0, 17.0, 19.0])
def test_count_stays_close_to_the_phase_target(schedule, t):
    assert abs(st.on_map_count(schedule, t) - tc.target_students(t)) <= 3


def test_lunch_peak_is_clearly_higher(schedule):
    lunch = st.on_map_count(schedule, 12.5)
    assert lunch >= 20
    assert lunch > st.on_map_count(schedule, 10.0) + 10
    assert lunch > st.on_map_count(schedule, 14.0) + 8


def test_count_changes_gradually(schedule):
    previous = st.on_map_count(schedule, 5.0)
    for minute in range(5, 16 * 60, 5):
        now = st.on_map_count(schedule, 5.0 + minute / 60)
        assert abs(now - previous) <= 4
        previous = now


def test_decisions_only_while_on_the_map(schedule):
    for plan in schedule.values():
        for d in plan["decisions"]:
            assert any(a <= d < b for a, b in plan["presence"])


def test_students_come_back_later_the_same_day(schedule):
    assert any(len(p["presence"]) > 1 for p in schedule.values())


def test_state_machine_allows_only_valid_transitions():
    s = {"id": "s1", "status": st.OFF_MAP}
    with pytest.raises(st.TransitionError):
        st.transition(s, "join_queue")
    for action, expected in [("arrive", st.WANDERING), ("go_to_shop", st.WALKING_TO_SHOP),
                             ("join_queue", st.QUEUING), ("accepted", st.BEING_SERVED),
                             ("served", st.WANDERING), ("leave", st.OFF_MAP)]:
        st.transition(s, action)
        assert s["status"] == expected
    with pytest.raises(st.TransitionError):
        st.transition(s, "accepted")


def test_best_bundle_respects_budget_and_one_coffee():
    utilities = {k: 300.0 for k in ["cafe:coffee", "cafe:orange_juice", "cafe:pastel_de_nata",
                                    "rival:coffee", "rival:tea", "rival:croissant"]}
    prices = {k: 100 for k in utilities}
    bundle = st.best_bundle(utilities, prices, {"cafe": 1.0, "rival": 1.0}, 250, list(utilities))
    assert len(bundle) == 2
    assert sum(1 for k in bundle if k.endswith(":coffee")) <= 1


def test_choose_order_picks_one_shop_and_skips_sold_out():
    student = {"budget": 1_000, "utilities": {
        "cafe:coffee": 250.0, "cafe:orange_juice": 40.0, "cafe:pastel_de_nata": 200.0,
        "rival:coffee": 50.0, "rival:tea": 40.0, "rival:croissant": 40.0}}
    prices = {"cafe:coffee": 90, "cafe:orange_juice": 250, "cafe:pastel_de_nata": 130,
              "rival:coffee": 100, "rival:tea": 120, "rival:croissant": 150}
    factors = {"cafe": 1.0, "rival": 1.2}
    assert st.choose_order(student, prices, factors, ["cafe", "rival"]) == ("cafe", ["coffee", "pastel_de_nata"])
    shop, items = st.choose_order(student, prices, factors, ["cafe", "rival"], sold_out={"cafe:coffee"})
    assert (shop, items) == ("cafe", ["pastel_de_nata"])
    assert st.choose_order(student, prices, factors, ["rival"]) is None


def test_same_purchases_at_1x_and_8x():
    base = sim.morning_setup(logic.new_game(seed=21))
    slow = sim.simulate_day(base, speed=1)
    fast = sim.simulate_day(base, speed=8)
    assert sim.purchases(slow) == sim.purchases(fast)
    assert len(sim.purchases(slow)) > 20


def test_students_never_overspend_and_keep_budget_between_visits():
    state = sim.simulate_day(sim.morning_setup(logic.new_game(seed=5)), speed=8)
    for s in state["students"].values():
        spent = CONFIG["students"]["budget"] - s["budget"]
        assert s["budget"] >= 0
        paid = sum(state["shops"][p["shop"]]["prices"][i] for p in s["purchases"] for i in p["items"])
        assert paid == spent
    assert any(len(s["purchases"]) > 1 for s in state["students"].values())


def test_day_ends_with_everyone_off_the_map_or_wandering():
    state = sim.simulate_day(sim.morning_setup(logic.new_game(seed=9)), speed=8)
    assert all(s["status"] in (st.OFF_MAP, st.WANDERING) for s in state["students"].values())
    assert state["day_state"] == logic.DAY_SUMMARY


def test_leave_and_arrive_are_safe_to_repeat():
    state = logic.new_game(seed=1)
    state, _ = logic.apply(state, {"type": "student_arrive", "student": "s0", "t": 8.0})
    state, res = logic.apply(state, {"type": "student_arrive", "student": "s0", "t": 8.0})
    assert res == {"ignored": True}
    state, _ = logic.apply(state, {"type": "student_leave", "student": "s0", "t": 9.0})
    state, res = logic.apply(state, {"type": "student_leave", "student": "s0", "t": 9.1})
    assert res == {"ignored": True} and state["students"]["s0"]["status"] == st.OFF_MAP


def test_leaving_from_the_queue_ends_off_map():
    state = logic.new_game(seed=1)
    s = state["students"]["s1"]
    s["status"], s["intent"] = st.QUEUING, {"shop": "cafe", "items": ["coffee"]}
    state, _ = logic.apply(state, {"type": "student_leave", "student": "s1", "t": 9.0})
    assert state["students"]["s1"]["status"] == st.OFF_MAP
