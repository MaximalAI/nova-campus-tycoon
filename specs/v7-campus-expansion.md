# Spec: v7 campus expansion

Product rules: `docs/product-brief-v2.md`, section 14. This spec says how we build it.

## Why
With one competitor the game is over after about two weeks. v7 turns it into a monopoly race over nine shops in two zones. Each new shop adds one new mechanic, so the game stays interesting while the player climbs from one café to the whole campus and the beach.

## What

### 1. Data model and config (commit 1)
- `config.py`:
  - `zones`: `campus` (open from the start), `beach` (unlocks when every campus shop is owned).
  - `shops`: seven new shops next to `cafe` and `rival` (ids `snackbots`, `mercado`, `bowl_bar`, `mensa`, `surf_shack`, `praia_bar`, `gelado`). Each shop has `order`, `zone`, `products`, `start_prices` (bot prices), `base_factor`, `acquisition_cost`, `manager_cost`, `max_queue`, `open_hours` (optional), and `mechanic: {"type": ..., params}`.
  - `wholesale_items`: 23 new items. `needs_rival` becomes `shops: [...]` (the item is sold once you own one of these shops).
  - `products`: 21 new products with `uses`, `station`, `prep_minutes`.
  - `students`: campus pool 40, beach pool with its own size, budget and utility range, phase tables per zone.
- `logic.py`:
  - Ids `cafe` and `rival` stay, so old saves keep working.
  - Every place that names `rival` today becomes generic: `next_for_sale(state)`, `can_buy(state, shop)`, `_take_over(state, shop)`, per-shop bot revenue, objective texts built from the shop data.
  - A new module `mechanics.py` holds one small class per mechanic type (`vending`, `shelves`, `assembly`, `lunch_rush`, `rental`, `sunset_bar`, `melting`) with hooks: `start_day`, `tick`, `can_sell`, `on_sell`, `end_day`, `view`. `logic.py` finds the class through `MECHANICS[shop["mechanic"]["type"]]`.
  - `migrate()` adds missing shops (bot owner), moves `rival_revenue` to the per-shop field, adds the new state keys (zone unlocks, daily weather, mechanic state). A v6 victory save continues as RUNNING with the new goal.
- `students.py`: per-shop bundle choice (at most 3 products per shop), shops filtered by zone and opening hours, two pools.
- Browser: buildings, stations and interaction points come from one layout table per shop in `world.js`; texts, products and prices always come from the config sent by Python.

### 2. SnackBots and Mercado & Go (commit 2)
- SnackBots: three machines with capacity, instant sale, refilling from the bag (P25), random breakdown per game hour with repair fee (P26, T13), office with manager hire (P27). The manager refills each morning from his purchases and repairs automatically.
- Mercado & Go: shelf slots, morning shelf stocking (P28) with sandwich assembly, students only buy what is on the shelves, register with short scan time.
- 3D: a vending canopy with three machines and an office, a mini market with shelves and a register.

### 3. Bowl Bar and Nova Mensa (commit 3)
- Bowl Bar: assembly station (P29), ingredient set decides the result, wrong set gives a "wrong bowl" item (T20) that counts as a wrong order.
- Nova Mensa: open 11:30 to 14:30, lunch rush 12:00 to 14:00 (higher student target, T14), queue of 8, short prep times, low prices.
- 3D: a bowl bar with one assembly station, a bigger Mensa hall with a long counter and tables.

### 4. New victory condition (commit 4)
- Buying rule: only the next shop in `order` is for sale, and only when every owned shop has a hired manager.
- Victory: all shops owned, each with a hired manager. Open mode stays.
- HUD monopoly progress bar and P35. FOR SALE sign moves to whichever shop is next.
- Headless balance run (`uv run python simulation.py --campaign --seeds 30`): plays whole campaigns with a simple strategy and prints the day each shop was bought. Prices in `config.py` are tuned until the medians hit the target: Café da Esquina around day 10, then about 5 days per further shop.

### 5. Beach zone (commit 5)
- Beach area south of the campus (sand, sea, promenade), closed by a barrier with a sign until unlocked (T19, P34).
- Daily weather: wave rating and temperature, seeded per day (P30).
- Surf Shack: reusable boards and wetsuits, rental return after N game hours (T15), wetsuit drying (T16), instructor booked per day for a number of classes, wave rating scales demand (P31).
- Praia Bar: opens at the start of the sunset lighting phase, happy hour discount chosen by the player (P32, T17).
- Gelado Kiosk: freezer and display, display melts after N game hours (P33, T18), temperature scales demand.
- Beach visitors: their own pool, only in the beach zone.

## Out of scope
- More zones after the beach, random events beyond the listed mechanics.
- Selling shops again, loans, staff other than one manager per shop.
- Sound, multiplayer, new controls.
- A second wholesaler near the beach (the big map already lets you travel).

## Done when
- All nine shops are playable and buyable in order, each mechanic works as described in brief 14.3, and the new victory works (including open mode).
- Everything new is data in `config.py`; `logic.py` has no if/else chains on shop names.
- v4, v5 and v6 saves load through `logic.migrate()` (tests with saved fixtures).
- `uv run pytest` passes: all old tests plus new tests for every new rule (buying order and rule, takeover, each mechanic, zones and pools, weather, victory, migration).
- The headless balance run (median over 30 seeds) buys Café da Esquina around day 10 and each further shop about 5 days later.
- A headless Playwright playthrough buys at least two new shops (SnackBots and Mercado & Go) and uses their mechanics.
- At 8x with all students of both zones on the map the game stays smooth (frame time measured in the browser test, compared with v6).
- In-game texts in English, no em dashes anywhere.
- Brief (section 14) and this spec are up to date; work is on branch `v7`, one commit per step, never merged into `main`.

## Result (11.11.2026)
- 9 shops, 7 mechanics in `mechanics.py`, all values in `config.py`.
- Balance (simulation, 30 seeds, median day of purchase): Café da Esquina 11, SnackBots 17, Mercado & Go 22, Bowl Bar 26, Nova Mensa 30, Surf Shack 35, Praia Bar 40, Gelado Kiosk 45.
- Browser: a headless Playwright playthrough bought Café da Esquina, SnackBots and Mercado & Go through P17, refilled the machines (P25), hired the vending manager (P27), filled the shelves (P28) and scanned a customer (P09); no browser errors.
- Tests: `tests/test_v7_model.py`, `test_v7_snackbots_mercado.py`, `test_v7_bowlbar_mensa.py`, `test_v7_victory.py`, `test_v7_beach.py`; old saves in `tests/fixtures/`.
