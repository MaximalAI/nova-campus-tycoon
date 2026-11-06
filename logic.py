"""Game rules for Nova Campus Tycoon.

Pure functions only: no Streamlit and no database code in this module.
All balancing values live in CONFIG. Money is handled as integer cents.

Every action function takes a Game, checks all rules first and returns a NEW
Game. The input is never modified, so a rejected action (GameError) leaves the
state exactly as it was.

See docs/product-brief.md for the rules.
"""

from __future__ import annotations

import copy
import itertools
import random
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Balancing values (all money in cents, all times in seconds)
# ---------------------------------------------------------------------------

CONFIG = {
    "start_balance": 10_000,
    "student_count": 10,
    "student_budget": 1_000,
    "utility_min": 50,
    "utility_max": 400,
    "day_time_budget": 720,
    "max_price": 1_000,
    "employee_cost": 20_000,
    "acquisition_cost": 50_000,
    "ingredients": {
        "coffee_beans": {"name": "Coffee beans", "cost": 40},
        "oranges": {"name": "Oranges", "cost": 60},
        "frozen_pastel": {"name": "Frozen Pastel de Nata", "cost": 50},
        "tea_leaves": {"name": "Tea leaves", "cost": 30},
        "frozen_croissants": {"name": "Frozen croissants", "cost": 70},
    },
    "products": {
        "coffee": {"name": "Coffee", "ingredient": "coffee_beans", "prep_time": 15},
        "orange_juice": {"name": "Orange Juice", "ingredient": "oranges", "prep_time": 25},
        "pastel_de_nata": {"name": "Pastel de Nata", "ingredient": "frozen_pastel", "prep_time": 20},
        "tea": {"name": "Tea", "ingredient": "tea_leaves", "prep_time": 10},
        "croissant": {"name": "Croissant", "ingredient": "frozen_croissants", "prep_time": 20},
    },
    "shops": {
        "player_cafe": {
            "name": "Player café",
            "products": ["coffee", "orange_juice", "pastel_de_nata"],
            "base_factor": 1.0,
            "start_owner": "player",
            "start_prices": {"coffee": 200, "orange_juice": 250, "pastel_de_nata": 180},
        },
        "competitor": {
            "name": "Competitor café",
            "products": ["coffee", "tea", "croissant"],
            "base_factor": 1.2,
            "start_owner": "bot",
            "start_prices": {"coffee": 200, "tea": 180, "croissant": 220},
        },
    },
    "upgrades": {
        "coffee_machine": {"name": "Better coffee machine", "factor_bonus": 0.15, "cost": 6_000},
        "seating": {"name": "Seating & decoration", "factor_bonus": 0.20, "cost": 12_000},
        "branding": {"name": "Branding & signage", "factor_bonus": 0.25, "cost": 20_000},
    },
}

SHOP_IDS = list(CONFIG["shops"])  # ["player_cafe", "competitor"]

# Game phases and statuses
MORNING, SELLING, SUMMARY, FINISHED = "morning", "selling", "summary", "finished"
RUNNING, GAME_OVER, VICTORY = "running", "game_over", "victory"


class GameError(Exception):
    """Raised when the player tries an action the rules do not allow."""


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class Order:
    """What one student wants to buy at one shop."""

    student: int
    items: list[str]


@dataclass
class Shop:
    shop_id: str
    owner: str  # "player" or "bot"
    prices: dict[str, int]
    upgrades: list[str] = field(default_factory=list)
    has_employee: bool = False
    inventory: dict[str, int] = field(default_factory=dict)


@dataclass
class ShopDayStats:
    """Numbers for one shop on the current day."""

    time_left: int = 0
    sold: dict[str, int] = field(default_factory=dict)
    revenue: int = 0
    ingredient_cost: int = 0
    spending: int = 0  # upgrades, hiring, acquisition
    spoiled_value: int = 0
    served: int = 0
    lost: int = 0


