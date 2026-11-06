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

import students as st
from config import CONFIG

T = CONFIG["time"]
ITEMS = CONFIG["wholesale_items"]
PRODUCTS = CONFIG["products"]
SHOPS = CONFIG["shops"]

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
        "shops": {s: {"revenue": 0, "sold": {}, "served": 0, "lost": 0, "wrong": 0} for s in SHOPS},
        "purchase_cost": 0,
        "spending": 0,
        "rival_revenue": 0,
    }


def new_game(seed: int | None = None) -> dict:
    if seed is None:
        seed = random.randrange(1, 1_000_000_000)
    shops = {
        s: {
            "owner": spec["start_owner"],
            "prices": dict(spec["start_prices"]),
            "upgrades": [],
            "manager": False,
            # Staff who serve automatically: the competitor's barista (also after you buy it).
            "staff": spec["start_owner"] == "bot",
            "stock": [],
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
    lo, hi = CONFIG["reputation"]["factor_range"]
    return round(lo + (hi - lo) * max(0, min(100, reputation)) / 100, 4)


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
        "cleaning": {spot: False for spot in CONFIG["cleaning_spots"]},
        "stats": _empty_stats(),
        "summary": None,
        "students": st.make_pool(state["seed"], day),
        "schedule": st.make_schedule(state["seed"], day),
        "restock": None,
    })
    if state["shops"]["rival"]["owner"] == "player" and state["shops"]["rival"].get("staff"):
        state["restock"] = _restock_rival(state)
    return state


def migrate(state: dict) -> dict:
    """Bring a saved game from an older version up to date (in place)."""
    for shop_id, shop in state["shops"].items():
        if "staff" not in shop:
            # The competitor's barista always stays, also in games bought in v2.
            shop["staff"] = shop_id == "rival"
    state.setdefault("cart_prefilled", False)
    state.setdefault("restock", None)
    return state


