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

    def visit_chance(self, state: dict) -> float:
        """v13: share of the interested customers who come at all today (1.0 = everyone)."""
        return 1.0

    def plan_scale(self, state: dict, day: int) -> float:
        """v13: how much more (or less) a manager should plan today than on ``day``."""
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

    # v8 hooks for machines that work on their own (vending)
    def front_count(self, state: dict, product: str) -> int | None:
        """Portions in the front if the mechanic counts them itself (None: the batches)."""
        return None

    def take(self, state: dict, product: str) -> bool:
        """Give out one portion itself (True) or let logic take it from front or storage."""
        return False

    def cash_in(self, state: dict, amount: int) -> int:
        """How much of a sale goes into your money right now (the rest waits somewhere)."""
        return amount

    def serve_at(self, state: dict, machine: str | None) -> None:
        """Where the next sale happens (a vending machine)."""

    def start_day(self, state: dict) -> None:
        pass

    def tick(self, state: dict) -> list[str]:
        return []

    def end_day(self, state: dict) -> int:
        return 0

    def plan_floor(self, state: dict, product: str) -> int:
        """v10: the least a manager plans of a product (shops with a front fill it)."""
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
    """SnackBots: machines spread over the campus instead of staff (brief 14.3, v8).

    Every machine sells all products and has its own stock, cash box and status.
    No prep time and nobody serves: a student walks to a machine and takes what it has.
    The player refills each machine from the office storage, takes the money out of the
    cash boxes and brings it back to the office. During opening hours a machine can
    break down (chance per game hour); a broken machine sells nothing until it is
    repaired for a fee. A working manager does all of this on his own."""

    staffed = False
    front_fill = "anytime"

    def machine_ids(self) -> list[str]:
        return [m["id"] for m in self.p["machines"]]

    def machines(self, state: dict) -> dict:
        d = self.data(state).setdefault("machines", {})
        for m in self.machine_ids():
            d.setdefault(m, {"stock": {}, "cash": 0, "broken": False})
        return d

    def front_products(self) -> set[str]:
        return set(CONFIG["shops"][self.shop]["products"])

    def front_capacity(self, product: str) -> int | None:
        return self.p["capacity"] * len(self.p["machines"])

    def front_count(self, state: dict, product: str) -> int | None:
        if not self.owned(state):
            return 0
        return sum(m["stock"].get(product, 0) for m in self.machines(state).values() if not m["broken"])

    def broken(self, state: dict) -> dict:
        return {mid: m["broken"] for mid, m in self.machines(state).items()}

    def available(self, state: dict, product: str) -> bool:
        return True  # broken machines simply do not count in front_count

    def objective(self, state: dict, day_state: str) -> str | None:
        """v15: say what to do with the machines, and remind about cash in your pocket."""
        carried = state.get("carried_cash", 0)
        if carried and day_state in ("SET_PRICES", "SHOP_OPEN", "CLOSING"):
            return (f"You carry €{carried / 100:.2f} from the machines - it is not in your account yet. "
                    "Bring it to the board in the SnackBots office.")
        return super().objective(state, day_state)

    def serve_at(self, state: dict, machine: str | None) -> None:
        self.data(state)["at"] = machine if machine in self.machine_ids() else None

    def take(self, state: dict, product: str) -> bool:
        ms = self.machines(state)
        at = self.data(state).get("at")
        order = ([at] if at else []) + sorted(ms, key=lambda m: -ms[m]["stock"].get(product, 0))
        for mid in order:
            m = ms[mid]
            if not m["broken"] and m["stock"].get(product, 0) > 0:
                m["stock"][product] -= 1
                self.data(state)["last_machine"] = mid
                return True
        return True  # nothing left; can_make was checked before

    def cash_in(self, state: dict, amount: int) -> int:
        mid = self.data(state).get("last_machine") or self.data(state).get("at") or self.machine_ids()[0]
        self.machines(state)[mid]["cash"] += amount
        return 0

    def refill(self, state: dict, machine: str | None) -> dict[str, int]:
        """Fill one machine (or all with None) from the storage, up to its capacity per product."""
        import logic

        moved: dict[str, int] = {}
        ids = [machine] if machine else self.machine_ids()
        for mid in ids:
            if mid not in self.machine_ids():
                raise logic.GameError("Unknown machine.")
        ms = self.machines(state)
        for product in CONFIG["shops"][self.shop]["products"]:
            uses = CONFIG["products"][product]["uses"]
            can = min(logic.stock_units(state, self.shop, i) // q for i, q in uses.items())
            # v10: with all machines, the goods are shared out evenly (one at a time, emptiest first)
            put = {mid: 0 for mid in ids}
            for _ in range(can):
                room = [mid for mid in ids if ms[mid]["stock"].get(product, 0) + put[mid] < self.p["capacity"]]
                if not room:
                    break
                mid = min(room, key=lambda m: (ms[m]["stock"].get(product, 0) + put[m], ids.index(m)))
                put[mid] += 1
            n = sum(put.values())
            if n > 0:
                logic._use_ingredients(state, self.shop, {i: q * n for i, q in uses.items()})
                for mid, k in put.items():
                    if k:
                        ms[mid]["stock"][product] = ms[mid]["stock"].get(product, 0) + k
                moved[product] = n
        return moved

    def plan_floor(self, state: dict, product: str) -> int:
        """v10: the manager plans enough to fill every machine, not only yesterday's sales."""
        in_machines = sum(m["stock"].get(product, 0) for m in self.machines(state).values())
        return max(0, self.p["capacity"] * len(self.p["machines"]) - in_machines)

    def collect(self, state: dict, machine: str | None) -> int:
        ids = [machine] if machine else self.machine_ids()
        total = 0
        for mid in ids:
            m = self.machines(state)[mid]
            total += m["cash"]
            m["cash"] = 0
        return total

    def repair(self, state: dict, machine: str) -> int:
        import logic

        if machine not in self.machine_ids():
            raise logic.GameError("Unknown machine.")
        m = self.machines(state)[machine]
        if not m["broken"]:
            raise logic.GameError("This machine works.")
        cost = self.p["repair_cost"]
        logic._pay(state, cost)
        state["stats"]["spending"] += cost
        m["broken"] = False
        return cost

    def start_day(self, state: dict) -> None:
        self.data(state)["last_hour"] = int(CONFIG["time"]["open"])
        self.data(state)["round_at"] = None  # v11: the manager has not been round the machines today

    # v11: the manager walks from machine to machine (the browser sends one event per machine).
    # The rounds below only run in Python if no round came from the browser for a while
    # (headless simulation, or the tab was closed).
    FALLBACK_HOURS = 2.0

    def service_machine(self, state: dict, machine: str) -> dict:
        """v11: the manager at one machine: repairs it, refills it and takes the cash out."""
        import logic

        if machine not in self.machine_ids():
            raise logic.GameError("Unknown machine.")
        m = self.machines(state)[machine]
        done = {"repaired": False, "moved": {}, "cash": 0}
        if m["broken"] and state["money"] >= self.p["repair_cost"]:
            self.repair(state, machine)
            done["repaired"] = True
        if not state["closed"]:
            done["moved"] = self.refill(state, machine)
        done["cash"] = self.collect(state, machine)
        state["money"] += done["cash"]
        self.data(state)["round_at"] = state["time"]
        return done

    def round_due(self, state: dict) -> bool:
        """v11: the Python fallback round is due: half an hour after opening, then every two hours without a round."""
        at = self.data(state).get("round_at")
        if at is None:
            return state["time"] + 1e-6 >= CONFIG["time"]["open"] + 0.5
        return state["time"] - at >= self.FALLBACK_HOURS

    def tick(self, state: dict) -> list[str]:
        """Breakdowns: one roll per machine for every full opening hour that passed."""
        if not self.owned(state) or not state["open"]:
            return []
        d = self.data(state)
        last = d.get("last_hour", int(CONFIG["time"]["open"]))
        now = min(int(state["time"] + 1e-6), int(CONFIG["time"]["close"]))
        toasts = []
        names = {m["id"]: m["name"] for m in self.p["machines"]}
        for hour in range(last, now):
            for mid, m in self.machines(state).items():
                if not m["broken"] and _rng(state, self.shop, mid, hour).random() < self.p["breakdown_per_hour"]:
                    m["broken"] = True
                    toasts.append(f"Machine broken: {names[mid]}")
        d["last_hour"] = max(last, now)
        return toasts  # v11: the manager repairs on his rounds (service), not by magic

    def manager_fill(self, state: dict) -> None:
        """A working manager refills every machine and brings the cash to the office.

        v11: in the game he walks round the machines (event manager_service). This is only
        the fallback when no round came for two hours (or none since opening)."""
        if not state["shops"][self.shop]["manager"] or state["closed"] or not self.round_due(state):
            return
        for mid in self.machine_ids():
            self.service_machine(state, mid)

    def end_day(self, state: dict) -> int:
        if state["shops"][self.shop]["manager"]:
            state["money"] += self.collect(state, None)
        return 0

    def view(self, state: dict) -> dict:
        ms = self.machines(state) if self.owned(state) else {}
        return {"repair_cost": self.p["repair_cost"], "capacity": self.p["capacity"],
                "broken": {mid: m["broken"] for mid, m in ms.items()},
                "machines": {mid: {"stock": dict(m["stock"]), "cash": m["cash"], "broken": m["broken"]} for mid, m in ms.items()}}


class Shelves(Mechanic):
    """Mercado & Go: limited shelf space (brief 14.3).

    The shelves hold a fixed number of items in total. The player puts products from the
    storage on the shelves (sandwiches are made while stocking: one roll and two slices of
    cheese each). v10: the shelves can be filled and refilled all day, not only in the
    morning. Students only buy what is on the shelves and pay at the register."""

    service = "checkout"
    front_fill = "anytime"

    def front_products(self) -> set[str]:
        return set(CONFIG["shops"][self.shop]["products"])

    def front_total_capacity(self) -> int | None:
        return self.p["capacity"]

    def storage_makes(self, state: dict, product: str) -> int:
        import logic

        uses = CONFIG["products"][product]["uses"]
        return min(logic.stock_units(state, self.shop, i) // q for i, q in uses.items())

    def objective(self, state: dict, day_state: str) -> str | None:
        """v10: the steps of the shop in order: storage -> shelves -> prices -> scan."""
        import logic

        products = CONFIG["shops"][self.shop]["products"]
        can_fill = [p for p in products if self.storage_makes(state, p) > 0 and logic.front_room(state, self.shop, p) > 0]
        empty = [p for p in products if logic.front_units(state, self.shop, p) == 0]
        if day_state == "SET_PRICES" and can_fill and sum(logic.front_units(state, self.shop, p) for p in products) == 0:
            return "Put the products from the storage on the shelves (walk to a shelf)."
        if day_state == "SHOP_OPEN" and empty and any(p in can_fill for p in empty):
            names = ", ".join(CONFIG["products"][p]["name"] for p in empty if p in can_fill)
            return f"Shelf empty: {names} - refill it from the storage."
        return self.p.get("objectives", {}).get(day_state)

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

    # v13: bad waves mean fewer surfers, not surfers who pay less. Before, a factor below 1
    # lowered what everybody would pay, so on a 1-star day nobody rented at all (-100 %
    # instead of the -60 % the forecast shows). Good waves still raise what people pay.
    def demand_factor(self, state: dict) -> float:
        return max(1.0, weather_factor(state, self.p.get("weather")))

    def visit_chance(self, state: dict) -> float:
        return min(1.0, weather_factor(state, self.p.get("weather")))

    def plan_scale(self, state: dict, day: int) -> float:
        """Today's waves against the waves of the day the plan is based on."""
        from logic import weather_for  # late import: logic imports this module
        then = weather_factor({"weather": weather_for(state["seed"], day)}, self.p.get("weather"))
        return weather_factor(state, self.p.get("weather")) / then

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
                "waves": (state.get("weather") or {}).get("waves"), "factor": weather_factor(state, self.p.get("weather"))}


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
