# Complete game: first release

Source of truth: `docs/product-brief.md` (all sections). Builds on `specs/first-feature.md`.

## Why
The first release must be playable from the first morning to game over or victory. Only the full loop (buy, price, sell, review the day, grow) shows whether the economic model and the progression work.

## What
Everything in sections 4 to 12 of the product brief:
- Start screen with "New game" and "Continue"; header with balance, day and phase; "Save & quit".
- Morning planning: buy ingredients per shop, set prices, buy upgrades, hire employees, buy the competitor, choose which shop to serve manually.
- Demand model: 10 students, €10.00 budget, daily random utilities, shop utility factor, brute-force bundle choice, at most one coffee per student.
- Selling day: order queue, 720 s preparation budget, "Accept next order", out-of-stock items dropped, employees serve automatically, competitor bot serves automatically, "End day".
- End of day: spoilage, per-shop statistics, market share, sales chart, game-over check.
- Progression: employee (€200), competitor acquisition (€500, needs an employee in the player café), victory when both shops are owned and staffed.
- Persistence of the full game state in SQLite after every action.
- A 3D campus view (Three.js inside Streamlit) that shows the three stalls, ownership and the students. It is a visual aid only; all rules stay in `logic.py`.

## Out of scope
Employee wages, a walking 3D character, a real-time clock, multiple save slots, multiplayer.

## Done when
- `uv run pytest` passes, covering every rule in brief section 12, the demand model, a full selling day, spoilage, game over, acquisition, victory and a restart from the same database file.
- In the running app a game can be played from day 1 to victory or game over.
- Stopping and restarting the app, then clicking "Continue", restores the exact state, including an open selling day.
