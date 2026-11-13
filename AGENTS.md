# AGENTS.md

## Project
Nova Campus Tycoon v10, a 3D café management game: Three.js in the browser, rules in Python.
- Product brief: `docs/product-brief-v2.md` (v1: `docs/product-brief.md`)
- Current task: the spec named in the prompt, for example `specs/v10-shop-logic.md`
- Architecture: `docs/architecture.md`

## Commands
- Install dependencies: `uv sync`
- Run the app: `uv run streamlit run app.py`
- Run the tests: `uv run pytest`

## Structure
- `app.py`: Streamlit page (UI only). Mounts the game, passes event batches to `bridge.py`, saves with `db.py`.
- `bridge.py`: runs a batch of browser events through `logic.apply`.
- `logic.py`: game state and all rules (no UI, no database code).
- `mechanics.py`: one class per shop mechanic (vending, shelves, assembly, ...).
- `easter_eggs.py`: easter eggs (v8 Jep and roulette, v9 casino bar and slot machines), pure rules.
- `students.py`, `timeclock.py`: student behaviour and decisions, clock, phases, lighting (pure rules).
- `config.py`: all balancing values in one place.
- `db.py`: SQLite storage. The database file is `data/game.db` (override with the env var `NCT_DB_PATH`).
- `simulation.py`: headless day driver for tests and balancing.
- `game/`: browser code (rendering, input, animation, HUD, pop-ups). It never decides game rules.
- `tests/`: pytest tests. Tests use a temporary database (`tmp_path`), never `data/game.db`.
- `docs/product-brief-v2.md`: Campus Tycoon BRD (source of truth).
- `specs/`: task specs (Why / What / Out of scope / Done when).

## Code rules
- Money is integer cents. Game time is hours as a float (8.5 = 08:30).
- Invalid actions raise a clear error in `logic.py` and change nothing in the saved state.
- Never commit `data/`, `*.db`, `.env` or other secrets.

## Branch rules
- Never work directly on `main`. One branch per spec, named after it (for example `first-feature`).
- Work only on the workflow in the current spec. Do not build features from later sections of the brief.
- Do not commit, push or merge unless asked.

## Test and verification rules
- Tests come first: propose them, wait for review, then implement.
- Reviewed tests are the acceptance checks. Never weaken, skip or delete them to make the implementation pass.
- If a test looks wrong, stop and explain why against `docs/product-brief.md`. Change it only after explicit approval.
- Before reporting a task as done:
  1. run `uv run pytest` and show the full output,
  2. list the changed files,
  3. explain how to verify the workflow in the running app, including stopping and restarting it.
