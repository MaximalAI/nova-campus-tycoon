# Testing (v15)

This document explains how Nova Campus Tycoon is tested: what is tested automatically, how, and why the tests can be trusted. The rules that the tests check are described in `docs/game-logic.md`, the structure of the program in `docs/architecture.md`.

## 1. How to run the tests

```bash
uv sync                      # install the exact versions from uv.lock
uv run pytest                # all tests (about 355, ~1 minute)
uv run pytest -q tests/test_sales.py           # one file
uv run pytest -k reputation                    # all tests with "reputation" in the name
uv run ruff check .          # style and simple bugs (13 known, accepted findings)
uv run python simulation.py --campaign --seeds 30   # balance: plays whole games headless
```

## 2. What is tested and why it can be tested

All game rules are pure Python functions on a JSON-compatible state dict (`logic.apply(state, event)` returns the new state and a result). They do not need a browser, Streamlit or a database. A test therefore:

1. creates a game with a fixed seed (`logic.new_game(seed=4)`), so every random number is the same in every run,
2. prepares a situation (for example stock in the café and a student in the queue),
3. sends events exactly as the browser would (`{"type": "accept", "shop": "cafe", "student": "s0", "t": 8.2}`),
4. checks the result and the new state (money, reputation, stock, student state, error messages).

Forbidden actions must raise `GameError` and change nothing; many tests check exactly that (`pytest.raises(GameError)`), because the browser must never be able to break the rules.

## 3. The test pyramid

| Level | What | Where |
|---|---|---|
| Unit | Single rules: shelf life, prices, shopping list, utility of a bundle, password hashing, lighting values | most test files |
| Scenario | A sequence of events through `logic.apply`: a whole order from the queue to the handover, a day with closing and cleaning, buying a shop and hiring its manager | `test_sales.py`, `test_progression.py`, `test_v7_*.py` |
| Simulation | Whole days and whole campaigns played headless by `simulation.py` (students decide, queue, buy; a perfect player serves) | `test_students.py::test_same_purchases_at_1x_and_8x`, `test_v7_model.py::test_a_simulated_day_sells_in_the_new_shops`, `test_v7_victory.py::test_balance_first_shop_and_the_days_between_purchases` |
| Integration | The Streamlit page starts, the component files exist, a batch of events goes through the bridge, the database survives crashes | `test_app.py`, `test_bridge.py`, `test_persistence.py`, `test_v8_safety.py`, `test_v12_accounts.py` |

## 4. The test files

