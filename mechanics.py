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


class Counter(Mechanic):
    """v1 to v6: order at the counter, prepare at the stations, hand over."""


class Vending(Mechanic):
    """SnackBots: machines instead of staff. Customers take the products themselves."""

    staffed = False


MECHANICS: dict[str, type[Mechanic]] = {
    "counter": Counter,
    "vending": Vending,
}

_cache: dict[str, Mechanic] = {}


def of(shop: str) -> Mechanic:
    """The mechanic object of a shop (built once from the config)."""
    if shop not in _cache:
        spec = dict(CONFIG["shops"][shop].get("mechanic") or {"type": "counter"})
        kind = spec.pop("type")
        _cache[shop] = MECHANICS[kind](shop, spec)
    return _cache[shop]
