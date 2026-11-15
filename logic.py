"""Game rules for Nova Campus Tycoon v2.

No UI and no database code. The game state is a JSON-compatible dict.
`apply(state, event)` checks the rules for one event from the browser and
returns (new_state, result). The input state is never modified, so a
rejected event (GameError) changes nothing.

See docs/product-brief-v2.md for the rules.
"""

from __future__ import annotations

import copy
import math
import random

import easter_eggs
import mechanics
import students as st
from config import CONFIG

T = CONFIG["time"]
ITEMS = CONFIG["wholesale_items"]
PRODUCTS = CONFIG["products"]
SHOPS = CONFIG["shops"]
# v7: the order in which the shops can be bought (1 = your café)
SHOP_ORDER = sorted(SHOPS, key=lambda s: SHOPS[s]["order"])

# Day states, used for the guidance ("next objective")
MORNING_PLANNING = "MORNING_PLANNING"
WALK_TO_WHOLESALE = "WALK_TO_WHOLESALE"
WHOLESALE_SHOPPING = "WHOLESALE_SHOPPING"
WALK_TO_CAFE = "WALK_TO_CAFE"
SET_PRICES = "SET_PRICES"
SHOP_OPEN = "SHOP_OPEN"
CLOSING = "CLOSING"
DAY_SUMMARY = "DAY_SUMMARY"

RUNNING, GAME_OVER, VICTORY = "running", "game_over", "victory"


class GameError(Exception):
    """Raised when an action is not allowed by the rules."""


def euro(cents: int) -> str:
    """Money format used in the game: 1234 -> '€12.34'."""
    sign = "-" if cents < 0 else ""
    cents = abs(int(round(cents)))
    return f"{sign}€{cents // 100}.{cents % 100:02d}"


# ---------------------------------------------------------------------------
# New game and new day
# ---------------------------------------------------------------------------


def _empty_stats() -> dict:
    return {
        "shops": {s: {"revenue": 0, "sold": {}, "served": 0, "lost": 0, "wrong": 0,
                      "sold_out": 0, "rejected": 0, "tips": 0, "sold_out_products": {}} for s in SHOPS},
        "purchase_cost": 0,
        "spending": 0,  # running costs (repairs)
        "investments": 0,  # v11: shops bought, upgrades, managers hired - not part of the day's profit
        "rival_revenue": 0,
        "wasted": 0,
        "jep": 0,  # v8: spent at Jep
        "casino": 0,  # v8: won (+) or lost (-) in the casino
        "bar": 0,  # v9: spent at the casino bar
        # Stock movements per shop and item: opening stock, goods in, used, spoiled
        "flow": {},
    }


def new_game(seed: int | None = None) -> dict:
    if seed is None:
        seed = random.randrange(1, 1_000_000_000)
    shops = {
        s: {
            "owner": spec["start_owner"],
            "prices": dict(spec["start_prices"]),
            "upgrades": [],
            "manager": False,  # a manager works here today
            "manager_hired": False,  # hired (starts the next day)
            "staff": spec["start_owner"] == "bot",  # the competitor's own barista
            "opens_day": 1,
            "prices_set": spec["start_owner"] == "bot",  # shown on the price board ("-" until set)
            "stock": [],
            "sold": False,  # bought today, becomes yours tomorrow morning
            "front": {},  # v7: portions in machines, on shelves or in a display (product -> batches)
            "mech": {},  # v7: state of the shop's mechanic
        }
        for s, spec in SHOPS.items()
    }
    state = {
        "seed": seed,
        "day": 0,
        "status": RUNNING,
        "money": CONFIG["start_money"],
        "reputation": CONFIG["reputation"]["start"],
        "shops": shops,
        "plan": dict(CONFIG["start_plan"]),
        "history": [],
        "total_profit": 0,
    }
    return _start_day(state, 1)


def reputation_factor(reputation: float) -> float:
    """Demand factor of your cafés: more students choose you with a good reputation."""
    lo, hi = CONFIG["reputation"]["factor_range"]
    return round(lo + (hi - lo) * max(0, min(100, reputation)) / 100, 4)


def patience_factor(reputation: float) -> float:
    """Customers wait longer at a café with a good reputation."""
    lo, hi = CONFIG["reputation"]["patience_range"]
    return round(lo + (hi - lo) * max(0, min(100, reputation)) / 100, 4)


def tip_rate(reputation: float) -> float:
    """Share of the bill that happy customers add as a tip."""
    rate = 0.0
    for threshold, share in CONFIG["reputation"]["tips"]:
        if reputation >= threshold:
            rate = share
    return rate


def reputation_perks(state: dict) -> dict:
    """What the current reputation brings, for the HUD. Demand uses today's factor."""
    rep = state["reputation"]
    return {
        "demand_today": round(state["rep_factor"] - 1, 4),
        "demand_tomorrow": round(reputation_factor(rep) - 1, 4),
        "patience": patience_factor(rep),
        "tip": tip_rate(rep),
        "next_tip": next((t for t, _ in CONFIG["reputation"]["tips"] if rep < t), None),
    }


def _start_day(state: dict, day: int) -> dict:
    state.update({
        "day": day,
        "time": T["day_start"],
        "day_state": MORNING_PLANNING,
        "rep_factor": reputation_factor(state["reputation"]),
        "shopping_list": {},
        "cart_prefilled": False,
        "cart": {},
        "bag": {},
        "in_wholesaler": False,
        "open": False,
        "closed": False,
        "last_call": False,
        "current_order": None,
        "tray": [],
        "cleaning": {},  # v10: {shop: {spot: done}}, filled at closing time
        "stats": _empty_stats(),
        "summary": None,
        "students": st.make_pool(state["seed"], day),
        "restock": None,
        "manager_proposals": {},
        "weather": weather_for(state["seed"], day),
        "zone_news": [],
        "jep": easter_eggs.jep_spot(state["seed"], day),
        "high_until": 0,
        "drunk_until": 0,
    })
    for shop in SHOP_ORDER:
        if state["shops"][shop].get("sold") and state["shops"][shop]["owner"] == "bot":
            state["zone_news"] += _take_over(state, shop)
    # v7: the visitors of a zone only come once the zone is open
    state["schedule"] = st.make_schedule(state["seed"], day, zones=tuple(z for z in CONFIG["zones"] if zone_open(state, z)))
    for shop in SHOP_ORDER:
        mechanics.of(shop).start_day(state)
    for shop in owned_shops(state):
        data = state["shops"][shop]
        if data["manager_hired"]:
            data["manager"] = True  # hired yesterday or earlier: works from today
        data["prices_set"] = False  # the price board shows "-" until prices are set
        for batch in data["stock"]:
            _flow(state, shop, batch["item"])["open"] += batch["units"]
    for shop in owned_shops(state):
        if state["shops"][shop]["manager"]:
            state["manager_proposals"][shop] = manager_proposal(state, shop)
    ws = work_shop(state)
    if ws:
        # keep yesterday's plan for this shop's products, otherwise the default suggestion
        defaults = CONFIG["start_plan"] if SHOPS[ws]["start_owner"] == "player" else {}
        state["plan"] = {p: state["plan"].get(p, defaults.get(p, CONFIG["manager"]["min_portions"]))
                         for p in SHOPS[ws]["products"]}
    return state


def weather_for(seed: int, day: int) -> dict:
    """v7: the beach weather of a day (seeded): wave rating and temperature."""
    w = CONFIG["weather"]
    rng = random.Random(f"{seed}-{day}-weather")
    return {"waves": rng.randint(*w["waves"]), "temperature": rng.randint(*w["temperature"])}


def migrate(state: dict) -> dict:
    """Bring a saved game from an older version up to date (in place)."""
    for shop_id, shop in state["shops"].items():
        if "staff" not in shop:
            # v2 saves: only the competitor (while it is a bot) has its own barista
            shop["staff"] = shop_id == "rival" and shop["owner"] == "bot"
    state.setdefault("cart_prefilled", False)
    state.setdefault("restock", None)
    state.setdefault("manager_proposals", {})
    for shop_id, shop in state["shops"].items():
        shop.setdefault("manager_hired", shop.get("manager", False))
        shop.setdefault("opens_day", 1)
        shop.setdefault("prices_set", True)
        if shop_id == "rival" and shop["owner"] == "player" and shop.get("staff"):
            shop["staff"] = False  # v3/v4 barista: in v5 you run the bought café yourself
    # v7: new shops start as bots; every shop gets the new fields
    for shop_id, spec in SHOPS.items():
        if shop_id not in state["shops"]:
            state["shops"][shop_id] = {
                "owner": spec["start_owner"], "prices": dict(spec["start_prices"]), "upgrades": [],
                "manager": False, "manager_hired": False, "staff": True, "opens_day": 1,
                "prices_set": True, "stock": [],
            }
        shop = state["shops"][shop_id]
        shop.setdefault("sold", False)
        shop.setdefault("front", {})
        shop.setdefault("mech", {})
    if state.get("status") == VICTORY and not all(
            d["owner"] == "player" and d["manager_hired"] for d in state["shops"].values()):
        # a v6 save that had already won: new shops on campus, the race goes on
        state["status"] = RUNNING
        state.pop("open_mode", None)
    for student in state.get("students", {}).values():
        st.complete_student(state["seed"], state["day"], student)
    state.setdefault("weather", weather_for(state["seed"], state["day"]))
    state.setdefault("zone_news", [])
    state.setdefault("jep", easter_eggs.jep_spot(state["seed"], state["day"]))  # v8
    state.setdefault("high_until", 0)
    state.setdefault("drunk_until", 0)  # v9
    # v10: cleaning per shop ({shop: {spot: done}}); a v9 save has the café's spots flat
    cleaning = state.get("cleaning") or {}
    if cleaning and all(isinstance(v, bool) for v in cleaning.values()):
        state["cleaning"] = {"cafe": cleaning}
    state.setdefault("cleaning", {})
    # v10: themed upgrades per shop - an old upgrade key counts as the same tier of the new list
    legacy = list(CONFIG["upgrades"])
    for shop_id, shop in state["shops"].items():
        catalogue = list(upgrade_catalogue(shop_id))
        mapped = []
        for u in shop.get("upgrades", []):
            if u not in catalogue and u in legacy and legacy.index(u) < len(catalogue):
                u = catalogue[legacy.index(u)]
            if u in catalogue and u not in mapped:
                mapped.append(u)
        shop["upgrades"] = mapped
    if "students" in state:  # v7: the beach visitors exist (but do not come before the beach opens)
        for sid, student in st.make_pool(state["seed"], state["day"]).items():
            if sid not in state["students"]:
                state["students"][sid] = student
                state.setdefault("schedule", {})[sid] = {"presence": [], "decisions": []}
    stats = state.get("stats")
    if stats is not None:  # v3 and older: new statistics fields
        stats.setdefault("wasted", 0)
        stats.setdefault("flow", {})
        stats.setdefault("jep", 0)
        stats.setdefault("casino", 0)
        stats.setdefault("bar", 0)
        for shop_id in SHOPS:
            stats["shops"].setdefault(shop_id, _empty_stats()["shops"][shop_id])
        for shop_stats in stats["shops"].values():
            for key in ("sold_out", "rejected", "tips"):
                shop_stats.setdefault(key, 0)
            shop_stats.setdefault("sold_out_products", {})
    return state


def _flow(state: dict, shop: str, item: str) -> dict:
    flows = state["stats"].setdefault("flow", {}).setdefault(shop, {})
    return flows.setdefault(item, {"open": 0, "in": 0, "used": 0, "spoiled": 0})


