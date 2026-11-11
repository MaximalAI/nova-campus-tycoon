"""Game time: clock, speed, daily phases and the lighting schedule.

Pure functions, no UI. The browser runs the same simple clock formula for
smooth animation; these functions define the rules and are tested.
"""

from __future__ import annotations

from config import CONFIG

T = CONFIG["time"]


def format_time(t: float) -> str:
    """5.5 -> '05:30'."""
    minutes = int(round(t * 60))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def game_hours_per_real_second(speed: int) -> float:
    if speed not in T["speeds"]:
        raise ValueError(f"Unknown speed {speed}")
    return speed / T["real_seconds_per_game_hour"]


def clock_runs(t: float, paused: bool, dialog_open: bool) -> bool:
    """Pause stops everything; before opening, dialogs pause the clock too."""
    if paused:
        return False
    if dialog_open and t < T["dialogs_pause_clock_before"]:
        return False
    return True


def advance(t: float, real_seconds: float, speed: int, paused: bool = False,
            dialog_open: bool = False) -> float:
    """Game time after `real_seconds` of real time. Never past the end of the day."""
    if not clock_runs(t, paused, dialog_open):
        return t
    return min(T["day_end"], t + real_seconds * game_hours_per_real_second(speed))


def real_seconds_for(game_hours: float, speed: int) -> float:
    return game_hours / game_hours_per_real_second(speed)


# ---------------------------------------------------------------------------
# Daily phases
# ---------------------------------------------------------------------------


def phase_at(t: float) -> dict:
    """The phase containing t (from <= t < to). The last phase includes day_end."""
    phases = CONFIG["phases"]
    for phase in phases:
        if phase["from"] <= t < phase["to"]:
            return phase
    return phases[-1] if t >= phases[-1]["from"] else phases[0]


def target_students(t: float, phases: list[dict] | None = None, cap: int | None = None) -> int:
    """Target number of students on the map, capped at the pool size."""
    if phases is None:
        phase = phase_at(t)
    else:
        phase = next((p for p in phases if p["from"] <= t < p["to"]), phases[-1])
    return min(phase["target"], cap if cap is not None else CONFIG["students"]["pool_size"])


def cafe_probability(t: float, phases: list[dict] | None = None) -> float:
    if phases is None:
        return phase_at(t)["cafe_probability"]
    return next((p for p in phases if p["from"] <= t < p["to"]), phases[-1])["cafe_probability"]


# ---------------------------------------------------------------------------
# Lighting
# ---------------------------------------------------------------------------


def _smooth(x: float) -> float:
    return x * x * (3 - 2 * x)


def _mix(a, b, w):
    if isinstance(a, list):
        return [_mix(x, y, w) for x, y in zip(a, b)]
    return a + (b - a) * w


def lighting_state_name(t: float) -> str:
    if t < 7.0:
        return "dawn"
    if t < 8.5:
        return "sunrise"
    if t < 17.5:
        return "daylight"
    if t < 19.5:
        return "sunset"
    return "dusk"


def lighting_at(t: float) -> dict:
    """Sky colour, sun and lamp values at game time t, interpolated smoothly."""
    keys = CONFIG["lighting"]
    t = max(keys[0]["t"], min(keys[-1]["t"], t))
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            w = _smooth((t - a["t"]) / (b["t"] - a["t"]))
            values = {k: _mix(a[k], b[k], w) for k in a if k not in ("t", "name")}
            values["t"] = t
            values["name"] = lighting_state_name(t)
            return values
    raise AssertionError("unreachable")


def lighting_table(step_minutes: int = 10) -> list[dict]:
    """Samples for the browser, which interpolates linearly between them."""
    start, end = CONFIG["lighting"][0]["t"], CONFIG["lighting"][-1]["t"]
    n = int(round((end - start) * 60 / step_minutes))
    return [lighting_at(start + i * step_minutes / 60) for i in range(n + 1)]
