# Nova Campus Tycoon

A 3D café management game on a university campus. Plan your day, shop at the wholesaler, set prices, serve students at the counter, upgrade your café, hire a manager and buy out the competitor until you own every café on campus.

## Run
```bash
uv sync
uv run streamlit run app.py
```
The game opens in the browser (full window). It needs an internet connection because Three.js is loaded from a CDN.

## Test
```bash
uv run pytest
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
| Fix a wrong order | 🗑 Throw away / ✖ Cancel order in the tray bar |
| New game | Pause (P) → 🔄 New game |

## How a day works
1. 05:00 planning board: decide what to sell, the shopping list is created.
2. Walk to the wholesaler, fill the cart, pay at the checkout.
3. Back in the café: stock the goods, set prices at the counter, then press ⏩ to jump to 08:00 (or open from 07:00).
4. 08:00-20:00: accept orders, prepare them at the stations, hand them over. Money comes at handover.
5. 20:00: clean the four spots, read the daily summary (today, stock, competitor, last days), next day.

The game is saved after every action. Close the browser whenever you like; "Continue" on the start screen brings you back.

## Documents
- Product brief v2 (source of truth): `docs/product-brief-v2.md`
- Task specs: `specs/v4-improvements.md` (current), `specs/v3-fixes.md`, `specs/v2-campus-game.md`
- Architecture: `docs/architecture.md`, assumptions: `docs/assumptions.md`
- Rules for coding agents: `AGENTS.md` (Claude Code reads `CLAUDE.md`, which imports it)