def _restock_rival(state: dict) -> dict:
    """The barista of the bought competitor orders supplies for the restock plan.

    Buys whole wholesale packs for what is missing, only as far as the money goes.
    The cost is booked as today's purchase cost.
    """
    shop = state["shops"]["rival"]
    need: dict[str, int] = {}
    for product, portions in CONFIG["rival_restock_plan"].items():
        for item, qty in PRODUCTS[product]["uses"].items():
            need[item] = need.get(item, 0) + portions * qty
    bought: dict[str, int] = {}
    cost = 0
    for item, units in need.items():
        missing = max(0, units - stock_units(state, "rival", item))
        packs = math.ceil(missing / ITEMS[item]["base_units"])
        affordable = min(packs, state["money"] // ITEMS[item]["price"])
        if affordable <= 0:
            continue
        price = affordable * ITEMS[item]["price"]
        state["money"] -= price
        cost += price
        shop["stock"].append({"item": item, "units": affordable * ITEMS[item]["base_units"], "age": 0})
        bought[item] = affordable
    state["stats"]["purchase_cost"] += cost
    return {"cost": cost, "items": bought}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def owned_shops(state: dict) -> list[str]:
    return [s for s in SHOPS if state["shops"][s]["owner"] == "player"]


def is_auto(state: dict, shop: str) -> bool:
    """Shops with a bot owner, a manager or staff serve automatically."""
    data = state["shops"][shop]
    return data["owner"] == "bot" or data["manager"] or data.get("staff", False)


def shop_factor(state: dict, shop: str) -> float:
    data = state["shops"][shop]
    factor = SHOPS[shop]["base_factor"] + sum(
        CONFIG["upgrades"][u]["factor_bonus"] for u in data["upgrades"]
    )
    if data["owner"] == "player":
        factor *= state["rep_factor"]
    return round(factor, 4)


def offer_prices(state: dict) -> dict[str, int]:
    return {
        st.offering_key(s, p): state["shops"][s]["prices"][p]
        for s in SHOPS for p in SHOPS[s]["products"]
    }


def item_available(state: dict, item: str) -> bool:
    return not ITEMS[item]["needs_rival"] or state["shops"]["rival"]["owner"] == "player"


def stock_units(state: dict, shop: str, item: str) -> int:
    return sum(b["units"] for b in state["shops"][shop]["stock"] if b["item"] == item)


def can_make(state: dict, shop: str, product: str) -> bool:
    if state["shops"][shop]["owner"] == "bot":
        return True
    return all(stock_units(state, shop, i) >= q for i, q in PRODUCTS[product]["uses"].items())


def _consume(state: dict, shop: str, product: str) -> None:
    """Use ingredients for one portion, oldest batch first."""
    stock = state["shops"][shop]["stock"]
    for item, qty in PRODUCTS[product]["uses"].items():
        for batch in sorted((b for b in stock if b["item"] == item), key=lambda b: -b["age"]):
            take = min(qty, batch["units"])
            batch["units"] -= take
            qty -= take
            if qty == 0:
                break
    state["shops"][shop]["stock"] = [b for b in stock if b["units"] > 0]


def _shop_items(shop: str) -> set[str]:
    return {i for p in SHOPS[shop]["products"] for i in PRODUCTS[p]["uses"]}


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


def _check_victory(state: dict) -> None:
    if all(d["owner"] == "player" and d["manager"] for d in state["shops"].values()):
        state["status"] = VICTORY


def _student(state: dict, sid: str) -> dict:
    if sid not in state["students"]:
        raise GameError(f"Unknown student: {sid}.")
    return state["students"][sid]


# ---------------------------------------------------------------------------
# Planning and shopping list
# ---------------------------------------------------------------------------


def shopping_list(state: dict, plan: dict[str, int]) -> dict[str, int]:
    """Wholesale units needed: planned portions minus usable stock, rounded up to packs."""
    need: dict[str, int] = {}
    for product, portions in plan.items():
        for item, qty in PRODUCTS[product]["uses"].items():
            need[item] = need.get(item, 0) + portions * qty
    result = {}
    for item, units in need.items():
        have = sum(stock_units(state, s, item) for s in owned_shops(state))
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
    sellable = {p for s in owned_shops(state) for p in SHOPS[s]["products"]}
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
    if not state["cart"] and state["shopping_list"] and not state["cart_prefilled"]:
        # Only the first visit after planning starts with the shopping list in the cart.
        state["cart"] = {i: q for i, q in state["shopping_list"].items() if item_available(state, i)}
        state["cart_prefilled"] = True
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
        state["shops"][shop]["stock"].append(
            {"item": item, "units": packs * ITEMS[item]["base_units"], "age": 0}
        )
        del state["bag"][item]
    if state["day_state"] in (MORNING_PLANNING, WALK_TO_WHOLESALE, WHOLESALE_SHOPPING, WALK_TO_CAFE):
        state["day_state"] = SET_PRICES if not state["open"] else SHOP_OPEN
    return {"toast": "Goods stocked"}


def _ev_set_prices(state, ev):
    shop = ev.get("shop", "cafe")
    _require_owned(state, shop)
    if state["open"] or state["closed"]:
        raise GameError("You can only change prices before opening.")
    prices = ev.get("prices") or {}
    for product, price in prices.items():
        if product not in SHOPS[shop]["products"]:
            raise GameError(f"{product} is not sold in this shop.")
        if isinstance(price, bool) or not isinstance(price, int):
            raise GameError("Prices must be whole cents.")
        if price <= 0 or price > CONFIG["max_price"] or price % CONFIG["price_step"]:
            raise GameError(f"Prices must be between €0.10 and {euro(CONFIG['max_price'])} in steps of €0.10.")
    state["shops"][shop]["prices"].update(prices)
    return {"toast": "Prices saved"}


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
    if not all(state["cleaning"].values()):
        _change_reputation(state, CONFIG["reputation"]["cleaning_missed"])
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
            else:
                kept.append(batch)
        state["shops"][shop]["stock"] = kept

    stats = state["stats"]
    revenue = sum(stats["shops"][s]["revenue"] for s in owned_shops(state))
    profit = revenue - stats["purchase_cost"] - stats["spending"]
    total_market = revenue + stats["rival_revenue"]
    sold: dict[str, int] = {}
    for s in owned_shops(state):
        for p, n in stats["shops"][s]["sold"].items():
            sold[p] = sold.get(p, 0) + n
    summary = {
        "day": state["day"],
        "revenue": revenue,
        "purchase_cost": stats["purchase_cost"],
        "spending": stats["spending"],
        "spoiled_value": spoiled_value,
        "spoiled": spoiled,
        "profit": profit,
        "sold": sold,
        "plan": dict(state["plan"]),
        "served": sum(stats["shops"][s]["served"] for s in owned_shops(state)),
        "lost": sum(stats["shops"][s]["lost"] for s in owned_shops(state)),
        "wrong": sum(stats["shops"][s]["wrong"] for s in owned_shops(state)),
        "reputation": round(state["reputation"]),
        "market_share": round(revenue / total_market, 4) if total_market else 0.0,
        "money": state["money"],
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


def _ev_tick(state, ev):
    """The browser reports that the clock passed an important time."""
    result = {}
    t = state["time"]
    if not state["open"] and not state["closed"] and t >= T["open"]:
        result.update(_open(state))
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
    spot = ev.get("spot")
    if spot not in CONFIG["cleaning_spots"]:
        raise GameError("Unknown cleaning spot.")
    if not state["closed"] or state["day_state"] != CLOSING:
        raise GameError("You can only clean up after closing time.")
    state["cleaning"][spot] = True
    result = {"toast": "Done"}
    if all(state["cleaning"].values()):
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
    if upgrade not in CONFIG["upgrades"]:
        raise GameError("Unknown upgrade.")
    if upgrade in state["shops"][shop]["upgrades"]:
        raise GameError("You already have this upgrade.")
    cost = CONFIG["upgrades"][upgrade]["cost"]
    _pay(state, cost)
    state["shops"][shop]["upgrades"].append(upgrade)
    state["stats"]["spending"] += cost
    return {"toast": f"{CONFIG['upgrades'][upgrade]['name']} bought"}


def _ev_hire_manager(state, ev):
    shop = ev.get("shop", "cafe")
    _require_owned(state, shop)
    if state["shops"][shop]["manager"]:
        raise GameError("A manager already works here.")
    _pay(state, CONFIG["manager_cost"])
    state["shops"][shop]["manager"] = True
    state["stats"]["spending"] += CONFIG["manager_cost"]
    _check_victory(state)
    return {"toast": "Manager hired"}


def _ev_buy_competitor(state, ev):
    rival = state["shops"]["rival"]
    if rival["owner"] == "player":
        raise GameError("You already own this café.")
    if not state["shops"]["cafe"]["manager"]:
        raise GameError("Hire a manager in your café first.")
    _pay(state, CONFIG["acquisition_cost"])
    rival["owner"] = "player"
    rival["stock"] = []
    rival["staff"] = True  # the barista stays and keeps selling automatically
    state["stats"]["spending"] += CONFIG["acquisition_cost"]
    state["plan"].update({p: 0 for p in SHOPS["rival"]["products"] if p not in state["plan"]})
    state["restock"] = _restock_rival(state)
    _check_victory(state)
    return {"toast": f"{SHOPS['rival']['name']} is yours now! Its barista restocked for {euro(state['restock']['cost'])}.",
            "restock": state["restock"]}


# Students and sales -----------------------------------------------------------


def _decide(state, sid: str, exclude: set[str] = frozenset(), sold_out: set[str] = frozenset()) -> dict:
    """Re-decide where to buy (or not) with the utility model."""
    student = state["students"][sid]
    shops = [s for s in SHOPS if s not in exclude]
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
    if state["closed"]:
        return _decide(state, student["id"])
    st.transition(student, "join_queue")
    return {}


def _ev_queue_full(state, ev):
    student = _student(state, ev["student"])
    return _decide(state, student["id"], exclude={ev.get("shop")})


def _ev_at_counter(state, ev):
    """A student reaches the counter: which of the wanted items can the shop make?"""
    student = _student(state, ev["student"])
    shop = ev.get("shop")
    if student["status"] != st.QUEUING or not student["intent"] or student["intent"]["shop"] != shop:
        raise GameError("This student is not at this counter.")
    if not state["open"]:
        raise GameError("The shop is not open.")
    sold_out = [p for p in student["intent"]["items"] if not can_make(state, shop, p)]
    if not sold_out:
        return {"items": student["intent"]["items"], "sold_out": []}
    # Re-decide without the sold-out products: something else here, the other café, or nothing.
    st.transition(student, "give_up")
    decision = _decide(state, student["id"], sold_out={st.offering_key(shop, p) for p in sold_out})
    if decision["action"] == "shop" and decision["shop"] == shop:
        st.transition(student, "join_queue")  # stays at the counter with the new order
        return {"items": decision["items"], "sold_out": sold_out}
    return {"items": [], "sold_out": sold_out, "leaves": True, "decision": decision}


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
    items = [p for p in student["intent"]["items"] if can_make(state, shop, p)]
    if not items:
        raise GameError("Nothing from this order is in stock.")
    student["intent"]["items"] = items
    st.transition(student, "accepted")
    state["current_order"] = {"shop": shop, "student": student["id"], "items": items,
                              "accepted_at": state["time"]}
    state["tray"] = []
    return {"order": state["current_order"]}


def _ev_reject(state, ev):
    shop = ev.get("shop", "cafe")
    student = _student(state, ev["student"])
    if student["status"] != st.QUEUING:
        raise GameError("This student is not waiting at the counter.")
    return _decide(state, student["id"], exclude={shop})


def _ev_prepare(state, ev):
    shop, product = ev.get("shop", "cafe"), ev.get("product")
    _require_manual(state, shop, ev)
    if not state["current_order"] or state["current_order"]["shop"] != shop:
        raise GameError("Accept an order first.")
    if product not in SHOPS[shop]["products"]:
        raise GameError("This is not sold in this shop.")
    if not can_make(state, shop, product):
        raise GameError(f"{PRODUCTS[product]['name']} is sold out.")
    _consume(state, shop, product)
    state["tray"].append(product)
    return {"toast": f"{PRODUCTS[product]['name']} fertig", "tray": list(state["tray"])}


def _sell(state, shop: str, student: dict, products: list[str]) -> int:
    """Book a sale: money (for player shops), statistics, student's budget."""
    prices = state["shops"][shop]["prices"]
    amount = sum(prices[p] for p in products)
    stats = state["stats"]["shops"][shop]
    if state["shops"][shop]["owner"] == "player":
        state["money"] += amount
        stats["revenue"] += amount
    else:
        state["stats"]["rival_revenue"] += amount
    for p in products:
        stats["sold"][p] = stats["sold"].get(p, 0) + 1
    stats["served"] += 1
    student["budget"] -= amount
    student["purchases"].append({"shop": shop, "items": list(products), "time": state["time"]})
    return amount


def _change_reputation(state, delta: float) -> None:
    state["reputation"] = max(0, min(100, state["reputation"] + delta))


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
    amount = _sell(state, shop, student, delivered) if delivered else 0
    rep = CONFIG["reputation"]
    if correct:
        fast = (state["time"] - order["accepted_at"]) * 60 <= T["fast_service_minutes"]
        _change_reputation(state, rep["correct_order"] + (rep["fast_bonus"] if fast else 0))
        toast = f"Happy customer: +{euro(amount)}"
    else:
        state["stats"]["shops"][shop]["wrong"] += 1
        _change_reputation(state, rep["wrong_order"])
        toast = f"Wrong order - unhappy customer (+{euro(amount)})"
    st.transition(student, "served")
    student["intent"] = None
    state["current_order"] = None
    state["tray"] = []
    return {"toast": toast, "amount": amount, "correct": correct}


def _ev_patience_expired(state, ev):
    student = _student(state, ev["student"])
    shop = ev.get("shop")
    if student["status"] not in (st.QUEUING, st.BEING_SERVED):
        return {"action": "ignored"}
    if state["shops"][shop]["owner"] == "player":
        state["stats"]["shops"][shop]["lost"] += 1
        _change_reputation(state, CONFIG["reputation"]["customer_lost"])
    if state["current_order"] and state["current_order"]["student"] == student["id"]:
        state["current_order"] = None
        state["tray"] = []
    result = _decide(state, student["id"], exclude={shop})
    result["toast"] = "A customer left"
    return result


def _ev_auto_serve(state, ev):
    """Bot or manager serves the student at the front of the queue."""
    shop = ev.get("shop")
    if not is_auto(state, shop):
        raise GameError("Someone has to serve here in person.")
    if not state["open"]:
        raise GameError("The shop is not open.")
    student = _student(state, ev["student"])
    if student["status"] != st.QUEUING or not student["intent"] or student["intent"]["shop"] != shop:
        raise GameError("This student is not waiting here.")
    items = []
    for p in student["intent"]["items"]:
        if can_make(state, shop, p):
            if state["shops"][shop]["owner"] == "player":
                _consume(state, shop, p)
            items.append(p)
    amount = _sell(state, shop, student, items) if items else 0
    if not items and state["shops"][shop]["owner"] == "player":
        state["stats"]["shops"][shop]["lost"] += 1
    st.transition(student, "served")
    student["intent"] = None
    return {"items": items, "amount": amount}


def _ev_resume(state, ev):
    """Continuing a saved game: students in a queue or on their way start fresh on campus."""
    for s in state["students"].values():
        if s["status"] in (st.WALKING_TO_SHOP, st.QUEUING, st.BEING_SERVED):
            s["status"] = st.WANDERING
            s["intent"] = None
    state["current_order"] = None
    state["tray"] = []
    return {}


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
}



def apply(state: dict, event: dict) -> tuple[dict, dict]:
    """Apply one event. Returns (new_state, result). Raises GameError if not allowed."""
    kind = event.get("type")
    if kind not in HANDLERS:
        raise GameError(f"Unknown event: {kind}.")
    if state["status"] != RUNNING:
        raise GameError("The game is over.")
    new = copy.deepcopy(state)
    if "t" in event:
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
    if ds == SHOP_OPEN and all(state["shops"][s]["manager"] for s in owned_shops(state)):
        return "Your manager is serving. Plan your next move!"
    if ds == CLOSING:
        done = sum(state["cleaning"].values())
        return f"Clean up the café ({done}/{len(state['cleaning'])})."
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
            "manager": d["manager"], "staff": d.get("staff", False), "auto": is_auto(state, s),
            "factor": shop_factor(state, s),
            "stock": stock,
            "can_make": {p: can_make(state, s, p) for p in SHOPS[s]["products"]},
        }
    return {
        "day": state["day"],
        "time": state["time"],
        "status": state["status"],
        "day_state": state["day_state"],
        "objective": objective(state),
        "money": state["money"],
        "reputation": round(state["reputation"]),
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
        "can_buy_competitor": state["shops"]["rival"]["owner"] == "bot" and state["shops"]["cafe"]["manager"],
        "students": {
            sid: {"name": s["name"], "status": s["status"], "intent": s["intent"],
                  "traits": s["traits"], "look": s["look"]}
            for sid, s in state["students"].items()
        },
    }


def day_plan(state: dict) -> dict:
    """Per-day data for the browser: who is on campus when, and when they think about buying."""
    return {"day": state["day"], "seed": state["seed"], "schedule": state["schedule"]}
