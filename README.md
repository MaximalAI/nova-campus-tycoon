# Nova Campus Tycoon

A 3D café management game on the Nova SBE campus in Carcavelos. You start with one small café and €50. Every day you plan, shop at the wholesaler, set prices and serve students at the counter. With the profit you buy upgrades, hire managers and buy out the competition shop by shop, until all nine shops on the campus and at the beach are yours: the monopoly.

**Play it:** <https://www.novacampustycoon.com>. Create an account with your e-mail address on the landing page; every account has its own saved games.

Course project for *Introduction to Programming*, Nova SBE (2026). Current version: **v15**.

## Team
| Name | Student number |
|---|---|
| Maximilian Friedrich Kienzle | 79927 |
| Marvin Jan Kramer | 79997 |
| Nicole Schatz | 79509 |
| Jan Andreas Hoffmann | 81217 |
| Jonas Vasterling | 66801 |

## Documentation: where to start

Read in this order to understand the whole project without opening the code:

1. **This README:** what the game is, how to run it, how a day works, the shops.
2. **`docs/game-logic.md`:** every feature and its rules with the numbers: time, wholesaler and stock, the student utility model, serving, reputation, money and the daily summary, managers, the monopoly race and game over, the nine shop mechanics, beach and weather, cleaning, upgrades, easter eggs, accounts and saving, guidance.
3. **`docs/architecture.md`:** how it is built: Python decides every rule, the browser (Three.js) only animates; how one player action travels from the browser through Streamlit to the rules and back; modules, the 48 events, storage, security, performance, hosting, and why this design.
4. **`docs/testing.md`:** how the ~355 automated tests work, what each test file proves, the balance simulation, and what was checked by playing.
5. **`docs/product-brief-v2.md`:** the original product decisions and design principles (source of truth for the ideas; `docs/game-logic.md` describes the current rules in detail).
6. **`specs/`:** one spec per version (Why / What / Out of scope / Done when); `specs/README.md` lists them. `docs/assumptions.md` lists decisions we made where the brief was open.

## Run the app locally
```bash
uv sync
uv run streamlit run app.py
```
The game opens in the browser (full window). It needs an internet connection because Three.js is loaded from a CDN. Locally the database is `data/game.db` (change it with the environment variable `NCT_DB_PATH`).

## Run the tests
```bash
uv run pytest
```
Balance check (plays whole games headless and prints the median day of each purchase):
```bash
uv run python simulation.py --campaign --seeds 30
```
Details: `docs/testing.md`.

## What the game does

**Principles.** Only the 3D world is on screen (no Streamlit widgets): title, HUD, pop-ups and statistics are drawn inside the game. The player is always guided: every action opens a numbered pop-up and the HUD always shows the next objective with a marker on the ground. The campus is alive: students arrive, go to lectures, crowd at lunch and react to prices, queues and service.

**How a day works**
1. **05:00** Planning board of the shop you run yourself: decide how much to sell; the game makes the shopping list.
2. **Wholesaler:** take every product from its stand (amounts start at 0, "Take the list amount" fills in the list), pay at the checkout.
3. **Back in the shop:** stock the goods, set prices at the counter, press ⏩ to jump to 08:00 (or open from 07:00).
4. **08:00 to 20:00:** students queue; accept orders, prepare them at the stations, hand them over. Money comes at the handover. Customers who wait too long leave.
5. **20:00:** clean the shop you ran (the marker leads you from spot to spot), read the daily summary, start the next day.
6. **Evening:** buy upgrades, hire a manager, buy the next shop.

**Students and prices.** 40 students (plus 20 at the beach) with a budget and a random value for every product every day. A student buys at the shop where (attractiveness x value - price) is highest. Attractiveness grows with upgrades and your reputation. So prices, reputation and stock decide your sales.

**Reputation (0 to 100).** Every customer of every shop you own counts, served by you or by a manager: served +2, partly served or sold out -1/-2, waited too long -3, wrong order -4. All customers of a day move it by at most 15. A high reputation brings more customers, more patience and tips.

**Managers.** A manager runs a shop on his own from the next morning: he proposes a plan and prices, buys at the wholesaler, serves and cleans. You can buy the next shop only when every shop you own has a manager.

**Win and lose.** You win when all nine shops are yours and each has a manager (then open mode). You lose when your cash is €0 or less at the end of a day, or when you are stuck: no stock, nothing to sell and too little money for anything at the wholesaler.

**The nine shops**

