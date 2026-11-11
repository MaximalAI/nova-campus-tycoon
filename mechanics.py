"""Shop mechanics (v7).

Every shop names a mechanic type in config.py (``"mechanic": {"type": ..., params}``).
logic.py looks the class up in ``MECHANICS`` and calls its hooks; logic.py itself never
asks for the name of a shop. The base class is the plain counter shop of v1 to v6:
the customer orders at the counter, the order is prepared at the stations and handed over.

Hooks (all optional for a mechanic):
    staffed           False: nobody serves, customers serve themselves (no worker).
    service           "stations" (prepare at stations), "checkout" (scan at the register),
                      "assembly" (put bowls together from ingredients).
    front_products()  products sold from a front area (machines, shelves, display) that
                      the player fills from the storage; the others use the storage directly.
    front_capacity()  how many portions fit into the front (per product or in total).
    front_fill        when the player may fill the front: "anytime" or "before_open".
    open_now()        is the shop open at this time (opening hours)?
    demand_factor()   multiplies the shop factor (weather, ...).
    price()           the price a customer pays right now (happy hour, ...).
    available()       can this product be sold right now (a broken machine cannot)?
    on_consumed()     after one portion was taken (rentals keep the item).
    tick()            the clock passed a tick (every full hour and a few special times).
    end_day()         the evening: what is lost overnight.
    view()            extra data for the browser.
"""

from __future__ import annotations

import random

from config import CONFIG


class Mechanic:
    staffed = True
    service = "stations"
    front_fill: str | None = None

    def __init__(self, shop: str, params: dict):
        self.shop = shop
        self.p = params

    # --- state of this mechanic inside the saved game -----------------------------
    def data(self, state: dict) -> dict:
        return state["shops"][self.shop].setdefault("mech", {})

    def owned(self, state: dict) -> bool:
        return state["shops"][self.shop]["owner"] == "player"

    # --- hooks --------------------------------------------------------------------
    def front_products(self) -> set[str]:
        return set()

    def front_capacity(self, product: str) -> int | None:
        return None

    def front_total_capacity(self) -> int | None:
        return None

    def open_now(self, state: dict) -> bool:
        hours = CONFIG["shops"][self.shop].get("open_hours")
        if not hours:
            return True
        return hours[0] - 1e-6 <= state["time"] < hours[1] - 1e-6

    def demand_factor(self, state: dict) -> float:
        return 1.0

    def price(self, state: dict, product: str, base: int) -> int:
        return base

    def available(self, state: dict, product: str) -> bool:
        return True

    def on_consumed(self, state: dict, product: str) -> None:
        pass

    def new_front_batch(self, state: dict, product: str) -> dict:
        """Extra fields of a batch put into the front (a melting time, ...)."""
        return {}

    def start_day(self, state: dict) -> None:
        pass

    def tick(self, state: dict) -> list[str]:
        return []

    def end_day(self, state: dict) -> int:
        return 0

    def manager_fill(self, state: dict) -> None:
        """A working manager keeps the front filled."""
        if self.front_products() and state["shops"][self.shop]["manager"]:
            import logic

            logic.fill_front(state, self.shop, None)

    def view(self, state: dict) -> dict:
        return {}

    def objective(self, state: dict, day_state: str) -> str | None:
        """A text for the HUD objective when the player runs this shop (None: the default)."""
        return self.p.get("objectives", {}).get(day_state)


class Counter(Mechanic):
    """v1 to v6: order at the counter, prepare at the stations, hand over."""


def _rng(state: dict, *parts) -> random.Random:
    return random.Random("-".join(str(p) for p in (state["seed"], state["day"], *parts)))


class Vending(Mechanic):
    """SnackBots: machines instead of staff (brief 14.3).

    No prep time and nobody serves: a student takes the product if the machine has it.
    The player refills the machines from the storage. During opening hours a machine
    can break down (chance per game hour); a broken machine sells nothing until it is
    repaired for a fee. A working manager refills and repairs automatically."""

    staffed = False
    front_fill = "anytime"

    def front_products(self) -> set[str]:
        return set(CONFIG["shops"][self.shop]["products"])

    def front_capacity(self, product: str) -> int | None:
        return self.p["capacity"]

    def broken(self, state: dict) -> dict:
        return self.data(state).setdefault("broken", {})

    def available(self, state: dict, product: str) -> bool:
        return not self.broken(state).get(product)

    def repair(self, state: dict, product: str) -> int:
        import logic

        if not self.broken(state).get(product):
            raise logic.GameError("This machine works.")
        cost = self.p["repair_cost"]
        logic._pay(state, cost)
        state["stats"]["spending"] += cost
        self.broken(state)[product] = False
        return cost

    def start_day(self, state: dict) -> None:
        self.data(state)["last_hour"] = int(CONFIG["time"]["open"])

    def tick(self, state: dict) -> list[str]:
        """Breakdowns: one roll per machine for every full opening hour that passed."""
        if not self.owned(state) or not state["open"]:
            return []
        d = self.data(state)
        last = d.get("last_hour", int(CONFIG["time"]["open"]))
        now = min(int(state["time"] + 1e-6), int(CONFIG["time"]["close"]))
        toasts = []
        for hour in range(last, now):
            for product in CONFIG["shops"][self.shop]["products"]:
                if self.broken(state).get(product):
                    continue
                if _rng(state, self.shop, product, hour).random() < self.p["breakdown_per_hour"]:
                    self.broken(state)[product] = True
                    toasts.append(f"Machine broken: {CONFIG['products'][product]['name']}")
        d["last_hour"] = max(last, now)
        if state["shops"][self.shop]["manager"]:
            for product, is_broken in list(self.broken(state).items()):
                if is_broken and state["money"] >= self.p["repair_cost"]:
                    self.repair(state, product)
                    toasts.append(f"Manager repaired the {CONFIG['products'][product]['name']} machine")
        return toasts

    def view(self, state: dict) -> dict:
        return {"broken": dict(self.broken(state)), "repair_cost": self.p["repair_cost"],
                "capacity": self.p["capacity"]}


