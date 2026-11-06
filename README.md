# Nova Campus Tycoon

A day-based café management game on a university campus: buy ingredients, set prices, serve students, upgrade your shop and buy out the competitor until you hold the monopoly.

## Run
```bash
uv sync
uv run streamlit run app.py
```
The 3D campus view loads Three.js from a CDN, so it needs an internet connection. The game itself works without it.

## Test
```bash
uv run pytest
```

## How to play
1. **Morning:** buy ingredients at the wholesaler (they spoil at the end of the day), set your prices, buy upgrades or hire staff. Then click **Open shop**.
2. **Selling day:** students queue at your café. Click **Accept next order** to prepare it; every product costs preparation time from your 720 s day budget. Click **End day** when you are done.
3. **End of day:** check revenue, costs, spoilage and market share, then start the next day.
4. Hire an employee (€200) so orders are served automatically, then buy the competitor (€500). You win when you own both shops and both have an employee. If your balance is €0.00 or below at the end of a day, the game is over.

## Documents
- Product brief (source of truth): `docs/product-brief.md`
- Task specs: `specs/`
- Rules for coding agents: `AGENTS.md` (Claude Code reads `CLAUDE.md`, which imports it)