| # | Shop | Zone | What is special |
|---|---|---|---|
| 1 | Your Café | Campus | Your start: stations, counter, cleaning |
| 2 | Café da Esquina | Campus | The first competitor (€300) |
| 3 | SnackBots | Campus | Three vending machines on the campus: refill them, take out the cash and bring it to the office; machines break and need repairs. Orange rings and tags show which machine needs you |
| 4 | Mercado & Go | Campus | Limited shelf space; customers take products, you scan them at the register |
| 5 | Bowl Bar | Campus | Put bowls together from two ingredients; a wrong mix is a wrong order |
| 6 | Nova Mensa | Campus | Open 11:30 to 14:30, lunch rush, long queue |
| 7 | Surf Shack | Beach | Boards and wetsuits come back after a rental; daily wave rating |
| 8 | Praia Bar | Beach | Opens at sunset, happy hour |
| 9 | Gelado Kiosk | Beach | Ice cream melts in the display; daily temperature |

The beach opens once every campus shop is yours. Two easter eggs are hidden on the campus (`specs/v8-fixes-and-easter-eggs.md`, `specs/v9-fixes-and-casino.md` explain them for graders).

**Saving.** The game is saved after every action, every 10 seconds and when the tab is closed; the database keeps a backup of the previous state. "Continue" brings you back.

## Controls
| Action | Key |
|---|---|
| Walk | WASD (or arrow keys), hold Shift to run |
| Look around | Click the game to capture the mouse, then move the mouse (Esc releases it); dragging with a mouse button also works |
| Zoom | Mouse wheel |
| Use / talk | E, or left click |
| Confirm / cancel pop-up | Enter / Esc |
| Shopping list and stock | Tab (hold); the "i" next to "Stock" shows the full stock |
| Pause and settings | P or the pause button: sound, account and log out, save & quit, new game |
| Game speed | 1x 2x 4x 8x buttons |
| Start the day early | ⏩ under the clock (after shopping, before 08:00) |
| Fix a wrong order | ✕ on a tray slot, 🗑 throw away extras, ✖ cancel order |
| Travel | Click the minimap or press M, then a place on the big map |
| Statistics | The "i" next to the day gain |

## Technology and structure
Python (3.12 or newer), Streamlit 1.67 (v2 component), SQLite, pytest, ruff, uv; Three.js in the browser. Hosted on Render.

| Path | Role |
|---|---|
| `app.py` | Streamlit page: mounts the game, accounts, event batches, saving |
| `bridge.py` | Runs a batch of browser events through the rules |
| `logic.py` | Game state and all rules (48 events) |
| `mechanics.py` | One class per shop mechanic |
| `students.py`, `timeclock.py` | Students and their decisions; clock, phases, lighting |
| `easter_eggs.py` | Jep and the casino |
| `config.py` | All balancing values |
| `db.py`, `auth.py` | SQLite storage; accounts and password hashing |
| `simulation.py` | Headless player for tests and balancing |
| `game/` | Browser: 3D world, animation, HUD, pop-ups (no rules) |
| `tests/` | ~355 pytest tests |
| `docs/`, `specs/` | Documentation (see above) |

## Deployment (Render)
- Web service on Render, Python runtime, branch of the current version (v15).
- Build: `uv sync --frozen && uv cache prune --ci`
- Start: `uv run streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
- Persistent disk at `/var/data` and `NCT_DB_PATH=/var/data/game.db`, so accounts and saves survive deploys.
- Domain `www.novacampustycoon.com` (Namecheap DNS: `A @ 216.24.57.1`, `CNAME www nova-campus-tycoon.onrender.com`).

## Versions
Every version is its own Git branch (`v2` ... `v15`); the spec of each version explains why and what changed.

| Version | Main change |
|---|---|
| v1 | First release as a Streamlit management screen: buy ingredients, set prices, sell to 10 students, buy the competitor |
| v2 | The 3D campus game: Python decides, the browser animates |
| v3 to v6 | Fixes, reputation perks and tips, managers, the second café |
| v7 | Campus expansion: nine shops in two zones, the monopoly race |
| v8, v9 | Safety (crash-proof saves), sound, easter eggs, casino |
| v10, v11 | Shop logic per shop, cleaning, vending managers, the day summary |
| v12 | Landing page and player accounts, hosting on Render |
| v13 | Playtest fixes: manager plans and budgets, reputation cap, surf waves |
| v14 | World fixes, legal notice, sold-out orders, performance |
| v15 | Flicker fix, one reputation rule for all customers, SnackBots guidance, game over when stuck, full documentation |

## Legal notice
The legal notice (Impressum) with the team, the contact person and a disclaimer opens from the landing page footer and from the title menu. Rules for coding agents: `AGENTS.md`.
