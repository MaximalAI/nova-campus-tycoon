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

    def units_for(self, product: str, portions: int) -> int:
        """Portions the shopping list must cover for a planned number of sales."""
        return portions

    def away_units(self, state: dict, item: str) -> int:
        """Units of an item that are yours but not in the storage right now (rented out)."""
        return 0

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


def weather_factor(state: dict, kind: str | None) -> float:
    """Demand factor from today's beach weather (waves or temperature)."""
    w = CONFIG["weather"]
    today = state.get("weather") or {}
    if kind == "waves" and "waves" in today:
        return w["wave_factor"][str(today["waves"])]
    if kind == "temperature" and "temperature" in today:
        (t0, t1), (f0, f1) = w["temperature"], w["temperature_factor"]
        x = max(0.0, min(1.0, (today["temperature"] - t0) / (t1 - t0)))
        return round(f0 + (f1 - f0) * x, 4)
    return 1.0


class Rental(Mechanic):
    """Surf Shack: boards and wetsuits are reusable (brief 14.3).

    A rental takes one free board or wetsuit; it comes back after some game hours.
    A wetsuit then dries before it can be rented again. A surf class needs a booked
    instructor (bought per day). The daily wave rating changes the demand."""

    def demand_factor(self, state: dict) -> float:
        return weather_factor(state, self.p.get("weather"))

    def units_for(self, product: str, portions: int) -> int:
        if product in self.p["rentals"]:
            return -(-portions // self.p["turns_per_day"])  # one board serves several customers a day
        return portions

    def away(self, state: dict) -> list[dict]:
        return self.data(state).setdefault("away", [])

    def away_units(self, state: dict, item: str) -> int:
        return sum(1 for a in self.away(state) if a["item"] == item)

    def on_consumed(self, state: dict, product: str) -> None:
        rule = self.p["rentals"].get(product)
        if not rule or not self.owned(state):
            return
        item = next(iter(CONFIG["products"][product]["uses"]))
        back = state["time"] + rule["hours"]
        self.away(state).append({"item": item, "back_at": round(back, 4),
                                 "ready_at": round(back + rule.get("dry_hours", 0.0), 4)})

    def _return(self, state: dict, item: str, n: int) -> None:
        state["shops"][self.shop]["stock"].append({"item": item, "units": n, "age": 0})

    def tick(self, state: dict) -> list[str]:
        now = state["time"] + 1e-6
        keep, back, dry = [], {}, {}
        for a in self.away(state):
            if a["ready_at"] <= now:
                self._return(state, a["item"], 1)
                (dry if a["ready_at"] > a["back_at"] else back)[a["item"]] = (dry if a["ready_at"] > a["back_at"] else back).get(a["item"], 0) + 1
            else:
                keep.append(a)
        self.data(state)["away"] = keep
        toasts = []
        if self.owned(state):
            for item, n in back.items():
                toasts.append(f"{n}x {CONFIG['wholesale_items'][item]['name']} returned")
            for item, n in dry.items():
                toasts.append(f"{n}x {CONFIG['wholesale_items'][item]['name']} dry again")
        return toasts

    def end_day(self, state: dict) -> int:
        for a in self.away(state):  # everything is back (and dry) by the next morning
            self._return(state, a["item"], 1)
        self.data(state)["away"] = []
        return 0

    def view(self, state: dict) -> dict:
        now = state["time"]
        out = [a for a in self.away(state) if a["back_at"] > now]
        drying = [a for a in self.away(state) if a["back_at"] <= now < a["ready_at"]]
        return {"rentals": {p: r["hours"] for p, r in self.p["rentals"].items()},
                "out": [{"item": a["item"], "back_at": a["back_at"]} for a in out],
                "drying": [{"item": a["item"], "ready_at": a["ready_at"]} for a in drying],
                "waves": (state.get("weather") or {}).get("waves"), "factor": self.demand_factor(state)}


class SunsetBar(Mechanic):
    """Praia Bar: opens at sunset (opening hours from the lighting table). The first hour
    is happy hour: prices are lower by the discount the player chooses, more people come."""

    def discount(self, state: dict) -> float:
        return self.data(state).get("discount", self.p["discount"])

    def happy(self, state: dict) -> bool:
        start = CONFIG["shops"][self.shop]["open_hours"][0]
        return start - 1e-6 <= state["time"] < start + self.p["happy_hours"] - 1e-6

    def price(self, state: dict, product: str, base: int) -> int:
        if not self.happy(state):
            return base
        step = CONFIG["price_step"]
        return max(step, int(base * (1 - self.discount(state)) // step) * step)

    def demand_factor(self, state: dict) -> float:
        return self.p["happy_factor"] if self.happy(state) else 1.0

    def set_discount(self, state: dict, discount) -> None:
        import logic

        if isinstance(discount, bool) or not isinstance(discount, (int, float)) or not 0 <= discount <= self.p["max_discount"]:
            raise logic.GameError(f"The discount must be between 0 and {round(self.p['max_discount'] * 100)} %.")
        if round(discount * 100) % 5:
            raise logic.GameError("The discount goes in steps of 5 %.")
        if state["time"] >= CONFIG["shops"][self.shop]["open_hours"][0] - 1e-6:
            raise logic.GameError("Set the happy hour before the bar opens.")
        self.data(state)["discount"] = round(discount, 2)

    def tick(self, state: dict) -> list[str]:
        d = self.data(state)
        if self.happy(state) and d.get("happy_day") != state["day"]:
            d["happy_day"] = state["day"]
            if self.owned(state):
                return [self.p["toast"]]
        return []

    def objective(self, state: dict, day_state: str) -> str | None:
        start = CONFIG["shops"][self.shop]["open_hours"][0]
        if day_state in ("SET_PRICES", "SHOP_OPEN") and state["time"] < start:
            return f"{CONFIG['shops'][self.shop]['name']} opens at sunset ({_hhmm(start)}). Set prices and the happy hour at the register."
        return super().objective(state, day_state)

    def view(self, state: dict) -> dict:
        return {"discount": self.discount(state), "max_discount": self.p["max_discount"],
                "happy": self.happy(state), "happy_hours": self.p["happy_hours"]}


class Melting(Mechanic):
    """Gelado Kiosk: ice cream waits in the freezer; the display melts its content after
    a few game hours. The daily temperature changes the demand."""

    front_fill = "anytime"

    def front_products(self) -> set[str]:
        return set(self.p["front"])

    def front_capacity(self, product: str) -> int | None:
        return self.p["capacity"]

    def demand_factor(self, state: dict) -> float:
        return weather_factor(state, self.p.get("weather"))

    def new_front_batch(self, state: dict, product: str) -> dict:
        return {"melt_at": round(state["time"] + self.p["melt_hours"], 4)}

    def _melt(self, state: dict, until: float) -> int:
        """Remove melted portions; returns how many melted."""
        import logic

        melted = 0
        front = state["shops"][self.shop]["front"]
        for product in list(front):
            keep = []
            for batch in front[product]:
                if batch.get("melt_at", 99) <= until + 1e-6:
                    melted += batch["units"]
                    self.data(state)["melted_value"] = self.data(state).get("melted_value", 0) + round(batch["units"] * logic.unit_cost(product))
                else:
                    keep.append(batch)
            front[product] = keep
        return melted

    def start_day(self, state: dict) -> None:
        self.data(state)["melted_value"] = 0

    def tick(self, state: dict) -> list[str]:
        n = self._melt(state, state["time"])
        if n:
            state["stats"]["wasted"] = state["stats"].get("wasted", 0) + n
            return [f"{n} portion{'s' if n != 1 else ''} of ice cream melted"] if self.owned(state) else []
        return []

    def manager_fill(self, state: dict) -> None:
        """A manager keeps the display about half full (less melts)."""
        if not state["shops"][self.shop]["manager"] or state["closed"]:
            return
        import logic

        half = self.p["capacity"] // 2
        logic.fill_front(state, self.shop, {p: max(0, half - logic.front_units(state, self.shop, p)) for p in self.p["front"]})

    def end_day(self, state: dict) -> int:
        self._melt(state, 99.0)  # everything in the display melts overnight
        value = self.data(state).get("melted_value", 0)
        self.data(state)["melted_value"] = 0
        return value

    def view(self, state: dict) -> dict:
        front = state["shops"][self.shop]["front"]
        next_melt = min((b["melt_at"] for bs in front.values() for b in bs if "melt_at" in b), default=None)
        return {"capacity": self.p["capacity"], "melt_hours": self.p["melt_hours"], "next_melt": next_melt,
                "temperature": (state.get("weather") or {}).get("temperature"), "factor": self.demand_factor(state)}


def _hhmm(t: float) -> str:
    return f"{int(t):02d}:{round((t - int(t)) * 60):02d}"


MECHANICS: dict[str, type[Mechanic]] = {
    "counter": Counter,
    "vending": Vending,
    "shelves": Shelves,
    "assembly": Assembly,
    "lunch_rush": LunchRush,
    "rental": Rental,
    "sunset_bar": SunsetBar,
    "melting": Melting,
}

_cache: dict[str, Mechanic] = {}


def of(shop: str) -> Mechanic:
    """The mechanic object of a shop (built once from the config)."""
    if shop not in _cache:
        spec = dict(CONFIG["shops"][shop].get("mechanic") or {"type": "counter"})
        kind = spec.pop("type")
        _cache[shop] = MECHANICS[kind](shop, spec)
    return _cache[shop]
