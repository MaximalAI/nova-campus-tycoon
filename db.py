"""SQLite storage for Nova Campus Tycoon.

Creates the schema, loads and saves the game state. No game rules here.
The database file lives in data/ (ignored by git). Tests use a temporary
database instead.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path

from logic import Game, Order, Shop, ShopDayStats

DEFAULT_DB_PATH = Path(os.environ.get("NCT_DB_PATH", "data/game.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day INTEGER NOT NULL,
    balance_cents INTEGER NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    seed INTEGER NOT NULL,
    manual_shop TEXT,
    total_profit INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS shops (
    game_id INTEGER NOT NULL REFERENCES games(id),
    shop TEXT NOT NULL,
    owner TEXT NOT NULL,
    has_employee INTEGER NOT NULL,
    PRIMARY KEY (game_id, shop)
);
CREATE TABLE IF NOT EXISTS prices (
    game_id INTEGER NOT NULL REFERENCES games(id),
    shop TEXT NOT NULL,
    product TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    PRIMARY KEY (game_id, shop, product)
);
CREATE TABLE IF NOT EXISTS inventory (
    game_id INTEGER NOT NULL REFERENCES games(id),
    shop TEXT NOT NULL,
    ingredient TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    PRIMARY KEY (game_id, shop, ingredient)
);
CREATE TABLE IF NOT EXISTS upgrades (
    game_id INTEGER NOT NULL REFERENCES games(id),
    shop TEXT NOT NULL,
    upgrade TEXT NOT NULL,
    PRIMARY KEY (game_id, shop, upgrade)
);
CREATE TABLE IF NOT EXISTS queue (
    game_id INTEGER NOT NULL REFERENCES games(id),
    shop TEXT NOT NULL,
    position INTEGER NOT NULL,
    student INTEGER NOT NULL,
    items TEXT NOT NULL,
    PRIMARY KEY (game_id, shop, position)
);
CREATE TABLE IF NOT EXISTS day_stats (
    game_id INTEGER NOT NULL REFERENCES games(id),
    shop TEXT NOT NULL,
    stats_json TEXT NOT NULL,
    PRIMARY KEY (game_id, shop)
);
CREATE TABLE IF NOT EXISTS history (
    game_id INTEGER NOT NULL REFERENCES games(id),
    day INTEGER NOT NULL,
    summary_json TEXT NOT NULL,
    PRIMARY KEY (game_id, day)
);
"""

CHILD_TABLES = ["shops", "prices", "inventory", "upgrades", "queue", "day_stats", "history"]


def connect(path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the database and create the tables if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def save_game(conn: sqlite3.Connection, game: Game) -> int:
    """Write the full game state in one transaction. Returns the game id."""
    with conn:
        if game.game_id is None:
            cur = conn.execute(
                "INSERT INTO games (day, balance_cents, phase, status, seed, manual_shop, total_profit)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (game.day, game.balance_cents, game.phase, game.status, game.seed,
                 game.manual_shop, game.total_profit),
            )
            game.game_id = cur.lastrowid
        else:
            conn.execute(
                "UPDATE games SET day=?, balance_cents=?, phase=?, status=?, seed=?,"
                " manual_shop=?, total_profit=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (game.day, game.balance_cents, game.phase, game.status, game.seed,
                 game.manual_shop, game.total_profit, game.game_id),
            )
        gid = game.game_id
        for table in CHILD_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE game_id=?", (gid,))
        for shop_id, shop in game.shops.items():
            conn.execute(
                "INSERT INTO shops VALUES (?, ?, ?, ?)",
                (gid, shop_id, shop.owner, int(shop.has_employee)),
            )
            conn.executemany(
                "INSERT INTO prices VALUES (?, ?, ?, ?)",
                [(gid, shop_id, p, c) for p, c in shop.prices.items()],
            )
            conn.executemany(
                "INSERT INTO inventory VALUES (?, ?, ?, ?)",
                [(gid, shop_id, i, q) for i, q in shop.inventory.items()],
            )
            conn.executemany(
                "INSERT INTO upgrades VALUES (?, ?, ?)",
                [(gid, shop_id, u) for u in shop.upgrades],
            )
        for shop_id, orders in game.queues.items():
            conn.executemany(
                "INSERT INTO queue VALUES (?, ?, ?, ?, ?)",
                [(gid, shop_id, pos, o.student, ",".join(o.items)) for pos, o in enumerate(orders)],
            )
        for shop_id, stats in game.stats.items():
            conn.execute(
                "INSERT INTO day_stats VALUES (?, ?, ?)",
                (gid, shop_id, json.dumps(asdict(stats))),
            )
        conn.executemany(
            "INSERT INTO history VALUES (?, ?, ?)",
            [(gid, h["day"], json.dumps(h)) for h in game.history],
        )
    return gid


def load_game(conn: sqlite3.Connection, game_id: int) -> Game | None:
    row = conn.execute(
        "SELECT day, balance_cents, phase, status, seed, manual_shop, total_profit"
        " FROM games WHERE id=?",
        (game_id,),
    ).fetchone()
    if row is None:
        return None
    day, balance, phase, status, seed, manual_shop, total_profit = row

    shops: dict[str, Shop] = {}
    for shop_id, owner, has_employee in conn.execute(
        "SELECT shop, owner, has_employee FROM shops WHERE game_id=? ORDER BY rowid", (game_id,)
    ):
        shops[shop_id] = Shop(shop_id=shop_id, owner=owner, prices={},
                              has_employee=bool(has_employee))
    for shop_id, product, price in conn.execute(
        "SELECT shop, product, price_cents FROM prices WHERE game_id=? ORDER BY rowid", (game_id,)
    ):
        shops[shop_id].prices[product] = price
    for shop_id, ingredient, qty in conn.execute(
        "SELECT shop, ingredient, quantity FROM inventory WHERE game_id=? ORDER BY rowid", (game_id,)
    ):
        shops[shop_id].inventory[ingredient] = qty
    for shop_id, upgrade in conn.execute(
        "SELECT shop, upgrade FROM upgrades WHERE game_id=? ORDER BY rowid", (game_id,)
    ):
        shops[shop_id].upgrades.append(upgrade)

    queues: dict[str, list[Order]] = {s: [] for s in shops}
    for shop_id, student, items in conn.execute(
        "SELECT shop, student, items FROM queue WHERE game_id=? ORDER BY shop, position", (game_id,)
    ):
        queues[shop_id].append(Order(student=student, items=items.split(",")))

    stats = {s: ShopDayStats() for s in shops}
    for shop_id, stats_json in conn.execute(
        "SELECT shop, stats_json FROM day_stats WHERE game_id=?", (game_id,)
    ):
        stats[shop_id] = ShopDayStats(**json.loads(stats_json))

    history = [
        json.loads(s)
        for (s,) in conn.execute(
            "SELECT summary_json FROM history WHERE game_id=? ORDER BY day", (game_id,)
        )
    ]
    return Game(
        day=day, balance_cents=balance, phase=phase, status=status, seed=seed,
        shops=shops, manual_shop=manual_shop, queues=queues, stats=stats,
        history=history, total_profit=total_profit, game_id=game_id,
    )


def latest_game_id(conn: sqlite3.Connection) -> int | None:
    """Id of the most recently saved game, or None if there is none."""
    row = conn.execute("SELECT id FROM games ORDER BY updated_at DESC, id DESC LIMIT 1").fetchone()
    return row[0] if row else None
