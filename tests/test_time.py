"""Clock, speed, phases and lighting (brief sections 5, 8.2, 11)."""

import pytest

import timeclock as tc


def test_one_real_minute_is_one_game_hour_at_1x():
    assert tc.advance(8.0, 60, speed=1) == pytest.approx(9.0)


@pytest.mark.parametrize("speed, minutes", [(1, 12), (2, 6), (4, 3), (8, 1.5)])
def test_opening_hours_last_12_6_3_1_5_real_minutes(speed, minutes):
    assert tc.real_seconds_for(12, speed) == pytest.approx(minutes * 60)


def test_switching_speed_continues_without_jump():
    t = tc.advance(8.0, 30, speed=1)  # 08:30
    t = tc.advance(t, 15, speed=8)  # +2 game hours
    assert t == pytest.approx(10.5)


def test_pause_stops_time_at_every_speed():
    for speed in (1, 2, 4, 8):
        assert tc.advance(12.0, 100, speed=speed, paused=True) == 12.0


def test_dialogs_pause_clock_only_before_opening():
    assert tc.advance(6.0, 30, speed=1, dialog_open=True) == 6.0
    assert tc.advance(9.0, 30, speed=1, dialog_open=True) == pytest.approx(9.5)


def test_day_never_runs_past_21():
    assert tc.advance(20.9, 600, speed=8) == 21.0


def test_unknown_speed_is_rejected():
    with pytest.raises(ValueError):
        tc.advance(8.0, 1, speed=3)


def test_format_time():
    assert tc.format_time(5.5) == "05:30"
    assert tc.format_time(19.75) == "19:45"


@pytest.mark.parametrize(
    "t, name, target, prob",
    [
        (6.0, "Night", 0, 0.0),
        (7.75, "Early morning", 3, 0.9),
        (8.5, "Morning rush", 18, 0.8),
        (10.0, "Morning lectures", 6, 0.15),
        (12.5, "Lunch break", 25, 0.9),
        (14.0, "Afternoon lectures", 4, 0.15),
        (16.5, "Late afternoon", 10, 0.4),
        (18.5, "Evening", 2, 0.2),
        (20.5, "Closed", 0, 0.0),
    ],
)
def test_phase_table(t, name, target, prob):
    phase = tc.phase_at(t)
    assert phase["name"] == name
    assert tc.target_students(t) == target
    assert tc.cafe_probability(t) == prob


@pytest.mark.parametrize(
    "t, name", [(7.5, "Early morning"), (8.0, "Morning rush"), (9.0, "Morning lectures"), (12.0, "Lunch break"),
                (13.5, "Afternoon lectures"), (16.0, "Late afternoon"), (18.0, "Evening"),
                (20.0, "Closed"), (21.0, "Closed")],
)
def test_phase_boundaries_belong_to_the_next_phase(t, name):
    assert tc.phase_at(t)["name"] == name


def test_target_is_capped_at_25():
    phases = [{"name": "x", "from": 5.0, "to": 21.0, "target": 40, "cafe_probability": 1.0}]
    assert tc.target_students(12.0, phases) == 25


@pytest.mark.parametrize(
    "t, name", [(6.0, "dawn"), (7.0, "sunrise"), (7.75, "sunrise"), (8.5, "daylight"), (12.0, "daylight"),
                (17.5, "sunset"), (18.0, "sunset"), (19.5, "dusk"), (19.25, "sunset"), (20.0, "dusk")],
)
def test_lighting_state(t, name):
    assert tc.lighting_at(t)["name"] == name


def test_lighting_values_make_sense():
    noon, dawn, dusk = tc.lighting_at(12.0), tc.lighting_at(6.0), tc.lighting_at(20.5)
    assert noon["sun"] > 1.2 and noon["elevation"] > 50 and noon["lamps"] == 0
    assert dawn["lamps"] > 0.5 and dusk["lamps"] > 0.5
    assert dawn["sun"] < 0.5 and dusk["sun"] < 0.5
    assert tc.lighting_at(18.0)["sky"][0] > tc.lighting_at(12.0)["sky"][0]  # warmer sky at sunset


def test_lighting_changes_smoothly():
    keys = ["sun", "ambient", "elevation", "azimuth", "lamps"]
    previous = tc.lighting_at(5.0)
    t = 5.0
    while t < 21.0:
        t = round(t + 1 / 60, 6)
        now = tc.lighting_at(t)
        for k in keys:
            assert abs(now[k] - previous[k]) < 2.0, (k, t)
        for a, b in zip(now["sky"], previous["sky"]):
            assert abs(a - b) < 0.02, t
        previous = now


def test_lighting_table_covers_the_day():
    table = tc.lighting_table(10)
    assert table[0]["t"] == 5.0 and table[-1]["t"] == pytest.approx(21.0)
    assert len(table) == 97