def _add_stock(state: dict, shop: str, item: str, units: int) -> None:
    state["shops"][shop]["stock"].append({"item": item, "units": units, "age": 0})
    _flow(state, shop, item)["in"] += units


def _best_day(state: dict, shop: str, product: str) -> int:
    """v13: the most portions of ``product`` this shop ever sold on one day."""
    return max((((h.get("by_shop") or {}).get(shop) or {}).get("sold", {}).get(product, 0)
                for h in state["history"]), default=0)


def manager_proposal(state: dict, shop: str) -> dict:
    """What the manager of a shop wants to buy and charge today.

    Plan: yesterday's sales plus the customers who found it sold out, plus a buffer
    (more if a product sold out),
    at least ``min_portions``. Prices: yesterday's prices, +€0.10 for products that
    sold out, -€0.10 for products nobody bought (never below cost + €0.10).

    v13: sold-out customers count only half (``missed_weight``) and a plan is at most
    ``max_vs_best_day`` times the best day the shop ever had, so one day with a long
    sold-out list cannot blow up the plan (Bowl Bar once planned 173 poke bowls). The
    Surf Shack also plans with today's waves against the waves of yesterday.
    """
    m = CONFIG["manager"]
    last = state["history"][-1] if state["history"] else {}
    y = (last.get("by_shop") or {}).get(shop)
    plan, prices = {}, dict(state["shops"][shop]["prices"])
    mech = mechanics.of(shop)
    scale = mech.plan_scale(state, last["day"]) if y and "day" in last else 1.0
    for p in SHOPS[shop]["products"]:
        sold = y["sold"].get(p, 0) if y else 0
        missed = y.get("sold_out_products", {}).get(p, 0) if y else 0
        sold_out = bool(missed)
        buffer = m["sold_out_buffer"] if sold_out else m["buffer"]
        # v8: customers who found it sold out count as demand too (sold-out now costs reputation)
        want = math.ceil((sold + missed * m["missed_weight"]) * buffer * scale)
        cap = math.ceil(max(_best_day(state, shop, p), m["min_portions"]) * m["max_vs_best_day"])
        plan[p] = max(m["min_portions"], min(want, cap),
                      mech.plan_floor(state, p))  # v10: e.g. fill every vending machine
        if y and sold_out:
            prices[p] = min(PRODUCTS[p].get("max_price", CONFIG["max_price"]), prices[p] + CONFIG["price_step"])
        elif y and sold == 0:
            floor = math.ceil((unit_cost(p) + CONFIG["price_step"]) / CONFIG["price_step"]) * CONFIG["price_step"]
            prices[p] = max(floor, prices[p] - CONFIG["price_step"])
    packs = shopping_list(state, plan, shop)
    return {"plan": plan, "prices": prices, "shopping_list": packs, "cost": cart_total(packs), "done": False}


def unit_cost(product: str) -> float:
    """Ingredient cost of one portion in cents.

    v11: a reusable item (surfboard, wetsuit) is not used up: one rental costs its price
    spread over the rentals it lasts (lifetime_uses), not the whole board."""
    return sum(q * ITEMS[i]["price"] / ITEMS[i]["base_units"] / ITEMS[i].get("lifetime_uses", 1)
               for i, q in PRODUCTS[product]["uses"].items())


def _affordable_plan(state: dict, shop: str, plan: dict, budget: int) -> tuple[dict, dict]:
    """v13: the biggest share of ``plan`` whose shopping list fits into ``budget``.

    Every product is scaled by the same share, so the manager buys complete portions
    (rice AND salmon for a poke bowl) instead of spending everything on the first item."""
    packs = shopping_list(state, plan, shop)
    if cart_total(packs) <= budget:
        return plan, packs
    lo, hi = 0.0, 1.0
    best = ({p: 0 for p in plan}, {})
    for _ in range(20):  # binary search on the share
        mid = (lo + hi) / 2
        scaled = {p: math.floor(n * mid) for p, n in plan.items()}
        packs = shopping_list(state, scaled, shop)
        if cart_total(packs) <= budget:
            lo, best = mid, (scaled, packs)
        else:
            hi = mid
    return best


def _manager_buys(state: dict, shop: str, plan: dict | None = None, prices: dict | None = None,
                  budget: int | None = None) -> dict:
    """The manager buys whole packs for the plan and sets the prices.

    v13: if the money (or ``budget``, the shop's share when all managers buy together) is
    not enough, the whole plan is scaled down, so the shop still gets complete portions,
    and the toast says how much of the plan he could buy."""
    proposal = state["manager_proposals"][shop]
    if plan is not None:
        for p, n in plan.items():
            if p not in SHOPS[shop]["products"]:
                raise GameError(f"{p} is not sold in this shop.")
            _whole(n, "The planned amount")
        proposal["plan"] = dict(plan)
        proposal["shopping_list"] = shopping_list(state, plan, shop)
    if prices is not None:
        _check_prices(shop, prices)
        proposal["prices"] = dict(prices)
    budget = state["money"] if budget is None else min(budget, state["money"])
    wanted = cart_total(proposal["shopping_list"])
    share = 1.0
    if wanted > budget:
        plan_now, packs = _affordable_plan(state, shop, proposal["plan"], budget)
        total = sum(proposal["plan"].values())
        share = sum(plan_now.values()) / total if total else 0.0
        proposal["plan_full"] = dict(proposal["plan"])
        proposal["plan"], proposal["shopping_list"] = plan_now, packs
    bought, cost = {}, 0
    for item, packs in proposal["shopping_list"].items():
        price = packs * ITEMS[item]["price"]
        state["money"] -= price
        cost += price
        _add_stock(state, shop, item, packs * ITEMS[item]["base_units"])
        bought[item] = packs
    state["stats"]["purchase_cost"] += cost
    state["shops"][shop]["prices"].update(proposal["prices"])
    state["shops"][shop]["prices_set"] = True
    proposal.update({"done": True, "bought": bought, "paid": cost, "share": round(share, 4)})
    mechanics.of(shop).manager_fill(state)
    name = SHOPS[shop]["name"]
    if share < 1:
        toast = (f"Not enough cash: the manager of {name} could only buy {round(share * 100)} % of his plan "
                 f"({euro(cost)})")
    else:
        toast = f"Manager of {name} bought supplies for {euro(cost)}"
    return {"toast": toast, "bought": bought, "cost": cost, "share": share}


