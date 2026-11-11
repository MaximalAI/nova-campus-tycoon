"""Students: daily pool, schedule over the day and purchase decisions.

The utility model is unchanged from v1:
    U = sum(F_s * u_ij for chosen items) + (budget_left - sum(prices))
A student buys the bundle that maximizes U within the remaining budget,
with at most one coffee per visit.
"""

from __future__ import annotations

import itertools
import random

import timeclock
from config import CONFIG

S = CONFIG["students"]

# States of the per-student state machine (see docs/product-brief-v2.md 8.3)
OFF_MAP, WANDERING, WALKING_TO_SHOP, QUEUING, BEING_SERVED = (
    "off_map", "wandering", "walking_to_shop", "queuing", "being_served",
)

ALLOWED = {
    "arrive": {OFF_MAP: WANDERING},
    "leave": {WANDERING: OFF_MAP, WALKING_TO_SHOP: OFF_MAP},
    "go_to_shop": {WANDERING: WALKING_TO_SHOP, WALKING_TO_SHOP: WALKING_TO_SHOP,
                   QUEUING: WALKING_TO_SHOP, BEING_SERVED: WALKING_TO_SHOP},
    "join_queue": {WALKING_TO_SHOP: QUEUING},
    "accepted": {QUEUING: BEING_SERVED},
    "served": {BEING_SERVED: WANDERING, QUEUING: WANDERING},
    "give_up": {QUEUING: WANDERING, BEING_SERVED: WANDERING, WALKING_TO_SHOP: WANDERING},
}


class TransitionError(Exception):
    pass


def transition(student: dict, action: str) -> None:
    """Move a student to the next state, or raise if the action is not allowed."""
    target = ALLOWED[action].get(student["status"])
    if target is None:
        raise TransitionError(f"Student {student['id']} cannot '{action}' while {student['status']}.")
    student["status"] = target


def offering_key(shop: str, product: str) -> str:
    return f"{shop}:{product}"


def all_offerings() -> list[tuple[str, str]]:
    return [(s, p) for s, spec in CONFIG["shops"].items() for p in spec["products"]]


# The first two cafés of v2 to v6. Their utilities keep the old random stream, so a seed
# plays the same in the old cafés; every newer offering gets its own stream (v7).
CLASSIC_SHOPS = ("cafe", "rival")


def _utility(rng: random.Random, product: str) -> float:
    lo, hi = CONFIG["products"][product].get("utility", (S["utility_min"], S["utility_max"]))
    return rng.uniform(lo, hi)


def complete_student(seed: int, day: int, student: dict) -> None:
    """Add what newer versions know about a student: zone and utilities for new offerings."""
    student.setdefault("zone", "campus")
    for shop, product in all_offerings():
        key = offering_key(shop, product)
        if key not in student["utilities"]:
            student["utilities"][key] = _utility(_rng(seed, day, "utility", student["id"], key), product)


# ---------------------------------------------------------------------------
# Daily pool and schedule
# ---------------------------------------------------------------------------


def _rng(*parts) -> random.Random:
    return random.Random("-".join(str(p) for p in parts))


def make_pool(seed: int, day: int) -> dict[str, dict]:
    """25 students with budget, daily utilities and personal traits."""
    rng = _rng(seed, day, "pool")
    pool = {}
    for i in range(S["pool_size"]):
        sid = f"s{i}"
        utilities = {
            offering_key(s, p): rng.uniform(S["utility_min"], S["utility_max"])
            for s, p in all_offerings() if s in CLASSIC_SHOPS
        }
        pool[sid] = {
            "id": sid,
            "name": S["names"][i % len(S["names"])],
            "budget": S["budget"],
            "utilities": utilities,
            "traits": {
                "walk_speed": round(rng.uniform(*S["walk_speed"]), 3),
                "patience": round(rng.uniform(*S["patience_minutes"]), 1),
                "fickleness": round(rng.uniform(*S["fickleness"]), 3),
            },
            "look": {"shirt": rng.randrange(12), "pants": rng.randrange(6), "hair": rng.randrange(8),
                     "skin": rng.randrange(5)},
            "status": OFF_MAP,
            "intent": None,
            "purchases": [],
            "zone": "campus",
        }
        complete_student(seed, day, pool[sid])
    return pool


