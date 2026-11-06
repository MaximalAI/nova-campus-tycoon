# Spec: v3 bug fixes and improvements

## Why
Playtesting v2 showed blocking bugs: the wholesaler could not be entered, the bought competitor café could not sell, and the player disappeared behind the counter. Controls felt stiff and the game mixed German and English.

## What
1. **Wholesaler:** entering, shopping and paying work. The exit gate only blocks while the cart holds unpaid goods. The leave check starts after the player was really inside.
2. **Competitor café:** after the purchase the barista stays and sells automatically. Customers get their products, pay (money goes to the player) and leave happy. The barista restocks right after the purchase and every morning (`rival_restock_plan`), paid from the player's cash.
3. **Camera:** one third-person follow camera everywhere. Walls and roofs between camera and player fade out; inside buildings the camera moves closer. The fixed counter camera is removed.
4. **Controls:** WASD walks relative to the camera, Shift runs, mouse look with pointer lock (right drag as fallback), wheel zooms. Smooth acceleration, turning and camera.
5. **Minimap:** legend with symbols for your café, competitor, wholesaler, player, students and the next goal.
6. **English:** all in-game text in English, including product names, phases, toasts and the minimap.
7. **Saves:** v2 saves still load (`logic.migrate`).

## Out of scope
- New products, new buildings or new balancing beyond the restock plan.
- Sound, mobile controls, multiplayer.

## Done when
- `uv run pytest` passes (new tests for barista, restock and migration in `tests/test_progression.py`).
- Browser test with the keyboard only: plan, walk into the wholesaler, pay, unpaid exit is blocked, paid exit works, stock arrives in the café.
- Serving at the counter keeps the player visible on screen.
- After buying the competitor, its customers are served automatically with no lost customers caused by missing staff or stock, and the player's cash rises.
- Closing, cleaning, daily summary, next morning, pause and Continue still work.
- No German text left in the game.
