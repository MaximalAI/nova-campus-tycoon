# Nova Campus Tycoon

A 3D café management game on a university campus. Plan your day, shop at the wholesaler, set prices, serve students at the counter, upgrade your café, hire a manager and buy out the competition shop by shop until you own every shop on campus and at Carcavelos beach (v7: the monopoly race over nine shops).

**Deployed app:** <https://www.novacampustycoon.com> (hosted on Render, see "Deployment" below). Create an account with your e-mail address on the landing page, then play; every account has its own saved game.

Course project for *Introduction to Programming*, Nova SBE.

## Team
| Name | Student number |
|---|---|
| Maximilian Friedrich Kienzle | 79927 |
| Marvin Jan Kramer | 79997 |
| Nicole Schatz | 79509 |
| Jan Andreas Hoffmann | 81217 |
| Jonas Vasterling | 66801 |

## Run the app
```bash
uv sync
uv run streamlit run app.py
```
The game opens in the browser (full window). It needs an internet connection because Three.js is loaded from a CDN.

Locally the first account you create keeps the games you saved before v12 (they had no account yet).

The legal notice (Impressum) with the team, the contact person and a disclaimer opens from the landing page footer and from the title menu.

## Deployment (Render)
- Web service on Render, Python runtime, branch of the current version (v14).
- Build command: `uv sync --frozen && uv cache prune --ci`
- Start command: `uv run streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
- A persistent disk mounted at `/var/data` and the environment variable `NCT_DB_PATH=/var/data/game.db`, so accounts and saved games survive deploys and restarts.
- Domain `www.novacampustycoon.com` (Namecheap DNS: `A @ 216.24.57.1`, `CNAME www nova-campus-tycoon.onrender.com`); `novacampustycoon.com` redirects to it.

## Run the tests
```bash
uv run pytest
```

Balance check (plays whole games headless and prints the median day of each purchase):
```bash
uv run python simulation.py --campaign --seeds 30
```

## Controls
| Action | Key |
|---|---|
| Walk | WASD (or arrow keys), hold Shift to run |
| Look around | Click the game to capture the mouse, then move the mouse: the figure turns with it (Esc releases it). Dragging with the left or right mouse button also works |
| Zoom | Mouse wheel |
| Use / talk | E, or left click (crosshair while the mouse is captured) |
| Confirm / cancel pop-up | Enter / Esc |
| Shopping list and stock | Tab (hold) |
| Pause | P or the pause button |
| Game speed | 1x 2x 4x 8x buttons |
| Start the day early | ⏩ button under the clock (after shopping, before 08:00) |
| Fix a wrong order | ✕ on a tray slot, 🗑 Throw away extras, ✖ Cancel order (tray bar) |
| Travel | Click the minimap or press M, then a place on the big map |
| Statistics | Click the day gain next to your cash (the small "i") |
| Sound | Pause (P): background music and sound effects can be switched off separately |
| New game | Pause (P) → 🔄 New game |

## How a day works
1. 05:00 planning board of the shop you run: decide what to sell, the shopping list is created.
2. At the wholesaler take every product from its stand (one stand per product, grouped by shop; the shopping list is only a reference), then pay at the checkout.
3. Back in the café: stock the goods, set prices at the counter, then press ⏩ to jump to 08:00 (or open from 07:00).
4. 08:00-20:00: accept orders, prepare them at the stations, hand them over. Money comes at handover.
5. 20:00: clean the shop you ran (the marker leads you from spot to spot), read the daily summary (today, stock, competitors, last days), next day.

Every shop has its own day plan and upgrade board; they only show that shop, and every shop has upgrades that fit it. At the wholesaler the objective leads you from stand to stand along your shopping list, then to the checkout.

Hiring a manager: he starts the next morning (that evening you still clean yourself). He proposes a shopping list and prices (pop-up); after you accept he walks to the wholesaler, takes the products from the stands, pays at the checkout and stocks the shop. He serves all day and cleans his shop after closing.

## The monopoly race (v7)
Nine shops, bought one after another. You can buy the next shop when every shop you own has a hired manager. A bought shop becomes yours the next morning; you run it yourself until you hire its manager. The HUD bar "Monopoly 3/9" shows how far you are (click it for details).

| # | Shop | Zone | What is special |
|---|---|---|---|
| 1 | Your Café | Campus | Your start: stations, counter, cleaning |
| 2 | Café da Esquina | Campus | The first competitor |
| 3 | SnackBots | Campus | Three vending machines spread over the campus (customers line up at them): refill them, collect their cash and bring it to the office; machines break down (repair for a fee). A board in the office explains the machine lights. The manager fills every machine in the morning and collects the cash in the evening |
| 4 | Mercado & Go | Campus | Limited shelf space: put the goods from the storage on the shelves (refill them any time during the day), scan the shopping at the register, clean up after closing |
| 5 | Bowl Bar | Campus | Put bowls together from ingredients; a wrong mix is a wrong order |
| 6 | Nova Mensa | Campus | Open 11:30 to 14:30, lunch rush 12:00 to 14:00, queue of 8 |
| 7 | Surf Shack | Beach | Boards and wetsuits come back after a rental, wetsuits dry; daily wave rating |
| 8 | Praia Bar | Beach | Opens at sunset, happy hour with your discount |
| 9 | Gelado Kiosk | Beach | Ice cream melts in the display; daily temperature |

The beach (south of the campus) opens once every campus shop is yours. You win when all nine shops are yours and each has a manager; then you can keep playing in open mode.

The game is saved after every action and every few seconds, and also when the tab is hidden or closed. The database runs in a crash-safe mode with a backup copy of the last good save, so a crash, a closed laptop or an empty battery costs you at most a few seconds. "Continue" on the start screen brings you back.

## Easter eggs (v8)
Two secrets are hidden on the campus. We do not spoil where; `specs/v8-fixes-and-easter-eggs.md` and `specs/v9-fixes-and-casino.md` explain them for the graders.

## Documents
- Product brief v2 (source of truth): `docs/product-brief-v2.md`
- Task specs: `specs/v14-world-ui-and-performance.md` (current), `specs/v13-playtest-bug-fixes.md`, `specs/v12-landing-page-and-accounts.md`, `specs/v11-managers-map-and-summary.md`, `specs/v10-shop-logic.md`, `specs/v9-fixes-and-casino.md`, `specs/v8-fixes-and-easter-eggs.md`, `specs/v7-campus-expansion.md`, `specs/v6-fixes.md`, `specs/v5-managers-and-polish.md`, `specs/v4-improvements.md`, `specs/v3-fixes.md`, `specs/v2-campus-game.md`
- Architecture: `docs/architecture.md`, assumptions: `docs/assumptions.md`
- Rules for coding agents: `AGENTS.md` (Claude Code reads `CLAUDE.md`, which imports it)
