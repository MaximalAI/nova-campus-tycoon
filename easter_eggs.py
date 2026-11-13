"""v8 easter eggs: Jep and the underground casino.

Both are rules in Python like the rest of the game: the browser only shows Jep at the
spot chosen here and spins the roulette wheel to the number drawn here.
"""

from __future__ import annotations

import random

from config import CONFIG

JEP = CONFIG["easter_eggs"]["jep"]
CASINO = CONFIG["easter_eggs"]["casino"]
RED = frozenset({1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36})


class EasterEggError(ValueError):
    """Not allowed (logic turns it into a GameError)."""


def jep_spot(seed: int, day: int) -> dict:
    """Where Jep stands today (the same spot for the same game and day)."""
    x, z = random.Random(f"{seed}-{day}-jep").choice(JEP["spots"])
    return {"x": x, "z": z}


def buy_from_jep(state: dict) -> dict:
    """Buy from Jep: costs money, the player is high for a few game minutes."""
    if state["time"] < state.get("high_until", 0):
        raise EasterEggError("Jep: 'Easy, you are still flying.'")
    if state["money"] < JEP["price"]:
        raise EasterEggError("Jep: 'Come back when you have the cash.'")
    state["money"] -= JEP["price"]
    state["stats"]["jep"] = state["stats"].get("jep", 0) + JEP["price"]
    state["high_until"] = state["time"] + JEP["high_minutes"] / 60
    return {"high_until": state["high_until"]}


def wins(bet: str, number: int) -> bool:
    if number == 0:
        return False
    return {
        "red": number in RED, "black": number not in RED,
        "even": number % 2 == 0, "odd": number % 2 == 1,
        "dozen1": number <= 12, "dozen2": 13 <= number <= 24, "dozen3": number >= 25,
    }[bet]


def spin(state: dict, bet: str, amount: int) -> dict:
    """One roulette spin. The number is seeded by game, day and spin count."""
    if bet not in CASINO["bets"]:
        raise EasterEggError("Unknown bet.")
    if amount <= 0 or amount > CASINO["max_bet"]:
        raise EasterEggError(f"Bets go from 1 cent to {CASINO['max_bet'] // 100} euros.")
    if amount > state["money"]:
        raise EasterEggError("You cannot bet more than you have.")
    casino = state.setdefault("casino", {"spins": 0, "net": 0})
    rng = random.Random(f"{state['seed']}-{state['day']}-roulette-{casino['spins']}")
    number = rng.randint(0, 36)
    won = wins(bet, number)
    change = amount * CASINO["bets"][bet]["pays"] if won else -amount
    state["money"] += change
    casino["spins"] += 1
    casino["net"] += change
    state["stats"]["casino"] = state["stats"].get("casino", 0) + change
    color = "green" if number == 0 else ("red" if number in RED else "black")
    return {"number": number, "color": color, "won": won, "change": change}


# ---------------------------------------------------------------------------
# v9: casino bar and slot machines
# ---------------------------------------------------------------------------
BAR = CASINO["bar"]
SLOTS = CASINO["slots"]


def buy_drink(state: dict, drink: str) -> dict:
    """A drink at the casino bar: costs money, the player is tipsy for a few game minutes."""
    spec = BAR["drinks"].get(drink)
    if spec is None:
        raise EasterEggError("The barkeeper does not know that drink.")
    if state["time"] < state.get("drunk_until", 0):
        raise EasterEggError("Barkeeper: 'I think you had enough for now.'")
    if state["money"] < spec["price"]:
        raise EasterEggError("Barkeeper: 'Cash first, my friend.'")
    state["money"] -= spec["price"]
    state["stats"]["bar"] = state["stats"].get("bar", 0) + spec["price"]
    state["drunk_until"] = state["time"] + BAR["drunk_minutes"] / 60
    return {"drunk_until": state["drunk_until"], "drink": drink}


def slot_payout(reels: list[str]) -> int:
    """How many times the bet comes back for these three symbols (0 = lost)."""
    if reels[0] == reels[1] == reels[2]:
        return SLOTS["symbols"][reels[0]]["triple"]
    if reels.count("cherry") == 2:
        return SLOTS["cherry_pair_pays"]
    return 0


def slot_return_rate() -> float:
    """Expected share of the bet that comes back (exact, from the weights)."""
    symbols = SLOTS["symbols"]
    total = sum(s["weight"] for s in symbols.values())
    p = {k: s["weight"] / total for k, s in symbols.items()}
    rate = sum(p[k] ** 3 * s["triple"] for k, s in symbols.items())
    rate += 3 * p["cherry"] ** 2 * (1 - p["cherry"]) * SLOTS["cherry_pair_pays"]
    return rate


def pull_slot(state: dict, machine: str, amount: int) -> dict:
    """One pull of a one-armed bandit. The reels are seeded by game, day and pull count."""
    if machine not in SLOTS["machines"]:
        raise EasterEggError("Unknown slot machine.")
    if amount not in SLOTS["bets"]:
        raise EasterEggError("This machine only takes the coins shown on it.")
    if amount > state["money"]:
        raise EasterEggError("You cannot bet more than you have.")
    casino = state.setdefault("casino", {"spins": 0, "net": 0})
    pulls = casino.get("pulls", 0)
    rng = random.Random(f"{state['seed']}-{state['day']}-slot-{pulls}")
    names = list(SLOTS["symbols"])
    weights = [SLOTS["symbols"][n]["weight"] for n in names]
    reels = rng.choices(names, weights=weights, k=3)
    pays = slot_payout(reels)
    change = amount * pays - amount
    state["money"] += change
    casino["pulls"] = pulls + 1
    casino["net"] += change
    state["stats"]["casino"] = state["stats"].get("casino", 0) + change
    return {"reels": reels, "icons": [SLOTS["symbols"][r]["icon"] for r in reels], "pays": pays, "change": change}