| File | Tests | What it proves |
|---|---|---|
| `test_time.py` | 15 | Clock: 1 real minute = 1 game hour at 1x, speeds 2x/4x/8x without jumps, pause, the day never runs past 21:00; phase table and its boundaries; lighting values are sensible, smooth and cover the whole day |
| `test_economy.py` | 19 | Planning and shopping list (in wholesale packs, minus usable stock), cart and payment (money, bag, cannot leave with unpaid goods), stocking in base units, price rules, opening rules, shelf life per batch (oranges 3 days), oldest batch used first, euro format |
| `test_students.py` | 17 | Pool of 40 students with budget, utilities and traits; utilities are new every day but reproducible; campus count follows the phase table and changes gradually; the student state machine only allows valid transitions; best bundle respects the budget; choice of one shop; same purchases at 1x and 8x; students never overspend |
| `test_sales.py` | 18 | Money only at the handover; one order at a time; the player must be inside; wrong items and fast service change the reputation; sold-out items make a student decide again; patience; closing cancels the order and sends the queue away; cleaning, summary numbers add up; game over when the money is gone |
| `test_progression.py` | 17 | Upgrades raise the shop factor; managers (start the next day, serve from stock, propose a plan, buy at 07:00, happy customers raise the reputation); buying a shop (yours the next morning, you run it yourself); victory and open mode |
| `test_persistence.py` | 5 | Save and continue restores the state; saving updates the same row; finished games are not offered for "Continue"; the state stays JSON after a full day; resuming resets open orders and queues |
| `test_bridge.py` | 3 | A batch runs in order and reports errors per event; an unknown event is an error, not a crash; time never runs backwards |
| `test_app.py` | 2 | The Streamlit page starts; the game files exist and export the component entry |
| `test_v4.py` | 25 | Reputation perks (demand, patience, tips), penalties (sold out, waiting, turning away, cancelling), throwing away products, stock report, summary with competitors and tips, migration of v3 saves |
| `test_v5.py` | 11 | Throwing away single products, price boards, a shop without anybody running it gets no customers, demand during lectures, day gain and chart data |
| `test_v6.py` | 5 | Objectives while a purchase is pending and after the takeover, the competitor sells on the day of the purchase, open mode after the victory |
| `test_v7_model.py` | 14 | Nine shops are complete data; prices rise from shop to shop; `logic.py` has no if-chains on shop names; config is JSON for the browser; only the next shop is for sale and only when every shop has a manager; old saves load and play a day |
| `test_v7_snackbots_mercado.py` | 13 | Vending machines (sell only what is inside, cash box until the office, breakdowns and repairs, the manager's rounds); shelves (limited space, refilling, checkout, spoilage, the manager shares the shelves) |
| `test_v7_bowlbar_mensa.py` | 10 | Bowl assembly (right and wrong ingredients); Mensa lunch hours, lunch rush and long queue |
| `test_v7_beach.py` | 18 | Beach opens after the campus; visitors stay at the beach; seeded weather; waves and temperature change demand; rental gear comes back, wetsuits dry; sunset bar and happy hour; ice cream melts |
| `test_v7_victory.py` | 4 | Monopoly progress and the "for sale" sign; victory needs every shop and every manager; **balance**: in simulated campaigns the first shop is bought around day 6 and each further shop takes about 4 days |
| `test_v8.py` | 14 | Monopoly counter, competitors in the summary, manager plans count sold-out customers, Jep (seeded spot, costs, profit), roulette (rules, payouts, fair over many spins, limits) |
| `test_v8_safety.py` | 5 | The database writes safely (full sync), a damaged save falls back to the previous state, a damaged database file is moved aside, autosave keeps the game time |
| `test_v9.py` | 11 | The wholesaler sells every base product; casino bar; slot machines (payouts, the house wins only slightly in the long run, seeded pulls, limits) |
| `test_v10.py` | 12 | Upgrades per shop, cleaning per shop (not for vending), the vending manager fills every machine, Mercado objectives, partly missing orders cost reputation |
| `test_v11.py` | 18 | Vending manager rounds, cleaning penalty, beach costs and prices, investments outside the profit, the plan of every shop, market share, a late event of yesterday cannot end the new day |
| `test_v12_accounts.py` | 13 | Passwords stored as salted hashes, broken hashes never log in, e-mail and password rules, one account per e-mail, login and kept login (token) until logout or expiry, the database keeps no password and no token, every player continues his own game |
| `test_v13_bug_fixes.py` | 12 | Manager plans capped (sold-out customers count half, at most 1.5x the best day); short cash shared between managers and complete portions; the reputation budget; cost estimate for the buy pop-up; calm sea means fewer surfers; objective after saving prices |
| `test_v14_sold_out_orders.py` | 4 | A product that sold out while waiting costs reputation at "accept"; a customer whose whole order sold out leaves instead of an error; the view sends only the summary fields of the last days |
| `test_v15.py` | 9 | One reputation rule for all customers (managers count like you, one daily budget, the summary names the reasons), partly served customers bring no plus, a broken machine is reported as broken, collected cash is not in the account yet, you never sell more than you had, game over when stuck (and not while something can still be sold) |

## 5. Balance tests with the simulation

`simulation.py` plays the game without a browser: every student follows his schedule and decides with the utility model, queues are served (by a perfect player in the shop he runs, by managers elsewhere), the simulated player plans, shops, cleans after closing (v15), brings the snack machine cash to the office, hires managers and buys the next shop whenever he can afford it while keeping a reserve of €40.

- `uv run python simulation.py --campaign --seeds 30` prints for 30 games the median day of every purchase and of the victory.
- `tests/test_v7_victory.py::test_balance_first_shop_and_the_days_between_purchases` runs a short version (3 seeds) and fails if the first purchase moves more than 3 days away from the target (day 6) or the days between purchases drift too far from 4.
- For v15 we also ran four full campaigns and checked invariants every day: money never negative, reputation within 0 to 100 and never stuck near 0 (it stayed above 20), profit = sales + tips - costs, no negative stock, the view can always be sent to the browser. All four campaigns were won on days 34 to 35.

## 6. What is not tested with pytest, and how we checked it

The browser part (3D world, animation, pop-ups) is presentation only and has no rules. It was checked by playing:

- **Manual playtests** by the team before each version (the bug lists in `specs/v13` to `specs/v15` come from them).
- **Automated browser runs** with Playwright during development: a bot creates an account, plays day 1 (planning, wholesaler, stocking, prices, serving orders), loads late-game saves (eight shops, beach open), opens every pop-up and checks for JavaScript errors. These scripts were development tools and are not part of the repository.
- **Measured checks** for specific bugs, for example: 400 sampled walking paths never cross a flower bed (v14); the game element keeps 100 % opacity while the server answers slowly (v15, the flicker fix).

## 7. Conventions

- Test names are sentences that say the rule (`test_money_only_at_handover`), so a failing test explains itself.
- Every version adds a test file for its new rules (`test_v4.py` ... `test_v15.py`) and keeps all older tests green; when a rule changes on purpose, the old test is updated with a comment that names the version.
- Tests never depend on the clock of the computer or on a network; all randomness is seeded.