@dataclass
class Game:
    day: int
    balance_cents: int
    phase: str
    status: str
    seed: int
    shops: dict[str, Shop]
    manual_shop: str | None = "player_cafe"
    queues: dict[str, list[Order]] = field(default_factory=dict)
    stats: dict[str, ShopDayStats] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    total_profit: int = 0
    game_id: int | None = None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def format_money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}€{cents // 100}.{cents % 100:02d}"


def shop_ingredients(shop_id: str) -> list[str]:
    """Ingredients needed for the products of a shop."""
    products = CONFIG["shops"][shop_id]["products"]
    return [CONFIG["products"][p]["ingredient"] for p in products]


def shop_factor(shop: Shop) -> float:
    base = CONFIG["shops"][shop.shop_id]["base_factor"]
    bonus = sum(CONFIG["upgrades"][u]["factor_bonus"] for u in shop.upgrades)
    return round(base + bonus, 4)


def player_shops(game: Game) -> list[str]:
    return [s for s in SHOP_IDS if game.shops[s].owner == "player"]


def _empty_stats() -> dict[str, ShopDayStats]:
    return {s: ShopDayStats() for s in SHOP_IDS}


def _require_running(game: Game) -> None:
    if game.status != RUNNING or game.phase == FINISHED:
        raise GameError("The game is over. Start a new game.")


def _require_phase(game: Game, phase: str) -> None:
    _require_running(game)
    if game.phase != phase:
        raise GameError(f"This action is only possible in the {phase} phase.")


def _require_player_shop(game: Game, shop_id: str) -> Shop:
    if shop_id not in game.shops:
        raise GameError(f"Unknown shop: {shop_id}.")
    shop = game.shops[shop_id]
    if shop.owner != "player":
        raise GameError("You do not own this shop.")
    return shop


def _pay(game: Game, amount: int) -> None:
    if amount > game.balance_cents:
        raise GameError(
            f"Not enough money: this costs {format_money(amount)}, "
            f"your balance is {format_money(game.balance_cents)}."
        )
    game.balance_cents -= amount


def _check_victory(game: Game) -> None:
    owned = all(s.owner == "player" for s in game.shops.values())
    staffed = all(s.has_employee for s in game.shops.values())
    if owned and staffed:
        game.status = VICTORY
        game.phase = FINISHED


# ---------------------------------------------------------------------------
# New game
# ---------------------------------------------------------------------------


def new_game(seed: int | None = None) -> Game:
    if seed is None:
        seed = random.randrange(1, 1_000_000_000)
    shops = {}
    for shop_id, spec in CONFIG["shops"].items():
        shops[shop_id] = Shop(
            shop_id=shop_id,
            owner=spec["start_owner"],
            prices=dict(spec["start_prices"]),
            inventory={i: 0 for i in shop_ingredients(shop_id)},
        )
    return Game(
        day=1,
        balance_cents=CONFIG["start_balance"],
        phase=MORNING,
        status=RUNNING,
        seed=seed,
        shops=shops,
        manual_shop="player_cafe",
        queues={s: [] for s in SHOP_IDS},
        stats=_empty_stats(),
    )


# ---------------------------------------------------------------------------
# Morning actions
# ---------------------------------------------------------------------------


def purchase_cost(quantities: dict[str, int]) -> int:
    ingredients = CONFIG["ingredients"]
    return sum(ingredients[i]["cost"] * q for i, q in quantities.items())


def buy_ingredients(game: Game, quantities: dict[str, int], shop_id: str = "player_cafe") -> Game:
    """Buy ingredients at the wholesaler for one of the player's shops."""
    _require_phase(game, MORNING)
    _require_player_shop(game, shop_id)
    allowed = shop_ingredients(shop_id)
    for ingredient, qty in quantities.items():
        if ingredient not in allowed:
            raise GameError(f"{ingredient} is not used by this shop.")
        if isinstance(qty, bool) or not isinstance(qty, int):
            raise GameError("Quantities must be whole numbers.")
        if qty < 0:
            raise GameError("Quantities cannot be negative.")
    if not any(q > 0 for q in quantities.values()):
        raise GameError("Choose at least one ingredient to buy.")

    cost = purchase_cost(quantities)
    new = copy.deepcopy(game)
    _pay(new, cost)
    shop = new.shops[shop_id]
    for ingredient, qty in quantities.items():
        shop.inventory[ingredient] = shop.inventory.get(ingredient, 0) + qty
    new.stats[shop_id].ingredient_cost += cost
    return new


def set_prices(game: Game, shop_id: str, prices: dict[str, int]) -> Game:
    _require_phase(game, MORNING)
    shop = _require_player_shop(game, shop_id)
    for product, price in prices.items():
        if product not in shop.prices:
            raise GameError(f"{product} is not sold in this shop.")
        if isinstance(price, bool) or not isinstance(price, int):
            raise GameError("Prices must be whole cents.")
        if price <= 0:
            raise GameError("Prices must be above €0.00.")
        if price > CONFIG["max_price"]:
            raise GameError(f"Prices cannot be above {format_money(CONFIG['max_price'])}.")
    new = copy.deepcopy(game)
    new.shops[shop_id].prices.update(prices)
    return new


def buy_upgrade(game: Game, shop_id: str, upgrade: str) -> Game:
    _require_phase(game, MORNING)
    shop = _require_player_shop(game, shop_id)
    if upgrade not in CONFIG["upgrades"]:
        raise GameError(f"Unknown upgrade: {upgrade}.")
    if upgrade in shop.upgrades:
        raise GameError("This upgrade has already been bought for this shop.")
    cost = CONFIG["upgrades"][upgrade]["cost"]
    new = copy.deepcopy(game)
    _pay(new, cost)
    new.shops[shop_id].upgrades.append(upgrade)
    new.stats[shop_id].spending += cost
    return new


def hire_employee(game: Game, shop_id: str) -> Game:
    _require_phase(game, MORNING)
    shop = _require_player_shop(game, shop_id)
    if shop.has_employee:
        raise GameError("This shop already has an employee.")
    cost = CONFIG["employee_cost"]
    new = copy.deepcopy(game)
    _pay(new, cost)
    new.shops[shop_id].has_employee = True
    new.stats[shop_id].spending += cost
    if new.manual_shop == shop_id:
        others = [s for s in player_shops(new) if not new.shops[s].has_employee]
        new.manual_shop = others[0] if others else None
    _check_victory(new)
    return new


def buy_competitor(game: Game) -> Game:
    _require_phase(game, MORNING)
    competitor = game.shops["competitor"]
    if competitor.owner == "player":
        raise GameError("You already own the competitor.")
    if not game.shops["player_cafe"].has_employee:
        raise GameError("Hire an employee in your café before buying the competitor.")
    cost = CONFIG["acquisition_cost"]
    new = copy.deepcopy(game)
    _pay(new, cost)
    new.shops["competitor"].owner = "player"
    new.shops["competitor"].inventory = {i: 0 for i in shop_ingredients("competitor")}
    new.stats["competitor"].spending += cost
    if new.manual_shop is None:
        new.manual_shop = "competitor"
    _check_victory(new)
    return new


def set_manual_shop(game: Game, shop_id: str) -> Game:
    """Choose which of the player's shops the player serves in person today."""
    _require_phase(game, MORNING)
    _require_player_shop(game, shop_id)
    new = copy.deepcopy(game)
    new.manual_shop = shop_id
    return new


# ---------------------------------------------------------------------------
# Demand model
# ---------------------------------------------------------------------------


def offerings(game: Game) -> list[tuple[str, str]]:
    """All (shop, product) pairs students can buy: 6 in this release."""
    return [(s, p) for s in SHOP_IDS for p in CONFIG["shops"][s]["products"]]


def draw_utilities(seed: int, day: int) -> list[dict[tuple[str, str], float]]:
    """Base utility u_ij (in cents) per student and offering, new every day."""
    rng = random.Random(f"{seed}-{day}-utilities")
    result = []
    pairs = [(s, p) for s in SHOP_IDS for p in CONFIG["shops"][s]["products"]]
    for _ in range(CONFIG["student_count"]):
        result.append(
            {pair: rng.uniform(CONFIG["utility_min"], CONFIG["utility_max"]) for pair in pairs}
        )
    return result


def best_bundle(
    utilities: dict[tuple[str, str], float],
    prices: dict[tuple[str, str], int],
    factors: dict[str, float],
    budget: int,
) -> list[tuple[str, str]]:
    """Brute-force the bundle that maximizes
    U = sum(F_s * u_ij) + (budget - sum(p_j)), with sum(p_j) <= budget
    and at most one coffee in total."""
    pairs = list(utilities)
    best: list[tuple[str, str]] = []
    best_value = float(budget)  # buying nothing keeps the whole budget
    for size in range(1, len(pairs) + 1):
        for bundle in itertools.combinations(pairs, size):
            if sum(1 for _, product in bundle if product == "coffee") > 1:
                continue
            spent = sum(prices[pair] for pair in bundle)
            if spent > budget:
                continue
            value = sum(factors[s] * utilities[(s, p)] for s, p in bundle) + (budget - spent)
            if value > best_value + 1e-9:
                best_value = value
                best = list(bundle)
    return best


def generate_demand(game: Game) -> dict[str, list[Order]]:
    """Today's queue per shop, in random arrival order."""
    utilities = draw_utilities(game.seed, game.day)
    prices = {(s, p): game.shops[s].prices[p] for s, p in offerings(game)}
    factors = {s: shop_factor(game.shops[s]) for s in SHOP_IDS}
    queues: dict[str, list[Order]] = {s: [] for s in SHOP_IDS}
    rng = random.Random(f"{game.seed}-{game.day}-arrivals")
    students = list(range(CONFIG["student_count"]))
    rng.shuffle(students)
    for student in students:
        bundle = best_bundle(utilities[student], prices, factors, CONFIG["student_budget"])
        for shop_id in SHOP_IDS:
            items = [p for s, p in bundle if s == shop_id]
            if items:
                queues[shop_id].append(Order(student=student, items=items))
    return queues


# ---------------------------------------------------------------------------
# Selling phase
# ---------------------------------------------------------------------------


def order_prep_time(shop: Shop, order: Order) -> int:
    """Preparation time for the items of an order that are in stock."""
    stock = dict(shop.inventory)
    total = 0
    for item in order.items:
        ingredient = CONFIG["products"][item]["ingredient"]
        if stock.get(ingredient, 0) > 0:
            stock[ingredient] -= 1
            total += CONFIG["products"][item]["prep_time"]
    return total


def _serve(game: Game, shop_id: str) -> None:
    """Serve the first order in the queue (game is already a copy)."""
    shop = game.shops[shop_id]
    stats = game.stats[shop_id]
    order = game.queues[shop_id].pop(0)
    delivered = 0
    for item in order.items:
        ingredient = CONFIG["products"][item]["ingredient"]
        if shop.owner == "bot" or shop.inventory.get(ingredient, 0) > 0:
            if shop.owner == "player":
                shop.inventory[ingredient] -= 1
                stats.time_left -= CONFIG["products"][item]["prep_time"]
            price = shop.prices[item]
            stats.revenue += price
            stats.sold[item] = stats.sold.get(item, 0) + 1
            if shop.owner == "player":
                game.balance_cents += price
            delivered += 1
    if delivered:
        stats.served += 1
    else:
        stats.lost += 1


def _employee_serves(game: Game, shop_id: str) -> None:
    """An employee works through the queue; orders that do not fit are lost."""
    shop = game.shops[shop_id]
    while game.queues[shop_id]:
        order = game.queues[shop_id][0]
        if order_prep_time(shop, order) <= game.stats[shop_id].time_left:
            _serve(game, shop_id)
        else:
            game.queues[shop_id].pop(0)
            game.stats[shop_id].lost += 1


def open_shop(game: Game) -> Game:
    """Start the selling phase: generate demand, let bot and employees work."""
    _require_phase(game, MORNING)
    new = copy.deepcopy(game)
    new.queues = generate_demand(new)
    for shop_id in SHOP_IDS:
        new.stats[shop_id].time_left = CONFIG["day_time_budget"]
    for shop_id in SHOP_IDS:
        shop = new.shops[shop_id]
        if shop.owner == "bot":
            while new.queues[shop_id]:
                _serve(new, shop_id)
        elif shop.has_employee:
            _employee_serves(new, shop_id)
        elif shop_id != new.manual_shop:
            # Nobody works in this shop today: all customers leave.
            new.stats[shop_id].lost += len(new.queues[shop_id])
            new.queues[shop_id] = []
    new.phase = SELLING
    return new


def accept_next_order(game: Game, shop_id: str | None = None) -> Game:
    """The player prepares the next order in the shop they serve today."""
    _require_phase(game, SELLING)
    shop_id = shop_id or game.manual_shop
    if shop_id is None or shop_id != game.manual_shop:
        raise GameError("You are not serving this shop today.")
    if not game.queues.get(shop_id):
        raise GameError("There are no orders waiting.")
    shop = game.shops[shop_id]
    needed = order_prep_time(shop, game.queues[shop_id][0])
    if needed > game.stats[shop_id].time_left:
        raise GameError(
            f"Not enough time left: this order needs {needed} s, "
            f"only {game.stats[shop_id].time_left} s remain."
        )
    new = copy.deepcopy(game)
    _serve(new, shop_id)
    return new


def end_day(game: Game) -> Game:
    """Close the shops: lost customers, spoilage, statistics, game-over check."""
    _require_phase(game, SELLING)
    new = copy.deepcopy(game)
    for shop_id in SHOP_IDS:
        new.stats[shop_id].lost += len(new.queues[shop_id])
        new.queues[shop_id] = []
        shop = new.shops[shop_id]
        if shop.owner == "player":
            spoiled = sum(
                CONFIG["ingredients"][i]["cost"] * q for i, q in shop.inventory.items()
            )
            new.stats[shop_id].spoiled_value = spoiled
            shop.inventory = {i: 0 for i in shop.inventory}

    summary = day_summary(new)
    new.history.append(summary)
    new.total_profit += summary["profit"]
    new.phase = SUMMARY
    if new.balance_cents <= 0:
        new.status = GAME_OVER
        new.phase = FINISHED
    return new


def next_day(game: Game) -> Game:
    _require_phase(game, SUMMARY)
    new = copy.deepcopy(game)
    new.day += 1
    new.phase = MORNING
    new.queues = {s: [] for s in SHOP_IDS}
    new.stats = _empty_stats()
    if new.manual_shop is None or new.shops[new.manual_shop].has_employee:
        unstaffed = [s for s in player_shops(new) if not new.shops[s].has_employee]
        new.manual_shop = unstaffed[0] if unstaffed else None
    return new


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def day_summary(game: Game) -> dict:
    """Statistics of the current day, per shop and in total."""
    total_revenue_all = sum(game.stats[s].revenue for s in SHOP_IDS)
    shops = {}
    profit = 0
    player_revenue = 0
    for shop_id in SHOP_IDS:
        st = game.stats[shop_id]
        owned = game.shops[shop_id].owner == "player"
        shop_profit = st.revenue - st.ingredient_cost - st.spending if owned else 0
        if owned:
            profit += shop_profit
            player_revenue += st.revenue
        shops[shop_id] = {
            "owner": game.shops[shop_id].owner,
            "sold": dict(st.sold),
            "revenue": st.revenue,
            "ingredient_cost": st.ingredient_cost,
            "spoiled_value": st.spoiled_value,
            "spending": st.spending,
            "profit": shop_profit,
            "served": st.served,
            "lost": st.lost,
        }
    share = player_revenue / total_revenue_all if total_revenue_all else 0.0
    return {
        "day": game.day,
        "shops": shops,
        "profit": profit,
        "market_share": round(share, 4),
        "balance": game.balance_cents,
    }