def make_schedule(seed: int, day: int, phases: list[dict] | None = None) -> dict[str, dict]:
    """When each student is on the map and when they think about buying.

    The number of students on the map moves gradually (max_change_per_step)
    towards the target of the current phase and never exceeds the pool size.
    """
    rng = _rng(seed, day, "schedule")
    ids = [f"s{i}" for i in range(S["pool_size"])]
    step = S["schedule_step_minutes"] / 60
    start, end = CONFIG["time"]["day_start"], CONFIG["time"]["day_end"]
    on: dict[str, float] = {}  # student -> arrival time of current visit
    visits = {sid: 0 for sid in ids}
    intervals: dict[str, list[list[float]]] = {sid: [] for sid in ids}

    t = start
    while t < end - 1e-9:
        target = timeclock.target_students(t, phases)
        diff = target - len(on)
        change = min(abs(diff), S["max_change_per_step"])
        if diff > 0:
            off = [s for s in ids if s not in on]
            off.sort(key=lambda s: (visits[s], rng.random()))
            for sid in off[:change]:
                on[sid] = round(t + rng.uniform(0, step), 4)
                visits[sid] += 1
        elif diff < 0:
            for sid in rng.sample(sorted(on), change):
                leave = max(on[sid] + step / 2, round(t + rng.uniform(0, step), 4))
                intervals[sid].append([on.pop(sid), round(min(leave, end), 4)])
        t = round(t + step, 6)
    for sid, arrived in on.items():
        intervals[sid].append([arrived, end])

    schedule = {}
    for sid in ids:
        decisions = []
        for arrive, leave in intervals[sid]:
            d = arrive + rng.uniform(2, 6) / 60
            while d < leave:
                decisions.append(round(d, 4))
                d += rng.uniform(*S["decide_every_minutes"]) / 60
        schedule[sid] = {"presence": sorted(intervals[sid]), "decisions": decisions}
    return schedule


def on_map_count(schedule: dict[str, dict], t: float) -> int:
    return sum(
        1 for s in schedule.values() for a, b in s["presence"] if a <= t < b
    )


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


def best_bundle(utilities: dict[str, float], prices: dict[str, int], factors: dict[str, float],
                budget: int, available: list[str]) -> list[str]:
    """Brute force over all bundles of the available offerings ("shop:product").

    Maximizes sum(F_s * u) + (budget - spent), spent <= budget, at most one coffee.
    """
    best: list[str] = []
    best_value = float(budget)
    for size in range(1, len(available) + 1):
        for bundle in itertools.combinations(available, size):
            if sum(1 for k in bundle if k.endswith(":coffee")) > 1:
                continue
            spent = sum(prices[k] for k in bundle)
            if spent > budget:
                continue
            value = sum(factors[k.split(":")[0]] * utilities[k] for k in bundle) + (budget - spent)
            if value > best_value + 1e-9:
                best_value, best = value, list(bundle)
    return best


def choose_order(student: dict, prices: dict[str, int], factors: dict[str, float],
                 shops: list[str], sold_out: set[str] = frozenset()) -> tuple[str, list[str]] | None:
    """Pick the shop and the items for one visit, or None if nothing is worth buying.

    v7: a visit goes to one shop, so the best bundle is computed per shop (at most three
    products each, so 8 bundles instead of 2^27) and the shop with the highest utility wins.
    Ties go to the shop listed first (the buying order)."""
    best: tuple[float, str, list[str]] | None = None
    for shop in shops:
        available = [offering_key(shop, p) for p in CONFIG["shops"][shop]["products"]
                     if offering_key(shop, p) not in sold_out]
        bundle = best_bundle(student["utilities"], prices, factors, student["budget"], available)
        if not bundle:
            continue
        value = sum(factors[shop] * student["utilities"][k] - prices[k] for k in bundle)
        if best is None or value > best[0] + 1e-9:
            best = (value, shop, [k.split(":")[1] for k in bundle])
    if best is None:
        return None
    return best[1], best[2]


def wants_to_visit(seed: int, day: int, student: dict, t: float) -> bool:
    """Random but reproducible: depends only on seed, day, student and game time."""
    rng = _rng(seed, day, student["id"], int(round(t * 600)))
    p = timeclock.cafe_probability(t) * student["traits"]["fickleness"]
    return rng.random() < p