def _managers_buy_all(state: dict) -> list[dict]:
    """v13: all managers who have not bought yet buy together. If the money is not enough
    for every plan, each shop gets a share of the money in proportion to its plan, so the
    last shop in the list is not left with nothing."""
    todo = [s for s, p in state.get("manager_proposals", {}).items() if not p["done"]]
    total = sum(cart_total(state["manager_proposals"][s]["shopping_list"]) for s in todo)
    money = state["money"]
    results = []
    for shop in todo:
        cost = cart_total(state["manager_proposals"][shop]["shopping_list"])
        budget = None if total <= money else (money * cost // total if total else 0)
        results.append({"shop": shop, **_manager_buys(state, shop, budget=budget)})
    return results


def upgrade_catalogue(shop: str) -> dict:
    """v10: the upgrades that fit this shop (the café's three for shops without their own)."""
    return SHOPS[shop].get("upgrades") or CONFIG["upgrades"]


def cleaning_spots(shop: str) -> dict:
    """v10: what has to be cleaned in this shop after closing (nothing in a vending shop)."""
    if not mechanics.of(shop).staffed:
        return {}
    return SHOPS[shop].get("cleaning") or CONFIG["cleaning_spots"]


def cleaning_shops(state: dict) -> list[str]:
    """v10: the shops that are cleaned tonight: owned, with staff, open today."""
    return [s for s in owned_shops(state)
            if cleaning_spots(s) and state["shops"][s].get("opens_day", 1) <= state["day"]]


def cleaning_left(state: dict, shop: str) -> int:
    spots = state.get("cleaning", {}).get(shop, {})
    return sum(1 for done in spots.values() if not done)


def owned_shops(state: dict) -> list[str]:
    return [s for s in SHOP_ORDER if state["shops"][s]["owner"] == "player"]


def is_auto(state: dict, shop: str) -> bool:
    """Bots, shops with a working manager and shops without staff (vending) serve automatically."""
    data = state["shops"][shop]
    return data["owner"] == "bot" or data["manager"] or not mechanics.of(shop).staffed


def work_shop(state: dict) -> str | None:
    """The shop the player runs himself today: the first owned shop without a working manager."""
    for s in owned_shops(state):
        if not state["shops"][s]["manager"] and state["shops"][s].get("opens_day", 1) <= state["day"]:
            return s
    return None


def shop_operating(state: dict, shop: str) -> bool:
    """Does this shop take customers today? A bought shop opens the next day;
    an owned shop without manager only opens if it is the one the player runs."""
    data = state["shops"][shop]
    if data["owner"] == "bot":
        return True
    if data.get("opens_day", 1) > state["day"]:
        return False
    return data["manager"] or shop == work_shop(state)


def shop_factor(state: dict, shop: str) -> float:
    data = state["shops"][shop]
    factor = SHOPS[shop]["base_factor"] + sum(
        upgrade_catalogue(shop)[u]["factor_bonus"] for u in data["upgrades"] if u in upgrade_catalogue(shop)
    )
    if data["owner"] == "player":
        factor *= state["rep_factor"]
    factor *= mechanics.of(shop).demand_factor(state)
    return round(factor, 4)


def shop_open_now(state: dict, shop: str) -> bool:
    """Takes customers right now: operating today, the day is open and within opening hours."""
    return shop_operating(state, shop) and mechanics.of(shop).open_now(state)


def price_now(state: dict, shop: str, product: str) -> int:
    """What a customer pays right now (a happy hour can lower the price board's price)."""
    return mechanics.of(shop).price(state, product, state["shops"][shop]["prices"][product])


def offer_prices(state: dict) -> dict[str, int]:
    return {
        st.offering_key(s, p): price_now(state, s, p)
        for s in SHOPS for p in SHOPS[s]["products"]
    }


def item_shops(item: str) -> list[str]:
    """The shops whose products need this wholesale item."""
    return [s for s in SHOP_ORDER if item in _shop_items(s)]


def item_available(state: dict, item: str) -> bool:
    """v7: the wholesaler sells an item once you own a shop that needs it."""
    return any(state["shops"][s]["owner"] == "player" for s in item_shops(item))


def stock_units(state: dict, shop: str, item: str) -> int:
    return sum(b["units"] for b in state["shops"][shop]["stock"] if b["item"] == item)


def front_units(state: dict, shop: str, product: str) -> int:
    counted = mechanics.of(shop).front_count(state, product)  # v8: vending machines count themselves
    if counted is not None:
        return counted
    return sum(b["units"] for b in state["shops"][shop].get("front", {}).get(product, []))


def can_make(state: dict, shop: str, product: str) -> bool:
    if state["shops"][shop]["owner"] == "bot":
        return True
    return bool(portions(state, shop, product))


def portions(state: dict, shop: str, product: str) -> int | None:
    """How many more portions can be sold (None: a bot shop, unlimited).

    Products of a front (machine, shelf, display) only sell what is in the front."""
    if state["shops"][shop]["owner"] == "bot":
        return None
    mech = mechanics.of(shop)
    if not mech.available(state, product):
        return 0
    if product in mech.front_products():
        return front_units(state, shop, product)
    return min(stock_units(state, shop, i) // q for i, q in PRODUCTS[product]["uses"].items())


def _consume(state: dict, shop: str, product: str) -> None:
    """Use one portion: from the front if the product is sold there, else the ingredients."""
    mech = mechanics.of(shop)
    if mech.take(state, product):  # v8: a machine gives out the product itself
        mech.on_consumed(state, product)
        return
    if product in mech.front_products():
        batches = state["shops"][shop]["front"].get(product, [])
        for batch in sorted(batches, key=lambda b: -b.get("age", 0)):
            if batch["units"] > 0:
                batch["units"] -= 1
                break
        state["shops"][shop]["front"][product] = [b for b in batches if b["units"] > 0]
    else:
        _use_ingredients(state, shop, PRODUCTS[product]["uses"])
    mech.on_consumed(state, product)


def _use_ingredients(state: dict, shop: str, uses: dict[str, int]) -> None:
    """Take ingredients from the storage, oldest batch first."""
    stock = state["shops"][shop]["stock"]
    for item, qty in uses.items():
        _flow(state, shop, item)["used"] += qty
        for batch in sorted((b for b in stock if b["item"] == item), key=lambda b: -b["age"]):
            take = min(qty, batch["units"])
            batch["units"] -= take
            qty -= take
            if qty == 0:
                break
    state["shops"][shop]["stock"] = [b for b in stock if b["units"] > 0]


def _shop_items(shop: str) -> set[str]:
    return {i for p in SHOPS[shop]["products"] for i in PRODUCTS[p]["uses"]}


def front_room(state: dict, shop: str, product: str) -> int:
    """How many more portions of a product fit into the front right now."""
    mech = mechanics.of(shop)
    room = 10**9
    cap = mech.front_capacity(product)
    if cap is not None:
        room = cap - front_units(state, shop, product)
    total = mech.front_total_capacity()
    if total is not None:
        used = sum(front_units(state, shop, p) for p in mech.front_products())
        room = min(room, total - used)
    return max(0, room)


def fill_front(state: dict, shop: str, amounts: dict[str, int] | None) -> dict[str, int]:
    """Make portions from the storage and put them into the front (machine, shelf, display).

    ``amounts``: wanted portions per product; None fills every product as far as it goes
    (a manager does this). Returns the portions actually moved."""
    mech = mechanics.of(shop)
    moved: dict[str, int] = {}
    wanted = amounts if amounts is not None else {p: 10**9 for p in SHOPS[shop]["products"]
                                                   if p in mech.front_products()}
    if amounts is None and mech.front_total_capacity() is not None:
        # share the shelf space fairly between the products
        share = mech.front_total_capacity() // max(1, len(wanted))
        wanted = {p: max(0, share - front_units(state, shop, p)) for p in wanted}
    for product, n in wanted.items():
        uses = PRODUCTS[product]["uses"]
        can = min(stock_units(state, shop, i) // q for i, q in uses.items())
        n = min(n, can, front_room(state, shop, product))
        if n <= 0:
            continue
        _use_ingredients(state, shop, {i: q * n for i, q in uses.items()})
        batch = {"units": n, "age": 0}
        batch.update(mech.new_front_batch(state, product))
        state["shops"][shop]["front"].setdefault(product, []).append(batch)
        moved[product] = n
    return moved


def _require_running(state: dict) -> None:
    if state["status"] != RUNNING:
        raise GameError("The game is over.")


def _require_owned(state: dict, shop: str) -> None:
    if shop not in SHOPS:
        raise GameError(f"Unknown shop: {shop}.")
    if state["shops"][shop]["owner"] != "player":
        raise GameError("You do not own this shop.")


def _whole(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GameError(f"{name} must be a whole number of 0 or more.")
    return value


def _pay(state: dict, amount: int) -> None:
    if amount > state["money"]:
        raise GameError(f"Not enough money: you need {euro(amount)} but have {euro(state['money'])}.")
    state["money"] -= amount


def monopoly_progress(state: dict) -> dict:
    """For the HUD bar: shops that are yours with a hired manager, out of all shops."""
    done = [s for s in SHOP_ORDER if state["shops"][s]["owner"] == "player" and state["shops"][s]["manager_hired"]]
    owned = owned_shops(state)
    return {"done": len(done), "owned": len(owned), "total": len(SHOPS)}


def _check_victory(state: dict) -> None:
    if state.get("open_mode"):
        return  # you already won and chose to keep playing
    if all(d["owner"] == "player" and d["manager_hired"] for d in state["shops"].values()):
        state["status"] = VICTORY


def _ev_continue_open_mode(state, ev):
    """After the victory: keep playing without a goal (open mode)."""
    if state["status"] != VICTORY:
        raise GameError("Open mode starts after you have won.")
    state["status"] = RUNNING
    state["open_mode"] = True
    return {"toast": "Open mode: keep running your cafés as long as you like."}


def _student(state: dict, sid: str) -> dict:
    if sid not in state["students"]:
        raise GameError(f"Unknown student: {sid}.")
    return state["students"][sid]


# ---------------------------------------------------------------------------
# Planning and shopping list
# ---------------------------------------------------------------------------


def shopping_list(state: dict, plan: dict[str, int], shop: str | None = None) -> dict[str, int]:
    """Wholesale units needed: planned portions minus usable stock, rounded up to packs.

    Only the stock of ``shop`` counts (default: the shop the player runs today)."""
    shop = shop or work_shop(state) or SHOP_ORDER[0]
    need: dict[str, int] = {}
    front = mechanics.of(shop).front_products()
    for product, portions in plan.items():
        if product in front and state["shops"][shop]["owner"] == "player":
            portions = max(0, portions - front_units(state, shop, product))  # already in the machine / on the shelf
        portions = mechanics.of(shop).units_for(product, portions)  # rentals: one board serves several customers
        for item, qty in PRODUCTS[product]["uses"].items():
            need[item] = need.get(item, 0) + portions * qty
    result = {}
    for item, units in need.items():
        have = (stock_units(state, shop, item) + mechanics.of(shop).away_units(state, item)
                if state["shops"][shop]["owner"] == "player" else 0)
        missing = max(0, units - have)
        packs = math.ceil(missing / ITEMS[item]["base_units"])
        if packs:
            result[item] = packs
    return result


def cart_total(cart: dict[str, int]) -> int:
    return sum(ITEMS[i]["price"] * q for i, q in cart.items())


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _ev_confirm_plan(state, ev):
    plan = ev.get("plan") or {}
    shop = work_shop(state)
    if shop is None:
        raise GameError("Your managers plan their own shops. Save up and grow!")
    sellable = set(SHOPS[shop]["products"])
    for product, portions in plan.items():
        if product not in sellable:
            raise GameError(f"You do not sell {product}.")
        _whole(portions, "The planned amount")
    state["plan"] = dict(plan)
    state["shopping_list"] = shopping_list(state, plan)
    state["cart_prefilled"] = False
    if state["day_state"] == MORNING_PLANNING:
        state["day_state"] = WALK_TO_WHOLESALE
    return {"toast": "Shopping list ready - off to the wholesaler!",
            "shopping_list": state["shopping_list"]}


def _ev_enter_wholesaler(state, ev):
    if state["closed"]:
        raise GameError("The wholesaler is closed now.")
    state["in_wholesaler"] = True
    if state["day_state"] in (MORNING_PLANNING, WALK_TO_WHOLESALE):
        state["day_state"] = WHOLESALE_SHOPPING
    # v5: the cart starts empty; the player takes the goods from the stands himself
    # (the shopping list is only a reference).
    return {}


def _ev_leave_wholesaler(state, ev):
    if state["cart"]:
        raise GameError("You still have unpaid goods in your cart. Pay at the checkout or put them back.")
    state["in_wholesaler"] = False
    return {}


def _ev_set_cart_item(state, ev):
    if not state["in_wholesaler"]:
        raise GameError("You are not inside the wholesaler.")
    item = ev.get("item")
    if item not in ITEMS or not item_available(state, item):
        raise GameError("This item is not sold here.")
    qty = _whole(ev.get("qty"), "The quantity")
    if qty:
        state["cart"][item] = qty
        return {"toast": f"{qty}x {ITEMS[item]['name']} in your cart"}
    state["cart"].pop(item, None)
    return {"toast": f"{ITEMS[item]['name']} removed from your cart"}


def _ev_pay(state, ev):
    if not state["in_wholesaler"]:
        raise GameError("You are not inside the wholesaler.")
    if not state["cart"]:
        raise GameError("Your cart is empty.")
    total = cart_total(state["cart"])
    _pay(state, total)
    for item, qty in state["cart"].items():
        state["bag"][item] = state["bag"].get(item, 0) + qty
    state["cart"] = {}
    state["stats"]["purchase_cost"] += total
    if state["day_state"] in (MORNING_PLANNING, WALK_TO_WHOLESALE, WHOLESALE_SHOPPING):
        state["day_state"] = WALK_TO_CAFE
    return {"toast": f"Purchase paid: {euro(total)}"}


def _ev_stock_goods(state, ev):
    shop = ev.get("shop", "cafe")
    _require_owned(state, shop)
    usable = _shop_items(shop)
    moved = {i: q for i, q in state["bag"].items() if i in usable}
    if not moved:
        raise GameError("Your bag has nothing for this shop.")
    for item, packs in moved.items():
        _add_stock(state, shop, item, packs * ITEMS[item]["base_units"])
        del state["bag"][item]
    if state["day_state"] in (MORNING_PLANNING, WALK_TO_WHOLESALE, WHOLESALE_SHOPPING, WALK_TO_CAFE):
        state["day_state"] = SET_PRICES if not state["open"] else SHOP_OPEN
    return {"toast": "Goods stocked"}


def _ev_set_prices(state, ev):
    shop = ev.get("shop", "cafe")
    _require_owned(state, shop)
    # v11: a shop that opens later (Praia Bar at sunset) can be priced until it opens
    opens_later = bool(SHOPS[shop].get("open_hours")) and state["time"] < SHOPS[shop]["open_hours"][0] - 1e-6
    if state["closed"] or (state["open"] and not opens_later):
        raise GameError("You can only change prices before opening.")
    prices = ev.get("prices") or {}
    _check_prices(shop, prices)
    state["shops"][shop]["prices"].update(prices)
    state["shops"][shop]["prices_set"] = True
    return {"toast": "Prices saved"}


def _check_prices(shop: str, prices: dict) -> None:
    for product, price in prices.items():
        if product not in SHOPS[shop]["products"]:
            raise GameError(f"{product} is not sold in this shop.")
        if isinstance(price, bool) or not isinstance(price, int):
            raise GameError("Prices must be whole cents.")
        top = PRODUCTS[product].get("max_price", CONFIG["max_price"])  # v7: expensive beach products
        if price <= 0 or price > top or price % CONFIG["price_step"]:
            raise GameError(f"Prices must be between €0.10 and {euro(top)} in steps of €0.10.")


def _ev_confirm_all_manager_plans(state, ev):
    """v13: "Accept all": every manager buys his proposal; a short budget is shared fairly."""
    _require_running(state)
    results = _managers_buy_all(state)
    if not results:
        raise GameError("The managers already bought today's supplies.")
    short = [f"{SHOPS[r['shop']]['name']} {round(r['share'] * 100)} %" for r in results if r["share"] < 1]
    cost = sum(r["cost"] for r in results)
    toast = (f"Not enough cash: your managers could only buy part of their plans ({', '.join(short)})"
             if short else f"Your managers bought supplies for {euro(cost)}")
    return {"toast": toast, "manager_bought": [r["shop"] for r in results], "cost": cost}


def _ev_confirm_manager_plan(state, ev):
    """You accept (or change) your manager's shopping list and prices; he buys right away."""
    shop = ev.get("shop", "cafe")
    _require_owned(state, shop)
    proposal = state.get("manager_proposals", {}).get(shop)
    if not proposal:
        raise GameError("There is no proposal from a manager.")
    if proposal["done"]:
        raise GameError("The manager already bought today's supplies.")
    return _manager_buys(state, shop, ev.get("plan"), ev.get("prices"))


def _open(state) -> dict:
    state["open"] = True
    state["day_state"] = SHOP_OPEN
    return {"toast": "Open - the first customers are coming", "opened": True}


def _ev_open_shop(state, ev):
    if state["open"]:
        raise GameError("The café is already open.")
    if state["closed"]:
        raise GameError("The café has already closed today.")
    if state["time"] < T["earliest_manual_open"]:
        raise GameError("You can open at 07:00 at the earliest.")
    return _open(state)


def _close(state) -> dict:
    """20:00: no new orders, waiting customers leave, an unfinished order is cancelled."""
    state["open"] = False
    state["closed"] = True
    state["day_state"] = CLOSING
    # v10: every owned shop with staff is cleaned tonight (by you or by its manager)
    state["cleaning"] = {s: {spot: False for spot in cleaning_spots(s)} for s in cleaning_shops(state)}
    cancelled = None
    if state["current_order"]:
        cancelled = state["current_order"]["student"]
        state["current_order"] = None
        state["tray"] = []
    for s in state["students"].values():
        if s["status"] in (st.QUEUING, st.BEING_SERVED, st.WALKING_TO_SHOP):
            s["status"] = st.WANDERING
            s["intent"] = None
    return {"closed": True, "cancelled": cancelled}


def _end_day(state) -> dict:
    """Spoilage, statistics, reputation for missed cleaning, game-over check."""
    for shop, spots in state.get("cleaning", {}).items():
        if all(spots.values()):
            continue
        if state["shops"][shop]["manager"]:
            for spot in spots:
                spots[spot] = True  # the manager finishes the job (also when nobody watched)
        else:
            _change_reputation(state, CONFIG["reputation"]["cleaning_missed"])  # v10: per shop you left dirty
    spoiled_value = 0
    spoiled = {}
    for shop in owned_shops(state):
        kept = []
        for batch in state["shops"][shop]["stock"]:
            batch["age"] += 1
            shelf = ITEMS[batch["item"]]["shelf_days"]
            if shelf is not None and batch["age"] >= shelf:
                value = round(batch["units"] * ITEMS[batch["item"]]["price"] / ITEMS[batch["item"]]["base_units"])
                spoiled_value += value
                spoiled[batch["item"]] = spoiled.get(batch["item"], 0) + batch["units"]
                _flow(state, shop, batch["item"])["spoiled"] += batch["units"]
            else:
                kept.append(batch)
        state["shops"][shop]["stock"] = kept
        # v7: portions in a front spoil with their shortest-lived ingredient
        for product, batches in state["shops"][shop].get("front", {}).items():
            uses = PRODUCTS[product]["uses"]
            shelves = [ITEMS[i]["shelf_days"] for i in uses if ITEMS[i]["shelf_days"] is not None]
            shelf = min(shelves) if shelves else None
            keep = []
            for batch in batches:
                batch["age"] = batch.get("age", 0) + 1
                if shelf is not None and batch["age"] >= shelf:
                    spoiled_value += round(batch["units"] * unit_cost(product))
                    spoiled[product] = spoiled.get(product, 0) + batch["units"]
                else:
                    keep.append(batch)
            state["shops"][shop]["front"][product] = keep
        spoiled_value += mechanics.of(shop).end_day(state)

    stats = state["stats"]
    revenue = sum(stats["shops"][s]["revenue"] for s in owned_shops(state))
    tips = sum(stats["shops"][s].get("tips", 0) for s in owned_shops(state))
    # v8: Jep and the casino count as well (they move real money)
    profit = (revenue + tips - stats["purchase_cost"] - stats["spending"] - stats.get("jep", 0)
              + stats.get("casino", 0) - stats.get("bar", 0))
    total_market = revenue + _bot_revenue(state)
    sold: dict[str, int] = {}
    for s in owned_shops(state):
        for p, n in stats["shops"][s]["sold"].items():
            sold[p] = sold.get(p, 0) + n
    summary = {
        "day": state["day"],
        "revenue": revenue,
        "purchase_cost": stats["purchase_cost"],
        "spending": stats["spending"],
        "investments": stats.get("investments", 0),  # v11: shown, but not taken off the profit
        "jep": stats.get("jep", 0),
        "casino": stats.get("casino", 0),
        "bar": stats.get("bar", 0),
        "spoiled_value": spoiled_value,
        "spoiled": spoiled,
        "profit": profit,
        "sold": sold,
        # v11: the plan of every shop (managers' proposals too), so "sold vs. plan" is never 0
        "plan": _sum_plans(day_plan_by_shop(state)),
        "market_zones": market_zones(state),
        "served": sum(stats["shops"][s]["served"] for s in owned_shops(state)),
        "lost": sum(stats["shops"][s]["lost"] for s in owned_shops(state)),
        "wrong": sum(stats["shops"][s]["wrong"] for s in owned_shops(state)),
        "reputation": round(state["reputation"]),
        "market_share": round(revenue / total_market, 4) if total_market else 0.0,
        "money": state["money"],
        "tips": tips,
        "sold_out": sum(stats["shops"][s].get("sold_out", 0) for s in owned_shops(state)),
        "wasted": stats.get("wasted", 0),
        "prices": {s: dict(state["shops"][s]["prices"]) for s in SHOPS},
        "stock": _stock_report(state),
        "competitor": _competitor_report(state),
        "competitors": _competitors_overview(state),
        # per shop (managers use this for tomorrow's proposal; v8: also the shops you do not
        # own yet, so the first plan in a bought shop knows how much it used to sell)
        "by_shop": {s: {"sold": dict(stats["shops"][s]["sold"]), "served": stats["shops"][s]["served"],
                        "lost": stats["shops"][s]["lost"], "revenue": stats["shops"][s]["revenue"],
                        "sold_out_products": dict(stats["shops"][s].get("sold_out_products", {})),
                        "plan": day_plan_by_shop(state).get(s, {}),
                        "manager": state["shops"][s]["manager"]}
                    for s in SHOP_ORDER},
    }
    state["summary"] = summary
    state["history"].append(summary)
    state["total_profit"] += profit
    state["day_state"] = DAY_SUMMARY
    state["open"] = False
    state["closed"] = True
    if state["money"] <= 0:
        state["status"] = GAME_OVER
    return {"summary": summary}


def _sum_plans(plans: dict) -> dict:
    total: dict[str, int] = {}
    for plan in plans.values():
        for p, n in plan.items():
            total[p] = total.get(p, 0) + n
    return total


def _stock_report(state: dict) -> dict:
    """Per owned shop and item: opening stock, goods in, used, spoiled, closing stock."""
    report = {}
    for shop in owned_shops(state):
        items = set(state["stats"].get("flow", {}).get(shop, {})) | {b["item"] for b in state["shops"][shop]["stock"]}
        rows = {}
        for item in sorted(items):
            f = dict(_flow(state, shop, item))
            f["close"] = stock_units(state, shop, item)
            f["change"] = f["close"] - f["open"]
            rows[item] = f
        report[shop] = rows
    return report


def _bot_revenue(state: dict) -> int:
    """What the shops you do not own sold today (v11: only in the zones that are open, so the
    market share is the campus market until the beach opens, then campus and beach)."""
    return sum(state["stats"]["shops"][s]["revenue"] for s in SHOPS
               if state["shops"][s]["owner"] == "bot" and zone_open(state, SHOPS[s]["zone"]))


def market_zones(state: dict) -> list[str]:
    """v11: the zones the market share counts (campus, and the beach once it is open)."""
    return [z for z in CONFIG["zones"] if zone_open(state, z)]


def day_plan_by_shop(state: dict) -> dict:
    """v11: the plan of every shop you run today: your own plan in the shop you work in,
    the manager's (accepted) proposal in a shop with a manager."""
    plans = {}
    proposals = state.get("manager_proposals", {})
    for s in owned_shops(state):
        if state["shops"][s]["manager"] and s in proposals:
            plans[s] = dict(proposals[s].get("plan", {}))
        elif s == work_shop(state):
            plans[s] = dict(state["plan"])
    return plans


def _competitors_overview(state: dict) -> list[dict]:
    """v8: every shop you do not own yet, for the summary table (in buying order)."""
    rows = []
    target = next_target(state)
    for shop in SHOP_ORDER:
        data = state["shops"][shop]
        if data["owner"] == "player":
            continue
        s = state["stats"]["shops"][shop]
        prices = data["prices"]
        rows.append({
            "shop": shop, "name": SHOPS[shop]["name"], "icon": SHOPS[shop].get("icon", ""),
            "zone": SHOPS[shop]["zone"], "zone_open": zone_open(state, SHOPS[shop]["zone"]),
            "served": s["served"], "revenue": s["revenue"], "sold": dict(s["sold"]),
            "avg_price": round(sum(prices.values()) / len(prices)), "factor": shop_factor(state, shop),
            "price": acquisition_cost(shop), "next": shop == target, "sold_to_you": bool(data.get("sold")),
        })
    return rows


def _competitor_report(state: dict) -> dict | None:
    """How your next acquisition target did today (None once you own everything)."""
    shop = next_target(state)
    if shop is None:
        return None
    s = state["stats"]["shops"][shop]
    return {
        "shop": shop,
        "name": SHOPS[shop]["name"],
        "served": s["served"],
        "lost": s["lost"],
        "revenue": s["revenue"],
        "sold": dict(s["sold"]),
        "prices": dict(state["shops"][shop]["prices"]),
        "factor": shop_factor(state, shop),
    }


def _ev_tick(state, ev):
    """The browser reports that the clock passed an important time."""
    result = {}
    t = state["time"] + 1e-6  # the browser clock is a float: 20.9999999 counts as 21:00
    if t >= T["manager_buys_at"]:
        for bought in _managers_buy_all(state):
            result["manager_bought"] = result.get("manager_bought", []) + [bought["shop"]]
            if bought["share"] < 1 or "toast" not in result:
                result["toast"] = bought["toast"]  # v13: a short budget is the toast to see
    if not state["open"] and not state["closed"] and t >= T["open"]:
        result.update(_open(state))
        for shop in owned_shops(state):
            state["shops"][shop]["prices_set"] = True  # the prices of the day are fixed now
    for shop in SHOP_ORDER:
        mech = mechanics.of(shop)
        toasts = mech.tick(state)
        mech.manager_fill(state)
        if toasts:
            result["toasts"] = result.get("toasts", []) + toasts
            result.setdefault("toast", toasts[-1])
    if t >= T["last_customer"] and not state["last_call"]:
        state["last_call"] = True
        result["toast"] = "Last customers"
    if t >= T["close"] and not state["closed"]:
        result.update(_close(state))
    if t >= T["day_end"] and state["day_state"] != DAY_SUMMARY:
        if not state["closed"]:
            _close(state)
        result.update(_end_day(state))
    return result


def _ev_clean(state, ev):
    """v10: clean one spot of one shop (the player in the shop he runs, a manager in his)."""
    spot, shop = ev.get("spot"), ev.get("shop", "cafe")
    if not state["closed"] or state["day_state"] != CLOSING:
        raise GameError("You can only clean up after closing time.")
    if shop not in state["cleaning"]:
        raise GameError(f"{SHOPS.get(shop, {}).get('name', shop)} does not need cleaning tonight.")
    if spot not in state["cleaning"][shop]:
        raise GameError("Unknown cleaning spot.")
    state["cleaning"][shop][spot] = True
    result = {"toast": "Done"}
    if all(all(spots.values()) for spots in state["cleaning"].values()):
        result.update(_end_day(state))
    return result


def _ev_next_day(state, ev):
    _require_running(state)
    if state["day_state"] != DAY_SUMMARY:
        raise GameError("The day is not over yet.")
    _start_day(state, state["day"] + 1)
    return {"new_day": state["day"]}


# Progression ----------------------------------------------------------------


def _ev_buy_upgrade(state, ev):
    shop, upgrade = ev.get("shop", "cafe"), ev.get("upgrade")
    _require_owned(state, shop)
    catalogue = upgrade_catalogue(shop)  # v10: every shop has its own upgrades
    if upgrade not in catalogue:
        raise GameError(f"This upgrade does not fit {SHOPS[shop]['name']}.")
    if upgrade in state["shops"][shop]["upgrades"]:
        raise GameError("You already have this upgrade.")
    cost = catalogue[upgrade]["cost"]
    _pay(state, cost)
    state["shops"][shop]["upgrades"].append(upgrade)
    state["stats"]["investments"] = state["stats"].get("investments", 0) + cost  # v11
    return {"toast": f"{catalogue[upgrade]['name']} bought"}


def _ev_hire_manager(state, ev):
    shop = ev.get("shop", "cafe")
    _require_owned(state, shop)
    if state["shops"][shop]["manager_hired"]:
        raise GameError("A manager already works here.")
    cost = manager_cost(shop)
    _pay(state, cost)
    state["shops"][shop]["manager_hired"] = True  # v5: starts tomorrow morning
    state["stats"]["investments"] = state["stats"].get("investments", 0) + cost  # v11
    _check_victory(state)
    return {"toast": "Manager hired - he starts tomorrow morning"}


def manager_cost(shop: str) -> int:
    return SHOPS[shop].get("manager_cost") or CONFIG["manager_cost"]


def acquisition_cost(shop: str) -> int:
    return SHOPS[shop].get("acquisition_cost") or CONFIG["acquisition_cost"]


def zone_open(state: dict, zone: str) -> bool:
    """A zone opens once every shop of the zone named in "unlock_after" is yours."""
    after = CONFIG["zones"][zone]["unlock_after"]
    if after is None:
        return True
    return all(state["shops"][s]["owner"] == "player" for s in SHOPS if SHOPS[s]["zone"] == after)


def next_target(state: dict) -> str | None:
    """The next shop in the buying order that is not yours yet (None: you own everything)."""
    for shop in SHOP_ORDER:
        if state["shops"][shop]["owner"] != "player":
            return shop
    return None


def buy_blocker(state: dict, shop: str | None = None) -> str | None:
    """Why you cannot buy this shop now (None: you can, if you have the money)."""
    shop = shop or next_target(state)
    if shop is None:
        return "You own every shop."
    data = state["shops"][shop]
    if data["owner"] == "player":
        return "You already own this shop."
    if data.get("sold"):
        return "You already bought it - it becomes yours tomorrow morning."
    if shop != next_target(state):
        return f"Buy {SHOPS[next_target(state)]['name']} first."
    if not zone_open(state, SHOPS[shop]["zone"]):
        return f"{CONFIG['zones'][SHOPS[shop]['zone']]['name']} opens once you own every shop before it."
    missing = [s for s in owned_shops(state) if not state["shops"][s]["manager_hired"]]
    if missing:
        names = ", ".join(SHOPS[s]["name"] for s in missing)
        return f"Hire a manager in every shop you own first ({names})."
    return None


def manager_cost_estimate(state: dict) -> int:
    """v13: roughly what all your managers will spend on supplies next morning.

    A manager who already bought today will need about the same again; a manager who
    starts tomorrow needs what his proposal would cost now. Shown in the buy dialog, so
    buying a shop does not leave the managers without cash."""
    total = 0
    for shop in owned_shops(state):
        data = state["shops"][shop]
        if not (data["manager"] or data["manager_hired"]):
            continue
        today = state.get("manager_proposals", {}).get(shop)
        total += today["paid"] if today and today.get("done") else manager_proposal(state, shop)["cost"]
    return total


def _ev_buy_shop(state, ev):
    """Buy the next shop. It is yours tomorrow morning; you run it until you hire its manager."""
    shop = ev.get("shop") or next_target(state)
    if shop not in SHOPS:
        raise GameError(f"Unknown shop: {shop}.")
    blocker = buy_blocker(state, shop)
    if blocker:
        raise GameError(blocker)
    cost = acquisition_cost(shop)
    _pay(state, cost)
    # v6: the contract is signed today, the shop becomes yours tomorrow morning. Until then
    # the old owner keeps running it. Then the staff leaves and you run it yourself
    # until you hire a manager there too.
    state["shops"][shop]["sold"] = True
    state["stats"]["investments"] = state["stats"].get("investments", 0) + cost  # v11
    return {"toast": f"Contract signed! {SHOPS[shop]['name']} becomes yours tomorrow morning - you will work there yourself.",
            "bought": shop}


def _ev_buy_competitor(state, ev):
    """v2 to v6 event name: buy the next shop (Café da Esquina first)."""
    return _ev_buy_shop(state, {"shop": ev.get("shop") or next_target(state)})


def _take_over(state: dict, shop: str) -> list[str]:
    """The morning after the purchase: the shop is yours, empty, without staff.

    Returns the zones that opened with this purchase."""
    before = {z for z in CONFIG["zones"] if zone_open(state, z)}
    state["shops"][shop].update({"owner": "player", "stock": [], "staff": False, "manager": False,
                                 "manager_hired": False, "opens_day": state["day"], "prices_set": False,
                                 "sold": False, "front": {}, "mech": {}})
    opened = [z for z in CONFIG["zones"] if zone_open(state, z) and z not in before]
    if opened:
        state.setdefault("zones_opened", []).extend(opened)
    return opened


# Students and sales -----------------------------------------------------------


def _comes_today(state, sid: str, shop: str) -> bool:
    """v13: on a bad day (flat sea) only a share of the customers consider the shop at all.

    Reproducible and fixed for the whole day: a student who skips the shop today skips it
    every time he decides again, so the share really is the share of the customers."""
    chance = mechanics.of(shop).visit_chance(state)
    if chance >= 1:
        return True
    rng = random.Random(f"{state['seed']}-{state['day']}-{sid}-{shop}-visit")
    return rng.random() < chance


def _decide(state, sid: str, exclude: set[str] = frozenset(), sold_out: set[str] = frozenset()) -> dict:
    """Re-decide where to buy (or not) with the utility model."""
    student = state["students"][sid]
    zone = student.get("zone", "campus")
    shops = [s for s in SHOP_ORDER if s not in exclude and SHOPS[s]["zone"] == zone and shop_open_now(state, s)
             and _comes_today(state, sid, s)]
    if state["closed"] or state["time"] >= T["last_customer"]:
        shops = []
    choice = st.choose_order(
        student, offer_prices(state), {s: shop_factor(state, s) for s in SHOPS}, shops, sold_out
    ) if shops else None
    if choice is None:
        student["intent"] = None
        if student["status"] != st.WANDERING:
            st.transition(student, "give_up")
        return {"action": "wander"}
    shop, items = choice
    st.transition(student, "go_to_shop")
    student["intent"] = {"shop": shop, "items": items}
    return {"action": "shop", "shop": shop, "items": items}


def _ev_student_arrive(state, ev):
    student = _student(state, ev["student"])
    if student["status"] != st.OFF_MAP:
        return {"ignored": True}  # already on campus (event repeated)
    st.transition(student, "arrive")
    return {}


def _ev_student_leave(state, ev):
    """A student walks off the map (lecture or home). Repeated events are ignored."""
    student = _student(state, ev["student"])
    if student["status"] == st.OFF_MAP:
        return {"ignored": True}
    if student["status"] in (st.QUEUING, st.BEING_SERVED):
        if state["current_order"] and state["current_order"]["student"] == student["id"]:
            state["current_order"] = None
            state["tray"] = []
        st.transition(student, "give_up")
    st.transition(student, "leave")
    student["intent"] = None
    return {}


def _ev_decide(state, ev):
    student = _student(state, ev["student"])
    if student["status"] != st.WANDERING:
        return {"action": "busy"}
    # Use the scheduled decision time, so the result does not depend on frame timing or speed.
    at = float(ev.get("at", state["time"]))
    if not st.wants_to_visit(state["seed"], state["day"], student, at):
        return {"action": "wander"}
    return _decide(state, ev["student"])


def _ev_join_queue(state, ev):
    student = _student(state, ev["student"])
    intent = student.get("intent")
    if not intent or intent["shop"] != ev.get("shop"):
        raise GameError("This student did not want to go to this shop.")
    if state["closed"] or not shop_open_now(state, ev["shop"]):
        return _decide(state, student["id"], exclude={ev["shop"]})
    st.transition(student, "join_queue")
    return {}


def _ev_queue_full(state, ev):
    student = _student(state, ev["student"])
    return _decide(state, student["id"], exclude={ev.get("shop")})


def _counter_check(state, student: dict, shop: str) -> dict | None:
    """Which of the wanted items can the shop make right now? None if all of them.

    Otherwise the student re-decides without the sold-out products: he keeps the rest of
    the order here, or leaves (to another shop or home). Your reputation suffers either way."""
    sold_out = [p for p in student["intent"]["items"] if not can_make(state, shop, p)]
    if not sold_out:
        return None
    _note_sold_out(state, shop, sold_out)
    # Re-decide without the sold-out products: something else here, the other café, or nothing.
    st.transition(student, "give_up")
    decision = _decide(state, student["id"], sold_out={st.offering_key(shop, p) for p in sold_out})
    # Why customers react differently: the utility model compares the rest of the order
    # here with the other café and with keeping the money. Whatever is worth most wins.
    if decision["action"] == "shop" and decision["shop"] == shop:
        st.transition(student, "join_queue")  # stays at the counter with the new order
        # v10: still a disappointed customer (Mercado: the product was not on the shelf)
        delta = _sold_out_penalty(state, student, partial=True) if state["shops"][shop]["owner"] == "player" else 0
        return {"items": decision["items"], "sold_out": sold_out, "rep_delta": delta,
                "reason": "The rest of the order is still worth the money here."}
    delta = 0
    if state["shops"][shop]["owner"] == "player":
        state["stats"]["shops"][shop]["lost"] += 1
        state["stats"]["shops"][shop]["sold_out"] = state["stats"]["shops"][shop].get("sold_out", 0) + 1
        delta = _sold_out_penalty(state, student, to_competitor=decision["action"] == "shop")
    reason = (f"prefers {SHOPS[decision['shop']]['name']}" if decision["action"] == "shop"
              else "nothing else here is worth the money")
    return {"items": [], "sold_out": sold_out, "leaves": True, "decision": decision, "rep_delta": delta, "reason": reason}


def _ev_at_counter(state, ev):
    """A student reaches the counter: which of the wanted items can the shop make?

    v14: the browser asks again right before it shows the order pop-up, if something the
    student wants has sold out meanwhile."""
    student = _student(state, ev["student"])
    shop = ev.get("shop")
    if student["status"] != st.QUEUING or not student["intent"] or student["intent"]["shop"] != shop:
        raise GameError("This student is not at this counter.")
    if not state["open"]:
        raise GameError("The shop is not open.")
    return _counter_check(state, student, shop) or {"items": student["intent"]["items"], "sold_out": []}


def _note_sold_out(state, shop: str, products: list[str]) -> None:
    seen = state["stats"]["shops"][shop].setdefault("sold_out_products", {})
    for p in products:
        seen[p] = seen.get(p, 0) + 1


def _require_manual(state, shop: str, ev: dict) -> None:
    _require_owned(state, shop)
    if is_auto(state, shop):
        raise GameError("Staff serves here automatically.")
    if not state["open"]:
        raise GameError("The shop is not open.")
    if not ev.get("player_inside"):
        raise GameError("You have to be inside the café to serve.")


def _ev_accept(state, ev):
    shop = ev.get("shop", "cafe")
    _require_manual(state, shop, ev)
    if state["current_order"]:
        raise GameError("You are already working on an order.")
    student = _student(state, ev["student"])
    if student["status"] != st.QUEUING or student["intent"]["shop"] != shop:
        raise GameError("This student is not waiting at your counter.")
    # v14: something sold out while the student waited at the counter (for example the last
    # croissant went into the order before). Before, the order was accepted without it (no
    # reputation loss) or refused with an error. Now the student reacts as at the counter:
    # he takes the rest or leaves, and the sold-out product costs reputation.
    check = _counter_check(state, student, shop)
    if check and check.get("leaves"):
        return check
    items = check["items"] if check else student["intent"]["items"]
    student["intent"]["items"] = items
    st.transition(student, "accepted")
    state["current_order"] = {"shop": shop, "student": student["id"], "items": items,
                              "accepted_at": state["time"]}
    state["tray"] = []
    result = {"order": state["current_order"]}
    if check:
        result.update({"sold_out": check["sold_out"], "rep_delta": check["rep_delta"], "reason": check["reason"]})
    return result


def _ev_reject(state, ev):
    shop = ev.get("shop", "cafe")
    student = _student(state, ev["student"])
    if student["status"] != st.QUEUING:
        raise GameError("This student is not waiting at the counter.")
    delta = 0
    if state["shops"].get(shop, {}).get("owner") == "player":
        state["stats"]["shops"][shop]["rejected"] = state["stats"]["shops"][shop].get("rejected", 0) + 1
        delta = _change_reputation(state, CONFIG["reputation"]["rejected"])
    result = _decide(state, student["id"], exclude={shop})
    result["rep_delta"] = delta
    return result


def _ev_prepare(state, ev):
    shop, product = ev.get("shop", "cafe"), ev.get("product")
    _require_manual(state, shop, ev)
    if not state["current_order"] or state["current_order"]["shop"] != shop:
        raise GameError("Accept an order first.")
    if product not in SHOPS[shop]["products"]:
        raise GameError("This is not sold in this shop.")
    if mechanics.of(shop).service != "stations":
        raise GameError("Nothing is prepared at a station here.")
    if not can_make(state, shop, product):
        raise GameError(f"{PRODUCTS[product]['name']} is sold out.")
    _consume(state, shop, product)
    state["tray"].append(product)
    return {"toast": f"{PRODUCTS[product]['name']} ready", "tray": list(state["tray"])}


def _sell(state, shop: str, student: dict, products: list[str], tip: bool = True) -> int:
    """Book a sale: money (for player shops), tip, statistics, student's budget."""
    amount = sum(price_now(state, shop, p) for p in products)
    stats = state["stats"]["shops"][shop]
    state["last_tip"] = 0
    if state["shops"][shop]["owner"] == "player":
        # v8: a vending machine keeps the money in its cash box until you collect it
        state["money"] += mechanics.of(shop).cash_in(state, amount)
        stats["revenue"] += amount
        if tip and mechanics.of(shop).staffed:
            extra = round(amount * tip_rate(state["reputation"]))
            state["money"] += extra
            stats["tips"] = stats.get("tips", 0) + extra
            state["last_tip"] = extra
    else:
        state["stats"]["rival_revenue"] += amount  # all shops you do not own (name kept from v2)
        stats["revenue"] += amount
    for p in products:
        stats["sold"][p] = stats["sold"].get(p, 0) + 1
    stats["served"] += 1
    student["budget"] -= amount
    student["purchases"].append({"shop": shop, "items": list(products), "time": state["time"]})
    return amount


def _change_reputation(state, delta: float) -> float:
    """Change the reputation (0-100). Returns the real change."""
    before = state["reputation"]
    state["reputation"] = max(0, min(100, before + delta))
    return state["reputation"] - before


def _customer_reputation(state, delta: float) -> float:
    """v13: change the reputation for a customer who waited too long or was served by a manager.

    Both share one daily budget of +-``customer_daily_cap`` (net, counted in ``stats``,
    which start fresh every morning): a gain first makes up for the day's losses. So one
    shop full of impatient customers cannot crash the reputation to 0, and hundreds of
    happy manager customers cannot push it from 0 to 100 in a day."""
    cap = CONFIG["reputation"]["customer_daily_cap"]
    net = state["stats"].get("customer_rep_net", 0.0)
    delta = _change_reputation(state, max(-cap - net, min(cap - net, delta)))
    state["stats"]["customer_rep_net"] = net + delta
    return delta


def _ev_handover(state, ev):
    shop = ev.get("shop", "cafe")
    _require_manual(state, shop, ev)
    order = state["current_order"]
    if not order or order["student"] != ev.get("student"):
        raise GameError("This order is not in progress.")
    student = _student(state, order["student"])
    remaining = list(state["tray"])
    delivered = []
    for p in order["items"]:
        if p in remaining:
            remaining.remove(p)
            delivered.append(p)
    correct = len(delivered) == len(order["items"]) and not remaining
    amount = _sell(state, shop, student, delivered, tip=correct) if delivered else 0
    tip = state.pop("last_tip", 0) if delivered else 0
    rep = CONFIG["reputation"]
    if correct:
        fast = (state["time"] - order["accepted_at"]) * 60 <= T["fast_service_minutes"]
        delta = _change_reputation(state, rep["correct_order"] + (rep["fast_bonus"] if fast else 0))
        toast = f"Happy customer: +{euro(amount)}" + (f" (+{euro(tip)} tip)" if tip else "")
    else:
        state["stats"]["shops"][shop]["wrong"] += 1
        delta = _change_reputation(state, rep["wrong_order"])
        toast = f"Wrong order - unhappy customer (+{euro(amount)})"
    st.transition(student, "served")
    student["intent"] = None
    state["current_order"] = None
    state["tray"] = []
    return {"toast": toast, "amount": amount, "tip": tip, "correct": correct, "rep_delta": delta}


def _ev_patience_expired(state, ev):
    student = _student(state, ev["student"])
    shop = ev.get("shop")
    if student["status"] not in (st.QUEUING, st.BEING_SERVED):
        return {"action": "ignored"}
    state["stats"]["shops"][shop]["lost"] += 1
    delta = 0
    if state["shops"][shop]["owner"] == "player":
        delta = _customer_reputation(state, CONFIG["reputation"]["customer_lost"])
    if state["current_order"] and state["current_order"]["student"] == student["id"]:
        state["current_order"] = None
        state["tray"] = []
    result = _decide(state, student["id"], exclude={shop})
    result["toast"] = "A customer left"
    result["rep_delta"] = delta
    return result


def _sold_out_penalty(state, student: dict, to_competitor: bool = False, partial: bool = False) -> float:
    """A student who finds your shelves empty and leaves costs reputation, every time (v8).

    Going to a competitor instead costs more than simply going home."""
    student["disappointed"] = True
    key = "sold_out_partial" if partial else "sold_out_to_competitor" if to_competitor else "sold_out_left"
    # at most this much per day, so one bad day cannot destroy the whole reputation
    lost = state["stats"].get("sold_out_rep", 0)
    delta = max(CONFIG["reputation"][key], -(CONFIG["reputation"]["sold_out_daily_cap"] - lost))
    delta = _change_reputation(state, delta)
    state["stats"]["sold_out_rep"] = lost - delta
    return delta


def _ev_discard_tray(state, ev):
    """Throw away products from the tray. The ingredients are lost.

    ``product``: only one portion of it; ``only_extras``: everything the order does not need;
    otherwise the whole tray."""
    shop = ev.get("shop", "cafe")
    _require_manual(state, shop, ev)
    tray = state["tray"]
    if not tray:
        raise GameError("The tray is empty.")
    if ev.get("product"):
        if ev["product"] not in tray:
            raise GameError("This product is not on the tray.")
        tray.remove(ev["product"])
        removed = [ev["product"]]
    elif ev.get("only_extras"):
        need = list(state["current_order"]["items"]) if state["current_order"] else []
        keep, removed = [], []
        for p in tray:
            if p in need:
                need.remove(p)
                keep.append(p)
            else:
                removed.append(p)
        if not removed:
            raise GameError("Everything on the tray belongs to the order.")
        state["tray"] = keep
    else:
        removed = list(tray)
        state["tray"] = []
    state["stats"]["wasted"] = state["stats"].get("wasted", 0) + len(removed)
    names = ", ".join(PRODUCTS[p]["name"] for p in removed)
    return {"toast": f"Thrown away: {names}", "removed": removed, "tray": list(state["tray"])}


def _ev_cancel_order(state, ev):
    """You give up on the accepted order: the customer leaves unhappy."""
    shop = ev.get("shop", "cafe")
    _require_manual(state, shop, ev)
    order = state["current_order"]
    if not order or order["shop"] != shop:
        raise GameError("There is no order to cancel.")
    student = _student(state, order["student"])
    state["stats"]["shops"][shop]["lost"] += 1
    state["stats"]["wasted"] = state["stats"].get("wasted", 0) + len(state["tray"])
    state["current_order"] = None
    state["tray"] = []
    delta = _change_reputation(state, CONFIG["reputation"]["order_cancelled"])
    st.transition(student, "give_up")
    result = _decide(state, student["id"], exclude={shop})
    result.update({"toast": "Order cancelled - the customer leaves", "student": student["id"], "rep_delta": delta})
    return result


def _ev_auto_serve(state, ev):
    """Bot or manager serves the student at the front of the queue."""
    shop = ev.get("shop")
    mechanics.of(shop).serve_at(state, ev.get("machine"))  # v8: which vending machine
    if not is_auto(state, shop):
        raise GameError("Someone has to serve here in person.")
    if not state["open"]:
        raise GameError("The shop is not open.")
    student = _student(state, ev["student"])
    if student["status"] != st.QUEUING or not student["intent"] or student["intent"]["shop"] != shop:
        raise GameError("This student is not waiting here.")
    items, missing = [], []
    for p in student["intent"]["items"]:
        if can_make(state, shop, p):
            if state["shops"][shop]["owner"] == "player":
                _consume(state, shop, p)
            items.append(p)
        else:
            missing.append(p)
    if missing:
        _note_sold_out(state, shop, missing)
    amount = _sell(state, shop, student, items) if items else 0
    tip = state.pop("last_tip", 0) if items else 0
    delta = 0
    if state["shops"][shop]["owner"] == "player":
        if not items:
            state["stats"]["shops"][shop]["lost"] += 1
            state["stats"]["shops"][shop]["sold_out"] = state["stats"]["shops"][shop].get("sold_out", 0) + 1
            delta = _sold_out_penalty(state, student)
        elif not missing:
            # v5: happy customers of your manager also improve the reputation
            delta = _customer_reputation(state, CONFIG["reputation"]["staff_served"])
        else:
            delta = _sold_out_penalty(state, student, partial=True)  # v10: got only part of it
    st.transition(student, "served")
    student["intent"] = None
    return {"items": items, "amount": amount, "tip": tip, "rep_delta": delta}


def _ev_resume(state, ev):
    """Continuing a saved game: students in a queue or on their way start fresh on campus."""
    for s in state["students"].values():
        if s["status"] in (st.WALKING_TO_SHOP, st.QUEUING, st.BEING_SERVED):
            s["status"] = st.WANDERING
            s["intent"] = None
    state["current_order"] = None
    state["tray"] = []
    if state["in_wholesaler"]:
        # The player starts outside again: unpaid goods go back on the shelf.
        state["in_wholesaler"] = False
        state["cart"] = {}
        state["cart_prefilled"] = False
    return {}


# v7: mechanics -----------------------------------------------------------------


def _ev_fill_front(state, ev):
    """Fill machines, shelves or a display from the storage (P25, P28, P33)."""
    shop = ev.get("shop")
    _require_owned(state, shop)
    mech = mechanics.of(shop)
    if not mech.front_products():
        raise GameError("This shop has nothing to fill.")
    if mech.front_fill == "before" and state["time"] >= mech.p["fill_until"] - 1e-6:
        raise GameError(f"The shelves can only be filled in the morning, before {int(mech.p['fill_until']):02d}:00.")
    if state["closed"]:
        raise GameError("The shop is closed for today.")
    if hasattr(mech, "refill"):  # v8: vending machines are filled one by one (or all at once)
        return _ev_refill_machine(state, ev)
    amounts = ev.get("amounts")
    if amounts is not None:
        for product, n in amounts.items():
            if product not in mech.front_products():
                raise GameError(f"{product} is not sold here.")
            _whole(n, "The amount")
    moved = fill_front(state, shop, amounts)
    if not moved:
        raise GameError("Nothing to fill: the storage is empty or there is no room left.")
    names = ", ".join(f"{n}x {PRODUCTS[p]['name']}" for p, n in moved.items())
    return {"toast": f"Filled: {names}", "moved": moved}


def _ev_repair(state, ev):
    """Repair a broken vending machine for a fee (P26)."""
    shop, product = ev.get("shop"), ev.get("product")
    _require_owned(state, shop)
    mech = mechanics.of(shop)
    if not hasattr(mech, "repair"):
        raise GameError("Nothing to repair here.")
    cost = mech.repair(state, ev.get("machine") or product)
    return {"toast": f"Machine repaired for {euro(cost)}"}


def _ev_assemble(state, ev):
    """Put a bowl together from the chosen ingredients (P29). A wrong set makes a wrong bowl."""
    shop = ev.get("shop")
    mech = mechanics.of(shop)
    if mech.service != "assembly":
        raise GameError("Nothing is assembled here.")
    _require_manual(state, shop, ev)
    if not state["current_order"] or state["current_order"]["shop"] != shop:
        raise GameError("Accept an order first.")
    chosen = ev.get("ingredients") or []
    if not chosen or len(set(chosen)) != len(chosen) or not set(chosen) <= set(mech.p["ingredients"]):
        raise GameError("Pick the ingredients for the bowl.")
    missing = [ITEMS[i]["name"] for i in chosen if stock_units(state, shop, i) < 1]
    if missing:
        raise GameError(f"Out of {', '.join(missing)}.")
    _use_ingredients(state, shop, {i: 1 for i in chosen})
    product = mech.result(set(chosen))
    state["tray"].append(product)
    return {"toast": f"{PRODUCTS[product]['name']} ready" if product in SHOPS[shop]["products"] else "Wrong bowl",
            "product": product, "tray": list(state["tray"])}


def _ev_manager_service(state, ev):
    """v11: the vending manager reached a machine on his round: repair, refill, take the cash."""
    shop, machine = ev.get("shop"), ev.get("machine")
    _require_owned(state, shop)
    mech = mechanics.of(shop)
    if not hasattr(mech, "service_machine"):
        raise GameError("There are no machines here.")
    if not state["shops"][shop]["manager"]:
        raise GameError("This shop has no manager.")
    done = mech.service_machine(state, machine)
    name = next(m["name"] for m in mech.p["machines"] if m["id"] == machine)
    parts = []
    if done["repaired"]:
        parts.append("repaired")
    if done["moved"]:
        parts.append(f"refilled {sum(done['moved'].values())}")
    if done["cash"]:
        parts.append(f"collected {euro(done['cash'])}")
    result = dict(done, amount=done["cash"])
    if parts:
        result["toast"] = f"Manager at {name}: " + ", ".join(parts)
    return result


def _ev_set_happy_hour(state, ev):
    """Praia Bar: choose the happy hour discount (P32)."""
    shop = ev.get("shop")
    _require_owned(state, shop)
    mech = mechanics.of(shop)
    if not hasattr(mech, "set_discount"):
        raise GameError("This shop has no happy hour.")
    mech.set_discount(state, ev.get("discount"))
    return {"toast": f"Happy hour: {round(mech.discount(state) * 100)} % off"}


def _ev_refill_machine(state, ev):
    """v8: fill one vending machine on the campus from the storage (P25)."""
    shop = ev.get("shop")
    _require_owned(state, shop)
    mech = mechanics.of(shop)
    if not hasattr(mech, "refill"):
        raise GameError("There are no machines here.")
    if state["closed"]:
        raise GameError("The shop is closed for today.")
    moved = mech.refill(state, ev.get("machine"))
    if not moved:
        raise GameError("Nothing to refill: the storage is empty or the machine is full.")
    return {"toast": "Refilled: " + ", ".join(f"{n}x {PRODUCTS[p]['name']}" for p, n in moved.items()), "moved": moved}


def _ev_collect_cash(state, ev):
    """v8: take the money out of a vending machine. Bring it to the office (deposit_cash)."""
    shop = ev.get("shop")
    _require_owned(state, shop)
    mech = mechanics.of(shop)
    if not hasattr(mech, "collect"):
        raise GameError("There are no machines here.")
    amount = mech.collect(state, ev.get("machine"))
    if not amount:
        raise GameError("The cash box is empty.")
    state["carried_cash"] = state.get("carried_cash", 0) + amount
    return {"toast": f"Collected {euro(amount)} - bring it to the office", "amount": amount}


def _ev_deposit_cash(state, ev):
    """v8: hand in the collected cash at the vending office."""
    shop = ev.get("shop")
    _require_owned(state, shop)
    amount = state.get("carried_cash", 0)
    if not amount:
        raise GameError("You carry no cash.")
    state["money"] += amount
    state["carried_cash"] = 0
    return {"toast": f"Deposited {euro(amount)}", "amount": amount}


def _ev_autosave(state, ev):
    """v8: the browser reports the clock every few seconds, so the save is never far behind."""
    return {}


def _ev_buy_from_jep(state, ev):
    """v8 easter egg: Jep sells you a joint; you are high for a few game minutes."""
    try:
        easter_eggs.buy_from_jep(state)
    except easter_eggs.EasterEggError as error:
        raise GameError(str(error)) from error
    return {"toast": f"Jep: 'Enjoy, my friend.' (-{euro(easter_eggs.JEP['price'])})", "high_until": state["high_until"]}


def _ev_enter_casino(state, ev):
    """v8 easter egg: you found the ladder under the broken machine."""
    casino = state.setdefault("casino", {"spins": 0, "net": 0})
    first = not casino.get("found")
    casino["found"] = True
    return {"first_visit": first}


def _ev_roulette(state, ev):
    """v8 easter egg: one roulette spin (red/black, even/odd or a dozen)."""
    try:
        result = easter_eggs.spin(state, ev.get("bet"), _whole(ev.get("amount"), "amount"))
    except easter_eggs.EasterEggError as error:
        raise GameError(str(error)) from error
    return result


def _ev_buy_drink(state, ev):
    """v9 easter egg: a drink at the casino bar; you are tipsy for a few game minutes."""
    try:
        res = easter_eggs.buy_drink(state, ev.get("drink"))
    except easter_eggs.EasterEggError as error:
        raise GameError(str(error)) from error
    spec = easter_eggs.BAR["drinks"][res["drink"]]
    return {"toast": f"{spec['icon']} {spec['name']} (-{euro(spec['price'])}). Cheers!", "drunk_until": state["drunk_until"]}


def _ev_slot(state, ev):
    """v9 easter egg: one pull of a one-armed bandit."""
    try:
        return easter_eggs.pull_slot(state, ev.get("machine"), _whole(ev.get("amount"), "amount"))
    except easter_eggs.EasterEggError as error:
        raise GameError(str(error)) from error


def _ev_checkout(state, ev):
    """Scan the shopping of the customer at the register (P09 in a self-service shop)."""
    shop = ev.get("shop")
    if mechanics.of(shop).service != "checkout":
        raise GameError("This shop has no checkout.")
    _ev_accept(state, ev)
    for product in list(state["current_order"]["items"]):
        _consume(state, shop, product)
        state["tray"].append(product)
    return _ev_handover(state, ev)


HANDLERS = {
    "resume": _ev_resume,
    "confirm_plan": _ev_confirm_plan,
    "enter_wholesaler": _ev_enter_wholesaler,
    "leave_wholesaler": _ev_leave_wholesaler,
    "set_cart_item": _ev_set_cart_item,
    "pay": _ev_pay,
    "stock_goods": _ev_stock_goods,
    "set_prices": _ev_set_prices,
    "open_shop": _ev_open_shop,
    "tick": _ev_tick,
    "clean": _ev_clean,
    "next_day": _ev_next_day,
    "buy_upgrade": _ev_buy_upgrade,
    "hire_manager": _ev_hire_manager,
    "buy_competitor": _ev_buy_competitor,
    "buy_shop": _ev_buy_shop,
    "student_arrive": _ev_student_arrive,
    "student_leave": _ev_student_leave,
    "decide": _ev_decide,
    "join_queue": _ev_join_queue,
    "queue_full": _ev_queue_full,
    "at_counter": _ev_at_counter,
    "accept": _ev_accept,
    "reject": _ev_reject,
    "prepare": _ev_prepare,
    "handover": _ev_handover,
    "patience_expired": _ev_patience_expired,
    "auto_serve": _ev_auto_serve,
    "discard_tray": _ev_discard_tray,
    "cancel_order": _ev_cancel_order,
    "confirm_manager_plan": _ev_confirm_manager_plan,
    "confirm_all_manager_plans": _ev_confirm_all_manager_plans,
    "continue_open_mode": _ev_continue_open_mode,
    "fill_front": _ev_fill_front,
    "repair": _ev_repair,
    "checkout": _ev_checkout,
    "assemble": _ev_assemble,
    "set_happy_hour": _ev_set_happy_hour,
    "refill_machine": _ev_refill_machine,
    "manager_service": _ev_manager_service,  # v11
    "autosave": _ev_autosave,
    "collect_cash": _ev_collect_cash,
    "deposit_cash": _ev_deposit_cash,
    "buy_from_jep": _ev_buy_from_jep,
    "enter_casino": _ev_enter_casino,
    "roulette": _ev_roulette,
    "buy_drink": _ev_buy_drink,
    "slot": _ev_slot,
}



def apply(state: dict, event: dict, inplace: bool = False) -> tuple[dict, dict]:
    """Apply one event. Returns (new_state, result). Raises GameError if not allowed.

    ``inplace=True`` skips the safety copy (only for the headless balance simulation,
    which plays thousands of days)."""
    kind = event.get("type")
    if kind not in HANDLERS:
        raise GameError(f"Unknown event: {kind}.")
    if state["status"] != RUNNING and not (kind == "continue_open_mode" and state["status"] == VICTORY):
        raise GameError("The game is over.")
    new = state if inplace else copy.deepcopy(state)
    # v11: the browser stamps each event with its day. An event of yesterday that arrives after
    # "next_day" (an autosave sent at 21:00 while the new day was loading) keeps its effect
    # but must not move the new morning to 21:00 (that ended the new day at its first tick).
    stale = kind != "next_day" and "day" in event and event["day"] != new["day"]
    if "t" in event and not stale:
        t = float(event["t"])
        if t < new["time"] - 1e-6 and kind != "next_day":
            t = new["time"]  # time never runs backwards
        new["time"] = min(max(t, T["day_start"]), T["day_end"])
    try:
        result = HANDLERS[kind](new, event)
    except st.TransitionError as error:
        raise GameError(str(error)) from error
    return new, result or {}


# ---------------------------------------------------------------------------
# What the browser needs to know
# ---------------------------------------------------------------------------


OBJECTIVES = {
    MORNING_PLANNING: "Go to the planning board in your café and plan your day.",
    WALK_TO_WHOLESALE: "Walk to the wholesaler - follow the marker.",
    WHOLESALE_SHOPPING: "Put goods in your cart and pay at the checkout.",
    WALK_TO_CAFE: "Bring the goods to your café and stock them.",
    SET_PRICES: "Set your prices at the counter and open the café.",
    "PRICES_SET": "Prices set - open the café at the counter.",  # v13
    SHOP_OPEN: "Serve your customers at the counter.",
    CLOSING: "Clean up the café.",
    DAY_SUMMARY: "Check the daily summary.",
}


def objective(state: dict) -> str:
    if state["status"] == VICTORY:
        return "Monopoly reached!"
    if state["status"] == GAME_OVER:
        return "Bankrupt - start a new game?"
    ds = state["day_state"]
    ws = work_shop(state)
    if ws is None and ds not in (CLOSING, DAY_SUMMARY):
        owned = owned_shops(state)
        runs = "Your manager runs the café" if len(owned) == 1 else f"Your managers run your {len(owned)} shops"
        pending = [s for s in SHOP_ORDER if state["shops"][s].get("sold") and state["shops"][s]["owner"] == "bot"]
        if pending:
            return f"{runs}. Tomorrow you start in {SHOPS[pending[0]]['name']}."
        mine_without = [s for s in owned if not state["shops"][s]["manager_hired"]]
        if mine_without:
            return f"{runs} - you run {SHOPS[mine_without[0]]['name']}."
        target = next_target(state)
        if target:
            return f"{runs}. Save up and buy the next shop: {SHOPS[target]['name']} ({euro(acquisition_cost(target))})."
        return "Your managers run every shop on the map."
    if ds == CLOSING:  # v10: the player cleans the shop he ran, managers clean theirs
        mine = [s for s in state["cleaning"] if not state["shops"][s]["manager"] and cleaning_left(state, s)]
        if mine:
            s = mine[0]
            total = len(state["cleaning"][s])
            return f"Clean up {SHOPS[s]['name']} ({total - cleaning_left(state, s)}/{total})."
        busy = [s for s in state["cleaning"] if cleaning_left(state, s)]
        if busy:
            left = sum(cleaning_left(state, s) for s in busy)
            return f"Your manager{'s' if len(busy) > 1 else ''} clean{'' if len(busy) > 1 else 's'} up ({left} spots left)."
    special = mechanics.of(ws).objective(state, ds) if ws else None
    if special and ds in (SET_PRICES, SHOP_OPEN):
        return special
    if ws and ds == SET_PRICES and state["shops"][ws]["prices_set"]:
        ds = "PRICES_SET"  # v13: the prices are saved, only opening is left
    if ws and SHOPS[ws]["start_owner"] != "player" and ds in (MORNING_PLANNING, WALK_TO_CAFE, SET_PRICES, SHOP_OPEN, "PRICES_SET"):
        text = OBJECTIVES[WALK_TO_CAFE if ds == WALK_TO_WHOLESALE and state["bag"] else ds]
        return text.replace("in your café", f"for {SHOPS[ws]['name']}").replace("your café", SHOPS[ws]["name"])
    if ds == WALK_TO_WHOLESALE and state["bag"]:
        return OBJECTIVES[WALK_TO_CAFE]
    return OBJECTIVES[ds]


def view(state: dict) -> dict:
    """Everything the browser shows. Utilities stay secret in Python."""
    shops = {}
    for s in SHOPS:
        d = state["shops"][s]
        stock = {}
        for b in d["stock"]:
            entry = stock.setdefault(b["item"], {"units": 0, "batches": []})
            entry["units"] += b["units"]
            shelf = ITEMS[b["item"]]["shelf_days"]
            entry["batches"].append({"units": b["units"], "days_left": None if shelf is None else shelf - b["age"]})
        shops[s] = {
            "owner": d["owner"], "prices": d["prices"], "upgrades": d["upgrades"],
            "manager": d["manager"], "manager_hired": d.get("manager_hired", d["manager"]),
            "staff": d.get("staff", False), "auto": is_auto(state, s),
            "operating": shop_operating(state, s), "opens_day": d.get("opens_day", 1),
            "prices_set": d.get("prices_set", True),
            "factor": shop_factor(state, s),
            "stock": stock,
            "portions": {p: portions(state, s, p) for p in SHOPS[s]["products"]},
            "can_make": {p: can_make(state, s, p) for p in SHOPS[s]["products"]},
            # v7
            "sold": bool(d.get("sold")),
            "open_now": shop_open_now(state, s),
            "price_now": {p: price_now(state, s, p) for p in SHOPS[s]["products"]},
            "front": {p: front_units(state, s, p) for p in mechanics.of(s).front_products()},
            "front_room": {p: front_room(state, s, p) for p in mechanics.of(s).front_products()},
            "mech": mechanics.of(s).view(state),
            "service": mechanics.of(s).service,
            "staffed": mechanics.of(s).staffed,
        }
    return {
        "day": state["day"],
        "time": state["time"],
        "status": state["status"],
        "day_state": state["day_state"],
        "objective": objective(state),
        "money": state["money"],
        "reputation": round(state["reputation"]),
        "rep_perks": reputation_perks(state),
        # v14: only what the summary table shows (the full days were 40+ KB in every answer)
        "history": [{k: h.get(k) for k in ("day", "revenue", "tips", "profit", "served", "lost", "reputation", "money")}
                    | ({"competitor": {"revenue": h["competitor"].get("revenue"), "served": h["competitor"].get("served")}}
                       if h.get("competitor") else {})
                    for h in state["history"][-7:]],
        # small numbers per day for the charts (all days)
        "chart": [{k: h.get(k) for k in ("day", "revenue", "tips", "profit", "served", "lost", "reputation",
                                         "market_share", "money", "investments", "market_zones")} |
                  {"competitor_revenue": (h.get("competitor") or {}).get("revenue")} for h in state["history"]],
        "market_zones": market_zones(state),  # v11
        "today": _today(state),
        "work_shop": work_shop(state),
        "manager_proposals": state.get("manager_proposals", {}),
        "shops": shops,
        "plan": state["plan"],
        "shopping_list": state["shopping_list"],
        "cart": state["cart"],
        "cart_total": cart_total(state["cart"]),
        "bag": state["bag"],
        "in_wholesaler": state["in_wholesaler"],
        "open": state["open"],
        "closed": state["closed"],
        "current_order": state["current_order"],
        "tray": state["tray"],
        "cleaning": state["cleaning"],
        "summary": state["summary"],
        "restock": state.get("restock"),
        "yesterday": state["history"][-1] if state["history"] else None,
        "total_profit": state["total_profit"],
        # v7: the monopoly race
        "next_target": next_target(state),
        "buy_blocker": buy_blocker(state),
        "for_sale": next_target(state) if buy_blocker(state) is None else None,
        # v13: what your managers will roughly need for tomorrow's supplies (shown when buying a shop)
        "manager_cost_estimate": manager_cost_estimate(state) if buy_blocker(state) is None else 0,
        "zones_open": [z for z in CONFIG["zones"] if zone_open(state, z)],
        "zone_news": state.get("zone_news", []),
        "carried_cash": state.get("carried_cash", 0),
        # v8 easter eggs
        "jep": state.get("jep"),
        "high_until": state.get("high_until", 0),
        "drunk_until": state.get("drunk_until", 0),
        "casino": state.get("casino", {"spins": 0, "net": 0}),
        "weather": state.get("weather"),
        "items_available": [i for i in ITEMS if item_available(state, i)],
        "monopoly": monopoly_progress(state),
        # v5/v6 names, kept for the first acquisition
        "can_buy_competitor": next_target(state) == "rival" and buy_blocker(state) is None,
        "rival_sold": bool(state["shops"]["rival"].get("sold")),
        "open_mode": bool(state.get("open_mode")),
        "students": {
            sid: {"name": s["name"], "status": s["status"], "intent": s["intent"],
                  "traits": s["traits"], "look": s["look"], "zone": s.get("zone", "campus")}
            for sid, s in state["students"].items()
        },
    }


def _today(state: dict) -> dict:
    """Running numbers of the current day (for the day gain next to the cash)."""
    stats = state["stats"]
    shops = owned_shops(state)
    revenue = sum(stats["shops"][s]["revenue"] for s in shops)
    tips = sum(stats["shops"][s].get("tips", 0) for s in shops)
    gain = (revenue + tips - stats["purchase_cost"] - stats["spending"] - stats.get("jep", 0)
            + stats.get("casino", 0) - stats.get("bar", 0))
    market = revenue + _bot_revenue(state)
    return {
        "revenue": revenue, "tips": tips, "purchase_cost": stats["purchase_cost"], "spending": stats["spending"],
        "investments": stats.get("investments", 0),
        "jep": stats.get("jep", 0), "casino": stats.get("casino", 0), "bar": stats.get("bar", 0),
        "gain": gain,
        "served": sum(stats["shops"][s]["served"] for s in shops),
        "lost": sum(stats["shops"][s]["lost"] for s in shops),
        "sold": {p: sum(stats["shops"][s]["sold"].get(p, 0) for s in shops)
                 for p in {p for s in shops for p in stats["shops"][s]["sold"]}},
        "rival_revenue": stats["rival_revenue"], "rival_served": stats["shops"]["rival"]["served"],
        "bot_served": sum(stats["shops"][s]["served"] for s in SHOPS if state["shops"][s]["owner"] == "bot"),
        "market_share": round(revenue / market, 4) if market else 0.0,
    }


def day_plan(state: dict) -> dict:
    """Per-day data for the browser: who is on campus when, and when they think about buying."""
    return {"day": state["day"], "seed": state["seed"], "schedule": state["schedule"]}
