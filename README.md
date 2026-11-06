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
| Walk | Arrow keys or WASD |
| Use / talk | E or left click |
| Confirm / cancel pop-up | Enter / Esc |
| Shopping list and stock | Tab (hold) |
| Pause | P or the pause button |
| Rotate / zoom camera | Right mouse drag / mouse wheel |
| Game speed | 1x 2x 4x 8x buttons |

## How a day works
1. 05:00 planning board: decide what to sell, the shopping list is created.
2. Walk to the wholesaler, fill the cart, pay at the checkout.
3. Back in the café: stock the goods, set prices at the counter, open (automatically at 08:00).
4. 08:00-20:00: accept orders, prepare them at the stations, hand them over. Money comes at handover.
5. 20:00: clean the four spots, read the daily summary, next day.

## Documents
- Product brief v2 (source of truth): `docs/product-brief-v2.md`
- Task spec: `specs/v2-campus-game.md`
- Architecture: `docs/architecture.md`, assumptions: `docs/assumptions.md`
- Rules for coding agents: `AGENTS.md` (Claude Code reads `CLAUDE.md`, which imports it)