class Shelves(Mechanic):
    """Mercado & Go: limited shelf space (brief 14.3).

    The shelves hold a fixed number of items in total. In the morning the player decides
    how many of each product go on the shelves (sandwiches are made while stocking:
    one bread and two slices of cheese each). Students only buy what is on the shelves
    and pay at the register."""

    service = "checkout"
    front_fill = "before"

    def front_products(self) -> set[str]:
        return set(CONFIG["shops"][self.shop]["products"])

    def front_total_capacity(self) -> int | None:
        return self.p["capacity"]

    def view(self, state: dict) -> dict:
        return {"capacity": self.p["capacity"], "fill_until": self.p["fill_until"],
                "scan_minutes": self.p["scan_minutes"]}


class Assembly(Mechanic):
    """Bowl Bar: the first products with two ingredients (brief 14.3).

    At the one assembly station the player picks the ingredients. The set decides what
    lands on the tray: exactly the ingredients of a product make that product, any other
    set is a "wrong bowl" (it still uses the ingredients). Handing over a wrong bowl is a
    wrong order. Staff (bot or manager) always assemble correctly."""

    service = "assembly"

    def result(self, ingredients: set[str]) -> str:
        for product in CONFIG["shops"][self.shop]["products"]:
            if set(CONFIG["products"][product]["uses"]) == ingredients:
                return product
        return self.p["wrong"]

    def view(self, state: dict) -> dict:
        return {"ingredients": list(self.p["ingredients"]), "wrong": self.p["wrong"]}


class LunchRush(Mechanic):
    """Nova Mensa: only open around lunch; during the rush (12:00 to 14:00) the Mensa is
    the place to be (higher demand factor) and the campus is full (phase table)."""

    def in_rush(self, state: dict) -> bool:
        a, b = self.p["rush"]
        return a - 1e-6 <= state["time"] < b - 1e-6

    def demand_factor(self, state: dict) -> float:
        return self.p["rush_factor"] if self.in_rush(state) else 1.0

    def tick(self, state: dict) -> list[str]:
        d = self.data(state)
        if self.in_rush(state) and d.get("rush_day") != state["day"]:
            d["rush_day"] = state["day"]
            if self.owned(state):
                return [self.p["toast"]]
        return []

    def objective(self, state: dict, day_state: str) -> str | None:
        hours = CONFIG["shops"][self.shop]["open_hours"]
        if day_state in ("SET_PRICES", "SHOP_OPEN") and state["time"] < hours[0]:
            return f"{CONFIG['shops'][self.shop]['name']} opens at {_hhmm(hours[0])} - get ready for the lunch rush."
        if day_state == "SHOP_OPEN" and state["time"] >= hours[1]:
            return f"{CONFIG['shops'][self.shop]['name']} is closed for today. Plan tomorrow's lunch."
        return super().objective(state, day_state)

    def view(self, state: dict) -> dict:
        return {"rush": list(self.p["rush"]), "in_rush": self.in_rush(state)}


def _hhmm(t: float) -> str:
    return f"{int(t):02d}:{round((t - int(t)) * 60):02d}"


MECHANICS: dict[str, type[Mechanic]] = {
    "counter": Counter,
    "vending": Vending,
    "shelves": Shelves,
    "assembly": Assembly,
    "lunch_rush": LunchRush,
}

_cache: dict[str, Mechanic] = {}


def of(shop: str) -> Mechanic:
    """The mechanic object of a shop (built once from the config)."""
    if shop not in _cache:
        spec = dict(CONFIG["shops"][shop].get("mechanic") or {"type": "counter"})
        kind = spec.pop("type")
        _cache[shop] = MECHANICS[kind](shop, spec)
    return _cache[shop]
